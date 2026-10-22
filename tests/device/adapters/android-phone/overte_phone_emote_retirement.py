"""Bounded whole-run Emote ownership transfer over original component evidence.

Archived contexts are readonly. Native facts always come from the existing real
readers; retained controls authorize recovery, never substitute measured facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re

from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.owned_world_render import OwnedWorldRenderCapture
from overte_phone_emote_actor import PhoneEmoteActor,image_policy
from overte_phone_emote_background import PhoneEmoteBackground
from overte_phone_emote_cleanup import PhoneEmoteCleanup
from overte_phone_emote_effects import PhoneEmoteEffects
from overte_phone_emote_failures import PhoneEmoteFailures,FailureOriginals
from overte_phone_emote_inputs import PhoneEmoteInputs,input_name
from overte_phone_emote_lifetime import PhoneEmoteLifetime
from overte_phone_emote_namespaces import PhoneEmoteNamespaces
from overte_phone_emote_originals import PhoneEmoteOriginals
from overte_phone_emote_role import PhoneEmoteRole,RoleOriginals
from overte_phone_emote_run import PhoneEmoteRun
from overte_phone_emote_sources import PhoneEmoteSources,source_name,MAX_SEGMENTS
from overte_phone_emote_scene import PhoneEmoteScene
from overte_phone_emote_view import PhoneEmoteView
from overte_phone_script_history import pack,unpack,same,canonical

VERSION=3
LIMIT=128


def forbidden(*_args,**_kwargs):need(False)


class RetirementOriginals(PhoneEmoteOriginals):
    KINDS=frozenset({'retirement'})


class PhoneEmoteRetirement:
    def __init__(self,run,policy):
        need(isinstance(run,PhoneEmoteRun));run.lock.assert_held()
        self.run,self.policy=run,image_policy(policy)
        self.store=PrivateFeatureState(run.store.path.with_name('phone-emote-retirement.json'))
        self.previous=self.store.read();self.failed=False;self.finished=False;self.started=self.clock=None
        if self.previous is None:
            need(run.state is not None and run.previous is not None)
            self.owner=deepcopy(run.previous)
        else:
            need(type(self.previous) is dict);self.owner=deepcopy(self.previous.get('runHeader'))
        self.owner_state=run.decode(self.owner);self.binding=deepcopy(context(self.owner_state['binding']))
        need(self.owner_state['phase']=='resources-restored')
        _ui,_native,binding,self.guard,_installed=run.adapter.normal_feature_runtime(run.selector,read_only=True)
        need(same(context(binding),self.binding))
        self.state=dict(phase='collecting',items=[],pending=None,attempts=0,verification=None,
            mode='unissued' if self.owner_state['setup']==dict(view='unissued',scene='unissued') and self.owner_state['call'] is None else 'setup' if self.owner_state.get('prepared') is False and self.owner_state['call'] is None else 'observed')
        self.originals=RetirementOriginals(run.root,self.binding,run.run,'primary',self.bound,self.storage_intent,
            kind='retirement',monotonic=run.monotonic)
        self.names=self.control_names();self.sources={};self.roles={}
        if self.previous is not None:self.state=self.decode(self.previous)
        self.bound()

    @staticmethod
    def control_names():
        names=['phone-emote-'+kind+'.json' for kind in ('run','view','scene','background','cleanup-inputs','namespaces',
            'primary-role','actor-role','primary-lifetime','actor-lifetime','actor-lifecycle','failures','primary-admission','actor-admission')]
        for segment in range(MAX_SEGMENTS):
            names.append(input_name(segment))
            names.extend(source_name(role,segment) for role in ('primary','actor'))
        need(len(names)==len(set(names)));return sorted(names)

    def valid_key(self,key):
        return type(key) is str and (key in ('scene','view','namespace')
            or key.startswith('control/') and key[8:] in self.names
            or re.fullmatch(r'(resources|unissued)/([1-9]|1[0-5])',key) is not None
            or re.fullmatch(r'work/([1-9]|1[0-5])/(source|work|complete)',key) is not None)

    def file(self,name):
        need(name in self.names);return PrivateFeatureState(self.store.path.with_name(name))

    def bound(self):
        self.run.lock.assert_held();need(not self.failed and not self.finished and not self.run.failed and self.guard() is not False
            and same(self.store.read(),self.previous))
        actual=self.run.store.read()
        need(same(actual,self.owner) or self.state['phase']=='retiring' and actual is None)
        now=self.run.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<60));self.clock=now

    def decode(self,value):
        exact(value,{'emoteRetirementVersion','runId','fixtureUrl','artifactRoot','binding','imagePolicy','runHeader','payload'})
        need(type(value['emoteRetirementVersion']) is int and value['emoteRetirementVersion'] in (1,2,VERSION)
            and value['runId']==self.run.run and value['fixtureUrl']==self.run.fixture_url
            and value['artifactRoot']==str(self.run.root) and same(value['binding'],self.binding)
            and same(value['imagePolicy'],self.policy) and same(value['runHeader'],self.owner))
        records=unpack(value['payload']);need(len(records)==1);state=records[0]
        exact(state,{'phase','items','pending','attempts','verification'}|({'mode'} if value['emoteRetirementVersion']>=2 else set()))
        state=deepcopy(state)
        if value['emoteRetirementVersion']==1:state['mode']='observed'
        need(state['mode'] in ('observed','unissued','setup'))
        if state['mode']=='setup':need(value['emoteRetirementVersion']>=3 and self.owner_state.get('prepared') is False
            and self.owner_state['call'] is None and self.owner_state['segment']==0
            and self.owner_state['baseline'] is not None and self.owner_state['admissionSha256'] is not None
            and 'issued' in self.owner_state['setup'].values()
            and all(flag in ('issued','unissued') for flag in self.owner_state['setup'].values()))
        if state['mode']=='unissued':need(self.owner_state['setup']==dict(view='unissued',scene='unissued')
            and self.owner_state['call'] is None and self.owner_state['segment']==0)
        need(state['phase'] in ('collecting','retiring') and type(state['items']) is list and len(state['items'])<=LIMIT
            and integer(state['attempts'],0,15));keys=set()
        for index,item in enumerate(state['items'],1):
            exact(item,{'key','original'});need(self.valid_key(item['key']) and item['key'] not in keys)
            keys.add(item['key']);original=self.originals.expand(item['original']);need(original['index']==index)
        pending=state['pending']
        if pending is not None:
            exact(pending,{'key','value','original'});need(len(keys)<LIMIT and self.valid_key(pending['key']) and pending['key'] not in keys and type(pending['value']) is dict)
            if pending['original'] is not None:
                self.originals.original(pending['original']);need(pending['original']['index']==len(keys)+1)
        need(state['verification'] is None or type(state['verification']) is str and state['verification'] in keys)
        if state['verification'] is not None:
            pattern=r'work/([1-9]|1[0-5])/complete' if state['mode']!='unissued' else r'unissued/([1-9]|1[0-5])'
            need(re.fullmatch(pattern,state['verification']) is not None)
        if state['phase']=='retiring':
            need(state['verification'] is not None and all('control/'+name in keys for name in self.names)
                and (state['mode']=='unissued' or all(key in keys for key in ('view','namespace'))
                    and (state['mode']=='setup' and self.owner_state['setup']['scene']=='unissued' or 'scene' in keys))
                and (pending is None or pending['key'].startswith(('work/','resources/','unissued/'))))
        return deepcopy(state)

    def save(self):
        self.bound()
        value=dict(emoteRetirementVersion=VERSION,runId=self.run.run,fixtureUrl=self.run.fixture_url,artifactRoot=str(self.run.root),
            binding=deepcopy(self.binding),imagePolicy=deepcopy(self.policy),runHeader=deepcopy(self.owner),payload=pack([self.state]))
        self.decode(value)
        try:
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:self.failed=True;raise

    def storage_intent(self,kind,value):
        need(kind=='original' and self.state['pending'] is not None);self.originals.original(value)
        pending=self.state['pending'];old=pending['original'];need(value['index']==len(self.state['items'])+1)
        if old is None:need(value['phase']=='planned')
        else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
            and (old['phase']=='planned' or same(old['file'],value['file'])))
        pending['original']=deepcopy(value);self.save()

    def get(self,key):
        self.bound();items=[item for item in self.state['items'] if item['key']==key];need(len(items)<=1)
        return None if not items else self.originals.read(self.originals.expand(items[0]['original']))

    def retain(self,key,value):
        self.bound();need(self.valid_key(key) and type(value) is dict)
        existing=self.get(key)
        if existing is not None:need(same(existing,value));return
        pending=self.state['pending']
        if pending is None:
            need(len(self.state['items'])<LIMIT);self.state['pending']=dict(key=key,value=deepcopy(value),original=None);self.save()
        else:need(pending['key']==key and same(pending['value'],value))
        pending=self.state['pending'];index=len(self.state['items'])+1
        reference=(self.originals.write(index,value) if pending['original'] is None else
            self.originals.resume_write(index,value,pending['original']))
        self.state['items'].append(dict(key=key,original=reference));self.state['pending']=None;self.save()

    def original(self,name):
        value=self.get('control/'+name)
        if value is None:
            need(self.state['phase']=='collecting');return self.file(name).read()
        exact(value,{'name','value'});need(value['name']==name);return deepcopy(value['value'])

    def witness(self,name):
        original=self.original(name);actual=self.file(name).read()
        if same(actual,original):return
        proof_key={'phone-emote-view.json':'view','phone-emote-scene.json':'scene','phone-emote-namespaces.json':'namespace'}.get(name)
        proof=self.get(proof_key) if proof_key else None
        need(actual is None and (self.state['phase']=='retiring' or proof is not None and same(proof['header'],original)))

    def check_controls(self):
        self.bound();seen={path.name for path in self.store.path.parent.glob('phone-emote-*.json')}
        need(seen<=set(self.names)|{self.store.path.name})
        for name in self.names:self.witness(name)
        self.bound()

    def context_bound(self,scope,limit):
        def bound():
            self.bound();now=self.run.monotonic();old=getattr(scope,'clock',None);started=getattr(scope,'started',None)
            need(number(now,0,1e15) and (old is None or now>=old) and (started is None or now-started<limit));scope.clock=now
        return bound

    def source(self,role='primary',segment=None):
        segment=self.owner_state['segment'] if segment is None else segment
        need(role in ('primary','actor') and integer(segment,0,self.owner_state['segment']))
        key=(role,segment);name=source_name(role,segment);header=self.original(name)
        need(header is not None and header.get('role')==role or self.state['mode']=='unissued' and segment==0 and role=='primary' and header is None)
        self.witness(name)
        if key in self.sources:need(same(self.sources[key].previous,header));return self.sources[key]
        source=object.__new__(PhoneEmoteSources)
        source.adapter,source.selector,source.phase,source.lock=self.run.adapter,self.run.selector,self.run.phase,self.run.lock
        source.run,source.role,source.segment=self.run.run,role,segment
        source.monotonic,source.binding,source.pid=self.run.monotonic,deepcopy(self.binding),int(self.binding['processIdentity'].split(':')[0])
        source.artifact_root,source.admission=self.run.root,deepcopy(self.run.policy)
        source.store,source.previous,source.historical,source.failed=self.file(name),deepcopy(header),False,False
        source.guard=self.bound;source.retirement_read_only=True
        source.originals=PhoneEmoteOriginals(self.run.root,self.binding,self.run.run,role,self.bound,forbidden,monotonic=self.run.monotonic)
        if header is None:source.state,source.frames=dict(phase='ready',revision=0,manifests=[],pending=None),[]
        else:
            source.state,source.frames=PhoneEmoteSources.archive(header,phase=self.run.phase,artifact_root=self.run.root,binding=self.binding,
                guard=self.bound,monotonic=self.run.monotonic)
        need(source.state['phase']=='ready' and source.state['pending'] is None
            and (source.frames or self.state['mode']=='unissued')
            and (header is None or same(header.get('admissionPolicy'),self.run.policy)))
        source.predecessor=source.prior_store=source.prior_header=None
        if segment:
            prior_name=source_name(role,segment-1);prior=self.source(role,segment-1)
            source.predecessor=deepcopy(prior.frames[-1]);source.prior_store=self.file(prior_name);source.prior_header=deepcopy(prior.previous)
            source.validate_frame(source.frames[0],source.predecessor)
            source.segment_start(source.frames[0]['group']['native'])
        source.configuration_bound=lambda:self.witness(name)
        def predecessor_bound():
            self.bound()
            if segment:
                self.witness(source_name(role,segment-1))
                PhoneEmoteSources.archive(source.prior_header,phase=self.run.phase,artifact_root=self.run.root,binding=self.binding,
                    guard=self.bound,monotonic=self.run.monotonic)
        source.predecessor_bound=predecessor_bound
        for method in ('read','save','recover_complete','transfer_failed','storage_intent'):setattr(source,method,forbidden)
        self.sources[key]=source;return source

    def inputs(self,source):
        owner=object.__new__(PhoneEmoteInputs);owner.source=source
        owner.adapter,owner.selector,owner.lock=source.adapter,source.selector,source.lock
        owner.run,owner.fixture_url,owner.binding=source.run,source.phase.fixture_url,source.binding
        owner.store=self.file(input_name(source.segment));owner.previous=self.original(owner.store.path.name)
        owner.started=owner.clock=None;owner.failed=False
        owner.history_store=PhoneEmoteOriginals(self.run.root,self.binding,self.run.run,'primary',self.bound,forbidden,
            kind='inputs',monotonic=self.run.monotonic)
        if owner.previous is None:owner.state,owner.history_state=dict(history=[],current=None),dict(count=0,manifests=[],pendingArchive=None)
        else:owner.state,owner.history_state=owner.decode(owner.previous)
        need(owner.history_state['pendingArchive'] is None)
        owner.bound=self.context_bound(owner,45)
        for method in ('act','save','persist','archive_current','archive_intent'):setattr(owner,method,forbidden)
        return owner

    def shadow_run(self):
        view=object.__new__(PhoneEmoteRun);view.__dict__=self.run.__dict__.copy()
        view.previous,view.state=deepcopy(self.owner),deepcopy(self.owner_state)
        view.source=lambda role='primary',segment=None:self.source(role,segment)
        for method in ('prepare','act','save','load','cleanup_inputs','cleanup_resources','cleanup_quiet'):setattr(view,method,forbidden)
        return view

    def role(self,role,policy=None):
        need(policy is None or same(policy,self.policy))
        if role in self.roles:
            value=self.roles[role];need(same(value.previous,self.original('phone-emote-'+role+'-role.json')));return value
        value=object.__new__(PhoneEmoteRole);value.run,value.role,value.policy=self.shadow_run(),role,deepcopy(self.policy)
        value.source=self.source(role);value.inputs=self.inputs(value.source if role=='primary' else self.source())
        value.effects=PhoneEmoteEffects(value.inputs,current_source=value.source)
        value.binding=deepcopy(self.binding);value.started=value.clock=None;value.failed=False
        name='phone-emote-'+role+'-role.json';value.store=self.file(name);value.previous=self.original(name);need(value.previous is not None)
        value.bound=self.context_bound(value,20)
        value.originals=RoleOriginals(self.run.root,self.binding,self.run.run,role,value.bound,forbidden,
            kind='role-observations',monotonic=self.run.monotonic)
        value.state=value.decode(value.previous);need(value.state['phase']=='ready' and value.state['pending'] is None)
        for method in ('read','save','recover','commit','sync_segment','transfer_phase','transfer_failed','publication'):setattr(value,method,forbidden)
        self.roles[role]=value;return value

    def lifetime(self,source):
        life=object.__new__(PhoneEmoteLifetime);life.source=source;name='phone-emote-'+source.role+'-lifetime.json'
        life.store=self.file(name);life.previous=self.original(name);need(life.previous is not None)
        life.failed=False;life.started=life.clock=None
        life.originals=PhoneEmoteOriginals(self.run.root,self.binding,self.run.run,source.role,self.bound,forbidden,monotonic=self.run.monotonic)
        life.local_bound=self.context_bound(life,30);life.state=life.decode(life.previous)
        need(life.state['phase']=='complete')
        for method in ('read','save','wait','retire','transfer_failed'):setattr(life,method,forbidden)
        return life

    def namespace(self):
        value=object.__new__(PhoneEmoteNamespaces);value.source=self.source();value.run=self.run.run;value.binding=deepcopy(self.binding)
        value.store=self.file('phone-emote-namespaces.json');header=self.original(value.store.path.name);value.previous=value.store.read()
        need(value.previous is None or same(value.previous,header))
        value.failed=False;value.started=value.clock=None;value.bound=self.context_bound(value,5)
        value.state=value.decode(header);return value

    def actor(self):
        actor=object.__new__(PhoneEmoteActor);actor.run,actor.policy,actor.client=self.shadow_run(),deepcopy(self.policy),self.run.phase.client
        actor.store=self.file('phone-emote-actor-lifecycle.json');actor.previous=self.original(actor.store.path.name);need(actor.previous is not None)
        actor.failed=False;actor.state=actor.decode(actor.previous)
        if self.state['mode'] in ('unissued','setup'):
            need(actor.state['phase']=='unadmitted' and actor.state['pending'] is actor.state['last'] is actor.state['quiet'] is None
                and not actor.state['dropped']);return actor
        need(actor.state['phase']=='retired' and actor.state['pending'] is None)
        sample=actor.state['last']['sample'];role=self.role('actor');row=role.stored(sample['actorSequence'])
        from feature_journeys.witness import projection
        need(same(sample,dict(ticket=row['ticket'],actor='owned-observer',actorSequence=row['sequence'],
            capturedEpochMs=row['public']['capturedEpochMs'],facts=projection('emotes',row['public']['state'])))
            and sample['ticket']==self.owner_state['cleanupTicket'] and row['public']['resources']==[]
            and row['public']['state']['animation']=='idle' and not row['public']['state']['override'] and not row['public']['state']['panel'])
        PhoneEmoteLifetime.retirement_archive(actor.state['quiet'],role.source)
        for dropped in actor.state['dropped']:need(role.stored(dropped['sequence'])['ticket']==dropped['ticket'])
        return actor

    def phase(self):
        actor=self.actor();status=self.run.phase.status(actor.state['providerRetirement'])
        need(not status['active'] and status['activations'][-1]['ticket']==self.owner_state['cleanupTicket'])
        return status

    def resources_absent(self):
        self.bound()
        for role in ('primary','actor'):
            need(not list(self.store.path.parent.glob('phone-emote-'+role+'-capture-*.json'))
                and not list(self.store.path.parent.glob('phone-emote-'+role+'-observation-*.json')))
            owned=self.run.adapter._world_render_capture(self.run.selector,read_only=True,role=role,require_frame_view=True)
            need(isinstance(owned,OwnedWorldRenderCapture) and same(owned.owner.binding,self.binding)
                and owned.owner.role==role and owned.owner.store.read() is None)
        self.bound()

    def validate_controls(self):
        self.check_controls();need(self.owner_state['baseline'] is not None and self.owner_state['setup']==dict(view='issued',scene='issued'))
        for role in ('primary','actor'):
            for segment in range(self.owner_state['segment']+1):
                source=self.source(role,segment)
                if role=='primary':self.inputs(source)
            observer=self.role(role)
            for index in range(1,observer.state['sequence']+1):observer.stored(index)
        self.actor();self.lifetime(self.source())
        self.validate_cleanup()
        self.validate_failures()
        background=self.original('phone-emote-background.json')
        if background is not None:
            value=object.__new__(PhoneEmoteBackground)
            value.adapter,value.selector,value.phase,value.lock=self.run.adapter,self.run.selector,self.run.phase,self.run.lock
            value.artifact_root,value.monotonic,value.sleep=self.run.root,self.run.monotonic,forbidden
            value.run,value.fixture_url,value.segment=self.run.run,self.run.fixture_url,background.get('sourceSegment',0)
            value.store=self.file('phone-emote-background.json');value.sources=self.file(source_name('primary',value.segment))
            value.previous=value.archive_header=deepcopy(background);value.historical=True;value.failed=False
            value.started=value.clock=value.before_phase=None
            state=value.decode(background);need(same(state['binding'],self.binding)
                and (state['cleanup'] is not None and state['cleanup']['phase']=='observed' or state['phase']=='observed'))
            _state,before=value.archive(state['beforeHeader'],self.binding)
            current=self.source('primary',value.segment);need(same(current.frames[:len(before)],before))
            if state['afterHeader'] is not None:
                _state,after=value.archive(state['afterHeader'],self.binding);need(same(current.frames[:len(after)],after))
            need(value.status(self.binding)['foreground'] is True)
        need(all(self.original('phone-emote-'+role+'-admission.json') is None for role in ('primary','actor'))
            and self.original('phone-emote-actor-lifetime.json') is None)
        for segment in range(self.owner_state['segment']+1,MAX_SEGMENTS):
            need(self.original(input_name(segment)) is None)
            for role in ('primary','actor'):need(self.original(source_name(role,segment)) is None)
        self.resources_absent();self.phase()

    def validate_cleanup(self):
        cleanup=object.__new__(PhoneEmoteCleanup);cleanup.inputs=self.inputs(self.source());cleanup.source=cleanup.inputs.source
        cleanup.run,cleanup.fixture_url,cleanup.binding=self.run.run,self.run.fixture_url,self.binding
        cleanup.origin=hashlib.sha256(canonical(cleanup.inputs.previous)).hexdigest();cleanup.state={}
        header=self.original('phone-emote-cleanup-inputs.json');need(header is not None)
        cleanup.state=cleanup.decode(header);need(cleanup.state['final'] is not None)
        return cleanup.state

    def validate_failures(self):
        failures=self.original('phone-emote-failures.json')
        if failures is not None:
            value=object.__new__(PhoneEmoteFailures);value.run=self.shadow_run();value.binding=self.binding
            value.store=self.file('phone-emote-failures.json');value.previous=failures;value.failed=False;value.started=value.clock=None
            value.bound=self.context_bound(value,20);value.role=lambda role,policy:self.role(role,policy)
            value.originals=FailureOriginals(self.run.root,self.binding,self.run.run,'primary',value.bound,forbidden,
                kind='source-failures',monotonic=self.run.monotonic)
            value.state=value.decode(failures);need(value.state['pending'] is None)
            for index,row in enumerate(value.originals.restore(value.state['manifests'],value.state['count']),1):value.record(row,index)
        self.bound()

    def validate_unissued(self):
        self.check_controls();setup=self.state['mode']=='setup'
        need(self.owner_state['call'] is None and self.owner_state['segment']==0)
        if setup:need(self.owner_state.get('prepared') is False and self.owner_state['baseline'] is not None
            and self.owner_state['admissionSha256'] is not None and self.owner_state['setup']['view']=='issued')
        else:need(self.owner_state['setup']==dict(view='unissued',scene='unissued'))
        for name in self.names:
            allowed={'phone-emote-run.json','phone-emote-primary-sources.json','phone-emote-namespaces.json',
                'phone-emote-failures.json','phone-emote-actor-lifecycle.json','phone-emote-cleanup-inputs.json'}
            if setup:
                allowed.add('phone-emote-primary-lifetime.json')
                allowed.update('phone-emote-'+kind+'.json' for kind,flag in self.owner_state['setup'].items() if flag=='issued')
            if name not in allowed:need(self.original(name) is None)
        source=self.source();self.validate_failures();actor=self.actor()
        namespace=self.namespace();state=namespace.state
        need(state['current']==0 and state['closed']==[] and state['pending'] is None and state['cleanup'] is not None)
        cleanup=state['cleanup'];need(cleanup['ticket']==self.owner_state['cleanupTicket'] and cleanup['pending'] is None
            and cleanup['inputsSha256']==hashlib.sha256(canonical(None)).hexdigest() and cleanup['headers']['actor'] is None)
        header=cleanup['headers']['primary']
        if header is not None:
            prior,frames=PhoneEmoteSources.archive(header,phase=self.run.phase,artifact_root=self.run.root,binding=self.binding,
                guard=self.bound,monotonic=self.run.monotonic)
            need(prior['phase']=='ready' and prior['pending'] is None and len(source.frames)>=len(frames)
                and same(source.frames[:len(frames)],frames))
        baseline=self.owner_state['baseline']
        if baseline is not None:
            PhoneEmoteInputs.original(self.inputs(source),baseline)
            restored=self.validate_cleanup()
            if setup:need(all(row['kind']=='sdk' and row['controlId']=='tablet.close' for row in restored['current']['intents']))
            else:need(not restored['current']['intents'])
        else:need(self.original('phone-emote-cleanup-inputs.json') is None)
        if setup:self.lifetime(self.source())
        self.resources_absent();self.phase();return actor

    def unissued_proof(self):
        self.validate_unissued();started=self.run.monotonic();host=self.run.phase.epoch_ms()
        provider=self.phase();self.bound()
        need(number(self.run.monotonic(),started,1e15) and number(host,1,1e15))
        return dict(emoteUnissuedRetirementVersion=1,runHeader=deepcopy(self.owner),namespaceHeader=self.original('phone-emote-namespaces.json'),
            sourceHeader=self.original('phone-emote-primary-sources.json'),actorHeader=self.original('phone-emote-actor-lifecycle.json'),
            provider=provider,startedMonotonicMs=started*1000,hostEpochMs=host)

    def unissued_delivery(self,proof):
        self.bound();need(type(proof['emoteUnissuedRetirementVersion']) is int and proof['emoteUnissuedRetirementVersion']==1
            and same(proof['runHeader'],self.owner))
        status=self.run.phase.status(proof['provider']);need(not status['active'])
        now,host=self.run.monotonic(),self.run.phase.epoch_ms()
        need(number(now,proof['startedMonotonicMs']/1000,1e15) and number(host,proof['hostEpochMs'],1e15)
            and now*1000-proof['startedMonotonicMs']<5000
            and max(host-proof['provider']['capturedEpochMs'],proof['hostEpochMs']-proof['provider']['capturedEpochMs']
                +now*1000-proof['startedMonotonicMs'])<=1500)
        self.bound()

    def retire_namespace(self):
        if self.state['mode']=='setup':
            saved=self.get('namespace')
            if saved is None:
                saved=dict(emoteSetupNamespaceRetirementVersion=1,header=self.original('phone-emote-namespaces.json'),
                    runHeader=deepcopy(self.owner),sourceHeader=self.original(source_name('primary',0)),
                    actorHeader=self.original('phone-emote-actor-lifecycle.json'),provider=self.phase())
                self.retain('namespace',saved)
            need(type(saved.get('emoteSetupNamespaceRetirementVersion')) is int and saved['emoteSetupNamespaceRetirementVersion']==1
                and same(saved['header'],self.original('phone-emote-namespaces.json')) and same(saved['runHeader'],self.owner)
                and same(saved['sourceHeader'],self.original(source_name('primary',0)))
                and same(saved['actorHeader'],self.original('phone-emote-actor-lifecycle.json')))
            self.run.phase.status(saved['provider']);actual=self.file('phone-emote-namespaces.json').read()
            if actual is not None:need(same(actual,saved['header']));self.file('phone-emote-namespaces.json').discard(actual)
            need(self.file('phone-emote-namespaces.json').read() is None)
        else:
            namespace=self.namespace();saved=self.get('namespace')
            namespace.retire_closed(lambda proof:self.retain('namespace',proof),retained=saved)

    def retire_resources(self):
        view=PhoneEmoteView(self.run.adapter,self.run.selector,self.run.phase,self.run.lock,monotonic=self.run.monotonic,sleep=self.run.sleep)
        scene=(PhoneEmoteScene(view,self.run.root,self.run.extent,self.run.marker,monotonic=self.run.monotonic,sleep=self.run.sleep)
            if self.owner_state['setup']['scene']=='issued' else None)
        for key,child,name in (('scene',scene,'phone-emote-scene.json'),('view',view,'phone-emote-view.json')):
            if child is None:need(self.original(name) is None and self.file(name).read() is None);continue
            saved=self.get(key);need(saved is None or same(saved['header'],self.original(name)))
            child.retire_closed(lambda proof:self.retain(key,proof),retained=saved)
        self.retire_namespace()
        # These are new actual groups, including on an archived child retry.
        view.state=view.decode(self.get('view')['header'])
        fresh=view.read(closed=True);view.restored(view.state['original'],fresh);view.delivery(fresh)
        view_frame=deepcopy(fresh);scene_frame=None
        if scene is not None:
            scene.state,scene.frames=scene.decode(self.get('scene')['header']);scene.required_phase='cleanup'
            scene.expected_ticket=self.owner_state['cleanupTicket'];scene_frame=scene.query('fixture',closed=True);scene.drained(scene_frame)
            view.restored(view.state['original'],dict(configuration=scene_frame['configuration'],avatar=scene_frame['avatar'],touch=scene_frame['touch']))
        self.retain('resources/'+str(self.state['attempts']),dict(view=view_frame,scene=scene_frame))
        if scene is not None:scene.delivery(scene_frame)
        else:view.delivery(view_frame)

    def finalize(self):
        self.bound();need(self.started is None);self.started=self.run.monotonic()
        try:
            if self.previous is None:self.save()
            if self.state['pending'] is not None:
                pending=deepcopy(self.state['pending']);self.retain(pending['key'],pending['value'])
            unissued=self.state['mode']=='unissued'
            if self.state['mode'] in ('unissued','setup'):self.validate_unissued()
            else:self.validate_controls()
            for name in self.names:self.retain('control/'+name,dict(name=name,value=self.original(name)))
            self.check_controls();need(self.state['attempts']<15);self.state['attempts']+=1;attempt=self.state['attempts'];self.save()
            if unissued:
                proof=self.unissued_proof();key='unissued/'+str(attempt);self.retain(key,proof)
                deliver=lambda:self.unissued_delivery(proof)
            else:
                self.retire_resources();self.check_controls()
                def retain(proof):self.retain('work/'+str(attempt)+'/'+proof['phase'],proof)
                source=self.source();life=self.lifetime(source);proof=life.final_work(retain)
                key='work/'+str(attempt)+'/complete'
                deliver=lambda:self.delivery(source,proof)
            need(same(self.get(key),proof))
            self.state.update(phase='retiring',verification=key);self.save();self.check_controls();self.resources_absent()
            for name in self.names:
                self.witness(name);actual=self.file(name).read()
                if actual is not None:self.file(name).discard(actual)
                need(self.file(name).read() is None);self.bound()
            self.check_controls()
            # This barrier belongs to the actual current acquisition; historical
            # packet times are never promoted into an acquisition anchor.
            deliver()
            # This artifact remains after controller removal. It contains the
            # complete original inode/digest reference graph, not a fresh fact
            # or a substitute for observing the controller's actual removal.
            handoff=PrivateFeatureState(self.run.root/('emote-retirement-handoff-'+self.run.run+'-'+str(attempt)+'.json'))
            value=dict(emoteRetirementHandoffVersion=1,retirementHeader=deepcopy(self.previous))
            existing=handoff.read()
            if existing is None:handoff.write(value,None)
            need(same(handoff.read(),value));self.check_controls();deliver()
            self.bound();self.store.discard(self.previous);need(self.store.read() is None)
            self.previous=None;self.bound();self.finished=True;return {'performed':True}
        finally:self.started=None


    def delivery(self,source,proof):
        self.bound();started,epoch,host,phase_started,clock=source.closed_anchor;frame=proof['source']['frame']
        status=self.run.phase.status(proof['providerAfter']);need(not status['active'])
        now,host_now,end=clock(),self.run.phase.epoch_ms(),self.run.monotonic()
        floor=frame['group']['rootsBefore']['requestedEpochMs'];provider=frame['phaseBefore']['capturedEpochMs']
        need(number(end,started,1e15) and end-started<5 and integer(now,frame['epochMs']) and number(host_now,frame['hostEpochMs'],1e15)
            and max(now-floor,epoch-floor+(end-started)*1000)<=1500
            and max(host_now-provider,host-provider+(end-phase_started)*1000)<=1500)
        self.bound()
