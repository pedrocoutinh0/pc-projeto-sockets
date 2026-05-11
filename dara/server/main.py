"""
Ponto de entrada do servidor — comunicação exclusivamente via Pyro5 (RPC/RMI).

O daemon do jogo regista-se no Pyro Name Server sob um nome lógico; os clientes
resolvem esse nome no NS e só assim obtêm o URI do daemon (modelo em que ambos
«vêem» apenas o catálogo central).
"""
from __future__ import annotations

import argparse
import logging
import sys

import Pyro5.api
import Pyro5.errors
import Pyro5.server

from dara.net.pyro_registry import SERVIDOR_REGISTRY_NAME, normalize_ns_host
from dara.server.pyro_service import ServidorDara


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Servidor Dara (Pyro5 RPC + Name Server)")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Interface onde o daemon do jogo escuta (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Porta do daemon do jogo (default: 9090; distinta da porta do NS)",
    )
    parser.add_argument(
        "--ns-host",
        default="localhost",
        help="Host onde está o Pyro Name Server (default: localhost)",
    )
    parser.add_argument(
        "--ns-port",
        type=int,
        default=9091,
        help="Porta do Pyro Name Server (default: 9091)",
    )
    args = parser.parse_args()
    ns_host = normalize_ns_host(args.ns_host)

    logger = logging.getLogger(__name__)
    serv = ServidorDara()
    daemon = Pyro5.server.Daemon(host=args.host, port=args.port)
    uri = daemon.register(serv, SERVIDOR_REGISTRY_NAME)
    logger.info("Daemon do jogo registado localmente. URI: %s", uri)

    try:
        ns = Pyro5.api.locate_ns(host=ns_host, port=args.ns_port)
    except Pyro5.errors.NamingError as exc:
        logger.error(
            "Não foi possível contactar o Name Server em %s:%s — arranca primeiro "
            "com: python -m Pyro5.nameserver -n 0.0.0.0 -p %s (%s)",
            ns_host,
            args.ns_port,
            args.ns_port,
            exc,
        )
        sys.exit(1)

    try:
        ns.register(SERVIDOR_REGISTRY_NAME, str(uri), safe=True)
    except Pyro5.errors.NamingError:
        ns.register(SERVIDOR_REGISTRY_NAME, str(uri), safe=False)
    logger.info(
        "Nome «%s» publicado no Name Server (%s:%s).",
        SERVIDOR_REGISTRY_NAME,
        ns_host,
        args.ns_port,
    )
    try:
        daemon.requestLoop()
    finally:
        try:
            ns.remove(SERVIDOR_REGISTRY_NAME)
        except Exception as exc:
            logger.debug("Falha ao remover nome do NS no encerramento: %s", exc)


if __name__ == "__main__":
    main()
