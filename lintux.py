#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lintux — facilitador e gerenciador de comandos e listas de execução no terminal.

Requisitos : Python 3.6 ou superior, somente com a biblioteca padrão.
Compatível : Debian, Ubuntu, Linux Mint e derivados; RHEL, Fedora, CentOS,
             AlmaLinux, Rocky Linux e derivados.
Dados      : ~/.lintux/database.json  (pode ser alterado com a variável LINTUX_HOME)

Autor      : M. A. Klippel <contato@klippelbit.app>
Projeto    : https://github.com/miqueiasklippel/lintux
Licença    : PolyForm Noncommercial License 1.0.0 (uso não comercial) — veja LICENSE.md

Visão geral da arquitetura deste arquivo:
  1. Terminal ........ cores ANSI, símbolos e mensagens padronizadas
  2. Armazenamento ... leitura, validação, gravação atômica e cópia .bak do banco
  3. Regras .......... nomes, palavras reservadas, parâmetros {{1}} e alertas de risco
  4. Execução ........ comandos individuais e listas, com histórico
  5. Subcomandos ..... add, edit, rm, list, show, mv, rename, desc, search, history,
                       new backup, add backup, help, version
  6. Ponto de entrada  roteamento dos argumentos
"""

import difflib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from datetime import datetime
from pathlib import Path

VERSAO = "1.0.0"
AUTOR = "M. A. KLIPPEL"
CONTATO = "contato@klippelbit.app"
REPOSITORIO = "https://github.com/miqueiasklippel/lintux"
ESQUEMA = 2  # versão da estrutura do database.json

# Palavras que não podem ser usadas como nome de comando ou de lista,
# porque são interpretadas pelo próprio Lintux.
RESERVADAS = {
    "add", "rm", "list", "new", "edit", "show", "help", "rename", "desc",
    "search", "history", "mv", "run", "version", "backup",
}

# Opções aceitas antes do nome na execução: lintux [opções] <nome> [args]
OPCOES_EXEC = {
    "-y": "sim", "--yes": "sim",
    "-k": "continuar", "--keep-going": "continuar",
    "-n": "simular", "--dry-run": "simular",
    "-q": "silencioso", "--quiet": "silencioso",
}
LETRAS_EXEC = {"y": "sim", "k": "continuar", "n": "simular", "q": "silencioso"}

NOME_RE = re.compile(r"^\w[\w.-]{0,63}$")
# Parâmetros: {{1}}, {{2}}, {{1:valor padrão}}, {{@}}
PARAM_RE = re.compile(r"\{\{\s*(\d+|@)\s*(?::([^}]*))?\}\}")


# =============================================================================
# 1. TERMINAL — cores, símbolos e mensagens
# =============================================================================

def _suporta_cor(fluxo):
    """Cores apenas em terminal real; respeita NO_COLOR (https://no-color.org)."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("LINTUX_FORCE_COLOR"):
        return True
    return hasattr(fluxo, "isatty") and fluxo.isatty() and os.environ.get("TERM", "") != "dumb"


class Estilo:
    """Códigos ANSI de um fluxo de saída (vazios quando não há suporte a cor)."""

    def __init__(self, fluxo):
        ativo = _suporta_cor(fluxo)

        def c(codigo):
            return codigo if ativo else ""

        self.verde = c("\033[32m")
        self.vermelho = c("\033[31m")
        self.amarelo = c("\033[33m")
        self.ciano = c("\033[36m")
        self.negrito = c("\033[1m")
        self.dim = c("\033[2m")
        self.reset = c("\033[0m")


OUT = Estilo(sys.stdout)
ERR = Estilo(sys.stderr)

# Símbolos Unicode com alternativa ASCII para terminais sem UTF-8 (ex.: locale C)
if "utf" in (getattr(sys.stdout, "encoding", "") or "").lower():
    S_OK, S_ERRO, S_ALERTA, S_SETA, S_PLAY, S_DESC, S_ITEM = "✔", "✖", "⚠", "→", "▶", "↳", "•"
else:
    S_OK, S_ERRO, S_ALERTA, S_SETA, S_PLAY, S_DESC, S_ITEM = "OK", "X", "!", "->", ">", "-", "*"


def _estilo(fluxo):
    return ERR if fluxo is sys.stderr else OUT


def sucesso(msg, fluxo=sys.stdout):
    e = _estilo(fluxo)
    print("{}{} {}{}".format(e.verde, S_OK, msg, e.reset), file=fluxo)


def erro(msg, fluxo=sys.stderr):
    e = _estilo(fluxo)
    print("{}{} Erro: {}{}".format(e.vermelho, S_ERRO, msg, e.reset), file=fluxo)


def alerta(msg, fluxo=sys.stdout):
    e = _estilo(fluxo)
    print("{}{} {}{}".format(e.amarelo, S_ALERTA, msg, e.reset), file=fluxo)


def dica(msg, fluxo=sys.stdout):
    e = _estilo(fluxo)
    print("{}  Dica: {}{}".format(e.dim, msg, e.reset), file=fluxo)


def titulo(msg, fluxo=sys.stdout):
    e = _estilo(fluxo)
    print("\n{}{}{}{}".format(e.ciano, e.negrito, msg, e.reset), file=fluxo)


def largura_terminal():
    return shutil.get_terminal_size((100, 24)).columns


def quebrar(texto, largura):
    """Quebra um texto (inclusive com várias linhas) sem cortar informação."""
    largura = max(20, largura)
    linhas = []
    for linha in (texto.splitlines() or [""]):
        partes = textwrap.wrap(linha, width=largura, break_long_words=True,
                               break_on_hyphens=False, replace_whitespace=False)
        linhas.extend(partes or [""])
    return linhas


def imprimir_bloco(texto, recuo, cor="", fluxo=sys.stdout):
    """Imprime um bloco de código recuado e quebrado na largura do terminal."""
    e = _estilo(fluxo)
    for linha in quebrar(texto, largura_terminal() - recuo - 2):
        print("{}{}{}{}".format(" " * recuo, cor, linha, e.reset if cor else ""), file=fluxo)


def formatar_duracao(segundos):
    if segundos < 60:
        return "{:.1f} s".format(segundos).replace(".", ",")
    total = int(round(segundos))
    horas, resto = divmod(total, 3600)
    minutos, seg = divmod(resto, 60)
    if horas:
        return "{} h {:02d} min {:02d} s".format(horas, minutos, seg)
    return "{} min {:02d} s".format(minutos, seg)


def confirmar(pergunta, padrao=False):
    """Pergunta sim/não no terminal. Sem terminal interativo, assume 'não'."""
    if not sys.stdin.isatty():
        return False
    opcoes = "S/n" if padrao else "s/N"
    try:
        sys.stderr.write("{}?{} {} [{}] ".format(ERR.amarelo, ERR.reset, pergunta, opcoes))
        sys.stderr.flush()
        resposta = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        return False
    if not resposta:
        return padrao
    return resposta in ("s", "sim", "y", "yes")


class ErroLintux(Exception):
    """Erro esperado, exibido de forma amigável (sem traceback)."""

    def __init__(self, mensagem, dica=None, codigo=1):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.dica = dica
        self.codigo = codigo


# =============================================================================
# 2. ARMAZENAMENTO — ~/.lintux/database.json
# =============================================================================

def pasta_lintux():
    personalizada = os.environ.get("LINTUX_HOME")
    return Path(personalizada).expanduser() if personalizada else Path.home() / ".lintux"


def arquivo_db():
    return pasta_lintux() / "database.json"


def arquivo_historico():
    return pasta_lintux() / "history.log"


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def novo_db():
    return {"schema": ESQUEMA, "commands": {}, "lists": {}}


def normalizar(dados):
    """
    Valida e converte dados para a estrutura atual. Aceita também o formato
    simplificado {"commands": {"nome": "código"}, "lists": {"lista": ["nome"]}}.
    Lança ValueError com a descrição do problema quando a estrutura é inválida.
    """
    if not isinstance(dados, dict):
        raise ValueError("o conteúdo principal do JSON não é um objeto")
    if "commands" not in dados and "lists" not in dados:
        raise ValueError("as chaves 'commands' e 'lists' não foram encontradas")
    comandos = dados.get("commands") or {}
    listas = dados.get("lists") or {}
    if not isinstance(comandos, dict) or not isinstance(listas, dict):
        raise ValueError("'commands' e 'lists' precisam ser objetos JSON")

    db = novo_db()
    for nome, valor in comandos.items():
        if isinstance(valor, str):
            valor = {"cmd": valor}
        if not isinstance(valor, dict) or not isinstance(valor.get("cmd"), str):
            raise ValueError("o comando '{}' não possui um código válido".format(nome))
        criado = valor.get("created") or agora()
        db["commands"][str(nome)] = {
            "cmd": valor["cmd"],
            "desc": str(valor.get("desc") or ""),
            "created": criado,
            "updated": valor.get("updated") or criado,
        }
    for nome, valor in listas.items():
        if isinstance(valor, list):
            valor = {"steps": valor}
        etapas = valor.get("steps") if isinstance(valor, dict) else None
        if not isinstance(etapas, list) or not all(isinstance(e, str) for e in etapas):
            raise ValueError("a lista '{}' não possui etapas válidas".format(nome))
        criado = valor.get("created") or agora()
        db["lists"][str(nome)] = {
            "steps": list(etapas),
            "desc": str(valor.get("desc") or ""),
            "created": criado,
            "updated": valor.get("updated") or criado,
        }
    return db


def salvar_db(db):
    """Grava de forma atômica (arquivo temporário + rename) e guarda a versão anterior em .bak."""
    pasta = pasta_lintux()
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    destino = arquivo_db()
    if destino.exists():
        try:
            shutil.copy2(str(destino), str(destino) + ".bak")
        except OSError:
            pass
    descritor, temporario = tempfile.mkstemp(prefix=".database.", suffix=".tmp", dir=str(pasta))
    try:
        with os.fdopen(descritor, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporario, 0o600)
        os.replace(temporario, str(destino))
    except Exception:
        try:
            os.unlink(temporario)
        except OSError:
            pass
        raise


def carregar_db(silencioso=False):
    """Carrega o banco; na primeira execução cria ~/.lintux/ e o database.json."""
    pasta = pasta_lintux()
    arquivo = arquivo_db()
    if not arquivo.exists():
        pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        db = novo_db()
        salvar_db(db)
        if not silencioso:
            print("{}Primeira execução: banco de dados criado em {}{}".format(
                ERR.ciano, arquivo, ERR.reset), file=sys.stderr)
        return db
    restaurar = "cp '{0}.bak' '{0}'".format(arquivo)
    try:
        with arquivo.open(encoding="utf-8") as f:
            dados = json.load(f)
    except ValueError as e:  # JSONDecodeError e UnicodeDecodeError
        raise ErroLintux("o banco de dados {} está corrompido ({}).".format(arquivo, e),
                         dica="Recupere a versão anterior com: " + restaurar)
    except OSError as e:
        raise ErroLintux("não foi possível ler {}: {}".format(arquivo, e))
    try:
        return normalizar(dados)
    except ValueError as e:
        raise ErroLintux("estrutura inválida em {}: {}.".format(arquivo, e),
                         dica="Recupere a versão anterior com: " + restaurar)


def registrar_historico(nome, tipo, codigo, duracao):
    """Acrescenta uma linha JSON ao histórico e mantém apenas as 2000 mais recentes."""
    arquivo = arquivo_historico()
    registro = {"data": agora(), "nome": nome, "tipo": tipo,
                "codigo": codigo, "duracao": round(duracao, 2)}
    try:
        with arquivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        if arquivo.stat().st_size > 512 * 1024:
            linhas = arquivo.read_text(encoding="utf-8").splitlines()[-2000:]
            arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    except OSError:
        pass  # o histórico nunca deve impedir a execução


# =============================================================================
# 3. REGRAS — nomes, parâmetros e alertas de risco
# =============================================================================

def nome_valido(nome):
    return bool(NOME_RE.match(nome)) and nome.lower() not in RESERVADAS


def validar_nome(db, nome):
    """Garante que o nome é aceitável e ainda não está em uso."""
    if not NOME_RE.match(nome):
        raise ErroLintux("o nome '{}' é inválido.".format(nome),
                         dica="Use letras, números, '_', '-' ou '.', começando por letra ou número "
                              "(máximo de 64 caracteres, sem espaços).")
    if nome.lower() in RESERVADAS:
        raise ErroLintux("'{}' é uma palavra reservada do Lintux e não pode ser usada como nome.".format(nome),
                         dica="Palavras reservadas: " + ", ".join(sorted(RESERVADAS)))
    if nome in db["commands"]:
        raise ErroLintux("já existe um comando chamado '{}'.".format(nome),
                         dica="Para alterá-lo use: lintux edit {} '<novo comando>'".format(nome))
    if nome in db["lists"]:
        raise ErroLintux("já existe uma lista chamada '{}'.".format(nome),
                         dica="Comandos e listas compartilham os mesmos nomes; escolha outro.")


def sugestoes(db, nome):
    candidatos = list(db["commands"]) + list(db["lists"])
    return difflib.get_close_matches(nome, candidatos, n=3, cutoff=0.6)


def nao_encontrado(db, nome, oque="comando ou lista"):
    sufixo = "a" if oque == "lista" else "o"
    parecidos = sugestoes(db, nome)
    if parecidos:
        texto_dica = "Você quis dizer: {}?".format(", ".join(parecidos))
    else:
        texto_dica = "Use 'lintux list' para ver tudo o que está salvo."
    raise ErroLintux("{} '{}' não encontrad{}.".format(oque, nome, sufixo), dica=texto_dica)


def listas_que_usam(db, comando):
    return [n for n, l in sorted(db["lists"].items()) if comando in l["steps"]]


def descrever_parametros(codigo):
    """Retorna descrições legíveis dos parâmetros {{...}} presentes no código."""
    vistos, resultado = set(), []
    for m in PARAM_RE.finditer(codigo):
        chave, padrao = m.group(1), m.group(2)
        if (chave, padrao) in vistos:
            continue
        vistos.add((chave, padrao))
        if chave == "@":
            resultado.append("{{@}} todos os argumentos")
        elif padrao is not None:
            resultado.append("{{%s}} opcional (padrão: '%s')" % (chave, padrao))
        else:
            resultado.append("{{%s}} obrigatório" % chave)
    return resultado


def resolver_parametros(codigo, args, anexar=True):
    """
    Substitui {{1}}, {{2:padrão}} e {{@}} pelos argumentos, sempre protegidos com
    shlex.quote. Se o código não tiver parâmetros e anexar=True, os argumentos
    são acrescentados ao final do comando (ex.: lintux ver -la → 'ls' + ' -la').
    """
    if not PARAM_RE.search(codigo):
        if args and anexar:
            return codigo + " " + " ".join(shlex.quote(a) for a in args)
        return codigo

    faltando = []

    def substituir(m):
        chave, padrao = m.group(1), m.group(2)
        if chave == "@":
            if args:
                return " ".join(shlex.quote(a) for a in args)
            return shlex.quote(padrao) if padrao else ""
        indice = int(chave)
        if 1 <= indice <= len(args):
            return shlex.quote(args[indice - 1])
        if padrao is not None:
            return shlex.quote(padrao) if padrao else ""
        faltando.append(indice)
        return ""

    resultado = PARAM_RE.sub(substituir, codigo)
    if faltando:
        posicoes = ", ".join(str(p) for p in sorted(set(faltando)))
        raise ErroLintux("argumento obrigatório ausente (posição {}).".format(posicoes),
                         dica="Parâmetros deste código: " + "; ".join(descrever_parametros(codigo)))
    return resultado


# Padrões de operações potencialmente destrutivas. É uma verificação heurística:
# serve como rede de proteção, não como garantia absoluta de segurança.
_PERIGOS = [
    (r"\brm\s+(?:-\S+\s+)*(?:/|/\*|~/?|\$HOME/?|\"\$HOME\"/?)(?=\s|;|&|\||$)",
     "remoção da raiz (/) ou da pasta pessoal inteira"),
    (r"\bmkfs(?:\.\w+)?\b", "formatação de partição (mkfs)"),
    (r"\bdd\b.*\bof=/dev/(?!null\b|zero\b|stdout\b|stderr\b)", "gravação direta em dispositivo (dd of=/dev/...)"),
    (r">\s*/dev/(?:sd|hd|vd|xvd|nvme|mmcblk)\w*", "escrita direta sobre um disco"),
    (r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "fork bomb (trava o sistema)"),
    (r"\bch(?:mod|own|grp)\s+(?:-\S*R\S*\s+|--recursive\s+)(?:\S+\s+)*?/(?=\s|;|&|$)",
     "alteração recursiva de permissões ou dono na raiz (/)"),
    (r"\b(?:curl|wget)\b[^|;&\n]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b",
     "execução direta de script baixado da internet (curl/wget | sh)"),
    (r"\b(?:shutdown|poweroff|reboot|halt)\b", "desligamento ou reinicialização do sistema"),
    (r"\b(?:wipefs|shred)\b", "apagamento irreversível de dados (wipefs/shred)"),
]
PERIGOS = [(re.compile(p), d) for p, d in _PERIGOS]


def riscos(codigo):
    return [descricao for padrao, descricao in PERIGOS if padrao.search(codigo)]


def avisos_ao_salvar(codigo, varios_argumentos=False):
    """Alertas exibidos após salvar ou editar um comando."""
    for r in riscos(codigo):
        alerta("Atenção: este comando envolve {}. O Lintux pedirá confirmação antes de executá-lo.".format(r))
    parametros = descrever_parametros(codigo)
    if parametros:
        print("{}  Parâmetros: {}{}".format(OUT.dim, "; ".join(parametros), OUT.reset))
    if varios_argumentos:
        dica("na próxima vez, envolva o comando em aspas simples '...' para preservar "
             "espaços, aspas internas e operadores como && | > ;")


# =============================================================================
# 4. EXECUÇÃO
# =============================================================================

def interpretador():
    """Usa o bash quando disponível (aceita sintaxe bash); caso contrário, /bin/sh."""
    return shutil.which("bash") or "/bin/sh"


def _restaurar_sinais():
    # Executado no processo filho: garante que Ctrl+C funcione normalmente nele.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGQUIT, signal.SIG_DFL)


def executar_shell(codigo):
    """
    Executa no shell herdando stdin/stdout/stderr — a saída aparece em tempo
    real e comandos interativos (senha do sudo, confirmações [S/n]) funcionam.
    Retorna (código de saída, duração em segundos).
    """
    inicio = time.time()
    sigint_original = signal.signal(signal.SIGINT, signal.SIG_IGN)  # o Lintux não morre no Ctrl+C
    try:
        processo = subprocess.run(codigo, shell=True, executable=interpretador(),
                                  preexec_fn=_restaurar_sinais)
        codigo_saida = processo.returncode
    finally:
        signal.signal(signal.SIGINT, sigint_original)
    if codigo_saida < 0:  # encerrado por sinal → convenção do shell (128 + sinal)
        codigo_saida = 128 + (-codigo_saida)
    return codigo_saida, time.time() - inicio


def confirmar_riscos(itens):
    """itens: lista de (rótulo, [riscos]). Retorna True se o usuário confirmar."""
    alerta("Atenção: operação(ões) potencialmente destrutiva(s) detectada(s):", sys.stderr)
    for rotulo, lista in itens:
        for r in lista:
            print("    {} {}: {}".format(S_ITEM, rotulo, r), file=sys.stderr)
    if not sys.stdin.isatty():
        erro("é necessária confirmação, mas o terminal não é interativo. Use a opção -y para confirmar.")
        return False
    return confirmar("Deseja realmente continuar?")


def ler_opcoes_execucao(argv):
    """Separa as opções iniciais (-y -k -n -q) do nome e dos argumentos."""
    opcoes = {"sim": False, "continuar": False, "simular": False, "silencioso": False}
    i = 0
    while i < len(argv) and argv[i].startswith("-") and argv[i] != "-":
        atual = argv[i]
        if atual in OPCOES_EXEC:
            opcoes[OPCOES_EXEC[atual]] = True
        elif re.match(r"^-[yknq]+$", atual):
            for letra in atual[1:]:
                opcoes[LETRAS_EXEC[letra]] = True
        else:
            raise ErroLintux("opção desconhecida: {}".format(atual), dica="Veja as opções em: lintux help")
        i += 1
    return opcoes, argv[i:]


def executar_item(argv):
    opcoes, resto = ler_opcoes_execucao(argv)
    if not resto:
        raise ErroLintux("informe o nome do comando ou da lista a executar.", dica="lintux <nome>")
    nome, args = resto[0], resto[1:]

    # Permite "lintux -y rm nome" e similares.
    if nome in SUBCOMANDOS:
        extra = ["-y"] if opcoes["sim"] and nome in ("rm", "history") else []
        return SUBCOMANDOS[nome](args + extra)

    db = carregar_db()
    if nome in db["commands"]:
        return executar_comando(db, nome, args, opcoes)
    if nome in db["lists"]:
        return executar_lista(db, nome, args, opcoes)
    nao_encontrado(db, nome)


def executar_comando(db, nome, args, opcoes):
    codigo = resolver_parametros(db["commands"][nome]["cmd"], args)

    if opcoes["simular"]:
        titulo("Simulação — '{}' NÃO será executado:".format(nome))
        imprimir_bloco(codigo, 2, OUT.ciano)
        return 0

    perigos = riscos(codigo)
    if perigos and not opcoes["sim"] and not confirmar_riscos([(nome, perigos)]):
        alerta("Execução cancelada.", sys.stderr)
        return 1

    if not opcoes["silencioso"]:
        print("{}{} {}{}".format(ERR.ciano + ERR.negrito, S_PLAY, nome, ERR.reset), file=sys.stderr)
        imprimir_bloco(codigo, 2, ERR.dim, sys.stderr)

    saida, duracao = executar_shell(codigo)
    registrar_historico(nome, "comando", saida, duracao)

    if saida == 0:
        if not opcoes["silencioso"]:
            sucesso("'{}' concluído ({}).".format(nome, formatar_duracao(duracao)), sys.stderr)
    elif saida == 130:
        alerta("'{}' interrompido pelo usuário (Ctrl+C).".format(nome), sys.stderr)
    else:
        erro("'{}' terminou com código de saída {} ({}).".format(nome, saida, formatar_duracao(duracao)))
    return saida


def executar_lista(db, nome, args, opcoes):
    lista = db["lists"][nome]
    etapas = lista["steps"]
    if not etapas:
        alerta("A lista '{}' está vazia.".format(nome))
        dica("Adicione etapas com: lintux add list {} <comando>".format(nome))
        return 0

    inexistentes = [e for e in etapas if e not in db["commands"]]
    if inexistentes:
        raise ErroLintux("a lista '{}' referencia comando(s) inexistente(s): {}.".format(
            nome, ", ".join(inexistentes)),
            dica="Corrija com 'lintux edit {0}' ou 'lintux rm list {0} <etapa>'.".format(nome))

    usa_parametros = any(PARAM_RE.search(db["commands"][e]["cmd"]) for e in etapas)
    if args and not usa_parametros:
        alerta("Os argumentos informados foram ignorados: nenhuma etapa desta lista usa parâmetros {{1}} ou {{@}}.",
               sys.stderr)
    codigos = [resolver_parametros(db["commands"][e]["cmd"], args, anexar=False) for e in etapas]
    total = len(etapas)

    if opcoes["simular"]:
        titulo("Simulação — lista '{}' ({} etapas) NÃO será executada:".format(nome, total))
        for i, (etapa, codigo) in enumerate(zip(etapas, codigos), 1):
            print("  {}[{}/{}] {}{}".format(OUT.ciano, i, total, etapa, OUT.reset))
            imprimir_bloco(codigo, 6)
        return 0

    perigosos = [("etapa {} ({})".format(i, e), riscos(c))
                 for i, (e, c) in enumerate(zip(etapas, codigos), 1) if riscos(c)]
    if perigosos and not opcoes["sim"] and not confirmar_riscos(perigosos):
        alerta("Execução cancelada.", sys.stderr)
        return 1

    inicio = time.time()
    falhas = []
    for i, (etapa, codigo) in enumerate(zip(etapas, codigos), 1):
        if not opcoes["silencioso"]:
            print("\n{}{}[{}/{}] Executando: {}...{}".format(
                ERR.ciano, ERR.negrito, i, total, etapa, ERR.reset), file=sys.stderr)
            imprimir_bloco(codigo, 6, ERR.dim, sys.stderr)

        saida, duracao = executar_shell(codigo)

        if saida == 0:
            if not opcoes["silencioso"]:
                sucesso("Etapa {}/{} concluída ({}).".format(i, total, formatar_duracao(duracao)), sys.stderr)
            continue

        if saida == 130:  # Ctrl+C sempre interrompe a lista inteira, mesmo com -k
            alerta("Lista '{}' interrompida pelo usuário na etapa {}/{} ('{}').".format(nome, i, total, etapa),
                   sys.stderr)
            registrar_historico(nome, "lista", saida, time.time() - inicio)
            return saida

        erro("falha na etapa {}/{} ('{}') — código de saída {}.".format(i, total, etapa, saida))
        falhas.append((i, etapa, saida))
        if not opcoes["continuar"]:
            pendentes = ["{}. {}".format(j, n) for j, n in enumerate(etapas[i:], i + 1)]
            if pendentes:
                alerta("Etapas não executadas: " + ", ".join(pendentes), sys.stderr)
                dica("para continuar mesmo após falhas, use: lintux -k {}".format(nome), sys.stderr)
            registrar_historico(nome, "lista", saida, time.time() - inicio)
            return saida

    duracao_total = time.time() - inicio
    if falhas:
        descricao = ", ".join("{} ('{}', código {})".format(i, e, c) for i, e, c in falhas)
        alerta("Lista '{}' concluída com {} falha(s) em {} etapa(s): {}. Duração: {}.".format(
            nome, len(falhas), total, descricao, formatar_duracao(duracao_total)), sys.stderr)
        registrar_historico(nome, "lista", falhas[0][2], duracao_total)
        return falhas[0][2]

    print(file=sys.stderr)
    sucesso("Lista '{}' concluída: {}/{} etapas em {}.".format(
        nome, total, total, formatar_duracao(duracao_total)), sys.stderr)
    registrar_historico(nome, "lista", 0, duracao_total)
    return 0


# =============================================================================
# 5. SUBCOMANDOS
# =============================================================================

def _criar_comando(db, nome, codigo):
    momento = agora()
    db["commands"][nome] = {"cmd": codigo, "desc": "", "created": momento, "updated": momento}


def cmd_add(args):
    """lintux add <nome> '<comando>' | add list ... | add backup ..."""
    if not args:
        raise ErroLintux("uso incorreto de 'add'.",
                         dica="lintux add <nome> '<comando>'   |   lintux add list <lista> [...]   |   "
                              "lintux add backup <arquivo>")
    if args[0] == "list":
        return cmd_add_list(args[1:])
    if args[0] == "backup":
        return cmd_restaurar_backup(args[1:])

    db = carregar_db()
    nome = args[0]
    codigo = " ".join(args[1:]).strip()
    validar_nome(db, nome)
    if not codigo:
        raise ErroLintux("informe o comando real a ser salvo.",
                         dica="lintux add {} 'comando && outro comando'".format(nome))
    _criar_comando(db, nome, codigo)
    salvar_db(db)
    sucesso("Comando '{}' salvo.".format(nome))
    imprimir_bloco(codigo, 2, OUT.ciano)
    avisos_ao_salvar(codigo, varios_argumentos=len(args) > 2)
    print("{}  Execute com: lintux {}{}".format(OUT.dim, nome, OUT.reset))
    return 0


def cmd_add_list(args):
    """lintux add list <lista> [<comando> ['<código>']]"""
    if not args:
        raise ErroLintux("informe o nome da lista.", dica="lintux add list <lista>")
    db = carregar_db()
    lista = args[0]
    criada = False
    if lista not in db["lists"]:
        validar_nome(db, lista)
        momento = agora()
        db["lists"][lista] = {"steps": [], "desc": "", "created": momento, "updated": momento}
        criada = True

    if len(args) == 1:
        if not criada:
            raise ErroLintux("a lista '{}' já existe.".format(lista),
                             dica="Adicione etapas com: lintux add list {} <comando>".format(lista))
        salvar_db(db)
        sucesso("Lista '{}' criada (vazia).".format(lista))
        dica("adicione etapas com: lintux add list {} <comando>".format(lista))
        return 0

    nome_cmd = args[1]
    codigo = " ".join(args[2:]).strip()
    novo_comando = False
    if codigo:
        # Formato 2: cria o comando e o vincula à lista
        if nome_cmd in db["commands"]:
            if db["commands"][nome_cmd]["cmd"] != codigo:
                raise ErroLintux("já existe um comando '{}' com outro conteúdo.".format(nome_cmd),
                                 dica="Altere-o com 'lintux edit {}' ou escolha outro nome.".format(nome_cmd))
        else:
            validar_nome(db, nome_cmd)
            _criar_comando(db, nome_cmd, codigo)
            novo_comando = True
    elif nome_cmd not in db["commands"]:
        # Formato 1: o comando precisa existir
        if nome_cmd in db["lists"]:
            raise ErroLintux("'{}' é uma lista; listas não podem conter outras listas.".format(nome_cmd))
        parecidos = sugestoes(db, nome_cmd)
        raise ErroLintux("o comando '{}' não existe.".format(nome_cmd),
                         dica=("Você quis dizer: {}? ".format(", ".join(parecidos)) if parecidos else "") +
                         "Para criar e vincular de uma vez: lintux add list {} {} '<comando>'".format(lista, nome_cmd))

    etapas = db["lists"][lista]["steps"]
    repetido = nome_cmd in etapas
    etapas.append(nome_cmd)
    db["lists"][lista]["updated"] = agora()
    salvar_db(db)

    if criada:
        sucesso("Lista '{}' criada.".format(lista))
    if novo_comando:
        sucesso("Comando '{}' salvo.".format(nome_cmd))
        avisos_ao_salvar(codigo, varios_argumentos=len(args) > 3)
    sucesso("'{}' adicionado à lista '{}' como etapa {}.".format(nome_cmd, lista, len(etapas)))
    if repetido:
        alerta("'{}' já fazia parte desta lista e agora aparece mais de uma vez.".format(nome_cmd))
    return 0


def abrir_editor(conteudo, sufixo):
    """Abre o editor do usuário ($VISUAL, $EDITOR, nano, vim ou vi) e devolve o texto final."""
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        for candidato in ("nano", "vim", "vi"):
            if shutil.which(candidato):
                editor = candidato
                break
    if not editor:
        raise ErroLintux("nenhum editor de texto foi encontrado.",
                         dica="Defina a variável EDITOR (ex.: export EDITOR=nano) ou informe o novo "
                              "comando diretamente entre aspas.")
    descritor, caminho = tempfile.mkstemp(prefix="lintux-", suffix=sufixo)
    try:
        with os.fdopen(descritor, "w", encoding="utf-8") as f:
            f.write(conteudo)
        retorno = subprocess.call(shlex.split(editor) + [caminho])
        if retorno != 0:
            raise ErroLintux("o editor terminou com código {}; nada foi alterado.".format(retorno))
        with open(caminho, encoding="utf-8") as f:
            return f.read()
    finally:
        try:
            os.unlink(caminho)
        except OSError:
            pass


def cmd_edit(args):
    """lintux edit <comando> ['<novo código>']  |  lintux edit <lista>"""
    if args and args[0] == "list" and len(args) > 1:
        args = args[1:]
    if not args:
        raise ErroLintux("informe o nome a editar.", dica="lintux edit <nome> '<novo comando>'")
    db = carregar_db()
    nome = args[0]
    novo = " ".join(args[1:]).strip()

    if nome in db["commands"]:
        antigo = db["commands"][nome]["cmd"]
        if not novo:
            novo = abrir_editor(antigo + "\n", ".sh").strip()
            if not novo:
                raise ErroLintux("o comando ficou vazio; nada foi alterado.")
        if novo == antigo:
            alerta("Nenhuma alteração foi feita em '{}'.".format(nome))
            return 0
        db["commands"][nome]["cmd"] = novo
        db["commands"][nome]["updated"] = agora()
        salvar_db(db)
        sucesso("Comando '{}' atualizado.".format(nome))
        print("  {}Antes:{}".format(OUT.dim, OUT.reset))
        imprimir_bloco(antigo, 4, OUT.vermelho)
        print("  {}Depois:{}".format(OUT.dim, OUT.reset))
        imprimir_bloco(novo, 4, OUT.verde)
        avisos_ao_salvar(novo, varios_argumentos=len(args) > 2)
        usadas = listas_que_usam(db, nome)
        if usadas:
            print("{}  A alteração vale também para as listas: {}{}".format(OUT.dim, ", ".join(usadas), OUT.reset))
        return 0

    if nome in db["lists"]:
        if novo:
            raise ErroLintux("listas são editadas sem texto adicional.",
                             dica="'lintux edit {}' abre o editor com uma etapa por linha.".format(nome))
        return editar_lista_no_editor(db, nome)

    nao_encontrado(db, nome)


def editar_lista_no_editor(db, nome):
    etapas = db["lists"][nome]["steps"]
    disponiveis = ", ".join(sorted(db["commands"], key=str.lower)) or "(nenhum)"
    cabecalho = [
        "# Lista: {}".format(nome),
        "# Uma etapa por linha (nome de um comando salvo), na ordem de execução.",
        "# Linhas vazias ou iniciadas por # são ignoradas. Salve e feche para aplicar.",
        "# Comandos disponíveis:",
    ] + ["#   " + l for l in textwrap.wrap(disponiveis, 74)]
    texto = abrir_editor("\n".join(cabecalho + [""] + etapas) + "\n", ".txt")
    novas = [l.strip() for l in texto.splitlines() if l.strip() and not l.strip().startswith("#")]
    invalidas = [e for e in novas if e not in db["commands"]]
    if invalidas:
        raise ErroLintux("etapa(s) com comando inexistente: {}. Nada foi alterado.".format(", ".join(invalidas)))
    if novas == etapas:
        alerta("Nenhuma alteração foi feita na lista '{}'.".format(nome))
        return 0
    db["lists"][nome]["steps"] = novas
    db["lists"][nome]["updated"] = agora()
    salvar_db(db)
    sucesso("Lista '{}' atualizada ({} etapa(s)).".format(nome, len(novas)))
    for i, e in enumerate(novas, 1):
        print("    {}. {}".format(i, e))
    return 0


def cmd_rm(args):
    """lintux rm <comando> [<comando>...] [-y]  |  lintux rm list <lista> [etapa]"""
    sim = any(a in ("-y", "--yes") for a in args)
    args = [a for a in args if a not in ("-y", "--yes")]
    if not args:
        raise ErroLintux("informe o que deseja remover.",
                         dica="lintux rm <comando>   |   lintux rm list <lista> [etapa]")
    if args[0] == "list":
        return cmd_rm_list(args[1:])

    db = carregar_db()
    alterou, falhou = False, False
    for nome in args:
        if nome in db["commands"]:
            usadas = listas_que_usam(db, nome)
            if usadas:
                alerta("'{}' faz parte da(s) lista(s): {}.".format(nome, ", ".join(usadas)))
                if not sim and not confirmar("Remover o comando e retirá-lo dessas listas?"):
                    alerta("Remoção de '{}' cancelada.".format(nome))
                    falhou = True
                    continue
                for lista in usadas:
                    db["lists"][lista]["steps"] = [e for e in db["lists"][lista]["steps"] if e != nome]
                    db["lists"][lista]["updated"] = agora()
            del db["commands"][nome]
            alterou = True
            sucesso("Comando '{}' removido.".format(nome) +
                    (" Também foi retirado de: {}.".format(", ".join(usadas)) if usadas else ""))
        elif nome in db["lists"]:
            erro("'{}' é uma lista.".format(nome))
            dica("para removê-la use: lintux rm list {}".format(nome), sys.stderr)
            falhou = True
        else:
            parecidos = sugestoes(db, nome)
            erro("comando '{}' não encontrado.".format(nome))
            if parecidos:
                dica("você quis dizer: {}?".format(", ".join(parecidos)), sys.stderr)
            falhou = True
    if alterou:
        salvar_db(db)
    return 1 if falhou else 0


def cmd_rm_list(args):
    if not args:
        raise ErroLintux("informe o nome da lista.", dica="lintux rm list <lista> [etapa]")
    db = carregar_db()
    lista = args[0]
    if lista not in db["lists"]:
        if lista in db["commands"]:
            raise ErroLintux("'{}' é um comando, não uma lista.".format(lista),
                             dica="Para removê-lo use: lintux rm {}".format(lista))
        nao_encontrado(db, lista, "lista")

    if len(args) == 1:
        del db["lists"][lista]
        salvar_db(db)
        sucesso("Lista '{}' removida. Os comandos individuais continuam salvos.".format(lista))
        return 0

    alvo = args[1]
    etapas = db["lists"][lista]["steps"]
    if alvo.isdigit():
        indice = int(alvo) - 1
        if not 0 <= indice < len(etapas):
            raise ErroLintux("a lista '{}' tem {} etapa(s); a posição {} não existe.".format(lista, len(etapas), alvo))
    elif alvo in etapas:
        indice = etapas.index(alvo)
    else:
        raise ErroLintux("'{}' não faz parte da lista '{}'.".format(alvo, lista),
                         dica="Veja as etapas com: lintux show {}".format(lista))
    retirado = etapas.pop(indice)
    db["lists"][lista]["updated"] = agora()
    salvar_db(db)
    sucesso("Etapa {} ('{}') retirada da lista '{}'. O comando continua salvo.".format(indice + 1, retirado, lista))
    return 0


def cmd_mv(args):
    """lintux mv <lista> <posição atual> <nova posição>"""
    if len(args) != 3 or not args[1].isdigit() or not args[2].isdigit():
        raise ErroLintux("uso incorreto de 'mv'.", dica="lintux mv <lista> <posição atual> <nova posição>  (ex.: lintux mv manutencao 3 1)")
    db = carregar_db()
    lista = args[0]
    if lista not in db["lists"]:
        nao_encontrado(db, lista, "lista")
    etapas = db["lists"][lista]["steps"]
    origem, destino = int(args[1]), int(args[2])
    if not (1 <= origem <= len(etapas) and 1 <= destino <= len(etapas)):
        raise ErroLintux("posições válidas para '{}': de 1 a {}.".format(lista, len(etapas)))
    etapas.insert(destino - 1, etapas.pop(origem - 1))
    db["lists"][lista]["updated"] = agora()
    salvar_db(db)
    sucesso("Etapa movida da posição {} para a {}. Nova ordem:".format(origem, destino))
    for i, e in enumerate(etapas, 1):
        print("    {}. {}".format(i, e))
    return 0


def cmd_rename(args):
    """lintux rename <nome atual> <novo nome>"""
    if len(args) != 2:
        raise ErroLintux("uso incorreto de 'rename'.", dica="lintux rename <nome atual> <novo nome>")
    db = carregar_db()
    antigo, novo = args
    if antigo in db["commands"]:
        validar_nome(db, novo)
        db["commands"][novo] = db["commands"].pop(antigo)
        db["commands"][novo]["updated"] = agora()
        usadas = listas_que_usam(db, antigo)
        for lista in usadas:
            db["lists"][lista]["steps"] = [novo if e == antigo else e for e in db["lists"][lista]["steps"]]
        salvar_db(db)
        sucesso("Comando '{}' renomeado para '{}'.".format(antigo, novo) +
                (" Listas atualizadas: {}.".format(", ".join(usadas)) if usadas else ""))
        return 0
    if antigo in db["lists"]:
        validar_nome(db, novo)
        db["lists"][novo] = db["lists"].pop(antigo)
        db["lists"][novo]["updated"] = agora()
        salvar_db(db)
        sucesso("Lista '{}' renomeada para '{}'.".format(antigo, novo))
        return 0
    nao_encontrado(db, antigo)


def cmd_desc(args):
    """lintux desc <nome> '<descrição>'  (descrição vazia remove)"""
    if not args:
        raise ErroLintux("informe o nome.", dica="lintux desc <nome> 'texto da descrição'")
    db = carregar_db()
    nome, texto = args[0], " ".join(args[1:]).strip()
    alvo = db["commands"].get(nome) or db["lists"].get(nome)
    if alvo is None:
        nao_encontrado(db, nome)
    alvo["desc"] = texto
    alvo["updated"] = agora()
    salvar_db(db)
    sucesso("Descrição de '{}' {}.".format(nome, "atualizada" if texto else "removida"))
    return 0


def cmd_show(args):
    """lintux show <nome> — mostra o conteúdo sem executar."""
    if args and args[0] in ("list", "cmd") and len(args) > 1:
        args = args[1:]
    if not args:
        raise ErroLintux("informe o nome.", dica="lintux show <nome>")
    db = carregar_db()
    nome = args[0]

    if nome in db["commands"]:
        item = db["commands"][nome]
        titulo("Comando: {}".format(nome))
        print("  {}Código:{}".format(OUT.dim, OUT.reset))
        imprimir_bloco(item["cmd"], 4, OUT.ciano)
        if item.get("desc"):
            print("  {}Descrição:{} {}".format(OUT.dim, OUT.reset, item["desc"]))
        parametros = descrever_parametros(item["cmd"])
        if parametros:
            print("  {}Parâmetros:{} {}".format(OUT.dim, OUT.reset, "; ".join(parametros)))
        usadas = listas_que_usam(db, nome)
        print("  {}Listas:{} {}".format(OUT.dim, OUT.reset, ", ".join(usadas) if usadas else "nenhuma"))
        print("  {}Criado em:{} {}   {}Alterado em:{} {}".format(
            OUT.dim, OUT.reset, item["created"], OUT.dim, OUT.reset, item["updated"]))
        for r in riscos(item["cmd"]):
            alerta("Atenção: envolve {} (pedirá confirmação ao executar).".format(r))
        return 0

    if nome in db["lists"]:
        lista = db["lists"][nome]
        etapas = lista["steps"]
        titulo("Lista: {} ({} etapa(s))".format(nome, len(etapas)))
        if lista.get("desc"):
            print("  {}Descrição:{} {}".format(OUT.dim, OUT.reset, lista["desc"]))
        print("  {}Criada em:{} {}   {}Alterada em:{} {}".format(
            OUT.dim, OUT.reset, lista["created"], OUT.dim, OUT.reset, lista["updated"]))
        if not etapas:
            alerta("A lista está vazia.")
        for i, etapa in enumerate(etapas, 1):
            if etapa in db["commands"]:
                print("\n  {}{}[{}/{}] {}{}".format(OUT.ciano, OUT.negrito, i, len(etapas), etapa, OUT.reset))
                imprimir_bloco(db["commands"][etapa]["cmd"], 6)
                for r in riscos(db["commands"][etapa]["cmd"]):
                    alerta("      Atenção: envolve {}.".format(r))
            else:
                print("\n  {}[{}/{}] {} — comando não encontrado{}".format(
                    OUT.vermelho, i, len(etapas), etapa, OUT.reset))
        return 0

    nao_encontrado(db, nome)


def listar_comandos(db):
    comandos = db["commands"]
    if not comandos:
        alerta("Nenhum comando salvo ainda.")
        dica("crie o primeiro com: lintux add <nome> '<comando>'")
        return
    titulo("Comandos salvos ({})".format(len(comandos)))
    coluna = min(max(len(n) for n in comandos), 22)
    largura = largura_terminal() - coluna - 6
    recuo = " " * (coluna + 4)
    for nome in sorted(comandos, key=str.lower):
        item = comandos[nome]
        linhas = quebrar(item["cmd"], largura)
        if len(nome) > coluna:
            print("  {}{}{}{}".format(OUT.ciano, OUT.negrito, nome, OUT.reset))
            restantes = linhas
        else:
            print("  {}{}{}{}  {}".format(OUT.ciano, OUT.negrito, nome.ljust(coluna), OUT.reset, linhas[0]))
            restantes = linhas[1:]
        for linha in restantes:
            print(recuo + linha)
        if item.get("desc"):
            for linha in quebrar("{} {}".format(S_DESC, item["desc"]), largura):
                print("{}{}{}{}".format(recuo, OUT.dim, linha, OUT.reset))


def listar_listas(db):
    listas = db["lists"]
    if not listas:
        alerta("Nenhuma lista criada ainda.")
        dica("crie a primeira com: lintux add list <lista>")
        return
    titulo("Listas de execução ({})".format(len(listas)))
    for nome in sorted(listas, key=str.lower):
        lista = listas[nome]
        etapas = lista["steps"]
        print("\n  {}{}{}{} {}({} etapa(s)){}".format(
            OUT.ciano, OUT.negrito, nome, OUT.reset, OUT.dim, len(etapas), OUT.reset))
        if lista.get("desc"):
            print("    {}{} {}{}".format(OUT.dim, S_DESC, lista["desc"], OUT.reset))
        if not etapas:
            print("    {}(vazia){}".format(OUT.dim, OUT.reset))
        for i, etapa in enumerate(etapas, 1):
            if etapa in db["commands"]:
                print("    {}{}.{} {}".format(OUT.ciano, i, OUT.reset, etapa))
                imprimir_bloco(db["commands"][etapa]["cmd"], 7, OUT.dim)
            else:
                print("    {}{}. {} — comando não encontrado{}".format(OUT.vermelho, i, etapa, OUT.reset))


def cmd_list(args):
    """lintux list [cmd | lists]"""
    escolha = args[0].lower() if args else "tudo"
    db = carregar_db()
    if escolha in ("cmd", "cmds", "comandos", "commands"):
        listar_comandos(db)
    elif escolha in ("lists", "list", "listas"):
        listar_listas(db)
    elif escolha in ("tudo", "all"):
        listar_comandos(db)
        listar_listas(db)
    else:
        raise ErroLintux("opção desconhecida para 'list': {}".format(args[0]),
                         dica="lintux list cmd   |   lintux list lists   |   lintux list")
    print()
    return 0


def cmd_search(args):
    """lintux search <termo> — procura em nomes, códigos e descrições."""
    if not args:
        raise ErroLintux("informe o termo de busca.", dica="lintux search <termo>")
    termo = " ".join(args).lower()
    db = carregar_db()
    comandos = [n for n, c in sorted(db["commands"].items(), key=lambda x: x[0].lower())
                if termo in n.lower() or termo in c["cmd"].lower() or termo in c.get("desc", "").lower()]
    listas = [n for n, l in sorted(db["lists"].items(), key=lambda x: x[0].lower())
              if termo in n.lower() or termo in l.get("desc", "").lower()
              or any(termo in e.lower() for e in l["steps"])]
    if not comandos and not listas:
        alerta("Nada encontrado para '{}'.".format(termo))
        return 1
    if comandos:
        titulo("Comandos ({})".format(len(comandos)))
        for n in comandos:
            print("  {}{}{}".format(OUT.ciano + OUT.negrito, n, OUT.reset))
            imprimir_bloco(db["commands"][n]["cmd"], 4)
    if listas:
        titulo("Listas ({})".format(len(listas)))
        for n in listas:
            print("  {}{}{} {}{}{}".format(OUT.ciano + OUT.negrito, n, OUT.reset, OUT.dim,
                                           " " + S_SETA + " ".join([""] + db["lists"][n]["steps"]), OUT.reset))
    print()
    return 0


def cmd_history(args):
    """lintux history [quantidade] | lintux history clear [-y]"""
    arquivo = arquivo_historico()
    args = [a for a in args if a not in ("-y", "--yes")]
    if args and args[0] in ("clear", "limpar"):
        if arquivo.exists():
            arquivo.unlink()
        sucesso("Histórico apagado.")
        return 0
    quantidade = 20
    if args:
        if not args[0].isdigit():
            raise ErroLintux("uso incorreto de 'history'.", dica="lintux history [quantidade]   |   lintux history clear")
        quantidade = int(args[0])
    if not arquivo.exists():
        alerta("O histórico está vazio.")
        return 0
    registros = []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        try:
            registros.append(json.loads(linha))
        except ValueError:
            continue
    registros = registros[-quantidade:] if quantidade else registros
    titulo("Últimas {} execução(ões)".format(len(registros)))
    for r in registros:
        ok = r.get("codigo") == 0
        simbolo = "{}{}{}".format(OUT.verde if ok else OUT.vermelho, S_OK if ok else S_ERRO, OUT.reset)
        print("  {}  {}  {}{:<24}{} {:<8} {:>12}  código {}".format(
            r.get("data", "?"), simbolo, OUT.ciano, r.get("nome", "?"), OUT.reset,
            r.get("tipo", "?"), formatar_duracao(float(r.get("duracao", 0))), r.get("codigo", "?")))
    print()
    return 0


def pasta_downloads():
    """Downloads via xdg-user-dir; depois ~/Downloads, ~/Transferências; por fim a Home."""
    home = Path.home()
    try:
        r = subprocess.run(["xdg-user-dir", "DOWNLOAD"], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, universal_newlines=True, timeout=5)
        caminho = r.stdout.strip()
        # xdg-user-dir devolve a própria Home quando a pasta não está configurada
        if r.returncode == 0 and caminho and Path(caminho).is_dir() and Path(caminho) != home:
            return Path(caminho)
    except (OSError, subprocess.SubprocessError):
        pass
    for nome in ("Downloads", "Transferências", "Transferencias", "Descargas"):
        if (home / nome).is_dir():
            return home / nome
    return home


def cmd_new(args):
    """lintux new backup [pasta de destino]"""
    if not args or args[0] != "backup":
        raise ErroLintux("uso incorreto de 'new'.", dica="lintux new backup [pasta de destino]")
    db = carregar_db()
    if len(args) > 1:
        destino = Path(" ".join(args[1:])).expanduser()
        if not destino.is_dir():
            raise ErroLintux("a pasta '{}' não existe.".format(destino))
    else:
        destino = pasta_downloads()
    base = "lintux_backup_{}".format(datetime.now().strftime("%Y-%m-%d_%H-%M"))
    arquivo = destino / (base + ".json")
    contador = 2
    while arquivo.exists():  # evita sobrescrever um backup feito no mesmo minuto
        arquivo = destino / "{}_{}.json".format(base, contador)
        contador += 1
    conteudo = dict(db)
    conteudo["lintux_backup"] = {"versao_lintux": VERSAO, "criado_em": agora()}
    try:
        with arquivo.open("w", encoding="utf-8") as f:
            json.dump(conteudo, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.chmod(str(arquivo), 0o600)
    except OSError as e:
        raise ErroLintux("não foi possível gravar o backup em {}: {}".format(destino, e))
    sucesso("Backup criado com sucesso ({} comando(s), {} lista(s)).".format(
        len(db["commands"]), len(db["lists"])))
    print("\n  {}Arquivo salvo em:{}".format(OUT.negrito, OUT.reset))
    print("  {}{}{}{}\n".format(OUT.verde, OUT.negrito, arquivo.resolve(), OUT.reset))
    print("{}  Para restaurar: lintux add backup '{}'{}".format(OUT.dim, arquivo.resolve(), OUT.reset))
    return 0


def cmd_restaurar_backup(args):
    """lintux add backup <arquivo> [--overwrite]"""
    sobrescrever = any(a in ("--overwrite", "-o", "--substituir") for a in args)
    resto = [a for a in args if a not in ("--overwrite", "-o", "--substituir")]
    if not resto:
        raise ErroLintux("informe o arquivo de backup.", dica="lintux add backup <arquivo.json> [--overwrite]")
    caminho = Path(" ".join(resto)).expanduser()
    if not caminho.exists():
        raise ErroLintux("o arquivo '{}' não existe.".format(caminho))
    if not caminho.is_file():
        raise ErroLintux("'{}' não é um arquivo.".format(caminho))
    try:
        with caminho.open(encoding="utf-8") as f:
            dados = json.load(f)
    except UnicodeDecodeError:
        raise ErroLintux("'{}' não é um arquivo de texto JSON.".format(caminho))
    except ValueError as e:
        raise ErroLintux("'{}' não é um JSON válido ({}).".format(caminho, e))
    except OSError as e:
        raise ErroLintux("não foi possível ler '{}': {}".format(caminho, e))
    try:
        entrada = normalizar(dados)
    except ValueError as e:
        raise ErroLintux("'{}' não está na estrutura do Lintux: {}.".format(caminho, e))

    db = carregar_db()

    # Cópia de segurança automática do estado atual, antes de mesclar
    pasta_seg = pasta_lintux() / "backups"
    pasta_seg.mkdir(parents=True, exist_ok=True, mode=0o700)
    marca = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    seguranca = pasta_seg / "antes_da_restauracao_{}.json".format(marca)
    contador = 2
    while seguranca.exists():
        seguranca = pasta_seg / "antes_da_restauracao_{}_{}.json".format(marca, contador)
        contador += 1
    with seguranca.open("w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    novos_c = iguais_c = subst_c = 0
    novas_l = iguais_l = subst_l = 0
    mantidos, ignorados, etapas_perdidas = [], [], []

    for nome in sorted(entrada["commands"]):
        item = entrada["commands"][nome]
        if not nome_valido(nome):
            ignorados.append("{} (nome inválido ou reservado)".format(nome))
        elif nome in db["lists"]:
            ignorados.append("{} (já existe uma lista com esse nome)".format(nome))
        elif nome not in db["commands"]:
            db["commands"][nome] = item
            novos_c += 1
        elif db["commands"][nome]["cmd"] == item["cmd"]:
            iguais_c += 1
            if not db["commands"][nome].get("desc") and item.get("desc"):
                db["commands"][nome]["desc"] = item["desc"]
        elif sobrescrever:
            item["updated"] = agora()
            db["commands"][nome] = item
            subst_c += 1
        else:
            mantidos.append("comando '{}'".format(nome))

    for nome in sorted(entrada["lists"]):
        item = entrada["lists"][nome]
        if not nome_valido(nome):
            ignorados.append("{} (nome inválido ou reservado)".format(nome))
            continue
        if nome in db["commands"]:
            ignorados.append("{} (já existe um comando com esse nome)".format(nome))
            continue
        validas = [e for e in item["steps"] if e in db["commands"]]
        perdidas = [e for e in item["steps"] if e not in db["commands"]]
        if perdidas:
            etapas_perdidas.append("{}: {}".format(nome, ", ".join(perdidas)))
        item["steps"] = validas
        if nome not in db["lists"]:
            db["lists"][nome] = item
            novas_l += 1
        elif db["lists"][nome]["steps"] == validas:
            iguais_l += 1
        elif sobrescrever:
            item["updated"] = agora()
            db["lists"][nome] = item
            subst_l += 1
        else:
            mantidos.append("lista '{}'".format(nome))

    salvar_db(db)
    sucesso("Backup restaurado e mesclado com sucesso: {}".format(caminho.resolve()))
    print("  Comandos: {} novo(s), {} idêntico(s), {} substituído(s)".format(novos_c, iguais_c, subst_c))
    print("  Listas:   {} nova(s), {} idêntica(s), {} substituída(s)".format(novas_l, iguais_l, subst_l))
    if mantidos:
        alerta("Conflitos mantidos com a versão atual ({}): {}.".format(len(mantidos), ", ".join(mantidos)))
        dica("para substituir pelos dados do backup, repita com --overwrite")
    for texto in ignorados:
        alerta("Ignorado: " + texto)
    for texto in etapas_perdidas:
        alerta("Etapas descartadas por falta do comando correspondente — " + texto)
    print("{}  Cópia do estado anterior: {}{}".format(OUT.dim, seguranca, OUT.reset))
    return 0


def completar(args):
    """Uso interno do autocompletar do bash: imprime nomes, um por linha."""
    tipo = args[0] if args else "all"
    try:
        db = carregar_db(silencioso=True)
    except ErroLintux:
        return 0
    nomes = []
    if tipo in ("all", "names", "cmds"):
        nomes += list(db["commands"])
    if tipo in ("all", "names", "lists"):
        nomes += list(db["lists"])
    if tipo == "all":
        nomes += sorted(RESERVADAS - {"backup"})
    print("\n".join(nomes))
    return 0


PINGUIM = r"""
       .--.
      |o_o |
      |:_/ |
     //   \ \
    (|     | )
   /'\_   _/`\
   \___)=(___/
"""

AJUDA = """
# Lintux {versao} — gerenciador de comandos e listas de execução no terminal

# USO
  lintux <nome> [argumentos...]               Executa um comando ou uma lista salvos
  lintux [opções] <nome> [argumentos...]      Executa com opções (veja abaixo)
  lintux run <nome> [argumentos...]           Forma explícita de execução

# COMANDOS INDIVIDUAIS
  lintux add <nome> '<comando>'               Salva um novo comando
  lintux edit <nome> '<novo comando>'         Substitui o código de um comando
  lintux edit <nome>                          Edita o código no editor de texto ($EDITOR)
  lintux rm <nome> [<nome>...] [-y]           Remove comando(s), retirando-o(s) das listas
  lintux list cmd                             Lista os comandos salvos

# LISTAS DE EXECUÇÃO
  lintux add list <lista>                     Cria uma lista vazia
  lintux add list <lista> <comando>           Adiciona um comando já salvo à lista
  lintux add list <lista> <novo> '<comando>'  Salva um novo comando e já o adiciona à lista
  lintux edit <lista>                         Reorganiza as etapas no editor de texto
  lintux mv <lista> <de> <para>               Move uma etapa de posição
  lintux rm list <lista>                      Remove a lista (os comandos continuam salvos)
  lintux rm list <lista> <etapa>              Retira uma etapa (pelo nome ou pelo número)
  lintux list lists                           Mostra as listas e as etapas de cada uma

# INSPEÇÃO E ORGANIZAÇÃO
  lintux show <nome>                          Mostra o código sem executar (segurança)
  lintux list                                 Mostra comandos e listas
  lintux search <termo>                       Procura em nomes, códigos e descrições
  lintux rename <nome atual> <novo nome>      Renomeia, atualizando as listas
  lintux desc <nome> '<descrição>'            Define uma descrição ('' remove)
  lintux history [quantidade]                 Mostra o histórico de execuções
  lintux history clear                        Apaga o histórico

# BACKUP E RESTAURAÇÃO
  lintux new backup [pasta]                   Cria backup (padrão: sua pasta de Downloads)
  lintux add backup <arquivo> [--overwrite]   Restaura e mescla um backup; com --overwrite,
                                              os conflitos ficam com a versão do backup

# OPÇÕES DE EXECUÇÃO (sempre antes do nome)
  -y, --yes         Não pede confirmação para operações potencialmente destrutivas
  -k, --keep-going  Em listas, continua as próximas etapas mesmo se uma falhar
  -n, --dry-run     Simulação: mostra o que seria executado, sem executar
  -q, --quiet       Oculta cabeçalhos e mensagens de status do Lintux

# PARÂMETROS NOS COMANDOS
  {{{{1}}}}, {{{{2}}}}...       Argumento na posição indicada (obrigatório)
  {{{{1:padrão}}}}       Argumento com valor padrão, caso não seja informado
  {{{{@}}}}              Todos os argumentos
  Sem parâmetros no código, os argumentos extras são acrescentados ao final do comando.
  Os argumentos são sempre protegidos (escapados) antes de irem para o shell.

# EXEMPLOS
  lintux add atualizar 'sudo apt update && sudo apt upgrade -y'        (Debian/Ubuntu/Mint)
  lintux add atualizar 'sudo dnf upgrade --refresh -y'                 (Fedora/RHEL/Alma)
  lintux add porta 'ss -tulpn | grep {{{{1}}}}'
  lintux porta 8080
  lintux add list manutencao
  lintux add list manutencao atualizar
  lintux add list manutencao limpar 'sudo apt autoremove -y && sudo apt clean'
  lintux -n manutencao
  lintux manutencao
  lintux new backup

# IMPORTANTE — USE ASPAS SIMPLES
  Ao cadastrar comandos com operadores especiais (&&  ||  |  >  <  ;  $  *  ~), envolva o
  comando em aspas simples '...'. Sem aspas, o seu shell interpreta esses operadores ANTES
  de o Lintux recebê-los. Exemplo do problema:
      lintux add x sudo apt update && sudo apt upgrade
  salva apenas "sudo apt update" e executa "sudo apt upgrade" imediatamente.
  Se o comando tiver aspas simples internas, use aspas duplas por fora: "echo 'olá'".

# ARQUIVOS
  ~/.lintux/database.json        Banco de dados (cópia anterior em database.json.bak)
  ~/.lintux/history.log          Histórico de execuções
  ~/.lintux/backups/             Cópias automáticas feitas antes de cada restauração
  A variável LINTUX_HOME permite usar outra pasta; NO_COLOR desativa as cores.
"""


def cmd_help(args=None):
    destaque_aspas = re.compile(r"('[^']*'|\"[^\"]*\")")
    for linha in AJUDA.format(versao=VERSAO).strip("\n").splitlines():
        if linha.startswith("# "):
            print("\n{}{}{}{}".format(OUT.ciano, OUT.negrito, linha[2:], OUT.reset))
        elif "lintux" in linha or "echo" in linha:
            print(destaque_aspas.sub(lambda m: OUT.amarelo + m.group(1) + OUT.reset, linha))
        else:
            print(linha)
    print()
    return 0


def cmd_version(args=None):
    print("Lintux {} (Python {}, shell: {})".format(
        VERSAO, ".".join(str(v) for v in sys.version_info[:3]), interpretador()))
    return 0


def tela_inicial():
    db = carregar_db()
    print("{}{}{}".format(OUT.ciano, PINGUIM.rstrip("\n"), OUT.reset))
    print("\n  {}Lintux {}{} — {} comando(s) e {} lista(s) salvos\n".format(
        OUT.negrito, VERSAO, OUT.reset, len(db["commands"]), len(db["lists"])))
    print("  lintux add <nome> '<comando>'    Salvar um comando")
    print("  lintux <nome>                    Executar")
    print("  lintux list                      Ver tudo o que está salvo")
    print("  lintux help                      Guia completo\n")
    print("  {}Desenvolvido por {}{}{}".format(OUT.dim, OUT.reset + OUT.negrito, AUTOR, OUT.reset))
    print("  {}{}{}".format(OUT.dim, CONTATO, OUT.reset))
    print("  {}{}{}\n".format(OUT.ciano, REPOSITORIO, OUT.reset))
    return 0


SUBCOMANDOS = {
    "add": cmd_add,
    "edit": cmd_edit,
    "rm": cmd_rm,
    "list": cmd_list,
    "show": cmd_show,
    "mv": cmd_mv,
    "rename": cmd_rename,
    "desc": cmd_desc,
    "search": cmd_search,
    "history": cmd_history,
    "new": cmd_new,
    "run": executar_item,
    "help": cmd_help,
    "version": cmd_version,
}


# =============================================================================
# 6. PONTO DE ENTRADA
# =============================================================================

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if not argv:
            return tela_inicial()
        primeiro = argv[0]
        if primeiro in ("-h", "--help"):
            return cmd_help()
        if primeiro in ("--version", "-V"):
            return cmd_version()
        if primeiro == "__complete":
            return completar(argv[1:])
        if primeiro in SUBCOMANDOS:
            return SUBCOMANDOS[primeiro](argv[1:])
        return executar_item(argv)
    except ErroLintux as e:
        erro(e.mensagem)
        if e.dica:
            dica(e.dica, sys.stderr)
        return e.codigo
    except KeyboardInterrupt:
        print(file=sys.stderr)
        alerta("Operação cancelada.", sys.stderr)
        return 130
    except BrokenPipeError:
        # Ex.: "lintux list | head" — encerra em silêncio
        try:
            sys.stdout = open(os.devnull, "w")
        except OSError:
            pass
        return 0
    except OSError as e:
        erro("falha de sistema: {}".format(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
