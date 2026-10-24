"""Measure actual large Snapshot OFS carriers, including all nested envelopes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import secrets
import tempfile
from types import SimpleNamespace
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.world_web_snapshot_parts import WorldWebSnapshotParts
from ios.adapters import world_web_snapshot as snapshot
from ios.self_tests.world_web_snapshot_fixture import SnapshotNative
from ios.self_tests.world_web_sources_fixture import RUN,URL
from ios.self_tests.test_ios_create_files import BINDING


class WorldWebSnapshotPartsCapacityTests(unittest.TestCase):
    def test_actual_high_entropy_native_wire_over_1mib_uses_three_original_inode_carriers_all_under_unchanged_OFS_limit(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700);intents=[]
        owner=SimpleNamespace(store=PrivateFeatureState(root/'ios-world-web-primary-sources.json'),binding=BINDING,run=RUN,role='primary',pid=42,
            phase=SimpleNamespace(fixture_url=URL),guard=lambda:True,monotonic=lambda:1.,snapshot_storage_intent=lambda kind,value:intents.append(value['phase']),
            state=dict(pending=dict(start=dict(nativeBefore=dict(requestId='ios-'+'e'*32)))))
        model=SnapshotNative(document=True)
        for _ in range(115):
            event=model.page.event('key-enter',dict(text=secrets.token_hex(4096),key=0,modifiers=0));model.page.event('signal-return',dict(entry=event['sequence']))
        query=dict(schemaVersion=1,commandId='ios-'+'f'*32,action=snapshot.ACTION,runId=RUN,fixtureUrl=URL);model.send(query)
        parts=WorldWebSnapshotParts(owner);reference=parts.write(1,model.last);self.assertGreater(reference['bytes'],1048576)
        paths=parts.paths(reference);self.assertEqual(3,len(paths));sizes=[path.stat().st_size for path in paths]
        self.assertTrue(all(size<1048576 for size in sizes));self.assertGreater(max(sizes),512*1024)
        self.assertEqual(['planned','opened','saved']*3,intents)
        with parts.validation_round():
            refs=parts.project(reference)
            self.assertEqual(model.page.events,parts.read(refs['ledgerAfter'])['events'])
            self.assertEqual(model.last,parts.packet(reference))
        print('WorldWeb Snapshot actual OFS carriers:',sizes,'wire:',reference['bytes'],flush=True)


if __name__=='__main__':unittest.main()
