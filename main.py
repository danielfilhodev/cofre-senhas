#!/usr/bin/env python3
"""Cofre de senhas local e criptografado — nada sai do seu computador.

Comandos (todos com --help próprio):
    cofre init      cria o cofre e define a senha mestra (uma única vez)
    cofre add <nome>      guarda/atualiza uma entrada
    cofre get <nome>      mostra uma entrada (--raw = só a senha,
                          --copy = cola na área de transferência e limpa sozinha)
    cofre list            lista os nomes guardados (nunca mostra senhas)
    cofre del <nome>      apaga uma entrada (pede confirmação)
    cofre import a.csv    importa senhas exportadas do navegador (--dry-run p/ testar)
    cofre gen             gera uma senha forte (--add <nome> já salva)
    cofre passwd          troca a senha mestra

Sem o atalho `cofre`, use:  python3 main.py <comando>
Arquivo do cofre: ~/.cofre_senhas/vault.json (chave derivada da senha
mestra com PBKDF2-HMAC-SHA256, dados cifrados com Fernet).
Guia completo para iniciantes: README.md
"""

from __future__ import annotations

import argparse
import csv
import getpass
import json
import os
import secrets
import shutil
import string
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken

VAULT_DIR = Path(os.environ.get("COFRE_DIR", Path.home() / ".cofre_senhas"))
VAULT_PATH = VAULT_DIR / "vault.json"
KDF_ITERATIONS = 600_000
_verifier = b"cofre-senhas-ok"  # valor conhecido p/ detectar senha mestra errada


# ---------------------------------------------------------------- utilidades
def die(msg: str, code: int = 1) -> None:
    print(f"erro: {msg}", file=sys.stderr)
    raise SystemExit(code)


def derive_key(master: str, salt: bytes, iterations: int = KDF_ITERATIONS) -> bytes:
    import base64

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return base64.urlsafe_b64encode(kdf.derive(master.encode("utf-8")))


def ask_master(confirm: bool = False) -> str:
    """Lê a senha mestra. Aceita também via stdin encanado (testes/automação)."""
    if not sys.stdin.isatty():
        value = sys.stdin.readline().rstrip("\n")
        if not value:
            die("senha mestra vazia")
        return value
    pw = getpass.getpass("Senha mestra: ")
    if not pw:
        die("senha mestra vazia")
    if confirm:
        again = getpass.getpass("Repita a senha mestra: ")
        if pw != again:
            die("as senhas não conferem")
    return pw


