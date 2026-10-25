"""Prepare the source-bound built-in Tutorial through ordinary Phone input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
from copy import deepcopy
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import re
import sys
import time

DEVICE_ROOT = Path(__file__).resolve().parents[1]
if str(DEVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(DEVICE_ROOT))
from adapters.normal_ui import NativeUI
from adapters.phone_navigation import PhoneNavigation
from contracts import validate_probe_snapshot

TUTORIAL_URL = 'file:///~/serverless/tutorial.json'
TUTORIAL_SOURCE = 'interface/resources/serverless/tutorial.json'
TUTORIAL_SHA256 = 'bb8e35a6d5b54fa05b63df4bc9d80cec41e080b4bfde9a9695b55b5dc746535c'
ADDRESS_SOURCE = 'interface/resources/qml/+android_phoneInterface/AddressBarDialog.qml'
ADDRESS_SHA256 = '4dcbee1fe5988e3ef06bdc2f4a10811ef429aa9b38d1004108a87e6a7956b9b9'
SPAWN_PATH = '/1985.26,1994.24,1994.25/0,-0.819884,0,0.572529'
SPAWN_FEET = (1985.26, 1994.1357422, 1994.25)
OBSERVATION_SECONDS = 45.0
POLL_SECONDS = .3


class PreparationError(ValueError):
    """Closed failure; preserve input state and original private observations."""


def need(ok, code):
    if not ok:
        raise PreparationError(code)


def _write(root, name, value):
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    with os.fdopen(os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _sources(context):
    """Verify actual loaded input code and the installed client's Tutorial source."""
    context.source_guard()
    source, client = context.admission.source, context.admission.client
    for cls, relative in ((NativeUI, 'tests/device/adapters/normal_ui.py'),
                          (PhoneNavigation, 'tests/device/adapters/phone_navigation.py'),
                          (type(context.phone_adapter), 'tests/device/adapters/android-phone/appium_adapter.py')):
        need(Path(inspect.getfile(cls)).resolve() == source / relative,
             'PHONE_TUTORIAL_LOADED_SOURCE_MISMATCH')
    result = {}
    for relative, expected in ((TUTORIAL_SOURCE, TUTORIAL_SHA256), (ADDRESS_SOURCE, ADDRESS_SHA256)):
        for root in (source, client):
            path = root / relative
            need(path.resolve() == path and path.is_file() and not path.is_symlink()
                 and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                 'PHONE_TUTORIAL_CLIENT_SOURCE_CHANGED')
        result[relative] = expected
    document = json.loads((client / TUTORIAL_SOURCE).read_bytes())
    need(document.get('Paths', {}).get('/') == SPAWN_PATH, 'PHONE_TUTORIAL_SPAWN_SOURCE_CHANGED')
    return result


def _vector(value):
    need(type(value) is dict and set(value) == {'x', 'y', 'z'}
         and all(type(value[key]) in (int, float) and math.isfinite(value[key]) for key in ('x', 'y', 'z')),
         'PHONE_TUTORIAL_VECTOR_REQUIRED')
    return [value[key] for key in ('x', 'y', 'z')]


def _row(probe, nonce, observed, identity):
    avatar, scene, domain = probe['avatar'], probe['scene'], probe['domain']
    return {'runNonce': nonce, 'observedEpochMs': observed, 'processIdentity': identity,
            'sceneUrl': scene['url'], 'protocol': domain['protocol'],
            'serverless': domain['serverless'], 'connected': domain['connected'],
            'entityCount': scene['entityCount'], 'feet': _vector(avatar['feetPosition']),
            'inAir': avatar['inAir'], 'flying': avatar['flying'], 'velocity': _vector(avatar['velocity'])}


def _ready(row):
    return (row['sceneUrl'] == TUTORIAL_URL and row['protocol'] == 'file'
            and row['serverless'] is True and row['connected'] is False
            and type(row['entityCount']) is int and row['entityCount'] > 0
            and all(abs(actual - expected) <= .75 for actual, expected in zip(row['feet'], SPAWN_FEET))
            and row['inAir'] is False and row['flying'] is False
            and math.sqrt(sum(value * value for value in row['velocity'])) <= .1)


