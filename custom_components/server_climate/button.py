"""Кнопки ручной паузы автоматики."""
from __future__ import annotations

from datetime import timedelta

import homeassistant.util.dt as dt_util
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_PAUSE_HOURS, DEFAULTS


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([PauseButton(hass, entry), ResumeButton(hass, entry)])


def _ctrl(hass, entry):
    return hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("controller")


class _Base(ButtonEntity):
    _attr_should_poll = False

    def __init__(self, hass, entry, uid, name, icon):
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{uid}"
        self._attr_name = name
        self._attr_icon = icon

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self.entry.entry_id)})


class PauseButton(_Base):
    def __init__(self, hass, entry):
        super().__init__(hass, entry, "pause", "Серверная — пауза (не управлять)", "mdi:pause-octagon")

    async def async_press(self) -> None:
        c = _ctrl(self.hass, self.entry)
        if not c:
            return
        hours = float(self.entry.options.get(CONF_PAUSE_HOURS)
                      or self.entry.data.get(CONF_PAUSE_HOURS, DEFAULTS[CONF_PAUSE_HOURS]))
        c._pause_until = dt_util.utcnow() + timedelta(hours=hours)
        c.reason = f"ручная пауза на {hours:.0f} ч"


class ResumeButton(_Base):
    def __init__(self, hass, entry):
        super().__init__(hass, entry, "resume", "Серверная — снять паузу", "mdi:play")

    async def async_press(self) -> None:
        c = _ctrl(self.hass, self.entry)
        if not c:
            return
        c._pause_until = None
        c.reason = "пауза снята"
