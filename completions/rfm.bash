# bash completion for Repo Fleet Manager (rfm)
# Install manually with:
#   rfm completion bash > ~/.local/share/bash-completion/completions/rfm

_rfm()
{
    local cur prev words cword
    if declare -F _init_completion >/dev/null 2>&1; then
        _init_completion -n : || return
    else
        words=("${COMP_WORDS[@]}")
        cword=$COMP_CWORD
        cur="${COMP_WORDS[COMP_CWORD]}"
        prev="${COMP_WORDS[COMP_CWORD-1]}"
    fi

    local commands="doctor catalog repos submodules local git source compose images docs completion"
    local global_opts="--help --version --config --root"

    case "$prev" in
        --config)
            if declare -F _filedir >/dev/null 2>&1; then
                _filedir '@(json)'
            else
                COMPREPLY=( $(compgen -f -- "$cur") )
            fi
            return
            ;;
        --root)
            if declare -F _filedir >/dev/null 2>&1; then
                _filedir -d
            else
                COMPREPLY=( $(compgen -d -- "$cur") )
            fi
            return
            ;;
        --provider)
            COMPREPLY=( $(compgen -W "github gitlab local" -- "$cur") )
            return
            ;;
        --visibility)
            COMPREPLY=( $(compgen -W "private public" -- "$cur") )
            return
            ;;
        completion)
            COMPREPLY=( $(compgen -W "bash fish" -- "$cur") )
            return
            ;;
    esac

    local cmd="" token i skip_next=0
    for ((i=1; i<cword; i++)); do
        token="${words[i]}"
        if (( skip_next )); then
            skip_next=0
            continue
        fi
        case "$token" in
            --config|--root|--provider|--namespace|--visibility)
                skip_next=1
                continue
                ;;
            --*)
                continue
                ;;
        esac
        case " $commands " in
            *" $token "*) cmd="$token"; break ;;
        esac
    done

    if [[ -z "$cmd" ]]; then
        COMPREPLY=( $(compgen -W "$commands $global_opts" -- "$cur") )
        return
    fi

    local opts action=""
    case "$cmd" in
        doctor)
            opts="--help --config --root"
            ;;
        catalog)
            opts="--help --config --root --json"
            ;;
        repos)
            for ((i=1; i<cword; i++)); do
                [[ "${words[i]}" == "audit" || "${words[i]}" == "create" || "${words[i]}" == "publish" ]] && action="${words[i]}"
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "audit create publish --help --config --root" -- "$cur") )
                return
            fi
            case "$action" in
                audit) opts="--help --provider --namespace --check-remote --json" ;;
                create) opts="--help --provider --namespace --visibility --apply" ;;
                publish) opts="--help --provider --namespace --visibility --only --remote-name --no-create --apply" ;;
            esac
            ;;
        submodules)
            for ((i=1; i<cword; i++)); do
                [[ "${words[i]}" == "sync" ]] && action="${words[i]}"
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "sync --help --config --root" -- "$cur") )
                return
            fi
            opts="--help --provider --namespace --apply"
            ;;
        local)
            for ((i=1; i<cword; i++)); do
                case "${words[i]}" in
                    plan|remotes|init|clone|bootstrap|localize) action="${words[i]}" ;;
                esac
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "plan remotes init clone bootstrap localize --help --config --root" -- "$cur") )
                return
            fi
            opts="--help --config --root --remotes-dir --apply --mirror-sources --update-mirrors --seed --with-remotes --set-origin --no-set-origin --json"
            ;;
        git)
            for ((i=1; i<cword; i++)); do
                [[ "${words[i]}" == "status" || "${words[i]}" == "pull" || "${words[i]}" == "push" ]] && action="${words[i]}"
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "status pull push --help --config --root" -- "$cur") )
                return
            fi
            opts="--help --config --root --apply --no-root"
            ;;
        source)
            for ((i=1; i<cword; i++)); do
                [[ "${words[i]}" == "fingerprint" ]] && action="${words[i]}"
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "fingerprint --help --config --root" -- "$cur") )
                return
            fi
            opts="--help --write"
            ;;
        compose)
            for ((i=1; i<cword; i++)); do
                case "${words[i]}" in
                    ps|up|down|build|pull|logs) action="${words[i]}" ;;
                esac
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "ps up down build pull logs --help --config --root" -- "$cur") )
                return
            fi
            opts="--help --apply"
            ;;
        images)
            for ((i=1; i<cword; i++)); do
                [[ "${words[i]}" == "verify" ]] && action="${words[i]}"
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "verify --help --config --root" -- "$cur") )
                return
            fi
            opts="--help --json"
            ;;
        docs)
            for ((i=1; i<cword; i++)); do
                [[ "${words[i]}" == "validate-links" ]] && action="${words[i]}"
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "validate-links --help --config --root" -- "$cur") )
                return
            fi
            opts="--help"
            ;;
        completion)
            opts="bash fish --help"
            ;;
    esac

    COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
}

complete -F _rfm rfm
