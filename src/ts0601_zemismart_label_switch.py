"""Zemismart 4-gang switch with label screen."""
from typing import ClassVar, Final

import zigpy.types as t
from zigpy.profiles import zgp, zha
from zigpy.zcl import foundation
from zigpy.zcl.clusters.general import Basic, GreenPowerProxy, Groups, Ota, Scenes, Time
from zigpy.zcl.foundation import UNDEFINED, ZCLAttributeDef

from zhaquirks.const import (
    DEVICE_TYPE,
    ENDPOINTS,
    INPUT_CLUSTERS,
    MODELS_INFO,
    OUTPUT_CLUSTERS,
    PROFILE_ID,
)
from zhaquirks.tuya import TuyaCommand, TuyaData, TuyaDatapointData, TuyaSwitch
from zhaquirks.tuya.mcu import (
    DPToAttributeMapping,
    TuyaAttributesCluster,
    TuyaMCUCluster,
    TuyaOnOff,
    TuyaOnOffManufCluster,
    TuyaOnOffNM,
)


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


class ZemismartSwitchEPCluster(TuyaAttributesCluster):
    """Per-endpoint cluster holding per-gang attributes (countdown, power-on state, label)."""

    cluster_id = 0xFC80
    ep_attribute: Final = "zemismart_ep"

    # switch_label DP number per endpoint
    _LABEL_DP: ClassVar[dict[int, int]] = {1: 105, 2: 106, 3: 107, 4: 108}

    class AttributeDefs(TuyaAttributesCluster.AttributeDefs):
        """Attribute definitions."""

        power_on_state: Final = ZCLAttributeDef(
            id=0x8010, type=ZemismartPowerOnState, is_manufacturer_specific=True
        )
        countdown: Final = ZCLAttributeDef(
            id=0x8011, type=t.uint32_t, is_manufacturer_specific=True
        )
        switch_label: Final = ZCLAttributeDef(
            id=0x8012, type=t.CharacterString, is_manufacturer_specific=True
        )

    async def write_attributes(self, attributes, manufacturer=UNDEFINED, **kwargs):
        """Handle switch_label (string DP) directly; delegate the rest to super."""
        attributes = dict(attributes)
        label = attributes.pop("switch_label", None)
        if label is None:
            label = attributes.pop(0x8012, None)

        if label is not None:
            ep_id = self.endpoint.endpoint_id
            dp = self._LABEL_DP[ep_id]
            mfg = self.endpoint.device.endpoints[1].tuya_manufacturer
            encoded = label.encode("utf-8")
            # TuyaData RAW: type(1B=0x00) + function(1B=0x00) + LVBytes(len 1B + data)
            tuya_data, _ = TuyaData.deserialize(bytes([0x00, 0x00, len(encoded)]) + encoded)
            dpd = TuyaDatapointData(dp, tuya_data)
            cmd = TuyaCommand(
                status=0,
                tsn=self.endpoint.device.application.get_sequence(),
                datapoints=[dpd],
            )
            await mfg.command(
                mfg.mcu_write_command, cmd,
                expect_reply=False, manufacturer=manufacturer,
            )
            self.update_attribute("switch_label", label)

        if attributes:
            return await super().write_attributes(attributes, manufacturer=manufacturer, **kwargs)
        return [[foundation.WriteAttributesStatusRecord(foundation.Status.SUCCESS)]]


