"""Original retirement of interrupted Emote GPU/image acquisitions.

An incomplete PNG is never published or deleted here. Original host inode,
partial bytes, issued capture, actual GPU retirement and phase/clock originals
are retained. A new image read always receives a new request identity.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import uuid
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,integer,need
from adapters.native_vulkan_world_frame import command,storage,absent,PNG_LIMIT
from adapters.normal_feature_state import PrivateFeatureState
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.original_marker_restoration_frames import owns_slot
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.phase_fixture import validate as phase_packet
from feature_journeys.contract import identifier
from ios.adapters.emote_native_prefix import follow as native_prefix
from ios.adapters.graphics_history import restore_native

VERSION=1


def retained_file(owner,root,binding,run,role,request,lock):
    """Validate an original owner and its real possibly incomplete host file."""
    class Archive(PrivateFeatureState):
        def read(self):return deepcopy(owner)
        def write(self,*_):need(False)
        def discard(self,*_):need(False)
    scope=VulkanWorldFrameOwner(Archive(lock.path.with_name('graphics-world-frame-'+role+'-0-'+request[4:]+'.json')),
        root,binding,run,role,0,request,lambda *_:need(False),lambda:True,source_lock=lock)
    scope._load();need(owns_slot(scope.state) and scope.state['phase']=='released' and absent(scope.state['absence']))
    path=Path(root)/scope.name
    if scope.state['file'] is None:need(not path.exists());return None
    descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(descriptor,'rb') as stream:
        scope._file(stream.fileno());raw=stream.read(PNG_LIMIT+1);scope._file(stream.fileno())
    need(len(raw)<=PNG_LIMIT);frame=scope.state['frame']
    if frame is None:need(not raw)
    else:
        expected=frame['source']['image'];need(len(raw)<=expected['bytes'])
        if len(raw)==expected['bytes']:need(hashlib.sha256(raw).hexdigest()==expected['sha256'])
    return dict(identity=deepcopy(scope.state['file']),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def validate_abandonment(sample,*,root,binding,run,role,lock):
    """Historical only: no native reader, live SDK, input or fresh envelope."""
    from ios.adapters.emote_samples import READS
    from ios.adapters.avatar_state import session
    exact(sample,{'iosEmoteSampleVersion','runId','role','binding','requestId','ticket','avatarId','phase','payload','owner'})
    need(type(sample['iosEmoteSampleVersion']) is int and sample['iosEmoteSampleVersion'] in READS and sample['runId']==run
        and sample['role']==role and same(sample['binding'],binding) and type(sample['requestId']) is str and sample['requestId'].startswith('ios-'))
    identifier(sample['requestId'][4:]);identifier(sample['ticket'])
    if sample['avatarId'] is not None:session(sample['avatarId'])
    lock.assert_held();need(sample['phase']=='abandoned')
    frames=unpack(sample['payload']);owners=unpack(sample['owner']);need(len(frames)==len(owners)==1)
    frame,owner=frames[0],owners[0]
    exact(frame,{'iosEmoteAbandonedSampleVersion','priorCursors','phaseBefore','phaseAfter','clockJoin','absence','partialFile','inspection'})
    need(type(frame['iosEmoteAbandonedSampleVersion']) is int and frame['iosEmoteAbandonedSampleVersion']==VERSION)
    exact(frame['priorCursors'],{'native','world','renderers'})
    proof=frame['absence'];join=validate_join(frame['clockJoin'],dict(absence=proof));pid=int(binding['processIdentity'])
    native_prefix(join['nativeBefore'],join['nativeAfter'])
    need(join['nativeBefore']['processId']==join['nativeAfter']['processId']==pid
        and proof['requestId']==sample['requestId'] and absent(proof))
    first,last=frame['phaseBefore'],frame['phaseAfter']
    for packet,epoch in ((first,join['hostBeforeEpochMs']),(last,join['hostAfterEpochMs'])):
        phase_packet(packet,run=run,area='emotes',request=packet['requestId'],epoch=epoch)
    phase_packet(last,run=run,area='emotes',request=last['requestId'],epoch=join['hostAfterEpochMs'],previous=first)
    need(first['active']==last['active'] and same(first['activations'],last['activations'])
        and any(row['ticket']==sample['ticket'] for row in last['activations'])
        and join['nativeBefore']['capturedEpochMs']<=proof['requestedEpochMs']<=proof['capturedEpochMs']<=join['nativeAfter']['capturedEpochMs'])
    if frame['priorCursors']['native'] is not None:native_prefix(frame['priorCursors']['native'],join['nativeBefore'])
    if owner is None:
        need(frame['partialFile'] is None and frame['inspection'] is not None)
        row=frame['inspection'];exact(row,{'command','receipt'});command(row['command'])
        need(row['command']['operation'] in ('inspect','release') and same(row['receipt'],proof))
        storage(proof,row['command'],pid,join['nativeAfter']['capturedEpochMs'])
        path=Path(root)/('vulkan-world-'+run+'-'+role+'-0-'+sample['requestId'][4:]+'.png');need(not path.exists())
    else:
        need(frame['inspection'] is None and same(owner['absence'],proof)
            and same(frame['partialFile'],retained_file(owner,root,binding,run,role,sample['requestId'],lock)))
    return deepcopy(frame)


class IOSEmoteSampleRecovery:
    def __init__(self,samples):
        from ios.adapters.emote_samples import IOSEmoteSamples
        need(isinstance(samples,IOSEmoteSamples));self.samples=samples
        self.store=PrivateFeatureState(samples.store.path.with_name('ios-emote-'+samples.role+'-sample-recovery.json'))
        self.previous=self.store.read();self.state=dict(records=[],pending=None)
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):
        s=self.samples
        return dict(iosEmoteSampleRecoveryVersion=VERSION,runId=s.run,role=s.role,binding=s.binding,artifactRoot=str(s.root),payload=pack([state]))

    def bound(self):self.samples.bound();need(same(self.store.read(),self.previous))

    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def decode(self,value):
        exact(value,{'iosEmoteSampleRecoveryVersion','runId','role','binding','artifactRoot','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'records','pending'});need(type(state['records']) is list and len(state['records'])<=128)
        for row in state['records']:
            exact(row,{'requestId','sampleSha256'});matches=[r for r in self.samples.state['rows'] if r['requestId']==row['requestId']]
            need(len(matches)==1 and matches[0]['phase']=='abandoned' and matches[0]['sampleSha256']==row['sampleSha256'])
            self.samples.record(matches[0])
        pending=state['pending']
        if pending is not None:
            exact(pending,{'row','priorOwner','attempts','sample','reference'})
            need(type(pending['attempts']) is list and len(pending['attempts'])<=16 and pending['row']['phase']=='reserved')
            need(pending['priorOwner']['binding']==self.samples.binding)
            for attempt in pending['attempts']:
                exact(attempt,{'phaseBefore','started','inspection','absence','owner','partialFile','clockJoin','phaseAfter'})
                inspection=attempt['inspection']
                if inspection is not None:
                    exact(inspection,{'command','receipt'});command(inspection['command'])
                    need(inspection['command']['requestId']==pending['row']['requestId'] and inspection['command']['operation'] in ('inspect','release'))
                    if inspection['receipt'] is not None:need(absent(inspection['receipt']))
            if pending['sample'] is not None:
                validate_abandonment(pending['sample'],root=self.samples.root,binding=self.samples.binding,
                    run=self.samples.run,role=self.samples.role,lock=self.samples.lock)
            if pending['reference'] is not None:
                need(pending['sample'] is not None and same(self.samples.sample_store(pending['row']).read(),pending['sample'])
                    and pending['reference']==digest(pending['sample']))
        return deepcopy(state)

    def inspect_unused(self,attempt,row,live):
        s=self.samples;need(s.owner(row).store.read() is None and not (s.root/s.owner(row).name).exists())
        def intent(query):
            command(query);need(query['requestId']==row['requestId'] and query['operation'] in ('inspect','release') and attempt['inspection'] is None)
            attempt['inspection']=dict(command=deepcopy(query),receipt=None);self.save()
        def receipt(query,value):
            need(same(attempt['inspection']['command'],query) and attempt['inspection']['receipt'] is None and absent(value))
            attempt['inspection']['receipt']=deepcopy(value);self.save()
        reader=live['observer'].vulkan_world_frame(intent,receipt)
        issued=any(item['inspection'] is not None and item['inspection']['command']['operation']=='release'
            for item in self.state['pending']['attempts'])
        query=dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='inspect' if issued else 'release',
            commandId='ios-'+uuid.uuid4().hex,requestId=row['requestId'])
        return reader.perform(query)

    def recover(self):
        self.bound();s=self.samples;pending=self.state['pending']
        if pending is None:
            if s.state['phase']=='ready':return True
            need(s.state['phase']=='reading' and s.state['rows'] and s.state['rows'][-1]['phase']=='reserved'
                and len(self.state['records'])<128)
            pending=dict(row=deepcopy(s.state['rows'][-1]),priorOwner=deepcopy(s.previous),attempts=[],sample=None,reference=None)
            self.state['pending']=pending;self.save()
        row=pending['row']
        if pending['sample'] is None:
            need(s.state['phase']=='reading' and same(s.state['rows'][-1],row) and len(pending['attempts'])<16)
            live=s.runtime._sources(s.selector);need(same(live['binding'],s.binding))
            native=live['observer'].bound_native_observer(live['clock_source']);restore_native(native,s.state['cursors']['native'])
            phase=s.phase.status();attempt=dict(phaseBefore=phase,started=None,inspection=None,absence=None,owner=None,
                partialFile=None,clockJoin=None,phaseAfter=None)
            pending['attempts'].append(attempt);self.save()
            window=NativeClockAcquisition(native,epoch_ms=s.epoch_ms,monotonic=s.monotonic);window.begin(phase['capturedEpochMs'])
            attempt['started']=deepcopy(window.started);self.save()
            owner=s.owner(row)
            if owner.store.read() is not None:
                need(owns_slot(owner.store.read()));proof=owner.release();attempt['owner']=deepcopy(owner.store.read())
                attempt['partialFile']=retained_file(attempt['owner'],s.root,s.binding,s.run,s.role,row['requestId'],s.lock)
            else:proof=self.inspect_unused(attempt,row,live)
            need(absent(proof));attempt['absence']=deepcopy(proof);self.save()
            attempt['clockJoin']=window.finish(dict(absence=proof),[('absence','capturedEpochMs')]);self.save()
            attempt['phaseAfter']=s.phase.status(phase);self.save()
            prior=unpack(pending['priorOwner']['payload'])[0]['cursors']
            frame=dict(iosEmoteAbandonedSampleVersion=VERSION,priorCursors=deepcopy(prior),phaseBefore=phase,phaseAfter=attempt['phaseAfter'],
                clockJoin=attempt['clockJoin'],absence=proof,partialFile=attempt['partialFile'],inspection=attempt['inspection'])
            from ios.adapters.emote_samples import VERSION as SAMPLE_VERSION
            sample=dict(iosEmoteSampleVersion=SAMPLE_VERSION,runId=s.run,role=s.role,binding=s.binding,requestId=row['requestId'],ticket=row['ticket'],
                avatarId=row['avatarId'],phase='abandoned',payload=pack([frame]),owner=pack([attempt['owner']]))
            validate_abandonment(sample,root=s.root,binding=s.binding,run=s.run,role=s.role,lock=s.lock)
            pending['sample']=sample;self.save()
        sample=pending['sample'];store=s.sample_store(row);saved=store.read()
        if saved is None:store.write(sample,None)
        else:need(same(saved,sample))
        pending['reference']=digest(sample);self.save()
        frame=unpack(sample['payload'])[0]
        if s.state['phase']=='reading':
            need(same(s.state['rows'][-1],row));s.state['rows'][-1].update(phase='abandoned',sampleSha256=pending['reference'])
            s.state['cursors']['native']=deepcopy(frame['clockJoin']['nativeAfter']);s.state['phase']='ready';s.save()
        need(s.state['rows'][-1]['phase']=='abandoned' and s.state['rows'][-1]['sampleSha256']==pending['reference'])
        self.state['records'].append(dict(requestId=row['requestId'],sampleSha256=pending['reference']));self.state['pending']=None;self.save()
        return True
