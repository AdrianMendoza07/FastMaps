# Fast-Maps — Enrutamiento seguro en Barranquilla

Proyecto de Matemáticas Discretas que usa **teoría de grafos** para encontrar la ruta más segura entre dos puntos en Barranquilla, minimizando el paso por zonas con alta accidentalidad vial.

## Descripción

El sistema descarga la red vial real de Barranquilla desde OpenStreetMap y superpone los datos de siniestros viales del dataset de la Secretaría de Tránsito. Luego aplica el **algoritmo de Dijkstra** con dos funciones de peso distintas:

| Ruta | Función de peso de arista |
|------|--------------------------|
| Más corta | `distancia (m)` |
| Más segura | `distancia × (1 + λ × densidad_accidentes)` |

El resultado es un mapa HTML interactivo que muestra ambas rutas simultáneamente junto con un mapa de calor de accidentes.

## Estructura del grafo

```
G = (V, E)
V = intersecciones viales donde ocurrieron siniestros
E = segmentos de calle entre intersecciones adyacentes
w(e) = longitud real del segmento en metros
a(v) = número de accidentes acumulados en el nodo v
```

Cada nodo del grafo representa un punto de accidentalidad: se toma la red vial de Barranquilla (nodos = intersecciones) y cada siniestro del dataset se proyecta al nodo más cercano, acumulando el conteo. Así, nodos con alto valor de `a(v)` representan zonas de alta peligrosidad.

## Requisitos

- Python 3.10+
- Conexión a internet (solo en la primera ejecución para descargar la red vial)

## Instalación

```bash
git clone https://github.com/TU_USUARIO/fast-maps.git
cd fast-maps
pip install -r requirements.txt
```

Coloca el archivo CSV del dataset en la raíz del repositorio:
```
fast-maps/
└── Accidentalidad_en_Barranquilla_20261116.csv
```

> El dataset puede descargarse desde [datos.gov.co](https://www.datos.gov.co) buscando *"accidentalidad Barranquilla"*.

## Uso

### Paso 1 — Preparación (solo la primera vez)

```bash
python setup_data.py
```

Esto descarga la red vial de Barranquilla desde OpenStreetMap (~100 MB, tarda 5-10 min) y proyecta los accidentes sobre el grafo. Todo queda guardado en la carpeta `cache/` para ejecuciones futuras.

Opciones:
```bash
python setup_data.py --top 1000   # usar las 1000 ubicaciones más peligrosas (default: 500)
python setup_data.py --csv otro_archivo.csv
```

### Paso 2 — Calcular una ruta

```bash
python main.py --from "Calle 72 Carrera 46, Barranquilla" --to "Calle 93 Carrera 53, Barranquilla"
```

El programa imprime en consola la comparación de rutas y abre automáticamente el mapa en el navegador.

**Sin argumentos** se ejecuta la ruta de demostración predefinida (Calle 72/Cr 46 → Calle 110/Cr 9G):

```bash
python main.py
```

Opciones adicionales:

| Argumento | Descripción | Default |
|-----------|-------------|---------|
| `--from` | Dirección de origen | demo |
| `--to` | Dirección de destino | demo |
| `--lambda` | Factor de penalización por accidentes (mayor = más seguro, más largo) | `150` |
| `--output` | Ruta del archivo HTML generado | `output/mapa_rutas.html` |

### Ejemplo de salida en consola

```
  RUTA MÁS CORTA
    Distancia  : 8.38 km
    Accidentes : 407
    Severidad  : 866.0

  RUTA MÁS SEGURA
    Distancia  : 9.35 km
    Accidentes : 92
    Severidad  : 181.0

  COMPARACIÓN
    Distancia extra     : +0.96 km
    Accidentes evitados : 315
    Reducción de riesgo : 79.1%
```

### Mapa interactivo

El mapa HTML generado incluye capas activables/desactivables:

- 🔴 **Puntos de accidentalidad** — círculos cuyo tamaño y color indican la cantidad y gravedad de accidentes en cada intersección
- 🌡️ **Mapa de calor** — visualización continua de la densidad de accidentes
- 🔵 **Ruta más corta** — trazada en azul
- 🟢 **Ruta más segura** — trazada en verde
- 📊 **Leyenda** — comparativa de distancia, accidentes y reducción de riesgo

## Estructura del proyecto

```
fast-maps/
├── Accidentalidad_en_Barranquilla_20261116.csv  ← dataset (no incluido en git)
├── src/
│   ├── loader.py          Carga y normaliza el CSV
│   ├── street_matcher.py  Mapea direcciones a nodos del grafo por nombre de calle
│   ├── graph.py           Descarga la red vial y superpone accidentes
│   ├── routing.py         Algoritmo de Dijkstra (distancia y seguridad)
│   ├── geocoder.py        Geocodifica origen/destino del usuario (Nominatim)
│   └── visualizer.py      Genera el mapa HTML interactivo con Folium
├── cache/                 Grafo y datos en caché (generado automáticamente)
├── output/                Mapas HTML generados
├── setup_data.py          Script de preparación (ejecutar una vez)
├── main.py                Aplicación principal
└── requirements.txt
```

## Dependencias principales

| Librería | Uso |
|----------|-----|
| [OSMnx](https://osmnx.readthedocs.io) | Descarga la red vial desde OpenStreetMap |
| [NetworkX](https://networkx.org) | Representación del grafo y algoritmo de Dijkstra |
| [Folium](https://python-visualization.github.io/folium) | Mapas interactivos con Leaflet.js |
| [GeoPy](https://geopy.readthedocs.io) | Geocodificación de origen/destino (Nominatim) |
| [Pandas](https://pandas.pydata.org) | Carga y procesamiento del CSV |

## Notas técnicas

- La proyección de accidentes al grafo se realiza **sin geocodificador externo**: se parsea el nombre de la calle del CSV y se busca directamente en los nombres de aristas del grafo OSMnx. Esto hace el proceso rápido y reproducible.
- El parámetro `λ` (lambda) controla el balance entre distancia y seguridad. Con `λ=0` ambas rutas son idénticas; valores mayores priorizan cada vez más la seguridad sobre la distancia.
- El grafo base incluye toda la red vial de Barranquilla (~11,800 nodos, ~33,400 aristas).
