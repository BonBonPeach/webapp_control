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
# REEMPLAZA ESTA URL CON LA TUYA REAL
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
# Cálculo de comisión real incluyendo IVA sobre la comisión
COMISION_TARJETA = COMISION_BASE_PORCENTAJE * (1 + (TASA_IVA_PORCENTAJE / 100))

# --- DICCIONARIOS DE TIEMPO ---
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
    Solicita datos al Worker. 
    Se espera que el Worker devuelva un JSON (lista de diccionarios).
    """
    try:
        url = f"{WORKER_URL}/{nombre_recurso}"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return pd.DataFrame(data)
        elif response.status_code == 404:
            # Si el archivo no existe en R2, devolvemos un DF vacío
            return pd.DataFrame()
        else:
            st.error(f"Error API ({response.status_code}): {response.text}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error de conexión con el servidor R2: {e}")
        return pd.DataFrame()

def api_r2_guardar(df, nombre_recurso):
    """
    Envía un DataFrame al Worker en formato JSON para que sea guardado en R2.
    """
    try:
        if df is None:
            return False
        
        # Convertir a lista de diccionarios para el envío JSON
        payload = df.to_dict('records')
        url = f"{WORKER_URL}/{nombre_recurso}"
        
        response = requests.post(url, json=payload, timeout=20)
        
        if response.status_code == 200:
            # Limpiamos caché local de Streamlit para forzar recarga de datos
            st.cache_data.clear()
            return True
        else:
            st.error(f"Error al guardar en R2 ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        st.error(f"Error crítico al sincronizar con R2: {e}")
        return False

# =============================================================================
# 3. SEGURIDAD Y ESTILOS
# =============================================================================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Credenciales (Mantener igual al original)
USERS = {
    "admin": hash_password("BonBonAdmin!"),
    "ventas": hash_password("VentasBBP2025!")
}

def check_auth():
    """Maneja el estado de sesión y el formulario de login."""
    if st.session_state.get("authenticated"):
        return True
    
    st.markdown("""
        <div style='text-align: center; padding: 40px 0;'>
            <h1 style='color: #F1B48B; font-size: 3rem;'>🍑 BonBon - Peach</h1>
            <p style='color: #666; font-size: 1.2rem;'>Sistema de Control de Inventarios y Ventas Cloud</p>
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
                    st.error("Usuario o contraseña no válidos.")
    return False

