import json
import logging
import os
import uuid

import azure.functions as func
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from entra_auth import AuthenticationError, validate_easy_auth_headers
from openai import AzureOpenAI
from request_validation import validate_request_body
from telemetry import Stopwatch, emit_event

# Easy Auth is the network authentication boundary. Requiring a Function key
# here would reject valid Entra bearer tokens before this code can run.
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# 1. Configuración de Azure OpenAI vía Managed Identity
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

# Token Provider con Managed Identity
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)

def get_openai_client():
    if not AZURE_OPENAI_ENDPOINT:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT no esta configurado.")
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version=AZURE_OPENAI_API_VERSION
    )

# 2. Definición Estándar de Herramientas Corporativas (Tools Schema)
CORPORATE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_dax_query",
            "description": "Ejecuta una consulta de solo lectura en DAX (iniciando con EVALUATE) contra el motor VertiPaq en memoria para obtener tablas de datos, rankings o metricas de ventas y cartera.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dax_query": {
                        "type": "string",
                        "description": "La consulta DAX completa iniciando con EVALUATE."
                    },
                    "purpose": {
                        "type": "string",
                        "description": "Breve explicacion de que calcula la consulta para auditoria."
                    }
                },
                "required": ["dax_query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "inject_measure",
            "description": "Inyecta o actualiza formalmente una medida DAX dentro del archivo .pbix abierto en Power BI Desktop utilizando Microsoft TOM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "measure_name": {
                        "type": "string",
                        "description": "Nombre exacto de la medida (ej. 'Cartera_Activable_90D')."
                    },
                    "expression": {
                        "type": "string",
                        "description": "Formula DAX completa con encabezado de documentacion obligatoria."
                    },
                    "format_string": {
                        "type": "string",
                        "description": "Formato numerico (ej. '#,##0.00', '$#,##0', '0.0%')."
                    },
                    "display_folder": {
                        "type": "string",
                        "description": "Carpeta de dominio (ej. '03. Cartera y Cobertura')."
                    },
                    "description": {
                        "type": "string",
                        "description": "Documentacion con • CONTEXTO, • PROPOSITO y • USO PREVISTO."
                    }
                },
                "required": ["measure_name", "expression"]
            }
        }
    }
]

@app.route(route="chat-stream", methods=["POST"])
def chat_stream(req: func.HttpRequest) -> func.HttpResponse:
    request_id = req.headers.get("x-correlation-id") or str(uuid.uuid4())
    logging.info("Recibida peticion en Proxy Backend de Azure. request_id=%s", request_id)

    with Stopwatch() as stopwatch:
        try:
            principal = validate_easy_auth_headers(dict(req.headers))
            logging.info("Solicitud autenticada. request_id=%s", request_id)
            try:
                req_body = req.get_json()
            except ValueError as exc:
                raise ValueError("El cuerpo debe ser JSON valido.") from exc
            messages = validate_request_body(req_body, len(req.get_body()))

            client = get_openai_client()
            params = {
                "model": AZURE_OPENAI_DEPLOYMENT,
                "messages": messages,
                "tools": CORPORATE_TOOLS,
                "tool_choice": "auto",
            }
            response = client.chat.completions.create(**params)
            choice = response.choices[0]
            result_payload = {
                "content": choice.message.content or "",
                "tool_calls": [],
            }
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    result_payload["tool_calls"].append(
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                    )
            emit_event(
                logging.getLogger(__name__),
                event_name="chat_completion",
                request_id=request_id,
                subject=principal["subject"],
                status="SUCCESS",
                duration_ms=stopwatch.duration_ms,
                attributes={"tool_count": len(result_payload["tool_calls"])},
            )
            return func.HttpResponse(
                json.dumps(result_payload),
                status_code=200,
                mimetype="application/json",
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        except AuthenticationError as exc:
            emit_event(
                logging.getLogger(__name__),
                event_name="chat_completion",
                request_id=request_id,
                subject="anonymous",
                status="UNAUTHORIZED",
                duration_ms=stopwatch.duration_ms,
                error_code="AUTHENTICATION_ERROR",
            )
            return func.HttpResponse(
                json.dumps({"error": str(exc), "request_id": request_id}),
                status_code=401,
                mimetype="application/json",
            )
        except ValueError as exc:
            emit_event(
                logging.getLogger(__name__),
                event_name="chat_completion",
                request_id=request_id,
                subject="anonymous",
                status="INVALID_REQUEST",
                duration_ms=stopwatch.duration_ms,
                error_code="VALIDATION_ERROR",
            )
            return func.HttpResponse(
                json.dumps({"error": str(exc), "request_id": request_id}),
                status_code=400,
                mimetype="application/json",
            )
        except Exception:
            logging.exception("Error procesando chat en Proxy. request_id=%s", request_id)
            emit_event(
                logging.getLogger(__name__),
                event_name="chat_completion",
                request_id=request_id,
                subject="anonymous",
                status="ERROR",
                duration_ms=stopwatch.duration_ms,
                error_code="INTERNAL_ERROR",
            )
            return func.HttpResponse(
                json.dumps(
                    {"error": "Error interno procesando la solicitud.", "request_id": request_id}
                ),
                status_code=500,
                mimetype="application/json",
            )
