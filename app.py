"""Bogotá Cerca de ti — dashboard piloto (Reto 2).

Dos páginas:
  · Inicio  (paginas/inicio.py): cómo usar el demo y cómo funciona el algoritmo (verificación, alternativa, tiempos por modo).
  · Demo    (paginas/demo.py):   la app a la izquierda y el resultado a la derecha.

Toda la lógica está en codigo/recomendar.py, el mismo script que se usa en Power BI.

Ejecutar:  streamlit run app.py

Acceso: si los secretos de Streamlit definen `clave_acceso` (en Streamlit Community Cloud: App settings → Secrets),
el dashboard pide esa clave antes de mostrar nada. Sin ese secreto, por ejemplo en local, entra directo.
"""
import hmac

import streamlit as st

st.set_page_config(page_title="Bogotá Cerca de ti · piloto", page_icon="🗺️", layout="wide")


def clave_configurada() -> str | None:
    try:
        return st.secrets.get("clave_acceso") or None
    except Exception:  # noqa: BLE001  (no hay secrets.toml)
        return None


clave = clave_configurada()
if clave and not st.session_state.get("acceso_ok"):
    st.markdown("### Bogotá Cerca de ti · piloto")
    st.caption("Acceso restringido al equipo del proyecto (DPA e IDT).")
    with st.form("acceso", clear_on_submit=True):
        intento = st.text_input("Clave de acceso", type="password")
        if st.form_submit_button("Entrar"):
            if hmac.compare_digest(intento.encode(), str(clave).encode()):
                st.session_state.acceso_ok = True
                st.rerun()
            st.error("Clave incorrecta.")
    st.stop()

pagina = st.navigation([
    st.Page("paginas/inicio.py", title="Inicio", icon="🏠", default=True),
    st.Page("paginas/demo.py", title="Demo", icon="📱"),
])
pagina.run()
