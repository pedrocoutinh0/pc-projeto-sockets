"""
Cliente Pygame — fluxo mental para debug:

1) run_ui regista session.on_message(on_net). O Pyro invoca receber() no cliente,
   que por sua vez chama on_net(msg) → msg_queue.put (nunca desenhar aqui).

2) Cada frame: process_network() esvazia a fila (get_nowait) e aplica START/
   STATE/CHAT/ERROR ao estado local (board, phase, current_turn, …).

3) Eventos (rato/tecla): click_cell / send_chat chamam métodos remotos na sessão
   Pyro (RPC), não strings nem dicts de rede manuais.

4) apply_state() copia o payload enviado pelo servidor para variáveis de UI.

Layout/desenho: constantes no topo, build_ui_layout recalcula geometria ao
redimensionar; funções _draw_* montam o frame.
"""

from __future__ import annotations

import datetime
import math
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any

import pygame

from dara.domain.board import ROWS, COLS, Phase
from dara.net.protocol import MessageType

INITIAL_WINDOW_W = 1000
INITIAL_WINDOW_H = 920

TITLE_BAR_H = 52
# Altura fixa do cartão “Conexão/Situação” (conteúdo em 4 linhas + margens)
STATUS_CARD_TOP = 8
STATUS_CARD_H = 120
GAME_OVER_BANNER_H = 208
MARGIN_BELOW_TOP = 10
BOARD_BELOW_HEADER_GAP = 22
STATUS_CARD_PAD_X = 22

SIDE_PANEL_W_BASE = 220
BOARD_SIDE_GAP_BASE = 14
CELL_SIZE_MAX = 56
CELL_SIZE_MIN = 30
BOARD_ABOVE_CHAT_GAP = 16

FOOTER_BTN_MARGIN = 12
BUTTON_ROW_H = 40
FOOTER_MARGIN_ONLY = 10

CHAT_LINES_MAX = 6
CHAT_LINE_H = 15
CHAT_VISIBLE_LINES = 3
CHAT_INPUT_H = 26
CHAT_GAP_ABOVE_INPUT = 12
CHAT_PANEL_BOTTOM_PAD = 12
CHAT_PANEL_TOP_PAD = 10
CHAT_TITLE_BELOW_TOP = 22

FRAME_PAD = 14

NICKNAME_MAX_LEN = 20


def _chat_panel_outer_height() -> int:
    """Altura total do cartão de chat (mensagens nunca sobrepõem o input)."""
    lines_block = CHAT_VISIBLE_LINES * CHAT_LINE_H + 4
    return (
        CHAT_PANEL_TOP_PAD
        + CHAT_TITLE_BELOW_TOP
        + lines_block
        + CHAT_GAP_ABOVE_INPUT
        + CHAT_INPUT_H
        + CHAT_PANEL_BOTTOM_PAD
    )


@dataclass(frozen=True)
class UiLayout:
    sw: int
    sh: int
    cell_size: int
    cell_gap: int
    side_panel_w: int
    board_side_gap: int
    chat_panel_h: int
    footer_reserve: int
    margin_x: int = 24


def _footer_reserve_for_state(my_player: int | None, winner: int | None) -> int:
    """Rodapé: fila de botões só quando há partida ativa ou fim com revanche."""
    if winner is not None:
        return FOOTER_BTN_MARGIN + BUTTON_ROW_H + 6
    if my_player is not None:
        return FOOTER_BTN_MARGIN + BUTTON_ROW_H + 6
    return FOOTER_MARGIN_ONLY


def _header_block_below_title(my_player: int | None, winner: int | None) -> int:
    if winner is not None and my_player is not None:
        return GAME_OVER_BANNER_H + MARGIN_BELOW_TOP + BOARD_BELOW_HEADER_GAP
    return STATUS_CARD_TOP + STATUS_CARD_H + MARGIN_BELOW_TOP + BOARD_BELOW_HEADER_GAP


