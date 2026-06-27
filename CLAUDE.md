# wb-mqtt-bridge — agent notes

## Testing & evaluation

Declarative tests (CLI contracts now; MQTT system tests pending a broker) live in
**[`eval/`](eval/README.md) — read that README before touching anything test-related.**

Key things it establishes (don't rediscover the hard way):
- All test *execution logic* (providers, scorers) lives in the sibling repo **`../eval-commons`** —
  this repo carries only YAML + a thin `eval/Makefile`. Change behavior there, not here.
- Run tests via `make` from `eval/` (it wires the **backend** `uv` venv + global `promptfoo`):
  `make cli` (no prerequisites), `make mqtt TARGET=local|wb7`.
- Code root is `backend/`: the CLI provider uses `cwd: ../backend` and the venv is
  `../backend/.venv` (not the repo-root `.venv`).
- Tests parameterize over the **TARGET** axis (local vs WB7 controller) via `eval/profiles/*.env` —
  never bake a broker host into a test case. promptfoo env refs are `{{env.VAR}}`, not `${VAR}`.

Status: `make cli` passes (wb-openapi, broadlink-cli over a real kitchen_hood code); the MQTT
suite is pending a running broker + bridge (see `eval/README.md` → Notes/TODO).
