# fish completion for Repo Fleet Manager (rfm)
# Install manually with:
#   rfm completion fish > ~/.config/fish/completions/rfm.fish

complete -c rfm -f
complete -c rfm -s h -l help -d 'Show help'
complete -c rfm -l version -d 'Show version'
complete -c rfm -l config -r -d 'Path to repo-fleet.json'
complete -c rfm -l root -r -a '(__fish_complete_directories)' -d 'Repository root'

complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a doctor -d 'Check dependencies and config'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a catalog -d 'Print repository catalog'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a repos -d 'Repository provider operations'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a submodules -d 'Submodule operations'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a local -d 'Local-only repository operations'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a git -d 'Run git across root and submodules'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a source -d 'Source/image metadata operations'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a compose -d 'Run compose operations'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a images -d 'Verify image labels'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a docs -d 'Documentation utilities'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a completion -d 'Print shell completion script'

complete -c rfm -n '__fish_seen_subcommand_from completion' -a bash -d 'Print Bash completion'
complete -c rfm -n '__fish_seen_subcommand_from completion' -a fish -d 'Print Fish completion'

complete -c rfm -n '__fish_seen_subcommand_from catalog' -l json -d 'Print JSON output'

complete -c rfm -n '__fish_seen_subcommand_from repos; and not __fish_seen_subcommand_from audit create publish' -a audit -d 'Audit .gitmodules and remotes'
complete -c rfm -n '__fish_seen_subcommand_from repos; and not __fish_seen_subcommand_from audit create publish' -a create -d 'Create repositories'
complete -c rfm -n '__fish_seen_subcommand_from repos; and not __fish_seen_subcommand_from audit create publish' -a publish -d 'Publish local repositories'
complete -c rfm -n '__fish_seen_subcommand_from repos' -l provider -r -a 'github gitlab local' -d 'Repository provider'
complete -c rfm -n '__fish_seen_subcommand_from repos' -l namespace -r -d 'Provider namespace/group/org'
complete -c rfm -n '__fish_seen_subcommand_from audit' -l check-remote -d 'Check remote existence'
complete -c rfm -n '__fish_seen_subcommand_from audit' -l json -d 'Print JSON output'
complete -c rfm -n '__fish_seen_subcommand_from create' -l visibility -r -a 'private public' -d 'Repository visibility'
complete -c rfm -n '__fish_seen_subcommand_from create' -l apply -d 'Apply changes'
complete -c rfm -n '__fish_seen_subcommand_from publish' -l only -r -a 'all new upstream existing' -d 'Source type filter'
complete -c rfm -n '__fish_seen_subcommand_from publish' -l remote-name -r -d 'Remote name for publishing'
complete -c rfm -n '__fish_seen_subcommand_from publish' -l no-create -d 'Do not create provider repo'
complete -c rfm -n '__fish_seen_subcommand_from publish' -l apply -d 'Apply changes'

complete -c rfm -n '__fish_seen_subcommand_from submodules; and not __fish_seen_subcommand_from sync' -a sync -d 'Sync .gitmodules and origins'
complete -c rfm -n '__fish_seen_subcommand_from submodules' -l provider -r -a 'github gitlab local' -d 'Repository provider'
complete -c rfm -n '__fish_seen_subcommand_from submodules' -l namespace -r -d 'Provider namespace/group/org'
complete -c rfm -n '__fish_seen_subcommand_from submodules' -l apply -d 'Apply changes'

