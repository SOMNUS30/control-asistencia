import streamlit as st
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import pandas as pd
from datetime import datetime, timedelta, timezone
import math
import io
import json
import base64
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
        
        div.stButton > button[kind="primary"],
        div.stButton > button:has(div:contains("Entrada")),
        div.stButton > button:has(div:contains("Salida")),
        div.stButton > button:has(div:contains("INICIAR")) {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
            color: #ffffff !important;
            border: none !important;
        }
        div.stButton > button[kind="primary"] * {
            color: #ffffff !important;
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

        modelos_a_probar = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.0-flash-lite"]
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
            
            # Componente de geolocalización con clave dinámica (se reinicia después de cada marcado)
            loc = obtener_geolocalizacion(st.session_state.geo_key)
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
            # CONSULTA DE HISTORIAL Y META MENSUAL
            # =========================================================
            with st.expander("📅 Consultar Mi Historial y Progreso Mensual", expanded=True):
                col_cal, col_meta = st.columns([1, 1.5])
                
                with col_cal:
                    fecha_busqueda = st.date_input("Seleccionar Fecha:", value=obtener_hora_peru().date(), key="cal_asesor_view")
                    
                pestana_busq = MESES_ESPANOL[fecha_busqueda.month]
                df_historial = cargar_datos_pestana(pestana_busq)
                
                fila_user_hist = df_historial[df_historial["Usuario"] == st.session_state.usuario_actual] if not df_historial.empty and "Usuario" in df_historial.columns else pd.DataFrame()
                
                f_str = fecha_busqueda.strftime("%d/%m/%Y")
                c_e, c_rs, c_rr, c_s = f"{f_str} (Entrada)", f"{f_str} (Inicio Ref)", f"{f_str} (Fin Ref)", f"{f_str} (Salida)"
                
                if not fila_user_hist.empty and c_e in df_historial.columns and c_s in df_historial.columns:
                    ve = str(fila_user_hist.iloc[0][c_e]).strip()
                    vrs = str(fila_user_hist.iloc[0][c_rs]).strip() if c_rs in df_historial.columns else "-"
                    vrr = str(fila_user_hist.iloc[0][c_rr]).strip() if c_rr in df_historial.columns else "-"
                    vs = str(fila_user_hist.iloc[0][c_s]).strip()
                    min_dia = calcular_minutos_netos_raw(ve, vrs, vrr, vs)
                    
                    df_day = pd.DataFrame({
                        "Fecha": [f_str],
                        "Entrada": [ve],
                        "Inicio Ref": [vrs],
                        "Fin Ref": [vrr],
                        "Salida": [vs],
                        "Total Neto": [formatear_minutos_a_string(min_dia)]
                    })
                    st.dataframe(df_day, use_container_width=True, hide_index=True)
                else:
                    st.caption(f"Sin registros para el {f_str} en {pestana_busq}.")

                total_minutos_mes = 0
                if not fila_user_hist.empty:
                    for col in df_historial.columns:
                        if " (Entrada)" in col:
                            base_f = col.replace(" (Entrada)", "")
                            if f"{base_f} (Salida)" in df_historial.columns:
                                e_v = str(fila_user_hist.iloc[0][col]).strip()
                                rs_v = str(fila_user_hist.iloc[0][f"{base_f} (Inicio Ref)"]).strip() if f"{base_f} (Inicio Ref)" in df_historial.columns else ""
                                rr_v = str(fila_user_hist.iloc[0][f"{base_f} (Fin Ref)"]).strip() if f"{base_f} (Fin Ref)" in df_historial.columns else ""
                                s_v = str(fila_user_hist.iloc[0][f"{base_f} (Salida)"]).strip()
                                total_minutos_mes += calcular_minutos_netos_raw(e_v, rs_v, rr_v, s_v)

                meta_horas = 0
                if not fila_user_hist.empty and "Meta" in df_historial.columns:
                    try:
                        meta_horas = float(fila_user_hist.iloc[0]["Meta"])
                        if pd.isna(meta_horas) or meta_horas <= 0:
                            meta_horas = 0
                    except (ValueError, TypeError):
                        meta_horas = 0

                st.markdown("---")
                col_m1, col_m2 = st.columns([1, 1.5])
                with col_m1:
                    st.metric(f"Total Acumulado en {pestana_busq.capitalize()}", formatear_minutos_a_string(total_minutos_mes))
                with col_m2:
                    if meta_horas > 0:
                        total_horas = total_minutos_mes / 60.0
                        pct = min(1.0, total_horas / meta_horas)
                        st.markdown(f"**Meta Mensual:** {total_horas:.1f} h / {meta_horas:.0f} h (**{pct*100:.1f}%**)")
                        st.progress(pct)
                        min_faltantes = int((meta_horas * 60) - total_minutos_mes)
                        if min_faltantes > 0:
                            st.caption(f"🎯 Faltan **{formatear_minutos_a_string(min_faltantes)}** para alcanzar tu meta.")
                        else:
                            st.success("🎉 ¡Felicidades! Has completado tu meta del mes.")

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
                                with st.spinner("Guardando en REPORTES TIKTOK..."):
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

                                        st.balloons()
                                        st.success(f"Reporte subido con éxito: **{total_tt_str}** agregados. Total acumulado del día: **{total_str_final}** en {pestana_tt}.")
                                        
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
                    sub_dia, sub_mes = st.tabs(["📋 Asistencia Diaria", "📈 Consolidado Mensual del Equipo"])
                    
                    with sub_dia:
                        if c_adm_e in df_admin.columns and c_adm_s in df_admin.columns:
                            rows_reporte = []
                            for _, r in df_admin.iterrows():
                                ve = str(r[c_adm_e]).strip() if c_adm_e in df_admin.columns else "Falta"
                                vrs = str(r[c_adm_rs]).strip() if c_adm_rs in df_admin.columns else "-"
                                vrr = str(r[c_adm_rr]).strip() if c_adm_rr in df_admin.columns else "-"
                                vs = str(r[c_adm_s]).strip() if c_adm_s in df_admin.columns else "Falta"
                                
                                m_netos = calcular_minutos_netos_raw(ve, vrs, vrr, vs)
                                meta_ind = str(r["Meta"]).split('.')[0].strip() if "Meta" in df_admin.columns and not pd.isna(r["Meta"]) else "-"
                                
                                rows_reporte.append({
                                    "Asesor": r["Usuario"],
                                    "Meta (H)": f"{meta_ind} h" if meta_ind != "-" else "-",
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

                    with sub_mes:
                        st.markdown(f"###### Resumen Consolidado - Mes de {pestana_admin}")
                        cols_ent = [c for c in df_admin.columns if " (Entrada)" in c]
                        resumen_mensual = []
                        
                        for _, r in df_admin.iterrows():
                            u = r["Usuario"]
                            min_asesor = 0
                            dias_asistidos = 0
                            
                            for ce in cols_ent:
                                b_f = ce.replace(" (Entrada)", "")
                                cs = f"{b_f} (Salida)"
                                if cs in df_admin.columns:
                                    ve = str(r[ce]).strip()
                                    vrs = str(r[f"{b_f} (Inicio Ref)"]).strip() if f"{b_f} (Inicio Ref)" in df_admin.columns else ""
                                    vrr = str(r[f"{b_f} (Fin Ref)"]).strip() if f"{b_f} (Fin Ref)" in df_admin.columns else ""
                                    vs = str(r[cs]).strip()
                                    m_d = calcular_minutos_netos_raw(ve, vrs, vrr, vs)
                                    if m_d > 0:
                                        min_asesor += m_d
                                        dias_asistidos += 1
                                        
                            meta_v = 0
                            if "Meta" in df_admin.columns and not pd.isna(r["Meta"]):
                                try:
                                    meta_v = float(str(r["Meta"]).strip())
                                except (ValueError, TypeError):
                                    meta_v = 0
                                    
                            horas_num = min_asesor / 60.0
                            pct_str = f"{(horas_num / meta_v * 100):.1f}%" if meta_v > 0 else "N/A"
                            
                            resumen_mensual.append({
                                "Asesor / Trabajador": u,
                                "Días Asistidos": dias_asistidos,
                                "Horas Totales": formatear_minutos_a_string(min_asesor),
                                "Meta Asignada": f"{meta_v:.0f} h" if meta_v > 0 else "-",
                                "% Cumplimiento": pct_str
                            })
                            
                        st.dataframe(pd.DataFrame(resumen_mensual), use_container_width=True, hide_index=True)
                else:
                    st.caption("No se encontraron datos en la hoja del mes seleccionado.")

                st.markdown('</div>', unsafe_allow_html=True)

except Exception as e:
    st.error("⚠️ Error de conexión con los servicios de datos.")
    st.code(str(e))
