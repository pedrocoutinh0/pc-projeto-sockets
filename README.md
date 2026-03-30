# Dara (rede)

Jogo **Dara** para dois jogadores: um **servidor** TCP (Python) e **clientes** com interface **Pygame**. O servidor aceita exatamente duas ligações e mantém o estado do tabuleiro.

## O que precisas

- **Python 3.10+**
- Dependências: `pip install -r requirements.txt` (inclui Pygame)

## Como correr

Na pasta do projeto:

```bash
pip install -r requirements.txt
```

**1. Servidor** (máquina que hospeda o jogo; para aceitar outros PCs usa `0.0.0.0`):

```bash
python3 -m dara.server.main --host 0.0.0.0 --port 9090
```

**2. Clientes** (dois terminais, na mesma máquina ou noutras). Troca `IP_DO_SERVIDOR` pelo IP real (ex.: `localhost` se for tudo local):

```bash
python3 -m dara.client.main --host IP_DO_SERVIDOR --port 9090
```

Liga o **primeiro** cliente e depois o **segundo**; a ordem define jogador 1 e 2. Abre a janela, escolhe apelido e joga.

## Testes (regras do tabuleiro)

```bash
python3 -m unittest tests.test_rules -v
```

## Opcional: instalar o pacote

```bash
pip install .
```

Depois podes usar os comandos `dara-server` e `dara-client` (com os mesmos argumentos `--host` / `--port`).
