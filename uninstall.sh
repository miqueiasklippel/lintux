#!/usr/bin/env bash
# =============================================================================
# Desinstalador do Lintux
#
#   ./uninstall.sh           Remove o programa e pergunta o que fazer com seus dados
#   ./uninstall.sh --purge   Remove também ~/.lintux (faz um backup antes, por segurança)
#   ./uninstall.sh --keep    Remove o programa e mantém ~/.lintux sem perguntar
#
# Remove tanto a instalação do sistema (/usr/local) quanto a do usuário (~/.local).
# Execute como usuário comum (o script pede sudo quando necessário).
# =============================================================================
set -euo pipefail

VERDE=$'\033[32m'; VERMELHO=$'\033[31m'; AMARELO=$'\033[33m'; CIANO=$'\033[36m'; NEGRITO=$'\033[1m'; RESET=$'\033[0m'
if [[ ! -t 1 || -n "${NO_COLOR:-}" ]]; then VERDE=""; VERMELHO=""; AMARELO=""; CIANO=""; NEGRITO=""; RESET=""; fi

ok()    { echo "${VERDE}✔ $*${RESET}"; }
falha() { echo "${VERMELHO}✖ Erro: $*${RESET}" >&2; exit 1; }
aviso() { echo "${AMARELO}⚠ $*${RESET}"; }

DADOS_ACAO="perguntar"
case "${1:-}" in
    --purge) DADOS_ACAO="apagar" ;;
    --keep)  DADOS_ACAO="manter" ;;
    --help|-h) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    "") ;;
    *) falha "opção desconhecida: $1 (use --purge, --keep ou --help)" ;;
esac

# Se rodado com sudo, os dados pertencem ao usuário que chamou o sudo
CASA="$HOME"
if [[ -n "${SUDO_USER:-}" && $EUID -eq 0 ]]; then
    CASA="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
    CASA="${CASA:-$HOME}"
fi
DADOS="${LINTUX_HOME:-$CASA/.lintux}"

echo "${CIANO}${NEGRITO}Desinstalador do Lintux${RESET}"

SUDO=""
if [[ $EUID -ne 0 ]] && command -v sudo >/dev/null 2>&1; then SUDO="sudo"; fi

removido=0
remover() {  # remover <caminho> <precisa de sudo: sim|nao>
    local alvo="$1" privilegio="$2"
    if [[ -e "$alvo" || -L "$alvo" ]]; then
        if [[ "$privilegio" == "sim" ]]; then $SUDO rm -rf -- "$alvo"; else rm -rf -- "$alvo"; fi
        ok "Removido: $alvo"
        removido=1
    fi
}

# --- Instalação do sistema --------------------------------------------------------
remover /usr/local/bin/lintux sim
remover /usr/local/lib/lintux sim
remover /usr/share/bash-completion/completions/lintux sim
remover /etc/bash_completion.d/lintux sim

# --- Instalação do usuário ----------------------------------------------------------
remover "$CASA/.local/bin/lintux" nao
remover "$CASA/.local/lib/lintux" nao
remover "${XDG_DATA_HOME:-$CASA/.local/share}/bash-completion/completions/lintux" nao

[[ $removido -eq 1 ]] || aviso "Nenhuma instalação do Lintux foi encontrada."

# --- Dados do usuário ----------------------------------------------------------------
if [[ -d "$DADOS" ]]; then
    if [[ "$DADOS_ACAO" == "perguntar" ]]; then
        if [[ -t 0 ]]; then
            read -r -p "${AMARELO}?${RESET} Apagar também seus comandos e listas em $DADOS? [s/N] " resposta
            [[ "${resposta,,}" =~ ^(s|sim|y|yes)$ ]] && DADOS_ACAO="apagar" || DADOS_ACAO="manter"
        else
            DADOS_ACAO="manter"
        fi
    fi

    if [[ "$DADOS_ACAO" == "apagar" ]]; then
        # Backup final antes de apagar, na pasta de Downloads (ou na Home)
        DESTINO="$(xdg-user-dir DOWNLOAD 2>/dev/null || true)"
        if [[ -z "$DESTINO" || ! -d "$DESTINO" || "$DESTINO" == "$CASA" ]]; then
            DESTINO="$CASA"
            for n in Downloads Transferências Transferencias; do
                [[ -d "$CASA/$n" ]] && { DESTINO="$CASA/$n"; break; }
            done
        fi
        if [[ -f "$DADOS/database.json" ]]; then
            ARQ="$DESTINO/lintux_backup_final_$(date +%Y-%m-%d_%H-%M).json"
            cp "$DADOS/database.json" "$ARQ"
            ok "Backup final dos seus dados salvo em: ${NEGRITO}$ARQ${RESET}"
        fi
        rm -rf -- "$DADOS"
        ok "Dados removidos: $DADOS"
    else
        aviso "Seus dados foram mantidos em $DADOS (reinstalar o Lintux os reaproveita)."
    fi
fi

echo
ok "Desinstalação concluída. Abra um novo terminal para limpar o autocompletar da sessão atual."
