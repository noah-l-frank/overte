"""Analytical GPU/Qt/OS producers driving actual browser stereo/file owners.

All product producers are explicit host seams. Fresh packets are produced on
the same test clock at the original producer call; retained originals are never
retimed. No physical browser, renderer, HMD or device is qualified here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
from PIL import Image,ImageDraw
from adapters.navigation_arrival import NavigationArrival
from adapters.pico4.browser_stereo import PicoBrowserStereo,original_name
from feature_journeys.fixtures import marker_bytes
from feature_journeys.graphics_fixture import subject_ids
from self_tests.test_pico_browser_stereo import Model


class RenderModel(Model):
    def __init__(self,target,artifacts):
        super().__init__();self.target=target;self.artifacts=artifacts;self.binding=deepcopy(target.binding)
        self.lock=target.lock;self.run_id=target.run
        target.capture_stores=[self.owner_store(role) for role in ('primary','actor')]
        self.source['absentIds']=list(subject_ids(target.run).values())
        native=self.features.mutate
        def feature(value):
            native(value);epoch=target.clock.tick()
            value.update(requestedEpochMs=epoch,capturedEpochMs=epoch,lifecycle=deepcopy(target.lifecycle))
            value['animationFence']['requestedEpochMs']=epoch
        self.features.mutate=feature
        ui=self.ui.write
        def write(*args,**kwargs):
            self.ui.epoch=target.clock.tick();self.ui.clock=target.clock.now();return ui(*args,**kwargs)
        self.ui.write=write
        storage=self.storage.mutate
        def stored(value):
            storage(value);value['capturedEpochMs']=target.clock.tick()
        self.storage.mutate=stored
        inventory=self.inventory.send
        def receipts(request):
            self.inventory.epoch=target.clock.tick();return inventory(request)
        self.inventory.send=receipts
        gpu=self.gpu.mutate
        def rendered(value):
            gpu(value);epoch=target.clock.tick()
            value.update(requestedEpochMs=epoch,capturedEpochMs=epoch)
            source=value['source'];source.update(recordedEpochMs=epoch,startedEpochMs=epoch,capturedEpochMs=epoch)
            source['renderTrace'].update(recordedEpochMs=epoch,begunEpochMs=epoch,completedEpochMs=epoch)
            source['presentation']['submittedEpochMs']=epoch
        self.gpu.mutate=rendered
        send=self.gpu.send
        def pixels(command):
            with Image.open(io.BytesIO(self.gpu.raw)) as original:
                image=original.copy()
            with Image.open(io.BytesIO(marker_bytes(target.run,self.active))) as marker:
                card=marker.resize((320,80),Image.Resampling.NEAREST).convert('RGBA')
                image.paste(card,(288,248));image.paste(card,(992,248))
            # Analytical page raster derives only from consumed original bytes,
            # independently of scenario expectations or the measured state.
            body=target.current.get('body',target.assert_consumption)
            bits=hashlib.sha256(body).digest();draw=ImageDraw.Draw(image)
            for offset in (0,800):
                for y in range(345,500,15):
                    for x in range(300,500,20):
                        index=((x-300)//20+(y-345)//15*10)%len(bits)
                        draw.rectangle((x+offset,y,x+offset+19,y+14),fill=(bits[index],bits[(index+7)%32],bits[(index+15)%32],255))
            output=io.BytesIO();image.save(output,format='PNG');self.gpu.raw=output.getvalue()
            self.gpu.pixels=hashlib.sha256(image.tobytes()).hexdigest();self.storage.raw=self.gpu.raw
            return send(command)
        self.gpu.send=pixels

    def epoch(self):return self.target.clock.epoch() if hasattr(self,'target') else super().epoch()
    def _native_feature_observer(self,target,*,read_only):
        reader=super()._native_feature_observer(target,read_only=read_only)
        if hasattr(self,'target'):
            reader.clock_ms=self.target.clock.epoch;reader.monotonic=self.target.clock.now;reader.sleep=self.target.clock.sleep
        return reader
    def arrival(self):
        return NavigationArrival(self.probe,self.subject_reader(),self.target.clock.epoch,self.guard,self.run_id,self.binding,
            self.target.scene_url,monotonic=self.target.clock.now)
    def _world_render_capture(self,*args,**kwargs):
        owned=super()._world_render_capture(*args,**kwargs)
        for reader in (owned.capture,owned.storage,owned.receipts.cleanup):
            reader.clock_ms=self.target.clock.epoch;reader.monotonic=self.target.clock.now;reader.sleep=self.target.clock.sleep
        return owned
    def stereo(self,flow,journal,role):
        self.active=flow.source.read()['ticket']
        ui=self.ui.source();ui.clock_ms=self.target.clock.epoch;ui.monotonic=self.target.clock.now;ui.sleep=self.target.clock.sleep
        _normal,scripts,*_=self.target.normal_feature_runtime('target')
        return PicoBrowserStereo(self.arrival(),
            lambda:self._world_render_capture('owned',read_only=True,role=role,require_frame_view=True,source_lock=self.lock),
            self.artifacts/original_name(flow.run,role,journal),self.artifacts,flow.run,self.binding,self.lock,self.guard,
            fixture_url=flow.fixture_url,foreign_fixture_url=flow.foreign_url,owner_token=flow.live_owner['ownerToken'],
            script_url=flow.live_owner['scriptUrl'],browser_factory=lambda:self.target._tablet_web_io('target',flow,read_only=True),
            runtime_factory=lambda:self.target._web_runtime_observer('target',read_only=True),scripts=scripts,
            http=lambda:flow.source.client.request('/runs/'+flow.run+'/browser'),role=role,journal_id=journal,
            ui_factory=lambda:ui,native_factory=lambda:self._native_feature_observer('owned',read_only=True),
            monotonic=self.target.clock.now)
