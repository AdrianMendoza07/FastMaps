"""
Geocodificación de direcciones colombianas con caché en disco.
Usa Nominatim (OpenStreetMap) con límite de 1 req/s según sus términos de uso.
"""

import json
import re
import time
from pathlib import Path

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

CACHE_PATH = Path('cache') / 'geocoded.json'
_CITY_SUFFIX = ', Barranquilla, Atlántico, Colombia'

_geolocator = Nominatim(user_agent='fast-maps-barranquilla/1.0', timeout=10)
_geocode_raw = RateLimiter(_geolocator.geocode, min_delay_seconds=1.1)


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        with open(CACHE_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(exist_ok=True)
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _norm_to_query(norm_addr: str) -> str:
    """
    Convierte una dirección normalizada al formato de consulta para Nominatim.
    Ej: 'CALLE 110 CARRERA 9G'  →  'Calle 110 & Carrera 9G, Barranquilla, ...'
    """
    # Detectar dos componentes viales
    parts = re.split(r'(?=CARRERA|CALLE|AVENIDA|DIAGONAL|TRANSVERSAL|VIA)', norm_addr.strip())
    parts = [p.strip() for p in parts if p.strip()]

    def title_part(p: str) -> str:
        tokens = p.split()
        return ' '.join(t.capitalize() if t.isalpha() else t for t in tokens)

    if len(parts) >= 2:
        return f'{title_part(parts[0])} & {title_part(parts[1])}{_CITY_SUFFIX}'
    return f'{title_part(parts[0])}{_CITY_SUFFIX}' if parts else norm_addr + _CITY_SUFFIX


def geocode_address(address: str, cache: dict | None = None) -> tuple[float | None, float | None]:
    """
    Geocodifica una dirección y devuelve (lat, lon).
    Usa caché en memoria si se pasa; de lo contrario carga y guarda en disco.
    """
    own_cache = cache is None
    if own_cache:
        cache = _load_cache()

    if address in cache:
        entry = cache[address]
        return entry.get('lat'), entry.get('lon')

    query = _norm_to_query(address)
    try:
        location = _geocode_raw(query)
        if location:
            lat, lon = location.latitude, location.longitude
        else:
            lat, lon = None, None
    except Exception:
        lat, lon = None, None

    cache[address] = {'lat': lat, 'lon': lon, 'query': query}

    if own_cache:
        _save_cache(cache)

    return lat, lon


def geocode_batch(addresses: list[str], verbose: bool = True) -> dict:
    """
    Geocodifica una lista de direcciones y devuelve un dict {address: (lat, lon)}.
    Guarda la caché periódicamente.
    """
    cache = _load_cache()
    results = {}
    pending = [a for a in addresses if a not in cache]

    if verbose:
        print(f'[geocoder] {len(cache)} en caché · {len(pending)} por geocodificar')

    for i, addr in enumerate(pending, 1):
        lat, lon = geocode_address(addr, cache)
        results[addr] = (lat, lon)
        if verbose and i % 50 == 0:
            coord_str = f'({lat:.4f}, {lon:.4f})' if lat is not None else '(sin resultado)'
            print(f'  → {i}/{len(pending)} {coord_str} para "{addr}"')
        if i % 100 == 0:
            _save_cache(cache)

    # Guardar caché final
    _save_cache(cache)

    # Incluir los que ya estaban en caché
    for addr in addresses:
        if addr not in results:
            entry = cache.get(addr, {})
            results[addr] = (entry.get('lat'), entry.get('lon'))

    return results


def geocode_free_text(text: str) -> tuple[float | None, float | None]:
    """Geocodifica texto libre (para el origen/destino del usuario)."""
    if _CITY_SUFFIX.lower() not in text.lower():
        text = text + _CITY_SUFFIX
    try:
        location = _geocode_raw(text)
        if location:
            return location.latitude, location.longitude
    except Exception:
        pass
    return None, None
