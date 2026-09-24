# APKO smoke tests

BitcoinAgent pins the APKO smoke-test contract from
[ethereum-optimism/actions@7eaff21e](https://github.com/ethereum-optimism/actions/commit/7eaff21e45042406c7e5602f04bcabe959c36047)
(*ci: run APKO smoke tests with Docker*). That consumer commit pins every
APKO factory stage to
[ethereum-optimism/factory@b87283a8](https://github.com/ethereum-optimism/factory/commit/b87283a8bb6c325da0ef18400eb819b5979a9bd3).

Do not follow `main` blindly. Later factory revisions can change runner
defaults or the smoke loop; this agent stays on the hashes above.

## Why the pin exists

The previous factory revision defaulted amd64 smoke jobs to
`ubuntu-slim`. That runner has the Docker **client** but no **daemon**.
`docker run` then wrote a connection error and exited 1. Exit 1 is not
in the loop's fatal set (`125`, `126`, `127`, `129–159`), so a
non-release job passed without starting the image.

The pinned revision:

1. Defaults amd64 to `ubuntu-24.04` and keeps arm64 on `ubuntu-24.04-arm`.
2. Pulls the image **before** the command loop.
3. Fails if `docker image inspect` reports a different architecture.

An explicit `smoke_runners` entry still wins. An arch the override omits
falls back to the Docker-capable default, not to the overridden value.

## What this agent will do

| Action | How |
| --- | --- |
| Explain the pin | `apko_smoke_overview` |
| Plan smoke legs | `apko_plan_smoke` — `images.apko.json` catalog |
| Check Docker | `apko_docker_status` — client vs daemon |
| Preflight | `apko_smoke_preflight` — pull + arch check |
| Run smoke commands | `apko_smoke_run` — preflight, then the factory loop |

## Limits

- Local Docker only. No GCP Artifact Registry login, no melange build,
  no apko publish, no GitHub Actions workflow added to this tree.
- Image references must be a docker `name[:tag]` or `name@sha256:...`.
- `docker run` is `--rm` with `--platform` and `--entrypoint` only. No
  privileged flags, volume mounts, or host-network.
- Catalog files are local `.json`, 1 MiB max.
- Smoke commands run **inside** the pulled image. They are never executed
  on the host shell.

## Check from this tree (no AWS)

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko plan path/to/images.apko.json
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko status
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko preflight alpine:3.20 amd64
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko run alpine:3.20 amd64 "uname -m"
```
