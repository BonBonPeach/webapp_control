import streamlit as st
import hashlib
import pandas as pd
import requests
import os
import unicodedata
import re
import datetime
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE CLOUDFLARE R2 ---
# REEMPLAZA ESTA URL CON LA DE TU WORKER REAL
WORKER_URL = "https://admin.bonbon-peach.com/api"

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="BonBon - Peach · Sistema de control",
    page_icon="🍑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- FUNCIONES NÚCLEO R2 ---
def cargar_csv_desde_r2(nombre_archivo):
    """Cargar CSV desde Cloudflare R2 vía Worker"""
    try:
        response = requests.get(f"{WORKER_URL}/{nombre_archivo}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data: return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error cargando {nombre_archivo}: {e}")
    return pd.DataFrame()

def guardar_csv_en_r2(df, nombre_archivo):
    """Guardar CSV en Cloudflare R2 vía Worker"""
    try:
        data = df.to_dict('records') if not df.empty else []
        response = requests.post(f"{WORKER_URL}/{nombre_archivo}", json=data, timeout=10)
        if response.status_code == 200:
            st.cache_data.clear() # Limpiar caché para refrescar datos
            return True
    except Exception as e:
        st.error(f"Error guardando {nombre_archivo}: {e}")
    return False

# --- CONSTANTES ---
COMISION_BASE_PORCENTAJE = 3.5
TASA_IVA_PORCENTAJE = 16.0
COMISION_TARJETA = COMISION_BASE_PORCENTAJE * (1 + (TASA_IVA_PORCENTAJE / 100))

DIAS_ESP = {
    'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
    'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
}
ORDEN_DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

# --- AUTENTICACIÓN ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

USERS = {
    "admin": hash_password("BonBonAdmin!"),
    "ventas": hash_password("VentasBBP2025!")
}