class ZemismartSwitchMfgCluster(TuyaMCUCluster):
    """Manufacturer cluster for Zemismart 4-gang switch.

    Handles all device-level DPs and routes per-gang DPs to the correct endpoints
    via DPToAttributeMapping(endpoint_id=N).
    """

    class AttributeDefs(TuyaMCUCluster.AttributeDefs):
        """Attribute definitions."""

        child_lock: Final = ZCLAttributeDef(
            id=0x8000, type=t.Bool, is_manufacturer_specific=True
        )
        indicator_mode: Final = ZCLAttributeDef(
            id=0x8001, type=ZemismartIndicatorMode, is_manufacturer_specific=True
        )
        backlight_brightness: Final = ZCLAttributeDef(
            id=0x8002, type=t.uint8_t, is_manufacturer_specific=True
        )
        color_on: Final = ZCLAttributeDef(
            id=0x8003, type=ZemismartSwitchColor, is_manufacturer_specific=True
        )
        color_off: Final = ZCLAttributeDef(
            id=0x8004, type=ZemismartSwitchColor, is_manufacturer_specific=True
        )

    dp_to_attribute: dict[int, DPToAttributeMapping] = {
        # On/off per gang (DPs 1–4)
        1: DPToAttributeMapping(TuyaOnOff.ep_attribute, "on_off"),
        2: DPToAttributeMapping(TuyaOnOff.ep_attribute, "on_off", endpoint_id=2),
        3: DPToAttributeMapping(TuyaOnOff.ep_attribute, "on_off", endpoint_id=3),
        4: DPToAttributeMapping(TuyaOnOff.ep_attribute, "on_off", endpoint_id=4),
        # Countdown per gang in seconds (DPs 7–10)
        7: DPToAttributeMapping(ZemismartSwitchEPCluster.ep_attribute, "countdown"),
        8: DPToAttributeMapping(ZemismartSwitchEPCluster.ep_attribute, "countdown", endpoint_id=2),
        9: DPToAttributeMapping(ZemismartSwitchEPCluster.ep_attribute, "countdown", endpoint_id=3),
        10: DPToAttributeMapping(ZemismartSwitchEPCluster.ep_attribute, "countdown", endpoint_id=4),
        # Indicator light mode (DP 15)
        15: DPToAttributeMapping(TuyaMCUCluster.ep_attribute, "indicator_mode", converter=ZemismartIndicatorMode),
        # Power-on behavior per gang (DPs 29–32)
        29: DPToAttributeMapping(ZemismartSwitchEPCluster.ep_attribute, "power_on_state", converter=ZemismartPowerOnState),
        30: DPToAttributeMapping(ZemismartSwitchEPCluster.ep_attribute, "power_on_state", converter=ZemismartPowerOnState, endpoint_id=2),
        31: DPToAttributeMapping(ZemismartSwitchEPCluster.ep_attribute, "power_on_state", converter=ZemismartPowerOnState, endpoint_id=3),
        32: DPToAttributeMapping(ZemismartSwitchEPCluster.ep_attribute, "power_on_state", converter=ZemismartPowerOnState, endpoint_id=4),
        # Child lock (DP 101)
        101: DPToAttributeMapping(TuyaMCUCluster.ep_attribute, "child_lock"),
        # Backlight brightness 0–100% (DP 102)
        102: DPToAttributeMapping(TuyaMCUCluster.ep_attribute, "backlight_brightness"),
        # LED color when on (DP 103)
        103: DPToAttributeMapping(TuyaMCUCluster.ep_attribute, "color_on", converter=ZemismartSwitchColor),
        # LED color when off (DP 104)
        104: DPToAttributeMapping(TuyaMCUCluster.ep_attribute, "color_off", converter=ZemismartSwitchColor),
        # Switch label per gang, UTF-8 max 12 chars (DPs 105–108)
        105: DPToAttributeMapping(ZemismartSwitchEPCluster.ep_attribute, "switch_label", converter=lambda x: x.decode("utf-8")),
        106: DPToAttributeMapping(ZemismartSwitchEPCluster.ep_attribute, "switch_label", converter=lambda x: x.decode("utf-8"), endpoint_id=2),
        107: DPToAttributeMapping(ZemismartSwitchEPCluster.ep_attribute, "switch_label", converter=lambda x: x.decode("utf-8"), endpoint_id=3),
        108: DPToAttributeMapping(ZemismartSwitchEPCluster.ep_attribute, "switch_label", converter=lambda x: x.decode("utf-8"), endpoint_id=4),
    }

    data_point_handlers = {dp: "_dp_2_attr_update" for dp in dp_to_attribute}


class Zemismart4GangLabelSwitch(TuyaSwitch):
    """Zemismart 4-gang switch with label screen and GreenPowerProxy cluster."""

    NAME = "Zemismart 4-gang switch with label screen"

    signature = {
        MODELS_INFO: [
            ("_TZE284_y4jqpry8", "TS0601"),
        ],
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.SMART_PLUG,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    TuyaOnOffManufCluster.cluster_id,
                    0xED00,  # undocumented Tuya cluster present in raw advertisement
                ],
                OUTPUT_CLUSTERS: [Time.cluster_id, Ota.cluster_id],
            },
            242: {
                PROFILE_ID: zgp.PROFILE_ID,
                DEVICE_TYPE: zgp.DeviceType.PROXY_BASIC,
                INPUT_CLUSTERS: [],
                OUTPUT_CLUSTERS: [GreenPowerProxy.cluster_id],
            },
        },
    }

    replacement = {
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.ON_OFF_LIGHT,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    ZemismartSwitchMfgCluster,
                    TuyaOnOffNM,
                    ZemismartSwitchEPCluster,
                ],
                OUTPUT_CLUSTERS: [Time.cluster_id, Ota.cluster_id],
            },
            2: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.ON_OFF_LIGHT,
                INPUT_CLUSTERS: [TuyaOnOffNM, ZemismartSwitchEPCluster],
                OUTPUT_CLUSTERS: [],
            },
            3: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.ON_OFF_LIGHT,
                INPUT_CLUSTERS: [TuyaOnOffNM, ZemismartSwitchEPCluster],
                OUTPUT_CLUSTERS: [],
            },
            4: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.ON_OFF_LIGHT,
                INPUT_CLUSTERS: [TuyaOnOffNM, ZemismartSwitchEPCluster],
                OUTPUT_CLUSTERS: [],
            },
            242: {
                PROFILE_ID: zgp.PROFILE_ID,
                DEVICE_TYPE: zgp.DeviceType.PROXY_BASIC,
                INPUT_CLUSTERS: [],
                OUTPUT_CLUSTERS: [GreenPowerProxy.cluster_id],
            },
        }
    }
