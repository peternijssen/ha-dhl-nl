"""Config flow for the DHL Package Tracker integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DhlApiClient, DhlAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class DhlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI-driven configuration flow for the DHL integration."""

    VERSION = 1

    async def _validate_credentials(self, email: str, password: str) -> None:
        """Validate credentials against the live DHL API using the HA-managed session."""
        session = async_get_clientsession(self.hass)
        client = DhlApiClient(email, password, session)
        await client.async_login()

    # ------------------------------------------------------------------
    # Initial setup step
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the credential form and validate on submit."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            try:
                await self._validate_credentials(email, password)
            except DhlAuthError:
                errors["base"] = "invalid_auth"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(email)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=email,
                    data={CONF_EMAIL: email, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_USER_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Re-authentication steps
    # ------------------------------------------------------------------

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Initiate re-authentication for an existing config entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the re-auth credential form and update the existing entry on success."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            try:
                await self._validate_credentials(email, password)
            except DhlAuthError:
                errors["base"] = "invalid_auth"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            else:
                try:
                    reauth_entry = self._get_reauth_entry()
                except AttributeError:
                    entry_id = self.context.get("entry_id")
                    reauth_entry = self.hass.config_entries.async_get_entry(entry_id)

                if reauth_entry is not None:
                    self.hass.config_entries.async_update_entry(
                        reauth_entry,
                        data={CONF_EMAIL: email, CONF_PASSWORD: password},
                    )

                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_USER_SCHEMA,
            errors=errors,
        )
