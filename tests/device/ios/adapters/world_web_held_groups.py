"""Lossless labels for already decoded World Web native lifetime groups.

This is a private projection, not a native cleanup source. Every use must still
derive the member originals from the typed native/lease decoders. No counter,
birth, identity or unresolved lifetime is removed or declared retired here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from collections import defaultdict
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.terminal import bounded,held

VERSION=1
MAX_MEMBERS=32768
MEMBER='iosWorldWebHeldResourceVersion'
GROUP='iosWorldWebHeldResourceGroupVersion'


def visible(row):return {key:deepcopy(row[key]) for key in ('resource','kind','originalSha256')}


def member(row):
    exact(row,{'resource','kind','originalSha256','original'});held([visible(row)])
    need(row['resource'].startswith('panel:world-web-'))
    original=row['original'];exact(original,{MEMBER,'binding','runId','source','owner'})
    need(type(original[MEMBER]) is int and original[MEMBER]==1)
    context(original['binding']);identifier(original['runId'])
    need(type(original['source']) is str and 1<=len(original['source'])<=128
        and type(original['owner']) is dict and original['owner'])
    bounded(original);need(digest(original)==row['originalSha256'])
    return deepcopy(row)


def members(rows):
    need(type(rows) is list and len(rows)<=MAX_MEMBERS)
    values=[member(row) for row in rows];values.sort(key=lambda row:row['resource'])
    need(len({row['resource'] for row in values})==len(values))
    if values:
        first=values[0]['original']
        need(all(same(row['original']['binding'],first['binding']) and row['original']['runId']==first['runId'] for row in values))
    return values


def grouped(kind,values):
    need(values and all(row['kind']==kind for row in values));first=values[0]['original']
    original={GROUP:VERSION,'binding':deepcopy(first['binding']),'runId':first['runId'],
        'kind':kind,'members':deepcopy(values)}
    bounded(original)
    # The label binds the complete member set, including each full original's
    # native source instance, context/owner identity and measured counters.
    sha=digest(original)
    return dict(resource='panel:world-web-'+kind+'-group-'+sha[:20],kind=kind,originalSha256=sha,original=original)


def project(rows):
    values=members(rows)
    if len(values)<=64:return values
    kinds=defaultdict(list)
    for row in values:kinds[row['kind']].append(row)
    result=[grouped(kind,kinds[kind]) for kind in sorted(kinds)]
    result.sort(key=lambda row:row['resource']);held([visible(row) for row in result])
    return result


def expand(rows):
    need(type(rows) is list);held([visible(row) for row in rows]);values=[]
    for row in rows:
        original=row['original']
        if MEMBER in original:values.append(member(row));continue
        exact(row,{'resource','kind','originalSha256','original'})
        exact(original,{GROUP,'binding','runId','kind','members'})
        need(type(original[GROUP]) is int and original[GROUP]==VERSION and original['kind']==row['kind'])
        current=members(original['members']);need(current and same(row,grouped(row['kind'],current)))
        values.extend(current);need(len(values)<=MAX_MEMBERS)
    values=members(values)
    need(same(rows,project(values)))
    return values


def verify(projected,actual_members):
    """Join labels to the caller's separately decoded complete original set."""
    need(same(projected,project(actual_members)));return expand(projected)
