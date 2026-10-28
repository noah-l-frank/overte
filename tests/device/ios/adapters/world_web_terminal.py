"""World-owned inspect/seal/process-end composition for original native owners.

Default v16 remains unchanged. No operation here can turn a requested public
window into native facts, purge a Qt cache, or query a stopped native process.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.original_file_reads import scope as original_reads
from ios.adapters.world_web_rooted_inventory import WorldWebRootedInventory,read_current_end
from adapters.script_feature.history import pack,unpack,same
from feature_journeys import terminal
from feature_journeys.retirement_receipts import binding_from_context
from ios.adapters.peer_admission import validate as peer_admitted
from ios.adapters.world_web_api_clock import operation
from ios.adapters.world_web_fence import original as scene_original,phase as retired_phase
from ios.adapters.world_web_final_archive import WorldWebFinalArchive
from ios.adapters.world_web_held_resources import primary as held_primary,public as held_public
from ios.adapters.world_web_retired import quiet
from ios.adapters.world_web_terminal_live import WorldWebTerminalLive
from ios.adapters.world_web_terminal_seal import original as seal_original,project as seal_projection,verify as verify_seal


class WorldWebTerminal:
    @classmethod
    def from_actor(cls,actor):
        """Use the actual actor's lock instances for a passive worker check."""
        from ios.adapters.world_web_feature import IOSWorldWebFeature
        need(type(actor) is IOSWorldWebFeature and actor.role=='actor')
        actor.lock.assert_held();actor.primary_lock.assert_held()
        primary=IOSWorldWebFeature(actor.runtime,actor.primary_selector,actor.client,actor.run,'primary',
            {key:actor.settings[key] for key in ('artifactRoot','imagePolicy','origins')}|dict(actorTarget=actor.selector),
            epoch_ms=actor.epoch_ms,monotonic=actor.monotonic,sleep=actor.sleep)
        primary.lock=primary.primary_lock=actor.primary_lock
        owner=cls(primary);owner.actor=actor;return owner

    def __init__(self,flow):
        from ios.adapters.world_web_feature import IOSWorldWebFeature
        need(type(flow) is IOSWorldWebFeature and flow.role=='primary')
        self.flow,self.monotonic=flow,flow.monotonic
        self.actor=IOSWorldWebFeature(flow.runtime,flow.settings['actorTarget'],flow.client,flow.run,'actor',
            {key:flow.settings[key] for key in ('artifactRoot','imagePolicy','origins')}|dict(primaryTarget=flow.selector),
            epoch_ms=flow.epoch_ms,monotonic=flow.monotonic,sleep=flow.sleep)
        self.actor.primary_lock=flow.lock
        self.store=flow.runtime._world_web_store(flow.selector,'ios-world-web-primary-'+flow.run+'-terminal.json')
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)
        self.frames=None

    @contextmanager
    def held(self):
        failure=None
        with ExitStack() as stack:
            for lock in sorted((self.flow.lock,self.actor.lock),key=lambda value:str(value.path)):stack.enter_context(lock.held())
            try:
                self.flow.load();self.actor.load();need(self.flow.state is not None and self.actor.state is not None)
                need(self.actor.state['binding']==peer_admitted(self.flow.state['actorAdmission'],self.flow.state['binding'])
                    and self.actor.state['primaryBinding']==self.flow.state['binding']
                    and self.actor.state['phaseInstance']==self.flow.state['phaseInstance'])
                self.frames=OriginalFrameStore(self.flow.root,self.flow.state['binding'],self.flow.run,'primary',self.guard,self.intent,
                    namespace='ios-world-web-terminal',schema_prefix='iosWorldWebTerminal',monotonic=self.monotonic)
                self.guard();yield;self.guard()
            except BaseException as original:failure=original
        if failure is not None:raise failure

    def envelope(self,state):
        return dict(iosWorldWebTerminalVersion=1,runId=self.flow.run,payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosWorldWebTerminalVersion','runId','payload'});rows=unpack(value['payload'])
        need(type(value['iosWorldWebTerminalVersion']) is int and value['iosWorldWebTerminalVersion']==1 and len(rows)==1
            and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','description','seal','end','records','pending'})
        need(state['phase'] in ('inspecting','inspected','sealing','sealed','ending','complete') and type(state['records']) is list and len(state['records'])<=3)
        if state['description'] is not None:terminal.description(state['description'],area='world-web',run=self.flow.run)
        if state['seal'] is not None:terminal.sealed(state['seal'],state['description'])
        if state['end'] is not None:terminal.ended(state['end'],state['seal'])
        need(state['phase']!='complete' or state['end'] is not None)
        return deepcopy(state)

    def guard(self):
        self.flow.lock.assert_held();self.actor.lock.assert_held();need(same(self.store.read(),self.previous))
        for flow in (self.flow,self.actor):need(same(flow.store.read(),flow.previous))

    def save(self):
        self.guard();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def intent(self,kind,value):
        need(kind=='original' and self.state is not None and value['index']==len(self.state['records'])+1)
        self.state['pending']=deepcopy(value);self.save()

    def write(self,value):
        self.guard();need(self.state['pending'] is None and len(self.state['records'])<3)
        reference=self.frames.write(len(self.state['records'])+1,value)
        self.state['records'].append(reference);self.state['pending']=None;self.save();return deepcopy(reference)

    def commit_seal(self,samples,measured,seal,roles):
        """Resolve proof-only interrupted writes without another product input."""
        self.guard();need(self.state['pending'] is None and self.state['phase'] in ('inspected','sealing','sealed')
            and len(self.state['records']) in (1,2))
        if self.state['phase']=='inspected':need(len(self.state['records'])==1 and self.state['seal'] is None)
        elif self.state['phase']=='sealing':need(self.state['seal'] is None)
        else:need(len(self.state['records'])==2 and same(seal,self.state['seal']))
        if len(self.state['records'])==2:
            retained=self.private(2);need(same(retained['samples'],samples) and same(retained['seal'],seal))
            verify_seal(retained,measured,roles)
        else:
            if self.state['phase']=='inspected':self.state['phase']='sealing';self.save()
            self.write(seal_projection(samples,measured,seal))
        if self.state['phase']!='sealed':self.state.update(phase='sealed',seal=deepcopy(seal));self.save()
        return dict(stage='seal',seal=deepcopy(seal))

    def commit_end(self,end):
        """Commit or reopen the same end carrier after a lost durable return."""
        self.guard();need(self.state['pending'] is None and self.state['phase'] in ('ending','complete')
            and len(self.state['records']) in (2,3))
        terminal.ended(end,self.state['seal'])
        if len(self.state['records'])==3:need(same(self.private(3)['end'],end))
        else:
            need(self.state['phase']=='ending' and self.state['end'] is None)
            self.write(dict(iosWorldWebTerminalEndOriginalVersion=1,end=deepcopy(end)))
        if self.state['phase']=='complete':need(same(self.state['end'],end))
        else:self.state.update(phase='complete',end=deepcopy(end));self.save()
        return dict(stage='finish',end=deepcopy(end))

    def recover(self):
        self.guard()
        if self.state is None or self.state['pending'] is None:return
        original=self.state['pending'];self.frames.original(original)
        # A planned-only original has no observed file birth. Never recreate it
        # or guess a file identity after uncertain delivery.
        need(original['phase'] in ('opened','saved'));self.frames.read(original)
        self.state['records'].append(self.frames.compact(dict(original,phase='saved')));self.state['pending']=None;self.save()

    def private(self,index):
        need(type(index) is int and self.state is not None and 1<=index<=len(self.state['records']))
        value=self.frames.read(self.frames.expand(self.state['records'][index-1]))
        if index==2:return seal_original(value)
        key,fields={
            1:('iosWorldWebTerminalRolesVersion',{'roles'}),
            3:('iosWorldWebTerminalEndOriginalVersion',{'end'}),
        }[index]
        exact(value,{key}|fields);need(type(value[key]) is int and value[key]==1)
        return value

    def roles(self,previous=None,*,historical=False):
        from ios.adapters.world_web_archived import rebuild
        roles={};parts={}
        for flow in (self.flow,self.actor):
            if historical:
                owner=rebuild(flow);component=dict(retirement=owner,source=owner.source,peer=None if flow.role=='primary' else owner.peer,
                    lease=owner.lease if flow.role=='primary' else owner.observer.lease)
            else:component=flow.parts();owner=component['retirement']
            need(owner is not None and owner.state['phase']=='retired')
            saved=None if previous is None else previous[flow.role]
            original=scene_original(owner) if saved is None else saved['original'];measured=owner.validate_original(original)
            feature=deepcopy(flow.state if saved is None else saved['feature'])
            need(all(same(feature[key],flow.state[key]) for key in ('binding','primaryBinding','phaseInstance','initialTicket','actorAdmission','baseline','lease','beforeImage'))
                and feature['phase']==('paired' if flow.role=='primary' else 'cleaned') and feature['retirement'] is not None)
            archive=WorldWebFinalArchive(flow.runtime._world_web_store(flow.selector,'ios-world-web-'+flow.role+'-'+flow.run+'-final.json'),
                flow.root,feature['binding'],flow.run,flow.role,flow.lock)
            archive.paired(feature,feature['retirement'],owner.validate_original,measured)
            state=owner.decode(original['owner']);holders=[]
            if flow.role=='primary':
                from ios.adapters.world_web_setup_retirement import WorldWebSetupRetirement
                if type(owner) is WorldWebSetupRetirement:holders=deepcopy(owner.qualification(state)['held'])
                else:holders=held_primary(owner.lease,owner.frame(state['quiet'][-1])['after'])
            row=dict(feature=feature,original=deepcopy(original),measured=measured,held=holders)
            if saved is not None:need(same(row,saved))
            roles[flow.role]=row;parts[flow.role]=component
        need(roles['primary']['measured']['ticket']==roles['actor']['measured']['ticket'])
        self.retained_inputs(parts,historical=historical)
        return roles,parts

    def retained_inputs(self,parts,*,historical=False):
        """Close the current role decode over real GPU and publication files.

        Frozen sample/GPU snapshots and Scene3 do not read these separate
        runtime/publication heads. Only existing typed decoders can admit
        their actual reads before the unchanged rooted orphan census.
        """
        from ios.adapters.world_web_retirement import WorldWebRetirement
        from ios.adapters.world_web_setup_retirement import WorldWebSetupRetirement
        primary=parts['primary']['retirement'];actor=parts['actor']['retirement']
        need(type(primary) in (WorldWebRetirement,WorldWebSetupRetirement) and primary.role=='primary'
            and primary.state['phase']=='retired' and primary.state['records'])
        with actor.observer.validation_round():
            if type(primary) is WorldWebRetirement:
                rows=primary.gpu_rows(primary.frame(primary.state['records'][-1]))
                expected={row['requestId']:row['owner'] for row in rows};need(len(expected)==len(rows))
            else:
                row=primary.state['records'][-1];values=primary.values(row)
                expected={request:values['gpu-owner:'+request] for request in row['images']}
            need(set(expected)==set(primary.state['images']))
            for request,original in expected.items():primary.sample(request).current_owner_original(original)
            # Empty selection still invokes the original full archive/load
            # decoder and exact record inventory. It publishes nothing and
            # does not rename, adopt or guess any carrier into membership.
            self.actor_publications(parts['actor'],[],historical=historical)

    def descriptor(self,roles):
        value=dict(featureTerminalVersion=1,profile=terminal.PROFILE,area='world-web',runId=self.flow.run,
            ticket=roles['primary']['measured']['ticket'],roles={role:dict(binding=binding_from_context(row['feature']['binding']),
                heldResources=held_public(row['held']),originalSha256=digest(row)) for role,row in roles.items()})
        terminal.description(value);return value

    def actor_publications(self,parts,samples,*,historical=False):
        from adapters.phase_witness_publisher import PhaseWitnessPublisher
        from ios.adapters.world_web_retirement import WorldWebRetirement
        owner=parts['retirement'];observer=owner.observer
        store=PrivateFeatureState(self.actor.store.path.with_name('phase-publication-world-web-'+self.flow.run+'-actor.json'))
        self.actor.lock.assert_held();observer.round_guard()
        if not historical:need(observer.guard() is not False)
        def inventory():return set(store.path.parent.glob(store.path.stem+'-*.json'))
        try:signature=WorldWebRetirement.record_signature(store.path)
        except FileNotFoundError:
            # Inspect may have no earlier witness publication at all. An
            # absent head grants no receipt: record-only responsibility and
            # a requested live window still fail closed without a decoder.
            need(store.read() is None and not samples and not inventory());return []
        original=store.read();need(original is not None)
        present=inventory();need(len(present)<=512)
        pins={path:WorldWebRetirement.record_signature(path) for path in present};pins[store.path]=signature
        # Sealing reads actual committed originals. A newly reconstructed actor
        # has no current PhaseFixtureReader acquisition, and this readonly path
        # must neither invent one nor query/send through a live publisher.
        state=PhaseWitnessPublisher.archive(original,store=store,binding=self.actor.state['binding'],run=self.flow.run,area='world-web',
            fixture_url=self.actor.client.url,phase_instance=self.actor.state['phaseInstance'],validate_original=observer.validate_original)
        publisher=object.__new__(PhaseWitnessPublisher);publisher.store=store;publisher.binding=deepcopy(self.actor.state['binding']);publisher.run=self.flow.run
        publisher.area='world-web';publisher.url=self.actor.client.url;publisher.instance=self.actor.state['phaseInstance'];publisher.validate_original=observer.validate_original
        need(state['pending'] is None)
        expected={publisher.record_store(reference['ordinal']).path for reference in state['records']};need(present==expected and inventory()==expected)
        try:
            originals=[]
            for reference in state['records']:
                path=publisher.record_store(reference['ordinal']).path;need(WorldWebRetirement.record_signature(path)==pins[path])
                originals.append(publisher.load(reference));need(WorldWebRetirement.record_signature(path)==pins[path])
            selected=[]
            for pair in samples:
                matches=[row for row in originals if row['mode']=='published' and same(row['entry'],pair['actor'])]
                need(len(matches)==1);row=matches[0];entry=observer.entries()[row['intent']['original']['reference']['index']-1]
                primary=observer.source.frame(entry['source']);peer=observer.peer.frame(entry['peer']);owner.native_frames(primary,peer)
                selected.append(dict(publication=deepcopy(row),primary=primary,peer=peer))
            observer.round_guard()
            if not historical:need(observer.guard() is not False)
            return deepcopy(selected)
        finally:
            need(inventory()==expected and same(store.read(),original))
            for path,record_signature in pins.items():need(WorldWebRetirement.record_signature(path)==record_signature)

    def live(self,samples,roles,parts,*,historical=False):
        # This is immutable replay only. End every original round before the
        # caller writes its seal or starts either once-only process Stop.
        # Existing Source/Lease/Observer rounds otherwise close after every
        # nested original callback and re-decode the entire same prefix.
        with ExitStack() as stack:
            from ios.adapters.world_web_scope_archive import original_round
            stack.enter_context(original_round())
            seen=set()
            for source in (parts['primary']['source'],parts['actor']['source'],parts['actor']['peer']):
                need(source is not None)
                if id(source) not in seen:
                    seen.add(id(source));stack.enter_context(source.validation_round())
            primary=parts['primary']['retirement'];actor=parts['actor']['retirement']
            if primary.lease is not None:stack.enter_context(primary.lease.validation_round())
            stack.enter_context(actor.observer.validation_round())
            return self._live(samples,roles,parts,historical=historical)

    def _live(self,samples,roles,parts,*,historical=False):
        terminal.window(samples,self.state['description']);primary=parts['primary']['retirement'];actor=parts['actor']['retirement']
        journal=WorldWebTerminalLive(primary);selected=journal.selected_many([pair['primary'] for pair in samples])
        actors=self.actor_publications(parts['actor'],samples,historical=historical)
        for row in selected:need(same(held_public(row['held']),self.state['description']['roles']['primary']['heldResources']))
        a=primary.decode(roles['primary']['original']['owner']);first=primary.source.frame(primary.frame(a['quiet'][-1])['after'])
        state=primary.decode(selected[-1]['original']['owner']);last=primary.source.frame(primary.frame(state['quiet'][-1])['before']);quiet(first,last)
        old=actor.decode(roles['actor']['original']['owner']);entry=actor.entry(old['quiet'][-1]);quiet(actor.peer.frame(entry['peer']),actors[-1]['peer'])
        for index,row in enumerate(selected):
            if index:need(actors[index-1]['peer']['clockJoin']['hostAfterMonotonic']<=row['acquisition']['hostBeforeMonotonic'])
        return dict(primary=selected,actor=actors)

    @operation
    def invoke(self,call):
        call=terminal.arguments('world-web',call);need(call['runId']==self.flow.run)
        if call['stage']=='finish':return self.finish(call['seal'])
        with self.held(),original_reads(fresh=True) as reads:
            self.recover()
            if call['stage']=='inspect':
                if self.state is None:
                    roles,_parts=self.roles();descriptor=self.descriptor(roles)
                    self.state=dict(phase='inspecting',description=descriptor,seal=None,end=None,records=[],pending=None);self.save()
                if self.state['phase']=='inspecting':
                    need(self.state['pending'] is None and len(self.state['records']) in (0,1))
                    if not self.state['records']:
                        roles,_parts=self.roles();need(same(self.descriptor(roles),self.state['description']))
                        self.write(dict(iosWorldWebTerminalRolesVersion=1,roles=roles))
                    roles,_parts=self.roles(self.private(1)['roles'])
                    need(same(self.descriptor(roles),self.state['description']))
                    self.state['phase']='inspected';self.save()
                need(self.state['phase'] in ('inspected','sealed'));roles,_parts=self.roles(self.private(1)['roles'])
                need(same(self.descriptor(roles),self.state['description']))
                WorldWebRootedInventory(self,reads).guard()
                return dict(stage='inspect',description=deepcopy(self.state['description']))
            need(self.state is not None and same(call['description'],self.state['description']))
            roles,parts=self.roles(self.private(1)['roles']);need(same(self.descriptor(roles),self.state['description']))
            measured=self.live(call['samples'],roles,parts)
            seal=dict(featureTerminalSealVersion=1,description=deepcopy(self.state['description']),windowSha256=digest(call['samples']),
                liveOriginalSha256=digest(dict(roles=roles,window=measured)))
            terminal.sealed(seal,self.state['description'],call['samples'])
            census=WorldWebRootedInventory(self,reads)
            result=self.commit_seal(call['samples'],measured,seal,roles);census.guard();return result

    def finish(self,seal):
        with original_reads(fresh=True) as reads:return self._finish(seal,reads)

    def _finish(self,seal,reads):
        with self.held():
            self.recover();need(self.state is not None and self.state['phase'] in ('sealed','ending','complete') and same(seal,self.state['seal']))
            retained=self.private(2);need(same(retained['seal'],seal));terminal.sealed(seal,self.state['description'],retained['samples'])
            # The sealed private graph is replayed before any once-only Stop.
            roles,parts=self.roles(self.private(1)['roles'],historical=True);need(same(self.descriptor(roles),seal['description']))
            verify_seal(retained,self.live(retained['samples'],roles,parts,historical=True),roles)
            read_current_end(self,parts)
            WorldWebRootedInventory(self,reads).guard()
            if self.state['phase']=='complete' or len(self.state['records'])==3:
                from ios.adapters.world_web_terminal_end import role_end
                end=dict(featureTerminalEndVersion=1,seal=deepcopy(seal),roles={flow.role:role_end(flow,seal['description']['roles'][flow.role]['originalSha256']) for flow in (self.flow,self.actor)})
                census=WorldWebRootedInventory(self,reads)
                result=self.commit_end(end);census.guard();return result
            current=retired_phase(self.flow.phase.status(),self.flow)
            self.state['phase']='ending';self.save()
        # Actor first: its final primary-SDK fence runs while the primary lives.
        # Each Stop keeps both exact role locks and a fresh closed paired
        # census through its ordinary final acquisition and transport send.
        from ios.adapters.world_web_session_end import WorldWebSessionEnd
        for flow in (self.actor,self.flow):
            with self.held(),original_reads(fresh=True) as role_reads:
                roles,parts=self.roles(self.private(1)['roles'],historical=True)
                verify_seal(retained,self.live(retained['samples'],roles,parts,historical=True),roles)
                read_current_end(self,parts)
                stop_census=WorldWebRootedInventory(self,role_reads)
                need(flow.finalize(current,stop_census=stop_census)==dict(performed=True))
                WorldWebSessionEnd(flow).finish()
        with self.held():
            roles,parts=self.roles(self.private(1)['roles'],historical=True)
            read_current_end(self,parts)
            from ios.adapters.world_web_terminal_end import role_end
            end=dict(featureTerminalEndVersion=1,seal=deepcopy(seal),roles={flow.role:role_end(flow,seal['description']['roles'][flow.role]['originalSha256']) for flow in (self.flow,self.actor)})
            census=WorldWebRootedInventory(self,reads)
            result=self.commit_end(end);census.guard();return result
