"""Pure historical proof reuse retains actual immutable original boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack,pack
from ios.self_tests import test_ios_world_web_input as fixture


class WorldWebInputRoundTests(unittest.TestCase):
    def setUp(self):
        self.test=fixture.WorldWebInputTests();self.test.setUp();self.addCleanup(self.test.doCleanups)
    def carrier(self,source):
        row=unpack(source.record_store(1).read()['payload'])[0];part=row['originals']['keys'];store=source.parts.store('keys')
        return store.path(store.expand(part['chunks'][0]))
    def replace(self,path):
        next_path=path.with_suffix('.replacement');next_path.write_bytes(path.read_bytes());next_path.chmod(0o600);os.replace(next_path,path)
    def test_warm_row_proof_cannot_hide_changed_body_or_same_bytes_new_original_inode(self):
        t=self.test
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock);owner=t.owner(source);owner.perform(t.sdk.ticket,'real-focus','tap','text');owner.decode(owner.previous)
            changed=deepcopy(owner.previous);rows=unpack(changed['payload']);rows[0]['records'][0]['body']['actions'][0]['actions'][0]['x']+=20;changed['payload']=pack(rows)
            with self.assertRaises(NativeUIError):owner.decode(changed)
            self.replace(self.carrier(source))
            with self.assertRaises(NativeUIError):owner.decode(owner.previous)
            self.assertEqual(1,len(t.sdk.posted))
    def test_actual_transport_preparation_replacing_source_carrier_blocks_before_first_post(self):
        t=self.test
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock);owner=t.owner(source)
            t.sdk.before_post=lambda:self.replace(self.carrier(source))
            with self.assertRaises(NativeUIError):owner.perform(t.sdk.ticket,'uncertain-input','tap','text')
            self.assertEqual([],t.sdk.posted);self.assertEqual('issued',owner.state['records'][0]['phase'])
            self.assertEqual(1,t.sdk.releases)
    def test_original_changed_then_restored_bytes_and_mtime_within_round_still_fails_exit(self):
        t=self.test
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock);reference=source.capture('original');path=self.carrier(source);raw=path.read_bytes();before=path.stat()
            with self.assertRaises(NativeUIError):
                with source.validation_round():
                    source.frame(reference);path.write_bytes(raw+b' ');path.write_bytes(raw);os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
            self.assertIsNone(source._round)
            self.assertTrue(source.frame(reference)['originals']['keys']['source']['complete'])


if __name__=='__main__':unittest.main()
