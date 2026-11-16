"""
Generación del mapa HTML interactivo con selección de origen/destino por click.

El HTML producido incluye:
  - Mapa base OpenStreetMap (Leaflet/Folium)
  - Puntos de accidentalidad como círculos coloreados
  - Mapa de calor (capa desactivable)
  - Panel lateral para seleccionar origen y destino haciendo click
  - Llamada a la API /api/route para calcular las rutas
  - Visualización de ambas rutas sobre el mapa
"""

import networkx as nx
import folium
from folium.plugins import HeatMap

BARRANQUILLA_CENTER = [10.9639, -74.7964]

# MAP_NAME_PLACEHOLDER se reemplaza por Python con el nombre real de la variable Folium.
# Se usa window[MAP_NAME] para evitar ReferenceError si la var aún no existe,
# y se reintenta cada 100 ms hasta que esté disponible.
_INTERACTIVE_JS = """
<script>
(function () {
  'use strict';

  /* Nombre de la variable global del mapa Leaflet generado por Folium.
     MAP_NAME_PLACEHOLDER es sustituido por Python antes de servir el HTML. */
  var MAP_NAME = 'MAP_NAME_PLACEHOLDER';

  /* ── Esperar a que Folium inicialice el mapa ── */
  function init() {
    var theMap = window[MAP_NAME];
    if (!theMap || typeof theMap.on !== 'function') {
      setTimeout(init, 100);
      return;
    }
    setupMap(theMap);
  }

  function setupMap(theMap) {
    var origin = null, dest = null;
    var originMarker = null, destMarker = null;
    var fastLayer  = null, safeLayer = null;
    var step = 0; /* 0=eligiendo origen, 1=eligiendo destino, 2=listo */

    /* Icono verde para el marcador de origen */
    var greenIcon = new L.Icon({
      iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
      shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
      iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34]
    });

    /* ── Panel de control ── */
    var panel = document.createElement('div');
    panel.style.cssText = [
      'position:fixed','top:70px','left:10px','z-index:1000',
      'background:white','padding:14px','border-radius:8px',
      'border:2px solid #555','font-family:Arial,sans-serif',
      'font-size:13px','max-width:240px',
      'box-shadow:3px 3px 8px rgba(0,0,0,.3)'
    ].join(';');
    panel.innerHTML = [
      '<b style="font-size:14px">&#128506; Fast-Maps &mdash; Barranquilla</b>',
      '<hr style="margin:6px 0">',
      '<p id="fm-status" style="margin:0 0 8px">',
        '&#128205; Haz click en el mapa para elegir el <b>origen</b>',
      '</p>',
      '<button id="fm-clear" style="font-size:12px;margin-right:5px;padding:4px 8px;cursor:pointer">Limpiar</button>',
      '<button id="fm-calc" disabled style="font-size:12px;padding:4px 10px;',
        'background:#238b45;color:white;border:none;border-radius:4px;cursor:pointer">',
        'Calcular Ruta</button>',
      '<div id="fm-result" style="display:none;margin-top:10px;font-size:12px;line-height:1.7"></div>'
    ].join('');
    document.body.appendChild(panel);
    L.DomEvent.disableClickPropagation(panel);

    var statusEl = document.getElementById('fm-status');
    var calcBtn  = document.getElementById('fm-calc');
    var clearBtn = document.getElementById('fm-clear');
    var resultEl = document.getElementById('fm-result');

    /* ── Click en el mapa ── */
    theMap.on('click', function (e) {
      if (step === 0) {
        origin = e.latlng;
        if (originMarker) originMarker.remove();
        originMarker = L.marker(e.latlng, {icon: greenIcon})
          .addTo(theMap).bindPopup('<b>Origen</b>').openPopup();
        statusEl.innerHTML = '&#127937; Ahora haz click para elegir el <b>destino</b>';
        step = 1;

      } else if (step === 1) {
        dest = e.latlng;
        if (destMarker) destMarker.remove();
        destMarker = L.marker(e.latlng)
          .addTo(theMap).bindPopup('<b>Destino</b>').openPopup();
        statusEl.innerHTML = '&#9989; Origen y destino seleccionados';
        calcBtn.disabled = false;
        step = 2;
      }
    });

    /* ── Botón Limpiar ── */
    clearBtn.addEventListener('click', function () {
      [originMarker, destMarker, fastLayer, safeLayer].forEach(function (l) {
        if (l) l.remove();
      });
      origin = dest = originMarker = destMarker = fastLayer = safeLayer = null;
      step = 0;
      calcBtn.disabled = true;
      statusEl.innerHTML = '&#128205; Haz click en el mapa para elegir el <b>origen</b>';
      resultEl.style.display = 'none';
    });

    /* ── Botón Calcular Ruta ── */
    calcBtn.addEventListener('click', function () {
      if (!origin || !dest) return;
      calcBtn.disabled = true;
      statusEl.innerHTML = '&#9203; Calculando rutas...';

      fetch('/api/route', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          orig_lat: origin.lat, orig_lon: origin.lng,
          dest_lat: dest.lat,  dest_lon: dest.lng
        })
      })
      .then(function (r) {
        if (!r.ok) return r.json().then(function(e) { throw new Error(e.error || r.statusText); });
        return r.json();
      })
      .then(function (data) {
        if (fastLayer) fastLayer.remove();
        if (safeLayer) safeLayer.remove();

        fastLayer = L.polyline(data.fast_path, {color:'#2171b5', weight:5, opacity:.85})
          .addTo(theMap).bindPopup('Ruta m&#225;s corta');
        safeLayer = L.polyline(data.safe_path, {color:'#238b45', weight:5, opacity:.85})
          .addTo(theMap).bindPopup('Ruta m&#225;s segura');

        var allCoords = data.fast_path.concat(data.safe_path);
        if (allCoords.length > 0) theMap.fitBounds(allCoords, {padding:[30,30]});

        var s = data.stats;
        resultEl.style.display = 'block';
        resultEl.innerHTML =
          '<span style="color:#2171b5">&#9644;</span> <b>M&#225;s corta:</b> ' +
            s.fast.distance_km + ' km &middot; ' + s.fast.accidents + ' acc.<br>' +
          '<span style="color:#238b45">&#9644;</span> <b>M&#225;s segura:</b> ' +
            s.safe.distance_km + ' km &middot; ' + s.safe.accidents + ' acc.<br>' +
          '<hr style="margin:4px 0">' +
          '&#128207; Distancia extra: +' + s.extra_distance_km + ' km<br>' +
          '&#128737; Reducci&#243;n de riesgo: <b>' + s.severity_reduction_pct + '%</b>';

        statusEl.innerHTML = '&#9989; Rutas calculadas';
        calcBtn.disabled = false;
      })
      .catch(function (err) {
        statusEl.innerHTML = '&#10060; Error: ' + err.message;
        calcBtn.disabled = false;
      });
    });
  }

  /* Arrancar: si la página ya cargó, intentar de inmediato; si no, esperar load */
  if (document.readyState === 'complete') {
    init();
  } else {
    window.addEventListener('load', init);
  }

})();
</script>
"""


