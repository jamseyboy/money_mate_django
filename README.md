# Money Mate (Django)

Money Mate is a Django REST backend (using django-ninja) with a PostgreSQL database. It ships with a `Dockerfile` (web app image) and a `docker-compose.yml` (web app + PostgreSQL database), so the whole stack can be pulled/built and run on any machine with Docker installed — no local Python or PostgreSQL install required.

This guide covers:
1. Prerequisites
2. Getting the code
3. Environment configuration
4. Downloading/building the images and running the app
5. Post-start setup (migrations, superuser)
6. Useful commands
7. Running without Docker (optional/manual setup)
8. Troubleshooting

---

## 1. Prerequisites

Install these on the machine you want to run the app on:

- **Docker Engine** (20.10+) — https://docs.docker.com/get-docker/
- **Docker Compose** (v2, usually bundled with Docker Desktop as `docker compose`)
- Git (to clone the repo) — optional if you already have the project as a zip

Verify installation:
```bash
docker --version
docker compose version
```

---

## 2. Getting the code

If you have the project as a zip file, unzip it:
```bash
unzip money_mate_django-main.zip
cd money_mate_django-main
```

Or clone it from source control if available:
```bash
git clone <your-repo-url>
cd money_mate_django-main
```

---

## 3. Environment configuration

The app reads configuration from a `.env` file in the project root (via `django-environ`). This file is **not committed to git** (see `.gitignore`), so you need to create it yourself.

Create a file named `.env` in the project root with the following variables:

```env
# Django
SECRET_KEY=change-this-to-a-long-random-string
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (must match the values Docker Compose uses to start Postgres)
DATABASE_NAME=money_mate_db
DATABASE_USER=money_mate
DATABASE_PASSWORD=money_mate_password
DATABASE_HOST=db
DATABASE_PORT=5432
```

Notes:
- `DATABASE_HOST=db` because inside Docker Compose the database container is reachable by its service name `db`. If you later run Django **outside** Docker against the same database, change this to `localhost`.
- Generate a real `SECRET_KEY` for anything beyond local testing, e.g.:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(50))"
  ```

---

## 4. Downloading the images and running the app

This project uses two containers, defined in `docker-compose.yml`:

| Service | Image | Where it comes from |
|---|---|---|
| `db` | `postgres:15-alpine` | Pulled directly from Docker Hub |
| `web` | built from the project's `Dockerfile` | Built locally from source (Django + Gunicorn) |

You don't need to pull anything by hand — `docker compose` handles both steps for you.

### Step 1 — Pull the database image and build the web image
```bash
docker compose pull db
docker compose build web
```

### Step 2 — Start the stack
```bash
docker compose up -d
```

This will:
- Start the `db` (PostgreSQL) container and wait until it reports healthy
- Start the `web` (Django) container, run database migrations, and start the dev server on port `8000`

### Step 3 — Check it's running
```bash
docker compose ps
docker compose logs -f web
```

Open your browser to:
```
http://localhost:8000
```

> **Note on the web container's startup command:** the `command:` in `docker-compose.yml` currently lists both `runserver` and `gunicorn` on the same line, which only runs the first one (`runserver`). For local/dev use this is fine (and matches `DEBUG: 'True'` in the compose file). If you want the container to run production-style with Gunicorn instead, edit the `command:` in `docker-compose.yml` to just:
> ```yaml
> command: >
>   sh -c "python manage.py migrate &&
>          gunicorn money_mate_django.wsgi:application --bind 0.0.0.0:8000"
> ```

---

## 5. Post-start setup

### Run migrations manually (if needed)
Migrations already run automatically on container start, but you can re-run them any time:
```bash
docker compose exec web python manage.py migrate
```

### Create an admin (superuser) account
```bash
docker compose exec web python manage.py createsuperuser
```
Then log in to the Django admin at:
```
http://localhost:8000/admin
```

### Collect static files (already run once during image build)
```bash
docker compose exec web python manage.py collectstatic --noinput
```

---

## 6. Useful commands

| Action | Command |
|---|---|
| Start in the background | `docker compose up -d` |
| Start with logs in foreground | `docker compose up` |
| Stop containers | `docker compose down` |
| Stop and delete the database volume (⚠ wipes data) | `docker compose down -v` |
| Rebuild the web image after code changes | `docker compose build web` |
| Tail logs | `docker compose logs -f` |
| Open a shell in the web container | `docker compose exec web sh` |
| Open a Django shell | `docker compose exec web python manage.py shell` |
| Connect to Postgres via psql | `docker compose exec db psql -U money_mate -d money_mate_db` |

---

## 7. Running without Docker (optional)

If you'd rather run the app directly on your machine:

1. Install **Python 3.11** and **PostgreSQL 15** locally.
2. Create and activate a virtual environment:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a local Postgres database/user matching your `.env` values, and set `DATABASE_HOST=localhost` in `.env`.
5. Run migrations and start the dev server:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py runserver 0.0.0.0:8000
   ```

---

## 8. Troubleshooting

- **`web` container keeps restarting / can't connect to database**: make sure `DATABASE_HOST=db` in `.env` when running under Docker Compose, and that the values in `.env` match what Postgres was initialized with. If you already created the Postgres volume with different credentials, either delete it (`docker compose down -v`) or update `.env` to match.
- **Port already in use**: if `5432` or `8000` is taken on your machine, change the left-hand side of the `ports:` mapping in `docker-compose.yml` (e.g. `"8001:8000"`).
- **`.env` not picked up**: confirm the file is named exactly `.env` and sits in the same folder as `manage.py` and `docker-compose.yml`.
- **Changes to code not reflected**: the `web` service mounts the project folder as a volume, so code edits should appear immediately with `runserver`. If running Gunicorn instead, restart the container: `docker compose restart web`.
