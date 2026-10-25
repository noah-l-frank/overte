"""Keep pre-stop and later settled originals; never reuse an unquiet anchor."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from ios.adapters.tablet_web_tail import TabletWebTail
from ios.adapters.tablet_web_cleanup_observation import candidates
from ios.self_tests.tablet_web_whole_fixture import TabletWholeBoundary


class TabletQuietSelectionTests(unittest.TestCase):
    def test_early_active_UI_frame_is_retained_but_later_original_quiet_suffix_is_selected(self):
        boundary=TabletWholeBoundary(self);runtime=boundary.runtime;tail=TabletWebTail(runtime)
        before,stop=tail.capture([]),tail.capture([])
        def shown(query,value):
            if query['action']=='normal-ui-input':value['observation']['tabletShown']=True;value['observation']['scriptInventory']['tabletShown']=True
        boundary.force=shown;early=tail.capture([]);original=deepcopy(tail.read(early));boundary.force=None
        refs=[early]
        for _ in range(3):boundary.sleep(1.6);refs.append(tail.capture([]))
        actual=candidates(runtime,before,stop,refs);self.assertTrue(actual)
        self.assertEqual(refs[1:],actual[-1]['quiet']);self.assertEqual(original,tail.read(early))
        self.assertEqual(6,len(tail.state['records']));self.assertEqual('returned',original['row']['status'])
        boundary.force=shown;latest=tail.capture([]);refs.append(latest)
        self.assertEqual([],candidates(runtime,before,stop,refs));self.assertEqual(7,len(tail.state['records']))


if __name__=='__main__':unittest.main()
