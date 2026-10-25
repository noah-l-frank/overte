"""Small paired whole lifecycle through scoped scene and actual held terminal.

This selects baseline/cleanup rather than replacing any whole/source predicate.
All native/SDK/GPU seams are explicitly modeled by TerminalDomain.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from contextvars import Context
from functools import wraps
from unittest.mock import patch
import json
import sys
import unittest
from feature_journeys import terminal
from feature_journeys.contract import VERSION
from ios.adapters import avatar_operation_clock
from ios.adapters.avatar_api_entry import scope as api_scope
from ios.adapters.avatar_terminal import AvatarTerminal
from ios.self_tests import test_ios_avatar_active_composed as active
from ios.self_tests import test_ios_avatar_whole_cleanup as diagnostic
from ios.self_tests.avatar_terminal_domain import TerminalDomain
from ios.self_tests.avatar_prepare_fixture import RUN
from self_tests import test_account_provider as tls


@contextmanager
def during_original_quiet_sleep(primary,ready,actor):
    """Run the other real role only after the first original quiet cut."""
    old=primary.sleep;started=[]
    def schedule(seconds):
        if not started and ready():started.append(True);actor()
        old(seconds)
    primary.sleep=schedule
    try:yield started
    finally:primary.sleep=old


@contextmanager
def original_role_api_calls(owners):
    """Keep each real cleanup API's original budget and guarded decoder scope.

    Cooperative scheduling does not combine the two roles' contexts, renew a
    deadline or memoize any product/cleanup verdict.
    """
    contexts={owner.role:Context() for owner in owners};scopes=[]
    try:
        for owner in owners:
            context=contexts[owner.role];manager=context.run(api_scope,owner.monotonic)
            context.run(manager.__enter__);scopes.append((context,manager))
        yield lambda owner,name,*args,**kwargs:contexts[owner.role].run(getattr(owner,name),*args,**kwargs)
    except BaseException:
        failure=sys.exc_info()
        for context,manager in reversed(scopes):context.run(manager.__exit__,*failure)
        raise
    else:
        for context,manager in reversed(scopes):context.run(manager.__exit__,None,None,None)


def clock_report(test,label):
    if not hasattr(test,'cleanup_clock_starts'):return
    d=test.cleanup_domain;rows={}
    for role,(started,native_start,queries) in test.cleanup_clock_starts.items():
        packet=d.natives[role].feature.sample
        rows[role]=dict(hostElapsedMs=round((d.clock[0]-started)*1000),originalNativeElapsedMs=packet['capturedEpochMs']-native_start,
            originalNativeQueries=len(d.scenes[role].domain.history)-queries)
    print('Avatar cleanup original clocks '+label+': '+json.dumps(rows,sort_keys=True),flush=True)


def clock_diagnostics(function):
    @wraps(function)
    def run(test,*args,**kwargs):
        try:return function(test,*args,**kwargs)
        finally:clock_report(test,'return')
    return run


class AvatarHeldTerminalTests(unittest.TestCase):
    retain_originals=True
    domain_type=TerminalDomain
    prepare=active.AvatarActiveComposedTests.prepare
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()
    @diagnostic.original_error_chain
    @clock_diagnostics
    def test_baseline_cleanup_preserves_login_holds_until_paired_os_and_sdk_end(self):
        print('Avatar held terminal: prepare',flush=True);d=self.prepare();p,a=d.owners['primary'],d.owners['actor']
        call=dict(contractVersion=VERSION,runId=RUN)
        for owner in (p,a):owner.observe(dict(call,afterSequence=0))
        ticket='f'*32;d.client.activate(ticket,'cleanup',{})
        with original_role_api_calls((p,a)) as invoke:
            self.cleanup_domain=d;self.cleanup_clock_starts={}
            for owner in (p,a):
                owner.requested_cleanup_clock=avatar_operation_clock.begin(d.host(),d.clock[0])
                self.cleanup_clock_starts[owner.role]=(d.clock[0],d.natives[owner.role].feature.sample['capturedEpochMs'],len(d.scenes[owner.role].domain.history))
                self.assertTrue(invoke(owner,'restore_inputs',call,deepcopy(owner.requested_cleanup_clock)))
            clock_report(self,'inputs')
            for owner in (p,a):invoke(owner,'cleanup_checkpoint')
            invoke(p,'wait_actor_checkpoint')
            for owner in (p,a):invoke(owner,'wait_peer_checkpoint')
            clock_report(self,'checkpoints')
            print('Avatar held terminal: scoped scene',flush=True)
            scope=d.scenes['primary'].scope
            with during_original_quiet_sleep(scope,lambda:scope.state['phase']=='quiet' and bool(scope.state['quiet']),lambda:invoke(a,'cleanup_native_scene',call)) as started:
                invoke(p,'cleanup_native_scene',call)
            self.assertTrue(started);invoke(a,'cleanup_native_scene',call)
            for owner in (p,a):invoke(owner,'wait_peer_native_scene')
            clock_report(self,'native-scenes')
            def primary_scene_quiet():
                from adapters.normal_feature_state import PrivateFeatureState
                from adapters.script_feature.history import unpack
                value=PrivateFeatureState(p.store.path.with_name('ios-avatar-primary-scene.json')).read()
                return value is not None and bool(unpack(value['payload'])[0]['quiet'])
            with during_original_quiet_sleep(p,primary_scene_quiet,lambda:invoke(a,'cleanup_scene',call)) as started:invoke(p,'cleanup_scene',call)
            self.assertTrue(started);invoke(a,'cleanup_scene',call)
            for owner in (p,a):invoke(owner,'wait_peer_scene')
            invoke(a,'publish_scene');invoke(p,'wait_actor_scene')
            clock_report(self,'scene-publication')
            print('Avatar held terminal: logout/preferences',flush=True)
            invoke(p,'cleanup_account');invoke(a,'cleanup_account')
            for owner in (p,a):invoke(owner,'cleanup_postlogout');invoke(owner,'cleanup_account_surface')
            for owner in (p,a):invoke(owner,'cleanup_authority')
            clock_report(self,'accounts')
            ready={role:False for role in ('primary','actor')}
            for _ in range(40):
                for owner in (p,a):
                    if not ready[owner.role]:ready[owner.role]=invoke(owner,'cleanup_final_round')
                clock_report(self,'final-round')
                if all(ready.values()):break
                d.sleep(.2)
            self.assertTrue(all(ready.values()))
            for owner in (p,a):
                print('Avatar held terminal: '+owner.role+' final peer join',flush=True);invoke(owner,'wait_peer_final')
            for owner in (p,a):
                print('Avatar held terminal: '+owner.role+' cleanup API reentry',flush=True)
                self.assertEqual(dict(performed=True),invoke(owner,'cleanup',call));self.assertEqual(dict(performed=True),invoke(owner,'cleanup',call))
                with owner.held():owner.load();self.assertEqual('terminal-ready',owner.state['phase'])
                print('Avatar held terminal: '+owner.role+' terminal-ready',flush=True)
        print('Avatar held terminal: inspect actual holds',flush=True)
        request=dict(contractVersion=1,runId=RUN,stage='inspect');description=p.terminal(request)['description']
        self.assertTrue(all(description['roles'][role]['heldResources'] for role in ('primary','actor')))
        print('Avatar held terminal: genuine paired live window',flush=True);samples=[]
        for index in range(3):
            print('Avatar held terminal: live cut '+str(index+1)+' actor',flush=True);a.observe(dict(call,afterSequence=0))
            print('Avatar held terminal: live cut '+str(index+1)+' primary',flush=True);public=p.observe(dict(call,afterSequence=0))
            witness=p.client.request('/runs/'+RUN)['entries'][-1];samples.append(dict(primary=public,actor=witness))
            if index<2:d.sleep(1.6)
        print('Avatar held terminal: seal actual window',flush=True)
        terminal.window(samples,description);seal=p.terminal(dict(request,stage='seal',description=description,samples=samples))['seal']
        from ios.adapters.avatar_feature import AvatarFeaturePending
        captured=len(d.scenes['actor'].domain.history)
        with self.assertRaises(AvatarFeaturePending):a.observe(dict(call,afterSequence=0))
        self.assertEqual(captured,len(d.scenes['actor'].domain.history))
        self.assertFalse(any(method=='DELETE' for _role,method in d.sdk_requests))
        self.assertTrue(all('app.stop' not in native.lifecycle_inputs for native in d.natives.values()))
        self.assertFalse(any(row.get('stage')=='complete' for row in d.server.phase_retirements.snapshot(RUN)['entries']))
        print('Avatar held terminal: once Stop/OS/SDK',flush=True);d.client.request('/runs/'+RUN,method='DELETE')
        end=p.terminal(dict(request,stage='finish',seal=seal))['end'];terminal.ended(end,seal)
        print('Avatar held terminal: both original OS/SDK ends retained',flush=True)
        for role in ('primary','actor'):
            self.assertEqual(1,d.natives[role].lifecycle_inputs.count('app.stop'))
            self.assertEqual(1,d.sdk_requests.count((role,'DELETE')));self.assertFalse(d.sdk_exists[role])
        counts=list(d.sdk_requests)
        print('Avatar held terminal: historical end graph',flush=True)
        with p.held(paired=True):p.load();owner=AvatarTerminal(p);self.assertEqual(end,owner.verify_end())
        print('Avatar held terminal: SDK-free canonical end graph',flush=True)
        self.assertTrue(p.verify_terminal_result(dict(request,stage='finish',seal=seal),dict(stage='finish',end=end)))
        from ios.adapters.avatar_ended_archive import verify
        from adapters.normal_feature_state import PrivateFeatureState
        coordinator=PrivateFeatureState(p.store.path).read();terminal_original=PrivateFeatureState(owner.store.path).read();members=set()
        with patch.object(d.runtime.adapter,'_target',side_effect=AssertionError('Historical Avatar end must not resolve a target')):
            for subject in ('primary','actor'):
                print('Avatar held terminal: '+subject+' file-only binding replay',flush=True)
                self.assertEqual(p.state['bindings'][subject],verify(d.runtime.adapter,p.selectors[subject],coordinator,terminal_original,membership=members))
        self.assertIn(p.store.path,members);self.assertIn(owner.store.path,members)
        self.assertEqual(counts,d.sdk_requests);self.assertTrue(a.terminal_actor_ended())


class AvatarQuietScheduleTests(unittest.TestCase):
    def test_role_api_contexts_preserve_separate_original_scopes_and_restore_the_caller(self):
        from types import SimpleNamespace
        from ios.adapters.avatar_api_entry import original_cache,check
        now=[1.];owners=[SimpleNamespace(role=role,monotonic=lambda:now[0]) for role in ('primary','actor')]
        for owner in owners:owner.read=lambda:(check(),original_cache('postlogout-account'))[1]
        self.assertIsNone(original_cache('postlogout-account'))
        with original_role_api_calls(owners) as invoke:
            first=invoke(owners[0],'read');other=invoke(owners[1],'read')
            self.assertIsNot(first,other);self.assertIs(first,invoke(owners[0],'read'))
            self.assertIsNone(original_cache('postlogout-account'));now[0]=25.999
            self.assertIs(other,invoke(owners[1],'read'))
        self.assertIsNone(original_cache('postlogout-account'))

    def test_role_api_reentry_does_not_renew_the_original_deadline(self):
        from types import SimpleNamespace
        from adapters.normal_ui import NativeUIError
        from ios.adapters.avatar_api_entry import check,scope,original_cache
        now=[1.];owner=SimpleNamespace(role='primary',monotonic=lambda:now[0])
        def read():
            with scope(owner.monotonic):check()
        owner.read=read
        with self.assertRaises(NativeUIError):
            with original_role_api_calls((owner,)) as invoke:
                invoke(owner,'read');now[0]=26.;invoke(owner,'read')
        self.assertIsNone(original_cache('postlogout-account'))

    def test_both_original_clock_domains_keep_full_quiet_inside_the_original_role_deadlines(self):
        from types import SimpleNamespace
        from adapters.original_marker_scope import OriginalMarkerScope
        time=[1.];captures={role:[] for role in ('primary','actor')}
        clocks={role:avatar_operation_clock.begin(1700000000000+time[0]*1000,time[0]) for role in captures}
        def sleep(seconds):time[0]+=seconds
        def sample(role):
            start=time[0];time[0]+=.001
            return dict(clockJoin=dict(hostBeforeMonotonic=start,hostAfterMonotonic=time[0]),world=dict(processId=31,instance=role,
                clockBefore=dict(epochMs=1700086400000+start*1000,monotonicMs=start*1000),
                clockAfter=dict(epochMs=1700086400000+time[0]*1000,monotonicMs=time[0]*1000)))
        def run(role,owner):
            for _ in range(40):
                avatar_operation_clock.check(clocks[role],1700000000000+time[0]*1000,time[0]);captures[role].append(sample(role))
                if len(captures[role])>=3 and OriginalMarkerScope.quiet_interval(captures[role][0],captures[role][-1]):return
                owner.sleep(.1)
            self.fail('Original quiet window unavailable')
        primary,actor=SimpleNamespace(sleep=sleep),SimpleNamespace(sleep=sleep)
        with during_original_quiet_sleep(primary,lambda:bool(captures['primary']),lambda:run('actor',actor)) as started:run('primary',primary)
        self.assertTrue(started)
        for role in captures:
            self.assertGreaterEqual(len(captures[role]),3);self.assertTrue(OriginalMarkerScope.quiet_interval(captures[role][0],captures[role][-1]))
            self.assertEqual(1.,clocks[role]['hostStartedMonotonic']);self.assertEqual(26.,clocks[role]['deadlineMonotonic'])
        self.assertLess(time[0]-1.,3.5)
    def test_actor_never_starts_before_actual_admission_and_sleep_restores_after_failure(self):
        from types import SimpleNamespace
        calls=[];old=lambda seconds:calls.append(seconds);primary=SimpleNamespace(sleep=old);ready=[False]
        def actor():raise OSError('Actual other role failed')
        with self.assertRaises(OSError):
            with during_original_quiet_sleep(primary,lambda:ready[0],actor) as started:
                primary.sleep(.1);self.assertEqual([],started);ready[0]=True;primary.sleep(.1)
        self.assertIs(old,primary.sleep);self.assertEqual([.1],calls)


if __name__=='__main__':unittest.main()
