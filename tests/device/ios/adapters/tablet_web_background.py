"""Once-only ordinary Tablet background/resume with original OS/native reads.

A backgrounded client cannot run native/UI source admission. This independent
input owner retains its original intent and only permits the one not-yet-issued
normal activation. Unknown background/activation sends are never repeated.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from adapters.operation_transport_guard import scope as transport_scope
from feature_journeys.contract import arguments,identifier
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.graphics_lifecycle import IOSGraphicsBackground
from ios.adapters.graphics_history import follow_native
from ios.adapters.tablet_web_native_reads import TabletNativeReads

VERSION=1


class TabletWebBackground:
    def __init__(self,runtime,selector,run,binding,*,monotonic=time.monotonic,sleep=time.sleep):
        self.runtime,self.selector,self.run=runtime,selector,identifier(run)
        self.binding=deepcopy(context(binding));self.root=runtime.state_path(selector).parent
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.store=PrivateFeatureState(self.root/('tabletweb-background-'+run+'.json'))
        self.monotonic,self.sleep=monotonic,sleep;self.deadline=None;self.last=None;self.failed=False
        self.saved=self.store.read();self.state=None if self.saved is None else self.decode(self.saved)
    def envelope(self):return dict(tabletWebBackgroundVersion=VERSION,binding=self.binding,runId=self.run,payload=pack([self.state]))
    def original(self,reference):
        owner=TabletNativeReads(self.root,self.binding,self.run,'primary','native',self.lock,lambda:need(False),historical=True)
        return owner.at(reference)
    def decode(self,value):
        exact(value,{'tabletWebBackgroundVersion','binding','runId','payload'})
        need(type(value['tabletWebBackgroundVersion']) is int and value['tabletWebBackgroundVersion']==VERSION
            and same(value['binding'],self.binding) and value['runId']==self.run)
        rows=unpack(value['payload']);need(len(rows)==1);row=rows[0]
        exact(row,{'call','phase','before','background','after'})
        call=arguments('feature.tablet-web.act',row['call'])
        need(call['runId']==self.run and call['verb']=='background-resume'
            and row['phase'] in ('background-issued','background-observed','foreground-issued','observed'))
        before=self.original(row['before'])
        if row['background'] is not None:
            IOSGraphicsBackground.status_packet(row['background'],self.binding);need(not row['background']['foreground'])
        need(row['phase']=='background-issued' or row['background'] is not None)
        if row['after'] is not None:self.completed(before,self.original(row['after']))
        need(row['phase']!='observed' or row['after'] is not None)
        return deepcopy(row)
    def clock(self):
        now=self.monotonic()
        if self.failed or not number(now,0,1e15) or self.last is not None and now<self.last or self.deadline is not None and now>=self.deadline:
            self.failed=True;need(False)
        self.last=now;return True
    def bound(self):
        self.lock.assert_held();self.clock();need(same(self.store.read(),self.saved));self.clock();return True
    def save(self):
        self.bound();value=self.envelope();self.decode(value);self.store.write(value,self.saved);self.saved=deepcopy(value)
    def status(self):
        self.bound();value=IOSGraphicsRuntime._graphics_lifecycle_status(self.runtime,self.selector,self.binding)
        IOSGraphicsBackground.status_packet(value,self.binding);self.bound();return value
    @staticmethod
    def completed(before,after):
        follow_native(before,after);a,b=before['lifecycle'],after['lifecycle']
        need(b['backgrounds']>=a['backgrounds']+1 and b['activations']>=a['activations']+1
            and b['launches']==a['launches'] and before['graphics']==after['graphics'])
    def send(self,operation):
        self.bound();need(operation in ('lifecycle.background','app.launch')
            and self.state['phase']==('background-issued' if operation=='lifecycle.background' else 'foreground-issued'))
        base=self.runtime.adapter;outer=base._operation
        need(outer in (None,'feature.tablet-web.act','feature.tablet-web.cleanup') and (outer!='feature.tablet-web.cleanup' or operation=='app.launch'))
        base._operation=None
        try:
            with transport_scope(self.clock):return base.invoke(self.selector,operation,{})
        finally:base._operation=outer
    def start(self,observer,call):
        """Called under the actual existing observer's exact shared source lock."""
        self.lock=observer.observer.source.lock;self.bound();call=deepcopy(arguments('feature.tablet-web.act',call))
        need(call['runId']==self.run and call['verb']=='background-resume' and same(observer.observer.source.binding,self.binding))
        if self.state is None:
            need(self.status()['foreground']);observer.read_auxiliary('native')
            before=deepcopy(observer.auxiliary('native').state['records'][-1])
            self.state=dict(call=call,phase='background-issued',before=before,background=None,after=None);self.save()
            self.send('lifecycle.background')
        else:need(same(self.state['call'],call))
        self.resume()
    def resume(self):
        """No native source/query, session creation or repeated issued input."""
        self.bound();need(self.state is not None)
        if self.state['phase']=='background-issued':
            for attempt in range(51):
                status=self.status()
                if not status['foreground']:break
                need(attempt<50);self.sleep(.1)
            self.state.update(phase='background-observed',background=deepcopy(status));self.save()
        if self.state['phase']=='background-observed':
            need(not self.status()['foreground']);self.state['phase']='foreground-issued';self.save();self.send('app.launch')
        need(self.state['phase'] in ('foreground-issued','observed') and self.status()['foreground'])
    def finish(self,observer):
        self.lock=observer.observer.source.lock;self.bound();need(self.state is not None and self.state['phase'] in ('foreground-issued','observed'))
        need(self.status()['foreground']);observer.read_auxiliary('native');after=deepcopy(observer.auxiliary('native').state['records'][-1])
        self.completed(self.original(self.state['before']),self.original(after))
        if self.state['after'] is not None:follow_native(self.original(self.state['after']),self.original(after))
        self.state.update(phase='observed',after=after);self.save();return {'performed':True}
    def recover_foreground(self):
        """Before foreground-only admission, recover this exact owned intent."""
        need(self.state is not None);self.deadline=self.monotonic()+30
        with self.lock.held(),transport_scope(self.clock):self.resume()
