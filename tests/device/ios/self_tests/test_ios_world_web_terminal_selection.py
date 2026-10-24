"""Local selection dataflow over actual carriers and Source5 observations.

The retirement measurement callback is an explicit test seam backed by actual
Observer originals. This verifies selection/bytes/aliases, never terminal or
native-resource retirement qualification. No Node or physical SDK is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_terminal_live import WorldWebTerminalLive
from ios.adapters.world_web_retirement import WorldWebRetirement
from ios.self_tests import test_ios_world_web_observer as fixture


class WorldWebTerminalSelectionTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.WorldWebObserverTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.sdk.use_snapshot=True;self.f.sdk.use_whole_snapshot=True

    def journal(self):
        f=self.f;source=f.sdk.owner(f.source_store,f.lock);observer=f.observer(source)
        observed=[observer.capture() for _ in range(3)]
        # Typed constructor scaffolding is not a qualified World retirement.
        retirement=object.__new__(WorldWebRetirement);retirement.role='primary';retirement.source=source
        retirement.lock=f.lock;retirement.binding=source.binding;retirement.run=source.run
        retirement.store=PrivateFeatureState(f.root/'ios-world-web-primary-retirement.json')
        journal=WorldWebTerminalLive(retirement)
        def measurement(original):
            actual=observer.validate_original(original)
            return dict(public=deepcopy(actual['public']),held=[],acquisition=deepcopy(actual['acquisition']),original=deepcopy(original))
        journal.measure=measurement;rows=[]
        for index,(original,_value) in enumerate(observed,1):
            actual=measurement(original);row=dict(index=index,measurement=actual);rows.append(actual)
            carrier=dict(iosWorldWebTerminalLiveRecordVersion=1,binding=source.binding,runId=source.run,payload=pack([row]))
            journal.record_store(index).write(carrier,None)
            journal.state['records'].append(dict(index=index,sha256=digest(carrier)))
        journal.save();return journal,rows

    def test_multiple_selections_revalidate_each_actual_carrier_once_and_return_copies(self):
        with self.f.held():
            journal,rows=self.journal();requests=[rows[0]['public'],rows[2]['public']]
            with patch.object(journal,'record',wraps=journal.record) as read:
                selected=journal.selected_many(requests);self.assertEqual(3,read.call_count)
            self.assertEqual([rows[0],rows[2]],selected)
            selected[0]['public']['state']['open']=True
            self.assertEqual(rows[0],journal.selected(rows[0]['public']))
            wrong=deepcopy(rows[0]['public']);wrong['sequence']=999
            with self.assertRaises(NativeUIError):journal.selected_many([wrong])

    def test_corrupted_unselected_actual_record_cannot_escape_the_single_pass(self):
        with self.f.held():
            journal,rows=self.journal();path=journal.record_store(2);old=path.read();changed=deepcopy(old)
            changed['payload']=pack([dict(index=2,measurement=deepcopy(rows[2]))]);path.write(changed,old)
            with self.assertRaises(NativeUIError):journal.selected_many([rows[0]['public']])

    def test_actual_record_replacement_after_final_read_cannot_escape_exit_guard(self):
        with self.f.held():
            journal,rows=self.journal();record=journal.record
            def changed(reference):
                value=record(reference)
                if reference['index']==3:
                    path=journal.record_store(2).path;other=path.with_suffix('.replacement')
                    other.write_bytes(path.read_bytes());other.chmod(0o600);other.replace(path)
                return value
            with patch.object(journal,'record',side_effect=changed),self.assertRaises(NativeUIError):journal.selected_many([rows[0]['public']])


if __name__=='__main__':unittest.main()
