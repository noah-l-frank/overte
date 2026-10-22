"""Durable normal NEW domain Model ownership; full Create remains separate."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from adapters.native_feature_observation import decode,exact,fresh,integer,need
from adapters.native_script_work import scope as work_scope,members
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_callbacks import active as active_callbacks
from adapters.pico4.create_entities import retired as entities_retired
from adapters.pico4.create_picker_owner import OriginalReader,OwnedCreatePicker
from adapters.script_journey.history import pack,unpack
from adapters.token_create_ui import control_id,nonce,scope
from feature_journeys.contract import arguments,identifier
from feature_journeys.scenarios import VERSION as CONTRACT

VERSION=2
WORK_VERSION=1
RESOURCES=('gltf-bundle/main.gltf','obj-bundle/main.obj')


def source_pin():
    code=(Path(__file__).resolve().parents[4]/'scripts/system/create/edit.js').read_text(encoding='utf-8').encode('utf-16le')
    return dict(encoding='utf-16le-code-units',codeUnits=len(code)//2,sha256=hashlib.sha256(code).hexdigest())


def selected(packet,pin):
    rows=[]
    for manager in packet['source']['managers']:
        for compilation in manager['compiled']['compilations']:
            url=urlsplit(compilation['resourceName'])
            if (url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment
                    and url.path.endswith('/system/create/edit.js') and all(compilation[k]==pin[k] for k in pin)):
                need(manager['membership']['assigned']);rows.append((manager['membership'],compilation))
    need(len(rows)==1);return deepcopy(rows[0])


def idle(value):
    return not any(value[k] for k in ('timers','unknownTimers','unknownActivity','evaluating','signalCallbacks',
        'timerCallbacks','unknownSignalCallbacks','unknownTimerCallbacks'))


def input_original(original,binding):
    exact(original,{'createInputVersion','action','controlId','controlToken','scope'});scope(original['scope'])
    need(type(original['createInputVersion']) is int and original['createInputVersion']==1
        and original['action'] in ('activate','replace','select-index','scroll')
        and control_id(original['controlId']) and original['controlId']!='create.page' and nonce(original['controlToken'])
        and original['scope']['instance']==binding['sessionId']
        and original['scope']['processId']==int(binding['processIdentity'].split(':')[0]))


class WorkJournal:
    """Original raw checkpoints + latest frame, retaining membership transitions.

    Completed counter history need not be duplicated at every poll. A selected
    input baseline and each real membership transition remain original frames;
    the latest actual native frame retains all append-only compilation/activity
    records. Replaying these originals reconstructs the actual retired-ID set.
    """
    def __init__(self,native,store,binding):
        self.native,self.store,self.binding=native,store,deepcopy(context(binding));self.previous=store.read();self.last_raw=None
        original=native.original
        def capture():
            self.last_raw=original();return self.last_raw
        native.original=capture
        if self.previous is not None:
            rows=self.check(self.previous);native.restore([decode(row['raw']) for row in rows])
    def check(self,value):
        exact(value,{'schemaVersion','binding','frames','lastPinned'})
        need(type(value['schemaVersion']) is int and value['schemaVersion']==WORK_VERSION and context(value['binding'])==self.binding
            and type(value['lastPinned']) is bool)
        rows=unpack(value['frames']);need(1<=len(rows)<=64)
        for row in rows:
            exact(row,{'raw','sha256'});need(type(row['raw']) is str and len(row['raw'].encode())<=262144
                and hashlib.sha256(row['raw'].encode()).hexdigest()==row['sha256'])
        return rows
    def state(self):
        value=self.store.read();need(value==self.previous);return value
    def read(self,manager):
        before=self.state();rows=[] if before is None else self.check(before)
        value=self.native.read(manager,0 if self.native.last is None else self.native.last['sequence'])
        need(decode(self.last_raw)==value)
        record=dict(raw=self.last_raw,sha256=hashlib.sha256(self.last_raw.encode()).hexdigest())
        if rows:
            old=decode(rows[-1]['raw'])
            retain=before['lastPinned'] or self.membership(old)!=self.membership(value)
            if not retain:rows.pop()
        rows.append(record);need(len(rows)<=64)
        state=dict(schemaVersion=WORK_VERSION,binding=self.binding,frames=pack(rows),lastPinned=False);self.check(state)
        self.store.write(state,before);self.previous=state;return value
    @staticmethod
    def membership(packet):
        value=members(packet['source']);value['managers']=sorted(value['managers'],key=lambda r:r['instance']);return value
    def pin(self):
        previous=self.state();need(previous is not None);rows=self.check(previous)
        current=previous|dict(lastPinned=True);self.store.write(current,previous);self.previous=current
        return rows[-1]['sha256']
    def lookup(self,digest):
        rows=self.check(self.state());found=[r for r in rows if r['sha256']==digest];need(len(found)==1)
        return decode(found[0]['raw'])
    def retire(self):
        self.store.discard(self.state());self.previous=None


class OwnedCreateModels:
    def __init__(self,store,binding,controls,entities,callbacks,work,*,pin=None,monotonic,sleep):
        self.store,self.binding,self.controls=store,deepcopy(context(binding)),controls
        self.entities,self.callbacks,self.work=entities,callbacks,work
        self.pin=deepcopy(source_pin() if pin is None else pin);exact(self.pin,{'encoding','codeUnits','sha256'})
        self.monotonic,self.sleep,self.clock=monotonic,sleep,None;self.previous=store.read()
        if self.previous is not None:self.validate(self.previous)
    def validate(self,value):
        exact(value,{'schemaVersion','binding','runId','fixtureUrl','sourcePin','manager','compilation','steps','pending','lastInput','inputCount'})
        version=value['schemaVersion']
        need(type(version) is int and version in (1,VERSION) and context(value['binding'])==self.binding
            and value['sourcePin']==self.pin and type(value['steps']) is list and 1<=len(value['steps'])<=2
            and integer(value['inputCount'],0,4096))
        identifier(value['runId']);tickets=[]
        for step in value['steps']:
            exact(step,{'ticket','resource','url','before','beforeWork','submitted','configureAttempted','attempted','entityId','lifetime','outcome'}|({'texture'} if version==2 else set()))
            arguments('feature.create.act',dict(contractVersion=CONTRACT,runId=value['runId'],ticket=step['ticket'],
                fixtureUrl=value['fixtureUrl'],verb='model-create',inputs={'resource':step['resource']}))
            if step['lifetime'] is not None:
                exact(step['lifetime'],{'id','instance','firstObservedEpochMs','alive','inTree'})
                need(step['lifetime']['id']==step['entityId'] and nonce(step['lifetime']['instance'])
                    and integer(step['lifetime']['firstObservedEpochMs'],1) and step['lifetime']['alive'] is True and step['lifetime']['inTree'] is True)
            need(step['resource'] in RESOURCES and step['url']==value['fixtureUrl']+'tickets/'+step['ticket']+'/'+step['resource']
                and type(step['submitted']) is bool and type(step['configureAttempted']) is bool
                and (not step['configureAttempted'] or step['submitted'])
                and step['attempted'] in (['create'],['create','delete'],['create','texture'],['create','texture','delete'])
                and step['outcome'] in ('reserved','created','texture-property-applied','deleted')
                and (step['entityId'] is None)==(step['lifetime'] is None)
                and (step['entityId'] is None or nonce(step['entityId'])))
            self.entities.reader.validate(step['before'],step['before']['requestId'],self.entities.reader.pid,step['before']['capturedEpochMs'])
            baseline=self.work.lookup(step['beforeWork']);work_scope(baseline,value['compilation'])
            need(baseline['source']['manager']==value['manager']);tickets.append(step['ticket'])
            texture=step.get('texture')
            if version==1:need(step['attempted'] in (['create'],['create','delete']) and step['outcome'] in ('reserved','created','deleted'))
            if texture is None:need('texture' not in step['attempted'] and step['outcome']!='texture-property-applied')
            if texture is not None:
                exact(texture,{'ticket','url','slot','before','beforeWork','submitted','applied'})
                arguments('feature.create.act',dict(contractVersion=CONTRACT,runId=value['runId'],ticket=texture['ticket'],
                    fixtureUrl=value['fixtureUrl'],verb='apply-texture',inputs={'resource':'checker.png'}))
                need(texture['slot']=='checker.png' and texture['url']==value['fixtureUrl']+'tickets/'+texture['ticket']+'/checker.png'
                    and type(texture['submitted']) is bool and type(texture['applied']) is bool
                    and ('texture' in step['attempted']) and step['resource']=='gltf-bundle/main.gltf'
                    and step['entityId'] is not None and step['configureAttempted']
                    and (not texture['applied'] or texture['submitted']))
                self.entities.reader.validate(texture['before'],texture['before']['requestId'],self.entities.reader.pid,texture['before']['capturedEpochMs'])
                originals=texture['before']['source']['entities'];need(len(originals)==1 and originals[0]['id']==step['entityId']
                    and texture['before']['capturedEpochMs']>=step['before']['capturedEpochMs']
                    and texture['before']['requestId']!=step['before']['requestId']
                    and originals[0]['textures']!=self.texture_text(texture))
                work_scope(self.work.lookup(texture['beforeWork']),value['compilation']);tickets.append(texture['ticket'])
        need(tickets==list(dict.fromkeys(tickets)) and value['manager']['assigned']
            and (value['pending'] is None or value['pending']==dict(ticket=value['steps'][-1]['ticket'],operation='create')
                or value['pending']==dict(ticket=value['steps'][-1]['ticket'],operation='delete')
                or value['pending']==dict(ticket=value['steps'][-1]['ticket'],operation='texture') and value['steps'][-1].get('texture') is not None)
            and (value['lastInput'] is None)==(value['inputCount']==0))
        if value['lastInput'] is not None:input_original(value['lastInput'],self.binding)
    def state(self):
        value=self.store.read();need(value is not None and value==self.previous);self.validate(value);return value
    def write(self,value):
        value=deepcopy(value)
        if value['schemaVersion']==1:
            value['schemaVersion']=VERSION
            for step in value['steps']:step.setdefault('texture',None)
        self.validate(value);self.store.write(value,self.previous);self.previous=deepcopy(value)
    def update(self,**changes):
        value=self.state();value['steps'][-1].update(deepcopy(changes));self.write(value)
    def now(self):
        value=self.monotonic();need(type(value) in (int,float) and math.isfinite(value) and value>=0 and (self.clock is None or value>=self.clock))
        self.clock=value;return value
    def intent(self,original):
        value=self.state();need(value['pending'] is not None and value['inputCount']<4096)
        input_original(original,self.binding)
        if original['controlId']=='create.new-model':
            need(value['pending']['operation']=='create' and not value['steps'][-1]['submitted'])
            value['steps'][-1]['submitted']=True
        if original['controlId']=='create.apply-typed':
            need(value['pending']['operation']=='texture' and not value['steps'][-1]['texture']['submitted'])
            value['steps'][-1]['texture']['submitted']=True
        value.update(lastInput=deepcopy(original),inputCount=value['inputCount']+1);self.write(value)
    def capture(self,initial=False):
        callback=self.callbacks.read();manager,compilation=selected(callback,self.pin)
        if not initial:
            value=self.state();need(manager==value['manager'] and compilation==value['compilation'])
        entities=self.entities.read();work=self.work.read(manager['instance']);measured=work_scope(work,compilation)
        need(work['source']['manager']==manager and entities['instance']==work['instance']
            and entities['processId']==work['processId']==int(self.binding['processIdentity'].split(':')[0])
            and entities['source']['createEntitySourceVersion'] in (3,4,5))
        epoch=self.work.native.clock_ms()
        for frame in [entities,work]+([callback] if callback is not None else []):
            fresh(frame['capturedEpochMs'],epoch);need(frame['instance']==work['instance'] and frame['processId']==work['processId'])
        return dict(entities=entities,callbacks=callback,work=work,scope=measured,manager=manager,compilation=compilation)
    def prepare(self):
        start=self.now()
        for attempt in range(17):
            actual=self.capture(initial=self.previous is None)
            need(entities_retired(actual['entities']['source']))
            if idle(actual['scope']) and not active_callbacks(actual['callbacks']):return actual
            need(self.now()-start<3 and attempt<16);self.sleep(.2)
        need(False)
    def create(self,run,ticket,fixture_url,resource):
        identifier(run);identifier(ticket);need(resource in RESOURCES and self.entities.reader.run==run)
        arguments('feature.create.act',dict(contractVersion=CONTRACT,runId=run,ticket=ticket,fixtureUrl=fixture_url,
            verb='model-create',inputs={'resource':resource}))
        actual=self.prepare();source=actual['entities']['source']
        need(source['domainConnected'] and source['domainId'] and source['sessionId'] and (source['canRez'] or source['canRezTmp']))
        controls=self.controls(self.intent);need(controls.page(controls.capture())['selectedIds']==[])
        if self.previous is None:
            value=dict(schemaVersion=VERSION,binding=self.binding,runId=run,fixtureUrl=fixture_url,sourcePin=self.pin,
                manager=actual['manager'],compilation=actual['compilation'],steps=[],pending=None,lastInput=None,inputCount=0)
        else:
            value=self.state();need(value['runId']==run and value['fixtureUrl']==fixture_url and len(value['steps'])<2
                and value['pending'] is None and value['steps'][-1]['outcome']=='deleted' and ticket not in [s['ticket'] for s in value['steps']])
            for step in value['steps']:OwnedCreatePicker.same_scene(step['before'],actual['entities'])
        step=dict(ticket=ticket,resource=resource,url=fixture_url+'tickets/'+ticket+'/'+resource,before=actual['entities'],
            beforeWork=self.work.pin(),submitted=False,configureAttempted=False,attempted=['create'],entityId=None,lifetime=None,outcome='reserved',texture=None)
        value['steps'].append(step);value['pending']=dict(ticket=ticket,operation='create');self.write(value)
        controls.tab(0);controls.choose('create.host',0);controls.replace('create.resource',step['url'])
        controls.reveal('create.new-model');controls.input('create.new-model')
        self.quiet('create')
        # Only the original invocation may issue these first normal edits.
        # Recovery observes desired properties and never repeats uncertain input.
        self.update(configureAttempted=True)
        controls.name_entity('e2e-'+run+'-model')
        for axis in 'xyz':controls.replace('create.field.dimensions.'+axis,'1.0')
        controls.reveal('create.apply');controls.input('create.apply')
        return self.reconcile()
    def actual_entity(self,actual,allow_absent=False):
        value=self.state();step=value['steps'][-1];frame=actual['entities'];OwnedCreatePicker.same_scene(step['before'],frame)
        source=frame['source'];need(len(source['entities'])<=1)
        if not source['entities']:
            need(allow_absent or step['entityId'] is None);return None
        row=source['entities'][0];need(step['submitted'] and row['type']=='Model' and row['hostType']=='domain' and row['modelUrl']==step['url']
            and row['parentId'] is None and not row['locked'] and row['lastEditedEpochUs']>=step['before']['capturedEpochMs']*1000)
        life=[r for r in source['entityLifetimes'] if r['id']==row['id']];need(len(life)==1 and life[0]['inTree'] and life[0]['alive'])
        if step['entityId'] is None:
            old={r['id'] for r in step['before']['source']['entities']}|set(step['before']['source']['absentIds'])
            need(row['id'] not in old and life[0]['firstObservedEpochMs']>=step['before']['capturedEpochMs'])
            self.update(entityId=row['id'],lifetime=life[0])
        else:need(row['id']==step['entityId'] and all(life[0][k]==step['lifetime'][k] for k in ('id','instance','firstObservedEpochMs')))
        return row
    def extra_ready(self,actual,operation,row):return True
    def extra_clocks(self,actual):return ()
    def extra_stable(self,actual):return None
    def extra_release_ready(self,actual):return True
    def original_readers(self):return (self.entities,self.callbacks,self.work)
    def quiet(self,operation,*,created=False):
        start=self.now();quiet=None;clocks=None;stable=None;previous_ui=None
        for attempt in range(103):
            actual=self.capture();row=self.actual_entity(actual,allow_absent=operation=='delete');value=self.state();step=value['steps'][-1]
            controls=self.controls(self.intent);ui=controls.capture();page=controls.page(ui);need(not page['statusError'])
            need(ui['scope']['instance']==self.binding['sessionId'] and ui['scope']['processId']==int(self.binding['processIdentity'].split(':')[0]))
            if previous_ui is not None:
                need(all(ui['scope'][k]==previous_ui[k] for k in ('instance','generation','processId','sequence'))
                    and ui['scope']['elapsedMs']>=previous_ui['elapsedMs'])
            previous_ui=deepcopy(ui['scope'])
            baseline=work_scope(self.work.lookup(step['beforeWork']),value['compilation']);current=actual['scope']
            ready=idle(current) and not active_callbacks(actual['callbacks'])
            if operation in ('create','texture'):
                ready=ready and row is not None and row['visible'] and row['visuallyReady'] and row['renderInfo']['vertices']>0
                ready=ready and current['timerRegistrations']>baseline['timerRegistrations'] and current['timerInvocations']>baseline['timerInvocations']
                if row is not None:ready=ready and page['selectedIds']==[row['id']]
                if created or operation=='texture':ready=ready and row['name']=='e2e-'+value['runId']+'-model' and row['dimensions']==[1,1,1]
                if operation=='texture':
                    texture=step['texture'];before=texture['before']['source']['entities'][0]
                    if row is not None:
                        need(all(row[k]==before[k] for k in ('id','name','type','hostType','modelUrl','parentId','locked','position','rotation','dimensions','textureNames','naturalDimensions')))
                        ready=ready and texture['submitted'] and row['textures']==self.texture_text(texture)
                        ready=ready and row['lastEditedEpochUs']>=texture['before']['capturedEpochMs']*1000
            else:ready=ready and entities_retired(actual['entities']['source']) and page['selectedIds']==[]
            extra=self.extra_ready(actual,operation,row);ready=ready and extra
            now=self.now();epochs=(actual['entities']['capturedEpochMs'],actual['work']['source']['work']['capturedEpochMs'],ui['scope']['elapsedMs'])+self.extra_clocks(actual)
            observed=(deepcopy(row),current['timerInvocations'],current['timerRegistrations'],self.extra_stable(actual))
            if ready and (stable is None or stable==observed):
                quiet=now if quiet is None else quiet;clocks=epochs if clocks is None else clocks;stable=observed
                if now-quiet>=3 and all(b-a>=3000 for a,b in zip(clocks,epochs)):return actual
            else:quiet=None;clocks=None;stable=None
            need(now-start<20 and attempt<102);self.sleep(.2)
        raise NativeUIError('Original Create Model work, effect or object lifetime did not settle')
    def reconcile(self):
        value=self.state();need(value['pending'] is not None);operation=value['pending']['operation'];step=value['steps'][-1]
        if operation=='create':
            need(step['configureAttempted']);self.quiet('create',created=True)
        elif operation=='texture':
            need(step['texture']['submitted']);self.quiet('texture')
        else:self.quiet('delete')
        value=self.state();value['steps'][-1]['outcome']={'create':'created','texture':'texture-property-applied','delete':'deleted'}[operation]
        if operation=='texture':value['steps'][-1]['texture']['applied']=True
        value['pending']=None;self.write(value)
        return {'performed':True}
    @staticmethod
    def texture_text(texture):return json.dumps({texture['slot']:texture['url']},sort_keys=True,separators=(',',':'))
    def apply_texture(self,run,ticket,fixture_url,resource):
        arguments('feature.create.act',dict(contractVersion=CONTRACT,runId=run,ticket=ticket,fixtureUrl=fixture_url,
            verb='apply-texture',inputs={'resource':resource}))
        value=self.state();step=value['steps'][-1]
        need(run==value['runId'] and fixture_url==value['fixtureUrl'] and value['pending'] is None and step['outcome']=='created'
            and step.get('texture') is None and step['resource']=='gltf-bundle/main.gltf'
            and ticket not in [s['ticket'] for s in value['steps']]
            and not any(s.get('texture') is not None and s['texture']['ticket']==ticket for s in value['steps']))
        actual=self.quiet('create',created=True);row=self.actual_entity(actual);need(row is not None)
        need('checker.png' in row['textureNames'] and row['textureNames']['checker.png']==step['url'].rsplit('/',1)[0]+'/textures/checker.png')
        texture=dict(ticket=ticket,url=fixture_url+'tickets/'+ticket+'/checker.png',slot='checker.png',before=actual['entities'],
            beforeWork=self.work.pin(),submitted=False,applied=False)
        need(row['textures']!=self.texture_text(texture))
        value=self.state();value['steps'][-1].update(texture=texture,attempted=step['attempted']+['texture'])
        value['pending']=dict(ticket=step['ticket'],operation='texture');self.write(value)
        controls=self.controls(self.intent);controls.tab(2);controls.replace('create.filter','textures')
        controls.replace('create.textures',self.texture_text(texture));controls.reveal('create.apply-typed');controls.input('create.apply-typed')
        return self.reconcile()
    def delete(self):
        value=self.state();step=value['steps'][-1]
        need('delete' not in step['attempted'] and (value['pending'] is None and step['outcome'] in ('created','texture-property-applied')
            or value['pending'] in (dict(ticket=step['ticket'],operation='create'),dict(ticket=step['ticket'],operation='texture'))))
        actual=self.capture();row=self.actual_entity(actual);need(row is not None)
        value=self.state();value['steps'][-1]['attempted'].append('delete');value['pending']=dict(ticket=step['ticket'],operation='delete');self.write(value)
        controls=self.controls(self.intent);controls.select_entity(row['id']);controls.delete_entity();return self.reconcile()
    def release(self):
        value=self.state();need(value['pending'] is None and all(s['outcome']=='deleted' for s in value['steps']))
        actual=self.quiet('delete');need(self.extra_release_ready(actual));self.store.discard(value);self.previous=None
        for reader in self.original_readers():reader.retire()
        return {'performed':True}

    def release_observations(self):
        """Retire acquisition-only journals under fresh joint original proof."""
        need(self.previous is None and self.store.read() is None)
        started=self.now();quiet=None;epochs=None;previous_ui=None
        for attempt in range(68):
            actual=self.capture(initial=True);controls=self.controls(self.intent);ui=controls.capture();page=controls.page(ui)
            need(ui['scope']['instance']==self.binding['sessionId'] and ui['scope']['processId']==int(self.binding['processIdentity'].split(':')[0]))
            if previous_ui is not None:
                need(all(ui['scope'][k]==previous_ui[k] for k in ('instance','generation','processId','sequence'))
                    and ui['scope']['elapsedMs']>=previous_ui['elapsedMs'])
            previous_ui=deepcopy(ui['scope'])
            ready=(entities_retired(actual['entities']['source']) and idle(actual['scope'])
                and not active_callbacks(actual['callbacks']) and not page['selectedIds'] and not page['statusError'] and self.extra_release_ready(actual))
            now=self.now();clocks=(actual['entities']['capturedEpochMs'],actual['work']['source']['work']['capturedEpochMs'],ui['scope']['elapsedMs'])+self.extra_clocks(actual)
            if ready:
                quiet=now if quiet is None else quiet;epochs=clocks if epochs is None else epochs
                if now-quiet>=3 and all(b-a>=3000 for a,b in zip(epochs,clocks)):
                    for reader in self.original_readers():reader.retire()
                    return {'performed':True}
            else:quiet=None;epochs=None
            need(now-started<13 and attempt<67);self.sleep(.2)
        need(False)


class PicoCreateModels:
    """Private candidate-bound composition, without a full Create capability."""
    def __init__(self,adapter,target,run,*,coordinator=None):
        from adapters.script_journey.lock import ScriptSourceLock
        from adapters.pico4.create_management import configuration
        identifier(run);need(configuration(os.environ) is not None)
        self.adapter,self.target,self.run=adapter,target,run
        self.key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
        self.parent=adapter.pico_configuration[1]
        self.coordinator=coordinator
        self.lock=ScriptSourceLock(self.parent/('normal-create-sources-'+self.key+'.lock')) if coordinator is None else coordinator.lock
    def store(self,role):
        from adapters.normal_feature_state import PrivateFeatureState
        return PrivateFeatureState(self.parent/('create-models-'+role+'-'+self.key+'-'+self.run+'.json'))
    @staticmethod
    def journals(adapter,target):
        from adapters.normal_feature_state import PrivateFeatureState
        if adapter.pico_configuration is None:return []
        parent=adapter.pico_configuration[1];key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
        PrivateFeatureState(parent/'create-models-parent-check.json')._parent();found=[]
        for path in parent.glob('create-models-*-'+key+'-*.json'):
            need(re.fullmatch(r'create-models-(?:owner|callbacks|entities|work|resources|resource-join)-'+key+r'-[0-9a-f]{32}\.json',path.name))
            if PrivateFeatureState(path).read() is not None:found.append(path)
        return found
    @staticmethod
    def owned_target(adapter,target):return bool(PicoCreateModels.journals(adapter,target))
    def owned(self):return any(self.store(role).read() is not None for role in ('owner','callbacks','entities','work','resources','resource-join'))
    def flow(self):
        from adapters.normal_feature_state import PrivateFeatureState
        self.lock.assert_held()
        allowed={self.store(role).path for role in ('owner','callbacks','entities','work','resources','resource-join')}
        need(set(self.journals(self.adapter,self.target))<=allowed)
        need(not self.adapter._create_management(self.target).owned())
        if self.coordinator is None:
            from adapters.pico4.create_journey import PicoCreateJourney
            need(not PicoCreateJourney.owned_target(self.adapter,self.target) and not self.adapter._create_picker_owned(self.target))
        else:self.coordinator.authorize('models',self.adapter,self.target,self.run)
        regular,_ui=self.adapter._script_paths(self.target);need(PrivateFeatureState(regular).read() is None)
        ui,_observe,binding=self.adapter._script_runtime(self.target)
        if self.coordinator is not None:self.coordinator.authorize('models',self.adapter,self.target,self.run,binding)
        entities=OriginalReader(self.adapter._create_entity_observer(self.target,self.run),self.store('entities'),binding)
        callbacks=OriginalReader(self.adapter._create_callback_observer(self.target),self.store('callbacks'),binding)
        work=WorkJournal(self.adapter._script_work(self.target),self.store('work'),binding)
        from adapters.pico4.create_model_resource_join import ResourceJoinedCreateModels
        resources=OriginalReader(self.adapter._create_model_resources_observer(self.target,self.run),self.store('resources'),binding)
        return ResourceJoinedCreateModels(self.store('owner'),binding,lambda intent:self.adapter._create_controls(self.target,intent) if self.coordinator is None else self.coordinator.controls(self.coordinator.wrap_intent('models',intent)),
            entities,callbacks,work,resources=resources,join_store=self.store('resource-join'),
            monotonic=ui.monotonic,sleep=ui.sleep)
    def invoke(self,operation,*,ticket=None,fixture_url=None,resource=None):
        need(operation in ('create','texture','delete','reconcile','release'))
        with self.lock.held():
            flow=self.flow()
            if operation=='create':return flow.create(self.run,ticket,fixture_url,resource)
            if operation=='texture':return flow.apply_texture(self.run,ticket,fixture_url,resource)
            need(ticket is None and fixture_url is None and resource is None)
            if operation=='release' and flow.previous is None:return flow.release_observations()
            return getattr(flow,operation)()
