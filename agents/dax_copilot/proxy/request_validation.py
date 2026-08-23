from __future__ import annotations

from typing import Any

MAX_BODY_BYTES = 256 * 1024
MAX_MESSAGES = 20
MAX_MESSAGE_CONTENT_CHARS = 32_000
ALLOWED_MESSAGE_ROLES = frozenset({"system", "user", "assistant", "tool"})


def validate_request_body(body: Any, body_size: int) -> list[dict[str, Any]]:
    if body_size > MAX_BODY_BYTES:
        raise ValueError("La solicitud supera el limite de 256 KiB.")
    if not isinstance(body, dict):
        raise ValueError("El cuerpo JSON debe ser un objeto.")

    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("Parametro 'messages' es requerido y debe ser una lista.")
    if len(messages) > MAX_MESSAGES:
        raise ValueError(f"La conversacion no puede superar {MAX_MESSAGES} mensajes.")

    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Cada mensaje debe ser un objeto JSON.")
        if message.get("role") not in ALLOWED_MESSAGE_ROLES:
            raise ValueError("El mensaje contiene un role no permitido.")
        content = message.get("content")
        if isinstance(content, str) and len(content) > MAX_MESSAGE_CONTENT_CHARS:
            raise ValueError("El contenido de un mensaje supera el limite permitido.")

    return messages
