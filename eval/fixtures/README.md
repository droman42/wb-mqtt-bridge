# CLI fixtures

| File | What | Source |
|---|---|---|
| `kitchen_hood_light_on.hex` | a real Broadlink RF packet (hex) | `config/devices/kitchen_hood.json` → `rf_codes.light.on`, base64-decoded to hex |

`broadlink-cli --convert` takes **hex** (the device configs store codes as base64), so the
fixture is the decoded form. Regenerate it after the device config changes:

```bash
cd ../../backend && .venv/bin/python -c "import json,base64; \
  d=json.load(open('config/devices/kitchen_hood.json')); \
  open('../eval/fixtures/kitchen_hood_light_on.hex','w').write(base64.b64decode(d['rf_codes']['light']['on']).hex())"
```
