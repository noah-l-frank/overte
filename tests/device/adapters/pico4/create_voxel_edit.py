"""Create parent voxel stroke over normal tools and one owned original stream."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlsplit
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.pico4.create_voxel_ui import settings,ENUMS
from adapters.pico4.create_primitives import CANONICAL
from adapters.pico4.create_entities import validate as validate_entities,voxel_source
from adapters.pico4.create_models import idle
from adapters.pico4.create_callbacks import active,validate as validate_callbacks
from adapters.pico4.tablet_home import bind_home,validate as validate_home
from adapters.pico4.lifecycle_back import PicoLifecycleBack
from adapters.script_journey.history import pack,unpack
from adapters.native_script_work import scope as work_scope,validate as validate_work
from adapters.token_create_ui import nonce
from adapters.android.input_geometry import observed_grip_pose
from adapters.normal_ui import NativeUIError
from openxr_input.adapter_session import PicoOpenXrAdapterSession,PROFILE_PATH
from openxr_input.controller_protocol import validate_envelope

PROFILE=json.loads(PROFILE_PATH.read_text())
ATTEMPTS={'configure','tablet-close','stroke','tablet-open','restore','cleanup-restore','cleanup-tools'}


def include_pins(packet,manager):
    rows=[r for r in packet['source']['managers'] if r['membership']==manager];need(len(rows)==1);result={}
    for kind,file in (('modes','editModes.js'),('voxels','editVoxels.js')):
        relative='system/create/editModes/'+file
        code=(Path(__file__).resolve().parents[4]/('scripts/'+relative)).read_text(encoding='utf-8').encode('utf-16le')
        expected=dict(encoding='utf-16le-code-units',codeUnits=len(code)//2,sha256=hashlib.sha256(code).hexdigest())
        actual=[]
        for row in rows[0]['compiled']['compilations']:
            url=urlsplit(row['resourceName'])
            if url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment and url.path.endswith('/'+relative):
                need(all(row[k]==v for k,v in expected.items()));actual.append(row)
        need(len(actual)==1);result[kind]=deepcopy(actual[0])
    return result


def archive(value,binding,run):
    exact(value,{'native','ui'});rows=unpack(value['native']);need([r['role'] for r in rows]==['entities','callbacks','work']);result={}
    for row in rows:
        exact(row,{'role','raw','sha256'});need(type(row['raw']) is str and hashlib.sha256(row['raw'].encode()).hexdigest()==row['sha256'])
        packet=decode(row['raw']);pid=int(binding['processIdentity'].split(':')[0]);need(packet['processId']==pid)
        if row['role']=='entities':validate_entities(packet,packet['requestId'],pid,packet['capturedEpochMs'],run)
        elif row['role']=='callbacks':validate_callbacks(packet,packet['requestId'],pid,packet['capturedEpochMs'])
        else:validate_work(packet,dict(schemaVersion=1,commandId=packet['requestId'],action='feature-script-work-observe',managerInstance=packet['source']['manager']['instance']),pid,packet['capturedEpochMs'])
        result[row['role']]=packet
    need(len({p['instance'] for p in result.values()})==1)
    from adapters.pico4.navigation import validate_snapshot
    validate_snapshot(value['ui'],pid,value['ui']['updatedEpochMs']);need(value['ui']['bridgeId']==binding['sessionId'])
    return result|dict(ui=deepcopy(value['ui']))


def validate_edit(value,binding,run):
    if value is None:return
    exact(value,{'ticket','before','settings','pins','attempted','streams','after','settingsRestored','outcome'})
    need(nonce(value['ticket']) and type(value['attempted']) is list and len(set(value['attempted']))==len(value['attempted'])
        and set(value['attempted'])<=ATTEMPTS and value['outcome'] in ('editing','edited','cancelled') and type(value['settingsRestored']) is bool)
    settings(value['settings']);before=archive(value['before'],binding,run);original=before['entities']['source']['entities']
    need(len(original)==1 and original[0]['type']=='PolyVox' and voxel_source(original[0]['voxels'])==CANONICAL)
    modes=[r for r in before['ui']['controls'] if r['id']=='create-voxel.mode'];need(len(modes)==1 and modes[0]['settings']==value['settings'])
    pins=include_pins(before['callbacks'],before['work']['source']['manager']);need(value['pins']==pins)
    need(type(value['streams']) is list and len(value['streams'])<=3)
    need(not value['streams'] or 'configure' in value['attempted'])
    for index,kind in enumerate(('tablet-close','stroke','tablet-open')):
        if len(value['streams'])>index:need(kind in value['attempted'])
    operations=['tablet.close','input.primary','tablet.open'];previous=None
    for index,row in enumerate(value['streams']):
        exact(row,{'operation','arguments','before','envelope','neutral','after'})
        need(row['operation']==operations[index]);home=row['before'];validate_home(home,home['commandId'],int(binding['processIdentity'].split(':')[0]),home['capturedEpochMs'])
        if index:
            prior=value['streams'][index-1]['after'];need(prior is not None
                and all(home[k]==prior[k] for k in ('instance','generation','tabletId','homeId'))
                and home['capturedEpochMs']>=prior['capturedEpochMs'] and home['elapsedMs']>=prior['elapsedMs']
                and home['sourceSequence']>prior['sourceSequence'])
        if row['operation']=='input.primary':
            expected=observed_grip_pose(home['sensorToWorld'],home['headPosition'],original[0]['position']);need(not home['tabletShown'])
        else:expected=dict(holdMilliseconds=1000);need(home['tabletShown']==(row['operation']=='tablet.close'))
        need(row['arguments']==expected)
        if row['envelope'] is not None:
            packet=row['envelope'];validate_envelope(packet,PROFILE)
            need(packet['commands']==[dict(id=row['operation'].replace('.','-')+'-'+str(packet['sequence']),operation=row['operation'],arguments=expected)])
            if previous is not None:need(packet['sessionNonce']==previous['sessionNonce'] and packet['sequence']>previous['sequence'])
            previous=packet
        else:need(index==len(value['streams'])-1 and row['neutral'] is None and row['after'] is None)
        if row['neutral'] is not None:
            need(row['envelope'] is not None);PicoLifecycleBack.neutral(row['neutral'],row['envelope'],home['capturedEpochMs'])
        if row['after'] is not None:
            after=row['after'];validate_home(after,after['commandId'],int(binding['processIdentity'].split(':')[0]),after['capturedEpochMs'])
            need(row['neutral'] is not None and after['capturedEpochMs']>=row['neutral']['updatedEpochMs']-250
                and all(after[k]==home[k] for k in ('instance','generation','tabletId','homeId'))
                and after['sourceSequence']>home['sourceSequence'] and after['tabletShown']==(row['operation']=='tablet.open'))
    if value['after'] is not None:
        after=archive(value['after'],binding,run);a=original[0];rows=after['entities']['source']['entities'];need(len(rows)==1);b=rows[0]
        need(all(a[k]==b[k] for k in ('id','createdEpochUs','name','type','hostType','position','rotation','dimensions','parentId')))
        need(len(value['streams'])>=2 and b['lastEditedEpochUs']>=max(a['lastEditedEpochUs'],value['streams'][1]['before']['capturedEpochMs']*1000))
        old,new=voxel_source(a['voxels']),voxel_source(b['voxels'])
        need(old!=new and len(new)==512 and 0<sum(v!=0 for v in new)<64 and all(y==x or x==255 and y==0 for x,y in zip(old,new))
            and a['voxels']['dataBase64']!=b['voxels']['dataBase64'])
    if value['outcome']=='cancelled':need(not value['streams'] and value['settingsRestored'])
    if value['outcome']=='edited':need(value['after'] is not None and value['settingsRestored'] and len(value['streams'])==3 and all(r['after'] is not None for r in value['streams']))
    if value['settingsRestored'] and value['after'] is not None:
        modes=[r for r in after['ui']['controls'] if r['id']=='create-voxel.mode'];need(len(modes)==1 and modes[0]['settings']==value['settings'])


class CreateVoxelEdit:
    def voxel_state(self):
        value=self.state().get('voxelEdit');need(value is not None);return value
    def voxel_update(self,**changes):
        value=deepcopy(self.voxel_state());value.update(deepcopy(changes));self.mark(voxelEdit=value)
    def voxel_attempt(self,kind):
        value=self.voxel_state();need(kind in ATTEMPTS and kind not in value['attempted']);self.voxel_update(attempted=value['attempted']+[kind])
    def voxel_controls(self):
        return self.adapter._create_voxel_controls(self.target,lambda original:self.record_input('voxel',original),before_send=self.dispatch_admission)
    def voxel_scroll(self,direction):
        controls=self.controls();before=controls.capture();bar=controls.row(before,'create.scrollbar')
        if bar is None or direction=='up' and bar['position']<=.000001 or direction=='down' and bar['position']+bar['size']>=.999999:return False
        controls.input('create.scrollbar','scroll',direction)
        controls.wait(lambda v:bool(controls.row(v,'create.scrollbar') and controls.row(v,'create.scrollbar')['position']!=bar['position']));return True
    def voxel_settings(self):
        tools=self.voxel_controls();observed=tools.wait(lambda v:tools.row(v,'create-voxel.mode') is not None)
        row=tools.row(observed,'create-voxel.mode');need(row is not None)
        return deepcopy(row['settings'])
    def voxel_apply_settings(self,original):
        settings(original);tools=self.voxel_controls();scroll=self.voxel_scroll
        tools.choose('create-voxel.mode',1,scroll)
        for identifier,key in (('shape','voxelEditMode'),('dynamics','voxelEditDynamics'),('pointer','voxelPointerMode')):
            tools.choose('create-voxel.'+identifier,ENUMS[key].index(original[key]),scroll)
        tools.reveal('create-voxel.remove',scroll)
        if tools.row(tools.capture(),'create-voxel.remove')['checked']!=original['voxelRemove']:tools.input('create-voxel.remove')
        for identifier,key in (('diameter','voxelSphereSize'),('reach','voxelBrushLength')):tools.replace('create-voxel.'+identifier,str(original[key]),scroll)
        tools.reveal('create-voxel.apply',scroll);tools.input('create-voxel.apply')
        expected=deepcopy(original)|dict(createAppMode='voxel')
        tools.reveal('create-voxel.mode',scroll);tools.wait(lambda v:bool(tools.row(v,'create-voxel.mode') and tools.row(v,'create-voxel.mode')['settings']==expected))
        if original['createAppMode']=='object':tools.choose('create-voxel.mode',0,scroll)
        need(self.voxel_settings()==original)
    def voxel_session(self):
        session=self.adapter.pico_input_session(self.target);need(isinstance(session,PicoOpenXrAdapterSession));return session
    def voxel_stage(self,operation):
        value=self.voxel_state();expected=['tablet.close','input.primary','tablet.open'];need(len(value['streams'])<3 and operation==expected[len(value['streams'])])
        actual=self.sample();ui,_binding=self.runtime();native=self.adapter._native_feature_observer(self.target)
        home=bind_home(self.adapter,self.target,native).source.capture();phase=self.phase_fence()
        self.fresh_sample(actual);anchor=deepcopy(actual['sampleAnchor']);started=anchor['hostStarted'];native_epoch=native.clock_ms()
        need(integer(native_epoch,anchor['nativeEpochMs']))
        need(home['tabletShown']==(operation=='tablet.close') if operation!='input.primary' else not home['tabletShown'])
        original=archive(value['before'],self.state()['binding'],self.run)['entities']['source']['entities'][0]
        current=self.primitive_row(actual);need(current is not None and all(current[k]==original[k]
            for k in ('id','createdEpochUs','name','position','rotation','dimensions','parentId')))
        arguments=observed_grip_pose(home['sensorToWorld'],home['headPosition'],original['position']) if operation=='input.primary' else dict(holdMilliseconds=1000)
        stream=dict(operation=operation,arguments=arguments,before=deepcopy(home),envelope=None,neutral=None,after=None)
        self.voxel_update(streams=value['streams']+[stream]);binding=self.state()['binding'];session=self.voxel_session()
        def host_fresh():
            now=self.source.monotonic();need(number(now,started,1e15))
            epoch=max(native_epoch,anchor['nativeEpochMs']+math.ceil((now-started)*1000))
            for role in ('callbacks','entities','dialogs','resources','work','lifecycle'):fresh(actual[role]['capturedEpochMs'],epoch)
            fresh(actual['ui']['updatedEpochMs'],epoch);fresh(home['capturedEpochMs'],epoch);fresh(phase['capturedEpochMs'],epoch)
        def intent(envelope):
            current=deepcopy(self.voxel_state());row=current['streams'][-1];need(row['envelope'] is None)
            row['envelope']=deepcopy(envelope);host_fresh();self.mark(voxelEdit=current);host_fresh()
        def before_publish(envelope):
            # No guard/source/HTTP/session IO while the original session lock
            # is held. Only validate the prior durable envelope and host age.
            need(self.voxel_state()['streams'][-1]['envelope']==envelope);host_fresh()
        session.stage(binding['processIdentity'],operation,arguments,intent=intent,before_publish=before_publish)
        self.voxel_stream_finish(actual)
    def voxel_stream_finish(self,actual=None):
        value=self.voxel_state();row=value['streams'][-1];need(row['envelope'] is not None)
        native=self.adapter._native_feature_observer(self.target);session=self.voxel_session();binding=self.state()['binding']
        if row['neutral'] is None:
            neutral=session.require_owned_neutral(binding['processIdentity'],row['envelope']);PicoLifecycleBack.neutral(neutral,row['envelope'],row['before']['capturedEpochMs'])
            fresh(neutral['updatedEpochMs'],native.clock_ms());value['streams'][-1]['neutral']=deepcopy(neutral);self.mark(voxelEdit=value)
        source=bind_home(self.adapter,self.target,native).source;started=source.monotonic()
        for attempt in range(81):
            current=source.capture();row=self.voxel_state()['streams'][-1]
            need(all(current[k]==row['before'][k] for k in ('instance','generation','tabletId','homeId')) and source.monotonic()-started<=8)
            if current['tabletShown']==(row['operation']=='tablet.open'):
                need(current['capturedEpochMs']>=row['neutral']['updatedEpochMs']-250 and current['capturedEpochMs']>=row['before']['capturedEpochMs']
                    and current['elapsedMs']>=row['before']['elapsedMs'] and current['sourceSequence']>row['before']['sourceSequence'])
                value=deepcopy(self.voxel_state());value['streams'][-1]['after']=deepcopy(current);self.mark(voxelEdit=value);return current
            need(attempt<80);source.sleep(.1)
        need(False)
    def voxel_effect(self,actual):
        value=self.voxel_state();original=archive(value['before'],self.state()['binding'],self.run)['entities']['source']['entities'][0]
        row=self.primitive_row(actual);need(row is not None)
        for key in ('id','createdEpochUs','name','type','hostType','position','rotation','dimensions','parentId'):need(row[key]==original[key])
        old,new=voxel_source(original['voxels']),voxel_source(row['voxels'])
        need(len(value['streams'])>=2)
        ready=(row['lastEditedEpochUs']>=max(original['lastEditedEpochUs'],value['streams'][1]['before']['capturedEpochMs']*1000)
            and row['voxels']['ready'] and row['voxels']['meshReady'] and row['voxels']['vertices']>0 and row['voxels']['indices']>0
            and len(new)==512 and old!=new and 0<sum(v!=0 for v in new)<64 and all(y==x or x==255 and y==0 for x,y in zip(old,new))
            and original['voxels']['dataBase64']!=row['voxels']['dataBase64'] and idle(actual['scope']) and not active(actual['callbacks']))
        before=archive(value['before'],self.state()['binding'],self.run)
        for pin in value['pins'].values():ready=ready and idle(work_scope(actual['work'],pin))
        from adapters.pico4.create_polyvox_resources import joined
        native=actual['entities']['source'];need(native['createEntitySourceVersion'] in (5,6))
        ready=ready and joined(native['polyvoxResources'],row['id'])
        previous=work_scope(before['work'],value['pins']['voxels']);current=work_scope(actual['work'],value['pins']['voxels'])
        return ready and current['timerRegistrations']>previous['timerRegistrations'] and current['timerInvocations']>previous['timerInvocations']
    def voxel_settle(self):
        ui,_binding=self.runtime();started=ui.monotonic();quiet=clocks=stable=None
        for attempt in range(103):
            actual=self.sample();now=ui.monotonic();row=self.primitive_row(actual);ready=self.voxel_effect(actual)
            epochs=(actual['entities']['capturedEpochMs'],actual['work']['source']['work']['capturedEpochMs'],actual['ui']['elapsedMs'])
            from adapters.pico4.create_polyvox_resources import stable as resource_stable
            observed=(row,resource_stable(actual['entities']['source']['polyvoxResources']))
            if ready and (stable is None or stable==observed):
                quiet=now if quiet is None else quiet;clocks=epochs if clocks is None else clocks;stable=deepcopy(observed)
                if now-quiet>=3 and all(b-a>=3000 for a,b in zip(clocks,epochs)):
                    self.phase_fence();self.fresh_sample(actual);return actual
            else:quiet=clocks=stable=None
            need(now-started<20 and attempt<102);ui.sleep(.2)
        need(False)
    def voxel_edit(self):
        initial=self.sample()
        need(self.state()['voxelEdit'] is None and self.state()['subject']=='primitive' and initial['ui'].get('createVoxelControlsVersion')==1
            and initial['entities']['source']['createEntitySourceVersion'] in (5,6));self.controls().tab(3)
        actual=self.sample();row=self.primitive_row(actual);need(row is not None and row['rotation']==[0,0,0,1] and voxel_source(row['voxels'])==CANONICAL)
        need(actual['entities']['source']['createEntitySourceVersion'] in (5,6))
        pins=include_pins(actual['callbacks'],actual['manager']);need(all(idle(work_scope(actual['work'],p)) for p in pins.values()))
        original=self.voxel_settings();value=dict(ticket=self.state()['pending'],before=self.primitive_proof(actual),settings=original,pins=pins,
            attempted=[],streams=[],after=None,settingsRestored=False,outcome='editing');self.mark(voxelEdit=value)
        self.voxel_attempt('configure');self.voxel_apply_settings(dict(createAppMode='voxel',voxelEditMode='cube',voxelSphereSize=.5,
            voxelEditDynamics='click',voxelRemove=True,voxelPointerMode='laser',voxelBrushLength=.5))
        self.voxel_attempt('tablet-close');self.voxel_stage('tablet.close')
        self.voxel_attempt('stroke');self.voxel_stage('input.primary');self.voxel_settle()
        self.voxel_attempt('tablet-open');self.voxel_stage('tablet.open')
        self.controls().tab(3);self.voxel_attempt('restore');self.voxel_apply_settings(original)
        self.voxel_update(settingsRestored=True);actual=self.voxel_settle();self.voxel_update(after=self.primitive_proof(actual),outcome='edited')
    def voxel_reconcile(self):
        value=self.voxel_state()
        if value['streams'] and value['streams'][-1]['envelope'] is not None and value['streams'][-1]['after'] is None:self.voxel_stream_finish()
        need(len(self.voxel_state()['streams'])==3 and all(r['after'] is not None for r in self.voxel_state()['streams'])
            and 'restore' in value['attempted'] and self.voxel_settings()==value['settings'])
        self.voxel_update(settingsRestored=True);actual=self.voxel_settle();self.voxel_update(after=self.primitive_proof(actual),outcome='edited')
    def voxel_final(self,actual):
        value=self.state().get('voxelEdit')
        if value is not None and self.state()['calls'][-1]['verb']=='voxel-edit':
            need(value['outcome']=='edited' and self.voxel_settings()==value['settings'] and self.voxel_effect(actual))
            original=archive(value['after'],self.state()['binding'],self.run);need(original['entities']['source']['entities']==actual['entities']['source']['entities'])

    def voxel_cleanup(self):
        """Distinct restore, with no controller replay after uncertain input."""
        value=self.state().get('voxelEdit')
        if value is None:return
        self.phase_fence()
        if value['streams']:
            last=value['streams'][-1]
            if last['envelope'] is not None and last['after'] is None:self.voxel_stream_finish()
            value=self.voxel_state()
            need(len(value['streams'])==3 and all(r['after'] is not None for r in value['streams']))
        # A lost normal restore may already have returned. Observe first, and
        # never repeat either the original restore or this distinct cleanup.
        tools=self.voxel_controls()
        if tools.row(tools.capture(),'create-voxel.mode') is None:
            need('cleanup-tools' not in value['attempted']);self.voxel_attempt('cleanup-tools')
            controls=self.controls()
            if controls.row(controls.capture(),'create.page',enabled=False) is None:self.open_editor()
            self.controls().tab(3)
        current=self.voxel_settings()
        if current!=value['settings']:
            need('cleanup-restore' not in value['attempted'])
            self.voxel_attempt('cleanup-restore');self.voxel_apply_settings(value['settings'])
        need(self.voxel_settings()==value['settings']);self.voxel_update(settingsRestored=True)
        if not value['streams']:self.voxel_update(outcome='cancelled')
        elif value['outcome']!='edited':
            actual=self.voxel_settle();self.voxel_update(after=self.primitive_proof(actual),outcome='edited')
        self.phase_fence()
