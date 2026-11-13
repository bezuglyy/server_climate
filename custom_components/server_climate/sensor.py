"""Диагностические сенсоры интеграции."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    async_add_entities([StatusSensor(hass, entry), ReasonSensor(hass, entry)])


def _ctrl(hass, entry):
    return hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("controller")


class _Base(SensorEntity):
    _attr_should_poll = True

    def __init__(self, hass, entry, uid, name):
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{uid}"
        self._attr_name = name

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.entry.entry_id)})

    def update(self) -> None:
        """Polling: HA сам обновит состояние раз в 30 с."""


class StatusSensor(_Base):
    _attr_icon = "mdi:hvac"

    def __init__(self, hass, entry):
        super().__init__(hass, entry, "status", "Серверная — статус")
        self._attr_options = ["фрикулинг", "кондиционеры", "защита", "ожидание", "нет данных"]

    @property
    def state(self):
        c = _ctrl(self.hass, self.entry)
        if not c:
            return "нет данных"
        r = (c.reason or "").lower()
        if "фрикулинг" in r:
            return "фрикулинг"
        if "жарко" in r or "кондиционер" in r:
            return "кондиционеры"
        if "защита" in r:
            return "защита"
        return "ожидание"

    @property
    def extra_state_attributes(self):
        c = _ctrl(self.hass, self.entry)
        return {"причина": getattr(c, "reason", None), "проблема": getattr(c, "problem", None)}


class ReasonSensor(_Base):
    _attr_icon = "mdi:text-box-outline"

    def __init__(self, hass, entry):
        super().__init__(hass, entry, "reason", "Серверная — причина")

    @property
    def state(self):
        c = _ctrl(self.hass, self.entry)
        return getattr(c, "reason", "—")
