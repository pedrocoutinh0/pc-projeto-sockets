"""
Contratos estruturais (Protocol): o GameRoom só precisa de "algo que envie"
para cada jogador; o cliente só precisa de "algo que envie e receba callbacks".

Debug mental: TcpClientEndpoint/UdpClientEndpoint implementam ClientEndpoint;
TcpConnection/UdpConnection implementam Connection — sem herança explícita,
só duck typing verificável com isinstance(..., Protocol) se runtime_checkable.
"""

from typing import Protocol, Callable, runtime_checkable


@runtime_checkable
class ClientEndpoint(Protocol):
    """Lado servidor: um objeto por jogador ligado (envia JSON para esse cliente)."""

    def send(self, msg: dict) -> None:
        """Envia mensagem ao cliente."""
        ...

    @property
    def player_id(self) -> int:
        """Identificação do jogador (1 ou 2) associada ao endpoint."""
        ...

    @property
    def peer_key(self) -> str:
        """Chave estável do cliente (estatísticas no servidor)."""
        ...


@runtime_checkable
class Connection(Protocol):
    """Lado cliente: ligação ao servidor; on_message dispara callback (tipicamente fila + UI)."""

    def send(self, msg: dict) -> None:
        """Envia mensagem ao servidor."""
        ...

    def on_message(self, callback: Callable[[dict], None]) -> None:
        """Registra callback para mensagens recebidas (recepção assíncrona)."""
        ...
