"""Pure original stereo Graphics facts; live owners must prove currentness."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from adapters.native_feature_observation import integer,need
from adapters.normal_feature_state import context
from adapters.pico4.graphics_source import resources as graphics_resources
from adapters.script_journey.files import validate as tablet_packet
from adapters.script_ui_inventory import validate as tablet_inventory
from adapters.world_render_evidence import measured_scale
from feature_journeys.stereo_graphics_evidence import analyse,policy,SURFACE_PROFILE

VERSION=2
FACTS={'ticket','afterEpochMs','nativeBefore','subjectBefore','graphics','tablet','capture','subjectAfter','nativeAfter','provider'}
FRAME=FACTS|{'image','metadata','retirement'}
SURFACE_FACTS=FACTS|{'graphicsAfter'}
SURFACE_FRAME=FRAME|{'graphicsAfter'}


def frame_fields(frame):return SURFACE_FRAME if 'graphicsAfter' in frame else FRAME


def native_metadata(frame,binding,run,role,stage,fixture_url):
    need(type(frame) is dict and set(frame) in (FACTS,FRAME,SURFACE_FACTS,SURFACE_FRAME));context(binding)
    version=2 if 'graphicsAfter' in frame else 1
    policy_value=dict(stereoGraphicsEvidenceVersion=version,runId=run,ticket=frame['ticket'],sceneTicket=frame['provider']['sceneTicket'],
        fixtureUrl=fixture_url,binding=deepcopy(binding),role=role,stage=stage)
    for field in ('nativeBefore','nativeAfter','subjectBefore','subjectAfter','graphics','capture','provider'):
        policy_value[field]=deepcopy(frame[field])
    if version==2:policy_value['graphicsAfter']=deepcopy(frame['graphicsAfter'])
    return policy_value


def metadata_bytes(frame,binding,run,role,stage,fixture_url):
    return json.dumps(native_metadata(frame,binding,run,role,stage,fixture_url),sort_keys=True,separators=(',',':')).encode()


def compose(run,frame,raw,binding,role,stage,fixture_url,image_policy):
    """Historical originals only, without a caller-supplied current clock.

    This is also used during live acquisition, before the owner separately
    checks its actual final clock, guard and original elapsed acquisition age.
    """
    policy(image_policy);need(type(frame) is dict and set(frame) in (FACTS,FRAME,SURFACE_FACTS,SURFACE_FRAME)
        and ('graphicsAfter' in frame)==(image_policy==SURFACE_PROFILE)
        and integer(frame['afterEpochMs'],1))
    metadata=metadata_bytes(frame,binding,run,role,stage,fixture_url)
    value=analyse(raw,metadata,run,frame['ticket'],fixture_url,role=role)
    tablet=frame['tablet'];pid=int(binding['processIdentity'].split(':')[0]);epoch=value['latestEpochMs']
    tablet_packet(tablet,tablet.get('commandId'),pid,epoch)
    inventory=tablet_inventory(tablet.get('scriptInventory'))
    need(inventory['complete'] and not inventory['managers'] and not inventory['pickers']
        and inventory['tabletShown']==frame['graphics']['tabletShown']
        and frame['graphics']['capturedEpochMs']<=tablet['capturedEpochMs']<=frame['capture']['requestedEpochMs']
        and value['earliestEpochMs']>=frame['afterEpochMs'])
    # The original tablet acquisition is bracketed by the already checked
    # native interval; it does not receive a synthetic archive timestamp.
    image=deepcopy(value['pixels']);image['metadataSha256']=hashlib.sha256(metadata).hexdigest()
    return deepcopy(dict(state=value['state'],capturedEpochMs=value['earliestEpochMs'],lifecycle=value['lifecycle'],
        resources=graphics_resources(frame['graphics']),image=image,trace=frame['capture']['source']['renderTrace'],
        scale=measured_scale(frame['capture'])))
