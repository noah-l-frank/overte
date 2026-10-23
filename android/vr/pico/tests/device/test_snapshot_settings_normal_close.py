"""Fresh pre-input lease through the existing normal Snapshot owners.

Actual owner/input/file/TLS protocols execute continuously in one original
scope. Native VM/Qt/renderer/SDK producers remain explicit host boundaries.
No archived background/Closed fixture is imported into this new run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[5]))
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.snapshot_background_owner import PicoSnapshotBackgroundOwner
from adapters.pico4.snapshot_settings_close import PicoSnapshotSettingsClose
from adapters.chat_journey.source_chunks import json_digest
from self_tests.test_pico_snapshot_return_image import ReturnBoundary
from test_snapshot_settings_baseline import BaselineBoundary
import test_snapshot_upload_owner as upload_prefix


class LiveBackground:
    """Explicit OS/lifecycle consumption model around the actual warm owner."""
    def __init__(self,test,upload):
        self.test,self.parent,self.h=test,upload,test.h
        self.root,self.run,self.binding,self.lock,self.source=upload.lock.path.parent,upload.run,upload.binding,upload.lock,upload.source
        self.foreground=True;self.calls=[]
        self.lifecycle=deepcopy(json.loads(upload.state['frames'][-1]['account']['raw'])['lifecycle'])
        observe=test.observe_account
        def observed(command):
            observe(command);value=json.loads(test.account_raw);value['lifecycle']=deepcopy(self.lifecycle);test.account_raw=json.dumps(value)
        original_foreground=self.h.adb.foreground_package
        def foreground(target):return original_foreground(target) if self.foreground else 'com.android.launcher'
        for change in (patch.object(test,'observe_account',side_effect=observed),patch.object(self.h.adb,'foreground_package',side_effect=foreground)):
            change.start();test.addCleanup(change.stop)
    @property
    def host(self):return self.h.adb.clock
    @host.setter
    def host(self,value):self.h.adb.clock=value
    def epoch(self):return self.h.clock()
    def sleep(self,amount):self.h.adb.sleep(amount)
    def native_guard(self):
        if not self.foreground:raise AssertionError('Native query during original OS background')
        return self.parent.native.guard()
    def status(self,binding):return dict(binding=deepcopy(binding),running=True,foreground=self.foreground)
    def consume(self,operation,binding,*,before_input):
        before_input();self.calls.append(operation);self.foreground=operation=='app.launch'
        self.lifecycle['activations' if self.foreground else 'backgrounds']+=1
    def runtime(self):
        # Match the existing private factory: its already owned warm parent
        # is returned directly. Each actual reader/Close/Return caller keeps
        # its original guard. This model only refuses runtime access in BG.
        if not self.foreground:raise AssertionError('Runtime access during original OS background')
        return self.parent
    def owner(self):
        return PicoSnapshotBackgroundOwner(self.root/'snapshot-background-owner.json',self.run,self.binding,self.lock,self.source,
            self.status,self.consume,self.runtime,monotonic=lambda:self.host,sleep=self.sleep)


class SnapshotSettingsNormalCloseTests(upload_prefix.SnapshotUploadFlowTests):
    # Inherit only the original fixture lifecycle, not its separate warm test.
    test_normal_cancel_still_save_offline_upload_then_success_independent_png_quiet_and_cold_no_resend=None

    def test_new_original_lease_normal_mode_format_and_same_controller_close_then_raw_settings(self):
        # Preserve the original private host archive even on timeout/failure.
        # This is fixture retention, never retirement of an app resource.
        temporary=self.h.h.h.fixture.fixture.temporary
        temporary._finalizer.detach();temporary.cleanup=lambda:None
        root=self.h.lock.path.parent
        print('Retained new Snapshot settings/normal-Close originals:',root,flush=True)
        started=time.monotonic();progress_path=root/'snapshot-settings-normal-close-progress.jsonl'
        descriptor=os.open(progress_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'w') as record:record.write('')
        def progress(label,owner=None):
            # Diagnostic host timings only, never native/fixture authority or
            # a replacement for the original source/ownership journals.
            row=dict(label=label,elapsedSeconds=time.monotonic()-started,stage=None if owner is None else owner.state['stage'],
                frames=0 if owner is None else len(owner.state.get('frames',[])))
            with progress_path.open('a') as record:record.write(json.dumps(row,sort_keys=True)+'\n');record.flush();os.fsync(record.fileno())
        progress('new-run')
        producer=BaselineBoundary(self,host=self.h,entry_source=lambda:deepcopy(self.settings),manager_instance=self.context_birth)
        lease=producer.attach()
        original_umask=os.umask(0o077)
        try:saved=self.saved.ready()
        finally:os.umask(original_umask)
        progress('cancel-still',self.h.owner)
        memo=self.h.owner.reply_grammar
        self.assertIsNotNone(memo.previous)
        self.assertEqual([json_digest(row) for row in self.h.owner.state['replies']],memo.previous['rows'])
        saved.prepare();saved.send();saved.start_read();saved.quiet()
        progress('save',saved)
        for verb in ('share-open','share-cancel','share-open','share-select-owned','upload-fail'):self.h.activate(verb)
        failed=self.owner(saved,'upload-fail');failed.prepare();failed.send();failed.quiet()
        progress('upload-fail',failed)
        self.h.activate('upload');uploaded=self.owner(saved,'upload',failure=failed)
        uploaded.prepare();uploaded.send();uploaded.start_read();uploaded.quiet()
        progress('upload',uploaded)
        self.assertFalse(uploaded.report()['precedingShareQualified'])
        self.assertEqual(3,self.h.owner.disk['snapshotCancelOwnerVersion']);self.assertTrue(lease.report()['originalInputBound'])
        original=deepcopy(lease.packet(lease.state['original']));self.h.activate('background-resume')
        background=LiveBackground(self,uploaded);returned=ReturnBoundary(root,background=background);image=returned.owner();image.acquire()
        progress('background-return-image',returned.bg)
        self.assertEqual(['lifecycle.background','app.launch'],background.calls)
        self.assertIs(returned.bg.live(),uploaded);self.assertIs(image.lock,self.h.lock)
        self.h.activate('close');session=self.h.owner.session;transport=session.transport
        consumed=transport.stage;read=transport.read_status;transition=[None]
        def consume(envelope,profile,*,before_publish=None):
            result=consumed(envelope,profile,before_publish=before_publish)
            if envelope['commands'][0]['operation']=='tablet.close':
                self.h.adb.generation=str(uuid.uuid4());transition[0]=self.h.clock()
            return result
        def status(**options):
            value=read(**options);value['updatedEpochMs']=self.h.clock()
            if options.get('expected_sequence') is None:
                self.assertIsNotNone(transition[0]);value.update(enabled=False,updatedEpochMs=transition[0])
            return value
        with patch.object(transport,'stage',side_effect=consume),patch.object(transport,'read_status',side_effect=status):
            close=self.h.adapter._snapshot_close_owner(self.h.adb.target,self.h.owner.run,self.h.phase,returned.images,parent=image,source_lock=self.h.lock)
            self.assertIs(close.session,session);self.assertIs(close.base,self.h.owner);self.assertIs(close.base.settings_baseline,lease)
            before=len(self.h.adb.inputs);close.prepare();close.restore()
            progress('normal-mode-format',close)
            normal=[command['controlId'] for command in self.h.adb.inputs[before:]]
            self.assertEqual(['snapshot.mode','snapshot.mode.'+close.preference['originalMode'],'snapshot.format','snapshot.format.'+close.preference['originalFormat']],normal)
            close.close();self.assertFalse(self.h.adb.opened);self.assertFalse(original['source']['formatCache']['initialized'])
            progress('normal-controller-close',close)
            result=close.observe_settings();checkpoint=PicoSnapshotSettingsClose(close,root/'snapshot-settings-close.json')
            progress('closed-raw-settings',close)
            current=lease.packet(checkpoint.state['settings']);self.assertTrue(result['originalClosedBookends'])
            self.assertFalse(result['typedSettingsMatchOriginal']);self.assertEqual(['previousStillSnapPath'],result['entryProjectionDifferences'])
            self.assertTrue(result['formatCacheProjectionChanged']);self.assertFalse(result['settingsRestored'])
            self.assertEqual(original,lease.packet(lease.state['original']))
            path=self.h.owner.state['capture']['file']['path'];self.assertEqual(dict(present=True,value=path),current['source']['entries']['previousStillSnapPath'])
            self.assertEqual(original['source']['entries']['alsoTakeAnimatedSnapshot'],current['source']['entries']['alsoTakeAnimatedSnapshot'])
            self.assertEqual(original['source']['entries']['snapshotFormat'],current['source']['entries']['snapshotFormat'])
            self.assertEqual(['tablet.open','tablet.close'],self.h.adb.controllers)
            self.assertEqual([lease.state['envelope'],close.state['controller']['envelope']],transport.envelopes)
            self.assertEqual(lease.state['envelope']['sessionNonce'],close.state['controller']['envelope']['sessionNonce'])
            queries=producer.sequence;inputs=(len(self.h.adb.inputs),len(transport.envelopes));self.assertEqual(result,close.observe_settings())
            self.assertEqual(queries,producer.sequence);self.assertEqual(inputs,(len(self.h.adb.inputs),len(transport.envelopes)))
            self.assertFalse(close.report()['continuousOriginalNeutral']);quiet=close.quiet();self.assertTrue(quiet['continuousOriginalNeutral'])
            progress('closed-quiet',close)
            self.assertFalse(quiet['fullSnapshotRecipe']);self.assertFalse(quiet['completeSettingsBaseline']);self.assertFalse(quiet['globalExportExecutorRetired'])
            self.assertEqual(original,lease.packet(lease.state['original']));self.assertTrue(PrivateFeatureState(root/'snapshot-settings-close.json').read())
        self.assertEqual(0,self.server.internal_errors)


if __name__=='__main__':unittest.main()
