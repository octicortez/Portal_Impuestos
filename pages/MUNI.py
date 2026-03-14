import streamlit as st
import pandas as pd
import time
import os
import base64
import shutil
import glob
from pypdf import PdfWriter
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import datetime

# --- IDs DE LA MUNICIPALIDAD ---
ID_C1_MUNI = "vEIWCIR"
ID_C2_MUNI = "vEIWSEC"
ID_C3_MUNI = "vEIWMZA"
ID_C4_MUNI = "vEIWPA"
ID_C5_MUNI = "vEIWPH"
ID_FECHA_MUNI = "vEIWVTO"
ID_BUSCAR_MUNI = "BUSCAR"
ID_TOTAL_MUNI = "span_vTOTDEU"
ID_BOLETA_MUNI = "BOLETADEPAGO1"
ID_IMPRIMIR_MUNI = "IMPRIMIR"

def consultar_muni(driver, wait, nomenclatura, periodo_buscado, carpeta_destino, fecha_pago_obj):
    fecha_pago_str = fecha_pago_obj.strftime("%d/%m/%Y")
    partes = str(nomenclatura).split("-")
    
    # Actualizamos el diccionario inicial
    datos_extraidos = {
        "Nomenclatura": nomenclatura, 
        "Periodo": periodo_buscado, 
        "Importe Total": "No encontrado", 
        "Vencimiento": fecha_pago_str, 
        "Estado": "Sin Deuda"
    }
    
    if len(partes) != 5:
        datos_extraidos["Estado"] = "Formato Incorrecto"
        return datos_extraidos

    try:
        driver.delete_all_cookies()
        driver.get("https://app.riocuarto.gov.ar:8443/gestiontributaria/servlet/com.recursos.hceduimpmul?Inmo")
        time.sleep(2) 

        c1 = wait.until(EC.presence_of_element_located((By.ID, ID_C1_MUNI)))
        c1.clear(); c1.send_keys(partes[0]); time.sleep(0.5)
        c2 = driver.find_element(By.ID, ID_C2_MUNI); c2.clear(); c2.send_keys(partes[1]); time.sleep(0.5)
        c3 = driver.find_element(By.ID, ID_C3_MUNI); c3.clear(); c3.send_keys(partes[2]); time.sleep(0.5)
        c4 = driver.find_element(By.ID, ID_C4_MUNI); c4.clear(); c4.send_keys(partes[3]); time.sleep(0.5)
        c5 = driver.find_element(By.ID, ID_C5_MUNI); c5.clear(); c5.send_keys(partes[4]); time.sleep(1)

        casillero_fecha = driver.find_element(By.ID, ID_FECHA_MUNI)
        casillero_fecha.click(); time.sleep(0.5)
        casillero_fecha.send_keys(Keys.END)
        for _ in range(12): casillero_fecha.send_keys(Keys.BACKSPACE)
        time.sleep(0.5); casillero_fecha.send_keys(fecha_pago_str); time.sleep(1)

        boton_buscar = driver.find_element(By.ID, ID_BUSCAR_MUNI)
        driver.execute_script("arguments[0].click();", boton_buscar)
        time.sleep(3) # Damos tiempo a que cargue la tabla

        # --- TRADUCTOR DE FORMATO MUNI ---
        # Convierte tu "2026/04" de Excel al formato raro "2026/ 4-01" de la Muni
        periodo_str = str(periodo_buscado).strip()
        if "/" in periodo_str:
            anio, mes = periodo_str.split("/")
            mes_entero = int(mes)
            if mes_entero < 10:
                periodo_muni_formato = f"{anio}/ {mes_entero}-01"
            else:
                periodo_muni_formato = f"{anio}/{mes_entero}-01"
        else:
            periodo_muni_formato = periodo_str

        # --- EL NUEVO ESCÁNER LÁSER PARA LA MUNI ---
        filas = driver.find_elements(By.TAG_NAME, "tr")
        periodo_encontrado = False
        
        for fila in filas:
            texto_fila = fila.text.strip()
            # Buscamos usando el formato raro traducido
            if periodo_muni_formato in texto_fila:
                try:
                    # Encontramos la fila, ahora hacemos clic en SU cuadradito
                    casilla = fila.find_element(By.TAG_NAME, "input")
                    driver.execute_script("arguments[0].click();", casilla)
                    time.sleep(1)
                    
                    # Leemos el importe total actualizado
                    elemento_total = driver.find_element(By.ID, ID_TOTAL_MUNI)
                    datos_extraidos["Importe Total"] = elemento_total.text.strip()
                    periodo_encontrado = True
                    break # Terminamos de buscar
                except Exception:
                    pass
                    
        if not periodo_encontrado:
            datos_extraidos["Estado"] = f"Error: Periodo '{periodo_buscado}' no encontrado"
            return datos_extraidos

        # --- CONTINÚA LA DESCARGA NORMAL ---
        boton_boleta = driver.find_element(By.ID, ID_BOLETA_MUNI)
        driver.execute_script("arguments[0].click();", boton_boleta)
        
        boton_imprimir = wait.until(EC.element_to_be_clickable((By.ID, ID_IMPRIMIR_MUNI)))
        driver.execute_script("arguments[0].click();", boton_imprimir); time.sleep(5) 

        cuadritos = driver.find_elements(By.CSS_SELECTOR, "iframe, embed, object")
        pdf_url = None
        for cuadrito in cuadritos:
            link = cuadrito.get_attribute("src") or cuadrito.get_attribute("data")
            if link: pdf_url = link; break

        if pdf_url:
            base64_pdf = driver.execute_async_script("""
                var uri = arguments[0]; var callback = arguments[1]; var xhr = new XMLHttpRequest();
                xhr.open('GET', uri, true); xhr.responseType = 'arraybuffer';
                xhr.onload = function() {
                    var arrayBuffer = xhr.response; var byteArray = new Uint8Array(arrayBuffer); var byteString = '';
                    for (var i = 0; i < byteArray.byteLength; i++) { byteString += String.fromCharCode(byteArray[i]); }
                    callback(btoa(byteString));
                };
                xhr.onerror = function() { callback(null); }; xhr.send();
            """, pdf_url)
            
            if base64_pdf:
                periodo_limpio = str(periodo_buscado).replace('/', '-')
                ruta_final = os.path.join(carpeta_destino, f"Boleta_MUNI_{nomenclatura}_{periodo_limpio}.pdf")
                with open(ruta_final, "wb") as f: f.write(base64.b64decode(base64_pdf))
                datos_extraidos["Estado"] = "PDF Descargado"
            else: datos_extraidos["Estado"] = "Error al descargar PDF"
        else: datos_extraidos["Estado"] = "PDF no encontrado"
        return datos_extraidos

    except Exception as e:
        try:
            driver.save_screenshot(os.path.join(carpeta_destino, f"ERROR_MUNI_{nomenclatura}.png"))
            datos_extraidos["Estado"] = "Error (Ver foto en ZIP)"
        except: 
            datos_extraidos["Estado"] = "Error Crítico"
        return datos_extraidos

