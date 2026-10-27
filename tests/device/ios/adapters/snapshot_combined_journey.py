"""Pure same-PNG join of the existing Combined upload and page-return paths.

This adds no Script, OS, input, backend request or cleanup. Independent image
fidelity, Photos, whole failure recovery and final retirement remain required.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_page_return_owner import SnapshotPageReturnOwner
from ios.adapters.snapshot_upload_backend_owner import IOSSnapshotUploadBackendOwner


def phase_prefix(before,after,run,*,strict=True):
    need(type(strict) is bool)
    for value in (before,after):phase_packet(value,run=run,area='snapshots',request=value['requestId'],epoch=value['capturedEpochMs'])
    need(before['active'] and after['active'] and before['instance']==after['instance']
        and before['createdEpochMs']==after['createdEpochMs']
        and same(before['activations'],after['activations'][:len(before['activations'])])
        and (len(before['activations'])<len(after['activations']) if strict else same(before,after)))
    if strict:need(after['sequence']>before['sequence'] and after['requestId']!=before['requestId'] and after['capturedEpochMs']>=before['capturedEpochMs'])


class SnapshotCombinedJourney:
    def __init__(self,returned,backend,*,monotonic=time.monotonic):
        need(type(returned) is SnapshotPageReturnOwner and returned.historical and returned.combined
            and type(backend) is IOSSnapshotUploadBackendOwner and backend.historical and backend.version==4
            and backend.native.frontend_caller and callable(monotonic))
        self.returned,self.backend,self.monotonic=returned,backend,monotonic
    @operation
    def proof(self):
        returned,backend=self.returned,self.backend;native=backend.native;files=returned.files;share=returned.end.share
        returned.bound();backend.guard();need(native.combined and native.frontend_http and native.historical
            and returned.run==backend.run and returned.fixture_url==backend.fixture_url
            and same(returned.binding,backend.binding) and native.root==returned.root
            and native.capture.store.path==files.capture.store.path
            and same(native.capture.previous,files.capture.previous))
        page_result=returned.proof();upload_result=backend.proof();capture_result=files.capture.result();pending_result=files.pending.result()
        need(upload_result['snapshotUploadBackendResultVersion']==4 and not upload_result['frontendBranchAcceptanceRequired']
            and page_result['snapshotPageReturnedVersion']==2 and returned.state['result'] is not None and backend.state['result'] is not None
            and files.pins['captureResultSha256']==native.pins['captureResultSha256']==share.state['capture']['resultSha256']==digest(capture_result)
            and native.pins['artifactJournalSha256']==files.pins['artifactJournalSha256']==share.state['capture']['artifactSha256'])
        phase_prefix(returned.page.state['phaseOriginal'],files.pending.state['phaseOriginal'],returned.run)
        phase_prefix(files.pending.state['phaseOriginal'],files.capture.state['phaseOriginal'],returned.run)
        phase_prefix(files.capture.state['phaseOriginal'],native.state['phaseOriginal'],returned.run)
        phase_prefix(native.state['phaseOriginal'],share.state['phaseOriginal'],returned.run)
        phase_prefix(share.state['phaseOriginal'],returned.phase_original,returned.run,strict=False)
        capture=files.capture;artifact=capture.history('artifact',capture.state['artifact']);fact,raw=artifact.originals()
        need(native.file==fact['file'] and upload_result['file']['bytes']==len(raw)
            and upload_result['file']['sha256']==fact['file']['sha256'])
        return dict(snapshotCombinedJourneyResultVersion=1,runId=returned.run,binding=deepcopy(returned.binding),
            fixtureUrl=returned.fixture_url,workProfile='combined',file=deepcopy(fact['file']),
            pins=dict(pageOwnerSha256=digest(returned.page.previous),pendingOwnerSha256=digest(files.pending.previous),
                captureResultSha256=digest(capture_result),artifactJournalSha256=digest(artifact.previous),
                uploadOwnerSha256=digest(native.previous),backendOwnerSha256=digest(backend.previous),
                backendResultSha256=digest(upload_result),journeyFilesOwnerSha256=digest(files.previous),
                shareOwnerSha256=digest(share.previous),archiveEndOwnerSha256=digest(returned.end.previous),
                returnOwnerSha256=digest(returned.previous),returnResultSha256=digest(page_result),pendingResultSha256=digest(pending_result)),
            originalMainAndPhasePrefixesJoined=True,normalPendingCancellationJoined=True,
            sameOriginalPNGJoined=True,originalCallbackUploadBackendJoined=True,ownedShareAndArchiveEndJoined=True,
            twoPrefixFileCleanupJoined=True,originalPageAndLauncherRestored=True,hostOriginalRetained=True,
            photosDestinationCompositionRequired=True,independentActorSceneAndRenderedReviewRequired=True,
            failedRecoveredWholeCompositionRequired=True,sourceMainSDKWitnessRetirementRequired=True,wholeFeatureRequired=True)
