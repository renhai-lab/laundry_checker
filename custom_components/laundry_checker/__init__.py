"""The Laundry Checker integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_LOCATION,
    CONF_MAX_SUITABLE_HUMIDITY,
    CONF_MIN_SUITABLE_HOURS,
    CONF_MAX_POP,
    CONF_START_HOUR,
    CONF_END_HOUR,
    CONF_PREFERRED_END_HOUR,
    CONF_QWEATHER_KEY,
    CONF_QWEATHER_API_HOST,
    DEFAULT_UNSUITABLE_WEATHER_TYPES,
    DEFAULT_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_USE_HA_LOCATION,
    CONF_MAX_AQI,
    DEFAULT_MAX_AQI,
    DEFAULT_QWEATHER_API_HOST,
    CONF_UNSUITABLE_WEATHER_TYPES,
    CONF_RAIN_LIGHT_THRESHOLD,
    CONF_RAIN_MODERATE_THRESHOLD,
    CONF_RAIN_HEAVY_THRESHOLD,
    CONF_RAIN_STORM_THRESHOLD,
    DEFAULT_RAIN_LIGHT_THRESHOLD,
    DEFAULT_RAIN_MODERATE_THRESHOLD,
    DEFAULT_RAIN_HEAVY_THRESHOLD,
    DEFAULT_RAIN_STORM_THRESHOLD,
)
from .coordinator import LaundryCheckerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Laundry Checker component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Laundry Checker from a config entry."""
    # 检查是否使用Home Assistant的位置
    use_ha_location = entry.data.get(CONF_USE_HA_LOCATION, False)

    # 获取位置信息
    location = entry.data[CONF_LOCATION]
    if use_ha_location:
        # 使用Home Assistant的配置位置
        location = f"{hass.config.longitude},{hass.config.latitude}"

    entry_options = entry.options

    max_suitable_humidity = entry_options.get(
        CONF_MAX_SUITABLE_HUMIDITY, entry.data[CONF_MAX_SUITABLE_HUMIDITY]
    )
    min_suitable_hours = entry_options.get(
        CONF_MIN_SUITABLE_HOURS, entry.data[CONF_MIN_SUITABLE_HOURS]
    )
    max_pop = entry_options.get(CONF_MAX_POP, entry.data[CONF_MAX_POP])
    start_hour = entry_options.get(CONF_START_HOUR, entry.data[CONF_START_HOUR])
    end_hour = entry_options.get(CONF_END_HOUR, entry.data[CONF_END_HOUR])
    preferred_end_hour = entry_options.get(
        CONF_PREFERRED_END_HOUR, entry.data[CONF_PREFERRED_END_HOUR]
    )
    max_aqi = entry_options.get(
        CONF_MAX_AQI, entry.data.get(CONF_MAX_AQI, DEFAULT_MAX_AQI)
    )
    unsuitable_weather_types = entry_options.get(
        CONF_UNSUITABLE_WEATHER_TYPES,
        entry.data.get(CONF_UNSUITABLE_WEATHER_TYPES, DEFAULT_UNSUITABLE_WEATHER_TYPES),
    )
    rain_light_threshold = entry_options.get(
        CONF_RAIN_LIGHT_THRESHOLD,
        entry.data.get(CONF_RAIN_LIGHT_THRESHOLD, DEFAULT_RAIN_LIGHT_THRESHOLD),
    )
    rain_moderate_threshold = entry_options.get(
        CONF_RAIN_MODERATE_THRESHOLD,
        entry.data.get(CONF_RAIN_MODERATE_THRESHOLD, DEFAULT_RAIN_MODERATE_THRESHOLD),
    )
    rain_heavy_threshold = entry_options.get(
        CONF_RAIN_HEAVY_THRESHOLD,
        entry.data.get(CONF_RAIN_HEAVY_THRESHOLD, DEFAULT_RAIN_HEAVY_THRESHOLD),
    )
    rain_storm_threshold = entry_options.get(
        CONF_RAIN_STORM_THRESHOLD,
        entry.data.get(CONF_RAIN_STORM_THRESHOLD, DEFAULT_RAIN_STORM_THRESHOLD),
    )

    coordinator = LaundryCheckerDataUpdateCoordinator(
        hass=hass,
        location=location,
        qweather_key=entry.data[CONF_QWEATHER_KEY],
        api_host=entry.data.get(CONF_QWEATHER_API_HOST, DEFAULT_QWEATHER_API_HOST),
        max_suitable_humidity=max_suitable_humidity,
        min_suitable_hours=min_suitable_hours,
        max_pop=max_pop,
        start_hour=start_hour,
        end_hour=end_hour,
        preferred_end_hour=preferred_end_hour,
        unsuitable_weather_types=unsuitable_weather_types,
        max_aqi=max_aqi,
        rain_light_threshold=rain_light_threshold,
        rain_moderate_threshold=rain_moderate_threshold,
        rain_heavy_threshold=rain_heavy_threshold,
        rain_storm_threshold=rain_storm_threshold,
    )

    try:
        # 首次加载数据
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("配置条目刷新错误: %s", err)
        # 让错误正常传播以触发重认证
        raise

    # 使用字典存储coordinator和其他数据
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "use_ha_location": use_ha_location,
    }

    # 获取配置
    scan_interval = entry_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    # 设置coordinator的更新间隔
    coordinator.update_interval = timedelta(hours=scan_interval)

    # 异步更新函数，现在直接使用coordinator的方法
    async def async_update(now=None):
        """更新洗衣状态。"""
        await coordinator.async_refresh()

    # 设置定时更新
    hass.data[DOMAIN][entry.entry_id]["unsub_timer"] = async_track_time_interval(
        hass, async_update, timedelta(hours=scan_interval)
    )

    # 如果使用Home Assistant的位置，添加位置变更的监听器
    if use_ha_location:

        @callback
        def handle_ha_location_update(event):
            """处理Home Assistant位置变更。"""
            if (
                event.data.get("latitude") is not None
                or event.data.get("longitude") is not None
            ):
                new_location = f"{hass.config.longitude},{hass.config.latitude}"
                _LOGGER.debug("Home Assistant位置已更改，更新位置为: %s", new_location)
                coordinator.location = new_location
                hass.async_create_task(coordinator.async_refresh())

        # 注册事件监听器
        unsub_location = hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, handle_ha_location_update
        )
        hass.data[DOMAIN][entry.entry_id]["unsub_location"] = unsub_location

    # 设置平台
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # 停止定时更新
    unsub_timer = hass.data[DOMAIN][entry.entry_id].get("unsub_timer")
    if unsub_timer:
        unsub_timer()

    # 停止位置监听
    unsub_location = hass.data[DOMAIN][entry.entry_id].get("unsub_location")
    if unsub_location:
        unsub_location()

    # 卸载平台
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entries to include the API host field."""
    version = config_entry.version or 1

    if version == 1:
        new_data = {**config_entry.data}
        new_data.setdefault(CONF_QWEATHER_API_HOST, DEFAULT_QWEATHER_API_HOST)

        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)
        _LOGGER.info(
            "Migrated Laundry Checker config entry %s to version 2 to store the QWeather API host.",
            config_entry.entry_id,
        )

    return True
