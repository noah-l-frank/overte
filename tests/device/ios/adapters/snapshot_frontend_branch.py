"""Causal original Window/queue/job join for explicit normal Upload4.

The full reviewed V8 stack and exact existing HTTP original are mandatory.
This composes originals; it cannot execute a Script branch or native input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from ios.adapters import avatar_call_stack,snapshot_causal_dispatch as causal

PINS=Path(__file__).parents[1]/'snapshot-causal-callsite-pins.v1.json'


def qualify(observed,root):
    pins=json.loads(PINS.read_text())
    exact(pins,{'snapshotCausalCallsitePinsVersion','encoding','profile','sources','frames'})
    need(type(pins['snapshotCausalCallsitePinsVersion']) is int and pins['snapshotCausalCallsitePinsVersion']==1
        and pins['encoding']=='utf-16le-code-units' and pins['profile']=='normal-share-for-url'
        and set(pins['sources'])=={'system/snapshot.js','modules/request.js'} and len(pins['frames'])==5)
    frames=observed['caller']['snapshotCombinedStack']['frames'];need(len(frames)==len(pins['frames']))
    for actual,pin in zip(frames,pins['frames']):
        exact(pin,{'source','line','column','token'});need(pin['source'] in pins['sources'])
        expected=pins['sources'][pin['source']];exact(expected,{'codeUnits','sha256'})
        compiled=actual['compiled'];url=root+pin['source'];url_sha=hashlib.sha256(url.encode()).hexdigest()
        need(actual['line']==pin['line'] and actual['column']==pin['column'] and not actual['isEval'] and not actual['isConstructor']
            and actual['sourceUrlSha256']==compiled['urlSha256']==url_sha
            and compiled['sha256']==expected['sha256'] and compiled['codeUnits']==expected['codeUnits'])
    return pins['profile']


def original(native,value):
    root=native.capture.root_original(native.capture.state['roots']);calls=causal.admitted(value,root)
    settled=native.capture.history('work',native.capture.state['settled']['work']).historical()['packet']
    worker=native.capture.work_source().admit(settled,root,quiet=True);history=avatar_call_stack.History()
    for entry in settled['source']['callerStacks']:history.accept(entry['callerStack'])
    for observed in calls:
        caller=observed['caller'];need(same(caller['manager'],worker['manager']) and same(caller['code'],worker['code'])
            and same(caller['snapshotCombinedSources'],worker['codeSources']))
        history.accept(caller['snapshotCombinedStack'])
    return value


def call(native,value):
    before=native.causal_original(native.state['causalBefore']);original(native,value)
    causal.validate(value,dict(schemaVersion=1,action=causal.ACTION,commandId=value['requestId'],runId=native.run),
        int(native.binding['processIdentity']),previous=before)
    baseline=before['source']['calls'];old={row['instance'] for row in baseline}
    if old:need(causal.drained(before,list(old)))
    if native.state['causalAfter'] is not None:
        after=native.causal_original(native.state['causalAfter'])
        if value['requestId']!=after['requestId']:
            causal.validate(value,dict(schemaVersion=1,action=causal.ACTION,commandId=value['requestId'],runId=native.run),
                int(native.binding['processIdentity']),previous=after)
    fresh=[row for row in value['source']['calls'] if row['instance'] not in old];need(len(fresh)==1)
    observed=fresh[0];need(observed['file']['privateName'] and observed['file']['name']==native.file['name']
        and observed['upload']==native.state['job'] and observed['associatedEpochMs'] is not None
        and before['clockAfter']['epochMs']<=observed['bornEpochMs']
        and native.delivery_source('input')['clock']['epochMs']<=observed['bornEpochMs'])
    stages=[row['stage'] for row in observed['hops']]
    need(stages in (['window','application','snapshot'],['window','application','snapshot','snapshot-queue','snapshot']))
    root=native.capture.root_original(native.capture.state['roots']);qualify(observed,root)
    http=native.http_original(native.state['httpAfter']);causal.http_join(observed,http,root)
    history=avatar_call_stack.History();history.accept(observed['caller']['snapshotCombinedStack'])
    for entry in http['callerStacks']:history.accept(entry['callerStack'])
    return deepcopy(observed)


def joined(backend,consumption):
    native=backend.native;need(backend.version==4 and native.frontend_caller and native.historical and native.state['result'] is not None)
    after=native.causal_original(native.state['causalAfter']);observed=call(native,after)
    need(consumption['upload']==observed['upload'] and consumption['xhrId']==observed['http']['xhrId']
        and consumption['replyId']==observed['http']['replyId']
        and consumption['backendResponseId']==observed['http']['finished']['details']['responseId']
        and observed['bornEpochMs']<=consumption['nativeUploadBornEpochMs']<=observed['associatedEpochMs'])
    quiet=[]
    for group in native.state['quiet']:
        packet=native.causal_original(group['causal']);current=call(native,packet)
        need(current['instance']==observed['instance'] and causal.drained(packet,[current['instance']]))
        quiet.append(digest(packet))
    need(len(quiet)==3)
    return dict(snapshotFrontendBranchVersion=1,runId=native.run,binding=deepcopy(native.binding),
        nativeUploadResultSha256=digest(native.proof()),frontendConsumptionSha256=digest(consumption),
        causalBeforeSha256=digest(native.causal_original(native.state['causalBefore'])),causalAfterSha256=digest(after),causalQuietSha256=quiet,
        call=observed['instance'],upload=observed['upload'],xhrId=consumption['xhrId'],replyId=consumption['replyId'],
        backendResponseId=consumption['backendResponseId'],callsite='normal-share-for-url',
        sameCaptureManagerJoined=True,sameCompiledV8HistoryJoined=True,actualResponseCallbackJoined=True,
        originalWindowCallerJoined=True,originalNativeUploadIDJoined=True,diagnosticQueueScopesDrained=True,
        renderedReviewRequired=True,externalMetaverseRegistrationRequired=True,wholeFeatureRequired=True)
