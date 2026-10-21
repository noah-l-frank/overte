"""Unchanged shared Script journey over iOS W3C/HTTP/AFC input boundaries.

The native client and OS are synthetic SDK boundaries. The missing-script HTTP
response and fixture files are real local originals. This proves host adapter
logic only, never a compiled iOS client or device qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from functools import partial
import hashlib
import json
from pathlib import Path
import secrets
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ios.self_tests import test_ios_normal_scripts as input_fixture
from ios.adapters import script_runtime,script_observation,normal_input,feature_observation
from ios.adapters.script_feature import IOSScriptFeature,ScriptFixtureReader
from adapters.native_feature_observation import need
from adapters.native_script_files import originals
from adapters.normal_feature_state import PrivateFeatureState
from adapters.token_script_file_ui import file_url
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.engine import Journey
from self_tests.test_native_feature_observation import Boundary as Lifecycle
from self_tests.test_native_script_observation import Boundary as Execution,code_source,effect_source
from self_tests.test_native_script_files import Boundary as Storage
from self_tests.test_native_process_presence import Boundary as Presence
from self_tests.test_native_script_loads import history,event
from self_tests.test_native_script_membership import membership_source
from self_tests.test_script_ui_inventory import inventory,picker
from self_tests.test_script_manager_status import observed

RUN='a'*32


class IOSScriptJourneyTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.clock=0.;self.host=lambda:1700000000000+round(self.clock*1000)
        self.device_epoch=lambda:self.host()+86400000
        self.native=input_fixture.Native();self.native.epoch=self.device_epoch
        self.native.qt.sleep=self.sleep
        self.native.target['testBuild'].update(scenePath='/scene.json',launchEnvironment={})
        self.storage=Storage(self.root);self.native.file_source=self.storage
        self.native.file_ui=input_fixture.FileBoundary(self.storage.root);self.native.file_ui.sleep=self.sleep
        self.birth='b'*32;self.events=[];self.retired=[];self.engine=None;self.engine_number=0
        self.source=Execution();self.lifecycle=Lifecycle();self.presence=None
        self.status_text='';self.ui_sequence=0;self.phase='bound';self.ignored=False
        self.service_instance='f'*32
        fingerprint=lambda:hashlib.sha256(json.dumps(self.native.target,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.state=dict(sessionId='native-session',generation=1,targetFingerprint=fingerprint(),processIdentity='42')
        scope=lambda:dict(sourceRevision='a'*40,artifactSha256='e'*64,sessionId='native-session',generation=1,targetFingerprint=fingerprint())
        test=self
        class Gate:
            def verify(self):need(test.native.running);return dict(schemaVersion=1,sourceRevision='a'*40,artifactSha256='e'*64,installedCandidateVerified=True)
            def continuity(self):need(test.native.running);return test.native.process()
            def record(self):return dict(phase=test.phase)
            def retired_absence(self):need(not test.native.running)
            def finish_retirement(self):need(not test.native.running);test.phase='retired'
        def lifecycle(_selector,operation,_values):
            if operation=='app.stop':
                self.native.execute('native-session','mobile: terminateApp',dict(bundleId=self.native.target['appId']))
                self.phase='retired';self.state.pop('processIdentity',None)
                return {'stopped':True}
            need(operation=='app.launch')
            target=self.native.target;contract=target['testBuild'];origin=contract['fixtureOrigin']
            self.native.execute('native-session','mobile: launchApp',dict(bundleId=target['appId'],arguments=[
                '--url',origin+contract['scenePath'],'--testScript',origin+input_fixture.component.AppiumAdapter.IOS_PROBE_SCRIPT_PATH,
                '--testResultsLocation',contract['resultsDirectory']],environment={}))
            self.phase='bound';self.state['processIdentity']=str(self.native.pid)
            return {'launched':True}
        base=SimpleNamespace(_operation=None,_session_recreation_forbidden=False,
            _candidate_guard=lambda **_:None,_target=lambda _:self.native.target,
            _scope=lambda *_:scope(),_binding=lambda *_:Gate(),_binding_store=lambda _:SimpleNamespace(read=lambda:dict(phase=self.phase)),
            read_session=lambda _:deepcopy(self.state),state_path=lambda _:self.root/'session.json',
            invoke=lifecycle,reset_launch_state=lambda *_:None,
            _script_restart_session=lambda *_a,**_kw:(self.native,self.state,self.native.target))
        for name,file in (('script_store','normal-scripts.json'),('script_files_store','normal-script-files.json'),
                          ('script_restart_store','normal-script-restart.json'),('script_restart_inputs_store','normal-script-restart-inputs.json')):
            setattr(base,name,lambda _selector,name=file:PrivateFeatureState(self.root/name))
        self.runtime=script_runtime.IOSScriptRuntime(base)
        self.native.on_launch=self.restarted
        original_observed=self.native.observed
        def visual():
            value=original_observed();self.ui_sequence+=1
            opened=self.native.qt.opened and self.native.qt.page=='scripts'
            picker_open=opened and self.native.file_ui.opened
            value.update(scriptObservationVersion=1,scriptSourceSequence=self.ui_sequence,
                scriptInventory=inventory([observed(statusText=self.status_text,labelText=self.status_text,
                    labelVisible=bool(self.status_text))] if opened else [],[picker()] if picker_open else [],
                    tabletShown=self.native.qt.opened))
            return value
        self.native.observed=visual
        original_call=self.native.call
        def call(method,path,body=None):
            if method=='GET' and path=='/session/native-session':return {}
            result=original_call(method,path,body);self.synchronize();return result
        self.native.call=call
        original_post=self.native.post
        def metadata(value):
            value.update(processId=self.native.pid,instance=self.birth,requestedEpochMs=self.device_epoch(),capturedEpochMs=self.device_epoch())
        self.storage.mutate=metadata
        def execution(value):
            metadata(value);source=value['source'];source['engines']=[]
            if self.engine is not None:
                source['engines']=[deepcopy(self.engine)]
                relative=self.engine['url'].removeprefix(self.storage.root.as_uri()+'/')
                code_source(value,originals(RUN)[relative].decode(),submitted=self.engine['assignedAt'])
                source['engines'][0].pop('assignedAt')
                effect_source(value,ticks=2+round(self.clock*10),edited=self.device_epoch()*1000)
                row=source['effects']['entities'][0];row.update(id=self.entity_id(),name='e2e-'+RUN+'-script',
                    userData=json.dumps(dict(runId=RUN,ticks=2+round(self.clock*10))))
            else:source.update(sourceIdentityVersion=1,effectSourceVersion=1,
                effects=dict(complete=True,scanRadiusMeters=64,scannedEntities=0,entities=[],absentIds=[]))
            source['effects']['absentIds']=deepcopy(self.retired)
            history(value,self.events);source['loads']['instance']=self.birth
            membership_source(value,revision=1+self.engine_number*2+len(self.retired))
            for row in source['membership']['managers']:
                row['assignedEpochMs']=self.engine['assignedAt']
                row['loadGeneration']=next(e['loadGeneration'] for e in self.events if e['managerInstance']==row['instance'])
        self.source.mutate=execution
        def native_clock(value):
            metadata(value);value['animationFence']['requestedEpochMs']=self.device_epoch();value['lifecycle']=dict(self.native.lifecycle)
        self.lifecycle.mutate=native_clock
        def post(request,timeout):
            command=json.loads(request.data)
            producer={'feature-native-observe':self.lifecycle,'feature-script-observe':self.source}.get(command['action'])
            if command['action']=='feature-process-presence':
                if self.presence is None or self.presence.pid!=self.native.pid:
                    self.presence=Presence(pid=self.native.pid,epoch_ms=self.device_epoch);self.presence.presence='absent'
                    self.presence.edit=lambda value:value.update(instance=self.birth)
                producer=self.presence
            if producer is not None:
                producer.send(command);self.native.echo=json.dumps(command).encode();return self.native
            result=original_post(request,timeout)
            if command['action']=='normal-ui-input' and command['operation']=='edit':
                self.native.receipt['status']['processId']=self.native.pid
            if command['action']=='normal-feature-observe':
                self.native.diagnostic['instance']=self.service_instance
                for row in self.native.diagnostic['scripts']:row['path']=file_url(row['url'])
            return result
        original_execute=self.native.execute
        def execute(session,operation,values):
            if operation=='mobile: pullFile':
                producer={'feature-native-observation.json':self.lifecycle,'feature-script-observation.json':self.source,
                    'feature-process-presence.json':self.presence}.get(values['remotePath'].rsplit('/',1)[-1])
                if producer is not None:return base64.b64encode(producer.original().encode()).decode()
            return original_execute(session,operation,values)
        self.native.execute=execute
        original_file=self.native.file_ui.activate
        def choose(identifier,**options):
            if identifier=='scripts.from-file':
                # NativeFileBrowser destroys its completed root; each normal
                # opening constructs a fresh selection model. Keep SDK history.
                self.native.file_ui.chosen=[];self.native.file_ui.review=None
                self.native.file_ui.current=self.storage.root.parent
            original_file(identifier,**options)
            if identifier=='script-file.confirm' and self.native.file_ui.accepted:
                source=self.native.file_ui.accepted[-1]
                self.native.qt.rows.append(dict(url=source,path=file_url(source)))
        self.native.file_ui.activate=choose
        original_activate=self.native.qt.activate
        def activate(identifier,**options):
            original_activate(identifier,**options)
            if identifier=='scripts.url.submit' and self.native.qt.text.endswith('/missing.js'):
                url=self.native.qt.text
                try:
                    with urlopen(url,timeout=2) as response:response.read()
                except HTTPError as error:
                    need(error.code==404);error.read();error.close()
                    self.events.append(event(sequence=len(self.events)+1,url=url,callbackEpochMs=self.device_epoch()))
                    self.status_text='Failed to load '+url+': server returned 404'
            self.synchronize()
        self.native.qt.activate=activate
        patches=[patch.object(script_runtime.backend,'WebDriver',return_value=self.native),
            patch.object(normal_input,'urlopen',side_effect=post),patch.object(feature_observation,'post_request',side_effect=post),
            patch.object(script_runtime,'NativeClockAcquisition',partial(script_runtime.NativeClockAcquisition,epoch_ms=self.host,monotonic=lambda:self.clock)),
            patch.object(script_runtime,'IOSScriptObservation',partial(script_observation.IOSScriptObservation,epoch_ms=self.host,monotonic=lambda:self.clock))]
        for name in ('NativeUI','TokenScriptUI','NormalScriptManager','TokenScriptFilePicker','ScriptRestartHandoff','RestartInputs'):
            patches.append(patch.object(script_runtime,name,partial(getattr(script_runtime,name),monotonic=lambda:self.clock,sleep=self.sleep) if name not in ('RestartInputs',) else partial(script_runtime.RestartInputs,monotonic=lambda:self.clock)))
        for boundary in patches:boundary.start();self.addCleanup(boundary.stop)
        self.server=make_server(secrets.token_hex(32),secrets.token_hex(32));self.server.script_resources.clock_ms=self.host;self.server.journal.clock=self.host
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.stop_server)
        url='http://127.0.0.1:'+str(self.server.server_port)+'/feature-fixture/v1'
        self.client=Client(url,self.server.reader_token)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.run,self.fixture=self.client.register('scripts')
        self.primary=IOSScriptFeature(self.runtime,'owned',ScriptFixtureReader(self.client,RUN,epoch_ms=self.host),monotonic=lambda:self.clock,sleep=self.sleep)
        self.actor=IOSScriptFeature(self.runtime,'owned',ScriptFixtureReader(Client(url,self.server.actor_token),RUN,epoch_ms=self.host),role='actor',monotonic=lambda:self.clock,sleep=self.sleep)

    def entity_id(self):return '11111111-1111-4111-8111-'+str(self.engine_number).zfill(12)

    def synchronize(self):
        rows=self.native.qt.rows
        current=rows[-1]['url'] if rows else None
        if self.engine is not None and current!=self.engine['url']:
            self.retired.append(self.entity_id());self.engine=None
        if current is not None and self.engine is None:
            self.engine_number+=1
            instance=format(self.engine_number,'032x')
            self.engine=deepcopy(self.source.engine);self.engine.update(url=current,assignedAt=self.device_epoch())
            self.engine['required'].update(instance=instance)
            self.engine['required']['modules'][0].update(url=current.rsplit('/',1)[0]+'/companion.js',capturedEpochMs=self.device_epoch())
            self.events.append(event(sequence=len(self.events)+1,url=current,success=True,status='Success',
                managerInstance=instance,loadGeneration=self.engine_number,callbackEpochMs=self.device_epoch()))
        if not self.native.qt.opened:self.status_text=''

    def restarted(self):
        if self.engine is not None:self.retired.append(self.entity_id())
        self.engine=None;self.birth='c'*32;self.events=[];self.retired=[];self.service_instance='e'*32
        self.native.pid=43;self.native.instance='22222222-2222-4222-8222-222222222222'
        self.native.qt.opened=False;self.native.qt.page='home';self.native.qt.rows=[];self.native.qt.dialog=False
        self.native.file_ui.opened=False;self.status_text=''

    def sleep(self,seconds):
        self.clock+=seconds;self.native.qt.clock=self.clock;self.native.file_ui.clock=self.clock

    def stop_server(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive());self.assertEqual(0,self.server.internal_errors)

    def test_uncertain_picker_open_is_persisted_and_same_ticket_never_resends_input(self):
        from feature_journeys.scenarios import VERSION
        self.client.activate('1'*32)
        self.primary.prepare()
        self.client.activate('2'*32,'open',{})
        self.primary.act(dict(contractVersion=VERSION,runId=RUN,fixtureUrl=self.fixture,ticket='2'*32,verb='open',inputs={}))
        self.client.activate('3'*32,'picker-open',{})
        self.native.file_ui.fault='open'
        call=dict(contractVersion=VERSION,runId=RUN,fixtureUrl=self.fixture,ticket='3'*32,verb='picker-open',inputs={})
        with self.assertRaises(RuntimeError):self.primary.act(call)
        self.assertEqual('issued',self.primary._actions().load()['phase'])
        before=list(self.native.file_ui.actions)
        with self.assertRaises(RuntimeError):self.primary.act(call)
        self.assertEqual(before,self.native.file_ui.actions)
        self.assertEqual(1,before.count('scripts.from-file'))

    def test_full_shared_journey_preserves_original_ios_inputs_files_failure_restart_and_both_role_cleanup(self):
        reports=[]
        def invoke(operation,values):return getattr(self.primary,operation.rsplit('.',1)[1])(values)
        def witness():self.actor.publish();return self.client.observe()
        journey=Journey('scripts',RUN,self.fixture,invoke=invoke,witness=witness,activate=self.client.activate,
            read_artifact=lambda _:self.fail('Scripts has no image shortcut'),image_policy={},continuity=lambda *_:None,
            monotonic=lambda:self.clock,epoch_ms=self.host,sleep=self.sleep,report=reports.append)
        with patch('feature_journeys.script_fixture.time.time',side_effect=lambda:self.host()/1000):journey.execute()
        self.assertTrue(reports[-1]['sequenceCompleted']);self.assertTrue(reports[-1]['cleanupSucceeded'])
        self.assertEqual(['stop','launch'],self.native.lifecycle_inputs);self.assertFalse(self.storage.root.exists())
        self.assertEqual(1,len(self.server.script_resources.snapshot(RUN)['responses']))
        self.assertEqual({'performed':True},self.primary.finalize())
        self.assertTrue(all(store.read() is None for store in self.primary._retirement_paths()))


if __name__=='__main__':unittest.main()
