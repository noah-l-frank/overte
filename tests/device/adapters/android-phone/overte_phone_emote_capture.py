"""One durably owned Emote image acquisition; no input/effect/publication verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
import os
import time

from adapters.native_avatar_render import NativeAvatarRender,validate as avatar_packet
from adapters.native_world_model_draws import NativeWorldModelDraws,validate as draws_packet
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.owned_world_render import OwnedWorldRenderCapture,WorldRenderOwner
from adapters.world_render_evidence import validate as capture_packet,LIMIT
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_packet
from overte_phone_emote_sources import PhoneEmoteSources
from overte_phone_emote_images import PhoneEmoteImages,record as image_record
from overte_phone_emote_pixels import original as original_pixels
from overte_phone_graphics_samples import retirement
from overte_phone_graphics_scene import operation
from overte_phone_script_history import pack,unpack,same

VERSION=1
FIELDS={'phase','providerBefore','providerAfter','avatarBefore','avatarAfter','capture','draws','image',
    'captureIntent','retirement','storage','inventory'}


class PhoneEmoteCapture:
    def __init__(self,source,index,policy,*,monotonic=time.monotonic):
        need(isinstance(source,PhoneEmoteSources) and getattr(source,'historical',False) is False and integer(index,1,256) and callable(monotonic))
        source.lock.assert_held();need(source.state['phase'] in ('ready','reading') and source.frames and not source.failed)
        exact(policy,{'source','marker','subject'});need(policy['source']=='world-render-target')
        self.source,self.index,self.policy,self.monotonic=source,index,deepcopy(policy),monotonic
        self.run,self.role,self.binding,self.pid=source.run,source.role,deepcopy(source.binding),source.pid
        self.guard,self.root,self.lock=source.guard,source.artifact_root,source.lock
        self.source_header=deepcopy(source.previous)
        self.store=PrivateFeatureState(source.store.path.with_name('phone-emote-'+self.role+'-capture-'+str(index)+'.json'))
        self.previous=self.store.read();self.failed=False;self.started=None;self.last_clock=None
        need(source.state['phase']=='ready' or self.previous is not None)
        self.started=self._bound()
        state,frames=PhoneEmoteSources.archive(self.source_header,phase=source.phase,artifact_root=self.root,
            binding=self.binding,guard=lambda:True,monotonic=self.monotonic)
        need(same(state,source.state) and same(frames,source.frames));self._bound();self.started=None
        self.state={key:None for key in FIELDS};self.state['phase']='ready'
        if self.previous is not None:self.state=self.decode(self.previous)

    def _bound(self):
        self.lock.assert_held();need(self.guard() is not False)
        need(self.source_header is not None and same(self.source.store.read(),self.source_header))
        now=self.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock)
            and (self.started is None or now-self.started<5))
        self.last_clock=now;return now

    def _phase(self,value):
        phase_packet(value,run=self.run,area='emotes',request=value.get('requestId'),epoch=value.get('capturedEpochMs'))
        need(value['active'] and value['activations'])
        return value['activations'][-1]['ticket']

    def decode(self,value):
        exact(value,{'emoteCaptureVersion','runId','fixtureUrl','role','index','binding','artifactRoot','imagePolicy','payload'})
        need(type(value['emoteCaptureVersion']) is int and value['emoteCaptureVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.source.phase.fixture_url and value['role']==self.role
            and type(value['index']) is int and value['index']==self.index and same(value['binding'],self.binding)
            and value['artifactRoot']==str(self.root) and same(value['imagePolicy'],self.policy))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,FIELDS)
        need(state['phase'] in ('ready','reading','complete'))
        for key in ('providerBefore','providerAfter'):
            if state[key] is not None:self._phase(state[key])
        for key in ('avatarBefore','avatarAfter'):
            packet=state[key]
            if packet is not None:
                avatar_packet(packet,dict(schemaVersion=1,commandId=packet.get('requestId'),action='feature-avatar-render-observe'),self.pid,packet.get('capturedEpochMs'))
        if state['captureIntent'] is not None:WorldRenderOwner.acquisition(state['captureIntent'])
        if state['capture'] is not None:
            packet=state['capture'];capture_packet(packet,packet.get('requestId'),self.pid,packet.get('capturedEpochMs'))
            need(state['captureIntent'] is not None and packet['requestId']==state['captureIntent']['commandId'])
        if state['draws'] is not None:
            packet=state['draws'];need(state['capture'] is not None)
            draws_packet(packet,dict(schemaVersion=1,commandId=packet.get('requestId'),action='feature-world-model-draws-observe',
                captureRequestId=state['capture']['requestId']),self.pid,packet.get('capturedEpochMs'),capture=state['capture'])
        if state['image'] is not None:
            image_record(state['image']);need(same(state['image']['binding'],self.binding)
                and state['image']['runId']==self.run and state['image']['role']==self.role and state['image']['stage']==self.index
                and same(state['image']['capture'],state['capture']))
        if state['retirement'] is not None:
            proof=state['retirement'];retirement(proof,proof['owner'],self.pid,self.binding,self.role)
            need(same(proof['owner']['capture'],state['captureIntent']) and same(proof['memory'],state['storage'])
                and same(proof['files']['absent'],state['inventory']))
        if state['phase']=='ready':need(all(state[key] is None for key in FIELDS-{'phase'}))
        if state['phase']=='complete':
            need(all(state[key] is not None for key in FIELDS-{'phase'}) and state['image']['phase']=='saved'
                and self._phase(state['providerBefore'])==self._phase(state['providerAfter'])==state['image']['ticket'])
        return deepcopy(state)

    def save(self):
        self._bound();need(not self.failed and same(self.store.read(),self.previous))
        value=dict(emoteCaptureVersion=VERSION,runId=self.run,fixtureUrl=self.source.phase.fixture_url,role=self.role,index=self.index,
            binding=deepcopy(self.binding),artifactRoot=str(self.root),imagePolicy=deepcopy(self.policy),payload=pack([self.state]))
        try:
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self._bound()
        except Exception:
            self.failed=True;raise

    def _remember(self,key,value):
        self.state[key]=deepcopy(value);self.save()

    def images(self):
        return PhoneEmoteImages(self.root,self.binding,self.run,self.role,self.index,self.guard,self._image_intent,monotonic=self.monotonic)

    def _image_intent(self,value):
        need(self.state['phase']=='reading');image_record(value)
        old=self.state['image']
        if old is None:need(value['phase']=='planned')
        else:
            need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
                and (old['phase']=='planned' or same(value['file'],old['file'])))
        self._remember('image',value)

    def _owned(self):
        owned=self.source.adapter._world_render_capture(self.source.selector,read_only=True,role=self.role,require_frame_view=True)
        need(isinstance(owned,OwnedWorldRenderCapture) and same(owned.owner.binding,self.binding) and owned.owner.role==self.role)
        stored,inventory=self.state['storage'],self.state['inventory']
        if stored is not None:owned.storage.instance,owned.storage.sequence=stored['instance'],stored['sequence']
        if inventory is not None:owned.receipts.cleanup.sequence,owned.receipts.cleanup.captured=inventory['sequence'],inventory['capturedEpochMs']
        return owned

    def _release(self,owned):
        need(same(owned.owner.owned()['capture'],self.state['captureIntent']))
        if self.state['retirement'] is not None:self._remember('retirement',None)
        memory=owned.storage.release(self.state['captureIntent']['commandId']);self._remember('storage',memory)
        owner=deepcopy(owned.owner.owned());request=owned.receipts.cleanup.request
        def inventory(operation):
            packet=request(operation);self._remember('inventory',packet);return packet
        owned.receipts.cleanup.request=inventory
        owned.receipts.retire();self._bound()
        proof=dict(memory=memory,files=deepcopy(owned.receipts.proof),owner=owner)
        retirement(proof,owner,self.pid,self.binding,self.role);self._remember('retirement',proof)
        need(same(owned.owner.owned(),owner));owned.owner.store.discard(owner);need(owned.owner.store.read() is None);self._bound()
        return proof

    def frame(self):
        state=self.state;need(state['providerBefore'] is not None)
        need(all(state[key] is not None for key in ('avatarBefore','avatarAfter','capture','draws')))
        return dict(ticket=self._phase(state['providerBefore']),**{key:deepcopy(state[key]) for key in ('avatarBefore','avatarAfter','capture','draws')})

    def read(self,ticket):
        identifier(ticket);need(not self.failed and self.previous is None and self.state['phase']=='ready'
            and self.source.state['phase']=='ready')
        self.started=self._bound();owned=None
        try:
            owned=self._owned();need(owned.owner.store.read() is None)
            self.state['phase']='reading';self.save()
            provider=self.source.phase.status(self.source.frames[-1]['phaseAfter']);need(self._phase(provider)==ticket)
            self._remember('providerBefore',provider)
            avatar=self.source.adapter._avatar_render_observer(self.source.selector,read_only=True)
            models=self.source.adapter._world_model_draws_observer(self.source.selector,read_only=True)
            need(isinstance(avatar,NativeAvatarRender) and isinstance(models,NativeWorldModelDraws)
                and avatar.pid==models.pid==self.pid and avatar.ios is False and models.ios is False)
            query_started=self._bound();epoch=avatar.clock_ms();need(integer(epoch,1))
            before=avatar.read();native=self.source.frames[-1]['group']['native']
            need(before['instance']==native['instance'] and before['source']['rigId']==native['animation']['rigId'])
            self._remember('avatarBefore',before)
            intent,send=owned.capture.intent,owned.capture.send
            def reserve(command):
                need(self.state['captureIntent'] is None and owned.owner.store.read() is None)
                WorldRenderOwner.acquisition(command)
                # Retain the exact nonce before the downstream owner write can
                # commit and lose its return. Never dispatch on a failed write.
                self._remember('captureIntent',command);intent(command)
                need(same(owned.owner.owned()['capture'],command));self._bound()
            def acquire(command):
                need(same(self.state['captureIntent'],command)
                    and same(owned.owner.owned()['capture'],command));self._bound();send(command)
            owned.capture.intent,owned.capture.send=reserve,acquire
            capture,raw=owned.read(0);self._remember('capture',capture)
            self._remember('draws',models.read(capture));self._remember('avatarAfter',avatar.read())
            self.images().write(ticket,capture,raw);self._bound()
            self._release(owned)
            host_started=self.source.phase.epoch_ms();need(number(host_started,1,1e15));host_query_start=self._bound()
            final=self.source.phase.status(provider);need(self._phase(final)==ticket);self._remember('providerAfter',final)
            now=avatar.clock_ms();need(integer(now,epoch));current=self._bound()
            original_pixels(self.run,self.frame(),raw,self.pid,max(now,epoch+math.ceil((current-query_started)*1000)),self.policy)
            self.state['phase']='complete';self.save()
            result=deepcopy(self.frame());self._bound();need(self.guard() is not False);self._bound()
            now=avatar.clock_ms();need(integer(now,epoch));current=self._bound()
            original_pixels(self.run,result,raw,self.pid,max(now,epoch+math.ceil((current-query_started)*1000)),self.policy)
            current=self._bound();floor=max(now,epoch+math.ceil((current-query_started)*1000))
            for stamp in (before['capturedEpochMs'],capture['source']['renderTrace']['recordedEpochMs'],
                    capture['source']['capturedEpochMs'],self.state['draws']['capturedEpochMs'],self.state['avatarAfter']['capturedEpochMs']):fresh(stamp,floor)
            delivered_host=self.source.phase.epoch_ms();need(number(delivered_host,host_started,1e15));current=self._bound()
            fresh(final['capturedEpochMs'],max(delivered_host,host_started+math.ceil((current-host_query_start)*1000)))
            return result
        except Exception:
            if owned is not None and not self.failed:
                try:
                    if owned.owner.store.read() is not None and self.state['captureIntent'] is not None:self._release(owned)
                except Exception:pass # Ownership remains durable; no result or cleanup success.
            raise NativeUIError('Owned original Emote image acquisition is unavailable') from None
        finally:self.started=None

    @operation
    def original(self):
        self._bound();need(not self.failed and self.state['phase']=='complete' and same(self.store.read(),self.previous))
        state=self.decode(self.previous);need(same(state,self.state))
        raw=self.images().read(state['image']);frame=self.frame()
        original_pixels(self.run,frame,raw,self.pid,state['avatarAfter']['capturedEpochMs'],self.policy);self._bound()
        return frame,raw # Historical only; no native query or fresh verdict.

    @classmethod
    def archive(cls,value,source,index,policy):
        """Reopen a parent's retained complete original after child retirement.

        This validates historical bytes/metadata only. The parent must retain
        the exact child header before cleanup and independently prove freshness
        and causality. A missing live child is not an observation.
        """
        need(isinstance(source,PhoneEmoteSources) and integer(index,1,256))
        source.lock.assert_held();started=source.monotonic();need(number(started,0,1e15) and source.guard() is not False)
        scope=object.__new__(cls);scope.source=source;scope.index=index;scope.policy=deepcopy(policy)
        scope.run,scope.role,scope.binding,scope.pid=source.run,source.role,deepcopy(source.binding),source.pid
        scope.guard,scope.root,scope.monotonic=source.guard,source.artifact_root,source.monotonic
        exact(policy,{'source','marker','subject'});need(policy['source']=='world-render-target')
        scope.state=scope.decode(value);need(scope.state['phase']=='complete')
        frame=scope.frame();raw=scope.images().read(scope.state['image'])
        original_pixels(scope.run,frame,raw,scope.pid,scope.state['avatarAfter']['capturedEpochMs'],scope.policy)
        returned=deepcopy((frame,raw,scope.state));source.lock.assert_held();need(source.guard() is not False)
        end=source.monotonic();need(number(end,started,1e15) and end-started<5)
        return returned

    def diagnostic(self):
        """Validate retained image ownership, measuring incomplete bytes only."""
        image=self.state['image']
        if image is None:return None
        images=self.images()
        if image['phase']=='saved':images.read(image);return None
        if image['phase']=='planned':need(images.absent(image));return None
        path=images._path(image);descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            images._file(path,stream.fileno(),image);raw=stream.read(LIMIT+1)
            images._file(path,stream.fileno(),image)
            need(len(raw)==os.fstat(stream.fileno()).st_size)
        return dict(name=image['name'],file=deepcopy(image['file']),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

    @classmethod
    def retirement_archive(cls,value,source,index,policy):
        """Historical failed/complete cleanup evidence, never an image result."""
        need(isinstance(source,PhoneEmoteSources) and integer(index,1,256));source.lock.assert_held()
        started=source.monotonic();need(number(started,0,1e15) and source.guard() is not False)
        exact(value,{'emoteCaptureRetirementVersion','sourceHeader','header','cleanup','partialFile'})
        need(type(value['emoteCaptureRetirementVersion']) is int and value['emoteCaptureRetirementVersion']==1
            and type(value['sourceHeader']) is dict and value['sourceHeader'].get('role')==source.role)
        _state,frames=PhoneEmoteSources.archive(value['sourceHeader'],phase=source.phase,artifact_root=source.artifact_root,
            binding=source.binding,guard=source.guard,monotonic=source.monotonic);need(bool(frames))
        scope=object.__new__(cls);scope.source,scope.index,scope.policy=source,index,deepcopy(policy)
        scope.run,scope.role,scope.binding,scope.pid=source.run,source.role,deepcopy(source.binding),source.pid
        scope.guard,scope.root,scope.monotonic=source.guard,source.artifact_root,source.monotonic
        exact(policy,{'source','marker','subject'});need(policy['source']=='world-render-target')
        scope.state=scope.decode(value['header']);state=scope.state
        if state['captureIntent'] is not None:need(state['retirement'] is not None)
        if state['providerBefore'] is not None:
            need(scope._phase(state['providerBefore'])==frames[-1]['phaseAfter']['activations'][-1]['ticket'])
        for key in ('avatarBefore','avatarAfter','capture'):
            if state[key] is not None:need(state[key]['instance']==frames[-1]['group']['native']['instance'])
        diagnostic=scope.diagnostic();need(same(diagnostic,value['partialFile']))
        expected=dict(emoteCaptureCleanupVersion=VERSION,completeImageRecord=state['phase']=='complete',
            retirement=state['retirement'],retainedPartialImage=diagnostic is not None)
        need(same(value['cleanup'],expected))
        if state['phase']=='complete':
            raw=scope.images().read(state['image'])
            original_pixels(scope.run,scope.frame(),raw,scope.pid,state['avatarAfter']['capturedEpochMs'],scope.policy)
        result=deepcopy(value);source.lock.assert_held();need(source.guard() is not False)
        end=source.monotonic();need(number(end,started,1e15) and end-started<5);return result

    @operation
    def cleanup(self,*,retain=None):
        """Retire this image scope; failed captures never become successful images."""
        need(retain is None or callable(retain))
        self._bound();need(not self.failed and self.previous is not None and same(self.store.read(),self.previous))
        state=self.decode(self.previous);need(same(state,self.state))
        owned=self._owned();current=owned.owner.store.read()
        if current is not None:
            need(state['captureIntent'] is not None and same(owned.owner.owned()['capture'],state['captureIntent']))
            self._release(owned)
        elif state['captureIntent'] is not None:need(state['retirement'] is not None)
        diagnostic=self.diagnostic()
        need(owned.owner.store.read() is None);self._bound()
        result=deepcopy(dict(emoteCaptureCleanupVersion=VERSION,completeImageRecord=self.state['phase']=='complete',
            retirement=self.state['retirement'],retainedPartialImage=diagnostic is not None))
        if retain is not None:
            proof=dict(emoteCaptureRetirementVersion=1,sourceHeader=deepcopy(self.source_header),header=deepcopy(self.previous),
                cleanup=deepcopy(result),partialFile=diagnostic)
            self.retirement_archive(proof,self.source,self.index,self.policy);self._bound()
            need(retain(deepcopy(proof)) is not False);self._bound()
            # IO inside the parent retention callback cannot authorize loss of
            # child metadata if originals, candidate or ownership changed.
            self.retirement_archive(proof,self.source,self.index,self.policy)
            need(owned.owner.store.read() is None);self._bound()
        self._bound();self.store.discard(self.previous);need(self.store.read() is None);self._bound()
        return result
