"""Independent primary-UI and remote-domain-original Create actor joins.

UI state does not replicate between apps. The actor reads the primary UI with
its own read-only channel, then independently reads another actual process for
the domain entities and renderer effects. No action ACK is a peer measurement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import uuid

from adapters.native_feature_observation import need
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from feature_journeys.contract import json_document
from ios.adapters import create_state
from ios.adapters.create_product_state import project, model_texture
from ios.adapters.emote_world import actual_domain

VERSION = 1


def near(a,b,tolerance=.0001):
    return len(a) == len(b) and all(abs(x-y) <= tolerance for x,y in zip(a,b))


def independent(primary,peer,primary_binding,peer_binding):
    context(primary_binding); context(peer_binding)
    a,b = create_state.live(primary),create_state.live(peer)
    need(primary['iosCreateStateVersion'] >= 2 and peer['iosCreateStateVersion'] >= 2
         and primary['runId'] == peer['runId'] and primary['processId'] == int(primary_binding['processIdentity'])
         and peer['processId'] == int(peer_binding['processIdentity']) and primary['instance'] != peer['instance']
         and primary_binding['targetFingerprint'] != peer_binding['targetFingerprint']
         and a['localSessionId'] != b['localSessionId'] and a['domainId'] == b['domainId']
         and a['domainId'] != '00000000-0000-0000-0000-000000000000')
    return a,b


def domains(primary,peer,primary_domain,peer_domain):
    """Fresh live real-domain/mixer originals joined on each device's clock."""
    observed=[]
    for state,packet in ((primary,primary_domain),(peer,peer_domain)):
        source=create_state.live(state);domain=actual_domain(packet)
        identity=hashlib.sha256(uuid.UUID(source['localSessionId']).bytes).hexdigest()
        need(packet['runId']==state['runId'] and packet['processId']==state['processId']
             and domain['domainId']==source['domainId'] and domain['selfSha256']==identity
             and abs(packet['clockAfter']['epochMs']-state['clockAfter']['epochMs'])<=1500
             and same(packet['source']['tree']['entities'],source['tree']['entities']))
        observed.append(domain)
    need(observed[0]['avatarMixerSha256']==observed[1]['avatarMixerSha256']
         and observed[0]['selfSha256']!=observed[1]['selfSha256'])
    return deepcopy(observed)


def replicated(primary,peer,owned_ids,primary_binding,peer_binding):
    a,b = independent(primary,peer,primary_binding,peer_binding)
    need(type(owned_ids) is list and len(set(owned_ids)) == len(owned_ids))
    actual = []
    for id_ in owned_ids:
        left = [row for row in a['entities'] if row['id'] == id_]; right = [row for row in b['entities'] if row['id'] == id_]
        need(bool(left) == bool(right))
        if not left: continue
        need(len(left) == len(right) == 1); left,right = left[0],right[0]
        need(left['hostType'] == right['hostType'] == 'domain' and left['lastEditedBy'] == right['lastEditedBy'] == a['localSessionId']
             and all(same(left[key],right[key]) for key in ('name','type','shape','modelURL','locked','visible'))
             and near(left['dimensions'],right['dimensions']) and near(left['position'],right['position'])
             and (near(left['rotation'],right['rotation']) or near(left['rotation'],[-v for v in right['rotation']])))
        if left['type'] == 'Model':
            need(all(row['model']['loaded'] and row['model']['addedToScene'] and not row['model']['failed'] for row in (left,right)))
            assignment = [json_document(row['textures']) if row['textures'] else {} for row in (left,right)]
            need(same(*assignment))
            if assignment[0]: need(model_texture(left) and model_texture(right))
        elif left['type'] == 'PolyVox':
            need(all(row['voxels']['ready'] for row in (left,right)) and all(same(left['voxels'][key],right['voxels'][key])
                 for key in ('sha256','bytes','volume','onCount')))
        actual.append(deepcopy(right))
    need((a['canRez'] or a['canRezTmp']) == (b['canRez'] or b['canRezTmp']))
    return actual


def project_actor(primary,peer,run,owned_ids,primary_binding,peer_binding,*,domain_originals,voxel_baseline=None):
    """World fields come from actual peer rows; UI fields from original primary UI."""
    need(type(domain_originals) in (tuple,list) and len(domain_originals)==2)
    domains(primary,peer,*domain_originals);replicated(primary,peer,owned_ids,primary_binding,peer_binding)
    # Validate the primary projection as a consistency assertion, never return
    # its world results as independent remote facts.
    local = project(primary,run,owned_ids,voxel_baseline=voxel_baseline)
    measured = project(peer,run,owned_ids,voxel_baseline=voxel_baseline)
    need(all(measured[key] == local[key] for key in ('objects','textured','voxelValue','canRez')))
    return dict(measured,**{key:local[key] for key in ('editor','picker','error','selection')})
