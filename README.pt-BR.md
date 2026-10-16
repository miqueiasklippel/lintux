<div align="center">

```
       .--.
      |o_o |
      |:_/ |
     //   \ \
    (|     | )
   /'\_   _/`\
   \___)=(___/
```

# LinTux

**Salve comandos longos do terminal com nomes curtos, encadeie-os em listas de execução e execute tudo com segurança.**

[Site oficial](https://lintux.klippelbit.app.br/) · Português · [English](README.md)

![Python](https://img.shields.io/badge/python-3.6%2B-blue)
![Dependências](https://img.shields.io/badge/depend%C3%AAncias-nenhuma-brightgreen)
![Plataforma](https://img.shields.io/badge/plataforma-Linux-lightgrey)
![Licença](https://img.shields.io/badge/licen%C3%A7a-PolyForm%20Noncommercial%201.0.0-orange)

</div>

---

## O que é o LinTux?

O LinTux é uma ferramenta de linha de comando para Linux que funciona como uma biblioteca pessoal de comandos do terminal. Em vez de decorar ou redigitar comandos longos como `sudo apt update && sudo apt upgrade -y`, você os salva uma única vez com um nome curto e os executa com `lintux <nome>`.

Os comandos podem ser agrupados em **listas de execução**: sequências ordenadas de etapas executadas uma após a outra, com um cabeçalho de progresso em cada etapa. Se uma etapa falhar, a lista é interrompida imediatamente e informa exatamente onde ocorreu o erro.

O LinTux foi pensado para dois públicos:

- **Quem está começando no Linux** e quer uma forma segura e legível de guardar os comandos que aprende, inspecioná-los antes de executar e evitar erros destrutivos.
- **Usuários experientes** que querem uma alternativa leve a aliases espalhados e scripts improvisados, com parâmetros, histórico e backups já incluídos.

É um único arquivo Python que usa apenas a biblioteca padrão, portanto não há nada para instalar além do próprio Python 3.

## Recursos

- **Comandos salvos:** guarde qualquer comando do shell, inclusive pipes, redirecionamentos e encadeamentos com `&&`, sob um nome curto.
- **Listas de execução:** encadeie comandos salvos em sequências ordenadas que param na primeira falha (ou continuam, com `-k`).
- **Parâmetros:** marcadores como `{{1}}`, `{{2:padrão}}` e `{{@}}` transformam um comando salvo em um modelo reutilizável. Os argumentos são sempre protegidos (escapados) antes de irem para o shell.
- **Inspeção antes de executar:** `lintux show <nome>` mostra exatamente o que será executado, e `-n` (simulação) mostra tudo sem executar.
- **Rede de proteção:** operações potencialmente destrutivas (`rm -rf /`, `mkfs`, `dd of=/dev/...`, `curl | sh`, `reboot` e outras) exigem confirmação antes da execução.
- **Comandos interativos funcionam:** a senha do `sudo` e as confirmações `[S/n]` funcionam exatamente como no seu terminal, com saída em tempo real.
- **Organização:** renomear (as listas são atualizadas automaticamente), reordenar etapas, adicionar descrições, pesquisar e editar no seu `$EDITOR`.
- **Histórico:** cada execução é registrada com data, duração e código de saída.
- **Backup e restauração:** backup com um único comando na pasta Downloads e restauração por mesclagem, com relatório de conflitos.
- **Segurança dos dados:** gravação atômica, cópia automática da versão anterior do banco e cópia de segurança antes de cada restauração.
- **Autocompletar com Tab** no bash, e sugestões do tipo "Você quis dizer…?" para nomes digitados errado.
- **Pronto para scripts:** o LinTux termina com o mesmo código de saída do comando executado.

## Compatibilidade

| Família | Distribuições |
|---|---|
| Debian | Debian, Ubuntu, Linux Mint e derivados |
| Red Hat | RHEL, Fedora, CentOS, AlmaLinux, Rocky Linux e derivados |

Requisito: **Python 3.6 ou superior** (já presente na maioria das distribuições desktop). O autocompletar precisa do pacote `bash-completion`, instalado por padrão no Debian, Ubuntu, Mint e Fedora.

## Instalação

```bash
git clone https://github.com/miqueiasklippel/lintux.git
cd lintux
./install.sh            # para todo o sistema: /usr/local/bin/lintux (usa sudo)
```

Ou, sem privilégios de administrador:

```bash
./install.sh --user     # apenas para o usuário atual: ~/.local/bin/lintux
```

Depois, abra um novo terminal para carregar o autocompletar. Executar o `install.sh` novamente atualiza uma instalação existente sem alterar seus dados salvos.

Se o Python 3 não estiver instalado em um servidor mínimo: `sudo apt install python3` (família Debian) ou `sudo dnf install python3` (família Red Hat).

## Primeiros passos

```bash
lintux                                   # tela inicial
lintux add ola 'echo "Olá, $USER!"'      # salva um comando
lintux ola                               # executa

lintux add disco 'df -h {{1:/}}'         # parâmetro com valor padrão
lintux disco /home

lintux add list rotina                   # cria uma lista vazia
lintux add list rotina ola               # adiciona um comando existente
lintux add list rotina memoria 'free -h' # cria um comando e já o adiciona
lintux show rotina                       # inspeciona sem executar
lintux -n rotina                         # simulação
lintux rotina                            # executa as etapas em ordem

lintux new backup                        # faz backup dos seus dados
lintux help                              # guia completo
```

## Referência de comandos

### Comandos individuais

| Comando | Descrição |
|---|---|
| `lintux <nome> [args]` | Executa um comando ou uma lista salvos |
| `lintux add <nome> '<comando>'` | Salva um novo comando |
| `lintux edit <nome> '<novo comando>'` | Substitui o código de um comando |
| `lintux edit <nome>` | Edita o código no seu editor de texto |
| `lintux rm <nome> [-y]` | Remove um comando (pergunta antes de retirá-lo das listas) |
| `lintux list cmd` | Mostra todos os comandos salvos |

### Listas de execução

| Comando | Descrição |
|---|---|
| `lintux add list <lista>` | Cria uma lista vazia |
| `lintux add list <lista> <comando>` | Adiciona um comando existente como etapa |
| `lintux add list <lista> <novo> '<código>'` | Salva um novo comando e o adiciona como etapa |
| `lintux edit <lista>` | Reorganiza as etapas no editor de texto |
| `lintux mv <lista> <de> <para>` | Move uma etapa para outra posição |
| `lintux rm list <lista> [etapa]` | Remove a lista, ou apenas uma etapa (pelo nome ou número) |
| `lintux list lists` | Mostra todas as listas e suas etapas |

### Inspeção e organização

| Comando | Descrição |
|---|---|
| `lintux show <nome>` | Mostra o código sem executar |
| `lintux list` | Mostra comandos e listas |
| `lintux search <termo>` | Pesquisa em nomes, códigos e descrições |
| `lintux rename <atual> <novo>` | Renomeia, atualizando todas as listas que o usam |
| `lintux desc <nome> '<texto>'` | Define uma descrição (`''` remove) |
| `lintux history [n \| clear]` | Mostra ou apaga o histórico de execuções |

### Backup

| Comando | Descrição |
|---|---|
| `lintux new backup [pasta]` | Cria `lintux_backup_AAAA-MM-DD_HH-MM.json` (padrão: Downloads) |
| `lintux add backup <arquivo> [--overwrite]` | Valida um backup e o mescla aos seus dados |

A pasta Downloads é detectada pelo `xdg-user-dir`, depois por `~/Downloads` ou `~/Transferências`; se nenhuma existir, o backup vai para a sua pasta pessoal. Na restauração, itens que já existem com conteúdo diferente são mantidos como estão, a menos que você use `--overwrite`.

### Opções de execução

As opções vêm **antes** do nome: `lintux [opções] <nome> [args]`.

| Opção | Efeito |
|---|---|
| `-y`, `--yes` | Não pede confirmação para operações potencialmente destrutivas |
| `-k`, `--keep-going` | Em listas, continua as próximas etapas após uma falha |
| `-n`, `--dry-run` | Mostra o que seria executado, sem executar |
| `-q`, `--quiet` | Oculta cabeçalhos e mensagens de status do LinTux |

## Parâmetros

| Marcador | Significado |
|---|---|
| `{{1}}`, `{{2}}`, … | Argumento na posição indicada (obrigatório) |
| `{{1:padrão}}` | Argumento com valor padrão |
| `{{@}}` | Todos os argumentos |

Se o comando salvo não tiver marcadores, os argumentos extras são acrescentados ao final: depois de `lintux add ver 'ls'`, executar `lintux ver -la /tmp` roda `ls -la /tmp`.

## Importante: use aspas

Sempre envolva em **aspas simples** os comandos que contenham `&&`, `||`, `|`, `>`, `<`, `;`, `$`, `*` ou `~`:

```bash
lintux add atualizar 'sudo apt update && sudo apt upgrade -y'   # correto
lintux add atualizar sudo apt update && sudo apt upgrade -y     # errado
```

Sem aspas, o seu shell processa esses operadores **antes** de o LinTux receber qualquer coisa: na segunda linha, apenas `sudo apt update` é salvo, e `sudo apt upgrade -y` é executado imediatamente. Nenhum programa consegue impedir isso, porque acontece no seu shell. Se o comando tiver aspas simples internas, use aspas duplas por fora: `"echo 'olá'"`.

## Bom saber

- Os comandos rodam com `bash -c` (ou `/bin/sh`, quando o bash não está disponível). Aliases e funções definidos no `~/.bashrc` **não** estão disponíveis nesse modo; salve o comando completo em vez do alias.
- O detector de operações destrutivas é uma rede de proteção heurística, não uma garantia. Use `lintux show` antes de executar algo que você não escreveu.
- Ctrl+C interrompe o comando em execução e a lista inteira, mesmo com `-k`.

## Arquivos

| Caminho | Conteúdo |
|---|---|
| `~/.lintux/database.json` | Seus comandos e listas (versão anterior em `database.json.bak`) |
| `~/.lintux/history.log` | Histórico de execuções |
| `~/.lintux/backups/` | Cópias de segurança feitas automaticamente antes de cada restauração |

Variáveis de ambiente: `LINTUX_HOME` (usa outra pasta de dados), `NO_COLOR` (desativa as cores), `EDITOR` / `VISUAL` (editor usado pelo `lintux edit`).

## Desinstalação

```bash
./uninstall.sh            # pergunta se deve apagar seus dados
./uninstall.sh --keep     # mantém ~/.lintux
./uninstall.sh --purge    # apaga ~/.lintux após salvar um backup final em Downloads
```

## Licença

O LinTux é distribuído sob a **[PolyForm Noncommercial License 1.0.0](LICENSE.md)**.

Você pode usá-lo, estudá-lo, modificá-lo e compartilhá-lo para qualquer finalidade **não comercial**: uso pessoal, estudo, pesquisa, projetos de hobby e uso por organizações beneficentes, educacionais e públicas. **O uso comercial não é permitido** sem autorização específica do autor.

Por restringir o uso comercial, esta licença é de *código disponível* (source-available), e não "código aberto" no sentido estrito definido pela Open Source Initiative. O código-fonte completo é público e livre para ler, alterar e redistribuir nos termos acima.

O texto oficial da licença está em inglês, e é ele que tem validade jurídica.

Para licenciamento comercial, entre em contato com o autor.

## Autor

Desenvolvido por **M. A. KLIPPEL**
Contato: [contato@klippelbit.app.br](mailto:contato@klippelbit.app.br)
Projeto: <https://github.com/miqueiasklippel/lintux>
