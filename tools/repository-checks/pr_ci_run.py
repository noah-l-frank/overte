#!/usr/bin/env python3
"""Run candidate commands without host credentials or controller mounts.

The trusted caller supplies a private ordinary clone and the exact command. It
also prepares dependencies before running tests. ``network=True`` is an explicit
dependency-fetch role, never an automatic retry or a test fallback. Nothing here
asserts native qualification or reusable execution evidence.

Docker's default seccomp/AppArmor policy remains enabled. The trusted planner
can explicitly choose a separate offline Bubblewrap boundary for tests which
themselves need user namespaces. This never retries a failed Docker command or
grants an unconfined Docker profile.
"""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import uuid

IMAGE = "ubuntu@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90"
DOCKER = "/usr/bin/docker"
BWRAP = "/usr/bin/bwrap"
PRLIMIT = "/usr/bin/prlimit"
DAEMON = "unix:///var/run/docker.sock"
DEFAULT_TIMEOUT = 900
MAX_TIMEOUT = 7200
CONTROLLER = Path(__file__).resolve().parents[2]
SAFE_ENVIRONMENT = frozenset({
    "PATH", "LANG", "LC_ALL", "TZ", "CI", "PYTHONDONTWRITEBYTECODE",
    "PYTHONUNBUFFERED", "JAVA_HOME", "CC", "CXX", "CPPFLAGS", "CFLAGS",
    "CXXFLAGS", "LDFLAGS", "OVERTE_TEST_GLM_INCLUDE",
    "OVERTE_TEST_QT_WEBCHANNEL_INCLUDE", "QT_QPA_PLATFORM",
})
PATH_ENVIRONMENT = frozenset({
    "JAVA_HOME", "OVERTE_TEST_GLM_INCLUDE", "OVERTE_TEST_QT_WEBCHANNEL_INCLUDE",
})


class RunError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise RunError(message)


def _directory(value, label):
    try:
        path = Path(value)
        require(path.is_absolute() and not any(c in str(path) for c in ",=\x00\r\n"),
                label + " must be an absolute ordinary mount path")
        require(path.resolve(strict=True) == path and path.is_dir() and not path.is_symlink(),
                label + " must be an existing directory without aliases")
    except (OSError, RuntimeError, TypeError) as error:
        raise RunError(label + " directory unavailable") from error
    return path


def _inside(path, parent):
    return path == parent or parent in path.parents


def _overlap(left, right):
    return _inside(left, right) or _inside(right, left)


def _private_path(path, label):
    # Individual prepared leaves may live below a home or runner scratch root;
    # whole roots, their ancestors and the trusted controller stay private.
    forbidden = {Path("/"), Path("/home"), Path("/root"), Path.home(),
                 Path("/etc"), Path("/run"), Path("/var"), Path("/var/run"),
                 Path("/proc"), Path("/sys"), Path("/dev"), Path("/tmp"), Path("/opt")}
    require(path not in forbidden, label + " would expose a host root or private directory")
    require(not any(_inside(path, parent) for parent in (
        Path("/etc"), Path("/run"), Path("/var"), Path("/proc"),
        Path("/sys"), Path("/dev"), Path("/root"))),
        label + " would expose private host state or sockets")
    require(not {".ssh", ".aws", ".azure", ".docker", ".gnupg", ".config"}.intersection(path.parts),
            label + " would expose a private credential directory")
    require(not _overlap(path, CONTROLLER), label + " overlaps the trusted controller")
    for name in ("RUNNER_TEMP", "GITHUB_WORKSPACE", "GITHUB_ACTION_PATH"):
        value = os.environ.get(name)
        if value and Path(value).is_absolute():
            require(not _inside(Path(value).resolve(), path),
                    label + " would expose the whole " + name)


def _roots(prepared_roots):
    require(type(prepared_roots) in (tuple, list), "prepared roots must be an explicit directory list")
    # Python 3.12 -S leaves sys.prefix at the base interpreter. The invocation
    # path still identifies its venv; VIRTUAL_ENV is untrusted ambient state.
    invoked = Path(sys.executable)
    venv = invoked.parent.parent
    config = venv / "pyvenv.cfg"
    invocation_roots = []
    if invoked.is_absolute() and config.is_file():
        require(not config.is_symlink() and config.stat().st_size <= 16_384,
                "invoked Python environment configuration is not ordinary")
        invocation_roots.append(venv)
    values = [Path("/usr"), *invocation_roots, Path(sys.prefix), Path(sys.base_prefix), *prepared_roots]
    result = []
    for value in values:
        path = _directory(value, "prepared root")
        if path != Path("/usr"):
            _private_path(path, "prepared root")
        if not any(_inside(path, previous) for previous in result):
            result = [previous for previous in result if not _inside(previous, path)]
            result.append(path)
    for root in result:
        if root != Path("/usr"):
            _ordinary_tree(root, snapshot=False)
    return result


