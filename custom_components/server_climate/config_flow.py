"""UI-настройка интеграции server_climate."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_TEMP_SENSOR,
    CONF_OUTSIDE_SENSOR,
    CONF_SUPPLY,
    CONF_EXHAUST,
    CONF_AC_CLIMATE,
    CONF_AC_VIRTUAL,
    CONF_AC_CONFIRM,
    CONF_AC_SCENE_ON,
    CONF_AC_SCENE_OFF,
    CONF_AC2_CLIMATE,
    CONF_AC2_VIRTUAL,
    CONF_AC2_CONFIRM,
    CONF_AC2_SCENE_ON,
    CONF_AC2_SCENE_OFF,
    CONF_RPM_SENSOR,
    CONF_RPM_MIN,
    CONF_FAN_CHECK_DELAY,
    CONF_ALERT_HOST,
    CONF_ALERT_PORT,
    CONF_ALERT_TEMP,
    CONF_FROST_TEMP,
    CONF_FROST_ON_MIN,
    CONF_FROST_OFF_MIN,
    CONF_EFF_MIN,
    CONF_EFF_DELTA,
    CONF_PAUSE_HOURS,
    CONF_ESCALATE_MIN,
    CONF_ESCALATE_DELTA,
    CONF_SETPOINT,
    CONF_HYSTERESIS,
    CONF_MIN_TEMP,
    CONF_OUTSIDE_MAX,
    CONF_AC_ALLOW_ABOVE,
    CONF_INTERVAL,
    CONF_RETRY_MIN,
    DEFAULTS,
)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = dict(DEFAULTS)
    if defaults:
        d.update({k: v for k, v in defaults.items() if v not in (None, "")})

    def ent(domain: str, multiple: bool = False):
        return selector.EntitySelector(
            selector.EntitySelectorConfig(domain=[domain], multiple=multiple)
        )

    return vol.Schema(
        {
            vol.Required(CONF_TEMP_SENSOR, default=d.get(CONF_TEMP_SENSOR)): ent(
                "sensor"
            ),
            vol.Required(CONF_OUTSIDE_SENSOR, default=d.get(CONF_OUTSIDE_SENSOR)): ent(
                "sensor"
            ),
            vol.Required(CONF_SUPPLY, default=d.get(CONF_SUPPLY)): ent("switch"),
            vol.Required(CONF_EXHAUST, default=d.get(CONF_EXHAUST)): ent("switch"),
            # кондиционер 1
            vol.Optional(CONF_AC_CLIMATE, default=d.get(CONF_AC_CLIMATE)): ent(
                "climate"
            ),
            vol.Optional(CONF_AC_VIRTUAL, default=d.get(CONF_AC_VIRTUAL)): ent(
                "switch"
            ),
            vol.Optional(CONF_AC_CONFIRM, default=d.get(CONF_AC_CONFIRM)): ent(
                "binary_sensor"
            ),
            vol.Optional(CONF_AC_SCENE_ON, default=d.get(CONF_AC_SCENE_ON)): ent(
                "scene"
            ),
            vol.Optional(CONF_AC_SCENE_OFF, default=d.get(CONF_AC_SCENE_OFF)): ent(
                "scene"
            ),
            # кондиционер 2
            vol.Optional(CONF_AC2_CLIMATE, default=d.get(CONF_AC2_CLIMATE)): ent(
                "climate"
            ),
            vol.Optional(CONF_AC2_VIRTUAL, default=d.get(CONF_AC2_VIRTUAL)): ent(
                "switch"
            ),
            vol.Optional(CONF_AC2_CONFIRM, default=d.get(CONF_AC2_CONFIRM)): ent(
                "binary_sensor"
            ),
            vol.Optional(CONF_AC2_SCENE_ON, default=d.get(CONF_AC2_SCENE_ON)): ent(
                "scene"
            ),
            vol.Optional(CONF_AC2_SCENE_OFF, default=d.get(CONF_AC2_SCENE_OFF)): ent(
                "scene"
            ),
            # контроль запуска приточки
            vol.Optional(CONF_RPM_SENSOR, default=d.get(CONF_RPM_SENSOR)): ent("sensor"),
            vol.Optional(CONF_RPM_MIN, default=d[CONF_RPM_MIN]): vol.Coerce(float),
            vol.Optional(CONF_FAN_CHECK_DELAY, default=d[CONF_FAN_CHECK_DELAY]): vol.Coerce(int),
            # алерты на ПК (TechlanNotifier)
            vol.Optional(CONF_ALERT_HOST, default=d.get(CONF_ALERT_HOST)): str,
            vol.Optional(CONF_ALERT_PORT, default=d[CONF_ALERT_PORT]): vol.Coerce(int),
            vol.Optional(CONF_ALERT_TEMP, default=d[CONF_ALERT_TEMP]): vol.Coerce(float),
            # мороз, эффективность, пауза
            vol.Optional(CONF_FROST_TEMP, default=d[CONF_FROST_TEMP]): vol.Coerce(float),
            vol.Optional(CONF_FROST_ON_MIN, default=d[CONF_FROST_ON_MIN]): vol.Coerce(int),
            vol.Optional(CONF_FROST_OFF_MIN, default=d[CONF_FROST_OFF_MIN]): vol.Coerce(int),
            vol.Optional(CONF_EFF_MIN, default=d[CONF_EFF_MIN]): vol.Coerce(int),
            vol.Optional(CONF_EFF_DELTA, default=d[CONF_EFF_DELTA]): vol.Coerce(float),
            vol.Optional(CONF_PAUSE_HOURS, default=d[CONF_PAUSE_HOURS]): vol.Coerce(int),
            vol.Optional(CONF_ESCALATE_MIN, default=d[CONF_ESCALATE_MIN]): vol.Coerce(int),
            vol.Optional(CONF_ESCALATE_DELTA, default=d[CONF_ESCALATE_DELTA]): vol.Coerce(float),
            # пороги
            vol.Optional(CONF_SETPOINT, default=d[CONF_SETPOINT]): vol.Coerce(float),
            vol.Optional(CONF_HYSTERESIS, default=d[CONF_HYSTERESIS]): vol.Coerce(
                float
            ),
            vol.Optional(CONF_MIN_TEMP, default=d[CONF_MIN_TEMP]): vol.Coerce(float),
            vol.Optional(CONF_OUTSIDE_MAX, default=d[CONF_OUTSIDE_MAX]): vol.Coerce(
                float
            ),
            vol.Optional(
                CONF_AC_ALLOW_ABOVE, default=d[CONF_AC_ALLOW_ABOVE]
            ): vol.Coerce(float),
            vol.Optional(CONF_INTERVAL, default=d[CONF_INTERVAL]): vol.Coerce(int),
            vol.Optional(CONF_RETRY_MIN, default=d[CONF_RETRY_MIN]): vol.Coerce(int),
        }
    )


class ServerClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            title = user_input.get("name") or "Серверная — климат"
            return self.async_create_entry(title=title, data=user_input)
        schema = _schema()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional("name", default="Серверная — климат"): str,
                    **schema.schema,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ServerClimateOptionsFlow(config_entry)


class ServerClimateOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        merged = dict(self.entry.data)
        merged.update(self.entry.options or {})
        return self.async_show_form(step_id="init", data_schema=_schema(merged))
