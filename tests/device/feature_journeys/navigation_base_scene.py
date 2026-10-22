"""Static original navigation base input; socket receipts are not client facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import re
from urllib.parse import urlsplit

from .contract import exact,identifier,number
from .navigation_scene import base_scene
from navigation_observation import viewpoint_urls

VERSION=1
PROFILE='navigation-static-base-v1'


def resource_url(scene_url):
    viewpoint_urls(scene_url);parsed=urlsplit(scene_url)
    if parsed.query or parsed.fragment:raise ValueError('A static navigation scene root is required')
    path=parsed.path[:-5]+'.base.json' if parsed.path.endswith('.json') else parsed.path+'.base.json'
    return parsed._replace(path=path).geturl()


def body():
    value=base_scene()
    if (len(value['Entities'])!=5 or any(row['type']!='Box' or any(key in row for key in ('script','serverScripts','sourceUrl'))
            for row in value['Entities'])):raise ValueError('Navigation base must remain static geometry')
    raw=json.dumps(value,separators=(',',':'),ensure_ascii=False).encode()
    if not 1<=len(raw)<=16384:raise ValueError('Static navigation base exceeds its bound')
    return raw


def validate_status(value,*,instance,scene_url,source_revision,previous=None):
    exact(value,{'navigationBaseSceneVersion','profile','instance','url','sourceRevision','bytes','sha256',
        'capturedEpochMs','available','complete','responses'},'original static navigation base source')
    raw=body();identifier(instance)
    if type(source_revision) is not str or re.fullmatch('[0-9a-f]{40}',source_revision) is None:
        raise ValueError('Original source revision is required')
    if (type(value['navigationBaseSceneVersion']) is not int or value['navigationBaseSceneVersion']!=VERSION
            or value['profile']!=PROFILE or value['instance']!=instance or value['url']!=resource_url(scene_url)
            or value['sourceRevision']!=source_revision or type(value['available']) is not bool or value['complete'] is not True
            or type(value['bytes']) is not int or value['bytes']!=len(raw) or value['sha256']!=hashlib.sha256(raw).hexdigest()
            or type(value['capturedEpochMs']) is not int or value['capturedEpochMs']<1
            or type(value['responses']) is not list or len(value['responses'])>256):raise ValueError('Original static navigation base unavailable')
    ids=set();last=0
    for index,row in enumerate(value['responses'],1):
        exact(row,{'sequence','responseId','bytes','sha256','completedEpochMs'},'original static base socket receipt')
        identifier(row['responseId'])
        if (type(row['sequence']) is not int or row['sequence']!=index or row['responseId'] in ids
                or type(row['bytes']) is not int or row['bytes']!=len(raw) or row['sha256']!=value['sha256']
                or not last<=number(row['completedEpochMs'],1)<=value['capturedEpochMs']):raise ValueError('Invalid static base socket history')
        ids.add(row['responseId']);last=row['completedEpochMs']
    if previous is not None:
        validate_status(previous,instance=instance,scene_url=scene_url,source_revision=source_revision)
        old=previous['responses']
        if (value['capturedEpochMs']<previous['capturedEpochMs'] or len(value['responses'])<len(old)
                or value['responses'][:len(old)]!=old or not previous['available'] and value['available']):
            raise ValueError('Original static base history changed')
    return value
