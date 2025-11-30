"""Config flow for Laundry Checker integration."""

from __future__ import annotations

from typing import Any
import voluptuous as vol
import requests

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_API_KEY

from .const import (
    DOMAIN,
    CONF_LOCATION,
    CONF_MAX_SUITABLE_HUMIDITY,
    CONF_MIN_SUITABLE_HOURS,
    CONF_MAX_POP,
    CONF_START_HOUR,
    CONF_END_HOUR,
    CONF_PREFERRED_END_HOUR,
    CONF_QWEATHER_KEY,
    CONF_SCAN_INTERVAL,
    CONF_MAX_AQI,
    DEFAULT_LOCATION,
    DEFAULT_MAX_SUITABLE_HUMIDITY,
    DEFAULT_MIN_SUITABLE_HOURS,
    DEFAULT_MAX_POP,
    DEFAULT_START_HOUR,
    DEFAULT_END_HOUR,
    DEFAULT_PREFERRED_END_HOUR,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_MAX_AQI,
    CONF_USE_HA_LOCATION,
)

CONF_CITY = "city"
CONF_MANUAL_LOCATION = "manual_location"
LOCATION_TYPE = "location_type"


async def validate_api_key(hass: HomeAssistant, api_key: str) -> bool:
    """验证和风天气API密钥是否有效。"""
    url = "https://devapi.qweather.com/v7/weather/now"
    params = {
        "location": "101010100",  # 使用北京作为测试位置
        "key": api_key,
    }

    try:
        response = await hass.async_add_executor_job(
            lambda: requests.get(url, params=params, timeout=10)
        )
        data = response.json()
        return data.get("code") == "200"
    except Exception:
        return False


async def search_city(hass: HomeAssistant, api_key: str, city: str) -> list[dict]:
    """搜索城市信息。"""
    url = "https://geoapi.qweather.com/v2/city/lookup"
    params = {
        "location": city,
        "key": api_key,
    }

    try:
        response = await hass.async_add_executor_job(
            lambda: requests.get(url, params=params, timeout=10)
        )
        data = response.json()
        if data.get("code") == "200":
            return data.get("location", [])
        return []
    except Exception:
        return []


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """验证用户输入。"""
    errors = {}

    # 验证API密钥
    api_key = data[CONF_QWEATHER_KEY]
    if not await validate_api_key(hass, api_key):
        errors["base"] = "invalid_api_key"
        return {"errors": errors}

    return {"title": "洗衣检查器"}


class LaundryCheckerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Laundry Checker."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self._api_key = None
        self._entry_data = {}
        self._reauth_entry = None
        self._cities = []
        self._use_ha_location = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """处理初始步骤，输入API密钥。"""
        errors = {}

        if user_input is not None:
            self._api_key = user_input[CONF_QWEATHER_KEY]
            valid = await validate_api_key(self.hass, self._api_key)

            if not valid:
                errors["base"] = "invalid_api_key"
            else:
                if self._reauth_entry:
                    # 如果正在重新认证，更新现有条目
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data={
                            **self._reauth_entry.data,
                            CONF_QWEATHER_KEY: self._api_key,
                        },
                    )
                    return self.async_abort(reason="reauth_successful")

                # 进入位置选择步骤
                return await self.async_step_location_type()

        schema = vol.Schema({vol.Required(CONF_QWEATHER_KEY): str})

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_location_type(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """选择位置类型的步骤。"""
        if user_input is not None:
            if user_input[LOCATION_TYPE] == "ha_location":
                self._use_ha_location = True
                # 使用HA位置，直接进入配置参数步骤
                return await self.async_step_parameters()
            else:
                # 进入城市搜索步骤
                return await self.async_step_city_search()

        options = {
            "ha_location": "使用Home Assistant默认位置",
            "city_search": "搜索城市",
        }

        schema = vol.Schema(
            {
                vol.Required(LOCATION_TYPE, default="ha_location"): vol.In(options),
            }
        )

        return self.async_show_form(step_id="location_type", data_schema=schema)

    async def async_step_city_search(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """搜索城市的步骤。"""
        errors = {}

        if user_input is not None:
            city = user_input[CONF_CITY]
            cities = await search_city(self.hass, self._api_key, city)

            if not cities:
                errors["base"] = "city_not_found"
            else:
                self._cities = cities
                return await self.async_step_city_select()

        schema = vol.Schema({vol.Required(CONF_CITY): str})

        return self.async_show_form(
            step_id="city_search",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_city_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """选择搜索到的城市的步骤。"""
        if user_input is not None:
            city_id = user_input["city_id"]
            selected_city = next(
                (city for city in self._cities if city["id"] == city_id), None
            )

            if selected_city:
                # 存储所选城市的位置信息
                self._entry_data[CONF_LOCATION] = (
                    f"{selected_city['lon']},{selected_city['lat']}"
                )
                self._entry_data[CONF_USE_HA_LOCATION] = False

                # 进入配置参数步骤
                return await self.async_step_parameters()

        options = {
            city["id"]: f"{city['name']} ({city['adm1']} {city['adm2']})"
            for city in self._cities
        }

        schema = vol.Schema(
            {
                vol.Required("city_id"): vol.In(options),
            }
        )

        return self.async_show_form(step_id="city_select", data_schema=schema)

    async def async_step_parameters(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """配置其他参数的步骤。"""
        errors = {}

        if user_input is not None:
            # 合并所有配置
            data = {
                CONF_QWEATHER_KEY: self._api_key,
                **user_input,
            }

            if self._use_ha_location:
                # 使用Home Assistant的位置
                data[CONF_LOCATION] = (
                    f"{self.hass.config.longitude},{self.hass.config.latitude}"
                )
                data[CONF_USE_HA_LOCATION] = True
            else:
                # 使用之前选择的城市位置
                data[CONF_LOCATION] = self._entry_data[CONF_LOCATION]
                data[CONF_USE_HA_LOCATION] = False

            # 创建配置条目
            return self.async_create_entry(title="洗衣检查器", data=data)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MAX_SUITABLE_HUMIDITY,
                    default=DEFAULT_MAX_SUITABLE_HUMIDITY,
                ): vol.Coerce(float),
                vol.Required(
                    CONF_MIN_SUITABLE_HOURS, default=DEFAULT_MIN_SUITABLE_HOURS
                ): vol.Coerce(int),
                vol.Required(CONF_MAX_POP, default=DEFAULT_MAX_POP): vol.Coerce(int),
                vol.Required(CONF_MAX_AQI, default=DEFAULT_MAX_AQI): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=500)
                ),
                vol.Required(CONF_START_HOUR, default=DEFAULT_START_HOUR): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=23)
                ),
                vol.Required(CONF_END_HOUR, default=DEFAULT_END_HOUR): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=23)
                ),
                vol.Required(
                    CONF_PREFERRED_END_HOUR, default=DEFAULT_PREFERRED_END_HOUR
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
            }
        )

        return self.async_show_form(
            step_id="parameters",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(self, user_input=None):
        """处理重新认证。"""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._entry_data = dict(self._reauth_entry.data)

        return await self.async_step_user()

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return LaundryCheckerOptionsFlow(config_entry)


class LaundryCheckerOptionsFlow(config_entries.OptionsFlow):
    """Handle a option flow for Laundry Checker."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