def _ordinary_tree(root, *, snapshot):
    count = 0
    linked = {}
    try:
        def fail(error):
            raise error
        for parent, directories, files in os.walk(root, followlinks=False, onerror=fail):
            for name in [*directories, *files]:
                count += 1
                require(count <= 200_000, "mounted input inventory exceeds its bound")
                path = Path(parent) / name
                info = path.lstat()
                require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode),
                        "mounted inputs contain a socket or special device")
                if snapshot and stat.S_ISREG(info.st_mode):
                    if info.st_nlink > 1:
                        key = (info.st_dev, info.st_ino)
                        seen, expected = linked.get(key, (0, info.st_nlink))
                        require(expected == info.st_nlink, "candidate hardlink inventory changed")
                        linked[key] = (seen + 1, expected)
                if snapshot and _inside(path, root / ".git"):
                    require(not stat.S_ISLNK(info.st_mode), "candidate Git metadata contains an external alias")
        require(all(seen == expected for seen, expected in linked.values()),
                "candidate snapshot has external hardlinks; clone with --no-hardlinks")
    except OSError as error:
        raise RunError("mounted input inventory unavailable") from error


def _candidate(value, roots):
    candidate = _directory(value, "candidate")
    _private_path(candidate, "candidate")
    require(not any(_overlap(candidate, root) for root in roots),
            "candidate and prepared roots overlap")
    git = candidate / ".git"
    require(git.is_dir() and not git.is_symlink() and git.resolve(strict=True) == git,
            "candidate must be a private clone, not a linked worktree or Git pointer")
    require(not any((git / name).exists() or (git / name).is_symlink()
                    for name in ("commondir", "worktrees", "objects/info/alternates", "objects/info/http-alternates")),
            "candidate Git metadata must not depend on an external object store")
    for name in ("objects", "refs"):
        _directory(git / name, "candidate Git " + name)
    config = git / "config"
    require(config.is_file() and not config.is_symlink() and config.resolve(strict=True) == config,
            "candidate Git configuration is not private")
    require(config.stat().st_size <= 64_000, "candidate Git configuration exceeds its bound")
    raw = config.read_text(encoding="utf-8")
    require(re.search(r"(?im)^\s*\[\s*(?:credential|include(?:if)?)(?:\s|\])"
                      r"|^\s*(?:extraheader|askpass)\s*=|https?://[^/\s@]+@", raw) is None,
            "candidate Git configuration contains credentials or external includes")
    _ordinary_tree(candidate, snapshot=True)
    return candidate


def _command(command):
    require(type(command) in (tuple, list) and 0 < len(command) <= 4096,
            "an explicit nonempty argument vector is required")
    require(all(type(value) is str and value and "\x00" not in value for value in command)
            and sum(len(value.encode()) + 1 for value in command) <= 128_000,
            "command arguments must be bounded strings without NULs")
    require(not command[0].startswith("-") and "=" not in command[0],
            "command executable cannot be an option or environment assignment")
    return list(command)


def _environment(environment, roots):
    require(environment is None or type(environment) is dict, "environment must be an explicit safe mapping")
    paths = [str(root / "bin") for root in roots if root != Path("/usr") and (root / "bin").is_dir()]
    values = {
        "PATH": ":".join(dict.fromkeys([*paths, "/usr/local/bin", "/usr/bin", "/bin"])),
        "HOME": "/tmp", "TMPDIR": "/tmp", "XDG_CACHE_HOME": "/tmp/cache",
        "NPM_CONFIG_CACHE": "/tmp/npm", "PIP_CACHE_DIR": "/tmp/pip",
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC", "CI": "true",
        "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
    }
    for name, value in (environment or {}).items():
        require(type(name) is str and name in SAFE_ENVIRONMENT,
                "environment key is not allowed in the candidate container")
        require(type(value) is str and "\x00" not in value and len(value.encode()) <= 8192,
                "environment values must be bounded strings without NULs")
        if name == "PATH":
            directories = value.split(":")
            require(directories and all(_environment_path(p, [Path("/work"), *roots])
                    for p in directories), "PATH must stay inside mounted inputs")
        elif name in PATH_ENVIRONMENT:
            require(_environment_path(value, roots),
                    name + " must stay inside prepared inputs")
        values[name] = value
    return values


