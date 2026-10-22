"""Pico parent join of original Runner Settings and actual client rights.

This module only reads the feature fixture. It has no domain-control token,
permission mutation method, native permission setter or new phase activation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import hashlib
import secrets
from adapters.native_feature_observation import exact,fresh,need,number,decode
from adapters.normal_feature_state import context
from feature_journeys.contract import typed_equal
from feature_journeys.create_permissions import receipt
from fixture.pico_create_permissions import rows
from fixture.create_permissions import REZ


def validate_source(value,run,domain,previous=None):
    exact(value,{'createPermissionSourceVersion','instance','runId','requestId','original','events','current','phaseInstance','phaseActivations'})
    from feature_journeys.contract import identifier
    need(type(value['createPermissionSourceVersion']) is int and value['createPermissionSourceVersion']==1 and value['runId']==run)
    for key in ('instance','requestId','phaseInstance'):identifier(value[key])
    rows(value['original']);receipt(value['current'],domain)
    need(type(value['events']) is list and len(value['events'])<=256 and type(value['phaseActivations']) is list)
    seen=set();sequence=0;positions=[]
    for event in value['events']:
        exact(event,{'ticket','operation','allowed','receipt'});identifier(event['ticket'])
        need(event['ticket'] not in seen and event['operation'] in ('set','restore') and type(event['allowed']) is bool)
        seen.add(event['ticket']);actual=receipt(event['receipt'],domain)
        need(actual['sequence']>sequence and actual['sequence']<=value['current']['sequence']);sequence=actual['sequence']
        target=deepcopy(value['original'])
        if event['operation']=='set':
            for row in target:
                for key in REZ:row[key]=event['allowed']
        need(actual['standard']==target and actual['restored']==(event['operation']=='restore'))
        positions.extend(i for i,row in enumerate(value['phaseActivations']) if row['ticket']==event['ticket'])
        matches=[row for row in value['phaseActivations'] if row['ticket']==event['ticket']]
        need(len(matches)==1 and actual['capturedEpochMs']>=matches[0]['activatedEpochMs'])
        expected=dict(verb='set-rez-permission',inputs=dict(allowed=event['allowed'])) if event['operation']=='set' else dict(verb='cleanup',inputs={})
        need(typed_equal(matches[0]['stimulus'],expected))
    need(positions==sorted(set(positions)))
    if value['events']:
        need(value['current']['standard']==value['events'][-1]['receipt']['standard']
            and value['current']['restored']==value['events'][-1]['receipt']['restored'])
    else:need(value['current']['standard']==value['original'] and not value['current']['restored'])
    if previous is not None:
        validate_source(previous,run,domain)
        need(all(value[k]==previous[k] for k in ('instance','runId','original','phaseInstance'))
            and value['requestId']!=previous['requestId'] and value['current']['sequence']>previous['current']['sequence']
            and value['current']['capturedEpochMs']>=previous['current']['capturedEpochMs']
            and typed_equal(value['events'][:len(previous['events'])],previous['events'])
            and typed_equal(value['phaseActivations'][:len(previous['phaseActivations'])],previous['phaseActivations']))
    return value


class CreateRez:
    def rez_state(self):
        store=self.source_store('rez');value=store.read()
        if value is not None:
            exact(value,{'createRezOwnerVersion','binding','runId','source','effects'})
            need(type(value['createRezOwnerVersion']) is int and value['createRezOwnerVersion']==1
                and context(value['binding'])==context(self.state()['binding']) and value['runId']==self.run)
            baseline=self.state()['baselineEntities'];domain=baseline['source']['domainId']
            validate_source(value['source'],self.run,domain)
            need(type(value['effects']) is list and len(value['effects'])<=32)
            tickets=set()
            for effect in value['effects']:
                exact(effect,{'ticket','cleanup','settings','native','sha256'})
                need(type(effect['cleanup']) is bool and effect['ticket'] not in tickets and type(effect['native']) is str
                    and hashlib.sha256(effect['native'].encode()).hexdigest()==effect['sha256'])
                tickets.add(effect['ticket']);source=effect['settings'];validate_source(source,self.run,domain)
                need(source['instance']==value['source']['instance'] and source['original']==value['source']['original']
                    and typed_equal(value['source']['events'][:len(source['events'])],source['events'])
                    and source['events'][-1]['ticket']==effect['ticket']
                    and source['events'][-1]['operation']==('restore' if effect['cleanup'] else 'set'))
                packet=decode(effect['native'])
                from adapters.pico4.create_entities import validate
                validate(packet,packet['requestId'],baseline['processId'],packet['capturedEpochMs'],self.run)
                from adapters.pico4.create_picker_owner import OwnedCreatePicker
                OwnedCreatePicker.same_scene_identity(baseline,packet)
                expected=(baseline['source']['canRez'],baseline['source']['canRezTmp']) if effect['cleanup'] else (source['events'][-1]['allowed'],)*2
                need((packet['source']['canRez'],packet['source']['canRezTmp'])==expected
                    and packet['capturedEpochMs']>=source['phaseActivations'][-1]['activatedEpochMs'])
        return value
    def rez_read(self):
        root=self.state();previous=self.rez_state();started=self.source.monotonic();epoch=self.source.epoch_ms()
        phase=self.source.read(root['phase']);nonce=secrets.token_hex(16)
        value=self.source.client.request('/runs/'+self.run+'/create-permissions',phase_nonce=nonce)
        validate_source(value,self.run,root['baselineEntities']['source']['domainId'],None if previous is None else previous['source'])
        need(value['requestId']==nonce and value['phaseInstance']==phase['status']['instance']
            and typed_equal(value['phaseActivations'],phase['status']['activations']))
        after=self.source.read(phase['status']);need(typed_equal(after['status']['activations'],phase['status']['activations']))
        now=self.source.monotonic();native=self.source.epoch_ms()
        need(number(started,0,1e15) and number(epoch,1,1e15) and number(now,started,1e15) and number(native,epoch,1e15))
        effective=math.ceil(max(native,epoch+math.ceil((now-started)*1000)));fresh(value['current']['capturedEpochMs'],effective)
        current=dict(createRezOwnerVersion=1,binding=deepcopy(root['binding']),runId=self.run,source=deepcopy(value),effects=[] if previous is None else deepcopy(previous['effects']))
        store=self.source_store('rez');store.write(current,previous);need(store.read()==current)
        fresh(value['current']['capturedEpochMs'],math.ceil(max(self.source.epoch_ms(),epoch+math.ceil((self.source.monotonic()-started)*1000))))
        return value
    def rez_admit(self,values):
        phase=self.source.read(self.state()['phase'])
        need(phase['ticket']==values['ticket'] and phase['verb']==values['verb'] and typed_equal(phase['inputs'],values['inputs']))
        source=self.rez_read();need(bool(source['events']))
        event=source['events'][-1]
        need(event['ticket']==values['ticket'] and event['operation']=='set' and event['allowed']==values['inputs']['allowed'])
    def rez_target(self,source):
        baseline=self.state()['baselineEntities']['source']
        if source['current']['restored'] or not source['events']:
            need(source['current']['standard']==source['original'])
            return baseline['canRez'],baseline['canRezTmp']
        event=source['events'][-1];need(event['operation']=='set')
        return event['allowed'],event['allowed']
    def rez_scene(self,before,after):
        from adapters.pico4.create_picker_owner import OwnedCreatePicker
        if self.rez_state() is None:
            OwnedCreatePicker.same_scene(before,after);return None
        OwnedCreatePicker.same_scene_identity(before,after)
        source=self.rez_read()
        rights=(after['source']['canRez'],after['source']['canRezTmp'])
        targets=[self.rez_target(source)]
        if source['events']:
            earlier=source['events'][:-1]
            baseline=self.state()['baselineEntities']['source']
            targets.append((earlier[-1]['allowed'],earlier[-1]['allowed']) if earlier and earlier[-1]['operation']=='set'
                else (baseline['canRez'],baseline['canRezTmp']))
        need(rights in targets)
        return source
    def rez_ready(self,actual,*,cleanup=False):
        source=actual.get('rez');need(source is not None)
        native=actual['entities']['source'];target=self.rez_target(source)
        if cleanup:
            need(source['current']['restored'] and source['current']['standard']==source['original'])
        return (native['canRez'],native['canRezTmp'])==target
    def rez_archive(self,actual,cleanup):
        previous=self.rez_state();source=actual['rez'];ticket=source['events'][-1]['ticket']
        if any(effect['ticket']==ticket for effect in previous['effects']):return
        raw=self.readers['entities'].reader.last_raw
        need(type(raw) is str and decode(raw)==actual['entities'])
        effect=dict(ticket=ticket,cleanup=cleanup,settings=deepcopy(source),native=raw,sha256=hashlib.sha256(raw.encode()).hexdigest())
        current=deepcopy(previous);current['effects'].append(effect)
        self.source_store('rez').write(current,previous);need(self.rez_state()==current)
    def rez_settle(self,*,cleanup=False):
        ui,_binding=self.runtime();started=ui.monotonic();quiet=None;clocks=None
        for attempt in range(103):
            actual=self.sample();now=ui.monotonic();source=actual['rez']
            from adapters.pico4.create_models import idle
            from adapters.pico4.create_callbacks import active
            ready=self.rez_ready(actual,cleanup=cleanup) and idle(actual['scope']) and not active(actual['callbacks'])
            epoch=(actual['entities']['capturedEpochMs'],source['current']['capturedEpochMs'],actual['work']['source']['work']['capturedEpochMs'])
            if ready:
                quiet=now if quiet is None else quiet;clocks=epoch if clocks is None else clocks
                if now-quiet>=3 and all(b-a>=3000 for a,b in zip(clocks,epoch)):
                    self.phase_fence();self.fresh_sample(actual);self.rez_archive(actual,cleanup);self.phase_fence();self.fresh_sample(actual);return actual
            else:quiet=None;clocks=None
            need(now-started<20 and attempt<102);ui.sleep(.2)
        need(False)
    def rez_final(self,actual):
        if self.rez_state() is None:return
        need(self.rez_ready(actual,cleanup=self.state()['cleanupStarted']))
        call=self.state()['calls'][-1]
        if call['verb']=='set-rez-permission' and not self.state()['cleanupStarted']:
            event=actual['rez']['events'][-1]
            need(event['ticket']==call['ticket'] and event['operation']=='set' and event['allowed']==call['inputs']['allowed']
                and any(effect['ticket']==call['ticket'] and not effect['cleanup'] for effect in self.rez_state()['effects']))
    def rez_before_input(self):
        if self.rez_state() is not None:need(self.rez_ready(self.sample(),cleanup=self.state()['cleanupStarted']))
