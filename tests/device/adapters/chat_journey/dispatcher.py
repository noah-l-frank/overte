"""Once-only fixed Chat inputs; original child journals are never ACK facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math

from adapters.chat_journey.background import ChatBackground
from adapters.chat_journey.cache_lifetime import ChatCacheLifetime
from adapters.chat_journey.flow_inputs import ChatFlowInputs,recipe,fresh_roles
from adapters.chat_journey.mixer import ChatMixerOwner
from adapters.chat_journey.no_replay import ChatNoReplay
from adapters.chat_journey.normal_input import ChatNormalInput,VERBS
from adapters.chat_journey.peer_distant import ChatPeerDistant
from adapters.chat_journey.peer_send import ChatPeerSend
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.native_feature_observation import exact,need,integer
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import same,unpack

VERSION=1
KINDS={'normal':ChatNormalInput,'peer':ChatPeerSend,'distant':ChatPeerDistant,
    'background':ChatBackground,'mixer':ChatMixerOwner,'no-replay':ChatNoReplay}


def route(verb):
    if verb=='baseline':return 'baseline'
    if verb in VERBS:return 'normal'
    return {'peer-send':'peer','peer-send-distant':'distant','background-resume':'background',
        'network-remove-mixer':'mixer','network-restore-mixer':'mixer','await-no-replay':'no-replay'}[verb]


class ChatDispatcher:
    """One original host session, with durable intent before every input.

    Reconstruction audits the retained immutable snapshots only. It cannot
    resume inputs: interrupted lazy owners do not yet all provide a passive
    reconstruction contract. This boundary is explicit and never a replay.
    """
    def __init__(self,flow,cache_factory,factories,store):
        need(type(flow) is ChatFlowInputs and callable(cache_factory) and type(factories) is dict
            and set(factories)==set(KINDS) and all(callable(value) for value in factories.values())
            and isinstance(store,PrivateFeatureState) and store.path.parent==flow.store.path.parent
            and store.path not in {flow.store.path,*[role.store.path for role in flow.roles+flow.initial_roles]})
        self.flow,self.cache_factory,self.factories,self.store=flow,cache_factory,factories,store
        self.children={};self.caches=None;self.poisoned=False
        self.scope=dict(chatDispatcherVersion=VERSION,runId=flow.source.run,binding=deepcopy(flow.roles[0].binding),
            peerBinding=deepcopy(flow.roles[0].peer_binding),flowJournal=flow.store.path.name)
        self.previous=store.read();self.cold=self.previous is not None
        self.base={**self.scope,'phase':'ready','steps':[],'chunks':[]}
        self.chunks=ChatSourceChunks(store,self.scope)
        if self.cold:
            exact(self.previous,set(self.base));need(all(same(self.previous[key],value) for key,value in self.scope.items()))
            self.base=deepcopy(self.previous)
        self.proofs=self.chunks.load(self.base['chunks']);self.audit()

    def audit(self):
        need(self.base['phase'] in ('ready','reading') and type(self.base['steps']) is list and len(self.base['steps'])<=26
            and len(self.proofs)==len(self.base['chunks'])==len(self.chunks.identities))
        used=[]
        for index,row in enumerate(self.base['steps']):
            exact(row,{'ticket','verb','inputs','route','phase','proofs'})
            need(same(dict(verb=row['verb'],inputs=row['inputs']),recipe(self.scope['runId'])[index])
                and row['route']==route(row['verb']) and row['phase'] in ('issued','observed','completed')
                and (index==len(self.base['steps'])-1 or row['phase']=='completed')
                and type(row['proofs']) is list)
            if index<len(self.flow.rows):
                original=self.flow.rows[index]
                need(row['ticket']==original['ticket'] and row['verb']==original['verb'] and same(row['inputs'],original['inputs']))
                if row['phase']=='completed':need(original['phase']=='completed')
            else:need(index==len(self.flow.rows) and row['phase']=='issued')
            for proof_index in row['proofs']:
                need(integer(proof_index,0,len(self.proofs)-1) and proof_index not in used);used.append(proof_index)
                proof=self.proofs[proof_index];exact(proof,{'stepIndex','kind','journal','journalSha256','rowIndex','record'})
                need(proof['stepIndex']==index and type(proof['journal']) is str
                    and proof['journal'] not in ('','.','..') and '/' not in proof['journal'] and '\\' not in proof['journal'])
                record=proof['record'];need(type(record) is dict and record.get('runId')==self.scope['runId'])
                expected=self.scope['peerBinding'] if proof['kind']=='cache-peer' else self.scope['binding']
                need(same(record.get('binding'),expected))
                if proof['kind']=='normal':
                    need(proof['rowIndex']==sum(value['route']=='normal' for value in self.base['steps'][:index]))
                    attempts=unpack(record['attempts']);need(len(attempts)==1 and attempts[0]['ticket']==row['ticket']
                        and attempts[0]['phase']=='observed' and attempts[0]['verb']==row['verb'] and same(attempts[0]['inputs'],row['inputs']))
                    need(type(proof['journalSha256']) is str and len(proof['journalSha256'])==64)
                else:need(proof['rowIndex'] is None)
                need(proof['journalSha256']==digest(record))
            if row['phase'] in ('observed','completed'):
                need([self.proofs[value]['kind'] for value in row['proofs']]
                    ==([] if index==0 else ['cache-primary','cache-peer','normal'] if index==1 else [row['route']]))
        need(used==list(range(len(self.proofs))) and len(self.flow.rows)<=len(self.base['steps']))

    def save(self):
        self.flow.roles[0].locks[0].assert_held();need(same(self.store.read(),self.previous))
        self.audit();value=deepcopy(self.base);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def child(self,kind):
        if kind not in self.children:
            owner=self.factories[kind]();need(type(owner) is KINDS[kind] and owner.store.read() is None)
            roles=(owner.primary,owner.actor) if kind=='no-replay' else owner.sender.roles if kind=='distant' else owner.roles
            need(all(a is b for a,b in zip(roles,self.flow.roles)))
            if kind=='distant':need(owner.sender is self.child('peer'))
            paths={self.store.path,self.flow.store.path,*[role.store.path for role in self.flow.roles+self.flow.initial_roles],
                *[child.store.path for child in self.children.values()]}
            need(owner.store.path.parent==self.store.path.parent and owner.store.path not in paths)
            self.children[kind]=owner
        return self.children[kind]

    def snapshot(self,kind,owner):
        record=owner.store.read();need(record is not None and same(record,owner.previous))
        row=self.base['steps'][-1];index=len(self.base['steps'])-1
        if kind.startswith('cache-'):
            owner.validate();need(owner.base['phase']=='active')
        elif kind=='normal':
            attempt=owner.base['attempts'][-1]
            need(attempt['phase']=='observed' and attempt['ticket']==row['ticket']
                and same(dict(verb=attempt['verb'],inputs=attempt['inputs']),dict(verb=row['verb'],inputs=row['inputs'])))
            owner.check_inputs(attempt);need(owner.reached(attempt,owner.sources(attempt['before']),owner.sources(attempt['after'])))
            owner.check_quiet(attempt)
        elif kind=='peer':
            attempt=record['attempts'][-1]
            from feature_journeys.fixtures import context
            need(attempt['phase']=='received' and attempt['channel']==row['inputs']['channel']
                and context(self.scope['runId'])[attempt['textKey']]==row['inputs']['text'])
            before,after=owner.sources(attempt['before']),owner.sources(attempt['after'])
            need(all(owner.delivery(a,b,attempt['channel'],attempt['textKey']) for a,b in zip(before,after)))
            original=owner.input.previous['intents'][attempt['inputIndex']]
            need(original['phase']=='consumed' and original['command']['textKey']==attempt['textKey']
                and original['command']['channel']==attempt['channel'])
        elif kind=='background':need(owner.state['phase']=='observed');owner.closed_history()
        elif kind=='mixer':need(record['phase']==('offline' if row['verb']=='network-remove-mixer' else 'online'))
        else:need(record['phase']=='complete' and (kind!='no-replay' or record['ticket']==row['ticket']))
        self.base['phase']='reading';self.save()
        # Normal v2 retains its exact current attempt and immutable completed
        # chunk manifest. Repeatedly nesting the growing v1 packed history
        # exceeded the existing 48 KiB bound at the final quiet Close.
        selected=deepcopy(record);row_index=None
        if kind=='normal':
            row_index=len(owner.base['attempts'])-1
        proof=dict(stepIndex=index,kind=kind,journal=owner.store.path.name,journalSha256=digest(record),rowIndex=row_index,record=selected)
        manifest=self.chunks.append(proof,self.base['chunks']);self.proofs.append(proof)
        row['proofs'].append(len(self.proofs)-1);self.base['chunks']=manifest;self.base['phase']='ready';self.save()

    def activate(self):
        need(self.caches is None and len(self.flow.rows)==2 and self.flow.rows[0]['phase']=='completed')
        caches=self.cache_factory();need(type(caches) is tuple and len(caches)==2 and all(type(owner) is ChatCacheLifetime for owner in caches)
            and caches[0] is not caches[1] and caches[0].store.path!=caches[1].store.path)
        for index,owner in enumerate(caches):
            key='primary' if index==0 else 'peer';frame=self.flow.initial_roles[0].frames[self.flow.rows[0]['references'][0]['index']][key]
            need(owner.lock is self.flow.roles[0].locks[index] and owner.capture.run==self.scope['runId']
                and same(owner.scope['binding'],self.scope['binding' if index==0 else 'peerBinding'])
                and owner.scope['sourceInstance']==frame['instance'] and owner.scope['selfSha256']==frame['source']['selfSha256']
                and owner.reader.pid==frame['processId'] and owner.base['phase']=='ready' and owner.previous is None
                and owner.store.path.parent==owner.lock.path.parent and owner.store.path not in
                {self.store.path,self.flow.store.path,*[role.store.path for role in self.flow.roles+self.flow.initial_roles]})
        self.caches=caches
        for index,owner in enumerate(caches):owner.activate();self.snapshot('cache-primary' if index==0 else 'cache-peer',owner)

    def dispatch(self,row,barrier):
        kind=row['route'];inputs=row['inputs'];verb=row['verb']
        if kind=='baseline':return
        if len(self.base['steps'])==2:self.activate()
        owner=self.child(kind)
        if kind=='normal':owner.perform(row['ticket'],verb,inputs,barrier)
        elif kind=='peer':
            from feature_journeys.fixtures import context
            keys=[key for key in ('reply','hidden') if context(self.scope['runId'])[key]==inputs['text']];need(len(keys)==1)
            owner.send(inputs['channel'],keys[0],barrier)
        elif kind in ('distant','background'):owner.run(barrier)
        elif kind=='mixer':
            if verb=='network-remove-mixer':owner.remove(barrier)
            else:owner.restore(barrier)
        else:owner.wait(row['ticket'],barrier)
        self.snapshot(kind,owner)

    def step(self):
        try:
            need(not self.cold and not self.poisoned and self.base['phase']=='ready'
                and (not self.base['steps'] or self.base['steps'][-1]['phase']=='completed')
                and len(self.base['steps'])==len(self.flow.rows)<26)
            with self.flow.session():
                self.chunks.verify();active=self.flow.source.read();index=len(self.base['steps']);fixed=recipe(self.scope['runId'])[index]
                need(same(dict(verb=active['verb'],inputs=active['inputs']),fixed))
                row=dict(ticket=active['ticket'],**deepcopy(fixed),route=route(fixed['verb']),phase='issued',proofs=[])
                self.base['steps'].append(row);self.save();self.flow.begin(active)
                self.dispatch(row,math.ceil(active['status']['capturedEpochMs']))
                row['phase']='observed';self.save()
                started=self.flow.now();observed=self.flow.finish();row['phase']='completed';self.save()
                result=deepcopy(observed);self.chunks.verify()
                fresh_roles(self.flow.initial_roles if index==0 else self.flow.roles,started,self.flow.now)
                return result
        except Exception:
            self.poisoned=True
            raise NativeUIError('Chat dispatch is unresolved; original intent and sources remain, without replay') from None

    def history(self):
        """Historical originals only. No measured state or completion claim."""
        self.chunks.verify();need(same(self.store.read(),self.previous));self.audit()
        return deepcopy(self.proofs)
