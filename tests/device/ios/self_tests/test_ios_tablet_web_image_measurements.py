"""Original fixture pixels projected through modeled actual UIKit geometry.

No native execution: these cases exercise the pixel/geometry boundary only.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import unittest
from PIL import Image
from adapters.normal_ui import NativeUIError
from feature_journeys.evidence import image_observation,MarkerNotReady
from feature_journeys.fixtures import marker_bytes
from ios.adapters.tablet_web_image_measurements import projected
from ios.adapters.tablet_web_screen_archive import raw_original,with_capture
from ios.self_tests.tablet_web_dom_fixture import shown

RUN='a'*32;TICKET='b'*32


def fixture():
    actual=shown();actual['screenScale']=1.;actual.update(screenCoordinates=[0.,0.,500.,800.],screenFrame=[0.,44.,500.,756.])
    document=dict(source=dict(presentationAfter=actual,dom=dict(document=dict(visualViewport=dict(
        offsetLeft=0.,offsetTop=0.,width=500.,height=756.)),elements=[dict(id='feature-marker',tag='IMG',visible=True,rect=[10.,10.,170.,50.])])) )
    policy=dict(source='native-screen',marker=[14,58,142,90],subject=[10,104,170,154])
    image=Image.new('RGB',(500,800),'gray');marker=Image.open(BytesIO(marker_bytes(RUN,TICKET))).convert('RGB');image.paste(marker,(10,54))
    for x in range(10,170):
        for y in range(104,154):image.putpixel((x,y),((x*7)%256,(y*13)%256,(x+y)%256))
    stream=BytesIO();image.save(stream,format='PNG');return document,policy,stream.getvalue()


class TabletWebImageMeasurementsTests(unittest.TestCase):
    def test_actual_fixture_marker_and_nonuniform_subject_fit_the_current_WK_projection(self):
        document,policy,raw=fixture();actual=projected(policy,document,[500,800])
        self.assertEqual(policy['marker'],actual['marker'])
        measured,subject=image_observation(raw,RUN,TICKET,policy)
        self.assertTrue(subject);self.assertTrue(measured)
        with self.assertRaises(MarkerNotReady):image_observation(raw,RUN,'c'*32,policy)

    def test_sheet_wrong_marker_window_scale_and_subject_outside_WK_are_rejected(self):
        document,policy,_raw=fixture()
        for fault in ('sheet','marker','subject','scale','viewport'):
            value,requested=deepcopy(document),deepcopy(policy);extent=[500,800]
            if fault=='sheet':value['source']['presentationAfter']['top']='f'*32
            elif fault=='marker':requested['marker'][0]+=5
            elif fault=='subject':requested['subject']=[10,0,170,30]
            elif fault=='scale':extent=[500,400]
            else:value['source']['dom']['document']['visualViewport']['offsetTop']=30.
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):projected(requested,value,extent)

    def test_raw_PNG_receipt_has_no_invented_capture_clock_and_exactly_matches_later_capture(self):
        _document,_policy,raw=fixture();header=dict(nativeScreenRawVersion=1,requestId='ios-'+TICKET,source='native-screen',
            transport='webdriveragent-original-png',sessionId='existing-session',processId=31,bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),extent=[500,800])
        raw_original(header,raw);capture={key:value for key,value in header.items() if key!='nativeScreenRawVersion'}
        capture.update(screenCaptureVersion=1,nativeBeforeMs=20000,nativeAfterMs=20050,hostBeginEpochMs=10000,
            hostEndEpochMs=10050,hostBeginMonotonic=1.,hostEndMonotonic=1.05)
        with_capture(header,capture)
        for fault in ('hash','request','hostClock','nativeClock','process'):
            value=deepcopy(capture)
            if fault=='hash':value['sha256']='0'*64
            elif fault=='request':value['requestId']='ios-'+'d'*32
            elif fault=='hostClock':value['hostEndEpochMs']+=1000
            elif fault=='nativeClock':value['nativeAfterMs']+=1000
            else:value['processId']+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):with_capture(header,value)


if __name__=='__main__':unittest.main()
