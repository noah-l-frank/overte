"""Direct compiled Chat root association; imports, SDK and whole Chat stay separate."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from adapters.native_feature_observation import exact, fresh, integer, need
from adapters.script_feature.history import same
from feature_journeys.contract import json_document
from ios.adapters.chat_script_sources import command as script_command
from ios.adapters.places_model import IOSPlacesModel

VERSION = 1
ACTION = 'feature-ios-chat-qml-sources'
FILE = ACTION + '.json'
LIMIT = 65536
QML = 'communityScripts/armored-chat/armored_chat.qml'
PIN_FILE = Path(__file__).parents[1] / 'chat-qml-source-pins.v1.json'


def command(value):
    other = deepcopy(value)
    other['action'] = 'feature-ios-chat-script-sources'
    script_command(other)
    need(value['action'] == ACTION)
    return value


def identity(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{32}', value))


def digest(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value))


def url(value, *, empty=False):
    need(type(value) is str and len(value) <= 4096)
    value.encode('utf-8')
    if empty and value == '':
        return value
    parsed = urlsplit(value)
    need(parsed.scheme in ('file', 'qrc') and not parsed.netloc and parsed.path.startswith('/')
        and '?' not in value and '#' not in value and '\\' not in value
        and '\x00' not in unquote(value) and all(part not in ('.', '..') for part in unquote(parsed.path).split('/')))
    return unquote(value)


def clock(value):
    exact(value, {'epochMs', 'monotonicMs'})
    need(integer(value['epochMs'], 1) and integer(value['monotonicMs']))


def interval(before, after, *, current=False):
    clock(before); clock(after)
    delta = after['epochMs'] - before['epochMs']
    elapsed = after['monotonicMs'] - before['monotonicMs']
    need(delta >= 0 and elapsed >= 0 and abs(delta - elapsed) <= 250)
    if current:
        need(delta < 1500 and elapsed < 1500)


def compiler_input(value, pid, epoch):
    exact(value, {'qtOverteQmlCompilerInputVersion', 'instance', 'sequence', 'processId', 'qtVersion',
        'encoding', 'codeUnits', 'sha256', 'requestedUrl', 'resolvedUrl', 'sourceBeforeEpochMs',
        'sourceAfterEpochMs', 'compilerUnitBytes', 'compilerUnitSha256', 'unitBytes', 'unitGeneration',
        'unitSha256', 'compiledEpochMs'})
    need(type(value['qtOverteQmlCompilerInputVersion']) is int and value['qtOverteQmlCompilerInputVersion'] == 1
        and integer(pid, 1) and type(value['processId']) is int and value['processId'] == pid
        and value['qtVersion'] == '6.11.1' and value['encoding'] == 'utf16-le-code-units'
        and integer(value['sequence'], 1, 1000000000) and integer(value['codeUnits'], 1, 1024 * 1024)
        and integer(value['unitBytes'], 1, 4 * 1024 * 1024) and type(value['compilerUnitBytes']) is int
        and value['compilerUnitBytes'] == value['unitBytes'] and integer(value['unitGeneration'], 0, 999999999))
    identity(value['instance'])
    for field in ('sha256', 'unitSha256', 'compilerUnitSha256'):
        digest(value[field])
    need(value['unitSha256'] == value['compilerUnitSha256'])
    for field in ('requestedUrl', 'resolvedUrl'):
        url(value[field])
    for field in ('sourceBeforeEpochMs', 'sourceAfterEpochMs', 'compiledEpochMs'):
        need(integer(value[field], 1, epoch))
    need(value['sourceBeforeEpochMs'] <= value['sourceAfterEpochMs'] <= value['compiledEpochMs'])
    return value


def loaded(value, pid, epoch):
    exact(value, {'iosLoadedQmlSourceVersion', 'instance', 'loadSequence', 'loadId', 'objectId',
        'creationContextId', 'objectContextId', 'processId', 'clockDomain', 'loadBefore', 'loadCompleted',
        'requestedUrl', 'selectedUrl', 'componentUrl', 'creationContextUrl', 'objectContextUrl', 'compilerInput'})
    need(type(value['iosLoadedQmlSourceVersion']) is int and value['iosLoadedQmlSourceVersion'] == 1
        and integer(value['loadSequence'], 1, 64) and type(value['processId']) is int and value['processId'] == pid
        and value['clockDomain'] == 'native-main-qml-load')
    for field in ('instance', 'loadId', 'objectId', 'creationContextId', 'objectContextId'):
        identity(value[field])
    interval(value['loadBefore'], value['loadCompleted'])
    need(value['loadCompleted']['epochMs'] <= epoch)
    for field in ('requestedUrl', 'selectedUrl', 'componentUrl'):
        url(value[field])
    for field in ('creationContextUrl', 'objectContextUrl'):
        url(value[field], empty=True)
    need(urlsplit(value['requestedUrl']).path.endswith('/armored-chat/armored_chat.qml'))
    source = compiler_input(value['compilerInput'], pid, epoch)
    need(value['loadBefore']['epochMs'] <= source['sourceBeforeEpochMs']
        and source['compiledEpochMs'] <= value['loadCompleted']['epochMs']
        and url(source['requestedUrl']) == url(value['componentUrl']))
    return value


def validate(value, query, pid, epoch=None, previous=None):
    command(query)
    exact(value, {'iosChatQmlSourcesVersion', 'requestId', 'runId', 'instance', 'sequence', 'processId',
        'clockDomain', 'clockBefore', 'clockAfter', 'pageControlSourceSha256', 'source'})
    need(type(value['iosChatQmlSourcesVersion']) is int and value['iosChatQmlSourcesVersion'] == VERSION
        and value['requestId'] == query['commandId'] and value['runId'] == query['runId']
        and integer(pid, 1) and type(value['processId']) is int and value['processId'] == pid
        and integer(value['sequence'], 1, 1000000000) and value['clockDomain'] == 'native-main-chat-qml-sources')
    identity(value['instance']); digest(value['pageControlSourceSha256'])
    interval(value['clockBefore'], value['clockAfter'], current=True)
    if epoch is not None:
        fresh(value['clockAfter']['epochMs'], epoch)
    current = loaded(value['source'], pid, value['clockBefore']['epochMs'])
    need(len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode()) <= LIMIT)
    if previous is not None:
        validate(previous, dict(query, commandId=previous['requestId']), pid)
        need(value['instance'] == previous['instance'] and value['sequence'] > previous['sequence']
            and value['requestId'] != previous['requestId']
            and value['clockBefore']['epochMs'] >= previous['clockAfter']['epochMs']
            and value['clockBefore']['monotonicMs'] >= previous['clockAfter']['monotonicMs'])
        old = previous['source']
        need(current['instance'] == old['instance'])
        if current['loadId'] == old['loadId']:
            need(same(current, old))
        else:
            need(current['loadSequence'] > old['loadSequence'] and current['objectId'] != old['objectId']
                and current['loadBefore']['epochMs'] >= old['loadCompleted']['epochMs']
                and current['loadBefore']['monotonicMs'] >= old['loadCompleted']['monotonicMs']
                and current['compilerInput']['instance'] == old['compilerInput']['instance']
                and current['compilerInput']['sequence'] > old['compilerInput']['sequence'])
    return value


def original(value):
    need(type(value) is dict)
    return validate(value, dict(schemaVersion=1, action=ACTION, commandId=value.get('requestId'), runId=value.get('runId')),
        value.get('processId'))


def pins():
    raw = PIN_FILE.read_bytes(); need(len(raw) <= 8192)
    value = json_document(raw)
    exact(value, {'iosChatQmlSourcePinsVersion', 'encoding', 'sources'})
    need(type(value['iosChatQmlSourcePinsVersion']) is int and value['iosChatQmlSourcePinsVersion'] == 1
        and value['encoding'] == 'utf16-le-code-units')
    exact(value['sources'], {QML})
    pin = value['sources'][QML]; exact(pin, {'codeUnits', 'sha256'})
    need(integer(pin['codeUnits'], 1, 1024 * 1024)); digest(pin['sha256'])
    return deepcopy(pin)


def admit_direct_unit(value, expected_url):
    """Only a pinned direct QML unit; no imported-code or installed-SDK admission."""
    original(value)
    actual = value['source']['compilerInput']; expected = pins()
    need(url(actual['resolvedUrl']) == url(expected_url)
        and all(actual[field] == expected[field] for field in ('codeUnits', 'sha256')))
    return deepcopy(value['source'])


class IOSChatQmlSources(IOSPlacesModel):
    _limit = LIMIT
    _action = ACTION
    _command = staticmethod(command)
    _validate = staticmethod(validate)
    _acquisition_key = 'iosChatQmlSourcesAcquisitionVersion'
