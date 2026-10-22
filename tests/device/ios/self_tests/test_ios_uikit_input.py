"""Original UIKit DTOs: distinct contact, callback return and cached weak life."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import uikit_input as source
from ios.self_tests.test_ios_tablet_web_source import packet as trace
from ios.self_tests.test_ios_tablet_web_sources import stamp,RUN,ROOT,packet as sources


def query(index=1):return dict(schemaVersion=1,action=source.ACTION,commandId='ios-'+format(index,'032x'),runId=RUN,fixtureUrl=ROOT)


def packet(index=1,*,phase='empty',kind='touch',owned=True,reuse=False,dead=False):
    # Independently authored native originals, not a transformation of a Qt
    # Pointer/Keys or World source. Only genuine Tablet identity fixture reused.
    value=dict(iosUIKitInputVersion=1,commandId=query(index)['commandId'],runId=RUN,fixtureUrl=ROOT,instance='a'*32,sequence=index,processId=31,
        clockDomain='native-main-ios-uikit-input',clockBefore=stamp(90300+index if phase=='empty' else 91020+index if dead else 90820+index if reuse else 90520+index if phase in ('active','pending') else 90620+index),clockAfter={},
        complete=True,installed=True,applicationClass='ActualRuntimeApplication',installation=stamp(90000),failure=None,
        dispatchSequence=0,pendingDispatches=[],objects=[],targets=[],contacts=[],dispatches=[])
    value['clockAfter']=deepcopy(value['clockBefore'])
    if phase=='empty':return value
    def object_(id_,kind_,born,expired=None):
        value['objects'].append(dict(id=id_,kind=kind_,born=stamp(born),expired=stamp(expired) if expired else None,alive=expired is None))
    object_('1'*32,'view',90402,91010 if dead and owned else None)
    object_('2'*32,'window',90402)
    object_('3'*32,kind,90500,91010 if dead else None)
    object_('4'*32,'event',90500,91010 if dead else None)
    identity=deepcopy(trace()['events'][0]['identity'])
    target=dict(view='1'*32,identity=identity,bound=stamp(90402))
    if owned:value['targets']=[target]
    association=dict(deepcopy(target),ancestry=['1'*32]) if owned else None
    def contact_(id_,begin,end):
        value['contacts'].append(dict(id=id_,kind=kind,object='3'*32,target='1'*32,window='2'*32,source=deepcopy(association),
            began=stamp(begin),ended=stamp(end) if end else None,phase=3 if end else 0,active=end is None))
    def dispatch(id_,contact,phase_,epoch,*,returned=True,finally_=True):
        value['dispatches'].append(dict(sequence=id_,event='4'*32,entered=stamp(epoch),returned=stamp(epoch+2) if returned else None,
            **{'finally':stamp(epoch+3) if finally_ else None},phases=[dict(object='3'*32,contact=contact,kind=kind,phase=phase_,target='1'*32,
            window='2'*32,source=deepcopy(association))]))
    contact_('5'*32,90501,90601 if phase not in ('active','pending') else None)
    dispatch(1,'5'*32,0,90501)
    if phase not in ('active','pending'):dispatch(2,'5'*32,3,90601,returned=phase!='exceptional')
    if phase=='pending':value['dispatches'][0]['returned']=None;value['dispatches'][0]['finally']=None;value['pendingDispatches']=[1]
    if reuse:
        contact_('6'*32,90701,90801);dispatch(3,'6'*32,0,90701);dispatch(4,'6'*32,3,90801)
    value['dispatchSequence']=len(value['dispatches']);return value


class UIKitInputTests(unittest.TestCase):
    def test_touch_and_press_delivery_quiescence_does_not_claim_cached_weak_death(self):
        for kind in ('touch','press'):
            before=packet();current=packet(2,phase='ended',kind=kind)
            source.quiescent(before,current,after_epoch=90001,require_delivery=True,kind=kind)
            source.join_sources(current,sources(),trace())
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):source.retired(before,current)
            dead=packet(3,phase='ended',kind=kind,dead=True)
            source.validate(dead,query(3),31,previous=current)
            self.assertEqual({'1'*32,'3'*32,'4'*32},set(source.retired(before,dead)))
            self.assertTrue(dead['objects'][1]['alive'])  # shared UIWindow is not owned

    def test_cached_object_reuse_has_same_birth_and_distinct_original_lifetimes(self):
        before=packet(1,phase='ended');current=packet(2,phase='ended',reuse=True)
        source.validate(current,query(2),31,previous=before)
        self.assertEqual(current['contacts'][0]['object'],current['contacts'][1]['object'])
        self.assertNotEqual(current['contacts'][0]['id'],current['contacts'][1]['id'])
        source.quiescent(before,current,after_epoch=90700,require_delivery=True)
        changed=deepcopy(current);changed['contacts'][1]['id']='5'*32
        with self.assertRaises(NativeUIError):source.original(changed)

    def test_exceptional_finally_or_nested_pending_is_not_actual_normal_return(self):
        before=packet()
        for phase in ('active','pending','exceptional'):
            current=packet(2,phase=phase);source.original(current)
            with self.subTest(phase=phase),self.assertRaises(NativeUIError):source.quiescent(before,current,after_epoch=90001)
        current=packet(2,phase='ended');current['dispatches'][0]['returned']=None;current['dispatches'][0]['finally']=None;current['pendingDispatches']=[1]
        source.original(current)
        with self.assertRaises(NativeUIError):source.quiescent(before,current,after_epoch=90001)

    def test_outsider_targets_remain_unowned_and_missing_hook_or_old_release_cannot_deliver(self):
        before=packet();current=packet(2,phase='ended',owned=False)
        source.original(current);source.quiescent(before,current,after_epoch=90001)
        with self.assertRaises(NativeUIError):source.retired(before,current)
        prior=packet(1,phase='ended');later=packet(2,phase='ended')
        with self.assertRaises(NativeUIError):source.quiescent(prior,later,after_epoch=90700,require_delivery=True)
        for fault in ('installed','complete'):
            changed=deepcopy(current);changed[fault]=False;changed['failure']='uninstalled'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.quiescent(before,changed,after_epoch=90001)

    def test_closed_private_grammar_rewrite_reset_retimed_expiry_and_foreign_source_fail(self):
        before=packet(1,phase='ended');current=packet(2,phase='ended',dead=True)
        for fault in ('key','location','source','birth','counter','rewrite','expiry','earlyExpiry','bool','resurrection','pending'):
            changed=deepcopy(current)
            if fault=='key':changed['dispatches'][0]['phases'][0]['key']='secret'
            elif fault=='location':changed['dispatches'][0]['phases'][0]['location']=[1,2]
            elif fault=='source':changed['targets'][0]['identity']['source']['root']='9'*32
            elif fault=='birth':changed['instance']='9'*32
            elif fault=='counter':changed['dispatchSequence']=0
            elif fault=='rewrite':changed['dispatches'][0]['entered']=stamp(90502)
            elif fault=='expiry':changed['objects'][2]['expired']=stamp(90499)
            elif fault=='earlyExpiry':changed['objects'][3]['expired']=stamp(90550)
            elif fault=='bool':changed['dispatches'][0]['sequence']=True
            elif fault=='resurrection':changed['objects'][2]['expired']=None
            else:changed['pendingDispatches']=[2]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                if fault=='source':source.join_sources(changed,sources(),trace())
                elif fault=='resurrection':source.validate(changed,query(2),31,previous=packet(1,phase='ended',dead=True))
                else:source.validate(changed,query(2),31,previous=before)

    def test_late_return_end_expiry_and_new_rows_cannot_hide_before_previous_capture(self):
        before=packet(1,phase='pending');after=packet(2,phase='ended')
        # The original pending acquisition is after the real first entered
        # dispatch; its previously absent normal return must occur later.
        before['clockBefore']=before['clockAfter']=stamp(90502)
        source.validate(after,query(2),31,previous=before)
        for fault in ('returned','finally','expired','newContact','newDispatch','newObject'):
            old=deepcopy(before);new=deepcopy(after)
            if fault=='returned':old['clockBefore']=old['clockAfter']=stamp(90504)
            elif fault=='finally':
                new['dispatches'][0]['returned']=None;old['clockBefore']=old['clockAfter']=stamp(90505)
            elif fault=='expired':
                old=packet(1,phase='ended');new=packet(2,phase='ended',dead=True)
                old['clockBefore']=old['clockAfter']=stamp(91011)
                new['clockBefore']=new['clockAfter']=stamp(91022)
            elif fault=='newContact':
                old=packet(1,phase='ended');new=packet(2,phase='ended',reuse=True)
                old['clockBefore']=old['clockAfter']=stamp(90702)
            elif fault=='newDispatch':old['clockBefore']=old['clockAfter']=stamp(90602)
            else:
                old=packet();new=packet(2,phase='ended');old['clockBefore']=old['clockAfter']=stamp(90403)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(new,query(2),31,previous=old)

    def test_own_transport_sends_once_preserves_original_and_never_installs_or_replays(self):
        calls=[];raw={}
        def send(q):
            calls.append(deepcopy(q));value=packet(len(calls),phase='ended');value['commandId']=q['commandId'];raw['value']=json.dumps(value)
        reader=source.IOSUIKitInput(send,lambda:raw['value'],lambda:90621,lambda:True,31,monotonic=lambda:0)
        value=reader.read(RUN,ROOT);self.assertEqual(source.ACTION,calls[0]['action']);self.assertEqual('ActualRuntimeApplication',value['applicationClass'])
        def lost(q):calls.append(deepcopy(q));raise OSError('Actual UIKit source query return lost')
        reader.send=lost
        with self.assertRaises(NativeUIError):reader.read(RUN,ROOT)
        self.assertEqual(2,len(calls))


if __name__=='__main__':unittest.main()
