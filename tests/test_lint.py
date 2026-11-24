import json
from pathlib import Path

from wflint.lint import lint_workflow
from wflint.cli import main

EX = Path(__file__).parent.parent / "examples"


def rules(wf):
    return {f.rule for f in lint_workflow(wf)}


def load(name):
    return json.loads((EX / name).read_text())


def test_risky_example_flags_everything():
    assert rules(load("risky-invoice-agent.json")) == {
        "no-error-workflow", "webhook-no-auth", "hardcoded-secret",
        "http-no-retry", "llm-direct-write", "disabled-node", "orphan-node"}


def test_safer_example_is_clean():
    assert lint_workflow(load("safer-invoice-agent.json")) == []


def test_findings_sorted_high_first():
    sev = [f.severity for f in lint_workflow(load("risky-invoice-agent.json"))]
    assert sev == sorted(sev, key={"high": 0, "medium": 1, "low": 2}.get)


def test_expression_value_is_not_a_secret():
    wf = {"nodes": [{"name": "A", "type": "n8n-nodes-base.set",
                     "parameters": {"v": "={{ $credentials.apiKey }}"}}],
          "settings": {"errorWorkflow": "x"}}
    assert "hardcoded-secret" not in rules(wf)


def test_error_trigger_node_counts_as_error_handling():
    wf = {"nodes": [{"name": "E", "type": "n8n-nodes-base.errorTrigger", "parameters": {}}]}
    assert "no-error-workflow" not in rules(wf)


def test_http_with_error_output_is_ok():
    wf = {"nodes": [{"name": "H", "type": "n8n-nodes-base.httpRequest",
                     "onError": "continueErrorOutput", "parameters": {}}],
          "settings": {"errorWorkflow": "x"}}
    assert "http-no-retry" not in rules(wf)


def test_empty_workflow_does_not_crash():
    assert rules({}) == {"no-error-workflow"}


def test_cli_exit_codes(tmp_path, capsys):
    assert main([str(EX / "risky-invoice-agent.json")]) == 1
    assert main([str(EX / "safer-invoice-agent.json")]) == 0
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    assert main([str(bad)]) == 2