def prepare_tutorial(context):
    """Return exactly three independently acquired stable Tutorial snapshots.

    context.phone_adapter is constructed by the admitted fixture from the
    sealed original candidate arguments. Only its already-owned existing SDK
    session is used. No installation, session creation, reset, navigation API,
    keyboard substitution or input retry is performed here.
    """
    need(callable(getattr(context, 'source_guard', None))
         and getattr(context, 'phone_adapter', None) is not None
         and type(context.nonce) is str and re.fullmatch('[0-9a-f]{32}', context.nonce),
         'PHONE_TUTORIAL_BOUND_CONTEXT_REQUIRED')
    binding = _sources(context)
    root = context.run_root / 'tutorial-preparation'
    need(root.resolve(strict=False) == root and not root.exists(), 'PHONE_TUTORIAL_FRESH_NAMESPACE_REQUIRED')
    root.mkdir(mode=0o700)
    _write(root, 'source-binding.private.json', {'files': binding, 'url': TUTORIAL_URL, 'spawnPath': SPAWN_PATH})
    adapter = context.phone_adapter
    selector = context.target['selector']
    need(adapter.candidate is not None, 'PHONE_TUTORIAL_CANDIDATE_REQUIRED')
    with adapter.existing_input_session(selector):
        client, session, state = adapter.existing_session(selector)
        target = deepcopy(adapter.target(selector))
        need(target == context.target, 'PHONE_TUTORIAL_TARGET_MAPPING_CHANGED')
        fingerprint = adapter.snapshot_fingerprint(target)
        generation = state.get('generation')
        installed = deepcopy(adapter.installed_identity(selector))
        manifest = context.admission.manifest
        need(installed.get('installedCandidateVerified') is True
             and installed.get('sourceRevision') == manifest['client']['revision']
             and installed.get('artifactSha256') == manifest['candidate']['sha256'],
             'PHONE_TUTORIAL_INSTALLED_CANDIDATE_CHANGED')
        process = deepcopy(adapter.process_state(selector, client, session, state, target))
        need(process.get('running') is True and type(process.get('identity')) is str
             and re.fullmatch(r'[1-9][0-9]{0,9}:[0-9]{1,20}', process['identity']),
             'PHONE_TUTORIAL_PROCESS_REQUIRED')

        def check():
            current = adapter.read_session(selector)
            need(type(current) is dict and current.get('sessionId') == session
                 and type(generation) is int and current.get('generation') == generation
                 and current.get('targetFingerprint') == fingerprint
                 and adapter.snapshot_fingerprint(adapter.target(selector)) == fingerprint
                 and adapter.query_app_state(client, session, target) == 4
                 and adapter.process_state(selector, client, session, state, target) == process,
                 'PHONE_TUTORIAL_PROCESS_OR_SESSION_CHANGED')
            need(adapter.installed_identity(selector) == installed, 'PHONE_TUTORIAL_INSTALL_CHANGED')

        check()
        ui = NativeUI(client, session, check, timeout=20)
        flow = PhoneNavigation(ui, target['controls']['normalNavigation'], state,
                               installed, process['identity'], lambda: adapter.save_session(selector, state))
        input_started_ms = time.time_ns() // 1_000_000
        # Identical ordinary input order to the committed3305 Phone flow.
        flow.open_address()
        ui.click(flow.address)
        ui.replace_text(flow.address, TUTORIAL_URL)
        flow.submit_address(TUTORIAL_URL)
        ui.wait_absent(flow.address)
        flow.mark('addressOwned', False)
        check()
        context.source_guard()
        deadline = time.monotonic() + OBSERVATION_SECONDS
        rows, previous_sequence, previous_sample, attempt = [], None, None, 0
        while time.monotonic() <= deadline:
            check()
            probe = adapter.existing_probe_snapshot(selector, {})
            observed = time.time_ns() // 1_000_000
            _write(root, 'probe-' + str(attempt).zfill(3) + '.private.json', probe)
            attempt += 1
            validate_probe_snapshot(probe)
            sampled, sequence = probe['sampleEpochMs'], probe['sampleSequence']
            need(input_started_ms <= sampled <= observed + 5000 and abs(observed - sampled) <= 5000,
                 'PHONE_TUTORIAL_STALE_PROBE')
            need(previous_sequence is None or sequence > previous_sequence
                 and sampled - previous_sample >= 250, 'PHONE_TUTORIAL_REPLAYED_PROBE')
            previous_sequence, previous_sample = sequence, sampled
            need(probe['application']['running'] is True and probe['application']['foreground'] is True,
                 'PHONE_TUTORIAL_BACKGROUND_PROBE')
            motion = probe.get('nativeMotion')
            if motion is not None:
                need(motion['processId'] == int(process['identity'].split(':')[0]),
                     'PHONE_TUTORIAL_PROBE_PROCESS_CHANGED')
            check()
            row = _row(probe, context.nonce, observed, process['identity'])
            if not _ready(row):
                rows = []
            else:
                if rows and (observed - rows[-1]['observedEpochMs'] < 250
                             or abs(row['entityCount'] - rows[0]['entityCount']) > 1
                             or math.dist(rows[0]['feet'], row['feet']) > .05):
                    rows = []
                rows.append(row)
                if len(rows) == 3:
                    context.source_guard()
                    _write(root, 'observations.private.json', rows)
                    return rows
            time.sleep(POLL_SECONDS)
        raise PreparationError('PHONE_TUTORIAL_FRESH_GROUNDED_SAMPLES_TIMEOUT')