def _environment_path(value, roots):
    path = Path(value)
    if not value or not path.is_absolute() or ".." in path.parts:
        return False
    # The fixed Ubuntu base uses merged /usr; no host /bin mount is added.
    for alias in ("bin", "sbin", "lib", "lib64"):
        if _inside(path, Path("/" + alias)):
            path = Path("/usr") / alias / path.relative_to("/" + alias)
            break
    return any(_inside(path, root) for root in roots)


def docker_command(candidate, command, *, prepared_roots=(), network=False,
                   environment=None, container_name=None):
    """Build and validate argv only; do not contact Docker or run the candidate."""
    require(type(network) is bool, "network is an explicit dependency-fetch boolean")
    uid, gid = os.getuid(), os.getgid()
    require(uid > 0 and gid > 0, "candidate container requires a nonroot UID and GID")
    roots = _roots(prepared_roots)
    candidate = _candidate(candidate, roots)
    command = _command(command)
    values = _environment(environment, roots)
    argv = [DOCKER, "--host=" + DAEMON, "run", "--rm", "--pull=never",
            "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
            "--user=" + str(uid) + ":" + str(gid), "--workdir=/work",
            # Docker's default PID namespace is private. The CLI accepts only
            # host/container selectors; an explicit "private" value is invalid.
            "--network=" + ("bridge" if network else "none"),
            "--ipc=private", "--cgroupns=private", "--pids-limit=512",
            "--memory=8g", "--memory-swap=8g", "--cpus=4",
            "--ulimit=nofile=8192:8192", "--ulimit=core=0", "--log-driver=none",
            "--tmpfs=/tmp:rw,nosuid,nodev,size=2g,mode=1777"]
    if container_name is not None:
        require(type(container_name) is str and re.fullmatch(r"overte-pr-ci-[0-9a-f]{32}", container_name),
                "invalid private container name")
        argv.append("--name=" + container_name)
    for root in roots:
        argv += ["--mount", "type=bind,source=" + str(root) + ",target=" + str(root)
                 + ",readonly,bind-propagation=rprivate"]
    argv += ["--mount", "type=bind,source=" + str(candidate)
             + ",target=/work,bind-propagation=rprivate",
             "--mount", "type=bind,source=" + str(candidate / ".git")
             + ",target=/work/.git,readonly,bind-propagation=rprivate",
             "--entrypoint=/usr/bin/env", IMAGE, "-i", "--"]
    argv += [name + "=" + value for name, value in sorted(values.items())]
    return [*argv, *command]


def _public_network_bindings():
    """Expose only public resolver/host entries and the system CA bundle."""
    result = []
    for destination in ("/etc/resolv.conf", "/etc/hosts"):
        source = Path(destination).resolve(strict=True)
        require(source.is_file() and source.stat().st_size <= 128_000,
                "public network configuration unavailable")
        result += ["--ro-bind", str(source), destination]
    bundle = Path("/etc/ssl/certs/ca-certificates.crt")
    if not bundle.is_file():
        bundle = Path("/etc/ssl/cert.pem")
    source = bundle.resolve(strict=True)
    require(source.is_file() and source.stat().st_size <= 4_000_000,
            "public CA bundle unavailable")
    return [*result, "--ro-bind", str(source), "/etc/ssl/certs/ca-certificates.crt",
            "--symlink", "certs/ca-certificates.crt", "/etc/ssl/cert.pem"]


