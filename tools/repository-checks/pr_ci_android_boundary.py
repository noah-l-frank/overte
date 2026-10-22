#!/usr/bin/env python3
"""Construct the offline Android consumer boundary from protected inputs.

Payload verification and product qualification belong to the calling protected
controller. This module accepts neither an image override nor ambient Docker
configuration and never invokes a dependency producer or downloads an image.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile
import uuid

import pr_ci_run as R

IMAGE = "sha256:1b2da099cf7c03f6ea4b751cf8f148784f12db71fdaabb2b6330d60ba1572dda"
# Classic engines address the image configuration; containerd addresses the
# Docker archive's image manifest. Both are independently pinned and must expose
# the same actual runtime configuration and ordered uncompressed rootfs layers.
MANIFEST_IMAGE = "sha256:b3d9fea96f913616d09f2a1fa41e7afc6e450576739451e6904e50c925f4a335"
CONFIG_SHA256 = "72b19f9d46f2e543c3e57b39a719edb32d7b85fbed7a0a840069f217ddb90c2e"
LAYERS = (
    "sha256:31631a95db7cd650d1c826f269b9e93b57d9f418128bf7c5499b4403be4d44d0",
    "sha256:698e3fdad3d4e4d05eaba5299fb7d3b08bc23540b140c73399ece8038824c214",
    "sha256:fae7c86f5bbe8cca65ea90052937672eb1eb3e80c6eb0e7bfb36808294301465",
    "sha256:16a342ede1173f9581d93e9f366680d5234d8928ea5e654353439d27cb3ba091",
    "sha256:ad57baf5d70ef43e1666caafa88629844665357a9bd5829cafb52173ba41745f",
    "sha256:27fc86a619639636c6695e289c4d44905a784d530f31b0b47a0d9a8767f733bb",
    "sha256:a46bc18268ea46423cddfa5d89ad96ff62ee1f6a5f6c2f50921376503b98811c",
)
TOOL_PATH = ("/opt/sh001/conan/bin:/usr/lib/jvm/java-17-openjdk-amd64/bin:"
             "/opt/android-sdk/build-tools/36.0.0:"
             "/opt/android-sdk/ndk/27.3.13750724/toolchains/llvm/prebuilt/linux-x86_64/bin:"
             "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
ENVIRONMENT = {
    "PATH": TOOL_PATH, "HOME": "/scratch/home", "TMPDIR": "/tmp",
    "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC", "CI": "true",
    "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
    "JAVA_HOME": "/usr/lib/jvm/java-17-openjdk-amd64",
    "ANDROID_SDK_ROOT": "/opt/android-sdk",
    "ANDROID_HOME": "/opt/android-sdk",
    "ANDROID_NDK_HOME": "/opt/android-sdk/ndk/27.3.13750724",
    "GRADLE_USER_HOME": "/scratch/gradle-home",
    "CONAN_HOME": "/attempt/conan",
    "OVERTE_QT_COMPOSED_SOURCE": "/attempt/qt-composed",
    "CMAKE_BUILD_PARALLEL_LEVEL": "2", "MAKEFLAGS": "-j2",
    "PICO_BUILD_JOBS": "2", "OMP_NUM_THREADS": "2", "OMP_THREAD_LIMIT": "2",
}


def directories(candidate, runtime, sdk, scratch, controller, qualification):
    roots = []
    for value, label in ((runtime, "Android dependency payload"), (sdk, "Android SDK payload"),
                         (scratch, "Android build scratch"), (controller, "Android consumer program"),
                         (qualification, "Android qualification inputs")):
        path = R._directory(value, label)
        R._private_path(path, label)
        roots.append(path)
    for index, left in enumerate(roots):
        R.require(not any(R._overlap(left, right) for right in roots[index + 1:]),
                  "Android mounted roots must not overlap")
    candidate = R._candidate(candidate, roots)
    for name in ("conan", "target-continuation", "qt-composed"):
        R.require((roots[0] / name).is_dir() and not (roots[0] / name).is_symlink(),
                  "Android dependency payload is incomplete: " + name)
    for name in ("build-tools/36.0.0/aapt2", "platforms/android-36/android.jar",
                 "ndk/27.3.13750724/toolchains/llvm/prebuilt/linux-x86_64/bin/clang"):
        path = roots[1] / name
        R.require(path.is_file() and path.resolve().is_relative_to(roots[1]),
                  "Android SDK payload is incomplete: " + name)
    return candidate, roots


def docker_command(candidate, command, *, runtime, sdk, scratch, controller, qualification,
                   name, product, image=IMAGE):
    R.require(product in {"common", "phone", "pico"}, "invalid Android consumer product")
    R.require(image in {IMAGE, MANIFEST_IMAGE}, "unreviewed Android image identity")
    candidate, roots = directories(candidate, runtime, sdk, scratch, controller, qualification)
    runtime, sdk, scratch, controller, qualification = roots
    command = R._command(command)
    R.require(type(name) is str and re.fullmatch(r"overte-android-ci-[0-9a-f]{32}", name),
              "invalid private Android consumer name")
    uid, gid = os.getuid(), os.getgid()
    R.require(uid > 0 and gid > 0, "Android candidate execution requires nonroot UID/GID")
    argv = [R.DOCKER, "--host=" + R.DAEMON, "run", "--rm", "--pull=never",
            "--name=" + name, "--read-only", "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true", "--user=" + str(uid) + ":" + str(gid),
            "--workdir=/attempt/source", "--network=none", "--ipc=private", "--cgroupns=private",
            "--pids-limit=512", "--memory=8g", "--memory-swap=8g", "--cpus=2",
            "--ulimit=nofile=8192:8192", "--ulimit=core=0", "--log-driver=none",
            "--tmpfs=/tmp:rw,nosuid,nodev,size=2g,mode=1777"]
    mounts = ((runtime, "/attempt", True), (runtime, "/prepared", True),
              (sdk, "/opt/android-sdk", True), (qualification, "/qualification", True),
              (controller, "/ci-controller", True), (scratch, "/scratch", False),
              (candidate, "/attempt/source", False), (candidate / ".git", "/attempt/source/.git", True))
    for source, target, readonly in mounts:
        argv += ["--mount", "type=bind,source=" + str(source) + ",target=" + target
                 + (",readonly" if readonly else "") + ",bind-propagation=rprivate"]
    argv += ["--entrypoint=/usr/bin/env", image, "-i", "--"]
    environment = dict(ENVIRONMENT)
    if product in {"common", "phone"}:
        environment["OVERTE_FDROID_CONAN_DIR"] = "/attempt/target-continuation"
    argv += [key + "=" + value for key, value in sorted(environment.items())]
    return [*argv, *command]


def image_identity(environment, client):
    for selector in (IMAGE, MANIFEST_IMAGE):
        try:
            raw = subprocess.check_output([R.DOCKER, "--host=" + R.DAEMON, "image", "inspect", selector],
                                          env=environment, cwd=client, timeout=30,
                                          stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            continue
        R.require(len(raw) <= 1_000_000, "Android image inspection exceeds its bound")
        try:
            images = json.loads(raw)
            R.require(type(images) is list and len(images) == 1 and type(images[0]) is dict,
                      "invalid Android image inspection")
            actual = images[0]
            config = json.dumps(actual["Config"], sort_keys=True, separators=(",", ":")).encode()
            R.require(actual["Id"] in {IMAGE, MANIFEST_IMAGE}
                      and actual["Os"] == "linux" and actual["Architecture"] == "amd64"
                      and actual["RootFS"] == {"Type": "layers", "Layers": list(LAYERS)}
                      and hashlib.sha256(config).hexdigest() == CONFIG_SHA256,
                      "Android image content differs from protected runtime identity")
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise R.RunError("invalid Android image inspection") from error
        return actual["Id"]
    raise R.RunError("prepared Android container image unavailable; no image is pulled automatically")


def run(candidate, command, *, runtime, sdk, scratch, controller, qualification, product, timeout=7200):
    R.require(type(timeout) is int and 0 < timeout <= 7200, "invalid Android consumer deadline")
    name = "overte-android-ci-" + uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix="overte-android-docker-client-") as client:
        environment = {"PATH": "/usr/bin:/bin", "HOME": client, "DOCKER_CONFIG": client,
                       "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
        identity = image_identity(environment, client)
        argv = docker_command(candidate, command, runtime=runtime, sdk=sdk, scratch=scratch,
                              controller=controller, qualification=qualification,
                              name=name, product=product, image=identity)
        try:
            return subprocess.run(argv, env=environment, cwd=client, timeout=timeout, check=False).returncode
        except BaseException as error:
            try:
                removed = subprocess.run([R.DOCKER, "--host=" + R.DAEMON, "rm", "--force", name],
                                        env=environment, cwd=client, timeout=30, check=False,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                R.require(removed.returncode == 0, "Android consumer cleanup was not confirmed")
            except (OSError, subprocess.TimeoutExpired) as cleanup:
                raise R.RunError("Android consumer cleanup was not confirmed") from cleanup
            if isinstance(error, subprocess.TimeoutExpired):
                return 124
            raise
