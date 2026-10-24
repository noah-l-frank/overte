"""Retired-only HTTP originals joined to actual Source5 carriers.

Native/Qt/clock producers are declared models; actual fixture HTTP and original
byte/inode ownership are production host code. No native effect is inferred.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_sources import WorldWebSources
from ios.self_tests.world_web_network_fixture import NetworkWorldWeb


class WorldWebRetiredSourceTests(unittest.TestCase):
    def test_actual_source5_final_capture_gets_new_retired_http_original_without_retiming_previous_inventory(self):
        # Native/Qt/clock producers are explicit models. Phase/browser HTTP,
        # production Source5 bytes, carrier identities and reconstruction are real.
        network=NetworkWorldWeb(use_whole_snapshot=True);self.addCleanup(network.close);source=network.whole.source;sdk=network.whole.sdk
        sdk.activate('cleanup',{});before=source.capture('before-closed-provider');original=deepcopy(source.frame(before));network.controller.close()
        final=source.capture('final-fence',retired=True);value=source.frame(final)
        self.assertEqual(2,value['originals']['browser']['browserFixtureVersion']);self.assertEqual(network.run,value['originals']['browser']['retirement']['runId'])
        self.assertEqual(original,source.frame(before));self.assertFalse(value['phaseBefore']['active']);self.assertFalse(value['phaseAfter']['active'])
        for name in ('instance','ready','sequence','responses'):
            self.assertEqual(original['originals']['browser'][name],value['originals']['browser'][name])
        rebuilt=WorldWebSources(source.store,source.lock,source.binding,source.run,source.role,lambda:True,phase=source.phase,historical=True)
        self.assertEqual(value,rebuilt.frame(final))

    def test_foreign_retired_run_is_durable_unknown_and_blocks_the_next_native_clock_query(self):
        network=NetworkWorldWeb(use_whole_snapshot=True);self.addCleanup(network.close);source=network.whole.source;sdk=network.whole.sdk
        sdk.activate('cleanup',{});source.capture('before-foreign-retired');network.controller.close()
        request=source.phase.client.request;observed=[]
        def corrupted(path,*args,**kwargs):
            value=request(path,*args,**kwargs)
            if path.endswith('/browser-retired'):
                value=deepcopy(value);value['retirement']['runId']='f'*32;observed.append(source.native.sequence)
            return value
        source.phase.client.request=corrupted
        with self.assertRaises(NativeUIError):source.capture('final-fence',retired=True)
        self.assertEqual([source.native.sequence],observed)
        self.assertIsNotNone(source.store.read())


if __name__=='__main__':unittest.main()
