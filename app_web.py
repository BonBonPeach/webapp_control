import streamlit as st
import pandas as pd
import requests
import os
import unicodedata
import re
import datetime
import plotly.express as px
import plotly.graph_objects as go
from collections import defaultdict

# --- CONFIGURACIÓN DE CLOUDFLARE R2 ---
# REEMPLAZA ESTA URL CON LA DE TU WORKER REAL
WORKER_URL = "https://admin.bonbon-peach.com/api"

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="BonBon - Peach · Sistema Cloud",
    page_icon="🍑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONSTANTES DE NEGOCIO ---
COMISION_BASE_PORCENTAJE = 3.5
TASA_IVA_PORCENTAJE = 16.0
COMISION_TARJETA = COMISION_BASE_PORCENTAJE * (1 + (TASA_IVA_PORCENTAJE / 100))

# --- FUNCIONES NÚCLEO R2 (REEMPLAZAN DISCO LOCAL) ---

def cargar_csv_desde_r2(nombre_archivo):
    """Carga datos desde el Worker de R2 y los convierte en DataFrame."""
    try:
        response = requests.get(f"{WORKER_URL}/{nombre_archivo}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.error(f"Error de conexión con R2 ({nombre_archivo}): {e}")
    return pd.DataFrame()

def guardar_csv_en_r2(df, nombre_archivo):
    """Envía el DataFrame al Worker de R2 para persistencia."""
    try:
        data = df.to_dict('records') if not df.empty else []
        response = requests.post(f"{WORKER_URL}/{nombre_archivo}", json=data, timeout=10)
        if response.status_code == 200:
            st.cache_data.clear() # Limpiar caché para actualizar vistas
            return True
    except Exception as e:
        st.error(f"Error al guardar en R2 ({nombre_archivo}): {e}")
    return False

# --- GESTIÓN DE DATOS CON CACHÉ ---

@st.cache_data
def leer_ingredientes():
    df = cargar_csv_desde_r2('ingredientes')
    if df.empty:
        return pd.DataFrame(columns=['Ingrediente', 'Proveedor', 'Unidad de Compra', 'Costo de Compra', 'Cantidad por Unidad de Compra', 'Unidad Receta', 'Costo por Unidad Receta'])
    return df

@st.cache_data
def leer_recetas():
    return cargar_csv_desde_r2('recetas')

@st.cache_data
def leer_desglose():
    return cargar_csv_desde_r2('desglose')

@st.cache_data
def leer_ventas():
    df = cargar_csv_desde_r2('ventas')
    if not df.empty and 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    return df

@st.cache_data
def leer_inventario_df():
    df = cargar_csv_desde_r2('inventario')
    if df.empty:
        return pd.DataFrame(columns=['Ingrediente', 'Stock Actual', 'Stock Mínimo', 'Stock Máximo'])
    return df

# --- HELPERS LÓGICOS ---

def normalizar_texto(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().strip()
    texto = str(unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8'))
    return re.sub(r'[^a-z0-9\s]', '', texto)

def check_auth():
    """Lógica de autenticación simple"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        with st.form("login"):
            password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                if password == "BonBon2024": # Cambia tu contraseña aquí
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrecto")
        return False
    return True

# --- SECCIONES DE LA INTERFAZ ---

def mostrar_dashboard(f_inicio, f_fin):
    st.title("📊 Dashboard de Negocio")
    df_v = leer_ventas()
    
    if df_v.empty:
        st.info("No hay ventas registradas en el rango seleccionado.")
        return

    # Filtro por fecha
    mask = (df_v['Fecha'].dt.date >= f_inicio) & (df_v['Fecha'].dt.date <= f_fin)
    df_periodo = df_v.loc[mask]

    if df_periodo.empty:
        st.warning("No hay datos para estas fechas.")
        return

    c1, c2, c3, c4 = st.columns(4)
    total_neto = df_periodo['Total Neto'].sum()
    ganancia_neta = df_periodo['Ganancia'].sum()
    c1.metric("Ventas Netas", f"${total_neto:,.2f}")
    c2.metric("Ganancia Real", f"${ganancia_neta:,.2f}")
    c3.metric("Ticket Promedio", f"${total_neto/len(df_periodo):,.2f}")
    c4.metric("N° Ventas", len(df_periodo))

    col_izq, col_der = st.columns(2)
    with col_izq:
        fig_prod = px.bar(df_periodo.groupby('Producto')['Cantidad'].sum().reset_index(), 
                          x='Producto', y='Cantidad', title="Productos más vendidos")
        st.plotly_chart(fig_prod, use_container_width=True)
    
    with col_der:
        df_diario = df_periodo.groupby(df_periodo['Fecha'].dt.date)['Total Neto'].sum().reset_index()
        fig_linea = px.line(df_diario, x='Fecha', y='Total Neto', title="Evolución diaria de ventas")
        st.plotly_chart(fig_linea, use_container_width=True)

def mostrar_ventas():
    st.title("🛒 Registro de Ventas")
    df_p = leer_desglose()
    df_r = leer_recetas()
    df_i = leer_ingredientes()
    
    if df_p.empty:
        st.error("Error: Debe configurar precios primero.")
        return

    with st.form("venta_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        fecha = col1.date_input("Fecha Venta", datetime.date.today())
        producto = col2.selectbox("Producto", df_p['Producto'].unique())
        cantidad = col3.number_input("Cantidad", min_value=1, step=1)
        
        col4, col5 = st.columns(2)
        pago = col4.selectbox("Método de Pago", ["Efectivo", "Tarjeta"])
        desc_porc = col5.number_input("Descuento %", min_value=0.0, max_value=100.0, value=0.0)
        
        if st.form_submit_button("Finalizar Venta"):
            # Lógica de costos
            costos_dict = {normalizar_texto(r['Ingrediente']): float(r['Costo por Unidad Receta']) for _, r in df_i.iterrows()}
            
            # Cálculo de costo de producción del producto
            costo_unitario_prod = 0.0
            if producto in df_r.columns:
                for _, row_rec in df_r.iterrows():
                    ing_nom = normalizar_texto(row_rec['Ingrediente'])
                    cant_req = pd.to_numeric(row_rec[producto], errors='coerce') or 0.0
                    costo_unitario_prod += (cant_req * costos_dict.get(ing_nom, 0.0))
            
            precio_v = float(df_p.loc[df_p['Producto'] == producto, 'Precio Venta'].values[0])
            bruto = precio_v * cantidad
            monto_desc = bruto * (desc_porc / 100)
            subtotal = bruto - monto_desc
            comision = subtotal * (COMISION_TARJETA / 100) if pago == "Tarjeta" else 0.0
            neto = subtotal - comision
            costo_total_v = costo_unitario_prod * cantidad
            ganancia = neto - costo_total_v

            nueva_venta = {
                'Fecha': fecha.strftime("%Y-%m-%d"),
                'Producto': producto,
                'Cantidad': cantidad,
                'Precio Unitario': precio_v,
                'Total Bruto': bruto,
                'Descuento %': desc_porc,
                'Comisión': comision,
                'Total Neto': neto,
                'Ganancia': ganancia,
                'Pago': pago
            }

            # 1. Guardar Venta
            df_ventas_existentes = cargar_csv_desde_r2('ventas')
            df_final_v = pd.concat([df_ventas_existentes, pd.DataFrame([nueva_venta])], ignore_index=True)
            guardar_csv_en_r2(df_final_v, 'ventas')

            # 2. Descontar Inventario
            df_inv = leer_inventario_df()
            if producto in df_r.columns:
                for _, row_rec in df_r.iterrows():
                    ing_orig = row_rec['Ingrediente']
                    cant_usada = (pd.to_numeric(row_rec[producto], errors='coerce') or 0.0) * cantidad
                    if cant_usada > 0:
                        df_inv.loc[df_inv['Ingrediente'] == ing_orig, 'Stock Actual'] -= cant_usada
                
                guardar_csv_en_r2(df_inv, 'inventario')
                st.success(f"Venta de {producto} registrada. Stock actualizado.")
                st.rerun()

def mostrar_inventario():
    st.title("📦 Inventario y Stock")
    df_inv = leer_inventario_df()
    
    col_a, col_b = st.columns([3, 1])
    
    with col_b:
        st.subheader("Ajuste Manual")
        ing_sel = st.selectbox("Ingrediente", df_inv['Ingrediente'].unique() if not df_inv.empty else [])
        cant_adj = st.number_input("Cantidad (+ compra / - merma)", value=0.0)
        if st.button("Aplicar Movimiento"):
            df_inv.loc[df_inv['Ingrediente'] == ing_sel, 'Stock Actual'] += cant_adj
            guardar_csv_en_r2(df_inv, 'inventario')
            st.rerun()

    with col_a:
        st.subheader("Estado General")
        # Marcado de stock bajo
        def resaltar_bajo(row):
            return ['background-color: #ff9999' if row['Stock Actual'] <= row['Stock Mínimo'] else '' for _ in row]
        
        if not df_inv.empty:
            st.dataframe(df_inv.style.apply(resaltar_bajo, axis=1), use_container_width=True)
        else:
            st.info("Inventario vacío.")

def mostrar_ingredientes():
    st.title("🧪 Maestro de Ingredientes")
    df = leer_ingredientes()
    
    with st.expander("➕ Agregar Nuevo Ingrediente"):
        with st.form("nuevo_ing"):
            c1, c2, c3 = st.columns(3)
            n = c1.text_input("Nombre")
            p = c2.text_input("Proveedor")
            cc = c3.number_input("Costo Compra", min_value=0.0)
            
            c4, c5, c6 = st.columns(3)
            cu = c4.number_input("Cantidad x Unidad Compra", min_value=0.01)
            ur = c5.text_input("Unidad Receta (gr, ml)")
            
            if st.form_submit_button("Guardar"):
                costo_r = cc / cu
                nueva_data = pd.DataFrame([{
                    'Ingrediente': n, 'Proveedor': p, 'Costo de Compra': cc,
                    'Cantidad por Unidad de Compra': cu, 'Unidad Receta': ur, 'Costo por Unidad Receta': costo_r
                }])
                df = pd.concat([df, nueva_data], ignore_index=True)
                # Crear también en inventario si no existe
                df_inv = leer_inventario_df()
                if n not in df_inv['Ingrediente'].values:
                    df_inv = pd.concat([df_inv, pd.DataFrame([{'Ingrediente': n, 'Stock Actual': 0, 'Stock Mínimo': 0, 'Stock Máximo': 0}])])
                    guardar_csv_en_r2(df_inv, 'inventario')
                
                guardar_csv_en_r2(df, 'ingredientes')
                st.rerun()

    edit_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
    if st.button("💾 Guardar Cambios en Tabla"):
        guardar_csv_en_r2(edit_df, 'ingredientes')
        st.rerun()

def mostrar_recetas():
    st.title("📝 Fórmulas y Recetas")
    df_r = leer_recetas()
    if df_r.empty:
        df_r = pd.DataFrame(columns=['Ingrediente'])
    
    col_r1, col_r2 = st.columns([1, 4])
    with col_r1:
        nuevo_p = st.text_input("Nuevo Producto")
        if st.button("Añadir Columna"):
            if nuevo_p and nuevo_p not in df_r.columns:
                df_r[nuevo_p] = 0.0
                guardar_csv_en_r2(df_r, 'recetas')
                st.rerun()
    
    with col_r2:
        res_df = st.data_editor(df_r, use_container_width=True)
        if st.button("Guardar Proporciones"):
            guardar_csv_en_r2(res_df, 'recetas')
            st.rerun()

def mostrar_precios():
    st.title("💰 Margen y Precios de Venta")
    df_p = leer_desglose()
    df_r = leer_recetas()
    df_i = leer_ingredientes()
    
    costos_dict = {normalizar_texto(r['Ingrediente']): float(r['Costo por Unidad Receta']) for _, r in df_i.iterrows()}
    
    productos = [c for c in df_r.columns if c != 'Ingrediente']
    data_margen = []
    
    for prod in productos:
        costo_prod = 0.0
        for _, row in df_r.iterrows():
            ing = normalizar_texto(row['Ingrediente'])
            cant = pd.to_numeric(row[prod], errors='coerce') or 0.0
            costo_prod += (cant * costos_dict.get(ing, 0.0))
        
        precio_actual = 0.0
        if not df_p.empty and prod in df_p['Producto'].values:
            precio_actual = float(df_p.loc[df_p['Producto'] == prod, 'Precio Venta'].values[0])
        
        data_margen.append({
            'Producto': prod,
            'Costo Producción': costo_prod,
            'Precio Venta': precio_actual,
            'Margen $': precio_actual - costo_prod,
            'Margen %': ((precio_actual - costo_prod) / precio_actual * 100) if precio_actual > 0 else 0
        })

    df_final_p = pd.DataFrame(data_margen)
    edit_p = st.data_editor(df_final_p, use_container_width=True, disabled=['Costo Producción', 'Margen $', 'Margen %'])
    
    if st.button("Actualizar Precios"):
        guardar_csv_en_r2(edit_p[['Producto', 'Precio Venta']], 'desglose')
        st.rerun()

# --- MAIN LOOP ---

def main():
    if not check_auth():
        st.stop()

    # Sidebar
    st.sidebar.image("https://via.placeholder.com/150?text=BonBon+Peach", width=100) # Opcional: tu logo
    st.sidebar.title("Menú Principal")
    
    hoy = datetime.date.today()
    st.sidebar.subheader("📅 Filtro Global")
    f_inicio = st.sidebar.date_input("Inicio", hoy.replace(day=1))
    f_fin = st.sidebar.date_input("Fin", hoy)
    
    opciones = {
        "📊 Dashboard": lambda: mostrar_dashboard(f_inicio, f_fin),
        "🛒 Ventas": mostrar_ventas,
        "📦 Inventario": mostrar_inventario,
        "🧪 Ingredientes": mostrar_ingredientes,
        "📝 Recetas": mostrar_recetas,
        "💰 Precios": mostrar_precios
    }
    
    seleccion = st.sidebar.radio("Navegación", list(opciones.keys()))
    
    st.sidebar.markdown("---")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.authenticated = False
        st.rerun()
    
    # Ejecutar sección
    opciones[seleccion]()

if __name__ == "__main__":
    main()
