import streamlit as st
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import pandas as pd
from datetime import datetime, timedelta
import math
from streamlit_geolocation import streamlit_geolocation
import io
import json
import base64
from PIL import Image
from groq import Groq
# Coordenadas del punto central requerido (Ica, Perú)
LAT_OBJETIVO = -14.0780018
LON_OBJETIVO = -75.7399245
RADIO_MAX_KM = 0.5

# Formula de Haversine para calcular distancia entre dos coordenadas (Lat/Lon)
def calcular_distancia(lat1, lon1, lat2, lon2):
    rad = math.pi / 180
    dlat = (lat2 - lat1) * rad
    dlon = (lon2 - lon1) * rad
    a = math.sin(dlat/2)**2 + math.cos(lat1*rad) * math.cos(lat2*rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return 6371.0 * c  # Retorna la distancia en kilómetros

# Función para obtener la hora exacta de Perú (UTC-5) sin importar el servidor
def obtener_hora_peru():
    return datetime.utcnow() - timedelta(hours=5)

# Función auxiliar para calcular la diferencia de minutos netos restando el refrigerio si existe
def calcular_minutos_netos_raw(entrada_str, ref_inicio_str, ref_fin_str, salida_str):
    try:
        if entrada_str in ["Falta", "Permiso", "-", "", "nan", "None"] or salida_str in ["Falta", "Permiso", "-", "", "nan", "None"]:
            return 0
            
        t_entrada = datetime.strptime(entrada_str, "%I:%M %p")
        t_salida = datetime.strptime(salida_str, "%I:%M %p")
        if t_salida < t_entrada:
            t_salida += timedelta(days=1)
            
        total_jornada_min = int((t_salida - t_entrada).total_seconds() / 60.0)
        
        tiempo_refrigerio_min = 0
        if ref_inicio_str not in ["Falta", "Permiso", "-", "", "nan", "None"] and ref_fin_str not in ["Falta", "Permiso", "-", "", "nan", "None"]:
            t_ref_in = datetime.strptime(ref_inicio_str, "%I:%M %p")
            t_ref_fi = datetime.strptime(ref_fin_str, "%I:%M %p")
            if t_ref_fi < t_ref_in:
                t_ref_fi += timedelta(days=1)
            tiempo_refrigerio_min = int((t_ref_fi - t_ref_in).total_seconds() / 60.0)
            
        return max(0, total_jornada_min - tiempo_refrigerio_min)
    except Exception:
        return 0

# Convierte minutos totales a cadena estructurada h/min
def formatear_minutos_a_string(minutos_totales):
    if minutos_totales <= 0:
        return "0 h 0 min"
    horas = minutos_totales // 60
    minutos = minutos_totales % 60
    return f"{horas} h {minutos} min"

# =========================================================
# FUNCIONES AUXILIARES PARA REPORTE TIKTOK LIVE
# =========================================================
def analizar_historial_tiktok(imagen_bytes):
    try:
        # 1. Obtenemos la clave de los Secrets de Streamlit
        api_key_val = str(st.secrets["GROQ_API_KEY"]).strip()
        client = Groq(api_key=api_key_val)

        # 2. Convertimos la imagen a base64 para enviarla a Groq
        base64_image = base64.b64encode(imagen_bytes).decode('utf-8')

        prompt = """
        Analiza detenidamente esta captura de pantalla de un historial de transmisiones de TikTok Live.
        Debes responder ÚNICAMENTE con un objeto JSON válido (sin texto adicional, sin bloques de código markdown ```json).

        Estructura requerida:
        {
          "valido": true,
          "motivo_error": "",
          "dia": "21",
          "mes": "jul",
          "transmisiones": [
            {"inicio": "11:54 a. m.", "fin": "12:47 p. m."},
            {"inicio": "4:13 p. m.", "fin": "7:18 p. m."},
            {"inicio": "7:40 p. m.", "fin": "8:51 p. m."}
          ]
        }

        REGLAS ESTRICTAS:
        1. Comprueba la fecha de CADA bloque de transmisión visible en la captura. Si hay transmisiones de 2 o más días distintos (por ejemplo, 'jul 21' y 'jul 20'), establece "valido": false y "motivo_error": "La captura contiene transmisiones de días diferentes. Sube un reporte de un solo día."
        2. Si la imagen no corresponde a un historial de TikTok Live, responde "valido": false y "motivo_error": "La imagen subida no parece ser un historial válido de TikTok Live."
        3. Extrae exactamente las horas de inicio y fin de cada transmisión de ese día único.
        """

        # 3. Consulta al modelo de visión de Groq
        completion = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        texto_respuesta = completion.choices[0].message.content.strip()

        # Limpieza defensiva por si el modelo incluye etiquetas markdown
        if texto_respuesta.startswith("```json"):
            texto_respuesta = texto_respuesta.replace("```json", "").replace("```", "").strip()
        elif texto_respuesta.startswith("```"):
            texto_respuesta = texto_respuesta.replace("```", "").strip()

        return json.loads(texto_respuesta)

    except Exception as e:
        return {
            "valido": False,
            "motivo_error": f"Error al procesar la imagen con Groq: {e}"
        }
def calcular_duracion_rango_tiktok(inicio_str, fin_str):
    fmt = "%I:%M %p"
    try:
        i_clean = inicio_str.lower().replace("a. m.", "AM").replace("p. m.", "PM").replace(".", "").upper().strip()
        f_clean = fin_str.lower().replace("a. m.", "AM").replace("p. m.", "PM").replace(".", "").upper().strip()

        t_inicio = datetime.strptime(i_clean, fmt)
        t_fin = datetime.strptime(f_clean, fmt)

        if t_fin < t_inicio:
            t_fin += timedelta(days=1)

        diferencia = t_fin - t_inicio
        return int(diferencia.total_seconds() / 60.0)
    except Exception:
        return 0

# Configuracion de pagina con diseno responsivo y centrado sin emoticonos
st.set_page_config(page_title="Control de Asistencia", page_icon=None, layout="centered")

# Diccionario para convertir el mes del año a mayúsculas en español
MESES_ESPANOL = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL", 
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO", 
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
}

