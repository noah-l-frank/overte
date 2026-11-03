"""Real composed native/account transport with a predeclared forward clock.

The existing Avatar PrepareDomain really composes its native producer with the
marker animation/history producer. No returned DTO/validator/factory verdict
is patched. The independent role threads use their real existing SDK locks.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
import threading
import unittest
from ios.self_tests.avatar_prepare_fixture import PrepareDomain
from ios.self_tests import test_ios_avatar_prepare_composed as preparation


class ForwardProducerClock:
    def __init__(self):self.value=1.;self.lock=threading.Lock()
    def __getitem__(self,index):
        if index!=0:raise AssertionError('Only the original clock cell is modeled')
        with self.lock:self.value+=.002;return self.value
    def __setitem__(self,index,value):
        if index!=0 or type(value) not in (int,float):raise AssertionError('Invalid original clock assignment')
        # Constructors may restore an earlier local baseline. This selected
        # source clock cannot move backward, including across role threads.
        with self.lock:self.value=max(self.value,value)


class ForwardPrepareDomain(PrepareDomain):
    def create_clock(self):return ForwardProducerClock()


class AvatarComposedNativeAccountOrderTests(preparation.AvatarPrepareComposedTests):
    domain_type=ForwardPrepareDomain

    def acquire(self,d,role):
        native=d.natives[role];owner=d.owners[role]
        try:
            with owner.held():
                source=d.runtime._sources(role)
                result=source['clock_source'].read(0,require_account=True)
                account=result['account']['observation']
                self.assertLessEqual(result['requestedEpochMs'],account['capturedEpochMs'])
                self.assertLessEqual(account['capturedEpochMs'],result['animation']['capturedEpochMs'])
                self.assertLessEqual(result['animation']['capturedEpochMs'],result['capturedEpochMs'])
                self.assertLess(result['requestedEpochMs'],result['capturedEpochMs'])
                self.assertEqual(result['requestedEpochMs'],result['animationFence']['requestedEpochMs'])
                self.assertFalse(result['account']['loggedIn']);self.assertEqual([],native.input_log)
                self.assertEqual(result,json.loads(native.feature.original()))
                return result
        finally:
            # Preserve the actual emitted raw packet even on validator failure;
            # no SDK query, constructor, timestamp or expected value is added.
            raw=native.feature.original()
            if raw:
                path=native.root/'actual-composed-forward-native-account.json'
                descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(descriptor,'w') as output:
                    output.write(raw);output.flush();os.fsync(output.fileno())

    def test_actual_composed_native_source_preserves_request_before_account_and_final_animation_capture(self):
        d=self.domain();self.acquire(d,'primary')

    def test_independent_role_threads_keep_original_account_inside_each_actual_native_request(self):
        d=self.domain();barrier=threading.Barrier(2,timeout=3);results={};errors=[]
        def work(role):
            try:barrier.wait();results[role]=self.acquire(d,role)
            except BaseException as error:errors.append(error)
        threads=[threading.Thread(target=work,args=(role,),name='avatar-composed-native-source-'+role) for role in ('primary','actor')]
        def stop():
            for thread in threads:
                if thread.ident is not None:thread.join(timeout=3)
            self.assertFalse(any(thread.is_alive() for thread in threads))
        self.addCleanup(stop)
        for thread in threads:thread.start()
        stop()
        if errors:raise errors[0]
        self.assertEqual({'primary','actor'},set(results))
        self.assertNotEqual(results['primary']['requestId'],results['actor']['requestId'])
        self.assertNotEqual(d.natives['primary'].state['sessionId'],d.natives['actor'].state['sessionId'])


if __name__=='__main__':unittest.main()
