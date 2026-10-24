"""One explicit continuation of the existing v16 Navigation prefix at restart.

The original prefix header/Binding/Session evidence stays unchanged. This is a
boundary ledger for the same recipe, not a second Journey or a replayable plan.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.native_feature_observation import need,exact,number,fresh
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation_originals import verify_archive
from adapters.pico4.navigation_restart import NavigationRestart
from adapters.script_journey.history import same,unpack
from feature_journeys.contract import arguments
from feature_journeys.phase_fixture import PhasePending
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.fixtures import context

VERSION=1


class NavigationContinuation:
    def __init__(self,prefix,restart_factory):
        need(callable(restart_factory));self.prefix=prefix;self.restart_factory=restart_factory;self.restart_owner=None
        self.continuation_store=PrivateFeatureState(prefix.lock.path.with_name('navigation-prefix-restart-parent.json'))
        self.continuation_disk=self.continuation_store.read()
        if self.continuation_disk is not None:self.validate_continuation(self.continuation_disk)

    def __getattr__(self,key):return getattr(self.prefix,key)

    def load_continuation(self):
        current=self.continuation_store.read()
        if self.continuation_disk is None:
            if current is None:return
            # An already-running passive role may first encounter the primary's
            # real boundary here. Refresh only the actual original header;
            # neither old Qt nor its stale child caches are queried.
            self.prefix.load();self.validate_continuation(current);self.continuation_disk=deepcopy(current)
        else:need(same(current,self.continuation_disk))

    def validate_continuation(self,value):
        exact(value,{'navigationContinuationVersion','runId','binding','scope','prefix','arguments','phase','restartSha256'})
        p=self.prefix;call=arguments('feature.world-navigation.act',value['arguments'])
        need(type(value['navigationContinuationVersion']) is int and value['navigationContinuationVersion']==VERSION
            and value['runId']==p.run and same(value['binding'],p.binding) and same(value['scope'],p.scope())
            and same(value['prefix'],p.disk) and value['prefix']['phase']=='ready' and len(value['prefix']['completed'])==11
            and value['phase'] in ('issued','ready') and (value['restartSha256'] is not None)==(value['phase']=='ready')
            and call['runId']==p.run and call['fixtureUrl']==p.phase.fixture_url)
        row=SCENARIOS['world-navigation']['steps'][11]
        need(same(dict(verb=call['verb'],inputs=call['inputs']),dict(verb=row['verb'],inputs=expand(row['inputs'],context(p.run)))))
        if value['restartSha256'] is not None:
            owner=self.restart();need(owner.state is not None and owner.state['phase']=='observed'
                and value['restartSha256']==json_digest(owner.disk))

    def restart(self):
        if self.restart_owner is None:
            owner=self.restart_factory(self.prefix)
            need(isinstance(owner,NavigationRestart) and owner.parent is self.prefix);self.restart_owner=owner
        return self.restart_owner

    def prepare(self):
        with self.prefix.lock.held():
            self.load_continuation();need(self.continuation_disk is None);return self.prefix.prepare()

    def act(self,call):
        call=deepcopy(arguments('feature.world-navigation.act',call));p=self.prefix;need(p.role=='primary')
        if call['verb']!='restart-app':
            with p.lock.held():
                self.load_continuation();need(self.continuation_disk is None);return p.act(call)
        # A private caller holding another outer context cannot publish a
        # result after that caller's still-future release. Refuse before input.
        need(p.lock._owner is None)
        with p.lock.held():
            self.load_continuation()
            p.load();need(p.state['phase']=='ready' and len(p.state['completed'])==11)
            if self.continuation_disk is None:
                value=dict(navigationContinuationVersion=VERSION,runId=p.run,binding=deepcopy(p.binding),scope=p.scope(),prefix=deepcopy(p.disk),
                    arguments=call,phase='issued',restartSha256=None)
                self.validate_continuation(value);self.continuation_store.write(value,None);self.continuation_disk=deepcopy(value)
            need(same(self.continuation_store.read(),self.continuation_disk) and same(self.continuation_disk['arguments'],call))
            self.restart().act(call)
            if self.continuation_disk['phase']=='issued':
                value=deepcopy(self.continuation_disk);value.update(phase='ready',restartSha256=json_digest(self.restart_owner.disk))
                self.validate_continuation(value);self.continuation_store.write(value,self.continuation_disk);self.continuation_disk=deepcopy(value)
            self.restart_owner.fence();owner=self.restart_owner
            runtime=owner.runtime if owner.runtime is not None else owner.successor(owner.inputs,owner.state)
            started=p.now();requested=runtime['native'].clock_ms()
            seal=self.seal(owner,runtime,requested,started,owner.state['newFrame']['before']['ui']['observedEpochMs'])
            result=dict(performed=True)
        self.finalize(seal)
        return result

    def observe(self):
        p=self.prefix;outer=p.lock._owner
        with p.lock.held():
            self.load_continuation()
            if self.continuation_disk is None:return p.observe()
            need(outer is None)
            need(same(self.continuation_store.read(),self.continuation_disk));self.validate_continuation(self.continuation_disk)
            if self.continuation_disk['phase']!='ready':raise PhasePending('The original Navigation restart remains unresolved')
            owner=self.restart();runtime=owner.successor(owner.inputs,owner.state);source=runtime['source'];binding=deepcopy(source.binding)
            self.runtime_scope(owner,source)
            store=PrivateFeatureState(p.lock.path.with_name('navigation-prefix-generation-1-'+p.role+'-sources.json'))
            scope=dict(runId=p.run,binding=binding,role=p.role,restartSha256=self.continuation_disk['restartSha256'])
            chunks=ChatSourceChunks(store,scope);old=store.read();manifest=[] if old is None else old['chunks'];frames=chunks.load(manifest)
            if old is not None:
                exact(old,{'navigationGenerationSamplesVersion','scope','phase','chunks'})
                need(type(old['navigationGenerationSamplesVersion']) is int and old['navigationGenerationSamplesVersion']==1
                    and same(old['scope'],scope) and old['phase']=='ready')
            previous=owner.state['newFrame']
            for frame in frames:
                source.project(frame);p.original_facts(frame);source.advance_frames(previous,frame);previous=frame
            reading=dict(navigationGenerationSamplesVersion=1,scope=scope,phase='reading',chunks=manifest);store.write(reading,old)
            phase=owner.fence();started=p.now();requested=runtime['native'].clock_ms();frame=source.capture(p.state['receipt'],phase['status'],lookup_receipt=p.state['lookupReceipt'])
            manifest=chunks.append(frame,manifest);facts=source.project(frame);p.original_facts(frame);source.advance_frames(previous,frame)
            self.runtime_scope(owner,source);need(same(frame['binding'],binding))
            result=dict(sequence=len(manifest),capturedEpochMs=frame['before']['ui']['observedEpochMs'],state=facts,
                fullNavigationRecipe=False,deviceAcceptance=False,journalsRetained=True,generation=1)
            original=PrivateFeatureState(p.lock.path.with_name('navigation-prefix-'+p.role+'-sources.json')).read()
            # Public source sequence continues the original role's acquired
            # frames. Native per-birth cursors remain in each immutable frame.
            result['sequence']+=len(original['chunks'])
            ready=deepcopy(reading);ready.update(phase='ready',chunks=manifest);store.write(ready,reading);chunks.verify()
            need(source.guard() is not False);self.runtime_scope(owner,source);owner.fence();epoch=p.phase.epoch_ms();self.runtime_scope(owner,source)
            need(number(epoch,1,1e15) and max(epoch-result['capturedEpochMs'],(p.now()-started)*1000)<=1500)
            seal=self.seal(owner,runtime,requested,started,result['capturedEpochMs'],samples=(store,ready,chunks))
        self.finalize(seal)
        return result

    def seal(self,owner,runtime,requested,started,captured,*,samples=None):
        self.runtime_scope(owner,runtime['source'])
        need(number(requested,1,1e15) and number(started,0,1e15) and number(captured,1,1e15))
        return dict(owner=owner,runtime=runtime,sourceGuard=runtime['source'].guard,nativeGuard=runtime['native'].guard,
            requested=requested,started=started,captured=captured,samples=samples)

    def finalize(self,seal):
        """No frame/query/retiming: validate originals AFTER real outer exit."""
        try:self.finalize_original(seal)
        except Exception:raise NativeUIError('Original Navigation publication after lock release is unavailable') from None

    def finalize_original(self,seal):
        p=self.prefix;owner=seal['owner'];runtime=seal['runtime'];source=runtime['source']
        need(p.lock._owner is None and source.guard is seal['sourceGuard'] and runtime['native'].guard is seal['nativeGuard'])
        p.control();self.runtime_scope(owner,source)
        need(same(self.continuation_store.read(),self.continuation_disk) and same(owner.store.read(),owner.disk)
            and same(unpack(owner.disk['payload']),[owner.state])
            and owner.state['phase']=='observed' and json_digest(p.scope())==owner.scope_sha)
        verify_archive(owner.state['files'],owner.store.path.parent,p.run,owner.state['normalUiPath'])
        if seal['samples'] is not None:
            store,body,chunks=seal['samples'];need(same(store.read(),body));chunks.verify()
        # NativeFeatureObservation's original independent PID/foreground/
        # installation guard does not require the Script source mutex. The
        # source's lock-asserting live-channel guard is not weakened or called.
        need(runtime['native'].guard() is not False)
        with runtime['session']._lock():need(same(runtime['session']._load(),owner.state['newSession']))
        self.runtime_scope(owner,source)
        phase=p.phase.read();need(phase['ticket']==owner.state['arguments']['ticket'] and phase['verb']=='restart-app'
            and same(phase['inputs'],{}) and phase['status']['instance']==owner.state['fixture']['instance']
            and same(phase['status']['activations'],owner.state['fixture']['activations']))
        epoch=runtime['native'].clock_ms();now=p.now();self.runtime_scope(owner,source)
        fresh(seal['captured'],epoch)
        need(source.guard is seal['sourceGuard'] and runtime['native'].guard is seal['nativeGuard']
            and number(epoch,1,1e15) and now>=seal['started']
            and max(epoch-seal['captured'],seal['requested']-seal['captured']+(now-seal['started'])*1000)<=1500)

    def runtime_scope(self,owner,source):
        p=self.prefix;binding=owner.state['proof']['input']['newBinding']
        need(same(source.binding,binding) and source.run==p.run and same(source.inputs,p.source.inputs)
            and source.origin==p.source.origin and source.provider_instance==p.source.provider_instance
            and same(source.profile,p.source.profile) and same(source.arrival.binding,binding)
            and source.arrival.run==p.run and source.arrival.scene_url==p.source.inputs['sceneUrl']
            and all(reader.pid==int(binding['processIdentity'].split(':',1)[0]) for reader in source.readers.values()))
