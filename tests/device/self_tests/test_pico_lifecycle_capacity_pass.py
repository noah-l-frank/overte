"""Actual namespace bytes/OFDs/budget reuse; UI/SDK remain declared models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import mmap
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.chat_journey.archive_file import signature
from adapters.native_fd_owner import OriginalDescriptor
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_capacity_pass import UNRESOLVED
from adapters.pico4.lifecycle_namespace_bill import LifecycleNamespaceBill
from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
from adapters.script_journey.history import pack
from adapters.script_journey.lock import ScriptSourceLock
from self_tests.test_pico_lifecycle_source import Boundary,RUN
from self_tests.test_pico_lifecycle_world import BINDING


class LifecycleCapacityPassTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.root.chmod(0o700);self.extra=None
        self.lock=ScriptSourceLock(self.root/'script-sources.lock')
        self.namespace=LifecycleNamespaceBill(self.root,self.lock,mutex_layout=2,expanded=lambda:self.extra)
        self.addCleanup(self.namespace.close)
        self.bank=LifecycleSourceRaw4(self.root/'lifecycle-background-raw.json',RUN,BINDING,self.lock,
            self.lock.assert_held,self.namespace,lambda:0.,capacity_batches=True)
        self.addCleanup(self.bank.close_host);self.helper=self.bank._capacity_pass
        self.path=self.root/'lifecycle-editor-owner.json'
        PrivateFeatureState(self.path).write(dict(lifecycleEditorOwnerVersion=1,payload=pack([{'original':'unchanged'}])),None)
        self.native=Boundary();self.source=self.native.source();self.bank.hook(self.source,'ui')

    def initial(self):self.source.capture(RUN)

    def test_fresh_actual_sources_continue_with_same_capacity_without_reparsing_unchanged_namespace(self):
        self.initial();before=self.helper.full_audits;proof=self.helper.proof
        self.native.rows[0]['focused']=False;self.native.raised=False
        with patch('adapters.pico4.lifecycle_namespace_bill.strict',side_effect=AssertionError('No repeated namespace JSON')):
            value=self.source.capture(RUN)
        self.assertFalse(value['source']['editors'][0]['focused']);self.assertIs(proof,self.helper.proof)
        self.assertEqual(before,self.helper.full_audits);self.assertGreater(self.helper.reuses,0)
        self.assertEqual(2,len(self.native.commands));self.assertEqual(2,self.bank.archive.state['reads'])

    def test_foreign_same_byte_replacement_or_plausible_new_root_cannot_inherit_old_capacity(self):
        self.initial();replacement=self.path.with_name('replace-root');replacement.write_bytes(self.path.read_bytes());replacement.chmod(0o600)
        os.replace(replacement,self.path)
        with self.assertRaises(NativeUIError):self.source.capture(RUN)
        self.assertEqual(1,len(self.native.commands));self.assertTrue(self.bank.failed)

    def test_genuine_mmap_byte_change_without_new_physical_stamp_is_caught_by_current_byte_pass(self):
        fd=os.open(self.path,os.O_RDWR|os.O_CLOEXEC);self.addCleanup(os.close,fd)
        mapping=mmap.mmap(fd,0);self.addCleanup(mapping.close)
        offset=mapping.find(b'unchanged')
        if offset<0:
            # Packed fixture root: use its actual JSON version digit instead.
            offset=mapping.find(b'"lifecycleEditorOwnerVersion":1')+len(b'"lifecycleEditorOwnerVersion":')
        mapping[offset:offset+1]=mapping[offset:offset+1]
        self.initial();before=signature(self.path.lstat())
        original=mapping[offset];mapping[offset:offset+1]=b'2' if original!=ord('2') else b'3'
        after=signature(self.path.lstat());self.assertEqual(before,after,'This counter requires actual same8 mmap semantics')
        with self.assertRaises(NativeUIError):self.source.capture(RUN)
        self.assertEqual(1,len(self.native.commands));self.assertTrue(self.bank.failed)

    def test_changed_actual_expanded_graph_refuses_before_hash_copy_and_next_source(self):
        self.initial();self.extra={'actualHeldState':'x'*(16*1024*1024)}
        with self.assertRaises(NativeUIError):self.source.capture(RUN)
        self.assertEqual(1,len(self.native.commands));self.assertTrue(self.bank.failed)

    def test_mutable_last_cost_or_returned_result_cannot_replace_the_immutable_full_bill(self):
        self.initial()
        with self.lock.held():actual=self.helper.current()
        expected=deepcopy(actual);actual['decodedBytes']=0;self.namespace.last['decodedBytes']=0
        with self.lock.held():observed=self.helper.current()
        self.assertEqual(expected,observed);self.assertGreater(observed['decodedBytes'],0)
        self.assertEqual(1,len(self.native.commands))

    def test_replaced_current_capacity_callback_refuses_before_any_next_file_read_or_sdk(self):
        self.initial();self.namespace.capacity_bill=lambda:0
        with patch('adapters.pico4.lifecycle_capacity_pass.os.pread',side_effect=AssertionError('No next file bytes')):
            with self.assertRaises(NativeUIError):self.source.capture(RUN)
        self.assertEqual(1,len(self.native.commands))

    def test_actual_after_open_ctor_failure_remains_original_strong_and_never_retried(self):
        self.initial();original=OriginalDescriptor.__init__;opened=[]
        def failed(owner,path,flags):
            original(owner,path,flags)
            if str(path).endswith('/lifecycle-editor-owner.json'):
                opened.append(owner);raise OSError('Actual original capacity window ctor failed after open')
        with patch.object(OriginalDescriptor,'__init__',failed),self.assertRaises(NativeUIError):self.source.capture(RUN)
        self.assertEqual(1,len(opened));self.assertIs(opened[0],self.helper.active);self.assertIn(self.helper,UNRESOLVED)
        self.helper.active.require(self.helper.active.fd);self.assertFalse(self.bank.close_host())
        with self.assertRaises(NativeUIError):self.source.capture(RUN)
        self.assertEqual(1,len(self.native.commands))

    def test_every_repeated_json_literal_keeps_exact_full_decoded_bill_against_default_audit(self):
        import json
        literal=json.dumps({'actual':[1,2,3],'nested':{'payload':pack([{'original':'same bytes'}])}})
        self.extra={'copies':[literal,literal,literal,literal]};self.initial()
        self.assertGreater(self.helper.literal_hits,0);self.assertGreater(self.helper.literal_misses,0)
        with self.lock.held():actual=self.namespace()
        baseline=Path(tempfile.mkdtemp(dir=self.root.parent,prefix='original-capacity-audit-'));baseline.chmod(0o700)
        for path in self.root.iterdir():
            if path.name.startswith('lifecycle-background-raw.json'):continue
            target=baseline/path.name;target.write_bytes(path.read_bytes());target.chmod(0o600)
        lock=ScriptSourceLock(baseline/'script-sources.lock')
        namespace=LifecycleNamespaceBill(baseline,lock,mutex_layout=2,expanded=lambda:self.extra)
        self.addCleanup(namespace.close)
        with lock.held():expected=namespace()
        self.assertEqual(expected,actual)
        self.assertEqual(1,len(self.native.commands))

    def test_decoder_function_replacement_cannot_reinterpret_original_literal_cost(self):
        import json
        self.extra={'literal':json.dumps({'actual':[1,2,3]})};self.initial()
        with patch('adapters.pico4.lifecycle_namespace_bill.unpack',return_value=[]):
            with self.assertRaises(NativeUIError):self.source.capture(RUN)
        self.assertEqual(1,len(self.native.commands));self.assertTrue(self.bank.failed)

    def test_actual_large_literal_reservation_precedes_lookup_utf8_copy_and_parser(self):
        self.extra={'literal':'{"actual":"'+'x'*(2*1024*1024)+'"}'}
        with patch.object(self.helper,'literal_lookup',side_effect=AssertionError('No literal work before full budget')) as lookup:
            with self.assertRaises(NativeUIError):self.source.capture(RUN)
        lookup.assert_not_called();self.assertEqual([],self.native.commands)

    def test_fake_close_true_cannot_replace_real_original_pair_terminal(self):
        self.initial();original=OriginalDescriptor.close;seen=[]
        def fake(owner):
            if self.helper.active is owner:seen.append(owner);return True
            return original(owner)
        with patch.object(OriginalDescriptor,'close',fake),self.assertRaises(NativeUIError):self.source.capture(RUN)
        self.assertTrue(seen);self.assertIs(self.helper.active,seen[0]);self.assertFalse(self.bank.close_host())
        self.assertEqual(1,len(self.native.commands));seen[0].require(seen[0].fd)
