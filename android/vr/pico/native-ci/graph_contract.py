"""Pico CI graph compatibility and minimum-delta planning.

The executing consumer must authenticate independently pinned completed-producer
receipts and all package bytes before supplying origins. This module does not
turn graph JSON or a successful transport into producer/build authentication.
Its result is always a plan, never native or APK acceptance.
"""
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import re

IDENTITY = ("ref", "rrev", "package_id", "prev", "context", "settings", "options", "package_type")
OVERRIDES = {"libnode": "Release", "webrtc-audio-processing": "Release", "etc2comp": "RelWithDebInfo", "gifcreator": None}
QT = "qt/5.15.18-2026.01.04@overte/stable#4fd1f62ee1914f2f3ec4fe298a07c283"


def require(value, message):
    if not value:
        raise ValueError(message)


def hexdigest(value, length):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{" + str(length) + "}", value) is not None


def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(nodes):
    require(isinstance(nodes, dict) and "0" in nodes and 1 < len(nodes) <= 2048, "Invalid graph membership")
    for key, node in nodes.items():
        require(isinstance(node, dict) and node.get("id") == key, "Graph node identity differs")
        require(node.get("remote") is None and node.get("binary_remote") is None, "Remote graph packages forbidden")
        edges = node.get("dependencies")
        require(isinstance(edges, dict) and set(edges) <= nodes.keys(), "Unresolved graph edges")
        require(all(isinstance(edge, dict) for edge in edges.values()), "Invalid graph edge traits")
        if key == "0":
            continue
        require(node.get("binary") in {"Build", "Cache", "Skip"}, "Unsupported package binary origin")
        require(node.get("context") in {"host", "build"}, "Unsupported graph context")
        require(isinstance(node.get("ref"), str) and hexdigest(node.get("rrev"), 32) and
                node["ref"].endswith("#" + node["rrev"]) and hexdigest(node.get("package_id"), 40),
                "Missing recipe/package identity")
        require(node.get("prev") is None or hexdigest(node["prev"], 32), "Invalid package revision")
        require(isinstance(node.get("settings"), dict) and isinstance(node.get("options"), dict), "Missing graph settings/options")


def validate_pico_target(nodes):
    """Validate the new Pico-owned CI profile; no legacy profile is changed."""
    validate(nodes)
    names = set()
    for key, node in nodes.items():
        if key == "0":
            continue
        settings = node["settings"]
        if settings.get("os") == "Linux":
            require(settings.get("arch") == "x86_64", "Wrong host-tools ABI")
            continue
        require(node["context"] == "host" and settings.get("os") == "Android" and
                settings.get("arch") == "armv8" and str(settings.get("os.api_level")) == "26", "Wrong Pico target ABI/API")
        name = node["ref"].split("/", 1)[0]
        names.add(name)
        require(settings.get("build_type") == OVERRIDES.get(name, "Debug"), "Wrong Pico CI package build type")
        for setting, expected in (("compiler", "clang"), ("compiler.version", "18"),
                                  ("compiler.libcxx", "c++_shared"), ("compiler.cppstd", "gnu20")):
            require(setting not in settings or str(settings[setting]) == expected, "Wrong Pico CI compiler settings")
        if name == "qt":
            require(node["ref"] == QT, "Wrong qualified Qt recipe revision")
            require(node["options"].get("opengl") == "es2", "Wrong Qt GLES profile")
            for option in ("qtwebengine", "with_mysql", "with_odbc", "with_openal", "with_pq"):
                require(str(node["options"].get(option)).lower() == "false", "Wrong Qt dependency options")
        if name == "openssl":
            require(node["ref"].split("#")[0] == "openssl/3.5.8@overte/stable", "Wrong OpenSSL provider version")
        if name == "openexr":
            require(node["ref"].split("#")[0] == "openexr/3.2.12", "Wrong OpenEXR graph cohort")
    require({"qt", "libnode", "etc2comp", "openssl", "openxr", "openexr"} <= names, "Required Pico dependency missing")


