"""Original VR owner IDs and head pose; no framework or scene restoration verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import re
from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_graphics_subject import entity_id,rotation,vector,text
from feature_journeys.graphics_fixture import subject_ids

VERSION=1
TABLET={'frame','screen','home','highlight','miniFrame','miniScreen'}


def digest(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def nullable_id(value):return value is None or entity_id(value) and value!='00000000-0000-0000-0000-000000000000'


def affine(value,*,rigid=False):
    vector(value,16,-1000000,1000000)
    need(all(abs(value[index]-wanted)<1e-5 for index,wanted in ((3,0),(7,0),(11,0),(15,1))))
    columns=[[value[col*4+row] for row in range(3)] for col in range(3)]
    scales=[math.sqrt(sum(v*v for v in col)) for col in columns]
    need(all(.0001<=v<=1000 for v in scales) and max(scales)-min(scales)<=max(scales)*.001
        and (not rigid or all(abs(v-1)<.001 for v in scales)))
    unit=[[v/scale for v in col] for col,scale in zip(columns,scales)]
    need(all(abs(sum(a*b for a,b in zip(unit[i],unit[j])))<.001 for i,j in ((0,1),(0,2),(1,2))))
    a,b,c=unit
    determinant=a[0]*(b[1]*c[2]-b[2]*c[1])-b[0]*(a[1]*c[2]-a[2]*c[1])+c[0]*(a[1]*b[2]-a[2]*b[1])
    need(abs(determinant-1)<.003)
    return scales[0]


def multiply(a,b):return [sum(a[k*4+r]*b[c*4+k] for k in range(4)) for c in range(4) for r in range(4)]


def rotation_columns(value):
    rotation(value);x,y,z,w=value;length=math.sqrt(sum(v*v for v in value));x,y,z,w=(v/length for v in value)
    return [[1-2*(y*y+z*z),2*(x*y+z*w),2*(x*z-y*w)],
        [2*(x*y-z*w),1-2*(x*x+z*z),2*(y*z+x*w)],
        [2*(x*z+y*w),2*(y*z-x*w),1-2*(x*x+y*y)]]


def head(value):
    exact(value,{'display','active','visible','mounted','sensorToWorld','sensorPose','worldPosition','worldRotation'})
    need(value['display']=='OpenXR' and value['active'] is True
        and type(value['visible']) is bool and type(value['mounted']) is bool)
    affine(value['sensorToWorld']);affine(value['sensorPose'],rigid=True)
    actual=multiply(value['sensorToWorld'],value['sensorPose']);scale=affine(actual)
    vector(value['worldPosition'],3,-1000000,1000000)
    need(all(abs(a-b)<=.001+abs(b)*2e-7 for a,b in zip(value['worldPosition'],actual[12:15])))
    columns=rotation_columns(value['worldRotation'])
    need(all(abs(actual[c*4+r]/scale-columns[c][r])<.002 for c in range(3) for r in range(3)))


def validate_framework(source,run):
    need(type(source) is dict and type(source.get('subjectVersion')) is int and source['subjectVersion']==3)
    value=source['framework'];exact(value,{'ownershipVersion','tablet','keyboard','pointers','entities'})
    need(type(value['ownershipVersion']) is int and value['ownershipVersion']==VERSION)
    exact(value['tablet'],TABLET);references=set()
    def collect(identifier):
        need(nullable_id(identifier))
        if identifier is not None:references.add(identifier)
    for identifier in value['tablet'].values():collect(identifier)
    keyboard=value['keyboard'];exact(keyboard,{'entityIds','anchor','textDisplay','backPlate','raised','use3D'})
    need(type(keyboard['entityIds']) is list and len(keyboard['entityIds'])<=1024
        and all(entity_id(v) for v in keyboard['entityIds'])
        and keyboard['entityIds']==sorted(set(keyboard['entityIds']))
        and type(keyboard['raised']) is bool and type(keyboard['use3D']) is bool)
    for identifier in keyboard['entityIds']:collect(identifier)
    for role in ('anchor','textDisplay','backPlate'):
        collect(keyboard[role]);need(keyboard[role] is None or keyboard[role] in keyboard['entityIds'])
    need(type(value['pointers']) is list and len(value['pointers'])<=128)
    previous=0;picks=set()
    for pointer in value['pointers']:
        exact(pointer,{'id','kind','pickId','enabled','renderState','scriptParametersSha256','hasScriptParameters','states'})
        need(integer(pointer['id'],previous+1,2**32-1) and integer(pointer['pickId'],1,2**32-1) and pointer['pickId'] not in picks
            and type(pointer['kind']) is str and pointer['kind'] in ('laser','parabola','stylus')
            and type(pointer['enabled']) is bool and type(pointer['hasScriptParameters']) is bool
            and digest(pointer['scriptParametersSha256']) and type(pointer['states']) is list and len(pointer['states'])<=128)
        previous=pointer['id'];picks.add(pointer['pickId'])
        need(pointer['renderState'] is None if pointer['kind']=='stylus' else text(pointer['renderState'],128))
        names=[]
        for state in pointer['states']:
            exact(state,{'scope','name','entities'})
            need(type(state['scope']) is str and state['scope'] in ('normal','default') and text(state['name'],128))
            names.append((0 if state['scope']=='normal' else 1,state['name']))
            roles={'start','end','path'} if pointer['kind']=='laser' else {'start','end'} if pointer['kind']=='parabola' else {'stylus'}
            exact(state['entities'],roles)
            for identifier in state['entities'].values():collect(identifier)
        need(names==sorted(set(names),key=lambda item:(item[0],item[1].encode('utf-16-be',errors='surrogatepass'))))
        if pointer['kind']=='stylus':need(names==[(0,'stylus')])
    need(len(references)<=2048 and not references.intersection(subject_ids(run).values())
        and type(value['entities']) is list and len(value['entities'])==len(references))
    identifiers=[]
    for row in value['entities']:
        exact(row,{'id','present','type','hostType','parentId','propertySha256','appearanceSha256'})
        need(entity_id(row['id']) and row['id'] in references and type(row['present']) is bool)
        identifiers.append(row['id'])
        if row['present']:
            need(text(row['type'],64) and row['type']!='Unknown' and row['hostType']=='local' and nullable_id(row['parentId'])
                and row['parentId'] not in subject_ids(run).values() and digest(row['propertySha256']) and digest(row['appearanceSha256']))
        else:need(all(row[key] is None for key in ('type','hostType','parentId','propertySha256','appearanceSha256')))
    need(identifiers==sorted(references))
    head(source['hmd'])
    return value


def separate_inventory(value):
    """Keep raw originals and derive a separate exact registered-UI partition.

    Appearance hashes deliberately omit position/rotation/dimensions/visibility.
    They cannot alone prove framework restoration; the original raw hashes,
    owner inventory, current UI/input lifetimes and avatar/head relation remain
    independently necessary. Nothing is excluded because of a name or host type.
    """
    from adapters.native_graphics_subject import validate
    need(type(value) is dict)
    validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action='feature-graphics-subject-observe',runId=value.get('runId')),
        value.get('processId'),value.get('capturedEpochMs'),require_avatar=True,require_framework=True)
    source=value['source'];ids={row['id'] for row in source['framework']['entities'] if row['present']}
    raw=deepcopy(source['scan']['unowned'])
    return dict(raw=raw,scene=[row for row in raw if row['id'] not in ids],framework=[row for row in raw if row['id'] in ids],
        ownership=deepcopy(source['framework']),hmd=deepcopy(source['hmd']))


def first_person_head(value):
    """Current native camera relation, not a demand to freeze physical head pose."""
    separate_inventory(value);source=value['source'];view=source['view'];hmd=source['hmd']
    need(view['mode'] in ('first person','first person look at') and view['perspective']
        and hmd['active'] and hmd['visible'] and hmd['mounted'])
    need(all(abs(a-b)<.002 for a,b in zip(view['position'],hmd['worldPosition'])))
    a=rotation_columns(view['rotation']);b=rotation_columns(hmd['worldRotation'])
    need(all(abs(a[c][r]-b[c][r])<.002 for c in range(3) for r in range(3)))
    return deepcopy(hmd)
