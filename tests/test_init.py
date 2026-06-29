"""Tests for the DHL integration setup/unload entry points."""
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from custom_components.dhl_nl import DhlData
from custom_components.dhl_nl.api import DhlAuthError
from custom_components.dhl_nl.const import (
    CONF_DELIVERED_FILTER_AMOUNT,
    CONF_DELIVERED_FILTER_TYPE,
    CONF_INCLUDE_HISTORY,
    CONF_REFRESH_INTERVAL,
    DEFAULT_REFRESH_INTERVAL,
    DOMAIN,
)

_ENTRY_DATA = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
_USER_INFO = {"userId": "abc123", "email": _ENTRY_DATA[CONF_EMAIL]}


def _add_entry(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=_ENTRY_DATA[CONF_EMAIL],
        data=_ENTRY_DATA,
        options={
            CONF_DELIVERED_FILTER_TYPE: "days",
            CONF_DELIVERED_FILTER_AMOUNT: 7,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.asyncio
async def test_setup_entry_succeeds_and_stores_runtime_data(hass):
    """A successful setup populates entry.runtime_data with a DhlData instance."""
    entry = _add_entry(hass)
    with (
        patch(
            "custom_components.dhl_nl.DhlApiClient.async_login",
            new=AsyncMock(return_value=_USER_INFO),
        ),
        patch(
            "custom_components.dhl_nl.DhlApiClient.async_get_parcels",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "custom_components.dhl_nl.DhlApiClient.async_get_sent_shipments",
            new=AsyncMock(return_value=[]),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, DhlData)
    assert entry.runtime_data.user_info == _USER_INFO


@pytest.mark.asyncio
async def test_setup_entry_retries_on_invalid_auth(hass):
    """A DhlAuthError during initial login surfaces as a setup retry."""
    entry = _add_entry(hass)
    with patch(
        "custom_components.dhl_nl.DhlApiClient.async_login",
        new=AsyncMock(side_effect=DhlAuthError(401)),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.asyncio
async def test_setup_entry_retries_on_connection_error(hass):
    """A network error during initial login surfaces as a setup retry."""
    entry = _add_entry(hass)
    with patch(
        "custom_components.dhl_nl.DhlApiClient.async_login",
        new=AsyncMock(side_effect=aiohttp.ClientError("boom")),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.asyncio
async def test_unload_entry_closes_session(hass):
    """Unloading the entry closes the per-entry aiohttp session."""
    entry = _add_entry(hass)
    with (
        patch(
            "custom_components.dhl_nl.DhlApiClient.async_login",
            new=AsyncMock(return_value=_USER_INFO),
        ),
        patch(
            "custom_components.dhl_nl.DhlApiClient.async_get_parcels",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "custom_components.dhl_nl.DhlApiClient.async_get_sent_shipments",
            new=AsyncMock(return_value=[]),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        session = entry.runtime_data.session
        assert not session.closed

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert session.closed


@pytest.mark.asyncio
async def test_options_flow_schedules_reload(hass):
    """Submitting the options form schedules a reload of the config entry."""
    entry = _add_entry(hass)
    with (
        patch(
            "custom_components.dhl_nl.DhlApiClient.async_login",
            new=AsyncMock(return_value=_USER_INFO),
        ),
        patch(
            "custom_components.dhl_nl.DhlApiClient.async_get_parcels",
            new=AsyncMock(return_value=[]),
        ) as mock_get_parcels,
        patch(
            "custom_components.dhl_nl.DhlApiClient.async_get_sent_shipments",
            new=AsyncMock(return_value=[]),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        baseline_calls = mock_get_parcels.await_count

        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "delivered": {
                    CONF_DELIVERED_FILTER_TYPE: "parcels",
                    CONF_DELIVERED_FILTER_AMOUNT: 14,
                },
                "history": {
                    CONF_INCLUDE_HISTORY: False,
                },
                "polling": {
                    CONF_REFRESH_INTERVAL: str(DEFAULT_REFRESH_INTERVAL),
                },
            },
        )
        await hass.async_block_till_done()

    assert mock_get_parcels.await_count > baseline_calls
