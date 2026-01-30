#!/usr/bin/env python3
# Copyright (c) 2025 FuzzingLabs
#
# Licensed under the Business Source License 1.1 (BSL). See the LICENSE file
# at the root of this repository for details.
#
# After the Change Date (four years from publication), this version of the
# Licensed Work will be made available under the Apache License, Version 2.0.
# See the LICENSE-APACHE file or http://www.apache.org/licenses/LICENSE-2.0
#
# Additional attribution and requirements are provided in the NOTICE file.

"""
Install shell completion for FuzzForge CLI.

This script installs completion using Typer's built-in --install-completion command.
"""

import os
import sys
import subprocess
from pathlib import Path
import typer


def run_fuzzforge_completion_install(shell: str) -> bool:
    """Install completion using the fuzzforge CLI itself."""
    try:
        # Use the CLI's built-in completion installation
        result = subprocess.run([
            sys.executable, "-m", "fuzzforge_cli.main",
            "--install-completion", shell
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

        if result.returncode == 0:
            print(f"✅ {shell.capitalize()} completion installed successfully")
            return True
        else:
            print(f"❌ Failed to install {shell} completion: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Error installing {shell} completion: {e}")
        return False


def create_manual_completion_scripts():
    """Create manual completion scripts as fallback."""
    scripts = {
        "bash": '''
# FuzzForge CLI completion for bash
_fuzzforge_completion() {
    local IFS=$'\\t'
    local response

    response=$(env COMP_WORDS="${COMP_WORDS[*]}" COMP_CWORD=$COMP_CWORD _FUZZFORGE_COMPLETE=bash_complete $1)

    for completion in $response; do
        IFS=',' read type value <<< "$completion"

        if [[ $type == 'dir' ]]; then
            COMPREPLY=()
            compopt -o dirnames
        elif [[ $type == 'file' ]]; then
            COMPREPLY=()
            compopt -o default
        elif [[ $type == 'plain' ]]; then
            COMPREPLY+=($value)
        fi
    done

    return 0
}

complete -o nosort -F _fuzzforge_completion fuzzforge
        ''',

        "zsh": '''
#compdef fuzzforge

_fuzzforge_completion() {
    local -a completions
    local -a completions_with_descriptions
    local -a response
    response=(${(f)"$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) _FUZZFORGE_COMPLETE=zsh_complete fuzzforge)"})

    for type_and_line in $response; do
        if [[ "$type_and_line" =~ ^([^,]*),(.*)$ ]]; then
            local type="$match[1]"
            local line="$match[2]"

            if [[ "$type" == "dir" ]]; then
                _path_files -/
            elif [[ "$type" == "file" ]]; then
                _path_files -f
            elif [[ "$type" == "plain" ]]; then
                if [[ "$line" =~ ^([^:]*):(.*)$ ]]; then
                    completions_with_descriptions+=("$match[1]":"$match[2]")
                else
                    completions+=("$line")
                fi
            fi
        fi
    done

    if [ -n "$completions_with_descriptions" ]; then
        _describe "" completions_with_descriptions -V unsorted
    fi

    if [ -n "$completions" ]; then
        compadd -U -V unsorted -a completions
    fi
}

compdef _fuzzforge_completion fuzzforge;
        ''',

        "fish": '''
# FuzzForge CLI completion for fish
function __fuzzforge_completion
    set -l response

    for value in (env _FUZZFORGE_COMPLETE=fish_complete COMP_WORDS=(commandline -cp) COMP_CWORD=(commandline -t) fuzzforge)
        set response $response $value
    end

    for completion in $response
        set -l metadata (string split "," $completion)

        if test $metadata[1] = "dir"
            __fish_complete_directories $metadata[2]
        else if test $metadata[1] = "file"
            __fish_complete_path $metadata[2]
        else if test $metadata[1] = "plain"
            echo $metadata[2]
        end
    end
end

complete --no-files --command fuzzforge --arguments "(__fuzzforge_completion)"
        '''
    }

    return scripts


def install_bash_completion():
    """Install bash completion."""
    print("📝 Installing bash completion...")

    # Get the manual completion script
    scripts = create_manual_completion_scripts()
    completion_script = scripts["bash"]

    # Try different locations for bash completion
    completion_dirs = [
        Path.home() / ".bash_completion.d",
        Path("/usr/local/etc/bash_completion.d"),
        Path("/etc/bash_completion.d")
    ]

    for completion_dir in completion_dirs:
        try:
            completion_dir.mkdir(exist_ok=True)
            completion_file = completion_dir / "fuzzforge"
            completion_file.write_text(completion_script)
            print(f"✅ Bash completion installed to: {completion_file}")

            # Add source line to .bashrc if not present
            bashrc = Path.home() / ".bashrc"
            source_line = f"source {completion_file}"

            if bashrc.exists():
                bashrc_content = bashrc.read_text()
                if source_line not in bashrc_content:
                    with bashrc.open("a") as f:
                        f.write(f"\n# FuzzForge CLI completion\n{source_line}\n")
                    print("✅ Added completion source to ~/.bashrc")

            return True
        except PermissionError:
            continue
        except Exception as e:
            print(f"❌ Failed to install bash completion: {e}")
            continue

    print("❌ Could not install bash completion (permission denied)")
    return False


def install_zsh_completion():
    """Install zsh completion."""
    print("📝 Installing zsh completion...")

    # Get the manual completion script
    scripts = create_manual_completion_scripts()
    completion_script = scripts["zsh"]

    # Create completion directory
    comp_dir = Path.home() / ".zsh" / "completions"
    comp_dir.mkdir(parents=True, exist_ok=True)

    try:
        completion_file = comp_dir / "_fuzzforge"
        completion_file.write_text(completion_script)
        print(f"✅ Zsh completion installed to: {completion_file}")

        # Add fpath to .zshrc if not present
        zshrc = Path.home() / ".zshrc"
        fpath_line = 'fpath=(~/.zsh/completions $fpath)'
        autoload_line = 'autoload -U compinit && compinit'

        if zshrc.exists():
            zshrc_content = zshrc.read_text()
            lines_to_add = []

            if fpath_line not in zshrc_content:
                lines_to_add.append(fpath_line)

            if autoload_line not in zshrc_content:
                lines_to_add.append(autoload_line)

            if lines_to_add:
                with zshrc.open("a") as f:
                    f.write("\n# FuzzForge CLI completion\n")
                    for line in lines_to_add:
                        f.write(f"{line}\n")
                print("✅ Added completion setup to ~/.zshrc")

        return True
    except Exception as e:
        print(f"❌ Failed to install zsh completion: {e}")
        return False


def install_fish_completion():
    """Install fish completion."""
    print("📝 Installing fish completion...")

    # Get the manual completion script
    scripts = create_manual_completion_scripts()
    completion_script = scripts["fish"]

    # Fish completion directory
    comp_dir = Path.home() / ".config" / "fish" / "completions"
    comp_dir.mkdir(parents=True, exist_ok=True)

    try:
        completion_file = comp_dir / "fuzzforge.fish"
        completion_file.write_text(completion_script)
        print(f"✅ Fish completion installed to: {completion_file}")
        return True
    except Exception as e:
        print(f"❌ Failed to install fish completion: {e}")
        return False


def detect_shell():
    """Detect the current shell."""
    shell_path = os.environ.get('SHELL', '')
    if 'bash' in shell_path:
        return 'bash'
    elif 'zsh' in shell_path:
        return 'zsh'
    elif 'fish' in shell_path:
        return 'fish'
    else:
        return None


def main():
    """Install completion for the current shell or all shells."""
    print("🚀 FuzzForge CLI Completion Installer")
    print("=" * 50)

    current_shell = detect_shell()
    if current_shell:
        print(f"🐚 Detected shell: {current_shell}")

    # Check for command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        install_all = True
        print("Installing completion for all shells...")
    else:
        # Ask user which shells to install (with default to current shell only)
        if current_shell:
            install_all = typer.confirm("Install completion for all supported shells (bash, zsh, fish)?", default=False)
            if not install_all:
                print(f"Installing completion for {current_shell} only...")
        else:
            install_all = typer.confirm("Install completion for all supported shells (bash, zsh, fish)?", default=True)

    success_count = 0

    if install_all or current_shell == 'bash':
        if install_bash_completion():
            success_count += 1

    if install_all or current_shell == 'zsh':
        if install_zsh_completion():
            success_count += 1

    if install_all or current_shell == 'fish':
        if install_fish_completion():
            success_count += 1

    print("\n" + "=" * 50)
    if success_count > 0:
        print(f"✅ Successfully installed completion for {success_count} shell(s)!")
        print("\n📋 To activate completion:")
        print("  • Bash: Restart your terminal or run 'source ~/.bashrc'")
        print("  • Zsh: Restart your terminal or run 'source ~/.zshrc'")
        print("  • Fish: Completion is active immediately")
        print("\n💡 Try typing 'fuzzforge <TAB>' to test completion!")
    else:
        print("❌ No completions were installed successfully.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())