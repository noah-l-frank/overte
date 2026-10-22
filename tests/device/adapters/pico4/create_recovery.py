"""Normal denied Shape and independent Cube insertion/deletion for Create v16."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,need,integer
from adapters.normal_feature_state import context
from adapters.pico4.create_voxel_edit import archive
from adapters.pico4.create_models import idle,input_original
from adapters.pico4.create_callbacks import active
from adapters.pico4.create_entities import retired
from adapters.token_create_ui import nonce

DENIED='Invalid entity type, properties or creation permission.'
ATTEMPTS={'tab','host','shape','create','name','delete-prepare','delete'}


def bridge_pins(packet,manager):
    managers=[r for r in packet['source']['managers'] if r['membership']==manager];need(len(managers)==1);result={}
    for name in ('nativeCreateBridge.js','picoQmlMessageValidation.js'):
        relative='system/create/modules/'+name
        code=(Path(__file__).resolve().parents[4]/('scripts/'+relative)).read_text().encode('utf-16le')
        expected=dict(encoding='utf-16le-code-units',codeUnits=len(code)//2,sha256=hashlib.sha256(code).hexdigest())
        matches=[]
        for row in managers[0]['compiled']['compilations']:
            url=urlsplit(row['resourceName'])
            if url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment and url.path.endswith('/'+relative):
                need(all(row[k]==v for k,v in expected.items()));matches.append(row)
        need(len(matches)==1);result[name]=deepcopy(matches[0])
    return result


class CreateRecovery:
    def recovery_state(self):
        value=self.source_store('recovery').read()
        if value is None:
            need(self.previous is None or self.state()['subject']!='recovery');return None
        exact(value,{'createRecoveryVersion','binding','runId','steps'})
        root=self.state();need(type(value['createRecoveryVersion']) is int and value['createRecoveryVersion']==1
            and context(value['binding'])==context(root['binding']) and value['runId']==self.run
            and type(value['steps']) is list and 1<=len(value['steps'])<=4)
        tickets=[]
        for step in value['steps']:
            exact(step,{'ticket','kind','before','pins','attempted','createOriginal','entityId','lifetime','outcome','effect','deleteTicket','deletion'})
            need(nonce(step['ticket']) and step['kind'] in ('denied','cube') and type(step['attempted']) is list
                and len(step['attempted'])==len(set(step['attempted'])) and set(step['attempted'])<=ATTEMPTS
                and step['outcome'] in ('creating','denied','created','deleted','cancelled')
                and (step['entityId'] is None)==(step['lifetime'] is None)
                and (step['deleteTicket'] is None or nonce(step['deleteTicket'])))
            tickets.append(step['ticket']);before=archive(step['before'],root['binding'],self.run)
            native=before['entities'];need(native['source']['createEntitySourceVersion']==6 and retired(native['source']))
            need(step['pins']==bridge_pins(before['callbacks'],root['manager']))
            calls=[r for r in root['calls'] if r['ticket']==step['ticket']]
            need(len(calls)==1 and calls[0]['verb']==('create-denied' if step['kind']=='denied' else 'create-retry'))
            if step['createOriginal'] is not None:
                input_original(step['createOriginal'],root['binding'])
                need('create' in step['attempted'] and step['createOriginal']['controlId']=='create.new-shape' and step['createOriginal']['action']=='activate')
            if step['lifetime'] is not None:
                life=step['lifetime'];exact(life,{'id','instance','firstObservedEpochMs','alive','inTree'})
                need(life['id']==step['entityId'] and nonce(life['id']) and nonce(life['instance'])
                    and integer(life['firstObservedEpochMs'],native['capturedEpochMs']) and life['alive'] is True and life['inTree'] is True)
            for field in ('effect','deletion'):
                if step[field] is not None:
                    proof=archive(step[field],root['binding'],self.run)
                    need(proof['entities']['instance']==native['instance']
                        and proof['entities']['source']['domainSession']==native['source']['domainSession'])
                    if field=='deletion':need(retired(proof['entities']['source']))
            if step['outcome'] in ('denied','created'):need(step['effect'] is not None and step['createOriginal'] is not None)
            if step['outcome']=='created':need(step['kind']=='cube' and step['entityId'] is not None)
            if step['outcome']=='deleted':need(step['deletion'] is not None)
        need(tickets==list(dict.fromkeys(tickets)))
        return value
    def recovery_write(self,value,previous):
        self.lock.assert_held();self.source_store('recovery').write(value,previous);need(self.recovery_state()==value)
    def recovery_step(self):
        value=self.recovery_state();need(value is not None);return value['steps'][-1]
    def recovery_update(self,**changes):
        previous=self.recovery_state();value=deepcopy(previous);value['steps'][-1].update(deepcopy(changes));self.recovery_write(value,previous)
    def recovery_attempt(self,kind):
        step=self.recovery_step();need(kind in ATTEMPTS and kind not in step['attempted']);self.recovery_update(attempted=step['attempted']+[kind])
    def recovery_input(self,kind,original):
        if kind!='create' or original['controlId']!='create.new-shape':return
        value=self.recovery_state()
        if value is None:return
        step=value['steps'][-1]
        need(step['ticket']==self.state()['pending'] and 'create' in step['attempted'] and step['createOriginal'] is None)
        self.recovery_update(createOriginal=deepcopy(original))
    def recovery_before(self):return archive(self.recovery_step()['before'],self.state()['binding'],self.run)
    def recovery_row(self,actual):
        step=self.recovery_step();before=self.recovery_before()['entities'];packet=actual['entities'];a,b=before['source'],packet['source']
        from adapters.pico4.create_picker_owner import OwnedCreatePicker
        OwnedCreatePicker.same_scene_identity(before,packet);need(self.rez_ready(actual) and b['createEntitySourceVersion']==6)
        old,new=a['localCreations'],b['localCreations'];need(old['armedAfterSequence']==new['armedAfterSequence'] and new['events'][:len(old['events'])]==old['events'])
        events=new['events'][len(old['events']):]
        if not events:
            need(not b['entities'] and step['entityId'] is None);return None
        need(step['createOriginal'] is not None and len(events)==1)
        event=events[0];need(event['type'] in ('Shape','Box','Sphere') and event['hostType']=='domain'
            and event['sessionId']==b['sessionId'] and event['observedEpochMs']>=before['capturedEpochMs']
            and event['createdEpochUs']>=before['capturedEpochMs']*1000)
        identifier=event['id'];need(step['entityId'] in (None,identifier))
        if not b['entities']:
            need(step['entityId']==identifier and identifier in b['absentIds']);return None
        need(len(b['entities'])==1);row=b['entities'][0]
        need(row['id']==identifier and row['type']==event['type'] and row['hostType']=='domain'
            and row['createdEpochUs']==event['createdEpochUs'] and row['lastEditedBy']==b['sessionId'] and row['parentId'] is None)
        life=next((r for r in b['entityLifetimes'] if r['id']==identifier),None);need(life is not None and life['alive'] and life['inTree'])
        if step['entityId'] is None:self.recovery_update(entityId=identifier,lifetime=life)
        else:need(all(life[k]==step['lifetime'][k] for k in ('id','instance','firstObservedEpochMs')))
        return row
    def recovery_ready(self,actual,operation):
        row=self.recovery_row(actual);step=self.recovery_step();before=self.recovery_before();source=actual['entities']['source']
        ready=idle(actual['scope']) and not active(actual['callbacks'])
        page=next((r for r in actual['ui']['controls'] if r['id']=='create.page'),None)
        need(bridge_pins(actual['callbacks'],self.state()['manager'])==step['pins'])
        from adapters.native_script_work import scope
        original_scope=scope(before['work'],self.state()['compilation'])
        if operation=='denied':
            need(not source['canRez'] and not source['canRezTmp'])
            return ready and row is None and source['localCreations']==before['entities']['source']['localCreations'] and source['scan']==before['entities']['source']['scan'] \
                and page is not None and page['statusError'] and page['statusText']==DENIED and not page['selectedIds'] \
                and actual['scope']['signalInvocations']>original_scope['signalInvocations'] and retired(source)
        if operation=='create':
            return ready and row is not None and row['type']=='Box' and row['shape']=='Cube' and row['visible'] and row['visuallyReady'] \
                and not row['locked'] and row['name']=='e2e-'+self.run+'-cube' and all(abs(v-.2)<=1e-6 for v in row['dimensions']) \
                and 'name' in step['attempted'] and page is not None and page['selectedIds']==[row['id']] and not page['statusError'] \
                and actual['scope']['signalInvocations']>original_scope['signalInvocations']
        need(operation=='delete');return ready and row is None and retired(source)
    def recovery_settle(self,operation):
        ui,_binding=self.runtime();started=ui.monotonic();quiet=None;clocks=None;stable=None
        for attempt in range(103):
            actual=self.sample();ready=self.recovery_ready(actual,operation);current=ui.monotonic()
            epochs=(actual['entities']['capturedEpochMs'],actual['work']['source']['work']['capturedEpochMs'],actual['ui']['elapsedMs'])
            # Original edit.js Script.update callbacks continue while idle. Their
            # cumulative signal count must not become a fictitious quiet clock.
            signature=(actual['entities']['source']['entities'],actual['scope']['timerRegistrations'],actual['scope']['timerInvocations'])
            if ready and (stable is None or signature==stable):
                quiet=current if quiet is None else quiet;clocks=epochs if clocks is None else clocks;stable=deepcopy(signature)
                if current-quiet>=3 and all(b-a>=3000 for a,b in zip(clocks,epochs)):
                    self.phase_fence();self.fresh_sample(actual);return actual
            else:quiet=None;clocks=None;stable=None
            need(current-started<20 and attempt<102);ui.sleep(.2)
        need(False)
    def recovery_create(self,kind):
        need(kind in ('denied','cube'));actual=self.sample();need(self.rez_state() is not None and self.rez_ready(actual))
        native=actual['entities'];need(native['source']['createEntitySourceVersion']==6 and retired(native['source']) and idle(actual['scope']))
        previous=self.recovery_state()
        if kind=='cube':
            need(previous is not None and previous['steps'][-1]['kind']=='denied' and previous['steps'][-1]['outcome']=='denied'
                and (native['source']['canRez'] or native['source']['canRezTmp']) and not actual['rez']['current']['restored'])
        else:
            need(previous is None or previous['steps'][-1]['outcome'] in ('deleted','cancelled'))
            need(not native['source']['canRez'] and not native['source']['canRezTmp'])
            page=next((r for r in actual['ui']['controls'] if r['id']=='create.page'),None);need(page is not None and not page['statusError'])
        step=dict(ticket=self.state()['pending'],kind=kind,before=self.primitive_proof(actual),pins=bridge_pins(actual['callbacks'],self.state()['manager']),
            attempted=[],createOriginal=None,entityId=None,lifetime=None,outcome='creating',effect=None,deleteTicket=None,deletion=None)
        value=dict(createRecoveryVersion=1,binding=deepcopy(self.state()['binding']),runId=self.run,steps=[]) if previous is None else deepcopy(previous)
        value['steps'].append(step);self.recovery_write(value,previous);controls=self.controls()
        self.recovery_attempt('tab');controls.tab(0)
        self.recovery_attempt('host');controls.choose('create.host',0)
        self.recovery_attempt('shape');controls.choose('create.shape',0)
        controls.reveal('create.new-shape');self.recovery_attempt('create');controls.input('create.new-shape')
        if kind=='cube':
            ui,_binding=self.runtime();started=ui.monotonic()
            for attempt in range(67):
                actual=self.sample();row=self.recovery_row(actual)
                if row is not None:break
                need(ui.monotonic()-started<10 and attempt<66);ui.sleep(.15)
            self.recovery_attempt('name');controls.select_entity(row['id']);controls.name_entity('e2e-'+self.run+'-cube')
        actual=self.recovery_settle('denied' if kind=='denied' else 'create')
        self.recovery_update(outcome='denied' if kind=='denied' else 'created',effect=self.primitive_proof(actual))
        if kind=='cube':self.mark(subject='recovery')
    def recovery_delete(self):
        step=self.recovery_step();actual=self.sample();row=self.recovery_row(actual)
        need(step['createOriginal'] is not None and (row is not None or step['entityId'] is not None))
        if row is not None and 'delete' not in step['attempted']:
            if step['deleteTicket'] is None:self.recovery_update(deleteTicket=self.state()['phase']['activations'][-1]['ticket'])
            controls=self.controls()
            if 'delete-prepare' not in step['attempted']:
                self.recovery_attempt('delete-prepare')
                if controls.row(controls.capture(),'create.page',enabled=False) is None:
                    self.close_editor();self.open_editor();controls=self.controls()
                controls.select_entity(row['id'])
            need(controls.page(controls.capture())['selectedIds']==[row['id']])
            self.recovery_attempt('delete');controls.delete_entity()
        actual=self.recovery_settle('delete');self.recovery_update(outcome='deleted',deletion=self.primitive_proof(actual));self.mark(subject=None)
    def recovery_reconcile(self,operation):
        step=self.recovery_step();need(step['createOriginal'] is not None)
        actual=self.recovery_settle(operation)
        if operation=='delete':self.recovery_update(outcome='deleted',deletion=self.primitive_proof(actual));self.mark(subject=None)
        else:
            self.recovery_update(outcome='denied' if operation=='denied' else 'created',effect=self.primitive_proof(actual))
            if operation=='create':self.mark(subject='recovery')
    def recovery_final(self,actual):
        value=self.recovery_state()
        if value is None:return
        call=self.state()['calls'][-1];step=value['steps'][-1]
        operation={'create-denied':'denied','create-retry':'create'}.get(call['verb'])
        if call['verb']=='delete-owned' and step['deleteTicket']==call['ticket']:operation='delete'
        if operation is not None:
            need(step['outcome']==dict(denied='denied',create='created',delete='deleted')[operation] and self.recovery_ready(actual,operation))
    def recovery_cleanup(self):
        value=self.recovery_state()
        if value is None:return
        step=value['steps'][-1]
        if step['outcome'] in ('deleted','cancelled','denied'):return
        actual=self.sample();row=self.recovery_row(actual)
        if row is not None or step['entityId'] is not None:self.recovery_delete()
        else:
            # No durable Create intent can mean no dispatched Create, because
            # the parent records it before the final actual writer admission.
            need(step['createOriginal'] is None and retired(actual['entities']['source']))
            self.recovery_update(outcome='cancelled')
    def recovery_retired(self):
        value=self.recovery_state()
        return value is None or value['steps'][-1]['outcome'] in ('deleted','cancelled','denied')
