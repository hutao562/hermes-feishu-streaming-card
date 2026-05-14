# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A **sidecar-only** plugin that adds Feishu (Lark) streaming card messages to [Hermes Agent](https://github.com/NousResearch/hermes-agent). It patches Hermes's `gateway/run.py` at install time and runs a separate HTTP sidecar server.

- Active source: `hermes_feishu_card/`
- **`legacy/` is V2 archive — never edit.**
- Version: 3.4.0 (declared in `pyproject.toml` and `hermes_feishu_card/__init__.py`)

## Development Commands

```bash
# Install with test dependencies
pip install -e ".[test]"

# Run full test suite (CI runs exactly this)
python -m pytest -q

# Run a single test
python -m pytest tests/unit/test_config.py::test_load_defaults -q
```

No linter, typechecker, or formatter is configured. The CI workflow is simply `pytest -q`.

## High-Level Architecture

### Sidecar-Only Architecture

```
Hermes Gateway
  └─ minimal hook in gateway/run.py (injected by install/patcher.py)
       └─ hermes_feishu_card.hook_runtime
            └─ HTTP POST /events ──→  sidecar server (server.py)
                                      ├─ CardSession 状态机 (session.py)
                                      ├─ render_card() 卡片渲染 (render.py)
                                      ├─ FeishuClient tenant token / send / update (feishu_client.py)
                                      ├─ 节流、重试、锁、诊断 (server.py)
                                      └─ /health 指标 (metrics.py)
```

Hermes hook emits `message.started` / `thinking.delta` / `answer.delta` / `tool.updated` / `message.completed` / `message.failed` events as `SidecarEvent` objects. The sidecar maintains full session state and Feishu CardKit boundaries, allowing independent testing, restart, and diagnosis.

### Key Modules

| File | Responsibility |
|------|---------------|
| `install/patcher.py` | **Only code that touches Hermes.** Uses AST parsing to find `_handle_message_with_agent`, inserts 5 marker-wrapped hook blocks, creates SHA256 manifests and backups. Corrupt markers → `ValueError`. Changed files → refuses restore. |
| `hook_runtime.py` | Event builders and HTTP forwarding. Extracts data from caller's `locals()` dict — **field names must match Hermes variable names exactly** (`source`, `event`, `response`, `agent_result`, `_response_time`, `event_message_id`, `_loop_for_step`, `_run_still_current`). |
| `server.py` | HTTP sidecar. Handles `/events`, `/health`. `CardSession` objects live in `request.app[SESSIONS_KEY]`. UPDATE_MIN_INTERVAL_SECONDS = 0.5. |
| `session.py` | `CardSession` state machine. Terminal events retry 3× with exponential backoff (1s, 2s, 4s). Non-terminal update failures are silently ignored. |
| `render.py` | CardKit JSON rendering. MAX_CARD_TABLES = 5 (auto-truncates). |
| `feishu_client.py` | Tenant token caching (expire - 60s), send/update card API. |
| `config.py` | Config loading with backward compatibility (V3.2 → V3.4). |
| `events.py` | `SidecarEvent` dataclass and serialization. |
| `cli.py` | CLI entry point (`setup`, `install`, `restore`, `uninstall`, `start`, `stop`, `status`, `doctor`, `smoke-feishu-card`, `bots`). |

### Multi-Profile Support (V3.3+)

One sidecar serves multiple Hermes profiles. Sessions use `profile_id:message_id` composite keys. Each profile has independent credentials and bot routing. In multi-profile mode, `FEISHU_APP_ID`/`FEISHU_APP_SECRET` env vars do **not** apply — credentials must be in `config.yaml` per profile.

### Hook Strategy Selection (V3.4)

The installer detects Hermes version and code anchors to choose the hook strategy:
- Hermes 0.13.0+ → `gateway_run_013_plus` strategy
- `v2026.4.23` to `0.12.x` → `legacy_gateway_run` strategy

Run `doctor --config ... --hermes-dir ...` to see which strategy and anchors were detected.

## Important Constraints

- Hermes ≥ `v2026.4.23` (checked by `detect_hermes()`)
- `gateway/run.py` must not be a symlink
- `hermes_feishu_card` must be importable inside Hermes's Python environment
- Message ID fallback system (`_fallback_message_id`, `_ACTIVE_FALLBACK_MESSAGE_IDS`, `created_at_lifecycle_token`) handles dedup across parallel sessions. Do not simplify without understanding lifecycle race conditions.

## Language Convention

思考输出用中文。字段名、变量名、函数名、专用名词、工具名保持英文。

## Release Checklist

1. Bump version in `pyproject.toml` and `hermes_feishu_card/__init__.py`
2. Update `CHANGELOG.md`, `README.md`, `README.en.md`, `config.yaml.example`, `TODO.md`
3. `python -m pytest -q` → must be all green
4. `git tag -a vX.Y.Z` **AND** `gh release create vX.Y.Z` — both required
5. GitHub Release notes from CHANGELOG with `## VX.Y.Z — YYYY-MM-DD`

## Doc Test Warning

`tests/unit/test_docs.py` uses **exact string matching** (including Chinese punctuation `。`). If you change `TODO.md`, verify every asserted string still exists, or 5 doc tests will fail.
