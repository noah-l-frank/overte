"""Actual Tablet facts plus original UIKit screen bytes from the same page.

The immutable sample retains both independent native source acquisitions. This
wrapper adds no capture clock: the public acquisition starts at the earliest
actual readiness/source original and ends at the last actual source original.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from feature_journeys.contract import result
from ios.adapters.tablet_web_sample_root import samples_owner

VERSION=1


def validate(runtime,original):
    exact(original,{'tabletWebImageObservationVersion','observation','sample','artifactRoot','policy'})
    need(type(original['tabletWebImageObservationVersion']) is int and original['tabletWebImageObservationVersion']==VERSION)
    root=Path(original['artifactRoot']);need(root.is_absolute() and root.resolve()==root)
    source=runtime.observer.source;configured=PrivateFeatureState(source.root/('tabletweb-feature-'+source.run+'-'+source.role+'.json')).read()
    need(type(configured) is dict and type(configured.get('tabletWebFeatureVersion')) is int and configured['tabletWebFeatureVersion']==1
        and same(configured.get('binding'),source.binding) and configured.get('runId')==source.run and configured.get('role')==source.role
        and same(configured.get('screen'),dict(artifactRoot=str(root),policy=original['policy'])))
    with runtime.image_observation_context(original['observation'],root) as (observed,tail):
        samples=samples_owner(runtime,root,original['policy'],historical=True,tail_validator=tail)
        value=samples.read(original['sample']);row=value['row']
        need(same(original['observation']['observation'],row['after']['observation']) and observed['ticket']==row['ticket'])
        first=tail(row['before'])['row']['clockJoin'];last=observed['acquisition'];clock=deepcopy(last)
        clock['hostBeforeEpochMs']=min(last['hostBeforeEpochMs'],first['hostBeforeEpochMs'])
        clock['hostBeforeMonotonic']=min(last['hostBeforeMonotonic'],first['hostBeforeMonotonic'])
        duration=(clock['hostAfterMonotonic']-clock['hostBeforeMonotonic'])*1000
        need(number(duration,0,1500) and duration<1500
            and 0<=clock['hostAfterEpochMs']-clock['hostBeforeEpochMs']<1500
            and abs(clock['hostAfterEpochMs']-clock['hostBeforeEpochMs']-duration)<=250)
        public=deepcopy(observed['public']);public['capturedEpochMs']=clock['hostBeforeEpochMs']
        public['artifacts']=[samples.artifact(original['sample'],public['sequence'])]
        result('feature.tablet-web.observe',public)
        return dict(ticket=observed['ticket'],public=public,acquisition=clock)
