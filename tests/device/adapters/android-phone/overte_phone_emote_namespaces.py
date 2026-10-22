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
from feature_journeys.phase_fixture import validate as phase_packet
from overte_phone_emote_sources import PhoneEmoteSources,source_name,MAX_SEGMENTS
from overte_phone_emote_inputs import PhoneEmoteInputs,input_name
from overte_phone_script_history import canonical,pack,unpack,same

VERSION=2
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
        self.state=dict(current=0,closed=[],pending=None,cleanup=None)
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
        need(type(value['emoteNamespacesVersion']) is int and value['emoteNamespacesVersion'] in (1,VERSION)
            and value['runId']==self.run and value['fixtureUrl']==self.source.phase.fixture_url
            and value['artifactRoot']==str(self.source.artifact_root) and same(value['binding'],self.binding))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'current','closed','pending'}|({'cleanup'} if value['emoteNamespacesVersion']==VERSION else set()))
        state=deepcopy(state)
        if value['emoteNamespacesVersion']==1:state['cleanup']=None
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
        cleanup=state['cleanup']
        if cleanup is not None:
            exact(cleanup,{'ticket','pending','headers','inputsSha256'})
            need(pending is None and type(cleanup['ticket']) is str and len(cleanup['ticket'])==32
                and all(ch in '0123456789abcdef' for ch in cleanup['ticket']) and sha(cleanup['inputsSha256']))
            exact(cleanup['headers'],ROLES)
            if cleanup['pending'] is not None:
                # Reuse the unchanged v1 handshake validator. An aborted
                # one-role freeze never becomes a completed two-role advance.
                normal=deepcopy(value);copy=deepcopy(state);copy.update(pending=deepcopy(cleanup['pending']),cleanup=None)
                normal['emoteNamespacesVersion']=VERSION;normal['payload']=pack([copy]);self.decode(normal)
                need(cleanup['pending']['inputsSha256']==cleanup['inputsSha256'])
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
        self.bound();self.verify_closed();need(self.source.segment==self.state['current'])
        if self.state['cleanup'] is not None:self.cleanup_status(self.state['cleanup']['ticket'])
        else:need(self.state['pending'] is None or self.state['pending']['roles'][self.source.role] is None)

    def verify_closed(self):
        """Closed control headers remain frozen until enclosing retirement."""
        for row in self.state['closed']:
            inputs=PrivateFeatureState(self.store.path.with_name(input_name(row['segment']))).read()
            need(inputs is not None)
            for role in ROLES:
                header=PrivateFeatureState(self.store.path.with_name(source_name(role,row['segment']))).read()
                need(header is not None and digest(header)==row['roles'][role]['sourcesSha256']
                    and digest(inputs)==row['roles'][role]['inputsSha256'])
        self.verify_cleanup()

    def archive(self,header):
        return PhoneEmoteSources.archive(header,phase=self.source.phase,artifact_root=self.source.artifact_root,
            binding=self.binding,guard=self.bound,monotonic=self.source.monotonic)

    def verify_cleanup(self):
        cleanup=self.state['cleanup']
        if cleanup is None:return
        inputs=PrivateFeatureState(self.store.path.with_name(input_name(self.state['current']))).read()
        need(digest(inputs)==cleanup['inputsSha256'])
        for role in ROLES:
            header=cleanup['headers'][role]
            proof=cleanup['pending']['roles'][role] if cleanup['pending'] is not None else None
            current=PrivateFeatureState(self.store.path.with_name(source_name(role,self.state['current']))).read()
            if header is None:need(proof is None);continue
            need(header.get('role')==role)
            state,frames=self.archive(header)
            if proof is not None:
                need(state['phase']=='ready' and state['pending'] is None and bool(frames)
                    and same(self.measured(header,frames,cleanup['inputsSha256']),proof))
            need(current is not None and current.get('role')==role)
            _state,continued=self.archive(current)
            need(len(continued)>=len(frames) and same(continued[:len(frames)],frames))

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
        need(self.state['cleanup'] is None and source.role=='primary'
            and source.segment==self.state['current'] and self.state['current']<MAX_SEGMENTS-1)
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

    def cleanup_status(self,ticket=None):
        status=self.source.phase.status();need(status['active'] and status['activations'])
        row=status['activations'][-1]
        need(row['stimulus']==dict(verb='cleanup',inputs={}) and (ticket is None or row['ticket']==ticket))
        return row['ticket']

    @bounded
    def begin_cleanup(self):
        """Release only this incomplete freeze under the real cleanup ticket.

        Original frozen headers and the actual partial handshake stay owned;
        current sources may append new cleanup originals without redating them.
        """
        need(self.source.role=='primary' and self.source.segment==self.state['current'])
        ticket=self.cleanup_status()
        if self.state['cleanup'] is not None:
            need(self.state['cleanup']['ticket']==ticket);return
        headers={role:PrivateFeatureState(self.store.path.with_name(source_name(role,self.state['current']))).read() for role in ROLES}
        inputs=PrivateFeatureState(self.store.path.with_name(input_name(self.state['current']))).read()
        pending=self.state['pending']
        if pending is not None:
            need(digest(inputs)==pending['inputsSha256'])
            for role in ROLES:
                if pending['roles'][role] is not None:
                    need(headers[role] is not None and digest(headers[role])==pending['roles'][role]['sourcesSha256'])
        self.state['cleanup']=dict(ticket=ticket,pending=deepcopy(pending),headers=deepcopy(headers),inputsSha256=digest(inputs))
        self.state['pending']=None;self.save();self.verify_cleanup()

    def retirement(self):
        need(self.state['cleanup'] is not None)
        ticket=self.cleanup_status(self.state['cleanup']['ticket']);headers={};roles={}
        inputs=PrivateFeatureState(self.store.path.with_name(input_name(self.state['current']))).read()
        for role in ROLES:
            self.no_scopes(role)
            header=PrivateFeatureState(self.store.path.with_name(source_name(role,self.state['current']))).read()
            need(header is not None and header.get('role')==role);state,frames=self.archive(header)
            need(state['phase']=='ready' and state['pending'] is None and frames)
            frame=frames[-1]
            need(frame['ui']['open'] is False and not frame['ui']['controls'])
            for key in ('phaseBefore','phaseAfter'):
                phase=frame[key]['activations'][-1]
                need(phase['ticket']==ticket and phase['stimulus']==dict(verb='cleanup',inputs={}))
            now=self.source.phase.epoch_ms();need(number(now,1,1e15) and -250<=now-frame['hostEpochMs']<=1500)
            roles[role]=self.measured(header,frames,digest(inputs));headers[role]=header
        self.same_native(roles)
        return dict(emoteNamespaceRetirementVersion=1,header=deepcopy(self.previous),headers=headers,roles=roles)

    def retire(self,retain):
        """Transfer original lease proof before removing only its metadata.

        This is not whole-run resource or file retirement. Source originals and
        input ownership deliberately remain for the enclosing cleanup owner.
        """
        need(callable(retain) and self.source.role=='primary' and self.source.segment==self.state['current'] and self.previous is not None)
        need(self.started is None);self.started=self.source.monotonic()
        try:
            self.bound();self.verify_closed();original=self.retirement()
            need(retain(deepcopy(original)) is not False);self.bound();self.verify_closed()
            need(same(self.retirement(),original));self.bound()
            self.store.discard(self.previous);need(self.store.read() is None);self.previous=None;self.bound()
            return deepcopy(original)
        finally:self.started=None


    def retirement_archive(self,value):
        """Bound historical replay even when called outside a live transfer."""
        outer=self.started is None
        if outer:self.started=self.source.monotonic()
        try:return self._retirement_archive(value)
        finally:
            if outer:self.started=None

    def _retirement_archive(self,value):
        """Verify all original namespace dependencies without live controls.

        Version 2 transfers historical ownership after actual provider closure.
        It supplies no fresh native/resource or whole-feature cleanup verdict.
        """
        self.bound();exact(value,{'emoteNamespaceRetirementVersion','header','sources','inputs','roles','cleanup'})
        need(type(value['emoteNamespaceRetirementVersion']) is int and value['emoteNamespaceRetirementVersion']==2)
        state=self.decode(value['header']);need(state['cleanup'] is not None and state['pending'] is None)
        sources,inputs=value['sources'],value['inputs'];count=state['current']+1
        need(type(sources) is list and type(inputs) is list and len(sources)==len(inputs)==count)
        cleanup=value['cleanup'];phase_packet(cleanup,run=self.run,area='emotes',request=cleanup.get('requestId'),epoch=cleanup.get('capturedEpochMs'))
        need(not cleanup['active'] and cleanup['activations'] and cleanup['activations'][-1]['ticket']==state['cleanup']['ticket']
            and cleanup['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        measured={};decoded=[]
        for index,headers in enumerate(sources):
            exact(headers,ROLES);rows={}
            for role in ROLES:
                header=headers[role];need(type(header) is dict and header.get('role')==role)
                original,frames=PhoneEmoteSources.archive(header,phase=self.source.phase,artifact_root=self.source.artifact_root,
                    binding=self.binding,guard=self.bound,monotonic=self.source.monotonic,
                    predecessor=sources[index-1][role] if index else None)
                need(original['phase']=='ready' and original['pending'] is None and frames);rows[role]=frames
                actual=self.measured(header,frames,digest(inputs[index]));self.proof(actual)
                if index<state['current']:need(same(actual,state['closed'][index]['roles'][role]))
                else:
                    need(frame_closed(frames[-1],state['cleanup']['ticket']))
                    phase_packet(cleanup,run=self.run,area='emotes',request=cleanup['requestId'],epoch=cleanup['capturedEpochMs'],
                        previous=frames[-1]['phaseAfter'])
                    need(same(cleanup['activations'],frames[-1]['phaseAfter']['activations']))
                    measured[role]=actual
            if inputs[index] is not None:
                PhoneEmoteInputs.archive(inputs[index],headers['primary'],phase=self.source.phase,artifact_root=self.source.artifact_root,
                    binding=self.binding,guard=self.bound,monotonic=self.source.monotonic)
            elif index<state['current']:need(False)
            decoded.append(rows)
        saved=state['cleanup'];need(digest(inputs[-1])==saved['inputsSha256'])
        for role in ROLES:
            header=saved['headers'][role];proof=saved['pending']['roles'][role] if saved['pending'] is not None else None
            if header is None:need(proof is None);continue
            need(header.get('role')==role)
            _original,frames=self.archive(header);current=decoded[-1][role]
            need(len(current)>=len(frames) and same(current[:len(frames)],frames))
            if proof is not None:need(same(self.measured(header,frames,saved['inputsSha256']),proof))
        self.same_native(measured);need(same(measured,value['roles']));self.bound();return deepcopy(value)

    def retire_closed(self,retain,*,retained=None):
        """Retain every original control before retiring only the lease."""
        need(callable(retain) and self.source.role=='primary' and self.started is None);self.started=self.source.monotonic()
        try:
            self.bound()
            if retained is None:
                self.verify_closed();need(self.previous is not None and self.source.segment==self.state['current']
                    and self.state['cleanup'] is not None)
                for role in ROLES:self.no_scopes(role)
                sources=[];inputs=[]
                for index in range(self.state['current']+1):
                    sources.append({role:PrivateFeatureState(self.store.path.with_name(source_name(role,index))).read() for role in ROLES})
                    inputs.append(PrivateFeatureState(self.store.path.with_name(input_name(index))).read())
                roles={}
                for role in ROLES:
                    _state,frames=self.archive(sources[-1][role]);need(frames)
                    roles[role]=self.measured(sources[-1][role],frames,digest(inputs[-1]))
                value=dict(emoteNamespaceRetirementVersion=2,header=deepcopy(self.previous),sources=sources,inputs=inputs,
                    roles=roles,cleanup=self.source.phase.status())
            else:
                value=deepcopy(retained);need(self.previous is None or same(self.previous,value['header']))
            value=self.retirement_archive(value);self.bound()
            current=self.source.phase.status(value['cleanup']);need(not current['active']);self.bound()
            need(retain(deepcopy(value)) is not False);self.bound();self.retirement_archive(value)
            # Source/input controls still present must be exactly the originals.
            # Missing dependencies are allowed only on a retained historical
            # retry after the enclosing owner started its own retirement.
            for index,headers in enumerate(value['sources']):
                for role in ROLES:
                    actual=PrivateFeatureState(self.store.path.with_name(source_name(role,index))).read()
                    need(same(actual,headers[role]) or retained is not None and actual is None)
                actual=PrivateFeatureState(self.store.path.with_name(input_name(index))).read()
                need(same(actual,value['inputs'][index]) or retained is not None and actual is None)
            for role in ROLES:self.no_scopes(role)
            self.bound();self.source.phase.status(value['cleanup']);self.bound()
            if self.previous is not None:
                self.store.discard(value['header']);need(self.store.read() is None);self.previous=None
            self.bound();return deepcopy(value)
        finally:self.started=None


def frame_closed(frame,ticket):
    """Historical native inactivity and UI absence; no freshness is inferred."""
    return frame['ui']['open'] is False and not frame['ui']['controls'] and all(
        frame[key]['activations'][-1]['ticket']==ticket
        and frame[key]['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}) for key in ('phaseBefore','phaseAfter'))
