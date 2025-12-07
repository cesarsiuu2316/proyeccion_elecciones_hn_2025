#!/usr/bin/env python3
"""
Análisis de Datos Históricos - Elecciones Honduras 2025

Este script analiza los datos históricos recopilados durante el scraping
y genera gráficos de tendencias para visualizar la evolución de los resultados.

Uso:
    python analisis.py              # Genera todos los gráficos
    python analisis.py --stats      # Muestra estadísticas sin gráficos
    python analisis.py --export     # Exporta resumen a CSV
"""

import pandas as pd
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

# Intentar importar matplotlib (opcional para gráficos)
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️  matplotlib no está instalado. Para generar gráficos ejecuta:")
    print("   pip install matplotlib")

HISTORICAL_DIR = "historical_data"
DEPT_FILE = os.path.join(HISTORICAL_DIR, "projection_data_per_department.csv")
MUN_FILE = os.path.join(HISTORICAL_DIR, "projection_data_per_municipality.csv")


def load_historical_data(file_path: str) -> Optional[pd.DataFrame]:
    """Carga los datos históricos desde el CSV especificado."""
    if not os.path.exists(file_path):
        print(f"❌ No se encontró el archivo {file_path}")
        print("   Ejecuta main.py para recopilar datos primero.")
        return None
    
    df = pd.read_csv(file_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def show_statistics(df: pd.DataFrame) -> None:
    """Muestra estadísticas básicas de los datos recopilados."""
    print("\n" + "="*60)
    print("📊 ESTADÍSTICAS DE DATOS HISTÓRICOS")
    print("="*60)
    
    # Información general
    print(f"\n📅 Período de recopilación:")
    print(f"   Inicio: {df['timestamp'].min().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Fin:    {df['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S')}")
    
    duration = df['timestamp'].max() - df['timestamp'].min()
    print(f"   Duración: {duration}")
    
    print(f"\n📈 Total de muestras: {len(df)}")
    
    # Progreso de actas
    print(f"\n📋 Progreso de actas escrutadas:")
    print(f"   Mínimo: {df['avg_actas_pct'].min():.2f}%")
    print(f"   Máximo: {df['avg_actas_pct'].max():.2f}%")
    print(f"   Actual: {df['avg_actas_pct'].iloc[-1]:.2f}%")
    
    # Resultados por candidato
    print("\n🗳️ RESULTADOS ACTUALES (última medición):")
    print("-"*50)
    
    last_row = df.iloc[-1]
    for i in range(1, 4):
        candidato = last_row.get(f'candidato_{i}', '')
        if candidato:
            votos_actual = last_row.get(f'votos_actuales_{i}', 0)
            votos_proy = last_row.get(f'votos_proyectados_{i}', 0)
            porcentaje = last_row.get(f'porcentaje_{i}', 0)
            print(f"   {i}. {candidato}")
            print(f"      Votos actuales:    {int(votos_actual):,}")
            print(f"      Votos proyectados: {int(votos_proy):,}")
            print(f"      Porcentaje:        {porcentaje:.2f}%")
            print()
    
    # Tendencias
    if len(df) >= 2:
        print("📉 TENDENCIAS (cambio desde primera medición):")
        print("-"*50)
        
        first_row = df.iloc[0]
        for i in range(1, 4):
            candidato = last_row.get(f'candidato_{i}', '')
            if candidato:
                pct_inicial = first_row.get(f'porcentaje_{i}', 0)
                pct_final = last_row.get(f'porcentaje_{i}', 0)
                cambio = pct_final - pct_inicial
                emoji = "📈" if cambio > 0 else "📉" if cambio < 0 else "➡️"
                print(f"   {emoji} {candidato}: {cambio:+.2f}%")


def plot_vote_trends(df: pd.DataFrame) -> None:
    """Genera gráfico de tendencia de votos proyectados."""
    if not MATPLOTLIB_AVAILABLE:
        print("❌ matplotlib no disponible para generar gráficos")
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    colors = ['#003893', '#DC143C', '#228B22']  # Azul, Rojo, Verde
    
    for i in range(1, 4):
        candidato = df[f'candidato_{i}'].iloc[-1] if f'candidato_{i}' in df.columns else None
        if candidato:
            ax.plot(df['timestamp'], df[f'votos_proyectados_{i}'], 
                   label=candidato, linewidth=2, color=colors[i-1], marker='o', markersize=3)
    
    ax.set_xlabel('Tiempo', fontsize=12)
    ax.set_ylabel('Votos Proyectados', fontsize=12)
    ax.set_title('Evolución de Votos Proyectados - Elecciones Honduras 2025', fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    # Formatear eje X
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)
    
    # Formatear números en eje Y con separadores de miles
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))
    
    plt.tight_layout()
    plt.savefig('grafico_votos.png', dpi=150)
    print("✅ Gráfico guardado: grafico_votos.png")
    plt.show()


