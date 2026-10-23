"""Original typed Snapshot capture settings; no replacement values or setters."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,integer,need
from adapters.pico4.snapshot_originals import nonce

VERSION=1
KEYS=('previousSnapshotDomainID','previousSnapshotHref','previousStillSnapPath')


def validate(value,epoch,*,minimum=1):
    exact(value,{'snapshotCaptureContextVersion','instance','capturedEpochMs','entries','normalizedHref'})
    need(type(value['snapshotCaptureContextVersion']) is int and value['snapshotCaptureContextVersion']==VERSION
        and nonce(value['instance']) and integer(value['capturedEpochMs'],minimum,epoch)
        and type(value['normalizedHref']) is str and len(value['normalizedHref'])<=4096 and '\0' not in value['normalizedHref'])
    exact(value['entries'],set(KEYS))
    for key in KEYS:
        row=value['entries'][key];exact(row,{'present','value'})
        need(type(row['present']) is bool and (type(row['value']) is str and len(row['value'])<=4096 and '\0' not in row['value'] if row['present'] else row['value'] is None))
    if not value['entries']['previousSnapshotHref']['present']:need(value['normalizedHref']=='')
    return value


def original(value,key):
    need(key in KEYS and value['entries'][key]['present']);return value['entries'][key]['value']
