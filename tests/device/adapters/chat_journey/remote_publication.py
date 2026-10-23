"""Passive original independent Chat publications; never a live Actor restore."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
import base64
import hashlib
import math
import time

from adapters.chat_journey.actor_stop import validate_publication_return
from adapters.chat_journey.evidence_archive import LIMIT_BYTES,LIMIT_FILES,stamp
from adapters.chat_journey.flow_inputs import validate_flow
from adapters.chat_journey.observation import STAGES
from adapters.chat_journey.observation_cursor import plain
from adapters.chat_journey.remote_actor_graph import GRAPH,ChatSourceGraphPrefix,validate_actor_pairs
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.chat_journey import source_bundles
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.observer_return import state,parent_node,raw_file
from adapters.script_journey.history import same,canonical
from adapters.script_journey.lock import ScriptSourceLock,ScriptSourceBusy
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending,PhaseRetired
from fixture.chat_observer_process import LinuxChatObserverProcess

VERSION=3
EXPECTED={'runId','fixtureUrl','binding','peerBinding','hostProcessIdentity','instance'}
STORES={'actor','flow','cleanup',*GRAPH}
ACTOR=EXPECTED|{'picoChatCursorActorVersion','phase','pairs','returnedPublication'}


def original_record(history,root,index):
    """Historical storage grammar only; never construct a live source owner."""
    need(type(history) is ChatSourceChunks);plain(root)
    version=root.get('chatRemotePublicationVersion')
    need(type(version) is int and version in (1,2,3))
    scope_keys=EXPECTED|{'chatRemotePublicationVersion','journal'}
    exact(root,scope_keys|{'phase','chunks'}|({'bundles','pendingBundle','logicalBytes'} if version==3 else set()))
    scope={key:root[key] for key in scope_keys}
    context(scope['binding']);context(scope['peerBinding']);identifier(scope['runId']);identifier(scope['instance'])
    need(root['phase']=='ready' and root['journal']==history.root.path.name and digest(scope)==history.scope
        and type(scope['hostProcessIdentity']) is str and type(scope['fixtureUrl']) is str
        and type(root['chunks']) is list and same(history.root.read(),root))
    history.verify()
    if version==3:
        need(root['pendingBundle'] is None and type(root['logicalBytes']) is int
            and root['logicalBytes']==source_bundles.logical_bytes(root['bundles']))
        value,_raw=source_bundles.original(history,root['chunks'],root['bundles'],index)
    else:
        # These bytes gain no missing v2 clocks, v3 fragments or fresh status.
        from adapters.script_journey.history import unpack
        need(integer(index,0,len(root['chunks'])-1) and len(root['chunks'])==len(history.identities))
        chunk=history.store(index).read();need(digest(chunk)==root['chunks'][index])
        exact(chunk,{'chatSampleChunkVersion','scopeSha256','index','transcript'})
        need(type(chunk['chatSampleChunkVersion']) is int and chunk['chatSampleChunkVersion']==1
            and type(chunk['index']) is int and chunk['index']==index and chunk['scopeSha256']==history.scope)
        values=unpack(chunk['transcript']);need(len(values)==1);value=values[0]
    need(same(history.root.read(),root));history.verify();return value


class ChatRemotePublication:
    """One originally live host and fixed paths, with actual independent GET.

    No publication, input, Stop command, source query or native owner is made
    from files. A later typed return still validates the entire sealed graph
    and actual kernel absence. Original clocks qualify each read separately.
    """
    def __init__(self,process,source,stores,expected,locks,store,*,peer_epoch_ms,guard,monotonic=time.monotonic):
        need(type(process) is LinuxChatObserverProcess and type(source) is PhaseFixtureReader and source.area=='chat'
            and type(stores) is dict and set(stores)==STORES and all(type(value) is PrivateFeatureState for value in stores.values())
            and type(locks) is tuple and len(locks)==2 and all(type(lock) is ScriptSourceLock for lock in locks)
            and locks[0] is not locks[1] and locks[0].path!=locks[1].path
            and type(store) is PrivateFeatureState and store.read() is None
            and callable(peer_epoch_ms) and callable(guard) and callable(monotonic))
        for method in ('guard','source_files','original_program','_arguments'):
            need(getattr(getattr(process,method),'__func__',None) is getattr(LinuxChatObserverProcess,method))
        exact(expected,EXPECTED);plain(expected);context(expected['binding']);context(expected['peerBinding'])
        identifier(expected['runId']);identifier(expected['instance'])
        need(expected['hostProcessIdentity']==process.process_identity and expected['runId']==source.run
            and expected['fixtureUrl']==source.fixture_url)
        paths=[store.path,*[value.path for value in stores.values()]]
        need(len(set(paths))==len(paths) and all(path.parent==store.path.parent for path in paths))
        self.process,self.source,self.stores,self.locks,self.store=process,source,dict(stores),locks,store
        self.expected=deepcopy(expected);self.expected_sha=digest(expected);self.parent=parent_node(store)
        self.paths={key:str(value.path) for key,value in stores.items()};self.lock_paths=[str(lock.path) for lock in locks]
        self.peer_epoch_ms,self.guard,self.monotonic=peer_epoch_ms,guard,monotonic
        self.scope=dict(chatRemotePublicationVersion=VERSION,**deepcopy(expected),journal=store.path.name)
        self.history=ChatSourceChunks(store,self.scope);self.history.inventory(0)
        self.previous=None;self.root_stamp=None;self.rows=[];self.admitted={};self.roots={}
        self.stop_intent=None;self.failed=False;self.grammar=self._grammar=ChatSourceGraphPrefix()
        self.cache_sha=self.cache_digest();self.control()

    def cache_digest(self):
        need(type(self.history) is ChatSourceChunks and self.history.root is self.store and self.history.scope==digest(self.scope)
            and type(self.history.raw_bytes) is int and type(self.history.identities) is list
            and all(type(row) is tuple and len(row)==8 and all(type(field) is int for field in row) for row in self.history.identities))
        for value in (self.expected,self.scope,self.previous,self.rows,self.admitted,self.roots,self.root_stamp,self.paths,self.lock_paths,self.stop_intent):plain(value)
        return digest(dict(expected=self.expected,scope=self.scope,previous=self.previous,rows=self.rows,
            admitted=self.admitted,roots=self.roots,stamp=self.root_stamp,paths=self.paths,locks=self.lock_paths,
            history=dict(rawBytes=self.history.raw_bytes,identities=[list(row) for row in self.history.identities]),stop=self.stop_intent))

    def control(self):
        need(type(self.grammar) is ChatSourceGraphPrefix and self.grammar is self._grammar);self.grammar.control()
        need(not self.failed and self.cache_digest()==self.cache_sha and digest(self.expected)==self.expected_sha
            and parent_node(self.store)==self.parent and self.process.process_identity==self.expected['hostProcessIdentity']
            and {key:str(value.path) for key,value in self.stores.items()}==self.paths
            and [str(lock.path) for lock in self.locks]==self.lock_paths
            and self.source.run==self.expected['runId'] and self.source.fixture_url==self.expected['fixtureUrl']
            and self.source.client.url+'/runs/'+self.source.run+'/'==self.expected['fixtureUrl']
            and self.store.path.name==self.scope['journal'])
        self.process.guard();self.history.verify()
        need(same(self.store.read(),self.previous))
        if self.previous is not None and self.scope['chatRemotePublicationVersion']==3:
            exact(self.previous,set(self.scope)|{'phase','chunks','bundles','pendingBundle','logicalBytes'})
            references=self.previous['bundles'];logical=source_bundles.logical_bytes(references)
            base=sum(ref['parts'] for ref in references);count=len(self.previous['chunks'])
            need(type(self.previous['logicalBytes']) is int)
            if self.previous['phase']=='ready':
                need(self.previous['pendingBundle'] is None and self.previous['logicalBytes']==logical
                    and base==count==len(self.history.identities) and len(references)==len(self.rows))
            else:
                need(self.previous['phase']=='reading');pending=source_bundles.reference(self.previous['pendingBundle'])
                need(self.previous['logicalBytes']==source_bundles.logical_bytes([*references,pending])
                    and base<=count<=base+pending['parts']
                    and count<=len(self.history.identities)<=min(count+1,base+pending['parts'])
                    and len(references)<=len(self.rows)<=len(references)+1)
                if len(self.rows)>len(references):
                    need(count==len(self.history.identities)==base+pending['parts']
                        and hashlib.sha256(canonical(self.rows[-1])).hexdigest()==pending['sha256'])
        if self.root_stamp is not None:need(stamp(self.store.path.lstat())==self.root_stamp)
        for path,signature in self.admitted.items():
            info=PrivateFeatureState(path).path.lstat()
            need([info.st_dev,info.st_ino,info.st_size,info.st_uid,info.st_mode,info.st_nlink,info.st_mtime_ns,info.st_ctime_ns]==signature)

    def held(self):
        held=ExitStack()
        try:
            for lock in sorted(self.locks,key=lambda value:str(value.path)):held.enter_context(lock.held())
            return held
        except BaseException:held.close();raise

    def save(self,phase,**changes):
        self.control();value={**(self.previous or {**self.scope,'chunks':[]}),'phase':phase,**deepcopy(changes)}
        self.store.write(value,self.previous);observed,_raw,physical=state(self.store);need(same(value,observed))
        self.previous=deepcopy(value);self.root_stamp=physical;self.cache_sha=self.cache_digest();self.control()

    def snapshot(self):
        files={};roots={};frames={};signatures={};total=0
        def read(key):
            nonlocal total
            value,raw,physical=state(self.stores[key]);plain(value)
            files[key]=(raw,physical);total+=len(raw);need(total<=LIMIT_BYTES)
            return value
        actor=read('actor')
        need(type(actor['picoChatCursorActorVersion']) is int and actor['picoChatCursorActorVersion']==3
            and all(same(actor[key],value) for key,value in self.expected.items()))
        if actor['phase']=='acquire-issued':
            exact(actor,EXPECTED|{'picoChatCursorActorVersion','phase'})
            raise PhasePending('The original Actor has not completed source acquisition')
        exact(actor,ACTOR);need(actor['phase']=='publishing');validate_actor_pairs(actor['pairs'])
        if actor['returnedPublication'] is None:raise PhasePending('Original Actor has not returned a publication')
        roots['cursor']=read('cursor');stages=roots['cursor'].get('stages')
        need(type(stages) is list and 1<=len(stages)<=3)
        stages=tuple(row.get('stage') for row in stages);need(stages==STAGES[:len(stages)])
        keys=('publisher','cursor','code')+tuple(stage+suffix for stage in stages for suffix in ('-observation','-samples'))
        for key in keys:
            root=roots[key] if key in roots else read(key);roots[key]=root
            need(root['phase']=='ready' and type(root['chunks']) is list and root['chunks'])
            remove={'phase','chunks'}|({'delivery','pending'} if key=='publisher' else {'stages','nextStage'} if key=='cursor' else {'revision'})
            scope={name:value for name,value in root.items() if name not in remove}
            if key in self.roots:
                old=self.roots[key];need(root['chunks'][:len(old['chunks'])]==old['chunks']
                    and same(scope,{name:value for name,value in old.items() if name not in remove}))
            history=ChatSourceChunks(self.stores[key],scope)
            before=tuple(history.signature(index) for index in range(len(root['chunks'])))
            for index,signature in enumerate(before):
                path=str(history.store(index).path);original=list(signature)
                need(path not in self.admitted or original==self.admitted[path]);signatures[path]=original
            frames[key]=history.load(root['chunks']);plain(frames[key]);need(tuple(history.identities)==before)
            total+=sum(row[2] for row in before)
            need(len(files)+len(signatures)<=LIMIT_FILES and total<=LIMIT_BYTES)
        need(set(self.roots)<=set(roots) and all(path in signatures for path in self.admitted))
        flow=read('flow');flow_rows=validate_flow(flow)
        need(all(same(flow[key],self.expected[key]) for key in ('runId','fixtureUrl','binding','peerBinding')))
        cleanup=read('cleanup') if stages[-1]=='cleanup' else None
        for key in ('actor','flow',*(['cleanup'] if cleanup is not None else [])):ChatSourceChunks(self.stores[key],{}).inventory(0)
        grammar=self.grammar.validate(roots,frames,self.stores,self.expected,flow,flow_rows,cleanup,stages)
        validate_publication_return(actor['returnedPublication'],publisher=roots['publisher'],cursor=roots['cursor'],rows=frames['publisher'],
            publisher_stamp=files['publisher'][1],cursor_stamp=files['cursor'][1])
        return dict(actor=actor,files=files,roots=roots,frames=frames,signatures=signatures,stages=stages,grammar=grammar)

    def fresh(self,clocks,started):
        measured=[]
        for clock,oldest in clocks:
            before=self.monotonic();epoch=clock();fresh(oldest,epoch);measured.append((before,epoch,oldest))
        ended=self.monotonic();need(number(ended,started,started+1.5)
            and all(epoch-oldest+math.ceil((ended-before)*1000)<=1500 for before,epoch,oldest in measured))

    def acquire(self,after_sequence):
        """Actual GET plus original source graph; no publication resend or offset."""
        need(not self.failed and self.stop_intent is None and integer(after_sequence,0));entered=False;pending=None
        try:
            started=self.monotonic();need(number(started,0,1e15));self.control()
            with self.held():
                entered=True
                try:
                    snapshot=self.snapshot();rows=snapshot['frames']['publisher'];need(after_sequence<=len(rows))
                    if after_sequence==len(rows):raise PhasePending('The original Actor has no newer returned publication')
                    latest=snapshot['frames'][snapshot['stages'][-1]+'-observation'][-1]
                    phase=self.source.read(latest['after'])
                    if not same(phase['status']['activations'],latest['after']['activations']):
                        raise PhasePending('Original independent Actor awaits the current actual fixture phase')
                except PhaseRetired:raise NativeUIError('The original Chat fixture phase has retired') from None
                except PhasePending as error:pending=error
                if pending is None:
                    need(self.guard() is not False)
                    received=deepcopy(self.source.client.request('/runs/'+self.expected['runId']));plain(received)
                    exact(received,{'schemaVersion','runId','area','ticket','sampleEpochMs','entries'})
                    need(type(received['schemaVersion']) is int and received['schemaVersion']==1
                        and received['runId']==self.expected['runId'] and received['area']=='chat'
                        and received['ticket']==phase['ticket']==rows[-1]['payload']['ticket']
                        and type(received['entries']) is list and len(received['entries'])==len(rows))
                    last=0
                    for actual,original in zip(received['entries'],rows):
                        exact(actual,{'ticket','actor','actorSequence','capturedEpochMs','facts','sequence','receivedEpochMs'})
                        need(integer(actual['sequence'],last+1) and all(same(actual[key],value) for key,value in original['payload'].items())
                            and number(actual['receivedEpochMs'],actual['capturedEpochMs']-250,received['sampleEpochMs']+250))
                        last=actual['sequence']
                    frame=snapshot['frames'][snapshot['stages'][-1]+'-samples'][latest['reference']['index']]
                    oldest=min(frame[key]['capturedEpochMs'] for key in ('primary','view','lifecycle'))
                    oldest=min(oldest,frame['compiledChat']['before']['requestedEpochMs'])
                    clocks=((self.source.epoch_ms,oldest),(self.peer_epoch_ms,frame['peer']['capturedEpochMs']),
                        (self.source.epoch_ms,phase['status']['capturedEpochMs']),(self.source.epoch_ms,received['sampleEpochMs']))
                    self.fresh(clocks,started)
                    record=dict(actorRawBase64=base64.b64encode(snapshot['files']['actor'][0]).decode('ascii'),
                        actorStamp=snapshot['files']['actor'][1],publication=deepcopy(rows[-1]),received=received,
                        phase=deepcopy(phase['status']),freshness=dict(startedMonotonic=started,primaryEpochMs=oldest,
                            peerEpochMs=frame['peer']['capturedEpochMs'],phaseEpochMs=phase['status']['capturedEpochMs'],
                            journalEpochMs=received['sampleEpochMs']),
                        roots={key:dict(rawBase64=base64.b64encode(raw).decode('ascii'),sha256=hashlib.sha256(raw).hexdigest(),stamp=physical)
                            for key,(raw,physical) in snapshot['files'].items()})
                    references=[] if self.previous is None else self.previous['bundles']
                    reference,parts=source_bundles.prepare(record,len(self.rows),references)
                    self.save('reading',bundles=references,pendingBundle=reference,
                        logicalBytes=source_bundles.logical_bytes([*references,reference]))
                    chunks=self.previous['chunks']
                    for part in parts:
                        chunks=self.history.append(part,chunks);self.cache_sha=self.cache_digest()
                        self.save('reading',chunks=chunks)
                    decoded,_raw=source_bundles.original(self.history,chunks,[*references,reference],len(self.rows))
                    need(same(decoded,record))
                    self.rows.append(record);self.admitted=snapshot['signatures'];self.roots=snapshot['roots'];self.cache_sha=self.cache_digest()
                    self.save('ready',chunks=chunks,bundles=[*references,reference],pendingBundle=None,
                        logicalBytes=source_bundles.logical_bytes([*references,reference]));result=deepcopy(received)
                    self.control();need(self.guard() is not False)
                    for key,(raw,physical) in snapshot['files'].items():need(raw_file(self.stores[key])==(raw,physical))
                    self.fresh(clocks,started)
            if pending is not None:raise pending
            self.control();self.fresh(clocks,started)
            self.grammar.commit(snapshot['grammar'])
            self.control();self.fresh(clocks,started);return result
        except ScriptSourceBusy:
            if not entered:raise PhasePending('Original Actor/Parent holds the source locks') from None
            self.failed=True;raise NativeUIError('Original remote Chat lock release is unresolved') from None
        except PhasePending:
            if pending is not None:raise
            self.failed=True;raise NativeUIError('Original remote Chat wait is unresolved') from None
        except BaseException:
            self.failed=True;raise NativeUIError('Original remote Chat publication is unresolved; originals remain') from None

    def original(self,index):
        """Historical original bytes only, including after actual Actor return."""
        need(not self.failed and self.previous is not None and self.previous['phase']=='ready'
            and integer(index,0,len(self.rows)-1) and same(self.store.read(),self.previous)
            and stamp(self.store.path.lstat())==self.root_stamp)
        value=original_record(self.history,self.previous,index)
        need(same(value,self.rows[index]) and same(self.store.read(),self.previous)
            and stamp(self.store.path.lstat())==self.root_stamp)
        self.history.verify();return value

    def fresh_current(self):
        """The same consumed originals, under Parent locks; never a new sample."""
        need(not self.failed and self.rows and self.previous['phase']=='ready')
        try:
            for lock in self.locks:lock.assert_held()
            self.control();need(self.guard() is not False)
            record=self.rows[-1];need(same(self.original(len(self.rows)-1),record))
            active=self.source.read(record['phase'])
            need(same(active['status']['activations'],record['phase']['activations']))
            need(self.guard() is not False);self.released_fresh_current()
            return True
        except BaseException:
            self.failed=True;raise NativeUIError('The original consumed Chat publication is no longer qualified') from None

    def released_fresh_current(self):
        """Final same-original clocks after actual lock exit, without UI guard."""
        try:
            self.control();need(self.rows and self.previous['phase']=='ready');original=self.rows[-1]['freshness']
            self.fresh(((self.source.epoch_ms,original['primaryEpochMs']),(self.peer_epoch_ms,original['peerEpochMs']),
                (self.source.epoch_ms,original['phaseEpochMs']),(self.source.epoch_ms,original['journalEpochMs'])),original['startedMonotonic'])
        except BaseException:
            self.failed=True;raise NativeUIError('The original consumed Chat publication exceeded its original clocks') from None

    def freeze(self,command):
        """Freeze after the distinct durable Parent intent, not a Stop success."""
        from adapters.chat_journey.actor_stop import shape
        self.control();need(self.stop_intent is None and shape(command)==2 and self.rows
            and command['instance']==self.expected['instance'] and command['runId']==self.expected['runId']
            and command['ticket']==self.rows[-1]['publication']['payload']['ticket']
            and command['consumedSequence']==self.rows[-1]['publication']['sequence']
            and command['consumedPayloadSha256']==digest(self.rows[-1]['publication']['payload']))
        self.stop_intent=deepcopy(command);self.cache_sha=self.cache_digest();self.control()