def plot_percentage_trends(df: pd.DataFrame) -> None:
    """Genera gráfico de tendencia de porcentajes."""
    if not MATPLOTLIB_AVAILABLE:
        print("❌ matplotlib no disponible para generar gráficos")
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    colors = ['#003893', '#DC143C', '#228B22']
    
    for i in range(1, 4):
        candidato = df[f'candidato_{i}'].iloc[-1] if f'candidato_{i}' in df.columns else None
        if candidato:
            ax.plot(df['timestamp'], df[f'porcentaje_{i}'], 
                   label=candidato, linewidth=2, color=colors[i-1], marker='o', markersize=3)
    
    ax.set_xlabel('Tiempo', fontsize=12)
    ax.set_ylabel('Porcentaje (%)', fontsize=12)
    ax.set_title('Evolución de Porcentajes - Elecciones Honduras 2025', fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 100)
    
    # Formatear eje X
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig('grafico_porcentajes.png', dpi=150)
    print("✅ Gráfico guardado: grafico_porcentajes.png")
    plt.show()


def plot_actas_progress(df: pd.DataFrame) -> None:
    """Genera gráfico de progreso de actas escrutadas."""
    if not MATPLOTLIB_AVAILABLE:
        print("❌ matplotlib no disponible para generar gráficos")
        return
    
    fig, ax = plt.subplots(figsize=(12, 4))
    
    ax.fill_between(df['timestamp'], df['avg_actas_pct'], alpha=0.3, color='green')
    ax.plot(df['timestamp'], df['avg_actas_pct'], linewidth=2, color='green', marker='o', markersize=3)
    
    ax.set_xlabel('Tiempo', fontsize=12)
    ax.set_ylabel('Porcentaje de Actas (%)', fontsize=12)
    ax.set_title('Progreso de Actas Escrutadas - Elecciones Honduras 2025', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 100)
    
    # Formatear eje X
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig('grafico_actas.png', dpi=150)
    print("✅ Gráfico guardado: grafico_actas.png")
    plt.show()


