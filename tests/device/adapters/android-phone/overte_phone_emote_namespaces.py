"""One bounded run-wide namespace lease over original primary/actor sources.

Only the enclosing Emote feature owns actions, publication and final retirement.
Freezing a namespace is not a product checkpoint or a resource-cleanup verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import wraps
import hashlib

from adapters.native_feature_observation import exact,integer,need,number
from adapters.emote_rig_measurements import source as source_group
from adapters.normal_feature_state import PrivateFeatureState,context
from feature_journeys.contract import arguments
from overte_phone_emote_sources import PhoneEmoteSources,source_name,MAX_SEGMENTS
from overte_phone_emote_inputs import PhoneEmoteInputs,input_name
from overte_phone_script_history import canonical,pack,unpack,same

VERSION=1
ROLES=('primary','actor')
PROOF={'sourcesSha256','inputsSha256','sourceIdentitySha256','frame','nativeInstance','rigId','historyInstance',
       'callSequence','overrideSequence','lifecycle'}


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def sha(value):return type(value) is str and len(value)==64 and all(ch in '0123456789abcdef' for ch in value)


def bounded(method):
    @wraps(method)
    def operation(self,*args,**kwargs):
        need(self.started is None);self.started=self.source.monotonic()
        try:
            self.bound();self.verify_closed();value=method(self,*args,**kwargs)
            self.verify_closed();self.bound();return value
        finally:self.started=None
    return operation


class PhoneEmoteNamespaces:
    def __init__(self,source):
        need(isinstance(source,PhoneEmoteSources) and source.historical is False)
        source.lock.assert_held();self.source=source;self.run=source.run;self.binding=deepcopy(context(source.binding))
        self.store=PrivateFeatureState(source.store.path.with_name('phone-emote-namespaces.json'))
        self.previous=self.store.read();self.failed=False;self.started=self.clock=None
        self.state=dict(current=0,closed=[],pending=None)
        if self.previous is not None:self.state=self.decode(self.previous)
        self.bound();self.verify_closed();self.bound()

    def bound(self):
        self.source.lock.assert_held()
        need(not self.failed and self.source.guard() is not False and same(self.store.read(),self.previous))
        now=self.source.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<5));self.clock=now

    def call(self,value):
        call=arguments('feature.emotes.act',value)
        need(call['runId']==self.run and call['fixtureUrl']==self.source.phase.fixture_url
            and call['verb'] in ('play','sit'))
        return call

    @staticmethod
    def proof(value):
        exact(value,PROOF);need(all(sha(value[key]) for key in ('sourcesSha256','inputsSha256','sourceIdentitySha256')))
        exact(value['frame'],{'revision','sha256'})
        need(integer(value['frame']['revision'],1,1024) and sha(value['frame']['sha256'])
            and all(type(value[key]) is str and len(value[key])==32 and all(ch in '0123456789abcdef' for ch in value[key])
                for key in ('nativeInstance','historyInstance'))
            and integer(value['rigId'],1) and integer(value['callSequence']) and integer(value['overrideSequence']))
        exact(value['lifecycle'],{'backgrounds','activations','launches'})
        need(all(integer(item,0,1000000) for item in value['lifecycle'].values()) and value['lifecycle']['launches']>=1)

    def decode(self,value):
        exact(value,{'emoteNamespacesVersion','runId','fixtureUrl','artifactRoot','binding','payload'})
        need(type(value['emoteNamespacesVersion']) is int and value['emoteNamespacesVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.source.phase.fixture_url
            and value['artifactRoot']==str(self.source.artifact_root) and same(value['binding'],self.binding))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'current','closed','pending'})
        need(integer(state['current'],0,MAX_SEGMENTS-1) and type(state['closed']) is list
            and len(state['closed'])==state['current'])
        for index,row in enumerate(state['closed']):
            exact(row,{'segment','call','roles'});need(type(row['segment']) is int and row['segment']==index)
            self.call(row['call']);exact(row['roles'],ROLES)
            for role in ROLES:self.proof(row['roles'][role])
            self.same_native(row['roles'])
        pending=state['pending']
        if pending is not None:
            exact(pending,{'call','inputsSha256','roles'});self.call(pending['call'])
            need(state['current']<MAX_SEGMENTS-1 and sha(pending['inputsSha256']))
            exact(pending['roles'],ROLES)
            for role in ROLES:
                if pending['roles'][role] is not None:
                    self.proof(pending['roles'][role]);need(pending['roles'][role]['inputsSha256']==pending['inputsSha256'])
        return deepcopy(state)

    @staticmethod
    def same_native(roles):
        for role in ROLES:need(roles[role] is not None)
        keys=PROOF-{'sourcesSha256','frame'}
        need(same({key:roles['primary'][key] for key in keys},{key:roles['actor'][key] for key in keys}))

    def save(self):
        self.bound()
        value=dict(emoteNamespacesVersion=VERSION,runId=self.run,fixtureUrl=self.source.phase.fixture_url,
            artifactRoot=str(self.source.artifact_root),binding=deepcopy(self.binding),payload=pack([self.state]))
        self.decode(value)
        try:
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:self.failed=True;raise

    def inputs(self):
        path=self.source.store.path.with_name(input_name(self.state['current']))
        value=PrivateFeatureState(path).read();need(value is not None)
        return value

    def active(self,call):
        status=self.source.phase.status();need(status['active'] and status['activations'])
        last=status['activations'][-1]
        need(last['ticket']==call['ticket'] and same(last['stimulus'],dict(verb=call['verb'],inputs=call['inputs'])))
        return status

    def no_scopes(self,role):
        root=self.store.path.parent
        need(not list(root.glob('phone-emote-'+role+'-capture-*.json'))
            and not list(root.glob('phone-emote-'+role+'-observation-*.json')))

    def assert_acquiring(self):
        self.bound();self.verify_closed();need(self.source.segment==self.state['current']
            and (self.state['pending'] is None or self.state['pending']['roles'][self.source.role] is None))

    def verify_closed(self):
        """Closed control headers remain frozen until enclosing retirement."""
        for row in self.state['closed']:
            inputs=PrivateFeatureState(self.store.path.with_name(input_name(row['segment']))).read()
            need(inputs is not None)
            for role in ROLES:
                header=PrivateFeatureState(self.store.path.with_name(source_name(role,row['segment']))).read()
                need(header is not None and digest(header)==row['roles'][role]['sourcesSha256']
                    and digest(inputs)==row['roles'][role]['inputsSha256'])

    def originals(self):
        source=self.source;need(not source.failed and source.state['phase']=='ready' and source.state['pending'] is None)
        header=source.store.read();need(header is not None and same(header,source.previous))
        state,frames=PhoneEmoteSources.archive(header,phase=source.phase,artifact_root=source.artifact_root,
            binding=source.binding,guard=self.bound,monotonic=source.monotonic)
        need(state['phase']=='ready' and state['pending'] is None and frames and same(frames[-1],source.frames[-1]))
        return header,frames

    def current_frame(self,frame,call):
        for key in ('phaseBefore','phaseAfter'):
            row=frame[key]['activations'][-1]
            need(row['ticket']==call['ticket'] and same(row['stimulus'],dict(verb=call['verb'],inputs=call['inputs'])))
        now=self.source.phase.epoch_ms();need(number(now,1,1e15) and -250<=now-frame['hostEpochMs']<=1500)

    @bounded
    def request(self,call):
        """Reserve a switch before an ordinary new play/Sit, never before abort."""
        self.bound();call=deepcopy(self.call(call));source=self.source
        need(source.role=='primary' and source.segment==self.state['current'] and self.state['current']<MAX_SEGMENTS-1)
        self.active(call)
        owner=PhoneEmoteInputs(source);need(owner.previous is not None and owner.history_state['pendingArchive'] is None
            and (owner.state['current'] is None or owner.state['current']['phase']=='acknowledged'))
        actual=digest(self.inputs());need(actual==digest(owner.previous))
        if self.state['pending'] is not None:
            need(same(self.state['pending']['call'],call) and self.state['pending']['inputsSha256']==actual)
            return
        self.no_scopes('primary')
        header,frames=self.originals();self.current_frame(frames[-1],call);self.measured(header,frames,actual)
        self.state['pending']=dict(call=call,inputsSha256=actual,roles={role:None for role in ROLES});self.save()

    @staticmethod
    def measured(header,frames,inputs):
        frame=frames[-1];native=frame['group']['native'];animation=native['animation'];history=animation['history']
        selected,_native,_urls=source_group(frame['group'],native['processId'],frame['epochMs'])
        need(animation['overrideActive'] is False and not any(row['id']=='emote.page' and row['activeName'] for row in frame['ui']['controls']))
        return dict(sourcesSha256=digest(header),inputsSha256=inputs,sourceIdentitySha256=digest(selected),
            frame=dict(revision=len(frames),sha256=digest(frame)),
            nativeInstance=native['instance'],rigId=animation['rigId'],historyInstance=history['instance'],
            callSequence=history['callSequence'],overrideSequence=history['overrideSequence'],lifecycle=deepcopy(native['lifecycle']))

    @bounded
    def acknowledge(self):
        """This role supplies its own fresh inactive originals, not supplied facts."""
        self.bound();source=self.source;pending=self.state['pending']
        need(pending is not None and source.segment==self.state['current'] and not source.failed
            and source.state['phase']=='ready' and source.state['pending'] is None and source.frames)
        self.no_scopes(source.role);self.active(pending['call'])
        header,frames=self.originals();self.current_frame(frames[-1],pending['call'])
        inputs=digest(self.inputs());need(inputs==pending['inputsSha256'])
        proof=self.measured(header,frames,inputs)
        if pending['roles'][source.role] is not None:need(same(pending['roles'][source.role],proof))
        else:pending['roles'][source.role]=proof;self.save()
        self.bound();need(same(source.store.read(),header));return deepcopy(proof)

    @bounded
    def advance(self):
        """Atomic lease transition only after both frozen original journals match."""
        self.bound();need(self.source.role=='primary' and self.state['pending'] is not None)
        pending=self.state['pending'];self.same_native(pending['roles']);self.active(pending['call'])
        need(digest(self.inputs())==pending['inputsSha256'])
        for role in ROLES:
            self.no_scopes(role)
            store=PrivateFeatureState(self.store.path.with_name(source_name(role,self.state['current'])))
            header=store.read();need(header is not None and digest(header)==pending['roles'][role]['sourcesSha256'])
            state,frames=PhoneEmoteSources.archive(header,phase=self.source.phase,artifact_root=self.source.artifact_root,
                binding=self.binding,guard=self.source.guard,monotonic=self.source.monotonic)
            need(state['phase']=='ready' and state['pending'] is None and len(frames)==pending['roles'][role]['frame']['revision']
                and digest(frames[-1])==pending['roles'][role]['frame']['sha256'] and same(store.read(),header))
            need(same(self.measured(header,frames,pending['inputsSha256']),pending['roles'][role]))
            now=self.source.phase.epoch_ms();need(number(now,1,1e15) and -250<=now-frames[-1]['hostEpochMs']<=1500)
        self.state['closed'].append(dict(segment=self.state['current'],call=deepcopy(pending['call']),roles=deepcopy(pending['roles'])))
        self.state['current']+=1;self.state['pending']=None;self.save()
        return self.state['current']
