"""Original retired fixture authority; no target facts or publication outcome."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_feature_observation import exact,need,number
from adapters.script_feature.history import same
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from feature_journeys.graphics_resources import validate_status
from ios.adapters.graphics_fixture import GraphicsFixtureReader

VERSION=1


def validate(value,*,run,url,instance):
    exact(value,{'iosGraphicsRunRetirementVersion','authorityBefore','provider','authorityAfter','acquisition'})
    need(type(value['iosGraphicsRunRetirementVersion']) is int and value['iosGraphicsRunRetirementVersion']==VERSION)
    first,last=value['authorityBefore'],value['authorityAfter'];provider=value['provider'];clock=value['acquisition']
    exact(clock,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'})
    a,b=clock['hostBeforeEpochMs'],clock['hostAfterEpochMs'];c,d=clock['hostBeforeMonotonic'],clock['hostAfterMonotonic']
    need(number(a,1,1e15) and number(b,a,a+1500) and b-a<1500 and number(c,0,1e15) and number(d,c,c+1.5)
         and d-c<1.5 and abs(b-a-(d-c)*1000)<=250)
    for packet in (first,last):phase_packet(packet,run=run,area='graphics',request=packet['requestId'],epoch=b)
    phase_packet(last,run=run,area='graphics',request=last['requestId'],epoch=b,previous=first)
    validate_status(provider,instance=instance,run=run,url=url,request=provider['requestId'])
    need(first['active'] is False and last['active'] is False and provider['active'] is False
         and a<=first['capturedEpochMs']<=provider['capturedEpochMs']<=last['capturedEpochMs']<=b
         and len(provider['activations'])==len(last['activations'])
         and all(same({k:row[k] for k in ('sequence','ticket')},{k:other[k] for k in ('sequence','ticket')})
                 for row,other in zip(provider['activations'],last['activations'])))
    return value


class IOSGraphicsRunRetirement:
    def __init__(self,source,*,monotonic=time.monotonic):
        need(isinstance(source,GraphicsFixtureReader) and callable(monotonic))
        self.source,self.monotonic=source,monotonic

    def read(self):
        source=self.source;epoch,started=source.clock(),self.monotonic()
        authority=PhaseFixtureReader(source.client,source.run,'graphics',epoch_ms=source.epoch_ms,monotonic=self.monotonic)
        first=authority.status();provider=source.status();last=authority.status(first)
        value=dict(iosGraphicsRunRetirementVersion=VERSION,authorityBefore=first,provider=provider,authorityAfter=last,
            acquisition=dict(hostBeforeEpochMs=epoch,hostAfterEpochMs=source.clock(),hostBeforeMonotonic=started,
                             hostAfterMonotonic=self.monotonic()))
        validate(value,run=source.run,url=source.client.url,instance=source.instance)
        return deepcopy(value)
