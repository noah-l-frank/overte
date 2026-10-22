"""Own the actual Emote domain fixture, original frames and Browser retirement.

Input receipts, native node absence, source files and Browser drainage remain
distinct. This component implements no Emote input, pixel or peer verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from pathlib import Path
import time
from urllib.parse import urlsplit
import uuid

from adapters.native_avatar_render import NativeAvatarRender,validate as avatar_packet
from adapters.native_phone_touch_state import NativePhoneTouchState,validate as touch_packet,released as touch_released
from adapters.normal_ui import NativeUIError
from adapters.native_phone_avatar_configuration import NativePhoneAvatarConfiguration,validate as config_packet,controlled
from adapters.native_phone_emote_fixture import NativePhoneEmoteFixture,validate as fixture_packet,input_command,ready as fixture_ready,retired as fixture_retired,layout
from adapters.native_phone_web_runtime import NativePhoneWebRuntime,validate as web_packet,continuity as web_continuity,active_marker,released as web_released
from adapters.native_graphics_subject import NativeGraphicsSubject,validate as world_packet
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_packet
from overte_phone_emote_originals import PhoneEmoteOriginals,MAX_FRAMES,BLOCK
from overte_phone_emote_view import PhoneEmoteView
from overte_phone_graphics_scene import operation,rotation_equal
from overte_phone_graphics_measurements import near
from overte_phone_script_history import pack,unpack,same

VERSION=1
FRAME={'configuration','avatar','touch','world','web','phaseBefore','phaseAfter','epochMs','hostEpochMs','hostStartedMonotonicMs','hostObservedMonotonicMs'}


class SceneOriginals(PhoneEmoteOriginals):
    # Same private, exclusive, inode/digest-bound file/manifest engine. The
    # existing source/input readers retain their original closed kind set.
    KINDS=frozenset({'scene'})


class PhoneEmoteScene:
    def __init__(self,view,artifact_root,image_extent,marker_roi,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(view,PhoneEmoteView) and callable(monotonic) and callable(sleep));view.lock.assert_held()
        self.view,self.adapter,self.selector,self.phase,self.lock=view,view.adapter,view.selector,view.phase,view.lock
        self.run,self.binding,self.pid=view.run,deepcopy(view.binding),view.pid
        self.root=Path(artifact_root);self.extent,self.marker=deepcopy(image_extent),deepcopy(marker_roi)
        self.monotonic,self.sleep,self.started,self.clock=monotonic,sleep,None,None
        self.failed=False;self.required_phase=None;self.expected_ticket=None;self.delivery_anchor=None
        self.fixture=self.adapter._emote_fixture_observer(self.selector,read_only=True)
        need(isinstance(self.fixture,NativePhoneEmoteFixture) and self.fixture.pid==self.pid and self.fixture.ios is False)
        self.guard=self.fixture.guard
        self.store=PrivateFeatureState(view.store.path.with_name('phone-emote-scene.json'))
        self.previous=self.store.read();self.frames=[]
        self.state=dict(phase='reserved',revision=0,manifests=[],pending=None,prepare=None,release=None,window=None)
        self.originals=SceneOriginals(self.root,self.binding,self.run,'primary',self.bound,self.storage_intent,kind='scene',monotonic=self.monotonic)
        self.command('prepare','a'*32) # Validate external construction inputs before any mutation.
        if self.previous is not None:self.state,self.frames=self.decode(self.previous)

    def bound(self):
        self.lock.assert_held();need(not self.failed and self.guard() is not False and same(self.store.read(),self.previous))
        now=self.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<45));self.clock=now

    def command(self,operation,ticket=None):
        value=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-emote-fixture-input',operation=operation,runId=self.run)
        if operation=='prepare':value.update(fixtureUrl=self.phase.fixture_url,ticket=identifier(ticket),imageExtent=deepcopy(self.extent),markerRoi=deepcopy(self.marker))
        else:
            need(self.frames and 'fixture' in self.frames[-1]['frame'])
            value['fixtureInstance']=self.frames[-1]['frame']['fixture']['source']['fixtureInstance']
        return input_command(value)

    def packet(self,frame,kind,previous=None,*,closed=False):
        exact(frame,FRAME|({'fixture'} if kind=='fixture' else set()));need(kind in ('baseline','fixture')
            and integer(frame['epochMs'],1) and number(frame['hostEpochMs'],1,1e15)
            and number(frame['hostStartedMonotonicMs'],0,1e18) and number(frame['hostObservedMonotonicMs'],frame['hostStartedMonotonicMs'],1e18))
        requests=(('configuration',config_packet,'phone-avatar-configuration-observe'),('avatar',avatar_packet,'feature-avatar-render-observe'),
            ('touch',touch_packet,'phone-touch-state-observe'),('world',world_packet,'feature-graphics-subject-observe'))
        for key,validator,action in requests:
            value=frame[key];request=dict(schemaVersion=1,commandId=value.get('requestId'),action=action)
            if key=='world':request['runId']=self.run;validator(value,request,self.pid,frame['epochMs'],require_avatar=True)
            else:validator(value,request,self.pid,frame['epochMs'])
        controlled(frame['configuration'],frame['avatar']);touch_released(frame['touch'])
        pose=frame['world']['source']['avatarPose'];actual=frame['avatar']['source']['pose']
        need(near(pose['feetPosition'],actual['feetPosition'],.01) and rotation_equal(pose['orientation'],actual['orientation'])
            and near(pose['modelScale'],actual['modelScale'],.0001))
        world_view=frame['world']['source']['view'];avatar_view=frame['avatar']['source']['view']
        need(world_view['mode']==frame['avatar']['source']['cameraMode']
            and all(near(world_view[key],avatar_view[key],.0001) for key in world_view if key!='mode'))
        need(frame['configuration']['instance']==frame['avatar']['instance']==frame['world']['instance']==frame['touch']['instance'])
        web=frame['web'];web_packet(web,dict(schemaVersion=1,commandId=web.get('commandId'),action='feature-phone-web-runtime-observe',
            runId=self.run,fixtureUrl=self.phase.fixture_url),self.pid,frame['epochMs']);need(web['status']=='ready')
        if kind=='fixture':
            value=frame['fixture'];fixture_packet(value,dict(schemaVersion=1,commandId=value.get('requestId'),
                action='phone-emote-fixture-observe',runId=self.run),self.pid,frame['epochMs'])
            need(value['instance']==frame['avatar']['instance'])
        before,after=frame['phaseBefore'],frame['phaseAfter']
        phase_packet(before,run=self.run,area='emotes',request=before.get('requestId'),epoch=frame['hostEpochMs'],
            previous=previous['phaseAfter'] if previous else None)
        phase_packet(after,run=self.run,area='emotes',request=after.get('requestId'),epoch=frame['hostEpochMs'],previous=before)
        need(before['active'] is (not closed) and before['activations']
            and same(before['activations'],after['activations']) and after['active'] is (not closed))
        if closed:need(before['activations'][-1]['stimulus']['verb']=='cleanup')
        if previous:
            need(frame['hostStartedMonotonicMs']>=previous['hostObservedMonotonicMs'])
            for key,_,_ in requests:
                a,b=previous[key],frame[key];need(a['instance']==b['instance'] and b['sequence']>a['sequence']
                    and b['requestedEpochMs']>=a['capturedEpochMs'])
            web_continuity(previous['web'],web,self.pid,self.phase.fixture_url)
            need(all(same(previous['configuration']['source'][key],frame['configuration']['source'][key]) for key in ('configured','loadedGeometry')))
            a,b=previous['avatar']['source'],frame['avatar']['source']
            need(all(same(a[k],b[k]) for k in ('modelInstance','rigId','geometry')) and near(a['pose']['feetPosition'],b['pose']['feetPosition'],.01)
                and rotation_equal(a['pose']['orientation'],b['pose']['orientation']) and near(a['pose']['modelScale'],b['pose']['modelScale'],.0001))

    def decode(self,value):
        exact(value,{'emoteSceneVersion','runId','fixtureUrl','binding','artifactRoot','imageExtent','markerRoi','payload'})
        need(type(value['emoteSceneVersion']) is int and value['emoteSceneVersion']==VERSION and value['runId']==self.run
            and value['fixtureUrl']==self.phase.fixture_url and same(context(value['binding']),self.binding)
            and value['artifactRoot']==str(self.root) and same(value['imageExtent'],self.extent) and same(value['markerRoi'],self.marker))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','revision','manifests','pending','prepare','release','window'})
        need(state['phase'] in ('reserved','baseline','preparing','active','releasing','released') and integer(state['revision'],0,MAX_FRAMES))
        frames=self.originals.restore(state['manifests'],state['revision']);previous=None
        seen_fixture=False
        for index,row in enumerate(frames):
            exact(row,{'emoteSceneFrameVersion','kind','frame'});need(type(row['emoteSceneFrameVersion']) is int
                and row['emoteSceneFrameVersion']==VERSION and row['kind'] in ('baseline','fixture')
                and (row['kind']=='fixture' or not seen_fixture) and (index>0 or row['kind']=='baseline'))
            seen_fixture=seen_fixture or row['kind']=='fixture'
            self.packet(row['frame'],row['kind'],previous);previous=row['frame']
        for key in ('prepare','release'):
            if state[key] is not None:
                row=state[key];exact(row,{'command','binding','fixturePhase'});input_command(row['command'])
                need(row['command']['runId']==self.run and row['command']['operation']==key and same(context(row['binding']),self.binding))
                phase=row['fixturePhase'];phase_packet(phase,run=self.run,area='emotes',request=phase.get('requestId'),epoch=phase.get('capturedEpochMs'))
                need(phase['active'] and phase['activations'] and phase['activations'][-1]['stimulus']['verb']==('baseline' if key=='prepare' else 'cleanup'))
                if key=='prepare':need(row['command']['fixtureUrl']==self.phase.fixture_url and same(row['command']['imageExtent'],self.extent)
                    and same(row['command']['markerRoi'],self.marker) and row['command']['ticket']==phase['activations'][-1]['ticket'])
        pending=state['pending']
        if pending is not None:
            exact(pending,{'index','kind','original','manifest'})
            need(integer(pending['index'],len(frames)+1,len(frames)+1) and pending['kind'] in ('baseline','fixture')
                and (pending['kind']=='fixture' and state['prepare'] is not None or pending['kind']=='baseline' and state['prepare'] is None and not seen_fixture))
            if pending['original'] is not None:self.originals.original(pending['original']);need(pending['original']['index']==pending['index'])
            if pending['manifest'] is not None:
                exact(pending['manifest'],{'emoteManifestVersion','reference','phase'})
                need(type(pending['manifest']['emoteManifestVersion']) is int and pending['manifest']['emoteManifestVersion']==1 and pending['manifest']['phase'] in ('planned','saved')
                    and pending['original'] is not None and pending['original']['phase']=='saved')
                self.originals.manifest_reference(pending['manifest']['reference'])
                need(pending['manifest']['reference']['block']==len(frames)//BLOCK+1
                    and pending['manifest']['reference']['count']==len(frames)%BLOCK+1)
        if state['phase']=='reserved':need(not frames and state['prepare'] is state['release'] is None)
        else:need(frames)
        if state['phase'] in ('active','releasing','released'):need(state['prepare'] is not None)
        if state['phase']=='baseline':need(state['prepare'] is None and not seen_fixture)
        if state['release'] is not None:
            need(state['phase'] in ('releasing','released'))
            actual=[row['frame']['fixture'] for row in frames if row['kind']=='fixture']
            need(actual and state['release']['command']['fixtureInstance']==actual[-1]['source']['fixtureInstance'])
        if frames:
            baseline=frames[0]['frame'];self.eligible(baseline)
            for row in frames[1:]:
                frame=row['frame']
                if row['kind']=='fixture':need(state['prepare'] is not None and same(frame['fixture']['source']['originalInput'],state['prepare']['command']))
                self.foreign_world(baseline,frame)
        if state['window'] is not None:
            exact(state['window'],{'start','complete'});need(integer(state['window']['start'],0,len(frames)-1) and type(state['window']['complete']) is bool
                and state['release'] is not None)
            self.window(frames,state['window']['start'],state['window']['complete'])
        if state['phase']=='active' and pending is None:need(frames[-1]['kind']=='fixture');self.active(frames[-1]['frame'],baseline=frames[0]['frame'])
        if state['phase']=='released':
            need(state['release'] is not None and state['window'] is not None and state['window']['complete'])
            if pending is None:self.drained(frames[-1]['frame'],baseline=frames[0]['frame'])
        return deepcopy(state),deepcopy(frames)

    def save(self):
        self.bound();self.state['revision']=len(self.frames)
        value=dict(emoteSceneVersion=VERSION,runId=self.run,fixtureUrl=self.phase.fixture_url,binding=deepcopy(self.binding),
            artifactRoot=str(self.root),imageExtent=deepcopy(self.extent),markerRoi=deepcopy(self.marker),payload=pack([self.state]))
        try:
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:self.failed=True;raise

    def storage_intent(self,kind,value):
        pending=self.state['pending'];need(pending is not None and kind in ('original','manifest'))
        old=pending[kind]
        if kind=='original':
            self.originals.original(value);need(value['index']==pending['index'])
            if old is None:need(value['phase']=='planned')
            else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
                and (old['phase']=='planned' or same(old['file'],value['file'])))
        else:
            exact(value,{'emoteManifestVersion','reference','phase'});need(type(value['emoteManifestVersion']) is int and value['emoteManifestVersion']==1
                and pending['original'] is not None and pending['original']['phase']=='saved')
            self.originals.manifest_reference(value['reference'])
            need(value['phase']=='planned' if old is None else old['phase']=='planned' and value['phase']=='saved'
                and same(old['reference'],value['reference']))
        pending[kind]=deepcopy(value);self.save()

    def record(self,kind,frame):
        need(self.state['pending'] is not None);self.packet(frame,kind,self.frames[-1]['frame'] if self.frames else None)
        row=dict(emoteSceneFrameVersion=VERSION,kind=kind,frame=deepcopy(frame))
        reference=self.originals.write(len(self.frames)+1,row);manifests=self.originals.append(self.state['manifests'],reference)
        self.frames.append(row);self.state.update(pending=None,manifests=manifests)
        if kind=='baseline':self.state['phase']='baseline'
        self.save()

    def query(self,kind,*,closed=False):
        self.bound();need(self.state['pending'] is None and (closed or len(self.frames)<MAX_FRAMES))
        if closed:need(kind=='fixture' and self.state['phase']=='released')
        started=self.monotonic();previous=self.frames[-1]['frame'] if self.frames else None
        readers=dict(configuration=self.adapter._avatar_configuration_observer(self.selector,read_only=True),
            avatar=self.adapter._avatar_render_observer(self.selector,read_only=True),touch=self.adapter._touch_state_observer(self.selector,read_only=True),world=self.adapter._graphics_subject_observer(self.selector,read_only=True),
            web=self.adapter._web_runtime_observer(self.selector,read_only=True),fixture=self.adapter._emote_fixture_observer(self.selector,read_only=True))
        classes=dict(configuration=NativePhoneAvatarConfiguration,avatar=NativeAvatarRender,touch=NativePhoneTouchState,
            world=NativeGraphicsSubject,web=NativePhoneWebRuntime,fixture=NativePhoneEmoteFixture)
        need(all(isinstance(readers[key],cls) for key,cls in classes.items()) and all(reader.pid==self.pid for reader in readers.values())
            and all(readers[key].ios is False for key in readers if key!='web'))
        if previous:
            for key in ('configuration','avatar','touch'):readers[key].restore([previous[key]])
            readers['world'].last=deepcopy(previous['world']);readers['web'].last=deepcopy(previous['web'])
            if 'fixture' in previous:readers['fixture'].restore([previous['fixture']])
        epoch=readers['configuration'].clock_ms();host=self.phase.epoch_ms();need(integer(epoch,1) and number(host,1,1e15));anchor=self.monotonic()
        before=self.phase.status(previous['phaseAfter'] if previous else None)
        need(before['active'] is (not closed) and before['activations'] and before['activations'][-1]['stimulus']['verb']==self.required_phase
            and (self.expected_ticket is None or before['activations'][-1]['ticket']==self.expected_ticket))
        need(kind in ('baseline','fixture') and (kind=='baseline')==(self.state['prepare'] is None))
        if not closed:
            self.state['pending']=dict(index=len(self.frames)+1,kind=kind,original=None,manifest=None);self.save()
        frame=dict(configuration=readers['configuration'].read(),avatar=readers['avatar'].read(),touch=readers['touch'].read(),
            world=readers['world'].read(self.run,require_avatar=True),web=readers['web'].read(self.run,self.phase.fixture_url),phaseBefore=before)
        if kind=='fixture':frame['fixture']=readers['fixture'].read(self.run)
        frame.update(phaseAfter=self.phase.status(before),epochMs=readers['configuration'].clock_ms(),hostEpochMs=self.phase.epoch_ms(),
            hostStartedMonotonicMs=anchor*1000,hostObservedMonotonicMs=self.monotonic()*1000)
        self.packet(frame,kind,previous,closed=closed)
        if kind=='fixture':need(self.state['prepare'] is not None and same(frame['fixture']['source']['originalInput'],self.state['prepare']['command']))
        if self.frames:self.foreign_world(self.frames[0]['frame'],frame)
        if closed:self.drained(frame)
        elif self.state['phase']=='released':
            try:self.drained(frame)
            except NativeUIError:self.state.update(phase='releasing',window=None)
        if not closed:self.record(kind,frame)
        self.bound()
        self.delivery_anchor=(anchor,epoch,host,readers['configuration'].clock_ms)
        need(self.monotonic()-started<5);self.delivery(frame);return deepcopy(frame)

    def delivery(self,frame):
        self.bound();need(self.delivery_anchor is not None)
        started,epoch,host,clock=self.delivery_anchor
        current=self.phase.status(frame['phaseAfter']);need(same(current['activations'],frame['phaseAfter']['activations'])
            and current['active'] is frame['phaseAfter']['active'] and current['retiredEpochMs']==frame['phaseAfter']['retiredEpochMs'])
        now=clock();host_now=self.phase.epoch_ms();self.bound();end=self.monotonic()
        need(integer(now,epoch) and number(host_now,host,1e15) and number(end,started,1e15) and end-started<5)
        for key in ('configuration','avatar','touch','world')+ (('fixture',) if 'fixture' in frame else ()):
            fresh(frame[key]['requestedEpochMs'],max(now,epoch+math.ceil((end-started)*1000)))
        fresh(frame['web']['source']['nativeBefore']['capturedEpochMs'],max(now,epoch+math.ceil((end-started)*1000)))
        fresh(frame['phaseBefore']['capturedEpochMs'],max(host_now,host+math.ceil((end-started)*1000)))

    def eligible(self,frame):
        self.view.ready(dict(configuration=frame['configuration'],avatar=frame['avatar'],touch=frame['touch']))
        world=frame['world']['source'];need(urlsplit(world['sceneUrl']).scheme=='hifi' and not world['entities'] and len(world['absentIds'])==7)
        need(world['scan']['scannedEntities']<=256)
        source=frame['web']['source']
        for key in ('nativeBefore','nativeAfter'):
            need(not any(row['sourceOwned'] or row['documentOwned'] or row['creationOwned'] for row in source[key]['views']))
        need(not any(row['sourceOwned'] or row['documentOwned'] for row in source['java']['views'])
            and not any(row['sourceOwned'] for row in source['java']['creations']))

    def foreign_world(self,baseline,frame):
        original,current=baseline['world']['source'],frame['world']['source'];owned={row['id'] for row in frame.get('fixture',{}).get('source',{}).get('objects',[]) if row['id'] is not None}
        a={row['id']:row['sha256'] for row in original['scan']['unowned']};b={row['id']:row['sha256'] for row in current['scan']['unowned'] if row['id'] not in owned}
        present={row['id'] for row in current['scan']['unowned'] if row['id'] in owned}
        need(original['sceneUrl']==current['sceneUrl'] and not current['entities'] and set(original['absentIds'])==set(current['absentIds'])
            and a==b and current['scan']['scannedEntities']==original['scan']['scannedEntities']+len(present))

    def active(self,frame,*,baseline=None):
        fixture_ready(frame['fixture'],frame['avatar']);self.foreign_world(baseline or self.frames[0]['frame'],frame)
        url=self.phase.fixture_url+'tickets/'+frame['fixture']['source']['originalInput']['ticket']+'/graphics-marker.v1.html'
        return active_marker(frame['web'],url)

    def drained(self,frame,*,baseline=None):
        original=baseline or self.frames[0]['frame']
        fixture_retired(frame['fixture']);web_released(frame['web']);self.foreign_world(original,frame)
        need(frame['world']['source']['scan']['scannedEntities']==original['world']['source']['scan']['scannedEntities'])

    def window(self,frames,start,complete=False):
        need(integer(start,1,len(frames)-1))
        selected=frames[start:];need(selected and all(row['kind']=='fixture' for row in selected))
        baseline=frames[0]['frame']
        for row in selected:self.drained(row['frame'],baseline=baseline)
        first,last=selected[0]['frame'],selected[-1]['frame']
        elapsed=math.floor(last['hostStartedMonotonicMs'])-math.ceil(first['hostObservedMonotonicMs'])
        native=last['configuration']['requestedEpochMs']-first['epochMs']
        enough=len(selected)>=3 and elapsed>=3000 and native>=3000
        if complete:need(enough)
        return enough

    def input(self,command,binding):
        self.bound();key=command['operation'];need(key in ('prepare','release') and self.state[key] is None and same(binding,self.binding))
        phase=self.phase.status(self.frames[-1]['frame']['phaseAfter'])
        need(phase['active'] and phase['activations'] and phase['activations'][-1]['stimulus']['verb']==self.required_phase
            and (self.expected_ticket is None or phase['activations'][-1]['ticket']==self.expected_ticket))
        if key=='prepare':need(command['ticket']==phase['activations'][-1]['ticket'])
        self.state[key]=dict(command=deepcopy(command),binding=deepcopy(binding),fixturePhase=phase);self.save()
        self.expected_ticket=phase['activations'][-1]['ticket']

    @operation
    def prepare(self):
        self.required_phase='baseline';self.bound();need(self.state['pending'] is None)
        self.expected_ticket=self.state['prepare']['fixturePhase']['activations'][-1]['ticket'] if self.state['prepare'] else None
        with self.adapter.existing_input_session(self.selector):
            if self.state['phase'] in ('reserved','baseline','preparing') and self.state['prepare'] is None:
                frame=self.query('baseline');self.eligible(frame)
                active=frame['phaseAfter']['activations'][-1];command=self.command('prepare',active['ticket'])
                preview=dict(originalInput=command,originalView=deepcopy(frame['avatar']['source']['view'])|dict(mode='selfie',
                    feetPosition=frame['avatar']['source']['pose']['feetPosition'],modelScale=frame['avatar']['source']['pose']['modelScale'],
                    boomLength=frame['configuration']['source']['boomLength']))
                for row in layout(preview).values():need(math.sqrt(sum(v*v for v in row['position']))+math.sqrt(sum((v/2)**2 for v in row['dimensions']))<120)
                self.state['phase']='preparing';self.save()
                self.adapter._emote_fixture_input(self.selector,command,lock=self.lock,intent=self.input)
            need(self.state['phase'] in ('preparing','active') and self.state['prepare'] is not None)
            for attempt in range(32):
                frame=self.query('fixture');need(same(frame['fixture']['source']['originalInput'],self.state['prepare']['command']))
                fixture_ready(frame['fixture'],frame['avatar']);self.foreign_world(self.frames[0]['frame'],frame)
                try:self.active(frame)
                except NativeUIError:
                    need(attempt<31);self.sleep(.1);self.bound();continue
                self.state['phase']='active';self.save();self.delivery(frame);return {'performed':True}
            need(False)

    @operation
    def cleanup(self):
        self.required_phase='cleanup';self.bound();need(self.state['pending'] is None and self.state['prepare'] is not None)
        self.expected_ticket=self.state['release']['fixturePhase']['activations'][-1]['ticket'] if self.state['release'] else None
        with self.adapter.existing_input_session(self.selector):
            need(self.state['phase'] in ('preparing','active','releasing','released'))
            if self.state['release'] is None:
                # A lost prepare return is recovered only by an original current
                # matching native lease, never by guessing IDs or replaying add.
                frame=self.query('fixture');need(same(frame['fixture']['source']['originalInput'],self.state['prepare']['command']))
                self.state['phase']='releasing';self.save()
                self.adapter._emote_fixture_input(self.selector,self.command('release'),lock=self.lock,intent=self.input)
            for attempt in range(32):
                frame=self.query('fixture')
                try:self.drained(frame)
                except NativeUIError:
                    self.state['window']=None;self.save()
                    need(attempt<31);self.sleep(.25);self.bound();continue
                if self.state['window'] is None:self.state['window']=dict(start=len(self.frames)-1,complete=False)
                if self.window(self.frames,self.state['window']['start']):
                    self.state['window']['complete']=True;self.state['phase']='released';self.save();self.delivery(frame);return {'performed':True}
                self.save();need(attempt<31);self.sleep(.25);self.bound()
            need(False)

    @operation
    def retire(self,retain):
        self.required_phase='cleanup';self.bound();need(callable(retain) and self.state['phase']=='released' and self.state['pending'] is None)
        self.expected_ticket=self.state['release']['fixturePhase']['activations'][-1]['ticket']
        frame=self.query('fixture');self.drained(frame);self.window(self.frames,self.state['window']['start'],True)
        need(retain(deepcopy(frame)) is not False);self.delivery(frame)
        self.store.discard(self.previous);need(self.store.read() is None);self.previous=None;self.delivery(frame);return deepcopy(frame)


    def retirement_archive(self,value):
        """Reopen the old scene originals and verify the frozen closed group."""
        exact(value,{'emoteSceneRetirementVersion','header','frame'})
        need(type(value['emoteSceneRetirementVersion']) is int and value['emoteSceneRetirementVersion']==1)
        state,frames=self.decode(value['header'])
        need(state['phase']=='released' and state['pending'] is None)
        frame=value['frame'];previous=frames[-1]['frame'];self.packet(frame,'fixture',previous,closed=True)
        need(same(frame['phaseBefore']['activations'],previous['phaseAfter']['activations'])
            and frame['phaseBefore']['activations'][-1]['ticket']==state['release']['fixturePhase']['activations'][-1]['ticket']
            and same(frame['fixture']['source']['originalInput'],state['prepare']['command']))
        self.drained(frame,baseline=frames[0]['frame']);self.window(frames,state['window']['start'],True)
        return deepcopy(value)

    @operation
    def retire_closed(self,retain,*,retained=None):
        """Do not append an inactive group to the active-only v1 originals."""
        self.required_phase='cleanup';self.bound();need(callable(retain));started=self.monotonic()
        if retained is None:
            need(self.previous is not None and self.state['phase']=='released' and self.state['pending'] is None)
            self.expected_ticket=self.state['release']['fixturePhase']['activations'][-1]['ticket']
            frame=self.query('fixture',closed=True)
            value=self.retirement_archive(dict(emoteSceneRetirementVersion=1,header=deepcopy(self.previous),frame=frame))
        else:
            value=self.retirement_archive(retained)
            need(self.previous is None or same(self.previous,value['header']))
            current=self.phase.status(value['frame']['phaseAfter'])
            need(not current['active'] and same(current['activations'],value['frame']['phaseAfter']['activations']))
        need(retain(deepcopy(value)) is not False);self.bound();need(self.monotonic()-started<5)
        if retained is None:self.delivery(value['frame'])
        if self.previous is not None:
            self.store.discard(value['header']);need(self.store.read() is None);self.previous=None
        self.bound();need(self.monotonic()-started<5)
        if retained is None:self.delivery(value['frame'])
        return deepcopy(value)
