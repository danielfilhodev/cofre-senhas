#!/usr/bin/env python3
"""Interface gráfica do Cofre de Senhas (CustomTkinter).

    uv run gui.py

Reaproveita toda a lógica de `main.py` (mesmo cofre, mesma cifra, mesmos
testes). A janela mostra a senha só quando você pede, e o cofre volta a
travar ao fechar o programa.
"""

from __future__ import annotations

import json
import threading
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from pathlib import Path

import customtkinter as ctk

import main as cofre

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

FONTE_TITULO: ctk.CTkFont | None = None
FONTE_NORMAL: ctk.CTkFont | None = None
FONTE_PEQUENA: ctk.CTkFont | None = None


class CofreApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        # as fontes precisam da janela raiz já criada
        global FONTE_TITULO, FONTE_NORMAL, FONTE_PEQUENA
        FONTE_TITULO = ctk.CTkFont(size=26, weight="bold")
        FONTE_NORMAL = ctk.CTkFont(size=14)
        FONTE_PEQUENA = ctk.CTkFont(size=12)
        self.title("Cofre de Senhas")
        self.geometry("980x640")
        self.minsize(860, 560)
        self.vault: dict | None = None
        self.f = None
        self.selecionado: str | None = None
        self._senha_visivel = False
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._montar_login()
        self._montar_principal()
        self.login_view.tkraise()

    # ------------------------------------------------------------ telas
    def _montar_login(self) -> None:
        self.login_view = ctk.CTkFrame(self, fg_color="transparent")
        self.login_view.grid(row=0, column=0, sticky="nsew")
        caixa = ctk.CTkFrame(self.login_view, corner_radius=20, width=380, height=320)
        caixa.place(relx=0.5, rely=0.5, anchor="center")
        caixa.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(caixa, text="🔐 Cofre de Senhas", font=FONTE_TITULO).grid(
            row=0, column=0, padx=30, pady=(34, 4))
        ctk.CTkLabel(
            caixa, text="Digite a senha mestra para destravar",
            font=FONTE_NORMAL, text_color="#9aa4b2").grid(row=1, column=0, padx=30)

        self.entry_master = ctk.CTkEntry(caixa, placeholder_text="Senha mestra",
                                         show="*", width=300, height=40)
        self.entry_master.grid(row=2, column=0, padx=30, pady=(24, 10))
        self.entry_master.bind("<Return>", lambda _e: self.entrar())

        self.btn_entrar = ctk.CTkButton(caixa, text="Entrar", height=40,
                                        command=self.entrar, font=FONTE_NORMAL)
        self.btn_entrar.grid(row=3, column=0, padx=30, pady=(4, 10))

        self.lbl_login_erro = ctk.CTkLabel(caixa, text="", text_color="#ff6b6b",
                                           font=FONTE_PEQUENA, wraplength=320)
        self.lbl_login_erro.grid(row=4, column=0, padx=30, pady=(0, 18))

        if not cofre.VAULT_PATH.exists():
            self.lbl_login_erro.configure(
                text=f"Cofre ainda não existe.\nCrie no terminal:  uv run main.py init",
                text_color="#ffd166")

    def _montar_principal(self) -> None:
        self.main_view = ctk.CTkFrame(self, fg_color="transparent")
        self.main_view.grid(row=0, column=0, sticky="nsew")
        self.main_view.grid_columnconfigure(1, weight=1)
        self.main_view.grid_rowconfigure(1, weight=1)

        # barra de topo
        topo = ctk.CTkFrame(self.main_view, fg_color="transparent")
        topo.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(14, 6))
        topo.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(topo, text="🔐 Cofre de Senhas", font=FONTE_TITULO).grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(topo, text="Importar CSV…", width=130, height=34,
                      command=self.importar_csv).grid(row=0, column=1, sticky="e", padx=(0, 8))
        ctk.CTkButton(topo, text="Travar", width=90, height=34, fg_color="#444b57",
                      hover_color="#343a44", command=self.travar).grid(row=0, column=2, sticky="e")

        # coluna esquerda: busca + lista
        esq = ctk.CTkFrame(self.main_view, corner_radius=14, width=320)
        esq.grid(row=1, column=0, sticky="nsw", padx=(16, 8), pady=8)
        esq.grid_rowconfigure(2, weight=1)
        esq.grid_columnconfigure(0, weight=1)
        esq.pack_propagate(False)

        ctk.CTkLabel(esq, text="Suas entradas", font=FONTE_TITULO).grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 6))
        self.entry_busca = ctk.CTkEntry(esq, placeholder_text="🔍 buscar por nome, usuário ou url",
                                        height=34)
        self.entry_busca.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        self.entry_busca.bind("<KeyRelease>", lambda _e: self.atualizar_lista())

        self.lista = ctk.CTkScrollableFrame(esq, fg_color="transparent")
        self.lista.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 10))
        self.lbl_total = ctk.CTkLabel(esq, text="0 entrada(s)", font=FONTE_PEQUENA,
                                      text_color="#9aa4b2")
        self.lbl_total.grid(row=3, column=0, sticky="w", padx=14, pady=(0, 12))

        # coluna direita: detalhes
        dir_ = ctk.CTkFrame(self.main_view, corner_radius=14)
        dir_.grid(row=1, column=1, sticky="nsew", padx=(8, 16), pady=8)
        dir_.grid_columnconfigure(0, weight=1)
        self.detalhes = ctk.CTkFrame(dir_, fg_color="transparent")
        self.detalhes.grid(row=0, column=0, sticky="nsew", padx=24, pady=18)
        self.detalhes.grid_columnconfigure(1, weight=1)

        botoes = ctk.CTkFrame(dir_, fg_color="transparent")
        botoes.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 18))
        for i, (texto, cmd, cor) in enumerate([
            ("Adicionar", self.adicionar, None),
            ("Editar", self.editar, None),
            ("Gerar senha", self.gerar, "#2f9e6e"),
            ("Apagar", self.apagar, "#b03a3a"),
        ]):
            ctk.CTkButton(botoes, text=texto, width=120, height=36, command=cmd,
                          fg_color=cor, hover_color=cor if cor else None).grid(
                row=0, column=i, padx=(0, 8))

        self.lbl_status = ctk.CTkLabel(self.main_view, text="", font=FONTE_PEQUENA,
                                       text_color="#9aa4b2", anchor="w")
        self.lbl_status.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 10))

        self.detalhes_vazio()

    # ------------------------------------------------------- desbloqueio
    def entrar(self) -> None:
        senha = self.entry_master.get()
        if not senha:
            self.lbl_login_erro.configure(text="Digite a senha mestra.")
            return
        if not cofre.VAULT_PATH.exists():
            return
        self.lbl_login_erro.configure(text="")
        self.btn_entrar.configure(state="disabled", text="Verificando…")

        def trabalho():
            try:
                vault = json.loads(cofre.VAULT_PATH.read_text(encoding="utf-8"))
                f = cofre.desbloquear(vault, senha)
                return vault, f
            except ValueError as e:
                return e
            except (OSError, json.JSONDecodeError, KeyError) as e:
                return RuntimeError(f"não consegui abrir o cofre: {e}")

        def ao_terminar(resultado):
            self.btn_entrar.configure(state="normal", text="Entrar")
            self.entry_master.delete(0, "end")
            if isinstance(resultado, Exception):
                self.lbl_login_erro.configure(text=str(resultado))
                return
            self.vault, self.f = resultado
            self.selecionado = None
            self.main_view.tkraise()
            self.atualizar_lista()
            self.status("cofre destravado")

        self._assinc(trabalho, ao_terminar)

    def travar(self) -> None:
        self.vault = None
        self.f = None
        self.selecionado = None
        self.detalhes_vazio()
        self.login_view.tkraise()
        self.status("cofre travado")

    def on_close(self) -> None:
        self.vault = None
        self.f = None
        self.destroy()

    # --------------------------------------------------------- utilidades
    def _assinc(self, trabalho, ao_terminar) -> None:
        """Roda `trabalho` numa thread e entrega o resultado na thread da UI."""
        caixa: dict = {}

        def rodar():
            try:
                caixa["ok"] = trabalho()
            except Exception as e:  # noqa: BLE001 - qualquer erro vira mensagem
                caixa["erro"] = e

        def esperar():
            if "ok" in caixa:
                ao_terminar(caixa["ok"])
            elif "erro" in caixa:
                ao_terminar(caixa["erro"])
            else:
                self.after(50, esperar)

        threading.Thread(target=rodar, daemon=True).start()
        self.after(50, esperar)

    def status(self, texto: str) -> None:
        self.lbl_status.configure(text=texto)

    def _nomes_filtrados(self) -> list[str]:
        busca = self.entry_busca.get().strip().casefold()
        nomes = sorted(self.vault["entries"])
        if not busca:
            return nomes
        saida = []
        for n in nomes:
            e = self.vault["entries"][n]
            alvo = f"{n} {e.get('username','')} {e.get('url','')}".casefold()
            if busca in alvo:
                saida.append(n)
        return saida

    def atualizar_lista(self) -> None:
        for w in self.lista.winfo_children():
            w.destroy()
        nomes = self._nomes_filtrados()
        for n in nomes:
            e = self.vault["entries"][n]
            texto = n + (f"\n{e['username']}" if e.get("username") else "")
            cor = "#2b7fff" if n == self.selecionado else None
            btn = ctk.CTkButton(
                self.lista, text=texto, anchor="w", height=48, corner_radius=10,
                fg_color=cor, hover_color="#1f5fbf" if cor else None,
                font=FONTE_NORMAL,
                command=lambda nome=n: self.selecionar(nome),
            )
            btn.pack(fill="x", padx=4, pady=3)
        total = len(self.vault["entries"])
        self.lbl_total.configure(
            text=f"{total} entrada(s)" + ("" if len(nomes) == total else f" — {len(nomes)} na busca"))
        if self.selecionado and self.selecionado not in self.vault["entries"]:
            self.selecionado = None
        if self.selecionado:
            self.selecionar(self.selecionado, atualizar_lista=False)
        elif not self.vault["entries"]:
            self.detalhes_vazio(mensagem="Cofre vazio — clique em “Adicionar” ou “Importar CSV”.")
        else:
            self.detalhes_vazio()

    def detalhes_vazio(self, mensagem: str = "Selecione uma entrada ao lado 👈") -> None:
        self.selecionado = None
        for w in self.detalhes.winfo_children():
            w.destroy()
        self.detalhes.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.detalhes, text=mensagem, font=FONTE_NORMAL,
                     text_color="#9aa4b2").grid(row=0, column=0, columnspan=2, pady=40)

    def selecionar(self, nome: str, atualizar_lista: bool = True) -> None:
        if nome not in (self.vault or {}).get("entries", {}):
            return
        self.selecionado = nome
        self._senha_visivel = False
        if atualizar_lista:
            self.atualizar_lista()
            return
        self._mostrar_detalhes()

    def _mostrar_detalhes(self) -> None:
        nome = self.selecionado
        if not nome:
            return
        dados = cofre.descrever_entrada(self.f, self.vault["entries"][nome])
        for w in self.detalhes.winfo_children():
            w.destroy()
        self.detalhes.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.detalhes, text=nome, font=FONTE_TITULO).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        linhas = [("Usuário", dados["username"] or "—"),
                  ("URL", dados["url"] or "—"),
                  ("Notas", dados["notes"] or "—")]
        for i, (rotulo, valor) in enumerate(linhas, start=1):
            ctk.CTkLabel(self.detalhes, text=rotulo, font=FONTE_PEQUENA,
                         text_color="#9aa4b2", width=70, anchor="w").grid(
                row=i, column=0, sticky="nw", pady=6)
            ctk.CTkLabel(self.detalhes, text=valor, font=FONTE_NORMAL,
                         wraplength=460, justify="left", anchor="w").grid(
                row=i, column=1, sticky="w", pady=6)

        # senha
        ctk.CTkLabel(self.detalhes, text="Senha", font=FONTE_PEQUENA,
                     text_color="#9aa4b2", width=70, anchor="w").grid(
            row=4, column=0, sticky="nw", pady=6)
        col_senha = ctk.CTkFrame(self.detalhes, fg_color="transparent")
        col_senha.grid(row=4, column=1, sticky="w", pady=6)
        self.lbl_senha = ctk.CTkLabel(
            col_senha,
            text=dados["password"] if self._senha_visivel else "•" * min(16, len(dados["password"])),
            font=FONTE_NORMAL)
        self.lbl_senha.pack(side="left")
        ctk.CTkButton(col_senha, text="Mostrar" if not self._senha_visivel else "Ocultar",
                      width=80, height=26, fg_color="#444b57", hover_color="#343a44",
                      command=self.alternar_senha).pack(side="left", padx=10)
        ctk.CTkButton(col_senha, text="Copiar", width=80, height=26,
                      command=self.copiar_senha).pack(side="left", padx=(0, 0))

        ctk.CTkLabel(self.detalhes, text=f"criado {dados['created']}   •   atualizado {dados['updated']}",
                     font=FONTE_PEQUENA, text_color="#6b7280").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(16, 0))

    def alternar_senha(self) -> None:
        self._senha_visivel = not self._senha_visivel
        self._mostrar_detalhes()

    def copiar_senha(self) -> None:
        if not self.selecionado:
            return
        senha = cofre.descrever_entrada(self.f, self.vault["entries"][self.selecionado])["password"]
        erro = cofre._para_area_transferencia(senha)
        if erro:
            messagebox.showerror("Área de transferência", erro)
            return
        restante = 30

        def tick():
            nonlocal restante
            if restante <= 0:
                atual = cofre._ler_area_transferencia()
                if atual is None or atual.strip() == senha.strip():
                    cofre._para_area_transferencia("")
                    self.status("senha copiada • área de transferência limpa")
                else:
                    self.status("senha copiada • área mantida (você copiou outra coisa)")
                return
            self.status(f"senha copiada para a área de transferência — limpa em {restante}s")
            restante -= 1
            self.after(1000, tick)

        tick()

    # ----------------------------------------------------------- ações
    def _formulario(self, titulo: str, dados: dict | None = None) -> None:
        dados = dados or {}
        janela = ctk.CTkToplevel(self)
        janela.title(titulo)
        janela.geometry("440x430")
        janela.grab_set()
        janela.grid_columnconfigure(1, weight=1)

        campos = {}
        rotulos = [("Apelido (nome)", "name"), ("Usuário", "username"),
                   ("URL", "url"), ("Senha", "password"), ("Notas", "notes")]
        for i, (rotulo, chave) in enumerate(rotulos):
            ctk.CTkLabel(janela, text=rotulo).grid(row=i, column=0, sticky="w",
                                                   padx=16, pady=(12 if i == 0 else 6, 0))
            if chave == "notes":
                widget = ctk.CTkTextbox(janela, height=70)
                widget.insert("1.0", dados.get("notes", ""))
            else:
                widget = ctk.CTkEntry(janela, width=280,
                                      show="*" if chave == "password" else "")
                widget.insert(0, dados.get(chave, ""))
                if chave == "name" and dados.get("name"):
                    widget.configure(state="disabled")
            widget.grid(row=i, column=1, sticky="ew", padx=(6, 16),
                        pady=(12 if i == 0 else 6, 0))
            campos[chave] = widget

        def gerar():
            senha = cofre.gerar_senha(20, True)
            campos["password"].delete(0, "end")
            campos["password"].insert(0, senha)
            self.status("senha forte gerada — salve para guardá-la")

        def salvar():
            nome = campos["name"].get().strip() if campos["name"].cget("state") != "disabled" \
                else dados.get("name", "")
            senha = campos["password"].get()
            if not nome:
                messagebox.showwarning("Falta o apelido", "Dê um nome para a entrada.", parent=janela)
                return
            if not senha:
                messagebox.showwarning("Falta a senha", "A senha não pode ficar vazia.", parent=janela)
                return
            if nome in self.vault["entries"] and nome != dados.get("name"):
                if not messagebox.askyesno("Já existe", f"“{nome}” já existe. Sobrescrever?", parent=janela):
                    return
            notas = campos["notes"].get("1.0", "end").strip()
            novo = {
                "username": campos["username"].get().strip(),
                "url": campos["url"].get().strip(),
                "password": senha,
                "notes": notas,
            }
            anterior = self.vault["entries"].get(nome)
            self.vault["entries"][nome] = cofre.montar_entrada(self.f, novo, anterior)
            cofre.save_vault(self.vault)
            self.selecionado = nome
            janela.destroy()
            self.atualizar_lista()
            self._mostrar_detalhes()
            self.status(f"salva: {nome}")

        ctk.CTkButton(janela, text="Gerar senha forte", width=140, height=30,
                      fg_color="#2f9e6e", hover_color="#26815b", command=gerar).grid(
            row=5, column=0, sticky="w", padx=16, pady=(14, 0))
        ctk.CTkButton(janela, text="Salvar", height=36, command=salvar).grid(
            row=6, column=1, sticky="e", padx=16, pady=(18, 16))

    def adicionar(self) -> None:
        self._formulario("Adicionar entrada")

    def editar(self) -> None:
        if not self.selecionado:
            messagebox.showinfo("Nada selecionado", "Escolha uma entrada primeiro.")
            return
        dados = cofre.descrever_entrada(self.f, self.vault["entries"][self.selecionado])
        dados["name"] = self.selecionado
        self._formulario("Editar entrada", dados)

    def gerar(self) -> None:
        senha = cofre.gerar_senha(20, True)
        dados = {"password": senha}
        self._formulario("Nova senha gerada — dê um apelido e salve", dados)

    def apagar(self) -> None:
        if not self.selecionado:
            messagebox.showinfo("Nada selecionado", "Escolha uma entrada primeiro.")
            return
        if messagebox.askyesno("Apagar", f"Remover “{self.selecionado}” do cofre?"):
            nome = self.selecionado
            del self.vault["entries"][nome]
            cofre.save_vault(self.vault)
            self.selecionado = None
            self.detalhes_vazio(mensagem="Nenhuma entrada selecionada.")
            self.atualizar_lista()
            self.status(f"removida: {nome}")

    def importar_csv(self) -> None:
        caminho = filedialog.askopenfilename(
            title="Escolha o CSV exportado do navegador",
            filetypes=[("CSV", "*.csv"), ("Todos os arquivos", "*.*")])
        if not caminho:
            return
        try:
            cabecalhos, linhas = cofre._ler_csv(Path(caminho))
            pendentes, sem_senha, vazias = cofre.entradas_de_importacao(cabecalhos, linhas)
        except (ValueError, OSError) as e:
            messagebox.showerror("Não consegui ler o arquivo", str(e))
            return
        if not pendentes:
            messagebox.showinfo("Nada a importar", "Nenhuma linha com senha nesse arquivo.")
            return
        if not messagebox.askyesno(
            "Importar",
            f"Encontrei {len(pendentes)} entrada(s) com senha"
            + (f" ({sem_senha} sem senha, puladas)" if sem_senha else "")
            + ".\n\nImportar para o cofre?",
        ):
            return

        def trabalho():
            antes = set(self.vault["entries"])
            existentes = set(self.vault["entries"])
            importadas = atualizadas = puladas = 0
            for e in pendentes:
                nome = e["name"]
                preexistente = nome in antes
                if preexistente:
                    puladas += 1  # não sobrescreve sem pedido; --overwrite é do CLI
                    continue
                if nome in existentes:
                    i = 2
                    while f"{nome}_{i}" in existentes:
                        i += 1
                    nome = f"{nome}_{i}"
                self.vault["entries"][nome] = cofre.montar_entrada(self.f, e)
                existentes.add(nome)
                importadas += 1
            cofre.save_vault(self.vault)
            return importadas, puladas

        def ao_terminar(resultado):
            if isinstance(resultado, Exception):
                messagebox.showerror("Falha ao importar", str(resultado))
                return
            importadas, puladas = resultado
            self.atualizar_lista()
            self.status(f"importadas: {importadas}"
                        + (f"  •  já existiam: {puladas} (não sobrescritas)" if puladas else "")
                        + "  •  ⚠ apague o CSV exportado")

        self._assinc(trabalho, ao_terminar)


def main_gui() -> None:
    app = CofreApp()
    app.mainloop()


if __name__ == "__main__":
    main_gui()