def semantic(nodes, key, *, linux_role_mapping=False, include_prev=True, active=(), memo=None):
    memo = {} if memo is None else memo
    require(key not in active and len(active) < 64, "Dependency cycle/depth")
    if key in memo:
        digest, height = memo[key]
        require(len(active) + height <= 64, "Dependency depth")
        return digest
    node = nodes[key]
    value = {field: node.get(field) for field in IDENTITY if include_prev or field != "prev"}
    if linux_role_mapping and node.get("settings", {}).get("os") == "Linux" and node["settings"].get("arch") == "x86_64":
        require(node.get("context") in {"host", "build"}, "Unsupported Linux role")
        value["context"] = "verified-linux-host-or-build"
    edges, heights = [], []
    for child, edge in node["dependencies"].items():
        require(not edge.get("skip") and nodes[child].get("binary") != "Skip", "Skipped dependency is not Build evidence")
        child_digest = semantic(nodes, child, linux_role_mapping=linux_role_mapping,
                                include_prev=include_prev, active=active + (key,), memo=memo)
        edges.append({"edge": {k: v for k, v in edge.items() if k != "skip"}, "node": child_digest})
        heights.append(memo[child][1])
    value["dependencies"] = sorted(edges, key=object_hash)
    result = object_hash(value)
    memo[key] = result, 1 + max(heights, default=0)
    return result


def minimum_delta(wanted, origins, *, linux_role_mapping=False):
    """Find exact reusable Build DAGs, with caller-authenticated receipt seals.

    Each origin supplies actual nodes plus independently verified graph/completion
    digests, producer_revision, completed=True and exit_code=0. These fields are
    prerequisites, not authentication in themselves. The runtime descriptor must
    pin the original receipt and inventory bytes outside candidate control.
    """
    validate_pico_target(wanted)
    require(isinstance(origins, list) and 0 < len(origins) <= 64, "Missing bounded producer lineage")
    available = {}
    for number, origin in enumerate(origins):
        require(origin.get("completed") is True and origin.get("exit_code") == 0 and
                hexdigest(origin.get("producer_revision"), 40) and
                hexdigest(origin.get("graph_sha256"), 64) and hexdigest(origin.get("completion_sha256"), 64),
                "Original completed producer seals required")
        nodes = origin["nodes"]
        validate(nodes)
        memo = {}
        for key, node in nodes.items():
            if key == "0" or node["binary"] != "Build":
                continue
            require(hexdigest(node.get("prev"), 32), "Build origin lacks package revision")
            digest = semantic(nodes, key, linux_role_mapping=linux_role_mapping, memo=memo)
            available.setdefault(digest, []).append((number, key))

    proven = {}

    def prove(number, key, active=()):
        identity = (number, key)
        require(identity not in active and len(active) < 64, "Producer lineage cycle/depth")
        if identity in proven:
            return proven[identity]
        node = origins[number]["nodes"][key]
        require(node["binary"] == "Build", "Cache/Skip is not an original Build")
        for child in node["dependencies"]:
            child_node = origins[number]["nodes"][child]
            if child_node["binary"] == "Build":
                prove(number, child, active + (identity,))
            else:
                require(child_node["binary"] == "Cache", "Skipped origin dependency")
                key_digest = semantic(origins[number]["nodes"], child, linux_role_mapping=linux_role_mapping)
                matches = available.get(key_digest, [])
                require(matches, "Origin dependency lacks an actual Build")
                # All origins were admitted by the caller. Choose a complete
                # non-cyclic chain; do not turn an invalid final proof into reuse.
                valid = []
                for candidate in matches:
                    try:
                        valid.append(prove(*candidate, active + (identity,)))
                    except ValueError:
                        continue
                require(valid, "Origin dependency has no complete Build lineage")
        result = {"producer_revision": origins[number]["producer_revision"],
                  "graph_sha256": origins[number]["graph_sha256"],
                  "completion_sha256": origins[number]["completion_sha256"], "node_id": key}
        proven[identity] = result
        return result

    reused, build, skipped = {}, [], []
    memo = {}
    for key, node in wanted.items():
        if key == "0":
            continue
        if node["binary"] == "Skip":
            skipped.append(key)
            continue
        digest = semantic(wanted, key, linux_role_mapping=linux_role_mapping, memo=memo)
        matches = available.get(digest, [])
        valid = []
        for candidate in matches:
            try:
                valid.append(prove(*candidate))
            except ValueError:
                continue
        if valid:
            reused[key] = valid[0]
        else:
            require(node["binary"] == "Build", "Cached package lacks complete original Build lineage")
            require(node["ref"].split("/", 1)[0] != "qt" and node["settings"].get("os") != "Linux",
                    "Missing qualified Qt/host-tool graph; a second full build is forbidden")
            build.append(key)
    return {"status": "PICO_CI_DELTA_PLAN_NATIVE_AND_APK_VERIFICATION_PENDING",
            "reused_original_builds": reused, "distinct_nodes_requiring_build": build,
            "skipped_unconsumed_nodes": skipped,
            "mandatory_remaining_checks": ["pinned producer/runtime/package-byte authentication",
                "OpenXR overlay/input provenance and actual 16KiB ELF",
                "Pico unsigned release native link and APK contents/ELF/SONAME/NEEDED"],
            "pico_qualified": False}
