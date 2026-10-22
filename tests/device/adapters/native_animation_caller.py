"""Original VM-to-native animation call identity; no requested cause or subject."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,integer,need
from adapters.native_script_membership import validate as membership
from adapters.native_script_observation import validate_code
from feature_journeys.contract import typed_equal

VERSION=1


def validate(value,kind,epoch):
    # Native callers outside an actual Script method invocation remain explicit
    # null. Generic history can retain them; an Emote effect may not adopt them.
    need(kind in ('override','restore') and integer(epoch,1))
    if value is None:return None
    exact(value,{'callerVersion','method','sequence','invokedEpochMs','manager','code'})
    need(type(value['callerVersion']) is int and value['callerVersion']==VERSION
        and value['method']==('overrideAnimation' if kind=='override' else 'restoreAnimation')
        and integer(value['sequence'],1,1_000_000_000) and integer(value['invokedEpochMs'],1,epoch))
    membership(dict(complete=True,revision=1,managers=[value['manager']]),value['invokedEpochMs'])
    validate_code(value['code'],value['invokedEpochMs'])
    need(value['manager']['assigned'] and value['code']['submitted']
        and value['manager']['assignedEpochMs']<=value['code']['submittedEpochMs'])
    return value


def selected(event,profile,*,after_epoch=0):
    """Join the actual native caller to independently acquired source facts."""
    need(type(event) is dict and 'caller' in event and integer(after_epoch))
    caller=validate(event['caller'],event['kind'],event['capturedEpochMs']);need(caller is not None)
    manager=caller['manager']
    need(manager['instance']==profile['engineInstance'] and manager['url']==profile['assignedUrl']
        and manager['loadGeneration']==profile['loadGeneration'] and manager['assignedEpochMs']==profile['assignedEpochMs']
        and typed_equal(caller['code'],profile['code']) and caller['invokedEpochMs']>=after_epoch)
    return caller
