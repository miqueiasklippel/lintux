# Autocompletar do Lintux para o bash.
# Instalado automaticamente pelo install.sh. Requer o pacote bash-completion
# (já presente por padrão no Debian, Ubuntu, Mint e Fedora; no RHEL/Alma/Rocky:
# sudo dnf install bash-completion).

_lintux() {
    local cur sub nomes
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    sub="${COMP_WORDS[1]}"

    if [[ $COMP_CWORD -eq 1 ]]; then
        nomes="$(lintux __complete all 2>/dev/null)"
        COMPREPLY=( $(compgen -W "$nomes" -- "$cur") )
        return 0
    fi

    case "$sub" in
        show|edit|rename|desc|run)
            if [[ $COMP_CWORD -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "$(lintux __complete names 2>/dev/null)" -- "$cur") )
            fi
            ;;
        rm)
            if [[ $COMP_CWORD -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "list $(lintux __complete cmds 2>/dev/null)" -- "$cur") )
            elif [[ ${COMP_WORDS[2]} == "list" && $COMP_CWORD -eq 3 ]]; then
                COMPREPLY=( $(compgen -W "$(lintux __complete lists 2>/dev/null)" -- "$cur") )
            elif [[ ${COMP_WORDS[2]} == "list" && $COMP_CWORD -eq 4 ]]; then
                COMPREPLY=( $(compgen -W "$(lintux __complete cmds 2>/dev/null)" -- "$cur") )
            else
                COMPREPLY=( $(compgen -W "$(lintux __complete cmds 2>/dev/null)" -- "$cur") )
            fi
            ;;
        add)
            if [[ $COMP_CWORD -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "list backup" -- "$cur") )
            elif [[ ${COMP_WORDS[2]} == "list" && $COMP_CWORD -eq 3 ]]; then
                COMPREPLY=( $(compgen -W "$(lintux __complete lists 2>/dev/null)" -- "$cur") )
            elif [[ ${COMP_WORDS[2]} == "list" && $COMP_CWORD -eq 4 ]]; then
                COMPREPLY=( $(compgen -W "$(lintux __complete cmds 2>/dev/null)" -- "$cur") )
            elif [[ ${COMP_WORDS[2]} == "backup" ]]; then
                compopt -o filenames 2>/dev/null
                COMPREPLY=( $(compgen -f -- "$cur") )
            fi
            ;;
        list)
            [[ $COMP_CWORD -eq 2 ]] && COMPREPLY=( $(compgen -W "cmd lists" -- "$cur") )
            ;;
        new)
            [[ $COMP_CWORD -eq 2 ]] && COMPREPLY=( $(compgen -W "backup" -- "$cur") )
            ;;
        history)
            [[ $COMP_CWORD -eq 2 ]] && COMPREPLY=( $(compgen -W "clear" -- "$cur") )
            ;;
        mv)
            [[ $COMP_CWORD -eq 2 ]] && COMPREPLY=( $(compgen -W "$(lintux __complete lists 2>/dev/null)" -- "$cur") )
            ;;
    esac
    return 0
}

complete -F _lintux lintux
