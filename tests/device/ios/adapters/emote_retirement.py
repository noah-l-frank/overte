"""Historical whole Emote cleanup originals, separate from publication ACKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.scenarios import SCENARIOS
from ios.adapters.emote_file_receipts import IOSEmoteFileReceipts
from ios.adapters.emote_marker_entities import IOSEmoteMarkerEntities
from ios.adapters.emote_pointers import IOSEmotePointers
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_marker_measurements import body_preserved,view_preserved
from ios.adapters.emote_marker_partial import drained_partial
from ios.adapters.emote_native_prefix import follow as native_prefix
from ios.adapters.emote_observation import IOSEmoteObservationDecoder
from ios.adapters.emote_peer_sources import IOSEmotePeerSources
from ios.adapters.emote_sources import IOSEmoteSources
from ios.adapters.web_closures import drained_owned_resources

VERSION=1


class Frozen(PrivateFeatureState):
    def __init__(self,path,value):super().__init__(path);self.value=deepcopy(value)
    def read(self):return deepcopy(self.value)
    def write(self,*_args,**_kwargs):need(False)
    def discard(self,*_args,**_kwargs):need(False)


class IOSEmoteRetirement:
    def __init__(self,store,root,binding,primary_binding,run,role,fixture_url,phase_instance,lock,primary_lock,policy,paths,guard):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and isinstance(primary_lock,ScriptSourceLock) and callable(guard))
        self.store,self.root,self.binding,self.primary_binding=store,Path(root),deepcopy(context(binding)),deepcopy(context(primary_binding))
        self.run,self.role,self.fixture_url,self.phase_instance=identifier(run),role,fixture_url,identifier(phase_instance)
        self.lock,self.primary_lock,self.policy,self.guard=lock,primary_lock,deepcopy(policy),guard
        need(role in ('primary','actor') and self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir())
        exact(paths,{'sources','peers','files','entities','pointers'});self.paths={key:Path(value) if value is not None else None for key,value in paths.items()}
        need(self.paths['sources'] is not None and self.paths['files'] is not None and self.paths['entities'] is not None and self.paths['pointers'] is not None and (role=='actor')==(self.paths['peers'] is not None))
        self.previous=store.read();self.state=dict(records=[],abandoned=[],pending=None)
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):return dict(iosEmoteRetirementVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,
        primaryBinding=self.primary_binding,fixtureUrl=self.fixture_url,phaseInstance=self.phase_instance,artifactRoot=str(self.root),imagePolicy=self.policy,
        paths={key:None if value is None else str(value) for key,value in self.paths.items()},payload=pack([state]))

    def record_store(self,index):
        need(integer(index,1,128));return PrivateFeatureState(self.root/('emote-retirement-'+self.run+'-'+self.role+'-'+str(index)+'.json'))

    def original(self,reference):
        exact(reference,{'index','sha256'});value=self.record_store(reference['index']).read();need(value is not None and digest(value)==reference['sha256'])
        exact(value,{'iosEmoteRetirementOriginalVersion','runId','role','binding','primaryBinding','phaseInstance','fixtureUrl','payload'})
        need(type(value['iosEmoteRetirementOriginalVersion']) is int and value['iosEmoteRetirementOriginalVersion']==VERSION
            and value['runId']==self.run and value['role']==self.role and same(value['binding'],self.binding)
            and same(value['primaryBinding'],self.primary_binding) and value['phaseInstance']==self.phase_instance and value['fixtureUrl']==self.fixture_url)
        rows=unpack(value['payload']);need(len(rows)==1);return rows[0]

    def decode(self,value):
        exact(value,{'iosEmoteRetirementVersion','runId','role','binding','primaryBinding','fixtureUrl','phaseInstance','artifactRoot','imagePolicy','paths','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'records','abandoned','pending'})
        need(all(type(state[key]) is list for key in ('records','abandoned')))
        used=state['records']+state['abandoned'];need(len(used)<=128)
        indices=[]
        for key in ('records','abandoned'):
            previous=0
            for ref in state[key]:
                self.original(ref);need(ref['index']>previous);previous=ref['index'];indices.append(ref['index'])
                if key=='records':self.derive(ref)
        need(sorted(indices)==list(range(1,len(used)+1)))
        pending=state['pending']
        if pending is not None:
            exact(pending,{'index','value'});need(pending['index']==len(used)+1 and pending['index']<=128)
            candidate=pending['value'];need(same(candidate,self.wrap(unpack(candidate['payload'])[0])))
            existing=self.record_store(pending['index']).read();need(existing is None or same(existing,candidate))
        elif len(used)<128:need(self.record_store(len(used)+1).read() is None)
        return deepcopy(state)

    def wrap(self,original):
        exact(original,{'observation','sources','peers','scope','fileReceipts','sampleOwners','inputOwners','entities','pointers'})
        return dict(iosEmoteRetirementOriginalVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,
            primaryBinding=self.primary_binding,phaseInstance=self.phase_instance,fixtureUrl=self.fixture_url,payload=pack([original]))

    def save(self):
        need(same(self.store.read(),self.previous));value=self.envelope(self.state)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def current(self):
        self.lock.assert_held();self.primary_lock.assert_held()
        actual=self.store.read()
        if not same(actual,self.previous):
            # A write may have committed before its local return was lost.
            # Adoption is limited to our exact immutable candidate/state.
            need(same(actual,self.envelope(self.state)));self.previous=deepcopy(actual)
        need(self.guard() is not False)

    def owners(self,original):
        source_root=self.root if self.role=='primary' else self.root/'primary-sdk-originals'
        sources=IOSEmoteSources(Frozen(self.paths['sources'],original['sources']),source_root,self.primary_binding,self.run,self.role,
            self.primary_lock,lambda:True,None,historical=True)
        peers=None
        if self.role=='actor':peers=IOSEmotePeerSources(Frozen(self.paths['peers'],original['peers']),self.root,self.binding,self.run,None,
            self.lock,lambda:True,historical=True)
        else:need(original['peers'] is None)
        decoder=IOSEmoteObservationDecoder(sources,self.binding,self.role,self.root,self.policy,self.lock,phase_instance=self.phase_instance,peers=peers)
        return sources,peers,decoder

    def derive(self,reference):
        """Pure callback: reread original files; no SDK, HTTP or live guard."""
        self.lock.assert_held();self.primary_lock.assert_held();original=self.original(reference)
        exact(original,{'observation','sources','peers','scope','fileReceipts','sampleOwners','inputOwners','entities','pointers'})
        sources,peers,decoder=self.owners(original);derived=decoder.derive(original['observation']);public=derived['public']
        need(public['state']==SCENARIOS['emotes']['baseline'] and public['resources']==[] and not public['artifacts'])
        current=decoder.source(original['observation']['source'])
        need(current['phaseAfter']['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        scope=IOSEmoteMarkerScope.archive(original['scope'],root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        need(scope.state['phase']=='released' and scope.state['pending'] is None and len(scope.state['quiet'])>=3 and scope.state['quiet'][-1]==len(scope.frames))
        baseline=scope.frames[scope.state['baseline']-1];owned=scope.state['admission'];quiet=[scope.frames[index-1] for index in scope.state['quiet']]
        need(scope.quiet_interval(quiet[0],quiet[-1]))
        for frame in quiet:
            scope.ui_absent(frame);scope.dialog_drained(frame);need(frame['clockJoin']['nativeAfter']['animation']['overrideActive'] is False)
            body_preserved(baseline['world'],frame['world']);view_preserved(baseline['world'],frame['world'])
            if scope.state['cleanupMode']=='unloaded':
                scope.unexecuted(frame);need(frame['world']['source']['tree']['entities']==baseline['world']['source']['tree']['entities'])
                drained_partial(frame['web'],baseline['web'])
            else:
                scope.restored_marker(baseline,frame,owned,scope.state['stopBarrier'])
                drain=drained_partial if scope.state['cleanupMode'] in ('partial-execution','finished-execution') else drained_owned_resources
                drain(frame['web'],scope.frames[scope.state['webAdmission']-1]['web'])
        entities=IOSEmoteMarkerEntities.archive(original['entities'],store=Frozen(self.paths['entities'],original['entities']),root=self.root,
            binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        pointers=IOSEmotePointers.archive(original['pointers'],store=Frozen(self.paths['pointers'],original['pointers']),root=self.root,
            binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        pointer_closure=pointers.closed(scope)
        entities.closed(scope);entity_end=entities.latest()['clockJoin']['nativeAfter']
        native_prefix(pointer_closure['quietLast']['clockJoin']['nativeAfter'],entities.latest()['clockJoin']['nativeBefore'])
        files=None
        if scope.state['fileOwnership'] is not None:
            files=IOSEmoteFileReceipts.archive(original['fileReceipts'],store=Frozen(self.paths['files'],original['fileReceipts']),root=self.root,
                binding=self.binding,run=self.run,role=self.role,lock=self.lock)
            need(files.state['pending'] is None and files.state['records']);last=files.original(files.state['records'][-1])
            need(last['kind']=='absent' and same(last['ownership'],scope.state['fileOwnership']))
            need(last['clockJoin']['hostBeforeEpochMs']>=quiet[-1]['clockJoin']['hostAfterEpochMs']
                and last['clockJoin']['hostBeforeMonotonic']>=quiet[-1]['clockJoin']['hostAfterMonotonic'])
            native_prefix(entity_end,last['clockJoin']['nativeBefore'])
        else:need(original['fileReceipts'] is None)
        if self.role=='primary':own_native=current['clockJoin']['nativeBefore'];own_end=current['clockJoin']['nativeAfter'];own_world=current['world']
        else:
            peer=decoder.retained(peers,original['observation']['peerAfter'])['peer'];own_native=peer['clockJoin']['nativeBefore'];own_end=peer['clockJoin']['nativeAfter'];own_world=peer['world']
        native_prefix((entity_end if files is None else last['clockJoin']['nativeAfter']),own_native)
        body_preserved(baseline['world'],own_world);view_preserved(baseline['world'],own_world)
        need(own_world['source']['tree']['entities']==baseline['world']['source']['tree']['entities'] and not own_world['source']['markers'])
        final_pointer=pointer_closure['last'];native_prefix(own_end,final_pointer['clockJoin']['nativeBefore'])
        need(final_pointer['clockJoin']['hostBeforeMonotonic']>=derived['acquisition']['hostAfterMonotonic']
            and final_pointer['clockJoin']['hostBeforeEpochMs']>=derived['acquisition']['hostAfterEpochMs']
            and same(own_end['lifecycle'],final_pointer['clockJoin']['nativeAfter']['lifecycle'])
            and final_pointer['clockJoin']['nativeAfter']['animation']['overrideActive'] is False
            and own_end['animation']['history']['callSequence']==final_pointer['clockJoin']['nativeAfter']['animation']['history']['callSequence'])
        # Extend only the measured end with the independently acquired original
        # pointer window; the public/source beginning is never refreshed.
        from adapters.phase_witness_publisher import PhaseWitnessPublisher
        derived['acquisition']=PhaseWitnessPublisher.acquisition(dict(derived['acquisition'],
            hostAfterEpochMs=final_pointer['clockJoin']['hostAfterEpochMs'],hostAfterMonotonic=final_pointer['clockJoin']['hostAfterMonotonic']))
        self.samples(original['sampleOwners'],scope)
        self.inputs(original['inputOwners'],current,sources)
        first,final=quiet[0],quiet[-1];a,b=first['world'],final['world']
        evidence=dict(hostAfterFirstEpochMs=first['clockJoin']['hostAfterEpochMs'],hostBeforeLastEpochMs=final['clockJoin']['hostBeforeEpochMs'],
            hostAfterFirstMonotonic=first['clockJoin']['hostAfterMonotonic'],hostBeforeLastMonotonic=final['clockJoin']['hostBeforeMonotonic'],
            nativeAfterFirstEpochMs=a['clockAfter']['epochMs'],nativeBeforeLastEpochMs=b['clockBefore']['epochMs'],
            nativeAfterFirstMonotonicMs=a['clockAfter']['monotonicMs'],nativeBeforeLastMonotonicMs=b['clockBefore']['monotonicMs'],
            nativeInstance=a['instance'],processId=a['processId'])
        return dict(derived,retirement=dict(originalSha256=reference['sha256'],quiet=evidence,
            provenance=dict(version=1,namespace='ios-emote-retirement-original',reference=deepcopy(reference),originalSha256=reference['sha256'])))

    def samples(self,owners,scope):
        # Keep only the original bounded owner metadata here. Each immutable
        # sample file and original GPU transcript is reread by its saved hash;
        # copying every full GPU transcript into each retirement would exceed
        # the private metadata size limit during an ordinary complete journey.
        from ios.adapters.emote_samples import IOSEmoteSamples,archived_sample
        from ios.adapters.emote_sample_recovery import validate_abandonment
        if owners is None:
            need(not any(self.root.glob('emote-sample-'+self.run+'-'+self.role+'-*.json')));return
        samples=object.__new__(IOSEmoteSamples);samples.root,samples.binding,samples.run,samples.role=self.root,self.binding,self.run,self.role
        samples.policy,samples.lock=self.policy,self.lock
        state=samples.decode(owners);need(state['phase']=='ready')
        for reference in state['rows']:
            row=samples.record(reference)
            if row['phase']=='abandoned':
                validate_abandonment(row,root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
            else:
                need(scope.state['admission'] is not None and scope.state['admission']['marker'] is not None)
                archived_sample(row,root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock,policy=self.policy,
                    marker_nonce=scope.state['fileOwnership']['nonce'],marker_url=scope.state['admission']['marker']['sourceUrl'])

    def inputs(self,owners,current,sources):
        exact(owners,{'cleanup','actions','background'})
        if self.role=='actor':need(all(value is None for value in owners.values()));return
        if owners['cleanup'] is not None:
            from ios.adapters.emote_cleanup import IOSEmoteCleanup
            cleanup=object.__new__(IOSEmoteCleanup);cleanup.sources=sources;state=cleanup.decode(owners['cleanup'])
            need(state['phase']=='closed' and state['intents'] and state['intents'][-1]['kind']=='release' and state['intents'][-1]['after'] is not None)
        elif owners['actions'] is not None:need(False)
        if owners['actions'] is not None:
            from ios.adapters.emote_actions import IOSEmoteActions
            from types import SimpleNamespace
            sources.phase=SimpleNamespace(fixture_url=self.fixture_url);actions=object.__new__(IOSEmoteActions);actions.source=sources
            state=actions.decode(owners['actions'])
            for row in state['history']+([state['current']] if state['current'] else []):
                for intent in row['intents']:
                    if intent['kind']=='qt':
                        need(current['ui']['scope']['sequence']>=intent['input']['sequence']
                            and all(current['ui']['scope'][key]==intent['input'][key] for key in ('instance','generation')))
                    elif intent['after'] is None:
                        before=intent['barrier']['revision'];wanted=intent['input']=='open'
                        need(any(frame['ui']['open']==wanted for frame in sources.frames[before:]))
        if owners['background'] is not None:
            from ios.adapters.emote_lifecycle import IOSEmoteBackground
            background=object.__new__(IOSEmoteBackground);background.run,background.fixture_url,background.binding,background.pid=self.run,self.fixture_url,self.binding,int(self.binding['processIdentity'])
            state=background.decode(owners['background']);need(state['phase']=='observed' and state['after'] is not None)
            native_prefix(state['after'],current['clockJoin']['nativeBefore'])

    def resolve(self):
        """Complete only the journaled immutable candidate; no acquisitions."""
        self.current();pending=self.state['pending']
        if pending is None:return None
        store=self.record_store(pending['index']);value=pending['value'];old=store.read()
        if old is None:store.write(value,None)
        else:need(same(old,value))
        reference=dict(index=pending['index'],sha256=digest(value));self.derive(reference)
        self.state['records'].append(reference);self.state['pending']=None;self.save();return deepcopy(reference)

    def abandon(self):
        """Keep an unpublishable original; permit a distinct future read."""
        self.current();pending=self.state['pending']
        if pending is None:return False
        store=self.record_store(pending['index']);value=pending['value'];old=store.read()
        if old is None:store.write(value,None)
        else:need(same(old,value))
        reference=dict(index=pending['index'],sha256=digest(value));self.original(reference)
        self.state['abandoned'].append(reference);self.state['pending']=None;self.save();return True

    def retain(self,original):
        self.current();need(self.state['pending'] is None)
        index=len(self.state['records'])+len(self.state['abandoned'])+1;need(index<=128)
        self.state['pending']=dict(index=index,value=self.wrap(original));self.save()
        return self.resolve()
