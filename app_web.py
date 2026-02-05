import requests
import streamlit as st
import hashlib
import pandas as pd
import time
import unicodedata
import re
import datetime
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math


WORKER_URL = "https://admin.bonbon-peach.com/api"
API_KEY=st.secrets["API_KEY"].strip()

R2_INGREDIENTES = "ingredientes"
R2_RECETAS = "recetas"
R2_MODIFICADORES = "modificadores"
R2_PRECIOS = "precios"
R2_VENTAS = "ventas"
R2_INVENTARIO = "inventario"

COMISION_TARJETA = 4.0406  

USERS = st.secrets["users"]


# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="BonBon - Peach · Sistema de control",
    page_icon="🍑",
    layout="wide",
    initial_sidebar_state="expanded"
)


# --- CONSTANTES ---
COMISION_BASE_PORCENTAJE = 3.5
TASA_IVA_PORCENTAJE = 16.0
COMISION_TARJETA = COMISION_BASE_PORCENTAJE * (1 + (TASA_IVA_PORCENTAJE / 100))
SESSION_TIMEOUT_MIN = 30 

# --- DICCIONARIOS PARA TRADUCCIÓN DE FECHAS ---
DIAS_ESP = {
    'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
    'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
}
ORDEN_DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

# --- AUTENTICACIÓN ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_auth():
    now = time.time()
    if st.session_state.get("authenticated"):
        last_activity = st.session_state.get("last_activity", now)
        if now - last_activity > SESSION_TIMEOUT_MIN * 60:
            st.session_state.clear()
            st.warning("⏱️ Sesión expirada por inactividad")
            st.rerun()
        st.session_state.last_activity = now
        return True

    st.title("🔐 Inicio de sesión")
    with st.form("login"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Ingresar")

    if submit:
        if username in USERS:
            if hash_password(password) == USERS[username]["password"]:
                st.session_state.authenticated = True
                st.session_state.usuario = username
                st.session_state.rol = USERS[username]["rol"]
                st.session_state.last_activity = now
                st.rerun()
        st.error("Usuario o contraseña incorrectos")
    return False

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .stApp { background-color: #FFF6FB; }
    .main .block-container {
        background-color: #FFFFFF;
        border-radius: 15px;
        padding: 1rem 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    }
    h1, h2, h3 { color: #4B2840; }
    .section-header {
        font-size: 1.5rem; color: #4B2840;
        border-bottom: 3px solid #F1B48B;
        padding-bottom: 0.5rem; margin-bottom: 1.5rem;
        font-weight: 600;
    }
    .stButton button {
        background-color: #F1B48B; color: white;
        border: none; border-radius: 8px; font-weight: bold;
    }
    .stButton button:hover { background-color: #CE8CCF; color: white; }
    [data-testid="stMetricValue"] { font-size: 1.5rem; color: #4B2840; }
</style>
""", unsafe_allow_html=True)

#_______________________________
#          Funciones de API
#_______________________________
def api_read(endpoint):
    try:
        r = requests.get(
            f"{WORKER_URL}/{endpoint}",
            headers={"X-API-Key": API_KEY, "User-Agent": "Streamlit-App/1.0", "Accept": "application/json"},
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list): return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"❌ Error de conexión con R2 ({endpoint}): {e}")
        return pd.DataFrame()

def api_write(endpoint, data):
    try:
        payload = data.to_dict("records") if isinstance(data, pd.DataFrame) else data
        r = requests.put(
            f"{WORKER_URL}/{endpoint}",
            json=payload,
            headers={"X-API-Key": API_KEY, "User-Agent": "Streamlit-App/1.0", "Accept": "application/json", "Content-Type": "application/json"},
            timeout=10
        )
        r.raise_for_status()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"❌ Error guardando {endpoint}: {e}")
        return False

def normalizar_texto(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().strip()
    texto = ' '.join(texto.split())
    texto = str(unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8'))
    return re.sub(r'[^a-z0-9\s]', '', texto)

def clean_and_convert_float(value_str, default=0.0):
    if isinstance(value_str, (int, float)): return round(float(value_str), 6)
    if not isinstance(value_str, str): return default
    cleaned = value_str.strip().replace('$', '').replace(',', '').replace('%', '')
    try: return round(float(cleaned), 6)
    except (ValueError, TypeError): return default

# --- GESTIÓN DE DATOS ---

# ============================================================================================================================
# INGREDIENTES
# ============================================================================================================================
def leer_ingredientes_base():
    df = api_read(R2_INGREDIENTES)
    ingredientes = []
    for _, r in df.iterrows():
        if not r.get("Ingrediente"): continue
        ingredientes.append({
            "nombre": r["Ingrediente"],
            "proveedor": r.get("Proveedor", ""),
            "unidad_compra": r.get("Unidad de Compra", ""),
            "costo_compra": clean_and_convert_float(r.get("Costo de Compra")),
            "cantidad_compra": clean_and_convert_float(r.get("Cantidad por Unidad de Compra")),
            "unidad_receta": r.get("Unidad Receta", ""),
            "costo_receta": clean_and_convert_float(r.get("Costo por Unidad Receta")),
            "nombre_normalizado": normalizar_texto(r["Ingrediente"])
        })
    return ingredientes

def guardar_ingredientes_base(data):
    df = pd.DataFrame([{
        "Ingrediente": i["nombre"], "Proveedor": i["proveedor"],
        "Unidad de Compra": i["unidad_compra"], "Costo de Compra": i["costo_compra"],
        "Cantidad por Unidad de Compra": i["cantidad_compra"],
        "Unidad Receta": i["unidad_receta"], "Costo por Unidad Receta": i["costo_receta"],
    } for i in data])
    return api_write(R2_INGREDIENTES, df)

# ============================================================================================================================
# RECETAS (Con soporte Sub-recetas y Modificadores Permitidos)
# ============================================================================================================================
def leer_recetas():
    df = api_read(R2_RECETAS)
    recetas = {}
    if df.empty or "Ingrediente" not in df.columns: return recetas

    productos = [c for c in df.columns if c not in ["Ingrediente", "ModificadoresValidos"]]
    
    # Pre-carga de modificadores válidos si existe la columna
    mods_map = {}
    if "ModificadoresValidos" in df.columns:
        # Esto asume que guardamos una fila especial o mapeamos de alguna forma
        # Para simplificar estructura tabular, buscaremos una fila donde Ingrediente == "CONFIG_MODS" o similar
        # O MEJOR: Usamos una hoja aparte o estructura JSON. 
        # TRUCO PANDAS: Usaremos filas donde el "Ingrediente" sea "__MODS__" para guardar la lista separada por comas
        pass

    for p in productos:
        recetas[p] = {"ingredientes": {}, "costo_total": 0, "modificadores_validos": []}

    ingredientes = leer_ingredientes_base()
    mapa_costos = {i["nombre"]: i["costo_receta"] for i in ingredientes}

    for _, r in df.iterrows():
        ing = r["Ingrediente"]
        
        # Detectar fila de configuración de modificadores
        if ing == "__MODS__":
            for p in productos:
                val = str(r.get(p, ""))
                if val and val != "nan":
                    recetas[p]["modificadores_validos"] = [x.strip() for x in val.split(",") if x.strip()]
            continue
            
        for p in productos:
            cant = clean_and_convert_float(r[p])
            if cant > 0:
                recetas[p]["ingredientes"][ing] = cant

    # Cálculo de costo
    for p in recetas:
        for ing, c in recetas[p]["ingredientes"].items():
            costo_u = mapa_costos.get(ing, 0)
            if costo_u == 0 and ing in recetas:
                pass 
            recetas[p]["costo_total"] += costo_u * c
            
    # Segunda pasada (Sub-recetas)
    for p in recetas:
        costo_recalc = 0
        for ing, c in recetas[p]["ingredientes"].items():
            val = mapa_costos.get(ing, 0)
            if val == 0 and ing in recetas:
                 val = recetas[ing]["costo_total"]
            costo_recalc += val * c
        if costo_recalc > 0:
            recetas[p]["costo_total"] = costo_recalc

    return recetas

def guardar_recetas(recetas):
    # Obtener todos los ingredientes únicos
    all_ings = sorted({i for r in recetas.values() for i in r["ingredientes"]})
    data = []
    
    # 1. Filas de ingredientes
    for ing in all_ings:
        fila = {"Ingrediente": ing}
        for p in recetas:
            fila[p] = recetas[p]["ingredientes"].get(ing, "")
        data.append(fila)
        
    # 2. Fila especial para Modificadores Válidos
    fila_mods = {"Ingrediente": "__MODS__"}
    hay_mods = False
    for p in recetas:
        mods_list = recetas[p].get("modificadores_validos", [])
        if mods_list:
            fila_mods[p] = ",".join(mods_list)
            hay_mods = True
        else:
            fila_mods[p] = ""
            
    if hay_mods:
        data.append(fila_mods)
        
    return api_write(R2_RECETAS, pd.DataFrame(data))

# ============================================================================================================================
# MODIFICADORES
# ============================================================================================================================
def leer_modificadores():
    df = api_read(R2_MODIFICADORES)
    modificadores = {}
    if df.empty: return modificadores
    
    if "Modificador" in df.columns:
        for mod_name, group in df.groupby("Modificador"):
            modificadores[mod_name] = {
                "precio_extra": float(group.iloc[0].get("Precio Extra", 0)),
                "ingredientes": {}
            }
            for _, r in group.iterrows():
                ing = r.get("Ingrediente Base")
                cant = clean_and_convert_float(r.get("Cantidad"))
                if ing and cant > 0:
                    modificadores[mod_name]["ingredientes"][ing] = cant
    return modificadores

def guardar_modificadores(mods_dict):
    data = []
    for nombre, info in mods_dict.items():
        if not info["ingredientes"]:
            data.append({
                "Modificador": nombre, "Precio Extra": info["precio_extra"],
                "Ingrediente Base": "", "Cantidad": 0
            })
        else:
            for ing, cant in info["ingredientes"].items():
                data.append({
                    "Modificador": nombre, "Precio Extra": info["precio_extra"],
                    "Ingrediente Base": ing, "Cantidad": cant
                })
    return api_write(R2_MODIFICADORES, pd.DataFrame(data))
    
def calcular_modificadores_totales(lista_mods):
    """
    lista_mods = [
        {"nombre": "...", "precio": 10, "cantidad": 2, "costo": 4},
        ...
    ]
    """
    total_precio = 0
    total_costo = 0

    for m in lista_mods or []:
        qty = m.get("cantidad", 0)
        total_precio += m.get("precio", 0) * qty
        total_costo += m.get("costo", 0) * qty

    return total_precio, total_costo

# ============================================================================================================================
# INVENTARIO
# ============================================================================================================================
def leer_inventario():
    inventario = {}
    try:
        df = api_read(R2_INVENTARIO)
        if df.empty: return inventario
        for _, fila in df.iterrows():
            nombre = str(fila.get('Ingrediente', '')).strip()
            if not nombre: continue
            inventario[nombre] = {
                'stock_actual': clean_and_convert_float(fila.get('Stock Actual')),
                'min': clean_and_convert_float(fila.get('Stock Mínimo')),
                'max': clean_and_convert_float(fila.get('Stock Máximo'))
            }
    except Exception as e: st.error(f"Error inv: {e}")
    return inventario

def guardar_inventario(inventario_data):
    try:
        datos = []
        for nombre, data in inventario_data.items():
            datos.append({
                'Ingrediente': nombre,
                'Stock Actual': round(data.get('stock_actual', 0.0), 4),
                'Stock Mínimo': round(data.get('min', 0.0), 4),
                'Stock Máximo': round(data.get('max', 0.0), 4),
            })
        return api_write(R2_INVENTARIO, pd.DataFrame(datos))
    except Exception as e: return False

# ============================================================================================================================
# VENTAS
# ============================================================================================================================
def leer_ventas(f_ini=None, f_fin=None):
    df = api_read(R2_VENTAS)
    if df.empty:
        return []

    # --- Fecha (compatibilidad total) ---
    if "Fecha" in df.columns:
        df["Fecha_DT"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
    elif "Fecha Venta" in df.columns:
        df["Fecha_DT"] = pd.to_datetime(df["Fecha Venta"], errors="coerce")
    else:
        return []

    df = df[df["Fecha_DT"].notna()].copy()
    df["Fecha_DT"] = df["Fecha_DT"].dt.normalize()

    if f_ini and f_fin:
        df = df[
            (df["Fecha_DT"].dt.date >= f_ini) &
            (df["Fecha_DT"].dt.date <= f_fin)
        ]

    # --- Tipos numéricos (SIN recalcular) ---
    cols_num = [
        "Cantidad", "Precio Unitario", "Total Venta Bruto",
        "Descuento ($)", "Comision ($)",
        "Total Venta Neta", "Costo Total", "Ganancia Neta"
    ]
    for col in cols_num:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    
    # --- Compatibilidad con histórico antiguo (CSV / Escritorio) ---
    if "Total Venta Neta" not in df.columns:
        df["Total Venta Neta"] = (
            df.get("Total Venta Bruto", 0)
            - df.get("Descuento ($)", 0)
            - df.get("Comision ($)", 0)
        )

    return df.to_dict("records")

def guardar_ventas(nuevas):
    df_actual = api_read(R2_VENTAS)
    df_nuevo = pd.DataFrame(nuevas)

    if df_nuevo.empty:
        return False

    # -----------------------------
    # FECHA (compatibilidad total)
    # -----------------------------
    if "Fecha" not in df_nuevo.columns:
        df_nuevo["Fecha"] = pd.Timestamp.today().strftime("%d/%m/%Y")
    else:
        df_nuevo["Fecha"] = (
            pd.to_datetime(df_nuevo["Fecha"], errors="coerce")
            .dt.strftime("%d/%m/%Y")
        )

    # -----------------------------
    # NUMÉRICOS
    # -----------------------------
    for col in [
        "Cantidad",
        "Precio Unitario",
        "Descuento (%)",
        "Costo Total"
    ]:
        if col not in df_nuevo.columns:
            df_nuevo[col] = 0

        df_nuevo[col] = (
            pd.to_numeric(df_nuevo[col], errors="coerce")
            .replace([np.inf, -np.inf], 0)
            .fillna(0)
        )

    # -----------------------------
    # CÁLCULOS (idénticos al histórico)
    # -----------------------------
    df_nuevo["Total Venta Bruto"] = df_nuevo["Precio Unitario"] * df_nuevo["Cantidad"]

    df_nuevo["Descuento ($)"] = (
        df_nuevo["Total Venta Bruto"]
        * (df_nuevo["Descuento (%)"] / 100)
    )

    df_nuevo["Comision ($)"] = df_nuevo.apply(
        lambda r: (
            (r["Total Venta Bruto"] - r["Descuento ($)"])
            * (COMISION_TARJETA / 100)
        )
        if r.get("Forma Pago") == "Tarjeta"
        else 0,
        axis=1
    )

    df_nuevo["Total Venta Neta"] = (
        df_nuevo["Total Venta Bruto"]
        - df_nuevo["Descuento ($)"]
        - df_nuevo["Comision ($)"]
    )

    df_nuevo["Ganancia Bruta"] = (
        df_nuevo["Total Venta Bruto"]
        - df_nuevo["Costo Total"]
    )

    df_nuevo["Ganancia Neta"] = (
        df_nuevo["Total Venta Neta"]
        - df_nuevo["Costo Total"]
    )

    # -----------------------------
    # LIMPIEZA JSON (CLAVE)
    # -----------------------------
    df_nuevo = (
        df_nuevo
        .replace([np.inf, -np.inf], 0)
        .fillna(0)
    )

    # -----------------------------
    # UNIR HISTÓRICO
    # -----------------------------
    df_final = (
        df_nuevo
        if df_actual.empty
        else pd.concat([df_actual, df_nuevo], ignore_index=True)
    )

    return api_write(R2_VENTAS, df_final)


#============================================================================================================================

def leer_precios_desglose():
    precios = {}
    try:
        df = api_read(R2_PRECIOS)
        if df.empty: return precios
        for _, row in df.iterrows():
            producto = str(row.get('Producto', '')).strip()
            if not producto: continue
            precios[producto] = {
                'precio_venta': clean_and_convert_float(row.get('Precio Venta')),
                'margen': clean_and_convert_float(row.get('Margen Bruto')),
                'margen_porc': clean_and_convert_float(row.get('Margen Bruto (%)'))
            }
    except: pass
    return precios

def calcular_reposicion_sugerida(fecha_inicio, fecha_fin):
    ventas = leer_ventas(fecha_inicio, fecha_fin)
    recetas = leer_recetas()
    ingredientes_base = leer_ingredientes_base()
    ingredientes_utilizados = {}

    for venta in ventas:
        producto = venta.get('Producto')
        prod_limpio = producto.split(" (+")[0].strip() # Limpiar nombre ticket
        
        cantidad_vendida = clean_and_convert_float(venta.get('Cantidad', 0))
        if prod_limpio in recetas:
            for ing_nom, cant_receta in recetas[prod_limpio]['ingredientes'].items():
                ingredientes_utilizados[ing_nom] = ingredientes_utilizados.get(ing_nom, 0) + (cant_receta * cantidad_vendida)

    resultado = []
    for ing_nom, cant_necesaria in ingredientes_utilizados.items():
        if cant_necesaria <= 0: continue
        info = next((i for i in ingredientes_base if i['nombre'] == ing_nom), None)
        if not info: continue
        
        costo_reposicion = cant_necesaria * info['costo_receta']
        resultado.append({
            'Ingrediente': ing_nom, 'Cantidad Necesaria': cant_necesaria,
            'Unidad': info['unidad_receta'], 'Proveedor': info['proveedor'],
            'Costo Reposición': costo_reposicion
        })
    return sorted(resultado, key=lambda x: x['Ingrediente'])
#============================================================================================================================
# --- PESTAÑAS Y VISTAS ---
#============================================================================================================================
def mostrar_dashboard(f_inicio, f_fin):
    st.markdown('<div class="section-header">📊 Dashboard General</div>', unsafe_allow_html=True)
    
    ventas = leer_ventas(f_inicio, f_fin)
    if not ventas:
        st.warning("No hay datos para el rango seleccionado.")
        return

    df_filtered = pd.DataFrame(ventas)
    
    # --- KPIs ---
    total_ventas = df_filtered['Total Venta Neta'].sum()
    total_ganancia = df_filtered['Ganancia Neta'].sum()
    total_transacciones = len(df_filtered)
    
    # METRICO NUEVO: TICKET PROMEDIO
    ticket_promedio = total_ventas / total_transacciones if total_transacciones > 0 else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ventas Totales", f"${total_ventas:,.2f}")
    c2.metric("Ganancia Neta", f"${total_ganancia:,.2f}")
    c3.metric("Ticket Promedio", f"${ticket_promedio:,.2f}")
    c4.metric("Transacciones", f"{total_transacciones}")
    
    st.markdown("---")
    
    # --- GRÁFICO 1: TENDENCIA DIARIA CON CONTROL SEMANAL ---
    st.subheader("Tendencia de Ventas (Diario)")
    
    # ===============================
    # Resumen diario
    # ===============================
    daily_summary = (
        df_filtered
            .groupby(df_filtered['Fecha_DT'].dt.date)
            .agg(
                Ventas=('Total Venta Neta', 'sum'),
                Ganancia=('Ganancia Neta', 'sum')
            )
            .reset_index()
            .rename(columns={'Fecha_DT': 'Fecha'})
    )
    
    daily_summary['Fecha'] = pd.to_datetime(daily_summary['Fecha'])
    
    # ===============================
    # Definición explícita de semana (LUNES → DOMINGO)
    # ===============================
    daily_summary['Inicio_Semana'] = daily_summary['Fecha'] - pd.to_timedelta(
        daily_summary['Fecha'].dt.weekday, unit='D'
    )
    daily_summary['Fin_Semana'] = daily_summary['Inicio_Semana'] + pd.Timedelta(days=6)
    
    # ===============================
    # Medias semanales
    # ===============================
    weekly_means = (
        daily_summary
            .groupby('Inicio_Semana')
            .agg(
                mean_ventas=('Ventas', 'mean'),
                mean_ganancia=('Ganancia', 'mean')
            )
            .reset_index()
    )
    
    weekly_means['Fin_Semana'] = weekly_means['Inicio_Semana'] + pd.Timedelta(days=7)
    
    # ===============================
    # Gráfico base
    # ===============================
    fig_daily = px.line(
        daily_summary,
        x='Fecha',
        y=['Ventas', 'Ganancia'],
        markers=True,
        color_discrete_sequence=['#4B2840', '#F1B48B'],
        template='plotly_white'
    )
    
    # ===============================
    # Líneas de media semanal (PUNTEADAS)
    # ===============================
    for _, row in weekly_means.iterrows():
    
        # Media semanal Ventas
        fig_daily.add_trace(
            go.Scatter(
                x=[row['Inicio_Semana'], row['Fin_Semana']],
                y=[row['mean_ventas'], row['mean_ventas']],
                mode="lines",
                line=dict(
                    color="#1f77b4",
                    width=1,
                    dash="dot"   # <<< punteado
                ),
                showlegend=False,
                hoverinfo="skip"
            )
        )
    
        # Media semanal Ganancia
        fig_daily.add_trace(
            go.Scatter(
                x=[row['Inicio_Semana'], row['Fin_Semana']],
                y=[row['mean_ganancia'], row['mean_ganancia']],
                mode="lines",
                line=dict(
                    color="#2ca02c",
                    width=1,
                    dash="dot"   # <<< punteado
                ),
                showlegend=False,
                hoverinfo="skip"
            )
        )
    
    # ===============================
    # Líneas verticales (lunes)
    # ===============================
    mondays = weekly_means['Inicio_Semana']
    
    for monday in mondays:
        fig_daily.add_vline(
            x=monday,
            line_width=1,
            line_dash="dot",
            line_color="gray",
            opacity=0.5
        )
    
    fig_daily.update_layout(
        legend_title_text="Indicadores",
        hovermode="x unified"
    )
    
    st.plotly_chart(fig_daily, use_container_width=True)

    # 3. Análisis de Productos
    st.subheader("Desempeño de Productos")
    col_g1, col_g2 = st.columns(2)
    
    product_summary = df_filtered.groupby('Producto').agg(
        Total_Venta=('Total Venta Neta', 'sum'),
        Total_Ganancia=('Ganancia Neta', 'sum'),
        Cantidad=('Cantidad', 'sum')
    ).reset_index()
    
    st.subheader("Top 10 Productos por Volumen")

    top_cant = product_summary.sort_values('Cantidad', ascending=False).head(10)
    fig_prod = px.bar(
        top_cant,
        x='Cantidad',
        y='Producto',
        orientation='h',
        text_auto=True,
        template='plotly_white',
        color='Cantidad',
        color_continuous_scale='Purples'
    )
    fig_prod.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_prod, use_container_width=True)
    
    st.subheader("Top 10 Productos por Ganancia")
    
    top_gan = product_summary.sort_values('Total_Ganancia', ascending=False).head(10)
    fig_gan = px.bar(
        top_gan,
        x='Total_Ganancia',
        y='Producto',
        orientation='h',
        text_auto='.2s',
        template='plotly_white',
        color='Total_Ganancia',
        color_continuous_scale='Peach'
    )
    fig_gan.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_gan, use_container_width=True)


    # --- GRÁFICO 2: PATRONES SEMANALES (SUPERPOSICIÓN) ---
    st.subheader("🔎 Patrones Semanales")
    st.caption(
        "Compara el comportamiento diario entre semanas completas para detectar patrones repetitivos."
    )
    
    df_patron = df_filtered.copy()
     
    df_patron['Inicio_Semana'] = df_patron['Fecha_DT'].apply(
        lambda x: x - datetime.timedelta(days=x.weekday())
    )
    # Día de la semana en español
    df_patron['Dia_Nombre'] = (
        df_patron['Fecha_DT']
        .dt.day_name()
        .map(DIAS_ESP)
    )
    
    # 1️⃣ AGRUPAR POR DÍA REAL (NO POR REGISTRO)
    ventas_diarias = (
        df_patron
        .groupby(['Fecha_DT', 'Dia_Nombre'], as_index=False)
        .agg({'Total Venta Neta': 'sum'})
    )
    
    # 2️⃣ QUITAR DÍAS SIN VENTA REAL
    ventas_diarias = ventas_diarias[
        ventas_diarias['Total Venta Neta'] > 0
    ]
    
    # 3️⃣ PROMEDIAR POR DÍA DE LA SEMANA
    patron_promedio = (
        ventas_diarias
        .groupby('Dia_Nombre', as_index=False)['Total Venta Neta']
        .mean()
    )
      
    # Forzar orden Lunes → Domingo
    patron_promedio['Dia_Nombre'] = pd.Categorical(
        patron_promedio['Dia_Nombre'],
        categories=ORDEN_DIAS,
        ordered=True
    )
    
    patron_promedio = patron_promedio.sort_values('Dia_Nombre')

    
    # Etiqueta corta para leyenda
    df_patron['Semana_Label'] = df_patron['Inicio_Semana'].dt.strftime('%d/%m')
    
    # Agrupación
    patron_agrupado = (
        df_patron
        .groupby(['Semana_Label', 'Dia_Nombre'], as_index=False)
        ['Total Venta Neta']
        .sum()
    )
    
    fig_patron = px.line(
        patron_agrupado,
        x='Dia_Nombre',
        y='Total Venta Neta',
        color='Semana_Label',
        category_orders={'Dia_Nombre': ORDEN_DIAS},
        markers=True,
        template='plotly_white',
        labels={
            'Total Venta Neta': 'Ventas ($)',
            'Dia_Nombre': 'Día de la semana',
            'Semana_Label': 'Semana'
        },
        title="Comparativa Semanal Día a Día"
    )
    
    fig_patron.update_layout(
        legend_title_text="Semana (Lun)",
        hovermode="x unified"
    )
    
    st.plotly_chart(fig_patron, use_container_width=True)


    st.subheader("📊 Venta Promedio por Día ")
    fig_prom = px.bar(
        patron_promedio,
        x='Dia_Nombre',
        y='Total Venta Neta',
        text_auto='.2s',
        template='plotly_white',
        labels={
            'Dia_Nombre': 'Día de la semana',
            'Total Venta Neta': 'Venta Promedio ($)'
        },
        color='Total Venta Neta',
        color_continuous_scale='bluyl'
    )

    st.plotly_chart(fig_prom, use_container_width=True)

    
    if not patron_promedio.empty:
        mejor = patron_promedio.loc[
            patron_promedio['Total Venta Neta'].idxmax()
        ]
        peor = patron_promedio.loc[
            patron_promedio['Total Venta Neta'].idxmin()
        ]
    
        st.success(
            f"🔥 Mejor día promedio: **{mejor['Dia_Nombre']}** "
            f"(${mejor['Total Venta Neta']:,.0f})\n\n"
            f"🧊 Día más bajo (con ventas): **{peor['Dia_Nombre']}** "
            f"(${peor['Total Venta Neta']:,.0f})"
        )

    # --- TABLA: RESUMEN SEMANAL (LUNES A DOMINGO) ---
    st.subheader("Resumen Semanal (Lunes - Domingo)")
    
    # Agrupar forzando inicio en Lunes
    df_filtered['Semana_Inicio'] = df_filtered['Fecha_DT'].apply(lambda x: x - datetime.timedelta(days=x.weekday()))
    
    weekly = df_filtered.groupby('Semana_Inicio').agg({
        'Total Venta Neta': 'sum',
        'Ganancia Neta': 'sum',
        'Cantidad': 'sum'
    }).reset_index().sort_values('Semana_Inicio', ascending=False)
    
    # Formatear columna fecha para visualización "Lun DD/MM - Dom DD/MM"
    weekly['Periodo'] = weekly['Semana_Inicio'].apply(
        lambda x: f"Lun {x.strftime('%d/%m')} - Dom {(x + datetime.timedelta(days=6)).strftime('%d/%m')}"
    )
    
    st.dataframe(
        weekly[['Periodo', 'Total Venta Neta', 'Ganancia Neta', 'Cantidad']].style.format({
            'Total Venta Neta': '${:,.2f}', 
            'Ganancia Neta': '${:,.2f}'
        }), 
        use_container_width=True, hide_index=True
    )

def mostrar_ingredientes():
    st.markdown('<div class="section-header">🧪 Gestión de Ingredientes</div>', unsafe_allow_html=True)
    ingredientes = leer_ingredientes_base()
    
    with st.expander("➕ Agregar / Modificar Ingrediente"):
        nombres = [i['nombre'] for i in ingredientes]
        sel = st.selectbox("Seleccionar para editar (o dejar vacío para nuevo):", [""] + nombres)
        datos_edit = next((i for i in ingredientes if i['nombre'] == sel), {}) if sel else {}
            
        with st.form("ing_form"):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre*", value=datos_edit.get('nombre', ''))
            prov = c2.text_input("Proveedor", value=datos_edit.get('proveedor', ''))
            c3, c4 = st.columns(2)
            u_compra = c3.text_input("Unidad Compra (ej. kg)*", value=datos_edit.get('unidad_compra', ''))
            costo_compra = c4.number_input("Costo Compra ($)*", min_value=0.0, value=float(datos_edit.get('costo_compra', 0)))
            c5, c6 = st.columns(2)
            cant_compra = c5.number_input("Cant. por U. Compra*", min_value=0.0, value=float(datos_edit.get('cantidad_compra', 0)))
            u_receta = c6.text_input("Unidad Receta (ej. gr)*", value=datos_edit.get('unidad_receta', ''))
            
            if st.form_submit_button("Guardar Ingrediente"):
                if nombre and u_compra and costo_compra > 0 and cant_compra > 0:
                    nuevo_costo_receta = costo_compra / cant_compra
                    nuevo_item = {
                        'nombre': nombre, 'proveedor': prov, 'unidad_compra': u_compra,
                        'costo_compra': costo_compra, 'cantidad_compra': cant_compra,
                        'unidad_receta': u_receta, 'costo_receta': nuevo_costo_receta,
                        'nombre_normalizado': normalizar_texto(nombre)
                    }
                    ingredientes = [i for i in ingredientes if i['nombre'] != nombre]
                    ingredientes.append(nuevo_item)
                    if guardar_ingredientes_base(ingredientes):
                        st.success("Guardado."); st.rerun()
                else: st.error("Faltan datos obligatorios.")

    if ingredientes:
        df = pd.DataFrame(ingredientes)
        df['Costo Compra'] = df['costo_compra'].apply(lambda x: f"${x:.2f}")
        df['Costo Receta'] = df['costo_receta'].apply(lambda x: f"${x:.4f}")
        st.dataframe(df[['nombre', 'proveedor', 'unidad_compra', 'Costo Compra', 'cantidad_compra', 'unidad_receta', 'Costo Receta']], use_container_width=True, hide_index=True)


def mostrar_recetas():
    st.markdown('<div class="section-header">📝 Recetas y Configuración</div>', unsafe_allow_html=True)
    st.info("💡 Ahora puedes asignar qué modificadores son válidos para cada receta.")
    
    recetas = leer_recetas()
    ingredientes = leer_ingredientes_base()
    modificadores = leer_modificadores()
    
    lista_opciones = [i['nombre'] for i in ingredientes] + list(recetas.keys())
    lista_opciones = sorted(list(set(lista_opciones)))

    col_izq, col_der = st.columns([1, 2])
    with col_izq:
        st.subheader("Menú")
        nuevo_nom = st.text_input("Nueva receta / sub-receta:")
        if st.button("Crear Receta") and nuevo_nom:
            if nuevo_nom not in recetas:
                recetas[nuevo_nom] = {'ingredientes': {}, 'costo_total': 0.0, 'modificadores_validos': []}
                guardar_recetas(recetas); st.success(f"Creada {nuevo_nom}"); st.rerun()
        st.divider()
        sel_receta = st.radio("Seleccionar Receta:", list(recetas.keys()))
        
    with col_der:
        if sel_receta:
            st.subheader(f"Editando: {sel_receta}")
            datos = recetas[sel_receta]
            
            # --- SECCIÓN 1: INGREDIENTES ---
            if datos['ingredientes']:
                lista_items = []
                for ing, cant in datos['ingredientes'].items():
                    info = next((i for i in ingredientes if i['nombre'] == ing), None)
                    costo_u = info['costo_receta'] if info else (recetas[ing]['costo_total'] if ing in recetas else 0)
                    tipo = "Ingrediente" if info else "Sub-Receta"
                    lista_items.append({'Tipo': tipo, 'Item': ing, 'Cantidad': cant, 'Costo': costo_u * cant})
                
                st.dataframe(pd.DataFrame(lista_items).style.format({'Costo': "${:.2f}"}), use_container_width=True)
                
                to_del = st.selectbox("Eliminar ingrediente:", [""] + list(datos['ingredientes'].keys()))
                if st.button("Eliminar Item") and to_del:
                    del recetas[sel_receta]['ingredientes'][to_del]; guardar_recetas(recetas); st.rerun()
            else: st.info("Receta vacía.")
            
            st.metric("Costo Insumos", f"${datos.get('costo_total', 0):.2f}")
            
            # Agregar Ingrediente
            c1, c2, c3 = st.columns([2,1,1])
            opciones_validas = [o for o in lista_opciones if o != sel_receta]
            ing_sel = c1.selectbox("Agregar Ingrediente/Sub-Receta", opciones_validas)
            cant_sel = c2.number_input("Cantidad", min_value=0.0, step=0.1)
            if c3.button("➕ Agregar"):
                if cant_sel > 0:
                    recetas[sel_receta]['ingredientes'][ing_sel] = cant_sel; guardar_recetas(recetas); st.rerun()
            
            st.markdown("---")
            
            # --- SECCIÓN 2: VINCULACIÓN DE MODIFICADORES ---
            st.markdown("#### 🔗 Modificadores Permitidos")
            st.caption("Selecciona qué extras se pueden vender con este producto (ej. 'Extra Queso' sí, 'Jarabe' no).")
            
            mods_actuales = datos.get("modificadores_validos", [])
            todos_mods = list(modificadores.keys())
            
            nuevos_mods = st.multiselect("Seleccionar permitidos:", todos_mods, default=[m for m in mods_actuales if m in todos_mods])
            
            if nuevos_mods != mods_actuales:
                if st.button("💾 Guardar Cambios en Modificadores"):
                    recetas[sel_receta]["modificadores_validos"] = nuevos_mods
                    guardar_recetas(recetas)
                    st.success("Configuración de modificadores guardada.")
                    
            st.markdown("---")
            # --- BOTÓN DE ELIMINAR RECETA COMPLETA ---
            if st.button("🗑️ Eliminar Receta Completa", type="primary"):
                del recetas[sel_receta]
                guardar_recetas(recetas)
                st.success(f"Receta '{sel_receta}' eliminada.")
                st.rerun()

def mostrar_modificadores():
    st.markdown('<div class="section-header">🧩 Modificadores (Extras)</div>', unsafe_allow_html=True)
    st.caption("Define extras, su precio de venta y su costo real.")
    
    mods = leer_modificadores()
    ingredientes = leer_ingredientes_base()
    mapa_costos_ing = {i["nombre"]: i["costo_receta"] for i in ingredientes}
    
    col_list, col_det = st.columns([1, 2])
    
    with col_list:
        st.subheader("Lista")
        new_mod = st.text_input("Nuevo Modificador (ej. Extra Queso)")
        if st.button("Crear Modificador") and new_mod:
            if new_mod not in mods:
                mods[new_mod] = {"precio_extra": 0.0, "ingredientes": {}}
                guardar_modificadores(mods); st.rerun()
        sel_mod = st.radio("Editar:", list(mods.keys()))
    
    with col_det:
        if sel_mod:
            st.subheader(f"Editando: {sel_mod}")
            curr = mods[sel_mod]
            
            # Calcular Costo Real
            costo_insumos = 0
            detalle_costo = []
            for ing, cant in curr["ingredientes"].items():
                c_unit = mapa_costos_ing.get(ing, 0)
                total_c = c_unit * cant
                costo_insumos += total_c
                detalle_costo.append({"Ingrediente": ing, "Cant": cant, "Costo": total_c})

            # Mostrar Comparativa
            m1, m2, m3 = st.columns(3)
            nuevo_precio = m1.number_input("Precio Venta ($)", value=curr["precio_extra"])
            m2.metric("Costo Insumos", f"${costo_insumos:.2f}")
            margen = nuevo_precio - costo_insumos
            m3.metric("Ganancia", f"${margen:.2f}", delta_color="normal")
            
            if nuevo_precio != curr["precio_extra"]:
                if st.button("Actualizar Precio"):
                    curr["precio_extra"] = nuevo_precio
                    guardar_modificadores(mods); st.success("Actualizado"); st.rerun()
            
            st.markdown("#### Ingredientes (Composición)")
            if detalle_costo:
                st.dataframe(pd.DataFrame(detalle_costo).style.format({'Costo': "${:.2f}"}), use_container_width=True)
                del_ing = st.selectbox("Quitar ingrediente:", [""] + list(curr["ingredientes"].keys()))
                if st.button("Quitar") and del_ing:
                    del curr["ingredientes"][del_ing]; guardar_modificadores(mods); st.rerun()
            else:
                st.info("Este modificador no descuenta inventario (Solo cobra extra).")

            c1, c2, c3 = st.columns([2,1,1])
            add_ing = c1.selectbox("Agregar Insumo:", [i["nombre"] for i in ingredientes])
            add_cant = c2.number_input("Cant:", min_value=0.0, step=0.1)
            if c3.button("Añadir"):
                curr["ingredientes"][add_ing] = add_cant; guardar_modificadores(mods); st.rerun()

def mostrar_precios():
    st.markdown('<div class="section-header">💰 Análisis de Precios</div>', unsafe_allow_html=True)
    recetas = leer_recetas()
    precios_existentes = leer_precios_desglose()
    
    data_tabla = []
    for prod, info_receta in recetas.items():
        costo = info_receta['costo_total']
        p_venta = precios_existentes.get(prod, {}).get('precio_venta', 0.0)
        margen = p_venta - costo
        margen_p = (margen / p_venta * 100) if p_venta else 0
        data_tabla.append({'Producto': prod, 'Costo Producción': costo, 'Precio Venta': p_venta, 'Margen $': margen, 'Margen %': margen_p})
    
    df = pd.DataFrame(data_tabla)
    if not df.empty:
        st.subheader("Estructura de Precios")
        fig = px.bar(df, x='Producto', y=['Costo Producción', 'Margen $'], title="Desglose del Precio", labels={'value': 'Dinero ($)', 'variable': 'Componente'}, color_discrete_map={'Costo Producción': '#FF9AA2', 'Margen $': '#B5EAD7'}, template='plotly_white')
        fig.update_layout(barmode='stack', hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("✏️ Modificar Precio de Venta"):
        prod_sel = st.selectbox("Producto:", df['Producto'].tolist())
        if prod_sel:
            row = df[df['Producto'] == prod_sel].iloc[0]
            st.write(f"Costo actual: ${row['Costo Producción']:.2f}")
            nuevo_precio = st.number_input("Nuevo Precio Venta:", value=float(row['Precio Venta']))
            if st.button("Actualizar Precio"):
                todos_precios = api_read(R2_PRECIOS).to_dict("records")
                found = False
                margen_nuevo = nuevo_precio - row['Costo Producción']
                margen_p_nuevo = (margen_nuevo / nuevo_precio * 100) if nuevo_precio else 0
                for item in todos_precios:
                    if item['Producto'] == prod_sel:
                        item['Precio Venta'] = nuevo_precio; item['Margen Bruto'] = margen_nuevo; item['Margen Bruto (%)'] = margen_p_nuevo; found = True; break
                if not found: todos_precios.append({'Producto': prod_sel, 'Precio Venta': nuevo_precio, 'Margen Bruto': margen_nuevo, 'Margen Bruto (%)': margen_p_nuevo})
                api_write(R2_PRECIOS, todos_precios); st.success("Actualizado."); st.rerun()

    st.dataframe(df.style.format({'Costo Producción': "${:.2f}", 'Precio Venta': "${:.2f}", 'Margen $': "${:.2f}", 'Margen %': "{:.1f}%"}), use_container_width=True)

def mostrar_ventas(f_inicio, f_fin):
    st.markdown('<div class="section-header">🛒 Terminal de Ventas (POS)</div>', unsafe_allow_html=True)
    es_admin = st.session_state.get("rol") == "admin"
    
    if 'carrito' not in st.session_state: st.session_state.carrito = []
    # --- Fecha de venta (solo admin) ---
    if es_admin:
        fecha_venta = st.date_input(
            "📅 Fecha de la venta",
            value=pd.Timestamp.today().date(),
            help="Permite registrar ventas en una fecha distinta a hoy"
        )
    else:
        fecha_venta = pd.Timestamp.today().date()
    # =========================================================
    # 1. SECCIÓN SUPERIOR: NUEVA ORDEN (POS)
    # =========================================================
    st.subheader("➕ Nueva Orden")
    
    recetas = leer_recetas()
    precios = leer_precios_desglose()
    modificadores = leer_modificadores()
    
    prod_sel = st.selectbox("Selecciona un Producto", [""] + list(recetas.keys()), key="pos_prod_sel")
    
    if prod_sel:
        p_base = precios.get(prod_sel, {}).get('precio_venta', 0)
        st.info(f"Precio Base: ${p_base:.2f}")

        # Modificadores (Aparición inmediata)
        nombres_mods_validos = recetas[prod_sel].get("modificadores_validos", [])
        if nombres_mods_validos:
            st.markdown("##### 🧩 Extras / Modificadores")
            for m_name in nombres_mods_validos:
                if m_name in modificadores:
                    precio_m = modificadores[m_name]["precio_extra"]
                    c_m1, c_m2, c_m3, c_m4 = st.columns([3, 1, 1, 1])
                    c_m1.caption(f"{m_name} (+${precio_m:.2f})")
                    
                    mod_key = f"qty_mod_{m_name}"
                    if mod_key not in st.session_state: st.session_state[mod_key] = 0
                    
                    if c_m2.button("➖", key=f"min_{m_name}"):
                        if st.session_state[mod_key] > 0: 
                            st.session_state[mod_key] -= 1
                            st.rerun()
                    c_m3.write(f"**{st.session_state[mod_key]}**")
                    if c_m4.button("➕", key=f"plus_{m_name}"):
                        st.session_state[mod_key] += 1
                        st.rerun()

        # Cantidad y Botón de agregar
        st.markdown("---")
        cc1, cc2 = st.columns(2)
        cant_principal = cc1.number_input("Cantidad de productos", min_value=1, value=1, step=1)
        desc_porc = cc2.number_input("Descuento %", min_value=0.0, max_value=100.0, step=5.0)
        pago_tarjeta = st.checkbox("💳 Pago con Tarjeta")

        if st.button("🛒 Agregar al Carrito", type="primary", use_container_width=True):
            # ... (Lógica de compilación de modificadores idéntica a la anterior)
            lista_mods_final = []
            costo_extra_total = 0
            for m_name in nombres_mods_validos:
                qty = st.session_state.get(f"qty_mod_{m_name}", 0)
                if qty > 0:
                    p_m = modificadores[m_name]["precio_extra"]
                    lista_mods_final.append({"nombre": m_name, "precio": p_m, "cantidad": qty})
                    costo_extra_total += (p_m * qty)
            
            st.session_state.carrito.append({
                'Producto': prod_sel,
                'Cantidad': cant_principal,
                'Precio Base': p_base,
                'Modificadores': lista_mods_final,
                'Precio Unitario Final': p_base + costo_extra_total,
                'Descuento %': desc_porc,
                'Es Tarjeta': pago_tarjeta,
                'Fecha': pd.to_datetime(fecha_venta)
            })

            for m_name in nombres_mods_validos: st.session_state[f"qty_mod_{m_name}"] = 0
            st.rerun()

    # --- VISTA DEL CARRITO Y COBRO ---
    if st.session_state.carrito:
        st.markdown("---")
        st.subheader("📝 Carrito de Compra")
        total_carrito = 0
        for i, item in enumerate(st.session_state.carrito):
            subtotal = (item['Precio Unitario Final'] * item['Cantidad']) * (1 - item['Descuento %']/100)
            total_carrito += subtotal
            with st.expander(f"{item['Producto']} (x{item['Cantidad']}) - ${subtotal:.2f}"):
                c1, c2, c3, c4 = st.columns([1,1,1,2])
                if c1.button("➖", key=f"c_min_{i}"):
                    if item['Cantidad'] > 1: st.session_state.carrito[i]['Cantidad'] -= 1; st.rerun()
                c2.write(f"**{item['Cantidad']}**")
                if c3.button("➕", key=f"c_plus_{i}"):
                    st.session_state.carrito[i]['Cantidad'] += 1; st.rerun()
                if c4.button("🗑️ Quitar", key=f"c_del_{i}"):
                    st.session_state.carrito.pop(i); st.rerun()
        
        st.metric("Total a Cobrar", f"${total_carrito:.2f}")
        if st.button("✅ FINALIZAR Y REGISTRAR VENTA", type="primary", use_container_width=True):

            recetas = leer_recetas()
            precios = leer_precios_desglose()
            desglose_precios = leer_precios_desglose()
            modificadores = leer_modificadores()

            ventas_detalladas = []
            fecha_guardado = pd.to_datetime(fecha_venta).strftime("%d/%m/%Y")
            
            for item in st.session_state.carrito:
                producto = item["Producto"]
                cantidad = item["Cantidad"]
                precio_unitario = item["Precio Unitario Final"]
                descuento_porc = item["Descuento %"]
            
                total_bruto = precio_unitario * cantidad
                descuento_monto = total_bruto * (descuento_porc / 100)
                subtotal = total_bruto - descuento_monto
            
                forma_pago = "Tarjeta" if item["Es Tarjeta"] else "Efectivo"
                comision = subtotal * (COMISION_TARJETA / 100) if item["Es Tarjeta"] else 0
                total_neto = subtotal - comision
            
                datos_prod = desglose_precios.get(producto, {})
                costo_unitario = datos_prod.get("costo_produccion", 0)
                costo_total = costo_unitario * cantidad
            
                ganancia_neta = total_neto - costo_total
            
                ventas_detalladas.append({
                    "Fecha": fecha_guardado,
                    "Producto": producto,
                    "Cantidad": cantidad,
                    "Precio Unitario": precio_unitario,
                    "Total Venta Bruto": total_bruto,
                    "Descuento (%)": descuento_porc,
                    "Descuento ($)": descuento_monto,
                    "Costo Total": costo_total,
                    "Comision ($)": comision,
                    "Ganancia Neta": ganancia_neta,
                    "Forma Pago": forma_pago
                })
        
                # 🔁 Reposición (producto completo, no modificadores individuales)
                #descontar_recursivo(producto, cantidad)
        
            ok = guardar_ventas(ventas_detalladas)
        
            if ok:
                st.success("Venta registrada correctamente")
                st.session_state.carrito = []
                st.rerun()
            else:
                st.error("No se pudo guardar la venta")


    # =========================================================
    # 2. SECCIÓN INFERIOR: HISTORIAL Y GRÁFICAS (ABAJO)
    # =========================================================
    st.markdown("<br><hr><br>", unsafe_allow_html=True) # Separador visual grande
    st.subheader("📜 Resumen de Actividad e Historial")
    
    ventas_hist = leer_ventas(f_inicio, f_fin)
    if ventas_hist:
        ventas_df = pd.DataFrame(ventas_hist)
        
        if es_admin:
            with st.expander("📊 Gráficas de Resumen Rápido", expanded=True):
                cg1, cg2 = st.columns(2)
                # Gráfica 1
                with cg1:
                    if 'Forma Pago' in ventas_df.columns:
                        fig_pago = px.pie(ventas_df.groupby('Forma Pago')['Total Venta Neta'].sum().reset_index(), 
                                        values='Total Venta Neta', names='Forma Pago', hole=.5, 
                                        color_discrete_sequence=["#D4D4D4", "#95E9BF"], title="Métodos de Pago")
                        st.plotly_chart(fig_pago, use_container_width=True)
                
                st.divider()
                with cg2:
                    # Gráfica 2
                    venta_t = ventas_df['Total Venta Neta'].sum()
                    ganancia_t = ventas_df['Ganancia Neta'].sum()
                    fig_rent = px.pie(names=['Ganancia', 'Costos'], values=[ganancia_t, max(0, venta_t - ganancia_t)], 
                                     hole=.5, color_discrete_sequence=["#80A6F8", "#A2FF9A"], title="Rentabilidad")
                    st.plotly_chart(fig_rent, use_container_width=True)
        
        # Tabla de historial al final
        st.markdown("##### Detalle de Ventas")
        st.dataframe(ventas_df[['Fecha', 'Producto', 'Cantidad', 'Total Venta Neta', 'Forma Pago']], 
                     use_container_width=True, hide_index=True)
    else:
        st.info("No hay ventas en el rango seleccionado.")
            
def mostrar_inventario():
    st.markdown('<div class="section-header">📦 Inventario</div>', unsafe_allow_html=True)
    inv = leer_inventario(); ings = leer_ingredientes_base()
    for i in ings:
        if i['nombre'] not in inv: inv[i['nombre']] = {'stock_actual': 0.0, 'min': 0.0, 'max': 0.0}
            
    rows = []
    for k, v in inv.items():
        estado = "OK"
        if v['max'] > 0:
            if v['stock_actual'] < v['min']: estado = "🚨 URGENTE"
            elif v['stock_actual'] < (v['min'] + v['max'])/2: estado = "⚠️ Bajo"
        rows.append({'Ingrediente': k, 'Stock': v['stock_actual'], 'Min': v['min'], 'Max': v['max'], 'Estado': estado})
        
    df = pd.DataFrame(rows)
    def color_row(row):
        color = 'transparent'
        if "URGENTE" in row['Estado']: color = '#FFDDDD'
        elif "Bajo" in row['Estado']: color = '#FFFFAA'
        return [f'background-color: {color}'] * len(row)
    
    st.dataframe(df.style.apply(color_row, axis=1), use_container_width=True)
    with st.expander("📥 Registrar Entrada Manual"):
        c1, c2, c3 = st.columns([2,1,1])
        ing_in = c1.selectbox("Ingrediente:", df['Ingrediente'].tolist())
        cant_in = c2.number_input("Cantidad a agregar:", min_value=0.0)
        if c3.button("Registrar Entrada"):
            inv[ing_in]['stock_actual'] += cant_in; guardar_inventario(inv); st.success(f"Actualizado {ing_in}"); st.rerun()

def mostrar_reposicion(f_inicio, f_fin):
    st.markdown('<div class="section-header">🔄 Reposición Sugerida</div>', unsafe_allow_html=True)
    data_reposicion = calcular_reposicion_sugerida(f_inicio, f_fin)
    
    if data_reposicion:
        df = pd.DataFrame(data_reposicion)
        m1, m2 = st.columns(2)
        m1.metric("Inversión Estimada", f"${df['Costo Reposición'].sum():,.2f}")
        m2.metric("Items a Reponer", len(df))
        st.divider()
        fig = px.bar(df.sort_values('Costo Reposición', ascending=False).head(10), 
                     x='Ingrediente', y='Costo Reposición', title="Top Costos Reposición", 
                     color='Costo Reposición', color_continuous_scale='Bluered', template='plotly_white')
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['Ingrediente', 'Cantidad Necesaria', 'Unidad', 'Proveedor', 'Costo Reposición']], use_container_width=True)
        csv = df.to_csv(index=False, encoding='latin-1')
        st.download_button("📥 Descargar CSV", data=csv, file_name=f"Reposicion.csv", mime='text/csv')
    else: st.warning("No hay datos suficientes.")

# --- MAIN LOOP ---
def main():
    if not check_auth(): st.stop()
    st.sidebar.markdown("### 🍑 BonBon Peach")
    st.sidebar.markdown("#### 📅 Rango de Fechas")
    hoy = datetime.date.today()
    f_inicio = st.sidebar.date_input("Inicio", value=hoy.replace(day=1))
    f_fin = st.sidebar.date_input("Fin", value=hoy)
    st.sidebar.markdown("---")
    st.sidebar.caption(f"👤 {st.session_state.usuario} ({st.session_state.rol})")

    rol = st.session_state.get("rol", "vendedor")
    menu_opts = ["📊 Dashboard", "🛒 Ventas", "🔄 Reposición", "📦 Inventario", "🧪 Ingredientes", "📝 Recetas", "🧩 Modificadores", "💰 Precios"]
    
    if rol == "vendedor":
        opcion = "🛒 Ventas"
    else:
        opcion = st.sidebar.radio("Navegación", menu_opts)

    st.sidebar.markdown("---")
    if st.sidebar.button("Cerrar Sesión"): st.session_state.authenticated = False; st.rerun()

    if opcion == "📊 Dashboard": mostrar_dashboard(f_inicio, f_fin)
    elif opcion == "🧪 Ingredientes": mostrar_ingredientes()
    elif opcion == "📝 Recetas": mostrar_recetas()
    elif opcion == "🧩 Modificadores": mostrar_modificadores()
    elif opcion == "💰 Precios": mostrar_precios()
    elif opcion == "🛒 Ventas": mostrar_ventas(f_inicio, f_fin)
    elif opcion == "📦 Inventario": mostrar_inventario()
    elif opcion == "🔄 Reposición": mostrar_reposicion(f_inicio, f_fin)

if __name__ == "__main__":
    main()
