"""Typed original scene/view/PNG plus independent Actor render-entry agreement.

The finite render-entry profile cannot certify material/texture/skin fidelity,
Actor image pixels, capture bracketing, canonical /samples publication or End.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.snapshot_capture_review_owner import SnapshotCaptureReviewOwner
from ios.adapters.snapshot_provenance_packet import SnapshotProvenancePacket
from ios.adapters.snapshot_scene_witness import SnapshotSceneWitnessOwner
from ios.adapters.snapshot_scene import measured_entities
from ios.adapters.snapshot_capture_clock import operation


class SnapshotSceneReviewJoin:
    def __init__(self,review,provenance,actor,actor_original):
        need(type(review) is SnapshotCaptureReviewOwner and type(provenance) is SnapshotProvenancePacket
            and type(actor) is SnapshotSceneWitnessOwner and type(actor_original) is dict)
        self.review,self.provenance,self.actor=review,provenance,actor
        self.actor_original=deepcopy(actor_original);self.monotonic=review.monotonic
        need(review.lock is provenance.lock and same(review.binding,provenance.binding)
            and review.run==provenance.run==actor.run and provenance.role=='primary' and actor.role=='actor'
            and review.store.path.parent!=actor.store.path.parent and review.lock.path!=actor.lock.path
            and review.binding['targetFingerprint']!=actor.binding['targetFingerprint']
            and all(review.binding[key]==actor.binding[key] for key in ('sourceRevision','artifactSha256'))
            and review.page.fixture_url==actor.fixture_url)

    @operation
    def proof(self):
        self.review.lock.assert_held();self.actor.lock.assert_held()
        reviewed=self.review.proof();primary=self.provenance.join_capture(self.review.capture)
        independent=self.actor.validate_original(self.actor_original)
        need(same(reviewed['pins']['captureResultSha256'],primary['pins']['captureResultSha256'])
            and self.actor.state['ticket']==self.review.state['ticket'])
        captured=self.review.capture.state['phaseOriginal'];before=independent['phaseBefore'];after=independent['phaseAfter']
        need(captured['instance']==before['instance']==after['instance'] and captured['runId']==before['runId']==after['runId']
            and same(captured['activations'],before['activations']) and same(before['activations'],after['activations']))
        a=primary['provenance']['frame'];b=independent['nativeOriginal']['packet']['source']['frame']
        need(a['snapshotFrameProvenanceVersion']==2 and same(measured_entities(a['scene']),measured_entities(b['scene']))
            and same(a['camera'],b['camera']) and same(a['worldFromCamera'],b['worldFromCamera']) and same(a['viewport'],b['viewport']))
        return dict(iosSnapshotSceneRenderedReviewVersion=1,binding=deepcopy(self.review.binding),actorBinding=deepcopy(self.actor.binding),
            runId=self.review.run,ticket=self.review.state['ticket'],sceneInputProfile='entity-render-entry-v1',
            sameOrdinaryFrameCameraCropCallbackPNGEstablished=True,primaryRenderedReviewEstablished=True,
            independentActorOriginalSceneInputsAgree=True,independentActorRecordedViewAgrees=True,
            pins=dict(renderedReviewSha256=digest(reviewed),ordinaryProvenanceSha256=digest(primary),
                actorWitnessOriginalSha256=digest(self.actor_original),actorPacketOwnerSha256=independent['packetOwnerSha256']),
            actualPrimaryScene=deepcopy(a['scene']),actualActorScene=deepcopy(b['scene']),
            actorSamplesBracketCaptureRequired=True,actorRenderedPixelsRequired=True,canonicalActorPublicationRequired=True,
            fullSceneAppearanceFidelityRequired=True,destinationCompositionRequired=True,pairedCleanupRequired=True,
            wholeFeatureRequired=True,nativeQualified=False,deviceQualified=False,wholeQualified=False)
