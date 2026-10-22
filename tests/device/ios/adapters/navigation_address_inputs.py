"""Durable ordinary Go To inputs and retained QML root ownership.

This wraps the existing IOSNavigation recipe. It neither replaces the scene
oracle nor treats a hidden root, a delivered input or a lost response as clean.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
import uuid
from urllib.parse import quote

from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUI
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import navigation_address_roots as roots
from ios.adapters.normal_input import NativeInput
from ios.adapters.normal_navigation import IOSNavigation

VERSION=1
ORDER=('hud.goto','address.field','replace','address.go')


def transfer_original(value,binding,run,ui):
    """Validate a retained owner and its actual pre-stop root, with no SDK IO.

    The enclosing restart owner must retain this original private carrier and
    independently prove old kernel-process death. This alone retires nothing.
    """
    context(binding);identifier(run)
    owner=object.__new__(NavigationAddressInputs);owner.binding=deepcopy(binding);owner.run=run
    state=owner.decode(value);need(state['lease'] is not None and state['rows']
        and all(row['phase']=='acknowledged' for row in state['rows']))
    last=state['rows'][-1];roots.follow(last['captures'][-1],ui)
    actual=roots.current(state['lease'],ui,closed=True)
    need(all(root['field']['text']==last['url'] for root in roots.packet(binding,ui)['roots']))
    from adapters.native_clock_join import digest
    return dict(ownerSha256=digest(value),root=actual)


class NavigationAddressInputs:
    def __init__(self,store,binding,run,lock,guard,ui,native,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        context(binding);identifier(run)
        pid=int(binding['processIdentity']);need(pid>0 and str(pid)==binding['processIdentity'])
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
             and isinstance(ui,NativeUI) and isinstance(native,NativeInput)
             and all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        need(store.path.name=='ios-navigation-address-'+binding['processIdentity']+'-inputs.json'
             and lock.path==store.path.with_name('script-feature-sources.lock')
             and native.session==binding['sessionId'] and ui.base=='/session/'+quote(binding['sessionId'],safe=''))
        self.store,self.binding,self.run,self.lock,self.guard=store,deepcopy(binding),run,lock,guard
        self.ui,self.native,self.epoch_ms,self.monotonic=ui,native,epoch_ms,monotonic
        lock.assert_held();self.previous=store.read();self.state=dict(lease=None,rows=[]) if self.previous is None else self.decode(self.previous)
        self.active=None;self.lookups={};self.started=None;self.failed=False

    def envelope(self,state):
        return dict(iosNavigationAddressInputsVersion=VERSION,binding=self.binding,runId=self.run,payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosNavigationAddressInputsVersion','binding','runId','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosNavigationAddressInputsVersion']) is int
            and value['iosNavigationAddressInputsVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'lease','rows'});need(type(state['rows']) is list and len(state['rows'])<=32)
        lease=state['lease'];admitted=False;prior=None;keys=set()
        openings=[e['intent'] for r in state['rows'] for e in r['intents'] if e['kind']=='hud.goto']
        if lease is not None:
            roots.validate(lease);need(same(lease['binding'],self.binding) and lease['runId']==self.run)
        for index,row in enumerate(state['rows']):
            exact(row,{'key','url','phase','component','captures','intents','closed'})
            need(row['key'] in ('enter','return') and row['key'] not in keys and type(row['url']) is str
                 and row['phase'] in ('issued','acknowledged') and type(row['component']) is dict
                 and set(row['component'])<= {'iosNormalNavigation'}
                 and type(row['captures']) is list and len(row['captures'])<=32
                 and type(row['intents']) is list and len(row['intents'])<=4)
            keys.add(row['key']);need(index==len(state['rows'])-1 or row['phase']=='acknowledged')
            for packet in row['captures']:
                projected=roots.packet(self.binding,packet)
                if prior is not None:roots.follow(prior,packet)
                if lease is not None and same(packet,lease['opened']):
                    need(not admitted and any(same(event,lease['opening']) for event in openings));admitted=True
                if admitted:roots.current(lease,packet)
                else:need(not projected['roots'])
                prior=packet
            for ordinal,event in enumerate(row['intents']):
                exact(event,{'kind','intent','receipt'});need(event['kind']==ORDER[ordinal])
                intent=event['intent']
                if ordinal==2:
                    exact(intent,{'original','command'});packet=intent['original'];command=intent['command']
                    roots.packet(self.binding,packet);exact(command,{'schemaVersion','commandId','instance','sequence','observedElapsedMs','fieldToken','operation','text'})
                    need(type(command['schemaVersion']) is int and command['schemaVersion']==1
                         and str(uuid.UUID(command['commandId']))==command['commandId']
                         and command['instance']==packet['instance'] and type(command['sequence']) is int
                         and command['sequence']==packet['lastSequence']+1 and command['observedElapsedMs']==packet['elapsedMs']
                         and command['operation']=='replace' and command['text']==row['url'])
                    controls=[c for c in packet['controls'] if c['id']=='address.field' and c['focused'] and c['enabled']]
                    need(len(controls)==1 and controls[0]['token']==command['fieldToken'])
                    receipt=event['receipt']
                    if receipt is not None:
                        exact(receipt,{'schemaVersion','commandId','status'})
                        need(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1
                             and type(receipt['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',receipt['commandId']))
                        status=receipt['status'];exact(status,{'schemaVersion','commandId','instance','sequence','performed','processId','sampleEpochMs'})
                        need(type(status['schemaVersion']) is int and status['schemaVersion']==1
                             and status['commandId']==command['commandId'] and status['instance']==packet['instance']
                             and type(status['sequence']) is int and status['sequence']==command['sequence'] and status['performed'] is True
                             and type(status['processId']) is int and status['processId']==int(self.binding['processIdentity'])
                             and type(status['sampleEpochMs']) is int and packet['sampleEpochMs']<=status['sampleEpochMs']<=packet['sampleEpochMs']+1500)
                else:
                    exact(intent,{'method','path','body','original','lookup'});lookup=intent['lookup']
                    exact(lookup,{'using','value','elements'});need(lookup['using']=='accessibility id'
                        and lookup['value']=='OverteNavigation.'+event['kind'] and len(lookup['elements'])==1
                        and intent['method']=='POST' and intent['body']=={}
                        and intent['path']==NativeUI._element(lookup['elements'][0])+'/click')
                    roots.packet(self.binding,intent['original'])
                    need(event['receipt'] is None or event['receipt']=={'returned':True})
                need(any(same(intent['original'],p) for p in row['captures']))
                if ordinal<len(row['intents'])-1 or row['phase']=='acknowledged':need(event['receipt'] is not None)
            if row['phase']=='acknowledged':
                need(lease is not None and len(row['intents'])==4 and row['captures'] and admitted)
                need(same(row['closed'],roots.current(lease,row['captures'][-1],closed=True)))
                need(row['closed']['original']['lastSequence']==row['intents'][2]['intent']['command']['sequence'])
            else:need(row['closed'] is None)
        need(lease is None or admitted);return deepcopy(state)

    def bound(self):
        self.lock.assert_held();need(not self.failed and self.guard() is not False and same(self.store.read(),self.previous))
        if self.started is not None:need(0<=self.monotonic()-self.started<30)

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        try:
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:self.failed=True;raise

    def capture(self):
        self.bound();need(self.active is not None);packet=self.native.capture();self.bound()
        current=roots.packet(self.binding,packet)
        previous=next((r['captures'][-1] for r in reversed(self.state['rows']) if r['captures']),None)
        if previous is not None:roots.follow(previous,packet)
        if self.state['lease'] is None and current['roots']:
            need(self.active['intents'] and self.active['intents'][0]['kind']=='hud.goto')
            self.state['lease']=roots.admit(self.binding,self.run,self.active['intents'][0]['intent'],packet)
        elif self.state['lease'] is not None:roots.current(self.state['lease'],packet)
        else:need(not current['roots'])
        need(len(self.active['captures'])<32);self.active['captures'].append(deepcopy(packet));self.save();return packet

    def fresh(self,before,after):
        now,mono=self.epoch_ms(),self.monotonic()
        need(number(now,after[0],before[0]+1500) and number(mono,after[1],before[1]+1.5)
             and now-before[0]<1500 and mono-before[1]<1.5)

    def intent(self,kind,value):
        self.bound();events=self.active['intents'];need(len(events)<4 and kind==ORDER[len(events)]
            and (not events or events[-1]['receipt'] is not None))
        event=dict(kind=kind,intent=deepcopy(value),receipt=None);events.append(event);self.save();return event

    def request(self,method,path,body=None):
        self.bound()
        if method=='POST' and path=='/elements':
            need(type(body) is dict and body.get('using')=='accessibility id')
            result=self.ui._request(method,path,body);self.bound()
            if body.get('value') in ('OverteNavigation.'+key for key in ORDER if key!='replace'):
                need(type(result) is list and len(result)<=1)
                if result:self.lookups[NativeUI._element(result[0])]=dict(body,elements=deepcopy(result))
            return result
        if method=='GET':return self.ui._request(method,path,body)
        need(method=='POST' and path.endswith('/click') and body=={})
        lookup=self.lookups.get(path[:-6]);need(lookup is not None);kind=lookup['value'].removeprefix('OverteNavigation.')
        before=(self.epoch_ms(),self.monotonic());packet=self.capture();after=(self.epoch_ms(),self.monotonic())
        need(not packet['tabletShown'])
        if kind=='hud.goto':
            need(not roots.packet(self.binding,packet)['addressDialog'])
            if self.state['lease'] is not None:
                roots.current(self.state['lease'],packet,closed=True)
                previous=self.state['rows'][-2];need(previous['phase']=='acknowledged')
                need(all(r['field']['text']==previous['url'] for r in roots.packet(self.binding,packet)['roots']))
        else:
            need(self.state['lease'] is not None and roots.packet(self.binding,packet)['addressDialog'])
            root=roots.packet(self.binding,packet)['roots'][0]
            if kind=='address.go':need(root['field']['text']==self.active['url'])
        event=self.intent(kind,dict(method=method,path=path,body=body,original=packet,lookup=lookup))
        self.fresh(before,after);self.bound();result=self.ui._request(method,path,body)
        event['receipt']={'returned':True};self.save();return result

    def edit(self,operation,text):
        need(operation=='replace' and text==self.active['url'])
        before=(self.epoch_ms(),self.monotonic());packet=self.capture();after=(self.epoch_ms(),self.monotonic())
        fields=[c for c in packet['controls'] if c['id']=='address.field' and c['enabled'] and c['focused']]
        need(len(fields)==1)
        command=dict(schemaVersion=1,commandId=str(uuid.uuid4()),instance=packet['instance'],sequence=packet['lastSequence']+1,
            observedElapsedMs=packet['elapsedMs'],fieldToken=fields[0]['token'],operation=operation,text=text)
        event=self.intent('replace',dict(original=packet,command=command));self.fresh(before,after);self.bound()
        result=self.native.deliver(command);need(result=={'performed':True})
        event['receipt']=deepcopy(self.native.last_receipt);self.save();return result

    def goto(self,key,url,profile,allowed):
        self.bound();need(self.active is None and key in ('enter','return') and url in allowed)
        old=[r for r in self.state['rows'] if r['key']==key]
        if old:
            need(old[0]['phase']=='acknowledged' and old[0]['url']==url);self.decode(self.previous);return deepcopy(old[0]['closed'])
        need(not self.state['rows'] or self.state['rows'][-1]['phase']=='acknowledged')
        row=dict(key=key,url=url,phase='issued',component={},captures=[],intents=[],closed=None)
        self.state['rows'].append(row);self.active=row;self.started=self.monotonic();self.save()
        owner=self
        class Ui(NativeUI):
            def _request(_self,*args,**kwargs):return owner.request(*args,**kwargs)
        class Native:
            def capture(_self):return owner.capture()
            def edit(_self,*args):return owner.edit(*args)
        ui=Ui(self.ui.client,self.binding['sessionId'],self.bound,timeout=self.ui.timeout,monotonic=self.ui.monotonic,sleep=self.ui.sleep)
        try:
            flow=IOSNavigation(ui,Native(),profile,row['component'],self.save);flow.urls=set(allowed)
            flow.invoke('places.goto',dict(url=url));packet=self.capture()
            row.update(phase='acknowledged',closed=roots.current(self.state['lease'],packet,closed=True));self.save()
            return deepcopy(row['closed'])
        finally:self.active=None;self.started=None

    def observe_pending(self):
        """Retain actual responsibility after a lost input return, without input.

        This does not acknowledge, finish or replay the interrupted recipe.
        An actual new root can be owned from the original pre-delivery HUD
        journal even when its SDK response was lost.
        """
        self.bound();need(self.active is None and self.state['rows'] and self.state['rows'][-1]['phase']=='issued')
        self.active=self.state['rows'][-1]
        try:
            packet=self.capture();lease=self.state['lease']
            return dict(original=deepcopy(packet),root=None if lease is None else roots.current(lease,packet))
        finally:self.active=None
