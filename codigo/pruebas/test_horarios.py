import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horarios import esta_abierto, parsear_horario


def dt(dia, h, m=0):  # 2026-11-09 es lunes
    return datetime(2026, 11, 9 + dia, h, m)


def test_lunes_a_jueves_y_viernes():
    s = parsear_horario("Lunes a jueves de 7:00a.m. a 7:30 p.m. y Viernes de 7:00 a.m. a 5:30 p.m.")
    assert s[0] == [(420, 1170)] and s[3] == [(420, 1170)] and s[4] == [(420, 1050)]
    assert 5 not in s and 6 not in s


def test_fines_de_semana_y_festivos():
    s = parsear_horario("Lunes a viernes de 10:00 a.m. a 7:00 p.m. y los fines de semana y festivos de 9:00 a.m. a 7:00 p.m")
    assert s[0] == [(600, 1140)] and s[5] == [(540, 1140)] and s[6] == [(540, 1140)]


def test_cruza_medianoche_y_vuelta_de_semana():
    s = parsear_horario("Domingo a jueves de 11:30 a.m. a 10:00p.m. Viernes y sábado de 11:30 a.m. a 1:00 a.m.")
    assert s[6] == [(690, 1320)] and s[0] == [(690, 1320)] and s[3] == [(690, 1320)]
    assert s[4] == [(690, 1500)] and s[5] == [(690, 1500)]
    # sábado 00:30 sigue abierto por el turno del viernes
    ok, _ = esta_abierto(s, dt(5, 0, 30), dt(5, 0, 50))
    assert ok


def test_plazas_con_br_y_sin_sufijo_en_inicio():
    s = parsear_horario("Lunes a jueves 8:00 a 5:00 p.m. <br>Viernes 8:00 a.m. a 3:00 p.m. <br>Sábado 8:00 a.m. a 5:00 p.m. <br>Domingo 8:00 a.m. a 4:00 p.m. <br>Festivos 8:00a.m. a 3:00 p.m.")
    assert s[0] == [(480, 1020)] and s[4] == [(480, 900)] and s[6] == [(480, 960)]


def test_lista_con_rango_y_dia_suelto():
    s = parsear_horario("Lunes 7:00 a.m. - 3:00 p.m. <br>Martes a Jueves, domingo y festivos: 7:00 a.m. - 6:00 p.m. <br>Viernes y Sábado: 7:00 a.m. - 8:00 p.m.")
    assert s[0] == [(420, 900)] and s[1] == [(420, 1080)] and s[6] == [(420, 1080)] and s[5] == [(420, 1200)]


def test_todos_los_dias_y_sin_dato():
    s = parsear_horario("Lunes a domingo de 8:00 a.m. a 8:00 p.m.")
    assert all(s[d] == [(480, 1200)] for d in range(7))
    assert parsear_horario("") is None and parsear_horario(None) is None and parsear_horario("Consultar en el sitio") is None


def test_esta_abierto():
    s = parsear_horario("Martes a domingo de 9:00 a.m. a 5:00 p.m.")
    assert esta_abierto(s, dt(1, 10), dt(1, 11))[0]
    ok, det = esta_abierto(s, dt(0, 10), dt(0, 11))   # lunes
    assert not ok and "cerrado" in det
    ok, det = esta_abierto(s, dt(1, 16, 30), dt(1, 17, 30))   # termina después del cierre
    assert not ok and "09:00" in det
