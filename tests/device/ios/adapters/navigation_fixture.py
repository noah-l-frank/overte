"""Read-only original navigation inputs and phase-consistent source attachment.

These are fixture metadata/HTTP inputs, never product, renderer or peer facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import time

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import identifier
from feature_journeys.navigation_fixture import configuration,validate_status
from feature_journeys.navigation_scene import validate_status as scene_status
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client

VERSION=1
LIMIT=262144


class NavigationPhasePending(NativeUIError):
    """The input phase crossed a read; this never authorizes resending input."""


class NavigationRunRetired(NavigationPhasePending):
    def __init__(self,status):
        super().__init__('The original owned navigation fixture run has retired')
        self.status=deepcopy(status)


class NavigationFixtureReader:
    def __init__(self,client,run,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic):
        identifier(run);need(isinstance(client,Client) and callable(epoch_ms) and callable(monotonic))
        self.client,self.run,self.base=client,run,client.url
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        self.instance=self.inputs=self.navigation_previous=self.scene_previous=None
        self.last_epoch=None;self.last=None;self.fixture_url=self.base+'/runs/'+run+'/'
        self.phase=PhaseFixtureReader(client,run,'world-navigation',epoch_ms=epoch_ms,monotonic=monotonic)
        self.bound()

    def bound(self):
        need(self.client.url==self.base and getattr(self.client,'run',None) in (None,self.run)
             and getattr(self.client,'area',None) in (None,'world-navigation') and type(getattr(self.client,'closed',False)) is bool)

    def clock(self):
        now=self.epoch_ms();need(integer(now,1) and (self.last_epoch is None or now>=self.last_epoch));self.last_epoch=now;return now

    def attach(self):
        self.bound();value=self.client.request('/navigation-provider')
        exact(value,{'navigationProviderVersion','instance','inputs','capturedEpochMs','ready','activeRuns','failedResponses','internalErrors'})
        need(type(value['navigationProviderVersion']) is int and value['navigationProviderVersion']==1
             and value['ready'] is True and integer(value['activeRuns'],0,1)
             and type(value['failedResponses']) is int and value['failedResponses']==0
             and type(value['internalErrors']) is int and value['internalErrors']==0)
        instance=identifier(value['instance']);inputs,_=configuration(value['inputs'])
        need(self.instance in (None,instance) and self.inputs in (None,inputs));fresh(value['capturedEpochMs'],self.clock())
        self.bound();self.instance,self.inputs=instance,deepcopy(inputs);return deepcopy(value)

    def status(self):
        self.bound();need(self.instance is not None)
        value=self.client.request('/runs/'+self.run+'/navigation')
        validate_status(value,instance=self.instance,run=self.run,inputs=self.inputs,previous=self.navigation_previous)
        fresh(value['capturedEpochMs'],self.clock());need(not getattr(self.client,'closed',False) or not value['active'])
        self.bound();self.navigation_previous=deepcopy(value);return deepcopy(value)

    def scene(self):
        self.bound();need(self.instance is not None)
        value=self.client.request('/runs/'+self.run+'/navigation-scene')
        scene_status(value,instance=self.instance,run=self.run,scene_url=self.inputs['sceneUrl'],previous=self.scene_previous)
        fresh(value['capturedEpochMs'],self.clock());need(not getattr(self.client,'closed',False) or not value['active'])
        self.bound();self.scene_previous=deepcopy(value);return deepcopy(value)

    def read(self):
        self.bound();need(self.instance is not None);started=self.monotonic();need(number(started,0,1e15))
        first=self.phase.status()
        if not first['active']:raise NavigationRunRetired(first)
        if not first['activations']:raise NavigationPhasePending('The original navigation run has no active input ticket')
        navigation=self.status();scene=self.scene();last=self.phase.status()
        if not last['active']:raise NavigationRunRetired(last)
        ended=self.monotonic();need(number(ended,started,started+1.5) and ended-started<1.5);self.bound()
        current=last['activations'][-1]
        if (first['activations']!=last['activations'] or not navigation['active'] or not scene['active']
                or len({current['ticket'],navigation['ticket'],scene['ticket']})!=1):
            raise NavigationPhasePending('The original navigation phase changed during its read')
        # Phase clocks retain sub-millisecond floats; provider clocks retain
        # original integer milliseconds. Preserve both, allowing only that
        # original quantization at the bracket boundaries.
        need(first['capturedEpochMs']-1<=navigation['capturedEpochMs']<=scene['capturedEpochMs']<=last['capturedEpochMs']+1)
        originals=dict(phaseBefore=first,navigation=navigation,scene=scene,phaseAfter=last)
        result=dict(navigationFixtureReaderVersion=VERSION,runId=self.run,ticket=current['ticket'],
            verb=current['stimulus']['verb'],inputs=deepcopy(current['stimulus']['inputs']),
            providerReadEpochMs=last['capturedEpochMs'],hostBeforeMonotonic=started,hostAfterMonotonic=ended,
            originals=originals,originalsSha256=digest(originals))
        need(len(json.dumps(result,allow_nan=False,ensure_ascii=False).encode())<=LIMIT)
        self.last=deepcopy(result);return deepcopy(result)
