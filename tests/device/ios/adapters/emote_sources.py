"""Durable iOS original Emote acquisitions, preserving separate native clocks.

A partial read remains owned. Reopening cannot resend it or mint a new envelope
around saved packets. Original current poses are independent of user inputs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
from adapters.emote_rig_measurements import source,continuation
from adapters.native_animation_history import accept as animation_history
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_script_observation import NativeScriptObservation,validate as script_packet
from adapters.native_script_roots import NativeScriptRoots,validate as roots_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters.emote_controls import IOSEmoteIO,project
from ios.adapters.emote_originals import IOSEmoteOriginals,MAX_FRAMES,BLOCK
from ios.adapters.graphics_history import restore_native
from ios.adapters.emote_native_prefix import follow as follow_native
from ios.adapters.emote_world import original as world_original,actual_domain,validate as world_packet,ACTION as WORLD_ACTION

VERSION=2
READS=(1,2)


class EmotePhaseChanged(NativeUIError):pass


class IOSEmoteSources:
    def __init__(self,store,root,binding,run,role,lock,guard,phase,*,readers=None,
                 historical=False,monotonic=time.monotonic,epoch_ms=lambda:time.time()*1000):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
            and type(historical) is bool and role in ('primary','actor')
            and all(callable(fn) for fn in (guard,monotonic,epoch_ms)))
        self.store,self.root,self.binding=store,Path(root),deepcopy(context(binding))
        self.run,self.role,self.lock,self.guard=identifier(run),role,lock,guard
        self.historical,self.monotonic,self.epoch_ms=historical,monotonic,epoch_ms
        need(store.path.name=='ios-emote-'+role+'-sources.json'
            and lock.path==store.path.with_name('script-feature-sources.lock'))
        self.pid=int(binding['processIdentity']);need(self.pid>0 and str(self.pid)==binding['processIdentity'])
        self.phase,self.readers=phase,readers
        if not historical:
            need(isinstance(phase,PhaseFixtureReader) and phase.area=='emotes' and phase.run==run)
            need(set(readers) in ({'roots','scripts','native','ui'},{'roots','scripts','native','ui','world'}))
            need(isinstance(readers['roots'],NativeScriptRoots) and readers['roots'].ios
                and isinstance(readers['scripts'],NativeScriptObservation) and readers['scripts'].ios
                and isinstance(readers['ui'],IOSEmoteIO))
            need(readers['roots'].pid==readers['scripts'].pid==readers['native'].pid==self.pid)
        self.frames=[];self.previous=None;self.failed=False
        self.state=dict(phase='ready',revision=0,manifests=[],pending=None)
        self.originals=IOSEmoteOriginals(root,binding,run,role,guard,self.storage_intent,monotonic=monotonic)
        lock.assert_held();self.previous=store.read()
        if self.previous is not None:self.state,self.frames=self.decode(self.previous)
        if not historical and self.frames:self.restore_readers()

    def envelope(self,state,version=VERSION):
        return dict(iosEmoteSourcesVersion=version,runId=self.run,role=self.role,binding=self.binding,
            artifactRoot=str(self.root),payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosEmoteSourcesVersion','runId','role','binding','artifactRoot','payload'})
        version=value['iosEmoteSourcesVersion'];need(type(version) is int and version in READS)
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0],version)))
        state=rows[0];exact(state,{'phase','revision','manifests','pending'})
        need(state['phase'] in ('ready','reading') and integer(state['revision'],0,MAX_FRAMES))
        frames=self.originals.restore(state['manifests'],state['revision']);old=None
        for frame in frames:self.validate_frame(frame,old);old=frame
        if state['phase']=='ready':need(state['pending'] is None)
        else:
            pending=state['pending'];exact(pending,{'original','manifest','partial'})
            need(type(pending['partial']) is dict)
            if pending['original'] is not None:
                self.originals.original(pending['original']);need(pending['original']['index']==state['revision']+1)
            if pending['manifest'] is not None:
                item=pending['manifest'];exact(item,{'emoteManifestVersion','reference','phase'})
                need(type(item['emoteManifestVersion']) is int and item['emoteManifestVersion']==1
                    and item['phase'] in ('planned','saved') and pending['original'] is not None
                    and pending['original']['phase']=='saved')
                self.originals.manifest_reference(item['reference'])
                need(item['reference']['block']==state['revision']//BLOCK+1
                    and item['reference']['count']==state['revision']%BLOCK+1)
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
        need(self.state['phase']=='reading' and name not in self.state['pending']['partial'])
        self.state['pending']['partial'][name]=deepcopy(value);self.save()

    def storage_intent(self,kind,value):
        need(self.state['phase']=='reading' and kind in ('original','manifest'))
        pending=self.state['pending'];old=pending[kind]
        if kind=='original':
            self.originals.original(value);need(value['index']==len(self.frames)+1)
            if old is None:need(value['phase']=='planned')
            else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                and all(same(value[k],old[k]) for k in value if k not in ('phase','file'))
                and (old['phase']=='planned' or same(old['file'],value['file'])))
        else:
            exact(value,{'emoteManifestVersion','reference','phase'})
            need(pending['original'] is not None and pending['original']['phase']=='saved')
            self.originals.manifest_reference(value['reference'])
            need(value['reference']['block']==len(self.frames)//BLOCK+1
                and value['reference']['count']==len(self.frames)%BLOCK+1)
            need(value['phase']=='planned' if old is None else old['phase']=='planned'
                and value['phase']=='saved' and same(old['reference'],value['reference']))
        pending[kind]=deepcopy(value);self.save()

    def validate_frame(self,frame,old=None):
        fields={'group','widgets','ui','clockJoin','phaseBefore','phaseAfter'}
        exact(frame,fields|({'world'} if 'world' in frame else set()))
        group=frame['group'];originals=dict(group,widgets=frame['widgets'])
        if 'world' in frame:originals['world']=frame['world']
        clock=validate_join(frame['clockJoin'],originals)
        selected,current,_=source(group,self.pid,clock['nativeAfter']['capturedEpochMs'])
        follow_native(clock['nativeBefore'],current);follow_native(current,clock['nativeAfter'])
        need(selected['profile']['ui']=='native-qml'
            and selected['profile']['id'] in ('touch-one-shot-chooser-v1','phone-one-shot-hide-v1'))
        need(same(project(frame['widgets']),frame['ui']) and frame['widgets']['processId']==self.pid
            and frame['widgets']['sampleEpochMs']>=group['rootsAfter']['capturedEpochMs'])
        if 'world' in frame:
            world=world_original(frame['world']);actual_domain(world)
            need(world['runId']==self.run and world['processId']==self.pid
                and frame['widgets']['sampleEpochMs']<=world['clockBefore']['epochMs']<=world['clockAfter']['epochMs']
                <=clock['nativeAfter']['capturedEpochMs'])
        for name in ('phaseBefore','phaseAfter'):
            status=frame[name]
            phase_packet(status,run=self.run,area='emotes',request=status['requestId'],
                epoch=clock['hostBeforeEpochMs'] if name=='phaseBefore' else clock['hostAfterEpochMs'])
            need(status['active'] and bool(status['activations']))
        first,last=frame['phaseBefore'],frame['phaseAfter']
        phase_packet(last,run=self.run,area='emotes',request=last['requestId'],epoch=clock['hostAfterEpochMs'],previous=first)
        need(first['activations'][-1]['activatedEpochMs']<=clock['hostBeforeEpochMs'])
        pages=[row for row in frame['ui']['controls'] if row['id']=='emote.page']
        if pages:
            from urllib.parse import urlsplit,urlunsplit
            from posixpath import dirname
            import hashlib
            assigned=urlsplit(selected['assignedUrl']);path=dirname(assigned.path)+'/PhoneEmote.qml'
            actual='qrc:'+path if assigned.scheme=='qrc' else urlunsplit((assigned.scheme,'',path,'',''))
            need(pages[0]['componentSourceSha256']==hashlib.sha256(actual.encode()).hexdigest())
        if old:
            follow_native(old['clockJoin']['nativeAfter'],clock['nativeBefore'])
            if 'world' in old:
                need('world' in frame)
                world_packet(frame['world'],dict(schemaVersion=1,commandId=frame['world']['requestId'],action=WORLD_ACTION,runId=self.run),
                    self.pid,clock['nativeAfter']['capturedEpochMs'],old['world'])
            before=old['group'];continuation(before['native'],current,self.pid)
            roots_packet(group['rootsBefore'],dict(schemaVersion=1,commandId=group['rootsBefore']['commandId'],
                action='feature-script-roots-observe'),self.pid,clock['nativeAfter']['capturedEpochMs'],previous=before['rootsAfter'])
            old_selected,_,_=source(before,self.pid,old['clockJoin']['nativeAfter']['capturedEpochMs'])
            need(same(selected,old_selected) and clock['hostBeforeEpochMs']>=old['clockJoin']['hostAfterEpochMs'])
            phase_packet(first,run=self.run,area='emotes',request=first['requestId'],epoch=clock['hostBeforeEpochMs'],previous=old['phaseAfter'])
            left,right=old['ui']['scope'],frame['ui']['scope']
            need(all(left[k]==right[k] for k in ('instance','generation','processId'))
                and right['sourceSequence']>left['sourceSequence'] and right['sequence']>=left['sequence']
                and right['elapsedMs']>=left['elapsedMs'] and right['capturedEpochMs']>=left['capturedEpochMs'])
        return first['activations'][-1]['ticket']==last['activations'][-1]['ticket']

    def restore_readers(self):
        old=self.frames[-1]['group'];r=self.readers
        r['roots'].restore(old['rootsAfter'])
        scripts=r['scripts'];scripts.restore_history([])
        for frame in self.frames:
            packet=frame['group']['script']
            script_packet(packet,packet['requestId'],self.pid,packet['capturedEpochMs'])
            need(scripts.instance in (None,packet['instance']) and packet['sequence']>scripts.sequence
                and packet['capturedEpochMs']>=scripts.captured_epoch)
            transition=scripts._history_transition(packet,require_effects=True,require_code_identity=True,
                require_load_history=True,require_membership=True)
            scripts._commit_history(packet,transition)
        last_native=self.frames[-1]['clockJoin']['nativeAfter'];restore_native(r['native'],last_native)
        if 'world' in self.frames[-1] and 'world' in r:r['world'].last=deepcopy(self.frames[-1]['world'])
        previous=None
        for frame in self.frames:
            for packet in (frame['clockJoin']['nativeBefore'],frame['group']['native'],frame['clockJoin']['nativeAfter']):
                previous=animation_history(previous,packet['animation']['rigId'],packet['animation']['history'])
        r['native'].animation_history=previous
        r['native'].rig=last_native['animation']['rigId'];r['native'].rig_sequence=last_native['animation']['evaluationSequence']

    def read(self):
        need(not self.historical);self.bound();need(self.state['phase']=='ready' and len(self.frames)<MAX_FRAMES)
        self.state.update(phase='reading',pending=dict(original=None,manifest=None,partial={}));self.save()
        previous=self.frames[-1] if self.frames else None;r=self.readers
        phase=self.phase.read(previous['phaseAfter'] if previous else None);self.remember('phaseBefore',phase['status'])
        window=NativeClockAcquisition(r['native'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        window.begin(phase['afterEpochMs']);self.remember('nativeStart',window.started)
        before=r['roots'].read(r['roots'].last['sequence'] if r['roots'].last else 0);self.remember('rootsBefore',before)
        script=r['scripts'].read(r['scripts'].sequence,require_effects=True,require_code_identity=True,require_load_history=True,require_membership=True)
        self.remember('script',script)
        native=r['native'].read(r['native'].sequence,require_animation=True,require_animation_history=True);self.remember('native',native)
        after=r['roots'].read(before['sequence']);self.remember('rootsAfter',after)
        ui=r['ui'].capture();widgets=r['ui'].original_packet;self.remember('widgets',widgets)
        group=dict(rootsBefore=before,script=script,native=native,rootsAfter=after)
        originals=dict(group,widgets=widgets)
        need('world' in r)
        world=r['world'].read(self.run);self.remember('world',world);originals['world']=world
        ending=dict(nativeAfter=r['native'].read(r['native'].sequence),hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic())
        self.remember('nativeEnd',ending)
        clock=dict(window.started,**ending,originalsSha256=digest(originals),sourceTimes=[
            dict(source=name,field=field,epochMs=packet[field]) for name,packet in originals.items()
            for field in ('capturedEpochMs','sampleEpochMs') if field in packet])
        self.remember('clockJoin',clock)
        final=self.phase.status(phase['status']);self.remember('phaseAfter',final)
        frame=dict(group=group,widgets=widgets,ui=ui,world=world,clockJoin=clock,phaseBefore=phase['status'],phaseAfter=final)
        stable=self.validate_frame(frame,previous)
        original=self.originals.write(len(self.frames)+1,frame)
        manifests=self.originals.append(self.state['manifests'],original)
        self.frames.append(deepcopy(frame));self.state.update(phase='ready',revision=len(self.frames),manifests=manifests,pending=None);self.save()
        self.bound();now=self.epoch_ms();mono=self.monotonic()
        need(number(now,clock['hostAfterEpochMs'],clock['hostBeforeEpochMs']+1500)
            and number(mono,clock['hostAfterMonotonic'],clock['hostBeforeMonotonic']+1.5)
            and now-clock['hostBeforeEpochMs']<1500 and mono-clock['hostBeforeMonotonic']<1.5)
        if not stable:raise EmotePhaseChanged('Original Emote acquisition crossed the actual input phase')
        return deepcopy(frame)
