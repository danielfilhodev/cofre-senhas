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
    main.save_vault(vault, f)

    janela = gui.CofreApp()
    janela.update()
    yield janela, main, gui, vault, f
    try:
        janela.update_idletasks()
        janela.destroy()
    except Exception:
        pass


def _linhas_visiveis(janela) -> list[str]:
    """Linhas empacotadas na lista — as filtradas ficam ocultas, não destruídas."""
    janela.update()
    return [w.cget("text").split("\n")[0]
            for w in janela.lista.winfo_children() if w.winfo_ismapped()]


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

    linhas = _linhas_visiveis(janela)
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
    assert _linhas_visiveis(janela) == ["Google"]

    # limpar a busca devolve a lista completa, na ordem
    janela.entry_busca.delete(0, "end")
    janela.atualizar_lista()
    assert _linhas_visiveis(janela) == ["GitHub", "Google", "mistral"]


def test_linha_atualiza_apos_edicao(app):
    """A lista não é mais recriada — confirmar que uma edição renova o rótulo."""
    janela, main, gui, vault, f = app
    janela.vault, janela.f = vault, f
    janela.atualizar_lista()
    janela.selecionar("GitHub")

    def linha(nome):
        janela.update()
        return [w for w in janela.lista.winfo_children()
                if w.winfo_ismapped() and w.cget("text").split("\n")[0] == nome][0]

    assert "beltrano" in linha("GitHub").cget("text")
    janela.vault["entries"]["GitHub"]["username"] = "fulano-editado"
    janela._atualizar_texto("GitHub")
    assert "fulano-editado" in linha("GitHub").cget("text")
    assert _linhas_visiveis(janela) == ["GitHub", "Google", "mistral"]


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


def test_lista_grande_cria_so_as_linhas_da_tela(app):
    """Com muitas entradas, só existem botões para o que cabe na tela."""
    janela, main, gui, vault, f = app
    janela.vault = {"entries": {f"site{i:04d}": {"username": f"u{i}"} for i in range(800)}}
    janela.f = f
    janela.main_view.tkraise()
    janela.atualizar_lista()

    linhas = _linhas_visiveis(janela)
    assert linhas[0] == "site0000"
    assert len(janela.lista.winfo_children()) < 30
    assert "800 entrada(s)" in janela.lbl_total.cget("text")

    # rolar troca o conteúdo das linhas, sem criar widgets novos
    janela._rolar_barra("moveto", 0.5)
    assert _linhas_visiveis(janela)[0] == "site0400"
    assert len(janela.lista.winfo_children()) < 30

    # rolar até o fim mostra a última entrada
    janela._rolar_barra("moveto", 1.0)
    assert _linhas_visiveis(janela)[-1] == "site0799"


def test_selecionar_entrada_fora_da_tela_rola_ate_ela(app):
    janela, main, gui, vault, f = app
    janela.vault = {"entries": {f"site{i:04d}": {"username": ""} for i in range(300)}}
    janela.atualizar_lista()
    janela.update()
    janela.selecionado = "site0250"
    janela._destacar()   # o que selecionar() faz com a lista
    assert "site0250" in _linhas_visiveis(janela)


def test_travar_esvazia_as_linhas(app):
    janela, main, gui, vault, f = app
    janela.vault, janela.f = vault, f
    janela.atualizar_lista()
    assert _linhas_visiveis(janela)
    janela.travar()
    assert _linhas_visiveis(janela) == []


def test_entrar_converte_cofre_antigo(app, tmp_path):
    """A janela destrava um cofre da versão 1 e já o regrava todo cifrado."""
    import json

    janela, main, gui, vault, f = app
    antigo = {"version": 1, "kdf": vault["kdf"], "verifier": vault["verifier"],
              "entries": vault["entries"]}
    main.VAULT_PATH.write_text(json.dumps(antigo), encoding="utf-8")

    janela.entry_master.insert(0, MASTER)
    janela.entrar()
    for _ in range(400):           # espera a thread do PBKDF2 terminar
        janela.update()
        if janela.vault is not None:
            break
        janela.after(25)
    assert janela.vault is not None, "não destravou"
    assert set(janela.vault["entries"]) == {"GitHub", "Google", "mistral"}

    texto = main.VAULT_PATH.read_text(encoding="utf-8")
    assert json.loads(texto)["version"] == 2
    assert "beltrano" not in texto and "GitHub" not in texto


