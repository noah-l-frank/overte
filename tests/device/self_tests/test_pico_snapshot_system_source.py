"""Original OS/owner seams: passive scope only, never Pico chooser input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from contextlib import contextmanager
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from adapters.pico4.snapshot_system_source import PicoSnapshotSystemSource,RESOLVE,current,resolved

BINDING=dict(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='123:1000',sessionId='original',generation=0,targetFingerprint='3'*64)
CHOOSER='com.android.intentresolver/com.android.intentresolver.ChooserActivity'
APP='org.overte.pico/org.overte.android.OverteActivity'


class Boundary:
    def __init__(self):
        self.authorized=True;self.foreground=True;self.active=APP;self.host=1.;self.epoch=20000;self.calls=[];self.late=lambda:None
        self.binding=deepcopy(BINDING);self.chooser=CHOOSER;self.uid=1001
    def status(self):
        self.calls.append('status');self.late();return dict(binding=deepcopy(self.binding),foreground=self.foreground,running=True)
    def shell(self,*args):
        self.calls.append(args)
        if args==RESOLVE:return self.chooser+'\n'
        if args==('dumpsys','activity','activities'):return '  topResumedActivity: ActivityRecord{a u0 '+self.active+' t4}\n'
        if args[:4]==('cmd','package','list','packages'):
            return 'package:'+args[-1]+' uid:'+str(1000 if args[-1]=='org.overte.pico' else self.uid)+'\n'
        raise AssertionError('No input, private app query or unqualified OS operation is permitted')


class SnapshotSystemSourceTests(unittest.TestCase):
    @contextmanager
    def scope(self):
        with tempfile.TemporaryDirectory(prefix='pico-snapshot-os-') as directory:
            root=Path(directory);root.chmod(0o700);lock=ScriptSourceLock(root/'script-sources.lock');boundary=Boundary()
            with lock.held():
                source=PicoSnapshotSystemSource(BINDING,lock,boundary.status,boundary.shell,lambda:boundary.epoch,
                    lambda:boundary.authorized,monotonic=lambda:boundary.host)
                yield source,boundary
    def test_same_original_scope_observes_foreground_chooser_and_return_without_input_or_qt(self):
        with self.scope() as (source,boundary):
            chooser=source.prepare();self.assertEqual(CHOOSER,chooser['component']);self.assertEqual(1001,chooser['uid'])
            first=source.capture();boundary.foreground=False;boundary.active=CHOOSER;during=source.capture()
            boundary.foreground=True;boundary.active=APP;after=source.capture()
            self.assertEqual([True,False,True],[row['foreground'] for row in (first,during,after)])
            self.assertEqual(CHOOSER,during['component']);self.assertEqual(1,during['picoSnapshotOsSourceVersion'])
            during['chooser']['uid']=9;after['finalSource']['activityRaw']='caller mutation'
            self.assertEqual(1001,source.last['chooser']['uid']);self.assertNotEqual('caller mutation',source.last['finalSource']['activityRaw'])
            self.assertTrue(all(item=='status' or item in (RESOLVE,('dumpsys','activity','activities')) or item[:4]==('cmd','package','list','packages') for item in boundary.calls))
    def test_foreign_or_receiver_activity_and_same_package_other_activity_are_not_admitted(self):
        for active in ('org.overte.e2e.snapshotreceiver/.SnapshotReceiverActivity','foreign.app/.Activity',CHOOSER+'Other'):
            with self.scope() as (source,boundary):
                source.prepare();boundary.foreground=False;boundary.active=active
                with self.subTest(active=active),self.assertRaises(NativeUIError):source.capture()
                self.assertIsNone(source.last)
    def test_owner_authority_must_exist_before_any_sdk_or_os_observation(self):
        for value in (False,None,1):
            with self.scope() as (source,boundary):
                boundary.authorized=value
                with self.subTest(value=value),self.assertRaises(NativeUIError):source.prepare()
                self.assertEqual([],boundary.calls)
    def test_old_scope_cannot_reacquire_same_lock_inode_after_release(self):
        with self.scope() as (source,boundary):source.prepare()
        # The original acquisition is gone; even the same object must not
        # become a new OS handoff authority after a release/reacquisition.
        with self.assertRaises(NativeUIError):source.capture()
    def test_release_reacquire_without_unlink_still_invalidates_original_scope(self):
        with tempfile.TemporaryDirectory(prefix='pico-snapshot-os-relock-') as directory:
            root=Path(directory);root.chmod(0o700);lock=ScriptSourceLock(root/'script-sources.lock');b=Boundary()
            with lock.held():
                source=PicoSnapshotSystemSource(BINDING,lock,b.status,b.shell,lambda:b.epoch,lambda:True,monotonic=lambda:b.host);source.prepare()
            before=len(b.calls)
            with lock.held(),self.assertRaises(NativeUIError):source.capture()
            self.assertEqual(before,len(b.calls))
    def test_changed_binding_uid_resolver_or_final_owner_and_frozen_clock_age_are_rejected(self):
        for fault in ('binding','uid','resolver','authority','native-age','host-age','late-window'):
            with self.scope() as (source,b):
                source.prepare();b.foreground=False;b.active=CHOOSER;calls=0
                def late():
                    nonlocal calls
                    calls+=1
                    if fault=='binding':b.binding['processIdentity']='123:1001'
                    elif fault=='uid':b.uid=1002
                    elif fault=='resolver':b.chooser=CHOOSER+'Other'
                    elif calls==2:
                        if fault=='authority':b.authorized=False
                        elif fault=='native-age':b.epoch+=2000
                        elif fault=='host-age':b.host+=2
                        else:b.active=CHOOSER+'Foreign'
                b.late=late
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.capture()
                self.assertIsNone(source.last)
    def test_late_copy_work_with_frozen_native_clock_is_covered_before_source_publication(self):
        from unittest.mock import patch
        import adapters.pico4.snapshot_system_source as module
        for operation in ('prepare','capture'):
            with self.scope() as (source,b):
                if operation=='capture':source.prepare()
                copy=module.deepcopy
                def slow(value):
                    result=copy(value)
                    if type(value) is dict and ('resolutionRaw' in value or 'picoSnapshotOsSourceVersion' in value):b.host+=2
                    return result
                with patch.object(module,'deepcopy',side_effect=slow),self.subTest(operation=operation),self.assertRaises(NativeUIError):getattr(source,operation)()
                self.assertIsNone(source.last)
                if operation=='prepare':self.assertIsNone(source.chooser)
    def test_last_prepare_sdk_guard_cannot_change_original_resolver_uid_or_foreground_activity(self):
        for fault in ('uid','resolver','activity'):
            with self.scope() as (source,b):
                calls=0
                def late():
                    nonlocal calls
                    calls+=1
                    if calls==2:
                        if fault=='uid':b.uid=1002
                        elif fault=='resolver':b.chooser=CHOOSER+'Other'
                        else:b.active=APP+'Other'
                b.late=late
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.prepare()
                self.assertIsNone(source.chooser)
    def test_ambiguous_resumed_activity_or_malformed_resolution_cannot_be_inferred(self):
        for raw in ('topResumedActivity: ActivityRecord{a u0 '+APP+' t1}\nmResumedActivity: ActivityRecord{b u0 '+CHOOSER+' t2}',
                'mResumedActivity: null',''):
            with self.subTest(raw=raw),self.assertRaises(NativeUIError):current(raw)
        for raw in ('No activity found','org.overte.pico/.Activity',CHOOSER+'\nunexpected'):
            with self.subTest(raw=raw),self.assertRaises(NativeUIError):resolved(raw)
