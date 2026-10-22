"""Independent Create actor facts from its own primary-UI and peer originals.

No primary action journal, public result, expected state or input ACK enters
this owner. Source references resolve immutable original records. This supplies
only actor facts/publication; images, original export and paired retirement
remain required responsibilities of the complete feature owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import os
import stat

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier,result
from feature_journeys.scenarios import SCENARIOS
from ios.adapters.create_actions import semantic_map
from ios.adapters.create_peer import project_actor
from ios.adapters.create_product_state import adopt_created
from ios.adapters.create_sources import CreateSources

VERSION=1


class CreateActorPublisher(PhaseWitnessPublisher):
    """Batch unchanged historical checks under both actual source locks."""
    def __init__(self,facts):
        self.facts=facts
        with facts.validation_round():
            super().__init__(PrivateFeatureState(facts.store.path.with_name('phase-publication-create-'+facts.run+'-actor.json')),
                facts.binding,facts.peer.phase,facts.lock,facts.guard,facts.validate_original,epoch_ms=facts.peer.epoch_ms,monotonic=facts.peer.monotonic)
    def publish(self,original):
        with self.facts.validation_round():return super().publish(original)
    def resolve(self):
        with self.facts.validation_round():return super().resolve()


class CreateActorFacts:
    def __init__(self,store,lock,run,primary,peer,guard,*,historical=False):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and isinstance(primary,CreateSources)
             and isinstance(peer,CreateSources) and primary.role=='actor-primary' and peer.role=='actor'
             and type(historical) is bool and callable(guard) and primary.run==peer.run==run
             and primary.binding['targetFingerprint']!=peer.binding['targetFingerprint'])
        self.store,self.lock,self.run,self.primary,self.peer,self.guard,self.historical=store,lock,identifier(run),primary,peer,guard,historical
        self.binding=deepcopy(context(peer.binding));self.primary_binding=deepcopy(context(primary.binding))
        self._frame_cache={};self._derive_cache={};self._publication_cache={};self._round=None
        need(store.path.name=='ios-create-actor-facts.json' and lock is peer.lock and lock.path==store.path.with_name('script-feature-sources.lock'))
        lock.assert_held();primary.lock.assert_held();self.previous=store.read()
        self.state=dict(records=[],pending=None,interrupted=[]) if self.previous is None else self.decode(self.previous)
    def envelope(self,state):
        return dict(iosCreateActorFactsVersion=VERSION,binding=self.binding,primaryBinding=self.primary_binding,runId=self.run,payload=pack([state]))
    def source_ref(self,source,frame):
        packet=source.record_store(frame['index']).read();need(packet is not None)
        return dict(index=frame['index'],sha256=digest(packet))
    @staticmethod
    def file_identity(store):
        store._parent();info=store.path.lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600)
        return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_nlink,info.st_uid)
    @contextmanager
    def validation_round(self):
        self.lock.assert_held();self.primary.lock.assert_held();need(self.guard() is not False)
        if self._round is not None:
            yield;return
        pins={};self._round=pins
        try:
            yield
        finally:
            try:
                for store,identity,sha,_packet in pins.values():
                    need(self.file_identity(store)==identity)
                    value=store.read();need(value is not None and digest(value)==sha and self.file_identity(store)==identity)
                self.lock.assert_held();self.primary.lock.assert_held();need(self.guard() is not False)
            finally:self._round=None
    def record_packet(self,source,reference):
        store=source.record_store(reference['index']);key=str(store.path)
        if self._round is not None and key in self._round:
            saved,identity,sha,packet=self._round[key]
            need(sha==reference['sha256'] and self.file_identity(saved)==identity);return packet
        before=self.file_identity(store);packet=store.read()
        need(packet is not None and digest(packet)==reference['sha256'] and self.file_identity(store)==before)
        if self._round is not None:self._round[key]=(store,before,reference['sha256'],packet)
        return packet
    def frame(self,source,reference):
        exact(reference,{'index','sha256'});need(integer(reference['index'],1,len(source.frames)))
        frame=source.frames[reference['index']-1];packet=self.record_packet(source,reference)
        need(same(reference,source.state['records'][frame['index']-1]))
        previous=None if frame['index']==1 else source.frames[frame['index']-2]
        key=(source.role,frame['index'],reference['sha256'],digest(frame),None if previous is None else digest(previous))
        if key not in self._frame_cache:
            originals=unpack(packet['payload']);need(len(originals)==1 and same(originals[0],frame))
            source.validate_frame(frame,previous);self._frame_cache[key]=deepcopy(frame)
        # Only historical validation is memoized. The immutable record bytes
        # and the exact current in-memory prefix are still checked on every use.
        return deepcopy(self._frame_cache[key])
    def derive(self,entry,before,baseline,owned,voxel):
        need(same(self.primary_binding,self.primary.binding) and same(self.binding,self.peer.binding))
        exact(entry,{'sequence','primary','peer'});need(integer(entry['sequence'],1,256))
        ui=self.frame(self.primary,entry['primary']);world=self.frame(self.peer,entry['peer'])
        need(ui['ticket']==world['ticket'] and ui['phaseBefore']['instance']==world['phaseBefore']['instance']
            and all(frame['phaseAfter']['active'] and frame['phaseAfter']['activations'][-1]['ticket']==ui['ticket'] for frame in (ui,world))
            and same(ui['phaseBefore']['activations'][-1]['stimulus'],world['phaseBefore']['activations'][-1]['stimulus']))
        primary,peer=ui['originals']['createAfter'],world['originals']['createAfter']
        if before is not None:
            old_ui=self.frame(self.primary,before['primary']);old_world=self.frame(self.peer,before['peer'])
            need(entry['sequence']==before['sequence']+1 and ui['index']>old_ui['index'] and world['index']>old_world['index'])
        if baseline is None:baseline=entry
        baseline_ui=self.frame(self.primary,baseline['primary'])['originals']['createAfter'];baseline_peer=self.frame(self.peer,baseline['peer'])['originals']['createAfter']
        memo=digest(dict(entry=entry,before=before,baseline=baseline,owned=owned,voxel=voxel,primary=ui,peer=world,baselineUi=baseline_ui,baselinePeer=baseline_peer,
                         primaryBinding=self.primary_binding,binding=self.binding))
        if memo in self._derive_cache:return deepcopy(self._derive_cache[memo])
        new=set(semantic_map(primary))-set(semantic_map(baseline_ui))-set(owned)
        if new:
            need(before is not None and len(new)==1)
            born=adopt_created(self.frame(self.primary,before['primary'])['originals']['createAfter'],primary,list(owned),self.run)
            need(born['id'] in new);owned=owned+[born['id']]
            if born['type']=='PolyVox':need(voxel is None);voxel=dict(id=born['id'],source=deepcopy(born['voxels']))
        need(same(semantic_map(baseline_ui),semantic_map(primary,owned)) and same(semantic_map(baseline_peer),semantic_map(peer,owned)))
        measured=project_actor(primary,peer,self.run,owned,self.primary_binding,self.binding,
            domain_originals=(ui['originals']['domain'],world['originals']['domain']),voxel_baseline=voxel)
        if before is None:need(same(measured,SCENARIOS['create']['baseline']))
        first,last=ui['clockJoin'],world['clockJoin']
        acquisition=dict(hostBeforeEpochMs=first['hostBeforeEpochMs'],hostAfterEpochMs=last['hostAfterEpochMs'],
            hostBeforeMonotonic=first['hostBeforeMonotonic'],hostAfterMonotonic=last['hostAfterMonotonic'])
        PhaseWitnessPublisher.acquisition(acquisition)
        resources=['entity:'+role for role in measured['objects']]
        if measured['editor']:resources.append('panel:create')
        if measured['picker']:resources.append('panel:create-picker')
        # Marker/JSON/GPU/input ownership belongs to their source-validated
        # owners. A matching native basename alone never adds such ownership.
        public=dict(schemaVersion=1,contractVersion=16,runId=self.run,sequence=entry['sequence'],capturedEpochMs=first['hostBeforeEpochMs'],
            state=measured,artifacts=[],resources=resources,lifecycle=deepcopy(last['nativeAfter']['lifecycle']))
        result('feature.create.observe',public)
        output=(dict(ticket=ui['ticket'],public=public,acquisition=acquisition),baseline,owned,voxel)
        self._derive_cache[memo]=deepcopy(output);return output
    def decode(self,value):
        exact(value,{'iosCreateActorFactsVersion','binding','primaryBinding','runId','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosCreateActorFactsVersion']) is int and value['iosCreateActorFactsVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'records','pending','interrupted'});need(type(state['records']) is list and len(state['records'])<=256
            and type(state['interrupted']) is list and len(state['interrupted'])<=128)
        before=baseline=None;owned=[];voxel=None
        for entry in state['records']:
            _,baseline,owned,voxel=self.derive(entry,before,baseline,owned,voxel);before=entry
        for pending in state['interrupted']+([] if state['pending'] is None else [state['pending']]):
            exact(pending,{'sequence','primary','peer'});need(integer(pending['sequence'],1,len(state['records'])+1))
            if pending['primary'] is not None:self.frame(self.primary,pending['primary'])
            if pending['peer'] is not None:self.frame(self.peer,pending['peer'])
        if state['pending'] is not None:need(state['pending']['sequence']==len(state['records'])+1)
        return deepcopy(state)
    def save(self):
        need(not self.historical);self.lock.assert_held();self.primary.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def capture(self):
        self.lock.assert_held();self.primary.lock.assert_held();need(not self.historical)
        if self.state['pending'] is not None:
            # Original source owners retain every successful/partial native
            # read. A delayed peer or interrupted read gets a separate fresh
            # acquisition, never an input replay or a new clock on old bytes.
            self.state['interrupted'].append(deepcopy(self.state['pending']));self.state['pending']=None;self.save()
        self.state['pending']=dict(sequence=len(self.state['records'])+1,primary=None,peer=None);self.save()
        frame=self.primary.capture('independent-primary-ui');self.state['pending']['primary']=self.source_ref(self.primary,frame);self.save()
        frame=self.peer.capture('independent-peer-world');self.state['pending']['peer']=self.source_ref(self.peer,frame);self.save()
        entry=deepcopy(self.state['pending']);baseline=before=None;owned=[];voxel=None
        for old in self.state['records']:
            _,baseline,owned,voxel=self.derive(old,before,baseline,owned,voxel);before=old
        derived,_,_,_=self.derive(entry,before,baseline,owned,voxel)
        self.state['records'].append(entry);self.state['pending']=None;self.save();return deepcopy(entry),derived
    def validate_original(self,original):
        """Historical Publisher decoder; it performs no SDK read or input."""
        exact(original,{'iosCreateActorOriginalVersion','binding','primaryBinding','runId','entry'})
        need(type(original['iosCreateActorOriginalVersion']) is int and original['iosCreateActorOriginalVersion']==VERSION
             and same(original['binding'],self.binding) and same(original['primaryBinding'],self.primary_binding) and original['runId']==self.run)
        index=original['entry']['sequence'];need(integer(index,1,len(self.state['records'])) and same(original['entry'],self.state['records'][index-1]))
        prefix=self.state['records'][:index];memo=digest(dict(binding=self.binding,primaryBinding=self.primary_binding,records=prefix))
        if memo in self._publication_cache:
            # Recheck every ownership-prefix original's immutable file bytes;
            # source verdicts cannot survive a changed/deleted source carrier.
            for entry in prefix:self.frame(self.primary,entry['primary']);self.frame(self.peer,entry['peer'])
            return deepcopy(self._publication_cache[memo])
        before=baseline=None;owned=[];voxel=None
        for entry in self.state['records']:
            derived,baseline,owned,voxel=self.derive(entry,before,baseline,owned,voxel);before=entry
            if entry['sequence']==original['entry']['sequence']:
                need(same(entry,original['entry']));self._publication_cache[memo]=deepcopy(derived);return derived
        need(False)
    def original(self,entry):
        original=dict(iosCreateActorOriginalVersion=VERSION,binding=deepcopy(self.binding),primaryBinding=deepcopy(self.primary_binding),runId=self.run,entry=deepcopy(entry))
        self.validate_original(original);return original
    def publisher(self):
        self.lock.assert_held();self.primary.lock.assert_held();need(not self.historical)
        return CreateActorPublisher(self)
    def publish(self):
        """Publish only independently recomposed original actor facts."""
        publisher=self.publisher()
        if not publisher.resolve():
            # An interrupted planned/issued responsibility stays owned. The
            # shared publisher alone decides whether its original POST exists;
            # neither this owner nor a new source read may resend it.
            return publisher.publish(deepcopy(publisher.state['pending']['original']))
        entry,_derived=self.capture();return publisher.publish(self.original(entry))
