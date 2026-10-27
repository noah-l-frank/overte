#!/usr/bin/env python3
"""Pure launcher contracts; no Docker daemon, candidate tests or network calls."""
import importlib.util
import os
from pathlib import Path
import subprocess
import socket
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pr_ci_run_under_test",
    ROOT / "tools/repository-checks/pr_ci_run.py")
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


class DockerCommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pr-ci-run-pure-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        git = self.candidate / ".git"
        (git / "objects").mkdir(parents=True)
        (git / "refs").mkdir()
        (git / "config").write_text("[core]\n repositoryformatversion = 0\n")
        self.tools = self.root / "prepared-tools"
        (self.tools / "bin").mkdir(parents=True)
        self.uid = patch.object(R.os, "getuid", return_value=1000)
        self.gid = patch.object(R.os, "getgid", return_value=1000)
        self.uid.start(); self.gid.start()
        self.addCleanup(self.uid.stop); self.addCleanup(self.gid.stop)
        # The isolated runner has no host passwd database. Give this fixture an
        # owned home instead of depending on the workstation's NSS lookup.
        self.clean_env = patch.dict(os.environ, {"HOME": str(self.root)}, clear=True)
        self.clean_env.start(); self.addCleanup(self.clean_env.stop)
        # Command assembly uses explicit public tool facts, including during a
        # controller rollout inside an older boundary with no awk alternative.
        # The real resolver is tested separately against controlled paths.
        self.resolve_public_aliases = R._public_tool_aliases
        self.alias_fixture = ["--symlink", "/usr/bin/prepared-awk", "/etc/alternatives/awk"]
        self.aliases = patch.object(R, "_public_tool_aliases", return_value=self.alias_fixture)
        self.aliases.start(); self.addCleanup(self.aliases.stop)

    def command(self, command=None, **kwargs):
        return R.docker_command(self.candidate, command or ["python3", "tests/one.py"], **kwargs)

    def mounts(self, argv):
        return [argv[i + 1] for i, word in enumerate(argv) if word == "--mount"]

    def environment(self, argv):
        start = argv.index(R.IMAGE) + 3
        values = {}
        while start < len(argv) and "=" in argv[start]:
            name, value = argv[start].split("=", 1)
            values[name] = value
            start += 1
        return values

    def test_only_candidate_is_writable_and_exact_runtime_roots_are_readonly(self):
        argv = self.command(prepared_roots=[self.tools])
        mounts = self.mounts(argv)
        self.assertIn("type=bind,source=/usr,target=/usr,readonly,bind-propagation=rprivate", mounts)
        self.assertIn("type=bind,source=" + str(self.tools) + ",target=" + str(self.tools)
                      + ",readonly,bind-propagation=rprivate", mounts)
        self.assertIn("type=bind,source=" + str(self.candidate / ".git")
                      + ",target=/work/.git,readonly,bind-propagation=rprivate", mounts)
        writable = [value for value in mounts if ",readonly," not in value]
        self.assertEqual(["type=bind,source=" + str(self.candidate)
                          + ",target=/work,bind-propagation=rprivate"], writable)
        self.assertFalse(any("docker.sock" in value for value in mounts))
        for private in (str(Path.home()), str(ROOT), "/run", "/var/run", "/tmp"):
            self.assertFalse(any("source=" + private + "," in value for value in mounts))

    def test_default_security_and_resource_limits_cannot_be_argv_options(self):
        argv = self.command(["python3", "script.py", "--privileged", "--network=host"])
        for value in ("--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
                      "--user=1000:1000", "--network=none", "--ipc=private",
                      "--cgroupns=private", "--pids-limit=512", "--memory=8g", "--memory-swap=8g",
                      "--cpus=4", "--pull=never", "--ulimit=core=0"):
            self.assertIn(value, argv[:argv.index(R.IMAGE)])
        self.assertEqual(["python3", "script.py", "--privileged", "--network=host"], argv[-4:])
        self.assertFalse(any("unconfined" in value for value in argv))
        self.assertFalse(any(value.startswith("--pid=") for value in argv))
        self.assertNotIn("--init", argv)

    def test_invoked_venv_is_readonly_even_when_python_S_uses_base_prefix(self):
        venv = self.root / "actual-venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = /usr/bin\n")
        (venv / "bin/python").symlink_to(R.sys.executable)
        ambient = self.root / "foreign-ambient-env"
        ambient.mkdir()
        with patch.object(R.sys, "executable", str(venv / "bin/python")), \
                patch.object(R.sys, "prefix", R.sys.base_prefix), \
                patch.dict(os.environ, {"VIRTUAL_ENV": str(ambient)}):
            argv = self.command()
            mounts = self.mounts(argv)
        self.assertIn("type=bind,source=" + str(venv) + ",target=" + str(venv)
                      + ",readonly,bind-propagation=rprivate", mounts)
        self.assertFalse(any(str(ambient) in value for value in mounts))
        self.assertEqual(str(venv / "bin"), self.environment(argv)["PATH"].split(":")[0])

    def test_namespace_boundary_is_explicit_offline_and_has_private_filesystem(self):
        argv = R.namespace_command(self.candidate, ["python3", "one.py"], prepared_roots=[self.tools])
        for flag in ("--unshare-all", "--new-session", "--die-with-parent", "--clearenv"):
            self.assertIn(flag, argv)
        self.assertNotIn("--share-net", argv)
        self.assertNotIn("--dev-bind", argv)
        self.assertNotIn("--cap-add", argv)
        self.assertNotIn("--unshare-user-try", argv)
        self.assertIn(self.alias_fixture, [argv[i:i + 3] for i in range(len(argv) - 2)])
        self.assertGreater(argv.index("--nproc=512:512"), argv.index(R.BWRAP))
        self.assertIn("--as=" + str(128 * 1024 ** 3), argv)
        ro = [argv[index + 1:index + 3] for index, word in enumerate(argv) if word == "--ro-bind"]
        self.assertIn([str(self.candidate / ".git"), "/work/.git"], ro)
        self.assertIn(["/usr", "/usr"], ro)
        self.assertIn([str(self.tools), str(self.tools)], ro)
        self.assertNotIn([str(Path.home()), str(Path.home())], ro)
        self.assertIn(["--remount-ro", "/"], [argv[i:i + 2] for i in range(len(argv) - 1)])
        public = {}
        for destination, name in (("/etc/resolv.conf", "resolver"), ("/etc/hosts", "hosts"),
                                  ("/etc/ssl/certs/ca-certificates.crt", "ca"), ("/etc/ssl/cert.pem", "ca")):
            fixture = self.root / name
            fixture.write_text("public test configuration\n")
            public[destination] = fixture
        real_resolve = Path.resolve
        def fixture_resolve(path, *args, **kwargs):
            return real_resolve(public.get(str(path), path), *args, **kwargs)
        with patch.object(Path, "resolve", fixture_resolve):
            fetch = R.namespace_command(self.candidate, ["npm", "ci"], network=True)
        self.assertIn("--share-net", fetch)
        bindings = [fetch[index + 1:index + 3] for index, word in enumerate(fetch) if word == "--ro-bind"]
        self.assertTrue({"/etc/hosts", "/etc/resolv.conf", "/etc/ssl/certs/ca-certificates.crt"}
                        <= {destination for source, destination in bindings})
        self.assertNotIn(["/etc", "/etc"], bindings)
        for invalid in (None, 1, "host"):
            with self.subTest(network=invalid), self.assertRaises(R.RunError):
                R.namespace_command(self.candidate, ["python3"], network=invalid)
        with patch.object(R.subprocess, "run", return_value=subprocess.CompletedProcess([], 19)) as call:
            self.assertEqual(19, R.run(self.candidate, ["python3", "one.py"], boundary="user-namespace"))
        self.assertEqual(1, call.call_count)
        self.assertEqual(R.PRLIMIT, call.call_args.args[0][0])
        self.assertEqual({"PATH", "LANG", "LC_ALL"}, set(call.call_args.kwargs["env"]))

    def test_public_tool_alternatives_preserve_only_usr_targets(self):
        aliases = {"/usr/bin/" + name: "/etc/alternatives/" + name
                   for name in ("ld", "cc", "c++", "awk")}
        targets = {name: Path("/usr/bin/prepared-" + name.rsplit("/", 1)[1]) for name in aliases}
        with patch.object(Path, "is_symlink", lambda path: str(path) in aliases), \
                patch.object(R.os, "readlink", lambda path: aliases[str(path)]), \
                patch.object(Path, "resolve", lambda path, **kwargs: targets[str(path)]), \
                patch.object(Path, "is_file", return_value=True):
            actual = self.resolve_public_aliases()
            self.assertEqual([part for tool, alias in aliases.items()
                              for part in ("--symlink", str(targets[tool]), alias)], actual)
            for tool in ("c++", "awk"):
                with self.subTest(tool=tool):
                    original = targets["/usr/bin/" + tool]
                    targets["/usr/bin/" + tool] = Path("/home/private/tool")
                    with self.assertRaises(R.RunError):
                        self.resolve_public_aliases()
                    targets["/usr/bin/" + tool] = original

    def test_private_tmp_cannot_hide_an_explicit_prepared_runtime(self):
        with tempfile.TemporaryDirectory(prefix="pr-ci-prepared-", dir="/tmp") as temporary:
            prepared = Path(temporary) / "runtime"
            (prepared / "bin").mkdir(parents=True)
            argv = R.namespace_command(self.candidate, [str(prepared / "bin/python"), "one.py"],
                                       prepared_roots=[prepared])
            scratch = next(i for i, value in enumerate(argv) if value == "--tmpfs" and argv[i + 1] == "/tmp")
            mount = next(i for i, value in enumerate(argv) if value == "--ro-bind" and argv[i + 1] == str(prepared))
            self.assertLess(scratch, mount)
            self.assertIn(["--tmpfs", "/run"], [argv[i:i + 2] for i in range(len(argv) - 1)])

    def test_namespace_failure_never_retries_docker_and_timeout_is_failure(self):
        with patch.object(R.subprocess, "run", side_effect=subprocess.TimeoutExpired([], 1)) as call:
            self.assertEqual(124, R.run(self.candidate, ["python3", "one.py"], boundary="user-namespace", timeout=1))
        self.assertEqual(1, call.call_count)
        for boundary in ("host", "unconfined", None):
            with self.subTest(boundary=boundary), self.assertRaises(R.RunError):
                R.run(self.candidate, ["python3"], boundary=boundary)

    def test_env_is_explicitly_empty_before_safe_values_and_never_inherits_credentials(self):
        with patch.dict(os.environ, {"GH_TOKEN": "do-not-forward", "GITHUB_TOKEN": "secret",
                                   "GITHUB_ACTIONS": "true", "ACTIONS_RUNTIME_TOKEN": "secret",
                                   "PATH": "/host/private-tools",
                                   "GITHUB_OUTPUT": "/host/output", "GITHUB_ENV": "/host/env"}):
            argv = self.command(prepared_roots=[self.tools], environment={"JAVA_HOME": str(self.tools)})
        self.assertEqual(["-i", "--"], argv[argv.index(R.IMAGE) + 1:argv.index(R.IMAGE) + 3])
        values = self.environment(argv)
        self.assertEqual("/tmp", values["HOME"])
        self.assertEqual("/tmp/npm", values["NPM_CONFIG_CACHE"])
        self.assertEqual(str(self.tools), values["JAVA_HOME"])
        self.assertFalse(any(name.startswith(("GH_", "GITHUB_", "ACTIONS_")) for name in values))
        self.assertNotIn("do-not-forward", " ".join(argv))
        self.assertNotIn("/host/output", " ".join(argv))
        self.assertNotIn("/host/private-tools", values["PATH"])
        for path in (Path("/usr/lib/qt6/bin"), Path("/usr/lib64/qt6/bin")):
            if path.is_dir():
                self.assertIn(str(path), values["PATH"].split(":"))

    def test_unsafe_environment_keys_and_paths_are_rejected(self):
        for name in ("GH_TOKEN", "GITHUB_OUTPUT", "GITHUB_ENV", "GITHUB_ACTIONS", "HOME",
                     "SSH_AUTH_SOCK", "DOCKER_HOST", "LD_PRELOAD", "PYTHONPATH", "BASH_ENV"):
            with self.subTest(name=name), self.assertRaises(R.RunError):
                self.command(environment={name: "x"})
        for value in ("", ":/usr/bin", "/home/private/bin:/usr/bin", "relative",
                      "/usr/../home/private/bin", "/work/../private/bin"):
            with self.subTest(path=value), self.assertRaises(R.RunError):
                self.command(environment={"PATH": value})
        with self.assertRaises(R.RunError):
            self.command(environment={"JAVA_HOME": "/private/tool"})
        with self.assertRaises(R.RunError):
            self.command(environment={"JAVA_HOME": "/usr/../home/private"})
        self.assertEqual("/usr/bin:/bin", self.environment(
            self.command(environment={"PATH": "/usr/bin:/bin"}))["PATH"])

    def test_only_explicit_dependency_network_uses_bridge(self):
        self.assertIn("--network=none", self.command())
        self.assertIn("--network=bridge", self.command(network=True))
        for value in (1, "host", None):
            with self.subTest(value=value), self.assertRaises(R.RunError):
                self.command(network=value)

    def test_host_roots_controller_runner_temp_and_aliases_are_rejected(self):
        for value in (Path("/"), Path.home(), ROOT, Path("/etc/ssl"), Path("/var/lib"),
                      self.candidate, self.candidate.parent):
            with self.subTest(root=value), self.assertRaises(R.RunError):
                self.command(prepared_roots=[value])
        alias = self.root / "alias"
        alias.symlink_to(self.tools, target_is_directory=True)
        with self.assertRaises(R.RunError):
            self.command(prepared_roots=[alias])
        comma = self.root / "bad,readonly"
        comma.mkdir()
        with self.assertRaises(R.RunError):
            self.command(prepared_roots=[comma])

    def test_private_workspace_clone_and_runner_temp_tool_leaf_are_allowed(self):
        workspace = self.root / "workspace"
        workspace.mkdir()
        candidate = workspace / "candidate"
        self.candidate.rename(candidate)
        trusted = workspace / "trusted"
        trusted.mkdir()
        runner_temp = self.root / "runner-temp"
        runner_temp.mkdir()
        venv = runner_temp / "pr-ci-venv"
        (venv / "bin").mkdir(parents=True)
        with patch.dict(os.environ, {"GITHUB_WORKSPACE": str(workspace), "RUNNER_TEMP": str(runner_temp)}), \
                patch.object(R, "CONTROLLER", trusted):
            argv = R.docker_command(candidate, ["python3", "test.py"], prepared_roots=[venv])
            mounts = self.mounts(argv)
            self.assertIn("type=bind,source=" + str(candidate)
                          + ",target=/work,bind-propagation=rprivate", mounts)
            self.assertIn("type=bind,source=" + str(venv) + ",target=" + str(venv)
                          + ",readonly,bind-propagation=rprivate", mounts)
            for whole in (workspace, runner_temp, self.root, trusted):
                with self.subTest(whole=whole), self.assertRaises(R.RunError):
                    R.docker_command(candidate, ["python3", "test.py"], prepared_roots=[whole])
            source = trusted / "tool"
            source.mkdir()
            with self.assertRaises(R.RunError):
                R.docker_command(candidate, ["python3", "test.py"], prepared_roots=[source])

    def test_prepared_parent_cannot_expose_candidate_or_vice_versa(self):
        inside = self.candidate / "tool"
        inside.mkdir()
        for value in (inside, self.candidate.parent):
            with self.subTest(root=value), self.assertRaises(R.RunError):
                self.command(prepared_roots=[value])
        with self.assertRaises(R.RunError):
            R.docker_command(ROOT, ["python3", "x"])

    def test_linked_git_pointers_external_objects_and_missing_metadata_are_rejected(self):
        git = self.candidate / ".git"
        for name in ("commondir", "objects/info/alternates", "objects/info/http-alternates"):
            path = git / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("/host/controller/.git/objects\n")
            with self.subTest(name=name), self.assertRaises(R.RunError):
                self.command()
            path.unlink()
        (git / "worktrees").mkdir()
        with self.assertRaises(R.RunError):
            self.command()
        (git / "worktrees").rmdir()
        git.rename(self.candidate / "saved-git")
        git.write_text("gitdir: /host/controller/.git/worktrees/one\n")
        with self.assertRaisesRegex(R.RunError, "private clone"):
            self.command()
        git.unlink()
        with self.assertRaises(R.RunError):
            self.command()

    def test_shared_hardlinks_and_live_host_sockets_are_not_private_inputs(self):
        original = self.root / "host-object"
        original.write_text("trusted data")
        linked = self.candidate / ".git/objects/shared"
        os.link(original, linked)
        with self.assertRaisesRegex(R.RunError, "hardlinks"):
            self.command()
        linked.unlink()
        with socket.socket(socket.AF_UNIX) as host_socket:
            host_socket.bind(str(self.tools / "host.sock"))
            with self.assertRaisesRegex(R.RunError, "socket"):
                self.command(prepared_roots=[self.tools])

    def test_guard_internal_version_pointer_is_preserved_without_allowing_git_aliases(self):
        guard = self.candidate / ".git/overte-branch-name-guard"
        version = "a" * 64
        destination = guard / "versions" / version
        destination.mkdir(parents=True)
        current = guard / "current"
        current.symlink_to("versions/" + version)
        self.command()
        current.unlink()
        for target in (str(destination), "../objects", "versions/missing", "../../../../outside"):
            with self.subTest(target=target):
                current.symlink_to(target)
                with self.assertRaisesRegex(R.RunError, "external alias"):
                    self.command()
                current.unlink()
        destination.rmdir()
        destination.symlink_to(self.tools, target_is_directory=True)
        current.symlink_to("versions/" + version)
        with self.assertRaisesRegex(R.RunError, "external alias"):
            self.command()
        current.unlink()
        destination.unlink()
        alias = self.candidate / ".git/refs/internal-alias"
        alias.symlink_to("../objects", target_is_directory=True)
        with self.assertRaisesRegex(R.RunError, "external alias"):
            self.command()

    def test_fully_enumerated_private_npm_hardlinks_are_allowed_but_external_links_are_not(self):
        original = self.candidate / "private-package-binary"
        original.write_text("private binary fixture")
        linked = self.candidate / "private-second-package-binary"
        os.link(original, linked)
        self.command()
        outside = self.root / "external-third-link"
        os.link(original, outside)
        with self.assertRaisesRegex(R.RunError, "external hardlinks"):
            self.command()

    def test_clone_configuration_cannot_carry_host_credentials_or_includes(self):
        config = self.candidate / ".git/config"
        for raw in ('[credential]\n helper = store\n',
                    '[include]\n path = /home/user/.gitconfig\n',
                    '[http "https://github.com/"]\n extraheader = authorization: secret\n',
                    '[remote "origin"]\n url = https://token@github.com/owner/repo\n'):
            with self.subTest(config=raw.splitlines()[0]):
                config.write_text(raw)
                with self.assertRaisesRegex(R.RunError, "credentials"):
                    self.command()

    def test_invalid_command_vectors_fail_before_any_execution(self):
        invalid = ("python3 tests/one.py", [], (), [""], [None], ["-i"], ["X=secret"],
                   ["python3", "a\x00b"], ["python3", "a" * 128_001])
        for value in invalid:
            with self.subTest(value=repr(value)[:80]), self.assertRaises(R.RunError):
                R.docker_command(self.candidate, value)
        self.assertEqual(["python3", "-c", "print('a'); print('b')"],
                         self.command(["python3", "-c", "print('a'); print('b')"])[-3:])

    def test_root_uid_or_gid_is_rejected(self):
        with patch.object(R.os, "getuid", return_value=0), self.assertRaises(R.RunError):
            self.command()
        with patch.object(R.os, "getgid", return_value=0), self.assertRaises(R.RunError):
            self.command()

    def test_run_returns_actual_exit_without_retry_and_clears_docker_client_env(self):
        with patch.dict(os.environ, {"GH_TOKEN": "secret", "DOCKER_HOST": "tcp://elsewhere"}), \
                patch.object(R.subprocess, "run", return_value=subprocess.CompletedProcess([], 23)) as call:
            self.assertEqual(23, R.run(self.candidate, ["python3", "one.py"], timeout=20))
        self.assertEqual(1, call.call_count)
        args, kwargs = call.call_args
        self.assertEqual([R.DOCKER, "--host=" + R.DAEMON, "run"], args[0][:3])
        self.assertEqual(20, kwargs["timeout"])
        self.assertEqual(False, kwargs["check"])
        self.assertNotIn("GH_TOKEN", kwargs["env"])
        self.assertNotIn("DOCKER_HOST", kwargs["env"])
        self.assertNotEqual(str(Path.home()), kwargs["env"]["HOME"])

    def test_timeout_removes_only_its_unique_container_without_running_command_again(self):
        expired = subprocess.TimeoutExpired(["docker"], 1)
        with patch.object(R.subprocess, "run", side_effect=[expired, subprocess.CompletedProcess([], 0)]) as call:
            self.assertEqual(124, R.run(self.candidate, ["python3", "one.py"], timeout=1))
        self.assertEqual(2, call.call_count)
        first = call.call_args_list[0].args[0]
        name = next(v.removeprefix("--name=") for v in first if v.startswith("--name="))
        self.assertEqual([R.DOCKER, "--host=" + R.DAEMON, "rm", "--force", name],
                         call.call_args_list[1].args[0])

    def test_unconfirmed_timeout_cleanup_remains_a_failure(self):
        with patch.object(R.subprocess, "run", side_effect=[subprocess.TimeoutExpired([], 1),
                           subprocess.CompletedProcess([], 1)]), self.assertRaisesRegex(R.RunError, "cleanup"):
            R.run(self.candidate, ["python3", "one.py"], timeout=1)

    def test_bad_timeout_fails_before_contacting_docker(self):
        for value in (0, -1, float("inf"), float("nan"), True, "30", R.MAX_TIMEOUT + 1):
            with self.subTest(value=value), patch.object(R.subprocess, "run") as call, self.assertRaises(R.RunError):
                R.run(self.candidate, ["python3", "one.py"], timeout=value)
            call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
