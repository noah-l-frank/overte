"""Original returned-null dialog and complete no-worker partial-setup proof.

Native/Script execution is modeled. Generated native file bytes, existing DTO
validators and the partial cleanup join execute unchanged; no ACK is a result.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_cleanup import unloaded_original
from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles
from ios.self_tests.tablet_web_whole_fixture import TabletWholeBoundary
from ios.self_tests.test_ios_emote_marker_files import NativeBoundary
from ios.self_tests.test_ios_script_dialogs import events


class TabletUnloadedCleanupTests(unittest.TestCase):
    def setUp(self):
        self.boundary=TabletWholeBoundary(self);b=self.boundary;native=NativeBoundary()
        store=PrivateFeatureState(b.root/'unloaded-files.json');files=OwnedTabletWebAppFiles(native,store,b.binding)
        self.metadata=files.reserve_app(b.source.run,b.source.fixture,'b'*32);self.directory=files.stage_reserved()
        scripts=b.runtime.read_auxiliary('scripts');terminal=b.runtime.read_auxiliary('terminal');self.dialog_before=b.runtime.read_auxiliary('dialogs')
        def original_dialog(query,value):
            if query['action']=='feature-ios-script-dialogs':
                rows=events(self.directory+'/script.js',True,None)
                for row in rows:row.update(capturedEpochMs=value['clockBefore']['epochMs'],monotonicMs=value['clockBefore']['monotonicMs'])
                value['source'].update(eventSequence=4,events=rows)
        b.force=original_dialog;dialog=b.runtime.read_auxiliary('dialogs');b.force=None
        self.current=dict(row=dict(source=dict(observation=dict(binding=b.binding))),packets=dict(scripts=scripts,terminal=terminal,dialogs=dialog))
        self.current['packets']['files:'+self.metadata['runId']]=dict(schemaVersion=1,requestId='ios-'+'e'*32,instance='f'*32,sequence=1,
            processId=42,requestedEpochMs=b.epoch(),capturedEpochMs=b.epoch(),runId=self.metadata['runId'],operation='observe',
            source=native.request('observe',self.metadata['runId'],self.metadata['ownerToken']))
        for row in self.current['packets']['files:'+self.metadata['runId']]['source']['files']:
            raw=base64.b64decode(row['base64'],validate=True);row.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    def test_original_null_selected_file_and_actual_cancel_can_retire_only_an_unloaded_scope(self):
        actual=unloaded_original(self.current,self.metadata,self.directory,self.dialog_before);self.assertEqual(self.metadata['runId'],actual['storageRun'])
        self.assertEqual('a'*32,actual['dialog']);self.assertNotIn('loaded',actual)
        current=deepcopy(self.current);rows=events()
        for row in rows:row.update(capturedEpochMs=current['packets']['dialogs']['clockBefore']['epochMs'],monotonicMs=current['packets']['dialogs']['clockBefore']['monotonicMs'])
        current['packets']['dialogs']['source']['events']=rows
        self.assertEqual(actual['storageRun'],unloaded_original(current,self.metadata,self.directory,self.dialog_before)['storageRun'])
    def test_live_or_unjoined_returned_manager_worker_missing_callback_or_foreign_file_scope_blocks(self):
        b=self.boundary;manager=dict(instance='1'*32,assigned=True,url=self.directory+'/script.js',loadGeneration=1,assignedEpochMs=19000)
        for fault in ('dialog','returned-manager','worker','membership','callback','terminal-complete','directory'):
            current=deepcopy(self.current);baseline=deepcopy(self.dialog_before)
            if fault=='dialog':baseline=deepcopy(current['packets']['dialogs'])
            elif fault=='returned-manager':current['packets']['dialogs']['source']['events'][2]['manager']=manager
            elif fault=='worker':
                current['packets']['terminal']['source'].update(eventSequence=1,events=[dict(eventSequence=1,capturedEpochMs=20001,monotonicMs=1001,
                    kind='thread-bound',threadInstance='2'*32,manager=manager,code=None,work=None)])
            elif fault=='membership':current['packets']['scripts']['source']['membership'].update(revision=1,managers=[manager])
            elif fault=='callback':
                rows=current['packets']['dialogs']['source']['events'];rows.pop(2);rows[-1]['eventSequence']=3
                current['packets']['dialogs']['source']['eventSequence']=3
            elif fault=='terminal-complete':current['packets']['terminal']['source']['complete']=False
            else:current['packets']['files:'+self.metadata['runId']]['source']['directory']='file:///private/foreign'
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):unloaded_original(current,self.metadata,self.directory,baseline)


if __name__=='__main__':unittest.main()
