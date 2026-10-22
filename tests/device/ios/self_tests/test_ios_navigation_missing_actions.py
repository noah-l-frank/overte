"""Real fixture 404/normal codecs/private owners; SDK and native Qt modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
import uuid
from urllib.parse import urlsplit

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_navigation_replies import NativeNavigationReplies
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input
from ios.adapters.navigation_missing_actions import NavigationMissingActions
from ios.self_tests import test_ios_navigation_scene_inputs as scene
from ios.self_tests.test_ios_navigation_dialogs import Boundary as Dialogs
from ios.self_tests.test_ios_navigation_world_measurements import global_packet
from feature_journeys.fixtures import context


class Native(NativeFeatureObservation):
    def __init__(self,h):
        self.h=h;self.ios=True;self.pid=42;self.sequence=2;self.guard=lambda:h.h.h.okay
    def read(self,after):
        self.h.tick();self.sequence+=1;value=global_packet(self.h.epoch(),self.sequence)
        value['requestId']='ios-'+uuid.uuid4().hex;return value


class Replies(NativeNavigationReplies):
    def __init__(self,h):self.h=h;self.sequence=0;self.pid=42;self.ios=True
    def read(self,run):
        self.h.tick();self.sequence+=1
        value=dict(navigationReplyVersion=1,commandId='ios-'+uuid.uuid4().hex,runId=run,instance='e'*32,
            sequence=self.sequence,processId=42,capturedEpochMs=self.h.epoch(),currentLookupGeneration=2,
            currentLookupActive=True,events=[] if self.h.dialogs.native_error is None else [deepcopy(self.h.dialogs.native_error)])
        return value


class NavigationMissingActionsTests(unittest.TestCase):
    def setUp(self):
        self.h=scene.NavigationSceneInputsTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.admission,self.b=self.h.admission,self.h.b;self.tick(10)
        self.dialogs=Dialogs();self.dialogs.epoch=self.epoch
        with self.held():proof=self.admission.archive()
        self.dialogs.sequence=proof['originals']['dialogs']['sequence']
        self.dialogs.clock=proof['originals']['dialogs']['clockAfter']['monotonicMs']/1000+.002
        self.admission.native=Native(self);self.admission.sources['dialogs']=self.dialogs.reader()
        self.admission.sources['replies']=Replies(self);self.admission.sources['ui']=self.h.native
        self.admission.sources['replies'].sequence=proof['originals']['replies']['sequence']
        self.ui_counter=100;self.ignored=False;self.ignore_ok=False;self.partial_destroy=False
        self.original_ui=self.b.observed
        def observed():
            self.tick();value=self.original_ui();self.ui_counter+=1
            value.update(elapsedMs=round(self.b.clock*1000)+100000,navigationDialogControlsVersion=1,
                navigationDialogSourceSequence=self.ui_counter,navigationInventory=dict(iosNavigationUiInventoryVersion=1,
                    complete=True,roots=deepcopy(value['navigationInventory']['roots'])))
            if self.dialogs.rows and self.dialogs.rows[0]['dialog'] is not None:
                value['controls'] += [dict(row,frame=dict(x=1,y=1,width=100,height=20)) for row in self.dialogs.controls()['controls']]
            return value
        self.b.observed=observed
        self.original_call=self.b.call
        def call(method,path,body=None):
            if method=='POST' and path.endswith('/click'):
                name=self.b.by_reference[path.split('/element/',1)[1].split('/')[0]]
                if name=='PhoneAddressGoButton':
                    old=self.b.mutation;self.b.mutation='goto-ignored'
                    try:result=self.original_call(method,path,body)
                    finally:self.b.mutation=old
                    if not self.ignored:
                        harness=self.h.h.fixture.harness
                        status,_raw,response=harness.get('/api/v1/places/'+context(self.admission.run)['hidden'])
                        self.assertEqual(404,status);self.tick(2)
                        src=urlsplit(self.admission.fixture.inputs['sceneUrl']);self.dialogs.create(response,origin=src.scheme+'://'+src.netloc)
                    return result
            return self.original_call(method,path,body)
        self.b.call=call
        self.original_post=self.b.post
        def post(request,timeout):
            result=self.original_post(request,timeout);query=json.loads(request.data)
            receipt=self.b.native_boundary.receipt
            receipt['observation' if 'observation' in receipt else 'status']['sampleEpochMs']=self.epoch()
            if query['operation']=='edit' and query['input']['operation']=='activate':
                if not self.ignore_ok:
                    self.dialogs.respond();self.dialogs.destroy(listener=not self.partial_destroy);self.tick(2)
            return result
        self.post=patch.object(normal_input,'urlopen',post);self.post.start();self.addCleanup(self.post.stop)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=self.admission.run):
            self.assertEqual(self.admission.run,self.h.h.fixture.harness.open())
    @contextmanager
    def held(self):
        caught=None
        with self.h.h.lock.held():
            try:yield
            except Exception as error:caught=error
        if caught is not None:raise caught
    def tick(self,count=1):self.h.h.ms+=count
    def epoch(self):return self.h.native_epoch()
    def owner(self):
        return NavigationMissingActions(PrivateFeatureState(self.h.h.root/'ios-navigation-missing-actions.json'),
            self.admission,self.b.ui,self.h.native,epoch_ms=self.h.h.epoch,monotonic=self.h.h.mono)
    def call(self,verb):
        ticket=uuid.uuid4().hex;self.h.h.fixture.harness.client.activate(ticket,verb,{})
        return dict(contractVersion=16,runId=self.admission.run,ticket=ticket,verb=verb,inputs={},fixtureUrl=self.admission.fixture.fixture_url)

    def test_normal_missing_uses_actual_hifi_name_and_independent_404_then_real_ok_and_destruction(self):
        with self.held():
            owner=self.owner();call=self.call('navigate-missing');self.assertEqual({'performed':True},owner.navigate(call))
            proof=owner.observe_missing();self.assertEqual(404,proof['joined']['nativeError']['httpStatus'])
            self.assertEqual('hifi://'+context(self.admission.run)['hidden'],self.b.field)
            before=list(self.b.inputs);self.assertEqual({'performed':True},self.owner().navigate(call));self.assertEqual(before,self.b.inputs)
            owner=self.owner();owner.dismiss(self.call('dismiss-error'));cleared=owner.observe_cleared()
            self.assertTrue(cleared['ownedDialogDrained']);self.assertEqual('none',cleared['fields']['error'])
            self.assertIsNotNone(owner.store.read());self.assertIsNotNone(owner.state['proof'])

    def test_retained_missing_root_and_actual_native_command_are_required_in_original_carrier(self):
        from adapters.script_feature.history import pack,unpack
        with self.held():
            owner=self.owner();owner.navigate(self.call('navigate-missing'))
            original=owner.state['addressOwner'];child=unpack(original['payload'])[0]
            self.assertEqual('missing',child['rows'][-1]['key']);self.assertFalse(child['rows'][-1]['closed']['drained'])
            command=child['rows'][-1]['intents'][2]
            self.assertEqual(command['intent']['command']['commandId'],command['receipt']['status']['commandId'])
            self.assertEqual('hifi://'+context(self.admission.run)['hidden'],command['intent']['command']['text'])
            before=list(self.b.inputs);state=deepcopy(owner.state);state['addressOwner']=None
            with self.assertRaises(NativeUIError):owner.decode(owner.envelope(state))
            state=deepcopy(owner.state);carrier=state['addressOwner'];rows=unpack(carrier['payload'])
            rows[0]['rows'][-1]['intents'][2]['receipt']['status']['commandId']=str(uuid.uuid4())
            carrier['payload']=pack(rows)
            with self.assertRaises(NativeUIError):owner.decode(owner.envelope(state))
            self.assertEqual(before,self.b.inputs)

    def test_lost_go_return_keeps_original_address_owner_issued_and_observes_root_without_replay(self):
        from ios.adapters.navigation_address_inputs import NavigationAddressInputs
        with self.held():
            original=self.b.call
            def lost(method,path,body=None):
                value=original(method,path,body)
                if method=='POST' and path.endswith('/click') and self.b.by_reference[path.split('/element/',1)[1].split('/')[0]]=='PhoneAddressGoButton':
                    raise OSError('Synthetic original Go return loss')
                return value
            self.b.call=lost;owner=self.owner();call=self.call('navigate-missing')
            with self.assertRaises(NativeUIError):owner.navigate(call)
            rebuilt=self.owner();self.assertEqual('issued',rebuilt.state['missing']['phase'])
            self.assertIsNone(rebuilt.state['addressOwner']);before=list(self.b.inputs)
            child=NavigationAddressInputs(PrivateFeatureState(self.h.h.root/'ios-navigation-address-42-inputs.json'),
                owner.binding,owner.run,owner.lock,lambda:True,self.b.ui,self.h.native,epoch_ms=self.h.h.epoch,monotonic=self.h.h.mono)
            self.assertEqual('issued',child.state['rows'][-1]['phase'])
            self.assertEqual('retained',child.observe_pending()['root']['status'])
            with self.assertRaises(NativeUIError):rebuilt.navigate(call)
            self.assertEqual(before,self.b.inputs)

    def test_version_one_carrier_stays_unchanged_without_claiming_new_root_ownership(self):
        with self.held():
            owner=self.owner();owner.version=1;owner.navigate(self.call('navigate-missing'))
            actual=deepcopy(owner.store.read());before=list(self.b.inputs);again=self.owner()
            self.assertEqual(1,actual['iosNavigationMissingActionsVersion']);self.assertEqual(actual,again.store.read())
            self.assertNotIn('addressOwner',again.state);self.assertEqual(before,self.b.inputs)

    def test_ignored_missing_input_ack_cannot_generate_modal_proof(self):
        with self.held():
            self.ignored=True;owner=self.owner();owner.navigate(self.call('navigate-missing'))
            self.assertIsNone(owner.observe_missing());self.assertIsNone(owner.state['proof'])
            with self.assertRaises(NativeUIError):owner.dismiss(self.call('dismiss-error'))

    def test_wrong_response_or_undestroyed_listener_is_not_cleared(self):
        with self.held():
            owner=self.owner();owner.navigate(self.call('navigate-missing'));owner.observe_missing();self.partial_destroy=True
            owner.dismiss(self.call('dismiss-error'))
            with self.assertRaises(NativeUIError):owner.observe_cleared()
            self.assertIsNone(owner.state['cleared']);self.dialogs.destroy(dialog=False,listener=True)
            self.assertTrue(owner.observe_cleared()['ownedDialogDrained'])

    def test_lost_input_return_remains_issued_and_never_reexecutes_native_or_w3c_input(self):
        with self.held():
            owner=self.owner();original=self.b.call
            def lost(method,path,body=None):
                value=original(method,path,body)
                if path.endswith('/click'):raise OSError('Synthetic return loss')
                return value
            self.b.call=lost;call=self.call('navigate-missing')
            with self.assertRaises(NativeUIError):owner.navigate(call)
            again=self.owner();before=list(self.b.inputs)
            with self.assertRaises(NativeUIError):again.navigate(call)
            self.assertEqual(before,self.b.inputs);self.assertEqual('issued',again.state['missing']['phase'])

    def test_unowned_modal_or_changed_provider_cannot_be_adopted_before_input(self):
        with self.held():
            self.dialogs.foreign=1;owner=self.owner()
            with self.assertRaises(NativeUIError):owner.navigate(self.call('navigate-missing'))
            self.assertEqual([],self.b.inputs)

    def test_lost_proof_result_recovers_the_same_original_without_reading_or_sending_again(self):
        with self.held():
            owner=self.owner();owner.navigate(self.call('navigate-missing'));write=owner.store.write
            def lose(value,previous):
                from adapters.script_feature.history import unpack
                if unpack(value['payload'])[0]['proof'] is not None:raise OSError('Synthetic proof result loss')
                write(value,previous)
            owner.store.write=lose
            with self.assertRaises(OSError):owner.observe_missing()
            again=self.owner();retained=deepcopy(again.state['frames'][-1]);before=list(self.b.inputs)
            again.admission.native.read=lambda *_:self.fail('Recovery read a new native clock')
            again.admission.fixture.status=lambda:self.fail('Recovery read new HTTP state')
            proof=again.recover_missing();self.assertEqual(retained['originals'],proof['originals'])
            self.assertEqual(retained['clockJoin'],proof['clockJoin']);self.assertEqual(before,self.b.inputs)

    def test_lost_ok_return_can_be_observed_drained_without_resending_the_native_input(self):
        with self.held():
            owner=self.owner();owner.navigate(self.call('navigate-missing'));owner.observe_missing()
            deliver=self.h.native.navigation_error_input
            def lost(**options):deliver(**options);raise OSError('Synthetic lost OK return')
            self.h.native.navigation_error_input=lost;call=self.call('dismiss-error')
            with self.assertRaises(OSError):owner.dismiss(call)
            again=self.owner();self.assertEqual('issued',again.state['dismiss']['phase'])
            count=len(self.b.native_boundary.requests)
            with self.assertRaises(NativeUIError):again.dismiss(call)
            cleared=again.observe_cleared();self.assertTrue(cleared['ownedDialogDrained'])
            self.assertGreater(len(self.b.native_boundary.requests),count)
            before=deepcopy(again.store.read());again.admission.native.read=lambda *_:self.fail('Cached drainage read a new clock')
            self.assertEqual(cleared,again.observe_cleared());self.assertEqual(before,again.store.read())

    def test_partial_source_read_retains_the_original_prefix_and_refuses_a_replacement_read(self):
        with self.held():
            owner=self.owner();owner.navigate(self.call('navigate-missing'))
            self.admission.sources['replies'].read=lambda *_:(_ for _ in ()).throw(OSError('Synthetic missing source return'))
            with self.assertRaises(OSError):owner.observe_missing()
            again=self.owner();row=again.state['frames'][-1];self.assertEqual({'dialogs'},set(row['originals']))
            self.assertIsNotNone(row['nativeStart']);self.assertIsNone(row['clockJoin']);before=list(self.b.inputs)
            with self.assertRaises(NativeUIError):again.observe_missing()
            with self.assertRaises(NativeUIError):again.recover_missing()
            self.assertEqual(before,self.b.inputs)

    def test_original_ui_counter_rollback_is_rejected_before_owned_ok_input(self):
        with self.held():
            owner=self.owner();owner.navigate(self.call('navigate-missing'));owner.observe_missing()
            self.ui_counter=0;before=len(self.b.native_boundary.requests)
            with self.assertRaises(NativeUIError):owner.dismiss(self.call('dismiss-error'))
            edits=[row for row in self.b.native_boundary.requests[before:] if row['operation']=='edit']
            self.assertEqual([],edits)
