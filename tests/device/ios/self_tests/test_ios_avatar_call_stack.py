"""Explicit native frame fixtures and independently read candidate module bytes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_call_stack as calls
from ios.adapters.avatar_code import pins
from ios.self_tests.avatar_callers2_fixture import original

ROOT=Path(__file__).resolve().parents[4]
EPOCH=1700000000000


class AvatarCallStackTests(unittest.TestCase):
    def test_independent_repository_bytes_join_actual_indexed_frames_and_reviewed_pins(self):
        packet,modules,code=original(calls.SUFFIXES)
        self.assertEqual(packet,calls.bound(packet,modules,EPOCH,code,pins(),required=set(calls.SUFFIXES)))
        changed=deepcopy(packet);changed['frames'][1]['compiled']['sha256']='b'*64
        with self.assertRaises(NativeUIError):calls.bound(changed,modules,EPOCH,code,pins(),required=set(calls.SUFFIXES))

    def test_repeated_current_frame_does_not_invent_a_parent_module(self):
        packet,modules,code=original(('/modules/request.js','/modules/request.js'))
        with self.assertRaises(NativeUIError):calls.bound(packet,modules,EPOCH,code,pins(),required={'/modules/request.js','/system/pal.js'})
        modules[1]['url']='qrc:/scripts/system/pal.js'
        with self.assertRaises(NativeUIError):calls.validate(packet,modules,EPOCH,required={'/system/pal.js'})

    def test_actual_top_frame_cannot_be_replaced_by_a_later_request_frame(self):
        packet,modules,code=original(('/system/pal.js','/modules/request.js'))
        with self.assertRaises(NativeUIError):calls.bound(packet,modules,EPOCH,code,pins(),required={'/modules/request.js'},top='/modules/request.js')

    def test_source_url_and_original_compiled_url_must_be_identical(self):
        packet,modules,_=original(('/modules/request.js',))
        for target in ('sourceUrlSha256','compiled'):
            changed=deepcopy(packet)
            if target=='compiled':changed['frames'][0][target]['urlSha256']='b'*64
            else:changed['frames'][0][target]='b'*64
            with self.assertRaises(NativeUIError):calls.validate(changed,modules,EPOCH)

    def test_script_identity_and_engine_birth_cannot_change_under_continuity(self):
        packet,modules,code=original(('/modules/request.js',))
        changed=deepcopy(packet);changed['frames'][0]['compiled']['firstObservedEpochMs']+=1
        with self.assertRaises(NativeUIError):calls.continuity(packet,changed)
        changed=deepcopy(packet);changed['instance']='b'*32
        with self.assertRaises(NativeUIError):calls.continuity(packet,changed)
        changed=deepcopy(packet);changed['frames'].append(deepcopy(changed['frames'][0]));changed['frames'][1]['compiled']['sha256']='b'*64
        with self.assertRaises(NativeUIError):calls.validate(changed,modules,EPOCH)

    def test_actual_first_observation_is_not_used_as_compile_or_submission_time(self):
        packet,modules,code=original(('/modules/request.js',));code[0]['submittedEpochMs']=EPOCH-10
        with self.assertRaises(NativeUIError):calls.bound(packet,modules,EPOCH,code,pins(),required={'/modules/request.js'})
        packet['frames'][0]['isEval']=True;code[0]['submittedEpochMs']=EPOCH-100
        with self.assertRaises(NativeUIError):calls.bound(packet,modules,EPOCH,code,pins(),required={'/modules/request.js'})

    def test_incomplete_stack_and_duplicate_or_boolean_module_indices_are_rejected(self):
        packet,modules,_=original(('/modules/request.js',))
        changed=deepcopy(packet);changed['complete']=False
        with self.assertRaises(NativeUIError):calls.validate(changed,modules,EPOCH)
        with self.assertRaises(NativeUIError):calls.validate(packet,modules+modules,EPOCH)
        modules[0]['frame']=False
        with self.assertRaises(NativeUIError):calls.validate(packet,modules,EPOCH)

    def test_native_resolver_uses_actual_compiled_bytes_and_preserves_original_stack(self):
        source=(ROOT/'libraries/script-engine/src/AvatarV8Callers.h').read_text()
        self.assertIn('result.stack=actual',source);self.assertIn('const auto frames=actual.value("frames").toList()',source)
        for key in ('sourceUrlSha256','urlSha256','encoding','codeUnits','sha256'):
            self.assertIn('"'+key+'"',source)
        self.assertIn('result.modules.append(QVariantMap{{"frame",index},{"url",matched}})',source)
        self.assertNotIn('parentContext',source);self.assertNotIn('newProgram',source)


if __name__=='__main__':unittest.main()
