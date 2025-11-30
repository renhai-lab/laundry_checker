"""Binary sensor platform for laundry checker."""

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import (
    DOMAIN,
    BINARY_SENSOR_NAME,
    ATTR_SUITABLE_HOURS,
    ATTR_AVERAGE_HUMIDITY,
    ATTR_HAS_PRECIPITATION,
    ATTR_MAX_POP,
    ATTR_WEATHER_CONDITIONS,
    ATTR_ESTIMATED_DRYING_TIME,
    ATTR_BEST_DRYING_PERIOD,
    ATTR_WIND_CONDITIONS,
    ATTR_DETAILED_MESSAGE,
    ATTR_TOMORROW_DETAIL,
    ATTR_UV_INDEX,
    ATTR_AQI,
    ATTR_AQI_LEVEL,
    ATTR_PRIMARY_POLLUTANT,
)
from .coordinator import LaundryCheckerDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the laundry checker binary sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            LaundryCheckerBinarySensor(coordinator, entry),
            TomorrowLaundryCheckerBinarySensor(coordinator, entry)
        ],
        True
    )


class LaundryCheckerBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a laundry checker binary sensor for today."""

    _attr_has_entity_name = True
    _attr_name = "Today's Laundry Advice"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:washing-machine"

    def __init__(
        self, coordinator: LaundryCheckerDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_suitable_today"

    @property
    def is_on(self) -> bool:
        """Return true if conditions are suitable for laundry today."""
        return self.coordinator.data["is_suitable"] if self.coordinator.data else False

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes for today."""
        if not self.coordinator.data:
            return {}

        stats = self.coordinator.data["stats"]
        attributes = {
            ATTR_SUITABLE_HOURS: stats.get("suitable_hours", 0),
            ATTR_AVERAGE_HUMIDITY: round(stats.get("avg_humidity", 0), 1),
            ATTR_HAS_PRECIPITATION: stats.get("has_precipitation", False),
            ATTR_MAX_POP: stats.get("max_pop", 0),
            ATTR_WEATHER_CONDITIONS: ", ".join(stats.get("weather_conditions", [])),
            ATTR_ESTIMATED_DRYING_TIME: stats.get("estimated_drying_time", 0),
            ATTR_BEST_DRYING_PERIOD: stats.get("best_drying_period", ""),
        }

        if "uv_index" in stats:
            attributes[ATTR_UV_INDEX] = stats["uv_index"]

        if "aqi" in stats:
            attributes[ATTR_AQI] = stats["aqi"]
            attributes[ATTR_AQI_LEVEL] = stats.get("aqi_level", "")
            attributes[ATTR_PRIMARY_POLLUTANT] = stats.get("primary_pollutant", "")

        if "wind_conditions" in stats:
            attributes[ATTR_WIND_CONDITIONS] = ", ".join(stats["wind_conditions"])

        if "detailed_message" in self.coordinator.data:
            attributes[ATTR_DETAILED_MESSAGE] = self.coordinator.data["detailed_message"]

        attributes["message"] = self.coordinator.data.get("message", "")

        return attributes

    @property
    def device_info(self) -> dict:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Laundry Checker",
            "manufacturer": "Custom Integration",
            "model": "Laundry Checker",
            "sw_version": "0.1.0",
        }


class TomorrowLaundryCheckerBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a laundry checker binary sensor for tomorrow."""

    _attr_has_entity_name = True
    _attr_name = "Tomorrow's Laundry Advice"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:washing-machine-alert"

    def __init__(
        self, coordinator: LaundryCheckerDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_suitable_tomorrow"

    @property
    def is_on(self) -> bool:
        """Return true if conditions are suitable for laundry tomorrow."""
        if not self.coordinator.data or "tomorrow_stats" not in self.coordinator.data:
            return False
        return self.coordinator.data["tomorrow_stats"].get("is_suitable", False)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes for tomorrow."""
        if not self.coordinator.data or "tomorrow_stats" not in self.coordinator.data:
            return {}

        stats = self.coordinator.data["tomorrow_stats"]
        attributes = {
            ATTR_SUITABLE_HOURS: stats.get("suitable_hours", 0),
            ATTR_AVERAGE_HUMIDITY: round(stats.get("avg_humidity", 0), 1),
            ATTR_HAS_PRECIPITATION: stats.get("has_precipitation", False),
            ATTR_MAX_POP: stats.get("max_pop", 0),
            ATTR_WEATHER_CONDITIONS: ", ".join(stats.get("weather_conditions", [])),
            ATTR_ESTIMATED_DRYING_TIME: stats.get("estimated_drying_time", 0),
            ATTR_BEST_DRYING_PERIOD: stats.get("best_drying_period", ""),
        }

        if "uv_index" in stats:
            attributes[ATTR_UV_INDEX] = stats["uv_index"]

        if "aqi" in stats:
            attributes[ATTR_AQI] = stats["aqi"]
            attributes[ATTR_AQI_LEVEL] = stats.get("aqi_level", "")
            attributes[ATTR_PRIMARY_POLLUTANT] = stats.get("primary_pollutant", "")

        if "wind_conditions" in stats:
            attributes[ATTR_WIND_CONDITIONS] = ", ".join(stats["wind_conditions"])

        if "tomorrow_detail" in self.coordinator.data:
            attributes[ATTR_DETAILED_MESSAGE] = stats.get("detailed_message", "")

        attributes["message"] = self.coordinator.data.get("tomorrow_message", "")

        return attributes

    @property
    def device_info(self) -> dict:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Laundry Checker",
            "manufacturer": "Custom Integration",
            "model": "Laundry Checker",
            "sw_version": "0.1.0",
        }