def load_vault() -> dict:
    if not VAULT_PATH.exists():
        die(f"cofre não existe ainda — rode: {sys.argv[0]} init")
    try:
        return json.loads(VAULT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        die(f"não consegui ler o cofre ({e})")


def unlock(vault: dict) -> Fernet:
    master = ask_master()
    salt = bytes(vault["kdf"]["salt"])
    key = derive_key(master, salt, vault["kdf"]["iterations"])
    f = Fernet(key)
    try:
        f.decrypt(vault["verifier"].encode())
    except InvalidToken:
        die("senha mestra incorreta")
    return f


def save_vault(vault: dict) -> None:
    VAULT_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = VAULT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(vault, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(VAULT_PATH)


def unlock_existing() -> tuple[dict, Fernet]:
    vault = load_vault()
    return vault, unlock(vault)


def _achar_nome(entries: dict, nome: str) -> str | None:
    """Acha a entrada ignorando maiúsculas/minúsculas (se o nome for único)."""
    if nome in entries:
        return nome
    alvo = nome.casefold()
    iguais = [n for n in entries if n.casefold() == alvo]
    return iguais[0] if len(iguais) == 1 else None


# ------------------------------------------------- área de transferência
def _clip_cmd() -> tuple[list[str], list[str]] | None:
    """(comando para ESCREVER, comando para LER) a área de transferência, ou None."""
    if sys.platform == "darwin":
        if shutil.which("pbcopy"):
            return ["pbcopy"], ["pbpaste"]
        return None
    if os.name == "nt":
        if shutil.which("clip") and shutil.which("powershell"):
            return ["clip"], ["powershell", "-NoProfile", "-Command", "Get-Clipboard"]
        return None
    # Linux/Unix: Wayland primeiro, depois X11
    if shutil.which("wl-copy") and shutil.which("wl-paste"):
        return ["wl-copy"], ["wl-paste", "--no-newline"]
    if shutil.which("xclip"):
        return ["xclip", "-selection", "clipboard"], ["xclip", "-selection", "clipboard", "-o"]
    if shutil.which("xsel"):
        return ["xsel", "--clipboard", "--input"], ["xsel", "--clipboard", "--output"]
    return None


def _para_area_transferencia(texto: str) -> str | None:
    """Copia para a área de transferência. Devolve None em sucesso, ou uma mensagem de erro."""
    cmd = _clip_cmd()
    if cmd is None:
        return (
            "não consegui acessar a área de transferência neste computador.\n"
            "  instale: Linux -> xclip (Debian/Ubuntu: sudo apt install xclip) ou wl-clipboard; "
            "macOS e Windows já têm nativamente"
        )
    try:
        p = subprocess.run(cmd[0], input=texto, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as e:
        return f"falha ao usar {cmd[0][0]}: {e}"
    if p.returncode != 0:
        return f"falha ao usar {cmd[0][0]}: {p.stderr.strip() or 'erro desconhecido'}"
    return None


def _ler_area_transferencia() -> str | None:
    cmd = _clip_cmd()
    if cmd is None:
        return None
    try:
        p = subprocess.run(cmd[1], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout if p.returncode == 0 else None


# ------------------------------------------------------------------ comandos
def cmd_init(_args) -> None:
    if VAULT_PATH.exists():
        die(f"cofre já existe em {VAULT_PATH}")
    master = ask_master(confirm=True)
    salt = secrets.token_bytes(16)
    key = derive_key(master, salt)
    f = Fernet(key)
    vault = {
        "version": 1,
        "kdf": {"name": "pbkdf2-hmac-sha256", "iterations": KDF_ITERATIONS, "salt": list(salt)},
        "verifier": f.encrypt(_verifier).decode(),
        "entries": {},
    }
    save_vault(vault)
    print(f"cofre criado em {VAULT_PATH}")


def _entry_fields(args, existing: dict | None) -> dict:
    if getattr(args, "password", None):
        password = args.password
    else:
        password = getpass.getpass("Senha: ") if sys.stdin.isatty() else sys.stdin.readline().rstrip("\n")
    if not password:
        die("senha da entrada vazia")
    return {
        "username": args.username or (existing or {}).get("username", ""),
        "url": args.url or (existing or {}).get("url", ""),
        "password": password,
        "notes": args.notes or (existing or {}).get("notes", ""),
        "created": (existing or {}).get("created", time.strftime("%Y-%m-%d %H:%M")),
        "updated": time.strftime("%Y-%m-%d %H:%M"),
    }


def cmd_add(args) -> None:
    vault, f = unlock_existing()
    existing = vault["entries"].get(args.name)
    entry = _entry_fields(args, existing)
    entry["password"] = f.encrypt(entry["password"].encode()).decode()
    vault["entries"][args.name] = entry
    save_vault(vault)
    print(f"{'atualizada' if existing else 'salva'}: {args.name}")


def cmd_get(args) -> None:
    vault, f = unlock_existing()
    nome = _achar_nome(vault["entries"], args.name)
    entry = vault["entries"].get(nome) if nome else None
    if entry is None:
        die(f"entrada '{args.name}' não encontrada — rode 'list' para ver os nomes")
    if args.raw and args.copy:
        die("--raw e --copy não combinam (escolha um)")
    password = f.decrypt(entry["password"].encode()).decode()
    if args.raw:
        print(password)
        return
    if args.copy:
        args.timeout = max(0, args.timeout)
        erro = _para_area_transferencia(password)
        if erro:
            die(erro)
        print(f"nome:     {nome}")
        print(f"usuário:  {entry['username'] or '-'}")
        print(f"url:      {entry['url'] or '-'}")
        fim = f" (limpa em {args.timeout}s)" if args.timeout > 0 else ""
        print(f"senha:    copiada para a área de transferência{fim}")
        if args.timeout > 0:
            try:
                time.sleep(args.timeout)
            except KeyboardInterrupt:
                print("\nsaindo sem limpar a área de transferência")
                return
            atual = _ler_area_transferencia()
            if atual is None or atual.strip() == password.strip():
                _para_area_transferencia("")
                print("área de transferência limpa")
            else:
                print("área de transferência mantida (você copiou outra coisa nesse meio-tempo)")
        return
    print(f"nome:     {nome}")
    print(f"usuário:  {entry['username'] or '-'}")
    print(f"url:      {entry['url'] or '-'}")
    print(f"senha:    {password}")
    if entry["notes"]:
        print(f"notas:    {entry['notes']}")
    print(f"atual.:   {entry['updated']}")


def cmd_list(args) -> None:
    vault, f = unlock_existing()
    names = sorted(vault["entries"])
    if not names:
        print("cofre vazio")
        return
    for n in names:
        e = vault["entries"][n]
        extra = f"  {e['username']}" if e["username"] else ""
        print(f"- {n}{extra}")
    print(f"\n{len(names)} entrada(s)")


def cmd_del(args) -> None:
    vault, f = unlock_existing()
    nome = _achar_nome(vault["entries"], args.name)
    if nome is None:
        die(f"entrada '{args.name}' não encontrada — rode 'list' para ver os nomes")
    if not args.yes:
        ans = input(f"remover '{nome}'? [s/N] ").strip().lower()
        if ans not in ("s", "sim", "y", "yes"):
            print("cancelado")
            return
    del vault["entries"][nome]
    save_vault(vault)
    print(f"removida: {nome}")


# ----------------------------------------------------- importação de CSV
# sinônimos de colunas aceitos (Chrome/Edge/Brave/Firefox/LastPass/1Password/KeePassXC)
_COLUNAS = {
    "name": {"name", "title", "entry", "nome", "label", "item"},
    "url": {"url", "urls", "origin", "login_uri", "website", "site", "address", "endereço"},
    "username": {"username", "user", "login", "user_name", "email", "mail", "usuário", "e-mail"},
    "password": {"password", "passwd", "pwd", "secret", "senha"},
    "notes": {"note", "notes", "extra", "comment", "httprealm", "notas", "obs"},
}


def _dominio(url: str) -> str | None:
    """'https://github.com/login' -> 'github.com'"""
    if not url:
        return None
    u = url.strip()
    if "://" not in u:
        u = "http://" + u
    host = urlparse(u).hostname or ""
    host = host.lower().removeprefix("www.")
    return host or None


def _ler_csv(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        die(f"arquivo não encontrado: {path}")
    raw = path.read_bytes()
    text = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    linhas = text.splitlines()
    if not linhas:
        die("o arquivo está vazio")
    primeira = linhas[0]
    delim = "," if primeira.count(",") >= max(primeira.count(";"), primeira.count("\t")) else (
        ";" if primeira.count(";") >= primeira.count("\t") else "\t"
    )
    import io

    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    if not reader.fieldnames:
        die("não consegui ler o cabeçalho do CSV")
    return list(reader.fieldnames), [dict(r) for r in reader]


def _mapear_colunas(cabecalhos: list[str]) -> dict[str, str]:
    """{coluna do arquivo: campo interno}"""
    mapa: dict[str, str] = {}
    usados: set[str] = set()
    for h in cabecalhos:
        k = (h or "").strip().lower().strip('"')
        for canon, sinonimos in _COLUNAS.items():
            if k in sinonimos and canon not in usados:
                mapa[h] = canon
                usados.add(canon)
                break
    return mapa


def cmd_import(args) -> None:
    cabecalhos, linhas = _ler_csv(Path(args.file).expanduser())
    mapa = _mapear_colunas(cabecalhos)
    if "password" not in mapa.values():
        die(
            "não achei uma coluna de senha no CSV.\n"
            f"  colunas encontradas: {', '.join(cabecalhos)}\n"
            "  esperado algo como: name,url,username,password,note"
        )

    # monta a lista do que seria importado (sem tocar no cofre ainda)
    pendentes: list[dict] = []
    sem_senha = vazias = 0
    for i, linha in enumerate(linhas, start=1):
        valores = {campo: (linha.get(col) or "").strip() for col, campo in mapa.items()}
        senha = valores.get("password", "")
        if not senha:
            sem_senha += 1
            continue
        nome = valores.get("name") or _dominio(valores.get("url", "")) or ""
        if not nome:
            nome = valores.get("username") or f"entrada_{i}"
            vazias += 1
        pendentes.append(
            {
                "name": nome,
                "username": valores.get("username", ""),
                "url": valores.get("url", ""),
                "password": senha,
                "notes": valores.get("notes", ""),
            }
        )

    print(f"arquivo:  {args.file}")
    print(f"entradas com senha: {len(pendentes)}"
          + (f"  |  sem senha: {sem_senha}" if sem_senha else ""))

    if args.dry_run:
        nomes = [e["name"] for e in pendentes]
        for n in nomes[:40]:
            print(f"  - {n}")
        if len(nomes) > 40:
            print(f"  ... e mais {len(nomes) - 40}")
        print("\nmodo de teste (--dry-run): nada foi gravado.")
        return

    if not pendentes:
        die("nenhuma entrada com senha para importar")

    vault, f = unlock_existing()
    antes = set(vault["entries"])
    existentes = set(vault["entries"])
    importadas = atualizadas = puladas = 0
    agora = time.strftime("%Y-%m-%d %H:%M")
    for e in pendentes:
        nome = e["name"]
        preexistente = nome in antes
        if preexistente and not args.overwrite:
            puladas += 1
            continue
        if nome in existentes and not preexistente:
            # nome repetido dentro do próprio CSV: ganha sufixo _2, _3...
            i = 2
            while f"{nome}_{i}" in existentes:
                i += 1
            nome = f"{nome}_{i}"
        anterior = vault["entries"].get(nome)
        vault["entries"][nome] = {
            "username": e["username"] or (anterior or {}).get("username", ""),
            "url": e["url"] or (anterior or {}).get("url", ""),
            "password": f.encrypt(e["password"].encode()).decode(),
            "notes": e["notes"] or (anterior or {}).get("notes", ""),
            "created": (anterior or {}).get("created", agora),
            "updated": agora,
        }
        existentes.add(nome)
        if preexistente:
            atualizadas += 1
        else:
            importadas += 1
    save_vault(vault)

    print(f"\nimportadas:    {importadas}")
    if atualizadas:
        print(f"atualizadas:   {atualizadas}")
    if puladas:
        print(f"puladas:       {puladas} (já existiam — use --overwrite para atualizar)")
    if sem_senha:
        print(f"sem senha:     {sem_senha}")
    if vazias:
        print(f"sem nome/url:  {vazias} (receberam um nome genérico)")
    print("\n⚠ apague o CSV exportado — ele contém suas senhas em texto puro.")


def cmd_gen(args) -> None:
    alphabet = string.ascii_letters + string.digits
    if args.symbols:
        alphabet += "!@#$%&*+-=?_"
    for _ in range(100):
        pw = "".join(secrets.choice(alphabet) for _ in range(args.length))
        if args.length >= 8 and len(set(pw)) >= max(4, args.length // 3):
            break
    if args.add:
        args.password = pw
        cmd_add(args)
    print(pw)


def cmd_passwd(_args) -> None:
    vault, old_f = unlock_existing()
    master = ask_master(confirm=True)
    salt = secrets.token_bytes(16)
    key = derive_key(master, salt)
    new_f = Fernet(key)
    for entry in vault["entries"].values():
        pw = old_f.decrypt(entry["password"].encode())
        entry["password"] = new_f.encrypt(pw).decode()
    vault["kdf"] = {"name": "pbkdf2-hmac-sha256", "iterations": KDF_ITERATIONS, "salt": list(salt)}
    vault["verifier"] = new_f.encrypt(_verifier).decode()
    save_vault(vault)
    print("senha mestra alterada")


# --------------------------------------------------------------------- main
_EXEMPLOS = """\
exemplos:
  cofre init                       cria o cofre (rode só uma vez)
  cofre add gmail -u joao@gmail.com   salva o acesso do e-mail
  cofre add banco                   pede a senha sem mostrar na tela
  cofre list                        mostra o que está guardado
  cofre get gmail                   mostra os dados de uma entrada
  cofre import senhas.csv           importa um CSV exportado do navegador
  cofre gen --add netflix           gera senha forte e já salva
  cofre passwd                      troca a senha mestra

esqueceu alguma coisa?  cofre <comando> --help
"""


def build_parser() -> argparse.ArgumentParser:
    from argparse import RawDescriptionHelpFormatter

    p = argparse.ArgumentParser(
        prog="cofre",
        description="Cofre de senhas local e criptografado — nada sai do seu computador.",
        epilog=_EXEMPLOS,
        formatter_class=RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser(
        "init",
        help="cria o cofre e define a senha mestra (rode uma única vez)",
        description="Cria o arquivo do cofre e pede para você definir a senha mestra.",
    ).set_defaults(func=cmd_init)

    add = sub.add_parser(
        "add",
        help="guarda uma senha nova (ou atualiza uma existente)",
        description="Guarda uma entrada no cofre. Se o nome já existir, atualiza.",
    )
    add.add_argument("name", metavar="nome", help="apelido da entrada, ex.: gmail, banco, netflix")
    add.add_argument("-u", "--username", metavar="USUARIO", help="seu usuário/e-mail no site")
    add.add_argument(
        "-p", "--password", metavar="SENHA",
        help="a senha; se omitir, o programa pede sem exibir (mais seguro)",
    )
    add.add_argument("--url", metavar="URL", help="endereço do site, ex.: https://gmail.com")
    add.add_argument("-n", "--notes", metavar="NOTA", help="anotações livres (opcional)")
    add.set_defaults(func=cmd_add)

    get = sub.add_parser("get", help="mostra os dados de uma entrada", description="Desbloqueia o cofre e mostra uma entrada.")
    get.add_argument("name", metavar="nome", help="apelido da entrada, ex.: gmail")
    get.add_argument("--raw", action="store_true", help="imprime só a senha, sem rótulos (para uso em scripts)")
    get.add_argument("--copy", action="store_true", help="copia a senha para a área de transferência (não imprime na tela)")
    get.add_argument("--timeout", type=int, default=30, metavar="SEG",
                     help="segundos até limpar a área de transferência no --copy (0 = não limpar; padrão: 30)")
    get.set_defaults(func=cmd_get)

    lst = sub.add_parser("list", help="lista os nomes guardados", description="Mostra os nomes das entradas (nunca as senhas).")
    lst.set_defaults(func=cmd_list)

    d = sub.add_parser("del", help="apaga uma entrada", description="Remove uma entrada do cofre; pede confirmação.")
    d.add_argument("name", metavar="nome", help="apelido da entrada, ex.: banco")
    d.add_argument("-y", "--yes", action="store_true", help="não perguntar nada (apaga direto)")
    d.set_defaults(func=cmd_del)

    imp = sub.add_parser(
        "import",
        help="importa senhas de um CSV (Chrome, Edge, Brave, Firefox...)",
        description="Importa um CSV exportado pelo navegador ou outro gerenciador de senhas.",
    )
    imp.add_argument("file", metavar="arquivo.csv", help="caminho do CSV exportado")
    imp.add_argument("--overwrite", action="store_true", help="atualiza entradas que já existem com o mesmo nome")
    imp.add_argument("--dry-run", action="store_true", help="só mostra o que seria importado; não grava nada")
    imp.set_defaults(func=cmd_import)

    g = sub.add_parser("gen", help="gera uma senha forte e aleatória", description="Sorteia uma senha difícil de adivinhar.")
    g.add_argument("-l", "--length", type=int, default=20, metavar="N", help="tamanho da senha (padrão: 20)")
    g.add_argument("--no-symbols", dest="symbols", action="store_false", help="sem símbolos especiais (!@#...)")
    g.add_argument("--add", metavar="nome", help="gera e já salva no cofre com esse nome")
    g.set_defaults(func=cmd_gen, add=None, username=None, url=None, notes=None, password=None)

    sub.add_parser(
        "passwd",
        help="troca a senha mestra (recriptografa tudo)",
        description="Define uma nova senha mestra. As senhas guardadas continuam as mesmas.",
    ).set_defaults(func=cmd_passwd)
    return p


def main() -> None:
    # garante UTF-8 na saída em qualquer SO (no Windows o padrão é cp1252 e
    # caracteres como ⚠ ou acentos quebrariam a impressão)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    args = build_parser().parse_args()
    if args.cmd == "gen" and args.add:
        args.name = args.add
        args.username = args.username or ""
        args.url = args.url or ""
        args.notes = args.notes or ""
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\ninterrompido", file=sys.stderr)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
