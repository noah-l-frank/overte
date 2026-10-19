"""Immediate settings recipe at an independent original-widget boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.token_graphics_ui import TokenGraphicsUI


class GraphicsBoundary:
    def __init__(self):
        self.clock,self.position,self.resolution=0.0,0.0,0.65
        self.haze,self.mirrors=False,False
        self.instance,self.generation='a'*32,'b'*32
        self.profile='phone-immediate-v1';self.fault=''
        self.actions,self.intents=[],[];self.transform=lambda value:value

    def sleep(self,seconds):self.clock+=seconds

    def intent(self,verb,value,identifier):
        self.intents.append((verb,identifier))
        if self.fault=='intent':raise NativeUIError('Original preference intent could not be saved')

    def capture(self):
        def row(identifier,location,**fields):
            viewport='above' if location<self.position else 'below' if location>self.position+0.35 else 'visible'
            source=repr((identifier,fields,viewport,self.position))
            return dict(id=identifier,token=hashlib.sha256(source.encode()).hexdigest()[:32],enabled=True,
                        inputReady=viewport=='visible',viewport=viewport,**fields)
        controls=[dict(id='graphics.page',token='c'*32,enabled=True,inputReady=False,viewport='visible',profile=self.profile),
            row('graphics.resolution',0.9,value=self.resolution,nativeValue=self.resolution,minimum=0.5,maximum=0.7,step=0.05),
            row('graphics.haze',0.2,checked=self.haze,nativeChecked=self.haze),
            row('graphics.mirrors',0.55,checked=self.mirrors,nativeChecked=self.mirrors),
            row('graphics.scrollbar',self.position+0.1,position=self.position,size=0.35)]
        if self.fault=='ui-only':
            current=next(r for r in controls if r['id']=='graphics.resolution')
            current['value']=getattr(self,'ui_resolution',self.resolution)
            current['inputReady']=current['viewport']=='visible' and current['value']==self.resolution
        return self.transform(dict(graphicsControlsVersion=1,ready=True,instance=self.instance,
                                   generation=self.generation,controls=controls))

    def original(self,identifier,token):
        if self.fault=='late-retirement':self.position=0.0
        rows=[r for r in self.capture()['controls'] if r['id']==identifier]
        if len(rows)!=1 or rows[0]['token']!=token or not rows[0]['inputReady']:
            raise NativeUIError('Original widget source token retired')
        assert len(self.intents)==len(self.actions)+1

    def scroll(self,identifier,direction,*,token):
        self.original(identifier,token);self.actions.append('scroll-'+direction)
        if self.fault!='scroll':self.position=max(0,min(0.65,self.position+(0.3 if direction=='down' else -0.3)))

    def set_value(self,identifier,value,*,token):
        assert identifier=='graphics.resolution'
        self.original(identifier,token);self.actions.append('resolution')
        if self.fault=='ui-only':self.ui_resolution=value
        elif self.fault!='resolution':self.resolution=value

    def activate(self,identifier,*,token):
        self.original(identifier,token);self.actions.append(identifier)
        if self.fault=='toggle':return
        if identifier=='graphics.haze':self.haze=not self.haze
        elif identifier=='graphics.mirrors':self.mirrors=not self.mirrors
        else:raise AssertionError(identifier)


class GraphicsUiTests(unittest.TestCase):
    def ui(self,fault=''):
        native=GraphicsBoundary();native.fault=fault
        return native,TokenGraphicsUI(native,native.intent,monotonic=lambda:native.clock,sleep=native.sleep)

    def test_normal_resolution_toggles_and_nondefault_restore_require_native_readback(self):
        native,ui=self.ui();original=native.resolution
        ui.set_resolution(0.5);ui.set_resolution(0.6);ui.set_resolution(original)
        ui.toggle('graphics.haze',True);ui.toggle('graphics.mirrors',True)
        ui.toggle('graphics.haze',False);ui.toggle('graphics.mirrors',False)
        self.assertEqual(original,native.resolution);self.assertFalse(native.haze);self.assertFalse(native.mirrors)
        self.assertEqual(3,native.actions.count('resolution'))
        self.assertIn('scroll-up',native.actions);self.assertIn('scroll-down',native.actions)

    def test_native_viewport_directions_choose_scroll_without_guessing_feature_order(self):
        native,ui=self.ui();native.position=0.6
        ui.toggle('graphics.haze',True)
        self.assertEqual(['scroll-up','scroll-up','graphics.haze'],native.actions)
        before=list(native.actions);ui.toggle('graphics.haze',True)
        self.assertEqual(before,native.actions)

    def test_ignored_resolution_scroll_and_toggle_fail_without_replay(self):
        for fault in ('resolution','scroll','toggle'):
            with self.subTest(fault=fault):
                native,ui=self.ui(fault)
                with self.assertRaises(NativeUIError):
                    if fault=='toggle':ui.toggle('graphics.haze',True)
                    else:ui.set_resolution(0.5)
                self.assertLessEqual(native.actions.count('resolution'),1)
                self.assertLessEqual(native.actions.count('graphics.haze'),1)
                if fault=='scroll':self.assertEqual(['scroll-down'],native.actions)
                self.assertLessEqual(native.clock,10.2)

    def test_ui_only_ack_cannot_substitute_native_settings(self):
        native,ui=self.ui('ui-only')
        with self.assertRaises(NativeUIError):ui.set_resolution(0.5)
        self.assertEqual(0.65,native.resolution);self.assertEqual(0.5,native.ui_resolution)
        self.assertEqual(1,native.actions.count('resolution'))

    def test_off_grid_nonfinite_and_boolean_values_are_refused_before_scroll_or_input(self):
        for value in (0.625,True,float('nan'),2.0):
            with self.subTest(value=value):
                native,ui=self.ui()
                with self.assertRaises(NativeUIError):ui.set_resolution(value)
                self.assertEqual([],native.actions)

    def test_persisted_intent_failure_prevents_actual_input(self):
        native,ui=self.ui('intent')
        with self.assertRaises(NativeUIError):ui.toggle('graphics.haze',True)
        self.assertEqual([],native.actions);self.assertFalse(native.haze)

    def test_missing_or_outside_control_never_causes_guessed_scrolling(self):
        for fault in ('missing','outside'):
            with self.subTest(fault=fault):
                native,ui=self.ui()
                def transform(value):
                    if fault=='missing':value['controls']=[r for r in value['controls'] if r['id']!='graphics.resolution']
                    else:next(r for r in value['controls'] if r['id']=='graphics.resolution').update(viewport='outside',inputReady=False)
                    return value
                native.transform=transform
                with self.assertRaises(NativeUIError):ui.set_resolution(0.5)
                self.assertEqual([],native.actions)

    def test_retired_native_token_and_foreign_identity_or_profile_prevent_input(self):
        native,ui=self.ui('late-retirement');native.position=0.6
        with self.assertRaises(NativeUIError):ui.set_resolution(0.5)
        self.assertEqual([],native.actions)
        for field,value in (('instance','f'*32),('generation','f'*32),('profile','generic-immediate-v1')):
            native,ui=self.ui();ui.capture();setattr(native,field,value)
            with self.assertRaises(NativeUIError):ui.toggle('graphics.haze',True)
            self.assertEqual([],native.actions)

    def test_missing_result_after_delivered_input_cannot_replay_slider(self):
        native,ui=self.ui();native.position=0.6;original=native.set_value
        def set_value(*args,**kwargs):original(*args,**kwargs);native.transform=lambda value:None
        native.set_value=set_value
        with self.assertRaises(NativeUIError):ui.set_resolution(0.5)
        self.assertEqual(['resolution'],native.actions);self.assertEqual(0.5,native.resolution)

    def test_malformed_metadata_duplicate_ids_missing_page_and_source_marker_fail(self):
        for fault in ('marker','duplicate','page','native','number','viewport'):
            with self.subTest(fault=fault):
                native,ui=self.ui()
                def corrupt(value):
                    if fault=='marker':value.pop('graphicsControlsVersion')
                    elif fault=='duplicate':value['controls'].append(deepcopy(value['controls'][0]))
                    elif fault=='page':value['controls']=[r for r in value['controls'] if r['id']!='graphics.page']
                    elif fault=='native':next(r for r in value['controls'] if r['id']=='graphics.haze')['nativeChecked']=True
                    elif fault=='number':next(r for r in value['controls'] if r['id']=='graphics.resolution')['step']=0
                    else:next(r for r in value['controls'] if r['id']=='graphics.resolution')['viewport']='guessed-below'
                    return value
                native.transform=corrupt
                with self.assertRaises(NativeUIError):ui.toggle('graphics.haze',True)
                self.assertEqual([],native.actions)

    def test_late_success_and_backward_clock_are_refused(self):
        native,ui=self.ui();original=native.capture
        def late():native.clock+=11;return original()
        native.capture=late
        with self.assertRaises(NativeUIError):ui.wait(lambda value:True)
        native,ui=self.ui();ui.now();native.clock=-1
        with self.assertRaises(NativeUIError):ui.wait(lambda value:True)


if __name__=='__main__':unittest.main()
