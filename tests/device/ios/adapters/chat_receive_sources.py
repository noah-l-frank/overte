"""Immutable original receive cuts on the existing independently bound pair.

This observational child issues no normal input and publishes no Chat result.
Native packets keep their own clocks. Storage recovery never becomes freshness.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import time
from pathlib import Path
from adapters.native_chat_observation import command as chat_command,validate as chat_packet
from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.native_clock_source_history import restore
from adapters.native_feature_observation import NativeFeatureObservation,exact,need,number,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from ios.adapters.chat_draft_clock import operation
from ios.adapters.chat_receive_runtime import IOSOwnedChatReceiver,binding_record
from ios.adapters.graphics_history import follow_native

VERSION=1


class IOSChatReceiveSources:
    def __init__(self,parts,store,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(type(parts) is dict and isinstance(parts['receiver'],IOSOwnedChatReceiver)
            and type(store) is PrivateFeatureState and all(callable(fn) for fn in (epoch_ms,monotonic)))
        self.parts,self.store=parts,store;self.receiver=parts['receiver']
        self.binding,self.primary_binding=deepcopy(context(parts['peer']['binding'])),deepcopy(context(parts['primary']['binding']))
        self.run=identifier(self.receiver.peer.run);self.lock=parts['peer_lock'];self.primary_lock=parts['primary_lock']
        self.root=parts['binding']['peerArtifactRoot']['path'];self.bound_record=deepcopy(parts['binding'])
        self.epoch_ms,self.monotonic=epoch_ms,monotonic;self.historical=False
        need(store.path==self.lock.path.with_name('ios-chat-receive-sources.json'))
        self.clocks={role:parts[role]['clock_source'] for role in ('primary','peer')}
        need(all(isinstance(clock,NativeFeatureObservation) and clock.ios and not clock.native_clock_bound
            and clock.pid==int(parts[role]['binding']['processIdentity']) for role,clock in self.clocks.items()))
        self.previous=store.read();self.state=self.empty()
        self.frames=OriginalFrameStore(self.root,self.binding,self.run,'actor',self.bound,self.storage_intent,
            namespace='ios-chat-receive',schema_prefix='iosChatReceive',monotonic=monotonic)
        self.bound()
        if self.previous is not None:self.state=self.decode(self.previous)
        else:self.inventory(self.state)
        latest=None if not self.state['records'] else self.original(self.state['records'][-1])
        pending=self.state['pending']
        if pending is not None and pending['wire'] is not None:
            need(pending['wire']['phase'] in ('opened','saved'))
            latest=self.frame(self.frames.read(pending['wire']),latest)
            need(same(latest,pending['partial']['frame']))
        for role,packet in self.native_floors(self.state).items():restore(self.clocks[role],packet)

    @classmethod
    def archive(cls,store,primary_binding,peer_binding,run,primary_root,peer_root,record,primary_lock,peer_lock):
        binding_record(record,primary_binding,peer_binding,run,primary_root,peer_root)
        owner=object.__new__(cls);owner.store=store;owner.parts=owner.receiver=None
        owner.binding,owner.primary_binding=deepcopy(context(peer_binding)),deepcopy(context(primary_binding))
        owner.run=identifier(run);owner.root=str(Path(peer_root));owner.bound_record=deepcopy(record)
        owner.lock,owner.primary_lock=peer_lock,primary_lock
        owner.monotonic,owner.epoch_ms=time.monotonic,None;owner.historical=True;owner.clocks=None
        need(type(store) is PrivateFeatureState and store.path==peer_lock.path.with_name('ios-chat-receive-sources.json')
            and primary_lock.path!=peer_lock.path)
        owner.previous=store.read();need(owner.previous is not None);owner.state=owner.empty()
        owner.frames=OriginalFrameStore(owner.root,owner.binding,owner.run,'actor',owner.bound,owner.storage_intent,
            namespace='ios-chat-receive',schema_prefix='iosChatReceive',monotonic=owner.monotonic)
        owner.bound();owner.state=owner.decode(owner.previous);need(owner.state['pending'] is None);return owner

    @staticmethod
    def empty():return dict(records=[],pending=None,interrupted=[])
    def envelope(self,state):
        return dict(iosChatReceiveSourcesVersion=VERSION,binding=self.binding,primaryBinding=self.primary_binding,
            runId=self.run,artifactRoot=str(self.root),peerBindingRecord=self.bound_record,payload=pack([state]))
    def bound(self):
        self.lock.assert_held();self.primary_lock.assert_held()
        need(same(self.store.read(),self.previous))
        if not self.historical:need(self.parts['check']() is not False)
        binding_record(self.bound_record,self.primary_binding,self.binding,self.run,
            self.bound_record['primaryArtifactRoot']['path'],self.root)
        return True
    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def query(self,value):
        exact(value,{'role','command'});need(value['role'] in ('primary','peer'));command=value['command']
        need(type(command) is dict)
        if command.get('action')=='feature-chat-observe':
            chat_command(command,ios=True);need(command['runId']==self.run and command['operation'] in ('inspect','observe'))
        else:
            exact(command,{'schemaVersion','commandId','action'})
            need(type(command['schemaVersion']) is int and command['schemaVersion']==1
                and command['action']=='feature-native-observe' and type(command['commandId']) is str
                and command['commandId'].startswith('ios-'));identifier(command['commandId'][4:])
    def query_intent(self,role,command):
        self.bound();pending=self.state['pending'];need(not self.historical and pending is not None and len(pending['queries'])<64)
        value=dict(role=role,command=deepcopy(command));self.query(value)
        need(not any(row['role']==role and row['command']['commandId']==command['commandId'] for row in pending['queries']))
        pending['queries'].append(value);self.save()
    @contextmanager
    def query_hooks(self):
        originals=[];reads=[]
        try:
            for role,reader in (('primary',self.clocks['primary']),('peer',self.clocks['peer']),
                ('primary',self.receiver.primary),('peer',self.receiver.peer.reader)):
                original=reader.send;originals.append((reader,original))
                def send(command,role=role,original=original):self.query_intent(role,command);return original(command)
                reader.send=send
            for role,reader in self.clocks.items():
                original=reader.read;reads.append((reader,original))
                def read(*args,role=role,original=original,**kwargs):
                    value=original(*args,**kwargs);self.remember_clock(role,value);return value
                reader.read=read
            yield
        finally:
            for reader,original in reads:reader.read=original
            for reader,original in originals:reader.send=original
    def remember_clock(self,role,packet):
        self.bound();pending=self.state['pending'];need(pending is not None and not self.historical)
        reads=pending['partial'].setdefault('clockReads',dict(primary=[],peer=[]))
        need(sum(len(rows) for rows in reads.values())<64)
        reads[role].append(deepcopy(packet));self.save()
    def remember(self,key,value):
        self.bound();need(self.state['pending'] is not None and key not in self.state['pending']['partial'])
        self.state['pending']['partial'][key]=deepcopy(value);self.save()
    def chat(self,role,packet):
        binding=self.primary_binding if role=='primary' else self.binding
        request=dict(schemaVersion=1,action='feature-chat-observe',
            **{key:packet[key] for key in ('commandId','runId','operation')})
        chat_command(request,ios=True);chat_packet(packet,request,int(binding['processIdentity']),packet['capturedEpochMs'])
        need(packet['runId']==self.run and packet['operation']==('inspect' if role=='primary' else 'observe'))
        source=packet['source'];need(source['scopePresent'] and not source['retired'] and source['droppedEvents']==0)
        return request
    def native_floors(self,state):
        """Keep every observed original clock floor, including interrupted reads."""
        packets={role:{} for role in ('primary','peer')}
        def add(role,packet,queries):
            binding=self.primary_binding if role=='primary' else self.binding
            native_packet(packet,packet['requestId'],int(binding['processIdentity']),packet['capturedEpochMs'])
            query=dict(role=role,command=dict(schemaVersion=1,action='feature-native-observe',commandId=packet['requestId']))
            need(query in queries);self.query(query)
            old=packets[role].get(packet['sequence']);need(old is None or same(old,packet))
            packets[role][packet['sequence']]=packet
        for reference in state['records']:
            frame=self.frames.read(self.frames.expand(reference))
            for role in packets:
                for packet in frame['clockReads'][role]:add(role,packet,frame['queries'])
                for key in ('nativeBefore','nativeAfter'):add(role,frame['joins'][role][key],frame['queries'])
        for pending in state['interrupted']+([] if state['pending'] is None else [state['pending']]):
            partial=pending['partial'];queries=pending['queries']
            reads=partial.get('clockReads',dict(primary=[],peer=[]));exact(reads,{'primary','peer'})
            need(all(type(rows) is list for rows in reads.values()) and sum(len(rows) for rows in reads.values())<=64)
            for role in packets:
                for packet in reads[role]:add(role,packet,queries)
                start=partial.get(role+'Start')
                if start is not None:
                    exact(start,{'clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore'})
                    need(type(start['clockJoinVersion']) is int and start['clockJoinVersion']==1
                        and number(start['hostBeforeEpochMs'],1,1e15) and number(start['hostBeforeMonotonic'],0,1e15))
                    add(role,start['nativeBefore'],queries)
                join=partial.get(role+'Join')
                if join is not None:
                    sample=partial['sample'];exact(sample,{'receiverVersion','runId','peerMessages','primary','peer'})
                    self.chat(role,sample[role]);validate_join(join,dict(chat=sample[role]))
                    for key in ('nativeBefore','nativeAfter'):add(role,join[key],queries)
        result={}
        for role,by_sequence in packets.items():
            previous=None
            for sequence in sorted(by_sequence):
                packet=by_sequence[sequence]
                if previous is not None:follow_native(previous,packet)
                previous=packet
            if previous is not None:result[role]=previous
        return result
    def storage_intent(self,event,wire):
        need(not self.historical and event=='original' and self.state['pending'] is not None)
        self.frames.original(wire);need(wire['index']==len(self.state['records'])+1)
        old=self.state['pending']['wire']
        if old is None:need(wire['phase']=='planned')
        else:
            need(wire['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                and all(same(wire[key],old[key]) for key in wire if key not in ('phase','file'))
                and (old['phase']=='planned' or same(wire['file'],old['file'])))
        self.state['pending']['wire']=deepcopy(wire);self.save()
    def frame(self,value,previous=None):
        exact(value,{'iosChatReceiveObservationVersion','sample','joins','queries','clockReads'})
        need(type(value['iosChatReceiveObservationVersion']) is int and value['iosChatReceiveObservationVersion']==VERSION)
        sample=value['sample'];exact(sample,{'receiverVersion','runId','peerMessages','primary','peer'})
        need(type(sample['receiverVersion']) is int and sample['receiverVersion']==2 and sample['runId']==self.run)
        exact(value['joins'],{'primary','peer'});queries=value['queries'];need(type(queries) is list and len(queries)<=64)
        ids=[]
        for query in queries:
            self.query(query);ids.append((query['role'],query['command']['commandId']))
        need(len(set(ids))==len(ids))
        exact(value['clockReads'],{'primary','peer'})
        need(all(type(rows) is list for rows in value['clockReads'].values())
            and sum(len(rows) for rows in value['clockReads'].values())<=64)
        for role,binding in (('primary',self.primary_binding),('peer',self.binding)):
            packet=sample[role];request=self.chat(role,packet);source=packet['source']
            join=value['joins'][role];validate_join(join,dict(chat=packet))
            need(join['nativeBefore']['processId']==int(binding['processIdentity']))
            reads=value['clockReads'][role];need(len(reads)>=2 and same(reads[0],join['nativeBefore']) and same(reads[-1],join['nativeAfter']))
            commands=[row['command']['commandId'] for row in queries if row['role']==role and row['command']['action']=='feature-native-observe']
            need(commands==[row['requestId'] for row in reads])
            for index,native in enumerate(reads):
                native_packet(native,native['requestId'],int(binding['processIdentity']),native['capturedEpochMs'])
                if index:follow_native(reads[index-1],native)
            for command in (request,*[dict(schemaVersion=1,action='feature-native-observe',commandId=join[key]['requestId'])
                for key in ('nativeBefore','nativeAfter')]):need(dict(role=role,command=command) in queries)
            if previous is not None:
                old=previous['sample'][role];old_source=old['source'];old_join=previous['joins'][role]
                need(packet['instance']==old['instance'] and packet['sequence']>old['sequence']
                    and packet['commandId']!=old['commandId'] and packet['capturedEpochMs']>=old['capturedEpochMs']
                    and source['selfSha256']==old_source['selfSha256'] and source['openedEpochMs']==old_source['openedEpochMs']
                    and same(source['events'][:len(old_source['events'])],old_source['events']))
                follow_native(old_join['nativeAfter'],join['nativeBefore'])
                need(join['hostBeforeEpochMs']>=old_join['hostAfterEpochMs']
                    and join['hostBeforeMonotonic']>=old_join['hostAfterMonotonic'])
        p,q=sample['primary'],sample['peer'];need(p['instance']!=q['instance'] and p['source']['selfSha256']!=q['source']['selfSha256'])
        messages=[row['text'] for row in q['source']['events'] if row['senderSha256']==p['source']['selfSha256'] and not row['localOnly']]
        need(same(sample['peerMessages'],messages))
        first,last=value['joins']['primary'],value['joins']['peer']
        need(first['hostBeforeEpochMs']<=last['hostBeforeEpochMs']<=first['hostAfterEpochMs']<=last['hostAfterEpochMs']
            and first['hostBeforeMonotonic']<=last['hostBeforeMonotonic']<=first['hostAfterMonotonic']<=last['hostAfterMonotonic']
            and last['hostAfterEpochMs']-first['hostBeforeEpochMs']<1500
            and last['hostAfterMonotonic']-first['hostBeforeMonotonic']<1.5)
        return value
    def original(self,reference):
        need(any(same(reference,row) for row in self.state['records']))
        return self.frame(self.frames.read(self.frames.expand(reference)))
    def inventory(self,state):
        expected={self.frames.path(self.frames.expand(ref)) for ref in state['records']}|{
            self.store.path,self.lock.path.with_name('ios-chat-receive-binding.json')}
        if state['pending'] is not None and state['pending']['wire'] is not None:expected.add(self.frames.path(state['pending']['wire']))
        for root in {Path(self.root),self.store.path.parent}:
            for index,path in enumerate(root.iterdir()):
                need(index<4096)
                if path.name.startswith('ios-chat-receive-'):need(path in expected)
    def decode(self,value):
        exact(value,{'iosChatReceiveSourcesVersion','binding','primaryBinding','runId','artifactRoot','peerBindingRecord','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,set(self.empty()));need(type(state['records']) is list and len(state['records'])<=128
            and type(state['interrupted']) is list and len(state['interrupted'])<=32)
        previous=None
        for index,reference in enumerate(state['records'],1):
            need(reference['index']==index);previous=self.frame(self.frames.read(self.frames.expand(reference)),previous)
        for pending in state['interrupted']+([] if state['pending'] is None else [state['pending']]):
            exact(pending,{'queries','partial','wire'});need(type(pending['queries']) is list and len(pending['queries'])<=64
                and type(pending['partial']) is dict and set(pending['partial'])<= {'primaryStart','peerStart','sample','primaryJoin','peerJoin','frame','clockReads'})
            for query in pending['queries']:self.query(query)
            if pending['wire'] is not None:
                need(pending is state['pending']);self.frames.original(pending['wire'])
                need(pending['wire']['index']==len(state['records'])+1 and 'frame' in pending['partial'])
        self.native_floors(state);self.inventory(state);return deepcopy(state)
    def recover(self):
        self.bound();pending=self.state['pending']
        if pending is None:return
        wire=pending['wire']
        if wire is None:
            need(len(self.state['interrupted'])<32);self.state['interrupted'].append(deepcopy(pending))
        else:
            need(wire['index']==len(self.state['records'])+1 and wire['phase'] in ('opened','saved'))
            previous=None if not self.state['records'] else self.original(self.state['records'][-1])
            value=self.frame(self.frames.read(wire),previous);need(same(value,pending['partial']['frame']))
            self.state['records'].append(self.frames.compact(dict(wire,phase='saved')))
        self.state['pending']=None;self.save()
    @operation
    def capture(self):
        self.bound();need(not self.historical);self.recover();need(len(self.state['records'])<128)
        owned=self.parts['primary_capture'].owner.owned()
        need(owned is not None and owned['runId']==self.run and owned['active'] and owned['admitted'])
        self.state['pending']=dict(queries=[],partial={},wire=None);self.save()
        with self.query_hooks():
            windows={role:NativeClockAcquisition(clock,epoch_ms=self.epoch_ms,monotonic=self.monotonic) for role,clock in self.clocks.items()}
            barrier=self.epoch_ms()
            for role in ('primary','peer'):windows[role].begin(barrier);self.remember(role+'Start',windows[role].started)
            sample=self.receiver.sample();self.remember('sample',sample);joins={}
            for role in ('primary','peer'):
                joins[role]=windows[role].finish(dict(chat=sample[role]),[('chat','capturedEpochMs')]);self.remember(role+'Join',joins[role])
            value=dict(iosChatReceiveObservationVersion=VERSION,sample=sample,joins=joins,
                queries=deepcopy(self.state['pending']['queries']),clockReads=deepcopy(self.state['pending']['partial']['clockReads']))
            self.frame(value,None if not self.state['records'] else self.original(self.state['records'][-1]));self.remember('frame',value)
            reference=self.frames.write(len(self.state['records'])+1,value)
            self.state['records'].append(reference);self.state['pending']=None;self.save()
        first=joins['primary'];now,mono=self.epoch_ms(),self.monotonic()
        need(number(now,joins['peer']['hostAfterEpochMs'],first['hostBeforeEpochMs']+1500)
            and number(mono,joins['peer']['hostAfterMonotonic'],first['hostBeforeMonotonic']+1.5)
            and now-first['hostBeforeEpochMs']<1500 and mono-first['hostBeforeMonotonic']<1.5)
        return deepcopy(reference)
