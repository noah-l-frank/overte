"""Owned app files and ordinary Running Scripts setup on the existing SDK.

Each actual mutation is preceded by durable responsibility. Unknown delivery
is never replayed. App code, VM assignment, controls and native absence remain
independently observed; ordinary input ACKs do not supply those facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_script_manager import NormalScriptManager
from adapters.normal_ui import NativeUI,Locator
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import same,pack,unpack
from adapters.token_script_ui import TokenScriptUI
from adapters.token_script_file_ui import TokenScriptFilePicker
from feature_journeys.contract import identifier
from ios.adapters.normal_input import NativeInput
from ios.adapters.normal_scripts import IOSScriptIO
from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles
from ios.adapters.tablet_web_app_origin import Frozen

VERSION=1


class TabletWebAppOwner:
    def __init__(self,runtime):
        self.runtime=runtime;source=runtime.observer.source
        self.root,self.binding,self.run,self.lock=source.root,source.binding,source.run,source.lock
        need(source.role=='primary');source.bound()
        self.store=PrivateFeatureState(self.root/('tabletweb-app-owner-'+self.run+'.json'))
        self.saved=self.store.read()
        if self.saved is None:self.state=dict(generations=[],operations=[],pending=None);self.save()
        else:
            exact(self.saved,{'tabletWebAppOwnerVersion','binding','runId','payload'})
            need(type(self.saved['tabletWebAppOwnerVersion']) is int and self.saved['tabletWebAppOwnerVersion']==VERSION
                and same(self.saved['binding'],self.binding) and self.saved['runId']==self.run)
            rows=unpack(self.saved['payload']);need(len(rows)==1);self.state=rows[0]
        self.decode()
    def bound(self):self.runtime.check();self.lock.assert_held();need(same(self.store.read(),self.saved))
    def save(self):
        self.bound();self.decode();value=dict(tabletWebAppOwnerVersion=VERSION,binding=self.binding,runId=self.run,payload=pack([self.state]))
        self.store.write(value,self.saved);self.saved=deepcopy(value)
    def stamp(self):
        source=self.runtime.observer.source;value=dict(epochMs=source.epoch_ms(),monotonic=source.monotonic())
        need(integer(value['epochMs'],1) and number(value['monotonic'],0,1e15));return value
    def ownership(self,generation):
        identifier(generation['ticket']);value=generation['ownership']
        owned=OwnedTabletWebAppFiles(None,Frozen(value),self.binding).owned()
        need(owned['featureRun']==self.run and owned['ticket']==generation['ticket'] and owned['fixtureUrl']==self.runtime.observer.source.fixture)
        current=PrivateFeatureState(self.root/generation['ownerFile']).read()
        if current is not None:need(same(current,owned))
        else:
            # A missing host intent is legal only after the exact token's
            # independently returned NativeFiles absence, never release ACK.
            from ios.adapters.tablet_web_native_reads import TabletNativeReads
            history=TabletNativeReads(self.root,self.binding,self.run,'primary','files',self.lock,lambda:need(False),
                epoch_ms=lambda:need(False),monotonic=self.runtime.observer.source.monotonic,historical=True)
            history.history();matching=[]
            for reference in history.state['records']:
                row=history.frames.read(history.frames.expand(reference))
                if row['query']['runId']==owned['runId']:
                    need(row['query']['ownerToken']==owned['ownerToken']);matching.append(history.at(reference))
            need(matching and matching[-1]['operation']=='observe' and matching[-1]['source']==dict(exists=False,files=[]))
        return owned
    def decode(self):
        exact(self.state,{'generations','operations','pending'});need(type(self.state['generations']) is list and len(self.state['generations'])<=16
            and type(self.state['operations']) is list and len(self.state['operations'])<=128)
        tickets=set();labels=set()
        for index,generation in enumerate(self.state['generations'],1):
            exact(generation,{'index','ticket','ownerFile','reserved','ownership','directory','admission','dialogBefore'})
            need(type(generation['index']) is int and generation['index']==index and generation['ticket'] not in tickets
                and generation['ownerFile']=='tabletweb-app-files-'+self.run+'-'+str(index)+'.json')
            tickets.add(generation['ticket']);need(type(generation['reserved']) is bool)
            owned=self.ownership(generation) if generation['reserved'] else None
            if not generation['reserved']:
                need(generation['directory'] is generation['admission'] is generation['dialogBefore'] is None)
                if generation['ownership'] is not None:
                    planned=OwnedTabletWebAppFiles(None,Frozen(generation['ownership']),self.binding).owned()
                    need(planned['featureRun']==self.run and planned['ticket']==generation['ticket'] and planned['fixtureUrl']==self.runtime.observer.source.fixture)
            if generation['directory'] is not None:
                from adapters.token_script_file_ui import file_url
                need(file_url(generation['directory']).endswith('/feature-script-'+owned['runId']))
            if generation['admission'] is not None:
                source=self.runtime.observer.source;need(generation['admission'] in source.state['apps'])
                app=source.app_originals.read(source.app_originals.expand(generation['admission']));need(same(app['owner'],owned))
            if generation['dialogBefore'] is not None:
                from ios.adapters.tablet_web_native_reads import TabletNativeReads
                history=TabletNativeReads(self.root,self.binding,self.run,'primary','dialogs',self.lock,lambda:need(False),
                    monotonic=self.runtime.observer.source.monotonic,historical=True)
                history.at(generation['dialogBefore'])
        for row in self.state['operations']+([self.state['pending']] if self.state['pending'] else []):
            exact(row,{'label','generation','status','before','after','requests'})
            need(type(row['label']) is str and re.fullmatch('[a-z][a-z0-9-]{0,79}',row['label']) and row['label'] not in labels
                and integer(row['generation'],1,len(self.state['generations'])) and row['status'] in ('issued','returned','failed')
                and type(row['requests']) is list and len(row['requests'])<=128);labels.add(row['label'])
            for request in row['requests']:
                exact(request,{'kind','request','nativeRef','returned'});need(request['kind'] in ('sdk','qt'))
                need(type(request['request']) is dict and (request['returned'] is None or type(request['returned']) is dict))
                if request['nativeRef'] is not None:
                    from ios.adapters.tablet_web_native_reads import TabletNativeReads
                    history=TabletNativeReads(self.root,self.binding,self.run,'primary','widgets',self.lock,lambda:need(False),
                        epoch_ms=lambda:need(False),monotonic=self.runtime.observer.source.monotonic,historical=True)
                    native=history.at(request['nativeRef'])['observation']
                    if request['kind']=='qt':
                        command=request['request'];need(command['instance']==native['instance'] and command['sequence']==native['lastSequence']+1
                            and command['observedElapsedMs']==native['elapsedMs'])
                        fields=[field for field in native['controls'] if field['token']==command['fieldToken'] and field['focused'] and field['enabled']]
                        need(len(fields)==1 and fields[0]['id'] in ('script-file.folder','script-file.primary'))
                else:need(request['kind']!='qt')
            if row['status']=='returned':need(row['after'] is not None and all(request['returned'] is not None for request in row['requests']))
        need(all(row['status']=='returned' for row in self.state['operations']))
        return deepcopy(self.state)
    def once(self,generation,label,function):
        self.bound();self.decode();need(self.state['pending'] is None and callable(function))
        found=[row for row in self.state['operations'] if row['label']==label]
        if found:need(found[0]['generation']==generation['index']);return
        row=dict(label=label,generation=generation['index'],status='issued',before=self.stamp(),after=None,requests=[])
        self.state['pending']=row;self.save();started=row['before']['monotonic'];last=[started]
        def deadline():
            now=self.runtime.observer.source.monotonic();need(number(now,last[0],started+60) and now-started<60);last[0]=now
        try:
            with transport_scope(deadline):function()
            deadline();row.update(status='returned',after=self.stamp());self.state['operations'].append(deepcopy(row));self.state['pending']=None;self.save()
        except Exception:row.update(status='failed',after=self.stamp());self.save();raise
    def intent(self,kind,request):
        self.bound();row=self.state['pending'];need(row is not None and row['status']=='issued' and len(row['requests'])<128
            and all(item['returned'] is not None for item in row['requests']))
        widgets=self.runtime.auxiliary('widgets');widgets.history();need(not widgets.blocked)
        native=deepcopy(widgets.state['records'][-1]) if widgets.state['records'] else None
        need(kind!='qt' or native is not None)
        row['requests'].append(dict(kind=kind,request=deepcopy(request),nativeRef=native,returned=None));self.save()
    def returned(self,kind,request,result):
        self.bound();row=self.state['pending'];need(row is not None and row['requests']);current=row['requests'][-1]
        need(current['kind']==kind and current['returned'] is None and same(current['request'],request))
        # Status is only input ACK metadata; SDK response bodies can be large
        # and contain unrelated content. Exact original sources prove effects.
        current['returned']=self.stamp();self.save()
    def input_objects(self):
        outer=self;runtime=self.runtime;source=runtime.observer.source
        class UI(NativeUI):
            def _request(self,method,path,body=None):
                mutation=method=='DELETE' or method=='POST' and path!='/elements'
                request=dict(method=method,path=path,body=deepcopy(body))
                if mutation:outer.intent('sdk',request)
                result=super()._request(method,path,body)
                if mutation:outer.returned('sdk',request,result)
                return result
        class Qt(NativeInput):
            def capture(self,*,native_epoch_ms=None):
                self._check();packet=runtime.read_auxiliary('widgets');self.last_receipt=deepcopy(packet);value=packet['observation']
                need(self.instance in (None,value['instance']));self.instance=value['instance'];return value
            def deliver(self,command,*,before_send=None):
                outer.intent('qt',command)
                result=super().deliver(command,before_send=before_send)
                outer.returned('qt',command,result);return result
        ui=UI(runtime.client,self.binding['sessionId'],lambda:runtime.process() is not None,monotonic=source.monotonic,sleep=runtime.transport.sleep)
        qt=Qt(runtime.client,self.binding['sessionId'],runtime.target,runtime.process,monotonic=source.monotonic,sleep=runtime.transport.sleep,native_epoch_ms=runtime.native_clock)
        return ui,qt
    def files(self,generation):
        runtime=self.runtime;metadata=self.ownership(generation)
        class Native:
            def request(_self,operation,run,token,files=None):
                need(run==metadata['runId'] and token==metadata['ownerToken'])
                packet=runtime.read_auxiliary('files',ownership=metadata,operation=operation,files=files);return packet['source']
        store=PrivateFeatureState(self.root/generation['ownerFile'])
        return OwnedTabletWebAppFiles(Native(),store if store.read() is not None else Frozen(metadata),self.binding)
    def manager(self,generation):
        ui,qt=self.input_objects();runtime=self.runtime;source=runtime.observer.source
        io=IOSScriptIO(ui,qt);tokens=TokenScriptUI(io,monotonic=source.monotonic,sleep=runtime.transport.sleep)
        picker=TokenScriptFilePicker(io,generation['directory'],monotonic=source.monotonic,sleep=runtime.transport.sleep)
        def observe(after):
            value=runtime.read_auxiliary('diagnostic');need(value['sampleSequence']>after);return value,value['sampleEpochMs']
        return NormalScriptManager(tokens,observe,PrivateFeatureState(self.root/('tabletweb-app-manager-'+self.run+'-'+str(generation['index'])+'.json')),
            self.binding,source_kind='script-file-bundle',file_owner=self.files(generation),file_picker=picker,
            monotonic=source.monotonic,sleep=runtime.transport.sleep)
    def prepare(self,ticket):
        self.bound();self.decode();identifier(ticket);need(self.state['pending'] is None)
        found=[row for row in self.state['generations'] if row['ticket']==ticket]
        if found:
            generation=found[0]
            if generation['admission'] is not None:return deepcopy(generation['admission'])
        else:generation=None
        if generation is None:
            need(len(self.state['generations'])<16)
            # No product input precedes the actual complete weak-root inventory.
            widget=self.runtime.read_auxiliary('widgets')['observation'];inventory=widget['scriptInventory']
            need(inventory['inventoryVersion']==2 and inventory['complete'] and not widget['tabletShown']
                and not any(row['rootVisible'] or row['labelVisible'] for row in inventory['managers'])
                and not any(row['visible'] or row['closing'] or row['requestId'] for row in inventory['pickers']))
            index=len(self.state['generations'])+1;name='tabletweb-app-files-'+self.run+'-'+str(index)+'.json'
            generation=dict(index=index,ticket=ticket,ownerFile=name,reserved=False,ownership=None,directory=None,admission=None,dialogBefore=None)
            self.state['generations'].append(generation);self.save()  # Before host reservation/file creation.
        index=generation['index'];name=generation['ownerFile']
        if not generation['reserved']:
            outer=self;actual_store=PrivateFeatureState(self.root/name)
            class Reservation:
                def read(_self):return actual_store.read()
                def write(_self,value,previous):
                    need(previous is None)
                    if generation['ownership'] is None:
                        generation['ownership']=deepcopy(value);outer.save()  # Exact nonce/token/bytes BEFORE host file write.
                    need(same(generation['ownership'],value));actual_store.write(value,previous)
            files=OwnedTabletWebAppFiles(None,Reservation(),self.binding)
            current=actual_store.read()
            if generation['ownership'] is None:
                need(current is None);files.reserve_app(self.run,self.runtime.observer.source.fixture,ticket)
            elif current is None:actual_store.write(deepcopy(generation['ownership']),None)
            else:need(same(current,generation['ownership']))
            value=files.owned();need(same(value,generation['ownership']))
            generation['reserved']=True;self.save()
        self.once(generation,'stage-app-'+str(index),lambda:self.files(generation).stage_reserved())
        generation['directory']=self.files(generation).verify();self.save()
        manager=self.manager(generation)
        self.once(generation,'open-manager-'+str(index),manager.open)
        if generation['dialogBefore'] is None:
            self.runtime.read_auxiliary('dialogs');generation['dialogBefore']=deepcopy(self.runtime.auxiliary('dialogs').state['records'][-1]);self.save()
        self.once(generation,'open-picker-'+str(index),manager.file_picker_open)
        self.once(generation,'load-app-'+str(index),lambda:manager.file_picker_choose('script.js'))
        self.once(generation,'close-manager-'+str(index),manager.close_tablet)
        self.once(generation,'open-app-home-'+str(index),manager.ui.open_tablet)
        def home():
            snapshot=manager.ui.capture()
            if manager.ui.control(snapshot,'tablet.home') is not None:manager.ui.activate('tablet.home')
            else:
                actual=[row for row in snapshot['controls'] if 'tabletAppButton' in row and row['enabled']
                    and row['tabletAppButton']['featureRun']==self.run and row['tabletAppButton']['nonce']==self.ownership(generation)['nonce']]
                need(len(actual)==3)
        self.once(generation,'show-app-home-'+str(index),home)
        generation['admission']=self.runtime.remember_app(self.ownership(generation));self.save();return deepcopy(generation['admission'])


def input_scopes(root,binding,run,*,ready_only=False):
    """Read Primary input ownership only; never its observations or effects.

    This private manifest admits no VM, source, button, native existence or
    successful input. The independent Actor must acquire and qualify all of
    those originals itself before associating a page with these input bytes.
    """
    need(type(ready_only) is bool)
    store=PrivateFeatureState(root/('tabletweb-app-owner-'+run+'.json'));value=store.read()
    if value is None:return []
    exact(value,{'tabletWebAppOwnerVersion','binding','runId','payload'})
    need(type(value['tabletWebAppOwnerVersion']) is int and value['tabletWebAppOwnerVersion']==VERSION
        and same(value['binding'],binding) and value['runId']==run)
    payload=unpack(value['payload']);need(len(payload)==1);plan=payload[0]
    exact(plan,{'generations','operations','pending'});need(type(plan['generations']) is list and len(plan['generations'])<=16)
    result=[];tickets=set()
    for index,generation in enumerate(plan['generations'],1):
        exact(generation,{'index','ticket','ownerFile','reserved','ownership','directory','admission','dialogBefore'})
        identifier(generation['ticket']);need(generation['index']==index and type(generation['index']) is int
            and type(generation['reserved']) is bool and generation['ticket'] not in tickets
            and generation['ownerFile']=='tabletweb-app-files-'+run+'-'+str(index)+'.json');tickets.add(generation['ticket'])
        if not generation['reserved']:continue
        metadata=OwnedTabletWebAppFiles(None,Frozen(generation['ownership']),binding).owned()
        current=PrivateFeatureState(root/generation['ownerFile']).read()
        if current is not None:need(same(current,metadata))
        need(metadata['featureRun']==run and metadata['ticket']==generation['ticket'])
        # This is only a readiness cue for independent acquisition. Never use
        # the Primary admission bytes/profile as an Actor observation.
        if not ready_only or generation['admission'] is not None:result.append(metadata)
    return result
