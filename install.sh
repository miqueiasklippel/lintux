#!/usr/bin/env bash
# =============================================================================
# Instalador do Lintux
#
#   ./install.sh           Instala para todo o sistema (/usr/local/bin/lintux; usa sudo)
#   ./install.sh --user    Instala só para o seu usuário (~/.local/bin/lintux; sem sudo)
#   ./install.sh --help    Mostra esta ajuda
#
# Funciona em Debian, Ubuntu, Linux Mint e derivados, e em RHEL, Fedora,
# CentOS, AlmaLinux, Rocky Linux e derivados. Executar de novo atualiza a versão.
# =============================================================================
set -euo pipefail

VERDE=$'\033[32m'; VERMELHO=$'\033[31m'; AMARELO=$'\033[33m'; CIANO=$'\033[36m'; NEGRITO=$'\033[1m'; RESET=$'\033[0m'
if [[ ! -t 1 || -n "${NO_COLOR:-}" ]]; then VERDE=""; VERMELHO=""; AMARELO=""; CIANO=""; NEGRITO=""; RESET=""; fi

ok()     { echo "${VERDE}✔ $*${RESET}"; }
falha()  { echo "${VERMELHO}✖ Erro: $*${RESET}" >&2; exit 1; }
aviso()  { echo "${AMARELO}⚠ $*${RESET}"; }
passo()  { echo "${CIANO}${NEGRITO}» $*${RESET}"; }

ORIGEM="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODO="sistema"

case "${1:-}" in
    --user|-u) MODO="usuario" ;;
    --help|-h) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    "") ;;
    *) falha "opção desconhecida: $1 (use --user ou --help)" ;;
esac

echo "${CIANO}${NEGRITO}Instalador do Lintux${RESET}"

# --- 1. Arquivos necessários --------------------------------------------------
[[ -f "$ORIGEM/lintux.py" ]] || falha "lintux.py não foi encontrado em $ORIGEM"

# --- 2. Python 3.6+ -------------------------------------------------------------
passo "Verificando o Python 3..."
if ! command -v python3 >/dev/null 2>&1; then
    DISTRO=""
    [[ -r /etc/os-release ]] && DISTRO="$(. /etc/os-release; echo "${ID:-} ${ID_LIKE:-}")"
    if [[ "$DISTRO" =~ (debian|ubuntu) ]]; then
        falha "python3 não está instalado. Instale com: sudo apt install python3"
    elif [[ "$DISTRO" =~ (rhel|fedora|centos) ]]; then
        falha "python3 não está instalado. Instale com: sudo dnf install python3"
    else
        falha "python3 não está instalado. Instale-o pelo gerenciador de pacotes da sua distribuição."
    fi
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 6) else 1)' \
    || falha "é necessário Python 3.6 ou superior (encontrado: $(python3 --version 2>&1))"
ok "$(python3 --version 2>&1) encontrado"

# --- 3. Destinos ------------------------------------------------------------------
if [[ "$MODO" == "sistema" ]]; then
    PASTA_APP="/usr/local/lib/lintux"
    PASTA_BIN="/usr/local/bin"
    if [[ -d /usr/share/bash-completion/completions ]]; then
        PASTA_COMP="/usr/share/bash-completion/completions"
    else
        PASTA_COMP="/etc/bash_completion.d"
    fi
    if [[ $EUID -eq 0 ]]; then
        SUDO=""
    else
        command -v sudo >/dev/null 2>&1 || falha "sudo não encontrado. Rode como root ou use: ./install.sh --user"
        SUDO="sudo"
        passo "A instalação para o sistema precisa de permissão de administrador (sudo)."
    fi
else
    PASTA_APP="$HOME/.local/lib/lintux"
    PASTA_BIN="$HOME/.local/bin"
    PASTA_COMP="${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions"
    SUDO=""
fi

if [[ -e "$PASTA_BIN/lintux" ]]; then
    aviso "Instalação anterior encontrada em $PASTA_BIN/lintux — será atualizada (seus dados em ~/.lintux não são alterados)."
fi

# --- 4. Cópia, permissão de execução e link simbólico ---------------------------
passo "Instalando em $PASTA_APP ..."
chmod +x "$ORIGEM/lintux.py"
$SUDO install -d -m 755 "$PASTA_APP" "$PASTA_BIN"
$SUDO install -m 755 "$ORIGEM/lintux.py" "$PASTA_APP/lintux.py"
$SUDO ln -sfn "$PASTA_APP/lintux.py" "$PASTA_BIN/lintux"
ok "Executável disponível em $PASTA_BIN/lintux"

if [[ -f "$ORIGEM/lintux-completion.bash" ]]; then
    $SUDO install -d -m 755 "$PASTA_COMP"
    $SUDO install -m 644 "$ORIGEM/lintux-completion.bash" "$PASTA_COMP/lintux"
    ok "Autocompletar (tecla Tab) instalado em $PASTA_COMP/lintux"
else
    aviso "lintux-completion.bash não encontrado; o autocompletar não foi instalado."
fi

# Fedora/RHEL com SELinux: garante o contexto correto dos arquivos novos
if [[ "$MODO" == "sistema" ]] && command -v restorecon >/dev/null 2>&1; then
    $SUDO restorecon -R "$PASTA_APP" "$PASTA_BIN/lintux" 2>/dev/null || true
fi

# --- 5. PATH e verificação ------------------------------------------------------
if [[ "$MODO" == "usuario" && ":$PATH:" != *":$PASTA_BIN:"* ]]; then
    aviso "$PASTA_BIN não está no seu PATH. Adicione esta linha ao final do ~/.bashrc e abra um novo terminal:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

"$PASTA_BIN/lintux" --version >/dev/null || falha "a verificação final falhou."

echo
ok "Lintux instalado com sucesso! $("$PASTA_BIN/lintux" --version)"
echo
echo "  Próximos passos:"
echo "    lintux help                                  ${CIANO}# guia completo${RESET}"
echo "    lintux add ola 'echo \"Olá, \$USER!\"'          ${CIANO}# salva um comando${RESET}"
echo "    lintux ola                                   ${CIANO}# executa${RESET}"
echo
echo "  Para o autocompletar com Tab funcionar, abra um novo terminal."
