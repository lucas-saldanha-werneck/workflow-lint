"""Rules that flag common reliability problems in an n8n-style workflow export.

Input is the JSON that n8n exports: {"nodes": [...], "connections": {...}, "settings": {...}}.
Everything runs offline on the file. Nothing is executed or sent anywhere.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),            # OpenAI-style key
    re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.=]{16,}"),    # literal bearer token
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),               # GitHub token
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                 # AWS access key id
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"),
]

WRITE_HINTS = ("httprequest", "emailsend", "gmail", "slack", "postgres", "mysql",
               "googlesheets", "airtable", "salesforce", "hubspot", "notion")
LLM_HINTS = ("openai", "lmchat", "agent", "anthropic", "chainllm", "gemini")
GUARD_HINTS = ("if", "switch", "wait", "filter", "code", "form", "approval")
TRIGGER_HINTS = ("trigger", "webhook", "cron", "schedule", "manual")


@dataclass
class Finding:
    rule: str
    severity: str
    node: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def _kind(node: dict) -> str:
    return str(node.get("type", "")).lower().split(".")[-1]


def _is(node: dict, hints: tuple) -> bool:
    k = _kind(node)
    return any(h in k for h in hints)


def _strings(value):
    """Yield every string inside nested parameters."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _edges(workflow: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for src, outputs in (workflow.get("connections") or {}).items():
        for branch in (outputs or {}).get("main", []) or []:
            for link in branch or []:
                out.setdefault(src, []).append(link.get("node"))
    return out


def lint_workflow(workflow: dict) -> list[Finding]:
    nodes = [n for n in workflow.get("nodes", []) if isinstance(n, dict)]
    by_name = {n.get("name"): n for n in nodes}
    edges = _edges(workflow)
    findings: list[Finding] = []

    # 1. No error handling at workflow level
    has_error_trigger = any(_kind(n) == "errortrigger" for n in nodes)
    if not (workflow.get("settings") or {}).get("errorWorkflow") and not has_error_trigger:
        findings.append(Finding("no-error-workflow", "medium", "(workflow)",
            "No error workflow is set, so a failed run is silent."))

    for n in nodes:
        name = n.get("name", "?")
        params = n.get("parameters") or {}
        if n.get("disabled"):
            findings.append(Finding("disabled-node", "low", name,
                "Node is disabled but still in the workflow. Remove it or document why."))
            continue

        # 2. Webhook without auth
        if _kind(n) == "webhook" and str(params.get("authentication", "none")).lower() == "none":
            findings.append(Finding("webhook-no-auth", "high", name,
                "Webhook accepts calls with no authentication. Anyone with the URL can trigger it."))

        # 3. Hardcoded secrets (expressions like {{ $credentials... }} or ={{ }} are fine)
        for s in _strings(params):
            if s.strip().startswith("={{") or "{{" in s and "$" in s:
                continue
            if any(p.search(s) for p in SECRET_PATTERNS):
                findings.append(Finding("hardcoded-secret", "high", name,
                    "A value looks like a secret typed into the node. Move it to a credential."))
                break

        # 4. HTTP calls with no retry and no error output
        if _kind(n) == "httprequest":
            if not n.get("retryOnFail") and n.get("onError") not in ("continueErrorOutput", "continueRegularOutput"):
                findings.append(Finding("http-no-retry", "medium", name,
                    "HTTP call has no retry and no error branch. One timeout stops the run."))

        # 5. LLM output going straight into a write action
        if _is(n, LLM_HINTS):
            for target in edges.get(name, []):
                t = by_name.get(target)
                if t and _is(t, WRITE_HINTS) and not _is(t, GUARD_HINTS):
                    findings.append(Finding("llm-direct-write", "high", name,
                        f"LLM output goes straight to '{target}' (a write action). "
                        "Add a validation or approval step in between."))

    # 6. Orphan nodes (not a trigger, no link in or out)
    linked = set(edges) | {t for ts in edges.values() for t in ts}
    for n in nodes:
        name = n.get("name", "?")
        if n.get("disabled") or _is(n, TRIGGER_HINTS):
            continue
        if name not in linked and n.get("type", "").lower().find("stickynote") < 0:
            findings.append(Finding("orphan-node", "low", name,
                "Node is not connected to anything."))

    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.node, f.rule))
    return findings
