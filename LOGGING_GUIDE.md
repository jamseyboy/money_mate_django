# Logging Guide — Money Mate (Django)

This project uses a **custom dynamic file handler** instead of Django's default logging setup. Rather than sending everything to one file, each logger's output is automatically split into its own `.log` file, named after the logger. This guide explains how it works, how to control it, and how to use it in your own code.

---

## 1. How it works

The relevant pieces live in two places:

- **`money_mate_django/settings.py`** — configures Django's `LOGGING` dict and points the root logger at the custom handler.
- **`money_mate_django/log_handlers.py`** — defines `DynamicFileHandler`, a custom `logging.Handler`.

### `DynamicFileHandler`

```python
class DynamicFileHandler(logging.Handler):
    """
    A custom handler that reads the log's 'name' and dynamically
    routes it to a file named <name>.log
    """
```

- On each log record, it reads `record.name` — this is the logger's name (the `{name}` you see in the log line), which is normally the dotted module path that called `logging.getLogger(__name__)`.
- If this is the first time that logger name has been seen, it lazily creates a `logging.FileHandler` writing to `LOG_DIR/<logger_name>.log`.
- Every subsequent record from that same logger name is appended to the same file.
- On shutdown, `close()` flushes and closes every file handler it created.

**In short: one log file per logger name, created on demand.**

### Where files are written

In `settings.py`:
```python
LOG_DIR = BASE_DIR / 'logs'
```

So logs are written to a `logs/` directory at the project root, e.g.:
```
logs/
├── django.request.log
├── django.server.log
├── django.db.backends.log
├── loginModule.views.log
├── workbook.views.log
└── ...
```

> `logs/` is already listed in `.gitignore`, so log files are never committed.

### Root logger configuration

`settings.py` wires the **root logger** (`''`) to this handler, which means *any* logger in the project — Django's own, your apps', or third-party libraries' — gets routed through it unless overridden:

```python
LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} [{name}] {message}',
                'style': '{',
            },
        },
        'handlers': {
            # Pointing this to the custom class for money_mate_django/log_handlers.py
            'dynamic_router': {
                'level': LOG_LEVEL,
                'class': 'money_mate_django.log_handlers.DynamicFileHandler',
                'log_dir': LOG_DIR,
                'formatter': 'verbose',
            },
        },
        'loggers': {
            # We use the empty string '' to catch ALL logs globally (the root logger)
            '': {
                'handlers': ['dynamic_router'],
                'level': LOG_LEVEL,
            },
            # silencing noisy dependencies:
            'django.utils.autoreload': {
                'level': 'WARNING',
            },
            'django.server': {
                'handlers': [],  # Empty handlers forces it to look at the parent ('')
                'level': LOG_LEVEL,
                'propagate': True,
            },

            'django.db.backends': {
                'handlers': [],
                'level': LOG_LEVEL,
                'propagate': True,
            },
        },
    }
else:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': True,
        'handlers': {'null': {'class': 'logging.NullHandler'}},
        'loggers': {'': {'handlers': ['null'], 'level': 'CRITICAL'}}
    }
```

Key points:
- `'' ` (the root logger) is the catch-all — everything not explicitly configured propagates up to it and lands in the dynamic handler.
- `django.server` and `django.db.backends` are declared with **empty `handlers: []`** but `propagate: True`, so their records still reach the root logger's handler instead of being duplicated. This is how request logs and SQL query logs end up split into their own files (`django.server.log`, `django.db.backends.log`) without being handled twice.
- `django.utils.autoreload` is set to `WARNING` only, to avoid noisy "changed file detected" spam.

### Log format

Every line uses the `verbose` formatter:
```
{levelname} {asctime} [{name}] {message}
```
Example:
```
INFO 2026-07-18 10:32:04,112 [loginModule.views] User admin logged in
```

---

## 2. Turning logging on/off
Two environment variables (read via `django-environ` in `settings.py`) control logging globally, and should go in your `.env` file:

| Variable | Default | Effect |
|---|---|---|
| `ENABLE_LOGGING` | `True` | If `False`, logging is switched to a `NullHandler` at `CRITICAL` level — i.e. effectively disabled. |
| `LOG_LEVEL` | `INFO` | Minimum level captured (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). |

Example `.env` entries:
```env
ENABLE_LOGGING=True
LOG_LEVEL=DEBUG
```

Setting `ENABLE_LOGGING=False` swaps in this fallback config instead, silencing everything:
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {'null': {'class': 'logging.NullHandler'}},
    'loggers': {'': {'handlers': ['null'], 'level': 'CRITICAL'}}
}
```

---

## 3. Using logging in your own code

The project already follows this pattern in `loginModule/views.py`:

```python
import logging

