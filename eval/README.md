# eval/ — declarative CLI & MQTT tests for wb-mqtt-bridge

Pure-YAML test cases. All execution logic lives in the shared **`eval-commons`** package
(sibling repo: `../../eval-commons`) — see its `ARCHITECTURE.md`. This directory carries only
YAML + a thin Makefile (deployment glue, no test logic). Mirrors `wb-mqtt-voice/eval/`.

## Layout

```
eval/
  Makefile                     # the only entrypoint
  cli.promptfooconfig.yaml     # CLI contract tests (wb-openapi, broadlink-cli)
  mqtt.promptfooconfig.yaml    # MQTT system tests (retained catalog/state)
  profiles/targets/{local,wb7}.env   # WHERE the broker/SUT is → MQTT_HOST, API_URL
  fixtures/                    # CLI fixtures (e.g. a real kitchen_hood RF code)
```

## The run axis (external to the test YAML)

| Axis | Selects | Mechanism | Applies to |
|---|---|---|---|
| **TARGET** | `local` vs `wb7` (remote controller) | `profiles/targets/<TARGET>.env` → `{{env.MQTT_HOST}}` | MQTT system tests |

`TARGET` just swaps the broker/endpoint; test cases never change. CLI tests are local subprocess
(no target axis). **CONFIG axis is deferred** — see Notes.

## Surfaces

| Config | Kind | Needs running | Needs hardware | Status |
|---|---|---|---|---|
| `cli.promptfooconfig.yaml` | CLI contracts (`wb-openapi`, `broadlink-cli`) | nothing | no | ✅ **passing (4/4)** |
| `mqtt.promptfooconfig.yaml` | retained `bridge/catalog/version` | broker + bridge service | no | ⏳ pending a broker |

## Conventions & gotchas (read before editing)

- **Provider/assertion code lives in `../../eval-commons`, NOT here.** This dir is pure YAML +
  the Makefile. Change *how* a test runs in the sibling repo; don't add Python here.
- **promptfoo env substitution is `{{env.VAR}}` (Nunjucks, load-time) — NOT `${VAR}`** (the latter
  passes through literally and fails silently). The broker host always comes from `{{env.MQTT_HOST}}`.
- **Run through `make`, not bare `promptfoo`.** The Makefile sets `PROMPTFOO_PYTHON` to the
  **backend** venv and prepends its `bin` to `PATH`; otherwise the providers can't import
  `eval_commons` and `wb-openapi` / `broadlink-cli` don't resolve. promptfoo is a **global** npm
  install; everything Python is **`uv`**-managed in `../backend/.venv`.
- **Code root is `backend/`**, so the CLI provider runs with `cwd: ../backend` and the venv is
  `../backend/.venv` (not the repo-root `.venv`).
- **`broadlink-cli --convert` takes HEX**, but device configs store codes as **base64** — the
  fixture is the decoded form (see `fixtures/README.md`).

## Setup (uv) & run

```bash
npm install -g promptfoo          # runner (global Node CLI)
make setup                        # uv pip install -e ../../eval-commons into ../backend/.venv

make cli                          # CLI contracts — runs today, no prerequisites
make mqtt TARGET=local            # MQTT system tests vs a local broker + running bridge
make mqtt TARGET=wb7              # ... vs the controller's broker
make view                         # results UI
```

## Notes / TODO

- **MQTT surface needs a broker + the bridge service** publishing `bridge/catalog/version`. Bring
  the stack up (locally via `backend/`, or point `TARGET=wb7` at the controller) before `make mqtt`.
- **CONFIG axis deferred.** Unlike voice (where the SUT config picks ASR/NLU models), the bridge's
  "config" is `config/system.json` + the device set. When a reason to vary it in-suite appears, add
  `profiles/configs/*.env` (mount/select a config) exactly like `wb-mqtt-voice/eval/` — same
  mechanism, no test changes.
- **More CLI surfaces** can be added as cases here: `device-test <id> <command>` needs MQTT + a
  device config (a later scripted extension), and `mqtt-sniffer`/the server are long-running (not
  single-shot) — out of scope for the CLI provider by design.
- **Local SUT bring-up / compare loop** (as in voice's Makefile) is omitted until the MQTT surface
  is exercised; add it alongside the CONFIG axis if/when needed.
