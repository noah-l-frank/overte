"""Typed historical Chat graph DTO; never restore a live Actor from files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json

from adapters.chat_journey.evidence_archive import LIMIT_BYTES,LIMIT_FILES,stamp
from adapters.chat_journey.actor_stop import shape as stop_shape,validate as validate_stop,validate_publication_return
from adapters.chat_journey.flow_inputs import validate_flow
from adapters.chat_journey.observation import (STAGES,observation_sample,original_authority,validate_original_row)
from adapters.chat_journey.observation_cursor import stage_transition,plain
from adapters.chat_journey.samples import compose,continuity
from adapters.chat_journey.script_source import validate_transaction,pins
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.independent_chat_receiver import binding_pid
from adapters.native_feature_observation import exact,integer,need
from adapters.native_script_observation import original_history
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.observer_return import ObserverReturnReceiver,state,physical,parent_node
from adapters.script_journey.history import canonical,same,MAX_FRAMES
from feature_journeys.contract import identifier
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.witness import projection

VERSION=2
GRAPH=('publisher','cursor','initial-observation','initial-samples','code','active-observation','active-samples',
    'cleanup-observation','cleanup-samples')
STORES={*GRAPH,'actor','stop','seal','flow','cleanup'}
EXPECTED={'runId','fixtureUrl','binding','peerBinding','hostProcessIdentity','instance','stopCommand'}
ACTOR={'picoChatCursorActorVersion','instance','runId','fixtureUrl','binding','peerBinding','hostProcessIdentity',
    'phase','pairs','stopCommand','stopStamp','stopSha256','seal','sealSha256','closedPairs','sourceScope'}
SEAL={'chatCursorSourceSealVersion','runId','role','binding','peerBinding','kind','journal','phase','originals'}
ORIGINAL={'journal','sha256','chunkCount','stamp','chunkManifestSha256','framesSha256','chunkStampsSha256'}


def validate_actor_pairs(rows):
    need(type(rows) is list and len(rows)==2)
    for row,label in zip(rows,('peer-directory','peer-executable')):
        exact(row,{'label','node','fd','anchor'})
        need(row['label']==label and type(row['node']) is list and len(row['node'])==2
            and all(integer(field,0) for field in row['node']) and integer(row['fd'],0) and integer(row['anchor'],0)
            and row['fd']!=row['anchor'])
    need(len({field for row in rows for field in (row['fd'],row['anchor'])})==4
        and len({tuple(row['node']) for row in rows})==2)


def validate_source_graph(roots,frames_by_key,stores,expected,flow,flow_rows,cleanup,stages=STAGES):
    """Original complete stage-prefix grammar; no acquisition or freshness."""
    return _validate_source_graph(roots,frames_by_key,stores,expected,flow,flow_rows,cleanup,stages,{})


class ChatSourceGraphPrefix:
    """Pure JSON admission of an already validated immutable graph prefix.

    Physical acquisition, old child identities/bytes and final clocks remain
    the caller's independent obligations. Cold readers start with no prefix.
    A candidate is committed only after the actual caller's final guards.
    """
    def __init__(self):
        self.previous=None;self.sha=digest(None);self.failed=False
        self.pending=None;self.pending_sha=digest(None)

    def control(self):
        plain(self.previous);plain(self.pending)
        need(not self.failed and digest(self.previous)==self.sha and digest(self.pending)==self.pending_sha)

    def validate(self,roots,frames,stores,expected,flow,flow_rows,cleanup,stages):
        self.control()
        try:
            for value in (roots,frames,expected,flow,flow_rows,cleanup):plain(value)
            need(type(stores) is dict and all(type(value) is PrivateFeatureState for value in stores.values())
                and type(stages) is tuple and stages==STAGES[:len(stages)] and stages)
            candidate=dict(expected=deepcopy(expected),paths={key:str(value.path) for key,value in stores.items()},pins=pins(),
                flow={key:deepcopy(value) for key,value in flow.items() if key!='payload'},
                flowRows=[digest(row) for row in flow_rows if row['phase']=='completed'],
                cleanup=None if cleanup is None else digest(cleanup),stages=list(stages),
                frames={key:[digest(row) for row in value] for key,value in frames.items()})
            counts={}
            if self.previous is not None:
                old=self.previous
                need(all(same(candidate[key],old[key]) for key in ('expected','paths','flow','pins'))
                    and candidate['stages'][:len(old['stages'])]==old['stages']
                    and candidate['flowRows'][:len(old['flowRows'])]==old['flowRows']
                    and (old['cleanup'] is None or candidate['cleanup']==old['cleanup'])
                    and set(old['frames'])<=set(candidate['frames']))
                for key,hashes in old['frames'].items():
                    need(candidate['frames'][key][:len(hashes)]==hashes);counts[key]=len(hashes)
            _validate_source_graph(roots,frames,stores,expected,flow,flow_rows,cleanup,stages,counts)
            self.control();self.pending=dict(previousSha256=self.sha,value=candidate,sha256=digest(candidate))
            self.pending_sha=digest(self.pending);self.control();return self.pending
        except BaseException:self.failed=True;raise

    def commit(self,candidate):
        self.control();plain(candidate);exact(candidate,{'previousSha256','value','sha256'})
        need(candidate is self.pending and candidate['previousSha256']==self.sha and digest(candidate['value'])==candidate['sha256'])
        self.previous=deepcopy(candidate['value']);self.sha=candidate['sha256']
        self.pending=None;self.pending_sha=digest(None);self.control()


def _validate_source_graph(roots,frames_by_key,stores,expected,flow,flow_rows,cleanup,stages,counts):
    need(type(stages) is tuple and 1<=len(stages)<=len(STAGES) and stages==STAGES[:len(stages)])
    run,binding,peer=expected['runId'],expected['binding'],expected['peerBinding']
    pid,peer_pid=binding_pid(binding),binding_pid(peer)
    code=roots['code'];exact(code,{'chatScriptObservationVersion','runId','role','binding','phase','revision','chunks'})
    need(type(code['chatScriptObservationVersion']) is int and code['chatScriptObservationVersion']==1
        and code['runId']==run and code['role']=='actor' and same(code['binding'],binding)
        and type(code['revision']) is int and code['revision']==2*len(frames_by_key['code']))
    for index,frame in enumerate(frames_by_key['code']):
        if index>=counts.get('code',0):validate_transaction(frame,frames_by_key['code'][:index],pid=pid)
    original_history([frame['scripts'] for frame in frames_by_key['code']],pid)
    code_frames={frame['ticket']:frame for frame in frames_by_key['code']};need(len(code_frames)==len(frames_by_key['code']))
    observed=[];selected=[]
    for stage in stages:
        key=stage+'-samples';root=roots[key];frames=frames_by_key[key]
        version='chatCompiledSamplesVersion' if stage=='active' else 'chatCompiledCacheAbsenceVersion'
        exact(root,{version,'runId','role','binding','peerBinding','vr','phase','revision','chunks'})
        need(type(root[version]) is int and root[version]==1 and root['runId']==run and root['role']=='actor'
            and same(root['binding'],binding) and same(root['peerBinding'],peer) and root['vr'] is True
            and type(root['revision']) is int and root['revision']==2*len(frames))
        for index,frame in enumerate(frames):
            if index<counts.get(key,0):continue
            compose(run,frame,pid,peer_pid,vr=True,cache_absent=stage!='active');continuity(frames[:index],frame)
            need(same(frame['compiledChat'],code_frames[frame['compiledChat']['ticket']]))
        key=stage+'-observation';root=roots[key];rows=frames_by_key[key]
        exact(root,{'chatObservationOwnerVersion','contractVersion','runId','fixtureUrl','role','binding','peerBinding','stage',
            'transcript','flowJournal','cleanupAdmission','phase','revision','chunks'})
        need(type(root['chatObservationOwnerVersion']) is int and root['chatObservationOwnerVersion']==1
            and type(root['contractVersion']) is int and root['contractVersion']==CONTRACT_VERSION
            and all(same(root[name],expected[name]) for name in ('runId','fixtureUrl','binding','peerBinding'))
            and root['role']=='actor' and root['stage']==stage and root['transcript']==stores[stage+'-samples'].path.name
            and root['flowJournal']==stores['flow'].path.name
            and root['cleanupAdmission']==(stores['cleanup'].path.name if stage=='cleanup' else None)
            and type(root['revision']) is int and root['revision']==2*len(rows))
        if stage!='cleanup':need(root['transcript'] in flow['baselineTranscripts' if stage=='initial' else 'transcripts'][1:])
        def authority(count):return original_authority(flow,flow_rows,stage,count,run=run,binding=binding,peer_binding=peer,cleanup=cleanup)
        def sample(sequence,frame):
            need(not frame.get('settings') and not frame.get('transition'))
            return observation_sample(run,sequence,compose(run,frame,pid,peer_pid,vr=True,cache_absent=stage!='active'))
        for index,row in enumerate(rows):
            if index<counts.get(key,0):frame=frames[row['reference']['index']]
            else:
                frame=validate_original_row(row,index+1,rows[index-1]['after'] if index else None,run=run,authority=authority,
                    source_frame=lambda position:frames[position],source_count=len(frames),sample=sample)
            selected.append((stage,index+1,row,frame))
        observed.append(dict(stage=stage,observation=stores[key].path.name,
            scopeSha256=digest({name:value for name,value in root.items() if name not in ('phase','revision','chunks')})))
    cursor=roots['cursor']
    initial_shape=stages==('initial',) and 'nextStage' not in cursor
    exact(cursor,{'chatObservationCursorVersion','runId','fixtureUrl','binding','peerBinding','role','phase','chunks','stages'}
        | (set() if initial_shape else {'nextStage'}))
    need(type(cursor['chatObservationCursorVersion']) is int and cursor['chatObservationCursorVersion']==1 and cursor['role']=='actor'
        and all(same(cursor[name],expected[name]) for name in ('runId','fixtureUrl','binding','peerBinding'))
        and cursor.get('nextStage') is None and same(cursor['stages'],observed) and len(frames_by_key['cursor'])==len(selected))
    prior=None
    for index,(row,(stage,sequence,original,frame)) in enumerate(zip(frames_by_key['cursor'],selected)):
        if index>=counts.get('cursor',0):
            exact(row,{'sequence','stageIndex','sourceSequence','observationSha256','sample'})
            need(type(row['sequence']) is int and row['sequence']==index+1 and type(row['stageIndex']) is int
                and row['stageIndex']==STAGES.index(stage) and type(row['sourceSequence']) is int and row['sourceSequence']==sequence
                and row['observationSha256']==digest(original) and same(row['sample'],{**original['sample'],'sequence':index+1}))
            if prior is not None and stage!=prior[0]:stage_transition(prior[1],frame,stage)
        prior=(stage,frame)
    publisher=roots['publisher'];exact(publisher,{'chatObservationPublisherVersion','runId','fixtureUrl','binding','peerBinding','cursor','phase','delivery','chunks','pending'})
    need(type(publisher['chatObservationPublisherVersion']) is int and publisher['chatObservationPublisherVersion']==1
        and all(same(publisher[name],expected[name]) for name in ('runId','fixtureUrl','binding','peerBinding'))
        and publisher['cursor']==stores['cursor'].path.name and publisher['delivery']=='ready' and publisher['pending'] is None
        and len(frames_by_key['publisher'])==len(frames_by_key['cursor']))
    for index,(row,cursor,selected_row) in enumerate(zip(frames_by_key['publisher'],frames_by_key['cursor'],selected)):
        if index<counts.get('publisher',0):continue
        exact(row,{'sequence','cursorSha256','payload'});local=selected_row[2]
        payload=dict(ticket=local['before']['activations'][-1]['ticket'],actor='owned-observer',actorSequence=index+1,
            capturedEpochMs=cursor['sample']['capturedEpochMs'],facts=projection('chat',cursor['sample']['state']))
        need(type(row['sequence']) is int and row['sequence']==index+1 and row['cursorSha256']==digest(cursor) and same(row['payload'],payload))


class ChatRemoteActorGraph:
    """Pending historical admission only, until a distinct process-return join.

    All paths are supplied by the original typed Parent factory. The returned
    manifest may neither discover paths nor construct live source/Actor owners.
    Version 2 admits Actor v2/v3's single original witness code source and
    three complete stages, with explicit Stop1/Stop2 admission per Actor.
    Other extensions fail closed.
    """
    def __init__(self,raw,source_stamp,stores,expected):
        need(type(raw) is bytes and 0<len(raw)<=65536 and type(stores) is dict and set(stores)==STORES
            and all(type(store) is PrivateFeatureState for store in stores.values()))
        exact(expected,EXPECTED);plain(expected);context(expected['binding']);context(expected['peerBinding'])
        identifier(expected['runId']);identifier(expected['instance']);physical(source_stamp)
        paths=[value.path for value in stores.values()]
        need(len(set(paths))==len(paths) and all(value.parent==paths[0].parent for value in paths))
        self.stores=dict(stores);self.paths={key:str(store.path) for key,store in stores.items()};self.parent=parent_node(stores['actor'])
        self.expected=deepcopy(expected);self.expected_sha=digest(expected)
        self.raw,self.source_stamp=raw,deepcopy(source_stamp);self.root=json.loads(raw)
        plain(self.root);need(canonical(self.root)+b'\n'==raw)
        exact(self.root,ACTOR|({'returnedPublication'} if self.root.get('picoChatCursorActorVersion')==3 else set()))
        self.pending=True;self.failed=False;self.successor=None;self.successor_sha=None;self.files={};self.histories={};self.roots={};self.frames={};self.total=0
        self.validate_actor();self.load();self.validate();self.cache_sha=self.cache_digest();self.verify()

    def retain(self,key):
        store=self.stores[key];value,raw,physical_stamp=state(store)
        self.files[key]=(raw,physical_stamp);self.total+=len(raw)
        need(len(self.files)<=LIMIT_FILES and self.total<=LIMIT_BYTES)
        return value

    def validate_actor(self):
        value=self.root;expected=self.expected
        need(type(value['picoChatCursorActorVersion']) is int and value['picoChatCursorActorVersion'] in (2,3)
            and all(same(value[key],expected[key]) for key in EXPECTED)
            and value['phase']=='host-closed' and value['sourceScope']=='original-independent-chat-host-handles'
            and type(value['closedPairs']) is int and value['closedPairs']==2)
        validate_actor_pairs(value['pairs'])
        stop=value['stopCommand'];version=stop_shape(stop)
        need(stop['instance']==expected['instance'] and stop['runId']==expected['runId']
            and (value['picoChatCursorActorVersion']>=3 or version==1))
        physical(value['stopStamp'])
        need(value['sealSha256']==digest(value['seal']))
        observed=self.retain('actor');need(same(observed,value) and self.files['actor']==(self.raw,self.source_stamp))
        observed=self.retain('stop');need(same(observed,stop) and self.files['stop'][1]==value['stopStamp']
            and hashlib.sha256(self.files['stop'][0]).hexdigest()==value['stopSha256'])
        seal=self.retain('seal');exact(seal,SEAL)
        need(same(seal,value['seal']) and type(seal['chatCursorSourceSealVersion']) is int and seal['chatCursorSourceSealVersion']==1
            and seal['phase']=='sealed' and seal['kind']=='cleanup-global-publisher' and seal['role']=='actor'
            and all(same(seal[key],expected[key]) for key in ('runId','binding','peerBinding'))
            and seal['journal']==self.stores['publisher'].path.name and type(seal['originals']) is list
            and len(seal['originals'])==len(GRAPH))
        for key in ('actor','stop','seal'):ChatSourceChunks(self.stores[key],{}).inventory(0)

    def load(self):
        for key,original in zip(GRAPH,self.root['seal']['originals']):
            exact(original,ORIGINAL);physical(original['stamp']);root=self.retain(key)
            need(original['journal']==self.stores[key].path.name and digest(root)==original['sha256']
                and self.files[key][1]==original['stamp'] and root['phase']=='ready'
                and type(root['chunks']) is list and integer(original['chunkCount'],1,MAX_FRAMES)
                and original['chunkCount']==len(root['chunks']) and digest(root['chunks'])==original['chunkManifestSha256'])
            remove={'phase','chunks'}|({'delivery','pending'} if key=='publisher' else {'stages','nextStage'} if key=='cursor' else {'revision'})
            scope={name:value for name,value in root.items() if name not in remove}
            history=ChatSourceChunks(self.stores[key],scope)
            admitted=tuple(history.signature(index) for index in range(len(root['chunks'])))
            frames=history.load(root['chunks'])
            need(tuple(history.identities)==admitted and digest(frames)==original['framesSha256']
                and digest([list(value) for value in admitted])==original['chunkStampsSha256'])
            self.histories[key]=history;self.roots[key]=root;self.frames[key]=frames
            self.total+=sum(value[2] for value in admitted)
            need(len(self.files)+sum(len(value.identities) for value in self.histories.values())<=LIMIT_FILES and self.total<=LIMIT_BYTES)
        self.flow=self.retain('flow');self.flow_rows=validate_flow(self.flow);self.cleanup=self.retain('cleanup')
        need(len(self.flow_rows)==26 and all(row['phase']=='completed' for row in self.flow_rows)
            and all(same(self.flow[key],self.expected[key]) for key in ('runId','fixtureUrl','binding','peerBinding')))
        for key in ('flow','cleanup'):ChatSourceChunks(self.stores[key],{}).inventory(0)

    def validate(self):
        validate_source_graph(self.roots,self.frames,self.stores,self.expected,self.flow,self.flow_rows,self.cleanup)
        run=self.expected['runId'];publisher=self.roots['publisher']
        validate_stop(self.root['stopCommand'],instance=self.expected['instance'],run=run,published=self.frames['publisher'])
        if self.root['picoChatCursorActorVersion']==3:
            validate_publication_return(self.root['returnedPublication'],publisher=publisher,cursor=self.roots['cursor'],rows=self.frames['publisher'],
                publisher_stamp=self.files['publisher'][1],cursor_stamp=self.files['cursor'][1])

    def admit_successor(self,receiver):
        """One exact nonce-bound successor; original payload stays historical."""
        need(type(receiver) is ObserverReturnReceiver and receiver.issued and not receiver.complete and self.pending
            and self.successor is None and not self.failed and receiver.raw==self.raw
            and receiver.scope['family']=='pico-chat-cursor-actor'
            and receiver.scope['sourceStamp']==self.source_stamp
            and receiver.scope['producerHostProcessIdentity']==self.expected['hostProcessIdentity']
            and receiver.scope['runId']==self.expected['runId']
            and receiver.scope['originalRequestId']==self.expected['stopCommand']['commandId'])
        self._verify(ignore_actor=True);value,_raw,_physical=receiver.consumed()
        expected={**self.root,'phase':'parent-consumed','returnId':value['returnId'],'returnSha256':digest(value),
            'consumptionSha256':value['consumptionSha256'],
            'parentHostProcessIdentity':value['consumption']['consumerHostProcessIdentity']}
        observed,raw,physical_stamp=state(self.stores['actor'])
        need(same(observed,expected))
        self.successor=(raw,physical_stamp);self.successor_sha=digest(dict(sha256=hashlib.sha256(raw).hexdigest(),stamp=physical_stamp))
        self.verify()

    def cache_digest(self):
        return digest(dict(expected=self.expected,root=self.root,sourceStamp=self.source_stamp,rawSha256=hashlib.sha256(self.raw).hexdigest(),
            roots=self.roots,frames=self.frames,flow=self.flow,cleanup=self.cleanup,paths=self.paths,parent=self.parent,
            files={key:dict(sha256=hashlib.sha256(row[0]).hexdigest(),stamp=row[1]) for key,row in self.files.items()},
            histories={key:dict(identities=history.identities,rawBytes=history.raw_bytes,scope=history.scope)
                for key,history in self.histories.items()}))

    def verify(self):
        try:self._verify()
        except Exception:self.failed=True;raise

    def _verify(self,*,ignore_actor=False):
        for value in (self.root,self.roots,self.frames,self.expected,self.flow,self.cleanup):plain(value)
        physical(self.source_stamp)
        need(type(self.files) is dict and set(self.files)==STORES and set(self.histories)==set(self.frames)==set(self.roots)==set(GRAPH)
            and all(type(row) is tuple and len(row)==2 and type(row[0]) is bytes
            and type(row[1]) is list and len(row[1])==8 and all(type(field) is int for field in row[1])
            for row in self.files.values()))
        need(not self.failed and type(self.raw) is bytes and digest(self.expected)==self.expected_sha
            and self.cache_digest()==self.cache_sha and parent_node(self.stores['actor'])==self.parent
            and all(str(store.path)==self.paths[key] for key,store in self.stores.items()))
        for key,(raw,physical_stamp) in self.files.items():
            if key=='actor':
                if ignore_actor:continue
                if self.successor is not None:
                    need(type(self.successor) is tuple and len(self.successor)==2 and type(self.successor[0]) is bytes)
                    raw,physical_stamp=self.successor;physical(physical_stamp)
                    need(digest(dict(sha256=hashlib.sha256(raw).hexdigest(),stamp=physical_stamp))==self.successor_sha)
            value,current,physical_now=state(self.stores[key]);need(current==raw and physical_now==physical_stamp)
        for key,history in self.histories.items():
            need(history.root is self.stores[key] and type(history.identities) is list
                and all(type(row) is tuple and len(row)==8 and all(type(field) is int for field in row) for row in history.identities)
                and type(history.raw_bytes) is int and type(history.scope) is str);history.verify()
        for key in ('actor','stop','seal','flow','cleanup'):ChatSourceChunks(self.stores[key],{}).inventory(0)
