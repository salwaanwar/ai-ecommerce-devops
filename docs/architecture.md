# Architecture

## Delivery flow
1. A developer pushes a feature branch; a pull request into `develop` is reviewed and merged.
2. Jenkins polls `develop` and runs the pipeline.
3. Validation and security stages: JS syntax check, Hadolint, Gitleaks, Trivy filesystem and config scans.
4. Docker image is built, scanned with Trivy, and pushed to Docker Hub tagged with the build number.
5. `helm upgrade --install` rolls the new image out to the `ecommerce` namespace (RollingUpdate, maxUnavailable 0).
6. Health check verifies `/health`.

## Runtime layout
- **Ingress:** Traefik routes traffic to the `nexvion` Service, which load-balances across pods.
- **Pod:** two containers: Nginx (app, port 8080, non-root) and nginx-prometheus-exporter (9113).
- **Namespaces:** `ecommerce` (app, Pod Security restricted), `monitoring` (Prometheus, Grafana),
  `logging` (Elasticsearch, Kibana, Fluent Bit), `traefik`.

## Observability
- Prometheus scrapes the exporter through a ServiceMonitor; Grafana visualizes pod and Nginx metrics.
- Fluent Bit tails container logs and ships them to Elasticsearch (`kubernetes-*` indices); Kibana searches them.

## Infrastructure as Code
- Terraform defines VPC, public subnet, internet gateway, route table, security group
  (SSH and Kubernetes API restricted to the admin IP), encrypted EC2 with IMDSv2.
- Ansible configures servers: base packages, application user and directories, SSH hardening, Docker.

## AI-assisted incident analysis
`ai/incident-analysis/analyze.py` reads logs from Elasticsearch (or a file), classifies errors,
assigns severity from rule and frequency, and reports probable root cause, investigation steps and
remediation. Secrets in log lines are redacted before output or any LLM use.
