"""
Modelo do tabuleiro 5×6 e contagem de peças colocadas (fase inicial).

Sem rede: o servidor usa Board + rules; JSON usa to_serializable / from_serializable.
"""
from enum import Enum
from typing import Optional

ROWS = 5
COLS = 6
PIECES_PER_PLAYER = 12


class Phase(str, Enum):
    PLACEMENT = "PLACEMENT"
    MOVEMENT = "MOVEMENT"


class Board:
    def __init__(self) -> None:
        # None = vazio; 1 ou 2 = dono da peça.
        self._grid: list[list[Optional[int]]] = [
            [None for _ in range(COLS)] for _ in range(ROWS)
        ]
        # Contador lógico da fase PLACEMENT (12 por jogador); pode divergir se
        # from_serializable reconstrói só pela grelha — aí recalcula-se no fim.
        self._pieces_placed: dict[int, int] = {1: 0, 2: 0}

    @property
    def grid(self) -> list[list[Optional[int]]]:
        return self._grid

    def get(self, row: int, col: int) -> Optional[int]:
        if 0 <= row < ROWS and 0 <= col < COLS:
            return self._grid[row][col]
        return None

    def set(self, row: int, col: int, player: Optional[int]) -> None:
        if 0 <= row < ROWS and 0 <= col < COLS:
            self._grid[row][col] = player

    def count_pieces(self, player: int) -> int:
        return sum(
            1 for row in self._grid for cell in row if cell == player
        )

    def pieces_placed(self, player: int) -> int:
        return self._pieces_placed.get(player, 0)

    def set_pieces_placed(self, player: int, count: int) -> None:
        self._pieces_placed[player] = count

    def to_serializable(self) -> list[list[Optional[int]]]:
        return [row[:] for row in self._grid]

    @classmethod
    def from_serializable(cls, data: list[list[Optional[int]]]) -> "Board":
        board = cls()
        for r, row in enumerate(data):
            for c, cell in enumerate(row):
                if r < ROWS and c < COLS:
                    board._grid[r][c] = cell
        for p in (1, 2):
            board._pieces_placed[p] = board.count_pieces(p)
        return board
