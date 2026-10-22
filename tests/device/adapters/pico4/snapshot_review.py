"""Actual original Snapshot Review properties, including a hidden owned page.

Observed absence within a valid live root does not prove Qt object retirement.
This source has no handler, setter, input or export authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from urllib.parse import unquote,urlsplit
from adapters.native_feature_observation import exact,integer,need

VERSION=1
BOOLS={'visible','capturing','processing','loggedIn','canShare','canBlast','statusError','captureSettingsLoaded','exportBusy'}
STRINGS={'statusText':2048,'uploadPath':2048,'exportTicket':2048,'format':16,'exportError':256}


def text(value,limit):return type(value) is str and len(value)<=limit and '\0' not in value


def validate(value):
    exact(value,{'snapshotReviewObservationVersion','present','review'})
    need(type(value['snapshotReviewObservationVersion']) is int and value['snapshotReviewObservationVersion']==VERSION
        and type(value['present']) is bool)
    if not value['present']:
        need(value['review'] is None);return value
    row=value['review'];exact(row,BOOLS|set(STRINGS)|{'componentUrl','mode','capabilities','images'})
    need(all(type(row[key]) is bool for key in BOOLS) and all(text(row[key],limit) for key,limit in STRINGS.items())
        and integer(row['mode'],0,3) and text(row['componentUrl'],4096))
    url=urlsplit(row['componentUrl'])
    need(url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment
        and unquote(url.path).endswith('/system/snapshot/NativeSnapshotReview.qml')
        and not any(part in ('.','..') for part in unquote(url.path).split('/')))
    need(type(row['capabilities']) is list and len(row['capabilities'])<=32
        and all(text(item,64) and item for item in row['capabilities'])
        and len(set(row['capabilities']))==len(row['capabilities'])
        and type(row['images']) is list and len(row['images'])<=8)
    paths=[]
    for image in row['images']:
        exact(image,{'path','storyPresent'})
        need(text(image['path'],2048) and image['path'] and type(image['storyPresent']) is bool)
        paths.append(image['path'])
    need(len(set(paths))==len(paths))
    return value
