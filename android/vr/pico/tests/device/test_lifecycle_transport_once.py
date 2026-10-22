"""Actual bound Pico OS writer; SDK/process/Qt sources are explicit seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
import test_normal_scripts as sources
from adapters.pico4.graphics_binding import PicoGraphicsBinding


class LifecycleOnceTests(unittest.TestCase):
    def setUp(self):
        self.h=sources.PicoNormalScriptsTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.adapter,self.sdk=self.h.instance,self.h.native;self.target=self.sdk.target
        self.binding=self.adapter._scripts(self.target).binding
        self.foreground=True;self.inputs=[];self.lost=False;self.effect=False;self.events=[]
        original=self.sdk.shell
        def shell(target,*arguments,**kwargs):
            if arguments==('input','keyevent','KEYCODE_HOME') or arguments[:4]==('am','start','-W','-n'):
                self.events.append('write');self.inputs.append(arguments)
                if self.effect:self.foreground=arguments[0]=='am'
                if self.lost:raise RuntimeError('explicit lost original OS response')
                return ''
            return original(target,*arguments,**kwargs)
        for boundary in (patch.object(self.sdk,'shell',side_effect=shell),
                         patch.object(self.sdk,'foreground_package',side_effect=lambda _target:'org.overte.pico' if self.foreground else 'com.example.synthetic')):
            boundary.start();self.addCleanup(boundary.stop)

    def test_actual_candidate_guards_then_callback_then_one_home_even_when_effect_is_absent(self):
        install=self.adapter._installation
        def installed(target):value=install(target);self.events.append('installation');return value
        def callback():self.assertEqual('installation',self.events[-1]);self.events.append('admission')
        with patch.object(self.adapter,'_installation',side_effect=installed):
            result=self.adapter._pico_lifecycle_input_once(self.target,'lifecycle.background',self.binding,before_input=callback)
        self.assertEqual({'requested':True},result);self.assertTrue(self.foreground)
        self.assertEqual([('input','keyevent','KEYCODE_HOME')],self.inputs)
        self.assertEqual(['admission','write'],[event for event in self.events if event in ('admission','write')])
        self.assertEqual([],self.sdk.inputs);self.assertEqual([],self.sdk.controllers)

    def test_original_resume_activity_is_once_and_lost_response_never_bootstraps_or_retries(self):
        self.foreground=False;self.lost=True;seen=[]
        with self.assertRaises(ValueError):
            self.adapter._pico_lifecycle_input_once(self.target,'app.launch',self.binding,before_input=lambda:seen.append('admitted'))
        self.assertEqual(['admitted'],seen)
        self.assertEqual([('am','start','-W','-n',self.adapter.profile.get('e2e_activity','org.overte.pico/.E2eLauncherActivity'))],self.inputs)
        self.assertFalse(self.foreground);self.assertEqual([],self.sdk.controllers)
        self.assertFalse(any(row[:2]==('am','force-stop') for row in self.sdk.events))

    def test_final_callback_refusal_and_changed_candidate_prevent_actual_os_writer(self):
        seen=[]
        def refused():seen.append('refused');raise RuntimeError('original source is stale')
        with self.assertRaises(ValueError):
            self.adapter._pico_lifecycle_input_once(self.target,'lifecycle.background',self.binding,before_input=refused)
        self.assertEqual(['refused'],seen);self.assertEqual([],self.inputs)
        self.sdk.digest='f'*64
        with self.assertRaises(ValueError):
            self.adapter._pico_lifecycle_input_once(self.target,'lifecycle.background',self.binding,before_input=refused)
        self.assertEqual(['refused'],seen);self.assertEqual([],self.inputs)

    def test_actual_audio_factory_passes_its_final_phase_callback_to_original_once_writer(self):
        def factory(path,run,binding,lock,status,os_input,runtime,phase_source,**kwargs):
            self.assertEqual(self.binding,binding)
            os_input('lifecycle.background',binding,before_input=lambda:self.events.append('audio-phase'))
            return 'actual-audio-factory'
        with patch('adapters.pico4.audio_background_owner.PicoAudioBackground',side_effect=factory):
            result=self.adapter._audio_background_owner(self.target,'a'*32,5,None)
        self.assertEqual('actual-audio-factory',result)
        self.assertEqual([('input','keyevent','KEYCODE_HOME')],self.inputs)
        self.assertEqual(['audio-phase','write'],[value for value in self.events if value in ('audio-phase','write')])
        self.assertEqual([],self.sdk.inputs);self.assertEqual([],self.sdk.controllers)

    def test_actual_graphics_facade_selects_once_route_and_final_fence_without_qml_dispatch(self):
        facade=PicoGraphicsBinding(self.adapter)
        class Fence:
            def check(_self):self.events.append('admission')
        facade.phase_fence=Fence();self.effect=True
        facade._graphics_lifecycle_input(self.target,'lifecycle.background',self.binding)
        facade._graphics_lifecycle_input(self.target,'app.launch',self.binding)
        self.assertEqual(2,self.events.count('admission'));self.assertEqual(2,len(self.inputs))
        self.assertTrue(self.foreground);self.assertEqual([],self.sdk.inputs)


if __name__=='__main__':unittest.main()
