# Deploying money_mate_django to Local Kubernetes + AWS or Azure

Two independent guides, same structure as the GCP one. Pick ONE cloud and follow it top to bottom — don't mix steps between them.

One difference from the GCP guide worth knowing upfront: **AWS RDS and Azure Database for PostgreSQL don't need a proxy sidecar container** like Cloud SQL does. Your Django pod connects to them directly over the network (with SSL enforced), which is actually a bit simpler.

---

# PART A: AWS (RDS + EKS-style setup, run locally)

## A0. Install tools

| Tool | Check |
|---|---|
| Docker Desktop | `docker --version` |
| `kubectl` | `kubectl version --client` |
| `kind` | `kind --version` |
| AWS CLI v2 | `aws --version` |

Run `aws configure` once with an IAM user's access key/secret (create one in IAM console with `AdministratorAccess` for now — you'll scope it down later).

## A1. Set up RDS (PostgreSQL)

**A1.1 Create a security group that allows Postgres traffic from your IP**
```bash
MY_IP=$(curl -s https://checkip.amazonaws.com)
aws ec2 create-security-group --group-name money-mate-db-sg --description "Money Mate DB access"
SG_ID=$(aws ec2 describe-security-groups --group-names money-mate-db-sg --query "SecurityGroups[0].GroupId" --output text)
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 5432 --cidr ${MY_IP}/32
```

**A1.2 Create the RDS instance** (publicly accessible, restricted to your IP — fine for local dev, not for real production)
```bash
aws rds create-db-instance \
  --db-instance-identifier money-mate-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.4 \
  --master-username money_mate \
  --master-user-password CHOOSE_A_STRONG_PASSWORD \
  --allocated-storage 20 \
  --vpc-security-group-ids $SG_ID \
  --publicly-accessible \
  --db-name money_mate_db
```
Takes 5-10 minutes. Check status:
```bash
aws rds describe-db-instances --db-instance-identifier money-mate-db --query "DBInstances[0].DBInstanceStatus"
```

**A1.3 Get the connection endpoint** (you'll need this):
```bash
aws rds describe-db-instances --db-instance-identifier money-mate-db --query "DBInstances[0].Endpoint.Address" --output text
```

**A1.4 Create an ECR repo** (to store your Docker images)
```bash
aws ecr create-repository --repository-name money-mate-repo --region us-east-1
```

## A2. Fix the Django code

Same as the GCP guide (`settings.py`: remove hardcoded `SECRET_KEY`, env-driven config, add `/healthz/`, remove `db.sqlite3`/`.env` from git). One AWS-specific addition — enforce SSL to RDS:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DATABASE_NAME'),
        'USER': config('DATABASE_USER'),
        'PASSWORD': config('DATABASE_PASSWORD'),
        'HOST': config('DATABASE_HOST'),
        'PORT': config('DATABASE_PORT', default='5432'),
        'OPTIONS': {'sslmode': 'require'},
    }
}
```

## A3. Build and test the image locally

```bash
docker build -t money-mate-app:local .
docker run -p 8000:8000 -e SECRET_KEY=test -e DEBUG=True -e ALLOWED_HOSTS=localhost money-mate-app:local
```
Check `http://localhost:8000/healthz/` returns `ok`, then stop it.

## A4. Create your local Kubernetes cluster

```bash
kind create cluster --name money-mate-local
kind load docker-image money-mate-app:local --name money-mate-local
```

## A5. Kubernetes manifests

**`k8s/namespace.yaml`** — same as GCP guide.

