"""Actual Share factory/installed-code gate with explicit fake OS producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_share_runtime import IOSSnapshotShareRuntime
from ios.self_tests.snapshot_share_domain import SnapshotShareDomain,RUN,DEVICE,SYSTEM_UI
from ios.self_tests import test_ios_installed_code as installed_fixture


class SnapshotShareFactoryTests(unittest.TestCase):
    def domain(self):
        d=SnapshotShareDomain(self);gate=installed_fixture.InstalledCodeTests();gate.setUp();self.addCleanup(gate.doCleanups)
        binding=deepcopy(d.main.ctx.binding);scope={key:value for key,value in binding.items() if key!='processIdentity'}
        gate.scope=scope;gate.binding=gate.make();gate.active()
        process=deepcopy(gate.process);gate.binding.process=lambda:dict(process,foreground=d.main_foreground)
        state=dict(sessionId=binding['sessionId'],generation=binding['generation'],targetFingerprint=binding['targetFingerprint'])
        target=dict(appId=gate.native.bundle['bundleId'],capabilities={'appium:udid':DEVICE})
        class Client:
            def execute(self,*_args):raise AssertionError('Factory must not send any UI, activation or native command')
        class Runtime(IOSSnapshotShareRuntime):
            def _existing(self,_selector):return Client(),binding['sessionId'],deepcopy(state),deepcopy(target),deepcopy(scope)
            def _sources(self,_selector):
                gate.binding.continuity();raise AssertionError('No foreground native source requested by factory')
        adapter=SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda *_:gate.binding,_session_recreation_forbidden=False,
            state_path=lambda _:d.main.ctx.root/'session.json')
        archive=dict(client=d.archive,sessionStore=d.archive.session,target=d.archive.target,binding=d.archive.binding,
            artifactPath=d.archive.ipa,admissionStore=d.archive.admission_store)
        return d,gate,state,Runtime(adapter),archive

    def test_actual_installed_binding_both_locks_and_phase_admission_without_input_or_recreation(self):
        d,gate,_state,runtime,archive=self.domain()
        with runtime.share_owner('primary',RUN,d.client(),archive,SYSTEM_UI,epoch_ms=d.main.epoch,monotonic=d.main.mono,sleep=d.main.sleep) as owner:
            self.assertIs(gate.binding,owner.primary.gate);owner.lock.assert_held();owner.archive_lock.assert_held();owner.guard()
            self.assertEqual(owner.fixture_url,owner.archive.admission.fixture_url);self.assertTrue(runtime.adapter._session_recreation_forbidden)
            d.main_foreground=False;d.archive.foreground=True
            with self.assertRaises(NativeUIError):owner.primary.foreground_sources()
            d.main_foreground=True;d.archive.foreground=False
        self.assertFalse(runtime.adapter._session_recreation_forbidden);self.assertEqual(0,d.share_count)

    def test_changed_actual_installed_source_or_original_session_blocks_before_any_share(self):
        for fault in ('main-source','main-session','archive-session'):
            with self.subTest(fault=fault):
                d,gate,state,runtime,archive=self.domain()
                with self.assertRaises((NativeUIError,ValueError)):
                    with runtime.share_owner('primary',RUN,d.client(),archive,SYSTEM_UI,epoch_ms=d.main.epoch,monotonic=d.main.mono,sleep=d.main.sleep) as owner:
                        if fault=='main-source':gate.source['instance']='0'*32
                        elif fault=='main-session':state['generation']=True
                        else:
                            old=d.archive.session.read();d.archive.session.write(dict(old,generation=True),old)
                        owner.guard()
                self.assertEqual(0,d.share_count);self.assertEqual(0,d.archive.read_count)

    def test_AFC_reader_rejects_other_run_raw_payload_and_boolean_limit_without_pull(self):
        d,_gate,_state,runtime,archive=self.domain()
        with runtime.share_owner('primary',RUN,d.client(),archive,SYSTEM_UI,epoch_ms=d.main.epoch,monotonic=d.main.mono,sleep=d.main.sleep) as owner:
            d.main_foreground=False;d.archive.foreground=True;reader=owner.archive_runtime();before=len(d.archive.sdk)
            for path,limit in (('../original.bytes',262144),('snapshot-share-'+RUN+'/original.bytes',262144),
                ('snapshot-share-'+'0'*32+'/original-extension.json',262144),('snapshot-share-chunk.json',True),('snapshot-share-chunk.json',720897)):
                with self.subTest(path=path,limit=limit),self.assertRaises(NativeUIError):reader.original_path(path,limit)
            self.assertEqual(before,len(d.archive.sdk));d.main_foreground=True;d.archive.foreground=False


if __name__=='__main__':unittest.main()
