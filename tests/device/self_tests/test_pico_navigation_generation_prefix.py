"""Fifteen continuous normal actions with explicit Qt/VM/OS/GPU host seams.

The first eleven, actual controlled TLS replies, original PNG owners, durable
SDK restart and both G1 roles execute. This is no headset, native scene/pixel,
public feature, or complete Journey cleanup qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sys
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.request import Request
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.graphics_source import PicoGraphicsSource
from adapters.pico4.navigation_generation import compose,history
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import unpack
from adapters.pico4.tablet_home import PicoHomeSource
from adapters.token_places_ui import sha
from feature_journeys.scenarios import SCENARIOS,expand,VERSION as CONTRACT_VERSION
from feature_journeys.fixtures import context
from feature_journeys.navigation_fixture import DIRECTORY,QUERY
from self_tests import test_pico_navigation_restart_prefix as original
from self_tests import test_pico_navigation_prefix as prefix
from self_tests.test_pico_tablet_home import original as home_original
from self_tests.test_pico_openxr_adapter_session import FakeTransport


class Model(original.Model):
    """One modeled OS clock; new widgets/script acquire their own original IDs."""
    def __init__(self,root):
        self.os_clock=[0.];self.g1=False;self.g1_root=None;self.native_consumptions=[]
        super().__init__(root)
    @property
    def clock(self):return self.os_clock[0]
    @clock.setter
    def clock(self,value):self.os_clock[0]=value
    def raw(self):
        value=super().raw()
        if self.g1 and self.g1_root is not None:
            for row in value['controls']:
                if row['id']=='places.page':row['rootInstance']=self.g1_root
        return value
    def source_read(self,request):
        super().source_read(request)
        if self.g1_root is not None:
            for row in self.source_packet['roots']:row['rootId']=self.g1_root
    def private(self,request,kind):
        super().private(request,kind)
        if self.g1_root is not None and kind=='panels':
            for row in self.native_packets[kind]['roots']:row['rootId']=self.g1_root
    def send(self,command):
        if not self.g1:return super().send(command)
        parent=PrivateFeatureState(self.root/'navigation-prefix-generation-1-parent.json').read()
        from adapters.script_journey.history import unpack
        need(parent is not None and unpack(parent['payload'])[0]['phase']=='acting')
        opening=command['controlId']=='places.entry'
        if opening:
            need(self.shown and not self.page);self.g1_root=uuid.uuid4().hex
        result=super().send(command)
        if opening:
            # Actual modeled READY_FOR_CONTENT runs the same original initial
            # transmitPortalList/fetchMetaverse HTTP path; no desired rows are
            # installed from the shared recipe or its expected state.
            with self.owner_test.opener.open(Request(self.network+DIRECTORY+'?'+QUERY,
                    headers={'Cache-Control':'no-cache'}),timeout=2) as response:
                raw=response.read();receipt=response.headers['X-Overte-Fixture-Response']
            first=len(self.messages);self.received(raw,receipt,origin=self.network)
            for row in self.messages[first:]:
                row['targetRootId']=self.g1_root
                if row['deliveredRootId'] is not None:row['deliveredRootId']=self.g1_root
        if opening and getattr(self,'lose_entry',False):raise NativeUIError('Synthetic applied G1 Entry response lost')
        if command['controlId'].startswith('places.bookmark.delete.') and getattr(self,'lose_delete',False):
            raise NativeUIError('Synthetic applied G1 Delete response lost')
        return result
    def consume_controller(self,envelope):
        if not self.g1:return super().consume_controller(envelope)
        try:
            if envelope['commands'][0]['operation']=='tablet.open':
                self.controller_calls.append(deepcopy(envelope));self.shown=True;self.generation=str(uuid.uuid4());return
            return super().consume_controller(envelope)
        finally:
            if any(row==envelope for row in self.controller_calls):
                self.native_consumptions.append(dict(envelope=deepcopy(envelope),transitionEpochMs=self.epoch()))



@unittest.skipUnless(shutil.which('openssl'),'Existing ephemeral TLS fixture requires OpenSSL')
class NavigationGenerationPrefixTests(unittest.TestCase):
    model_type=Model
    process_start='10001'
    setUpClass=classmethod(original.NavigationRestartPrefixTests.setUpClass.__func__)
    tearDownClass=classmethod(original.NavigationRestartPrefixTests.tearDownClass.__func__)
    setUp=original.NavigationRestartPrefixTests.setUp
    make=original.NavigationRestartPrefixTests.make
    write=original.NavigationRestartPrefixTests.write
    read=original.NavigationRestartPrefixTests.read
    installed=original.NavigationRestartPrefixTests.installed
    activate=original.NavigationRestartPrefixTests.activate
    target_fingerprint=original.NavigationRestartPrefixTests.target_fingerprint
    first_eleven=original.NavigationRestartPrefixTests.first_eleven
    bind_restart=original.NavigationRestartPrefixTests.bind_restart
    twelve_call=original.NavigationRestartPrefixTests.twelve_call
    native_reader=original.NavigationRestartPrefixTests.native_reader
    successor=original.NavigationRestartPrefixTests.successor

    def launch_receiver(self):
        # All original G0 objects/bytes/clocks remain unchanged. New producer
        # construction shares only the modeled OS clock, not old source DTOs.
        with patch.object(original,'Model',Model):original.NavigationRestartPrefixTests.launch_receiver(self)
        self.new_model.os_clock=self.original_model.os_clock
        self.new_model.provider=self.original_model.provider
        self.new_model.g1=True

    def prepare_generation(self):
        self.first_eleven();continuation,factory=self.bind_restart();actor=original.NavigationContinuation(self.original_actor,factory)
        continuation.act(self.twelve_call());continuation.observe();actor.observe()
        self.assertFalse(self.original_model.alive)
        self.model=self.new_model;self.world=self.new_world;self.flow=continuation
        self.runtime= self.successor(continuation.restart().inputs,continuation.restart().state)
        m=self.model;self.ui_status=None;self.ui_command=None
        self.home_sequence=0;self.home_birth=uuid.uuid4().hex;self.tablet_birth=uuid.uuid4().hex;self.button_birth=uuid.uuid4().hex
        self.graphics_birth=uuid.uuid4().hex;self.graphics_generation=uuid.uuid4().hex
        source=self.runtime['source'];native=self.native_reader()
        self.native_status_reads=0
        def native_status(*,expected_nonce=None,expected_sequence=None):
            # FakeTransport's global list index is not a per-native-birth
            # cursor. Keep every old envelope, but read only actual consumed
            # records of this live new process and exact requested nonce.
            m.guard();need(self.current_identity=='32:10002')
            consumed=[row for row in m.native_consumptions if row['envelope']['sessionNonce']==expected_nonce]
            need(consumed and [row['envelope']['sequence'] for row in consumed]==list(range(1,len(consumed)+1)))
            sequence=len(consumed) if expected_sequence is None else expected_sequence
            need(type(sequence) is int and 1<=sequence<=len(consumed))
            actual=FakeTransport.read_status(SimpleNamespace(envelopes=[row['envelope'] for row in consumed]),
                expected_nonce=expected_nonce,expected_sequence=expected_sequence)
            actual['updatedEpochMs']=consumed[sequence-1]['transitionEpochMs']
            path=self.root/f'navigation-prefix-generation-1-controller-status-{self.native_status_reads:03d}.json'
            self.native_status_reads+=1
            PrivateFeatureState(path).write(dict(processIdentity=self.current_identity,status=deepcopy(actual)),None)
            return actual
        self.xr.read_status=native_status
        installed=dict(schemaVersion=1,installedCandidateVerified=True,
            **{key:self.binding[key] for key in ('sourceRevision','artifactSha256')})
        home_native=None
        def write(target,package,path,raw):
            nonlocal home_native
            need((target,package)==('owned-model','org.overte.pico'))
            if path.endswith('tablet-home-observation-command.json'):
                request=json.loads(raw);self.home_sequence+=1
                home_native=home_original()|dict(commandId=request['commandId'],processId=32,instance=self.home_birth,generation=self.home_birth,
                    tabletId=self.tablet_birth,parentId=self.tablet_birth,homeId=self.button_birth,sourceSequence=self.home_sequence,
                    elapsedMs=100+round(m.clock*1000),capturedEpochMs=m.epoch(),tabletShown=m.shown,onHomeScreen=not m.login and not m.page)
                return
            self.ui_command=raw;command=json.loads(raw)
            self.ui_status,_epoch=m.send(command)
        def read(target,package,path,**_options):
            need((target,package)==('owned-model','org.overte.pico'))
            if path.endswith('tablet-home-observation.json'):return json.dumps(home_native)
            if path.endswith('observation.json'):return json.dumps(m.raw())
            if path.endswith('status.json'):return json.dumps(self.ui_status)
            return self.ui_command
        def identity(_target):need(self.running and self.current_identity=='32:10002');return self.current_identity
        def same_process(_target,process,_why):need(identity(_target)==process);return m.guard()
        self.adapter=SimpleNamespace(pico_configuration=self.scope_configuration,
            _installation=lambda _target:deepcopy(installed),require_controlled_debug_identity=identity,
            require_pico_session_identity=identity,require_same_process=same_process,require=lambda _target:True,
            pico_input_session=lambda _target:self.session,probe_retry_policy=lambda:(1,0),
            _native_feature_observer=lambda _target:self.native_reader(),_process_presence=lambda _target:self.kernel.reader(),
            _feature_observer=lambda _target:SimpleNamespace(read=lambda _after:need(False)),
            adb=SimpleNamespace(write_debug_app_file=write,read_debug_app_file=read,
                epoch_milliseconds=lambda _target:m.epoch(),foreground_package=lambda _target:'org.overte.pico'),
            read_probe_snapshot=lambda _target,_package,after:source.arrival.probe(after),
            _graphics_subject_observer=lambda _target:source.arrival.subject,
            _location_bookmarks=lambda _target:source.readers['bookmarks'],_navigation_panels=lambda _target:source.readers['panels'],
            _navigation_environment=lambda _target:source.readers['environment'],_navigation_modals=lambda _target:source.readers['modals'],
            _navigation_directory_source=lambda _target:source.readers['directory'],_navigation_replies=lambda _target:source.readers['replies'])
        boundary=self.world.ui;previous=boundary.write
        def graphics_write(*args):
            boundary.clock=m.clock;boundary.epoch=m.epoch();boundary.shown=m.shown;return previous(*args)
        boundary.write=graphics_write
        boundary.edit=lambda packet:packet.update(processId=32,instance=self.graphics_birth,generation=self.graphics_generation)
        def graphics(_target):
            actual=SimpleNamespace(guard=m.guard,clock_ms=m.epoch,pid=32,monotonic=lambda:m.clock,sleep=m.sleep)
            return PicoGraphicsSource(SimpleNamespace(adb=SimpleNamespace(write_debug_app_file=boundary.write,read_debug_app_file=boundary.read)),
                'synthetic',actual)
        self.adapter._graphics_ui_observer=graphics
        self.environment=patch.dict('os.environ',dict(OVERTE_PICO_NORMAL_SCRIPTS='1',OVERTE_ANDROID_E2E_DEBUG='1',
            OVERTE_PICO_OPENXR_INPUT='1',OVERTE_E2E_SCENE_URL=prefix.INPUTS['sceneUrl']))
        self.environment.start();self.addCleanup(self.environment.stop)
        with self.lock.held():
            self.flow=compose(self.adapter,'owned-model',self.original_parent)
            self.actor=compose(self.adapter,'owned-model',self.original_actor)
        return self.flow

    def cold_generation(self):
        parent=self.original_parent
        with self.lock.held():
            archived=history(self.root,prefix.RUN,parent.phase,self.lock,role='primary',status=parent.source.status,
                provider_instance=parent.source.provider_instance,inputs=parent.source.inputs,origin=self.url,profile=parent.source.profile)
            self.flow=compose(self.adapter,'owned-model',archived)
        return self.flow

    def actions(self,stop):
        self.prepare_generation()
        for index in range(12,stop):self.flow.act(self.next_call(index))

    def source_counts(self):
        m=self.model
        return dict(native=self.new_native.sequence,bookmarks=m.native_sequence,environmentDirectory=m.source_sequence,
            panelsModals=dict(m.native_counters),replies=m.modal.replies.sequence,pose=self.world.probe_sequence,subject=self.world.subject.sequence)

    def next_call(self,index):
        row=SCENARIOS['world-navigation']['steps'][index];inputs=expand(row['inputs'],context(prefix.RUN));ticket=uuid.uuid4().hex
        self.server.journal.activate(prefix.RUN,ticket,row['verb'],inputs);self.model.provider.activate(prefix.RUN,ticket)
        return dict(contractVersion=CONTRACT_VERSION,runId=prefix.RUN,fixtureUrl=self.url+'/feature-fixture/v1/runs/'+prefix.RUN+'/',
            ticket=ticket,verb=row['verb'],inputs=inputs)

    def test_continuous_fifteen_original_restart_places_delete_home_close_and_both_g1_roles(self):
        self.prepare_generation()
        for index in range(12,15):
            call=self.next_call(index)
            try:
                self.flow.act(call);actual=self.flow.observe();peer=self.actor.observe()
            except Exception as error:
                errors=[];current=error
                while current is not None and len(errors)<12:
                    detail=''.join(traceback.format_exception(type(current),current,current.__traceback__,chain=False))
                    errors.append(dict(type=type(current).__name__,traceback=detail));print(detail,flush=True);current=current.__context__
                PrivateFeatureState(self.root/'navigation-prefix-generation-1-inner-failure.json').write(dict(index=index,errors=errors),None)
                raise
            expected=expand(SCENARIOS['world-navigation']['steps'][index]['state'],context(prefix.RUN))
            self.assertEqual(expected,{key:actual['state'][key] for key in expected})
            self.assertEqual(actual['state'],peer['state']);self.assertEqual(actual['sequence'],peer['sequence'])
        owner=self.flow.generation_owner
        self.assertEqual(['open','bookmark-delete','close'],[row['verb'] for row in owner.state['completed']])
        self.assertEqual(2,len(self.sdk_calls));self.assertFalse(self.model.shown);self.assertFalse(self.model.page)
        self.assertEqual(self.original_prefix,self.original_parent.store.path.read_bytes())
        self.assertEqual(self.original_ui,original.read_original(self.original_parent.source.normal.io.original.navigation.path))
        self.assertEqual(['tablet.open','input.primary','tablet.close'],[row['commands'][0]['operation'] for row in self.model.controller_calls])
        self.assertEqual(3,owner.close_owner.close_owner().disk['navigationTabletCloseVersion'])
        self.assertTrue(owner.close_owner.close_owner().state['quiet']);self.assertFalse(actual['fullNavigationRecipe'])

    def test_cold_lost_applied_entry_adopts_original_new_page_without_second_entry_or_open(self):
        self.prepare_generation();call=self.next_call(12);self.model.lose_entry=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        before=deepcopy(self.model.calls);envelopes=deepcopy(self.xr.envelopes);root=self.model.g1_root
        self.assertTrue(self.model.page);self.assertEqual(1,len(self.model.reads))
        self.model.lose_entry=False;cold=self.cold_generation();cold.act(call);actual=cold.observe()
        self.assertTrue(actual['state']['panel']);self.assertTrue(actual['state']['bookmark'])
        self.assertEqual(before,self.model.calls);self.assertEqual(envelopes,self.xr.envelopes);self.assertEqual(root,self.model.g1_root)
        self.assertEqual(2,len(self.sdk_calls));self.assertEqual(self.original_prefix,self.original_parent.store.path.read_bytes())

    def test_cold_lost_applied_delete_finishes_actual_storage_quiet_and_normal_tab_zero_once(self):
        self.actions(13);call=self.next_call(13);self.model.lose_delete=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        before=deepcopy(self.model.calls);envelopes=deepcopy(self.xr.envelopes)
        self.assertNotIn(context(prefix.RUN)['renamed'],json.loads(self.model.disk.read_text()))
        self.model.lose_delete=False;cold=self.cold_generation();cold.act(call);actual=cold.observe()
        self.assertFalse(actual['state']['bookmark']);self.assertTrue(actual['state']['panel'])
        self.assertEqual(before+[self.model.calls[-1]],self.model.calls);self.assertEqual('places.tab.0',self.model.calls[-1]['controlId'])
        self.assertEqual(envelopes,self.xr.envelopes);self.assertEqual(2,len(self.sdk_calls))
        self.assertEqual(self.original_prefix,self.original_parent.store.path.read_bytes())

    def test_retained_actual_g1_page_blocks_close_and_cold_never_repeats_home(self):
        self.actions(14);call=self.next_call(14);self.model.retain_root=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        before=deepcopy(self.xr.envelopes);self.assertTrue(self.model.shown);self.assertFalse(self.model.page);self.assertFalse(self.model.root_dead)
        self.assertEqual(['tablet.open','input.primary'],[row['commands'][0]['operation'] for row in self.model.controller_calls])
        cold=self.cold_generation()
        with self.assertRaises(NativeUIError):cold.act(call)
        self.assertEqual(before,self.xr.envelopes);self.assertTrue(self.model.shown);self.assertEqual(2,len(self.sdk_calls))

    def test_phase_advance_after_actual_parent_qml_cas_prevents_g1_entry_writer(self):
        self.prepare_generation();call=self.next_call(12);write=PrivateFeatureState.write;changed=[]
        def landed(store,value,previous):
            result=write(store,value,previous)
            if store.path==self.root/'navigation-prefix-generation-1-parent.json' and not changed:
                row=unpack(value['payload'])[0]
                if row['qml'] and row['qml'][-1]['controlId']=='places.entry':
                    changed.append(True);self.next_call(13)
            return result
        with patch.object(PrivateFeatureState,'write',landed):
            with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertTrue(changed);self.assertEqual([],self.model.calls);self.assertEqual([],self.model.reads)
        self.assertFalse(self.model.page);self.assertEqual(1,len(self.model.controller_calls))
        state=unpack(PrivateFeatureState(self.root/'navigation-prefix-generation-1-open.json').read()['payload'])[0]
        self.assertEqual('places.entry',state['pending']['controlId']);self.assertEqual('entry',state['phase'])

    def test_actual_g1_native_clock_regression_after_real_outer_exit_refuses_without_new_frame(self):
        self.actions(13);owner=self.flow.generation_owner;runtime=owner.runtime;native=runtime['native'];clock=native.clock_ms
        original_held=self.lock.held;changed=[];samples=self.root/'navigation-prefix-generation-1-primary-sources.json'
        before=len(PrivateFeatureState(samples).read()['chunks']);counts=[];host=self.model.clock
        @contextmanager
        def released():
            with original_held():yield
            value=PrivateFeatureState(samples).read()
            if value is not None and value['phase']=='ready' and len(value['chunks'])==before+1 and not changed:
                self.assertIsNone(self.lock._owner);changed.append(True);counts.append(self.source_counts())
                native.clock_ms=lambda:clock()-2000
                PrivateFeatureState(self.root/'navigation-prefix-generation-1-final-native-clock.json').write(dict(
                    outerReleased=True,nativeEpochMs=native.clock_ms(),phaseEpochMs=self.original_parent.phase.epoch_ms(),hostMonotonic=self.model.clock),None)
        with patch.object(self.lock,'held',released):
            with self.assertRaises(NativeUIError):self.flow.observe()
        self.assertTrue(changed);self.assertEqual(host,self.model.clock);self.assertEqual(counts[0],self.source_counts())
        self.assertEqual(before+1,len(PrivateFeatureState(samples).read()['chunks']));self.assertEqual(2,len(self.sdk_calls))

    def test_missing_original_open_owner_refuses_cold_delete_before_new_source_or_input(self):
        self.actions(13);call=self.next_call(13);before=self.source_counts();commands=deepcopy(self.model.calls)
        original_path=self.root/'navigation-prefix-generation-1-open.json';retained=self.root/'retained-synthetic-original-open.json'
        original_path.rename(retained)
        cold=self.cold_generation()
        with self.assertRaises(NativeUIError):cold.act(call)
        self.assertEqual(before,self.source_counts());self.assertEqual(commands,self.model.calls)
        self.assertTrue(retained.is_file());self.assertEqual(2,len(self.sdk_calls))


if __name__=='__main__':unittest.main()
