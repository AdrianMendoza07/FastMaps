"""
Script de preparación de datos (ejecutar UNA sola vez).

Acciones:
  1. Lee el CSV de accidentalidad y guarda las ubicaciones en caché.
  2. Descarga la red vial de Barranquilla desde OpenStreetMap (OSMnx).
  3. Proyecta los accidentes sobre el grafo usando nombres de calles (sin API externa).
  4. Muestra estadísticas del grafo resultante.

Uso:
    python setup_data.py [--top 500] [--csv Accidentalidad_en_Barranquilla_20261116.csv]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.loader import load_accidents, top_locations
from src.graph import load_city_graph, overlay_accidents, add_safety_weights, graph_stats

ACCIDENTS_CACHE = Path('cache') / 'accident_locations.json'


def main():
    parser = argparse.ArgumentParser(description='Preparar datos de fast-maps')
    parser.add_argument('--csv', default='Accidentalidad_en_Barranquilla_20261116.csv')
    parser.add_argument('--top', type=int, default=500,
                        help='Ubicaciones más peligrosas a incluir (default: 500)')
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f'[ERROR] No se encontró: {csv_path}')
        sys.exit(1)

    # 1. Cargar y agrupar accidentes
    print('\n=== 1. Cargando datos de accidentalidad ===')
    accidents = load_accidents(csv_path)
    print(f'  Total ubicaciones únicas: {len(accidents)}')

    top = top_locations(accidents, n=args.top)
    print(f'  Usando top {len(top)} ubicaciones más peligrosas')

    ACCIDENTS_CACHE.parent.mkdir(exist_ok=True)
    with open(ACCIDENTS_CACHE, 'w', encoding='utf-8') as f:
        json.dump(top, f, ensure_ascii=False, indent=2)
    print(f'  Guardado en: {ACCIDENTS_CACHE}')

    # 2. Descargar red vial
    print('\n=== 2. Descargando red vial de Barranquilla ===')
    G = load_city_graph(verbose=True)

    # 3. Proyectar accidentes (sin Nominatim — usa nombres de calles del grafo)
    print('\n=== 3. Proyectando accidentes sobre el grafo ===')
    G = overlay_accidents(G, top, verbose=True)

    # 4. Pesos de seguridad
    print('\n=== 4. Calculando pesos de seguridad (λ=150) ===')
    G = add_safety_weights(G, lambda_safety=150.0)

    stats = graph_stats(G)
    print('\n=== Resumen del grafo ===')
    for k, v in stats.items():
        print(f'  {k}: {v}')

    print('\n✓ Configuración completa. Ahora puede ejecutar: python main.py')


if __name__ == '__main__':
    main()
