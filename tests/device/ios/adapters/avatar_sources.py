"""Durable original Avatar acquisitions through the candidate-qualified runtime.

Each group retains separate native source clocks, original widgets, genuine
phase input metadata and exact immutable evidence bytes. Partial acquisition
or storage remains owned; it cannot be replayed as a fresh successful group.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time

from adapters.native_clock_join import NativeClockAcquisition, digest, validate_join
from adapters.native_feature_observation import exact, integer, need, number
from adapters.native_script_membership import accept as accept_membership
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack, unpack, same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader, validate as phase_packet
from ios.adapters import avatar_state, avatar_renderers, avatar_social_http, people_model, avatar_scripts, avatar_entities
from ios.adapters.avatar_controls import IOSAvatarIO, project
from ios.adapters.avatar_originals import IOSAvatarOriginals, MAX_FRAMES, BLOCK
from ios.adapters.graphics_history import restore_native, follow_native
from ios.adapters.normal_input import observation as native_widgets

VERSION=2
READS=(1,2)
CHANNELS=dict(state=avatar_state,renderers=avatar_renderers,http=avatar_social_http,people=people_model,scripts=avatar_scripts,entities=avatar_entities)
ACQUISITIONS=dict(state='iosAvatarStateAcquisitionVersion',renderers='iosAvatarRenderersAcquisitionVersion',
    http='iosAvatarSocialHttpAcquisitionVersion',people='iosPeopleModelAcquisitionVersion',scripts='iosAvatarScriptsAcquisitionVersion',
    entities='iosAvatarEntitiesAcquisitionVersion')
VERSIONS=dict(state=('iosAvatarStateVersion',2),renderers=('iosAvatarRenderersVersion',4),
    http=('iosAvatarSocialHttpVersion',2),people=('iosPeopleModelVersion',1),scripts=('iosAvatarScriptsVersion',2),entities=('iosAvatarEntitiesVersion',1))


class AvatarPhaseChanged(NativeUIError):pass
class AvatarSourcePending(NativeUIError):pass


class IOSAvatarSources:
    def __init__(self,store,root,binding,run,role,lock,guard,phase,*,readers=None,historical=False,
                 monotonic=time.monotonic,epoch_ms=lambda:time.time()*1000):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and type(historical) is bool
             and role in ('primary','actor') and all(callable(fn) for fn in (guard,monotonic,epoch_ms)))
        self.store,self.root,self.binding=store,Path(root),deepcopy(context(binding));self.run=identifier(run)
        self.role,self.lock,self.guard,self.historical=role,lock,guard,historical
        self.monotonic,self.epoch_ms=monotonic,epoch_ms
        need(store.path.name=='ios-avatar-'+role+'-sources.json' and lock.path==store.path.with_name('script-feature-sources.lock'))
        self.pid=int(binding['processIdentity']);need(self.pid>0 and str(self.pid)==binding['processIdentity'])
        self.phase,self.readers=phase,readers
        if not historical:
            need(isinstance(phase,PhaseFixtureReader) and phase.area=='avatar-people' and phase.run==run)
            exact(readers,set(CHANNELS)|{'native','ui'})
            for name,module in CHANNELS.items():need(isinstance(readers[name],module.IOSPlacesModel) and readers[name].pid==self.pid)
            need(isinstance(readers['ui'],IOSAvatarIO) and readers['native'].pid==self.pid)
        self.frames=[];self.previous=None;self.failed=False
        self.state=dict(phase='ready',revision=0,manifests=[],pending=None)
        self.originals=IOSAvatarOriginals(root,binding,run,role,self.file_guard,self.storage_intent,monotonic=monotonic)
        lock.assert_held()
        if not historical:need(guard() is not False)
        self.previous=store.read()
        if self.previous is not None:self.state,self.frames=self.decode(self.previous)
        if not historical and self.frames:self.restore_readers()
        if not historical:need(guard() is not False)

    def file_guard(self):
        # Private immutable originals are not product acquisitions. Keep their
        # real lock/file checks without reacquiring SDK data for every file.
        # Live constructor boundaries, saves, captures and transports retain
        # their full candidate guard; historical reads remain SDK-free.
        self.lock.assert_held();return True

    def envelope(self,state,*,version=VERSION):
        return dict(iosAvatarSourcesVersion=version,runId=self.run,role=self.role,binding=self.binding,artifactRoot=str(self.root),payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosAvatarSourcesVersion','runId','role','binding','artifactRoot','payload'})
        version=value['iosAvatarSourcesVersion'];need(type(version) is int and version in READS)
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0],version=version)))
        state=rows[0];exact(state,{'phase','revision','manifests','pending'})
        need(state['phase'] in ('ready','reading') and integer(state['revision'],0,MAX_FRAMES))
        frames=self.originals.restore(state['manifests'],state['revision']);previous=None;retired=set()
        for frame in frames:
            need(version>=2 or 'avatarSourceGroupVersion' not in frame)
            self.validate_frame(frame,previous)
            _members,retired=accept_membership(avatar_scripts.members(previous['originals']['scripts']['source']) if previous else None,
                avatar_scripts.members(frame['originals']['scripts']['source']),retired,frame['originals']['scripts']['clockAfter']['epochMs'])
            previous=frame
        if state['phase']=='ready':need(state['pending'] is None)
        else:
            pending=state['pending'];exact(pending,{'original','manifest','partial'});need(type(pending['partial']) is dict)
            if pending['original'] is not None:
                self.originals.original(pending['original']);need(pending['original']['index']==state['revision']+1)
            if pending['manifest'] is not None:
                manifest=pending['manifest'];exact(manifest,{'avatarManifestVersion','reference','phase'})
                need(type(manifest['avatarManifestVersion']) is int and manifest['avatarManifestVersion']==1
                    and manifest['phase'] in ('planned','saved') and pending['original'] is not None and pending['original']['phase']=='saved')
                self.originals.manifest_reference(manifest['reference'])
                need(manifest['reference']['block']==state['revision']//BLOCK+1 and manifest['reference']['count']==state['revision']%BLOCK+1)
        # unpack() owns state, and restore() opens/parses each frame afresh.
        # Validators retain neither tree, so no second copy is needed here.
        return state,frames

    def bound(self):
        self.lock.assert_held();need(not self.failed and same(self.store.read(),self.previous)
            and (self.historical or self.guard() is not False))
    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state)
        try:self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:self.failed=True;raise
    def remember(self,name,value):
        need(self.state['phase']=='reading' and name not in self.state['pending']['partial'])
        self.state['pending']['partial'][name]=deepcopy(value);self.save()
    def storage_intent(self,kind,value):
        need(not self.historical and self.state['phase']=='reading' and kind in ('original','manifest'));pending=self.state['pending'];old=pending[kind]
        if kind=='original':
            self.originals.original(value);need(value['index']==len(self.frames)+1)
            if old is None:need(value['phase']=='planned')
            else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
                and (old['phase']=='planned' or same(old['file'],value['file'])))
        else:
            exact(value,{'avatarManifestVersion','reference','phase'});self.originals.manifest_reference(value['reference'])
            need(value['avatarManifestVersion']==1 and type(value['avatarManifestVersion']) is int
                and pending['original'] is not None and pending['original']['phase']=='saved'
                and value['reference']['block']==len(self.frames)//BLOCK+1 and value['reference']['count']==len(self.frames)%BLOCK+1)
            need(value['phase']=='planned' if old is None else old['phase']=='planned' and value['phase']=='saved' and same(old['reference'],value['reference']))
        pending[kind]=deepcopy(value);self.save()

    def validate_frame(self,frame,previous=None):
        current='avatarSourceGroupVersion' in frame
        exact(frame,{'originals','acquisitions','ui','clockJoin','phaseBefore','phaseAfter'}|({'avatarSourceGroupVersion'} if current else set()))
        if current:need(type(frame['avatarSourceGroupVersion']) is int and frame['avatarSourceGroupVersion']==2)
        originals=frame['originals'];channels=CHANNELS if current else {key:value for key,value in CHANNELS.items() if key!='entities'}
        need(previous is None or 'entities' not in previous['originals'] or 'entities' in originals)
        exact(originals,set(channels)|{'native','widgets'})
        acquisitions=frame['acquisitions'];exact(acquisitions,set(channels))
        clock=validate_join(frame['clockJoin'],originals);first,last=clock['nativeBefore'],clock['nativeAfter']
        need(first['processId']==last['processId']==self.pid)
        queries=[first['requestId'],last['requestId'],originals['native']['requestId']]+[originals[name]['requestId'] for name in channels]
        need(len(set(queries))==len(queries))
        if previous:follow_native(previous['clockJoin']['nativeAfter'],first)
        for name,module in channels.items():
            packet=originals[name];need(type(packet) is dict)
            query=dict(schemaVersion=1,commandId=packet.get('requestId'),action=module.ACTION,runId=self.run)
            prior=previous['originals'].get(name) if previous is not None else None
            module.validate(packet,query,self.pid,previous=prior)
            version_key,version=VERSIONS[name];need(type(packet[version_key]) is int
                and (packet[version_key]==version or name=='state' and packet[version_key]==3
                    or name in ('http','scripts') and packet[version_key]==1))
            need(packet['processId']==self.pid and packet['runId']==self.run
                 and first['capturedEpochMs']<=packet['clockBefore']['epochMs']<=packet['clockAfter']['epochMs']<=last['capturedEpochMs'])
            acquisition=acquisitions[name]
            exact(acquisition,{'hostBeforeMonotonic','hostAfterMonotonic','nativeRequestedEpochMs','nativeAfterEpochMs','originalSha256',ACQUISITIONS[name]})
            need(type(acquisition[ACQUISITIONS[name]]) is int and acquisition[ACQUISITIONS[name]]==1
                 and acquisition['originalSha256']==digest(packet)
                 and first['capturedEpochMs']<=acquisition['nativeRequestedEpochMs']<=packet['clockBefore']['epochMs']
                 and packet['clockAfter']['epochMs']<=acquisition['nativeAfterEpochMs']<=last['capturedEpochMs']
                 and number(acquisition['hostBeforeMonotonic'],clock['hostBeforeMonotonic'],clock['hostAfterMonotonic'])
                 and number(acquisition['hostAfterMonotonic'],acquisition['hostBeforeMonotonic'],clock['hostAfterMonotonic']))
        native_widgets(originals['widgets'],self.pid,originals['widgets']['sampleEpochMs'])
        need(same(project(originals['widgets']),frame['ui']) and originals['native']['processId']==self.pid)
        need(originals['people']['source']['tabletShown']==frame['ui']['open'])
        people_pages=[row for row in frame['ui']['controls'] if row['id']=='people.page']
        active_people=[row for row in originals['people']['source']['roots'] if row['active']]
        if people_pages:
            need(len(active_people)==1 and active_people[0]['rootId']==people_pages[0]['rootId']
                 and active_people[0]['qmlSource']==people_pages[0]['qmlSource'])
        else:need(not active_people)
        self_rows=[row for row in originals['renderers']['source']['avatars'] if row['self']]
        if self_rows:need(len(self_rows)==1 and self_rows[0]['sessionId']==originals['state']['source']['sessionId'])
        follow_native(first,originals['native']);follow_native(originals['native'],last)
        for name,host in (('phaseBefore','hostBeforeEpochMs'),('phaseAfter','hostAfterEpochMs')):
            status=frame[name];phase_packet(status,run=self.run,area='avatar-people',request=status['requestId'],epoch=clock[host])
            need(status['active'] and status['activations'])
        phase_packet(frame['phaseAfter'],run=self.run,area='avatar-people',request=frame['phaseAfter']['requestId'],
            epoch=clock['hostAfterEpochMs'],previous=frame['phaseBefore'])
        need(frame['phaseBefore']['activations'][-1]['activatedEpochMs']<=clock['hostBeforeEpochMs'])
        if previous:
            phase_packet(frame['phaseBefore'],run=self.run,area='avatar-people',request=frame['phaseBefore']['requestId'],
                epoch=clock['hostBeforeEpochMs'],previous=previous['phaseAfter'])
            left,right=previous['ui']['scope'],frame['ui']['scope']
            need(all(left[key]==right[key] for key in ('instance','generation','processId'))
                 and right['sourceSequence']>left['sourceSequence'] and right['sequence']>=left['sequence']
                 and right['elapsedMs']>=left['elapsedMs'] and right['capturedEpochMs']>=left['capturedEpochMs'])
        return frame['phaseBefore']['activations'][-1]['ticket']==frame['phaseAfter']['activations'][-1]['ticket']

    def restore_readers(self):
        originals=self.frames[-1]['originals']
        for name in CHANNELS:
            reader=self.readers[name];need(reader.last is None)
            if name not in originals:continue # Legacy v1 contains no entity-return facts.
            if name=='scripts':reader.restore([frame['originals'][name] for frame in self.frames])
            else:reader.last=deepcopy(originals[name])
        restore_native(self.readers['native'],self.frames[-1]['clockJoin']['nativeAfter'])

    def read(self):
        need(not self.historical);self.bound()
        if self.state['phase']!='ready':raise AvatarSourcePending('An incomplete original Avatar acquisition remains owned')
        need(len(self.frames)<MAX_FRAMES)
        self.state.update(phase='reading',pending=dict(original=None,manifest=None,partial={}));self.save()
        previous=self.frames[-1] if self.frames else None;r=self.readers
        phase=self.phase.read(previous['phaseAfter'] if previous else None);self.remember('phaseBefore',phase['status'])
        window=NativeClockAcquisition(r['native'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        window.begin(phase['afterEpochMs']);self.remember('nativeStart',window.started)
        originals=dict(native=r['native'].read(r['native'].sequence));self.remember('native',originals['native']);acquisitions={}
        for name in CHANNELS:
            originals[name]=r[name].read(self.run);acquisitions[name]=deepcopy(r[name].acquisition)
            self.remember(name,dict(original=originals[name],acquisition=acquisitions[name]))
        ui=r['ui'].capture();originals['widgets']=deepcopy(r['ui'].original_packet);self.remember('widgets',originals['widgets'])
        clock=window.finish(originals,[('native','capturedEpochMs'),('widgets','sampleEpochMs')]);self.remember('clockJoin',clock)
        final=self.phase.status(phase['status']);self.remember('phaseAfter',final)
        frame=dict(avatarSourceGroupVersion=2,originals=originals,acquisitions=acquisitions,ui=ui,clockJoin=clock,phaseBefore=phase['status'],phaseAfter=final)
        stable=self.validate_frame(frame,previous)
        original=self.originals.write(len(self.frames)+1,frame);manifests=self.originals.append(self.state['manifests'],original)
        self.frames.append(deepcopy(frame));self.state.update(phase='ready',revision=len(self.frames),manifests=manifests,pending=None);self.save()
        self.bound();now=self.epoch_ms();mono=self.monotonic()
        need(number(now,clock['hostAfterEpochMs'],clock['hostBeforeEpochMs']+1500)
            and number(mono,clock['hostAfterMonotonic'],clock['hostBeforeMonotonic']+1.5)
            and now-clock['hostBeforeEpochMs']<1500 and mono-clock['hostBeforeMonotonic']<1.5)
        if not stable:raise AvatarPhaseChanged('Original Avatar acquisition crossed the actual input phase')
        return deepcopy(frame)
