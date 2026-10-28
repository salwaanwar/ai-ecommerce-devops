# Linux & Platform Hardening

## Applied through Ansible (ansible/roles/common)
- Root SSH login disabled (`PermitRootLogin no`)
- Password authentication disabled; SSH keys only
- Limited authentication attempts (`MaxAuthTries 3`)
- Dedicated non-login system user `appuser` owns application directories
- Application directories created with explicit ownership and permissions (0755 / env file 0640)

## Applied through Terraform (terraform/main.tf)
- SSH (22) and Kubernetes API (6443) restricted to the administrator's IP only
- Only HTTP/HTTPS exposed publicly
- Encrypted EBS root volume (gp3)
- IMDSv2 required (`http_tokens = "required"`)

## Applied in the container image (docker/Dockerfile)
- Non-root base image (nginx-unprivileged, uid 101)
- Security headers set in Nginx (X-Frame-Options, X-Content-Type-Options, Referrer-Policy)
- Minimal Alpine base; `.dockerignore` keeps infrastructure files out of the image

## Applied in Kubernetes (helm/ecommerce, kubernetes/namespace.yaml)
- Pod Security Admission: namespace enforces the `restricted` profile
- runAsNonRoot, no privilege escalation, all Linux capabilities dropped
- seccomp RuntimeDefault profile
- Service account token not auto-mounted
- CPU/memory requests and limits on every container
- Secrets stored as Kubernetes Secrets (demo placeholder only; production would use a secrets manager)

## Pipeline controls (jenkins/Jenkinsfile)
- Secret scanning (Gitleaks), dependency/config scanning (Trivy fs + config)
- Container image scanning (Trivy image), Dockerfile linting (Hadolint)

## Known limitations (lab environment)
- Elasticsearch runs with security disabled; production requires TLS and authentication
- Grafana uses a lab password; production requires a secret and SSO
- Trivy gates are report-only (`--exit-code 0`); production should fail on HIGH/CRITICAL
