from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bitcoin_tools import developer_howto
from local_cli import route_query

from apko_smoke import (
    ACTIONS_COMMIT,
    DEFAULT_SMOKE_RUNNERS,
    FACTORY_COMMIT,
    FORBIDDEN_SMOKE_RUNNER,
    apko_from_arg,
    apko_plan_smoke,
    apko_smoke_overview,
    apko_smoke_preflight,
    apko_smoke_run,
    format_smoke_matrix,
    inspect_docker,
    parse_smoke_commands,
    plan_smoke_matrix,
    preflight_image,
    run_smoke_loop,
    smoke_runner,
    validate_image_ref,
)


def _proc(rc: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["docker"], returncode=rc, stdout=stdout, stderr=stderr)


class FakeDocker:
    def __init__(
        self,
        *,
        daemon: bool = True,
        pull_rc: int = 0,
        inspect_arch: str = "amd64",
        inspect_rc: int = 0,
        runs: list[tuple[int, str]] | None = None,
    ) -> None:
        self.daemon = daemon
        self.pull_rc = pull_rc
        self.inspect_arch = inspect_arch
        self.inspect_rc = inspect_rc
        self.runs = list(runs or [(0, "ok\n")])
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if args[:1] == ["info"]:
            if self.daemon:
                return _proc(0, "Server Version: fake\n")
            return _proc(1, stderr="failed to connect to the docker API at unix:///var/run/docker.sock")
        if args[:1] == ["pull"]:
            return _proc(self.pull_rc, stderr="" if self.pull_rc == 0 else "pull failed")
        if args[:2] == ["image", "inspect"]:
            return _proc(self.inspect_rc, stdout=f"{self.inspect_arch}\n")
        if args[:1] == ["run"]:
            if not self.runs:
                return _proc(0, "ok\n")
            rc, output = self.runs.pop(0)
            return _proc(rc, stdout=output)
        return _proc(1, stderr=f"unexpected {args}")


def _catalog(**overrides: object) -> dict:
    data: dict = {
        "apko_archs": "amd64,arm64",
        "images": {
            "widget": {
                "smoke_test": "widget --version",
            }
        },
    }
    data.update(overrides)
    return data


