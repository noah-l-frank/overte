"""Normal World Web start/IME/Send on the unchanged v16 source phase chain.

This private prefix attaches existing input and original-source owners. It is
not a second Journey, an advertised feature, a stereo substitute or cleanup.
Later common steps and complete Actor/Scene/resource retirement remain open.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from pathlib import Path
import uuid
from urllib.parse import urlsplit

from adapters.chat_journey.source_chunks import json_digest,digest
from adapters.native_feature_observation import need,exact,integer,number,fresh
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.phase_input_fence import PhaseInputFence
from adapters.pico4.browser_history import PicoBrowserHistory
from adapters.pico4.browser_measurements import browser_status,measurement
from adapters.pico4.browser_sample_grammar import validate_sample
from adapters.pico4.browser_source import fixture
from adapters.pico4.browser_vm import PicoBrowserVm,reviewed
from adapters.chat_journey.archive_file import ClosedOriginalFile
import hashlib
from adapters.script_journey.history import same,pack,unpack
from feature_journeys.contract import arguments,result,identifier
from feature_journeys.fixtures import context as fixture_context
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending,validate as phase_packet
from feature_journeys.scenarios import SCENARIOS,VERSION as CONTRACT_VERSION,expand

VERSION=2
READS=(1,2)
LIMIT=len(SCENARIOS['world-web']['steps'])
INPUT_LIMIT=13  # Closed v16 grammar; only this original prefix is executable.


class PicoWorldWebPrefix:
    area='world-web'
    def __init__(self,adapter,target,source,foreign_fixture_url,*,role='primary'):
        need(isinstance(source,PhaseFixtureReader) and source.area==self.area and role in ('primary','actor'))
        self.adapter,self.target,self.source,self.role=adapter,target,source,role
        self.run,self.url=source.run,source.fixture_url;fixture(self.run,self.url)
        self.foreign=foreign_fixture_url.rstrip('/')+'/runs/'+self.run+'/';fixture(self.run,self.foreign)
        need(urlsplit(self.url).netloc!=urlsplit(self.foreign).netloc)
        self.lock=adapter._lock(target);self.root=adapter.state_path(target).parent
        self.store=PrivateFeatureState(self.root/'pico-world-web-prefix.json');self.disk=None;self.state=None
        self.scope=dict(runId=self.run,fixtureUrl=self.url,foreignFixtureUrl=self.foreign,sourceLock=str(self.lock.path),
            path=str(self.store.path),worldCode=reviewed('world')[0])
        self.scope_sha=json_digest(self.scope);self.role_sha=json_digest(role);self.fence=None;self.history=None;self.vm=None;self.runtime_guard=None;self.failed=False

    def read(self):
        self.lock.assert_held();body=self.store.read()
        if body is None:need(self.disk is None);return None
        exact(body,{'picoWorldWebPrefixVersion','scope','payload'})
        need(type(body['picoWorldWebPrefixVersion']) is int and body['picoWorldWebPrefixVersion'] in READS and same(body['scope'],self.scope))
        rows=unpack(body['payload']);need(len(rows)==1);value=rows[0]
        self.validate(value,version=body['picoWorldWebPrefixVersion']);self.disk=deepcopy(body);self.state=deepcopy(value);return self.state

    def control(self):
        self.lock.assert_held();need(not self.failed and self.scope_sha==json_digest(self.scope) and self.role_sha==json_digest(self.role)
            and self.source.run==self.run and self.source.area==self.area and self.source.fixture_url==self.url)
        if self.state is not None:need(same(self.store.read(),self.disk) and same(unpack(self.disk['payload']),[self.state]))

    def validate(self,value,*,version=VERSION):
        need(type(version) is int and version in READS);limit=3 if version==1 else LIMIT
        exact(value,{'binding','ownerToken','phase','fixture','completed','active','reserved','scriptUrl','inputs'})
        context(value['binding']);identifier(value['ownerToken'])
        need(value['phase'] in ('preparing','ready','acting') and type(value['reserved']) is bool
            and type(value['completed']) is list and len(value['completed'])<=limit and type(value['inputs']) is list and len(value['inputs'])<=256
            and (value['active'] is not None)==(value['phase']=='acting'))
        phase=value['fixture'];phase_packet(phase,run=self.run,area=self.area,request=phase['requestId'],epoch=phase['capturedEpochMs'])
        need(phase['active'] and phase['activations'][0]['stimulus']==dict(verb='baseline',inputs={}))
        tickets=[]
        for index,call in enumerate(value['completed']+([] if value['active'] is None else [value['active']])):
            parsed=arguments('feature.world-web.act',call);step=SCENARIOS[self.area]['steps'][index]
            need(index<limit and parsed['runId']==self.run and parsed['fixtureUrl']==self.url
                and same(dict(verb=parsed['verb'],inputs=parsed['inputs']),dict(verb=step['verb'],inputs=expand(step['inputs'],fixture_context(self.run)))))
            original=phase['activations'][index+1]
            need(original['ticket']==parsed['ticket'] and same(original['stimulus'],dict(verb=parsed['verb'],inputs=parsed['inputs'])))
            tickets.append(parsed['ticket'])
        need(len(tickets)==len(set(tickets)) and len(phase['activations'])==len(tickets)+1)
        if value['scriptUrl'] is not None:
            need(tickets and value['scriptUrl']==self.url+'tickets/'+tickets[0]+'/client.js')
        if value['completed']:need(value['scriptUrl'] is not None and value['reserved'])
        for row in value['inputs']:
            exact(row,{'ticket','original','anchor','complete','envelope'});identifier(row['ticket']);json_digest(row)
            need(type(row['complete']) is bool and type(row['original']) is dict)
            anchor=row['anchor'];exact(anchor,{'ticket','before','packet','hostMonotonic','epochMs'})
            need(row['ticket']==anchor['ticket'] and number(anchor['hostMonotonic'],0,1e15) and integer(anchor['epochMs'],1))
            for field in ('before','packet'):
                packet=anchor[field];phase_packet(packet,run=self.run,area=self.area,request=packet['requestId'],epoch=packet['capturedEpochMs'])
                need(packet['activations'][-1]['ticket']==row['ticket'])
            need(same(anchor['before']['activations'],anchor['packet']['activations']))

    def save(self,value,*,host_only=False):
        self.control();self.validate(value)
        body=dict(picoWorldWebPrefixVersion=VERSION,scope=self.scope,payload=pack([value]))
        self.store.write(body,self.disk);self.disk=deepcopy(body);self.state=deepcopy(value)
        # host_only is explicit at the call site; this function performs only
        # strict original grammar and private host reads/CAS/fsync in both paths.

    def runtime(self):
        self.control();need(self.state is not None)
        ui,observe,binding,guard,installed=self.adapter.normal_feature_runtime(self.target,read_only=True)
        need(same(binding,self.state['binding']) and guard() is not False)
        return ui,observe,binding,guard,installed

    def exact_phase(self):
        self.control();self.runtime();current=self.source.read(self.state['fixture'])
        need(same(current['status']['activations'],self.state['fixture']['activations']))
        return current

    def input_fence(self):
        if self.fence is None:
            parent=self
            class Fence(PhaseInputFence):
                def original(inner):
                    parent.control();need(parent.state is not None and parent.state['phase'] in ('preparing','acting'))
                    return parent.state['fixture']
                def _before_send(inner,command):
                    parent.input_command(command)
                    super()._before_send(command)
            self.fence=Fence(self.source);self.fence.stream_intent=self.stream_intent
        return self.fence

    def input_begin(self,original):
        self.control();need(self.role=='primary' and self.state['phase'] in ('preparing','acting')
            and (not self.state['inputs'] or self.state['inputs'][-1]['complete']))
        fence=self.input_fence();anchor=fence.mark();value=deepcopy(self.state)
        value['inputs'].append(dict(ticket=anchor['ticket'],original=deepcopy(original),anchor=deepcopy(anchor),complete=False,envelope=None))
        self.save(value);fence.check()

    def stream_intent(self,envelope):
        self.control();self.input_fence().host_fresh();need(self.state['inputs'] and not self.state['inputs'][-1]['complete']
            and self.state['inputs'][-1]['envelope'] is None)
        value=deepcopy(self.state);value['inputs'][-1]['envelope']=deepcopy(envelope);self.save(value,host_only=True)
        self.input_fence().host_fresh()

    def input_command(self,command):
        self.control();need(self.state['inputs'] and not self.state['inputs'][-1]['complete'])
        value=deepcopy(self.state);original=value['inputs'][-1]['original']
        need('nativeCommand' not in original);original['nativeCommand']=deepcopy(command);self.save(value)

    def input_result(self,original):
        self.control();need(self.state['inputs'] and not self.state['inputs'][-1]['complete'])
        value=deepcopy(self.state);need('result' not in value['inputs'][-1]['original'])
        value['inputs'][-1]['original']['result']=deepcopy(original);self.save(value)

    def input_done(self):
        self.control();need(self.state['inputs'] and not self.state['inputs'][-1]['complete'])
        value=deepcopy(self.state);value['inputs'][-1]['complete']=True;self.save(value);self.exact_phase()

    def io(self,*,read_only=True):return self.adapter.world_prefix_io(self.target,self,read_only=read_only)

    def prepare(self):
        need(self.role=='primary' and self.lock._owner is None)
        with self.lock.held(),self.adapter.existing_input_session(self.target):
            value=self.read()
            if value is not None:
                need(value['phase']=='ready' and value['reserved']);self.exact_phase();return deepcopy(value)
            need(not any(self.root.iterdir()))
            self.adapter.world_prefix_capture_guard(self.target,self.lock)
            phase=self.source.read();need(phase['verb']=='baseline' and len(phase['status']['activations'])==1)
            _ui,_observe,binding,guard,_installed=self.adapter.normal_feature_runtime(self.target,read_only=True);need(guard() is not False)
            self.save(dict(binding=deepcopy(binding),ownerToken=uuid.uuid4().hex,phase='preparing',fixture=deepcopy(phase['status']),
                completed=[],active=None,reserved=False,scriptUrl=None,inputs=[]))
            self.input_begin(dict(kind='source-control',operation='reserve'))
            packet=self.io(read_only=False).request(self.run,self.url,self.state['ownerToken'],'reserve')
            need(packet['source']=={'reserved':True});self.input_done()
            value=deepcopy(self.state);value.update(phase='ready',reserved=True);self.save(value);self.exact_phase()
            return deepcopy(value)

    def history_reader(self):
        self.control();need(self.state is not None)
        scope={**self.scope,'binding':self.state['binding'],'ownerToken':self.state['ownerToken'],'role':self.role}
        if self.history is None:
            self.history=PicoBrowserHistory(PrivateFeatureState(self.root/('pico-world-web-prefix-'+self.role+'-sources.json')),
                self.lock,scope,self.validate_frame,area=self.area)
        need(same(self.history.scope,dict(picoWorldBrowserHistoryVersion=1,**scope)))
        self.history.verify();return self.history

    def vm_reader(self):
        self.control();need(self.state['scriptUrl'] is not None)
        if self.vm is None:
            self.vm=self.adapter.world_prefix_vm(self.target,self)
            need(type(self.vm) is PicoBrowserVm and self.vm.surface()=='world')
        need(self.vm.scope['scriptUrl']==self.state['scriptUrl'] and self.vm.scope['role']==self.role
            and same(self.vm.scope['binding'],self.state['binding']))
        self.vm.verify();return self.vm

    def validate_frame(self,frame,previous):
        validate_sample(frame,previous,owner=self.state,run=self.run,fixture_url=self.url,foreign_url=self.foreign,
            vm=None if frame['vm'] is None else self.vm_reader(),image=lambda _name:need(False),area=self.area)

    def observation_admission(self):
        self.history_reader().verify()
        for role in ('primary','actor'):
            body=PrivateFeatureState(self.root/('pico-world-web-prefix-'+role+'-sources.json')).read()
            if body is not None:need(body['phase']=='ready' and body['intent'] is None)

    def act(self,call):
        call=deepcopy(arguments('feature.world-web.act',call));need(self.role=='primary' and self.lock._owner is None)
        with self.lock.held(),self.adapter.existing_input_session(self.target):
            self.read();self.control();need(self.state is not None and self.state['phase']=='ready')
            index=len(self.state['completed']);need(index<INPUT_LIMIT)
            step=SCENARIOS[self.area]['steps'][index]
            need(call['runId']==self.run and call['fixtureUrl']==self.url and same(dict(verb=call['verb'],inputs=call['inputs']),
                dict(verb=step['verb'],inputs=expand(step['inputs'],fixture_context(self.run)))))
            self.observation_admission();phase=self.source.read(self.state['fixture'])
            need(phase['ticket']==call['ticket'] and phase['verb']==call['verb'] and same(phase['inputs'],call['inputs'])
                and len(phase['status']['activations'])==index+2)
            value=deepcopy(self.state);value.update(phase='acting',active=call,fixture=deepcopy(phase['status']))
            if index==0:value['scriptUrl']=self.url+'tickets/'+call['ticket']+'/client.js'
            self.save(value);self.exact_phase()
            if index==0:
                manager=self.adapter.world_prefix_manager(self.target,self)
                manager.open();manager.load_source(self.state['scriptUrl'])
                manager.wait_rows(lambda rows:any(row['url']==self.state['scriptUrl'] for row in rows));manager.close_tablet()
                self.vm_reader().capture()
            else:
                packet=self.io().request(self.run,self.url,self.state['ownerToken'],'observe')
                current=packet['source']['current'];need(current)
                view=current['source']['nativeView']
                verb=call['verb']
                if verb in ('focus-type','clear-text'):
                    self.adapter.world_prefix_text(self.target,self,view,call['inputs'].get('text',''))
                elif verb=='navigate-foreign':
                    # The normal URL field receives the configured foreign
                    # listener and this actual original Script's ticket path.
                    original=urlsplit(view['sourceUrl']);foreign=urlsplit(self.foreign)
                    need(view['sourceUrl']==self.state['scriptUrl'].rsplit('/',1)[0]+'/index.html')
                    path=original.path.rsplit('/',1)[0]+'/'+call['inputs']['resource']
                    target=foreign.scheme+'://'+foreign.netloc+path
                    self.adapter.world_prefix_text(self.target,self,view,target,control='foreign')
                    self.adapter.world_prefix_click(self.target,self,view,'navigate')
                elif verb=='restore-resource':
                    # Reader-owned original phase activation changes only the
                    # test fixture. This adapter never restores the resource.
                    status=browser_status(self.source.client.request('/runs/'+self.run+'/browser'))
                    need(status['ready'] is True)
                else:
                    if verb in ('submit','foreign-origin-message'):control='bridge'
                    elif verb=='navigate':control={'page-b.html':'second','reference.html':'reference','recovery.html':'recovery'}[call['inputs']['resource']]
                    else:need(verb in ('back','reload'));control=verb
                    self.adapter.world_prefix_click(self.target,self,view,control)
            self.exact_phase();started=self.source.monotonic();native=self.adapter._native_feature_observer(self.target,read_only=True);requested=native.clock_ms()
            value=deepcopy(self.state);value['completed'].append(call);value.update(phase='ready',active=None);self.save(value)
            seal=self.seal(started,requested,[],native)
        self.finalize(seal)
        return dict(performed=True)

    def pins(self):
        names=sorted(self.root.iterdir());need(len(names)<=512)
        rows=[]
        for path in names:
            # Existing closed-original reader checks the full physical stamp,
            # immutable bytes and actual descriptor closure on every read.
            original=ClosedOriginalFile(path,0o600,lambda:PrivateFeatureState(path)._parent())
            raw,stamp=original.read();need(original.close())
            rows.append(dict(path=str(path),signature=stamp,sha256=hashlib.sha256(raw).hexdigest()))
        return rows

    def seal(self,started,requested,epochs,native):
        _ui,_observe,binding,guard,_installed=self.runtime();phase=self.exact_phase()
        need(same(binding,self.state['binding']))
        return dict(started=started,requested=requested,epochs=list(epochs)+[phase['status']['capturedEpochMs']],
            phase=deepcopy(phase['status']),guard=guard,native=native,body=deepcopy(self.disk),pins=self.pins())

    def finalize(self,seal):
        need(self.lock._owner is None and not self.failed)
        try:
            need(self.scope_sha==json_digest(self.scope) and same(self.store.read(),seal['body']) and same(self.pins(),seal['pins']))
            need(seal['guard']() is not False and seal['native'].guard() is not False)
            phase=self.source.read(seal['phase']);need(same(phase['status']['activations'],seal['phase']['activations']))
            need(same(self.store.read(),seal['body']) and same(self.pins(),seal['pins']))
            epoch=seal['native'].clock_ms();now=self.source.monotonic()
            need(number(now,seal['started'],seal['started']+1.5))
            for captured in seal['epochs']:
                fresh(captured,epoch);need(max(epoch-captured,seal['requested']-captured+math.ceil((now-seal['started'])*1000))<=1500)
        except BaseException:
            self.failed=True
            raise NativeUIError('Original World Web prefix publication is unavailable; journals remain owned') from None

    def observe(self):
        need(self.lock._owner is None);pending=False
        with self.lock.held():
            self.read();self.control();need(self.state is not None)
            if self.state['phase']!='ready':
                pending=True;started=self.source.monotonic()
                native_reader=self.adapter._native_feature_observer(self.target,read_only=True)
                requested=native_reader.clock_ms();seal=self.seal(started,requested,[],native_reader)
            else:
                phase=self.exact_phase();history=self.history_reader();sequence=1 if history.last is None else history.last['sample']['sequence']+1
                history.begin('sample',sequence);started=self.source.monotonic()
                native_reader=self.adapter._native_feature_observer(self.target,read_only=True);requested=native_reader.clock_ms();before=native_reader.read(0)
                vm=None
                if self.state['scriptUrl'] is not None:
                    reader=self.vm_reader();reader.capture();vm=dict(scopeSha256=digest(reader.scope),index=reader.frame_count-1,sha256=reader.frame_hash(-1))
                browser=self.io().request(self.run,self.url,self.state['ownerToken'],'observe')
                runtime=self.adapter.world_prefix_runtime(self.target,self).read(self.run,self.url)
                status=browser_status(self.source.client.request('/runs/'+self.run+'/browser'))
                _ui,observe,_binding,_guard,_installed=self.runtime();diagnostic,_epoch=observe(0)
                measured,resources=measurement(self.run,self.url,self.foreign,browser,status,runtime,diagnostic['scripts'],self.state['scriptUrl'],area=self.area)
                after=native_reader.read(before['sequence']);end=self.exact_phase()
                sample=result('feature.world-web.observe',dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.run,
                    sequence=sequence,capturedEpochMs=after['capturedEpochMs'],state=measured,artifacts=[],resources=resources,lifecycle=after['lifecycle']))
                frame=dict(phaseBefore=phase['status'],phaseAfter=end['status'],nativeBefore=before,nativeAfter=after,native=browser,runtime=runtime,
                    browser=status,diagnostic=diagnostic,scriptUrl=self.state['scriptUrl'],vm=vm,sample=deepcopy(sample),
                    startedHost=started,startedEpoch=requested,finishedHost=self.source.monotonic(),finishedEpoch=native_reader.clock_ms())
                history.finish(frame)
                epochs=[frame[key]['capturedEpochMs'] for key in ('nativeBefore','nativeAfter','native','runtime')]+[sample['capturedEpochMs'],diagnostic['sampleEpochMs']]
                epochs.extend(runtime['source'][key]['capturedEpochMs'] for key in ('nativeBefore','java','nativeAfter'))
                if vm is not None:
                    actual=self.vm.frame(vm['index']);epochs.extend([actual['objectsBefore']['source']['capturedEpochMs'],
                        actual['scripts']['capturedEpochMs'],actual['objectsAfter']['source']['capturedEpochMs']])
                returned=deepcopy(sample);seal=self.seal(started,requested,epochs,native_reader)
        self.finalize(seal)
        if pending:raise PhasePending('Original World Web input remains unresolved')
        return returned
