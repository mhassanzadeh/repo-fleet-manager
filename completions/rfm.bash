# bash completion for Repo Fleet Manager (rfm)
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

    local commands="config doctor auth catalog graph safety repos submodules local git source compose images ops docs completion"
    local global_opts="--help --version --config --root --profile --group"

    case "$prev" in
        --config|--output|--catalog-file|--config-output)
            COMPREPLY=( $(compgen -f -- "$cur") ); return ;;
        --root|--remotes-dir|--backups-dir)
            COMPREPLY=( $(compgen -d -- "$cur") ); return ;;
        --provider)
            COMPREPLY=( $(compgen -W "github gitlab local" -- "$cur") ); return ;;
        --visibility)
            COMPREPLY=( $(compgen -W "private public" -- "$cur") ); return ;;
        --format)
            COMPREPLY=( $(compgen -W "text json markdown dot" -- "$cur") ); return ;;
        --view)
            COMPREPLY=( $(compgen -W "repositories summary tree gaps all" -- "$cur") ); return ;;
        --priority)
            COMPREPLY=( $(compgen -W "P0 P1 P2 P3" -- "$cur") ); return ;;
        --status)
            COMPREPLY=( $(compgen -W "implemented partial planned missing" -- "$cur") ); return ;;
        --only)
            COMPREPLY=( $(compgen -W "all new upstream existing" -- "$cur") ); return ;;
        --to)
            COMPREPLY=( $(compgen -W "1.0.0" -- "$cur") ); return ;;
        completion)
            COMPREPLY=( $(compgen -W "bash fish" -- "$cur") ); return ;;
    esac

    local cmd="" action="" token i skip_next=0
    for ((i=1; i<cword; i++)); do
        token="${words[i]}"
        if (( skip_next )); then skip_next=0; continue; fi
        case "$token" in
            --config|--root|--profile|--group|--provider|--namespace|--visibility|--format|--view|--priority|--status|--output|--catalog-file|--reason|--jobs|--remote-name|--to|--backups-dir|--config-output|--retention)
                skip_next=1; continue ;;
            --*) continue ;;
        esac
        if [[ -z "$cmd" && " $commands " == *" $token "* ]]; then cmd="$token"; continue; fi
        if [[ -n "$cmd" && -z "$action" ]]; then action="$token"; fi
    done

    if [[ -z "$cmd" ]]; then
        COMPREPLY=( $(compgen -W "$commands $global_opts" -- "$cur") ); return
    fi

    local actions="" opts="--help --config --root --profile --group"
    case "$cmd" in
        config) actions="validate migrate render profiles groups"; opts+=" --strict --json --to --no-backup --output --apply --force --reason" ;;
        doctor) opts+=" --auth --provider --strict-auth" ;;
        auth) actions="status"; opts+=" --provider --json --verbose --strict-scopes" ;;
        catalog) opts+=" --view --format --json --output --catalog-file --priority --status --check-evidence" ;;
        graph) actions="show"; opts+=" --format --output" ;;
        safety) actions="status"; opts+=" --json" ;;
        repos) actions="audit create publish fork mirror reconcile"; opts+=" --provider --namespace --visibility --check-remote --json --only --remote-name --no-create --apply --strict-scopes --force --reason" ;;
        submodules) actions="sync"; opts+=" --provider --namespace --apply --force --reason" ;;
        local) actions="plan remotes init clone bootstrap localize backup verify-backup backups restore"; opts+=" --remotes-dir --backups-dir --output --config-output --json --mirror-sources --update-mirrors --seed --with-remotes --set-origin --no-set-origin --jobs --include-operations --no-include-operations --restore-operations --retention --overwrite --no-config --apply --force --reason" ;;
        git) actions="status pull push"; opts+=" --jobs --apply --no-root --force --reason" ;;
        source) actions="fingerprint"; opts+=" --write --force --reason" ;;
        compose) actions="ps up down build pull logs"; opts+=" --apply --force --reason" ;;
        images) actions="verify"; opts+=" --json" ;;
        ops) actions="list show resume rollback"; opts+=" --json --force --reason" ;;
        docs) actions="validate-links" ;;
        completion) actions="bash fish"; opts="--help" ;;
    esac

    if [[ "$cmd" == "local" && ( "$action" == "verify-backup" || "$action" == "restore" ) && "$cur" != -* ]]; then
        COMPREPLY=( $(compgen -f -- "$cur") )
        return
    fi

    if [[ -n "$actions" && ( -z "$action" || "$cur" != -* ) ]]; then
        COMPREPLY=( $(compgen -W "$actions $opts" -- "$cur") )
    else
        COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
    fi
}
complete -F _rfm rfm
