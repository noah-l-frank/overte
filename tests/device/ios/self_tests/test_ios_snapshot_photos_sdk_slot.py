"""Isolated SDK-slot metadata gates; no SDK/admission/end fact is constructed."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.snapshot_photos_end_context import SnapshotPhotosEndContext
from ios.adapters.snapshot_photos_end_owner import end_record


class SnapshotPhotosSDKSlotTests(unittest.TestCase):
    def component(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        artifact=root/'metadata-artifact';artifact.write_bytes(b'Isolated file-stat model; no signed app admission');artifact.chmod(0o600)
        target=dict(platform='ios',physical=True,appId='org.example.photos',serverUrl='http://metadata.invalid')
        binding=dict(sourceRevision='a'*40,artifactSha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),targetFingerprint=digest(target),
            processIdentity='84',sessionId='metadata-slot',generation=3)
        state={key:binding[key] for key in ('sessionId','generation','targetFingerprint')};store=PrivateFeatureState(root/'session.json');store.write(state,None)
        ctx=object.__new__(SnapshotPhotosEndContext);ctx.session_store=store;ctx.target=target;ctx.binding=binding;ctx.artifact_path=artifact
        ctx.session=binding['sessionId'];ctx.run='a'*32;ctx.fixture_url='https://metadata.invalid/runs/'+'a'*32+'/'
        ctx.source=dict(recordedMetadataOnly=True);ctx.lock=ScriptSourceLock(root/'script-feature-sources.lock')
        # This is deliberately not IOSSnapshotCompanionOwner. The unit fixture
        # isolates metadata/path validation and cannot enter an End authority.
        ctx.admission=SimpleNamespace(previous={'recordedMetadata':'only'},bound=ctx.lock.assert_held)
        sdk_pin=ctx.pin(store.path)
        slot=dict(snapshotPhotosSDKSlotVersion=1,path=str(store.path),parentPath=str(root),parentIdentity=ctx.parent_pin(),binding=deepcopy(binding),
            runId=ctx.run,fixtureUrl=ctx.fixture_url,admissionOwnerSha256=digest(ctx.admission.previous),source=deepcopy(ctx.source),
            sdkStateSha256=digest(state),originalSDKStat=deepcopy(sdk_pin),artifactPath=str(artifact),artifactSha256=binding['artifactSha256'])
        ctx.snapshot=dict(snapshotPhotosEndSnapshotVersion=2,sdkState=state,sdkPin=sdk_pin,artifactPin=ctx.pin(artifact),sdkSlot=slot)
        return ctx
    def test_exact_recorded_slot_metadata_accepts_only_its_own_private_position(self):
        ctx=self.component()
        with ctx.lock.held():self.assertTrue(ctx.validate_snapshot());self.assertTrue(ctx.local())
    def test_different_missing_file_cannot_satisfy_recorded_sdk_pointer_absence(self):
        ctx=self.component();actual=ctx.session_store;ctx.session_store=PrivateFeatureState(actual.path.with_name('other-missing.json'))
        with ctx.lock.held(),self.assertRaises(NativeUIError):ctx.local(allow_absent=True)
        self.assertIsNotNone(actual.read())
    def test_parent_identity_mismatch_blocks_even_when_the_exact_sdk_file_is_absent(self):
        ctx=self.component();ctx.session_store.discard(ctx.snapshot['sdkState']);ctx.snapshot['sdkSlot']['parentIdentity'][1]+=1
        with ctx.lock.held(),self.assertRaises(NativeUIError):ctx.local(allow_absent=True)
    def test_identical_json_on_another_inode_cannot_replace_the_admitted_sdk_file(self):
        ctx=self.component();state=ctx.session_store.read();ctx.session_store.write(state,state)
        with ctx.lock.held(),self.assertRaises(NativeUIError):ctx.local()
    def test_pathless_snapshot_one_is_not_migrated_to_snapshot_two(self):
        ctx=self.component();ctx.snapshot={key:ctx.snapshot[key] for key in ('sdkState','sdkPin','artifactPin')}
        with self.assertRaises(NativeUIError):ctx.validate_snapshot()
    def test_changed_binding_run_source_admission_or_original_stat_is_rejected(self):
        ctx=self.component();baseline=deepcopy(ctx.snapshot)
        mutations=[lambda s:s['sdkSlot'].__setitem__('runId','b'*32),
            lambda s:s['sdkSlot']['binding'].__setitem__('processIdentity','85'),
            lambda s:s['sdkSlot'].__setitem__('source',{'differentMetadata':True}),
            lambda s:s['sdkSlot'].__setitem__('admissionOwnerSha256','e'*64),
            lambda s:s['sdkSlot']['originalSDKStat'].__setitem__(1,s['sdkSlot']['originalSDKStat'][1]+1),
            lambda s:s['sdkSlot'].__setitem__('artifactPath',str(ctx.artifact_path)+'.alias'),
            lambda s:s['sdkState'].__setitem__('generation',4)]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                ctx.snapshot=deepcopy(baseline);mutation(ctx.snapshot)
                with self.assertRaises(NativeUIError):ctx.validate_snapshot()
    def test_owner_one_or_boolean_version_cannot_enter_the_owner_two_decoder(self):
        ctx=self.component();value=dict(snapshotPhotosEndOwnerVersion=2,binding=ctx.binding,primaryBinding=ctx.binding,runId=ctx.run,
            fixtureUrl=ctx.fixture_url,source=ctx.source,bundleId=ctx.target['appId'],payload=pack([{'snapshot':ctx.snapshot}]))
        self.assertEqual(ctx.snapshot,end_record(value)['snapshot'])
        for version in (1,True,3):
            with self.subTest(version=version),self.assertRaises(NativeUIError):end_record(dict(value,snapshotPhotosEndOwnerVersion=version))
    def test_historical_slot_metadata_cannot_open_any_live_sdk_or_process_operation(self):
        ctx=self.component();ctx.historical=True
        for method in ('sdk','live','terminate','process_reader'):
            with self.subTest(method=method),self.assertRaises(NativeUIError):getattr(ctx,method)()


if __name__=='__main__':unittest.main()
