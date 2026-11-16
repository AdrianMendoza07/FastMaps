"""
Fast-Maps: Enrutamiento seguro en Barranquilla basado en siniestros viales.

Uso:
    python main.py --from "Calle 72 con Carrera 46" --to "Calle 93 con Carrera 53"
    python main.py --from "..." --to "..." --lambda 200 --output mi_ruta.html

Sin argumentos se ejecuta la ruta de demostración predefinida.
"""

import argparse
import http.server
import json
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.loader import load_accidents, top_locations
from src.geocoder import geocode_free_text
from src.graph import load_city_graph, overlay_accidents, add_safety_weights
from src.routing import fastest_route, safest_route, compare_routes
from src.visualizer import build_map

CSV_PATH = Path('Accidentalidad_en_Barranquilla_20261116.csv')
ACCIDENTS_CACHE = Path('cache') / 'accident_locations.json'

DEMO_ORIGIN = 'Calle 72 Carrera 46, Barranquilla'
DEMO_DEST = 'Calle 110 Carrera 9G, Barranquilla'


def _load_accident_data():
    if ACCIDENTS_CACHE.exists():
        with open(ACCIDENTS_CACHE, encoding='utf-8') as f:
            return json.load(f)
    if not CSV_PATH.exists():
        print('[ERROR] No se encontró el CSV. Ejecute primero: python setup_data.py')
        sys.exit(1)
    accidents = load_accidents(CSV_PATH)
    return top_locations(accidents, n=500)


def _serve_map(html_path: Path, port: int = 8765) -> None:
    """Levanta un servidor HTTP local y abre el mapa en el navegador."""
    directory = html_path.parent

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, *args):
            pass  # silenciar logs del servidor

    httpd = http.server.HTTPServer(('localhost', port), _Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    url = f'http://localhost:{port}/{html_path.name}'
    print(f'[main] Mapa disponible en: {url}')
    webbrowser.open(url)
    input('[main] Presione Enter para cerrar el servidor y salir...\n')
    httpd.shutdown()


def run(origin_text: str, dest_text: str, lambda_safety: float, output: str):
    # 1. Geocodificar origen y destino del usuario
    print(f'\n[main] Geocodificando origen: "{origin_text}"')
    orig_lat, orig_lon = geocode_free_text(origin_text)
    if orig_lat is None:
        print('[ERROR] No se pudo geocodificar el origen.')
        sys.exit(1)
    print(f'       → ({orig_lat:.5f}, {orig_lon:.5f})')

    print(f'[main] Geocodificando destino: "{dest_text}"')
    dest_lat, dest_lon = geocode_free_text(dest_text)
    if dest_lat is None:
        print('[ERROR] No se pudo geocodificar el destino.')
        sys.exit(1)
    print(f'       → ({dest_lat:.5f}, {dest_lon:.5f})')

    # 2. Cargar grafo base
    print('\n[main] Cargando grafo vial...')
    G = load_city_graph(verbose=True)

    # 3. Superponer accidentes
    print('[main] Superponiendo datos de accidentes...')
    accident_data = _load_accident_data()
    G = overlay_accidents(G, accident_data, verbose=True)
    G = add_safety_weights(G, lambda_safety=lambda_safety)

    # 4. Calcular rutas
    print('\n[main] Calculando ruta más corta...')
    fast = fastest_route(G, orig_lat, orig_lon, dest_lat, dest_lon)

    print('[main] Calculando ruta más segura...')
    safe = safest_route(G, orig_lat, orig_lon, dest_lat, dest_lon)

    # 5. Resumen
    stats = compare_routes(fast, safe)
    print('\n' + '=' * 50)
    print('  RUTA MÁS CORTA')
    print(f'    Distancia  : {stats["fast"]["distance_km"]} km')
    print(f'    Accidentes : {stats["fast"]["accidents"]}')
    print(f'    Severidad  : {stats["fast"]["severity"]}')
    print('\n  RUTA MÁS SEGURA')
    print(f'    Distancia  : {stats["safe"]["distance_km"]} km')
    print(f'    Accidentes : {stats["safe"]["accidents"]}')
    print(f'    Severidad  : {stats["safe"]["severity"]}')
    print('\n  COMPARACIÓN')
    print(f'    Distancia extra     : +{stats["extra_distance_km"]} km')
    print(f'    Accidentes evitados : {stats["accidents_avoided"]}')
    print(f'    Reducción de riesgo : {stats["severity_reduction_pct"]}%')
    print('=' * 50)

    # 6. Generar mapa
    print(f'\n[main] Generando mapa → {output}')
    out_path = build_map(
        G, fast, safe,
        origin_coords=(orig_lat, orig_lon),
        dest_coords=(dest_lat, dest_lon),
        output_path=output,
    )
    print(f'[main] ✓ Mapa guardado en: {out_path}')

    # Servir el mapa desde un servidor HTTP local para que los tiles carguen correctamente
    _serve_map(out_path)


def main():
    parser = argparse.ArgumentParser(
        description='Fast-Maps: Ruta segura en Barranquilla',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--from', dest='origin', default=DEMO_ORIGIN)
    parser.add_argument('--to', dest='dest', default=DEMO_DEST)
    parser.add_argument('--lambda', dest='lam', type=float, default=150.0)
    parser.add_argument('--output', default='output/mapa_rutas.html')
    args = parser.parse_args()

    run(args.origin, args.dest, args.lam, args.output)


if __name__ == '__main__':
    main()
