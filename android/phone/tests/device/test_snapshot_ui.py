"""Normal-input composition with explicit synthetic Qt/SDK producer boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import unittest

from test_snapshot_controls import Boundary
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_ui import PhoneSnapshotControls

PATH='/data/user/0/io.github.noah_be.overte.phone/files/Snapshots/owned.png'


class Product(Boundary):
    def __init__(self):
        super().__init__();self.shown=False;self.page='home';self.mode=0;self.format=0;self.text='';self.focus=False
        self.ignored=set();self.sdk=[];self.sdk_intents=[];self.image=PATH;self.refresh()

    def row(self,id,**fields):
        return dict(id=id,token=hashlib.sha256(id.encode()).hexdigest()[:32],enabled=True,focused=False,inputReady=True)|fields

    def refresh(self):
        if not self.shown:self.controls=[]
        elif self.page=='home':self.controls=[self.row('snapshot.entry')]
        else:
            self.controls=[self.row('snapshot.page',inputReady=False,profile='native-snapshot-review-v1',
                component='file:///original/scripts/system/snapshot/NativeSnapshotReview.qml',capturing=False,processing=False,
                captureSettingsLoaded=True,statusError=False,statusText='',exportTicket='',uploadPath=''),
                self.row('snapshot.name',text=self.text,focused=self.focus),self.row('snapshot.capture'),
                self.row('snapshot.mode',currentIndex=self.mode,count=4,currentText=('still','animated','panorama','cubemap')[self.mode],
                    options=['still','animated','panorama','cubemap']),
                self.row('snapshot.format',currentIndex=self.format,count=2,currentText=('png','webp')[self.format],options=['png','webp'])]
            for action in ('save','share','upload'):
                self.controls.append(self.row('snapshot.'+action+'.'+hashlib.sha256(self.image.encode()).hexdigest(),path=self.image))

    def send(self,value):
        self.refresh();super().send(value);request=value['request']
        if request['action']=='observe' or request['controlId'] in self.ignored:return
        id=request['controlId']
        if id=='snapshot.entry':self.page='snapshot'
        elif id=='snapshot.name':
            if request['action']=='activate':self.focus=True
            else:self.text=request['text']
        elif id=='snapshot.mode' and request['action']=='select-index':self.mode=request['index']
        elif id=='snapshot.format' and request['action']=='select-index':self.format=request['index']
        # Save/Share/Upload ACKs deliberately create no native/file/HTTP effect.

    def tablet_visible(self):return self.shown
    def open_tablet(self):
        assert self.sdk_intents[-1]['action']=='tablet.open';self.sdk.append('tablet.open')
        if 'tablet.open' not in self.ignored:self.shown=True
    def close_tablet(self):
        assert self.sdk_intents[-1]['action']=='tablet.close';self.sdk.append('tablet.close')
        if 'tablet.close' not in self.ignored:self.shown=False
    def release(self):assert self.sdk_intents[-1]['action']=='input.release';self.sdk.append('input.release')
    def ui(self):return PhoneSnapshotControls(self.io(),self,lambda row:self.sdk_intents.append(row),
        monotonic=lambda:self.clock,sleep=self.sleep)


class SnapshotUiTests(unittest.TestCase):
    def test_normal_entry_name_choices_exact_original_image_inputs_and_close_have_no_feature_verdict(self):
        product=Product();ui=product.ui();ui.open();ui.name('Owned photo');ui.configure('animated','webp')
        self.assertEqual('Owned photo',product.text);self.assertEqual((1,1),(product.mode,product.format))
        for action in ('save','share','upload'):
            actual=ui.image_action(action,PATH)
            self.assertNotIn('files',actual);self.assertNotIn('saved',actual);self.assertNotIn('uploads',actual)
        ui.close();ui.release();self.assertEqual(['tablet.open','tablet.close','input.release'],product.sdk)
        self.assertFalse(product.shown)

    def test_ignored_entry_choice_text_or_close_is_detected_by_new_actual_widget_reads(self):
        for fault in ('snapshot.entry','snapshot.mode','snapshot.name','tablet.close'):
            with self.subTest(fault=fault):
                product=Product();ui=product.ui()
                if fault=='snapshot.entry':product.ignored.add(fault)
                else:ui.open();product.ignored.add(fault)
                with self.assertRaises(NativeUIError):
                    if fault=='snapshot.entry':ui.open()
                    elif fault=='snapshot.mode':ui.configure('animated','png')
                    elif fault=='snapshot.name':ui.name('Actual new text')
                    else:ui.close()
                if fault=='snapshot.entry':
                    delivered=[row for row in product.calls if row['request'].get('controlId')=='snapshot.entry']
                    self.assertEqual(1,len(delivered))

    def test_capture_cancel_plan_is_original_and_durable_without_delivering_capture(self):
        product=Product();ui=product.ui();ui.open();ui.configure('animated','png')
        before=product.commands;request=ui.plan_cancel()
        self.assertEqual(before,product.commands);self.assertEqual('snapshot.capture',request['controlId'])
        self.assertEqual(request,product.intents[-1]['request'])
        self.assertEqual([], [row for row in product.calls if row['request'].get('controlId')=='snapshot.capture'])

    def test_idle_still_choice_cannot_be_borrowed_for_the_animated_pending_cancel_recipe(self):
        product=Product();ui=product.ui();ui.open()
        with self.assertRaises(NativeUIError):ui.plan_cancel()
        self.assertEqual([], [row for row in product.calls if row['request'].get('controlId')=='snapshot.capture'])

    def test_foreign_image_path_or_missing_original_button_cannot_target_another_capture(self):
        product=Product();ui=product.ui();ui.open();before=product.commands
        for path in (PATH.replace('owned','foreign'),'/tmp/foreign.png',PATH+'/foreign.png'):
            with self.subTest(path=path),self.assertRaises(NativeUIError):ui.image_action('save',path)
        self.assertEqual(before,product.commands)

    def test_sdk_intent_failure_and_ignored_open_cannot_create_a_ready_page(self):
        product=Product();ui=product.ui();ui.intent=lambda *_:False
        with self.assertRaises(NativeUIError):ui.open()
        self.assertEqual([],product.sdk)
        product=Product();ui=product.ui();product.ignored.add('tablet.open')
        with self.assertRaises(NativeUIError):ui.open()
        self.assertEqual(['tablet.open'],product.sdk);self.assertFalse(product.shown)


if __name__=='__main__':unittest.main()