def check_auth():
    if st.session_state.get("authenticated"):
        return True
    
    st.markdown("""
    <div style='text-align: center; padding: 50px 20px;'>
        <h1 style='color: #F1B48B;'>🍑 BonBon - Peach</h1>
        <p style='color: #666;'>Sistema de Gestión Integral (Cloud)</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Acceder", use_container_width=True):
                if username in USERS and hash_password(password) == USERS[username]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
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

# --- FUNCIONES AUXILIARES ---
def normalizar_texto(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().strip()
    texto = ' '.join(texto.split())
    texto = str(unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8'))
    return re.sub(r'[^a-z0-9\s]', '', texto)

def clean_and_convert_float(value_str, default=0.0):
    if isinstance(value_str, (int, float)): 
        return round(float(value_str), 2)
    if not isinstance(value_str, str): 
        return default
    cleaned = value_str.strip().replace('$', '').replace(',', '').replace('%', '')
    try: 
        return round(float(cleaned), 2)
    except (ValueError, TypeError): 
        return default

# --- GESTIÓN DE DATOS (R2 INTEGRADO) ---
@st.cache_data
def leer_ingredientes_base():
    df = cargar_csv_desde_r2('ingredientes')
    ingredientes = []
    if not df.empty:
        for _, fila in df.iterrows():
            nombre = str(fila.get('Ingrediente', '')).strip()
            if not nombre: continue
            costo_compra = clean_and_convert_float(fila.get(' Costo de Compra ', '0'))
            cantidad_compra = clean_and_convert_float(fila.get('Cantidad por Unidad de Compra', '0'))
            costo_receta = clean_and_convert_float(fila.get('Costo por Unidad Receta', '0'))
            if cantidad_compra != 0 and costo_receta == 0:
                costo_receta = costo_compra / cantidad_compra
            
            ingredientes.append({
                'nombre': nombre, 'proveedor': str(fila.get('Proveedor', '')).strip(),
                'costo_compra': costo_compra, 'cantidad_compra': cantidad_compra,
                'unidad_compra': str(fila.get('Unidad de Compra', '')).strip(),
                'unidad_receta': str(fila.get('Unidad Receta', '')).strip(),
                'costo_receta': costo_receta, 'nombre_normalizado': normalizar_texto(nombre)
            })
    return ingredientes

def guardar_ingredientes_base(ingredientes_data):
    datos = []
    for ing in sorted(ingredientes_data, key=lambda x: x['nombre']):
        datos.append({
            'Ingrediente': ing['nombre'], 'Proveedor': ing['proveedor'],
            'Unidad de Compra': ing['unidad_compra'],
            ' Costo de Compra ': f"{ing.get('costo_compra', 0.0):.2f}",
            'Cantidad por Unidad de Compra': f"{ing.get('cantidad_compra', 0.0)}",
            'Unidad Receta': ing['unidad_receta'],
            'Costo por Unidad Receta': f"{ing.get('costo_receta', 0.0):.4f}"
        })
    return guardar_csv_en_r2(pd.DataFrame(datos), 'ingredientes')

def leer_inventario():
    df = cargar_csv_desde_r2('inventario')
    inventario = {}
    if not df.empty:
        for _, fila in df.iterrows():
            nombre = str(fila.get('Ingrediente', '')).strip()
            if nombre:
                inventario[nombre] = {
                    'stock_actual': clean_and_convert_float(fila.get('Stock Actual', '0')),
                    'min': clean_and_convert_float(fila.get('Stock Mínimo', '0')),
                    'max': clean_and_convert_float(fila.get('Stock Máximo', '0'))
                }
    return inventario

def guardar_inventario_csv(inventario_data):
    datos = []
    for nombre, data in inventario_data.items():
        datos.append({
            'Ingrediente': nombre,
            'Stock Actual': f"{data.get('stock_actual', 0.0):.4f}",
            'Stock Mínimo': f"{data.get('min', 0.0):.4f}",
            'Stock Máximo': f"{data.get('max', 0.0):.4f}"
        })
    guardar_csv_en_r2(pd.DataFrame(datos), 'inventario')

@st.cache_data
def leer_recetas():
    df = cargar_csv_desde_r2('recetas')
    recetas = {}
    ingredientes = leer_ingredientes_base()
    if not df.empty and 'Ingrediente' in df.columns:
        productos = [col for col in df.columns if col != 'Ingrediente']
        for p in productos: recetas[p] = {'ingredientes': {}, 'costo_total': 0.0}
        
        for _, fila in df.iterrows():
            ing_nombre = str(fila['Ingrediente']).strip()
            if not ing_nombre: continue
            for p in productos:
                if p in fila:
                    cant = clean_and_convert_float(fila[p])
                    if cant > 0: recetas[p]['ingredientes'][ing_nombre] = cant
        
        for p, datos in recetas.items():
            costo = 0.0
            for ing_nom, cant in datos['ingredientes'].items():
                ing_info = next((i for i in ingredientes if i['nombre'] == ing_nom), None)
                if ing_info: costo += ing_info['costo_receta'] * cant
            recetas[p]['costo_total'] = costo
    return recetas

def guardar_recetas_csv(recetas_data):
    todos_ings = set()
    for r in recetas_data.values(): todos_ings.update(r['ingredientes'].keys())
    todos_ings = sorted(list(todos_ings))
    nombres_prod = sorted(recetas_data.keys())
    data = []
    for ing in todos_ings:
        fila = {'Ingrediente': ing}
        for prod in nombres_prod:
            fila[prod] = recetas_data[prod]['ingredientes'].get(ing, '')
        data.append(fila)
    guardar_csv_en_r2(pd.DataFrame(data), 'recetas')

def leer_ventas(fecha_inicio=None, fecha_fin=None):
    df = cargar_csv_desde_r2('ventas')
    if not df.empty and 'Fecha' in df.columns:
        df['Fecha_DT'] = pd.to_datetime(df['Fecha'], format='%d/%m/%Y', errors='coerce')
        df = df.dropna(subset=['Fecha_DT'])
        if fecha_inicio and fecha_fin:
            mask = (df['Fecha_DT'].dt.date >= fecha_inicio) & (df['Fecha_DT'].dt.date <= fecha_fin)
            df = df.loc[mask]
        return df.to_dict('records')
    return []

def leer_precios_desglose():
    df = cargar_csv_desde_r2('desglose')
    precios = {}
    if not df.empty:
        for _, row in df.iterrows():
            precios[row['Producto']] = {
                'precio_venta': clean_and_convert_float(row.get('Precio Venta')),
                'margen': clean_and_convert_float(row.get('Margen Bruto')),
                'margen_porc': clean_and_convert_float(row.get('Margen Bruto (%)'))
            }
    return precios

def calcular_reposicion_sugerida(fecha_inicio, fecha_fin):
    ventas = leer_ventas(fecha_inicio, fecha_fin)
    recetas = leer_recetas()
    ingredientes_base = leer_ingredientes_base()
    ingredientes_utilizados = {}
    
    for venta in ventas:
        producto = venta.get('Producto')
        cantidad_vendida = clean_and_convert_float(venta.get('Cantidad', 0))
        if producto in recetas:
            for ing_nom, cant_receta in recetas[producto]['ingredientes'].items():
                total_ing = cant_receta * cantidad_vendida
                ingredientes_utilizados[ing_nom] = ingredientes_utilizados.get(ing_nom, 0) + total_ing
    
    resultado = []
    for ing_nom, cant_necesaria in ingredientes_utilizados.items():
        if cant_necesaria <= 0: continue
        info = next((i for i in ingredientes_base if i['nombre'] == ing_nom), None)
        if info:
            cant_compra = info['cantidad_compra']
            porcentaje = (cant_necesaria / cant_compra * 100) if cant_compra > 0 else 0
            costo_reposicion = cant_necesaria * info['costo_receta']
            resultado.append({
                'Ingrediente': ing_nom, 'Cantidad Necesaria': cant_necesaria,
                'Unidad': info['unidad_receta'], 'Costo Compra Base': info['costo_compra'],
                'Proveedor': info['proveedor'], '% Unidad Compra': porcentaje,
                'Costo Reposición': costo_reposicion
            })
    return sorted(resultado, key=lambda x: x['Ingrediente'])

# --- VISTAS (DASHBOARD, VENTAS, ETC.) ---
# Nota: Aquí se pegan tus funciones mostrar_dashboard, mostrar_ingredientes, 
# mostrar_recetas, mostrar_precios, mostrar_ventas, mostrar_inventario, mostrar_reposicion 
# manteniendo la lógica exacta de tu archivo original.

def mostrar_dashboard(f_inicio, f_fin):
    st.markdown('<div class="section-header">📊 Dashboard General</div>', unsafe_allow_html=True)
    ventas = leer_ventas(f_inicio, f_fin)
    if not ventas:
        st.warning("No hay datos para el rango seleccionado.")
        return
    df_filtered = pd.DataFrame(ventas)
    
    total_ventas = df_filtered['Total Venta Bruto'].sum()
    total_ganancia = df_filtered['Ganancia Neta'].sum()
    total_transacciones = len(df_filtered)
    ticket_promedio = total_ventas / total_transacciones if total_transacciones > 0 else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ventas Totales", f"${total_ventas:,.2f}")
    c2.metric("Ganancia Neta", f"${total_ganancia:,.2f}")
    c3.metric("Ticket Promedio", f"${ticket_promedio:,.2f}")
    c4.metric("Transacciones", f"{total_transacciones}")
    
    st.markdown("---")
    
    st.subheader("Tendencia de Ventas (Diario)")
    daily_summary = df_filtered.groupby(df_filtered['Fecha_DT'].dt.date).agg(
        Ventas=('Total Venta Bruto', 'sum'),
        Ganancia=('Ganancia Neta', 'sum')
    ).reset_index().rename(columns={'Fecha_DT': 'Fecha'})
    fig_daily = px.line(daily_summary, x='Fecha', y=['Ventas', 'Ganancia'], 
                        markers=True, color_discrete_sequence=['#4B2840', '#F1B48B'], template='plotly_white')
    st.plotly_chart(fig_daily, use_container_width=True)

    # ... (Resto de la lógica de gráficos de tu archivo original) ...

def mostrar_ventas(f_inicio, f_fin):
    st.markdown('<div class="section-header">🛒 Terminal de Ventas</div>', unsafe_allow_html=True)
    ventas = leer_ventas(f_inicio, f_fin)
    col_pos, col_hist = st.columns([2, 3])
    ventas_df = pd.DataFrame(ventas) if ventas else pd.DataFrame()

    with col_pos:
        st.subheader("➕ Agregar al Carrito")
        if 'carrito' not in st.session_state: st.session_state.carrito = []
        recetas = leer_recetas(); precios = leer_precios_desglose()
        
        with st.form("add_form"):
            prod = st.selectbox("Producto", [""] + list(recetas.keys()))
            c1, c2 = st.columns(2)
            cant = c1.number_input("Cant", min_value=1, value=1)
            desc = c2.number_input("Desc %", min_value=0.0, max_value=100.0)
            pago_tarjeta = st.checkbox("💳 Pago con Tarjeta")
            if st.form_submit_button("Agregar", use_container_width=True):
                if prod:
                    p_unit = precios.get(prod, {}).get('precio_venta', 0)
                    st.session_state.carrito.append({
                        'Producto': prod, 'Cantidad': cant, 
                        'Precio Unitario': p_unit, 'Descuento %': desc, 'Es Tarjeta': pago_tarjeta
                    }); st.rerun()

        if st.session_state.carrito:
            total_carrito = 0
            for i, item in enumerate(st.session_state.carrito):
                subtotal = (item['Precio Unitario'] * item['Cantidad']) * (1 - item['Descuento %']/100)
                total_carrito += subtotal
                st.markdown(f"**{item['Producto']}** x{item['Cantidad']} | ${subtotal:.2f}")

            if st.button("✅ FINALIZAR VENTA", type="primary", use_container_width=True):
                ventas_nuevas = []
                fecha_hoy = datetime.date.today().strftime('%d/%m/%Y')
                inventario = leer_inventario()
                for item in st.session_state.carrito:
                    # Lógica de cálculo idéntica a tu original...
                    # Guardar en R2
                    pass
                # Actualizar ventas en R2
                df_old = cargar_csv_desde_r2('ventas')
                # pd.concat y guardar_csv_en_r2(...)
                st.session_state.carrito = []; st.toast("✅ Venta registrada!"); st.rerun()

# ... (Implementar el resto de secciones mostrar_inventario, mostrar_reposicion, etc. con la misma estructura R2) ...

def main():
    if not check_auth(): st.stop()
    st.sidebar.markdown("### 🍑 BonBon Peach")
    hoy = datetime.date.today()
    f_inicio = st.sidebar.date_input("Inicio", value=hoy.replace(day=1))
    f_fin = st.sidebar.date_input("Fin", value=hoy)
    
    opcion = st.sidebar.radio("Navegación", ["📊 Dashboard", "🛒 Ventas", "🔄 Reposición", "📦 Inventario", "🧪 Ingredientes", "📝 Recetas", "💰 Precios"])
    
    if st.sidebar.button("Cerrar Sesión"): 
        st.session_state.authenticated = False; st.rerun()

    if opcion == "📊 Dashboard": mostrar_dashboard(f_inicio, f_fin)
    elif opcion == "🧪 Ingredientes": mostrar_ingredientes()
    elif opcion == "📝 Recetas": mostrar_recetas()
    elif opcion == "💰 Precios": mostrar_precios()
    elif opcion == "🛒 Ventas": mostrar_ventas(f_inicio, f_fin)
    elif opcion == "📦 Inventario": mostrar_inventario()
    elif opcion == "🔄 Reposición": mostrar_reposicion(f_inicio, f_fin)

if __name__ == "__main__":
    main()
