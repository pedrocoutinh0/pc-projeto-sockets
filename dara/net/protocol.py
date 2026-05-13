"""
Contrato de aplicação: tipos de mensagem nos payloads (STATE, CHAT, …).

Com Pyro5, estes dicts já não atravessam sockets geridos manualmente: passam a ser
argumentos das chamadas remotas nomeadas no cliente (notificar_inicio,
atualizar_estado, …) e dos métodos no servidor. Mantêm-se para compatibilidade
com GameRoom e com a UI que interpreta o campo \"type\".
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
