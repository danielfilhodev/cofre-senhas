"""Testes do cofre de senhas.

Rodam o `main.py` como subprocesso de verdade (o mesmo caminho que o usuário
usa), com o cofre apontado para um diretório temporário via COFRE_DIR.
No non-tty o app lê a senha mestra da primeira linha do stdin.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

MAIN = Path(__file__).resolve().parents[1] / "main.py"
MASTER = "frase-mestra-de-teste"
MASTER_NOVA = "outra-frase-bem-longa-2026"


def run(args: list[str], *, vault: Path | None = None, stdin: str = "") -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    if vault is not None:
        env["COFRE_DIR"] = str(vault)
    return subprocess.run(
        [sys.executable, str(MAIN), *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    p = run(["init"], vault=v, stdin=f"{MASTER}\n{MASTER}\n")
    assert p.returncode == 0, p.stderr
    return v


def vault_json(vault: Path) -> dict:
    return json.loads((vault / "vault.json").read_text(encoding="utf-8"))


def add(vault: Path, name: str, senha: str, *extra: str) -> subprocess.CompletedProcess:
    return run(["add", name, *extra], vault=vault, stdin=f"{MASTER}\n{senha}\n")


# ------------------------------------------------------------------- cofre
def test_init_cria_cofre_cifrado(tmp_path: Path):
    v = tmp_path / "vault"
    p = run(["init"], vault=v, stdin=f"{MASTER}\n{MASTER}\n")
    assert p.returncode == 0
    dados = vault_json(v)
    assert dados["entries"] == {}
    texto = (v / "vault.json").read_text(encoding="utf-8")
    assert MASTER not in texto  # a senha mestra nunca vai para o disco
    if os.name == "posix":
        assert oct((v / "vault.json").stat().st_mode)[-3:] == "600"


def test_init_duas_vezes_erro(vault: Path):
    p = run(["init"], vault=vault, stdin=f"{MASTER}\n{MASTER}\n")
    assert p.returncode == 1
    assert "já existe" in p.stderr


def test_senha_mestra_errada_é_rejeitada(vault: Path):
    p = run(["list"], vault=vault, stdin="senha-errada\n")
    assert p.returncode == 1
    assert "senha mestra incorreta" in p.stderr


# ------------------------------------------------------------ add / get / list
def test_add_get_roundtrip(vault: Path):
    p = add(vault, "gmail", "minha-senha-123", "-u", "joao@gmail.com", "--url", "https://gmail.com")
    assert p.returncode == 0, p.stderr

    p = run(["get", "gmail"], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 0
    assert "minha-senha-123" in p.stdout
    assert "joao@gmail.com" in p.stdout

    p = run(["get", "gmail", "--raw"], vault=vault, stdin=f"{MASTER}\n")
    assert p.stdout.strip() == "minha-senha-123"


def test_get_ignora_maiusculas(vault: Path):
    assert add(vault, "GitHub", "senha-x").returncode == 0
    p = run(["get", "github"], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 0
    assert "senha-x" in p.stdout


def test_list_nunca_mostra_senha(vault: Path):
    add(vault, "banco", "senha-secreta-999")
    p = run(["list"], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 0
    assert "banco" in p.stdout
    assert "senha-secreta-999" not in p.stdout


def test_get_entrada_inexistente(vault: Path):
    p = run(["get", "nao-existe"], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 1
    assert "não encontrada" in p.stderr


# ------------------------------------------------------------------------ del
def test_del_cancela_sem_confirmacao(vault: Path):
    add(vault, "netflix", "senha-nf")
    p = run(["del", "netflix"], vault=vault, stdin=f"{MASTER}\nn\n")
    assert p.returncode == 0
    assert "cancelado" in p.stdout
    assert "netflix" in vault_json(vault)["entries"]


def test_del_com_confirmacao(vault: Path):
    add(vault, "netflix", "senha-nf")
    p = run(["del", "netflix"], vault=vault, stdin=f"{MASTER}\ns\n")
    assert p.returncode == 0
    assert "netflix" not in vault_json(vault)["entries"]


def test_del_yes_nao_pergunta(vault: Path):
    add(vault, "netflix", "senha-nf")
    p = run(["del", "netflix", "-y"], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 0
    assert "netflix" not in vault_json(vault)["entries"]


# ------------------------------------------------------------------------ gen
def test_gen_fornece_senha_forte(vault: Path):
    p = run(["gen", "-l", "24", "--no-symbols"], vault=vault)
    senha = p.stdout.strip()
    assert p.returncode == 0
    assert len(senha) == 24
    assert re.fullmatch(r"[A-Za-z0-9]+", senha)


def test_gen_add_salva_no_cofre(vault: Path):
    p = run(["gen", "--add", "wifi"], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 0, p.stderr
    gerada = p.stdout.strip().splitlines()[-1]
    p = run(["get", "wifi", "--raw"], vault=vault, stdin=f"{MASTER}\n")
    assert p.stdout.strip() == gerada


# -------------------------------------------------------------------- passwd
def test_passwd_troca_mestra_e_preserva_senhas(vault: Path):
    add(vault, "gmail", "senha-antiga-ok")
    p = run(["passwd"], vault=vault, stdin=f"{MASTER}\n{MASTER_NOVA}\n{MASTER_NOVA}\n")
    assert p.returncode == 0, p.stderr

    assert run(["list"], vault=vault, stdin=f"{MASTER}\n").returncode == 1
    p = run(["get", "gmail", "--raw"], vault=vault, stdin=f"{MASTER_NOVA}\n")
    assert p.returncode == 0
    assert p.stdout.strip() == "senha-antiga-ok"


# -------------------------------------------------------------------- import
CHROME_CSV = (
    "\ufeffname,url,username,password,note\n"
    "GitHub,https://github.com/login,beltrano,SenhaForte1!,\n"
    "Google,https://accounts.google.com,fulano@exemplo.com,outra#senha42,fatura\n"
    ",https://www.uol.com.br,usuario_uol,senha_uol,\n"
    "Site Sem Senha,https://exemplo.com,fulano,\n"
    ",,usuario_semsenha,so-username,\n"
    "GitHub,https://github.com,outra-conta,senha-repetida,\n"
)

FIREFOX_CSV = (
    "url,username,password,httpRealm,formActionOrigin,guid,timeCreated\n"
    "https://mail.google.com,fulano@exemplo.com,gmail-senha-123,,https://google.com,abc,1\n"
)

SEMICOLON_CSV = (
    "url;username;password;totp;extra;name;grouping;fav\n"
    "https://nubank.com.br;12345678;senha-nubank;;nota;Banco Nubank;fin;1\n"
)


def write_csv(tmp_path: Path, nome: str, conteudo: str) -> Path:
    p = tmp_path / nome
    p.write_text(conteudo, encoding="utf-8")
    return p


def test_import_dry_run_nao_grava(vault: Path, tmp_path: Path):
    csv = write_csv(tmp_path, "chrome.csv", CHROME_CSV)
    # stdin vazio: se pedisse a senha mestra, falharia
    p = run(["import", str(csv), "--dry-run"], vault=vault, stdin="")
    assert p.returncode == 0, p.stderr
    assert "nada foi gravado" in p.stdout
    p = run(["list"], vault=vault, stdin=f"{MASTER}\n")
    assert "cofre vazio" in p.stdout


def test_import_chrome_completo(vault: Path, tmp_path: Path):
    csv = write_csv(tmp_path, "chrome.csv", CHROME_CSV)
    p = run(["import", str(csv)], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 0, p.stderr
    assert "importadas:    5" in p.stdout
    assert "sem senha:     1" in p.stdout

    dados = vault_json(vault)
    assert set(dados["entries"]) == {"GitHub", "GitHub_2", "Google", "uol.com.br", "usuario_semsenha"}

    p = run(["get", "github", "--raw"], vault=vault, stdin=f"{MASTER}\n")
    assert p.stdout.strip() == "SenhaForte1!"
    p = run(["get", "uol.com.br"], vault=vault, stdin=f"{MASTER}\n")
    assert "senha_uol" in p.stdout

    # a senha importada não pode aparecer em texto puro no disco
    assert "SenhaForte1!" not in (vault / "vault.json").read_text(encoding="utf-8")


def test_import_reimportar_pula_e_overwrite_atualiza(vault: Path, tmp_path: Path):
    csv = write_csv(tmp_path, "chrome.csv", CHROME_CSV)
    run(["import", str(csv)], vault=vault, stdin=f"{MASTER}\n")

    p = run(["import", str(csv)], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 0
    assert "importadas:    0" in p.stdout
    assert "puladas:       5" in p.stdout

    p = run(["import", str(csv), "--overwrite"], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 0
    assert "atualizadas:   5" in p.stdout


def test_import_firefox_e_ponto_e_virgula(vault: Path, tmp_path: Path):
    ff = write_csv(tmp_path, "firefox.csv", FIREFOX_CSV)
    p = run(["import", str(ff)], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 0, p.stderr
    assert "importadas:    1" in p.stdout
    p = run(["get", "mail.google.com", "--raw"], vault=vault, stdin=f"{MASTER}\n")
    assert p.stdout.strip() == "gmail-senha-123"

    lp = write_csv(tmp_path, "lastpass.csv", SEMICOLON_CSV)
    p = run(["import", str(lp)], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 0, p.stderr
    p = run(["get", "Banco Nubank"], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 0
    assert "senha-nubank" in p.stdout


def test_import_erros(vault: Path, tmp_path: Path):
    p = run(["import", str(tmp_path / "nao-existe.csv")], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 1
    assert "arquivo não encontrado" in p.stderr

    ruim = write_csv(tmp_path, "ruim.csv", "nome,sitio\na,https://x.com\n")
    p = run(["import", str(ruim)], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 1
    assert "coluna de senha" in p.stderr

    vazio = write_csv(tmp_path, "vazio.csv", "")
    assert run(["import", str(vazio)], vault=vault, stdin=f"{MASTER}\n").returncode == 1


def test_sem_cofre_erro_amigavel(tmp_path: Path):
    p = run(["list"], vault=tmp_path / "nao-existe", stdin=f"{MASTER}\n")
    assert p.returncode == 1
    assert "init" in p.stderr


# ----------------------------------------------------------------- --copy
def load_main():
    import importlib.util

    spec = importlib.util.spec_from_file_location("cofre_main", MAIN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_copy_e_raw_nao_combinam(vault: Path):
    add(vault, "gmail", "senha-x")
    p = run(["get", "gmail", "--copy", "--raw"], vault=vault, stdin=f"{MASTER}\n")
    assert p.returncode == 1
    assert "não combinam" in p.stderr


def test_copy_sem_ferramenta_erro_amigavel(monkeypatch):
    mod = load_main()
    monkeypatch.setattr(mod.sys, "platform", "linux")
    monkeypatch.setattr(mod.shutil, "which", lambda nome: None)
    assert mod._clip_cmd() is None
    erro = mod._para_area_transferencia("qualquer")
    assert erro is not None
    assert "área de transferência" in erro
    assert "xclip" in erro  # diz o que instalar


def test_copy_detecta_ferramentas_por_sistema(monkeypatch):
    mod = load_main()

    def fake(*permitidos):
        permitidos = set(permitidos)
        return lambda nome: nome if nome in permitidos else None

    # Windows: clip + powershell
    monkeypatch.setattr(mod.os, "name", "nt")
    monkeypatch.setattr(mod.shutil, "which", fake("clip", "powershell"))
    assert mod._clip_cmd() == (["clip"], ["powershell", "-NoProfile", "-Command", "Get-Clipboard"])

    # macOS: pbcopy/pbpaste nativos
    monkeypatch.setattr(mod.os, "name", "posix")
    monkeypatch.setattr(mod.sys, "platform", "darwin")
    monkeypatch.setattr(mod.shutil, "which", fake("pbcopy", "pbpaste"))
    assert mod._clip_cmd() == (["pbcopy"], ["pbpaste"])

    # Linux Wayland
    monkeypatch.setattr(mod.sys, "platform", "linux")
    monkeypatch.setattr(mod.shutil, "which", fake("wl-copy", "wl-paste"))
    assert mod._clip_cmd() == (["wl-copy"], ["wl-paste", "--no-newline"])

    # Linux X11 com xclip
    monkeypatch.setattr(mod.shutil, "which", fake("xclip"))
    assert mod._clip_cmd() == (
        ["xclip", "-selection", "clipboard"],
        ["xclip", "-selection", "clipboard", "-o"],
    )

    # nada instalado
    monkeypatch.setattr(mod.shutil, "which", fake())
    assert mod._clip_cmd() is None


def test_get_copy_comportamento(vault: Path):
    """Sucesso (há clipboard) ou falha amigável — nunca exceção ou senha na tela."""
    add(vault, "gmail", "senha-copiar-123")
    p = run(["get", "gmail", "--copy", "--timeout", "1"], vault=vault, stdin=f"{MASTER}\n")
    assert "senha-copiar-123" not in p.stdout
    if p.returncode == 0:
        assert "copiada" in p.stdout
    else:
        assert p.returncode == 1
        assert "área de transferência" in p.stderr
