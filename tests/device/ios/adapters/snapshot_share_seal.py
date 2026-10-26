"""Actual original Share admission-reader closure and current output pins."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import re
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.snapshot_destination import stamp
from ios.adapters.snapshot_share_admission import IOSSnapshotShareAdmissionOwner

FIELDS={'snapshotShareAdmissionSealVersion','requestId','instance','processId','bundleId','sequence','sourceBirthClock','preparedClock',
    'bundle','bundleRootIdentity','clockBefore','clockAfter','outputs','descriptorClose','sealed','outputReadersClosed','collectorAlive','readerClosed'}


def admitted_outputs(admission):
    need(isinstance(admission,IOSSnapshotShareAdmissionOwner));admission.bound();admission.result();outputs={};last=None;identity=None
    for row in admission.state['queries']:
        need(row['frame'] is not None);packet=admission.original(row,last);last=packet
        ref=admission.frames.expand(row['frame']);raw=base64.b64decode(admission.frames.read(ref)['raw'],validate=True)
        need(same(packet,decode(raw.decode('utf-8'))));outputs[row['action']]=raw
        if row['action']=='identity':identity=packet
    need(identity is not None and identity['status']=='ready' and set(outputs)=={'identity','clock'})
    return last,identity,outputs


def original(value,nonce,admission):
    exact(value,FIELDS);last,identity,raw=admitted_outputs(admission)
    need(type(value['snapshotShareAdmissionSealVersion']) is int and value['snapshotShareAdmissionSealVersion']==1
        and type(nonce) is str and re.fullmatch('ios-[a-f0-9]{32}',nonce) and value['requestId']==nonce
        and type(value['instance']) is str and value['instance']==last['instance']
        and integer(value['processId'],1,2147483647) and value['processId']==last['processId']==int(admission.binding['processIdentity'])
        and value['bundleId']==last['bundleId']==admission.artifact['bundle']['bundleId']
        and type(value['sequence']) is int and value['sequence']==last['sequence']+1
        and same(value['sourceBirthClock'],last['sourceBirthClock']) and same(value['preparedClock'],identity['preparedClock'])
        and same(value['bundle'],identity['bundle']) and type(value['bundleRootIdentity']) is str and re.fullmatch('[a-f0-9]{64}',value['bundleRootIdentity']))
    stamp(value['clockBefore'],last['clockAfter']);stamp(value['clockAfter'],value['clockBefore'])
    need(value['clockAfter']['epochMs']-value['clockBefore']['epochMs']<1500
        and value['clockAfter']['monotonicMs']-value['clockBefore']['monotonicMs']<1500)
    close=value['descriptorClose'];exact(close,{'clockBefore','clockAfter','succeeded'})
    stamp(close['clockBefore'],value['clockBefore']);stamp(close['clockAfter'],close['clockBefore']);stamp(value['clockAfter'],close['clockAfter'])
    need(all(type(value[key]) is bool for key in ('sealed','outputReadersClosed','collectorAlive','readerClosed'))
        and type(close['succeeded']) is bool and close['succeeded']==value['readerClosed'] and value['sealed'] is True)
    need(type(value['outputs']) is list and len(value['outputs'])==2);parent=None
    for action,pin in zip(('identity','clock'),value['outputs']):
        exact(pin,{'name','revision','sha256','byteCount','parentIdentity'})
        need(pin['name']=='snapshot-share-companion-'+action+'.json' and type(pin['revision']) is str and re.fullmatch('[a-f0-9]{64}',pin['revision'])
            and type(pin['parentIdentity']) is str and re.fullmatch('[a-f0-9]{64}',pin['parentIdentity'])
            and integer(pin['byteCount'],1,262144) and pin['byteCount']==len(raw[action]) and pin['sha256']==hashlib.sha256(raw[action]).hexdigest())
        if parent is None:parent=pin['parentIdentity']
        else:need(parent==pin['parentIdentity'])
    return value


def qualified(value):
    need(value['sealed'] is True and value['readerClosed'] is True and value['outputReadersClosed'] is True
        and value['collectorAlive'] is False and value['descriptorClose']['succeeded'] is True)
    return value
