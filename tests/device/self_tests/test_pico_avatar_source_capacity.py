"""Actual original-source storage pressure before remote Native send/read."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import json
import unittest
from adapters.normal_ui import NativeUIError
from self_tests import test_pico_avatar_remote as existing

LIMIT=196608


class RemoteSourceCapacityTests(unittest.TestCase):
    def fixture(self):
        model=existing.RemoteBoundary();self.addCleanup(model.close);return model

    def test_capacity_work_cannot_send_after_original_host_query_window(self):
        model=self.fixture()
        with model.lock.held():
            owner=model.owner();capacity=owner.raw_capacity
            def delayed():
                capacity();model.clock+=2
            owner.raw_capacity=delayed
            with self.assertRaises(NativeUIError):owner.read()
        self.assertEqual([],model.commands)

    def test_capacity_work_cannot_acquire_a_reply_after_original_host_query_window(self):
        model=self.fixture();reads=[];original=model.original
        def read():
            reads.append(True);return original()
        model.original=read
        with model.lock.held():
            owner=model.owner();capacity=owner.raw_capacity;calls=[]
            def delayed():
                capacity();calls.append(True)
                if len(calls)==2:model.clock+=2
            owner.raw_capacity=delayed
            with self.assertRaises(NativeUIError):owner.read()
        self.assertEqual(1,len(model.commands))
        self.assertEqual([],reads)

    def test_maximum_control_literal_is_fully_preserved_before_decode_refusal(self):
        model=self.fixture();raw='\0'*LIMIT;seen=[]
        def read():
            if seen:raise OSError('End this explicit malformed-source counter')
            seen.append(raw);return raw
        model.original=read
        with model.lock.held():
            owner=model.owner()
            with self.assertRaises(NativeUIError):owner.read()
            self.assertEqual('failed',owner.store.read()['phase'])
            self.assertIsNone(owner.state['pending']['partialRaw'])
            self.assertEqual([raw],[owner.raw(ref) for ref in owner.state['pending']['raw']])

    def test_full_size_distinct_replies_stop_before_next_getter_and_keep_every_original(self):
        model=self.fixture();seen=[]
        noise=base64.b64encode(hashlib.shake_256(b'original nonsecret remote source quota counter').digest(LIMIT)).decode()
        def read():
            raw=('invalid-json-'+str(len(seen))+'-'+noise)[:LIMIT]
            seen.append(raw);return raw
        model.original=read
        with model.lock.held():
            owner=model.owner()
            with self.assertRaises(NativeUIError):owner.read()
            self.assertEqual('failed',owner.store.read()['phase'])
            self.assertIsNone(owner.state['pending']['partialRaw'])
            self.assertTrue(seen)
            self.assertEqual(seen,[owner.raw(ref) for ref in owner.state['pending']['raw']])
            self.assertLessEqual(len(owner.state['chunks']),512)
            self.assertEqual(1,len(model.commands))

    def test_valid_large_originals_refuse_next_dispatch_before_its_send_and_getter(self):
        model=self.fixture();seen=[]
        def read():
            raw=json.dumps(model.sample,separators=(',',':'))
            self.assertLess(len(raw),65536)
            raw+=' '*(65536-len(raw));seen.append(raw);return raw
        model.original=read
        with model.lock.held():
            owner=model.owner();completed=[]
            for _ in range(32):
                before=(len(model.commands),len(seen))
                try:owner.read()
                except NativeUIError:
                    self.assertEqual(before,(len(model.commands),len(seen)))
                    self.assertEqual('failed',owner.store.read()['phase'])
                    self.assertIsNone(owner.state['pending']['partialRaw'])
                    break
                completed.append(seen[-1])
            else:self.fail('The bounded original container did not apply backpressure')
            self.assertTrue(completed)
            self.assertEqual(completed,[owner.raw(row['raw']) for row in owner.state['records']])
            self.assertLessEqual(len(owner.state['chunks']),512)


if __name__=='__main__':unittest.main()
