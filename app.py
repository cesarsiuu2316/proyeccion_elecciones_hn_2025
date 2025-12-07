"""
Elecciones Honduras 2025 - Dashboard de Streamlit
Muestra proyecciones electorales con actualización automática.
"""

import streamlit as st
import pandas as pd
import json
import os
import subprocess
import sys
from datetime import datetime
import time

# Configuración de la página
st.set_page_config(
    page_title="Elecciones Honduras 2025 - Proyecciones",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Constantes
CACHE_FILE = "last_results.json"
REFRESH_INTERVAL = 120  # segundos
SCRAPER_RUNNING_FILE = ".scraper_running"
DATA_UPDATED_FILE = ".data_updated"

def check_for_new_data():
    """Verificar si el scraper ha escrito nuevos datos."""
    if os.path.exists(DATA_UPDATED_FILE):
        try:
            os.remove(DATA_UPDATED_FILE)
            return True
        except:
            pass
    return False

def is_scraper_running():
    """Verificar si el proceso del scraper está corriendo."""
    return os.path.exists(SCRAPER_RUNNING_FILE)

def trigger_scrape():
    """Solicitar un nuevo scrape creando un archivo de trigger."""
    trigger_file = ".trigger_scrape"
    with open(trigger_file, 'w') as f:
        f.write(datetime.now().isoformat())
    return True

def load_cached_data():
    """Cargar los datos más recientes del caché."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error cargando caché: {e}")
    return None

def calculate_projection(current_votes: float, actas_percentage: float) -> float:
    """Calcular votos proyectados basado en el conteo actual y porcentaje de actas."""
    if actas_percentage <= 0:
        return current_votes
    return (current_votes * 100) / actas_percentage

def generate_projection_summary(data, calculation_mode):
    """
    Genera el resumen de proyección recalculando desde los datos crudos.
    calculation_mode: 'DEPARTAMENTOS' o 'MUNICIPIOS'
    """
    if not data or 'departments' not in data:
        return []
        
    global_totals = {} # {name: {'current': 0, 'projected': 0}}
    
    departments = data['departments']
    
    for dept_name, dept_data in departments.items():
        if dept_name in ('raw_data', 'Nacional'):
            continue
            
        if calculation_mode == 'DEPARTAMENTOS':
            actas_pct = dept_data.get('actas_percentage', 0)
            candidates = dept_data.get('candidates', [])
            
            for cand in candidates:
                name = cand.get('name', 'Desconocido')
                votes = cand.get('votes', 0)
                
                if name in ["Información General", "Información Acta"]:
                    continue
                
                if name not in global_totals:
                    global_totals[name] = {'current': 0, 'projected': 0.0}
                
                global_totals[name]['current'] += votes
                
                proj = calculate_projection(votes, actas_pct)
                global_totals[name]['projected'] += proj
                
        elif calculation_mode == 'MUNICIPIOS':
            municipios = dept_data.get('municipios', {})
            # Si no hay municipios (ej. Voto Exterior a veces), usar datos del depto si existen
            if not municipios and calculation_mode == 'MUNICIPIOS':
                 pass 

            for mun_name, mun_data in municipios.items():
                actas_pct = mun_data.get('actas_percentage', 0)
                candidates = mun_data.get('candidates', [])
                
                for cand in candidates:
                    name = cand.get('name', 'Desconocido')
                    votes = cand.get('votes', 0)
                    
                    if name in ["Información General", "Información Acta"]:
                        continue
                    
                    if name not in global_totals:
                        global_totals[name] = {'current': 0, 'projected': 0.0}
                    
                    global_totals[name]['current'] += votes
                    
                    proj = calculate_projection(votes, actas_pct)
                    global_totals[name]['projected'] += proj

    # Calculate stats
    results = []
    grand_total_projected = sum(t['projected'] for t in global_totals.values())
    
    for name, totals in global_totals.items():
        proj = totals['projected']
        pct = (proj / grand_total_projected * 100) if grand_total_projected > 0 else 0
        results.append({
            'Candidate': name,
            'Current Votes': totals['current'],
            'Projected Votes': proj,
            'Percentage': pct
        })
        
    # Sort by projected votes
    results.sort(key=lambda x: x['Projected Votes'], reverse=True)
    return results[:3]

def display_summary_metrics(summary_data, key_prefix=""):
    """Helper para mostrar las tarjetas de métricas."""
    if not summary_data:
        st.warning("No hay datos suficientes para generar la proyección.")
        return

    try:
        summary_df = pd.DataFrame(summary_data)
        num_cols = min(len(summary_df), 3)
        if num_cols == 0:
            return

        cols = st.columns(num_cols)
        colors = ['🥇', '🥈', '🥉']
        
        for i, (idx, row) in enumerate(summary_df.iterrows()):
            if i >= 3: break
            with cols[i]:
                medal = colors[i] if i < 3 else '📊'
                candidate_name = str(row['Candidate'])
                st.metric(
                    label=f"{medal} {candidate_name[:20]}",
                    value=f"{row['Percentage']:.2f}%",
                    delta=f"{row['Projected Votes']:,.0f} votos proyectados"
                )
                st.caption(f"Actual: {row['Current Votes']:,.0f}")
    except Exception as e:
        st.error(f"Error mostrando métricas: {str(e)}")

def format_timestamp(timestamp_str):
    """Formatear timestamp para que sea más legible."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime("%d de %B, %Y a las %I:%M:%S %p")
    except:
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d de %B, %Y a las %I:%M:%S %p")
        except:
            return timestamp_str

def check_data_quality(data):
    """Verificar si algún departamento (excepto VOTO EN EL EXTERIOR) tiene 0 votos."""
    issues = []
    if not data or 'departments' not in data:
        return issues
    
    departments = data['departments']
    for dept_name, dept_data in departments.items():
        if dept_name in ('raw_data', 'Nacional', 'VOTO EN EL EXTERIOR'):
            continue
        
        candidates = dept_data.get('candidates', [])
        total_votes = sum(c.get('votes', 0) for c in candidates)
        
        if total_votes == 0:
            issues.append(dept_name)
    
    return issues

def process_department_data(data):
    """Procesar datos de departamentos en DataFrames para mostrar."""
    if not data or 'departments' not in data:
        return None, None
    
    departments = data['departments']
    
    # Obtener nombres de candidatos del primer departamento con votos
    top_candidates = []
    for dept_name, dept_data in departments.items():
        if dept_name in ('raw_data', 'Nacional'):
            continue
        candidates = dept_data.get('candidates', [])
        # Filter out non-candidates
        candidates = [c for c in candidates if c.get('name') not in ["Información General", "Información Acta"]]
        
        total_votes = sum(c.get('votes', 0) for c in candidates)
        if candidates and total_votes > 0:
            sorted_cands = sorted(candidates, key=lambda x: x.get('votes', 0), reverse=True)
            top_candidates = [c.get('name', 'Desconocido') for c in sorted_cands[:3]]
            break
    
    if not top_candidates:
        return None, None
    
    # Construir tabla de departamentos
    dept_rows = []
    totals = {c: {'current': 0, 'projected': 0.0} for c in top_candidates}
    
    for dept_name in sorted(departments.keys()):
        if dept_name in ('raw_data', 'Nacional'):
            continue
            
        dept_data = departments[dept_name]
        actas_pct = dept_data.get('actas_percentage', 0)
        candidates = dept_data.get('candidates', [])
        cand_votes = {c.get('name', 'Desconocido'): c.get('votes', 0) for c in candidates}
        
        row = {'Departamento': dept_name, 'Actas %': actas_pct}
        
        for cand in top_candidates:
            votes = cand_votes.get(cand, 0)
            
            if actas_pct > 0:
                raw_proj = calculate_projection(votes, actas_pct)
                projected = int(round(raw_proj))
                totals[cand]['projected'] += raw_proj
            else:
                projected = votes
                totals[cand]['projected'] += float(votes)
            
            row[f'{cand[:15]} (Actual)'] = votes
            row[f'{cand[:15]} (Proyectado)'] = projected
            
            totals[cand]['current'] += votes
        
        dept_rows.append(row)
    
    dept_df = pd.DataFrame(dept_rows)
    
    # Construir fila de totales
    total_row = {'Departamento': 'TOTAL', 'Actas %': ''}
    for cand in top_candidates:
        total_row[f'{cand[:15]} (Actual)'] = totals[cand]['current']
        total_row[f'{cand[:15]} (Proyectado)'] = int(round(totals[cand]['projected']))
    
    return dept_df, total_row

def process_municipality_data(data):
    """Procesar datos de municipios en DataFrames para mostrar."""
    if not data or 'departments' not in data:
        return None, None
    
    departments = data['departments']
    
    # Obtener nombres de candidatos
    top_candidates = []
    for dept_name, dept_data in departments.items():
        if dept_name in ('raw_data', 'Nacional'):
            continue
        candidates = dept_data.get('candidates', [])
        # Filter out non-candidates
        candidates = [c for c in candidates if c.get('name') not in ["Información General", "Información Acta"]]
        
        total_votes = sum(c.get('votes', 0) for c in candidates)
        if candidates and total_votes > 0:
            sorted_cands = sorted(candidates, key=lambda x: x.get('votes', 0), reverse=True)
            top_candidates = [c.get('name', 'Desconocido') for c in sorted_cands[:3]]
            break
    
    if not top_candidates:
        return None, None
        
    mun_rows = []
    totals = {c: {'current': 0, 'projected': 0.0} for c in top_candidates}
    
    for dept_name in sorted(departments.keys()):
        if dept_name in ('raw_data', 'Nacional'):
            continue
            
        dept_data = departments[dept_name]
        municipios = dept_data.get('municipios', {})
        
        if not municipios:
            continue
            
        for mun_name, mun_data in municipios.items():
            actas_pct = mun_data.get('actas_percentage', 0)
            candidates = mun_data.get('candidates', [])
            cand_votes = {c.get('name', 'Desconocido'): c.get('votes', 0) for c in candidates}
            
            row = {
                'Departamento': dept_name,
                'Municipio': mun_name,
                'Actas %': actas_pct
            }
            
            for cand in top_candidates:
                votes = cand_votes.get(cand, 0)
                
                if actas_pct > 0:
                    raw_proj = calculate_projection(votes, actas_pct)
                    projected = int(round(raw_proj))
                    totals[cand]['projected'] += raw_proj
                else:
                    projected = votes
                    totals[cand]['projected'] += float(votes)
                
                row[f'{cand[:15]} (Actual)'] = votes
                row[f'{cand[:15]} (Proyectado)'] = projected
                
                totals[cand]['current'] += votes
        
        mun_rows.append(row)
            
    if not mun_rows:
        return None, None

    mun_df = pd.DataFrame(mun_rows)
    
    # Construir fila de totales
    total_row = {'Departamento': 'TOTAL', 'Municipio': '', 'Actas %': ''}
    for cand in top_candidates:
        total_row[f'{cand[:15]} (Actual)'] = totals[cand]['current']
        total_row[f'{cand[:15]} (Proyectado)'] = int(round(totals[cand]['projected']))
        
    return mun_df, total_row

def format_number(x):
    """Formatear números con comas."""
    if isinstance(x, (int, float)) and not pd.isna(x):
        return f"{int(x):,}"
    return x

def main():
    # Encabezado
    st.title("🗳️ Elecciones Generales Honduras 2025")
    st.subheader("Dashboard de Proyecciones en Tiempo Real")
    
    # Configuración en barra lateral
    st.sidebar.header("⚙️ Configuración")
    auto_refresh = st.sidebar.checkbox("Auto-actualizar", value=True)
    refresh_interval = st.sidebar.slider("Intervalo de actualización (segundos)", 30, 300, REFRESH_INTERVAL, 30)
    
    # Cargar datos
    data = load_cached_data()
    
    if not data:
        st.warning("⚠️ No hay datos disponibles. Por favor ejecuta `python main.py` primero para recolectar datos.")
        st.info("El scraper necesita ejecutarse al menos una vez para llenar el archivo de caché.")
        
        if auto_refresh:
            with st.spinner("Esperando datos... Revisando de nuevo en 10 segundos"):
                time.sleep(10)
                st.rerun()
        return
    
    # Verificar calidad de datos
    data_issues = check_data_quality(data)
    if data_issues:
        st.warning(f"⚠️ Problema de calidad: Los siguientes departamentos tienen 0 votos (pueden necesitar re-scraping): {', '.join(data_issues)}")
    
    # Obtener timestamp
    cached_time = data.get('cached_at', 'Desconocido')
    formatted_time = format_timestamp(cached_time)
    
    # Mostrar tiempo de última actualización
    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    with col1:
        st.success(f"📅 **Última Actualización:** {formatted_time}")
    with col2:
        current_time = datetime.now().strftime("%I:%M:%S %p")
        st.info(f"🕐 **Hora Actual:** {current_time}")
    with col3:
        if st.button("🔄 Recargar", type="secondary", help="Recargar datos del caché"):
            st.rerun()
    with col4:
        if st.button("🔃 Nuevo Scrape", type="primary", help="Solicitar nuevos datos del CNE"):
            trigger_scrape()
            st.toast("✅ ¡Scrape solicitado! El scraper obtendrá nuevos datos en su próximo ciclo.", icon="🔃")
            time.sleep(1)
            st.rerun()
    
    st.divider()
    
    # Procesar datos
    mode = data.get('mode', 'DEPARTAMENTOS')
    
    # Sección de resumen
    st.header(f"📊 Resumen de Proyección Nacional")
    
    if mode == 'BOTH':
        st.info("Mostrando proyecciones comparativas (Departamental vs Municipal)")
        tab1, tab2 = st.tabs(["🏛️ Proyección por Departamentos", "🏘️ Proyección por Municipios"])
        
        with tab1:
            st.caption("Proyección calculada sumando las proyecciones individuales de cada DEPARTAMENTO.")
            summary_dept = generate_projection_summary(data, 'DEPARTAMENTOS')
            display_summary_metrics(summary_dept, key_prefix="dept")
            
        with tab2:
            st.caption("Proyección calculada sumando las proyecciones individuales de cada MUNICIPIO (Más preciso).")
            summary_mun = generate_projection_summary(data, 'MUNICIPIOS')
            display_summary_metrics(summary_mun, key_prefix="mun")
            
    else:
        # Modo simple (solo uno)
        summary_data = generate_projection_summary(data, mode)
        display_summary_metrics(summary_data, key_prefix="simple")
    
    st.divider()
    
    # Mostrar tablas según el modo
    show_dept = mode in ["DEPARTAMENTOS", "BOTH"]
    show_mun = mode in ["MUNICIPIOS", "BOTH"]
    
    if show_dept:
        st.header("🗺️ Resultados por Departamento")
        dept_df, dept_total = process_department_data(data)
        
        if dept_df is not None and not dept_df.empty:
            # Formatear el dataframe para mostrar
            display_df = dept_df.copy()
            
            # Formatear columna de Actas %
            display_df['Actas %'] = display_df['Actas %'].apply(lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x)
            
            # Formatear columnas de votos
            for col in display_df.columns:
                if 'Actual' in col or 'Proyectado' in col:
                    display_df[col] = display_df[col].apply(format_number)
            
            st.dataframe(
                display_df,
                hide_index=True,
                height=600
            )
            
            # Mostrar totales
            st.subheader("📊 Totales (Departamentos)")
            total_df = pd.DataFrame([dept_total])
            for col in total_df.columns:
                if 'Actual' in col or 'Proyectado' in col:
                    total_df[col] = total_df[col].apply(format_number)
            
            st.dataframe(total_df, hide_index=True)
            
    if show_mun:
        if show_dept: st.divider()
        st.header("🏙️ Resultados por Municipio")
        mun_df, mun_total = process_municipality_data(data)
        
        if mun_df is not None and not mun_df.empty:
            # Formatear el dataframe para mostrar
            display_mun_df = mun_df.copy()
            
            # Formatear columna de Actas %
            display_mun_df['Actas %'] = display_mun_df['Actas %'].apply(lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x)
            
            # Formatear columnas de votos
            for col in display_mun_df.columns:
                if 'Actual' in col or 'Proyectado' in col:
                    display_mun_df[col] = display_mun_df[col].apply(format_number)
            
            st.dataframe(
                display_mun_df,
                hide_index=True,
                height=600
            )
            
            # Mostrar totales
            st.subheader("📊 Totales (Municipios)")
            total_mun_df = pd.DataFrame([mun_total])
            for col in total_mun_df.columns:
                if 'Actual' in col or 'Proyectado' in col:
                    total_mun_df[col] = total_mun_df[col].apply(format_number)
            
            st.dataframe(total_mun_df, hide_index=True)
    
    st.divider()
    
    # Pie de página
    st.caption("**Fórmula de Proyección:** Votos Proyectados = (Votos Actuales × 100) / Porcentaje de Actas")
    st.caption("**Fuente de Datos:** CNE Honduras - https://resultadosgenerales2025.cne.hn/")
    st.caption("**Nota:** Ejecuta `python main.py` en una terminal separada para mantener los datos actualizados.")
    
    # Auto-actualización con cuenta regresiva
    if auto_refresh:
        st.sidebar.divider()
        st.sidebar.subheader("🔄 Estado de Auto-Actualización")
        
        # Crear placeholder para cuenta regresiva
        countdown_placeholder = st.sidebar.empty()
        progress_placeholder = st.sidebar.empty()
        
        for remaining in range(refresh_interval, 0, -1):
            # Verificar nuevos datos cada segundo
            if check_for_new_data():
                countdown_placeholder.success("🔄 ¡Nuevos datos disponibles! Recargando...")
                time.sleep(0.5)
                st.rerun()
            
            countdown_placeholder.info(f"⏱️ Actualizando en **{remaining}** segundos...")
            progress_placeholder.progress((refresh_interval - remaining) / refresh_interval)
            time.sleep(1)
        
        countdown_placeholder.success("🔄 Actualizando datos ahora...")
        time.sleep(0.5)
        st.rerun()

if __name__ == "__main__":
    main()
