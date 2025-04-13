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
    ATTR_DRYING_INDEX,
    ATTR_DRYING_INDEX_LEVEL,
    ATTR_DRYING_INDEX_CATEGORY,
    ATTR_DRYING_INDEX_TEXT,
)
from .coordinator import LaundryCheckerDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the laundry checker binary sensor."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([LaundryCheckerBinarySensor(coordinator, entry)], True)


class LaundryCheckerBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a laundry checker binary sensor."""

    _attr_has_entity_name = True
    _attr_name = "Laundry Advice"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:washing-machine"

    def __init__(
        self, coordinator: LaundryCheckerDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_suitable"

    @property
    def is_on(self) -> bool:
        """Return true if conditions are suitable for laundry."""
        return self.coordinator.data["is_suitable"] if self.coordinator.data else False

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
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

        # 添加紫外线指数
        if "uv_index" in stats:
            attributes[ATTR_UV_INDEX] = stats["uv_index"]

        # 添加晾晒指数
        if "drying_index" in stats:
            attributes[ATTR_DRYING_INDEX] = stats["drying_index"]
            attributes[ATTR_DRYING_INDEX_LEVEL] = stats["drying_index_level"]
            attributes[ATTR_DRYING_INDEX_CATEGORY] = stats["drying_index_category"]
            attributes[ATTR_DRYING_INDEX_TEXT] = stats["drying_index_text"]

        # 添加风力信息
        if "wind_conditions" in stats:
            attributes[ATTR_WIND_CONDITIONS] = ", ".join(stats["wind_conditions"])

        # 添加详细消息
        if "detailed_message" in self.coordinator.data:
            attributes[ATTR_DETAILED_MESSAGE] = self.coordinator.data[
                "detailed_message"
            ]

        # 添加明天的详细信息
        if "tomorrow_detail" in self.coordinator.data:
            attributes[ATTR_TOMORROW_DETAIL] = self.coordinator.data["tomorrow_detail"]

        # 添加消息
        attributes["message"] = self.coordinator.data.get("message", "")

        return attributes

    @property
    def device_info(self) -> dict:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "洗衣检查器",
            "manufacturer": "自定义集成",
            "model": "Laundry Checker",
            "sw_version": "0.1.0",
        }
