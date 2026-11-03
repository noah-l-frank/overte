"""Durable independent Actor microphone capture on the existing iOS Source.

This owns test observation resources only. It never starts microphone input,
changes permission/mode/device, plays audio or claims successful preview/peer
behavior. Immutable byte transport is distinct from fresh product observations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import base64
import hashlib
import json
import re
import stat
import time
import uuid
from adapters.native_clock_join import NativeClockAcquisition,validate_join,digest
from adapters.native_clock_source_history import restore
from adapters.native_feature_observation import NativeFeatureObservation,exact,integer,need,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters.audio_api_clock import operation
from ios.adapters.audio_passive_journal import AudioPassiveJournal,STREAMS
from ios.adapters.audio_passive_capture_source import IOSAudioPassiveCaptureSource
from ios.adapters import audio_passive_capture_source as source_contract
from ios.adapters.emote_original_lease import EmoteOriginalLease

VERSION=1
PREFIX='ios-audio-passive-'


class IOSAudioPassiveOwner:
    def __init__(self,store,root,binding,run,lease,lock,guard,*,native,transport,phase,
                 epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(native,NativeFeatureObservation) and native.ios and not native.native_clock_bound
            and isinstance(phase,PhaseFixtureReader) and phase.run==run and phase.area=='audio'
            and type(transport) is dict and set(transport)=={'send','read'}
            and all(callable(fn) for fn in (*transport.values(),guard,epoch_ms,monotonic,sleep)))
        self.initialize(store,root,binding,run,lease,lock,phase.fixture_url,monotonic)
        self.native,self.transport,self.phase,self.guard=native,transport,phase,guard
        self.epoch_ms,self.sleep=epoch_ms,sleep;self.historical=False
        need(native.pid==self.pid);self.load()
        if self.previous is None:self.save()
        self.admit()
        self.bound()
        tail=None
        for frame in self.journals['proofs'].restore():
            if frame['kind']=='reply':tail=frame['clockJoin']['nativeAfter']
        if tail is not None:restore(native,tail)
        actual_send=native.send
        def before_native(query):self.query_intent('native',query);return actual_send(query)
        native.send=before_native
        self.source=None

    def initialize(self,store,root,binding,run,lease,lock,fixture_url,monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
            and source_contract.hex32(run) and source_contract.hex32(lease) and callable(monotonic))
        self.store,self.root,self.binding,self.run,self.lease,self.lock=store,Path(root),deepcopy(context(binding)),run,lease,lock
        need(self.root.is_absolute() and self.root.resolve(strict=True)==self.root
            and store.path==self.root/'ios-audio-passive-owner.json')
        self.pid=int(self.binding['processIdentity']);need(self.pid>0);self.fixture_url=fixture_url;self.monotonic=monotonic
        self.previous=None;self._admitted=False;self._allowed=set();self._signatures={};self._query_index={};self._proof_cache={}
        self.journals={name:AudioPassiveJournal(self,name) for name in STREAMS}
        info=self.root.lstat();need(stat.S_ISDIR(info.st_mode))
        self.root_identity=dict(device=info.st_dev,inode=info.st_ino)
        self.state=dict(instance=None,startIdentity='ios-'+uuid.uuid4().hex,birth=None,streams={name:dict(revision=0,manifests=[]) for name in STREAMS},
            pending=None,start=None,capture=None,release=None,snapshot=None,absence=None,phase='new')

    @classmethod
    def archive(cls,store,root,binding,run,lease,lock,fixture_url):
        owner=object.__new__(cls);owner.initialize(store,root,binding,run,lease,lock,fixture_url,time.monotonic)
        owner.historical=True;owner.guard=lambda:True;owner.load();need(owner.previous is not None);owner.admit();return owner

    def envelope(self):
        return dict(iosAudioPassiveOwnerVersion=VERSION,binding=self.binding,runId=self.run,role='actor',leaseId=self.lease,
            artifactRoot=str(self.root),rootIdentity=self.root_identity,fixtureUrl=self.fixture_url,payload=pack([self.state]))

    def load(self):
        self.lock.assert_held();self.previous=self.store.read()
        if self.previous is None:return
        value=self.previous;exact(value,{'iosAudioPassiveOwnerVersion','binding','runId','role','leaseId','artifactRoot','rootIdentity','fixtureUrl','payload'})
        rows=unpack(value['payload']);need(len(rows)==1);self.state=rows[0]
        need(same(value,self.envelope()))
        exact(self.state,{'instance','startIdentity','birth','streams','pending','start','capture','release','snapshot','absence','phase'})
        need(self.state['instance'] is None or source_contract.hex32(self.state['instance']))
        need(type(self.state['startIdentity']) is str and re.fullmatch('ios-[0-9a-f]{32}',self.state['startIdentity']))
        need(self.state['phase'] in ('new','start-issued','capturing','capture-issued','captured','release-issued','retired'))
        exact(self.state['streams'],set(STREAMS))
        for item in self.state['streams'].values():
            exact(item,{'revision','manifests'});need(integer(item['revision'],0,1024) and type(item['manifests']) is list)
        for name,verb in [('start','start'),('capture','capture'),('release','release')]:
            query=self.state[name]
            if query is not None:source_contract.command(query);need(query['operation']==verb)
        if self.state['pending'] is not None:
            pending=self.state['pending'];exact(pending,{'stream','original','manifest'});need(pending['stream'] in STREAMS)
        for name in ('birth','snapshot','absence'):
            if self.state[name] is not None:need(integer(self.state[name],1,self.state['streams']['proofs']['revision']))
        need(self.state['phase']!='retired' or self.state['absence'] is not None)

    def file_guard(self):
        self.lock.assert_held();info=self.root.lstat()
        need(stat.S_ISDIR(info.st_mode) and dict(device=info.st_dev,inode=info.st_ino)==self.root_identity
            and same(self.store.read(),self.previous))
        PrivateFeatureState(self.root/'boundary.json')._parent()
        if self._admitted:
            for path,before in self._signatures.items():need(EmoteOriginalLease.signature(path.lstat())==before)
            allowed=set(self._allowed);pending=self.state['pending']
            if pending is not None:
                files=self.journals[pending['stream']].files
                if pending['original'] is not None:allowed.add(files.path(pending['original']))
                if pending['manifest'] is not None:allowed.add(files.manifest_path(pending['manifest']['reference']))
            actual=set(self.root.iterdir());need(len(actual)<=8192 and actual.issubset(allowed))
            need(self._allowed.issubset(actual))
        return True

    def bound(self):
        self.file_guard();need(self._admitted and self.guard() is not False);return True

    def save(self):
        need(not self.historical);self.file_guard();value=self.envelope();self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def admit_storage_paths(self,journal,pending):
        if not self._admitted:return
        files=journal.files
        paths=[files.path(pending['original']),files.manifest_path(pending['manifest']['reference'])]
        for path in paths:
            info=path.lstat();need(stat.S_ISREG(info.st_mode) and info.st_nlink==1)
            self._allowed.add(path);self._signatures[path]=EmoteOriginalLease.signature(info)

    def admit(self):
        self.file_guard();self._query_index={};self._proof_cache={}
        for name in ('native','passive'):
            for index,query in enumerate(self.journals[name].restore(),1):
                need(query['commandId'] not in self._query_index)
                self._query_index[query['commandId']]=(name,index,deepcopy(query))
        for key in ('start','capture','release'):
            command=self.state[key]
            actual=[value for stream,_index,value in self._query_index.values() if stream=='passive' and value['operation']==key]
            need(len(actual)<=1 and (command is None and not actual or len(actual)==1 and same(command,actual[0])))
        frames=self.journals['proofs'].restore();self.phase_chain(frames)
        for index,frame in enumerate(frames,1):self._proof_cache[index]=frame
        allowed={self.store.path}
        for journal in self.journals.values():allowed.update(journal.inventory())
        pending=self.state['pending'];optional=set()
        if pending is not None:
            journal=self.journals[pending['stream']]
            if pending['original'] is not None:
                wire=pending['original'];journal.files.original(wire)
                if wire['phase']=='planned':optional.add(journal.files.path(wire))
                else:journal.frame(journal.files.read(wire),wire['index'])
            if pending['manifest'] is not None:optional.add(journal.files.manifest_path(pending['manifest']['reference']))
        actual=set(self.root.iterdir());need(actual.issubset(allowed) and allowed-optional<=actual)
        self._allowed=actual;self._signatures={path:EmoteOriginalLease.signature(path.lstat()) for path in actual if path!=self.store.path}
        self._admitted=True;self.file_guard()

    def validate_entry(self,stream,value,*,ordinal):
        need(stream in STREAMS and type(value) is dict and integer(ordinal,1,1024))
        if stream=='native':
            exact(value,{'schemaVersion','commandId','action'})
            need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-native-observe'
                and type(value['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',value['commandId']))
            return
        if stream=='passive':
            source_contract.command(value)
            need(value['runId']==self.run and value['leaseId']==self.lease and value['role']=='actor'
                and value['instance']==self.state['instance'] and value['startCommandId']==self.state['startIdentity'])
            return
        kind=value.get('kind')
        if kind=='reply':
            exact(value,{'kind','query','packet','clockJoin','phaseBefore','phaseAfter'})
            query=self.journals['passive'].read(value['query']);need(query['operation']!='read')
            join=validate_join(value['clockJoin'],dict(reply=value['packet']))
            need(join['nativeBefore']['processId']==join['nativeAfter']['processId']==self.pid
                and join['nativeBefore']['instance']==join['nativeAfter']['instance']==self.state['instance'])
            for native in (join['nativeBefore'],join['nativeAfter']):
                need(native['requestId'] in self._query_index and self._query_index[native['requestId']][0]=='native')
            source_contract.validate(value['packet'],query,self.pid,join['nativeAfter'])
            active=query['operation'] not in ('release','recover','files')
            for packet in (value['phaseBefore'],value['phaseAfter']):
                phase_packet(packet,run=self.run,area='audio',request=packet['requestId'],epoch=packet['capturedEpochMs'])
                need(not active or packet['active'])
            phase_packet(value['phaseAfter'],run=self.run,area='audio',request=value['phaseAfter']['requestId'],
                epoch=value['phaseAfter']['capturedEpochMs'],previous=value['phaseBefore'])
            need(same(value['phaseBefore']['activations'],value['phaseAfter']['activations']))
        elif kind=='chunk':
            exact(value,{'kind','selection','query','packet'})
            need(integer(value['selection'],1,ordinal-1))
            selected=self.proof(value['selection']);need(selected['kind']=='reply')
            query=self.journals['passive'].read(value['query']);need(query['operation']=='read')
            packet=source_contract.validate(value['packet'],query,self.pid,None,original_only=True)
            descriptors=selected['packet']['source']['files']
            chosen=next(row for row in descriptors if row['kind']==query['kind'])
            need(same(chosen,packet['source']['original']))
        elif kind=='birth':
            exact(value,{'kind','selection','chunks'})
            need(integer(value['selection'],1,ordinal-1))
            selected=self.proof(value['selection']);need(selected['kind']=='reply')
            source=selected['packet']['source'];need(source['startAttempted'] and not source['releaseAttempted'])
            intent=source_contract.original_intent(self.assembled(value['chunks'],'intent',value['selection'],ordinal),self.state['start'],self.pid)
            need(source['state']['owned'] and source['state']['startedEpochMs']>=intent['issuedEpochMs'])
        elif kind=='snapshot':
            exact(value,{'kind','selection','chunks'})
            need(integer(value['selection'],1,ordinal-1));exact(value['chunks'],{'intent','capture','wav'})
            raw={kind:self.assembled(value['chunks'][kind],kind,value['selection'],ordinal) for kind in source_contract.KINDS}
            need(self.state['birth'] is not None)
            birth=self.proof(self.state['birth']);need(birth['kind']=='birth')
            issued=self.assembled(birth['chunks'],'intent',birth['selection'],self.state['birth'])
            need(raw['intent']==issued)
            intent=source_contract.original_intent(raw['intent'],self.state['start'],self.pid)
            original=source_contract.original_frame(raw['capture'],raw['wav'],self.state['capture'],self.pid)
            need(original['source']['startedEpochMs']>=intent['issuedEpochMs'])
        else:need(False)

    def proof(self,index):
        need(integer(index,1,self.state['streams']['proofs']['revision']))
        return self.journals['proofs'].read(index)

    def assembled(self,indices,kind,selection,before):
        need(type(indices) is list and len(indices)<=512 and indices==sorted(set(indices)))
        parts=[];offset=0;reference=None
        for index in indices:
            need(integer(index,1,before-1));frame=self.proof(index)
            need(frame['kind']=='chunk' and frame['selection']==selection)
            packet=frame['packet']['source'];need(packet['kind']==kind and packet['offset']==offset)
            if reference is None:reference=packet['original']
            else:need(same(reference,packet['original']))
            raw=base64.b64decode(packet['base64'],validate=True);parts.append(raw);offset+=len(raw)
        need(reference is not None);raw=b''.join(parts)
        need(len(raw)==reference['bytes'] and hashlib.sha256(raw).hexdigest()==reference['sha256']);return raw

    def query_intent(self,stream,query):
        self.bound();need(not self.historical and self.state['pending'] is None and query['commandId'] not in self._query_index)
        if stream=='passive' and query['operation'] in ('start','capture','release'):
            key=query['operation'];need(self.state[key] is None)
            if key=='start':need(self.state['phase']=='new')
            if key=='capture':need(self.state['start'] is not None and self.state['release'] is None)
        reference=self.journals[stream].append(query)
        self._query_index[query['commandId']]=(stream,reference['index'],deepcopy(query));return True

    def link_entry(self,stream,value):
        # Journal revision and its once-issued effect pointer are one final
        # parent CAS. No delivery can precede this completed metadata commit.
        if stream=='proofs':
            # Bind complete immutable proof and parent effect pointer in the
            # same final WAL commit, also after lost append/parent returns.
            if value['kind'] in ('birth','snapshot'):
                key=value['kind'];need(self.state[key] is None)
                self.state[key]=self.state['streams']['proofs']['revision']+1
                if key=='snapshot':self.state['phase']='captured'
            if value['kind']=='reply':
                query=self.journals['passive'].read(value['query']);source=value['packet']['source'];state=source['state']
                if query['operation']=='files' and source['retired']:
                    need(source['releaseAttempted'] and self.state['release'] is not None and not state['owned']
                        and not state['watchdogOwned'] and not state['watchdogActive'] and state['bytes']==0
                        and source['openOriginalFds']==source['originalBytes']==0 and all(not row['exists'] for row in source['files']))
                    need(self.state['absence'] is None)
                    self.state.update(absence=self.state['streams']['proofs']['revision']+1,phase='retired')
            return
        if stream!='passive' or value['operation'] not in ('start','capture','release'):return
        key=value['operation'];old=self.state[key]
        need(old is None or same(old,value))
        self.state[key]=deepcopy(value);self.state['phase']=key+'-issued'

    def recover_storage(self):
        self.bound()
        pending=self.state['pending']
        if pending is not None:self.journals[pending['stream']].recover();self.admit()

    def wire(self):
        need(self.state['instance'] is not None)
        if self.source is None:
            self.source=IOSAudioPassiveCaptureSource(self.transport['send'],self.transport['read'],self.bound,
                lambda:self.native.read(self.native.sequence),self.pid,self.state['instance'],self.run,self.lease,
                start_command_id=self.state['startIdentity'],intent=lambda query:self.query_intent('passive',query),monotonic=self.monotonic,sleep=self.sleep)
            packets=[frame['packet'] for frame in self.journals['proofs'].restore() if frame['kind'] in ('reply','chunk')]
            if packets:
                self.source.sequence=packets[-1]['sequence'];self.source.epoch=packets[-1]['capturedEpochMs']
        return self.source

    def phase_chain(self,frames):
        """Type original fixture continuity across complete native groups.

        A reconstructed reader cannot replace a retired fixture instance or
        drop already observed activation history for this still-owned lease.
        These are immutable input originals, never a new native fact.
        """
        previous=None
        for frame in frames:
            if frame['kind']!='reply':continue
            before=frame['phaseBefore']
            if previous is not None:
                phase_packet(before,run=self.run,area='audio',request=before['requestId'],epoch=before['capturedEpochMs'],previous=previous)
            previous=frame['phaseAfter']
        return previous

    def control(self,verb,**fields):
        self.bound();self.recover_storage();previous=self.phase_chain(self.journals['proofs'].restore());before=self.phase.status()
        if previous is not None:
            phase_packet(before,run=self.run,area='audio',request=before['requestId'],epoch=before['capturedEpochMs'],previous=previous)
        need(verb in ('release','recover','files') or before['active']);acquisition=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        acquisition.begin(self.epoch_ms());instance=acquisition.started['nativeBefore']['instance']
        if self.state['instance'] is None:self.state['instance']=instance;self.save()
        else:need(self.state['instance']==instance)
        query,packet=self.wire().query(verb,**fields)
        join=acquisition.finish(dict(reply=packet),[('reply','capturedEpochMs')]);after=self.phase.status(before)
        value=dict(kind='reply',query=self._query_index[query['commandId']][1],packet=packet,clockJoin=join,phaseBefore=before,phaseAfter=after)
        reference=self.journals['proofs'].append(value);return reference['index'],value

    def download(self,selection,kind):
        """Resume retained original chunks; never re-dispatch capture/start."""
        selected=self.proof(selection);need(selected['kind']=='reply')
        descriptor=next(row for row in selected['packet']['source']['files'] if row['kind']==kind)
        need(descriptor['exists'] and descriptor['complete'])
        indices=[];offset=0
        for index,frame in enumerate(self.journals['proofs'].restore(),1):
            if frame['kind']!='chunk' or frame['selection']!=selection or frame['packet']['source']['kind']!=kind:continue
            source=frame['packet']['source'];need(source['offset']==offset and source['original']==descriptor)
            indices.append(index);offset+=source['bytes']
        while offset<descriptor['bytes']:
            query,packet=self.wire().query('read',kind=kind,offset=offset,bytes=min(4096,descriptor['bytes']-offset))
            frame=dict(kind='chunk',selection=selection,query=self._query_index[query['commandId']][1],packet=packet)
            reference=self.journals['proofs'].append(frame);indices.append(reference['index']);offset+=packet['source']['bytes']
        return indices

    def retained_selection(self,kinds):
        for index in range(1,self.state['streams']['proofs']['revision']+1):
            frame=self.proof(index)
            if frame['kind']!='reply':continue
            source=frame['packet']['source'];files={row['kind']:row for row in source['files']}
            if all(files[kind]['exists'] and files[kind]['complete'] for kind in kinds) and not source['releaseAttempted']:
                return index
        return None

    def authenticate_birth(self,selection):
        if self.state['birth'] is not None:
            birth=self.proof(self.state['birth']);need(birth['kind']=='birth')
            return self.state['birth']
        # Earlier completed control originals may already own partial chunks.
        retained=self.retained_selection(('intent',));need(retained is not None)
        chunks=self.download(retained,'intent')
        reference=self.journals['proofs'].append(dict(kind='birth',selection=retained,chunks=chunks))
        need(self.state['birth']==reference['index']);return reference['index']

    @operation
    def start(self,seconds=10):
        self.bound();self.recover_storage()
        verb='start' if self.state['start'] is None else 'observe'
        index,value=self.control(verb,**({'seconds':seconds} if verb=='start' else {}))
        current=value['packet']['source']['state'];need(current['owned'] and not current['invalid'])
        self.authenticate_birth(index)
        self.state['phase']='capturing';self.save();return dict(original=index,birth=self.state['birth'],state=deepcopy(current))

    @operation
    def capture(self):
        self.bound();self.recover_storage()
        if self.state['snapshot'] is not None:return self.snapshot()
        need(self.state['start'] is not None and self.state['birth'] is not None and self.state['release'] is None)
        if self.state['capture'] is None:self.control('capture')
        index=self.retained_selection(source_contract.KINDS)
        if index is None:
            index,_value=self.control('files')
        selected=self.proof(index);need(selected['kind']=='reply')
        chunks={kind:self.download(index,kind) for kind in source_contract.KINDS}
        reference=self.journals['proofs'].append(dict(kind='snapshot',selection=index,chunks=chunks))
        self.state.update(snapshot=reference['index'],phase='captured');self.save();return self.snapshot()

    def snapshot(self):
        self.file_guard();need(self.state['snapshot'] is not None);frame=self.proof(self.state['snapshot'])
        need(frame['kind']=='snapshot')
        return dict(original=self.state['snapshot'],capture=deepcopy(self.state['capture']),
            wav=self.assembled(frame['chunks']['wav'],'wav',frame['selection'],self.state['snapshot']))

    @operation
    def retire(self):
        self.bound();self.recover_storage()
        if self.state['absence'] is not None:return self.retired()
        index,value=self.control('release' if self.state['release'] is None else 'recover')
        # ACK is not absence. A distinct subsequent native files/memory query
        # must independently observe every resource after the release returned.
        index,value=self.control('files');observed=value['packet']['source'];current=observed['state']
        need(observed['retired'] and observed['releaseAttempted'] and not current['owned']
            and not current['watchdogOwned'] and not current['watchdogActive'] and current['bytes']==0
            and observed['openOriginalFds']==observed['originalBytes']==0
            and all(not row['exists'] for row in observed['files']))
        self.state.update(absence=index,phase='retired');self.save();return self.retired()

    def retired(self):
        self.file_guard();need(self.state['phase']=='retired' and self.state['absence'] is not None)
        frame=self.proof(self.state['absence']);need(frame['kind']=='reply')
        query=self.journals['passive'].read(frame['query']);source=frame['packet']['source'];state=source['state']
        need(query['operation']=='files' and source['retired'] and source['releaseAttempted'] and not state['owned']
            and not state['watchdogOwned'] and not state['watchdogActive'] and state['bytes']==0
            and source['openOriginalFds']==source['originalBytes']==0 and all(not row['exists'] for row in source['files']))
        return dict(retired=True,absence=self.state['absence'],nativeQualified=False,wholeQualified=False)
