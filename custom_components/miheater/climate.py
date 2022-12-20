"""
    Support for Xiaomi wifi-enabled home heaters via miio.
    author: sunfang1cn@gmail.com
"""
import logging
import enum
import voluptuous as vol
import asyncio

from homeassistant.components.climate import ClimateEntity, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    DOMAIN, ATTR_HVAC_MODE, HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_HOST, ATTR_ENTITY_ID, CONF_NAME, CONF_TOKEN,
    TEMP_CELSIUS)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['python-miio>=0.5.11']
SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE)
DATA_KEY = 'climate.xiaomi_miio_heater'

SERVICE_SET_BUZZER = 'xiaomi_heater_set_buzzer'
SERVICE_SET_BRIGHTNESS = 'xiaomi_heater_set_brightness'
SERVICE_SET_POWEROFF_TIME = 'xiaomi_heater_set_poweroff_time'
SERVICE_SET_CHILD_LOCK = 'xiaomi_heater_set_child_lock'

CONF_BUZZER = 'buzzer'
CONF_BRIGHTNESS = 'brightness'
CONF_POWEROFF_TIME = 'poweroff_time'
CONF_CHILD_LOCK = 'lock'

MIN_TEMP = 16
MAX_TEMP = 32
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
})

SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
})

SERVICE_SCHEMA_SET_BUZZER = SERVICE_SCHEMA.extend({
    vol.Required(CONF_BUZZER): vol.All(vol.Coerce(str), vol.Clamp('off', 'on'))
})
SERVICE_SCHEMA_SET_BRIGHTNESS = SERVICE_SCHEMA.extend({
    vol.Required(CONF_BRIGHTNESS): vol.All(vol.Coerce(int), vol.Range(min=0, max=2)),
})
SERVICE_SCHEMA_SET_POWEROFF_TIME = SERVICE_SCHEMA.extend({
    vol.Required(CONF_POWEROFF_TIME): vol.All(vol.Coerce(int), vol.Range(min=0, max=28800)),
})
SERVICE_SCHEMA_SET_CHILD_LOCK = SERVICE_SCHEMA.extend({
    vol.Required(CONF_CHILD_LOCK): vol.All(vol.Coerce(str), vol.Clamp('off', 'on'))
})


SERVICE_TO_METHOD = {
    SERVICE_SET_BUZZER: {'method': 'async_set_buzzer',
                            'schema': SERVICE_SCHEMA_SET_BUZZER},
    SERVICE_SET_BRIGHTNESS: {'method': 'async_set_brightness',
                            'schema': SERVICE_SCHEMA_SET_BRIGHTNESS},
    SERVICE_SET_POWEROFF_TIME: {'method': 'async_set_poweroff_time',
                            'schema': SERVICE_SCHEMA_SET_POWEROFF_TIME},
    SERVICE_SET_CHILD_LOCK: {'method': 'async_set_child_lock',
                            'schema': SERVICE_SCHEMA_SET_CHILD_LOCK},
}

def setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Perform the setup for Xiaomi heaters."""
    from miio import Device, DeviceException
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)

    _LOGGER.info("Initializing Xiaomi heaters with host %s (token %s...)", host, token[:5])

    try:
        device = Device(host, token)

        device_info = device.info()
        model = device_info.model
        unique_id = "{}-{}".format(model, device_info.mac_address)
        _LOGGER.info("%s %s %s detected",
                     model,
                     device_info.firmware_version,
                     device_info.hardware_version)
    except DeviceException:
        _LOGGER.exception('Fail to setup Xiaomi heater')
        raise PlatformNotReady
    miHeater = MiHeater(device, name, unique_id, hass)
    hass.data[DATA_KEY][host] = miHeater
    async_add_devices([miHeater], update_before_add=True)

    async def async_service_handler(service):
        """Map services to methods on XiaomiAirConditioningCompanion."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = {key: value for key, value in service.data.items()
                  if key != ATTR_ENTITY_ID}
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            devices = [device for device in hass.data[DATA_KEY].values() if
                       device.entity_id in entity_ids]
        else:
            devices = hass.data[DATA_KEY].values()

        update_tasks = []
        for device in devices:
            if not hasattr(device, method['method']):
                continue
            await getattr(device, method['method'])(**params)
            update_tasks.append(device.async_update_ha_state(True))

        if update_tasks:
            await asyncio.wait(update_tasks, loop=hass.loop)

    for service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service].get('schema', SERVICE_SCHEMA)
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=schema)

