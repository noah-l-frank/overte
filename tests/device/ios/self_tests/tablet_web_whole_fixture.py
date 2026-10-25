"""Actual Tablet readers/HTTP/AFC/private owners with explicit native models.

The host JS prerequisite runs unchanged. Native Qt/UIKit/WK producers are DTO
models, not executed native code. Native epochs and host boundary clocks are
explicitly distinct and progress only at actual modeled deliveries.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import patch
from adapters.native_script_observation import NativeScriptObservation
from adapters.script_feature.history import same
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client,Journal
from ios.adapters.feature_observation import FeatureObservation
from ios.adapters.graphics_history import restore_native
from ios.adapters.tablet_web_context import TabletWebContext
from ios.adapters.tablet_web_runtime import TabletRuntimeObserver,FACTORIES
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner,FRAME_KEYS
from ios.adapters.tablet_web_observer import TabletWebObserver,TabletWebDOMDisposition
from ios.self_tests import test_ios_tablet_web_context as context_tests
from ios.self_tests.tablet_web_history_fixture import frame
from ios.self_tests.test_ios_tablet_web_sources import RUN,ROOT,stamp
from ios.self_tests.test_ios_tablet_web_documents import ORIGINS
from ios.self_tests.test_ios_world_web_keys import QtKeys
from ios.self_tests.test_ios_pointer_state import NativePointerBoundary
from ios.self_tests.world_web_ui_roots_fixture import RootCensus
from self_tests import test_native_feature_observation as feature_tests


class TabletWholeBoundary:
    def __init__(self,test,*,fixture_url=ROOT,origins=ORIGINS):
        self.test=test;self.context_test=context_tests.TabletWebContextTests('test_bootstrap_original_raw_precedes_interpretation_and_reconstructs_actual_native_birth')
        self.context_test.setUp();test.addCleanup(self.context_test.doCleanups)
        self.root,self.lock,self.binding=self.context_test.root,self.context_test.lock,self.context_test.binding
        self.template,_app=frame();self.base=self.template['document']['clockAfter']['epochMs']+1000
        # Configure fixture INPUT URLs before any original from this model is
        # produced. Existing observations and their hashes are never rebased.
        def fixture_inputs(value):
            if type(value) is dict:return {key:fixture_inputs(child) for key,child in value.items()}
            if type(value) is list:return [fixture_inputs(child) for child in value]
            return value.replace(ROOT,fixture_url) if type(value) is str else value
        self.template=fixture_inputs(self.template)
        self.elapsed=0.;self.raw={};self.commands=[];self.sequence={};self.lost=None;self.force=None
        def processes(node):
            if type(node) is dict:
                for key,value in node.items():
                    if key=='processId':node[key]=42
                    else:processes(value)
            elif type(node) is list:
                for value in node:processes(value)
        processes(self.template)
        self.template['ledger'].update(events=[],eventSequence=0)
        self.template['sources'].update(roots=[],navigations=[],carriers=[])
        self.template['document'].update(status='unavailable',source={})
        for name in ('models','tablets','buttons','controls'):self.template['buttons'][name]=[]
        self.template['state'].update(iosTabletWebStateVersion=2,presentations=[],owners=[],targets=[],otherLiveTablets=0)
        self.template['browser'].update(sequence=0,responses=[])
        self.template['touches']['targets']=[]
        for row in self.template['touches']['contacts']:row['source']=None
        for row in self.template['touches']['dispatches']:
            for phase in row['phases']:phase['source']=None
        self.qt=QtKeys();self.pointer=NativePointerBoundary();self.roots=RootCensus()
        self.native=feature_tests.Boundary();self.native.sequence=self.context_test.setup['sequence']
        self.native.mutate=self.native_fields
        self.target=dict(appId='org.example.client',platform='ios',physical=True,probe=dict(kind='ios-documents'),
            nativeUiObservation=dict(kind='uikit-documents',version=1),testBuild=dict(fixtureOrigin='http://controlled.invalid:49121',resultsDirectory='owned-results'))
        self.sdk=SimpleNamespace(execute=self.execute)
        from ios.adapters import feature_observation,normal_input
        for change in (patch.object(feature_observation,'post_request',side_effect=self.post),patch.object(normal_input,'urlopen',side_effect=self.post)):
            change.start();test.addCleanup(change.stop)
        self.transport=FeatureObservation(self.sdk,self.binding['sessionId'],self.target,self.process,epoch_ms=self.epoch,monotonic=self.mono,sleep=self.sleep)
        self.bootstrap=TabletWebContext(self.root,self.binding,RUN,'primary',self.lock,self.context_test.proof,self.context_test.setup,lambda:True,monotonic=self.mono)
        self.bootstrap.bootstrap(self.transport.native_observer())
        self.clock=self.transport.native_observer();native=self.transport.bound_native_observer(self.clock);restore_native(native,self.bootstrap.original())
        self.journal=Journal(self.host)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('tablet-web')
        self.journal.activate(RUN,'f'*32);self.client=Client(fixture_url.split('/runs/')[0],'a'*64);self.client.request=self.request
        phase=PhaseFixtureReader(self.client,RUN,'tablet-web',epoch_ms=self.host,monotonic=self.mono)
        self.source=TabletWebSourceOwner(self.root,self.binding,RUN,'primary',fixture_url,42,self.lock,lambda:True,epoch_ms=self.host,monotonic=self.mono)
        readers={name:getattr(self.transport,method)(self.clock) for name,method in FACTORIES.items()}
        readers['dom']=TabletWebDOMDisposition.from_reader(readers['dom'])
        observer=TabletWebObserver(self.source,readers,native,phase,lambda:deepcopy(self.template['browser']),origins)
        self.runtime=TabletRuntimeObserver(observer,self.bootstrap)
        self.runtime.transport,self.runtime.native_clock_source=self.transport,self.clock
        self.runtime.native_clock=lambda:self.clock.read(self.clock.sequence)['capturedEpochMs']
        self.runtime.client,self.runtime.target,self.runtime.process,self.runtime.check=self.sdk,self.target,self.process,lambda:True
    def epoch(self):return self.base+round(self.elapsed*1000)
    def host(self):return self.epoch()+10000
    def mono(self):return self.elapsed
    def sleep(self,duration):self.elapsed+=duration
    def process(self):return dict(bundleId=self.target['appId'],pid=42,foreground=True)
    def request(self,path,value=None,**kwargs):
        if path.endswith('/phase'):return self.journal.phase(RUN,kwargs['phase_nonce'])
        if path.endswith('/samples'):
            if value is not None:self.journal.publish(RUN,value)
            return self.journal.snapshot(RUN)
        raise AssertionError('Unexpected fixture request')
    def native_fields(self,value):
        epoch=self.epoch()
        def clocks(node):
            if type(node) is dict:
                for key,child in node.items():
                    if key.endswith('EpochMs'):node[key]=epoch
                    else:clocks(child)
            elif type(node) is list:
                for child in node:clocks(child)
        clocks(value);value['processId']=42
    def produce(self,query):
        action=query['action'];self.sequence[action]=self.sequence.get(action,0)+1;index=self.sequence[action];epoch=self.epoch()
        mapping={'feature-ios-tablet-sources':'sources','feature-ios-tablet-web':'ledger','feature-ios-tablet-web-dom':'document',
            'feature-ios-tablet-app-buttons':'buttons','feature-ios-uikit-input':'touches','feature-ios-tablet-web-state':'state',
            'feature-ios-tablet-web-closures':'closures','feature-ios-web-script-emissions':'emitter','feature-ios-tablet-web-deferred':'deferred'}
        if action=='feature-native-observe':self.native.send(query);return 'feature-native-observation.json',deepcopy(self.native.sample)
        if action in mapping:
            value=deepcopy(self.template[mapping[action]]);value.update(commandId=query['commandId'],sequence=index)
            if action.endswith('closures'):value['capturedEpochMs']=epoch
            else:value.update(clockBefore=stamp(epoch),clockAfter=stamp(epoch))
            return action+'.json',value
        if action=='feature-ios-world-web-keys':
            self.qt.epoch=epoch;value=self.qt.packet();value.update(requestId=query['commandId']);return action+'.json',value
        if action=='feature-ios-pointer-state':
            self.pointer.now=epoch;self.pointer.send(query);return action+'.json',deepcopy(self.pointer.packet)
        if action=='feature-ios-script-dialogs':
            return action+'.json',dict(iosScriptDialogVersion=1,requestId=query['commandId'],runId=RUN,instance='1'*32,sequence=index,processId=42,
                clockDomain='native-main-script-dialog',clockBefore=stamp(epoch),clockAfter=stamp(epoch),
                source=dict(scriptDialogLedgerVersion=1,instance='2'*32,processId=42,complete=True,eventSequence=0,events=[]))
        if action=='feature-script-terminal-observe':
            return 'feature-script-terminal.json',dict(scriptTerminalObservationVersion=1,commandId=query['commandId'],instance='3'*32,sequence=index,
                processId=42,requestedEpochMs=epoch,capturedEpochMs=epoch,source=dict(scriptTerminalVersion=1,instance='4'*32,processId=42,complete=True,eventSequence=0,events=[]))
        if action=='feature-script-observe':
            return 'feature-script-observation.json',dict(schemaVersion=1,requestId=query['commandId'],instance='5'*32,sequence=index,processId=42,
                requestedEpochMs=epoch,capturedEpochMs=epoch,source=dict(complete=True,engines=[],sourceIdentityVersion=1,membershipSourceVersion=1,
                    membership=dict(complete=True,revision=0,managers=[])))
        if action=='native-geometry-snapshot':
            return 'ios-ui-request-result.json',dict(schemaVersion=1,commandId=query['commandId'],observation=dict(schemaVersion=1,sampleEpochMs=epoch,
                sampleSequence=index,window=dict(width=1024,height=768),nativeUi=dict(valid=True,keyboardVisible=False,imeInsetBottom=0,
                    safeInsetLeft=0,safeInsetTop=0,safeInsetRight=0,safeInsetBottom=0,surfaceWidth=1024,surfaceHeight=768,density=1,fontScale=1)))
        if action=='normal-ui-input':
            assert query['operation']=='observe'
            self.roots.elapsed=epoch-20000;root=self.roots.source();root['processId']=42
            return 'ios-normal-ui-request-result.json',dict(schemaVersion=1,commandId=query['commandId'],observation=dict(schemaVersion=1,
                instance='11111111-1111-4111-8111-111111111111',frameSpace='qt-window-logical',processId=42,sampleEpochMs=epoch,
                elapsedMs=round(self.elapsed*1000),lastSequence=0,tabletShown=False,ready=True,controls=[],fileControlsVersion=1,featureControlsVersion=1,
                scriptObservationVersion=1,scriptSourceSequence=index,scriptInventory=dict(inventoryVersion=2,complete=True,tabletPresent=True,tabletShown=False,
                    managers=[],pickers=[],rootOwnership=root,rootMembership=dict(managers=[],pickers=[]))))
        raise AssertionError('Unexpected native action '+action)
    def post(self,request,timeout):
        query=json.loads(request.data);self.commands.append(deepcopy(query));self.sleep(.002)
        name,value=self.produce(query)
        if self.force is not None:self.force(query,value)
        self.raw[name]=json.dumps(value);self.echo=json.dumps(query).encode()
        if self.lost==query['action']:raise OSError('Actual HTTP response return lost')
        return self
    status=200
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,limit):return self.echo[:limit]
    def execute(self,session,operation,arguments):
        assert session==self.binding['sessionId'] and operation=='mobile: pullFile'
        prefix='@'+self.target['appId']+':documents/owned-results/';assert arguments['remotePath'].startswith(prefix)
        return base64.b64encode(self.raw[arguments['remotePath'][len(prefix):]].encode()).decode()
