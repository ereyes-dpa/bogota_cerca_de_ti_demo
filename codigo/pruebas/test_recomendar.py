import socket
import sys
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import chatbot  # noqa: E402
from recomendar import recomendar, recomendar_lote, resolver_cuando, resolver_origen  # noqa: E402

BASE = {"minutos": 120, "origen": "Suba, Bogotá", "cuando": "2026-11-14 15:00", "con": "ninos", "prefs": "naturaleza", "modo": "transporte"}


def test_origenes():
    assert resolver_origen("Suba, Bogotá")[2] == "Suba"
    assert resolver_origen("4.6495, -74.0624")[2] == "Chapinero"
    assert resolver_origen("Plaza de Bolívar")[2].startswith("Centro")
    la, lo, et = resolver_origen("Museo del Oro")
    assert et == "Museo del Oro" and 4.5 < la < 4.7
    with pytest.raises(ValueError):
        resolver_origen("lugar inexistente xyz")


def test_cuando():
    assert resolver_cuando("2026-11-14T15:00").hour == 15
    assert resolver_cuando("17:30").minute == 30


def test_504_usa_selector_propio():
    r = recomendar(BASE, fuente="guardada", escenario="piloto_suba_ninos")
    assert r["chatbot"]["status"] == 504 and r["recomendacion"]["origen"] == "selector_propio"
    assert r["recomendacion"]["plan"]["paradas"] and "enlaces" in r["recomendacion"]["plan"]


def test_plan_lograble_del_chatbot_se_usa():
    c = {"minutos": 120, "origen": "Chapinero", "cuando": "2026-11-09 19:30", "con": "solo", "prefs": "comer", "modo": "pie"}
    r = recomendar(c, fuente="guardada", escenario="piloto_chapinero_noche", rnt_en_linea=False)
    assert r["recomendacion"]["origen"] == "chatbot"
    assert r["recomendacion"]["plan"]["paradas"][0]["nombre"] == "PRESTO BTA LOURDES"


def test_plan_no_lograble_se_reemplaza():
    c = {"minutos": 180, "origen": "4.5981, -74.076", "cuando": "2026-11-09 10:00", "con": "pareja", "prefs": "cultura|comer", "modo": "pie"}
    r = recomendar(c, fuente="guardada", escenario="sintetico_cerrado_e_inexistente", rnt_en_linea=False)
    assert r["chatbot"]["plan"]["veredicto"] == "NO LOGRABLE" and r["recomendacion"]["origen"] == "selector_propio"


def test_validacion():
    with pytest.raises(ValueError):
        recomendar({**BASE, "con": "abuelos"}, fuente="ninguna")
    with pytest.raises(ValueError):
        recomendar({**BASE, "minutos": 600}, fuente="ninguna")


def test_lote_para_powerbi(tmp_path):
    consultas, paradas, chequeos = recomendar_lote(AQUI.parents[1] / "datos" / "consultas_ejemplo.csv", fuente="guardada", salida=tmp_path)
    assert len(consultas) == 8 and len(paradas) > 8 and len(chequeos) > 8
    # las 8 son respuestas reales de Candelaria: 6 planes suyos se recomiendan y los 2 con mascota se reemplazan
    assert consultas.chatbot_respondio.all()
    assert (consultas.recomendacion_origen == "chatbot").sum() == 6
    assert {"consulta_id", "recomendacion_origen", "chatbot_veredicto"} <= set(consultas.columns)
    assert (tmp_path / "paradas.csv").exists()


def test_espera_maxima(monkeypatch):
    llamadas = []

    def lento(req, timeout):
        llamadas.append(timeout)
        raise socket.timeout("timed out")
    monkeypatch.setattr(chatbot.urllib.request, "urlopen", lento)
    r = chatbot.consultar(chatbot.Backend("candelaria"), "hola", espera_s=40)
    assert not r.ok and "40 s" in r.error and len(llamadas) == 1 and llamadas[0] <= 40


def test_menu_de_guardadas_solo_funcionales():
    """El menú del dashboard ofrece solo respuestas reales HTTP 200 del mensaje actual; las 504 y sintéticas quedan para pruebas."""
    import json
    from chatbot import RESPUESTAS_REALES
    d = json.loads(RESPUESTAS_REALES.read_text(encoding="utf-8"))
    menu = {k: v for k, v in d.items() if v.get("real") and v.get("prompt_compacto") and v.get("status") == 200 and v.get("respuesta")}
    assert len(menu) == 8 and all(v.get("orden") for v in menu.values())
    for k in menu:
        r = recomendar({**d[k]["parametros"], "origen": f"{d[k]['parametros']['lat']}, {d[k]['parametros']['lon']}"},
                       fuente="guardada", escenario=k, rnt_en_linea=False)
        assert r["chatbot"]["ok"] and r["recomendacion"]["plan"], k


def test_tiempos_por_modo():
    """Fórmulas que explica la página de inicio: km por calle = línea recta × 1,3; minutos = km / velocidad + minutos fijos."""
    from planificador import haversine_km, tiempo_traslado
    a, b = (4.6495, -74.0624), (4.6720, -74.0624)          # ~2,5 km al norte en línea recta
    km = haversine_km(*a, *b) * 1.3
    assert abs(tiempo_traslado(a, b, "pie", False)[0] - km / 4.8 * 60) < 0.01
    assert abs(tiempo_traslado(a, b, "pie", True)[0] - km / 3.6 * 60) < 0.01
    assert abs(tiempo_traslado(a, b, "bici", False)[0] - km / 12 * 60) < 0.01
    assert abs(tiempo_traslado(a, b, "transporte", False)[0] - (6 + km / 17 * 60 + 4)) < 0.01
    assert abs(tiempo_traslado(a, b, "auto", False)[0] - (8 + km / 23 * 60)) < 0.01
    cerca = (4.6500, -74.0624)                              # tramo corto: se camina aunque el modo sea transporte o auto
    assert tiempo_traslado(a, cerca, "transporte", False) == tiempo_traslado(a, cerca, "pie", False)
    assert tiempo_traslado(a, cerca, "auto", False) == tiempo_traslado(a, cerca, "pie", False)


def test_modo_auto():
    r = recomendar({"minutos": 180, "origen": "Usaquén", "cuando": "2026-11-14 11:00", "con": "pareja", "prefs": ["cultura"], "modo": "auto"},
                   fuente="ninguna", rnt_en_linea=False)
    assert r["consulta"]["modo"] == "auto" and r["recomendacion"]["plan"]["paradas"]
