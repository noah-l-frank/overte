"""Original retired Worlds authority, separate from all product outcomes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need,number
from adapters.script_feature.history import same
from feature_journeys.phase_fixture import validate as phase_packet
from feature_journeys.navigation_fixture import validate_status as navigation_packet
from feature_journeys.navigation_scene import validate_status as scene_packet
from ios.adapters.navigation_fixture import NavigationFixtureReader

VERSION=1


def validate(value,*,run,instance,inputs,ticket):
    exact(value,{'iosNavigationRunRetirementVersion','authorityBefore','navigation','scene','authorityAfter','acquisition'})
    need(type(value['iosNavigationRunRetirementVersion']) is int and value['iosNavigationRunRetirementVersion']==VERSION)
    first,last=value['authorityBefore'],value['authorityAfter'];clock=value['acquisition']
    exact(clock,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'})
    a,b=clock['hostBeforeEpochMs'],clock['hostAfterEpochMs'];c,d=clock['hostBeforeMonotonic'],clock['hostAfterMonotonic']
    need(number(a,1,1e15) and number(b,a,a+1500) and b-a<1500 and number(c,0,1e15) and number(d,c,c+1.5)
        and d-c<1.5 and abs(b-a-(d-c)*1000)<=250)
    for packet in (first,last):phase_packet(packet,run=run,area='world-navigation',request=packet['requestId'],epoch=b)
    phase_packet(last,run=run,area='world-navigation',request=last['requestId'],epoch=b,previous=first)
    navigation,scene=value['navigation'],value['scene']
    navigation_packet(navigation,instance=instance,run=run,inputs=inputs)
    scene_packet(scene,instance=instance,run=run,scene_url=inputs['sceneUrl'])
    need(first['active'] is False and last['active'] is False and navigation['active'] is False and scene['active'] is False
        and navigation['ticket'] is None and scene['ticket'] is None and same(first['activations'],last['activations'])
        and last['activations'] and last['activations'][-1]['ticket']==ticket
        and last['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
    # Provider clocks are original integer milliseconds; phase clocks retain
    # fractions. Preserve that quantization without retiming either original.
    need(a-1<=first['capturedEpochMs']<=last['capturedEpochMs']<=b+1
        and first['capturedEpochMs']-1<=navigation['capturedEpochMs']<=scene['capturedEpochMs']<=last['capturedEpochMs']+1)
    return value


class NavigationRunRetirement:
    def __init__(self,source,ticket):
        need(type(source) is NavigationFixtureReader);self.source,self.ticket=source,ticket

    def read(self):
        source=self.source;source.bound();need(source.instance is not None)
        epoch,started=source.clock(),source.monotonic()
        first=source.phase.status();navigation=source.status();scene=source.scene();last=source.phase.status(first)
        value=dict(iosNavigationRunRetirementVersion=VERSION,authorityBefore=first,navigation=navigation,scene=scene,authorityAfter=last,
            acquisition=dict(hostBeforeEpochMs=epoch,hostAfterEpochMs=source.clock(),hostBeforeMonotonic=started,hostAfterMonotonic=source.monotonic()))
        validate(value,run=source.run,instance=source.instance,inputs=source.inputs,ticket=self.ticket)
        return deepcopy(value)
