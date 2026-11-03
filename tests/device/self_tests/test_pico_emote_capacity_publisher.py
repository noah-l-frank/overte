"""Actual host-native publisher protocol model; C++ remains UNCOMPILED."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import uuid

from adapters.normal_ui import NativeUIError
from self_tests.test_pico_emote_stream_capacity import StreamCapacityTests,RETAINED
from self_tests.pico_emote_capacity_publisher_model import NativePublisherModel,PENDING


class StreamPublisherTests(StreamCapacityTests):
    # Wrappers select ONLY these declared methods, not inherited cases.
    def publisher(self):
        capacity=self.active();self.publisher_model=object.__new__(NativePublisherModel)
        self.model.publisher_models.append(self.publisher_model)
        with self.model.m.s.lock.held():NativePublisherModel.__init__(self.publisher_model,self.model.scope_root,capacity.guard)
        return self.publisher_model

    def test_actual_exact_cap_write_then_oversize_keeps_original_bytes_and_failed_nonce(self):
        publisher=self.publisher();name='world-render-observation.json';original=os.urandom(262144)
        with self.model.m.s.lock.held():
            publisher.publish(name,uuid.uuid4().hex,original);nonce=uuid.uuid4().hex
            with self.assertRaises(NativeUIError):publisher.publish(name,nonce,original+b'\0')
            self.assertEqual(original,(publisher.root/name).read_bytes());self.assertTrue((publisher.root/PENDING).read_bytes().startswith(nonce.encode()+b'\n'))
            events=list(publisher.events)
            with self.assertRaises(NativeUIError):publisher.publish(name,uuid.uuid4().hex,b'new')
            self.assertEqual(events,publisher.events)

    def test_actual_partial_write_retains_marker_original_ofds_and_partial_bytes(self):
        publisher=self.publisher();publisher.fault='partial';value=os.urandom(131072);name='world-render-observation.json'
        with self.model.m.s.lock.held(),self.assertRaises(OSError):publisher.publish(name,uuid.uuid4().hex,value)
        self.assertEqual(value[:65536],(publisher.root/name).read_bytes());self.assertTrue((publisher.root/PENDING).is_file())
        owner=publisher.files[name]['owner'];owner.require(owner.fd);self.assertTrue(publisher.failed)

    def test_actual_complete_write_lost_return_never_becomes_clean_success_or_retry(self):
        publisher=self.publisher();publisher.fault='lost-complete';value=os.urandom(65537);name='world-render-observation.json'
        with self.model.m.s.lock.held(),self.assertRaises(OSError):publisher.publish(name,uuid.uuid4().hex,value)
        self.assertEqual(value,(publisher.root/name).read_bytes());self.assertTrue((publisher.root/PENDING).is_file())
        with self.model.m.s.lock.held(),self.assertRaises(NativeUIError):publisher.require()
        self.assertEqual(1,len([event for event in publisher.events if event[0]=='written']))

    def test_actual_equal_bytes_inode_replacement_refuses_before_intent_or_write(self):
        publisher=self.publisher();name='world-render-observation.json'
        with self.model.m.s.lock.held():publisher.publish(name,uuid.uuid4().hex,b'original')
        path=publisher.root/name;path.rename(path.with_name('retained-native-original.bin'));path.write_bytes(b'original');path.chmod(0o600)
        events=list(publisher.events)
        with self.model.m.s.lock.held(),self.assertRaises(NativeUIError):publisher.publish(name,uuid.uuid4().hex,b'changed')
        self.assertEqual(events,publisher.events);self.assertFalse((publisher.root/PENDING).exists())

    def test_actual_ancestor_directory_exchange_refuses_before_native_publication(self):
        publisher=self.publisher();path=publisher.root;path.rename(path.with_name('retained-native-original-root'));path.mkdir(mode=0o700)
        with self.model.m.s.lock.held(),self.assertRaises(NativeUIError):publisher.publish('world-render-observation.json',uuid.uuid4().hex,b'value')
        self.assertEqual([],publisher.events);self.assertEqual([],list(path.iterdir()))

    def test_actual_orphan_receipt_prevents_any_fixed_slot_or_native_output(self):
        capacity=self.active();root=self.model.scope_root;path=root/('world-render-storage-'+uuid.uuid4().hex+'.json')
        path.write_bytes(b'owned-test-foreign-receipt');path.chmod(0o600)
        # Holder is retained BEFORE constructor; no new fixed slot is created.
        publisher=object.__new__(NativePublisherModel);self.publisher_model=publisher
        self.model.publisher_models.append(publisher)
        with self.model.m.s.lock.held(),self.assertRaises(NativeUIError):NativePublisherModel.__init__(publisher,root,capacity.guard)
        self.assertEqual([path],list(root.iterdir()));self.assertEqual([],publisher.events)


if __name__=='__main__':
    import unittest
    unittest.main()
