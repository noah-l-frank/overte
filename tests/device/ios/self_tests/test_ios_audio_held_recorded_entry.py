"""Real held Audio owner reentry and ordinary Installed refusal; host models.

Actual SDK/source/candidate guards, private WALs and original byte parsers run.
No full Audio capability, native execution, acoustic/peer or resource end.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import threading
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import VERSION
from ios.adapters.audio_session_owners import register_scope,ensure_released
from ios.self_tests.audio_background_domain import AudioBackgroundDomain


class AudioHeldRecordedEntryTests(unittest.TestCase):
    def domain(self):
        b=AudioBackgroundDomain(self,pages=True,prepare_recording=False);p=b.parent
        p.close_evidence=lambda owner:b.runtime.close_recording_evidence('test-only',owner)
        register_scope(b.runtime.adapter,'test-only',p.binding,p.run,p.root)
        b.m.add_phase('open','3'*32)
        return b

    @staticmethod
    def call(b):
        p=b.parent
        return dict(contractVersion=VERSION,runId=p.run,fixtureUrl=p.fixture_url,
            ticket=b.m.ticket,verb=b.m.active_verb,inputs=deepcopy(b.m.activations[-1]['stimulus']['inputs']))

    @staticmethod
    def inputs(b):return deepcopy((b.m.actions,b.m.page_model.actions,b.inputs))

    @staticmethod
    def audio_files(b):
        return {path:path.read_bytes() for path in b.root.iterdir()
            if path.is_file() and path.name.startswith('ios-audio-')}

    def invoke(self,b):return b.runtime.normal_act('test-only',b.parent,self.call(b))

    def test_same_held_owner_reentry_uses_original_native_effect_but_never_opens_ordinary_Installed_entry(self):
        b=self.domain();result=self.invoke(b);self.assertTrue(result['state']['open'])
        self.assertEqual('audio',b.m.page_model.route);originals=self.audio_files(b);inputs=self.inputs(b)
        repeated=self.invoke(b);self.assertTrue(repeated['state']['open']);self.assertEqual(inputs,self.inputs(b))
        self.assertEqual(originals.keys(),self.audio_files(b).keys() & originals.keys())
        # Fresh current observation files may append; the original action's
        # actual bytes stay identical and no page/input is repeated.
        self.assertTrue(all(path.read_bytes()==body for path,body in originals.items() if 'recorded-owner.json' not in path.name))
        calls=deepcopy((b.f.commands,b.f.process,b.f.adapter.read_session('test-only')))
        for ordinary in (lambda:ensure_released(b.runtime.adapter,'test-only'),
            lambda:b.f.adapter.describe('test-only'),lambda:b.f.adapter.invoke('test-only','app.stop',{}),
            lambda:b.f.adapter.cleanup('test-only')):
            with self.assertRaises(NativeUIError):ordinary()
            self.assertEqual(calls,(b.f.commands,b.f.process,b.f.adapter.read_session('test-only')))
        self.assertEqual(inputs,self.inputs(b))

    def test_foreign_scope_refuses_before_native_input_without_replacing_that_original(self):
        b=self.domain();scope=PrivateFeatureState(b.root/'ios-audio-scope.json');value=scope.read()
        wrong=deepcopy(value);wrong['runId']='a'*32;scope.write(wrong,value)
        before=self.inputs(b);reads=b.reads
        with self.assertRaises(NativeUIError):self.invoke(b)
        self.assertEqual(before,self.inputs(b));self.assertEqual(reads,b.reads);self.assertEqual(wrong,scope.read())
        self.assertIsNone(b.parent.store.read())

    def test_changed_current_parent_WAL_is_not_adopted_by_same_live_owner(self):
        b=self.domain();self.invoke(b);old=b.parent.store.read();wrong=deepcopy(old);wrong['runId']='a'*32
        b.parent.store.write(wrong,old);before=self.inputs(b)
        with self.assertRaises(NativeUIError):self.invoke(b)
        self.assertEqual(before,self.inputs(b));self.assertEqual(wrong,b.parent.store.read())
        self.assertEqual(old,b.parent.previous)

    def test_unowned_Settings_responsibility_with_matching_run_and_binding_is_not_a_membership_grant(self):
        b=self.domain();self.invoke(b);before=self.inputs(b)
        foreign=PrivateFeatureState(b.root/'ios-audio-settings-restore.json')
        value=dict(runId=b.parent.run,binding=deepcopy(b.parent.binding),responsibility='unparsed Settings')
        foreign.write(value,None)
        with self.assertRaises(NativeUIError):self.invoke(b)
        self.assertEqual(before,self.inputs(b));self.assertEqual(value,foreign.read())

    def test_changed_original_frame_body_is_refused_even_while_parent_WAL_and_input_ticket_match(self):
        b=self.domain();self.invoke(b);p=b.parent;header=p.store.path.read_bytes()
        reference=p.state['records'][0];path=p.frames.path(p.frames.expand(reference));raw=bytearray(path.read_bytes())
        raw[len(raw)//2]=ord('x') if raw[len(raw)//2]!=ord('x') else ord('y');path.write_bytes(bytes(raw))
        before=self.inputs(b)
        with self.assertRaises((NativeUIError,ValueError)):self.invoke(b)
        self.assertEqual(before,self.inputs(b));self.assertEqual(header,p.store.path.read_bytes())
        self.assertEqual(bytes(raw),path.read_bytes())

    def test_actual_current_SDK_process_change_refuses_same_owner_before_another_page_input(self):
        b=self.domain();before=self.inputs(b);originals=self.audio_files(b)
        b.f.process['pid']+=1
        with self.assertRaises((NativeUIError,RuntimeError,ValueError)):self.invoke(b)
        self.assertEqual(before,self.inputs(b));self.assertEqual(originals,self.audio_files(b))
        self.assertIsNone(b.parent.store.read())

    def test_same_object_in_another_thread_cannot_borrow_original_source_lock_or_enter_normal_input(self):
        b=self.domain();errors=[];before=self.inputs(b)
        def foreign_thread():
            try:self.invoke(b)
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=foreign_thread,name='declared-foreign-owner-thread');thread.start();thread.join(timeout=2)
        self.assertFalse(thread.is_alive());self.assertEqual(1,len(errors));self.assertIsInstance(errors[0],NativeUIError)
        self.assertEqual(before,self.inputs(b));self.assertIsNone(b.parent.store.read())


if __name__=='__main__':unittest.main()
