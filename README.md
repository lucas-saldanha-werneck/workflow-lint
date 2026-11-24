# workflow-lint

Independent demo, not affiliated with Oyster.

A small command-line check for n8n-style workflow JSON exports. It reads the file, runs seven rules, and lists reliability problems before the workflow goes live. It never runs the workflow and never makes a network call.

I built it after reading the Senior AI Solutions Engineer posting. The posting asks for agents and automations that stay reliable after launch. These are the failures I check for first when I review one.

## Run it

Python 3.9 or newer, no dependencies.

```
python -m wflint examples/risky-invoice-agent.json
python -m wflint examples/safer-invoice-agent.json
python -m wflint some-export.json --json --fail-on medium
```

Exit code is 1 when a finding at or above `--fail-on` exists (default `high`), 2 when a file can't be read, 0 otherwise. That makes it usable as a CI gate on exported workflows.

## Rules

| Rule | Severity | What it flags |
|---|---|---|
| `webhook-no-auth` | high | Webhook trigger with no authentication |
| `hardcoded-secret` | high | Key, bearer token or password typed into a node instead of a credential |
| `llm-direct-write` | high | LLM or agent node wired straight into a write action (HTTP, email, database, CRM) with no check in between |
| `no-error-workflow` | medium | No error workflow and no error trigger, so failures are silent |
| `http-no-retry` | medium | HTTP request with no retry and no error output |
| `disabled-node` | low | Disabled node left in the workflow |
| `orphan-node` | low | Node connected to nothing |

## What was tested

- 8 offline tests with pytest, run in GitHub Actions on every push.
- The risky example triggers all seven rules. The safer example triggers none.
- Expression values such as `={{ $credentials.apiKey }}` are not reported as secrets.
- An empty workflow does not crash the checker.
- Exit codes 0, 1 and 2.

## What was not tested

- No real n8n export. Both example workflows are invented by me and marked as examples. Real exports have more node types and more shapes than I covered.
- Only the `main` connection type is read. Agent tool and memory connections are ignored.
- The secret patterns are a short list and will miss some formats. They can also flag a harmless string.
- Node type matching is by name fragments (`httprequest`, `agent`, `if`). A custom node with an unusual name can be misclassified.
- No other tool's format (Make, Zapier) is supported.
- Not tested on Windows.

## License

MIT
