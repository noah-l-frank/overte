"""Normal still-PNG composition with original callbacks/files; partial v16 only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import re
import stat
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.android_snapshot_files import original_stat,ORIGINAL_VERSION
from adapters.pico4.snapshot import PicoSnapshot,MODES,FORMATS
from adapters.pico4.navigation import NativeNavigationIO,validate_snapshot,identifier
from adapters.pico4 import snapshot_originals as originals
from adapters.script_journey.history import pack,unpack
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from openxr_input.adapter_session import PicoOpenXrAdapterSession,STATE_SCHEMA_VERSION
from openxr_input.controller_protocol import validate_envelope
from snapshot_observation import inspect_snapshot,MAX_BYTES

VERSION=1
STAGES=('arm-issued','prepared','open-issued','opened','capture-issued','captured','quiet-issued','native-quiet','close-issued','closed','closed-quiet-issued','partial-closed')


def signature(info):
    need(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode)==0o600 and info.st_uid==os.getuid() and info.st_nlink==1)
    return [info.st_dev,info.st_ino,info.st_size,info.st_mode,info.st_uid,info.st_nlink,info.st_mtime_ns,info.st_ctime_ns]


def artifact(root,record):
    exact(record,{'basename','artifact','bytes','sha256','originalStat','pathSha256','hostFile','decoded'})
    need(type(record['artifact']) is str and re.fullmatch(r'snapshot-[0-9a-f]{24}-[0-9a-f]{64}\.png',record['artifact'])
        and integer(record['bytes'],1,MAX_BYTES) and originals.sha(record['sha256']) and type(record['hostFile']) is list
        and original_stat(record['originalStat'],record['bytes']) and originals.sha(record['pathSha256']))
    path=root/record['artifact'];descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(descriptor,'rb') as stream:
        before=signature(os.fstat(stream.fileno()));need(before==record['hostFile']==signature(path.lstat()))
        raw=stream.read(MAX_BYTES+1)
        need(signature(os.fstat(stream.fileno()))==before==signature(path.lstat()) and len(raw)==record['bytes']
            and hashlib.sha256(raw).hexdigest()==record['sha256'])
    return raw


class PicoSnapshotStillOwner:
    def __init__(self,path,run,binding,snapshot,native,session,source):
        need(originals.nonce(run) and isinstance(snapshot,PicoSnapshot) and isinstance(native,originals.PicoSnapshotOriginals)
            and isinstance(snapshot.ui.io,NativeNavigationIO) and isinstance(session,PicoOpenXrAdapterSession)
            and isinstance(source,PhaseFixtureReader) and source.run==run and source.area=='snapshots')
        self.store,self.run,self.binding=PrivateFeatureState(path),run,deepcopy(context(binding))
        self.snapshot,self.native,self.session,self.source=snapshot,native,session,source;self.lock=native.lock
        need(session.bound_process_identity()==binding['processIdentity'])
        with session._lock():self.session_origin=deepcopy(session._load())
        self.session_nonce=self.session_origin['sessionNonce']
        need(self.store.path==self.lock.path.with_name('snapshot-still-owner.json') and native.pid==int(binding['processIdentity'].split(':')[0])
            and snapshot.ui.context['processIdentity']==binding['processIdentity']
            and all(snapshot.ui.context[key]==binding[key] for key in ('sourceRevision','artifactSha256')))
        self.disk=self.state=self.anchor=self.controller_anchor=self.controller_envelope=None;self.current=False;self.last_clock=None;self.decoded_cache={}
        self.prefix='parity-'+run[:16]+'-still-png'
        # Store these bound method objects once: the original transport owns an
        # immutable exact callable, not a fresh equal-looking method per bind.
        self.qml_callback=self.before_send;self.controller_callback=self.before_controller
        self.intent_callback=self.controller_intent;self.publish_callback=self.before_publish
        snapshot.ui.io.bind_before_send(self.qml_callback)
        snapshot.ui.io.bind_controller_admission(self.controller_callback,intent=self.intent_callback,before_publish=self.publish_callback)
        with self.lock.held():self.load()
    def now(self):
        now=self.native.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock));self.last_clock=now;return now
    def packet(self,row):
        exact(row,{'native','ui','hostMonotonic'})
        exact(row['native'],{'raw','sha256'});raw=row['native']['raw']
        need(type(raw) is str and len(raw.encode())<=originals.LIMIT and hashlib.sha256(raw.encode()).hexdigest()==row['native']['sha256'])
        value=decode(raw);originals.validate(value,self.run,value['commandId'],self.native.pid,value['capturedEpochMs'])
        validate_snapshot(row['ui'],self.native.pid,row['ui']['updatedEpochMs'])
        need(number(row['hostMonotonic'],0,1e15) and row['ui']['bridgeId']==self.binding['sessionId']
            and abs(row['ui']['updatedEpochMs']-value['capturedEpochMs'])<=1500)
        return value
    def phase(self,value):
        phase_packet(value,run=self.run,area='snapshots',request=value['requestId'],epoch=value['capturedEpochMs'])
        need(value['active'] and value['activations'])
    def validate(self,state,*,host_only=False):
        exact(state,{'stage','source','baseline','sessionOrigin','frames','deliveries','preferences','capture','quiet','restoration'})
        origin=state['sessionOrigin'];exact(origin,{'schemaVersion','processIdentity','sessionNonce','nextSequence'})
        need(type(origin['schemaVersion']) is int and origin['schemaVersion']==STATE_SCHEMA_VERSION
            and origin['processIdentity']==self.binding['processIdentity'] and origin['sessionNonce']==self.session_nonce
            and integer(origin['nextSequence'],1,0xffffffff))
        need(state['stage'] in STAGES and type(state['frames']) is list and len(state['frames'])<=96
            and type(state['deliveries']) is list and len(state['deliveries'])<=80 and type(state['quiet']) is list and len(state['quiet'])<=2)
        self.phase(state['source']);self.phase(state['baseline'])
        stage=state['stage'];verb='baseline' if stage in ('arm-issued','prepared') else 'open' if stage in ('open-issued','opened') else 'close' if stage in ('close-issued','closed','closed-quiet-issued','partial-closed') else 'capture'
        need(state['source']['activations'][-1]['stimulus']==dict(verb=verb,inputs=dict(mode='still',format='png') if verb=='capture' else {}))
        need(state['baseline']['activations'][-1]['stimulus']==dict(verb='baseline',inputs={})
            and all(state['source'][key]==state['baseline'][key] for key in ('instance','createdEpochMs'))
            and state['source']['activations'][:len(state['baseline']['activations'])]==state['baseline']['activations'])
        previous=None;host=0
        for row in state['frames']:
            value=self.packet(row);previous=originals.accept(previous,value)
            need(row['hostMonotonic']>=host);host=row['hostMonotonic']
            need(row['ui']['generation']==state['frames'][0]['ui']['generation'])
            need(len(value['requests'])<=1) # Foreign concurrent capture is unavailable.
        ids=set();sequence=state['frames'][0]['ui']['lastCommandSequence'] if state['frames'] else 0;controller=None
        for delivery in state['deliveries']:
            exact(delivery,{'kind','command','frame','stage','source'});self.phase(delivery['source'])
            need(delivery['stage'] in ('open-issued','capture-issued','close-issued') and delivery['kind'] in ('qml','controller')
                and integer(delivery['frame'],0,len(state['frames'])-1))
            verb={'open-issued':'open','capture-issued':'capture','close-issued':'close'}[delivery['stage']]
            need(delivery['source']['activations'][-1]['stimulus']==dict(verb=verb,inputs=dict(mode='still',format='png') if verb=='capture' else {})
                and all(delivery['source'][key]==state['baseline'][key] for key in ('instance','createdEpochMs'))
                and state['source']['activations'][:len(delivery['source']['activations'])]==delivery['source']['activations'])
            command=delivery['command'];need(type(command) is dict)
            if delivery['kind']=='qml':
                exact(command,{'schemaVersion','commandId','bridgeId','generation','sequence','observedElapsedMs','controlId','controlToken','action'}
                    | ({'text'} if command.get('action')=='replace' else set()))
                observed=state['frames'][delivery['frame']]['ui'];control=self.snapshot.ui.control(observed,command.get('controlId'))
                need(command.get('commandId') not in ids and identifier(command.get('commandId'))
                    and type(command.get('sequence')) is int and command['sequence']==sequence+1 and command.get('bridgeId')==self.binding['sessionId']
                    and command.get('generation')==observed['generation'] and command['sequence']==observed['lastCommandSequence']+1
                    and control is not None and command['controlToken']==control['token']
                    and type(command['schemaVersion']) is int and command['schemaVersion']==1
                    and integer(command['observedElapsedMs']) and 0<=observed['elapsedMs']-command['observedElapsedMs']<=1500)
                ids.add(command['commandId']);sequence=command['sequence'];self.allowed(command,delivery['stage'])
            else:
                validate_envelope(command,self.session.profile);need(type(command['schemaVersion']) is int and command['schemaVersion']==1
                    and command['sessionNonce']==self.session_nonce
                    and len(command['commands'])==1 and command['commands'][0]['operation'] in ('tablet.open','tablet.close')
                    and command['commands'][0]['arguments']==dict(holdMilliseconds=1000)
                    and command['commands'][0]['id']==command['commands'][0]['operation'].replace('.','-')+'-'+str(command['sequence']))
                need(command['sequence']==(origin['nextSequence'] if controller is None else controller['sequence']+1))
                controller=command
        preference=state['preferences']
        if preference is not None:
            self.snapshot._validate(preference);need(preference['originalMode'] in MODES and preference['originalFormat'] in FORMATS)
            need(preference['prefix'] is None and preference['nonce'] is None and not preference['capturePending'] and not preference['preflightEmpty'])
            for key in ('mode','format'):
                control='snapshot.'+key+'.'+preference['original'+key.title()]
                observed=[state['frames'][delivery['frame']]['ui'] for delivery in state['deliveries']
                    if delivery['stage']=='open-issued' and delivery['kind']=='qml' and delivery['command']['controlId']==control]
                need(len(observed)==1 and self.snapshot.ui.control(observed[0],control)['checked'] is True)
        if STAGES.index(state['stage'])>=STAGES.index('opened'):need(preference is not None)
        if state['capture'] is not None:self.proof(state['capture'],state,host_only=host_only)
        if STAGES.index(state['stage'])>=STAGES.index('captured'):need(state['capture'] is not None)
        for quiet in state['quiet']:
            exact(quiet,{'where','first','last'});need(quiet['where'] in ('open','closed')
                and integer(quiet['first'],0,len(state['frames'])-1) and integer(quiet['last'],quiet['first']+1,len(state['frames'])-1))
            rows=state['frames'][quiet['first']:quiet['last']+1];clocks=[]
            for row in rows:
                self.native_quiet(row);need(row['ui']['open']==(quiet['where']=='open'))
                clocks.append((row['hostMonotonic']*1000,self.packet(row)['capturedEpochMs'],row['ui']['updatedEpochMs']))
            need(all(all(0<=b-a<=500 for a,b in zip(old,new)) for old,new in zip(clocks,clocks[1:]))
                and all(b-a>=3000 for a,b in zip(clocks[0],clocks[-1])))
        if state['stage'] in ('native-quiet','close-issued','closed','closed-quiet-issued','partial-closed'):
            need(state['quiet'] and state['quiet'][0]['where']=='open')
        restoration=state['restoration']
        if restoration is not None:
            exact(restoration,{'mode','format'})
            for key,control in (('mode','snapshot.mode.'+preference['originalMode']),('format','snapshot.format.'+preference['originalFormat'])):
                need(integer(restoration[key],0,len(state['deliveries'])-1));delivery=state['deliveries'][restoration[key]]
                need(delivery['stage']=='close-issued' and delivery['kind']=='qml' and delivery['command']['controlId']==control)
                observed=state['frames'][delivery['frame']]['ui'];choice=self.snapshot.ui.control(observed,control)
                need(choice is not None and choice['checked'] is True)
        if state['stage'] in ('closed','closed-quiet-issued','partial-closed'):
            need(restoration is not None and not state['frames'][-1]['ui']['open'])
        if state['stage']=='partial-closed':need(len(state['quiet'])==2 and state['quiet'][-1]['where']=='closed')
    def proof(self,record,state,*,host_only=False):
        exact(record,{'requestBirth','requestId','event','file'})
        rows=[self.packet(frame)['requests'] for frame in state['frames']];need(rows and rows[-1])
        row=rows[-1][0];need(row['birth']==record['requestBirth'] and row['requestId']==record['requestId']
            and row['events'] and row['events'][-1]==record['event'] and record['event']['phase']=='complete')
        issued=[delivery for delivery in state['deliveries'] if delivery['kind']=='qml' and delivery['stage']=='capture-issued'
            and delivery['command']['controlId']=='snapshot.capture']
        need(len(issued)==1);delivery=issued[0];frame=state['frames'][delivery['frame']]
        need(not self.packet(frame)['requests'] and row['registeredEpochMs']>=max(self.packet(frame)['capturedEpochMs'],
            frame['ui']['updatedEpochMs'],delivery['source']['activations'][-1]['activatedEpochMs']))
        basename=self.prefix+'-'+row['requestId']+'.png';file=record['file']
        need(file['basename']==basename and record['event']['pathSha256']==file['pathSha256']
            and record['event']['basenameSha256']==hashlib.sha256((self.run+'\0'+basename).encode()).hexdigest())
        # A cold owner independently decodes once. Warm validation still reads
        # the original FD/path signature and bytes, then compares the immutable
        # decoded DTO; it cannot adopt a caller's altered decoded facts.
        key=tuple(file['hostFile'])+(file['sha256'],)
        if not host_only:
            raw=artifact(self.snapshot.files.artifacts,file)
            if key not in self.decoded_cache:self.decoded_cache[key]=inspect_snapshot(raw,mode='still',file_format='png')
        need(key in self.decoded_cache)
        need(file['decoded']==self.decoded_cache[key])
    def load(self):
        self.lock.assert_held();self.now();disk=self.store.read()
        if self.disk is not None:need(self.disk==disk)
        if disk is None:need(self.state is None);return
        exact(disk,{'snapshotStillOwnerVersion','runId','binding','fixtureUrl','payload'})
        need(type(disk['snapshotStillOwnerVersion']) is int and disk['snapshotStillOwnerVersion']==VERSION and disk['runId']==self.run
            and disk['binding']==self.binding and disk['fixtureUrl']==self.source.fixture_url)
        rows=unpack(disk['payload']);need(len(rows)==1);self.validate(rows[0]);state=rows[0]
        if state['frames']:
            last=self.packet(state['frames'][-1])
            if self.native.previous is None:self.native.restore(last)
            elif self.native.previous!=last:originals.accept(last,self.native.previous)
        self.disk,self.state=deepcopy(disk),deepcopy(state)
    def save(self,state,*,host_only=False):
        self.lock.assert_held();need(self.store.read()==self.disk);self.validate(state,host_only=host_only)
        value=dict(snapshotStillOwnerVersion=VERSION,runId=self.run,binding=self.binding,fixtureUrl=self.source.fixture_url,payload=pack([state]))
        self.store.write(value,self.disk);need(self.store.read()==value);self.disk,self.state=deepcopy(value),deepcopy(state)
    def capture_frame(self,operation='read'):
        self.lock.assert_held();started=self.now();requested=self.native.clock_ms()
        native=self.native.capture(self.run,operation);ui=self.snapshot.ui.snapshot()
        row=dict(native=self.native.original(),ui=deepcopy(ui),hostMonotonic=self.now());need(self.packet(row)==native)
        self.anchor=(started,requested,min(native['capturedEpochMs'],ui['updatedEpochMs']))
        state=deepcopy(self.state);state['frames'].append(row);self.save(state);return row
    def fence(self,source):
        need(self.anchor is not None);started,requested,captured=self.anchor
        # All SDK/native guards precede the last independent exact phase read.
        need(self.native.guard() is not False);native_epoch=self.native.clock_ms()
        phase_started=self.now();phase_epoch=self.source.epoch_ms();value=self.source.status(source)
        need(value['active'] and all(value[key]==source[key] for key in ('instance','createdEpochMs','activations')))
        final_native=self.native.clock_ms();need(number(final_native,native_epoch,1e15));native_epoch=final_native
        final_epoch=self.source.epoch_ms();completed=self.now()
        need(number(native_epoch,captured-250,1e15) and max(native_epoch-captured,requested-captured+(completed-started)*1000)<=1500
            and number(final_epoch,phase_epoch,1e15) and -250<=final_epoch-value['capturedEpochMs']
            and max(final_epoch-value['capturedEpochMs'],phase_epoch-value['capturedEpochMs']+(completed-phase_started)*1000)<=1500)
        age=max(native_epoch-captured,requested-captured+(completed-started)*1000,final_epoch-value['capturedEpochMs'],
            phase_epoch-value['capturedEpochMs']+(completed-phase_started)*1000)
        return (completed,age)
    def fixture(self,verb,inputs):
        value=self.source.status(None if self.state is None else self.state['source']);self.phase(value)
        need(value['activations'][-1]['stimulus']==dict(verb=verb,inputs=inputs));return value
    def issued(self,stage,source):
        state=deepcopy(self.state);state.update(stage=stage,source=deepcopy(source));self.save(state)
    def allowed(self,command,stage):
        control=command['controlId'];action=command.get('action')
        if stage=='open-issued':need(control=='snapshot.entry' or control=='tablet.home' or re.fullmatch(r'tablet\.page\.([1-9]|[12][0-9]|3[0-2])',control)
            or control in ('snapshot.mode','snapshot.format') or control in ('snapshot.mode.'+mode for mode in MODES) or control in ('snapshot.format.'+fmt for fmt in FORMATS))
        elif stage=='capture-issued':need(control in ('snapshot.name','snapshot.capture','snapshot.mode','snapshot.format','tablet.home')
            or control.startswith(('snapshot.mode.','snapshot.format.','tablet.page.')) or control=='snapshot.entry')
        else:need(stage=='close-issued' and (control in ('snapshot.mode','snapshot.format','snapshot.entry','tablet.home')
            or control.startswith(('snapshot.mode.','snapshot.format.','tablet.page.'))))
        need(action=='activate' or stage=='capture-issued' and control=='snapshot.name' and action=='replace' and command.get('text')==self.prefix)
    def delivery(self,kind,command,*,host_only=False):
        need(self.current and self.state['stage'] in ('open-issued','capture-issued','close-issued'))
        state=deepcopy(self.state);state['deliveries'].append(dict(kind=kind,command=deepcopy(command),frame=len(state['frames'])-1,
            stage=state['stage'],source=deepcopy(state['source'])));self.save(state,host_only=host_only)
    def before_send(self,command):
        self.lock.assert_held();need(self.current);self.allowed(command,self.state['stage']);self.capture_frame()
        self.delivery('qml',command);self.fence(self.state['source'])
    def before_controller(self,operation):
        self.lock.assert_held();need(self.current and operation in ('tablet.open','tablet.close'))
        need(operation=='tablet.open' or self.state['stage']=='close-issued' and self.state['restoration'] is not None)
        self.capture_frame();self.controller_anchor=self.fence(self.state['source']);self.controller_envelope=None
    def controller_intent(self,envelope):
        # This original Session callback is deliberately host-only: no phase,
        # SDK/native query, source guard or session re-entry while it is locked.
        self.lock.assert_held();need(self.controller_anchor is not None and self.controller_envelope is None)
        self.delivery('controller',envelope,host_only=True);self.controller_envelope=deepcopy(envelope);self.before_publish(envelope)
    def before_publish(self,envelope):
        need(self.controller_envelope==envelope and self.controller_anchor is not None)
        start,age=self.controller_anchor;now=self.native.monotonic()
        need(number(now,start,1e15) and age+(now-start)*1000<=1500)
    def prepare(self):
        with self.lock.held():
            self.load();need(self.state is None and self.snapshot.state is None and self.snapshot.ui.state is None)
            source=self.fixture('baseline',{});state=dict(stage='arm-issued',source=source,baseline=deepcopy(source),sessionOrigin=deepcopy(self.session_origin),frames=[],deliveries=[],
                preferences=None,capture=None,quiet=[],restoration=None);self.save(state)
            self.capture_frame('arm');need(not self.packet(self.state['frames'][-1])['requests'] and not self.state['frames'][-1]['ui']['open'])
            self.issued('prepared',source);result=self.report();self.fence(source);return result
    def open(self):
        with self.lock.held():
            self.load();need(self.state['stage']=='prepared');source=self.fixture('open',{});self.issued('open-issued',source)
            self.current=True
            try:self.snapshot.open()
            finally:self.current=False
            return self.reconcile()
    def take(self):
        with self.lock.held():
            self.load();need(self.state['stage']=='opened');source=self.fixture('capture',dict(mode='still',format='png'))
            self.issued('capture-issued',source);self.capture_frame();need(not self.packet(self.state['frames'][-1])['requests'])
            self.fence(source);need(self.snapshot.original_files(self.prefix)==dict(files=[]))
            self.current=True
            try:self.snapshot.take(dict(name=self.prefix,mode='still',format='png'))
            finally:self.current=False
            return self.reconcile()
    def reconcile(self):
        with self.lock.held():
            self.load();need(self.state is not None);row=self.capture_frame();native=self.packet(row);state=deepcopy(self.state)
            if state['stage']=='arm-issued':
                need(not native['requests'] and not row['ui']['open']);state['stage']='prepared'
            elif state['stage']=='open-issued':
                preference=self.snapshot._read()
                if preference is not None and all(preference[key] is not None for key in ('originalMode','originalFormat')):
                    need(self.snapshot.ui.control(row['ui'],'snapshot.capture') is not None);state.update(stage='opened',preferences=deepcopy(preference))
            elif state['stage']=='capture-issued' and native['requests']:
                request=native['requests'][0];need(request['registeredEpochMs']>=state['source']['activations'][-1]['activatedEpochMs'])
                if request['events'] and request['events'][-1]['phase']=='complete':
                    result=self.snapshot.files.files(self.prefix,run=self.run);files=self.file_source()
                    need(len(result['files'])==len(files['files'])==1);file=deepcopy(files['files'][0]);path=self.snapshot.files.artifacts/file['artifact']
                    file.update(hostFile=signature(path.lstat()),decoded={})
                    raw=artifact(self.snapshot.files.artifacts,file);file['decoded']=inspect_snapshot(raw,mode='still',file_format='png')
                    state['capture']=dict(requestBirth=request['birth'],requestId=request['requestId'],event=deepcopy(request['events'][-1]),file=file)
                    state['stage']='captured'
            elif state['stage']=='close-issued' and state['restoration'] is not None and not row['ui']['open']:state['stage']='closed'
            self.save(state);result=self.report();self.fence(state['source']);return result
    def native_quiet(self,row):
        value=self.packet(row);resource=value['resources'];need(len(value['requests'])==1 and not value['requests'][0]['alive']
            and resource['activeRequests']==resource['projectionImagesBytes']==0
            and not any(resource[key] for key in ('taking360','waitingOnSnapshot','projectionTimerActive')))
    def file_source(self):
        value=self.snapshot.files.last_original
        exact(value,{'snapshotFileOriginalVersion','prefix','context','files'})
        need(type(value['snapshotFileOriginalVersion']) is int and value['snapshotFileOriginalVersion']==ORIGINAL_VERSION==2
            and value['prefix']==self.prefix and value['context']=={key:self.binding[key] for key in ('sourceRevision','artifactSha256','processIdentity')})
        return value
    def quiet(self):
        with self.lock.held():
            self.load();where='closed' if self.state['stage'] in ('closed','closed-quiet-issued') else 'open'
            need(self.state['stage'] in (('closed','closed-quiet-issued') if where=='closed' else ('captured','quiet-issued')))
            self.issued('closed-quiet-issued' if where=='closed' else 'quiet-issued',self.state['source']);first=None;previous=None
            for _ in range(33):
                row=self.capture_frame();self.native_quiet(row);need(row['ui']['open']==(where=='open'))
                result=self.snapshot.files.files(self.prefix,run=self.run);file=self.state['capture']['file']
                need(result['files']==[dict(basename=file['basename'],artifact=file['artifact'])]
                    and self.file_source()['files']==[{key:file[key] for key in ('basename','artifact','bytes','sha256','originalStat','pathSha256')}])
                clocks=(row['hostMonotonic']*1000,self.packet(row)['capturedEpochMs'],row['ui']['updatedEpochMs'])
                if first is None or previous is not None and any(b-a>500 for a,b in zip(previous,clocks)):first=(len(self.state['frames'])-1,clocks)
                previous=clocks;self.fence(self.state['source'])
                if all(b-a>=3000 for a,b in zip(first[1],clocks)):
                    state=deepcopy(self.state);state['quiet'].append(dict(where=where,first=first[0],last=len(state['frames'])-1))
                    state['stage']='partial-closed' if where=='closed' else 'native-quiet';self.save(state)
                    result=self.report();self.fence(state['source']);return result
                self.native.sleep(.25)
            need(False)
    def close(self):
        with self.lock.held():
            self.load();need(self.state['stage']=='native-quiet');source=self.fixture('close',{});self.issued('close-issued',source)
            self.current=True
            try:
                self.snapshot.show();preference=self.state['preferences']
                self.snapshot.choose('snapshot.mode',MODES,preference['originalMode'])
                self.snapshot.choose('snapshot.format',FORMATS,preference['originalFormat'])
                state=deepcopy(self.state);state['restoration']={key:max(index for index,row in enumerate(state['deliveries'])
                    if row['stage']=='close-issued' and row['kind']=='qml' and row['command']['controlId']=='snapshot.'+key+'.'+preference['original'+key.title()]) for key in ('mode','format')}
                self.save(state);self.fence(source)
                # Reuse the original normal controller-close/wait route and
                # preserve both owned child journals. Native quiet alone does
                # not retire Script/Qt/settings or actual output ownership.
                need(self.snapshot.ui.state is not None and self.snapshot.ui.state['tabletOwned'])
                if self.snapshot.ui.snapshot()['open']:self.snapshot.ui.controller('tablet.close')
                self.snapshot.ui.wait(lambda value:not value['open'])
            finally:self.current=False
            return self.reconcile()
    def report(self):
        return dict(qualification='PICO_NORMAL_STILL_PNG_COMPONENT_ONLY',stage=self.state['stage'],deviceAcceptance=False,
            nativeRequest=None if self.state['capture'] is None else self.state['capture']['requestId'],
            png=None if self.state['capture'] is None else deepcopy(self.state['capture']['file']['decoded']),
            fullSnapshotRecipe=False,journalRetained=True)
