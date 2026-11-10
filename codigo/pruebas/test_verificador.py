import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
from chatbot import leer_respuesta  # noqa: E402
from planificador import Solicitud, cargar_catalogo  # noqa: E402
from verificador import verificar  # noqa: E402

D = json.loads((AQUI / "respuestas_candelaria.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cat():
    df = cargar_catalogo()
    # horario oficial de prueba (el mismo formato que Guía Destino Diverso) para La Puerta Falsa
    df.loc[df.nombre == "La Puerta Falsa", ["horario_texto", "horario_fuente"]] = ["Lunes a domingo de 9:00 a.m. a 8:00 p.m.", "guia_destino_diverso"]
    return df


def req_de(k):
    p = D[k]["parametros"]
    return Solicitud(p["lat"], p["lon"], p["minutos"], datetime.strptime(p["cuando"], "%Y-%m-%d %H:%M"), p["con"], tuple(p["prefs"]), p["modo"])


def correr(k, cat):
    return verificar(req_de(k), leer_respuesta(D[k]["respuesta"], cat), cat)


def estados(v, id_):
    return [c["estado"] for c in v["chequeos"] if c["id"] == id_]


def test_no_cabe_detecta_distancias_reales(cat):
    v = correr("sintetico_no_cabe", cat)
    assert v["veredicto"] == "NO LOGRABLE"
    assert estados(v, "tiempo") == ["falla"] and v["duracion_total_min"] > 120
    assert estados(v, "consistencia") == ["aviso"]          # declara 118 y la suma real es mucho mayor


def test_inexistente_y_cerrado(cat):
    v = correr("sintetico_cerrado_e_inexistente", cat)
    assert v["veredicto"] == "NO LOGRABLE"
    assert "falla" in estados(v, "catalogo")                  # Café Imaginario del Chorro
    assert "aviso" in estados(v, "apertura")                  # Museo del Oro, lunes: supuesto, no horario oficial
    assert not any("Capilla" in (p["nombre_catalogo"] or "") for p in v["paradas"])   # no se empareja por cercanía


def test_chapinero_noche_total_inconsistente(cat):
    v = correr("chapinero_noche", cat)
    assert estados(v, "consistencia") == ["aviso"]            # declara 80–100 min; la suma real es ~65 o menos
    assert v["duracion_total_min"] < 90 and len(v["paradas"]) == 2      # solo el primer plan (a pie)
    assert all(c == "ok" for c in estados(v, "catalogo"))     # todas las paradas existen


def test_json_ingles_resuelve_por_coordenadas(cat):
    v = correr("chapinero_json", cat)
    assert estados(v, "catalogo").count("ok") == 3


def test_suba_prosa_es_lograble(cat):
    v = correr("suba_ninos", cat)
    assert v["veredicto"] in ("LOGRABLE", "LOGRABLE CON ADVERTENCIAS")
    assert [p["opcional"] for p in v["paradas"]] == [False, True, True]
    assert [p["nombre_catalogo"] for p in v["paradas"]][0] == "Plaza Fundacional de Suba"


def test_mascota_exige_etiqueta_oficial(cat):
    r = req_de("suba_ninos")
    r.mascota = True
    v = verificar(r, leer_respuesta(D["suba_ninos"]["respuesta"], cat), cat)
    assert "falla" in estados(v, "mascota") and v["veredicto"] == "NO LOGRABLE"


def test_horario_oficial_se_usa(cat):
    lect = {"paradas": [{"nombre": "La Puerta Falsa", "lat": None, "lon": None, "minutos_en_sitio": 30, "traslado_min": None}], "avisos": []}
    r = Solicitud(4.5981, -74.0760, 120, datetime(2026, 11, 9, 21, 0), "pareja", (), "pie")      # 21:00 → cierra a las 20:00
    v = verificar(r, lect, cat)
    assert "falla" in estados(v, "apertura")
    assert any("oficial" in c["detalle"] for c in v["chequeos"] if c["id"] == "apertura")


def test_sin_paradas(cat):
    v = verificar(req_de("suba_ninos"), {"paradas": [], "avisos": []}, cat)
    assert v["veredicto"] == "NO LOGRABLE"


def test_restaurante_rnt_real_de_candelaria(cat):
    # Respuesta real al prompt del piloto: "PRESTO BTA LOURDES" es un prestador del RNT, no la Plaza de Lourdes
    v = correr("piloto_chapinero_noche", cat)
    p = v["paradas"][0]
    assert p["nombre_catalogo"] == "PRESTO BTA LOURDES" and p["forma_match"].startswith("RNT")
    assert estados(v, "catalogo") == ["ok"]
    assert estados(v, "apertura") == ["aviso"]          # restaurante sin horario oficial: lunes 19:35 es "probable", no confirmado


def test_respuestas_fallidas_guardadas():
    from chatbot import Backend, consultar
    r = consultar(Backend("simulado", escenario="piloto_suba_ninos"), "")
    assert not r.ok and r.status == 504 and r.simulada


def test_403_explica_bloqueo_y_no_reintenta(monkeypatch):
    import io
    import urllib.error
    import chatbot
    llamadas = []

    def falso(req, timeout):
        llamadas.append(req.get_header("User-agent"))
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b""))
    monkeypatch.setattr(chatbot.urllib.request, "urlopen", falso)
    r = chatbot.consultar(chatbot.Backend("candelaria"), "hola")
    assert not r.ok and r.status == 403 and "Cloudflare" in r.error
    assert len(llamadas) == 1 and llamadas[0].startswith("BogotaCercaDeTi-Piloto")


# ---- respuestas reales del prompt compacto (10-nov-2026)
def test_exceso_pequeno_es_advertencia(cat):
    """Candelaria cuadra el total en 120/120; nuestra estimación de traslados lo pasa por 2 min: no es un dato verificable."""
    v = correr("vivo_chapinero_lunes_noche", cat)
    assert estados(v, "tiempo") == ["aviso"]
    assert v["veredicto"] != "NO LOGRABLE"


def test_lugar_reconocido_por_coordenadas_y_nombre_propio(cat):
    """«Parque Simón Bolívar - Sector Virgilio Barco» llega con las coordenadas exactas de la Biblioteca Virgilio Barco."""
    v = correr("vivo_teusaquillo_sabado_bici", cat)
    assert "falla" not in estados(v, "catalogo")
    assert any("Virgilio Barco" in (p.get("nombre_catalogo") or "") for p in v["paradas"])


def test_mascota_sin_etiqueta_oficial_es_falla(cat):
    r = req_de("vivo_usaquen_domingo_mascota")
    r = Solicitud(r.lat, r.lon, r.minutos, r.cuando, r.con, r.prefs, r.modo, mascota=True)
    v = verificar(r, leer_respuesta(D["vivo_usaquen_domingo_mascota"]["respuesta"], cat), cat)
    assert estados(v, "mascota") == ["falla"] * 3 and v["veredicto"] == "NO LOGRABLE"
