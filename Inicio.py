import streamlit as st

st.set_page_config(
    page_title="Portal de Impuestos",
    page_icon="👋",
    layout="centered"
)

st.title("Bienvenido al Portal de Impuestos")
st.markdown("---")

st.markdown("""
### Sistema de Descarga Automática
Hola! Este es tu asistente virtual para descargar boletas de impuestos de forma masiva.

👈 **Para empezar, elige qué quieres hacer en el menú de la izquierda:**

* **💧 EMOS:** Sube un Excel con Nomenclatura y Periodo (ej: 2026/04).
* **🏛️ MUNI:** Sube un Excel con Nomenclatura y Periodo (ej: 2026/04) y el sistema lo adaptará automáticamente.

---
""")