"""server_climate — управление вентиляцией и кондиционерами серверной.

Логика (по требованиям владельца):
  1) Фрикулинг: включать вентиляцию, только если на улице < outside_max.
  2) Включать при T >= setpoint; выключать при T <= setpoint - hysteresis.
  3) Жёсткая защита: при T <= min_temp вентиляция выключается всегда.
  4) Пока вентиляция работает — кондиционеры выключены (hvac_mode: off).
  5) Если T > ac_allow_above — разрешаем кондиционерам работать (cool), вентиляция не справляется.
     Когда T снова <= setpoint - hysteresis — возвращаем кондиционеры в cool.
  6) Команды подтверждаются датчиком (вход УВ): если состояние не совпало — повтор раз в retry_min.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers import device_registry as dr

from .const import (
    RETRY_SECONDS,
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
    CONF_SINGLE_AC,
    FAN_GRACE_SECONDS,
    CONF_SETPOINT,
    CONF_HYSTERESIS,
    CONF_MIN_TEMP,
    CONF_OUTSIDE_MAX,
    CONF_AC_ALLOW_ABOVE,
    CONF_INTERVAL,
    CONF_RETRY_MIN,
    DEFAULTS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "switch", "number", "button"]


def cfg(entry: ConfigEntry, key: str) -> Any:
    """Значение из options -> data -> default."""
    if key in (entry.options or {}) and entry.options.get(key) not in (None, ""):
        return entry.options[key]
    if key in (entry.data or {}) and entry.data.get(key) not in (None, ""):
        return entry.data[key]
    return DEFAULTS.get(key)


def _float(hass: HomeAssistant, entity_id: str | None) -> float | None:
    if not entity_id:
        return None
    st = hass.states.get(entity_id)
    if not st:
        return None
    try:
        return float(st.state)
    except (ValueError, TypeError):
        return None


class ServerClimateController:
    """Движок: считает, что должно быть включено, и приводит к этому."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.reason: str = "запуск"
        self.problem: str | None = None
        self._last_repeat: dict[str, Any] = {}
        self._unsub = None
        self._vent_turned_on_at = None
        self._fan_ok: bool | None = None
        self._fan_best: float | None = None
        self._fan_next = None
        self._lead = 0                 # индекс ведущего кондиционера
        self._lead_fails = 0
        self._last_alert: dict[str, Any] = {}
        self._pause_until = None
        self._frost_cycle_start = None
        self._vent_since = None
        self._vent_start_temp = None
        self._vent_ineffective = False

    # ---------- получение настроек ----------
    def _get(self, key: str) -> Any:
        return cfg(self.entry, key)

    def _acs(self) -> list[dict[str, Any]]:
        """Список кондиционеров (1 или 2), у которых задан climate."""
        out = []
        ac1 = self._get(CONF_AC_CLIMATE)
        if ac1:
            out.append(
                {
                    "climate": ac1,
                    "virtual": self._get(CONF_AC_VIRTUAL),
                    "confirm": self._get(CONF_AC_CONFIRM),
                    "scene_on": self._get(CONF_AC_SCENE_ON),
                    "scene_off": self._get(CONF_AC_SCENE_OFF),
                }
            )
        ac2 = self._get(CONF_AC2_CLIMATE)
        if ac2:
            out.append(
                {
                    "climate": ac2,
                    "virtual": self._get(CONF_AC2_VIRTUAL),
                    "confirm": self._get(CONF_AC2_CONFIRM),
                    "scene_on": self._get(CONF_AC2_SCENE_ON),
                    "scene_off": self._get(CONF_AC2_SCENE_OFF),
                }
            )
        return out

    # ---------- работа ----------
    async def async_start(self) -> None:
        interval = int(self._get(CONF_INTERVAL) or 30)
        self._unsub = async_track_time_interval(
            self.hass, self._tick, timedelta(seconds=interval)
        )
        await self.async_evaluate()

    @callback
    def _tick(self, _now) -> None:
        self.hass.async_create_task(self.async_evaluate())

    def stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    async def async_evaluate(self) -> None:
        hass = self.hass
        if not hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {}).get("enabled", True):
            self.reason = "автоматика выключена"
            self.problem = None
            hass.bus.async_fire(f"{DOMAIN}_update", {"entry_id": self.entry.entry_id})
            return
        import homeassistant.util.dt as _dt
        if self._pause_until is not None:
            if _dt.utcnow() < self._pause_until:
                self.reason = f"ручная пауза до {self._pause_until.astimezone().strftime('%H:%M')}"
                self.problem = None
                hass.bus.async_fire(f"{DOMAIN}_update", {"entry_id": self.entry.entry_id})
                return
            self._pause_until = None

        t = _float(hass, self._get(CONF_TEMP_SENSOR))
        t_out = _float(hass, self._get(CONF_OUTSIDE_SENSOR))

        setpoint = float(self._get(CONF_SETPOINT))
        hyst = float(self._get(CONF_HYSTERESIS))
        min_temp = float(self._get(CONF_MIN_TEMP))
        out_max = float(self._get(CONF_OUTSIDE_MAX))
        ac_above = float(self._get(CONF_AC_ALLOW_ABOVE))

        supply = self._get(CONF_SUPPLY)
        exhaust = self._get(CONF_EXHAUST)

        self.problem = None
        if t is None:
            self.problem = "датчик температуры помещения недоступен"
            self.reason = "нет данных"
            return
        if t_out is None:
            self.problem = "датчик улицы недоступен"
            self.reason = "нет данных по улице"
            return

        running = self._is_on(supply) or self._is_on(exhaust)
        cold_outside = t_out < out_max

        # защита от обмерзания: при сильном морозе работаем циклами
        frost_temp = float(self._get(CONF_FROST_TEMP) or -99)
        frost_mode = t_out < frost_temp
        if frost_mode:
            on_min = float(self._get(CONF_FROST_ON_MIN) or 5)
            off_min = float(self._get(CONF_FROST_OFF_MIN) or 10)
            now_f = _dt.utcnow()
            if self._frost_cycle_start is None:
                self._frost_cycle_start = now_f
            elapsed = (now_f - self._frost_cycle_start).total_seconds() / 60.0
            if running and elapsed >= on_min:
                await self._set_vent(False, f"мороз {t_out:.0f} °C: пауза {off_min:.0f} мин")
                self._frost_cycle_start = now_f
                return
            if (not running) and elapsed < off_min:
                self.reason = f"мороз {t_out:.0f} °C: пауза ({elapsed:.0f}/{off_min:.0f} мин)"
                hass.bus.async_fire(f"{DOMAIN}_update", {"entry_id": self.entry.entry_id})
                return
            if (not running) and elapsed >= off_min:
                self._frost_cycle_start = now_f
        else:
            self._frost_cycle_start = None

        # --- 1. вентиляция ---
        if t <= min_temp:
            if running:
                await self._set_vent(False, f"защита: T {t:.1f} ≤ {min_temp:.0f}")
            else:
                self.reason = f"защита: T {t:.1f} ≤ {min_temp:.0f}"
        elif not cold_outside:
            if running:
                await self._set_vent(
                    False, f"улица {t_out:.1f} ≥ {out_max:.0f} — нет смысла"
                )
            else:
                self.reason = f"ожидание: улица {t_out:.1f} ≥ {out_max:.0f}"
        elif not running:
            if t >= setpoint:
                await self._set_vent(
                    True, f"фрикулинг: T {t:.1f} ≥ {setpoint:.1f}, улица {t_out:.1f}"
                )
            else:
                self.reason = f"ожидание: T {t:.1f} < {setpoint:.1f}"
        else:
            if t <= setpoint - hyst:
                await self._set_vent(
                    False, f"остыло: T {t:.1f} ≤ {setpoint - hyst:.1f}"
                )
            else:
                self.reason = f"фрикулинг работает: T {t:.1f}"

        # --- 1a. контроль фактического запуска приточки (по тахометру) ---
        import homeassistant.util.dt as dt_util
        now = dt_util.utcnow()
        vent_running = self._is_on(supply) or self._is_on(exhaust)
        rpm_entity = self._get(CONF_RPM_SENSOR)
        rpm_min = float(self._get(CONF_RPM_MIN) or 0)
        check_delay = int(self._get(CONF_FAN_CHECK_DELAY) or 20)

        if vent_running and rpm_entity:
            if self._vent_turned_on_at is None:
                self._vent_turned_on_at = now
                self._fan_ok = None
                self._fan_best = None
                self._fan_next = None
            rpm = _float(hass, rpm_entity)
            if rpm is not None:
                self._fan_best = rpm if self._fan_best is None else max(self._fan_best, rpm)
            elapsed = (now - self._vent_turned_on_at).total_seconds()
            # вентилятор раскручивается не мгновенно: сначала ждём check_delay,
            # затем ещё FAN_GRACE секунд перепроверяем и берём лучший результат
            deadline = check_delay + FAN_GRACE_SECONDS
            if self._fan_ok is not True and elapsed >= check_delay:
                if self._fan_next is None or (now - self._fan_next).total_seconds() >= 10:
                    self._fan_next = now
                    best = float(self._fan_best or 0)
                    if best >= rpm_min:
                        self._fan_ok = True
                        self.problem = None
                    elif elapsed >= deadline:
                        self._fan_ok = False
                        self.problem = (
                            f"приточка не запустилась: обороты {best:.0f} < {rpm_min:.0f}"
                        )
                        await self._alert(
                            "Серверная: приточка не запустилась", self.problem
                        )
        else:
            self._vent_turned_on_at = None
            self._fan_ok = None
            self._fan_best = None
            self._fan_next = None

        # если приточка не крутится — вентиляцию «не считаем» рабочей (кондиционеры не блокируем)
        if self._fan_ok is False:
            vent_running = False

        # контроль эффективности фрикулинга
        eff_min = float(self._get(CONF_EFF_MIN) or 0)
        eff_delta = float(self._get(CONF_EFF_DELTA) or 0)
        if vent_running:
            if self._vent_since is None:
                self._vent_since = now
                self._vent_start_temp = t
                self._vent_ineffective = False
            elif (eff_min and not self._vent_ineffective and self._vent_start_temp is not None
                  and (now - self._vent_since).total_seconds() >= eff_min * 60):
                if (self._vent_start_temp - t) < eff_delta:
                    self._vent_ineffective = True
                    self.problem = f"фрикулинг неэффективен: за {eff_min:.0f} мин T не упала на {eff_delta:.1f} °C"
                    await self._alert("Серверная: фрикулинг неэффективен", self.problem)
        else:
            self._vent_since = None
            self._vent_start_temp = None
            self._vent_ineffective = False

        # если фрикулинг неэффективен — кондиционеры не блокируем
        if self._vent_ineffective:
            vent_running = False

        # --- 2. кондиционеры ---
        acs = self._acs()
        single_ac = bool(self._get(CONF_SINGLE_AC))
        if single_ac and len(acs) > 1:
            # ведущий/резервный: если ведущий не подтвердил включение 2 раза — переключаемся
            needs_cool = t > ac_above
            if needs_cool and self._lead_fails >= 2:
                self._lead = 1 - self._lead
                self._lead_fails = 0
                self.reason = "переключение на резервный кондиционер"
            # оба — только при сильной жаре
            both = t > (ac_above + 2)
            order = acs if both else [acs[self._lead]]
            for ac in order:
                await self._handle_ac(ac, t, vent_running, ac_above, setpoint, hyst)
            # неработающему — выключаем (если не оба)
            if not both:
                for ac in acs:
                    if ac not in order:
                        st = self.hass.states.get(ac["climate"])
                        if st and st.state != "off":
                            await self._call("climate", "set_hvac_mode", {"entity_id": ac["climate"], "hvac_mode": "off"})
        else:
            for ac in acs:
                await self._handle_ac(ac, t, vent_running, ac_above, setpoint, hyst)

        alert_temp = float(self._get(CONF_ALERT_TEMP) or 0)
        if alert_temp and t is not None and t > alert_temp:
            await self._alert("Серверная: перегрев", f"Температура {t:.1f} °C > {alert_temp:.0f} °C")

        hass.bus.async_fire(f"{DOMAIN}_update", {"entry_id": self.entry.entry_id})

    async def _handle_ac(
        self,
        ac: dict[str, Any],
        t: float,
        vent_running: bool,
        ac_above: float,
        setpoint: float,
        hyst: float,
    ) -> None:
        climate = ac["climate"]
        st = self.hass.states.get(climate)
        if st is None:
            return

        # Жарко — вентиляция не справляется: разрешаем кондиционер
        if t > ac_above:
            if st.state != "cool":
                await self._call(
                    "climate",
                    "set_hvac_mode",
                    {"entity_id": climate, "hvac_mode": "cool"},
                )
            await self._confirm_ac(ac, want_on=True)
            self.reason = f"жарко {t:.1f} > {ac_above:.0f}: кондиционеры разрешены"
            return

        # Вентиляция работает и не жарко — кондиционеры выключаем
        if vent_running:
            if st.state != "off":
                await self._call(
                    "climate",
                    "set_hvac_mode",
                    {"entity_id": climate, "hvac_mode": "off"},
                )
            await self._confirm_ac(ac, want_on=False)
            return

        # Вентиляция не работает — обычный режим: кондиционер живёт по своему
        # термостату (виртуальный переключатель -> сцена -> ИК). Не вмешиваемся,
        # но сверяем факт: если термостат просит "вкл", а аппарат стоит — повторяем сцену.
        if st.state != "cool":
            await self._call(
                "climate", "set_hvac_mode", {"entity_id": climate, "hvac_mode": "cool"}
            )
        virtual = ac.get("virtual")
        want = self._is_on(virtual) if virtual else True
        await self._confirm_ac(ac, want_on=want)

    async def _confirm_ac(self, ac: dict[str, Any], want_on: bool) -> None:
        """Проверяет подтверждение (вход УВ) и повторяет команду, если разошлось."""
        confirm = ac.get("confirm")
        if not confirm:
            return
        st = self.hass.states.get(confirm)
        if st is None:
            return
        actual = st.state == "on"
        if actual == want_on:
            self._last_repeat[confirm] = None
            if want_on:
                self._lead_fails = 0
            return

        # расхождение показываем сразу, не дожидаясь окна повтора
        self.problem = f"команда не подтверждена: {confirm}"

        import homeassistant.util.dt as dt_util

        # повтор команды не чаще раза в RETRY_SECONDS (60 с)
        now = dt_util.utcnow()
        last = self._last_repeat.get(confirm)
        if last and (now - last) < timedelta(seconds=RETRY_SECONDS):
            return
        self._last_repeat[confirm] = now

        scene = ac.get("scene_on") if want_on else ac.get("scene_off")
        virtual = ac.get("virtual")
        if virtual:
            await self._call(
                "switch", "turn_on" if want_on else "turn_off", {"entity_id": virtual}
            )
        if scene:
            await self._call("scene", "turn_on", {"entity_id": scene})
        if want_on:
            self._lead_fails += 1

    async def _set_vent(self, on: bool, reason: str) -> None:
        supply = self._get(CONF_SUPPLY)
        exhaust = self._get(CONF_EXHAUST)
        if on:
            if exhaust:
                await self._call("switch", "turn_on", {"entity_id": exhaust})
                await asyncio.sleep(1)
            if supply:
                await self._call("switch", "turn_on", {"entity_id": supply})
        else:
            if supply:
                await self._call("switch", "turn_off", {"entity_id": supply})
                await asyncio.sleep(0.3)
            if exhaust:
                await self._call("switch", "turn_off", {"entity_id": exhaust})
        self.reason = reason

    def _is_on(self, entity_id: str | None) -> bool:
        if not entity_id:
            return False
        st = self.hass.states.get(entity_id)
        return bool(st and st.state == "on")

    async def _alert(self, title: str, text: str) -> None:
        """Окно на ПК через TechlanNotifier (без спама: не чаще раза в 10 минут)."""
        host = str(self._get(CONF_ALERT_HOST) or "").strip()
        if not host:
            return
        port = int(self._get(CONF_ALERT_PORT) or 9171)
        import homeassistant.util.dt as dt_util
        now = dt_util.utcnow()
        last = self._last_alert.get(title)
        if last and (now - last).total_seconds() < 600:
            return
        self._last_alert[title] = now
        url = f"http://{host}:{port}/notify"
        try:
            from homeassistant.helpers.aiohttp_client import async_get_clientsession
            session = async_get_clientsession(self.hass)
            async with session.get(url, params={"title": title, "text": text, "sec": 30}, timeout=8) as resp:
                if resp.status != 200:
                    _LOGGER.warning("alert %s: HTTP %s", url, resp.status)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("alert %s: %s", url, err)

    async def _call(self, domain: str, service: str, data: dict[str, Any]) -> None:
        try:
            await self.hass.services.async_call(domain, service, data, blocking=False)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("%s.%s %s: %s", domain, service, data, err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    controller = ServerClimateController(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = {"controller": controller}

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title or "Серверная — климат",
        manufacturer="bezuglyy",
        model="Server Climate",
    )

    await controller.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    c = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("controller")
    if c:
        c.stop()
        c.entry = entry
        await c.async_start()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    c = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("controller")
    if c:
        c.stop()
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return ok
