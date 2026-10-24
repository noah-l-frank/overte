"""Original historical background pairs share one unchanged source read round."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_api_clock import scope
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


class WorldWebBackgroundRoundTests(unittest.TestCase):
    def test_actual_normal_home_resume_and_unchanged_pair_decoder_reads_full_graph_once_then_rejects_replaced_old_carrier(self):
        whole=ComposedWorldWeb(wall_clock=True);self.addCleanup(whole.close);sdk,source=whole.sdk,whole.source;actions=whole.actions()
        with scope(lambda:sdk.time):actions.act(sdk.activate('open',{}))
        with scope(lambda:sdk.time):actions.act(sdk.activate('background-resume',{}))
        background=actions.background;before,after=background.state['before'],background.state['after']
        decode=source._decode
        with patch.object(source,'_decode',wraps=decode) as actual:
            background.completed(before,after);self.assertEqual(1,actual.call_count)
            self.assertEqual(background.state,background.decode(background.previous));self.assertEqual(2,actual.call_count)
        outward=background.decode(background.previous);outward['phase']='background-issued';self.assertEqual('observed',background.decode(background.previous)['phase'])
        original=source.frame(before);path=source.parts.snapshot.paths(original['nativeSnapshot'])[0];raw=path.read_bytes()
        path.unlink();path.write_bytes(raw);path.chmod(0o600);queries=len(sdk.snapshot_native.commands)
        with self.assertRaises(NativeUIError):background.decode(background.previous)
        self.assertEqual(queries,len(sdk.snapshot_native.commands))


if __name__=='__main__':unittest.main()
