"""Same recovered public owners continue into original paired Scene5 receipts.

Qt/OS/SDK/renderers remain StrongDomain models; real HTTPS/Pal/People/marker
JavaScript, original PNG/files and production Avatar owners execute. Scene5
preserves Login/cache/process holders; this case does not qualify Final/end.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from feature_journeys.contract import VERSION
from feature_journeys.retirement_receipts import AVATAR_HELD_STAGE,AVATAR_HELD_REMAINING
from ios.adapters import avatar_operation_clock
from ios.self_tests.avatar_strong_domain import StrongDomain,RUN
from ios.self_tests import test_ios_avatar_prepare_composed as preparation
from ios.self_tests.test_ios_avatar_recovered_active_checkpoint import AvatarRecoveredActiveCheckpointTests
from ios.self_tests.test_ios_avatar_held_terminal import original_role_api_calls,during_original_quiet_sleep


class AvatarRecoveredSceneCheckpointTests(unittest.TestCase):
    retain_originals=True
    domain_type=StrongDomain
    domain=preparation.AvatarPrepareComposedTests.domain
    issued_original_pin=preparation.AvatarPrepareComposedTests.issued_original_pin
    recovered_public_preparation=preparation.AvatarPrepareComposedTests.recovered_public_preparation
    preparation_unchanged=AvatarRecoveredActiveCheckpointTests.preparation_unchanged

    @classmethod
    def setUpClass(cls):preparation.AvatarPrepareComposedTests.setUpClass()
    @classmethod
    def tearDownClass(cls):preparation.AvatarPrepareComposedTests.tearDownClass()

    def recovered_scene(self,continuation=None):
        d,kept=self.recovered_public_preparation();p,a=d.owners['primary'],d.owners['actor']
        initial={}
        for role,owner in d.owners.items():
            with owner.held(paired=True):owner.load();initial[role]=deepcopy(owner.initial_original())
        call=dict(contractVersion=VERSION,runId=RUN)
        for owner in (p,a):owner.observe(dict(call,afterSequence=0))
        self.preparation_unchanged(d,kept,initial)
        ticket='9'*32;d.client.activate(ticket,'cleanup',{})
        with original_role_api_calls((p,a)) as invoke:
            for owner in (p,a):
                owner.requested_cleanup_clock=avatar_operation_clock.begin(d.host(),d.clock[0])
                self.assertTrue(invoke(owner,'restore_inputs',call,deepcopy(owner.requested_cleanup_clock)))
            for owner in (p,a):invoke(owner,'cleanup_checkpoint')
            invoke(p,'wait_actor_checkpoint')
            for owner in (p,a):invoke(owner,'wait_peer_checkpoint')
            scope=d.scenes['primary'].scope
            # The other actual role runs only after the first original cut;
            # original per-role API/cleanup clocks and quiet durations stay.
            with during_original_quiet_sleep(scope,lambda:scope.state['phase']=='quiet' and bool(scope.state['quiet']),
                    lambda:invoke(a,'cleanup_native_scene',call)) as scheduled:
                invoke(p,'cleanup_native_scene',call)
            self.assertTrue(scheduled);invoke(a,'cleanup_native_scene',call)
            # Native endpoints exist, but no bilateral endpoint barrier yet.
            # Scene image acquisition must fail BEFORE adding any image/cut.
            scene_path=p.store.path.with_name('ios-avatar-primary-scene.json');native_scene=self.issued_original_pin(scene_path)
            with self.assertRaises(NativeUIError):invoke(p,'cleanup_scene',call)
            self.assertEqual(native_scene,self.issued_original_pin(scene_path))
            for owner in (p,a):invoke(owner,'wait_peer_native_scene')
            def primary_scene_cut():
                value=PrivateFeatureState(scene_path).read()
                return value is not None and bool(unpack(value['payload'])[0]['quiet'])
            with during_original_quiet_sleep(p,primary_scene_cut,lambda:invoke(a,'cleanup_scene',call)) as scheduled:
                invoke(p,'cleanup_scene',call)
            self.assertTrue(scheduled);invoke(a,'cleanup_scene',call)
            for owner in (p,a):invoke(owner,'wait_peer_scene')
            before={role:list(native.input_log) for role,native in d.natives.items()}
            # A local scene/peer metadata handoff cannot authorize logout.
            with self.assertRaises(NativeUIError):invoke(p,'cleanup_account')
            self.assertEqual(before,{role:list(native.input_log) for role,native in d.natives.items()})
            invoke(a,'publish_scene');invoke(p,'wait_actor_scene')
            for role,owner in d.owners.items():
                with owner.held(paired=True):
                    owner.load();self.assertEqual('cleaning',owner.state['phase'])
                    event=next(row for row in owner.state['cleanup'] if row['kind']=='scene')
                    self.assertEqual(2,owner.scene_version(event));self.assertEqual(AVATAR_HELD_STAGE,owner.scene_stage(event))
                    original=owner.kept(event['scoped']);scoped=owner.scoped_scene(event);joined=scoped.joined(original)
                    self.assertEqual(ticket,joined['ticket']);self.assertTrue(joined['heldResources'])
                    self.assertEqual(list(AVATAR_HELD_REMAINING),joined['scene']['remaining'])
                    self.assertFalse(any(row['kind'] in ('postlogout','accounts-retired','final-ready','complete-publication') for row in owner.state['cleanup']))
                    self.assertTrue(d.natives[role].account['loggedIn']);self.assertEqual(0,d.natives[role].input_log.count('login.logout'))
            with p.held(paired=True):
                p.load();admitted=next(row for row in p.state['cleanup'] if row['kind']=='actor-scene')
                receipt=p.reader_history(p.kept(admitted['owner']),AVATAR_HELD_STAGE)
                self.assertEqual(ticket,receipt['records'][-1]['entry']['ticket'])
            self.preparation_unchanged(d,kept,initial)
            if continuation is not None:return continuation(d,kept,initial,call,invoke)
        return d,kept,initial,call

    def test_recovered_public_owners_join_both_native_endpoints_Scene5_and_actor_receipt_without_releasing_accounts(self):
        d,kept,initial,call=self.recovered_scene();p=d.owners['primary']
        # Preserve the exact original receipt inode OUTSIDE both owner trees;
        # changing membership cannot mask same-byte carrier substitution.
        with p.held(paired=True):
            p.load();event=next(row for row in p.state['cleanup'] if row['kind']=='actor-scene')
            wire=p.snapshot_ledger().entries()[event['owner']['index']-1]
            carrier=p.snapshot_ledger().originals.path(wire)
        raw=carrier.read_bytes();before=carrier.stat();inputs={role:list(n.input_log) for role,n in d.natives.items()}
        with tempfile.TemporaryDirectory(prefix='avatar-scene-receipt-old-inode-') as directory:
            original=Path(directory)/'actor-scene-receipt.original';carrier.rename(original);carrier.write_bytes(raw);carrier.chmod(0o600)
            self.assertEqual(before.st_ino,original.stat().st_ino);self.assertNotEqual(before.st_ino,carrier.stat().st_ino)
            with self.assertRaises(NativeUIError):p.cleanup_account()
            self.assertEqual(raw,original.read_bytes());self.assertEqual(raw,carrier.read_bytes())
        self.assertEqual(inputs,{role:list(n.input_log) for role,n in d.natives.items()})
        self.assertTrue(all(n.account['loggedIn'] for n in d.natives.values()))


if __name__=='__main__':unittest.main()
