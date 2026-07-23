"""Catalogo versionado de consultas hacia FactorySoft.

Este subpaquete contiene:

- ``models``: enums y ``QueryDefinition`` (dataclass inmutable).
- ``catalog``: registro de todas las consultas disponibles.
- ``renderer``: sustitucion segura de parametros SQL.
- ``masters/*.sql``: SQL de tablas maestras (una por archivo).
- ``transactions/*.sql``: SQL de tablas transaccionales (vacio en Fase 1).
- ``schemas/*.json``: contrato de columnas por entidad.

Regla de oro: **el SQL nunca se construye por concatenacion**. Todo
parametro pasa por ``renderer.render`` que valida tipo, dominio y
prohibe contenido peligroso.
"""

from __future__ import annotations
