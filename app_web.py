import requests
import streamlit as st
import hashlib
import pandas as pd
import time
import os
import unicodedata
import re
import datetime
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO, BytesIO

WORKER_URL = "https://admin.bonbon-peach.com/api"

R2_INGREDIENTES = "IngredientesBase"
R2_RECETAS = "Recetas"
R2_PRECIOS = "CostoPorProducto"
R2_VENTAS = "VentasDiarias"
R2_INVENTARIO = "Inventario"

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
SESSION_TIMEOUT_MIN = 5  # minutos (ajusta a gusto)

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
    # Si ya está autenticado, validar timeout
    if st.session_state.get("authenticated"):
        last_activity = st.session_state.get("last_activity", now)

        # ⏱️ Expiración por inactividad
        if now - last_activity > SESSION_TIMEOUT_MIN * 60:
            st.session_state.clear()
            st.warning("⏱️ Sesión expirada por inactividad")
            st.rerun()

        # Actualizar actividad
        st.session_state.last_activity = now
        return True

    # ---- LOGIN ----
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

def r2_read_csv(filename):
    """Cargar CSV desde Cloudflare R2 (Worker devuelve JSON)"""
    try:
        response = requests.get(f"{WORKER_URL}/{filename}", timeout=10)

        if response.status_code != 200:
            st.error(f"❌ Error HTTP {response.status_code} al leer {filename}")
            return pd.DataFrame()

        data = response.json()

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df.columns = [c.strip() for c in df.columns]
        return df

    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error de conexión con R2 ({filename}): {e}")
        return pd.DataFrame()

    except ValueError as e:
        st.error(f"❌ Error parseando JSON de {filename}: {e}")
        return pd.DataFrame()

    except Exception as e:
        st.error(f"❌ Error inesperado leyendo {filename}: {e}")
        return pd.DataFrame()

def r2_write_csv(df, filename):
    """Guardar CSV en Cloudflare R2"""
    try:
        # Convertir DataFrame a lista de diccionarios
        if not df.empty:
            data = df.to_dict('records')
        else:
            data = []
            
        response = requests.post(
            f"{WORKER_URL}/{filename}", 
            json=data
        )
        if response.status_code == 200:
            st.success("✅ Datos guardados correctamente")
            return True
        else:
            st.error("❌ Error guardando datos")
            return False
    except Exception as e:
        st.error(f"❌ Error guardando {filename}: {e}")
        return False

