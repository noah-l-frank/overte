"""Pure original sharing-group joins; no normal journey/native/device claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_strong_release as release
from ios.self_tests.test_ios_assets_strong_consumers import AssetsStrongConsumersTests
from ios.self_tests.test_ios_assets_model_origin import RUN


class AssetsStrongReleaseTests(unittest.TestCase):
    def packets(self):
        b=AssetsStrongConsumersTests().prepare();reader=b.reader();first=reader.read(RUN)
        lineage=dict(readerId=b.row['id'],sha256=b.row['sha256'],bytes=b.row['bytes'],processId=42,runId=RUN)
        return b,reader,first,lineage
    def test_original_positive_mesh_and_still_live_external_group_remain_explicit(self):
        b,reader,first,lineage=self.packets();last=reader.read(RUN)
        original,rows=release.strong_history(first,[last],lineage)
        self.assertFalse(original['allKnownStrongOwnersGone']);self.assertFalse(rows[0]['allKnownStrongOwnersGone'])
        self.assertFalse(rows[0]['destructorCompletionAvailable']);self.assertFalse(rows[0]['resourceRetirementAvailable'])
    def test_original_fixture_expiry_stamps_are_retained_without_freshness_or_end_upgrade(self):
        b,reader,first,lineage=self.packets()
        death=b.stamp()
        for row in b.state['history']['consumerOwnership']['rows']:
            row.update(strongOwnersAlive=False,ownershipExpiryObserved=deepcopy(death))
        packets=[reader.read(RUN),reader.read(RUN),reader.read(RUN)]
        saved=deepcopy((first,packets));original,rows=release.strong_history(first,packets,lineage)
        self.assertTrue(all(row['allKnownStrongOwnersGone'] for row in rows));self.assertEqual(saved,(first,packets))
        self.assertEqual([row['ownershipExpiryObserved'] for row in packets[0]['source']['history']['consumerOwnership']['rows']],
            [row['ownershipExpiryObserved'] for row in rows[-1]['consumers']])
        self.assertTrue(all(not row['resourceRetirementAvailable'] for row in rows))
    def test_foreign_body_reader_pid_run_or_missing_positive_mesh_is_not_original_ownership(self):
        for fault in ('hash','bytes','reader','pid','run','already-gone','no-mesh'):
            b,reader,first,lineage=self.packets();last=reader.read(RUN)
            if fault=='hash':lineage['sha256']='f'*64
            elif fault=='bytes':lineage['bytes']+=1
            elif fault=='reader':lineage['readerId']='f'*32
            elif fault=='pid':lineage['processId']=43
            elif fault=='run':lineage['runId']='b'*32
            elif fault=='already-gone':
                for row in first['source']['history']['consumerOwnership']['rows']:
                    row.update(strongOwnersAlive=False,ownershipExpiryObserved=deepcopy(row['born']))
            else:first['source']['history']['consumerOwnership']['rows']=[row for row in first['source']['history']['consumerOwnership']['rows'] if row['kind']!='mesh']
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):release.strong_history(first,[last],lineage)
    def test_native_source_rollback_or_lost_known_group_cannot_make_a_quiet_empty_inventory(self):
        for fault in ('history3','drop','instance','clock','resurrection','death-before-alive-sample'):
            b,reader,first,lineage=self.packets();second=reader.read(RUN);third=reader.read(RUN)
            if fault=='history3':third['source']['history']['assetModelOriginHistoryVersion']=3;third['source']['history'].pop('consumerOwnership')
            elif fault=='drop':third['source']['history']['consumerOwnership']['rows'].pop()
            elif fault=='instance':third['source']['history']['instance']='f'*32
            elif fault=='clock':third=deepcopy(first)
            elif fault=='resurrection':
                row=second['source']['history']['consumerOwnership']['rows'][0]
                row.update(strongOwnersAlive=False,ownershipExpiryObserved=deepcopy(second['source']['history']['clock']))
            else:
                row=third['source']['history']['consumerOwnership']['rows'][0]
                row.update(strongOwnersAlive=False,ownershipExpiryObserved=deepcopy(row['born']))
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):release.strong_history(first,[second,third],lineage)
