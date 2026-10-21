"""Original login lifetime counterexamples, with no Qt or native execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.authentication_journey.login_source import inventory,accept_inventory
from adapters.normal_ui import NativeUIError


def loads(rows=(),retired=()):
    return dict(qmlLoadInventoryVersion=1,instance='e'*32,complete=True,components=list(rows),retiredComponents=sorted(retired))


def component(key='d'*32,phase='loading'):
    return dict(id=key,sourceSha256='f'*64,phase=phase,loading=phase=='loading',callbackPending=phase=='loading',parentPresent=True)


def original(roots=(),retired=()):
    return dict(inventoryVersion=1,complete=True,qmlLoads=loads(),keyboard3D=dict(raised=False,enabled=False),roots=[dict(id=key,profile='qml-login-v1',visible=visible,inCurrentTree=current,
        callbackRunning=False,callbackItemPresent=False)
        for key,visible,current in roots],retiredRoots=sorted(retired))


class LoginInventoryTests(unittest.TestCase):
    def test_hidden_and_detached_original_objects_are_retained_until_actual_destruction(self):
        opened=original([('a'*32,True,True)])
        hidden=original([('a'*32,False,False)])
        self.assertEqual(hidden,accept_inventory(opened,hidden))
        self.assertEqual([],accept_inventory(hidden,original(retired=['a'*32]))['roots'])

    def test_an_empty_array_or_reused_retired_identity_cannot_claim_resource_release(self):
        opened=original([('a'*32,True,True)])
        for current in (original(),original([('a'*32,True,True)],['a'*32])):
            with self.subTest(current=current),self.assertRaises(NativeUIError):accept_inventory(opened,current)
        with self.assertRaises(NativeUIError):accept_inventory(original(retired=['a'*32]),original([('a'*32,True,True)]))

    def test_retirement_history_profile_and_incomplete_walk_cannot_be_rewritten(self):
        value=original([('a'*32,True,True)],['b'*32])
        for change in ('history','profile','complete','duplicates','boolean'):
            bad=deepcopy(value)
            if change=='history':bad['retiredRoots']=[]
            if change=='profile':bad['roots'][0]['profile']='phone-login-v1'
            if change=='complete':bad['complete']=False
            if change=='duplicates':bad['roots']*=2
            if change=='boolean':bad['roots'][0]['inCurrentTree']=1
            with self.subTest(change=change),self.assertRaises(NativeUIError):accept_inventory(value,bad)

    def test_native_pending_component_cannot_disappear_or_be_replaced_by_a_new_source(self):
        before=original();before['qmlLoads']=loads([component()])
        for change in ('empty','source','incomplete','forgotten-retirement','phase','url'):
            after=deepcopy(before)
            if change=='empty':after['qmlLoads']=loads()
            elif change=='source':after['qmlLoads']['instance']='a'*32
            elif change=='incomplete':after['qmlLoads']['complete']=False
            elif change=='forgotten-retirement':
                before['qmlLoads']['retiredComponents']=['b'*32];after['qmlLoads']['retiredComponents']=[]
            elif change=='phase':after['qmlLoads']['components']=[component(phase='constructing')]
            elif change=='url':after['qmlLoads']['components'][0]['sourceSha256']='a'*64
            with self.subTest(change=change),self.assertRaises(NativeUIError):accept_inventory(before,after)
        after=original();after['qmlLoads']=loads(retired=['b'*32,'d'*32])
        self.assertEqual(after,accept_inventory(before,after))

    def test_finished_component_is_still_an_original_resource_until_actual_qobject_destruction(self):
        before=original();before['qmlLoads']=loads([component()])
        finished=deepcopy(before);finished['qmlLoads']['components']=[component(phase='finished')]
        self.assertEqual(finished,accept_inventory(before,finished))
        with self.assertRaises(NativeUIError):accept_inventory(finished,original())
        for invalid in ({'raised':0,'enabled':False},{'raised':False}):
            bad=original();bad['keyboard3D']=invalid
            with self.subTest(invalid=invalid),self.assertRaises(NativeUIError):inventory(bad)

    def test_distinct_new_lifetime_is_allowed_after_original_retirement(self):
        first=original([('a'*32,True,True)])
        second=original([('c'*32,True,True)],['a'*32])
        self.assertEqual(second,accept_inventory(first,second));inventory(second)


if __name__=='__main__':unittest.main()