def normalizar_texto(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().strip()
    texto = ' '.join(texto.split())
    texto = str(unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8'))
    return re.sub(r'[^a-z0-9\s]', '', texto)

def clean_and_convert_float(value_str, default=0.0):
    if isinstance(value_str, (int, float)): 
        return round(float(value_str), 2)  # <--- Añadido round
    if not isinstance(value_str, str): 
        return default
    cleaned = value_str.strip().replace('$', '').replace(',', '').replace('%', '')
    try: 
        return round(float(cleaned), 2)    # <--- Añadido round
    except (ValueError, TypeError): 
        return default

# --- GESTIÓN DE DATOS ---
#@st.cache_data
def leer_ingredientes_base():
    ingredientes = []
    
    try:
            df = r2_read_csv(R2_INGREDIENTES)
            df.columns = df.columns.str.strip()
            for _, fila in df.iterrows():
                nombre = str(fila.get('Ingrediente', '')).strip()
                if not nombre: continue
                costo_compra = clean_and_convert_float(fila.get('Costo de Compra', 0))
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
    except Exception as e: st.error(f"Error ingredientes: {e}")
    return ingredientes

def guardar_ingredientes_base(df):
    df = df.copy()

    # Limpieza final
    df.columns = df.columns.str.strip()
    df = df.fillna("")

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)

    response = requests.put(
        f"{WORKER_URL}/IngredientesBase.csv",
        data=csv_buffer.getvalue(),
        headers={"Content-Type": "text/csv"},
        timeout=10
    )

    if response.status_code != 200:
        st.error("❌ Error al guardar IngredientesBase")
    else:
        st.success("✅ IngredientesBase guardado correctamente")

        r2_write_csv(pd.DataFrame(datos), R2_INGREDIENTES)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error guardando ingredientes: {e}")
        return False

def leer_inventario():
    inventario = {}
    try:
            df = r2_read_csv(R2_INVENTARIO)
            for _, fila in df.iterrows():
                nombre = str(fila.get('Ingrediente', '')).strip()
                if nombre:
                    inventario[nombre] = {
                        'stock_actual': clean_and_convert_float(fila.get('Stock Actual', '0')),
                        'min': clean_and_convert_float(fila.get('Stock Mínimo', '0')),
                        'max': clean_and_convert_float(fila.get('Stock Máximo', '0'))
                    }
    except Exception: pass
    return inventario

def guardar_inventario_csv(inventario_data):
    try:
        datos = []
        for nombre, data in inventario_data.items():
            datos.append({
                'Ingrediente': nombre,
                'Stock Actual': f"{data.get('stock_actual', 0.0):.4f}",
                'Stock Mínimo': f"{data.get('min', 0.0):.4f}",
                'Stock Máximo': f"{data.get('max', 0.0):.4f}"
            })
        r2_write_csv(pd.DataFrame(datos), R2_INVENTARIO)
    except Exception as e: st.error(f"Error guardando inventario: {e}")

#@st.cache_data
def leer_recetas():
    recetas = {}
    ingredientes = leer_ingredientes_base()
    try:
            df = r2_read_csv(R2_RECETAS)
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
    except Exception as e: st.error(f"Error recetas: {e}")
    return recetas

def guardar_recetas_csv(recetas_data):
    try:
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
        r2_write_csv(pd.DataFrame(data), R2_RECETAS)
        st.cache_data.clear()
    except Exception as e: st.error(f"Error guardando recetas: {e}")

def guardar_ventas(ventas_data):
    if not ventas_data:
        return False

    try:
        # 1️⃣ Leer ventas actuales desde R2
        df_actual = r2_read_csv(R2_VENTAS)

        # 2️⃣ Convertir nuevas ventas a DF
        df_nuevas = pd.DataFrame(ventas_data)

        # 3️⃣ Concatenar
        if df_actual.empty:
            df_final = df_nuevas
        else:
            df_final = pd.concat([df_actual, df_nuevas], ignore_index=True)

        # 4️⃣ Normalizar columnas
        df_final.columns = [c.strip() for c in df_final.columns]

        # 5️⃣ Guardar en R2
        return r2_write_csv(df_final, R2_VENTAS)

    except Exception as e:
        st.error(f"❌ Error guardando ventas: {e}")
        return False

def leer_ventas(fecha_inicio=None, fecha_fin=None):
    ventas = []
    try:
            df = r2_read_csv(R2_VENTAS)
            if not df.empty and 'Fecha' in df.columns:
                df['Fecha_DT'] = pd.to_datetime(df['Fecha'], format='%d/%m/%Y', errors='coerce')
                df = df.dropna(subset=['Fecha_DT'])
                
                if fecha_inicio and fecha_fin:
                    mask = (df['Fecha_DT'].dt.date >= fecha_inicio) & (df['Fecha_DT'].dt.date <= fecha_fin)
                    df = df.loc[mask]
                
                numeric_cols = ['Total Venta Bruto', 'Ganancia Neta', 'Cantidad', 'Comision ($)', 'Descuento ($)']
                for col in numeric_cols:
                    if col in df.columns:
                         if df[col].dtype == 'object':
                             df[col] = df[col].astype(str).str.replace(',', '', regex=False).str.replace('$', '', regex=False).astype(float)
                ventas = df.to_dict('records')
    except Exception as e: st.error(f"Error lectura ventas: {e}")
    return ventas


    encabezados = ['Fecha', 'Producto', 'Cantidad', 'Precio Unitario', 'Total Venta Bruto', 
                   'Descuento (%)', 'Descuento ($)', 'Costo Total', 'Ganancia Bruta', 
                   'Comision ($)', 'Ganancia Neta', 'Forma Pago']
   # 1️⃣ Leer ventas actuales desde R2
    df_actual = r2_read_csv(R2_VENTAS)

    if df_actual.empty:
        df_actual = pd.DataFrame(ventas_nuevas)
    else:
        df_nuevas = pd.DataFrame(ventas_nuevas)
        df_actual = pd.concat([df_actual, df_nuevas], ignore_index=True)

    # 2️⃣ Normalizar columnas (evita errores silenciosos)
    df_actual.columns = [c.strip() for c in df_actual.columns]

    # 3️⃣ Convertir a JSON (formato esperado por el Worker)
    data_json = df_actual.to_dict(orient="records")

    # 4️⃣ Subir nuevamente a R2
    response = requests.put(
        f"{WORKER_URL}/{R2_VENTAS}",
        json=data_json
    )

    if response.status_code != 200:
        st.error(f"❌ Error al guardar ventas en R2: {response.text}")
    else:
        st.success("✅ Venta guardada correctamente")

def leer_precios_desglose():
    precios = {}
    try:
            df = r2_read_csv(R2_PRECIOS)
            for _, row in df.iterrows():
                precios[row['Producto']] = {
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

# --- PESTAÑAS Y VISTAS ---

def mostrar_dashboard(f_inicio, f_fin):
    st.markdown('<div class="section-header">📊 Dashboard General</div>', unsafe_allow_html=True)
    
    ventas = leer_ventas(f_inicio, f_fin)
    if not ventas:
        st.warning("No hay datos para el rango seleccionado.")
        return

    df_filtered = pd.DataFrame(ventas)
    
    # --- KPIs ---
    total_ventas = df_filtered['Total Venta Bruto'].sum()
    total_ganancia = df_filtered['Ganancia Neta'].sum()
    total_transacciones = len(df_filtered)
    
    # METRICO NUEVO: TICKET PROMEDIO
    ticket_promedio = total_ventas / total_transacciones if total_transacciones > 0 else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ventas Totales", f"${total_ventas:,.2f}")
    c2.metric("Ganancia Neta", f"${total_ganancia:,.2f}")
    c3.metric("Ticket Promedio", f"${ticket_promedio:,.2f}") # Nuevo
    c4.metric("Transacciones", f"{total_transacciones}")
    
    st.markdown("---")
    
    # --- GRÁFICO 1: TENDENCIA DIARIA ---
    st.subheader("Tendencia de Ventas (Diario)")
    daily_summary = df_filtered.groupby(df_filtered['Fecha_DT'].dt.date).agg(
        Ventas=('Total Venta Bruto', 'sum'),
        Ganancia=('Ganancia Neta', 'sum')
    ).reset_index().rename(columns={'Fecha_DT': 'Fecha'})
    
    fig_daily = px.line(daily_summary, x='Fecha', y=['Ventas', 'Ganancia'], 
                        markers=True, color_discrete_sequence=['#4B2840', '#F1B48B'], template='plotly_white')
    st.plotly_chart(fig_daily, use_container_width=True)
    
    # 3. Análisis de Productos
    st.subheader("Desempeño de Productos")
    col_g1, col_g2 = st.columns(2)
    
    product_summary = df_filtered.groupby('Producto').agg(
        Total_Venta=('Total Venta Bruto', 'sum'),
        Total_Ganancia=('Ganancia Neta', 'sum'),
        Cantidad=('Cantidad', 'sum')
    ).reset_index()
    
    with col_g1:
        top_cant = product_summary.sort_values('Cantidad', ascending=False).head(10)
        fig_prod = px.bar(top_cant, x='Cantidad', y='Producto', orientation='h',
                          title="Top 10 Productos (Volumen)", 
                          text_auto=True, template='plotly_white',
                          color='Cantidad', color_continuous_scale='Purples')
        fig_prod.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_prod, use_container_width=True)
        
    with col_g2:
        top_gan = product_summary.sort_values('Total_Ganancia', ascending=False).head(10)
        fig_gan = px.bar(top_gan, x='Total_Ganancia', y='Producto', orientation='h',
                         title="Top 10 Productos (Ganancia $)",
                         text_auto='.2s', template='plotly_white',
                         color='Total_Ganancia', color_continuous_scale='Peach')
        fig_gan.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_gan, use_container_width=True)

    # --- GRÁFICO 2: PATRONES SEMANALES (SUPERPOSICIÓN) ---
    st.subheader("🔎 Patrones Semanales ")
    st.caption("Compara el rendimiento de los días de la semana entre diferentes semanas para identificar patrones (ej. 'Los martes siempre son bajos').")
    
    # Preparar datos para superposición
    df_patron = df_filtered.copy()
    # Mapear día en inglés a español y asegurar orden
    df_patron['Dia_Nombre'] = df_patron['Fecha_DT'].dt.day_name().map(DIAS_ESP)
    # Agrupar por semana (Inicio Lunes)
    df_patron['Inicio_Semana'] = df_patron['Fecha_DT'].apply(lambda x: x - datetime.timedelta(days=x.weekday()))
    
    patron_agrupado = df_patron.groupby(['Inicio_Semana', 'Dia_Nombre'])['Total Venta Bruto'].sum().reset_index()
    
    fig_patron = px.line(patron_agrupado, x='Dia_Nombre', y='Total Venta Bruto', color='Inicio_Semana',
                         category_orders={'Dia_Nombre': ORDEN_DIAS}, # Forzar orden Lun-Dom
                         title="Comparativa Semanal (Día a Día)",
                         labels={'Total Venta Bruto': 'Ventas ($)', 'Inicio_Semana': 'Semana del'},
                         template='plotly_white')
    st.plotly_chart(fig_patron, use_container_width=True)

    # --- TABLA: RESUMEN SEMANAL (LUNES A DOMINGO) ---
    st.subheader("Resumen Semanal (Lunes - Domingo)")
    
    # Agrupar forzando inicio en Lunes
    df_filtered['Semana_Inicio'] = df_filtered['Fecha_DT'].apply(lambda x: x - datetime.timedelta(days=x.weekday()))
    
    weekly = df_filtered.groupby('Semana_Inicio').agg({
        'Total Venta Bruto': 'sum',
        'Ganancia Neta': 'sum',
        'Cantidad': 'sum'
    }).reset_index().sort_values('Semana_Inicio', ascending=False)
    
    # Formatear columna fecha para visualización "Lun DD/MM - Dom DD/MM"
    weekly['Periodo'] = weekly['Semana_Inicio'].apply(
        lambda x: f"Lun {x.strftime('%d/%m')} - Dom {(x + datetime.timedelta(days=6)).strftime('%d/%m')}"
    )
    
    st.dataframe(
        weekly[['Periodo', 'Total Venta Bruto', 'Ganancia Neta', 'Cantidad']].style.format({
            'Total Venta Bruto': '${:,.2f}', 
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
    st.markdown('<div class="section-header">📝 Recetas y Costos</div>', unsafe_allow_html=True)
    recetas = leer_recetas()
    ingredientes = leer_ingredientes_base()
    
    col_izq, col_der = st.columns([1, 2])
    with col_izq:
        st.subheader("Menú")
        nuevo_nom = st.text_input("Nueva receta:")
        if st.button("Crear Receta") and nuevo_nom:
            if nuevo_nom not in recetas:
                recetas[nuevo_nom] = {'ingredientes': {}, 'costo_total': 0.0}
                guardar_recetas_csv(recetas); st.success(f"Creada {nuevo_nom}"); st.rerun()
        st.divider()
        sel_receta = st.radio("Seleccionar Receta:", list(recetas.keys()))
        
    with col_der:
        if sel_receta:
            st.subheader(f"Editando: {sel_receta}")
            datos = recetas[sel_receta]
            if datos['ingredientes']:
                lista_items = []
                for ing, cant in datos['ingredientes'].items():
                    info = next((i for i in ingredientes if i['nombre'] == ing), None)
                    costo_parcial = (info['costo_receta'] * cant) if info else 0
                    lista_items.append({'Ingrediente': ing, 'Cantidad': cant, 'Costo': costo_parcial})
                st.dataframe(pd.DataFrame(lista_items).style.format({'Costo': "${:.2f}"}), use_container_width=True)
                
                to_del = st.selectbox("Eliminar ingrediente:", [""] + list(datos['ingredientes'].keys()))
                if st.button("Eliminar") and to_del:
                    del recetas[sel_receta]['ingredientes'][to_del]; guardar_recetas_csv(recetas); st.rerun()
            else: st.info("Receta vacía.")
            
            st.metric("Costo Total Receta", f"${datos['costo_total']:.2f}")
            st.divider()
            c1, c2, c3 = st.columns([2,1,1])
            ing_sel = c1.selectbox("Ingrediente", [i['nombre'] for i in ingredientes])
            cant_sel = c2.number_input("Cantidad", min_value=0.0, step=0.1)
            if c3.button("Agregar"):
                recetas[sel_receta]['ingredientes'][ing_sel] = cant_sel; guardar_recetas_csv(recetas); st.rerun()

def mostrar_precios():
    st.markdown('<div class="section-header">💰 Análisis de Precios y Márgenes</div>', unsafe_allow_html=True)
    recetas = leer_recetas()
    precios_existentes = leer_precios_desglose()
    
    data_tabla = []
    for prod, info_receta in recetas.items():
        costo = info_receta['costo_total']
        p_venta = precios_existentes.get(prod, {}).get('precio_venta', 0.0)
        margen = p_venta - costo
        margen_p = (margen / p_venta * 100) if p_venta else 0
        
        data_tabla.append({
            'Producto': prod, 'Costo Producción': costo,
            'Precio Venta': p_venta, 'Margen $': margen, 'Margen %': margen_p
        })
    
    df = pd.DataFrame(data_tabla)
    
    # --- GRÁFICO VISUAL DE PRECIOS (NUEVO) ---
    if not df.empty:
        st.subheader("Estructura de Precios: Costo vs. Ganancia")
        
        # Para Plotly apilado, usamos Costo y Margen. La suma visual es el Precio.
        fig = px.bar(df, x='Producto', y=['Costo Producción', 'Margen $'],
                     title="Desglose del Precio de Venta",
                     labels={'value': 'Dinero ($)', 'variable': 'Componente'},
                     color_discrete_map={'Costo Producción': '#FF9AA2', 'Margen $': '#B5EAD7'}, # Rojo y Verde pastel
                     template='plotly_white')
        
        fig.update_layout(barmode='stack', hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
        
        # MÉTRICA EXTRA: TOP MARGEN PORCENTUAL
        top_margen = df.sort_values('Margen %', ascending=False).head(3)
        st.caption(f"🏆 Productos con mejor rendimiento (%): {', '.join(top_margen['Producto'].tolist())}")

    with st.expander("✏️ Modificar Precio de Venta"):
        prod_sel = st.selectbox("Producto:", df['Producto'].tolist())
        if prod_sel:
            row = df[df['Producto'] == prod_sel].iloc[0]
            st.write(f"Costo actual: ${row['Costo Producción']:.2f}")
            nuevo_precio = st.number_input("Nuevo Precio Venta:", value=float(row['Precio Venta']))
            
            if st.button("Actualizar Precio"):
                todos_precios = []
                todos_precios = r2_read_csv(R2_PRECIOS).to_dict('records')

                
                found = False
                margen_nuevo = nuevo_precio - row['Costo Producción']
                margen_p_nuevo = (margen_nuevo / nuevo_precio * 100) if nuevo_precio else 0
                
                for item in todos_precios:
                    if item['Producto'] == prod_sel:
                        item['Precio Venta'] = nuevo_precio
                        item['Margen Bruto'] = margen_nuevo
                        item['Margen Bruto (%)'] = margen_p_nuevo
                        found = True; break
                if not found:
                    todos_precios.append({
                        'Producto': prod_sel, 'Precio Venta': nuevo_precio,
                        'Margen Bruto': margen_nuevo, 'Margen Bruto (%)': margen_p_nuevo
                    })
                r2_write_csv(pd.DataFrame(todos_precios), R2_PRECIOS)
                st.success("Precio actualizado."); st.rerun()

    st.dataframe(df.style.format({
        'Costo Producción': "${:.2f}", 'Precio Venta': "${:.2f}", 
        'Margen $': "${:.2f}", 'Margen %': "{:.1f}%"
    }), use_container_width=True)

def mostrar_ventas(f_inicio, f_fin):
   st.markdown('<div class="section-header">🛒 Terminal de Ventas</div>', unsafe_allow_html=True)
   ventas = leer_ventas(f_inicio, f_fin)
   col_pos, col_hist = st.columns([2, 3])
   es_admin = st.session_state.get("rol") == "admin"
    
# CORRECCIÓN: Convertir a DataFrame si es una lista, de lo contrario Pandas no funcionará
   if isinstance(ventas, list):
        ventas_df = pd.DataFrame(ventas)
   else:
        ventas_df = ventas

    # --- Resumen Gráfico de Ventas (Donas) ---
   if es_admin and not ventas_df.empty:
        st.subheader("📈 Resumen del Periodo Seleccionado")
        cg1, cg2 = st.columns(2)
        
        with cg1:
            # Gráfico Dona: Efectivo vs Tarjeta
            if 'Forma Pago' in ventas_df.columns:
                metodo_sum = ventas_df.groupby('Forma Pago')['Total Venta Bruto'].sum().reset_index()
                fig_met = px.pie(metodo_sum, values='Total Venta Bruto', names='Forma Pago', hole=.5, 
                                title="Distribución de Pago", 
                                color_discrete_sequence=["#D4D4D4", "#95E9BF"])
                st.plotly_chart(fig_met, use_container_width=True)
            
        with cg2:
            # Gráfico Dona: Venta vs Ganancia
            venta_t = ventas_df['Total Venta Bruto'].sum()
            ganancia_t = ventas_df['Ganancia Neta'].sum()
            costos_t = venta_t - ganancia_t
            
            fig_gan = px.pie(names=['Ganancia Neta', 'Costos operativos'], 
                            values=[ganancia_t, costos_t], 
                            hole=.5, title="Venta Bruta vs Utilidad", 
                            color_discrete_sequence=["#80A6F8", "#A2FF9A"])
            st.plotly_chart(fig_gan, use_container_width=True)
    
        st.divider()
       
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

        st.markdown("---")
        if st.session_state.carrito:
            total_carrito = 0
            for i, item in enumerate(st.session_state.carrito):
                subtotal = (item['Precio Unitario'] * item['Cantidad']) * (1 - item['Descuento %']/100)
                total_carrito += subtotal
                with st.container():
                    c_det, c_del = st.columns([5, 1])
                    with c_det:
                        icon = "💳" if item['Es Tarjeta'] else "💵"
                        st.markdown(f"**{item['Producto']}** x{item['Cantidad']} | {icon}")
                        st.caption(f"${subtotal:.2f} (Desc: {item['Descuento %']}%)")
                    with c_del:
                        if st.button("❌", key=f"del_{i}"):
                            st.session_state.carrito.pop(i); st.rerun()
                    st.divider()

            st.metric("Total a Pagar", f"${total_carrito:.2f}")

            if st.button("✅ FINALIZAR VENTA", type="primary", use_container_width=True):
                ventas_nuevas = []
                fecha_hoy = datetime.date.today().strftime('%d/%m/%Y')
                inventario = leer_inventario()
                
                for item in st.session_state.carrito:
                    p = item['Producto']; q = item['Cantidad']; pu = item['Precio Unitario']; d = item['Descuento %']; es_tarjeta = item['Es Tarjeta']
                    total_bruto = pu * q; monto_desc = total_bruto * (d/100); subtotal = total_bruto - monto_desc
                    comision = subtotal * (COMISION_TARJETA / 100) if es_tarjeta else 0.0
                    costo_total = recetas[p]['costo_total'] * q
                    total_neto = subtotal - comision; ganancia = total_neto - costo_total
                    
                    ventas_nuevas.append({
                        'Fecha': fecha_hoy, 'Producto': p, 'Cantidad': q,
                        'Precio Unitario': pu, 'Total Venta Bruto': total_bruto,
                        'Descuento (%)': d, 'Descuento ($)': monto_desc,
                        'Costo Total': costo_total, 'Ganancia Bruta': subtotal - costo_total,
                        'Comision ($)': comision, 'Ganancia Neta': ganancia,
                        'Forma Pago': "Tarjeta" if es_tarjeta else "Efectivo"
                    })
                    if p in recetas:
                        for ing, cant_r in recetas[p]['ingredientes'].items():
                            if ing in inventario:
                                inventario[ing]['stock_actual'] -= (cant_r * q)
                                if inventario[ing]['stock_actual'] < 0: inventario[ing]['stock_actual'] = 0
                if guardar_ventas(ventas_nuevas):
                 guardar_inventario_csv(inventario)
                 st.session_state.carrito = []
                 st.toast("✅ Venta registrada y guardada en la nube")
                 st.rerun()
                else:
                 st.error("❌ No se pudo guardar la venta") 
        else: st.info("Carrito vacío")

   with col_hist:
        st.subheader("📜 Historial Reciente")
        ventas_hist = leer_ventas(f_inicio, f_fin)
        if ventas_hist:
            df_h = pd.DataFrame(ventas_hist)
            if 'Fecha_DT' in df_h.columns: df_h = df_h.sort_values('Fecha_DT', ascending=False)
            cols_admin = ['Fecha', 'Producto', 'Cantidad', 'Total Venta Bruto', 'Forma Pago']
            cols_vendedor = ['Fecha', 'Producto', 'Cantidad', 'Forma Pago']
            cols = cols_admin if es_admin else cols_vendedor
            st.dataframe(df_h[cols], use_container_width=True, hide_index=True)
        else: st.info("No hay ventas en este rango.")

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
            inv[ing_in]['stock_actual'] += cant_in; guardar_inventario_csv(inv); st.success(f"Actualizado {ing_in}"); st.rerun()

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
    # Por defecto mostrar el mes actual
    f_inicio = st.sidebar.date_input("Inicio", value=hoy.replace(day=1))
    f_fin = st.sidebar.date_input("Fin", value=hoy)
    st.sidebar.markdown("---")
    st.sidebar.caption(f"👤 {st.session_state.usuario} ({st.session_state.rol})")

    rol = st.session_state.get("rol", "vendedor")

    if rol == "vendedor":
        opcion = "🛒 Ventas"
    else:
        opcion = st.sidebar.radio(
            "Navegación",
            ["📊 Dashboard", "🛒 Ventas", "🔄 Reposición", "📦 Inventario", "🧪 Ingredientes", "📝 Recetas", "💰 Precios"]
        )

    st.sidebar.markdown("---")
    if st.sidebar.button("Cerrar Sesión"): st.session_state.authenticated = False; st.rerun()

    if opcion == "📊 Dashboard": mostrar_dashboard(f_inicio, f_fin)
    elif opcion == "🧪 Ingredientes": mostrar_ingredientes()
    elif opcion == "📝 Recetas": mostrar_recetas()
    elif opcion == "💰 Precios": mostrar_precios()
    elif opcion == "🛒 Ventas": mostrar_ventas(f_inicio, f_fin)
    elif opcion == "📦 Inventario": mostrar_inventario()
    elif opcion == "🔄 Reposición": mostrar_reposicion(f_inicio, f_fin)

if __name__ == "__main__":
    main()
