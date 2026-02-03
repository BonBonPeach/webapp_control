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

WORKER_URL = "https://admin.bonbon-peach.com/api"
API_KEY=st.secrets["API_KEY"].strip()

R2_INGREDIENTES = "ingredientes"
R2_RECETAS = "recetas"
R2_MODIFICADORES = "modificadores"
R2_PRECIOS = "precios"
R2_VENTAS = "ventas"
R2_INVENTARIO = "inventario"

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

# ===============================
# INGREDIENTES
# ===============================
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

# ===============================
# RECETAS (Con soporte Sub-recetas y Modificadores Permitidos)
# ===============================
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

# ===============================
# MODIFICADORES
# ===============================
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

# ===============================
# INVENTARIO
# ===============================
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

# ===============================
# VENTAS
# ===============================
def leer_ventas(f_ini=None, f_fin=None):
    df = api_read(R2_VENTAS)
    if df.empty or "Fecha" not in df.columns: return []
    df["Fecha_DT"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["Fecha_DT"])
    if f_ini and f_fin:
        df = df[(df["Fecha_DT"].dt.date >= f_ini) & (df["Fecha_DT"].dt.date <= f_fin)]
    
    cols_num = ["Total Venta Bruto", "Descuento ($)", "Ganancia Bruta", "Ganancia Neta", "Costo Total", "Precio Unitario", "Cantidad"]
    for col in cols_num:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    
    if "Total Venta Neta" not in df.columns:
        df["Total Venta Neta"] = df["Total Venta Bruto"] - df.get("Descuento ($)", 0)
    else:
        df["Total Venta Neta"] = pd.to_numeric(df["Total Venta Neta"], errors="coerce").fillna(df["Total Venta Bruto"] - df.get("Descuento ($)", 0))
    return df.to_dict("records")

def guardar_ventas(nuevas):
    df_actual = api_read(R2_VENTAS)
    df_nuevo = pd.DataFrame(nuevas).fillna(0)
    if "Total Venta Neta" not in df_nuevo.columns:
        df_nuevo["Total Venta Neta"] = df_nuevo.get("Total Venta Bruto", 0) - df_nuevo.get("Descuento ($)", 0)
    
    df = df_nuevo if df_actual.empty else pd.concat([df_actual, df_nuevo], ignore_index=True)
    return api_write(R2_VENTAS, df)

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

# --- PESTAÑAS Y VISTAS ---

