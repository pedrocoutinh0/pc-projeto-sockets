"""
Único sítio a alterar para mudar transporte (ex.: return UdpConnection(...)).

main.py importa só create_connection; ui.py só usa a interface Connection.
"""

from dara.net.transport.tcp import TcpConnection
from dara.net.interfaces import Connection


def create_connection(host: str, port: int) -> Connection:
    return TcpConnection(host, port)
