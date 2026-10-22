"""Actual marker Script execution, entity identity and restoration originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib

from adapters.native_feature_observation import exact,need
from adapters.native_script_observation import validate as scripts_packet,running_owned_engine,loaded_relative_modules
from adapters.native_script_terminal import terminal
from adapters.script_feature.history import same
from ios.adapters import create_state
from ios.adapters.create_actions import semantic_map
from ios.adapters.create_marker_files import originals
from ios.adapters.create_marker_identity import marker
from ios.adapters.emote_world import original as domain_original, actual_domain

VERSION = 1


def body_preserved(before,after):
    """Passive actual body/domain/view preservation; marker code sets none."""
    domain_original(before);domain_original(after)
    need(before['runId']==after['runId'] and before['instance']==after['instance'] and before['processId']==after['processId']
         and same(actual_domain(before),actual_domain(after)))
    a,b=before['source'],after['source']
    for field in ('feetPosition','velocity','orientation'):
        left,right=a['avatar'][field],b['avatar'][field]
        need(all(abs(x-y)<.001 for x,y in zip(left,right)) or field=='orientation' and all(abs(x+y)<.0001 for x,y in zip(left,right)))
    need(all(a['avatar'][field]==b['avatar'][field] for field in ('inAir','flying','modelScale'))
         and not b['avatar']['inAir'] and not b['avatar']['flying'])
    for field in ('position','rotation'):
        need(all(abs(x-y)<.001 for x,y in zip(a['view'][field],b['view'][field])))
    need(all(a['view'][field]==b['view'][field] for field in ('mode','perspective','fieldOfViewDegrees','aspectRatio'))
         and same(a['cameraOrbit'],b['cameraOrbit']))
    return True


def view_preserved(before,after):
    a,b = create_state.live(before),create_state.live(after)
    need(a['domainId'] == b['domainId'] and a['localSessionId'] == b['localSessionId']
         and before['runId'] == after['runId'] and before['instance'] == after['instance'] and before['processId'] == after['processId'])
    left,right = a['view'],b['view']
    for key in ('position','rotation'):
        need(len(left[key]) == len(right[key]) and all(abs(x-y) < .0001 for x,y in zip(left[key],right[key])))
    need(all(left[key] == right[key] for key in ('perspective','fieldOfViewDegrees','aspectRatio','uiWidth','uiHeight')))


def admitted(before,after,scripts,files,directory,*,after_epoch):
    view_preserved(before,after); run = before['runId']; need(files['runId'] == run)
    url = files['fixtureUrl']+'tickets/'+files['ticket']+'/graphics-marker.v1.html'; actual = marker(after,files['nonce'],url)
    first,last = create_state.live(before),create_state.live(after)
    need(actual['id'] not in {row['id'] for row in first['entities']}
         and same(semantic_map(before),semantic_map(after,[actual['id']])))
    scripts_packet(scripts,scripts['requestId'],after['processId'],scripts['capturedEpochMs'])
    need(abs(scripts['capturedEpochMs']-after['clockAfter']['epochMs'])<=1500 and scripts['requestedEpochMs']>=after_epoch)
    source = directory+'/script-bundle/main.js'; engine = running_owned_engine(scripts,source)
    need(loaded_relative_modules(engine) == ['companion.js'] and scripts['source'].get('membershipSourceVersion') == 1
         and scripts['source']['membership']['complete'])
    managers = [row for row in scripts['source']['membership']['managers'] if row['instance'] == engine['required']['instance']]
    need(len(managers) == 1); manager = managers[0]
    need(manager['assigned'] and manager['url'] == source and manager['assignedEpochMs'] >= after_epoch
         and manager['assignedEpochMs'] <= engine['code']['submittedEpochMs'])
    units = originals(run,files['fixtureUrl'],files['ticket'],files['nonce'])['script-bundle/main.js'].decode('utf-8').encode('utf-16le')
    code = engine['code']; need(code['submitted'] and code['encoding'] == 'utf-16le-code-units'
         and code['codeUnits'] == len(units)//2 and code['sha256'] == hashlib.sha256(units).hexdigest())
    return dict(iosCreateMarkerAdmissionVersion=VERSION,marker=actual,manager=deepcopy(manager),code=deepcopy(code),sourceUrl=source)


def restored(before,after,scripts,owned,terminal_packet,*,after_sequence,after_epoch):
    view_preserved(before,after); need(owned['iosCreateMarkerAdmissionVersion'] == VERSION)
    need(owned['marker']['id'] not in {row['id'] for row in after['source']['entities']} and same(semantic_map(before),semantic_map(after)))
    scripts_packet(scripts,scripts['requestId'],after['processId'],scripts['capturedEpochMs'])
    need(scripts['source'].get('membershipSourceVersion') == 1 and scripts['source']['membership']['complete']
         and not any(row['instance'] == owned['manager']['instance'] for row in scripts['source']['membership']['managers'])
         and not any(row['required']['instance'] == owned['manager']['instance'] or row['url'] == owned['sourceUrl'] for row in scripts['source']['engines']))
    boundaries = terminal(terminal_packet,owned['manager'],owned['code'],after_sequence=after_sequence,after_epoch=after_epoch)
    need(terminal_packet['processId'] == after['processId']); return deepcopy(boundaries)
