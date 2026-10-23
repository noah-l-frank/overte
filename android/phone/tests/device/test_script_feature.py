"""Phone Script facade against synthetic native SDK and real loopback fixture.

Only host control logic is exercised. No APK, native binary or device is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from functools import partial
import secrets
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
import test_feature_adapters as bound
from overte_phone_script_feature import PhoneScriptFeature,ScriptFixtureReader,ScriptPhasePending
from adapters.normal_ui import NativeUIError
from adapters.token_script_file_ui import file_url
from adapters.native_script_files import originals
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.scenarios import VERSION
from self_tests.test_native_script_loads import history,event
from self_tests.test_native_script_membership import membership_source,manager
from self_tests.test_native_script_observation import code_source,effect_source
from self_tests.test_script_ui_inventory import inventory,picker
from self_tests.test_script_manager_status import observed

RUN='a'*32


class ScriptFeatureTests(unittest.TestCase):
    def setUp(self):
        self.f=bound.FeatureAdapterTests('test_phone_initial_script_baseline_uses_actual_native_location_without_staging_files')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.commands,_fixture,files=self.f.script_measurement_boundaries(absent=True)
        files.store.discard(files.owned());self.storage=self.f.script_measurement_storage
        self.f.read_only_boundaries(forbid_normal_session=False)
        sdk_call=self.f.native.call
        def sdk(method,path,body=None):
            if method=='DELETE' and path=='/session/native-session':return None
            return sdk_call(method,path,body)
        for boundary in (patch('adapters.shared_appium.adapter.WebDriver',return_value=self.f.native),
                         patch.object(self.f.native,'call',side_effect=sdk)):
            boundary.start();self.addCleanup(boundary.stop)
        self.f.target.update(scene={'kind':'android-debug-e2e'},clientControl={
            'kind':'android-run-as-command','relativePath':self.f.adapter.ANDROID_CLIENT_COMMAND})
        self.f.target['capabilities']['appium:autoLaunch']=False
        self.f.adapter.read_session(bound.SELECTOR)['targetFingerprint']=self.f.adapter.snapshot_fingerprint(self.f.target)
        self.clock=0.0;self.ticket_count=0;self.events=[];self.active_engine=None;self.retired=[]
        self.engine_count=0;self.member_revision=0;self.status='';self.error_url='';self.error_epoch=0;self.input_ignored=False
        self.birth='d'*32;self.load_birth='c'*32
        self.server=make_server(secrets.token_hex(32),secrets.token_hex(32))
        self.server.script_resources.clock_ms=self.epoch
        self.server.journal.clock=self.epoch
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop_server)
        url='http://127.0.0.1:'+str(self.server.server_port)+'/feature-fixture/v1'
        self.client=Client(url,self.server.reader_token)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):
            self.run,self.fixture=self.client.register('scripts')
        self.source=ScriptFixtureReader(self.client,RUN,epoch_ms=self.epoch)
        self.actor_client=Client(url,self.server.actor_token)
        self.actor_source=ScriptFixtureReader(self.actor_client,RUN,epoch_ms=self.epoch)
        self.primary=PhoneScriptFeature(self.f.adapter,bound.SELECTOR,self.source,monotonic=lambda:self.clock,sleep=self.sleep)
        self.actor=PhoneScriptFeature(self.f.adapter,bound.SELECTOR,self.actor_source,role='actor',monotonic=lambda:self.clock,sleep=self.sleep)
        original_send=self.f.adapter.write_android_client_command.side_effect
        original_read=self.f.fixture.adb.read_debug_app_file.side_effect
        self.last_presence=None;self.presence_sequence=0
        def send(client,session,target,command,process):
            self.f.native.epoch_ms=self.epoch()
            if command['action']=='feature-process-presence':
                self.presence_sequence+=1
                self.last_presence=dict(processPresenceVersion=1,commandId=command['commandId'],instance=self.birth,
                    sequence=self.presence_sequence,processId=int(self.f.native.identity.split(':')[0]),
                    queryProcessId=command['queryProcessId'],requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),
                    presence='absent',nativeResult=-1,nativeError=3,errorSymbol='ESRCH')
                return
            original_send(client,session,target,command,process)
            if command['action']=='phone-script-file-ui':
                request=command['request']
                if request.get('controlId')=='script-file.confirm':self.synchronize()
        def read(device,package,path,**options):
            if path.endswith('/feature-process-presence.json'):return json.dumps(self.last_presence)
            raw=original_read(device,package,path,**options);value=json.loads(raw)
            if path.endswith('/feature-script-observation.json'):
                self.synchronize();source=value['source'];source['engines']=[]
                if self.active_engine is not None:
                    engine=deepcopy(self.active_engine);source['engines']=[engine]
                    code_source(value,originals(RUN)[engine['url'].removeprefix(self.storage.root.as_uri()+'/')].decode(),
                                submitted=engine.pop('submittedAt'))
                    ticks=2+int(self.clock*10)
                    effect_source(value,ticks=ticks,edited=self.epoch()*1000)
                    row=source['effects']['entities'][0]
                    row.update(id=self.entity_id(),name='e2e-'+RUN+'-script',userData=json.dumps(dict(runId=RUN,ticks=ticks)))
                else:
                    source.update(sourceIdentityVersion=1,effectSourceVersion=1,
                        effects=dict(complete=True,scanRadiusMeters=64,scannedEntities=0,entities=[],absentIds=[]))
                source['effects']['absentIds']=deepcopy(self.retired)
                history(value,self.events);source['loads']['instance']=self.load_birth
                membership_source(value,revision=self.member_revision)
                for row in source['membership']['managers']:
                    row['assignedEpochMs']=self.active_engine['submittedAt']
                    row['loadGeneration']=next(event['loadGeneration'] for event in self.events
                        if event['managerInstance']==row['instance'])
                value.update(instance=self.birth,processId=int(self.f.native.identity.split(':')[0]),
                    requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
            elif path.endswith('/phone-script-file-ui.json'):
                value['processId']=int(self.f.native.identity.split(':')[0])
                if value['action']=='observe':
                    value['capturedEpochMs']=self.epoch()
                    # Passive native inventory derives from the synthetic SDK's
                    # actual open page and actual picker controls, never a verb.
                    opened=self.f.native.screen=='scripts'
                    picker_open=any('picker' in row for row in value['controls'])
                    value['scriptInventory']=inventory([observed(statusText=self.status,labelText=self.status,
                        labelVisible=bool(self.status),errorUrl=self.error_url,errorEpochMs=self.error_epoch)] if opened else [],[picker()] if picker_open else [],
                        tabletPresent=self.f.native.screen is not None,tabletShown=self.f.native.screen is not None)
            elif path.endswith('/feature-native-observation.json'):
                def timestamps(node):
                    if type(node) is dict:
                        for key,item in node.items():
                            if key.endswith('EpochMs'):node[key]=self.epoch()
                            else:timestamps(item)
                    elif type(node) is list:
                        for item in node:timestamps(item)
                timestamps(value);value.update(instance=self.birth,processId=int(self.f.native.identity.split(':')[0]),
                    lifecycle=deepcopy(self.f.native.lifecycle))
            elif path.endswith('/normal-feature-observation.json'):
                value['sampleEpochMs']=self.epoch()
                for row in value['scripts']:row['path']=file_url(row['url'])
            return json.dumps(value)
        def storage_clock(packet):
            packet.update(instance=self.birth,processId=int(self.f.native.identity.split(':')[0]),
                requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
        self.storage.mutate=storage_clock
        for boundary in (patch.object(self.f.adapter,'write_android_client_command',side_effect=send),
                         patch.object(self.f.fixture.adb,'read_debug_app_file',side_effect=read),
                         patch.object(self.f.fixture.adb,'epoch_milliseconds',side_effect=lambda *_:self.epoch()),
                         patch.object(bound.appium,'ScriptRestartHandoff',partial(bound.ScriptRestartHandoff,
                            monotonic=lambda:self.clock,sleep=self.sleep)),
                         patch.object(bound.appium,'RestartInputs',partial(bound.RestartInputs,monotonic=lambda:self.clock))):
            boundary.start();self.addCleanup(boundary.stop)
        def mutation(name):
            if name=='OK' and self.f.native.text.endswith('/missing.js'):
                with urlopen(self.f.native.text,timeout=2) as response:response.read()
            self.synchronize()
        def input_mutation(name):
            try:mutation(name)
            except HTTPError as error:
                try:
                    self.assertEqual(404,error.code);error.read()
                    self.events.append(event(len(self.events)+1,url=self.f.native.text,callbackEpochMs=self.epoch()))
                    self.error_url=self.f.native.text;self.error_epoch=self.epoch()
                    self.status='Failed to load missing.js: server returned 404'
                finally:error.close()
        self.f.native.mutation=input_mutation
        def launch():
            self.birth='a'*32;self.load_birth='7'*32;self.events=[];self.active_engine=None;self.retired=[]
            self.member_revision=0;self.status='';self.error_url='';self.error_epoch=0
            self.f.native.identity='32:15';self.f.native.screen=None;self.f.native.rows=[];self.f.native.instance='9'*32
            self.f.script_measurement_ui.ui.opened=False
            self.f.script_measurement_ui.ui.instance='e'*32
            self.f.script_measurement_ui.generation='f'*32
        self.f.native.on_launch=launch
        self.f.native.epoch_ms=self.epoch()
        self.activate('baseline')

    def stop_server(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive());self.assertEqual(0,self.server.internal_errors)

    def epoch(self):return 20000+round(self.clock*1000)
    def sleep(self,value):self.clock+=value;self.f.native.epoch_ms=self.epoch()
    def entity_id(self):return '11111111-1111-4111-8111-'+format(self.engine_count,'012x')

    def close_fixture(self):
        # Only the pre-existing runner Client's host clock is a boundary here;
        # the actual loopback provider keeps its independently controlled clock.
        with patch('feature_journeys.witness.time.time',side_effect=lambda:self.epoch()/1000):self.client.close()

    def synchronize(self):
        rows=self.f.native.rows
        if self.active_engine is not None and not any(row['url']==self.active_engine['url'] for row in rows):
            self.retired.append(self.entity_id());self.active_engine=None;self.member_revision+=1
        if rows and self.active_engine is None and not self.input_ignored:
            self.engine_count+=1;self.member_revision+=1
            url=rows[0]['url'];instance=format(100+self.engine_count,'032x')
            self.active_engine=dict(url=url,running=True,stopping=False,finished=False,submittedAt=self.epoch(),
                required=dict(instance=instance,sequence=1,modules=[dict(url=url.rsplit('/',1)[0]+'/companion.js',
                    loaded=True,cached=False,sequence=1,capturedEpochMs=self.epoch())]))
            self.events.append(event(len(self.events)+1,managerInstance=instance,url=url,success=True,status='Success',
                callbackEpochMs=self.epoch()))

    def activate(self,verb,inputs=None):
        self.ticket_count+=1;ticket=format(1000+self.ticket_count,'032x')
        self.client.activate(ticket,verb,inputs or {})
        return dict(contractVersion=VERSION,runId=RUN,fixtureUrl=self.fixture,ticket=ticket,verb=verb,inputs=inputs or {})

    def observe(self,flow=None):
        return (flow or self.primary).observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))

    def act(self,verb,inputs=None):return self.primary.act(self.activate(verb,inputs))

    def test_baseline_uses_independent_original_sources_no_stage_and_separate_actor_history(self):
        one=self.observe();two=self.observe(self.actor)
        self.assertEqual([],one['resources']);self.assertEqual(one['state'],two['state'])
        self.assertFalse(self.storage.root.exists());self.assertEqual([],self.f.native.inputs)
        self.assertNotEqual(self.primary.role_store.path,self.actor.role_store.path)
        self.assertIsNotNone(self.f.adapter.script_history_store(bound.SELECTOR,'actor').read())

    def test_normal_import_stop_cancel_missing_url_and_close_retain_actual_results(self):
        self.observe();self.observe(self.actor)
        for verb,inputs in [('open',{}),('picker-open',{}),('picker-cancel',{}),('picker-open',{}),
            ('picker-accept',{'resource':'script.js'}),('stop-owned',{}),
            ('load-url',{'resource':'missing.js'}),('close',{})]:
            self.assertEqual({'performed':True},self.act(verb,inputs))
            primary=self.observe();actor=self.observe(self.actor)
            self.assertEqual(primary['state'],actor['state'])
            if verb=='picker-accept':
                self.assertEqual(['owned-script'],primary['state']['running']);self.assertGreater(primary['state']['effects'],0)
            if verb=='load-url':
                self.assertEqual('not-found',primary['state']['error'])
                self.assertEqual(1,len(self.server.script_resources.snapshot(RUN)['responses']))
        self.assertFalse(primary['state']['open']);self.assertEqual(['file:script-fixtures'],primary['resources'])

    def test_ignored_input_ack_never_becomes_successful_script_readiness(self):
        self.observe();self.act('open');self.act('picker-open');self.input_ignored=True
        with self.assertRaises(NativeUIError):self.act('picker-accept',{'resource':'script.js'})
        self.assertEqual('acting',self.primary.control()['phase'])
        with self.assertRaises(ScriptPhasePending):self.observe(self.actor)
        self.assertIsNotNone(self.f.adapter.script_files_store(bound.SELECTOR).read())

    def test_actor_waits_for_new_ticket_without_publishing_a_prior_input_as_current(self):
        self.observe();self.actor.publish();self.activate('open')
        before=len(self.client.observe()['entries'])
        with self.assertRaises(ScriptPhasePending):self.actor.publish()
        self.assertEqual(before,len(self.client.observe()['entries']))
        self.assertEqual('ready',self.actor.role_state()['phase'])

    def test_actor_drops_a_sample_when_the_ticket_changes_during_its_original_acquisition(self):
        self.observe();self.actor.publish();original=self.actor_source.read;calls=[0];issued=[]
        def read(previous=None):
            calls[0]+=1
            if calls[0]==2:issued.append(self.activate('open'))
            return original(previous)
        with patch.object(self.actor_source,'read',side_effect=read):
            with self.assertRaises(ScriptPhasePending):self.actor.publish()
        self.assertEqual('ready',self.actor.role_state()['phase'])
        self.assertEqual(1,len(self.client.observe()['entries']))
        self.primary.act(issued[0]);self.actor.publish()
        entries=self.client.observe()['entries']
        self.assertEqual(2,len(entries));self.assertEqual(issued[0]['ticket'],entries[-1]['ticket'])
        self.assertTrue(entries[-1]['facts']['open'])

    def test_actor_token_can_publish_but_reader_token_cannot_publish_measured_facts(self):
        self.observe();self.actor.publish()
        self.assertEqual(1,len(self.client.observe()['entries']))
        wrong=PhoneScriptFeature(self.f.adapter,bound.SELECTOR,self.source,role='actor')
        with self.assertRaises(ValueError):wrong.publish()
        self.assertEqual(1,len(self.client.observe()['entries']))

    def test_foreign_stimulus_is_rejected_before_any_normal_input(self):
        self.observe();call=self.activate('open');before=list(self.f.native.inputs)
        with self.assertRaises(NativeUIError):self.primary.act(call|dict(verb='picker-open'))
        self.assertEqual(before,self.f.native.inputs)

    def test_provider_instance_change_or_lost_durable_sample_cannot_reset_history(self):
        self.observe();before=len(self.commands)
        self.server.script_resources.instance='f'*32
        with self.assertRaises((ValueError,RuntimeError)):self.observe()
        self.assertEqual(before,len(self.commands))
        with self.assertRaises(NativeUIError):self.observe()

    def test_cleanup_proves_quiet_absence_releases_actual_files_and_is_idempotent(self):
        self.observe();self.act('open');self.act('picker-open');self.act('picker-accept',{'resource':'script.js'})
        self.observe();self.activate('cleanup')
        call=dict(contractVersion=VERSION,runId=RUN)
        self.assertEqual({'performed':True},self.primary.cleanup(call))
        first=self.observe();self.observe(self.actor)
        self.assertEqual([],first['resources']);self.assertFalse(self.storage.root.exists())
        self.assertEqual({'performed':True},self.primary.cleanup(call))
        self.assertGreater(self.observe()['sequence'],first['sequence'])
        self.assertEqual(1,sum(row['operation']=='release' for row in self.storage.commands))

    def test_ignored_release_retains_cleanup_and_never_reports_empty_resources(self):
        self.observe();self.act('open');self.activate('cleanup');self.storage.fault='ignored-release'
        with self.assertRaises(NativeUIError):self.primary.cleanup(dict(contractVersion=VERSION,runId=RUN))
        self.assertEqual('cleaning',self.primary.control()['phase']);self.assertTrue(self.storage.root.exists())
        self.assertIsNotNone(self.f.adapter.script_files_store(bound.SELECTOR).read())
        with self.assertRaises(ScriptPhasePending):self.observe(self.actor)

    def test_restart_requires_each_roles_original_bundle_and_fresh_kernel_exit_without_autoload(self):
        self.observe();self.observe(self.actor)
        for verb,inputs in [('open',{}),('picker-open',{}),('picker-accept',{'resource':'script-bundle/main.js'})]:
            self.act(verb,inputs);self.observe();self.observe(self.actor)
        old_primary=self.f.adapter.script_history_store(bound.SELECTOR,'primary').read()
        old_actor=self.f.adapter.script_history_store(bound.SELECTOR,'actor').read()
        self.assertEqual({'performed':True},self.act('restart-app'))
        primary=self.observe();actor=self.observe(self.actor)
        self.assertEqual([],primary['state']['running']);self.assertFalse(primary['state']['open'])
        self.assertEqual(primary['state'],actor['state']);self.assertEqual(['stop','launch'],self.f.native.lifecycle_inputs)
        self.assertEqual(old_primary,self.f.adapter.script_history_store(bound.SELECTOR,'primary').read())
        self.assertEqual(old_actor,self.f.adapter.script_history_store(bound.SELECTOR,'actor').read())
        self.assertNotEqual(self.primary.role_state()['restart']['exit']['commandId'],self.actor.role_state()['restart']['exit']['commandId'])
        self.assertEqual('ESRCH',self.actor.role_state()['restart']['exit']['errorSymbol'])
        for verb,inputs in [('open',{}),('picker-open',{}),('picker-cancel',{}),('picker-open',{}),
                            ('picker-accept',{'resource':'script-bundle/main.js'})]:
            self.act(verb,inputs);self.assertEqual(self.observe()['state'],self.observe(self.actor)['state'])
        self.assertEqual(1,sum(row['operation']=='stage' for row in self.storage.commands))

    def test_actor_without_original_pre_restart_bundle_cannot_adopt_primarys_restart_proof(self):
        self.observe();self.observe(self.actor)
        for verb,inputs in [('open',{}),('picker-open',{}),('picker-accept',{'resource':'script-bundle/main.js'})]:
            self.act(verb,inputs);self.observe()
        self.act('restart-app');self.observe()
        with self.assertRaises(NativeUIError):self.observe(self.actor)
        self.assertIsNone(self.f.adapter.script_history_store(bound.SELECTOR,'actor',stage=1).read())

    def test_native_not_found_without_the_original_http_receipt_cannot_be_reported(self):
        self.observe();self.act('open');self.act('picker-open');self.act('picker-accept',{'resource':'script.js'})
        self.act('stop-owned');self.act('load-url',{'resource':'missing.js'})
        self.server.script_resources.runs[RUN]['responses']=[]
        with self.assertRaises((RuntimeError,ValueError)):self.observe()

    def test_ignored_stop_retains_actual_execution_and_fails_cleanup_before_file_release(self):
        self.observe();self.act('open');self.act('picker-open');self.act('picker-accept',{'resource':'script.js'})
        self.observe();self.activate('cleanup');self.f.native.ignore_stop=True
        with self.assertRaises(NativeUIError):self.primary.cleanup(dict(contractVersion=VERSION,runId=RUN))
        self.assertTrue(self.storage.root.exists())
        self.assertFalse(any(row['operation']=='release' for row in self.storage.commands))

    def cleaned(self):
        self.observe();self.observe(self.actor);self.act('open');self.observe();self.observe(self.actor)
        self.activate('cleanup');self.primary.cleanup(dict(contractVersion=VERSION,runId=RUN));self.observe()

    def test_finalization_requires_the_actors_own_cleanup_observation(self):
        self.cleaned()
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.store.read());self.assertIsNotNone(self.actor.role_store.read())
        self.assertIsNone(self.primary.retirement_store.read())

    def test_original_fixture_retirement_stops_actor_and_both_observed_cleanups_allow_host_retirement(self):
        from overte_phone_script_feature import ScriptRunRetired
        self.cleaned();self.actor.publish();self.close_fixture()
        with self.assertRaises(ScriptRunRetired):self.actor.publish()
        self.assertEqual('retired',self.actor.role_state()['phase'])
        self.assertEqual({'performed':True},self.primary.finalize())
        self.assertTrue(all(store.read() is None for store in self.primary._retirement_paths()))
        self.assertIsNone(self.primary.retirement_store.read())

    def test_lost_partial_journal_retirement_resumes_only_its_hashes_and_rechecks_actual_absence(self):
        from adapters.normal_feature_state import PrivateFeatureState
        self.cleaned();self.observe(self.actor)
        original=PrivateFeatureState.discard;lost=[False]
        def discard(store,value):
            original(store,value)
            if store.path.name=='phone-script-actions.json' and not lost[0]:
                lost[0]=True;raise OSError('synthetic lost host retirement return')
        with patch.object(PrivateFeatureState,'discard',new=discard):
            with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.retirement_store.read());before=len(self.commands)
        self.assertEqual({'performed':True},self.primary.finalize())
        self.assertGreater(len(self.commands),before);self.assertFalse(self.storage.root.exists())
        self.assertEqual(1,sum(row['operation']=='release' for row in self.storage.commands))

    def test_retirement_cannot_remove_a_replaced_private_owner(self):
        from adapters.normal_feature_state import PrivateFeatureState
        self.cleaned();self.observe(self.actor);original=PrivateFeatureState.discard
        def discard(store,value):
            if store.path.name=='phone-script-actions.json':raise OSError('synthetic interruption before host retirement')
            return original(store,value)
        with patch.object(PrivateFeatureState,'discard',new=discard):
            with self.assertRaises(NativeUIError):self.primary.finalize()
        store=self.f.adapter.script_actions_store(bound.SELECTOR);value=store.read()
        changed=deepcopy(value);changed['runId']='f'*32;store.write(changed,value)
        before=len(self.commands)
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertEqual(before,len(self.commands));self.assertEqual(changed,store.read())

    def test_registered_invocation_and_capability_require_explicit_complete_configuration(self):
        import os
        self.assertFalse(any(value.startswith('feature.scripts.') for value in self.f.adapter.advertised_capabilities(self.f.target)))
        access=self.f.adapter.state_path(bound.SELECTOR).with_name('adapter-fixture-access.json')
        from adapters.normal_feature_state import PrivateFeatureState
        PrivateFeatureState(access).write(dict(fixtureAdapterAccessVersion=1,fixtureUrl=self.client.url,adapterToken='d'*64),None)
        config={'OVERTE_PHONE_FEATURE_SCRIPTS':'1','OVERTE_E2E_FEATURE_FIXTURE_URL':self.client.url,
                'OVERTE_PHONE_FEATURE_FIXTURE_CONFIG':str(access)}
        with patch.dict(os.environ,config),patch.object(self.f.adapter,'_script_feature',return_value=self.primary):
            caps=self.f.adapter.advertised_capabilities(self.f.target)
            self.assertTrue(all('feature.scripts.'+kind in caps for kind in ('act','observe','cleanup')))
            result=self.f.adapter.invoke(bound.SELECTOR,'feature.scripts.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
            self.assertEqual([],result['resources'])
        with self.assertRaises((ValueError,RuntimeError)):
            self.f.adapter.invoke(bound.SELECTOR,'feature.scripts.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))

    def test_general_cleanup_still_tears_down_but_refuses_an_unfinished_full_feature_owner(self):
        self.observe()
        with patch.object(self.f.adapter,'_script_feature',return_value=self.primary):
            with self.assertRaisesRegex((ValueError,RuntimeError),'PHONE_SCRIPT_FEATURE_CLEANUP_INCOMPLETE'):
                self.f.adapter.cleanup(bound.SELECTOR)
        self.assertFalse(self.f.native.running);self.assertIsNotNone(self.primary.store.read())

    def test_general_cleanup_retires_both_observed_owners_before_normal_sdk_teardown(self):
        self.cleaned();self.observe(self.actor)
        with patch.object(self.f.adapter,'_script_feature',return_value=self.primary):
            self.assertEqual({'cleaned':True},self.f.adapter.cleanup(bound.SELECTOR))
        self.assertFalse(self.f.native.running);self.assertIsNone(self.primary.store.read())
        self.assertTrue(all(store.read() is None for store in self.primary._retirement_paths()))

    def test_separate_publisher_worker_acquires_its_own_facts_and_stops_after_original_retirement(self):
        import script_observer
        self.cleaned()
        def factory(selector,run,*,role,client):
            self.assertEqual('actor',role);self.assertEqual(self.server.actor_token,client.token)
            return PhoneScriptFeature(self.f.adapter,selector,ScriptFixtureReader(client,run,epoch_ms=self.epoch),
                role=role,monotonic=lambda:self.clock,sleep=self.sleep)
        sleeps=[0]
        def sleep(value):
            self.sleep(value);sleeps[0]+=1
            if sleeps[0]==1:self.close_fixture()
        config=dict(target=bound.SELECTOR,fixtureUrl=self.client.url,actorToken=self.server.actor_token,durationSeconds=30)
        before=list(self.f.native.inputs)
        with patch.object(self.f.adapter,'_script_feature',side_effect=factory):
            self.assertEqual(0,script_observer.run(self.f.adapter,config,monotonic=lambda:self.clock,sleep=sleep))
        self.assertEqual(before,self.f.native.inputs);self.assertEqual('retired',self.actor.role_state()['phase'])

    def test_publisher_wait_for_an_owned_run_has_a_whole_deadline_and_sends_no_native_requests(self):
        import script_observer
        config=dict(target=bound.SELECTOR,fixtureUrl=self.client.url,actorToken=self.server.actor_token,durationSeconds=30)
        before=len(self.commands)
        with self.assertRaises(NativeUIError):script_observer.run(self.f.adapter,config,monotonic=lambda:self.clock,sleep=self.sleep)
        self.assertEqual(before,len(self.commands));self.assertEqual([],self.f.native.inputs)

    def test_publisher_private_config_rejects_unknown_fields_versions_and_public_permissions(self):
        import script_observer
        from adapters.normal_feature_state import PrivateFeatureState
        store=PrivateFeatureState(self.storage.root.parent/'synthetic-observer.json')
        value=dict(scriptObserverVersion=1,target=bound.SELECTOR,candidateArguments=[],fixtureUrl=self.client.url,
                   actorToken=self.server.actor_token,durationSeconds=30)
        store.write(value,None);self.assertEqual(value,script_observer.configuration(store.path))
        for edit in (dict(scriptObserverVersion=True),dict(readerToken=self.client.token),dict(durationSeconds=1801)):
            changed=value|edit;store.write(changed,store.read())
            with self.assertRaises((ValueError,RuntimeError)):script_observer.configuration(store.path)
        store.write(value,store.read());store.path.chmod(0o644)
        with self.assertRaises(NativeUIError):script_observer.configuration(store.path)
        store.path.chmod(0o600)


if __name__=='__main__':unittest.main()
