"""Sensor platform for Laundry Checker integration."""

import logging
from typing import Dict, Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DOMAIN,
    ATTR_ESTIMATED_DRYING_TIME,
    DRYING_TIME_SENSOR_NAME,
)
from .coordinator import LaundryCheckerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Laundry Checker sensor based on a config entry."""
    # 从域数据中获取coordinator实例
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # 添加传感器
    async_add_entities([LaundryDryingTimeSensor(coordinator, entry)], True)


class LaundryDryingTimeSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Laundry Drying Time Sensor."""

    _attr_has_entity_name = True
    _attr_name = "Estimated Drying Time"
    _attr_icon = "mdi:clock-time-eight"

    def __init__(
        self, coordinator: LaundryCheckerDataUpdateCoordinator, entry: ConfigEntry
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_drying_time"

    @property
    def native_value(self) -> Optional[float]:
        """Return the native value of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data["stats"].get(ATTR_ESTIMATED_DRYING_TIME, 0)

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        value = self.native_value
        if value is None:
            return None
        return f"{value}小时"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}

        stats = self.coordinator.data["stats"]
        return {
            "best_drying_period": stats.get("best_drying_period", ""),
            "suitable_hours": stats.get("suitable_hours", 0),
            "avg_humidity": stats.get("avg_humidity", 0),
            "has_precipitation": stats.get("has_precipitation", False),
            "max_pop": stats.get("max_pop", 0),
            "weather_conditions": ", ".join(stats.get("weather_conditions", [])),
        }

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "洗衣检查器",
            "manufacturer": "自定义集成",
            "model": "Laundry Checker",
            "sw_version": "0.1.0",
        }
