"""Real Create facade/owners with synthetic target IO and separate host actor.

The actual native private-file header is compiled. The common v17 Journey and
HTTP witness run unchanged. This does not execute an Android client or device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from create_feature_target import Target,Proxy,Handler,POLICY,RUN,DOMAIN,epoch,ROOT
import test_create_files as native_files
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.engine import Journey
from overte_phone_create_feature import PhoneCreateFeature
from overte_phone_create_role import PhoneCreateRole
from overte_phone_script_history import unpack,pack

ACTOR=r'''
import json,sys,time
from pathlib import Path
sys.path[:0]=json.loads(sys.argv[1])
from create_feature_target import Proxy,RUN
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.witness import Client
from feature_journeys.phase_fixture import PhaseFixtureReader
from overte_phone_create_feature import PhoneCreateFeature
from overte_phone_create_actor import PhoneCreateActor
from overte_phone_script_lock import PhoneScriptSourceBusy
config=PrivateFeatureState(Path(sys.argv[2])).read();adapter=Proxy(config['targetUrl'],config['root'])
client=Client(config['fixtureUrl'],config['actorToken'])
metadata=PrivateFeatureState(adapter.state_path('synthetic').with_name('phone-create-feature.json')).read()
flow=PhoneCreateActor(PhoneCreateFeature(adapter,'synthetic',PhaseFixtureReader(client,RUN,'create',epoch_ms=adapter.clock_ms),metadata['configuration'],role='actor'))
started=time.monotonic()
while time.monotonic()-started<180:
    try:
        if flow.step():sys.exit(0)
    except PhoneScriptSourceBusy:pass
    except Exception as error:
        import traceback
        context=error.__context__
        while context is not None:
            traceback.print_exception(type(context),context,context.__traceback__,chain=False)
            context=context.__context__
        raise
    time.sleep(.25)
raise RuntimeError('Synthetic actor lifetime exceeded')
'''


class CreateFeatureHarness:
    @classmethod
    def setUpClass(cls):
        native_files.CreateFilesTests.setUpClass();cls.executable=native_files.CreateFilesTests.executable
    @classmethod
    def tearDownClass(cls):native_files.CreateFilesTests.tearDownClass()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='create-facade-');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.files=native_files.NativeFiles(self.executable,self.root);self.addCleanup(self.files.close)
        self.target=Target(self.root,self.files);self.addCleanup(self.target.close)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.target=self.target;self.server.errors=[]
        thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        def close_target():self.server.shutdown();self.server.server_close();thread.join(2)
        self.addCleanup(close_target)
        self.url='http://127.0.0.1:'+str(self.server.server_port);self.adapter=Proxy(self.url,self.root)
        self.fixture=make_server('r'*64,'a'*64,adapter_token='b'*64);self.fixture.journal.clock=self.adapter.clock_ms
        thread2=threading.Thread(target=self.fixture.serve_forever,daemon=True);thread2.start()
        def close_fixture():self.fixture.shutdown();self.fixture.server_close();thread2.join(2)
        self.addCleanup(close_fixture)
        self.base='http://127.0.0.1:'+str(self.fixture.server_port)+'/feature-fixture/v1'
        self.client=Client(self.base,'r'*64)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):_run,_url=self.client.register('create');self.context=dict(fixtureUrl=_url)
        self.target.fixture=self.context['fixtureUrl']
        self.config=dict(createFeatureVersion=1,artifactRoot=str(self.root),imageExtent=[1000,750],markerRoi=[20,20,180,60],imagePolicy=POLICY,
            domainId=DOMAIN,permissionsControlUrl=self.url+'/v1/create-permissions',permissionsControlToken='z'*64)
        self.primary=self.feature();self.actor=None
    def feature(self):return PhoneCreateFeature(self.adapter,'synthetic',PhaseFixtureReader(Client(self.base,'b'*64),RUN,'create',epoch_ms=self.adapter.clock_ms),self.config)
    def call(self,verb,inputs=None):
        ticket=os.urandom(16).hex();inputs={} if inputs is None else inputs;self.client.activate(ticket,verb,inputs)
        self.target.ticket=ticket
        return dict(contractVersion=18,runId=RUN,fixtureUrl=self.context['fixtureUrl'],ticket=ticket,verb=verb,inputs=inputs)
    def observe(self,after=0):return self.feature().observe(dict(contractVersion=18,runId=RUN,afterSequence=after))
    def start_actor(self):
        path=self.root/'actor-test-configuration.json';PrivateFeatureState(path).write(dict(targetUrl=self.url,root=str(self.root),fixtureUrl=self.base,actorToken='a'*64),None)
        self.actor=subprocess.Popen([sys.executable,'-c',ACTOR,json.dumps(sys.path),str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        def close():
            if self.actor.poll() is None:self.actor.terminate()
            self.actor.communicate(timeout=5)
        self.addCleanup(close)
    def actor_ok(self):
        if self.actor is not None and self.actor.poll() is not None:
            out,err=self.actor.communicate();self.fail('Synthetic actor stopped: '+str(self.actor.returncode)+' '+err[-6000:])


class CreateFeatureTests(CreateFeatureHarness,unittest.TestCase):
    def test_baseline_reconstruction_acquires_fresh_originals_and_never_prepares_files(self):
        self.call('baseline');a=self.observe();b=self.observe(a['sequence'])
        self.assertEqual(1,a['sequence']);self.assertEqual(2,b['sequence']);self.assertEqual([],b['resources']);self.assertFalse(self.files.root.exists())
        self.assertLess(a['capturedEpochMs'],b['capturedEpochMs']);self.assertEqual([],self.target.inputs)


    def prepared(self):
        self.call('baseline');self.observe();self.feature().act(self.call('open'))

    def test_acknowledged_input_does_not_supply_original_model_effect_or_replay(self):
        self.prepared();call=self.call('model-create',dict(resource='gltf-bundle/main.gltf'))
        self.assertEqual({'performed':True},self.feature().act(call));count=len(self.target.inputs)
        self.assertEqual({'performed':True},self.feature().act(call));self.assertEqual(count,len(self.target.inputs))
        self.target.rows[0]['render']['geometry']['sourceSha256']='0'*64
        with self.assertRaises(NativeUIError):self.observe()
        owner=self.feature()
        with owner.lock.held():
            owner.load();role=PhoneCreateRole(owner,'primary');self.assertEqual('reading',role.state['phase'])
        self.call('cleanup');self.feature().cleanup(dict(contractVersion=18,runId=RUN))
        self.assertEqual([],self.target.rows);self.assertFalse(self.files.root.exists())
        self.assertIsNotNone(self.feature().store.read()) # No invented actor retirement.

    def test_ignored_normal_property_apply_never_returns_performed_or_loses_owned_uuid(self):
        self.prepared();self.target.ignore.add('create.apply')
        with self.assertRaises(NativeUIError):self.feature().act(self.call('model-create',dict(resource='gltf-bundle/main.gltf')))
        owner=self.feature()
        with owner.lock.held():owner.load();self.assertEqual(self.target.rows[0]['id'],owner.state['objects'][0]['id'])
        self.call('cleanup');self.feature().cleanup(dict(contractVersion=18,runId=RUN));self.assertEqual([],self.target.rows)

    def test_cleanup_cancels_only_owned_actual_picker_before_restoring_tools_and_files(self):
        self.prepared();self.feature().act(self.call('import-picker-open',dict(resource='entity-import.json')))
        self.assertIsNotNone(self.target.widgets.dialog);self.call('cleanup')
        self.assertEqual({'performed':True},self.feature().cleanup(dict(contractVersion=18,runId=RUN)))
        self.assertIsNone(self.target.widgets.dialog);self.assertFalse(self.files.root.exists())
        self.assertEqual({'performed':True},self.feature().cleanup(dict(contractVersion=18,runId=RUN)))

    def test_lost_original_and_manifest_callbacks_recover_archival_only_then_acquire_new_sources(self):
        self.call('baseline');self.observe()
        for boundary in ('original','manifest'):
            feature=self.feature()
            with feature.lock.held():
                feature.load();role=PhoneCreateRole(feature,'primary');intent=role.originals.intent;sequence=role.state['sequence']
                def lose(kind,value):
                    intent(kind,value)
                    if kind==boundary and value['phase']=='saved':raise NativeUIError('Synthetic lost archive callback')
                role.originals.intent=lose
                with self.assertRaises(NativeUIError):role.read(sequence)
            source_counts=deepcopy(self.target.sequence)
            feature=self.feature()
            with feature.lock.held():
                feature.load();role=PhoneCreateRole(feature,'primary');role.recover()
                self.assertEqual(sequence+1,role.state['sequence']);self.assertEqual(source_counts,self.target.sequence)
                current=role.read(role.state['sequence']);self.assertEqual(sequence+2,current['sequence'])
                self.assertGreater(self.target.sequence['native'],source_counts['native'])

    def test_interrupted_export_archive_resumes_only_exact_owned_prefix_before_native_retirement(self):
        self.prepared();self.feature().act(self.call('model-create',dict(resource='gltf-bundle/main.gltf')))
        feature=self.feature();save=feature.save;lost=[False]
        def lose():
            save()
            if feature.state['export'] is not None and feature.state['export']['phase']=='opened' and not lost[0]:
                lost[0]=True;raise NativeUIError('Synthetic lost opened archive return')
        with patch.object(feature,'save',side_effect=lose),self.assertRaises(NativeUIError):feature.act(self.call('export-selection'))
        self.assertEqual(b'',(self.root/('create-export-'+RUN+'.json')).read_bytes())
        self.call('cleanup');self.feature().cleanup(dict(contractVersion=18,runId=RUN))
        self.assertEqual(0,json.loads((self.root/('create-export-'+RUN+'.json')).read_bytes())['DataVersion'])
        self.assertFalse(self.files.root.exists())

    def test_foreign_export_replacement_cannot_be_overwritten_or_retired_as_owned(self):
        self.prepared();self.feature().act(self.call('model-create',dict(resource='gltf-bundle/main.gltf')))
        self.feature().act(self.call('export-selection'));path=self.root/('create-export-'+RUN+'.json')
        path.rename(path.with_suffix('.retained'));path.write_bytes(b'foreign output');path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.observe()
        self.call('cleanup')
        with self.assertRaises(NativeUIError):self.feature().cleanup(dict(contractVersion=18,runId=RUN))
        self.assertEqual(b'foreign output',path.read_bytes());self.assertIsNotNone(self.feature().store.read())


    def test_foreign_ownership_ledger_changes_fail_before_any_new_source_or_input(self):
        self.prepared();self.feature().act(self.call('model-create',dict(resource='gltf-bundle/main.gltf')))
        store=self.feature().store;original=store.read();state=unpack(original['payload'])[0];state['objects'][0]['instance']='0'*32
        store.write(original|dict(payload=pack([state])),original);count=len(self.target.inputs);sources=deepcopy(self.target.sequence)
        with self.assertRaises(NativeUIError):self.observe()
        self.assertEqual(count,len(self.target.inputs));self.assertEqual(sources,self.target.sequence)

    def test_cell_baseline_is_recovered_from_original_frame_not_mutable_journal_field(self):
        self.prepared();self.feature().act(self.call('voxel-create'));self.observe()
        store=PrivateFeatureState(self.root/'phone-create-primary-originals.json');original=store.read();state=unpack(original['payload'])[0]
        state['baselineVoxel']['voxel']['cells']['occupied']=65;store.write(original|dict(payload=pack([state])),original)
        sources=deepcopy(self.target.sequence)
        with self.assertRaises(NativeUIError):self.observe()
        self.assertEqual(sources,self.target.sequence)

    def test_primary_host_process_cannot_adopt_independent_actor_role(self):
        from overte_phone_create_actor import PhoneCreateActor
        self.call('baseline');self.observe();header=self.feature().store.read()
        feature=PhoneCreateFeature(self.adapter,'synthetic',PhaseFixtureReader(Client(self.base,'a'*64),RUN,'create',epoch_ms=self.adapter.clock_ms),header['configuration'],role='actor')
        with self.assertRaises(NativeUIError):PhoneCreateActor(feature).step()
        self.assertIsNone(PrivateFeatureState(self.root/'phone-create-actor-lifecycle.json').read())

    def test_http_ack_without_backend_entry_keeps_original_actor_pending_and_red(self):
        self.call('baseline');self.observe()
        with patch.object(self.fixture.journal,'publish',return_value=None):
            self.start_actor();out,error=self.actor.communicate(timeout=10)
        self.assertNotEqual(0,self.actor.returncode);header=PrivateFeatureState(self.root/'phone-create-actor-lifecycle.json').read()
        state=unpack(header['payload'])[0];self.assertIsNone(state['last']);self.assertTrue(state['pending']['issued'])
        self.assertEqual([],self.client.observe()['entries']);self.assertEqual('watching',state['phase'])

    def test_interrupted_png_prefix_uses_original_native_memory_before_actual_retirement(self):
        self.prepared();self.feature().act(self.call('model-create',dict(resource='gltf-bundle/main.gltf')))
        feature=self.feature()
        with feature.lock.held():
            feature.load();role=PhoneCreateRole(feature,'primary');intent=role.image_intent
            def lose(value):
                intent(value)
                if value['phase']=='opened':raise NativeUIError('Synthetic interrupted PNG write')
            with patch.object(role,'image_intent',side_effect=lose),self.assertRaises(NativeUIError):role.read(role.state['sequence'])
            image=deepcopy(role.state['pending']['image']);self.assertEqual('opened',image['phase']);self.assertEqual(b'',(self.root/image['name']).read_bytes())
        feature=self.feature()
        with feature.lock.held():
            feature.load();role=PhoneCreateRole(feature,'primary');role.recover();frame=role.frames[-1]
            self.assertTrue(frame['diagnostic']);self.assertEqual('saved',frame['image']['phase']);self.assertTrue((self.root/image['name']).read_bytes().startswith(b'\x89PNG'))
            self.assertIsNotNone(frame['retirement']);self.assertEqual([],list(self.target.world.receipt_root.iterdir()))
            current=role.read(role.state['sequence']);self.assertTrue(current['artifacts'])

    def test_old_originals_stay_red_with_deterministic_target_epoch(self):
        self.call('baseline');self.target.fault='stale-native'
        with self.assertRaises(NativeUIError):self.observe()
        role=PrivateFeatureState(self.root/'phone-create-primary-originals.json').read()
        self.assertEqual(0,unpack(role['payload'])[0]['sequence']);self.assertFalse(self.files.root.exists())

    def test_real_five_second_native_deadline_stays_red_even_when_target_epoch_is_stopped(self):
        self.call('baseline');self.target.fault='slow-native';started=time.monotonic()
        with self.assertRaises(NativeUIError):self.observe()
        self.assertGreaterEqual(time.monotonic()-started,5)
        role=PrivateFeatureState(self.root/'phone-create-primary-originals.json').read()
        self.assertEqual(0,unpack(role['payload'])[0]['sequence']);self.assertFalse(self.files.root.exists())

    def retired_actor(self):
        self.call('baseline');self.observe();self.start_actor();deadline=time.monotonic()+10
        while True:
            header=PrivateFeatureState(self.root/'phone-create-actor-lifecycle.json').read()
            if header is not None and unpack(header['payload'])[0]['last'] is not None:break
            self.actor_ok();self.assertLess(time.monotonic(),deadline);time.sleep(.05)
        self.call('cleanup');self.feature().cleanup(dict(contractVersion=18,runId=RUN));started=time.monotonic()
        while True:
            self.observe();header=PrivateFeatureState(self.root/'phone-create-actor-lifecycle.json').read();state=unpack(header['payload'])[0]
            if state['quiet'] is not None and state['quiet']['complete'] and state['last'] is not None and state['last']['original']['sample']['ticket']==self.client.observe()['ticket'] and time.monotonic()-started>=3:break
            self.actor_ok();self.assertLess(time.monotonic()-started,15);time.sleep(.25)
        self.client.close();out,error=self.actor.communicate(timeout=10);self.assertEqual(0,self.actor.returncode,error[-2000:])

    def test_ignored_or_lost_child_unlink_never_discards_parent_and_exact_resume_is_idempotent(self):
        self.retired_actor();discard=PrivateFeatureState.discard;lost=[False]
        def ignored(store,previous):
            if store.path.name=='phone-create-primary-originals.json':return
            return discard(store,previous)
        with patch.object(PrivateFeatureState,'discard',ignored),self.assertRaises(NativeUIError):self.feature().finalize()
        self.assertIsNotNone(PrivateFeatureState(self.root/'phone-create-retirement.json').read())
        def after_owner_unlink(store,previous):
            result=discard(store,previous)
            if store.path.name=='phone-create-feature.json' and not lost[0]:lost[0]=True;raise NativeUIError('Synthetic lost final owner unlink return')
            return result
        with patch.object(PrivateFeatureState,'discard',after_owner_unlink),self.assertRaises(NativeUIError):self.feature().finalize()
        self.assertIsNone(self.feature().store.read());self.assertIsNotNone(PrivateFeatureState(self.root/'phone-create-retirement.json').read())
        self.assertEqual({'performed':True},self.feature().finalize())
        self.assertIsNone(PrivateFeatureState(self.root/'phone-create-retirement.json').read())


class CreateFeatureJourneyTests(CreateFeatureHarness,unittest.TestCase):
    def test_complete_common_v17_journey_and_original_actor_exit_retire_all_controls(self):
        reports=[];initialized=[False];last_verb=['baseline'];timings=[]
        def invoke(operation,fields):
            if operation.endswith('.act'):last_verb[0]=str(len(timings))+':'+fields['verb']
            started=time.monotonic()
            value=getattr(self.feature(),operation.rsplit('.',1)[1])(fields)
            timings.append((operation.rsplit('.',1)[1],last_verb[0],round(time.monotonic()-started,3),epoch()-value.get('capturedEpochMs',epoch())))
            if operation.endswith('.observe') and not initialized[0]:initialized[0]=True;self.start_actor()
            return value
        def activate(ticket,verb='baseline',inputs=None):
            self.client.activate(ticket,verb,inputs);self.target.ticket=ticket
        def sleep(seconds):self.actor_ok();time.sleep(seconds)
        def witness():self.actor_ok();return self.client.observe()
        journey=Journey('create',RUN,self.context['fixtureUrl'],invoke=invoke,witness=witness,activate=activate,
            read_artifact=lambda name:(self.root/name).read_bytes(),image_policy=dict(screen=POLICY),continuity=lambda *_:None,
            monotonic=time.monotonic,epoch_ms=self.adapter.clock_ms,sleep=sleep,report=reports.append)
        try:journey.execute()
        except Exception:
            print('Synthetic Create journey stopped after '+last_verb[0]+'; timings '+repr(timings[-12:]),file=sys.stderr)
            data=self.client.observe();print('Actor rows '+repr([(r['actorSequence'],epoch()-r['capturedEpochMs'],r['facts']) for r in data['entries'] if r['ticket']==data['ticket']][-4:]),file=sys.stderr)
            self.actor_ok();raise
        self.assertTrue(reports[-1]['sequenceCompleted']);self.assertTrue(reports[-1]['cleanupSucceeded']);self.assertEqual(21,len(reports[-1]['phases'])-2)
        self.client.close();out,err=self.actor.communicate(timeout=10);self.assertEqual(0,self.actor.returncode,err[-6000:])
        self.assertEqual({'performed':True},self.feature().finalize())
        for name in ('feature','primary-originals','actor-originals','actor-lifecycle','files-owner','retirement'):
            self.assertIsNone(PrivateFeatureState(self.root/('phone-create-'+name+'.json')).read())
        self.assertEqual([],self.server.errors);self.assertFalse(self.files.root.exists());self.assertEqual([],self.target.rows)
        self.assertTrue(list(self.root.glob('emote-frame-create-retirement-*.json')))


if __name__=='__main__':unittest.main()
