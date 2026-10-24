"""Historical Pending2 quiet is not a new current observation after World2."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_close import run_close
from self_tests import test_pico_lifecycle_close as original


class LifecyclePendingHistoricalQuietTests(unittest.TestCase):
    def test_actual_second_world_keeps_original_v2_quiet_grammar_without_current_replay(self):
        fixture=original.LifecycleCloseTests();self.addCleanup(fixture.doCleanups);fixture.setUp()
        pending=fixture.pending;self.assertEqual(2,pending.version)
        state=deepcopy(pending.state);row=state['frames'][state['quiet'][-1]]
        before=pending.store.path.read_bytes()
        run_close(fixture.owner);fixture.world.world_input()
        self.assertEqual(2,len(fixture.world.state['attempts']))
        calls=[]
        for target,name in ((fixture.world,'acquire'),(pending.pending,'send')):
            callback=getattr(target,name)
            def record(*args,_original=callback,_name=name,**kwargs):
                calls.append(_name);return _original(*args,**kwargs)
            setattr(target,name,record)
        with fixture.lock.held():pending.load()
        self.assertEqual(before,pending.store.path.read_bytes())
        self.assertEqual(state,pending.state)
        pending.quiet_packet(state,row,historical=True)
        with self.assertRaises(NativeUIError):pending.quiet_packet(state,row)
        self.assertEqual([],calls)


if __name__=='__main__':unittest.main()
