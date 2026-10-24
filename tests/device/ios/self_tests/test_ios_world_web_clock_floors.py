"""Actual prior clock floors save only redundant queries, never terminal clocks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.native_feature_observation import validate
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.self_tests.world_web_sources_fixture import SDK


class WorldWebClockFloorTests(unittest.TestCase):
    @contextmanager
    def owner(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);sdk=SDK();lock=ScriptSourceLock(root/'script-feature-sources.lock');caught=None
            with lock.held():
                try:yield sdk,sdk.owner(PrivateFeatureState(root/'ios-world-web-primary-sources.json'),lock)
                except BaseException as error:caught=error
            if caught is not None:raise caught
    def test_actual_default_query_counts_remain_and_explicit_floor_always_acquires_a_new_terminal(self):
        for name,default_count,floor_count in (('world',2,1),('ledger',3,2)):
            with self.subTest(name=name),self.owner() as (sdk,source):
                reader=source.readers[name];args=(sdk.run,) if name=='world' else (sdk.run,source.phase.fixture_url)
                start=len(sdk.native.commands);reader.read(*args);self.assertEqual(default_count,len(sdk.native.commands)-start)
                floor=source.native.read(source.native.sequence);start=len(sdk.native.commands);original=reader.read(*args,native_before_floor=floor)
                self.assertEqual(floor_count,len(sdk.native.commands)-start);self.assertEqual(sdk.pid,original['processId'])
                self.assertTrue(all(row['commandId']!=floor['requestId'] for row in sdk.native.commands[start:]))
                if name=='world':self.assertIn('nativeBeforeOriginalFloorSha256',reader.acquisition)
    def test_stale_actual_floor_and_foreign_actual_process_cannot_qualify_a_current_read(self):
        with self.owner() as (sdk,source):
            floor=source.native.read(source.native.sequence);sdk.sleep(1.6)
            with self.assertRaises(NativeUIError):source.readers['world'].read(sdk.run,native_before_floor=floor)
        with self.owner() as (sdk,source),self.owner() as (other,_foreign):
            # A genuine separate original process supplies its own native PID.
            other.pid+=1;other.native.mutate=other.clock_packet
            # Make a reader bound to the actual new original PID before its
            # first query; no original DTO is relabelled.
            from adapters.native_feature_observation import NativeFeatureObservation
            native=NativeFeatureObservation(other.native.send,other.native.original,other.tick,lambda:True,other.pid,ios=True,monotonic=lambda:other.time,sleep=other.sleep)
            floor=native.read(0);validate(floor,floor['requestId'],other.pid,floor['capturedEpochMs'])
            before=len(sdk.queries)
            with self.assertRaises(NativeUIError):source.readers['world'].read(sdk.run,native_before_floor=floor)
            self.assertEqual(before,len(sdk.queries))
    def test_whole_floor_is_joined_to_exact_actual_raw_and_same_source_acquisition(self):
        with self.owner() as (_sdk,source):
            old=source.frame(source.capture('first'));reference=source.capture('second');frame=source.frame(reference)
            self.assertEqual(8,len(frame['clockFloors']))
            source.validate_frame(frame,old)
            for fault in ('acquisition','raw','index','terminal'):
                changed=deepcopy(frame);row=changed['clockFloors'][0]
                if fault=='acquisition':row['acquisitionId']=old['clockJoin']['nativeBefore']['requestId']
                elif fault=='raw':row['floor']=deepcopy(old['clockJoin']['nativeAfter'])
                elif fault=='index':row['beforeQueries']+=1
                else:row['afterQueries']=row['beforeQueries']
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate_frame(changed,old)


if __name__=='__main__':unittest.main()
