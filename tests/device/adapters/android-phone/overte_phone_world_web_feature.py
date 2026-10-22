"""Public v17 Phone world-browser operations and independently sampled actor.

All product facts come from original sources. Fixture activations authorize
inputs only; an ACK never supplies text, document counts, HTTP status or pixels.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import base64
import hashlib
import io
import math
import os
from pathlib import Path
import stat
import time
import uuid
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.native_phone_web_runtime import released
from adapters.feature_fixture_access import AdapterFixtureClient
from feature_journeys.contract import arguments,result,identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending,PhaseRetired
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.witness import projection
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_world_web_source import continuity,fixture,validate as validate_source
from overte_phone_world_web_measurements import browser_status,measurement

VERSION=1


class PhoneWorldWebFeature:
    def __init__(self,adapter,selector,source,artifact_root,foreign_fixture_url,*,role='primary',monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,PhaseFixtureReader) and source.area=='world-web' and role in ('primary','actor')
            and callable(monotonic) and callable(sleep))
        self.adapter,self.selector,self.source,self.role=adapter,selector,source,role
        self.run,self.fixture_url=source.run,source.fixture_url
        self.artifact_root=Path(artifact_root);PrivateFeatureState(self.artifact_root/'world-web-boundary.json')._parent()
        fixture(self.run,self.fixture_url)
        foreign=foreign_fixture_url.rstrip('/')+'/runs/'+self.run+'/'
        fixture(self.run,foreign);a,b=urlsplit(self.fixture_url),urlsplit(foreign)
        need((a.scheme,a.netloc)!=(b.scheme,b.netloc));self.foreign_url=foreign
        if role=='actor':need(not isinstance(source.client,AdapterFixtureClient))
        self.monotonic,self.sleep=monotonic,sleep
        path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('phone-world-web-feature.json'))
        self.role_store=PrivateFeatureState(path.with_name('phone-world-web-'+role+'.json'))
        self.retirement_store=PrivateFeatureState(path.with_name('phone-world-web-retirement.json'))
        self.lock=PhoneScriptSourceLock(path.with_name('phone-script-sources.lock'))
        self.originals={}
        self.completed_store=PrivateFeatureState(self.artifact_root/('world-web-'+self.run+'-retirement.json'))

    @contextmanager
    def serialized(self):
        pending=None
        with self.lock.held():
            try:yield
            except PhasePending as error:pending=error
        if pending is not None:raise pending

    def read(self,store,kind):
        value=store.read();self.originals[store.path]=deepcopy(value)
        if value is None:return None
        exact(value,{'worldWebFeatureVersion','kind','runId','fixtureUrl','artifactRoot','foreignFixtureUrl','payload'})
        need(type(value['worldWebFeatureVersion']) is int and value['worldWebFeatureVersion']==VERSION and value['kind']==kind
            and value['runId']==self.run and value['fixtureUrl']==self.fixture_url and value['artifactRoot']==str(self.artifact_root)
            and value['foreignFixtureUrl']==self.foreign_url.rsplit('/runs/',1)[0])
        rows=unpack(value['payload']);need(len(rows)==1);return rows[0]

    def write(self,store,kind,value):
        self.lock.assert_held();need(store.path in self.originals and same(store.read(),self.originals[store.path]))
        record=dict(worldWebFeatureVersion=VERSION,kind=kind,runId=self.run,fixtureUrl=self.fixture_url,
            artifactRoot=str(self.artifact_root),foreignFixtureUrl=self.foreign_url.rsplit('/runs/',1)[0],payload=pack([value]))
        store.write(record,self.originals[store.path]);need(same(store.read(),record));self.originals[store.path]=deepcopy(record)

    def owner(self):
        value=self.read(self.store,'owner')
        if value is None:return None
        exact(value,{'binding','ownerToken','phase','reserved','scriptUrl','call','tickets','phaseSource','cleanupProof','lifecycle'})
        context(value['binding']);identifier(value['ownerToken'])
        need(value['phase'] in ('preparing','baseline','acting','active','cleaning','cleaned') and type(value['reserved']) is bool
            and type(value['tickets']) is list and len(value['tickets'])<=256 and len(set(value['tickets']))==len(value['tickets'])
            and type(value['cleanupProof']) is list and len(value['cleanupProof'])<=64)
        for ticket in value['tickets']:identifier(ticket)
        if value['scriptUrl'] is not None:
            need(value['scriptUrl'].startswith(self.fixture_url+'tickets/') and re_script(value['scriptUrl'][len(self.fixture_url+'tickets/'):]))
        if value['call'] is not None:
            arguments('feature.world-web.act',value['call']);need(value['call']['runId']==self.run and value['call']['fixtureUrl']==self.fixture_url
                and value['call']['ticket']==value['tickets'][-1])
        return value

    def save(self,value):self.write(self.store,'owner',value)

    def runtime(self,owner):
        _ui,_observe,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(context(binding),owner['binding']) and guard() is not False)
        return binding,guard

    def io(self,owner,*,read_only=True):
        self.runtime(owner);return self.adapter._world_web_io(self.selector,read_only=read_only)

    def phase(self,owner):
        active=self.source.read(owner['phaseSource'])
        if owner['phase'] in ('acting','cleaning'):raise PhasePending('Owned World Web input or retirement is in progress')
        return active

    def prepare(self):
        need(self.role=='primary')
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            owner=self.owner()
            if owner is None:
                need(self.retirement_store.read() is None and self.role_store.read() is None and self.completed_store.read() is None
                    and self.adapter.world_web_manager_store(self.selector).read() is None)
                phase=self.source.read();need(phase['verb']=='baseline')
                _ui,_observe,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
                guard();owner=dict(binding=deepcopy(binding),ownerToken=uuid.uuid4().hex,phase='preparing',reserved=False,scriptUrl=None,
                    call=None,tickets=[],phaseSource=phase['status'],cleanupProof=[],lifecycle=None);self.save(owner)
            self.runtime(owner)
            if owner['phase']=='preparing':
                packet=self.io(owner,read_only=False).request(self.run,self.fixture_url,owner['ownerToken'],'reserve')
                need(packet['source']=={'reserved':True})
                owner.update(reserved=True,phase='baseline');self.save(owner)
            return deepcopy(owner)

    def sample_native(self,owner,previous=None):
        io=self.io(owner);io.last=deepcopy(previous)
        return io.request(self.run,self.fixture_url,owner['ownerToken'],'observe')

    def input(self,owner,control,text=''):
        before=self.sample_native(owner);current=before['source']['current'];need(bool(current))
        view=current['source']['nativeView'];fields={k:view[k] for k in ('handle','creation','grant','page')}
        receipt=self.io(owner,read_only=False).request(self.run,self.fixture_url,owner['ownerToken'],'input',control=control,text=text,**fields)
        need(receipt['source']=={'delivered':True})
        return receipt # Never a browser-effect observation.

    def deliver(self,owner,call):
        verb=call['verb']
        if verb=='open':
            need(owner['scriptUrl'] is None)
            owner['scriptUrl']=self.fixture_url+'tickets/'+call['ticket']+'/client.js';self.save(owner)
            manager=self.adapter._world_web_manager(self.selector)
            manager.open();manager.load_source(owner['scriptUrl'])
            manager.wait_rows(lambda rows:any(row['url']==owner['scriptUrl'] for row in rows));manager.close_tablet()
        elif verb=='close':self.close_source(owner)
        elif verb in ('focus-type','clear-text'):self.input(owner,'text',call['inputs'].get('text',''))
        elif verb in ('submit','foreign-origin-message'):self.input(owner,'bridge')
        elif verb=='navigate':self.input(owner,{'reference.html':'reference','page-b.html':'second','recovery.html':'recovery'}[call['inputs']['resource']])
        elif verb=='navigate-foreign':
            native=self.sample_native(owner);url=native['source']['current']['source']['nativeView']['sourceUrl']
            path=urlsplit(url).path;foreign=urlsplit(self.foreign_url)
            target=foreign.scheme+'://'+foreign.netloc+path
            self.input(owner,'foreign',target);self.input(owner,'navigate')
        elif verb in ('back','reload'):self.input(owner,verb)
        elif verb=='restore-resource':
            # The reader-owned phase activation already changed the server.
            # This adapter may only inspect that original control state.
            status=browser_status(self.source.client.request('/runs/'+self.run+'/browser'));need(status['ready'] is True)
        elif verb=='background-resume':
            before=self.adapter._native_feature_observer(self.selector,read_only=True).read(0)
            self.adapter.invoke(self.selector,'lifecycle.background',{})
            for attempt in range(41):
                observed=self.adapter._graphics_lifecycle_status(self.selector,owner['binding'])
                if observed['foreground'] is False:break
                need(attempt<40);self.sleep(.1)
            self.adapter.invoke(self.selector,'app.launch',{})
            after=self.adapter._native_feature_observer(self.selector,read_only=True).read(0)
            need(after['lifecycle']['launches']==before['lifecycle']['launches']
                and after['lifecycle']['backgrounds']>before['lifecycle']['backgrounds']
                and after['lifecycle']['activations']>before['lifecycle']['activations'])
        else:need(False)

    def act(self,value):
        need(self.role=='primary');call=deepcopy(arguments('feature.world-web.act',value))
        need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        self.prepare()
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            owner=self.owner();need(owner['phase'] in ('baseline','acting','active'))
            active=self.source.read(owner['phaseSource']);need(active['ticket']==call['ticket'] and active['verb']==call['verb'] and same(active['inputs'],call['inputs']))
            if call['ticket'] in owner['tickets']:
                need(same(owner['call'],call) and owner['phase']=='active');return {'performed':True}
            need(owner['phase'] in ('baseline','active') and len(owner['tickets'])<256)
            owner.update(phase='acting',call=call,phaseSource=active['status']);owner['tickets'].append(call['ticket']);self.save(owner)
            # One durable intent precedes any ordinary product input. A lost
            # response stays issued; another act cannot repeat it.
            self.runtime(owner);self.deliver(owner,call);self.runtime(owner)
            owner.update(phase='active');self.save(owner)
            return {'performed':True}

    def role_state(self):
        value=self.read(self.role_store,self.role)
        if value is None:return dict(sequence=0,native=None,browser=None,lifecycle=None,last=None,quiet=None,retired=None,images=[])
        exact(value,{'sequence','native','browser','lifecycle','last','quiet','retired','images'})
        need(integer(value['sequence'],0,1000000000) and type(value['images']) is list and len(value['images'])<=256)
        if value['native'] is not None:
            owner=self.owner();need(owner is not None)
            packet=value['native'];request=dict(schemaVersion=1,commandId=packet['commandId'],action='phone-world-web',runId=self.run,
                fixtureUrl=self.fixture_url,ownerToken=owner['ownerToken'],operation='observe')
            validate_source(packet,request,int(owner['binding']['processIdentity'].split(':')[0]),packet['capturedEpochMs'])
        if value['browser'] is not None:browser_status(value['browser'])
        for image in value['images']:
            exact(image,{'name','phase','device','inode','sha256','bytes'})
            name=image['name'];need(type(name) is str and name.startswith('world-web-'+self.run+'-'+self.role+'-')
                and name.endswith('.png') and len(name)==len('world-web-'+self.run+'-'+self.role+'-')+36
                and '/' not in name and '\\' not in name and image['phase'] in ('planned','opened','saved'))
            identifier(name[-36:-4])
            if image['phase']=='planned':need(all(image[key] is None for key in ('device','inode','sha256','bytes')))
            else:
                need(integer(image['device'],0,2**64-1) and integer(image['inode'],1,2**64-1))
                if image['phase']=='saved':need(type(image['sha256']) is str and len(image['sha256'])==64 and integer(image['bytes'],1,32*1024*1024))
        if value['last'] is not None:result('feature.world-web.observe',value['last'])
        return value

    def screenshot(self,owner,ticket,sequence,role,state):
        binding,guard=self.runtime(owner)
        client,session,_state=self.adapter.existing_session(self.selector)
        from urllib.parse import quote
        name='world-web-'+self.run+'-'+role+'-'+uuid.uuid4().hex+'.png';path=self.artifact_root/name
        image=dict(name=name,phase='planned',device=None,inode=None,sha256=None,bytes=None)
        state['images'].append(image);self.write(self.role_store,self.role,state)
        capture_start=self.adapter._world_web_clock(self.selector)
        encoded=client.call('GET','/session/'+quote(session,safe='')+'/screenshot')
        captured=self.adapter._world_web_clock(self.selector);need(integer(captured,capture_start) and captured-capture_start<=1500)
        need(type(encoded) is str and len(encoded)<=44*1024*1024);raw=base64.b64decode(encoded,validate=True)
        need(0<len(raw)<=32*1024*1024)
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as picture:
            need(picture.format=='PNG' and picture.width*picture.height<=8388608);picture.load()
        guard()
        # The caller records intent before native acquisition; an interrupted
        # file write is retained by that exact role, never adopted by a retry.
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(descriptor,'wb') as output:
            opened=os.fstat(output.fileno());image.update(phase='opened',device=opened.st_dev,inode=opened.st_ino)
            self.write(self.role_store,self.role,state)
            output.write(raw);output.flush();os.fsync(output.fileno())
        info=path.lstat();need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_mode&0o777==0o600)
        need((info.st_dev,info.st_ino)==(image['device'],image['inode']))
        image.update(phase='saved',sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw));self.write(self.role_store,self.role,state)
        return dict(kind='image',name=name,sequence=sequence,capturedEpochMs=captured,ticket=ticket,source='native-screen')

    def acquire(self,owner,phase,state,*,after_sequence=0):
        start=self.monotonic();need(number(start,0,1e15) and integer(after_sequence) and after_sequence<=state['sequence'])
        self.runtime(owner)
        native=self.sample_native(owner,state['native'])
        if native['source']['retired']:need(owner['phase']=='cleaned')
        before=self.adapter._native_feature_observer(self.selector,read_only=True).read(0)
        runtime=self.adapter._web_runtime_observer(self.selector,read_only=True).read(self.run,self.fixture_url)
        status=browser_status(self.source.client.request('/runs/'+self.run+'/browser'),state['browser'])
        _ui,observe,_binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        diagnostic,_diagnostic_epoch=observe(0);rows=diagnostic['scripts']
        measured,resources=measurement(self.run,self.fixture_url,self.foreign_url,native,status,runtime,rows,owner['scriptUrl'])
        artifacts=[];sequence=state['sequence']+1
        if measured['open'] and self.role=='primary':
            need(len(state['images'])<256)
            artifact=self.screenshot(owner,phase['ticket'],sequence,self.role,state);artifacts.append(artifact)
        after=self.adapter._native_feature_observer(self.selector,read_only=True).read(0)
        epoch=self.adapter._world_web_clock(self.selector)
        need(after['instance']==before['instance'] and after['lifecycle']==before['lifecycle']
            and min(before['capturedEpochMs'],native['capturedEpochMs'],runtime['source']['nativeBefore']['capturedEpochMs'])>=phase['afterEpochMs'])
        for captured in (native['capturedEpochMs'],runtime['source']['nativeBefore']['capturedEpochMs'],before['capturedEpochMs'],diagnostic['sampleEpochMs']):fresh(captured,epoch)
        need(self.monotonic()-start<10 and self.source.epoch_ms()-phase['afterEpochMs']>=0)
        if state['lifecycle'] is not None:need(all(after['lifecycle'][k]>=v for k,v in state['lifecycle'].items()))
        captured=after['capturedEpochMs']
        value=result('feature.world-web.observe',dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.run,sequence=sequence,
            capturedEpochMs=captured,state=measured,artifacts=artifacts,resources=resources,lifecycle=after['lifecycle']))
        end=self.source.read();need(end['ticket']==phase['ticket'] and end['verb']==phase['verb'] and same(end['inputs'],phase['inputs']))
        state.update(sequence=sequence,native=native,browser=status,lifecycle=after['lifecycle'],last=value)
        if measured==dict(surface='world',text='',page='none',bridgeMessages=0,bridgeEchoes=0,attemptedMessages=0,documentLoads=0,
                httpStatus=0,origin='none',documentKind='none',inlineLeases=0,deferredMessages=0,error='none',focused=False,open=False) and not resources and native['source']['retired']:
            quiet=state['quiet'];now=self.monotonic()
            if quiet is None:quiet=dict(start=now,latest=now,count=0,complete=False)
            need(number(now,quiet['latest'],1e15));quiet.update(latest=now,count=quiet['count']+1,complete=now-quiet['start']>=3 and quiet['count']>=3)
            state['quiet']=quiet
        else:state['quiet']=None
        guard();self.write(self.role_store,self.role,state)
        return value

    def observe(self,value):
        call=arguments('feature.world-web.observe',value);need(self.role=='primary' and call['runId']==self.run)
        self.prepare()
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            owner=self.owner();phase=self.phase(owner);state=self.role_state()
            return self.acquire(owner,phase,state,after_sequence=call['afterSequence'])

    def publish(self):
        need(self.role=='actor')
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            owner=self.owner();need(owner is not None);state=self.role_state()
            try:phase=self.phase(owner)
            except PhaseRetired as retired:
                need(owner['phase']=='cleaned' and state['quiet'] is not None and state['quiet']['complete'] and state['native']['source']['retired'])
                native=self.sample_native(owner,state['native']);need(native['source']['retired'])
                state.update(native=native,retired=retired.status);self.write(self.role_store,self.role,state);raise
            value=self.acquire(owner,phase,state)
            self.source.client.request('/runs/'+self.run+'/samples',dict(ticket=phase['ticket'],actor='owned-observer',actorSequence=value['sequence'],
                capturedEpochMs=value['capturedEpochMs'],facts=projection('world-web',value['state'])))
            return value

    def close_source(self,owner):
        if self.adapter.world_web_manager_store(self.selector).read() is None:return
        manager=self.adapter._world_web_manager(self.selector)
        if manager.state['loadAttempted']:
            manager.open();manager.stop_source(owner['scriptUrl'])
        manager.close()

    def cleanup(self,value):
        call=arguments('feature.world-web.cleanup',value);need(self.role=='primary' and call['runId']==self.run)
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            owner=self.owner()
            if owner is None:return {'performed':True} # No reserved scope or product input was ever issued.
            if owner['phase']=='cleaned':return {'performed':True}
            phase=self.source.read(owner['phaseSource']);need(phase['verb']=='cleanup')
            owner.update(phase='cleaning',phaseSource=phase['status']);self.save(owner);self.close_source(owner)
            start=previous=self.monotonic();stable=None
            for attempt in range(81):
                self.runtime(owner)
                native=self.sample_native(owner)
                runtime=self.adapter._web_runtime_observer(self.selector,read_only=True).read(self.run,self.fixture_url)
                need(not native['source']['current'])
                if runtime['source']['nativeAfter']['knownHandles']:released(runtime)
                else:need(not runtime['source']['nativeAfter']['views'] and not runtime['source']['java']['views'] and not runtime['source']['java']['creations'])
                now=self.monotonic();need(number(now,previous,start+20));previous=now
                if stable is None:stable=now
                owner['cleanupProof'].append(dict(native=native,runtime=runtime));self.save(owner)
                if now-stable>=3 and len(owner['cleanupProof'])>=3:break
                need(attempt<80 and len(owner['cleanupProof'])<64);self.sleep(.1)
            receipt=self.io(owner,read_only=False).request(self.run,self.fixture_url,owner['ownerToken'],'retire');need(receipt['source']=={'retired':True})
            owner.update(phase='cleaned');self.save(owner)
            return {'performed':True}

    def finalize(self):
        need(self.role=='primary');started=previous=self.monotonic()
        for attempt in range(81):
            with self.serialized(),self.adapter.existing_input_session(self.selector):
                plan=self.read(self.retirement_store,'retirement')
                completed=self.read(self.completed_store,'completed')
                if plan is None and self.store.read() is None:
                    need(completed is not None and all(PrivateFeatureState(self.store.path.with_name('phone-world-web-'+role+'.json')).read() is None
                        for role in ('primary','actor')) and self.adapter.world_web_manager_store(self.selector).read() is None)
                    original=unpack(completed['owner']['payload'])[0];native=self.sample_native(original)
                    need(native['source']['retired']);return {'performed':True}
                if plan is None:
                    owner=self.owner();need(owner is not None and owner['phase']=='cleaned' and self.adapter.world_web_manager_store(self.selector).read() is None)
                    status=self.source.status();need(status['active'] is False)
                    actor_store=PrivateFeatureState(self.store.path.with_name('phone-world-web-actor.json'))
                    actor=self.read(actor_store,'actor')
                    if actor is not None and actor['retired'] is not None:
                        need(actor['quiet'] is not None and actor['quiet']['complete'])
                        primary=self.role_state()
                        plan=dict(owner=deepcopy(self.originals[self.store.path]),actor=deepcopy(self.originals[actor_store.path]),
                            primary=deepcopy(self.originals[self.role_store.path]),status=status,binding=owner['binding'])
                        self.write(self.retirement_store,'retirement',plan)
                if plan is not None:
                    if completed is None:self.write(self.completed_store,'completed',plan)
                    else:need(same(completed,plan))
                    self.runtime(dict(binding=plan['binding']))
                    for name,key in (('phone-world-web-actor.json','actor'),('phone-world-web-primary.json','primary'),('phone-world-web-feature.json','owner')):
                        store=PrivateFeatureState(self.store.path.with_name(name));current=store.read();need(current is None or same(current,plan[key]))
                        if current is not None:store.discard(current)
                        need(store.read() is None)
                    current=self.retirement_store.read();need(same(current,self.originals[self.retirement_store.path]));self.retirement_store.discard(current)
                    return {'performed':True}
            now=self.monotonic();need(number(now,previous,started+20));previous=now;need(attempt<80);self.sleep(.25)
        raise NativeUIError('Independent World Web actor retirement did not finish')


def re_script(value):
    import re
    return re.fullmatch('[0-9a-f]{32}/client\\.js',value) is not None
