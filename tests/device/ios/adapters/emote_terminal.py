"""Internal rooted Emote live seal and separately owned paired end operations.

Whole-area admission remains separate from these internal durable owners.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import scope as read_scope,record as original_read
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
from ios.adapters.emote_rooted_inventory import IOSEmoteRootedInventory
from ios.adapters.emote_rooted_end_lock import held_existing


class IOSEmoteTerminal:
    Flow=IOSEmoteRootedFeature
    Live=IOSEmoteRootedLive
    Responsibility=IOSEmoteRootedResponsibility
    Window=IOSEmoteTerminalWindow
    Journal=IOSEmoteTerminalJournal
    Inventory=IOSEmoteRootedInventory
    snapshot_capture=staticmethod(capture)

    def sample_envelope(self,raw):return raw['sampleOwners']

    @staticmethod
    def existing_actor(primary):
        """Reopen the real Actor root without preparing or querying an SDK."""
        from ios.adapters.emote_configuration import settings
        # Acquire Actor -> Primary outside an existing Primary lease. A newly
        # constructed same-path lock must never reverse the worker's order.
        need(primary.lock._owner is None)
        path=primary.runtime.state_path(primary.actor_selector).with_name('ios-emote-actor-feature.json')
        actor_lock=ScriptSourceLock(path.with_name('script-feature-sources.lock'))
        with held_existing(actor_lock),held_existing(primary.lock):
            value=PrivateFeatureState(path).read();actual=deepcopy(value)
            if value is None:
                from ios.adapters.emote_rooted_finish import existing_archive
                archive,ownership=existing_archive(primary,actor_lock)
                need(archive is not None);ownership.read()
                value=archive.copies().get(str(path));need(type(value) is dict)
            need(type(value) is dict and type(value.get('iosEmoteFeatureVersion')) is int and value['iosEmoteFeatureVersion'] in (2,3))
            version=value['iosEmoteFeatureVersion']
            exact(value,{'iosEmoteFeatureVersion','runId','role','artifactRoot','fixtureUrl','imagePolicy','payload'}|({'targetPair'} if version==3 else set()))
            need(value['runId']==primary.run and value['role']=='actor' and value['fixtureUrl']==primary.phase.fixture_url)
            pair=getattr(primary,'configured_pair',None)
            need((version==3) is (pair is not None))
            if pair is not None:
                from ios.adapters.emote_target_pair import selected as pair_configuration
                need(same(pair_configuration(value['targetPair']),pair))
            selected=settings(dict(artifactRoot=value['artifactRoot'],imagePolicy=value['imagePolicy'],primaryTarget=primary.selector),
                role='actor',target=primary.actor_selector)
            need(selected['artifactRoot']!=str(primary.root))
            actor=IOSEmoteRootedFeature(primary.runtime,primary.actor_selector,primary.client,primary.run,'actor',
                selected['artifactRoot'],selected['imagePolicy'],primary_selector=primary.selector,monotonic=primary.monotonic,
                epoch_ms=primary.epoch_ms,sleep=primary.sleep,target_pair=pair)
            actor.lock,actor.primary_lock=actor_lock,primary.lock
            actor.load();need(same(actor.previous,actual));return actor

    def __init__(self,primary,actor=None):
        need(type(primary) is self.Flow and primary.role=='primary')
        if actor is None:actor=self.existing_actor(primary)
        need(type(actor) is self.Flow and actor.role=='actor' and actor.runtime is primary.runtime
            and actor.run==primary.run and actor.selector==primary.actor_selector and actor.primary_selector==primary.selector
            and actor.primary_lock is primary.lock and primary.primary_lock is primary.lock
            and actor.phase.fixture_url==primary.phase.fixture_url and actor.root!=primary.root)
        need(same(getattr(primary,'configured_pair',None),getattr(actor,'configured_pair',None)))
        self.flow,self.actor,self.runtime=primary,actor,primary.runtime
        self.monotonic,self.deadline,self.last_clock=primary.monotonic,None,None
        self.responsibilities=[]
        self.inventory=None

    def clock(self):return clock(self)

    def guard(self):
        self.clock()
        for original in self.responsibilities:original.guard()
        if self.inventory is not None:self.inventory.guard()
        self.clock();return True

    def local_window(self,flow):
        parts=flow.components();scope,samples,observer=parts['scope'],parts['samples'],parts['observer']
        need(scope.state['phase']=='released' and scope.state['pending'] is None and samples.state['phase']=='ready'
            and observer.state['pending'] is None and parts['sources'].state['pending'] is None)
        owner=flow.retirement_owner(parts);owner.current()
        live=self.Live(owner);need(live.state['pending'] is None and live.state['records'])
        snapshot=live.read_frame(live.state['records'][-1])['snapshot']
        need(same(snapshot,self.snapshot_capture(owner,flow.state['cleanup'][-1])))
        rendered=owner.rendered_owner;native=rendered.native_owner
        rendered_ref=owner.original(snapshot['reference'])['renderedReference']
        raw=native.original(rendered.original(rendered_ref)['nativeReference'])
        # Match current ordinary owners to their actual cleanup originals.
        # Separately guard recovery/scene/publication responsibility below.
        need(same(scope.snapshot(),raw['scope']) and same(parts['sources'].store.read(),raw['sources'])
            and same(None if parts['peers'] is None else parts['peers'].store.read(),raw['peers'])
            and same(samples.store.read(),self.sample_envelope(raw)) and observer.state['records']
            and same(observer.original(observer.state['records'][-1]),raw['observation']))
        for name,field in (('files','fileReceipts'),('entities','entities'),('pointers','pointers')):
            need(same(PrivateFeatureState(native.paths[name]).read(),raw[field]))
        for tail in ('marker-files','marker-script'):
            need(PrivateFeatureState(flow.store.path.with_name('ios-emote-'+flow.role+'-'+tail+'.json')).read() is None)
        if flow.role=='primary':
            for key,name in (('cleanup','cleanup-inputs'),('actions','inputs'),('background','background')):
                need(same(PrivateFeatureState(flow.store.path.with_name('ios-emote-'+name+'.json')).read(),raw['inputOwners'][key]))
        responsibility=self.Responsibility(flow,parts,owner,live)
        self.responsibilities.append(responsibility)
        for path in responsibility.signatures:original_read(path)
        return live

    def window(self,*,retired=False):
        roles={};self.responsibilities=[]
        for flow in (self.flow,self.actor):
            flow.load();need(flow.state is not None and flow.state['phase']=='cleaned' and flow.state['cleanup'])
            if retired:
                status=flow.phase.status();need(status['active'] is False and status['activations'])
                stimulus=status['activations'][-1]['stimulus'];phase=dict(stimulus,status=status)
            else:phase=flow.phase.read()
            retirement=flow.state['retirement']
            need(phase['verb']=='cleanup' and phase['inputs']=={} and flow.phase.previous['active'] is (not retired)
                and phase['status']['instance']==flow.state['phaseInstance'] and retirement is not None
                and retirement['kind']==('primary-scene-ordered' if flow.role=='primary' else 'actor-published')
                and retirement['original'] in flow.state['cleanup'])
            roles[flow.role]=self.local_window(flow)
        need(same(admitted(self.flow.state['actorAdmission'],self.flow.state['binding']),self.actor.state['binding']))
        return self.Window(roles['primary'],roles['actor'])

    @operation(30)
    def invoke(self,call):
        call=terminal.arguments('emotes',call);need(call['runId']==self.flow.run)
        self.inventory=None
        if call['stage']=='finish':
            from ios.adapters.emote_rooted_finish import IOSEmoteRootedFinish
            failure=None
            with held_existing(self.actor.lock),held_existing(self.flow.lock),self.actor.held(30):
                # Shared ordinary lock contexts normalize body errors. Keep
                # the original pending/uncertain result inside every lease
                # until all inode, owner and deadline exit checks succeed.
                try:result=IOSEmoteRootedFinish(self,call['seal']).invoke()
                except BaseException as error:failure=(error,error.__traceback__)
            if failure is not None:
                self.clock();raise failure[0].with_traceback(failure[1])
            terminal.result('emotes',result);self.clock();return result
        with self.actor.held(30):
            with read_scope(fresh=True) as reads:
                window=self.window();self.guard();journal=self.Journal(window,check=self.guard)
            self.inventory=self.Inventory(journal,reads);self.guard()
            if call['stage']=='inspect':
                refs=({role:live.state['records'][-1] for role,live in window.roles.items()}
                    if journal.state is None else journal.state['references'])
                result=journal.inspect(refs)
            else:
                publisher=PrivateFeatureState(self.actor.store.path.with_name('phase-publication-emotes-'+self.flow.run+'-actor.json'))
                result=journal.seal(call['description'],call['samples'],publisher_store=publisher)
            terminal.result('emotes',result);self.clock();return result
