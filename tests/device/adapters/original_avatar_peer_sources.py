"""Configured immutable actor receive/render originals from frozen 54d48ae5d9.

Raw world/receive/renderer DTOs keep their original types and clocks. Profile
configuration changes only owner namespace, phase area and private archive keys.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
from adapters.native_avatar_receive import validate as receive_packet
from adapters.native_clock_join import NativeClockAcquisition,digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore,BLOCK,MAX_FRAMES
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters import avatar_renderers
from ios.adapters.emote_peer import acquisition
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_world import validate as world_packet,ACTION as WORLD_ACTION
from ios.adapters.graphics_history import restore_native,follow_native
from ios.adapters.script_runtime import IOSScriptRuntime

VERSION=1


class OriginalAvatarPeerSources:
    def __init__(self,store,root,binding,run,phase,lock,guard,*,runtime=None,selector=None,
                 profile,phase_changed,role='actor',historical=False,monotonic=time.monotonic,epoch_ms=lambda:time.time()*1000):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
            and type(historical) is bool and all(callable(fn) for fn in (guard,monotonic,epoch_ms)))
        need(profile in ('emote','avatar') and isinstance(phase_changed,type) and issubclass(phase_changed,NativeUIError))
        need(role in ('primary','actor') and (profile=='avatar' or role=='actor'))
        self.profile,self.phase_changed=profile,phase_changed
        self.role=role
        self.area="emotes" if profile=='emote' else 'avatar-people'
        self.schema_prefix=profile+'Peer';self.version_key='ios'+profile.title()+'PeerSourcesVersion'
        self.manifest_key=self.schema_prefix+'ManifestVersion'
        self.store,self.root,self.binding=store,Path(root),deepcopy(context(binding))
        self.run,self.phase,self.lock,self.guard=identifier(run),phase,lock,guard
        self.runtime,self.selector,self.historical=runtime,selector,historical
        self.monotonic,self.epoch_ms=monotonic,epoch_ms
        self.pid=int(binding['processIdentity']);need(self.pid>0 and str(self.pid)==binding['processIdentity'])
        need(store.path.name=='ios-'+profile+'-'+role+'-peer-sources.json' and lock.path==store.path.with_name('script-feature-sources.lock'))
        if not historical:
            need(isinstance(runtime,IOSScriptRuntime) and isinstance(phase,PhaseFixtureReader)
                and phase.run==run and phase.area==self.area)
        self.originals=OriginalFrameStore(root,binding,run,role,guard,self.storage_intent,
            namespace=profile+'-peer',schema_prefix=self.schema_prefix,monotonic=monotonic)
        self.frames=[];self.previous=None;self.failed=False
        self.state=dict(revision=0,manifests=[],pending=None)
        lock.assert_held();self.previous=store.read()
        if self.previous is not None:self.state,self.frames=self.decode(self.previous)

    def envelope(self,state):
        return dict(binding=self.binding,runId=self.run,artifactRoot=str(self.root),payload=pack([state]),
            **{self.version_key:VERSION},**({'role':self.role} if self.profile=='avatar' else {}))

    def decode(self,value):
        exact(value,{self.version_key,'binding','runId','artifactRoot','payload'}|({'role'} if self.profile=='avatar' else set()))
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'revision','manifests','pending'});need(integer(state['revision'],0,MAX_FRAMES))
        frames=self.originals.restore(state['manifests'],state['revision']);old=None
        for frame in frames:self.validate_frame(frame,old);old=frame
        pending=state['pending']
        if pending is not None:
            exact(pending,{'original','manifest','partial'});need(type(pending['partial']) is dict)
            if pending['original'] is not None:
                self.originals.original(pending['original']);need(pending['original']['index']==len(frames)+1)
            if pending['manifest'] is not None:
                item=pending['manifest'];exact(item,{self.manifest_key,'reference','phase'})
                need(type(item[self.manifest_key]) is int and item[self.manifest_key]==VERSION
                    and item['phase'] in ('planned','saved') and pending['original'] is not None
                    and pending['original']['phase']=='saved')
                self.originals.manifest_reference(item['reference'])
                need(item['reference']['block']==len(frames)//BLOCK+1 and item['reference']['count']==len(frames)%BLOCK+1)
        return deepcopy(state),deepcopy(frames)

    def bound(self):
        self.lock.assert_held();need(not self.failed and same(self.store.read(),self.previous)
            and (self.historical or self.guard() is not False))

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state)
        try:
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:self.failed=True;raise

    def remember(self,name,value):
        self.bound();need(self.state['pending'] is not None and name not in self.state['pending']['partial'])
        self.state['pending']['partial'][name]=deepcopy(value);self.save()

    def storage_intent(self,kind,value):
        self.bound();pending=self.state['pending'];need(pending is not None and kind in ('original','manifest'))
        old=pending[kind]
        if kind=='original':
            self.originals.original(value);need(value['index']==len(self.frames)+1)
            need(value['phase']=='planned' if old is None else value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                and all(same(value[k],old[k]) for k in value if k not in ('phase','file'))
                and (old['phase']=='planned' or same(value['file'],old['file'])))
        else:
            exact(value,{self.manifest_key,'reference','phase'})
            need(type(value[self.manifest_key]) is int and value[self.manifest_key]==VERSION
                and pending['original'] is not None and pending['original']['phase']=='saved')
            self.originals.manifest_reference(value['reference'])
            need(value['phase']=='planned' if old is None else old['phase']=='planned' and value['phase']=='saved'
                and same(value['reference'],old['reference']))
        pending[kind]=deepcopy(value);self.save()

    def validate_frame(self,frame,old=None):
        exact(frame,{'peer','phaseBefore','phaseAfter'});peer=frame['peer'];join=acquisition(peer,self.binding)
        world=peer['world'];need(world['runId']==self.run and peer['renderers']['iosAvatarRenderersVersion']>=4)
        for key,epoch in (('phaseBefore',join['hostBeforeEpochMs']),('phaseAfter',join['hostAfterEpochMs'])):
            p=frame[key];phase_packet(p,run=self.run,area=self.area,request=p['requestId'],epoch=epoch)
            need(p['active'] and p['activations'])
        first,last=frame['phaseBefore'],frame['phaseAfter']
        phase_packet(last,run=self.run,area=self.area,request=last['requestId'],epoch=join['hostAfterEpochMs'],previous=first)
        need(first['activations'][-1]['activatedEpochMs']<=join['hostBeforeEpochMs'])
        if old is not None:
            before=old['peer'];follow_native(before['clockJoin']['nativeAfter'],join['nativeBefore'])
            need(join['hostBeforeMonotonic']>=before['clockJoin']['hostAfterMonotonic'])
            world_packet(world,dict(schemaVersion=1,commandId=world['requestId'],action=WORLD_ACTION,runId=self.run),
                self.pid,join['nativeAfter']['capturedEpochMs'],before['world'])
            packet=peer['receive'];receive_packet(packet,dict(schemaVersion=1,commandId=packet['commandId'],
                action='feature-avatar-receive-observe'),self.pid,join['nativeAfter']['capturedEpochMs'],previous=before['receive'])
            packet=peer['renderers'];avatar_renderers.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],
                action=avatar_renderers.ACTION,runId=self.run),self.pid,join['nativeAfter']['capturedEpochMs'],before['renderers'])
            phase_packet(first,run=self.run,area=self.area,request=first['requestId'],epoch=join['hostBeforeEpochMs'],previous=old['phaseAfter'])
        return first['activations'][-1]['ticket']==last['activations'][-1]['ticket']

    def read(self):
        need(not self.historical);self.bound();need(self.state['pending'] is None and len(self.frames)<MAX_FRAMES)
        live=self.runtime._sources(self.selector);need(same(live['binding'],self.binding))
        observer=live['observer'];clock=live['clock_source'];native=observer.bound_native_observer(clock)
        world=observer.emote_world(clock);renderer=observer.avatar_renderers(clock);receiver=self.runtime._avatar_receive(self.selector)
        if self.frames:
            before=self.frames[-1]['peer'];restore_native(native,before['clockJoin']['nativeAfter'])
            world.last=deepcopy(before['world']);renderer.last=deepcopy(before['renderers']);receiver.restore(before['receive'])
        self.state['pending']=dict(original=None,manifest=None,partial={});self.save()
        status=self.phase.read(self.frames[-1]['phaseAfter'] if self.frames else None);self.remember('phaseBefore',status['status'])
        window=NativeClockAcquisition(native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        window.begin(status['afterEpochMs']);self.remember('nativeStart',window.started)
        originals={}
        for key,read in (('world',lambda:world.read(self.run)),('receive',lambda:receiver.read(receiver.last['sequence'] if receiver.last else 0)),('renderers',lambda:renderer.read(self.run))):
            originals[key]=read();self.remember(key,originals[key])
        fields=[(key,field) for key,p in originals.items() for field in ('capturedEpochMs','sampleEpochMs') if field in p]
        peer=dict(originals,clockJoin=window.finish(originals,fields));self.remember('clockJoin',peer['clockJoin'])
        status=self.phase.read();self.remember('phaseAfter',status['status'])
        frame=dict(peer=peer,phaseBefore=self.state['pending']['partial']['phaseBefore'],phaseAfter=status['status'])
        stable=self.validate_frame(frame,self.frames[-1] if self.frames else None)
        item=self.originals.write(len(self.frames)+1,frame);manifests=self.originals.append(self.state['manifests'],item)
        self.frames.append(deepcopy(frame));self.state.update(revision=len(self.frames),manifests=manifests,pending=None);self.save()
        join=peer['clockJoin'];now,mono=self.epoch_ms(),self.monotonic()
        need(number(now,join['hostAfterEpochMs'],join['hostBeforeEpochMs']+1500)
            and number(mono,join['hostAfterMonotonic'],join['hostBeforeMonotonic']+1.5)
            and now-join['hostBeforeEpochMs']<1500 and mono-join['hostBeforeMonotonic']<1.5)
        if not stable:raise self.phase_changed('Independent receiver acquisition crossed the actual input phase')
        return deepcopy(frame)

    def reference(self,index=None):
        index=len(self.frames) if index is None else index;need(integer(index,1,len(self.frames)))
        return dict(index=index,sha256=digest(self.frames[index-1]))

    def original(self,reference):
        exact(reference,{'index','sha256'});need(integer(reference['index'],1,len(self.frames)))
        frame=self.frames[reference['index']-1];need(digest(frame)==reference['sha256']);return deepcopy(frame)
