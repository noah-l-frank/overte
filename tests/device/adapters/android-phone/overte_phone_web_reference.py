"""Normal world/tablet reference-video inputs; pixels are read by the common suite.

No media clock, desired frame, player state or pixel verdict enters this owner.
Its only outputs are input receipts and independently observed owned retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import uuid
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact,need,number
from adapters.native_phone_web_runtime import released,continuity as runtime_continuity
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from contracts import validate_operation_arguments
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock

OPERATIONS={'web.reference.'+kind for kind in ('open','close','play','pause','seek')}


class PhoneWebReference:
    def __init__(self,adapter,selector,*,monotonic=time.monotonic,sleep=time.sleep):
        need(callable(monotonic) and callable(sleep));self.adapter,self.selector=adapter,selector
        self.monotonic,self.sleep=monotonic,sleep;path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('phone-web-reference.json'))
        self.completed=PrivateFeatureState(path.with_name('phone-web-reference-retired.json'))
        self.lock=PhoneScriptSourceLock(path.with_name('phone-script-sources.lock'))
        self.previous=self.state=None

    def load(self):
        self.previous=self.store.read()
        if self.previous is None:self.state=None;return None
        exact(self.previous,{'phoneWebReferenceVersion','payload'})
        need(type(self.previous['phoneWebReferenceVersion']) is int and self.previous['phoneWebReferenceVersion']==1)
        rows=unpack(self.previous['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'binding','runId','root','scriptUrl','surface','ownerToken','phase','tabletOwned','call','native','runtime','proof'})
        context(state['binding']);validate_operation_arguments('web.reference.open',dict(surface=state['surface'],scriptUrl=state['scriptUrl']))
        from feature_journeys.contract import identifier
        identifier(state['runId']);identifier(state['ownerToken'])
        need(state['root']==state['scriptUrl'].removesuffix('client.js') and type(state['tabletOwned']) is bool
            and state['phase'] in ('reserved','load-issued','loaded','tablet-issued','active','issued','closing','retired')
            and type(state['proof']) is list and len(state['proof'])<=64)
        if state['call'] is not None:
            exact(state['call'],{'operation','arguments'});need(state['call']['operation'] in OPERATIONS)
            validate_operation_arguments(state['call']['operation'],state['call']['arguments'])
        self.state=deepcopy(state);return self.state

    def save(self):
        self.lock.assert_held();value=dict(phoneWebReferenceVersion=1,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def guard(self):
        _ui,_observe,binding,check,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(binding,self.state['binding']) and check() is not False)
        return check

    def source(self,operation,**fields):
        self.guard();reader=self.adapter._world_web_io(self.selector,read_only=operation=='observe')
        if self.state['native'] is not None:reader.last=deepcopy(self.state['native'])
        value=reader.request(self.state['runId'],self.state['root'],self.state['ownerToken'],operation,
            reference_surface=self.state['surface'],**fields)
        self.state['native']=deepcopy(value);self.save();return value

    def runtime(self,view=None):
        value=self.adapter._web_runtime_observer(self.selector,read_only=True).read(self.state['runId'],self.state['root'])
        if self.state['runtime'] is not None:
            runtime_continuity(self.state['runtime'],value,int(self.state['binding']['processIdentity'].split(':')[0]),self.state['root'])
        if view is not None:
            before=value['source']['nativeAfter'];java=value['source']['java']
            a=[row for row in before['views'] if row['handle']==view['handle']]
            b=[row for row in java['views'] if row['handle']==view['handle']]
            need(len(a)==len(b)==1 and any(row['handle']==view['handle'] for row in before['knownHandles']))
            a,b=a[0],b[0]
            need(a['surface']==self.state['surface'] and a['sourceOwned'] and a['documentOwned'] and a['created'] and a['sessionActive']
                and not a['pendingCreate'] and not a['suspended'] and not a['loading'] and b['sourceOwned'] and b['documentOwned']
                and b['active'] and b['ownerCurrent'] and b['foreground'] and not b['destroyed'] and not b['closing'] and not b['loading']
                and all(a[key]==b[key]==view[key] for key in ('handle','creation','grant','page')))
        self.state['runtime']=deepcopy(value);self.save();return value

    def current(self):
        value=self.source('observe');current=value['source']['current'];need(bool(current) and not value['source']['retired'])
        return current['nativeView']

    def open(self,arguments):
        self.load()
        if self.state is not None:
            need(self.state['scriptUrl']==arguments['scriptUrl'] and self.state['surface']==arguments['surface'])
            if self.state['phase']=='active':self.runtime(self.current());return {'performed':True}
            need(False) # An uncertain original load/tablet input is not replayable.
        _ui,_observe,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        completed=self.completed.read()
        if completed is not None:
            exact(completed,{'phoneWebReferenceVersion','payload'});old=unpack(completed['payload'])
            need(type(completed['phoneWebReferenceVersion']) is int and completed['phoneWebReferenceVersion']==1 and len(old)==1
                and old[0]['phase']=='retired' and same(context(old[0]['binding']),binding))
        need(self.adapter.web_reference_manager_store(self.selector).read() is None)
        self.state=dict(binding=deepcopy(binding),runId=uuid.uuid4().hex,root=arguments['scriptUrl'].removesuffix('client.js'),
            scriptUrl=arguments['scriptUrl'],surface=arguments['surface'],ownerToken=uuid.uuid4().hex,
            phase='reserved',tabletOwned=False,call=None,native=None,runtime=None,proof=[]);self.save()
        self.source('reserve');self.state['phase']='load-issued';self.save()
        manager=self.adapter._web_reference_manager(self.selector)
        manager.open();manager.load_source(self.state['scriptUrl'])
        manager.wait_rows(lambda rows:any(row['url']==self.state['scriptUrl'] for row in rows));manager.close_tablet()
        self.state['phase']='loaded';self.save()
        if self.state['surface']=='tablet':
            self.state.update(phase='tablet-issued',tabletOwned=True);self.save()
            self.adapter._web_reference_tablet(self.selector,'open')
        view=self.current();self.runtime(view);self.state['phase']='active';self.save();guard()
        return {'performed':True}

    def input(self,operation,arguments):
        self.load();need(self.state is not None and self.state['phase']=='active' and self.state['surface']==arguments['surface'])
        view=self.current();self.runtime(view);control={'web.reference.play':'play','web.reference.pause':'pause'}.get(operation)
        if operation=='web.reference.seek':control='seekStart' if arguments['seconds']==0 else 'seek'
        need(control is not None)
        self.state.update(phase='issued',call=dict(operation=operation,arguments=deepcopy(arguments)));self.save()
        self.source('input',control=control,text='',**{k:view[k] for k in ('handle','creation','grant','page')})
        self.state['phase']='active';self.save();return {'performed':True}

    def close(self,arguments=None):
        self.load()
        if self.state is None:
            need(self.adapter.web_reference_manager_store(self.selector).read() is None)
            completed=self.completed.read()
            if completed is None:return {'performed':True}
            exact(completed,{'phoneWebReferenceVersion','payload'});need(type(completed['phoneWebReferenceVersion']) is int and completed['phoneWebReferenceVersion']==1)
            rows=unpack(completed['payload']);need(len(rows)==1 and rows[0]['phase']=='retired')
            self.state=rows[0];context(self.state['binding'])
        if arguments is not None:need(self.state['surface']==arguments['surface'])
        self.guard()
        if self.state['phase']!='retired':
            self.state['phase']='closing';self.save()
            if self.state['tabletOwned']:
                self.adapter._web_reference_tablet(self.selector,'close');self.state['tabletOwned']=False;self.save()
            if self.adapter.web_reference_manager_store(self.selector).read() is not None:
                manager=self.adapter._web_reference_manager(self.selector)
                if manager.state['loadAttempted']:
                    manager.open();manager.stop_source(self.state['scriptUrl'])
                manager.close()
            self.empty_window()
            self.source('retire');self.state['phase']='retired';self.save()
        # A retained retirement plan must never hide a late original view/callback.
        self.empty_window();self.guard()
        old=self.completed.read();self.completed.write(dict(phoneWebReferenceVersion=1,payload=pack([self.state])),old)
        self.store.discard(self.previous);self.previous=self.state=None
        return {'performed':True}

    def empty_window(self):
        start=previous=self.monotonic();stable=None;count=0
        for attempt in range(81):
            self.guard();native=self.source('observe');need(not native['source']['current'])
            runtime=self.runtime()
            if runtime['source']['nativeAfter']['knownHandles']:released(runtime)
            else:need(not native['source']['documents'] and not runtime['source']['nativeAfter']['views'] and not runtime['source']['java']['views'] and not runtime['source']['java']['creations'])
            _ui,observe,_binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
            diagnostic,_epoch=observe(0);need(not any(row['url']==self.state['scriptUrl'] for row in diagnostic['scripts']))
            now=self.monotonic();need(number(now,previous,start+20));previous=now
            if stable is None:stable=now
            count+=1
            if count>=3 and now-stable>=3:
                self.state['proof'].append(dict(native=native,runtime=runtime,diagnostic=diagnostic));need(len(self.state['proof'])<=64)
                self.save();guard();return
            need(attempt<80);self.sleep(.1)
        raise NativeUIError('Original reference Web surface did not remain retired')

    def invoke(self,operation,arguments):
        need(operation in OPERATIONS);arguments=deepcopy(validate_operation_arguments(operation,arguments))
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            if operation=='web.reference.open':return self.open(arguments)
            if operation=='web.reference.close':return self.close(arguments)
            return self.input(operation,arguments)

    def cleanup(self):
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            result=self.close();completed=self.completed.read()
            if completed is not None:self.completed.discard(completed)
            need(self.store.read() is None and self.completed.read() is None);return result