try:
    # Conexión utilizando los Secrets de Streamlit Cloud para producción (Convertido a diccionario explícito)
    gc = gspread.service_account_from_dict(dict(st.secrets["gspread"]))
    
    # Conexión directa con tu ID de Google Sheets
    hoja_calculo = gc.open_by_key('1-GCk6phMzn9UEAFomTYco8C8hoLYc7R_daBwcBuRwtU')

    # FUNCIÓN CON CACHÉ PARA EVITAR AGOTAR LA API DE GOOGLE (SOLUCIONA EL ERROR 429)
    @st.cache_data(ttl=60)
    def cargar_datos_pestana(pestana_nombre):
        try:
            wks_local = hoja_calculo.worksheet(pestana_nombre)
            return get_as_dataframe(wks_local).dropna(how="all").dropna(axis=1, how="all")
        except Exception:
            return pd.DataFrame()

    # Detectar el mes actual automáticamente basándose en la hora de Perú
    hora_peru_actual = obtener_hora_peru()
    mes_actual_num = hora_peru_actual.month
    nombre_pestana = MESES_ESPANOL[mes_actual_num]
    
    wks = hoja_calculo.worksheet(nombre_pestana)
    df = cargar_datos_pestana(nombre_pestana)
    
    # =========================================================
    # AUTOMATIZACIÓN DE FALTAS DIARIAS CON REFRIGERIO (Hora de Perú)
    # =========================================================
    fecha_hoy = hora_peru_actual.strftime("%d/%m/%Y")
    col_entrada = f"{fecha_hoy} (Entrada)"
    col_ref_salida = f"{fecha_hoy} (Inicio Ref)"
    col_ref_retorno = f"{fecha_hoy} (Fin Ref)"
    col_salida = f"{fecha_hoy} (Salida)"
    
    columnas_a_crear = []
    
    # Verificamos qué columnas faltan sin alterar el DataFrame original bruscamente
    if col_entrada not in df.columns:
        columnas_a_crear.append(col_entrada)
    if col_ref_salida not in df.columns:
        columnas_a_crear.append(col_ref_salida)
    if col_ref_retorno not in df.columns:
        columnas_a_crear.append(col_ref_retorno)
    if col_salida not in df.columns:
        columnas_a_crear.append(col_salida)
        
    if columnas_a_crear:
        # 1. Obtenemos el número de la última columna actual en el Sheets
        num_columnas_actuales = wks.col_count
        num_nuevas = len(columnas_a_crear)
        
        # 2. Agregamos físicamente el espacio de columnas nuevas a la derecha en Google Sheets
        wks.add_cols(num_nuevas)
        
        # 3. Preparamos los títulos y los valores por defecto ("Falta") para cada fila
        num_filas = len(df) + 1  # Incluye la fila de encabezados
        
        for i, col_name in enumerate(columnas_a_crear):
            col_index = num_columnas_actuales + i + 1
            
            # Creamos una lista de celdas para actualizar de golpe esa columna completa
            lista_celdas = wks.range(1, col_index, num_filas, col_index)
            
            # La primera celda es el encabezado (la fecha)
            lista_celdas[0].value = col_name
            
            # El resto de celdas hacia abajo se llenan con "Falta"
            for celda in lista_celdas[1:]:
                celda.value = "Falta"
                
            # Enviamos la actualización de esa columna al Sheets de forma segura sin borrar nada
            wks.update_cells(lista_celdas)
            
        # 4. Actualizamos el DataFrame interno de la app para que reconozca los nuevos cambios de inmediato
        st.cache_data.clear()
        df = cargar_datos_pestana(nombre_pestana)
    # =========================================================

    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False
        st.session_state.usuario_actual = ""

    if not st.session_state.autenticado:
        # Inyección de estilos CSS avanzados y adaptables (Media Queries) para PC y celular según el modelo
        st.markdown("""
            <style>
            /* Fondo base claro */
            .stApp {
                background-color: #f3f5f9 !important;
            }
            
            /* Ocultar elementos estructurales nativos superiores de Streamlit para el login limpio */
            header, div[data-testid="stHeader"] {
                background: transparent !important;
            }

            /* --- CONFIGURACIÓN PARA COMPUTADORA (PC) - SE MANTIENE PERFECTO E INTACTO --- */
            @media (min-width: 769px) {
                div[data-testid="stHorizontalBlock"] {
                    background-color: #ffffff !important;
                    border-radius: 24px !important;
                    box-shadow: 0px 15px 35px rgba(0, 0, 0, 0.08) !important;
                    overflow: hidden !important;
                    display: flex !important;
                    align-items: stretch !important;
                    min-height: 480px !important;
                    border: none !important;
                    padding: 0 !important;
                    gap: 0 !important;
                }
                div[data-testid="stHorizontalBlock"] > div:nth-child(1) {
                    background: linear-gradient(135deg, #4fa8fb 0%, #3b5998 100%) !important;
                    display: flex !important;
                    flex-direction: column !important;
                    justify-content: center !important;
                    align-items: center !important;
                    padding: 40px !important;
                    position: relative !important;
                }
                div[data-testid="stHorizontalBlock"] > div:nth-child(1)::after {
                    content: "";
                    position: absolute;
                    width: 100%;
                    height: 100%;
                    top: 0; left: 0;
                    background: radial-gradient(circle at 0% 100%, rgba(255,255,255,0.15) 0%, transparent 60%),
                                radial-gradient(circle at 100% 0%, rgba(255,255,255,0.1) 0%, transparent 50%);
                    pointer-events: none;
                }
                div[data-testid="stHorizontalBlock"] > div:nth-child(2) {
                    background-color: #ffffff !important;
                    padding: 45px 35px !important;
                    display: flex !important;
                    flex-direction: column !important;
                    justify-content: center !important;
                }
                div[data-testid="stVerticalBlock"] > div:has(div[class*="stTextInput"]) {
                    background: transparent !important;
                    box-shadow: none !important;
                    padding: 0 !important;
                    border: none !important;
                }
                div[data-testid="stHorizontalBlock"] > div:nth-child(1)::before {
                    content: "B";
                    font-family: 'sans-serif', Arial;
                    font-size: 64px;
                    font-weight: 900;
                    color: white;
                    border: 6px solid white;
                    border-radius: 18px;
                    padding: 5px 25px;
                    margin-bottom: 15px;
                    display: block;
                    letter-spacing: -2px;
                    box-shadow: 0px 4px 10px rgba(0,0,0,0.15);
                }
            }

            /* --- CONFIGURACIÓN PARA CELULAR - TOTALMENTE BLANCO Y PANTALLA COMPLETA --- */
            @media (max-width: 768px) {

                .stMainBlockContainer, .block-container, .stApp {

                    padding: 0px !important;

                    margin: 0px !important;

                    max-width: 100% !important;

                    width: 100% !important;

                    background-color: #ffffff !important;

                }

                

                div[data-testid="stElementContainer"], div[data-testid="stVerticalBlock"] {

                    padding: 0px !important;

                    margin: 0px !important;

                    width: 100% !important;

                }



                div[data-testid="stHorizontalBlock"] {

                    display: flex !important;

                    flex-direction: column !important;

                    background-color: #ffffff !important;

                    background-image: none !important;

                    width: 100% !important;

                    min-height: 100vh !important;

                    margin: 0px !important;

                    padding: 0px !important;

                    gap: 0px !important;

                    border: none !important;

                    border-radius: 0px !important;

                    box-shadow: none !important;

                }



                div[data-testid="stHorizontalBlock"] > div:nth-child(1) {

                    display: none !important;

                }



                div[data-testid="stHorizontalBlock"] > div:nth-child(2) {

                    padding: 80px 24px 40px 24px !important;

                    background-color: #ffffff !important;

                    width: 100% !important;

                    display: flex !important;

                    flex-direction: column !important;

                    justify-content: center !important;

                }



                div[data-testid="stVerticalBlock"] > div {

                    background-color: transparent !important;

                    box-shadow: none !important;

                    padding: 0px !important;

                    border: none !important;

                }

                

                div[data-testid="stHorizontalBlock"] h2 {

                    font-size: 32px !important;

                    font-weight: 700 !important;

                    color: #2f3542 !important;

                    text-align: center !important;

                    margin-bottom: 30px !important;

                }

            } 


            </style>
        """, unsafe_allow_html=True)

        # Contenedor estructural nativo
        col_izq, col_centro = st.columns([1, 1.2])
        
        with col_izq:
            st.markdown("<h1 style='text-align: center; color: white; font-size: 28px; font-weight: 800; margin: 0;'>Bienvenido</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: rgba(255,255,255,0.85); font-size: 14px; margin-top: 5px;'>Inicia sesión con código de usuario para continuar</p>", unsafe_allow_html=True)

        with col_centro:
            with st.container():
                st.markdown("<h2 style='text-align: center; margin-bottom: 5px; font-size: 24px; color: #2f3542; font-weight: bold;'>Bienvenido</h2>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: #747d8c; font-size: 13px; margin-bottom: 25px;'>Introduce tus credenciales de acceso.</p>", unsafe_allow_html=True)
                
                codigo_ingresado = st.text_input("Código de Asesor", type="password")
                
                st.write("") 
                
                # Inyección local segura para forzar el color azul en este botón específico
                st.markdown("""
                    <style>
                    div.stButton > button {
                        background-color: #007bff !important;
                        color: white !important;
                        border-radius: 8px !important;
                        border: none !important;
                        font-weight: bold !important;
                    }
                    </style>
                """, unsafe_allow_html=True)
                
                if st.button("INICIAR SESIÓN", use_container_width=True):
                    df["Codigo"] = df["Codigo"].astype(str).str.split('.').str[0].str.strip()
                    codigo_ingresado = str(codigo_ingresado).strip()
                    
                    usuario_encontrado = df[df["Codigo"] == codigo_ingresado]
                    
                    if not usuario_encontrado.empty:
                        st.session_state.autenticado = True
                        st.session_state.usuario_actual = usuario_encontrado.iloc[0]["Usuario"]
                        st.session_state.codigo_actual = codigo_ingresado
                        st.rerun()
                    else:
                        st.error("Código incorrecto. Intente de nuevo.")
    else:
        st.markdown(f"<h3 style='margin-bottom:0px;'>Control de Asistencia</h3>", unsafe_allow_html=True)
        
        es_admin = (st.session_state.usuario_actual == "VALENTIN ISASI")
        
        if es_admin:
            st.caption(f"Usuario: {st.session_state.usuario_actual} (Administrador)")
            tab_marcado, tab_tiktok, tab_reporte = st.tabs(["Mi Marcado", "Reporte TikTok", "Reporte General"])
        else:
            st.caption(f"Usuario: {st.session_state.usuario_actual}")
            tab_marcado, tab_tiktok = st.tabs(["Mi Marcado", "Reporte TikTok"])

        fila_usuario = df[df["Usuario"] == st.session_state.usuario_actual]
        
        # Lecturas de celdas del usuario actual
        marca_entrada = str(fila_usuario.iloc[0][col_entrada]).strip() if not pd.isna(fila_usuario.iloc[0][col_entrada]) else ""
        marca_ref_salida = str(fila_usuario.iloc[0][col_ref_salida]).strip() if not pd.isna(fila_usuario.iloc[0][col_ref_salida]) else ""
        marca_ref_retorno = str(fila_usuario.iloc[0][col_ref_retorno]).strip() if not pd.isna(fila_usuario.iloc[0][col_ref_retorno]) else ""
        marca_salida = str(fila_usuario.iloc[0][col_salida]).strip() if not pd.isna(fila_usuario.iloc[0][col_salida]) else ""

        # Inyección única de estilos para forzar las letras de todos los botones en negrita
        st.markdown("""
            <style>
            div[data-testid="stButton"] button div p {
                font-weight: bold !important;
            }
            </style>
        """, unsafe_allow_html=True)

        # =========================================================
        # PESTAÑA 1: PANEL DE MARCADO DIARIO (ADMIN Y ASESORES)
        # =========================================================
        with tab_marcado:
            st.write("")
            
            st.markdown("##### Verificación de Ubicación Requerida")
            st.markdown("<small style='color:gray;'>Haz clic en el botón de abajo para activar tu GPS e iniciar la verificación de rango.</small>", unsafe_allow_html=True)
            loc = streamlit_geolocation()
            
            ubicacion_valida = False
            
            if loc and loc['latitude'] is not None:
                lat_user = loc['latitude']
                lon_user = loc['longitude']
                distancia_km = calcular_distancia(lat_user, lon_user, LAT_OBJETIVO, LON_OBJETIVO)
                
                if distancia_km <= RADIO_MAX_KM:
                    ubicacion_valida = True
                    st.success(f"Ubicación confirmada. Te encuentras dentro del rango permitido ({distancia_km:.2f} km de la base).")
                else:
                    st.error(f"Acceso denegado. Estás fuera del rango permitido. Distancia actual: {distancia_km:.2f} km (Máximo permitido: {RADIO_MAX_KM} km).")
            else:
                st.warning("Por favor, pulsa el botón del GPS de arriba y otorga los permisos correspondientes en tu navegador web para continuar.")
            
            st.write("---")
            
            tiempo_peru_actual = obtener_hora_peru()
            hora_visualizacion = tiempo_peru_actual.strftime("%I:%M %p")
            
            # CASO 1: NO TIENE ENTRADA REGISTRADA
            if marca_entrada in ["Falta", "-", "", "nan", "None"]:
                st.info("Estado: Sin registro de ingreso hoy.")
                st.metric(label="Hora actual detectada para registro", value=hora_visualizacion)
                st.write("")
                
                if st.button("Registrar Entrada", use_container_width=True, disabled=not ubicacion_valida):
                    ahora_click = obtener_hora_peru()
                    hora_formateada = ahora_click.strftime("%I:%M %p")
                    df.loc[df["Usuario"] == st.session_state.usuario_actual, col_entrada] = hora_formateada
                    wks.clear()
                    set_with_dataframe(wks, df)
                    st.cache_data.clear()  # <-- LÍNEA NUEVA
                    st.success(f"Entrada registrada: {hora_formateada}")
                    st.session_state.autenticado = False
                    st.session_state.usuario_actual = ""
                    st.rerun()
                
                if st.button("Registrar Permiso", use_container_width=True):
                    df.loc[df["Usuario"] == st.session_state.usuario_actual, col_entrada] = "Permiso"
                    df.loc[df["Usuario"] == st.session_state.usuario_actual, col_ref_salida] = "Permiso"
                    df.loc[df["Usuario"] == st.session_state.usuario_actual, col_ref_retorno] = "Permiso"
                    df.loc[df["Usuario"] == st.session_state.usuario_actual, col_salida] = "Permiso"
                    wks.clear()
                    set_with_dataframe(wks, df)
                    st.cache_data.clear()  # <-- LÍNEA NUEVA
                    st.success("Permiso registrado.")
                    st.session_state.autenticado = False
                    st.session_state.usuario_actual = ""
                    st.rerun()
                    
            elif marca_entrada == "Permiso":
                st.info("Tu estado de hoy es: Permiso.")
                
            # CASO 2: JORNADA YA COMPLETADA TOTALMENTE
            elif marca_salida not in ["Falta", "-", "", "nan", "None"]:
                st.success(f"Jornada registrada.\nEntrada: {marca_entrada} | Ref: {marca_ref_salida} - {marca_ref_retorno} | Salida: {marca_salida}")
                
            # CASO 3: TIENE ENTRADA PERO NO TIENE SALIDA FINAL (Botones flexibles disponibles)
            else:
                st.warning(f"Ingreso registrado a las: {marca_entrada}")
                st.metric(label="Hora actual detectada para registro", value=hora_visualizacion)
                st.write("")
                
                if marca_ref_salida in ["Falta", "-", "", "nan", "None"]:
                    if st.button("Iniciar Refrigerio", use_container_width=True, disabled=not ubicacion_valida):
                        ahora_click = obtener_hora_peru()
                        hora_formateada = ahora_click.strftime("%I:%M %p")
                        df.loc[df["Usuario"] == st.session_state.usuario_actual, col_ref_salida] = hora_formateada
                        wks.clear()
                        set_with_dataframe(wks, df)
                        st.cache_data.clear()  # <-- LÍNEA NUEVA
                        st.success(f"Salida a refrigerio registrada: {hora_formateada}")
                        st.session_state.autenticado = False
                        st.session_state.usuario_actual = ""
                        st.rerun()
                elif marca_ref_retorno in ["Falta", "-", "", "nan", "None"]:
                    st.info(f"Saliste a almuerzo a las: {marca_ref_salida}")
                    if st.button("Terminar Refrigerio", use_container_width=True, disabled=not ubicacion_valida):
                        ahora_click = obtener_hora_peru()
                        hora_formateada = ahora_click.strftime("%I:%M %p")
                        df.loc[df["Usuario"] == st.session_state.usuario_actual, col_ref_retorno] = hora_formateada
                        wks.clear()
                        set_with_dataframe(wks, df)
                        st.cache_data.clear()  # <-- LÍNEA NUEVA
                        st.success(f"Retorno de refrigerio registrado: {hora_formateada}")
                        st.session_state.autenticado = False
                        st.session_state.usuario_actual = ""
                        st.rerun()
                else:
                    st.info(f"Refrigerio registrado: {marca_ref_salida} a {marca_ref_retorno}")
                
                st.write("")
                if st.button("Registrar Salida Final", use_container_width=True, disabled=not ubicacion_valida):
                    ahora_click = obtener_hora_peru()
                    hora_formateada = ahora_click.strftime("%I:%M %p")
                    df.loc[df["Usuario"] == st.session_state.usuario_actual, col_salida] = hora_formateada
                    wks.clear()
                    set_with_dataframe(wks, df)
                    st.cache_data.clear()  # <-- LÍNEA NUEVA
                    st.success(f"Salida registrada automáticamente: {hora_formateada}")
                    st.session_state.autenticado = False
                    st.session_state.usuario_actual = ""
                    st.rerun()

            # Historial propio estructurado
            st.write("")
            with st.container(): 
                with st.expander("Consultar mi historial"):
                    fecha_busqueda = st.date_input("Selecciona fecha:", value=obtener_hora_peru().date(), key="cal_asesor")
                    if fecha_busqueda:
                        fecha_formateada_busqueda = fecha_busqueda.strftime("%d/%m/%Y")
                        
                        # DINÁMICO: Detectamos qué pestaña del Sheets corresponde al mes de la fecha buscada
                        mes_busqueda_num = fecha_busqueda.month
                        pestana_busqueda = MESES_ESPANOL[mes_busqueda_num]
                        
                        # Conectamos y leemos la pestaña exacta seleccionada en el calendario
                        df_historial = cargar_datos_pestana(pestana_busqueda)
                        if not df_historial.empty and "Usuario" in df_historial.columns:
                            fila_usuario_historial = df_historial[df_historial["Usuario"] == st.session_state.usuario_actual]
                        else:
                            fila_usuario_historial = pd.DataFrame()

                        col_hist_ent = f"{fecha_formateada_busqueda} (Entrada)"
                        col_hist_ref_sal = f"{fecha_formateada_busqueda} (Inicio Ref)"
                        col_hist_ref_ret = f"{fecha_formateada_busqueda} (Fin Ref)"
                        col_hist_sal = f"{fecha_formateada_busqueda} (Salida)"
                        
                        if not fila_usuario_historial.empty and col_hist_ent in df_historial.columns and col_hist_sal in df_historial.columns:
                            val_ent = str(fila_usuario_historial.iloc[0][col_hist_ent]).strip()
                            val_r_sal = str(fila_usuario_historial.iloc[0][col_hist_ref_sal]).strip() if col_hist_ref_sal in df_historial.columns else ""
                            val_r_ret = str(fila_usuario_historial.iloc[0][col_hist_ref_ret]).strip() if col_hist_ref_ret in df_historial.columns else ""
                            val_sal = str(fila_usuario_historial.iloc[0][col_hist_sal]).strip()
                            
                            minutos_dia = calcular_minutos_netos_raw(val_ent, val_r_sal, val_r_ret, val_sal)
                            
                            df_individual = pd.DataFrame({
                                "Fecha": [fecha_formateada_busqueda],
                                "Entrada": [val_ent],
                                "Inicio Ref": [val_r_sal if val_r_sal != "" else "-"],
                                "Fin Ref": [val_r_ret if val_r_ret != "" else "-"],
                                "Salida": [val_sal],
                                "Horas Netas": [formatear_minutos_a_string(minutos_dia)]
                            })
                            st.dataframe(df_individual, use_container_width=True, hide_index=True)
                        else:
                            st.caption(f"Sin registros para esta fecha en la pestaña de {pestana_busqueda}.")
                        
                        # =========================================================
                        # CÁLCULO MENSUAL NETO EN FORMATO REAL H/MIN Y META INDIVIDUAL
                        # =========================================================
                        st.markdown("---")
                        st.markdown(f"##### Resumen Mensual ({pestana_busqueda})")
                        
                        total_minutos_mes = 0
                        if not fila_usuario_historial.empty:
                            for col in df_historial.columns:
                                if " (Entrada)" in col:
                                    col_base_fecha = col.replace(" (Entrada)", "")
                                    col_r_sal_par = f"{col_base_fecha} (Inicio Ref)"
                                    col_r_ret_par = f"{col_base_fecha} (Fin Ref)"
                                    col_salida_par = f"{col_base_fecha} (Salida)"
                                    
                                    if col_salida_par in df_historial.columns:
                                        v_e = str(fila_usuario_historial.iloc[0][col]).strip()
                                        v_rs = str(fila_usuario_historial.iloc[0][col_r_sal_par]).strip() if col_r_sal_par in df_historial.columns else ""
                                        v_rr = str(fila_usuario_historial.iloc[0][col_r_ret_par]).strip() if col_r_ret_par in df_historial.columns else ""
                                        v_s = str(fila_usuario_historial.iloc[0][col_salida_par]).strip()
                                        
                                        total_minutos_mes += calcular_minutos_netos_raw(v_e, v_rs, v_rr, v_s)
                        
                        string_acumulado_real = formatear_minutos_a_string(total_minutos_mes)
                        st.metric(label=f"Total neto acumulado en {pestana_busqueda.lower()}", value=string_acumulado_real)

                        # Lógica de barra de progreso basada en la columna 'Meta' de Google Sheets
                        if not fila_usuario_historial.empty and "Meta" in df_historial.columns:
                            try:
                                meta_horas = float(fila_usuario_historial.iloc[0]["Meta"])
                                if pd.isna(meta_horas) or meta_horas <= 0:
                                    meta_horas = 0
                            except ValueError:
                                meta_horas = 0
                            
                            if meta_horas > 0:
                                total_horas_mes = total_minutos_mes / 60.0
                                porcentaje_avance = min(1.0, total_horas_mes / meta_horas)
                                st.write("")
                                st.markdown(f"**Progreso de Meta Mensual: {porcentaje_avance*100:.1f}%** ({string_acumulado_real} / {meta_horas:.0f} h)")
                                st.progress(porcentaje_avance)
                                
                                minutos_restantes = int((meta_horas * 60) - total_minutos_mes)
                                if minutos_restantes > 0:
                                    st.caption(f"Faltan **{formatear_minutos_a_string(minutos_restantes)}** para cumplir tu meta del mes.")
                                else:
                                    st.success("¡Felicidades! Has completado tu meta de horas del mes.")
                        
                        # =========================================================
                        # CÁLCULO MENSUAL NETO EN FORMATO REAL H/MIN Y META INDIVIDUAL
                        # =========================================================
                        st.markdown("---")
                        st.markdown(f"##### Resumen Mensual ({pestana_busqueda})")
                        
                        total_minutos_mes = 0
                        if not fila_usuario_historial.empty:
                            for col in df_historial.columns:
                                if " (Entrada)" in col:
                                    col_base_fecha = col.replace(" (Entrada)", "")
                                    col_r_sal_par = f"{col_base_fecha} (Inicio Ref)"
                                    col_r_ret_par = f"{col_base_fecha} (Fin Ref)"
                                    col_salida_par = f"{col_base_fecha} (Salida)"
                                    
                                    if col_salida_par in df_historial.columns:
                                        v_e = str(fila_usuario_historial.iloc[0][col]).strip()
                                        v_rs = str(fila_usuario_historial.iloc[0][col_r_sal_par]).strip() if col_r_sal_par in df_historial.columns else ""
                                        v_rr = str(fila_usuario_historial.iloc[0][col_r_ret_par]).strip() if col_r_ret_par in df_historial.columns else ""
                                        v_s = str(fila_usuario_historial.iloc[0][col_salida_par]).strip()
                                        
                                        total_minutos_mes += calcular_minutos_netos_raw(v_e, v_rs, v_rr, v_s)
                        
                        string_acumulado_real = formatear_minutos_a_string(total_minutos_mes)
                        st.metric(label=f"Total neto acumulado en {pestana_busqueda.lower()}", value=string_acumulado_real)

                        # Lógica de barra de progreso basada en la columna 'Meta' de Google Sheets
                        if not fila_usuario_historial.empty and "Meta" in df_historial.columns:
                            try:
                                meta_horas = float(fila_usuario_historial.iloc[0]["Meta"])
                                if pd.isna(meta_horas) or meta_horas <= 0:
                                    meta_horas = 0
                            except ValueError:
                                meta_horas = 0
                            
                            if meta_horas > 0:
                                total_horas_mes = total_minutos_mes / 60.0
                                porcentaje_avance = min(1.0, total_horas_mes / meta_horas)
                                st.write("")
                                st.markdown(f"**Progreso de Meta Mensual: {porcentaje_avance*100:.1f}%** ({string_acumulado_real} / {meta_horas:.0f} h)")
                                st.progress(porcentaje_avance)
                                
                                minutos_restantes = int((meta_horas * 60) - total_minutos_mes)
                                if minutos_restantes > 0:
                                    st.caption(f"Faltan **{formatear_minutos_a_string(minutos_restantes)}** para cumplir tu meta del mes.")
                                else:
                                    st.success("¡Felicidades! Has completado tu meta de horas del mes.")

        # =========================================================
        # PESTAÑA NUEVA: REPORTE TIKTOK LIVE
        # =========================================================
        with tab_tiktok:
            st.write("")
            st.markdown("##### 📹 Cargar Captura de Historial TikTok Live")
            st.caption("Sube la captura de pantalla de tu historial de en vivos. La IA extraerá los rangos del día y calculará la duración total.")

            archivo_tt = st.file_uploader("Cargar captura de historial", type=["png", "jpg", "jpeg"], key="uploader_tiktok_historial")

            if archivo_tt is not None:
                bytes_tt = archivo_tt.getvalue()
                col_img_tt, col_info_tt = st.columns([1, 1.2])

                with col_img_tt:
                    st.image(bytes_tt, caption="Captura subida", use_container_width=True)

                with col_info_tt:
                    if "res_tiktok_data" not in st.session_state or st.session_state.get("nombre_archivo_tt_actual") != archivo_tt.name:
                        with st.spinner("Analizando historial y validando fechas con IA..."):
                            data_analisis = analizar_historial_tiktok(bytes_tt)
                            st.session_state.res_tiktok_data = data_analisis
                            st.session_state.nombre_archivo_tt_actual = archivo_tt.name

                    data_ia = st.session_state.res_tiktok_data

                    if not data_ia.get("valido", False):
                        st.error(f"❌ **Reporte rechazado:** {data_ia.get('motivo_error', 'Ocurrió un error al procesar la imagen.')}")
                        if st.button("🔄 Volver a Intentar", use_container_width=True):
                            st.session_state.pop("res_tiktok_data", None)
                            st.session_state.pop("nombre_archivo_tt_actual", None)
                            st.rerun()
                    else:
                        dia_detectado = str(data_ia.get("dia", "")).strip()
                        mes_detectado = str(data_ia.get("mes", "")).capitalize().strip()
                        transmisiones = data_ia.get("transmisiones", [])

                        st.success(f" Validado: **{len(transmisiones)} Live(s)** detectado(s) para el **{dia_detectado} de {mes_detectado}**.")
                        st.markdown("###### 🕒 Rangos de horas extraídos:")

                        total_minutos_tiktok = 0
                        for idx_live, live_item in enumerate(transmisiones, start=1):
                            i_live = live_item.get("inicio", "")
                            f_live = live_item.get("fin", "")
                            dur_min = calcular_duracion_rango_tiktok(i_live, f_live)
                            total_minutos_tiktok += dur_min
                            
                            hrs_l = dur_min // 60
                            mins_l = dur_min % 60
                            str_dur = f"{hrs_l}h {mins_l}m" if hrs_l > 0 else f"{mins_l} min"
                            st.write(f"• **Live {idx_live}:** {i_live} - {f_live} (`{str_dur}`)")

                        total_formateado_tt = formatear_minutos_a_string(total_minutos_tiktok)
                        st.markdown("---")
                        st.metric(label="⏱️ Tiempo Total Transmitido", value=total_formateado_tt)

                        st.write("¿Los datos mostrados son correctos?")
                        col_subir_tt, col_repetir_tt = st.columns(2)

                        with col_subir_tt:
                            if st.button("✅ Subir Reporte", use_container_width=True):
                                with st.spinner("Guardando reporte en REPORTES TIKTOK..."):
                                    try:
                                        doc_tiktok = gc.open("REPORTES TIKTOK")
                                        pestana_mes_tt = MESES_ESPANOL[obtener_hora_peru().month]

                                        try:
                                            wks_tt = doc_tiktok.worksheet(pestana_mes_tt)
                                        except Exception:
                                            wks_tt = doc_tiktok.add_worksheet(title=pestana_mes_tt, rows="100", cols="20")

                                        df_tt = get_as_dataframe(wks_tt).dropna(how="all")
                                        if df_tt.empty or "Usuario" not in df_tt.columns:
                                            df_tt = pd.DataFrame(columns=["Usuario", "Codigo", "Meta"])

                                        # Formato fecha columna: DD/MM/YYYY
                                        anio_actual = obtener_hora_peru().strftime("%Y")
                                        mes_num_str = obtener_hora_peru().strftime("%m")
                                        col_fecha_tt = f"{dia_detectado.zfill(2)}/{mes_num_str}/{anio_actual}"

                                        # Nos aseguramos de que existan las columnas fijas
                                        for c_fija in ["Usuario", "Codigo", "Meta"]:
                                            if c_fija not in df_tt.columns:
                                                df_tt[c_fija] = ""

                                        # Asegurar columna de fecha
                                        if col_fecha_tt not in df_tt.columns:
                                            df_tt[col_fecha_tt] = ""

                                        # Si el usuario no existe en la hoja de REPORTES TIKTOK, lo agregamos
                                        usr_act = st.session_state.usuario_actual
                                        cod_act = st.session_state.get("codigo_actual", "")

                                        if usr_act not in df_tt["Usuario"].values:
                                            nueva_fila = {"Usuario": usr_act, "Codigo": cod_act, "Meta": "0"}
                                            df_tt = pd.concat([df_tt, pd.DataFrame([nueva_fila])], ignore_index=True)

                                        # Asignar el valor acumulado a la celda
                                        df_tt.loc[df_tt["Usuario"] == usr_act, col_fecha_tt] = total_formateado_tt

                                        wks_tt.clear()
                                        set_with_dataframe(wks_tt, df_tt, resize=True)
                                        st.cache_data.clear()

                                        st.balloons()
                                        st.success(f" Reporte de **{total_formateado_tt}** guardado con éxito para el día {col_fecha_tt}.")
                                        st.session_state.pop("res_tiktok_data", None)
                                        st.session_state.pop("nombre_archivo_tt_actual", None)
                                        st.rerun()

                                    except Exception as ex_tt:
                                        st.error(f"Error al guardar en 'REPORTES TIKTOK': {ex_tt}")

                        with col_repetir_tt:
                            if st.button("🔄 Volver a Subir", use_container_width=True):
                                st.session_state.pop("res_tiktok_data", None)
                                st.session_state.pop("nombre_archivo_tt_actual", None)
                                st.rerun()

        # =========================================================
        # PESTAÑA 2: REPORTE GENERAL (VISIBLE PARA EL ADMIN CON REFRIGERIO)
        # =========================================================
        if es_admin:
            with tab_reporte:
                st.write("")
                st.markdown("##### Filtro de Asistencia General")
                fecha_busqueda_admin = st.date_input("Fecha a consultar:", value=obtener_hora_peru().date(), key="cal_admin")
                
                if fecha_busqueda_admin:
                    fecha_formateada_busqueda = fecha_busqueda_admin.strftime("%d/%m/%Y")
                    col_hist_ent = f"{fecha_formateada_busqueda} (Entrada)"
                    col_hist_ref_sal = f"{fecha_formateada_busqueda} (Inicio Ref)"
                    col_hist_ref_ret = f"{fecha_formateada_busqueda} (Fin Ref)"
                    col_hist_sal = f"{fecha_formateada_busqueda} (Salida)"
                    
                    # DINÁMICO: Cargamos los datos de la pestaña correspondiente para el Administrador
                    # DINÁMICO: Cargamos los datos de la pestaña correspondiente usando la caché
                    mes_admin_num = fecha_busqueda_admin.month
                    pestana_admin = MESES_ESPANOL[mes_admin_num]
                    
                    df_admin = cargar_datos_pestana(pestana_admin)
                    
                    if not df_admin.empty:
                        # Vistas separadas para Diario y Mensual
                        subtab_diario, subtab_mensual = st.tabs(["Reporte Diario", "Total Acumulado del Mes"])
                        
                        # --- SUBPESTAÑA 1: REPORTE DIARIO ORIGINAL ---
                        with subtab_diario:
                            if col_hist_ent in df_admin.columns and col_hist_sal in df_admin.columns:
                                df_reporte_raw = []
                                for idx, row in df_admin.iterrows():
                                    v_e = str(row[col_hist_ent]).strip() if col_hist_ent in df_admin.columns else "Falta"
                                    v_rs = str(row[col_hist_ref_sal]).strip() if col_hist_ref_sal in df_admin.columns else "Falta"
                                    v_rr = str(row[col_hist_ref_ret]).strip() if col_hist_ref_ret in df_admin.columns else "Falta"
                                    v_s = str(row[col_hist_sal]).strip() if col_hist_sal in df_admin.columns else "Falta"
                                    
                                    minutos_totales = calcular_minutos_netos_raw(v_e, v_rs, v_rr, v_s)
                                    horas_netas_str = formatear_minutos_a_string(minutos_totales) if minutos_totales > 0 else "0 h 0 min"
                                    
                                    meta_individual = str(row["Meta"]).split('.')[0].strip() if "Meta" in df_admin.columns and not pd.isna(row["Meta"]) else "-"
                                    
                                    df_reporte_raw.append({
                                        "Asesor": row["Usuario"],
                                        "Meta (H)": meta_individual,
                                        "Entrada": v_e,
                                        "Inicio Ref": v_rs,
                                        "Fin Ref": v_rr,
                                        "Salida": v_s,
                                        "Horas Netas": horas_netas_str
                                    })
                                    
                                df_reporte_final = pd.DataFrame(df_reporte_raw)
                                st.dataframe(df_reporte_final, use_container_width=True, hide_index=True)
                            else:
                                st.caption(f"No hay registros específicos de entrada/salida para el {fecha_formateada_busqueda} en la pestaña {pestana_admin}.")

                        # --- SUBPESTAÑA 2: REPORTE TOTAL DEL MES DE TODOS LOS TRABAJADORES ---
                        with subtab_mensual:
                            st.markdown(f"###### Resumen Consolidado de Horas - {pestana_admin}")
                            df_mensual_admin = []
                            
                            # Identificamos todas las columnas de entrada en la hoja del mes
                            cols_entrada_mes = [c for c in df_admin.columns if " (Entrada)" in c]
                            
                            for idx, row in df_admin.iterrows():
                                asesor_nombre = row["Usuario"]
                                total_minutos_asesor = 0
                                dias_trabajados = 0
                                
                                # Iteramos por cada día registrado en el mes para este asesor
                                for col_ent in cols_entrada_mes:
                                    col_base = col_ent.replace(" (Entrada)", "")
                                    c_rs = f"{col_base} (Inicio Ref)"
                                    c_rr = f"{col_base} (Fin Ref)"
                                    c_sal = f"{col_base} (Salida)"
                                    
                                    if c_sal in df_admin.columns:
                                        val_e = str(row[col_ent]).strip()
                                        val_rs = str(row[c_rs]).strip() if c_rs in df_admin.columns else ""
                                        val_rr = str(row[c_rr]).strip() if c_rr in df_admin.columns else ""
                                        val_s = str(row[c_sal]).strip()
                                        
                                        min_dia = calcular_minutos_netos_raw(val_e, val_rs, val_rr, val_s)
                                        if min_dia > 0:
                                            total_minutos_asesor += min_dia
                                            dias_trabajados += 1
                                
                                # Lectura y cálculo de meta
                                meta_val = 0
                                if "Meta" in df_admin.columns and not pd.isna(row["Meta"]):
                                    try:
                                        meta_val = float(str(row["Meta"]).strip())
                                    except ValueError:
                                        meta_val = 0
                                
                                total_horas_num = total_minutos_asesor / 60.0
                                porcentaje_cumplimiento = f"{(total_horas_num / meta_val * 100):.1f}%" if meta_val > 0 else "N/A"
                                
                                df_mensual_admin.append({
                                    "Asesor / Trabajador": asesor_nombre,
                                    "Días Asistidos": dias_trabajados,
                                    "Horas Totales Mes": formatear_minutos_a_string(total_minutos_asesor),
                                    "Meta Mes (H)": f"{meta_val:.0f} h" if meta_val > 0 else "-",
                                    "% Cumplimiento": porcentaje_cumplimiento
                                })
                            
                            df_resumen_mes_final = pd.DataFrame(df_mensual_admin)
                            st.dataframe(df_resumen_mes_final, use_container_width=True, hide_index=True)

                    else:
                        st.caption(f"No hay datos registrados en la pestaña de {pestana_admin}.")

        # Botón para salir de la app
        st.write("")
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state.autenticado = False
            st.session_state.usuario_actual = ""
            st.rerun()

except Exception as e:
    st.error("Error de conexión con la base de datos.")
    st.code(str(e))
