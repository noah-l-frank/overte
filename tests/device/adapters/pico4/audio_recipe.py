"""Durable normal v16 Audio dispatch; no independent/acoustic/full verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.audio_page_owner import PicoAudioPageOwner
from adapters.pico4.audio_capture_owner import PicoAudioCaptureOwner,read_original_file
from adapters.pico4.audio_background_owner import PicoAudioBackground
from adapters.pico4.audio_final_close import PicoAudioFinalClose
from adapters.pico4.lifecycle_back import BUTTON
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.script_journey.history import pack,unpack
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.contract import arguments
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from feature_journeys.scenarios import SCENARIOS,VERSION as COMMON_VERSION

VERSION=1
# Only the shared ordinary input inventory is selected; assertions/evidence
# requirements never enter this dispatcher or any child action.
INPUTS=tuple((row['verb'],deepcopy(row['inputs'])) for row in SCENARIOS['audio']['steps'])
PLAN=(('page.tablet','page.open_audio','page.claim_preview'),('page.mute',),('page.record',),('page.restore',),
    ('capture2.prepare','capture2.start'),('capture2.cancel','capture2.retain'),('capture3.prepare','capture3.start'),
    ('capture3.await','capture3.retain'),('capture4.prepare','capture4.start'),('capture4.mute',),
    ('capture4.restore','capture4.retain'),('capture5.prepare','capture5.start'),
    ('background5.prepare','background5.home','background5.resume','background5.quiet','capture5.retain'),
    ('final5.prepare','final5.release','final5.back','final5.close','final5.quiet','final5.deferred'))
POST={'page.prepare':'prepared','page.tablet':'tablet-open','page.open_audio':'opened','page.claim_preview':'claimed',
    'page.mute':'muted','page.record':'rejected','page.restore':'restored','capture.prepare':'prepared',
    'capture.start':'capturing','capture.cancel':'terminal','capture.await':'terminal','capture.mute':'terminal',
    'capture.restore':'terminal','capture.retain':'retained','background.prepare':'prepared','background.home':'background-observed',
    'background.resume':'returned','background.quiet':'quiet','final.prepare':'prepared','final.release':'released',
    'final.back':'home','final.close':'closed','final.quiet':'closed','final.deferred':'closed'}


def parts(name):
    kind,operation=name.split('.')
    return ('page' if kind=='page' else kind[:-1]),(0 if kind=='page' else int(kind[-1])),operation


class PicoAudioRecipe:
    def __init__(self,path,run,binding,lock,source,page_factory,capture_factory,background_factory,final_factory,os_status,*,monotonic):
        need(COMMON_VERSION==16 and len(INPUTS)==len(PLAN)==14 and isinstance(lock,ScriptSourceLock)
            and isinstance(source,PhaseFixtureReader) and source.run==run and source.area=='audio'
            and all(callable(value) for value in (page_factory,capture_factory,background_factory,final_factory,os_status,monotonic)))
        self.store,self.run,self.binding,self.lock,self.source=PrivateFeatureState(path),run,deepcopy(context(binding)),lock,source
        need(self.store.path==lock.path.with_name('audio-recipe-owner.json'))
        self.factories=dict(page=page_factory,capture=capture_factory,background=background_factory,final=final_factory)
        self.os_status,self.monotonic=os_status,monotonic
        self.sources=ChatSourceChunks(self.store,dict(runId=run,binding=self.binding,role='audio-recipe-originals'))
        self.disk=self.state=None;self.frames=[];self.children={};self.current=None;self.last_clock=None;self.loaded=False
        self.delivery_callback=self.before_send;self.stream_callback=self.before_stream;self.page_gate=self.page_input_gate;self.os_callback=self.before_os
        with lock.held():self.disk=self.store.read();self.load()
    def bound(self,*,host_only=False):
        self.lock.assert_held();need(self.store.read()==self.disk)
        if self.loaded:self.sources.verify()
        now=self.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock)
            and all(now>=frame['hostMonotonic'] for frame in self.frames));self.last_clock=now
        return now
    def validate(self,state):
        exact(state,{'cursor','baseline','steps','pending','lastPhase'})
        need(integer(state['cursor'],0,len(PLAN)) and type(state['steps']) is list
            and len(state['steps']) in (state['cursor'],min(len(PLAN),state['cursor']+1)))
        def phase(value):
            phase_packet(value,run=self.run,area='audio',request=value['requestId'],epoch=value['capturedEpochMs'])
            need(value['active'] and value['activations'])
        previous=None;reference=0;latest={};qml_ids=set();qml_sequence=0;controller=None
        starts={cycle:state['steps'][index]['source'] for cycle,index in ((2,4),(3,6),(4,8),(5,11)) if index<len(state['steps'])}
        def action(value,expected,*,pending=False):
            nonlocal reference,qml_sequence,controller
            exact(value,{'name','before','after','deliveries'}|({'source'} if pending else set()))
            need(value['name']==expected);self.deliveries(value['deliveries'],expected,completed=not pending)
            for delivery in value['deliveries']:
                command=delivery['original']
                if delivery['kind']=='qml':
                    need(command['commandId'] not in qml_ids and command['sequence']>qml_sequence)
                    qml_ids.add(command['commandId']);qml_sequence=command['sequence']
                elif delivery['kind']=='controller':
                    if controller is not None:need(command['sessionNonce']==controller['sessionNonce'] and command['sequence']==controller['sequence']+1)
                    controller=command
            for stage in ('before','after'):
                index=value[stage]
                if index is None:need(pending and (stage=='after' or value['after'] is None));continue
                need(type(index) is int and index==reference and index<len(self.frames));reference+=1
                frame=self.frames[index];need(frame['action']==expected and frame['stage']==stage)
                self.check_original(frame)
                if stage=='after' and value['deliveries'] and value['deliveries'][0]['kind']=='controller':
                    original=unpack(frame['original']['payload'])[0]
                    need(original['streams'][-1]['envelope']==value['deliveries'][0]['original'])
                kind,cycle,_operation=parts(expected);key=(kind,cycle);root=frame['original']
                if stage=='before':need(root==latest.get(key))
                latest[key]=root
                if root is not None and kind!='page':
                    child=unpack(root['payload'])[0]
                    original=child['start'] if kind=='capture' else child['fixturePhase']
                    source=starts[cycle] if kind=='capture' else state['steps'][12 if kind=='background' else 13]['source']
                    need(all(original[field]==source[field] for field in ('instance','createdEpochMs','activations')))
                    if kind=='background':latest[('capture',cycle)]=child['captureArchive']
            if not pending:need(value['before'] is not None and value['after'] is not None)
        if state['baseline'] is not None:
            exact(state['baseline'],{'source','action'});previous=state['baseline']['source'];phase(previous)
            need(previous['activations'][-1]['stimulus']==dict(verb='baseline',inputs={}))
            action(state['baseline']['action'],'page.prepare')
        else:need(state['cursor']==0 and not state['steps'])
        for index,row in enumerate(state['steps']):
            exact(row,{'source','actions'});phase(row['source'])
            need(previous is not None and row['source']['instance']==previous['instance']
                and row['source']['createdEpochMs']==previous['createdEpochMs']
                and row['source']['activations'][:-1]==previous['activations'])
            need(row['source']['activations'][-1]['stimulus']==dict(verb=INPUTS[index][0],inputs=INPUTS[index][1]))
            previous=row['source'];need(type(row['actions']) is list and len(row['actions'])<=len(PLAN[index]))
            if index<state['cursor']:need(len(row['actions'])==len(PLAN[index]))
            for value,expected in zip(row['actions'],PLAN[index]):action(value,expected)
        if state['lastPhase'] is not None:
            phase(state['lastPhase'])
            if previous is not None:need(state['lastPhase']==previous)
        pending=state['pending']
        if pending is not None:
            phase(pending['source']);need(pending['source']==state['lastPhase'])
            if state['baseline'] is None:expected='page.prepare'
            else:
                need(state['cursor']<len(PLAN) and len(state['steps'])==state['cursor']+1)
                expected=PLAN[state['cursor']][len(state['steps'][-1]['actions'])]
            action(pending,expected,pending=True)
        need(reference==len(self.frames))
    def check_original(self,frame):
        value=frame['original'];kind,cycle,operation=parts(frame['action'])
        if value is None:need(frame['stage']=='before' and operation=='prepare');return
        need(type(value) is dict and value.get('runId')==self.run and value.get('binding')==self.binding)
        version=dict(page='audioPageOwnerVersion',capture='audioCaptureOwnerVersion',background='audioBackgroundOwnerVersion',final='audioFinalCloseVersion')[kind]
        need(type(value.get(version)) is int and value[version] in ((1,2) if kind=='capture' else (1,)))
        if kind in ('capture','final'):need(value.get('fixtureUrl')==self.source.fixture_url)
        states=unpack(value['payload']);need(len(states)==1);original=states[0]
        if kind in ('capture','background'):
            need(original.get('beforeCycle',cycle-1)+1==cycle if kind=='capture' else original['cycle']==cycle)
        if frame['stage']=='after':
            need(original['phase']==POST[kind+'.'+operation])
            if frame['action']=='page.prepare':need(original['previewOrigin'] is False)
            if kind=='final' and operation in ('quiet','deferred'):
                need(original['quiet'] and original['quiet'][-1]['where']=='closed'
                    and original['quiet'][-1]['deferred']==(operation=='deferred'))
    def deliveries(self,rows,action,*,completed=False):
        need(type(rows) is list and len(rows)<=24)
        kind,_cycle,operation=parts(action)
        target={'page.open_audio':'audio.entry','page.mute':'audio.mute','page.restore':'audio.mute','page.record':'audio.record',
            'capture.start':'audio.record','capture.cancel':'audio.record','capture.mute':'audio.mute','capture.restore':'audio.mute'}.get(kind+'.'+operation)
        mode='qml' if target else 'controller' if action in ('page.tablet','final5.back','final5.close') else 'os' if kind=='background' and operation in ('home','resume') else None
        for row in rows:
            exact(row,{'kind','original'});need(row['kind']==mode and type(row['original']) is dict)
            command=row['original']
            if mode=='qml':
                scrolling=command.get('controlId')=='audio.scrollbar'
                exact(command,{'schemaVersion','commandId','bridgeId','generation','sequence','observedElapsedMs','controlId','controlToken','action'}|({'direction'} if scrolling else set()))
                need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and command['bridgeId']==self.binding['sessionId']
                    and integer(command['sequence'],1,2**53-1)
                    and number(command['observedElapsedMs'],0,1e15) and command['controlId'] in (target,'audio.scrollbar','audio.mode.vr')
                    and command['action']==('scroll' if scrolling else 'activate'))
                for key in ('commandId','controlToken','generation'):need(type(command[key]) is str and re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',command[key]))
                if scrolling:need(command['direction'] in ('up','down'))
            elif mode=='controller':
                exact(command,{'schemaVersion','sessionNonce','sequence','commands'})
                need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and type(command['sessionNonce']) is str
                    and re.fullmatch('[0-9a-f]{32,128}',command['sessionNonce']) and integer(command['sequence'],1,2**53-1))
                opening=action=='page.tablet';need(command['commands']==[dict(id=('tablet-open-' if opening else 'controller-button-')+str(command['sequence']),
                    operation='tablet.open' if opening else 'controller.button',arguments=dict(holdMilliseconds=1000) if opening else BUTTON)])
            elif mode=='os':
                exact(command,{'operation','binding'});need(command['binding']==self.binding
                    and command['operation']==('lifecycle.background' if operation=='home' else 'app.launch'))
        if completed:
            if mode=='qml':need(sum(row['original'].get('controlId')==target and row['original'].get('action')=='activate' for row in rows)==1)
            elif mode is not None:need(len(rows)==1)
            else:need(not rows)
    def load(self):
        self.bound();disk=self.store.read()
        if disk is None:need(self.state is None);self.sources.inventory(0);self.loaded=True;return
        exact(disk,{'audioRecipeVersion','runId','binding','fixtureUrl','phase','chunks','payload'})
        need(type(disk['audioRecipeVersion']) is int and disk['audioRecipeVersion']==VERSION and disk['runId']==self.run
            and disk['binding']==self.binding and disk['fixtureUrl']==self.source.fixture_url
            and disk['phase'] in ('ready','issued','reading','partial-complete'))
        frames=self.sources.load(disk['chunks'])
        for frame in frames:
            exact(frame,{'action','stage','original','hostMonotonic'});need(number(frame['hostMonotonic'],0,1e15) and frame['stage'] in ('before','after') and type(frame['action']) is str
                and (frame['original'] is None or type(frame['original']) is dict))
        need(all(b['hostMonotonic']>=a['hostMonotonic'] for a,b in zip(frames,frames[1:])))
        values=unpack(disk['payload']);need(len(values)==1);self.frames=frames;self.validate(values[0]);self.state=deepcopy(values[0]);self.disk=deepcopy(disk);self.loaded=True;self.bound()
        need((disk['phase'] in ('issued','reading'))==(self.state['pending'] is not None))
        need(disk['phase']!='partial-complete' or self.state['cursor']==len(PLAN) and self.state['pending'] is None)
    def save(self,state,*,phase=None,chunks=None):
        self.bound(host_only=True);self.validate(state)
        value=dict(audioRecipeVersion=VERSION,runId=self.run,binding=self.binding,fixtureUrl=self.source.fixture_url,
            phase=phase or self.disk['phase'],chunks=(self.disk['chunks'] if chunks is None else chunks),payload=pack([state]))
        self.store.write(value,self.disk);need(self.store.read()==value);self.state,self.disk=deepcopy(state),deepcopy(value);self.bound(host_only=True)
    def archive(self,action,stage,original):
        phase=self.disk['phase'];self.save(deepcopy(self.state),phase='reading')
        frame=dict(action=action,stage=stage,original=deepcopy(original),hostMonotonic=self.bound());self.check_original(frame)
        manifest=self.sources.append(frame,self.disk['chunks']);self.frames.append(frame)
        state=deepcopy(self.state);need(state['pending']['name']==action and state['pending'][stage] is None)
        state['pending'][stage]=len(manifest)-1;self.save(state,phase=phase,chunks=manifest)
        return len(manifest)-1
    def status(self):
        value=self.os_status(deepcopy(self.binding));exact(value,{'binding','foreground','running'})
        need(value['binding']==self.binding and value['running'] is True and type(value['foreground']) is bool);return value
    def child(self,name):
        kind,cycle,_operation=parts(name);key=(kind,cycle)
        if key not in self.children:
            if kind!='background':need(self.status()['foreground'])
            if kind=='page':
                child=self.factories[kind]();need(isinstance(child,PicoAudioPageOwner))
                need(child.recipe_gate in (None,self.page_gate) and child.before_stream in (None,self.stream_callback))
                child.recipe_gate,child.before_stream=self.page_gate,self.stream_callback
                # Both actual normal UI transports are captured by their
                # original factory; the preview factory returns only a wrapper.
                child.route.io.bind_before_send(self.delivery_callback)
                child.preview._ui().io.bind_before_send(self.delivery_callback)
            elif kind=='capture':child=self.factories[kind](cycle,self.child('page.prepare'));need(isinstance(child,PicoAudioCaptureOwner))
            elif kind=='background':
                child=self.factories[kind](cycle,self.children.get(('capture',cycle)));need(isinstance(child,PicoAudioBackground))
                need(child.before_os in (None,self.os_callback));child.before_os=self.os_callback
            else:
                child=self.factories[kind](cycle,self.child(f'capture{cycle}.prepare'));need(isinstance(child,PicoAudioFinalClose))
                need(child.before_stream in (None,self.stream_callback));child.before_stream=self.stream_callback
            need(child.run==self.run and child.binding==self.binding and child.lock is self.lock and child.store.path.parent==self.store.path.parent)
            self.children[key]=child
        return self.children[key]
    def anchor(self):return self.bound(),self.source.epoch_ms()
    def fence(self,anchor,original,*,native=True):
        started,requested=anchor;self.bound();foreground=self.status()['foreground'];page=self.children.get(('page',0))
        if native and foreground and page is not None and page.anchor is not None:page.fresh()
        value=self.source.status(original)
        need(value['active'] and all(value[key]==original[key] for key in ('instance','createdEpochMs','activations')))
        epoch=self.source.epoch_ms();completed=self.bound()
        need(number(epoch,requested,1e15) and -250<=epoch-value['capturedEpochMs']
            and max(epoch-value['capturedEpochMs'],requested-value['capturedEpochMs']+(completed-started)*1000)<=1500)
        return started,requested,value['capturedEpochMs'],epoch,completed
    def active_pending(self):
        self.bound(host_only=True);need(self.current is not None and self.state['pending'] is not None
            and self.state['pending']['name']==self.current and self.state['pending']['before'] is not None and self.disk['phase']=='issued')
        return self.state['pending']
    def page_input_gate(self):
        self.active_pending();need(parts(self.current)[0]=='page');return True
    def record_delivery(self,kind,command):
        pending=self.active_pending();state=deepcopy(self.state)
        state['pending']['deliveries'].append(dict(kind=kind,original=deepcopy(command)));self.save(state,phase='issued')
        return pending['source']
    def before_send(self,command):
        need(type(command) is dict and type(command.get('controlId')) is str);pending=self.active_pending();kind,_cycle,operation=parts(pending['name'])
        allowed={'page.open_audio':{'audio.entry'},'page.mute':{'audio.mute','audio.scrollbar'},'page.restore':{'audio.mute','audio.scrollbar'},
            'page.record':{'audio.record','audio.scrollbar'},'capture.start':{'audio.record','audio.scrollbar','audio.mode.vr'},
            'capture.cancel':{'audio.record','audio.scrollbar'},'capture.mute':{'audio.mute','audio.scrollbar'},'capture.restore':{'audio.mute','audio.scrollbar'}}
        need(command['controlId'] in allowed.get(kind+'.'+operation,set()))
        anchor=self.anchor();page=self.child('page.prepare')
        if kind=='page':page.capture()
        else:self.child(pending['name']).capture()
        original=self.record_delivery('qml',command);self.fence(anchor,original)
    def before_stream(self):
        pending=self.active_pending();need(pending['name'] in ('page.tablet','final5.back','final5.close'));anchor=self.anchor();fixture=self.fence(anchor,pending['source'])
        native=self.child('page.prepare').anchor
        def check_age(*,publish=False):
            # Final publication validates only already retained memory and the
            # advancing host clock: no source, SDK, session, CAS or filesystem IO.
            now=self.monotonic() if publish else self.bound(host_only=True)
            need(number(now,0,1e15) and now>=self.last_clock);self.last_clock=now
            started,requested,captured,epoch,completed=fixture;native_started,native_requested,native_captured=native
            need(now>=completed and native_requested-native_captured+(now-native_started)*1000<=1500
                and max(epoch-captured+(now-completed)*1000,requested-captured+(now-started)*1000)<=1500)
        def intent(command):
            operation='tablet.open' if pending['name']=='page.tablet' else 'controller.button'
            need(len(command['commands'])==1 and command['commands'][0]['operation']==operation
                and command['commands'][0]['arguments']==(dict(holdMilliseconds=1000) if operation=='tablet.open' else BUTTON))
            self.record_delivery('controller',command);check_age()
        def publish(command):
            current=self.state['pending'];need(self.current==pending['name'] and current is not None and current['name']==pending['name']
                and current['deliveries'] and current['deliveries'][-1]==dict(kind='controller',original=command));check_age(publish=True)
        return intent,publish
    def before_os(self,operation,binding):
        pending=self.active_pending();need(pending['name'] in ('background5.home','background5.resume') and binding==self.binding)
        need(operation==('lifecycle.background' if pending['name']=='background5.home' else 'app.launch'))
        anchor=self.anchor();original=self.record_delivery('os',dict(operation=operation,binding=deepcopy(binding)))
        self.fence(anchor,original,native=False)
    def original(self,name):
        child=self.child(name);child.load();return deepcopy(child.store.read())
    def prepare(self):
        with self.lock.held():
            self.load();need(self.state is None);source=self.source.status()
            need(source['active'] and source['activations'][-1]['stimulus']==dict(verb='baseline',inputs={}))
            state=dict(cursor=0,baseline=None,steps=[],pending=None,lastPhase=source)
            # No existing immutable originals may be adopted by a new owner.
            self.save(state,phase='ready',chunks=[]);self.action('page.prepare',source)
    def invoke_child(self,name):
        child=self.child(name);kind,_cycle,operation=parts(name)
        if kind=='page':
            if operation in ('mute','record','restore'):return child.action(operation)
            return getattr(child,operation)()
        if kind=='capture':return getattr(child,{'await':'await_completion','retain':'retain_originals','mute':'mute_interrupt','restore':'restore_mute'}.get(operation,operation))()
        if kind=='background':return getattr(child,operation)()
        if operation in ('back','close'):return child.stream('back-issued' if operation=='back' else 'tablet-close-issued')
        if operation=='quiet':return child.quiet('closed')
        return getattr(child,{'deferred':'await_deferred'}.get(operation,operation))()
    def post(self,name):
        child=self.child(name);child.load();kind,_cycle,operation=parts(name);need(child.state is not None and child.state['phase']==POST[kind+'.'+operation])
        if name=='page.prepare':need(child.state['previewOrigin'] is False)
        if kind=='capture' and operation=='await':need(child.frame(child.state['frames'][-1])['audio']['recordedVoice']['event']['phase']=='completed')
        if kind=='final' and operation in ('quiet','deferred'):
            need(child.state['quiet'] and child.state['quiet'][-1]['where']=='closed' and child.state['quiet'][-1]['deferred']==(operation=='deferred'))
        return deepcopy(child.store.read())
    def finish(self):
        pending=self.active_pending();name=pending['name'];after=self.post(name)
        if pending['after'] is None:
            self.archive(name,'after',after)
        else:need(self.frames[pending['after']]['original']==after)
        anchor=self.anchor();state=deepcopy(self.state);pending=state['pending'];state['pending']=None
        if name=='page.prepare':state['baseline']=dict(source=pending['source'],action={key:pending[key] for key in ('name','before','after','deliveries')})
        else:
            state['steps'][-1]['actions'].append(dict(name=name,before=pending['before'],after=pending['after'],deliveries=pending['deliveries']))
            if len(state['steps'][-1]['actions'])==len(PLAN[state['cursor']]):state['cursor']+=1
        self.save(state,phase='partial-complete' if state['cursor']==len(PLAN) else 'ready')
        result=self.report();self.resources();self.fence(anchor,pending['source']);return result
    def action(self,name,source):
        need(self.state['pending'] is None and self.current is None and self.disk['phase']=='ready')
        anchor=self.anchor();state=deepcopy(self.state)
        state['pending']=dict(name=name,source=deepcopy(source),before=None,after=None,deliveries=[]);self.save(state,phase='issued')
        self.current=name
        try:
            before=self.original(name);self.archive(name,'before',before)
            self.fence(anchor,source,native=False);self.invoke_child(name);return self.finish()
        finally:self.current=None
    @staticmethod
    def matches(call,source):
        activation=source['activations'][-1]
        return activation['ticket']==call['ticket'] and activation['stimulus']==dict(verb=call['verb'],inputs=call['inputs'])
    def resources(self):
        # Pure original host files remain checkable while Qt is backgrounded.
        expected={};pending=self.state['pending'];allowed=set()
        if pending is not None:
            kind,cycle,_operation=parts(pending['name']);allowed.add((kind,cycle))
            if kind=='background':allowed.add(('capture',cycle))
        for frame in self.frames:
            kind,cycle,_operation=parts(frame['action']);value=frame['original'];expected[(kind,cycle)]=value
            if kind=='background' and value is not None:expected[('capture',cycle)]=unpack(value['payload'])[0]['captureArchive']
        for (kind,cycle),value in expected.items():
            name='audio-page-owner.json' if kind=='page' else 'audio-final-close.json' if kind=='final' else f'audio-{kind}-cycle-{cycle:02d}.json'
            if (kind,cycle) not in allowed:need(PrivateFeatureState(self.store.path.with_name(name)).read()==value)
            if kind=='capture' and value is not None:
                state=unpack(value['payload'])[0]
                for original in state['artifacts'].values():
                    if original['phase']=='saved':read_original_file(self.store.path,original)
    def act(self,call):
        call=arguments('feature.audio.act',call);need(call['runId']==self.run and call['fixtureUrl']==self.source.fixture_url)
        with self.lock.held():
            self.load();need(self.state is not None and self.state['baseline'] is not None and self.disk['phase']!='reading');self.resources()
            if self.state['pending'] is not None:
                need(self.matches(call,self.state['pending']['source']));return self.reconcile()
            index=self.state['cursor']
            if index and self.matches(call,self.state['steps'][index-1]['source']):
                original=self.state['steps'][index-1]['source'];anchor=self.anchor()
                self.fence(anchor,original,native=False);result=self.report();self.fence(anchor,original,native=False);return result
            need(index<len(PLAN) and (call['verb'],call['inputs'])==INPUTS[index])
            source=self.source.status(self.state['lastPhase']);need(source['active'] and self.matches(call,source))
            if len(self.state['steps'])==index:
                state=deepcopy(self.state);state['steps'].append(dict(source=source,actions=[]));state['lastPhase']=source;self.save(state)
            else:
                need(self.state['steps'][-1]['source']['activations']==source['activations']);source=self.state['steps'][-1]['source']
            for name in PLAN[index][len(self.state['steps'][index]['actions']):]:self.action(name,source)
            anchor=self.anchor();result=self.report();self.resources();self.fence(anchor,source);return result
    def reconcile(self):
        with self.lock.held():
            self.load();need(self.state is not None and self.state['pending'] is not None and self.disk['phase']=='issued');pending=self.state['pending']
            need(pending['before'] is not None);self.resources();name=pending['name'];self.current=name
            try:
                self.fence(self.anchor(),pending['source'],native=False);child=self.child(name);child.load()
                kind,_cycle,operation=parts(name);phase=child.state['phase']
                observational=kind=='final' and operation in ('quiet','deferred')
                original=self.frames[pending['before']]['original']
                need(child.store.read()!=original or observational)
                if observational:
                    need(original is not None)
                    # Retrying an already issued read-only wait cannot deliver
                    # another normal input. Preserve every original frame/window
                    # and all immutable close/process/source ownership fields.
                    before=unpack(original['payload'])[0];after=child.state
                    need(phase==before['phase']=='closed' and all(after[key]==value for key,value in before.items() if key not in ('frames','quiet'))
                        and after['frames'][:len(before['frames'])]==before['frames'] and after['quiet'][:len(before['quiet'])]==before['quiet'])
                    completed=after['quiet'] and after['quiet'][-1]['where']=='closed' and after['quiet'][-1]['deferred']==(operation=='deferred')
                    if not completed:
                        if operation=='quiet':child.quiet('closed')
                        else:child.await_deferred()
                if kind in ('page','capture','final') and (phase.endswith('-issued') or phase in ('opening','awaiting')):child.reconcile()
                elif kind=='background':
                    if operation=='home' and phase in ('home-issued','background-observed'):child.observe_background()
                    elif operation=='resume' and phase=='resume-issued':child.reconcile()
                # Interrupted PCM writers, missing delivery/cursors and private
                # intent gaps stay unresolved. No normal child action is retried.
                return self.finish()
            finally:self.current=None
    def report(self):
        need(self.state is not None)
        return dict(normalStagesDispatched=self.state['cursor'],normalRecipeStages=len(PLAN),
            pending=None if self.state['pending'] is None else self.state['pending']['name'],
            fullAudioQualified=False,acousticObserved=False,independentPeerObserved=False,journalsRetained=True)
