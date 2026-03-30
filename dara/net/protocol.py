"""
Contrato de aplicação: tipos de mensagem + JSON.

Fluxo mental: cliente e servidor trocam dicts com chave "type" igual a um
MessageType.value. serialize/deserialize são o passo final antes/depois dos bytes
no socket (TCP acrescenta '\\n' por mensagem em transport/tcp.py).
"""
import json
from enum import Enum
from typing import Any


class MessageType(str, Enum):
    # str + Enum: .value é string JSON-friendly ("PLACE", não PLACE).
    HELLO = "HELLO"
    START = "START"
    CHAT = "CHAT"
    PLACE = "PLACE"
    MOVE = "MOVE"
    CAPTURE = "CAPTURE"
    RESIGN = "RESIGN"
    REMATCH = "REMATCH"
    STATE = "STATE"
    ERROR = "ERROR"


def serialize(msg: dict[str, Any]) -> str:
    return json.dumps(msg, ensure_ascii=False)


def deserialize(payload: str) -> dict[str, Any]:
    return json.loads(payload)
