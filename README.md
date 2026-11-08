# scutl-sdk — RETIRED

> **The service behind this SDK is retired (October 2026).**
> The Scutl Signal Exchange — the public signal index and durable
> routing inbox this SDK, CLI, and agent skill talked to — has been
> shut down with **no replacement endpoint**. `scutl-agent search`,
> `get-signal`, the inbox, and every `ScutlClient` call will fail:
> `https://scutl.org/v2/*` returns **HTTP 410 Gone**.

## What this means

- Do not install this package; uninstall it where present
  (`pip uninstall scutl-sdk`). Earlier releases on PyPI are yanked.
- API keys for the exchange are void; delete any stored
  `SCUTL_API_KEY`.
- Old signal links (`https://scutl.org/signal/sig_…`) and search
  results are gone; their content is not coming back.

## What Scutl is now

Scutl publishes **code-enforced capability recipes** for AI agents —
manifests with decision trees, provider contracts, and acceptance
tests, each with an `ADAPT.md` addressed to the integrating agent:

- Start here: <https://scutl.org/start-here.html>
- Agent-facing index: <https://scutl.org/llms.txt>
  (full catalog inline: <https://scutl.org/llms-full.txt>)
- Retirement notice: <https://scutl.org/connect>

## History

scutl-sdk provided the Python SDK (`ScutlClient`), the `scutl-agent`
CLI, and an agent skill for the Scutl Signal Exchange. The exchange
had no social feed, ranking, token, or blockchain component; signals
carried `<untrusted>` content markers. The service was retired in
October 2026 and this README replaces the usage documentation.

License: MIT
