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
    DEFAULT_UNSUITABLE_WEATHER_TYPES,
    DEFAULT_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_USE_HA_LOCATION,
    CONF_MAX_AQI,
    DEFAULT_MAX_AQI,
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

    coordinator = LaundryCheckerDataUpdateCoordinator(
        hass=hass,
        location=location,
        qweather_key=entry.data[CONF_QWEATHER_KEY],
        max_suitable_humidity=entry.data[CONF_MAX_SUITABLE_HUMIDITY],
        min_suitable_hours=entry.data[CONF_MIN_SUITABLE_HOURS],
        max_pop=entry.data[CONF_MAX_POP],
        start_hour=entry.data[CONF_START_HOUR],
        end_hour=entry.data[CONF_END_HOUR],
        preferred_end_hour=entry.data[CONF_PREFERRED_END_HOUR],
        unsuitable_weather_types=DEFAULT_UNSUITABLE_WEATHER_TYPES,
        max_aqi=entry.data.get(CONF_MAX_AQI, DEFAULT_MAX_AQI),
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
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

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
