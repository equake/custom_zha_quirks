"""Zemismart 4-gang switch with label screen.

Manufacturer: _TZE284_y4jqpry8  Model: TS0601

The device reports as a single SMART_PLUG endpoint. This quirk splits it into
four ON_OFF_LIGHT endpoints (one per gang) and exposes configuration options
(countdown, power-on behavior, indicator, child lock, backlight, LED colors)
via the Home Assistant Configuration panel. Gang labels are writable as UTF-8
strings using a RAW Tuya DP type (not the standard STRING type).

Automation — changing gang labels:

  Use the reusable script in examples/zemismart_set_label.yaml (paste into
  HA → Settings → Scripts → Add Script → Edit as YAML). One script works for
  all Zemismart switches on the network.

  Direct service call (without the script):

    service: zha.set_zigbee_cluster_attribute
    data:
      ieee: "<device IEEE>"   # HA → Devices → Zemismart → Zigbee info
      endpoint_id: 1          # gang number (1–4)
      cluster_id: 64640       # ZemismartSwitchEPCluster (0xFC80)
      cluster_type: in
      attribute: switch_label
      value: "Sala"
"""

from typing import ClassVar, Final

import zigpy.types as t
from zigpy.profiles import zha
from zigpy.zcl import foundation
from zigpy.zcl.foundation import UNDEFINED, ZCLAttributeDef, ZCLCommandDef
from zigpy.quirks.v2.homeassistant import PERCENTAGE, UnitOfTime

from zhaquirks.tuya import TuyaCommand, TuyaData, TuyaDatapointData
from zhaquirks.tuya.builder import TuyaQuirkBuilder
from zhaquirks.tuya.mcu import TuyaAttributesCluster


def _decode_label(raw: bytes) -> str:
    """Decode a RAW Tuya DP payload to a UTF-8 string label."""
    return raw.decode("utf-8")


class ZemismartPowerOnState(t.enum8):
    """Power-on behavior enum."""

    power_off = 0x00
    power_on = 0x01
    restart_memory = 0x02


class ZemismartIndicatorMode(t.enum8):
    """Indicator light mode enum."""

    off = 0x00
    on_off_status = 0x01
    switch_position = 0x02


class ZemismartSwitchColor(t.enum8):
    """LED color enum."""

    red = 0x00
    blue = 0x01
    green = 0x02
    white = 0x03
    yellow = 0x04
    magenta = 0x05
    cyan = 0x06
    warm_white = 0x07
    warm_yellow = 0x08


class ZemismartBacklightTime(t.enum8):
    """Backlight on-time after touch/proximity detection."""

    none = 0x00
    ten_seconds = 0x01
    twenty_seconds = 0x02
    thirty_seconds = 0x03
    forty_five_seconds = 0x04
    sixty_seconds = 0x05


class ZemismartSwitchEPCluster(TuyaAttributesCluster):
    """Per-endpoint cluster for switch labels (UTF-8, RAW Tuya DP type)."""

    cluster_id = 0xFC80
    ep_attribute = "zemismart_ep"

    # Label DP number per endpoint
    _LABEL_DP: ClassVar[dict[int, int]] = {1: 105, 2: 106, 3: 107, 4: 108}

    class ServerCommandDefs(TuyaAttributesCluster.ServerCommandDefs):
        """Server command definitions."""

        flash_backlight: Final = ZCLCommandDef(
            id=0x00, schema={}, is_manufacturer_specific=True
        )

    class AttributeDefs(TuyaAttributesCluster.AttributeDefs):
        """Attribute definitions."""

        switch_label: Final = ZCLAttributeDef(
            id=0x8012, type=t.CharacterString, is_manufacturer_specific=True
        )

    async def command(self, command_id, *args, **kwargs):
        """Re-write the current label to trigger the physical backlight."""
        if command_id == self.ServerCommandDefs.flash_backlight.id:
            label = self.get("switch_label") or ""
            await self.write_attributes({"switch_label": label})
            return
        return await super().command(command_id, *args, **kwargs)

    async def write_attributes(self, attributes, manufacturer=UNDEFINED, **kwargs):
        """Send switch_label as a RAW Tuya DP; pass other attributes to super."""
        attributes = dict(attributes)
        label = attributes.pop("switch_label", None)
        if label is None:
            label = attributes.pop(0x8012, None)

        if label is not None:
            ep_id = self.endpoint.endpoint_id
            dp = self._LABEL_DP[ep_id]
            mfg = self.endpoint.device.endpoints[1].tuya_manufacturer
            encoded = label.encode("utf-8")
            # Device uses RAW (0x00) not STRING (0x03): type(1B) + fn(1B) + len(1B) + data
            tuya_data, _ = TuyaData.deserialize(
                bytes([0x00, 0x00, len(encoded)]) + encoded
            )
            cmd = TuyaCommand(
                status=0,
                tsn=self.endpoint.device.application.get_sequence(),
                datapoints=[TuyaDatapointData(dp, tuya_data)],
            )
            await mfg.command(
                mfg.mcu_write_command, cmd,
                expect_reply=False, manufacturer=manufacturer,
            )
            self.update_attribute("switch_label", label)

        if attributes:
            return await super().write_attributes(attributes, manufacturer=manufacturer, **kwargs)
        return [[foundation.WriteAttributesStatusRecord(foundation.Status.SUCCESS)]]


