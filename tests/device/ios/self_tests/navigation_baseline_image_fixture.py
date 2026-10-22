"""One untouched physical Worlds model, actual source readers and PNG owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
from copy import deepcopy
import uuid
from PIL import Image,ImageDraw

from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.navigation_baseline_image import NavigationBaselineImage
from ios.self_tests.navigation_feature_observer_fixture import Whole
from self_tests.test_native_completed_frame import view


class Baseline:
    def __init__(self,test):
        self.h=Whole(test);h=self.h
        # The same modeled native event loop drives every fresh producer.
        gpu=h.sdk.gpu
        h.inventory.__class__=type('InitialImportClock',(type(h.inventory),),{
            'clock':property(lambda _:gpu.clock,lambda _,value:setattr(gpu,'clock',max(gpu.clock,value)))})
        self.sources=dict(h.sources,inventory=h.inventory.reader(),navigation=h.navigation)
        self.black=False
        def raster():
            recorded=view();recorded['position']=deepcopy(h.sdk.navigation.source['view']['position'])
            image=Image.new('RGBA',(640,400),(120,120,120,255));draw=ImageDraw.Draw(image)
            def screen(point):
                camera=[a-b for a,b in zip(point,recorded['position'])]+[1]
                clip=[sum(recorded['projection'][r*4+c]*camera[c] for c in range(4)) for r in range(4)]
                return [(clip[0]/clip[3]+1)*320,(1-clip[1]/clip[3])*200]
            if not self.black:
                draw.polygon([tuple(screen(p)) for p in [[-4,0,.75],[-4,4,.75],[4,4,.75],[4,0,.75]]],fill=(180,80,180,255))
            stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue(),image.tobytes(),recorded
        h.gpu.raster=raster
        self.request='ios-'+uuid.uuid4().hex

    def owner(self,*,role='primary',historical=False,request=None):
        h=self.h;request=request or self.request
        return NavigationBaselineImage(PrivateFeatureState(h.root/('ios-navigation-baseline-'+role+'-'+request[4:]+'.json')),
            h.root,h.binding,h.run,role,request,h.lock,lambda:h.sdk.okay,historical=historical,
            native=None if historical else h.native,sources=None if historical else self.sources,
            fixture=None if historical else h.fixture,frame_factory=None if historical else h.gpu.factory,
            epoch_ms=h.now,monotonic=h.mono,sleep=h.sdk.gpu.sleep)
