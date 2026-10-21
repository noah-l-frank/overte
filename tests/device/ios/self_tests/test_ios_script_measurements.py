"""Script joins on original iOS HTTP/AFC frames; native SDKs are synthetic.

No compiler, device, Appium server, or installed-product acceptance is involved.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.native_script_files import originals, OwnedScriptFiles
from adapters.token_script_file_ui import file_url
from adapters.script_feature.measurements import ScriptMeasurements, compose
from adapters.script_feature.history import ScriptSourceHistory, DurableScriptMeasurements, unpack
from adapters.script_feature.observation import ScriptObservation
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.script_observation import IOSScriptObservation
from ios.adapters.script_ui_source import IOSScriptUISource
from ios.adapters import normal_input
from ios.self_tests.test_ios_script_ui_source import Boundary as UI
from self_tests.test_native_script_observation import Boundary as Execution, code_source, effect_source, RUN
from self_tests.test_native_feature_observation import Boundary as Lifecycle
from self_tests.test_native_script_files import Boundary as Storage
from self_tests.test_native_script_loads import history, event
from self_tests.test_native_script_membership import membership_source
from self_tests.test_script_ui_inventory import inventory, picker
from self_tests.test_script_manager_status import observed

TICKET='b'*32
FIXTURE='http://fixture.test:12345/feature-fixture/v1/runs/'+RUN+'/'
BINDING=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='31',sessionId='actual-session',generation=1,targetFingerprint='c'*64)


class IOSScriptMeasurementTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.directory=(self.root/('feature-script-'+RUN)).as_uri()
        self.storage=Storage(self.root);self.storage.root=self.root/('feature-script-'+RUN)
        self.storage.mutate=lambda value:value.update(instance='b'*32)
        self.files=OwnedScriptFiles(self.storage.native(ios=True),PrivateFeatureState(self.root/'files.json'),BINDING)
        self.files.reserve(RUN);self.files.stage_reserved()
        self.execution=Execution();self.execution.engine['url']=self.directory+'/script.js'
        self.execution.engine['required']['modules'][0]['url']=self.directory+'/companion.js'
        def measured(value):
            code_source(value,originals(RUN)['script.js'].decode());effect_source(value);history(value,[]);membership_source(value)
        self.execution.mutate=measured
        self.ui=UI();self.ui.pid=31;self.ui.inventory=inventory([observed(statusText='',labelText='',labelVisible=False)])
        self.ui.edit=lambda value:value.update(processId=31,tabletShown=True)
        self.lifecycle=Lifecycle();self.lifecycle.mutate=lambda value:value.update(processId=31,instance='b'*32)
        self.service_sequence=0;self.okay=True
        self.patch=patch.object(normal_input,'urlopen',self.ui.post);self.patch.start();self.addCleanup(self.patch.stop)

    def source(self):
        def service(after):
            self.service_sequence+=1
            return dict(schemaVersion=1,instance='f'*32,sampleSequence=self.service_sequence,sampleEpochMs=20000,
                complete=True,scripts=[dict(url=self.directory+'/script.js',path=file_url(self.directory+'/script.js'))]),20000
        storage=self.storage.native(ios=True)
        files=OwnedScriptFiles(storage,self.files.store,BINDING)
        def verify():return files.verify()
        verify()
        source=IOSScriptUISource(self.ui.input(),lambda:20000,lambda:self.okay,31,monotonic=lambda:0.)
        lifecycle=self.lifecycle.reader(ios=True);lifecycle.pid=31
        reader=ScriptMeasurements(RUN,self.directory,FIXTURE,self.execution.reader(ios=True),source,service,lifecycle,
            verify,lambda:self.okay,file_instance=lambda:storage.instance,monotonic=lambda:0.)
        reader.file_observation=lambda:deepcopy(storage.last_packet)
        return reader

    def clocked(self,role='primary',*,epoch=1000000.):
        lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        observation_store=PrivateFeatureState(self.root/('script-feature-'+role+'-observation.json'))
        history_store=PrivateFeatureState(self.root/('script-feature-'+role+'-history.json'))
        def factory(held):
            reader=self.source()
            archive=ScriptSourceHistory(history_store,BINDING,RUN,role,self.directory,FIXTURE)
            return DurableScriptMeasurements(reader,archive,source_lock=held)
        inner=ScriptObservation(observation_store,BINDING,RUN,role,FIXTURE,factory,lock,lambda:self.okay,monotonic=lambda:0.)
        clock=self.lifecycle.reader(ios=True);clock.pid=31
        return IOSScriptObservation(inner,clock,history_store,PrivateFeatureState(self.root/('script-feature-'+role+'-clock.json')),
            epoch_ms=lambda:epoch,monotonic=lambda:0.)

    def test_five_new_originals_keep_native_clock_while_public_acquisition_uses_host_clock(self):
        owner=self.clocked();first=owner.read(TICKET,999999)
        self.assertEqual(1000000,first['hostCapturedEpochMs']);self.assertEqual(20000,first['measurement']['capturedEpochMs'])
        self.assertEqual(dict(running=['owned-script'],picker=False,error='none',effects=2,open=True,companions=['companion.js']),first['measurement']['state'])
        self.assertEqual(['entity:script-effect','file:script-fixtures','panel:script-manager','script:owned-script'],first['resources'])
        self.assertTrue(first['sources']['ui']['commandId'].startswith('ios-'))
        self.assertEqual(first['sources']['ui']['originalReceipt'],self.ui.receipt)
        self.assertEqual('ready',owner.store.read()['phase'])

    def test_reconstructed_owner_replays_validation_only_then_acquires_new_nonce_and_all_sources(self):
        first=self.clocked().read(TICKET,999999)
        before=(len(self.ui.requests),len(self.execution.commands),len(self.lifecycle.commands))
        owner=self.clocked();self.assertEqual(before,(len(self.ui.requests),len(self.execution.commands),len(self.lifecycle.commands)))
        second=owner.read(TICKET,999999)
        self.assertNotEqual(first['sources']['execution']['requestId'],second['sources']['execution']['requestId'])
        self.assertNotEqual(first['sources']['ui']['commandId'],second['sources']['ui']['commandId'])
        self.assertEqual(2,len(unpack(owner.history_store.read()['transcript'])))

    def test_actor_makes_its_own_original_requests_and_keeps_separate_history(self):
        first=self.clocked().read(TICKET,999999);second=self.clocked('actor').read(TICKET,999999)
        for source,key in (('execution','requestId'),('ui','commandId'),('lifecycle','requestId')):
            self.assertNotEqual(first['sources'][source][key],second['sources'][source][key])
        self.assertEqual(1,self.clocked('actor').inner.state['sequence'])

    def test_ignored_input_source_retains_uncertainty_and_cannot_return_stored_measurement(self):
        self.clocked().read(TICKET,999999);owner=self.clocked();self.execution.ignore=True
        with self.assertRaises(NativeUIError):owner.read(TICKET,999999)
        self.assertEqual('reading',owner.store.read()['phase'])
        before=len(self.execution.commands)
        with self.assertRaises(NativeUIError):self.clocked()
        self.assertEqual(before,len(self.execution.commands))

    def test_foreign_clock_join_digest_or_public_host_clock_cannot_relabel_old_native_sources(self):
        owner=self.clocked();owner.read(TICKET,999999)
        value=owner.inner.store.read();packet=deepcopy(value);packet['fileObservation']['source']['directory']='file:///foreign'
        owner.inner.store.write(packet,value)
        with self.assertRaises(NativeUIError):self.clocked()

    def test_changed_companion_bytes_are_not_empty_or_successful_execution(self):
        (self.storage.root/'companion.js').write_bytes(b'foreign bytes')
        with self.assertRaises(NativeUIError):self.clocked().read(TICKET,999999)

    def test_actual_pending_hidden_picker_and_partial_inventory_cannot_be_cleaned(self):
        for visual in (inventory(complete=False),inventory(pickers=[picker(visible=False,requestId='actual-pending')],tabletShown=False)):
            self.ui.inventory=visual
            with self.assertRaises(NativeUIError):self.source().read(TICKET,19000)

    def test_missing_actual_membership_or_submitted_code_cannot_borrow_file_url(self):
        original=self.execution.mutate
        for mutate in (lambda v:v['source'].pop('membershipSourceVersion'),
                       lambda v:v['source']['engines'][0]['code'].update(sha256='f'*64)):
            self.execution.mutate=lambda value:(original(value),mutate(value))
            with self.assertRaises(NativeUIError):self.source().read(TICKET,19000)

    def test_candidate_guard_loss_prevents_fresh_observation(self):
        reader=self.source();self.okay=False
        before=len(self.execution.commands)
        with self.assertRaises(NativeUIError):reader.read(TICKET,19000)
        self.assertEqual(before,len(self.execution.commands))


if __name__=='__main__':unittest.main()
