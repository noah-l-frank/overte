"""Create parent primitive operations on independent native insertion/volume sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import hashlib
from adapters.native_feature_observation import decode
from adapters.script_journey.history import pack,unpack
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_entities import validate as validate_entities,voxel_source,retired
from adapters.pico4.create_models import idle
from adapters.pico4.create_callbacks import active
from adapters.token_create_ui import nonce

CANONICAL=bytes(255 if 2<=x<6 and 2<=y<6 and 2<=z<6 else 0 for z in range(8) for y in range(8) for x in range(8))
ATTEMPTS={'open','configure','create','return','properties','delete-prepare','delete','properties-apply','cancel'}


def validate_steps(value):
    need(type(value) is list and len(value)<=2)
    for step in value:
        exact(step,{'ticket','before','position','attempted','entityId','lifetime','outcome','configured','pageId','deleteTicket','createOriginal','creationProof'})
        packet=step['before'];validate_entities(packet,packet['requestId'],packet['processId'],packet['capturedEpochMs'],packet['source']['runId'])
        need(nonce(step['ticket']) and packet['source']['createEntitySourceVersion'] in (4,5) and retired(packet['source'])
            and type(step['position']) is list and len(step['position'])==3 and all(type(v) in (float,int) and math.isfinite(v) and abs(v)<=1e6 for v in step['position'])
            and type(step['attempted']) is list and len(set(step['attempted']))==len(step['attempted']) and set(step['attempted'])<=ATTEMPTS
            and type(step['configured']) is bool and (step['pageId'] is None or nonce(step['pageId']))
            and (step['deleteTicket'] is None or nonce(step['deleteTicket']))
            and step['outcome'] in ('creating','created','deleted') and (step['entityId'] is None)==(step['lifetime'] is None))
        if step['createOriginal'] is not None:
            original=step['createOriginal'];exact(original,{'createExtraInputVersion','action','controlId','controlToken','scope'})
            from adapters.token_create_ui import scope
            scope(original['scope']);need(type(original['createExtraInputVersion']) is int and original['createExtraInputVersion']==1
                and original['action']=='activate' and original['controlId']=='create-extra.polyvox.add' and nonce(original['controlToken']))
        if step['entityId'] is not None:
            life=step['lifetime'];exact(life,{'id','instance','firstObservedEpochMs','alive','inTree'})
            need(life['id']==step['entityId'] and nonce(life['instance']) and integer(life['firstObservedEpochMs'],1)
                and life['alive'] is True and life['inTree'] is True)
        if step['creationProof'] is not None:
            proof=step['creationProof'];exact(proof,{'native','ui'})
            records=unpack(proof['native']);need([r['role'] for r in records]==['entities','callbacks','work'])
            packets={}
            for original in records:
                exact(original,{'role','raw','sha256'});need(type(original['raw']) is str and hashlib.sha256(original['raw'].encode()).hexdigest()==original['sha256'])
                packet=decode(original['raw']);packets[original['role']]=packet;pid=step['before']['processId']
                need(packet['processId']==pid and packet['instance']==step['before']['instance'])
                if original['role']=='entities':validate_entities(packet,packet['requestId'],pid,packet['capturedEpochMs'],step['before']['source']['runId'])
                elif original['role']=='callbacks':
                    from adapters.pico4.create_callbacks import validate
                    validate(packet,packet['requestId'],pid,packet['capturedEpochMs'])
                else:
                    from adapters.native_script_work import validate
                    request=dict(schemaVersion=1,commandId=packet['requestId'],action='feature-script-work-observe',managerInstance=packet['source']['manager']['instance'])
                    validate(packet,request,pid,packet['capturedEpochMs'])
            from adapters.pico4.navigation import validate_snapshot
            validate_snapshot(proof['ui'],step['before']['processId'],proof['ui']['updatedEpochMs'])
            actual=packets['entities']['source']['entities'];need(len(actual)==1 and actual[0]['id']==step['entityId'] and voxel_source(actual[0]['voxels'])==CANONICAL)
        if step['outcome']=='created':need(step['configured'] and step['entityId'] is not None and step['creationProof'] is not None)


class CreatePrimitives:
    def primitive_step(self):
        steps=self.state().get('primitives',[]);need(bool(steps));return steps[-1]
    def primitive_update(self,**changes):
        steps=deepcopy(self.state()['primitives']);steps[-1].update(deepcopy(changes));self.mark(primitives=steps)
    def primitive_attempt(self,kind):
        step=self.primitive_step();need(kind in ATTEMPTS and kind not in step['attempted'])
        self.primitive_update(attempted=step['attempted']+[kind])
    def primitive_extra(self):
        return self.adapter._create_extra_controls(self.target,lambda original:self.record_input('primitive',original),before_send=self.dispatch_admission)
    def primitive_row(self,actual,*,absent=False):
        step=self.primitive_step();before=step['before'];packet=actual['entities'];a,b=before['source'],packet['source']
        from adapters.pico4.create_picker_owner import OwnedCreatePicker
        OwnedCreatePicker.same_scene(before,packet);need(b['createEntitySourceVersion'] in (4,5))
        old=a['localCreations'];new=b['localCreations'];need(old['armedAfterSequence']==new['armedAfterSequence']
            and new['events'][:len(old['events'])]==old['events'])
        events=new['events'][len(old['events']):];rows=b['entities']
        if not events:
            need(not rows and step['entityId'] is None);return None
        need(len(events)==1);event=events[0]
        need('create' in step['attempted'] and step['createOriginal'] is not None and event['type']=='PolyVox' and event['hostType']=='domain'
            and event['sessionId']==b['sessionId'] and event['observedEpochMs']>=before['capturedEpochMs']
            and event['createdEpochUs']>=before['capturedEpochMs']*1000)
        identifier=event['id'];need(step['entityId'] in (None,identifier))
        if not rows:
            need(absent and identifier in b['absentIds'] and step['entityId']==identifier);return None
        need(len(rows)==1);row=rows[0];need(row['id']==identifier and row['type']=='PolyVox' and row['hostType']=='domain'
            and row['createdEpochUs']==event['createdEpochUs'] and row['lastEditedBy']==b['sessionId']
            and row['parentId'] is None and not row['locked'])
        lives=[r for r in b['entityLifetimes'] if r['id']==identifier];need(len(lives)==1);life=lives[0]
        need(life['alive'] and life['inTree'] and life['firstObservedEpochMs']>=before['capturedEpochMs'])
        if step['entityId'] is None:self.primitive_update(entityId=identifier,lifetime=life)
        else:need(all(life[k]==step['lifetime'][k] for k in ('id','instance','firstObservedEpochMs')))
        return row
    def primitive_proof(self,actual):
        records=[]
        for role in ('entities','callbacks','work'):
            original=self.readers[role]
            raw=original.last_raw if role=='work' else original.reader.last_raw
            need(type(raw) is str and decode(raw)==actual[role])
            records.append(dict(role=role,raw=raw,sha256=hashlib.sha256(raw.encode()).hexdigest()))
        return dict(native=pack(records),ui=deepcopy(actual['ui']))
    def primitive_final(self,actual):
        value=self.state();call=value['calls'][-1]
        if call['verb']=='voxel-create':
            step=self.primitive_step();need(step['outcome']=='created' and step['creationProof'] is not None)
            records=unpack(step['creationProof']['native']);original=decode(records[0]['raw'])
            need(actual['entities']['source']['entities']==original['source']['entities'])
            row=self.primitive_row(actual);need(row is not None)
        elif call['verb']=='delete-owned' and value.get('primitives') and value['primitives'][-1]['deleteTicket']==call['ticket']:
            need(self.primitive_step()['outcome']=='deleted' and self.primitive_row(actual,absent=True) is None and retired(actual['entities']['source']))

    def primitive_settle(self,operation):
        ui,_binding=self.runtime();started=ui.monotonic();quiet=None;clocks=None;stable=None
        for attempt in range(103):
            actual=self.sample();row=self.primitive_row(actual,absent=operation=='delete');step=self.primitive_step()
            ready=idle(actual['scope']) and not active(actual['callbacks'])
            if operation=='create':
                if row is None:ready=False
                else:
                    values=voxel_source(row['voxels']);ready=ready and row['voxels']['ready'] and values==CANONICAL
                    ready=ready and row['visible'] and row['visuallyReady'] and row['voxels']['meshReady'] and row['voxels']['vertices']>0 and row['voxels']['indices']>0
                    ready=ready and row['name']=='e2e-'+self.run+'-voxel' and row['dimensions']==[1,1,1]
                    ready=ready and all(abs(a-b)<=1e-5 for a,b in zip(row['position'],step['position']))
                    page=next((r for r in actual['ui']['controls'] if r['id']=='create.page'),None)
                    ready=ready and step['configured'] and page is not None and page['selectedIds']==[row['id']] and not page['statusError']
            else:ready=ready and row is None and retired(actual['entities']['source']) and (step['createOriginal'] is None or step['entityId'] is not None)
            current=ui.monotonic();epochs=(actual['entities']['capturedEpochMs'],actual['work']['source']['work']['capturedEpochMs'],actual['ui']['elapsedMs'])
            observed=deepcopy((row,actual['scope']['timerRegistrations'],actual['scope']['timerInvocations']))
            if ready and (stable is None or stable==observed):
                quiet=current if quiet is None else quiet;clocks=epochs if clocks is None else clocks;stable=observed
                if current-quiet>=3 and all(b-a>=3000 for a,b in zip(clocks,epochs)):
                    self.phase_fence();self.fresh_sample(actual);return actual
            else:quiet=None;clocks=None;stable=None
            need(current-started<20 and attempt<102);ui.sleep(.2)
        raise NativeUIError('Original Create primitive effect or lifetime did not settle')
    def primitive_return(self):
        self.primitive_attempt('return')
        # Original fromQml pops the tablet stack before handling DialogAdd.
        # Only observe that ordinary route; never pop or load a page here.
        extra=self.primitive_extra();extra.wait(lambda v:extra.row(v,'create-extra.polyvox.page',ready=False) is None)
        self.controls().wait_create()
    def primitive_create(self):
        actual=self.sample();before=actual['entities'];source=before['source'];need(source['createEntitySourceVersion'] in (4,5) and retired(source))
        ui=actual['ui'];need(ui.get('createExtraControlsVersion')==1 and self.state()['baselineExtra'] is not None)
        steps=self.state()['primitives'];need(not steps or steps[-1]['outcome']=='deleted')
        q=source['avatarRotation'];x,y,z,w=q
        # Rotate the actual avatar forward vector; no requested controller pose
        # or nominal spawn offset is passed off as an observed source.
        forward=(-4*(x*z+w*y),-4*(y*z-w*x),-2*(1-2*(x*x+y*y)))
        position=[round(a+b,8) for a,b in zip(source['scan']['center'],forward)]
        step=dict(ticket=self.state()['pending'],before=deepcopy(before),position=position,attempted=[],entityId=None,lifetime=None,
            outcome='creating',configured=False,pageId=None,deleteTicket=None,createOriginal=None,creationProof=None)
        self.mark(primitives=steps+[step]);controls=self.controls()
        self.primitive_attempt('open');controls.tab(0);extra=self.primitive_extra();opened=extra.open_polyvox()
        page=extra.row(opened,'create-extra.polyvox.page',ready=False);need(page is not None);self.primitive_update(pageId=page['pageId'])
        self.sample();self.primitive_attempt('configure');extra.configure_polyvox()
        self.primitive_attempt('create');extra.input('create-extra.polyvox.add')
        # Capture the original successful local insertion before normal naming.
        ui,_binding=self.runtime();started=ui.monotonic()
        for attempt in range(67):
            actual=self.sample();row=self.primitive_row(actual)
            if row is not None:break
            need(ui.monotonic()-started<10 and attempt<66);ui.sleep(.15)
        self.primitive_return();controls=self.controls()
        self.primitive_attempt('properties');controls.select_entity(self.primitive_step()['entityId']);controls.name_entity('e2e-'+self.run+'-voxel')
        for axis in 'xyz':controls.replace('create.field.dimensions.'+axis,'1')
        for axis,value in zip('xyz',position):controls.replace('create.field.position.'+axis,str(value))
        controls.reveal('create.apply');self.primitive_attempt('properties-apply');self.primitive_update(configured=True);controls.input('create.apply')
        actual=self.primitive_settle('create');self.primitive_update(outcome='created',creationProof=self.primitive_proof(actual));self.mark(subject='primitive')
    def primitive_delete(self):
        actual=self.sample();row=self.primitive_row(actual,absent=True);step=self.primitive_step()
        # A never-granted Add can receive a distinct normal Cancel. An
        # uncertain granted Add without its native insertion stays unresolved.
        if row is None and step['createOriginal'] is None:
            extra=self.primitive_extra();current=extra.capture();page=extra.row(current,'create-extra.polyvox.page',ready=False)
            if page is not None:
                need('open' in step['attempted'] and 'cancel' not in step['attempted'])
                if step['pageId'] is None:
                    before=self.state()['baselineExtra'];need(before is not None)
                    new=[r for r in current['createExtraUiInventory']['pages'] if r['id'] not in {p['id'] for p in before['pages']} and r['pageAlive']]
                    need(len(new)==1 and new[0]['id']==page['pageId'] and new[0]['firstObservedEpochMs']>=step['before']['capturedEpochMs'])
                    self.primitive_update(pageId=page['pageId']);step=self.primitive_step()
                need(page['pageId']==step['pageId']);self.primitive_attempt('cancel');extra.input('create-extra.polyvox.cancel')
                extra.wait(lambda v:extra.row(v,'create-extra.polyvox.page',ready=False) is None)

        if row is not None and 'delete' not in step['attempted']:
            if step['deleteTicket'] is None:self.primitive_update(deleteTicket=self.state()['phase']['activations'][-1]['ticket'])
            controls=self.controls()
            if 'delete-prepare' not in step['attempted']:
                self.primitive_attempt('delete-prepare')
                if controls.row(controls.capture(),'create.page',enabled=False) is None:
                    self.close_editor();self.open_editor();controls=self.controls()
                controls.select_entity(row['id'])
            need(controls.page(controls.capture())['selectedIds']==[row['id']])
            self.primitive_attempt('delete');controls.delete_entity()
        self.primitive_settle('delete');self.primitive_update(outcome='deleted');self.mark(subject=None)
    def primitive_reconcile(self,operation):
        if operation=='create':
            need(self.primitive_step()['configured']);actual=self.primitive_settle('create');self.primitive_update(outcome='created',creationProof=self.primitive_proof(actual));self.mark(subject='primitive')
        else:self.primitive_settle('delete');self.primitive_update(outcome='deleted');self.mark(subject=None)
