"""Durable primary Create observations from native originals and actual owners.

This owns read acquisitions and publication records, never Create input. A
failed read/image remains owned. A later attempt reads again without repeating
an action or attaching a new clock to an older native packet.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.scenarios import SCENARIOS
from ios.adapters.create_actions import CreateActions,semantic_map
from ios.adapters.create_export_artifact import CreateExportArtifact
from ios.adapters.create_marker_identity import PreparedCreateMarker
from ios.adapters.create_primary_measurements import compose
from ios.adapters.create_sample import CreateSampleOwner
from ios.adapters.create_sources import CreateSources

VERSION=1


class CreatePrimary:
    def __init__(self,store,lock,binding,run,source,guard,*,actions=None,marker=None,sample_resolver=None,export_resolver=None):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and isinstance(source,CreateSources)
            and source.role=='primary' and source.lock is lock and callable(guard)
            and (actions is None or isinstance(actions,CreateActions)) and (marker is None or isinstance(marker,PreparedCreateMarker))
            and (sample_resolver is None or callable(sample_resolver)) and (export_resolver is None or callable(export_resolver)))
        self.store,self.lock,self.binding,self.run,self.source,self.guard=store,lock,deepcopy(context(binding)),identifier(run),source,guard
        self.actions,self.marker,self.sample_resolver,self.export_resolver=actions,marker,sample_resolver,export_resolver
        need(source.run==run and same(source.binding,binding) and store.path.name=='ios-create-primary.json'
            and lock.path==store.path.with_name('script-feature-sources.lock'))
        for owner in (actions,):
            if owner is not None:need(owner.lock is lock and owner.run==run and same(owner.binding,binding))
        if marker is not None:need(marker.run==run and same(marker.binding,binding) and marker.fixture_url==source.phase.fixture_url)
        lock.assert_held();self._samples={};self._frames={};self._contexts={};self.previous=store.read();self.state=dict(records=[],pending=None,interrupted=[])
        if self.previous is not None:self.state=self.decode(self.previous)
    def envelope(self,state):
        return dict(iosCreatePrimaryVersion=VERSION,binding=self.binding,runId=self.run,payload=pack([state]))
    def record_store(self,index):
        need(integer(index,1,256));return PrivateFeatureState(self.store.path.with_name('ios-create-primary-'+str(index)+'.json'))
    def source_ref(self,frame):
        ref=self.source.state['records'][frame['index']-1];need(ref['index']==frame['index']);return deepcopy(ref)
    def frame(self,ref):
        exact(ref,{'index','sha256'});need(integer(ref['index'],1,len(self.source.frames)) and same(ref,self.source.state['records'][ref['index']-1]))
        carrier=self.source.record_store(ref['index']).read();need(carrier is not None and digest(carrier)==ref['sha256'])
        frame=self.source.frames[ref['index']-1];previous=None;predecessor=None
        if ref['index']>1:
            predecessor=self.source.state['records'][ref['index']-2];exact(predecessor,{'index','sha256'});need(predecessor['index']==ref['index']-1)
            old=self.source.record_store(predecessor['index']).read();need(old is not None and digest(old)==predecessor['sha256'])
            rows=unpack(old['payload']);need(len(rows)==1 and same(rows[0],self.source.frames[ref['index']-2]))
            previous=rows[0]
        key=(ref['index'],ref['sha256'],digest(frame),None if predecessor is None else predecessor['sha256'])
        if key not in self._frames:
            rows=unpack(carrier['payload']);need(len(rows)==1 and same(rows[0],frame))
            self.source.validate_frame(frame,previous);self._frames[key]=deepcopy(frame)
        return deepcopy(self._frames[key])
    def context(self,entry):
        action=entry['actions'];marker=entry['marker'];owned=[];voxel=None
        if action is not None:
            need(isinstance(self.actions,CreateActions) and self.actions.lock is self.lock and self.actions.run==self.run and same(self.actions.binding,self.binding))
        if marker is not None:
            need(isinstance(self.marker,PreparedCreateMarker) and same(self.marker.binding,self.binding) and self.marker.run==self.run
                and same(self.marker.state['admission'],marker))
        key=digest(dict(actions=action,marker=marker))
        if key not in self._contexts:
            if action is not None:
                state=self.actions.decode(action);owned=[row['id'] for row in state['owned']];voxel=state['voxelBaseline']
                need(marker is not None and same(state['baseline']['marker'],marker['marker']))
            self._contexts[key]=deepcopy((owned,voxel))
        return deepcopy(self._contexts[key])
    def sample(self,reference):
        if reference is None:return None
        exact(reference,{'requestId','sha256'});need(self.sample_resolver is not None)
        key=(reference['requestId'],reference['sha256'])
        if key not in self._samples:
            owner=self.sample_resolver(reference['requestId'])
            need(isinstance(owner,CreateSampleOwner) and owner.lock is self.lock and owner.run==self.run and owner.role=='primary'
                and same(owner.binding,self.binding) and owner.previous is not None and digest(owner.previous)==reference['sha256'])
            state=deepcopy(owner.state);need(state['phase']=='qualified')
            self._samples[key]=dict(store=owner.store,root=owner.frame_owner.root,state=state)
        cached=self._samples[key];current=cached['store'].read()
        need(current is not None and digest(current)==reference['sha256'])
        # Only pure native/pixel qualification is memoized. Every historical
        # use still checks actual owner bytes and reads the inode-bound PNG,
        # including every retained original native chunk and its exact hash.
        state=cached['state']
        VulkanWorldFrameOwner.archive_original(state['frameOwnership'],cached['root'],self.binding,self.run,'primary',0,reference['requestId'],self.lock)
        return dict(state=deepcopy(state),frameOwnership=deepcopy(state['frameOwnership']),measurement=deepcopy(state['qualification']))
    def export_owner(self,reference):
        exact(reference,{'storeName','snapshot'})
        need(type(reference['storeName']) is str and re.fullmatch(r'ios-create-export-[a-f0-9]{32}-artifact\.json',reference['storeName']) and self.export_resolver is not None)
        owner=self.export_resolver(reference['storeName'])
        need(isinstance(owner,CreateExportArtifact) and owner.lock is self.lock and owner.run==self.run and same(owner.binding,self.binding)
            and owner.store.path==self.store.path.with_name(reference['storeName']))
        return owner
    def derive(self,entry,baseline,validated_previous):
        exact(entry,{'sequence','ticket','actions','marker','before','after','sample','export','files','phaseAfter'})
        need(integer(entry['sequence'],1,256));identifier(entry['ticket']);before,after=self.frame(entry['before']),self.frame(entry['after'])
        need(before['ticket']==after['ticket']==entry['ticket'] and same(entry['phaseAfter'],after['phaseAfter']))
        owned,voxel=self.context(entry);sample=self.sample(entry['sample']);export=None
        if sample is not None and sample['state']['qualificationInputs']['changed']:
            previous=[]
            for old in validated_previous:
                if old['sequence']<entry['sequence'] and old['ticket']!=entry['ticket'] and old['sample'] is not None:previous.append(old['sample'])
            need(previous and sample['state']['qualificationInputs']['previous']['requestId']==previous[-1]['requestId'])
        if entry['files'] is not None:
            need(self.actions is not None and self.actions.files.state is not None)
            need(same(self.actions.files.store.read(),self.actions.files.previous))
            originals=self.actions.files.decode(self.actions.files.previous)['originals'];need(any(same(row,entry['files']) for row in originals))
        if entry['export'] is not None:
            reference=entry['export'];artifact=self.export_owner(reference)
            need(reference['snapshot'] is not None)
            state=artifact.decode(reference['snapshot']);need(state['phase']=='copied' and entry['files'] is not None)
            current=artifact.state;need(current is not None and same(current['originals'],state['originals']) and same(current['file'],state['file']))
            artifact.read()
            export=dict(name=state['name'],measurement=state['measurement'],model=state['originals']['model'],current=state['originals']['current'])
        return compose(self.run,self.binding,entry['sequence'],before,after,baseline,owned_ids=owned,marker=entry['marker'],voxel_baseline=voxel,
            sample=sample,export=export,files=None if entry['files'] is None else entry['files']['packet'])
    def decode(self,value):
        exact(value,{'iosCreatePrimaryVersion','binding','runId','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosCreatePrimaryVersion']) is int and value['iosCreatePrimaryVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'records','pending','interrupted'});need(type(state['records']) is list and len(state['records'])<=256
            and type(state['interrupted']) is list and len(state['interrupted'])<=128)
        baseline=None;previous_after=0;validated_previous=[]
        for index,ref in enumerate(state['records'],1):
            exact(ref,{'index','sha256'});need(ref['index']==index);carrier=self.record_store(index).read()
            need(carrier is not None and digest(carrier)==ref['sha256']);exact(carrier,{'iosCreatePrimaryRecordVersion','binding','runId','payload'})
            need(type(carrier['iosCreatePrimaryRecordVersion']) is int and carrier['iosCreatePrimaryRecordVersion']==VERSION and same(carrier['binding'],self.binding) and carrier['runId']==self.run)
            entries=unpack(carrier['payload']);need(len(entries)==1);entry=entries[0]
            need(entry['sequence']==index and entry['before']['index']>previous_after);previous_after=entry['after']['index']
            if baseline is None:
                need(entry['actions'] is None and entry['marker'] is None and entry['sample'] is None and entry['export'] is None and entry['files'] is None)
                baseline=self.frame(entry['before'])['originals']['createBefore']
            self.derive(entry,baseline,validated_previous);validated_previous.append(deepcopy(entry))
        for pending in state['interrupted']+([] if state['pending'] is None else [state['pending']]):
            exact(pending,{'sequence','ticket','actions','marker','before','after','sample','export','files','phaseAfter'})
            need(integer(pending['sequence'],1,len(state['records'])+1));identifier(pending['ticket'])
            self.context(pending)
            if pending['sample'] is not None:
                ref=pending['sample'];exact(ref,{'requestId','sha256'});identifier(ref['requestId'][4:])
                need(ref['requestId'].startswith('ios-') and self.sample_resolver is not None)
                owner=self.sample_resolver(ref['requestId'])
                need(isinstance(owner,CreateSampleOwner) and owner.lock is self.lock and owner.run==self.run and owner.role=='primary' and same(owner.binding,self.binding))
                if ref['sha256'] is not None:need(owner.previous is not None and digest(owner.previous)==ref['sha256'])
            if pending['export'] is not None:self.export_owner(pending['export'])
            for key in ('before','after'):
                if pending[key] is not None:self.frame(pending[key])
        return deepcopy(state)
    def save(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def record_entries(self):
        entries=[]
        for ref in self.state['records']:
            packet=self.record_store(ref['index']).read();need(packet is not None and digest(packet)==ref['sha256'])
            rows=unpack(packet['payload']);need(len(rows)==1 and rows[0]['sequence']==ref['index']);entries.append(rows[0])
        return entries
    def baseline(self):
        need(self.state['records']);record=self.record_store(1).read();entry=unpack(record['payload'])[0]
        return self.frame(entry['before'])['originals']['createBefore']
    def capture(self,*,sample=None,policy=None,export_artifact=None):
        """A fresh readonly attempt; caller supplies a newly reserved GPU owner."""
        self.lock.assert_held();need(self.guard() is not False and len(self.state['records'])<256 and (export_artifact is None or isinstance(export_artifact,CreateExportArtifact)))
        need(sample is None or isinstance(sample,CreateSampleOwner) and sample.state is None and sample.lock is self.lock
            and sample.run==self.run and sample.role=='primary' and same(sample.binding,self.binding))
        if self.state['pending'] is not None:
            # A saved complete record is adopted through its retained intent,
            # never by issuing another source/GPU acquisition for that record.
            target=self.record_store(len(self.state['records'])+1);extra=target.read()
            if extra is not None:
                entries=unpack(extra['payload']);need(len(entries)==1 and same(entries[0],self.state['pending']))
                self.derive(entries[0],self.baseline() if self.state['records'] else self.frame(entries[0]['before'])['originals']['createBefore'],self.record_entries())
                self.state['records'].append(dict(index=entries[0]['sequence'],sha256=digest(extra)));self.state['pending']=None;self.save()
            else:self.state['interrupted'].append(deepcopy(self.state['pending']));self.state['pending']=None;self.save()
        first=self.source.phase.read();initial=not self.state['records']
        candidates=[row['evidence'] for row in SCENARIOS['create']['steps'] if row['verb']==first['verb'] and same(row['inputs'],first['inputs'])]
        required=[] if first['verb'] in ('baseline','cleanup') else (candidates[0] if candidates else None)
        need(required is not None and all(same(row,required) for row in candidates))
        need(not ({'image','changed'} & set(required)) or sample is not None)
        need('file' not in required or export_artifact is not None)
        changed='changed' in required
        previous=None
        if changed:
            prior=[]
            for ref in self.state['records']:
                entry=unpack(self.record_store(ref['index']).read()['payload'])[0]
                if entry['ticket']!=first['ticket'] and entry['sample'] is not None:prior.append(entry['sample'])
            need(prior and self.sample_resolver is not None);previous=self.sample_resolver(prior[-1]['requestId'])
        if initial:need(self.actions is None and self.marker is None and sample is None and export_artifact is None)
        action=None if self.actions is None else deepcopy(self.actions.store.read())
        marker=None if self.marker is None else self.marker.state['admission']
        entry=dict(sequence=len(self.state['records'])+1,ticket=first['ticket'],actions=action,marker=marker,before=None,after=None,sample=None,export=None,files=None,phaseAfter=None)
        self.state['pending']=entry;self.save()
        frame=self.source.capture('primary-before');entry['before']=self.source_ref(frame);self.save()
        owned,voxel=self.context(entry)
        if sample is not None:
            need(self.sample_resolver is not None)
            resolved=self.sample_resolver(sample.request)
            need(isinstance(resolved,CreateSampleOwner) and resolved.store.path==sample.store.path and resolved.frame_owner.root==sample.frame_owner.root and resolved.state is None)
            # The outer ledger owns this request before any native capture.
            # Failure leaves its exact request discoverable for retirement.
            entry['sample']=dict(requestId=sample.request,sha256=None);self.save()
            need(marker is not None);sample.capture(first['ticket'],first['afterEpochMs'])
            actual=marker['marker'];import json
            sample.qualify(policy,owned,dict(id=actual['id'],sourceUrl=actual['sourceUrl'],nonce=json.loads(actual['userData'])['nonce']),
                voxel_baseline=voxel,previous=previous,changed=changed)
            entry['sample']=dict(requestId=sample.request,sha256=digest(sample.previous));self.save()
        if self.actions is not None and self.actions.files.state is not None and self.actions.files.state['phase']=='staged':
            self.actions.files.observe();entry['files']=deepcopy(self.actions.files.state['originals'][-1]);self.save()
        if export_artifact is not None:
            need(self.actions is not None and export_artifact.state is None and entry['files'] is not None)
            entry['export']=dict(storeName=export_artifact.store.path.name,snapshot=None)
            actual=self.export_owner(entry['export']);need(actual.state is None and actual.root==export_artifact.root);self.save()
            history=self.actions.files.state['originals'];before_files=next(row for row in history if row['query']['operation']=='observe' and row['packet']['source']['exists']
                and row['packet']['source']['files'][1]==dict(name='export.json',exists=False))
            model=self.source.readers['create'].read(self.run)
            selected=[row for row in model['source']['entities'] if row['id'] in owned and row['type']=='Model'];need(len(selected)==1)
            export_artifact.capture(before_files,entry['files'],model,selected[0]['id'],after_native=before_files['packet']['clockAfter']['epochMs'])
            entry['export']['snapshot']=deepcopy(export_artifact.previous);self.save()
        frame=self.source.capture('primary-after');entry['after']=self.source_ref(frame);entry['phaseAfter']=deepcopy(frame['phaseAfter']);self.save()
        need(same(action,None if self.actions is None else self.actions.store.read()))
        baseline=frame['originals']['createBefore'] if initial else self.baseline();value=self.derive(entry,baseline,self.record_entries())
        if initial:need(value['resources']==[])
        carrier=dict(iosCreatePrimaryRecordVersion=VERSION,binding=self.binding,runId=self.run,payload=pack([entry]));target=self.record_store(entry['sequence'])
        need(target.read() is None);target.write(carrier,None)
        self.state['records'].append(dict(index=entry['sequence'],sha256=digest(carrier)));self.state['pending']=None;self.save()
        return deepcopy(value)
    def owned_samples(self):
        """Every intent, including failed/interrupted reads, remains discoverable."""
        self.lock.assert_held();references=[]
        for ref in self.state['records']:
            packet=self.record_store(ref['index']).read();need(packet is not None and digest(packet)==ref['sha256'])
            references.append(unpack(packet['payload'])[0]['sample'])
        references += [entry['sample'] for entry in self.state['interrupted']+([] if self.state['pending'] is None else [self.state['pending']])]
        owners={}
        for ref in references:
            if ref is None or ref['requestId'] in owners:continue
            need(self.sample_resolver is not None);owner=self.sample_resolver(ref['requestId'])
            need(isinstance(owner,CreateSampleOwner) and owner.lock is self.lock and owner.role=='primary' and owner.run==self.run and same(owner.binding,self.binding))
            owners[ref['requestId']]=owner
        return list(owners.values())
    def owned_exports(self):
        self.lock.assert_held();references=[]
        for ref in self.state['records']:
            packet=self.record_store(ref['index']).read();need(packet is not None and digest(packet)==ref['sha256'])
            references.append(unpack(packet['payload'])[0]['export'])
        references += [entry['export'] for entry in self.state['interrupted']+([] if self.state['pending'] is None else [self.state['pending']])]
        return list({ref['storeName']:self.export_owner(ref) for ref in references if ref is not None}.values())
