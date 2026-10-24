"""Source5 UIKit floors join original native PID/birth/epoch before SDK POST."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.self_tests.world_web_sources_fixture import SDK


class WorldWebGeometryFloorTests(unittest.TestCase):
    def test_stale_future_foreign_pid_birth_or_candidate_native_floor_blocks_actual_uikit_send(self):
        for fault in ('stale','future','pid','birth','candidate','old-acquisition'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);root.chmod(0o700);lock=ScriptSourceLock(root/'script-feature-sources.lock');sdk=SDK();sdk.use_snapshot=True;sdk.use_whole_snapshot=True
                with lock.held():
                    owner=sdk.owner(PrivateFeatureState(root/'ios-world-web-primary-sources.json'),lock);capture=owner.capture_widgets
                    def mutate():
                        capture();pending=owner.state['pending'];row=pending['nativeQueries'][-1];raw=json.loads(row['raws'][-1])
                        if fault in ('stale','future'):raw['capturedEpochMs']+=(-2000 if fault=='stale' else 2000)
                        elif fault=='pid':raw['processId']=99
                        elif fault=='birth':owner.native.instance='f'*32
                        elif fault=='candidate':owner.guard=lambda:False
                        else:pending['start']['nativeBefore']['instance']='f'*32
                        row['raws'][-1]=json.dumps(raw)
                    owner.capture_widgets=mutate
                    with self.assertRaises(NativeUIError):owner.capture('rejected-floor')
                    self.assertNotIn('uikit',sdk.queries)
                    self.assertEqual(1 if fault=='candidate' else 0,len(owner.state['pending']['geometryQueries']))


if __name__=='__main__':unittest.main()