def mostrar_dashboard(f_inicio, f_fin):
    st.markdown('<div class="section-header">📊 Dashboard General</div>', unsafe_allow_html=True)
    ventas = leer_ventas(f_inicio, f_fin)
    if not ventas:
        st.warning("No hay datos para el rango seleccionado.")
        return
    df_filtered = pd.DataFrame(ventas)
    
    total_ventas = df_filtered['Total Venta Neta'].sum()
    total_ganancia = df_filtered['Ganancia Neta'].sum()
    total_transacciones = len(df_filtered)
    ticket_promedio = total_ventas / total_transacciones if total_transacciones > 0 else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ventas Totales", f"${total_ventas:,.2f}")
    c2.metric("Ganancia Neta", f"${total_ganancia:,.2f}")
    c3.metric("Ticket Promedio", f"${ticket_promedio:,.2f}")
    c4.metric("Transacciones", f"{total_transacciones}")
    st.markdown("---")
    
    daily_summary = df_filtered.groupby(df_filtered['Fecha_DT'].dt.date).agg(
        Ventas=('Total Venta Neta', 'sum'),
        Ganancia=('Ganancia Neta', 'sum')
    ).reset_index().rename(columns={'Fecha_DT': 'Fecha'})
    daily_summary['Fecha'] = pd.to_datetime(daily_summary['Fecha'])
    
    fig_daily = px.line(daily_summary, x='Fecha', y=['Ventas', 'Ganancia'], markers=True, color_discrete_sequence=['#4B2840', '#F1B48B'], template='plotly_white')
    st.plotly_chart(fig_daily, use_container_width=True)

    col_g1, col_g2 = st.columns(2)
    product_summary = df_filtered.groupby('Producto').agg(Total_Venta=('Total Venta Neta', 'sum'), Total_Ganancia=('Ganancia Neta', 'sum'), Cantidad=('Cantidad', 'sum')).reset_index()
    
    with col_g1:
        fig_prod = px.bar(product_summary.sort_values('Cantidad', ascending=False).head(10), x='Cantidad', y='Producto', orientation='h', title="Top 10 (Volumen)", text_auto=True, template='plotly_white', color='Cantidad', color_continuous_scale='Purples')
        fig_prod.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_prod, use_container_width=True)
    with col_g2:
        fig_gan = px.bar(product_summary.sort_values('Total_Ganancia', ascending=False).head(10), x='Total_Ganancia', y='Producto', orientation='h', title="Top 10 (Ganancia $)", text_auto='.2s', template='plotly_white', color='Total_Ganancia', color_continuous_scale='Peach')
        fig_gan.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_gan, use_container_width=True)

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
   ventas = leer_ventas(f_inicio, f_fin)
   col_pos, col_hist = st.columns([2, 3])
   es_admin = st.session_state.get("rol") == "admin"
   
   if isinstance(ventas, list): ventas_df = pd.DataFrame(ventas)
   else: ventas_df = ventas

   # GRÁFICOS MINI
   if es_admin and not ventas_df.empty:
        with st.expander("📊 Resumen Rápido", expanded=False):
            cg1, cg2 = st.columns(2)
            with cg1:
                if 'Forma Pago' in ventas_df.columns:
                    st.plotly_chart(px.pie(ventas_df.groupby('Forma Pago')['Total Venta Neta'].sum().reset_index(), values='Total Venta Neta', names='Forma Pago', hole=.5, color_discrete_sequence=["#D4D4D4", "#95E9BF"]), use_container_width=True)
            with cg2:
                venta_t = ventas_df['Total Venta Neta'].sum(); ganancia_t = ventas_df['Ganancia Neta'].sum()
                st.plotly_chart(px.pie(names=['Ganancia', 'Costos'], values=[ganancia_t, venta_t - ganancia_t], hole=.5, color_discrete_sequence=["#80A6F8", "#A2FF9A"]), use_container_width=True)
       
   with col_pos:
        st.subheader("➕ Nueva Orden")
        if 'carrito' not in st.session_state: st.session_state.carrito = []
        
        recetas = leer_recetas()
        precios = leer_precios_desglose()
        modificadores = leer_modificadores()
        
        with st.form("add_form"):
            prod = st.selectbox("Producto", [""] + list(recetas.keys()))
            
            # --- LÓGICA DE MODIFICADORES CONDICIONALES ---
            mods_disponibles = []
            if prod:
                nombres_mods = recetas[prod].get("modificadores_validos", [])
                # Filtrar solo los que existen en la DB de modificadores
                mods_disponibles = [m for m in nombres_mods if m in modificadores]
            
            mods_sel = []
            if mods_disponibles:
                mods_sel = st.multiselect("Extras / Modificadores:", mods_disponibles)
            elif prod:
                st.caption("🚫 Sin modificadores disponibles para este producto.")

            c1, c2 = st.columns(2)
            cant = c1.number_input("Cant", min_value=1, value=1)
            desc = c2.number_input("Desc %", min_value=0.0, max_value=100.0)
            pago_tarjeta = st.checkbox("💳 Pago con Tarjeta")
            
            if st.form_submit_button("Agregar al Carrito", use_container_width=True):
                if prod:
                    p_base = precios.get(prod, {}).get('precio_venta', 0)
                    
                    costo_extra_mods = 0
                    lista_mods_detalle = []
                    for m in mods_sel:
                        precio_m = modificadores[m]["precio_extra"]
                        costo_extra_mods += precio_m
                        lista_mods_detalle.append({"nombre": m, "precio": precio_m})
                    
                    p_unit_final = p_base + costo_extra_mods

                    st.session_state.carrito.append({
                        'Producto': prod, 
                        'Cantidad': cant, 
                        'Precio Base': p_base,
                        'Modificadores': lista_mods_detalle,
                        'Precio Unitario Final': p_unit_final, 
                        'Descuento %': desc, 
                        'Es Tarjeta': pago_tarjeta
                    })
                    st.rerun()

        st.markdown("---")
        # VISTA CARRITO
        if st.session_state.carrito:
            total_carrito = 0
            for i, item in enumerate(st.session_state.carrito):
                subtotal = (item['Precio Unitario Final'] * item['Cantidad']) * (1 - item['Descuento %']/100)
                total_carrito += subtotal
                with st.container():
                    c_det, c_del = st.columns([5, 1])
                    with c_det:
                        icon = "💳" if item['Es Tarjeta'] else "💵"
                        st.markdown(f"**{item['Producto']}** x{item['Cantidad']} | {icon}")
                        if item['Modificadores']:
                            txt_mods = ", ".join([f"{m['nombre']} (+${m['precio']})" for m in item['Modificadores']])
                            st.caption(f"🧩 {txt_mods}")
                        st.caption(f"${subtotal:.2f} (Desc: {item['Descuento %']}%)")
                    with c_del:
                        if st.button("❌", key=f"del_{i}"):
                            st.session_state.carrito.pop(i); st.rerun()
                    st.divider()

            st.metric("Total a Pagar", f"${total_carrito:.2f}")

            if st.button("✅ COBRAR", type="primary", use_container_width=True):
                ventas_nuevas = []
                fecha_hoy = datetime.date.today().strftime('%d/%m/%Y')
                inventario = leer_inventario()
                
                # Función para descontar inventario recursivamente
                def descontar_recursivo(nombre_item, cantidad_necesaria):
                    if nombre_item in inventario:
                        inventario[nombre_item]['stock_actual'] -= cantidad_necesaria
                        if inventario[nombre_item]['stock_actual'] < 0: inventario[nombre_item]['stock_actual'] = 0
                    elif nombre_item in recetas:
                        sub_r = recetas[nombre_item]
                        for sub_ing, sub_cant in sub_r['ingredientes'].items():
                            descontar_recursivo(sub_ing, sub_cant * cantidad_necesaria)
                
                for item in st.session_state.carrito:
                    p = item['Producto']; q = item['Cantidad']
                    pu = item['Precio Unitario Final']; d = item['Descuento %']
                    es_tarjeta = item['Es Tarjeta']
                    
                    total_bruto = pu * q
                    monto_desc = total_bruto * (d/100)
                    subtotal_venta = total_bruto - monto_desc
                    comision = subtotal_venta * (COMISION_TARJETA / 100) if es_tarjeta else 0.0
                    
                    costo_total_item = 0
                    
                    # 1. Procesar Producto Principal
                    if p in recetas:
                        costo_total_item += (recetas[p]['costo_total'] * q)
                        for ing_nom, cant_receta in recetas[p]['ingredientes'].items():
                            descontar_recursivo(ing_nom, cant_receta * q)

                    # 2. Procesar Modificadores
                    for mod in item['Modificadores']:
                        mod_data = modificadores.get(mod['nombre'])
                        if mod_data:
                            # Sumar costo de ingredientes del modificador al costo total de la venta (para reporte)
                            costo_extra_mod = 0
                            # Descontar inventario
                            for m_ing, m_cant in mod_data["ingredientes"].items():
                                descontar_recursivo(m_ing, m_cant * q)
                                # Buscar costo para métricas
                                # (Simplificación: si es ingrediente base lo sumamos al costo del item)
                                # En un sistema real esto debe ser más robusto, aquí lo aproximamos
                            # Nota: El costo del modificador ya está implícito si sumamos sus ingredientes, 
                            # pero como el costo de receta solo incluye lo base, no sumamos el costo del modificador a `costo_total_item`
                            # a menos que queramos ver la ganancia neta reducida. Vamos a sumarlo:
                            for m_ing, m_cant in mod_data["ingredientes"].items():
                                # Buscar costo unitario (solo aproximado de ingredientes base)
                                # Esta parte es compleja sin cargar ingredientes base aqui.
                                # Por ahora asumiremos que el margen se calcula sobre el precio venta final.
                                pass

                    total_neto = subtotal_venta - comision
                    ganancia = total_neto - costo_total_item
                    
                    mods_str = ", ".join([m['nombre'] for m in item['Modificadores']])
                    nombre_ticket = f"{p} (+ {mods_str})" if mods_str else p

                    ventas_nuevas.append({
                        'Fecha': fecha_hoy, 'Producto': nombre_ticket, 'Cantidad': q,
                        'Precio Unitario': pu, 'Total Venta Neta': total_bruto,
                        'Descuento (%)': d, 'Descuento ($)': monto_desc,
                        'Costo Total': costo_total_item, 'Ganancia Bruta': subtotal_venta - costo_total_item,
                        'Comision ($)': comision, 'Ganancia Neta': ganancia,
                        'Forma Pago': "Tarjeta" if es_tarjeta else "Efectivo"
                    })

                if guardar_ventas(ventas_nuevas):
                    guardar_inventario(inventario)
                    st.session_state.carrito = []
                    st.toast("✅ Venta registrada correctamente")
                    st.rerun()
                else:
                    st.error("❌ Error al guardar")
 
        else: st.info("Carrito vacío")

   with col_hist:
        st.subheader("📜 Historial")
        ventas_hist = leer_ventas(f_inicio, f_fin)
        if ventas_hist:
            df_h = pd.DataFrame(ventas_hist)
            if 'Fecha_DT' in df_h.columns: df_h = df_h.sort_values('Fecha_DT', ascending=False)
            st.dataframe(df_h[['Fecha', 'Producto', 'Cantidad', 'Total Venta Neta', 'Forma Pago']], use_container_width=True, hide_index=True)

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
    data = calcular_reposicion_sugerida(f_inicio, f_fin)
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    else: st.warning("Sin datos.")

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
