# Zemismart 4-Gang Switch with Label Screen (ZMS-206)

> **Model:** ZMS-206 · **Zigbee model:** TS0601 · **Manufacturer ID:** `_TZE284_y4jqpry8`
>
> **Product page:** https://www.zemismart.com/products/zms-206us
> **Manufacturer resources (DP table, firmware notes):** [Google Drive](https://drive.google.com/drive/folders/1f2V50kujRQSj6CbSlTVunVxVK_Yb6eZa)

---

## What this quirk does

The ZMS-206 is a 4-gang wall switch with a small e-ink/LCD label screen below each button. Out of the box, ZHA sees it as a single `SMART_PLUG` endpoint and exposes none of its configuration options.

This quirk:

- Splits the device into **4 independent `ON_OFF_LIGHT` endpoints** (one per gang), so ZHA discovers 4 separate light entities that can be controlled and automated individually.
- Exposes all configuration options available in the official Zemismart app in HA's **Configuration** panel (countdown, power-on behavior, indicator, backlight, LED colors, child lock).
- Adds an **extra on-demand backlight** feature not present in the original app — see [below](#extra-feature-on-demand-backlight).
- Provides a reusable **automation script** for changing gang labels — see [below](#changing-gang-labels-via-automation).

---

## Background

### Baseline: Zigbee2MQTT

The DP map used in this quirk was derived from the [Zigbee2MQTT](https://www.zigbee2mqtt.io/) TS0601 device definition, which already documented the Tuya data points for on/off, countdown, power-on state, and LED configuration.

### Prior Home Assistant community solution

A [community guide](https://community.home-assistant.io/t/complete-guide-to-adding-zemismart-zigbee-screen-switch-zms-206-to-home-assistant-via-zha-with-converter-tool/898706) proposed adding ZMS-206 support by patching the `zhaquirks` package itself — specifically modifying `tuya/mcu/__init__.py` to accept raw `bytes` strings as Tuya STRING-type DPs.

This approach works but requires modifying a third-party package, which breaks on updates and isn't accepted by the official zha-device-handlers repository.

**This quirk takes a different approach:** the label DPs (105–108) use the Tuya RAW type (`0x00`), not STRING (`0x03`). The raw bytes are decoded/encoded as UTF-8 inside a custom cluster (`ZemismartSwitchEPCluster`) that overrides `write_attributes` — no changes to any package required.

---

## Features

All features available in the official Zemismart app are implemented:

| DP | Gang | HA Entity | Panel | Description |
|----|------|-----------|-------|-------------|
| 1–4 | 1–4 | Light (on/off) | Controls | Individual gang on/off |
| 7–10 | 1–4 | Number | Configuration | Countdown timer (0–86400 s) |
| 15 | — | Select | Configuration | Indicator light mode |
| 16 | — | Switch | Configuration | Backlight on/off |
| 29–32 | 1–4 | Select | Configuration | Power-on behavior |
| 101 | — | Switch | Configuration | Child lock |
| 102 | — | Number | Configuration | Backlight brightness (0–100 %) |
| 103 | — | Select | Configuration | LED color when switch is ON |
| 104 | — | Select | Configuration | LED color when switch is OFF |
| 105–108 | 1–4 | *(attribute only)* | — | Gang label text (UTF-8, max 12 chars) |
| 111 | — | Select | Configuration | Backlight on-time after touch |

**Indicator mode options:** off · on/off status · switch position
**Power-on behavior options:** power off · power on · restore last state
**LED color options:** red · blue · green · white · yellow · magenta · cyan · warm white · warm yellow
**Backlight time options:** none · 10 s · 20 s · 30 s · 45 s · 60 s

---

## Extra feature: on-demand backlight

The device activates its physical backlight whenever a label is written to it — even if the new label is identical to the current one. This quirk exposes a **"Flash backlight"** `button` entity that re-sends the current label, lighting the display without changing any text.

**Use case:** trigger the backlight when a presence sensor detects motion, so occupants can see the switch in the dark.

### Automation example

```yaml
automation:
  alias: Light up switch when motion detected
  trigger:
    - platform: state
      entity_id: binary_sensor.corridor_presence
      to: "on"
  action:
    - service: button.press
      target:
        entity_id: button.zemismart_flash_backlight
```

The backlight stays on for the duration configured in the **Backlight time** setting (Configuration panel).

---

## Changing gang labels via automation

Gang labels are written as UTF-8 strings via a custom ZCL cluster. ZHA does not (yet) expose string attributes as text entities, so labels are changed using the `zha.set_zigbee_cluster_attribute` service.

### Recommended: reusable script

Use the script template in [`scripts/zemismart_set_label.yaml`](../scripts/zemismart_set_label.yaml):

1. Copy the file content.
2. In HA: **Settings → Scripts → Add Script → Edit as YAML** → paste → save.

Then in any automation:

```yaml
service: script.set_zemismart_label
data:
  device: "{{ device_id('light.sala_gang_1') }}"   # any entity of the switch
  gang: 1                                            # 1–4
  label: "Sala"
```

The `device` field accepts a device_id — use `device_id('entity_id')` to reference the switch by one of its light entities. The script works for **any Zemismart switch** on the network; no hardcoded IEEE address.

### Direct service call

```yaml
service: zha.set_zigbee_cluster_attribute
data:
  ieee: "<device IEEE>"         # HA → Devices → Zemismart → Zigbee info
  endpoint_id: 1                # gang number (1–4)
  cluster_id: 64640             # 0xFC80 — ZemismartSwitchEPCluster
  cluster_type: in
  attribute: switch_label
  value: "Sala"
```

> **Side effect:** writing a label also activates the backlight for the configured duration. You can use this intentionally to combine a label update with a backlight flash in a single service call.

---

## Installation

See the [main README](../README.md#installation).

---

## Known limitations

- **Gang labels have no HA text entity.** `EntityPlatform.TEXT` is not yet available in the zigpy version used by this quirk. Labels can only be changed via the `zha.set_zigbee_cluster_attribute` service or the wrapper script. This will be revisited when text entity support is added to zigpy.

- **Label cache is not restored after ZHA restart.** The label stored in HA's attribute cache is cleared when ZHA restarts. It is repopulated the next time the device reports the DP (typically on the next state change or power cycle). The label on the physical device is unaffected.
