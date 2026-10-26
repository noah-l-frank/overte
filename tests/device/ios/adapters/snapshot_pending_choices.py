"""Actual owned SNAP popup delegates, closed to animated/still choices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.snapshot_export_controls import identity

IDS=frozenset({'snapshot.mode.animated','snapshot.mode.still'})
FIELDS={'snapshotPendingChoice'}


def metadata(value):
    exact(value,{'snapshotPendingChoiceVersion','rootId','qmlSource','comboId','option','selectedMode','format','checked','popupOpen','inputReady'})
    need(type(value['snapshotPendingChoiceVersion']) is int and value['snapshotPendingChoiceVersion']==1
        and value['option'] in ('animated','still') and integer(value['selectedMode'],0,3) and value['format'] in ('png','jpg','webp')
        and all(type(value[key]) is bool for key in ('checked','popupOpen','inputReady')))
    identity(value['rootId']);identity(value['comboId']);need(type(value['qmlSource']) is str);url=urlsplit(value['qmlSource'])
    need(type(value['qmlSource']) is str and len(value['qmlSource'])<=4096 and all(ord(char)>=32 for char in value['qmlSource'])
        and url.scheme in ('qrc','file') and not url.netloc and not url.query and not url.fragment
        and url.path.endswith('/system/snapshot/NativeSnapshotReview.qml')
        and value['checked']==(value['selectedMode']==(1 if value['option']=='animated' else 0)))
    return value


def project(value,control):
    need(control in IDS and value.get('snapshotPendingControlsVersion')==1 and type(value['snapshotPendingControlsVersion']) is int)
    rows=[row for row in value['controls'] if row['id']==control];need(len(rows)==1);row=rows[0];meta=metadata(row['snapshotPendingChoice'])
    need(row['checked']==meta['checked'] and control=='snapshot.mode.'+meta['option'] and row['enabled'] and meta['inputReady'] and meta['popupOpen'])
    result=dict(scope={key:value[source] for key,source in [('processId','processId'),('instance','instance'),('sampleEpochMs','sampleEpochMs'),('elapsedMs','elapsedMs'),('sequence','lastSequence')]},
        control={key:deepcopy(row[key]) for key in ('id','token','enabled','focused','checked')},root=deepcopy(meta))
    reference(result,control);return result


def reference(value,control):
    exact(value,{'scope','control','root'});need(control in IDS);scope=value['scope'];row=value['control'];meta=metadata(value['root'])
    exact(scope,{'processId','instance','sampleEpochMs','elapsedMs','sequence'});identity(scope['instance'])
    need(integer(scope['processId'],1) and integer(scope['sampleEpochMs'],1) and integer(scope['elapsedMs']) and integer(scope['sequence']))
    exact(row,{'id','token','enabled','focused','checked'});identity(row['token'])
    need(row['id']==control=='snapshot.mode.'+meta['option'] and row['enabled'] is True and type(row['focused']) is bool
        and type(row['checked']) is bool and row['checked']==meta['checked'] and meta['inputReady'] and meta['popupOpen']);return row


def same_reference(before,after,control):
    reference(before,control);reference(after,control)
    need(same(before['control'],after['control']) and same(before['root'],after['root'])
        and all(before['scope'][key]==after['scope'][key] for key in ('instance','processId','sequence'))
        and all(0<=after['scope'][key]-before['scope'][key]<=3000 for key in ('sampleEpochMs','elapsedMs')))
