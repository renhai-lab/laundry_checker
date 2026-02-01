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
    RAIN_WITHIN_6H_SENSOR_NAME,
    RAIN_TOMORROW_SENSOR_NAME,
    RAIN_DAY_AFTER_TOMORROW_SENSOR_NAME,
    ATTR_WILL_RAIN,
    ATTR_RAIN_LEVEL,
    ATTR_RAIN_HOURS,
    ATTR_TOTAL_PRECIP,
    ATTR_MAX_HOURLY_PRECIP,
    ATTR_RAIN_MAX_POP,
)
from .coordinator import LaundryCheckerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Laundry Checker sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            LaundryDryingTimeSensor(coordinator, entry),
            RainForecastSensor(
                coordinator,
                entry,
                "next_6h",
                RAIN_WITHIN_6H_SENSOR_NAME,
                "rain_within_6h",
                "rain_within_6h",
            ),
            RainForecastSensor(
                coordinator,
                entry,
                "tomorrow",
                RAIN_TOMORROW_SENSOR_NAME,
                "rain_tomorrow",
                "rain_tomorrow",
            ),
            RainForecastSensor(
                coordinator,
                entry,
                "day_after_tomorrow",
                RAIN_DAY_AFTER_TOMORROW_SENSOR_NAME,
                "rain_day_after_tomorrow",
                "rain_day_after_tomorrow",
            ),
        ],
        True,
    )


class LaundryDryingTimeSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Laundry Drying Time Sensor for today."""

    _attr_has_entity_name = True
    _attr_name = "Today's Estimated Drying Time"
    _attr_icon = "mdi:clock-time-eight"

    def __init__(
        self, coordinator: LaundryCheckerDataUpdateCoordinator, entry: ConfigEntry
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_drying_time_today"

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
        return f"{value} hours"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return today's state attributes."""
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
            "name": "Laundry Checker",
            "manufacturer": "Custom Integration",
            "model": "Laundry Checker",
            "sw_version": "0.1.0",
        }


class RainForecastSensor(CoordinatorEntity, SensorEntity):
    """Representation of a rain forecast sensor."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:weather-rainy"

    def __init__(
        self,
        coordinator: LaundryCheckerDataUpdateCoordinator,
        entry: ConfigEntry,
        period_key: str,
        name: str,
        unique_id_suffix: str,
        translation_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._period_key = period_key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._attr_translation_key = translation_key

    @property
    def native_value(self) -> Optional[str]:
        """Return the native value of the sensor."""
        if not self.coordinator.data:
            return None
        forecast = self.coordinator.data.get("rain_forecast", {}).get(self._period_key)
        if not forecast:
            return None
        return "rain" if forecast.get("will_rain") else "no_rain"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return rain forecast attributes."""
        if not self.coordinator.data:
            return {}

        forecast = self.coordinator.data.get("rain_forecast", {}).get(self._period_key)
        if not forecast:
            return {}

        return {
            ATTR_WILL_RAIN: forecast.get("will_rain", False),
            ATTR_RAIN_LEVEL: forecast.get("rain_level", "无雨"),
            ATTR_RAIN_HOURS: forecast.get("rain_hours", 0),
            ATTR_TOTAL_PRECIP: forecast.get("total_precipitation", 0),
            ATTR_MAX_HOURLY_PRECIP: forecast.get("max_hourly_precipitation", 0),
            ATTR_RAIN_MAX_POP: forecast.get("max_precipitation_probability", 0),
        }

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Laundry Checker",
            "manufacturer": "Custom Integration",
            "model": "Laundry Checker",
            "sw_version": "0.1.0",
        }
