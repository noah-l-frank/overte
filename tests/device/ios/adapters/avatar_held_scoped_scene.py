"""Scoped scene2 names current quiet and preserves actual native holders."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from feature_journeys.terminal import held
from ios.adapters.avatar_held_scene import IOSAvatarHeldScene
from ios.adapters.avatar_scoped_scene import AvatarScopedScene
from ios.adapters.avatar_held_ui import disposition


class AvatarHeldScopedScene(AvatarScopedScene):
    VERSION=2
    Scene=IOSAvatarHeldScene

    def summary(self,summary):
        need(summary.get('avatarHeldMarkerSceneQuietVersion')==1);return deepcopy(summary)

    def resources(self,joined,holds):
        scope=joined['scope'];p=joined['original'];frame=scope.frames[p['quiet'][-1]['scope']-1]
        parts=self.scene.resource_quiet(frame,scope);source=joined['history'].frames[p['quiet'][-1]['source']['index']-1]
        panels=disposition(source['originals']['widgets'],binding=self.scene.binding,run=self.scene.run)
        originals=parts['web']['holders']+parts['ui']['holders']+[parts['process']]+panels['holders']
        resources=deepcopy(holds[-1]['heldResources'])+[{key:deepcopy(row[key]) for key in ('resource','kind','originalSha256')} for row in originals]
        resources.sort(key=lambda row:row['resource']);held(resources);return resources
