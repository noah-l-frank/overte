"""Durable normal Create JSON Cancel/Import composition; no full feature claim.

Input delivery, actual domain properties, Script callback retirement and native
Qt resource lifetime have separate owners. A retained context never disappears
because a later action starts or because an application teardown is requested.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import math
import os
import re
import time
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact,fresh,need,decode,integer
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_callbacks import active as active_callbacks
from adapters.pico4.create_browse_setting import restored as browse_setting_restored
from adapters.pico4.create_dialogs import active as active_dialogs,joined
from adapters.pico4.create_entities import retired as entities_retired
from adapters.pico4.create_file_ui import inventory
from adapters.token_create_ui import nonce,scope,control_id
from feature_journeys.contract import identifier

VERSION=2
ORIGINAL_VERSION=1


class OriginalReader:
    """Keep original bytes/hash and native history across adapter reconstruction."""
    def __init__(self,reader,store,binding):
        self.reader,self.store,self.binding=reader,store,deepcopy(context(binding))
        previous=store.read()
        if previous is not None:
            exact(previous,{'schemaVersion','binding','raw','sha256'})
            need(type(previous['schemaVersion']) is int and previous['schemaVersion']==ORIGINAL_VERSION
                and context(previous['binding'])==self.binding and type(previous['raw']) is str
                and hashlib.sha256(previous['raw'].encode()).hexdigest()==previous['sha256'])
            value=decode(previous['raw'])
            reader.validate(value,value['requestId'],reader.pid,value['capturedEpochMs'])
            reader.last=deepcopy(value)
        self.previous=previous

    def read(self):
        value=self.reader.read();raw=self.reader.last_raw
        need(type(raw) is str and decode(raw)==value and hashlib.sha256(raw.encode()).hexdigest()==self.reader.last_sha256)
        current=dict(schemaVersion=ORIGINAL_VERSION,binding=self.binding,raw=raw,sha256=self.reader.last_sha256)
        self.store.write(current,self.previous);self.previous=current
        return value

    def retire(self):
        self.store.discard(self.previous);self.previous=None


def callback_rows(packet):
    rows={}
    for manager in packet['source']['managers']:
        proxies={r['id']:r for r in manager['callbacks']['proxies']}
        compiled={r['scriptId']:r for r in manager['compiled']['compilations']}
        for row in manager['callbacks']['callbacks']:
            key=manager['callbacks']['instance']+':'+row['id']
            rows[key]=dict(manager=deepcopy(manager['membership']),sourceId=manager['callbacks']['instance'],
                callback=deepcopy(row),proxy=deepcopy(proxies[row['proxyId']]),compiled=deepcopy(compiled[row['scriptId']]))
    return rows


class OwnedCreatePicker:
    def __init__(self,store,binding,controls,file_ui,file_io,files,callbacks,dialogs,entities,setting,source,*,
                 monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (controls,file_ui,files,monotonic,sleep)))
        self.store,self.binding=store,deepcopy(context(binding))
        self.controls,self.file_ui,self.file_io,self.files=controls,file_ui,file_io,files
        self.callbacks,self.dialogs,self.entities=callbacks,dialogs,entities
        self.setting=setting
        self.source=deepcopy(source);exact(source,{'import','export'})
        for code in source.values():
            exact(code,{'sha256','codeUnits'})
            need(type(code['sha256']) is str and re.fullmatch('[0-9a-f]{64}',code['sha256']) and integer(code['codeUnits'],1))
        self.monotonic,self.sleep,self.previous,self.clock=monotonic,sleep,store.read(),None
        if self.previous is not None:self.validate(self.previous)

    def validate(self,value):
        exact(value,{'schemaVersion','binding','runId','fixtureUrl','steps','lastInput','inputCount','pending'})
        need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and context(value['binding'])==self.binding
            and type(value['steps']) is list and 1<=len(value['steps'])<=4 and integer(value['inputCount'],0,4096))
        identifier(value['runId']);tickets=[]
        for step in value['steps']:
            exact(step,{'ticket','beforeUi','beforeCallbacks','beforeDialogs','baseline','directory','uiRootId','dialogBinding',
                'callback','attempted','outcome','entityId','filesReleased','beforeSelection','role','exportOriginal','beforeChoice','exportEvidence'})
            identifier(step['ticket']);tickets.append(step['ticket']);inventory(step['beforeUi'])
            need(type(step['beforeCallbacks']) is list and len(step['beforeCallbacks'])<=512
                and step['beforeCallbacks']==sorted(set(step['beforeCallbacks']))
                and type(step['beforeDialogs']) is list and step['beforeDialogs']==sorted(set(step['beforeDialogs']))
                and all(nonce(v) for v in step['beforeDialogs']) and type(step['attempted']) is list
                and len(step['attempted'])==len(set(step['attempted'])) and set(step['attempted'])<={'open','cancel','import','export','delete'}
                and step['role'] in ('import','export') and type(step['beforeSelection']) is list
                and (step['beforeSelection']==[] if step['role']=='import' else len(step['beforeSelection'])==1 and nonce(step['beforeSelection'][0]))
                and type(step['filesReleased']) is bool and step['outcome'] in ('reserved','open','cancelled','imported','exported','deleted')
                and (step['exportOriginal'] is None if step['role']=='import' else type(step['exportOriginal']) is dict)
                and (step['uiRootId'] is None or nonce(step['uiRootId'])) and (step['entityId'] is None or nonce(step['entityId'])))
            self.entities.reader.validate(step['baseline'],step['baseline']['requestId'],self.entities.reader.pid,
                step['baseline']['capturedEpochMs'])
            if step['role']=='export':
                need(step['baseline']['source']['entities']==[step['exportOriginal']]
                    and step['beforeSelection']==[step['exportOriginal']['id']] and step['entityId']==step['exportOriginal']['id'])
            # The stored actual input is validated by OwnedCreateFiles; no URL
            # request can substitute new bytes into an old ticket's namespace.
            if step['directory'] is not None:
                from adapters.token_script_file_ui import file_url
                need(file_url(step['directory']).endswith('/feature-create-'+value['runId']+'-'+step['ticket']))
            for field in ('beforeChoice','exportEvidence'):
                if step[field] is not None:self.file_packet(step[field],step,value['runId'])
            need(step['role']=='export' or step['beforeChoice'] is None and step['exportEvidence'] is None)
            if step['beforeChoice'] is not None:need(not step['beforeChoice']['source']['files'][1]['exists'])
            if step['exportEvidence'] is not None:need(step['beforeChoice'] is not None and step['exportEvidence']['source']['files'][1]['exists'])
            if step['dialogBinding'] is not None:
                need(type(step['dialogBinding']) is dict and step['uiRootId'] is not None)
            need(step['callback'] is None or type(step['callback']) is dict)
        need(tickets==list(dict.fromkeys(tickets)))
        need(value['pending'] is None or type(value['pending']) is dict and set(value['pending'])=={'ticket','operation'}
            and value['pending']['ticket']==tickets[-1] and value['pending']['operation'] in ('open','cancel','import','export','delete'))
        need(value['inputCount']==0 and value['lastInput'] is None or value['inputCount']>0 and type(value['lastInput']) is dict)

    def state(self):
        value=self.store.read();need(value is not None and value==self.previous);self.validate(value);return value

    def write(self,value):
        self.validate(value);self.store.write(value,self.previous);self.previous=deepcopy(value)

    def update_step(self,**changes):
        value=self.state();value['steps'][-1].update(deepcopy(changes));self.write(value)

    def now(self):
        value=self.monotonic();need(type(value) in (int,float) and math.isfinite(value) and value>=0 and (self.clock is None or value>=self.clock))
        self.clock=value;return value

    def intent(self,original):
        value=self.state();need(value['pending'] is not None and value['inputCount']<4096)
        need(type(original) is dict and ('createInputVersion' in original or 'createFileInputVersion' in original))
        scope(original['scope']);need(original['scope']['processId']==int(self.binding['processIdentity'].split(':')[0])
            and original['scope']['instance']==self.binding['sessionId'] and nonce(original['controlToken']))
        if 'createInputVersion' in original:
            exact(original,{'createInputVersion','action','controlId','controlToken','scope'})
            need(original['createInputVersion']==1 and control_id(original['controlId']))
        else:
            exact(original,{'createFileInputVersion','action','controlId','controlToken','scope','rootId','role','page'})
            need(original['createFileInputVersion']==1 and original['role']==value['steps'][-1]['role']
                and original['rootId']==value['steps'][-1]['uiRootId'] and original['controlId'].startswith('create-file.'))
        value.update(lastInput=deepcopy(original),inputCount=value['inputCount']+1);self.write(value)

    def begin(self,operation):
        value=self.state();step=value['steps'][-1]
        need(operation not in step['attempted'])
        if value['pending'] is not None:
            # A distinct ordinary Cancel is the only uncertain-input recovery.
            need(operation=='cancel' and value['pending']['operation'] in ('open','import','export'))
        step['attempted'].append(operation);value['pending']=dict(ticket=step['ticket'],operation=operation);self.write(value)

    def finish(self,outcome):
        value=self.state();value['steps'][-1]['outcome']=outcome;value['pending']=None;self.write(value)

    def actual(self):
        values=dict(callbacks=self.callbacks.read(),dialogs=self.dialogs.read(),entities=self.entities.read())
        need(len({v['instance'] for v in values.values()})==1)
        for key,value in values.items():fresh(value['capturedEpochMs'],getattr(self,key).reader.clock_ms())
        need(len({v['processId'] for v in values.values()})==1
            and next(iter(values.values()))['processId']==int(self.binding['processIdentity'].split(':')[0]))
        return values

    @staticmethod
    def same_scene(before,after):
        a,b=before['source'],after['source']
        need(before['instance']==after['instance'] and a['domainConnected'] and b['domainConnected'] and a['domainId'] is not None and a['sessionId'] is not None
            and a['createEntitySourceVersion']==b['createEntitySourceVersion'] and a['createEntitySourceVersion'] in (2,3) and a['domainSession']==b['domainSession']
            and all(a[k]==b[k] for k in ('runId','domainId','sessionId','canRez','canRezTmp'))
            and a['scan']['center']==b['scan']['center'] and a['scan']['unowned']==b['scan']['unowned'])

    def join_open(self):
        value=self.state();step=value['steps'][-1]
        ui=self.file_ui(self.intent,step);page=ui.wait_open();row=ui.page(page)
        need(step['uiRootId'] in (None,row['rootId']));self.update_step(uiRootId=row['rootId'])
        actual=self.actual();self.same_scene(step['baseline'],actual['entities'])
        need(actual['entities']['source']['entities']==step['baseline']['source']['entities'])
        bindings=self.file_io.dialog_bindings();need(bindings['complete'])
        rows=[r for r in bindings['bindings'] if r['uiRootId']==row['rootId']];need(len(rows)==1)
        binding=rows[0]['native'];native=joined(binding,actual['dialogs'])
        need(actual['dialogs']['source']['createDialogSourceVersion']==3)
        read_started=self.now()
        for attempt in range(51):
            if native['browseSettingRead'] is not None:break
            need(attempt<50 and self.now()-read_started<5);self.sleep(.1)
            actual=self.actual();self.same_scene(step['baseline'],actual['entities']);native=joined(binding,actual['dialogs'])
        need({r['id'] for r in actual['dialogs']['source']['dialogs']}==set(step['beforeDialogs'])|{binding['dialogId']})
        need(binding['dialogId'] not in step['beforeDialogs'] and native['role']==step['role'] and native['pending']
            and native['dispatches']==0 and native['rootAlive'] and native['listenerAlive'] and native['contextAlive'])
        candidates={key:r for key,r in callback_rows(actual['callbacks']).items() if key not in step['beforeCallbacks']}
        need(len(candidates)==1);key,callback=next(iter(candidates.items()))
        code=callback['compiled'];url=urlsplit(code['resourceName'])
        need(callback['callback']['disconnectedEpochMs']==0 and callback['proxy']['signal']==('browseChanged(QString)' if step['role']=='import' else 'saveFileChanged(QString)')
            and callback['proxy']['dispatches']==0 and callback['manager']['assigned'] is True
            and url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment
            and url.path.endswith('/system/create/'+('edit.js' if step['role']=='import' else 'entityList/entityList.js'))
            and all(code[k]==self.source[step['role']][k] for k in ('sha256','codeUnits')))
        owned_callbacks={key}
        for previous in value['steps'][:-1]:
            if previous['callback'] is not None:owned_callbacks.add(previous['callback']['key'])
        need(all(r['sourceId']+':'+r['callbackId'] in owned_callbacks for r in active_callbacks(actual['callbacks']) if 'callbackId' in r))
        need(not any('dispatches' in r for r in active_callbacks(actual['callbacks'])))
        need(step['dialogBinding'] in (None,binding) and step['callback'] in (None,dict(key=key,original=callback)))
        self.update_step(dialogBinding=binding,callback=dict(key=key,original=callback))
        self.setting.claim_read(self.owned_files(self.state()['steps'][-1]).owned(),binding)
        return ui

    def open(self,run,ticket,fixture_url,role='import'):
        identifier(run);identifier(ticket)
        need(self.entities.reader.run==run and role in ('import','export'))
        control=self.controls(self.intent);before_selection=control.page(control.capture())['selectedIds']
        need(before_selection==[] if role=='import' else len(before_selection)==1)
        before=self.file_io.capture();inventory(before['inventory'])
        need(before['inventory']['complete'] and len(before['inventory']['roots'])==1
            and before['inventory']['roots'][0]['profile']=='create-editor-v1')
        actual=self.actual();need(not active_callbacks(actual['callbacks']))
        previous=self.previous
        if previous is not None:
            value=self.state();need(value['runId']==run and value['fixtureUrl']==fixture_url and value['pending'] is None
                and value['steps'][-1]['outcome'] in (('cancelled','deleted') if role=='import' else ('imported','exported','cancelled')) and len(value['steps'])<4
                and ticket not in [s['ticket'] for s in value['steps']])
            allowed={s['dialogBinding']['dialogId'] for s in value['steps'] if s['dialogBinding'] is not None}
        else:
            value=dict(schemaVersion=VERSION,binding=self.binding,runId=run,fixtureUrl=fixture_url,steps=[],lastInput=None,inputCount=0,pending=None)
            allowed=set();need(role=='import')
        need(all(r['id'] in allowed for r in active_dialogs(actual['dialogs'])))
        source=actual['entities']['source'];need(source['createEntitySourceVersion']==3 and source['domainConnected'] and source['domainId'] and source['sessionId']
            and (source['canRez'] or source['canRezTmp']))
        if role=='import':need(entities_retired(source))
        else:
            need(len(source['entities'])==1 and before_selection==[source['entities'][0]['id']]
                and any(s['role']=='import' and s['outcome']=='imported' and s['entityId']==before_selection[0] for s in value['steps']))
            for old in value['steps']:self.same_scene(old['baseline'],actual['entities'])
        step=dict(ticket=ticket,beforeUi=deepcopy(before['inventory']),beforeCallbacks=sorted(callback_rows(actual['callbacks'])),
            beforeDialogs=sorted(r['id'] for r in actual['dialogs']['source']['dialogs']),baseline=actual['entities'],directory=None,
            uiRootId=None,dialogBinding=None,callback=None,attempted=[],outcome='reserved',
            entityId=before_selection[0] if role=='export' else None,filesReleased=False,beforeSelection=deepcopy(before_selection),role=role,
            exportOriginal=deepcopy(source['entities'][0]) if role=='export' else None,beforeChoice=None,exportEvidence=None)
        value['steps'].append(step);self.write(value)
        self.setting.reserve(run) # Exact original captured before any real Select.
        files=self.files(ticket);files.reserve(run,fixture_url)
        observed=files.stage();need(not observed['files'][1]['exists'])
        self.update_step(directory=observed['directory']);self.begin('open')
        controls=self.controls(self.intent);controls.tab(4)
        if role=='import':
            controls.choose('create.import-host',0);controls.reveal('create.import-browse');controls.input('create.import-browse')
        else:
            controls.reveal('create.export');controls.input('create.export')
        self.join_open();self.finish('open');return {'performed':True}

    def open_export(self,run,ticket,fixture_url):return self.open(run,ticket,fixture_url,'export')

    def owned_files(self,step):
        value=self.state();files=self.files(step['ticket']);owned=files.owned()
        need(owned['runId']==value['runId'] and owned['fixtureUrl']==value['fixtureUrl'] and owned['ticket']==step['ticket'])
        return files

    def callback_returned(self,actual):
        step=self.state()['steps'][-1];need(step['dialogBinding'] is not None and step['callback'] is not None)
        row=joined(step['dialogBinding'],actual['dialogs'])
        need(not row['pending'] and row['dispatches']==0 and row['returnedEpochMs']>0
            and not row['rootAlive'] and not row['listenerAlive'])
        original=step['callback'];current=callback_rows(actual['callbacks']);need(original['key'] in current)
        callback=current[original['key']];old=original['original']
        need(callback['compiled']==old['compiled'] and callback['sourceId']==old['sourceId']
            and all(callback['callback'][k]==old['callback'][k] for k in ('id','proxyId','scriptId','connectedEpochMs'))
            and callback['callback']['disconnectedEpochMs']>0 and callback['proxy']['dispatches']==0)
        need(not active_callbacks(actual['callbacks']))
        need(set(current)==set(step['beforeCallbacks'])|{original['key']}
            and {r['id'] for r in actual['dialogs']['source']['dialogs']}==set(step['beforeDialogs'])|{step['dialogBinding']['dialogId']})
        return row

    def finish_choice(self,operation):
        value=self.state();step=value['steps'][-1]
        need(step['outcome']=='open' or value['pending'] is not None and operation=='cancel')
        need(operation=='cancel' or operation==step['role'])
        ui=self.join_open();files=self.owned_files(step);observed=files.verify()
        if step['role']=='export':
            need(not observed['files'][1]['exists'])
            if operation=='export':
                self.file_packet(files.native.last_packet,step,value['runId'])
                need(step['beforeChoice'] is None);self.update_step(beforeChoice=files.native.last_packet)
        actual_setting=self.setting.observe()
        need(actual_setting['current']==actual_setting['owned'])
        self.begin(operation)
        if operation=='cancel':ui.cancel()
        else:ui.accept()
        return self.reconcile()

    def cancel(self):return self.finish_choice('cancel')
    def import_file(self):return self.finish_choice('import')
    def export_file(self):return self.finish_choice('export')

    def reconcile(self):
        value=self.state();step=value['steps'][-1];need(value['pending'] is not None)
        operation=value['pending']['operation'];need(operation in ('cancel','import','export','delete'))
        ui=self.file_ui(self.intent,step);ui.root=step['uiRootId'];ui.retired()
        start=self.now();quiet=None;native_quiet=None;dialog_quiet=None;last=0
        for attempt in range(132):
            actual=self.actual();self.same_scene(step['baseline'],actual['entities']);self.callback_returned(actual)
            entities=actual['entities']['source']['entities'];controls=self.controls(self.intent)
            page=controls.page(controls.capture());need(not page['statusError'])
            if operation in ('import','export'):
                self.setting.claim(self.owned_files(step).owned(),step['dialogBinding'])
            if operation=='import':
                expected=json.loads(base64.b64decode(self.owned_files(step).owned()['inputBase64']))['Entities'][0]
                need(len(entities)<=1)
                ready=len(entities)==1
                if ready:
                    row=entities[0];need(row['hostType']=='domain' and row['type']=='Model' and row['name']==expected['name']
                        and row['modelUrl']==expected['modelURL'] and row['dimensions']==[expected['dimensions'][k] for k in 'xyz']
                        and row['parentId'] is None and page['selectedIds']==[row['id']] and page['statusText']=='Imported 1 entities.'
                        and row['lastEditedEpochUs']>=step['baseline']['capturedEpochMs']*1000)
                    self.update_step(entityId=row['id'])
            elif operation=='export' or operation=='cancel' and step['role']=='export':
                need(entities==step['baseline']['source']['entities'] and page['selectedIds']==step['beforeSelection'])
                ready=True
                if operation=='export':self.verify_export(step)
                else:need(not self.owned_files(step).verify()['files'][1]['exists'])
            else:
                ready=entities_retired(actual['entities']['source'])
                need(page['selectedIds']==[])
                if operation=='cancel':need(page['statusText']=='Import cancelled.')
            packet=actual['entities'];current=self.now()
            if ready and packet['sequence']>last:
                quiet=current if quiet is None else quiet
                native_quiet=packet['capturedEpochMs'] if native_quiet is None else native_quiet
                dialog_elapsed=actual['dialogs']['source']['elapsedMs']
                dialog_quiet=dialog_elapsed if dialog_quiet is None else dialog_quiet
                if current-quiet>=3 and packet['capturedEpochMs']-native_quiet>=3000 and dialog_elapsed-dialog_quiet>=3000:
                    self.finish(dict(cancel='cancelled',import_='imported',export='exported',delete='deleted')['import_' if operation=='import' else operation])
                    return {'performed':True}
            else:quiet=None;native_quiet=None;dialog_quiet=None
            last=packet['sequence'];need(current-start<13 and attempt<131);self.sleep(.1)
        need(False)

    def file_packet(self,packet,step,run):
        native=self.files(step['ticket']).native
        exact(packet,native.packet_fields());native.packet_scope(packet);native.validate_source(packet['source'],'observe',run)
        need(packet['schemaVersion']==1 and type(packet['schemaVersion']) is int and nonce(packet['requestId'])
            and packet['instance']==step['baseline']['instance'] and integer(packet['sequence'],1)
            and packet['processId']==int(self.binding['processIdentity'].split(':')[0])
            and packet['runId']==run and packet['operation']=='observe' and integer(packet['requestedEpochMs'],1)
            and integer(packet['capturedEpochMs'],packet['requestedEpochMs'])
            and packet['capturedEpochMs']-packet['requestedEpochMs']<5000 and packet['source']['exists']
            and packet['source']['directory']==step['directory'])

    def verify_export(self,step):
        step=self.state()['steps'][-1];files=self.owned_files(step);row=files.exported()
        packet=deepcopy(files.native.last_packet);self.file_packet(packet,step,self.state()['runId'])
        before_choice=step['beforeChoice'];need(before_choice is not None and packet['sequence']>before_choice['sequence']
            and packet['capturedEpochMs']>=before_choice['capturedEpochMs'])
        for field in ('modified','changed'):
            seconds,nanos=row[field].split('.')
            need(int(seconds)*1000000000+int(nanos)>=before_choice['capturedEpochMs']*1000000)
        if step['exportEvidence'] is not None:need(row==step['exportEvidence']['source']['files'][1])
        raw=base64.b64decode(row['base64'],validate=True)
        # The output is acquired from product-created bytes/inode/hash. Compare
        # against independently observed pre-Save domain properties, never the
        # requested import document or a generated expected export artifact.
        document=decode(raw.decode('utf-8'));need(type(document) is dict and type(document.get('DataVersion')) is int
            and document['DataVersion']==0 and type(document.get('Entities')) is list and len(document['Entities'])==1)
        actual=document['Entities'][0];before=step['exportOriginal'];need(type(actual) is dict)
        need(actual.get('name')==before['name'] and actual.get('type')==before['type'] and actual.get('modelURL')==before['modelUrl']
            and type(actual.get('dimensions')) is dict and set(actual['dimensions'])==set('xyz')
            and all(type(actual['dimensions'][k]) in (int,float) and actual['dimensions'][k]==v for k,v in zip('xyz',before['dimensions'])))
        identity=actual.get('id');need(type(identity) is str and identity in (before['id'],'{'+before['id']+'}'))
        textures=actual.get('textures','');need(type(textures) in (str,dict))
        normalize=lambda v:decode(v) if type(v) is str and v else {} if not v else v
        need(normalize(textures)==normalize(before['textures']))
        # Preserve all original fields/bytes in the existing private file owner;
        # this narrow foundation does not claim texture/peer/stereo checkpoints.
        if step['exportEvidence'] is None:self.update_step(exportEvidence=packet)
        return row

    def delete_import(self):
        step=self.state()['steps'][-1];need(step['outcome'] in ('imported','exported','cancelled') and step['entityId'] is not None)
        actual=self.actual();self.same_scene(step['baseline'],actual['entities']);self.callback_returned(actual)
        need([r['id'] for r in actual['entities']['source']['entities']]==[step['entityId']])
        self.begin('delete');controls=self.controls(self.intent)
        controls.select_entity(step['entityId']);controls.delete_entity();return self.reconcile()

    def release_ui(self,previous):
        value=self.file_io.capture();inventory(value['inventory']);scope(value['scope'])
        need(value['inventory']['complete'] and value['scope']['instance']==self.binding['sessionId']
            and value['scope']['processId']==int(self.binding['processIdentity'].split(':')[0])
            and not any(r['profile']!='create-editor-v1' for r in value['inventory']['roots']))
        if self.previous is not None:
            for step in self.state()['steps']:
                need(value['inventory']['instance']==step['beforeUi']['instance']
                    and step['uiRootId'] in value['inventory']['retiredRoots'])
        if previous is not None:
            a,b=previous['inventory'],value['inventory']
            need(a['instance']==b['instance'] and b['sequence']>a['sequence'] and set(a['retiredRoots'])<=set(b['retiredRoots'])
                and {r['id'] for r in a['roots']}<={r['id'] for r in b['roots']}|set(b['retiredRoots'])
                and all(previous['scope'][k]==value['scope'][k] for k in ('instance','generation','processId','sequence'))
                and value['scope']['elapsedMs']>=previous['scope']['elapsedMs'])
        return value

    def release_observations(self):
        """Recover read-only acquisition failures; caller proves no file owner."""
        need(self.previous is None and self.store.read() is None)
        start=self.now();quiet=None;epochs=None;previous_ui=None
        for attempt in range(132):
            actual=self.actual();ui=self.release_ui(previous_ui);previous_ui=deepcopy(ui)
            ready=True
            ready=ready and not active_callbacks(actual['callbacks']) and not active_dialogs(actual['dialogs']) and entities_retired(actual['entities']['source'])
            clocks=(actual['entities']['capturedEpochMs'],actual['dialogs']['source']['elapsedMs'],ui['scope']['elapsedMs'])
            now=self.now()
            if ready:
                quiet=now if quiet is None else quiet;epochs=clocks if epochs is None else epochs
                if now-quiet>=3 and all(b-a>=3000 for a,b in zip(epochs,clocks)):
                    if self.setting.previous is not None:
                        self.setting.release();self.setting.retire()
                    for observer in (self.callbacks,self.dialogs,self.entities):observer.retire()
                    return {'performed':True}
            else:quiet=None;epochs=None
            need(now-start<13 and attempt<131);self.sleep(.1)
        need(False)

    def release(self):
        value=self.state();need(value['pending'] is None and value['steps'][-1]['outcome'] in ('cancelled','deleted')
            and all(s['outcome'] in ('cancelled','imported','exported','deleted') for s in value['steps'])
            and (not any(s['entityId'] is not None for s in value['steps']) or value['steps'][-1]['outcome']=='deleted'))
        # Require a fresh complete joint quiet window before deleting original
        # files. Page disappearance does not waive the original QQmlContext.
        self.setting.restore()
        started=self.now();quiet=None;native_quiet=None;dialog_quiet=None;ui_quiet=None;last=0;previous_ui=None
        for attempt in range(132):
            actual=self.actual();ui=self.release_ui(previous_ui);previous_ui=deepcopy(ui)
            setting=self.setting.observe();need(browse_setting_restored(setting))
            if active_dialogs(actual['dialogs']):
                raise NativeUIError('Original Create Qt context, listener or delivery remains retained')
            ready=not active_callbacks(actual['callbacks']) and entities_retired(actual['entities']['source'])
            for step in value['steps']:
                self.same_scene(step['baseline'],actual['entities']);joined(step['dialogBinding'],actual['dialogs'])
            current=self.now();packet=actual['entities']
            if ready and packet['sequence']>last:
                quiet=current if quiet is None else quiet
                native_quiet=packet['capturedEpochMs'] if native_quiet is None else native_quiet
                dialog_elapsed=actual['dialogs']['source']['elapsedMs']
                dialog_quiet=dialog_elapsed if dialog_quiet is None else dialog_quiet
                ui_elapsed=ui['scope']['elapsedMs'];ui_quiet=ui_elapsed if ui_quiet is None else ui_quiet
                if current-quiet>=3 and packet['capturedEpochMs']-native_quiet>=3000 and dialog_elapsed-dialog_quiet>=3000 and ui_elapsed-ui_quiet>=3000:break
            else:quiet=None;native_quiet=None;dialog_quiet=None;ui_quiet=None
            last=packet['sequence'];need(current-started<13 and attempt<131);self.sleep(.1)
        self.setting.release()
        for index,step in enumerate(value['steps']):
            if not step['filesReleased']:
                self.owned_files(step).release()
                value=self.state();value['steps'][index]['filesReleased']=True;self.write(value)
        self.store.discard(value);self.previous=None
        self.setting.retire()
        for observer in (self.callbacks,self.dialogs,self.entities):observer.retire()
        return {'performed':True}


class PicoCreatePicker:
    """Candidate-bound private composition for the eventual complete Create owner.

    This does not advertise the incomplete common feature.create operation trio.
    The caller enters the original Create page before reserving a picker.
    """
    def __init__(self,adapter,target,run):
        from adapters.script_journey.lock import ScriptSourceLock
        from adapters.pico4.create_management import configuration
        identifier(run);need(configuration(os.environ) is not None)
        self.adapter,self.target,self.run=adapter,target,run
        key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
        parent=adapter.pico_configuration[1]
        self.parent,self.key=parent,key
        self.lock=ScriptSourceLock(parent/('normal-create-sources-'+key+'.lock'))

    def store(self,role,ticket=None):
        from adapters.normal_feature_state import PrivateFeatureState
        return PrivateFeatureState(self.parent/('create-picker-'+role+'-'+self.key+'-'+self.run+('-'+ticket if ticket else '')+'.json'))

    @staticmethod
    def owned_target(adapter,target):
        from adapters.normal_feature_state import PrivateFeatureState
        if adapter.pico_configuration is None:return False
        parent=adapter.pico_configuration[1]
        key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
        PrivateFeatureState(parent/'create-picker-parent-check.json')._parent()
        found=False
        for path in parent.glob('create-picker-*-'+key+'-*.json'):
            need(re.fullmatch(r'create-picker-(?:owner|callbacks|dialogs|entities|setting|files)-'+key+r'-[0-9a-f]{32}(?:-[0-9a-f]{32})?\.json',path.name))
            found=PrivateFeatureState(path).read() is not None or found
        return found

    def owned(self):
        # Retain orphaned source journals after a host-only retirement error.
        return any(self.store(role).read() is not None for role in ('owner','callbacks','dialogs','entities','setting'))

    def flow(self):
        from adapters.pico4.create_files import NativeCreateFiles,OwnedCreateFiles,FILE
        from adapters.pico4.create_file_ui import PicoCreateFileIO
        self.lock.assert_held()
        need(not self.adapter._create_management(self.target).owned() and not self.adapter._create_models_owned(self.target))
        regular,_ui=self.adapter._script_paths(self.target)
        from adapters.normal_feature_state import PrivateFeatureState
        need(PrivateFeatureState(regular).read() is None)
        ui,_observe,binding=self.adapter._script_runtime(self.target)
        native=self.adapter._native_feature_observer(self.target)
        callbacks=OriginalReader(self.adapter._create_callback_observer(self.target),self.store('callbacks'),binding)
        dialogs=OriginalReader(self.adapter._create_dialog_observer(self.target),self.store('dialogs'),binding)
        entities=OriginalReader(self.adapter._create_entity_observer(self.target,self.run),self.store('entities'),binding)
        from adapters.pico4.create_browse_setting import OwnedCreateBrowseSetting
        setting=OwnedCreateBrowseSetting(self.adapter._create_browse_setting_native(self.target),self.store('setting'),binding)
        def files(ticket):
            original=NativeCreateFiles(native.send,
                lambda:self.adapter.adb.read_debug_app_file(self.target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,ticket=ticket,monotonic=native.monotonic,sleep=native.sleep)
            return OwnedCreateFiles(original,self.store('files',ticket),binding)
        def file_ui(intent,step):
            return self.adapter._create_file_controls(self.target,intent,step['directory'],self.run,step['ticket'],
                step['role'],step['beforeUi'])
        from pathlib import Path
        source={}
        for role,name in (('import','edit.js'),('export','entityList/entityList.js')):
            code=(Path(__file__).resolve().parents[4]/('scripts/system/create/'+name)).read_text(encoding='utf-8').encode('utf-16le')
            source[role]=dict(sha256=hashlib.sha256(code).hexdigest(),codeUnits=len(code)//2)
        return OwnedCreatePicker(self.store('owner'),binding,lambda intent:self.adapter._create_controls(self.target,intent),
            file_ui,PicoCreateFileIO(ui.io),files,callbacks,dialogs,entities,setting,source,monotonic=ui.monotonic,sleep=ui.sleep)

    def invoke(self,operation,*,ticket=None,fixture_url=None):
        need(operation in ('open','open-export','cancel','import','export','delete','reconcile','release'))
        with self.lock.held():
            flow=self.flow()
            if operation in ('open','open-export'):
                return (flow.open if operation=='open' else flow.open_export)(self.run,ticket,fixture_url)
            need(ticket is None and fixture_url is None)
            if operation=='release' and flow.previous is None:
                # No effectful code precedes the main owner/file reservation.
                # Orphaned read-only sources may retire only under fresh proof.
                need(not any(self.parent.glob('create-picker-files-'+self.key+'-'+self.run+'-*.json')))
                return flow.release_observations()
            return getattr(flow,{'import':'import_file','export':'export_file','delete':'delete_import'}.get(operation,operation))()
