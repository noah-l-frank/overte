"""Closed retired HTTP audit; no native freshness or quiet outcome is derived."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from adapters.native_feature_observation import exact,integer,need
from feature_journeys.browser_retirement import RESOURCE_NAMES,MAX_ATTEMPTS


def original(value,previous=None,*,after_epoch=0):
    exact(value,{'browserRetirementVersion','runId','complete','closedEpochMs','attempts'})
    need(type(value['browserRetirementVersion']) is int and value['browserRetirementVersion']==1
        and type(value['runId']) is str and re.fullmatch('[0-9a-f]{32}',value['runId'])
        and value['complete'] is True and integer(value['closedEpochMs'],max(1,after_epoch),2**53-1) and type(value['attempts']) is list and len(value['attempts'])<=MAX_ATTEMPTS)
    previous_entry=value['closedEpochMs']
    for index,row in enumerate(value['attempts'],1):
        exact(row,{'sequence','ticket','resource','origin','method','enteredEpochMs','headers','write','finallyEpochMs'})
        need(type(row['sequence']) is int and row['sequence']==index and type(row['ticket']) is str and re.fullmatch('[0-9a-f]{32}',row['ticket'])
            and row['resource'] in RESOURCE_NAMES and row['origin'] in ('primary','foreign')
            and type(row['method']) is str and re.fullmatch('[A-Z]{1,16}',row['method'])
            and integer(row['enteredEpochMs'],max(1,previous_entry),2**53-1));previous_entry=row['enteredEpochMs']
        floor=row['enteredEpochMs']
        if row['headers'] is not None:
            header=row['headers'];exact(header,{'status','bytes','sha256','observedEpochMs'})
            need(integer(header['status'],400,599) and integer(header['bytes'],0,1048576)
                and type(header['sha256']) is str and re.fullmatch('[0-9a-f]{64}',header['sha256'])
                and integer(header['observedEpochMs'],floor,2**53-1));floor=header['observedEpochMs']
        if row['write'] is not None:
            written=row['write'];exact(written,{'bytes','observedEpochMs'})
            need(row['headers'] is not None and type(written['bytes']) is int and written['bytes']==row['headers']['bytes']
                and integer(written['observedEpochMs'],floor,2**53-1));floor=written['observedEpochMs']
        if row['finallyEpochMs'] is not None:need(integer(row['finallyEpochMs'],floor,2**53-1))
    if previous is not None:
        original(previous);need(value['runId']==previous['runId'] and value['closedEpochMs']==previous['closedEpochMs'] and len(value['attempts'])>=len(previous['attempts']))
        for old,new in zip(previous['attempts'],value['attempts']):
            need(all(new[key]==old[key] for key in old if key not in ('headers','write','finallyEpochMs')))
            for key in ('headers','write','finallyEpochMs'):
                if old[key] is not None:need(new[key]==old[key])
    return value
