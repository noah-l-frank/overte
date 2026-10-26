"""Separate Share archive native originals; no Photos or extension outcome."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.bundle_identity import compare
from ios.adapters.snapshot_destination import stamp


FIELDS={'snapshotShareCompanionObservationVersion','action','nonce','role','instance','processId','bundleId','sequence',
    'sourceBirthClock','clockBefore','clockAfter','status'}


def original(value,*,action=None,nonce=None,pid=None,bundle=None,previous=None):
    need(type(value) is dict and value.get('action') in ('identity','clock'));kind=value['action']
    exact(value,FIELDS|({'preparedClock','bundle'} if kind=='identity' else set()))
    need(type(value['snapshotShareCompanionObservationVersion']) is int and value['snapshotShareCompanionObservationVersion']==1
        and value['role']=='share-archive' and (action is None or kind==action)
        and type(value['nonce']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['nonce']) and (nonce is None or value['nonce']==nonce)
        and type(value['instance']) is str and re.fullmatch('[a-f0-9]{32}',value['instance'])
        and integer(value['processId'],1,2147483647) and (pid is None or value['processId']==pid)
        and type(value['bundleId']) is str and re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+',value['bundleId'])
        and (bundle is None or value['bundleId']==bundle) and integer(value['sequence'],1)
        and value['status'] in ('pending','ready','unavailable') and (kind=='identity' or value['status']!='pending'))
    stamp(value['sourceBirthClock']);stamp(value['clockBefore'],value['sourceBirthClock']);stamp(value['clockAfter'],value['clockBefore'])
    need(value['clockAfter']['epochMs']-value['clockBefore']['epochMs']<1500 and value['clockAfter']['monotonicMs']-value['clockBefore']['monotonicMs']<1500)
    if kind=='identity':
        if value['status']=='ready':
            compare(value['bundle'],value['bundle']);need(value['bundle']['bundleId']==value['bundleId'])
            stamp(value['preparedClock'],value['sourceBirthClock']);stamp(value['clockBefore'],value['preparedClock'])
        else:need(value['preparedClock'] is None and type(value['bundle']) is dict and not value['bundle'])
    if previous is not None:
        original(previous);need(all(same(previous[key],value[key]) for key in ('instance','processId','bundleId','sourceBirthClock','role'))
            and value['sequence']>previous['sequence'] and value['nonce']!=previous['nonce']);stamp(value['clockBefore'],previous['clockAfter'])
    return value


def admission(identity,before,after,expected):
    original(before,action='clock');original(identity,action='identity',previous=before);original(after,action='clock',previous=identity)
    need(before['status']==identity['status']==after['status']=='ready');compare(identity['bundle'],expected)
    need(after['clockAfter']['epochMs']-before['clockBefore']['epochMs']<1500
        and after['clockAfter']['monotonicMs']-before['clockBefore']['monotonicMs']<1500)
    return dict(snapshotShareCompanionCodeAdmissionVersion=1,role='share-archive',bundle=identity['bundle'],processId=identity['processId'],
        sourceInstance=identity['instance'],nativeClock=after['clockAfter'],archiveCodeVerified=True,
        extensionProcessQualificationRequired=True,shareOutcomeRequired=True,companionCleanupRequired=True,wholeFeatureRequired=True)
