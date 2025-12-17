"""Error handling tests for LaundryCheckerDataUpdateCoordinator."""

from unittest.mock import MagicMock, patch

import pytest
import requests
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.laundry_checker.coordinator import (
    LaundryCheckerDataUpdateCoordinator,
)


async def test_get_weather_network_error(hass):
    """Network errors should raise UpdateFailed (not trigger reauth)."""
    coordinator = LaundryCheckerDataUpdateCoordinator(
        hass=hass,
        location="120.15,30.28",
        qweather_key="test-key",
    )

    with patch(
        "custom_components.laundry_checker.coordinator.requests.get",
        side_effect=requests.exceptions.ConnectionError("boom"),
    ):
        with pytest.raises(UpdateFailed):
            coordinator.get_weather_data()


async def test_get_weather_auth_error(hass):
    """QWeather code 401 should raise ConfigEntryAuthFailed."""

    def _fake_response(code: str):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"code": code, "message": "error"}
        return response

    coordinator = LaundryCheckerDataUpdateCoordinator(
        hass=hass,
        location="120.15,30.28",
        qweather_key="test-key",
    )

    with patch(
        "custom_components.laundry_checker.coordinator.requests.get",
        side_effect=[_fake_response("401")],
    ):
        with pytest.raises(ConfigEntryAuthFailed):
            coordinator.get_weather_data()
