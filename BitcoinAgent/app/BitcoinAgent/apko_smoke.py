"""APKO smoke-test tools pinned to ethereum-optimism/actions@7eaff21e.

That consumer commit pins factory APKO stages to
b87283a8bb6c325da0ef18400eb819b5979a9bd3 so amd64 smoke jobs get a Docker
daemon and fail before the command loop when image pull or architecture
validation fails.

This module reimplements the planner's smoke-runner defaults and the
smoke-test preflight + command loop. It does not vendor factory bash, run
melange, publish images, or talk to GCP Artifact Registry.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from optional_tool import tool

ACTIONS_COMMIT = "7eaff21e45042406c7e5602f04bcabe959c36047"
FACTORY_COMMIT = "b87283a8bb6c325da0ef18400eb819b5979a9bd3"
ACTIONS_REPO = "https://github.com/ethereum-optimism/actions"
FACTORY_REPO = "https://github.com/ethereum-optimism/factory"
ACTIONS_COMMIT_URL = f"{ACTIONS_REPO}/commit/{ACTIONS_COMMIT}"
FACTORY_COMMIT_URL = f"{FACTORY_REPO}/commit/{FACTORY_COMMIT}"
FACTORY_SMOKE_WORKFLOW = (
    f"{FACTORY_REPO}/blob/{FACTORY_COMMIT}/.github/workflows/apko-smoke-test.yaml"
)

DEFAULT_SMOKE_RUNNERS = {
    "amd64": "ubuntu-24.04",
    "arm64": "ubuntu-24.04-arm",
}
FORBIDDEN_SMOKE_RUNNER = "ubuntu-slim"
SUPPORTED_ARCHES = ("amd64", "arm64")
FATAL_DOCKER_EXIT = frozenset({125, 126, 127, *range(129, 160)})

_IMAGE_REF = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9._-]*[a-zA-Z0-9])?(?::[0-9]+)?/)?"
    r"[a-zA-Z0-9][a-zA-Z0-9._/-]*"
    r"(?::[a-zA-Z0-9_][a-zA-Z0-9._-]*)?"
    r"(?:@sha256:[0-9a-f]{64})?$"
)
_CATALOG_MAX_BYTES = 1_048_576
_DOCKER_INFO_TIMEOUT = 10
_DOCKER_PULL_TIMEOUT = 120
_DOCKER_RUN_TIMEOUT = 60

DockerFn = Callable[[list[str], int], subprocess.CompletedProcess[str]]


class SmokeError(ValueError):
    """User-facing failure for catalog, image, or Docker preflight."""


def smoke_runner(arch: str, smoke_runners: dict[str, str] | None = None) -> str:
    """Return the GitHub runner label for one smoke arch.

    Matches factory `apko-plan.sh` at the pinned revision: an explicit
    `smoke_runners` entry wins; an omitted arch falls back to the
    Docker-capable default (amd64 → ubuntu-24.04, arm64 → ubuntu-24.04-arm).
    """
    wanted = (arch or "").strip().lower()
    overrides = smoke_runners or {}
    explicit = str(overrides.get(wanted) or "").strip()
    if explicit:
        return explicit
    return DEFAULT_SMOKE_RUNNERS.get(wanted, DEFAULT_SMOKE_RUNNERS["amd64"])


def normalize_arch(arch: str, default: str = "amd64") -> str:
    raw = (arch or "").strip().lower()
    if not raw:
        return default
    aliases = {"x86_64": "amd64", "x64": "amd64", "aarch64": "arm64", "arm": "arm64"}
    wanted = aliases.get(raw, raw)
    if wanted not in SUPPORTED_ARCHES:
        raise SmokeError(f"unsupported smoke arch {arch!r}; use amd64 or arm64")
    return wanted


def parse_arch_list(raw: str) -> list[str]:
    parts = [part.strip() for part in (raw or "").split(",")]
    arches = [normalize_arch(part) for part in parts if part]
    if not arches:
        return ["amd64", "arm64"]
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    unique: list[str] = []
    for arch in arches:
        if arch not in seen:
            seen.add(arch)
            unique.append(arch)
    return unique


def parse_smoke_commands(smoke_test: str) -> list[list[str]]:
    """Split a comma-separated smoke_test string into entrypoint + args."""
    commands: list[list[str]] = []
    for chunk in (smoke_test or "").split(","):
        parts = chunk.split()
        if parts:
            commands.append(parts)
    return commands


def validate_image_ref(image: str) -> str:
    ref = (image or "").strip()
    if not ref:
        raise SmokeError("Provide an image reference: apko preflight alpine:3.20 amd64")
    if len(ref) > 256 or not _IMAGE_REF.fullmatch(ref):
        raise SmokeError(
            f"refusing image reference {image!r}. Use a docker name[:tag] "
            "or name@sha256:... without shell metacharacters."
        )
    return ref


def _load_catalog(path: str) -> tuple[Path, dict]:
    raw = (path or "").strip()
    if not raw:
        raise SmokeError("Provide a catalog path: apko plan .github/images.apko.json")
    catalog = Path(raw).expanduser()
    if not catalog.is_file():
        raise SmokeError(f"catalog not found: {catalog}")
    if catalog.suffix.lower() != ".json":
        raise SmokeError(f"catalog must be a .json file: {catalog}")
    size = catalog.stat().st_size
    if size > _CATALOG_MAX_BYTES:
        raise SmokeError(f"catalog is {size} bytes; max is {_CATALOG_MAX_BYTES}")
    try:
        data = json.loads(catalog.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SmokeError(f"catalog is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("images"), dict):
        raise SmokeError("catalog must be an object with an images map")
    return catalog, data


def _image_archs(image: dict, catalog: dict) -> str:
    for key in ("apko_archs", "archs"):
        value = image.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list) and value:
            return ",".join(str(item) for item in value)
    catalog_archs = catalog.get("apko_archs", "amd64,arm64")
    if isinstance(catalog_archs, list):
        return ",".join(str(item) for item in catalog_archs)
    return str(catalog_archs or "amd64,arm64")


def plan_smoke_matrix(catalog: dict) -> list[dict[str, str]]:
    """Build the factory smoke matrix from an images.apko.json catalog."""
    images = catalog.get("images") or {}
    if not isinstance(images, dict):
        raise SmokeError("catalog images must be an object")
    overrides_raw = catalog.get("smoke_runners") or {}
    if overrides_raw and not isinstance(overrides_raw, dict):
        raise SmokeError("catalog smoke_runners must be an object")
    overrides = {str(key): str(value) for key, value in dict(overrides_raw).items()}

    matrix: list[dict[str, str]] = []
    for name, image in images.items():
        if not isinstance(image, dict):
            continue
        smoke_test = str(image.get("smoke_test") or "").strip()
        if not smoke_test:
            continue
        expected = str(image.get("expected_version") or "").strip()
        for arch in parse_arch_list(_image_archs(image, catalog)):
            runner = smoke_runner(arch, overrides)
            matrix.append(
                {
                    "service": str(name),
                    "arch": arch,
                    "runner": runner,
                    "expected_version": expected,
                    "smoke_test": smoke_test,
                }
            )
    return matrix


def format_smoke_matrix(matrix: list[dict[str, str]], catalog_path: Path | None = None) -> str:
    header = [
        f"APKO smoke plan (factory @{FACTORY_COMMIT[:7]}, actions @{ACTIONS_COMMIT[:7]})",
    ]
    if catalog_path is not None:
        header.append(f"Catalog: {catalog_path}")
    header.append(f"{len(matrix)} smoke leg(s)")
    if not matrix:
        header.append("No images declared a smoke_test.")
        return "\n".join(header)

    lines = header[:]
    slim = [leg for leg in matrix if leg["runner"] == FORBIDDEN_SMOKE_RUNNER]
    if slim:
        names = ", ".join(sorted({leg["service"] for leg in slim}))
        lines.append(
            f"WARNING: {len(slim)} leg(s) still use {FORBIDDEN_SMOKE_RUNNER} "
            f"({names}). That runner has a Docker client but no daemon, so "
            f"the command loop can pass without starting the image."
        )
    for leg in matrix:
        expected = leg["expected_version"] or "(none)"
        note = ""
        if leg["runner"] == FORBIDDEN_SMOKE_RUNNER:
            note = "  [no docker daemon]"
        elif (
            leg["arch"] == "amd64"
            and leg["runner"] == DEFAULT_SMOKE_RUNNERS["amd64"]
        ) or (
            leg["arch"] == "arm64"
            and leg["runner"] == DEFAULT_SMOKE_RUNNERS["arm64"]
        ):
            note = "  [docker-capable default]"
        lines.append(
            f"- {leg['service']} {leg['arch']} on {leg['runner']}{note}\n"
            f"  smoke_test: {leg['smoke_test']}\n"
            f"  expected_version: {expected}"
        )
    return "\n".join(lines)


def _default_docker() -> DockerFn:
    def run(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    return run


def docker_client_path() -> str | None:
    return shutil.which("docker")


def inspect_docker(docker: DockerFn | None = None) -> dict[str, str | bool]:
    """Report whether the Docker client can reach a daemon."""
    run = docker or _default_docker()
    client = docker_client_path()
    if docker is None and not client:
        return {
            "client": False,
            "daemon": False,
            "detail": "docker is not on PATH. The smoke test cannot run.",
        }
    try:
        info = run(["info"], _DOCKER_INFO_TIMEOUT)
    except FileNotFoundError:
        return {
            "client": False,
            "daemon": False,
            "detail": "docker is not installed. The smoke test cannot run.",
        }
    except subprocess.TimeoutExpired:
        return {
            "client": True,
            "daemon": False,
            "detail": "docker info timed out; treat this as no reachable daemon.",
        }
    detail = (info.stderr or info.stdout or "").strip()
    if info.returncode != 0:
        lowered = detail.lower()
        if "cannot connect" in lowered or "docker.sock" in lowered or "daemon" in lowered:
            detail = (
                "Docker client is present but no daemon is reachable "
                "(the ubuntu-slim failure mode). Pull/arch preflight would "
                "fail here instead of letting the command loop pass."
            )
        return {"client": True, "daemon": False, "detail": detail}
    return {"client": True, "daemon": True, "detail": "Docker daemon is reachable."}


def _combined_output(proc: subprocess.CompletedProcess[str]) -> str:
    parts = [proc.stdout or "", proc.stderr or ""]
    return "".join(parts)


def preflight_image(
    image: str,
    arch: str,
    docker: DockerFn | None = None,
    *,
    skip_pull: bool = False,
) -> dict[str, str]:
    """Pull the image and verify its architecture before any smoke command.

    A runner that cannot pull, or that pulled a foreign arch, must fail
    here. Inside the command loop docker's own errors are captured as
    output and only a narrow set of exit codes is fatal.
    """
    ref = validate_image_ref(image)
    wanted = normalize_arch(arch)
    run = docker or _default_docker()
    status = inspect_docker(run)
    if not status["daemon"]:
        raise SmokeError(
            "FAIL: no Docker daemon. amd64 smoke jobs must run on a "
            f"daemon-capable runner (default {DEFAULT_SMOKE_RUNNERS['amd64']}, "
            f"not {FORBIDDEN_SMOKE_RUNNER}). {status['detail']}"
        )

    if not skip_pull:
        try:
            pull = run(["pull", "--platform", f"linux/{wanted}", ref], _DOCKER_PULL_TIMEOUT)
        except subprocess.TimeoutExpired as exc:
            raise SmokeError(f"FAIL: docker pull timed out for {ref}") from exc
        if pull.returncode != 0:
            output = _combined_output(pull).strip() or f"exit {pull.returncode}"
            raise SmokeError(f"FAIL: docker pull --platform linux/{wanted} {ref}\n{output}")

    try:
        inspect = run(
            ["image", "inspect", "--format", "{{.Architecture}}", ref],
            _DOCKER_INFO_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise SmokeError(f"FAIL: docker image inspect timed out for {ref}") from exc
    pulled_arch = (inspect.stdout or "").strip()
    if inspect.returncode != 0 or not pulled_arch:
        output = _combined_output(inspect).strip() or f"exit {inspect.returncode}"
        raise SmokeError(f"FAIL: could not inspect {ref}\n{output}")
    if pulled_arch != wanted:
        raise SmokeError(
            f"FAIL: {ref} is {pulled_arch} but this runner is {wanted}; "
            "the image cannot execute here"
        )
    return {"image": ref, "arch": wanted, "pulled_arch": pulled_arch}


def run_smoke_loop(
    image: str,
    arch: str,
    smoke_test: str,
    expected_version: str = "",
    docker: DockerFn | None = None,
    *,
    skip_pull: bool = False,
) -> str:
    """Run factory smoke commands after a successful pull + arch preflight."""
    ref_info = preflight_image(image, arch, docker, skip_pull=skip_pull)
    ref = ref_info["image"]
    wanted = ref_info["arch"]
    commands = parse_smoke_commands(smoke_test)
    if not commands:
        raise SmokeError("Provide at least one smoke command, e.g. 'node --version'")

    run = docker or _default_docker()
    normalized_version = expected_version.lstrip("v")
    version_matched = False
    blocks = [
        f"APKO smoke (factory @{FACTORY_COMMIT[:7]})",
        f"Image: {ref}",
        f"Arch: {wanted} (pulled {ref_info['pulled_arch']})",
        f"Preflight: docker pull --platform linux/{wanted} + arch check OK",
    ]

    for parts in commands:
        entrypoint, args = parts[0], parts[1:]
        argv = [
            "run",
            "--rm",
            "--platform",
            f"linux/{wanted}",
            "--entrypoint",
            entrypoint,
            ref,
            *args,
        ]
        display_args = " ".join(args)
        blocks.append(f"==> docker run --platform linux/{wanted} --entrypoint {entrypoint} ... {display_args}".rstrip())
        try:
            proc = run(argv, _DOCKER_RUN_TIMEOUT)
        except subprocess.TimeoutExpired as exc:
            raise SmokeError(f"FAIL: {entrypoint} timed out") from exc
        output = _combined_output(proc)
        if output:
            blocks.append(output.rstrip())
        if normalized_version and normalized_version in output:
            version_matched = True
        if proc.returncode in FATAL_DOCKER_EXIT:
            raise SmokeError(f"FAIL: {entrypoint} could not run (exit {proc.returncode})")
        if proc.returncode != 0:
            blocks.append(f"(exit {proc.returncode} tolerated by the factory loop)")

    if normalized_version and not version_matched:
        raise SmokeError(f"FAIL: no smoke command reported expected version {expected_version}")
    if normalized_version:
        blocks.append(f"Version OK: {expected_version}")
    blocks.append("Smoke OK")
    return "\n".join(blocks)


def overview_text() -> str:
    return (
        "APKO smoke tests at ethereum-optimism/actions@"
        f"{ACTIONS_COMMIT[:7]} pin factory @{FACTORY_COMMIT[:7]}.\n"
        f"Consumer: {ACTIONS_COMMIT_URL}\n"
        f"Factory:  {FACTORY_COMMIT_URL}\n"
        f"Workflow: {FACTORY_SMOKE_WORKFLOW}\n"
        "\n"
        "The previous factory revision defaulted amd64 smoke jobs to "
        f"{FORBIDDEN_SMOKE_RUNNER}, which has a Docker client but no daemon. "
        "docker run then exited 1 (tolerated by the command loop) and a "
        "non-release job passed without starting the image.\n"
        "\n"
        "This pin:\n"
        f"- defaults amd64 → {DEFAULT_SMOKE_RUNNERS['amd64']} "
        f"and arm64 → {DEFAULT_SMOKE_RUNNERS['arm64']}\n"
        "- pulls the image before the command loop\n"
        "- fails if the pulled architecture does not match the runner\n"
        "- still treats docker-client exits 125/126/127/129-159 as fatal "
        "inside the loop; other process exits are tolerated unless "
        "expected_version is set and missing from output\n"
        "\n"
        "This agent plans a catalog smoke matrix and can run the same "
        "preflight + loop against a local Docker daemon. It does not "
        "build with melange, publish with apko, or log in to Artifact "
        "Registry.\n"
        "\n"
        "Local:\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko plan "
        ".github/images.apko.json\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko status\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko preflight "
        "alpine:3.20 amd64\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko run "
        "alpine:3.20 amd64 \"uname -m\"\n"
        "See BitcoinAgent/APKO.md."
    )


def _format_status(status: dict[str, str | bool]) -> str:
    client = "yes" if status["client"] else "no"
    daemon = "yes" if status["daemon"] else "no"
    return (
        f"APKO docker status (factory @{FACTORY_COMMIT[:7]})\n"
        f"Client: {client}\n"
        f"Daemon: {daemon}\n"
        f"{status['detail']}"
    )


def _default_catalog_path() -> str:
    env = os.environ.get("APKO_CATALOG")
    if env:
        return env
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".github" / "images.apko.json"
        if candidate.is_file():
            return str(candidate)
    return ""


@tool
def apko_smoke_overview() -> str:
    """Explain the pinned APKO smoke-test contract (Docker daemon + preflight).

    Use when the user asks about APKO, melange smoke tests, ubuntu-slim
    false greens, or ethereum-optimism/actions@7eaff21e.
    """
    return overview_text()


@tool
def apko_plan_smoke(catalog_path: str = "") -> str:
    """Plan APKO smoke legs from an images.apko.json catalog.

    Uses the factory@b87283a8 defaults: amd64 → ubuntu-24.04,
    arm64 → ubuntu-24.04-arm. Explicit smoke_runners win; an omitted
    arch falls back to the default. Images without smoke_test are skipped.
    """
    path = (catalog_path or "").strip() or _default_catalog_path()
    try:
        catalog_file, catalog = _load_catalog(path)
        matrix = plan_smoke_matrix(catalog)
        return format_smoke_matrix(matrix, catalog_file)
    except SmokeError as exc:
        return str(exc)


@tool
def apko_docker_status() -> str:
    """Check whether a local Docker daemon is reachable for APKO smoke tests.

    ubuntu-slim has the client but no daemon; this tool reports that failure
    mode instead of treating a later docker run exit 1 as a passing smoke.
    """
    return _format_status(inspect_docker())


@tool
def apko_smoke_preflight(image: str, arch: str = "amd64") -> str:
    """Pull an image and verify its architecture before any smoke command.

    Fails if there is no Docker daemon, the pull fails, or the pulled
    architecture does not match amd64/arm64. Matches factory preflight at
    b87283a8.
    """
    try:
        info = preflight_image(image, arch)
    except SmokeError as exc:
        return str(exc)
    return (
        f"Preflight OK (factory @{FACTORY_COMMIT[:7]})\n"
        f"Image: {info['image']}\n"
        f"Requested arch: {info['arch']}\n"
        f"Pulled arch: {info['pulled_arch']}"
    )


@tool
def apko_smoke_run(image: str, arch: str = "amd64", smoke_test: str = "", expected_version: str = "") -> str:
    """Run APKO smoke commands after pull + architecture preflight.

    smoke_test is a comma-separated list of container commands
    (entrypoint + args). Docker-client exits 125/126/127/129-159 fail the
    job. Other process exits are tolerated unless expected_version is set
    and no command output contains it. No privileged flags, mounts, or
    host-network. The container is removed after each command.
    """
    try:
        return run_smoke_loop(image, arch, smoke_test, expected_version)
    except SmokeError as exc:
        return str(exc)


def apko_from_arg(text: str) -> str:
    """Route a local-CLI argument string onto the APKO smoke tools."""
    raw = (text or "").strip()
    lower = raw.lower()
    if not raw or lower in {"overview", "help", "docs"}:
        return apko_smoke_overview()
    if re.search(r"^(status|docker|daemon)\b", lower):
        return apko_docker_status()

    plan_match = re.match(r"^(plan|matrix)\b(?:\s+(.*))?$", raw, re.I)
    if plan_match:
        return apko_plan_smoke(plan_match.group(2) or "")

    pre_match = re.match(r"^(preflight|pull)\b(?:\s+(.*))?$", raw, re.I)
    if pre_match:
        tokens = (pre_match.group(2) or "").split()
        image = tokens[0] if tokens else ""
        arch = tokens[1] if len(tokens) > 1 else "amd64"
        return apko_smoke_preflight(image, arch)

    run_match = re.match(r"^(run|smoke|test)\b(?:\s+(.*))?$", raw, re.I)
    if run_match:
        rest = (run_match.group(2) or "").strip()
        return _run_from_rest(rest)

    if lower.startswith(".github/") or lower.endswith(".json"):
        return apko_plan_smoke(raw)
    return apko_smoke_overview()


def _run_from_rest(rest: str) -> str:
    if not rest:
        return "Provide an image and command: apko run alpine:3.20 amd64 \"uname -m\""
    tokens = rest.split()
    image = tokens[0]
    idx = 1
    arch = "amd64"
    if idx < len(tokens) and tokens[idx].lower() in {*SUPPORTED_ARCHES, "x86_64", "aarch64"}:
        arch = tokens[idx]
        idx += 1
    expected = ""
    command_tokens = tokens[idx:]
    if command_tokens and command_tokens[-1].startswith("expected="):
        expected = command_tokens[-1].split("=", 1)[1]
        command_tokens = command_tokens[:-1]
    smoke_test = " ".join(command_tokens)
    return apko_smoke_run(image, arch, smoke_test, expected)