# Each gang is exposed as a separate ON_OFF_LIGHT endpoint so ZHA discovers them as
# independent light entities. Per-gang config (countdown, power-on state) is placed
# on endpoint 1 where the MCU cluster lives.
(
    TuyaQuirkBuilder("_TZE284_y4jqpry8", "TS0601")
    .replaces_endpoint(1, device_type=zha.DeviceType.ON_OFF_LIGHT)
    .adds_endpoint(2, device_type=zha.DeviceType.ON_OFF_LIGHT)
    .adds_endpoint(3, device_type=zha.DeviceType.ON_OFF_LIGHT)
    .adds_endpoint(4, device_type=zha.DeviceType.ON_OFF_LIGHT)
    # On/off per gang (DPs 1–4); ZHA auto-discovers these as light entities
    .tuya_onoff(dp_id=1, endpoint_id=1)
    .tuya_onoff(dp_id=2, endpoint_id=2)
    .tuya_onoff(dp_id=3, endpoint_id=3)
    .tuya_onoff(dp_id=4, endpoint_id=4)
    # Countdown per gang in seconds (DPs 7–10)
    .tuya_number(dp_id=7, type=t.uint32_t, attribute_name="countdown_1",
                 min_value=0, max_value=86400, step=1, unit=UnitOfTime.SECONDS,
                 translation_key="countdown_1", fallback_name="Countdown 1")
    .tuya_number(dp_id=8, type=t.uint32_t, attribute_name="countdown_2",
                 min_value=0, max_value=86400, step=1, unit=UnitOfTime.SECONDS,
                 translation_key="countdown_2", fallback_name="Countdown 2")
    .tuya_number(dp_id=9, type=t.uint32_t, attribute_name="countdown_3",
                 min_value=0, max_value=86400, step=1, unit=UnitOfTime.SECONDS,
                 translation_key="countdown_3", fallback_name="Countdown 3")
    .tuya_number(dp_id=10, type=t.uint32_t, attribute_name="countdown_4",
                 min_value=0, max_value=86400, step=1, unit=UnitOfTime.SECONDS,
                 translation_key="countdown_4", fallback_name="Countdown 4")
    # Indicator light mode (DP 15)
    .tuya_enum(dp_id=15, attribute_name="indicator_mode",
               enum_class=ZemismartIndicatorMode,
               translation_key="indicator_mode", fallback_name="Indicator mode")
    # Power-on behavior per gang (DPs 29–32)
    .tuya_enum(dp_id=29, attribute_name="power_on_state_1",
               enum_class=ZemismartPowerOnState,
               translation_key="power_on_state_1", fallback_name="Power-on state 1")
    .tuya_enum(dp_id=30, attribute_name="power_on_state_2",
               enum_class=ZemismartPowerOnState,
               translation_key="power_on_state_2", fallback_name="Power-on state 2")
    .tuya_enum(dp_id=31, attribute_name="power_on_state_3",
               enum_class=ZemismartPowerOnState,
               translation_key="power_on_state_3", fallback_name="Power-on state 3")
    .tuya_enum(dp_id=32, attribute_name="power_on_state_4",
               enum_class=ZemismartPowerOnState,
               translation_key="power_on_state_4", fallback_name="Power-on state 4")
    # Child lock (DP 101)
    .tuya_switch(dp_id=101, attribute_name="child_lock",
                 translation_key="child_lock", fallback_name="Child lock")
    # Backlight — on/off, brightness 0–100%, on-time after touch (DPs 16, 102, 111)
    .tuya_switch(dp_id=16, attribute_name="backlight_mode",
                 translation_key="backlight_mode", fallback_name="Backlight")
    .tuya_number(dp_id=102, type=t.uint8_t, attribute_name="backlight_brightness",
                 min_value=0, max_value=100, step=1, unit=PERCENTAGE,
                 translation_key="backlight_brightness", fallback_name="Backlight brightness")
    .tuya_enum(dp_id=111, attribute_name="backlight_time",
               enum_class=ZemismartBacklightTime,
               translation_key="backlight_time", fallback_name="Backlight time")
    # LED color when on/off (DPs 103–104)
    .tuya_enum(dp_id=103, attribute_name="color_on",
               enum_class=ZemismartSwitchColor,
               translation_key="color_on", fallback_name="LED color (on)")
    .tuya_enum(dp_id=104, attribute_name="color_off",
               enum_class=ZemismartSwitchColor,
               translation_key="color_off", fallback_name="LED color (off)")
    # Switch labels, UTF-8, max 12 chars (DPs 105–108); attribute-only, no HA entity
    .tuya_dp(dp_id=105, ep_attribute=ZemismartSwitchEPCluster.ep_attribute,
             attribute_name="switch_label",
             converter=_decode_label, endpoint_id=1)
    .tuya_dp(dp_id=106, ep_attribute=ZemismartSwitchEPCluster.ep_attribute,
             attribute_name="switch_label",
             converter=_decode_label, endpoint_id=2)
    .tuya_dp(dp_id=107, ep_attribute=ZemismartSwitchEPCluster.ep_attribute,
             attribute_name="switch_label",
             converter=_decode_label, endpoint_id=3)
    .tuya_dp(dp_id=108, ep_attribute=ZemismartSwitchEPCluster.ep_attribute,
             attribute_name="switch_label",
             converter=_decode_label, endpoint_id=4)
    .adds(ZemismartSwitchEPCluster, endpoint_id=1)
    .adds(ZemismartSwitchEPCluster, endpoint_id=2)
    .adds(ZemismartSwitchEPCluster, endpoint_id=3)
    .adds(ZemismartSwitchEPCluster, endpoint_id=4)
    # Button to re-send the current label, triggering the physical backlight
    .command_button(
        command_name="flash_backlight",
        cluster_id=ZemismartSwitchEPCluster.cluster_id,
        endpoint_id=1,
        translation_key="flash_backlight",
        fallback_name="Flash backlight",
    )
    .skip_configuration()
    .add_to_registry()
)
