"""Actual Pico source factory with explicit audio engine/property boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_normal_scripts as original
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.pico4.audio_settings_source import FILE,ACTION
from adapters.android.adapter import ANDROID_CONTROL_COMMAND
from self_tests.test_audio_preview_lifetime import AudioPreviewLifetimeTests
from self_tests.test_pico_audio_pages import AudioPageTests
from self_tests.test_pico_audio_settings_source import AudioSettingsTests,AudioSettingsProbeTests,Boundary,RUN
ROOT=Path(__file__).resolve().parents[5]


class PicoAudioSettingsTests(unittest.TestCase):
    def test_actual_factory_reuses_exact_parent_lock_process_candidate_and_private_source_channel(self):
        fixture=original.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        adapter,native=fixture.instance,fixture.native;boundary=Boundary()
        write_original=native.write_debug_app_file;read_original=native.read_debug_app_file
        def write(target,package,path,raw):
            request=json.loads(raw)
            if request.get('action')!=ACTION:return write_original(target,package,path,raw)
            self.assertEqual('org.overte.pico',package);self.assertEqual(ANDROID_CONTROL_COMMAND,path)
            boundary.epoch=native.epoch_milliseconds(target);boundary.send(request)
            boundary.value['processId']=int(native.identity.split(':')[0])
        def read(target,package,path,**options):
            if path!='files/overte-e2e/'+FILE:return read_original(target,package,path,**options)
            self.assertEqual({'attempts':1},options);return boundary.read()
        with patch.object(native,'write_debug_app_file',side_effect=write),patch.object(native,'read_debug_app_file',side_effect=read):
            lock=adapter._script_journey()._lock(native.target);reader=adapter._audio_settings_source(native.target,source_lock=lock)
            self.assertIs(lock,reader.source_lock)
            with lock.held():packet=reader.capture(RUN)
            self.assertEqual(False,packet['source']['inputPeakValuesEnabled']);self.assertEqual([],native.inputs)
            native.digest='f'*64
            with self.assertRaises((RuntimeError,ValueError)):reader.capture(RUN)
            self.assertEqual(1,len(boundary.commands))
            self.assertFalse(any(cap.startswith('feature.audio.') for cap in adapter.capabilities(native.target)))

    def test_actual_page_factory_reuses_original_native_snapshot_and_same_parent_lock(self):
        from self_tests.test_pico_audio_pages import Boundary as PageBoundary
        fixture=original.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        adapter,native=fixture.instance,fixture.native;boundary=PageBoundary();read_original=native.read_debug_app_file
        def read(target,package,path,**options):
            raw=read_original(target,package,path,**options)
            if path!='files/overte-e2e/navigation-ui-observation.json':return raw
            self.assertEqual({'attempts':1},options);boundary.epoch=native.epoch_milliseconds(target)
            pages=json.loads(boundary.read())['picoAudioPages'];packet=json.loads(raw)
            packet.update(picoAudioPageVersion=1,picoAudioPages=pages);return json.dumps(packet)
        with patch.object(native,'read_debug_app_file',side_effect=read):
            lock=adapter._script_journey()._lock(native.target);reader=adapter._audio_pages_source(native.target,source_lock=lock)
            self.assertIs(lock,reader.source_lock)
            with lock.held():packet=reader.capture()
            self.assertEqual([],packet['picoAudioPages']['originals']);self.assertEqual([],native.inputs)
            native.digest='f'*64
            with self.assertRaises((RuntimeError,ValueError)):reader.capture()

    def test_actual_qt_native_observer_and_whole_pico_nonpico_getter_bodies(self):
        subprocess.run([sys.executable,str(ROOT/'tests/device/contracts/audio/test_audio_settings_observation.py')],check=True,timeout=180)

    def test_actual_original_audio_client_cleanup_functor_and_timer(self):
        subprocess.run([sys.executable,str(ROOT/'tests/device/contracts/audio/test_recorded_preview_lifetime.py')],check=True,timeout=90)

    def test_actual_original_audio_qml_page_and_peak_restore(self):
        subprocess.run([sys.executable,str(ROOT/'tests/device/contracts/audio/test_audio_page_observation.py')],check=True,timeout=180)


if __name__=='__main__':unittest.main()