# Estilos CSS personalizados para mantener la identidad visual
st.markdown("""
<style>
    /* Fondo general */
    .stApp { background-color: #FFF6FB; }
    
    /* Contenedor principal */
    .main .block-container {
        background-color: #FFFFFF;
        border-radius: 20px;
        padding: 2rem;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        margin-top: 20px;
    }
    
    /* Encabezados de sección */
    .section-header {
        font-size: 1.8rem; 
        color: #4B2840;
        border-left: 6px solid #F1B48B;
        padding-left: 15px;
        margin-bottom: 25px;
        margin-top: 10px;
        font-weight: 700;
    }
    
    /* Botones personalizados */
    .stButton button {
        background-color: #F1B48B;
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
    }
    .stButton button:hover {
        background-color: #CE8CCF;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    
    /* Métricas */
    [data-testid="stMetricValue"] {
        color: #4B2840;
        font-weight: 800;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #EEE;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# 4. UTILIDADES DE PROCESAMIENTO
# =============================================================================

def normalizar_texto(texto):
    """Limpia texto para comparaciones consistentes."""
    if not isinstance(texto, str): return ""
    texto = texto.lower().strip()
    texto = ' '.join(texto.split())
    # Eliminar acentos
    texto = str(unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8'))
    # Quitar caracteres especiales
    return re.sub(r'[^a-z0-9\s]', '', texto)

def clean_and_convert_float(value, default=0.0):
    """Convierte strings financieros o nulos a float de forma segura."""
    if value is None or pd.isna(value):
        return default
    if isinstance(value, (int, float)):
        return round(float(value), 4)
    
    try:
        # Limpieza de símbolos comunes
        s = str(value).strip().replace('$', '').replace(',', '').replace('%', '')
        if not s:
            return default
        return round(float(s), 4)
    except (ValueError, TypeError):
        return default

# =============================================================================
# 5. GESTIÓN DE DATOS (REMPLAZO DE CSV LOCAL POR R2)
# =============================================================================

@st.cache_data
def leer_ingredientes_base():
    """Carga y procesa la lista de ingredientes desde R2."""
    df = api_r2_leer('ingredientes')
    ingredientes = []
    
    if not df.empty:
        for _, fila in df.iterrows():
            nombre = str(fila.get('Ingrediente', '')).strip()
            if not nombre: continue
            
            costo_compra = clean_and_convert_float(fila.get(' Costo de Compra ', 0))
            cant_compra = clean_and_convert_float(fila.get('Cantidad por Unidad de Compra', 0))
            costo_receta = clean_and_convert_float(fila.get('Costo por Unidad Receta', 0))
            
            # Recalcular si el costo unitario no está presente
            if cant_compra > 0 and costo_receta == 0:
                costo_receta = costo_compra / cant_compra
                
            ingredientes.append({
                'nombre': nombre,
                'proveedor': str(fila.get('Proveedor', '')).strip(),
                'unidad_compra': str(fila.get('Unidad de Compra', '')).strip(),
                'costo_compra': costo_compra,
                'cantidad_compra': cant_compra,
                'unidad_receta': str(fila.get('Unidad Receta', '')).strip(),
                'costo_receta': costo_receta,
                'nombre_normalizado': normalizar_texto(nombre)
            })
    return ingredientes

def guardar_ingredientes_base(lista_ingredientes):
    """Convierte la lista a DataFrame y la sube a R2."""
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
    """Lee el stock actual desde R2."""
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

def guardar_inventario_r2(dict_inventario):
    """Sincroniza el diccionario de inventario con R2."""
    rows = []
    for nombre, data in dict_inventario.items():
        rows.append({
            'Ingrediente': nombre,
            'Stock Actual': f"{data.get('stock_actual', 0.0):.4f}",
            'Stock Mínimo': f"{data.get('min', 0.0):.4f}",
            'Stock Máximo': f"{data.get('max', 0.0):.4f}"
        })
    return api_r2_guardar(pd.DataFrame(rows), 'inventario')

@st.cache_data
def leer_recetas():
    """Genera el diccionario de recetas cruzando datos de R2 e Ingredientes."""
    df = api_r2_leer('recetas')
    ingredientes_master = leer_ingredientes_base()
    recetas = {}
    
    if not df.empty and 'Ingrediente' in df.columns:
        # Los nombres de los productos son las columnas (excepto 'Ingrediente')
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
                    
        # Calcular costos totales por receta
        for prod, data in recetas.items():
            total_costo = 0.0
            for ing_nombre, cant_necesaria in data['ingredientes'].items():
                # Buscar el costo unitario en el maestro de ingredientes
                match = next((i for i in ingredientes_master if i['nombre'] == ing_nombre), None)
                if match:
                    total_costo += match['costo_receta'] * cant_necesaria
            recetas[prod]['costo_total'] = round(total_costo, 2)
            
    return recetas

def guardar_recetas_r2(dict_recetas):
    """Transforma el diccionario de recetas a formato matricial para R2."""
    # Obtener lista única de todos los ingredientes usados en cualquier receta
    set_ingredientes = set()
    for r in dict_recetas.values():
        set_ingredientes.update(r['ingredientes'].keys())
    
    lista_ings = sorted(list(set_ingredientes))
    productos = sorted(dict_recetas.keys())
    
    matrix = []
    for ing in lista_ings:
        fila = {'Ingrediente': ing}
        for p in productos:
            # Si el ingrediente está en la receta, poner la cantidad, sino vacío
            valor = dict_recetas[p]['ingredientes'].get(ing, '')
            fila[p] = valor
        matrix.append(fila)
        
    return api_r2_guardar(pd.DataFrame(matrix), 'recetas')

def leer_ventas(f_inicio=None, f_fin=None):
    """Recupera el histórico de ventas filtrado por fecha."""
    df = api_r2_leer('ventas')
    if df.empty:
        return pd.DataFrame()
        
    # Procesar fechas para filtrado
    if 'Fecha' in df.columns:
        df['Fecha_DT'] = pd.to_datetime(df['Fecha'], format='%d/%m/%Y', errors='coerce')
        df = df.dropna(subset=['Fecha_DT'])
        
        if f_inicio and f_fin:
            mask = (df['Fecha_DT'].dt.date >= f_inicio) & (df['Fecha_DT'].dt.date <= f_fin)
            df = df.loc[mask]
            
        # Asegurar tipos numéricos para cálculos en el Dashboard
        cols_num = ['Total Venta Bruto', 'Ganancia Neta', 'Cantidad', 'Comision ($)', 'Descuento ($)', 'Costo Total']
        for c in cols_num:
            if c in df.columns:
                df[c] = df[c].apply(clean_and_convert_float)
                
    return df

def leer_precios_desglose():
    """Obtiene el maestro de precios y márgenes configurados."""
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

# =============================================================================
# 6. LÓGICA DE NEGOCIO Y CÁLCULOS
# =============================================================================

def procesar_finalizacion_venta(carrito):
    """
    Calcula costos, comisiones, impuestos y descuenta inventario.
    Actualiza R2 automáticamente.
    """
    if not carrito:
        return False
    
    ventas_historico_df = api_r2_leer('ventas')
    inventario_actual = leer_inventario()
    recetas_master = leer_recetas()
    
    nuevas_filas_ventas = []
    fecha_str = datetime.date.today().strftime('%d/%m/%Y')
    
    for item in carrito:
        prod = item['Producto']
        cant = item['Cantidad']
        p_unitario = item['Precio Unitario']
        desc_porc = item['Descuento %']
        tarjeta = item['Es Tarjeta']
        
        # 1. Cálculos monetarios
        bruto = p_unitario * cant
        monto_descuento = bruto * (desc_porc / 100)
        subtotal_post_desc = bruto - monto_descuento
        
        # Comisión bancaria si aplica
        comision_monto = subtotal_post_desc * (COMISION_TARJETA / 100) if tarjeta else 0.0
        
        # Costos de producción
        costo_unitario_prod = recetas_master.get(prod, {}).get('costo_total', 0.0)
        costo_total_venta = costo_unitario_prod * cant
        
        # Utilidades
        total_neto_ingreso = subtotal_post_desc - comision_monto
        utilidad_neta = total_neto_ingreso - costo_total_venta
        
        # 2. Registrar fila
        nuevas_filas_ventas.append({
            'Fecha': fecha_str,
            'Producto': prod,
            'Cantidad': cant,
            'Precio Unitario': p_unitario,
            'Total Venta Bruto': round(bruto, 2),
            'Descuento (%)': desc_porc,
            'Descuento ($)': round(monto_descuento, 2),
            'Costo Total': round(costo_total_venta, 2),
            'Ganancia Bruta': round(subtotal_post_desc - costo_total_venta, 2),
            'Comision ($)': round(comision_monto, 2),
            'Ganancia Neta': round(utilidad_neta, 2),
            'Forma Pago': "Tarjeta" if tarjeta else "Efectivo"
        })
        
        # 3. Descuento de Inventario
        if prod in recetas_master:
            for ing_nom, cant_receta in recetas_master[prod]['ingredientes'].items():
                if ing_nom in inventario_actual:
                    descuento_total_ing = cant_receta * cant
                    inventario_actual[ing_nom]['stock_actual'] -= descuento_total_ing
                    # Evitar stocks negativos
                    if inventario_actual[ing_nom]['stock_actual'] < 0:
                        inventario_actual[ing_nom]['stock_actual'] = 0
    
    # 4. Persistencia en R2
    df_actualizado_ventas = pd.concat([ventas_historico_df, pd.DataFrame(nuevas_filas_ventas)], ignore_index=True)
    
    exito_v = api_r2_guardar(df_actualizado_ventas, 'ventas')
    exito_i = guardar_inventario_r2(inventario_actual)
    
    return exito_v and exito_i

# =============================================================================
# 7. VISTAS DE LA INTERFAZ (UI)
# =============================================================================

def vista_dashboard(f_ini, f_fin):
    st.markdown('<div class="section-header">📊 Análisis de Rendimiento</div>', unsafe_allow_html=True)
    
    df_v = leer_ventas(f_ini, f_fin)
    
    if df_v.empty:
        st.info("No se encontraron registros de ventas para el período seleccionado.")
        return

    # --- KPIs SUPERIORES ---
    t_venta = df_v['Total Venta Bruto'].sum()
    t_ganancia = df_v['Ganancia Neta'].sum()
    t_transacciones = len(df_v)
    ticket_avg = t_venta / t_transacciones if t_transacciones > 0 else 0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ventas Totales", f"${t_venta:,.2f}")
    m2.metric("Ganancia Neta", f"${t_ganancia:,.2f}", 
              delta=f"{(t_ganancia/t_venta*100):.1f}% Margen" if t_venta > 0 else None)
    m3.metric("Ticket Promedio", f"${ticket_avg:,.2f}")
    m4.metric("Transacciones", f"{t_transacciones}")
    
    st.divider()
    
    # --- GRÁFICOS ---
    col_izq, col_der = st.columns([2, 1])
    
    with col_izq:
        st.subheader("Evolución de Ingresos")
        df_diario = df_v.groupby(df_v['Fecha_DT'].dt.date).agg({
            'Total Venta Bruto': 'sum',
            'Ganancia Neta': 'sum'
        }).reset_index().rename(columns={'Fecha_DT': 'Día'})
        
        fig_line = px.area(df_diario, x='Día', y=['Total Venta Bruto', 'Ganancia Neta'],
                           title="Venta Bruta vs Utilidad Neta",
                           color_discrete_map={'Total Venta Bruto': '#F1B48B', 'Ganancia Neta': '#4B2840'},
                           template='plotly_white')
        st.plotly_chart(fig_line, use_container_width=True)
        
    with col_der:
        st.subheader("Métodos de Pago")
        df_pago = df_v.groupby('Forma Pago')['Total Venta Bruto'].sum().reset_index()
        fig_pie = px.pie(df_pago, values='Total Venta Bruto', names='Forma Pago',
                         hole=0.4, color_discrete_sequence=['#CE8CCF', '#F1B48B'])
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- TOP PRODUCTOS ---
    st.subheader("Ranking de Productos")
    prod_stats = df_v.groupby('Producto').agg({
        'Cantidad': 'sum',
        'Ganancia Neta': 'sum'
    }).reset_index().sort_values('Ganancia Neta', ascending=False)
    
    c_top1, c_top2 = st.columns(2)
    with c_top1:
        fig_bar1 = px.bar(prod_stats.head(10), x='Ganancia Neta', y='Producto', orientation='h',
                          title="Top 10 por Rentabilidad ($)", color='Ganancia Neta',
                          color_continuous_scale='Purpor')
        st.plotly_chart(fig_bar1, use_container_width=True)
    with c_top2:
        fig_bar2 = px.bar(prod_stats.sort_values('Cantidad', ascending=False).head(10), 
                          x='Cantidad', y='Producto', orientation='h',
                          title="Top 10 por Volumen de Ventas", color='Cantidad',
                          color_continuous_scale='Peach')
        st.plotly_chart(fig_bar2, use_container_width=True)

def vista_ventas():
    st.markdown('<div class="section-header">🛒 Terminal de Punto de Venta</div>', unsafe_allow_html=True)
    
    if 'carrito' not in st.session_state:
        st.session_state.carrito = []
        
    recetas = leer_recetas()
    precios_master = leer_precios_desglose()
    
    col_form, col_cart = st.columns([1, 1])
    
    with col_form:
        st.subheader("Añadir Producto")
        with st.form("pos_form", clear_on_submit=True):
            prod_sel = st.selectbox("Seleccione Producto", [""] + sorted(list(recetas.keys())))
            c1, c2 = st.columns(2)
            cantidad = c1.number_input("Cantidad", min_value=1, value=1, step=1)
            descuento = c2.number_input("Descuento %", min_value=0.0, max_value=100.0, value=0.0)
            es_tarjeta = st.toggle("💳 Pago con Tarjeta / Transferencia")
            
            if st.form_submit_button("Agregar al Carrito", use_container_width=True):
                if prod_sel:
                    p_info = precios_master.get(prod_sel, {'precio_venta': 0.0})
                    st.session_state.carrito.append({
                        'Producto': prod_sel,
                        'Cantidad': cantidad,
                        'Precio Unitario': p_info['precio_venta'],
                        'Descuento %': descuento,
                        'Es Tarjeta': es_tarjeta
                    })
                    st.rerun()
                else:
                    st.error("Por favor seleccione un producto.")

    with col_cart:
        st.subheader("Detalle del Carrito")
        if not st.session_state.carrito:
            st.info("El carrito está vacío.")
        else:
            total_vca = 0
            for idx, item in enumerate(st.session_state.carrito):
                sub = (item['Precio Unitario'] * item['Cantidad']) * (1 - item['Descuento %']/100)
                total_vca += sub
                
                with st.container():
                    cd1, cd2, cd3 = st.columns([3, 2, 1])
                    cd1.markdown(f"**{item['Producto']}** (x{item['Cantidad']})")
                    cd2.write(f"${sub:,.2f}")
                    if cd3.button("🗑️", key=f"del_{idx}"):
                        st.session_state.carrito.pop(idx)
                        st.rerun()
            
            st.divider()
            st.write(f"### Total: ${total_vca:,.2f}")
            
            if st.button("✅ FINALIZAR Y REGISTRAR VENTA", type="primary", use_container_width=True):
                with st.spinner("Sincronizando con R2..."):
                    if procesar_finalizacion_venta(st.session_state.carrito):
                        st.session_state.carrito = []
                        st.success("Venta procesada con éxito y stock actualizado.")
                        st.balloons()
                        st.rerun()

def vista_inventario():
    st.markdown('<div class="section-header">📦 Gestión de Stock e Ingredientes</div>', unsafe_allow_html=True)
    
    tabs = st.tabs(["Stock Actual", "Maestro de Ingredientes", "Recetas"])
    
    with tabs[0]:
        st.subheader("Estado del Almacén")
        inv = leer_inventario()
        if not inv:
            st.warning("No hay datos de inventario.")
        else:
            rows = []
            for k, v in inv.items():
                stock = v['stock_actual']
                minimo = v['min']
                # Semáforo de estado
                estado = "✅ OK"
                if stock <= 0: estado = "❌ AGOTADO"
                elif stock < minimo: estado = "🚨 RELLENAR URGENTE"
                elif stock < minimo * 1.5: estado = "⚠️ Bajo"
                
                rows.append({
                    'Ingrediente': k,
                    'Stock Actual': round(stock, 2),
                    'Mínimo': minimo,
                    'Estado': estado
                })
            
            df_inv = pd.DataFrame(rows)
            st.dataframe(df_inv, use_container_width=True, hide_index=True)
            
            st.divider()
            st.subheader("Ajuste Manual / Entrada de Mercancía")
            with st.form("ajuste_inv"):
                c1, c2 = st.columns(2)
                ing_ajuste = c1.selectbox("Ingrediente", df_inv['Ingrediente'].tolist())
                cant_ajuste = c2.number_input("Cantidad a sumar (negativo para restar)", value=0.0)
                if st.form_submit_button("Actualizar Stock"):
                    inv[ing_ajuste]['stock_actual'] += cant_ajuste
                    if guardar_inventario_r2(inv):
                        st.success(f"Stock de {ing_ajuste} actualizado.")
                        st.rerun()

    with tabs[1]:
        st.subheader("Configuración de Ingredientes")
        ings = leer_ingredientes_base()
        
        with st.expander("➕ Añadir / Editar Ingrediente Maestro"):
            with st.form("form_ing_maestro"):
                nom = st.text_input("Nombre del Ingrediente")
                prov = st.text_input("Proveedor")
                c_a, c_b = st.columns(2)
                u_c = c_a.text_input("Unidad Compra (ej. Bulto 20kg)")
                u_r = c_b.text_input("Unidad Receta (ej. gr)")
                c_c, c_d = st.columns(2)
                costo_c = c_c.number_input("Costo de Compra ($)", min_value=0.0)
                cant_c = c_d.number_input("Equivalencia (Cuantas U.R. hay en U.C.)", min_value=0.01)
                
                if st.form_submit_button("Guardar en R2"):
                    # Lógica de guardado...
                    nuevo = {
                        'nombre': nom, 'proveedor': prov, 'unidad_compra': u_c,
                        'unidad_receta': u_r, 'costo_compra': costo_c, 'cantidad_compra': cant_c,
                        'costo_receta': costo_c/cant_c
                    }
                    ings = [i for i in ings if i['nombre'] != nom]
                    ings.append(nuevo)
                    if guardar_ingredientes_base(ings):
                        st.success("Ingrediente guardado."); st.rerun()
        
        if ings:
            st.dataframe(pd.DataFrame(ings).drop(columns=['nombre_normalizado']), use_container_width=True)

    with tabs[2]:
        st.subheader("Configurador de Recetas")
        recetas = leer_recetas()
        ings_maestro = leer_ingredientes_base()
        
        sel_r = st.selectbox("Seleccione Receta para editar", ["-- Nueva Receta --"] + list(recetas.keys()))
        
        if sel_r == "-- Nueva Receta --":
            nom_n = st.text_input("Nombre de la nueva receta")
            if st.button("Crear"):
                recetas[nom_n] = {'ingredientes': {}, 'costo_total': 0.0}
                guardar_recetas_r2(recetas); st.rerun()
        else:
            datos_r = recetas[sel_r]
            st.write(f"### Costo de Producción: ${datos_r['costo_total']:.2f}")
            
            # Mostrar tabla de ingredientes actuales en la receta
            if datos_r['ingredientes']:
                df_ri = pd.DataFrame([{'Ingrediente': k, 'Cantidad': v} for k, v in datos_r['ingredientes'].items()])
                st.table(df_ri)
                
            # Formulario para añadir ingredientes a la receta
            with st.form("add_ing_receta"):
                c1, c2 = st.columns([2, 1])
                ing_add = c1.selectbox("Ingrediente a añadir", [i['nombre'] for i in ings_maestro])
                cant_add = c2.number_input("Cantidad (U.R.)", min_value=0.0)
                if st.form_submit_button("Actualizar Ingrediente en Receta"):
                    recetas[sel_r]['ingredientes'][ing_add] = cant_add
                    guardar_recetas_r2(recetas); st.rerun()

def vista_precios():
    st.markdown('<div class="section-header">💰 Gestión de Márgenes y Precios</div>', unsafe_allow_html=True)
    
    recetas = leer_recetas()
    precios_actuales = leer_precios_desglose()
    
    rows = []
    for prod, info in recetas.items():
        costo = info['costo_total']
        p_venta = precios_actuales.get(prod, {}).get('precio_venta', 0.0)
        margen_abs = p_venta - costo
        margen_rel = (margen_abs / p_venta * 100) if p_venta > 0 else 0
        
        rows.append({
            'Producto': prod,
            'Costo de Producción': costo,
            'Precio de Venta Actual': p_venta,
            'Margen ($)': margen_abs,
            'Margen (%)': margen_rel
        })
    
    df_p = pd.DataFrame(rows)
    st.dataframe(df_p.style.format({
        'Costo de Producción': '${:,.2f}',
        'Precio de Venta Actual': '${:,.2f}',
        'Margen ($)': '${:,.2f}',
        'Margen (%)': '{:.1f}%'
    }), use_container_width=True, hide_index=True)
    
    st.divider()
    st.subheader("Actualizar Precio de Venta")
    with st.form("update_price"):
        up_prod = st.selectbox("Producto", df_p['Producto'].tolist())
        up_price = st.number_input("Nuevo Precio ($)", min_value=0.0)
        if st.form_submit_button("Guardar Cambio en R2"):
            # Lógica para guardar en el archivo 'desglose' en R2
            df_desglose_r2 = api_r2_leer('desglose')
            # Actualizar o insertar
            mask = df_desglose_r2['Producto'] == up_prod
            if mask.any():
                idx = df_desglose_r2.index[mask][0]
                df_desglose_r2.at[idx, 'Precio Venta'] = up_price
            else:
                nueva_fila = pd.DataFrame([{'Producto': up_prod, 'Precio Venta': up_price}])
                df_desglose_r2 = pd.concat([df_desglose_r2, nueva_fila], ignore_index=True)
            
            if api_r2_guardar(df_desglose_r2, 'desglose'):
                st.success("Precio actualizado correctamente."); st.rerun()

# =============================================================================
# 8. BUCLE PRINCIPAL (MAIN)
# =============================================================================

def main():
    # Verificación de identidad
    if not check_auth():
        st.stop()
    
    # --- BARRA LATERAL ---
    st.sidebar.image("https://img.icons8.com/clouds/200/peach.png", width=100)
    st.sidebar.title("Menú Principal")
    
    # Filtro de fechas global
    hoy = datetime.date.today()
    inicio_mes = hoy.replace(day=1)
    
    st.sidebar.subheader("📅 Período de Análisis")
    f_ini = st.sidebar.date_input("Fecha Inicio", inicio_mes)
    f_fin = st.sidebar.date_input("Fecha Fin", hoy)
    
    st.sidebar.divider()
    
    menu = {
        "📊 Dashboard": vista_dashboard,
        "🛒 Punto de Venta": vista_ventas,
        "📦 Inventario y Recetas": vista_inventario,
        "💰 Precios y Márgenes": vista_precios
    }
    
    choice = st.sidebar.radio("Navegación", list(menu.keys()))
    
    st.sidebar.divider()
    if st.sidebar.button("🔒 Cerrar Sesión", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
        
    st.sidebar.caption(f"Conectado a: R2 Cloud Storage")
    st.sidebar.caption(f"Última sync: {datetime.datetime.now().strftime('%H:%M:%S')}")

    # --- EJECUCIÓN DE VISTA ---
    try:
        if choice == "📊 Dashboard":
            menu[choice](f_ini, f_fin)
        else:
            menu[choice]()
    except Exception as e:
        st.error(f"Se produjo un error al renderizar la vista: {e}")
        st.info("Intente recargar la página o verifique la conexión con el Worker.")

if __name__ == "__main__":
    main()

# =============================================================================
# FIN DEL CÓDIGO - SISTEMA BONBON PEACH R2
# =============================================================================