class OperationMode(enum.Enum):
    Heat = 'heat'
    Off = 'off'

class MiHeater(ClimateEntity):
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
        self._poweroff_time = None
        self._buzzer = None
        self._brightness = None
        self._child_lock = None
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
    
    @asyncio.coroutine
    def async_update(self):
        """Update the state of this device."""
        try:
            data = {}
            power = self._device.send('get_prop', ['power'])[0]
            humidity = self._device.send('get_prop', ['relative_humidity'])[0]
            target_temperature = self._device.send('get_prop', ['target_temperature'])[0]
            current_temperature = self._device.send('get_prop', ['temperature'])[0]
            poweroff_time = self._device.send('get_prop', ['poweroff_time'])[0]
            buzzer = self._device.send('get_prop', ['buzzer'])[0]
            brightness = self._device.send('get_prop', ['brightness'])[0]
            child_lock = self._device.send('get_prop', ['child_lock'])[0]
            if power == 'off':
                self._hvac_mode = 'off'
            else:
                self._hvac_mode = "heat"
            self._poweroff_time = None
            self._buzzer = None
            self._brightness = None
            self._child_lock = None 
            self._target_temperature = target_temperature
            self._current_temperature = current_temperature
            self._power = power != "off"
            self._state_attrs.update({
                ATTR_HVAC_MODE: power if power == "off"  else "heat",
                ATTR_TEMPERATURE:target_temperature,
                "power": power,
                "humidity": humidity,
                "poweroff_time": poweroff_time,
                "buzzer": buzzer,
                "brightness": brightness,
                "child_lock": child_lock,
                "current_temperature":current_temperature,
                "temperature":target_temperature
            })
        except DeviceException:
            _LOGGER.exception('Fail to get_prop from Xiaomi heater')
            raise PlatformNotReady

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

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

    @asyncio.coroutine
    def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._device.send('set_target_temperature', [int(temperature)])

    @asyncio.coroutine
    def async_set_brightness(self, **kwargs):
        """Set new led brightness."""
        brightness = kwargs.get(CONF_BRIGHTNESS)
        if brightness is None:
            return
        self._device.send('set_brightness', [int(brightness)])

    @asyncio.coroutine
    def async_set_poweroff_time(self, **kwargs):
        """Set new led brightness."""
        poweroff_time = kwargs.get(CONF_POWEROFF_TIME)
        if poweroff_time is None:
            return
        self._device.send('set_poweroff_time', [int(poweroff_time)])

    @asyncio.coroutine
    def async_set_child_lock(self, **kwargs):
        """Set new led brightness."""
        child_lock = kwargs.get(CONF_CHILD_LOCK)
        if child_lock is None:
            return
        self._device.send('set_child_lock', [str(child_lock)])

    @asyncio.coroutine
    def async_set_buzzer(self, **kwargs):
        """Set new led brightness."""
        buzzer = kwargs.get(CONF_BUZZER)
        if buzzer is None:
            return
        self._device.send('set_buzzer', [str(buzzer)])

    @asyncio.coroutine
    def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == OperationMode.Heat.value:
            result = self._device.send('set_power', ['on'])
            # if result[0] == 'ok':
            #     self.async_update()
            # self.async_turn_on()
        elif hvac_mode == OperationMode.Off.value:
            result = self._device.send('set_power', ['off'])
            # if result[0] == 'ok':
            #     self.async_update()
            # self.async_turn_off()
        else:
            _LOGGER.error("Unrecognized operation mode: %s", hvac_mode)

