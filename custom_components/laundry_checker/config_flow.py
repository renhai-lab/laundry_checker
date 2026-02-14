"""Config flow for Laundry Checker integration."""

from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol
import requests

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_LOCATION,
    CONF_LOCATION_NAME,
    CONF_LOCATION_SUFFIX,
    CONF_MAX_SUITABLE_HUMIDITY,
    CONF_MIN_SUITABLE_HOURS,
    CONF_MAX_POP,
    CONF_START_HOUR,
    CONF_END_HOUR,
    CONF_PREFERRED_END_HOUR,
    CONF_QWEATHER_KEY,
    CONF_QWEATHER_API_HOST,
    CONF_SCAN_INTERVAL,
    CONF_MAX_AQI,
    CONF_UNSUITABLE_WEATHER_TYPES,
    CONF_RAIN_LIGHT_THRESHOLD,
    CONF_RAIN_MODERATE_THRESHOLD,
    CONF_RAIN_HEAVY_THRESHOLD,
    CONF_RAIN_STORM_THRESHOLD,
    CONF_RAIN_WORK_COMMUTE_HOURS,
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
    DEFAULT_QWEATHER_API_HOST,
    DEFAULT_UNSUITABLE_WEATHER_TYPES,
    DEFAULT_RAIN_LIGHT_THRESHOLD,
    DEFAULT_RAIN_MODERATE_THRESHOLD,
    DEFAULT_RAIN_HEAVY_THRESHOLD,
    DEFAULT_RAIN_STORM_THRESHOLD,
    DEFAULT_RAIN_WORK_COMMUTE_HOURS,
)
from .helpers import (
    normalize_api_host,
    validate_coordinates,
    format_location,
    build_location_suffix,
)

_LOGGER = logging.getLogger(__name__)

CONF_CITY = "city"
CONF_MANUAL_LOCATION = "manual_location"
LOCATION_TYPE = "location_type"
CONF_LONGITUDE = "longitude"
CONF_LATITUDE = "latitude"


async def validate_api_key(hass: HomeAssistant, api_key: str, api_host: str) -> bool:
    """验证和风天气API密钥是否有效。"""
    base_url = normalize_api_host(api_host)
    url = f"{base_url}/v7/weather/now"
    params = {
        "location": "101010100",  # 使用北京作为测试位置
        "key": api_key,
    }

    try:
        response = await hass.async_add_executor_job(
            lambda: requests.get(url, params=params, timeout=10)
        )

        # 检查HTTP状态码
        if response.status_code != 200:
            _LOGGER.error(
                "HTTP error %s while validating API key: %s",
                response.status_code,
                response.text[:200],
            )
            return False

        # 尝试解析JSON
        try:
            data = response.json()
        except ValueError as json_err:
            _LOGGER.error(
                "Invalid JSON response while validating API key: %s. Response: %s",
                json_err,
                response.text[:200],
            )
            return False

        return data.get("code") == "200"
    except Exception as err:
        _LOGGER.error("Error validating API key: %s", err)
        return False


