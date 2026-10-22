"""Retain interrupted passive Emote reads without replaying their requests.

The original incomplete owner and every opened artifact inode remain owned in
the recovery ledger. Their facts never become a fresh/public observation. A
later distinct acquisition must preserve every actually returned source prefix.
This component sends no SDK, native command, normal input or file deletion.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import stat
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_script_observation import NativeScriptObservation,validate as script_packet
from adapters.native_script_roots import validate as roots_packet
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters.emote_controls import project
from ios.adapters.emote_native_prefix import follow as native_prefix
from ios.adapters.emote_sources import IOSEmoteSources
from ios.adapters.emote_world import validate as world_packet,ACTION as WORLD_ACTION

VERSION=1


class IOSEmoteSourceRecovery:
    @classmethod
    def archive(cls,value,sources):
        """Reconstruct only local original storage; no live guard or SDK call."""
        need(isinstance(sources,IOSEmoteSources));sources.lock.assert_held()
        archived=IOSEmoteSources(sources.store,sources.root,sources.binding,sources.run,sources.role,sources.lock,
            lambda:True,None,historical=True)
        scope=object.__new__(cls);scope.sources,scope.lock=archived,archived.lock
        scope.store=PrivateFeatureState(sources.store.path.with_name('ios-emote-'+sources.role+'-source-recovery.json'))
        scope.previous=scope.store.read();scope.state=scope.decode(value)
        return scope

    def __init__(self,sources):
        need(isinstance(sources,IOSEmoteSources) and not sources.historical)
        self.sources,self.lock=sources,sources.lock
        self.store=PrivateFeatureState(sources.store.path.with_name('ios-emote-'+sources.role+'-source-recovery.json'))
        self.previous=self.store.read();self.state=dict(records=[],pending=None)
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):
        s=self.sources
        return dict(iosEmoteSourceRecoveryVersion=VERSION,runId=s.run,role=s.role,binding=s.binding,
            artifactRoot=str(s.root),payload=pack([state]))

    def bound(self):
        self.sources.bound();need(same(self.store.read(),self.previous))

    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def record_store(self,index):
        need(integer(index,1,128));s=self.sources
        return PrivateFeatureState(s.root/('emote-source-abandoned-'+s.run+'-'+s.role+'-'+str(index)+'.json'))

    def file(self,original):
        """Inspect only an inode already acquired by the interrupted writer."""
        self.sources.originals.original(original);path=self.sources.originals.path(original)
        if original['phase']=='planned':
            need(not path.exists());return None
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            # Partial contents are retained honestly, not validated as a
            # finished OriginalFrameStore frame or completed native read.
            self.sources.originals.file(path,stream.fileno(),original);raw=stream.read(original['bytes']+1)
            self.sources.originals.file(path,stream.fileno(),original)
        need(len(raw)<=original['bytes'])
        if original['phase']=='saved':
            need(len(raw)==original['bytes'] and hashlib.sha256(raw).hexdigest()==original['sha256'])
            self.sources.originals.read(original)
        return dict(file=deepcopy(original['file']),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

    def attempt(self,value):
        exact(value,{'iosEmoteAbandonedSourceVersion','index','priorOwner','partialFile'})
        need(type(value['iosEmoteAbandonedSourceVersion']) is int and value['iosEmoteAbandonedSourceVersion']==VERSION
            and integer(value['index'],1,128))
        state,frames=self.sources.decode(value['priorOwner']);need(state['phase']=='reading' and state['pending'] is not None)
        original=state['pending']['original']
        need(value['partialFile'] is None if original is None else same(value['partialFile'],self.file(original)))
        return state

    def record(self,reference):
        exact(reference,{'index','sha256'});value=self.record_store(reference['index']).read()
        need(value is not None and digest(value)==reference['sha256'] and value['index']==reference['index'])
        self.attempt(value);return value

    def decode(self,value):
        exact(value,{'iosEmoteSourceRecoveryVersion','runId','role','binding','artifactRoot','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'records','pending'});need(type(state['records']) is list and len(state['records'])<=128)
        for index,reference in enumerate(state['records'],1):need(reference['index']==index);self.record(reference)
        if state['pending'] is not None:
            pending=state['pending'];exact(pending,{'attempt','reference','targetOwner'})
            prior=self.attempt(pending['attempt']);need(pending['attempt']['index']==len(state['records'])+1)
            target=deepcopy(prior);target.update(phase='ready',pending=None)
            need(same(pending['targetOwner'],self.sources.envelope(target)))
            if pending['reference'] is not None:need(same(self.record(pending['reference']),pending['attempt']))
        else:need(len(state['records'])==128 or self.record_store(len(state['records'])+1).read() is None)
        return deepcopy(state)

    def recover(self):
        self.bound();s=self.sources;pending=self.state['pending']
        if pending is None:
            if s.state['phase']=='ready':return True
            need(s.state['phase']=='reading' and s.state['pending'] is not None and len(self.state['records'])<128)
            original=s.state['pending']['original']
            attempt=dict(iosEmoteAbandonedSourceVersion=VERSION,index=len(self.state['records'])+1,
                priorOwner=deepcopy(s.previous),partialFile=None if original is None else self.file(original))
            self.attempt(attempt);target=deepcopy(s.state);target.update(phase='ready',pending=None)
            pending=dict(attempt=attempt,reference=None,targetOwner=s.envelope(target));self.state['pending']=pending;self.save()
        prior,target=pending['attempt']['priorOwner'],pending['targetOwner']
        need(same(s.previous,prior) or same(s.previous,target))
        index=pending['attempt']['index'];store=self.record_store(index);saved=store.read()
        if saved is None:store.write(pending['attempt'],None)
        else:need(same(saved,pending['attempt']))
        reference=dict(index=index,sha256=digest(pending['attempt']));self.record(reference)
        if pending['reference'] is None:pending['reference']=reference;self.save()
        else:need(same(pending['reference'],reference))
        if same(s.previous,prior):
            # Normal source CAS owns the transition; no completed frame, native
            # counter, event, source generation or input is reset here.
            s.state=unpack(target['payload'])[0];s.save()
        need(same(s.previous,target));self.state['records'].append(reference);self.state['pending']=None;self.save()
        return True

    def follow(self,frame,*,historical=False):
        """A fresh successful read must extend every returned abandoned fact."""
        if historical:self.lock.assert_held();need(self.sources.historical)
        else:self.bound()
        need(self.state['pending'] is None);s=self.sources
        need(s.validate_frame(frame));current=frame['group'];native=frame['clockJoin']['nativeBefore']
        for reference in self.state['records']:
            attempt=self.record(reference);old=self.attempt(attempt);partial=old['pending']['partial']
            # The original record can also contain older completed frames. Only
            # subsequent acquisitions follow this interrupted attempt.
            if old['revision']>=len(s.frames):continue
            packets=[]
            if 'nativeStart' in partial:packets.append(partial['nativeStart']['nativeBefore'])
            if 'native' in partial:packets.append(partial['native'])
            if 'nativeEnd' in partial:packets.append(partial['nativeEnd']['nativeAfter'])
            for packet in packets:native_prefix(packet,native)
            if 'script' in partial:
                packet=partial['script'];script_packet(packet,packet['requestId'],s.pid,packet['capturedEpochMs'])
                need(current['script']['instance']==packet['instance'] and current['script']['sequence']>packet['sequence']
                    and current['script']['requestedEpochMs']>=packet['capturedEpochMs'])
                reader=NativeScriptObservation(lambda _:need(False),lambda:need(False),lambda:need(False),lambda:True,s.pid,
                    ios=packet['requestId'].startswith('ios-'))
                requirements=dict(require_effects=packet['source'].get('effectSourceVersion')==1,require_code_identity=True,
                    require_load_history=packet['source'].get('loadSourceVersion')==1,require_membership=True)
                transition=reader._history_transition(packet,**requirements);reader._commit_history(packet,transition)
                reader._history_transition(current['script'],**requirements)
            roots=partial.get('rootsAfter',partial.get('rootsBefore'))
            if roots is not None:
                roots_packet(current['rootsBefore'],dict(schemaVersion=1,commandId=current['rootsBefore']['commandId'],
                    action='feature-script-roots-observe'),s.pid,frame['clockJoin']['nativeAfter']['capturedEpochMs'],previous=roots)
            if 'widgets' in partial:
                a,b=project(partial['widgets'])['scope'],frame['ui']['scope']
                need(all(a[k]==b[k] for k in ('instance','generation','processId')) and b['sourceSequence']>a['sourceSequence']
                    and b['sequence']>=a['sequence'] and b['elapsedMs']>=a['elapsedMs'] and b['capturedEpochMs']>=a['capturedEpochMs'])
            if 'world' in partial:
                world=frame['world'];world_packet(world,dict(schemaVersion=1,commandId=world['requestId'],action=WORLD_ACTION,runId=s.run),
                    s.pid,frame['clockJoin']['nativeAfter']['capturedEpochMs'],partial['world'])
            phase=partial.get('phaseAfter',partial.get('phaseBefore'))
            if phase is not None:
                status=frame['phaseBefore'];phase_packet(status,run=s.run,area='emotes',request=status['requestId'],
                    epoch=frame['clockJoin']['hostBeforeEpochMs'],previous=phase)
        return True
