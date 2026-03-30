"""
Transporte UDP alternativo: um datagrama ≈ um JSON completo.

Debug mental: sem conexão TCP; quem é jogador 1/2 = ordem dos endereços que
primeiro falaram com o servidor (recvfrom). O arranque padrão do projeto usa
TCP (server/main.py); para UDP seria preciso trocar main + run_udp_receiver.

Cliente UDP usa connect() ao servidor para recv/send sem sendto explícito.
"""
from __future__ import annotations

import json
import socket
import threading
from typing import Callable, Tuple

from dara.net.protocol import serialize, deserialize


class UdpClientEndpoint:
    """Endpoint UDP para um cliente no servidor. Implementa a interface ClientEndpoint."""

    def __init__(
        self,
        sock: socket.socket,
        address: Tuple[str, int],
        player_id: int,
    ) -> None:
        self._socket = sock
        self._address = address
        self._player_id = player_id
        self._closed = False
        self._lock = threading.Lock()

    @property
    def player_id(self) -> int:
        return self._player_id

    @property
    def peer_key(self) -> str:
        a = self._address
        return f"{a[0]}#{a[1]}"

    @property
    def address(self) -> Tuple[str, int]:
        return self._address

    def send(self, msg: dict) -> None:
        with self._lock:
            if self._closed:
                return
            payload = serialize(msg).encode("utf-8")
            self._socket.sendto(payload, self._address)

    def close(self) -> None:
        with self._lock:
            self._closed = True


def create_udp_server_endpoints(
    host: str = "", port: int = 9090
) -> tuple[UdpClientEndpoint, UdpClientEndpoint, socket.socket]:
    """
    Cria socket UDP, aguarda dois clientes (dois endereços distintos que enviem um datagrama)
    e retorna (endpoint1, endpoint2, socket). O socket deve ser usado em run_udp_receiver.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    addr1: Tuple[str, int] | None = None
    addr2: Tuple[str, int] | None = None
    # Descarta conteúdo dos primeiros pacotes; só interessa (addr1, addr2) distintos.
    while addr2 is None:
        data, addr = sock.recvfrom(4096)
        if addr1 is None:
            addr1 = addr
        elif addr != addr1:
            addr2 = addr
    ep1 = UdpClientEndpoint(sock, addr1, 1)
    ep2 = UdpClientEndpoint(sock, addr2, 2)
    return ep1, ep2, sock


class UdpConnection:
    """Conexão UDP do cliente ao servidor. Implementa a interface Connection."""

    def __init__(self, host: str, port: int) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.connect((host, port))
        self._callback: Callable[[dict], None] | None = None
        self._lock = threading.Lock()
        self._closed = False
        self._thread: threading.Thread | None = None

    def send(self, msg: dict) -> None:
        with self._lock:
            if self._closed:
                return
            payload = serialize(msg).encode("utf-8")
            self._socket.send(payload)

    def on_message(self, callback: Callable[[dict], None]) -> None:
        self._callback = callback
        if self._thread is None:
            self._thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._thread.start()

    def _receive_loop(self) -> None:
        try:
            while not self._closed:
                data = self._socket.recv(4096)
                if not data:
                    break
                try:
                    msg = deserialize(data.decode("utf-8"))
                    if self._callback:
                        self._callback(msg)
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                    pass
        except OSError:
            pass

    def close(self) -> None:
        self._closed = True
        try:
            self._socket.close()
        except OSError:
            pass