def build_ui_layout(
    sw: int,
    sh: int,
    *,
    my_player: int | None,
    winner: int | None,
) -> UiLayout:
    margin_x = 24
    footer_reserve = _footer_reserve_for_state(my_player, winner)
    header_below = _header_block_below_title(my_player, winner)
    top_used = TITLE_BAR_H + header_below
    chat_h = _chat_panel_outer_height()
    frame_total = FRAME_PAD * 2

    avail_h = sh - top_used - chat_h - BOARD_ABOVE_CHAT_GAP - footer_reserve - frame_total - 6
    avail_w = sw - 2 * margin_x
    with_panel = my_player is not None
    if with_panel:
        avail_w -= SIDE_PANEL_W_BASE + BOARD_SIDE_GAP_BASE

    avail_h = max(120, avail_h)
    avail_w = max(160, avail_w)

    cell_size = CELL_SIZE_MIN
    cell_gap = 4
    for cs in range(CELL_SIZE_MAX, CELL_SIZE_MIN - 1, -1):
        cg = max(3, min(7, cs // 11))
        bw = COLS * cs + (COLS - 1) * cg
        bh = ROWS * cs + (ROWS - 1) * cg
        if bw <= avail_w and bh <= avail_h:
            cell_size, cell_gap = cs, cg
            break

    return UiLayout(
        sw=sw,
        sh=sh,
        cell_size=cell_size,
        cell_gap=cell_gap,
        side_panel_w=SIDE_PANEL_W_BASE,
        board_side_gap=BOARD_SIDE_GAP_BASE,
        chat_panel_h=chat_h,
        footer_reserve=footer_reserve,
        margin_x=margin_x,
    )

# Cores — base demo + peças do jogo
COLOR_BG_TOP = (24, 29, 42)
COLOR_BG_BOTTOM = (30, 36, 50)
COLOR_GOLD = (212, 175, 55)
COLOR_GOLD_DIM = (160, 130, 45)
COLOR_TEXT = (245, 245, 248)
COLOR_TEXT_SEC = (165, 170, 185)
COLOR_PANEL = (38, 44, 58)
COLOR_PANEL_BORDER = (65, 75, 95)
COLOR_BOARD_FRAME = (210, 198, 175)
COLOR_CELL = (248, 242, 230)
COLOR_CELL_LINE = (110, 95, 78)
COLOR_P1 = (192, 57, 43)
COLOR_P2 = (41, 128, 185)
COLOR_SELECTED = (212, 175, 55)
COLOR_CAPTURE_HIGHLIGHT = (100, 200, 120)
COLOR_WIN_GOLD = (255, 215, 80)
COLOR_LOSE_MUTED = (140, 150, 170)
COLOR_DECO_ACCENT = (255, 200, 120)
COLOR_ACCENT_GREEN = (110, 185, 130)
COLOR_ACCENT_LOSE = (200, 120, 120)
COLOR_BTN_OK = (60, 140, 90)
COLOR_BTN_OK_H = (80, 170, 110)
COLOR_BTN_BG = (32, 38, 52)
COLOR_INPUT = (26, 31, 44)
COLOR_BTN_DANGER = (160, 55, 55)
COLOR_BTN_DANGER_H = (190, 70, 70)
COLOR_BTN_NEUTRAL = (70, 130, 180)
COLOR_BTN_NEUTRAL_H = (90, 150, 210)
COLOR_CELL_WAIT = (210, 200, 188)
COLOR_CARD_SHADE = (22, 27, 38)


def _draw_background(screen: pygame.Surface, lay: UiLayout) -> None:
    """Gradiente vertical suave (evita faixa horizontal no meio da tela)."""
    w, h = lay.sw, lay.sh
    top_c = COLOR_BG_TOP
    bot_c = COLOR_BG_BOTTOM
    bands = max(64, min(200, h // 5))
    for i in range(bands):
        y0 = i * h // bands
        y1 = (i + 1) * h // bands
        if y1 <= y0:
            continue
        t = ((y0 + y1) * 0.5) / max(1, h - 1)
        r = int(top_c[0] + (bot_c[0] - top_c[0]) * t)
        g = int(top_c[1] + (bot_c[1] - top_c[1]) * t)
        b = int(top_c[2] + (bot_c[2] - top_c[2]) * t)
        pygame.draw.rect(screen, (r, g, b), (0, y0, w, y1 - y0))


def _draw_star(
    surface: pygame.Surface,
    cx: float,
    cy: float,
    outer: float,
    color: tuple[int, int, int],
) -> None:
    inner = outer * 0.42
    pts: list[tuple[float, float]] = []
    for i in range(10):
        r = outer if i % 2 == 0 else inner
        ang = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    pygame.draw.polygon(surface, color, pts)


def _draw_title_bar(screen: pygame.Surface, font_title: pygame.font.Font, lay: UiLayout) -> None:
    t = font_title.render("DARA", True, COLOR_GOLD)
    screen.blit(t, (lay.sw // 2 - t.get_width() // 2, 12))
    for i in range(4):
        _draw_star(screen, float(lay.sw - 46 - i * 22), 34.0, 7.0, COLOR_GOLD_DIM)
    pygame.draw.line(
        screen,
        COLOR_PANEL_BORDER,
        (STATUS_CARD_PAD_X, TITLE_BAR_H - 4),
        (lay.sw - STATUS_CARD_PAD_X, TITLE_BAR_H - 4),
        1,
    )
    pygame.draw.line(
        screen,
        COLOR_GOLD_DIM,
        (STATUS_CARD_PAD_X, TITLE_BAR_H - 3),
        (lay.sw - STATUS_CARD_PAD_X, TITLE_BAR_H - 3),
        1,
    )


def _draw_status_card(
    screen: pygame.Surface,
    font_panel: pygame.font.Font,
    font_ui: pygame.font.Font,
    font_small: pygame.font.Font,
    my_player: int | None,
    status_line: str,
    status_hint: str,
    lay: UiLayout,
    player_alias: str | None = None,
) -> None:
    """Cartão único de situação (mesma linguagem visual do fim de jogo)."""
    y = TITLE_BAR_H + STATUS_CARD_TOP
    card = pygame.Rect(
        STATUS_CARD_PAD_X,
        y,
        lay.sw - 2 * STATUS_CARD_PAD_X,
        STATUS_CARD_H,
    )
    pygame.draw.rect(screen, COLOR_PANEL, card, border_radius=12)
    pygame.draw.rect(screen, COLOR_PANEL_BORDER, card, 1, border_radius=12)
    inner_x = card.x + 14
    inner_y = card.y + 12
    gap_main = 8
    gap_small = 6

    def advance_after(surf: pygame.Surface, gap: int) -> None:
        nonlocal inner_y
        inner_y += surf.get_height() + gap

    if my_player is None:
        lab = font_panel.render("Conexão", True, COLOR_GOLD)
        screen.blit(lab, (inner_x, inner_y))
        advance_after(lab, gap_main)
        s1 = font_ui.render(status_line[:96], True, COLOR_TEXT)
        screen.blit(s1, (inner_x, inner_y))
        advance_after(s1, gap_main)
        if status_hint:
            s2 = font_small.render(status_hint[:108], True, COLOR_TEXT_SEC)
            screen.blit(s2, (inner_x, inner_y))
    else:
        lab = font_panel.render("Situação", True, COLOR_GOLD)
        screen.blit(lab, (inner_x, inner_y))
        advance_after(lab, gap_main)
        if player_alias:
            pj = font_ui.render(
                f"{player_alias}  ·  peça {my_player}",
                True,
                COLOR_TEXT_SEC,
            )
        else:
            pj = font_ui.render(f"Você é o Jogador {my_player}", True, COLOR_TEXT_SEC)
        screen.blit(pj, (inner_x, inner_y))
        advance_after(pj, gap_small)
        s1 = font_ui.render(status_line[:96], True, COLOR_TEXT)
        screen.blit(s1, (inner_x, inner_y))
        advance_after(s1, gap_main)
        if status_hint:
            s2 = font_small.render(status_hint[:108], True, COLOR_TEXT_SEC)
            screen.blit(s2, (inner_x, inner_y))


def _draw_header_mood(
    surface: pygame.Surface,
    mood: str,
    ticks: int,
    lay: UiLayout,
) -> None:
    # À esquerda, para não sobrepor as estrelas do título (canto direito).
    rx = min(96, lay.sw // 5)
    ry = 30
    if mood == "victory":
        pulse = 0.85 + 0.15 * math.sin(ticks / 200)
        s = int(12 * pulse)
        _draw_star(surface, rx - 24, ry - 6, s, COLOR_WIN_GOLD)
        _draw_star(surface, rx, ry - 14, int(9 * pulse), (255, 235, 150))
        _draw_star(surface, rx + 22, ry - 4, int(10 * pulse), COLOR_DECO_ACCENT)
    elif mood == "defeat":
        pygame.draw.circle(surface, COLOR_LOSE_MUTED, (rx - 18, ry - 10), 3)
        pygame.draw.circle(surface, COLOR_LOSE_MUTED, (rx + 18, ry - 10), 3)
        rect = pygame.Rect(rx - 20, ry - 2, 40, 24)
        pygame.draw.arc(surface, COLOR_LOSE_MUTED, rect, math.pi * 0.15, math.pi * 0.85, 2)
    elif mood == "waiting":
        phase_dot = (ticks // 350) % 4
        for i in range(3):
            col = COLOR_DECO_ACCENT if (i < phase_dot or phase_dot == 3) else (80, 90, 110)
            pygame.draw.circle(surface, col, (rx - 18 + i * 18, ry - 6), 5)
    elif mood == "opponent_capture":
        pygame.draw.polygon(
            surface, (180, 140, 90), [(rx, ry - 18), (rx + 6, ry - 4), (rx - 6, ry - 4)]
        )
        pygame.draw.circle(surface, COLOR_TEXT_SEC, (rx, ry + 4), 9, 2)
    elif mood == "capture":
        pygame.draw.line(surface, (220, 100, 90), (rx - 16, ry - 12), (rx + 16, ry + 4), 2)
        pygame.draw.line(surface, (90, 140, 220), (rx + 16, ry - 12), (rx - 16, ry + 4), 2)
    elif mood == "place":
        pygame.draw.circle(surface, COLOR_GOLD, (rx, ry - 4), 14, 2)
        pygame.draw.circle(surface, COLOR_GOLD, (rx, ry - 4), 5, 2)
    elif mood == "move":
        pygame.draw.polygon(
            surface, COLOR_GOLD, [(rx - 18, ry - 12), (rx + 12, ry), (rx - 18, ry + 12)]
        )
    elif mood == "connecting":
        t = ticks / 280
        for i in range(3):
            yoff = int(4 * math.sin(t + i * 0.9))
            pygame.draw.circle(surface, COLOR_GOLD, (rx - 18 + i * 18, ry - 6 + yoff), 4)
    elif mood == "neutral":
        pygame.draw.circle(surface, COLOR_TEXT_SEC, (rx, ry - 6), 7, 2)


def _board_inner_size(lay: UiLayout) -> tuple[int, int]:
    cs, cg = lay.cell_size, lay.cell_gap
    bw = COLS * cs + (COLS - 1) * cg
    bh = ROWS * cs + (ROWS - 1) * cg
    return bw, bh


def _board_pixel_origin(
    board_top_y: int, with_side_panel: bool, lay: UiLayout
) -> tuple[int, int]:
    bw, _ = _board_inner_size(lay)
    if with_side_panel:
        cluster_w = bw + lay.board_side_gap + lay.side_panel_w
    else:
        cluster_w = bw
    ox = (lay.sw - cluster_w) // 2
    return ox, board_top_y


def _side_panel_rect(board_top_y: int, lay: UiLayout) -> pygame.Rect:
    ox, oy = _board_pixel_origin(board_top_y, True, lay)
    bw, bh = _board_inner_size(lay)
    x = ox + bw + lay.board_side_gap
    top = oy - FRAME_PAD
    return pygame.Rect(x, top, lay.side_panel_w, bh + 2 * FRAME_PAD)


def _cell_rect(
    row: int, col: int, board_top_y: int, with_side_panel: bool, lay: UiLayout
) -> pygame.Rect:
    ox, oy = _board_pixel_origin(board_top_y, with_side_panel, lay)
    cs, cg = lay.cell_size, lay.cell_gap
    x = ox + col * (cs + cg)
    y = oy + row * (cs + cg)
    return pygame.Rect(x, y, cs, cs)


def _footer_button_row_y(lay: UiLayout) -> int:
    return lay.sh - FOOTER_BTN_MARGIN - BUTTON_ROW_H


def _rematch_button_rect(lay: UiLayout) -> pygame.Rect:
    y = _footer_button_row_y(lay)
    return pygame.Rect(lay.sw // 2 - 110, y, 220, BUTTON_ROW_H - 2)


def _draw_trophy(screen: pygame.Surface, cx: int, cy: int) -> None:
    cup_w, cup_h = 34, 26
    pygame.draw.rect(
        screen,
        COLOR_GOLD,
        (cx - cup_w // 2, cy - cup_h // 2, cup_w, cup_h),
        border_radius=6,
        width=2,
    )
    pygame.draw.rect(screen, COLOR_GOLD, (cx - 5, cy + cup_h // 2 - 2, 10, 12))
    pygame.draw.rect(
        screen, COLOR_GOLD, (cx - 16, cy + cup_h // 2 + 8, 32, 4), border_radius=2
    )


def _draw_game_over_banner(
    screen: pygame.Surface,
    font_hero: pygame.font.Font,
    font_ui: pygame.font.Font,
    font_small: pygame.font.Font,
    winner: int,
    my_player: int,
    lay: UiLayout,
    winner_label: str,
) -> None:
    y0 = TITLE_BAR_H + 4
    cx = lay.sw // 2
    i_won = winner == my_player
    if i_won:
        _draw_trophy(screen, cx, y0 + 26)
        y0 += 52
        hero = font_hero.render("Vitória!", True, COLOR_GOLD)
        screen.blit(hero, (cx - hero.get_width() // 2, y0))
        y0 += 44
        sub = font_ui.render(
            f"{winner_label} venceu a partida", True, COLOR_TEXT
        )
        screen.blit(sub, (cx - sub.get_width() // 2, y0))
        y0 += 28
        hint = font_small.render(
            "Troféu mental desbloqueado — você dominou o Dara!", True, COLOR_TEXT_SEC
        )
        screen.blit(hint, (cx - hint.get_width() // 2, y0))
    else:
        y0 += 8
        hero = font_hero.render("Derrota", True, COLOR_ACCENT_LOSE)
        screen.blit(hero, (cx - hero.get_width() // 2, y0))
        y0 += 44
        sub = font_ui.render(
            f"{winner_label} venceu a partida", True, COLOR_TEXT
        )
        screen.blit(sub, (cx - sub.get_width() // 2, y0))
        y0 += 28
        hint = font_small.render(
            "Boa luta — cada partida é treino de mestre.", True, COLOR_TEXT_SEC
        )
        screen.blit(hint, (cx - hint.get_width() // 2, y0))


def _peer_nick(peer_nicks: dict[int, str], player_id: int) -> str:
    n = peer_nicks.get(player_id, "").strip()
    return n if n else f"Jogador {player_id}"


def _compute_board_top_y(my_player: int | None, winner: int | None) -> int:
    return TITLE_BAR_H + _header_block_below_title(my_player, winner)


def _layout_chat_and_board_top(
    board_top_y: int,
    with_side_panel: bool,
    lay: UiLayout,
) -> tuple[int, int]:
    """
    Garante que o chat fique acima da fila de botões e, se preciso, sobe o tabuleiro.
    """
    floor_top = board_top_y
    _, board_h = _board_inner_size(lay)
    frame_total = FRAME_PAD * 2
    max_chat_bottom = lay.sh - lay.footer_reserve
    max_chat_y = max_chat_bottom - lay.chat_panel_h

    _, oy = _board_pixel_origin(board_top_y, with_side_panel, lay)
    cluster_bottom = oy + board_h + frame_total
    chat_y = min(cluster_bottom + BOARD_ABOVE_CHAT_GAP, max_chat_y)
    max_board_top = chat_y - BOARD_ABOVE_CHAT_GAP - board_h - frame_total
    board_top_y = max(floor_top, min(board_top_y, int(max_board_top)))
    _, oy2 = _board_pixel_origin(board_top_y, with_side_panel, lay)
    cluster_bottom2 = oy2 + board_h + frame_total
    chat_y = min(cluster_bottom2 + BOARD_ABOVE_CHAT_GAP, max_chat_y)
    return board_top_y, chat_y


def _draw_side_panel(
    screen: pygame.Surface,
    board_top_y: int,
    font_panel: pygame.font.Font,
    font_ui: pygame.font.Font,
    font_small: pygame.font.Font,
    phase: Phase,
    winner: int | None,
    my_player: int | None,
    match_started_ts: float | None,
    match_ended_ts: float | None,
    stats_you: tuple[int, int],
    lay: UiLayout,
    peer_nicks: dict[int, str],
) -> None:
    pr = _side_panel_rect(board_top_y, lay)
    pygame.draw.rect(screen, COLOR_PANEL, pr, border_radius=14)
    pygame.draw.rect(screen, COLOR_PANEL_BORDER, pr, 2, border_radius=14)
    x0 = pr.x + 14
    y = pr.y + 14

    t = font_panel.render("Resumo da partida", True, COLOR_GOLD)
    screen.blit(t, (x0, y))
    y += 26
    if my_player is None:
        screen.blit(font_ui.render("Fase: —", True, COLOR_TEXT_SEC), (x0, y))
    else:
        fase_nome = "Colocação" if phase == Phase.PLACEMENT else "Movimentação"
        screen.blit(font_ui.render(f"Fase: {fase_nome}", True, COLOR_TEXT), (x0, y))
    y += 22
    if match_started_ts is None:
        screen.blit(
            font_small.render("Duração: após 1ª peça", True, COLOR_TEXT_SEC),
            (x0, y),
        )
        y += 20
    else:
        dt = datetime.datetime.fromtimestamp(match_started_ts)
        screen.blit(
            font_small.render(f"Início: {dt.strftime('%d/%m %H:%M')}", True, COLOR_TEXT_SEC),
            (x0, y),
        )
        y += 20
        if match_ended_ts is not None:
            elapsed = max(0.0, match_ended_ts - match_started_ts)
        else:
            elapsed = max(0.0, time.time() - match_started_ts)
        em, es = int(elapsed // 60), int(elapsed % 60)
        screen.blit(
            font_ui.render(f"Duração: {em:02d}:{es:02d}", True, COLOR_TEXT),
            (x0, y),
        )
        y += 24
    first_label = _peer_nick(peer_nicks, 1)
    screen.blit(
        font_small.render(f"Primeiro a jogar: {first_label}", True, COLOR_TEXT_SEC),
        (x0, y),
    )
    y += 22
    if my_player is None:
        screen.blit(
            font_small.render("Partida: aguardando…", True, COLOR_TEXT_SEC),
            (x0, y),
        )
        y += 28
    elif winner is not None:
        lbl = font_ui.render("Resultado: ", True, COLOR_TEXT)
        screen.blit(lbl, (x0, y))
        ox = x0 + lbl.get_width()
        if winner == my_player:
            screen.blit(
                font_ui.render("Vitória", True, COLOR_ACCENT_GREEN),
                (ox, y),
            )
        else:
            screen.blit(
                font_ui.render("Derrota", True, COLOR_ACCENT_LOSE),
                (ox, y),
            )
        y += 30
    else:
        screen.blit(
            font_small.render("Partida em andamento.", True, COLOR_TEXT_SEC),
            (x0, y),
        )
        y += 24

    pygame.draw.line(screen, COLOR_PANEL_BORDER, (x0, y), (pr.right - 14, y), 1)
    y += 12
    screen.blit(font_panel.render("Placar da sessão", True, COLOR_GOLD), (x0, y))
    y += 26
    sw, sl = stats_you
    line = f"{sw} vit.  ·  {sl} der."
    screen.blit(font_ui.render(line, True, COLOR_TEXT), (x0, y))
    for i in range(min(sw, 3)):
        _draw_star(screen, float(pr.right - 34 - i * 15), float(y - 2), 5, COLOR_GOLD_DIM)


def _chat_input_rect(chat_y: int, lay: UiLayout) -> pygame.Rect:
    mx = lay.margin_x
    panel = pygame.Rect(mx, chat_y, lay.sw - 2 * mx, lay.chat_panel_h)
    inner_l = panel.x + 14
    bottom_line = panel.bottom - CHAT_PANEL_BOTTOM_PAD
    return pygame.Rect(
        inner_l - 2,
        bottom_line - CHAT_INPUT_H,
        panel.width - 28 - CHAT_INPUT_H - 8,
        CHAT_INPUT_H,
    )


def _nickname_gate_layout(lay: UiLayout) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
    cw, ch = 440, 218
    card = pygame.Rect(lay.sw // 2 - cw // 2, lay.sh // 2 - ch // 2, cw, ch)
    x0 = card.x + 24
    y_in = card.y + 20 + 28 + 36
    input_rect = pygame.Rect(x0, y_in, card.width - 48, 36)
    confirm_rect = pygame.Rect(card.centerx - 130, input_rect.bottom + 22, 260, 40)
    return card, input_rect, confirm_rect


def _draw_nickname_gate(
    screen: pygame.Surface,
    lay: UiLayout,
    font_ui: pygame.font.Font,
    font_small: pygame.font.Font,
    nick_buffer: str,
    nick_input_focus: bool,
    ticks: int,
    mouse_xy: tuple[int, int],
) -> None:
    card, input_rect, confirm_rect = _nickname_gate_layout(lay)
    veil = pygame.Surface((lay.sw, lay.sh), pygame.SRCALPHA)
    veil.fill((12, 16, 26, 210))
    screen.blit(veil, (0, 0))
    pygame.draw.rect(screen, COLOR_PANEL, card, border_radius=16)
    pygame.draw.rect(screen, COLOR_GOLD_DIM, card, 2, border_radius=16)
    x0 = card.x + 24
    y = card.y + 20
    screen.blit(font_ui.render("Nome no jogo", True, COLOR_GOLD), (x0, y))
    y += 28
    screen.blit(
        font_small.render(
            "Aparece no chat. Opcional — até 20 caracteres.",
            True,
            COLOR_TEXT_SEC,
        ),
        (x0, y),
    )
    pygame.draw.rect(screen, COLOR_INPUT, input_rect, border_radius=8)
    pygame.draw.rect(screen, COLOR_PANEL_BORDER, input_rect, 1, border_radius=8)
    text_y = input_rect.y + (input_rect.height - font_ui.get_height()) // 2
    ts = font_ui.render(nick_buffer, True, COLOR_TEXT)
    screen.blit(ts, (input_rect.x + 10, text_y))
    if nick_input_focus and (ticks // 530) % 2 == 0:
        caretx = input_rect.x + 10 + ts.get_width()
        pygame.draw.rect(screen, COLOR_GOLD, (caretx, text_y, 2, font_ui.get_height()))
    hov_c = confirm_rect.collidepoint(mouse_xy)
    _draw_styled_button(
        screen,
        confirm_rect,
        "Entrar na partida",
        font_small,
        hov_c,
        COLOR_BTN_OK,
        COLOR_BTN_OK_H,
    )


def _draw_styled_button(
    screen: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    hover: bool,
    fill: tuple[int, int, int],
    fill_hover: tuple[int, int, int],
    border: tuple[int, int, int] = COLOR_GOLD_DIM,
) -> None:
    bg = fill_hover if hover else fill
    pygame.draw.rect(screen, bg, rect, border_radius=10)
    pygame.draw.rect(screen, border, rect, 1, border_radius=10)
    surf = font.render(label, True, COLOR_TEXT)
    screen.blit(surf, surf.get_rect(center=rect.center))


def _draw_chat_panel(
    screen: pygame.Surface,
    chat_y: int,
    font_small: pygame.font.Font,
    font_ui: pygame.font.Font,
    chat_input: str,
    chat_lines: list[str],
    lay: UiLayout,
    chat_focused: bool,
    ticks: int,
) -> None:
    mx = lay.margin_x
    rect = pygame.Rect(mx, chat_y, lay.sw - 2 * mx, lay.chat_panel_h)
    pygame.draw.rect(screen, COLOR_PANEL, rect, border_radius=14)
    pygame.draw.rect(screen, COLOR_PANEL_BORDER, rect, 2, border_radius=14)

    inner_l = rect.x + 14
    title_s = font_ui.render("Chat", True, COLOR_GOLD)
    screen.blit(title_s, (inner_l, rect.y + CHAT_PANEL_TOP_PAD))

    input_rect = _chat_input_rect(chat_y, lay)
    messages_bottom = input_rect.top - CHAT_GAP_ABOVE_INPUT
    lines_top = rect.y + CHAT_PANEL_TOP_PAD + CHAT_TITLE_BELOW_TOP

    clip_h = messages_bottom - lines_top + 2
    prev_clip = screen.get_clip()
    if clip_h > 4:
        messages_clip = pygame.Rect(
            inner_l - 2,
            max(0, lines_top - 2),
            max(1, rect.width - 24),
            clip_h,
        )
        screen.set_clip(messages_clip)

    visible = chat_lines[-CHAT_VISIBLE_LINES:] if chat_lines else []
    line_h = max(CHAT_LINE_H, font_small.get_height() + 2)
    if not visible:
        pl = font_small.render("Nenhuma mensagem ainda.", True, COLOR_TEXT_SEC)
        if pl.get_height() + lines_top <= messages_bottom:
            screen.blit(pl, (inner_l, lines_top))
    else:
        y = lines_top
        for line in visible:
            if y + font_small.get_height() > messages_bottom:
                break
            col = COLOR_TEXT if line.startswith("Você:") else COLOR_TEXT_SEC
            surf = font_small.render(line[:88], True, col)
            screen.blit(surf, (inner_l, y))
            y += line_h

    if clip_h > 4:
        screen.set_clip(prev_clip)

    pygame.draw.rect(screen, COLOR_INPUT, input_rect, border_radius=8)
    pygame.draw.rect(screen, COLOR_PANEL_BORDER, input_rect, 1, border_radius=8)
    v_pad = max(5, (CHAT_INPUT_H - font_small.get_height()) // 2)
    text_x = input_rect.x + 8
    text_y = input_rect.y + v_pad
    if chat_input:
        ts = font_small.render(chat_input, True, COLOR_TEXT)
        screen.blit(ts, (text_x, text_y))
        text_w = ts.get_width()
    elif chat_focused:
        text_w = 0
    else:
        ph = font_small.render("Enter para enviar", True, COLOR_TEXT_SEC)
        screen.blit(ph, (text_x, text_y))
        text_w = 0
    if chat_focused and (ticks // 530) % 2 == 0:
        ch = font_small.get_height()
        caretx = min(text_x + text_w, input_rect.right - 6)
        pygame.draw.rect(screen, COLOR_GOLD, (caretx, text_y, 2, ch))

    send_r = pygame.Rect(
        input_rect.right + 6,
        input_rect.y,
        CHAT_INPUT_H,
        CHAT_INPUT_H,
    )
    pygame.draw.rect(screen, COLOR_BTN_BG, send_r, border_radius=8)
    pygame.draw.rect(screen, COLOR_GOLD_DIM, send_r, 1, border_radius=8)
    sx, sy = send_r.centerx, send_r.centery
    pygame.draw.polygon(
        screen, COLOR_GOLD, [(sx - 4, sy), (sx + 6, sy - 3), (sx + 6, sy + 3)]
    )


def run_ui(session: Any) -> None:
    # session: DaraPyroSession (on_message + métodos remotos). Any evita imports circulares.
    pygame.init()
    try:
        pygame.display.set_caption("Dara — F11 tela cheia")
        _win_flags = pygame.RESIZABLE
        screen = pygame.display.set_mode(
            (INITIAL_WINDOW_W, INITIAL_WINDOW_H),
            _win_flags,
        )
        clock = pygame.time.Clock()

        try:
            font_title = pygame.font.SysFont("georgia", 36, bold=True)
            font_hero = pygame.font.SysFont("georgia", 38, bold=True)
            font_panel = pygame.font.SysFont("helvetica", 17, bold=True)
            font_ui = pygame.font.SysFont("helvetica", 17)
            font_small = pygame.font.SysFont("helvetica", 14)
            font_piece = pygame.font.SysFont("helvetica", 28, bold=True)
        except OSError:
            font_title = pygame.font.Font(None, 40)
            font_hero = pygame.font.Font(None, 44)
            font_panel = pygame.font.Font(None, 20)
            font_ui = pygame.font.Font(None, 20)
            font_small = pygame.font.Font(None, 17)
            font_piece = pygame.font.Font(None, 32)

        # Ponte thread de rede → thread principal Pygame (fila thread-safe).
        msg_queue: queue.Queue[dict] = queue.Queue()

        def on_net(msg: dict) -> None:
            msg_queue.put(msg)

        session.on_message(on_net)

        my_player: int | None = None
        board: list[list[int | None]] = [[None] * COLS for _ in range(ROWS)]
        phase = Phase.PLACEMENT
        current_turn: int | None = None
        winner: int | None = None
        awaiting_capture = False
        selected: tuple[int, int] | None = None
        status_line = "Conectando ao servidor…"
        status_hint = "Só um instante — o tabuleiro já vem!"
        chat_lines: list[str] = []
        chat_input = ""
        chat_focused = False
        resign_confirm = False
        resign_timer = 0
        match_started_ts: float | None = None
        match_ended_ts: float | None = None
        nickname_done = False
        nick_buffer = ""
        nick_gate_focus = True
        chosen_nick = ""
        peer_nicks: dict[int, str] = {}
        stats_you = (0, 0)
        stats_opp = (0, 0)
        rematch_votes: set[int] = set()
        board_top_y = _compute_board_top_y(None, None)
        resign_rect = pygame.Rect(0, 0, 1, 1)
        resign2_rect = pygame.Rect(0, 0, 1, 1)

        running = True
        mouse_pos = (0, 0)

        def set_status(main: str, hint: str = "") -> None:
            nonlocal status_line, status_hint
            status_line = main
            status_hint = hint

        def apply_state(msg: dict) -> None:
            nonlocal board, phase, current_turn, winner, status_line, status_hint, awaiting_capture, selected
            nonlocal match_started_ts, match_ended_ts, stats_you, stats_opp, rematch_votes, peer_nicks
            bd = msg.get("board", [])
            for r, row in enumerate(bd):
                for c, cell in enumerate(row):
                    if r < ROWS and c < COLS:
                        board[r][c] = cell
            phase = Phase(msg.get("phase", Phase.PLACEMENT.value))
            current_turn = msg.get("currentTurn")
            w = msg.get("winner")
            winner = int(w) if w is not None else None
            awaiting_capture = bool(msg.get("awaitingCapture", False))
            if awaiting_capture:
                selected = None
            if "matchStartedAt" in msg:
                mst = msg["matchStartedAt"]
                match_started_ts = float(mst) if mst is not None else None
            if "matchEndedAt" in msg:
                met = msg.get("matchEndedAt")
                match_ended_ts = float(met) if met is not None else None
            raw_nn = msg.get("nicknames")
            if isinstance(raw_nn, dict):
                new_nicks: dict[int, str] = {}
                for k, v in raw_nn.items():
                    try:
                        pid = int(k)
                    except (TypeError, ValueError):
                        continue
                    s = str(v).strip() if v is not None else ""
                    new_nicks[pid] = s if s else f"Jogador {pid}"
                peer_nicks = new_nicks
            sb = msg.get("statsByPlayer")
            if sb is not None and my_player is not None:
                me = str(my_player)
                d_me = sb.get(me) or {}
                stats_you = (int(d_me.get("wins", 0)), int(d_me.get("losses", 0)))
                opp = str(3 - my_player)
                d_opp = sb.get(opp) or {}
                stats_opp = (int(d_opp.get("wins", 0)), int(d_opp.get("losses", 0)))
            rv = msg.get("rematchVotes")
            if rv is not None:
                rematch_votes = {int(x) for x in rv}
            if winner is not None and my_player is not None:
                if winner == my_player:
                    set_status(
                        "Vitória! Você brilhou no tabuleiro!",
                        "Troféu mental desbloqueado — você dominou o Dara!",
                    )
                    pygame.display.set_caption("Dara — Campeão!")
                else:
                    set_status(
                        "Boa luta! Desta vez o adversário levou a melhor.",
                        "Não desanime: cada partida é treino de mestre.",
                    )
                    pygame.display.set_caption("Dara — Até a próxima!")
            elif current_turn == my_player:
                if phase == Phase.PLACEMENT:
                    set_status(
                        "Sua vez — escolha onde colocar a peça!",
                        "Evite formar linha de 3 na colocação; pense duas jogadas à frente.",
                    )
                elif awaiting_capture:
                    set_status(
                        "Linha de três! Hora de brilhar!",
                        "Clique numa peça adversária (contorno verde) para capturar.",
                    )
                else:
                    set_status(
                        "Sua jogada — mova com estratégia!",
                        "Clique na sua peça e depois numa casa vazia ao lado. Linha de 4 é proibida.",
                    )
            else:
                if awaiting_capture:
                    set_status(
                        "O adversário está escolhendo a captura…",
                        "Observe: a peça que remover pode mudar tudo.",
                    )
                else:
                    set_status(
                        "Aguarde o oponente jogar.",
                        "Respire fundo, planeje a resposta… ou mande um alô no chat!",
                    )

        def register_nickname() -> None:
            nonlocal nickname_done, nick_buffer, chosen_nick
            if nickname_done:
                return
            chosen_nick = nick_buffer.strip()[:NICKNAME_MAX_LEN]
            try:
                session.registar_apelido(chosen_nick)
            except Exception as exc:
                set_status(
                    "Não foi possível registar no servidor.",
                    str(exc)[:120],
                )
                return
            nickname_done = True

        def process_network() -> None:
            # Chamado a cada frame: drena mensagens acumuladas desde o último frame.
            nonlocal my_player, chat_lines
            while True:
                try:
                    msg = msg_queue.get_nowait()
                except queue.Empty:
                    break
                kind = msg.get("type")
                if kind == MessageType.START.value:
                    p = msg.get("player")
                    my_player = int(p) if p is not None else None
                    if my_player is not None:
                        session.bind_player_id(my_player)
                    pygame.display.set_caption(f"Dara — Jogador {my_player}")
                    apply_state(msg)
                    set_status(
                        "Partida em andamento!",
                        "Boa sorte — que vença o mais astuto!",
                    )
                elif kind == MessageType.STATE.value:
                    apply_state(msg)
                elif kind == MessageType.CHAT.value:
                    fid = msg.get("from", "?")
                    text = str(msg.get("text", ""))
                    onick = str(msg.get("nick", "")).strip()
                    if fid != my_player:
                        label = onick if onick else f"Jogador {fid}"
                        chat_lines.append(f"{label}: {text}")
                        while len(chat_lines) > CHAT_LINES_MAX:
                            chat_lines.pop(0)
                elif kind == MessageType.ERROR.value:
                    set_status(
                        "Ops — " + str(msg.get("message", "")),
                        "Veja a dica abaixo no seu turno ou tente outra casa.",
                    )

        def cell_from_mouse(
            mx: int,
            my: int,
            lay: UiLayout,
            bty: int,
        ) -> tuple[int, int] | None:
            wsp = my_player is not None
            for r in range(ROWS):
                for c in range(COLS):
                    if _cell_rect(r, c, bty, wsp, lay).collidepoint(mx, my):
                        return r, c
            return None

        def send_chat() -> None:
            nonlocal chat_input
            if not nickname_done:
                return
            t = chat_input.strip()
            if not t:
                return
            session.enviar_mensagem(t)
            chat_lines.append(f"Você: {t}")
            while len(chat_lines) > CHAT_LINES_MAX:
                chat_lines.pop(0)
            chat_input = ""

        def click_cell(row: int, col: int) -> None:
            nonlocal selected
            if my_player is None or current_turn is None or winner is not None:
                return
            if current_turn != my_player:
                set_status(
                    "Calma — ainda não é a sua vez!",
                    "Veja o ícone ao lado: é a vez do oponente.",
                )
                return
            cell = board[row][col]
            if phase == Phase.PLACEMENT:
                if cell is None:
                    session.colocar_peca(row, col)
                else:
                    set_status(
                        "Essa casa já está ocupada!",
                        "Procure um quadrado vazio no tabuleiro.",
                    )
                return
            if awaiting_capture:
                opponent = 3 - my_player
                if cell == opponent:
                    session.escolher_captura(row, col)
                else:
                    set_status(
                        "Você precisa clicar numa peça do adversário!",
                        "As peças com contorno verde podem ser capturadas.",
                    )
                return
            if selected is None:
                if cell == my_player:
                    selected = (row, col)
                    set_status(
                        "Peça escolhida! Agora o movimento.",
                        "Clique numa casa vazia ao lado (cima, baixo, esquerda ou direita).",
                    )
                else:
                    set_status(
                        "Primeiro escolha uma das SUAS peças.",
                        "São as bolas com o seu número (1 ou 2).",
                    )
                return
            sr, sc = selected
            if (row, col) == (sr, sc):
                selected = None
                set_status("Seleção cancelada.", "Escolha outra peça quando quiser.")
                return
            if cell is None and abs(sr - row) + abs(sc - col) == 1:
                session.mover_peca(sr, sc, row, col)
                selected = None
            else:
                set_status(
                    "Esse movimento não vale!",
                    "Só para casa vazia e ao lado. Lembre-se: linha de 4 na movimentação é proibida.",
                )

        while running:
            # --- frame: geometria → rede → eventos → desenho ---
            sw, sh = screen.get_size()
            lay = build_ui_layout(sw, sh, my_player=my_player, winner=winner)
            mouse_pos = pygame.mouse.get_pos()
            with_side_panel = my_player is not None
            base_board_top = _compute_board_top_y(my_player, winner)
            board_top_y, chat_y = _layout_chat_and_board_top(
                base_board_top,
                with_side_panel,
                lay,
            )
            btn_row = _footer_button_row_y(lay)
            cx_screen = lay.sw // 2
            _bw = 120
            _bgap = 10
            if my_player is not None and winner is None and resign_confirm:
                pair_w = _bw + _bgap + _bw
                x0 = cx_screen - pair_w // 2
                resign_rect = pygame.Rect(x0, btn_row, _bw, BUTTON_ROW_H - 2)
                resign2_rect = pygame.Rect(x0 + _bw + _bgap, btn_row, _bw, BUTTON_ROW_H - 2)
            elif my_player is not None and winner is None:
                resign_rect = pygame.Rect(
                    cx_screen - _bw // 2, btn_row, _bw, BUTTON_ROW_H - 2
                )
                resign2_rect = pygame.Rect(0, 0, 1, 1)
            else:
                resign_rect = pygame.Rect(0, 0, 1, 1)
                resign2_rect = pygame.Rect(0, 0, 1, 1)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    nw, nh = event.size
                    nw, nh = max(640, nw), max(480, nh)
                    screen = pygame.display.set_mode((nw, nh), pygame.RESIZABLE)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    try:
                        pygame.display.toggle_fullscreen()
                    except pygame.error:
                        pass
                elif not nickname_done:
                    _, n_input_rect, n_confirm_rect = _nickname_gate_layout(lay)
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if n_confirm_rect.collidepoint(event.pos):
                            register_nickname()
                        elif n_input_rect.collidepoint(event.pos):
                            nick_gate_focus = True
                        else:
                            nick_gate_focus = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            register_nickname()
                        elif event.key == pygame.K_BACKSPACE:
                            nick_gate_focus = True
                            nick_buffer = nick_buffer[:-1]
                        elif (
                            event.unicode
                            and event.unicode.isprintable()
                            and len(nick_buffer) < NICKNAME_MAX_LEN
                        ):
                            nick_gate_focus = True
                            nick_buffer += event.unicode
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if winner is not None and _rematch_button_rect(lay).collidepoint(
                        event.pos
                    ):
                        session.votar_revanche()
                    elif (
                        my_player is not None
                        and resign_rect.collidepoint(event.pos)
                    ):
                        if winner is None:
                            if not resign_confirm:
                                resign_confirm = True
                                resign_timer = pygame.time.get_ticks()
                                set_status(
                                    "Desistindo…",
                                    "Clique em Confirmar para sair ou Cancelar para voltar ao jogo.",
                                )
                            else:
                                resign_confirm = False
                                if winner is None and my_player is not None:
                                    apply_state({
                                        "board": [row[:] for row in board],
                                        "phase": phase.value,
                                        "currentTurn": current_turn,
                                        "awaitingCapture": awaiting_capture,
                                        "winner": winner,
                                    })
                    elif (
                        my_player is not None
                        and resign2_rect.collidepoint(event.pos)
                        and winner is None
                        and resign_confirm
                    ):
                        session.desistir()
                        set_status("Desistência enviada.", "Obrigado por jogar — até breve!")
                        resign_confirm = False
                    elif _chat_input_rect(chat_y, lay).collidepoint(event.pos):
                        chat_focused = True
                    else:
                        hit = cell_from_mouse(event.pos[0], event.pos[1], lay, board_top_y)
                        if hit:
                            click_cell(hit[0], hit[1])
                        chat_focused = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        chat_focused = True
                        send_chat()
                    elif event.key == pygame.K_BACKSPACE:
                        chat_focused = True
                        chat_input = chat_input[:-1]
                    elif event.unicode and event.unicode.isprintable() and len(chat_input) < 120:
                        chat_focused = True
                        chat_input += event.unicode

            if resign_confirm and pygame.time.get_ticks() - resign_timer > 5000:
                resign_confirm = False
                if winner is None and my_player is not None:
                    apply_state({
                        "board": [row[:] for row in board],
                        "phase": phase.value,
                        "currentTurn": current_turn,
                        "awaitingCapture": awaiting_capture,
                        "winner": winner,
                    })

            process_network()  # aplica mensagens da thread de rede antes de desenhar

            _draw_background(screen, lay)
            _draw_title_bar(screen, font_title, lay)

            if my_player is None:
                header_mood = "connecting"
            elif winner is not None and my_player is not None:
                header_mood = "victory" if winner == my_player else "defeat"
            elif current_turn is None:
                header_mood = "neutral"
            elif current_turn != my_player:
                header_mood = "opponent_capture" if awaiting_capture else "waiting"
            elif awaiting_capture:
                header_mood = "capture"
            elif phase == Phase.PLACEMENT:
                header_mood = "place"
            else:
                header_mood = "move"
            _draw_header_mood(screen, header_mood, pygame.time.get_ticks(), lay)

            if winner is not None and my_player is not None:
                _draw_game_over_banner(
                    screen,
                    font_hero,
                    font_ui,
                    font_small,
                    winner,
                    my_player,
                    lay,
                    _peer_nick(peer_nicks, winner),
                )
            else:
                alias_me = (
                    peer_nicks.get(my_player, "").strip() or chosen_nick
                    if my_player is not None
                    else None
                )
                _draw_status_card(
                    screen,
                    font_panel,
                    font_ui,
                    font_small,
                    my_player,
                    status_line,
                    status_hint,
                    lay,
                    player_alias=alias_me if alias_me else None,
                )

            if resign_confirm and winner is None:
                band_h = TITLE_BAR_H + STATUS_CARD_TOP + STATUS_CARD_H + 10
                band = pygame.Surface((lay.sw, band_h), pygame.SRCALPHA)
                band.fill((20, 28, 40, 140))
                screen.blit(band, (0, 0))
                q = font_ui.render("Desistir mesmo? :(", True, COLOR_GOLD)
                screen.blit(q, (lay.sw // 2 - q.get_width() // 2, TITLE_BAR_H + 18))

            ox, oy = _board_pixel_origin(board_top_y, with_side_panel, lay)
            board_w, board_h = _board_inner_size(lay)
            fp = FRAME_PAD
            frame = pygame.Rect(ox - fp, oy - fp, board_w + 2 * fp, board_h + 2 * fp)
            pygame.draw.rect(screen, COLOR_BOARD_FRAME, frame, border_radius=14)
            pygame.draw.rect(screen, COLOR_PANEL_BORDER, frame, 2, border_radius=14)

            cell_idle = COLOR_CELL_WAIT if my_player is None else COLOR_CELL
            piece_r = max(8, lay.cell_size // 2 - 8)
            for r in range(ROWS):
                for c in range(COLS):
                    rect = _cell_rect(r, c, board_top_y, with_side_panel, lay)
                    pygame.draw.rect(screen, cell_idle, rect, border_radius=8)
                    pygame.draw.rect(screen, COLOR_CELL_LINE, rect, 1, border_radius=8)
                    if selected == (r, c):
                        pygame.draw.rect(screen, COLOR_SELECTED, rect, 3, border_radius=8)
                    val = board[r][c]
                    opp = 3 - my_player if my_player is not None else None
                    if (
                        awaiting_capture
                        and current_turn == my_player
                        and opp is not None
                        and val == opp
                    ):
                        pygame.draw.rect(
                            screen, COLOR_CAPTURE_HIGHLIGHT, rect, 3, border_radius=8
                        )
                    if val == 1:
                        pygame.draw.circle(
                            screen, COLOR_P1, rect.center, piece_r
                        )
                        t = font_piece.render("1", True, (255, 255, 255))
                        screen.blit(t, (t.get_rect(center=rect.center)))
                    elif val == 2:
                        pygame.draw.circle(
                            screen, COLOR_P2, rect.center, piece_r
                        )
                        t = font_piece.render("2", True, (255, 255, 255))
                        screen.blit(t, (t.get_rect(center=rect.center)))

            if my_player is not None:
                _draw_side_panel(
                    screen,
                    board_top_y,
                    font_panel,
                    font_ui,
                    font_small,
                    phase,
                    winner,
                    my_player,
                    match_started_ts,
                    match_ended_ts,
                    stats_you,
                    lay,
                    peer_nicks,
                )

            _draw_chat_panel(
                screen,
                chat_y,
                font_small,
                font_ui,
                chat_input,
                chat_lines,
                lay,
                chat_focused,
                pygame.time.get_ticks(),
            )

            mx, my = mouse_pos
            rematch_hit = _rematch_button_rect(lay)
            if winner is not None:
                i_voted = my_player is not None and my_player in rematch_votes
                opp_voted = (
                    my_player is not None and (3 - my_player) in rematch_votes
                )
                wn = int(winner) if winner is not None else None
                mp = my_player
                i_won = mp is not None and wn is not None and wn == int(mp)
                hov_rm = rematch_hit.collidepoint(mx, my)
                if i_won:
                    rematch_lbl = "Cancelar" if i_voted else "Jogar novamente"
                else:
                    rematch_lbl = "Cancelar revanche" if i_voted else "Revanche"
                _draw_styled_button(
                    screen,
                    rematch_hit,
                    rematch_lbl,
                    font_small,
                    hov_rm,
                    COLOR_BTN_OK,
                    COLOR_BTN_OK_H,
                )
                vote_hint = ""
                if i_voted and not opp_voted:
                    vote_hint = (
                        "Aguardando o oponente confirmar…"
                        if i_won
                        else "Aguardando o oponente aceitar a revanche…"
                    )
                elif opp_voted and not i_voted:
                    vote_hint = (
                        "O oponente já confirmou — clique em Jogar novamente!"
                        if i_won
                        else "O oponente já confirmou — clique em Revanche!"
                    )
                elif len(rematch_votes) == 2:
                    vote_hint = "Nova partida a começar…"
                if vote_hint:
                    vh = font_small.render(vote_hint[:90], True, COLOR_GOLD)
                    hint_y = _footer_button_row_y(lay) - 20
                    screen.blit(vh, (lay.sw // 2 - vh.get_width() // 2, hint_y))
            elif my_player is not None:
                hover_r = resign_rect.collidepoint(mx, my)
                hover_c = resign2_rect.collidepoint(mx, my) if resign_confirm else False
                _draw_styled_button(
                    screen,
                    resign_rect,
                    "Desistir" if not resign_confirm else "Cancelar",
                    font_small,
                    hover_r,
                    COLOR_BTN_DANGER,
                    COLOR_BTN_DANGER_H,
                    border=(120, 60, 60),
                )
                if resign_confirm:
                    _draw_styled_button(
                        screen,
                        resign2_rect,
                        "Confirmar",
                        font_small,
                        hover_c,
                        COLOR_BTN_NEUTRAL,
                        COLOR_BTN_NEUTRAL_H,
                        border=(100, 140, 180),
                    )

            if not nickname_done:
                _draw_nickname_gate(
                    screen,
                    lay,
                    font_ui,
                    font_small,
                    nick_buffer,
                    nick_gate_focus,
                    pygame.time.get_ticks(),
                    mouse_pos,
                )

            pygame.display.flip()
            clock.tick(60)
    finally:
        pygame.quit()