class ApkoSmokeTests(unittest.TestCase):
    def test_overview_pins_both_commits(self) -> None:
        text = apko_smoke_overview()
        self.assertIn(ACTIONS_COMMIT, text)
        self.assertIn(FACTORY_COMMIT, text)
        self.assertIn(DEFAULT_SMOKE_RUNNERS["amd64"], text)
        self.assertIn(FORBIDDEN_SMOKE_RUNNER, text)
        self.assertIn("before the command loop", text)

    def test_howto_apko_topic(self) -> None:
        text = developer_howto("apko")
        self.assertIn(ACTIONS_COMMIT[:7], text)
        self.assertIn("ubuntu-24.04", text)

    def test_smoke_runner_defaults(self) -> None:
        self.assertEqual(smoke_runner("amd64"), "ubuntu-24.04")
        self.assertEqual(smoke_runner("arm64"), "ubuntu-24.04-arm")
        self.assertEqual(smoke_runner("amd64", {}), "ubuntu-24.04")

    def test_smoke_runner_partial_override(self) -> None:
        overrides = {"amd64": "ubuntu-latest"}
        self.assertEqual(smoke_runner("amd64", overrides), "ubuntu-latest")
        self.assertEqual(smoke_runner("arm64", overrides), "ubuntu-24.04-arm")

    def test_plan_defaults_and_skips_empty_smoke(self) -> None:
        matrix = plan_smoke_matrix(
            {
                "images": {
                    "widget": {"smoke_test": "widget --version"},
                    "silent": {},
                }
            }
        )
        self.assertEqual(len(matrix), 2)
        amd = next(leg for leg in matrix if leg["arch"] == "amd64")
        arm = next(leg for leg in matrix if leg["arch"] == "arm64")
        self.assertEqual(amd["runner"], "ubuntu-24.04")
        self.assertEqual(arm["runner"], "ubuntu-24.04-arm")
        self.assertEqual(amd["service"], "widget")
        self.assertTrue(all(leg["service"] != "silent" for leg in matrix))

    def test_plan_partial_override_does_not_capture_other_arch(self) -> None:
        matrix = plan_smoke_matrix(
            {
                "apko_archs": "amd64,arm64",
                "smoke_runners": {"amd64": "ubuntu-latest"},
                "images": {"widget": {"smoke_test": "widget --help"}},
            }
        )
        runners = {leg["arch"]: leg["runner"] for leg in matrix}
        self.assertEqual(runners["amd64"], "ubuntu-latest")
        self.assertEqual(runners["arm64"], "ubuntu-24.04-arm")

    def test_plan_respects_per_image_archs(self) -> None:
        matrix = plan_smoke_matrix(
            {
                "apko_archs": "amd64,arm64",
                "images": {
                    "only-amd": {"smoke_test": "true", "apko_archs": "amd64"},
                },
            }
        )
        self.assertEqual([leg["arch"] for leg in matrix], ["amd64"])

    def test_format_warns_on_ubuntu_slim(self) -> None:
        text = format_smoke_matrix(
            [
                {
                    "service": "widget",
                    "arch": "amd64",
                    "runner": "ubuntu-slim",
                    "expected_version": "",
                    "smoke_test": "true",
                }
            ]
        )
        self.assertIn("ubuntu-slim", text)
        self.assertIn("WARNING", text)

    def test_plan_tool_reads_catalog_file(self) -> None:
        catalog = _catalog()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "images.apko.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            text = apko_plan_smoke(str(path))
        self.assertIn("2 smoke leg(s)", text)
        self.assertIn("ubuntu-24.04", text)
        self.assertIn(FACTORY_COMMIT[:7], text)

    def test_plan_rejects_missing_catalog(self) -> None:
        self.assertIn("catalog not found", apko_plan_smoke("/no/such/images.apko.json"))

    def test_validate_image_ref(self) -> None:
        self.assertEqual(validate_image_ref("alpine:3.20"), "alpine:3.20")
        self.assertEqual(
            validate_image_ref("ghcr.io/org/app@sha256:" + "ab" * 32),
            "ghcr.io/org/app@sha256:" + "ab" * 32,
        )
        with self.assertRaises(Exception):
            validate_image_ref("alpine:3.20; rm -rf /")
        with self.assertRaises(Exception):
            validate_image_ref("alpine:3.20 && reboot")

    def test_parse_smoke_commands(self) -> None:
        self.assertEqual(
            parse_smoke_commands("node --version, widget --help"),
            [["node", "--version"], ["widget", "--help"]],
        )
        self.assertEqual(parse_smoke_commands("  ,  "), [])

    def test_inspect_docker_reports_no_daemon(self) -> None:
        status = inspect_docker(FakeDocker(daemon=False))
        self.assertTrue(status["client"])
        self.assertFalse(status["daemon"])
        self.assertIn("ubuntu-slim", str(status["detail"]))

    def test_preflight_fails_without_daemon(self) -> None:
        with self.assertRaises(Exception) as ctx:
            preflight_image("alpine:3.20", "amd64", FakeDocker(daemon=False))
        self.assertIn("no Docker daemon", str(ctx.exception))
        self.assertIn("ubuntu-slim", str(ctx.exception))

    def test_preflight_fails_on_pull_error(self) -> None:
        docker = FakeDocker(pull_rc=1)
        with self.assertRaises(Exception) as ctx:
            preflight_image("alpine:3.20", "amd64", docker)
        self.assertIn("docker pull", str(ctx.exception))
        self.assertTrue(any(call[:1] == ["pull"] for call in docker.calls))
        self.assertFalse(any(call[:1] == ["run"] for call in docker.calls))

    def test_preflight_fails_on_arch_mismatch_before_run(self) -> None:
        docker = FakeDocker(inspect_arch="arm64")
        with self.assertRaises(Exception) as ctx:
            preflight_image("alpine:3.20", "amd64", docker)
        self.assertIn("is arm64 but this runner is amd64", str(ctx.exception))
        self.assertFalse(any(call[:1] == ["run"] for call in docker.calls))

    def test_preflight_ok(self) -> None:
        info = preflight_image("alpine:3.20", "amd64", FakeDocker())
        self.assertEqual(info["pulled_arch"], "amd64")

    def test_run_loop_fatal_exit_before_version(self) -> None:
        docker = FakeDocker(runs=[(126, "exec format error\n")])
        with self.assertRaises(Exception) as ctx:
            run_smoke_loop("alpine:3.20", "amd64", "widget --version", docker=docker)
        self.assertIn("could not run (exit 126)", str(ctx.exception))

    def test_run_loop_tolerates_process_exit_1(self) -> None:
        docker = FakeDocker(runs=[(1, "usage: widget\n")])
        text = run_smoke_loop("alpine:3.20", "amd64", "widget --help", docker=docker)
        self.assertIn("Smoke OK", text)
        self.assertIn("tolerated", text)

    def test_run_loop_requires_expected_version(self) -> None:
        docker = FakeDocker(runs=[(0, "widget 1.2.3\n")])
        with self.assertRaises(Exception) as ctx:
            run_smoke_loop(
                "alpine:3.20",
                "amd64",
                "widget --version",
                expected_version="v9.9.9",
                docker=docker,
            )
        self.assertIn("expected version v9.9.9", str(ctx.exception))

        docker = FakeDocker(runs=[(0, "widget 1.2.3\n")])
        text = run_smoke_loop(
            "alpine:3.20",
            "amd64",
            "widget --version",
            expected_version="v1.2.3",
            docker=docker,
        )
        self.assertIn("Version OK", text)

    def test_run_uses_safe_docker_flags(self) -> None:
        docker = FakeDocker(runs=[(0, "x86_64\n")])
        run_smoke_loop("alpine:3.20", "amd64", "uname -m", docker=docker)
        run_calls = [call for call in docker.calls if call[:1] == ["run"]]
        self.assertEqual(len(run_calls), 1)
        argv = run_calls[0]
        self.assertIn("--rm", argv)
        self.assertIn("--platform", argv)
        self.assertIn("--entrypoint", argv)
        self.assertNotIn("--privileged", argv)
        self.assertNotIn("-v", argv)
        self.assertNotIn("--network=host", argv)

    def test_tool_wrappers_return_strings(self) -> None:
        docker = FakeDocker()
        with patch("apko_smoke._default_docker", return_value=docker):
            text = apko_smoke_preflight("alpine:3.20", "amd64")
            self.assertIn("Preflight OK", text)
            ran = apko_smoke_run("alpine:3.20", "amd64", "true")
            self.assertIn("Smoke OK", ran)
            failed = apko_smoke_preflight("alpine:3.20; rm -rf /", "amd64")
            self.assertIn("refusing image reference", failed)

    def test_cli_overview_and_plan(self) -> None:
        self.assertIn(ACTIONS_COMMIT, apko_from_arg(""))
        self.assertIn(ACTIONS_COMMIT, route_query("apko"))
        self.assertIn(ACTIONS_COMMIT, route_query("what is apko smoke"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "images.apko.json"
            path.write_text(json.dumps(_catalog()), encoding="utf-8")
            text = route_query(f"apko plan {path}")
        self.assertIn("widget", text)
        self.assertIn("ubuntu-24.04-arm", text)

    def test_cli_run_and_help(self) -> None:
        docker = FakeDocker(runs=[(0, "ok\n")])
        with patch("apko_smoke._default_docker", return_value=docker):
            text = route_query("apko run alpine:3.20 amd64 uname -m")
        self.assertIn("Smoke OK", text)
        help_text = route_query("help")
        self.assertIn("apko", help_text)
        howto = route_query("howto apko")
        self.assertIn("7eaff21", howto)


if __name__ == "__main__":
    unittest.main()
