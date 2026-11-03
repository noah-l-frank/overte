"""One canonical candidate and target model for normal input and Actor sources.

Candidate files, host session and source-lock inode are shared originals. The
worker independently opens them; only native/Qt/SDK effects remain models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack,contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'android/vr/pico/tests/device'))
import test_normal_scripts as canonical
from adapters.android import adapter as android
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4 import lifecycle_source as ui,lifecycle_gesture as gesture,lifecycle_drive as drive
from adapters.script_journey.history import unpack
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_lifecycle_ui import ID
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from self_tests import test_pico_lifecycle_editor as editor_models
from self_tests import test_pico_lifecycle_process as process_models
from self_tests.test_pending_commit_owner import Boundary as PendingBoundary
from self_tests.pico_lifecycle_actor_fixture import IndependentLifecycleSources,CanonicalIndependentLifecycleSources,LifecycleProducts
from self_tests.pico_lifecycle_actor_fixture import WORKER as ORIGINAL_WORKER
from self_tests.test_vr_graphics_subject import framework_source
from self_tests import test_pico_lifecycle_world as world_models


def original_channels(adapter,target,native,channel,clock):
    """Use the existing canonical private file/command transport over raw models."""
    from adapters.native_feature_observation import FILE as NATIVE_FILE
    from adapters.native_graphics_subject import FILE as SUBJECT_FILE
    from adapters.pending_commit_owner import FILE as PENDING_FILE
    names={'ui':ui.FILE,'gesture':gesture.FILE,'drive':drive.FILE,'pending':PENDING_FILE,'feature':NATIVE_FILE,'subject':SUBJECT_FILE}
    actions={gesture.ACTION:'gesture',drive.ACTION:'drive','feature-pending-commit-owner':'pending',
        'feature-native-observe':'feature','feature-graphics-subject-observe':'subject'}
    replies={};factory=adapter._native_feature_observer
    def source(actual_target):
        need(actual_target==target);result=factory(actual_target)
        def send(request):replies[names[actions[request['action']]]]=channel(actions[request['action']],request)
        result.send=send;result.clock_ms=clock.epoch;result.monotonic=clock.now;result.sleep=clock.sleep
        return result
    adapter._native_feature_observer=source
    read,write=adapter.adb.read_debug_app_file,adapter.adb.write_debug_app_file
    def original(target_,package,path,**kwargs):
        name=path.removeprefix('files/overte-e2e/')
        if name not in names.values():return read(target_,package,path,**kwargs)
        need(target_==target and package=='org.overte.pico');return replies.get(name,'')
    def command(target_,package,path,raw):
        if path!=ui.COMMAND:return write(target_,package,path,raw)
        need(target_==target and package=='org.overte.pico');replies[ui.FILE]=channel('ui',json.loads(raw))
    adapter.adb.read_debug_app_file=original;adapter.adb.write_debug_app_file=command


class CanonicalLifecycleTarget:
    def __init__(self,case):
        self.case=case;self.fixture=canonical.PicoNormalScriptsTests();self.fixture.setUp();case.addCleanup(self.fixture.doCleanups)
        temporary=self.fixture.fixture.fixture.fixture.temporary
        temporary._finalizer.detach();temporary.cleanup=lambda:None
        self.adapter,self.os=self.fixture.instance,self.fixture.native;self.target=self.os.target
        self.root=self.adapter._lifecycle_world_store(self.target).path.parent
        self.native=editor_models.Native();self.run=editor_models.RUN
        self.os.identity='123:400';self.os.require_process_identity=lambda value:need(value==self.os.identity)
        installed=self.adapter._installation(self.target)
        self.binding=dict(sourceRevision=installed['sourceRevision'],artifactSha256=installed['artifactSha256'],
            processIdentity=self.os.identity,sessionId=self.os.bridge_id,generation=0,
            targetFingerprint=hashlib.sha256((self.target+'\0'+str(self.adapter.pico_configuration)).encode()).hexdigest())
        self.model=editor_models.NativeCreate(self.root);self.model.tablet=False;self.model.page='home'
        self.controls=editor_models.Controls(self.model);self.field=editor_models.FieldBoundary()
        for controls in (self.controls,self.field):
            controls.instance=self.os.bridge_id;controls.generation=self.os.generation
        self.controls.pid=123;self.lock=ScriptSourceLock(self.root/'script-sources.lock')
        self.path=self.root/'lifecycle-editor-owner.json'
        # One existing native/physics model and one existing session transport.
        # Route normal tablet input through its original FakeTransport path;
        # world input uses the already tested World Transport implementation.
        self.transport=world_models.Transport(self.native,self.root/'lifecycle-world-owner.json')
        world_stage=self.transport.stage;status=self.transport.read_status
        def tablet(envelope,profile,*,before_publish=None):
            if envelope['commands'][0]['operation']=='input.move':
                return world_stage(envelope,profile,before_publish=before_publish)
            owner=unpack(json.loads(self.path.read_text())['payload'])[0]
            need(owner['tablet']['envelope']==envelope)
            result=editor_models.FakeTransport.stage(self.transport,envelope,profile,before_publish=before_publish)
            self.native.ui.shown=self.native.ui.home=self.model.tablet=self.os.opened=True
            return result
        self.transport.stage=tablet
        self.transport.read_status=lambda **kw:status(**kw)|dict(updatedEpochMs=self.native.epoch())
        self.session=PicoOpenXrAdapterSession(self.transport,self.target,self.root);self.session.begin(self.os.identity)
        self.adapter.pico_input_session=lambda target:self.session if target==self.target else need(False)
        self.adapter._scripts=lambda *_args:need(False)
        self.attach_controls()
        holder=SimpleNamespace(native=self.native,sleep=self.native.sleep)
        feature,_=process_models.LifecycleProcessTests.features(holder,self.native,123,'a'*32,1)
        pending=PendingBoundary();pending.epoch=self.native.epoch
        def pending_original():
            value=json.loads(pending.original());value['current']=dict(status='none');return json.dumps(value)
        product_case=SimpleNamespace(editor=self,observer=SimpleNamespace(run=self.run),native_producer=feature,
            boundary=pending,reader=SimpleNamespace(original=pending_original))
        self.products=LifecycleProducts(product_case);case.addCleanup(self.products.close)
        framework_source(self.products.subject)
        pose=self.products.subject.source['avatarPose']
        self.native.drive.source.update(feetPosition=deepcopy(pose['feetPosition']),bodyPosition=deepcopy(pose['feetPosition']),
            orientation=deepcopy(pose['orientation']),modelScale=pose['modelScale'])
        dispatch=self.products.dispatch
        def current(action,value):
            if action=='candidate':
                need(self.adapter.require_controlled_debug_identity(self.target)==self.binding['processIdentity']
                    and self.adapter.require_pico_session_identity(self.target)==self.binding['processIdentity'])
                installed=self.adapter._installation(self.target)
                need(all(installed[key]==self.binding[key] for key in ('sourceRevision','artifactSha256')))
            return dispatch(action,value)
        self.products.dispatch=current
        clock=SimpleNamespace(epoch=self.native.epoch,now=lambda:self.native.clock,sleep=self.native.sleep)
        original_channels(self.adapter,self.target,self.os,self.products.dispatch,clock)
        # Keep a test-only private diagnostic before the unchanged sanitizer.
        import traceback
        previous=sys.gettrace();recorded=[]
        def trace(frame,event,error):
            if event=='exception' and frame.f_code.co_name=='_lifecycle_editor' and not recorded:
                recorded.append(True);traceback.print_exception(*error,file=sys.stderr)
            return trace
        try:
            sys.settrace(trace)
            self.owner=self.adapter._lifecycle_editor(self.target,self.run,source_lock=self.lock)
        finally:sys.settrace(previous)
        self.owner.prepare()

    def attach_controls(self):
        for controls in (self.controls,self.field):
            capture=controls.capture
            def tokens(capture=capture):
                value=capture()
                for row in value['controls']:
                    row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,row['token']))
                    if row['id'].startswith('tablet.'):row.pop('inputReady',None)
                return value
            controls.capture=tokens
        original=self.os.snapshot;write=self.os.write_debug_app_file
        def snapshot():
            value=original();create=self.controls.capture();fields=self.field.capture()
            live=self.model.tablet and self.model.page=='create'
            value.update(open=self.model.tablet,ready=self.model.tablet,createControlsVersion=1,
                lifecycleControlsVersion=1,lastCommandSequence=self.os.sequence,
                elapsedMs=create['scope']['elapsedMs'],controls=deepcopy(create['controls']))
            if live:value['controls'].extend(deepcopy(fields['controls']))
            return value
        self.os.snapshot=snapshot
        def command(target,package,path,raw):
            if path!='files/overte-e2e/navigation-ui-command.json':return write(target,package,path,raw)
            need(target==self.target and package=='org.overte.pico');value=json.loads(raw)
            need(value['bridgeId']==self.os.bridge_id and value['generation']==self.os.generation
                and value['sequence']==self.os.sequence+1)
            disk=unpack(json.loads(self.path.read_text())['payload'])[0];intent=disk['inputs'][-1]
            need(intent['consumed'] is None and value['controlId']==intent['intent']['controlId'])
            self.os.inputs.append(deepcopy(value))
            if value['controlId']==ID:
                before=self.field.capture();self.field.input(value['controlId'],value['action'],value.get('text'),reference=before)
                self.controls.sequence=self.field.sequence
                self.native.ui.rows[0].update(focused=self.field.focused,text=self.field.text);self.native.ui.raised=self.field.focused
            else:
                self.controls.intents.append(deepcopy(intent['intent']))
                before=self.controls.capture();self.controls.input(value['controlId'],value['action'],before)
                self.field.sequence=self.controls.sequence
                if self.model.page=='create' and not self.native.ui.rows:
                    self.native.create();self.native.ui.rows[0]['focused']=False;self.native.ui.raised=False;self.native.ui.home=False
            self.os.sequence=self.controls.sequence
            self.os.status=dict(schemaVersion=1,bridgeId=self.os.bridge_id,commandId=value['commandId'],
                sequence=value['sequence'],performed=True,error='',processId=123,updatedEpochMs=self.os.epoch_milliseconds(target))
        self.os.write_debug_app_file=command

    def shared_candidate(self):
        names=('OVERTE_PICO_OPENXR_INPUT','OVERTE_PICO_NORMAL_NAVIGATION','OVERTE_PICO_NORMAL_SCRIPTS',
            'OVERTE_ANDROID_E2E_DEBUG','OVERTE_E2E_UPGRADE_SOURCE_ARTIFACT','ANDROID_ADB_SERVER_PORT',
            'OVERTE_PICO_OPENXR_STATE_DIR','OVERTE_E2E_SCENE_URL','OVERTE_ANDROID_E2E_PROBE_ATTEMPTS')
        return dict(prefix=deepcopy(self.fixture.fixture.prefix),environment={key:os.environ[key] for key in names if key in os.environ},
            target=self.target,stateDirectory=str(self.root),stateRoot=str(self.fixture.fixture.state_root))


class SharedCanonicalLifecycleSources(IndependentLifecycleSources):
    """Read the SAME sealed candidate and session originals in another process."""
    source=CanonicalIndependentLifecycleSources.source
    def __init__(self,config):
        super().__init__(config);self.context=ExitStack();shared=config['sharedCandidate']
        self.context.enter_context(patch.dict(os.environ,shared['environment']))
        self.os=canonical.existing.NavigationAdb(config['binding']['artifactSha256'],Path(shared['stateRoot']))
        self.os.identity=config['binding']['processIdentity'];self.os.bridge_id=config['binding']['sessionId']
        self.os.require_process_identity=lambda value:need(value==self.os.identity)
        self.target=shared['target'];self.root=Path(shared['stateDirectory'])
        session=PicoOpenXrAdapterSession(editor_models.FakeTransport(),self.target,self.root)
        self.context.enter_context(patch.object(android,'AdbTransport',return_value=self.os))
        self.context.enter_context(patch.object(android.AndroidAdapter,'pico_input_session',return_value=session))
        args,binding=android.cli([*shared['prefix'],'describe','--target',self.target])
        self.adapter=binding.create_adapter(args,android.AndroidAdapter)
        self.lock=ScriptSourceLock(self.root/'script-sources.lock');self.adapter._scripts=lambda *_args:need(False)
        if config.get('traceInitialLock'):
            held=self.lock.held;announced=[False]
            @contextmanager
            def traced():
                first=not announced[0];announced[0]=True
                if first:print(json.dumps(dict(event='lock-attempt')),flush=True)
                with held():
                    if first:print(json.dumps(dict(event='lock-acquired')),flush=True)
                    yield
            self.lock.held=traced
        original_channels(self.adapter,self.target,self.os,self.rpc.call,self.clock)
        native=self.adapter._native_feature_observer
        def guarded(target):
            value=native(target);guard=value.guard
            def current():guard();return self.guard()
            value.guard=current;return value
        self.adapter._native_feature_observer=guarded
        need(self.adapter._lifecycle_world_store(self.target).path.parent==self.root)
    def close(self):
        try:super().close()
        finally:self.context.close()


WORKER=ORIGINAL_WORKER.replace(
    "transport=(CanonicalIndependentLifecycleSources if config.get('canonicalFactory') else IndependentLifecycleSources)(config);source=None",
    "from self_tests.pico_lifecycle_canonical_actor_fixture import SharedCanonicalLifecycleSources\n"
    "transport=SharedCanonicalLifecycleSources(config);source=None")
WORKER=WORKER.replace("  print(json.dumps({'event':'published','sequence':value['actorSequence']}),flush=True)",
    "  import os\n"
    "  with source.lock.held():\n"
    "   locked=os.fstat(source.lock._owner[1])\n"
    "   audit={'path':str(source.lock.path),'device':locked.st_dev,'inode':locked.st_ino,'ownerPid':source.lock._owner[2]}\n"
    "  print(json.dumps({'event':'published','sequence':value['actorSequence'],'sourceLock':audit,'sourceStorage':source.storage.highwater}),flush=True)")
