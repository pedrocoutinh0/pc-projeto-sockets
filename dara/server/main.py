"""
Ponto de entrada do servidor.

Fluxo: escuta TCP → 2 clientes → GameRoom → START para cada um → 2 threads
run_handler_tcp (uma por socket). join() mantém o processo vivo até ambos
handlers terminarem (ex.: desconexão).
"""
import argparse
import logging
import threading

from dara.net.transport.tcp import create_tcp_server_endpoints
from dara.server.game_room import GameRoom
from dara.server.handler import run_handler_tcp


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Servidor Dara (TCP)")
    parser.add_argument("--host", default="", help="Host para escutar (default: todas as interfaces)")
    parser.add_argument("--port", type=int, default=9090, help="Porta (default: 9090)")
    args = parser.parse_args()

    logger = logging.getLogger(__name__)
    logger.info("Aguardando dois clientes (TCP) em %s:%s...", args.host or "*", args.port)
    endpoint1, endpoint2 = create_tcp_server_endpoints(args.host, args.port)
    logger.info("Dois clientes conectados. Iniciando partida.")

    game_room = GameRoom(endpoint1, endpoint2)
    # Cada cliente recebe o seu número (player) e snapshot inicial do tabuleiro.
    for ep in (endpoint1, endpoint2):
        ep.send(game_room.start_message(ep.player_id))

    # Paralelismo: ler um socket não bloqueia o outro; GameRoom é partilhado.
    t1 = threading.Thread(target=run_handler_tcp, args=(endpoint1, game_room), daemon=True)
    t2 = threading.Thread(target=run_handler_tcp, args=(endpoint2, game_room), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()


if __name__ == "__main__":
    main()
