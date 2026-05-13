# Dara (rede, Pyro5 RPC + Name Server)

Jogo **Dara** para dois jogadores: um **servidor** que expõe a lógica via **Pyro5** e **clientes** com **Pygame**. O **Pyro Name Server** mantém o catálogo nome → URI: na teoria, cliente e servidor do jogo **só precisam de saber onde está o NS** e o **nome lógico** (`dara.ServidorDara`); não referenciam directamente a porta do daemon do outro. O estado do tabuleiro continua autoritário no processo do servidor de jogo.

## O que precisas

- **Python 3.10+**
- Dependências: `pip install -r requirements.txt` (Pygame + Pyro5)

## Como correr

Na pasta do projeto:

```bash
pip install -r requirements.txt
```

Ordem típica (três processos):

**1. Name Server Pyro** (catálogo central; primeiro terminal):

```bash
python3 -m Pyro5.nameserver -n 0.0.0.0 -p 9091
```

**2. Servidor do jogo** — regista o daemon no NS (`--ns-host` / `--ns-port` apontam para o passo 1):

```bash
python3 -m dara.server.main --host 0.0.0.0 --port 9090 --ns-host localhost --ns-port 9091
```

Num servidor remoto, os clientes usarão o IP desse host em `--ns-host`; na mesma máquina podes usar `localhost` (internamente usa-se IPv4 `127.0.0.1` para coincidir com o NS em `0.0.0.0`, evitando falhas típicas no macOS com `::1`).

**3. Clientes** (dois terminais). Só indicam o **Name Server**, não a porta do daemon do jogo:

```bash
python3 -m dara.client.main --ns-host localhost --ns-port 9091
```

Noutro PC: `--ns-host <IP_ou_hostname_do_NS>`.

Fluxo: primeiro cliente confirma apelido (jogador 1); segundo cliente confirma (jogador 2); a partida inicia quando ambos estão registados.

### Ver pedidos / jogadas nos logs

As **jogadas** (RPC `colocar_peca`, `mover_peca`, …) chegam ao **servidor do jogo**, não ao Name Server: vês linhas `[RPC] …` no terminal onde corre `dara.server.main` (nível INFO por defeito).

O **Name Server** só trata de registar e resolver nomes; não vê movimentos no tabuleiro. Para debug do próprio Pyro NS (tráfego de registo/lookup), podes subir o NS com verbosidade alta, por exemplo:

```bash
PYRO_LOGLEVEL=DEBUG python3 -m Pyro5.nameserver -n 0.0.0.0 -p 9091
```

### Callbacks (servidor do jogo → cliente)

O servidor de jogo invoca remotamente métodos no cliente (`notificar_inicio`,
`atualizar_estado`, `notificar_chat`, `notificar_erro`) — callbacks RPC com
interface nomeada. O daemon Pyro **do cliente** escuta numa porta local (por
defeito aleatória). Em LAN, se falhar, verifica firewall e portas; `--bind-host
0.0.0.0` no cliente mantém o bind em todas as interfaces (valor por defeito
quando vazio).

## Testes

Regras do tabuleiro:

```bash
python3 -m unittest tests.test_rules -v
```

Smoke (Name Server + registo + dois clientes):

```bash
python3 -m unittest tests.test_pyro_integration -v
```

## Opcional: instalar o pacote

```bash
pip install .
```

Comandos `dara-server` e `dara-client` com os mesmos argumentos (`--ns-host`, `--ns-port`, etc.).
