"""Retain interrupted passive receive/render reads without replaying their requests.

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
from adapters.native_clock_join import digest,validate_join
from adapters.native_feature_observation import exact,integer,need,number,validate as native_packet
from ios.adapters.avatar_sources import IOSAvatarSources,CHANNELS,ACQUISITIONS
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters import avatar_scripts
from ios.adapters.avatar_controls import project
from adapters.native_script_membership import accept as accept_membership
from ios.adapters.graphics_history import follow_native as native_prefix

VERSION=1


class IOSAvatarSourceRecovery:
    @classmethod
    def archive(cls,value,sources):
        """Reconstruct only local original storage; no live guard or SDK call."""
        need(isinstance(sources,IOSAvatarSources));sources.lock.assert_held()
        archived=IOSAvatarSources(sources.store,sources.root,sources.binding,sources.run,sources.role,sources.lock,
            lambda:True,None,historical=True)
        scope=object.__new__(cls);scope.sources,scope.lock=archived,archived.lock
        scope.store=PrivateFeatureState(sources.store.path.with_name('ios-avatar-'+sources.role+'-source-recovery.json'))
        scope.previous=scope.store.read();scope.state=scope.decode(value)
        return scope

    def __init__(self,sources):
        need(isinstance(sources,IOSAvatarSources) and not sources.historical)
        self.sources,self.lock=sources,sources.lock
        self.store=PrivateFeatureState(sources.store.path.with_name('ios-avatar-'+sources.role+'-source-recovery.json'))
        self.previous=self.store.read();self.state=dict(records=[],pending=None)
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):
        s=self.sources
        return dict(iosAvatarSourceRecoveryVersion=VERSION,runId=s.run,role=s.role,binding=s.binding,
            artifactRoot=str(s.root),payload=pack([state]))

    def bound(self):
        self.sources.bound();need(same(self.store.read(),self.previous))

    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def record_store(self,index):
        need(integer(index,1,128));s=self.sources
        return PrivateFeatureState(s.root/('avatar-source-abandoned-'+s.run+'-'+s.role+'-'+str(index)+'.json'))

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
        exact(value,{'iosAvatarAbandonedSourceVersion','index','priorOwner','partialFile'})
        need(type(value['iosAvatarAbandonedSourceVersion']) is int and value['iosAvatarAbandonedSourceVersion']==VERSION
            and integer(value['index'],1,128))
        state,frames=self.sources.decode(value['priorOwner']);need(state['phase']=='reading' and state['pending'] is not None and same(frames,self.sources.frames[:len(frames)]))
        self.partial(state['pending']['partial'],version=value['priorOwner']['iosAvatarSourcesVersion'])
        original=state['pending']['original']
        need(value['partialFile'] is None if original is None else same(value['partialFile'],self.file(original)))
        return state

    def record(self,reference):
        exact(reference,{'index','sha256'});value=self.record_store(reference['index']).read()
        need(value is not None and digest(value)==reference['sha256'] and value['index']==reference['index'])
        self.attempt(value);return value

    def decode(self,value):
        exact(value,{'iosAvatarSourceRecoveryVersion','runId','role','binding','artifactRoot','payload'})
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
            if s.state['pending'] is None:return True
            need(s.state['pending'] is not None and len(self.state['records'])<128)
            original=s.state['pending']['original']
            attempt=dict(iosAvatarAbandonedSourceVersion=VERSION,index=len(self.state['records'])+1,
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
    def partial(self,value,*,version=2):
        """Only an actual acquisition prefix may be abandoned, never a result."""
        need(type(value) is dict and type(version) is int and version in (1,2))
        channels=list(CHANNELS) if version>=2 else [name for name in CHANNELS if name!='entities']
        order=['phaseBefore','nativeStart','native',*channels,'widgets','clockJoin','phaseAfter']
        need(any(set(value)==set(order[:index]) for index in range(len(order)+1)))
        s=self.sources
        for name in ('phaseBefore','phaseAfter'):
            if name in value:
                phase=value[name];phase_packet(phase,run=s.run,area='avatar-people',request=phase['requestId'],
                    epoch=phase['capturedEpochMs'],previous=value['phaseBefore'] if name=='phaseAfter' else None)
        start=value.get('nativeStart')
        if start is not None:
            exact(start,{'clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore'})
            need(type(start['clockJoinVersion']) is int and start['clockJoinVersion']==1
                and number(start['hostBeforeEpochMs'],1,1e15) and number(start['hostBeforeMonotonic'],0,1e15))
            packet=start['nativeBefore'];native_packet(packet,packet['requestId'],s.pid,packet['capturedEpochMs'])
        if 'native' in value:
            packet=value['native'];native_packet(packet,packet['requestId'],s.pid,packet['capturedEpochMs'])
            native_prefix(start['nativeBefore'],packet)
        for name,module in CHANNELS.items():
            if name not in value:continue
            row=value[name];exact(row,{'original','acquisition'});packet=module.original(row['original']);acquisition=row['acquisition']
            need(packet['processId']==s.pid and packet['runId']==s.run
                and packet['clockBefore']['epochMs']>=start['nativeBefore']['capturedEpochMs'])
            key=ACQUISITIONS[name];exact(acquisition,{key,'hostBeforeMonotonic','hostAfterMonotonic',
                'nativeRequestedEpochMs','nativeAfterEpochMs','originalSha256'})
            need(type(acquisition[key]) is int and acquisition[key]==1 and acquisition['originalSha256']==digest(packet)
                and number(acquisition['hostBeforeMonotonic'],start['hostBeforeMonotonic'],1e15)
                and number(acquisition['hostAfterMonotonic'],acquisition['hostBeforeMonotonic'],1e15)
                and integer(acquisition['nativeRequestedEpochMs'],start['nativeBefore']['capturedEpochMs'],packet['clockBefore']['epochMs'])
                and integer(acquisition['nativeAfterEpochMs'],packet['clockAfter']['epochMs']))
        if 'widgets' in value:
            widget=project(value['widgets']);need(widget['scope']['processId']==s.pid
                and widget['scope']['capturedEpochMs']>=start['nativeBefore']['capturedEpochMs'])
        if 'clockJoin' in value:
            originals={name:value[name]['original'] for name in channels}
            originals.update(native=value['native'],widgets=value['widgets']);join=validate_join(value['clockJoin'],originals)
            need(all(same(join[key],start[key]) for key in start))
        return value

    def follow(self,frame,*,historical=False):
        """Every actual source prefix and retired worker stays authoritative."""
        if historical:self.lock.assert_held();need(self.sources.historical)
        else:self.bound()
        s=self.sources;need(self.state['pending'] is None and s.validate_frame(frame))
        matches=[index for index,item in enumerate(s.frames,1) if same(item,frame)];need(len(matches)==1);index=matches[0]
        originals=frame['originals'];join=frame['clockJoin'];native=join['nativeBefore'];scripts=[]
        for completed in s.frames[:index]:scripts.append(completed['originals']['scripts'])
        for reference in self.state['records']:
            record=self.record(reference);old=self.attempt(record)
            if old['revision']>=index:continue
            partial=old['pending']['partial']
            packets=[]
            if 'nativeStart' in partial:packets.append(partial['nativeStart']['nativeBefore'])
            if 'native' in partial:packets.append(partial['native'])
            if 'clockJoin' in partial:packets.append(partial['clockJoin']['nativeAfter'])
            for packet in packets:native_prefix(packet,native)
            for name,module in CHANNELS.items():
                if name not in partial:continue
                packet=originals[name];module.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],
                    action=module.ACTION,runId=s.run),s.pid,join['nativeAfter']['capturedEpochMs'],partial[name]['original'])
                if name=='scripts':scripts.append(partial[name]['original'])
            if 'widgets' in partial:
                a,b=project(partial['widgets'])['scope'],frame['ui']['scope']
                need(all(a[key]==b[key] for key in ('instance','generation','processId')) and b['sourceSequence']>a['sourceSequence']
                    and b['sequence']>=a['sequence'] and b['elapsedMs']>=a['elapsedMs'] and b['capturedEpochMs']>=a['capturedEpochMs'])
            phase=partial.get('phaseAfter',partial.get('phaseBefore'))
            if phase is not None:
                current=frame['phaseBefore'];phase_packet(current,run=s.run,area='avatar-people',request=current['requestId'],
                    epoch=join['hostBeforeEpochMs'],previous=phase)
        previous=None;retired=set();unique={}
        for packet in scripts:
            key=packet['sequence']
            if key in unique:need(same(unique[key],packet))
            else:unique[key]=packet
        for packet in [unique[key] for key in sorted(unique)]:
            avatar_scripts.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=avatar_scripts.ACTION,runId=s.run),
                s.pid,previous=previous)
            _members,retired=accept_membership(avatar_scripts.members(previous['source']) if previous else None,
                avatar_scripts.members(packet['source']),retired,packet['clockAfter']['epochMs'])
            previous=packet
        return True
