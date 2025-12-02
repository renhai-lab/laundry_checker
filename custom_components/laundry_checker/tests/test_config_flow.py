"""Test the Laundry Checker config flow."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.laundry_checker.const import (
    DOMAIN,
    CONF_LOCATION,
    CONF_MAX_SUITABLE_HUMIDITY,
    CONF_MIN_SUITABLE_HOURS,
    CONF_MAX_POP,
    CONF_START_HOUR,
    CONF_END_HOUR,
    CONF_PREFERRED_END_HOUR,
    CONF_QWEATHER_KEY,
    CONF_QWEATHER_API_HOST,
    DEFAULT_LOCATION,
    DEFAULT_MAX_SUITABLE_HUMIDITY,
    DEFAULT_MIN_SUITABLE_HOURS,
    DEFAULT_MAX_POP,
    DEFAULT_START_HOUR,
    DEFAULT_END_HOUR,
    DEFAULT_PREFERRED_END_HOUR,
    DEFAULT_QWEATHER_API_HOST,
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "custom_components.laundry_checker.config_flow.validate_input",
        return_value={"title": "洗衣检查器"},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_QWEATHER_KEY: "test_api_key",
                CONF_QWEATHER_API_HOST: DEFAULT_QWEATHER_API_HOST,
                CONF_LOCATION: DEFAULT_LOCATION,
                CONF_MAX_SUITABLE_HUMIDITY: DEFAULT_MAX_SUITABLE_HUMIDITY,
                CONF_MIN_SUITABLE_HOURS: DEFAULT_MIN_SUITABLE_HOURS,
                CONF_MAX_POP: DEFAULT_MAX_POP,
                CONF_START_HOUR: DEFAULT_START_HOUR,
                CONF_END_HOUR: DEFAULT_END_HOUR,
                CONF_PREFERRED_END_HOUR: DEFAULT_PREFERRED_END_HOUR,
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "洗衣检查器"
    assert result2["data"] == {
        CONF_QWEATHER_KEY: "test_api_key",
        CONF_QWEATHER_API_HOST: DEFAULT_QWEATHER_API_HOST,
        CONF_LOCATION: DEFAULT_LOCATION,
        CONF_MAX_SUITABLE_HUMIDITY: DEFAULT_MAX_SUITABLE_HUMIDITY,
        CONF_MIN_SUITABLE_HOURS: DEFAULT_MIN_SUITABLE_HOURS,
        CONF_MAX_POP: DEFAULT_MAX_POP,
        CONF_START_HOUR: DEFAULT_START_HOUR,
        CONF_END_HOUR: DEFAULT_END_HOUR,
        CONF_PREFERRED_END_HOUR: DEFAULT_PREFERRED_END_HOUR,
    }


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.laundry_checker.config_flow.validate_input",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_QWEATHER_KEY: "invalid_api_key",
                CONF_QWEATHER_API_HOST: DEFAULT_QWEATHER_API_HOST,
                CONF_LOCATION: DEFAULT_LOCATION,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
