"""Fresh actual marker/cache/UI holders after the original Scene2 barrier.

The scope's original admission and current independent Web/Tail originals are
joined without a World getter. No held resource is inferred destroyed here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters import original_marker_holders as policy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from adapters.script_ui_root_ownership import membership
from feature_journeys.terminal import held
from feature_journeys.retirement_receipts import sha
from ios.adapters.avatar_held_marker_scope import IOSAvatarHeldMarkerScope
from ios.adapters.avatar_held_ui import disposition as panel_disposition
from ios.adapters.avatar_held_tail import IOSAvatarHeldTail
from ios.adapters.emote_native_prefix import follow


class AvatarMarkerLifetime:
    def __init__(self,scope,scene_frame,*,scene_reference,binding,run):
        need(type(scope) is IOSAvatarHeldMarkerScope and scope.state['phase']=='released' and scope.state['cleanupMode']=='full'
            and scope.state['pending'] is None and scene_frame in scope.frames and scope.run==run and same(scope.binding,binding))
        exact(scene_reference,{'index','sha256'});need(integer(scene_reference['index'],1,64) and sha(scene_reference['sha256']))
        scope.lock.assert_held();self.scope,self.binding,self.run,self.scene_reference=scope,context(binding),run,deepcopy(scene_reference)
        self.pid=int(binding['processIdentity']);self.scene=deepcopy(scene_frame)
        self.admitted=deepcopy(scope.frames[scope.state['webAdmission']-1]['web'])
        self.process=deepcopy(scope.frames[scope.state['baseline']-1]['clockJoin']['nativeBefore'])
        self.ui=membership(scene_frame['widgets']['scriptInventory'],pid=self.pid)
    def at(self,parts):
        self.scope.lock.assert_held();tail=parts['tail'];need(type(tail) is IOSAvatarHeldTail and tail.historical and same(tail.binding,self.binding) and tail.run==self.run)
        widgets=parts['ui']['widgetsReceipt']['observation'];web=parts['webReceipt'];source=web['packet'];clock=parts['ui']['clockJoin']
        follow(self.scene['clockJoin']['nativeAfter'],clock['nativeBefore'])
        follow(clock['nativeAfter'],web['clockJoin']['nativeBefore'])
        native=web['clockJoin']['nativeAfter'];follow(native,parts['right']['clockJoin']['nativeBefore'])
        from ios.adapters.web_closures import continuity
        continuity(self.scene['web'],source,self.pid)
        disposition=policy.web('avatar',source,self.admitted)
        ui=policy.ui('avatar',widgets['scriptInventory'],pid=self.pid,epoch=clock['nativeAfter']['capturedEpochMs'],previous=self.ui)
        need(clock['nativeBefore']['capturedEpochMs']<=ui['ownership']['capturedEpochMs']<=clock['nativeAfter']['capturedEpochMs'])
        panel=panel_disposition(widgets,binding=self.binding,run=self.run)
        process=policy.process('avatar',self.process,native,binding=self.binding,run=self.run)
        originals=disposition['holders']+ui['holders']+panel['holders']+[process]
        originals=sorted(originals,key=lambda row:row['resource']);need(len({row['resource'] for row in originals})==len(originals))
        resources=[{key:deepcopy(row[key]) for key in ('resource','kind','originalSha256')} for row in originals];held(resources)
        return dict(iosAvatarMarkerLifetimeVersion=1,runId=self.run,binding=deepcopy(self.binding),sceneReference=deepcopy(self.scene_reference),
            webOriginalSha256=digest(web),widgetsOriginalSha256=digest(widgets),webDisposition=disposition,uiDisposition=ui,
            panelDisposition=panel,processOriginal=process,heldOriginals=originals,heldResources=resources)
