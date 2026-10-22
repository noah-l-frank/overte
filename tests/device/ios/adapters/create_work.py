"""Actual Create closure entry/return/finally and pending-work originals.

A fresh VM heartbeat is required alongside the complete retained native event
history. An ended script or hidden panel cannot substitute for drained work.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact, fresh, integer, need
from adapters.native_script_membership import validate as membership
from adapters.native_script_observation import validate_code
from adapters.native_script_roots import root_url
from adapters.script_feature.history import same
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters.create_state import command as state_command, text, uuid

VERSION = 1
ACTION = 'feature-ios-create-work'
FILE = ACTION+'.json'
LIMIT = 262144
PATHS = dict(edit='system/create/edit.js', bridge='system/create/modules/nativeCreateBridge.js',
             voxels='system/create/editModes/editVoxels.js', **{'entity-list':'system/create/entityList/entityList.js'})
HELPER = 'system/create/modules/featureCreateWork.js'
PIN_FILE = Path(__file__).parents[1]/'create-work-source-pins.v1.json'


def command(value):
    original = deepcopy(value); original['action'] = 'feature-ios-create-state'; state_command(original)
    need(value['action'] == ACTION); return value


def code_sources(value, epoch):
    exact(value, {'createSourcesVersion', 'complete', 'evaluations'})
    need(type(value['createSourcesVersion']) is int and value['createSourcesVersion'] == 1
         and type(value['complete']) is bool and type(value['evaluations']) is list and len(value['evaluations']) <= 64)
    previous = 0
    for index, row in enumerate(value['evaluations']):
        exact(row, {'sequence', 'url', 'submittedEpochMs', 'encoding', 'codeUnits', 'sha256'})
        parsed = urlsplit(text(row['url']))
        need(type(row['sequence']) is int and row['sequence'] == index+1 and parsed.scheme in ('file', 'qrc')
             and not parsed.netloc and not parsed.query and not parsed.fragment and '/system/create/' in parsed.path
             and row['encoding'] == 'utf-16le-code-units' and integer(row['codeUnits'], 1, 4194304)
             and re.fullmatch('[a-f0-9]{64}', text(row['sha256'], 64))
             and integer(row['submittedEpochMs'], previous, epoch))
        previous = row['submittedEpochMs']
    return value


def pending(role, state):
    need(type(state) is dict)
    if role == 'edit':
        exact(state, {'browseCallback', 'numericEditing', 'numericDirty', 'active'})
        need(all(type(value) is bool for value in state.values()))
        return state['browseCallback'] or state['numericEditing'] or state['numericDirty']
    if role == 'bridge':
        exact(state, {'browsing', 'browseGeneration'}); need(type(state['browsing']) is bool and integer(state['browseGeneration'], 0, 1000000000))
        return state['browsing']
    if role == 'entity-list':
        exact(state, {'exportCallback'}); need(type(state['exportCallback']) is bool); return state['exportCallback']
    need(role == 'voxels'); exact(state, {'strokeIds', 'strokeTimer', 'strokePolls', 'editing', 'updateConnected', 'sphereId', 'triggeredHand', 'pressedHand'})
    need(type(state['strokeIds']) is list and len(state['strokeIds']) <= 128 and state['strokeIds'] == sorted(set(state['strokeIds']))
         and all(type(state[key]) is bool for key in ('strokeTimer', 'editing', 'updateConnected'))
         and integer(state['strokePolls'], 0, 1000000000) and state['triggeredHand'] in (-1, 0, 1) and state['pressedHand'] in (-1, 0, 1))
    for id_ in state['strokeIds']: uuid(id_)
    if state['sphereId']: uuid(state['sphereId'])
    else: need(state['sphereId'] == '')
    return bool(state['strokeIds'] or state['strokeTimer'] or state['editing'] or state['updateConnected'] or state['sphereId']
                or state['triggeredHand'] != -1 or state['pressedHand'] != -1)


def event(value, role, epoch):
    exact(value, {'sequence', 'capturedEpochMs', 'callerSequence', 'invokedEpochMs', 'event', 'closure', 'call', 'state'})
    need(integer(value['sequence'], 1, 1000000000) and integer(value['callerSequence'], 1, 1000000000)
         and integer(value['invokedEpochMs'], 1, value['capturedEpochMs']) and integer(value['capturedEpochMs'], 1, epoch)
         and value['event'] in ('snapshot', 'entry', 'returned', 'finally', 'ending')
         and integer(value['call'], 0, 1000000000))
    text(value['closure'], 64)
    need((value['event'] in ('snapshot', 'ending')) == (value['call'] == 0 and value['closure'] == ''))
    pending(role, value['state']); return value


def lifetimes(value, epoch, previous=None):
    exact(value, {'createLifetimesVersion', 'complete', 'entities'})
    need(type(value['createLifetimesVersion']) is int and value['createLifetimesVersion'] == 1
         and type(value['complete']) is bool and type(value['entities']) is list and len(value['entities']) <= 512)
    ids = []
    def lifetime(row):
        need(type(row['destroyed']) is bool and integer(row['bornEpochMs'], 1, epoch)
             and integer(row['destructionObservedEpochMs'], 0, epoch)
             and (row['destructionObservedEpochMs'] >= row['bornEpochMs'] if row['destroyed'] else row['destructionObservedEpochMs'] == 0))
    for row in value['entities']:
        exact(row, {'id', 'bornEpochMs', 'destroyed', 'destructionObservedEpochMs', 'models'}); uuid(row['id']); ids.append(row['id']); lifetime(row)
        need(type(row['models']) is list and len(row['models']) <= 16)
        instances = set()
        for model in row['models']:
            exact(model, {'instance', 'bornEpochMs', 'destroyed', 'destructionObservedEpochMs'}); lifetime(model)
            need(re.fullmatch('[a-f0-9]{32}', text(model['instance'], 32)) and model['instance'] not in instances)
            instances.add(model['instance'])
    need(ids == sorted(set(ids)))
    if previous is not None:
        need(previous['complete'] or not value['complete'])
        for old in previous['entities']:
            matching = [row for row in value['entities'] if row['id'] == old['id']]; need(len(matching) == 1); row = matching[0]
            need(row['bornEpochMs'] == old['bornEpochMs'] and (not old['destroyed'] or row['destroyed'])
                 and (not old['destroyed'] or row['destructionObservedEpochMs'] == old['destructionObservedEpochMs'])
                 and len(row['models']) >= len(old['models']))
            for a, b in zip(old['models'], row['models']):
                need(a['instance'] == b['instance'] and a['bornEpochMs'] == b['bornEpochMs']
                     and (not a['destroyed'] or same(a, b)))
    return value


def validate(value, query, pid, epoch=None, previous=None):
    command(query); exact(value, {'iosCreateWorkVersion', 'requestId', 'runId', 'instance', 'sequence', 'processId',
                                 'clockDomain', 'clockBefore', 'clockAfter', 'source'})
    need(type(value['iosCreateWorkVersion']) is int and value['iosCreateWorkVersion'] == VERSION
         and value['requestId'] == query['commandId'] and value['runId'] == query['runId'] and type(value['processId']) is int and value['processId'] == pid
         and re.fullmatch('[a-f0-9]{32}', text(value['instance'], 32)) and integer(value['sequence'], 1, 1000000000)
         and value['clockDomain'] == 'native-main-create-work')
    for clock in (value['clockBefore'], value['clockAfter']):
        exact(clock, {'epochMs', 'monotonicMs'}); need(integer(clock['epochMs'], 1) and integer(clock['monotonicMs']))
    before, after = value['clockBefore'], value['clockAfter']
    delta, elapsed = after['epochMs']-before['epochMs'], after['monotonicMs']-before['monotonicMs']
    need(0 <= delta < 1500 and 0 <= elapsed < 1500 and abs(delta-elapsed) <= 250)
    if epoch is not None: fresh(after['epochMs'], epoch)
    source = value['source']; exact(source, {'complete', 'eventSequence', 'roles', 'entityLifetimes'})
    lifetimes(source['entityLifetimes'], after['epochMs'])
    need(type(source['complete']) is bool and integer(source['eventSequence'], 0, 1000000000)
         and type(source['roles']) is list and len(source['roles']) <= 4)
    roles, sequences = set(), set()
    for row in source['roles']:
        exact(row, {'role', 'sourceUrl', 'manager', 'code', 'codeSources', 'calls', 'events', 'ended', 'state', 'latest'})
        role = row['role']; need(role in PATHS and role not in roles); roles.add(role)
        need(text(row['sourceUrl']).endswith('/'+PATHS[role]) and type(row['ended']) is bool)
        membership(dict(complete=True, revision=1, managers=[row['manager']]), after['epochMs'])
        validate_code(row['code'], after['epochMs']); code_sources(row['codeSources'], after['epochMs'])
        need(row['manager']['assigned'] and row['code']['submitted'])
        events = row['events']; need(type(events) is list and 1 <= len(events) <= 512)
        stack, last_call, cursor, native_cursor, stamp = [], 0, 0, 0, 0
        for entry in events:
            event(entry, role, after['epochMs'])
            need(entry['sequence'] > cursor and entry['callerSequence'] > native_cursor and entry['capturedEpochMs'] >= stamp
                 and entry['sequence'] not in sequences and entry['sequence'] <= source['eventSequence'])
            sequences.add(entry['sequence']); cursor, native_cursor, stamp = (entry[key] for key in ('sequence', 'callerSequence', 'capturedEpochMs'))
            if entry['event'] == 'entry':
                need(entry['call'] > last_call); last_call = entry['call']
                stack.append(dict(call=entry['call'], closure=entry['closure'], returned=False))
            elif entry['event'] in ('returned', 'finally'):
                need(stack and stack[-1]['call'] == entry['call'] and stack[-1]['closure'] == entry['closure'])
                if entry['event'] == 'returned': need(not stack[-1]['returned']); stack[-1]['returned'] = True
                else: stack.pop()
        need(same(stack, row['calls']) and len(stack) <= 32)
        latest = event(row['latest'], role, after['epochMs'])
        need(latest['sequence'] >= cursor and latest['callerSequence'] >= native_cursor
             and latest['capturedEpochMs'] >= stamp and same(latest['state'], row['state'])
             and row['ended'] == (latest['event'] == 'ending'))
        if latest['sequence'] == cursor: need(same(latest, events[-1]))
        else: need(latest['event'] == 'snapshot' and same(latest['state'], events[-1]['state']))
    if previous is not None:
        validate(previous, dict(query, commandId=previous['requestId']), pid)
        need(value['instance'] == previous['instance'] and value['sequence'] > previous['sequence'] and value['requestId'] != previous['requestId']
             and before['epochMs'] >= previous['clockAfter']['epochMs'] and before['monotonicMs'] >= previous['clockAfter']['monotonicMs']
             and source['eventSequence'] >= previous['source']['eventSequence'] and (previous['source']['complete'] or not source['complete']))
        lifetimes(source['entityLifetimes'], after['epochMs'], previous['source']['entityLifetimes'])
        for old in previous['source']['roles']:
            new = [row for row in source['roles'] if row['role'] == old['role']]; need(len(new) == 1); new = new[0]
            need(all(same(old[key], new[key]) for key in ('sourceUrl', 'manager', 'code'))
                 and len(new['events']) >= len(old['events']) and same(new['events'][:len(old['events'])], old['events'])
                 and same(new['codeSources']['evaluations'][:len(old['codeSources']['evaluations'])], old['codeSources']['evaluations'])
                 and new['latest']['sequence'] >= old['latest']['sequence'] and (not old['ended'] or same(old, new)))
    return value


def original(value):
    return validate(value, dict(schemaVersion=1, action=ACTION, commandId=value.get('requestId'), runId=value.get('runId')), value.get('processId'))


def admit(value, scripts_root, *, quiet=False):
    original(value); root = root_url(scripts_root); source = value['source']
    need(source['complete'] and source['entityLifetimes']['complete'] and {row['role'] for row in source['roles']} == set(PATHS))
    pins = json.loads(PIN_FILE.read_text()); exact(pins, {'createWorkSourcePinsVersion', 'encoding', 'sources'})
    need(pins['createWorkSourcePinsVersion'] == 1 and pins['encoding'] == 'utf-16le-code-units')
    for row in source['roles']:
        need(row['sourceUrl'] == root+PATHS[row['role']] and row['manager']['url'] == root+PATHS['edit']
             and row['code']['sha256'] == pins['sources'][PATHS['edit']]['sha256']
             and row['code']['codeUnits'] == pins['sources'][PATHS['edit']]['codeUnits']
             and row['codeSources']['complete'] and not row['ended'])
        fresh(row['latest']['capturedEpochMs'], value['clockAfter']['epochMs'])
        for path in (PATHS[row['role']], HELPER):
            evaluations = [entry for entry in row['codeSources']['evaluations'] if entry['url'] == root+path]
            need(len(evaluations) == 1 and all(evaluations[0][key] == pins['sources'][path][key] for key in ('codeUnits', 'sha256')))
        if quiet: need(not row['calls'] and not pending(row['role'], row['state']))
    return deepcopy(source)


def retired(value, scripts_root, owned_ids):
    source = admit(value, scripts_root, quiet=True)
    need(type(owned_ids) is list and len(set(owned_ids)) == len(owned_ids))
    for id_ in owned_ids:
        matches = [row for row in source['entityLifetimes']['entities'] if row['id'] == id_]
        need(len(matches) == 1 and matches[0]['destroyed'] and all(model['destroyed'] for model in matches[0]['models']))
    return source


class IOSCreateWork(IOSPlacesModel):
    _action = ACTION
    _command = staticmethod(command)
    _validate = staticmethod(validate)
    _acquisition_key = 'iosCreateWorkAcquisitionVersion'
