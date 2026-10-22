"""Context-local bookkeeping only; no source facts or file I/O are produced."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import unittest
from unittest.mock import patch
from adapters.original_file_reads import record,scope


class FileReadMembershipTests(unittest.TestCase):
    def test_default_hook_and_active_hook_perform_no_file_io(self):
        with patch('builtins.open',side_effect=AssertionError('Audit opened a file')),patch('os.stat',side_effect=AssertionError('Audit statted a file')):
            record('/private/unobserved')
            with scope() as current:
                self.assertEqual(set(),current);record('/private/actual-original')
                self.assertEqual({Path('/private/actual-original')},current)
    def test_nested_readers_share_only_the_current_decoder_and_exit_resets(self):
        with scope() as outer:
            record('/private/first')
            with scope() as inner:
                self.assertIs(inner,outer);record('/private/second')
        record('/private/after')
        with scope() as after:self.assertEqual(set(),after)
        self.assertEqual({Path('/private/first'),Path('/private/second')},outer)
    def test_failed_decoder_exits_context_without_qualifying_a_later_replay(self):
        with self.assertRaises(ValueError),scope():record('/private/not-qualified');raise ValueError('Full decoder failed')
        with scope() as fresh:self.assertEqual(set(),fresh)
    def test_an_independent_thread_cannot_add_its_files_to_this_decoder(self):
        with ThreadPoolExecutor(max_workers=1) as executor,scope() as current:
            record('/private/owner')
            def other():
                record('/private/foreign-no-scope')
                with scope() as isolated:record('/private/foreign');return set(isolated)
            result=executor.submit(other).result(timeout=5)
            self.assertEqual({Path('/private/owner')},current)
            self.assertEqual({Path('/private/foreign')},result)


class ActualFileReadHookTests(unittest.TestCase):
    """Run only after the three explicit shared hooks have been integrated."""
    def setUp(self):
        import tempfile
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
    def test_actual_private_json_read_records_only_a_successfully_parsed_existing_file(self):
        from adapters.normal_feature_state import PrivateFeatureState
        from adapters.normal_ui import NativeUIError
        store=PrivateFeatureState(self.root/'actual.json');store.write(dict(actual='original bytes'),None)
        with scope() as reads:self.assertEqual(dict(actual='original bytes'),store.read())
        self.assertEqual({store.path},reads)
        with scope() as missing:self.assertIsNone(PrivateFeatureState(self.root/'missing.json').read())
        self.assertEqual(set(),missing)
        store.path.write_bytes(b'{invalid json')
        with scope() as failed,self.assertRaises(NativeUIError):store.read()
        self.assertEqual(set(),failed)
    def test_actual_immutable_frame_read_records_only_verified_bytes_and_inode(self):
        from adapters.original_frame_store import OriginalFrameStore
        from adapters.normal_ui import NativeUIError
        from ios.self_tests.test_ios_emote_sources import BINDING,RUN
        store=OriginalFrameStore(self.root,BINDING,RUN,'primary',lambda:True,lambda *_:None,namespace='emote',schema_prefix='emote')
        reference=store.write(1,dict(actual='unchanged frame'))
        original=store.expand(reference);path=store.path(original)
        with scope() as reads:self.assertEqual(dict(actual='unchanged frame'),store.read(original))
        self.assertEqual({path},reads)
        path.write_bytes(path.read_bytes()+b' ')
        with scope() as failed,self.assertRaises(NativeUIError):store.read(original)
        self.assertEqual(set(),failed)
    def test_actual_archived_png_read_records_only_verified_original_pixels_without_native_send(self):
        from adapters.normal_feature_state import PrivateFeatureState
        from adapters.normal_ui import NativeUIError
        from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
        from adapters.script_feature.lock import ScriptSourceLock
        from self_tests.test_owned_vulkan_world_frame import owner,World,TICKET,BINDING,RUN,REQUEST
        store=PrivateFeatureState(self.root/'owner.json');boundary=World();current=owner(boundary,store,self.root)
        _capture,raw=current.capture(TICKET);current.release();value=store.read();before=len(boundary.commands)
        lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        with lock.held(),scope() as reads:
            self.assertEqual(raw,VulkanWorldFrameOwner.archive_original(value,self.root,BINDING,RUN,'primary',0,REQUEST,lock))
        self.assertEqual({self.root/current.name},reads);self.assertEqual(before,len(boundary.commands))
        path=self.root/current.name;path.write_bytes(path.read_bytes()+b' ')
        with lock.held(),scope() as failed,self.assertRaises(NativeUIError):
            VulkanWorldFrameOwner.archive_original(value,self.root,BINDING,RUN,'primary',0,REQUEST,lock)
        self.assertEqual(set(),failed);self.assertEqual(before,len(boundary.commands))
