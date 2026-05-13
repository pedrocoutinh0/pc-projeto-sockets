"""
Contratos RPC com Pyro5 (invocação remota de métodos, semelhante a RMI em Java).

O nome lógico em ``dara.net.pyro_registry`` é publicado no Pyro Name Server;
as aplicações resolvem PYRONAME contra esse catálogo em vez de fixarem o URI do
daemon do jogo.

Contexto pedagógico (Projeto PPD — RPC/RMI):
- Antes, a aplicação abria sockets TCP manualmente e enviava JSON com um campo
  "type" por mensagem (contrato informal).
- Agora, o cliente invoca métodos remotos expostos pelo servidor através do
  proxy Pyro; a serialização e o transporte ficam por conta da biblioteca.
- A interface remota (Protocol abaixo) define apenas o que o cliente pode pedir;
  a implementação real está no servidor e encapsula a lógica do jogo.
- Os jogadores não criam ligações entre si: apenas chamam o servidor, que
  centraliza o estado e notifica cada cliente via objeto remoto de callback.
- O callback no cliente expõe vários métodos remotos nomeados (como uma
  interface RMI no cliente), em vez de um único receber(dict) genérico.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class NotificadorCliente(Protocol):
    """Lado servidor: stub para o objecto remoto exposto no cliente (callbacks RPC)."""

    def notificar_inicio(self, mensagem_inicio: dict[str, Any]) -> None:
        """RPC: início de partida (equivalente a START)."""
        ...

    def atualizar_estado(self, estado: dict[str, Any]) -> None:
        """RPC: novo snapshot do tabuleiro (STATE)."""
        ...

    def notificar_chat(self, de_jogador: int, apelido: str, texto: str) -> None:
        """RPC: linha de chat de outro jogador."""
        ...

    def notificar_erro(self, texto_erro: str) -> None:
        """RPC: erro de validação dirigido a este jogador."""
        ...


@runtime_checkable
class JogoRemoto(Protocol):
    """Contrato do que o cliente pode invocar no servidor (API remota)."""

    def registar(self, uri_notificador: str, apelido: str) -> int: ...

    def colocar_peca(self, jogador: int, linha: int, coluna: int) -> None: ...

    def mover_peca(
        self,
        jogador: int,
        origem_linha: int,
        origem_coluna: int,
        destino_linha: int,
        destino_coluna: int,
    ) -> None: ...

    def escolher_captura(self, jogador: int, linha: int, coluna: int) -> None: ...

    def enviar_mensagem(self, jogador: int, texto: str) -> None: ...

    def desistir(self, jogador: int) -> None: ...

    def votar_revanche(self, jogador: int) -> None: ...
