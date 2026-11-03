"""UI2 reader/relations over explicit weak-object native fixtures; Qt uncompiled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import unittest
import uuid
import weakref

from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_source as ui
from adapters.pico4.lifecycle_field_binding import pending_match
from self_tests import test_pico_lifecycle_source as original
from self_tests import test_pending_commit_owner as pending_fixture

ROOT=Path(__file__).resolve().parents[3]
PHONE='5e8ff8aa19571f5718b982dc47a165b8f22e0dc0'
NATIVE_FILES=('tests/device/native/PicoLifecycleFieldIdentity.h',
    'tests/device/native/PendingFieldCommitOwner.h','tests/device/native/LifecycleUiObservation.h',
    'android/vr/pico/apps/picoInterface/e2e/PicoE2eTabletBridge.cpp')


class Object:
    def __init__(self):self.thread=threading.get_ident()


class Field(Object):
    def __init__(self,window):super().__init__();self.window=weakref.ref(window)


class WeakTripleModel:
    """Declared Python model of the copied Qt helper, never native execution."""
    def __init__(self):self.originals=[];self.thread=threading.get_ident();self.test_script=True
    def identity(self,field,window,context):
        if not self.test_script or threading.get_ident()!=self.thread or any(value is None for value in (field,window,context)):
            return ''
        if any(value.thread!=self.thread for value in (field,window,context)) or field.window() is not window:return ''
        for old_field,old_window,old_context,token in self.originals:
            if old_field() is not None and old_field() is field and old_window() is window and old_context() is context:return token
        if len(self.originals)>=64:return ''
        token=uuid.uuid4().hex;self.originals.append((weakref.ref(field),weakref.ref(window),weakref.ref(context),token));return token


class BoundUi(original.Boundary):
    def __init__(self):
        super().__init__();self.rows=[original.editor(3,'scripts')]
        self.registry=WeakTripleModel();self.window,self.context=Object(),Object();self.field=Field(self.window);self.tokens={}
    def send(self,request):
        super().send(request)
        if self.value is None or request['schemaVersion']!=2:return
        self.value['lifecycleUiVersion']=2
        for row in self.value['source']['editors']:
            live=all(row[key] for key in ('fieldAlive','windowAlive','contextAlive'))
            if live:
                token=self.registry.identity(self.field,self.window,self.context)
                if not token or self.tokens.get(row['id'],token)!=token:self.value=None;return
                self.tokens[row['id']]=token
            token=self.tokens.get(row['id'],'')
            row['fieldBinding']=dict(lifecycleFieldBindingVersion=1,uiFieldId=row['fieldId'],
                pendingFieldToken=token,weakBirth=token,status='linked' if live else 'retired' if token else 'unobserved')
    def bound_source(self,**kwargs):
        return ui.PicoLifecycleSource(self.send,self.read,lambda:20000,lambda:self.alive,123,
            monotonic=lambda:self.clock,sleep=self.sleep,field_bindings=True,**kwargs)
    def pending(self,field=None):
        boundary=pending_fixture.Boundary();boundary.token=self.registry.identity(field or self.field,self.window,self.context)
        return boundary.owner(readonly=True),boundary


class LifecycleFieldBindingTests(unittest.TestCase):
    def setUp(self):
        def stamp(path):
            info=path.lstat();return (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
        self.native_pins={name:(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),stamp(ROOT/name)) for name in NATIVE_FILES}
        def unchanged():
            self.assertEqual(self.native_pins,{name:(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),stamp(ROOT/name)) for name in NATIVE_FILES})
        self.addCleanup(unchanged)

    def test_native_helper_function_is_exact_fixed_phone_reuse_with_pico_gate_and_both_actual_callers(self):
        phone=subprocess.check_output(['git','show',PHONE+':tests/device/native/PhoneLifecycleFieldIdentity.h'],cwd=ROOT,text=True)
        pico=(ROOT/NATIVE_FILES[0]).read_text()
        def body(text,name):return text.split('inline QString '+name,1)[1].split('} // namespace',1)[0]
        self.assertEqual(body(phone,'phoneLifecycleFieldIdentity'),body(pico,'picoLifecycleFieldIdentity'))
        self.assertIn('defined(ANDROID_APP_PICO_INTERFACE)',pico)
        for name in NATIVE_FILES[1:3]:self.assertIn('picoLifecycleFieldIdentity(', (ROOT/name).read_text())
        owner=(ROOT/NATIVE_FILES[1]).read_text()
        self.assertIn('#else\n            result.token = nonce();',owner)
        self.assertLess(owner.index('if (_seen.size() >= 64)'),owner.index('result.token = picoLifecycleFieldIdentity'))

    def test_opt_in_ui2_retains_literal_and_joins_different_original_ids_from_same_weak_triple(self):
        native=BoundUi();source=native.bound_source();packet=source.capture(original.RUN)
        pending,boundary=native.pending();value=pending.read(original.RUN)
        row=ui.current_editor(packet);self.assertNotEqual(row['fieldId'],value['current']['token'])
        self.assertEqual(row['fieldBinding'],pending_match(row,value))
        self.assertEqual(native.read(),source.last_raw);self.assertEqual(2,native.commands[0]['schemaVersion'])
        self.assertEqual(2,source.previous['lifecycleSourceStateVersion']);self.assertEqual(1,len(boundary.commands))

    def test_same_text_selector_or_equal_legacy_fieldid_cannot_replace_actual_shared_object_relation(self):
        native=BoundUi();source=native.bound_source();row=ui.current_editor(source.capture(original.RUN))
        foreign=Field(native.window);reader,boundary=native.pending(foreign);value=reader.read(original.RUN)
        self.assertEqual(row['text'],value['current']['text'])
        with self.assertRaises(NativeUIError):pending_match(row,value)
        forged=deepcopy(value);forged['current']['token']=row['fieldId']
        with self.assertRaises(NativeUIError):pending_match(row,forged)
        self.assertEqual(1,len(boundary.commands));self.assertEqual(1,len(native.commands))

    def test_default_ui1_keeps_original_rows_and_cannot_become_binding1_by_inference(self):
        native=BoundUi();source=native.source();packet=source.capture(original.RUN);row=ui.current_editor(packet)
        self.assertEqual(1,packet['lifecycleUiVersion']);self.assertNotIn('fieldBinding',row)
        reader,_boundary=native.pending();pending=reader.read(original.RUN)
        with self.assertRaises(NativeUIError):pending_match(row,pending)
        self.assertEqual(1,native.commands[0]['schemaVersion'])

    def test_live_mode_or_cold_summary_cannot_switch_after_original_admission(self):
        native=BoundUi();source=native.bound_source();source.capture(original.RUN)
        source.field_bindings=False
        with self.assertRaises(NativeUIError):source.capture(original.RUN)
        self.assertEqual(1,len(native.commands))
        other=native.source()
        with self.assertRaises(NativeUIError):other.restore(source.previous)

    def test_weak_model_keeps_64_birth_cap_and_does_not_reuse_dead_object_context_or_window(self):
        registry=WeakTripleModel();window,context=Object(),Object();first=Field(window)
        old=registry.identity(first,window,context);self.assertEqual(old,registry.identity(first,window,context))
        changed_context=Object();new_context_birth=registry.identity(first,window,changed_context)
        self.assertTrue(new_context_birth);self.assertNotEqual(old,new_context_birth)
        moved_window=Object();self.assertEqual('',registry.identity(first,moved_window,context))
        first.window=weakref.ref(moved_window);new_window_birth=registry.identity(first,moved_window,context)
        self.assertTrue(new_window_birth);self.assertNotIn(new_window_birth,(old,new_context_birth))
        reference=weakref.ref(first);del first;gc.collect();self.assertIsNone(reference())
        count=64-len(registry.originals);values=[Field(window) for _ in range(count+1)]
        self.assertNotEqual(old,registry.identity(values[0],window,context))
        for item in values[1:count]:self.assertTrue(registry.identity(item,window,context))
        self.assertEqual(64,len(registry.originals));self.assertEqual('',registry.identity(values[-1],window,context))

    def test_original_shared_birth_survives_retired_history_without_creating_a_new_identity(self):
        native=BoundUi();source=native.bound_source();first=source.capture(original.RUN)
        original_token=ui.current_editor(first)['fieldBinding']['weakBirth']
        native.retire();reference=weakref.ref(native.field);native.field=None;gc.collect();self.assertIsNone(reference())
        second=source.capture(original.RUN);row=second['source']['editors'][0]
        self.assertEqual('retired',row['fieldBinding']['status']);self.assertEqual(original_token,row['fieldBinding']['weakBirth'])
        self.assertEqual(1,len(native.registry.originals));self.assertIsNone(ui.current_editor(second))

    def test_constructor_mode_aliases_refuse_before_any_native_query(self):
        native=BoundUi()
        for value in (0,1,None,'true',[],{}):
            with self.subTest(value=repr(value)),self.assertRaises(NativeUIError):
                ui.PicoLifecycleSource(native.send,native.read,lambda:20000,lambda:True,123,field_bindings=value)
        self.assertEqual([],native.commands)

    def test_ui2_closed_binding_aliases_and_rewritten_weak_birth_fail_before_new_cursor(self):
        for fault in ('version','ui-id','birth','extra'):
            with self.subTest(fault=fault):
                native=BoundUi();source=native.bound_source();source.capture(original.RUN);before=deepcopy(source.previous)
                send=native.send
                def changed(request):
                    send(request);relation=native.value['source']['editors'][0]['fieldBinding']
                    if fault=='version':relation['lifecycleFieldBindingVersion']=True
                    elif fault=='ui-id':relation['uiFieldId']='f'*32
                    elif fault=='birth':relation.update(weakBirth='e'*32,pendingFieldToken='e'*32)
                    else:relation['expected']=True
                source.send=changed
                with self.assertRaises(NativeUIError):source.capture(original.RUN)
                self.assertEqual(before,source.previous)


if __name__=='__main__':unittest.main()
