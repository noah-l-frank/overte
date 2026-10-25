"""Actual native failure prefix invalidates a full historical cleanup proof.

All HTTP/AFC/private owners execute. Native producers and clocks are explicit
models. Reuse never creates new originals or current cleanup authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_tail import TabletWebTail
from ios.self_tests.tablet_web_whole_fixture import TabletWholeBoundary


class TabletCleanupPublicationCacheTests(unittest.TestCase):
    def test_exact_unchanged_proof_reused_but_actual_rejected_pointer_birth_forces_full_revalidation(self):
        b=TabletWholeBoundary(self);runtime=b.runtime;runtime.proof_roots=[b.root]
        tail=TabletWebTail(runtime);before=tail.capture([]);stop=tail.capture([]);quiet=[]
        for _ in range(3):b.sleep(1.6);quiet.append(tail.capture([]))
        original=dict(tabletWebCleanupObservationVersion=1,before=before,stop=stop,quiet=quiet)
        calls=[];decode=runtime._publication_original
        def actual(value):calls.append(value);return decode(value)
        runtime._publication_original=actual
        expected=runtime.publication_original(original);commands=len(b.commands)
        self.assertEqual(expected,runtime.publication_original(original));self.assertEqual(1,len(calls));self.assertEqual(commands,len(b.commands))
        def bad_birth(query,value):
            if query['action']=='feature-ios-pointer-state':value['source']['instance']='e'*32
        b.force=bad_birth
        with self.assertRaises(NativeUIError):tail.capture([])
        count=len(b.commands)
        # This earlier capture remains readable as historical evidence. It is
        # redecoded, and cannot discharge the later failed query or become a
        # newly captured/current cleanup sample.
        self.assertEqual(expected,runtime.publication_original(original))
        self.assertEqual(2,len(calls));self.assertEqual(count,len(b.commands))
        pointer=runtime.auxiliary('pointer');pointer.history();self.assertTrue(pointer.blocked)
        self.assertIsNotNone(pointer.state['pending']);self.assertTrue(pointer.state['pending']['raws'])
        with self.assertRaises(NativeUIError):tail.capture([])
        self.assertEqual(count,len(b.commands))


if __name__=='__main__':unittest.main()
