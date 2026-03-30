"""
Cliente: parse de argumentos → conexão TCP → loop Pygame (run_ui).

pygame.quit() no finally garante libertação mesmo se a janela fechar com erro.
"""
import argparse

import pygame

from dara.client.connection import create_connection
from dara.client.ui import run_ui


def main() -> None:
    parser = argparse.ArgumentParser(description="Cliente Dara")
    parser.add_argument("--host", default="localhost", help="Host do servidor (default: localhost)")
    parser.add_argument("--port", type=int, default=9090, help="Porta (default: 9090)")
    args = parser.parse_args()

    connection = create_connection(args.host, args.port)
    try:
        run_ui(connection)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
