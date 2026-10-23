"""Original host weak lifetime operands and closed legacy-independent source."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_ui_root_ownership import validate,membership
from ios.self_tests.world_web_ui_roots_fixture import Root,RootCensus


class ScriptUiRootOwnershipTests(unittest.TestCase):
    def test_retained_hidden_root_stays_alive_and_real_weak_expiry_never_claims_allocation_birth(self):
        source=RootCensus();root=Root('manager');identity=source.observe(root)
        first=source.source();validate(first,pid=31,epoch=first['capturedEpochMs'])
        self.assertTrue(first['roots'][0]['weakAlive']);self.assertNotIn('birthEpochMs',first['roots'][0])
        again=source.source();validate(again,pid=31,previous=first);self.assertEqual(identity,source.observe(root))
        del root;gc.collect();last=source.source();validate(last,pid=31,previous=again)
        self.assertFalse(last['roots'][0]['weakAlive']);self.assertGreater(last['roots'][0]['weakExpiredObservedEpochMs'],0)
        new=Root('manager');self.assertNotEqual(identity,source.observe(new));validate(source.source(),pid=31,previous=last)
    def test_process_source_sequence_identity_resurrection_epoch_and_untyped_fields_refuse(self):
        source=RootCensus();root=Root('picker');source.observe(root);first=source.source();later=source.source()
        for edit in (dict(processId=52),dict(instance='f'*32),dict(sequence=first['sequence']),dict(clockDomain='appium-node-host'),
                     dict(complete=1),dict(observationSequence=True),dict(capturedEpochMs=1),dict(expected=True)):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):validate(dict(later,**edit),pid=31,previous=first)
        del root;gc.collect();dead=source.source();bad=deepcopy(source.source());bad['roots'][0].update(weakAlive=True,weakExpiredObservedEpochMs=0,weakExpiredObservedMonotonicMs=0)
        with self.assertRaises(NativeUIError):validate(bad,pid=31,previous=dead)
        invalid=deepcopy(later);invalid['roots'][0]['firstObservedSequence']=True
        with self.assertRaises(NativeUIError):validate(invalid,pid=31)
    def test_wholewalk_membership_is_exact_actual_original_root_and_unready_is_never_empty_absence(self):
        source=RootCensus();root=Root('picker');identity=source.observe(root);packet=source.source()
        inventory=dict(inventoryVersion=2,complete=True,managers=[],pickers=[dict(componentSource=root.source)],
            rootOwnership=packet,rootMembership=dict(managers=[],pickers=[identity]))
        self.assertEqual(packet,membership(inventory,pid=31))
        for change in ('missing','foreign','wrong-component','unready'):
            bad=deepcopy(inventory)
            if change=='missing':bad['rootMembership']['pickers']=[]
            elif change=='foreign':bad['rootMembership']['pickers']=['f'*32]
            elif change=='wrong-component':bad['pickers'][0]['componentSource']='qrc:/other/dialogs/NativeFileBrowser.qml'
            else:bad['rootOwnership']['wholeTreeReady']=False
            with self.subTest(change=change),self.assertRaises(NativeUIError):membership(bad,pid=31)
        unready=dict(inventoryVersion=2,complete=False,managers=[],pickers=[],rootOwnership=source.source(ready=False),rootMembership=dict(managers=[],pickers=[]))
        self.assertTrue(membership(unready,pid=31)['roots'][0]['weakAlive'])
    def test_oversize_or_overflow_stays_incomplete_and_does_not_reset_prior_identity_history(self):
        source=RootCensus();roots=[Root('manager') for _ in range(65)]
        for root in roots:source.observe(root)
        value=source.source();self.assertFalse(value['complete']);validate(value,pid=31)
        following=source.source();validate(following,pid=31,previous=value)
        with self.assertRaises(NativeUIError):validate(dict(following,complete=True),pid=31,previous=value)
        self.assertEqual(dict(iosScriptUiRootOwnershipVersion=1,available=False),validate(dict(iosScriptUiRootOwnershipVersion=1,available=False)))
    def test_wrong_native_clock_or_foreign_candidate_pid_is_not_a_current_owned_root(self):
        source=RootCensus();root=Root('manager');source.observe(root);value=source.source()
        for pid,epoch in ((52,value['capturedEpochMs']),(31,value['capturedEpochMs']+1600)):
            with self.subTest(pid=pid,epoch=epoch),self.assertRaises(NativeUIError):validate(value,pid=pid,epoch=epoch)


if __name__=='__main__':unittest.main()
