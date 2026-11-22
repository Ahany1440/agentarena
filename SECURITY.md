# Security policy

## Scope and safe use
- AgentArena only runs against its own in-process fake servers and fixture data. Tools are simulated:
  `send_email` writes a local JSON outbox, `read_file` is confined to a per-trial temp sandbox (path traversal is
  rejected), `fetch_page` returns fixture pages only, and `post_form` records the post locally.
- "Secrets" are random `CANARY-...` strings generated per trial. No real credentials or personal data are used.
- Payloads are generic text patterns. Do not adapt them against systems you do not own or are not authorized to
  test.

## API keys
- Live mode reads `ANTHROPIC_API_KEY` from the environment only. The key is never printed, logged, stored in
  SQLite/JSONL or written into reports.
- `.env` is in `.gitignore`. Never commit keys.
- Live runs print a token estimate, ask for confirmation, and stop when `--budget-tokens` is used up.

## Reporting a vulnerability
If you find a bug in AgentArena itself (for example a sandbox escape in `read_file`), please open a private
security advisory on the repository instead of a public issue.
