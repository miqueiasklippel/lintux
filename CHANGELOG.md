# Changelog

Todas as mudanças relevantes do LinTux são registradas aqui.
All notable changes to LinTux are documented here.

## [1.0.1] - 2026-11-15

### Corrigido

- **Comandos que já têm aspas simples.** O bash não permite aspas simples dentro de aspas simples. Em `lintux add x 'grep 'foo bar' arquivo'`, o shell consumia as aspas internas antes de o LinTux receber o comando, que era salvo quebrado sem nenhum aviso. Agora há formas de salvar esses comandos sem passar pelo shell:
  - `lintux add <nome>`: o LinTux pede o comando no terminal e o salva exatamente como foi digitado. Uma linha terminada em `\` continua na próxima.
  - `lintux add <nome> - <<'EOF'` (ou `< arquivo`): lê o comando da entrada padrão, para uso em scripts.
  - `lintux add list <lista> <comando>`, com um comando que ainda não existe: o LinTux oferece criá-lo na hora.
- **Detecção de aspas consumidas pelo shell.** Quando o comando chega em pedaços, o LinTux mostra os pedaços recebidos e oferece digitar o comando de novo. Sem terminal interativo, não salva nada e termina com erro, em vez de gravar um comando incorreto.

### Alterado

- `lintux edit <nome>` sem um editor de texto instalado agora edita o comando na própria linha do terminal, já preenchida com o código atual, em vez de terminar com erro.
- A ajuda (`lintux help`), os READMEs e o site explicam as novas formas de entrada e deixam de recomendar aspas duplas por fora, que expandem `$variáveis` no momento em que o comando é salvo.

### Fixed (English summary)

- Commands that already contain single quotes can now be saved with `lintux add <name>` (interactive prompt, no shell involved), `lintux add <name> - <<'EOF'` (standard input), or created on the fly by `lintux add list`. When the shell has eaten the inner quotes, LinTux now detects it instead of silently saving a broken command.

## [1.0.0] - 2026-10-15

- Primeira versão pública: comandos salvos, listas de execução, parâmetros, simulação, rede de proteção, histórico, backup e restauração, autocompletar e instaladores.
