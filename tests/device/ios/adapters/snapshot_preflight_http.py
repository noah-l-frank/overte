"""Original Snapshot XHR response reads and actual weak lifetime observations.

The closed profile shares the existing Social event parser, retaining its
literal default grammars. A response read is separate from Upload effects,
authenticated backend admission, OS absence and whole-journey completion.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from ios.adapters import avatar_social_http as shared
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-snapshot-preflight-http'
FILE='feature-ios-snapshot-preflight-http.json'
LIMIT=262144


def command(value):return shared.command(value,_snapshot=True)
def validate(value,query,pid,epoch=None,previous=None):return shared.validate(value,query,pid,epoch,previous,_snapshot=True)
def events(value):return shared.events(value,_snapshot=True)
def original(value):
    need(type(value) is dict)
    return validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION,runId=value.get('runId')),value.get('processId'))


def response_reads(value):
    original(value);return _response_reads(value,events(value))


def _response_reads(value,states):
    result=[]
    for xhr,state in states.items():
        for reply,observed in state['replies'].items():
            finished,read=observed['finished'],observed['read']
            if finished is None or read is None or not observed.get('callbackRead'):continue
            detail=finished['details'];sent=observed['sent']['details']
            if detail['httpStatus']!=200 or detail['networkError']!=0 or not detail['responseId'] or detail['body'] is None or not sent['authorizationAttached']:continue
            result.append(dict(xhrId=xhr,replyId=reply,backendResponseId=detail['responseId'],requestUrl=sent['url'],body=deepcopy(detail['body']),
                engine=deepcopy(state['created']['details']['engine']),createdClock=deepcopy(state['created']['clock']),
                sentClock=deepcopy(observed['sent']['clock']),finishedClock=deepcopy(finished['clock']),readClock=deepcopy(read['clock']),
                nativeClockDomain=value['clockDomain'],nativeResponseTextRead=True,authenticatedBackendOriginalRequired=True,
                normalUploadEffectRequired=True,resourceRetirementRequired=True,wholeFeatureRequired=True))
    return result


def drained(value,owned_xhrs):return shared.drained(value,owned_xhrs,_snapshot=True)


class IOSSnapshotPreflightHttp(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosSnapshotPreflightHttpAcquisitionVersion'
