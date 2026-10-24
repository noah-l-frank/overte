"""Closed normal HTTP base-scene admission for the reused Phone foundations.

No input ACK proves scene success. The ordinary modules independently observe
actual scene URL, native readiness, domain departure and unchanged process.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.phone_navigation import validate_profile
from feature_journeys.navigation_fixture import configuration as provider_inputs
from feature_journeys.contract import identifier
from navigation_observation import owned_scene


def configuration(profile,url,environment_url):
    validate_profile(profile);owned_scene(url)
    need(url==profile['sceneUrl']==environment_url)
    return profile


def provider(value,url,revision,epoch):
    exact(value,{'navigationProviderVersion','instance','inputs','capturedEpochMs','ready','activeRuns','failedResponses','internalErrors'})
    need(type(value['navigationProviderVersion']) is int and value['navigationProviderVersion']==1 and value['ready'] is True
        and integer(value['activeRuns'],0,1) and type(value['failedResponses']) is int and value['failedResponses']==0
        and type(value['internalErrors']) is int and value['internalErrors']==0)
    identifier(value['instance']);inputs,_=provider_inputs(value['inputs']);fresh(value['capturedEpochMs'],epoch)
    need(inputs['sceneUrl']==url and inputs['sourceRevision']==revision)
    return value
