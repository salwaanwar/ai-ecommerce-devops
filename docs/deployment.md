# Deployment Guide

## Prerequisites
Docker, kubectl, Helm, kind, Python 3. Jenkins (Windows service) needs `kubectl` and `helm`
reachable (this project copies them to `C:\Tools` and sets PATH in the Jenkinsfile) and these
credentials: `dockerhub-creds` (username + access token) and `kubeconfig` (secret file).

## 1. Local container
```bash
./scripts/deploy.sh                      # http://localhost:8082
```

## 2. Kubernetes cluster
```bash
kind create cluster --config kubernetes/cluster/kind-config.yaml
helm repo add traefik https://traefik.github.io/charts
helm install traefik traefik/traefik -n traefik --create-namespace \
  --set service.type=NodePort --set ports.web.nodePort=30080
kubectl apply -f kubernetes/namespace.yaml
```

## 3. Application (Helm)
```bash
helm upgrade --install nexvion helm/ecommerce -n ecommerce \
  --set image.repository=<dockerhub-user>/nexvion-ecommerce --set image.tag=<tag> --set image.pullPolicy=Always
kubectl -n ecommerce get pods
kubectl -n traefik port-forward svc/traefik 8095:80      # http://localhost:8095
```
Rollback: `helm history nexvion -n ecommerce` then `helm rollback nexvion <revision> -n ecommerce`.

## 4. Monitoring
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace \
  -f monitoring/prometheus/values.yaml
kubectl -n monitoring port-forward svc/monitoring-grafana 3001:80
```

## 5. Logging
```bash
kubectl apply -f logging/elk/namespace.yaml
kubectl apply -f logging/elk/elasticsearch.yaml -f logging/elk/kibana.yaml
helm repo add fluent https://fluent.github.io/helm-charts
helm install fluent-bit fluent/fluent-bit -n logging -f logging/elk/fluent-bit-values.yaml
```

## 6. Security scans
```bash
./security/scan.sh                       # reports in security/reports/
```

## 7. AI analysis
```bash
kubectl -n logging port-forward svc/elasticsearch 9200:9200
python3 ai/incident-analysis/analyze.py --minutes 120
python3 ai/incident-analysis/analyze.py --file ai/incident-analysis/samples/db-timeout.log
```

## 8. Cloud (not applied in this project)
```bash
cd terraform && terraform init && terraform validate
terraform plan -var-file=environments/dev.tfvars      # needs AWS credentials
```
Then run `ansible/playbook.yml` against the created server.
