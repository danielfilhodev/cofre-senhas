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
MIN_MESTRA = 8   # tamanho mínimo da senha mestra ao criar o cofre pela janela


def _alinhar_esquerda(btn: ctk.CTkButton) -> None:
    """Texto de várias linhas alinhado à esquerda. O CTkButton não expõe
    `justify`; o rótulo interno é recriado quando o texto fica vazio, então
    chame de novo depois de cada `configure(text=...)`."""
    rotulo = getattr(btn, "_text_label", None)
    if rotulo is not None:
        rotulo.configure(justify="left")


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
        self._pool: list = []              # botões reaproveitados (só os que cabem na tela)
        self._pool_estado: list = []       # (rótulo, selecionado) desenhado em cada botão
        self._pool_nomes: list = []        # entrada mostrada em cada botão
        self._alt_linha: int | None = None # altura de uma linha, em pixels
        self._topo = 0                     # índice da primeira linha visível
        self._ultima_busca = ""
        self._linhas_visiveis: list | None = None
        self._detalhes_mostrados: str | None = None
        self._busca_debounce = None
        self._cor_padrao_linha = None      # capturada do primeiro botão
        self._hover_padrao_linha = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._montar_login()
        self._montar_criacao()
        self._montar_principal()
        if cofre.VAULT_PATH.exists():
            self.login_view.tkraise()
        else:   # primeiro uso: cria o cofre aqui mesmo, sem terminal
            self.criar_view.tkraise()
            self.entry_nova.focus_set()

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

    def _montar_criacao(self) -> None:
        """Tela do primeiro uso: define a senha mestra e cria o cofre vazio."""
        self.criar_view = ctk.CTkFrame(self, fg_color="transparent")
        self.criar_view.grid(row=0, column=0, sticky="nsew")
        caixa = ctk.CTkFrame(self.criar_view, corner_radius=20)
        caixa.place(relx=0.5, rely=0.5, anchor="center")
        caixa.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(caixa, text="🔐 Criar seu cofre", font=FONTE_TITULO).grid(
            row=0, column=0, padx=30, pady=(30, 4))
        ctk.CTkLabel(
            caixa, text="Escolha uma senha mestra. Ela abre o cofre e\n"
                        "é a única senha que você vai precisar decorar.",
            font=FONTE_NORMAL, text_color="#9aa4b2", justify="center").grid(
            row=1, column=0, padx=30)

        self.entry_nova = ctk.CTkEntry(caixa, placeholder_text=f"Senha mestra (mín. {MIN_MESTRA} caracteres)",
                                       show="*", width=320, height=40)
        self.entry_nova.grid(row=2, column=0, padx=30, pady=(22, 8))
        self.entry_nova.bind("<Return>", lambda _e: self.entry_confirma.focus_set())
        self.entry_confirma = ctk.CTkEntry(caixa, placeholder_text="Repita a senha mestra",
                                           show="*", width=320, height=40)
        self.entry_confirma.grid(row=3, column=0, padx=30, pady=(0, 10))
        self.entry_confirma.bind("<Return>", lambda _e: self.criar())

        ctk.CTkLabel(
            caixa, text="⚠ Não existe \"esqueci a senha\": sem ela, ninguém\n"
                        "(nem você) consegue abrir o cofre. Anote num papel.",
            font=FONTE_PEQUENA, text_color="#ffd166", justify="center").grid(
            row=4, column=0, padx=30, pady=(2, 10))

        self.btn_criar = ctk.CTkButton(caixa, text="Criar cofre", height=40, width=320,
                                       fg_color="#2f9e6e", hover_color="#26815b",
                                       command=self.criar, font=FONTE_NORMAL)
        self.btn_criar.grid(row=5, column=0, padx=30, pady=(4, 8))

        self.lbl_criar_erro = ctk.CTkLabel(caixa, text="", text_color="#ff6b6b",
                                           font=FONTE_PEQUENA, wraplength=320)
        self.lbl_criar_erro.grid(row=6, column=0, padx=30)
        self.lbl_caminho = ctk.CTkLabel(caixa, text=f"será salvo em: {cofre.VAULT_PATH}",
                                        font=FONTE_PEQUENA, text_color="#6b7280", wraplength=340)
        self.lbl_caminho.grid(row=7, column=0, padx=30, pady=(0, 22))

    def criar(self) -> None:
        senha, repetida = self.entry_nova.get(), self.entry_confirma.get()
        if len(senha) < MIN_MESTRA:
            self.lbl_criar_erro.configure(text=f"Use pelo menos {MIN_MESTRA} caracteres.")
            return
        if senha != repetida:
            self.lbl_criar_erro.configure(text="As duas senhas não conferem.")
            return
        self.lbl_criar_erro.configure(text="")
        self.btn_criar.configure(state="disabled", text="Criando…")

        def ao_terminar(resultado):
            self.btn_criar.configure(state="normal", text="Criar cofre")
            if isinstance(resultado, Exception):
                self.lbl_criar_erro.configure(text=f"Não consegui criar o cofre: {resultado}")
                return
            self.entry_nova.delete(0, "end")
            self.entry_confirma.delete(0, "end")
            self.vault, self.f = resultado
            self.selecionado = None
            self.main_view.tkraise()
            self.atualizar_lista()
            self.status(f"cofre criado em {cofre.VAULT_PATH}")

        self._assinc(lambda: cofre.criar_cofre(senha), ao_terminar)

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
        self.btn_novo = ctk.CTkButton(topo, text="＋ Nova entrada  ▾", width=160, height=34,
                                      fg_color="#2f9e6e", hover_color="#26815b",
                                      command=self.alternar_menu_novo)
        self.btn_novo.grid(row=0, column=1, sticky="e", padx=(0, 8))
        ctk.CTkButton(topo, text="Travar", width=90, height=34, fg_color="#444b57",
                      hover_color="#343a44", command=self.travar).grid(row=0, column=2, sticky="e")

        # coluna esquerda: busca + lista
        esq = ctk.CTkFrame(self.main_view, corner_radius=14, width=320)
        esq.grid(row=1, column=0, sticky="nsw", padx=(16, 8), pady=8)
        esq.grid_rowconfigure(2, weight=1)
        esq.grid_columnconfigure(0, weight=1)
        esq.pack_propagate(False)

        ctk.CTkLabel(esq, text="Suas entradas", font=FONTE_TITULO).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(14, 6))
        self.entry_busca = ctk.CTkEntry(esq, placeholder_text="🔍 buscar por nome, usuário ou url",
                                        height=34)
        self.entry_busca.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8))
        self.entry_busca.bind("<KeyRelease>", lambda _e: self._ao_digitar())

        # lista virtual: só existem botões para as linhas que cabem na tela;
        # rolar troca o texto deles em vez de criar um widget por entrada
        self.lista = ctk.CTkFrame(esq, fg_color="transparent")
        self.lista.grid(row=2, column=0, sticky="nsew", padx=(6, 0), pady=(0, 10))
        self.lista.grid_columnconfigure(0, weight=1)
        self.lista.grid_propagate(False)
        self.lista.bind("<Configure>", lambda _e: self._ajustar_pool())
        self.barra = ctk.CTkScrollbar(esq, command=self._rolar_barra)
        self.barra.grid(row=2, column=1, sticky="ns", padx=(0, 6), pady=(0, 10))
        self.bind_all("<MouseWheel>", self._rolar_roda, add="+")
        self.bind_all("<Button-4>", self._rolar_roda, add="+")   # Linux/X11
        self.bind_all("<Button-5>", self._rolar_roda, add="+")
        self.lbl_total = ctk.CTkLabel(esq, text="0 entrada(s)", font=FONTE_PEQUENA,
                                      text_color="#9aa4b2")
        self.lbl_total.grid(row=3, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 12))

        # coluna direita: detalhes
        dir_ = ctk.CTkFrame(self.main_view, corner_radius=14)
        dir_.grid(row=1, column=1, sticky="nsew", padx=(8, 16), pady=8)
        dir_.grid_columnconfigure(0, weight=1)
        self.detalhes = ctk.CTkFrame(dir_, fg_color="transparent")
        self.detalhes.grid(row=0, column=0, sticky="nsew", padx=24, pady=18)
        self.detalhes.grid_columnconfigure(1, weight=1)

        # ações da entrada selecionada: só aparecem quando há uma seleção
        self.acoes_entrada = ctk.CTkFrame(dir_, fg_color="transparent")
        self.acoes_entrada.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 18))
        ctk.CTkButton(self.acoes_entrada, text="Editar", width=120, height=36,
                      command=self.editar).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(self.acoes_entrada, text="Apagar", width=120, height=36,
                      fg_color="#b03a3a", hover_color="#8f2f2f",
                      command=self.apagar).grid(row=0, column=1)
        self.acoes_entrada.grid_remove()

        self._montar_menu_novo()

        self.lbl_status = ctk.CTkLabel(self.main_view, text="", font=FONTE_PEQUENA,
                                       text_color="#9aa4b2", anchor="w")
        self.lbl_status.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 10))

        self.detalhes_vazio()

    # ------------------------------------------------------ menu "Nova entrada"
    def _montar_menu_novo(self) -> None:
        """Menu suspenso do botão "＋ Nova entrada": as formas de criar entradas."""
        self.menu_novo = ctk.CTkFrame(self.main_view, corner_radius=10, border_width=1,
                                      fg_color="#2b2f36", border_color="#3a404a")
        self._opcoes_menu_novo = []
        for i, (texto, dica, cmd) in enumerate([
            ("✏  Preencher manualmente", "você digita usuário e senha", self.adicionar),
            ("🎲  Com senha forte gerada", "o cofre cria uma senha de 20 caracteres", self.gerar),
            ("📥  Importar do navegador…", "CSV exportado do Chrome, Edge, Firefox…",
             self.importar_csv),
        ]):
            btn = ctk.CTkButton(
                self.menu_novo, text=f"{texto}\n{dica}", anchor="w", width=290, height=50,
                corner_radius=8, fg_color="transparent", hover_color="#3a404a",
                font=FONTE_PEQUENA, command=lambda c=cmd: self._escolher_no_menu(c))
            btn.grid(row=i, column=0, sticky="ew", padx=6, pady=(6 if i == 0 else 0, 6))
            _alinhar_esquerda(btn)
            self._opcoes_menu_novo.append(btn)
        self.bind_all("<Button-1>", self._clique_fora_do_menu, add="+")
        self.bind_all("<Escape>", lambda _e: self.fechar_menu_novo(), add="+")

    def menu_novo_aberto(self) -> bool:
        return bool(self.menu_novo.winfo_manager())

    def alternar_menu_novo(self) -> None:
        if self.menu_novo_aberto():
            self.fechar_menu_novo()
            return
        # logo abaixo do botão, alinhado pela direita
        self.menu_novo.place(in_=self.btn_novo, relx=1.0, rely=1.0, anchor="ne", y=6)
        self.menu_novo.lift()

    def fechar_menu_novo(self) -> None:
        self.menu_novo.place_forget()

    def _escolher_no_menu(self, acao) -> None:
        self.fechar_menu_novo()
        acao()

    def _clique_fora_do_menu(self, evento) -> None:
        if not self.menu_novo_aberto():
            return
        w = evento.widget
        dentro = (self.menu_novo, self.btn_novo)
        while w is not None:
            if w in dentro:
                return
            w = getattr(w, "master", None)
        self.fechar_menu_novo()

    def _mostrar_acoes(self, visiveis: bool) -> None:
        if visiveis:
            self.acoes_entrada.grid()
        else:
            self.acoes_entrada.grid_remove()

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
                cofre.migrar_formato(vault, f)
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
        self.fechar_menu_novo()
        self.selecionado = None
        self._linhas_visiveis = None
        self._topo = 0
        self._desenhar()   # esvazia as linhas: nada do cofre fica nos widgets
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

    def _ao_digitar(self) -> None:
        """Debounce: espera a digitação assentar antes de filtrar (90 ms)."""
        if self._busca_debounce is not None:
            self.after_cancel(self._busca_debounce)
        self._busca_debounce = self.after(90, self.atualizar_lista)

    # ------------------------------------------------------ lista virtual
    def _novo_botao(self, slot: int):
        btn = ctk.CTkButton(
            self.lista, text="", anchor="w", height=48, corner_radius=10,
            font=FONTE_NORMAL,
            command=lambda: self._clicar_linha(slot),
        )
        if self._cor_padrao_linha is None:
            # guarda as cores do tema para restaurar quando sair da seleção
            self._cor_padrao_linha = btn.cget("fg_color")
            self._hover_padrao_linha = btn.cget("hover_color")
        btn.grid(row=slot, column=0, sticky="ew", padx=4, pady=3)
        btn.grid_remove()   # só aparece quando tiver uma entrada para mostrar
        return btn

    def _clicar_linha(self, slot: int) -> None:
        if slot < len(self._pool_nomes) and self._pool_nomes[slot]:
            self.selecionar(self._pool_nomes[slot])

    def _linhas_inteiras(self) -> int:
        """Quantas linhas cabem inteiras na área da lista."""
        if not self._alt_linha:
            return 1
        return max(1, self.lista.winfo_height() // self._alt_linha)

    def _ajustar_pool(self) -> None:
        """Cria/destrói botões para caber exatamente na altura atual da lista."""
        if not self._pool:
            self._pool.append(self._novo_botao(0))
            self._pool_estado.append(None)
            self._pool_nomes.append(None)
            # altura do botão (já com a escala de DPI) + pady 3 em cima e embaixo
            req = self._pool[0].winfo_reqheight()
            self._alt_linha = max(1, round(req * 54 / 48))
        precisa = self._linhas_inteiras() + 1   # +1 para a linha cortada no fim
        while len(self._pool) < precisa:
            self._pool.append(self._novo_botao(len(self._pool)))
            self._pool_estado.append(None)
            self._pool_nomes.append(None)
        while len(self._pool) > precisa:
            self._pool.pop().destroy()
            self._pool_estado.pop()
            self._pool_nomes.pop()
        self._desenhar()

    def _rotulo(self, nome: str) -> str:
        e = self.vault["entries"][nome]
        return nome + (f"\n{e['username']}" if e.get("username") else "")

    def _desenhar(self) -> None:
        """Mostra nos botões do pool as entradas a partir de `_topo`. Só mexe
        no botão cujo texto ou cor mudou — é isso que deixa a rolagem leve."""
        nomes = self._linhas_visiveis if self.vault else []
        nomes = nomes or []
        inteiras = self._linhas_inteiras()
        self._topo = max(0, min(self._topo, len(nomes) - inteiras))
        for i, btn in enumerate(self._pool):
            idx = self._topo + i
            nome = nomes[idx] if idx < len(nomes) else None
            self._pool_nomes[i] = nome
            if nome is None:
                if self._pool_estado[i] is not None:
                    btn.grid_remove()
                    self._pool_estado[i] = None
                continue
            estado = (self._rotulo(nome), nome == self.selecionado)
            if self._pool_estado[i] == estado:
                continue
            if self._pool_estado[i] is None:
                btn.grid()
            texto, selecionado = estado
            if selecionado:
                btn.configure(text=texto, fg_color="#2b7fff", hover_color="#1f5fbf")
            else:
                btn.configure(text=texto, fg_color=self._cor_padrao_linha,
                              hover_color=self._hover_padrao_linha)
            _alinhar_esquerda(btn)
            self._pool_estado[i] = estado
        if nomes:
            self.barra.set(self._topo / len(nomes),
                           min(1.0, (self._topo + inteiras) / len(nomes)))
        else:
            self.barra.set(0.0, 1.0)

    def _rolar_para(self, topo: float) -> None:
        self._topo = int(topo)
        self._desenhar()

    def _rolar_barra(self, *args) -> None:
        total = len(self._linhas_visiveis or [])
        if args[0] == "moveto":
            self._rolar_para(float(args[1]) * total)
        elif args[0] == "scroll":
            passo = int(float(args[1]))
            if len(args) > 2 and args[2] == "pages":
                passo *= self._linhas_inteiras()
            self._rolar_para(self._topo + passo)

    def _rolar_roda(self, evento) -> None:
        """Roda do mouse em cima da lista (ou de uma linha dela): 3 linhas por clique."""
        w = self.winfo_containing(evento.x_root, evento.y_root)
        raiz = str(self.lista)
        if w is None or not (str(w) == raiz or str(w).startswith(raiz + ".")):
            return
        if evento.num == 4 or getattr(evento, "delta", 0) > 0:
            self._rolar_para(self._topo - 3)
        elif evento.num == 5 or getattr(evento, "delta", 0) < 0:
            self._rolar_para(self._topo + 3)

    def _garantir_visivel(self, nome: str) -> None:
        nomes = self._linhas_visiveis or []
        if nome not in nomes:
            return
        i = nomes.index(nome)
        inteiras = self._linhas_inteiras()
        if i < self._topo:
            self._topo = i
        elif i >= self._topo + inteiras:
            self._topo = i - inteiras + 1

    def _renderizar(self, nomes: list[str]) -> None:
        busca = self.entry_busca.get()
        if busca != self._ultima_busca:   # nova busca começa do topo
            self._ultima_busca = busca
            self._topo = 0
        self._linhas_visiveis = nomes
        self._desenhar()

    def _atualizar_texto(self, nome: str) -> None:
        """Mantém o rótulo da linha em dia após uma edição, sem recriar a lista."""
        if nome in (self.vault or {}).get("entries", {}):
            self._desenhar()

    def _destacar(self) -> None:
        """Recolore só os botões cuja seleção mudou (o resto já está certo)."""
        if self.selecionado:
            self._garantir_visivel(self.selecionado)
        self._desenhar()

    def atualizar_lista(self) -> None:
        self._busca_debounce = None
        if not getattr(self, "vault", None):
            return
        nomes = self._nomes_filtrados()
        if nomes != self._linhas_visiveis:
            self._renderizar(nomes)
        total = len(self.vault["entries"])
        self.lbl_total.configure(
            text=f"{total} entrada(s)" + ("" if len(nomes) == total else f" — {len(nomes)} na busca"))
        if self.selecionado and self.selecionado not in self.vault["entries"]:
            self.selecionado = None
            self.detalhes_vazio(mensagem="Nenhuma entrada selecionada.")
        if self.selecionado:
            self._destacar()
            if self.selecionado != self._detalhes_mostrados:
                self._mostrar_detalhes()
        else:
            msg = ("Cofre vazio — clique em “＋ Nova entrada” lá em cima."
                   if not self.vault["entries"] else "Selecione uma entrada ao lado 👈")
            if self._detalhes_mostrados is not None or self._msg_vazio != msg:
                self.detalhes_vazio(mensagem=msg)

    def detalhes_vazio(self, mensagem: str = "Selecione uma entrada ao lado 👈") -> None:
        self.selecionado = None
        self._detalhes_mostrados = None
        self._msg_vazio = mensagem
        self._mostrar_acoes(False)
        for w in self.detalhes.winfo_children():
            w.destroy()
        self.detalhes.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.detalhes, text=mensagem, font=FONTE_NORMAL,
                     text_color="#9aa4b2").grid(row=0, column=0, columnspan=2, pady=40)

    def selecionar(self, nome: str, atualizar_lista: bool = True) -> None:
        """Seleciona uma linha. `atualizar_lista` é mantido por compatibilidade —
        a lista agora só re-renderiza quando o resultado da busca muda."""
        if nome not in (self.vault or {}).get("entries", {}):
            return
        self.selecionado = nome
        self._senha_visivel = False
        self._destacar()
        self._mostrar_detalhes()

    def _mostrar_detalhes(self) -> None:
        nome = self.selecionado
        if not nome:
            return
        self._detalhes_mostrados = nome
        self._mostrar_acoes(True)
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
            cofre.save_vault(self.vault, self.f)
            self.selecionado = nome
            janela.destroy()
            self.atualizar_lista()
            self._atualizar_texto(nome)   # lista é reaproveitada: renova o rótulo
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
            cofre.save_vault(self.vault, self.f)
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
            cofre.save_vault(self.vault, self.f)
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
