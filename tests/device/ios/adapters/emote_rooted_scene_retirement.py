"""Project original rooted cleanup into the existing Emote Web-quiet stage.

Scene quiet retains native holders. Only a separate terminal OS/SDK owner can
end them. No source timestamp, private original or legacy Complete is changed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from feature_journeys.contract import result
from feature_journeys.retirement_receipts import WEB_SCENE_CLASSES,web_scene
from feature_journeys.terminal import held
from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope
from ios.adapters.emote_rooted_retirement import IOSEmoteRootedKeyedRetirement


class IOSEmoteRootedSceneRetirement:
    def __init__(self,owner):
        need(type(owner) is IOSEmoteRootedKeyedRetirement);self.owner=owner

    def read(self,reference):
        owner=self.owner;owner.lock.assert_held();owner.primary_lock.assert_held()
        measured=owner.derive(reference)
        exact(measured,{'ticket','public','acquisition','retirement','held'})
        rendered=owner.rendered_owner;frame=rendered.original(owner.original(reference)['renderedReference'])
        native=rendered.native_owner;original=native.original(frame['nativeReference'])
        scope=IOSEmoteRootedMarkerScope.archive(original['scope'],root=owner.root,binding=owner.binding,
            run=owner.run,role=owner.role,lock=owner.lock)
        rows=scope.held_originals();need(rows==measured['held'])
        held([{key:row[key] for key in ('resource','kind','originalSha256')} for row in rows])
        last=scope.frames[scope.state['quiet'][-1]-1]['clockJoin'];clock=measured['acquisition']
        need(last['hostBeforeEpochMs']<=clock['hostBeforeEpochMs']
            and last['hostBeforeMonotonic']<=clock['hostBeforeMonotonic'])
        # These are the two actual boundary pairs. Widen the containing read
        # to its genuine earlier scope acquisition; never renew a timestamp.
        acquisition=PhaseWitnessPublisher.acquisition(dict(clock,hostBeforeEpochMs=last['hostBeforeEpochMs'],
            hostBeforeMonotonic=last['hostBeforeMonotonic']))
        public=deepcopy(measured['public']);need(public['resources']==[] and not public['artifacts'])
        public['resources']=[row['resource'] for row in rows]
        result('feature.emotes.observe',public)
        scene=dict(webMarkerSceneQuietVersion=1,runId=owner.run,sequence=public['sequence'],
            capturedEpochMs=public['capturedEpochMs'],quiet=list(WEB_SCENE_CLASSES),
            remaining=['native-process-resources'],lifecycle=deepcopy(public['lifecycle']))
        web_scene(scene,owner.run,public['sequence'])
        return dict(ticket=measured['ticket'],public=public,sourcePublic=deepcopy(measured['public']),scene=scene,held=deepcopy(rows),
            acquisition=acquisition,retirement=deepcopy(measured['retirement']))

    def actor_original(self,reference):
        need(self.owner.role=='actor')
        value=self.read(reference)
        return {key:deepcopy(value[key]) for key in ('ticket','scene','acquisition','retirement')}
