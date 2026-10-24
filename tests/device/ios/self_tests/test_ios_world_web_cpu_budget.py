"""Real host CPU/storage time stays inside unchanged original/API budgets.

The native/WK/SDK are explicit models. Their monotonic producer includes real
elapsed CPU, Node and durability work before its first original is produced.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time
import unittest
from feature_journeys.fixtures import context
from ios.adapters.world_web_api_clock import scope
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_history import derive
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


class WorldWebCpuBudgetTests(unittest.TestCase):
    def test_actual_open_focus_unicode_submit_with_real_cpu_storage_and_new_native_clocks(self):
        whole=ComposedWorldWeb(wall_clock=True,use_whole_snapshot=True);self.addCleanup(whole.close)
        sdk,source=whole.sdk,whole.source;actions=whole.actions();measurements=[]
        for verb,inputs in [('open',{}),('focus-type',dict(text=context(sdk.run)['unicode'])),('submit',{})]:
            started=time.perf_counter()
            with scope(lambda:sdk.time):
                self.assertEqual(dict(performed=True),actions.act(sdk.activate(verb,inputs)))
                if verb=='open':
                    entry=actions.state['calls'][-1];lease=WorldWebLease(whole.scope,source,entry['before'],entry['after'])
                    actions.inputs.entity=lease.packet()['returned']['returned']['entityId']
            measurements.append((verb,time.perf_counter()-started))
        self.assertTrue(all(elapsed<25 for _verb,elapsed in measurements),measurements)
        original=source.frame(source.state['records'][-1]);dom=original['originals']['document']['source']['dom']
        self.assertEqual(context(sdk.run)['unicode'],next(row['value'] for row in dom['elements'] if row['id']=='text'))
        owned=lease.packet();observed=derive(source.browser_frames(),ownership=owned['files'],directory=owned['directory'],
            entity=owned['returned']['returned']['entityId'],origins=sdk.origins)['public']
        self.assertEqual((1,1,1),(observed['attemptedMessages'],observed['bridgeMessages'],observed['bridgeEchoes']))


if __name__=='__main__':unittest.main()
