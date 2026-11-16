"""
Construcción del grafo de accidentalidad sobre la red vial de Barranquilla.

El grafo G = (V, E) se define como:
  V  = intersecciones viales donde se proyectan los siniestros registrados
  E  = segmentos de calle que conectan intersecciones adyacentes
  w(e) = longitud del segmento (metros)
  a(v) = número de siniestros asignados al nodo v

Para el enrutamiento seguro se calcula además:
  ws(e) = w(e) × (1 + λ × (a(u) + a(v)) / 2 / max_a)
donde λ es el parámetro de ponderación de seguridad.
"""

from pathlib import Path

import networkx as nx
import osmnx as ox

from .street_matcher import build_street_index, addr_to_node

GRAPH_CACHE = Path('cache') / 'barranquilla.graphml'
CITY_QUERY = 'Barranquilla, Atlántico, Colombia'


def load_city_graph(verbose: bool = True) -> nx.MultiDiGraph:
    """
    Descarga (o carga desde caché) el grafo vial de Barranquilla usando OSMnx.
    Nodos = intersecciones.  Aristas = segmentos de calle con atributo 'length' (m).
    """
    if GRAPH_CACHE.exists():
        if verbose:
            print('[graph] Cargando grafo desde caché...')
        G = ox.load_graphml(GRAPH_CACHE)
        if verbose:
            print(f'[graph] {G.number_of_nodes()} nodos · {G.number_of_edges()} aristas')
        return G

    if verbose:
        print(f'[graph] Descargando red vial de {CITY_QUERY} (puede tardar varios minutos)...')
    G = ox.graph_from_place(CITY_QUERY, network_type='drive')
    GRAPH_CACHE.parent.mkdir(exist_ok=True)
    ox.save_graphml(G, GRAPH_CACHE)
    if verbose:
        print(f'[graph] Guardado en caché · {G.number_of_nodes()} nodos · {G.number_of_edges()} aristas')
    return G


def overlay_accidents(
    G: nx.MultiDiGraph,
    accident_locations: dict,
    verbose: bool = True,
) -> nx.MultiDiGraph:
    """
    Asigna conteos de accidentes a los nodos del grafo buscando cada dirección
    directamente en los nombres de aristas del grafo OSMnx (sin geocodificador externo).

    Parámetros
    ----------
    G                  grafo OSMnx
    accident_locations dict {norm_addr: {count, severity, ...}}
    """
    nx.set_node_attributes(G, 0, 'accidents')
    nx.set_node_attributes(G, 0.0, 'severity')

    if verbose:
        print('[graph] Construyendo índice de nombres de calles...')
    index = build_street_index(G)
    if verbose:
        print(f'[graph] Índice listo: {len(index)} tokens')

    mapped = 0
    for addr, data in accident_locations.items():
        node = addr_to_node(G, index, addr)
        if node is None:
            continue
        G.nodes[node]['accidents'] += data['count']
        G.nodes[node]['severity'] += data['severity']
        mapped += 1

    if verbose:
        total_acc = sum(d.get('accidents', 0) for _, d in G.nodes(data=True))
        print(f'[graph] {mapped}/{len(accident_locations)} ubicaciones proyectadas · {total_acc} accidentes en el grafo')

    return G


def add_safety_weights(G: nx.MultiDiGraph, lambda_safety: float = 150.0) -> nx.MultiDiGraph:
    """
    Agrega el atributo 'safety_weight' a cada arista:

        safety_weight = length × (1 + λ × media_accidentes_extremos / max_accidentes)

    Un λ mayor prioriza seguridad sobre distancia.
    """
    max_acc = max((d.get('accidents', 0) for _, d in G.nodes(data=True)), default=1)
    max_acc = max(max_acc, 1)

    for u, v, k, data in G.edges(keys=True, data=True):
        length = data.get('length', 1.0)
        u_acc = G.nodes[u].get('accidents', 0)
        v_acc = G.nodes[v].get('accidents', 0)
        avg = (u_acc + v_acc) / 2.0
        G[u][v][k]['safety_weight'] = length * (1.0 + lambda_safety * avg / max_acc)

    return G


def graph_stats(G: nx.MultiDiGraph) -> dict:
    accident_nodes = [n for n, d in G.nodes(data=True) if d.get('accidents', 0) > 0]
    total_accidents = sum(d.get('accidents', 0) for _, d in G.nodes(data=True))
    return {
        'nodes_total': G.number_of_nodes(),
        'edges_total': G.number_of_edges(),
        'nodes_with_accidents': len(accident_nodes),
        'total_accidents_mapped': total_accidents,
        'avg_accidents_per_node': round(total_accidents / max(len(accident_nodes), 1), 1),
    }
