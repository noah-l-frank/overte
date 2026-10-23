"""Original inactive-phase Actor exit, without altering accepted active samples.

The closed fixture cannot provide a new HTTP response inventory. Its admitted
immutable HTTP receipt remains compilation provenance only; QObject, script,
browser, Java, lifecycle and phase observations below are newly acquired.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math

from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest,json_digest
from adapters.native_feature_observation import need,fresh,number
from adapters.native_script_object_lifetimes import validate as object_packet,ACTION
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_script_manager import diagnostic as service_packet
from adapters.pico4.browser_quiet import frame as quiet_frame
from adapters.pico4.browser_vm import join
from adapters.script_journey.history import canonical,same
from feature_journeys.phase_fixture import validate as phase_packet

VERSION=1


def validate_original_frame(value,owner,state,anchor,origin,active,*,run,fixture_url):
    """Historical original grammar only; no query or current release authority.

    Callers separately bind the originally returned bytes and physical graph.
    An accepted historical frame cannot substitute for the original warm
    completion, fresh Parent consumption or actual observer process absence.
    """
    from adapters.native_feature_observation import exact,integer,validate as native_packet
    from adapters.native_web_runtime import continuity as runtime_advance
    from adapters.pico4.browser_source import continuity as browser_advance
    from adapters.normal_feature_state import context
    json_digest(value);context(owner['binding']);pid=int(owner['binding']['processIdentity'].split(':',1)[0])
    exact(value,{'phaseBefore','phaseAfter','nativeBefore','nativeAfter','browser','runtime','objectsBefore','scripts',
        'objectsAfter','diagnostic','compiledHttpAnchor','startedHost','startedEpoch','finishedHost','finishedEpoch'})
    need(owner['phase']=='cleaned' and owner['scriptUrl'] is not None and state['quiet'] is not None and state['quiet']['complete']
        and state['native']['source']['retired'] and state['publication'] is not None and state['publication']['phase']=='accepted')
    previous=state['phase'];need(previous['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
    for name in ('phaseBefore','phaseAfter'):
        packet=value[name]
        phase_packet(packet,run=run,area='tablet-web',request=packet['requestId'],epoch=packet['capturedEpochMs'],previous=previous)
        need(packet['active'] is False and same(packet['activations'],state['phase']['activations']));previous=packet
    need(number(value['startedHost'],0,1e15) and number(value['finishedHost'],value['startedHost'],value['startedHost']+10)
        and integer(value['startedEpoch'],1) and integer(value['finishedEpoch'],value['startedEpoch']))
    before,after=value['nativeBefore'],value['nativeAfter']
    for packet in (before,after):native_packet(packet,packet['requestId'],pid,value['finishedEpoch'])
    need(before['instance']==after['instance']==active['nativeAfter']['instance']
        and after['sequence']>before['sequence']>active['nativeAfter']['sequence']
        and before['lifecycle']==after['lifecycle']==state['lifecycle']
        and len({before['requestId'],after['requestId'],active['nativeAfter']['requestId']})==3)
    browser_advance(state['native'],value['browser']);runtime_advance(state['runtime'],value['runtime'],pid,fixture_url)
    need(value['browser']['commandId']!=state['native']['commandId'] and value['runtime']['commandId']!=state['runtime']['commandId'])
    quiet_frame(dict(host=value['finishedHost'],browser=value['browser'],runtime=value['runtime']),run,fixture_url,
        owner['ownerToken'],pid,retired=True)
    need(same(value['compiledHttpAnchor'],anchor['http']))
    vm_frame=dict(objectsBefore=value['objectsBefore'],scripts=value['scripts'],objectsAfter=value['objectsAfter'],
        http=value['compiledHttpAnchor'],hostMonotonic=value['finishedHost'])
    original,facts=join(vm_frame,owner['scriptUrl'],pid,origin=origin)
    need(same(original,origin) and facts==dict(retired=True,running=False))
    object_packet(value['objectsBefore'],dict(schemaVersion=1,commandId=value['objectsBefore']['commandId'],action=ACTION),
        pid,value['objectsAfter']['capturedEpochMs'],previous=anchor['objectsAfter'])
    scripts=value['scripts'];old_loads=anchor['scripts']['source']['loads'];loads=scripts['source']['loads']
    need(scripts['instance']==anchor['scripts']['instance'] and scripts['sequence']>anchor['scripts']['sequence']
        and scripts['requestId']!=anchor['scripts']['requestId']
        and loads['sequence']>=old_loads['sequence'] and same(loads['events'][:len(old_loads['events'])],old_loads['events'])
        and not any(row['url']==owner['scriptUrl'] for row in loads['events'][len(old_loads['events']):]))
    diagnostic=value['diagnostic'];service_packet(diagnostic,value['finishedEpoch'])
    need(diagnostic['instance']==active['diagnostic']['instance'] and diagnostic['sampleSequence']>active['diagnostic']['sampleSequence']
        and not any(row['url']==owner['scriptUrl'] for row in diagnostic['scripts']))
    epochs=[value[key]['capturedEpochMs'] for key in ('phaseBefore','phaseAfter','nativeBefore','nativeAfter','browser','runtime')]
    epochs.extend(value[key][clock] for key in ('objectsBefore','scripts','objectsAfter') for clock in ('requestedEpochMs','capturedEpochMs'))
    epochs.append(diagnostic['sampleEpochMs'])
    epochs.extend(value['runtime']['source'][key]['capturedEpochMs'] for key in ('nativeBefore','java','nativeAfter'))
    for captured in epochs:
        fresh(captured,value['finishedEpoch'])
        need(max(value['finishedEpoch']-captured,
            value['startedEpoch']-captured+math.ceil((value['finishedHost']-value['startedHost'])*1000))<=1500)
    return value


class PicoBrowserActorRetirement:
    """One warm, durable transaction; uncertain/cold completion is retained."""
    def __init__(self,flow,owner,state,inactive):
        flow.lock.assert_held()
        need(flow.role=='actor' and owner['phase']=='cleaned' and owner['scriptUrl'] is not None
            and state['quiet'] is not None and state['quiet']['complete'] and state['native']['source']['retired']
            and state['publication'] is not None and state['publication']['phase']=='accepted')
        self.flow,self.owner,self.state=flow,deepcopy(owner),deepcopy(state)
        self.history=flow.source_history(owner);self.history.matches(state)
        self.vm=flow.vm_reader(owner)
        need(state['phase']['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        self.inactive=deepcopy(inactive);self.phase(inactive,state['phase'])
        need(self.vm.quiet(math.ceil(state['phase']['activations'][-1]['activatedEpochMs'])))
        self.anchor=self.vm.frame(-1)
        self.store=PrivateFeatureState(flow.store.path.with_name('pico-tablet-web-actor-retirement.json'))
        need(self.store.read() is None)
        self.roots=[(store,deepcopy(value)) for store,value in (
            (flow.store,flow.originals[flow.store.path]),(flow.role_store,flow.originals[flow.role_store.path]),
            (self.history.store,self.history.disk),(self.vm.store,self.vm.previous))]
        self.quiet=flow.cleanup_window(owner);self.quiet.verify()
        self.roots.append((self.quiet.store,deepcopy(self.quiet.disk)))
        self.root_stamps=self.original_roots()
        self.scope=dict(picoBrowserActorRetirementVersion=VERSION,runId=flow.run,role='actor',
            fixtureUrl=flow.fixture_url,binding=deepcopy(owner['binding']),ownerToken=owner['ownerToken'],
            parentSha256=digest(self.roots[0][1]),roleSha256=digest(self.roots[1][1]),
            historySha256=digest(self.history.disk),vmSha256=digest(self.vm.previous))
        self.chunks=ChatSourceChunks(self.store,self.scope);self.chunks.inventory(0)
        self.previous=None;self.raw=None;self.failed=self.completed=False;self.stamp=None
        self._admitted=canonical(self.admission());self._sealed_admitted=self._admitted
        self._sealed_raw=None;self._completed_root=None

    def admission(self):
        value=dict(owner=self.owner,state=self.state,inactive=self.inactive,anchor=self.anchor,scope=self.scope,
            roots=[dict(path=str(store.path),value=value) for store,value in self.roots],stamps=self.root_stamps)
        json_digest(value);return value

    def phase(self,value,previous):
        flow=self.flow
        phase_packet(value,run=flow.run,area=flow.area,request=value['requestId'],
            epoch=value['capturedEpochMs'],previous=previous)
        need(value['active'] is False and same(value['activations'],self.state['phase']['activations'])
            and value['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))

    def original_roots(self):
        stamps=[]
        for store,value in self.roots:
            stamp=signature(store.path.lstat())
            need(same(store.read(),value) and signature(store.path.lstat())==stamp)
            stamps.append(stamp)
        return stamps

    def originals(self):
        flow=self.flow
        need(self._admitted is self._sealed_admitted and canonical(self.admission())==self._admitted
            and (self.raw is None or self.raw is self._sealed_raw)
            and (self._completed_root is None or canonical(self.previous)==self._completed_root))
        need(self.original_roots()==self.root_stamps)
        self.history.matches(self.state);self.vm.verify();self.quiet.verify();flow.verify_images(self.state,'actor')
        need(self.original_roots()==self.root_stamps)
        self.chunks.verify();need(same(self.store.read(),self.previous))

    def write(self,phase,chunks):
        self.originals();value={**self.scope,'phase':phase,'chunks':deepcopy(chunks)}
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def clocks(self,started,epoch_started,epochs):
        flow=self.flow;measured=flow.monotonic();epoch=flow.source.epoch_ms();ended=flow.monotonic()
        need(number(measured,started,started+10) and number(ended,measured,started+10)
            and number(epoch,epoch_started,1e16))
        for captured in epochs:
            fresh(captured,epoch)
            need(max(epoch-captured,epoch_started-captured+math.ceil((ended-started)*1000),
                epoch-captured+math.ceil((ended-measured)*1000))<=1500)
        return ended,epoch

    def run(self):
        flow=self.flow
        need(not self.failed and not self.completed and self.previous is None)
        try:
            with flow.lock.held(),flow.adapter.existing_input_session(flow.selector):
                started=flow.monotonic();epoch_started=flow.source.epoch_ms();flow.runtime(self.owner)
                self.write('reading',[]);self.clocks(started,epoch_started,[epoch_started])
                before=flow.source.status(self.inactive);self.phase(before,self.inactive)
                native_before=flow.adapter._native_feature_observer(flow.selector,read_only=True).read(0)
                browser=flow.sample_native(self.owner,self.state['native'])
                reader=flow.adapter._web_runtime_observer(flow.selector,read_only=True);reader.last=deepcopy(self.state['runtime'])
                runtime=reader.read(flow.run,flow.fixture_url)
                objects_before=self.vm.objects.read(self.anchor['objectsAfter']['sequence'])
                scripts=self.vm.scripts.read(self.vm.scripts.sequence,require_effects=True,require_code_identity=True,
                    require_load_history=True,require_membership=True)
                objects_after=self.vm.objects.read(objects_before['sequence'])
                vm_frame=dict(objectsBefore=objects_before,scripts=scripts,objectsAfter=objects_after,
                    http=deepcopy(self.anchor['http']),hostMonotonic=flow.monotonic())
                # Historical HTTP is only the already admitted compilation
                # receipt, never a fresh observation of the retired fixture.
                origin,facts=join(vm_frame,self.owner['scriptUrl'],self.vm.scripts.pid,origin=self.vm.origin)
                need(same(origin,self.vm.origin) and facts==dict(retired=True,running=False))
                object_packet(objects_before,dict(schemaVersion=1,commandId=objects_before['commandId'],action=ACTION),
                    self.vm.scripts.pid,objects_after['capturedEpochMs'],previous=self.anchor['objectsAfter'])
                old_loads=self.anchor['scripts']['source']['loads'];loads=scripts['source']['loads']
                need(scripts['instance']==self.anchor['scripts']['instance']
                    and scripts['sequence']>self.anchor['scripts']['sequence']
                    and loads['sequence']>=old_loads['sequence']
                    and same(loads['events'][:len(old_loads['events'])],old_loads['events'])
                    and not any(row['url']==self.owner['scriptUrl'] for row in loads['events'][len(old_loads['events']):]))
                _ui,observe,_binding,guard,_installed=flow.adapter.normal_feature_runtime(flow.selector,read_only=True)
                diagnostic,_epoch=observe(0)
                service_packet(diagnostic,flow.source.epoch_ms())
                need(not any(row['url']==self.owner['scriptUrl'] for row in diagnostic['scripts']))
                native_after=flow.adapter._native_feature_observer(flow.selector,read_only=True).read(0)
                active=self.history.last
                need(native_before['instance']==native_after['instance']==active['nativeAfter']['instance']
                    and native_after['sequence']>native_before['sequence']>active['nativeAfter']['sequence']
                    and native_before['lifecycle']==native_after['lifecycle']==self.state['lifecycle'])
                need(diagnostic['instance']==active['diagnostic']['instance']
                    and diagnostic['sampleSequence']>active['diagnostic']['sampleSequence'])
                quiet_frame(dict(host=flow.monotonic(),browser=browser,runtime=runtime),flow.run,flow.fixture_url,
                    self.owner['ownerToken'],self.vm.scripts.pid,retired=True)
                after=flow.source.status(before);self.phase(after,before)
                epochs=[self.inactive['capturedEpochMs'],before['capturedEpochMs'],after['capturedEpochMs'],browser['capturedEpochMs'],
                    runtime['capturedEpochMs'],native_before['capturedEpochMs'],native_after['capturedEpochMs'],
                    objects_before['requestedEpochMs'],scripts['requestedEpochMs'],objects_after['requestedEpochMs'],diagnostic['sampleEpochMs']]
                epochs.extend(runtime['source'][key]['capturedEpochMs'] for key in ('nativeBefore','java','nativeAfter'))
                row=dict(phaseBefore=before,phaseAfter=after,nativeBefore=native_before,nativeAfter=native_after,
                    browser=browser,runtime=runtime,objectsBefore=objects_before,scripts=scripts,objectsAfter=objects_after,
                    diagnostic=diagnostic,compiledHttpAnchor=deepcopy(self.anchor['http']),
                    startedHost=started,startedEpoch=epoch_started)
                flow.runtime(self.owner);guard();self.originals();ended,epoch=self.clocks(started,epoch_started,epochs)
                row.update(finishedHost=ended,finishedEpoch=epoch)
                validate_original_frame(row,self.owner,self.state,self.anchor,self.vm.origin,active,run=flow.run,fixture_url=flow.fixture_url)
                json_digest(row);self.raw=canonical(row);self._sealed_raw=self.raw
                chunks=self.chunks.append(row,[]);self.write('ready',chunks)
                self._completed_root=canonical(self.previous)
                self.stamp=signature(self.store.path.lstat());flow.runtime(self.owner);self.originals()
                need(signature(self.store.path.lstat())==self.stamp);result=deepcopy(self.previous)
                self.clocks(started,epoch_started,epochs)
            # Session and original source-lock exits also consume the original
            # clocks. A ready-looking root alone never authorizes Actor exit.
            self.clocks(started,epoch_started,epochs);self.completed=True;return result
        except Exception:
            self.failed=True;self.completed=False;raise

    def receipt(self):
        need(self.completed and not self.failed and self.raw is not None)
        with self.flow.lock.held():
            self.originals();need(signature(self.store.path.lstat())==self.stamp)
            # Verify immutable original bytes without replacing the live
            # admitted chunk identities during a cold reader load.
            from copy import copy
            identities=tuple(self.chunks.identities);raw_bytes=self.chunks.raw_bytes
            reader=copy(self.chunks);rows=reader.load(self.previous['chunks'])
            need(len(rows)==1 and canonical(rows[0])==self.raw and tuple(reader.identities)==identities
                and reader.raw_bytes==raw_bytes and tuple(self.chunks.identities)==identities
                and self.chunks.raw_bytes==raw_bytes)
            self.originals();need(signature(self.store.path.lstat())==self.stamp)
            return deepcopy(self.previous)
