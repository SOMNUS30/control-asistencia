import streamlit as st
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import pandas as pd
from datetime import datetime
import math
from streamlit_geolocation import streamlit_geolocation

# Coordenadas del punto central requerido (Ica, Perú)
LAT_OBJETIVO = -14.0639
LON_OBJETIVO = -75.7292
RADIO_MAX_KM = 2.0

# Formula de Haversine para calcular distancia entre dos coordenadas (Lat/Lon)
def calcular_distancia(lat1, lon1, lat2, lon2):
    rad = math.pi / 180
    dlat = (lat2 - lat1) * rad
    dlon = (lon2 - lon1) * rad
    a = math.sin(dlat/2)**2 + math.cos(lat1*rad) * math.cos(lat2*rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return 6371.0 * c  # Retorna la distancia en kilómetros

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
    
    # Detectar el mes actual automáticamente
    mes_actual_num = datetime.now().month
    nombre_pestana = MESES_ESPANOL[mes_actual_num]
    
    wks = hoja_calculo.worksheet(nombre_pestana)
    df = get_as_dataframe(wks).dropna(how="all").dropna(axis=1, how="all")
    
    # =========================================================
    # AUTOMATIZACIÓN DE FALTAS DIARIAS
    # =========================================================
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    col_entrada = f"{fecha_hoy} (Entrada)"
    col_salida = f"{fecha_hoy} (Salida)"
    
    cambio_estructura = False
    
    if col_entrada not in df.columns:
        df[col_entrada] = "Falta"
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
        # Espacio superior para centrar verticalmente la tarjeta
        st.write("")
        st.write("")
        
        # Columnas para encuadrar el login en un rectángulo vertical centrado (Formato Tarjeta)
        col_izq, col_centro, col_der = st.columns([1, 1.6, 1])
        
        with col_centro:
            with st.container(border=True):
                st.markdown("<h2 style='text-align: center; margin-bottom: 5px; font-size: 24px;'>Control de Asistencia</h2>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: gray; font-size: 13px; margin-bottom: 25px;'>Introduce tus credenciales de acceso.</p>", unsafe_allow_html=True)
                
                codigo_ingresado = st.text_input("Código de Asesor", type="password")
                
                st.write("") 
                
                if st.button("Iniciar Sesión", use_container_width=True):
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
        
        # Unificación de la estructura de pestañas para evitar errores de renderizado del Administrador
        if es_admin:
            st.caption(f"Usuario: {st.session_state.usuario_actual} (Administrador)")
            tab_marcado, tab_reporte = st.tabs(["Mi Marcado", "Reporte General"])
        else:
            st.caption(f"Usuario: {st.session_state.usuario_actual}")
            tab_marcado, = st.tabs(["Mi Marcado"])

        fila_usuario = df[df["Usuario"] == st.session_state.usuario_actual]
        
        # Lectura segura y limpia de los estados de las celdas
        marca_entrada = str(fila_usuario.iloc[0][col_entrada]).strip() if not pd.isna(fila_usuario.iloc[0][col_entrada]) else ""
        marca_salida = str(fila_usuario.iloc[0][col_salida]).strip() if not pd.isna(fila_usuario.iloc[0][col_salida]) else ""

        # =========================================================
        # CÁLCULO DE HORA ACTUAL AUTOMÁTICA EN FORMATO 12 HORAS
        # =========================================================
        ahora = datetime.now()
        hora_24 = ahora.hour
        minuto_actual = ahora.minute

        periodo_actual_idx = 1 if hora_24 >= 12 else 0
        hora_12 = hora_24 % 12
        if hora_12 == 0:
            hora_12 = 12
            
        idx_hora = hora_12 - 1
        idx_minuto = minuto_actual
        # =========================================================

        # =========================================================
        # PESTAÑA 1: PANEL DE MARCADO DIARIO (ADMIN Y ASESORES)
        # =========================================================
        with tab_marcado:
            st.write("")
            
            # Verificación interactiva de ubicación por GPS usando el navegador movil o pc
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
            
            if marca_entrada in ["Falta", "-", "", "nan", "None"]:
                st.info("Estado: Sin registro de ingreso hoy.")
                st.markdown("Selecciona tu hora de Entrada:")
                
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1:
                    h_ent = st.selectbox("Hora", [f"{i:02d}" for i in range(1, 13)], index=idx_hora, key="sel_h_ent")
                with c2:
                    m_ent = st.selectbox("Minuto", [f"{i:02d}" for i in range(0, 60)], index=idx_minuto, key="sel_m_ent")
                with c3:
                    p_ent = st.selectbox("Periodo", ["AM", "PM"], index=periodo_actual_idx, key="sel_p_ent")
                
                st.write("")
                
                # Botón condicionado a la geocerca de 2 km
                if st.button("Registrar Entrada", use_container_width=True, disabled=not ubicacion_valida):
                    hora_formateada = f"{h_ent}:{m_ent} {p_ent}"
                    df.loc[df["Usuario"] == st.session_state.usuario_actual, col_entrada] = hora_formateada
                    wks.clear()
                    set_with_dataframe(wks, df)
                    st.success(f"Entrada registrada: {hora_formateada}")
                    st.session_state.autenticado = False
                    st.session_state.usuario_actual = ""
                    st.rerun()
                
                if st.button("Registrar Permiso", use_container_width=True):
                    df.loc[df["Usuario"] == st.session_state.usuario_actual, col_entrada] = "Permiso"
                    df.loc[df["Usuario"] == st.session_state.usuario_actual, col_salida] = "Permiso"
                    wks.clear()
                    set_with_dataframe(wks, df)
                    st.success("Permiso registrado.")
                    st.session_state.autenticado = False
                    st.session_state.usuario_actual = ""
                    st.rerun()
                    
            elif marca_salida in ["Falta", "-", "", "nan", "None"]:
                if marca_entrada == "Permiso":
                    st.info("Tu estado de hoy es: Permiso.")
                else:
                    st.warning(f"Entrada registrada hoy a las: {marca_entrada}")
                    st.markdown("Selecciona tu hora de Salida:")
                    
                    c1, c2, c3 = st.columns([1, 1, 1])
                    with c1:
                        h_sal = st.selectbox("Hora", [f"{i:02d}" for i in range(1, 13)], index=idx_hora, key="sel_h_sal")
                    with c2:
                        m_sal = st.selectbox("Minuto", [f"{i:02d}" for i in range(0, 60)], index=idx_minuto, key="sel_m_sal")
                    with c3:
                        p_sal = st.selectbox("Periodo", ["AM", "PM"], index=periodo_actual_idx, key="sel_p_sal")
                    
                    st.write("")
                    
                    # Botón condicionado a la geocerca de 2 km
                    if st.button("Registrar Salida", use_container_width=True, disabled=not ubicacion_valida):
                        hora_formateada = f"{h_sal}:{m_sal} {p_sal}"
                        df.loc[df["Usuario"] == st.session_state.usuario_actual, col_salida] = hora_formateada
                        wks.clear()
                        set_with_dataframe(wks, df)
                        st.success(f"Salida registrada: {hora_formateada}")
                        st.session_state.autenticado = False
                        st.session_state.usuario_actual = ""
                        st.rerun()
            else:
                st.success(f"Jornada registrada.\nEntrada: {marca_entrada} | Salida: {marca_salida}")

            # Historial propio estructurado en una tabla limpia
            st.write("")
            with st.expander("Consultar mi historial"):
                fecha_busqueda = st.date_input("Selecciona fecha:", value=datetime.now().date(), key="cal_asesor")
                if fecha_busqueda:
                    fecha_formateada_busqueda = fecha_busqueda.strftime("%d/%m/%Y")
                    col_hist_ent = f"{fecha_formateada_busqueda} (Entrada)"
                    col_hist_sal = f"{fecha_formateada_busqueda} (Salida)"
                    
                    if col_hist_ent in df.columns and col_hist_sal in df.columns:
                        val_ent = fila_usuario.iloc[0][col_hist_ent]
                        val_sal = fila_usuario.iloc[0][col_hist_sal]
                        
                        df_individual = pd.DataFrame({
                            "Usuario": [st.session_state.usuario_actual],
                            "Entrada": [val_ent],
                            "Salida": [val_sal]
                        })
                        st.dataframe(df_individual, use_container_width=True, hide_index=True)
                    else:
                        st.caption("Sin registros para esta fecha.")

        # =========================================================
        # PESTAÑA 2: REPORTE GENERAL (SOLO VISIBLE PARA EL ADMIN)
        # =========================================================
        if es_admin:
            with tab_reporte:
                st.write("")
                st.markdown("##### Filtro de Asistencia General")
                fecha_busqueda_admin = st.date_input("Fecha a consultar:", value=datetime.now().date(), key="cal_admin")
                
                if fecha_busqueda_admin:
                    fecha_formateada_busqueda = fecha_busqueda_admin.strftime("%d/%m/%Y")
                    col_hist_ent = f"{fecha_formateada_busqueda} (Entrada)"
                    col_hist_sal = f"{fecha_formateada_busqueda} (Salida)"
                    
                    if col_hist_ent in df.columns and col_hist_sal in df.columns:
                        df_reporte = df[["Usuario", col_hist_ent, col_hist_sal]].copy()
                        df_reporte.columns = ["Asesor", "Entrada", "Salida"]
                        
                        st.dataframe(df_reporte, use_container_width=True, hide_index=True)
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
