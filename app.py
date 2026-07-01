import streamlit as st
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import pandas as pd
from datetime import datetime, timedelta
import math
from streamlit_geolocation import streamlit_geolocation

# Coordenadas del punto central requerido (Ica, Perú)
LAT_OBJETIVO = -14.0780018
LON_OBJETIVO = -75.7399245
RADIO_MAX_KM = 1.0

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
    
    # Detectar el mes actual automáticamente basándose en la hora de Perú
    hora_peru_actual = obtener_hora_peru()
    mes_actual_num = hora_peru_actual.month
    nombre_pestana = MESES_ESPANOL[mes_actual_num]
    
    wks = hoja_calculo.worksheet(nombre_pestana)
    df = get_as_dataframe(wks).dropna(how="all").dropna(axis=1, how="all")
    
    # =========================================================
    # AUTOMATIZACIÓN DE FALTAS DIARIAS CON REFRIGERIO (Hora de Perú)
    # =========================================================
    fecha_hoy = hora_peru_actual.strftime("%d/%m/%Y")
    col_entrada = f"{fecha_hoy} (Entrada)"
    col_ref_salida = f"{fecha_hoy} (Inicio Ref)"
    col_ref_retorno = f"{fecha_hoy} (Fin Ref)"
    col_salida = f"{fecha_hoy} (Salida)"
    
    cambio_estructura = False
    
    if col_entrada not in df.columns:
        df[col_entrada] = "Falta"
        cambio_estructura = True
    if col_ref_salida not in df.columns:
        df[col_ref_salida] = "Falta"
        cambio_estructura = True
    if col_ref_retorno not in df.columns:
        df[col_ref_retorno] = "Falta"
        cambio_estructura = True
    if col_salida not in df.columns:
        df[col_salida] = "Falta"
        cambio_estructura = True
        
    if cambio_estructura:
        wks.clear()
        set_with_dataframe(wks, df)
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

            /* --- CONFIGURACIÓN PARA COMPUTADORA (PC) --- */
            @media (min-width: 769px) {
                /* Forzar la fila contenedora para que actue como el diseño dividido */
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
                /* Panel Izquierdo Decorativo Azul con Ondas */
                div[data-testid="stHorizontalBlock"] > div:nth-child(1) {
                    background: linear-gradient(135deg, #4fa8fb 0%, #3b5998 100%) !important;
                    display: flex !important;
                    flex-direction: column !important;
                    justify-content: center !important;
                    align-items: center !important;
                    padding: 40px !important;
                    position: relative !important;
                }
                /* Añadir el efecto de curvas/ondas sutiles en el panel azul */
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
                /* Panel Derecho Blanco (Formulario de credenciales) */
                div[data-testid="stHorizontalBlock"] > div:nth-child(2) {
                    background-color: #ffffff !important;
                    padding: 45px 35px !important;
                    display: flex !important;
                    flex-direction: column !important;
                    justify-content: center !important;
                }
                /* Eliminar el contenedor interno redundante en PC */
                div[data-testid="stVerticalBlock"] > div:has(div[class*="stTextInput"]) {
                    background: transparent !important;
                    box-shadow: none !important;
                    padding: 0 !important;
                    border: none !important;
                }
                /* Insertar dinámicamente el isotipo de la marca en el lado azul de PC */
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

            /* --- CONFIGURACIÓN PARA CELULAR (MÓVIL) --- */
            @media (max-width: 768px) {
                /* Caja vertical fluida */
                div[data-testid="stHorizontalBlock"] {
                    display: flex !important;
                    flex-direction: column !important;
                    gap: 0 !important;
                    padding: 0 !important;
                }
                /* El bloque 1 se convierte en la cabecera curva superior azul del celular */
                div[data-testid="stHorizontalBlock"] > div:nth-child(1) {
                    background: linear-gradient(135deg, #4fa8fb 0%, #3b5998 100%) !important;
                    padding: 50px 20px !important;
                    text-align: center !important;
                    border-radius: 0 0 40px 40px !important;
                    box-shadow: 0px 8px 20px rgba(0, 0, 0, 0.1) !important;
                }
                /* Estilización de la tarjeta del login inferior que aloja los inputs en el celular */
                div[data-testid="stVerticalBlock"] > div:has(div[class*="stTextInput"]) {
                    background-color: #ffffff !important;
                    border-radius: 24px !important;
                    box-shadow: 0px 10px 25px rgba(0, 0, 0, 0.04) !important;
                    padding: 35px 24px !important;
                    border: 1px solid #e1e4e8 !important;
                    margin-top: 25px !important;
                }
            }

            /* --- ELEMENTOS COMUNES DE CAMPOS Y ENTRADAS (AMBOS MODELOS) --- */
            /* Inputs estilizados con bordes redondeados y tono suave */
            div[data-testid="stTextInput"] input {
                border-radius: 14px !important;
                border: 1px solid #c2c9d1 !important;
                padding: 12px !important;
                font-size: 16px !important;
                background-color: #f9fbfd !important;
                transition: border-color 0.2s, box-shadow 0.2s !important;
            }
            div[data-testid="stTextInput"] input:focus {
                border-color: #3b5998 !important;
                box-shadow: 0 0 0 3px rgba(59, 89, 152, 0.15) !important;
            }
            /* Botón de envío imponente con esquinas redondeadas y relleno completo */
            div[data-testid="stButton"] button {
                background-color: #3b5998 !important;
                color: white !important;
                border-radius: 14px !important;
                padding: 14px 24px !important;
                border: none !important;
                font-size: 16px !important;
                font-weight: bold !important;
                letter-spacing: 0.5px !important;
                box-shadow: 0px 4px 12px rgba(59, 89, 152, 0.25) !important;
                transition: background-color 0.2s, transform 0.1s !important;
            }
            div[data-testid="stButton"] button:hover {
                background-color: #2d4373 !important;
            }
            div[data-testid="stButton"] button:active {
                transform: scale(0.98) !important;
            }
            </style>
        """, unsafe_allow_html=True)

        # Contenedor estructural nativo reorganizado mediante las reglas CSS superiores
        col_izq, col_centro = st.columns([1, 1.2])
        
        with col_izq:
            # En PC este bloque aloja el texto decorativo blanco. En celular opera como la cabecera superior.
            st.markdown("<h1 style='text-align: center; color: white; font-size: 28px; font-weight: 800; margin: 0;'>Welcome</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: rgba(255,255,255,0.85); font-size: 14px; margin-top: 5px;'>Login to your account to continue</p>", unsafe_allow_html=True)

        with col_centro:
            with st.container():
                st.markdown("<h2 style='text-align: center; margin-bottom: 5px; font-size: 24px; color: #2f3542; font-weight: bold;'>Consulta de Trabajador</h2>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: #747d8c; font-size: 13px; margin-bottom: 25px;'>Introduce tus credenciales de acceso.</p>", unsafe_allow_html=True)
                
                codigo_ingresado = st.text_input("DNI / Código de Asesor", type="password")
                
                st.write("") 
                
                if st.button("CONSULTAR TODO", use_container_width=True):
                    df["Codigo"] = df["Codigo"].astype(str).str.split('.').str[0].str.strip()
                    codigo_ingresado = str(codigo_ingresado).strip()
                    
                    usuario_encontrado = df[df["Codigo"] == codigo_ingresado]
                    
                    if not usuario_encontrado.empty:
                        st.session_state.autenticado = True
                        st.session_state.usuario_actual = usuario_encontrado.iloc[0]["Usuario"]
                        st.rerun()
                    else:
                        st.error("Código incorrecto. Intente de nuevo.")
    else:
        st.markdown(f"<h3 style='margin-bottom:0px;'>Control de Asistencia</h3>", unsafe_allow_html=True)
        
        es_admin = (st.session_state.usuario_actual == "VALENTIN ISASI")
        
        if es_admin:
            st.caption(f"Usuario: {st.session_state.usuario_actual} (Administrador)")
            tab_marcado, tab_reporte = st.tabs(["Mi Marcado", "Reporte General"])
        else:
            st.caption(f"Usuario: {st.session_state.usuario_actual}")
            tab_marcado, = st.tabs(["Mi Marcado"])

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
                    st.success(f"Salida registrada automáticamente: {hora_formateada}")
                    st.session_state.autenticado = False
                    st.session_state.usuario_actual = ""
                    st.rerun()

            # Historial propio estructurado
            st.write("")
            with st.expander("Consultar mi historial"):
                fecha_busqueda = st.date_input("Selecciona fecha:", value=obtener_hora_peru().date(), key="cal_asesor")
                if fecha_busqueda:
                    fecha_formateada_busqueda = fecha_busqueda.strftime("%d/%m/%Y")
                    col_hist_ent = f"{fecha_formateada_busqueda} (Entrada)"
                    col_hist_ref_sal = f"{fecha_formateada_busqueda} (Inicio Ref)"
                    col_hist_ref_ret = f"{fecha_formateada_busqueda} (Fin Ref)"
                    col_hist_sal = f"{fecha_formateada_busqueda} (Salida)"
                    
                    if col_hist_ent in df.columns and col_hist_sal in df.columns:
                        val_ent = str(fila_usuario.iloc[0][col_hist_ent]).strip()
                        val_r_sal = str(fila_usuario.iloc[0][col_hist_ref_sal]).strip() if col_hist_ref_sal in df.columns else ""
                        val_r_ret = str(fila_usuario.iloc[0][col_hist_ref_ret]).strip() if col_hist_ref_ret in df.columns else ""
                        val_sal = str(fila_usuario.iloc[0][col_hist_sal]).strip()
                        
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
                        st.caption("Sin registros para esta fecha específica.")
                    
                    # =========================================================
                    # CÁLCULO MENSUAL NETO EN FORMATO REAL H/MIN Y META INDIVIDUAL
                    # =========================================================
                    st.markdown("---")
                    st.markdown(f"##### Resumen Mensual ({nombre_pestana})")
                    
                    total_minutos_mes = 0
                    for col in df.columns:
                        if " (Entrada)" in col:
                            col_base_fecha = col.replace(" (Entrada)", "")
                            col_r_sal_par = f"{col_base_fecha} (Inicio Ref)"
                            col_r_ret_par = f"{col_base_fecha} (Fin Ref)"
                            col_salida_par = f"{col_base_fecha} (Salida)"
                            
                            if col_salida_par in df.columns:
                                v_e = str(fila_usuario.iloc[0][col]).strip()
                                v_rs = str(fila_usuario.iloc[0][col_r_sal_par]).strip() if col_r_sal_par in df.columns else ""
                                v_rr = str(fila_usuario.iloc[0][col_r_ret_par]).strip() if col_r_ret_par in df.columns else ""
                                v_s = str(fila_usuario.iloc[0][col_salida_par]).strip()
                                
                                total_minutos_mes += calcular_minutos_netos_raw(v_e, v_rs, v_rr, v_s)
                    
                    string_acumulado_real = formatear_minutos_a_string(total_minutos_mes)
                    st.metric(label="Total neto acumulado en el mes", value=string_acumulado_real)

                    # Lógica de barra de progreso basada en la columna 'Meta' de Google Sheets
                    if "Meta" in df.columns:
                        try:
                            meta_horas = float(fila_usuario.iloc[0]["Meta"])
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
                    
                    if col_hist_ent in df.columns and col_hist_sal in df.columns:
                        df_reporte_raw = []
                        for idx, row in df.iterrows():
                            v_e = str(row[col_hist_ent]).strip() if col_hist_ent in df.columns else "Falta"
                            v_rs = str(row[col_hist_ref_sal]).strip() if col_hist_ref_sal in df.columns else "Falta"
                            v_rr = str(row[col_hist_ref_ret]).strip() if col_hist_ref_ret in df.columns else "Falta"
                            v_s = str(row[col_hist_sal]).strip() if col_hist_sal in df.columns else "Falta"
                            
                            minutos_totales = calcular_minutos_netos_raw(v_e, v_rs, v_rr, v_s)
                            horas_netas_str = formatear_minutos_a_string(minutos_totales) if minutos_totales > 0 else "0 h 0 min"
                            
                            # Lectura limpia del valor de la Meta por cada fila
                            meta_individual = str(row["Meta"]).split('.')[0].strip() if "Meta" in df.columns and not pd.isna(row["Meta"]) else "-"
                            
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
                        st.caption(f"No hay datos registrados para el {fecha_formateada_busqueda}.")

        # Botón para salir de la app
        st.write("")
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state.autenticado = False
            st.session_state.usuario_actual = ""
            st.rerun()

except Exception as e:
    st.error("Error de conexión con la base de datos.")
    st.code(str(e))
