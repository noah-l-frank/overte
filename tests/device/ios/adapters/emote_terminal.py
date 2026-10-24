"""Internal rooted Emote inspect/seal operation on the existing role owners.

The whole process-end operation is not admitted here. Pending current-WAL,
failed preparation, OS death and SDK retirement need their own typed owners.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys import terminal
from ios.adapters.emote_observer import EmoteObservationPending
from ios.adapters.emote_operation import clock,operation
from ios.adapters.emote_rooted_archive import capture
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
from ios.adapters.emote_rooted_responsibility import IOSEmoteRootedResponsibility
from ios.adapters.emote_terminal_window import IOSEmoteTerminalWindow
from ios.adapters.peer_admission import validate as admitted
from ios.adapters.emote_terminal_journal import IOSEmoteTerminalJournal


class IOSEmoteTerminal:
    @staticmethod
    def existing_actor(primary):
        """Reopen the real Actor root without preparing or querying an SDK."""
        from ios.adapters.emote_configuration import settings
        # Acquire Actor -> Primary outside an existing Primary lease. A newly
        # constructed same-path lock must never reverse the worker's order.
        need(primary.lock._owner is None)
        path=primary.runtime.state_path(primary.actor_selector).with_name('ios-emote-actor-feature.json')
        actor_lock=ScriptSourceLock(path.with_name('script-feature-sources.lock'))
        with actor_lock.held(),primary.lock.held():
            value=PrivateFeatureState(path).read()
            exact(value,{'iosEmoteFeatureVersion','runId','role','artifactRoot','fixtureUrl','imagePolicy','payload'})
            need(type(value['iosEmoteFeatureVersion']) is int and value['iosEmoteFeatureVersion']==2
                and value['runId']==primary.run and value['role']=='actor' and value['fixtureUrl']==primary.phase.fixture_url)
            selected=settings(dict(artifactRoot=value['artifactRoot'],imagePolicy=value['imagePolicy'],primaryTarget=primary.selector),
                role='actor',target=primary.actor_selector)
            need(selected['artifactRoot']!=str(primary.root))
            actor=IOSEmoteRootedFeature(primary.runtime,primary.actor_selector,primary.client,primary.run,'actor',
                selected['artifactRoot'],selected['imagePolicy'],primary_selector=primary.selector,monotonic=primary.monotonic,
                epoch_ms=primary.epoch_ms,sleep=primary.sleep)
            actor.lock,actor.primary_lock=actor_lock,primary.lock
            actor.load();need(same(actor.previous,value));return actor

    def __init__(self,primary,actor=None):
        need(type(primary) is IOSEmoteRootedFeature and primary.role=='primary')
        if actor is None:actor=self.existing_actor(primary)
        need(type(actor) is IOSEmoteRootedFeature and actor.role=='actor' and actor.runtime is primary.runtime
            and actor.run==primary.run and actor.selector==primary.actor_selector and actor.primary_selector==primary.selector
            and actor.primary_lock is primary.lock and primary.primary_lock is primary.lock
            and actor.phase.fixture_url==primary.phase.fixture_url and actor.root!=primary.root)
        self.flow,self.actor,self.runtime=primary,actor,primary.runtime
        self.monotonic,self.deadline,self.last_clock=primary.monotonic,None,None
        self.responsibilities=[]

    def clock(self):return clock(self)

    def guard(self):
        self.clock()
        for original in self.responsibilities:original.guard()
        self.clock();return True

    def local_window(self,flow):
        parts=flow.components();scope,samples,observer=parts['scope'],parts['samples'],parts['observer']
        need(scope.state['phase']=='released' and scope.state['pending'] is None and samples.state['phase']=='ready'
            and observer.state['pending'] is None and parts['sources'].state['pending'] is None)
        owner=flow.retirement_owner(parts);owner.current()
        live=IOSEmoteRootedLive(owner);need(live.state['pending'] is None and live.state['records'])
        snapshot=live.read_frame(live.state['records'][-1])['snapshot']
        need(same(snapshot,capture(owner,flow.state['cleanup'][-1])))
        rendered=owner.rendered_owner;native=rendered.native_owner
        rendered_ref=owner.original(snapshot['reference'])['renderedReference']
        raw=native.original(rendered.original(rendered_ref)['nativeReference'])
        # Match current ordinary owners to their actual cleanup originals.
        # Separately guard recovery/scene/publication responsibility below.
        need(same(scope.snapshot(),raw['scope']) and same(parts['sources'].store.read(),raw['sources'])
            and same(None if parts['peers'] is None else parts['peers'].store.read(),raw['peers'])
            and same(samples.store.read(),raw['sampleOwners']) and observer.state['records']
            and same(observer.original(observer.state['records'][-1]),raw['observation']))
        for name,field in (('files','fileReceipts'),('entities','entities'),('pointers','pointers')):
            need(same(PrivateFeatureState(native.paths[name]).read(),raw[field]))
        for tail in ('marker-files','marker-script'):
            need(PrivateFeatureState(flow.store.path.with_name('ios-emote-'+flow.role+'-'+tail+'.json')).read() is None)
        if flow.role=='primary':
            for key,name in (('cleanup','cleanup-inputs'),('actions','inputs'),('background','background')):
                need(same(PrivateFeatureState(flow.store.path.with_name('ios-emote-'+name+'.json')).read(),raw['inputOwners'][key]))
        self.responsibilities.append(IOSEmoteRootedResponsibility(flow,parts,owner,live))
        return live

    def window(self):
        roles={};self.responsibilities=[]
        for flow in (self.flow,self.actor):
            flow.load();need(flow.state is not None and flow.state['phase']=='cleaned' and flow.state['cleanup'])
            phase=flow.phase.read();retirement=flow.state['retirement']
            need(phase['verb']=='cleanup' and phase['inputs']=={} and flow.phase.previous['active']
                and phase['status']['instance']==flow.state['phaseInstance'] and retirement is not None
                and retirement['kind']==('primary-scene-ordered' if flow.role=='primary' else 'actor-published')
                and retirement['original'] in flow.state['cleanup'])
            roles[flow.role]=self.local_window(flow)
        need(same(admitted(self.flow.state['actorAdmission'],self.flow.state['binding']),self.actor.state['binding']))
        return IOSEmoteTerminalWindow(roles['primary'],roles['actor'])

    @operation(30)
    def invoke(self,call):
        call=terminal.arguments('emotes',call);need(call['runId']==self.flow.run)
        if call['stage']=='finish':
            # Never open an SDK/native component while answering an unfinished
            # process-end retry. Historical proof replay is a separate reader.
            raise EmoteObservationPending('Rooted Emote process and SDK end are not implemented')
        with self.actor.held(30):
            window=self.window();self.guard();journal=IOSEmoteTerminalJournal(window,check=self.guard)
            if call['stage']=='inspect':
                refs=({role:live.state['records'][-1] for role,live in window.roles.items()}
                    if journal.state is None else journal.state['references'])
                result=journal.inspect(refs)
            else:
                publisher=PrivateFeatureState(self.actor.store.path.with_name('phase-publication-emotes-'+self.flow.run+'-actor.json'))
                result=journal.seal(call['description'],call['samples'],publisher_store=publisher)
            terminal.result('emotes',result);self.clock();return result
