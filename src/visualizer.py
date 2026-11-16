"""
Generación del mapa interactivo con Folium.

Capas producidas:
  - Mapa base (OpenStreetMap)
  - Círculos de accidentes (tamaño ∝ cantidad, color ∝ severidad)
  - Ruta más corta (azul)
  - Ruta más segura (verde)
  - Marcadores de origen y destino
  - Leyenda y resumen de métricas
"""

from pathlib import Path

import folium
import networkx as nx
import osmnx as ox
from folium.plugins import HeatMap

from .routing import RouteResult, compare_routes

BARRANQUILLA_CENTER = [10.9639, -74.7964]


def _node_latlng(G: nx.MultiDiGraph, node: int) -> list[float]:
    data = G.nodes[node]
    return [data['y'], data['x']]


def _path_coords(G: nx.MultiDiGraph, path: list[int]) -> list[list[float]]:
    return [_node_latlng(G, n) for n in path]


def _accident_color(severity: float, max_sev: float) -> str:
    ratio = severity / max(max_sev, 1)
    if ratio > 0.6:
        return '#d7191c'   # rojo — muy peligroso
    if ratio > 0.3:
        return '#fdae61'   # naranja
    return '#1a9641'       # verde — relativamente seguro


def _make_legend(stats: dict) -> str:
    fast = stats['fast']
    safe = stats['safe']
    return f"""
    <div style="
        position: fixed; bottom: 30px; left: 30px; z-index: 1000;
        background: white; padding: 14px; border-radius: 8px;
        border: 2px solid #333; font-family: Arial, sans-serif; font-size: 13px;
        box-shadow: 3px 3px 8px rgba(0,0,0,0.3); max-width: 280px;">
      <b style="font-size:14px;">🗺️ Rutas — Barranquilla</b><hr style="margin:6px 0">
      <span style="color:#2171b5;">&#9644;</span>
      <b>Ruta más corta</b><br>
      &nbsp;&nbsp;Distancia: {fast['distance_km']} km<br>
      &nbsp;&nbsp;Accidentes en ruta: {fast['accidents']}<br>
      &nbsp;&nbsp;Severidad: {fast['severity']}<br><br>
      <span style="color:#238b45;">&#9644;</span>
      <b>Ruta más segura</b><br>
      &nbsp;&nbsp;Distancia: {safe['distance_km']} km<br>
      &nbsp;&nbsp;Accidentes en ruta: {safe['accidents']}<br>
      &nbsp;&nbsp;Severidad: {safe['severity']}<br><hr style="margin:6px 0">
      <small>
        Distancia extra: +{stats['extra_distance_km']} km<br>
        Accidentes evitados: {stats['accidents_avoided']}<br>
        Reducción de riesgo: {stats['severity_reduction_pct']}%
      </small>
    </div>
    """


def build_map(
    G: nx.MultiDiGraph,
    fast: RouteResult,
    safe: RouteResult,
    origin_coords: tuple[float, float],
    dest_coords: tuple[float, float],
    output_path: str | Path = 'output/mapa_rutas.html',
    show_heatmap: bool = True,
    max_accident_nodes: int = 1000,
) -> Path:
    """
    Genera el mapa interactivo HTML con ambas rutas superpuestas.

    Parámetros
    ----------
    G              grafo OSMnx con atributos 'accidents' y 'severity'
    fast           resultado de la ruta más corta
    safe           resultado de la ruta más segura
    origin_coords  (lat, lon) del origen
    dest_coords    (lat, lon) del destino
    output_path    ruta del archivo HTML de salida
    """
    m = folium.Map(location=BARRANQUILLA_CENTER, zoom_start=13, tiles='OpenStreetMap')

    # --- Capa de accidentes (círculos) -----------------------------------------
    accident_nodes = [(n, d) for n, d in G.nodes(data=True) if d.get('accidents', 0) > 0]
    if accident_nodes:
        max_sev = max(d.get('severity', 0) for _, d in accident_nodes)

        acc_layer = folium.FeatureGroup(name='Puntos de accidentalidad', show=True)
        # Limitar para no sobrecargar el mapa
        for node, data in sorted(accident_nodes, key=lambda x: x[1].get('severity', 0), reverse=True)[:max_accident_nodes]:
            lat, lon = data['y'], data['x']
            cnt = data['accidents']
            sev = data.get('severity', cnt)
            color = _accident_color(sev, max_sev)
            radius = max(4, min(18, int(cnt ** 0.5) * 3))
            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.6,
                popup=folium.Popup(
                    f'<b>Accidentes:</b> {cnt}<br><b>Severidad:</b> {sev:.0f}',
                    max_width=200
                ),
                tooltip=f'{cnt} accidentes',
            ).add_to(acc_layer)
        acc_layer.add_to(m)

        # Mapa de calor (opcional)
        if show_heatmap:
            heat_data = [
                [d['y'], d['x'], d.get('severity', 1)]
                for _, d in accident_nodes
            ]
            HeatMap(heat_data, name='Mapa de calor', show=False, radius=15).add_to(m)

    # --- Ruta más corta (azul) ------------------------------------------------
    fast_coords = _path_coords(G, fast.nodes)
    folium.PolyLine(
        fast_coords,
        color='#2171b5',
        weight=5,
        opacity=0.85,
        tooltip='Ruta más corta',
    ).add_to(folium.FeatureGroup(name='Ruta más corta', show=True).add_to(m))

    # --- Ruta más segura (verde) -----------------------------------------------
    safe_coords = _path_coords(G, safe.nodes)
    folium.PolyLine(
        safe_coords,
        color='#238b45',
        weight=5,
        opacity=0.85,
        tooltip='Ruta más segura',
    ).add_to(folium.FeatureGroup(name='Ruta más segura', show=True).add_to(m))

    # --- Marcadores de origen y destino ----------------------------------------
    folium.Marker(
        location=list(origin_coords),
        popup='<b>Origen</b>',
        tooltip='Origen',
        icon=folium.Icon(color='green', icon='play', prefix='fa'),
    ).add_to(m)

    folium.Marker(
        location=list(dest_coords),
        popup='<b>Destino</b>',
        tooltip='Destino',
        icon=folium.Icon(color='red', icon='flag', prefix='fa'),
    ).add_to(m)

    # --- Leyenda ---------------------------------------------------------------
    stats = compare_routes(fast, safe)
    m.get_root().html.add_child(folium.Element(_make_legend(stats)))

    # Control de capas
    folium.LayerControl(collapsed=False).add_to(m)

    # Guardar
    output_path = Path(output_path)
    output_path.parent.mkdir(exist_ok=True)
    m.save(str(output_path))
    return output_path
