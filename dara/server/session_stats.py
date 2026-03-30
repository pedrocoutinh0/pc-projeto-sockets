"""
Placar W/L em RAM durante a vida do processo servidor.

Chave = peer_key dos endpoints: "IP#porta" (ver TcpClientEndpoint.peer_key).
Não há persistência em disco; reiniciar o servidor zera o dicionário _store.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlayerRecord:
    wins: int = 0
    losses: int = 0


_store: dict[str, PlayerRecord] = {}


def record_match(winner_key: str, loser_key: str) -> None:
    if winner_key not in _store:
        _store[winner_key] = PlayerRecord()
    if loser_key not in _store:
        _store[loser_key] = PlayerRecord()
    _store[winner_key].wins += 1
    _store[loser_key].losses += 1


def snapshot(key: str) -> dict[str, int]:
    r = _store.get(key)
    if r is None:
        return {"wins": 0, "losses": 0}
    return {"wins": r.wins, "losses": r.losses}


def stats_payload_for_keys(key1: str, key2: str) -> dict[str, dict[str, int]]:
    return {
        "1": snapshot(key1),
        "2": snapshot(key2),
    }
