"""Explicit owned Pico Navigation world stimulus; geometry is never evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import uuid
from urllib.parse import urlsplit
from .contract import identifier
from navigation_observation import POSITIONS,FIXTURE_MARKERS

VERSION=1
PROFILE='pico-navigation-scene-v1'
MARKER='navigation-marker.v1.html'


def scene(run,ticket,origin):
    identifier(run);identifier(ticket)
    p=urlsplit(origin)
    if (p.scheme not in ('http','https') or not p.hostname or p.username is not None or p.password is not None
            or p.path or p.query or p.fragment):raise ValueError('Original Navigation scene origin is required')
    p.port
    root=Path(__file__).resolve().parents[1]/'fixture'
    # Keep original geometry/spawn and rebase the existing interactable script
    # to its identical owned HTTP resource on this explicit fixture origin.
    value=json.loads((root/'scene.json').read_text())
    if value.get('DataVersion')!=3 or not set(FIXTURE_MARKERS).issubset({e.get('name') for e in value.get('Entities',[])}):
        raise ValueError('Original Navigation scene foundation changed')
    for original in value['Entities']:
        if original.get('script')=='scripted_interactable.js':
            original['script']=origin+'/feature-fixture/v1/runs/'+run+'/tickets/'+ticket+'/navigation-interactable.v1.js'
    namespace=uuid.UUID(hex=run)
    def entity(name,kind,position,dimensions,**properties):
        return dict(id='{'+str(uuid.uuid5(namespace,'navigation-stimulus-v1/'+name))+'}',name='e2e-'+run+'-navigation-'+name,
            type=kind,position=dict(zip('xyz',position)),dimensions=dict(zip('xyz',dimensions)),
            rotation=dict(x=0,y=0,z=0,w=1),collisionless=True,locked=False,**properties)
    colors=((220,40,170),(25,90,210),(30,190,65))
    marker_url=origin+'/feature-fixture/v1/runs/'+run+'/tickets/'+ticket+'/'+MARKER
    for index,(label,feet) in enumerate(POSITIONS.items()):
        x=feet['x']
        # The marker is above the original interactable. Its projected size is
        # about 320x80 per 800-pixel 90-degree eye at the authored viewpoint.
        # Actual pixel policy/visibility and physical head pose remain external.
        value['Entities'].append(entity('marker-'+label,'Web',(x,2.7,2),(1.6,.4,.01),dpi=100,sourceUrl=marker_url))
        for row in range(2):
            for column in range(4):
                rgb=colors[index] if (row+column)%2 else (225,225,225)
                value['Entities'].append(entity('cue-'+label+'-'+str(row)+'-'+str(column),'Box',
                    (x-.6+column*.4,.55+row*.4,1.3),(.4,.4,.05),color=dict(zip(('red','green','blue'),rgb))))
    # This is the existing A/B/C location mechanism, not a camera or pose setter.
    return value
