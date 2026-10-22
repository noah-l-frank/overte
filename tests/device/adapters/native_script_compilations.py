"""Original V8 compile-boundary records, including shared-manager includes.

These are compilation identities, not execution, caller or timer provenance.
No filename, requested script or expected digest supplies a measured record.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re

from adapters.native_feature_observation import exact,integer,need
from feature_journeys.contract import typed_equal

VERSION=1
EMPTY=hashlib.sha256(b'').hexdigest()


def compilation(row,epoch):
    exact(row,{'scriptId','resourceName','encoding','codeUnits','sha256','compiledEpochMs'})
    need(integer(epoch,1) and integer(row['scriptId'],1,2147483647)
        and type(row['resourceName']) is str and len(row['resourceName'])<=4096
        and not any(ord(c)<32 for c in row['resourceName'])
        and row['encoding']=='utf-16le-code-units' and integer(row['codeUnits'],0,4194304)
        and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']) is not None
        and (row['codeUnits']!=0 or row['sha256']==EMPTY) and integer(row['compiledEpochMs'],1,epoch))
    return row


def validate(value,epoch):
    need(type(value) is dict and type(value.get('complete')) is bool and integer(epoch,1))
    exact(value,{'compiledSourcesVersion','complete'}|({'compilations'} if value['complete'] else set()))
    need(type(value['compiledSourcesVersion']) is int and value['compiledSourcesVersion']==VERSION)
    if value['complete']:
        rows=value['compilations'];need(type(rows) is list and len(rows)<=256)
        previous=0
        for row in rows:
            compilation(row,epoch);need(row['scriptId']>previous);previous=row['scriptId']
    return value


def accept(previous,value,epoch):
    validate(value,epoch);need(value['complete'])
    if previous is not None:
        validate(previous,epoch);need(previous['complete'])
        current={row['scriptId']:row for row in value['compilations']}
        for row in previous['compilations']:
            need(row['scriptId'] in current and typed_equal(current[row['scriptId']],row))
    return deepcopy(value)