complete -c rfm -n '__fish_seen_subcommand_from local; and not __fish_seen_subcommand_from plan remotes init clone bootstrap localize' -a plan -d 'Show local materialization plan'
complete -c rfm -n '__fish_seen_subcommand_from local; and not __fish_seen_subcommand_from plan remotes init clone bootstrap localize' -a remotes -d 'Create local bare remotes'
complete -c rfm -n '__fish_seen_subcommand_from local; and not __fish_seen_subcommand_from plan remotes init clone bootstrap localize' -a init -d 'Create local working repositories'
complete -c rfm -n '__fish_seen_subcommand_from local; and not __fish_seen_subcommand_from plan remotes init clone bootstrap localize' -a clone -d 'Clone from local remotes'
complete -c rfm -n '__fish_seen_subcommand_from local; and not __fish_seen_subcommand_from plan remotes init clone bootstrap localize' -a bootstrap -d 'Bootstrap full local submodule workspace'
complete -c rfm -n '__fish_seen_subcommand_from local; and not __fish_seen_subcommand_from plan remotes init clone bootstrap localize' -a localize -d 'Materialize local workspace'
complete -c rfm -n '__fish_seen_subcommand_from local' -l remotes-dir -r -a '(__fish_complete_directories)' -d 'Local bare remotes directory'
complete -c rfm -n '__fish_seen_subcommand_from local' -l apply -d 'Apply changes'
complete -c rfm -n '__fish_seen_subcommand_from local' -l update-mirrors -d 'Update existing local mirrors'
complete -c rfm -n '__fish_seen_subcommand_from local' -l json -d 'Print JSON output'
complete -c rfm -n '__fish_seen_subcommand_from localize' -l no-set-origin -d 'Keep current root origin'
complete -c rfm -n '__fish_seen_subcommand_from local' -l mirror-sources -d 'Mirror configured source/upstream URLs'
complete -c rfm -n '__fish_seen_subcommand_from remotes' -l seed -d 'Seed empty bare repositories with an initial commit'
complete -c rfm -n '__fish_seen_subcommand_from init' -l with-remotes -d 'Create local bare remotes too'
complete -c rfm -n '__fish_seen_subcommand_from init' -l set-origin -d 'Point origin to local bare remotes'
complete -c rfm -n '__fish_seen_subcommand_from bootstrap' -l set-origin -d 'Point root origin to local bare remote'

complete -c rfm -n '__fish_seen_subcommand_from git; and not __fish_seen_subcommand_from status pull push' -a status -d 'Run git status'
complete -c rfm -n '__fish_seen_subcommand_from git; and not __fish_seen_subcommand_from status pull push' -a pull -d 'Run git pull'
complete -c rfm -n '__fish_seen_subcommand_from git; and not __fish_seen_subcommand_from status pull push' -a push -d 'Run git push'
complete -c rfm -n '__fish_seen_subcommand_from git' -l apply -d 'Apply changes'
complete -c rfm -n '__fish_seen_subcommand_from git' -l no-root -d 'Skip root repository'

complete -c rfm -n '__fish_seen_subcommand_from source; and not __fish_seen_subcommand_from fingerprint' -a fingerprint -d 'Compute source digests'
complete -c rfm -n '__fish_seen_subcommand_from fingerprint' -l write -d 'Write metadata files'

complete -c rfm -n '__fish_seen_subcommand_from compose; and not __fish_seen_subcommand_from ps up down build pull logs' -a ps -d 'Compose ps'
complete -c rfm -n '__fish_seen_subcommand_from compose; and not __fish_seen_subcommand_from ps up down build pull logs' -a up -d 'Compose up'
complete -c rfm -n '__fish_seen_subcommand_from compose; and not __fish_seen_subcommand_from ps up down build pull logs' -a down -d 'Compose down'
complete -c rfm -n '__fish_seen_subcommand_from compose; and not __fish_seen_subcommand_from ps up down build pull logs' -a build -d 'Compose build'
complete -c rfm -n '__fish_seen_subcommand_from compose; and not __fish_seen_subcommand_from ps up down build pull logs' -a pull -d 'Compose pull'
complete -c rfm -n '__fish_seen_subcommand_from compose; and not __fish_seen_subcommand_from ps up down build pull logs' -a logs -d 'Compose logs'
complete -c rfm -n '__fish_seen_subcommand_from compose' -l apply -d 'Apply changes'

complete -c rfm -n '__fish_seen_subcommand_from images; and not __fish_seen_subcommand_from verify' -a verify -d 'Verify image labels'
complete -c rfm -n '__fish_seen_subcommand_from verify' -l json -d 'Print JSON output'

complete -c rfm -n '__fish_seen_subcommand_from docs; and not __fish_seen_subcommand_from validate-links' -a validate-links -d 'Validate Markdown links'