async def search_city(
    hass: HomeAssistant, api_key: str, api_host: str, city: str
) -> tuple[list[dict], str | None]:
    """搜索城市信息。

    返回:
        tuple: (城市列表, 错误码)
        错误码可能的值: None(成功), 'network_error', 'api_error', 'city_not_found'
    """
    # GeoAPI使用固定的公共域名，不使用用户的独立API Host
    # 用户的独立API Host仅用于天气数据API和空气质量API
    url = "https://geoapi.qweather.com/v2/city/lookup"
    params = {
        "location": city,
        "key": api_key,
    }

    _LOGGER.debug("Searching city: %s with API: %s", city, url)

    try:
        response = await hass.async_add_executor_job(
            lambda: requests.get(url, params=params, timeout=10)
        )

        # 检查HTTP状态码
        _LOGGER.debug("HTTP status code: %s", response.status_code)
        if response.status_code != 200:
            _LOGGER.error(
                "HTTP error %s while searching city %s: %s",
                response.status_code,
                city,
                response.text[:200],
            )
            return [], "network_error"

        # 尝试解析JSON
        try:
            data = response.json()
        except ValueError as json_err:
            _LOGGER.error(
                "Invalid JSON response for city %s: %s. Response text: %s",
                city,
                json_err,
                response.text[:200],
            )
            return [], "api_error"

        _LOGGER.debug("City search response: %s", data)

        code = data.get("code")
        if code == "200":
            locations = data.get("location", [])
            if not locations:
                _LOGGER.warning("No cities found for: %s", city)
                return [], "city_not_found"
            _LOGGER.info("Found %d cities for: %s", len(locations), city)
            return locations, None
        else:
            _LOGGER.error(
                "QWeather API returned error code: %s for city: %s", code, city
            )
            return [], "api_error"
    except requests.RequestException as err:
        _LOGGER.error("Network error while searching city %s: %s", city, err)
        return [], "network_error"
    except Exception as err:
        _LOGGER.exception("Unexpected error while searching city %s: %s", city, err)
        return [], "network_error"


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """验证用户输入。"""
    errors = {}

    # 验证API密钥
    api_key = data[CONF_QWEATHER_KEY]
    api_host = data.get(CONF_QWEATHER_API_HOST, DEFAULT_QWEATHER_API_HOST)
    if not await validate_api_key(hass, api_key, api_host):
        errors["base"] = "invalid_api_key"
        return {"errors": errors}

    return {"title": "洗衣检查器"}


class LaundryCheckerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Laundry Checker."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self._api_key: str = ""
        self._entry_data = {}
        self._reauth_entry = None
        self._cities = []
        self._use_ha_location = False
        self._api_host = DEFAULT_QWEATHER_API_HOST
        self._manual_longitude: float | None = None
        self._manual_latitude: float | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """处理初始步骤，输入API密钥。"""
        errors = {}
        default_host = (
            self._entry_data.get(CONF_QWEATHER_API_HOST) or DEFAULT_QWEATHER_API_HOST
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_QWEATHER_KEY): str,
                vol.Required(CONF_QWEATHER_API_HOST, default=default_host): str,
            }
        )

        if user_input is not None:
            self._api_key = user_input[CONF_QWEATHER_KEY]
            try:
                self._api_host = normalize_api_host(user_input[CONF_QWEATHER_API_HOST])
            except ValueError:
                errors["base"] = "invalid_api_host"
                return self.async_show_form(
                    step_id="user", data_schema=schema, errors=errors
                )
            valid = await validate_api_key(self.hass, self._api_key, self._api_host)

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
                            CONF_QWEATHER_API_HOST: self._api_host,
                        },
                    )
                    return self.async_abort(reason="reauth_successful")

                # 进入位置选择步骤
                return await self.async_step_location_type()

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
            elif user_input[LOCATION_TYPE] == "manual_coordinates":
                # 进入手动坐标输入步骤
                return await self.async_step_manual_coordinates()
            else:
                # 进入城市搜索步骤
                return await self.async_step_city_search()

        options = {
            "ha_location": "使用Home Assistant默认位置",
            "city_search": "搜索城市",
            "manual_coordinates": "手动输入经纬度坐标",
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
            cities, error_code = await search_city(
                self.hass, self._api_key, self._api_host, city
            )

            if error_code:
                errors["base"] = error_code
            elif cities:
                self._cities = cities
                return await self.async_step_city_select()
            else:
                errors["base"] = "city_not_found"

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
                city_name = selected_city.get("name", "")
                adm1 = selected_city.get("adm1", "")
                adm2 = selected_city.get("adm2", "")
                display_name = " ".join(
                    part for part in [city_name, adm1, adm2] if part
                )
                self._entry_data[CONF_LOCATION_NAME] = display_name or city_name
                self._entry_data[CONF_LOCATION_SUFFIX] = (
                    f"city_{build_location_suffix(city_name)}"
                )

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

    async def async_step_manual_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """手动输入经纬度坐标的步骤。"""
        errors = {}

        if user_input is not None:
            try:
                longitude = float(user_input[CONF_LONGITUDE])
                latitude = float(user_input[CONF_LATITUDE])

                # 验证坐标范围
                validate_coordinates(longitude, latitude)

                # 存储坐标信息
                formatted_location = format_location(longitude, latitude)
                self._entry_data[CONF_LOCATION] = formatted_location
                self._entry_data[CONF_USE_HA_LOCATION] = False
                self._entry_data[CONF_LOCATION_NAME] = formatted_location
                coord_suffix = formatted_location.replace(",", "_")
                self._entry_data[CONF_LOCATION_SUFFIX] = (
                    f"lat_lng_{build_location_suffix(coord_suffix)}"
                )

                _LOGGER.info(
                    "Manual coordinates set: %s", self._entry_data[CONF_LOCATION]
                )

                # 进入配置参数步骤
                return await self.async_step_parameters()

            except ValueError as err:
                _LOGGER.error("Invalid coordinates input: %s", err)
                if "range" in str(err).lower():
                    errors["base"] = "coordinates_out_of_range"
                else:
                    errors["base"] = "invalid_coordinates"
            except Exception as err:
                _LOGGER.exception("Unexpected error in manual coordinates: %s", err)
                errors["base"] = "invalid_coordinates"

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LONGITUDE,
                    description={"suggested_value": "121.47"},
                ): vol.Coerce(float),
                vol.Required(
                    CONF_LATITUDE,
                    description={"suggested_value": "31.23"},
                ): vol.Coerce(float),
            }
        )

        return self.async_show_form(
            step_id="manual_coordinates",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_parameters(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """配置其他参数的步骤。"""
        errors = {}

        if user_input is not None:
            # 合并所有配置
            data = {
                CONF_QWEATHER_KEY: self._api_key,
                CONF_QWEATHER_API_HOST: self._api_host,
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

            title = "洗衣检查器"
            if not self._use_ha_location:
                location_name = self._entry_data.get(CONF_LOCATION_NAME)
                if location_name:
                    title = f"洗衣检查器 ({location_name})"

            # 创建配置条目
            return self.async_create_entry(title=title, data=data)

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
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
                vol.Required(
                    CONF_UNSUITABLE_WEATHER_TYPES,
                    default=DEFAULT_UNSUITABLE_WEATHER_TYPES,
                ): cv.multi_select(DEFAULT_UNSUITABLE_WEATHER_TYPES),
                vol.Required(
                    CONF_RAIN_LIGHT_THRESHOLD,
                    default=DEFAULT_RAIN_LIGHT_THRESHOLD,
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=50)),
                vol.Required(
                    CONF_RAIN_MODERATE_THRESHOLD,
                    default=DEFAULT_RAIN_MODERATE_THRESHOLD,
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=50)),
                vol.Required(
                    CONF_RAIN_HEAVY_THRESHOLD,
                    default=DEFAULT_RAIN_HEAVY_THRESHOLD,
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                vol.Required(
                    CONF_RAIN_STORM_THRESHOLD,
                    default=DEFAULT_RAIN_STORM_THRESHOLD,
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                vol.Required(
                    CONF_RAIN_WORK_COMMUTE_HOURS,
                    default=DEFAULT_RAIN_WORK_COMMUTE_HOURS,
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
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
        self._api_host = self._entry_data.get(
            CONF_QWEATHER_API_HOST, DEFAULT_QWEATHER_API_HOST
        )

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
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        entry_data = self.config_entry.data
        entry_options = self.config_entry.options

        options = {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=entry_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
            vol.Required(
                CONF_MAX_SUITABLE_HUMIDITY,
                default=entry_options.get(
                    CONF_MAX_SUITABLE_HUMIDITY,
                    entry_data.get(
                        CONF_MAX_SUITABLE_HUMIDITY, DEFAULT_MAX_SUITABLE_HUMIDITY
                    ),
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            vol.Required(
                CONF_MIN_SUITABLE_HOURS,
                default=entry_options.get(
                    CONF_MIN_SUITABLE_HOURS,
                    entry_data.get(CONF_MIN_SUITABLE_HOURS, DEFAULT_MIN_SUITABLE_HOURS),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
            vol.Required(
                CONF_MAX_POP,
                default=entry_options.get(
                    CONF_MAX_POP, entry_data.get(CONF_MAX_POP, DEFAULT_MAX_POP)
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Required(
                CONF_MAX_AQI,
                default=entry_options.get(
                    CONF_MAX_AQI, entry_data.get(CONF_MAX_AQI, DEFAULT_MAX_AQI)
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=500)),
            vol.Required(
                CONF_START_HOUR,
                default=entry_options.get(
                    CONF_START_HOUR, entry_data.get(CONF_START_HOUR, DEFAULT_START_HOUR)
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
            vol.Required(
                CONF_END_HOUR,
                default=entry_options.get(
                    CONF_END_HOUR, entry_data.get(CONF_END_HOUR, DEFAULT_END_HOUR)
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
            vol.Required(
                CONF_PREFERRED_END_HOUR,
                default=entry_options.get(
                    CONF_PREFERRED_END_HOUR,
                    entry_data.get(CONF_PREFERRED_END_HOUR, DEFAULT_PREFERRED_END_HOUR),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
            vol.Required(
                CONF_UNSUITABLE_WEATHER_TYPES,
                default=entry_options.get(
                    CONF_UNSUITABLE_WEATHER_TYPES,
                    entry_data.get(
                        CONF_UNSUITABLE_WEATHER_TYPES,
                        DEFAULT_UNSUITABLE_WEATHER_TYPES,
                    ),
                ),
            ): cv.multi_select(DEFAULT_UNSUITABLE_WEATHER_TYPES),
            vol.Required(
                CONF_RAIN_LIGHT_THRESHOLD,
                default=entry_options.get(
                    CONF_RAIN_LIGHT_THRESHOLD,
                    entry_data.get(
                        CONF_RAIN_LIGHT_THRESHOLD, DEFAULT_RAIN_LIGHT_THRESHOLD
                    ),
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=50)),
            vol.Required(
                CONF_RAIN_MODERATE_THRESHOLD,
                default=entry_options.get(
                    CONF_RAIN_MODERATE_THRESHOLD,
                    entry_data.get(
                        CONF_RAIN_MODERATE_THRESHOLD, DEFAULT_RAIN_MODERATE_THRESHOLD
                    ),
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=50)),
            vol.Required(
                CONF_RAIN_HEAVY_THRESHOLD,
                default=entry_options.get(
                    CONF_RAIN_HEAVY_THRESHOLD,
                    entry_data.get(
                        CONF_RAIN_HEAVY_THRESHOLD, DEFAULT_RAIN_HEAVY_THRESHOLD
                    ),
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            vol.Required(
                CONF_RAIN_STORM_THRESHOLD,
                default=entry_options.get(
                    CONF_RAIN_STORM_THRESHOLD,
                    entry_data.get(
                        CONF_RAIN_STORM_THRESHOLD, DEFAULT_RAIN_STORM_THRESHOLD
                    ),
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            vol.Required(
                CONF_RAIN_WORK_COMMUTE_HOURS,
                default=entry_options.get(
                    CONF_RAIN_WORK_COMMUTE_HOURS,
                    entry_data.get(
                        CONF_RAIN_WORK_COMMUTE_HOURS,
                        DEFAULT_RAIN_WORK_COMMUTE_HOURS,
                    ),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
