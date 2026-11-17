"""Config flow for Paprika Recipes."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from . import PaprikaConfigEntry
from .api import PaprikaApi, PaprikaApiError, PaprikaAuthError
from .const import (
    CONF_SYNC_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_SYNC_INTERVAL,
    DOMAIN,
    MAX_SYNC_INTERVAL,
    MIN_SYNC_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

CREDENTIALS = {
    vol.Required(CONF_EMAIL): str,
    vol.Required(CONF_PASSWORD): str,
}


class PaprikaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def _async_validate(self, email: str, password: str) -> str | None:
        api = PaprikaApi(async_get_clientsession(self.hass), email, password, DEFAULT_BASE_URL)
        try:
            await api.list_categories()
        except PaprikaAuthError:
            return "invalid_auth"
        except PaprikaApiError:
            return "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error validating Paprika credentials")
            return "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()
            if error := await self._async_validate(email, user_input[CONF_PASSWORD]):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=email,
                    data={CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(CREDENTIALS), user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            email = entry.data[CONF_EMAIL]
            if error := await self._async_validate(email, user_input[CONF_PASSWORD]):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: PaprikaConfigEntry) -> PaprikaOptionsFlow:
        return PaprikaOptionsFlow()


class PaprikaOptionsFlow(OptionsFlowWithReload):
    """Options: how often to sync."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SYNC_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SYNC_INTERVAL, DEFAULT_SYNC_INTERVAL
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SYNC_INTERVAL, max=MAX_SYNC_INTERVAL),
                    )
                }
            ),
        )
