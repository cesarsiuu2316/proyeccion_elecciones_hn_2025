# Sistema de Proyección - Elecciones Honduras 2025

Obtiene resultados en tiempo real de [CNE Honduras](https://resultadosgenerales2025.cne.hn) y proyecta el conteo final de votos basado en las actas procesadas por departamento o municipio.

## Requisitos

- Python 3.8+
- Microsoft Edge (Windows) o Google Chrome (Mac/Linux)

## Instalación y Ejecución

**Windows:**
```
setup.bat   (primera vez)
run.bat
```

**Mac/Linux:**
```
chmod +x setup.sh run.sh
./setup.sh   (primera vez)
./run.sh
```

## Uso

1. Al ejecutar, se abrirá el navegador automáticamente.
2. **Importante:** Recarga la página en el navegador hasta que muestre los datos de las elecciones.
3. Cuando la página cargue correctamente, presiona **ENTER** en la terminal para iniciar el scraping.
4. Selecciona el modo de proyección:
    - **1. Departamentos:** Más rápido. Proyecta basado en el % de actas de cada departamento.
    - **2. Municipios:** Más detallado. Itera por cada municipio de cada departamento.
    - **3. Both (Ambos):** Genera ambas proyecciones para comparación.

## Estructura del Proyecto

```
proyeccion_elecciones_hn_2025/
├── main.py             # Scraper - conecta a Edge/Chrome y recolecta datos
├── analisis.py         # Herramienta de análisis de datos históricos
├── historical_data/    # Carpeta donde se guardan los CSVs de proyección
│   ├── projection_data_per_department.csv
│   └── projection_data_per_municipality.csv
├── requirements.txt
├── setup.bat           # Configuración para Windows
├── run.bat             # Ejecutar en Windows
├── setup.sh            # Configuración para Mac/Linux
├── run.sh              # Ejecutar en Mac/Linux
└── last_results.json   # Resultados en caché (auto-generado)
```

## Notas Importantes sobre la Proyección

### Fórmula de Proyección

El sistema utiliza una proyección lineal basada en el porcentaje de **Actas Correctas** (no solo procesadas). Esto es crucial para la precisión, ya que las actas con inconsistencias no suman votos al conteo actual.

$$
\text{Votos Proyectados} = \sum \left( \frac{\text{Votos Actuales} \times 100}{\% \text{ Actas Correctas}} \right)
$$

**Cómo funciona:**
1.  **Nivel Local:** Para cada departamento (o municipio, según el modo), se calcula cuántos votos tendría un candidato si se mantuviera la tendencia actual hasta llegar al 100% de las actas.
    *   *Ejemplo:* Si un candidato tiene 500 votos con el 10% de actas correctas, la proyección para ese lugar es $500*100 / 10 = 5,000$ votos.
2.  **Nivel Nacional:** Se suman las proyecciones individuales de todas las unidades para obtener el total nacional. Esto es más preciso que proyectar usando solo los totales nacionales, ya que respeta el peso y el avance de cada región individualmente.

### Consideraciones

Las proyecciones generadas por este sistema son estimaciones matemáticas basadas en los datos disponibles en el sitio del CNE. Ten en cuenta lo siguiente:

1.  **Precisión de los Datos del CNE:** La proyección depende totalmente de la exactitud de los datos reportados en la página web.
2.  **Actas con 0 Votos:** En ocasiones, el sistema del CNE puede reportar un porcentaje de actas procesadas, pero algunas de esas actas pueden no tener votos cargados aún (actas en blanco o con errores de transmisión), lo que puede afectar la proyección.
3.  **Inconsistencias:** Las actas marcadas con inconsistencias no se incluyen en el conteo oficial inmediato y, por lo tanto, no son consideradas por este scraper hasta que son resueltas y sumadas al conteo oficial.
4.  **Voto en el Exterior:** Los votos del exterior pueden no estar completamente contabilizados o pueden tener un ritmo de actualización diferente.
5.  **Variabilidad:** Las proyecciones a nivel de Municipio pueden ser más volátiles si el porcentaje de actas es muy bajo.

## Análisis de Datos

Puedes ejecutar `python analisis.py` para ver estadísticas y gráficos de la evolución de la proyección. El script te permitirá elegir entre analizar los datos históricos por departamento o por municipio.
