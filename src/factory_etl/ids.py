"""Generacion determinista de identificadores y hashes del ETL.

- ``run_id``   : UUID aleatorio por corrida completa (no deterministico).
- ``lote_id``  : identificador deterministico de un lote de aterrizaje;
                 permite detectar duplicados sin llamar a Bronze.
- ``sql_hash`` : hash del SQL renderizado; sirve para garantizar que el
                 mismo query con los mismos parametros produce el mismo hash.
- ``payload_hash``: hash del cuerpo crudo de la respuesta de FactorySoft.
- ``row_hash`` : hash de las columnas de negocio de una fila; usado en
                 Silver para detectar cambios sin comparar campo a campo.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable

_UNIT_SEPARATOR = "\x1f"
_NULL_SENTINEL = "\x00NULL\x00"


def new_run_id() -> str:
    """UUID v4 nuevo por corrida."""
    return str(uuid.uuid4())


def sha256_hex(data: bytes | str) -> str:
    """SHA-256 hex; conveniente para tener un solo helper."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sql_hash(sql_rendered: str) -> str:
    """Hash estable del SQL renderizado."""
    return sha256_hex(sql_rendered)


def payload_hash(payload_bytes: bytes) -> str:
    """Hash del payload crudo devuelto por FactorySoft.

    Se calcula sobre los bytes exactos recibidos (antes de cualquier parseo)
    para que dos respuestas byte-identicas produzcan el mismo hash aunque
    tuvieran BOM, orden de claves distinto o espacios en blanco distintos.
    """
    return sha256_hex(payload_bytes)


def batch_id(
    *,
    source_empresa: str,
    query_id: str,
    dt: str,
    payload_hash_hex: str,
) -> str:
    """Identificador deterministico de un lote.

    Formula:

        sha256( source_empresa | query_id | dt | payload_hash )

    Dos corridas con el mismo insumo producen el mismo ``batch_id``; asi el
    ETL puede rechazar duplicados consultando `etl_batches` antes de escribir.
    """
    raw = f"{source_empresa}|{query_id}|{dt}|{payload_hash_hex}"
    return sha256_hex(raw)


def row_hash(values: Iterable[object]) -> str:
    """Hash estable de una fila.

    Usa un separador de unidad ASCII (0x1f) que no puede aparecer en JSON
    escapado ni en payloads legitimos, para minimizar riesgo de colision por
    contenido. Nulos se sustituyen por un centinela distinguible del string
    literal "None".
    """
    parts: list[str] = []
    for value in values:
        if value is None:
            parts.append(_NULL_SENTINEL)
        else:
            parts.append(str(value))
    joined = _UNIT_SEPARATOR.join(parts)
    return sha256_hex(joined)
