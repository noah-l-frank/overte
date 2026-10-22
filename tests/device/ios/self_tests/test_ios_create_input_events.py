"""Real native token originals in bounded immutable Create event carriers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.self_tests import test_ios_create_action_owner as fixture


class CreateInputEventsTests(unittest.TestCase):
    def setUp(self):
        self.h=fixture.CreateActionOwnerTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
    def completed(self):
        owner=self.h.owner();owner.begin(fixture.QUERY);self.h.ui(owner).choose('create.host',1);owner.finish();return owner
    def test_original_native_admissions_receipts_and_readbacks_are_reopened_from_actual_private_carriers(self):
        with self.h.lock.held():
            owner=self.completed();value=owner.store.read();self.assertEqual(2,value['iosCreateActionOwnerVersion'])
            stored=unpack(value['payload'])[0];self.assertEqual({'sha256'},set(stored['calls'][0]['events'][0]))
            original=deepcopy(owner.state);commands=deepcopy(self.h.harness.native.commands)
            self.assertEqual(original,self.h.owner().state)
            reference=stored['calls'][0]['events'][0];carrier=owner.event_store(reference['sha256']);packet=carrier.read();packet['owner']='foreign.json';carrier.write(packet,carrier.read())
            with self.assertRaises(NativeUIError):self.h.owner()
            self.assertEqual(commands,self.h.harness.native.commands)
    def test_original_inline_v1_read_does_not_write_or_migrate_until_new_durable_intent(self):
        with self.h.lock.held():
            owner=self.completed();original=deepcopy(owner.state);legacy=owner.envelope(original,version=1);owner.store.write(legacy,owner.previous)
            raw=owner.store.path.read_bytes();rebuilt=self.h.owner();self.assertEqual(original,rebuilt.state);self.assertEqual(raw,owner.store.path.read_bytes())
            rebuilt.begin(dict(fixture.QUERY,ticket='c'*32));self.assertEqual(2,rebuilt.store.read()['iosCreateActionOwnerVersion'])
            self.assertEqual(original['calls'],rebuilt.state['calls'][:1])


if __name__=='__main__':unittest.main()
