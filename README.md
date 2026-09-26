# 🔐 Cofre de Senhas

Um aplicativo em Python para **guardar suas senhas com segurança, direto no seu computador**.

- Não tem nuvem, não tem conta, não tem servidor: **nada sai da sua máquina**.
- Tudo fica guardado num único arquivo, **trancado com uma senha mestra** que só você conhece.
- Funciona em **Linux, macOS e Windows**.
- **Importa de uma vez** as senhas que já estão salvas no Chrome, Edge, Brave ou Firefox.
- Não precisa saber programar. Se você sabe abrir um terminal e digitar comandos, dá conta.

> **Em 3 linhas:** você cria um cofre com uma senha mestra, guarda quantas senhas quiser
> dentro dele, e usa a senha mestra para abrir e ver o que está lá.

---

## Sumário

1. [O que você precisa ter](#1-o-que-você-precisa-ter)
2. [Instalação passo a passo](#2-instalação-passo-a-passo)
3. [Primeiros passos (tutorial completo)](#3-primeiros-passos-tutorial-completo)
4. [Todos os comandos](#4-todos-os-comandos)
5. [Importar senhas do navegador](#5-importar-senhas-do-navegador)
6. [Onde ficam os seus dados + backup](#6-onde-ficam-os-seus-dados--backup)
7. [Erros comuns e como resolver](#7-erros-comuns-e-como-resolver)
8. [Perguntas frequentes](#8-perguntas-frequentes)
9. [Dicas de segurança (para leigos)](#9-dicas-de-segurança-para-leigos)
10. [Como funciona por dentro (técnico)](#10-como-funciona-por-dentro-técnico)

---

## 1. O que você precisa ter

| O que | Por quê | Onde baixar |
|---|---|---|
| **Python 3.10 ou mais novo** | é a linguagem do app | [python.org/downloads](https://www.python.org/downloads/) |
| **uv** (recomendado) | instala as dependências em 1 comando | veja abaixo |

**Para instalar o uv** (escolha o seu sistema):

- **Linux/macOS** — abra o terminal e cole:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Windows** — abra o *PowerShell* e cole:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

> Não quer instalar o uv? Também funciona só com Python — veja o
> [método alternativo](#método-alternativo-sem-uv) na seção de instalação.

**Não tem certeza se já tem Python?** Abra o terminal (Linux/macOS) ou o PowerShell (Windows) e digite:

```bash
python3 --version    # Linux/macOS
```
```powershell
python --version     # Windows
```

Se aparecer `Python 3.10...` ou maior, está pronto. Se der "comando não encontrado", instale em [python.org](https://www.python.org/downloads/).

---

## 2. Instalação passo a passo

### Linux e macOS

```bash
git clone https://github.com/danielfilhodev/cofre-senhas.git
cd cofre-senhas
uv sync
```

Pronto. A partir de agora você usa o app assim:

```bash
uv run main.py <comando>       # forma completa
```

**Opcional — criar o atalho `cofre`** para não digitar `uv run main.py` toda vez:

```bash
# Linux (edite o caminho e cole no ~/.bashrc)
export PATH="/caminho/para/cofre-senhas:$PATH"

# macOS (edite e cole no ~/.zshrc)
export PATH="/caminho/para/cofre-senhas:$PATH"
```

Depois feche e abra o terminal de novo e teste:

```bash
cofre --help        # agora funciona de qualquer pasta
```

### Windows

Abra o **PowerShell** e digite:

```powershell
git clone https://github.com/danielfilhodev/cofre-senhas.git
cd cofre-senhas
uv sync
```

Uso:

```powershell
uv run main.py <comando>
```

> ⚠️ No Windows **não existe o atalho `cofre`** (ele é um script Unix). Use sempre
> `uv run main.py ...`. O resto funciona igual.

### Método alternativo (sem uv)

Se não conseguiu instalar o uv, use o Python puro:

```bash
# Linux/macOS
python3 -m venv .venv
.venv/bin/pip install cryptography
.venv/bin/python main.py --help
```
```powershell
# Windows
py -3 -m venv .venv
.venv\Scripts\pip install cryptography
.venv\Scripts\python main.py --help
```

Nesse caso troque `uv run main.py` por `.venv/bin/python main.py`
(Windows: `.venv\Scripts\python main.py`) em todos os comandos deste guia.

---

## 3. Primeiros passos (tutorial completo)

Siga na ordem. O que está depois do `#` em cada linha é uma explicação.

### Passo 1 — Criar o cofre (rode **uma única vez**)

```bash
uv run main.py init
```

```
Senha mestra:            ← você digita a senha e ela NÃO aparece na tela
Repita a senha mestra:   ← digita de novo para conferir
cofre criado em /home/voce/.cofre_senhas/vault.json
```

**A senha mestra é a chave de tudo.** Escolha algo forte e que você consiga lembrar
(ex.: uma frase de 4 palavras). Ela não é guardada em lugar nenhum — se você esquecer,
**não existe "recuperar senha"**: só resta recomeçar o cofre.

### Passo 2 — Guardar a primeira senha

```bash
uv run main.py add gmail -u voce@gmail.com --url https://gmail.com
```

```
Senha:                    ← digita a senha do seu e-mail (também não aparece)
salva: gmail
```

Opcional: `--url` e `-u` podem ficar de fora. O mínimo é o nome e a senha.

```bash
uv run main.py add banco
```

### Passo 3 — Listar o que está guardado

```bash
uv run main.py list
```

```
- gmail  voce@gmail.com

1 entrada(s)
```

Repare: **aparecem só os nomes, nunca as senhas.** Para ver uma senha você abre
a entrada específica (próximo passo).

### Passo 4 — Ver uma senha guardada

```bash
uv run main.py get gmail
```

```
nome:     gmail
usuário:  voce@gmail.com
url:      https://gmail.com
senha:    minhasenha123
atual.:   2026-09-26 07:13
```

> Antes de mostrar, ele pede a senha mestra para destravar o cofre.
> Não importa se você digitar `Gmail`, `GMAIL` ou `gmail` — a busca ignora
> maiúsculas e minúsculas.

### Passo 5 — Gerar uma senha forte

Nem precisa inventar: o app sorteia uma senha difícil de adivinhar.

```bash
uv run main.py gen                 # gera e só mostra (não salva)
uv run main.py gen --add netflix   # gera e já guarda no cofre com o nome "netflix"
uv run main.py gen -l 32           # 32 caracteres
uv run main.py gen --no-symbols    # sem símbolos (!@#...), se o site não aceitar
```

### Passo 6 — Apagar uma senha que não usa mais

```bash
uv run main.py del netflix
```

```
remover 'netflix'? [s/N] s        ← ele pergunta antes de apagar
removida: netflix
```

Use `-y` para não receber a pergunta (apaga direto).

### Passo 7 — Trocar a senha mestra (quando quiser)

```bash
uv run main.py passwd
```

Ele pede a senha atual, depois a nova (duas vezes). **As senhas guardadas continuam
as mesmas** — só muda o "trinco" do cofre.

> Já tem um monte de senha no navegador? Pule para a
> [seção 5](#5-importar-senhas-do-navegador) e traga tudo de uma vez.

---

## 4. Todos os comandos

| Comando | O que faz | Exemplo |
|---|---|---|
| `init` | cria o cofre e define a senha mestra (1× só) | `uv run main.py init` |
| `add <nome>` | guarda/atualiza uma entrada | `uv run main.py add gmail -u joao@gmail.com` |
| `get <nome>` | mostra uma entrada inteira | `uv run main.py get gmail` |
| `get <nome> --raw` | mostra **só** a senha (para colar num script) | `uv run main.py get gmail --raw` |
| `list` | lista os nomes guardados (nunca mostra senhas) | `uv run main.py list` |
| `del <nome>` | apaga uma entrada (pede confirmação) | `uv run main.py del banco -y` |
| `import <arquivo>` | importa um CSV do navegador/gerenciador | `uv run main.py import senhas.csv` |
| `gen` | gera uma senha forte | `uv run main.py gen -l 24` |
| `gen --add <nome>` | gera e salva já no cofre | `uv run main.py gen --add netflix` |
| `passwd` | troca a senha mestra | `uv run main.py passwd` |

**Opções do `add`:**

| Opção | Significado |
|---|---|
| `-u`, `--username` | seu usuário ou e-mail no site |
| `--url` | endereço do site |
| `-n`, `--notes` | anotações livres (ex.: "pergunta secreta: nome do gato") |
| `-p`, `--password` | passa a senha por argumento — **evite**, fica no histórico do terminal |

**Opções do `import`:**

| Opção | Significado |
|---|---|
| `--dry-run` | só mostra o que seria importado, **sem gravar nada** (nem pede a senha mestra) |
| `--overwrite` | atualiza entradas que já existem com o mesmo nome (senão são puladas) |

Esqueceu algum comando? Digite `uv run main.py --help` ou
`uv run main.py add --help` — o ajuda está em português.

---

## 5. Importar senhas do navegador

Se você já salvou senhas no Chrome, Edge, Brave ou Firefox, **não precisa digitar uma
por uma**: exporte tudo num arquivo CSV e mande para o cofre de uma vez.

### Passo A — Exportar o CSV no navegador

**Chrome / Edge / Brave** (mesmo caminho nos três):

1. Abra a página `chrome://password-manager-passwords`
   (no Edge: `edge://password-manager/passwords`, no Brave: `brave://password-manager/passwords`).
2. Clique nos **3 pontinhos** ⋮ e escolha **"Exportar senhas"**.
3. Ele vai avisar que o arquivo fica com as senhas **em texto puro** — confirme.
4. Salve o arquivo (ex.: `senhas.csv`) numa pasta fácil de achar, como Downloads.

**Firefox:**

1. Abra `about:logins`.
2. ⋮ (3 pontinhos) → **"Exportar logins"** → escolha **CSV**.

> Se o navegador pedir a senha do seu usuário/computador, é normal: é uma proteção deles.

### Passo B — Conferir antes de importar (recomendado)

```bash
uv run main.py import Downloads/senhas.csv --dry-run
```

```
arquivo:  Downloads/senhas.csv
entradas com senha: 47  |  sem senha: 2
  - GitHub
  - Google
  - uol.com.br
  ...

modo de teste (--dry-run): nada foi gravado.
```

Assim você vê quantas entradas seriam importadas **sem tocar no cofre** — e nem é
pedida a senha mestra.

### Passo C — Importar de verdade

```bash
uv run main.py import Downloads/senhas.csv
```

```
arquivo:  Downloads/senhas.csv
entradas com senha: 47  |  sem senha: 2

importadas:    47
sem senha:     2

⚠ apague o CSV exportado — ele contém suas senhas em texto puro.
```

Depois confira com `uv run main.py list` e abra uma ou duas entradas com `get`
para garantir que as senhas estão certas.

### O que acontece com cada linha

- **Sem senha na linha** → é pulada (contada no resumo).
- **Sem nome** → o app usa o **domínio da URL** (ex.: `uol.com.br`); sem URL e sem
  nome, usa o usuário; em último caso, gera um nome genérico.
- **Nome repetido no CSV** → a segunda vira `GitHub_2`, a terceira `GitHub_3`...
- **Nome que já existe no cofre** → é **pulada**, para não sobrescrever o que você já
  guardou. Para atualizar mesmo assim, use `--overwrite`.
- **Colunas diferentes** (`name`/`title`, `url`/`origin`, `note`/`extra`...) → o app
  reconhece sozinho. Aceita separador `,` `;` ou tab, com ou sem acento, e também
  exportações de LastPass, 1Password e KeePassXC.

### ⚠️ Depois de importar: apague o CSV

O arquivo exportado contém suas senhas **abertas para qualquer um que abra o arquivo**.

1. Apague o `senhas.csv` (e esvazie a lixeira).
2. Se exportou por engano para um lugar sincronizado (OneDrive, Google Drive), apague
   também a cópia na nuvem.
3. O cofre, esse sim, fica cifrado — pode ficar tranquilo.

### Se o navegador não exportar CSV

Alguns navegadores só permitem copiar senha por senha. Nesse caso, cadastre manualmente
com `add` — de site em site.

---

## 6. Onde ficam os seus dados + backup

| Sistema | Local do cofre |
|---|---|
| Linux | `~/.cofre_senhas/vault.json` |
| macOS | `~/.cofre_senhas/vault.json` |
| Windows | `C:\Users\voce\.cofre_senhas\vault.json` |

- Em Linux/macOS a pasta tem permissão `700` e o arquivo `600` (só o seu usuário lê).
- O arquivo é **ilegível sem a senha mestra**: é só texto embaralhado.
- O caminho pode ser mudado definindo a variável de ambiente `COFRE_DIR`.

**Backup (muito importante):**

```bash
cp ~/.cofre_senhas/vault.json /caminho/do/seu/backup/
```

Copie o arquivo de vez em quando para um HD externo ou pen drive.
A cópia sozinha não serve para nada sem a senha mestra — guarde essa **em outro lugar**
(papel na gaveta, por exemplo). Juntos, eles recuperam tudo; separados, não valem nada
para alguém que roubar um dos dois.

---

## 7. Erros comuns e como resolver

| Mensagem | Causa | O que fazer |
|---|---|---|
| `erro: cofre não existe ainda — rode: ... init` | você ainda não criou o cofre | rode `init` |
| `erro: senha mestra incorreta` | digitou errado | confira o Caps Lock e digite de novo |
| `erro: cofre já existe em ...` | rodou `init` duas vezes | não precisa recriar; siga com `add` |
| `erro: entrada 'x' não encontrada` | o nome não existe (o app já ignora maiúsculas) | rode `list` para ver os nomes |
| `erro: arquivo não encontrado: x.csv` | caminho errado no `import` | confira onde o navegador salvou (geralmente `Downloads`) e passe o caminho completo |
| `erro: não achei uma coluna de senha no CSV` | o arquivo não é um export de senhas | exporte de novo seguindo a [seção 5](#5-importar-senhas-do-navegador) |
| `command not found: uv` / `'uv' não é reconhecido` | uv não instalado, ou terminal aberto antes da instalação | feche e abra o terminal de novo, ou use o [método sem uv](#método-alternativo-sem-uv) |
| `No module named 'cryptography'` | dependência não instalada | rode `uv sync` (ou `pip install cryptography` no venv) |
| `permission denied` ao salvar | falta de permissão na pasta | rode **sem** `sudo`; confira as permissões de `~/.cofre_senhas` |
| Digitei a senha e nada apareceu | normal: a senha digitada não é exibida | termine de digitar e aperte **Enter** |

**Importante:** não existe recuperação de senha mestra. Se esquecer, o conteúdo antigo
não pode ser salvo (por segurança, não há como resetar). Por isso anote a senha mestra
em local físico seguro.

---

## 8. Perguntas frequentes

**Já tenho todas as minhas senhas no Chrome. Preciso digitar tudo de novo?**
Não. Exporte o CSV no navegador e rode `import` — veja a
[seção 5](#5-importar-senhas-do-navegador). Em segundos está tudo no cofre.

**Esqueci a senha mestra. E agora?**
Infelizmente não há o que fazer — é proposital: se existisse um jeito de resetar,
um invasor também encontraria. Recomece o cofre com `init` (apague o arquivo antigo)
e cadastre de novo as senhas que lembrar.

**Posso usar no celular?**
Não — este app roda em computador (Linux, macOS, Windows).

**Alguém consegue abrir o arquivo `vault.json` que roubar do meu PC?**
Não, sem a senha mestra. O arquivo é cifrado.

**Preciso de internet para usar?**
Não. O app funciona 100% offline. A internet só é necessária para baixar o código
a primeira vez.

**Importei e o navegador continua com as senhas dele.**
Sim, o import é uma **cópia**. Se quiser tirar do navegador: nas configurações de
senhas dele, apague as entradas (e, se o navegador sincronizar, apague também no
servidor de sincronização).

**Meu antivírus reclamou. É vírus?**
Não. É um programa Python comum, e o código-fonte está inteiro neste repositório —
o coração dele é o arquivo `main.py`, com poucas centenas de linhas.

**Posso guardar coisas que não são senhas?** (chave de Wi-Fi, PIN, código de cofre)
Pode. O campo `--notes` aceita qualquer texto, e o valor guardado é só uma string.

**Duas pessoas usam o mesmo PC?**
Cada um deve ter seu próprio usuário no sistema. O cofre fica dentro do diretório
pessoal de quem criou.

**Como copio a senha sem ela aparecer na listagem?**
`uv run main.py get gmail --raw` imprime só a senha — útil para encadear comandos,
mas quem estiver olhando a tela ainda vê.

---

## 9. Dicas de segurança (para leigos)

1. **Senha mestra forte e memorável.** Uma frase de 4 palavras é muito melhor
   que `Senha123!`. Ex.: `cavalo-marinho-panela-42`.
2. **Anote a senha mestra em papel** e guarde em local físico (gaveta, cofre).
   Nunca dentro do próprio computador.
3. **Faça backup do arquivo** `vault.json` — mas só junto com o papel da senha mestra.
4. **Apague o CSV exportado do navegador** logo depois do `import` — ele tem suas
   senhas em texto puro.
5. **Não use `-p` para digitar senhas** no terminal: fica gravado no histórico.
   Deixe o programa pedir.
6. **Bloqueie a tela do computador** quando sair do lugar (no Windows: `Win+L`;
   no macOS: `Ctrl+Cmd+Q`; no Linux: atalho do seu ambiente). Enquanto um terminal
   mostra a saída de um comando, quem estiver na frente vê.
7. **Não fotografe a tela** com senhas abertas nem mande prints para ninguém.
8. **Troque a senha mestra** de vez em quando com `passwd`.

---

## 10. Como funciona por dentro (técnico)

Para quem quer conferir antes de confiar:

- **Derivação de chave:** PBKDF2-HMAC-SHA256, 600.000 iterações, salt aleatório
  de 128 bits por cofre. A senha mestra nunca é gravada — só a chave derivada.
- **Cifra:** `Fernet` da biblioteca `cryptography` (AES-128-CBC + HMAC-SHA256),
  ou seja, os dados são confidenciais **e** autenticados: qualquer adulteração
  manual do arquivo invalida a leitura.
- **Verificador:** um bloco cifrado de conteúdo conhecido detecta senha mestra
  errada sem vazar informação nenhuma.
- **Armazenamento:** JSON, sem metadados sensíveis. Cada senha de entrada é um
  token Fernet individual.
- **Importação:** o CSV é lido com detecção de codificação (UTF-8 com/sem BOM,
  latin-1) e de separador (`,` `;` tab); as colunas são reconhecidas por sinônimos.
  O arquivo é lido localmente — nada vai para a rede.
- **Permissões:** pasta `700`, arquivo `600`, escrita atômica (arquivo temporário
  + troca) para não corromper o cofre se o programa fechar no meio.
- **Sem rede:** o app não faz nenhuma requisição.

---

## Estrutura do projeto

```
cofre-senhas/
├── main.py                 # o app inteiro (CLI com argparse)
├── cofre                   # atalho de shell (Linux/macOS)
├── README.md               # este guia
├── pyproject.toml          # dependências
├── uv.lock                 # versões travadas
├── tests/test_cofre.py     # suíte de testes (pytest)
└── .github/workflows/ci.yml# CI: roda os testes em Linux, Windows e macOS
```

## Testes e integração contínua

```bash
uv sync          # instala também o pytest (grupo de desenvolvimento)
uv run pytest -q
```

Os testes cobrem o fluxo completo: criação do cofre, senha mestra errada,
adicionar/ver/listar/apagar, gerador de senhas, troca de senha mestra e a
importação de CSV (Chrome, Firefox, separador `;`, dry-run, reimportação).
Cada teste roda o `main.py` como subprocesso, com o cofre em pasta temporária —
ou seja, exatamente o caminho que o usuário usa.

A **GitHub Actions** (`.github/workflows/ci.yml`) roda essa suíte em **Linux,
Windows e macOS** a cada push na `main` e a cada pull request. Um PR só deve
ser mesclado com a CI verde.
