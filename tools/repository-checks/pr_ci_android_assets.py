#!/usr/bin/env python3
"""Prepare only protected, completed Android runtime assets; execute no producer.

Every URL, byte count and digest comes from reviewed controller policy. Public
asset downloads use no GitHub credentials. A local cache is only a transport
optimization and receives exactly the same verification as a fresh download.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import urllib.parse
import urllib.request

import pr_ci_android_runtime as R
import pr_ci_android_capacity as CAP

ROOT = Path(__file__).resolve().parents[2]
POLICY = ".github/pr-ci-android-native.json"
NATIVE_KINDS = frozenset({"image", "sdk", "runtime", "qualification", "controller"})
KINDS = NATIVE_KINDS | {"groovy"}
MAX_ASSET = 2 * 1024 ** 3 - 1
SHA = re.compile(r"[0-9a-f]{64}")


def require(value, message):
    if not value:
        raise ValueError(message)


def asset(value):
    require(type(value) is dict and set(value) == {"url", "bytes", "sha256"},
            "invalid protected Android asset descriptor")
    require(type(value["bytes"]) is int and 0 < value["bytes"] <= MAX_ASSET
            and type(value["sha256"]) is str and SHA.fullmatch(value["sha256"]),
            "invalid Android asset byte identity")
    url = urllib.parse.urlsplit(value["url"])
    require(url.scheme == "https" and url.netloc == "github.com" and not url.query and not url.fragment
            and re.fullmatch(r"/noah-l-frank/overte/releases/download/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+", url.path),
            "Android runtime asset must belong to the authorized fork release")
    return value


def policy(root=ROOT, *, qualified=True):
    raw = (Path(root) / POLICY).read_bytes()
    require(len(raw) <= 2_000_000, "Android runtime policy exceeds its bound")
    value = json.loads(raw, object_pairs_hook=R.unique)
    require(type(value) is dict and set(value) == ({"schema", "kind", "status", "assets", "products"}
                | ({"capacity"} if value.get("status") == "qualified" else set()))
            and value["schema"] == 1 and value["kind"] == "overte-android-native-runtime-v1"
            and value["status"] in {"awaiting-local-qualification", "qualified"}
            and type(value["assets"]) is dict and type(value["products"]) is dict,
            "invalid protected Android runtime policy")
    if value["status"] != "qualified":
        require(not value["assets"] and not value["products"], "unqualified Android policy grants partial authority")
        require(not qualified, "Android runtime is awaiting actual local native/APK qualification")
        return value
    require(set(value["assets"]) == KINDS and set(value["products"]) == {"common", "phone", "pico"},
            "qualified Android runtime is missing an owning product or immutable payload")
    require(type(value["capacity"]) is dict and set(value["capacity"]) == {"prepare", "execute"},
            "qualified Android runtime is missing measured capacity budgets")
    for limit in value["capacity"].values():
        CAP.budget(limit)
    for name, payload in value["assets"].items():
        keys = {"archive"} if name == "image" else {"archive", "inventory"}
        require(type(payload) is dict and set(payload) == keys, "invalid Android runtime payload")
        for descriptor in payload.values():
            asset(descriptor)
        if name != "image":
            require(payload["inventory"]["bytes"] <= 150_000_000, "Android inventory exceeds its bound")
    for name, product in value["products"].items():
        require(type(product) is dict and set(product) == {"template", "baseline", "dependency_intent"},
                "invalid Android product qualification")
        require(type(product["dependency_intent"]) is dict and bool(product["dependency_intent"]),
                "missing Android dependency declaration closure")
        for path, digest in product["dependency_intent"].items():
            R.relative(path)
            require(type(digest) is str and SHA.fullmatch(digest), "invalid Android dependency declaration digest")
        template, baseline = product["template"], product["baseline"]
        require(type(template) is dict and set(template) == {"path", "sha256"}, "invalid Android consumer template")
        R.relative(template["path"])
        require(type(template["sha256"]) is str and SHA.fullmatch(template["sha256"]),
                "invalid Android consumer template digest")
        require(type(baseline) is dict and set(baseline) == {"source", "tree", "receipt_path", "receipt_sha256"}
                and all(type(baseline[key]) is str and re.fullmatch(r"[0-9a-f]{40}", baseline[key])
                        for key in ("source", "tree")) and type(baseline["receipt_sha256"]) is str
                and SHA.fullmatch(baseline["receipt_sha256"]), "invalid completed Android qualification identity")
        R.relative(baseline["receipt_path"])
    return value


def verified_file(path, descriptor):
    return (path.is_file() and not path.is_symlink() and path.stat().st_size == descriptor["bytes"]
            and R.digest(path) == descriptor["sha256"])


def fetch(descriptor, cache, *, opener=urllib.request.urlopen):
    """Download a bounded immutable data file, or reverify its exact cache hit."""
    descriptor = asset(descriptor)
    cache = Path(cache)
    require(cache.is_dir() and not cache.is_symlink() and cache.resolve(strict=True) == cache,
            "Android asset cache must be an existing ordinary directory")
    destination = cache / descriptor["sha256"]
    if destination.exists() or destination.is_symlink():
        if verified_file(destination, descriptor):
            return destination
        # This optional cache carries no authority. Remove only its fixed
        # digest-named leaf, never a link target, then fetch protected bytes.
        require(stat.S_ISREG(destination.lstat().st_mode) or destination.is_symlink(),
                "restored Android cache leaf is not a file")
        destination.unlink()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".android-download-", dir=cache, delete=False) as output:
            temporary = Path(output.name)
            request = urllib.request.Request(descriptor["url"], headers={"User-Agent": "Overte-Android-CI"})
            with opener(request, timeout=60) as response:
                final = urllib.parse.urlsplit(response.geturl())
                require(final.scheme == "https" and final.hostname in {
                    "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"},
                    "Android asset redirected outside the public release transport")
                total, digest = 0, hashlib.sha256()
                while True:
                    chunk = response.read(min(1024 * 1024, descriptor["bytes"] - total + 1))
                    if not chunk:
                        break
                    total += len(chunk)
                    require(total <= descriptor["bytes"], "Android asset exceeded its protected byte count")
                    digest.update(chunk)
                    output.write(chunk)
                require(total == descriptor["bytes"] and digest.hexdigest() == descriptor["sha256"],
                        "downloaded Android asset differs from protected bytes")
            output.flush()
        os.link(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


def prepare(value, destination, cache, *, opener=urllib.request.urlopen):
    """Extract a completed runtime into a new private root; no image is loaded."""
    require(value["status"] == "qualified", "unqualified Android runtime cannot be prepared for execution")
    destination = Path(destination)
    require(not destination.exists() and not destination.is_symlink()
            and destination.parent.resolve(strict=True) == destination.parent,
            "Android runtime destination must be new and canonical")
    staging = Path(tempfile.mkdtemp(prefix=".android-runtime-", dir=destination.parent))
    try:
        image = None
        for name in sorted(NATIVE_KINDS):
            payload = value["assets"][name]
            archive = fetch(payload["archive"], cache, opener=opener)
            if name == "image":
                image = archive
                continue
            ledger = fetch(payload["inventory"], cache, opener=opener)
            R.extract(archive, staging / name, ledger, payload["inventory"]["sha256"],
                      payload["archive"]["sha256"], payload["archive"]["bytes"])
            shutil.copyfile(ledger, staging / (name + "-inventory.json"))
        # Never replace a concurrently created destination, even an empty one.
        destination.mkdir()
        try:
            for path in staging.iterdir():
                path.rename(destination / path.name)
        except BaseException:
            remove_private_tree(destination)
            raise
        return {"root": str(destination), "image_archive": str(image), "build_qualified": False}
    finally:
        # Extraction can restore read-only directories. Cleanup changes only our
        # private staging tree and never follows a payload symlink.
        remove_private_tree(staging)


def remove_private_tree(root):
    """Remove only a caller-owned staging tree, including sealed directories."""
    for directory, dirs, _files in os.walk(root, followlinks=False):
        for entry in [Path(directory), *(Path(directory) / name for name in dirs)]:
            if not entry.is_symlink():
                entry.chmod(entry.stat().st_mode | 0o700)
    shutil.rmtree(root)
