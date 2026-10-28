# Troubleshooting Log

Real problems met during implementation and their fixes.

| Symptom | Cause | Fix |
|---|---|---|
| `ports are not available: 0.0.0.0:8080` | Host port already in use | Parameterize the host port (`APP_PORT`, default 8082); keep a port plan |
| Hadolint `DL3025` fails Dockerfile lint | `HEALTHCHECK CMD` in shell form | Use exec form: `CMD ["sh","-c","..."]` |
| Ansible: `community.general.yaml` callback removed | Old config for new ansible-core | Use `callback_result_format = yaml` |
| Ansible: `ansible_virtual_type` undefined | Facts no longer top-level variables | Set `is_container` in the inventory instead |
| Pods `ImagePullBackOff` | Registry image missing/private | Make repo public, or `kind load docker-image` for local images |
| `curl localhost:8085` returned a foreign nginx 404 | Another listener on the host port | Port-forward Traefik to a free port |
| Grafana pod `2/3` for minutes | Large image still pulling, slow start | Wait; pre-pull with `docker pull` + `kind load` |
| Helm chart files vanished after `git checkout` | Branch lacked the chart | Restore with `git checkout <branch> -- helm/`; merge before branching |
| Trivy `unknown flag: --no-progress` | Flag unsupported by `trivy config` | Remove it from the config command only |
| Jenkins: `'helm' is not recognized` | Service account does not see user-installed tools | Copy to `C:\Tools` and set PATH in the Jenkinsfile |
| `Changes must be made through a pull request` | Branch protection working as intended | Work on a feature branch and open a PR |
| Working on `/mnt/c/...` in WSL | Slow I/O, permission quirks | Keep the repo in the Linux filesystem (`~/`) |

## Useful diagnostics
```bash
kubectl -n <ns> get pods
kubectl -n <ns> describe pod <pod>      # read Events
kubectl -n <ns> logs <pod> --previous
helm history <release> -n <ns>
curl -s localhost:9200/_cat/indices?v
```
