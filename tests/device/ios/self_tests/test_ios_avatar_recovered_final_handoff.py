"""Recovered public preparation reaches original Final2 held ownership.

All native/Qt/OS/SDK/GPU edges remain StrongDomain models. The same original
HTTPS/Node/pixel/owner graph continues; no capability or process end follows.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.test_ios_avatar_recovered_scene_checkpoint import AvatarRecoveredSceneCheckpointTests as SceneCase


class AvatarRecoveredFinalHandoffTests(unittest.TestCase):
    retain_originals=True
    domain_type=SceneCase.domain_type
    domain=SceneCase.domain
    issued_original_pin=SceneCase.issued_original_pin
    recovered_public_preparation=SceneCase.recovered_public_preparation
    preparation_unchanged=SceneCase.preparation_unchanged
    recovered_scene=SceneCase.recovered_scene

    @classmethod
    def setUpClass(cls):SceneCase.setUpClass()
    @classmethod
    def tearDownClass(cls):SceneCase.tearDownClass()

    def continue_final(self,d,kept,initial,call,invoke):
        p,a=d.owners['primary'],d.owners['actor']
        # Still inside BOTH original API contexts begun before restoration;
        # this continuation does not start another25s cleanup clock.
        authority=deepcopy(d.server.avatar_accounts.snapshot(p.run))
        with self.assertRaises(NativeUIError):invoke(p,'cleanup_authority')
        self.assertEqual(authority,d.server.avatar_accounts.snapshot(p.run))
        invoke(p,'cleanup_account');self.assertFalse(d.natives['primary'].account['loggedIn'])
        self.assertTrue(d.natives['actor'].account['loggedIn'])
        invoke(a,'cleanup_account');self.assertFalse(d.natives['actor'].account['loggedIn'])
        for owner in (p,a):invoke(owner,'cleanup_postlogout')
        native=d.natives['primary'];original=native.call;lost=[];before=native.input_log.count('OverteTabletClose')
        def once(method,path,body=None):
            value=original(method,path,body)
            if method=='POST' and path.endswith('/click') and native.input_log[-1:]==['OverteTabletClose'] and not lost:
                lost.append(True);raise OSError('Actual account-surface Close succeeded; local return lost')
            return value
        with patch.object(native,'call',once),self.assertRaises(NativeUIError):invoke(p,'cleanup_account_surface')
        self.assertEqual([True],lost);self.assertFalse(native.shown)
        self.assertEqual(before+1,native.input_log.count('OverteTabletClose'))
        invoke(p,'cleanup_account_surface');self.assertEqual(before+1,native.input_log.count('OverteTabletClose'))
        invoke(a,'cleanup_account_surface')
        for owner in (p,a):invoke(owner,'cleanup_authority')
        ready={role:False for role in d.owners}
        for _index in range(40):
            for owner in (p,a):
                if not ready[owner.role]:ready[owner.role]=invoke(owner,'cleanup_final_round')
            if all(ready.values()):break
            d.sleep(.2)
        self.assertTrue(all(ready.values()))
        for owner in (p,a):invoke(owner,'wait_peer_final')
        for role,owner in d.owners.items():
            self.assertEqual(dict(performed=True),invoke(owner,'cleanup',call))
            with owner.held(paired=True):
                owner.load();self.assertEqual('terminal-ready',owner.state['phase'])
                event=next(row for row in owner.state['cleanup'] if row['kind']=='final-ready')
                final=owner.final_owner(value=owner.kept(event['owner']));self.assertEqual(2,final.VERSION)
                proof=owner.terminal_live_proof(event);self.assertTrue(any(proof['heldResources'].values()))
                self.assertFalse(any(row['kind']=='complete-publication' for row in owner.state['cleanup']))
                preparation=owner.state['preparationClose'];self.assertEqual(kept[role]['event']['before'],preparation['before'])
                self.assertEqual(kept[role]['event']['issuedIntent'],preparation['issuedIntent'])
                for path,pin in kept[role]['pins'].values():self.assertEqual(pin,self.issued_original_pin(path))
                self.assertEqual(initial[role],owner.initial_original())
            self.assertEqual(1,d.natives[role].input_log.count('login.submit'))
            self.assertEqual(1,d.natives[role].input_log.count('login.logout'))
        self.assertTrue(all(d.worldless_web_queries[role] for role in d.owners))
        authority=d.server.avatar_accounts.snapshot(p.run)
        self.assertEqual('revoking',authority['phase'])
        self.assertTrue(all(not row['grantsEnabled'] for row in authority['accounts'].values()))
        self.assertFalse(any(native.lifecycle_inputs for native in d.natives.values()))
        return d

    def test_same_recovered_scene_owners_continue_normal_logout_lost_close_and_final2_without_process_end(self):
        self.recovered_scene(continuation=self.continue_final)


if __name__=='__main__':unittest.main()
