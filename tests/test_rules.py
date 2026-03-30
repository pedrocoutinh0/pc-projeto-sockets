"""Testes unitários de dara.domain.rules (sem servidor nem sockets)."""

import unittest

from dara.domain.board import Board, Phase, ROWS, COLS, PIECES_PER_PLAYER
from dara.domain import rules


class TestRules(unittest.TestCase):
    def setUp(self) -> None:
        self.board = Board()

    def test_can_place_empty_cell_placement_phase(self) -> None:
        ok, _ = rules.can_place(self.board, Phase.PLACEMENT, 1, 0, 0)
        self.assertTrue(ok)

    def test_can_place_rejects_occupied_cell(self) -> None:
        self.board.set(0, 0, 1)
        ok, err = rules.can_place(self.board, Phase.PLACEMENT, 2, 0, 0)
        self.assertFalse(ok)
        self.assertIn("ocupada", err)

    def test_can_place_rejects_wrong_phase(self) -> None:
        ok, err = rules.can_place(self.board, Phase.MOVEMENT, 1, 0, 0)
        self.assertFalse(ok)
        self.assertIn("colocação", err)

    def test_can_place_forbids_line_of_three_vertical(self) -> None:
        self.board.set(0, 0, 1)
        self.board.set(1, 0, 1)
        ok, err = rules.can_place(self.board, Phase.PLACEMENT, 1, 2, 0)
        self.assertFalse(ok)
        self.assertIn("linha de 3", err)

    def test_can_place_forbids_line_of_three_horizontal(self) -> None:
        self.board.set(0, 0, 1)
        self.board.set(0, 1, 1)
        ok, err = rules.can_place(self.board, Phase.PLACEMENT, 1, 0, 2)
        self.assertFalse(ok)
        self.assertIn("linha de 3", err)

    def test_can_place_allows_placement_without_line(self) -> None:
        self.board.set(0, 0, 1)
        self.board.set(0, 1, 2)
        ok, _ = rules.can_place(self.board, Phase.PLACEMENT, 1, 1, 0)
        self.assertTrue(ok)

    def test_apply_place_updates_board_and_count(self) -> None:
        rules.apply_place(self.board, 1, 0, 0)
        self.assertEqual(self.board.get(0, 0), 1)
        self.assertEqual(self.board.pieces_placed(1), 1)

    def test_can_move_adjacent_empty(self) -> None:
        self.board.set(0, 0, 1)
        ok, _ = rules.can_move(self.board, Phase.MOVEMENT, 1, 0, 0, 1, 0)
        self.assertTrue(ok)

    def test_can_move_rejects_non_adjacent(self) -> None:
        self.board.set(0, 0, 1)
        ok, err = rules.can_move(self.board, Phase.MOVEMENT, 1, 0, 0, 0, 2)
        self.assertFalse(ok)
        self.assertIn("adjacente", err)

    def test_can_move_rejects_occupied_destination(self) -> None:
        self.board.set(0, 0, 1)
        self.board.set(1, 0, 2)
        ok, err = rules.can_move(self.board, Phase.MOVEMENT, 1, 0, 0, 1, 0)
        self.assertFalse(ok)
        self.assertIn("ocupado", err)

    def test_can_move_rejects_wrong_player_piece(self) -> None:
        self.board.set(0, 0, 2)
        ok, err = rules.can_move(self.board, Phase.MOVEMENT, 1, 0, 0, 1, 0)
        self.assertFalse(ok)
        self.assertIn("sua peça", err)

    def test_can_move_rejects_line_of_four_horizontal(self) -> None:
        self.board.set(0, 0, 1)
        self.board.set(0, 1, 1)
        self.board.set(0, 2, 1)
        self.board.set(1, 3, 1)
        ok, err = rules.can_move(self.board, Phase.MOVEMENT, 1, 1, 3, 0, 3)
        self.assertFalse(ok)
        self.assertIn("linha de 4", err)

    def test_can_move_rejects_line_of_four_vertical(self) -> None:
        self.board.set(0, 0, 1)
        self.board.set(1, 0, 1)
        self.board.set(2, 0, 1)
        self.board.set(3, 1, 1)
        ok, err = rules.can_move(self.board, Phase.MOVEMENT, 1, 3, 1, 3, 0)
        self.assertFalse(ok)
        self.assertIn("linha de 4", err)

    def test_can_move_allows_line_of_three_not_four(self) -> None:
        self.board.set(0, 0, 1)
        self.board.set(0, 1, 1)
        self.board.set(1, 2, 1)
        ok, _ = rules.can_move(self.board, Phase.MOVEMENT, 1, 1, 2, 0, 2)
        self.assertTrue(ok)

    def test_player_has_line_of_at_least_four_detects_run(self) -> None:
        self.board.set(0, 0, 1)
        self.board.set(0, 1, 1)
        self.board.set(0, 2, 1)
        self.board.set(0, 3, 1)
        self.assertTrue(rules.player_has_line_of_at_least_four(self.board, 1))

    def test_find_lines_of_three_horizontal(self) -> None:
        self.board.set(0, 0, 1)
        self.board.set(0, 1, 1)
        self.board.set(0, 2, 1)
        lines = rules.find_lines_of_three(self.board, 1)
        self.assertEqual(len(lines), 1)
        self.assertEqual(len(lines[0]), 3)
        self.assertEqual(set(lines[0]), {(0, 0), (0, 1), (0, 2)})

    def test_find_lines_of_three_vertical(self) -> None:
        self.board.set(0, 0, 1)
        self.board.set(1, 0, 1)
        self.board.set(2, 0, 1)
        lines = rules.find_lines_of_three(self.board, 1)
        self.assertEqual(len(lines), 1)
        self.assertEqual(set(lines[0]), {(0, 0), (1, 0), (2, 0)})

    def test_newly_completed_lines_empty_when_line_unchanged(self) -> None:
        before = rules.find_lines_of_three(self.board, 1)
        after = rules.find_lines_of_three(self.board, 1)
        self.assertEqual(rules.newly_completed_lines_of_three(before, after), [])

    def test_newly_completed_lines_detects_new_alignment(self) -> None:
        self.board.set(0, 0, 1)
        self.board.set(0, 1, 1)
        before = rules.find_lines_of_three(self.board, 1)
        self.board.set(0, 2, 1)
        after = rules.find_lines_of_three(self.board, 1)
        neww = rules.newly_completed_lines_of_three(before, after)
        self.assertEqual(len(neww), 1)
        self.assertEqual(set(neww[0]), {(0, 0), (0, 1), (0, 2)})

    def test_newly_completed_lines_ignores_preexisting_line_after_other_move(self) -> None:
        """Movimento que não altera uma linha de 3 já existente não gera captura nova."""
        self.board.set(4, 2, 2)
        self.board.set(4, 3, 2)
        self.board.set(4, 4, 2)
        self.board.set(3, 3, 2)
        self.board.set(3, 4, None)
        before = rules.find_lines_of_three(self.board, 2)
        rules.apply_move(self.board, 2, 3, 3, 3, 4)
        after = rules.find_lines_of_three(self.board, 2)
        neww = rules.newly_completed_lines_of_three(before, after)
        self.assertEqual(
            neww,
            [],
            "Linha na fila 4 já existia; mover (3,3)->(3,4) não cria linha nova",
        )

    def test_apply_capture_removes_opponent_piece(self) -> None:
        self.board.set(0, 0, 2)
        rules.apply_capture(self.board, 2, 0, 0)
        self.assertIsNone(self.board.get(0, 0))

    def test_can_choose_capture_valid_opponent_cell(self) -> None:
        self.board.set(1, 1, 2)
        ok, _ = rules.can_choose_capture(self.board, 2, 1, 1)
        self.assertTrue(ok)

    def test_can_choose_capture_rejects_own_piece(self) -> None:
        self.board.set(0, 0, 1)
        self.board.set(0, 1, 2)
        ok, err = rules.can_choose_capture(self.board, 2, 0, 0)
        self.assertFalse(ok)
        self.assertIn("oponente", err)

    def test_can_choose_capture_rejects_empty(self) -> None:
        ok, err = rules.can_choose_capture(self.board, 2, 0, 0)
        self.assertFalse(ok)
        self.assertIn("oponente", err)

    def test_check_winner_player1_wins_when_player2_has_two_pieces(self) -> None:
        for r in range(ROWS):
            for c in range(COLS):
                self.board.set(r, c, None)
        self.board.set(0, 0, 1)
        self.board.set(0, 1, 1)
        self.board.set(1, 0, 1)
        self.board.set(0, 2, 2)
        self.board.set(1, 1, 2)
        winner = rules.check_winner(self.board)
        self.assertEqual(winner, 1)

    def test_check_winner_none_when_both_have_many_pieces(self) -> None:
        self.board.set(0, 0, 1)
        self.board.set(0, 1, 2)
        winner = rules.check_winner(self.board)
        self.assertIsNone(winner)

    def test_get_adjacent_cells_center(self) -> None:
        adj = rules.get_adjacent_cells(1, 1)
        self.assertEqual(set(adj), {(0, 1), (2, 1), (1, 0), (1, 2)})

    def test_get_adjacent_cells_corner(self) -> None:
        adj = rules.get_adjacent_cells(0, 0)
        self.assertEqual(set(adj), {(1, 0), (0, 1)})


if __name__ == "__main__":
    unittest.main()
