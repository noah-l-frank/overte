"""Actual unchanged HTTP/AFC widget route and durable Tablet query ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import normal_input
from ios.adapters.tablet_web_widgets import TabletWidgetsReader
from ios.adapters.tablet_web_native_reads import TabletNativeReads
from ios.adapters.tablet_web_runtime import file_responsibilities
from ios.self_tests.test_ios_normal_input import Boundary

RUN='a'*32


class TabletWidgetsTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.native=Boundary();self.native.observed=lambda:dict(schemaVersion=1,instance=self.native.instance,frameSpace='qt-window-logical',processId=42,
            sampleEpochMs=100000,elapsedMs=100,lastSequence=0,tabletShown=False,ready=True,controls=[])
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='owned-session',generation=1,targetFingerprint='c'*64)
        self.opener=patch.object(normal_input,'urlopen',side_effect=self.native.post);self.opener.start();self.addCleanup(self.opener.stop)
    def owner(self,**kwargs):return TabletNativeReads(self.root,self.binding,RUN,'primary','widgets',self.lock,lambda:True,epoch_ms=lambda:90000,monotonic=lambda:0.,**kwargs)
    def reader(self):return TabletWidgetsReader(self.native,'owned-session',self.native.target,self.native.process,lambda:100000,monotonic=lambda:0.,sleep=lambda _:None)
    def test_actual_query_and_original_afc_bytes_saved_before_reader_returns_and_replayed_historically(self):
        owner=self.owner();packet=owner.capture(self.reader(),lambda reader:reader.read())
        self.assertEqual(self.native.receipt,packet);self.assertEqual(1,len(self.native.requests));self.assertEqual('observe',self.native.requests[0]['operation'])
        self.assertEqual([packet],self.owner(historical=True).history());self.assertEqual([],packet['observation']['controls'])
        again=owner.capture(self.reader(),lambda reader:reader.read());self.assertEqual(2,len(self.native.requests))
        self.assertEqual(packet['observation']['lastSequence'],again['observation']['lastSequence'])
        self.assertNotEqual(packet['commandId'],again['commandId'])
    def test_lost_http_ack_reconciles_actual_old_afc_receipt_without_reissuing_normal_ui_request(self):
        owner=self.owner();post=self.native.post
        def lost(request,timeout):post(request,timeout);raise OSError('Actual HTTP return lost after native receipt')
        self.opener.stop();self.opener=patch.object(normal_input,'urlopen',side_effect=lost);self.opener.start()
        with self.assertRaises(OSError):owner.capture(self.reader(),lambda reader:reader.read())
        self.assertEqual(1,len(self.native.requests));rebuilt=self.owner();packet=rebuilt.reconcile(self.reader())
        self.assertEqual(self.native.receipt,packet);self.assertEqual(1,len(self.native.requests));self.assertFalse(rebuilt.blocked)
        row=rebuilt.frames.read(rebuilt.frames.expand(rebuilt.state['records'][-1]));self.assertFalse(row['sendReturned']);self.assertEqual('reconciled',row['status'])
    def test_actual_matching_foreign_pid_receipt_is_retained_but_cannot_qualify_or_retry(self):
        original=self.native.observed;self.native.observed=lambda:dict(original(),processId=43)
        owner=self.owner()
        with self.assertRaises(NativeUIError):owner.capture(self.reader(),lambda reader:reader.read())
        rebuilt=self.owner(historical=True);self.assertTrue(rebuilt.blocked)
        raw=rebuilt.parts.read(rebuilt.state['pending']['raws'][0]['parts']);self.assertEqual(43,json.loads(raw)['observation']['processId'])
        self.assertEqual([],rebuilt.history());self.assertEqual(1,len(self.native.requests))
    def test_actual_normal_script_diagnostic_retains_its_own_query_and_afc_packet(self):
        from ios.self_tests.test_ios_normal_scripts import Native
        from ios.adapters.feature_observation import FeatureObservation
        from ios.adapters import feature_observation
        from ios.adapters.tablet_web_widgets import TabletDiagnosticReader
        native=Native();transport=FeatureObservation(native,'owned-session',native.target,native.process,
            epoch_ms=native.epoch,monotonic=lambda:0.,sleep=lambda _:None)
        reader=TabletDiagnosticReader(transport,42,native.epoch,lambda:0.,lambda _:None)
        owner=TabletNativeReads(self.root,self.binding,RUN,'primary','diagnostic',self.lock,lambda:True,
            epoch_ms=lambda:90000,monotonic=lambda:0.)
        with patch.object(feature_observation,'post_request',side_effect=native.post):packet=owner.capture(reader,lambda current:current.read(0))
        self.assertEqual(native.diagnostic,packet);self.assertEqual(1,len(native.commands));self.assertEqual('normal-feature-observe',native.commands[0]['action'])
        self.assertEqual(packet,TabletNativeReads(self.root,self.binding,RUN,'primary','diagnostic',self.lock,lambda:True,
            epoch_ms=lambda:90000,monotonic=lambda:0.,historical=True).history()[-1])

    def test_release_ack_and_other_scope_absence_do_not_erase_actual_file_responsibility(self):
        def p(scope,operation,source):return dict(runId=scope,operation=operation,source=source)
        packets=[p('first','stage',dict(performed=True)),p('first','release',dict(performed=True)),p('other','observe',dict(exists=False,files=[]))]
        self.assertEqual(['first'],file_responsibilities(packets))
        packets.append(p('first','observe',dict(exists=False,files=[])));self.assertEqual([],file_responsibilities(packets))


if __name__=='__main__':unittest.main()
