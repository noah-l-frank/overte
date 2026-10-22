"""Opt-in normal serverless navigation stimulus; never product observation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import re
from urllib.parse import parse_qs,urlsplit
import uuid

from .contract import exact,identifier,number
from navigation_observation import VIEWPOINTS

VERSION=1
PROFILE='navigation-marker-scene-v1'
MARKER_RESOURCE='navigation-marker.v1.html'


def marker_id(run):return str(uuid.uuid5(uuid.UUID(hex=identifier(run)),'navigation-marker-v1'))


def resource_root(value,run):
    identifier(run)
    if type(value) is not str or len(value)>512:raise ValueError('Original navigation resource root is required')
    url=urlsplit(value);port=url.port
    if (url.scheme not in ('http','https') or not url.hostname or url.username is not None or url.password is not None
            or port is not None and not 1<=port<=65535 or url.query or url.fragment
            or url.path!='/feature-fixture/v1/runs/'+run+'/'):
        raise ValueError('Navigation resource root belongs to another run or origin')
    return value


def viewpoint_query(value):
    if type(value) is not str or len(value)>1024:return False
    if value=='':return True
    try:parts=parse_qs(value,keep_blank_values=True,strict_parsing=True)
    except ValueError:return False
    return set(parts)=={'location'} and len(parts['location'])==1 and parts['location'][0] in VIEWPOINTS.values()


def scene(run,ticket,fixture_url):
    identifier(run);identifier(ticket);resource_root(fixture_url,run)
    original=json.loads((Path(__file__).resolve().parents[1]/'fixture'/'scene.json').read_text())
    # Retain all five real navigation geometry/physics markers. The unrelated
    # interactable and its entity-script load are outside this fixture profile.
    original['Entities']=[row for row in original['Entities'] if row['name']!='OVERTE_E2E_INTERACTABLE']
    original['Entities'].append(dict(id='{'+marker_id(run)+'}',name='e2e-'+run+'-navigation-marker',type='Web',
        position=dict(x=1.,y=1.3,z=.8),dimensions=dict(x=2.2,y=.55,z=.01),rotation=dict(x=0.,y=0.,z=0.,w=1.),
        collisionless=True,locked=True,visible=True,dpi=100,
        sourceUrl=fixture_url+'tickets/'+ticket+'/'+MARKER_RESOURCE))
    return original


def validate_status(value,*,instance,run,scene_url,previous=None):
    exact(value,{'navigationSceneVersion','instance','runId','profile','sceneUrl','active','ticket','capturedEpochMs',
                 'responses','complete'},'original navigation scene source')
    identifier(instance);identifier(run)
    if (type(value['navigationSceneVersion']) is not int or value['navigationSceneVersion']!=VERSION
            or value['instance']!=instance or value['runId']!=run or value['profile']!=PROFILE or value['sceneUrl']!=scene_url
            or type(value['active']) is not bool or value['complete'] is not True
            or type(value['responses']) is not list or len(value['responses'])>256):raise ValueError('Navigation scene source unavailable')
    number(value['capturedEpochMs'],1)
    if value['ticket'] is not None:identifier(value['ticket'])
    if not value['active'] and value['ticket'] is not None:raise ValueError('Retired scene source retained an active ticket')
    seen=set();epoch=0
    for sequence,row in enumerate(value['responses'],1):
        exact(row,{'sequence','responseId','ticket','bytes','sha256','completedEpochMs'},'navigation scene socket receipt')
        identifier(row['responseId']);identifier(row['ticket'])
        if (type(row['sequence']) is not int or row['sequence']!=sequence or row['responseId'] in seen
                or type(row['bytes']) is not int or not 1<=row['bytes']<=16384
                or type(row['sha256']) is not str or re.fullmatch('[0-9a-f]{64}',row['sha256']) is None
                or not epoch<=number(row['completedEpochMs'],1)<=value['capturedEpochMs']):raise ValueError('Invalid original scene receipt')
        seen.add(row['responseId']);epoch=row['completedEpochMs']
    if previous is not None:
        validate_status(previous,instance=instance,run=run,scene_url=scene_url)
        if (value['capturedEpochMs']<previous['capturedEpochMs'] or len(value['responses'])<len(previous['responses'])
                or value['responses'][:len(previous['responses'])]!=previous['responses'] or not previous['active'] and value['active']):
            raise ValueError('Original scene history changed or resurrected')
    return value