st.set_page_config(page_title="Gestor Municipalidad", page_icon="🏛️", layout="centered")
st.title("🏛️ Gestor Automático - MUNI")
fecha_seleccionada = st.date_input("Fecha de pago:", datetime.date.today())

# Actualizamos el aviso en pantalla
st.info("El Excel debe tener: Columna 1 (Nomenclatura) y Columna 2 (Periodo).")
archivo_subido = st.file_uploader("Sube tu archivo Excel para Municipalidad", type=["xlsx"])

if "proceso_terminado" not in st.session_state: st.session_state.proceso_terminado = False

if archivo_subido is not None:
    df = pd.read_excel(archivo_subido)
    st.write(f"Filas detectadas: {len(df)}")
    
    if st.button("🚀 Iniciar Búsqueda MUNI", use_container_width=True):
        carpeta_temp = "Boletas_MUNI_Temp"
        if os.path.exists(carpeta_temp): shutil.rmtree(carpeta_temp, ignore_errors=True)
        os.makedirs(carpeta_temp, exist_ok=True)
        for f_viejo in ["Boletas_MUNI.zip", "MUNI_Unidas.pdf"] + glob.glob("Reporte_MUNI*.xlsx"):
            if os.path.exists(f_viejo): os.remove(f_viejo)
                    
        resultados = []; barra = st.progress(0); estado = st.empty()
        
        try:
            estado.text("Iniciando motor MUNI...")
            chrome_options = Options(); chrome_options.add_argument("--window-size=1920,1080")
            if os.path.exists("/usr/bin/chromium"):
                chrome_options.binary_location = "/usr/bin/chromium"; chrome_options.add_argument("--headless=new") 
                chrome_options.add_argument("--no-sandbox"); chrome_options.add_argument("--disable-dev-shm-usage") 
                chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                servicio = Service("/usr/bin/chromedriver")
            else:
                chrome_options.add_argument("--headless=new"); chrome_options.page_load_strategy = 'eager' 
                servicio = Service(ChromeDriverManager().install())
                
            driver = webdriver.Chrome(service=servicio, options=chrome_options)
            driver.set_page_load_timeout(180); wait = WebDriverWait(driver, 15)
            
            for index, row in df.iterrows():
                if pd.isna(row.iloc[0]): continue
                nomenclatura = row.iloc[0]
                # Ahora leemos la columna 2 del Excel
                periodo = row.iloc[1] if len(row) > 1 else "-" 
                
                estado.text(f"Consultando: {nomenclatura}...")
                resultados.append(consultar_muni(driver, wait, nomenclatura, periodo, carpeta_temp, fecha_seleccionada))
                barra.progress(int(((index + 1) / len(df)) * 100))

            driver.quit()
            
            df_res = pd.DataFrame(resultados); df_res.to_excel("Reporte_MUNI.xlsx", index=False)
            estado.text("Uniendo PDFs...")
            pdfs = glob.glob(os.path.join(carpeta_temp, "*.pdf"))
            if pdfs:
                fusionador = PdfWriter()
                for p in pdfs: fusionador.append(p)
                fusionador.write("MUNI_Unidas.pdf"); fusionador.close()
            
            shutil.make_archive("Boletas_MUNI", 'zip', carpeta_temp)
            st.session_state.proceso_terminado = True
            shutil.rmtree(carpeta_temp, ignore_errors=True); estado.empty()
            
        except Exception as e: st.error(f"Error: {e}")

if st.session_state.proceso_terminado:
    st.success("✅ ¡Terminado!")
    col1, col2, col3 = st.columns(3)
    with col1:
        if os.path.exists("Boletas_MUNI.zip"): st.download_button("📦 Bajar .ZIP", data=open("Boletas_MUNI.zip", "rb"), file_name="Boletas_MUNI.zip", mime="application/zip")
    with col2:
        if os.path.exists("MUNI_Unidas.pdf"): st.download_button("🖨️ Bajar PDF", data=open("MUNI_Unidas.pdf", "rb"), file_name="MUNI_Unidas.pdf", mime="application/pdf")
    with col3:
        if os.path.exists("Reporte_MUNI.xlsx"): st.download_button("📊 Bajar Excel", data=open("Reporte_MUNI.xlsx", "rb"), file_name="Reporte_MUNI.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")