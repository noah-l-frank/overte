"""Actual immutable emitter packet graph and source-reset recovery boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_packets import TabletWebPackets
from ios.adapters import web_script_emissions as emission
from ios.self_tests.test_ios_web_script_emissions import Emitter
from ios.self_tests.test_ios_tablet_web_packets import BINDING,RUN,ROOT


class TabletWebEmissionPacketTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.native=Emitter();self.held=self.native.good();self.queries=[];self.raw=None;self.reset=False
    def owner(self,**kwargs):return TabletWebPackets(self.root,BINDING,RUN,'primary',ROOT,31,'emissions',lambda:True,monotonic=lambda:0.,epoch_ms=lambda:120000,**kwargs)
    def reader(self):
        def send(query):
            self.queries.append(query);value=self.native.snapshot();value['commandId']=query['commandId']
            if self.reset:value['instance']='0'*32
            self.raw=json.dumps(value)
        return emission.IOSWebScriptEmissions(send,lambda:self.raw,lambda:self.native.now,lambda:True,31,monotonic=lambda:0.)
    def test_exact_actual_emitter_caller_stack_and_weak_capture_bytes_survive_reconstruction(self):
        owner=self.owner();value=owner.capture(self.reader());rebuilt=self.owner(historical=True);self.assertEqual([value],rebuilt.history())
        record=rebuilt.originals.read(rebuilt.originals.expand(rebuilt.state['records'][0]));raw=rebuilt.segments.read(record['raws'][0]['segments'])
        self.assertEqual(self.raw.encode(),raw);self.assertEqual(value,json.loads(raw));self.assertEqual('emissions',record['raws'][0]['segments']['label'])
        sink=value['sinks'][-1];self.assertEqual(self.held[0]['id'],emission.selected(value,sink,self.native.buttons.profile(),self.native.locations())['id'])
        self.assertTrue(value['queues'][0]['captureAlive']);self.assertEqual(1,len(self.queries))
        with self.assertRaises(NativeUIError):rebuilt.capture(self.reader())
    def test_safe_matching_source_birth_reset_is_retained_unchanged_and_permanently_blocks_new_source(self):
        owner=self.owner();owner.capture(self.reader());self.reset=True
        with self.assertRaises(NativeUIError):owner.capture(self.reader())
        rebuilt=self.owner();self.assertTrue(rebuilt.blocked);pending=rebuilt.state['pending'];self.assertEqual('rejected',pending['raws'][0]['outcome'])
        raw=rebuilt.segments.read(pending['raws'][0]['segments']);self.assertEqual(self.raw.encode(),raw);self.assertEqual('0'*32,json.loads(raw)['instance'])
        rebuilt.archive_pending(abandon=True);blocked=self.owner();self.assertTrue(blocked.blocked)
        with self.assertRaises(NativeUIError):blocked.capture(self.reader())
        self.assertEqual(2,len(self.queries));self.assertEqual(1,len(blocked.history()))


if __name__=='__main__':unittest.main()
