"""Original controlled delayed-grant facts; no credentials or product verdicts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import need,exact,integer

VERSION=2
HEX='[0-9a-f]{32}'
FIELDS={'providerVersion','instance','runId','capturedEpochMs','eventSequence','grantsEnabled','requests','delayedGrantOutstanding'}
ROW={'requestId','requestTicket','startedEpochMs','releasedEpochMs','issuedEpochMs','status','state','accessValid','refreshValid'}


def validate(value,run):
    exact(value,FIELDS)
    need(type(run) is str and re.fullmatch(HEX,run) and value['runId']==run
         and type(value['providerVersion']) is int and value['providerVersion']==VERSION
         and type(value['instance']) is str and re.fullmatch(HEX,value['instance'])
         and integer(value['capturedEpochMs'],1) and integer(value['eventSequence'])
         and type(value['grantsEnabled']) is bool and type(value['delayedGrantOutstanding']) is bool
         and type(value['requests']) is list and len(value['requests'])<=64)
    seen=set()
    for row in value['requests']:
        exact(row,ROW)
        need(all(type(row[k]) is str and re.fullmatch(HEX,row[k]) for k in ('requestId','requestTicket'))
             and row['requestId'] not in seen and integer(row['startedEpochMs'],1)
             and all(integer(row[k]) for k in ('releasedEpochMs','issuedEpochMs','status'))
             and 0<row['startedEpochMs']<=value['capturedEpochMs']
             and all(row[k]==0 or row['startedEpochMs']<=row[k]<=value['capturedEpochMs'] for k in ('releasedEpochMs','issuedEpochMs'))
             and all(type(row[k]) is bool for k in ('accessValid','refreshValid'))
             and type(row['state']) is str and row['state'] in ('held','issued','expired','cancelled','rejected'))
        seen.add(row['requestId'])
        if row['state']=='issued':
            need(row['status']==200 and row['startedEpochMs']<=row['releasedEpochMs']<=row['issuedEpochMs'] and row['releasedEpochMs']>0)
        else:
            need(not row['accessValid'] and not row['refreshValid'] and row['issuedEpochMs']==0
                 and row['status']==(0 if row['state']=='held' else 503))
    need(value['delayedGrantOutstanding']==any(r['accessValid'] or r['refreshValid'] for r in value['requests']))
    return value


class DelayedGrantObservation:
    def __init__(self,run,provider_instance=None):
        need(type(run) is str and re.fullmatch(HEX,run)
             and (provider_instance is None or type(provider_instance) is str and re.fullmatch(HEX,provider_instance)))
        self.run,self.instance=run,provider_instance;self.previous=None

    def accept(self,value):
        validate(value,self.run);need(self.instance in (None,value['instance']))
        if self.previous is not None:
            old=self.previous
            need(value['capturedEpochMs']>=old['capturedEpochMs'] and value['eventSequence']>=old['eventSequence']
                 and (old['grantsEnabled'] or not value['grantsEnabled']))
            current={r['requestId']:r for r in value['requests']}
            for row in old['requests']:
                need(row['requestId'] in current);new=current[row['requestId']]
                need(all(new[k]==row[k] for k in ('requestId','requestTicket','startedEpochMs')))
                for key in ('releasedEpochMs','issuedEpochMs','status'):
                    if row[key]:need(new[key]==row[key])
                if row['state']!='held':need(new['state']==row['state'])
                # Issued authority cannot reappear after expiry/revocation.
                if row['state']=='issued':
                    need(all(row[key] or not new[key] for key in ('accessValid','refreshValid')))
        self.instance=value['instance'];self.previous=deepcopy(value)
        return value['delayedGrantOutstanding'] # Actual current retained authority, not requested login state.