def namespace_command(candidate, command, *, prepared_roots=(), network=False,
                      environment=None, timeout=DEFAULT_TIMEOUT):
    """Build an explicit namespace boundary; network is a trusted fetch role.

    network=True shares the host network for dependency fetching, including its
    localhost services. Test/build commands must retain the offline default.
    """
    require(type(network) is bool, "network is an explicit dependency-fetch boolean")
    uid, gid = os.getuid(), os.getgid()
    require(uid > 0 and gid > 0, "candidate namespace requires a nonroot UID and GID")
    require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= MAX_TIMEOUT,
            "candidate timeout is outside the allowed bound")
    roots = _roots(prepared_roots)
    candidate = _candidate(candidate, roots)
    command = _command(command)
    values = _environment(environment, roots)
    # Limit address space, processes, files and CPU without a privileged cgroup
    # manager. This is an address-space bound, not Docker's physical-memory cap.
    argv = [PRLIMIT, "--as=" + str(32 * 1024 ** 3),
            "--nofile=8192:8192", "--core=0:0", "--fsize=" + str(4 * 1024 ** 3),
            "--cpu=" + str(math.ceil(timeout)), "--", BWRAP,
            "--unshare-all", "--die-with-parent", "--new-session", "--clearenv",
            "--cap-drop", "ALL", "--uid", str(uid), "--gid", str(gid),
            "--hostname", "overte-pr-ci"]
    if network:
        argv += ["--share-net", *_public_network_bindings()]
        values.update(SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt",
                      SSL_CERT_DIR="/etc/ssl/certs")
    for root in roots:
        argv += ["--ro-bind", str(root), str(root)]
    for alias in ("bin", "sbin", "lib", "lib64"):
        if (Path("/usr") / alias).is_dir():
            argv += ["--symlink", "usr/" + alias, "/" + alias]
    # Some hosts select their linker through /etc/alternatives. Recreate only
    # this public tool alias, after proving its target is already in RO /usr.
    linker = Path("/usr/bin/ld")
    if linker.is_symlink() and os.readlink(linker) == "/etc/alternatives/ld":
        target = linker.resolve(strict=True)
        require(_inside(target, Path("/usr")) and target.is_file(),
                "system linker alias escapes prepared /usr")
        argv += ["--symlink", str(target), "/etc/alternatives/ld"]
    argv += ["--proc", "/proc", "--dev", "/dev", "--size", str(2 * 1024 ** 3),
             "--tmpfs", "/tmp", "--bind", str(candidate), "/work",
             "--ro-bind", str(candidate / ".git"), "/work/.git",
             "--remount-ro", "/", "--chdir", "/work"]
    for name, value in sorted(values.items()):
        argv += ["--setenv", name, value]
    # Apply the process limit after entering the private user namespace. Applying
    # it to the host UID can prevent namespace setup on a busy shared machine.
    return [*argv, "--", PRLIMIT, "--nproc=512:512", "--", *command]


def run(candidate, command, *, prepared_roots=(), network=False,
        timeout=DEFAULT_TIMEOUT, environment=None, boundary="docker"):
    """Return the real Docker/command exit code; timeout returns124 after removal.

    Only the trusted host launches Docker and observes output. There is no shell,
    inherited Docker context, credential forwarding, image pull or command retry.
    """
    require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= MAX_TIMEOUT,
            "candidate timeout is outside the allowed bound")
    require(boundary in ("docker", "user-namespace"), "unknown candidate execution boundary")
    if boundary == "user-namespace":
        argv = namespace_command(candidate, command, prepared_roots=prepared_roots,
            network=network, environment=environment, timeout=timeout)
        try:
            return subprocess.run(argv, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8"}, cwd="/", timeout=timeout, check=False).returncode
        except subprocess.TimeoutExpired:
            # bwrap's isolated PID namespace and --die-with-parent terminate its
            # descendants when the timed-out monitor is killed by subprocess.
            return 124
    name = "overte-pr-ci-" + uuid.uuid4().hex
    argv = docker_command(candidate, command, prepared_roots=prepared_roots,
                          network=network, environment=environment, container_name=name)
    with tempfile.TemporaryDirectory(prefix="overte-pr-ci-docker-client-") as config:
        client_env = {"PATH": "/usr/bin:/bin", "HOME": config, "DOCKER_CONFIG": config,
                      "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
        try:
            return subprocess.run(argv, cwd=config, env=client_env, timeout=timeout, check=False).returncode
        except BaseException as error:
            # Killing the CLI alone does not stop its container. This is cleanup
            # of exactly our unique name, not another candidate execution attempt.
            try:
                removed = subprocess.run([DOCKER, "--host=" + DAEMON, "rm", "--force", name],
                    cwd=config, env=client_env, timeout=30, check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                require(removed.returncode == 0, "candidate container cleanup was not confirmed")
            except (OSError, subprocess.TimeoutExpired) as cleanup:
                raise RunError("candidate container cleanup was not confirmed") from cleanup
            if isinstance(error, subprocess.TimeoutExpired):
                return 124
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--prepared-root", type=Path, action="append", default=[])
    parser.add_argument("--network-for-dependencies", action="store_true")
    parser.add_argument("--boundary", choices=("docker", "user-namespace"), default="docker")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--command", nargs=argparse.REMAINDER, required=True)
    args = parser.parse_args(argv)
    try:
        return run(args.candidate, args.command, prepared_roots=args.prepared_root,
                   network=args.network_for_dependencies, timeout=args.timeout, boundary=args.boundary)
    except (RunError, OSError) as error:
        print("Candidate container unavailable: " + str(error), file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
