"""Declared lower frame/callback producer over existing actual Snapshot owners.

Native/OpenGL/SDK are MODELS. No real frame/backend execution is claimed. This
producer is installed before the ordinary modeled capture begins. Its frame
record is produced on the existing begin/finish path, never by the reader.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import uuid
from unittest.mock import patch
from PIL import Image
from adapters.native_feature_observation import need
from ios.adapters import feature_observation, snapshot_provenance as source
from ios.self_tests.test_ios_snapshot_capture_rendered_review import ReviewDomain


class ProvenanceCaptureDomain(ReviewDomain):
    def __init__(self, case):
        super().__init__(case)
        self.provenance_rows = {}
        self.provenance_sequence = 0
        self.frame_sequence = 0
        self.provenance_instance = uuid.uuid4().hex
        self.provenance_queries = []
        self.provenance_fault = None
        self.deliver_callback = True
        self.recorded = {}
        # Closed model camera exists before this model's first capture.
        self.model_camera = dict(position=[0, 0, 0], rotation=[0, 0, 0, 1],
            projection=[1,0,0,0, 0,1,0,0, 0,0,-1.002002,-.2002002, 0,0,-1,0],
            fieldOfViewDegrees=90, aspectRatio=1, nearClip=.1, farClip=100, perspective=True)
        native = self.capture.native
        original_begin, original_finish = native.begin, native.finish
        def begin(request='snap_1700000000000_1'):
            cap, identity = original_begin(request)
            self.frame_sequence += 1
            self.recorded[identity] = dict(snapshotFrameProvenanceVersion=1,
                frameInstance=uuid.uuid4().hex, frameIndex=self.frame_sequence,
                processId=int(self.ctx.binding['processIdentity']), pipeline='forward-primary-mono',
                recordedEpochMs=self.capture.epoch(), transformSlot=0, viewport=[0,0,128,128],
                worldFromCamera=[1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1],
                camera=deepcopy(self.model_camera), backend='opengl')
            return cap, identity
        def finish(cap, identity):
            if self.deliver_callback:
                # The existing original capture model wrote these actual bytes
                # before delivering finish. Read them, never an expected PNG.
                raw = self.f.f.h.path.read_bytes()
                with Image.open(BytesIO(raw)) as image:
                    extent = list(image.size)
                    pixels = image.convert('RGBA').tobytes()
                row = deepcopy(self.recorded[identity])
                need(extent == row['viewport'][2:])
                row.update(callbackEpochMs=self.capture.epoch(),
                    readback=dict(sourceExtent=extent, rectBottomLeft=[0,0,*extent], imageExtent=extent,
                        pixelFormat='rgba8-top-left', pixelSha256=hashlib.sha256(pixels).hexdigest(),
                        readEpochMs=self.capture.epoch()))
                actual = native.captures[identity][1]
                self.provenance_rows[identity] = dict(captureInstance=identity,
                    requestId=actual['requestId'], frame=row)
            return original_finish(cap, identity)
        native.begin, native.finish = begin, finish
        prior = feature_observation.post_request
        def post(request, timeout):
            query = json.loads(request.data)
            if query.get('action') != source.ACTION:
                return prior(request, timeout)
            need(timeout == 5)
            source.command(query)
            self.provenance_queries.append(deepcopy(query))
            self.provenance_sequence += 1
            value = dict(iosSnapshotProvenanceVersion=1, requestId=query['commandId'], runId=query['runId'],
                instance=self.provenance_instance, sequence=self.provenance_sequence,
                processId=int(self.ctx.binding['processIdentity']), clockDomain='native-main-snapshot-provenance',
                clockBefore=self.capture.clock(), clockAfter=self.capture.clock(),
                source=dict(complete=True, captures=[deepcopy(self.provenance_rows[key]) for key in sorted(self.provenance_rows)]))
            if self.provenance_fault is not None:
                self.provenance_fault(value)
            self.capture.raws[source.FILE] = json.dumps(value, indent=1) + '\n'
            self.ctx.files.echo = json.dumps(query).encode()
            return self.ctx.files
        actual = patch.object(feature_observation, 'post_request', post)
        actual.start()
        case.addCleanup(actual.stop)
