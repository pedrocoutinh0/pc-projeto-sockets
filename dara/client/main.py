"""
Cliente: argumentos → sessão Pyro (proxy remoto + callback local) → UI Pygame.
"""
from __future__ import annotations

import argparse

import pygame

from dara.client.pyro_session import DaraPyroSession
from dara.client.ui import run_ui


def main() -> None:
    parser = argparse.ArgumentParser(description="Cliente Dara (Pyro5 RPC + Name Server)")
    parser.add_argument(
        "--ns-host",
        default="localhost",
        help="Host do Pyro Name Server (default: localhost)",
    )
    parser.add_argument(
        "--ns-port",
        type=int,
        default=9091,
        help="Porta do Pyro Name Server (default: 9091)",
    )
    parser.add_argument(
        "--bind-host",
        default="",
        help="Interface do daemon local de callbacks (default: todas, '')",
    )
    parser.add_argument(
        "--bind-port",
        type=int,
        default=0,
        help="Porta do daemon local de callbacks (0 = aleatória)",
    )
    args = parser.parse_args()

    session = DaraPyroSession(
        args.ns_host,
        args.ns_port,
        bind_host=args.bind_host,
        bind_port=args.bind_port,
    )
    try:
        run_ui(session)
    finally:
        session.close()
        pygame.quit()


if __name__ == "__main__":
    main()
