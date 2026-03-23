# AGENTS.md — Developer Guide for AI Agents

> This is the canonical reference for AI agents (Claude Code, OpenCode, Cursor, etc.)
> working in this repository. `CLAUDE.md` defers to this file.

---

## What This Is

Custom ZHA (Zigbee Home Automation) quirks for Home Assistant. Quirks are device-specific
Python files that fix or extend ZHA's understanding of non-standard Zigbee devices. They are
loaded from the directory configured in `configuration.yaml`:

```yaml
zha:
  custom_quirks_path: /config/custom_zha_quirks/
```

Deployment: copy `src/*.py` to `/config/custom_zha_quirks/` and restart ZHA. No build step.

---

## Project Structure

```
src/                    ← one .py file per quirk
docs/                   ← one .md file per quirk (linked from README)
examples/               ← reusable HA automation scripts/blueprints
.github/workflows/      ← CI: import check on every push/PR
pyproject.toml          ← dependencies (managed with uv)
```

---

## Quirk API: always use v2 (TuyaQuirkBuilder)

All quirks in this repo use the **v2 `TuyaQuirkBuilder` API**. Never write v1 quirks
(class-based `signature`/`replacement` dicts inheriting from `TuyaSwitch`).

### Minimal v2 skeleton

```python
from zhaquirks.tuya.builder import TuyaQuirkBuilder
import zigpy.types as t

(
    TuyaQuirkBuilder("_MANUFACTURER_ID", "TS0601")
    .tuya_onoff(dp_id=1, endpoint_id=1)
    .tuya_switch(dp_id=101, attribute_name="child_lock",
                 translation_key="child_lock", fallback_name="Child lock")
    .skip_configuration()
    .add_to_registry()
)
```

### Key builder methods

| Method | Creates HA entity | Panel | Notes |
|--------|------------------|-------|-------|
| `.tuya_onoff(dp_id, endpoint_id)` | Light (auto-discovered) | Controls | Use with `ON_OFF_LIGHT` device_type |
| `.tuya_switch(dp_id, attribute_name, translation_key, fallback_name)` | Switch | Configuration | Bool DP |
| `.tuya_enum(dp_id, attribute_name, enum_class, translation_key, fallback_name)` | Select | Configuration | Enum DP |
| `.tuya_number(dp_id, type, attribute_name, min_value, max_value, step, unit, translation_key, fallback_name)` | Number | Configuration | Numeric DP |
| `.tuya_dp(dp_id, ep_attribute, attribute_name, converter, endpoint_id)` | None | — | Attribute-only mapping |
| `.adds(ClusterClass, endpoint_id)` | — | — | Attach a custom cluster to an endpoint |
| `.command_button(command_name, cluster_id, endpoint_id, translation_key, fallback_name)` | Button | Configuration | Backed by `ZCLCommandDef` |
| `.replaces_endpoint(N, device_type)` | — | — | Override device_type of existing endpoint |
| `.adds_endpoint(N, device_type)` | — | — | Add a virtual endpoint |
| `.applies_to(manufacturer, model)` | — | — | Add additional manufacturer+model pairs |
| `.skip_configuration()` | — | — | Always call before `.add_to_registry()` |
| `.add_to_registry()` | — | — | Register the quirk; must be last |

### Rules

- Every `tuya_switch`, `tuya_enum`, `tuya_number` call **must** include both
  `translation_key` (snake_case) and `fallback_name` (Title Case).
- `translation_key` is required by zigpy's entity validation — `fallback_name` is what HA
  displays when no translation file exists.
- `tuya_switch/enum/number` all put attributes on the MCU cluster (TUYA_CLUSTER_ID `0xEF00`
  on endpoint 1). The `endpoint_id` parameter only affects which endpoint the HA entity is
  associated with — it does NOT move the attribute to a different cluster.
- All DPs must be unique within a builder chain (`tuya_dp_multi` raises if a DP is re-used).

### Multi-endpoint pattern (multi-gang switches)

