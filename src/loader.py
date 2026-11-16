"""
Carga y normalización de datos de accidentalidad.
"""

import re
import pandas as pd
from pathlib import Path

# Tabla de expansión de abreviaturas colombianas
_ABBREV = [
    (r'\bCLLE\b', 'CALLE'), (r'\bCLL\b', 'CALLE'), (r'\bCL\b', 'CALLE'),
    (r'\bCRA\b', 'CARRERA'), (r'\bCTRA\b', 'CARRERA'), (r'\bCRR\b', 'CARRERA'),
    (r'\bCR\b', 'CARRERA'),
    (r'\bAVE\b', 'AVENIDA'), (r'\bAV\b', 'AVENIDA'),
    (r'\bDIAG\b', 'DIAGONAL'),
    (r'\bTRANSV\b', 'TRANSVERSAL'), (r'\bTRANS\b', 'TRANSVERSAL'),
    (r'\bTV\b', 'TRANSVERSAL'),
]


def normalize_address(addr: str) -> str:
    """Expande abreviaturas y limpia la dirección."""
    if not isinstance(addr, str):
        return ''
    s = addr.upper().strip()
    s = re.sub(r'\s+', ' ', s)
    for pattern, repl in _ABBREV:
        s = re.sub(pattern, repl, s)
    # Elimina numeración de casa (ej: "# 25-10")
    s = re.sub(r'#\s*\S.*', '', s).strip()
    return s


def _severity_weight(row_gravity: str) -> tuple[int, int]:
    """Retorna (con_heridos, con_muertos) según GRAVEDAD_ACCIDENTE."""
    g = str(row_gravity).lower()
    return (1 if 'herido' in g else 0, 1 if 'muerto' in g else 0)


def load_accidents(csv_path: str | Path) -> dict:
    """
    Lee el CSV de siniestros viales y agrupa por ubicación normalizada.

    Retorna
    -------
    dict[str, dict]  clave = dirección normalizada
        {
          'count':          int,   # total de accidentes
          'with_injuries':  int,
          'with_deaths':    int,
          'raw_address':    str,   # forma original en el CSV
          'severity':       float  # peso ponderado (daños=1, heridos=3, muertos=10)
        }
    """
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    df.columns = [c.strip() for c in df.columns]

    locations: dict = {}

    for _, row in df.iterrows():
        raw = str(row.get('SITIO_EXACTO_ACCIDENTE', '')).strip()
        norm = normalize_address(raw)
        if not norm:
            continue

        inj, dead = _severity_weight(row.get('GRAVEDAD_ACCIDENTE', ''))

        if norm not in locations:
            locations[norm] = {
                'count': 0,
                'with_injuries': 0,
                'with_deaths': 0,
                'raw_address': raw,
                'severity': 0.0,
            }

        d = locations[norm]
        d['count'] += 1
        d['with_injuries'] += inj
        d['with_deaths'] += dead
        # daños materiales = accidente sin heridos ni muertos → peso 1
        d['severity'] += (
            dead * 10.0 + inj * 3.0 + (1 if not inj and not dead else 0)
        )

    return locations


def top_locations(locations: dict, n: int = 500) -> dict:
    """Devuelve los N sitios con más siniestros."""
    ranked = sorted(locations.items(), key=lambda x: x[1]['severity'], reverse=True)
    return dict(ranked[:n])
