"""Real Photos factory/installed-code gate; SDK and OS producers are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_photos_runtime import IOSSnapshotPhotosRuntime
from ios.self_tests.snapshot_photos_domain import SnapshotPhotosDomain,RUN
from ios.self_tests import test_ios_installed_code as installed_fixture


class SnapshotPhotosFactoryTests(unittest.TestCase):
    def domain(self):
        d=SnapshotPhotosDomain(self);gate=installed_fixture.InstalledCodeTests();gate.setUp();self.addCleanup(gate.doCleanups)
        binding=deepcopy(d.main.ctx.binding);scope={key:value for key,value in binding.items() if key!='processIdentity'}
        gate.scope=scope;gate.binding=gate.make();gate.active()
        process=deepcopy(gate.process);gate.binding.process=lambda:dict(process,foreground=d.main_foreground)
        state=dict(sessionId=binding['sessionId'],generation=binding['generation'],targetFingerprint=binding['targetFingerprint'])
        target=dict(appId=gate.native.bundle['bundleId'],capabilities={'appium:udid':'HOST-PHYSICAL-DEVICE-MODEL'})
        class Client:
            def execute(self,session,operation,query):
                if operation=='mobile: activateApp':
                    if query!=dict(bundleId=target['appId']):raise AssertionError('Unexpected app activation')
                    d.main_foreground=True;d.helper.foreground=False;return True
                raise AssertionError('Factory unexpectedly queried native sources')
        class Runtime(IOSSnapshotPhotosRuntime):
            def _existing(self,selector):return Client(),binding['sessionId'],deepcopy(state),deepcopy(target),deepcopy(scope)
            def _sources(self,selector):
                gate.binding.continuity();raise AssertionError('Factory test does not allow native/UI reads')
        adapter=SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda *_:gate.binding,_session_recreation_forbidden=False,
            state_path=lambda _:d.main.ctx.root/'session.json')
        runtime=Runtime(adapter)
        companion=dict(client=d.helper,sessionStore=d.helper.session,target=d.helper.target,binding=d.helper_binding,
            artifactPath=d.helper.ipa,admissionStore=d.admission_store)
        return d,gate,state,runtime,companion

    def test_factory_retains_two_actual_locks_real_installed_gate_and_exact_phase_url(self):
        d,gate,_state,runtime,companion=self.domain()
        with runtime.photos_owner('primary',RUN,d.client(),companion,
            epoch_ms=d.main.epoch,monotonic=d.main.mono,sleep=d.main.sleep) as owner:
            self.assertIs(owner.primary.gate,gate.binding);owner.lock.assert_held();owner.companion_lock.assert_held();owner.guard()
            self.assertEqual(owner.fixture_url,owner.companion.admission.fixture_url)
            self.assertTrue(runtime.adapter._session_recreation_forbidden)
            d.main_foreground=False;d.helper.foreground=True
            self.assertFalse(owner.primary.probe(False)['process']['foreground'])
            with self.assertRaises((NativeUIError,ValueError)):owner.primary.foreground_sources()
            d.main_foreground=True;d.helper.foreground=False
        self.assertFalse(runtime.adapter._session_recreation_forbidden);self.assertEqual(0,d.save_count)

    def test_changed_original_OS_source_or_session_generation_blocks_before_any_save(self):
        for fault in ('main-source','main-session','companion-boolean-generation'):
            with self.subTest(fault=fault):
                d,gate,state,runtime,companion=self.domain()
                with self.assertRaises((NativeUIError,ValueError)):
                    with runtime.photos_owner('primary','a'*32,d.client(),companion,epoch_ms=d.main.epoch,monotonic=d.main.mono,sleep=d.main.sleep) as owner:
                        if fault=='main-source':gate.source['instance']='0'*32
                        elif fault=='main-session':state['generation']=True
                        else:
                            old=d.helper.session.read();d.helper.session.write(dict(old,generation=True),old)
                        owner.guard()
                self.assertEqual(0,d.save_count);self.assertFalse(d.library)

    def test_companion_original_path_reader_rejects_unowned_paths_before_any_AFC_pull(self):
        d,_gate,_state,runtime,companion=self.domain()
        with runtime.photos_owner('primary','a'*32,d.client(),companion,epoch_ms=d.main.epoch,monotonic=d.main.mono,sleep=d.main.sleep) as owner:
            d.main_foreground=False;d.helper.foreground=True;reader=owner.companion.foreground_runtime()
            before=len(d.helper.sdk)
            for path,limit in (('../original.bytes',262144),('snapshot-photos-'+'a'*32+'/original.bytes',262144),('snapshot-photos-chunk.json',True),('snapshot-photos-chunk.json',720897)):
                with self.subTest(path=path,limit=limit),self.assertRaises(NativeUIError):reader.original_path(path,limit)
            self.assertEqual(before,len(d.helper.sdk));d.main_foreground=True;d.helper.foreground=False


if __name__=='__main__':unittest.main()
