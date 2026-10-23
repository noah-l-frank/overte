"""Pure original Snapshot base-frame grammar shared by live and OS recovery.

No source query, current foreground authority or effect is supplied by a parser.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from adapters.native_feature_observation import decode,exact,need,number
from adapters.pico4 import snapshot_originals as native_source
from adapters.pico4.snapshot_script_originals import validate as script_packet
from adapters.pico4.snapshot_capture_source import validate as file_packet
from adapters.pico4.navigation import validate_snapshot
from adapters.native_script_work import validate as work_packet,scope as work_scope
from feature_journeys.contract import typed_equal


def original(row,limit):
    exact(row,{'raw','sha256'})
    need(type(row['raw']) is str and len(row['raw'].encode())<=limit
        and hashlib.sha256(row['raw'].encode()).hexdigest()==row['sha256'])
    return decode(row['raw'])


def clocks(row):
    return (row['hostMonotonic']*1000,decode(row['native']['raw'])['capturedEpochMs'],decode(row['script']['raw'])['capturedEpochMs'],
        row['ui']['updatedEpochMs'],decode(row['files']['raw'])['capturedEpochMs'])+(() if decode(row['script']['raw'])['snapshotScriptOriginalsVersion']!=3 else
        (decode(row['script']['raw'])['captureContext']['capturedEpochMs'],))+(() if row['work'] is None else
        (row['work']['capturedEpochMs'],row['work']['source']['work']['capturedEpochMs']))


def validate(row,run,pid,bridge):
    exact(row,{'native','script','ui','files','inventory','work','hostMonotonic'})
    native=original(row['native'],native_source.LIMIT);script=original(row['script'],65536)
    native_source.validate(native,run,native['commandId'],pid,native['capturedEpochMs'])
    script_packet(script,run,script['commandId'],pid,script['capturedEpochMs'])
    need(native['snapshotNativeCaptureVersion']==2 and script['snapshotScriptOriginalsVersion'] in (2,3))
    validate_snapshot(row['ui'],pid,row['ui']['updatedEpochMs'])
    exact(row['files'],{'raw','sha256','request'})
    packet=original({key:row['files'][key] for key in ('raw','sha256')},262144)
    file_packet(packet,row['files']['request'],pid,packet['capturedEpochMs'])
    need(packet['runId']==run and row['ui']['bridgeId']==bridge and number(row['hostMonotonic'],0,1e15))
    exact(row['inventory'],{'files','rows','capturedEpochMs'})
    need(row['inventory']['capturedEpochMs']==packet['capturedEpochMs']
        and type(row['inventory']['files']) is list and type(row['inventory']['rows']) is list)
    events=script['history']['events']
    if events:
        caller=events[-1]['caller'];value=row['work']
        request=dict(schemaVersion=1,commandId=value['requestId'],action='feature-script-work-observe',managerInstance=caller['manager']['instance'])
        work_packet(value,request,pid,value['capturedEpochMs'])
        need(typed_equal(value['source']['manager'],caller['manager']) and typed_equal(value['source']['code'],caller['code']))
        work_scope(value,caller['compilation'])
    else:need(row['work'] is None)
    source_clocks=clocks(row)[1:]
    need(max(source_clocks)-min(source_clocks)<=1500);return native,script,packet
