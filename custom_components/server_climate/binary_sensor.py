"""Проблемы интеграции server_climate."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([ProblemSensor(hass, entry)])


class ProblemSensor(BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = True

    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_problem"
        self._attr_name = "Серверная — проблема"

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self.entry.entry_id)})

    def update(self) -> None:
        """Polling: состояние обновляется автоматически."""

    @property
    def is_on(self):
        c = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {}).get("controller")
        return bool(getattr(c, "problem", None))

    @property
    def extra_state_attributes(self):
        c = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {}).get("controller")
        return {"текст": getattr(c, "problem", None)}
