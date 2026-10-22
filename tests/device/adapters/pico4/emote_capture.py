"""One durable original stereo Emote acquisition and independent retirement.

No Emote input, animation state, actor publication or whole feature verdict is
provided. Interrupted acquisitions are retained and can only be cleaned up.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from pathlib import Path
import time

from adapters.native_avatar_render import NativeAvatarRender,validate as avatar_packet
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.owned_world_render import WorldRenderOwner
from adapters.graphics_journey.originals import GraphicsOriginals,record as image_record,transition
from adapters.graphics_journey.samples import retirement
from adapters.pico4.emote_sources import PicoEmoteSources
from adapters.pico4.emote_model_draws import PicoWorldModelDraws,validate as model_packet,ACTION
from adapters.pico4.emote_pixels import original as pixel_original
from adapters.pico4.graphics_binding import SerializedWorldCapture
from adapters.script_journey.history import pack,unpack,same
from adapters.world_render_evidence import validate as capture_packet
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_packet

VERSION=1
FIELDS={'phase','providerBefore','providerAfter','avatarBefore','avatarAfter','capture','draws','image',
    'captureIntent','storage','inventory','retirement'}


class PicoEmoteCapture:
    def __init__(self,source,index,policy,world,avatar,models,*,monotonic=time.monotonic):
        need(isinstance(source,PicoEmoteSources) and integer(index,1,256)
            and all(callable(value) for value in (world,avatar,models,monotonic)))
        source.lock.assert_held();need(source.frames and source.previous is not None and source.state['phase']=='ready')
        self.source,self.index,self.policy=source,index,deepcopy(policy)
        self.world,self.avatar,self.models,self.monotonic=world,avatar,models,monotonic
        self.lock,self.guard,self.binding,self.pid=source.lock,source.guard,deepcopy(source.binding),source.pid
        self.run,self.role,self.root=source.run,source.role,Path(source.artifact_root)
        self.source_header=deepcopy(source.previous)
        self.store=PrivateFeatureState(source.store.path.with_name(source.store.path.stem+'-image-'+str(index)+'.json'))
        self.previous=self.store.read();self.started=self.clock=None;self.failed=False
        self.state={key:None for key in FIELDS};self.state['phase']='ready'
        self.bound()
        state,frames=PicoEmoteSources.archive(self.source_header,phase=source.phase,artifact_root=self.root,
            binding=self.binding,guard=self.guard,monotonic=self.monotonic)
        need(same(state,source.state) and same(frames,source.frames))
        self.source_frames=frames
        exact(self.policy,{'picoEmotePixelPolicyVersion','source','eyes'})
        need(type(self.policy['picoEmotePixelPolicyVersion']) is int and self.policy['picoEmotePixelPolicyVersion']==1
            and self.policy['source']=='world-render-target');exact(self.policy['eyes'],{'left','right'})
        for eye in self.policy['eyes'].values():
            exact(eye,{'marker','subject'})
            for rect in eye.values():
                need(type(rect) is list and len(rect)==4 and all(integer(v) for v in rect)
                    and rect[0]<rect[2] and rect[1]<rect[3])
        if self.previous is not None:self.state=self.decode(self.previous)

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.source.store.read(),self.source_header)
            and same(self.store.read(),self.previous))
        now=self.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<5));self.clock=now;return now

    def phase_ticket(self,value):
        phase_packet(value,run=self.run,area='emotes',request=value.get('requestId'),epoch=value.get('capturedEpochMs'))
        need(value['active'] and value['activations']);return value['activations'][-1]['ticket']

    def decode(self,value):
        exact(value,{'picoEmoteCaptureVersion','runId','fixtureUrl','role','index','binding','artifactRoot','pixelPolicy','sourceHeader','payload'})
        need(type(value['picoEmoteCaptureVersion']) is int and value['picoEmoteCaptureVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.source.phase.fixture_url and value['role']==self.role
            and type(value['index']) is int and value['index']==self.index and same(value['binding'],self.binding)
            and value['artifactRoot']==str(self.root) and same(value['pixelPolicy'],self.policy)
            and same(value['sourceHeader'],self.source_header))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,FIELDS)
        need(state['phase'] in ('ready','reading','complete'))
        for key in ('providerBefore','providerAfter'):
            if state[key] is not None:self.phase_ticket(state[key])
        if state['providerBefore'] is not None:
            previous=self.source_frames[-1]['phaseAfter'];before=state['providerBefore']
            phase_packet(before,run=self.run,area='emotes',request=before['requestId'],epoch=before['capturedEpochMs'],previous=previous)
            need(self.phase_ticket(before)==self.phase_ticket(previous))
        if state['providerAfter'] is not None:
            before,after=state['providerBefore'],state['providerAfter']
            need(before is not None)
            phase_packet(after,run=self.run,area='emotes',request=after['requestId'],epoch=after['capturedEpochMs'],previous=before)
        for key in ('avatarBefore','avatarAfter'):
            packet=state[key]
            if packet is not None:avatar_packet(packet,dict(schemaVersion=1,commandId=packet.get('requestId'),action='feature-avatar-render-observe'),self.pid,packet.get('capturedEpochMs'))
        if state['avatarBefore'] is not None:
            packet=state['avatarBefore'];native=self.source_frames[-1]['group']['native']
            need(packet['instance']==native['instance'] and packet['source']['rigId']==native['animation']['rigId'])
        if state['captureIntent'] is not None:WorldRenderOwner.acquisition(state['captureIntent'])
        if state['capture'] is not None:
            packet=state['capture'];capture_packet(packet,packet.get('requestId'),self.pid,packet.get('capturedEpochMs'),stereo=True,require_cameras=True)
            need(state['captureIntent'] is not None and packet['requestId']==state['captureIntent']['commandId'])
        if state['draws'] is not None:
            packet=state['draws'];need(state['capture'] is not None)
            model_packet(packet,dict(schemaVersion=1,commandId=packet.get('requestId'),action=ACTION,captureRequestId=state['capture']['requestId']),
                self.pid,packet.get('capturedEpochMs'),capture=state['capture'])
        if state['image'] is not None:
            image_record(state['image']);need(same(state['image']['binding'],self.binding) and state['image']['runId']==self.run
                and state['image']['role']==self.role and state['image']['stage']==0 and same(state['image']['capture'],state['capture']))
        if state['retirement'] is not None:
            proof=state['retirement'];retirement(proof,proof['owner'],self.pid,self.binding,self.role)
            need(same(proof['owner']['capture'],state['captureIntent']) and same(proof['memory'],state['storage'])
                and same(proof['files']['absent'],state['inventory']))
        if state['phase']=='ready':need(all(state[key] is None for key in FIELDS-{'phase'}))
        if state['phase']=='complete':
            need(all(state[key] is not None for key in FIELDS-{'phase'}) and state['image']['phase']=='saved'
                and self.phase_ticket(state['providerBefore'])==self.phase_ticket(state['providerAfter'])==state['image']['ticket'])
        return deepcopy(state)

    def save(self):
        self.bound();need(not self.failed)
        value=dict(picoEmoteCaptureVersion=VERSION,runId=self.run,fixtureUrl=self.source.phase.fixture_url,role=self.role,index=self.index,
            binding=self.binding,artifactRoot=str(self.root),pixelPolicy=self.policy,sourceHeader=self.source_header,payload=pack([self.state]))
        try:self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:self.failed=True;raise

    def remember(self,key,value):self.state[key]=deepcopy(value);self.save()

    def image_intent(self,value):
        need(self.state['phase']=='reading');transition(self.state['image'],value);self.remember('image',value)

    def images(self,*,create=False):
        # Exact existing stereo Graphics byte engine; stage0 is local to this
        # separately indexed Emote directory, not a Graphics feature assertion.
        root=self.root/('emote-images-'+self.run+'-'+self.role+'-'+str(self.index))
        if create:
            PrivateFeatureState(self.root/'emote-image-boundary.json')._parent();root.mkdir(mode=0o700)
        return GraphicsOriginals(root,self.binding,self.run,self.role,0,self.guard,self.image_intent,monotonic=self.monotonic)

    def owned(self):
        value=self.world();need(isinstance(value,SerializedWorldCapture) and value.source_lock is self.lock
            and same(value.owner.binding,self.binding) and value.owner.role==self.role)
        if self.state['storage'] is not None:
            value.storage.instance=self.state['storage']['instance'];value.storage.sequence=self.state['storage']['sequence']
        if self.state['inventory'] is not None:
            value.receipts.cleanup.sequence=self.state['inventory']['sequence'];value.receipts.cleanup.captured=self.state['inventory']['capturedEpochMs']
        return value

    def release(self,owned):
        self.bound();need(self.state['captureIntent'] is not None and same(owned.owner.owned()['capture'],self.state['captureIntent']))
        if self.state['retirement'] is not None:self.remember('retirement',None)
        memory=owned.storage.release(self.state['captureIntent']['commandId']);self.remember('storage',memory)
        owner=deepcopy(owned.owner.owned());request=owned.receipts.cleanup.request
        def inventory(operation):
            packet=request(operation);self.remember('inventory',packet);return packet
        owned.receipts.cleanup.request=inventory;owned.receipts.retire();self.bound()
        proof=dict(memory=memory,files=deepcopy(owned.receipts.proof),owner=owner)
        retirement(proof,owner,self.pid,self.binding,self.role);self.remember('retirement',proof)
        need(same(owned.owner.owned(),owner));owned.owner.store.discard(owner);need(owned.owner.store.read() is None);self.bound();return proof

    def frame(self):
        need(all(self.state[key] is not None for key in ('providerBefore','avatarBefore','avatarAfter','capture','draws')))
        return dict(ticket=self.phase_ticket(self.state['providerBefore']),**{key:deepcopy(self.state[key]) for key in ('avatarBefore','avatarAfter','capture','draws')})

    def read(self,ticket):
        identifier(ticket);need(not self.failed and not self.source.historical and self.previous is None and self.state['phase']=='ready')
        self.started=self.bound();owned=None
        try:
            self.state['phase']='reading';self.save();owned=self.owned();need(owned.owner.store.read() is None)
            before_phase=self.source.phase.status(self.source.frames[-1]['phaseAfter']);need(self.phase_ticket(before_phase)==ticket)
            need(self.phase_ticket(self.source.frames[-1]['phaseAfter'])==ticket)
            self.remember('providerBefore',before_phase)
            avatar,models=self.avatar(),self.models()
            need(isinstance(avatar,NativeAvatarRender) and isinstance(models,PicoWorldModelDraws) and avatar.pid==models.pid==self.pid
                and not avatar.ios and not models.ios)
            epoch=avatar.clock_ms();need(integer(epoch,1));begin=self.bound()
            before=avatar.read();native=self.source.frames[-1]['group']['native']
            need(before['instance']==native['instance'] and before['source']['rigId']==native['animation']['rigId']);self.remember('avatarBefore',before)
            intent,send=owned.capture.intent,owned.capture.send
            def reserve(command):
                need(self.state['captureIntent'] is None and owned.owner.store.read() is None)
                WorldRenderOwner.acquisition(command);self.remember('captureIntent',command);intent(command)
                need(same(owned.owner.owned()['capture'],command));self.bound()
            def acquire(command):
                need(same(self.state['captureIntent'],command) and same(owned.owner.owned()['capture'],command));self.bound();send(command)
            owned.capture.intent,owned.capture.send=reserve,acquire
            capture,raw=owned.read(0);self.remember('capture',capture);self.remember('draws',models.read(capture));self.remember('avatarAfter',avatar.read())
            self.images(create=True).write(ticket,capture,raw);self.bound();self.release(owned)
            host=self.source.phase.epoch_ms();need(number(host,1,1e15));host_begin=self.bound()
            after_phase=self.source.phase.status(before_phase);need(self.phase_ticket(after_phase)==ticket);self.remember('providerAfter',after_phase)
            now=avatar.clock_ms();need(integer(now,epoch));end=self.bound()
            pixel_original(self.run,self.frame(),raw,self.pid,max(now,epoch+math.ceil((end-begin)*1000)),self.policy)
            self.state['phase']='complete';self.save();result=deepcopy(self.frame());self.bound();need(self.guard() is not False)
            now=avatar.clock_ms();need(integer(now,epoch));end=self.bound();floor=max(now,epoch+math.ceil((end-begin)*1000))
            pixel_original(self.run,result,raw,self.pid,floor,self.policy);end=self.bound()
            # Include revalidation, copies and final guards in both clock domains.
            need(self.guard() is not False);native_end=avatar.clock_ms();need(integer(native_end,now));end=self.bound()
            floor=max(native_end,epoch+math.ceil((end-begin)*1000))
            for stamp in (before['capturedEpochMs'],capture['source']['renderTrace']['recordedEpochMs'],capture['source']['capturedEpochMs'],
                    self.state['draws']['capturedEpochMs'],self.state['avatarAfter']['capturedEpochMs']):fresh(stamp,floor)
            delivered=self.source.phase.epoch_ms();need(number(delivered,host,1e15));end=self.bound()
            fresh(after_phase['capturedEpochMs'],max(delivered,host+math.ceil((end-host_begin)*1000)));return result
        except Exception:
            if owned is not None and not self.failed:
                try:
                    if owned.owner.store.read() is not None and self.state['captureIntent'] is not None:self.release(owned)
                except Exception:pass
            raise NativeUIError('Original Pico Emote image acquisition failed; ownership is retained') from None
        finally:self.started=None

    def original(self):
        # A historical image remains usable after its parent source advances;
        # it cannot satisfy a new live acquisition or authorize another input.
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous)
            and self.state['phase']=='complete' and same(self.state,self.decode(self.previous)))
        frame,raw=self.archive(self.previous,self.source,self.index,self.policy)
        need(self.guard() is not False and same(self.store.read(),self.previous));return frame,raw

    @classmethod
    def archive(cls,value,source,index,policy):
        """Pure original metadata/bytes, including after child journal retirement.

        The parent must retain this exact header and independently bind any
        later live result. No current source, candidate or timestamp is invented.
        """
        need(isinstance(source,PicoEmoteSources) and integer(index,1,256));source.lock.assert_held()
        started=source.monotonic();need(number(started,0,1e15))
        scope=object.__new__(cls);scope.source,scope.index,scope.policy=source,index,deepcopy(policy)
        scope.binding,scope.pid,scope.run,scope.role=deepcopy(source.binding),source.pid,source.run,source.role
        scope.root,scope.lock,scope.guard,scope.monotonic=Path(source.artifact_root),source.lock,lambda:True,source.monotonic
        need(type(value) is dict and type(value.get('sourceHeader')) is dict);scope.source_header=deepcopy(value['sourceHeader'])
        _state,originals=PicoEmoteSources.archive(scope.source_header,phase=source.phase,artifact_root=scope.root,
            binding=scope.binding,guard=lambda:True,monotonic=scope.monotonic)
        need(len(originals)<=len(source.frames) and all(same(a,b) for a,b in zip(originals,source.frames)))
        scope.source_frames=originals
        scope.state=scope.decode(value);need(scope.state['phase']=='complete')
        raw=scope.images().read(scope.state['image']);frame=scope.frame()
        pixel_original(scope.run,frame,raw,scope.pid,frame['avatarAfter']['capturedEpochMs'],scope.policy)
        need(number(source.monotonic(),started,started+5));return frame,raw

    def recover(self):
        """Cleanup only: never dispatch/reconstruct a lost acquisition result."""
        self.bound();need(self.previous is not None and self.state['phase']=='reading' and not self.failed)
        owned=self.owned()
        if owned.owner.store.read() is None:
            # Original cleanup may have completed before a later phase/pixel
            # failure. Replaying its proof never acquires or releases again.
            proof=self.state['retirement'];need(proof is not None)
            retirement(proof,proof['owner'],self.pid,self.binding,self.role);self.bound()
            return deepcopy(proof)
        self.release(owned);return deepcopy(self.state['retirement'])
