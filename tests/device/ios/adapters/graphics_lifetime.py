"""Durable original iOS Graphics marker/resource admission and final quiet proof.

Read-only product observations only. No input, fixture activation, resource
reset, public sample or whole-feature capability is supplied by this owner.
"""
# Lifetime decomposition reviewed at frozen Phone fe4684bf46585088370b3a328a738f147e670b97.
# Native clocks, WK/Qt/Vulkan lifetime and crash-safe records are iOS-owned.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
import time
from types import SimpleNamespace

from adapters.graphics_subject_geometry import aligned_entities
from adapters.native_clock_join import NativeClockAcquisition, digest, validate_join
from adapters.native_feature_observation import exact, fresh, integer, need, number, validate as native_packet
from adapters.native_graphics_subject import validate as subject_packet
from adapters.native_scene_loads import validate as loads_packet, continuity as load_continuity, committed
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack, unpack, same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.graphics_fixture import subject_ids
from feature_journeys.graphics_resources import validate_status
from ios.adapters.graphics_fixture import GraphicsFixtureReader
from ios.adapters.graphics_history import restore_native, follow_native
from ios.adapters.graphics_restart_proof import validate as restart_packet
from ios.adapters.graphics_scene import eligible, restored
from ios.adapters.login_source import nonce
from ios.adapters.web_closures import (IOSWebClosures, validate as web_packet, continuity as web_continuity,
    drained_owned_resources, RESOURCES, SOFTWARE_RESOURCES, GPU_RESOURCES)

VERSION = 1
CURSORS = {'provider', 'native', 'subject', 'loads', 'web'}
REQUIRED = RESOURCES | SOFTWARE_RESOURCES | GPU_RESOURCES | {'native-delegate', 'native-snapshot-object'}
LIVE = {'policy-grant', 'native-view', 'native-bitmap', 'scenegraph-node', 'offscreen-image',
        'cpu-texture', 'vulkan-texture', 'vulkan-image', 'vulkan-image-view', 'vulkan-sampler', 'vulkan-allocation'}


class GraphicsLifetimePending(NativeUIError):
    """Fresh valid originals have not yet admitted the complete actual marker."""


def request(packet, kind, run, fixture_url):
    if kind == 'web':
        return dict(schemaVersion=1, commandId=nonce(packet['commandId']), action='feature-ios-web-closures',
                    runId=run, fixtureUrl=fixture_url)
    return dict(schemaVersion=1, commandId=nonce(packet['requestId' if kind == 'subject' else 'commandId']),
                action='feature-graphics-subject-observe' if kind == 'subject' else 'feature-scene-load-observe', runId=run)


def marker(web, subject, run):
    """Actual entity identity/source joined to original producer-owned counters."""
    need(web['iosWebClosureVersion'] >= 5 and web['complete'] is True)
    rows = [r for r in subject['source']['entities'] if r['id'] == subject_ids(run)['marker']]
    need(len(rows) == 1 and rows[0]['type'] == 'Web' and rows[0]['visible'])
    entity = rows[0]; identity = hashlib.sha256(('web-entity:' + entity['id']).encode()).hexdigest()
    contexts = [r for r in web['contexts'] if r['descriptor']['surface'] == 'world-entity'
                and r['descriptor']['identitySha256'] == identity and r['descriptor']['sourceUrl'] == entity['sourceUrl']]
    # The marker's URL belongs to the original scene ticket, not the current
    # phase ticket; its real page polls /current for later challenge pixels.
    if (not contexts or not any(r['callbacks']['snapshot']['created'] > 0 for r in contexts)
            or not all(any(r['resources'][k]['created'] > 0 for r in contexts) for k in REQUIRED)
            or not all(any(r['resources'][k]['pending'] > 0 for r in contexts) for k in LIVE)):
        raise GraphicsLifetimePending('Actual iOS marker resource admission is incomplete')
    return [r['id'] for r in contexts]


def activity(row):
    # Read sequence/capture time advances are observations, not resource activity.
    return digest(dict(lifecycle=[row['clockJoin'][k]['lifecycle'] for k in ('nativeBefore','nativeAfter')],
        loads=row['loads']['requests'], contexts=[dict(id=r['id'], descriptor=r['descriptor'],
        callbacks=r['callbacks'], resources=r['resources']) for r in row['web']['contexts']]))


