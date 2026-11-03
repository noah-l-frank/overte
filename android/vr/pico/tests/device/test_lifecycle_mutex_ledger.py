"""Explicit warm mutex2 capacity counters and unchanged canonical seven-entry."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.script_journey.history import canonical
from self_tests import test_pico_lifecycle_mutex_ledger as counters
import test_lifecycle_actor_storage3 as original


class LifecycleMutexLedger2CanonicalTests(unittest.TestCase):
    setUp=original.LifecycleActorStorage3Tests.setUp
    baseline=original.LifecycleActorStorage3Tests.baseline
    fields=original.LifecycleActorStorage3Tests.fields
    act=original.LifecycleActorStorage3Tests.act
    storage_failure_receipt=original.LifecycleActorStorage3EntryTests.storage_failure_receipt

    def test_original_canonical_factory_selects_ledger2_before_same_seven_inputs(self):
        original.LifecycleActorStorage3EntryTests.test_actual_canonical_factory_normal_background_entry_and_original_process_return(self)
        namespace=self.background.raw_namespace;ledger=namespace._mutex_ledger
        self.assertEqual(2,namespace.mutex_layout);self.assertIs(ledger,namespace._original_mutex_ledger)
        self.assertGreater(len(namespace.mutex_observations),0)
        self.assertEqual('released',self.background.state['phase'])
        self.assertFalse(ledger.poisoned);self.assertIsNone(ledger.pending)
        print('Canonical mutex2 exact compact bill: '+canonical(dict(lifecycleMutexLedgerVersion=2,
            actualTransitions=len(namespace.mutex_observations),cohorts=len(ledger.state[0]),
            compactEncodedBytes=ledger.encoded_bytes(),metadataIncludingReconstructionWindow=ledger.metadata_bytes(),
            unchangedRawReceipts=self.background.originals.archive.bill()['receipts'],
            actualNormalActions=7,full24Groups=False,full16Effects=False)).decode(),flush=True)


def load_tests(loader,tests,pattern):
    return unittest.TestSuite((loader.loadTestsFromTestCase(counters.LifecycleMutexLedger2Tests),
        loader.loadTestsFromTestCase(LifecycleMutexLedger2CanonicalTests)))


if __name__=='__main__':unittest.main()
