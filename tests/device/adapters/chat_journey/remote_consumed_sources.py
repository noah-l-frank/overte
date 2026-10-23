"""Consumed original Chat prefix, full actual Actor return and primary seal.

Historical source closure only. Application restart, IPC, archival, final host
closure, successful shared execution and public capability remain separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json

from adapters.chat_journey.actor_stop import validate_publication_return
from adapters.chat_journey.cursor_source_seal import ChatCursorSourceSeal
from adapters.chat_journey.flow_inputs import validate_flow
from adapters.chat_journey.observation import STAGES
from adapters.chat_journey.observation_cursor import plain
from adapters.chat_journey.remote_actor_graph import ChatSourceGraphPrefix,validate_actor_pairs
from adapters.chat_journey.remote_actor_return import ChatRemoteActorReturn
from adapters.chat_journey.remote_cleanup_prefix import ChatRemoteCleanupPrefix
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import state,parent_node,physical
from adapters.script_journey.history import canonical,same,unpack

VERSION=1


def literal(value):
    exact(value,{'rawBase64','sha256','stamp'});physical(value['stamp'])
    need(type(value['rawBase64']) is str and type(value['sha256']) is str)
    raw=base64.b64decode(value['rawBase64'],validate=True);root=json.loads(raw);plain(root)
    need(canonical(root)+b'\n'==raw and hashlib.sha256(raw).hexdigest()==value['sha256'])
    return root,raw


def returned_prefix(prefix,returned):
    """No current/native authority, and no reconstructed Actor or reader."""
    need(type(prefix) is ChatRemoteCleanupPrefix and prefix.completed and not prefix.failed
        and prefix.raw is prefix.journey.cleanup_consumption and type(returned) is ChatRemoteActorReturn
        and returned.complete and not returned.failed and returned.process is prefix.actor.process)
    prefix.control();returned.receipt();graph=returned.graph;reader=prefix.actor
    need(not graph.pending and not reader.failed and reader.cache_digest()==reader.cache_sha
        and parent_node(reader.store)==reader.parent and same(reader.store.read(),reader.previous)
        and state(reader.store)[2]==reader.root_stamp and same(reader.stop_intent,prefix.command)
        and all(graph.stores[key].path==store.path for key,store in reader.stores.items())
        and same(graph.root['stopCommand'],prefix.command) and graph.stores['stop'].path==prefix.stop_store.path
        and prefix.command['cleanupConsumptionSha256']==hashlib.sha256(prefix.raw).hexdigest())
    reader.history.verify()
    original={str(history.store(index).path):list(signature) for history in graph.histories.values()
        for index,signature in enumerate(history.identities)}
    need(all(original.get(path)==signature for path,signature in reader.admitted.items()))
    stop,stop_raw,stop_stamp=state(prefix.stop_store)
    need(same(stop,prefix.command) and stop_stamp==prefix.previous['stopStamp']
        and hashlib.sha256(stop_raw).hexdigest()==prefix.previous['stopSha256'])
    reconstructed={**prefix.previous['header'],'samples':[row['common'] for row in prefix.rows]}
    need(canonical(reconstructed)==prefix.raw)
    for index,row in enumerate(prefix.rows):
        chunk=prefix.history.store(index).read()
        need(digest(chunk)==prefix.previous['chunks'][index] and same(unpack(chunk['transcript']),[row]))
    # One EMPTY pure memo per complete historical pass. Every record/literal
    # is still read, hashed and joined to the actual final graph below; only
    # grammar already accepted in this same pass can supply a prefix.
    grammar=ChatSourceGraphPrefix()
    for index,record in enumerate(reader.rows):
        chunk=reader.history.store(index).read()
        need(digest(chunk)==reader.previous['chunks'][index] and same(unpack(chunk['transcript']),[record]))
        roots={key:literal(value)[0] for key,value in record['roots'].items()}
        stages=tuple(row['stage'] for row in roots['cursor']['stages'])
        need(1<=len(stages)<=3 and stages==STAGES[:len(stages)]
            and set(roots)=={'actor','flow','publisher','cursor','code',
                *[stage+suffix for stage in stages for suffix in ('-observation','-samples')],
                *(['cleanup'] if stages[-1]=='cleanup' else [])})
        actor,raw=literal(record['roots']['actor'])
        need(base64.b64decode(record['actorRawBase64'],validate=True)==raw
            and same(record['actorStamp'],record['roots']['actor']['stamp'])
            and actor['phase']=='publishing' and actor['picoChatCursorActorVersion']==3
            and all(same(actor[key],graph.root[key]) for key in reader.expected)
            and same(actor['pairs'],graph.root['pairs']))
        validate_actor_pairs(actor['pairs']);frames={}
        for key in ('publisher','cursor','code',*[stage+suffix for stage in stages for suffix in ('-observation','-samples')]):
            root,final=roots[key],graph.roots[key];need(root['phase']=='ready' and root['chunks']
                and same(root['chunks'],final['chunks'][:len(root['chunks'])]))
            remove={'phase','chunks','revision'}|({'delivery','pending'} if key=='publisher' else {'stages','nextStage'} if key=='cursor' else set())
            need(same({name:value for name,value in root.items() if name not in remove},
                {name:value for name,value in final.items() if name not in remove}))
            frames[key]=graph.frames[key][:len(root['chunks'])]
        flow=roots['flow'];flow_rows=validate_flow(flow)
        need(same(flow_rows,graph.flow_rows[:len(flow_rows)])
            and same({key:value for key,value in flow.items() if key!='payload'},
                {key:value for key,value in graph.flow.items() if key!='payload'}))
        cleanup=roots.get('cleanup')
        if cleanup is not None:
            need(same(cleanup,graph.cleanup) and record['roots']['cleanup']['stamp']==graph.files['cleanup'][1]
                and literal(record['roots']['cleanup'])[1]==graph.files['cleanup'][0])
        candidate=grammar.validate(roots,frames,graph.stores,reader.expected,flow,flow_rows,cleanup,stages)
        validate_publication_return(actor['returnedPublication'],publisher=roots['publisher'],cursor=roots['cursor'],
            rows=frames['publisher'],publisher_stamp=record['roots']['publisher']['stamp'],cursor_stamp=record['roots']['cursor']['stamp'])
        need(same(record['publication'],frames['publisher'][-1]) and len(record['received']['entries'])==len(frames['publisher']))
        for actual,published in zip(record['received']['entries'],frames['publisher']):
            need(all(same(actual[key],value) for key,value in published['payload'].items()))
        grammar.commit(candidate)
    consumed=prefix.command['consumedSequence']
    need(consumed<=len(graph.frames['publisher']) and prefix.command['consumedPayloadSha256']==digest(graph.frames['publisher'][consumed-1]['payload']))
    prefix.control();reader.history.verify();returned.receipt()
    return dict(cleanupConsumptionSha256=hashlib.sha256(prefix.raw).hexdigest(),
        sequenceSucceeded=prefix.previous['header']['sequenceSucceeded'],primaryFinalSequence=prefix.previous['header']['finalSequence'],
        consumedActorSequence=consumed,finalActorSequence=len(graph.frames['publisher']),
        actorTypedReturnSha256=digest(returned.previous),actorSourceSealSha256=graph.root['sealSha256'])


class ChatRemoteConsumedSources:
    def __init__(self,prefix,returned,primary_seal,store):
        need(type(prefix) is ChatRemoteCleanupPrefix and prefix.completed and not prefix.failed
            and type(returned) is ChatRemoteActorReturn and returned.complete and not returned.failed
            and type(primary_seal) is ChatCursorSourceSeal and primary_seal.owner is prefix.primary and primary_seal.live()
            and type(store) is PrivateFeatureState and store.read() is None
            and store.path.parent==prefix.store.path.parent and store.path not in
                (prefix.store.path,returned.store.path,primary_seal.store.path))
        self.prefix,self.returned,self.primary_seal,self.store=prefix,returned,primary_seal,store
        self.parent=parent_node(store)
        self.scope=dict(chatRemoteConsumedSourcesVersion=VERSION,runId=prefix.scope['runId'],binding=deepcopy(prefix.scope['binding']),
            peerBinding=deepcopy(prefix.scope['peerBinding']),prefixJournal=prefix.store.path.name,
            actorReturnJournal=returned.store.path.name,primarySealJournal=primary_seal.store.path.name,
            parentHostProcessIdentity=host_identity(),sourceScope='original-consumed-chat-source-graphs')
        self.previous=None;self.root_stamp=None;self.failed=self.started=self.completed=False;self.seal=None;self.result=None
        self.scope_sha=digest(self.scope);self.previous_sha=digest(None);self.result_sha=None
        ChatSourceChunks(store,{}).inventory(0)

    def control(self):
        plain(self.scope);plain(self.previous)
        need(not self.failed and digest(self.scope)==self.scope_sha and digest(self.previous)==self.previous_sha
            and host_identity()==self.scope['parentHostProcessIdentity'] and parent_node(self.store)==self.parent
            and same(self.store.read(),self.previous) and self.prefix.store.path.name==self.scope['prefixJournal']
            and self.returned.store.path.name==self.scope['actorReturnJournal']
            and self.primary_seal.store.path.name==self.scope['primarySealJournal'])
        if self.root_stamp is not None:need(state(self.store)[2]==self.root_stamp)
        ChatSourceChunks(self.store,{}).inventory(0)

    def save(self,phase,**changes):
        self.control();value={**(self.previous or self.scope),'phase':phase,**deepcopy(changes)}
        self.store.write(value,self.previous);observed,_raw,physical=state(self.store);need(same(observed,value))
        self.previous=deepcopy(value);self.previous_sha=digest(value);self.root_stamp=physical;self.control()

    def run(self):
        need(not self.started and not self.failed);self.started=True
        try:
            self.save('joining-return');original=returned_prefix(self.prefix,self.returned)
            self.save('sealing-primary',original=original);self.seal=self.primary_seal.run()
            need(returned_prefix(self.prefix,self.returned)==original);self.primary_seal.receipt(self.seal)
            self.save('complete',original=original,primarySealSha256=digest(self.seal))
            self.result=deepcopy(self.previous);self.result_sha=digest(self.result);result=deepcopy(self.result);self.control()
            self.primary_seal.receipt(self.seal);self.returned.receipt();self.completed=True;return result
        except BaseException:
            self.failed=True;self.primary_seal.failed=True
            raise NativeUIError('Consumed Chat source/return join is unresolved; originals remain') from None

    def receipt(self):
        need(self.completed and not self.failed)
        try:
            plain(self.result);need(digest(self.result)==self.result_sha)
            self.control();need(same(self.previous,self.result));returned_prefix(self.prefix,self.returned)
            self.primary_seal.receipt(self.seal);result=deepcopy(self.result);self.control();self.returned.receipt();return result
        except BaseException:
            self.failed=True;self.primary_seal.failed=True
            raise NativeUIError('Original consumed Chat sources no longer match their historical receipt') from None
