"""Actual Combined pair cleanup, with all original four-read quiet windows."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from ios.adapters.snapshot_journey_files import IOSSnapshotJourneyFilesOwner
from ios.self_tests.snapshot_combined_journey_domain import CombinedJourneyDomain,RUN


class SnapshotPreparedQuietIntegrationTests(unittest.TestCase):
    def test_normal_pair_cleanup_prepares_before_each_bounded_original_group(self):
        d=CombinedJourneyDomain(self);d.complete_pending()
        with d.capture_owner() as capture:capture.capture('c'*32);host=capture.history('artifact',capture.state['artifact']).path()
        original=(host.stat().st_ino,host.read_bytes());trace=[]
        with d.files_owner() as owner:
            actual=owner.capture.prepare_observation
            def record(*args,**kwargs):
                before=len(d.commands);token=actual(*args,**kwargs)
                trace.append(dict(label=token.slot['label'],before=before,after=len(d.commands),phase=token.child.state['phase'],started=token.child.state['started'],proof=token.child.state['proof']))
                return token
            # This delegates the actual helper unchanged. No guard, clock,
            # sender, effect producer or returned original is replaced.
            with patch.object(owner.capture,'prepare_observation',side_effect=record):result=owner.cleanup()
            self.assertEqual(12,len(trace));self.assertEqual(3,len(owner.state['quiet']))
            for number in (1,2,3):
                group=[row for row in trace if row['label'].startswith('journey-quiet-'+str(number)+'-')]
                self.assertEqual(4,len(group));self.assertEqual(1,len({row['before'] for row in group}))
                for row in group:self.assertEqual(row['before'],row['after']);self.assertEqual('reserved',row['phase']);self.assertIsNone(row['started']);self.assertIsNone(row['proof'])
                sample=owner.sample(owner.state['quiet'][number-1]);epoch=sample['hostAfterEpochMs']-sample['hostBeforeEpochMs'];mono=(sample['hostAfterMonotonic']-sample['hostBeforeMonotonic'])*1000
                native=sample['nativeAfter']['capturedEpochMs']-sample['nativeBefore']['capturedEpochMs']
                self.assertTrue(0<=epoch<1500 and 0<=mono<1500 and 0<=native<1500);self.assertLessEqual(abs(epoch-mono),250)
                print('Original quiet group',number,'epoch_ms',epoch,'mono_ms',round(mono,3),'native_ms',native,flush=True)
            self.assertEqual(2,result['iosSnapshotJourneyFilesResultVersion']);self.assertTrue(result['hostOriginalRetained'])
            self.assertEqual(3000,result['fileChannel']['fileChannelQuietMilliseconds']);commands=deepcopy(d.commands)
            with owner.lock.held():
                archived=IOSSnapshotJourneyFilesOwner.archive(owner.store,owner.lock,owner.binding,RUN,owner.fixture_url,combined=True)
                self.assertEqual(result,archived.proof())
            self.assertEqual(commands,d.commands)
        self.assertFalse(d.f.f.h.path.exists());self.assertEqual(original,(host.stat().st_ino,host.read_bytes()))
        self.assertEqual((2,1,1),(d.capture_count,d.cancel_count,d.png_count))
        self.assertEqual(1,sum(query['action']=='feature-ios-snapshot-file-remove' for query in d.commands))


if __name__=='__main__':unittest.main()
