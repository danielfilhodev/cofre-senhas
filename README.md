# Cofre de Senhas

App em Python para guardar suas senhas de forma segura, local e criptografada.
Nada sai do seu computador — não tem nuvem, não tem conta, não tem servidor.

## Como funciona

- Você define **uma senha mestra**. Ela nunca é gravada em disco.
- A chave de criptografia é derivada da senha mestra com **PBKDF2-HMAC-SHA256**
  (600.000 iterações + salt aleatório de 128 bits).
- Os dados são cifrados com **Fernet (AES-128-CBC + HMAC)** — além de
  confidencialidade, qualquer alteração manual no arquivo é detectada.
- O cofre fica em `~/.cofre_senhas/vault.json` com permissão `600`
  (só você lê), dentro de pasta `700`.

## Instalação

```bash
cd /opt/data/home/cofre-senhas
uv sync          # baixa a dependência (cryptography)
```

Atalho global (opcional):

```bash
export PATH="/opt/data/home/cofre-senhas:$PATH"   # ~/.bashrc ou ~/.zshrc
cofre list
```

## Uso

```bash
cofre init                      # cria o cofre e define a senha mestra
cofre add gmail -u joao@gmail.com --url https://gmail.com
cofre add banco -u agencia01    # a senha é pedida sem exibir no terminal
cofre list                      # lista nomes (não mostra senhas)
cofre get gmail                 # mostra todos os dados
cofre get gmail --raw           # só a senha, para usar em pipeline
cofre del banco                 # remove (pede confirmação)
cofre gen -l 24                 # gera senha forte de 24 caracteres
cofre gen --add wifi            # gera e salva direto no cofre
cofre passwd                    # troca a senha mestra (recriptografa tudo)
```

`gen` aceita `--no-symbols` e `-l <tamanho>`.

## Segurança — o que você precisa saber

- **Esqueceu a senha mestra?** Não há recuperação. Sem ela o cofre é
  irrecuperável por design (não guardamos nada que permita reset).
- **Backup:** copie `~/.cofre_senhas/vault.json` — só tem sentido junto com
  a senha mestra, que você deve guardar em outro lugar (ex.: papel).
- O cofre protege contra cópia/leitura do arquivo. Se alguém tiver acesso
  **enquanto você está desbloqueado no terminal**, ele pode ler a saída.
  Não deixe o terminal desbloqueado sem supervisão.
- Senhas passadas por argumento (`-p`) aparecem no histórico do shell e em
  `ps`. Prefira deixar o app pedir no terminal.

## Estrutura

```
cofre-senhas/
├── main.py        # app inteiro (CLI com argparse)
├── cofre          # atalho de shell
├── pyproject.toml # dependências (uv)
└── README.md
```
