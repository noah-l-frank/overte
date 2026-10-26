"""Scene two has quiet current UI and samplers, with actual holders retained.

No cached image/GPU/Qt object is called destroyed by this stage. Its separately
versioned protocol summary leaves process resources owned until OS/SDK end.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.avatar_held_marker_scope import IOSAvatarHeldMarkerScope
from ios.adapters.avatar_held_samples import IOSAvatarHeldSamples
from ios.adapters.avatar_scene import IOSAvatarScene,Frozen
from ios.adapters import avatar_cleanup_sources
from ios.adapters.avatar_held_ui import disposition as panel_disposition
from ios.adapters.avatar_observation import source_history


class IOSAvatarHeldScene(IOSAvatarScene):
    VERSION=2
    Marker=IOSAvatarHeldMarkerScope
    Samples=IOSAvatarHeldSamples

    @staticmethod
    def restored_sources(*args,**kwargs):return avatar_cleanup_sources.restored_held(*args,**kwargs)

    @staticmethod
    def resource_quiet(frame,scope):
        need(type(scope) is IOSAvatarHeldMarkerScope)
        return scope.dispositions(frame,scope.frames[scope.state['webAdmission']-1])

    @staticmethod
    def holders_unchanged(first,last,scope):return scope.unchanged(first,last,scope.pid)

    def scene_summary(self,p,acquisition,native):
        # The explicitly versioned shared stage retains actual process holders.
        from feature_journeys.retirement_receipts import AVATAR_HELD_CLASSES,AVATAR_HELD_REMAINING
        return dict(avatarHeldMarkerSceneQuietVersion=1,runId=self.run,sequence=p['sequence'],capturedEpochMs=acquisition['hostAfterEpochMs'],
            quiet=list(AVATAR_HELD_CLASSES),remaining=list(AVATAR_HELD_REMAINING),lifecycle=deepcopy(native['lifecycle']))

    def held_originals(self,reference):
        _proof,joined=self.joined(reference);p=joined['original'];scope=joined['scope']
        frame=scope.frames[p['quiet'][-1]['scope']-1]
        parts=self.resource_quiet(frame,scope)
        history=joined['history']
        panel=panel_disposition(history.frames[p['quiet'][-1]['source']['index']-1]['originals']['widgets'],binding=self.binding,run=self.run)
        rows=parts['web']['holders']+parts['ui']['holders']+[parts['process']]+panel['holders']
        need(len({row['resource'] for row in rows})==len(rows));return deepcopy(sorted(rows,key=lambda row:row['resource']))


def scene_type(value):
    need(type(value) is dict and type(value.get('iosAvatarSceneVersion')) is int)
    version=value['iosAvatarSceneVersion'];need(version in (1,2));return IOSAvatarHeldScene if version==2 else IOSAvatarScene
