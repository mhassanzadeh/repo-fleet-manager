# fish completion for Repo Fleet Manager (rfm)
complete -c rfm -f
complete -c rfm -s h -l help -d 'Show help'
complete -c rfm -l version -d 'Show version'

set -l rfm_commands config doctor auth catalog graph safety repos submodules local git source compose images ops docs completion
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a config -d 'Validate and migrate configuration'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a doctor -d 'Dependency and provider diagnostics'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a auth -d 'Authentication diagnostics'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a catalog -d 'Repository and capability catalog'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a graph -d 'Repository dependency graph'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a safety -d 'Workspace safety status'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a repos -d 'Repository provider operations'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a submodules -d 'Submodule operations'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a local -d 'Local-only workflows'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a git -d 'Fleet-wide Git operations'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a source -d 'Source fingerprint operations'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a compose -d 'Compose operations'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a images -d 'Image verification'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a ops -d 'Operation journals and rollback'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a docs -d 'Documentation utilities'
complete -c rfm -n "not __fish_seen_subcommand_from $rfm_commands" -a completion -d 'Generate shell completion'

complete -c rfm -n '__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from validate migrate render profiles groups' -a 'validate migrate render profiles groups'
complete -c rfm -n '__fish_seen_subcommand_from auth; and not __fish_seen_subcommand_from status' -a status
complete -c rfm -n '__fish_seen_subcommand_from graph; and not __fish_seen_subcommand_from show' -a show
complete -c rfm -n '__fish_seen_subcommand_from safety; and not __fish_seen_subcommand_from status' -a status
complete -c rfm -n '__fish_seen_subcommand_from repos; and not __fish_seen_subcommand_from audit create publish fork mirror reconcile' -a 'audit create publish fork mirror reconcile'
complete -c rfm -n '__fish_seen_subcommand_from submodules; and not __fish_seen_subcommand_from sync' -a sync
complete -c rfm -n '__fish_seen_subcommand_from local; and not __fish_seen_subcommand_from plan remotes init clone bootstrap localize backup verify-backup backups restore' -a 'plan remotes init clone bootstrap localize backup verify-backup backups restore'
complete -c rfm -n '__fish_seen_subcommand_from git; and not __fish_seen_subcommand_from status pull push' -a 'status pull push'
complete -c rfm -n '__fish_seen_subcommand_from source; and not __fish_seen_subcommand_from fingerprint' -a fingerprint
complete -c rfm -n '__fish_seen_subcommand_from compose; and not __fish_seen_subcommand_from ps up down build pull logs' -a 'ps up down build pull logs'
complete -c rfm -n '__fish_seen_subcommand_from images; and not __fish_seen_subcommand_from verify' -a verify
complete -c rfm -n '__fish_seen_subcommand_from ops; and not __fish_seen_subcommand_from list show resume rollback' -a 'list show resume rollback'
complete -c rfm -n '__fish_seen_subcommand_from docs; and not __fish_seen_subcommand_from validate-links' -a validate-links
complete -c rfm -n '__fish_seen_subcommand_from completion' -a 'bash fish'

complete -c rfm -l config -r -a '(__fish_complete_suffix .json)' -d 'Configuration file'
complete -c rfm -l root -r -a '(__fish_complete_directories)' -d 'Workspace root'
complete -c rfm -l profile -r -d 'Named configuration profile; repeatable'
complete -c rfm -l group -r -d 'Named repository group; repeatable'
complete -c rfm -l provider -r -a 'github gitlab local' -d 'Provider'
complete -c rfm -l namespace -r -d 'Provider namespace'
complete -c rfm -l visibility -r -a 'private public'
complete -c rfm -l format -r -a 'text json markdown dot'
complete -c rfm -l view -r -a 'repositories summary tree gaps all'
complete -c rfm -l priority -r -a 'P0 P1 P2 P3'
complete -c rfm -l status -r -a 'implemented partial planned missing'
complete -c rfm -l only -r -a 'all new upstream existing'
complete -c rfm -l jobs -r -d 'Maximum parallel jobs'
complete -c rfm -l apply -d 'Apply changes'
complete -c rfm -l force -d 'Override safety guards; requires --reason'
complete -c rfm -l reason -r -d 'Reason for forced operation'
complete -c rfm -l json -d 'JSON output'
complete -c rfm -l verbose -d 'Verbose output'
complete -c rfm -l strict -d 'Strict schema validation'
complete -c rfm -l write -d 'Write generated metadata'
complete -c rfm -l check-remote -d 'Check provider remote existence'
complete -c rfm -l check-evidence -d 'Validate catalog evidence'
complete -c rfm -l mirror-sources -d 'Create local mirrors from upstream URLs'
complete -c rfm -l update-mirrors -d 'Fetch/prune existing mirrors'
complete -c rfm -l no-set-origin -d 'Keep existing root origin'
complete -c rfm -l no-create -d 'Do not create provider repository'
complete -c rfm -l remote-name -r -d 'Git remote name'

complete -c rfm -l strict-scopes -d 'Fail when required provider scopes cannot be verified'
complete -c rfm -l strict-auth -d 'Include strict provider authentication checks in doctor'

complete -c rfm -l backups-dir -r -a '(__fish_complete_directories)' -d 'Backup archive directory'
complete -c rfm -l output -r -d 'Backup archive output path'
complete -c rfm -l config-output -r -d 'Restored configuration output path'
complete -c rfm -l include-operations -d 'Include completed operation journals in backup'
complete -c rfm -l restore-operations -d 'Restore operation journals from backup'
complete -c rfm -l retention -r -d 'Number of backup archives to retain'
complete -c rfm -l overwrite -d 'Replace existing restore targets'
complete -c rfm -l no-config -d 'Do not restore repo-fleet.json'
complete -c rfm -l no-include-operations -d 'Exclude operation journals from backup'
complete -c rfm -n '__fish_seen_subcommand_from verify-backup restore' -F -d 'Backup archive'
