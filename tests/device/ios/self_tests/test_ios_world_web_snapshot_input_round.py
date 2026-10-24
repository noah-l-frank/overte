"""An actual post-preparation carrier replacement still blocks the SDK send."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from ios.adapters.world_web_api_clock import scope
from ios.adapters.world_web_identity import WorldWebLease
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


class WorldWebSnapshotInputRoundTests(unittest.TestCase):
    def test_replaced_actual_new_parent_after_full_decoder_before_transport_is_refused_without_POST_or_replay(self):
        whole=ComposedWorldWeb(wall_clock=True);self.addCleanup(whole.close);sdk,source=whole.sdk,whole.source;actions=whole.actions()
        with scope(lambda:sdk.time):actions.act(sdk.activate('open',{}))
        row=actions.state['calls'][-1];lease=WorldWebLease(whole.scope,source,row['before'],row['after']);actions.inputs.entity=lease.packet()['returned']['returned']['entityId']
        before=len(sdk.posted);replaced=[]
        def replace():
            frame=source.frames[-1];path=source.parts.snapshot.paths(frame['nativeSnapshot'])[0];raw=path.read_bytes()
            path.unlink();path.write_bytes(raw);path.chmod(0o600);replaced.append(path)
        sdk.before_post=replace
        with self.assertRaises(NativeUIError):
            with scope(lambda:sdk.time):actions.act(sdk.activate('focus-type',dict(text=context(sdk.run)['unicode'])))
        self.assertEqual(1,len(replaced));self.assertEqual(before,len(sdk.posted))
        self.assertNotEqual('returned',actions.inputs.state['records'][-1]['phase'])
        original_queries=len(sdk.snapshot_native.commands);sdk.before_post=None
        with self.assertRaises(NativeUIError):
            with scope(lambda:sdk.time):actions.act(sdk.activate('focus-type',dict(text=context(sdk.run)['unicode'])))
        self.assertEqual(original_queries,len(sdk.snapshot_native.commands));self.assertEqual(before,len(sdk.posted))


if __name__=='__main__':unittest.main()
