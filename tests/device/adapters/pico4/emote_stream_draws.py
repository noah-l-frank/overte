"""Explicit Source4 sample-ID brackets for the existing executed stereo trace.

Only the source envelope differs from the original remote draw join. The
native draw validator and its actual submitted left/right camera rows remain
unchanged. Callers must bind every sample to its actual retained role original.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_avatar_render import nonce
from adapters.native_feature_observation import need
from adapters.pico4.emote_model_draws import validate as draw_packet,ACTION
from adapters.pico4.emote_stream_frame import frame as sample_packet,continuity,independent
from adapters.pico4 import remote_joint_pose
from adapters.script_journey.history import same


def remote_draws(primary,before,after,capture,draws,pid,epoch):
    """Join actual sample4/remote geometry to the original used-eye draw rows."""
    for value in (primary,before,after):
        source=value['source']
        sample_packet(value,run=source['runId'],subject=source['subjectSessionId'],pid=value['processId'],
            epoch=value['capturedEpochMs'],stream=value['streamId'],policy_sha=value['ownerPolicySha256'])
    independent(primary,before);independent(primary,after);continuity(before,after)
    need(before['processId']==after['processId']==pid)
    draw_packet(draws,dict(schemaVersion=1,commandId=draws.get('requestId'),action=ACTION,
        captureRequestId=capture.get('requestId')),pid,epoch,capture=capture)
    trace=capture['source']['renderTrace'];left,right=before['source'],after['source']
    need(nonce(left['worldRenderInstance']) and left['worldRenderInstance']==right['worldRenderInstance']==capture['instance']==draws['instance']
        and before['capturedEpochMs']<=trace['recordedEpochMs']
        and capture['source']['capturedEpochMs']<=after['requestedEpochMs'])
    def near(a,b,tolerance):return len(a)==len(b) and all(abs(x-y)<=tolerance for x,y in zip(a,b))
    def rotation(a,b):return near(a,b,.001) or near(a,[-value for value in b],.001)
    a,b=left['subject'],right['subject']
    need(same(a['geometry'],b['geometry']) and left['cameraMode']==right['cameraMode']
        and near(a['pose']['feetPosition'],b['pose']['feetPosition'],.005)
        and rotation(a['pose']['orientation'],b['pose']['orientation'])
        and abs(a['pose']['modelScale']-b['pose']['modelScale'])<=1e-4)
    for source in (left,right):
        subject=source['subject'];view=source['view'];recorded=trace['recordedView']
        need(all(subject[key] is True for key in ('loaded','visible','addedToScene','avatarShouldRender'))
            and subject['geometry'] is not None and subject['geometry']['sourcePresent']
            and near(view['position'],recorded['position'],.005) and rotation(view['rotation'],recorded['rotation'])
            and near(view['projection'],recorded['projection'],1e-4))
        remote_joint_pose.validate(subject['remoteJointPose'],subject,epoch,version=2)
        for key in ('fieldOfViewDegrees','aspectRatio','nearClip','farClip'):
            need(abs(view[key]-recorded[key])<=1e-4*max(1,abs(recorded[key])))
    rows=[row for row in draws['source']['modelTrace']['models'] if row['modelInstance']==a['modelInstance']]
    need(len(rows)==1);row=rows[0];geometry=a['geometry']
    need(row['geometryInstance']==geometry['instance'] and row['loadedSourcePresent']
        and row['loadedSourceSha256']==geometry['sourceSha256'] and row['skinnedDrawCommands']>0
        and row['originalGeometryDrawCommands']==row['drawCommands']
        and all(x<y for x,y in zip(row['minimum'],row['maximum'])))
    return deepcopy(row)
