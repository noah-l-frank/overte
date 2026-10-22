"""One ordinary Cancel on the actual root reopened by owned lookup failure.

Hidden roots remain retained responsibility. Neither this input acknowledgment
nor visible closure establishes QObject death or final Worlds cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,NativeUIError,Locator
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.navigation_address_inputs import NavigationAddressInputs
from ios.adapters import navigation_address_roots as roots

VERSION=1


class NavigationAddressDismiss:
    def __init__(self,store,address,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(address,NavigationAddressInputs)
            and callable(epoch_ms) and callable(monotonic))
        address.bound();self.store,self.address,self.lock=store,address,address.lock
        self.binding,self.run=address.binding,address.run
        need(store.path==address.store.path.with_name('ios-navigation-address-dismiss-'+self.binding['processIdentity']+'.json'))
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        self.previous=store.read();self.state=None if self.previous is None else self.decode(self.previous)
        self.lookup=self.last_mono=None

    def envelope(self,state):
        return dict(iosNavigationAddressDismissVersion=VERSION,binding=self.binding,runId=self.run,payload=pack([state]))

    def original_address(self,value):
        checker=object.__new__(NavigationAddressInputs);checker.binding=self.binding;checker.run=self.run
        state=checker.decode(value)
        need(state['lease'] is not None and state['rows'] and state['rows'][-1]['key']=='missing'
            and all(row['phase']=='acknowledged' for row in state['rows']))
        return state

    def packet(self,state,value,*,closed=False):
        original=self.original_address(state['addressOriginal'])
        roots.follow(original['rows'][-1]['captures'][-1],value)
        actual=roots.current(original['lease'],value,closed=closed)
        need(not value['tabletShown'] and not any(row['id'].startswith('navigation.error.') for row in value['controls']))
        need(all(row['field']['text']==original['rows'][-1]['url'] for row in roots.packet(self.binding,value)['roots']))
        return actual

    def decode(self,value):
        exact(value,{'iosNavigationAddressDismissVersion','binding','runId','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosNavigationAddressDismissVersion']) is int
            and value['iosNavigationAddressDismissVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','started','addressOriginal','before','intent','returned','after','root'})
        need(state['phase'] in ('checking','issued','complete') and type(state['returned']) is bool)
        exact(state['started'],{'epochMs','monotonic'})
        need(number(state['started']['epochMs'],1,1e15) and number(state['started']['monotonic'],0,1e15))
        self.original_address(state['addressOriginal'])
        for key in ('before','after'):
            if state[key] is not None:self.packet(state,state[key],closed=key=='after')
        if state['intent'] is not None:
            need(state['phase'] in ('issued','complete'))
            intent=state['intent'];exact(intent,{'lookup','path','original'})
            exact(intent['lookup'],{'using','value','elements'})
            need(intent['lookup']['using']=='accessibility id' and intent['lookup']['value']=='OverteNavigation.address.cancel'
                and type(intent['lookup']['elements']) is list and len(intent['lookup']['elements'])==1
                and intent['path']==NativeUI._element(intent['lookup']['elements'][0])+'/click')
            need(self.packet(state,intent['original'])['status']=='visible')
            need(state['before'] is not None);roots.follow(state['before'],intent['original'])
        if state['phase']=='issued':need(state['intent'] is not None)
        if state['returned']:need(state['intent'] is not None)
        if state['after'] is not None:
            need(state['before'] is not None);roots.follow(state['before'],state['after'])
            if state['intent'] is not None:need(state['returned']);roots.follow(state['intent']['original'],state['after'])
        if state['phase']=='complete':need(state['after'] is not None and same(state['root'],self.packet(state,state['after'],closed=True)))
        else:need(state['root'] is None)
        return deepcopy(state)

    def bound(self):
        self.address.bound();need(same(self.store.read(),self.previous))
        if self.state is not None:
            old=self.original_address(self.state['addressOriginal']);current=self.address.state
            need(same(old['lease'],current['lease']) and same(current['rows'][:len(old['rows'])],old['rows']))

    def clock(self):
        first=self.state['started'];epoch,mono=self.epoch_ms(),self.monotonic()
        need(number(epoch,first['epochMs'],first['epochMs']+30000) and epoch-first['epochMs']<30000
            and number(mono,first['monotonic'],first['monotonic']+30) and mono-first['monotonic']<30
            and (self.last_mono is None or mono>=self.last_mono)
            and abs(epoch-first['epochMs']-(mono-first['monotonic'])*1000)<=250)
        self.last_mono=mono

    def save(self):
        self.bound();self.clock();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.clock()

    def capture(self):
        self.bound();self.clock();value=self.address.native.capture();self.bound();self.clock();self.packet(self.state,value)
        return value

    def request(self,method,path,body=None):
        self.bound();self.clock()
        if method=='POST' and path=='/elements':
            need(body==dict(using='accessibility id',value='OverteNavigation.address.cancel'))
            result=self.address.ui._request(method,path,body);self.bound();self.clock()
            need(type(result) is list and len(result)<=1)
            if result:self.lookup=dict(body,elements=deepcopy(result))
            return result
        if method=='GET':return self.address.ui._request(method,path,body)
        need(method=='POST' and body=={} and self.lookup is not None and self.state['phase']=='checking'
            and self.state['intent'] is None and path==NativeUI._element(self.lookup['elements'][0])+'/click')
        original=self.capture();need(self.packet(self.state,original)['status']=='visible')
        self.state.update(phase='issued',intent=dict(lookup=deepcopy(self.lookup),path=path,original=deepcopy(original)))
        self.save();self.bound();self.clock()
        result=self.address.ui._request(method,path,body)
        self.state['returned']=True;self.save();return result

    def close(self):
        self.bound()
        if self.state is not None:
            need(same(self.envelope(self.state),self.previous))
            if self.state['phase']=='complete':self.decode(self.previous);return deepcopy(self.state['root'])
            raise NativeUIError('Original address Cancel remains owned and is not repeated')
        original=deepcopy(self.address.store.read());self.original_address(original)
        self.state=dict(phase='checking',started=dict(epochMs=self.epoch_ms(),monotonic=self.monotonic()),
            addressOriginal=original,before=None,intent=None,returned=False,after=None,root=None);self.save()
        self.state['before']=self.capture();self.save()
        if self.packet(self.state,self.state['before'])['status']=='visible':
            owner=self
            class UI(NativeUI):
                def _request(_self,*args,**kwargs):return owner.request(*args,**kwargs)
            source=self.address.ui
            ui=UI(source.client,self.binding['sessionId'],self.bound,timeout=source.timeout,
                monotonic=source.monotonic,sleep=source.sleep)
            ui.click(Locator('accessibility id','OverteNavigation.address.cancel'))
        self.state['after']=self.capture();self.packet(self.state,self.state['after'],closed=True);self.save()
        return self.recover()

    def recover(self):
        """Only the fully retained return; no source acquisition or new input."""
        self.bound();need(self.state is not None and self.state['after'] is not None
            and same(self.envelope(self.state),self.previous))
        if self.state['phase']=='complete':self.decode(self.previous);return deepcopy(self.state['root'])
        self.state['root']=self.packet(self.state,self.state['after'],closed=True)
        self.state['phase']='complete';self.save();return deepcopy(self.state['root'])
