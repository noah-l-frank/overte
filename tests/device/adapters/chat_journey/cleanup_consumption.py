"""Strict warm join of shared consumed cleanup bytes to original Chat rows."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math

from adapters.chat_journey.cleanup_baseline import ChatCleanupBaseline
from adapters.native_feature_observation import exact,need
from adapters.script_journey.history import same,MAX_RAW
from feature_journeys.contract import json_document
from feature_journeys.engine import Journey
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION

VERSION=1


class ChatCleanupConsumption:
    """One callback, exact Journey, new original rows; no cursor translation.

    Attach this callback before execution, then begin after original cleanup
    sources are available. It never performs a second baseline to qualify the
    shared engine's receipt. Uncertain callbacks remain permanently retained.
    """
    def __init__(self,baseline):
        need(type(baseline) is ChatCleanupBaseline and not baseline.started and not baseline.failed
            and baseline.external_consumer is None)
        self.baseline=baseline;self.journey=None;self.started=self.issued=self.completed=self.failed=False
        self.raw=None;self.value=None;self.result=None;self.callback=self.consume
        baseline.external_consumer=self

    def attach(self,journey):
        need(self.journey is None and type(journey) is Journey and journey.area=='chat'
            and journey.run==self.baseline.scope['runId'] and journey.url==self.baseline.scope['fixtureUrl']
            and journey.after_cleanup_baseline is self.callback and not journey.cleanup_hook_started
            and journey.cleanup_consumption is None)
        self.journey=journey

    def begin(self):
        need(self.journey is not None and not self.started and not self.failed and not self.baseline.started
            and not self.baseline.primary.rows and not self.baseline.actor.rows)
        self.started=True;self.baseline.started=True;self.baseline.journey=self.journey
        try:self.baseline.save('external-observing',externalConsumptionVersion=VERSION)
        except Exception:self.quarantine();raise

    def quarantine(self):
        self.failed=self.baseline.failed=True
        for seal in self.baseline.seals:seal.failed=True

    def consume(self,raw):
        need(self.started and not self.issued and not self.failed);self.issued=True
        baseline=self.baseline;journey=self.journey
        try:
            need(type(raw) is bytes and 0<len(raw)<=MAX_RAW and journey.cleanup_hook_started
                and raw is journey.cleanup_consumption and not baseline.completed)
            value=json_document(raw)
            exact(value,{'cleanupConsumptionVersion','contractVersion','area','runId','fixtureUrl','ticket',
                'actionBarrierEpochMs','sequenceSucceeded','phase','samples','finalSequence'})
            need(type(value['cleanupConsumptionVersion']) is int and value['cleanupConsumptionVersion']==VERSION
                and type(value['contractVersion']) is int and value['contractVersion']==CONTRACT_VERSION
                and value['area']=='chat' and value['runId']==baseline.scope['runId']
                and value['fixtureUrl']==baseline.scope['fixtureUrl'] and type(value['sequenceSucceeded']) is bool
                and type(value['samples']) is list and value['samples']
                and same(value['phase'],journey.phases[-1]) and value['phase']['phase']=='cleanup-restored-baseline'
                and value['phase']['stableSeconds']>=3 and same(value['samples'],journey.samples[-len(value['samples']):])
                and type(value['finalSequence']) is int and value['finalSequence']==journey.sequence
                and value['finalSequence']==len(baseline.primary.rows)==len(baseline.actor.rows)==len(value['samples']))
            # Do not manufacture a global external cursor from the private
            # phase count or accept a caller offset. Each original primary
            # and independent actor row is matched without sequence rewriting.
            for index,(sample,source,published) in enumerate(zip(value['samples'],baseline.primary.rows,baseline.actor.rows)):
                need(sample['sequence']==source['sequence']==index+1
                    and sample['phase']=='cleanup-restored-baseline' and sample['ticket']==value['ticket']
                    and sample['actionBarrierEpochMs']==value['actionBarrierEpochMs']
                    and sample['witness'] is not None
                    and all(same(sample[key],source['sample'][key]) for key in
                        ('capturedEpochMs','state','resources','lifecycle'))
                    and all(same(sample['witness'][key],field) for key,field in published['payload'].items()))
            with baseline.held(baseline.primary):
                _authority,phase=baseline.primary.current();activation=phase['activations'][-1]
                need(value['ticket']==activation['ticket'] and activation['stimulus']==dict(verb='cleanup',inputs={})
                    and value['actionBarrierEpochMs']>=math.ceil(activation['activatedEpochMs']))
            self.raw=raw;self.value=deepcopy(value)
            header={key:deepcopy(field) for key,field in value.items() if key!='samples'}
            baseline.fresh_pair()
            baseline.save('externally-consumed',externalConsumption=dict(header=header,sha256=hashlib.sha256(raw).hexdigest()))
            self.result=deepcopy(baseline.complete(value['samples'],value['phase']))
            baseline.receipt(self.result);baseline.fresh_pair();self.completed=True
        except Exception:self.quarantine();raise

    def receipt(self):
        need(self.completed and not self.failed and self.raw is self.journey.cleanup_consumption
            and self.journey.cleanup_hook_started and same(self.result,self.baseline.previous))
        value=self.baseline.receipt(self.result);extension=value['externalConsumption']
        reconstructed={**extension['header'],'samples':[deepcopy(row['common']) for row in self.baseline.rows]}
        raw=json.dumps(reconstructed,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
        need(raw==self.raw and extension['sha256']==hashlib.sha256(raw).hexdigest())
        return value
