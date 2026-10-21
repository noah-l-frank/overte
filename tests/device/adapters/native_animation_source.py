"""Actual consumed animation model/FBX identities, never a requested URL digest."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact,integer,need

VERSION=1
LIMIT=32*1024*1024
PINS=Path(__file__).resolve().parents[1]/'feature_journeys/emote-animation-pins.v1.json'
NAMES=('Crying','Surprised','Dancing','Cheering','Waving','Fall','Pointing','Clapping','Sit1','Sit2','Sit3','Love')


def nonce(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None
def digest(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def model(value,epoch):
    exact(value,{'animationDataVersion','instance','sourceUrlSha256','bytes','sha256','parser','frames','joints','parsedEpochMs'})
    need(integer(epoch,1) and type(value['animationDataVersion']) is int and value['animationDataVersion']==VERSION
        and nonce(value['instance']) and digest(value['sourceUrlSha256']) and digest(value['sha256'])
        and integer(value['bytes'],1,LIMIT) and value['parser'] in ('fbx-full-v1','fbx-skip-unused-curves-v1')
        and integer(value['frames'],1,1000000) and integer(value['joints'],1,10000) and integer(value['parsedEpochMs'],1,epoch))
    return value


def validate(value,epoch):
    exact(value,{'animationSourceVersion','resourceInstance','model','consumedEpochMs','blend'})
    need(integer(epoch,1) and type(value['animationSourceVersion']) is int and value['animationSourceVersion']==VERSION
        and nonce(value['resourceInstance']) and integer(value['consumedEpochMs'],1,epoch)
        and value['blend'] in ('normal','add-absolute','add-relative'))
    model(value['model'],value['consumedEpochMs']);return value


def pins(path=PINS):
    value=json.loads(Path(path).read_text());exact(value,{'contractVersion','sourceBase','animations'})
    need(type(value['contractVersion']) is int and value['contractVersion']==VERSION
        and type(value['sourceBase']) is str and re.fullmatch('[0-9a-f]{40}',value['sourceBase'])
        and type(value['animations']) is list and len(value['animations'])==len(NAMES))
    names=[]
    for row in value['animations']:
        exact(row,{'name','sourcePath','bytes','sha256'})
        need(row['name'] in NAMES and row['sourcePath']=='scripts/system/assets/animations/'+row['name']+'.fbx'
            and integer(row['bytes'],1,LIMIT) and digest(row['sha256']));names.append(row['name'])
    need(tuple(names)==NAMES);return deepcopy(value)


def controlled(clip,name,epoch):
    """Join a measured loaded resource/name to actual consumed known FBX bytes.

    name is independently resolved from the current loaded URL/source profile,
    never an input name. This adds no pose, image, readiness or success verdict.
    """
    need(type(clip) is dict and name in NAMES and type(clip.get('animationSourceVersion')) is int
        and clip['animationSourceVersion']==VERSION and clip.get('assetSource') is not None)
    need(type(clip.get('url')) is str and len(clip['url'])<=4096)
    url=urlsplit(clip['url'])
    need(url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment
        and url.path.rsplit('/',1)[-1]==name+'.fbx')
    value=validate(clip['assetSource'],epoch);actual=value['model']
    need(value['blend']=='normal' and actual['parser']=='fbx-full-v1' and type(clip.get('url')) is str
        and actual['sourceUrlSha256']==hashlib.sha256(clip['url'].encode('utf-8')).hexdigest()
        and actual['frames']==clip['loadedFrames'])
    expected=next(row for row in pins()['animations'] if row['name']==name)
    need(actual['bytes']==expected['bytes'] and actual['sha256']==expected['sha256'])
    return deepcopy(value)
