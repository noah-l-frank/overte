"""Pre-stop callback quiet retains every actual cached image/resource holder.

This is not resource retirement. The whole owner must separately join actual
Entity/renderer lease retirement, revoked views, restored pixels, native quiet
and the original post-stop OS proof. No pending resource is rewritten to zero.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from ios.adapters.web_closures import (validate,continuity,drained,RESOURCES,
    SOFTWARE_RESOURCES,GPU_RESOURCES)
from adapters.normal_ui import NativeUIError


class ResourceAdmissionPending(NativeUIError):
    """Valid originals have not observed the complete actual rendered path."""


def resource_admission(value,entity,source_url):
    validate(value,dict(schemaVersion=1,commandId=value.get('commandId'),action='feature-ios-web-closures',
        runId=value.get('runId'),fixtureUrl=value.get('fixtureUrl')),value.get('processId'),value.get('capturedEpochMs'))
    need(value['iosWebClosureVersion']==5 and value['complete'])
    identity=hashlib.sha256(('web-entity:'+entity).encode()).hexdigest()
    contexts=[row for row in value['contexts'] if row['descriptor']['surface']=='world-entity'
        and row['descriptor']['identitySha256']==identity and row['descriptor']['sourceUrl']==source_url]
    required=RESOURCES|SOFTWARE_RESOURCES|GPU_RESOURCES|{'native-delegate','native-snapshot-object'}
    if not contexts or not any(row['callbacks']['snapshot']['created']>0 for row in contexts) or not all(
            any(row['resources'][kind]['created']>0 for row in contexts) for kind in required):
        raise ResourceAdmissionPending('Actual World Web rendered resource admission is incomplete')
    return dict(iosWorldWebResourceAdmissionVersion=1,instance=value['instance'],processId=value['processId'],runId=value['runId'],
        contexts=[row['id'] for row in contexts],capturedEpochMs=value['capturedEpochMs'])


def disposition(value,admitted,*,partial=False):
    need(type(partial) is bool)
    for packet in (admitted,value):
        validate(packet,dict(schemaVersion=1,commandId=packet.get('commandId'),action='feature-ios-web-closures',
            runId=packet.get('runId'),fixtureUrl=packet.get('fixtureUrl')),packet.get('processId'),packet.get('capturedEpochMs'))
        need(packet['iosWebClosureVersion']==5 and packet['complete'])
    continuity(admitted,value,admitted['processId'])
    if not partial:
        drained(value,admitted)
        required=RESOURCES|SOFTWARE_RESOURCES|GPU_RESOURCES|{'native-delegate','native-snapshot-object'}
        need(all(any(row['resources'][kind]['created']>0 for row in admitted['contexts']) for kind in required))
    # Product grants must actually retire, and every original callback body
    # must return. An ACK or view teardown cannot substitute for either.
    need(all(counter['pending']==0 for row in value['contexts'] for counter in row['callbacks'].values())
        and all(row['resources']['policy-grant']['pending']==0 for row in value['contexts']))
    contexts=deepcopy(value['contexts'])
    held=any(counter['pending'] for row in contexts for counter in row['resources'].values())
    return dict(iosWorldWebResourceDispositionVersion=1,mode='held' if held else 'released',
        source=dict(instance=value['instance'],sequence=value['sequence'],processId=value['processId'],
            capturedEpochMs=value['capturedEpochMs'],sha256=digest(value)),contexts=contexts)


def unchanged(first,last):
    """Pure activity equality only; earns no duration or process-death credit."""
    continuity(first,last,first['processId'])
    need(first['contexts']==last['contexts'])
    return True
