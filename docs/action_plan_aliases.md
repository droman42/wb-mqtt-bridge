# Action-plan ID aliases — old → new (one-time map)

**Status:** FROZEN reference. The 2026-06-30 re-ID (§5.2 #5 / DOC-9) moved the ledger from the
positional `P0…P4 / #n / §5.1` scheme to stable `PREFIX-N` workstream-serial IDs
(see `docs/design/ledger_format_convergence.md`). The **active ledger and the DONE file use the new
IDs**; the **journal keeps its historical prose** (back-refs like "§P3.7 #19" or "§5.1 #7" are not
rewritten). This table resolves any old reference to its new ID. New IDs are assigned once and never
renumbered; folded/retired tasks keep their number as a tombstone.

## By workstream (new ← old)

### DRV — device drivers
| New | Old | Task |
|---|---|---|
| DRV-1 | §5.1 #7 | Per-driver HW verification pass |
| DRV-2 | §5.1 (Apple TV apps) | Apple TV app launching |
| DRV-3 | §5.1 (IR-learn page) | IR-code learning page |
| DRV-4 | §5.1 (LG audio_output) | LG TV `audio_output` rework + `watch_tv` |
| DRV-5 | §5.1 (force flag) | Per-action `force` escape hatch |
| DRV-6 | §5.1 (IR ROM tooling) | IR ROM backup/restore — remaining play-test |
| DRV-7 | §5.1 (ESP32 scaffold) | ESP32 transport-bridge firmware (PARKED) |

### SCN — scenarios / topology / reconciler
| New | Old | Task |
|---|---|---|
| SCN-1 | P0.5 #12 | Scenario layer rebuild (Harmony/reconciler) |
| SCN-2 | §5.1 (manual-notes baseline) | Transition-aware manual notes — baseline |
| SCN-3 | P3.6 | Round-2 music scenarios |
| SCN-4 | P4 #7 | Scenario↔WB rebuild (mandatory design) |
| SCN-5 | §5.2 #6 | Transition-aware manual notes — activation-time half |

### VWB — voice-integration + native WB onboarding
| New | Old | Task |
|---|---|---|
| VWB-1 | §P3.7 #13 | Generic WB-passthrough driver |
| VWB-2 | §P3.7 #14 | cabinet_spots config + `light_switch` profile |
| VWB-3 | §P3.7 #15 | `POST /devices/{id}/canonical` |
| VWB-4 | §P3.7 #16 | `device_name → names` bilingual migration |
| VWB-5 | §P3.7 #17 | `GET /system/catalog` |
| VWB-6 | §P3.7 #18 | Slice end-to-end HW validation |
| VWB-7 | §P3.7 #19 (+ folded #20) | Capability profiles + driver enrichment |
| VWB-8 | §P3.7 #21 | `rooms.json` bootstrap + `global` |
| VWB-9 | §P3.7 #R | Room-architecture refactor |
| VWB-10 | §P3.7 #22 | Aggregate devices in `global` (`all_lights`) |
| VWB-11 | §P3.7 #23 | Bulk device configs (57 across 10 rooms) |
| VWB-12 | §P3.7 #24 | `wb-msw-v3_*` sensor side |
| VWB-13 | §P3.7 #25 | Catalog completeness + bulk e2e verification |
| VWB-14 | §P3.7 #26 | Value-label translation layer |

### UI — config-ui
| New | Old | Task |
|---|---|---|
| UI-1 | P0 #0a | Ship appliance-category UI feature |
| UI-2 | P0 #1 | Backend half of the appliance feature |
| UI-3 | P1 #3 | Generate OpenAPI types for the UI |
| UI-4 | P1 #3.5 | Kill the Python-AST coupling in UI codegen |
| UI-5 | P1 #4 | Parameterize nginx + MQTT URLs |
| UI-6 | P1 #4.5 | Move `device-state-mapping.json` to backend |
| UI-7 | P2.5 #10 | Placement contract (→ Layer-3 manifest) |
| UI-8 | §5.1 (vite 5→6) | Vite 5 → 6 migration |

### OPS — docker / CI-CD / deploy / ops
| New | Old | Task |
|---|---|---|
| OPS-1 | P0 #0b | Delete stale branches |
| OPS-2 | P0 #2 | Wire tests into CI |
| OPS-3 | P3 #7 | GHCR image push |
| OPS-4 | P3 #8 | compose / systemd / update.sh |
| OPS-5 | P3 #9 | Monorepo decision (Phase 2) |
| OPS-6 | §5.1 #8 | Clean shutdown (SSE drain + pyatv teardown) |
| OPS-7 | §5.1 (dep refresh) | Dependency / Dependabot refresh |
| OPS-8 | P4 #6 | Lifecycle-robustness leftovers |

### CORE — backend core / architecture
| New | Old | Task |
|---|---|---|
| CORE-1 | §5.1 (system-router) | System-router adapter cleanup (Item A) |

### DOC — docs / ledger / process
| New | Old | Task |
|---|---|---|
| DOC-1 | P2 #5 | Archive `TODO.md` → history |
| DOC-2 | P2 #6 | Doc-accuracy pass |
| DOC-3 | P2.6 #11 | GSD workflow (adopted then dropped) |
| DOC-4 | §5.1 (scope-drift guard) | Machine-checkable scope-drift guard |
| DOC-5 | §5.2 #1 | Ledger-format convergence design |
| DOC-6 | §5.2 #2 | Two-file split (initial) |
| DOC-7 | §5.2 #3 | Adopt additive conventions (folded into DOC-9) |
| DOC-8 | §5.2 #4 | Extract narrative sections (archived survey) |
| DOC-9 | §5.2 #5 | Full re-ID execution |
| DOC-10 | §5.2 #7 | Retire frozen scenario/Layer-3 ledgers |

**Acceptance gate** (ex-P4 #1–#5) is not a workstream task — it is the house-works completion
checklist; see `action_plan.md` → "Acceptance gate".
