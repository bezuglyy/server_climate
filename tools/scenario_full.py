#!/usr/bin/env python3
"""Полный прогон server_climate в ЛЮБЫХ условиях.

Температуры подменяются управляемыми состояниями sensor.tst_inside / sensor.tst_outside,
которые временно прописываются в настройки интеграции (в конце возвращаются реальные).
"""

import json
import ssl
import sys
import time
import urllib.request
import urllib.error

BASE = "https://192.168.103.200:38123"
TOK = open("/opt/opencode/mcp/ha-mcp.token").read().strip()
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

ENTRY = "01M796A2SR2XK63WJYC2YYE7FW"
REAL_IN = "sensor.sts_severnaia_servernaia_shchkaf_ops_temperatura"
REAL_OUT = "sensor.servernaia_uv_temperatura_ulitsy"
FAKE_IN = "sensor.tst_inside"
FAKE_OUT = "sensor.tst_outside"

N = {
    "setpoint": "number.servernaia_klimat_servernaia_ustavka_vkliuchenie_frikulinga",
    "hyst": "number.servernaia_klimat_servernaia_gisterezis_vykliucheniia",
    "mintemp": "number.servernaia_klimat_servernaia_nizhnii_predel_zhestkaia_zashchita",
    "outside": "number.servernaia_klimat_servernaia_ulitsa_dolzhna_byt_nizhe",
    "allow": "number.servernaia_klimat_servernaia_razreshat_konditsionery_vyshe",
    "frost_t": "number.servernaia_klimat_servernaia_moroz_tsikly_nizhe",
    "frost_on": "number.servernaia_klimat_servernaia_moroz_rabotat_min",
    "frost_off": "number.servernaia_klimat_servernaia_moroz_pauza_min",
    "eff_min": "number.servernaia_klimat_servernaia_otsenka_effektivnosti_cherez_min",
    "eff_delta": "number.servernaia_klimat_servernaia_dolzhna_upast_na",
}
E = {
    "why": "sensor.servernaia_klimat_servernaia_prichina",
    "status": "sensor.servernaia_klimat_servernaia_status",
    "problem": "binary_sensor.servernaia_klimat_servernaia_problema",
    "sup": "switch.servernaia_uv_pritochnyi_ventiliator_sup",
    "exh": "switch.servernaia_uv_vytiazhnoi_ventiliator_exh",
    "rpm": "sensor.servernaia_uv_skorost_vrashcheniia_ventiliatora",
    "aux_v": "switch.smart_control2_aux2_virtual",
    "oas_v": "switch.smart_control2_oasis2_virtual",
    "aux_c": "binary_sensor.servernaia_uv_konditsioner_aux",
    "oas_c": "binary_sensor.servernaia_uv_konditsioner_oasis",
    "pause": "button.servernaia_klimat_servernaia_pauza_ne_upravliat",
    "unpause": "button.servernaia_klimat_servernaia_sniat_pauzu",
    "uptime": "sensor.servernaia_uv_aptaim_sek",
}
CANON = {
    "setpoint": 22.0,
    "hyst": 1.0,
    "mintemp": 15.0,
    "outside": 10.0,
    "allow": 24.0,
    "frost_t": -20.0,
    "frost_on": 5.0,
    "frost_off": 10.0,
    "eff_min": 20.0,
    "eff_delta": 0.5,
}

RESULTS = []
T0 = time.time()
_states = {}


def log(m):
    print("[%6.1fs] %s" % (time.time() - T0, m), flush=True)


