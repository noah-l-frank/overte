"""Original standalone companion identity and independent native clock codecs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,integer,need
from ios.adapters.bundle_identity import compare
from ios.adapters.snapshot_destination import stamp
from adapters.script_feature.history import same
import re

BASE={'snapshotCompanionObservationVersion','action','nonce','role','instance','processId','bundleId','sequence','sourceBirthClock','clockBefore','clockAfter','status'}


def original(value,*,action=None,nonce=None,pid=None,bundle=None,previous=None):
    need(type(value) is dict and value.get('action') in ('identity','clock'))
    kind=value['action'];exact(value,BASE|({'preparedClock','bundle'} if kind=='identity' else set()))
    need(type(value['snapshotCompanionObservationVersion']) is int and value['snapshotCompanionObservationVersion']==1
        and value['role']=='photos' and (action is None or kind==action)
        and type(value['nonce']) is str and re.fullmatch('ios-[0-9a-f]{32}',value['nonce']) and (nonce is None or value['nonce']==nonce)
        and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
        and integer(value['processId'],1,2147483647) and (pid is None or value['processId']==pid)
        and type(value['bundleId']) is str and re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+',value['bundleId'])
        and (bundle is None or value['bundleId']==bundle) and integer(value['sequence'],1)
        and value['status'] in ('pending','ready','unavailable') and (kind=='identity' or value['status']!='pending'))
    stamp(value['sourceBirthClock']);stamp(value['clockBefore'],value['sourceBirthClock']);stamp(value['clockAfter'],value['clockBefore'])
    need(value['clockAfter']['epochMs']-value['clockBefore']['epochMs']<1500
        and value['clockAfter']['monotonicMs']-value['clockBefore']['monotonicMs']<1500)
    if kind=='identity':
        if value['status']=='ready':
            compare(value['bundle'],value['bundle']);need(value['bundle']['bundleId']==value['bundleId'])
            stamp(value['preparedClock'],value['sourceBirthClock']);stamp(value['clockBefore'],value['preparedClock'])
        else:need(value['preparedClock'] is None and type(value['bundle']) is dict and not value['bundle'])
    if previous is not None:
        original(previous);need(all(same(previous[key],value[key]) for key in ('instance','processId','bundleId','sourceBirthClock','role'))
            and value['sequence']>previous['sequence'] and value['nonce']!=previous['nonce'])
        stamp(value['clockBefore'],previous['clockAfter'])
    return value


def admission(identity,before,after,expected):
    original(before,action='clock');original(identity,action='identity',previous=before);original(after,action='clock',previous=identity)
    need(before['status']==identity['status']==after['status']=='ready');compare(identity['bundle'],expected)
    need(after['clockAfter']['epochMs']-before['clockBefore']['epochMs']<1500
        and after['clockAfter']['monotonicMs']-before['clockBefore']['monotonicMs']<1500)
    return dict(snapshotCompanionCodeAdmissionVersion=1,role='photos',bundle=identity['bundle'],processId=identity['processId'],
        sourceInstance=identity['instance'],nativeClock=after['clockAfter'],companionCodeVerified=True,
        photosOutcomeRequired=True,companionCleanupRequired=True,wholeFeatureRequired=True)
