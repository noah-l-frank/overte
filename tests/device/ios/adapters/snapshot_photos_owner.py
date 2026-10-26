"""Normal Save -> independently admitted Photos bytes -> owned retirement.

This internal owner retains every uncertain input and original. The complete
Snapshot journey, independent Actor, Share/upload and process end stay separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import re
import uuid
from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_clock_join import digest
from adapters.native_clock_source_history import restore
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import check as transport_check
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters.graphics_history import follow_native
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_photos_actions import PhotosAction
from ios.adapters.snapshot_photos_context import PhotosClientContext,PhotosCompanionContext,same_device
from ios.adapters.snapshot_photos_packets import PhotosSaveInputs,PACKETS
from ios.adapters.installed_code import source as process_source
from ios.adapters.tablet_web_admission import installed_forward
from ios.adapters import snapshot_export_controls as controls,snapshot_exports as exports
from ios.adapters import snapshot_destination as destination,snapshot_photos_source as source,snapshot_companion_source as companion_source
from snapshot_observation import inspect_snapshot


class SnapshotPhotosPending(NativeUIError):pass


def clock(value,previous=None):
    exact(value,{'epochMs','monotonic'});need(number(value['epochMs'],1,1e15) and number(value['monotonic'],0,1e15))
    if previous is not None:need(value['epochMs']>=previous['epochMs'] and value['monotonic']>=previous['monotonic'])
    return value


class IOSSnapshotPhotosOwner:
    def __init__(self,runtime,selector,run,primary,companion,primary_lock,companion_lock,phase,*,epoch_ms,monotonic,sleep):
        from ios.adapters.snapshot_photos_runtime import IOSSnapshotPhotosRuntime
        need(isinstance(runtime,IOSSnapshotPhotosRuntime) and isinstance(primary,PhotosClientContext)
            and isinstance(companion,PhotosCompanionContext) and isinstance(phase,PhaseFixtureReader)
            and phase.area=='snapshots' and phase.run==run and all(callable(fn) for fn in (epoch_ms,monotonic,sleep)))
        self.runtime,self.selector,self.run,self.primary,self.companion=runtime,selector,identifier(run),primary,companion
        self.lock,self.companion_lock=primary_lock,companion_lock;self.lock.assert_held();self.companion_lock.assert_held()
        self.binding,self.companion_binding=deepcopy(context(primary.binding)),deepcopy(context(companion.binding))
        self.root=runtime.state_path(selector).parent;self.companion_root=companion.session_store.path.parent
        need(self.root!=self.companion_root and self.lock.path==self.root/'script-feature-sources.lock'
            and companion_lock.path==self.companion_root/'script-feature-sources.lock')
        self.phase,self.fixture_url,self.epoch_ms,self.monotonic,self.sleep=phase,phase.fixture_url,epoch_ms,monotonic,sleep
        self.store=PrivateFeatureState(self.root/'photos-save-owner.json');self.previous=self.store.read();self.historical=False
        self.state=dict(ticket=None,phaseOriginal=None,capture=None,device=None,slots=[],input=None,export=None,actions=[],handoffs=[],
            nativeTail=None,companionTail=None,destination=[],chunks=[],saved=None,photoQuiet=[],fileQuiet=[],retireOriginal=None,cleaned=None)
        if self.previous is not None:self.state=self.decode(self.previous)
        else:self.inventory(set())

    def stamp(self):return clock(dict(epochMs=self.epoch_ms(),monotonic=self.monotonic()))
    def guard(self):
        self.lock.assert_held();self.companion_lock.assert_held();transport_check()
        need(same(self.store.read(),self.previous));self.primary.probe();self.companion.probe();transport_check();return True
    def envelope(self):
        return dict(iosSnapshotPhotosOwnerVersion=1,binding=self.binding,companionBinding=self.companion_binding,
            runId=self.run,fixtureUrl=self.fixture_url,companionArtifact=str(self.companion.artifact_path),payload=pack([self.state]))
    def save_state(self):
        self.guard();value=self.envelope();self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def inventory(self,reads):
        names={self.store.path.name}
        for slot in self.state['slots']:names.add(self.packet_store(slot).path.name)
        if self.state['input'] is not None:names.add(PhotosSaveInputs.store_name('primary'))
        for path in self.root.iterdir():
            if path.name.startswith('photos-save-'):need(path.name in names or path in reads)
        named={self.action(row,True).store.path for row in self.state['actions']}
        for path in self.companion_root.iterdir():
            if path.name.startswith('photos-normal-'):need(path in named or path in reads)
    def decode(self,value):
        exact(value,{'iosSnapshotPhotosOwnerVersion','binding','companionBinding','runId','fixtureUrl','companionArtifact','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosSnapshotPhotosOwnerVersion']) is int and value['iosSnapshotPhotosOwnerVersion']==1)
        state=rows[0];exact(state,set(self.state));prior=self.state;self.state=state
        try:
            need(same(value,self.envelope()) and type(state['slots']) is list and len(state['slots'])<=256
                and type(state['actions']) is list and len(state['actions'])<=1024 and type(state['handoffs']) is list and len(state['handoffs'])<=8
                and type(state['destination']) is list and len(state['destination'])<=32 and type(state['chunks']) is list and len(state['chunks'])<=512
                and type(state['photoQuiet']) is list and len(state['photoQuiet'])<=3 and type(state['fileQuiet']) is list and len(state['fileQuiet'])<=3)
            with read_scope(fresh=True) as reads:
                counts={};labels=set()
                for slot in state['slots']:
                    exact(slot,{'label','kind','index','sha256'});need(slot['kind'] in PACKETS and re.fullmatch('[a-z][a-z0-9-]{0,63}',slot['label']) and slot['label'] not in labels)
                    labels.add(slot['label']);counts[slot['kind']]=counts.get(slot['kind'],0)+1;need(slot['index']==counts[slot['kind']])
                    if self.packet_store(slot).read() is not None:
                        child=PACKETS[slot['kind']].history(self.packet_store(slot),self.lock,self.binding,self.run,'primary',slot['index'])
                        if slot['sha256'] is not None:need(digest(child.previous)==slot['sha256']);child.qualified()
                    else:need(slot['sha256'] is None)
                for index,row in enumerate(state['actions'],1):
                    exact(row,{'index','label','plan','before','after','sha256'});need(row['index']==index and row['label']==row['plan']['label']);clock(row['before'])
                    action=self.action(row,True)
                    if row['after'] is not None:clock(row['after'],row['before']);need(row['sha256']==digest(action.previous));action.original()
                    else:need(row['sha256'] is None)
                for index,row in enumerate(state['handoffs'],1):
                    exact(row,{'index','label','target','before','issued','after'});need(row['index']==index and row['target'] in ('primary','companion') and type(row['issued']) is bool)
                    if row['after'] is not None:need(row['issued']);self.handoff_original(row)
                if state['input'] is not None:
                    exact(state['input'],{'control','index','baseline'});need(state['input']['index']==1 and state['input']['control'] in controls.IDS and state['input']['control'].startswith('snapshot.save.'))
                    input_store=PrivateFeatureState(self.root/PhotosSaveInputs.store_name('primary'))
                    if input_store.read() is not None:
                        inputs=PhotosSaveInputs.history(input_store,self.lock,self.binding,self.run,'primary')
                        need(len(inputs.state['events'])<=1)
                        if inputs.state['events']:need(inputs.state['events'][0]['controlId']==state['input']['control'])
                if state['saved'] is not None:self.returned('read-client');need(same(self.proof(),state['saved']))
                if state['cleaned'] is not None:self.returned('cleanup-client');need(same(self.cleanup_proof(),state['cleaned']))
                self.inventory(reads)
        finally:self.state=prior
        return deepcopy(state)

    def capture(self):
        owner=IOSSnapshotCaptureOwner.archive(PrivateFeatureState(self.root/'ios-snapshot-primary-capture-owner.json'),self.lock,self.binding,self.run,self.fixture_url)
        result=owner.result();artifact=owner.history('artifact',owner.state['artifact']);fact,raw=artifact.originals()
        if self.state['capture'] is not None:
            need(self.state['capture']==dict(resultSha256=digest(result),artifactSha256=digest(artifact.previous),file=fact['file']))
        return owner,result,artifact,raw
    def packet_store(self,slot):
        cls=PACKETS[slot['kind']];return PrivateFeatureState(self.root/('photos-save-primary-'+cls._name+'-'+format(slot['index'],'04d')+'.json'))
    def packet(self,slot,historical=False):
        cls=PACKETS[slot['kind']];args=(self.packet_store(slot),self.lock,self.binding,self.run,'primary',slot['index'])
        if historical:return cls.history(*args)
        actual=self.primary.foreground_sources();native=actual['clock_source']
        if self.state['nativeTail'] is not None:restore(native,self.state['nativeTail'])
        return cls(*args,actual['observer'],native,self.guard,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
    def observed(self,label,kind):
        rows=[row for row in self.state['slots'] if row['label']==label]
        if rows:need(len(rows)==1 and rows[0]['kind']==kind);slot=rows[0]
        else:
            slot=dict(label=label,kind=kind,index=1+sum(row['kind']==kind for row in self.state['slots']),sha256=None)
            self.state['slots'].append(slot);self.save_state()
        child=self.packet(slot)
        if child.state is None:child.reserve()
        if child.state['phase']=='reserved':child.send()
        if child.state['phase']=='issued':child.retain()
        child.qualified();frame=child.historical()
        if slot['sha256'] is None:
            if self.state['nativeTail'] is not None:follow_native(self.state['nativeTail'],frame['acquisition']['nativeBefore'])
            self.state['nativeTail']=deepcopy(frame['acquisition']['nativeAfter']);slot['sha256']=digest(child.previous);self.save_state()
        else:need(slot['sha256']==digest(child.previous))
        return child
    def packet_original(self,label):
        rows=[row for row in self.state['slots'] if row['label']==label];need(len(rows)==1 and rows[0]['sha256'] is not None)
        child=self.packet(rows[0],True);need(digest(child.previous)==rows[0]['sha256']);child.qualified();return child.historical()['packet']
    def inputs(self,historical=False):
        store=PrivateFeatureState(self.root/PhotosSaveInputs.store_name('primary'))
        if historical:return PhotosSaveInputs.history(store,self.lock,self.binding,self.run,'primary')
        actual=self.primary.foreground_sources();return PhotosSaveInputs(store,self.lock,self.binding,self.run,'primary',actual['native'],self.guard)

    def next_label(self,prefix,*,actions=False):
        rows=[row for row in self.state['actions' if actions else 'slots'] if row['label'].startswith(prefix)]
        if rows and rows[-1]['sha256'] is None:return rows[-1]['label']
        return prefix+str(len(rows)+1)

    def handoff_original(self,row):
        before,after=row['before'],row['after'];need(type(before) is dict and type(after) is dict and set(before)==set(after)=={'primary','companion'})
        for role,binding in (('primary',self.binding),('companion',self.companion_binding)):
            fields={'binding','process','source'}|({'installed'} if role=='primary' and 'installed' in before[role] else set())
            exact(before[role],fields);exact(after[role],fields)
            for item in (before[role],after[role]):
                exact(item['process'],{'bundleId','pid','foreground'});process_source(item['source'])
                need(type(item['process']['pid']) is int and type(item['process']['foreground']) is bool
                    and item['process']['bundleId']==(self.primary if role=='primary' else self.companion).target['appId'])
            if 'installed' in fields:installed_forward(before[role]['installed'],after[role]['installed'])
            need(before[role]['binding']==after[role]['binding']==binding and before[role]['process']['pid']==after[role]['process']['pid']==int(binding['processIdentity'])
                and before[role]['source']==after[role]['source'])
        target=row['target'];other='companion' if target=='primary' else 'primary'
        need(before[target]['process']['foreground'] is False and before[other]['process']['foreground'] is True
            and after[target]['process']['foreground'] is True and after[other]['process']['foreground'] is False)
    def returned(self,label):
        rows=[row for row in self.state['handoffs'] if row['label']==label]
        need(len(rows)==1 and rows[0]['issued'] is True and rows[0]['after'] is not None and rows[0]['target']=='primary');self.handoff_original(rows[0])
    def handoff(self,label,target):
        rows=[row for row in self.state['handoffs'] if row['label']==label]
        if rows:row=rows[0];need(row['target']==target)
        else:
            before=dict(primary=self.primary.probe(),companion=self.companion.probe())
            row=dict(index=len(self.state['handoffs'])+1,label=label,target=target,before=before,issued=False,after=None)
            self.state['handoffs'].append(row);self.save_state()
        if row['after'] is not None:self.handoff_original(row);return
        selected=self.primary if target=='primary' else self.companion
        if not row['issued']:
            row['issued']=True;self.save_state();selected.activate()
        after=dict(primary=self.primary.probe(),companion=self.companion.probe());candidate=dict(row,after=after)
        try:self.handoff_original(candidate)
        except NativeUIError:raise SnapshotPhotosPending('Original Photos app activation is unresolved') from None
        row['after']=after;self.save_state()

    def action(self,row,historical=False):
        args=(self.companion_root,self.companion_lock,self.companion_binding,self.run,row['index'],row['plan'],lambda:True)
        if historical:return PhotosAction(*args,historical=True)
        runtime=self.companion.foreground_runtime()
        return PhotosAction(*args[:-1],self.guard,client=runtime.client,session=runtime.session,read=runtime.original_path,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
    def acted(self,label,control,file,fields,limit=262144):
        plan=dict(label=label,control=control,file=file,fields=[list(row) for row in fields],limit=limit)
        rows=[row for row in self.state['actions'] if row['label']==label]
        if rows:row=rows[0];need(row['plan']==plan)
        else:
            row=dict(index=len(self.state['actions'])+1,label=label,plan=plan,before=self.stamp(),after=None,sha256=None)
            self.state['actions'].append(row);self.save_state()
        action=self.action(row,row['after'] is not None)
        if row['after'] is not None:
            need(row['sha256']==digest(action.previous));return row,action.original()
        result=action.execute()
        if row['after'] is None:row['after']=self.stamp();row['sha256']=digest(action.previous);self.save_state()
        else:need(row['sha256']==digest(action.previous))
        return row,result
    def original_action(self,index):
        need(integer(index,1,len(self.state['actions'])));row=self.state['actions'][index-1];need(row['after'] is not None)
        action=self.action(row,True);need(row['sha256']==digest(action.previous));return action.original()
    def action_nonce(self,label,identifier):
        rows=[row for row in self.state['actions'] if row['label']==label]
        if rows:return dict(rows[0]['plan']['fields'])[identifier]
        return 'ios-'+uuid.uuid4().hex
    def companion_clock(self,label):
        nonce=self.action_nonce(label,'snapshot.companion.nonce')
        row,value=self.acted(label,'snapshot.companion.clock','snapshot-companion-clock.json',[('snapshot.companion.nonce',nonce)])
        previous=self.state['companionTail'];is_new=previous is None or value['sequence']>previous['sequence']
        companion_source.original(value,action='clock',nonce=nonce,pid=int(self.companion_binding['processIdentity']),bundle=self.companion.artifact['bundle']['bundleId'],previous=previous if is_new else None)
        if previous is not None:need(all(same(value[key],previous[key]) for key in ('instance','processId','bundleId','sourceBirthClock','role')))
        if is_new:self.state['companionTail']=deepcopy(value);self.save_state()
        return row,value
    def permission(self,label):
        _first,before=self.companion_clock(label+'-before');nonce=self.action_nonce(label,'snapshot.companion.nonce')
        row,value=self.acted(label,'snapshot.companion.photos','snapshot-companion-photos.json',[('snapshot.companion.nonce',nonce)])
        source.permission(value,nonce,pid=int(self.companion_binding['processIdentity']),bundle=self.companion.artifact['bundle']['bundleId'],previous=before)
        _last,after=self.companion_clock(label+'-after');companion_source.original(after,previous=value)
        need(after['clockAfter']['epochMs']-before['clockBefore']['epochMs']<1500 and after['clockAfter']['monotonicMs']-before['clockBefore']['monotonicMs']<1500)
        return row,value

    def active(self,ticket,verb):
        packet=self.phase.read(self.state['phaseOriginal'])['status'];phase_packet(packet,run=self.run,area='snapshots',request=packet['requestId'],epoch=packet['capturedEpochMs'])
        if self.state['phaseOriginal'] is None:
            previous=self.capture()[0].state['phaseOriginal']
            phase_packet(packet,run=self.run,area='snapshots',request=packet['requestId'],epoch=packet['capturedEpochMs'],previous=previous)
        need(packet['active'] and packet['activations'][-1]['ticket']==ticket and packet['activations'][-1]['stimulus']==dict(verb=verb,inputs={}))
        self.state['phaseOriginal']=deepcopy(packet);self.save_state();return packet
    def destination_original(self,index):
        value=self.original_action(index);destination.original(value);need(value['processId']==int(self.companion_binding['processIdentity']) and value['runId']==self.run)
        transaction=exports.photos_asset(self.packet_original(self.state['export']['label']),self.state['export']['id'])
        need(value['basename']==transaction['operation']['fileName'] and value['photosIdentifier']==transaction['photosIdentifier']
            and value['createdClock']['epochMs']>=transaction['nativeResult']['clock']['epochMs'])
        return value
    def inspect_destination(self,label):
        nonce=self.action_nonce(label,'snapshot.destination.query');file='snapshot-photos-'+self.run+'/photos-original.json'
        row,value=self.acted(label,'snapshot.destination.inspect',file,[('snapshot.destination.query',nonce)])
        previous=None if not self.state['destination'] else self.destination_original(self.state['destination'][-1])
        destination.original(value,previous if previous is None or row['index']!=self.state['destination'][-1] else None)
        need(value['queries'] and value['queries'][-1]['requestId']==nonce)
        self.destination_original(row['index'])
        if row['index'] not in self.state['destination']:self.state['destination'].append(row['index']);self.save_state()
        return row,value
    def proof(self):
        _capture,result,artifact,raw=self.capture();need(self.state['export'] is not None and self.state['destination'] and self.state['chunks'])
        original=self.destination_original(self.state['destination'][0]);chunks=[self.original_action(index) for index in self.state['chunks']]
        copied=source.original_bytes(chunks,original,int(self.companion_binding['processIdentity']));need(copied==raw)
        saved=destination.saved_original(original,self.packet_original(self.state['export']['label']),self.state['export']['id'],copied)
        image=inspect_snapshot(copied,mode='still',file_format='png');need(image['sha256']==result['image']['sha256'])
        return dict(iosSnapshotPhotosSavedVersion=1,savedOriginal=saved,image=image,hostOriginalRetained=True,
            photosCleanupRequired=True,captureCleanupRequired=True,independentWitnessRequired=True,wholeFeatureRequired=True)

    @operation
    def save(self,ticket):
        identifier(ticket);self.guard()
        if self.state['saved'] is not None:need(self.state['ticket']==ticket);self.primary.probe(True);return self.proof()
        if self.state['ticket'] is None:
            self.state['ticket']=ticket;capture,result,artifact,_raw=self.capture();fact,_raw=artifact.originals()
            self.state['capture']=dict(resultSha256=digest(result),artifactSha256=digest(artifact.previous),file=fact['file'])
            self.state['nativeTail']=deepcopy(capture.state['nativeTail']);self.state['device']=same_device(self.primary,self.companion);self.save_state()
        need(self.state['ticket']==ticket);self.active(ticket,'save')
        self.handoff('permission-companion','companion');self.permission('permission');self.handoff('permission-client','primary')
        if self.state['input'] is None:
            before=self.observed('save-before','exports');exports.drained(before.historical()['packet'])
            actual=self.primary.foreground_sources();view=controls.project(actual['native'].capture())
            rows=[row for row in view['controls'] if row['id'].startswith('snapshot.save.') and row['snapshotFileName']==self.state['capture']['file']['name']]
            need(len(rows)==1);self.state['input']=dict(control=rows[0]['id'],index=1,baseline='save-before');self.save_state()
        inputs=self.inputs(self.state['export'] is not None)
        if not inputs.state['events']:
            # The parent declaration precedes the child's durable reserve. A
            # restart in that gap may reserve once; no command has been issued.
            need(self.state['export'] is None)
            actual=self.primary.foreground_sources();view=controls.project(actual['native'].capture())
            rows=[row for row in view['controls'] if row['id']==self.state['input']['control']
                and row['snapshotFileName']==self.state['capture']['file']['name']]
            need(len(rows)==1);inputs.reserve(rows[0]['id'],view)
        need(len(inputs.state['events'])==1)
        if inputs.state['events'][0]['phase']=='reserved':self.active(ticket,'save');inputs.send()
        elif inputs.state['events'][0]['phase']=='issued':inputs.recover(self.observed('save-delivery','inputs').historical()['packet'])
        inputs.validate_original(1)
        if self.state['export'] is None:
            before=self.packet_original('save-before');old={row['id'] for row in before['source']['operations']}
            label=self.next_label('save-after-')
            after=self.observed(label,'exports').historical()['packet'];exports.validate(after,dict(schemaVersion=1,action=exports.ACTION,commandId=after['requestId'],runId=self.run),int(self.binding['processIdentity']),previous=before)
            rows=[row for row in after['source']['operations'] if row['id'] not in old]
            need(len(rows)==1 and rows[0]['action']=='save' and rows[0]['owned'] and rows[0]['fileName']==self.state['capture']['file']['name'])
            try:exports.photos_asset(after,rows[0]['id']);exports.drained(after)
            except NativeUIError:raise SnapshotPhotosPending('Original Photos Save has not completed and drained') from None
            self.state['export']=dict(id=rows[0]['id'],label=label);self.save_state()
        self.handoff('read-companion','companion')
        if not any(row['label']=='read' for row in self.state['actions']):self.permission('read-permission')
        transaction=exports.photos_asset(self.packet_original(self.state['export']['label']),self.state['export']['id'])
        self.acted('read','snapshot.destination.read','snapshot-photos-'+self.run+'/photos-original.json',
            [('snapshot.destination.run',self.run),('snapshot.destination.asset',transaction['photosIdentifier']),('snapshot.destination.basename',transaction['operation']['fileName'])])
        if not self.state['destination']:
            row,original=self.inspect_destination(self.next_label('read-inspect-',actions=True))
            try:
                need(original['phase']=='complete' and any(event['kind']=='weak-expired' for event in original['events'])
                    and original['queries'][-1]['operationAlive'] is False and original['queries'][-1]['assetPresent'] is True and original['queries'][-1]['authorization']==3)
            except NativeUIError:
                self.state['destination'].remove(row['index']);self.save_state();raise SnapshotPhotosPending('Original Photos resource read remains pending') from None
        original=self.destination_original(self.state['destination'][0]);need(original['iosSnapshotDestinationVersion']>=2)
        for offset in range(0,original['byteCount'],source.CHUNK_BYTES):
            label='chunk-'+str(offset//source.CHUNK_BYTES+1);nonce=self.action_nonce(label,'snapshot.destination.query')
            row,value=self.acted(label,'snapshot.destination.chunk','snapshot-photos-chunk.json',
                [('snapshot.destination.query',nonce),('snapshot.destination.offset',str(offset))],source.CHUNK_LIMIT)
            part=offset//source.CHUNK_BYTES;previous=None if part==0 else self.original_action(self.state['chunks'][part-1])
            source.chunk(value,nonce,offset,original,pid=int(self.companion_binding['processIdentity']),previous=previous)
            if len(self.state['chunks'])>part:need(self.state['chunks'][part]==row['index'])
            else:need(len(self.state['chunks'])==part);self.state['chunks'].append(row['index']);self.save_state()
        proof=self.proof();self.handoff('read-client','primary');self.primary.foreground_sources()
        self.state['saved']=proof;self.save_state();return deepcopy(proof)

    def quiet(self,indices,*,files=False):
        need(len(indices)==3);rows=[self.state['actions'][index-1] for index in indices]
        need(rows[-1]['before']['epochMs']-rows[0]['after']['epochMs']>=3000 and rows[-1]['before']['monotonic']-rows[0]['after']['monotonic']>=3)
        originals=[self.original_action(index) for index in indices]
        if files:
            for at,(value,row) in enumerate(zip(originals,rows)):
                native=self.destination_original(self.state['retireOriginal']);raw=self.action(self.state['actions'][self.state['retireOriginal']-1],True).original_bytes()
                source.retirement(value,dict(row['plan']['fields'])['snapshot.destination.query'],native,raw,pid=int(self.companion_binding['processIdentity']),previous=None if at==0 else originals[at-1])
                need(value['receipt']['phase']=='complete')
            first,last=originals[0]['clockAfter'],originals[-1]['clockBefore']
        else:
            _capture,_result,_artifact,raw=self.capture();packet=self.packet_original(self.state['export']['label'])
            for value in originals:destination.photos_absent(value,packet,self.state['export']['id'],raw)
            first,last=originals[0]['queries'][-1]['clock'],originals[-1]['queries'][-1]['clock']
        need(last['epochMs']-first['epochMs']>=3000 and last['monotonicMs']-first['monotonicMs']>=3000)
        return dict(nativeMilliseconds=last['epochMs']-first['epochMs'],hostMilliseconds=rows[-1]['before']['epochMs']-rows[0]['after']['epochMs'])
    def cleanup_proof(self):
        return dict(iosSnapshotPhotosCleanupVersion=1,saved=self.proof(),photoQuiet=self.quiet(self.state['photoQuiet']),
            fileQuiet=self.quiet(self.state['fileQuiet'],files=True),photosAssetAbsent=True,companionRunFilesAbsent=True,
            hostOriginalRetained=True,captureCleanupRequired=True,pairedCleanupRequired=True,wholeFeatureRequired=True)

    @operation
    def cleanup(self):
        self.guard();need(self.state['saved'] is not None)
        if self.state['cleaned'] is not None:self.primary.probe(True);return self.cleanup_proof()
        self.handoff('cleanup-companion','companion');self.permission('cleanup-permission')
        nonce=self.action_nonce('delete','snapshot.destination.query')
        self.acted('delete','snapshot.destination.delete','snapshot-photos-'+self.run+'/photos-original.json',[('snapshot.destination.query',nonce)])
        while len(self.state['photoQuiet'])<3:
            if self.state['photoQuiet']:self.sleep(1.6)
            label=self.next_label('delete-inspect-',actions=True)
            row,value=self.inspect_destination(label)
            _capture,_result,_artifact,raw=self.capture()
            try:destination.photos_absent(value,self.packet_original(self.state['export']['label']),self.state['export']['id'],raw)
            except NativeUIError:raise SnapshotPhotosPending('Original Photos deletion/confirmation remains pending') from None
            self.state['photoQuiet'].append(row['index']);self.save_state()
        self.quiet(self.state['photoQuiet']);self.state['retireOriginal']=self.state['photoQuiet'][-1];self.save_state()
        while len(self.state['fileQuiet'])<3:
            if self.state['fileQuiet']:self.sleep(1.6)
            first=not self.state['fileQuiet'];label='retire' if first else 'retire-inspect-'+str(len(self.state['fileQuiet']))
            nonce=self.action_nonce(label,'snapshot.destination.query');row,value=self.acted(label,
                'snapshot.destination.retire' if first else 'snapshot.destination.retire-inspect','snapshot-photos-retire.json',[('snapshot.destination.query',nonce)],16384)
            original=self.destination_original(self.state['retireOriginal']);raw=self.action(self.state['actions'][self.state['retireOriginal']-1],True).original_bytes()
            source.retirement(value,nonce,original,raw,pid=int(self.companion_binding['processIdentity']));need(value['receipt']['phase']=='complete')
            self.state['fileQuiet'].append(row['index']);self.save_state()
        proof=self.cleanup_proof();self.handoff('cleanup-client','primary');self.primary.foreground_sources()
        self.observed('cleanup-exports','exports');exports.drained(self.packet_original('cleanup-exports'))
        self.state['cleaned']=proof;self.save_state();return deepcopy(proof)
