"""Durable original two-eye capture at independently observed navigation arrival.

Reuses the actual Pico world-render owner, original file writer and complete
native receipt retirement. This is source provenance, not challenge/pixel proof
of the full Navigation feature.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.navigation_arrival import pose_packet,stereo_frame,STEREO_VERSION as SOURCE_VERSION
from adapters.graphics_journey.originals import GraphicsOriginals,record as image_record,transition as image_transition
from adapters.graphics_journey.samples import retirement
from adapters.owned_world_render import OwnedWorldRenderCapture
from adapters.script_journey.history import pack,unpack
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.contract import identifier

from adapters.original_stereo_retirement import OriginalStereoRetirement

VERSION=2

class NavigationStereo(OriginalStereoRetirement):
    def __init__(self,arrival,capture_factory,path,artifact_root,run,binding,lock,guard,*,role='primary',journal_id=None,ui_factory=None,native_factory=None,monotonic=time.monotonic):
        context(binding);identifier(run)
        need(isinstance(lock,ScriptSourceLock) and all(callable(f) for f in (capture_factory,guard,monotonic)) and role in ('primary','actor'))
        self.arrival,self.capture_factory,self.run,self.binding,self.lock,self.guard=arrival,capture_factory,run,deepcopy(binding),lock,guard
        if journal_id is not None:identifier(journal_id)
        need(ui_factory is None or callable(ui_factory));self.ui_factory=ui_factory
        need(native_factory is None or callable(native_factory));self.native_factory=native_factory
        self.journal_id=journal_id
        self.role,self.monotonic=role,monotonic;self.store=PrivateFeatureState(path);self.disk=self.store.read();self.state=None
        self.images=GraphicsOriginals(artifact_root,binding,run,role,0,guard,self.image_intent,monotonic=monotonic)
        if self.disk is not None:
            version=self.disk.get('navigationStereoOwnerVersion')
            exact(self.disk,{'navigationStereoOwnerVersion','runId','binding','role','artifactRoot','payload'}|({'journalId'} if version==2 else set()))
            need(type(version) is int and version in (1,2) and self.disk.get('journalId')==journal_id
                 and self.disk['runId']==run and self.disk['binding']==binding and self.disk['role']==role
                 and self.disk['artifactRoot']==str(self.images.root))
            rows=unpack(self.disk['payload']);need(len(rows)==1);self.validate(rows[0]);self.state=rows[0]
        if journal_id is not None:
            from feature_journeys.stereo_navigation_evidence import original_name
            need(self.store.path.parent==self.images.root and self.store.path.name==original_name(run,role,journal_id))
        self.deadline=self.clock=None
    def now(self):
        self.lock.assert_held();need(self.guard() is not False);value=self.monotonic()
        need(number(value,0,1e15) and (self.clock is None or value>=self.clock) and (self.deadline is None or value<=self.deadline))
        self.clock=value;return value
    def validate(self,value):
        exact(value,{'ticket','phase','before','captureIntent','frame','image','memory','files','owner','proof'})
        identifier(value['ticket']);need(value['phase'] in ('ready','acquiring','framed','saved','retiring','complete'))
        if value['before'] is not None:pose_packet(value['before'],self.run,self.binding,self.arrival.scene_url,value['before']['subject']['capturedEpochMs'])
        if value['captureIntent'] is not None:
            from adapters.owned_world_render import WorldRenderOwner
            WorldRenderOwner.acquisition(value['captureIntent']);need(value['phase']!='ready')
        if value['frame'] is not None:
            frame=value['frame'];exact(frame,{'navigationStereoSourceVersion','runId','binding','before','capture','after'}
                |({'uiBefore','uiAfter','nativeBefore','nativeAfter'} if frame.get('navigationStereoSourceVersion')==2 else set()))
            need(value['before']==frame['before'] and frame['capture']['requestId']==value['captureIntent']['commandId'])
        if value['image'] is not None:
            image_record(value['image']);image=value['image']
            need(image['binding']==self.binding and image['runId']==self.run and image['role']==self.role
                 and image['stage']==0 and image['ticket']==value['ticket'] and image['kind']=='image'
                 and value['frame'] is not None and image['capture']==value['frame']['capture'])
            if image['phase']=='saved':stereo_frame(value['frame'],GraphicsOriginals.archive(self.images.root,image),self.run,self.binding,self.arrival.scene_url)
        if value['proof'] is not None:
            retirement(value['proof'],value['proof']['owner'],int(self.binding['processIdentity'].split(':',1)[0]),self.binding,self.role)
            need(value['proof']['owner']['capture']==value['captureIntent']
                 and value['memory']==value['proof']['memory'] and value['owner']==value['proof']['owner']
                 and value['files']==dict(remove=value['proof']['files']['removed'],inspect=value['proof']['files']['absent']))
        if value['phase']=='complete':need(value['image'] is not None and value['image']['phase']=='saved' and value['proof'] is not None)
    def save(self,value):
        self.now();self.validate(value)
        disk=dict(navigationStereoOwnerVersion=VERSION,runId=self.run,binding=self.binding,role=self.role,
                  artifactRoot=str(self.images.root),journalId=self.journal_id,payload=pack([value]))
        self.store.write(disk,self.disk);self.disk=deepcopy(disk);self.state=deepcopy(value)
    def image_intent(self,image):
        self.now();need(self.state['frame'] is not None)
        image_transition(self.state['image'],image);current=deepcopy(self.state);current['image']=image;self.save(current)
    def image_bytes(self):
        need(self.state is not None and self.state['image'] is not None and self.state['image']['phase']=='saved')
        return self.images.read(self.state['image'])
    def artifacts(self,sequence):
        """Original complete source journal plus PNG; no fresh sample is implied."""
        from adapters.native_feature_observation import integer
        from feature_journeys.stereo_navigation_evidence import original_name
        need(integer(sequence,1) and self.state is not None and self.state['phase']=='complete'
             and self.state['frame']['navigationStereoSourceVersion']==2
             and self.store.path.parent==self.images.root
             and self.journal_id is not None and self.store.path.name==original_name(self.run,self.role,self.journal_id)
             and self.store.read()==self.disk)
        self.image_bytes();capture=self.state['frame']['capture'];ticket=self.state['ticket']
        return [dict(kind=kind,name=name,sequence=sequence,capturedEpochMs=capture['capturedEpochMs'],ticket=ticket,
                     **(dict(source='world-render-target') if kind=='image' else {}))
                for kind,name in (('image',self.state['image']['name']),('file',self.store.path.name))]

    def acquire(self,ticket):
        identifier(ticket)
        with self.lock.held():
            need(self.deadline is None);self.deadline=self.now()+20
            try:return self.execute(ticket)
            except NativeUIError:raise
            except Exception:raise NativeUIError('Original navigation stereo ownership remains unresolved') from None
            finally:self.deadline=None
    def execute(self,ticket):
        if self.state is None:
            self.save(dict(ticket=ticket,phase='ready',before=None,captureIntent=None,frame=None,image=None,memory=None,files=None,owner=None,proof=None))
        need(self.state['ticket']==ticket)
        # A completed record is historical operation evidence, never a fresh
        # screenshot. Its bytes and original metadata are still revalidated.
        if self.state['phase']=='complete':self.image_bytes();return deepcopy(self.state)
        owned=self.capture_factory();need(isinstance(owned,OwnedWorldRenderCapture) and owned.owner.role==self.role
            and owned.capture.stereo and owned.capture.require_cameras and owned.owner.binding==self.binding)
        if self.state['captureIntent'] is not None:
            # No uncertain acquisition is sent again or replaced. A saved frame
            # can finish its original retirement; unknown/partial image data stay
            # owned for explicit failure cleanup by the enclosing feature.
            need(self.state['frame'] is not None and self.state['image'] is not None and self.state['image']['phase']=='saved')
            stereo_frame(self.state['frame'],self.image_bytes(),self.run,self.binding,self.arrival.scene_url)
            if self.state['proof'] is None or owned.owner.store.read() is not None:self.retire(owned)
        else:
            need(owned.owner.store.read() is None)
            native=None
            if self.journal_id is not None:
                need(callable(self.native_factory));native=self.native_factory();native_before=native.read(0)
            before=self.arrival.read();need(pose_packet(before,self.run,self.binding,self.arrival.scene_url,before['subject']['capturedEpochMs']) is not None)
            current=deepcopy(self.state);current['before']=before;self.save(current)
            original=owned.capture.intent
            def remember(command):
                current=deepcopy(self.state);current['phase']='acquiring';current['captureIntent']=command;self.save(current);original(command)
            owned.capture.intent=remember
            ui=None
            if self.journal_id is not None:
                need(callable(self.ui_factory));ui=self.ui_factory();ui_before=ui.capture()
                need(not ui_before['tabletShown'] and not ui_before['editorFocused'] and not ui_before['graphicsInventory']['keyboard3D']['raised'])
            capture,raw=owned.read(0);self.now()
            if ui is not None:ui_after=ui.capture()
            after=self.arrival.read(floor=before)
            if native is not None:native_after=native.read(native_before['sequence'])
            frame=dict(navigationStereoSourceVersion=SOURCE_VERSION if ui is not None else 1,runId=self.run,binding=self.binding,
                before=before,capture=capture,after=after,**(dict(uiBefore=ui_before,uiAfter=ui_after,nativeBefore=native_before,nativeAfter=native_after) if ui is not None else {}))
            stereo_frame(frame,raw,self.run,self.binding,self.arrival.scene_url)
            current=deepcopy(self.state);current['frame']=frame;current['phase']='framed';self.save(current)
            self.images.write(ticket,capture,raw);self.now()
            current=deepcopy(self.state);current['phase']='saved';self.save(current);self.retire(owned)
        current=deepcopy(self.state);current['phase']='complete';self.save(current);return deepcopy(self.state)
