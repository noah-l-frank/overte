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
from adapters.navigation_arrival import pose_packet,stereo_frame
from adapters.graphics_journey.originals import GraphicsOriginals,record as image_record,transition as image_transition
from adapters.graphics_journey.samples import retirement
from adapters.owned_world_render import OwnedWorldRenderCapture
from adapters.script_journey.history import pack,unpack
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.contract import identifier

VERSION=1

class NavigationStereo:
    def __init__(self,arrival,capture_factory,path,artifact_root,run,binding,lock,guard,*,role='primary',monotonic=time.monotonic):
        context(binding);identifier(run)
        need(isinstance(lock,ScriptSourceLock) and all(callable(f) for f in (capture_factory,guard,monotonic)) and role in ('primary','actor'))
        self.arrival,self.capture_factory,self.run,self.binding,self.lock,self.guard=arrival,capture_factory,run,deepcopy(binding),lock,guard
        self.role,self.monotonic=role,monotonic;self.store=PrivateFeatureState(path);self.disk=self.store.read();self.state=None
        self.images=GraphicsOriginals(artifact_root,binding,run,role,0,guard,self.image_intent,monotonic=monotonic)
        if self.disk is not None:
            exact(self.disk,{'navigationStereoOwnerVersion','runId','binding','role','artifactRoot','payload'})
            need(type(self.disk['navigationStereoOwnerVersion']) is int and self.disk['navigationStereoOwnerVersion']==VERSION
                 and self.disk['runId']==run and self.disk['binding']==binding and self.disk['role']==role
                 and self.disk['artifactRoot']==str(self.images.root))
            rows=unpack(self.disk['payload']);need(len(rows)==1);self.validate(rows[0]);self.state=rows[0]
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
            frame=value['frame'];exact(frame,{'navigationStereoSourceVersion','runId','binding','before','capture','after'})
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
                  artifactRoot=str(self.images.root),payload=pack([value]))
        self.store.write(disk,self.disk);self.disk=deepcopy(disk);self.state=deepcopy(value)
    def image_intent(self,image):
        self.now();need(self.state['frame'] is not None)
        image_transition(self.state['image'],image);current=deepcopy(self.state);current['image']=image;self.save(current)
    def image_bytes(self):
        need(self.state is not None and self.state['image'] is not None and self.state['image']['phase']=='saved')
        return self.images.read(self.state['image'])
    def retire(self,owned):
        self.now();owner=owned.owner.owned();need(owner['capture']==self.state['captureIntent'])
        # Bind recreated storage to the original native issuer before any read
        # or retirement. A new renderer/source cannot report an old one absent.
        owned.storage.bind(self.state['frame']['capture'])
        resumed=self.state['phase']=='retiring'
        if resumed:
            # Do not repeat an uncertain release/remove mutation. Known original
            # successful headers can finish through a fresh read-only inventory;
            # a lost mutation header retains ownership for failure cleanup.
            need(self.state['memory'] is not None and self.state['owner']==owner
                 and type(self.state['files']) is dict and 'remove' in self.state['files'])
            memory=deepcopy(self.state['memory']);removed=deepcopy(self.state['files']['remove'])
            absent=owned.receipts.cleanup.request('inspect');self.now()
            current=deepcopy(self.state);current['files']['inspect']=absent;self.save(current)
            files=dict(removed=removed,absent=absent)
        else:
            current=deepcopy(self.state);current['phase']='retiring';self.save(current)
            memory=owned.storage.release(owner['capture']['commandId']);self.now()
            current=deepcopy(self.state);current['memory']=memory;current['owner']=owned.owner.owned();self.save(current)
            original=owned.receipts.cleanup.request
            def remember(operation):
                packet=original(operation);self.now();current=deepcopy(self.state)
                current['files']=dict(current['files'] or {});current['files'][operation]=packet;self.save(current);return packet
            owned.receipts.cleanup.request=remember
            files=owned.receipts.retire();self.now();owner=owned.owner.owned()
        proof=dict(memory=memory,files=files,owner=owner)
        retirement(proof,owner,int(self.binding['processIdentity'].split(':',1)[0]),self.binding,self.role)
        current=deepcopy(self.state);current['proof']=proof;self.save(current)
        need(owned.owner.owned()==owner);owned.owner.store.discard(owner);need(owned.owner.store.read() is None);self.now()
        return proof
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
            before=self.arrival.read();need(pose_packet(before,self.run,self.binding,self.arrival.scene_url,before['subject']['capturedEpochMs']) is not None)
            current=deepcopy(self.state);current['before']=before;self.save(current)
            original=owned.capture.intent
            def remember(command):
                current=deepcopy(self.state);current['phase']='acquiring';current['captureIntent']=command;self.save(current);original(command)
            owned.capture.intent=remember
            capture,raw=owned.read(0);self.now();after=self.arrival.read(floor=before)
            frame=dict(navigationStereoSourceVersion=VERSION,runId=self.run,binding=self.binding,before=before,capture=capture,after=after)
            stereo_frame(frame,raw,self.run,self.binding,self.arrival.scene_url)
            current=deepcopy(self.state);current['frame']=frame;current['phase']='framed';self.save(current)
            self.images.write(ticket,capture,raw);self.now()
            current=deepcopy(self.state);current['phase']='saved';self.save(current);self.retire(owned)
        current=deepcopy(self.state);current['phase']='complete';self.save(current);return deepcopy(self.state)
