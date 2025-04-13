"""Test the Laundry Checker binary sensor."""

from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

import pytest
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.laundry_checker.const import (
    DOMAIN,
    CONF_LOCATION,
    CONF_QWEATHER_KEY,
    BINARY_SENSOR_NAME,
)


async def test_binary_sensor(hass: HomeAssistant) -> None:
    """Test the creation and values of the binary sensor."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_QWEATHER_KEY: "test_api_key",
            CONF_LOCATION: "120.15,30.28",
        },
    )
    config_entry.add_to_hass(hass)

    # 模拟天气数据
    mock_weather_data = {
        datetime.now().date()
        + timedelta(days=1): [
            {
                "fxTime": "2024-03-20T12:00+08:00",
                "temp": "25",
                "humidity": "60",
                "precip": "0",
                "windScale": "3",
                "text": "晴",
                "pop": "0",
            }
        ]
    }

    with patch(
        "custom_components.laundry_checker.coordinator.LaundryCheckerDataUpdateCoordinator.get_weather_data",
        return_value=mock_weather_data,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.laundry_checker")
    assert state is not None
    assert state.name == BINARY_SENSOR_NAME
    assert state.state == STATE_ON

    # 测试属性
    attributes = state.attributes
    assert "suitable_hours" in attributes
    assert "average_humidity" in attributes
    assert "has_precipitation" in attributes
    assert "max_pop" in attributes
    assert "weather_conditions" in attributes
    assert "estimated_drying_time" in attributes
    assert "best_drying_period" in attributes


async def test_binary_sensor_unsuitable_weather(hass: HomeAssistant) -> None:
    """Test the binary sensor with unsuitable weather conditions."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_QWEATHER_KEY: "test_api_key",
            CONF_LOCATION: "120.15,30.28",
        },
    )
    config_entry.add_to_hass(hass)

    # 模拟不适合晾衣的天气数据
    mock_weather_data = {
        datetime.now().date()
        + timedelta(days=1): [
            {
                "fxTime": "2024-03-20T12:00+08:00",
                "temp": "20",
                "humidity": "90",
                "precip": "10",
                "windScale": "2",
                "text": "大雨",
                "pop": "80",
            }
        ]
    }

    with patch(
        "custom_components.laundry_checker.coordinator.LaundryCheckerDataUpdateCoordinator.get_weather_data",
        return_value=mock_weather_data,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.laundry_checker")
    assert state is not None
    assert state.state == STATE_OFF
