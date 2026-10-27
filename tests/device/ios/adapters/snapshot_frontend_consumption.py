"""Pure join of retained Combined XHR, backend and normal upload originals.

The native process epoch joins independent sources; their monotonic origins
remain separate. Reading responseText proves consumption, not the subsequent
JavaScript branch or the causal caller of Window.shareSnapshot.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from urllib.parse import urlsplit
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters import snapshot_combined_preflight_http as http


def joined(backend):
    native=backend.native
    need(backend.version in (3,4) and native.frontend_http and native.combined and native.historical
        and native.state['result'] is not None and native.state['httpBefore'] is not None and native.state['httpAfter'] is not None)
    before=native.http_original(native.state['httpBefore']);after=native.http_original(native.state['httpAfter'])
    http.validate(after,dict(schemaVersion=1,action=http.ACTION,commandId=after['requestId'],runId=native.run),
        int(native.binding['processIdentity']),previous=before)
    old=http.events(before);root=native.capture.root_original(native.capture.state['roots'])
    original=backend.packet(backend.state['preflight']);preflight=backend.preflight_join()
    request=next(row for row in original['snapshot']['requests'] if row['requestId']==preflight['requestId'])
    response=next(row for row in original['responses'] if row['requestId']==preflight['requestId'])
    need(response['original'] is not None and request['written'] and request['left'] is not None)
    expected=base64.b64decode(response['original']['base64'],validate=True)
    query=base64.b64decode(response['requestQueryOriginal']['base64'],validate=True).decode('ascii')
    endpoint=urlsplit(native.fixture_url);received=native.delivery_source('input')
    decision=native.packet('uploads',native.state['decision'])
    jobs=[row for row in decision['source']['uploads'] if row['instance']==native.state['job']];need(len(jobs)==1)
    eligible=[]
    for row in http.response_reads(after,root):
        if row['xhrId'] in old:continue
        actual=urlsplit(row['requestUrl']);body=row['body']
        if ((actual.scheme,actual.netloc)!=(endpoint.scheme,endpoint.netloc)
                or actual.path!='/api/v1/user_stories' or actual.query!=query
                or row['backendResponseId']!=request['requestId']
                or body['bytes']!=response['original']['bytes'] or body['sha256']!=response['original']['sha256']
                or base64.b64decode(body['contentBase64'],validate=True)!=expected):continue
        # Only process epoch fields share an origin. Do not compare HTTP's
        # monotonic counter to native-main or backend monotonic counters.
        if not (received['clock']['epochMs']<=row['createdClock']['epochMs']
                <=row['sentClock']['epochMs']<=row['finishedClock']['epochMs']
                <=row['readClock']['epochMs']<=jobs[0]['bornEpochMs']):continue
        need(http.drained(after,[row['xhrId']]));eligible.append(row)
    need(len(eligible)==1);row=eligible[0]
    return dict(snapshotFrontendConsumptionVersion=1,runId=native.run,binding=deepcopy(native.binding),
        captureResultSha256=digest(native.capture.result()),nativeUploadResultSha256=digest(native.proof()),
        httpBeforeSha256=digest(before),httpAfterSha256=digest(after),backendOriginalSha256=digest(original),
        xhrId=row['xhrId'],replyId=row['replyId'],backendResponseId=row['backendResponseId'],
        querySha256=request['querySha256'],responseSha256=row['body']['sha256'],engine=deepcopy(row['engine']),
        nativeCreated=deepcopy(row['createdClock']),nativeRead=deepcopy(row['readClock']),
        nativeUploadBornEpochMs=jobs[0]['bornEpochMs'],upload=native.state['job'],
        sameCaptureManagerJoined=True,originalResponseTextRead=True,backendBytesJoined=True,
        knownXHRObjectsDrained=True,normalNativeUploadAfterRead=True,
        frontendBranchAcceptanceRequired=True,renderedReviewRequired=True,
        externalMetaverseRegistrationRequired=True,wholeFeatureRequired=True)
