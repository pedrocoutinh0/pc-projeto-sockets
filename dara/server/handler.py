"""
Despacho de mensagens JSON → GameRoom.

Fluxo TCP: run_handler_tcp lê uma linha por vez (bloqueante) e chama
handle_message. Fluxo UDP: run_udp_receiver mapeia endereço → player_id.

handle_message valida campos básicos; regras de jogo ficam em game_room/rules.
"""
import logging
import socket
from typing import TYPE_CHECKING

from dara.net.protocol import MessageType, deserialize
from dara.net.transport.udp import UdpClientEndpoint

if TYPE_CHECKING:
    from dara.server.game_room import GameRoom
    from dara.net.transport.tcp import TcpClientEndpoint

logger = logging.getLogger(__name__)


def handle_message(msg: dict, game_room: "GameRoom", player_id: int) -> None:
    # player_id vem do endpoint (TCP) ou do mapa addr→id (UDP), não do JSON.
    msg_type = msg.get("type")
    if msg_type == MessageType.HELLO.value:
        nick = msg.get("nick", "")
        game_room.set_nickname(player_id, nick)
        logger.info("HELLO jogador %s: %s", player_id, nick or "(sem nick)")
        return
    if msg_type == MessageType.PLACE.value:
        row = msg.get("row")
        col = msg.get("col")
        if row is None or col is None:
            game_room.send_error(player_id, "PLACE requer row e col.")
            return
        try:
            row, col = int(row), int(col)
        except (TypeError, ValueError):
            game_room.send_error(player_id, "row e col devem ser inteiros.")
            return
        if not (0 <= row < 5 and 0 <= col < 6):
            game_room.send_error(player_id, "Posição fora do tabuleiro.")
            return
        ok, err = game_room.apply_place(player_id, row, col)
        if not ok:
            game_room.send_error(player_id, err)
        return
    if msg_type == MessageType.MOVE.value:
        from_pos = msg.get("from")
        to_pos = msg.get("to")
        if not from_pos or not to_pos or len(from_pos) != 2 or len(to_pos) != 2:
            game_room.send_error(player_id, "MOVE requer from e to como [row,col].")
            return
        try:
            from_row, from_col = int(from_pos[0]), int(from_pos[1])
            to_row, to_col = int(to_pos[0]), int(to_pos[1])
        except (TypeError, ValueError, IndexError):
            game_room.send_error(player_id, "from e to devem ser [row,col].")
            return
        if not (0 <= from_row < 5 and 0 <= from_col < 6 and 0 <= to_row < 5 and 0 <= to_col < 6):
            game_room.send_error(player_id, "Posição fora do tabuleiro.")
            return
        ok, err = game_room.apply_move(player_id, from_row, from_col, to_row, to_col)
        if not ok:
            game_room.send_error(player_id, err)
        return
    if msg_type == MessageType.CAPTURE.value:
        row = msg.get("row")
        col = msg.get("col")
        if row is None or col is None:
            game_room.send_error(player_id, "CAPTURE requer row e col.")
            return
        try:
            row, col = int(row), int(col)
        except (TypeError, ValueError):
            game_room.send_error(player_id, "row e col devem ser inteiros.")
            return
        if not (0 <= row < 5 and 0 <= col < 6):
            game_room.send_error(player_id, "Posição fora do tabuleiro.")
            return
        ok, err = game_room.apply_capture_choice(player_id, row, col)
        if not ok:
            game_room.send_error(player_id, err)
        return
    if msg_type == MessageType.CHAT.value:
        text = msg.get("text", "")
        game_room.broadcast({
            "type": MessageType.CHAT.value,
            "from": player_id,
            "nick": game_room.nickname_of(player_id),
            "text": str(text),
        })
        logger.info("CHAT jogador %s: %s", player_id, text[:50])
        return
    if msg_type == MessageType.RESIGN.value:
        game_room.resign(player_id)
        return
    if msg_type == MessageType.REMATCH.value:
        ok, err = game_room.toggle_rematch_vote(player_id)
        if not ok:
            game_room.send_error(player_id, err)
        return
    game_room.send_error(player_id, "Tipo de mensagem desconhecido: %s" % msg_type)


def run_handler_tcp(endpoint: "TcpClientEndpoint", game_room: "GameRoom") -> None:
    """Um thread por cliente: loop bloqueante read_message → handle_message."""
    player_id = endpoint.player_id
    while True:
        msg = endpoint.read_message()
        if msg is None:
            logger.info("Cliente %s desconectado.", player_id)
            break
        try:
            handle_message(msg, game_room, player_id)
        except Exception as e:
            logger.exception("Erro ao processar mensagem do jogador %s: %s", player_id, e)
            game_room.send_error(player_id, "Erro interno no servidor.")


def run_udp_receiver(
    sock: socket.socket,
    endpoint1: UdpClientEndpoint,
    endpoint2: UdpClientEndpoint,
    game_room: "GameRoom",
) -> None:
    """Loop único de recepção UDP: recvfrom e despacha por endereço."""
    addr_to_player = {endpoint1.address: 1, endpoint2.address: 2}
    while True:
        try:
            data, addr = sock.recvfrom(4096)
        except OSError:
            break
        player_id = addr_to_player.get(addr)
        if player_id is None:
            continue
        try:
            msg = deserialize(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        try:
            handle_message(msg, game_room, player_id)
        except Exception as e:
            logger.exception("Erro ao processar mensagem do jogador %s: %s", player_id, e)
            game_room.send_error(player_id, "Erro interno no servidor.")
