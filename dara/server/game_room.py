"""
Estado autoritário da partida (servidor).

Fluxo mental: qualquer jogada válida altera _board/_phase/_current_turn e depois
broadcast(STATE) para os dois. Erros de validação → send_error só ao autor.
Chat: broadcast(CHAT). Vitória → _winner; stats gravadas uma vez por partida.

3 - player_id alterna entre 1 e 2 (oponente).
"""
from __future__ import annotations

import logging
import time
from typing import Any

from dara.domain.board import Board, Phase, ROWS, COLS, PIECES_PER_PLAYER
from dara.domain import rules
from dara.net.protocol import MessageType
from dara.net.interfaces import ClientEndpoint
from dara.server import session_stats

logger = logging.getLogger(__name__)


class GameRoom:
    """Sala de 2 jogadores: tabuleiro + turno + rede (ClientEndpoint)."""

    def __init__(
        self,
        endpoint1: ClientEndpoint,
        endpoint2: ClientEndpoint,
    ) -> None:
        self._endpoints: dict[int, ClientEndpoint] = {
            1: endpoint1,
            2: endpoint2,
        }
        self._player_keys: dict[int, str] = {
            1: endpoint1.peer_key,
            2: endpoint2.peer_key,
        }
        self._board = Board()
        self._phase = Phase.PLACEMENT
        self._current_turn = 1
        self._winner: int | None = None
        self._nicknames: dict[int, str] = {1: "", 2: ""}
        self._awaiting_capture_for: int | None = None
        self._match_started_at: float | None = None
        self._match_ended_at: float | None = None
        self._rematch_votes: set[int] = set()
        self._match_result_recorded = False

    def _extras_message(self) -> dict[str, Any]:
        votes = sorted(self._rematch_votes)
        return {
            "matchStartedAt": self._match_started_at,
            "matchEndedAt": self._match_ended_at,
            "nicknames": {
                "1": self.nickname_of(1),
                "2": self.nickname_of(2),
            },
            "statsByPlayer": session_stats.stats_payload_for_keys(
                self._player_keys[1],
                self._player_keys[2],
            ),
            "rematchVotes": votes,
        }

    def _freeze_match_end_time_if_needed(self) -> None:
        if self._winner is not None and self._match_ended_at is None:
            self._match_ended_at = time.time()

    def nickname_of(self, player_id: int) -> str:
        n = self._nicknames.get(player_id, "")
        return n if n else f"Jogador {player_id}"

    def _state_message(self) -> dict[str, Any]:
        return {
            "type": MessageType.STATE.value,
            "board": self._board.to_serializable(),
            "phase": self._phase.value,
            "currentTurn": self._current_turn,
            "awaitingCapture": self._awaiting_capture_for is not None,
            "captured": {
                1: PIECES_PER_PLAYER - self._board.count_pieces(1),
                2: PIECES_PER_PLAYER - self._board.count_pieces(2),
            },
            "winner": self._winner,
            **self._extras_message(),
        }

    def _record_stats_once(self) -> None:
        if self._match_result_recorded or self._winner is None:
            return
        self._match_result_recorded = True
        w = self._winner
        loser = 3 - w
        session_stats.record_match(
            self._player_keys[w],
            self._player_keys[loser],
        )
        logger.info(
            "Placar sessão: %s W/L=%s, %s W/L=%s",
            self._player_keys[w],
            session_stats.snapshot(self._player_keys[w]),
            self._player_keys[loser],
            session_stats.snapshot(self._player_keys[loser]),
        )

    def broadcast(self, msg: dict[str, Any]) -> None:
        # "Entre clientes" na prática = servidor reenvia o mesmo JSON aos dois.
        for ep in self._endpoints.values():
            try:
                ep.send(msg)
            except Exception as e:
                logger.warning("Falha ao enviar para cliente: %s", e)

    def send_error(self, player_id: int, message: str) -> None:
        self._endpoints[player_id].send({
            "type": MessageType.ERROR.value,
            "message": message,
        })

    def set_nickname(self, player_id: int, nick: str) -> None:
        self._nicknames[player_id] = nick or f"Jogador {player_id}"

    def apply_place(self, player_id: int, row: int, col: int) -> tuple[bool, str]:
        if self._winner is not None:
            return False, "Partida já encerrada."
        if self._current_turn != player_id:
            return False, "Não é seu turno."
        ok, err = rules.can_place(self._board, self._phase, player_id, row, col)
        if not ok:
            return False, err
        pieces_before = self._board.count_pieces(1) + self._board.count_pieces(2)
        rules.apply_place(self._board, player_id, row, col)
        if self._match_started_at is None and pieces_before == 0:
            self._match_started_at = time.time()
        self._current_turn = 3 - player_id
        # Quando ambos colocaram 12 peças, passa à fase de movimento; turno reinicia em 1.
        if (
            self._board.pieces_placed(1) >= PIECES_PER_PLAYER
            and self._board.pieces_placed(2) >= PIECES_PER_PLAYER
        ):
            self._phase = Phase.MOVEMENT
            self._current_turn = 1
        self.broadcast(self._state_message())
        logger.info("PLACE jogador %s em (%s, %s)", player_id, row, col)
        return True, ""

    def apply_move(
        self,
        player_id: int,
        from_row: int,
        from_col: int,
        to_row: int,
        to_col: int,
    ) -> tuple[bool, str]:
        if self._winner is not None:
            return False, "Partida já encerrada."
        if self._awaiting_capture_for is not None:
            if self._awaiting_capture_for == player_id:
                return False, "Formou linha de 3: escolha uma peça do oponente para capturar."
            return False, "Aguarde o oponente concluir a captura."
        if self._current_turn != player_id:
            return False, "Não é seu turno."
        ok, err = rules.can_move(
            self._board, self._phase, player_id,
            from_row, from_col, to_row, to_col,
        )
        if not ok:
            return False, err
        lines_before = rules.find_lines_of_three(self._board, player_id)
        rules.apply_move(
            self._board, player_id,
            from_row, from_col, to_row, to_col,
        )
        opponent = 3 - player_id
        lines_after = rules.find_lines_of_three(self._board, player_id)
        lines = rules.newly_completed_lines_of_three(lines_before, lines_after)
        # Linha de 3 nova + oponente com peças → este jogador deve escolher CAPTURE.
        if lines and self._board.count_pieces(opponent) > 0:
            self._awaiting_capture_for = player_id
            self.broadcast(self._state_message())
            logger.info(
                "MOVE jogador %s de (%s,%s) para (%s,%s); aguardando escolha de captura",
                player_id, from_row, from_col, to_row, to_col,
            )
            return True, ""
        self._winner = rules.check_winner(self._board)
        self._freeze_match_end_time_if_needed()
        self._record_stats_once()
        self._current_turn = 3 - player_id
        self.broadcast(self._state_message())
        logger.info("MOVE jogador %s de (%s,%s) para (%s,%s)", player_id, from_row, from_col, to_row, to_col)
        return True, ""

    def apply_capture_choice(
        self, player_id: int, row: int, col: int
    ) -> tuple[bool, str]:
        if self._winner is not None:
            return False, "Partida já encerrada."
        if self._awaiting_capture_for is None:
            return False, "Não há captura pendente."
        if self._awaiting_capture_for != player_id:
            return False, "Não é você quem deve capturar."
        opponent = 3 - player_id
        ok, err = rules.can_choose_capture(self._board, opponent, row, col)
        if not ok:
            return False, err
        rules.apply_capture(self._board, opponent, row, col)
        logger.info(
            "CAPTURA jogador %s removeu peça do oponente em (%s, %s)",
            player_id, row, col,
        )
        self._awaiting_capture_for = None
        self._winner = rules.check_winner(self._board)
        self._freeze_match_end_time_if_needed()
        self._record_stats_once()
        self._current_turn = 3 - player_id
        self.broadcast(self._state_message())
        return True, ""

    def resign(self, player_id: int) -> None:
        if self._winner is not None:
            return
        self._awaiting_capture_for = None
        self._winner = 3 - player_id
        self._match_ended_at = time.time()
        self._record_stats_once()
        self.broadcast(self._state_message())
        logger.info("RESIGN jogador %s; vencedor: %s", player_id, self._winner)

    def start_message(self, player_id: int) -> dict[str, Any]:
        return {
            "type": MessageType.START.value,
            "player": player_id,
            "board": self._board.to_serializable(),
            "phase": self._phase.value,
            "currentTurn": self._current_turn,
            "awaitingCapture": self._awaiting_capture_for is not None,
            "winner": self._winner,
            **self._extras_message(),
        }

    def toggle_rematch_vote(self, player_id: int) -> tuple[bool, str]:
        if self._winner is None:
            return False, "Revanche só está disponível após o fim da partida."
        if player_id in self._rematch_votes:
            self._rematch_votes.discard(player_id)
        else:
            self._rematch_votes.add(player_id)
        if len(self._rematch_votes) == 2:
            self._begin_rematch()
        else:
            self.broadcast(self._state_message())
        return True, ""

    def _begin_rematch(self) -> None:
        self._board = Board()
        self._phase = Phase.PLACEMENT
        self._current_turn = 1
        self._winner = None
        self._awaiting_capture_for = None
        self._rematch_votes.clear()
        self._match_result_recorded = False
        self._match_started_at = None
        self._match_ended_at = None
        for pid, ep in self._endpoints.items():
            ep.send(self.start_message(pid))
        logger.info("Revanche: nova partida iniciada (mesmos clientes).")
