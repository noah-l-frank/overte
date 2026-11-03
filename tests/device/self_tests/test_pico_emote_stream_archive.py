"""Passive real Source4 files/ranges; no current Native or input authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_stream_archive import PicoEmoteStreamArchive
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from self_tests.test_pico_emote_stream_cycle import StreamCycleTests,RETAINED


class StreamArchiveTests(unittest.TestCase):
    setUp=StreamCycleTests.setUp
    finalize=StreamCycleTests.finalize

    def acquire(self):
        m=self.model
        with m.m.s.lock.held():cycle=m.create()
        with cycle.held():cycle.baseline();cycle.sample_pair()
        return cycle

    def reader(self,cycle,role='primary'):
        source=cycle.streams[role]
        value=PicoEmoteStreamArchive(source.store,cycle.originals.path,guard=lambda:True)
        self.addCleanup(value.close);return value

    def counters(self):
        return (list(self.model.m.s.calls),list(self.model.m.input.inputs),list(self.model.m.input.controllers),
            [(deepcopy(producer.controls),producer.getters) for producer in self.model.streams.values()])

    def test_actual_role_and_range_replay_survives_business_source_loss_without_any_getter_or_input(self):
        cycle=self.acquire();before=self.counters();self.model.m.s.okay=False
        for role in ('primary','actor'):
            reader=self.reader(cycle,role);report=reader.report()
            self.assertTrue(report['historicalOnly']);self.assertFalse(report['liveAuthority'])
            self.assertFalse(report['wholeFeatureComplete'] or report['stereoQualified'] or report['independentActorQualified'])
            self.assertFalse(report['pendingOrUncertain']);self.assertEqual(2,report['acceptedRecords'])
            record,packet=reader.original(1)
            self.assertEqual('sample',record['kind']);self.assertEqual(cycle.streams[role].last_sample,packet)
            self.assertNotIn('requestId',packet);self.assertEqual(4,packet['picoRemoteAvatarStreamFrameVersion'])
        self.assertEqual(before,self.counters())

    def test_real_unknown_role_cas_tail_remains_unconfirmed_original_without_becoming_accepted_arm(self):
        m=self.model
        with m.m.s.lock.held():cycle=m.create()
        write=LifecycleProcessFile.write;lost=[]
        def unknown(owner,value,previous):
            write(owner,value,previous)
            if 'emote-remote-owner-' in owner.path.name and len(value.get('chunks',[]))==1 and not lost:
                lost.append(True);raise OSError('Actual original role CAS reply lost')
        with patch.object(LifecycleProcessFile,'write',unknown),self.assertRaises(NativeUIError):
            with cycle.held():cycle.baseline()
        before=self.counters();reader=self.reader(cycle);report=reader.report()
        self.assertEqual(0,report['acceptedRecords']);self.assertEqual(1,report['unconfirmedRecords'])
        self.assertTrue(report['pendingOrUncertain']);original=reader.pending_original(0)
        self.assertTrue(original['unconfirmed']);self.assertFalse(original['liveAuthority'])
        self.assertEqual('arm',original['record']['command']['operation'])
        self.assertEqual('a'*32,original['packet']['streamId'])
        with self.assertRaises(NativeUIError):reader.original(0)
        self.assertEqual(before,self.counters())

    def test_actual_equal_bytes_foreign_range_inode_cannot_be_replayed_as_original_source(self):
        cycle=self.acquire();path=cycle.originals.archive.part_path(0)
        replacement=path.with_name('owned-passive-range-replacement')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600)
        path.rename(path.with_name('owned-retained-original-range.bin'));os.replace(replacement,path)
        before=self.counters()
        with self.assertRaises(NativeUIError):self.reader(cycle)
        self.assertEqual(before,self.counters())

    def test_mutated_passive_packet_memory_never_replaces_actual_retained_original(self):
        cycle=self.acquire();reader=self.reader(cycle);before=self.counters()
        reader.packets[1]['source']['subject']['modelInstance']='0'*32
        with self.assertRaises(NativeUIError):reader.original(1)
        self.assertEqual(before,self.counters())


if __name__=='__main__':unittest.main()
