"""Explicit marker-scene proof with Login/process responsibility still held.

Original Scene-v1 files and their Scene-v2 interpretation stay unchanged. This
additional consumer emits only the separately versioned scoped protocol stage.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from feature_journeys.retirement_receipts import AVATAR_SCOPED_CLASSES,AVATAR_SCOPED_REMAINING
from ios.adapters.avatar_login_lifetime import AvatarLoginLifetime
from ios.adapters.avatar_scene import IOSAvatarScene,Frozen
from ios.adapters.avatar_observation import source_history

VERSION=1


class AvatarScopedScene:
    VERSION=VERSION
    Scene=IOSAvatarScene
    def __init__(self,scene,login):
        need(type(scene) is self.Scene and isinstance(login,AvatarLoginLifetime)
            and scene.run==login.run and scene.role==login.role and same(scene.binding,login.binding))
        self.scene,self.login=scene,login

    def original(self,reference):
        self.scene.lock.assert_held();need(reference in self.scene.state['records'])
        return dict(iosAvatarScopedSceneOriginalVersion=self.VERSION,runId=self.scene.run,role=self.scene.role,
            binding=deepcopy(self.scene.binding),scene=deepcopy(reference),loginOriginalSha256=digest(self.login.original))

    def joined(self,original):
        exact(original,{'iosAvatarScopedSceneOriginalVersion','runId','role','binding','scene','loginOriginalSha256'})
        need(same(original,self.original(original['scene'])))
        scene=self.scene;proof,joined=scene.joined(original['scene']);p=joined['original'];sources=joined['history']
        holds=[self.login.source(sources,cut['source']) for cut in p['quiet']]
        need(len(holds)>=3)
        # These are actual retained operands, never a root-death inference.
        # Their immutable admission and weak histories are checked again at
        # every original quiet cut, including the last publication cut.
        for before,after in zip(holds,holds[1:]):
            from ios.adapters.login_root_ownership import validate
            validate(after['ownership'],pid=int(scene.binding['processIdentity']),previous=before['ownership'])
        scoped=self.summary(proof['scene'])
        sha=digest(original);retirement=deepcopy(proof['retirement']);retirement.update(originalSha256=sha,
            provenance=dict(version=1,namespace='ios-avatar-scoped-scene-original',reference=dict(index=original['scene']['index'],sha256=sha),
                originalSha256=sha))
        resources=self.resources(joined,holds)
        return dict(ticket=proof['ticket'],scene=scoped,acquisition=deepcopy(proof['acquisition']),retirement=retirement,
            loginLifetimes=holds,heldResources=resources)

    def resources(self,joined,holds):return deepcopy(holds[-1]['heldResources'])

    def summary(self,summary):
        return dict(avatarMarkerSceneQuietVersion=1,runId=self.scene.run,sequence=summary['sequence'],
            capturedEpochMs=summary['capturedEpochMs'],quiet=list(AVATAR_SCOPED_CLASSES),remaining=list(AVATAR_SCOPED_REMAINING),
            lifecycle=deepcopy(summary['lifecycle']))

    def derive(self,original):
        value=self.joined(original)
        return {key:value[key] for key in ('ticket','scene','acquisition','retirement')}
