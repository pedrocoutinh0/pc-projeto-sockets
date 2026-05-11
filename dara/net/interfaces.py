"""
Contratos estruturais (Protocol): o GameRoom só precisa de "algo que envie"
para cada jogador (ClientEndpoint).
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ClientEndpoint(Protocol):
    """Lado servidor: um objeto por jogador ligado (envia payload ao cliente)."""

    def send(self, msg: dict) -> None:
        """Envia mensagem ao cliente (tipicamente dict com \"type\" STATE/CHAT/ERROR)."""
        ...

    @property
    def player_id(self) -> int:
        """Identificação do jogador (1 ou 2) associada ao endpoint."""
        ...

    @property
    def peer_key(self) -> str:
        """Chave estável do cliente (estatísticas no servidor)."""
        ...