def plot_combined_dashboard(df: pd.DataFrame) -> None:
    """Genera un dashboard combinado con todos los gráficos."""
    if not MATPLOTLIB_AVAILABLE:
        print("❌ matplotlib no disponible para generar gráficos")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    colors = ['#003893', '#DC143C', '#228B22']
    
    # Gráfico 1: Votos proyectados
    ax1 = axes[0, 0]
    for i in range(1, 4):
        candidato = df[f'candidato_{i}'].iloc[-1] if f'candidato_{i}' in df.columns else None
        if candidato:
            ax1.plot(df['timestamp'], df[f'votos_proyectados_{i}'], 
                    label=candidato, linewidth=2, color=colors[i-1])
    ax1.set_title('Votos Proyectados', fontweight='bold')
    ax1.legend(loc='best', fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))
    
    # Gráfico 2: Porcentajes
    ax2 = axes[0, 1]
    for i in range(1, 4):
        candidato = df[f'candidato_{i}'].iloc[-1] if f'candidato_{i}' in df.columns else None
        if candidato:
            ax2.plot(df['timestamp'], df[f'porcentaje_{i}'], 
                    label=candidato, linewidth=2, color=colors[i-1])
    ax2.set_title('Porcentajes', fontweight='bold')
    ax2.legend(loc='best', fontsize=8)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 100)
    
    # Gráfico 3: Progreso de actas
    ax3 = axes[1, 0]
    ax3.fill_between(df['timestamp'], df['avg_actas_pct'], alpha=0.3, color='green')
    ax3.plot(df['timestamp'], df['avg_actas_pct'], linewidth=2, color='green')
    ax3.set_title('Progreso de Actas Escrutadas', fontweight='bold')
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(0, 100)
    
    # Gráfico 4: Votos actuales
    ax4 = axes[1, 1]
    for i in range(1, 4):
        candidato = df[f'candidato_{i}'].iloc[-1] if f'candidato_{i}' in df.columns else None
        if candidato:
            ax4.plot(df['timestamp'], df[f'votos_actuales_{i}'], 
                    label=candidato, linewidth=2, color=colors[i-1])
    ax4.set_title('Votos Actuales (sin proyección)', fontweight='bold')
    ax4.legend(loc='best', fontsize=8)
    ax4.grid(True, alpha=0.3)
    ax4.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))
    
    # Formatear ejes X
    for ax in axes.flat:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        for label in ax.get_xticklabels():
            label.set_rotation(45)
    
    plt.suptitle('Dashboard Electoral - Honduras 2025', fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('dashboard_electoral.png', dpi=150, bbox_inches='tight')
    print("✅ Dashboard guardado: dashboard_electoral.png")
    plt.show()


def export_summary(df: pd.DataFrame) -> None:
    """Exporta un resumen de los datos a un nuevo CSV."""
    summary_file = f"resumen_electoral_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    # Crear resumen
    summary_data = []
    
    for i in range(1, 4):
        candidato = df[f'candidato_{i}'].iloc[-1] if f'candidato_{i}' in df.columns else None
        if candidato:
            summary_data.append({
                'Candidato': candidato,
                'Votos Actuales': int(df[f'votos_actuales_{i}'].iloc[-1]),
                'Votos Proyectados': int(df[f'votos_proyectados_{i}'].iloc[-1]),
                'Porcentaje': df[f'porcentaje_{i}'].iloc[-1],
                'Porcentaje Inicial': df[f'porcentaje_{i}'].iloc[0],
                'Cambio (%)': df[f'porcentaje_{i}'].iloc[-1] - df[f'porcentaje_{i}'].iloc[0],
                'Muestras': len(df)
            })
    
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(summary_file, index=False, encoding='utf-8')
    print(f"✅ Resumen exportado: {summary_file}")


def main():
    """Función principal del análisis."""
    print("\n" + "="*60)
    print("🗳️  ANÁLISIS ELECTORAL - HONDURAS 2025")
    print("="*60)
    
    # Seleccionar archivo
    print("\nSelecciona los datos a analizar:")
    print("1. Proyección por Departamentos")
    print("2. Proyección por Municipios")
    
    choice = input("Opción (1/2) [Default: 1]: ").strip()
    
    if choice == "2":
        file_path = MUN_FILE
        print(f"📂 Analizando datos de MUNICIPIOS: {file_path}")
    else:
        file_path = DEPT_FILE
        print(f"📂 Analizando datos de DEPARTAMENTOS: {file_path}")
    
    # Cargar datos
    df = load_historical_data(file_path)
    if df is None:
        return
    
    print(f"\n✅ Datos cargados: {len(df)} registros")
    
    # Verificar argumentos de línea de comandos
    if len(sys.argv) > 1:
        if '--stats' in sys.argv:
            show_statistics(df)
            return
        elif '--export' in sys.argv:
            show_statistics(df)
            export_summary(df)
            return
    
    # Mostrar estadísticas
    show_statistics(df)
    
    # Verificar si hay suficientes datos para gráficos
    if len(df) < 2:
        print("\n⚠️  Se necesitan al menos 2 muestras para generar gráficos.")
        print("   Ejecuta main.py varias veces para recopilar más datos.")
        return
    
    # Generar gráficos
    if MATPLOTLIB_AVAILABLE:
        print("\n📊 Generando gráficos...")
        plot_combined_dashboard(df)
        
        print("\n¿Deseas generar gráficos individuales? (s/n): ", end="")
        try:
            respuesta = input().strip().lower()
            if respuesta == 's':
                plot_vote_trends(df)
                plot_percentage_trends(df)
                plot_actas_progress(df)
        except:
            pass
    
    # Preguntar si exportar
    print("\n¿Deseas exportar un resumen a CSV? (s/n): ", end="")
    try:
        respuesta = input().strip().lower()
        if respuesta == 's':
            export_summary(df)
    except:
        pass


if __name__ == "__main__":
    main()