logger = logging.getLogger(__name__)
```

Then log inside your views/services as needed:
```python
logger.info("User %s logged in", user.username)
logger.warning("Failed login attempt for %s", username)
logger.error("Unexpected error while processing transaction", exc_info=True)
```

**Because the handler names files after `record.name` (which equals `__name__`), each module automatically gets its own log file** — no extra config needed per app. For example:
- `logging.getLogger(__name__)` inside `loginModule/views.py` → `logs/loginModule.views.log`
- `logging.getLogger(__name__)` inside `workbook/views.py` → `logs/workbook.views.log`

Always use `logging.getLogger(__name__)` (not a hardcoded string) so log files line up predictably with your module structure.

### Log levels — when to use which

| Level | Use for |
|---|---|
| `DEBUG` | Verbose diagnostic detail, useful only while developing |
| `INFO` | Normal operational events (request handled, user logged in, job completed) |
| `WARNING` | Something unexpected but recoverable (deprecated usage, retryable failure) |
| `ERROR` | An operation failed and needs attention; pair with `exc_info=True` inside `except` blocks |
| `CRITICAL` | The application itself may be unable to continue |

---

## 4. Viewing logs

### Locally / without Docker
```bash
tail -f logs/loginModule.views.log
tail -f logs/django.server.log
```

### Inside Docker
The `docker-compose.yml` mounts `./logs` into both containers:
```yaml
volumes:
  - ./logs:/logs
```
So log files are visible on the host machine at `./logs/` even though the app runs inside a container. You can tail them the same way:
```bash
tail -f logs/django.db.backends.log
```

Or view container stdout/stderr (separate from these files, captured by Docker's own JSON logging driver):
```bash
docker compose logs -f web
```

> Note: the app's own logging (via `DynamicFileHandler`) writes to files under `logs/`, while `docker compose logs` shows whatever is printed to stdout/stderr by the process itself (e.g. Gunicorn/runserver startup messages, uncaught exceptions before the logger initializes).

---

## 5. Adding a per-module or per-app override

If you want a specific logger to behave differently (e.g. silence a noisy third-party library, or set a different level for one app), add it to the `loggers` dict in `settings.py`, following the same pattern used for `django.server` and `django.db.backends`:

```python
'loggers': {
    # ... existing entries ...
    'workbook': {
        'handlers': [],       # let it propagate to the root handler
        'level': 'DEBUG',     # but capture more detail for this app
        'propagate': True,
    },
},
```

This still lands in `logs/workbook.*.log` files via the same `DynamicFileHandler`, just at a different verbosity.

---

## 6. Gotchas / things to watch

- **File handle growth**: `DynamicFileHandler` keeps one open `FileHandler` per unique logger name for the lifetime of the process (`self._handlers` dict). In a codebase with many modules this is fine, but if you ever generate logger names dynamically (e.g. `logging.getLogger(f"user.{user_id}")`), this handler will open a new file — and a new file handle — per unique name and never close it until shutdown. Avoid dynamic/unbounded logger names with this handler.
- **No log rotation**: unlike `RotatingFileHandler`, `DynamicFileHandler` never rotates or truncates files — they grow indefinitely. For long-running production deployments, consider adding rotation (see below) or shipping logs to an external aggregator.
- **`logs/` must be writable**: the directory is created automatically (`log_dir.mkdir(parents=True, exist_ok=True)`), but the container/user running Django needs write permission to it. In Docker this is mounted as a host volume, so check host-side permissions if you see `PermissionError`.
- **Logging disabled ⇒ silent failures**: with `ENABLE_LOGGING=False`, *everything* below `CRITICAL` is dropped, including Django's own error logging. Keep this `True` in any environment where you need to debug issues.

### Optional improvement: add rotation
If log file size becomes a problem, you can extend `DynamicFileHandler` to use `RotatingFileHandler` instead of the plain `FileHandler` when creating per-logger files:
```python
from logging.handlers import RotatingFileHandler

fh = RotatingFileHandler(file_path, maxBytes=5 * 1024 * 1024, backupCount=3)
```

---

## 7. Quick reference

| Task | How |
|---|---|
| Enable/disable logging | `.env` → `ENABLE_LOGGING=True/False` |
| Change verbosity | `.env` → `LOG_LEVEL=DEBUG` |
| Log from your code | `logger = logging.getLogger(__name__)` then `logger.info(...)` |
| Find a module's logs | `logs/<dotted.module.name>.log` |
| Watch logs live (Docker) | `tail -f logs/<name>.log` or `docker compose logs -f web` |
| Silence a noisy logger | Add an entry under `LOGGING['loggers']` in `settings.py` |
