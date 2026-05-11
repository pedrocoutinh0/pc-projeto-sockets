"""Smoke test: Name Server + daemon do jogo + dois clientes recebem START."""

from __future__ import annotations

import threading
import time
import unittest

import Pyro5.api
import Pyro5.server

from dara.client.pyro_session import DaraPyroSession
from dara.net.protocol import MessageType
from dara.net.pyro_registry import SERVIDOR_REGISTRY_NAME
from dara.server.pyro_service import ServidorDara


class TestPyroIntegration(unittest.TestCase):
    def test_two_players_receive_start_via_nameserver(self) -> None:
        ns_port = 18991
        game_port = 18990

        _, ns_daemon, _bc = Pyro5.api.start_ns(host="127.0.0.1", port=ns_port)
        ns_thread = threading.Thread(target=ns_daemon.requestLoop, daemon=True)
        ns_thread.start()
        time.sleep(0.25)

        game_container: dict = {}

        def run_game() -> None:
            serv = ServidorDara()
            gd = Pyro5.server.Daemon(host="127.0.0.1", port=game_port)
            uri = gd.register(serv, SERVIDOR_REGISTRY_NAME)
            ns_proxy = Pyro5.api.locate_ns("127.0.0.1", ns_port)
            ns_proxy.register(SERVIDOR_REGISTRY_NAME, str(uri), safe=True)
            game_container["daemon"] = gd
            gd.requestLoop()

        game_thread = threading.Thread(target=run_game, daemon=True)
        game_thread.start()
        time.sleep(0.35)

        msgs1: list = []
        msgs2: list = []

        s1 = DaraPyroSession("127.0.0.1", ns_port)
        s2 = DaraPyroSession("127.0.0.1", ns_port)
        try:
            s1.on_message(lambda m: msgs1.append(m))
            s2.on_message(lambda m: msgs2.append(m))

            self.assertEqual(s1.registar_apelido("alice"), 1)
            self.assertEqual(len(msgs1), 0)

            self.assertEqual(s2.registar_apelido("bob"), 2)

            for _ in range(80):
                if len(msgs1) >= 1 and len(msgs2) >= 1:
                    break
                time.sleep(0.03)

            self.assertTrue(len(msgs1) >= 1 and len(msgs2) >= 1)
            self.assertEqual(msgs1[0].get("type"), MessageType.START.value)
            self.assertEqual(msgs2[0].get("type"), MessageType.START.value)
        finally:
            s1.close()
            s2.close()
            gd = game_container.get("daemon")
            if gd is not None:
                gd.shutdown()
            ns_daemon.shutdown()
            game_thread.join(timeout=2)
            ns_thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
