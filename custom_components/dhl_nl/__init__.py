"""DHL Package Tracker custom component for Home Assistant."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DhlApiClient, DhlAuthError
from .const import PLATFORMS
from .coordinator import DhlCoordinator, DhlSentShipmentsCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class DhlData:
    """Runtime data attached to a DHL config entry."""

    client: DhlApiClient
    coordinator: DhlCoordinator
    sent_coordinator: DhlSentShipmentsCoordinator
    user_info: dict[str, Any]
    session: aiohttp.ClientSession


type DhlConfigEntry = ConfigEntry[DhlData]


async def async_setup_entry(hass: HomeAssistant, entry: DhlConfigEntry) -> bool:
    """Set up DHL from a config entry."""
    # Each config entry needs its own cookie jar so multiple DHL accounts
    # don't overwrite each other's auth cookies in the shared session.
    session = aiohttp.ClientSession(
        connector=async_get_clientsession(hass).connector,
        connector_owner=False,
        cookie_jar=aiohttp.CookieJar(),
    )
    client = DhlApiClient(
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        session,
    )

    try:
        user_info = await client.async_login()
    except DhlAuthError as exc:
        _LOGGER.error("DHL authentication failed during setup: %s", exc)
        raise ConfigEntryNotReady("DHL login failed") from exc
    except aiohttp.ClientError as exc:
        raise ConfigEntryNotReady("DHL login failed") from exc

    coordinator = DhlCoordinator(hass, client, entry)
    sent_coordinator = DhlSentShipmentsCoordinator(hass, client)

    entry.runtime_data = DhlData(
        client=client,
        coordinator=coordinator,
        sent_coordinator=sent_coordinator,
        user_info=user_info,
        session=session,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    return True


async def _async_update_options(hass: HomeAssistant, entry: DhlConfigEntry) -> None:
    """Refresh the coordinator immediately when options are changed."""
    await entry.runtime_data.coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: DhlConfigEntry) -> bool:
    """Unload a DHL config entry."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.session.close()
        return True
    return False
