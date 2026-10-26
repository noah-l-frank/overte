"""Actual editor/OS ownership codecs and CAS; native/SDK boundaries modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.appium_adapter import AppiumAdapter
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.lifecycle_background import LifecycleBackground,LifecycleOSContext,os_original
from ios.adapters.lifecycle_background_runtime import IOSLifecycleBackgroundRuntime
from ios.adapters.lifecycle_originals import IOSLifecycleSources
from ios.self_tests.test_ios_lifecycle_editors import EditorDomain
from ios.self_tests.test_ios_keyboard_runtime import KeyboardRuntimeTests


class Host:
    def __init__(self):self.time=0.
    def mono(self):return self.time
    def epoch(self):return 1800000000000+self.time*1000
    def sleep(self,seconds):self.time+=seconds


class BackgroundDomain:
    def __init__(self,case):
        self.d=EditorDomain(case);self.f=self.d.f.f.f;self.host=Host();self.inputs=[];self.fault=None;self.block_native=False;self.native_queries=[]
        self.lifecycle=dict(backgrounds=0,activations=1,launches=1)
        prior=self.f.clock.mutate
        def clock(packet):prior(packet);packet['lifecycle']=deepcopy(self.lifecycle)
        self.f.clock.mutate=clock
        self.d.flow.open('create');self.d.flow.back('create');self.d.flow.open('chat');self.d.flow.type('chat','reply-'+self.d.source.run)
        self.runtime=IOSScriptRuntime(self.f.adapter);client=self.d.source.source['client'];previous=client.execute
        def execute(session,operation,values):
            if operation=='mobile: queryAppState':return 4 if self.f.process and self.f.process['foreground'] else 3
            if operation in ('mobile: backgroundApp','mobile: activateApp'):
                self.inputs.append(operation)
                state=PrivateFeatureState(self.d.root/'ios-lifecycle-background.json').read()['state']
                case.assertEqual('background-issued' if operation.endswith('backgroundApp') else 'foreground-issued',state['phase'])
                if operation=='mobile: backgroundApp':
                    if self.fault!='ignored-home':
                        self.f.process['foreground']=False;self.lifecycle['backgrounds']+=1
                        self.d.current()['focused']=False;self.d.f.f.p.k.b.notify('did-hide',valid=False)
                else:
                    if self.fault!='ignored-activation':self.f.process['foreground']=True;self.lifecycle['activations']+=1
                    if self.fault=='restart':self.lifecycle['launches']+=1
                    if self.fault=='native-counters':self.lifecycle.update(backgrounds=0,activations=1)
                    if self.fault=='draft-lost':
                        import hashlib
                        self.d.current().update(text='',textSha256=hashlib.sha256(b'').hexdigest(),textCodeUnits=0)
                    if self.fault=='focus-retained':self.d.current()['focused']=True;self.d.f.f.p.k.b.notify('did-show',valid=True,intersects=True)
                if self.fault==('lost-home' if operation.endswith('backgroundApp') else 'lost-activation'):raise OSError('Declared lost normal OS return')
                return True
            if operation=='mobile: pullFile':
                case.assertTrue(self.f.process['foreground'],'Background recovery must not make a native/UI AFC read')
                self.native_queries.append(values['remotePath'])
                if self.block_native:raise AssertionError('Historical recovery unexpectedly queried native/UI source')
            return previous(session,operation,values)
        client.execute=execute
        self.f.adapter.query_app_state=AppiumAdapter.query_app_state.__get__(self.f.adapter,type(self.f.adapter))
        self.owner=self.reopen()

    def reopen(self):
        os=LifecycleOSContext(self.runtime,'test-only',self.d.source.binding)
        def sources():return IOSLifecycleSources(self.runtime._sources('test-only'),self.d.source.run,
            epoch_ms=self.host.epoch,monotonic=self.host.mono)
        self.owner=LifecycleBackground(PrivateFeatureState(self.d.root/'ios-lifecycle-background.json'),self.d.f.store,
            os,self.d.source.run,self.d.lock,sources,epoch_ms=self.host.epoch,monotonic=self.host.mono,sleep=self.host.sleep)
        return self.owner


class LifecycleBackgroundTests(unittest.TestCase):
    def setUp(self):self.b=BackgroundDomain(self)

    def test_normal_chat_draft_keyboard_and_generation_survive_original_os_resume(self):
        b=self.b;before=(b.f.sessions,b.f.launches);result=b.owner.act();self.assertTrue(result['historical'])
        self.assertEqual(['mobile: backgroundApp','mobile: activateApp'],b.inputs);self.assertEqual(before,(b.f.sessions,b.f.launches))
        history=b.owner.history();actual=history.historical_editor(result['originalAfter'])
        self.assertEqual(dict(editor='chat',text='reply-'+b.d.source.run,focused=False,generation=2,keyboard=False),actual)
        self.assertEqual('observed',b.owner.state['phase']);b.reopen().act();self.assertEqual(2,len(b.inputs))
        changed=deepcopy(b.owner.previous);changed['state']['afterReference']['sha256']='f'*64
        with self.assertRaises(NativeUIError):b.owner.decode(changed)

    def test_lost_home_recovers_in_background_with_no_native_read_or_repeated_home(self):
        b=self.b;b.fault='lost-home'
        with self.assertRaises(OSError):b.owner.act()
        self.assertFalse(b.f.process['foreground']);before=len(b.native_queries);b.block_native=True;b.reopen()
        self.assertEqual(before,len(b.native_queries));b.block_native=False;b.fault=None;b.owner.act()
        self.assertEqual(['mobile: backgroundApp','mobile: activateApp'],b.inputs)

    def test_lost_activation_recovers_without_another_activation_or_session(self):
        b=self.b;b.fault='lost-activation';before=(b.f.sessions,b.f.launches)
        with self.assertRaises(OSError):b.owner.act()
        self.assertTrue(b.f.process['foreground']);b.fault=None;b.reopen().act()
        self.assertEqual(['mobile: backgroundApp','mobile: activateApp'],b.inputs);self.assertEqual(before,(b.f.sessions,b.f.launches))

    def test_ignored_home_keeps_issued_intent_without_activation_or_resend(self):
        b=self.b;b.fault='ignored-home'
        with self.assertRaises(NativeUIError):b.owner.act()
        with self.assertRaises(NativeUIError):b.reopen().act()
        self.assertEqual(['mobile: backgroundApp'],b.inputs);self.assertEqual('background-issued',b.owner.state['phase'])

    def test_ignored_activation_keeps_background_without_native_reads_or_resend(self):
        b=self.b;b.fault='ignored-activation'
        with self.assertRaises(NativeUIError):b.owner.act()
        before=len(b.native_queries);b.block_native=True
        with self.assertRaises(NativeUIError):b.reopen().act()
        self.assertEqual(before,len(b.native_queries));self.assertEqual(['mobile: backgroundApp','mobile: activateApp'],b.inputs)

    def test_os_ack_cannot_replace_native_counters_retained_draft_or_released_focus(self):
        b=self.b;b.fault='native-counters'
        with self.assertRaises(NativeUIError):b.owner.act()
        self.assertEqual('foreground-issued',b.owner.state['phase']);self.assertIsNone(b.owner.state['after'])
        self.assertEqual(['mobile: backgroundApp','mobile: activateApp'],b.inputs)

    def test_actual_draft_loss_cannot_be_replaced_by_the_requested_reply(self):
        b=self.b;b.fault='draft-lost'
        with self.assertRaises(NativeUIError):b.owner.act()
        self.assertEqual('',b.d.current()['text']);self.assertIsNone(b.owner.state['after'])

    def test_retained_keyboard_focus_is_not_a_completed_background_resume(self):
        b=self.b;b.fault='focus-retained'
        with self.assertRaises(NativeUIError):b.owner.act()
        self.assertTrue(b.d.current()['focused']);self.assertIsNone(b.owner.state['after'])

    def test_changed_original_process_prevents_background_recovery_activation(self):
        b=self.b;b.fault='lost-home'
        with self.assertRaises(OSError):b.owner.act()
        before=len(b.native_queries);saved=b.owner.store.path.read_bytes();b.f.process['pid']=43
        with self.assertRaises((ValueError,NativeUIError)):b.reopen()
        self.assertEqual(before,len(b.native_queries));self.assertEqual(saved,b.owner.store.path.read_bytes())
        self.assertEqual(['mobile: backgroundApp'],b.inputs)

    def test_saved_after_original_recovers_without_native_query_or_another_os_input(self):
        from adapters.original_frame_store import OriginalFrameStore
        b=self.b;write=OriginalFrameStore.write;saved={}
        def interrupted(store,index,value):
            result=write(store,index,value)
            if store.namespace=='lifecycle-editor' and b.lifecycle['activations']==2:
                path=store.path(store.expand(result));saved.update(path=path,inode=path.stat().st_ino,body=path.read_bytes())
                raise OSError('Declared lost return after real original save and before history append')
            return result
        with patch.object(OriginalFrameStore,'write',interrupted):
            with self.assertRaises(OSError):b.owner.act()
        self.assertTrue(saved);count=len(b.native_queries);b.block_native=True;b.reopen().act()
        self.assertEqual(count,len(b.native_queries));self.assertEqual(saved['inode'],saved['path'].stat().st_ino)
        self.assertEqual(saved['body'],saved['path'].read_bytes());self.assertEqual(2,len(b.inputs))

    def test_canonical_recovery_factory_stays_os_only_while_backgrounded(self):
        b=self.b;b.fault='lost-home'
        with self.assertRaises(OSError):b.owner.act()
        before=len(b.native_queries);b.block_native=True
        owner=IOSLifecycleBackgroundRuntime(b.f.adapter).owner('test-only',b.d.source.run,b.d.lock,
            epoch_ms=b.host.epoch,monotonic=b.host.mono,sleep=b.host.sleep)
        self.assertEqual('background-issued',owner.state['phase']);self.assertEqual(before,len(b.native_queries))
        b.block_native=False;b.fault=None;owner.act();self.assertEqual(2,len(b.inputs))

    def test_existing_editor_flow_continues_to_scripts_after_canonical_background_child(self):
        b=self.b;runtime=IOSLifecycleBackgroundRuntime(b.f.adapter);before=(b.f.sessions,b.f.launches)
        result=runtime.resume_chat('test-only',b.d.flow,epoch_ms=b.host.epoch,monotonic=b.host.mono,sleep=b.host.sleep);self.assertTrue(result['historical'])
        b.d.flow.open('scripts');measured=b.d.flow.history.historical_editor(len(b.d.flow.history.state['frames']))
        self.assertEqual('scripts',measured['editor']);self.assertEqual(3,measured['generation'])
        self.assertEqual(before,(b.f.sessions,b.f.launches));self.assertEqual(2,len(b.inputs))
        native=len(b.native_queries);b.block_native=True;historical=b.reopen().act()
        self.assertEqual(result,historical);self.assertEqual(native,len(b.native_queries));self.assertEqual(2,len(b.inputs))

    def test_failed_durable_intent_prevents_home_and_preserves_editor(self):
        b=self.b
        with patch.object(b.owner.store,'write',side_effect=OSError('Declared failed original OS intent CAS')):
            with self.assertRaises(OSError):b.owner.act()
        self.assertEqual([],b.inputs);self.assertTrue(b.d.current()['focused']);self.assertTrue(b.f.process['foreground'])

    def test_os_original_rejects_foreign_source_pid_boolean_appstate_and_clock_domain_faults(self):
        b=self.b;value=b.owner.status()
        for mutate in (lambda v:v['process'].update(pid=43),lambda v:v['source'].update(instance='e'*32),
            lambda v:v.update(appState=True),lambda v:v['hostAfter'].update(monotonic=6)):
            bad=deepcopy(value);mutate(bad)
            with self.subTest(mutate=mutate),self.assertRaises((ValueError,NativeUIError)):os_original(bad,b.owner.binding,b.owner.os.gate.bundle)
        self.assertEqual([],b.inputs)


class LifecycleBackgroundRuntimeTests(unittest.TestCase):
    def test_factory_preserves_existing_candidate_and_never_creates_sdk_or_launch(self):
        k=KeyboardRuntimeTests();k.setUp();self.addCleanup(k.doCleanups);f=k.f;before=(f.sessions,f.launches)
        with f.adapter._lifecycle_background_runtime().background('test-only','a'*32) as owner:
            self.assertIsInstance(owner,LifecycleBackground);owner.file_guard()
        self.assertEqual(before,(f.sessions,f.launches))
        with self.assertRaises((ValueError,RuntimeError)):owner.file_guard()
