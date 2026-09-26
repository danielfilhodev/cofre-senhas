"""Teste de fumaça da interface gráfica.

Pula automaticamente onde não há tkinter nem display — o restante da suíte
(roda em qualquer SO) continua cobrindo a lógica do cofre.
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest

tk = pytest.importorskip("tkinter", reason="tkinter indisponível neste Python")

if sys.platform not in ("win32", "darwin") and not os.environ.get("DISPLAY"):
    pytest.skip("sem display (X11/Wayland) para a janela", allow_module_level=True)


def _ambiente_grafico_utilizavel() -> None:
    """Alguns Pythons têm o import do tkinter mas o Tcl quebrado (ex.: sem init.tcl).
    Nesse caso a UI não roda aqui — pulamos em vez de quebrar a suíte."""
    try:
        raiz = tk.Tk()
        raiz.withdraw()
        raiz.update()
        raiz.destroy()
    except tk.TclError as e:
        pytest.skip(f"tkinter sem ambiente gráfico utilizável: {e}", allow_module_level=True)


_ambiente_grafico_utilizavel()

MASTER = "frase-mestra-de-teste-gui"


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("COFRE_DIR", str(tmp_path / "vault"))
    sys.modules.pop("main", None)
    sys.modules.pop("gui", None)
    main = importlib.import_module("main")
    gui = importlib.import_module("gui")

    from cryptography.fernet import Fernet

    salt = b"\x02" * 16
    f = Fernet(main.derive_key(MASTER, salt))
    vault = {
        "version": 1,
        "kdf": {"name": "pbkdf2-hmac-sha256", "iterations": main.KDF_ITERATIONS, "salt": list(salt)},
        "verifier": f.encrypt(b"cofre-senhas-ok").decode(),
        "entries": {},
    }
    for nome, user, url, pw in [
        ("GitHub", "beltrano", "https://github.com/login", "SenhaForte1!"),
        ("Google", "fulano@exemplo.com", "https://accounts.google.com", "outra#senha42"),
        ("mistral", "", "", "sem-usuario"),
    ]:
        vault["entries"][nome] = main.montar_entrada(
            f, {"username": user, "url": url, "password": pw, "notes": ""})
    main.save_vault(vault)

    janela = gui.CofreApp()
    janela.update()
    yield janela, main, gui, vault, f
    try:
        janela.update_idletasks()
        janela.destroy()
    except Exception:
        pass


def test_tela_de_login(app):
    janela, *_ = app
    assert janela.login_view.winfo_ismapped()
    assert janela.btn_entrar.cget("text") == "Entrar"
    assert "Senha mestra" in janela.entry_master.cget("placeholder_text")


def test_destrava_e_lista_as_entradas(app):
    janela, main, gui, vault, f = app
    janela.vault, janela.f = vault, f
    janela.main_view.tkraise()
    janela.atualizar_lista()
    janela.update()

    linhas = [w.cget("text").split("\n")[0] for w in janela.lista.winfo_children()]
    assert linhas == ["GitHub", "Google", "mistral"]  # ordem alfabética
    assert "3 entrada(s)" in janela.lbl_total.cget("text")


def test_detalhes_nao_vaza_a_senha(app):
    janela, main, gui, vault, f = app
    janela.vault, janela.f = vault, f
    janela.atualizar_lista()
    janela.selecionar("GitHub")
    janela.update()

    def textos(widget):
        for w in widget.winfo_children():
            if isinstance(w, gui.ctk.CTkLabel):
                yield str(w.cget("text"))
            yield from textos(w)

    visiveis = list(textos(janela.detalhes))
    assert any("GitHub" in t for t in visiveis)
    assert not any("SenhaForte1!" in t for t in visiveis)  # fica mascarada


def test_busca_filtra_a_lista(app):
    janela, main, gui, vault, f = app
    janela.vault, janela.f = vault, f
    janela.atualizar_lista()
    janela.entry_busca.insert(0, "goog")
    janela.atualizar_lista()
    linhas = [w.cget("text").split("\n")[0] for w in janela.lista.winfo_children()]
    assert linhas == ["Google"]
    janela.entry_busca.delete(0, "end")


def test_travar_volta_para_o_login(app):
    janela, main, gui, vault, f = app
    janela.vault, janela.f = vault, f
    janela.main_view.tkraise()
    janela.travar()
    janela.update()
    assert janela.vault is None and janela.f is None
    assert janela.login_view.winfo_ismapped()


def test_adicionar_e_apagar_via_ui(app):
    janela, main, gui, vault, f = app
    janela.vault, janela.f = vault, f
    janela.atualizar_lista()

    janela.adicionar()
    janela.update()
    janelas = [w for w in janela.winfo_children() if isinstance(w, gui.ctk.CTkToplevel)]
    assert janelas, "o formulário de adicionar não abriu"
    formulario = janelas[0]
    formulario.destroy()
    janela.update()

    # a ação de apagar abre caixa de confirmação nativa (bloqueia o teste);
    # cobrimos ela pelo caminho da lógica em tests/test_cofre.py
    assert callable(janela.apagar) and callable(janela.editar)
