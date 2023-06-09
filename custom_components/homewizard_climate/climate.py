"""Climate platform for homewizard_climate."""
import logging
import time

from homewizard_climate_ws.model.climate_device_state import (
    HomeWizardClimateDeviceState,
)
from homewizard_climate_ws.model.climate_device import (
    HomeWizardClimateDeviceType,
)

from homewizard_climate_ws.ws.hw_websocket import HomeWizardClimateWebSocket

from homeassistant.components.climate import (
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    FAN_ON,
    PRESET_BOOST,
    PRESET_ECO,
    SWING_HORIZONTAL,
    SWING_OFF,
    ClimateEntity,
    ClimateEntityFeature,
    PRESET_COMFORT,
    PRESET_SLEEP,
    PRESET_ECO,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create entries for each device in Homewizard cloud."""
    websockets = hass.data[DOMAIN][entry.entry_id]["websockets"]
    entities = [HomeWizardClimateEntity(ws, hass) for ws in websockets]
    async_add_entities(entities)


class HomeWizardClimateEntity(ClimateEntity):
    """Climate entity for a given device in Homewizard cloud."""

    def __init__(
        self, device_web_socket: HomeWizardClimateWebSocket, hass: HomeAssistant
    ) -> None:
        """Initialize the device and identifiers."""
        self._device_web_socket = device_web_socket
        self._device_web_socket.set_on_state_change(self.on_device_state_change)
        self._hass = hass
        self._isIR = False
        self._isFAN = False
        self._isHEATER = False
        self._isDEHUMID = False
        self._logger = logging.getLogger(
            f"{__name__}.{self._device_web_socket.device.identifier}"
        )
        if self._device_web_socket.device.type == HomeWizardClimateDeviceType.INFRAREDHEATER:
            self._isIR = True
        if self._device_web_socket.device.type == HomeWizardClimateDeviceType.FAN:
            self._isFAN = True
        if self._device_web_socket.device.type == HomeWizardClimateDeviceType.HEATER:
            self._isHEATER = True
        if self._device_web_socket.device.type == HomeWizardClimateDeviceType.DEHUMIDIFIER:
            self._isDEHUMID = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_web_socket.device.identifier)},
            name=self.name,
        )

    @property
    def unique_id(self) -> str:
        """Return unique ID for this device."""
        return f"{self._device_web_socket.device.type}_{self._device_web_socket.device.identifier}"

    @property
    def name(self) -> str:
        """Return the name of the climate device."""
        return self._device_web_socket.device.name

    @property
    def current_temperature(self) -> int:
        """Return the current temperature."""
        return self._device_web_socket.last_state.current_temperature

    @property
    def fan_mode(self):
        """Return fan mode of the AC this group belongs to."""
        return FAN_ON

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        if self._isFAN:
            return [FAN_LOW, FAN_MEDIUM, FAN_HIGH]
        return [FAN_ON, FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    @property
    def preset_mode(self):
        """Return preset mode."""
        if self._isFAN:
            return PRESET_COMFORT
        if self._isDEHUMID:
            return self._device_web_socket.last_state.mode
        if self._isHEATER:
            mode = self._device_web_socket.last_state.mode
            if mode == "low":
                return PRESET_ECO
            elif mode == "high":
                return PRESET_BOOST
        raise NotImplementedError()

    @property
    def preset_modes(self):
        if self._isDEHUMID:
            return ['dehumidify', 'fan', 'laundry', 'continuous', 'automatic']
        if self._isFAN:
            return [PRESET_COMFORT, PRESET_SLEEP, PRESET_ECO]
        if self._isHEATER:
            return [PRESET_ECO, PRESET_BOOST]

    @property
    def supported_features(self) -> ClimateEntityFeature:
        if self._isDEHUMID:
            return (
                ClimateEntityFeature.TARGET_HUMIDITY
                | ClimateEntityFeature.PRESET_MODE
                | ClimateEntityFeature.FAN_MODE
                | ClimateEntityFeature.SWING_MODE
            )
        if self._isIR:
            return (
                ClimateEntityFeature.TARGET_TEMPERATURE
            )
        if self._isHEATER:
            return (
                ClimateEntityFeature.TARGET_TEMPERATURE
                | ClimateEntityFeature.PRESET_MODE
            )
        if self._isFAN:
            return (
                ClimateEntityFeature.FAN_MODE
                | ClimateEntityFeature.SWING_MODE
                | ClimateEntityFeature.PRESET_MODE
            )
        """Return the list of supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
        )

    @property
    def swing_modes(self) -> list[str]:
        """Return all possible swing modes."""
        return [SWING_HORIZONTAL, SWING_OFF]

    @property
    def swing_mode(self) -> str:
        """Return current swing mode."""
        return (
            SWING_HORIZONTAL
            if self._device_web_socket.last_state.oscillate
            else SWING_OFF
        )

    @property
    def hvac_mode(self):
        if self._isIR or self._isHEATER:
            if self._device_web_socket.last_state.power_on:
                return HVACMode.HEAT
            return HVACMode.OFF
        """Return hvac target hvac state."""
        if self._device_web_socket.last_state.power_on:
            result = (
                HVACMode.HEAT
                if self._device_web_socket.last_state.heater
                else HVACMode.COOL
            )
        else:
            result = HVACMode.OFF

        return result

    @property
    def hvac_modes(self):
        if self._isIR or self._isHEATER:
            return [HVACMode.HEAT, HVACMode.OFF]
        if self._isFAN:
            return [HVACMode.COOL, HVACMode.OFF]
        """Return the list of available operation modes."""
        return [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]

    @property
    def temperature_unit(self):
        """Return the current temperature unit."""
        return TEMP_CELSIUS

    @property
    def target_temperature_step(self) -> float:
        """Return the current target_temperature_step."""
        return 1

    @property
    def target_temperature_high(self) -> float:
        """Return the highest possible target temperature."""
        return 30

    @property
    def target_temperature_low(self) -> float:
        """Return the lowest possible target temperature."""
        return 14

    @property
    def min_temp(self) -> float:
        """Return the minimum possible temperature."""
        return self.target_temperature_low

    @property
    def max_temp(self) -> float:
        """Return the maximum possible temperature."""
        return self.target_temperature_high

    @property
    def humidity(self) -> float:
        """Return the current target temperature."""
        if self._isDEHUMID:
            return self._device_web_socket.last_state.target_humidity
        raise NotImplementedError()

    def set_humidity(self, target_humidity) -> None:
        """Set the current target humidity."""
        if self._isDEHUMID:
            return self._device_web_socket.set_target_humidity(
                int(target_humidity)
            )
        raise NotImplementedError()

    @property
    def target_temperature(self) -> float:
        """Return the current target temperature."""
        return self._device_web_socket.last_state.target_temperature

    def set_temperature(self, **kwargs) -> None:
        """Set the current target temperature."""
        if self._isDEHUMID:
            raise NotImplementedError()
        self._device_web_socket.set_target_temperature(
            int(kwargs.get(ATTR_TEMPERATURE, "0"))
        )

    def set_fan_mode(self, fan_mode: str) -> None:
        if self._isIR or self._isHEATER:
            raise NotImplementedError()

        if self._isDEHUMID:
            self._device_web_socket.set_fan_speed(fan_mode)
            return
        if self._isFAN:
            if fan_mode == FAN_ON:
                self._device_web_socket.turn_on()
            elif fan_mode == FAN_OFF:
                self._device_web_socket.turn_off()
            elif fan_mode == FAN_LOW:
                self._device_web_socket.set_speed(1)
            elif fan_mode == FAN_MEDIUM:
                self._device_web_socket.set_speed(2)
            elif fan_mode == FAN_HIGH:
                self._device_web_socket.set_speed(3)
            return

        """Set fan mode."""
        if fan_mode == FAN_ON:
            self._device_web_socket.turn_on()
        elif fan_mode == FAN_OFF:
            self._device_web_socket.turn_off()
        elif fan_mode == FAN_LOW:
            self._device_web_socket.set_fan_speed(1)
        elif fan_mode == FAN_MEDIUM:
            speed = 4 if self.hvac_mode == HVACMode.COOL else 2
            self._device_web_socket.set_fan_speed(speed)
        elif fan_mode == FAN_HIGH:
            speed = 8 if self.hvac_mode == HVACMode.COOL else 4
            self._device_web_socket.set_fan_speed(speed)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.HEAT:
            if not self._device_web_socket.last_state.power_on:
                self._device_web_socket.turn_on()
                time.sleep(1)
            if not self._device_web_socket.last_state.heater:
                self._device_web_socket.turn_on_heater()
        elif hvac_mode == HVACMode.OFF:
            self._device_web_socket.turn_off()
        else:
            if not self._device_web_socket.last_state.power_on:
                self._device_web_socket.turn_on()
                time.sleep(1)
            if self._device_web_socket.last_state.heater:
                self._device_web_socket.turn_on_cooler()

    def turn_on(self) -> None:
        """Turn on."""
        self._device_web_socket.turn_on()

    def turn_off(self) -> None:
        """Turn off."""
        self._device_web_socket.turn_off()

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        if self._isDEHUMID:
            self._device_web_socket.set_swing(swing_mode)
            return
        if swing_mode == SWING_HORIZONTAL:
            self._device_web_socket.turn_on_oscillation()
        else:
            self._device_web_socket.turn_off_oscillation()

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if self._isFAN:
            if preset_mode == PRESET_ECO:
                self._device_web_socket.set_mode('natural')
            elif preset_mode == PRESET_SLEEP:
                self._device_web_socket.set_mode('sleep')
            elif preset_mode == PRESET_COMFORT:
                self._device_web_socket.set_mode('normal')
        elif self._isHEATER:
            if preset_mode == PRESET_ECO:
                self._device_web_socket.set_mode("low")
            elif preset_mode == PRESET_BOOST:
                self._device_web_socket.set_mode("high")
        elif self._isDEHUMID:
            self._device_web_socket.set_mode(preset_mode)
        else:
            raise NotImplementedError()

    def turn_aux_heat_on(self) -> None:
        """Not implemented."""
        raise NotImplementedError()

    def turn_aux_heat_off(self) -> None:
        """Not implemented."""
        raise NotImplementedError()

    # def set_humidity(self, humidity: int) -> None:
    #     """Not implemented."""
    #     raise NotImplementedError()

    def on_device_state_change(
        self, state: HomeWizardClimateDeviceState, diff: str
    ) -> None:
        """Get called when any update is pushed through the websocket server andupdates HA state."""
        self._logger.debug("State updated, diff: %s", diff)
        self._hass.add_job(self.async_write_ha_state)
