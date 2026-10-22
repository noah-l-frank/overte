"""Actual current native disposition differs from teardown and weak death."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_state as state,uikit_input
from ios.self_tests.test_ios_tablet_web_source import packet as trace
from ios.self_tests.test_ios_tablet_web_sources import packet as sources,stamp,RUN,ROOT
from ios.self_tests.test_ios_uikit_input import packet as inputs


def query(index=1):return dict(schemaVersion=1,action=state.ACTION,commandId='ios-'+format(index,'032x'),runId=RUN,fixtureUrl=ROOT)


def packet(index=1,*,attached=False,dead=False):
    uikit=dict(inputs(phase='ended'),iosUIKitInputVersion=2)
    source=deepcopy(uikit['targets'][0]);owner=dict(id='8'*32,handle='1',source=deepcopy(source['identity']['source']),
        firstObserved=stamp(90400),expired=stamp(90620+index) if dead else None,alive=not dead,
        current=None if dead else dict({name:False for name in state.FLAGS},generation=0))
    value=dict(iosTabletWebStateVersion=1,commandId=query(index)['commandId'],runId=RUN,fixtureUrl=ROOT,instance='9'*32,sequence=index,processId=31,
        clockDomain='native-main-ios-tablet-web-state',clockBefore=stamp(90620+index),clockAfter=stamp(90620+index),complete=True,
        uikitInstance=uikit['instance'],otherLiveTablets=0,owners=[owner],targets=[dict(source=source,kind='wk',alive=True,
            windowAttached=attached,superviewPresent=True,subtreeResponder=False)])
    return value,uikit


def closed(value,uikit):return state.closed(value,sources(),trace(),uikit)


class TabletWebStateTests(unittest.TestCase):
    def test_detached_cache_held_native_view_is_closed_page_but_is_not_weak_retirement(self):
        value,uikit=packet();closed(value,uikit)
        self.assertTrue(value['targets'][0]['alive']);self.assertTrue(value['targets'][0]['superviewPresent'])
        self.assertIsNone(uikit['objects'][0]['expired'])
        with self.assertRaises(NativeUIError):uikit_input.retired(dict(inputs(),iosUIKitInputVersion=2),uikit)
        # The observable Qt owner can itself subsequently die independently;
        # the still-cache-held original UIView remains explicitly alive.
        later,_=packet(2,dead=True);state.validate(later,query(2),31,previous=value);closed(later,uikit)

    def test_teardown_entry_or_private_pointer_clear_does_not_hide_still_attached_real_UIView(self):
        value,uikit=packet(attached=True)
        for field in state.FLAGS:self.assertFalse(value['owners'][0]['current'][field])
        with self.assertRaises(NativeUIError):closed(value,uikit)
        value['targets'][0].update(windowAttached=False,subtreeResponder=True)
        with self.assertRaises(NativeUIError):closed(value,uikit)

    def test_native_active_or_pending_reopen_error_payload_and_unowned_tablet_never_become_closed(self):
        for fault in sorted(state.FLAGS)+['generation','foreign','incomplete']:
            value,uikit=packet()
            if fault=='foreign':value['otherLiveTablets']=1
            elif fault=='incomplete':value['complete']=False
            elif fault=='generation':value['owners'][0]['current']['generation']=1
            else:
                value['owners'][0]['current'][fault]=True
                if fault=='cleanupFailed':value['complete']=False
            state.original(value)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):closed(value,uikit)

    def test_sources_native_owner_and_every_original_UIKit_target_are_joined(self):
        value,uikit=packet()
        for fault in ('source','owner','uikit','target','new-target'):
            changed=deepcopy(value);other=deepcopy(uikit)
            if fault=='source':changed['owners'][0]['source']['navigation']='0'*32
            elif fault=='owner':changed['owners'][0]['handle']='99'
            elif fault=='uikit':changed['uikitInstance']='0'*32
            elif fault=='target':changed['targets'][0]['source']['view']='0'*32
            else:
                object_=deepcopy(other['objects'][0]);object_['id']='0'*32;other['objects'].append(object_)
                target=deepcopy(other['targets'][0]);target['view']='0'*32;other['targets'].append(target)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):closed(changed,other)

    def test_native_history_cannot_reset_retime_expiry_resurrect_or_drop_cached_targets(self):
        before,uikit=packet();current,_=packet(2,dead=True);state.validate(current,query(2),31,previous=before)
        for fault in ('birth','expiry','root','drop-owner','drop-target','bool','clock','counter','private'):
            value=deepcopy(current)
            if fault=='birth':value['instance']='0'*32
            elif fault=='expiry':value['owners'][0]['expired']=stamp(90600)
            elif fault=='root':value['owners'][0]['source']['root']='0'*32
            elif fault=='drop-owner':value['owners']=[]
            elif fault=='drop-target':value['targets']=[]
            elif fault=='bool':value['otherLiveTablets']=True
            elif fault=='clock':value['clockBefore']=stamp(90619)
            elif fault=='counter':value['sequence']=1
            else:value['targets'][0]['label']='private uncontrolled text'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):state.validate(value,query(2),31,previous=before)
        restored,_=packet(3)
        with self.assertRaises(NativeUIError):state.validate(restored,query(3),31,previous=current)

    def test_observed_native_cleanup_exception_cannot_be_forgotten_when_QObject_later_dies(self):
        before,_=packet();before['owners'][0]['current']['cleanupFailed']=True;before['complete']=False;state.original(before)
        current,_=packet(2,dead=True)
        with self.assertRaises(NativeUIError):state.validate(current,query(2),31,previous=before)


if __name__=='__main__':unittest.main()
