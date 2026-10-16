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

**Save long terminal commands under short names, chain them into run lists, and execute them safely.**

[Website](https://miqueiasklippel.github.io/lintux/) · [Português](README.pt-BR.md) · English

![Python](https://img.shields.io/badge/python-3.6%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)
![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-orange)

</div>

---

## What is LinTux?

LinTux is a command-line tool for Linux that works as a personal library of terminal commands. Instead of memorizing or retyping long commands such as `sudo apt update && sudo apt upgrade -y`, you save them once under a short name and run them with `lintux <name>`.

Commands can be grouped into **run lists**: ordered sequences of steps executed one after another, with a progress header for each step. If a step fails, the list stops immediately and tells you exactly where.

LinTux is aimed at two audiences:

- **People who are new to Linux** and want a safe, readable way to keep the commands they learn, inspect them before running, and avoid destructive mistakes.
- **Experienced users** who want a lightweight alternative to scattered aliases and ad-hoc scripts, with parameters, history and backups built in.

It is a single Python file that uses only the standard library, so there is nothing to install besides Python 3 itself.

> **Note:** the program's interface (messages, help and prompts) is in Brazilian Portuguese.

## Features

- **Saved commands:** store any shell command, including pipes, redirects and `&&` chains, under a short name.
- **Run lists:** chain saved commands into ordered sequences that stop at the first failure (or continue with `-k`).
- **Parameters:** placeholders such as `{{1}}`, `{{2:default}}` and `{{@}}` turn a saved command into a reusable template. Arguments are always shell-escaped.
- **Inspect before running:** `lintux show <name>` displays exactly what will run, and `-n` (dry run) simulates without executing.
- **Safety net:** potentially destructive operations (`rm -rf /`, `mkfs`, `dd of=/dev/...`, `curl | sh`, `reboot` and others) require confirmation before running.
- **Interactive commands work:** `sudo` password prompts and `[Y/n]` confirmations behave exactly as they do in your terminal, with real-time output.
- **Organization:** rename (lists are updated automatically), reorder list steps, add descriptions, search, and edit in your `$EDITOR`.
- **History:** every run is logged with date, duration and exit code.
- **Backup and restore:** one-command backups to your Downloads folder, and merge-based restoration with conflict reporting.
- **Data safety:** atomic writes, an automatic copy of the previous database, and a safety copy before every restore.
- **Tab completion** for bash, plus "did you mean…?" suggestions for mistyped names.
- **Script-friendly:** LinTux exits with the same exit code as the command it ran.

## Compatibility

| Family | Distributions |
|---|---|
| Debian | Debian, Ubuntu, Linux Mint and derivatives |
| Red Hat | RHEL, Fedora, CentOS, AlmaLinux, Rocky Linux and derivatives |

Requirements: **Python 3.6 or newer** (already present on most desktop distributions). Tab completion needs the `bash-completion` package, which is installed by default on Debian, Ubuntu, Mint and Fedora.

## Installation

```bash
git clone https://github.com/miqueiasklippel/lintux.git
cd lintux
./install.sh            # system-wide: /usr/local/bin/lintux (uses sudo)
```

Or, without administrator privileges:

```bash
./install.sh --user     # current user only: ~/.local/bin/lintux
```

Open a new terminal afterwards so Tab completion is loaded. Running `install.sh` again updates an existing installation without touching your saved data.

If Python 3 is missing on a minimal server: `sudo apt install python3` (Debian family) or `sudo dnf install python3` (Red Hat family).

## Quick start

```bash
lintux                                   # welcome screen
lintux add hello 'echo "Hello, $USER!"'  # save a command
lintux hello                             # run it

lintux add disk 'df -h {{1:/}}'          # parameter with a default value
lintux disk /home

lintux add list routine                  # create an empty run list
lintux add list routine hello            # add an existing command
lintux add list routine memory 'free -h' # create a command and add it at once
lintux show routine                      # inspect without running
lintux -n routine                        # dry run
lintux routine                           # run every step in order

lintux new backup                        # back up your data
lintux help                              # full guide
```

## Command reference

### Single commands

| Command | Description |
|---|---|
| `lintux <name> [args]` | Run a saved command or list |
| `lintux add <name> '<command>'` | Save a new command |
| `lintux edit <name> '<new command>'` | Replace a command's code |
| `lintux edit <name>` | Edit the code in your text editor |
| `lintux rm <name> [-y]` | Remove a command (asks before removing it from lists) |
| `lintux list cmd` | Show all saved commands |

### Run lists

| Command | Description |
|---|---|
| `lintux add list <list>` | Create an empty list |
| `lintux add list <list> <command>` | Add an existing command as a step |
| `lintux add list <list> <new> '<code>'` | Save a new command and add it as a step |
| `lintux edit <list>` | Reorder steps in your text editor |
| `lintux mv <list> <from> <to>` | Move a step to another position |
| `lintux rm list <list> [step]` | Remove the list, or a single step (by name or number) |
| `lintux list lists` | Show all lists and their steps |

### Inspection and organization

| Command | Description |
|---|---|
| `lintux show <name>` | Show the code without running it |
| `lintux list` | Show commands and lists |
| `lintux search <term>` | Search names, code and descriptions |
| `lintux rename <old> <new>` | Rename, updating every list that uses it |
| `lintux desc <name> '<text>'` | Set a description (`''` removes it) |
| `lintux history [n \| clear]` | Show or clear the execution history |

### Backup

| Command | Description |
|---|---|
| `lintux new backup [folder]` | Create `lintux_backup_YYYY-MM-DD_HH-MM.json` (default: Downloads) |
| `lintux add backup <file> [--overwrite]` | Validate and merge a backup into your data |

The Downloads folder is detected with `xdg-user-dir`, then `~/Downloads` or `~/Transferências`, falling back to your home folder. When restoring, entries that already exist with different content are kept as they are unless you pass `--overwrite`.

### Execution options

Options go **before** the name: `lintux [options] <name> [args]`.

| Option | Effect |
|---|---|
| `-y`, `--yes` | Skip confirmation for potentially destructive operations |
| `-k`, `--keep-going` | In lists, continue with the next steps after a failure |
| `-n`, `--dry-run` | Show what would run, without running it |
| `-q`, `--quiet` | Hide LinTux headers and status messages |

## Parameters

| Placeholder | Meaning |
|---|---|
| `{{1}}`, `{{2}}`, … | Argument at that position (required) |
| `{{1:default}}` | Argument with a default value |
| `{{@}}` | All arguments |

If a saved command has no placeholders, extra arguments are appended to the end: after `lintux add see 'ls'`, running `lintux see -la /tmp` executes `ls -la /tmp`.

## Important: quote your commands

Always wrap commands containing `&&`, `||`, `|`, `>`, `<`, `;`, `$`, `*` or `~` in **single quotes**:

```bash
lintux add update 'sudo apt update && sudo apt upgrade -y'   # correct
lintux add update sudo apt update && sudo apt upgrade -y     # wrong
```

Without quotes, your shell processes those operators **before** LinTux receives anything: in the second line, only `sudo apt update` is saved and `sudo apt upgrade -y` runs immediately. No program can prevent this, because it happens in your shell. If the command itself contains single quotes, use double quotes around it: `"echo 'hi'"`.

## Good to know

- Commands run through `bash -c` (or `/bin/sh` when bash is not available). Aliases and functions defined in `~/.bashrc` are **not** available in this mode, so save the full command instead of an alias.
- The destructive-operation detector is a heuristic safety net, not a guarantee. Use `lintux show` before running anything you did not write yourself.
- Pressing Ctrl+C stops the running command and the whole list, even with `-k`.

## Files

| Path | Contents |
|---|---|
| `~/.lintux/database.json` | Your commands and lists (previous version in `database.json.bak`) |
| `~/.lintux/history.log` | Execution history |
| `~/.lintux/backups/` | Safety copies made automatically before each restore |

Environment variables: `LINTUX_HOME` (use another data folder), `NO_COLOR` (disable colors), `EDITOR` / `VISUAL` (editor used by `lintux edit`).

## Uninstall

```bash
./uninstall.sh            # asks whether to delete your data
./uninstall.sh --keep     # keeps ~/.lintux
./uninstall.sh --purge    # deletes ~/.lintux after saving a final backup to Downloads
```

## License

LinTux is distributed under the **[PolyForm Noncommercial License 1.0.0](LICENSE.md)**.

You may use, study, modify and share it for any **noncommercial** purpose: personal use, study, research, hobby projects, and use by charitable, educational and public organizations. **Commercial use is not permitted** without separate permission from the author.

Because it restricts commercial use, this license is *source-available* rather than "open source" in the strict sense defined by the Open Source Initiative. The full source code is public and free to read, change and redistribute under the terms above.

For commercial licensing, contact the author.

## Author

Developed by **M. A. KLIPPEL**
Contact: [contato@klippelbit.app.br](mailto:contato@klippelbit.app.br)
Project: <https://github.com/miqueiasklippel/lintux>
