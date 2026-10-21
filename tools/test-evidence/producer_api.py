#!/usr/bin/env python3
"""Dormant read-only GitHub adapter for producer.py; no dispatch or retry.

Only independently read API facts create Authenticated* protocol objects. The
separate source contracts support open same-fork PRs and integrated source lookup: API
referenced_workflows identifies the ORIGINAL merge/source, never head_sha or an
artifact assertion. Unknown sources, incomplete inventories and mixed attempts
cannot fall back to an older green. Trusted policy is supplied by the controller;
there is deliberately no candidate JSON/CLI policy or facts constructor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import re
import selectors
import shutil
import signal
import subprocess
import time
from urllib.parse import quote

import producer as P
import source_admission


REPOSITORY = "noah-l-frank/overte"
PREFIX = "repos/" + REPOSITORY
WORKFLOWS = frozenset(".github/workflows/" + name + ".yml" for name in (
    "project-tests", "parent-qualification", "sync-validation", "repository-checks"))
METADATA_WORKFLOW = ".github/workflows/pr-metadata-context.yml"
METADATA_WORKFLOWS = WORKFLOWS | {".github/workflows/browser-client.yml", METADATA_WORKFLOW}
METADATA_CALLERS = {".github/workflows/repository-checks.yml": METADATA_WORKFLOWS,
                    ".github/workflows/codeql.yml": frozenset({".github/workflows/codeql.yml", METADATA_WORKFLOW})}
METADATA_SOURCE = "tools/repository-checks/metadata_context.py"
METADATA_JOB = "Authenticate PR text edit / Recognize immutable text edit context"
METADATA_STEP = "Authenticated one-way metadata non-producer"
ORDINARY_SOURCE_STEP = "Authenticated ordinary producer scheduling source"
NONPRODUCER_RUN_NAME = 'Overte native metadata nonproducer v2'
ORDINARY_RUN_NAME = 'Overte native ordinary qualification v2'
METADATA_INTENT_KIND = 'authenticated-metadata-nonproducer-intent'
_SCHEDULING_RUN_FIELDS = ('id', 'workflow_id', 'check_suite_id', 'path', 'event', 'head_sha',
                          'head_branch', 'run_attempt', 'run_number', 'display_title')
CODEQL_UPLOAD_WORKFLOW = 'b29e0558dc69bc9dd6fc6b47bd6024382be4079d'
CODEQL_UPLOAD_TEMPLATE = 'tools/repository-checks/workflows/metadata-edits/codeql-upload-provenance.yml'
# A server-rendered title is meaningful only under these exact reviewed native
# recipes. Their nonproducer intent structurally excludes every heavy job even
# when recognition is missing/failed. Historical recipes require their marker.
_NATIVE_INTENT_RECIPES = frozenset({
    ('.github/workflows/repository-checks.yml', '5ab9ff4592635ad67cd7f542de9676702180592d',
     'b76ade9fd7a76da21bf2cb2161deae7a262163e8'),
    ('.github/workflows/codeql.yml', CODEQL_UPLOAD_WORKFLOW,
     'b76ade9fd7a76da21bf2cb2161deae7a262163e8'),
    ('.github/workflows/repository-checks.yml', '22fe0d6d39d120f800099136d7d1ab5280d80b41',
     'b76ade9fd7a76da21bf2cb2161deae7a262163e8'),
    ('.github/workflows/codeql.yml', '7b0703d88d404f38c1b3dec92f77f03586c9144c',
     'b76ade9fd7a76da21bf2cb2161deae7a262163e8'),
    ('.github/workflows/repository-checks.yml', '15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a',
     'b76ade9fd7a76da21bf2cb2161deae7a262163e8'),
    ('.github/workflows/codeql.yml', '3b7a88765b7181a1bc7dd6f48b9b459e590055d3',
     'b76ade9fd7a76da21bf2cb2161deae7a262163e8'),
    ('.github/workflows/repository-checks.yml', 'bc9c4284286b5c3d2de07a3ecf3b98393e2f2a2c',
     'b76ade9fd7a76da21bf2cb2161deae7a262163e8'),
    ('.github/workflows/repository-checks.yml', '81bcf1933edc435826e2de411a777cccd4dec7c7',
     'b76ade9fd7a76da21bf2cb2161deae7a262163e8'),
    ('.github/workflows/codeql.yml', 'e9aaaed9693efc5ffb4701697ac2a4d51f5f5ba1',
     'b76ade9fd7a76da21bf2cb2161deae7a262163e8'),
})
RETAINED_OWNER_GENERATIONS = frozenset({'protected-producer-original-default-v1',
    'protected-producer-original-default-boolean-v1',
    'protected-producer-original-default-required-context-v1',
    'protected-producer-optional-parent-source-v1',
    'protected-producer-optional-leaf-common-v1',
    'protected-producer-exact-parent-command-owners-v1'})


def retain_native_metadata_sources(generations, sources):
    """Retain exact original workflow/helper pairs without replacing current ones."""
    prior = {METADATA_SOURCE: {'mode':'100644','type':'blob',
        'sha':'c6ce80aa78d2f2161b1ea0caf715a6346187e8b9'}}
    for name, workflows in list(generations.items()):
        marker = workflows.get(METADATA_WORKFLOW, {})
        old = (marker.get('sha') == 'b76ade9fd7a76da21bf2cb2161deae7a262163e8'
            and (set(workflows) == METADATA_WORKFLOWS
                and workflows['.github/workflows/repository-checks.yml'].get('sha') == '81bcf1933edc435826e2de411a777cccd4dec7c7'
                or set(workflows) == METADATA_CALLERS['.github/workflows/codeql.yml']
                and workflows['.github/workflows/codeql.yml'].get('sha') == 'e9aaaed9693efc5ffb4701697ac2a4d51f5f5ba1'))
        if old and not any(workflows == row and sources[key] == prior for key,row in generations.items()):
            key = name + '-reviewed-helper-v1'
            require(key not in generations, 'retained helper pair name collides')
            generations[key], sources[key] = workflows, prior
    # The Boolean generation was deployed with this exact helper before the
    # canonical required-context successor. Preserve its real native pair too;
    # a current template cannot rewrite an original invocation's helper.
    boolean_prior = {METADATA_SOURCE: {'mode':'100644','type':'blob',
        'sha':'8f157f4bb98f56fc431dfff301f566727096bf7c'}}
    for name, workflows in list(generations.items()):
        caller = ('.github/workflows/repository-checks.yml' if set(workflows) == METADATA_WORKFLOWS
                  else '.github/workflows/codeql.yml' if set(workflows) == METADATA_CALLERS['.github/workflows/codeql.yml']
                  else None)
        if caller is None or workflows[METADATA_WORKFLOW].get('sha') != 'b76ade9fd7a76da21bf2cb2161deae7a262163e8':
            continue
        approved = ({'81bcf1933edc435826e2de411a777cccd4dec7c7','15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a'}
                    if caller.endswith('/repository-checks.yml') else
                    {'e9aaaed9693efc5ffb4701697ac2a4d51f5f5ba1','3b7a88765b7181a1bc7dd6f48b9b459e590055d3'})
        if workflows[caller].get('sha') in approved and not any(
                workflows == row and sources[key] == boolean_prior for key, row in generations.items()):
            key = name + '-reviewed-helper-v2'
            require(key not in generations, 'retained Boolean helper pair name collides')
            generations[key], sources[key] = workflows, boolean_prior
    return generations, sources


def _retained_metadata_generation(policy, workflows):
    """Return the real catalog name of exactly one reviewed complete tuple."""
    matches = [name for name in RETAINED_OWNER_GENERATIONS
        if policy.generations.get(name) == workflows]
    require(len(matches) == 1, 'retained workflow tuple is unknown or ambiguous')
    return matches[0]


METADATA_TARGETS = frozenset({'main', 'apple-main', 'apple-ios', 'android-main',
                              'android-phone', 'android-vr', 'android-vr-pico'})
_PR_REUSABLES = METADATA_WORKFLOWS | frozenset('.github/workflows/' + name + '.yml' for name in (
    'native-tests', 'android-required', 'documentation-checks', 'workflow-security'))
PROTECTED_PUSH_WORKFLOWS = {
    350930890: (".github/workflows/parent-qualification.yml",
                frozenset({"main", "android-main", "android-vr", "apple-main"})),
    330551824: (".github/workflows/project-tests.yml",
                frozenset({"android-phone", "android-vr-pico", "apple-ios"})),
}
# This consumer is registered by its one fixed path, never an artifact/CLI ID.
# Its registration may be new; it cannot publish original producer authority.
DOCUMENTATION_PUSH_WORKFLOW = '.github/workflows/documentation-push-owner.yml'
DOCUMENTATION_PUSH_BRANCHES = frozenset({'main','android-phone','android-vr-pico','apple-ios'})
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


class ApiError(P.ProtocolError):
    """Complete authenticated producer evidence is unavailable."""


class OriginalAttemptUnavailable(ApiError):
    """A rerun snapshot cannot authenticate original successful execution."""


class SchedulingPending(ApiError):
    """A tiny native ordinary source may still be queued; never run a substitute."""


def require(condition, message):
    if not condition:
        raise ApiError(message)


def positive(value):
    require(type(value) is int and value > 0, "invalid positive API identity")
    return value


def sha(value):
    require(isinstance(value, str) and _SHA.fullmatch(value) and set(value) != {"0"}, "invalid immutable API SHA")
    return value


def metadata_inventory_record(row, observation):
    """Normalize progress only AFTER this adapter authenticated the exact intent.

    This helper supplies no authentication. Callers must freshly classify each
    complete run inventory at both bookends; all ordinary/historical rows retain
    their original full status/ordering data.
    """
    if type(observation) is dict and observation.get('kind') == METADATA_INTENT_KIND:
        require({key: row.get(key) for key in _SCHEDULING_RUN_FIELDS} == observation['run'],
                'native metadata intent inventory identity differs')
        return {'native_nonproducer_intent': observation}
    return row


def _scheduling_identity(source):
    return {**source, 'run': {key: source['run'].get(key) for key in _SCHEDULING_RUN_FIELDS}}


def _scheduling_candidate_matches(candidate, binding):
    """Compare authenticated immutable candidates only for result scheduling.

    The caller has already authenticated the native reusable source and read
    its immutable commit. This cannot authorize producer evidence or receipts.
    """
    sha(candidate.get('merge_sha')); sha(candidate.get('merge_tree'))
    expected = [sha(binding.get('base_sha')), sha(binding.get('head_sha'))]
    require(binding.get('merge_parents') == expected, 'scheduling live ordered candidate differs')
    return candidate['merge_tree'] == sha(binding.get('merge_tree')) and candidate.get('merge_parents') == expected


def _scheduling_context_matches(before, after):
    """Only a regenerated temporary M may differ between result bookends."""
    binding, references = before
    fresh, refs = after
    return (_scheduling_candidate_matches(fresh, binding)
        and {k: v for k, v in binding.items() if k != 'merge_sha'} ==
            {k: v for k, v in fresh.items() if k != 'merge_sha'}
        and references.get('merge') == binding['merge_sha'] and refs.get('merge') == fresh['merge_sha']
        and {k: v for k, v in references.items() if k != 'merge'} ==
            {k: v for k, v in refs.items() if k != 'merge'})


def _now():
    return datetime.now(timezone.utc)


class GitHubReadOnly:
    """Fixed github.com/fork GET boundary with deadlines and bounded pipes.

    gh follows its own authenticated archive redirect. No signed URL, token,
    stderr body, environment or arbitrary endpoint is returned in errors.
    """

    def _request(self, endpoint, maximum, *, api_version="2026-03-10"):
        require(isinstance(endpoint, str) and (endpoint == PREFIX or endpoint.startswith(PREFIX + "/"))
                and not re.search(r"[\x00-\x20\x7f]", endpoint) and ":" not in endpoint
                and ".." not in endpoint and "\\" not in endpoint, "GET endpoint is outside the reviewed fork")
        require(api_version == "2026-03-10" or api_version == "2022-11-28"
                and re.fullmatch(re.escape(PREFIX) + r"/pulls/[1-9][0-9]*", endpoint) is not None,
                "GET API version is outside the reviewed endpoint contract")
        executable = shutil.which("gh")
        roots = (Path("/usr/bin"), Path("/usr/local/bin"), Path("/opt/hostedtoolcache"))
        try:
            require(executable is not None and Path(executable).is_absolute()
                    and any(Path(executable).is_relative_to(root) for root in roots),
                    "reviewed system GitHub CLI unavailable")
            resolved = Path(executable).resolve()
            require(any(resolved.is_relative_to(root) for root in roots), "reviewed system GitHub CLI unavailable")
        except (OSError, RuntimeError):
            raise ApiError("reviewed system GitHub CLI unavailable") from None
        command = [str(resolved), "api", "--hostname", "github.com", "--method", "GET",
                   "-H", "Accept: application/vnd.github+json", "-H", "X-GitHub-Api-Version: " + api_version, endpoint]
        process = None
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            output = bytearray()
            deadline = time.monotonic() + 45
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, True)
                selector.register(process.stderr, selectors.EVENT_READ, False)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    require(remaining > 0, "GitHub GET deadline exceeded")
                    for key, _ in selector.select(min(remaining, 0.25)):
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                        elif key.data:
                            output.extend(chunk)
                            require(len(output) <= maximum, "GitHub GET response exceeds reviewed byte bound")
                        # Always drain stderr without storing or exposing it.
                require(process.wait(timeout=max(0.01, deadline - time.monotonic())) == 0,
                        "GitHub GET failed; response details withheld")
            return bytes(output)
        except (OSError, subprocess.SubprocessError):
            raise ApiError("GitHub GET unavailable; response details withheld") from None
        finally:
            if process is not None:
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                for pipe in (process.stdout, process.stderr):
                    if pipe is not None:
                        pipe.close()

    def _json(self, raw):
        def invalid_constant(value):
            raise ApiError("GitHub GET returned invalid bounded JSON")
        try:
            return json.loads(raw, object_pairs_hook=P.inputs._unique_object,
                              parse_constant=invalid_constant)
        except (UnicodeError, ValueError) as error:
            if isinstance(error, ApiError):
                raise
            raise ApiError("GitHub GET returned invalid bounded JSON") from None

    def json(self, endpoint):
        return self._json(self._request(endpoint, 2_000_000))

    def integrated_pr(self, number):
        # 2026-03-10 removed merge_commit_sha. This independently versioned
        # full-PR read is fixed, explicit and has no unversioned fallback.
        endpoint = PREFIX + f"/pulls/{positive(number)}"
        return self._json(self._request(endpoint, 2_000_000, api_version="2022-11-28"))

    def bytes(self, endpoint):
        return self._request(endpoint, P._MAX_ARCHIVE)

    def immutable_tree(self, tree_sha):
        """Bounded complete source inventory; no archive or materialized code.

        Overte's full tree exceeds the small metadata response bound. The
        independently authenticated immutable tree endpoint alone gets 20MB.
        Truncation and entry structure must still be rejected by the consumer.
        """
        return self._json(self._request(PREFIX + '/git/trees/' + sha(tree_sha) + '?recursive=1', 20_000_000))

    def immutable_blob(self, blob_sha, maximum=64_000):
        """Read one content-addressed small policy blob, never a path or ref."""
        require(type(maximum) is int and 0 < maximum <= 64_000, 'immutable blob limit exceeds the reviewed policy bound')
        identity = sha(blob_sha)
        endpoint = PREFIX + '/git/blobs/' + identity
        raw = self._request(endpoint, 100_000)
        require(type(raw) is bytes and len(raw) <= 100_000, 'immutable blob JSON exceeds its reviewed byte bound')
        value = self._json(raw)
        fields = {'sha', 'size', 'encoding', 'content'}
        require(type(value) is dict and fields <= value.keys() <= fields | {'url', 'node_id'},
                'immutable blob response has unsupported fields')
        require(value['sha'] == identity and value['encoding'] == 'base64'
            and type(value['size']) is int and 0 <= value['size'] <= maximum
            and type(value['content']) is str and len(value['content']) <= 100_000,
            'immutable blob identity, encoding or size differs from the request')
        require('url' not in value or value['url'] == 'https://api.github.com/' + endpoint,
                'immutable blob URL differs from its fixed fork identity')
        require('node_id' not in value or type(value['node_id']) is str and 0 < len(value['node_id']) <= 512,
                'immutable blob node metadata is unsupported')
        # GitHub wraps base64 with LF. No other whitespace or noncanonical
        # padding can enter the exact decoded-byte identity.
        encoded = value['content'].replace('\n', '')
        require(len(encoded) <= 4 * ((maximum + 2) // 3), 'immutable blob content exceeds its decoded byte bound')
        try:
            content = base64.b64decode(encoded.encode('ascii'), validate=True)
        except (UnicodeError, binascii.Error, ValueError):
            raise ApiError('immutable blob content is not strict base64') from None
        require(len(content) == value['size'] and base64.b64encode(content).decode('ascii') == encoded,
                'immutable blob decoded size or canonical base64 differs')
        actual = hashlib.sha1(b'blob ' + str(len(content)).encode('ascii') + b'\0' + content).hexdigest()
        require(actual == identity, 'immutable blob content differs from its Git object identity')
        return content

    def immutable_source_blob(self, blob_sha):
        """Fixed bounded original-source transport, not a policy-size override.

        Only retained source reconstruction chooses the fixed seventeen object
        identities from an authenticated complete original Git tree.
        """
        identity = sha(blob_sha)
        # Repeated native/source bookends still revalidate every source map and
        # mode. Only independently hashed immutable bytes may avoid another GET.
        cache = getattr(self, '_immutable_source_cache', None)
        if cache is not None and identity in cache:
            content = cache[identity]
            require(type(content) is bytes and len(content) <= 1_000_000
                and hashlib.sha1(b'blob ' + str(len(content)).encode('ascii') + b'\0' + content).hexdigest() == identity,
                'cached immutable source content differs')
            return content
        endpoint = PREFIX + '/git/blobs/' + identity
        raw = self._request(endpoint, 1_500_000)
        require(type(raw) is bytes and len(raw) <= 1_500_000, 'source blob JSON exceeds its bound')
        value = self._json(raw)
        fields = {'sha', 'size', 'encoding', 'content'}
        require(type(value) is dict and fields <= value.keys() <= fields | {'url', 'node_id'}
            and value['sha'] == identity and value['encoding'] == 'base64'
            and type(value['size']) is int and 0 <= value['size'] <= 1_000_000
            and type(value['content']) is str and len(value['content']) <= 1_500_000,
            'source blob identity, encoding, size or fields differ')
        require('url' not in value or value['url'] == 'https://api.github.com/' + endpoint,
            'source blob URL differs from its immutable fork identity')
        require('node_id' not in value or type(value['node_id']) is str and 0 < len(value['node_id']) <= 512,
            'source blob metadata is unsupported')
        encoded = value['content'].replace('\n', '')
        require(len(encoded) <= 4 * ((1_000_000 + 2) // 3), 'source blob exceeds decoded bound')
        try:
            content = base64.b64decode(encoded.encode('ascii'), validate=True)
        except (UnicodeError, binascii.Error, ValueError):
            raise ApiError('source blob content is not strict base64') from None
        require(len(content) == value['size'] and base64.b64encode(content).decode('ascii') == encoded
            and hashlib.sha1(b'blob ' + str(len(content)).encode('ascii') + b'\0' + content).hexdigest() == identity,
            'source blob content differs from its exact Git object identity')
        if cache is None:
            cache = self._immutable_source_cache = {}
        while cache and (len(cache) >= 17 or sum(map(len, cache.values())) + len(content) > 8_000_000):
            del cache[next(iter(cache))]
        cache[identity] = content
        return content


@dataclass(frozen=True)
class MetadataPolicy:
    caller_workflow_id: int
    caller_path: str
    generations: dict[str, dict]
    sources: dict[str, dict]


@dataclass(frozen=True)
class AdapterPolicy:
    producer: P.Policy
    caller_workflow_id: int
    caller_path: str
    generations: dict[str, dict]
    publisher_job: str
    owner_jobs: dict[str, str]
    final_publisher_prefix: str
    metadata_generations: dict[str, dict] | None = None
    metadata_sources: dict[str, dict] | None = None


@dataclass(frozen=True)
class IntegratedOrigin:
    """Internal freshly reconstructed facts; never accepted as supplied proof."""
    binding: dict
    references: dict


@dataclass(frozen=True)
class Snapshot:
    binding: dict
    references: dict
    observations: list[P.Observation]
    inventory_complete: bool
    unavailable: tuple[str, ...]
    source_chains: dict[int, dict]
    artifact_inventories: dict[int, list[dict]]
    other_candidates: dict[int, dict]
    metadata_nonproducers: dict[int, dict] = field(default_factory=dict)


def _policy(value, plan, number):
    require(isinstance(value, AdapterPolicy), "trusted controller adapter policy required")
    P.policy_digest(value.producer)
    P.validate_plan(plan)
    positive(value.caller_workflow_id)
    require(value.producer.events == ("pull_request",)
            and value.producer.workflow_ref == f"refs/pull/{number}/merge"
            and value.producer.workflow_path == ".github/workflows/project-tests.yml"
            and value.caller_path == ".github/workflows/repository-checks.yml",
            "unsupported producer source-chain contract")
    require(isinstance(value.generations, dict) and bool(value.generations), "trusted complete generations unavailable")
    for name, workflows in value.generations.items():
        require(isinstance(name, str) and name and isinstance(workflows, dict) and set(workflows) == WORKFLOWS,
                "workflow generation must bind the complete reviewed tuple")
        for entry in workflows.values():
            require(isinstance(entry, dict) and set(entry) == {"mode", "type", "sha"}
                    and entry["mode"] == "100644" and entry["type"] == "blob", "invalid trusted workflow entry")
            sha(entry["sha"])
    require(isinstance(value.owner_jobs, dict) and set(value.owner_jobs) == set(plan["owners"])
            and all(isinstance(name, str) and name for name in [value.publisher_job, *value.owner_jobs.values()])
            and len({value.publisher_job, *value.owner_jobs.values()}) == 1 + len(value.owner_jobs),
            "trusted exact publisher/owner job names unavailable")
    require(isinstance(value.final_publisher_prefix, str) and 0 < len(value.final_publisher_prefix) <= 200
            and not re.search(r"[\x00-\x1f\x7f]", value.final_publisher_prefix)
            and not any(name.startswith(value.final_publisher_prefix)
                        for name in [value.publisher_job, *value.owner_jobs.values()]),
            "trusted distinct final publisher prefix unavailable")
    if value.metadata_generations is None and value.metadata_sources is None:
        return
    _metadata_policy(MetadataPolicy(value.caller_workflow_id, value.caller_path,
                                   value.metadata_generations, value.metadata_sources))


def _metadata_policy(value):
    require(isinstance(value, MetadataPolicy) and value.caller_path in METADATA_CALLERS,
            "unsupported fixed metadata caller")
    positive(value.caller_workflow_id)
    generations, sources = value.generations, value.sources
    require(isinstance(generations, dict) and 1 <= len(generations) <= 19
            and isinstance(sources, dict) and set(sources) == set(generations),
            "complete trusted metadata source generations unavailable")
    identities = set()
    for name, workflows in generations.items():
        require(isinstance(name, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", name)
                and isinstance(workflows, dict) and set(workflows) == METADATA_CALLERS[value.caller_path]
                and isinstance(sources[name], dict) and set(sources[name]) == {METADATA_SOURCE},
                "metadata source requires a fixed complete workflow/helper pair")
        for entry in [*workflows.values(), *sources[name].values()]:
            require(isinstance(entry, dict) and set(entry) == {"mode", "type", "sha"}
                    and entry["mode"] == "100644" and entry["type"] == "blob",
                    "metadata source requires ordinary immutable blobs")
            sha(entry["sha"])
        identity = P.digest({"workflows": workflows, "sources": sources[name]})
        require(identity not in identities, "duplicate complete metadata source generation")
        identities.add(identity)


class Adapter:
    def __init__(self, api=None):
        self.api = api if api is not None else GitHubReadOnly()

    def _object(self, endpoint):
        value = self.api.json(PREFIX + ("/" + endpoint if endpoint else ""))
        require(isinstance(value, dict), "GitHub omitted a required API object")
        return value

    def _pages(self, endpoint, field, *, search=False):
        values, seen, expected = [], set(), None
        separator = "&" if "?" in endpoint else "?"
        for page in range(1, 11):
            value = self._object(endpoint + separator + f"per_page=100&page={page}")
            total, items = value.get("total_count"), value.get(field)
            require(type(total) is int and total >= 0 and isinstance(items, list) and len(items) <= 100
                    and (not search or total < 1000), "API search cap or incomplete paginated inventory")
            require(expected is None or total == expected, "API inventory changed during pagination")
            expected = total
            for item in items:
                require(isinstance(item, dict), "API page contains an invalid record")
                identity = positive(item.get("id"))
                require(identity not in seen, "API pagination repeats an identity")
                seen.add(identity)
            values.extend(items)
            require(len(values) <= expected, "API inventory exceeds its declared total")
            if len(values) == expected:
                return values
            if len(items) < 100:
                raise ApiError("API paginated inventory is incomplete")
        raise ApiError("API inventory exceeds reviewed pagination bound")

    def _ref(self, ref):
        value = self._object("git/ref/" + quote(ref, safe="/"))
        require(value.get("ref") == "refs/" + ref and value.get("object", {}).get("type") == "commit",
                "current Git ref identity unavailable")
        return sha(value["object"].get("sha"))

    def _commit(self, revision):
        value = self._object("git/commits/" + sha(revision))
        require(value.get("sha") == revision and isinstance(value.get("parents"), list)
                and all(isinstance(parent, dict) for parent in value["parents"]), "immutable commit identity mismatch")
        return sha(value.get("tree", {}).get("sha")), [sha(parent.get("sha")) for parent in value["parents"]]

    def _associated_prs(self, revision):
        """The commit association API returns arrays, without an Actions total."""
        values, seen = [], set()
        for page in range(1, 11):
            items = self.api.json(f"{PREFIX}/commits/{sha(revision)}/pulls?per_page=100&page={page}")
            require(isinstance(items, list) and len(items) <= 100, "merged PR association inventory unavailable")
            for item in items:
                require(isinstance(item, dict), "invalid merged PR association")
                identity = positive(item.get("id"))
                positive(item.get("number"))
                require(identity not in seen, "merged PR association repeats an identity")
                seen.add(identity)
            values.extend(items)
            if len(items) < 100:
                return values
        raise ApiError("merged PR association exceeds reviewed pagination bound")

    def _introduced_pr(self, revision, now, *, parents, target):
        """Classify every actual association; only its introducer supplies proof.

        Non-default commits may also be associated with open/downstream PRs.
        Their existence is not ambiguity about which PR actually merged here.
        """
        introduced, facts = [], []
        for summary in self._associated_prs(revision):
            number = positive(summary.get("number"))
            pr = self.api.integrated_pr(number)
            require(isinstance(pr, dict) and all(key in pr for key in (
                "id", "number", "state", "base", "head", "merged", "merge_commit_sha", "merged_at", "closed_at")),
                "versioned full PR identity is unavailable")
            introduces = pr["merge_commit_sha"] == revision
            snapshots = []
            identity = {}
            for value in (summary, pr):
                current = {"id": positive(value.get("id")), "number": positive(value.get("number")),
                           "state": value.get("state")}
                require(current["state"] in {"open", "closed"}, "associated PR state is unknown")
                for side in ("base", "head"):
                    branch = value.get(side)
                    repo = branch.get("repo") if isinstance(branch, dict) else None
                    require(isinstance(repo, dict) and repo.get("id") == 1319052603
                            and repo.get("full_name") == REPOSITORY,
                            "associated PR repository is outside the same-fork contract")
                    ref = branch.get("ref")
                    require(isinstance(ref, str) and 0 < len(ref) <= 255
                            and re.search(r"[\x00-\x20\x7f]", ref) is None,
                            "associated PR ref identity is unavailable")
                    current[side] = {"ref": ref, "sha": sha(branch.get("sha")),
                                     "repository_id": repo["id"], "repository": repo["full_name"]}
                if introduces:
                    require(current["base"]["ref"] == target and current["head"]["sha"] == parents[1],
                            "introducing PR differs from normal integration parents/target")
                    snapshots.append(current["base"]["sha"])
                    # These are authority facts, not a rewrite of either raw
                    # response. Snapshot SHAs are validated separately below.
                    current["base"] = {key: value for key, value in current["base"].items() if key != "sha"}
                require(not identity or identity == current, "associated PR summary/full identity differs")
                identity = current
            if introduces:
                try:
                    for snapshot in dict.fromkeys(snapshots):
                        source_admission.validate_base_snapshot(SimpleNamespace(get=self._object), snapshot, parents[0])
                except source_admission.SourceUnavailable as error:
                    raise ApiError(str(error)) from error
            require(type(pr["merged"]) is bool, "associated PR merged state is unavailable")
            merge = pr["merge_commit_sha"]
            if merge is not None:
                sha(merge)
            # No summary field is required that the 2026 API actually omits.
            # A contradictory optional claim still cannot be silently ignored.
            require(all(key not in summary or summary[key] == pr[key]
                        for key in ("merged", "merge_commit_sha", "merged_at", "closed_at")),
                    "associated PR summary/full merge facts differ")
            if pr["state"] == "open":
                require(pr["merged"] is False and pr["merged_at"] is None and pr["closed_at"] is None,
                        "open associated PR has contradictory merge facts")
            else:
                closed = P._time(pr["closed_at"])
                require(closed <= now, "associated PR close is in the future")
                if pr["merged"]:
                    require(merge is not None and P._time(pr["merged_at"]) <= closed,
                            "merged associated PR commit/time is unavailable")
                else:
                    require(pr["merged_at"] is None, "unmerged associated PR has a merge time")
            introduces = merge == revision
            require(not introduces or pr["state"] == "closed" and pr["merged"] is True,
                    "associated PR contradicts the actual protected integration")
            if introduces:
                introduced.append(pr)
            facts.append({**identity, **{key: pr[key] for key in
                          ("merged", "merge_commit_sha", "merged_at", "closed_at")},
                          "classification": "introducer" if introduces else "known-nonintroducer"})
        require(len(introduced) == 1, "integrated source introducer PR is missing or ambiguous")
        return introduced[0], sorted(facts, key=lambda value: value["id"])

    def _integrated_current(self, push_run_id, app_id, now):
        """Authenticate a normal current protected push without a topic ref.

        This is provenance for looking up an ORIGINAL PR candidate. It is not a
        receipt for executing the push commit or admission across a sync edge.
        """
        positive(push_run_id); positive(app_id)
        repository = self._object("")
        require(repository.get("id") == 1319052603 and repository.get("full_name") == REPOSITORY
                and repository.get("default_branch") == "main", "integrated repository identity changed")
        latest = self._object(f"actions/runs/{push_run_id}")
        require(positive(latest.get("run_attempt")) == 1, "protected push original attempt unavailable")
        run = self._object(f"actions/runs/{push_run_id}/attempts/1")
        fields = ("id", "workflow_id", "check_suite_id", "event", "path", "head_sha", "head_branch",
                  "run_attempt", "status", "conclusion", "run_started_at")
        require(all(run.get(key) == latest.get(key) for key in fields) and run.get("id") == push_run_id
                and run.get("event") == "push" and type(run.get("workflow_id")) is int,
                "protected push run/attempt identity unavailable")
        for key in ("repository", "head_repository"):
            value = run.get(key)
            require(isinstance(value, dict) and value.get("id") == 1319052603
                    and value.get("full_name") == REPOSITORY, "protected push repository mismatch")
        if run['workflow_id'] in PROTECTED_PUSH_WORKFLOWS:
            path, branches = PROTECTED_PUSH_WORKFLOWS[run['workflow_id']]
        else:
            require(run.get('path') == DOCUMENTATION_PUSH_WORKFLOW,
                    'unreviewed protected push consumer')
            registered = self._object('actions/workflows/documentation-push-owner.yml')
            require(positive(registered.get('id')) == run['workflow_id']
                    and registered.get('path') == DOCUMENTATION_PUSH_WORKFLOW
                    and registered.get('state') == 'active',
                    'fixed documentation consumer registration changed')
            path, branches = DOCUMENTATION_PUSH_WORKFLOW, DOCUMENTATION_PUSH_BRANCHES
        target, revision = run.get("head_branch"), sha(run.get("head_sha"))
        require(target in branches and run.get("path") == path
                and run.get("status") in P._PENDING | {"completed"}
                and (run.get("status") == "completed" and run.get("conclusion") == "success"
                     or run.get("status") in P._PENDING and run.get("conclusion") is None),
                "protected push source/status unavailable")
        workflow = self._object(f"actions/workflows/{run['workflow_id']}")
        require(workflow.get("id") == run["workflow_id"] and workflow.get("path") == path,
                "protected push workflow registration changed")
        branch = self._object("branches/" + quote(target, safe=""))
        require(branch.get("name") == target and branch.get("protected") is True
                and branch.get("commit", {}).get("sha") == revision
                and self._ref("heads/" + target) == revision, "protected push is not the exact current target")
        suite = self._object(f"check-suites/{positive(run.get('check_suite_id'))}")
        require(suite.get("id") == run["check_suite_id"] and suite.get("head_sha") == revision
                and suite.get("repository", {}).get("id") == 1319052603
                and suite.get("app", {}).get("id") == app_id, "protected push check-suite/app mismatch")
        tree, parents = self._commit(revision)
        require(len(parents) == 2, "integrated source requires a normal two-parent PR merge")
        pr, associations = self._introduced_pr(revision, now, parents=parents, target=target)
        number = positive(pr["number"])
        merged = P._time(pr.get("merged_at"))
        require(merged <= P._time(pr.get("closed_at")) <= now
                and merged <= P._time(run.get("run_started_at")) <= now,
                "integrated PR/push chronology unavailable")
        binding = {"repository": REPOSITORY, "repository_id": 1319052603, "pull_request": number,
                   "head_repository_id": 1319052603, "base_ref": pr["base"].get("ref"),
                   "base_sha": parents[0], "head_ref": pr["head"].get("ref"),
                   "head_sha": sha(pr["head"].get("sha")), "merge_sha": revision,
                   "merge_tree": tree, "merge_parents": parents}
        P.validate_binding(binding)
        require(binding["base_ref"] == target, "merged PR targets a different protected branch")
        integration = {"push_run_id": push_run_id, "push_attempt": 1, "workflow_id": run["workflow_id"],
                       "workflow_path": path, "target": target, "commit": revision, "tree": tree,
                       "parents": parents, "pull_request": number, "pr_id": pr["id"],
                       "merged_at": pr["merged_at"], "closed_at": pr["closed_at"],
                       "push_status": run["status"], "push_conclusion": run.get("conclusion")}
        references = {"integration": integration, "associated_prs": associations,
                      "target": revision, "default_ref": "main",
                      "default": self._ref("heads/main")}
        return binding, references

    def _origin_integration(self, revision, target, now):
        """Private immutable ancestor, reached only via authenticated parent0."""
        tree, parents = self._commit(revision)
        require(len(parents) == 2, 'retained integration is not a normal two-parent merge')
        pr, associations = self._introduced_pr(revision, now, parents=parents, target=target)
        binding = P.validate_binding({'repository': REPOSITORY, 'repository_id': 1319052603,
            'pull_request': positive(pr['number']), 'head_repository_id': 1319052603,
            'base_ref': target, 'base_sha': parents[0], 'head_ref': pr['head']['ref'],
            'head_sha': parents[1], 'merge_sha': revision, 'merge_tree': tree, 'merge_parents': parents})
        return binding, {'target': target, 'commit': revision, 'tree': tree, 'parents': parents,
            'pull_request': pr['number'], 'pr_id': pr['id'], 'merged_at': pr['merged_at'],
            'closed_at': pr['closed_at']}, associations

    def _origin_tree(self, tree):
        value = self.api.immutable_tree(tree)
        require(type(value) is dict and value.get('sha') == tree and value.get('truncated') is False
            and type(value.get('tree')) is list and 0 < len(value['tree']) <= 200000,
            'retained complete tree inventory is unavailable')
        result, names = {}, set()
        for row in value['tree']:
            require(type(row) is dict and type(row.get('path')) is str and row['path'] not in names,
                'retained tree member is missing or duplicated')
            names.add(row['path'])
            require(row['path'] and not row['path'].startswith('/')
                and all(part not in {'', '.', '..'} for part in row['path'].split('/'))
                and not any(ord(char) < 32 or ord(char) == 127 for char in row['path']),
                'retained directory or file path is invalid')
            sha(row.get('sha'))
            if row.get('type') == 'tree':
                require(row.get('mode') == '040000', 'retained tree directory is aliased')
                continue
            require(row.get('type') == 'blob' and row.get('mode') in {'100644', '100755'},
                'retained tree has a nonordinary member')
            result[row['path']] = {key: row.get(key) for key in ('mode', 'type', 'sha')}
        source_admission.validate_tree(result)
        return result

    def _origin_jobs(self, run, expected, now, *, jobs=None):
        jobs = jobs if jobs is not None else self._pages(f"actions/runs/{run['id']}/attempts/1/jobs", 'jobs')
        require(len(jobs) == len(expected) and {row.get('name') for row in jobs} == set(expected),
            'retained native job inventory is incomplete or unknown')
        checks = {}
        for row in jobs:
            fact = self._job(row, run, 15368, final_name=row['name'])
            require((fact.status, fact.conclusion) == ('completed', expected[row['name']]),
                'retained native validation job did not finish as selected')
            if fact.conclusion == 'success':
                require(P._time(run.get('run_started_at')) <= P._time(fact.started_at)
                    <= P._time(fact.completed_at) <= now, 'retained native job chronology differs')
            require(type(row.get('steps', [])) is list and all(type(step) is dict for step in row.get('steps', [])),
                'retained native steps are malformed')
            checks[fact.job_id] = vars(fact)
        return jobs, checks

    @staticmethod
    def _origin_step(jobs, job_name, name, conclusion, now):
        job = next(row for row in jobs if row['name'] == job_name)
        steps = [row for row in job.get('steps', []) if row.get('name') == name]
        require(len(steps) == 1 and (steps[0].get('status'), steps[0].get('conclusion')) == ('completed', conclusion),
            'retained fixed native validation step is unavailable')
        if conclusion == 'success':
            require(P._time(job['started_at']) <= P._time(steps[0].get('started_at'))
                <= P._time(steps[0].get('completed_at')) <= P._time(job['completed_at']) <= now,
                'retained validation step chronology differs')

    def _origin_pr_inventory(self, binding, policy, now):
        """Classify complete introducing-H inventory; no absent-artifact inference."""
        _metadata_policy(policy)
        require(policy.caller_path == '.github/workflows/repository-checks.yml', 'unknown retention caller')
        require(any(type(policy.generations.get(name)) is dict for name in RETAINED_OWNER_GENERATIONS),
            'fixed no-execution generation is not enrolled')
        endpoint = f"actions/workflows/{policy.caller_workflow_id}/runs?head_sha={binding['head_sha']}"
        listed = self._pages(endpoint, 'workflow_runs', search=True)
        require(bool(listed), 'retained introducing-head inventory is missing')
        classified, ordinary, bearing = {}, [], False
        for row in listed:
            identity = positive(row.get('id'))
            marker = self.metadata_observation(row, binding, policy, now=now, integrated=True)
            if marker is not None:
                classified[identity] = {'metadata': marker}
                continue
            source = self._scheduling_source(row, binding, policy, now=now, integrated=True)
            family = _retained_metadata_generation(policy, source['workflows'])
            require(source['workflows'] == policy.generations[family]
                and source['run'].get('display_title') == ORDINARY_RUN_NAME,
                'retained ordinary source recipe differs')
            run = source['run']
            require((run.get('status'), run.get('conclusion')) == ('completed', 'success'),
                'newer retained ordinary source is pending, failed or cancelled')
            candidate = source['candidate']
            require(candidate['merge_tree'] == binding['merge_tree'] and candidate['merge_parents'] == binding['merge_parents'],
                'retained ordinary original candidate differs from integration')
            jobs = self._pages(f'actions/runs/{identity}/attempts/1/jobs', 'jobs')
            artifacts = self._pages(f'actions/runs/{identity}/artifacts', 'artifacts')
            # Stop at the first execution-bearing integration, even when its
            # complete tree happens to equal its first parent. Never walk past it.
            if any(type(job.get('name')) is str and job['name'].startswith('project / ') for job in jobs) \
                    or any(type(item.get('name')) is str and item['name'].startswith('ci-') for item in artifacts):
                bearing = True
                classified[identity] = {'execution_source': source, 'jobs': jobs, 'artifacts': artifacts}
                continue
            expected = {METADATA_JOB: 'success', 'Select required repository checks': 'success',
                'native': 'skipped', 'project': 'skipped', 'android': 'skipped',
                'documentation / documentation': 'success',
                'workflow-security / Actionlint, Zizmor, and Gitleaks': 'success',
                'workflow-contracts': 'success', 'repository-checks': 'success'}
            jobs, checks = self._origin_jobs(run, expected, now, jobs=jobs)
            self._origin_step(jobs, METADATA_JOB, ORDINARY_SOURCE_STEP + ' (diagnostics absent)', 'success', now)
            self._origin_step(jobs, 'repository-checks', 'Require all selected checks to succeed', 'success', now)
            require(not artifacts, 'unchanged PR published unexpected execution or other artifacts')
            ordinary.append(identity)
            classified[identity] = {'source': source, 'jobs': jobs, 'checks': checks, 'artifacts': artifacts}
        require(self._pages(endpoint, 'workflow_runs', search=True) == listed, 'retained PR source inventory changed')
        require(bool(ordinary) or bearing, 'retained ordinary source is unavailable')
        return not bearing, {'listed': listed, 'classified': classified}

    def _origin_empty_push(self, binding, integration, policy, now, *, current_run=None):
        target, revision = binding['base_ref'], binding['merge_sha']
        _, _, workflows = self._workflow_tuple(revision, paths=METADATA_CALLERS[policy.caller_path])
        _retained_metadata_generation(policy, workflows)
        original_source = self._metadata_source(binding['base_sha'])
        require(any(workflows == row and original_source == policy.sources[name]
                    for name,row in policy.generations.items()),
            'retained unchanged workflow/helper recipe differs')
        endpoint = f'actions/workflows/350930890/runs?branch={quote(target, safe="")}&event=push&head_sha={revision}'
        listed = self._pages(endpoint, 'workflow_runs', search=True)
        require(bool(listed) and all(row.get('event') == 'push' and row.get('head_sha') == revision
            and row.get('head_branch') == target and row.get('workflow_id') == 350930890
            and row.get('path') == '.github/workflows/parent-qualification.yml' for row in listed),
            'retained push inventory is unavailable or foreign')
        starts = [P._time(row.get('run_started_at')) for row in listed]
        require(max(starts) <= now and starts.count(max(starts)) == 1, 'retained newest push is ambiguous')
        run_id = positive(listed[starts.index(max(starts))].get('id'))
        require(current_run is None or run_id == current_run, 'current no-execution push is not newest')
        latest = self._object(f'actions/runs/{run_id}')
        attempt = self._object(f'actions/runs/{run_id}/attempts/1')
        row = next(row for row in listed if row['id'] == run_id)
        fields = ('id','workflow_id','check_suite_id','event','path','head_sha','head_branch','run_attempt',
            'status','conclusion','run_started_at','updated_at','referenced_workflows')
        require(all(row.get(key) == latest.get(key) == attempt.get(key) for key in fields)
            and latest.get('run_attempt') == 1 and (latest.get('status'), latest.get('conclusion')) == ('completed','success')
            and all(latest.get(key, {}).get('id') == 1319052603 and latest[key].get('full_name') == REPOSITORY
                    for key in ('repository', 'head_repository')), 'retained push is not successful original native source')
        workflow = self._object('actions/workflows/350930890')
        require(workflow.get('id') == 350930890 and workflow.get('path') == '.github/workflows/parent-qualification.yml',
            'retained parent workflow registration differs')
        require(P._time(integration['merged_at']) <= P._time(latest.get('run_started_at')) <= now,
            'retained merge/push chronology differs')
        suite = self._object(f"check-suites/{positive(latest.get('check_suite_id'))}")
        require(suite.get('id') == latest['check_suite_id'] and suite.get('head_sha') == revision
            and suite.get('app',{}).get('id') == 15368 and suite.get('repository',{}).get('id') == 1319052603,
            'retained push suite/App differs')
        expected_jobs = {'Plan current parent owners': 'success' if target in {'android-main','android-vr'} else 'skipped',
            'Common parent tests': 'success', 'Android platform tests': 'skipped', 'Qualify exact parent': 'success'}
        jobs, checks = self._origin_jobs(latest, expected_jobs, now)
        self._origin_step(jobs, 'Common parent tests', 'Authenticate the protected base commitment before repository imports', 'success', now)
        self._origin_step(jobs, 'Common parent tests', 'Independently verify unchanged parent inputs', 'success', now)
        for name in ('Execute common parent suites without claiming platform evidence', 'Run complete host qualification',
                'Run independently selected parent host contracts', 'Create content-addressed qualification evidence',
                'Upload immutable qualification evidence', 'Check only affected tool dependencies and behavior',
                'Check independently selected S3 package dependencies and behavior'):
            self._origin_step(jobs, 'Common parent tests', name, 'skipped', now)
        self._origin_step(jobs, 'Qualify exact parent', 'Require protected parent aggregate source admission', 'success', now)
        self._origin_step(jobs, 'Qualify exact parent', 'Require both actual parent owners', 'success', now)
        artifacts = self._pages(f'actions/runs/{run_id}/artifacts', 'artifacts')
        require(all(type(item.get('name')) is str and item['name'] == f'parent-qualification-reports-{revision}-1'
            for item in artifacts) and len(artifacts) <= 1, 'unchanged push published unknown or execution authority')
        require(self._pages(endpoint, 'workflow_runs', search=True) == listed, 'retained push inventory changed')
        return {'run': latest, 'suite': suite, 'jobs': jobs, 'checks': checks, 'artifacts': artifacts, 'listed': listed}

    def integrated_origin(self, push_run_id, app_id, metadata_policy=None, *, now=None):
        """Reconstruct a bounded original anchor from CURRENT authenticated P1.

        Internal typed facts confer no authority by construction: every actual
        capture reconstructs this chain from native/current/immutable API facts.
        No historical SHA, caller-created context or callback selects an origin.
        """
        now = _now() if now is None else now
        P._now(now)
        current, references = self._integrated_current(push_run_id, app_id, now)
        if metadata_policy is None or current['base_ref'] not in {'main', 'apple-main', 'android-main', 'android-vr'}:
            # Leaves retain their existing strict lookup. Their project router
            # independently skips full-host/package/platform work for empty Git
            # inputs; only parent recipes have the completed no-execution job.
            return IntegratedOrigin(current, references)
        _metadata_policy(metadata_policy)
        if not any(name in metadata_policy.generations for name in RETAINED_OWNER_GENERATIONS):
            return IntegratedOrigin(current, references)
        binding, integration, associations = current, references['integration'], references['associated_prs']
        hops = []
        while True:
            previous_tree, _ = self._commit(binding['base_sha'])
            if previous_tree != binding['merge_tree']:
                break
            _, _, workflows = self._workflow_tuple(binding['merge_sha'], paths=METADATA_CALLERS[metadata_policy.caller_path])
            if not any(metadata_policy.generations.get(name) == workflows
                       for name in RETAINED_OWNER_GENERATIONS):
                # No old/unknown recipe is transparent. Preserve the original
                # strict execution lookup at this integration, never skip it.
                break
            transparent, inventory = self._origin_pr_inventory(binding, metadata_policy, now)
            if not transparent:
                break
            require(len(hops) < 8, 'same-tree retained origin exceeds the fixed hop cap')
            self._origin_tree(binding['merge_tree'])
            push = self._origin_empty_push(binding, integration, metadata_policy, now,
                current_run=push_run_id if not hops else None)
            hops.append({'binding': binding, 'integration': integration, 'associations': associations,
                'ordinary_inventory': inventory, 'no_execution_push': push})
            next_binding, next_integration, next_associations = self._origin_integration(binding['base_sha'], binding['base_ref'], now)
            require(next_binding['merge_tree'] == binding['merge_tree']
                and P._time(next_integration['merged_at']) <= P._time(integration['merged_at']),
                'retained first-parent tree or merge chronology changed')
            binding, integration, associations = next_binding, next_integration, next_associations
        origin_refs = references if not hops else {**references, 'origin_integration': integration,
            'origin_associated_prs': associations, 'retained_no_execution_hops': hops}
        return IntegratedOrigin(binding, origin_refs)

    def current(self, number):
        positive(number)
        repository = self._object("")
        require(repository.get("full_name") == REPOSITORY and repository.get("id") == 1319052603,
                "repository API identity mismatch")
        pr = self._object(f"pulls/{number}")
        require(pr.get("number") == number and pr.get("state") == "open", "current open PR unavailable")
        for side in ("base", "head"):
            repo = pr.get(side, {}).get("repo", {})
            require(repo.get("full_name") == REPOSITORY and repo.get("id") == 1319052603,
                    "foreign-head source-chain contract is not implemented")
        # The PR payload base SHA is a snapshot. Only M's actual first
        # parent plus independent protected live target/head refs selects B.
        merge_commit = self._object(f"commits/refs/pull/{number}/merge")
        try:
            resolved = source_admission.resolve_pr_base(SimpleNamespace(get=self._object), pr, merge_commit)
        except source_admission.SourceUnavailable as error:
            raise ApiError(str(error)) from error
        base, head, merge = resolved['base'], resolved['head'], resolved['source']
        binding = {"repository": REPOSITORY, "repository_id": 1319052603, "pull_request": number,
                   "head_repository_id": pr["head"]["repo"]["id"], "base_ref": resolved['target'],
                   "base_sha": base, "head_ref": resolved['head_ref'], "head_sha": head,
                   "merge_sha": merge, "merge_tree": "1" * 40, "merge_parents": [base, head]}
        P.validate_binding(binding)
        default = repository.get("default_branch")
        require(isinstance(default, str) and default, "current default branch unavailable")
        P.validate_binding({**binding, "head_ref": default})
        references = {"base": self._ref("heads/" + binding["base_ref"]),
                      "head": self._ref("heads/" + binding["head_ref"]),
                      "merge": merge, "default_ref": default,
                      "default": self._ref("heads/" + default)}
        require([references[key] for key in ("base", "head", "merge")] == [base, head, merge],
                "live PR and Git refs disagree")
        tree, parents = self._commit(merge)
        require(merge_commit["commit"].get("tree", {}).get("sha") == tree
                and [parent.get("sha") for parent in merge_commit["parents"]] == parents == [base, head],
                "current PR merge ref differs from its immutable ordered parents/tree")
        binding.update(merge_tree=tree, merge_parents=parents)
        return P.validate_binding(binding), references

    def _workflow_tuple(self, revision, *, paths=WORKFLOWS):
        tree, parents = self._commit(revision)
        cursor = tree
        for directory in (".github", "workflows"):
            value = self._object("git/trees/" + cursor)
            require(value.get("sha") == cursor and value.get("truncated") is False and isinstance(value.get("tree"), list)
                    and all(isinstance(entry, dict) for entry in value["tree"]),
                    "immutable workflow tree is unavailable or truncated")
            found = [entry for entry in value["tree"] if entry.get("path") == directory]
            require(len(found) == 1 and found[0].get("mode") == "040000" and found[0].get("type") == "tree",
                    "workflow directory is missing or aliased")
            cursor = sha(found[0].get("sha"))
        value = self._object("git/trees/" + cursor)
        require(value.get("sha") == cursor and value.get("truncated") is False and isinstance(value.get("tree"), list)
                and all(isinstance(entry, dict) for entry in value["tree"]),
                "immutable workflow inventory is unavailable or truncated")
        workflows = {}
        for path in paths:
            found = [entry for entry in value["tree"] if entry.get("path") == path.rsplit("/", 1)[1]]
            require(len(found) == 1, "complete caller generation is missing or ambiguous")
            workflows[path] = {key: found[0].get(key) for key in ("mode", "type", "sha")}
        return tree, parents, workflows

    def _metadata_source(self, revision):
        """Read the one fixed helper through ordinary immutable directories."""
        cursor, _ = self._commit(revision)
        parts = METADATA_SOURCE.split("/")
        for index, name in enumerate(parts):
            value = self._object("git/trees/" + cursor)
            require(value.get("sha") == cursor and value.get("truncated") is False
                    and isinstance(value.get("tree"), list)
                    and all(isinstance(entry, dict) for entry in value["tree"]),
                    "immutable metadata helper inventory unavailable")
            matches = [entry for entry in value["tree"] if entry.get("path") == name]
            require(len(matches) == 1, "metadata helper source missing or ambiguous")
            entry = matches[0]
            sha(entry.get("sha"))
            if index == len(parts) - 1:
                require(entry.get("mode") == "100644" and entry.get("type") == "blob",
                        "metadata helper source is nonregular")
                return {METADATA_SOURCE: {key: entry[key] for key in ("mode", "type", "sha")}}
            require(entry.get("mode") == "040000" and entry.get("type") == "tree",
                    "metadata helper parent is missing or aliased")
            cursor = entry["sha"]

    def metadata_observation(self, listed, binding, policy, *, integrated=False, now=None,
                             observation_clock=None, scheduling_progress=False):
        """Classify a finite native non-producer; this never supplies a result.

        The referenced reusable workflow authenticates original M. Marker text,
        missing descriptors and caller-provided run IDs cannot establish it.
        The reviewed helper/recipe must enforce a one-way route after its marker.
        """
        _metadata_policy(policy)
        P.validate_binding(binding)
        require(type(scheduling_progress) is bool, 'invalid scheduling progress mode')
        if observation_clock is None:
            observation_clock = _now if now is None else lambda: now
        require(callable(observation_clock), 'invalid metadata observation clock')
        now = observation_clock() if now is None else now
        P._now(now)
        identity = positive(listed.get("id"))
        latest = self._object(f"actions/runs/{identity}")
        attempt_number = positive(latest.get("run_attempt"))
        if attempt_number > 1 and policy.caller_path == '.github/workflows/codeql.yml':
            source = self._scheduling_source(listed, binding, policy, now=now, integrated=integrated,
                observation_clock=observation_clock, scheduling_progress=True)
            require(source.get('codeql_result_continuation') is not None
                and source['run'].get('display_title') == ORDINARY_RUN_NAME,
                'CodeQL retry is not an authenticated ordinary source')
            return None
        if attempt_number != 1:
            raise OriginalAttemptUnavailable("original metadata attempt unavailable")
        attempt = self._object(f"actions/runs/{identity}/attempts/1")
        fields = ("id", "workflow_id", "check_suite_id", "path", "event", "head_sha", "head_branch",
                  "run_attempt", "status", "conclusion", "run_started_at", "updated_at", "display_title")
        current_intent_recipes = any((policy.caller_path, entries[policy.caller_path]['sha'],
            entries[METADATA_WORKFLOW]['sha']) in _NATIVE_INTENT_RECIPES for entries in policy.generations.values())
        if attempt.get('display_title') == NONPRODUCER_RUN_NAME or current_intent_recipes \
                and attempt.get('display_title') not in {NONPRODUCER_RUN_NAME, ORDINARY_RUN_NAME}:
            intent = self._native_metadata_intent(listed, binding, policy, now=now,
                integrated=integrated, observation_clock=observation_clock)
            if intent is not None:
                return intent
        if scheduling_progress and attempt.get('display_title') == ORDINARY_RUN_NAME:
            # Only scheduling may wait for a complete original observation.
            # Authenticate the entire immutable source before classifying a
            # mutable native read as pending; this never excludes a producer.
            source = self._scheduling_source(listed, binding, policy, now=now,
                integrated=integrated, observation_clock=observation_clock,
                scheduling_progress=True)
            recipe = (policy.caller_path, source['workflows'][policy.caller_path]['sha'],
                      source['workflows'][METADATA_WORKFLOW]['sha'])
            if recipe in _NATIVE_INTENT_RECIPES:
                return None
        require(all(listed.get(key) == latest.get(key) == attempt.get(key) for key in fields),
                "metadata run/attempt inventory changed")
        references = attempt.get("referenced_workflows")
        prefix = REPOSITORY + "/" + METADATA_WORKFLOW + "@"
        matches = [item for item in references if isinstance(item, dict)
                   and str(item.get("path", "")).startswith(prefix)] if isinstance(references, list) else []
        if not matches:
            return None
        # A reusable edge can be reported even when its job was skipped. It is
        # no exclusion claim until the fixed job AND marker actually succeeded;
        # ordinary producer evidence must retain its existing strict path.
        jobs = self._pages(f"actions/runs/{identity}/attempts/1/jobs", "jobs")
        markers = [job for job in jobs if job.get("name") == METADATA_JOB]
        require(len(markers) <= 1, "metadata native source job is ambiguous")
        if not markers or (markers[0].get("status"), markers[0].get("conclusion")) != ("completed", "success"):
            return None
        marker = markers[0]
        require(isinstance(marker.get("steps"), list)
                and all(isinstance(step, dict) for step in marker["steps"]), "metadata marker steps malformed")
        steps = [step for step in marker["steps"] if step.get("name") == METADATA_STEP]
        require(len(steps) <= 1, "one-way metadata marker is ambiguous")
        if not steps or (steps[0].get("status"), steps[0].get("conclusion")) != ("completed", "success"):
            return None
        require(len(matches) == 1 and binding["base_ref"] in METADATA_TARGETS
                and attempt.get("repository", {}).get("id") == 1319052603
                and attempt.get("repository", {}).get("full_name") == REPOSITORY
                and attempt.get("head_repository", {}).get("id") == binding["head_repository_id"] == 1319052603
                and attempt.get("head_repository", {}).get("full_name") == REPOSITORY
                and attempt.get("workflow_id") == policy.caller_workflow_id
                and attempt.get("path") == policy.caller_path and attempt.get("event") == "pull_request"
                and attempt.get("head_sha") == binding["head_sha"]
                and attempt.get("head_branch") == binding["head_ref"],
                "metadata caller repository/source differs")
        associated = attempt.get("pull_requests")
        require(isinstance(associated, list) and (integrated and not associated or
                sum(isinstance(item, dict) and item.get("number") == binding["pull_request"]
                    for item in associated) == 1), "metadata PR association missing or ambiguous")
        revision = sha(matches[0].get("sha"))
        ref = f"refs/pull/{binding['pull_request']}/merge"
        require(all(isinstance(item, dict) and item.get("sha") == revision and item.get("ref") == ref
                    and item.get("path") in {REPOSITORY + "/" + path + "@" + revision
                                             for path in METADATA_CALLERS[policy.caller_path]}
                    for item in references), "unknown or mixed metadata reusable source")
        tree, parents, workflows = self._workflow_tuple(revision, paths=METADATA_CALLERS[policy.caller_path])
        require(len(parents) == 2 and parents[1] == binding["head_sha"],
                "metadata source lacks exact original ordered PR parents")
        if revision == binding["merge_sha"]:
            require(tree == binding["merge_tree"] and parents == binding["merge_parents"],
                    "metadata original candidate tree/parents differ")
        source = self._metadata_source(parents[0])
        generations = [name for name, expected in policy.generations.items()
                       if workflows == expected and source == policy.sources[name]]
        require(len(generations) == 1, "metadata workflow/helper generation is unknown or mixed")
        suite = self._object(f"check-suites/{positive(attempt.get('check_suite_id'))}")
        require(suite.get("id") == attempt["check_suite_id"] and suite.get("head_sha") == binding["head_sha"]
                and suite.get("repository", {}).get("id") == 1319052603
                and suite.get("repository", {}).get("full_name") == REPOSITORY
                and suite.get("app", {}).get("id") == 15368,
                "metadata native check suite/app differs")
        require(attempt.get("status") in P._PENDING | {"completed"}
                and (attempt["status"] == "completed") == (attempt.get("conclusion") in P._CONCLUSIONS),
                "metadata native run status is inconsistent")
        require(all("steps" not in job or isinstance(job["steps"], list)
                    and all(isinstance(step, dict) for step in job["steps"]) for job in jobs),
                "metadata native job steps are malformed")
        if any((policy.caller_path == ".github/workflows/repository-checks.yml"
                and isinstance(job.get("name"), str) and job["name"].startswith("project / "))
               or job.get("name") in {"CodeQL (javascript-typescript)", "CodeQL (python)"}
               or any(isinstance(step, dict) and step.get("name") == "Analyze"
                      and step.get("conclusion") != "skipped" for step in job.get("steps", [])) for job in jobs):
            return None
        checks, names = {}, set()
        for job in jobs:
            require(isinstance(job.get("name"), str) and job["name"] and job["name"] not in names,
                    "metadata job name unavailable or ambiguous")
            names.add(job["name"])
            fact = self._job(job, attempt, 15368, final_name=job["name"])
            require(fact.status in P._PENDING | {"completed"}
                    and (fact.status == "completed") == (fact.conclusion in P._CONCLUSIONS),
                    "metadata native job status is inconsistent")
            checks[fact.job_id] = vars(fact)
        require(P._time(attempt.get("run_started_at")) <= P._time(marker.get("started_at"))
                <= P._time(steps[0].get("started_at")) <= P._time(steps[0].get("completed_at"))
                <= P._time(marker.get("completed_at")) <= now, "metadata marker is outside its original native job")
        artifacts = self._pages(f"actions/runs/{identity}/artifacts", "artifacts")
        if artifacts:
            return None
        return {"kind": "authenticated-metadata-nonproducer", "generation": generations[0],
                "candidate": {"merge_sha": revision, "merge_tree": tree, "merge_parents": parents},
                "source": source, "run": {key: attempt.get(key) for key in fields},
                "references": references, "jobs": jobs, "checks": checks, "artifacts": artifacts}

    def _codeql_carried_jobs(self, current, originals, result, now):
        """Authenticate retry inventory mirrors; original1 keeps all authority."""
        before = {job.get('name'):job for job in originals if job.get('name') != 'codeql-security-results'}
        carried = [job for job in current if job.get('name') != 'codeql-security-results']
        require(len(before) == len(originals)-1 and len(carried) == len(before)
            and {job.get('name') for job in carried} == set(before),
            'CodeQL carried inventory is incomplete, mixed or unknown')
        retry_start = P._time(result.get('run_started_at'))
        identities = {positive(job.get('id')) for job in originals}
        require(len(identities) == len(originals)
            and len({positive(job.get('id')) for job in current}) == len(current),
            'CodeQL native job identity is repeated')
        # These are transport/record identities, not execution fields. GitHub
        # gives carried rows new IDs/creation times and omits runner_group_id.
        metadata = {'id','node_id','url','html_url','check_run_url','run_attempt','created_at','runner_group_id'}
        checks = {}
        for job in carried:
            original = before[job['name']]
            fact = self._job(job,result,15368,final_name=job['name'])
            require(fact.job_id not in identities and (fact.status,fact.conclusion) == ('completed','success')
                and set(job) == set(original)
                and {key:value for key,value in job.items() if key not in metadata}
                    == {key:value for key,value in original.items() if key not in metadata}
                and job.get('runner_group_id') in (None,original.get('runner_group_id')),
                'CodeQL carried native execution differs from original1')
            require(P._time(job.get('started_at')) <= P._time(job.get('completed_at')) <= retry_start,
                'CodeQL carried execution is not wholly before retry')
            if 'created_at' in job:
                require(retry_start <= P._time(job['created_at']) <= now,
                    'CodeQL carried record was not created by this retry')
            checks[fact.job_id] = vars(fact)
        return carried, checks

    def codeql_result_attempts(self, run_id, source, head, *, attempt, now=None, completed=False):
        """Authenticate one whole native analysis attempt and its real result gate.

        A full fresh current attempt never borrows prior analyses. The sole
        continuation is result-only attempt2 after successful analysis1 and a
        failure confined to its result-verification step. No object is aliased.
        """
        now = _now() if now is None else now
        P._now(now); positive(run_id); sha(source); sha(head); positive(attempt)
        require(type(completed) is bool, 'invalid CodeQL completion mode')
        latest = self._object(f'actions/runs/{run_id}')
        result = self._object(f'actions/runs/{run_id}/attempts/{attempt}')
        registered = self._object('actions/workflows/codeql.yml')
        require(registered.get('path') == '.github/workflows/codeql.yml' and registered.get('state') == 'active',
                'CodeQL result workflow is not registered')
        fields = ('id','workflow_id','check_suite_id','path','event','head_sha','head_branch',
                  'run_number','display_title','run_attempt','run_started_at','status','conclusion')
        require(all(latest.get(key) == result.get(key) for key in fields)
                and latest.get('id') == run_id and latest.get('workflow_id') == positive(registered.get('id'))
                and latest.get('path') == '.github/workflows/codeql.yml' and latest.get('head_sha') == head
                and latest.get('event') in {'pull_request','push','schedule'}
                and latest.get('run_attempt') == attempt, 'CodeQL attempt source changed')
        _, parents, workflows = self._workflow_tuple(source, paths=METADATA_CALLERS['.github/workflows/codeql.yml'])
        require(workflows == {'.github/workflows/codeql.yml': {'mode':'100644','type':'blob','sha':CODEQL_UPLOAD_WORKFLOW},
                METADATA_WORKFLOW: {'mode':'100644','type':'blob','sha':'b76ade9fd7a76da21bf2cb2161deae7a262163e8'}},
                'CodeQL upload recipe is not the exact protected generation')
        if result['event'] == 'pull_request':
            require(len(parents) == 2 and parents[1] == head and result.get('display_title') == ORDINARY_RUN_NAME,
                    'CodeQL upload source lacks ordered ordinary PR identity')
        current_jobs = self._pages(f'actions/runs/{run_id}/attempts/{attempt}/jobs', 'jobs')
        gates = [job for job in current_jobs if job.get('name') == 'codeql-security-results']
        non_gates = [job for job in current_jobs if job.get('name') != 'codeql-security-results']
        old_clock = (attempt == 2 and result['event'] == 'pull_request' and non_gates
            and any(P._time(job.get('started_at')) < P._time(result.get('run_started_at')) for job in non_gates))
        continuation = attempt == 2 and len(gates) == 1 and (len(current_jobs) == 1 or old_clock)
        analysis_attempt = 1 if continuation else attempt
        analysis = self._object(f'actions/runs/{run_id}/attempts/1') if continuation else result
        originals = self._pages(f'actions/runs/{run_id}/attempts/1/jobs','jobs') if continuation else current_jobs
        carried, carried_checks = ([],{})
        if continuation and non_gates:
            carried, carried_checks = self._codeql_carried_jobs(current_jobs,originals,result,now)
        if continuation:
            require(result['event'] == 'pull_request' and analysis.get('run_attempt') == 1
                and all(analysis.get(key) == result.get(key) for key in (
                    'id','workflow_id','path','event','head_sha','head_branch','run_number','display_title'))
                and (analysis.get('status'),analysis.get('conclusion')) == ('completed','failure')
                and P._time(analysis.get('updated_at')) <= P._time(result.get('run_started_at')),
                'CodeQL result retry has no matching failed original')
        if result['event'] == 'pull_request':
            associations = result.get('pull_requests')
            require(type(associations) is list and len(associations) == 1 and type(associations[0]) is dict,
                    'CodeQL original PR association unavailable')
            number = positive(associations[0].get('number'))
            refs = result.get('referenced_workflows')
            require(type(refs) is list and refs and all(type(row) is dict
                and row.get('sha') == source and row.get('ref') == f'refs/pull/{number}/merge'
                and row.get('path') in {REPOSITORY+'/'+path+'@'+source for path in workflows} for row in refs)
                and len({row['path'] for row in refs}) == len(refs)
                and any(row['path'] == REPOSITORY+'/'+METADATA_WORKFLOW+'@'+source for row in refs)
                and all(run.get('referenced_workflows') == refs and run.get('pull_requests') == associations
                        for run in (latest,analysis)), 'CodeQL native source chain differs across attempts')
        for run in (latest,result,analysis):
            require(all(run.get(key,{}).get('id') == 1319052603 and run[key].get('full_name') == REPOSITORY
                        for key in ('repository','head_repository')), 'foreign CodeQL upload run')
            require(run.get('status') in P._PENDING | {'completed'}
                and ((run['status'] == 'completed' and run.get('conclusion') in P._CONCLUSIONS)
                     or run['status'] in P._PENDING and run.get('conclusion') is None),
                'CodeQL native result status is malformed')
            require(P._time(run.get('run_started_at')) <= P._time(run.get('updated_at')) <= now,
                    'CodeQL native result chronology differs')
            suite = self._object(f"check-suites/{positive(run.get('check_suite_id'))}")
            require(suite.get('id') == run['check_suite_id'] and suite.get('head_sha') == head
                and suite.get('app',{}).get('id') == 15368
                and suite.get('repository',{}).get('id') == 1319052603
                and suite['repository'].get('full_name') == REPOSITORY, 'CodeQL native App/source differs')
        allowed_status = {('completed','success')} if completed else {(state,None) for state in P._PENDING} | {('completed','success')}
        require(all((run['status'],run.get('conclusion')) in allowed_status for run in (latest,result)),
                'CodeQL result failed or remains pending')
        names = [job.get('name') for job in originals]
        require(len(names) == len(set(names)), 'CodeQL analysis job names are ambiguous')
        selected = [language for language in ('javascript-typescript','python') if f'CodeQL ({language})' in names]
        # Actions expands an executed reusable workflow into its nested job
        # name. A call skipped at the parent event guard retains the call name.
        metadata_job = METADATA_JOB if analysis['event'] == 'pull_request' else 'Authenticate PR text edit'
        allowed = {metadata_job,'Select affected CodeQL languages','codeql-security-results',
                   *(f'CodeQL ({language})' for language in selected)}
        require(set(names) == allowed, 'CodeQL analysis job inventory is incomplete or unknown')
        checks = {}
        for job in originals:
            fact = self._job(job,analysis,15368,final_name=job['name']); checks[fact.job_id] = vars(fact)
            if job['name'] == 'codeql-security-results':
                if continuation:
                    require((fact.status,fact.conclusion) == ('completed','failure'),
                            'CodeQL retry has no original failed result gate')
                    steps = job.get('steps')
                    require(type(steps) is list and steps and all(type(step) is dict for step in steps),
                            'CodeQL original gate steps unavailable')
                    failed = [step for step in steps if step.get('conclusion') in {'failure','cancelled','timed_out'}]
                    require(len(failed) == 1 and failed[0].get('name') == 'Require current selected-language security results'
                        and all(step.get('status') == 'completed' and step.get('conclusion') in {'success','skipped','failure'}
                                for step in steps), 'CodeQL original failure was not confined to result verification')
                else:
                    require((fact.status,fact.conclusion) in allowed_status, 'current CodeQL native gate failed')
                continue
            expected = 'skipped' if job['name'] == metadata_job and analysis['event'] != 'pull_request' else 'success'
            require((fact.status,fact.conclusion) == ('completed',expected), 'CodeQL current selector/analyzer did not succeed')
        if continuation:
            fact = self._job(gates[0],result,15368,final_name='codeql-security-results')
            require((fact.status,fact.conclusion) in allowed_status, 'CodeQL retry native gate failed or unavailable')
            if fact.started_at is None:
                require(fact.status in P._PENDING-{'in_progress'} and fact.completed_at is None,
                    'CodeQL retry result has no actual execution interval')
            else:
                require(P._time(result.get('run_started_at')) <= P._time(fact.started_at) <= now
                    and (fact.completed_at is None or P._time(fact.started_at) <= P._time(fact.completed_at) <= now),
                    'CodeQL retry result gate did not execute in its actual attempt')
            checks[fact.job_id] = vars(fact)
        return {'analysis_attempt':analysis_attempt,'result_attempt':attempt,'source_commit':source,
                'analysis_run':analysis,'result_run':result,'latest_run':latest,
                'analysis_jobs':originals,'result_jobs':current_jobs,'native_checks':checks,'languages':selected,
                **({'carried_forward_jobs':carried,'carried_forward_checks':carried_checks} if carried else {})}

    def _scheduling_source(self, listed, binding, policy, *, now, integrated=False,
                           allow_intent_progress=False, observation_clock=None,
                           scheduling_progress=False):
        """Native same-M provenance only; no descriptor, E, result or authority.

        A reusable reference alone does not classify a queued invocation. The
        exact new recipe additionally binds the native rendered intent name;
        an ordinary scheduling owner separately needs its fixed source step.
        """
        _metadata_policy(policy)
        require(type(scheduling_progress) is bool, 'invalid scheduling progress mode')
        identity = positive(listed.get('id'))
        latest = self._object(f'actions/runs/{identity}')
        continuation = None
        if positive(latest.get('run_attempt')) > 1 and policy.caller_path == '.github/workflows/codeql.yml':
            # The factory resolves genuine fresh execution versus native carried
            # rows; job count alone cannot select the analysis attempt.
            edges = [row for row in latest.get('referenced_workflows', []) if type(row) is dict
                and row.get('path', '').startswith(REPOSITORY + '/' + METADATA_WORKFLOW + '@')]
            require(len(edges) == 1, 'CodeQL result retry original native source is unavailable')
            continuation = self.codeql_result_attempts(identity, sha(edges[0].get('sha')),
                binding['head_sha'], attempt=latest['run_attempt'], now=now)
        require(latest.get('run_attempt') == (continuation['result_attempt'] if continuation else 1), 'scheduling original attempt unavailable')
        run = continuation['analysis_run'] if continuation else self._object(f'actions/runs/{identity}/attempts/1')
        fields = ('id', 'workflow_id', 'check_suite_id', 'path', 'event', 'head_sha', 'head_branch',
                  'run_attempt', 'run_number', 'status', 'conclusion', 'run_started_at', 'updated_at', 'display_title')
        require(all(listed.get(key) == latest.get(key) and (continuation is not None and key in {
                    'run_attempt','check_suite_id'} or latest.get(key) == run.get(key))
                    for key in _SCHEDULING_RUN_FIELDS if key != 'display_title')
            and run.get('run_attempt') == (continuation['analysis_attempt'] if continuation else 1)
            and binding['base_ref'] in METADATA_TARGETS,
            'scheduling original native attempt changed')
        positive(run.get('run_number'))
        require(run.get('workflow_id') == policy.caller_workflow_id
            and run.get('path') == policy.caller_path and run.get('event') == 'pull_request'
            and run.get('head_sha') == binding['head_sha'] and run.get('head_branch') == binding['head_ref']
            and all(run.get(key, {}).get('id') == 1319052603
                    and run[key].get('full_name') == REPOSITORY for key in ('repository', 'head_repository')),
            'scheduling caller or repository changed')
        associated = run.get('pull_requests')
        require(type(associated) is list and (integrated and not associated or len(associated) == 1
            and type(associated[0]) is dict and associated[0].get('number') == binding['pull_request']),
            'scheduling PR association differs')
        refs = run.get('referenced_workflows')
        edges = [row for row in refs if type(row) is dict and row.get('path', '').startswith(
            REPOSITORY + '/' + METADATA_WORKFLOW + '@')] if type(refs) is list else []
        if not edges:
            raise SchedulingPending('scheduling native source edge unavailable')
        require(len(edges) == 1, 'scheduling native source edge is ambiguous')
        revision = sha(edges[0].get('sha')); ref = f"refs/pull/{binding['pull_request']}/merge"
        allowed = _PR_REUSABLES if policy.caller_path.endswith('/repository-checks.yml') else METADATA_CALLERS[policy.caller_path]
        require(type(refs) is list and bool(refs) and all(type(row) is dict
            and row.get('sha') == revision and row.get('ref') == ref
            and row.get('path') in {REPOSITORY + '/' + path + '@' + revision for path in allowed} for row in refs)
            and len({row['path'] for row in refs}) == len(refs)
            and sum(row['path'] == REPOSITORY + '/' + METADATA_WORKFLOW + '@' + revision for row in refs) == 1,
            'scheduling has no unique same-M native source edge')
        tree, parents, workflows = self._workflow_tuple(revision, paths=METADATA_CALLERS[policy.caller_path])
        require(len(parents) == 2 and parents[1] == binding['head_sha'],
                'scheduling original ordered PR parents differ')
        require(revision != binding['merge_sha'] or tree == binding['merge_tree']
            and parents == binding['merge_parents'], 'scheduling original ordered candidate differs')
        source = self._metadata_source(parents[0])
        generations = [name for name, expected in policy.generations.items()
            if expected == workflows and source == policy.sources[name]]
        require(len(generations) == 1, 'scheduling workflow/helper pair is unknown or mixed')
        recipe = (policy.caller_path, workflows[policy.caller_path]['sha'], workflows[METADATA_WORKFLOW]['sha'])
        if recipe in _NATIVE_INTENT_RECIPES and any(row.get('display_title') not in
                {NONPRODUCER_RUN_NAME, ORDINARY_RUN_NAME} for row in (listed, latest, run)):
            raise SchedulingPending('reviewed native scheduling title is not available yet')
        require(listed.get('display_title') == latest.get('display_title') == run.get('display_title'),
                'scheduling native intent identity changed')
        progress = (allow_intent_progress and recipe in _NATIVE_INTENT_RECIPES
                    and run.get('display_title') == NONPRODUCER_RUN_NAME)
        ordinary = (scheduling_progress and recipe in _NATIVE_INTENT_RECIPES
                    and run.get('display_title') == ORDINARY_RUN_NAME)
        completed_ordinary = ordinary and all(row.get('status') == 'completed'
                                             for row in (listed, latest, run))
        matching = all(listed.get(key) == latest.get(key) == run.get(key) for key in fields)
        require(progress or ordinary or matching, 'scheduling native run observation changed')
        suite = self._object(f"check-suites/{positive(run.get('check_suite_id'))}")
        require(suite.get('id') == run['check_suite_id'] and suite.get('head_sha') == binding['head_sha']
            and suite.get('app', {}).get('id') == 15368
            and suite.get('repository', {}).get('id') == 1319052603
            and suite['repository'].get('full_name') == REPOSITORY, 'scheduling native check-suite/app differs')
        for observed in (listed, latest, run):
            require(observed.get('status') in P._PENDING | {'completed'}
                and (observed['status'] == 'completed') == (observed.get('conclusion') in P._CONCLUSIONS),
                'scheduling run status differs')
        observed_now = now
        if (progress or ordinary) and observation_clock is not None:
            # A live never-producer may advance while the native GETs run.
            # Sample after those reads. An ordinary source still needs its
            # fixed cutoff: valid later progress causes a fresh full retry.
            require(callable(observation_clock), 'invalid scheduling observation clock')
            observed_now = observation_clock()
            P._now(observed_now)
            require(observed_now >= now, 'scheduling observation clock moved backwards')
        if ordinary:
            advanced = False
            for observed in (listed, latest, run):
                require(observed['status'] == 'completed' or observed.get('conclusion') is None,
                        'pending scheduling source has a native conclusion')
                updated = P._time(observed.get('updated_at'))
                require(updated <= observed_now, 'scheduling update time is in the future')
                started = observed.get('run_started_at')
                if started is None:
                    require(observed['status'] in P._PENDING,
                            'completed scheduling source has no native start')
                else:
                    started = P._time(started)
                    require(started <= updated, 'scheduling source time order differs')
                    require(started <= observed_now, 'scheduling source starts in the future')
                    advanced |= started > now
                advanced |= updated > now
            # Completed list/latest and attempt responses can retain distinct
            # updated_at values. Keep each actual timestamp and authenticate
            # its chronology above; every other observed field remains exact.
            completed_matching = completed_ordinary and all(
                listed.get(key) == latest.get(key) == run.get(key)
                for key in fields if key != 'updated_at')
            if not matching and not completed_matching and continuation is None:
                raise SchedulingPending('ordinary scheduling native inventory changed after its cutoff')
            if advanced:
                raise SchedulingPending('ordinary scheduling source is in the future of its fixed cutoff')
        if run.get('run_started_at') is not None:
            require(P._time(run['run_started_at']) <= observed_now, 'scheduling source starts in the future')
        else:
            require(run['status'] in P._PENDING, 'completed scheduling source has no native start')
        require(P._time(run.get('updated_at')) <= observed_now, 'scheduling update time is in the future')
        value = {'run': run, 'generation': generations[0], 'source': source, 'workflows': workflows,
                 'candidate': {'merge_sha': revision, 'merge_tree': tree, 'merge_parents': parents}}
        if continuation is not None:
            value['codeql_result_continuation'] = {
                'result_identity':{key:continuation['result_run'].get(key) for key in _SCHEDULING_RUN_FIELDS},
                'analysis_jobs':continuation['analysis_jobs'],
                'result_job_ids':[job['id'] for job in continuation['result_jobs']]}
        if completed_ordinary:
            # _scheduling_identity retains these same-endpoint observations at
            # the closing admission, including the unmodified update times.
            value['completed_observations'] = {
                name: {key: observed.get(key) for key in fields}
                for name, observed in (('listed', listed), ('latest', latest), ('attempt', run))}
        return value

    def _native_metadata_intent(self, listed, binding, policy, *, now, integrated=False,
                                observation_clock=None):
        """Exact native never-producer recipe; queued intent supplies no result.

        REST display_title is the server-rendered run-name only when set in the
        authenticated immutable workflow. It is never interpreted as authority
        for a historical/unknown recipe, PR text, candidate field or old head.
        """
        source = self._scheduling_source(listed, binding, policy, now=now, integrated=integrated,
            allow_intent_progress=True, observation_clock=observation_clock)
        run, workflows = source['run'], source['workflows']
        recipe = (policy.caller_path, workflows[policy.caller_path]['sha'], workflows[METADATA_WORKFLOW]['sha'])
        if recipe not in _NATIVE_INTENT_RECIPES:
            return None
        require(run.get('display_title') == NONPRODUCER_RUN_NAME, 'native scheduling intent title differs')
        identity = run['id']
        jobs = self._pages(f'actions/runs/{identity}/attempts/1/jobs', 'jobs')
        small = {METADATA_JOB, 'Select required repository checks', 'Select affected CodeQL languages',
                 'repository-checks', 'repository-checks (metadata unchanged)',
                 'codeql-security-results', 'codeql-security-results (metadata unchanged)'}
        checks, names = {}, set()
        for job in jobs:
            name = job.get('name')
            require(type(name) is str and name and name not in names, 'native intent job is ambiguous')
            names.add(name)
            fact = self._job(job, run, 15368, final_name=name)
            require(fact.status in P._PENDING | {'completed'}
                and (fact.status == 'completed') == (fact.conclusion in P._CONCLUSIONS),
                'native intent job status is inconsistent')
            require(name in small or (fact.status, fact.conclusion) == ('completed', 'skipped'),
                    'native nonproducer intent cannot contain executed or queued heavy work')
            checks[fact.job_id] = vars(fact)
        artifacts = self._pages(f'actions/runs/{identity}/artifacts', 'artifacts')
        require(not artifacts, 'native nonproducer intent cannot publish artifacts')
        return {'kind': METADATA_INTENT_KIND,
                'generation': source['generation'], 'candidate': source['candidate'],
                'source': source['source'], 'run': _scheduling_identity(source)['run'],
                'workflows': workflows, 'actions_app_id': 15368,
                'native_source': {key: next(row for row in run['referenced_workflows'] if row['path'] ==
                    REPOSITORY + '/' + METADATA_WORKFLOW + '@' + source['candidate']['merge_sha'])[key]
                    for key in ('path', 'sha', 'ref')}}

    def _scheduling_diagnostics(self, number, policy):
        value = self._object(f'pulls/{positive(number)}')
        labels = value.get('labels')
        require(value.get('number') == number and type(labels) is list
            and all(type(row) is dict and type(row.get('id')) is int and row['id'] > 0
                and type(row.get('name')) is str and 0 < len(row['name']) <= 100 for row in labels)
            and len({row['id'] for row in labels}) == len(labels)
            and len({row['name'] for row in labels}) == len(labels), 'scheduling label inventory unavailable')
        return policy.caller_path.endswith('/repository-checks.yml') and any(
            row['name'] == 'android-long-diagnostics' for row in labels)

    def metadata_schedule(self, number, current_run_id, policy, *, diagnostics=False, now=None,
                          observation_clock=None):
        """Suppress duplicate scheduling while preserving original gate state.

        The current invocation is excluded only after its own immutable native
        source is authenticated. Every other invocation must be either a proven
        nonproducer or an ordinary source with the successful fixed native step.
        A pending/failed source is intentionally not promoted to successful proof.
        """
        if observation_clock is None:
            observation_clock = _now if now is None else lambda: now
        require(callable(observation_clock), 'invalid scheduling observation clock')
        now = observation_clock() if now is None else now
        P._now(now); positive(current_run_id); _metadata_policy(policy)
        require(type(diagnostics) is bool and self._scheduling_diagnostics(number, policy) == diagnostics,
                'scheduling meaningful diagnostic labels changed')
        binding, references = self.current(number)
        workflow = self._object('actions/workflows/' + policy.caller_path.rsplit('/', 1)[1])
        require(workflow.get('id') == policy.caller_workflow_id and workflow.get('path') == policy.caller_path
                and workflow.get('state') == 'active', 'scheduling native workflow registration differs')
        endpoint = f"actions/workflows/{policy.caller_workflow_id}/runs?head_sha={binding['head_sha']}"
        listed = self._pages(endpoint, 'workflow_runs', search=True)
        identities = [positive(row.get('id')) for row in listed]
        require(len(identities) == len(set(identities)) and identities.count(current_run_id) == 1,
                'scheduling current invocation is missing or ambiguous')
        observations, ordinary = {}, []
        current_row = next(row for row in listed if row['id'] == current_run_id)
        # The current exact never-producer has its own running result job.
        # GitHub's list/latest/attempt endpoints can report different progress
        # timestamps while that job runs. Bind its immutable native intent,
        # just as for other authenticated metadata invocations; no original
        # execution status or canonical result is accepted by this projection.
        current = self._scheduling_source(current_row, binding, policy, now=now,
            allow_intent_progress=True, observation_clock=observation_clock)
        require((policy.caller_path, current['workflows'][policy.caller_path]['sha'],
                 current['workflows'][METADATA_WORKFLOW]['sha']) in _NATIVE_INTENT_RECIPES,
                'scheduling current workflow has no exact never-producer recipe')
        require(_scheduling_candidate_matches(current['candidate'], binding)
            and current['run'].get('display_title') == NONPRODUCER_RUN_NAME
            and current['run']['status'] in P._PENDING and current['run'].get('conclusion') is None,
            'scheduling current invocation is not the active exact candidate')
        for row in listed:
            identity = row['id']
            if identity == current_run_id:
                observations[identity] = ('current', current)
                continue
            marker = self.metadata_observation(row, binding, policy, now=now,
                observation_clock=observation_clock, scheduling_progress=True)
            if marker is not None:
                observations[identity] = ('metadata', marker)
                continue
            source = self._scheduling_source(row, binding, policy, now=now,
                observation_clock=observation_clock, scheduling_progress=True)
            if not _scheduling_candidate_matches(source['candidate'], binding):
                observations[identity] = ('other-source', source)
                continue
            require(source['run'].get('display_title') == ORDINARY_RUN_NAME,
                    'ordinary scheduling source has no reviewed ordinary intent')
            jobs = self._pages(f"actions/runs/{identity}/attempts/{source['run']['run_attempt']}/jobs", 'jobs')
            matches = [job for job in jobs if job.get('name') == METADATA_JOB]
            if not matches:
                raise SchedulingPending('ordinary scheduling source job unavailable')
            require(len(matches) == 1, 'ordinary scheduling source job is ambiguous')
            job = matches[0]
            fact = self._job(job, source['run'], 15368, final_name=METADATA_JOB)
            if fact.status in P._PENDING:
                raise SchedulingPending('ordinary scheduling source job remains pending')
            step_names = {ORDINARY_SOURCE_STEP + ' (diagnostics absent)',
                          ORDINARY_SOURCE_STEP + ' (diagnostics requested)'}
            steps = [step for step in job.get('steps', []) if type(step) is dict
                     and step.get('name') in step_names]
            require(fact.status == 'completed' and fact.conclusion == 'success'
                and len(steps) == 1 and steps[0].get('status') == 'completed'
                and steps[0].get('conclusion') == 'success'
                and P._time(fact.started_at) <= P._time(steps[0].get('started_at'))
                <= P._time(steps[0].get('completed_at')) <= P._time(fact.completed_at),
                'ordinary scheduling source was not independently observed')
            if P._time(fact.completed_at) > now:
                recipe = (policy.caller_path, source['workflows'][policy.caller_path]['sha'],
                          source['workflows'][METADATA_WORKFLOW]['sha'])
                if recipe in _NATIVE_INTENT_RECIPES:
                    observed_now = observation_clock()
                    P._now(observed_now)
                    require(observed_now >= now, 'scheduling observation clock moved backwards')
                    require(P._time(fact.completed_at) <= observed_now,
                            'ordinary scheduling source job completed in the future')
                    raise SchedulingPending('ordinary scheduling source job completed after its cutoff')
                require(False, 'ordinary scheduling source was not independently observed')
            # Start timestamps have only second resolution and two separately
            # queued native events can share one. The workflow-specific run
            # sequence is independently bound across list/latest/attempt.
            require(source['run']['run_number'] < current['run']['run_number'],
                    'ordinary scheduling source is not older')
            observations[identity] = ('ordinary', source, job, vars(fact))
            if steps[0]['name'] == ORDINARY_SOURCE_STEP + (
                    ' (diagnostics requested)' if diagnostics else ' (diagnostics absent)'):
                ordinary.append(source)
        if not ordinary:
            raise SchedulingPending('matching ordinary scheduling source unavailable')
        newest = max(row['run']['run_number'] for row in ordinary)
        originals = [row for row in ordinary if row['run']['run_number'] == newest]
        require(len(originals) == 1 and newest < current['run']['run_number'],
                'ordinary scheduling source is ambiguous or newer')
        # Complete fresh inventories and native source checks; neither transient
        # availability nor run IDs are cached or supplied by a caller marker.
        final_list = self._pages(endpoint, 'workflow_runs', search=True)
        require([{key: row.get(key) for key in _SCHEDULING_RUN_FIELDS} for row in final_list]
            == [{key: row.get(key) for key in _SCHEDULING_RUN_FIELDS} for row in listed]
            and _scheduling_context_matches((binding, references), self.current(number))
            and self._scheduling_diagnostics(number, policy) == diagnostics,
            'scheduling candidate, semantic labels or inventory changed')
        for row in final_list:
            kind, source, *extra = observations[row['id']]
            if kind == 'metadata':
                require(self.metadata_observation(row, binding, policy, now=now,
                    observation_clock=observation_clock, scheduling_progress=True) == source,
                        'scheduling nonproducer source changed')
            else:
                fresh = self._scheduling_source(row, binding, policy, now=now,
                    allow_intent_progress=kind == 'current', observation_clock=observation_clock,
                    scheduling_progress=True)
                require(_scheduling_identity(fresh) == _scheduling_identity(source),
                        'scheduling native source changed')
                if kind == 'current':
                    require(fresh['run']['status'] in P._PENDING, 'current scheduling invocation stopped')
                if kind == 'ordinary':
                    jobs = self._pages(f"actions/runs/{row['id']}/attempts/{fresh['run']['run_attempt']}/jobs", 'jobs')
                    matches = [job for job in jobs if job.get('name') == METADATA_JOB]
                    require(len(matches) == 1 and matches[0] == extra[0]
                        and vars(self._job(matches[0], fresh['run'], 15368, final_name=METADATA_JOB)) == extra[1],
                        'scheduling ordinary source job changed')
        original = originals[0]['run']
        result_identity = originals[0].get('codeql_result_continuation', {}).get('result_identity')
        actual_result = self._object(f"actions/runs/{original['id']}") if result_identity else original
        return {'kind': 'native-nonproducer-scheduling', 'qualification': False,
                'metadata_only': 'true', 'binding': binding, 'references': references,
                'current_run_id': current_run_id, 'original_run_id': original['id'],
                'current_merge_sha': current['candidate']['merge_sha'],
                'original_merge_sha': originals[0]['candidate']['merge_sha'],
                'original_status': actual_result['status'], 'original_conclusion': actual_result.get('conclusion'),
                'diagnostics': diagnostics,
                'original_identity': result_identity or {key: original.get(key) for key in _SCHEDULING_RUN_FIELDS}}

    def metadata_result_status(self, observed):
        """One fixed-ID native read between full source admissions; no discovery."""
        require(type(observed) is dict and observed.get('kind') == 'native-nonproducer-scheduling'
            and observed.get('qualification') is False and observed.get('metadata_only') == 'true',
            'metadata result requires an authenticated scheduling observation')
        identity = observed.get('original_identity')
        if type(identity) is dict and type(identity.get('run_attempt')) is int and identity['run_attempt'] > 1:
            require(identity.get('path') == '.github/workflows/codeql.yml', 'foreign result retry caller')
            split = self.codeql_result_attempts(positive(observed.get('original_run_id')),
                sha(observed.get('original_merge_sha')), observed['binding']['head_sha'], attempt=identity['run_attempt'])
            require({key:split['result_run'].get(key) for key in _SCHEDULING_RUN_FIELDS} == identity,
                    'CodeQL result retry identity changed')
            return split['result_run']
        require(type(identity) is dict and set(identity) == set(_SCHEDULING_RUN_FIELDS)
            and positive(identity.get('id')) == positive(observed.get('original_run_id'))
            and identity.get('run_attempt') == 1
            and identity.get('display_title') == ORDINARY_RUN_NAME
            and identity.get('path') in METADATA_CALLERS, 'original result native identity unavailable')
        run = self._object(f"actions/runs/{identity['id']}")
        require(all(run.get(key) == value for key, value in identity.items())
            and type(run.get('run_attempt')) is int and run['run_attempt'] == 1,
            'original result native identity or attempt changed')
        binding = observed['binding']
        require(run.get('head_sha') == binding['head_sha'] and run.get('head_branch') == binding['head_ref']
            and all(run.get(key, {}).get('id') == 1319052603 and run[key].get('full_name') == REPOSITORY
                    for key in ('repository','head_repository')),
            'original result repository or head changed')
        require(run.get('status') in P._PENDING | {'completed'}
            and ((run['status'] == 'completed' and run.get('conclusion') in P._CONCLUSIONS)
                 or run['status'] in P._PENDING and run.get('conclusion') is None),
            'original result native status unavailable')
        return run

    def metadata_result_success(self, observed, *, now=None):
        """Authenticate the real canonical native job before mirroring success.

        No producer artifact, execution receipt or qualification is minted.
        """
        now = _now() if now is None else now
        P._now(now)
        require(type(observed) is dict, 'metadata result observation is malformed')
        if type(observed.get('original_identity', {}).get('run_attempt')) is int and observed['original_identity']['run_attempt'] > 1:
            run = self.metadata_result_status(observed)
            split = self.codeql_result_attempts(run['id'], observed['original_merge_sha'],
                observed['binding']['head_sha'], attempt=run['run_attempt'], now=now, completed=True)
            require(_scheduling_context_matches((observed['binding'], observed['references']),
                    self.current(observed['binding']['pull_request'])), 'CodeQL result retry candidate changed')
            require(self.codeql_result_attempts(run['id'], observed['original_merge_sha'],
                    observed['binding']['head_sha'], attempt=run['run_attempt'], now=now, completed=True) == split
                and self._scheduling_diagnostics(observed['binding']['pull_request'],
                    SimpleNamespace(caller_path=run['path'])) == observed['diagnostics'],
                    'CodeQL result retry changed before metadata output')
            require(_scheduling_context_matches((observed['binding'],observed['references']),
                    self.current(observed['binding']['pull_request'])), 'CodeQL retry closing candidate changed')
            gate = next(job for job in split['result_jobs'] if job['name'] == 'codeql-security-results')
            return {'job_id':gate['id'],'qualification':False,
                    'analysis_attempt':split['analysis_attempt'],'result_attempt':split['result_attempt']}
        run = self.metadata_result_status(observed)
        require(run['status'] == 'completed' and run.get('conclusion') == 'success',
                'original workflow did not succeed')
        attempt = self._object(f"actions/runs/{run['id']}/attempts/1")
        fields = (*_SCHEDULING_RUN_FIELDS, 'repository', 'head_repository', 'pull_requests',
                  'referenced_workflows', 'status', 'conclusion', 'run_started_at')
        require(type(attempt.get('run_attempt')) is int and attempt['run_attempt'] == 1
            and all(attempt.get(key) == run.get(key) for key in fields),
            'original successful attempt changed')
        canonical = {'repository-checks.yml':'repository-checks',
                     'codeql.yml':'codeql-security-results'}[run['path'].rsplit('/',1)[1]]
        jobs = self._pages(f"actions/runs/{run['id']}/attempts/1/jobs", 'jobs')
        identities = [positive(row.get('id')) for row in jobs]
        require(len(identities) == len(set(identities)), 'original canonical job inventory repeats an identity')
        matches = [row for row in jobs if row.get('name') == canonical]
        require(len(matches) == 1, 'original canonical native aggregate unavailable or ambiguous')
        fact = self._job(matches[0], run, 15368, final_name=canonical)
        require(fact.status == 'completed' and fact.conclusion == 'success'
            and all(P._time(observed.get('run_started_at')) <= P._time(fact.started_at)
                <= P._time(fact.completed_at) <= P._time(observed.get('updated_at')) <= now
                for observed in (run, attempt)),
            'original canonical native aggregate did not succeed in its workflow')
        require(self.metadata_result_status(observed) == run
            and self._object(f"actions/runs/{run['id']}/attempts/1") == attempt
            and self._pages(f"actions/runs/{run['id']}/attempts/1/jobs", 'jobs') == jobs
            and vars(self._job(matches[0], run, 15368, final_name=canonical)) == vars(fact),
            'original canonical result changed before output')
        require(type(observed.get('diagnostics')) is bool
            and self._scheduling_diagnostics(observed['binding']['pull_request'],
                SimpleNamespace(caller_path=run['path'])) == observed['diagnostics'],
            'original result diagnostic demand changed before output')
        return {'job_id':fact.job_id,'qualification':False}

    def _metadata_observation(self, listed, policy, binding, now, *, integrated=False):
        if policy.metadata_generations is None:
            return None
        if listed.get('display_title') == ORDINARY_RUN_NAME and any(
                (policy.caller_path, row[policy.caller_path]['sha'], row[METADATA_WORKFLOW]['sha'])
                in _NATIVE_INTENT_RECIPES for row in policy.metadata_generations.values()):
            # None opts INTO the full strict _observation producer path. An
            # ordinary intent never excludes a run or grants metadata/result
            # authority, and its timestamps need no metadata classification.
            return None
        value = self.metadata_observation(listed, binding, MetadataPolicy(policy.caller_workflow_id,
            policy.caller_path, policy.metadata_generations, policy.metadata_sources), integrated=integrated, now=now)
        if value is not None:
            if value.get('kind') == METADATA_INTENT_KIND:
                return value
            forbidden = {policy.publisher_job, *policy.owner_jobs.values()}
            if any(job.get("name") in forbidden or job["name"].startswith(policy.final_publisher_prefix)
                   for job in value["jobs"]):
                return None
        return value

    def _chain(self, run, policy, binding, *, integrated=False):
        require(run.get("repository", {}).get("id") == 1319052603
                and run.get("repository", {}).get("full_name") == REPOSITORY
                and run.get("head_repository", {}).get("id") == binding["head_repository_id"]
                and run.get("head_repository", {}).get("full_name") == REPOSITORY
                and run.get("workflow_id") == policy.caller_workflow_id
                and run.get("path") == policy.caller_path and run.get("event") == "pull_request"
                and run.get("head_sha") == binding["head_sha"] and run.get("head_branch") == binding["head_ref"],
                "run repository/caller/head identity mismatch")
        associated = run.get("pull_requests")
        require(isinstance(associated, list) and (
            integrated and (not associated or len(associated) == 1 and isinstance(associated[0], dict)
                            and associated[0].get("number") == binding["pull_request"])
            or not integrated and sum(isinstance(item, dict) and item.get("number") == binding["pull_request"]
                                      for item in associated) == 1),
                "run's independently associated PR is missing or ambiguous")
        # Closed same-fork runs legitimately lose this API array. Only the
        # separate integrated path has independently authenticated the unique
        # merged PR; its exact original ref and immutable parents/tree below
        # must still bind the source. OPEN association requirements are intact.
        references = run.get("referenced_workflows")
        require(isinstance(references, list), "original reusable source chain unavailable")
        prefix = REPOSITORY + "/" + policy.producer.workflow_path + "@"
        matches = [item for item in references if isinstance(item, dict) and str(item.get("path", "")).startswith(prefix)]
        require(len(matches) == 1, "original reusable producer source is missing or ambiguous")
        source = matches[0]
        revision = sha(source.get("sha"))
        require(source.get("path") == prefix + revision and source.get("ref") == policy.producer.workflow_ref,
                "producer source is not the independently observed local PR merge")
        tree, parents, workflows = self._workflow_tuple(revision)
        matching = [name for name, expected in policy.generations.items() if workflows == expected]
        require(len(matching) == 1 and workflows[policy.producer.workflow_path]["sha"] == policy.producer.workflow_blob,
                "original caller/producer workflow generation is unknown or mixed")
        require(len(parents) == 2 and parents[1] == binding["head_sha"],
                "original producer has unknown ordered PR parents")
        if revision == binding["merge_sha"]:
            require(tree == binding["merge_tree"] and parents == binding["merge_parents"],
                    "current producer source tree/parents differ from independently read candidate")
        # Verify every local reusable reference against the SAME independently
        # observed merge. A foreign/remote/other-generation reference is unknown.
        for item in references:
            require(isinstance(item, dict) and item.get("sha") == revision
                    and item.get("ref") == policy.producer.workflow_ref
                    and isinstance(item.get("path"), str)
                    and item["path"].startswith(REPOSITORY + "/.github/workflows/")
                    and item["path"].endswith("@" + revision), "unsupported referenced workflow chain")
        return {"caller_path": policy.caller_path, "caller_blob": workflows[policy.caller_path]["sha"],
                "caller_commit": revision, "producer_path": policy.producer.workflow_path,
                "producer_blob": workflows[policy.producer.workflow_path]["sha"], "producer_commit": revision,
                "producer_ref": source["ref"], "generation": matching[0],
                "candidate": {"merge_sha": revision, "merge_tree": tree, "merge_parents": parents}}

    def _job(self, value, run, app_id, *, final_name=None):
        require(value.get("run_id") == run["id"] and value.get("run_attempt") == run["run_attempt"]
                and value.get("head_sha") == run["head_sha"], "mixed or foreign job attempt")
        identity = positive(value.get("id"))
        require(value.get("check_run_url") == f"https://api.github.com/{PREFIX}/check-runs/{identity}",
                "job check-run source is unavailable")
        check = self._object(f"check-runs/{identity}")
        require(check.get("id") == identity and check.get("head_sha") == run["head_sha"]
                and check.get("check_suite", {}).get("id") == run["check_suite_id"]
                and check.get("app", {}).get("id") == app_id, "job check app/suite identity mismatch")
        if final_name is not None:
            require(value.get("name") == check.get("name") == final_name
                    and all(value.get(key) == check.get(key) for key in
                            ("status", "conclusion", "started_at", "completed_at")),
                    "final publisher native job/check commitment differs")
        return P.AuthenticatedJob(identity, value["run_attempt"], value.get("status"), value.get("conclusion"),
                                  value.get("started_at"), value.get("completed_at"))

    def _artifacts(self, run):
        return self._pages(f"actions/runs/{run.run_id}/artifacts", "artifacts")

    def _artifact(self, run, kind, items, now, head_sha):
        name = f"ci-{kind}-{run.run_id}-{run.attempt}"
        selected = [item for item in items if item.get("name") == name]
        if not selected:
            return None, None
        require(len(selected) == 1, "producer artifact name is reused or ambiguous")
        item = selected[0]
        detail = self._object(f"actions/artifacts/{positive(item.get('id'))}")
        keys = ("id", "name", "digest", "size_in_bytes", "expired", "created_at", "expires_at", "workflow_run")
        require(all(detail.get(key) == item.get(key) for key in keys), "artifact inventory/detail changed")
        owner = detail.get("workflow_run", {})
        require(owner.get("id") == run.run_id and owner.get("repository_id") == 1319052603
                and owner.get("head_repository_id") == 1319052603
                and owner.get("head_sha") == head_sha
                and isinstance(detail.get("digest"), str) and _DIGEST.fullmatch(detail["digest"])
                and type(detail.get("size_in_bytes")) is int and 0 < detail["size_in_bytes"] <= P._MAX_ARCHIVE,
                "artifact source or bounded API digest unavailable")
        facts = P.AuthenticatedArtifact(detail["id"], owner["repository_id"], owner["id"], detail["name"],
                                         detail["digest"], detail.get("expired"), detail.get("created_at"),
                                         detail.get("expires_at"), True, 1)
        raw = self.api.bytes(PREFIX + f"/actions/artifacts/{facts.artifact_id}/zip")
        require(isinstance(raw, bytes) and len(raw) == detail["size_in_bytes"], "raw artifact size differs from API")
        P.read_artifact(raw, kind, facts, run, now=now)
        return raw, facts

    def _observation(self, listed, policy, binding, now, *, integrated=False):
        identity = positive(listed.get("id"))
        latest = self._object(f"actions/runs/{identity}")
        latest_attempt = positive(latest.get("run_attempt"))
        # Failed-only retries can carry old successful timestamps under NEW job
        # IDs and run_attempt fields. Do not infer original execution from them.
        if latest_attempt != 1:
            raise OriginalAttemptUnavailable("original first-attempt producer source unavailable")
        attempt = self._object(f"actions/runs/{identity}/attempts/{latest_attempt}")
        fields = ("id", "workflow_id", "check_suite_id", "path", "event", "head_sha", "head_branch", "run_attempt", "status", "conclusion")
        require(all(listed.get(key) == latest.get(key) == attempt.get(key) for key in fields),
                "latest run/attempt inventory changed or mixed")
        chain = self._chain(attempt, policy, binding, integrated=integrated)
        suite = self._object(f"check-suites/{positive(attempt.get('check_suite_id'))}")
        require(suite.get("id") == attempt["check_suite_id"] and suite.get("head_sha") == binding["head_sha"]
                and suite.get("repository", {}).get("id") == 1319052603
                and suite.get("app", {}).get("id") == policy.producer.actions_app_id,
                "run check-suite/app authority mismatch")
        source_run = P.AuthenticatedRun(REPOSITORY, 1319052603, suite["app"]["id"], identity, 1, 1,
                                       attempt.get("run_started_at"), policy.producer.workflow_path,
                                       chain["producer_blob"], chain["producer_commit"], chain["producer_ref"],
                                       attempt["event"], attempt["status"], attempt.get("conclusion"), None, {})
        P._run(source_run, policy.producer)
        candidate = chain["candidate"]
        matches = (candidate["merge_tree"] == binding["merge_tree"] and
                   candidate["merge_parents"] == binding["merge_parents"]) if integrated else (
                       chain["producer_commit"] == binding["merge_sha"])
        if not matches:
            # Fully classify a different original merge before excluding it.
            # Its source is known, but no artifacts/runtime/results are reused.
            return None, chain, []
        jobs = self._pages(f"actions/runs/{identity}/attempts/{latest_attempt}/jobs", "jobs")
        require(all(job.get("run_id") == identity and job.get("run_attempt") == latest_attempt for job in jobs),
                "latest-attempt job snapshot contains mixed executions")
        by_name = {}
        for job in jobs:
            by_name.setdefault(job.get("name"), []).append(job)
        selected = {}
        for name in [policy.publisher_job, *policy.owner_jobs.values()]:
            require(len(by_name.get(name, [])) <= 1, "selected job name is ambiguous")
            selected[name] = self._job(by_name[name][0], attempt, policy.producer.actions_app_id) if name in by_name else None
        final_jobs = [job for job in jobs if isinstance(job.get("name"), str)
                      and job["name"].startswith(policy.final_publisher_prefix)]
        require(len(final_jobs) <= 1, "final publisher commitment is ambiguous")
        publication = None
        if final_jobs:
            job = final_jobs[0]
            commitment = job["name"][len(policy.final_publisher_prefix):]
            require(re.fullmatch(r"[0-9a-f]{64}", commitment) is not None,
                    "reserved final publisher commitment is malformed")
            publication = P.AuthenticatedPublication(
                self._job(job, attempt, policy.producer.actions_app_id, final_name=job["name"]), commitment)
        run = P.AuthenticatedRun(REPOSITORY, 1319052603, suite["app"]["id"], identity, latest_attempt, latest_attempt,
                                 attempt.get("run_started_at"), policy.producer.workflow_path, chain["producer_blob"],
                                 chain["producer_commit"], chain["producer_ref"], attempt["event"], attempt["status"],
                                 attempt.get("conclusion"), selected[policy.publisher_job],
                                 {name: selected[job] for name, job in policy.owner_jobs.items() if selected[job] is not None}, publication)
        P._run(run, policy.producer)
        items = self._artifacts(run)
        raw, facts = self._artifact(run, "descriptor", items, now, binding["head_sha"])
        return P.Observation(run, raw, facts), chain, items

    def _capture_inventory(self, binding, policy, now, *, integrated=False):
        # Read-only native source availability may lag job creation. No ordinary
        # failure/result is retried or ignored; only the explicit source-pending
        # category receives this short bounded wait before remaining unavailable.
        for attempt in range(3):
            try:
                return self._capture_inventory_once(binding, policy, now, integrated=integrated)
            except SchedulingPending:
                if attempt == 2:
                    return [], {}, {}, ['native-scheduling-source-pending'], {}, {}
                time.sleep(2)

    def _capture_inventory_once(self, binding, policy, now, *, integrated=False):
        endpoint = f"actions/workflows/{policy.caller_workflow_id}/runs?head_sha={binding['head_sha']}"
        observations, chains, inventories, unavailable, other, metadata = [], {}, {}, [], {}, {}
        try:
            listed = self._pages(endpoint, "workflow_runs", search=True)
            for item in listed:
                try:
                    marker = self._metadata_observation(item, policy, binding, now, integrated=integrated)
                    if marker is not None:
                        metadata[positive(item.get("id"))] = marker
                        continue
                    observation, chain, artifacts = self._observation(item, policy, binding, now, integrated=integrated)
                    if observation is None:
                        other[positive(item.get("id"))] = chain
                        continue
                    observations.append(observation)
                    chains[observation.run.run_id] = chain
                    inventories[observation.run.run_id] = artifacts
                except SchedulingPending:
                    raise
                except OriginalAttemptUnavailable:
                    unavailable.append("original-attempt-unavailable")
                except (ApiError, P.ProtocolError, KeyError, TypeError, ValueError):
                    unavailable.append("run-source-or-proof-unclassified")
            final_list = self._pages(endpoint, "workflow_runs", search=True)
            fields = ("id", "run_attempt", "status", "conclusion", "run_started_at", "updated_at")
            def inventory_row(row):
                classified = metadata.get(row['id'])
                if classified is not None and classified.get('kind') == METADATA_INTENT_KIND:
                    return metadata_inventory_record(row, classified)
                return {key: row.get(key) for key in fields}
            require([inventory_row(row) for row in listed] == [inventory_row(row) for row in final_list],
                    "authority inventory changed")
            for item in final_list:
                identity = positive(item.get("id"))
                if identity in metadata:
                    require(self._metadata_observation(item, policy, binding, now, integrated=integrated) == metadata[identity],
                            "metadata jobs, native checks or artifacts changed during classification")
        except SchedulingPending:
            raise
        except (ApiError, KeyError, TypeError, ValueError):
            unavailable.append("run-inventory-incomplete-or-changed")
        return observations, chains, inventories, unavailable, other, metadata

    def capture(self, number, plan, policy, *, now=None):
        """Return a bookended complete API snapshot, or explicit no-reuse gaps."""
        now = now if now is not None else _now()
        P._now(now)
        _policy(policy, plan, number)
        binding, references = self.current(number)
        observations, chains, inventories, unavailable, other, metadata = self._capture_inventory(binding, policy, now)
        final_binding, final_refs = self.current(number)
        require(final_binding == binding and final_refs == references, "current PR or refs changed during API snapshot")
        return Snapshot(binding, references, observations, not unavailable, tuple(sorted(set(unavailable))), chains, inventories, other, metadata)

    def capture_integrated(self, push_run_id, plan, policy, *, now=None):
        """Look up original source facts; never alias a receipt to the push SHA."""
        now = now if now is not None else _now()
        P._now(now)
        require(isinstance(policy, AdapterPolicy), "trusted controller adapter policy required")
        P.policy_digest(policy.producer)
        origin_policy = (MetadataPolicy(policy.caller_workflow_id, policy.caller_path,
            policy.metadata_generations, policy.metadata_sources) if policy.metadata_generations is not None else None)
        origin = self.integrated_origin(push_run_id, policy.producer.actions_app_id, origin_policy, now=now)
        integrated, references = origin.binding, origin.references
        _policy(policy, plan, integrated["pull_request"])
        observations, chains, inventories, unavailable, other, metadata = self._capture_inventory(
            integrated, policy, now, integrated=True)
        originals = {item.run.workflow_commit for item in observations}
        require(len(originals) == 1, "original integrated producer candidate is missing or ambiguous")
        binding = P.validate_binding({**integrated, "merge_sha": originals.pop()})
        final = self.integrated_origin(push_run_id, policy.producer.actions_app_id, origin_policy, now=now)
        require(final.binding == integrated and final.references == references,
                "merged PR, protected push, protection or current refs changed during API snapshot")
        return Snapshot(binding, references, observations, not unavailable, tuple(sorted(set(unavailable))), chains, inventories, other, metadata)

    def verify(self, number, plan, policy, contexts, *, clock=_now):
        """Read both snapshots and validate original aggregate; no implicit rerun."""
        return self._verify(lambda now: self.capture(number, plan, policy, now=now), plan, policy, contexts, clock)

    def verify_integrated(self, push_run_id, plan, policy, contexts, *, clock=_now):
        """Verify the original evidence and separately return integration facts."""
        return self._verify(lambda now: self.capture_integrated(push_run_id, plan, policy, now=now),
                            plan, policy, contexts, clock)

    def _verify(self, capture, plan, policy, contexts, clock):
        initial = capture(clock())
        authority = P.select_authority(initial.observations, initial.binding, plan, policy.producer,
                                       inventory_complete=initial.inventory_complete, now=clock())
        require(authority["state"] == "proof-required", "newest producer is absent, pending, failed or unresolved")
        selected = next(item for item in initial.observations if item.run.run_id == authority["run_id"])
        artifacts = initial.artifact_inventories[selected.run.run_id]
        raw, artifact = self._artifact(selected.run, "aggregate", artifacts, clock(), initial.binding["head_sha"])
        require(raw is not None and artifact is not None, "newest aggregate proof is missing")
        final = capture(clock())
        require(initial.references == final.references, "current refs changed during aggregate verification")
        require(initial.metadata_nonproducers == final.metadata_nonproducers,
                "metadata non-producer inventory changed during aggregate verification")
        # Artifacts authenticate a run, not a publishing job. Retain the complete
        # independently read final inventory too: a new duplicate, deletion or
        # replacement must not leave the initially downloaded aggregate usable.
        initial_items = [item for item in artifacts if item.get("name") == artifact.name]
        final_items = [item for item in final.artifact_inventories.get(selected.run.run_id, [])
                       if item.get("name") == artifact.name]
        require(len(initial_items) == len(final_items) == 1 and initial_items == final_items,
                "aggregate artifact inventory changed during verification")
        value = P.verify_aggregate(raw, artifact, initial.binding, plan, policy.producer, initial.observations,
                                   inventory_complete=initial.inventory_complete, final_binding=final.binding,
                                   final_observations=final.observations, final_inventory_complete=final.inventory_complete,
                                   contexts=contexts, now=clock())
        result = {**value, "source_chain": final.source_chains[value["run_id"]]}
        if "integration" in final.references:
            integration = final.references["integration"]
            original_integration = final.references.get("origin_integration", integration)
            merged = P._time(original_integration["merged_at"])
            require(P._time(value["qualified_at"]) <= merged and P._time(artifact.created_at) <= merged
                    and P._time(selected.descriptor_artifact.created_at) <= merged
                    and P._time(selected.run.final_publisher.job.completed_at) <= merged,
                    "original evidence was not complete before integration")
            result["integration"] = integration
            if "origin_integration" in final.references:
                result["origin_integration"] = original_integration
                result["retained_no_execution_hops"] = final.references["retained_no_execution_hops"]
        return result
