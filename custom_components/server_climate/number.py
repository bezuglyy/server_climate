"""Пороги, редактируемые из UI."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN, CONF_SETPOINT, CONF_HYSTERESIS, CONF_MIN_TEMP,
    CONF_OUTSIDE_MAX, CONF_AC_ALLOW_ABOVE, CONF_FROST_TEMP,
    CONF_FROST_ON_MIN, CONF_FROST_OFF_MIN, CONF_EFF_MIN,
    CONF_EFF_DELTA, CONF_PAUSE_HOURS, DEFAULTS,
)

ITEMS = [
    (CONF_SETPOINT, "Уставка (включение фрикулинга)", 10, 35, 0.5, "°C"),
    (CONF_HYSTERESIS, "Гистерезис выключения", 0.5, 10, 0.5, "°C"),
    (CONF_MIN_TEMP, "Нижний предел (жёсткая защита)", 5, 25, 0.5, "°C"),
    (CONF_OUTSIDE_MAX, "Улица должна быть ниже", -30, 30, 0.5, "°C"),
    (CONF_AC_ALLOW_ABOVE, "Разрешать кондиционеры выше", 15, 40, 0.5, "°C"),
    (CONF_FROST_TEMP, "Мороз: циклы ниже", -40, 10, 1, "°C"),
    (CONF_FROST_ON_MIN, "Мороз: работать, мин", 1, 30, 1, "мин"),
    (CONF_FROST_OFF_MIN, "Мороз: пауза, мин", 1, 60, 1, "мин"),
    (CONF_EFF_MIN, "Оценка эффективности через, мин", 5, 120, 5, "мин"),
    (CONF_EFF_DELTA, "Должна упасть на", 0.1, 5, 0.1, "°C"),
    (CONF_PAUSE_HOURS, "Длительность паузы", 1, 24, 1, "ч"),
]


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([ThresholdNumber(hass, entry, *item) for item in ITEMS])


class ThresholdNumber(NumberEntity):
    _attr_should_poll = False
    _attr_mode = "box"

    def __init__(self, hass, entry, key, name, mn, mx, step, unit):
        self.hass = hass
        self.entry = entry
        self.key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = f"Серверная — {name}"
        self._attr_native_min_value = mn
        self._attr_native_max_value = mx
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = "mdi:tune"

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self.entry.entry_id)})

    @property
    def native_value(self):
        o = self.entry.options or {}
        d = self.entry.data or {}
        return o.get(self.key, d.get(self.key, DEFAULTS.get(self.key)))

    async def async_set_native_value(self, value: float):
        new = dict(self.entry.options or {})
        new[self.key] = float(value)
        self.hass.config_entries.async_update_entry(self.entry, options=new)
        self.async_write_ha_state()
