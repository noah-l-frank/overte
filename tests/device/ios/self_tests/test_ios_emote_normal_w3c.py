"""Normal W3C entry uses the actual modeled original widget reference."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.emote_active_observer_fixture import ActiveObserverFixture
from ios.self_tests.emote_normal_w3c_fixture import normal_tablet


class NormalW3CTests(unittest.TestCase):
    def test_actual_lookup_state_click_and_original_root_retirement_surround_real_emote_script(self):
        target=ActiveObserverFixture(self);client,_normal=normal_tablet(target)
        target.actions.act(target.activate('open'));old=client.item
        target.actions.act(target.activate('play',name='Waving'));self.assertEqual('overrideAnimation',target.vm.state['events'][-1]['method'])
        target.actions.act(target.activate('cancel'));target.actions.act(target.activate('close'))
        self.assertFalse(target.native.tablet);self.assertIsNot(old,client.item)
        self.assertEqual(2,sum(method=='POST' and path.endswith('/click') for method,path,_ in client.calls))
        self.assertTrue(any(method=='GET' and path.endswith('/displayed') for method,path,_ in client.calls))
        self.assertTrue(any(method=='GET' and path.endswith('/enabled') for method,path,_ in client.calls))
        self.assertTrue(all(packet['processId']==31 for packet in client.observations))
        self.assertEqual('restoreAnimation',target.vm.state['events'][-1]['method'])

    def test_retired_original_widget_cannot_be_refound_or_replayed_after_issued_tablet_input(self):
        target=ActiveObserverFixture(self);client,_normal=normal_tablet(target);client.retire_before_click=True
        call=target.activate('open')
        with self.assertRaises(NativeUIError):target.actions.act(call)
        clicks=sum(path.endswith('/click') for _,path,_ in client.calls)
        with self.assertRaises(NativeUIError):target.actions.act(call)
        self.assertEqual(clicks,sum(path.endswith('/click') for _,path,_ in client.calls))
        self.assertEqual([],target.vm.state['events']);self.assertEqual('issuing',target.actions.state['current']['phase'])


if __name__=='__main__':unittest.main()