def test_editar_e_apagar_so_com_selecao(app):
    janela, main, gui, vault, f = app
    janela.vault, janela.f = vault, f
    janela.main_view.tkraise()
    janela.atualizar_lista()
    janela.update()
    assert not janela.acoes_entrada.winfo_ismapped()   # nada selecionado

    janela.selecionar("GitHub")
    janela.update()
    assert janela.acoes_entrada.winfo_ismapped()

    janela.travar()
    janela.update()
    assert not janela.acoes_entrada.winfo_manager()


def test_menu_nova_entrada(app, monkeypatch):
    janela, main, gui, vault, f = app
    janela.vault, janela.f = vault, f
    janela.main_view.tkraise()
    janela.update()
    assert not janela.menu_novo_aberto()

    janela.alternar_menu_novo()
    janela.update()
    assert janela.menu_novo_aberto()
    textos = [b.cget("text").split("\n")[0] for b in janela._opcoes_menu_novo]
    assert any("manualmente" in t for t in textos)
    assert any("senha forte" in t for t in textos)
    assert not any("Importar" in t for t in textos)   # importar tem botão próprio
    assert "Importar" in janela.btn_importar.cget("text")
    assert janela.btn_importar.winfo_ismapped()

    # escolher uma opção fecha o menu e chama a ação
    chamadas = []
    monkeypatch.setattr(janela, "adicionar", lambda: chamadas.append("adicionar"))
    janela._escolher_no_menu(lambda: janela.adicionar())
    janela.update()
    assert chamadas == ["adicionar"]
    assert not janela.menu_novo_aberto()

    # clicar de novo no botão abre; clicar outra vez fecha
    janela.alternar_menu_novo()
    janela.alternar_menu_novo()
    assert not janela.menu_novo_aberto()


@pytest.fixture()
def app_sem_cofre(tmp_path, monkeypatch):
    """Primeiro uso: a pasta do cofre ainda não existe."""
    monkeypatch.setenv("COFRE_DIR", str(tmp_path / "novo"))
    sys.modules.pop("main", None)
    sys.modules.pop("gui", None)
    main = importlib.import_module("main")
    gui = importlib.import_module("gui")
    janela = gui.CofreApp()
    janela.update()
    yield janela, main
    try:
        janela.destroy()
    except Exception:
        pass


def _esperar(janela, condicao, vezes=400):
    for _ in range(vezes):          # o PBKDF2 roda numa thread
        janela.update()
        if condicao():
            return True
        janela.after(25)
    return False


def test_primeiro_uso_mostra_tela_de_criar(app_sem_cofre):
    janela, main = app_sem_cofre
    janela.update()
    assert janela.criar_view.winfo_ismapped()
    assert janela.btn_criar.cget("text") == "Criar cofre"
    assert str(main.VAULT_PATH) in janela.lbl_caminho.cget("text")


def test_criar_valida_tamanho_e_confirmacao(app_sem_cofre):
    janela, main = app_sem_cofre
    janela.entry_nova.insert(0, "curta")
    janela.entry_confirma.insert(0, "curta")
    janela.criar()
    assert "pelo menos" in janela.lbl_criar_erro.cget("text")

    janela.entry_nova.delete(0, "end")
    janela.entry_nova.insert(0, "uma-frase-bem-longa")
    janela.criar()
    assert "não conferem" in janela.lbl_criar_erro.cget("text")
    assert not main.VAULT_PATH.exists()


def test_criar_cofre_pela_janela(app_sem_cofre):
    janela, main = app_sem_cofre
    janela.entry_nova.insert(0, MASTER)
    janela.entry_confirma.insert(0, MASTER)
    janela.criar()
    assert _esperar(janela, lambda: janela.vault is not None), "não criou"
    assert main.VAULT_PATH.exists()
    assert janela.vault["entries"] == {}
    assert janela.entry_nova.get() == "" and janela.entry_confirma.get() == ""

    # o cofre criado abre com a mesma senha
    import json
    dados = json.loads(main.VAULT_PATH.read_text(encoding="utf-8"))
    main.desbloquear(dados, MASTER)
    assert dados["entries"] == {}
