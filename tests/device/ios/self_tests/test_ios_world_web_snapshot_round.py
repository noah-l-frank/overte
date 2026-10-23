"""Pure scoped body memo never replaces freshness or an actual carrier read."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_snapshot as snapshot
from ios.self_tests.world_web_snapshot_fixture import SnapshotNative,packed
from ios.self_tests.world_web_source_boundary import RUN,URL


class WorldWebSnapshotRoundTests(unittest.TestCase):
    def original(self):
        model=SnapshotNative();query=dict(schemaVersion=1,commandId='ios-'+'f'*32,action=snapshot.ACTION,runId=RUN,fixtureUrl=URL)
        model.send(query);return model.last,query
    def test_default_revalidates_and_one_scoped_equal_actual_body_has_no_outward_alias_or_next_round_reuse(self):
        value,query=self.original();decode=snapshot._body
        with patch.object(snapshot,'_body',wraps=decode) as actual:
            snapshot.body(value);snapshot.body(value);self.assertEqual(2,actual.call_count)
            with snapshot.validation_round():
                first,parts=snapshot.body(value);first['calls'].clear();parts['keys']['source']['complete']=False
                snapshot.validate(value,query,42);other,again=snapshot.body(value)
                self.assertTrue(other['calls']);self.assertTrue(again['keys']['source']['complete']);self.assertEqual(3,actual.call_count)
            with snapshot.validation_round():snapshot.body(value)
            self.assertEqual(4,actual.call_count)
    def test_warm_original_still_checks_actual_epoch_query_pid_and_complete_hashed_body(self):
        value,query=self.original()
        with snapshot.validation_round():
            snapshot.validate(value,query,42,value['clockAfter']['epochMs'])
            with self.assertRaises(NativeUIError):snapshot.validate(value,query,42,value['clockAfter']['epochMs']+1501)
            with self.assertRaises(NativeUIError):snapshot.validate(value,query|dict(runId='b'*32),42)
            with self.assertRaises(NativeUIError):snapshot.validate(value,query,43)
            changed=deepcopy(value);body=snapshot.unpack(changed['payload']);body['calls'][0]['command']['commandId']='ios-'+'a'*32;changed['payload']=packed(body)
            with self.assertRaises(NativeUIError):snapshot.body(changed)
            changed=deepcopy(value);changed['instance']='a'*32
            with self.assertRaises(NativeUIError):snapshot.body(changed)


if __name__=='__main__':unittest.main()
