"""Modelo simples de jogador (id + nick). O fluxo em rede usa nicknames no GameRoom."""

from dataclasses import dataclass


@dataclass
class Player:
    id: int
    nickname: str = ""

    def __str__(self) -> str:
        return self.nickname or f"Jogador {self.id}"