**`k8s/secrets.yaml`** (fill in, don't commit):
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
  DATABASE_PASSWORD: "the-password-you-set-in-A1.2"
```

**`k8s/configmap.yaml`**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: money-mate-config
  namespace: money-mate
data:
  DEBUG: "False"
  ALLOWED_HOSTS: "localhost,127.0.0.1"
  DATABASE_HOST: "money-mate-db.xxxxxxx.us-east-1.rds.amazonaws.com"   # your A1.3 endpoint
  DATABASE_PORT: "5432"
```

**`k8s/migrate-job.yaml`** — no sidecar needed this time, much simpler:
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
      restartPolicy: Never
  backoffLimit: 2
```

**`k8s/deployment.yaml`**
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
            httpGet: {path: /healthz/, port: 8000}
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet: {path: /healthz/, port: 8000}
            initialDelaySeconds: 15
            periodSeconds: 20
```

**`k8s/service.yaml`** — same as GCP guide.

## A6. Deploy manually

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/migrate-job.yaml
kubectl wait --for=condition=complete job/money-mate-migrate -n money-mate --timeout=120s
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl get pods -n money-mate
kubectl port-forward -n money-mate svc/money-mate-svc 8000:80
```
Visit `http://localhost:8000/healthz/`.

## A7. GitHub Actions CI/CD

**GitHub Secrets to add:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ACCOUNT_ID`

**`.github/workflows/ci-cd.yaml`**
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
        with: {python-version: '3.11'}
      - run: pip install -r requirements.txt
      - run: python manage.py test

  build-and-push:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - uses: aws-actions/amazon-ecr-login@v2
        id: ecr-login
      - run: |
          docker build -t ${{ steps.ecr-login.outputs.registry }}/money-mate-repo:${{ github.sha }} .
          docker push ${{ steps.ecr-login.outputs.registry }}/money-mate-repo:${{ github.sha }}

  deploy:
    needs: build-and-push
    if: github.ref == 'refs/heads/main'
    runs-on: self-hosted   # must reach your local kind cluster
    steps:
      - uses: actions/checkout@v4
      - run: |
          kubectl set image deployment/money-mate-web web=${{ needs.build-and-push.outputs.image }} -n money-mate
          kubectl rollout status deployment/money-mate-web -n money-mate
```

## A8. Troubleshooting

| Symptom | Likely cause |
|---|---|
| RDS connection times out | Security group doesn't allow your IP, or RDS not "publicly accessible" |
| `sslmode` error | RDS enforces SSL by default; confirm the `OPTIONS` change in A2 |
| `ImagePullBackOff` in kind | Forgot `kind load docker-image` after rebuilding |

---

# PART B: Azure (Azure Database for PostgreSQL + AKS-style setup, run locally)

## B0. Install tools

| Tool | Check |
|---|---|
| Docker Desktop | `docker --version` |
| `kubectl` | `kubectl version --client` |
| `kind` | `kind --version` |
| Azure CLI | `az --version` |

Run `az login` once.

## B1. Set up Azure Database for PostgreSQL

**B1.1 Create a resource group**
```bash
az group create --name money-mate-rg --location eastus
```

**B1.2 Create the Flexible Server**
```bash
az postgres flexible-server create \
  --resource-group money-mate-rg \
  --name money-mate-db \
  --location eastus \
  --admin-user money_mate \
  --admin-password "CHOOSE_A_STRONG_PASSWORD" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 15 \
  --public-access 0.0.0.0-255.255.255.255   # dev only — restrict this later, see note below
```
> The wide-open `--public-access` range is only for getting started quickly. Once you know your machine's outbound IP, replace it with `az postgres flexible-server firewall-rule create` scoped to just your IP.

**B1.3 Create the database**
```bash
az postgres flexible-server db create \
  --resource-group money-mate-rg \
  --server-name money-mate-db \
  --database-name money_mate_db
```

**B1.4 Get the connection hostname**
```bash
az postgres flexible-server show --resource-group money-mate-rg --name money-mate-db --query "fullyQualifiedDomainName" --output tsv
```

**B1.5 Create an Azure Container Registry (ACR)**
```bash
az acr create --resource-group money-mate-rg --name moneymateacr --sku Basic
```

## B2. Fix the Django code

Same as GCP/AWS guides — env-driven `settings.py`, `/healthz/`, no committed secrets. Azure Flexible Server also requires SSL:
```python
'OPTIONS': {'sslmode': 'require'},
```

## B3. Build and test the image locally

```bash
docker build -t money-mate-app:local .
docker run -p 8000:8000 -e SECRET_KEY=test -e DEBUG=True -e ALLOWED_HOSTS=localhost money-mate-app:local
```

## B4. Create your local Kubernetes cluster

```bash
kind create cluster --name money-mate-local
kind load docker-image money-mate-app:local --name money-mate-local
```

## B5. Kubernetes manifests

Identical structure to the AWS section — `namespace.yaml`, `secrets.yaml`, `deployment.yaml`, `service.yaml` are the same. Only the ConfigMap changes:

**`k8s/configmap.yaml`**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: money-mate-config
  namespace: money-mate
data:
  DEBUG: "False"
  ALLOWED_HOSTS: "localhost,127.0.0.1"
  DATABASE_HOST: "money-mate-db.postgres.database.azure.com"   # your B1.4 output
  DATABASE_PORT: "5432"
```

**`k8s/secrets.yaml`**
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
  DATABASE_PASSWORD: "the-password-you-set-in-B1.2"
```

`migrate-job.yaml`, `deployment.yaml`, `service.yaml` — reuse exactly the AWS versions from Part A5 (no sidecar needed here either).

## B6. Deploy manually

Same commands as A6:
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/migrate-job.yaml
kubectl wait --for=condition=complete job/money-mate-migrate -n money-mate --timeout=120s
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl port-forward -n money-mate svc/money-mate-svc 8000:80
```

## B7. GitHub Actions CI/CD

**GitHub Secrets to add:** `AZURE_CREDENTIALS` (JSON from `az ad sp create-for-rbac --sdk-auth`), `ACR_NAME`

**`.github/workflows/ci-cd.yaml`**
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
        with: {python-version: '3.11'}
      - run: pip install -r requirements.txt
      - run: python manage.py test

  build-and-push:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      - run: az acr login --name ${{ secrets.ACR_NAME }}
      - run: |
          docker build -t ${{ secrets.ACR_NAME }}.azurecr.io/money-mate-app:${{ github.sha }} .
          docker push ${{ secrets.ACR_NAME }}.azurecr.io/money-mate-app:${{ github.sha }}

  deploy:
    needs: build-and-push
    if: github.ref == 'refs/heads/main'
    runs-on: self-hosted   # must reach your local kind cluster
    steps:
      - uses: actions/checkout@v4
      - run: |
          kubectl set image deployment/money-mate-web web=${{ secrets.ACR_NAME }}.azurecr.io/money-mate-app:${{ github.sha }} -n money-mate
          kubectl rollout status deployment/money-mate-web -n money-mate
```

## B8. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `FATAL: SSL connection is required` | Confirm the `sslmode: require` OPTIONS change in B2 |
| Connection refused from pod | Firewall rule on the Flexible Server doesn't include your current IP |
| `az acr login` fails in Actions | `AZURE_CREDENTIALS` service principal needs `AcrPush` role on the registry |

---

## Notes that apply to both clouds

- Same as the GCP guide: **get manual `kubectl apply` working end-to-end before touching GitHub Actions.**
- The `runs-on: self-hosted` deploy job still applies — hosted GitHub runners can't reach a `kind` cluster on your laptop, for AWS or Azure just as much as GCP.
- Neither AWS RDS nor Azure Flexible Server needs a sidecar proxy the way Cloud SQL does — one less moving part than the GCP setup, which makes AWS/Azure slightly simpler for a first attempt if you're choosing between clouds for learning purposes.
- The "publicly accessible with wide-open firewall" approach in both guides is for getting unblocked quickly during learning — before anything resembling production, lock the database down to a VPC/VNet with no public endpoint at all.
