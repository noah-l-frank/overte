"""Actual Pico passive-profile factory; APK/native device IO are explicit seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest
from unittest.mock import patch

import test_normal_scripts as pico_seams
from self_tests.test_chat_profile_current import CurrentBoundary
from adapters.normal_ui import NativeUIError

RUN='a'*32


class PicoCurrentProfileTests(unittest.TestCase):
    def setUp(self):
        self.pico=pico_seams.PicoNormalScriptsTests();self.pico.setUp();self.addCleanup(self.pico.doCleanups)
        self.instance,self.native=self.pico.instance,self.pico.native;self.source=CurrentBoundary()
        write=self.native.write_debug_app_file;read=self.native.read_debug_app_file
        def original_write(target,package,path,raw):
            request=json.loads(raw)
            if request['action']=='feature-chat-profile-current':
                self.source.epoch=self.native.epoch_milliseconds(target);self.source.send(request)
            else:return write(target,package,path,raw)
        def original_read(target,package,path,**kwargs):
            if path.endswith('/feature-chat-profile-current.json'):return self.source.original()
            return read(target,package,path,**kwargs)
        for boundary in (patch.object(self.native,'write_debug_app_file',side_effect=original_write),
                patch.object(self.native,'read_debug_app_file',side_effect=original_read)):
            boundary.start();self.addCleanup(boundary.stop)
    def test_original_pico_factory_reads_current_without_acquiring_or_restoring_profile(self):
        reader=self.instance._chat_profile_current(self.native.target);self.assertEqual([],self.source.commands)
        packet=reader.read(RUN);self.assertEqual(self.source.value,packet);self.assertEqual('a'*32,packet['instance'])
        self.assertEqual(['feature-chat-profile-current'],[row['action'] for row in self.source.commands])
        self.assertIsNone(self.instance._chat_profile_store(self.native.target).read())
        self.assertIsNone(self.instance._chat_capture_store(self.native.target).read());self.assertEqual([],self.native.inputs)
        self.assertNotIn('original',packet);self.assertNotIn('restored',packet);self.assertNotIn('owned',packet)
    def test_changed_actual_candidate_blocks_the_passive_query_before_native_dispatch(self):
        reader=self.instance._chat_profile_current(self.native.target);self.native.digest='f'*64
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual([],self.source.commands);self.assertIsNone(reader.last)
        self.assertIsNone(self.instance._chat_profile_store(self.native.target).read());self.assertEqual([],self.native.inputs)


if __name__=='__main__':unittest.main()
