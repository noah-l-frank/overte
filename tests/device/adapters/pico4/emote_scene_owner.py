"""Durable two-object Emote stimulus; no stereo, actor or feature verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time

from adapters.native_avatar_render import NativeAvatarRender,controlled_resources,validate as avatar_packet
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import context
from adapters.pico4.emote_scene_source import NativePicoEmoteScene,command,validate,receipt,ready,retired,INPUT,OBSERVE
from adapters.pico4.emote_view import PicoEmoteView
from adapters.script_journey.history import pack,unpack,same
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet

VERSION=1


class PicoEmoteScene:
    def __init__(self,store,binding,phase,lock,native,avatar,guard,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='emotes' and isinstance(lock,ScriptSourceLock)
            and all(callable(v) for v in (native,avatar,guard,monotonic,sleep)))
        lock.assert_held();self.store,self.binding,self.phase,self.lock=store,deepcopy(context(binding)),phase,lock
        self.native,self.avatar,self.guard,self.monotonic,self.sleep=native,avatar,guard,monotonic,sleep
        self.run,self.pid=phase.run,int(binding['processIdentity'].split(':')[0]);need(integer(self.pid,1))
        self.failed=False;self.clock=None;self.anchor=None
        self.previous=store.read();self.state=dict(phase='reserved',prepare=None,release=None,baseline=None,originals=[],frames=[],readyFrame=None)
        self.bound()
        if self.previous is not None:self.state=self.decode(self.previous)

    def bound(self):
        self.lock.assert_held();need(not self.failed and self.guard() is not False and same(self.store.read(),self.previous))
        now=self.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock));self.clock=now

    def phase_original(self,value,previous=None):
        phase_packet(value,run=self.run,area='emotes',request=value.get('requestId'),epoch=value.get('capturedEpochMs'),previous=previous)
        need(value['activations']);return value['activations'][-1]

    def avatar_original(self,value):
        avatar_packet(value,dict(schemaVersion=1,commandId=value.get('requestId'),action='feature-avatar-render-observe'),self.pid,value.get('capturedEpochMs'))
        controlled_resources(value)
        need(value['source']['cameraMode']=='look at' and value['source'].get('cameraStateVersion')==1
            and value['source']['cameraState']['hmd'] is True and 1.5<=value['source']['cameraState']['boomLength']<=25)

    def decode(self,value):
        exact(value,{'picoEmoteSceneOwnerVersion','runId','fixtureUrl','binding','payload'})
        need(type(value['picoEmoteSceneOwnerVersion']) is int and value['picoEmoteSceneOwnerVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.phase.fixture_url and same(value['binding'],self.binding))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','prepare','release','baseline','originals','frames','readyFrame'})
        need(state['phase'] in ('reserved','preparing','ready','releasing','retired') and type(state['originals']) is list
            and type(state['frames']) is list and len(state['originals'])<=256 and len(state['frames'])<=128)
        if state['phase']=='reserved':
            need(state['prepare'] is state['release'] is state['baseline'] is state['readyFrame'] is None and not state['originals'] and not state['frames']);return state
        self.avatar_original(state['baseline'])
        for key,verb in (('prepare','baseline'),('release','cleanup')):
            row=state[key]
            if row is None:need(key=='release');continue
            exact(row,{'request','phase','attempted'});request=command(row['request']);activation=self.phase_original(row['phase'])
            need(request['action']==INPUT and request['operation']==key and request['runId']==self.run and type(row['attempted']) is bool
                and activation['stimulus']['verb']==verb and (row['phase']['active'] or verb=='cleanup'))
            if key=='prepare':need(request['fixtureUrl']==self.phase.fixture_url and request['ticket']==activation['ticket'])
            else:
                self.phase_original(row['phase'],state['prepare']['phase'])
                need(request['commandId']!=state['prepare']['request']['commandId'])
        need(state['prepare'] is not None and (state['release'] is None or state['prepare']['attempted']))
        need(state['release'] is None if state['phase'] in ('preparing','ready') else state['release'] is not None)
        self.reader(state['originals'])
        for original in state['originals']:
            request=original['request'];packet=original['packet'];need(request['runId']==self.run)
            if request['action']==INPUT:
                intent=state[request['operation']];need(intent is not None and intent['attempted'] and same(request,intent['request']))
            else:need(state['prepare']['attempted'] and packet['source']['originalInput']==state['prepare']['request'])
        previous=state['baseline'];native_packets={r['packet']['requestId']:r['packet'] for r in state['originals']}
        last_phase=state['prepare']['phase'];last_scene=None;last_host=0
        for frame in state['frames']:
            exact(frame,{'scene','avatar','phaseBefore','phaseAfter','hostStarted','hostFinished'})
            need(number(frame['hostStarted'],last_host,1e15) and number(frame['hostFinished'],frame['hostStarted'],frame['hostStarted']+1.5))
            last_host=frame['hostFinished']
            self.phase_original(frame['phaseBefore'],last_phase);self.phase_original(frame['phaseAfter'],frame['phaseBefore'])
            need(same(frame['phaseBefore']['activations'],frame['phaseAfter']['activations'])
                and frame['phaseBefore']['active']==frame['phaseAfter']['active'])
            scene,avatar=frame['scene'],frame['avatar'];need(same(native_packets.get(scene['requestId']),scene))
            need(last_scene is None or scene['sequence']>last_scene['sequence'] and scene['requestId']!=last_scene['requestId']);last_scene=scene
            self.avatar_original(avatar);PicoEmoteView.unchanged(dict(avatar=previous),dict(avatar=avatar))
            need(avatar['sequence']>previous['sequence'] and avatar['requestId']!=previous['requestId']
                and avatar['requestedEpochMs']>=previous['capturedEpochMs'] and scene['instance']==avatar['instance']
                and scene['source']['originalInput']==state['prepare']['request'])
            previous=avatar;last_phase=frame['phaseAfter']
        if state['release'] is not None:
            need(state['frames'] and state['release']['request']['fixtureInstance']==state['frames'][-1]['scene']['source']['fixtureInstance']
                and any(same(frame['phaseAfter'],state['release']['phase']) for frame in state['frames']))
        if state['readyFrame'] is not None:
            need(integer(state['readyFrame'],1,len(state['frames'])));frame=state['frames'][state['readyFrame']-1]
            ready(frame['scene'],state['prepare']['request'],frame['avatar'])
        if state['phase'] in ('ready','retired'):
            need(state['prepare']['attempted'] and state['frames'])
            if state['phase']=='ready':need(state['readyFrame'] is not None)
            else:
                need(state['release'] is not None and state['release']['attempted']);self.retirement(state['frames'])
        return deepcopy(state)

    def reader(self,rows=None):
        value=self.native();need(isinstance(value,NativePicoEmoteScene) and value.pid==self.pid and value.ios is False)
        rows=self.state['originals'] if rows is None else rows
        if rows:value.restore(rows)
        return value

    def save(self):
        self.bound();value=dict(picoEmoteSceneOwnerVersion=VERSION,runId=self.run,fixtureUrl=self.phase.fixture_url,
            binding=self.binding,payload=pack([self.state]))
        try:self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:self.failed=True;raise

    def retain(self,request,packet):
        need(len(self.state['originals'])<256);self.state['originals'].append(dict(request=deepcopy(request),packet=deepcopy(packet)));self.save()

    def fence(self,original):
        latest=self.phase.status(original);need(same(latest['activations'],original['activations']) and latest['active']==original['active'])
        return latest

    def host_fresh(self,avatar,phase):
        need(self.anchor is not None);started,native,host,clock=self.anchor;now=self.monotonic()
        need(number(now,started,started+1.5));fresh(avatar['requestedEpochMs'],native+math.ceil((now-started)*1000))
        fresh(phase['capturedEpochMs'],host+math.ceil((now-started)*1000))

    def delivery(self,avatar,phase):
        self.fence(phase);self.bound();self.host_fresh(avatar,phase)
        native=self.anchor[3]();need(integer(native,self.anchor[1]));fresh(avatar['requestedEpochMs'],native)
        self.host_fresh(avatar,phase)

    def input(self,key):
        row=self.state[key];need(row is not None and not row['attempted']);reader=self.reader();self.delivery(self.state['baseline'] if key=='prepare' else self.state['frames'][-1]['avatar'],row['phase'])
        avatar=self.state['baseline'] if key=='prepare' else self.state['frames'][-1]['avatar']
        original_guard=reader.guard
        def guarded():
            result=original_guard();self.host_fresh(avatar,row['phase']);return result
        reader.guard=guarded
        def intent(request):
            need(same(request,row['request']) and not row['attempted']);row['attempted']=True;self.save();self.delivery(avatar,row['phase'])
        packet=reader.input(row['request'],intent=intent)
        self.retain(row['request'],packet) # Receipt remains distinct from effect.

    def prepare(self,image_extent,marker_roi):
        self.bound();need(self.state['phase']=='reserved' and self.previous is None)
        reader=self.avatar();need(isinstance(reader,NativeAvatarRender) and reader.pid==self.pid and reader.ios is False)
        started=self.monotonic();epoch=reader.clock_ms();host=self.phase.epoch_ms();phase=self.phase.status()
        activation=self.phase_original(phase);need(phase['active'] and activation['stimulus']['verb']=='baseline')
        avatar=reader.read();self.avatar_original(avatar)
        self.anchor=(started,epoch,host,reader.clock_ms)
        request=command(dict(schemaVersion=1,commandId=self.reader()._request(INPUT)['commandId'],action=INPUT,operation='prepare',
            runId=self.run,ticket=activation['ticket'],fixtureUrl=self.phase.fixture_url,imageExtent=image_extent,markerRoi=marker_roi))
        self.state.update(phase='preparing',baseline=avatar,prepare=dict(request=request,phase=phase,attempted=False));self.save()
        self.input('prepare');return self.reconcile()

    def sample(self,verb=None):
        self.bound();need(self.state['prepare'] is not None and self.state['prepare']['attempted'])
        reader=self.reader();avatar=self.avatar();need(isinstance(avatar,NativeAvatarRender) and avatar.pid==self.pid and avatar.ios is False)
        previous=self.state['frames'][-1] if self.state['frames'] else None
        avatar.restore([self.state['baseline'] if previous is None else previous['avatar']])
        started=self.monotonic();epoch=reader.clock_ms();host=self.phase.epoch_ms()
        before=self.phase.status(self.state['prepare']['phase'] if previous is None else previous['phaseAfter'])
        activation=self.phase_original(before)
        if verb is not None:need(activation['stimulus']['verb']==verb and (before['active'] or verb=='cleanup'))
        scene=reader.read(self.run);self.retain(dict(schemaVersion=1,commandId=scene['requestId'],action=OBSERVE,runId=self.run),scene)
        actual=avatar.read();self.avatar_original(actual);PicoEmoteView.unchanged(dict(avatar=self.state['baseline']),dict(avatar=actual))
        need(scene['instance']==actual['instance'] and scene['source']['originalInput']==self.state['prepare']['request'])
        after=self.phase.status(before);need(same(before['activations'],after['activations']) and before['active']==after['active'])
        self.anchor=(started,epoch,host,reader.clock_ms);self.delivery(actual,before);fresh(scene['requestedEpochMs'],max(reader.clock_ms(),epoch+math.ceil((self.monotonic()-started)*1000)))
        frame=dict(scene=scene,avatar=actual,phaseBefore=before,phaseAfter=after,hostStarted=started,hostFinished=self.monotonic())
        need(len(self.state['frames'])<128);self.state['frames'].append(frame);self.save();self.delivery(actual,before)
        fresh(scene['requestedEpochMs'],max(reader.clock_ms(),epoch+math.ceil((self.monotonic()-started)*1000)))
        return frame

    def reconcile(self):
        self.bound();need(self.state['phase'] in ('preparing','ready') and self.state['release'] is None)
        value=self.sample('baseline');ready(value['scene'],self.state['prepare']['request'],value['avatar'])
        if self.state['readyFrame'] is None:self.state['readyFrame']=len(self.state['frames'])
        self.state['phase']='ready';self.save();self.delivery(value['avatar'],value['phaseBefore']);return deepcopy(value)

    def cleanup(self):
        self.bound();need(self.state['phase'] in ('preparing','ready','releasing','retired'))
        if self.state['phase']=='retired':self.state['phase']='releasing';self.save()
        if self.state['release'] is None:
            value=self.sample('cleanup');source=value['scene']['source']
            need(source['phase'] in ('active','failed') and all(r['originalObject'] and r['hostType']=='local' and not r['locked']
                and r['parentId']=='00000000-0000-0000-0000-000000000000' for r in source['entities']))
            request=command(dict(schemaVersion=1,commandId=self.reader()._request(INPUT)['commandId'],action=INPUT,operation='release',
                runId=self.run,fixtureInstance=source['fixtureInstance']))
            self.state.update(phase='releasing',release=dict(request=request,phase=value['phaseAfter'],attempted=False));self.save();self.input('release')
        need(self.state['release']['attempted']);started=self.monotonic()
        for attempt in range(41):
            value=self.sample('cleanup')
            if retired(value['scene']):
                rows=self.quiet_rows(self.state['frames'])
                if len(rows)>=2 and rows[0]['scene']['capturedEpochMs']-rows[-1]['scene']['capturedEpochMs']>=3000 and rows[0]['hostStarted']-rows[-1]['hostFinished']>=3:
                    self.retirement(list(reversed(rows)));self.state['phase']='retired';self.save()
                    self.delivery(value['avatar'],value['phaseBefore']);return self.proof()
            need(attempt<40 and self.monotonic()-started<8);self.sleep(.1)

    @staticmethod
    def quiet_rows(frames):
        rows=[]
        for row in reversed(frames):
            if not retired(row['scene']) or row['phaseBefore']['activations'][-1]['stimulus']['verb']!='cleanup':break
            if rows and (rows[-1]['scene']['capturedEpochMs']-row['scene']['capturedEpochMs']>1500
                    or rows[-1]['hostStarted']-row['hostFinished']>1.5
                    or not same(rows[-1]['phaseAfter']['activations'],row['phaseAfter']['activations'])
                    or rows[-1]['phaseAfter']['active']!=row['phaseAfter']['active']):break
            rows.append(row)
        return rows

    @staticmethod
    def retirement(frames):
        rows=PicoEmoteScene.quiet_rows(frames)
        need(len(rows)>=2 and rows[0]['scene']['capturedEpochMs']-rows[-1]['scene']['capturedEpochMs']>=3000
            and rows[0]['avatar']['capturedEpochMs']-rows[-1]['avatar']['capturedEpochMs']>=3000
            and rows[0]['hostStarted']-rows[-1]['hostFinished']>=3
            and all(a['scene']['capturedEpochMs']-b['scene']['capturedEpochMs']<=1500
                and a['hostStarted']-b['hostFinished']<=1.5 for a,b in zip(rows,rows[1:])))
        return deepcopy(rows)

    def proof(self):
        self.bound();need(self.state['phase']=='retired');self.retirement(self.state['frames'])
        return deepcopy(self.previous) # Keep originals for the future parent join.
