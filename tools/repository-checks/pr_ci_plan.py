#!/usr/bin/env python3
"""Pure PR task selection from complete immutable trees and protected policy.

The caller supplies object contents; this module never checks out, imports, or
executes candidate code. A reuse key identifies inputs, commands and declared
runtime requirements. It is not a successful result or permission to reuse one.
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys


ROOT = Path(__file__).resolve().parents[2]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Only the installed planner's helpers are imported, never supplied tree blobs.
_INPUTS = _load("central_pr_input_data", "tools/test-evidence/inputs.py")
_NATIVE = _load("central_pr_native_selection", "tools/native-tests/check.py")
_PACKAGES = _load("central_pr_package_selection", "tools/repository-checks/package_checks.py")
_CODEQL = _load("central_pr_codeql_selection", "tools/repository-checks/codeql.py")
_TOOLS = _load("central_pr_tool_dependencies", "tools/repository-checks/tool_dependencies.py")
_ANDROID_NATIVE = _load("central_android_native_inputs", "tools/repository-checks/pr_ci_android_preflight.py")
# package_checks.select uses this same protected helper. Cache that code at
# import time so planning itself does not read files or load another module.
_PACKAGES.tools = lambda: _TOOLS
NPM_PROJECTS = (*_TOOLS.PROJECTS, _PACKAGES.S3, _PACKAGES.BROWSER, "browser-direct-client")

TARGETS = ("main", "apple-main", "apple-ios", "android-main",
           "android-phone", "android-vr", "android-vr-pico")
REGISTRY = ".github/test-suites.json"
DEPENDENCIES = ".github/test-suite-dependencies.json"
ACTIVE_REGISTRY = ".github/pr-ci-suites.json"
ACTIVE_DEPENDENCIES = ".github/pr-ci-dependencies.json"
RUNTIME_INPUTS = (".github/attested-runtime.json", ".github/ci37-runtime.json",
                  "tests/requirements-host.txt", ".tool-versions", ".github/pr-ci-platforms.json",
                  ".github/pr-ci-platform-inputs.json")
_BROWSER_SUFFIXES = frozenset({".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx",
    ".mts", ".cts", ".html", ".css", ".scss", ".sass", ".vue", ".svelte",
    ".json", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".wasm", ".glb"})
_KNOWN_ROOTS = (".github/", "docs/", "scripts/", "unpublishedScripts/", "tests/",
    "tools/", "ios/", "android/", "browser-client/", "browser-direct-client/",
    "script-archive/", "server-console/", "interface/", "libraries/", "plugins/",
    "cmake/", "assignment-client/", "domain-server/", "ice-server/", "launchers/",
    "pkg-scripts/", "provenance/", "resources/")
_KNOWN_ROOT_FILES = frozenset({"CMakeLists.txt", "conanfile.py", "conan.lock",
    ".gitmodules", ".gitignore", ".gitattributes", "LICENSE", "COPYING",
    "AGENTS.md", "requirements.txt", "package.json", "package-lock.json"})
_KNOWN_SUFFIXES = _BROWSER_SUFFIXES | frozenset({".py", ".pyw", ".pyi", ".sh",
    ".yml", ".yaml", ".toml", ".ini", ".cfg", ".txt", ".xml", ".qrc", ".qml",
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".m", ".mm", ".swift",
    ".kt", ".java", ".cmake", ".gradle", ".properties", ".pro", ".pri"})
_SETUP = frozenset({"host-full", "python", "git", "qt5-qml", "qt6-qml",
                   "node", "npm", "browser", "cmake", "compiler", "qt", "glm", "pillow"})


class PlanError(ValueError):
    """A complete input or trusted task definition cannot be established."""


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _rows(tree, patterns=None):
    return [{"path": path, **tree[path]} for path in sorted(tree)
            if patterns is None or any(fnmatchcase(path, pattern) for pattern in patterns)]


def _read_json(tree, path, read_blob):
    entry = tree.get(path)
    if not entry or entry["mode"] != "100644" or entry["type"] != "blob":
        raise PlanError("missing ordinary trusted policy: " + path)
    try:
        raw = read_blob(entry["sha"])
        if type(raw) is not bytes or len(raw) > 4 * 1024 ** 2:
            raise PlanError("invalid trusted policy bytes: " + path)
        algorithm = hashlib.sha1 if len(entry["sha"]) == 40 else hashlib.sha256
        oid = algorithm(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if oid != entry["sha"]:
            raise PlanError("trusted policy blob identity mismatch: " + path)
        return json.loads(raw, object_pairs_hook=_INPUTS._unique_object)
    except (KeyError, OSError, UnicodeError, json.JSONDecodeError, _INPUTS.InputError) as error:
        raise PlanError("cannot read trusted policy: " + path) from error


def _blob(entry, read_blob):
    if not entry or entry["mode"] != "100644" or entry["type"] != "blob":
        raise PlanError("ordinary immutable blob required")
    raw = read_blob(entry["sha"])
    if type(raw) is not bytes or len(raw) > 4 * 1024 ** 2:
        raise PlanError("immutable blob exceeds its bound")
    algorithm = hashlib.sha1 if len(entry["sha"]) == 40 else hashlib.sha256
    if algorithm(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != entry["sha"]:
        raise PlanError("immutable blob identity mismatch")
    return raw


def _analysis_recipe(trusted_tree, read_blob):
    """Validate the actual protected no-build extractor, without workflow epochs."""
    try:
        recipe = _blob(trusted_tree.get(".github/workflows/repository-checks.yml"), read_blob).decode()
        config = _blob(trusted_tree.get(".github/codeql/codeql-config.yml"), read_blob).decode()
    except (PlanError, KeyError, OSError, UnicodeError, TypeError):
        return False
    action = "cdf488f595d80d6e07e03d4674febd5ab45fa938"
    uses = re.findall(r"(?m)^\s*uses:\s*github/codeql-action/([^\s@]+)@([0-9a-f]+)\s*(?:#.*)?$", recipe)
    if (sorted(uses) != [("analyze", action), ("init", action)]
            or re.findall(r"(?m)^\s*tools:\s*(\S+)\s*$", recipe) != [
                "https://github.com/github/codeql-action/releases/download/codeql-bundle-v2.27.2/codeql-bundle-linux64.tar.zst"]
            or re.findall(r"(?m)^\s*build-mode:\s*(\S+)\s*$", recipe) != ["none"]
            or re.findall(r"(?m)^\s*config-file:\s*(\S+)\s*$", recipe) not in (
                ["./trusted/.github/codeql/codeql-config.yml"], ["./.github/codeql/codeql-config.yml"])
            or re.search(r"LGTM_INDEX_|CODEQL_EXTRACTOR_|(?m:^\s*(?:packs|queries|config):)", recipe)):
        return False
    # The supported configuration only removes paths; query/model packs and
    # extractor customization require a conservative complete analysis.
    in_ignores = False
    for line in config.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if not line.startswith(" ") and text.startswith("name:"):
            in_ignores = False
        elif line == "paths-ignore:":
            in_ignores = True
        elif in_ignores and line.startswith("  - ") and re.fullmatch(r"[A-Za-z0-9_./*+?\[\]-]+", text[2:]):
            continue
        else:
            return False
    return True


def _security(base_tree, candidate_tree, trusted_tree, changes, read_blob):
    """Use the 2.27.2 extractor footprint, not a historical workflow blob list."""
    both = list(_CODEQL.LANGUAGES)
    controls = (".github/workflows/repository-checks.yml", ".github/codeql/codeql-config.yml")
    if (not _analysis_recipe(trusted_tree, read_blob) or any(
            tree.get(path) != trusted_tree.get(path)
            for tree in (base_tree, candidate_tree) for path in controls)):
        return {"languages": both, "reasons": [{"code": "changed-or-unknown-analysis-controls"}]}
    if any(entry["mode"] not in {"100644", "100755"}
           for tree in (base_tree, candidate_tree) for entry in tree.values()):
        return {"languages": both, "reasons": [{"code": "unresolved-source-alias-or-submodule"}]}
    if any(PurePosixPath(path).name in _CODEQL._PACK_MANIFESTS
           or PurePosixPath(path).suffix.lower() in _CODEQL._QUERY_EXTENSIONS
           or (path.startswith(".github/codeql/") and path != controls[1])
           for tree in (base_tree, candidate_tree) for path in tree):
        return {"languages": both, "reasons": [{"code": "custom-or-unknown-analysis-inputs"}]}
    languages, reasons = set(), []
    native_count, native_bytes = 0, 0
    for change in changes:
        path = change["path"]
        ordinary = all(entry and entry["mode"] == "100644" and entry["type"] == "blob"
                       for entry in (change["before"], change["after"]))
        native = False
        if (ordinary and not PurePosixPath(path).name.startswith(".")
                and PurePosixPath(path).suffix in _CODEQL._PINNED_NATIVE_EXTENSIONS):
            try:
                if native_count + 2 > _CODEQL._NATIVE_BLOB_COUNT:
                    return {"languages": both, "reasons": [{"code": "native-input-inventory-bound"}]}
                values = [_blob(change[side], read_blob) for side in ("before", "after")]
                native_count += 2
                native_bytes += sum(map(len, values))
                if native_bytes > _CODEQL._NATIVE_TOTAL_BYTES:
                    return {"languages": both, "reasons": [{"code": "native-input-inventory-bound"}]}
                native = all(b"\0" not in value and not value.decode("utf-8-sig").startswith("#!") for value in values)
            except (PlanError, KeyError, OSError, UnicodeError, TypeError):
                pass
        if ordinary and path in _CODEQL._PINNED_NPM_LOCKS:
            selected, reason = (), "reviewed-2.27.2-npm-lock"
        elif native:
            selected, reason = (), "reviewed-2.27.2-native-source"
        elif ordinary and path in _CODEQL._PYTHON_POLICY_JSONS:
            selected, reason = ("python",), "protected-python-policy-input"
        elif ordinary and path in _CODEQL._INERT_CI_JSONS:
            selected, reason = (), "reviewed-inert-policy-json"
        else:
            selected, reason = _CODEQL._source_languages(path), "extractor-input"
        if selected is None:
            return {"languages": both, "reasons": [{"code": "unknown-analysis-input", "path": path}]}
        languages.update(selected)
        reasons.append({"code": reason, "path": path, "languages": list(selected)})
    return {"languages": [language for language in both if language in languages], "reasons": reasons}


def _policy(trusted_tree, read_blob):
    active = (ACTIVE_REGISTRY in trusted_tree, ACTIVE_DEPENDENCIES in trusted_tree)
    if any(active) and not all(active):
        raise PlanError("active CI registry and dependencies must be present together")
    registry_path, dependencies_path = ((ACTIVE_REGISTRY, ACTIVE_DEPENDENCIES)
        if all(active) else (REGISTRY, DEPENDENCIES))
    try:
        registry = _INPUTS._validate_registry(_read_json(trusted_tree, registry_path, read_blob))
    except _INPUTS.InputError as error:
        raise PlanError("invalid trusted suite registry") from error
    dependencies = _read_json(trusted_tree, dependencies_path, read_blob)
    if (type(dependencies) is not dict or type(dependencies.get("schema")) is not int
            or dependencies.get("schema") not in (1, 2)
            or type(dependencies.get("suites")) is not dict
            or set(dependencies["suites"]) != set(registry["suites"])):
        raise PlanError("incomplete trusted suite dependency data")
    independent = dependencies.get("product_independent_paths", [])
    ci_independent = dependencies.get("ci_independent_paths", [])
    try:
        _INPUTS._paths(independent, "independent product inputs")
        _INPUTS._paths(ci_independent, "independent CI inputs")
    except _INPUTS.InputError as error:
        raise PlanError("invalid product input exclusions") from error
    if any(any(char in path for char in "*?[") for path in independent + ci_independent):
        raise PlanError("product exclusions must be exact reviewed paths")
    rows = {}
    for name, suite in registry["suites"].items():
        row = dependencies["suites"][name]
        if (type(row) is not dict or type(row.get("setup")) is not list
                or any(type(item) is not str or item not in _SETUP for item in row["setup"])
                or len(row["setup"]) != len(set(row["setup"]))
                or (not all(active) and row.get("definition_digest")
                    != _INPUTS._suite_definition_digest(suite))):
            raise PlanError("invalid trusted dependencies for suite " + name)
        if all(active) and row.get("kind") not in {"patterns", "product-inventory", "documentation-inventory"}:
            raise PlanError("unsupported active dependency closure for suite " + name)
        if "content_inputs" in row:
            try:
                _INPUTS._paths(row["content_inputs"], "content inputs", nonempty=True)
            except _INPUTS.InputError as error:
                raise PlanError("invalid content input closure for suite " + name) from error
            if not all(active) or suite["closure"]["kind"] != "repository":
                raise PlanError("content inputs require an active repository inventory")
        rows[name] = dict(row)
        rows[name]["excluded"] = set(independent + ci_independent) if row.get("kind") == "product-inventory" else set()
    # Epochs, workflow generations, lookup pins and target program hashes are
    # not task dependencies. No finite source-generation admission is applied.
    return registry, rows


def _suite_inputs(tree, registry, suite, dependency):
    # A link can connect a pattern closure to an otherwise unrelated input.
    if any(entry["mode"] not in {"100644", "100755"} for entry in tree.values()):
        return _rows(tree)
    if suite["closure"]["kind"] == "repository":
        excluded = dependency["excluded"] - set(suite["closure"]["required"])
        rows = [entry for entry in _rows(tree) if entry["path"] not in excluded
                or any(fnmatchcase(entry["path"], pattern) for pattern in registry["control_inputs"])]
        if "content_inputs" in dependency:
            content = [*dependency["content_inputs"], *registry["control_inputs"],
                       *suite["closure"]["required"]]
            # Directory existence, glob discovery and deleted paths remain
            # dependencies even when a reader does not consume file contents.
            entrypoint = next((arg for arg in suite["command"][1:] if arg.endswith(".py")), None)
            lookup = {PurePosixPath("."), PurePosixPath(entrypoint).parent} if entrypoint else set()
            def consumes(row):
                path = PurePosixPath(row["path"])
                return (any(fnmatchcase(row["path"], pattern) for pattern in content)
                    or path.parent in lookup and path.suffix in {".py", ".pyc", ".pyo", ".so", ".pyd", ".pth"})
            rows = [row if consumes(row)
                    else {key: value for key, value in row.items() if key != "sha"}
                    for row in rows]
        return rows
    patterns = list(suite["closure"]["inputs"]) + list(registry["control_inputs"])
    for root in suite.get("python_imports", {}).get("roots", []):
        patterns.extend((root, root + "/**"))
    selected = {entry["path"]: entry for entry in _rows(tree, patterns)}
    # Preserve negative import-lookup membership without a finite lookup hash.
    # Adding a shadow module beside the entrypoint or at repository root is an
    # input change even when it was not present when the closure was written.
    if suite["command"][0] == "python" and len(suite["command"]) > 1:
        entrypoint = next((arg for arg in suite["command"][1:] if arg.endswith(".py")), None)
        directories = {"", str(PurePosixPath(entrypoint).parent)} if entrypoint else {""}
        for path, entry in tree.items():
            parent = str(PurePosixPath(path).parent)
            if parent == ".":
                parent = ""
            if (parent in directories and PurePosixPath(path).name.split(".", 1)[0].isidentifier()
                    and PurePosixPath(path).suffix in {".py", ".pyc", ".pyo", ".so", ".pyd", ".pth"}):
                selected[path] = {"path": path, **entry}
    return [selected[path] for path in sorted(selected)]


def _browser_code(path):
    return (path.startswith(("browser-client/", "browser-direct-client/"))
            and PurePosixPath(path).name not in {"package.json", "package-lock.json"}
            and PurePosixPath(path).suffix.lower() in _BROWSER_SUFFIXES)


def _npm_source(path):
    return (any(path.startswith(project + "/")
                for project in NPM_PROJECTS)
            and PurePosixPath(path).suffix.lower() in _BROWSER_SUFFIXES)


def _browser_product_suite(name, suite):
    # This existing Python suite tests CI routing, not the browser product.
    if name == "browser-cpu-selection":
        return False
    return (name.startswith("browser-") or any(
        argument.startswith("browser-client/") for argument in suite["command"])
        or any(pattern.startswith("browser-client/")
               for pattern in suite["closure"]["inputs"]))


def _platform_inputs(paths, native_mode, target):
    product = native_mode != "skip"
    android = target.startswith("android-") and (product or any(
        path.startswith("android/") and not path.endswith(".md") for path in paths))
    ios = target == "apple-ios" and (product or any(
        (path.startswith("ios/") and not path.endswith(".md"))
        or path in {".github/workflows/ios-integrated.yml", ".github/workflows/ios-qt-source.yml"}
        for path in paths))
    return android, ios



def _android_compile_products(paths, base_tree, candidate_tree, target):
    """Select real SDK Java/resource compilation only for present app inputs."""
    if not target.startswith("android-"):
        return []
    roots = {"phone": "android/phone/apps/phoneInterface/src/main/",
             "pico": "android/vr/pico/apps/picoInterface/src/main/"}
    shared = any(not path.endswith((".md", ".markdown")) and (
        path.startswith(("android/common/web/java/", "android/common/web/res/",
                         "android/common/snapshot/java/", "android/common/snapshot/res/",
                         "android/common/documents/java/", "android/common/documents/res/",
                         "security/redaction/java/", "android/common/libraries/qt/src/main/")))
        for path in paths)
    available = base_tree.keys() | candidate_tree.keys()
    # Integration branches retain historical product snapshots. Compile only
    # their governed owner, never stale sibling applications merely present.
    owner = {"android-main": "common", "android-vr": "common",
             "android-phone": "phone", "android-vr-pico": "pico"}[target]
    if owner == "common":
        present = any(path.startswith("android/common/") for path in available)
        return [owner] if shared and present else []
    root = roots[owner]
    return [owner] if any(path.startswith(root) for path in available) and (shared or any(
        path.startswith((root + "java/", root + "res/")) or path == root + "AndroidManifest.xml"
        for path in paths)) else []



def _server_console_coverage(tree, registry, dependency, read_blob):
    """Recognize only the actual standard npm script covering the registered subset."""
    suite = registry["suites"].get("server-console-behavior")
    if (not suite or suite["environment"] != "node" or dependency["setup"] != ["node"]
            or suite["command"][:2] != ["node", "--test"]):
        return False
    try:
        manifest = _read_json(tree, "server-console/package.json", read_blob)
    except PlanError:
        return False
    scripts = manifest.get("scripts") if type(manifest) is dict else None
    if (type(scripts) is not dict or scripts.get("test") != "node --test test/*.test.js"
            or "pretest" in scripts or "posttest" in scripts):
        return False
    registered = suite["command"][2:]
    matched = sorted(path for path in tree
        if str(PurePosixPath(path).parent) == "server-console/test" and path.endswith(".test.js"))
    required = suite["closure"]["required"]
    inputs = _suite_inputs(tree, registry, suite, dependency)
    return (bool(registered) and len(registered) == len(set(registered))
        and set(registered) <= set(matched) and not (set(required) - set(tree))
        and all(row["mode"] in {"100644", "100755"} and row["type"] == "blob" for row in inputs))


def _version(value):
    if type(value) is not str or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value):
        raise ValueError("exact release version required")
    return tuple(map(int, value.split(".")))


def _range_contains(requirement, version):
    prefix = requirement[:1] if type(requirement) is str else ""
    minimum = _version(requirement[1:] if prefix in {"^", "~"} else requirement)
    actual = _version(version)
    if prefix == "~":
        return actual >= minimum and actual[:2] == minimum[:2]
    if prefix == "^" and minimum[0] > 0:
        return actual >= minimum and actual[0] == minimum[0]
    return actual == minimum


def _project_manifest_only(base, candidate, project):
    paths = {path for path in base.keys() | candidate.keys()
             if path.startswith(project + "/") and base.get(path) != candidate.get(path)}
    manifests = {project + "/package.json", project + "/package-lock.json"}
    return bool(paths) and paths <= manifests and all(
        tree.get(path) and tree[path]["mode"] == "100644" and tree[path]["type"] == "blob"
        for tree in (base, candidate) for path in paths)


def _vite_profile(base, candidate, project, read_blob):
    """Prove a patch-only Vite graph change and unchanged real build consumers."""
    if project not in {"browser-client", "browser-direct-client"} or not _project_manifest_only(base, candidate, project):
        return None
    required = [project + "/" + path for path in ("vite.config.ts", "tsconfig.json",
                "tools/build-notices.mjs", "tools/prepare-default-avatar.mjs")]
    if project == "browser-client":
        required += [project + "/" + path for path in ("vite.embedded.config.mjs",
            "tests/embedded-fbx-worker.test.ts", "tests/fixtures/embedded-worker-entry.ts",
            "tests/fixtures/node-browser-worker.mjs", "src/model-fbx-worker.ts")]
    if any(not candidate.get(path) or candidate[path]["mode"] not in {"100644", "100755"}
           for path in required):
        return None
    manifests = {root + "/" + name for root in ("browser-client", "browser-direct-client")
                 for name in ("package.json", "package-lock.json")}
    consumers = lambda tree: [row for row in _rows(tree) if row["path"] not in manifests and (
        row["path"].startswith(("browser-client/", "browser-direct-client/", "LICENSES/", "interface/resources/meshes/"))
        or row["path"] in {"LICENSE", ".npmrc", ".nvmrc", ".node-version", ".tool-versions", "package.json", "package-lock.json"})]
    old_inputs, new_inputs = consumers(base), consumers(candidate)
    if old_inputs != new_inputs or any(row["mode"] not in {"100644", "100755"} for row in old_inputs):
        return None
    try:
        old, new = [_read_json(tree, project + "/package.json", read_blob) for tree in (base, candidate)]
        old_lock, new_lock = [_read_json(tree, project + "/package-lock.json", read_blob) for tree in (base, candidate)]
        before, after = old["devDependencies"]["vite"], new["devDependencies"]["vite"]
        if not (_version(before)[:2] == _version(after)[:2] and _version(before) < _version(after)):
            return None
        if (new["scripts"].get("build") != "tsc --noEmit && vite build && node tools/build-notices.mjs"
                or new["scripts"].get("prebuild") != "node tools/prepare-default-avatar.mjs"
                or any(key in new["scripts"] for key in ("postbuild", "pretest", "posttest"))):
            return None
        normalized_manifests = [deepcopy(value) for value in (old, new)]
        for value in normalized_manifests:
            del value["devDependencies"]["vite"]
        if normalized_manifests[0] != normalized_manifests[1]:
            return None
        normalized_locks = [deepcopy(value) for value in (old_lock, new_lock)]
        records = []
        for lock, version in zip(normalized_locks, (before, after)):
            if lock["lockfileVersion"] != 3 or lock["packages"][""]["devDependencies"]["vite"] != version:
                return None
            del lock["packages"][""]["devDependencies"]["vite"]
            record = lock["packages"]["node_modules/vite"]
            if (record["version"] != version or record["resolved"] !=
                    "https://registry.npmjs.org/vite/-/vite-" + version + ".tgz"
                    or not re.fullmatch(r"sha512-[A-Za-z0-9+/]+={0,2}", record["integrity"])):
                return None
            records.append(record)
            for key in ("version", "resolved", "integrity"):
                del record[key]
        if set(records[0]["dependencies"]) != set(records[1]["dependencies"]):
            return None
        for name, requirement in records[0]["dependencies"].items():
            current = records[1]["dependencies"][name]
            if requirement != current:
                resolved = old_lock["packages"].get("node_modules/vite/node_modules/" + name,
                           old_lock["packages"].get("node_modules/" + name))
                if not resolved or not (_range_contains(requirement, resolved["version"])
                                        and _range_contains(current, resolved["version"])):
                    return None
        del records[0]["dependencies"], records[1]["dependencies"]
        if normalized_locks[0] != normalized_locks[1]:
            return None
    except (PlanError, KeyError, ValueError, TypeError, OSError):
        return None
    return {"kind": "vite-compatible-patch", "from": before, "to": after,
            "manifest_complement": _digest(normalized_manifests[0]),
            "graph_complement": _digest(normalized_locks[0]), "consumer_inputs": _digest(new_inputs)}


def _pillow_profile(base, candidate, read_blob):
    path = "tests/requirements-host.txt"
    if base.get(path) == candidate.get(path):
        return False
    try:
        old, new = [_blob(tree.get(path), read_blob).decode() for tree in (base, candidate)]
        old_value, old_count = re.subn(r"(?m)^Pillow==[0-9]+\.[0-9]+\.[0-9]+$", "Pillow=={version}", old)
        new_value, new_count = re.subn(r"(?m)^Pillow==13\.0\.0$", "Pillow=={version}", new)
        return old_count == new_count == 1 and old_value == new_value
    except (PlanError, KeyError, UnicodeError, TypeError, OSError):
        return False


def plan(base_tree, candidate_tree, trusted_tree, *, read_blob, target="main"):
    """Return deterministic tasks for one of seven target branches.

    Trees must be complete path -> {mode,type,sha} maps, including deletions,
    symlinks and gitlinks. read_blob(sha) returns immutable Git blob bytes.
    Rename detection is unnecessary: both removed and added paths are examined.
    Platform flags request target-specific product validation; they do not
    authorize a device build. Execution, runtime attestation and result reuse
    are the coordinator's responsibility.
    """
    if target not in TARGETS or not callable(read_blob):
        raise PlanError("unsupported target or missing immutable blob reader")
    try:
        for tree in (base_tree, candidate_tree, trusted_tree):
            _INPUTS._validate_tree(tree)
    except (_INPUTS.InputError, TypeError, ValueError) as error:
        raise PlanError("complete immutable trees are required") from error
    registry, dependencies = _policy(trusted_tree, read_blob)
    changes = [{"path": path, "before": dict(base_tree[path]) if path in base_tree else None,
                "after": dict(candidate_tree[path]) if path in candidate_tree else None}
               for path in sorted(base_tree.keys() | candidate_tree.keys())
               if base_tree.get(path) != candidate_tree.get(path)]
    paths = [change["path"] for change in changes]
    regular = all(entry is None or entry["mode"] in {"100644", "100755"}
                  for change in changes for entry in (change["before"], change["after"]))
    unknown = not regular or any(not (path in _KNOWN_ROOT_FILES or path.endswith(".md")
        or (path.startswith(_KNOWN_ROOTS) and (PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES
            or PurePosixPath(path).name == "CMakeLists.txt"))) for path in paths)
    if ACTIVE_REGISTRY in trusted_tree:
        independent = {path for row in dependencies.values() for path in row["excluded"]}
        patterns = [pattern for suite in registry["suites"].values()
                    for pattern in suite["closure"]["inputs"]]
        unknown |= any(change["before"] is None and change["path"] not in trusted_tree
            and change["path"] not in independent and not _npm_source(change["path"])
            and not change["path"].endswith((".md", ".markdown"))
            and not any(fnmatchcase(change["path"], pattern) for pattern in patterns)
            for change in changes)
    packages = _PACKAGES.select(paths, regular, include_browser=True, unknown=unknown)
    browser = any(_browser_code(path) for path in paths)
    npm_projects = list(dict.fromkeys(packages["tool_projects"] + packages["package_set"]
        + [project for project in NPM_PROJECTS
           if any(path.startswith(project + "/") and not path.endswith(".md") for path in paths)]))
    # JS browser source/assets have their own package owner. Build definitions
    # and unknown browser extensions still reach the native conservative path.
    native_paths = [path for path in paths if not _npm_source(path)
                    and path != "tests/requirements-host.txt"]
    native = _NATIVE.plan(native_paths, regular, verified_empty=not native_paths)
    if unknown:
        native = {"mode": "full", "paths": paths,
                  "reasons": ["unknown or non-regular input"], "force_broad": True}
    security = (_security(base_tree, candidate_tree, trusted_tree, changes, read_blob)
                if paths else {"languages": [], "reasons": [{"code": "identical-immutable-inputs"}]})
    manifest_paths = {project + "/" + name for project in NPM_PROJECTS
                      for name in ("package.json", "package-lock.json")}
    package_only = (regular and bool(set(paths) & manifest_paths)
                    and all(path in manifest_paths or path.endswith((".md", ".markdown")) for path in paths))
    vite_profiles = {project: profile for project in npm_projects
                     if (profile := _vite_profile(base_tree, candidate_tree, project, read_blob))}
    pillow = _pillow_profile(base_tree, candidate_tree, read_blob)
    pillow_suites = {"pillow-image-observation", "pillow-animated-overlay"}
    dependency_selection = dict(candidate_tree)
    if pillow and pillow_suites <= set(registry["suites"]):
        dependency_selection["tests/requirements-host.txt"] = base_tree["tests/requirements-host.txt"]
    product_selection = dict(dependency_selection)
    for project in npm_projects:
        if _project_manifest_only(base_tree, candidate_tree, project):
            for name in ("package.json", "package-lock.json"):
                path = project + "/" + name
                if path in base_tree:
                    product_selection[path] = base_tree[path]
    selected = []
    if paths:
        for name, suite in registry["suites"].items():
            if package_only and name != "server-console-behavior" and not (
                any(path.endswith((".md", ".markdown")) for path in paths)
                and (dependencies[name]["kind"] == "documentation-inventory" or name == "documentation")):
                continue
            if _browser_product_suite(name, suite) and not browser:
                continue
            selection = (candidate_tree if name in pillow_suites else
                product_selection if dependencies[name]["kind"] == "product-inventory" else dependency_selection)
            if (unknown or suite["scope"] == "candidate"
                    or _suite_inputs(base_tree, registry, suite, dependencies[name])
                       != _suite_inputs(selection, registry, suite, dependencies[name])):
                selected.append(name)
    android, ios = _platform_inputs(paths, native["mode"], target)
    android_compile = _android_compile_products(paths, base_tree, candidate_tree, target)
    android_native = ([{"android-main": "common", "android-vr": "common",
                        "android-phone": "phone", "android-vr-pico": "pico"}[target]]
                      if _ANDROID_NATIVE.classify(paths, target=target)["native_qualification_required"] else [])
    android = android or bool(android_compile) or bool(android_native)
    ios_build = ios and (native["mode"] != "skip" or any(
        (path.startswith("ios/") and not path.startswith(("ios/tests/", "ios/release-check/"))
         and not path.endswith(".md"))
        or path in {".github/workflows/ios-integrated.yml", ".github/workflows/ios-qt-source.yml"}
        for path in paths))
    covered = {}
    if ("server-console" in npm_projects and "server-console-behavior" in selected
            and _server_console_coverage(candidate_tree, registry,
                dependencies["server-console-behavior"], read_blob)):
        covered["suite:server-console-behavior"] = "npm:server-console"
    tasks = {}
    runtime_entries = _rows(trusted_tree, list(RUNTIME_INPUTS))

    def add(task_id, kind, command, inputs, setup, *, environment, required=(), target_scoped=False):
        missing = sorted(set(required) - set(candidate_tree))
        task = {"id": task_id, "kind": kind, "command": command,
                "setup": sorted(set(setup)), "environment": environment,
                "missing_inputs": missing,
                "reuse_key": _digest({"task": task_id, "command": command,
                    "environment": environment, "setup": sorted(set(setup)),
                    **({"target": target} if target_scoped else {}),
                    "inputs": inputs, "missing_inputs": missing, "runtime": runtime_entries}),
                "reuse_requires": ["authenticated-successful-result", "matching-resolved-command",
                                   "matching-observed-runtime"]}
        if task_id in tasks and tasks[task_id] != task:
            raise PlanError("conflicting duplicate task " + task_id)
        tasks[task_id] = task

    for name in selected:
        if "suite:" + name in covered:
            continue
        suite = registry["suites"][name]
        add("suite:" + name, "host", suite["command"], _suite_inputs(candidate_tree, registry, suite, dependencies[name]),
            dependencies[name]["setup"], environment=suite["environment"],
            required=suite["closure"]["required"], target_scoped=suite["scope"] == "candidate")
    for project in npm_projects:
        commands = ([list(command) for command in _TOOLS.BROWSER_MANIFEST_COMMANDS]
                    if project == "browser-client" else [
                        ["npm", "ci", "--ignore-scripts", "--no-fund", "--no-audit"],
                        ["npm", "audit", "--audit-level=low"]])
        if project == "tools/jsdoc":
            commands.append(["node_modules/.bin/jsdoc", "root.js", "-c", "config.json", "-d", "{temporary_output}"])
        elif project == "server-console":
            commands.extend([["npm", "test"], ["node_modules/.bin/electron-packager", "--version"]])
        elif project == _PACKAGES.S3:
            commands.append(["npm", "test"])
        elif project == "browser-direct-client":
            commands.extend([["npm", "run", "build"], ["npm", "test"]])
        if project == "browser-client" and project in vite_profiles:
            commands = commands[:2] + [["npm", "run", "build"],
                ["node_modules/.bin/tsx", "--test", "tests/embedded-fbx-worker.test.ts"]]
        browser_journey = (project in {"browser-client", "browser-direct-client"}
            and any(path.startswith(project + "/") and _browser_code(path) for path in paths))
        if browser_journey:
            commands.append(["npm", "run", "test:browser"] if project == "browser-client" else
                ["node", "node_modules/@playwright/test/cli.js", "test", "--config", "playwright.config.ts"])
        # Package scripts may read files outside their directory. Until a
        # narrower closure is declared, their identity includes the whole tree.
        add("npm:" + project, "npm", commands, _rows(candidate_tree),
            ["node", "npm", *(["browser"] if browser_journey else [])], environment="node", required=[project + "/package.json",
                                                              project + "/package-lock.json"])
        tasks["npm:" + project]["covers"] = [name for name, owner in covered.items()
                                              if owner == "npm:" + project]
        tasks["npm:" + project]["profile"] = vite_profiles.get(project, {"kind": "full"})
        if project == "tools/jsdoc":
            tasks["npm:" + project]["temporary_output"] = {
                "placeholder": "{temporary_output}", "kind": "outside-checkout-temporary-directory"}
    if native["mode"] != "skip":
        add("native:" + native["mode"], "native", ["native-tests", native["mode"]],
            _rows(candidate_tree), ["cmake", "compiler", "conan", "qt"], environment="native")
    for language in security["languages"]:
        add("codeql:" + language, "codeql", ["codeql", "analyze", language],
            _rows(candidate_tree), ["codeql"], environment="codeql")
    if android:
        add("platform:android", "android", ["platform-validation", target,
                *[argument for product in android_compile for argument in ("--compile-product", product)],
                *[argument for product in android_native for argument in ("--native-product", product)]],
            _rows(candidate_tree), ["host-full"], environment=target, target_scoped=True)
    if ios:
        add("platform:ios", "ios", ["platform-validation", target],
            _rows(candidate_tree), ["host-full", *(["xcode"] if ios_build else [])], environment=target, target_scoped=True)
    return {"schema": 1, "target": target, "changes": changes, "paths": paths,
            "regular": regular, "conservative_fallback": unknown,
            "host_suites": selected, "npm_projects": npm_projects,
            "covered_tasks": covered,
            "dependency_profiles": {"pillow13": pillow, "vite": vite_profiles},
            "native": native, "codeql_languages": security["languages"],
            "codeql_reasons": security["reasons"], "browser_required": browser,
            "android_required": android, "android_compile_products": android_compile,
            "android_native_products": android_native, "ios_required": ios, "ios_build_required": ios_build,
            "tasks": list(tasks.values()),
            "setup": sorted({item for task in tasks.values() for item in task["setup"]}),
            "input_identity": {"base": _digest(_rows(base_tree)),
                               "candidate": _digest(_rows(candidate_tree)),
                               "trusted": _digest(_rows(trusted_tree))},
            "execution": False, "reusable_result": False}
