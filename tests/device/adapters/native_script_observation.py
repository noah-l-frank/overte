"""Source-owned engine membership and actual CommonJS require history.

No module path, code, expected companion, engine ID or verdict is sent to the
native getter. It cannot load/stop/restart a script or touch a foreign JS heap.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from copy import deepcopy
import posixpath
import re
import time
import uuid
from urllib.parse import unquote, urlsplit

from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.normal_ui import NativeUIError

FILE = 'feature-script-observation.json'
LIMIT = 262144


def text(value):
    return type(value) is str and 0 < len(value) <= 4096 and not any(ord(c) < 32 for c in value)


def validate(value, request, pid, epoch):
    exact(value, {'schemaVersion', 'requestId', 'instance', 'sequence', 'requestedEpochMs',
                  'capturedEpochMs', 'processId', 'source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1 and value['requestId'] == request
         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}', value['instance'])
         and integer(value['sequence'], 1) and integer(value['processId'], 1) and value['processId'] == pid
         and integer(value['requestedEpochMs'], 1) and integer(value['capturedEpochMs'], 1)
         and 0 <= value['capturedEpochMs'] - value['requestedEpochMs'] < 5000)
    fresh(value['capturedEpochMs'], epoch)
    source = value['source']
    extended = type(source) is dict and 'effectSourceVersion' in source
    identified = type(source) is dict and 'sourceIdentityVersion' in source
    fields = {'complete','engines'}
    if extended: fields |= {'effectSourceVersion','effects'}
    if identified:
        fields.add('sourceIdentityVersion')
        need(type(source['sourceIdentityVersion']) is int and source['sourceIdentityVersion'] == 1)
    exact(source, fields)
    need(source['complete'] is True and type(source['engines']) is list and len(source['engines']) <= 128)
    identities = set()
    for engine in source['engines']:
        exact(engine, {'url', 'running', 'stopping', 'finished', 'required'} | ({'code'} if identified else set()))
        if identified: validate_code(engine['code'],value['capturedEpochMs'])
        need(text(engine['url'])
             and all(type(engine[key]) is bool for key in ('running', 'stopping', 'finished')))
        required = engine['required']
        exact(required, {'instance', 'sequence', 'modules'})
        need(type(required['instance']) is str and re.fullmatch('[0-9a-f]{32}', required['instance'])
             and required['instance'] not in identities and integer(required['sequence'], 0, 1000000000)
             and type(required['modules']) is list and len(required['modules']) <= 256)
        identities.add(required['instance'])
        module_urls, cursors = set(), set()
        for module in required['modules']:
            exact(module, {'url', 'loaded', 'cached', 'sequence', 'capturedEpochMs'})
            need(text(module['url']) and module['url'] not in module_urls
                 and type(module['loaded']) is bool and type(module['cached']) is bool
                 and integer(module['sequence'], 1, required['sequence']) and module['sequence'] not in cursors
                 and integer(module['capturedEpochMs'], 1) and module['capturedEpochMs'] <= value['capturedEpochMs'])
            module_urls.add(module['url']); cursors.add(module['sequence'])
        need((required['sequence'] == 0) == (not required['modules']))
        if required['modules']:
            need(max(cursors) == required['sequence'])
    if extended:
        need(type(source['effectSourceVersion']) is int and source['effectSourceVersion'] == 1)
        effects = source['effects']
        exact(effects, {'complete', 'scanRadiusMeters', 'scannedEntities', 'entities', 'absentIds'})
        need(effects['complete'] is True and type(effects['scanRadiusMeters']) is int and effects['scanRadiusMeters'] == 64
             and integer(effects['scannedEntities'], 0, 4096)
             and type(effects['entities']) is list and len(effects['entities']) <= 32
             and type(effects['absentIds']) is list and len(effects['absentIds']) <= 256)
        seen = set()
        for row in effects['entities']:
            exact(row, {'id', 'name', 'type', 'hostType', 'userData', 'lastEditedEpochUs', 'color'})
            need(entity_id(row['id']) and row['id'] not in seen and text(row['name']) and len(row['name']) <= 256
                 and text(row['type']) and row['hostType'] in ('local', 'avatar', 'domain')
                 and type(row['userData']) is str and len(row['userData']) <= 1024
                 and integer(row['lastEditedEpochUs'], 1) and row['lastEditedEpochUs'] <= value['capturedEpochMs'] * 1000 + 999
                 and type(row['color']) is list and len(row['color']) == 3
                 and all(integer(channel, 0, 255) for channel in row['color']))
            seen.add(row['id'])
        for identifier in effects['absentIds']:
            need(entity_id(identifier) and identifier not in seen); seen.add(identifier)
        need(len(seen) <= 256)
    return value


def validate_code(value, captured):
    exact(value, {'submitted','encoding','codeUnits','sha256','submittedEpochMs'})
    need(type(value['submitted']) is bool and value['encoding']=='utf-16le-code-units'
         and integer(value['codeUnits'],0,4194304) and type(value['sha256']) is str
         and integer(value['submittedEpochMs']))
    if value['submitted']:
        need(re.fullmatch('[0-9a-f]{64}',value['sha256']) is not None
             and 0 < value['submittedEpochMs'] <= captured)
    else: need(value['codeUnits']==0 and value['sha256']=='' and value['submittedEpochMs']==0)


def submitted_source(value, source_url):
    """Actual unique live source identity, not proof its initialization succeeded."""
    need(type(value['source'].get('sourceIdentityVersion')) is int and value['source']['sourceIdentityVersion']==1)
    engine=running_owned_engine(value,source_url)
    need(engine['code']['submitted'])
    return deepcopy(engine['code'])


def entity_id(value):
    try:
        return type(value) is str and str(uuid.UUID(value)) == value and uuid.UUID(value).int != 0
    except ValueError: return False


def measured_effect(value, run):
    """Actual unique local Box and native color/data; empty data is not a tick."""
    need(type(run) is str and re.fullmatch('[0-9a-f]{32}', run))
    source = value['source']
    need(type(source.get('effectSourceVersion')) is int and source['effectSourceVersion'] == 1)
    rows = [row for row in source['effects']['entities'] if row['name'] == 'e2e-' + run + '-script']
    need(len(rows) <= 1)
    if not rows: return None
    row = rows[0]
    need(row['type'] == 'Box' and row['hostType'] == 'local')
    if row['userData'] == '': return dict(row, ticks=None)
    data = decode(row['userData'])
    exact(data, {'runId', 'ticks'})
    need(data['runId'] == run and integer(data['ticks'], 0, 1000000000)
         and row['color'] == [(data['ticks'] % 2) * 255, 128, 0])
    return dict(row, ticks=data['ticks'])


def effect_absent(value, identifier):
    need(entity_id(identifier) and type(value['source'].get('effectSourceVersion')) is int
         and value['source']['effectSourceVersion'] == 1)
    return identifier in value['source']['effects']['absentIds']


def running_owned_engine(value, source_url):
    """Select the actual unique active source; never guess by its basename."""
    need(text(source_url))
    engines = [engine for engine in value['source']['engines'] if engine['url'] == source_url
               and engine['running'] and not engine['stopping'] and not engine['finished']]
    need(len(engines) == 1)
    return engines[0]


def loaded_relative_modules(engine):
    """Public aliases measured from actually loaded URLs in this source root."""
    main = urlsplit(engine['url'])
    path = unquote(main.path, errors='strict')
    need(main.scheme in ('file', 'http', 'https') and not main.query and not main.fragment
         and path.startswith('/') and '\\' not in path and '..' not in path.split('/'))
    root = posixpath.dirname(path) + '/'
    modules = []
    for module in engine['required']['modules']:
        if not module['loaded']: continue
        parsed = urlsplit(module['url'])
        path = unquote(parsed.path, errors='strict')
        need('\\' not in path and '..' not in path.split('/'))
        if ((parsed.scheme, parsed.netloc) == (main.scheme, main.netloc)
                and not parsed.query and not parsed.fragment and path.startswith(root)):
            relative = path[len(root):]
            need(bool(relative) and relative not in modules)
            modules.append(relative)
    return sorted(modules)


class NativeScriptObservation:
    def __init__(self, send, read, clock_ms, guard, pid, *, ios=False,
                 monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(v) for v in (send, read, clock_ms, guard, monotonic, sleep))
             and integer(pid, 1) and type(ios) is bool)
        self.send, self.original, self.clock_ms, self.guard, self.pid = send, read, clock_ms, guard, pid
        self.ios, self.monotonic, self.sleep = ios, monotonic, sleep
        self.instance, self.sequence, self.engines = None, 0, {}
        self.active, self.retired = set(), set()
        self.effect_rows, self.absent_effects = {}, set()
        self.effects_required = False
        self.code_required = False

    def read(self, after_sequence, *, require_effects=False, require_code_identity=False):
        try:
            need(type(require_effects) is bool and type(require_code_identity) is bool)
            need(integer(after_sequence) and after_sequence >= self.sequence and self.guard() is not False)
            started = previous = self.monotonic()
            need(number(started, 0, 1e15))
            requested = self.clock_ms()
            need(integer(requested, 1))
            need(self.guard() is not False)
            now = self.monotonic()
            need(number(now, 0, 1e15) and now >= previous and now - started < 5)
            previous = now
            request = ('ios-' if self.ios else '') + uuid.uuid4().hex
            self.send(dict(schemaVersion=1, commandId=request, action='feature-script-observe'))
            for attempt in range(51):
                need(self.guard() is not False)
                raw = self.original()
                try:
                    value = decode(raw) if raw else None
                except json.JSONDecodeError:
                    value = None
                need(self.guard() is not False)
                now = self.monotonic()
                need(number(now, 0, 1e15) and now >= previous and now - started < 5)
                previous = now
                if type(value) is dict and value.get('requestId') == request:
                    epoch = self.clock_ms()
                    need(integer(epoch, 1) and epoch >= requested)
                    validate(value, request, self.pid, epoch)
                    need(self.instance in (None, value['instance']) and value['sequence'] > after_sequence
                         and value['requestedEpochMs'] >= requested)
                    source = value['source']
                    need(not (require_effects or self.effects_required) or source.get('effectSourceVersion') == 1)
                    identified = source.get('sourceIdentityVersion') == 1
                    need(not (require_code_identity or self.code_required) or identified)
                    next_effects, absent = None, None
                    if source.get('effectSourceVersion') == 1:
                        next_effects = {row['id']: row for row in source['effects']['entities']}
                        absent = set(source['effects']['absentIds'])
                        need(self.absent_effects <= absent and not self.absent_effects & set(next_effects)
                             and set(self.effect_rows) <= set(next_effects) | absent)
                        for identifier, row in next_effects.items():
                            old = self.effect_rows.get(identifier)
                            if old is not None:
                                need(row['name'] == old['name'] and row['type'] == old['type']
                                     and row['hostType'] == old['hostType']
                                     and row['lastEditedEpochUs'] >= old['lastEditedEpochUs'])
                                if row['lastEditedEpochUs'] == old['lastEditedEpochUs']: need(row == old)
                        need(len(set(next_effects) | absent) <= 256)
                    engines = {}
                    for engine in value['source']['engines']:
                        source = engine['required']
                        instance = source['instance']
                        need(instance not in self.retired)
                        old = self.engines.get(instance)
                        if old is not None:
                            need(old['url'] == engine['url'] and source['sequence'] >= old['sequence'])
                            if old.get('code',{}).get('submitted'):
                                need(identified and engine['code']==old['code'])
                            modules = {m['url']: m for m in source['modules']}
                            for module in old['modules']:
                                need(module['url'] in modules and modules[module['url']]['sequence'] >= module['sequence']
                                     and modules[module['url']]['capturedEpochMs'] >= module['capturedEpochMs'])
                            previous_modules = {m['url']: m for m in old['modules']}
                            for module in source['modules']:
                                previous_module = previous_modules.get(module['url'])
                                if previous_module is not None and module['sequence'] == previous_module['sequence']:
                                    need(module == previous_module)
                                else:
                                    need(module['sequence'] > old['sequence'])
                        engines[instance] = dict(url=engine['url'], sequence=source['sequence'], modules=deepcopy(source['modules']))
                        if identified: engines[instance]['code']=deepcopy(engine['code'])
                    need(self.guard() is not False)
                    need(len(set(self.engines) | set(engines)) <= 4096)
                    now = self.monotonic()
                    need(number(now, 0, 1e15) and now >= previous and now - started < 5)
                    self.retired |= self.active - set(engines)
                    self.active = set(engines)
                    self.engines.update(engines)
                    if next_effects is not None:
                        self.effect_rows, self.absent_effects = deepcopy(next_effects), absent
                        self.effects_required = True
                    self.code_required = self.code_required or identified
                    self.instance, self.sequence = value['instance'], value['sequence']
                    return value
                if attempt < 50: self.sleep(0.1)
        except Exception:
            raise NativeUIError('Native Script execution observation is unavailable or invalid') from None
        raise NativeUIError('Native Script execution observation did not produce this request')
