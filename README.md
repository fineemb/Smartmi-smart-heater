<!--
 * @Author        : fineemb
 * @Github        : https://github.com/fineemb
 * @Description   : 
 * @Date          : 2019-12-19 22:01:59
 * @LastEditors   : fineemb
 * @LastEditTime  : 2020-02-03 12:16:46
 -->
# Smartmi Smart Heater

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

This is a custom component for home assistant to integrate the Smartmi smart heater.

![Smartmi_smart_heater](https://sc01.alicdn.com/kf/H0beecf680bd94ab284ceab2476b0b01bP/231348130/H0beecf680bd94ab284ceab2476b0b01bP.jpg)

Please follow the instructions on [Retrieving the Access Token](https://home-assistant.io/components/xiaomi/#retrieving-the-access-token) to get the API token to use in the configuration.yaml file.

Credits: Thanks to [Rytilahti](https://github.com/rytilahti/python-miio) for all the work.

## Features

### viomi.health_pot.v1

* Sensors
  - hvac_modes: heat,off
  - min_temp
  - max_temp
  - target_temp_step
  - current_temperature
  - temperature
  - curr_tempe
  - power
  - humidity
  - target_temperature
* Chart
  - Temperature History
* Services
  - set_hvac_mode
  - set_temperature

## Setup

```yaml
# configuration.yaml

climate: 
  - platform: miheater
    host: 192.168.1.13
    token: a9bd32552dc9bd4e156954c20ddbcb38
    name: 取暖器

```

Configuration variables:
- **host** (*Required*): The IP of your cooker.
- **token** (*Required*): The API token of your cooker.
- **name** (*Optional*): The name of your cooker.

## Platform services

#### Service `climate.set_hvac_mode`

Specify the heater mode.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific heater.                  |
| `hvac_mode`               |      yes | Specify the heater mode (heat/off).       |

#### Service `climate.set_temperature`

Set the temperature of heater.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific heater.     |
| `temperature`             | yes      | Set the temperature of heater.   |