Use multiple `ON_OFF_LIGHT` endpoints so ZHA auto-discovers independent light entities.
Per-gang config attributes (countdown, power-on state) go on endpoint 1 with numbered
attribute names (`countdown_1`, `countdown_2`, …):

```python
(
    TuyaQuirkBuilder("_TZE284_example", "TS0601")
    .replaces_endpoint(1, device_type=zha.DeviceType.ON_OFF_LIGHT)
    .adds_endpoint(2, device_type=zha.DeviceType.ON_OFF_LIGHT)
    .tuya_onoff(dp_id=1, endpoint_id=1)
    .tuya_onoff(dp_id=2, endpoint_id=2)
    .tuya_number(dp_id=7, type=t.uint32_t, attribute_name="countdown_1",
                 min_value=0, max_value=86400, step=1, unit=UnitOfTime.SECONDS,
                 translation_key="countdown_1", fallback_name="Countdown 1")
    .skip_configuration()
    .add_to_registry()
)
```

### Custom clusters

For attributes that need non-standard write logic (e.g., RAW-type strings, compound commands),
define a cluster class inheriting from `TuyaAttributesCluster` and attach it with `.adds()`.
Override `write_attributes` for custom send logic. Override `command()` + add `ServerCommandDefs`
for button entities backed by local Python code (not an over-the-air ZCL command):

```python
class MyCluster(TuyaAttributesCluster):
    cluster_id = 0xFC80
    ep_attribute = "my_cluster"

    class ServerCommandDefs(TuyaAttributesCluster.ServerCommandDefs):
        my_action: Final = ZCLCommandDef(id=0x00, schema={}, is_manufacturer_specific=True)

    async def command(self, command_id, *args, **kwargs):
        if command_id == self.ServerCommandDefs.my_action.id:
            await self.write_attributes({"some_attr": self.get("some_attr")})
            return
        return await super().command(command_id, *args, **kwargs)
```

---

## Code style

- **Module docstring**: multi-line, include manufacturer ID + model, describe what the quirk
  fixes, add an "Automation" section if the device has writable attributes.
- **Enums**: one per logical group, prefixed with device/brand name (e.g., `ZemismartPowerOnState`).
  Add a one-line docstring.
- **Helper functions**: extract repeated lambdas as module-level named functions
  (e.g., `def _decode_label(raw: bytes) -> str`).
- **`ep_attribute`**: plain string assignment, no `Final` annotation.
- **`_LABEL_DP` and similar dicts**: annotate as `ClassVar[dict[K, V]]`.
- **Builder chain**: group related DPs together with a single comment header per group.
- **Import order**: stdlib → zigpy → zhaquirks.

---

## Key dependencies

- `zigpy` — profiles, device types, cluster IDs, ZCL types (`zigpy.profiles`, `zigpy.zcl`)
- `zha-quirks` (package name) / `zhaquirks` (import name) — builder, base clusters, Tuya MCU
- `from zhaquirks.tuya.builder import TuyaQuirkBuilder` — always use this for new quirks
- `from zhaquirks.tuya.mcu import TuyaAttributesCluster, TuyaOnOffNM` — custom clusters
- `from zigpy.quirks.v2.homeassistant import PERCENTAGE, UnitOfTime` — entity metadata

---

## Dev setup

```bash
uv venv && uv sync
```

Validate all quirks:

```bash
uv run python -c "
import importlib.util, pathlib
for f in sorted(pathlib.Path('src').glob('*.py')):
    spec = importlib.util.spec_from_file_location('quirk', f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print(f'  OK: {f}')
"
```

CI runs this automatically on push/PR via `.github/workflows/check.yml`.

---

## Adding a new quirk — checklist

- [ ] `src/<ts_model>_<brand>_<description>.py` — v2 builder, follows code style above
- [ ] `docs/<same_name>.md` — DP table, features, automation examples
- [ ] Row added to quirks table in `README.md`
- [ ] `uv run python -c "import src.<module>"` passes locally
- [ ] CI green
