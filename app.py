import streamlit as st
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import pandas as pd
from datetime import datetime, timedelta, timezone
import calendar
import math
import io
import json
import base64
import urllib.request
from PIL import Image

# Importación segura de geolocalización con soporte para reseteo dinámico
try:
    from streamlit_geolocation import _streamlit_geolocation
    def obtener_geolocalizacion(clave_dinamica=0):
        return _streamlit_geolocation(key=f"geo_loc_{clave_dinamica}", default={'latitude': None, 'longitude': None})
except Exception:
    import streamlit_geolocation as _sg
    def obtener_geolocalizacion(clave_dinamica=0):
        return _sg.streamlit_geolocation()

# Importación segura de Google GenAI (compatible tanto local como en la nube)
try:
    from google import genai
except ImportError:
    genai = None

# Importación segura de Google Drive API
try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    drive_api_disponible = True
except ImportError:
    drive_api_disponible = False

# =========================================================
# CONFIGURACIÓN DE PÁGINA Y CONSTANTES
# =========================================================
st.set_page_config(
    page_title="Control de Asistencia & TikTok Live",
    page_icon="⏱️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Coordenadas del punto central requerido (Ica, Perú)
LAT_OBJETIVO = -14.0780018
LON_OBJETIVO = -75.7399245
RADIO_MAX_KM = 0.5

# Diccionario para convertir el mes del año a mayúsculas en español
MESES_ESPANOL = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL", 
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO", 
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
}

DIAS_SEMANA_ESPANOL = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"
}

MESES_TEXTO_A_NUM = {
    "ene": 1, "enero": 1, "feb": 2, "febrero": 2,
    "mar": 3, "marzo": 3, "abr": 4, "abril": 4,
    "may": 5, "mayo": 5, "jun": 6, "junio": 6,
    "jul": 7, "julio": 7, "ago": 8, "agosto": 8,
    "sep": 9, "septiembre": 9, "setiembre": 9,
    "oct": 10, "octubre": 10, "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12
}

