"""
Transporte TCP: stream com uma mensagem JSON por linha (\\n).

Debug mental: TCP não tem "mensagens" nativas — só bytes. O \\n delimita onde
corta cada JSON. Servidor: read_message() bloqueia até uma linha completa.
Cliente: thread em _receive_loop acumula buffer e parte por \\n.

Padrão do jogo: server/main.py e client/connection.py usam isto. UDP: udp.py.
"""
from __future__ import annotations

import json
import socket
import threading
from typing import Callable

from dara.net.protocol import serialize, deserialize


class TcpClientEndpoint:
    """Uma sessão TCP aceite no servidor (jogador 1 ou 2)."""

    def __init__(self, sock: socket.socket, player_id: int) -> None:
        self._socket = sock
        self._player_id = player_id
        self._closed = False
        # Lock: duas threads (handlers) podem enviar; sendall deve ser serializado.
        self._lock = threading.Lock()
        addr = sock.getpeername()
        self._peer_key = f"{addr[0]}#{addr[1]}"

    @property
    def player_id(self) -> int:
        return self._player_id

    @property
    def peer_key(self) -> str:
        """Identificador estável desta conexão (estatísticas no servidor)."""
        return self._peer_key

    def send(self, msg: dict) -> None:
        with self._lock:
            if self._closed:
                return
            line = serialize(msg) + "\n"
            self._socket.sendall(line.encode("utf-8"))

    def read_message(self) -> dict | None:
        """Uma linha = uma mensagem. Nota: 'rest' após \\n não é guardado para a próxima chamada."""
        try:
            buffer = b""
            while True:
                chunk = self._socket.recv(4096)
                if not chunk:
                    return None
                buffer += chunk
                if b"\n" in buffer:
                    line, rest = buffer.split(b"\n", 1)
                    return deserialize(line.decode("utf-8"))
        except (ConnectionResetError, OSError, json.JSONDecodeError):
            return None

    def close(self) -> None:
        with self._lock:
            self._closed = True
            try:
                self._socket.close()
            except OSError:
                pass


def create_tcp_server_endpoints(
    host: str = "", port: int = 9090
) -> tuple[TcpClientEndpoint, TcpClientEndpoint]:
    # Bloqueia até 2 accept: 1.º cliente = jogador 1, 2.º = jogador 2.
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(2)
    sock1, _ = server.accept()
    sock2, _ = server.accept()
    server.close()
    return (
        TcpClientEndpoint(sock1, 1),
        TcpClientEndpoint(sock2, 2),
    )


class TcpConnection:
    """Cliente → servidor: envia linhas JSON; recebe numa thread para não bloquear Pygame."""

    def __init__(self, host: str, port: int) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((host, port))
        self._callback: Callable[[dict], None] | None = None
        self._lock = threading.Lock()
        self._closed = False
        self._thread: threading.Thread | None = None

    def send(self, msg: dict) -> None:
        with self._lock:
            if self._closed:
                return
            line = serialize(msg) + "\n"
            self._socket.sendall(line.encode("utf-8"))

    def on_message(self, callback: Callable[[dict], None]) -> None:
        self._callback = callback
        if self._thread is None:
            self._thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._thread.start()

    def _receive_loop(self) -> None:
        # Buffer global: várias mensagens podem chegar num único recv.
        buffer = b""
        try:
            while not self._closed:
                chunk = self._socket.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    try:
                        msg = deserialize(line.decode("utf-8"))
                        if self._callback:
                            self._callback(msg)
                    except (ValueError, UnicodeDecodeError):
                        pass
        except (ConnectionResetError, OSError):
            pass

    def close(self) -> None:
        self._closed = True
        try:
            self._socket.close()
        except OSError:
            pass
