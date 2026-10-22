"""Original loaded avatar/model failure generations and bookmark enumeration.

These facts supply only Avatar prerequisites. They do not establish wearable
geometry, a real consenting peer, backend relationships or complete capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact, fresh, integer, need, number
from ios.adapters.places_model import IOSPlacesModel, tree

VERSION = 3
READS = (1, 2, 3)
ACTION = 'feature-ios-avatar-state'
FILE = ACTION+'.json'
LIMIT = 262144


def text(value, maximum=2048):
    need(type(value) is str and len(value.encode()) <= maximum and not any(ord(c) < 32 for c in value))
    return value


def identity(value):
    return type(value) is str and re.fullmatch('[a-f0-9]{32}', value) is not None


def session(value):
    need(type(value) is str and re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', value)
         and value != '00000000-0000-0000-0000-000000000000')
    return value


def command(value):
    exact(value, {'schemaVersion', 'commandId', 'action', 'runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1 and value['action'] == ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}', value['commandId'])
         and identity(value['runId']))
    return value


def history(value, pid, epoch, previous=None):
    exact(value, {'avatarModelHistoryVersion', 'instance', 'processId', 'currentGeneration',
                  'eventSequence', 'complete', 'events'})
    need(type(value['avatarModelHistoryVersion']) is int and value['avatarModelHistoryVersion'] == 1
         and identity(value['instance']) and type(value['processId']) is int and value['processId'] == pid
         and integer(value['currentGeneration'], 0, 256) and integer(value['eventSequence'], 0, 512)
         and type(value['complete']) is bool and type(value['events']) is list
         and len(value['events']) <= 512 and len(value['events']) == value['eventSequence'])
    generation = assignment = last_epoch = last_mono = 0
    requested = {}; assignments = {}
    for index, event in enumerate(value['events'], 1):
        exact(event, {'kind', 'generation', 'requestedUrl', 'resourceUrl', 'success', 'assignment',
                      'resourceIdentity', 'eventSequence', 'epochMs', 'monotonicMs'})
        need(type(event['eventSequence']) is int and event['eventSequence'] == index
             and integer(event['generation'], 1, value['currentGeneration'])
             and integer(event['epochMs'], max(1, last_epoch), epoch)
             and integer(event['monotonicMs'], last_mono))
        if index > 1: need(abs((event['epochMs']-last_epoch)-(event['monotonicMs']-last_mono)) <= 250)
        last_epoch, last_mono = event['epochMs'], event['monotonicMs']
        text(event['requestedUrl']); need(event['requestedUrl'])
        if event['kind'] == 'requested':
            generation += 1; need(event['generation'] == generation and event['resourceUrl'] is None
                and event['success'] is None and type(event['assignment']) is int and event['assignment'] == 0
                and event['resourceIdentity'] is None)
            requested[generation] = event['requestedUrl']
        else:
            need(event['generation'] in requested and event['requestedUrl'] == requested[event['generation']])
            text(event['resourceUrl']); need(event['resourceUrl'])
            need(type(event['resourceIdentity']) is str and re.fullmatch('[a-f0-9]{1,16}', event['resourceIdentity']))
            if event['kind'] == 'assigned':
                assignment += 1
                need(event['generation'] == generation and type(event['assignment']) is int
                     and event['assignment'] == assignment and event['success'] is None)
                assignments[assignment] = event
            else:
                need(event['kind'] == 'finished' and type(event['success']) is bool
                     and type(event['assignment']) is int and event['assignment'] in assignments)
                original = assignments[event['assignment']]
                need(all(event[field] == original[field] for field in
                         ('generation', 'requestedUrl', 'resourceUrl', 'assignment', 'resourceIdentity')))
    need(generation == value['currentGeneration'])
    if previous is not None:
        history(previous, pid, epoch)
        need(value['instance'] == previous['instance'] and value['currentGeneration'] >= previous['currentGeneration']
             and value['eventSequence'] >= previous['eventSequence']
             and value['events'][:len(previous['events'])] == previous['events']
             and (previous['complete'] or not value['complete']))
    return value


def _validate(value, query, pid, epoch=None, previous=None,*,postlogout=False):
    need(type(postlogout) is bool)
    command(query)
    exact(value, {'iosAvatarStateVersion', 'requestId', 'runId', 'instance', 'sequence', 'processId',
                  'clockDomain', 'clockBefore', 'clockAfter', 'source'})
    need(type(value['iosAvatarStateVersion']) is int and value['iosAvatarStateVersion'] in READS
         and value['requestId'] == query['commandId'] and value['runId'] == query['runId']
         and integer(pid, 1) and type(value['processId']) is int and value['processId'] == pid
         and identity(value['instance']) and integer(value['sequence'], 1, 1000000000)
         and value['clockDomain'] == 'native-main-avatar')
    before, after = value['clockBefore'], value['clockAfter']
    for clock in (before, after):
        exact(clock, {'epochMs', 'monotonicMs'})
        need(integer(clock['epochMs'], 1) and integer(clock['monotonicMs'], 0))
    utc, mono = after['epochMs']-before['epochMs'], after['monotonicMs']-before['monotonicMs']
    need(0 <= utc < 1500 and 0 <= mono < 1500 and abs(utc-mono) <= 250)
    if epoch is not None: fresh(after['epochMs'], epoch)
    source = value['source']
    exact(source, {'sessionId', 'requestedUrl', 'resourceUrl', 'defaultResourceUrl', 'geometryLoaded',
                   'rigReady', 'shouldRender', 'targetScale', 'modelScale', 'jointNames', 'bookmarks', 'modelHistory'}
          | ({'bookmarkFile'} if value['iosAvatarStateVersion'] >= 2 else set())
          | ({'sessionPresent'} if value['iosAvatarStateVersion'] >= 3 else set()))
    if value['iosAvatarStateVersion']>=3:
        need(type(source['sessionPresent']) is bool)
        if source['sessionPresent']:session(source['sessionId'])
        else:need(postlogout and source['sessionId']=='00000000-0000-0000-0000-000000000000')
    else:session(source['sessionId']);need(not postlogout)
    for field in ('requestedUrl', 'resourceUrl', 'defaultResourceUrl'): text(source[field])
    need(source['requestedUrl'] and source['defaultResourceUrl'])
    for field in ('geometryLoaded', 'rigReady', 'shouldRender'): need(type(source[field]) is bool)
    need(not source['rigReady'] or source['geometryLoaded'])
    for field in ('targetScale', 'modelScale'): need(number(source[field], .0001, 1000))
    need(type(source['jointNames']) is list and len(source['jointNames']) <= 1024
         and len(set(source['jointNames'])) == len(source['jointNames']))
    for name in source['jointNames']: text(name, 256)
    if source['rigReady']: need(source['jointNames'])
    bookmarks = source['bookmarks']
    exact(bookmarks, {'source', 'entries', 'loadError'})
    need(bookmarks['source'] == 'AvatarBookmarks.getBookmarks' and type(bookmarks['entries']) is dict
         and type(bookmarks['loadError']) is bool)
    tree(bookmarks['entries'])
    if value['iosAvatarStateVersion'] >= 2:
        from ios.adapters.avatar_bookmarks import original_bytes
        original_bytes(source['bookmarkFile'])
    native_history = history(source['modelHistory'], pid, after['epochMs'])
    if native_history['currentGeneration']:
        wanted = [event for event in native_history['events'] if event['kind'] == 'requested'][-1]
        need(wanted['requestedUrl'] == source['requestedUrl'])
    need(len(json.dumps(value, allow_nan=False).encode()) <= LIMIT)
    if previous is not None:
        _validate(previous, dict(query, commandId=previous['requestId']), pid,postlogout=postlogout)
        need(value['iosAvatarStateVersion'] >= previous['iosAvatarStateVersion']
             and value['instance'] == previous['instance'] and value['sequence'] > previous['sequence']
             and value['requestId'] != previous['requestId'] and value['runId'] == previous['runId']
             and (postlogout or source['sessionId'] == previous['source']['sessionId'])
             and before['epochMs'] >= previous['clockAfter']['epochMs']
             and before['monotonicMs'] >= previous['clockAfter']['monotonicMs'])
        history(native_history, pid, after['epochMs'], previous['source']['modelHistory'])
    return value


def validate(value,query,pid,epoch=None,previous=None):
    """Every active consumer still requires an actual nonnull avatar session."""
    return _validate(value,query,pid,epoch,previous)


def original(value):
    return validate(value, dict(schemaVersion=1, commandId=value['requestId'], action=ACTION, runId=value['runId']),
                    value['processId'])


def model_state(value, *, original_url, avatar_url, missing_url):
    """Derive four model fields and settled scale from independent native facts.

    Expected resource identities only label an actually observed resource; they
    cannot fill a missing native result, current generation, geometry or rig.
    """
    original(value); source = value['source']; facts = source['modelHistory']
    need(facts['complete'] and abs(source['modelScale']-source['targetScale']) < .0001)
    for url in (original_url, avatar_url, missing_url): text(url); need(url)
    need(len({original_url, avatar_url, missing_url}) == 3)
    names = {original_url: 'original', avatar_url: 'A', missing_url: 'missing'}
    requested = names.get(source['requestedUrl']); need(requested is not None)
    loaded = source['geometryLoaded'] and source['rigReady']
    resource = source['resourceUrl']
    if not loaded: avatar = 'unavailable'
    elif requested == 'missing' and resource == source['defaultResourceUrl']: avatar = 'fallback'
    else:
        avatar = names.get(resource)
        need(avatar in ('original', 'A') and avatar == requested)
    generation = facts['currentGeneration']
    failed = any(event['kind'] == 'finished' and event['generation'] == generation
        and event['requestedUrl'] == source['requestedUrl'] and event['resourceUrl'] == source['requestedUrl']
        and event['success'] is False for event in facts['events'])
    return dict(requestedAvatar=requested, avatar=avatar, modelLoaded=loaded,
                loadFailed=failed if requested == 'missing' else False, scale=source['modelScale'])


def bookmark(value, name, baseline, expected=None):
    """Independently enumerate owned bookmark while preserving unrelated rows."""
    original(value); text(name, 256); need(name and type(baseline) is dict and name not in baseline)
    loaded = value['source']['bookmarks']; need(not loaded['loadError'])
    rows = loaded['entries']; need({key: row for key, row in rows.items() if key != name} == baseline)
    if name not in rows: return False
    entry = rows[name]; need(type(entry) is dict)
    if expected is not None: need(entry == expected)
    return True


class IOSAvatarState(IOSPlacesModel):
    _action = ACTION
    _command = staticmethod(command)
    _validate = staticmethod(validate)
    _acquisition_key = 'iosAvatarStateAcquisitionVersion'
