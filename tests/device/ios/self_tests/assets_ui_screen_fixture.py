"""Pre-import original QML upload/browser with declared screen-source models.

Qt placement, UIKit geometry, WDA transport and raster remain modeled. Original
staged JS, normal QML events, clock/UI originals, PNG files and custody execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from io import BytesIO
import json
import math
from types import SimpleNamespace
from PIL import Image,ImageDraw
from adapters.graphics_subject_geometry import projected_box
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.assets_ui_source import AssetsUiSource
from ios.adapters.assets_ui_samples import AssetsUiSamples
from ios.adapters.assets_tree_owner import OwnedAssetsTree
from ios.adapters.assets_marker_owner import OwnedAssetsMarker
from ios.adapters.create_marker_files import OwnedCreateMarkerFiles
from ios.adapters.create_marker_scope import marker_name
from ios.adapters.create_originals import IOSCreateOriginals
from ios.adapters.native_geometry import OriginalGeometry
from ios.adapters import create_state
from ios.self_tests import assets_image_removal_fixture as prior
from ios.self_tests.test_ios_create_marker_scope import MarkerScopeTests
from ios.self_tests.assets_reply_fixture import RUN,TICKET,URL
from feature_journeys.fixtures import marker_bytes


class Boundary(prior.Boundary):
    def normal(self):
        value=super().normal()
        # Fresh declared layout before observation; original QML decides rows.
        for control in value['controls']:
            if control['id'].startswith('assets.tree.row.'):
                control['frame']=dict(x=400,y=180+int(control['id'].rsplit('.',1)[-1])*24,width=220,height=24)
            elif control['id']=='assets.baking':control['frame']=dict(x=400,y=120,width=220,height=40)
        return value


class ParsedFixture(prior.ParsedFixture):boundary_type=Boundary


class UiFixture:
    def __init__(self,test,directory):
        self.f=ParsedFixture(directory);test.addCleanup(self.f.close);self.b=self.f.boundary
        template=MarkerScopeTests();template.root=directory;template.lock=self.f.lock
        scope=template.owner(binding=self.f.files.binding)
        scope.run,scope.role,scope.namespace,scope._version=RUN,'primary','assets',3;scope.fixture_url,scope.ticket=URL,TICKET
        scope.store=PrivateFeatureState(directory/marker_name('primary','assets'));scope.previous=scope.store.read();scope.guard=lambda:self.b.live
        scope.files=OwnedCreateMarkerFiles(None,scope.marker_store('files'),scope.binding)
        scope.originals=IOSCreateOriginals(directory,scope.binding,RUN,'primary',scope.guard,scope.storage_intent,kind='inputs',namespace='assets-marker')
        self.scope=scope;self.domain=prior.Domain(scope,self.b);self.b.marker_domain=self.domain
        self.marker=OwnedAssetsMarker(scope,PrivateFeatureState(directory/('ios-assets-marker-'+RUN+'-primary.json')))
        self.marker.reserve();self.marker.prepare()
        self.f.start();upload=self.f.owner();upload.reserve();upload.review();upload.destination();upload.start_upload();upload.uploaded()
        self.upload=upload;tree=OwnedAssetsTree(upload,PrivateFeatureState(directory/'ui-tree.json'),lock=self.f.lock);tree.reserve();tree.browse()
        self.subject='assets.tree.row.0';self.gets=[];self.display_run,self.display_ticket=RUN,TICKET;self.blank=False
        self.geometry_sequence=0;geometry_raw=['']
        def geometry_send(query):
            self.geometry_sequence+=1;self.b.tick();geometry_raw[0]=json.dumps(dict(schemaVersion=1,commandId=query['commandId'],observation=dict(
                schemaVersion=1,sampleEpochMs=self.b.clock(),sampleSequence=self.geometry_sequence,
                nativeUi=dict(valid=True,surfaceWidth=640,surfaceHeight=400,safeInsetLeft=0,safeInsetTop=0,safeInsetRight=0,safeInsetBottom=0,
                    density=1,keyboardVisible=False,imeInsetBottom=0),window=dict(width=640,height=400))))
        def native_clock():return scope.native.read(scope.native.sequence)['capturedEpochMs']
        raw=['']
        def create_send(query):create_state.command(query);raw[0]=json.dumps(self.b.state(query['commandId']))
        create=create_state.IOSCreateState(create_send,lambda:raw[0],native_clock,lambda:self.b.live,42,monotonic=self.b.monotonic,sleep=self.b.sleep)
        geometry=OriginalGeometry(geometry_send,lambda:geometry_raw[0],native_clock,lambda:self.b.live,monotonic=self.b.monotonic,sleep=self.b.sleep)
        self.source=AssetsUiSource(upload,self.marker,scope.native,create,geometry,
            PrivateFeatureState(directory/('ios-assets-ui-sources-'+RUN+'-browse.json')),self.f.lock,lambda:self.b.live,
            subject=self.subject,checkpoint='browse',epoch_ms=lambda:self.b.clock()+5000,monotonic=self.b.monotonic)
        self.artifacts=directory/'screen';self.artifacts.mkdir(mode=0o700)
        self.native_clock=native_clock;self.policy=self.regions();self.client=SimpleNamespace(call=self.call)
    def view(self):
        actual=deepcopy(self.b.state()['source']['view']);n,f=.1,100.;t=1/math.tan(math.radians(actual['fieldOfViewDegrees'])/2)
        return {key:actual[key] for key in ('position','rotation','fieldOfViewDegrees','aspectRatio','perspective')}|dict(nearClip=n,farClip=f,
            projection=[t/actual['aspectRatio'],0,0,0,0,t,0,0,0,0,-(f+n)/(f-n),-2*f*n/(f-n),0,0,-1,0])
    def card_box(self):return projected_box(dict(self.domain.marker,dimensions=self.domain.marker['dimensions'][:2]+[.000001]),self.view(),[640,400])
    def regions(self):
        a,b,c,d=self.card_box();w,h=c-a,d-b
        return dict(source='native-screen',marker=[round(a+w*4/160),round(b+h*4/40),round(a+w*132/160),round(b+h*36/40)],subject=[410,184,610,200])
    def render(self):
        # This producer receives no requested owner ticket or expected verdict.
        image=Image.new('RGB',(640,400),(40,40,40));draw=ImageDraw.Draw(image)
        if self.b.host_state['pageAlive'] and not self.blank:
            for control in self.b.normal()['controls']:
                if control['id']!=self.subject:continue
                r=control['frame']
                for y in range(r['y'],r['y']+r['height'],4):
                    for x in range(r['x'],r['x']+r['width'],4):draw.rectangle((x,y,x+3,y+3),fill=(220,220,220) if (x//4+y//4)%2 else (20,60,100))
        if self.domain.running:
            a,b,c,d=[round(v) for v in self.card_box()]
            card=Image.open(BytesIO(marker_bytes(self.display_run,self.display_ticket)));image.paste(card.resize((c-a,d-b),Image.Resampling.NEAREST),(a,b))
        raw=BytesIO();image.save(raw,format='PNG');return raw.getvalue()
    def call(self,method,path,body=None):
        assert method=='GET' and path=='/session/'+self.f.files.binding['sessionId']+'/screenshot' and body is None
        self.gets.append(path);self.b.tick(5);self.last_png=self.render();return base64.b64encode(self.last_png).decode()
    def samples(self,native_clock=None):return AssetsUiSamples(self.source,self.artifacts,self.policy,self.client,native_clock or self.native_clock)
