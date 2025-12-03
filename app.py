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
        return None, None, None
    
    departments = data['departments']
    
    # Obtener nombres de candidatos del primer departamento con votos
    top_candidates = []
    for dept_name, dept_data in departments.items():
        if dept_name in ('raw_data', 'Nacional'):
            continue
        candidates = dept_data.get('candidates', [])
        total_votes = sum(c.get('votes', 0) for c in candidates)
        if candidates and total_votes > 0:
            sorted_cands = sorted(candidates, key=lambda x: x.get('votes', 0), reverse=True)
            top_candidates = [c['name'] for c in sorted_cands[:3]]
            break
    
    if not top_candidates:
        return None, None, None
    
    # Construir tabla de departamentos
    dept_rows = []
    totals = {c: {'current': 0, 'projected': 0} for c in top_candidates}
    
    for dept_name in sorted(departments.keys()):
        if dept_name in ('raw_data', 'Nacional'):
            continue
            
        dept_data = departments[dept_name]
        actas_pct = dept_data.get('actas_percentage', 0)
        candidates = dept_data.get('candidates', [])
        cand_votes = {c['name']: c['votes'] for c in candidates}
        
        row = {'Departamento': dept_name, 'Actas %': actas_pct}
        
        for cand in top_candidates:
            votes = cand_votes.get(cand, 0)
            projected = int(calculate_projection(votes, actas_pct)) if actas_pct > 0 else votes
            
            row[f'{cand[:15]} (Actual)'] = votes
            row[f'{cand[:15]} (Proyectado)'] = projected
            
            totals[cand]['current'] += votes
            totals[cand]['projected'] += projected
        
        dept_rows.append(row)
    
    dept_df = pd.DataFrame(dept_rows)
    
    # Construir fila de totales
    total_row = {'Departamento': 'TOTAL', 'Actas %': ''}
    for cand in top_candidates:
        total_row[f'{cand[:15]} (Actual)'] = totals[cand]['current']
        total_row[f'{cand[:15]} (Proyectado)'] = totals[cand]['projected']
    
    # Construir DataFrame de resumen
    total_projected = sum(t['projected'] for t in totals.values())
    total_current = sum(t['current'] for t in totals.values())
    
    summary_rows = []
    for cand in top_candidates:
        curr_pct = (totals[cand]['current'] / total_current * 100) if total_current > 0 else 0
        proj_pct = (totals[cand]['projected'] / total_projected * 100) if total_projected > 0 else 0
        summary_rows.append({
            'Candidato': cand,
            'Votos Actuales': totals[cand]['current'],
            '% Actual': curr_pct,
            'Votos Proyectados': totals[cand]['projected'],
            '% Proyectado': proj_pct
        })
    
    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df.sort_values('Votos Proyectados', ascending=False).reset_index(drop=True)
    summary_df.index = summary_df.index + 1
    
    return dept_df, total_row, summary_df

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
    dept_df, total_row, summary_df = process_department_data(data)
    
    if summary_df is None:
        st.error("No se pudieron procesar los datos electorales.")
        return
    
    # Sección de resumen
    st.header("📊 Resumen de Proyección Nacional")
    
    # Crear tarjetas de métricas para el top 3
    cols = st.columns(len(summary_df))
    colors = ['🥇', '🥈', '🥉']
    
    for i, (idx, row) in enumerate(summary_df.iterrows()):
        with cols[i]:
            medal = colors[i] if i < 3 else '📊'
            st.metric(
                label=f"{medal} {row['Candidato'][:20]}",
                value=f"{row['% Proyectado']:.2f}%",
                delta=f"{row['Votos Proyectados']:,.0f} votos proyectados"
            )
            st.caption(f"Actual: {row['Votos Actuales']:,.0f} ({row['% Actual']:.2f}%)")
    
    st.divider()
    
    # Desglose por departamento
    st.header("🗺️ Resultados por Departamento")
    
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
        st.subheader("📊 Totales")
        total_df = pd.DataFrame([total_row])
        for col in total_df.columns:
            if 'Actual' in col or 'Proyectado' in col:
                total_df[col] = total_df[col].apply(format_number)
        
        st.dataframe(total_df, hide_index=True)
    
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
