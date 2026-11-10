"""Componente de Streamlit con la pantalla «Cuéntame lo esencial» (componentes/app_telefono/index.html).

Se declara en un módulo importable porque Streamlit no permite declarar componentes dentro de una página de st.navigation.
"""
from pathlib import Path

import streamlit.components.v1 as components

telefono = components.declare_component("app_telefono", path=str(Path(__file__).resolve().parents[1] / "componentes" / "app_telefono"))
