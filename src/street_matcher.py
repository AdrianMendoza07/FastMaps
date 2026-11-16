"""
Mapeo de direcciones del CSV a nodos del grafo OSMnx sin geocodificador externo.

Estrategia: para una dirección como 'CALLE 110 CARRERA 9G', extraemos los
identificadores numéricos/alfanuméricos de cada componente ('110', '9g') y
buscamos nodos del grafo que sean extremo de aristas cuyo nombre contenga
ambos identificadores. El nodo en la intersección de ambos conjuntos es el
punto del accidente en el grafo.
"""

import re
import networkx as nx

_STREET_KEYWORDS = ('CALLE', 'CARRERA', 'AVENIDA', 'DIAGONAL', 'TRANSVERSAL', 'VIA')


def _split_parts(norm_addr: str) -> list[str]:
    """'CALLE 110 CARRERA 9G' → ['CALLE 110', 'CARRERA 9G']"""
    pattern = '|'.join(_STREET_KEYWORDS)
    parts = re.split(rf'(?={pattern})', norm_addr.strip())
    return [p.strip() for p in parts if p.strip()]


def _street_id(part: str) -> str:
    """'CALLE 110' → '110',  'CARRERA 9G' → '9g',  'VIA 40' → '40'"""
    tokens = part.strip().split()
    return tokens[-1].lower() if len(tokens) >= 2 else part.lower()


def build_street_index(G: nx.MultiDiGraph) -> dict[str, set[int]]:
    """
    Construye un índice {token: conjunto_de_nodos} a partir de los nombres de
    aristas del grafo OSMnx.  Un nodo pertenece al conjunto de un token si al
    menos una de sus aristas tiene ese token en su nombre.

    Ejemplo: el token '110' incluirá todos los nodos adyacentes a aristas
    llamadas 'Calle 110', 'Calle 110B', etc.
    """
    index: dict[str, set[int]] = {}

    for u, v, data in G.edges(data=True):
        raw_name = data.get('name')
        if raw_name is None:
            continue
        names: list[str] = raw_name if isinstance(raw_name, list) else [raw_name]

        for name in names:
            for token in name.lower().split():
                index.setdefault(token, set()).add(u)
                index.setdefault(token, set()).add(v)

    return index


def addr_to_node(
    G: nx.MultiDiGraph,
    index: dict[str, set[int]],
    norm_addr: str,
) -> int | None:
    """
    Devuelve el nodo OSMnx que mejor representa la dirección normalizada.

    Para dos componentes ('CALLE 110', 'CARRERA 9G'):
      Nodos(110) ∩ Nodos(9g) → intersección buscada.

    Si no hay intersección exacta, intenta con solo el primer componente.
    Elige el nodo de mayor grado (esquina principal).
    """
    parts = _split_parts(norm_addr)
    if not parts:
        return None

    ids = [_street_id(p) for p in parts]

    # Intersección de los conjuntos de nodos para cada identificador
    if len(ids) >= 2:
        candidates = index.get(ids[0], set()).copy()
        for sid in ids[1:]:
            candidates &= index.get(sid, set())
            if not candidates:
                break

        if candidates:
            return max(candidates, key=lambda n: G.degree(n))

    # Fallback: solo el primer identificador
    fallback = index.get(ids[0], set())
    if fallback:
        return max(fallback, key=lambda n: G.degree(n))

    return None
