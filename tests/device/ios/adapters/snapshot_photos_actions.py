"""One-send companion field/button slot and immutable original AFC output."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import re
import time
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUI,Locator,WEBDRIVER_KEYS
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same


class PhotosAction:
    def __init__(self,root,lock,binding,run,index,plan,guard,*,client=None,session=None,read=None,epoch_ms=None,monotonic=None,historical=False):
        self.root,self.lock,self.binding,self.run,self.index=root,lock,deepcopy(context(binding)),run,index
        need(integer(index,1,1024));self.plan=deepcopy(plan);exact(plan,{'label','fields','control','file','limit'})
        need(type(plan['label']) is str and re.fullmatch('[a-z][a-z0-9-]{0,63}',plan['label']) and type(plan['fields']) is list and 0<=len(plan['fields'])<=4
            and plan['control'] in {'snapshot.companion.photos','snapshot.companion.clock','snapshot.destination.read','snapshot.destination.inspect','snapshot.destination.delete','snapshot.destination.chunk','snapshot.destination.retire','snapshot.destination.retire-inspect'}
            and type(plan['file']) is str and re.fullmatch(r'(snapshot-companion-(photos|clock)\.json|snapshot-photos-(chunk|retire)\.json|snapshot-photos-[a-f0-9]{32}/photos-original\.json)',plan['file'])
            and integer(plan['limit'],1,720896))
        fields={'snapshot.companion.nonce','snapshot.destination.run','snapshot.destination.asset','snapshot.destination.basename','snapshot.destination.query','snapshot.destination.offset'}
        for row in plan['fields']:
            need(type(row) in (list,tuple) and len(row)==2 and row[0] in fields and type(row[1]) is str and len(row[1].encode('utf-16le'))//2<=4096
                and all(ord(char)>=32 and ord(char)!=127 and ord(char) not in WEBDRIVER_KEYS for char in row[1]))
        self.guard,self.read,self.epoch_ms,self.monotonic,self.historical=guard,read,epoch_ms,monotonic or time.monotonic,historical
        self.store=PrivateFeatureState(root/('photos-normal-slot-'+format(index,'04d')+'.json'));lock.assert_held();self.previous=self.store.read()
        self.state=dict(fields=[dict(element=None,cleared=False,written=False) for _ in plan['fields']],button=None,issued=False,wire=None,frame=None)
        self.frames=OriginalFrameStore(root,self.binding,run,'primary',self.bound,self.storage,namespace='photos-normal',schema_prefix='photosNormal',monotonic=self.monotonic)
        if not historical:self.ui=NativeUI(client,session,self.bound,timeout=1,monotonic=self.monotonic,sleep=lambda _:None)
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self):return dict(photosNormalActionVersion=1,binding=self.binding,runId=self.run,index=self.index,plan=self.plan,payload=pack([self.state]))
    def bound(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous) and self.guard() is not False);return True
    def save(self):
        self.bound();need(not self.historical);value=self.envelope();self.store.write(value,self.previous);need(same(value,self.store.read()));self.previous=deepcopy(value)
    def storage(self,event,wire):
        self.bound();need(event=='original' and self.state['issued'] and self.state['frame'] is None);self.state['wire']=deepcopy(wire);self.save();return True
    def decode(self,value):
        exact(value,{'photosNormalActionVersion','binding','runId','index','plan','payload'});rows=unpack(value['payload']);need(len(rows)==1)
        state=rows[0];prior=self.state;self.state=state
        try:need(type(value['photosNormalActionVersion']) is int and value['photosNormalActionVersion']==1 and same(value,self.envelope()))
        finally:self.state=prior
        exact(state,{'fields','button','issued','wire','frame'});need(type(state['fields']) is list and len(state['fields'])==len(self.plan['fields']) and type(state['issued']) is bool)
        for field in state['fields']:
            exact(field,{'element','cleared','written'});need(type(field['cleared']) is bool and type(field['written']) is bool and (not field['written'] or field['cleared']))
            need(field['element'] is None or type(field['element']) is str and re.fullmatch('/element/[A-Za-z0-9_.:%-]{1,480}',field['element']))
        need(state['button'] is None or type(state['button']) is str and re.fullmatch('/element/[A-Za-z0-9_.:%-]{1,480}',state['button']))
        if state['wire'] is not None:self.frames.original(state['wire']);need(state['issued'])
        if state['frame'] is not None:self.original(state)
        elif state['wire'] is not None and state['wire']['phase']!='planned':self.original(state)
        return deepcopy(state)
    def original(self,state=None):
        state=self.state if state is None else state;wire=state['wire'] if state['frame'] is None else self.frames.expand(state['frame'])
        need(wire is not None and wire['phase'] in ('opened','saved'));frame=self.frames.read(wire);exact(frame,{'photosNormalOutputVersion','plan','raw','hostBefore','hostAfter','inputs','button','issued'})
        need(type(frame['photosNormalOutputVersion']) is int and frame['photosNormalOutputVersion']==1 and same(frame['plan'],self.plan)
            and type(frame['raw']) is str and len(frame['raw'])<=4*((self.plan['limit']+2)//3)
            and frame['issued'] is True and same(frame['inputs'],state['fields']) and frame['button']==state['button'])
        raw=base64.b64decode(frame['raw'],validate=True);need(1<=len(raw)<=self.plan['limit'])
        before,after=frame['hostBefore'],frame['hostAfter']
        for clock in (before,after):exact(clock,{'epochMs','monotonic'})
        need(number(before['epochMs'],1,1e15) and number(after['epochMs'],before['epochMs'],before['epochMs']+1500)
            and number(before['monotonic'],0,1e15) and number(after['monotonic'],before['monotonic'],before['monotonic']+1.5)
            and abs((after['epochMs']-before['epochMs'])-(after['monotonic']-before['monotonic'])*1000)<=250)
        return decode(raw.decode('utf-8'),limit=self.plan['limit'])
    def original_bytes(self):
        self.original();wire=self.frames.expand(self.state['frame']) if self.state['frame'] is not None else self.state['wire']
        return base64.b64decode(self.frames.read(wire)['raw'],validate=True)
    def execute(self):
        self.bound();need(not self.historical)
        if self.state['frame'] is not None:return self.original()
        if self.previous is None:self.save()
        if self.state['wire'] is None:
            for index,(identifier,text) in enumerate(self.plan['fields']):
                field=self.state['fields'][index]
                if field['element'] is None:field['element']=self.ui._resolve(Locator('accessibility id',identifier));self.save()
                if not field['cleared']:field['cleared']=True;self.save();self.ui._request('POST',field['element']+'/clear',{})
                if not field['written']:
                    need(self.ui._request('GET',field['element']+'/text')=='');field['written']=True;self.save()
                    self.ui._request('POST',field['element']+'/value',dict(text=text,value=list(text)))
                need(self.ui._request('GET',field['element']+'/text')==text)
            if self.state['button'] is None:self.state['button']=self.ui._resolve(Locator('accessibility id',self.plan['control']));self.save()
            if not self.state['issued']:self.ui._check();self.state['issued']=True;self.save();self.ui._request('POST',self.state['button']+'/click',{})
            before=dict(epochMs=self.epoch_ms(),monotonic=self.monotonic());raw=self.read(self.plan['file'],self.plan['limit'])
            after=dict(epochMs=self.epoch_ms(),monotonic=self.monotonic());frame=dict(photosNormalOutputVersion=1,plan=self.plan,raw=base64.b64encode(raw).decode(),hostBefore=before,hostAfter=after,
                inputs=deepcopy(self.state['fields']),button=self.state['button'],issued=self.state['issued'])
            self.state['frame']=self.frames.write(self.index,frame);self.state['wire']=None;self.save()
        else:
            self.original();self.state['frame']=self.frames.compact(dict(self.state['wire'],phase='saved'));self.state['wire']=None;self.save()
        return self.original()
