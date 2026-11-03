"""Canonical retained candidate plus explicit lower SDK/native/WDA producers.

The real runtime/source factories, InstalledCodeBinding, OS context, capture,
review, Page, input packets, files and locks execute. No native SDK is imported.
OS and QML state changes happen only in their modeled delivered input handlers.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import unpack
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.witness import Client
from ios.adapters import feature_observation,normal_input
from ios.adapters.appium_adapter import AppiumAdapter
from ios.adapters.snapshot_resume_runtime import IOSSnapshotResumeRuntime
from ios.self_tests.test_ios_script_runtime import IOSScriptRuntimeTests
from ios.self_tests.test_ios_snapshot_capture_rendered_review import ReviewDomain,RUN,TICKET

RESUME='e'*32


class ResumeOSDomain(ReviewDomain):
    def __init__(self,case):
        canonical=IOSScriptRuntimeTests();canonical.setUp();case.addCleanup(canonical.doCleanups)
        self.canonical,self.installed=canonical,canonical.f
        super().__init__(case)
        self.os_commands=[];self.native_pulls=[];self.os_fault=None;self.block_native=False;self.current_root=None
        self.lifecycle=dict(backgrounds=0,activations=1,launches=1)
        mutate=self.ctx.native.mutate
        def native_producer(value):mutate(value);value['lifecycle']=deepcopy(self.lifecycle)
        self.ctx.native.mutate=native_producer
        observed=self.f.input_native.observed
        def ui_producer():
            value=observed()
            if self.current_root is not None:
                for row in value['controls']:
                    if 'snapshotRootId' in row:row['snapshotRootId']=self.current_root
                for row in value['snapshotReviewInventory']['roots']:row['rootIdentity']=self.current_root
            return value
        self.f.input_native.observed=ui_producer
        # These are initial modeled producer settings, before the first
        # Snapshot owner/original. No saved original is edited or retimed.
        self.installed.native.mutate=lambda value:value.update(capturedEpochMs=self.f.now)
        self.ctx.root=self.installed.adapter.state_path('test-only').parent
        self.ctx.binding=dict(canonical.runtime._existing('test-only')[4],processIdentity='42')
        self.ctx.lock=ScriptSourceLock(self.ctx.root/'script-feature-sources.lock')
        client=canonical.client;previous_execute=client.execute
        def execute(session,operation,args):
            need(session=='test-only')
            if operation=='mobile: queryAppState':return 4 if self.installed.process['foreground'] else 3
            if operation in ('mobile: backgroundApp','mobile: activateApp'):
                state=PrivateFeatureState(self.ctx.root/'ios-snapshot-resume-os-owner.json').read()['state']
                case.assertEqual('background-issued' if operation.endswith('backgroundApp') else 'foreground-issued',state['phase'])
                self.os_commands.append(operation)
                if operation=='mobile: backgroundApp':
                    if self.os_fault!='ignored-home':self.installed.process['foreground']=False;self.lifecycle['backgrounds']+=1
                else:
                    if self.os_fault!='ignored-activation':self.installed.process['foreground']=True;self.lifecycle['activations']+=1
                    if self.os_fault=='relaunch':self.lifecycle['launches']+=1
                    if self.os_fault=='extra-transition':self.lifecycle['backgrounds']+=1;self.lifecycle['activations']+=1
                    if self.os_fault=='root-replaced':self.current_root='99999999-9999-4999-8999-999999999999'
                    if self.os_fault=='missing-native-transition':self.lifecycle=dict(backgrounds=0,activations=1,launches=1)
                self.f.now+=10
                if self.os_fault==('lost-home' if operation.endswith('backgroundApp') else 'lost-activation'):
                    raise OSError('Modeled delivered OS input with lost transport return')
                return True
            if operation=='mobile: pullFile':
                filename=args['remotePath'].rsplit('/',1)[-1]
                expected='@'+self.installed.target['appId']+':documents/'+self.installed.target['testBuild']['resultsDirectory']+'/'+filename
                case.assertEqual({'remotePath':expected},args)
                if filename!='ios-installed-bundle-observation.json':
                    case.assertTrue(self.installed.process['foreground'],'Native/UI AFC read while backgrounded')
                    case.assertFalse(self.block_native,'Historical completed resume repeated a native/UI query')
                    self.native_pulls.append(filename)
                if filename=='feature-native-observation.json':return base64.b64encode(self.ctx.native.original().encode()).decode()
                if filename=='ios-normal-ui-request-result.json':return base64.b64encode(json.dumps(self.f.input_native.receipt).encode()).decode()
                if filename in self.capture.raws:return base64.b64encode(self.capture.raws[filename].encode()).decode()
                if filename=='ios-snapshot-file-result.json':return base64.b64encode(json.dumps(self.ctx.files.value).encode()).decode()
            return previous_execute(session,operation,args)
        client.execute=execute
        def call(method,path,body=None):
            if method=='GET' and path=='/session/test-only':return {}
            return self.http(method,path,body)
        client.call=call
        expected_post=self.installed.target['testBuild']['fixtureOrigin']+'/e2e-client-command.json'
        normal_post=normal_input.urlopen
        def normal_request(request,timeout):
            case.assertEqual(expected_post,request.full_url);case.assertEqual(5,timeout)
            return normal_post(request,timeout)
        actual=patch.object(normal_input,'urlopen',normal_request);actual.start();case.addCleanup(actual.stop)
        def post(request,timeout):
            case.assertEqual(expected_post,request.full_url);case.assertEqual(5,timeout)
            query=json.loads(request.data);action=query['action']
            if action in ('feature-native-observe','ios-bundle-observe'):
                case.assertTrue(self.installed.process['foreground'],'Foreground native source while backgrounded')
                producer=self.ctx.native if action=='feature-native-observe' else self.installed.native
                producer.send(query);raw=json.dumps(query).encode()
                class Response:
                    status=200
                    def __enter__(self):return self
                    def __exit__(self,*_args):return False
                    def read(self,limit):return raw[:limit]
                return Response()
            return self.capture.post(request,timeout)
        actual=patch.object(feature_observation,'post_request',post);actual.start();case.addCleanup(actual.stop)
        self.installed.adapter.query_app_state=AppiumAdapter.query_app_state.__get__(self.installed.adapter,type(self.installed.adapter))
        self.runtime=IOSSnapshotResumeRuntime(self.installed.adapter)
        self.prepare()
        with self.review() as review:review.acquire(TICKET)
        self.original_phase=deepcopy(unpack(PrivateFeatureState(self.ctx.root/'ios-snapshot-primary-capture-owner.json').read()['payload'])[0]['phaseOriginal'])
        self.f.now+=10;self.activated=self.f.now

    def resume_client(self):
        domain=self
        class Phase(Client):
            def request(self,path,value=None,method=None,*,phase_nonce=None,**_kwargs):
                need(path=='/runs/'+RUN+'/phase');domain.capture.phase_sequence+=1;old=domain.original_phase
                activation=dict(sequence=len(old['activations'])+1,ticket=RESUME,activatedEpochMs=domain.activated,
                    stimulus=dict(verb='background-resume',inputs={}))
                return dict(fixturePhaseVersion=1,instance=old['instance'],sequence=domain.capture.phase_sequence,
                    requestId=phase_nonce,runId=RUN,area='snapshots',capturedEpochMs=domain.f.now,active=True,
                    createdEpochMs=old['createdEpochMs'],retiredEpochMs=None,activations=deepcopy(old['activations'])+[activation])
        return Phase('https://controlled.invalid/feature-fixture/v1','r'*64,monotonic=self.capture.mono,sleep=self.capture.sleep)

    def resumed(self):
        return self.runtime.resume_owner('test-only',RUN,self.resume_client(),epoch_ms=self.capture.epoch,
            monotonic=self.capture.mono,sleep=self.capture.sleep)
