# custom-zha-quirks

Custom ZHA quirks for Home Assistant — device-specific fixes and extensions built on top of [zha-quirks](https://github.com/zigpy/zha-device-handlers).

[![Check quirks](https://github.com/equake/custom-zha-quirks/actions/workflows/check.yml/badge.svg)](https://github.com/equake/custom-zha-quirks/actions/workflows/check.yml)

---

## What is this?

[ZHA](https://www.home-assistant.io/integrations/zha/) (Zigbee Home Automation) is Home Assistant's built-in Zigbee integration. Some devices report non-standard Zigbee profiles or use manufacturer-specific extensions that ZHA doesn't understand out of the box. **Quirks** are small Python files that teach ZHA how to handle these devices — splitting endpoints, mapping proprietary data points, and exposing the right HA entities.

This repository contains quirks that are not (yet) part of the official [zha-device-handlers](https://github.com/zigpy/zha-device-handlers) repository, or extend official quirks with additional features.

---

## Quirks

| Device | Model / Manufacturer ID | Quirk file | Documentation |
|--------|------------------------|------------|---------------|
| [Zemismart ZMS-206 4-gang switch with label screen](https://www.zemismart.com/products/zms-206us) | TS0601 / `_TZE284_y4jqpry8` | [`src/ts0601_zemismart_label_switch.py`](src/ts0601_zemismart_label_switch.py) | [docs/zemismart_4gang_label_switch.md](docs/zemismart_4gang_label_switch.md) |

---

## Installation

### 1. Configure Home Assistant

Add to your `configuration.yaml`:

```yaml
zha:
  custom_quirks_path: /config/custom_zha_quirks/
```

### 2. Copy the quirk files

Copy the files from `src/` to `/config/custom_zha_quirks/` on your Home Assistant instance:

```bash
# Example using scp:
scp src/*.py homeassistant:/config/custom_zha_quirks/
```

### 3. Restart ZHA

In Home Assistant: **Settings → Devices & Services → ZHA → ⋮ → Reload**.

> **Tip for live development:** Instead of copying, symlink the `src/` directory so changes take effect after a ZHA reload without re-copying files.

---

## Development setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/equake/custom-zha-quirks
cd custom-zha-quirks
uv venv
uv sync
```

### Validate all quirks import cleanly

```bash
uv run python -c "
import importlib.util
import pathlib

for f in sorted(pathlib.Path('src').glob('*.py')):
    spec = importlib.util.spec_from_file_location('quirk', f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print(f'  OK: {f}')
"
```

CI runs this automatically on every push and pull request (see `.github/workflows/check.yml`).

---

## Adding a new quirk

1. **Capture the device's Zigbee profile** using [zigbee2mqtt interview](https://www.zigbee2mqtt.io/guide/usage/exposes.html) or the [ZHA Toolkit](https://github.com/mdeweerd/zha-toolkit) add-on. This gives you the raw endpoint/cluster layout and the Tuya DP map.

2. **Write the quirk** in `src/` following the v2 `TuyaQuirkBuilder` pattern used by existing quirks. See [zhaquirks/tuya/builder](https://github.com/zigpy/zha-device-handlers/blob/dev/zhaquirks/tuya/builder/__init__.py) and the [official guide](https://github.com/zigpy/zha-device-handlers/blob/dev/tuya.md).

3. **Validate** with `uv run python -c "import src.your_new_quirk"`.

4. **Add documentation** in `docs/` (one Markdown file per quirk). Include the DP table, features, and automation examples.

5. Open a pull request.

---

## Troubleshooting

**Quirk not loading**
- Confirm the path in `configuration.yaml` matches where you copied the files.
- Reload ZHA (not just HA) after copying.
- Check the HA log for import errors: **Settings → System → Logs**.

**"Manage Zigbee Device" attribute reads return `None`**
- Expected for virtual endpoints (2–4). These endpoints don't exist on the physical device; their state is cached locally by the quirk and updated when the device reports a DP change. Reads always return the last known value, not a fresh read from the device.

**Quirk matched but device not working**
- Check the manufacturer ID and model string exactly — they're case-sensitive. Compare what your device reports (visible in ZHA device info) with the `MODELS_INFO` or `TuyaQuirkBuilder(...)` call in the quirk.

---

## Contributing

- One quirk per pull request.
- All quirks must pass the import check (CI enforces this).
- Each quirk must have a corresponding `docs/` file.
- Follow the v2 `TuyaQuirkBuilder` API (see existing quirks for examples).

---

## License

MIT — see [LICENSE](LICENSE).
