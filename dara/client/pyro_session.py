"""
Sessão cliente Pyro: objeto local exposto ao servidor (callbacks) + proxy remoto.

O cliente não gere sockets nem monta mensagens de rede: obtém o stub através do
nome lógico no Pyro Name Server (URI PYRONAME), que resolve para o daemon real
do jogo. O método receber() no ClienteNotificador é invocado remotamente pelo
servidor (callback RMI). A UI continua a receber dicts com "type" na fila do
run_ui.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

import Pyro5.api
import Pyro5.server

from dara.net.pyro_registry import SERVIDOR_REGISTRY_NAME, normalize_ns_host

logger = logging.getLogger(__name__)


@Pyro5.server.expose
class ClienteNotificador:
    """Objeto remoto mínimo: o servidor chama receber() para empurrar mensagens."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._on_message: Callable[[dict[str, Any]], None] | None = None

    def set_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            self._on_message = callback

    def receber(self, mensagem: dict[str, Any]) -> None:
        with self._lock:
            cb = self._on_message
        if cb is not None:
            cb(mensagem)


class DaraPyroSession:
    """
    Liga o cliente ao ServidorDara e mantém um Daemon local para callbacks.

    Compatível com run_ui: on_message + métodos por operação no lugar de send().
    """

    def __init__(
        self,
        ns_host: str,
        ns_port: int,
        *,
        bind_host: str = "",
        bind_port: int = 0,
    ) -> None:
        self._player_id: int | None = None

        self._notifier = ClienteNotificador()
        self._daemon = Pyro5.server.Daemon(host=bind_host, port=bind_port)
        self._notifier_uri = str(self._daemon.register(self._notifier))
        self._daemon_thread = threading.Thread(
            target=self._daemon.requestLoop,
            name="pyro-client-daemon",
            daemon=True,
        )
        self._daemon_thread.start()

        # Resolução via Name Server: não referimos IP/porta do daemon do jogo.
        loc = normalize_ns_host(ns_host)
        if ":" in loc and not loc.startswith("["):
            loc = f"[{loc}]"
        self._servidor_uri = f"PYRONAME:{SERVIDOR_REGISTRY_NAME}@{loc}:{ns_port}"

    def _servidor_proxy(self) -> Pyro5.api.Proxy:
        """Um Proxy novo por uso evita erros de propriedade entre threads (FAQ Pyro5)."""
        return Pyro5.api.Proxy(self._servidor_uri)

    def on_message(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Regista o mesmo callback que o TcpConnection chamava por cada mensagem."""
        self._notifier.set_callback(callback)

    def close(self) -> None:
        try:
            self._daemon.shutdown()
        except Exception as e:
            logger.debug("Encerramento daemon cliente: %s", e)

    def registar_apelido(self, apelido: str) -> int:
        pid = int(self._servidor_proxy().registar(self._notifier_uri, apelido))
        self._player_id = pid
        return pid

    def bind_player_id(self, jogador: int) -> None:
        self._player_id = jogador

    def _pid(self) -> int:
        if self._player_id is None:
            raise RuntimeError("Jogador ainda não identificado.")
        return self._player_id

    def colocar_peca(self, linha: int, coluna: int) -> None:
        self._servidor_proxy().colocar_peca(self._pid(), linha, coluna)

    def mover_peca(
        self,
        origem_linha: int,
        origem_coluna: int,
        destino_linha: int,
        destino_coluna: int,
    ) -> None:
        self._servidor_proxy().mover_peca(
            self._pid(),
            origem_linha,
            origem_coluna,
            destino_linha,
            destino_coluna,
        )

    def escolher_captura(self, linha: int, coluna: int) -> None:
        self._servidor_proxy().escolher_captura(self._pid(), linha, coluna)

    def enviar_mensagem(self, texto: str) -> None:
        self._servidor_proxy().enviar_mensagem(self._pid(), texto)

    def desistir(self) -> None:
        self._servidor_proxy().desistir(self._pid())

    def votar_revanche(self) -> None:
        self._servidor_proxy().votar_revanche(self._pid())
