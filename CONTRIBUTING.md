# Contributing to OmaTrophy

Thanks for helping. OmaTrophy is a small project; issues and focused pull
requests are welcome. Support for another game store is the most useful
contribution: see [adding a store](docs/guide/stores.md).

## Before you start

- Bugs and ideas: open an issue first for anything larger than a small fix.
- Security problems: follow [SECURITY.md](SECURITY.md), not a public issue.
- Read [AGENTS.md](AGENTS.md): it holds the code rules for people and coding
  agents alike, and [docs/architecture.md](docs/architecture.md).

## Set up

```sh
git clone https://github.com/mateuspim/omatrophy.git
ln -s "$PWD/omatrophy" ~/.config/omarchy/plugins/pym.omatrophy
cd omatrophy
omarchy plugin validate .
omarchy-shell shell rescanPlugins
omarchy plugin enable pym.omatrophy
```

Details, previews and releases are in the
[development runbook](docs/runbooks/development.md).

## Make a change

1. Branch from `master`.
2. Keep the change focused; update the README section or doc it affects.
3. Add or update tests. Run `python3 -m unittest discover -s tests` and
   `omarchy plugin validate .`.
4. For UI changes, attach a capture from `dev/preview.sh` with sample data,
   never a desktop screenshot with personal data.
5. Durable design choice? Add an ADR under [docs/adr](docs/adr/README.md).

## Commit style

Plain imperative subject ("Add …", "Keep …"), under ~72 characters, and a
body that explains why.

## Pull request checklist

- [ ] Tests pass and `omarchy plugin validate .` exits 0
- [ ] Docs and CHANGELOG (Unreleased) updated
- [ ] No personal paths, account ids or screenshots in tracked files

## License

By contributing you agree your work is released under the [MIT License](LICENSE).
