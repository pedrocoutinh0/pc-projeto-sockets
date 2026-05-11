"""
Servidor de jogo exposto via Pyro5: implementação remota da API JogoRemoto.

Antes: mensagens TCP manuais eram interpretadas em handler.py (dict com "type").
Agora: cada operação é um método remoto; o Pyro encaminha a chamada para este
objeto, que valida e delega em GameRoom. As atualizações para os clientes
continuam a ser o mesmo payload dict (STATE, CHAT, …), mas enviadas através do
callback remoto receber() em cada NotificadorCliente — modelo análogo a RMI
callback. O cliente não conhece GameRoom nem sockets; só vê o proxy remoto.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

import Pyro5.api
import Pyro5.server

from dara.net.interfaces import ClientEndpoint
from dara.net.protocol import MessageType
from dara.server.game_room import GameRoom

logger = logging.getLogger(__name__)


class PyroClientEndpoint:
    """Adapta o proxy Pyro do notificador do cliente ao protocolo ClientEndpoint."""

    def __init__(
        self,
        uri_notificador: str,
        player_id: int,
        peer_key: str,
    ) -> None:
        self._uri_notificador = uri_notificador
        self._player_id = player_id
        self._peer_key = peer_key

    @property
    def player_id(self) -> int:
        return self._player_id

    @property
    def peer_key(self) -> str:
        return self._peer_key

    def send(self, msg: dict[str, Any]) -> None:
        # Novo Proxy por envio: workers do daemon Pyro podem ser threads diferentes;
        # reutilizar o mesmo Proxy entre threads gera erro de "owner" no cliente.
        notifier = Pyro5.api.Proxy(self._uri_notificador)
        notifier.receber(msg)


@Pyro5.server.expose
class ServidorDara:
    """
    Objeto remoto único do servidor: dois jogadores registam-se em sequência;
    ao segundo registo cria-se o GameRoom e envia-se START a ambos.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: tuple[PyroClientEndpoint, str] | None = None
        self._room: GameRoom | None = None

    def _game_or_raise(self) -> GameRoom:
        if self._room is None:
            raise ValueError("A partida ainda não começou (aguarde o segundo jogador).")
        return self._room

    def registar(self, uri_notificador: str, apelido: str) -> int:
        apelido = str(apelido).strip()
        uri_notificador = uri_notificador.strip()
        peer_key = uri_notificador
        with self._lock:
            if self._room is not None:
                raise ValueError(
                    "Esta sala já tem uma partida a decorrer. Tente mais tarde."
                )
            if self._pending is None:
                endpoint = PyroClientEndpoint(uri_notificador, 1, peer_key)
                self._pending = (endpoint, apelido)
                logger.info(
                    "[RPC] registar → jogador 1 apelido=%r (à espera do segundo).",
                    apelido or "(vazio)",
                )
                return 1
            ep1, nick1 = self._pending
            ep2 = PyroClientEndpoint(uri_notificador, 2, peer_key)
            self._room = GameRoom(ep1, ep2)
            self._room.set_nickname(1, nick1)
            self._room.set_nickname(2, apelido)
            self._pending = None
            for ep in (ep1, ep2):
                ep.send(self._room.start_message(ep.player_id))
            logger.info(
                "[RPC] registar → jogador 2 apelido=%r; partida iniciada (%s vs %s).",
                apelido or "(vazio)",
                self._room.nickname_of(1),
                self._room.nickname_of(2),
            )
            return 2

    def colocar_peca(self, jogador: int, linha: int, coluna: int) -> None:
        logger.info("[RPC] colocar_peca jogador=%s célula=(%s,%s)", jogador, linha, coluna)
        with self._lock:
            room = self._game_or_raise()
            ok, err = room.apply_place(jogador, linha, coluna)
            if not ok:
                logger.info("[RPC] colocar_peca recusado jogador=%s: %s", jogador, err)
                room.send_error(jogador, err)

    def mover_peca(
        self,
        jogador: int,
        origem_linha: int,
        origem_coluna: int,
        destino_linha: int,
        destino_coluna: int,
    ) -> None:
        logger.info(
            "[RPC] mover_peca jogador=%s de (%s,%s) para (%s,%s)",
            jogador,
            origem_linha,
            origem_coluna,
            destino_linha,
            destino_coluna,
        )
        with self._lock:
            room = self._game_or_raise()
            ok, err = room.apply_move(
                jogador,
                origem_linha,
                origem_coluna,
                destino_linha,
                destino_coluna,
            )
            if not ok:
                logger.info("[RPC] mover_peca recusado jogador=%s: %s", jogador, err)
                room.send_error(jogador, err)

    def escolher_captura(self, jogador: int, linha: int, coluna: int) -> None:
        logger.info("[RPC] escolher_captura jogador=%s célula=(%s,%s)", jogador, linha, coluna)
        with self._lock:
            room = self._game_or_raise()
            ok, err = room.apply_capture_choice(jogador, linha, coluna)
            if not ok:
                logger.info("[RPC] escolher_captura recusado jogador=%s: %s", jogador, err)
                room.send_error(jogador, err)

    def enviar_mensagem(self, jogador: int, texto: str) -> None:
        logger.info("[RPC] enviar_mensagem jogador=%s texto=%r", jogador, str(texto)[:200])
        with self._lock:
            room = self._game_or_raise()
            room.broadcast({
                "type": MessageType.CHAT.value,
                "from": jogador,
                "nick": room.nickname_of(jogador),
                "text": str(texto),
            })

    def desistir(self, jogador: int) -> None:
        logger.info("[RPC] desistir jogador=%s", jogador)
        with self._lock:
            room = self._game_or_raise()
            room.resign(jogador)

    def votar_revanche(self, jogador: int) -> None:
        logger.info("[RPC] votar_revanche jogador=%s", jogador)
        with self._lock:
            room = self._game_or_raise()
            ok, err = room.toggle_rematch_vote(jogador)
            if not ok:
                logger.info("[RPC] votar_revanche recusado jogador=%s: %s", jogador, err)
                room.send_error(jogador, err)