class IOSGraphicsLifetime:
    def __init__(self, adapter, selector, source, role, stage, lock, *,
                 monotonic=time.monotonic, sleep=time.sleep):
        need(isinstance(source, GraphicsFixtureReader) and role in ('primary', 'actor') and type(stage) is int and stage in (0, 1)
             and isinstance(lock, ScriptSourceLock) and callable(monotonic) and callable(sleep))
        self.adapter, self.selector, self.source, self.role, self.stage, self.lock = adapter, selector, source, role, stage, lock
        self.run, self.fixture_url = source.run, source.fixture_url
        self.monotonic, self.sleep = monotonic, sleep
        self.store = PrivateFeatureState(adapter.state_path(selector).with_name('ios-graphics-'+role+'-'+str(stage)+'-lifetime.json'))
        need(lock.path == self.store.path.with_name('script-feature-sources.lock')); lock.assert_held()
        _ui, _observe, binding, self.guard, _installed = adapter.normal_feature_runtime(selector, read_only=True)
        self.binding = deepcopy(context(binding)); self.pid = int(binding['processIdentity']); need(str(self.pid) == binding['processIdentity'])
        if source.instance is None:source.status()
        self.historical = False; self.deadline = self.local_clock = None
        self.previous = self.store.read()
        if self.previous is None:
            self.state = dict(binding=self.binding, phase='ready', cursors={k:None for k in CURSORS}, records=[],
                              activeProofs=[], original=None, windows=[], pending=None)
            self.save()
        else:self.state = self.decode(self.previous)

    def envelope(self, state):
        return dict(iosGraphicsLifetimeVersion=VERSION, runId=self.run, fixtureUrl=self.source.client.url,
                    providerInstance=self.source.instance, role=self.role, stage=self.stage, payload=pack([state]))

    def record_store(self, ordinal):
        need(integer(ordinal, 1, 256))
        return PrivateFeatureState(self.store.path.with_name('ios-graphics-'+self.role+'-'+str(self.stage)+'-lifetime-'+str(ordinal)+'.json'))

    def validate_packet(self, kind, packet):
        need(type(packet) is dict)
        if kind == 'provider':
            validate_status(packet, instance=self.source.instance, run=self.run, url=self.source.client.url, request=packet['requestId'])
        elif kind == 'native':native_packet(packet, nonce(packet['requestId']), self.pid, packet['capturedEpochMs'])
        elif kind == 'subject':
            subject_packet(packet, request(packet, kind, self.run, self.fixture_url), self.pid, packet['capturedEpochMs'],
                           require_avatar=True, require_camera=True)
        elif kind == 'loads':
            loads_packet(packet, request(packet, kind, self.run, self.fixture_url), self.pid, packet['capturedEpochMs'])
            need(packet['complete'] is True)
        else:
            need(kind == 'web'); web_packet(packet, request(packet, kind, self.run, self.fixture_url), self.pid, packet['capturedEpochMs'])
            need(packet['iosWebClosureVersion'] >= 5 and packet['complete'] is True)

    def follows(self, kind, old, new, *, equal=False):
        if old is None:return
        if equal and same(old, new):return
        if kind == 'provider':
            validate_status(new, instance=self.source.instance, run=self.run, url=self.source.client.url, request=new['requestId'], previous=old)
        elif kind == 'loads':load_continuity(old, new, self.pid)
        elif kind == 'web':web_continuity(old, new, self.pid)
        else:
            need(new['instance'] == old['instance'] and new['sequence'] > old['sequence']
                 and new['capturedEpochMs'] >= old['capturedEpochMs'] and new['requestedEpochMs'] >= old['capturedEpochMs'])
            if kind == 'native':
                follow_native(old,new)

    @staticmethod
    def packets(row):
        return dict(provider=row['providerAfter'], native=row['clockJoin']['nativeAfter'],
                    subject=row['subject'], loads=row['loads'], web=row['web'])

    def original(self, value):
        exact(value, {'subject', 'restart'}); packet=value['subject']
        subject_packet(packet, request(packet, 'subject', self.run, self.fixture_url), packet['processId'], packet['capturedEpochMs'],
                       require_avatar=True, require_camera=True); eligible(packet)
        if self.stage == 0:
            need(value['restart'] is None and packet['processId'] == self.pid)
        else:
            proof = restart_packet(value['restart'])
            need(proof['input']['ownerFiles'] == [str(self.store.path.with_name(name)) for name in
                ('ios-graphics-scene.json','ios-graphics-primary-0-samples.json','ios-graphics-actor-0-samples.json')]
                 and same(proof['input']['newBinding'], self.binding) and packet['processId'] == proof['oldNative']['processId']
                 and packet['instance'] == proof['oldNative']['instance']
                 and packet['capturedEpochMs'] <= proof['oldNative']['requestedEpochMs'])
        return value

    def group(self, row, original=None, admitted=None):
        exact(row, {'ordinal', 'intent', 'mode', 'providerBefore', 'subject', 'loads', 'web', 'providerAfter', 'clockJoin'})
        need(integer(row['ordinal'], 1, 256) and row['mode'] in ('active', 'held', 'released'))
        exact(row['intent'], {'ordinal','kind','window'})
        need(row['intent']['ordinal'] == row['ordinal'] and (row['intent']['kind'] == 'active') == (row['mode'] == 'active'))
        for kind, key in (('provider','providerBefore'), ('subject','subject'), ('loads','loads'), ('web','web'), ('provider','providerAfter')):
            self.validate_packet(kind, row[key])
        self.follows('provider', row['providerBefore'], row['providerAfter'])
        packets = {k:row[k] for k in ('subject','loads','web')}; clock=validate_join(row['clockJoin'], packets)
        need(clock['nativeBefore']['processId'] == self.pid and clock['nativeBefore']['instance'] == row['subject']['instance']
             and row['providerBefore']['capturedEpochMs'] <= clock['hostBeforeEpochMs'] <= clock['hostAfterEpochMs'] <= row['providerAfter']['capturedEpochMs']
             and row['providerAfter']['capturedEpochMs'] - row['providerBefore']['capturedEpochMs'] < 1500)
        follow_native(clock['nativeBefore'],clock['nativeAfter'])
        committed(row['loads'], row['subject']['source']['sceneUrl'])
        if row['mode'] == 'active':
            before, after = row['providerBefore'], row['providerAfter']
            need(before['active'] and after['active'] and before['ticket'] == after['ticket'] and after['sceneTicket'] is not None)
            aligned_entities(row['subject'], self.run, after['sceneTicket'], self.fixture_url)
            marker(row['web'], row['subject'], self.run)
        else:
            need(not row['providerBefore']['active'] and not row['providerAfter']['active'] and original is not None and admitted is not None)
            self.original(original); restored(original['subject'], row['subject'])
            web_continuity(admitted['web'], row['web'], self.pid)
            held = any(c['pending'] for r in row['web']['contexts'] for collection in ('callbacks','resources') for c in r[collection].values())
            need(held == (row['mode'] == 'held'))
            if not held:drained_owned_resources(row['web'], admitted['web'])
        return row

    def load(self, reference):
        exact(reference, {'ordinal', 'sha256'}); store=self.record_store(reference['ordinal'])
        value=store.read() if getattr(self,'_archives',None) is None else self._archives.get(reference['ordinal'])
        need(value is not None and digest(value) == reference['sha256'])
        exact(value, {'iosGraphicsLifetimeRecordVersion', 'runId', 'fixtureUrl', 'providerInstance', 'role', 'stage', 'binding', 'payload'})
        need(type(value['iosGraphicsLifetimeRecordVersion']) is int and value['iosGraphicsLifetimeRecordVersion'] == 1
             and value['runId'] == self.run and value['fixtureUrl'] == self.source.client.url and value['providerInstance'] == self.source.instance
             and value['role'] == self.role and type(value['stage']) is int and value['stage'] == self.stage and same(value['binding'], self.binding))
        rows=unpack(value['payload']); need(len(rows) == 1 and type(rows[0]['ordinal']) is int and rows[0]['ordinal'] == reference['ordinal']); return rows[0]

    def decode(self, value):
        exact(value, {'iosGraphicsLifetimeVersion','runId','fixtureUrl','providerInstance','role','stage','payload'})
        rows=unpack(value['payload']); need(len(rows) == 1 and type(value['iosGraphicsLifetimeVersion']) is int and value['iosGraphicsLifetimeVersion'] == VERSION
            and same(value, self.envelope(rows[0])))
        state=rows[0]; exact(state, {'binding','phase','cursors','records','activeProofs','original','windows','pending'})
        need(same(context(state['binding']), self.binding) and state['phase'] in ('ready','releasing','released')
             and type(state['records']) is list and len(state['records']) <= 256 and type(state['activeProofs']) is list and len(state['activeProofs']) <= 8
             and type(state['windows']) is list and len(state['windows']) <= 8)
        exact(state['cursors'], CURSORS)
        for k,p in state['cursors'].items():
            if p is not None:self.validate_packet(k,p)
        original=state['original']
        if original is not None:self.original(original)
        accepted={k:None for k in CURSORS}; active={}; records={}
        for ordinal,ref in enumerate(state['records'],1):
            need(ref['ordinal'] == ordinal); row=self.load(ref); records[ordinal]=row
            if row.get('mode') == 'abandoned':
                exact(row, {'ordinal','mode','intent','cursors'}); self.intent(row['intent'],ordinal,state)
                exact(row['cursors'], CURSORS); packets=row['cursors']
                for kind,p in packets.items():
                    if p is not None:self.validate_packet(kind,p)
            else:
                self.intent(row['intent'],ordinal,state)
                self.group(row,original,next(iter(active.values())) if active else None)
                self.follows('native',accepted['native'],row['clockJoin']['nativeBefore'],equal=True)
                packets=self.packets(row)
                if row['mode'] == 'active':active[ordinal]=row
            for kind,p in packets.items():
                if p is not None:self.follows(kind,accepted[kind],p,equal=True); accepted[kind]=p
                else:need(accepted[kind] is None)
        need(state['activeProofs'] == list(active))
        for kind,p in accepted.items():
            if p is not None:need(state['cursors'][kind] is not None); self.follows(kind,p,state['cursors'][kind],equal=True)
            if state['pending'] is None:need(same(p,state['cursors'][kind]))
        if active:
            first=next(iter(active.values()))
            if self.stage == 0 and original is not None:
                need(original['subject']['instance'] == first['subject']['instance'] and original['subject']['sequence'] < first['subject']['sequence'])
        for index,window in enumerate(state['windows']):
            exact(window, {'samples','start','elapsedMs','complete'})
            need(type(window['samples']) is list and len(window['samples']) <= 81 and type(window['complete']) is bool
                 and integer(window['elapsedMs'],0,20000) and original is not None and active
                 and (window['start'] is None or integer(window['start'],0,len(window['samples'])-1)))
            need(all(type(n) is int and n in records and records[n]['mode'] in ('held','released','abandoned') for n in window['samples'])
                 and window['samples'] == sorted(set(window['samples'])))
            need(window['samples'] == [n for n,row in records.items() if row['intent']['kind'] == 'release' and row['intent']['window'] == index])
            if window['complete']:
                need(window['start'] is not None and window['elapsedMs'] >= 3000)
                quiet=[records[n] for n in window['samples'][window['start']:]]; self.quiet(quiet)
                need(window['elapsedMs'] == math.floor((quiet[-1]['clockJoin']['hostBeforeMonotonic']-quiet[0]['clockJoin']['hostAfterMonotonic'])*1000))
        if state['phase'] == 'ready':need(original is None and not state['windows'])
        else:need(original is not None and active and state['windows'])
        if state['phase'] == 'released':need(state['windows'][-1]['complete'] and state['pending'] is None)
        if state['pending'] is not None:
            self.intent(state['pending'],len(state['records'])+1,state)
            need(state['pending']['kind'] == ('active' if state['phase'] == 'ready' else 'release'))
        return state

    def intent(self, value, ordinal, state):
        exact(value, {'ordinal','kind','window'})
        need(type(value['ordinal']) is int and value['ordinal'] == ordinal and value['kind'] in ('active','release'))
        if value['kind'] == 'active':need(value['window'] is None)
        else:need(integer(value['window'],0,len(state['windows'])-1))

    def bound(self):
        need(not self.historical); self.lock.assert_held(); need(self.guard() is not False and same(self.store.read(),self.previous))
        now=self.monotonic(); need(number(now,0,1e15) and (self.local_clock is None or now >= self.local_clock)
            and (self.deadline is None or now < self.deadline)); self.local_clock=now; return now

    def save(self):
        self.bound(); value=self.envelope(self.state); self.store.write(value,self.previous)
        need(same(self.store.read(),value)); self.previous=deepcopy(value); self.bound()

    def accept(self, kind, packet):
        self.bound(); self.validate_packet(kind,packet); self.follows(kind,self.state['cursors'][kind],packet)
        self.state['cursors'][kind]=deepcopy(packet); self.save(); return packet

    def store_record(self, row):
        ordinal=row['ordinal']; store=self.record_store(ordinal)
        value=dict(iosGraphicsLifetimeRecordVersion=1,runId=self.run,fixtureUrl=self.source.client.url,
                   providerInstance=self.source.instance,role=self.role,stage=self.stage,binding=self.binding,payload=pack([row]))
        previous=store.read()
        if previous is None:store.write(value,None)
        else:need(same(previous,value))
        need(same(store.read(),value)); return dict(ordinal=ordinal,sha256=digest(value))

    def adopt(self, reference):
        self.bound(); intent=self.state['pending']; self.intent(intent,len(self.state['records'])+1,self.state)
        row=self.load(reference); need(row['ordinal'] == intent['ordinal'])
        if row.get('mode') == 'abandoned':need(same(row['intent'],intent) and same(row['cursors'],self.state['cursors']))
        else:
            admitted=self.load(self.state['records'][self.state['activeProofs'][0]-1]) if self.state['activeProofs'] else None
            self.group(row,self.state['original'],admitted)
            need(same(row['intent'],intent) and (row['mode'] == 'active') == (intent['kind'] == 'active'))
            for kind,p in self.packets(row).items():self.follows(kind,p,self.state['cursors'][kind],equal=True)
        self.state['records'].append(deepcopy(reference))
        if intent['kind'] == 'active' and row['mode'] == 'active':self.state['activeProofs'].append(row['ordinal'])
        elif intent['kind'] == 'release':self.state['windows'][intent['window']]['samples'].append(row['ordinal'])
        self.state['pending']=None; self.save(); return row

    def recover(self):
        """Adopt retained history or retire a lost passive read, never replay input."""
        self.bound(); intent=self.state['pending']
        if intent is None:return
        store=self.record_store(intent['ordinal']); value=store.read()
        if value is None:
            ref=self.store_record(dict(ordinal=intent['ordinal'],mode='abandoned',intent=deepcopy(intent),cursors=deepcopy(self.state['cursors'])))
        else:ref=dict(ordinal=intent['ordinal'],sha256=digest(value))
        self.adopt(ref) # Historical ownership only; no public current fact.

    def read_group(self, kind, window=None):
        self.bound(); need(self.state['pending'] is None and len(self.state['records']) < 256)
        intent=dict(ordinal=len(self.state['records'])+1,kind=kind,window=window); self.intent(intent,intent['ordinal'],self.state)
        self.state['pending']=intent; self.save(); started=self.bound(); epoch=self.source.clock()
        before=self.accept('provider',self.source.status(self.state['cursors']['provider']))
        native=self.adapter._native_feature_observer(self.selector,read_only=True); restore_native(native,self.state['cursors']['native'])
        acquisition=NativeClockAcquisition(native,epoch_ms=self.source.clock,monotonic=self.monotonic)
        acquisition.begin(math.ceil(before['capturedEpochMs'])); self.accept('native',acquisition.started['nativeBefore'])
        subject=self.adapter._graphics_subject_observer(self.selector,read_only=True); subject.last=deepcopy(self.state['cursors']['subject'])
        actual=self.accept('subject',subject.read(self.run,require_avatar=True,require_camera=True))
        loads=self.adapter._scene_load_observer(self.selector,read_only=True); loads.last=deepcopy(self.state['cursors']['loads'])
        pending=self.accept('loads',loads.read(self.run))
        web=self.adapter._web_closure_observer(self.selector,read_only=True); need(isinstance(web,IOSWebClosures)); web.last=deepcopy(self.state['cursors']['web'])
        closures=self.accept('web',web.read(self.run,self.fixture_url))
        originals=dict(subject=actual,loads=pending,web=closures)
        clock=acquisition.finish(originals,[(k,'capturedEpochMs') for k in originals]); self.accept('native',clock['nativeAfter'])
        after=self.accept('provider',self.source.status(self.state['cursors']['provider']))
        mode='active' if kind == 'active' else ('held' if any(c['pending'] for r in closures['contexts']
              for collection in ('callbacks','resources') for c in r[collection].values()) else 'released')
        row=dict(ordinal=intent['ordinal'],intent=deepcopy(intent),mode=mode,providerBefore=before,subject=actual,loads=pending,web=closures,providerAfter=after,clockJoin=clock)
        admitted=self.load(self.state['records'][self.state['activeProofs'][0]-1]) if self.state['activeProofs'] else None
        self.group(row,self.state['original'],admitted)
        ref=self.store_record(row); self.adopt(ref)
        end=self.bound(); now=self.source.clock(); fresh(before['capturedEpochMs'],now)
        need(now-epoch < 1500 and end-started < 1.5 and abs(now-epoch-(end-started)*1000) <= 250)
        return ref,row

    def observe_active(self):
        self.bound(); need(self.state['phase'] == 'ready' and len(self.state['activeProofs']) < 8)
        started=self.bound(); self.deadline=started+20
        try:
            before=len(self.state['activeProofs']); self.recover()
            if len(self.state['activeProofs']) > before:return deepcopy(self.state['records'][self.state['activeProofs'][-1]-1])
            need(len(self.state['activeProofs']) < 8); ref,_row=self.read_group('active'); return deepcopy(ref)
        finally:self.deadline=None

    @staticmethod
    def quiet(rows):
        need(len(rows) >= 3 and all(row['mode'] == 'released' for row in rows) and len({activity(row) for row in rows}) == 1)
        first,last=rows[0]['clockJoin'],rows[-1]['clockJoin']
        need(last['hostBeforeEpochMs']-first['hostAfterEpochMs'] >= 3000
             and last['nativeBefore']['capturedEpochMs']-first['nativeAfter']['capturedEpochMs'] >= 3000
             and last['hostBeforeMonotonic']-first['hostAfterMonotonic'] >= 3)

    def wait_released(self, original, *, restart=None):
        self.bound(); need(self.state['activeProofs'] and len(self.state['windows']) < 8)
        expected=self.original(dict(subject=deepcopy(original),restart=deepcopy(restart)))
        if self.state['original'] is not None:need(same(expected,self.state['original']))
        started=self.bound(); self.deadline=started+20
        try:
            self.recover(); self.state.update(phase='releasing',original=expected)
            self.state['windows'].append(dict(samples=[],start=None,elapsedMs=0,complete=False)); self.save()
            index=len(self.state['windows'])-1; since=None; last_activity=None
            for attempt in range(81):
                _ref,row=self.read_group('release',index); now=self.bound(); current=activity(row)
                window=self.state['windows'][index]
                if row['mode'] != 'released':since=None; last_activity=None; window.update(start=None,elapsedMs=0)
                else:
                    if since is None or current != last_activity:
                        since=row['clockJoin']['hostAfterMonotonic']; window['start']=len(window['samples'])-1
                    last_activity=current; window['elapsedMs']=max(0,math.floor((row['clockJoin']['hostBeforeMonotonic']-since)*1000))
                    refs=window['samples'][window['start']:]
                    if len(refs) >= 3 and row['clockJoin']['hostBeforeMonotonic']-since >= 3:
                        rows=[self.load(self.state['records'][n-1]) for n in refs]; self.quiet(rows)
                        window['complete']=True; self.state['phase']='released'; self.save(); self.decode(self.previous); self.bound()
                        return deepcopy(self.previous)
                self.save(); need(attempt < 80); self.sleep(.25); self.bound()
        finally:self.deadline=None

    @classmethod
    def archive(cls, value, *, path, run, fixture_url, provider_instance, role, stage, binding, records=None):
        """Pure historical validation; no live SDK/factory, write or clock exists."""
        identifier(run); identifier(provider_instance); context(binding)
        need(role in ('primary','actor') and type(stage) is int and stage in (0,1))
        scope=object.__new__(cls); scope.run,scope.fixture_url=run,fixture_url+'/runs/'+run+'/'
        scope.source=SimpleNamespace(instance=provider_instance,client=SimpleNamespace(url=fixture_url))
        scope.role,scope.stage,scope.binding,scope.pid=role,stage,deepcopy(binding),int(binding['processIdentity'])
        scope.store=PrivateFeatureState(path); scope.historical=True
        if records is not None:
            need(type(records) is dict and all(type(n) is int for n in records))
            rows=unpack(value['payload']); need(len(rows) == 1 and set(records) == {r['ordinal'] for r in rows[0]['records']})
        scope._archives=deepcopy(records)
        need(scope.store.path.name == 'ios-graphics-'+role+'-'+str(stage)+'-lifetime.json')
        return deepcopy(scope.decode(value))
