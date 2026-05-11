"""
Nome lógico do objeto remoto no catálogo Pyro (Name Server).

Cliente e servidor do jogo não precisam de conhecer IP/porta um do outro: apenas o
endereço do Name Server e este nome — o NS devolve o URI real do daemon do jogo.
"""

SERVIDOR_REGISTRY_NAME = "dara.ServidorDara"


def normalize_ns_host(host: str) -> str:
    """
    Garante ligação ao Name Server em IPv4 quando o NS escuta em 0.0.0.0.

    Em macOS (e outros), «localhost» pode resolver primeiro para ::1; o Pyro NS
    típico em -n 0.0.0.0 aceita só IPv4, e locate_ns falha. Usar 127.0.0.1 alinha
    cliente/servidor do jogo com o mesmo caminho que «localhost» na prática.
    """
    h = host.strip()
    lower = h.lower()
    if lower == "localhost" or h == "::1":
        return "127.0.0.1"
    return h
