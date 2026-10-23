"""Typed historical Chat graph DTO; never restore a live Actor from files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json

from adapters.chat_journey.evidence_archive import LIMIT_BYTES,LIMIT_FILES,stamp
from adapters.chat_journey.flow_inputs import validate_flow
from adapters.chat_journey.observation import (STAGES,observation_sample,original_authority,validate_original_row)
from adapters.chat_journey.observation_cursor import stage_transition,plain
from adapters.chat_journey.samples import compose,continuity
from adapters.chat_journey.script_source import validate_transaction
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.independent_chat_receiver import binding_pid
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.observer_return import state,physical,parent_node
from adapters.script_journey.history import canonical,same,MAX_FRAMES
from feature_journeys.contract import identifier
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.witness import projection

VERSION=1
GRAPH=('publisher','cursor','initial-observation','initial-samples','code','active-observation','active-samples',
    'cleanup-observation','cleanup-samples')
STORES={*GRAPH,'actor','stop','seal','flow','cleanup'}
EXPECTED={'runId','fixtureUrl','binding','peerBinding','hostProcessIdentity','instance','stopCommand'}
ACTOR={'picoChatCursorActorVersion','instance','runId','fixtureUrl','binding','peerBinding','hostProcessIdentity',
    'phase','pairs','stopCommand','stopStamp','stopSha256','seal','sealSha256','closedPairs','sourceScope'}
SEAL={'chatCursorSourceSealVersion','runId','role','binding','peerBinding','kind','journal','phase','originals'}
ORIGINAL={'journal','sha256','chunkCount','stamp','chunkManifestSha256','framesSha256','chunkStampsSha256'}


class ChatRemoteActorGraph:
    """Pending historical admission only, until a distinct process-return join.

    All paths are supplied by the original typed Parent factory. The returned
    manifest may neither discover paths nor construct live source/Actor owners.
    Version 1 admits exactly the current Actor v2's single original witness
    code source and three complete stages; extensions fail closed.
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
        plain(self.root);need(canonical(self.root)+b'\n'==raw);exact(self.root,ACTOR)
        self.pending=True;self.failed=False;self.files={};self.histories={};self.roots={};self.frames={};self.total=0
        self.validate_actor();self.load();self.validate();self.cache_sha=self.cache_digest();self.verify()

    def retain(self,key):
        store=self.stores[key];value,raw,physical_stamp=state(store)
        self.files[key]=(raw,physical_stamp);self.total+=len(raw)
        need(len(self.files)<=LIMIT_FILES and self.total<=LIMIT_BYTES)
        return value

    def validate_actor(self):
        value=self.root;expected=self.expected
        need(type(value['picoChatCursorActorVersion']) is int and value['picoChatCursorActorVersion']==2
            and all(same(value[key],expected[key]) for key in EXPECTED)
            and value['phase']=='host-closed' and value['sourceScope']=='original-independent-chat-host-handles'
            and type(value['closedPairs']) is int and value['closedPairs']==2
            and type(value['pairs']) is list and len(value['pairs'])==2)
        for row,label in zip(value['pairs'],('peer-directory','peer-executable')):
            exact(row,{'label','node','fd','anchor'})
            need(row['label']==label and type(row['node']) is list and len(row['node'])==2
                and all(integer(field,0) for field in row['node']) and integer(row['fd'],0) and integer(row['anchor'],0)
                and row['fd']!=row['anchor'])
        need(len({field for row in value['pairs'] for field in (row['fd'],row['anchor'])})==4
            and len({tuple(row['node']) for row in value['pairs']})==2)
        stop=value['stopCommand'];exact(stop,{'picoChatCursorActorStopVersion','commandId','instance','runId','afterSequence','ticket'})
        need(type(stop['picoChatCursorActorStopVersion']) is int and stop['picoChatCursorActorStopVersion']==1
            and stop['instance']==expected['instance'] and stop['runId']==expected['runId']
            and integer(stop['afterSequence'],1,MAX_FRAMES))
        identifier(stop['commandId']);identifier(stop['ticket']);physical(value['stopStamp'])
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
        run,binding,peer=self.expected['runId'],self.expected['binding'],self.expected['peerBinding']
        pid,peer_pid=binding_pid(binding),binding_pid(peer)
        code=self.roots['code'];exact(code,{'chatScriptObservationVersion','runId','role','binding','phase','revision','chunks'})
        need(type(code['chatScriptObservationVersion']) is int and code['chatScriptObservationVersion']==1
            and code['runId']==run and code['role']=='actor' and same(code['binding'],binding)
            and type(code['revision']) is int and code['revision']==2*len(self.frames['code']))
        for index,frame in enumerate(self.frames['code']):validate_transaction(frame,self.frames['code'][:index],pid=pid)
        code_frames={frame['ticket']:frame for frame in self.frames['code']};need(len(code_frames)==len(self.frames['code']))
        observed=[];selected=[]
        for stage in STAGES:
            key=stage+'-samples';root=self.roots[key];frames=self.frames[key]
            version='chatCompiledSamplesVersion' if stage=='active' else 'chatCompiledCacheAbsenceVersion'
            exact(root,{version,'runId','role','binding','peerBinding','vr','phase','revision','chunks'})
            need(type(root[version]) is int and root[version]==1 and root['runId']==run and root['role']=='actor'
                and same(root['binding'],binding) and same(root['peerBinding'],peer) and root['vr'] is True
                and type(root['revision']) is int and root['revision']==2*len(frames))
            for index,frame in enumerate(frames):
                compose(run,frame,pid,peer_pid,vr=True,cache_absent=stage!='active');continuity(frames[:index],frame)
                need(same(frame['compiledChat'],code_frames[frame['compiledChat']['ticket']]))
            key=stage+'-observation';root=self.roots[key];rows=self.frames[key]
            exact(root,{'chatObservationOwnerVersion','contractVersion','runId','fixtureUrl','role','binding','peerBinding','stage',
                'transcript','flowJournal','cleanupAdmission','phase','revision','chunks'})
            need(type(root['chatObservationOwnerVersion']) is int and root['chatObservationOwnerVersion']==1
                and type(root['contractVersion']) is int and root['contractVersion']==CONTRACT_VERSION
                and all(same(root[name],self.expected[name]) for name in ('runId','fixtureUrl','binding','peerBinding'))
                and root['role']=='actor' and root['stage']==stage and root['transcript']==self.stores[stage+'-samples'].path.name
                and root['flowJournal']==self.stores['flow'].path.name
                and root['cleanupAdmission']==(self.stores['cleanup'].path.name if stage=='cleanup' else None)
                and type(root['revision']) is int and root['revision']==2*len(rows))
            if stage!='cleanup':need(root['transcript'] in self.flow['baselineTranscripts' if stage=='initial' else 'transcripts'][1:])
            def authority(count):return original_authority(self.flow,self.flow_rows,stage,count,run=run,binding=binding,peer_binding=peer,cleanup=self.cleanup)
            def sample(sequence,frame):
                need(not frame.get('settings') and not frame.get('transition'))
                return observation_sample(run,sequence,compose(run,frame,pid,peer_pid,vr=True,cache_absent=stage!='active'))
            for index,row in enumerate(rows):
                frame=validate_original_row(row,index+1,rows[index-1]['after'] if index else None,run=run,authority=authority,
                    source_frame=lambda position:frames[position],source_count=len(frames),sample=sample)
                selected.append((stage,index+1,row,frame))
            observed.append(dict(stage=stage,observation=self.stores[key].path.name,
                scopeSha256=digest({name:value for name,value in root.items() if name not in ('phase','revision','chunks')})))
        cursor=self.roots['cursor'];exact(cursor,{'chatObservationCursorVersion','runId','fixtureUrl','binding','peerBinding','role','phase','chunks','stages','nextStage'})
        need(type(cursor['chatObservationCursorVersion']) is int and cursor['chatObservationCursorVersion']==1 and cursor['role']=='actor'
            and all(same(cursor[name],self.expected[name]) for name in ('runId','fixtureUrl','binding','peerBinding'))
            and cursor['nextStage'] is None and same(cursor['stages'],observed) and len(self.frames['cursor'])==len(selected))
        prior=None
        for index,(row,(stage,sequence,original,frame)) in enumerate(zip(self.frames['cursor'],selected)):
            exact(row,{'sequence','stageIndex','sourceSequence','observationSha256','sample'})
            need(type(row['sequence']) is int and row['sequence']==index+1 and type(row['stageIndex']) is int
                and row['stageIndex']==STAGES.index(stage) and type(row['sourceSequence']) is int and row['sourceSequence']==sequence
                and row['observationSha256']==digest(original) and same(row['sample'],{**original['sample'],'sequence':index+1}))
            if prior is not None and stage!=prior[0]:stage_transition(prior[1],frame,stage)
            prior=(stage,frame)
        publisher=self.roots['publisher'];exact(publisher,{'chatObservationPublisherVersion','runId','fixtureUrl','binding','peerBinding','cursor','phase','delivery','chunks','pending'})
        need(type(publisher['chatObservationPublisherVersion']) is int and publisher['chatObservationPublisherVersion']==1
            and all(same(publisher[name],self.expected[name]) for name in ('runId','fixtureUrl','binding','peerBinding'))
            and publisher['cursor']==self.stores['cursor'].path.name and publisher['delivery']=='ready' and publisher['pending'] is None
            and len(self.frames['publisher'])==len(self.frames['cursor']))
        for index,(row,cursor,selected_row) in enumerate(zip(self.frames['publisher'],self.frames['cursor'],selected)):
            exact(row,{'sequence','cursorSha256','payload'});local=selected_row[2]
            payload=dict(ticket=local['before']['activations'][-1]['ticket'],actor='owned-observer',actorSequence=index+1,
                capturedEpochMs=cursor['sample']['capturedEpochMs'],facts=projection('chat',cursor['sample']['state']))
            need(type(row['sequence']) is int and row['sequence']==index+1 and row['cursorSha256']==digest(cursor) and same(row['payload'],payload))
        stop=self.root['stopCommand'];need(stop['afterSequence']==len(self.frames['publisher']) and stop['ticket']==self.frames['publisher'][-1]['payload']['ticket'])

    def cache_digest(self):
        return digest(dict(expected=self.expected,root=self.root,sourceStamp=self.source_stamp,rawSha256=hashlib.sha256(self.raw).hexdigest(),
            roots=self.roots,frames=self.frames,flow=self.flow,cleanup=self.cleanup,paths=self.paths,parent=self.parent,
            files={key:dict(sha256=hashlib.sha256(row[0]).hexdigest(),stamp=row[1]) for key,row in self.files.items()},
            histories={key:dict(identities=history.identities,rawBytes=history.raw_bytes,scope=history.scope)
                for key,history in self.histories.items()}))

    def verify(self):
        try:self._verify()
        except Exception:self.failed=True;raise

    def _verify(self):
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
            value,current,physical_now=state(self.stores[key]);need(current==raw and physical_now==physical_stamp)
        for key,history in self.histories.items():
            need(history.root is self.stores[key] and type(history.identities) is list
                and all(type(row) is tuple and len(row)==8 and all(type(field) is int for field in row) for row in history.identities)
                and type(history.raw_bytes) is int and type(history.scope) is str);history.verify()
        for key in ('actor','stop','seal','flow','cleanup'):ChatSourceChunks(self.stores[key],{}).inventory(0)