def _accident_color(severity: float, max_sev: float) -> str:
    ratio = severity / max(max_sev, 1)
    if ratio > 0.6:
        return '#d7191c'
    if ratio > 0.3:
        return '#fdae61'
    return '#1a9641'


def build_interactive_html(G: nx.MultiDiGraph, max_markers: int = 1000) -> str:
    """
    Genera el HTML completo del mapa interactivo con selección por click.

    Parámetros
    ----------
    G             grafo OSMnx con atributos 'accidents' y 'severity' en nodos
    max_markers   número máximo de puntos de accidentalidad a dibujar
    """
    m = folium.Map(location=BARRANQUILLA_CENTER, zoom_start=13, tiles='OpenStreetMap')

    # Capas de accidentalidad
    accident_nodes = [(n, d) for n, d in G.nodes(data=True) if d.get('accidents', 0) > 0]

    if accident_nodes:
        max_sev = max(d.get('severity', 0) for _, d in accident_nodes)

        acc_layer = folium.FeatureGroup(name='Puntos de accidentalidad', show=True)
        top_nodes = sorted(accident_nodes,
                           key=lambda x: x[1].get('severity', 0),
                           reverse=True)[:max_markers]
        for node, data in top_nodes:
            lat, lon = data['y'], data['x']
            cnt  = data['accidents']
            sev  = data.get('severity', cnt)
            color  = _accident_color(sev, max_sev)
            radius = max(4, min(18, int(cnt ** 0.5) * 3))
            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                color=color, fill=True, fill_color=color, fill_opacity=0.6,
                popup=folium.Popup(
                    f'<b>Accidentes:</b> {cnt}<br><b>Severidad:</b> {sev:.0f}',
                    max_width=200
                ),
                tooltip=f'{cnt} accidentes',
            ).add_to(acc_layer)
        acc_layer.add_to(m)

        heat_data = [[d['y'], d['x'], d.get('severity', 1)] for _, d in accident_nodes]
        HeatMap(heat_data, name='Mapa de calor', show=False, radius=15).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    # Renderizar HTML de Folium
    html_str = m.get_root().render()

    # Obtener el nombre exacto de la variable JS que Folium generó para este mapa.
    # m.get_name() devuelve algo como 'map_a1b2c3d4e5f6' que coincide 1:1 con
    # la variable global que aparece en el HTML generado.
    try:
        map_var_name = m.get_name()
    except AttributeError:
        map_var_name = f'map_{m._id}'

    js = _INTERACTIVE_JS.replace('MAP_NAME_PLACEHOLDER', map_var_name)
    html_str = html_str.replace('</body>', js + '\n</body>')

    return html_str
