"""The real terminal operation retains interpretation scope and live file guards.

Finish's end-proof body is a failing sentinel, never a modeled successful
retirement. Actual packet files, current locks and the production operation
cache execute; no SDK/native source or complete end graph is supplied.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import time
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.terminal import PROFILE
from feature_journeys.witness import Client
from ios.adapters.tablet_web_feature import IOSTabletWebFeature
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime
from ios.adapters.tablet_web_packets import TabletWebPackets
from ios.adapters.tablet_web_process_inventory import TabletWebProcessInventory
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.self_tests import test_ios_tablet_web_packets as fixture


class TabletFinishScopeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.TabletWebPacketsTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        root=self.f.root;self.lock=ScriptSourceLock(root/'script-feature-sources.lock')
        held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.owner=TabletWebPackets(root,fixture.BINDING,fixture.RUN,'primary',fixture.ROOT,31,'sources',
            lambda:self.lock.assert_held() or True,monotonic=lambda:0.,epoch_ms=lambda:120000)
        self.owner.capture(self.f.reader())
        def forbidden(*_args,**_kwargs):self.fail('No SDK/native/session operation is permitted')
        class Adapter:
            _candidate_guard=staticmethod(forbidden)
            _binding=staticmethod(forbidden)
            def state_path(self,_selector):return root/'original-sdk-session.json'
        client=Client(fixture.ROOT.split('/runs/')[0],'a'*64)
        self.feature=IOSTabletWebFeature(IOSTabletWebRuntime(Adapter()),'retained-host-test',client,fixture.RUN,
            'primary',fixture.BINDING,dict(explicitUnadmittedSetup=True),
            dict(primary='http://127.0.0.1:18000',foreign='http://127.0.0.1:18001'),
            monotonic=time.monotonic,epoch_ms=forbidden,sleep=forbidden)
        binding={key:value for key,value in fixture.BINDING.items() if key!='sessionId'}
        binding['sessionSha256']='a'*64
        description=dict(featureTerminalVersion=1,profile=PROFILE,area='tablet-web',runId=fixture.RUN,ticket='b'*32,
            roles={role:dict(binding=binding,heldResources=[],originalSha256=sha*64) for role,sha in (('primary','c'),('actor','d'))})
        self.call=dict(contractVersion=1,runId=fixture.RUN,stage='finish',seal=dict(featureTerminalSealVersion=1,
            description=description,windowSha256='e'*64,liveOriginalSha256='f'*64))

    def test_same_terminal_operation_cache_never_hides_rewritten_actual_original(self):
        feature=self.feature;visits=[];queries=len(self.f.sends)
        def unfinished(actual,seal):
            self.assertIs(feature,actual);visits.append(actual.record_cache)
            with read_scope(fresh=True) as first:before=self.owner.history()
            self.assertTrue(first);reads_after_first=reads.call_count;self.assertGreater(reads_after_first,0)
            with actual.operation():
                self.assertIs(visits[0],actual.record_cache)
                with read_scope(fresh=True) as second:after=self.owner.history()
            self.assertEqual(before,after);self.assertEqual(first,second)
            self.assertEqual(reads_after_first,reads.call_count)
            self.assertEqual(1,len(actual.record_cache.originals.rows))
            path=next(iter(next(iter(actual.record_cache.originals.rows.values()))[1]))
            info=path.stat();raw=path.read_bytes();path.write_bytes(raw)
            os.utime(path,ns=(info.st_atime_ns,info.st_mtime_ns))
            self.assertEqual(info.st_ino,path.stat().st_ino);self.assertEqual(raw,path.read_bytes())
            self.owner.history()  # Must raise before any end result can escape.
            self.fail('Rewritten original escaped the production cache guard')
        with patch.object(self.owner.segments,'read',wraps=self.owner.segments.read) as reads,patch(
                'ios.adapters.tablet_web_terminal_finish.finish',side_effect=unfinished) as finish:
            with self.assertRaises(NativeUIError):feature.terminal(self.call)
        self.assertEqual(1,finish.call_count);self.assertEqual(1,len(visits));self.assertIsNone(feature.deadline)
        self.assertEqual(queries,len(self.f.sends));self.lock.assert_held()
        self.assertFalse(feature.store.path.exists());self.assertEqual([],list(self.f.root.glob('tabletweb-*end*')))

    def test_same_operation_record_cache_does_not_cache_original_process_inventory_reads(self):
        feature=self.feature
        inventory=TabletWebProcessInventory(self.f.root,fixture.BINDING,fixture.RUN,self.lock,
            lambda:self.lock.assert_held() or True,monotonic=time.monotonic)
        rows={str(self.f.root):{name:list(value) for name,value in EmoteOriginalLease(self.f.root,inventory.paths()).rows.items()}}
        reference=inventory.write(rows);queries=len(self.f.sends)
        def unfinished(actual,_seal):
            self.owner.history();self.assertEqual(1,len(actual.record_cache.originals.rows))
            count=reads.call_count
            with read_scope(fresh=True) as first:self.assertEqual(rows,inventory.read(reference))
            self.assertEqual(count+1,reads.call_count)
            with read_scope(fresh=True) as second:self.assertEqual(rows,inventory.read(reference))
            self.assertEqual(count+2,reads.call_count);self.assertEqual(first,second)
            path=inventory.frames.path(inventory.state['chunks'][0]);info=path.stat();raw=path.read_bytes()
            path.write_bytes(raw);os.utime(path,ns=(info.st_atime_ns,info.st_mtime_ns))
            self.assertEqual(info.st_ino,path.stat().st_ino);self.assertEqual(raw,path.read_bytes())
            inventory.read(reference)
            self.fail('Operation cache hid the original process inventory rewrite')
        with patch.object(inventory.frames,'read',wraps=inventory.frames.read) as reads,patch(
                'ios.adapters.tablet_web_terminal_finish.finish',side_effect=unfinished) as finish:
            with self.assertRaises(NativeUIError):feature.terminal(self.call)
        self.assertEqual(1,finish.call_count);self.assertEqual(queries,len(self.f.sends));self.assertIsNone(feature.deadline)
        self.assertFalse(feature.store.path.exists());self.assertEqual([],list(self.f.root.glob('tabletweb-*end*')))


if __name__=='__main__':unittest.main()
