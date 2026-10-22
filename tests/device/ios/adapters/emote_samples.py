"""Durable original Emote Vulkan sample owners, including failed challenges.

No image read is replayed after uncertainty. Each original PNG retains its
native command/chunk/file ledger and independently observed GPU retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
import uuid
from adapters.native_clock_join import NativeClockAcquisition,digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_vulkan_world_frame import absent
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.evidence import MarkerNotReady
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_images import compose,originals
from ios.adapters.graphics_history import restore_native
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.avatar_state import session

VERSION=2
READS=(1,2)


class EmoteMarkerPending(MarkerNotReady):pass


def archived_sample(value,*,root,binding,run,role,lock,policy,marker_nonce,marker_url):
    """Decode immutable native/image originals without any SDK or live guard."""
    need(isinstance(lock,ScriptSourceLock));lock.assert_held();context(binding);identifier(run)
    exact(value,{'iosEmoteSampleVersion','runId','role','binding','requestId','ticket','avatarId','phase','payload','owner'})
    need(type(value['iosEmoteSampleVersion']) is int and value['iosEmoteSampleVersion'] in READS
        and value['runId']==run and value['role']==role and same(value['binding'],binding)
        and value['phase'] in ('observed','marker-pending') and value['requestId'].startswith('ios-'))
    identifier(value['requestId'][4:]);identifier(value['ticket'])
    if value['avatarId'] is not None:session(value['avatarId'])
    rows=unpack(value['payload']);owners=unpack(value['owner']);need(len(rows)==len(owners)==1)
    frame,owner=rows[0],owners[0];need(type(frame) is dict and type(owner) is dict
        and same(owner['frame'],frame['capture']) and owner['ticket']==value['ticket']
        and any(same(row['receipt'],frame['retirement']) for row in unpack(owner['transcript'])))
    raw=VulkanWorldFrameOwner.archive_original(owner,Path(root),binding,run,role,0,value['requestId'],lock)
    try:
        result,_subject=compose(run,value['ticket'],binding,frame,raw,policy,marker_nonce=marker_nonce,
            marker_url=marker_url,avatar_id=value['avatarId'],legacy=value['iosEmoteSampleVersion']==1)
    except MarkerNotReady:
        need(value['phase']=='marker-pending');return deepcopy(frame),raw,None,owner['name']
    need(value['phase']=='observed');return deepcopy(frame),raw,result,owner['name']


class IOSEmoteSamples:
    def __init__(self,runtime,selector,scope,root,policy,phase,lock,*,monotonic=time.monotonic,epoch_ms=lambda:time.time()*1000,sleep=time.sleep):
        need(isinstance(runtime,IOSScriptRuntime) and isinstance(scope,IOSEmoteMarkerScope) and isinstance(lock,ScriptSourceLock)
            and isinstance(phase,PhaseFixtureReader) and phase.area=='emotes' and phase.run==scope.run
            and all(callable(fn) for fn in (monotonic,epoch_ms,sleep)))
        self.runtime,self.selector,self.scope=runtime,selector,scope
        self.root,self.policy,self.phase,self.lock=Path(root),deepcopy(policy),phase,lock
        self.run,self.role,self.binding=scope.run,scope.role,deepcopy(context(scope.binding));self.pid=int(self.binding['processIdentity'])
        need(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir()
            and policy.get('source')=='world-render-target' and phase.fixture_url==scope.fixture_url)
        PrivateFeatureState(self.root/'emote-image-root-check')._parent()
        self.monotonic,self.epoch_ms,self.sleep=monotonic,epoch_ms,sleep;lock.assert_held()
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-emote-'+self.role+'-samples.json'))
        need(lock.path==self.store.path.with_name('script-feature-sources.lock'))
        self.previous=self.store.read();self.state=dict(phase='ready',rows=[],seenFrames=[],cursors=dict(native=None,world=None,renderers=None))
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):
        return dict(iosEmoteSamplesVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,
            artifactRoot=str(self.root),imagePolicy=self.policy,payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosEmoteSamplesVersion','runId','role','binding','artifactRoot','imagePolicy','payload'})
        rows=unpack(value['payload']);need(type(value['iosEmoteSamplesVersion']) is int and value['iosEmoteSamplesVersion'] in READS
            and len(rows)==1 and same(value,dict(self.envelope(rows[0]),iosEmoteSamplesVersion=value['iosEmoteSamplesVersion'])));state=rows[0]
        exact(state,{'phase','rows','seenFrames','cursors'});need(state['phase'] in ('ready','reading')
            and type(state['rows']) is list and len(state['rows'])<=128 and type(state['seenFrames']) is list
            and len(set(state['seenFrames']))==len(state['seenFrames']))
        exact(state['cursors'],{'native','world','renderers'});seen=set();frames=[]
        for index,row in enumerate(state['rows']):
            exact(row,{'requestId','ticket','avatarId','phase','sampleSha256'})
            need(type(row['requestId']) is str and row['requestId'].startswith('ios-'));identifier(row['requestId'][4:]);identifier(row['ticket'])
            need(row['requestId'] not in seen and row['phase'] in ('reserved','observed','marker-pending','abandoned'));seen.add(row['requestId'])
            if row['avatarId'] is not None:session(row['avatarId'])
            if row['phase']=='reserved':need(state['phase']=='reading' and index==len(state['rows'])-1 and row['sampleSha256'] is None)
            else:
                sample=self.record(row);frame=unpack(sample['payload'])[0]
                if row['phase']!='abandoned':frames.append(frame['capture']['source']['renderTrace']['frameId'])
        need(frames==state['seenFrames'] and (state['phase']!='reading' or state['rows'] and state['rows'][-1]['phase']=='reserved'))
        if state['phase']=='ready' and state['rows']:
            sample=self.record(state['rows'][-1]);frame=unpack(sample['payload'])[0]
            if state['rows'][-1]['phase']!='abandoned':
                need(same(state['cursors']['native'],frame['clockJoin']['nativeAfter'])
                    and same(state['cursors']['world'],frame['worldAfter']))
                if sample['iosEmoteSampleVersion']>=2 or state['rows'][-1]['avatarId'] is not None:need(same(state['cursors']['renderers'],frame['renderersAfter']))
            else:
                need(same(state['cursors']['native'],frame['clockJoin']['nativeAfter'])
                    and all(same(state['cursors'][key],frame['priorCursors'][key]) for key in ('world','renderers')))
        return deepcopy(state)

    def bound(self):
        self.lock.assert_held();self.scope.bound();need(same(self.store.read(),self.previous))

    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def remember(self,field,value):
        need(field in self.state['cursors'] and self.state['phase']=='reading');self.state['cursors'][field]=deepcopy(value);self.save()

    def sample_store(self,row):
        return PrivateFeatureState(self.root/('emote-sample-'+self.run+'-'+self.role+'-'+row['requestId'][4:]+'.json'))

    def owner(self,row):
        live=self.runtime._sources(self.selector);need(same(live['binding'],self.binding));observer=live['observer']
        path=self.store.path.with_name('graphics-world-frame-'+self.role+'-0-'+row['requestId'][4:]+'.json')
        return VulkanWorldFrameOwner(PrivateFeatureState(path),self.root,self.binding,self.run,self.role,0,row['requestId'],
            lambda intent,receipt:observer.vulkan_world_frame(intent,receipt),live['check'],source_lock=self.lock,
            monotonic=self.monotonic,sleep=self.sleep)

    def record(self,row):
        value=self.sample_store(row).read();need(value is not None and digest(value)==row['sampleSha256'])
        exact(value,{'iosEmoteSampleVersion','runId','role','binding','requestId','ticket','avatarId','phase','payload','owner'})
        need(type(value['iosEmoteSampleVersion']) is int and value['iosEmoteSampleVersion'] in READS and value['runId']==self.run and value['role']==self.role
            and same(value['binding'],self.binding) and all(value[k]==row[k] for k in ('requestId','ticket','avatarId','phase')))
        frames=unpack(value['payload']);need(len(frames)==1 and type(frames[0]) is dict)
        owners=unpack(value['owner']);need(len(owners)==1 and (owners[0] is None or type(owners[0]) is dict))
        if row['phase']=='abandoned':
            from ios.adapters.emote_sample_recovery import validate_abandonment
            validate_abandonment(value,root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        return deepcopy(value)

    def archive(self,row):
        self.bound();need(row['phase'] in ('observed','marker-pending'));sample=self.record(row);frame=unpack(sample['payload'])[0]
        marker=self.scope.state['admission']['marker']
        frame,raw,result,_name=archived_sample(sample,root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock,
            policy=self.policy,marker_nonce=self.scope.state['fileOwnership']['nonce'],marker_url=marker['sourceUrl'])
        return frame,raw,result

    def capture(self,ticket,*,avatar_id=None):
        identifier(ticket);self.bound();need(self.state['phase']=='ready' and self.scope.state['phase']=='ready' and len(self.state['rows'])<128)
        if avatar_id is not None:session(avatar_id)
        phase=self.phase.read();need(phase['ticket']==ticket)
        live=self.runtime._sources(self.selector);need(same(live['binding'],self.binding));observer=live['observer'];clock=live['clock_source']
        native=observer.bound_native_observer(clock);restore_native(native,self.state['cursors']['native'])
        world=observer.emote_world(clock);world.last=deepcopy(self.state['cursors']['world'])
        renderers=observer.avatar_renderers(clock);renderers.last=deepcopy(self.state['cursors']['renderers'])
        row=dict(requestId='ios-'+uuid.uuid4().hex,ticket=ticket,avatarId=avatar_id,phase='reserved',sampleSha256=None)
        self.state['rows'].append(row);self.state['phase']='reading';self.save();owner=self.owner(row)
        need(owner.store.read() is None and self.sample_store(row).read() is None)
        window=NativeClockAcquisition(native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);window.begin(phase['afterEpochMs'])
        self.remember('native',window.started['nativeBefore']);frame={}
        try:
            frame['worldBefore']=world.read(self.run);self.remember('world',frame['worldBefore'])
            frame['renderersBefore']=renderers.read(self.run);self.remember('renderers',frame['renderersBefore'])
            frame['capture'],raw=owner.capture(ticket)
            identity=frame['capture']['source']['renderTrace']['frameId'];need(identity not in self.state['seenFrames'])
        finally:
            if owner.store.read() is not None:frame['retirement']=owner.release()
        frame['renderersAfter']=renderers.read(self.run);self.remember('renderers',frame['renderersAfter'])
        frame['worldAfter']=world.read(self.run);self.remember('world',frame['worldAfter'])
        packets=originals(frame);fields=[(name,field) for name,p in packets.items() for field in ('capturedEpochMs','sampleEpochMs') if field in p]
        frame['clockJoin']=window.finish(packets,fields);self.remember('native',frame['clockJoin']['nativeAfter'])
        status=self.phase.read();need(status['ticket']==ticket)
        marker=self.scope.state['admission']['marker'];pending=False
        try:
            result,_subject=compose(self.run,ticket,self.binding,frame,raw,self.policy,marker_nonce=self.scope.state['fileOwnership']['nonce'],
                marker_url=marker['sourceUrl'],avatar_id=avatar_id)
        except MarkerNotReady:pending=True
        selected='marker-pending' if pending else 'observed'
        sample=dict(iosEmoteSampleVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,requestId=row['requestId'],
            ticket=ticket,avatarId=avatar_id,phase=selected,payload=pack([frame]),owner=pack([owner.store.read()]))
        self.sample_store(row).write(sample,None);need(same(self.sample_store(row).read(),sample) and owner.archive()==raw)
        row.update(phase=selected,sampleSha256=digest(sample));self.state['seenFrames'].append(identity);self.state['phase']='ready';self.save()
        self.archive(row);self.bound()
        join=frame['clockJoin'];now,mono=self.epoch_ms(),self.monotonic()
        need(number(now,join['hostAfterEpochMs'],join['hostBeforeEpochMs']+1500)
            and number(mono,join['hostAfterMonotonic'],join['hostBeforeMonotonic']+1.5)
            and now-join['hostBeforeEpochMs']<1500 and mono-join['hostBeforeMonotonic']<1.5)
        if pending:raise EmoteMarkerPending('mismatch')
        return deepcopy(dict(requestId=row['requestId'],imagePath=str(self.root/owner.name),**result))

    def drain(self):
        """Release only owned original frames; a failed sample remains retained."""
        self.bound();proofs=[]
        for row in self.state['rows']:
            owner=self.owner(row)
            if owner.store.read() is not None:
                proof=owner.release();need(absent(proof));proofs.append(deepcopy(proof))
            else:need(row['phase'] in ('reserved','abandoned'))
        return proofs
