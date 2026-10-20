"""Strict v13 action/read boundary for feature additions to the existing harness."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
import json
import re
from urllib.parse import urlsplit
from .fixtures import context
from .scenarios import SCENARIOS, VERSION, actions, expand

HEX = re.compile(r'[0-9a-f]{32}')


def json_document(raw):
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('Duplicate feature JSON field')
            value[key]=item
        return value
    def nonfinite(_value):raise ValueError('Nonfinite feature JSON number')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=nonfinite)


def exact(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError('Invalid ' + label + ' fields')


def identifier(value):
    if type(value) is not str or HEX.fullmatch(value) is None:
        raise ValueError('A fresh 128-bit owned identifier is required')
    return value


def number(value, minimum=0, maximum=1e15):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError('Invalid bounded finite observation number')
    return value


def operation_parts(operation):
    parts = operation.split('.')
    if len(parts) != 3 or parts[0] != 'feature' or parts[1] not in SCENARIOS or parts[2] not in {'act', 'observe', 'cleanup'}:
        raise ValueError('Unknown feature operation')
    return parts[1:]


def arguments(operation, value):
    area, kind = operation_parts(operation)
    fields = {'contractVersion', 'runId'}
    fields |= {'verb', 'inputs', 'ticket', 'fixtureUrl'} if kind == 'act' else {'afterSequence'} if kind == 'observe' else set()
    exact(value, fields, 'feature input')
    if type(value['contractVersion']) is not int or value['contractVersion'] != VERSION:
        raise ValueError('Unsupported feature contract version')
    run = identifier(value['runId'])
    if kind == 'observe':
        if type(value['afterSequence']) is not int or not 0 <= value['afterSequence'] <= 1_000_000_000:
            raise ValueError('Invalid feature observation cursor')
    elif kind == 'act':
        identifier(value['ticket'])
        url = value['fixtureUrl']
        if type(url) is not str or len(url) > 512:
            raise ValueError('Invalid owned fixture URL')
        parsed = urlsplit(url)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment
                or parsed.path != '/feature-fixture/v1/runs/' + run + '/'):
            raise ValueError('Feature fixture URL requires the exact owned run path')
        parsed.port  # Fail malformed ports before any input.
        verb = value['verb']
        if type(verb) is not str or verb not in actions(area):
            raise ValueError('Unsupported ordinary feature action')
        allowed = [expand(candidate, context(run)) for candidate in actions(area)[verb]]
        # Equality alone would equate bools and numbers. Canonical types must match.
        if not any(typed_equal(value['inputs'], candidate) for candidate in allowed):
            raise ValueError('Feature input is outside the closed owned fixture inventory')
    return value


def typed_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(typed_equal(left[k], right[k]) for k in right)
    if isinstance(left, list):
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def state(area, value, run=None):
    baseline = SCENARIOS[area]['baseline']
    exact(value, baseline, 'actual product state')
    for key, prototype in baseline.items():
        item = value[key]
        if type(prototype) in (int, float):
            number(item, -1000000, 1000000)
            if type(prototype) is int and type(item) is not int:
                raise ValueError('Integer product counter required')
        elif type(item) is not type(prototype):
            raise ValueError('Invalid product state type')
        elif isinstance(item, str) and (len(item) > 256 or any(ord(ch) < 32 for ch in item)):
            raise ValueError('Product state string exceeds the public fixed-text contract')
        elif isinstance(item, list):
            if len(item) > 32 or any(type(x) is not str or len(x) > 256 or any(ord(ch) < 32 for ch in x) for x in item):
                raise ValueError('Invalid bounded product list')
    if run is not None:
        checkpoints = [expand(baseline, context(run))] + [expand(step['state'], context(run)) for step in SCENARIOS[area]['steps']]
        for key, prototype in baseline.items():
            if isinstance(prototype, str):
                allowed = set()
                for row in checkpoints:
                    candidate = row[key]
                    allowed.update(candidate['oneOf'] if type(candidate) is dict and 'oneOf' in candidate else [candidate])
                if value[key] not in allowed:
                    raise ValueError('Product string is outside the selector-free public vocabulary')
            if isinstance(prototype, list):
                allowed = {item for row in checkpoints for item in row[key]}
                if any(item not in allowed for item in value[key]):
                    raise ValueError('Product list contains private or unowned values')
    if area == 'assets':
        if value['baking'] != (value['bakeState'] == 'baking'):
            raise ValueError('Asset bake activity disagrees with original server state')
        if value['bakeAvailable'] != (value['bakeState'] in {'baking','ready','disabled'}):
            raise ValueError('Asset bake control disagrees with the selected original file type')
        if value['deleteEnabled'] and (not value['open'] or not value['canWrite'] or not value['selected']):
            raise ValueError('Asset Delete cannot be enabled without a writable selection')
        if value['selected'] and value['selected'] not in value['mappings']:
            raise ValueError('Asset selection has no original owned mapping')
        if not value['picker'] and (value['pickerFile'] or value['stagedAvailable']):
            raise ValueError('Asset picker ownership outlived its original surface')
    if area == 'avatar-people':
        if value['modelLoaded'] != (value['avatar'] != 'unavailable'):
            raise ValueError('Avatar geometry readiness disagrees with the actual loaded model')
        if value['loadFailed'] and value['requestedAvatar'] != 'missing':
            raise ValueError('Avatar failure belongs to a different original request')
        if value['avatar'] == 'fallback' and value['requestedAvatar'] != 'missing':
            raise ValueError('Avatar fallback belongs to a different original request')
    if area in {'world-web','tablet-web'}:
        if (min(value[k] for k in ('documentLoads','bridgeMessages','bridgeEchoes','attemptedMessages'))<0
                or value['inlineLeases'] not in (0,1) or value['deferredMessages'] not in (0,1)
                or value['bridgeMessages']+value['deferredMessages']>value['attemptedMessages']
                or value['bridgeEchoes']>value['bridgeMessages']):
            raise ValueError('Browser original event/lease counters disagree')
        if value['open']:
            if value['documentLoads']<1 or value['page']=='none' or value['documentKind']=='none':
                raise ValueError('Browser has no actual loaded document')
        elif (value['page']!='none' or value['text'] or value['focused'] or value['documentKind']!='none'
              or value['origin']!='none' or value['httpStatus'] or value['inlineLeases']):
            raise ValueError('Closed browser retains an actual document/input/lease')
        if value['documentKind']=='http':
            if value['httpStatus'] not in (200,404) or value['origin'] not in ('primary','foreign') or value['inlineLeases']:
                raise ValueError('Browser HTTP status, original origin and carrier disagree')
        elif value['documentKind']=='inline':
            if area!='tablet-web' or value['httpStatus'] or value['origin']!='inline' or value['inlineLeases']!=1:
                raise ValueError('Inline app has no original native carrier')
        elif value['documentKind']!='none':raise ValueError('Unknown original browser document kind')
        if area=='world-web' and value['deferredMessages']:
            raise ValueError('World browser has an unsupported deferred inline event')
    if area == 'chat':
        if value['open']:
            if value['channel'] not in {'local','domain'}:
                raise ValueError('Open Chat lacks an actual active channel')
            visible=value[value['channel']+'Messages']
        else:
            if value['channel']!='none' or value['draft']!='' or value['focused'] or value['keyboard']:
                raise ValueError('Closed Chat retains a fictional active channel/editor/keyboard')
            visible=[]
        if value['messages'] != visible:
            raise ValueError('Chat visible rows disagree with original channel history')
        if value['keyboard'] and not value['focused']:
            raise ValueError('Chat keyboard has no actual editor focus')
    if area == 'snapshots':
        backend=value['saveBackend'];permission=value['savePermission']
        if backend not in {'photos-add-only','media-store','document-picker'} or permission not in ({'granted','denied'} if backend=='photos-add-only' else {'not-required'}):
            raise ValueError('Snapshot Save backend and original OS authorization disagree')
        if any(type(value[k]) is not int or not 0<=value[k]<=1 for k in ('files','saved','uploads','shares')):
            raise ValueError('Snapshot owned output inventory is invalid')
        if value['saveSheet'] and backend!='document-picker' or value['saveSheet'] and value['shareSheet']:
            raise ValueError('Snapshot system sheet does not belong to its backend')
        if (value['saved'] or value['uploads'] or value['shares']) and value['files']!=1:
            raise ValueError('Snapshot external result has no retained owned capture')
        history=value['captureHistory']
        if (history and history[0]!='pending' or any((a,b) not in {('pending','cancelled'),('pending','complete'),('cancelled','pending'),('complete','pending')} for a,b in zip(history,history[1:]))
                or bool(value['pending'])!=bool(history and history[-1]=='pending')):
            raise ValueError('Snapshot original capture history and pending state disagree')
        if value['pending'] and (value['files'] or value['saveSheet'] or value['shareSheet']):
            raise ValueError('Snapshot pending capture overlaps a retained output or export sheet')
    if area == 'graphics':
        number(value['resolution'],0.1,2.0); number(value['renderScale'],0.1,2.0)
    if area == 'audio':
        phase, history = value['phase'], value['history']
        if (any(value[key] < 0 for key in ('recordedFrames', 'playedFrames', 'bufferedFrames'))
                or not history and phase != 'idle' or history and history[-1] != phase
                or any(a == b for a, b in zip(history, history[1:]))
                or value['recording'] != (phase == 'capturing')
                or value['preview'] != (phase in ('playing', 'draining'))
                or value['playedFrames'] > value['recordedFrames']
                or value['bufferedFrames'] > value['recordedFrames']):
            raise ValueError('Audio phase, original history and measured counters disagree')
        if (phase == 'error' and value['error'] == 'none'
                or phase in ('idle', 'capturing', 'playing', 'draining', 'completed') and value['error'] != 'none'
                or phase == 'idle' and (history or value['recordedFrames'] or value['playedFrames'])):
            raise ValueError('Audio state lacks its actual native phase/error history')
        if phase in ('idle', 'error', 'cancelled', 'completed') and value['bufferedFrames'] != 0:
            raise ValueError('Inactive audio retained product preview buffers')
        if phase == 'completed' and (history != ['capturing', 'playing', 'draining', 'completed']
                or value['playedFrames'] != value['recordedFrames'] or value['recordedFrames'] <= 0):
            raise ValueError('Audio completion lacks actual whole-cycle playback')
    return value


def result(operation, value):
    area, kind = operation_parts(operation)
    if kind in {'act', 'cleanup'}:
        exact(value, {'performed'}, 'feature acknowledgment')
        if value['performed'] is not True:
            raise ValueError('Feature input delivery was not confirmed')
        return value
    exact(value, {'schemaVersion', 'contractVersion', 'runId', 'sequence', 'capturedEpochMs', 'state', 'artifacts', 'resources', 'lifecycle'}, 'feature observation')
    if (type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
            or type(value['contractVersion']) is not int or value['contractVersion'] != VERSION):
        raise ValueError('Unsupported feature observation version')
    identifier(value['runId'])
    if type(value['sequence']) is not int or not 1 <= value['sequence'] <= 1_000_000_000:
        raise ValueError('Invalid product sequence')
    number(value['capturedEpochMs'], 1)
    state(area, value['state'], value['runId'])
    if (type(value['resources']) is not list or len(value['resources']) > 64
            or any(type(x) is not str or re.fullmatch(r'(entity|script|file|panel|input|connection):[a-z0-9-]{1,64}', x) is None for x in value['resources'])
            or len(set(value['resources'])) != len(value['resources'])):
        raise ValueError('Invalid public owned-resource inventory')
    exact(value['lifecycle'], {'backgrounds', 'activations', 'launches'}, 'native lifecycle counters')
    if any(type(x) is not int or not 0 <= x <= 1000000 for x in value['lifecycle'].values()):
        raise ValueError('Native lifecycle counts must be bounded actual integers')
    if type(value['artifacts']) is not list or len(value['artifacts']) > 4:
        raise ValueError('Invalid artifact inventory')
    kinds, names = set(), set()
    for artifact in value['artifacts']:
        fields = {'kind', 'name', 'sequence', 'capturedEpochMs', 'ticket'}
        if type(artifact) is dict and (artifact.get('kind') == 'image' or area=='snapshots' and artifact.get('kind')=='file'):
            fields.add('source')
        exact(artifact, fields, 'feature artifact')
        if artifact['kind'] == 'image' and artifact['source'] not in {'native-screen', 'world-render-target'}:
            raise ValueError('Unsupported original image acquisition source')
        if area=='snapshots' and artifact['kind']=='file' and artifact['source'] not in {'snapshot-private-original','snapshot-saved-original','snapshot-receiver-original','snapshot-upload-original'}:
            raise ValueError('Snapshot file has no supported original acquisition source')
        if artifact['kind'] not in {'image', 'audio', 'file'} or artifact['kind'] in kinds:
            raise ValueError('Unsupported or duplicate artifact kind')
        kinds.add(artifact['kind'])
        name = artifact['name']
        if type(name) is not str or re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}', name) is None or name in names:
            raise ValueError('Artifacts require distinct direct private-run filenames')
        names.add(name)
        identifier(artifact['ticket'])
        if type(artifact['sequence']) is not int or artifact['sequence'] != value['sequence']:
            raise ValueError('Artifact and product sample sequences differ')
        number(artifact['capturedEpochMs'], 1)
        if abs(artifact['capturedEpochMs'] - value['capturedEpochMs']) > 1500:
            raise ValueError('Artifact is stale relative to the product observation')
    return value
