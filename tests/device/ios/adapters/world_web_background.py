"""Once-only normal Home/activate with actual OS and native lifetime originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import arguments
from ios.adapters.graphics_lifecycle import IOSGraphicsBackground
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.world_web_api_clock import check
from ios.adapters.world_web_sources import WorldWebSources


class WorldWebBackground:
    def __init__(self,runtime,selector,source,store,*,sleep=time.sleep):
        need(isinstance(runtime,IOSGraphicsRuntime) and isinstance(source,WorldWebSources) and isinstance(store,PrivateFeatureState) and callable(sleep))
        self.runtime,self.selector,self.source,self.store,self.sleep=runtime,selector,source,store,sleep
        self.binding,self.run,self.lock=source.binding,source.run,source.lock;self.previous=store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):return dict(iosWorldWebBackgroundVersion=1,binding=self.binding,runId=self.run,payload=pack([state]))
    def decode(self,value):
        with self.source.validation_round():return self._decode(value)

    def _decode(self,value):
        exact(value,{'iosWorldWebBackgroundVersion','binding','runId','payload'});rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'call','phase','before','background','after'})
        call=arguments('feature.world-web.act',state['call']);need(call['runId']==self.run and call['verb']=='background-resume'
            and state['phase'] in ('background-issued','background-observed','foreground-issued','observed'))
        self.source.frame(state['before'])
        if state['background'] is not None:IOSGraphicsBackground.status_packet(state['background'],self.binding);need(not state['background']['foreground'])
        if state['after'] is not None:self.completed(state['before'],state['after'])
        need(state['phase']=='background-issued' or state['background'] is not None);need(state['phase']!='observed' or state['after'] is not None)
        return deepcopy(state)
    def save(self):
        check();self.lock.assert_held();need(same(self.store.read(),self.previous));value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);check()
    def status(self):
        check();value=IOSGraphicsRuntime._graphics_lifecycle_status(self.runtime,self.selector,self.binding)
        IOSGraphicsBackground.status_packet(value,self.binding);check();return deepcopy(value)
    def completed(self,before,after):
        with self.source.validation_round():return self._completed(before,after)

    def _completed(self,before,after):
        first,last=self.source.frame(before),self.source.frame(after);a,b=first['clockJoin']['nativeAfter'],last['clockJoin']['nativeBefore']
        from ios.adapters.graphics_history import follow_native
        follow_native(a,b);need(b['lifecycle']['backgrounds']>=a['lifecycle']['backgrounds']+1
            and b['lifecycle']['activations']>=a['lifecycle']['activations']+1 and b['lifecycle']['launches']==a['lifecycle']['launches'])
        old=first['originals']['document'];new=last['originals']['document'];need(old is not None and new is not None)
        left,right=old['source']['nativeView'],new['source']['nativeView'];need((left['handle'],left['creation'])!=(right['handle'],right['creation'])
            and left['nonce']!=right['nonce'] and new['source']['dom']['editor']==dict(text='',focused=False)
            and right['url']==right['sourceUrl']==left['sourceUrl'])
    def send(self,operation):
        check();base=self.runtime.adapter;outer=base._operation
        need(outer in (None,'feature.world-web.act','feature.world-web.cleanup') and operation in ('lifecycle.background','app.launch')
            and self.state['phase']==('background-issued' if operation=='lifecycle.background' else 'foreground-issued'))
        base._operation=None
        try:return base.invoke(self.selector,operation,{})
        finally:base._operation=outer
    def act(self,call):
        call=deepcopy(arguments('feature.world-web.act',call));need(call['runId']==self.run and call['verb']=='background-resume')
        if self.state is None:
            need(self.status()['foreground']);before=self.source.capture('before-background')
            self.state=dict(call=call,phase='background-issued',before=before,background=None,after=None);self.save();self.send('lifecycle.background')
        else:need(same(self.state['call'],call))
        if self.state['phase']=='background-issued':
            for attempt in range(51):
                value=self.status()
                if not value['foreground']:break
                need(attempt<50);self.sleep(.1)
            self.state.update(phase='background-observed',background=value);self.save()
        if self.state['phase']=='background-observed':
            need(not self.status()['foreground']);self.state['phase']='foreground-issued';self.save();self.send('app.launch')
        need(self.state['phase'] in ('foreground-issued','observed') and self.status()['foreground'])
        after=self.source.capture('after-background');self.completed(self.state['before'],after)
        self.state.update(phase='observed',after=after);self.save();return {'performed':True}
