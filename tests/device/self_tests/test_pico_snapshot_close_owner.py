"""Normal control/Session close with original host lineage; native/SDK seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation import NavigationError
from adapters.pico4.snapshot_close_owner import PicoSnapshotCloseOwner
from adapters.pico4.snapshot_cancel_owner import PicoSnapshotCancelOwner
from adapters.pico4.snapshot import PicoSnapshot,MODES,FORMATS
from adapters.pico4.navigation import PicoNavigation,NativeNavigationIO
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from self_tests.test_pico_openxr_adapter_session import FakeTransport
from self_tests.test_pico_snapshot_return_image import ReturnBoundary


class CloseBoundary:
    def __init__(self,root):
        self.m=ReturnBoundary(root);self.image=self.m.owner();self.image.acquire();self.b=self.m.b
        self.commands=[];self.last_sequence=self.b.origin['base']['ui']['lastCommandSequence'];self.popup=None
        self.open=True;self.generation=self.b.origin['base']['ui']['generation'];self.mode=self.b.origin['base']['ui']['picoSnapshotReview']['review']['mode']
        self.format=self.b.origin['base']['ui']['picoSnapshotReview']['review']['format'];self.status={};self.ignore=False;self.lose=False
        self.closed_generation=None;self.live_owner=None;self.publish_delay=0;source_frame=self.b.frame
        def frame():
            value=source_frame();ui=value['base']['ui'];ui.update(open=self.open,ready=self.open,generation=self.generation,lastCommandSequence=self.last_sequence,elapsedMs=round(self.b.host*1000))
            ui['picoSnapshotReview']['review'].update(mode=self.mode,format=self.format)
            if not self.open:ui['controls']=[]
            elif self.popup:
                choices=MODES if self.popup=='mode' else FORMATS
                for index,name in enumerate(choices):
                    ui['controls'].append(dict(id='snapshot.'+self.popup+'.'+name,token=str(uuid.uuid5(uuid.NAMESPACE_URL,self.popup+name)),enabled=True,focused=False,
                        checked=self.mode==index if self.popup=='mode' else self.format==name))
            return value
        self.frame=frame;self.b.parent.read_frame=frame
        native=self.b.parent.native;native.pid=123;native.monotonic=lambda:self.b.host;native.sleep=self.b.sleep
        native.guard=self.b.native_guard
        b=self.b;test=self
        class Transport(FakeTransport):
            def stage(self,envelope,profile,*,before_publish=None):
                if before_publish:
                    b.host+=test.publish_delay
                    with patch.object(test.live_owner.source,'status',side_effect=AssertionError('Phase IO under publication')),patch.object(test.live_owner.store,'read',side_effect=AssertionError('File IO under publication')),patch.object(native,'guard',side_effect=AssertionError('Native guard under publication')):
                        before_publish(deepcopy(envelope));before_publish(deepcopy(envelope))
                self.envelopes.append(deepcopy(envelope));self.sent.append(deepcopy(envelope))
                if not test.ignore:
                    test.open=False;test.generation=str(uuid.uuid4());test.closed_generation=test.generation
                if test.lose=='controller-stage':raise OSError('Explicit lost consumed controller response')
                return dict(sequence=envelope['sequence'])
            def read_status(self,**kwargs):
                if test.lose=='controller-ack' and kwargs.get('expected_sequence') is not None:
                    test.lose=False;raise OSError('Explicit lost acknowledgement after actual Session cursor commit')
                return dict(super().read_status(**kwargs),updatedEpochMs=b.epoch())
        self.transport=Transport();self.transport.sent=[];self.session=PicoOpenXrAdapterSession(self.transport,'synthetic-close-owner',root)
        # Seed the actual private Session file with the archived model's
        # original nonce/cursor. This test setup is not a production adoption.
        original=self.b.states['snapshot-cancel'];historical=[row['command'] for row in original['deliveries'] if row['kind']=='controller']
        cursor=deepcopy(original['sessionOrigin']);cursor['nextSequence']+=len(historical)
        with self.session._lock():self.session._save(cursor)
        self.transport.envelopes.extend(deepcopy(historical))
        def read_debug(_target,_package,path,**options):
            if path.endswith('observation.json'):return json.dumps(frame()['base']['ui'])
            if path.endswith('status.json'):return json.dumps(self.status)
            raise AssertionError('Unknown explicit normal input path')
        def write_debug(_target,_package,path,raw):
            command=json.loads(raw);self.commands.append(deepcopy(command));self.last_sequence=command['sequence']
            if not self.ignore:
                control=command['controlId'];parts=control.split('.')
                if len(parts)==2:self.popup=parts[-1]
                else:
                    if parts[1]=='mode':self.mode=MODES.index(parts[2])
                    else:self.format=parts[2]
                    self.popup=None
            self.status=dict(schemaVersion=1,bridgeId=b.binding['sessionId'],commandId=command['commandId'],sequence=command['sequence'],performed=True,error='',processId=123,updatedEpochMs=b.epoch())
            if self.lose=='qml':self.lose=False;raise OSError('Explicit lost original QML response after actual model consumption')
        adapter=SimpleNamespace(require=lambda target:None,require_same_process=lambda *args:None,require_pico_session_identity=lambda target:b.binding['processIdentity'],
            _installation=lambda target:None,pico_input_session=lambda target:self.session,probe_retry_policy=lambda:(1,0),
            adb=SimpleNamespace(foreground_package=lambda target:'org.overte.pico',read_debug_app_file=read_debug,write_debug_app_file=write_debug,epoch_milliseconds=lambda target:b.epoch()))
        io=NativeNavigationIO(adapter,'synthetic-close-owner',b.binding['processIdentity'],lambda operation:None)
        identity=dict(schemaVersion=1,installedCandidateVerified=True,sourceRevision=b.binding['sourceRevision'],artifactSha256=b.binding['artifactSha256'])
        ui=PicoNavigation(io,root/'close-test-navigation.json',identity,b.binding['processIdentity'],'https://snapshot.invalid/scene.json',monotonic=lambda:b.host,sleep=b.sleep)
        ui._mark(frame()['base']['ui'],True);snapshot=PicoSnapshot(ui,SimpleNamespace(artifacts=self.m.images),root/'close-test-preference.json')
        # The old warm fixture does not contain its separate preference file.
        # Reconstruct only this test header from its actual original checked
        # delegates. Production construction never creates a missing baseline.
        original=self.b.states['snapshot-cancel'];values={}
        for field,options in (('mode',MODES),('format',FORMATS)):
            for delivery in original['deliveries']:
                control=delivery['command'].get('controlId','')
                if delivery['stage']=='open-issued' and control.startswith('snapshot.'+field+'.'):
                    value=control.rsplit('.',1)[-1];choice=ui.control(original['frames'][delivery['frame']]['ui'],control)
                    if choice and choice['checked']:values[field]=value
        snapshot.mark(originalMode=values['mode'],originalFormat=values['format'])
        base=object.__new__(PicoSnapshotCancelOwner);base.lock=b.lock;base.binding=b.binding;base.snapshot=snapshot;base.native=native;base.session=self.session
        base.state=deepcopy(original);base.close_owner=None;base.save_owner=None;base.current=False
        base.qml_callback=base.before_qml;base.controller_callback=base.before_controller;base.intent_callback=base.controller_intent;base.publish_callback=base.before_publish
        io.bind_before_send(base.qml_callback);io.bind_controller_admission(base.controller_callback,intent=base.intent_callback,before_publish=base.publish_callback)
        self.b.parent.base=base;self.base=base
        phase=self.b.phase;phase['activations'].append(dict(sequence=len(phase['activations'])+1,ticket=uuid.uuid4().hex,activatedEpochMs=b.epoch(),stimulus=dict(verb='close',inputs={})))
    def owner(self,*,cold=False):
        if cold:
            base=object.__new__(PicoSnapshotCancelOwner);base.__dict__.update(self.base.__dict__);base.close_owner=None
            self.b.parent.base=base;self.base=base;io=base.snapshot.ui.io
            # A new cold NativeNavigationIO binds its exact receiver once.
            old=io;io=NativeNavigationIO(old.adapter,old.target,old.identity,old._controller)
            base.snapshot.ui.io=io;base.qml_callback=base.before_qml;base.controller_callback=base.before_controller;base.intent_callback=base.controller_intent;base.publish_callback=base.before_publish
            io.bind_before_send(base.qml_callback);io.bind_controller_admission(base.controller_callback,intent=base.intent_callback,before_publish=base.publish_callback)
        value=PicoSnapshotCloseOwner(self.image,self.b.root/'snapshot-close-owner.json');self.live_owner=value;return value


class SnapshotCloseCase(unittest.TestCase):
    def model(self):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-close-host-');self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700);return CloseBoundary(root)


class SnapshotCloseOwnerTests(SnapshotCloseCase):
    def test_normal_original_mode_format_controls_then_controller_close_new_generation_neutral_and_quiet(self):
        m=self.model();owner=m.owner();old=m.image.store.read();owner.prepare();owner.restore();self.assertTrue(owner.report()['checkedModeFormatRestored'])
        owner.close();result=owner.quiet();self.assertEqual('partial-closed',result['stage']);self.assertTrue(result['tabletClosed']);self.assertTrue(result['originalControllerNeutral'])
        self.assertFalse(result['completeSettingsBaseline']);self.assertFalse(result['qtObjectsRetired']);self.assertFalse(result['fullSnapshotRecipe'])
        self.assertEqual(old,m.image.store.read());self.assertEqual(m.closed_generation,owner.state['closedGeneration']);self.assertNotEqual(m.generation,m.b.origin['base']['ui']['generation'])
        self.assertEqual(['snapshot.mode','snapshot.mode.'+m.base.snapshot.state['originalMode'],'snapshot.format','snapshot.format.'+m.base.snapshot.state['originalFormat']],[row['controlId'] for row in m.commands])
        self.assertEqual(1,len(m.transport.sent));self.assertTrue(m.base.snapshot.path.exists());self.assertTrue(m.base.snapshot.ui.path.exists())
        queries=m.b.queries;reopened=m.owner(cold=True);self.assertEqual('partial-closed',reopened.report()['stage']);self.assertEqual(queries,m.b.queries)
        with m.b.lock.held():
            state=deepcopy(reopened.state);state['quiet'][0]['indices'].pop(1)
            with self.assertRaises(NativeUIError):reopened.validate(state)
            state=deepcopy(reopened.state);state['restoration']=0
            with self.assertRaises(NativeUIError):reopened.validate(state)
            state=deepcopy(reopened.state);state['steps'][1]['before']=0
            with self.assertRaises(NativeUIError):reopened.validate(state)
            state=deepcopy(reopened.state);state['neutrals'][-1]['value']['updatedEpochMs']+=2000;state['neutral']=deepcopy(state['neutrals'][-1]['value'])
            with self.assertRaises(NativeUIError):reopened.validate(state)
            state=deepcopy(reopened.state);state['closedGeneration']=m.b.origin['base']['ui']['generation']
            with self.assertRaises(NativeUIError):reopened.validate(state)
        m.mode=(m.mode+1)%len(MODES)
        with self.assertRaises(NativeUIError):reopened.reconcile()
        self.assertEqual(1,len(m.transport.sent));self.assertTrue(reopened.store.path.exists())


class SnapshotCloseRecoveryTests(SnapshotCloseCase):
    def test_lost_qml_and_controller_ack_reopen_only_reads_effect_then_continues_unissued_actions(self):
        m=self.model();owner=m.owner();owner.prepare();m.lose='qml'
        with self.assertRaises(NativeUIError):owner.restore()
        self.assertEqual(1,len(m.commands));self.assertEqual('restore-issued',owner.state['stage'])
        cold=m.owner(cold=True);self.assertEqual('prepared',cold.reconcile()['stage']);cold.restore()
        self.assertEqual(['snapshot.mode','snapshot.mode.'+m.base.snapshot.state['originalMode'],'snapshot.format','snapshot.format.'+m.base.snapshot.state['originalFormat']],[row['controlId'] for row in m.commands])
        m.lose='controller-ack'
        with self.assertRaises(NativeUIError):cold.close()
        self.assertEqual('close-issued',cold.state['stage']);queries=m.b.queries;another=m.owner(cold=True)
        self.assertEqual(queries,m.b.queries);save=another.save
        def interrupted(state,**options):
            if state['stage']=='closed':raise OSError('Explicit interruption after durable original closed/neutral frame')
            return save(state,**options)
        with patch.object(another,'save',side_effect=interrupted),self.assertRaises(NativeUIError):another.reconcile()
        self.assertEqual('close-issued',another.state['stage']);self.assertTrue(another.state['neutrals']);another=m.owner(cold=True)
        self.assertEqual('closed',another.reconcile()['stage']);self.assertEqual(1,len(m.transport.sent))
        with self.assertRaises(NativeUIError):another.close()
        self.assertEqual(1,len(m.transport.sent));self.assertTrue(another.store.path.exists())


    def test_consumed_controller_ack_without_original_closed_ui_stays_owned_and_is_not_repeated(self):
        m=self.model();owner=m.owner();owner.prepare();owner.restore();m.ignore=True
        with self.assertRaises(NativeUIError):owner.close()
        cold=m.owner(cold=True)
        with self.assertRaises(NativeUIError):cold.reconcile()
        with self.assertRaises(NativeUIError):cold.close()
        with self.assertRaises(NativeUIError):cold.quiet()
        self.assertEqual(1,len(m.transport.sent));self.assertTrue(m.open);self.assertEqual('close-issued',cold.state['stage'])
        self.assertFalse(cold.report()['tabletClosed']);self.assertTrue(cold.store.path.exists())


class SnapshotCloseFenceTests(SnapshotCloseCase):
    def test_ack_without_qml_effect_keeps_unknown_action_and_never_resends(self):
        m=self.model();owner=m.owner();owner.prepare();m.ignore=True
        with self.assertRaises(NativeUIError):owner.restore()
        cold=m.owner(cold=True)
        with self.assertRaises(NativeUIError):cold.reconcile()
        with self.assertRaises(NativeUIError):cold.restore()
        self.assertEqual(1,len(m.commands));self.assertEqual([],m.transport.sent);self.assertEqual('restore-issued',cold.state['stage']);self.assertTrue(cold.store.path.exists())

    def test_exact_phase_after_last_native_guard_refuses_controller_close(self):
        m=self.model();owner=m.owner();owner.prepare();owner.restore();guard=m.base.native.guard
        def changed():
            if owner.state['stage']=='close-issued':
                rows=m.b.phase['activations'];rows.append(dict(sequence=len(rows)+1,ticket=uuid.uuid4().hex,activatedEpochMs=m.b.epoch(),stimulus=dict(verb='cleanup',inputs={})))
            return guard()
        with patch.object(m.base.native,'guard',side_effect=changed),self.assertRaises(NativeUIError):owner.close()
        self.assertEqual([],m.transport.sent);self.assertEqual('close-issued',owner.state['stage']);self.assertIsNone(owner.state['controller']['envelope'])
        with self.assertRaises(NativeUIError):owner.close()
        self.assertTrue(owner.store.path.exists())

    def test_frozen_native_clock_slow_actual_transport_refuses_publish_without_retry(self):
        m=self.model();owner=m.owner();owner.prepare();owner.restore();epoch=m.b.epoch();m.publish_delay=2
        with patch.object(m.base.native,'clock_ms',return_value=epoch),patch.object(m.b.source,'epoch_ms',return_value=epoch),self.assertRaises(NativeUIError):owner.close()
        self.assertEqual([],m.transport.sent);self.assertEqual('close-issued',owner.state['stage']);self.assertIsNotNone(owner.state['controller']['envelope'])
        cold=m.owner(cold=True)
        with self.assertRaises(NativeUIError):cold.reconcile()
        self.assertEqual([],m.transport.sent);self.assertTrue(cold.store.path.exists())


if __name__=='__main__':unittest.main()

