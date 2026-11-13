"""Главный выключатель автоматики."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([AutoSwitch(hass, entry)])


class AutoSwitch(SwitchEntity):
    _attr_should_poll = False
    _attr_icon = "mdi:robot"

    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_auto"
        self._attr_name = "Серверная — автоматика"

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self.entry.entry_id)})

    @property
    def is_on(self):
        return self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {}).get("enabled", True)

    async def async_turn_on(self, **kwargs):
        self.hass.data[DOMAIN][self.entry.entry_id]["enabled"] = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self.hass.data[DOMAIN][self.entry.entry_id]["enabled"] = False
        self.async_write_ha_state()
