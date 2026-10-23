"""Normal Pico open/Capture/Cancel composition with original file ownership.

This is the first part of the unchanged v16 recipe, not a Snapshot verdict.
All original journals remain obligations for the subsequent capture/export flow.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import uuid

from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.native_script_observation import NativeScriptObservation
from adapters.native_script_roots import NativeScriptRoots,root_url,validate as roots_packet
from adapters.native_script_work import NativeScriptWork,validate as work_packet,scope as work_scope
from adapters.pico4.snapshot import PicoSnapshot,MODES,FORMATS
from adapters.pico4.snapshot_cancel import PicoSnapshotCancel,command as cancel_command,validate as cancel_packet,idle
from adapters.pico4.snapshot_capture_files import PicoSnapshotCaptureFiles
from adapters.pico4.snapshot_capture_source import validate as file_packet,command as file_command,continuity as file_continuity
from adapters.pico4.snapshot_script_originals import PicoSnapshotScriptOriginals,validate as script_packet,accept as script_accept
from adapters.pico4.snapshot_script_history import join_compilation
from adapters.pico4.snapshot_cancel_originals import SnapshotCancelOriginals
from adapters.pico4.snapshot_platform import PicoSnapshotPlatform,profile as platform_profile
from adapters.pico4 import snapshot_originals as native_source
from adapters.pico4.navigation import NativeNavigationIO,validate_snapshot,identifier
from adapters.script_journey.history import pack,unpack,canonical
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from feature_journeys.contract import typed_equal
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from openxr_input.controller_protocol import validate_envelope
from snapshot_observation import inspect_snapshot

VERSION=2
READS=(1,2)
CANCEL_STAGES=('arm-issued','prepared','open-issued','opened','cancel-issued','cancel-observed',
        'quiet-issued','cancel-quiet','job-retire-issued','partial-ready')
CAPTURE_STAGES=('capture-prepare-issued','capture-issued','captured','still-quiet-issued','still-ready')
STAGES=CANCEL_STAGES+CAPTURE_STAGES


def original(row,limit):
    exact(row,{'raw','sha256'})
    need(type(row['raw']) is str and len(row['raw'].encode())<=limit
        and hashlib.sha256(row['raw'].encode()).hexdigest()==row['sha256'])
    return decode(row['raw'])


class PicoSnapshotCancelOwner:
    """One parent and one exact shared source lock; no cold ordinary resend."""
    def __init__(self,path,run,binding,snapshot,native,script,cancel,files,roots,execution,work,platform,session,source):
        need(native_source.nonce(run) and isinstance(snapshot,PicoSnapshot)
            and isinstance(native,native_source.PicoSnapshotOriginals) and isinstance(script,PicoSnapshotScriptOriginals)
            and isinstance(cancel,PicoSnapshotCancel) and isinstance(files,PicoSnapshotCaptureFiles)
            and isinstance(roots,NativeScriptRoots) and isinstance(execution,NativeScriptObservation) and isinstance(work,NativeScriptWork)
            and isinstance(platform,PicoSnapshotPlatform)
            and isinstance(snapshot.ui.io,NativeNavigationIO) and isinstance(session,PicoOpenXrAdapterSession)
            and isinstance(source,PhaseFixtureReader) and source.area=='snapshots' and source.run==run)
        self.store,self.run,self.binding=PrivateFeatureState(path),run,deepcopy(context(binding))
        self.snapshot,self.native,self.script,self.cancel,self.files=snapshot,native,script,cancel,files
        self.roots,self.execution,self.work,self.platform,self.session,self.source=roots,execution,work,platform,session,source
        self.lock=native.lock
        need(all(reader.lock is self.lock for reader in (script,cancel,files.source))
            and all(reader.pid==native.pid for reader in (script,cancel,files.source,roots,execution,work))
            and native.pid==int(binding['processIdentity'].split(':')[0])
            and files.context==binding and snapshot.ui.context['processIdentity']==binding['processIdentity']
            and all(snapshot.ui.context[key]==binding[key] for key in ('sourceRevision','artifactSha256'))
            and self.store.path==self.lock.path.with_name('snapshot-cancel-owner.json')
            and session.bound_process_identity()==binding['processIdentity'])
        self.prefix='parity-'+run[:16]+'-animated'
        self.still_prefix='parity-'+run[:16]+'-still-png';self.encoding_version=VERSION;self.decoded_cache={}
        self.disk=self.state=self.anchor=self.controller_anchor=self.controller_envelope=None
        self.current=False;self.last_clock=None;self.save_owner=None
        with session._lock():self.session_origin=deepcopy(session._load())
        self.reviewed=json.loads(Path(__file__).with_name('snapshot-script-pin.v1.json').read_text())
        self.qml_callback=self.before_qml;self.cancel_callback=self.before_cancel;self.file_callback=self.before_file
        self.controller_callback=self.before_controller;self.intent_callback=self.controller_intent;self.publish_callback=self.before_publish
        snapshot.ui.io.bind_before_send(self.qml_callback)
        snapshot.ui.io.bind_controller_admission(self.controller_callback,intent=self.intent_callback,before_publish=self.publish_callback)
        # The factory installs these exact callbacks before constructing this
        # owner. A different callback cannot later take over either publisher.
        with self.lock.held():
            self.originals=SnapshotCancelOriginals(self.store.path.with_name('snapshot-cancel-originals.json'),run,self.binding)
            self.load()

    def now(self):
        value=self.native.monotonic();need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock))
        self.last_clock=value;return value

    def phase(self,value):
        phase_packet(value,run=self.run,area='snapshots',request=value['requestId'],epoch=value['capturedEpochMs'])
        need(value['active'] and value['activations']);return value

    def frame_context(self):
        return dict(run=self.run,pid=self.native.pid,bridge=self.binding['sessionId'])

    def frame(self,row):
        # These are pure DTO validators. A previously accepted exact original
        # may be decoded again by many journal/history joins in one warm owner.
        # Fresh source reads, filesystem signatures and cross-frame continuity
        # are outside this cache and still run at every original boundary.
        key=hashlib.sha256(canonical(dict(context=self.frame_context(),original=row))).digest()
        cache=getattr(self,'_original_frame_cache',None)
        if cache is None:self._original_frame_cache=cache={}
        if key in cache:return deepcopy(cache[key])
        result=self.original_frame(row)
        if len(cache)>=128:cache.pop(next(iter(cache)))
        cache[key]=deepcopy(result);return result

    def original_frame(self,row):
        exact(row,{'native','script','ui','files','inventory','work','hostMonotonic'})
        native=original(row['native'],native_source.LIMIT);script=original(row['script'],65536)
        native_source.validate(native,self.run,native['commandId'],self.native.pid,native['capturedEpochMs'])
        script_packet(script,self.run,script['commandId'],self.native.pid,script['capturedEpochMs'])
        need(native['snapshotNativeCaptureVersion']==2 and script['snapshotScriptOriginalsVersion']==2)
        validate_snapshot(row['ui'],self.native.pid,row['ui']['updatedEpochMs'])
        exact(row['files'],{'raw','sha256','request'})
        packet=original({key:row['files'][key] for key in ('raw','sha256')},262144)
        file_packet(packet,row['files']['request'],self.native.pid,packet['capturedEpochMs'])
        need(packet['runId']==self.run and row['ui']['bridgeId']==self.binding['sessionId'] and number(row['hostMonotonic'],0,1e15))
        exact(row['inventory'],{'files','rows','capturedEpochMs'})
        need(row['inventory']['capturedEpochMs']==packet['capturedEpochMs']
            and type(row['inventory']['files']) is list and type(row['inventory']['rows']) is list)
        events=script['history']['events']
        if events:
            caller=events[-1]['caller'];value=row['work']
            request=dict(schemaVersion=1,commandId=value['requestId'],action='feature-script-work-observe',managerInstance=caller['manager']['instance'])
            work_packet(value,request,self.native.pid,value['capturedEpochMs'])
            need(typed_equal(value['source']['manager'],caller['manager']) and typed_equal(value['source']['code'],caller['code']))
            work_scope(value,caller['compilation'])
        else:need(row['work'] is None)
        clocks=self.clocks(row)[1:]
        need(max(clocks)-min(clocks)<=1500);return native,script,packet

    def validate(self,state,*,host_only=False):
        extra={'platform','migration','stillPlan','capture','captureQuiet'} if self.encoding_version==2 else set()
        exact(state,{'stage','source','baseline','sessionOrigin','frames','deliveries','plan','job','requests','replies','vm','quiet'}|extra)
        need(self.encoding_version in READS and (self.encoding_version==2 or state['stage'] in CANCEL_STAGES))
        origin=state['sessionOrigin'];exact(origin,{'schemaVersion','sessionNonce','processIdentity','nextSequence'})
        need(type(origin['schemaVersion']) is int and origin['schemaVersion']==self.session_origin['schemaVersion']
            and origin['processIdentity']==self.binding['processIdentity']
            and origin['sessionNonce']==self.session_origin['sessionNonce'] and integer(origin['nextSequence'],1,0xffffffff))
        need(state['stage'] in STAGES and type(state['frames']) is list and len(state['frames'])<=128
            and (state['frames'] or state['stage']=='arm-issued')
            and type(state['deliveries']) is list and len(state['deliveries'])<=128
            and type(state['requests']) is list and len(state['requests'])<=64
            and type(state['replies']) is list and len(state['replies'])<=64
            and native_source.nonce(state['job']) and type(state['quiet']) is list and len(state['quiet'])<=1)
        self.phase(state['source']);self.phase(state['baseline'])
        need(state['baseline']['activations'][-1]['stimulus']==dict(verb='baseline',inputs={})
            and state['source']['activations'][:len(state['baseline']['activations'])]==state['baseline']['activations']
            and all(state['source'][key]==state['baseline'][key] for key in ('instance','createdEpochMs')))
        verb='baseline' if state['stage'] in ('arm-issued','prepared') else 'open' if state['stage'] in ('open-issued','opened') else 'capture' if state['stage'] in CAPTURE_STAGES else 'capture-cancel'
        inputs=dict(mode='animated',format='png') if verb=='capture-cancel' else dict(mode='still',format='png') if verb=='capture' else {}
        need(state['source']['activations'][-1]['stimulus']==dict(verb=verb,inputs=inputs))
        previous_native=previous_script=previous_files=previous_work=None;clock=0
        for row in state['frames']:
            native,script,_packet=self.frame(row)
            previous_native=native_source.accept(previous_native,native);previous_script=script_accept(previous_script,script)
            if previous_files is not None:file_continuity(previous_files,_packet)
            previous_files=_packet
            if row['work'] is not None:
                value=row['work'];request=dict(schemaVersion=1,commandId=value['requestId'],action='feature-script-work-observe',managerInstance=value['source']['manager']['instance'])
                work_packet(value,request,self.native.pid,value['capturedEpochMs'],previous=previous_work);previous_work=value
            need(row['hostMonotonic']>=clock);clock=row['hostMonotonic']
        if state['plan'] is not None:
            plan=state['plan'];need(type(plan) is dict and native_source.nonce(plan.get('id')) and plan.get('runId')==self.run
                and plan.get('prefix')==self.prefix and plan.get('sealed') is False)
            plans=[row for row in self.frame(state['frames'][-1])[2]['source']['plans'] if row['id']==plan['id']]
            need(len(plans)==1 and typed_equal(plans[0],plan))
        requests={}
        for request in state['requests']:
            cancel_command(request);need(request['runId']==self.run and request['jobId']==state['job'] and request['commandId'] not in requests)
            requests[request['commandId']]=request
        starts=[request for request in requests.values() if request['operation']=='start'];need(len(starts)<=1)
        for saved in state['replies']:
            exact(saved,{'raw','sha256','anchor','request'});need(saved['request']['commandId'] in requests)
            packet=original({key:saved[key] for key in ('raw','sha256')},262144)
            exact(packet,{'commandId','packet'});value=packet['packet'];request=requests[packet['commandId']]
            need(typed_equal(saved['request'],request));cancel_packet(value,request,self.native.pid,value['capturedEpochMs'])
            exact(saved['anchor'],{'hostMonotonic','nativeEpochMs'})
            need(number(saved['anchor']['hostMonotonic'],0,1e15) and integer(saved['anchor']['nativeEpochMs'],1))
        next_controller=origin['nextSequence']
        for delivery in state['deliveries']:
            exact(delivery,{'kind','command','frame','stage'});need(delivery['kind'] in ('qml','controller','files','cancel')
                and delivery['stage'] in STAGES and integer(delivery['frame'],0,len(state['frames'])-1))
            if delivery['kind']=='qml':
                command=delivery['command'];self.allowed(command,delivery['stage'])
                ui=state['frames'][delivery['frame']]['ui'];control=self.snapshot.ui.control(ui,command['controlId'])
                need(control is not None and command['controlToken']==control['token'] and command['generation']==ui['generation']
                    and command['sequence']==ui['lastCommandSequence']+1 and 0<=ui['elapsedMs']-command['observedElapsedMs']<=1500)
            elif delivery['kind']=='controller':
                validate_envelope(delivery['command'],self.session.profile)
                command=delivery['command'];need(len(command['commands'])==1 and command['commands'][0]['operation']=='tablet.open'
                    and command['sessionNonce']==origin['sessionNonce'] and command['sequence']==next_controller
                    and command['commands'][0]['arguments']==dict(holdMilliseconds=1000)
                    and command['commands'][0]['id']=='tablet-open-'+str(command['sequence']))
                next_controller+=1
            elif delivery['kind']=='cancel':
                request=delivery['command'];need(request['commandId'] in requests)
                if request['operation']=='start':
                    frame=state['frames'][delivery['frame']];native,script,packet=self.frame(frame)
                    need(state['plan'] is not None and not script['history']['events'] and not native['requests']
                        and not packet['source']['rows'] and not packet['source']['captures']
                        and any(typed_equal(plan,state['plan']) for plan in packet['source']['plans']))
                    command=request['request'];ui=frame['ui'];control=self.snapshot.ui.control(ui,'snapshot.capture')
                    need(control is not None and command['controlToken']==control['token'] and command['generation']==ui['generation']
                        and command['bridgeId']==ui['bridgeId'] and command['sequence']==ui['lastCommandSequence']+1
                        and 0<=ui['elapsedMs']-command['observedElapsedMs']<=1500)
            else:
                command=file_command(delivery['command'])
                selected=state['plan'] if command['prefix']==self.prefix else state.get('stillPlan')
                need(command['runId']==self.run and command['operation']=='plan' and command['prefix'] in (self.prefix,self.still_prefix)
                    and (selected is None or command['operationId']==selected['id']))
                need((command['prefix']==self.prefix and delivery['stage']=='cancel-issued')
                    or (self.encoding_version==2 and command['prefix']==self.still_prefix and delivery['stage']=='capture-prepare-issued'))
        captures=[row for row in state['deliveries'] if row['kind']=='qml' and row['command']['controlId']=='snapshot.capture']
        need(len(captures)<=1)
        for delivery in captures:self.capture_admission(state['frames'][delivery['frame']],state)
        for window in state['quiet']:
            exact(window,{'first','last'});need(integer(window['first'],0,len(state['frames'])-1) and integer(window['last'],window['first']+1,len(state['frames'])-1))
            rows=state['frames'][window['first']:window['last']+1];clocks=[]
            for row in rows:self.no_output(row,state);clocks.append(self.clocks(row))
            need(all(all(0<=b-a<=500 for a,b in zip(old,new)) for old,new in zip(clocks,clocks[1:]))
                and all(b-a>=3000 for a,b in zip(clocks[0],clocks[-1])))
            counts=[self.scoped_work(row) for row in rows]
            need(all(all(value[key]==counts[0][key] for key in ('signalInvocations','timerInvocations','timerRegistrations')) for value in counts))
        if state['stage'] in ('cancel-observed','quiet-issued','cancel-quiet','job-retire-issued','partial-ready')+CAPTURE_STAGES:
            need(state['plan'] is not None and starts and state['replies'] and self.cancel_value(state)['source']['phase']=='complete')
            job=self.cancel_value(state)['source']
            need(not job['before']['script']['history']['events'] and state['plan']['checkedEpochMs']<=job['startedEpochMs'])
        if state['stage'] in ('cancel-quiet','job-retire-issued','partial-ready')+CAPTURE_STAGES:need(state['quiet'])
        if state['stage'] in ('partial-ready',)+CAPTURE_STAGES:need(self.cancel_value(state)['source']['retired'])
        if state['vm'] is not None:
            exact(state['vm'],{'roots','execution'});root=state['vm']['roots']
            roots_packet(root,dict(schemaVersion=1,commandId=root['commandId'],action='feature-script-roots-observe'),self.native.pid,root['capturedEpochMs'])
            history=self.frame(state['frames'][-1])[1]['history']
            need(history['events'])
            join_compilation(history,state['vm']['execution'],root_url(root['source']['defaultScriptsUrl'])+'system/snapshot.js',self.reviewed)
        if state['stage'] in ('cancel-observed','quiet-issued','cancel-quiet','job-retire-issued','partial-ready')+CAPTURE_STAGES:need(state['vm'] is not None)
        if self.encoding_version==2:
            if state['migration'] is not None:
                exact(state['migration'],{'fromVersion','originalSha256'})
                need(type(state['migration']['fromVersion']) is int and state['migration']['fromVersion']==1
                    and native_source.sha(state['migration']['originalSha256']))
            if state['platform'] is not None:
                observed=state['platform'];exact(observed,{'where','original'})
                need(observed['where'] in ('baseline','before-still'))
                value=observed['original'];exact(value,{'requestedEpochMs','capturedEpochMs','source'})
                need(integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
                    and value['capturedEpochMs']-value['requestedEpochMs']<=1500 and type(value['source']) is dict
                    and type(value['source'].get('sdk')) is int and typed_equal(value['source'],platform_profile(str(value['source']['sdk']))))
            else:need(state['stage']=='arm-issued' or state['migration'] is not None and state['stage'] in ('partial-ready','capture-prepare-issued'))
            if state['stillPlan'] is not None:
                plan=state['stillPlan'];need(type(plan) is dict and native_source.nonce(plan.get('id')) and plan.get('runId')==self.run
                    and plan.get('prefix')==self.still_prefix and plan.get('sealed') is False)
                need(any(typed_equal(plan,value) for value in self.frame(state['frames'][-1])[2]['source']['plans']))
            if state['capture'] is not None:self.capture_proof(state,host_only=host_only)
            if state['stage'] in ('captured','still-quiet-issued','still-ready'):need(state['capture'] is not None)
            need(type(state['captureQuiet']) is list and len(state['captureQuiet'])<=1)
            for window in state['captureQuiet']:
                exact(window,{'first','last'});need(integer(window['first'],0,len(state['frames'])-1)
                    and integer(window['last'],window['first']+1,len(state['frames'])-1))
                rows=state['frames'][window['first']:window['last']+1];clocks=[self.clocks(row) for row in rows]
                for row in rows:self.still_idle(row,state)
                need(all(all(0<=b-a<=500 for a,b in zip(old,new)) for old,new in zip(clocks,clocks[1:]))
                    and all(b-a>=3000 for a,b in zip(clocks[0],clocks[-1])))
                counts=[self.scoped_work(row) for row in rows]
                need(all(all(value[key]==counts[0][key] for key in ('signalInvocations','timerInvocations','timerRegistrations')) for value in counts))
            if state['stage']=='still-ready':need(state['captureQuiet'])

    @staticmethod
    def cancel_value(state):return decode(state['replies'][-1]['raw'])['packet']

    def load(self):
        self.lock.assert_held();self.now();disk=self.store.read()
        if self.disk is not None:need(typed_equal(disk,self.disk))
        if disk is None:
            need(self.state is None and self.originals.disk is None);self.originals.verify();return
        exact(disk,{'snapshotCancelOwnerVersion','runId','binding','fixtureUrl','payload'})
        need(type(disk['snapshotCancelOwnerVersion']) is int and disk['snapshotCancelOwnerVersion'] in READS
            and disk['runId']==self.run and typed_equal(disk['binding'],self.binding) and disk['fixtureUrl']==self.source.fixture_url)
        self.encoding_version=disk['snapshotCancelOwnerVersion']
        rows=unpack(disk['payload']);need(len(rows)==1)
        state=self.originals.decode(rows[0]) if self.encoding_version==2 else rows[0]
        self.validate(state)
        if state['frames']:
            native,script,_packet=self.frame(state['frames'][-1])
            if self.native.previous is None:self.native.restore(native)
            if self.script.previous is None:self.script.restore(script)
        if state['vm'] is not None and self.roots.last is None:self.roots.restore(state['vm']['roots'])
        if self.work.last is None:self.work.restore([row['work'] for row in state['frames'] if row['work'] is not None])
        if state.get('platform') is not None:self.platform.original=deepcopy(state['platform']['original']['source'])
        if state['replies'] and self.cancel.last is None:
            saved=state['replies'][-1];self.cancel.restore(decode(saved['raw'])['packet'],saved['request'],anchor=saved['anchor'])
        self.disk,self.state=deepcopy(disk),deepcopy(state)

    def save(self,state,*,host_only=False):
        self.lock.assert_held();need(typed_equal(self.store.read(),self.disk));self.validate(state,host_only=host_only)
        encoded=self.originals.encode(state,host_only=host_only) if self.encoding_version==2 else state
        disk=dict(snapshotCancelOwnerVersion=self.encoding_version,runId=self.run,binding=self.binding,fixtureUrl=self.source.fixture_url,payload=pack([encoded]))
        self.store.write(disk,self.disk);need(typed_equal(self.store.read(),disk));self.disk,self.state=deepcopy(disk),deepcopy(state)

    def read_frame(self,operation='read'):
        self.lock.assert_held();started=self.now();requested=self.native.clock_ms()
        self.native.capture(self.run,operation);self.script.capture(self.run);ui=self.snapshot.ui.snapshot()
        events=self.script.previous['history']['events'];work=None
        if events:work=self.work.read(events[-1]['caller']['manager']['instance'],0 if self.work.last is None else self.work.last['sequence'])
        inventory=self.files.inventory() if self.files.store.read() is not None else None
        if inventory is None:
            value=self.files.source.request(self.run);inventory=dict(files=[],rows=[],capturedEpochMs=value['capturedEpochMs'])
            need(not value['source']['rows'] and not value['source']['captures'])
        row=dict(native=self.native.original(),script=self.script.original(),ui=deepcopy(ui),files=self.files.source.original(),
            inventory=deepcopy(inventory),work=deepcopy(work),hostMonotonic=self.now());self.frame(row)
        self.anchor=(started,requested,min(self.clocks(row)[1:]));return row

    def append_frame(self,operation='read'):
        row=self.read_frame(operation);state=deepcopy(self.state);state['frames'].append(row)
        if state['vm'] is not None and decode(row['script']['raw'])['history']['sequence']>decode(self.state['frames'][-1]['script']['raw'])['history']['sequence']:
            self.observe_vm(state)
        self.save(state);return row

    def observe_vm(self,state):
        root=self.roots.read(0 if self.roots.last is None else self.roots.last['sequence'])
        execution=self.execution.read(self.execution.sequence,require_code_identity=True,require_membership=True)
        if state['vm'] is not None:
            previous=state['vm']['execution']
            need(execution['instance']==previous['instance'] and execution['sequence']>previous['sequence']
                and execution['capturedEpochMs']>=previous['capturedEpochMs'])
        state['vm']=dict(roots=deepcopy(root),execution=deepcopy(execution))

    def fence(self):
        need(self.anchor is not None);started,requested,captured=self.anchor
        need(self.native.guard() is not False);native_epoch=self.native.clock_ms()
        phase_started=self.now();phase_epoch=self.source.epoch_ms();value=self.source.status(self.state['source'])
        need(value['active'] and all(typed_equal(value[key],self.state['source'][key]) for key in ('instance','createdEpochMs','activations')))
        final_native=self.native.clock_ms();final_epoch=self.source.epoch_ms();completed=self.now()
        need(number(final_native,native_epoch,1e15) and number(final_epoch,phase_epoch,1e15))
        age=max(final_native-captured,requested-captured+(completed-started)*1000,
            final_epoch-value['capturedEpochMs'],phase_epoch-value['capturedEpochMs']+(completed-phase_started)*1000)
        need(-250<=final_native-captured and -250<=final_epoch-value['capturedEpochMs'] and age<=1500)
        return completed,age

    def fixture(self,verb,inputs):
        value=self.phase(self.source.status(None if self.state is None else self.state['source']))
        need(value['activations'][-1]['stimulus']==dict(verb=verb,inputs=inputs));return value

    def issued(self,stage,source=None):
        state=deepcopy(self.state);state['stage']=stage
        if source is not None:state['source']=deepcopy(source)
        self.save(state)

    def allowed(self,command,stage):
        extra={'text'} if command.get('action')=='replace' else set()
        exact(command,{'schemaVersion','commandId','bridgeId','generation','sequence','observedElapsedMs','controlId','controlToken','action'}|extra)
        control=command['controlId']
        need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and identifier(command['commandId'])
            and command['bridgeId']==self.binding['sessionId'] and all(identifier(command[key]) for key in ('generation','controlToken'))
            and integer(command['sequence'],1) and integer(command['observedElapsedMs']))
        if stage=='open-issued':need(command['action']=='activate' and (control in ('snapshot.entry','tablet.home','snapshot.mode','snapshot.format')
            or control.startswith(('tablet.page.','snapshot.mode.','snapshot.format.'))))
        elif stage=='cancel-issued':
            need(stage=='cancel-issued' and (control in ('snapshot.name','snapshot.mode','snapshot.format') or control.startswith(('snapshot.mode.','snapshot.format.'))))
            need(command['action']=='activate' or control=='snapshot.name' and command['action']=='replace' and command['text']==self.prefix)
        else:
            need(stage=='capture-issued' and (control in ('snapshot.name','snapshot.capture','snapshot.mode','snapshot.format')
                or control.startswith(('snapshot.mode.','snapshot.format.'))))
            need(command['action']=='activate' or control=='snapshot.name' and command['action']=='replace' and command['text']==self.still_prefix)

    def delivery(self,kind,command,*,host_only=False):
        state=deepcopy(self.state);state['deliveries'].append(dict(kind=kind,command=deepcopy(command),stage=state['stage'],frame=len(state['frames'])-1));self.save(state,host_only=host_only)

    def bind_save_owner(self,owner):
        from adapters.pico4.snapshot_save_owner import PicoSnapshotSaveOwner
        need(isinstance(owner,PicoSnapshotSaveOwner) and owner.parent is self and owner.lock is self.lock
            and (self.save_owner is None or self.save_owner is owner))
        self.save_owner=owner

    def before_qml(self,command):
        self.lock.assert_held()
        if self.state['stage']=='still-ready' and self.save_owner is not None:
            self.save_owner.before_qml(command);return
        need(self.current);self.allowed(command,self.state['stage']);self.append_frame()
        if command['controlId']=='snapshot.capture':self.capture_admission(self.state['frames'][-1],self.state)
        self.delivery('qml',command);self.fence()

    def before_file(self,command):
        if command['action']=='pico-snapshot-files-observe':return
        self.lock.assert_held();need(self.current and command['operation']=='plan' and command['runId']==self.run
            and ((self.state['stage']=='cancel-issued' and command['prefix']==self.prefix)
                or (self.state['stage']=='capture-prepare-issued' and command['prefix']==self.still_prefix)))
        # Child control CAS has already committed. This parent CAS follows it;
        # the last exact fixture read is after both journals and all guards.
        self.delivery('files',command);self.fence()

    def before_cancel(self,command):
        self.lock.assert_held();need(self.current and any(typed_equal(command,row) for row in self.state['requests']))
        need(self.state['stage'] in ('cancel-issued','cancel-observed','quiet-issued','cancel-quiet','job-retire-issued'))
        self.append_frame();self.delivery('cancel',command);self.fence()

    def before_controller(self,operation):
        self.lock.assert_held();need(self.current and self.state['stage']=='open-issued' and operation=='tablet.open')
        self.append_frame();self.controller_anchor=self.fence();self.controller_envelope=None

    def controller_intent(self,envelope):
        self.lock.assert_held();need(self.controller_anchor is not None and self.controller_envelope is None)
        self.delivery('controller',envelope,host_only=True);self.controller_envelope=deepcopy(envelope);self.before_publish(envelope)

    def before_publish(self,envelope):
        need(typed_equal(self.controller_envelope,envelope) and self.controller_anchor is not None)
        started,age=self.controller_anchor;now=self.native.monotonic();need(number(now,started,1e15) and age+(now-started)*1000<=1500)

    def prepare(self):
        with self.lock.held():
            self.load();need(self.state is None and self.snapshot.state is None and self.snapshot.ui.state is None and self.files.store.read() is None)
            source=self.fixture('baseline',{})
            self.save(dict(stage='arm-issued',source=source,baseline=deepcopy(source),sessionOrigin=deepcopy(self.session_origin),frames=[],deliveries=[],plan=None,
                job=uuid.uuid4().hex,requests=[],replies=[],vm=None,quiet=[],migration=None,platform=None,stillPlan=None,capture=None,captureQuiet=[]))
            row=self.append_frame('arm');native,script,_packet=self.frame(row)
            need(not native['requests'] and not script['history']['events'] and not row['ui']['open'])
            state=deepcopy(self.state);state['platform']=dict(where='baseline',original=self.platform.read());self.save(state)
            self.issued('prepared');result=self.report();self.fence();return result

    def open(self):
        with self.lock.held():
            self.load();need(self.state['stage']=='prepared');self.issued('open-issued',self.fixture('open',{}));self.current=True
            try:self.snapshot.open()
            finally:self.current=False
            self.append_frame();need(self.snapshot.state['originalMode'] in MODES and self.snapshot.state['originalFormat'] in FORMATS)
            self.issued('opened');result=self.report();self.fence();return result

    def send_cancel(self,operation,request=None):
        envelope=self.cancel.envelope(self.run,self.state['job'],operation,request)
        state=deepcopy(self.state);state['requests'].append(deepcopy(envelope));self.save(state)
        self.current=True
        try:value=self.cancel.request(envelope)
        finally:self.current=False
        saved=self.cancel.original();saved['request']=deepcopy(envelope)
        state=deepcopy(self.state);state['replies'].append(saved);self.save(state);return value

    def start(self):
        with self.lock.held():
            self.load();need(self.state['stage']=='opened');self.issued('cancel-issued',self.fixture('capture-cancel',dict(mode='animated',format='png')))
            self.append_frame();self.fence();self.current=True
            try:
                plan=self.files.plan(self.run,self.prefix)
                self.snapshot.click('snapshot.name');self.snapshot.ui.input('snapshot.name','replace',self.prefix)
                self.snapshot.choose('snapshot.mode',MODES,'animated');self.snapshot.choose('snapshot.format',FORMATS,'png')
            finally:self.current=False
            self.append_frame();state=deepcopy(self.state);state['plan']=plan;self.save(state);self.fence()
            ui=self.snapshot.ui.snapshot();control=self.snapshot.ui.control(ui,'snapshot.capture')
            need(ui['ready'] and control is not None)
            command=dict(schemaVersion=1,commandId=str(uuid.uuid4()),action='activate',controlId='snapshot.capture',
                controlToken=control['token'],bridgeId=ui['bridgeId'],generation=ui['generation'],sequence=ui['lastCommandSequence']+1,observedElapsedMs=ui['elapsedMs'])
            self.send_cancel('start',command);return self.reconcile()

    def reconcile(self):
        """Only new original queries; an uncertain start is never repeated."""
        with self.lock.held():
            self.load();need(self.state is not None)
            if self.state['stage'] in ('arm-issued','open-issued'):
                row=self.append_frame();native,script,_packet=self.frame(row)
                if self.state['stage']=='arm-issued':
                    need(not native['requests'] and not script['history']['events'] and not row['ui']['open'])
                    if self.encoding_version==2 and self.state['platform'] is None:
                        state=deepcopy(self.state);state['platform']=dict(where='baseline',original=self.platform.read());self.save(state)
                    self.issued('prepared')
                else:
                    preferences=self.snapshot._read()
                    if preferences is not None and preferences['originalMode'] in MODES and preferences['originalFormat'] in FORMATS:
                        need(row['ui']['open'] and self.snapshot.ui.control(row['ui'],'snapshot.capture') is not None);self.issued('opened')
                result=self.report();self.fence();return result
            if self.state['stage'] in CAPTURE_STAGES:return self.reconcile_still()
            need(self.state['stage'] in ('cancel-issued','cancel-observed','quiet-issued','cancel-quiet','job-retire-issued','partial-ready'))
            starts=[row for row in self.state['requests'] if row['operation']=='start'];need(len(starts)==1)
            if self.state['stage']!='partial-ready':self.send_cancel('observe')
            self.append_frame();value=self.cancel_value(self.state)
            if value['source']['phase']=='complete':
                state=deepcopy(self.state);self.observe_vm(state)
                if state['stage']=='cancel-issued':state['stage']='cancel-observed'
                if state['stage']=='job-retire-issued' and value['source']['retired']:state['stage']='partial-ready'
                self.save(state)
            result=self.report();self.fence();return result

    @staticmethod
    def clocks(row):
        return (row['hostMonotonic']*1000,decode(row['native']['raw'])['capturedEpochMs'],decode(row['script']['raw'])['capturedEpochMs'],
            row['ui']['updatedEpochMs'],decode(row['files']['raw'])['capturedEpochMs'])+(() if row['work'] is None else
            (row['work']['capturedEpochMs'],row['work']['source']['work']['capturedEpochMs']))

    @staticmethod
    def scoped_work(row):
        caller=decode(row['script']['raw'])['history']['events'][-1]['caller']
        selected=work_scope(row['work'],caller['compilation'])
        need(all(selected[key]>=caller['snapshotWork'][key] for key in ('signalInvocations','timerInvocations','timerRegistrations')))
        return selected

    def no_output(self,row,state):
        native,script,packet=self.frame(row);baseline=self.frame(state['frames'][0])[0]
        need(typed_equal(native['requests'],baseline['requests']) and not script['activeUploads']
            and not row['inventory']['files'] and not row['inventory']['rows'] and not packet['source']['rows'] and not packet['source']['captures'])
        resources=native['resources'];need(resources['activeRequests']==resources['projectionImagesBytes']==0
            and not any(resources[key] for key in ('taking360','waitingOnSnapshot','projectionTimerActive')))
        value=self.cancel_value(state)['source'];need(value['phase']=='complete' and not value['timerActive'] and idle(value['current']))
        need(typed_equal(script['history'],value['cancelled']['script']['history']))
        work=self.scoped_work(row)
        need(not work['evaluating'] and not work['timers'] and not work['unknownTimers']
            and all(work[key]==0 for key in ('signalCallbacks','timerCallbacks','unknownSignalCallbacks','unknownTimerCallbacks')))

    def quiet(self):
        with self.lock.held():
            self.load();need(self.state['stage'] in ('cancel-observed','quiet-issued'));self.issued('quiet-issued');first=previous=counts=None
            for _ in range(65):
                self.send_cancel('observe');row=self.append_frame();self.no_output(row,self.state);clocks=self.clocks(row)
                if first is None or previous is not None and any(b-a>500 for a,b in zip(previous,clocks)):first=(len(self.state['frames'])-1,clocks)
                previous=clocks;self.fence()
                current=self.scoped_work(row)
                if counts is None:counts=current
                else:need(all(current[key]==counts[key] for key in ('signalInvocations','timerInvocations','timerRegistrations')))
                if all(b-a>=3000 for a,b in zip(first[1],clocks)):
                    state=deepcopy(self.state);state['quiet']=[dict(first=first[0],last=len(state['frames'])-1)];state['stage']='cancel-quiet';self.save(state)
                    result=self.report();self.fence();return result
                self.native.sleep(.25)
            need(False)

    def retire_job(self):
        with self.lock.held():
            self.load();need(self.state['stage']=='cancel-quiet');self.issued('job-retire-issued')
            self.send_cancel('retire');return self.reconcile()

    def upgrade(self):
        """Explicit private schema CAS; no historical backend fact is invented."""
        self.lock.assert_held();need(self.state['stage']=='partial-ready')
        if self.encoding_version==2:return
        need(self.encoding_version==1)
        from adapters.script_journey.history import canonical
        state=deepcopy(self.state);state.update(platform=None,stillPlan=None,capture=None,captureQuiet=[],
            migration=dict(fromVersion=1,originalSha256=hashlib.sha256(canonical(self.disk)).hexdigest()))
        self.encoding_version=2;self.save(state)

    def capture_admission(self,row,state):
        need(self.encoding_version==2 and state['stillPlan'] is not None)
        native,script,files=self.frame(row)
        need(not native['requests'] and len(script['history']['events'])==2
            and [event['kind'] for event in script['history']['events']]==['pending','cancelled']
            and not files['source']['rows'] and not files['source']['captures'] and not row['inventory']['files']
            and any(typed_equal(plan,state['stillPlan']) for plan in files['source']['plans']))
        review=row['ui'].get('picoSnapshotReview');need(type(review) is dict and review['snapshotReviewObservationVersion']==2 and review['present'])
        value=review['review'];need(value['visible'] and value['mode']==0 and value['format']=='png'
            and value['captureName']==self.still_prefix and value['captureSettingsLoaded']
            and not any(value[key] for key in ('capturing','processing','exportBusy','exportTicket','uploadPath')))

    def capture_still(self):
        with self.lock.held():
            self.load();need(self.state['stage']=='partial-ready');self.upgrade()
            self.issued('capture-prepare-issued',self.fixture('capture',dict(mode='still',format='png')))
            self.append_frame();self.fence();self.current=True
            try:plan=self.files.plan(self.run,self.still_prefix)
            finally:self.current=False
            self.append_frame();state=deepcopy(self.state);state['stillPlan']=plan
            # Reobserve the actual unchanged SDK branch at its current clock.
            # A v1 migration is marked before-still, never as a baseline read.
            value=self.platform.read()
            if state['platform'] is None:state['platform']=dict(where='before-still',original=value)
            self.save(state);self.issued('capture-issued');self.fence()
            need(self.snapshot.original_files(self.still_prefix)==dict(files=[]))
            self.current=True
            try:self.snapshot.take(dict(name=self.still_prefix,mode='still',format='png'))
            finally:self.current=False
            return self.reconcile_still()

    def capture_proof(self,state,*,host_only=False):
        record=state['capture'];exact(record,{'requestBirth','requestId','event','file','artifactRecord','decoded','frame','source'})
        self.phase(record['source']);need(record['source']['activations'][-1]['stimulus']==dict(verb='capture',inputs=dict(mode='still',format='png'))
            and all(record['source'][key]==state['baseline'][key] for key in ('instance','createdEpochMs'))
            and state['source']['activations'][:len(record['source']['activations'])]==record['source']['activations'])
        need(integer(record['frame'],0,len(state['frames'])-1))
        row=state['frames'][record['frame']];native,script,packet=self.frame(row)
        need(len(native['requests'])==1);request=native['requests'][0]
        need(request['birth']==record['requestBirth'] and request['requestId']==record['requestId']
            and request['events'] and typed_equal(request['events'][-1],record['event']) and record['event']['phase']=='complete')
        events=script['history']['events'];need(len(events)==4 and [event['kind'] for event in events]==['pending','cancelled','pending','complete']
            and events[-2]['mode']==events[-1]['mode']=='still' and events[-1]['id']==events[-2]['id']==record['requestId'])
        delivered=[value for value in state['deliveries'] if value['kind']=='qml' and value['command']['controlId']=='snapshot.capture'];need(len(delivered)==1)
        before=state['frames'][delivered[0]['frame']];self.capture_admission(before,state)
        need(request['registeredEpochMs']>=max(state['stillPlan']['checkedEpochMs'],self.frame(before)[0]['capturedEpochMs'],
            before['ui']['updatedEpochMs'],record['source']['activations'][-1]['activatedEpochMs'])
            and events[-2]['capturedEpochMs']>=record['source']['activations'][-1]['activatedEpochMs'])
        file=record['file'];exact(file,{'path','captureId','bytes','sha256','device','inode','artifact','capturedEpochMs','nativeClosedEpochMs','fileId','source'})
        matches=[value for value in packet['source']['rows'] if value['id']==file['fileId']];need(len(matches)==1);original_file=matches[0]
        need(original_file['planId']==state['stillPlan']['id'] and original_file['runId']==self.run and original_file['captureId']==record['requestId']
            and original_file['opened'] and original_file['closed'] and not original_file['retireId'] and not original_file['nativeRemoved']
            and all(typed_equal(original_file[key],file[key]) for key in ('path','bytes','sha256','device','inode'))
            and file['nativeClosedEpochMs']==original_file['closedEpochMs']<=record['event']['publishedEpochMs']
            and file['captureId']==record['requestId'] and file['source']=='snapshot-capture-original'
            and integer(file['capturedEpochMs'],file['nativeClosedEpochMs'],packet['capturedEpochMs'])
            and Path(file['path']).name==self.still_prefix+'-'+record['requestId']+'.png'
            and record['event']['canonicalPathSha256']==hashlib.sha256((self.run+'\0'+file['path']).encode()).hexdigest()
            and record['event']['basenameSha256']==hashlib.sha256((self.run+'\0'+Path(file['path']).name).encode()).hexdigest())
        artifact=record['artifactRecord'];exact(artifact,{'name','bytes','sha256','phase','file','removeIntent'})
        exact(artifact['file'],{'device','inode'});need(integer(artifact['file']['device']) and integer(artifact['file']['inode'],1))
        need(artifact['name']==file['artifact']=='snapshot-owned-'+self.run+'-'+file['fileId']+'.bin'
            and artifact['phase']=='saved' and artifact['removeIntent'] is False
            and all(typed_equal(artifact[key],file[key]) for key in ('bytes','sha256')))
        key=(file['fileId'],artifact['file']['device'],artifact['file']['inode'],file['bytes'],file['sha256'])
        if not host_only:
            raw=self.files.host_read(artifact)
            if key not in self.decoded_cache:self.decoded_cache[key]=inspect_snapshot(raw,mode='still',file_format='png')
        need(key in self.decoded_cache and typed_equal(record['decoded'],self.decoded_cache[key]))

    def reconcile_still(self):
        """New sources only; no Capture, preference or controller resend."""
        with self.lock.held():
            self.load();need(self.encoding_version==2 and self.state['stage'] in CAPTURE_STAGES)
            row=self.append_frame();native,script,packet=self.frame(row)
            if self.state['stage']=='capture-issued' and len(native['requests'])==1:
                request=native['requests'][0];events=script['history']['events'];review=row['ui'].get('picoSnapshotReview')
                need(type(review) is dict and review['snapshotReviewObservationVersion']==2)
                if (request['events'] and request['events'][-1]['phase']=='complete' and len(events)==4 and review['present']
                        and review['review']['visible'] and row['ui']['open'] and row['ui']['ready']):
                    paths=[value['path'] for value in packet['source']['rows'] if value['captureId']==request['requestId'] and value['planId']==self.state['stillPlan']['id']]
                    need(len(paths)==1 and any(image['path']==paths[0] for image in review['review']['images']))
                    file=self.files.acquire(paths[0],request['requestId'])
                    with self.files.held():artifact=deepcopy(self.files.state['artifacts'][file['fileId']]);raw=self.files.host_read(artifact)
                    self.append_frame();state=deepcopy(self.state);state['capture']=dict(requestBirth=request['birth'],requestId=request['requestId'],
                        event=deepcopy(request['events'][-1]),file=deepcopy(file),artifactRecord=artifact,decoded=inspect_snapshot(raw,mode='still',file_format='png'),
                        frame=len(state['frames'])-1,source=deepcopy(state['source']))
                    state['stage']='captured';self.save(state)
            result=self.report();self.fence();return result

    def still_idle(self,row,state):
        native,script,packet=self.frame(row);record=state['capture'];need(record is not None)
        need(len(native['requests'])==1 and native['requests'][0]['alive'] is False
            and typed_equal(native['requests'],self.frame(state['frames'][record['frame']])[0]['requests'])
            and typed_equal(script['history'],self.frame(state['frames'][record['frame']])[1]['history']) and script['activeUploads']==0)
        resources=native['resources'];need(resources['activeRequests']==resources['projectionImagesBytes']==0
            and not any(resources[key] for key in ('taking360','waitingOnSnapshot','projectionTimerActive')))
        need(len(row['inventory']['files'])==len(row['inventory']['rows'])==len(packet['source']['rows'])==1)
        file=record['file'];need(all(row['inventory']['files'][0][key]==file[key] for key in ('bytes','sha256','device','inode')))
        review=row['ui'].get('picoSnapshotReview');need(type(review) is dict and review['present'] and review['review']['visible']
            and any(image['path']==file['path'] for image in review['review']['images'])
            and not any(review['review'][key] for key in ('capturing','processing','exportBusy','exportTicket','uploadPath')))
        work=self.scoped_work(row);need(not work['evaluating'] and not work['timers'] and not work['unknownTimers']
            and all(work[key]==0 for key in ('signalCallbacks','timerCallbacks','unknownSignalCallbacks','unknownTimerCallbacks')))

    def quiet_still(self):
        with self.lock.held():
            self.load();need(self.state['stage'] in ('captured','still-quiet-issued'));self.issued('still-quiet-issued');first=previous=counts=None
            for _ in range(65):
                row=self.append_frame();self.still_idle(row,self.state);clocks=self.clocks(row);work=self.scoped_work(row)
                if first is None or previous is not None and any(b-a>500 for a,b in zip(previous,clocks)):first=(len(self.state['frames'])-1,clocks)
                previous=clocks
                if counts is None:counts=work
                else:need(all(work[key]==counts[key] for key in ('signalInvocations','timerInvocations','timerRegistrations')))
                self.fence()
                if all(b-a>=3000 for a,b in zip(first[1],clocks)):
                    state=deepcopy(self.state);state['captureQuiet']=[dict(first=first[0],last=len(state['frames'])-1)];state['stage']='still-ready';self.save(state)
                    result=self.report();self.fence();return result
                self.native.sleep(.25)
            need(False)

    def report(self):
        return dict(qualification='PICO_NORMAL_CAPTURE_CANCEL_COMPONENT_ONLY' if self.state['stage'] in CANCEL_STAGES else 'PICO_NORMAL_SNAPSHOT_PRE_EXPORT_COMPONENT_ONLY',stage=self.state['stage'],fullSnapshotRecipe=False,
            deviceAcceptance=False,journalRetained=True,filePlan=None if self.state['plan'] is None else self.state['plan']['id'],
            ordinaryCaptureResendAllowed=False,saveBackend=None if self.state.get('platform') is None else self.state['platform']['original']['source']['saveBackend'],
            png=None if self.state.get('capture') is None else deepcopy(self.state['capture']['decoded']))
