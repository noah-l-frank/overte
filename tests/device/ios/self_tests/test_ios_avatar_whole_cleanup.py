"""Paired scene/logout/final flow with original native producers and HTTPS.

Host scheduling advances both independent owners at their actual barriers;
all cleanup methods, original decoders and final public API remain unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import copy,deepcopy
import unittest
from functools import wraps
import traceback
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import VERSION
from ios.adapters import avatar_operation_clock
from ios.self_tests.avatar_final_domain import FinalDomain,RUN
from ios.self_tests import test_ios_avatar_active_composed as active_fixture
from self_tests import test_account_provider as tls


def original_error_chain(function):
    """Diagnostics only: preserve every exception and inspect no secret values."""
    @wraps(function)
    def run(self,*args,**kwargs):
        try:return function(self,*args,**kwargs)
        except Exception as error:
            seen=set();current=error
            while current is not None and id(current) not in seen:
                seen.add(id(current));frames=['%s:%s:%s'%(item.filename.rsplit('/',1)[-1],item.lineno,item.name) for item in traceback.extract_tb(current.__traceback__)]
                print('Avatar original error context:',type(current).__name__,frames,flush=True)
                current=current.__cause__ or current.__context__
            raise
    return run


class AvatarWholeCleanupTests(unittest.TestCase):
    domain_type=FinalDomain
    prepare=active_fixture.AvatarActiveComposedTests.prepare
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()
    @original_error_chain
    def test_both_original_scene_barriers_account_logout_keys_quiet_and_historical_complete(self):
        print('Avatar paired cleanup: preparation',flush=True)
        d=self.prepare();p,a=d.owners['primary'],d.owners['actor'];call=dict(contractVersion=VERSION,runId=RUN)
        for owner in (p,a):owner.observe(dict(call,afterSequence=0))
        ticket='f'*32;d.client.activate(ticket,'cleanup',{})
        for owner in (p,a):
            owner.requested_cleanup_clock=avatar_operation_clock.begin(d.host(),d.clock[0])
            self.assertTrue(owner.restore_inputs(call,deepcopy(owner.requested_cleanup_clock)))
        print('Avatar paired cleanup: bilateral checkpoint',flush=True)
        for owner in (p,a):owner.cleanup_checkpoint()
        p.wait_actor_checkpoint()
        for owner in (p,a):owner.wait_peer_checkpoint()
        print('Avatar paired cleanup: native scene',flush=True)
        for owner in (p,a):owner.cleanup_native_scene(call)
        for owner in (p,a):owner.wait_peer_native_scene()
        print('Avatar paired cleanup: scene pixels and quiet',flush=True)
        for owner in (p,a):owner.cleanup_scene(call)
        for owner in (p,a):owner.wait_peer_scene()
        a.publish_scene();p.wait_actor_scene()
        print('Avatar paired cleanup: ordered normal account logout',flush=True)
        p.cleanup_account();self.assertFalse(d.natives['primary'].account['loggedIn']);self.assertTrue(d.natives['actor'].account['loggedIn'])
        a.cleanup_account();self.assertFalse(d.natives['actor'].account['loggedIn'])
        print('Avatar paired cleanup: original postlogout properties',flush=True)
        for owner in (p,a):owner.cleanup_postlogout()
        # The real ordinary logout/preferences route has reopened this tablet.
        # Lose the Primary close reply only after the native widget consumed it.
        print('Avatar paired cleanup: actual lost UIKit tablet-close reply',flush=True)
        native=d.natives['primary'];self.assertTrue(native.shown)
        before=native.input_log.count('OverteTabletClose');original_call=native.call;lost=[]
        def missing_return(method,path,body=None):
            value=original_call(method,path,body)
            if method=='POST' and path.endswith('/click') and native.input_log[-1]=='OverteTabletClose' and not lost:
                lost.append(True);raise OSError('Actual UIKit close return lost')
            return value
        native.call=missing_return
        try:
            with self.assertRaises(NativeUIError):p.cleanup_account_surface()
        finally:native.call=original_call
        self.assertFalse(native.shown);self.assertEqual(before+1,native.input_log.count('OverteTabletClose'))
        rebuilt=copy(p);rebuilt.cleanup_account_surface()
        self.assertEqual(before+1,native.input_log.count('OverteTabletClose'))
        a.cleanup_account_surface();self.assertFalse(d.natives['actor'].shown)
        print('Avatar paired cleanup: controlled grants revoke',flush=True)
        for owner in (p,a):owner.cleanup_authority()
        print('Avatar paired cleanup: paired final original quiet',flush=True)
        # Both actual owners run independently. Interleave their original
        # passive rounds so the second role's first sample is not delayed until
        # the first role's entire measured quiet interval has already ended.
        ready={role:False for role in ('primary','actor')}
        for _ in range(40):
            for owner in (p,a):
                if not ready[owner.role]:ready[owner.role]=owner.cleanup_final_round()
            if all(ready.values()):break
            d.sleep(.2)
        self.assertTrue(all(ready.values()))
        for owner in (p,a):owner.wait_peer_final()
        print('Avatar paired cleanup: closed complete receipts',flush=True)
        a.publish_complete();p.wait_actor_complete()
        for owner in (p,a):
            self.assertEqual({'performed':True},owner.cleanup(call))
            with owner.held(paired=True):
                owner.load();self.assertEqual('cleaned',owner.state['phase']);proof=owner.completed_original()
                self.assertEqual([],proof['public']['resources']);self.assertEqual('none',proof['public']['state']['connection'])
        self.assertFalse(d.social.snapshot(RUN)['connected'])
        for role in ('primary','actor'):
            self.assertEqual(1,d.natives[role].input_log.count('login.submit'));self.assertEqual(1,d.natives[role].input_log.count('login.logout'))


if __name__=='__main__':unittest.main()
