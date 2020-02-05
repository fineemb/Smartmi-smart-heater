"""
    Support for Xiaomi wifi-enabled home heaters via miio.
    author: sunfang1cn@gmail.com
"""
import logging
import enum
import voluptuous as vol
import asyncio

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    DOMAIN, ATTR_HVAC_MODE, HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_HOST, CONF_NAME, CONF_TOKEN,
    TEMP_CELSIUS)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import PlatformNotReady


_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['python-miio>=0.3.1']
SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE)
SERVICE_SET_ROOM_TEMP = 'miheater_set_room_temperature'
MIN_TEMP = 16
MAX_TEMP = 32
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
})

SET_ROOM_TEMP_SCHEMA = vol.Schema({
    vol.Optional('temperature'): cv.positive_int
})



def setup_platform(hass, config, add_devices, discovery_info=None):
    """Perform the setup for Xiaomi heaters."""
    from miio import Device, DeviceException

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)

    _LOGGER.info("Initializing Xiaomi heaters with host %s (token %s...)", host, token[:5])

    devices = []
    unique_id = None

    try:
        device = Device(host, token)

        device_info = device.info()
        model = device_info.model
        unique_id = "{}-{}".format(model, device_info.mac_address)
        _LOGGER.info("%s %s %s detected",
                     model,
                     device_info.firmware_version,
                     device_info.hardware_version)
        miHeater = MiHeater(device, name, unique_id, hass)
        devices.append(miHeater)
        add_devices(devices)
        async def set_room_temp(service):
            """Set room temp."""
            temperature = service.data.get('temperature')
            await miHeater.async_set_temperature(temperature)

        hass.services.async_register(DOMAIN, SERVICE_SET_ROOM_TEMP,
                                     set_room_temp, schema=SET_ROOM_TEMP_SCHEMA)
    except DeviceException:
        _LOGGER.exception('Fail to setup Xiaomi heater')
        raise PlatformNotReady

class OperationMode(enum.Enum):
    Heat = 'heat'
    Off = 'off'

class MiHeater(ClimateDevice):
    from miio import DeviceException

    """Representation of a MiHeater device."""

    def __init__(self, device, name, unique_id, _hass):
        """Initialize the heater."""
        self._device = device
        self._name = name
        self._state_attrs = {}
        self._target_temperature = 0
        self._current_temperature = 0
        self._power = None
        self._hvac_mode = None
        self.entity_id = generate_entity_id('climate.{}', unique_id, hass=_hass)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self) -> str:
        """Return the current state."""
        return self.hvac_mode

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS
    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS
    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def hvac_modes(self):
        """Return the list of available hvac modes."""
        return [mode.value for mode in OperationMode]
        
    @property
    def hvac_mode(self):
        """Return hvac mode ie. heat, cool, fan only."""
        return self._hvac_mode

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1
    def update(self):
        try:
            data = {}
            power = self._device.send('get_prop', ['power'])[0]
            humidity = self._device.send('get_prop', ['relative_humidity'])[0]
            target_temperature = self._device.send('get_prop', ['target_temperature'])[0]
            current_temperature = self._device.send('get_prop', ['temperature'])[0]
            if power == 'off':
                self._hvac_mode = 'off'
            else:
                self._hvac_mode = "heat"
            self._target_temperature = current_temperature != 16
            self._current_temperature = current_temperature != 16
            self._power = power != "off"
            self._state_attrs.update({
                ATTR_HVAC_MODE: power if power == "off"  else "heat",
                "power": power,
                "humidity": humidity,
                ATTR_TEMPERATURE:target_temperature,
                "current_temperature":current_temperature
            })
        except DeviceException:
            _LOGGER.exception('Fail to get_prop from Xiaomi heater')
            raise PlatformNotReady

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def is_on(self):
        """Return true if heater is on."""
        return self._power == 'on'

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return MIN_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return MAX_TEMP

    @property
    def current_operation(self):
        """Return current operation."""
        return OperationMode.Off.value if self._power == 'off' else OperationMode.Heat.value

    @property
    def operation_list(self):
        """List of available operation modes."""
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._device.send('set_target_temperature', [int(temperature)])

    @asyncio.coroutine
    def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == OperationMode.Heat.value:
            self._device.send('set_power', ['on'])
            # self.async_turn_on()
        elif hvac_mode == OperationMode.Off.value:
            self._device.send('set_power', ['off'])
            # self.async_turn_off()
        else:
            _LOGGER.error("Unrecognized operation mode: %s", hvac_mode)

