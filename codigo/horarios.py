"""Interpreta horarios escritos en español ("Lunes a jueves de 7:00 a.m. a 7:30 p.m. y Viernes ...")
y responde si un lugar está abierto durante una visita.

Representación: dict {dia(0=lunes..6=domingo): [(inicio_min, fin_min), ...]}.
fin_min puede pasar de 1440 cuando el horario cruza la medianoche (p. ej. 11:30 a.m. a 1:00 a.m.).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime

DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
NOMBRES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_DIA_RE = r"(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?"
_HORA = r"(\d{1,2})(?::(\d{2}))?\s*([ap])?\.?\s*m?\.?"
# "7:00 a.m. a 7:30 p.m." | "8:00 a 5:00 p.m." | "9 - 18" | "08:00-17:00"
_RANGO = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(?:([ap])\.?\s?m\.?)?\s*(?:a|-|–|—|hasta)\s*(\d{1,2})(?::(\d{2}))?\s*(?:([ap])\.?\s?m\.?)?")


def _norm(t: str) -> str:
    t = (t or "").replace("–", "-").replace("—", "-")                  # los guiones largos se perderían al pasar a ASCII
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\b12(:00)?\s*m\b\.?", "12:00 pm", t)                  # "12:00 m." = mediodía
    t = re.sub(r"<[^>]+>", " . ", t).replace("\n", " . ")
    return re.sub(r"\s+", " ", t).strip()


def _minutos(h: int, m: str | None, suf: str | None) -> int:
    h = int(h) % 24 if suf is None else int(h)
    mm = int(m) if m else 0
    if suf == "p" and h < 12:
        h += 12
    if suf == "a" and h == 12:
        h = 0
    return h * 60 + mm


def _dias_en(texto: str) -> set[int]:
    """Días citados en un fragmento: rangos ("lunes a jueves", con vuelta de semana), listas y 'fines de semana'."""
    dias: set[int] = set()
    resto = texto
    for a, b in re.findall(_DIA_RE + r"\s+(?:a|hasta)\s+" + _DIA_RE, texto):
        i, j = DIAS[a], DIAS[b]
        k = i
        while True:
            dias.add(k)
            if k == j:
                break
            k = (k + 1) % 7
    resto = re.sub(_DIA_RE + r"\s+(?:a|hasta)\s+" + _DIA_RE, " ", resto)
    if re.search(r"fines? de semana|fin de semana", resto):
        dias |= {5, 6}
    if re.search(r"todos los dias|diario|a diario", resto):
        dias |= set(range(7))
    for d in re.findall(_DIA_RE, resto):
        dias.add(DIAS[d])
    return dias


def parsear_horario(texto: str | None) -> dict[int, list[tuple[int, int]]] | None:
    """Devuelve el horario semanal o None si no se pudo interpretar (entonces: 'verificar')."""
    if not texto or not str(texto).strip():
        return None
    t = _norm(str(texto))
    if re.search(r"24\s*horas|abierto las 24", t):
        return {d: [(0, 1440)] for d in range(7)}
    rangos = list(_RANGO.finditer(t))
    if not rangos:
        return None
    sched: dict[int, list[tuple[int, int]]] = {}
    previo_fin = 0
    dias_prev: set[int] = set()
    for r in rangos:
        gap = t[previo_fin:r.start()]
        dias = _dias_en(gap)
        if not dias and "festiv" in gap:        # tramo solo para festivos: no se asigna a un día de semana
            previo_fin = r.end()
            continue
        if not dias:
            dias = dias_prev or set(range(7))
        h1, m1, s1, h2, m2, s2 = r.groups()
        if s1 is None and s2 is not None:
            # "8:00 a 5:00 p.m." -> inicio a.m. si cabe antes del cierre
            s1 = "a" if (int(h1) % 12) <= (int(h2) % 12) or s2 == "p" and int(h1) < 12 else "p"
        ini = _minutos(h1, m1, s1)
        fin = _minutos(h2, m2, s2)
        if s1 is None and s2 is None and fin <= ini and int(h2) < 12:
            fin += 12 * 60
        if fin <= ini:
            fin += 24 * 60
        for d in dias:
            sched.setdefault(d, []).append((ini, fin))
        previo_fin = r.end()
        dias_prev = dias
    return sched or None


def esta_abierto(sched: dict, llegada: datetime, salida: datetime) -> tuple[bool, str]:
    """¿Cubre el horario toda la visita [llegada, salida]? Devuelve (abierto, detalle legible)."""
    d = llegada.weekday()
    t0 = llegada.hour * 60 + llegada.minute
    t1 = t0 + int((salida - llegada).total_seconds() // 60)
    tramos = [(a, b) for a, b in sched.get(d, [])] + [(a - 1440, b - 1440) for a, b in sched.get((d - 1) % 7, []) if b > 1440]
    for a, b in tramos:
        if a <= t0 and t1 <= b:
            c = b % 1440
            return True, f"abierto hasta las {c // 60:02d}:{c % 60:02d}"
    if not tramos:
        return False, f"cerrado los {NOMBRES[d]}"
    a, b = max(tramos, key=lambda x: x[1])
    ab = f"{max(a, 0) // 60:02d}:{max(a, 0) % 60:02d}"
    ce = f"{(b % 1440) // 60:02d}:{(b % 1440) % 60:02d}"
    return False, f"horario del {NOMBRES[d]}: {ab}–{ce}"


def resumen(sched: dict | None) -> str:
    if not sched:
        return "sin horario"
    partes = []
    for d in range(7):
        if d in sched:
            partes.append(f"{NOMBRES[d][:3]} " + "/".join(f"{a // 60:02d}:{a % 60:02d}-{(b % 1440) // 60:02d}:{(b % 1440) % 60:02d}" for a, b in sched[d]))
    return "; ".join(partes)
