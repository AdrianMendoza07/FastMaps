"""
Algoritmos de enrutamiento sobre el grafo de accidentalidad.

Implementa dos variantes de búsqueda de camino mínimo:
  1. Ruta más corta  → Dijkstra ponderado por distancia (metros).
  2. Ruta más segura → Dijkstra ponderado por safety_weight (distancia × factor_seguridad).

Ambas usan la implementación de NetworkX (Dijkstra clásico) sobre el grafo
descargado desde OpenStreetMap vía OSMnx.
"""

from dataclasses import dataclass

import networkx as nx
import osmnx as ox


@dataclass
class RouteResult:
    nodes: list[int]       # secuencia de nodos del camino
    total_distance: float  # metros
    total_accidents: int   # accidentes acumulados en los nodos del camino
    total_severity: float  # severidad acumulada
    safety_weight: float   # costo de la función de seguridad


def _node_from_coords(G: nx.MultiDiGraph, lat: float, lon: float) -> int:
    """Devuelve el nodo del grafo más cercano a las coordenadas dadas."""
    return ox.nearest_nodes(G, lon, lat)


def _path_metrics(G: nx.MultiDiGraph, path: list[int]) -> tuple[float, int, float, float]:
    """Calcula distancia, accidentes, severidad y safety_weight totales del camino."""
    dist = 0.0
    accidents = 0
    severity = 0.0
    sw = 0.0

    for n in path:
        accidents += G.nodes[n].get('accidents', 0)
        severity += G.nodes[n].get('severity', 0.0)

    for u, v in zip(path[:-1], path[1:]):
        edge_data = min(G[u][v].values(), key=lambda d: d.get('length', float('inf')))
        dist += edge_data.get('length', 0.0)
        sw += edge_data.get('safety_weight', edge_data.get('length', 0.0))

    return dist, accidents, severity, sw


def fastest_route(G: nx.MultiDiGraph, origin_lat: float, origin_lon: float,
                  dest_lat: float, dest_lon: float) -> RouteResult:
    """
    Calcula la ruta más corta (menor distancia en metros) entre dos puntos.
    Usa Dijkstra con peso = 'length'.
    """
    orig_node = _node_from_coords(G, origin_lat, origin_lon)
    dest_node = _node_from_coords(G, dest_lat, dest_lon)

    path = nx.shortest_path(G, orig_node, dest_node, weight='length')
    dist, accidents, severity, sw = _path_metrics(G, path)

    return RouteResult(
        nodes=path,
        total_distance=dist,
        total_accidents=accidents,
        total_severity=severity,
        safety_weight=sw,
    )


def safest_route(G: nx.MultiDiGraph, origin_lat: float, origin_lon: float,
                 dest_lat: float, dest_lon: float) -> RouteResult:
    """
    Calcula la ruta más segura (menor safety_weight) entre dos puntos.
    Usa Dijkstra con peso = 'safety_weight'.
    Requiere que el grafo haya sido procesado con graph.add_safety_weights().
    """
    orig_node = _node_from_coords(G, origin_lat, origin_lon)
    dest_node = _node_from_coords(G, dest_lat, dest_lon)

    path = nx.shortest_path(G, orig_node, dest_node, weight='safety_weight')
    dist, accidents, severity, sw = _path_metrics(G, path)

    return RouteResult(
        nodes=path,
        total_distance=dist,
        total_accidents=accidents,
        total_severity=severity,
        safety_weight=sw,
    )


def compare_routes(fast: RouteResult, safe: RouteResult) -> dict:
    """Genera un resumen comparativo entre la ruta rápida y la segura."""
    return {
        'fast': {
            'distance_km': round(fast.total_distance / 1000, 2),
            'accidents': fast.total_accidents,
            'severity': round(fast.total_severity, 1),
        },
        'safe': {
            'distance_km': round(safe.total_distance / 1000, 2),
            'accidents': safe.total_accidents,
            'severity': round(safe.total_severity, 1),
        },
        'extra_distance_km': round((safe.total_distance - fast.total_distance) / 1000, 2),
        'accidents_avoided': fast.total_accidents - safe.total_accidents,
        'severity_reduction_pct': (
            round((1 - safe.total_severity / max(fast.total_severity, 1)) * 100, 1)
        ),
    }