def req(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Authorization": "Bearer " + TOK, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(r, context=CTX, timeout=30) as resp:
            b = resp.read().decode()
            return json.loads(b) if b.strip() else None
    except urllib.error.HTTPError as e:
        log("  !! %s %s -> %s %s" % (method, path, e.code, e.read().decode()[:120]))
        raise


def refresh():
    global _states
    _states = {s["entity_id"]: s for s in req("GET", "/api/states")}


def st(key):
    s = _states.get(E.get(key, key))
    if not s:
        return None
    return s["state"] == "on" if key == "problem" else s["state"]


def num(key):
    try:
        return float(st(key))
    except (TypeError, ValueError):
        return None


def set_t(in_t=None, out_t=None):
    if in_t is not None:
        req(
            "POST",
            "/api/states/" + FAKE_IN,
            {"state": str(in_t), "attributes": {"unit_of_measurement": "°C"}},
        )
    if out_t is not None:
        req(
            "POST",
            "/api/states/" + FAKE_OUT,
            {"state": str(out_t), "attributes": {"unit_of_measurement": "°C"}},
        )
    refresh()


def setn(key, v):
    req(
        "POST",
        "/api/services/number/set_value",
        {"entity_id": N[key], "value": float(v)},
    )


def vent_on():
    return st("sup") == "on" or st("exh") == "on"


def press(key):
    req("POST", "/api/services/button/press", {"entity_id": E[key]})


def wait_for(pred, timeout, step=3):
    end = time.time() + timeout
    while time.time() < end:
        refresh()
        if pred():
            return True
        time.sleep(step)
    refresh()
    return pred()


def ptext():
    s_ = _states.get(E["problem"], {})
    return (s_.get("attributes") or {}).get("текст")


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    log(
        "%s  %s%s"
        % ("PASS" if ok else "FAIL", name, (" — " + detail) if detail else "")
    )


def snap():
    return (
        "Tвн=%s Tул=%s rpm=%s SUP=%s EXH=%s AUX=%s/%s OAS=%s/%s | %s | проблема=%s"
        % (
            st(FAKE_IN),
            st(FAKE_OUT),
            st("rpm"),
            st("sup"),
            st("exh"),
            st("aux_v"),
            st("aux_c"),
            st("oas_v"),
            st("oas_c"),
            st("why"),
            st("problem"),
        )
    )


def apply_options(overrides):
    flow = req("POST", "/api/config/config_entries/options/flow", {"handler": ENTRY})
    fid = flow["flow_id"]
    vals = {f["name"]: f["default"] for f in flow["data_schema"] if "default" in f}
    vals.update(overrides)
    res = req("POST", "/api/config/config_entries/options/flow/" + fid, vals)
    log("  options -> %s" % res.get("type"))
    time.sleep(12)


# ------------------------------------------------------------------ старт
log("=== подготовка: управляемые датчики ===")
try:
    apply_options({"temp_sensor": FAKE_IN, "outside_sensor": FAKE_OUT})
    set_t(22.0, 21.0)
    for k, v in CANON.items():
        setn(k, v)
    time.sleep(6)
    wait_for(lambda: "ожидание" in str(st("why")) or "жарко" not in str(st("why")), 90)
    refresh()
    log("состояние: " + snap())
    up_start = num("uptime")

    # ---- S1 ожидание
    log("\n=== S1: тепло на улице (21 °C) -> ждём ===")
    check(
        "S1 ожидание",
        wait_for(lambda: not vent_on(), 45) and "ожидание" in str(st("why")),
        str(st("why")),
    )

    # ---- S2 фрикулинг включается
    log("\n=== S2: улица 9 °C, в доме 23 °C -> фрикулинг ВКЛ ===")
    set_t(23.0, 9.0)
    ok = wait_for(vent_on, 60)
    time.sleep(40)
    refresh()
    check("S2 вентиляция включилась", ok, snap())
    check("S2 причина «фрикулинг»", "фрикулинг" in str(st("why")), str(st("why")))
    rpm = num("rpm")
    check("S2 тахометр подтвердил (≥300 rpm)", (rpm or 0) >= 300, "rpm=%s" % rpm)
    check("S2 нет проблемы по приточке", "приточка не запустилась" not in str(ptext()),
          "проблема=%s (%s)" % (st("problem"), ptext()))

    # ---- S3 кондиционеры выключены при фрикулинге
    log("\n=== S3: при работающем фрикулинге кондиционеры выключены ===")
    ok = wait_for(lambda: st("aux_v") == "off" and st("oas_v") == "off", 90)
    ok2 = wait_for(lambda: st("aux_c") == "off" and st("oas_c") == "off", 90)
    check(
        "S3 кондиционеры выключены и подтверждено",
        ok and ok2,
        "virtual %s/%s факт %s/%s"
        % (st("aux_v"), st("oas_v"), st("aux_c"), st("oas_c")),
    )

    # ---- S4 защита по низу
    log("\n=== S4: в доме 14.5 °C -> жёсткая защита ВЫКЛ ===")
    set_t(14.5, 9.0)
    check(
        "S4 защита выключила вентиляцию",
        wait_for(lambda: not vent_on(), 60),
        str(st("why")),
    )

    # ---- S5 возврат
    log("\n=== S5: снова 23 °C -> ВКЛ ===")
    set_t(23.0, 9.0)
    check("S5 вентиляция вернулась", wait_for(vent_on, 60), str(st("why")))

    # ---- S6 охлаждение до гистерезиса
    log("\n=== S6: остыло до 20.5 (уставка 22, гистерезис 1) -> ВЫКЛ ===")
    set_t(20.5, 9.0)
    check(
        "S6 выключилась по гистерезису",
        wait_for(lambda: not vent_on(), 90),
        str(st("why")),
    )

    # ---- S7 морозные циклы
    log("\n=== S7: мороз −25 °C -> циклы 1 мин / 1 мин ===")
    setn("frost_on", 1.0)
    setn("frost_off", 1.0)
    set_t(23.0, -25.0)
    end = time.time() + 170
    prev = vent_on()
    trans = []
    frost_why = []
    while time.time() < end:
        refresh()
        if "мороз" in str(st("why")):
            frost_why.append(str(st("why")))
        cur = vent_on()
        if cur != prev:
            trans.append((round(time.time() - T0), cur))
            log("    переход: %s" % ("ВКЛ" if cur else "ВЫКЛ"))
            prev = cur
        time.sleep(3)
    check("S7 циклы: ≥2 перехода", len(trans) >= 2, str(trans))
    refresh()
    check("S7 причина упоминает мороз", bool(frost_why), (frost_why[0] if frost_why else str(st("why"))))
    setn("frost_on", 5.0)
    setn("frost_off", 10.0)

    # ---- S8 эффективность
    log("\n=== S8: фрикулинг неэффективен (5 мин, падение 5 °C) ===")
    setn("eff_min", 5.0)
    setn("eff_delta", 5.0)
    set_t(23.0, 9.0)
    wait_for(vent_on, 90)
    ok = wait_for(lambda: st("problem") is True, 420, step=10)
    check(
        "S8 зафиксирована неэффективность",
        ok,
        "проблема=%s | %s" % (st("problem"), st("why")),
    )
    ok2 = wait_for(lambda: st("aux_v") == "on" or st("oas_v") == "on", 120)
    check(
        "S8 кондиционеры разрешены при неэффективном фрикулинге",
        ok2,
        "virtual %s/%s" % (st("aux_v"), st("oas_v")),
    )
    setn("eff_min", 20.0)
    setn("eff_delta", 0.5)

    # ---- S9 жара: оба кондиционера
    log("\n=== S9: в доме 26 °C (> 24) -> оба кондиционера ===")
    set_t(26.0, 21.0)
    ok = wait_for(lambda: "жарко" in str(st("why")), 120)
    ok2 = wait_for(lambda: st("aux_v") == "on" and st("oas_v") == "on", 120)
    ok3 = wait_for(lambda: st("aux_c") == "on" and st("oas_c") == "on", 150)
    check("S9 режим «жарко»", ok, str(st("why")))
    check(
        "S9 оба кондиционера включены и подтверждены",
        ok2 and ok3,
        "факт %s/%s" % (st("aux_c"), st("oas_c")),
    )

    # ---- S10 перегрев -> алерт
    log("\n=== S10: 31 °C (> тревога 30) -> алерт на ПК ===")
    set_t(31.0, 21.0)
    time.sleep(40)
    refresh()
    check(
        "S10 перегрев виден в статусе/причине",
        "жарко" in str(st("why")),
        str(st("why")),
    )

    # ---- S11 пауза
    log("\n=== S11: ручная пауза ===")
    press("pause")
    ok = wait_for(lambda: "пауза" in str(st("why")), 60)
    check("S11 пауза ставится", ok, str(st("why")))
    press("unpause")
    ok2 = wait_for(lambda: "пауза" not in str(st("why")), 60)
    check("S11 пауза снимается", ok2, str(st("why")))

finally:
    log("\n=== возврат к норме ===")
    for k, v in CANON.items():
        try:
            setn(k, v)
        except Exception:
            pass
    try:
        apply_options(
            {"temp_sensor": REAL_IN, "outside_sensor": REAL_OUT, "single_ac": False}
        )
    except Exception as e:
        log("  !! не удалось вернуть датчики: %s" % e)
    time.sleep(12)
    refresh()
    if vent_on():
        req("POST", "/api/services/switch/turn_off", {"entity_id": E["sup"]})
        req("POST", "/api/services/switch/turn_off", {"entity_id": E["exh"]})
        log("  вентиляция выключена принудительно")
    time.sleep(5)
    refresh()
    log("итог: " + snap())
    up_end = num("uptime")
    if up_start and up_end:
        check(
            "ESP без перезагрузки (аптайм растёт)",
            up_end >= up_start,
            "%s -> %s" % (up_start, up_end),
        )

print("\n================ ИТОГ ================")
bad = 0
for name, ok, det in RESULTS:
    if not ok:
        bad += 1
    print(("  OK   " if ok else "  FAIL ") + name + ((" — " + det) if det else ""))
print("\nВсего %d, провалов %d" % (len(RESULTS), bad))
sys.exit(1 if bad else 0)
