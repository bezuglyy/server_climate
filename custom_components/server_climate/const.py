"""Константы интеграции server_climate."""

DOMAIN = "server_climate"

# --- сенсоры ---
CONF_TEMP_SENSOR = "temp_sensor"          # температура помещения
CONF_OUTSIDE_SENSOR = "outside_sensor"    # температура улицы

# --- вентиляция ---
CONF_SUPPLY = "supply_switch"             # приток
CONF_EXHAUST = "exhaust_switch"           # вытяжка

# --- кондиционеры (до 2) ---
CONF_AC_CLIMATE = "ac_climate"            # climate-сущность
CONF_AC_VIRTUAL = "ac_virtual"            # virtual switch (ESP)
CONF_AC_CONFIRM = "ac_confirm"            # binary_sensor подтверждения (вход УВ)
CONF_AC_SCENE_ON = "ac_scene_on"          # сцена включения
CONF_AC_SCENE_OFF = "ac_scene_off"        # сцена выключения

# --- второй кондиционер ---
CONF_AC2_CLIMATE = "ac2_climate"
CONF_AC2_VIRTUAL = "ac2_virtual"
CONF_AC2_CONFIRM = "ac2_confirm"
CONF_AC2_SCENE_ON = "ac2_scene_on"
CONF_AC2_SCENE_OFF = "ac2_scene_off"

# --- контроль запуска приточки ---
CONF_RPM_SENSOR = "rpm_sensor"            # тахометр вентилятора
CONF_RPM_MIN = "rpm_min"                  # минимальные обороты "работает"
CONF_FAN_CHECK_DELAY = "fan_check_delay"  # через сколько секунд проверять

# --- алерты ---
CONF_ALERT_HOST = "alert_host"            # IP/host TechlanNotifier (ARMC)
CONF_ALERT_PORT = "alert_port"
CONF_ALERT_TEMP = "alert_temp"            # порог тревоги по температуре

# --- защита от сильного мороза (циклы) ---
CONF_FROST_TEMP = "frost_temp"            # ниже этой уличной — работаем циклами
CONF_FROST_ON_MIN = "frost_on_min"        # минут работы
CONF_FROST_OFF_MIN = "frost_off_min"      # минут паузы

# --- контроль эффективности фрикулинга ---
CONF_EFF_MIN = "eff_min"                  # через сколько минут оценивать
CONF_EFF_DELTA = "eff_delta"              # насколько должна упасть T

# --- ручная пауза ---
CONF_PAUSE_HOURS = "pause_hours"          # длительность паузы по умолчанию

# --- ротация кондиционеров (один за раз) ---
CONF_SINGLE_AC = "single_ac"              # true = работает один, второй резерв

# --- пороги ---
CONF_SETPOINT = "setpoint"                # уставка, °C
CONF_HYSTERESIS = "hysteresis"            # гистерезис, °C
CONF_MIN_TEMP = "min_temp"                # нижняя защита, °C
CONF_OUTSIDE_MAX = "outside_max"          # улица должна быть ниже, °C
CONF_AC_ALLOW_ABOVE = "ac_allow_above"    # разрешить кондиционеры выше, °C
CONF_INTERVAL = "interval"                # период проверки, сек
CONF_RETRY_MIN = "retry_min"              # повтор команды, мин

DEFAULTS = {
    CONF_SETPOINT: 22.0,
    CONF_HYSTERESIS: 1.0,
    CONF_MIN_TEMP: 15.0,
    CONF_OUTSIDE_MAX: 10.0,
    CONF_AC_ALLOW_ABOVE: 24.0,
    CONF_INTERVAL: 30,
    CONF_RETRY_MIN: 1,
    CONF_RPM_MIN: 300.0,
    CONF_FAN_CHECK_DELAY: 20,
    CONF_ALERT_HOST: "",
    CONF_ALERT_PORT: 9171,
    CONF_ALERT_TEMP: 30.0,
    CONF_FROST_TEMP: -20.0,
    CONF_FROST_ON_MIN: 5,
    CONF_FROST_OFF_MIN: 10,
    CONF_EFF_MIN: 20,
    CONF_EFF_DELTA: 0.5,
    CONF_PAUSE_HOURS: 2,
    CONF_SINGLE_AC: False,
}

# повтор команды кондиционеру, секунды
RETRY_SECONDS = 60
