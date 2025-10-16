import streamlit as st
import hashlib
import pandas as pd
import csv
import os
import unicodedata
import re
import datetime
from datetime import datetime as dt
import plotly.express as px
import plotly.graph_objects as go
import requests
import json

# --- CONFIGURACIÓN DE WORKER ---
WORKER_URL = "https://admin.bonbon-peach.com/api"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# CAMBIA ESTAS CONTRASEÑAS!
USERS = {
    "admin": hash_password("BonBonAdmin!"),
    "ventas": hash_password("VentasBBP2025!")
}

def check_auth():
    if st.session_state.get("authenticated"):
        return True
    
    # Login simple
    st.markdown("""
    <div style='text-align: center; padding: 100px 20px;'>
        <h1 style='color: #667eea;'>🍑 BonBon - Peach</h1>
        <p style='color: #666;'>Sistema de Gestión</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("login"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Acceder"):
            if username in USERS and hash_password(password) == USERS[username]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    
    return False

# --- FUNCIONES R2 ACTUALIZADAS ---
def cargar_csv_desde_r2(nombre_archivo):
    """Cargar CSV desde Cloudflare R2"""
    try:
        response = requests.get(f"{WORKER_URL}/{nombre_archivo}")
        if response.status_code == 200:
            data = response.json()
            if data:  # Ahora devuelve array directamente
                return pd.DataFrame(data)
            else:
                return pd.DataFrame()  # Array vacío
    except Exception as e:
        st.error(f"Error cargando {nombre_archivo}: {e}")
    
    return pd.DataFrame()

def guardar_csv_en_r2(df, nombre_archivo):
    """Guardar CSV en Cloudflare R2"""
    try:
        # Convertir DataFrame a lista de diccionarios
        if not df.empty:
            data = df.to_dict('records')
        else:
            data = []
            
        response = requests.post(
            f"{WORKER_URL}/{nombre_archivo}", 
            json=data
        )
        if response.status_code == 200:
            st.success("✅ Datos guardados correctamente")
            return True
        else:
            st.error("❌ Error guardando datos")
            return False
    except Exception as e:
        st.error(f"❌ Error guardando {nombre_archivo}: {e}")
        return False

# --- CONFIGURACIÓN ---
COMISION_BASE_PORCENTAJE = 3.5
TASA_IVA_PORCENTAJE = 16.0
COMISION_TARJETA = COMISION_BASE_PORCENTAJE * (1 + (TASA_IVA_PORCENTAJE / 100))

# --- Configuración de página ---
st.set_page_config(
    page_title="🍑 BonBon - Peach · Sistema Web",
    page_icon="🍑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Estilos CSS simplificados y seguros ---
st.markdown("""
<style>
    /* Fondo principal */
    .stApp {
          background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%) ;
    }
    
    /* Contenedor principal */
    .main .block-container {
        background-color: white;
        border-radius: 15px;
        padding: 2rem;
        margin: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    /* Headers */
    .main-header {
        font-size: 2.8rem;
        color: #667eea;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: 700;
    }
    
    .section-header {
        font-size: 1.8rem;
        color: #764ba2;
        border-bottom: 3px solid #f093fb;
        padding-bottom: 0.5rem;
        margin-bottom: 1.5rem;
        font-weight: 600;
    }
    
    /* Botones */
    .stButton button {
        background-color: #667eea;
        color: white;
        border: none;
        padding: 0.5rem 1.5rem;
        border-radius: 25px;
        font-weight: 600;
    }
    
    .stButton button:hover {
        background-color: #764ba2;
        color: white;
    }
    
    /* Sidebar */
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
    }
    
    /* Métricas cards */
    [data-testid="metric-container"] {
        background-color: #667eea;
        color: white;
        padding: 1rem;
        border-radius: 10px;
    }
    
    /* Badges básicos */
    .badge-success { background-color: #28a745; color: white; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.8rem; }
    .badge-warning { background-color: #ffc107; color: black; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.8rem; }
    .badge-danger { background-color: #dc3545; color: white; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.8rem; }
    .badge-info { background-color: #667eea; color: white; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# --- Funciones auxiliares ---
def normalizar_texto(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().strip()
    texto = ' '.join(texto.split())
    texto = str(unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8'))
    return re.sub(r'[^a-z0-9\s]', '', texto)

def clean_and_convert_float(value_str, default=0.0):
    if isinstance(value_str, (int, float)): return float(value_str)
    if not isinstance(value_str, str): return default
    cleaned = value_str.strip().replace('$', '').replace(',', '').replace('%', '')
    try: return float(cleaned)
    except (ValueError, TypeError): return default

# --- Rutas de archivos ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ruta_ingredientes = os.path.join(BASE_DIR, "IngredientesBase.csv")
ruta_recetas = os.path.join(BASE_DIR, "Recetas.csv")
ruta_desglose_precios = os.path.join(BASE_DIR, "CostoPorProducto.csv")
ruta_venta_diaria = os.path.join(BASE_DIR, "VentasDiarias.csv")
ruta_inventario = os.path.join(BASE_DIR, "Inventario.csv")

# --- Funciones de gestión de datos ---
@st.cache_data
def leer_ingredientes_base(_ruta_archivo):
    df = cargar_csv_desde_r2('ingredientes')
    if df.empty:
        return []
    # CONVERTIR DataFrame a lista de diccionarios
    return df.to_dict('records')
    
def guardar_ingredientes_base(ingredientes_data):
    df = pd.DataFrame(ingredientes_data)
    success = guardar_csv_en_r2(df, 'ingredientes')
    if success:
        st.cache_data.clear()
    return success

def leer_inventario():
    """Leer inventario desde R2"""
    df = cargar_csv_desde_r2('inventario')
    inventario = {}
    
    if not df.empty:
        for _, row in df.iterrows():
            nombre = row.get('Ingrediente', '')
            if nombre and pd.notna(nombre):
                inventario[str(nombre)] = {
                    'stock_actual': float(row.get('Stock Actual', 0.0)),
                    'min': float(row.get('Stock Mínimo', 0.0)),
                    'max': float(row.get('Stock Máximo', 0.0))
                }
    
    return inventario

def guardar_inventario(inventario_data):
    datos = []
    for nombre, info in inventario_data.items():
        if nombre and nombre.strip():
            datos.append({
                'Ingrediente': str(nombre),
                'Stock Actual': float(info.get('stock_actual', 0.0)),
                'Stock Mínimo': float(info.get('min', 0.0)),
                'Stock Máximo': float(info.get('max', 0.0))
            })
    
    df = pd.DataFrame(datos)
    return guardar_csv_en_r2(df, 'inventario')

@st.cache_data

def leer_recetas():
    recetas = {}
    ingredientes = leer_ingredientes_base(ruta_ingredientes)
    
    # Usar R2 en lugar de archivo local
    df = cargar_csv_desde_r2('recetas')
    
    if not df.empty and 'Ingrediente' in df.columns:
        productos = [col for col in df.columns if col != 'Ingrediente']
        
        for producto in productos:
            recetas[producto] = {
                'ingredientes': {},
                'costo_total': 0.0
            }
        
        for _, fila in df.iterrows():
            ingrediente_nombre = str(fila['Ingrediente']).strip()
            if not ingrediente_nombre:
                continue
            
            for producto in productos:
                if producto in fila:
                    cantidad = clean_and_convert_float(fila[producto])
                    if cantidad > 0:
                        recetas[producto]['ingredientes'][ingrediente_nombre] = cantidad
        
        # Calcular costos
        for producto, datos in recetas.items():
            costo_total = 0.0
            for ing_nombre, cantidad in datos['ingredientes'].items():
                ing_info = next((i for i in ingredientes if i['nombre'] == ing_nombre), None)
                if ing_info:
                    costo_total += ing_info['costo_receta'] * cantidad
            recetas[producto]['costo_total'] = costo_total
    
    return recetas

def leer_ventas(fecha_inicio=None, fecha_fin=None):
    """Leer ventas desde R2"""
    df = cargar_csv_desde_r2('ventas')
    if df.empty:
        return []
    
    # Convertir a formato de tus funciones existentes
    ventas = []
    for _, row in df.iterrows():
        venta = {}
        for col in df.columns:
            value = row[col]
            # Convertir números
            if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '').isdigit()):
                venta[col] = float(value)
            else:
                venta[col] = value
        ventas.append(venta)
    
    # Aplicar filtros de fecha si se proporcionan
    if fecha_inicio and fecha_fin:
        ventas_filtradas = []
        for venta in ventas:
            fecha_str = venta.get('Fecha', '')
            try:
                fecha_venta = pd.to_datetime(fecha_str, format='%d/%m/%Y').date()
                if fecha_inicio <= fecha_venta <= fecha_fin:
                    ventas_filtradas.append(venta)
            except:
                continue
        return ventas_filtradas
    
    return ventas

def guardar_ventas_csv(ventas_data):
    """Guardar ventas en R2"""
    df = pd.DataFrame(ventas_data)
    return guardar_csv_en_r2(df, 'ventas')

# --- Funciones para autocompletado ---
def filtrar_opciones(opciones, texto_busqueda):
    """Filtra opciones basado en texto de búsqueda"""
    if not texto_busqueda:
        return opciones
    texto_busqueda = texto_busqueda.lower()
    return [op for op in opciones if texto_busqueda in op.lower()]

# --- Interfaz principal ---
def main():
    # VERIFICAR AUTENTICACIÓN PRIMERO
    if not check_auth():
        st.stop()
    
    st.markdown('<div class="main-header">🍑 BonBon - Peach · Sistema Web</div>', unsafe_allow_html=True)
    
    # Sidebar para navegación
    with st.sidebar:
        st.markdown("### 🧭 Navegación")
        pagina = st.radio(
            "Selecciona una sección:",
            ["📊 Dashboard", "🧪 Ingredientes", "📝 Recetas", "💰 Precios", 
             "🛒 Ventas", "📦 Inventario", "🔄 Reposición"]
        )
        
        st.markdown("---")
        st.markdown("### 📈 Métricas Rápidas")
        ingredientes = leer_ingredientes_base(ruta_ingredientes)
        inventario = leer_inventario()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Ingredientes", len(ingredientes))
        with col2:
            alertas = sum(1 for data in inventario.values() if data.get('min', 0) > 0 and data.get('stock_actual', 0) < data['min'])
            st.metric("Alertas", alertas, delta=f"-{alertas}" if alertas > 0 else None)
    
    # Páginas
    if pagina == "📊 Dashboard":
        mostrar_dashboard()
    elif pagina == "🧪 Ingredientes":
        mostrar_ingredientes()
    elif pagina == "📝 Recetas":
        mostrar_recetas()
    elif pagina == "💰 Precios":
        mostrar_precios()
    elif pagina == "🛒 Ventas":
        mostrar_ventas()
    elif pagina == "📦 Inventario":
        mostrar_inventario()
    elif pagina == "🔄 Reposición":
        mostrar_reposicion()

def mostrar_dashboard():
    st.markdown('<div class="section-header">📊 Dashboard General</div>', unsafe_allow_html=True)
    
    # Filtros de fecha para el dashboard
    col1, col2, col3 = st.columns(3)
    with col1:
        rango = st.selectbox("Rango de tiempo:", ["Última semana", "Último mes", "Últimos 3 meses", "Personalizado"])
    
    fecha_inicio, fecha_fin = None, None
    if rango == "Personalizado":
        with col2:
            fecha_inicio = st.date_input("Fecha inicio:", datetime.date.today() - datetime.timedelta(days=30))
        with col3:
            fecha_fin = st.date_input("Fecha fin:", datetime.date.today())
    else:
        if rango == "Última semana":
            fecha_inicio = datetime.date.today() - datetime.timedelta(days=7)
        elif rango == "Último mes":
            fecha_inicio = datetime.date.today() - datetime.timedelta(days=30)
        elif rango == "Últimos 3 meses":
            fecha_inicio = datetime.date.today() - datetime.timedelta(days=90)
        fecha_fin = datetime.date.today()
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        ingredientes = leer_ingredientes_base(ruta_ingredientes)
        st.metric("Total Ingredientes", len(ingredientes))
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        inventario = leer_inventario()
        stock_total = sum(data.get('stock_actual', 0) for data in inventario.values())
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Stock Total", f"{stock_total:.0f} uds")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        recetas = leer_recetas()
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Recetas", len(recetas))
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        ventas = leer_ventas(fecha_inicio, fecha_fin)
        total_ventas = sum(clean_and_convert_float(venta.get('Total Venta Bruto', 0)) for venta in ventas)
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Ventas Período", f"${total_ventas:.2f}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Gráficas
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📈 Productos Más Vendidos")
        if ventas:
            # Agrupar ventas por producto
            ventas_por_producto = {}
            for venta in ventas:
                producto = venta.get('Producto', 'Desconocido')
                cantidad = clean_and_convert_float(venta.get('Cantidad', 0))
                if producto in ventas_por_producto:
                    ventas_por_producto[producto] += cantidad
                else:
                    ventas_por_producto[producto] = cantidad
            
            # Crear gráfico de barras
            if ventas_por_producto:
                df_ventas = pd.DataFrame({
                    'Producto': list(ventas_por_producto.keys()),
                    'Cantidad': list(ventas_por_producto.values())
                }).sort_values('Cantidad', ascending=False).head(10)
                
                fig = px.bar(df_ventas, x='Producto', y='Cantidad', 
                            title='Top 10 Productos Más Vendidos',
                            color='Cantidad', color_continuous_scale='Viridis')
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos de ventas para el período seleccionado")
        else:
            st.info("No hay datos de ventas disponibles")
    
    with col2:
        st.markdown("### 💰 Tendencia de Ganancia")
        if ventas:
            # Agrupar por fecha
            ventas_por_fecha = {}
            for venta in ventas:
                fecha_str = venta.get('Fecha', '')
                if fecha_str:
                    try:
                        fecha = pd.to_datetime(fecha_str).date()
                        ganancia = clean_and_convert_float(venta.get('Ganancia Neta', 0))
                        if fecha in ventas_por_fecha:
                            ventas_por_fecha[fecha] += ganancia
                        else:
                            ventas_por_fecha[fecha] = ganancia
                    except:
                        continue
            
            if ventas_por_fecha:
                df_ganancia = pd.DataFrame({
                    'Fecha': list(ventas_por_fecha.keys()),
                    'Ganancia': list(ventas_por_fecha.values())
                }).sort_values('Fecha')
                
                fig = px.line(df_ganancia, x='Fecha', y='Ganancia', 
                             title='Tendencia de Ganancia Diaria',
                             markers=True)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos de ganancia para el período")
        else:
            st.info("No hay datos de ventas disponibles")
    
    # Alertas de inventario
    st.markdown("### 🔔 Alertas de Inventario")
    inventario = leer_inventario()
    alertas_urgentes = []
    alertas_normales = []
    
    for nombre, data in inventario.items():
        min_val = data.get('min', 0)
        stock_actual = data.get('stock_actual', 0)
        max_val = data.get('max', 0)
        
        if min_val > 0 and stock_actual < min_val:
            alertas_urgentes.append(f"🚨 **{nombre}**: Stock bajo ({stock_actual:.1f} < {min_val:.1f})")
        elif max_val > 0 and stock_actual > max_val * 0.8:
            alertas_normales.append(f"⚠️ {nombre}: Stock alto ({stock_actual:.1f})")
    
    if alertas_urgentes:
        for alerta in alertas_urgentes:
            st.error(alerta)
    if alertas_normales:
        for alerta in alertas_normales:
            st.warning(alerta)
    if not alertas_urgentes and not alertas_normales:
        st.success("✅ Todo en orden con el inventario")

def mostrar_ingredientes():
    st.markdown('<div class="section-header">🧪 Gestión de Ingredientes</div>', unsafe_allow_html=True)
    
    ingredientes = leer_ingredientes_base(ruta_ingredientes)
    
    # Formulario para agregar/modificar ingrediente
    with st.expander("➕ Agregar/Modificar Ingrediente", expanded=True):
        col1, col2 = st.columns(2)
        
        # Selección de ingrediente existente para modificar - CON BÚSQUEDA
        with col1:
            nombres_ingredientes = [ing['nombre'] for ing in ingredientes]
            texto_busqueda = st.text_input("Buscar ingrediente para modificar:", key="buscar_ing_modificar")
            ingredientes_filtrados = filtrar_opciones(nombres_ingredientes, texto_busqueda)
            
            ingrediente_seleccionado = st.selectbox(
                "Seleccionar Ingrediente para modificar:",
                [""] + ingredientes_filtrados,
                format_func=lambda x: "Nuevo ingrediente..." if x == "" else x
            )
        
        # Precargar datos si se selecciona un ingrediente existente
        ingrediente_existente = None
        if ingrediente_seleccionado:
            ingrediente_existente = next((ing for ing in ingredientes if ing['nombre'] == ingrediente_seleccionado), None)
        
        with st.form("form_ingrediente"):
            col1, col2 = st.columns(2)
            
            with col1:
                nombre = st.text_input("Nombre del Ingrediente*", 
                                     value=ingrediente_existente['nombre'] if ingrediente_existente else "")
                proveedor = st.text_input("Proveedor", 
                                        value=ingrediente_existente['proveedor'] if ingrediente_existente else "")
                unidad_compra = st.text_input("Unidad de Compra (ej. kg)*", 
                                           value=ingrediente_existente['unidad_compra'] if ingrediente_existente else "")
            
            with col2:
                costo_compra = st.number_input("Costo de Compra ($)*", 
                                             min_value=0.0, step=0.1,
                                             value=float(ingrediente_existente['costo_compra']) if ingrediente_existente else 0.0)
                cantidad_compra = st.number_input("Cantidad por Unidad de Compra*", 
                                                min_value=0.0, step=0.1,
                                                value=float(ingrediente_existente['cantidad_compra']) if ingrediente_existente else 0.0)
                unidad_receta = st.text_input("Unidad Receta (ej. gr)*", 
                                           value=ingrediente_existente['unidad_receta'] if ingrediente_existente else "")
            
            col1, col2 = st.columns(2)
            with col1:
                if ingrediente_existente:
                    submitted = st.form_submit_button("💾 Actualizar Ingrediente")
                else:
                    submitted = st.form_submit_button("➕ Agregar Ingrediente")
            
            with col2:
                if ingrediente_existente:
                    if st.form_submit_button("🗑️ Eliminar Ingrediente", type="secondary"):
                        ingredientes.remove(ingrediente_existente)
                        guardar_ingredientes_base(ingredientes)
                        st.rerun()
            
            if submitted:
                if nombre and unidad_compra and costo_compra > 0 and cantidad_compra > 0 and unidad_receta:
                    costo_receta = costo_compra / cantidad_compra if cantidad_compra != 0 else 0.0
                    
                    if ingrediente_existente:
                        # Actualizar ingrediente existente
                        ingrediente_existente.update({
                            'nombre': nombre,
                            'proveedor': proveedor,
                            'costo_compra': costo_compra,
                            'cantidad_compra': cantidad_compra,
                            'unidad_compra': unidad_compra,
                            'unidad_receta': unidad_receta,
                            'costo_receta': costo_receta,
                            'nombre_normalizado': normalizar_texto(nombre)
                        })
                        st.success(f"✅ Ingrediente '{nombre}' actualizado correctamente")
                    else:
                        # Nuevo ingrediente
                        nuevo_ingrediente = {
                            'nombre': nombre,
                            'proveedor': proveedor,
                            'costo_compra': costo_compra,
                            'cantidad_compra': cantidad_compra,
                            'unidad_compra': unidad_compra,
                            'unidad_receta': unidad_receta,
                            'costo_receta': costo_receta,
                            'nombre_normalizado': normalizar_texto(nombre)
                        }
                        ingredientes.append(nuevo_ingrediente)
                        st.success(f"✅ Ingrediente '{nombre}' agregado correctamente")
                    
                    guardar_ingredientes_base(ingredientes)
                    st.rerun()
                else:
                    st.error("❌ Por favor completa todos los campos requeridos (*)")
    
    # Lista de ingredientes existentes
    st.markdown("### 📋 Lista de Ingredientes")
    
if ingredientes:
        datos_tabla = []
        for ing in sorted(ingredientes, key=lambda x: x['nombre']):
            datos_tabla.append({
                'Ingrediente': ing['nombre'],
                'Proveedor': ing['proveedor'],
                'Unidad Compra': ing['unidad_compra'],
                'Costo Compra': f"${ing['costo_compra']:.2f}",
                'Cant. Compra': f"{ing['cantidad_compra']:.1f}",
                'Unidad Receta': ing['unidad_receta'],
                'Costo/Receta': f"${ing['costo_receta']:.4f}"
            })
        
        df = pd.DataFrame(datos_tabla)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Estadísticas
        st.markdown("### 📈 Estadísticas")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            costo_promedio = sum(ing['costo_compra'] for ing in ingredientes) / len(ingredientes)
            st.metric("Costo Promedio", f"${costo_promedio:.2f}")
        
        with col2:
            proveedores_unicos = len(set(ing['proveedor'] for ing in ingredientes if ing['proveedor']))
            st.metric("Proveedores Únicos", proveedores_unicos)
        
        with col3:
            st.metric("Ingredientes Activos", len(ingredientes))
    else:
        st.info("📝 No hay ingredientes registrados. Agrega el primero usando el formulario arriba.")

def mostrar_recetas():
    st.markdown('<div class="section-header">📝 Gestión de Recetas</div>', unsafe_allow_html=True)
    
    ingredientes = leer_ingredientes_base(ruta_ingredientes)
    recetas = leer_recetas()
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("#### Lista de Recetas")
        nombres_recetas = list(recetas.keys())
        
        # Crear nueva receta
        with st.form("nueva_receta"):
            nueva_receta_nombre = st.text_input("Nombre de nueva receta:")
            if st.form_submit_button("➕ Crear Receta"):
                if nueva_receta_nombre and nueva_receta_nombre.strip():
                    recetas[nueva_receta_nombre.strip()] = {'ingredientes': {}, 'costo_total': 0.0}
                    guardar_recetas_csv(recetas)
                    st.success(f"✅ Receta '{nueva_receta_nombre}' creada")
                    st.cache_data.clear()  # Limpiar cache para refrescar
                    st.rerun()
        
        # Selección de receta - CON BÚSQUEDA
        if nombres_recetas:
            texto_busqueda = st.text_input("Buscar receta:", key="buscar_receta")
            recetas_filtradas = filtrar_opciones(nombres_recetas, texto_busqueda)
            receta_seleccionada = st.selectbox("Seleccionar Receta:", recetas_filtradas)
        else:
            st.info("No hay recetas creadas")
            receta_seleccionada = None
    
    with col2:
        if receta_seleccionada:
            st.markdown(f"#### 🍽️ {receta_seleccionada}")
            
            # Mostrar ingredientes actuales
            st.markdown("**Ingredientes en la receta:**")
            ingredientes_receta = recetas[receta_seleccionada]['ingredientes']
            
            if ingredientes_receta:
                datos = []
                for ing_nombre, cantidad in ingredientes_receta.items():
                    ing_info = next((i for i in ingredientes if i['nombre'] == ing_nombre), None)
                    costo_ing = ing_info['costo_receta'] * cantidad if ing_info else 0
                    datos.append({
                        'Ingrediente': ing_nombre,
                        'Cantidad': cantidad,
                        'Costo': f"${costo_ing:.2f}"
                    })
                
                df_ing = pd.DataFrame(datos)
                st.dataframe(df_ing, use_container_width=True, hide_index=True)
                
                # Botón para eliminar ingredientes
                with st.expander("🗑️ Eliminar Ingrediente"):
                    ing_a_eliminar = st.selectbox("Seleccionar ingrediente a eliminar:", 
                                                list(ingredientes_receta.keys()))
                    if st.button("Eliminar Ingrediente", type="secondary"):
                        del recetas[receta_seleccionada]['ingredientes'][ing_a_eliminar]
                        # Recalcular costo
                        costo_total = 0.0
                        for ing_nombre, cant in recetas[receta_seleccionada]['ingredientes'].items():
                            ing_info = next((i for i in ingredientes if i['nombre'] == ing_nombre), None)
                            if ing_info:
                                costo_total += ing_info['costo_receta'] * cant
                        recetas[receta_seleccionada]['costo_total'] = costo_total
                        guardar_recetas_csv(recetas)
                        st.success("✅ Ingrediente eliminado")
                        st.rerun()
            else:
                st.info("No hay ingredientes en esta receta")
            
            # Agregar/Modificar ingrediente
            st.markdown("---")
            st.markdown("**Agregar/Modificar Ingrediente:**")
            
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                # Autocompletado para ingredientes
                nombres_ing = [ing['nombre'] for ing in ingredientes]
                texto_busqueda = st.text_input("Buscar ingrediente:", key="buscar_ing_receta")
                ingredientes_filtrados = filtrar_opciones(nombres_ing, texto_busqueda)
                if ingredientes_filtrados:
                    ingrediente_seleccionado = st.selectbox("Ingrediente:", ingredientes_filtrados)
                else:
                    ingrediente_seleccionado = None
                    st.info("No hay ingredientes que coincidan")
            
            with col2:
                cantidad = st.number_input("Cantidad:", min_value=0.0, step=0.1, value=1.0)
            
            with col3:
                st.markdown("")  # Espacio vertical
                st.markdown("")
                if st.button("➕ Agregar", use_container_width=True) and ingrediente_seleccionado:
                    recetas[receta_seleccionada]['ingredientes'][ingrediente_seleccionado] = cantidad
                    # Recalcular costo
                    costo_total = 0.0
                    for ing_nombre, cant in recetas[receta_seleccionada]['ingredientes'].items():
                        ing_info = next((i for i in ingredientes if i['nombre'] == ing_nombre), None)
                        if ing_info:
                            costo_total += ing_info['costo_receta'] * cant
                    recetas[receta_seleccionada]['costo_total'] = costo_total
                    
                    guardar_recetas_csv(recetas)
                    st.success("✅ Ingrediente agregado")
                    st.rerun()
            
            # Mostrar costo total
            costo_total = recetas[receta_seleccionada]['costo_total']
            st.markdown(f"**Costo total de la receta: ${costo_total:.2f}**")

def guardar_recetas_csv(recetas_data):
    try:
        # Recopilar todos los ingredientes únicos
        todos_ingredientes = set()
        for receta in recetas_data.values():
            todos_ingredientes.update(receta['ingredientes'].keys())
        
        todos_ingredientes = sorted(list(todos_ingredientes))
        nombres_recetas = sorted(recetas_data.keys())
        
        # Crear DataFrame
        data = []
        for ingrediente in todos_ingredientes:
            fila = {'Ingrediente': ingrediente}
            for receta in nombres_recetas:
                cantidad = recetas_data[receta]['ingredientes'].get(ingrediente, '')
                fila[receta] = cantidad
            data.append(fila)
        
        df = pd.DataFrame(data)
        # CAMBIAR: Usar R2 en lugar de archivo local
        guardar_csv_en_r2(df, 'recetas')
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error guardando recetas: {e}")

def mostrar_precios():
    st.markdown('<div class="section-header">💰 Desglose de Precios</div>', unsafe_allow_html=True)
    
    recetas = leer_recetas()
    
    if not recetas:
        st.info("📝 No hay recetas creadas. Ve a la pestaña 'Recetas' para crear algunas.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Seleccionar Producto")
        
        # Autocompletado para productos
        nombres_productos = list(recetas.keys())
        texto_busqueda = st.text_input("Buscar producto:", key="buscar_producto_precios")
        productos_filtrados = filtrar_opciones(nombres_productos, texto_busqueda)
        
        if productos_filtrados:
            producto_seleccionado = st.selectbox("Producto:", productos_filtrados)
        else:
            producto_seleccionado = None
            st.info("No hay productos que coincidan")
    
    with col2:
        if producto_seleccionado:
            st.markdown("#### Información del Producto")
            costo_produccion = recetas[producto_seleccionado]['costo_total']
            
            st.metric("Costo de Producción", f"${costo_produccion:.2f}")
            
            # Modificar precio de venta
            with st.form("modificar_precio"):
                nuevo_precio = st.number_input("Precio de Venta ($):", 
                                             min_value=0.0, step=0.1, 
                                             value=max(costo_produccion * 1.5, 10.0))
                
                if st.form_submit_button("💾 Actualizar Precio"):
                    margen = nuevo_precio - costo_produccion
                    margen_porcentual = (margen / nuevo_precio) * 100 if nuevo_precio > 0 else 0
                    
                    # Guardar en desglose de precios
                    guardar_precio_producto(producto_seleccionado, nuevo_precio, costo_produccion, margen, margen_porcentual)
                    st.success(f"✅ Precio actualizado para '{producto_seleccionado}'")
    
    # Tabla de todos los productos
    st.markdown("### 📊 Resumen de Precios")
    datos_tabla = []
    for producto, datos in recetas.items():
        info_precio = leer_precio_producto(producto)
        precio_venta = info_precio.get('precio_venta', 0)
        margen = precio_venta - datos['costo_total']
        margen_porcentual = (margen / precio_venta) * 100 if precio_venta > 0 else 0
        
        datos_tabla.append({
            'Producto': producto,
            'Costo Producción': f"${datos['costo_total']:.2f}",
            'Precio Venta': f"${precio_venta:.2f}",
            'Margen $': f"${margen:.2f}",
            'Margen %': f"{margen_porcentual:.1f}%"
        })
    
    if datos_tabla:
        df = pd.DataFrame(datos_tabla)
        st.dataframe(df, use_container_width=True, hide_index=True)

def leer_precio_producto(producto):
    """Leer precio de un producto específico"""
    if os.path.exists(ruta_desglose_precios):
        try:
            df = pd.read_csv(ruta_desglose_precios, encoding='latin-1')
            if 'Producto' in df.columns:
                fila = df[df['Producto'] == producto]
                if not fila.empty:
                    return {
                        'precio_venta': clean_and_convert_float(fila.iloc[0].get('Precio Venta', 0)),
                        'margen_bruto': clean_and_convert_float(fila.iloc[0].get('Margen Bruto', 0)),
                        'margen_porcentual': clean_and_convert_float(fila.iloc[0].get('Margen Bruto (%)', 0))
                    }
        except Exception as e:
            st.error(f"Error leyendo precios: {e}")
    return {'precio_venta': 0, 'margen_bruto': 0, 'margen_porcentual': 0}

def guardar_precio_producto(producto, precio_venta, costo_produccion, margen, margen_porcentual):
    """Guardar precio de un producto"""
    try:
        datos = []
        if os.path.exists(ruta_desglose_precios):
            try:
                df_existente = pd.read_csv(ruta_desglose_precios, encoding='latin-1')
                datos = df_existente.to_dict('records')
            except:
                datos = []
        
        # Actualizar o agregar producto
        producto_encontrado = False
        for item in datos:
            if item.get('Producto') == producto:
                item.update({
                    'Precio Venta': f"{precio_venta:.2f}",
                    'Margen Bruto': f"{margen:.2f}",
                    'Margen Bruto (%)': f"{margen_porcentual:.2f}"
                })
                producto_encontrado = True
                break
        
        if not producto_encontrado:
            datos.append({
                'Producto': producto,
                'Precio Venta': f"{precio_venta:.2f}",
                'Margen Bruto': f"{margen:.2f}",
                'Margen Bruto (%)': f"{margen_porcentual:.2f}"
            })
        
        df = pd.DataFrame(datos)
        df.to_csv(ruta_desglose_precios, index=False, encoding='latin-1')
    except Exception as e:
        st.error(f"Error guardando precio: {e}")

def mostrar_ventas():
    st.markdown('<div class="section-header">🛒 Gestión de Ventas</div>', unsafe_allow_html=True)
    
    # Botones de acceso rápido para fechas
    st.markdown("### 📅 Selección Rápida de Fechas")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📅 Hoy", use_container_width=True):
            st.session_state.fecha_inicio = datetime.date.today()
            st.session_state.fecha_fin = datetime.date.today()
    
    with col2:
        if st.button("📅 Ayer", use_container_width=True):
            st.session_state.fecha_inicio = datetime.date.today() - datetime.timedelta(days=1)
            st.session_state.fecha_fin = datetime.date.today() - datetime.timedelta(days=1)
    
    with col3:
        if st.button("📅 Última Semana", use_container_width=True):
            st.session_state.fecha_inicio = datetime.date.today() - datetime.timedelta(days=7)
            st.session_state.fecha_fin = datetime.date.today()
    
    with col4:
        if st.button("📅 Último Mes", use_container_width=True):
            st.session_state.fecha_inicio = datetime.date.today() - datetime.timedelta(days=30)
            st.session_state.fecha_fin = datetime.date.today()
    
    # Filtros de fecha manuales
    st.markdown("### 🔍 Filtros Avanzados")
    col1, col2, col3 = st.columns([2, 2, 1])
    
    # Inicializar fechas en session_state si no existen
    if 'fecha_inicio' not in st.session_state:
        st.session_state.fecha_inicio = datetime.date.today() - datetime.timedelta(days=30)
    if 'fecha_fin' not in st.session_state:
        st.session_state.fecha_fin = datetime.date.today()
    
    with col1:
        fecha_inicio = st.date_input("Fecha inicial:", st.session_state.fecha_inicio)
        st.session_state.fecha_inicio = fecha_inicio
    
    with col2:
        fecha_fin = st.date_input("Fecha final:", st.session_state.fecha_fin)
        st.session_state.fecha_fin = fecha_fin
    
    with col3:
        st.markdown("")  # Espacio vertical
        st.markdown("")
        if st.button("🔄 Actualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # Leer ventas filtradas
    ventas = leer_ventas(fecha_inicio, fecha_fin)
    
    # Métricas de ventas en tarjetas
    st.markdown("### 📊 Métricas de Ventas")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_ventas = sum(clean_and_convert_float(venta.get('Total Venta Bruto', 0)) for venta in ventas)
        st.metric("💰 Total Ventas", f"${total_ventas:,.2f}")
    
    with col2:
        ganancia_neta = sum(clean_and_convert_float(venta.get('Ganancia Neta', 0)) for venta in ventas)
        st.metric("💸 Ganancia Neta", f"${ganancia_neta:,.2f}")
    
    with col3:
        total_ventas_count = len(ventas)
        st.metric("📋 Transacciones", f"{total_ventas_count}")
    
    with col4:
        avg_ganancia = ganancia_neta / total_ventas_count if total_ventas_count > 0 else 0
        st.metric("📈 Ganancia Promedio", f"${avg_ganancia:.2f}")
    
    # Sistema de ventas múltiples
    st.markdown("### 🛍️ Sistema de Ventas Múltiples")
    
    with st.expander("➕ Agregar Venta con Múltiples Productos", expanded=True):
        # Inicializar lista de productos en la venta actual
        if 'productos_venta_actual' not in st.session_state:
            st.session_state.productos_venta_actual = []
        
        col1, col2 = st.columns(2)
        
        with col1:
            fecha_venta = st.date_input("Fecha de venta:", datetime.date.today(), key="fecha_venta_multiple")
            productos_disponibles = list(leer_recetas().keys())
            
            # Autocompletado para productos
            texto_busqueda_producto = st.text_input("🔍 Buscar producto:", key="buscar_producto_venta_multiple")
            productos_filtrados = filtrar_opciones(productos_disponibles, texto_busqueda_producto)
            producto_seleccionado = st.selectbox("Producto:", productos_filtrados, key="select_producto_multiple")
            
            if producto_seleccionado:
                precios = leer_precio_producto(producto_seleccionado)
                precio_venta = precios.get('precio_venta', 0)
                st.metric("Precio Unitario", f"${precio_venta:.2f}")
        
        with col2:
            cantidad = st.number_input("Cantidad:", min_value=1, value=1, step=1, key="cantidad_multiple")
            descuento_porc = st.number_input("Descuento (%):", min_value=0.0, max_value=100.0, value=0.0, step=1.0, key="descuento_multiple")
            forma_pago = st.radio("Forma de Pago:", ["Efectivo", "Tarjeta"], key="pago_multiple")
            
            col_add, col_clear = st.columns(2)
            with col_add:
                if st.button("➕ Agregar Producto", use_container_width=True):
                    if producto_seleccionado and cantidad > 0:
                        # Agregar producto a la venta actual
                        producto_venta = {
                            'producto': producto_seleccionado,
                            'cantidad': cantidad,
                            'descuento_porc': descuento_porc,
                            'precio_unitario': precio_venta,
                            'forma_pago': forma_pago
                        }
                        st.session_state.productos_venta_actual.append(producto_venta)
                        st.success(f"✅ {cantidad} x {producto_seleccionado} agregado a la venta")
                        st.rerun()
            
            with col_clear:
                if st.button("🗑️ Limpiar Lista", use_container_width=True):
                    st.session_state.productos_venta_actual = []
                    st.rerun()
        
        # Mostrar productos en la venta actual
        if st.session_state.productos_venta_actual:
            st.markdown("#### 🛒 Productos en la Venta Actual")
            
            # Calcular totales
            total_venta_actual = 0
            total_ganancia_actual = 0
            
            for i, producto_venta in enumerate(st.session_state.productos_venta_actual):
                col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
                
                with col1:
                    st.write(f"**{producto_venta['producto']}**")
                
                with col2:
                    st.write(f"Cantidad: {producto_venta['cantidad']}")
                
                with col3:
                    subtotal = producto_venta['precio_unitario'] * producto_venta['cantidad']
                    descuento_monto = subtotal * (producto_venta['descuento_porc'] / 100)
                    total_producto = subtotal - descuento_monto
                    st.write(f"Total: ${total_producto:.2f}")
                
                with col4:
                    st.write(f"Pago: {producto_venta['forma_pago']}")
                
                with col5:
                    if st.button("❌", key=f"eliminar_{i}"):
                        st.session_state.productos_venta_actual.pop(i)
                        st.rerun()
                
                total_venta_actual += total_producto
                # Calcular ganancia aproximada
                recetas = leer_recetas()
                if producto_venta['producto'] in recetas:
                    costo_producto = recetas[producto_venta['producto']]['costo_total'] * producto_venta['cantidad']
                    ganancia_producto = total_producto - costo_producto
                    total_ganancia_actual += ganancia_producto
            
            # Mostrar totales de la venta actual
            st.markdown(f"**Total Venta Actual: ${total_venta_actual:.2f}** | **Ganancia Estimada: ${total_ganancia_actual:.2f}**")
            
            # Botón para registrar toda la venta
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Registrar Venta Completa", use_container_width=True, type="primary"):
                    if st.session_state.productos_venta_actual:
                        for producto_venta in st.session_state.productos_venta_actual:
                            registrar_venta_individual(
                                fecha_venta, 
                                producto_venta['producto'], 
                                producto_venta['cantidad'], 
                                producto_venta['descuento_porc'], 
                                producto_venta['forma_pago']
                            )
                        st.success(f"✅ Venta registrada con {len(st.session_state.productos_venta_actual)} productos")
                        st.session_state.productos_venta_actual = []
                        st.rerun()
    
    # Venta individual rápida (para casos simples)
    with st.expander("⚡ Venta Rápida (Un Producto)", expanded=False):
        with st.form("form_venta_rapida"):
            col1, col2 = st.columns(2)
            
            with col1:
                fecha_rapida = st.date_input("Fecha:", datetime.date.today(), key="fecha_rapida")
                producto_rapido = st.selectbox("Producto:", productos_disponibles, key="producto_rapido")
                
                if producto_rapido:
                    precios_rapido = leer_precio_producto(producto_rapido)
                    precio_rapido = precios_rapido.get('precio_venta', 0)
                    st.metric("Precio", f"${precio_rapido:.2f}")
            
            with col2:
                cantidad_rapida = st.number_input("Cantidad:", min_value=1, value=1, step=1, key="cantidad_rapida")
                descuento_rapido = st.number_input("Descuento %:", min_value=0.0, max_value=100.0, value=0.0, step=1.0, key="descuento_rapido")
                pago_rapido = st.radio("Pago:", ["Efectivo", "Tarjeta"], key="pago_rapido", horizontal=True)
            
            if st.form_submit_button("⚡ Registrar Venta Rápida"):
                if producto_rapido and cantidad_rapida > 0:
                    registrar_venta_individual(
                        fecha_rapida, 
                        producto_rapido, 
                        cantidad_rapida, 
                        descuento_rapido, 
                        pago_rapido
                    )
                    st.success("✅ Venta rápida registrada")
                    st.rerun()
    
    # Tabla de ventas
    st.markdown("### 📋 Historial de Ventas")
    
    if ventas:
        # Opciones de visualización
        col1, col2 = st.columns([3, 1])
        with col2:
            mostrar_detalles = st.checkbox("Mostrar detalles completos", value=True)
        
        datos_tabla = []
        for venta in reversed(ventas):  # Mostrar las más recientes primero
            fecha = venta.get('Fecha', '')
            producto = venta.get('Producto', '')
            cantidad = venta.get('Cantidad', '')
            precio_unitario = clean_and_convert_float(venta.get('Precio Unitario', 0))
            total_bruto = clean_and_convert_float(venta.get('Total Venta Bruto', 0))
            descuento_porc = clean_and_convert_float(venta.get('Descuento (%)', 0))
            ganancia_neta = clean_and_convert_float(venta.get('Ganancia Neta', 0))
            forma_pago = venta.get('Forma Pago', '')
            
            if mostrar_detalles:
                datos_tabla.append({
                    'Fecha': fecha,
                    'Producto': producto,
                    'Cantidad': cantidad,
                    'Precio Unit.': f"${precio_unitario:.2f}",
                    'Total Bruto': f"${total_bruto:.2f}",
                    'Desc. %': f"{descuento_porc:.1f}%",
                    'Gan. Neta': f"${ganancia_neta:.2f}",
                    'Pago': forma_pago
                })
            else:
                datos_tabla.append({
                    'Fecha': fecha,
                    'Producto': producto,
                    'Cantidad': cantidad,
                    'Total': f"${total_bruto:.2f}",
                    'Ganancia': f"${ganancia_neta:.2f}",
                    'Pago': forma_pago
                })
        
        df = pd.DataFrame(datos_tabla)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Botones de exportación
        col1, col2 = st.columns(2)
        with col1:
            csv = df.to_csv(index=False, encoding='latin-1')
            st.download_button(
                label="📥 Exportar a CSV",
                data=csv,
                file_name=f"ventas_{fecha_inicio}_{fecha_fin}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # Resumen ejecutivo
            st.info(f"""
            **Resumen del Período:**
            - 📅 {fecha_inicio} a {fecha_fin}
            - 💰 ${total_ventas:,.2f} en ventas
            - 💸 ${ganancia_neta:,.2f} de ganancia neta
            - 📋 {total_ventas_count} transacciones
            """)
    else:
        st.info("📝 No hay ventas registradas en el período seleccionado")

def registrar_venta_individual(fecha, producto, cantidad, descuento_porc, forma_pago):
    """Registrar una venta individual en el sistema"""
    try:
        # Obtener datos del producto
        recetas = leer_recetas()
        precios = leer_precio_producto(producto)
        
        if producto not in recetas:
            st.error(f"❌ Producto '{producto}' no encontrado")
            return
        
        precio_venta = precios.get('precio_venta', 0)
        costo_produccion = recetas[producto]['costo_total']
        
        # Cálculos
        total_bruto = precio_venta * cantidad
        descuento_monto = total_bruto * (descuento_porc / 100)
        total_despues_descuento = total_bruto - descuento_monto
        
        # Comisión por tarjeta
        comision_monto = 0.0
        if forma_pago == "Tarjeta":
            comision_monto = total_despues_descuento * (COMISION_TARJETA / 100)
        
        total_neto = total_despues_descuento - comision_monto
        costo_total = costo_produccion * cantidad
        ganancia_bruta = total_despues_descuento - costo_total
        ganancia_neta = total_neto - costo_total
        
        # Crear registro de venta
        venta_nueva = {
            'Fecha': fecha.strftime('%d/%m/%Y'),
            'Producto': producto,
            'Cantidad': cantidad,
            'Precio Unitario': f"{precio_venta:.2f}",
            'Total Venta Bruto': f"{total_bruto:.2f}",
            'Descuento (%)': f"{descuento_porc:.2f}",
            'Descuento ($)': f"{descuento_monto:.2f}",
            'Costo Total': f"{costo_total:.2f}",
            'Ganancia Bruta': f"{ganancia_bruta:.2f}",
            'Comision ($)': f"{comision_monto:.2f}",
            'Ganancia Neta': f"{ganancia_neta:.2f}",
            'Forma Pago': forma_pago
        }
        
        # Guardar venta
        ventas_existentes = leer_ventas()
        ventas_existentes.append(venta_nueva)
        guardar_ventas_csv(ventas_existentes)
        
        # Deducir inventario
        deducir_inventario_venta(producto, cantidad)
        
    except Exception as e:
        st.error(f"❌ Error registrando venta: {e}")

def deducir_inventario_venta(producto, cantidad):
    """Deducir inventario por venta"""
    try:
        recetas = leer_recetas()
        inventario = leer_inventario()
        
        if producto in recetas:
            for ingrediente, cantidad_receta in recetas[producto]['ingredientes'].items():
                if ingrediente in inventario:
                    inventario[ingrediente]['stock_actual'] -= cantidad_receta * cantidad
                    if inventario[ingrediente]['stock_actual'] < 0:
                        inventario[ingrediente]['stock_actual'] = 0.0
        
        guardar_inventario(inventario)
        
    except Exception as e:
        st.error(f"❌ Error deduciendo inventario: {e}")

def mostrar_inventario():
    st.markdown('<div class="section-header">📦 Gestión de Inventario</div>', unsafe_allow_html=True)
    
    inventario = leer_inventario()
    ingredientes = leer_ingredientes_base(ruta_ingredientes)
    
    # Agregar ingredientes que no están en inventario
    for ing in ingredientes:
        if ing['nombre'] not in inventario:
            inventario[ing['nombre']] = {'stock_actual': 0.0, 'min': 0.0, 'max': 0.0}
    
    # Métricas de inventario
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_ingredientes = len(inventario)
        st.metric("Total Ingredientes", total_ingredientes)
    
    with col2:
        stock_total = sum(data.get('stock_actual', 0) for data in inventario.values())
        st.metric("Stock Total", f"{stock_total:.1f} uds")
    
    with col3:
        alertas_urgentes = sum(1 for data in inventario.values() if data.get('min', 0) > 0 and data.get('stock_actual', 0) < data['min'])
        st.metric("Alertas Urgentes", alertas_urgentes, delta=f"-{alertas_urgentes}" if alertas_urgentes > 0 else None)
    
    with col4:
        ingredientes_sin_umbral = sum(1 for data in inventario.values() if data.get('max', 0) == 0)
        st.metric("Sin Umbrales", ingredientes_sin_umbral)
    
    # Gestión de inventario
    col1, col2 = st.columns(2)
    
    with col1:
        with st.expander("📥 Registrar Compra/Entrada", expanded=False):
            with st.form("form_compra"):
                # Autocompletado para ingredientes
                nombres_ingredientes = list(inventario.keys())
                texto_busqueda = st.text_input("Buscar ingrediente:", key="buscar_ing_inventario")
                ingredientes_filtrados = filtrar_opciones(nombres_ingredientes, texto_busqueda)
                
                ingrediente_compra = st.selectbox("Ingrediente:", ingredientes_filtrados)
                cantidad_compra = st.number_input("Cantidad a agregar:", min_value=0.0, step=0.1, value=1.0)
                
                if st.form_submit_button("📥 Registrar Entrada"):
                    if ingrediente_compra:
                        inventario[ingrediente_compra]['stock_actual'] += cantidad_compra
                        guardar_inventario(inventario)
                        st.success(f"✅ Se agregaron {cantidad_compra:.2f} unidades de '{ingrediente_compra}'")
                        st.rerun()
    
    with col2:
        with st.expander("⚙️ Establecer Mínimos/Máximos", expanded=False):
            with st.form("form_umbrales"):
                # Autocompletado para ingredientes
                texto_busqueda_umbral = st.text_input("Buscar ingrediente:", key="buscar_ing_umbral")
                ingredientes_filtrados_umbral = filtrar_opciones(nombres_ingredientes, texto_busqueda_umbral)
                
                ingrediente_umbral = st.selectbox("Ingrediente para configurar:", ingredientes_filtrados_umbral)
                
                if ingrediente_umbral:
                    stock_actual = inventario[ingrediente_umbral].get('stock_actual', 0)
                    min_actual = inventario[ingrediente_umbral].get('min', 0)
                    max_actual = inventario[ingrediente_umbral].get('max', 0)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        nuevo_min = st.number_input("Stock Mínimo:", min_value=0.0, step=0.1, value=float(min_actual))
                    with col2:
                        nuevo_max = st.number_input("Stock Máximo:", min_value=0.0, step=0.1, value=float(max_actual))
                
                if st.form_submit_button("💾 Guardar Umbrales"):
                    if ingrediente_umbral and nuevo_max >= nuevo_min:
                        inventario[ingrediente_umbral]['min'] = nuevo_min
                        inventario[ingrediente_umbral]['max'] = nuevo_max
                        guardar_inventario(inventario)
                        st.success(f"✅ Umbrales actualizados para '{ingrediente_umbral}'")
                        st.rerun()
                    else:
                        st.error("❌ El máximo debe ser mayor o igual al mínimo")
    
    # Tabla de inventario - VERSIÓN SIMPLIFICADA Y FUNCIONAL
    st.markdown("### 📊 Estado del Inventario")
    
    if inventario:
        datos_tabla = []
        colores_fondo = []  # Lista separada para colores
        
        for nombre, data in sorted(inventario.items()):
            stock_actual = data.get('stock_actual', 0)
            stock_min = data.get('min', 0)
            stock_max = data.get('max', 0)
            
            # Determinar estado y color
            if stock_max > 0:
                if stock_actual < stock_min:
                    estado = "🚨 REPONER URGENTE"
                    color_fondo = '#FFDDDD'  # Rojo claro
                    unidades_reponer = stock_max - stock_actual
                elif stock_actual < (stock_min + stock_max) / 2:
                    estado = "⚠️ Stock Bajo"
                    color_fondo = '#FFFFAA'  # Amarillo claro
                    unidades_reponer = 0
                else:
                    estado = "🟢 OK"
                    color_fondo = '#DDFFDD'  # Verde claro
                    unidades_reponer = 0
            elif stock_actual > 0:
                estado = "🔵 Con Stock"
                color_fondo = '#DDEEFF'  # Azul claro
                unidades_reponer = 0
            else:
                estado = "⚪ Inactivo"
                color_fondo = '#F0F0F0'  # Gris claro
                unidades_reponer = 0
            
            datos_tabla.append({
                'Ingrediente': nombre,
                'Stock Actual': f"{stock_actual:.2f}",
                'Mínimo': f"{stock_min:.2f}",
                'Máximo': f"{stock_max:.2f}",
                'A Reponer': f"{unidades_reponer:.2f}",
                'Estado': estado
            })
            
            colores_fondo.append(color_fondo)
        
        # Crear DataFrame
        df = pd.DataFrame(datos_tabla)
        
        # Función para aplicar colores - VERSIÓN CORREGIDA
        def aplicar_estilos(dataframe, colores):
            styles = []
            for i in range(len(dataframe)):
                style = [f'background-color: {colores[i]}' for _ in range(len(dataframe.columns))]
                styles.append(style)
            return styles
        
        # Aplicar estilos
        estilos = aplicar_estilos(df, colores_fondo)
        styled_df = df.style.apply(lambda x: estilos[df.index.get_loc(x.name)], axis=1)
        
        # Mostrar DataFrame con estilos
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # Resumen de alertas
        st.markdown("### 🔔 Resumen de Alertas")
        alertas_urgentes_lista = []
        alertas_bajas_lista = []
        
        for nombre, data in inventario.items():
            min_val = data.get('min', 0)
            stock_actual = data.get('stock_actual', 0)
            max_val = data.get('max', 0)
            
            if min_val > 0 and stock_actual < min_val:
                alertas_urgentes_lista.append(f"🚨 **{nombre}**: {stock_actual:.1f} < {min_val:.1f}")
            elif max_val > 0 and stock_actual > max_val * 0.8:
                alertas_bajas_lista.append(f"⚠️ {nombre}: Stock alto ({stock_actual:.1f})")
        
        if alertas_urgentes_lista:
            st.error("#### Alertas Urgentes - REPONER INMEDIATAMENTE")
            for alerta in alertas_urgentes_lista:
                st.error(alerta)
        
        if alertas_bajas_lista:
            st.warning("#### Alertas de Stock Alto")
            for alerta in alertas_bajas_lista:
                st.warning(alerta)
        
        if not alertas_urgentes_lista and not alertas_bajas_lista:
            st.success("✅ Todo en orden con el inventario")
            
    else:
        st.info("📦 No hay datos de inventario disponibles")

def mostrar_reposicion():
    st.markdown('<div class="section-header">🔄 Reposición Sugerida</div>', unsafe_allow_html=True)
    
    # Filtros de fecha (actualización automática)
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("Fecha inicial:", datetime.date.today() - datetime.timedelta(days=30))
    with col2:
        fecha_fin = st.date_input("Fecha final:", datetime.date.today())
    
    # Calcular reposición automáticamente
    ingredientes_necesarios = calcular_reposicion_sugerida(fecha_inicio, fecha_fin)
    
    if ingredientes_necesarios:
        # Métricas de reposición
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_ingredientes = len(ingredientes_necesarios)
            st.metric("Ingredientes a Reponer", total_ingredientes)
        
        with col2:
            inversion_total = sum(item['costo_reposicion'] for item in ingredientes_necesarios)
            st.metric("Inversión Total", f"${inversion_total:.2f}")
        
        with col3:
            ingredientes_urgentes = sum(1 for item in ingredientes_necesarios if item['porcentaje_compra'] > 80)
            st.metric("Compra Urgente", ingredientes_urgentes)
        
        # Tabla de reposición sugerida
        st.markdown("### 📋 Reposición Sugerida")
        
        datos_tabla = []
        for item in ingredientes_necesarios:
            datos_tabla.append({
                'Ingrediente': item['ingrediente'],
                'Cantidad Necesaria': f"{item['cantidad_necesaria']:.2f}",
                'Unidad': item['unidad'],
                'Costo Compra': f"${item['costo_compra']:.2f}",
                '% Compra Utilizado': f"{item['porcentaje_compra']:.1f}%",
                'Proveedor': item['proveedor'],
                'Costo Reposición': f"${item['costo_reposicion']:.2f}"
            })
        
        df = pd.DataFrame(datos_tabla)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Gráfica de inversión por ingrediente
        st.markdown("### 📊 Distribución de Inversión")
        
        df_grafica = pd.DataFrame({
            'Ingrediente': [item['ingrediente'] for item in ingredientes_necesarios],
            'Inversión': [item['costo_reposicion'] for item in ingredientes_necesarios]
        }).sort_values('Inversión', ascending=False).head(10)
        
        fig = px.pie(df_grafica, values='Inversión', names='Ingrediente', 
                    title='Top 10 - Distribución de Inversión en Reposición')
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.info("📊 No se encontraron ingredientes para reponer en el período seleccionado")

def calcular_reposicion_sugerida(fecha_inicio, fecha_fin):
    """Calcular ingredientes necesarios para reposición basado en ventas"""
    ingredientes_necesarios = []
    
    try:
        # Leer ventas del período
        ventas = leer_ventas(fecha_inicio, fecha_fin)
        recetas = leer_recetas()
        ingredientes_base = leer_ingredientes_base(ruta_ingredientes)
        
        # Calcular ingredientes utilizados
        ingredientes_utilizados = {}
        for venta in ventas:
            producto = venta.get('Producto', '')
            cantidad = clean_and_convert_float(venta.get('Cantidad', 0))
            
            if producto in recetas:
                for ingrediente, cantidad_receta in recetas[producto]['ingredientes'].items():
                    if ingrediente in ingredientes_utilizados:
                        ingredientes_utilizados[ingrediente] += cantidad_receta * cantidad
                    else:
                        ingredientes_utilizados[ingrediente] = cantidad_receta * cantidad
        
        # Calcular costos y porcentajes
        inversion_total = 0.0
        for ingrediente, cantidad_necesaria in sorted(ingredientes_utilizados.items()):
            ingrediente_info = next((i for i in ingredientes_base if i['nombre'] == ingrediente), None)
            
            if ingrediente_info:
                # Calcular porcentaje de compra utilizado
                cantidad_compra = ingrediente_info['cantidad_compra']
                if cantidad_compra > 0:
                    porcentaje_compra = (cantidad_necesaria / cantidad_compra) * 100
                else:
                    porcentaje_compra = 0
                
                # Calcular costo de reposición
                costo_reposicion = cantidad_necesaria * ingrediente_info['costo_receta']
                inversion_total += costo_reposicion
                
                ingredientes_necesarios.append({
                    'ingrediente': ingrediente,
                    'cantidad_necesaria': cantidad_necesaria,
                    'unidad': ingrediente_info['unidad_receta'],
                    'costo_compra': ingrediente_info['costo_compra'],
                    'porcentaje_compra': porcentaje_compra,
                    'proveedor': ingrediente_info['proveedor'],
                    'costo_reposicion': costo_reposicion
                })
        
        return ingredientes_necesarios
        
    except Exception as e:
        st.error(f"❌ Error calculando reposición: {e}")
        return []

if __name__ == "__main__":
    main()
