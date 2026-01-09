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
from io import StringIO

# =============================================================================
# 1. CONFIGURACIÓN GLOBAL Y PARÁMETROS DE CLOUDFLARE R2
# =============================================================================

# URL de tu Worker de Cloudflare (Debe terminar sin /)
# REEMPLAZA ESTA URL CON LA TUYA REAL CUANDO DESPLIEGUES EL WORKER
WORKER_URL = "https://admin.bonbon-peach.com/api"

st.set_page_config(
    page_title="BonBon - Peach · Sistema de Gestión R2",
    page_icon="🍑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONSTANTES DE NEGOCIO ---
COMISION_BASE_PORCENTAJE = 3.5
TASA_IVA_PORCENTAJE = 16.0
# Cálculo de comisión real incluyendo IVA sobre la comisión bancaria
COMISION_TARJETA = COMISION_BASE_PORCENTAJE * (1 + (TASA_IVA_PORCENTAJE / 100))

# --- DICCIONARIOS PARA TRADUCCIÓN DE FECHAS ---
DIAS_ESP = {
    'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
    'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
}
ORDEN_DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

# =============================================================================
# 2. FUNCIONES DE COMUNICACIÓN CON EL WORKER (API R2)
# =============================================================================

def api_r2_leer(nombre_recurso):
    """
    Solicita datos al Worker de Cloudflare. 
    Se espera que el Worker devuelva un JSON (lista de diccionarios).
    """
    try:
        url = f"{WORKER_URL}/{nombre_recurso}"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return pd.DataFrame(data)
        elif response.status_code == 404:
            # Si el archivo no existe aún en el bucket R2, devolvemos un DataFrame vacío
            return pd.DataFrame()
        else:
            st.error(f"Error de API ({response.status_code}): {response.text}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error de conexión con el servidor R2: {e}")
        return pd.DataFrame()

def api_r2_guardar(df, nombre_recurso):
    """
    Envía un DataFrame al Worker en formato JSON para que sea persistido en R2.
    """
    try:
        if df is None or (isinstance(df, pd.DataFrame) and df.empty and nombre_recurso != 'ventas'):
             # Permitimos guardar ventas vacías si es inicialización, pero validamos general
             pass
        
        # Convertimos el DataFrame a una lista de diccionarios (formato JSON estándar)
        payload = df.to_dict('records')
        url = f"{WORKER_URL}/{nombre_recurso}"
        
        response = requests.post(url, json=payload, timeout=20)
        
        if response.status_code == 200:
            # Limpiamos el caché de Streamlit para asegurar que la próxima lectura sea fresca
            st.cache_data.clear()
            return True
        else:
            st.error(f"Error al guardar en R2 ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        st.error(f"Error crítico al sincronizar con Cloudflare: {e}")
        return False

# =============================================================================
# 3. SEGURIDAD, ESTILOS Y AUTENTICACIÓN
# =============================================================================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Credenciales de acceso
USERS = {
    "admin": hash_password("BonBonAdmin!"),
    "ventas": hash_password("VentasBBP2025!")
}

def check_auth():
    """Maneja el estado de sesión y el formulario de acceso."""
    if st.session_state.get("authenticated"):
        return True
    
    st.markdown("""
        <div style='text-align: center; padding: 40px 0;'>
            <h1 style='color: #F1B48B; font-size: 3rem;'>🍑 BonBon - Peach</h1>
            <p style='color: #666; font-size: 1.2rem;'>Sistema de Gestión Cloud (R2 Storage)</p>
        </div>
    """, unsafe_allow_html=True)
    
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        with st.form("login_form"):
            st.markdown("### Acceso al Sistema")
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Entrar", use_container_width=True)
            
            if submit:
                if u in USERS and hash_password(p) == USERS[u]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Credenciales no válidas.")
    return False

# Estilos CSS personalizados para mantener la identidad visual
st.markdown("""
<style>
    .stApp { background-color: #FFF6FB; }
    .main .block-container {
        background-color: #FFFFFF;
        border-radius: 20px;
        padding: 2rem;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        margin-top: 20px;
    }
    .section-header {
        font-size: 1.8rem; color: #4B2840;
        border-left: 6px solid #F1B48B;
        padding-left: 15px; margin-bottom: 25px;
        font-weight: 700;
    }
    .stButton button {
        background-color: #F1B48B; color: white;
        border: none; border-radius: 10px;
        padding: 0.5rem 1rem; transition: all 0.3s ease;
    }
    .stButton button:hover {
        background-color: #CE8CCF; transform: translateY(-2px);
    }
    [data-testid="stMetricValue"] { color: #4B2840; font-weight: 800; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# 4. UTILIDADES DE PROCESAMIENTO
# =============================================================================

def normalizar_texto(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().strip()
    texto = ' '.join(texto.split())
    texto = str(unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8'))
    return re.sub(r'[^a-z0-9\s]', '', texto)

def clean_and_convert_float(value, default=0.0):
    if value is None or pd.isna(value): return default
    if isinstance(value, (int, float)): return round(float(value), 4)
    try:
        s = str(value).strip().replace('$', '').replace(',', '').replace('%', '')
        return round(float(s), 4) if s else default
    except: return default

# =============================================================================
# 5. GESTIÓN DE DATOS (MIGRADO A API R2)
# =============================================================================

@st.cache_data
def leer_ingredientes_base():
    """Obtiene los ingredientes desde R2."""
    df = api_r2_leer('ingredientes')
    ingredientes = []
    if not df.empty:
        for _, fila in df.iterrows():
            nombre = str(fila.get('Ingrediente', '')).strip()
            if not nombre: continue
            
            c_compra = clean_and_convert_float(fila.get(' Costo de Compra ', 0))
            q_compra = clean_and_convert_float(fila.get('Cantidad por Unidad de Compra', 0))
            c_receta = clean_and_convert_float(fila.get('Costo por Unidad Receta', 0))
            
            if q_compra > 0 and c_receta == 0:
                c_receta = c_compra / q_compra
                
            ingredientes.append({
                'nombre': nombre,
                'proveedor': str(fila.get('Proveedor', '')).strip(),
                'unidad_compra': str(fila.get('Unidad de Compra', '')).strip(),
                'costo_compra': c_compra,
                'cantidad_compra': q_compra,
                'unidad_receta': str(fila.get('Unidad Receta', '')).strip(),
                'costo_receta': c_receta,
                'nombre_normalizado': normalizar_texto(nombre)
            })
    return ingredientes

def guardar_ingredientes_base(lista_ingredientes):
    """Sincroniza ingredientes con R2."""
    rows = []
    for ing in sorted(lista_ingredientes, key=lambda x: x['nombre']):
        rows.append({
            'Ingrediente': ing['nombre'],
            'Proveedor': ing['proveedor'],
            'Unidad de Compra': ing['unidad_compra'],
            ' Costo de Compra ': f"{ing.get('costo_compra', 0.0):.2f}",
            'Cantidad por Unidad de Compra': f"{ing.get('cantidad_compra', 0.0):.4f}",
            'Unidad Receta': ing['unidad_receta'],
            'Costo por Unidad Receta': f"{ing.get('costo_receta', 0.0):.4f}"
        })
    return api_r2_guardar(pd.DataFrame(rows), 'ingredientes')

def leer_inventario():
    """Lee el stock desde R2."""
    df = api_r2_leer('inventario')
    inventario = {}
    if not df.empty:
        for _, fila in df.iterrows():
            nombre = str(fila.get('Ingrediente', '')).strip()
            if nombre:
                inventario[nombre] = {
                    'stock_actual': clean_and_convert_float(fila.get('Stock Actual', 0)),
                    'min': clean_and_convert_float(fila.get('Stock Mínimo', 0)),
                    'max': clean_and_convert_float(fila.get('Stock Máximo', 0))
                }
    return inventario

def guardar_inventario_csv(dict_inv):
    """Guarda el inventario en R2."""
    rows = []
    for nombre, data in dict_inv.items():
        rows.append({
            'Ingrediente': nombre,
            'Stock Actual': f"{data.get('stock_actual', 0.0):.4f}",
            'Stock Mínimo': f"{data.get('min', 0.0):.4f}",
            'Stock Máximo': f"{data.get('max', 0.0):.4f}"
        })
    return api_r2_guardar(pd.DataFrame(rows), 'inventario')

@st.cache_data
def leer_recetas():
    """Lee y calcula costos de recetas desde R2."""
    df = api_r2_leer('recetas')
    ingredientes_master = leer_ingredientes_base()
    recetas = {}
    
    if not df.empty and 'Ingrediente' in df.columns:
        productos = [col for col in df.columns if col != 'Ingrediente']
        for p in productos:
            recetas[p] = {'ingredientes': {}, 'costo_total': 0.0}
            
        for _, fila in df.iterrows():
            ing_nombre = str(fila['Ingrediente']).strip()
            if not ing_nombre: continue
            for p in productos:
                cantidad = clean_and_convert_float(fila.get(p, 0))
                if cantidad > 0:
                    recetas[p]['ingredientes'][ing_nombre] = cantidad
                    
        for prod, data in recetas.items():
            total_costo = 0.0
            for ing_nom, cant_nec in data['ingredientes'].items():
                match = next((i for i in ingredientes_master if i['nombre'] == ing_nom), None)
                if match: total_costo += match['costo_receta'] * cant_nec
            recetas[prod]['costo_total'] = round(total_costo, 2)
    return recetas

def guardar_recetas_csv(dict_recetas):
    """Guarda recetas en formato matricial en R2."""
    set_ings = set()
    for r in dict_recetas.values(): set_ings.update(r['ingredientes'].keys())
    lista_ings = sorted(list(set_ings))
    productos = sorted(dict_recetas.keys())
    
    matrix = []
    for ing in lista_ings:
        fila = {'Ingrediente': ing}
        for p in productos:
            fila[p] = dict_recetas[p]['ingredientes'].get(ing, '')
        matrix.append(fila)
    return api_r2_guardar(pd.DataFrame(matrix), 'recetas')

def leer_ventas(f_inicio=None, f_fin=None):
    """Histórico de ventas desde R2."""
    df = api_r2_leer('ventas')
    if df.empty: return []
    
    if 'Fecha' in df.columns:
        df['Fecha_DT'] = pd.to_datetime(df['Fecha'], format='%d/%m/%Y', errors='coerce')
        df = df.dropna(subset=['Fecha_DT'])
        if f_inicio and f_fin:
            mask = (df['Fecha_DT'].dt.date >= f_inicio) & (df['Fecha_DT'].dt.date <= f_fin)
            df = df.loc[mask]
            
        cols_num = ['Total Venta Bruto', 'Ganancia Neta', 'Cantidad', 'Comision ($)', 'Descuento ($)', 'Costo Total']
        for c in cols_num:
            if c in df.columns: df[c] = df[c].apply(clean_and_convert_float)
                
    return df.to_dict('records')

def leer_precios_desglose():
    """Maestro de precios desde R2."""
    df = api_r2_leer('desglose')
    precios = {}
    if not df.empty:
        for _, row in df.iterrows():
            p_nom = str(row.get('Producto', ''))
            if p_nom:
                precios[p_nom] = {
                    'precio_venta': clean_and_convert_float(row.get('Precio Venta')),
                    'margen': clean_and_convert_float(row.get('Margen Bruto')),
                    'margen_porc': clean_and_convert_float(row.get('Margen Bruto (%)'))
                }
    return precios

def calcular_reposicion_sugerida(f_inicio, f_fin):
    """Calcula insumos necesarios basados en ventas históricas."""
    ventas = leer_ventas(f_inicio, f_fin)
    recetas = leer_recetas()
    ings_base = leer_ingredientes_base()
    uso = {}
    
    for v in ventas:
        prod = v.get('Producto')
        cant = clean_and_convert_float(v.get('Cantidad', 0))
        if prod in recetas:
            for ing, cant_r in recetas[prod]['ingredientes'].items():
                uso[ing] = uso.get(ing, 0) + (cant_r * cant)
                
    res = []
    for ing, cant_n in uso.items():
        info = next((i for i in ings_base if i['nombre'] == ing), None)
        if info:
            costo_r = cant_n * info['costo_receta']
            res.append({
                'Ingrediente': ing, 'Cantidad Necesaria': cant_n,
                'Unidad': info['unidad_receta'], 'Proveedor': info['proveedor'],
                'Costo Reposición': costo_r
            })
    return sorted(res, key=lambda x: x['Ingrediente'])

# =============================================================================
# 6. VISTAS DE LA INTERFAZ
# =============================================================================

def mostrar_dashboard(f_inicio, f_fin):
    st.markdown('<div class="section-header">📊 Dashboard de Rendimiento</div>', unsafe_allow_html=True)
    ventas_raw = leer_ventas(f_inicio, f_fin)
    if not ventas_raw:
        st.info("No hay datos para el período seleccionado.")
        return

    df = pd.DataFrame(ventas_raw)
    t_venta = df['Total Venta Bruto'].sum()
    t_ganancia = df['Ganancia Neta'].sum()
    t_trans = len(df)
    t_avg = t_venta / t_trans if t_trans > 0 else 0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ventas Totales", f"${t_venta:,.2f}")
    m2.metric("Ganancia Neta", f"${t_ganancia:,.2f}")
    m3.metric("Ticket Promedio", f"${t_avg:,.2f}")
    m4.metric("Transacciones", f"{t_trans}")
    
    st.divider()
    
    c_izq, c_der = st.columns([2, 1])
    with c_izq:
        st.subheader("Tendencia Diaria")
        df_d = df.groupby(df['Fecha_DT'].dt.date).agg({'Total Venta Bruto': 'sum', 'Ganancia Neta': 'sum'}).reset_index()
        fig = px.area(df_d, x='Fecha_DT', y=['Total Venta Bruto', 'Ganancia Neta'], 
                      color_discrete_map={'Total Venta Bruto': '#F1B48B', 'Ganancia Neta': '#4B2840'},
                      template='plotly_white')
        st.plotly_chart(fig, use_container_width=True)
        
    with c_der:
        st.subheader("Métodos de Pago")
        df_p = df.groupby('Forma Pago')['Total Venta Bruto'].sum().reset_index()
        fig_p = px.pie(df_p, values='Total Venta Bruto', names='Forma Pago', hole=0.4,
                       color_discrete_sequence=['#CE8CCF', '#F1B48B'])
        st.plotly_chart(fig_p, use_container_width=True)

def mostrar_ventas(f_inicio, f_fin):
    st.markdown('<div class="section-header">🛒 Terminal de Ventas</div>', unsafe_allow_html=True)
    
    if 'carrito' not in st.session_state: st.session_state.carrito = []
    
    col_pos, col_hist = st.columns([2, 3])
    
    with col_pos:
        st.subheader("Punto de Venta")
        recetas = leer_recetas(); precios = leer_precios_desglose()
        
        with st.form("pos_form", clear_on_submit=True):
            prod = st.selectbox("Producto", [""] + sorted(list(recetas.keys())))
            c1, c2 = st.columns(2)
            cant = c1.number_input("Cantidad", min_value=1, value=1)
            desc = c2.number_input("Descuento %", min_value=0.0, max_value=100.0)
            tarjeta = st.toggle("💳 Pago con Tarjeta")
            
            if st.form_submit_button("Agregar", use_container_width=True):
                if prod:
                    p_u = precios.get(prod, {}).get('precio_venta', 0)
                    st.session_state.carrito.append({
                        'Producto': prod, 'Cantidad': cant, 
                        'Precio Unitario': p_u, 'Descuento %': desc, 'Es Tarjeta': tarjeta
                    })
                    st.rerun()

        if st.session_state.carrito:
            st.divider()
            total_c = 0
            for i, item in enumerate(st.session_state.carrito):
                sub = (item['Precio Unitario'] * item['Cantidad']) * (1 - item['Descuento %']/100)
                total_c += sub
                with st.container():
                    cd1, cd2 = st.columns([4, 1])
                    cd1.write(f"**{item['Producto']}** (x{item['Cantidad']}) - ${sub:,.2f}")
                    if cd2.button("🗑️", key=f"del_{i}"):
                        st.session_state.carrito.pop(i); st.rerun()
            
            st.write(f"### Total: ${total_c:,.2f}")
            if st.button("✅ REGISTRAR VENTA", type="primary", use_container_width=True):
                # Lógica de guardado...
                ventas_existentes = api_r2_leer('ventas')
                nuevas = []
                inv = leer_inventario()
                f_str = datetime.date.today().strftime('%d/%m/%Y')
                
                for item in st.session_state.carrito:
                    bruto = item['Precio Unitario'] * item['Cantidad']
                    monto_d = bruto * (item['Descuento %']/100)
                    neto_desc = bruto - monto_d
                    com = neto_desc * (COMISION_TARJETA/100) if item['Es Tarjeta'] else 0
                    costo_t = recetas[item['Producto']]['costo_total'] * item['Cantidad']
                    
                    nuevas.append({
                        'Fecha': f_str, 'Producto': item['Producto'], 'Cantidad': item['Cantidad'],
                        'Precio Unitario': item['Precio Unitario'], 'Total Venta Bruto': bruto,
                        'Descuento ($)': monto_d, 'Costo Total': costo_t,
                        'Comision ($)': com, 'Ganancia Neta': (neto_desc - com - costo_t),
                        'Forma Pago': "Tarjeta" if item['Es Tarjeta'] else "Efectivo"
                    })
                    # Descontar stock
                    for ing_n, q_r in recetas[item['Producto']]['ingredientes'].items():
                        if ing_n in inv:
                            inv[ing_n]['stock_actual'] -= (q_r * item['Cantidad'])
                
                df_f = pd.concat([ventas_existentes, pd.DataFrame(nuevas)], ignore_index=True)
                if api_r2_guardar(df_f, 'ventas') and guardar_inventario_csv(inv):
                    st.session_state.carrito = []
                    st.success("Venta sincronizada con R2."); st.rerun()

    with col_hist:
        st.subheader("Últimos Registros")
        vh = leer_ventas(f_inicio, f_fin)
        if vh:
            st.dataframe(pd.DataFrame(vh)[['Fecha', 'Producto', 'Cantidad', 'Total Venta Bruto', 'Forma Pago']], 
                         use_container_width=True, hide_index=True)

def mostrar_inventario():
    st.markdown('<div class="section-header">📦 Inventario y Almacén</div>', unsafe_allow_html=True)
    inv = leer_inventario()
    if not inv:
        st.warning("No hay datos de inventario en R2.")
    else:
        df_inv = pd.DataFrame([{'Ingrediente': k, **v} for k, v in inv.items()])
        st.dataframe(df_inv, use_container_width=True, hide_index=True)
        
        with st.expander("Ajuste de Stock"):
            with st.form("adj"):
                sel_ing = st.selectbox("Ingrediente", df_inv['Ingrediente'].tolist())
                nueva_q = st.number_input("Cantidad a sumar/restar", value=0.0)
                if st.form_submit_button("Actualizar"):
                    inv[sel_ing]['stock_actual'] += nueva_q
                    if guardar_inventario_csv(inv): 
                        st.success("Actualizado"); st.rerun()

def mostrar_ingredientes():
    st.markdown('<div class="section-header">🧪 Maestro de Ingredientes</div>', unsafe_allow_html=True)
    ings = leer_ingredientes_base()
    if ings:
        st.dataframe(pd.DataFrame(ings).drop(columns=['nombre_normalizado']), use_container_width=True)
    
    with st.expander("Añadir / Editar Ingrediente"):
        with st.form("ing_f"):
            nom = st.text_input("Nombre")
            c1, c2 = st.columns(2)
            prov = c1.text_input("Proveedor")
            costo = c2.number_input("Costo Compra", min_value=0.0)
            u_c = st.text_input("Unidad Compra")
            q_c = st.number_input("Equivalencia en Receta", min_value=0.01)
            u_r = st.text_input("Unidad Receta")
            
            if st.form_submit_button("Guardar en R2"):
                nuevo = {
                    'nombre': nom, 'proveedor': prov, 'unidad_compra': u_c,
                    'costo_compra': costo, 'cantidad_compra': q_c,
                    'unidad_receta': u_r, 'costo_receta': costo/q_c
                }
                ings = [i for i in ings if i['nombre'] != nom]
                ings.append(nuevo)
                if guardar_ingredientes_base(ings): st.success("Sincronizado"); st.rerun()

def mostrar_recetas():
    st.markdown('<div class="section-header">📝 Recetas y Fichas Técnicas</div>', unsafe_allow_html=True)
    recetas = leer_recetas(); ings = leer_ingredientes_base()
    sel = st.selectbox("Seleccionar Receta", [""] + list(recetas.keys()))
    
    if sel:
        st.write(f"### Costo: ${recetas[sel]['costo_total']:.2f}")
        df_r = pd.DataFrame([{'Ingrediente': k, 'Cantidad': v} for k, v in recetas[sel]['ingredientes'].items()])
        st.table(df_r)
        
        with st.form("add_i_r"):
            i_sel = st.selectbox("Insumo", [i['nombre'] for i in ings])
            q_sel = st.number_input("Cantidad", min_value=0.0)
            if st.form_submit_button("Actualizar Receta"):
                recetas[sel]['ingredientes'][i_sel] = q_sel
                if guardar_recetas_csv(recetas): st.rerun()

def mostrar_precios():
    st.markdown('<div class="section-header">💰 Análisis de Precios</div>', unsafe_allow_html=True)
    recetas = leer_recetas(); precios = leer_precios_desglose()
    
    rows = []
    for p, data in recetas.items():
        costo = data['costo_total']
        venta = precios.get(p, {}).get('precio_venta', 0)
        rows.append({
            'Producto': p, 'Costo': costo, 'Venta': venta, 'Margen $': venta - costo
        })
    
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

def mostrar_reposicion(f_ini, f_fin):
    st.markdown('<div class="section-header">🔄 Reposición Sugerida</div>', unsafe_allow_html=True)
    rep = calcular_reposicion_sugerida(f_ini, f_fin)
    if rep:
        df = pd.DataFrame(rep)
        st.metric("Inversión Necesaria", f"${df['Costo Reposición'].sum():,.2f}")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Sin datos para calcular.")

# =============================================================================
# 7. CICLO PRINCIPAL
# =============================================================================

def main():
    if not check_auth(): st.stop()
    
    st.sidebar.title("🍑 BonBon Peach")
    hoy = datetime.date.today()
    f_ini = st.sidebar.date_input("Inicio", hoy.replace(day=1))
    f_fin = st.sidebar.date_input("Fin", hoy)
    
    opc = st.sidebar.radio("Navegación", 
        ["📊 Dashboard", "🛒 Ventas", "🔄 Reposición", "📦 Inventario", "🧪 Ingredientes", "📝 Recetas", "💰 Precios"])
    
    st.sidebar.divider()
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.authenticated = False
        st.rerun()

    if opc == "📊 Dashboard": mostrar_dashboard(f_ini, f_fin)
    elif opc == "🛒 Ventas": mostrar_ventas(f_ini, f_fin)
    elif opc == "🔄 Reposición": mostrar_reposicion(f_ini, f_fin)
    elif opc == "📦 Inventario": mostrar_inventario()
    elif opc == "🧪 Ingredientes": mostrar_ingredientes()
    elif opc == "📝 Recetas": mostrar_recetas()
    elif opc == "💰 Precios": mostrar_precios()

if __name__ == "__main__":
    main()
