"""Whole-setup/tail original queries with real files and modeled native DTOs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import world_web_keys as keys
from ios.adapters.tablet_web_native_reads import TabletNativeReads
from ios.self_tests.test_ios_world_web_keys import QtKeys,LegacyQtKeys,RUN
from ios.self_tests.test_ios_tablet_web_context import admission_tests
from self_tests import test_native_script_files as file_tests


class TabletNativeReadsTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.qt=QtKeys();self.raw=None;self.sent=[];self.mutate=None
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='existing-sdk',generation=1,targetFingerprint='c'*64)
    def owner(self,kind='keys',**kwargs):return TabletNativeReads(self.root,self.binding,RUN,'primary',kind,self.lock,lambda:True,epoch_ms=lambda:100000,monotonic=lambda:0.,**kwargs)
    def reader(self):
        def send(query):
            self.sent.append(deepcopy(query));value=self.qt.packet();value['requestId']=query['commandId']
            if self.mutate:self.mutate(value)
            self.raw=json.dumps(value)
        return keys.IOSWorldWebKeys(send,lambda:self.raw,lambda:self.qt.epoch,lambda:True,42,monotonic=lambda:0.,sleep=lambda _:None)
    def test_real_query_raw_original_and_source_prefix_reconstruct_without_new_transport(self):
        owner=self.owner();packet=owner.capture(self.reader(),lambda reader:reader.read(RUN));keys.drained(packet)
        self.assertEqual(1,len(self.sent));self.assertEqual(packet,self.owner(historical=True).history()[-1])
        self.qt.finish(self.qt.enter('key-press'));self.qt.finish(self.qt.enter('key-release'))
        after=owner.capture(self.reader(),lambda reader:reader.read(RUN));self.assertEqual(1,len(keys.drained(after)['ended']))
        self.assertEqual(2,len(self.owner(historical=True).history()))
        with self.assertRaises(NativeUIError):self.owner(historical=True).capture(self.reader(),lambda reader:reader.read(RUN))
        self.assertEqual(2,len(self.sent))
    def test_matching_wrong_pid_original_is_retained_and_no_retry_or_false_history_floor(self):
        owner=self.owner();self.mutate=lambda value:value.update(processId=43)
        with self.assertRaises(NativeUIError):owner.capture(self.reader(),lambda reader:reader.read(RUN))
        rebuilt=self.owner();self.assertTrue(rebuilt.blocked);pending=rebuilt.state['pending']
        self.assertEqual('rejected',pending['raws'][0]['outcome']);self.assertIn('"processId": 43',rebuilt.parts.read(pending['raws'][0]['parts']).decode())
        before=len(self.sent)
        with self.assertRaises(NativeUIError):rebuilt.capture(self.reader(),lambda reader:reader.read(RUN))
        self.assertEqual(before,len(self.sent));self.assertEqual([],rebuilt.history())
    def test_unsafe_legacy_keys_never_create_new_raw_parts(self):
        self.qt=LegacyQtKeys();self.qt.finish(self.qt.enter('input-method',commit='Never persist this credential'))
        owner=self.owner()
        with self.assertRaises(NativeUIError):owner.capture(self.reader(),lambda reader:reader.read(RUN))
        self.assertEqual([],list(self.root.glob('*-frame-*')));self.assertEqual(1,len(owner.state['pending']['unsafe']))
        self.assertTrue(self.owner(historical=True).blocked)
    def test_actual_complete_opened_record_flush_recovers_without_native_query_or_inode_change(self):
        owner=self.owner();fsync=os.fsync;lost=[False]
        def flush(fd):
            if not lost[0] and 'tabletweb-aux-keys-frame-' in os.readlink('/proc/self/fd/'+str(fd)):
                lost[0]=True;raise OSError('Actual tail row flush lost')
            return fsync(fd)
        with patch('os.fsync',side_effect=flush),self.assertRaises(OSError):owner.capture(self.reader(),lambda reader:reader.read(RUN))
        rebuilt=self.owner();ref=rebuilt.state['original'];self.assertEqual('opened',ref['phase']);path=rebuilt.frames.path(ref)
        before=path.stat();raw=path.read_bytes();count=len(self.sent);packet=rebuilt.recover_record();keys.drained(packet)
        self.assertEqual(before,path.stat());self.assertEqual(raw,path.read_bytes());self.assertEqual(count,len(self.sent))
    def test_lost_send_is_reconciled_only_from_exact_actual_old_response_without_send_or_freshness(self):
        owner=self.owner();reader=self.reader();send=reader.send
        def lost(query):send(query);raise OSError('Actual send ACK lost after native response')
        reader.send=lost
        with self.assertRaises(NativeUIError):owner.capture(reader,lambda reader:reader.read(RUN))
        before=len(self.sent);rebuilt=self.owner();packet=rebuilt.reconcile(self.reader())
        self.assertEqual(before,len(self.sent));self.assertFalse(rebuilt.blocked)
        row=rebuilt.frames.read(rebuilt.frames.expand(rebuilt.state['records'][0]));self.assertEqual('reconciled',row['status'])
        self.assertFalse(row['sendReturned']);self.assertEqual(packet,self.owner(historical=True).history()[-1])
        current=rebuilt.capture(self.reader(),lambda reader:reader.read(RUN));self.assertGreater(current['sequence'],packet['sequence'])
        self.assertEqual(before+1,len(self.sent))

    def test_native_start_packet_is_saved_as_its_actual_source_and_reconstructs(self):
        from adapters.native_feature_observation import NativeFeatureObservation
        from self_tests import test_native_feature_observation as native_tests
        boundary=native_tests.Boundary()
        boundary.mutate=lambda value:value.update(processId=42)
        reader=NativeFeatureObservation(boundary.send,boundary.original,lambda:20000,lambda:True,42,ios=True,
            monotonic=lambda:0.,sleep=lambda _:None)
        owner=self.owner('native');packet=owner.capture(reader,lambda current:current.read(0))
        self.assertEqual(packet,self.owner('native',historical=True).history()[-1]);self.assertEqual(1,len(boundary.commands))

    def test_original_native_file_readback_and_actual_absence_are_distinct_from_release_ACK(self):
        # Native filesystem operations are modeled by the existing retained
        # fixture producer; the transport owner and host inode checks are real.
        self.binding['processIdentity']='31';native_path=self.root/'native';native_path.mkdir(mode=0o700)
        boundary=file_tests.Boundary(native_path);reader=boundary.native(ios=True);owner=self.owner('files')
        supplied={name:b'// controlled ordinary app input\n' for name in file_tests.NAMES}
        stage=owner.capture(reader,lambda reader:reader.request('stage',RUN,'f'*64,supplied));self.assertEqual({'performed':True},stage['source'])
        current=owner.capture(reader,lambda reader:reader.request('observe',RUN,'f'*64));self.assertTrue(current['source']['exists'])
        owner.capture(reader,lambda reader:reader.request('release',RUN,'f'*64))
        absent=owner.capture(reader,lambda reader:reader.request('observe',RUN,'f'*64));self.assertEqual(dict(exists=False,files=[]),absent['source'])
        self.assertEqual(4,len(self.owner('files',historical=True).history()))


if __name__=='__main__':unittest.main()
