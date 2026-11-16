"""
Fast-Maps: Enrutamiento seguro en Barranquilla basado en siniestros viales.

Uso:
    python main.py                   # inicia el servidor y abre el mapa
    python main.py --port 9000       # puerto personalizado
    python main.py --lambda 200      # mayor valor = más seguro, más largo
"""

import argparse
import http.server
import json
import socket
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.loader import load_accidents, top_locations
from src.graph import load_city_graph, overlay_accidents, add_safety_weights
from src.routing import fastest_route, safest_route, compare_routes
from src.interactive import build_interactive_html

CSV_PATH = Path('Accidentalidad_en_Barranquilla_20261116.csv')
ACCIDENTS_CACHE = Path('cache') / 'accident_locations.json'


def _load_accident_data() -> dict:
    if ACCIDENTS_CACHE.exists():
        with open(ACCIDENTS_CACHE, encoding='utf-8') as f:
            return json.load(f)
    if not CSV_PATH.exists():
        print('[ERROR] No se encontró el CSV. Ejecute primero: python setup_data.py')
        sys.exit(1)
    accidents = load_accidents(CSV_PATH)
    return top_locations(accidents, n=500)


def _build_graph(lambda_safety: float):
    print('[main] Cargando grafo vial...')
    G = load_city_graph(verbose=True)
    print('[main] Superponiendo datos de accidentes...')
    accident_data = _load_accident_data()
    G = overlay_accidents(G, accident_data, verbose=True)
    G = add_safety_weights(G, lambda_safety=lambda_safety)
    return G


def _make_handler(G, lambda_safety: float):
    """Crea el handler HTTP con el grafo precargado."""

    # Generar HTML interactivo una sola vez
    print('[main] Generando mapa interactivo...')
    _html = build_interactive_html(G).encode('utf-8')
    print('[main] ✓ Listo')

    class _Handler(http.server.BaseHTTPRequestHandler):

        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(_html))
            self.end_headers()
            self.wfile.write(_html)

        def do_POST(self):
            if self.path != '/api/route':
                self.send_response(404)
                self.end_headers()
                return

            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))

            try:
                fast = fastest_route(
                    G,
                    body['orig_lat'], body['orig_lon'],
                    body['dest_lat'], body['dest_lon'],
                )
                safe = safest_route(
                    G,
                    body['orig_lat'], body['orig_lon'],
                    body['dest_lat'], body['dest_lon'],
                )
            except Exception as e:
                resp = json.dumps({'error': str(e)}).encode('utf-8')
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', len(resp))
                self.end_headers()
                self.wfile.write(resp)
                return

            fast_coords = [[G.nodes[n]['y'], G.nodes[n]['x']] for n in fast.nodes]
            safe_coords = [[G.nodes[n]['y'], G.nodes[n]['x']] for n in safe.nodes]

            result = {
                'fast_path': fast_coords,
                'safe_path': safe_coords,
                'stats': compare_routes(fast, safe),
            }
            resp = json.dumps(result).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(resp))
            self.end_headers()
            self.wfile.write(resp)

        def log_message(self, *args):
            pass  # silenciar logs del servidor

    return _Handler


def _find_free_port(start: int = 8765) -> int:
    for port in range(start, start + 10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('localhost', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f'No hay puerto disponible entre {start} y {start + 9}')


def main():
    parser = argparse.ArgumentParser(description='Fast-Maps — servidor de enrutamiento seguro')
    parser.add_argument('--port',   type=int,   default=8765, help='Puerto de inicio (default: 8765)')
    parser.add_argument('--lambda', dest='lam', type=float, default=150.0,
                        help='Factor de penalización por accidentes (default: 150)')
    args = parser.parse_args()

    G = _build_graph(args.lam)

    Handler = _make_handler(G, args.lam)
    port = _find_free_port(args.port)
    httpd = http.server.HTTPServer(('localhost', port), Handler)

    url = f'http://localhost:{port}'
    print(f'\n[main] Servidor corriendo en {url}')
    print('[main] Presiona Ctrl+C para detenerlo\n')
    webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n[main] Servidor detenido.')
    finally:
        httpd.shutdown()


if __name__ == '__main__':
    main()
