"""Fresh original stereo return pixels and actual shared capture retirement.

A decoded two-eye frame is not Snapshot scene/challenge or whole acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import os
import stat
from adapters.native_feature_observation import decode,exact,need,integer,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_stereo_retirement import OriginalStereoRetirement
from adapters.owned_world_render import OwnedWorldRenderCapture,WorldRenderOwner
from adapters.graphics_journey.originals import GraphicsOriginals,record as image_record,transition as image_transition
from adapters.graphics_journey.samples import retirement
from adapters.pico4.snapshot_background_owner import PicoSnapshotBackgroundOwner
from adapters.pico4.snapshot_upload_originals import SnapshotUploadOriginals
from adapters.pico4.snapshot_upload_frame import validate as frame_packet,clocks
from adapters.pico4.snapshot_upload_owner import sha,provider_phase
from adapters.pico4.snapshot_originals import accept as native_accept
from adapters.pico4.snapshot_script_originals import accept as script_accept
from adapters.pico4.snapshot_capture_source import continuity as file_accept
from adapters.pico4.snapshot_upload_source import continuity as upload_accept
from adapters.pico4.snapshot_upload_fixture import validate as provider_packet
from adapters.native_account_observation import accept as account_accept
from adapters.script_journey.history import pack,unpack,canonical
from adapters.world_render_evidence import validate as capture_packet,original_pixels
from feature_journeys.contract import typed_equal,json_document

VERSION=1
PHASES=('ready','acquiring','framed','saved','retiring','complete')


class SnapshotReturnImageOriginals(SnapshotUploadOriginals):
    VERSION_KEY='snapshotReturnImageOriginalsVersion'
    VERBS=('return-image-primary','return-image-actor')


class PicoSnapshotReturnImage(OriginalStereoRetirement):
    def __init__(self,parent,path,artifact_root,capture_factory,*,role,monotonic=time.monotonic):
        need(isinstance(parent,PicoSnapshotBackgroundOwner) and role in ('primary','actor')
            and all(callable(f) for f in (capture_factory,monotonic)))
        self.parent,self.run,self.binding,self.lock,self.source=parent,parent.run,deepcopy(parent.binding),parent.lock,parent.source
        self.role,self.capture_factory,self.monotonic=role,capture_factory,monotonic
        self.store=PrivateFeatureState(path);need(self.store.path==self.lock.path.with_name('snapshot-return-image-'+role+'.json'))
        self.disk=self.state=self.anchor=self.state_sha=None;self.deadline=self.clock=None
        with self.lock.held():
            parent.load();need(parent.state['stage']=='partial-ready');self.parent_disk=deepcopy(parent.disk);self.parent_state=deepcopy(parent.state)
            self.parent_sha=sha(self.parent_disk);self.parent_state_sha=sha(self.parent_state)
            self.originals=SnapshotReturnImageOriginals(self.lock.path.with_name('snapshot-return-image-'+role+'-originals.json'),self.run,self.binding,'return-image-'+role)
            self.images=GraphicsOriginals(artifact_root,self.binding,self.run,role,0,self.guard,self.image_intent,monotonic=monotonic)
            self.load()

    def bound(self):
        self.parent.bound();need(sha(self.parent_disk)==self.parent_sha and sha(self.parent_state)==self.parent_state_sha
            and typed_equal(self.parent_disk,self.parent.store.read()) and typed_equal(self.parent.state,self.parent_state))
        for row in (self.parent_disk,self.parent_state):need(typed_equal(row,json_document(canonical(row))))
        self.parent.originals.verify()
        if self.state is not None:
            need(typed_equal(self.store.read(),self.disk) and sha(self.state)==self.state_sha
                and typed_equal(self.state,json_document(canonical(self.state))));self.originals.verify()
            if self.state['image'] is not None and self.state['image']['phase']=='saved':need(self.state['imageStamp']==self.file_stamp(self.state['image']))
        return self.monotonic()

    def now(self):
        now=self.bound();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.deadline is None or now<=self.deadline));self.clock=now;return now

    def guard(self):
        self.now();need(self.parent.status()['foreground']);owner=self.parent.live();need(owner.native.guard() is not False);self.now();return True

    def validate(self,state):
        exact(state,{'phase','parentSha256','ticket','frames','captureIntent','frame','image','imageStamp','memory','files','owner','proof','received'})
        need(state['phase'] in PHASES and state['parentSha256']==self.parent_sha and state['ticket']==self.parent_state['source']['activations'][-1]['ticket']
            and state['received'] is None and type(state['frames']) is list and len(state['frames'])<=8)
        for index,row in enumerate(state['frames']):
            self.parent.frame(row,returned=True);provider_phase(row['provider'],self.parent_state['source'])
            if index:
                old=state['frames'][index-1];need(row['hostMonotonic']>=old['hostMonotonic'])
                a=frame_packet(old,self.run,self.parent.pid,self.binding['sessionId']);b=frame_packet(row,self.run,self.parent.pid,self.binding['sessionId'])
                native_accept(a[0],b[0]);script_accept(a[1],b[1]);file_accept(a[2],b[2]);upload_accept(a[3],b[3]);account_accept(a[4]['account']['observation'],b[4]['account'])
                need(b[4]['instance']==a[4]['instance'] and b[4]['sequence']>a[4]['sequence'] and b[4]['requestId']!=a[4]['requestId'])
                provider_packet(row['provider'],self.run,row['provider']['requestId'],row['provider']['capturedEpochMs'],previous=old['provider'])
        if state['phase']!='ready':need(state['captureIntent'] is not None)
        if state['phase']=='ready':need(all(state[key] is None for key in ('captureIntent','frame','image','memory','files','owner','proof')) and len(state['frames'])<=1)
        if state['phase']=='acquiring':need(state['frame'] is None and state['image'] is None and len(state['frames'])==1)
        if state['phase'] in ('framed','saved','retiring','complete'):need(state['frame'] is not None)
        if state['captureIntent'] is not None:WorldRenderOwner.acquisition(state['captureIntent']);need(state['phase']!='ready' and state['frames'])
        if state['frame'] is not None:
            exact(state['frame'],{'capture'});capture=state['frame']['capture'];need(state['captureIntent'] is not None and len(state['frames'])>=1)
            capture_packet(capture,state['captureIntent']['commandId'],self.parent.pid,capture['capturedEpochMs'],stereo=True,require_cameras=True)
            before=state['frames'][0];need(capture['requestedEpochMs']>=max(clocks(before)[1:]) and capture['source']['capturedEpochMs']>=min(clocks(before)[1:]))
            if len(state['frames'])>=2:need(min(clocks(state['frames'][1])[1:])>=capture['capturedEpochMs'])
        need(state['imageStamp'] is None or type(state['imageStamp']) is list and len(state['imageStamp'])==9 and all(type(value) is int and value>=0 for value in state['imageStamp']))
        if state['image'] is not None:
            image_record(state['image']);image=state['image']
            need(image['binding']==self.binding and image['runId']==self.run and image['role']==self.role and image['stage']==0
                and image['ticket']==state['ticket'] and image['kind']=='image' and state['frame'] is not None and typed_equal(image['capture'],state['frame']['capture']))
            if image['phase']=='saved':
                need(state['imageStamp']==self.file_stamp(image));original_pixels(state['frame']['capture'],GraphicsOriginals.archive(self.images.root,image));need(state['imageStamp']==self.file_stamp(image))
            else:need(state['imageStamp'] is None)
        else:need(state['imageStamp'] is None)
        if state['proof'] is not None:
            retirement(state['proof'],state['proof']['owner'],self.parent.pid,self.binding,self.role)
            need(state['frame'] is not None and state['proof']['memory']['instance']==state['frame']['capture']['instance']
                and state['proof']['memory']['capturedEpochMs']>=state['frame']['capture']['capturedEpochMs']
                and state['proof']['owner']['capture']==state['captureIntent'] and state['memory']==state['proof']['memory']
                and state['owner']==state['proof']['owner'] and state['files']==dict(remove=state['proof']['files']['removed'],inspect=state['proof']['files']['absent']))
        if state['phase'] in ('saved','retiring','complete'):need(state['image'] is not None and state['image']['phase']=='saved' and len(state['frames'])>=2)
        if state['phase']=='complete':need(state['proof'] is not None and len(state['frames'])>=3)

    def load(self):
        self.bound();disk=self.store.read();need(self.disk is None or typed_equal(self.disk,disk))
        if disk is None:need(self.state is None);self.originals.verify();return
        exact(disk,{'snapshotReturnImageVersion','runId','binding','role','artifactRoot','payload'})
        need(type(disk['snapshotReturnImageVersion']) is int and disk['snapshotReturnImageVersion']==VERSION and disk['runId']==self.run
            and typed_equal(disk['binding'],self.binding) and disk['role']==self.role and disk['artifactRoot']==str(self.images.root))
        rows=unpack(disk['payload']);need(len(rows)==1);state=self.originals.decode(rows[0]);self.validate(state);self.disk,self.state=deepcopy(disk),state;self.state_sha=sha(state);self.bound()

    def save(self,state):
        self.now();need(typed_equal(self.store.read(),self.disk));self.validate(state)
        disk=dict(snapshotReturnImageVersion=VERSION,runId=self.run,binding=self.binding,role=self.role,artifactRoot=str(self.images.root),payload=pack([self.originals.encode(state)]))
        self.store.write(disk,self.disk);need(typed_equal(self.store.read(),disk));self.disk,self.state=deepcopy(disk),state;self.state_sha=sha(state);self.bound()

    def file_stamp(self,image):
        info=(self.images.root/image['name']).lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600 and info.st_size==image['bytes'])
        return [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns]

    def image_intent(self,image):
        image_transition(self.state['image'],image);state=deepcopy(self.state);state['image']=image
        if image['phase']=='saved':state['imageStamp']=self.file_stamp(image)
        self.save(state)

    def observe(self):
        need(self.parent.status()['foreground']);owner=self.parent.live();started=self.now();requested=owner.native.clock_ms();row=owner.read_frame();self.parent.frame(row,returned=True)
        state=deepcopy(self.state);state['frames'].append(row);self.save(state)
        need(owner.native.guard() is not False);epoch=owner.native.clock_ms();completed=self.now();captured=min(clocks(row)[1:])
        need(-250<=epoch-captured and max(epoch-captured,requested-captured+(completed-started)*1000)<=1500)
        self.anchor=(started,requested,captured);return owner

    def fence(self,owner):
        need(self.anchor is not None);started,requested,captured=self.anchor;self.bound();need(owner.native.guard() is not False)
        phase_started=self.now();phase_requested=self.source.epoch_ms();current=self.source.status(self.parent_state['source'])
        need(current['active'] and all(typed_equal(current[key],self.parent_state['source'][key]) for key in ('instance','createdEpochMs','activations')))
        native=owner.native.clock_ms();epoch=self.source.epoch_ms();completed=self.now()
        need(number(native,1,1e15) and number(epoch,phase_requested,1e15) and -250<=native-captured and -250<=epoch-current['capturedEpochMs']
            and max(native-captured,requested-captured+(completed-started)*1000,epoch-current['capturedEpochMs'],phase_requested-current['capturedEpochMs']+(completed-phase_started)*1000)<=1500)

    def image_bytes(self):
        with self.lock.held():
            self.load();need(self.state is not None and self.state['image'] is not None and self.state['image']['phase']=='saved')
            return self.images.read(self.state['image'])

    def acquire(self):
        with self.lock.held():
            need(self.deadline is None);self.deadline=self.now()+20
            try:return self.execute()
            finally:self.deadline=None

    def execute(self):
        self.load()
        if self.state is None:
            self.save(dict(phase='ready',parentSha256=self.parent_sha,ticket=self.parent_state['source']['activations'][-1]['ticket'],frames=[],
                captureIntent=None,frame=None,image=None,imageStamp=None,memory=None,files=None,owner=None,proof=None,received=None))
        if self.state['phase']=='complete':self.image_bytes();return self.report()
        need(self.parent.status()['foreground']);owned=self.capture_factory();need(isinstance(owned,OwnedWorldRenderCapture) and owned.owner.role==self.role and owned.capture.stereo
            and owned.capture.require_cameras and typed_equal(owned.owner.binding,self.binding) and owned.source_lock is self.lock)
        if self.state['captureIntent'] is not None:
            # No cold acquisition resend; only a saved original may finish its
            # own concrete retirement. Lost acquisition/partial copy stay owned.
            need(self.state['image'] is not None and self.state['image']['phase']=='saved')
            if len(self.state['frames'])<2:
                owner=self.observe();self.fence(owner);state=deepcopy(self.state);state['phase']='saved';self.save(state)
            if self.state['proof'] is None or owned.owner.store.read() is not None:self.retire(owned)
        else:
            need(owned.owner.store.read() is None);owner=self.observe();self.fence(owner);original=owned.capture.intent
            def remember(command):
                state=deepcopy(self.state);state['phase']='acquiring';state['captureIntent']=deepcopy(command);self.save(state);self.fence(owner);original(command)
            owned.capture.intent=remember
            capture,raw=owned.read(0);state=deepcopy(self.state);state['frame']=dict(capture=capture);state['phase']='framed';self.save(state)
            self.images.write(self.state['ticket'],capture,raw);owner=self.observe();self.fence(owner)
            state=deepcopy(self.state);state['phase']='saved';self.save(state);self.retire(owned)
        owner=self.observe();state=deepcopy(self.state);state['phase']='complete';self.save(state);result=self.report();self.fence(owner);return result

    def report(self):
        return dict(qualification='PICO_SNAPSHOT_ORIGINAL_STEREO_RETURN_COMPONENT_ONLY',complete=self.state['phase']=='complete',
            fullSnapshotRecipe=False,deviceAcceptance=False,sceneChallengeVerified=False,journalRetained=True,
            originalStereoReturnPng=self.state['phase']=='complete',captureMemoryAndReceiptsRetired=self.state['proof'] is not None)
