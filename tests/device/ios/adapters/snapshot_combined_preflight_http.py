"""Closed Combined XHR originals and separately admitted response reads.

The Script root is an independently observed input to local admission, never
a requested native fact. Backend/Upload/capture-manager joins remain required.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from adapters.native_feature_observation import exact,need
from adapters.native_script_roots import root_url
from ios.adapters import avatar_social_http as shared,snapshot_preflight_http as separate,snapshot_combined_work
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-snapshot-combined-preflight-http'
FILE=ACTION+'.json'
LIMIT=shared.LIMIT
FILES=('defaultScripts.js','system/snapshot.js','modules/request.js','system/snapshot/featureSnapshotWork.js')


def command(value):return shared.command(value,_combined=True)
def validate(value,query,pid,epoch=None,previous=None):return shared.validate(value,query,pid,epoch,previous,_combined=True)
def events(value):return shared.events(value,_combined=True)
def original(value):
    need(type(value) is dict)
    return validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION,runId=value.get('runId')),value.get('processId'))


def admit(value,scripts_root):
    original(value);root=root_url(scripts_root);pins=json.loads(snapshot_combined_work.PIN_FILE.read_text())
    exact(pins,{'snapshotCombinedWorkSourcePinsVersion','encoding','sources'})
    need(type(pins['snapshotCombinedWorkSourcePinsVersion']) is int and pins['snapshotCombinedWorkSourcePinsVersion']==1
        and pins['encoding']=='utf-16le-code-units' and set(pins['sources'])==set(FILES))
    states=events(value)
    for state in states.values():
        observed=state['created']['details'];need(observed['engine']['url']==root+'defaultScripts.js')
        need(observed['submitted']['encoding']==pins['encoding'] and all(observed['submitted'][key]==pins['sources']['defaultScripts.js'][key]
            for key in ('codeUnits','sha256')))
        sources=observed['codeSources'];need(sources['complete'] and len(sources['evaluations'])==len(FILES))
        for path in FILES:
            entries=[entry for entry in sources['evaluations'] if entry['url']==root+path]
            need(len(entries)==1 and entries[0]['encoding']==pins['encoding']
                and all(entries[0][key]==pins['sources'][path][key] for key in ('codeUnits','sha256')))
    return states


def response_reads(value,scripts_root):
    rows=separate._response_reads(value,admit(value,scripts_root))
    for row in rows:row.update(combinedSourceAdmitted=True,sameCaptureManagerRequired=True)
    return rows


def drained(value,owned_xhrs):return shared.drained(value,owned_xhrs,_combined=True)


class IOSSnapshotCombinedPreflightHttp(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosSnapshotCombinedPreflightHttpAcquisitionVersion'
