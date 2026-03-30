"""
Regras do Dara: validação (can_*) e efeitos (apply_*).

can_place / can_move simulam no tabuleiro e desfazem se inválido — o estado
real só muda quando GameRoom chama apply_* após can_* True.

newly_completed_lines_of_three: captura só quando o alinhamento de 3 é novo
após o movimento (não reaproveita linhas que já existiam).
"""
from __future__ import annotations

from dara.domain.board import Board, ROWS, COLS, PIECES_PER_PLAYER
from dara.domain.board import Phase


def get_adjacent_cells(row: int, col: int) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        r, c = row + dr, col + dc
        if 0 <= r < ROWS and 0 <= c < COLS:
            result.append((r, c))
    return result


def player_has_line_of_at_least_four(board: Board, player: int) -> bool:
    """True se existir segmento horizontal ou vertical com 4+ peças seguidas do jogador."""
    for r in range(ROWS):
        run = 0
        for c in range(COLS):
            if board.get(r, c) == player:
                run += 1
                if run >= 4:
                    return True
            else:
                run = 0
    for c in range(COLS):
        run = 0
        for r in range(ROWS):
            if board.get(r, c) == player:
                run += 1
                if run >= 4:
                    return True
            else:
                run = 0
    return False


def find_lines_of_three(board: Board, player: int) -> list[list[tuple[int, int]]]:
    """Returns list of lines; each line is list of 3 (row, col) cells."""
    lines: list[list[tuple[int, int]]] = []
    seen: set[frozenset[tuple[int, int]]] = set()
    for r in range(ROWS):
        for c in range(COLS):
            if c + 2 < COLS and all(
                board.get(r, c + i) == player for i in range(3)
            ):
                line = [(r, c + i) for i in range(3)]
                key = frozenset(line)
                if key not in seen:
                    seen.add(key)
                    lines.append(line)
            if r + 2 < ROWS and all(
                board.get(r + i, c) == player for i in range(3)
            ):
                line = [(r + i, c) for i in range(3)]
                key = frozenset(line)
                if key not in seen:
                    seen.add(key)
                    lines.append(line)
    return lines


def newly_completed_lines_of_three(
    lines_before: list[list[tuple[int, int]]],
    lines_after: list[list[tuple[int, int]]],
) -> list[list[tuple[int, int]]]:
    """Linhas de 3 após o movimento que não existiam como linha completa antes (captura só por alinhamento novo)."""
    before_keys: set[frozenset[tuple[int, int]]] = {frozenset(line) for line in lines_before}
    return [line for line in lines_after if frozenset(line) not in before_keys]


def can_place(
    board: Board, phase: Phase, player: int, row: int, col: int
) -> tuple[bool, str]:
    if phase != Phase.PLACEMENT:
        return False, "Não é fase de colocação."
    if board.get(row, col) is not None:
        return False, "Casa ocupada."
    if board.pieces_placed(player) >= PIECES_PER_PLAYER:
        return False, "Todas as peças já foram colocadas."
    board.set(row, col, player)
    if find_lines_of_three(board, player):
        board.set(row, col, None)
        return False, "Não é permitido formar linha de 3 na fase de colocação."
    board.set(row, col, None)
    return True, ""


def can_move(
    board: Board, phase: Phase, player: int,
    from_row: int, from_col: int, to_row: int, to_col: int
) -> tuple[bool, str]:
    if phase != Phase.MOVEMENT:
        return False, "Não é fase de movimentação."
    if board.get(from_row, from_col) != player:
        return False, "Origem não é sua peça."
    if board.get(to_row, to_col) is not None:
        return False, "Destino ocupado."
    adj = get_adjacent_cells(from_row, from_col)
    if (to_row, to_col) not in adj:
        return False, "Destino não é adjacente (horizontal ou vertical)."
    board.set(from_row, from_col, None)
    board.set(to_row, to_col, player)
    if player_has_line_of_at_least_four(board, player):
        board.set(to_row, to_col, None)
        board.set(from_row, from_col, player)
        return False, "Na movimentação não é permitido formar linha de 4 (ou mais) peças."
    board.set(to_row, to_col, None)
    board.set(from_row, from_col, player)
    return True, ""


def apply_place(board: Board, player: int, row: int, col: int) -> None:
    board.set(row, col, player)
    board.set_pieces_placed(player, board.pieces_placed(player) + 1)


def apply_move(
    board: Board, player: int,
    from_row: int, from_col: int, to_row: int, to_col: int
) -> None:
    board.set(from_row, from_col, None)
    board.set(to_row, to_col, player)


def apply_capture(board: Board, opponent: int, row: int, col: int) -> None:
    if board.get(row, col) == opponent:
        board.set(row, col, None)


def can_choose_capture(
    board: Board, opponent: int, row: int, col: int
) -> tuple[bool, str]:
    if not (0 <= row < ROWS and 0 <= col < COLS):
        return False, "Posição fora do tabuleiro."
    if board.get(row, col) != opponent:
        return False, "Escolha uma casa com peça do oponente."
    return True, ""


def check_winner(board: Board) -> int | None:
    """Returns 1 or 2 if that player won (opponent has <= 2 pieces), else None."""
    c1 = board.count_pieces(1)
    c2 = board.count_pieces(2)
    if c2 <= 2 and c1 > 2:
        return 1
    if c1 <= 2 and c2 > 2:
        return 2
    return None
