# Sistema de Proyección - Elecciones Honduras 2025

Obtiene resultados en tiempo real de [CNE Honduras](https://resultadosgenerales2025.cne.hn) y proyecta el conteo final de votos basado en las actas procesadas por departamento. Gracias a Claude Opus 4.5 por haber hecho el 95% del trabajo.  

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

1. Al ejecutar, se abrirá el navegador automáticamente
2. **Importante:** Recarga la página en el navegador hasta que muestre los datos de las elecciones
3. Cuando la página cargue correctamente, presiona **ENTER** en la terminal para iniciar el scraping
4. El dashboard se abre automáticamente en http://localhost:8501

## Estructura del Proyecto

```
proyeccion_elecciones_hn_2025/
├── main.py             # Scraper - conecta a Edge/Chrome y recolecta datos
├── app.py              # Dashboard de Streamlit
├── requirements.txt
├── setup.bat           # Configuración para Windows
├── run.bat             # Ejecutar en Windows
├── setup.sh            # Configuración para Mac/Linux
├── run.sh              # Ejecutar en Mac/Linux
└── last_results.json   # Resultados en caché (auto-generado)
```

## Solución de Problemas

- **¿No hay datos en el dashboard?** Ejecuta `python main.py` primero
- **¿El navegador abre una página incorrecta?** Elimina la carpeta `browser_scraper_profile/` y reintenta
- **¿No puede conectar al navegador?** Cierra todas las ventanas del navegador y reintenta
