# Deploying money_mate_django to Local Kubernetes + GCP Cloud SQL

A beginner-friendly, in-order checklist. Do the steps top to bottom — later steps depend on earlier ones.

---

## Part 0: Install tools (one-time setup)

You need these on your machine:

| Tool | What it's for | Check install |
|---|---|---|
| Docker Desktop | Build/run containers | `docker --version` |
| `kubectl` | Talk to your Kubernetes cluster | `kubectl version --client` |
| `kind` (or `minikube`) | Run a local Kubernetes cluster | `kind --version` |
| `gcloud` CLI | Talk to GCP | `gcloud --version` |
| A GitHub repo for this project | CI/CD | — |

Install `kind`: https://kind.sigs.k8s.io/docs/user/quick-start/#installation
Install `gcloud`: https://cloud.google.com/sdk/docs/install

Run `gcloud init` and `gcloud auth login` once to connect the CLI to your GCP account.

---

## Part 1: Set up the GCP side (Cloud SQL database)

**1.1 Create a GCP project** (or use an existing one) and note the **Project ID**.

```bash
gcloud config set project YOUR_PROJECT_ID
```

**1.2 Enable required APIs**
```bash
gcloud services enable sqladmin.googleapis.com artifactregistry.googleapis.com
```

**1.3 Create the Cloud SQL Postgres instance**
```bash
gcloud sql instances create money-mate-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1
```
This takes 5-10 minutes.

**1.4 Create the database and user**
```bash
gcloud sql databases create money_mate_db --instance=money-mate-db

gcloud sql users create money_mate \
  --instance=money-mate-db \
  --password=CHOOSE_A_STRONG_PASSWORD
```

