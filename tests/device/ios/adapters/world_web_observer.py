"""Whole browser publications rederived from independent immutable originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager,ExitStack
from adapters.native_clock_join import digest
from adapters.original_file_reads import active as recording_original_reads
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import result
from ios.adapters.world_web_sources import WorldWebSources
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_sample import WorldWebSample
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.adapters.world_web_history import derive as browser_state
from ios.adapters.emote_marker_measurements import body_preserved,view_preserved
from ios.adapters.world_web_api_clock import check
from ios.adapters.world_web_evidence import required as required_evidence
from ios.adapters.emote_original_lease import EmoteOriginalLease


class WorldWebObserver:
    def __init__(self,store,source,origins,guard,*,role='primary',peer=None,lease=None,sample_resolver=None,setup_scope=None):
        need(isinstance(store,PrivateFeatureState) and isinstance(source,WorldWebSources) and role in ('primary','actor')
            and callable(guard) and (lease is None or isinstance(lease,WorldWebLease)) and (sample_resolver is None or callable(sample_resolver)))
        if role=='actor':need(isinstance(peer,WorldWebSources) and peer.role=='actor' and source.role=='actor-primary'
            and source.binding['sessionId']!=peer.binding['sessionId'] and source.binding['targetFingerprint']!=peer.binding['targetFingerprint']
            and all(source.binding[key]==peer.binding[key] for key in ('sourceRevision','artifactSha256')))
        else:need(peer is None and source.role=='primary')
        self.store,self.source,self.origins,self.guard,self.role,self.peer,self.lease,self.sample_resolver=store,source,deepcopy(origins),guard,role,peer,lease,sample_resolver
        need(setup_scope is None or type(setup_scope) is IOSWorldWebScope and setup_scope.lock is source.lock
            and setup_scope.binding==source.binding and setup_scope.run==source.run)
        self.setup_scope=setup_scope
        self.run,self.binding,self.lock=source.run,source.binding if peer is None else peer.binding,source.lock if peer is None else peer.lock
        self.previous=store.read();self.version=2 if self.previous is None else self.previous.get('iosWorldWebObserverVersion')
        need(type(self.version) is int and self.version in (1,2))
        self.state=dict(records=[],pending=None,interrupted=[]);self._round=None
        if self.previous is not None:self.state=self.decode(self.previous)
    def envelope(self,state):return dict(iosWorldWebObserverVersion=self.version,runId=self.run,role=self.role,binding=self.binding,primaryBinding=self.source.binding,
        origins=self.origins,payload=pack([state]))
    def record_store(self,index):return PrivateFeatureState(self.store.path.with_name('ios-world-web-'+self.role+'-observation-'+str(index)+'.json'))
    def entries(self):
        entries=[]
        for reference in self.state['records']:
            carrier=self.record_store(reference['index']).read();need(carrier is not None and digest(carrier)==reference['sha256'])
            exact(carrier,{'iosWorldWebObservationRecordVersion','runId','role','binding','payload'});need(type(carrier['iosWorldWebObservationRecordVersion']) is int
                and carrier['iosWorldWebObservationRecordVersion']==1 and carrier['runId']==self.run and carrier['role']==self.role and same(carrier['binding'],self.binding))
            rows=unpack(carrier['payload']);need(len(rows)==1 and rows[0]['sequence']==reference['index']);entries.append(rows[0])
        return entries
    @contextmanager
    def validation_round(self,*,publication=None):
        if publication is not None:
            from ios.adapters.world_web_publication_round import WorldWebPublicationRound
            need(type(publication) is WorldWebPublicationRound and publication.observer is self and self.role=='actor' and self._round is None)
        if self._round is not None:
            self.round_guard();yield;self.round_guard();return
        roots={self.source.store.path.parent}
        if self.peer is not None:roots.add(self.peer.store.path.parent)
        if self.lease is not None:roots.add(self.lease.scope.root)
        if self.setup_scope is not None:roots.add(self.setup_scope.root)
        leases=[EmoteOriginalLease(root,[] if publication is None else [path for path in publication.mutable if path.parent==root]) for root in roots]
        with ExitStack() as stack:
            stack.enter_context(self.source.validation_round())
            if self.peer is not None:stack.enter_context(self.peer.validation_round())
            if self.lease is not None:stack.enter_context(self.lease.validation_round())
            header=self.round_header();self._round=dict(header=header,leases=leases,derived={},scopes={})
            if publication is not None:publication.attach(leases)
            try:self.round_guard();yield;self.round_guard()
            finally:self._round=None
    def round_header(self):
        setup=None
        if self.setup_scope is not None:
            scope=self.setup_scope
            need(type(scope) is IOSWorldWebScope and scope.lock is self.source.lock and scope.run==self.run
                and scope.binding==self.source.binding and same(scope.store.read(),scope.previous))
            if scope.previous is not None:need(same(scope.envelope(scope.state),scope.previous))
            else:need(scope.state['phase']=='new')
            setup=(id(scope),str(scope.root),str(scope.store.path),deepcopy(scope.binding),scope.run,scope.role,deepcopy(scope.previous))
        return (deepcopy(self.binding),deepcopy(self.source.binding),self.run,self.role,deepcopy(self.origins),self.source.pid,
            self.source.run,self.source.role,self.source.phase.fixture_url,id(self.source),id(self.peer),id(self.lease),id(self.sample_resolver),setup)
    def round_guard(self):
        need(self._round is not None and same(self.round_header(),self._round['header']) and same(self.store.read(),self.previous))
        self.source.guard_originals()
        if self.peer is not None:self.peer.guard_originals()
        if self.lease is not None:self.lease.header()
        for lease in self._round['leases']:lease.guard()
    def derive(self,entry):
        with self.validation_round():
            original=deepcopy(entry);self.round_guard()
            lease=None if self.lease is None else self.lease.packet()
            key=digest([original,self.state,lease,self._round['header']])
            # A fresh file-read membership scope must actually replay its
            # readers. Metadata continuity alone cannot add a file to a seal.
            cache=self._round['derived'];memo=not recording_original_reads()
            if memo and key in cache:self.round_guard();return deepcopy(cache[key])
            value=self._derive(original);self.round_guard()
            if memo and len(cache)<256:cache[key]=deepcopy(value)
            return deepcopy(value)
    def _derive(self,entry):
        exact(entry,{'sequence','ticket','source','peer','lease','scope','sample'});need(integer(entry['sequence'],1,256))
        frame=self.source.frame(entry['source']);need(entry['ticket']==frame['ticket'] and frame['phaseBefore']['active'] and frame['phaseAfter']['active'])
        if entry['sequence']>1:
            previous=self.entries()[entry['sequence']-2];owner=self.source if self.peer is None else self.peer
            floor=owner.frame(previous['source' if self.peer is None else 'peer'])['clockJoin'];start=frame['clockJoin']
            need(start['hostBeforeEpochMs']>=floor['hostAfterEpochMs'] and start['hostBeforeMonotonic']>=floor['hostAfterMonotonic'])
        scope_state=None
        if entry['scope'] is not None:
            scope=self.lease.scope if self.lease is not None else self.setup_scope
            need(scope is not None)
            key=digest([entry['scope'],self.source.binding,self.run,str(scope.root)])
            cache=self._round['scopes'];memo=not recording_original_reads()
            if memo and key in cache:scope_state=deepcopy(cache[key])
            else:
                archived=IOSWorldWebScope.archive(entry['scope'],root=scope.root,binding=self.source.binding,run=self.run,role='primary',lock=self.source.lock)
                scope_state=deepcopy(archived.state)
                if memo and len(cache)<256:cache[key]=deepcopy(scope_state)
            need(scope_state is not None)
            if entry['lease'] is not None:need(same(scope_state['fileOwnership'],entry['lease']['files']))
            else:need(self.version==2 and self.setup_scope is scope and scope_state['phase']=='released'
                and same(entry['scope'],scope.previous) and frame['phaseBefore']['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        else:need(entry['lease'] is None)
        ownership=directory=entity=None
        if entry['lease'] is not None:
            need(self.lease is not None and same(entry['lease'],self.lease.packet()))
            owned=entry['lease'];ownership,directory,entity=owned['files'],owned['directory'],owned['returned']['returned']['entityId']
        elif entry['scope'] is not None:
            # A real partially executed Script may have opened and closed a
            # WK document before rendered admission failed. Its actual return,
            # VM terminal, callback/weak and native restoration originals are
            # separate from a full rendered lease and cannot invent one.
            from ios.adapters.world_web_setup_measurements import original as setup_original
            first=self.entries()[0] if self.state['records'] else entry
            proof=setup_original(self.setup_scope,self.source,first['source'],entry['source'])
            if proof['returned'] is not None:
                ownership,directory,entity=scope_state['fileOwnership'],scope_state['directory'],proof['returned']['returned']['entityId']
        history=self.source.derive_browser(entry['source'],ownership=ownership,directory=directory,entity=entity,origins=self.origins)
        if self.lease is not None and entry['lease'] is not None:self.lease.current(frame,live=history['public']['open'])
        clock=frame['clockJoin'];native=clock['nativeAfter'];start,end=clock['hostBeforeEpochMs'],clock['hostAfterEpochMs'];mono_start,mono_end=clock['hostBeforeMonotonic'],clock['hostAfterMonotonic']
        if self.role=='actor':
            peer=self.peer.frame(entry['peer']);need(peer['ticket']==frame['ticket'] and peer['phaseBefore']['instance']==frame['phaseBefore']['instance']
                and peer['clockJoin']['hostBeforeMonotonic']>=clock['hostAfterMonotonic'])
            actual=frame['originals']['world']['source']['domain'];observed=peer['originals']['world']['source']['domain']
            need(actual['connected'] and observed['connected'] and not actual['serverless'] and not observed['serverless']
                and actual['domainId']==observed['domainId'] and actual['avatarMixerSha256']==observed['avatarMixerSha256'])
            first_entry=self.entries()[0] if self.state['records'] else entry
            baseline=self.peer.frame(first_entry['peer'])
            body_preserved(baseline['originals']['world'],peer['originals']['world']);view_preserved(baseline['originals']['world'],peer['originals']['world'])
            need(baseline['originals']['world']['source']['tree']['entities']==peer['originals']['world']['source']['tree']['entities'])
            end=peer['clockJoin']['hostAfterEpochMs'];mono_end=peer['clockJoin']['hostAfterMonotonic'];native=peer['clockJoin']['nativeAfter']
        else:need(entry['peer'] is None)
        stimulus=frame['phaseBefore']['activations'][-1]['stimulus']
        required=required_evidence(self.run,stimulus['verb'],stimulus['inputs'])
        artifacts=[]
        if entry['sample'] is not None:
            need(self.role=='primary' and self.sample_resolver is not None);sample=self.sample_resolver(entry['sample']['requestId'])
            need(isinstance(sample,WorldWebSample) and sample.state is not None and sample.state['phase']=='qualified'
                and digest(sample.previous)==entry['sample']['sha256'] and same(sample.state['after'],entry['source']))
            need(sample.state['qualificationInputs']['changed']==('changed' in required));sample.decode(sample.previous)
            before=self.source.frame(sample.state['before']);need(before['ticket']==entry['ticket'])
            start=before['clockJoin']['hostBeforeEpochMs'];mono_start=before['clockJoin']['hostBeforeMonotonic']
            # Public freshness uses the original host acquisition boundary.
            # The GPU's distinct native capture epoch remains unchanged in
            # frameOwnership and is joined by the sample's native brackets.
            artifacts.append(dict(kind='image',name=sample.state['frameOwnership']['name'],sequence=entry['sequence'],
                capturedEpochMs=start,ticket=entry['ticket'],source='world-render-target'))
        need(0<=end-start<1500 and 0<=mono_end-mono_start<1.5 and abs(end-start-(mono_end-mono_start)*1000)<=250)
        if self.role=='primary':need(not({'image','changed'}&set(required)) or artifacts)
        resources=[];raw=frame['originals']
        if entry['lease'] is not None:
            marker=entry['lease']['admission']['marker'];manager=entry['lease']['admission']['manager']
            if any(row['id']==marker['id'] for row in raw['world']['source']['tree']['entities']):resources.append('entity:world-web')
            if any(row['instance']==manager['instance'] for row in raw['world']['source']['scriptOriginal']['source']['membership']['managers']):resources.append('script:world-web')
            if scope_state['phase']!='released':resources.append('file:world-web-input')
        if history['public']['open']:resources.append('panel:world-web')
        if raw['uikit']['observation']['nativeUi']['keyboardVisible'] or raw['keys']['source']['down'] or raw['keys']['source']['pendingDispatches']:resources.append('input:world-web-keyboard')
        if raw['pointer']['source']['contacts'] or raw['pointer']['source']['pendingDispatches']:resources.append('input:world-web-pointer')
        public=dict(schemaVersion=1,contractVersion=16,runId=self.run,sequence=entry['sequence'],capturedEpochMs=start,state=history['public'],artifacts=artifacts,
            resources=sorted(resources),lifecycle=deepcopy(native['lifecycle']));result('feature.world-web.observe',public)
        return dict(ticket=entry['ticket'],public=public,acquisition=dict(hostBeforeEpochMs=start,hostAfterEpochMs=end,hostBeforeMonotonic=mono_start,hostAfterMonotonic=mono_end))
    def decode(self,value):
        with self.validation_round():return self._decode(value)
    def _decode(self,value):
        exact(value,{'iosWorldWebObserverVersion','runId','role','binding','primaryBinding','origins','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0];exact(state,{'records','pending','interrupted'})
        need(type(state['records']) is list and len(state['records'])<=256 and type(state['interrupted']) is list and len(state['interrupted'])<=64)
        previous=self.state;self.state=state
        try:
            last_source=last_peer=0
            for index,(reference,entry) in enumerate(zip(state['records'],self.entries()),1):
                exact(reference,{'index','sha256'});need(type(reference['index']) is int and reference['index']==entry['sequence']==index
                    and entry['source']['index']>last_source)
                last_source=entry['source']['index']
                if self.peer is not None:need(entry['peer']['index']>last_peer);last_peer=entry['peer']['index']
                self.derive(entry)
            for partial in state['interrupted']+([] if state['pending'] is None else [state['pending']]):
                exact(partial,{'sequence','ticket','source','peer','lease','scope','sample'});need(integer(partial['sequence'],1,len(state['records'])+1))
                from feature_journeys.contract import identifier
                identifier(partial['ticket'])
                for owner,key in ((self.source,'source'),(self.peer,'peer')):
                    if partial[key] is not None:need(owner is not None);owner.frame(partial[key])
                if partial['scope'] is not None:
                    scope=self.lease.scope if self.lease is not None else self.setup_scope
                    need(scope is not None and (partial['lease'] is not None or self.version==2))
                    archived=IOSWorldWebScope.archive(partial['scope'],root=scope.root,binding=self.source.binding,run=self.run,role='primary',lock=self.source.lock)
                    if partial['lease'] is None:need(archived.state['phase']=='released' and same(partial['scope'],scope.previous))
                if partial['lease'] is not None:need(self.lease is not None and same(partial['lease'],self.lease.packet()))
                if partial['sample'] is not None:
                    ref=partial['sample'];exact(ref,{'requestId','sha256'});need(self.sample_resolver is not None and ref['requestId'].startswith('ios-'));identifier(ref['requestId'][4:])
                    sample=self.sample_resolver(ref['requestId']);need(isinstance(sample,WorldWebSample) and sample.source is self.source)
                    if ref['sha256'] is not None:need(sample.previous is not None and digest(sample.previous)==ref['sha256'])
        finally:self.state=previous
        return deepcopy(state)
    def save(self):
        check();self.lock.assert_held();self.source.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        # These are delivery/read intentions. Replaying every old original
        # graph at each field write consumes the new original's freshness.
        # Reconstruction/publication still perform the full typed decoder.
        old=[] if self.previous is None else unpack(self.previous['payload'])[0]['records'];records=self.state['records']
        need(type(records) is list and len(old)<=len(records)<=min(256,len(old)+1) and same(records[:len(old)],old)
            and type(self.state['interrupted']) is list and len(self.state['interrupted'])<=64)
        if len(records)>len(old):
            ref=records[-1];need(ref['index']==len(records));carrier=self.record_store(ref['index']).read()
            need(carrier is not None and digest(carrier)==ref['sha256'])
        value=self.envelope(self.state);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def capture(self,*,sample=None,policy=None,previous=None,changed=False):
        from ios.adapters import world_web_source
        from adapters.operation_transport_guard import scope as transport_scope
        # Both actual old byte graphs are qualified before the first fresh
        # SDK original. Keep only the existing parent DTO memo/pins alive;
        # a readonly Source round must end before any journal can append.
        with ExitStack() as stack:
            stack.enter_context(world_web_source.validation_round())
            owners=[self.source]+([] if self.peer is None else [self.peer])
            for source in owners:stack.enter_context(source.parts.snapshot.validation_round())
            guards=[source.prewarm_snapshot_history() for source in owners]
            def guard():
                for check_originals in guards:check_originals()
            for source in owners:
                previous_guard=source.guard_originals
                def guarded(*,previous_guard=previous_guard):previous_guard();guard()
                source.guard_originals=guarded
                stack.callback(setattr,source,'guard_originals',previous_guard)
            with transport_scope(guard):
                guard();value=self._capture(sample=sample,policy=policy,previous=previous,changed=changed);guard();return value
    def _capture(self,*,sample=None,policy=None,previous=None,changed=False):
        self.lock.assert_held();self.source.lock.assert_held();need(len(self.state['records'])<256)
        if self.state['pending'] is not None:
            extra=self.record_store(len(self.state['records'])+1).read()
            if extra is not None:
                rows=unpack(extra['payload']);need(len(rows)==1 and same(rows[0],self.state['pending']));self.derive(rows[0])
                self.state['records'].append(dict(index=rows[0]['sequence'],sha256=digest(extra)));self.state['pending']=None;self.save()
            else:self.state['interrupted'].append(deepcopy(self.state['pending']));self.state['pending']=None;self.save()
        active=self.source.phase.read();entry=dict(sequence=len(self.state['records'])+1,ticket=active['ticket'],source=None,peer=None,
            lease=None if self.lease is None else self.lease.packet(),scope=None if self.lease is None else deepcopy(self.lease.scope.previous),sample=None);self.state['pending']=entry;self.save()
        if self.lease is None and self.version==2 and self.setup_scope is not None and self.setup_scope.state['phase']=='released':
            need(active['verb']=='cleanup');entry['scope']=deepcopy(self.setup_scope.previous);self.save()
        if sample is not None:
            need(self.role=='primary' and entry['lease'] is not None and isinstance(sample,WorldWebSample) and sample.state is None)
            entry['sample']=dict(requestId=sample.request,sha256=None);self.save();sample.capture(active['ticket'])
            sample.qualify(policy,entry['lease']['returned']['returned']['entityId'],previous=previous,changed=changed)
            entry['sample']['sha256']=digest(sample.previous);entry['source']=deepcopy(sample.state['after'])
        else:entry['source']=self.source.capture('observe-browser')
        self.save()
        if self.peer is not None:entry['peer']=self.peer.capture('independent-observer');self.save()
        observed=self.derive(entry);carrier=dict(iosWorldWebObservationRecordVersion=1,runId=self.run,role=self.role,binding=self.binding,payload=pack([entry]))
        self.record_store(entry['sequence']).write(carrier,None);self.state['records'].append(dict(index=entry['sequence'],sha256=digest(carrier)))
        self.state['pending']=None;self.save();return self.original(self.state['records'][-1]),observed
    def original(self,reference):
        need(reference in self.state['records']);return dict(iosWorldWebObservationOriginalVersion=1,runId=self.run,role=self.role,binding=deepcopy(self.binding),reference=deepcopy(reference))
    def validate_original(self,value):
        exact(value,{'iosWorldWebObservationOriginalVersion','runId','role','binding','reference'})
        need(type(value['iosWorldWebObservationOriginalVersion']) is int and value['iosWorldWebObservationOriginalVersion']==1 and same(value,self.original(value['reference'])))
        return self.derive(self.entries()[value['reference']['index']-1])