# =========================================================
# ESTILOS CSS BLINDADOS (CORRECCIÓN TOTAL MODO OSCURO / CLARO)
# =========================================================
def inyectar_estilos():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

        /* 1. FORZADO GLOBAL DE TEMA CLARO Y ALTO CONTRASTE */
        :root, html, body, .stApp {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
            background-color: #f8fafc !important;
            color: #0f172a !important;
        }

        /* Ancho de contenedor agradable */
        .block-container {
            max-width: 1040px !important;
            padding-top: 1.2rem !important;
            padding-bottom: 3rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            background-color: transparent !important;
        }

        /* Ocultar elementos nativos innecesarios de Streamlit */
        header[data-testid="stHeader"] {
            background: transparent !important;
            display: none !important;
        }
        #MainMenu, footer {
            visibility: hidden !important;
        }

        /* 2. PROTECCIÓN CONTRA LETRAS INVISIBLES EN DISPOSITIVOS CON MODO OSCURO */
        p, span, div, h1, h2, h3, h4, h5, h6, strong, b, em, label {
            color: #0f172a !important;
        }
        
        .stMarkdown, .stMarkdown * {
            color: #1e293b !important;
        }

        .stCaption, [data-testid="stCaptionContainer"], small {
            color: #64748b !important;
        }

        /* 3. INPUTS Y FORMULARIOS BLINDADOS (FONDO BLANCO Y TEXTO NEGRO) */
        input, textarea, select {
            background-color: #ffffff !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            border-color: #cbd5e1 !important;
        }
        div[data-baseweb="base-input"], div[data-baseweb="input"] {
            background-color: #ffffff !important;
            border: 1.5px solid #cbd5e1 !important;
            border-radius: 10px !important;
        }
        div[data-baseweb="input"] input {
            background-color: transparent !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
        }
        div[data-baseweb="input"] input::placeholder {
            color: #94a3b8 !important;
            -webkit-text-fill-color: #94a3b8 !important;
        }

        /* Calendario emergente de Streamlit */
        div[data-baseweb="popover"], div[data-baseweb="calendar"] {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border-radius: 12px !important;
            box-shadow: 0 10px 25px rgba(0,0,0,0.15) !important;
        }
        div[data-baseweb="calendar"] * {
            color: #0f172a !important;
        }

        /* ================= CARDS MODERNAS ================= */
        .saas-card {
            background: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 18px !important;
            padding: 24px !important;
            box-shadow: 0 4px 15px -3px rgba(15, 23, 42, 0.04), 0 2px 6px -2px rgba(15, 23, 42, 0.02) !important;
            margin-bottom: 20px !important;
        }
        .saas-card * {
            color: #1e293b !important;
        }
        .saas-card h1, .saas-card h2, .saas-card h3, .saas-card h4, .saas-card h5, .saas-card h6 {
            color: #0f172a !important;
        }
        .saas-card .stCaption, .saas-card small {
            color: #64748b !important;
        }

        /* ================= NAVBAR & HEADER ================= */
        .app-navbar {
            background: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 16px !important;
            padding: 14px 20px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: space-between !important;
            margin-bottom: 20px !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03) !important;
        }
        .app-brand {
            display: flex !important;
            align-items: center !important;
            gap: 12px !important;
        }
        .app-logo-badge {
            width: 42px !important;
            height: 42px !important;
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
            color: #ffffff !important;
            border-radius: 12px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            font-weight: 800 !important;
            font-size: 20px !important;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25) !important;
        }
        .app-title {
            font-size: 16px !important;
            font-weight: 700 !important;
            color: #0f172a !important;
            margin: 0 !important;
            line-height: 1.2 !important;
        }
        .app-subtitle {
            font-size: 12px !important;
            color: #64748b !important;
            margin: 0 !important;
        }
        .role-badge-admin {
            background: #eff6ff !important;
            color: #2563eb !important;
            border: 1px solid #bfdbfe !important;
            padding: 2px 8px !important;
            border-radius: 6px !important;
            font-size: 11px !important;
            font-weight: 700 !important;
            text-transform: uppercase !important;
        }
        .role-badge-asesor {
            background: #f8fafc !important;
            color: #475569 !important;
            border: 1px solid #e2e8f0 !important;
            padding: 2px 8px !important;
            border-radius: 6px !important;
            font-size: 11px !important;
            font-weight: 600 !important;
        }

        /* ================= STEPPER DE ASISTENCIA ================= */
        .stepper-container {
            display: grid !important;
            grid-template-columns: repeat(4, 1fr) !important;
            gap: 12px !important;
            margin: 18px 0 24px 0 !important;
        }
        @media (max-width: 640px) {
            .stepper-container {
                grid-template-columns: repeat(2, 1fr) !important;
            }
        }
        .step-card {
            background: #ffffff !important;
            border: 1.5px solid #e2e8f0 !important;
            border-radius: 14px !important;
            padding: 14px 12px !important;
            text-align: center !important;
        }
        .step-card * {
            color: #0f172a !important;
        }
        .step-card.active {
            border-color: #3b82f6 !important;
            background: #eff6ff !important;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12) !important;
        }
        .step-card.completed {
            border-color: #10b981 !important;
            background: #f0fdf4 !important;
        }
        .step-icon {
            font-size: 20px !important;
            margin-bottom: 6px !important;
        }
        .step-label {
            font-size: 12px !important;
            font-weight: 600 !important;
            color: #475569 !important;
            margin-bottom: 4px !important;
            text-transform: uppercase !important;
            letter-spacing: 0.3px !important;
        }
        .step-value {
            font-size: 14px !important;
            font-weight: 700 !important;
            color: #0f172a !important;
        }
        .step-value.empty {
            color: #94a3b8 !important;
            font-weight: 500 !important;
            font-size: 12px !important;
        }

        /* ================= GPS BADGES ================= */
        .gps-card-ok {
            background: #ecfdf5 !important;
            border: 1px solid #a7f3d0 !important;
            border-radius: 14px !important;
            padding: 14px 18px !important;
            display: flex !important;
            align-items: center !important;
            gap: 12px !important;
            margin-bottom: 18px !important;
        }
        .gps-card-ok * {
            color: #065f46 !important;
        }
        .gps-card-error {
            background: #fef2f2 !important;
            border: 1px solid #fecaca !important;
            border-radius: 14px !important;
            padding: 14px 18px !important;
            display: flex !important;
            align-items: center !important;
            gap: 12px !important;
            margin-bottom: 18px !important;
        }
        .gps-card-error * {
            color: #991b1b !important;
        }
        .gps-card-warning {
            background: #fffbeb !important;
            border: 1px solid #fde68a !important;
            border-radius: 14px !important;
            padding: 14px 18px !important;
            display: flex !important;
            align-items: center !important;
            gap: 12px !important;
            margin-bottom: 18px !important;
        }
        .gps-card-warning * {
            color: #92400e !important;
        }

        /* ================= BOTONES PERSONALIZADOS ================= */
        div.stButton > button {
            border-radius: 12px !important;
            font-weight: 600 !important;
            padding: 0.6rem 1.2rem !important;
            border: 1px solid transparent !important;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important;
        }
        div.stButton > button:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 6px 14px rgba(0,0,0,0.1) !important;
        }
        
        /* Solo botones activos/habilitados llevan fondo azul y texto blanco */
        div.stButton > button[kind="primary"]:not(:disabled),
        div.stButton > button:not(:disabled):has(div:contains("Entrada")),
        div.stButton > button:not(:disabled):has(div:contains("Salida")),
        div.stButton > button:not(:disabled):has(div:contains("INICIAR")) {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
            color: #ffffff !important;
            border: none !important;
        }
        div.stButton > button[kind="primary"]:not(:disabled) *,
        div.stButton > button:not(:disabled):has(div:contains("Entrada")) *,
        div.stButton > button:not(:disabled):has(div:contains("Salida")) *,
        div.stButton > button:not(:disabled):has(div:contains("INICIAR")) * {
            color: #ffffff !important;
        }

        /* Cuando el botón está deshabilitado a la espera del GPS, se mantiene legible */
        div.stButton > button:disabled,
        div.stButton > button:disabled * {
            color: #64748b !important;
            background-color: #f1f5f9 !important;
            border: 1px solid #e2e8f0 !important;
        }

        /* ================= TABS MODERNOS ================= */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px !important;
            background-color: #f1f5f9 !important;
            padding: 6px !important;
            border-radius: 14px !important;
            border: 1px solid #e2e8f0 !important;
            margin-bottom: 20px !important;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 10px !important;
            padding: 8px 18px !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            color: #64748b !important;
            border: none !important;
            background: transparent !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: #ffffff !important;
            color: #0f172a !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.06) !important;
        }

        /* ================= PANTALLA DE LOGIN ================= */
        .login-wrapper {
            max-width: 440px !important;
            margin: 40px auto !important;
            background: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 24px !important;
            padding: 40px 32px !important;
            box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.07) !important;
            text-align: center !important;
        }
        .login-icon {
            width: 64px !important;
            height: 64px !important;
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
            border-radius: 20px !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            font-size: 28px !important;
            color: white !important;
            margin-bottom: 20px !important;
            box-shadow: 0 8px 20px rgba(37, 99, 235, 0.3) !important;
        }
        .login-title {
            font-size: 24px !important;
            font-weight: 800 !important;
            color: #0f172a !important;
            margin-bottom: 6px !important;
        }
        .login-desc {
            font-size: 14px !important;
            color: #64748b !important;
            margin-bottom: 28px !important;
        }

        /* ================= EXPANDERS Y DATAFRAMES ================= */
        div[data-testid="stExpander"] {
            background-color: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 14px !important;
        }
        div[data-testid="stExpander"] details {
            background-color: #ffffff !important;
        }
        div[data-testid="stExpander"] summary span {
            color: #0f172a !important;
            font-weight: 600 !important;
        }

        div[data-testid="stDataFrame"] {
            background-color: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 12px !important;
            overflow: hidden !important;
        }

        /* Métricas nativas */
        [data-testid="stMetricValue"] {
            font-size: 1.6rem !important;
            font-weight: 800 !important;
            color: #0f172a !important;
        }
        [data-testid="stMetricValue"] * {
            color: #0f172a !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.85rem !important;
            font-weight: 600 !important;
            color: #64748b !important;
        }
        [data-testid="stMetricLabel"] * {
            color: #64748b !important;
        }
        </style>
    """, unsafe_allow_html=True)

# =========================================================
# FUNCIONES AUXILIARES DE TIEMPO (ZONA HORARIA PERÚ UTC-5)
# =========================================================
def obtener_hora_peru():
    """Retorna la fecha y hora exacta de Perú (UTC-5) de forma confiable."""
    return datetime.now(timezone(timedelta(hours=-5)))

def normalizar_cadena_hora(hora_str):
    """
    Normaliza y parsea cualquier formato de hora (ej: '11:54 a. m.', '01:30 PM', '14:20')
    garantizando que no falle con cadenas devueltas por IA o Google Sheets.
    """
    if not hora_str or str(hora_str).strip() in ["Falta", "Permiso", "-", "", "nan", "None"]:
        return None
    s = str(hora_str).strip().lower()
    s = s.replace("a. m.", "am").replace("p. m.", "pm")
    s = s.replace("a.m.", "am").replace("p.m.", "pm")
    s = s.replace("am.", "am").replace("pm.", "pm")
    s = s.replace(".", "").strip().upper()
    
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%I:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None

def calcular_distancia(lat1, lon1, lat2, lon2):
    """Fórmula de Haversine para calcular distancia en km entre dos coordenadas."""
    rad = math.pi / 180
    dlat = (lat2 - lat1) * rad
    dlon = (lon2 - lon1) * rad
    a = math.sin(dlat/2)**2 + math.cos(lat1*rad) * math.cos(lat2*rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return 6371.0 * c

def calcular_minutos_netos_raw(entrada_str, ref_inicio_str, ref_fin_str, salida_str):
    """Calcula los minutos netos trabajados restando el refrigerio si existe."""
    try:
        t_entrada = normalizar_cadena_hora(entrada_str)
        t_salida = normalizar_cadena_hora(salida_str)
        if not t_entrada or not t_salida:
            return 0
            
        if t_salida < t_entrada:
            t_salida += timedelta(days=1)
            
        total_jornada_min = int((t_salida - t_entrada).total_seconds() / 60.0)
        
        tiempo_refrigerio_min = 0
        t_ref_in = normalizar_cadena_hora(ref_inicio_str)
        t_ref_fi = normalizar_cadena_hora(ref_fin_str)
        
        if t_ref_in and t_ref_fi:
            if t_ref_fi < t_ref_in:
                t_ref_fi += timedelta(days=1)
            tiempo_refrigerio_min = int((t_ref_fi - t_ref_in).total_seconds() / 60.0)
            
        return max(0, total_jornada_min - tiempo_refrigerio_min)
    except Exception:
        return 0

def formatear_minutos_a_string(minutos_totales):
    """Convierte minutos enteros a formato legible 'X h Y min'."""
    if minutos_totales <= 0:
        return "0 h 0 min"
    horas = minutos_totales // 60
    minutos = minutos_totales % 60
    return f"{horas} h {minutos} min"

def parsear_string_a_minutos(cadena_tiempo):
    """Convierte 'X h Y min' a minutos numéricos."""
    if str(cadena_tiempo).strip() in ["", "nan", "None", "0 h 0 min", "-", "0"]:
        return 0
    try:
        cadena_clean = str(cadena_tiempo).replace("min", "").strip()
        if "h" in cadena_clean:
            partes = cadena_clean.split("h")
            h = int(partes[0].strip())
            m = int(partes[1].strip()) if len(partes) > 1 and partes[1].strip() != "" else 0
            return (h * 60) + m
        else:
            return int(cadena_clean)
    except Exception:
        return 0

def obtener_semanas_laborales(year, month):
    """
    Divide el mes en semanas laborales de Lunes a Sábado (omitiendo Domingos).
    Retorna un diccionario {semana_num: {'num': int, 'dias': [day_ints], 'inicio': date, 'fin': date, 'label': str, 'meta_col': str}}
    """
    num_days = calendar.monthrange(year, month)[1]
    semanas = {}
    current_w = 1
    for day in range(1, num_days + 1):
        d = datetime(year, month, day).date()
        if d.weekday() == 6:  # Domingo no se labora
            continue
        if d.weekday() == 0 and day > 1:
            if current_w in semanas and len(semanas[current_w]) > 0:
                current_w += 1
        if current_w not in semanas:
            semanas[current_w] = []
        semanas[current_w].append(day)
        
    resultado = {}
    for w_idx, dias in semanas.items():
        d_ini = datetime(year, month, dias[0]).date()
        d_fin = datetime(year, month, dias[-1]).date()
        lbl = f"Semana {w_idx} ({d_ini.strftime('%d/%m')} al {d_fin.strftime('%d/%m')})"
        resultado[w_idx] = {
            "num": w_idx,
            "dias": dias,
            "inicio": d_ini,
            "fin": d_fin,
            "label": lbl,
            "meta_col": f"Meta S{w_idx}"
        }
    return resultado

def obtener_num_semana_para_fecha(fecha_d, dict_semanas):
    """Determina a qué semana laboral pertenece una fecha del mes."""
    day = fecha_d.day
    for w_idx, s_info in dict_semanas.items():
        if day in s_info["dias"]:
            return w_idx
    if fecha_d.weekday() == 6 and day > 1:
        for w_idx, s_info in dict_semanas.items():
            if (day - 1) in s_info["dias"]:
                return w_idx
    return 1

def calcular_resumen_semanal_asesor(fila_user, df_mes, year, month, dict_semanas):
    """
    Calcula las horas trabajadas por semana y las metas semanales de un asesor.
    Retorna: (resumen_por_semana, total_mes_min, meta_mes_total)
    """
    resumen = {}
    total_mes_min = 0
    meta_mes_total = 0
    tiene_metas_semanales = False

    for w_idx, s_info in dict_semanas.items():
        min_semana = 0
        dias_asistidos_sem = 0
        for day in s_info["dias"]:
            f_str = f"{day:02d}/{month:02d}/{year}"
            ce = f"{f_str} (Entrada)"
            cs = f"{f_str} (Salida)"
            if ce in df_mes.columns and cs in df_mes.columns and not fila_user.empty:
                ve = str(fila_user.iloc[0][ce]).strip()
                vrs = str(fila_user.iloc[0][f"{f_str} (Inicio Ref)"]).strip() if f"{f_str} (Inicio Ref)" in df_mes.columns else ""
                vrr = str(fila_user.iloc[0][f"{f_str} (Fin Ref)"]).strip() if f"{f_str} (Fin Ref)" in df_mes.columns else ""
                vs = str(fila_user.iloc[0][cs]).strip()
                m_d = calcular_minutos_netos_raw(ve, vrs, vrr, vs)
                if m_d > 0:
                    min_semana += m_d
                    dias_asistidos_sem += 1

        # Leer meta de la semana (ej. 'Meta S1', 'Meta S2')
        m_col = s_info["meta_col"]
        meta_s_val = 0.0
        if not fila_user.empty and m_col in df_mes.columns:
            try:
                v_raw = str(fila_user.iloc[0][m_col]).strip()
                if v_raw not in ["", "nan", "None", "-"]:
                    meta_s_val = float(v_raw)
                    if meta_s_val > 0:
                        tiene_metas_semanales = True
            except (ValueError, TypeError):
                meta_s_val = 0.0

        total_mes_min += min_semana
        meta_mes_total += max(0.0, meta_s_val)

        pct_s = min(1.0, (min_semana / 60.0) / meta_s_val) if meta_s_val > 0 else 0.0
        resumen[w_idx] = {
            "num": w_idx,
            "label": s_info["label"],
            "minutos": min_semana,
            "horas_str": formatear_minutos_a_string(min_semana),
            "meta_horas": meta_s_val,
            "pct": pct_s,
            "dias_asistidos": dias_asistidos_sem,
            "inicio": s_info["inicio"],
            "fin": s_info["fin"],
            "dias": s_info["dias"]
        }

    # Si no se encontraron metas en Meta S1..S5, usar la columna 'Meta' mensual si existe
    if not tiene_metas_semanales and not fila_user.empty and "Meta" in df_mes.columns:
        try:
            meta_gen = float(str(fila_user.iloc[0]["Meta"]).strip())
            if not pd.isna(meta_gen) and meta_gen > 0:
                meta_mes_total = meta_gen
        except (ValueError, TypeError):
            pass

    return resumen, total_mes_min, meta_mes_total

def calcular_duracion_rango_tiktok(inicio_str, fin_str):
    """Calcula duración en minutos entre inicio y fin de un live."""
    try:
        t_in = normalizar_cadena_hora(inicio_str)
        t_fi = normalizar_cadena_hora(fin_str)
        if not t_in or not t_fi:
            return 0
        if t_fi < t_in:
            t_fi += timedelta(days=1)
        return int((t_fi - t_in).total_seconds() / 60.0)
    except Exception:
        return 0

# =========================================================
# ANÁLISIS DE HISTORIAL TIKTOK CON IA (GEMINI)
# =========================================================
def analizar_historial_tiktok(imagen_bytes):
    try:
        if genai is None:
            return {"valido": False, "motivo_error": "El paquete google-genai no está instalado en el entorno."}

        api_key_val = str(st.secrets["GEMINI_API_KEY"]).strip()
        client = genai.Client(api_key=api_key_val)

        imagen_pil = Image.open(io.BytesIO(imagen_bytes))
        if imagen_pil.mode in ("RGBA", "P"):
            imagen_pil = imagen_pil.convert("RGB")
        imagen_pil.thumbnail((1024, 1024))

        prompt = """
        Analiza detenidamente esta captura de pantalla de un historial de transmisiones de TikTok Live.
        Debes responder ÚNICAMENTE con un objeto JSON válido (sin texto adicional, sin bloques markdown ```json).

        Estructura requerida:
        {
          "valido": true,
          "motivo_error": "",
          "dia": "21",
          "mes": "jul",
          "transmisiones": [
            {"inicio": "11:54 a. m.", "fin": "12:47 p. m."}
          ]
        }

        REGLAS ESTRICTAS:
        1. Si hay transmisiones de 2 o más días distintos, responde "valido": false y "motivo_error": "La captura contiene transmisiones de días diferentes. Sube un reporte de un solo día."
        2. Si la imagen no es un historial de TikTok Live, responde "valido": false y "motivo_error": "La imagen subida no parece ser un historial válido de TikTok Live."
        3. Extrae con exactitud las horas de inicio y fin de cada transmisión de ese día único.
        """

        modelos_a_probar = ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]
        response = None
        ultimo_error = None

        for modelo in modelos_a_probar:
            try:
                response = client.models.generate_content(
                    model=modelo,
                    contents=[prompt, imagen_pil]
                )
                if response and response.text:
                    break
            except Exception as e:
                ultimo_error = e
                continue

        if not response or not response.text:
            raise Exception(f"No se pudo obtener respuesta de la IA: {ultimo_error}")

        texto_limpio = response.text.strip()
        if texto_limpio.startswith("```json"):
            texto_limpio = texto_limpio.replace("```json", "").replace("```", "").strip()
        elif texto_limpio.startswith("```"):
            texto_limpio = texto_limpio.replace("```", "").strip()

        return json.loads(texto_limpio)

    except Exception as e:
        return {"valido": False, "motivo_error": str(e)}

# =========================================================
# INTEGRACIÓN GOOGLE DRIVE (ALMACENAMIENTO DE CAPTURAS TIKTOK)
# =========================================================
def obtener_servicio_drive():
    """Conecta con la API de Google Drive v3 usando la cuenta de servicio de Google."""
    if not drive_api_disponible:
        return None
    try:
        creds_dict = dict(st.secrets["gspread"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception:
        return None

def obtener_o_crear_carpeta_capturas(service):
    """Obtiene el ID de la carpeta configurada en secrets o busca/crea 'Capturas_TikTok_Asistencia'."""
    folder_id = st.secrets.get("DRIVE_FOLDER_ID", "").strip()
    if folder_id:
        return folder_id
    try:
        query = "mimeType = 'application/vnd.google-apps.folder' and name = 'Capturas_TikTok_Asistencia' and trashed = false"
        res = service.files().list(q=query, fields="files(id, name)", spaces="drive").execute()
        files = res.get("files", [])
        if files:
            return files[0]["id"]
        metadata = {
            "name": "Capturas_TikTok_Asistencia",
            "mimeType": "application/vnd.google-apps.folder"
        }
        nueva_carpeta = service.files().create(body=metadata, fields="id").execute()
        return nueva_carpeta.get("id")
    except Exception:
        return None

DRIVE_WEBHOOK_URL_DEFAULT = "https://script.google.com/macros/s/AKfycbxNtXbCZ0WOU64MAiUNo1gePADX2t264CMn9NpkF9e6UCCgaq2H5n5c9e0U23LbHvbZOQ/exec"

def subir_captura_drive(imagen_bytes, usuario, fecha_live):
    """
    Comprime y sube la captura de TikTok a Google Drive vía Webhook de Apps Script (o Service Account).
    Retorna un diccionario con datos del archivo y None, o None y el motivo del fallo.
    """
    try:
        # Optimizar imagen (JPEG calidad 85%, máx 1280px) para ahorrar espacio y acelerar carga
        img = Image.open(io.BytesIO(imagen_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((1280, 1280))
        buffer_opt = io.BytesIO()
        img.save(buffer_opt, format="JPEG", quality=85, optimize=True)
        img_bytes_opt = buffer_opt.getvalue()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        usuario_slug = "".join([c if c.isalnum() else "_" for c in usuario]).strip("_")
        fecha_slug = str(fecha_live).replace("/", "-")
        nombre_archivo = f"{fecha_slug}_{usuario_slug}_{timestamp}.jpg"

        # 1. Método principal: Google Apps Script Webhook (sin restricción de cuota de Service Account)
        webhook_url = st.secrets.get("DRIVE_WEBHOOK_URL", DRIVE_WEBHOOK_URL_DEFAULT)
        if webhook_url:
            try:
                b64_img = base64.b64encode(img_bytes_opt).decode("utf-8")
                payload = json.dumps({
                    "image_base64": b64_img,
                    "filename": nombre_archivo
                }).encode("utf-8")
                
                req = urllib.request.Request(
                    webhook_url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    
                if resp_data.get("status") == "success":
                    file_id = resp_data.get("file_id")
                    view_link = resp_data.get("view_link") or f"https://drive.google.com/file/d/{file_id}/view"
                    direct_link = f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000"
                    return {
                        "file_id": file_id,
                        "view_link": view_link,
                        "direct_link": direct_link,
                        "nombre": nombre_archivo
                    }, None
                else:
                    webhook_err = resp_data.get("message", "Error devuelto por Apps Script")
            except Exception as w_ex:
                webhook_err = str(w_ex)
        else:
            webhook_err = "No hay URL de webhook configurada"

        # 2. Respaldo: Google Drive API (Service Account)
        if drive_api_disponible:
            service = obtener_servicio_drive()
            if service:
                folder_id = obtener_o_crear_carpeta_capturas(service)
                file_metadata = {"name": nombre_archivo}
                if folder_id:
                    file_metadata["parents"] = [folder_id]
                media = MediaIoBaseUpload(io.BytesIO(img_bytes_opt), mimetype="image/jpeg", resumable=False)
                archivo = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, webViewLink, webContentLink"
                ).execute()
                file_id = archivo.get("id")
                try:
                    service.permissions().create(
                        fileId=file_id,
                        body={"role": "reader", "type": "anyone"}
                    ).execute()
                except Exception:
                    pass
                view_link = archivo.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view"
                direct_link = f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000"
                return {
                    "file_id": file_id,
                    "view_link": view_link,
                    "direct_link": direct_link,
                    "nombre": nombre_archivo
                }, None

        return None, f"Fallo al subir a Google Drive: {webhook_err}"
    except Exception as e:
        return None, str(e)

def registrar_evidencia_tiktok(doc_tiktok, fecha_registro, fecha_live, usuario, codigo, total_horas_str, transmisiones_lista, drive_info):
    """Registra la auditoría en la pestaña EVIDENCIAS_CAPTURA de Google Sheets con el link a Drive."""
    try:
        try:
            wks_ev = doc_tiktok.worksheet("EVIDENCIAS_CAPTURA")
        except Exception:
            wks_ev = doc_tiktok.add_worksheet(title="EVIDENCIAS_CAPTURA", rows="1000", cols="8")
            wks_ev.append_row([
                "Fecha Registro", "Fecha Live", "Usuario", "Codigo", 
                "Tiempo Total", "Detalle Transmisiones", "Link Captura", "Drive File ID"
            ])
            
        detalle_str = " | ".join([f"{t.get('inicio', '')} a {t.get('fin', '')}" for t in transmisiones_lista])
        link_str = drive_info.get("view_link", "") if drive_info else ""
        file_id_str = drive_info.get("file_id", "") if drive_info else ""
        
        wks_ev.append_row([
            fecha_registro,
            fecha_live,
            usuario,
            codigo,
            total_horas_str,
            detalle_str,
            link_str,
            file_id_str
        ])
        return True
    except Exception:
        return False

# =========================================================
# OPERACIONES SEGURAS EN GOOGLE SHEETS (SIN wks.clear())
# =========================================================
def actualizar_marcado_seguro(wks, df, usuario, actualizaciones_dict):
    """
    Actualiza de forma atómica únicamente las celdas necesarias para el usuario.
    Evita wks.clear() para prevenir pérdidas de datos por concurrencia y preservar formatos.
    """
    try:
        headers = [str(h).strip() for h in wks.row_values(1)]
        
        if "Usuario" not in headers:
            raise ValueError("No se encontró la columna 'Usuario' en la hoja")
        col_usuario_idx = headers.index("Usuario") + 1
        
        col_usuarios_valores = [str(u).strip() for u in wks.col_values(col_usuario_idx)]
        if usuario not in col_usuarios_valores:
            raise ValueError(f"El usuario '{usuario}' no se encuentra en la hoja")
        fila_idx = col_usuarios_valores.index(usuario) + 1
        
        for col_nombre, nuevo_valor in actualizaciones_dict.items():
            if col_nombre in headers:
                col_idx = headers.index(col_nombre) + 1
            else:
                wks.add_cols(1)
                col_idx = len(headers) + 1
                wks.update_cell(1, col_idx, col_nombre)
                headers.append(col_nombre)
                
            wks.update_cell(fila_idx, col_idx, nuevo_valor)
            df.loc[df["Usuario"] == usuario, col_nombre] = nuevo_valor
            
        st.cache_data.clear()
        return True
    except Exception as e:
        for col_nombre, nuevo_valor in actualizaciones_dict.items():
            df.loc[df["Usuario"] == usuario, col_nombre] = nuevo_valor
        set_with_dataframe(wks, df, resize=True)
        st.cache_data.clear()
        return True

# Inyectamos estilos visuales blindados
inyectar_estilos()

# =========================================================
# CONEXIÓN PRINCIPAL CON GOOGLE SHEETS
# =========================================================
try:
    gc = gspread.service_account_from_dict(dict(st.secrets["gspread"]))
    
    sheet_id = st.secrets.get("SHEET_ID", "1-GCk6phMzn9UEAFomTYco8C8hoLYc7R_daBwcBuRwtU")
    hoja_calculo = gc.open_by_key(sheet_id)

    @st.cache_data(ttl=60)
    def cargar_datos_pestana(pestana_nombre):
        try:
            wks_local = hoja_calculo.worksheet(pestana_nombre)
            return get_as_dataframe(wks_local).dropna(how="all").dropna(axis=1, how="all")
        except Exception:
            return pd.DataFrame()

    @st.cache_data(ttl=60)
    def cargar_datos_pestana_tiktok(pestana_nombre):
        try:
            doc_tt = gc.open("REPORTES TIKTOK")
            wks_tt_local = doc_tt.worksheet(pestana_nombre)
            return get_as_dataframe(wks_tt_local).dropna(how="all").dropna(axis=1, how="all")
        except Exception:
            return pd.DataFrame()

    @st.cache_data(ttl=60)
    def cargar_evidencias_tiktok():
        try:
            doc_tt = gc.open("REPORTES TIKTOK")
            wks_ev = doc_tt.worksheet("EVIDENCIAS_CAPTURA")
            return get_as_dataframe(wks_ev).dropna(how="all").dropna(axis=1, how="all")
        except Exception:
            return pd.DataFrame()

    def eliminar_reporte_evidencia_tiktok(usuario, fecha_live, fecha_registro, file_id=""):
        """
        Elimina un reporte de la pestaña EVIDENCIAS_CAPTURA en REPORTES TIKTOK
        y recalcula automáticamente el acumulado de horas de ese día en la hoja del mes.
        """
        try:
            doc_tt = gc.open("REPORTES TIKTOK")
            wks_ev = doc_tt.worksheet("EVIDENCIAS_CAPTURA")
            
            all_rows = wks_ev.get_all_values()
            if len(all_rows) < 2:
                return False, "La hoja de evidencias está vacía."
                
            headers = [str(h).strip() for h in all_rows[0]]
            idx_freg = headers.index("Fecha Registro") if "Fecha Registro" in headers else -1
            idx_flive = headers.index("Fecha Live") if "Fecha Live" in headers else -1
            idx_usr = headers.index("Usuario") if "Usuario" in headers else -1
            idx_fid = headers.index("Drive File ID") if "Drive File ID" in headers else -1
            idx_tot = headers.index("Tiempo Total") if "Tiempo Total" in headers else -1
            
            fila_a_borrar = -1
            minutos_restantes_dia = 0
            
            # Buscar la fila exacta a borrar
            for row_idx, r in enumerate(all_rows[1:], start=2):
                u_val = str(r[idx_usr]).strip() if idx_usr != -1 and len(r) > idx_usr else ""
                fl_val = str(r[idx_flive]).strip() if idx_flive != -1 and len(r) > idx_flive else ""
                fr_val = str(r[idx_freg]).strip() if idx_freg != -1 and len(r) > idx_freg else ""
                fid_val = str(r[idx_fid]).strip() if idx_fid != -1 and len(r) > idx_fid else ""
                
                es_esta_fila = False
                if file_id and fid_val and fid_val == file_id:
                    es_esta_fila = True
                elif u_val == usuario and fl_val == fecha_live and fr_val == fecha_registro:
                    es_esta_fila = True
                    
                if es_esta_fila and fila_a_borrar == -1:
                    fila_a_borrar = row_idx
                else:
                    # Sumar los minutos de los otros reportes del mismo usuario en ese mismo día
                    if u_val == usuario and fl_val == fecha_live:
                        t_str = str(r[idx_tot]).strip() if idx_tot != -1 and len(r) > idx_tot else ""
                        minutos_restantes_dia += parsear_string_a_minutos(t_str)
                        
            if fila_a_borrar == -1:
                return False, "No se encontró el registro a eliminar."
                
            # 1. Eliminar la fila de EVIDENCIAS_CAPTURA
            wks_ev.delete_rows(fila_a_borrar)
            
            # 2. Recalcular y actualizar la celda en la hoja del mes correspondiente
            try:
                partes_f = fecha_live.split("/")
                if len(partes_f) == 3:
                    num_mes = int(partes_f[1])
                    pestana_mes = MESES_ESPANOL.get(num_mes)
                    if pestana_mes:
                        try:
                            wks_mes = doc_tt.worksheet(pestana_mes)
                            df_mes_tt = get_as_dataframe(wks_mes).dropna(how="all")
                            
                            nuevo_acumulado_str = formatear_minutos_a_string(minutos_restantes_dia) if minutos_restantes_dia > 0 else "0 h 0 min"
                            actualizar_marcado_seguro(wks_mes, df_mes_tt, usuario, {fecha_live: nuevo_acumulado_str})
                        except Exception:
                            pass
            except Exception:
                pass
                
            st.cache_data.clear()
            return True, None
        except Exception as e:
            return False, str(e)

    hora_peru_actual = obtener_hora_peru()
    mes_actual_num = hora_peru_actual.month
    nombre_pestana = MESES_ESPANOL[mes_actual_num]

    wks = hoja_calculo.worksheet(nombre_pestana)
    df = cargar_datos_pestana(nombre_pestana)

    # Automatización diaria de columnas para el día actual
    fecha_hoy = hora_peru_actual.strftime("%d/%m/%Y")
    col_entrada = f"{fecha_hoy} (Entrada)"
    col_ref_salida = f"{fecha_hoy} (Inicio Ref)"
    col_ref_retorno = f"{fecha_hoy} (Fin Ref)"
    col_salida = f"{fecha_hoy} (Salida)"

    cols_requeridas = [col_entrada, col_ref_salida, col_ref_retorno, col_salida]
    columnas_a_crear = [c for c in cols_requeridas if c not in df.columns]

    if columnas_a_crear:
        num_nuevas = len(columnas_a_crear)
        wks.add_cols(num_nuevas)
        for c in columnas_a_crear:
            df[c] = "Falta"
        set_with_dataframe(wks, df, resize=True)
        st.cache_data.clear()
        df = cargar_datos_pestana(nombre_pestana)

    # Estado de sesión
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False
        st.session_state.usuario_actual = ""
    
    # Clave dinámica para resetear el GPS cada vez que se marque
    if "geo_key" not in st.session_state:
        st.session_state.geo_key = 0

    # =========================================================
    # VISTA: INICIO DE SESIÓN (LOGIN MODERNO)
    # =========================================================
    if not st.session_state.autenticado:
        col_esp_izq, col_login, col_esp_der = st.columns([1, 1.4, 1])
        
        with col_login:
            st.markdown("""
                <div class="login-wrapper">
                    <div class="login-icon">⏱️</div>
                    <div class="login-title">Control de Asistencia</div>
                    <div class="login-desc">Ingresa tu código de asesor para registrar tu jornada laboral o reportes de TikTok.</div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.form("form_login", clear_on_submit=False):
                codigo_ingresado = st.text_input(
                    "Código de Asesor", 
                    type="password", 
                    placeholder="Ingresa tu código...",
                    help="Tu código personal asignado en la hoja de asistencia"
                )
                
                btn_ingresar = st.form_submit_button("INICIAR SESIÓN", use_container_width=True, type="primary")
                
                if btn_ingresar:
                    if not codigo_ingresado or str(codigo_ingresado).strip() == "":
                        st.error("Por favor, introduce un código de asesor.")
                    else:
                        df["Codigo"] = df["Codigo"].astype(str).str.split('.').str[0].str.strip()
                        codigo_clean = str(codigo_ingresado).strip()
                        usuario_encontrado = df[df["Codigo"] == codigo_clean]
                        
                        if not usuario_encontrado.empty:
                            st.session_state.autenticado = True
                            st.session_state.usuario_actual = usuario_encontrado.iloc[0]["Usuario"]
                            st.session_state.codigo_actual = codigo_clean
                            st.session_state.geo_key += 1
                            st.rerun()
                        else:
                            st.error("Código incorrecto. Por favor, verifica tus credenciales.")

    # =========================================================
    # VISTA: APLICACIÓN PRINCIPAL (USUARIO AUTENTICADO)
    # =========================================================
    else:
        es_admin = (st.session_state.usuario_actual == "VALENTIN ISASI")
        hora_live_str = obtener_hora_peru().strftime("%I:%M %p")
        
        # Barra de Navegación Superior
        col_nav_info, col_nav_btn = st.columns([3.5, 1])
        with col_nav_info:
            role_badge = '<span class="role-badge-admin">Administrador</span>' if es_admin else '<span class="role-badge-asesor">Asesor</span>'
            st.markdown(f"""
                <div class="app-navbar">
                    <div class="app-brand">
                        <div class="app-logo-badge">⏱️</div>
                        <div>
                            <p class="app-title">{st.session_state.usuario_actual} {role_badge}</p>
                            <p class="app-subtitle">🇵🇪 Hora Perú: <strong>{hora_live_str}</strong> • Sede Ica</p>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        with col_nav_btn:
            st.write("")
            if st.button("Cerrar Sesión", use_container_width=True):
                st.session_state.autenticado = False
                st.session_state.usuario_actual = ""
                st.session_state.geo_key += 1
                st.rerun()

        # Tabs de Navegación
        if es_admin:
            tab_marcado, tab_tiktok, tab_reporte = st.tabs(["📍 Mi Marcado", "📹 Reporte TikTok", "📊 Panel Administrador"])
        else:
            tab_marcado, tab_tiktok = st.tabs(["📍 Mi Marcado", "📹 Reporte TikTok"])

        fila_usuario = df[df["Usuario"] == st.session_state.usuario_actual]
        
        # Valores de asistencia para el día de hoy
        marca_entrada = str(fila_usuario.iloc[0][col_entrada]).strip() if not pd.isna(fila_usuario.iloc[0][col_entrada]) else ""
        marca_ref_salida = str(fila_usuario.iloc[0][col_ref_salida]).strip() if not pd.isna(fila_usuario.iloc[0][col_ref_salida]) else ""
        marca_ref_retorno = str(fila_usuario.iloc[0][col_ref_retorno]).strip() if not pd.isna(fila_usuario.iloc[0][col_ref_retorno]) else ""
        marca_salida = str(fila_usuario.iloc[0][col_salida]).strip() if not pd.isna(fila_usuario.iloc[0][col_salida]) else ""

        # =========================================================
        # PESTAÑA 1: MI MARCADO (DIARIO)
        # =========================================================
        with tab_marcado:
            st.markdown('<div class="saas-card">', unsafe_allow_html=True)
            st.markdown("#### 📍 Verificación de Ubicación Requerida")
            st.caption(f"Por seguridad y transparencia, debes verificar tu ubicación con el botón GPS para cada registro (Radio máximo permitido: **{RADIO_MAX_KM*1000:.0f} metros** de la base Ica).")
            
            # --- FORZADO CSS PARA CENTRAR EL IFRAME DEL GPS ---
            st.markdown("""
                <style>
                /* Centra el contenedor del iframe del componente de geolocalización */
                div[data-testid="stCustomComponentV1"],
                div:has(> iframe[title*="streamlit_geolocation"]) {
                    display: flex !important;
                    justify-content: center !important;
                    align-items: center !important;
                    text-align: center !important;
                    margin: 0 auto !important;
                    width: 100% !important;
                }
                div:has(> iframe[title*="streamlit_geolocation"]) iframe {
                    margin: 0 auto !important;
                }
                </style>
            """, unsafe_allow_html=True)

            # Tarjeta contenedora centrada
            st.markdown("""
                <div style="
                    background: #f8fafc;
                    border: 1.5px dashed #94a3b8;
                    border-radius: 16px;
                    padding: 16px 14px 12px 14px;
                    text-align: center;
                    max-width: 380px;
                    margin: 12px auto 18px auto;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                ">
                    <div style="font-size: 13px; font-weight: 700; color: #1e293b; margin-bottom: 2px;">
                        🛰️ COMPROBAR COORDENADAS
                    </div>
                    <div style="font-size: 11px; color: #64748b; margin-bottom: 10px;">
                        Presiona el botón de abajo para activar tu GPS
                    </div>
            """, unsafe_allow_html=True)

            # Componente de geolocalización (ahora centrado por flexbox)
            loc = obtener_geolocalizacion(st.session_state.geo_key)

            st.markdown("</div>", unsafe_allow_html=True)

            ubicacion_valida = False
            
            if loc and loc.get('latitude') is not None:
                lat_user = loc['latitude']
                lon_user = loc['longitude']
                distancia_km = calcular_distancia(lat_user, lon_user, LAT_OBJETIVO, LON_OBJETIVO)
                
                if distancia_km <= RADIO_MAX_KM:
                    ubicacion_valida = True
                    st.markdown(f"""
                        <div class="gps-card-ok">
                            <span style="font-size: 20px;">✅</span>
                            <div>
                                <strong>Ubicación confirmada:</strong> Te encuentras dentro del perímetro permitido 
                                (a <strong>{distancia_km*1000:.0f} metros</strong> de la base). Ahora puedes pulsar el botón de registro abajo.
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                        <div class="gps-card-error">
                            <span style="font-size: 20px;">⚠️</span>
                            <div>
                                <strong>Fuera de rango:</strong> Estás a <strong>{distancia_km:.2f} km</strong> de la sede central. 
                                El límite máximo permitido es de <strong>{RADIO_MAX_KM} km</strong>.
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("""
                    <div class="gps-card-warning">
                        <span style="font-size: 20px;">📡</span>
                        <div>
                            <strong>Paso obligatorio:</strong> Pulsa el botón del GPS de arriba para verificar tu ubicación actual.
                        </div>
                    </div>
                """, unsafe_allow_html=True)

            # --- STEPPER VISUAL DE JORNADA ---
            is_ent_done = marca_entrada not in ["Falta", "Permiso", "-", "", "nan", "None"]
            is_ref_sal_done = marca_ref_salida not in ["Falta", "Permiso", "-", "", "nan", "None"]
            is_ref_ret_done = marca_ref_retorno not in ["Falta", "Permiso", "-", "", "nan", "None"]
            is_sal_done = marca_salida not in ["Falta", "Permiso", "-", "", "nan", "None"]
            is_permiso = marca_entrada == "Permiso"

            cls_ent = "completed" if is_ent_done else ("active" if not is_permiso else "")
            cls_rs = "completed" if is_ref_sal_done else ("active" if is_ent_done and not is_ref_sal_done else "")
            cls_rr = "completed" if is_ref_ret_done else ("active" if is_ref_sal_done and not is_ref_ret_done else "")
            cls_sal = "completed" if is_sal_done else ("active" if is_ent_done and (is_ref_ret_done or not is_ref_sal_done) and not is_sal_done else "")

            val_ent_txt = marca_entrada if is_ent_done else ("Permiso" if is_permiso else "Pendiente")
            val_rs_txt = marca_ref_salida if is_ref_sal_done else "-"
            val_rr_txt = marca_ref_retorno if is_ref_ret_done else "-"
            val_sal_txt = marca_salida if is_sal_done else "Pendiente"

            st.markdown(f"""
                <div class="stepper-container">
                    <div class="step-card {cls_ent}">
                        <div class="step-icon">{"🟢" if is_ent_done else "📥"}</div>
                        <div class="step-label">1. Entrada</div>
                        <div class="step-value {'empty' if not is_ent_done else ''}">{val_ent_txt}</div>
                    </div>
                    <div class="step-card {cls_rs}">
                        <div class="step-icon">{"☕" if is_ref_sal_done else "🥪"}</div>
                        <div class="step-label">2. Inicio Almuerzo</div>
                        <div class="step-value {'empty' if not is_ref_sal_done else ''}">{val_rs_txt}</div>
                    </div>
                    <div class="step-card {cls_rr}">
                        <div class="step-icon">{"💼" if is_ref_ret_done else "🕒"}</div>
                        <div class="step-label">3. Fin Almuerzo</div>
                        <div class="step-value {'empty' if not is_ref_ret_done else ''}">{val_rr_txt}</div>
                    </div>
                    <div class="step-card {cls_sal}">
                        <div class="step-icon">{"🏁" if is_sal_done else "🚪"}</div>
                        <div class="step-label">4. Salida Final</div>
                        <div class="step-value {'empty' if not is_sal_done else ''}">{val_sal_txt}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            tiempo_ahora_peru = obtener_hora_peru()
            hora_registro_str = tiempo_ahora_peru.strftime("%I:%M %p")

            # --- BOTONES DE ACCIÓN INTELIGENTES ---
            if is_permiso:
                st.info("ℹ️ Tu estado del día de hoy está registrado como **Permiso Especial**.")
            elif not is_ent_done:
                st.markdown(f"###### Hora detectada para registro: **{hora_registro_str}**")
                col_btn_ent, col_btn_perm = st.columns([2, 1])
                with col_btn_ent:
                    if st.button("📥 Registrar Entrada", use_container_width=True, type="primary", disabled=not ubicacion_valida):
                        actualizar_marcado_seguro(wks, df, st.session_state.usuario_actual, {col_entrada: hora_registro_str})
                        st.session_state.geo_key += 1  # Reset GPS para el siguiente registro
                        st.success(f"Entrada registrada: {hora_registro_str}")
                        st.rerun()
                with col_btn_perm:
                    if st.button("📄 Solicitar Permiso", use_container_width=True):
                        actualizar_marcado_seguro(wks, df, st.session_state.usuario_actual, {
                            col_entrada: "Permiso",
                            col_ref_salida: "Permiso",
                            col_ref_retorno: "Permiso",
                            col_salida: "Permiso"
                        })
                        st.session_state.geo_key += 1  # Reset GPS
                        st.success("Permiso registrado exitosamente.")
                        st.rerun()
            elif is_sal_done:
                minutos_hoy = calcular_minutos_netos_raw(marca_entrada, marca_ref_salida, marca_ref_retorno, marca_salida)
                st.success(f"🎉 **¡Jornada de hoy completada!** Tiempo total neto acumulado: **{formatear_minutos_a_string(minutos_hoy)}**.")
            else:
                st.markdown(f"###### Hora detectada para registro: **{hora_registro_str}**")
                col_ref, col_sal = st.columns(2)
                
                with col_ref:
                    if not is_ref_sal_done:
                        if st.button("☕ Iniciar Refrigerio / Almuerzo", use_container_width=True, disabled=not ubicacion_valida):
                            actualizar_marcado_seguro(wks, df, st.session_state.usuario_actual, {col_ref_salida: hora_registro_str})
                            st.session_state.geo_key += 1  # Reset GPS para que deban volver a verificar al retornar
                            st.success(f"Inicio de refrigerio registrado: {hora_registro_str}")
                            st.rerun()
                    elif not is_ref_ret_done:
                        if st.button("💼 Terminar Refrigerio (Retorno)", use_container_width=True, disabled=not ubicacion_valida):
                            actualizar_marcado_seguro(wks, df, st.session_state.usuario_actual, {col_ref_retorno: hora_registro_str})
                            st.session_state.geo_key += 1  # Reset GPS para la salida final
                            st.success(f"Retorno de refrigerio registrado: {hora_registro_str}")
                            st.rerun()
                    else:
                        st.caption(f"Refrigerio completado: {marca_ref_salida} a {marca_ref_retorno}")
                        
                with col_sal:
                    if st.button("🚪 Registrar Salida Final", use_container_width=True, type="primary", disabled=not ubicacion_valida):
                        actualizar_marcado_seguro(wks, df, st.session_state.usuario_actual, {col_salida: hora_registro_str})
                        st.session_state.geo_key += 1  # Reset GPS
                        st.success(f"Salida registrada: {hora_registro_str}")
                        st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

            # =========================================================
            # CONSULTA DE HISTORIAL Y METAS SEMANALES / MENSUALES
            # =========================================================
            with st.expander("📅 Mi Progreso Semanal y Asistencias", expanded=True):
                col_cal, col_sem = st.columns([1, 1.5])
                
                with col_cal:
                    fecha_busqueda = st.date_input("Seleccionar Fecha de Consulta:", value=obtener_hora_peru().date(), key="cal_asesor_view")
                    
                pestana_busq = MESES_ESPANOL[fecha_busqueda.month]
                df_historial = cargar_datos_pestana(pestana_busq)
                fila_user_hist = df_historial[df_historial["Usuario"] == st.session_state.usuario_actual] if not df_historial.empty and "Usuario" in df_historial.columns else pd.DataFrame()

                # Semanas laborales de Lunes a Sábado del mes seleccionado
                dict_semanas = obtener_semanas_laborales(fecha_busqueda.year, fecha_busqueda.month)
                sem_sugerida_idx = obtener_num_semana_para_fecha(fecha_busqueda, dict_semanas)
                opciones_sem_labels = [dict_semanas[k]["label"] for k in sorted(dict_semanas.keys())]
                idx_default = max(0, min(sem_sugerida_idx - 1, len(opciones_sem_labels) - 1))

                with col_sem:
                    sem_elegida_label = st.selectbox("Seleccionar Semana a Revisar:", opciones_sem_labels, index=idx_default, key="cal_asesor_sem_sel")

                sem_num_act = [k for k, v in dict_semanas.items() if v["label"] == sem_elegida_label][0]
                resumen_semanas, total_minutos_mes, meta_mes_total = calcular_resumen_semanal_asesor(
                    fila_user_hist, df_historial, fecha_busqueda.year, fecha_busqueda.month, dict_semanas
                )
                info_semana_act = resumen_semanas[sem_num_act]

                # 1. Métricas de la Semana Seleccionada
                col_w1, col_w2 = st.columns([1, 1.5])
                with col_w1:
                    st.metric(
                        f"Horas {info_semana_act['label'].split(' ')[0]} {info_semana_act['label'].split(' ')[1]}", 
                        info_semana_act["horas_str"],
                        f"{info_semana_act['dias_asistidos']} días asistidos"
                    )
                with col_w2:
                    if info_semana_act["meta_horas"] > 0:
                        h_trabajadas = info_semana_act["minutos"] / 60.0
                        pct_s = info_semana_act["pct"]
                        st.markdown(f"**Meta de la Semana:** {h_trabajadas:.1f} h / {info_semana_act['meta_horas']:.0f} h (**{pct_s*100:.1f}%**)")
                        st.progress(pct_s)
                        min_faltan_s = int((info_semana_act["meta_horas"] * 60) - info_semana_act["minutos"])
                        if min_faltan_s > 0:
                            st.caption(f"🎯 Faltan **{formatear_minutos_a_string(min_faltan_s)}** para alcanzar tu meta de esta semana.")
                        else:
                            st.success("🎉 ¡Felicidades! Has completado tu meta de esta semana.")
                    else:
                        st.caption("ℹ️ Sin meta asignada para esta semana.")

                # 2. Desglose detallado de asistencias de esa semana (Lunes a Sábado)
                st.markdown(f"###### 📋 Registro de Asistencias — {info_semana_act['label']}")
                filas_dias_sem = []
                for dia_int in info_semana_act["dias"]:
                    d_dt = datetime(fecha_busqueda.year, fecha_busqueda.month, dia_int).date()
                    f_d_str = f"{dia_int:02d}/{fecha_busqueda.month:02d}/{fecha_busqueda.year}"
                    nom_dia = DIAS_SEMANA_ESPANOL.get(d_dt.weekday(), "")
                    
                    ce = f"{f_d_str} (Entrada)"
                    crs = f"{f_d_str} (Inicio Ref)"
                    crr = f"{f_d_str} (Fin Ref)"
                    cs = f"{f_d_str} (Salida)"
                    
                    if not fila_user_hist.empty and ce in df_historial.columns and cs in df_historial.columns:
                        ve = str(fila_user_hist.iloc[0][ce]).strip()
                        vrs = str(fila_user_hist.iloc[0][crs]).strip() if crs in df_historial.columns else "-"
                        vrr = str(fila_user_hist.iloc[0][crr]).strip() if crr in df_historial.columns else "-"
                        vs = str(fila_user_hist.iloc[0][cs]).strip()
                        m_d = calcular_minutos_netos_raw(ve, vrs, vrr, vs)
                        tot_dia_str = formatear_minutos_a_string(m_d) if (ve not in ["", "Falta", "-", "nan", "None"] or vs not in ["", "Falta", "-", "nan", "None"]) else "-"
                    else:
                        ve, vrs, vrr, vs, tot_dia_str = "-", "-", "-", "-", "-"
                        
                    filas_dias_sem.append({
                        "Fecha": f_d_str,
                        "Día": nom_dia,
                        "Entrada": ve if ve not in ["nan", "None"] else "-",
                        "Inicio Ref": vrs if vrs not in ["nan", "None"] else "-",
                        "Fin Ref": vrr if vrr not in ["nan", "None"] else "-",
                        "Salida": vs if vs not in ["nan", "None"] else "-",
                        "Total Neto": tot_dia_str
                    })
                st.dataframe(pd.DataFrame(filas_dias_sem), use_container_width=True, hide_index=True)

                # 3. Consolidado Mensual Global
                st.markdown("---")
                col_m1, col_m2 = st.columns([1, 1.5])
                with col_m1:
                    st.metric(f"Total Acumulado en {pestana_busq.capitalize()}", formatear_minutos_a_string(total_minutos_mes))
                with col_m2:
                    if meta_mes_total > 0:
                        total_horas = total_minutos_mes / 60.0
                        pct = min(1.0, total_horas / meta_mes_total)
                        st.markdown(f"**Meta Mensual Total:** {total_horas:.1f} h / {meta_mes_total:.0f} h (**{pct*100:.1f}%**)")
                        st.progress(pct)
                        min_faltantes = int((meta_mes_total * 60) - total_minutos_mes)
                        if min_faltantes > 0:
                            st.caption(f"🎯 Faltan **{formatear_minutos_a_string(min_faltantes)}** para completar la meta global del mes.")
                        else:
                            st.success("🎉 ¡Felicidades! Has completado tu meta del mes.")
                    else:
                        st.caption("ℹ️ Sin meta mensual asignada.")

        # =========================================================
        # PESTAÑA 2: REPORTE TIKTOK LIVE (IA VISION)
        # =========================================================
        with tab_tiktok:
            st.markdown('<div class="saas-card">', unsafe_allow_html=True)
            st.markdown("#### 📹 Subir Captura de TikTok Live")
            st.caption("Sube una captura de tu historial de en vivos de TikTok. La IA extraerá automáticamente los rangos del día y sumará las horas a tu cuenta.")

            if "uploader_key" not in st.session_state:
                st.session_state.uploader_key = 0

            archivo_tt = st.file_uploader(
                "Cargar captura de historial",
                type=["png", "jpg", "jpeg"],
                key=f"tt_uploader_{st.session_state.uploader_key}"
            )

            if archivo_tt is not None:
                bytes_tt = archivo_tt.getvalue()
                col_prev, col_analisis = st.columns([1, 1.2])

                with col_prev:
                    st.image(bytes_tt, caption="Captura subida", use_container_width=True)

                with col_analisis:
                    id_archivo = f"{archivo_tt.name}_{len(bytes_tt)}"
                    if "res_tiktok_data" not in st.session_state or st.session_state.get("id_archivo_tt_actual") != id_archivo:
                        with st.spinner("🧠 Analizando historial y validando fechas con IA..."):
                            data_analisis = analizar_historial_tiktok(bytes_tt)
                            st.session_state.res_tiktok_data = data_analisis
                            st.session_state.id_archivo_tt_actual = id_archivo

                    data_ia = st.session_state.res_tiktok_data

                    if not data_ia.get("valido", False):
                        st.error(f"❌ **Reporte Rechazado:** {data_ia.get('motivo_error', 'Ocurrió un error al procesar la imagen.')}")
                        if st.button("🔄 Probar con otra imagen", use_container_width=True):
                            st.session_state.pop("res_tiktok_data", None)
                            st.session_state.pop("id_archivo_tt_actual", None)
                            st.session_state.uploader_key += 1
                            st.rerun()
                    else:
                        dia_detectado = str(data_ia.get("dia", "")).strip()
                        mes_raw = str(data_ia.get("mes", "")).lower().strip()
                        mes_detectado = mes_raw.capitalize()
                        transmisiones = data_ia.get("transmisiones", [])

                        st.success(f"✅ **Validado:** {len(transmisiones)} Live(s) detectado(s) el **{dia_detectado} de {mes_detectado}**.")
                        
                        total_minutos_tiktok = 0
                        for idx_l, live in enumerate(transmisiones, 1):
                            ini = live.get("inicio", "")
                            fin = live.get("fin", "")
                            dur = calcular_duracion_rango_tiktok(ini, fin)
                            total_minutos_tiktok += dur
                            hrs_l = dur // 60
                            mins_l = dur % 60
                            dur_str = f"{hrs_l}h {mins_l}m" if hrs_l > 0 else f"{mins_l} min"
                            st.markdown(f"• **Live {idx_l}:** `{ini}` a `{fin}` (**{dur_str}**)")

                        total_tt_str = formatear_minutos_a_string(total_minutos_tiktok)
                        st.metric("⏱️ Tiempo Total Transmitido", total_tt_str)

                        col_subir, col_cancelar = st.columns(2)
                        with col_subir:
                            if st.button("✅ Subir Reporte", use_container_width=True, type="primary"):
                                with st.spinner("Guardando horas y subiendo captura a Google Drive..."):
                                    try:
                                        doc_tiktok = gc.open("REPORTES TIKTOK")
                                        num_mes = MESES_TEXTO_A_NUM.get(mes_raw, obtener_hora_peru().month)
                                        pestana_tt = MESES_ESPANOL[num_mes]

                                        try:
                                            wks_tt = doc_tiktok.worksheet(pestana_tt)
                                        except Exception:
                                            wks_tt = doc_tiktok.add_worksheet(title=pestana_tt, rows="100", cols="20")

                                        df_tt = get_as_dataframe(wks_tt).dropna(how="all")
                                        if df_tt.empty or "Usuario" not in df_tt.columns:
                                            df_tt = pd.DataFrame(columns=["Usuario", "Codigo", "Meta"])

                                        anio_act = obtener_hora_peru().strftime("%Y")
                                        col_fecha_tt = f"{dia_detectado.zfill(2)}/{num_mes:02d}/{anio_act}"

                                        for c_f in ["Usuario", "Codigo", "Meta"]:
                                            if c_f not in df_tt.columns:
                                                df_tt[c_f] = ""
                                        if col_fecha_tt not in df_tt.columns:
                                            df_tt[col_fecha_tt] = ""

                                        usr_act = st.session_state.usuario_actual
                                        cod_act = st.session_state.get("codigo_actual", "")

                                        if usr_act not in df_tt["Usuario"].values:
                                            nueva_fila = {"Usuario": usr_act, "Codigo": cod_act, "Meta": "0"}
                                            df_tt = pd.concat([df_tt, pd.DataFrame([nueva_fila])], ignore_index=True)

                                        # Suma acumulativa si ya existía tiempo en ese día
                                        val_existente = df_tt.loc[df_tt["Usuario"] == usr_act, col_fecha_tt].values[0]
                                        minutos_previos = parsear_string_a_minutos(val_existente)
                                        total_dia = minutos_previos + total_minutos_tiktok
                                        total_str_final = formatear_minutos_a_string(total_dia)

                                        df_tt.loc[df_tt["Usuario"] == usr_act, col_fecha_tt] = total_str_final
                                        
                                        actualizar_marcado_seguro(wks_tt, df_tt, usr_act, {col_fecha_tt: total_str_final})

                                        # Subir captura a Google Drive y registrar evidencia de auditoría
                                        drive_info, drive_err = subir_captura_drive(bytes_tt, usr_act, col_fecha_tt)
                                        fecha_reg_str = obtener_hora_peru().strftime("%d/%m/%Y %I:%M %p")
                                        registrar_evidencia_tiktok(
                                            doc_tiktok=doc_tiktok,
                                            fecha_registro=fecha_reg_str,
                                            fecha_live=col_fecha_tt,
                                            usuario=usr_act,
                                            codigo=cod_act,
                                            total_horas_str=total_tt_str,
                                            transmisiones_lista=transmisiones,
                                            drive_info=drive_info
                                        )

                                        st.balloons()
                                        if drive_info:
                                            st.success(f"🎉 **¡Reporte Exitoso!** Horas agregadas: **{total_tt_str}** (Total acumulado: **{total_str_final}** en {pestana_tt}). La foto se guardó en Google Drive para auditoría.")
                                        else:
                                            st.warning(f"Horas registradas con éxito (**{total_tt_str}**), pero la foto no se pudo subir a Drive ({drive_err}).")
                                        
                                        st.session_state.pop("res_tiktok_data", None)
                                        st.session_state.pop("id_archivo_tt_actual", None)
                                        st.session_state.uploader_key += 1
                                        st.rerun()
                                    except Exception as ex_tt:
                                        st.error(f"Error al guardar reporte: {ex_tt}")

                        with col_cancelar:
                            if st.button("🔄 Cancelar / Reintentar", use_container_width=True):
                                st.session_state.pop("res_tiktok_data", None)
                                st.session_state.pop("id_archivo_tt_actual", None)
                                st.session_state.uploader_key += 1
                                st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

            # Historial de TikTok
            with st.expander("📊 Consultar Mis Reportes de TikTok", expanded=True):
                fecha_busq_tt = st.date_input("Fecha a Consultar:", value=obtener_hora_peru().date(), key="cal_tt_history")
                pestana_tt_b = MESES_ESPANOL[fecha_busq_tt.month]
                df_hist_tt = cargar_datos_pestana_tiktok(pestana_tt_b)
                
                f_tt_str = fecha_busq_tt.strftime("%d/%m/%Y")
                fila_user_tt = df_hist_tt[df_hist_tt["Usuario"] == st.session_state.usuario_actual] if not df_hist_tt.empty and "Usuario" in df_hist_tt.columns else pd.DataFrame()
                
                if not fila_user_tt.empty and f_tt_str in df_hist_tt.columns:
                    val_t = str(fila_user_tt.iloc[0][f_tt_str]).strip()
                    val_t = val_t if val_t not in ["", "nan", "None", "-"] else "0 h 0 min"
                    st.dataframe(pd.DataFrame({"Fecha": [f_tt_str], "Horas Transmitidas": [val_t]}), use_container_width=True, hide_index=True)
                else:
                    st.caption(f"Sin transmisiones registradas para el {f_tt_str} en {pestana_tt_b}.")

                # Acumulado mensual TikTok
                tot_min_tt = 0
                if not fila_user_tt.empty:
                    cols_dias = [c for c in df_hist_tt.columns if c not in ["Usuario", "Codigo", "Meta"]]
                    for cd in cols_dias:
                        tot_min_tt += parsear_string_a_minutos(fila_user_tt.iloc[0][cd])
                
                st.markdown("---")
                col_tt1, col_tt2 = st.columns([1, 1.5])
                with col_tt1:
                    st.metric(f"Total TikTok en {pestana_tt_b.capitalize()}", formatear_minutos_a_string(tot_min_tt))
                with col_tt2:
                    meta_tt = 0
                    if not fila_user_tt.empty and "Meta" in df_hist_tt.columns:
                        try:
                            meta_tt = float(fila_user_tt.iloc[0]["Meta"])
                        except (ValueError, TypeError):
                            meta_tt = 0
                    if meta_tt > 0:
                        pct_tt = min(1.0, (tot_min_tt / 60.0) / meta_tt)
                        st.markdown(f"**Meta Mensual TikTok:** {(tot_min_tt/60.0):.1f} h / {meta_tt:.0f} h (**{pct_tt*100:.1f}%**)")
                        st.progress(pct_tt)

                # Historial de capturas enviadas por el asesor
                df_mis_ev = cargar_evidencias_tiktok()
                if not df_mis_ev.empty and "Usuario" in df_mis_ev.columns:
                    ev_user = df_mis_ev[df_mis_ev["Usuario"] == st.session_state.usuario_actual]
                    if not ev_user.empty:
                        st.markdown("---")
                        st.markdown("###### 📸 Mis Capturas Subidas Recientes")
                        for _, row_ev in ev_user.iloc[::-1].head(5).iterrows():
                            f_l = row_ev.get("Fecha Live", "-")
                            h_t = row_ev.get("Tiempo Total", "-")
                            l_k = row_ev.get("Link Captura", "")
                            c_t1, c_t2 = st.columns([3, 1])
                            with c_t1:
                                st.caption(f"• **Live {f_l}:** `{h_t}` ({row_ev.get('Detalle Transmisiones', '')})")
                            with c_t2:
                                if l_k and str(l_k).startswith("http"):
                                    st.markdown(f"[🔗 Ver Foto]({l_k})")

        # =========================================================
        # PESTAÑA 3: PANEL GENERAL ADMINISTRADOR
        # =========================================================
        if es_admin:
            with tab_reporte:
                st.markdown('<div class="saas-card">', unsafe_allow_html=True)
                st.markdown("#### 📊 Reporte General y Control de Asistencia")
                st.caption("Visión global de las asistencias diarias y cumplimiento de metas del equipo.")

                col_admin_f, col_admin_kpi = st.columns([1, 2])
                with col_admin_f:
                    fecha_admin = st.date_input("Fecha de Consulta:", value=obtener_hora_peru().date(), key="cal_admin_filter")
                
                pestana_admin = MESES_ESPANOL[fecha_admin.month]
                df_admin = cargar_datos_pestana(pestana_admin)
                
                f_adm_str = fecha_admin.strftime("%d/%m/%Y")
                c_adm_e = f"{f_adm_str} (Entrada)"
                c_adm_rs = f"{f_adm_str} (Inicio Ref)"
                c_adm_rr = f"{f_adm_str} (Fin Ref)"
                c_adm_s = f"{f_adm_str} (Salida)"

                if not df_admin.empty:
                    sub_dia, sub_semana, sub_mes, sub_tt_general, sub_auditoria_tt = st.tabs([
                        "📋 Asistencia Diaria", 
                        "📅 Asistencia Semanal",
                        "📈 Asistencia Mensual", 
                        "📹 Reporte General TikTok",
                        "📸 Auditoría Capturas TikTok"
                    ])
                    
                    with sub_dia:
                        if c_adm_e in df_admin.columns and c_adm_s in df_admin.columns:
                            dict_semanas_adm = obtener_semanas_laborales(fecha_admin.year, fecha_admin.month)
                            sem_dia_num = obtener_num_semana_para_fecha(fecha_admin, dict_semanas_adm)
                            meta_col_dia = f"Meta S{sem_dia_num}"

                            rows_reporte = []
                            for _, r in df_admin.iterrows():
                                ve = str(r[c_adm_e]).strip() if c_adm_e in df_admin.columns else "Falta"
                                vrs = str(r[c_adm_rs]).strip() if c_adm_rs in df_admin.columns else "-"
                                vrr = str(r[c_adm_rr]).strip() if c_adm_rr in df_admin.columns else "-"
                                vs = str(r[c_adm_s]).strip() if c_adm_s in df_admin.columns else "Falta"
                                
                                m_netos = calcular_minutos_netos_raw(ve, vrs, vrr, vs)
                                
                                meta_ind = "-"
                                if meta_col_dia in df_admin.columns and not pd.isna(r[meta_col_dia]):
                                    v_m = str(r[meta_col_dia]).split('.')[0].strip()
                                    if v_m not in ["", "-", "nan", "None"]:
                                        meta_ind = f"{v_m} h (S{sem_dia_num})"
                                elif "Meta" in df_admin.columns and not pd.isna(r["Meta"]):
                                    v_m = str(r["Meta"]).split('.')[0].strip()
                                    if v_m not in ["", "-", "nan", "None"]:
                                        meta_ind = f"{v_m} h"
                                
                                rows_reporte.append({
                                    "Asesor": r["Usuario"],
                                    "Meta Semanal": meta_ind,
                                    "Entrada": ve,
                                    "Inicio Almuerzo": vrs,
                                    "Fin Almuerzo": vrr,
                                    "Salida": vs,
                                    "Horas Netas": formatear_minutos_a_string(m_netos)
                                })
                            
                            df_rep = pd.DataFrame(rows_reporte)
                            st.dataframe(df_rep, use_container_width=True, hide_index=True)
                        else:
                            st.info(f"No hay registros de asistencia para el día **{f_adm_str}** en la pestaña {pestana_admin}.")

                    with sub_semana:
                        dict_semanas_adm = obtener_semanas_laborales(fecha_admin.year, fecha_admin.month)
                        sem_adm_def = obtener_num_semana_para_fecha(fecha_admin, dict_semanas_adm)
                        opcs_sem_adm = [dict_semanas_adm[k]["label"] for k in sorted(dict_semanas_adm.keys())]
                        idx_def_adm = max(0, min(sem_adm_def - 1, len(opcs_sem_adm) - 1))
                        
                        col_adm_s1, col_adm_s2 = st.columns([1.5, 1])
                        with col_adm_s1:
                            sel_sem_label_adm = st.selectbox("Seleccionar Semana a Evaluar:", opcs_sem_adm, index=idx_def_adm, key="adm_filtro_sem")
                            
                        sem_num_adm = [k for k, v in dict_semanas_adm.items() if v["label"] == sel_sem_label_adm][0]
                        info_s_adm = dict_semanas_adm[sem_num_adm]
                        meta_col_name = info_s_adm["meta_col"]
                        
                        filas_semana_admin = []
                        total_horas_equipo_sem = 0.0
                        cumplieron_meta_cnt = 0
                        con_meta_cnt = 0
                        
                        for _, r in df_admin.iterrows():
                            u = r["Usuario"]
                            min_asesor_sem = 0
                            dias_asistidos_sem = 0
                            
                            for dia_int in info_s_adm["dias"]:
                                f_d_str = f"{dia_int:02d}/{fecha_admin.month:02d}/{fecha_admin.year}"
                                ce = f"{f_d_str} (Entrada)"
                                cs = f"{f_d_str} (Salida)"
                                if ce in df_admin.columns and cs in df_admin.columns:
                                    ve = str(r[ce]).strip()
                                    vrs = str(r[f"{f_d_str} (Inicio Ref)"]).strip() if f"{f_d_str} (Inicio Ref)" in df_admin.columns else ""
                                    vrr = str(r[f"{f_d_str} (Fin Ref)"]).strip() if f"{f_d_str} (Fin Ref)" in df_admin.columns else ""
                                    vs = str(r[cs]).strip()
                                    m_d = calcular_minutos_netos_raw(ve, vrs, vrr, vs)
                                    if m_d > 0:
                                        min_asesor_sem += m_d
                                        dias_asistidos_sem += 1
                                        
                            meta_s_val = 0.0
                            if meta_col_name in df_admin.columns and not pd.isna(r[meta_col_name]):
                                try:
                                    raw_v = str(r[meta_col_name]).strip()
                                    if raw_v not in ["", "nan", "None", "-"]:
                                        meta_s_val = float(raw_v)
                                except (ValueError, TypeError):
                                    meta_s_val = 0.0
                                    
                            horas_sem_num = min_asesor_sem / 60.0
                            total_horas_equipo_sem += horas_sem_num
                            
                            if meta_s_val > 0:
                                con_meta_cnt += 1
                                pct_s_num = (horas_sem_num / meta_s_val) * 100.0
                                pct_str = f"{pct_s_num:.1f}%"
                                if pct_s_num >= 100.0:
                                    estado_str = "✅ Meta Cumplida"
                                    cumplieron_meta_cnt += 1
                                elif pct_s_num >= 50.0:
                                    estado_str = "⏳ En Progreso"
                                elif min_asesor_sem > 0:
                                    estado_str = "⚠️ Por Debajo"
                                else:
                                    estado_str = "❌ Sin Horas"
                            else:
                                pct_str = "N/A"
                                estado_str = "Sin Meta" if min_asesor_sem == 0 else "Registrando"
                                
                            filas_semana_admin.append({
                                "Asesor": u,
                                "Días Asistidos": dias_asistidos_sem,
                                "Horas de la Semana": formatear_minutos_a_string(min_asesor_sem),
                                "Meta Semanal": f"{meta_s_val:.0f} h" if meta_s_val > 0 else "-",
                                "% Cumplimiento": pct_str,
                                "Estado": estado_str
                            })
                            
                        with col_adm_s2:
                            st.metric(
                                "Total Horas Equipo en la Semana",
                                f"{total_horas_equipo_sem:.1f} h",
                                f"{cumplieron_meta_cnt}/{con_meta_cnt} con meta alcanzada" if con_meta_cnt > 0 else None
                            )
                            
                        st.markdown(f"###### Resumen del Equipo — {info_s_adm['label']}")
                        st.dataframe(pd.DataFrame(filas_semana_admin), use_container_width=True, hide_index=True)

                    with sub_mes:
                        st.markdown(f"###### Resumen Consolidado - Mes de {pestana_admin}")
                        dict_semanas_adm = obtener_semanas_laborales(fecha_admin.year, fecha_admin.month)
                        resumen_mensual = []
                        
                        for _, r in df_admin.iterrows():
                            u = r["Usuario"]
                            fila_user_df = df_admin[df_admin["Usuario"] == u]
                            resumen_semanas_u, min_tot_u, meta_tot_u = calcular_resumen_semanal_asesor(
                                fila_user_df, df_admin, fecha_admin.year, fecha_admin.month, dict_semanas_adm
                            )
                            
                            dias_asistidos_mes = sum(info_w["dias_asistidos"] for info_w in resumen_semanas_u.values())
                            horas_num = min_tot_u / 60.0
                            pct_str = f"{(horas_num / meta_tot_u * 100):.1f}%" if meta_tot_u > 0 else "N/A"
                            
                            row_m = {
                                "Asesor / Trabajador": u,
                                "Días Asistidos": dias_asistidos_mes,
                                "Horas Totales (Mes)": formatear_minutos_a_string(min_tot_u),
                                "Meta Mes Total": f"{meta_tot_u:.0f} h" if meta_tot_u > 0 else "-",
                                "% Cumplimiento": pct_str
                            }
                            
                            for w_num in sorted(dict_semanas_adm.keys()):
                                w_h = resumen_semanas_u[w_num]["horas_str"]
                                w_meta = resumen_semanas_u[w_num]["meta_horas"]
                                col_lbl = f"S{w_num} ({w_meta:.0f}h)" if w_meta > 0 else f"S{w_num}"
                                row_m[col_lbl] = w_h
                                
                            resumen_mensual.append(row_m)
                            
                        st.dataframe(pd.DataFrame(resumen_mensual), use_container_width=True, hide_index=True)

                    with sub_tt_general:
                        st.markdown(f"###### 📹 Reporte General y Desempeño TikTok Live — Mes de {pestana_admin}")
                        st.caption("Seguimiento de horas transmitidas, días con live y métricas de todo el equipo en TikTok.")
                        
                        df_tt_admin = cargar_datos_pestana_tiktok(pestana_admin)
                        dict_semanas_adm = obtener_semanas_laborales(fecha_admin.year, fecha_admin.month)
                        sem_act_adm = obtener_num_semana_para_fecha(fecha_admin, dict_semanas_adm)
                        info_sem_adm = dict_semanas_adm.get(sem_act_adm, {})
                        
                        f_adm_str = fecha_admin.strftime("%d/%m/%Y")
                        
                        # Lista consolidada de asesores
                        lista_asesores = []
                        if not df_admin.empty and "Usuario" in df_admin.columns:
                            lista_asesores = list(df_admin["Usuario"].dropna().unique())
                        if not df_tt_admin.empty and "Usuario" in df_tt_admin.columns:
                            for u_tt in df_tt_admin["Usuario"].dropna().unique():
                                if u_tt not in lista_asesores:
                                    lista_asesores.append(u_tt)
                        lista_asesores = sorted(lista_asesores)
                        
                        if lista_asesores:
                            # Columnas de fechas registradas en TikTok
                            cols_fechas_tt = []
                            if not df_tt_admin.empty:
                                for c in df_tt_admin.columns:
                                    partes_c = str(c).strip().split("/")
                                    if len(partes_c) == 3:
                                        cols_fechas_tt.append(str(c).strip())
                                        
                            # Ordenar fechas cronológicamente de forma segura
                            try:
                                cols_fechas_tt = sorted(cols_fechas_tt, key=lambda x: datetime.strptime(x, "%d/%m/%Y"))
                            except Exception:
                                cols_fechas_tt = sorted(cols_fechas_tt)
                                
                            dias_sem_actual = info_sem_adm.get("dias", [])
                            cols_sem_actual = [f"{d:02d}/{fecha_admin.month:02d}/{fecha_admin.year}" for d in dias_sem_actual]
                            
                            filas_tt_resumen = []
                            total_minutos_equipo_mes = 0
                            total_minutos_equipo_dia = 0
                            total_minutos_equipo_sem = 0
                            asesores_activos_mes = 0
                            top_asesor_nombre = "-"
                            top_asesor_minutos = 0
                            
                            for u in lista_asesores:
                                row_u = df_tt_admin[df_tt_admin["Usuario"] == u] if not df_tt_admin.empty and "Usuario" in df_tt_admin.columns else pd.DataFrame()
                                
                                min_u_dia = 0
                                min_u_sem = 0
                                min_u_mes = 0
                                dias_con_live = 0
                                
                                if not row_u.empty:
                                    # Minutos hoy
                                    if f_adm_str in df_tt_admin.columns:
                                        min_u_dia = parsear_string_a_minutos(row_u.iloc[0][f_adm_str])
                                        
                                    # Minutos semana seleccionada
                                    for c_s in cols_sem_actual:
                                        if c_s in df_tt_admin.columns:
                                            min_u_sem += parsear_string_a_minutos(row_u.iloc[0][c_s])
                                            
                                    # Minutos mes y conteo de días activos
                                    for c_m in cols_fechas_tt:
                                        if c_m in df_tt_admin.columns:
                                            m_val = parsear_string_a_minutos(row_u.iloc[0][c_m])
                                            if m_val > 0:
                                                min_u_mes += m_val
                                                dias_con_live += 1
                                                
                                    # Meta TikTok
                                    meta_tt_val = 0.0
                                    meta_col_s = f"Meta S{sem_act_adm}"
                                    if meta_col_s in df_tt_admin.columns and not pd.isna(row_u.iloc[0][meta_col_s]):
                                        try:
                                            meta_tt_val = float(str(row_u.iloc[0][meta_col_s]).strip())
                                        except (ValueError, TypeError):
                                            meta_tt_val = 0.0
                                    elif "Meta" in df_tt_admin.columns and not pd.isna(row_u.iloc[0]["Meta"]):
                                        try:
                                            meta_tt_val = float(str(row_u.iloc[0]["Meta"]).strip())
                                        except (ValueError, TypeError):
                                            meta_tt_val = 0.0
                                else:
                                    meta_tt_val = 0.0
                                    
                                total_minutos_equipo_dia += min_u_dia
                                total_minutos_equipo_sem += min_u_sem
                                total_minutos_equipo_mes += min_u_mes
                                
                                if min_u_mes > 0:
                                    asesores_activos_mes += 1
                                    if min_u_mes > top_asesor_minutos:
                                        top_asesor_minutos = min_u_mes
                                        top_asesor_nombre = u
                                        
                                # Porcentaje de cumplimiento
                                if meta_tt_val > 0:
                                    pct_num = ((min_u_mes / 60.0) / meta_tt_val) * 100.0
                                    pct_str = f"{pct_num:.1f}%"
                                else:
                                    pct_str = "N/A"
                                    
                                if min_u_dia > 0:
                                    estado_tt = "🔴 Transmitió Hoy"
                                elif min_u_sem > 0:
                                    estado_tt = "🟡 Activo en la Semana"
                                elif min_u_mes > 0:
                                    estado_tt = "⚪ Activo en el Mes"
                                else:
                                    estado_tt = "❌ Sin Transmisiones"
                                    
                                nom_sem_corta = info_sem_adm.get("label", f"Semana {sem_act_adm}").split("(")[0].strip()
                                filas_tt_resumen.append({
                                    "Asesor": u,
                                    f"Horas Día ({f_adm_str})": formatear_minutos_a_string(min_u_dia) if min_u_dia > 0 else "-",
                                    f"Horas {nom_sem_corta}": formatear_minutos_a_string(min_u_sem),
                                    "Días con Live": dias_con_live,
                                    "Total Horas Mes": formatear_minutos_a_string(min_u_mes),
                                    "Meta TikTok": f"{meta_tt_val:.0f} h" if meta_tt_val > 0 else "-",
                                    "% Cumplimiento": pct_str,
                                    "Estado": estado_tt
                                })
                                
                            # Métricas visuales
                            col_tt_k1, col_tt_k2, col_tt_k3, col_tt_k4 = st.columns(4)
                            with col_tt_k1:
                                st.metric("Total Mes Equipo", formatear_minutos_a_string(total_minutos_equipo_mes), f"{asesores_activos_mes}/{len(lista_asesores)} asesores activos")
                            with col_tt_k2:
                                st.metric(f"Total {info_sem_adm.get('label', 'Semana').split('(')[0].strip()}", formatear_minutos_a_string(total_minutos_equipo_sem))
                            with col_tt_k3:
                                st.metric(f"Total Día ({f_adm_str})", formatear_minutos_a_string(total_minutos_equipo_dia))
                            with col_tt_k4:
                                st.metric("Top Asesor TikTok", top_asesor_nombre if top_asesor_nombre != "-" else "Sin datos", formatear_minutos_a_string(top_asesor_minutos) if top_asesor_minutos > 0 else None)
                                
                            st.markdown("---")
                            st.markdown(f"###### 📊 Tabla Consolidada de Todo el Equipo — TikTok Live ({pestana_admin})")
                            st.dataframe(pd.DataFrame(filas_tt_resumen), use_container_width=True, hide_index=True)
                            
                            # Matriz Diaria detallada
                            if cols_fechas_tt:
                                with st.expander("📅 Ver Matriz Diaria Detallada de TikTok (Día por Día)", expanded=False):
                                    matriz_tt = []
                                    for u in lista_asesores:
                                        row_u = df_tt_admin[df_tt_admin["Usuario"] == u] if not df_tt_admin.empty and "Usuario" in df_tt_admin.columns else pd.DataFrame()
                                        fila_m = {"Asesor": u}
                                        for c_f in cols_fechas_tt:
                                            if not row_u.empty and c_f in df_tt_admin.columns:
                                                v_c = str(row_u.iloc[0][c_f]).strip()
                                                fila_m[c_f] = v_c if v_c not in ["", "nan", "None", "0 h 0 min", "-"] else "-"
                                            else:
                                                fila_m[c_f] = "-"
                                        matriz_tt.append(fila_m)
                                    st.dataframe(pd.DataFrame(matriz_tt), use_container_width=True, hide_index=True)
                        else:
                            st.info(f"No se encontraron datos en la hoja de TikTok para el mes de {pestana_admin}.")

                    with sub_auditoria_tt:
                        st.markdown("###### 📸 Historial y Auditoría de Capturas TikTok")
                        st.caption("Inspecciona las capturas originales subidas a Google Drive para contrastar con las lecturas de la IA.")
                        
                        df_auditoria = cargar_evidencias_tiktok()
                        if not df_auditoria.empty and "Usuario" in df_auditoria.columns:
                            col_f_usr, col_f_dia, col_f_ref = st.columns([1.3, 1.3, 0.8])
                            with col_f_usr:
                                lista_usrs = ["Todos"] + sorted(list(df_auditoria["Usuario"].dropna().unique()))
                                sel_usr = st.selectbox("Filtrar por Asesor:", lista_usrs, key="aud_filtro_asesor")
                            with col_f_dia:
                                lista_fechas = ["Todas"] + sorted(list(df_auditoria["Fecha Live"].dropna().unique()), reverse=True)
                                sel_fecha = st.selectbox("Filtrar por Fecha del Live:", lista_fechas, key="aud_filtro_fecha")
                            with col_f_ref:
                                st.write("")
                                st.write("")
                                if st.button("🔄 Refrescar", use_container_width=True, help="Recargar datos directamente desde Google Sheets"):
                                    st.cache_data.clear()
                                    st.rerun()
                                
                            df_aud_filtrada = df_auditoria.copy()
                            if sel_usr != "Todos":
                                df_aud_filtrada = df_aud_filtrada[df_aud_filtrada["Usuario"] == sel_usr]
                            if sel_fecha != "Todas":
                                df_aud_filtrada = df_aud_filtrada[df_aud_filtrada["Fecha Live"] == sel_fecha]
                                
                            st.caption(f"Mostrando **{len(df_aud_filtrada)}** capturas registradas:")
                            
                            # Mostrar las más recientes primero
                            for idx_ev, (_, r_aud) in enumerate(df_aud_filtrada.iloc[::-1].iterrows()):
                                a_usr = str(r_aud.get("Usuario", "-"))
                                a_flive = str(r_aud.get("Fecha Live", "-"))
                                a_freg = str(r_aud.get("Fecha Registro", "-"))
                                a_tot = str(r_aud.get("Tiempo Total", "-"))
                                a_det = str(r_aud.get("Detalle Transmisiones", "-"))
                                a_link = str(r_aud.get("Link Captura", ""))
                                a_fid = str(r_aud.get("Drive File ID", "")).strip()
                                
                                with st.expander(f"📷 {a_usr} — Live: {a_flive} ({a_tot})", expanded=False):
                                    col_info_aud, col_img_aud = st.columns([1.2, 1.8])
                                    with col_info_aud:
                                        st.markdown(f"**Asesor:** {a_usr}")
                                        st.markdown(f"**Fecha del Live:** `{a_flive}`")
                                        st.markdown(f"**Fecha y Hora Registro:** `{a_freg}`")
                                        st.markdown(f"**Tiempo Reconocido:** `{a_tot}`")
                                        st.markdown(f"**Transmisiones:** {a_det}")
                                        st.write("")
                                        
                                        col_btn_drive, col_btn_del = st.columns([1.2, 1])
                                        with col_btn_drive:
                                            if a_link and a_link.startswith("http"):
                                                st.link_button("🔍 Ver en Drive", a_link, use_container_width=True)
                                            else:
                                                st.caption("Sin enlace directo a Drive.")
                                                
                                        with col_btn_del:
                                            btn_del_key = f"del_btn_{idx_ev}_{a_fid[:6] if a_fid else idx_ev}"
                                            if st.button("🗑️ Eliminar", key=btn_del_key, use_container_width=True, help="Eliminar este reporte del sistema y recalcular horas acumuladas"):
                                                st.session_state[f"confirm_{btn_del_key}"] = True
                                                
                                        if st.session_state.get(f"confirm_{btn_del_key}", False):
                                            st.warning("⚠️ ¿Eliminar este reporte del sistema?")
                                            col_c1, col_c2 = st.columns(2)
                                            with col_c1:
                                                if st.button("Sí, Eliminar", key=f"yes_{btn_del_key}", type="primary", use_container_width=True):
                                                    with st.spinner("Eliminando y recalculando horas..."):
                                                        ok_del, err_del = eliminar_reporte_evidencia_tiktok(a_usr, a_flive, a_freg, a_fid)
                                                        if ok_del:
                                                            st.session_state.pop(f"confirm_{btn_del_key}", None)
                                                            st.success("✅ Reporte eliminado.")
                                                            st.rerun()
                                                        else:
                                                            st.error(f"Error: {err_del}")
                                            with col_c2:
                                                if st.button("Cancelar", key=f"no_{btn_del_key}", use_container_width=True):
                                                    st.session_state.pop(f"confirm_{btn_del_key}", None)
                                                    st.rerun()
                                            
                                    with col_img_aud:
                                        if a_fid and a_fid not in ["nan", "None", ""]:
                                            thumb_url = f"https://drive.google.com/thumbnail?id={a_fid}&sz=w1000"
                                            st.image(thumb_url, caption=f"Captura de {a_usr} ({a_flive})", use_container_width=True)
                                        elif a_link and a_link.startswith("http"):
                                            st.markdown(f"[🔗 Ver captura completa en Drive]({a_link})")
                                        else:
                                            st.info("Sin previsualización.")
                                            
                            st.markdown("---")
                            with st.expander("📄 Ver Tabla Completa de Registros"):
                                st.dataframe(df_aud_filtrada, use_container_width=True, hide_index=True)
                        else:
                            st.info("Aún no hay capturas de TikTok registradas en la pestaña EVIDENCIAS_CAPTURA.")
                else:
                    st.caption("No se encontraron datos en la hoja del mes seleccionado.")

                st.markdown('</div>', unsafe_allow_html=True)

except Exception as e:
    st.error("⚠️ Error de conexión con los servicios de datos.")
    st.code(str(e))
