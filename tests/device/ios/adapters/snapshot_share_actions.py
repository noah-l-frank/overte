"""Once-only normal Share UI slots; every effect needs separate originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import re
import time
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUI,NativeUIError,Locator,WEBDRIVER_KEYS
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.snapshot_share_query_owner import host_clock


FIELDS={
    'system-select':set(),'system-cancel':set(),
    'snapshot.share.receive':{'snapshot.share.run','snapshot.share.basename'},
    'snapshot.share.inspect':{'snapshot.share.query'},'snapshot.share.finish':set(),'snapshot.share.cancel':set(),
    'snapshot.share.archive.import':{'snapshot.share.archive.run'},
    'snapshot.share.archive.chunk':{'snapshot.share.archive.query','snapshot.share.archive.offset'},
    'snapshot.share.archive.retire':{'snapshot.share.archive.query'},
    'snapshot.share.archive.retire-inspect':{'snapshot.share.archive.query'}}


class SnapshotShareUIAction:
    _fields=FIELDS
    _store_prefix='share-normal-slot'
    _namespace='share-normal'
    _schema='shareNormalOutput'
    _owner_key='snapshotShareUIActionVersion'
    _frame_key='snapshotShareUIOutputVersion'
    _output_control='snapshot.share.inspect'
    _output_locator='snapshot.share.original'
    def __init__(self,root,lock,binding,run,index,plan,guard,*,client=None,session=None,epoch_ms=None,monotonic=time.monotonic,historical=False):
        self.root,self.lock,self.binding,self.run,self.index=root,lock,deepcopy(context(binding)),run,index
        need(integer(index,1,1024) and lock.path==root/'script-feature-sources.lock' and callable(guard));lock.assert_held()
        exact(plan,{'label','control','selector','fields'});need(type(plan['label']) is str and re.fullmatch('[a-z][a-z0-9-]{0,63}',plan['label'])
            and plan['control'] in self._fields and type(plan['fields']) is list and len(plan['fields'])<=2)
        names=set()
        for row in plan['fields']:
            need(type(row) in (tuple,list) and len(row)==2 and row[0] in self._fields[plan['control']] and row[0] not in names
                and type(row[1]) is str and 0<len(row[1].encode('utf-16le'))//2<=4096
                and all(ord(char)>=32 and ord(char)!=127 and ord(char) not in WEBDRIVER_KEYS for char in row[1]));names.add(row[0])
        need(names==self._fields[plan['control']]);self.plan=deepcopy(plan)
        if plan['control'].startswith('system-'):
            exact(plan['selector'],{'using','value'});need(plan['selector']['using']=='accessibility id');self.selector=Locator(**plan['selector'])
        else:need(plan['selector'] is None);self.selector=Locator('accessibility id',plan['control'])
        self.guard,self.epoch_ms,self.monotonic,self.historical=guard,epoch_ms,monotonic,historical
        need(historical or session==binding['sessionId']);self.store=PrivateFeatureState(root/(self._store_prefix+'-'+format(index,'04d')+'.json'))
        self.previous=self.store.read();self.state=dict(fields=[dict(element=None,cleared=False,written=False) for _ in plan['fields']],button=None,issued=False,before=None,returned=False,output=None,wire=None,proof=None)
        self.files=OriginalFrameStore(root,self.binding,run,'primary',self.bound,self.intent,namespace=self._namespace,schema_prefix=self._schema,monotonic=monotonic)
        if not historical:self.ui=NativeUI(client,session,self.bound,timeout=1,monotonic=monotonic,sleep=lambda _:None)
        if self.previous is not None:self.state=self.load(self.previous)
    def envelope(self):return {self._owner_key:1,'binding':self.binding,'runId':self.run,'index':self.index,'plan':self.plan,'payload':pack([self.state])}
    def bound(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous) and self.guard() is not False);return True
    def save(self):
        need(not self.historical);self.bound();value=self.envelope();self.store.write(value,self.previous);need(same(value,self.store.read()));self.previous=deepcopy(value)
    @staticmethod
    def element(value):need(value is None or type(value) is str and re.fullmatch('/element/[A-Za-z0-9_.:%-]{1,480}',value))
    def load(self,value):
        exact(value,{self._owner_key,'binding','runId','index','plan','payload'});rows=unpack(value['payload']);need(len(rows)==1)
        state=rows[0];prior=self.state;self.state=state
        try:need(type(value[self._owner_key]) is int and value[self._owner_key]==1 and same(value,self.envelope()))
        finally:self.state=prior
        exact(state,set(prior));need(type(state['fields']) is list and len(state['fields'])==len(self.plan['fields'])
            and type(state['issued']) is bool and type(state['returned']) is bool and (not state['returned'] or state['issued']))
        for row in state['fields']:
            exact(row,{'element','cleared','written'});self.element(row['element'])
            need(type(row['cleared']) is bool and type(row['written']) is bool and (not row['written'] or row['cleared']))
        self.element(state['button']);self.element(state['output'])
        if state['issued']:need(state['button'] is not None and all(row['written'] for row in state['fields']));host_clock(state['before'])
        else:need(state['before'] is None)
        if state['wire'] is not None:self.files.original(state['wire']);need(state['issued'] and state['proof'] is None)
        if state['proof'] is not None or state['wire'] is not None and state['wire']['phase']!='planned':self.original(state)
        return deepcopy(state)
    def intent(self,kind,value):
        need(kind=='original' and self.state['issued'] and self.state['proof'] is None);self.files.original(value);old=self.state['wire']
        if old is None:need(value['phase']=='planned')
        else:need((old['phase'],value['phase']) in (('planned','opened'),('opened','saved'))
            and all(same(old[key],value[key]) for key in old if key not in ('phase','file')) and (old['file'] is None or same(old['file'],value['file'])))
        self.state['wire']=deepcopy(value);self.save()
    def original(self,state=None):
        state=self.state if state is None else state;need(self.plan['control']==self._output_control)
        ref=state['wire'] if state['proof'] is None else self.files.expand(state['proof']);need(ref is not None)
        frame=self.files.read(ref);exact(frame,{self._frame_key,'plan','fields','button','output','hostBefore','hostAfter','raw'})
        need(type(frame[self._frame_key]) is int and frame[self._frame_key]==1 and same(frame['plan'],self.plan)
            and same(frame['fields'],state['fields']) and frame['button']==state['button'] and frame['output']==state['output']
            and state['issued'] is True and type(frame['raw']) is str and len(frame['raw'])<=349528)
        need(same(frame['hostBefore'],state['before']));host_clock(frame['hostBefore']);host_clock(frame['hostAfter'],frame['hostBefore'])
        raw=base64.b64decode(frame['raw'],validate=True);need(1<=len(raw)<=262144 and base64.b64encode(raw).decode()==frame['raw']);return raw
    def stamp(self):return dict(epochMs=self.epoch_ms(),monotonicMs=self.monotonic()*1000)
    def execute(self):
        need(not self.historical);self.bound()
        if self.previous is None:self.save()
        if not self.state['issued']:
            for index,(identifier,text) in enumerate(self.plan['fields']):
                row=self.state['fields'][index]
                if row['element'] is None:row['element']=self.ui._resolve(Locator('accessibility id',identifier));self.save()
                if not row['cleared']:row['cleared']=True;self.save();self.ui._request('POST',row['element']+'/clear',{})
                if not row['written']:
                    need(self.ui._request('GET',row['element']+'/text')=='');row['written']=True;self.save()
                    self.ui._request('POST',row['element']+'/value',dict(text=text,value=list(text)))
                need(self.ui._request('GET',row['element']+'/text')==text)
            if self.state['button'] is None:self.state['button']=self.ui._resolve(self.selector);self.save()
            self.ui._check();self.state['issued']=True;self.state['before']=self.stamp();self.save();self.ui._request('POST',self.state['button']+'/click',{})
            self.state['returned']=True;self.save()
        if self.plan['control']!=self._output_control:return dict(deliveryKnown=self.state['returned'],independentOutcomeRequired=True)
        if self.state['proof'] is not None:return self.original()
        if self.state['wire'] is not None:
            self.original();wire=self.state['wire'];need(wire['phase'] in ('opened','saved'))
            if wire['phase']=='opened':self.intent('original',dict(wire,phase='saved'));wire=self.state['wire']
            self.state['proof']=self.files.compact(wire)
        else:
            if self.state['output'] is None:
                element=self.ui._find_once(Locator('accessibility id',self._output_locator),require_enabled=False)
                if element is None:raise NativeUIError('Original Share journal view is unavailable')
                self.state['output']=element;self.save()
            raw=self.ui._request('GET',self.state['output']+'/attribute/value');after=self.stamp()
            need(type(raw) is str and 1<=len(raw.encode('utf-8'))<=262144)
            frame={self._frame_key:1,'plan':self.plan,'fields':deepcopy(self.state['fields']),'button':self.state['button'],'output':self.state['output'],
                'hostBefore':deepcopy(self.state['before']),'hostAfter':after,'raw':base64.b64encode(raw.encode('utf-8')).decode()}
            self.state['proof']=self.files.write(self.index,frame)
        self.state['wire']=None;self.save();return self.original()
    def qualified(self):
        self.original();ref=self.state['wire'] if self.state['proof'] is None else self.files.expand(self.state['proof']);frame=self.files.read(ref)
        need(frame['hostAfter']['monotonicMs']-frame['hostBefore']['monotonicMs']<5500
            and frame['hostAfter']['epochMs']-frame['hostBefore']['epochMs']<5500);return True
