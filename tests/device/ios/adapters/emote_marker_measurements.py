"""Original marker Script/whole-tree/view admission and restoration joins."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_feature_observation import need
from adapters.native_script_observation import running_owned_engine,loaded_relative_modules
from adapters.native_script_terminal import terminal
from ios.adapters.emote_marker_files import originals
from ios.adapters.emote_world import original,actual_domain,owned_marker,preserve_unowned
from ios.adapters.view_controls import MODES

VERSION=1


def near(left,right,tolerance):return len(left)==len(right) and sum((a-b)**2 for a,b in zip(left,right))<=tolerance*tolerance


def orientation(left,right):
    return near(left,right,.00001) or near(left,[-x for x in right],.00001)


def body_preserved(before,after):
    for value in (before,after):original(value)
    need(before['runId']==after['runId'] and before['processId']==after['processId']
        and before['instance']==after['instance'] and actual_domain(before)==actual_domain(after)
        and before['source']['sceneUrl']==after['source']['sceneUrl'])
    a,b=before['source']['avatar'],after['source']['avatar']
    need(not a['flying'] and not b['flying'] and not a['inAir'] and not b['inAir']
        and near(a['feetPosition'],b['feetPosition'],.005) and orientation(a['orientation'],b['orientation'])
        and abs(a['modelScale']-b['modelScale'])<.00001 and sum(v*v for v in b['velocity'])<.0001)
    return deepcopy(b)


def view_preserved(before,after):
    for value in (before,after):original(value)
    a,b=before['source']['view'],after['source']['view']
    need(a['mode']==b['mode'] and a['perspective']==b['perspective'] and near(a['position'],b['position'],.005)
        and orientation(a['rotation'],b['rotation']) and abs(a['fieldOfViewDegrees']-b['fieldOfViewDegrees'])<.0001
        and abs(a['aspectRatio']-b['aspectRatio'])<.0001)
    x,y=before['source']['cameraOrbit'],after['source']['cameraOrbit']
    need(orientation(x['lookAtRotation'],y['lookAtRotation'])
        and all(abs(x[k]-y[k])<.0001 for k in ('boomLength','minimumBoomLength','defaultBoomLength')))
    return deepcopy(b)


def admitted(before,after,files,directory,*,after_epoch):
    """Exact submitted bytes and actual returned UUID, never requested IDs."""
    body_preserved(before,after);need(not before['source']['markers'])
    need(before['source']['view']['mode'] in MODES)
    run=before['runId'];need(files['runId']==run)
    url=files['fixtureUrl']+'tickets/'+files['ticket']+'/graphics-marker.v1.html'
    marker=owned_marker(after,files['nonce'],url)
    old={r['id'] for r in before['source']['tree']['entities']};new={r['id'] for r in after['source']['tree']['entities']}
    need(new-old=={marker['id']} and not old-new);preserve_unowned(before,after,{marker['id']})
    scripts=after['source']['scriptOriginal'];source=directory+'/script-bundle/main.js'
    engine=running_owned_engine(scripts,source);need(loaded_relative_modules(engine)==['companion.js'])
    need(scripts['source'].get('membershipSourceVersion')==1 and scripts['source']['membership']['complete'])
    members=[r for r in scripts['source']['membership']['managers'] if r['instance']==engine['required']['instance']]
    need(len(members)==1);manager=members[0]
    need(manager['assigned'] and manager['url']==source and after_epoch<=manager['assignedEpochMs']<=engine['code']['submittedEpochMs'])
    raw=originals(run,files['fixtureUrl'],files['ticket'],files['nonce'])['script-bundle/main.js']
    units=raw.decode('utf-8').encode('utf-16le');code=engine['code']
    need(code['submitted'] and code['encoding']=='utf-16le-code-units' and code['codeUnits']==len(units)//2
        and code['sha256']==hashlib.sha256(units).hexdigest())
    return dict(iosEmoteMarkerVersion=VERSION,marker=marker,manager=deepcopy(manager),code=deepcopy(code),sourceUrl=source)


def restored(before,after,owned,terminal_packet,*,after_sequence,after_epoch):
    """Original map absence, unowned preservation, two terminal boundaries."""
    body_preserved(before,after);need(type(owned) is dict and owned.get('iosEmoteMarkerVersion')==VERSION)
    marker=owned['marker'];need(not after['source']['markers'])
    need(marker['id'] not in {r['id'] for r in after['source']['tree']['entities']})
    preserve_unowned(before,after,{marker['id']})
    need(after['source']['tree']['entities']==before['source']['tree']['entities'])
    scripts=after['source']['scriptOriginal'];membership=scripts['source'].get('membership')
    need(scripts['source'].get('membershipSourceVersion')==1 and membership['complete']
        and not any(r['instance']==owned['manager']['instance'] for r in membership['managers'])
        and not any(r['required']['instance']==owned['manager']['instance'] or r['url']==owned['sourceUrl']
                    for r in scripts['source']['engines']))
    boundaries=terminal(terminal_packet,owned['manager'],owned['code'],after_sequence=after_sequence,after_epoch=after_epoch)
    need(terminal_packet['processId']==after['processId'])
    view_preserved(before,after)
    return deepcopy(boundaries)
