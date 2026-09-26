#!/usr/bin/env python3
"""Cofre de senhas local e criptografado.

Uso:
    python main.py init              # cria o cofre (define a senha mestra)
    python main.py add <nome>        # adiciona/atualiza uma entrada
    python main.py get <nome>        # mostra uma entrada
    python main.py list              # lista os nomes salvos
    python main.py del <nome>        # remove uma entrada
    python main.py gen               # gera uma senha forte
    python main.py passwd            # muda a senha mestra

O cofre fica em ~/.cofre_senhas/vault.json (criptografado com Fernet,
chave derivada da senha mestra via PBKDF2-HMAC-SHA256).
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
import string
import sys
import time
from pathlib import Path

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
    entry = vault["entries"].get(args.name)
    if entry is None:
        die(f"entrada '{args.name}' não encontrada")
    password = f.decrypt(entry["password"].encode()).decode()
    if args.raw:
        print(password)
        return
    print(f"nome:     {args.name}")
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
    if args.name not in vault["entries"]:
        die(f"entrada '{args.name}' não encontrada")
    if not args.yes:
        ans = input(f"remover '{args.name}'? [s/N] ").strip().lower()
        if ans not in ("s", "sim", "y", "yes"):
            print("cancelado")
            return
    del vault["entries"][args.name]
    save_vault(vault)
    print(f"removida: {args.name}")


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
    else:
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
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cofre", description="Cofre de senhas local e criptografado")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="cria o cofre").set_defaults(func=cmd_init)

    add = sub.add_parser("add", help="adiciona/atualiza uma entrada")
    add.add_argument("name")
    add.add_argument("-u", "--username")
    add.add_argument("-p", "--password", help="caso contrário, é pedido no terminal")
    add.add_argument("--url")
    add.add_argument("-n", "--notes")
    add.set_defaults(func=cmd_add)

    get = sub.add_parser("get", help="mostra uma entrada")
    get.add_argument("name")
    get.add_argument("--raw", action="store_true", help="só a senha (para scripts)")
    get.set_defaults(func=cmd_get)

    lst = sub.add_parser("list", help="lista as entradas")
    lst.set_defaults(func=cmd_list)

    d = sub.add_parser("del", help="remove uma entrada")
    d.add_argument("name")
    d.add_argument("-y", "--yes", action="store_true")
    d.set_defaults(func=cmd_del)

    g = sub.add_parser("gen", help="gera uma senha forte")
    g.add_argument("-l", "--length", type=int, default=20)
    g.add_argument("--no-symbols", dest="symbols", action="store_false")
    g.add_argument("--add", metavar="NOME", help="gera e salva já no cofre")
    g.set_defaults(func=cmd_gen, add=None, username=None, url=None, notes=None, password=None)

    sub.add_parser("passwd", help="muda a senha mestra").set_defaults(func=cmd_passwd)
    return p


def main() -> None:
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