**1.5 Note your instance connection name** (you'll need this later):
```bash
gcloud sql instances describe money-mate-db --format="value(connectionName)"
# looks like: YOUR_PROJECT_ID:us-central1:money-mate-db
```

**1.6 Create a service account for the Cloud SQL Proxy**
```bash
gcloud iam service-accounts create cloudsql-proxy-sa \
  --display-name="Cloud SQL Proxy"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:cloudsql-proxy-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud iam service-accounts keys create cloudsql-key.json \
  --iam-account=cloudsql-proxy-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
```
This downloads `cloudsql-key.json` — **do not commit this file to git**. Keep it in a safe local folder outside your repo.

**1.7 Create an Artifact Registry repo** (to store your Docker images)
```bash
gcloud artifacts repositories create money-mate-repo \
  --repository-format=docker \
  --location=us-central1
```

---

## Part 2: Fix the Django code (do this before building images)

Open `money_mate_django/settings.py` and make these changes:

1. **Remove the hardcoded `SECRET_KEY`** — replace with:
   ```python
   SECRET_KEY = config('SECRET_KEY')
   ```
2. Confirm `DEBUG`, `ALLOWED_HOSTS`, `DATABASE_*` all read from env vars (they mostly already do — just delete leftover hardcoded fallback values).
3. Add a health check endpoint. In `money_mate_django/urls.py`:
   ```python
   from django.http import HttpResponse
   urlpatterns += [path('healthz/', lambda r: HttpResponse('ok'))]
   ```
4. Delete `db.sqlite3` from the repo and add it (plus `.env`) to `.gitignore` — they should never be committed.
5. In `requirements.txt`, remove `django-allauth` (unused) and pin versions, e.g. `Django==5.1.2`.

Commit these changes to your GitHub repo now.

---

## Part 3: Build and test the Docker image locally

```bash
cd money_mate_django
docker build -t money-mate-app:local .
```

Quick sanity check it runs (using dummy env vars, no real DB yet):
```bash
docker run -p 8000:8000 -e SECRET_KEY=test -e DEBUG=True -e ALLOWED_HOSTS=localhost money-mate-app:local
```
Visit `http://localhost:8000/healthz/` — you should see `ok`. Stop the container (Ctrl+C) once confirmed.

---

## Part 4: Create your local Kubernetes cluster

```bash
kind create cluster --name money-mate-local
kubectl cluster-info --context kind-money-mate-local
```

Confirm it's up:
```bash
kubectl get nodes
```

**Load your image into the kind cluster** (kind can't pull from your local Docker daemon automatically):
```bash
kind load docker-image money-mate-app:local --name money-mate-local
```

---

## Part 5: Create Kubernetes manifests

Make a folder `k8s/` in your repo with these files.

**5.1 `k8s/namespace.yaml`**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: money-mate
```

**5.2 `k8s/secrets.yaml`** — fill in real values, then **do not commit this file** (add `k8s/secrets.yaml` to `.gitignore`; you'll apply it manually or via GitHub Secrets in CI).
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: money-mate-secrets
  namespace: money-mate
type: Opaque
stringData:
  SECRET_KEY: "generate-a-new-random-50-char-string"
  DATABASE_NAME: "money_mate_db"
  DATABASE_USER: "money_mate"
  DATABASE_PASSWORD: "the-password-you-set-in-step-1.4"
```

**5.3 `k8s/cloudsql-secret.yaml`** — turns your downloaded key file into a K8s Secret (run as a command, not a file you write by hand):
```bash
kubectl create secret generic cloudsql-sa-key \
  --namespace=money-mate \
  --from-file=sa-key.json=/path/to/cloudsql-key.json
```

**5.4 `k8s/configmap.yaml`**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: money-mate-config
  namespace: money-mate
data:
  DEBUG: "False"
  ALLOWED_HOSTS: "localhost,127.0.0.1"
  DATABASE_HOST: "127.0.0.1"
  DATABASE_PORT: "5432"
```

**5.5 `k8s/migrate-job.yaml`** (run migrations once, separately from the running app)
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: money-mate-migrate
  namespace: money-mate
spec:
  template:
    spec:
      containers:
        - name: migrate
          image: money-mate-app:local
          command: ["python", "manage.py", "migrate"]
          envFrom:
            - configMapRef:
                name: money-mate-config
            - secretRef:
                name: money-mate-secrets
        - name: cloud-sql-proxy
          image: gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.11.4
          args: ["--credentials-file=/secrets/sa-key.json", "YOUR_PROJECT_ID:us-central1:money-mate-db"]
          volumeMounts:
            - name: cloudsql-key
              mountPath: /secrets
              readOnly: true
      volumes:
        - name: cloudsql-key
          secret:
            secretName: cloudsql-sa-key
      restartPolicy: Never
  backoffLimit: 2
```

**5.6 `k8s/deployment.yaml`**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: money-mate-web
  namespace: money-mate
spec:
  replicas: 2
  selector:
    matchLabels:
      app: money-mate-web
  template:
    metadata:
      labels:
        app: money-mate-web
    spec:
      containers:
        - name: web
          image: money-mate-app:local
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: money-mate-config
            - secretRef:
                name: money-mate-secrets
          readinessProbe:
            httpGet:
              path: /healthz/
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /healthz/
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 20
        - name: cloud-sql-proxy
          image: gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.11.4
          args: ["--credentials-file=/secrets/sa-key.json", "YOUR_PROJECT_ID:us-central1:money-mate-db"]
          volumeMounts:
            - name: cloudsql-key
              mountPath: /secrets
              readOnly: true
      volumes:
        - name: cloudsql-key
          secret:
            secretName: cloudsql-sa-key
```

**5.7 `k8s/service.yaml`**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: money-mate-svc
  namespace: money-mate
spec:
  selector:
    app: money-mate-web
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP
```

---

## Part 6: Deploy manually (first time, to learn the flow)

Apply everything in order:
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl create secret generic cloudsql-sa-key --namespace=money-mate --from-file=sa-key.json=/path/to/cloudsql-key.json
kubectl apply -f k8s/migrate-job.yaml
kubectl wait --for=condition=complete job/money-mate-migrate -n money-mate --timeout=120s
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

**Check everything came up:**
```bash
kubectl get pods -n money-mate
kubectl logs -n money-mate deployment/money-mate-web -c web
```

**Access the app locally** (kind doesn't expose services externally by default):
```bash
kubectl port-forward -n money-mate svc/money-mate-svc 8000:80
```
Visit `http://localhost:8000/healthz/`.

---

## Part 7: Set up GitHub Actions CI/CD

**7.1 Add GitHub Secrets** (repo Settings → Secrets and variables → Actions):
- `GCP_SA_KEY` — paste the full contents of a **separate** service account key with Artifact Registry push permission
- `GCP_PROJECT_ID`
- `DJANGO_SECRET_KEY`, `DB_PASSWORD`, etc. as needed

**7.2 Create `.github/workflows/ci-cd.yaml`**
```yaml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python manage.py test

  build-and-push:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      - uses: google-github-actions/setup-gcloud@v2
      - run: gcloud auth configure-docker us-central1-docker.pkg.dev
      - run: |
          docker build -t us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID }}/money-mate-repo/app:${{ github.sha }} .
          docker push us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID }}/money-mate-repo/app:${{ github.sha }}

  deploy:
    needs: build-and-push
    if: github.ref == 'refs/heads/main'
    runs-on: self-hosted   # must be a runner that can reach your local cluster
    steps:
      - uses: actions/checkout@v4
      - run: |
          kubectl set image deployment/money-mate-web web=us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID }}/money-mate-repo/app:${{ github.sha }} -n money-mate
          kubectl rollout status deployment/money-mate-web -n money-mate
```

> **Important beginner note:** GitHub's free hosted runners run in GitHub's cloud and cannot reach a Kubernetes cluster on your laptop. The `deploy` job above needs a **self-hosted runner** (install the GitHub Actions runner on your own machine) so it can run `kubectl` against your local `kind` cluster. If you'd rather keep it simple at first, skip the `deploy` job for now and just run `kubectl set image ...` manually after each push — add automated deploy once you're comfortable.

---

## Part 8: Verify the full loop

1. Make a small code change, push to `main`.
2. Watch the Actions tab — test → build/push → (manual or self-hosted) deploy.
3. `kubectl get pods -n money-mate` — see new pods roll out.
4. `kubectl port-forward` again and confirm the change is live.

---

## Common troubleshooting

| Symptom | Likely cause |
|---|---|
| Pod stuck in `ImagePullBackOff` | Image not loaded into kind (`kind load docker-image ...`) or wrong image name |
| Pod `CrashLoopBackOff` | Check `kubectl logs -n money-mate <pod> -c web` — usually a missing env var |
| Web can't reach DB | Check the `cloud-sql-proxy` container logs: `kubectl logs <pod> -c cloud-sql-proxy -n money-mate` |
| `migrate` Job never completes | Same as above — proxy/credentials issue, or wrong instance connection name |
| 403 from Cloud SQL Proxy | Service account missing `roles/cloudsql.client`, or wrong key mounted |

---

### Recommended order to actually do this in

1. Part 1 (GCP) can run in the background while you do Part 2 (code fixes).
2. Get Part 3-6 working with **manual `kubectl apply`** first — don't touch CI/CD until you can deploy by hand and it works end-to-end.
3. Only add Part 7 (GitHub Actions) once manual deploys are solid — CI/CD automates a process you already understand, it shouldn't be how you debug the process for the first time.
