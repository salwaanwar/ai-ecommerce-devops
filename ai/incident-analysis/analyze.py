#!/usr/bin/env python3
"""
AI-assisted incident and log analysis for the e-commerce platform.

Pipeline: logs (Elasticsearch or file) -> classify -> severity -> root cause -> remediation
Modes:    rule-based (default, works offline)
          --llm adds an LLM-written summary (needs ANTHROPIC_API_KEY)
Only the Python standard library is used.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone

ES_URL = os.getenv("ES_URL", "http://localhost:9200")
SEVERITIES = ["Low", "Medium", "High", "Critical"]

HTTP_RE = re.compile(r'"[A-Z]+ (\S+) HTTP/[\d.]+" (\d{3}) ')

# Ordered from most to least specific. The first matching rule wins for each log line.
RULES = [
    {
        "id": "oom", "category": "Resource exhaustion", "severity": "Critical",
        "title": "Out-of-memory condition",
        "regex": r"oomkilled|out of memory|cannot allocate memory",
        "root_cause": "A container exceeded its memory limit or the node ran out of memory.",
        "investigate": ["Run kubectl describe pod and look for 'OOMKilled' in Last State",
                        "Compare memory usage with the limit in Grafana (namespace/pod dashboard)",
                        "Check for recent traffic spikes or memory leaks"],
        "remediate": ["Raise the memory limit in helm/ecommerce/values.yaml",
                      "Scale out replicas to spread load",
                      "Fix the leak if usage grows steadily"],
    },
    {
        "id": "crashloop", "category": "Container lifecycle", "severity": "High",
        "title": "Container crash loop",
        "regex": r"crashloopbackoff|back-off restarting failed container",
        "root_cause": "The container starts and exits repeatedly: bad config, missing dependency, or application crash.",
        "investigate": ["kubectl logs <pod> --previous to see why it exited",
                        "kubectl describe pod for exit code and events",
                        "Compare ConfigMap/Secret values with what the app expects"],
        "remediate": ["Fix the failing config or code and redeploy",
                      "Roll back with: helm rollback nexvion -n ecommerce"],
    },
    {
        "id": "image-pull", "category": "Deployment", "severity": "High",
        "title": "Image pull failure",
        "regex": r"errimagepull|imagepullbackoff|pull access denied",
        "root_cause": "The image name or tag is wrong, the registry repository is private, or the registry is unreachable.",
        "investigate": ["Check the image name/tag in the deployment",
                        "Confirm the Docker Hub repository exists and is public",
                        "Test the pull manually: docker pull <image>"],
        "remediate": ["Correct image.repository / image.tag in values.yaml",
                      "Add an imagePullSecret for private repositories",
                      "Use kind load docker-image for local clusters"],
    },
    {
        "id": "disk", "category": "Resource exhaustion", "severity": "High",
        "title": "Disk space exhausted",
        "regex": r"no space left on device",
        "root_cause": "A volume or node filesystem is full (often logs, images or data growth).",
        "investigate": ["df -h on the node and kubectl describe node (DiskPressure)",
                        "Find large log or image directories"],
        "remediate": ["Run scripts/cleanup.sh and docker system prune",
                      "Add log rotation / retention and enlarge the volume"],
    },
    {
        "id": "tls", "category": "Security / certificates", "severity": "High",
        "title": "TLS certificate problem",
        "regex": r"certificate (has expired|verify failed)|x509",
        "root_cause": "An expired, untrusted or mismatched TLS certificate.",
        "investigate": ["Inspect the certificate expiry and issuing CA", "Check the hostname matches the certificate"],
        "remediate": ["Renew or reissue the certificate", "Install the correct CA bundle"],
    },
    {
        "id": "db-auth", "category": "Database", "severity": "High",
        "title": "Database authentication failure",
        "regex": r"access denied for user|password authentication failed|authentication failed",
        "root_cause": "Wrong database credentials or a user without the required privileges.",
        "investigate": ["Compare DB_USER/DB_PASSWORD in the Kubernetes Secret with the database",
                        "Check the user's grants on the database"],
        "remediate": ["Update the Secret and restart the deployment", "Rotate the credentials if exposed"],
    },
    {
        "id": "db-timeout", "category": "Database", "severity": "High",
        "title": "Database connectivity / timeout",
        "regex": r"(database|mysql|postgres|\bdb\b).{0,60}(timeout|timed out|refused|unavailable|unreachable)|too many connections",
        "root_cause": "Database connectivity or configuration issue: the database is down or overloaded, the network path is blocked, or the connection limit is reached.",
        "investigate": ["Database availability: is the DB pod/server running?",
                        "Network connectivity: DNS, Service, NetworkPolicy, security group",
                        "Credentials: are username/password in the Secret correct?",
                        "Connection limits: max_connections vs. active connections"],
        "remediate": ["Restore or restart the database",
                      "Fix the connection string / Secret and redeploy",
                      "Add connection pooling and raise max_connections if exhausted"],
    },
    {
        "id": "upstream-timeout", "category": "Networking", "severity": "High",
        "title": "Upstream timeout / gateway error",
        "regex": r"upstream timed out|504 gateway|gateway time-?out",
        "root_cause": "A backend service responded too slowly or not at all.",
        "investigate": ["Check backend pod health and latency in Grafana", "Review recent deployments"],
        "remediate": ["Scale the backend", "Tune proxy timeouts", "Roll back a faulty release"],
    },
    {
        "id": "conn-refused", "category": "Networking", "severity": "Medium",
        "title": "Connection refused",
        "regex": r"connection refused|connect\(\) failed",
        "root_cause": "The target service is not listening: it is down, still starting, or on a different port.",
        "investigate": ["Verify the Service name, port and selector", "Check the target pod is Ready"],
        "remediate": ["Fix the port/service configuration", "Restart or scale the target workload"],
    },
    {
        "id": "permission", "category": "Security / permissions", "severity": "Medium",
        "title": "Permission denied",
        "regex": r"permission denied|eacces|forbidden",
        "root_cause": "The process lacks permission: file ownership, RBAC, or the restricted pod security profile.",
        "investigate": ["Check file/volume ownership and the container user", "Review RBAC and PodSecurity events"],
        "remediate": ["Adjust ownership/fsGroup", "Grant only the minimal RBAC permission needed"],
    },
    {
        "id": "probe", "category": "Container lifecycle", "severity": "Medium",
        "title": "Health probe failures",
        "regex": r"(readiness|liveness) probe failed",
        "root_cause": "The application is not answering /health in time: slow start, overload, or wrong probe settings.",
        "investigate": ["Test /health from inside the pod", "Check CPU throttling and startup time"],
        "remediate": ["Increase initialDelaySeconds / timeoutSeconds", "Raise CPU limits"],
    },
    {
        "id": "generic-error", "category": "Application error", "severity": "Low",
        "title": "Unclassified application errors",
        "regex": r"\b(error|exception|traceback|fatal|panic)\b",
        "root_cause": "Application-level errors that do not match a known pattern.",
        "investigate": ["Read the example lines and look for the first occurrence", "Correlate timestamps with deployments"],
        "remediate": ["Add a rule for this pattern if it recurs", "Fix the underlying code or config"],
    },
]
for _r in RULES:
    _r["compiled"] = re.compile(_r["regex"])

HTTP_5XX = {
    "id": "http-5xx", "category": "Application availability", "severity": "High",
    "title": "HTTP 5xx server errors",
    "root_cause": "The application or its backend is failing requests (crash, overload or dependency failure).",
    "investigate": ["Check pod status and restarts", "Look at request rate and error rate in Grafana",
                    "Review the deployment history for a recent change"],
    "remediate": ["Roll back the last release", "Scale out replicas", "Fix the failing dependency"],
}
HTTP_404 = {
    "id": "http-404", "category": "Client / routing", "severity": "Low",
    "title": "Repeated HTTP 404 Not Found",
    "root_cause": "Requests for missing paths: broken links, a deleted page, or automated scanning.",
    "investigate": ["Review the most requested missing paths (listed below)",
                    "Check whether a route or file was removed in a recent release",
                    "Look for one source IP generating most of the requests"],
    "remediate": ["Fix or redirect broken links", "Restore the missing page",
                  "Rate-limit or block abusive clients at the Ingress"],
}


def redact(text):
    text = re.sub(r"(?i)(password|passwd|token|secret|api[_-]?key)\s*[=:]\s*\S+", r"\1=<redacted>", text)
    return re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "<email>", text)


def load_file(path):
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip():
                out.append({"pod": os.path.basename(path), "text": line.rstrip("\n")})
    return out


def fetch_es(namespace, minutes, size=3000):
    body = {
        "size": size,
        "sort": [{"@timestamp": "desc"}],
        "query": {"bool": {"filter": [
            {"match_phrase": {"kubernetes.namespace_name": namespace}},
            {"range": {"@timestamp": {"gte": f"now-{minutes}m"}}},
        ]}},
    }
    req = urllib.request.Request(
        f"{ES_URL}/kubernetes-*/_search", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    out = []
    for hit in data["hits"]["hits"]:
        src = hit["_source"]
        k = src.get("kubernetes") if isinstance(src.get("kubernetes"), dict) else {}
        pod = k.get("pod_name") or src.get("kubernetes.pod_name") or "unknown"
        text = src.get("log") or src.get("message") or ""
        if text.strip():
            out.append({"pod": pod, "text": text.rstrip()})
    return out


def add(findings, rule, entry, count=1):
    f = findings.setdefault(rule["id"], {"rule": rule, "count": 0, "pods": set(), "examples": []})
    f["count"] += count
    f["pods"].add(entry["pod"])
    if len(f["examples"]) < 3:
        f["examples"].append(redact(entry["text"]))


def severity_for(rule, count):
    idx = SEVERITIES.index(rule["severity"])
    idx += (count >= 50) + (count >= 200)
    return SEVERITIES[min(idx, len(SEVERITIES) - 1)]


def analyze(entries):
    findings, status, missing = {}, Counter(), Counter()
    for e in entries:
        text = e["text"]
        m = HTTP_RE.search(text)
        if m:
            path, code = m.group(1), m.group(2)
            status[code[0] + "xx"] += 1
            if code == "404":
                missing[path] += 1
            elif code.startswith("5"):
                add(findings, HTTP_5XX, e)
            continue
        low = text.lower()
        for rule in RULES:
            if rule["compiled"].search(low):
                add(findings, rule, e)
                break
    total_404 = sum(missing.values())
    if total_404 >= 5:
        pods = {"nginx access log"}
        findings["http-404"] = {
            "rule": HTTP_404, "count": total_404, "pods": pods,
            "examples": [f"{p}  ({n} requests)" for p, n in missing.most_common(3)],
        }
    result = []
    for f in findings.values():
        f["severity"] = severity_for(f["rule"], f["count"])
        result.append(f)
    result.sort(key=lambda f: (-SEVERITIES.index(f["severity"]), -f["count"]))
    return result, status


def llm_summary(findings, model):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return "_LLM mode skipped: set ANTHROPIC_API_KEY to enable it._"
    digest = [{"title": f["rule"]["title"], "severity": f["severity"], "occurrences": f["count"],
               "examples": f["examples"]} for f in findings[:6]]
    prompt = ("You are a DevOps on-call assistant. Using these log findings from a Kubernetes "
              "e-commerce platform, write a short incident summary for an engineer: the most "
              "likely story, what to check first, and a safe remediation. Be concise and say "
              "when evidence is insufficient.\n\n" + json.dumps(digest, indent=2))
    body = {"model": model, "max_tokens": 700, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        return "".join(b.get("text", "") for b in data.get("content", []))
    except Exception as exc:  # network, auth, model name, etc.
        return f"_LLM call failed: {exc}_"


def build_report(findings, status, source, total, llm_text):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    overall = findings[0]["severity"] if findings else "None"
    mix = ", ".join(f"{k}: {v}" for k, v in sorted(status.items())) or "no HTTP access lines"
    lines = ["# Incident Analysis Report", "",
             f"- **Generated:** {now}", f"- **Source:** {source}",
             f"- **Log lines analysed:** {total}", f"- **HTTP status mix:** {mix}",
             f"- **Overall severity:** {overall}", ""]
    if not findings:
        lines += ["No incidents detected in the analysed logs.", ""]
    else:
        lines += ["## Summary", "", "| # | Severity | Classification | Occurrences | Sources |",
                  "|---|----------|----------------|-------------|---------|"]
        for i, f in enumerate(findings, 1):
            lines.append(f"| {i} | {f['severity']} | {f['rule']['title']} | {f['count']} | {len(f['pods'])} |")
        lines.append("")
        for i, f in enumerate(findings, 1):
            r = f["rule"]
            lines += [f"## {i}. [{f['severity']}] {r['title']}", "",
                      f"- **Category:** {r['category']}", f"- **Occurrences:** {f['count']}",
                      f"- **Sources:** {', '.join(sorted(f['pods']))}", "",
                      f"**Possible root cause:** {r['root_cause']}", "", "**Suggested investigation:**"]
            lines += [f"- {s}" for s in r["investigate"]]
            lines += ["", "**Suggested remediation:**"] + [f"- {s}" for s in r["remediate"]]
            lines += ["", "**Example log lines:**", "```"] + f["examples"] + ["```", ""]
    if llm_text:
        lines += ["## LLM-written summary", "", llm_text, ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="AI-assisted incident and log analysis")
    ap.add_argument("--file", help="analyse a log file instead of Elasticsearch")
    ap.add_argument("--namespace", default="ecommerce")
    ap.add_argument("--minutes", type=int, default=60, help="time window for Elasticsearch")
    ap.add_argument("--llm", action="store_true", help="add an LLM summary (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--model", default=os.getenv("LLM_MODEL", "claude-sonnet-5-5"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports"))
    args = ap.parse_args()

    try:
        if args.file:
            entries, source = load_file(args.file), f"file {args.file}"
        else:
            entries = fetch_es(args.namespace, args.minutes)
            source = f"Elasticsearch ({args.namespace}, last {args.minutes} min)"
    except (urllib.error.URLError, OSError) as exc:
        sys.exit(f"Cannot read logs: {exc}\nFor Elasticsearch run: "
                 "kubectl -n logging port-forward svc/elasticsearch 9200:9200")

    findings, status = analyze(entries)
    llm_text = llm_summary(findings, args.model) if args.llm else ""
    report = build_report(findings, status, source, len(entries), llm_text)
    print(report)

    os.makedirs(args.out, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(args.out, f"incident-{stamp}.md"), "w", encoding="utf-8") as f:
        f.write(report)
    payload = [{"title": f["rule"]["title"], "severity": f["severity"], "category": f["rule"]["category"],
                "occurrences": f["count"], "root_cause": f["rule"]["root_cause"],
                "remediation": f["rule"]["remediate"], "examples": f["examples"]} for f in findings]
    with open(os.path.join(args.out, f"incident-{stamp}.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\nSaved to {args.out}/incident-{stamp}.(md|json)", file=sys.stderr)


if __name__ == "__main__":
    main()
