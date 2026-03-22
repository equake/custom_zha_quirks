# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Custom ZHA (Zigbee Home Automation) quirks for Home Assistant. Quirks are device-specific overrides that fix or extend ZHA's understanding of non-standard Zigbee devices. They are loaded by placing them in the `custom_zha_quirks` directory configured in `configuration.yaml`.

## Deployment

Quirks are deployed by copying files to the Home Assistant config directory (e.g., `/config/custom_zha_quirks/`) and restarting ZHA or Home Assistant. There is no build step.

To configure Home Assistant to load these quirks, add to `configuration.yaml`:
```yaml
zha:
  custom_quirks_path: /config/custom_zha_quirks/
```

## Architecture

Each quirk file defines a class that inherits from a `zhaquirks` base class (e.g., `TuyaSwitch`). The class has two main sections:

- **`signature`**: Matches the device's raw Zigbee advertisement — manufacturer/model strings and the endpoint/cluster layout the device actually reports.
- **`replacement`**: Defines the corrected endpoint/cluster layout that ZHA should use instead — typically splitting a single multi-gang switch endpoint into multiple numbered endpoints (one per gang), each with the proper device type and clusters.

The `MODELS_INFO` list in `signature` scopes the quirk to specific manufacturer+model pairs, so it only affects the targeted device.

## Key Dependencies

- `zigpy` — Zigbee profiles, device types, cluster IDs (`zigpy.profiles`, `zigpy.zcl.clusters`)
- `zhaquirks` — Base classes and Tuya-specific clusters (`zhaquirks.tuya`, `zhaquirks.tuya.mcu`)

Relevant cluster classes used in Tuya quirks:
- `TuyaOnOffNM` — Non-manufacturer on/off cluster for additional gang endpoints
- `MoesSwitchManufCluster` — Manufacturer cluster for the primary endpoint (provides Tuya MCU data points)
- `TuyaOnOffManufCluster` — Raw manufacturer cluster as seen in the device signature
