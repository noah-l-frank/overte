"""Bounded actual per-channel history dependencies and independent Rig input join.

This verifies a retained producer DTO, not native execution, socket delivery,
skinning or packet-to-draw causality. Inactive float storage is never read or invented; the actual Rig branch
gives retained active nonfinite/zero representations their meaning.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import math
import re
import struct
from adapters.native_feature_observation import exact, integer, need, number
from adapters.native_graphics_subject import vector
from adapters.script_journey.history import same

VERSION = 1


def floats(value, count):
    need(type(value) is list and len(value) == count
         and all(type(bit) is str and re.fullmatch('[0-9a-f]{8}', bit) for bit in value))
    return [struct.unpack('>f', bytes.fromhex(bit))[0] for bit in value]


def near(a, b):
    need(len(a) == len(b) and all(math.isfinite(x) and math.isfinite(y)
        and abs(x-y) <= 2e-4 * max(1, abs(x), abs(y)) for x, y in zip(a, b)))


def multiply(a, b):
    x,y,z,w=a; X,Y,Z,W=b
    return [w*X+x*W+y*Z-z*Y, w*Y+y*W+z*X-x*Z, w*Z+z*W+x*Y-y*X, w*W-x*X-y*Y-z*Z]


def inverse(q):
    size=sum(x*x for x in q); need(math.isfinite(size) and size > 0)
    return [-q[0]/size,-q[1]/size,-q[2]/size,q[3]/size]


def section_assignments(row):
    """Original LSB validity/default bits; no latest-section substitution."""
    raw=base64.b64decode(row['base64']); count=raw[0]; width=(count+7)//8
    if row['kind'] == 'default-flags':
        need(len(raw) == 1+2*width)
        return raw[1:1+width], raw[1+width:], True
    need(len(raw) >= 1+2*width+4)
    rotations=raw[1:1+width]
    offset=1+width+6*sum(bool(rotations[i//8] & (1 << (i%8))) for i in range(count))
    need(offset+width+4 <= len(raw)); translations=raw[offset:offset+width]
    scale=struct.unpack('<f',raw[offset+width:offset+width+4])[0]
    need(math.isfinite(scale) and scale > 0 and len(raw) == offset+width+4+
        6*sum(bool(translations[i//8] & (1 << (i%8))) for i in range(count)))
    return rotations,translations,False


def wire_value(source, joint, channel):
    raw=base64.b64decode(source['base64']); count=raw[0]; width=(count+7)//8
    rotations,translations,defaults=section_assignments(source); need(not defaults and channel < 2)
    prior=lambda flags:sum(bool(flags[i//8] & (1 << (i%8))) for i in range(joint))
    if channel == 0:
        start=1+width+6*prior(rotations); data=raw[start:start+6]
        parts=[(((data[i]&127)<<8)|data[i+1])/32767*(2/math.sqrt(2))-1/math.sqrt(2) for i in (0,2,4)]
        square=sum(x*x for x in parts)
        if square > 1: parts=[x/math.sqrt(square) for x in parts]; missing=0.
        else: missing=-math.sqrt(1-square)
        largest=((data[2]&128)>>6)|((data[0]&128)>>7); parts.insert(largest,missing);return parts
    offset=1+width+6*sum(bool(rotations[i//8] & (1 << (i%8))) for i in range(count))+width
    scale=struct.unpack('<f',raw[offset:offset+4])[0];start=offset+4+6*prior(translations)
    return [x/16384*scale for x in struct.unpack('<hhh',raw[start:start+6])]


def interpolated(channel, a, b, theta, observed):
    # Native float32 endpoints are retained exactly. Arithmetic comparison is
    # bounded, with float rounding tolerance; this is not a replacement renderer.
    if not all(map(math.isfinite,a+b)):
        need(any(not math.isfinite(x) for x in observed));return
    if channel == 1: near(observed,[x*(1-theta)+y*theta for x,y in zip(a,b)]);return
    cosine=sum(x*y for x,y in zip(a,b))
    if cosine < 0: b=[-x for x in b];cosine=-cosine
    if cosine > 1-1.1920928955078125e-7: expected=[x*(1-theta)+y*theta for x,y in zip(a,b)]
    else:
        angle=math.acos(cosine);denominator=math.sin(angle)
        expected=[(math.sin((1-theta)*angle)*x+math.sin(theta*angle)*y)/denominator for x,y in zip(a,b)]
    near(observed,expected)


def validate(value, rig, pose, committed):
    exact(value, {'jointInterpolationVersion','available','assignmentPending','failure','nowUs','historyResets','historyAppends',
        'historyPrunes','roots','selection','nodes','sections'})
    count=pose['inputJointCount']
    need(type(value['jointInterpolationVersion']) is int and value['jointInterpolationVersion'] == VERSION
         and value['available'] is True and value['assignmentPending'] is False and value['failure'] == ''
         and integer(value['nowUs'],1,9007199254740991)
         and all(integer(value[k],0,9007199254740991) for k in ('historyResets','historyAppends','historyPrunes'))
         and type(value['roots']) is list and len(value['roots']) == count
         and type(value['selection']) is list and len(value['selection']) == count
         and type(value['nodes']) is list and 1 <= len(value['nodes']) <= 1024
         and type(value['sections']) is list and len(value['sections']) <= 1024)
    sections={}; masks={}; total=0
    for row in value['sections']:
        need(type(row) is dict and row.get('kind') in ('joint-data','default-flags'))
        committed(row,row['kind'],pose['subjectSessionId'],row.get('jointCount'),pose['begunEpochMs'],
            pose['capturedEpochMs'],require_fresh=False)
        latest=pose['received']['jointData' if row['kind'] == 'joint-data' else 'defaultFlags']
        need(latest is not None and row['sequence'] <= latest['sequence']
             and row['parsedEpochMs'] <= latest['parsedEpochMs'] and row['committedEpochMs'] <= latest['committedEpochMs'])
        if row['sequence'] == latest['sequence']: need(same(row,latest))
        need(row['sequence'] not in sections); sections[row['sequence']]=row; masks[row['sequence']]=section_assignments(row)
        total+=row['bytes'];need(total <= 65536)
    nodes={}; depths={}; used_sources=set()
    for row in value['nodes']:
        exact(row, {'id','joint','channel','op','value','parents','source','detail'})
        ident=row['id']; j,c=row['joint'],row['channel']
        need(integer(ident,1,9007199254740991) and ident not in nodes and integer(j,0,count-1) and integer(c,0,3)
             and type(row['parents']) is list and len(row['parents']) <= 2)
        if c < 2:
            if row['value'] is not None: floats(row['value'],4 if c == 0 else 3)
        else: need(type(row['value']) is bool)
        parents=row['parents']
        need(all(integer(p,1,ident-1) and p in nodes and nodes[p]['joint'] == j and nodes[p]['channel'] == c for p in parents))
        depth=1+max((depths[p] for p in parents),default=0);need(depth <= 256); depths[ident]=depth
        if row['op'] in ('initial','inactive'):
            need(not parents and row['source'] is None and row['detail'] == {})
            if row['op'] == 'inactive': need(c < 2 and row['value'] is None)
        elif row['op'] == 'wire':
            need(not parents and integer(row['source'],1,9007199254740991) and row['source'] in sections and row['detail'] == {})
            source=sections[row['source']]; need(j < source['jointCount']); r,t,defaults=masks[row['source']]
            flag=bool((r if c in (0,2) else t)[j//8] & (1 << (j%8)))
            if defaults: need(c >= 2 and row['value'] is flag)
            else:
                need(flag)
                if c >= 2: need(row['value'] is False)
                else: near(floats(row['value'],4 if c == 0 else 3),wire_value(source,j,c))
            used_sources.add(row['source'])
        else:
            need(row['op'] == 'interpolate' and c < 2 and len(parents) == 2 and row['source'] is None)
            exact(row['detail'], {'thetaBits'}); theta=floats([row['detail']['thetaBits']],1)[0];need(number(theta,0,1))
            if row['value'] is not None:
                interpolated(c, floats(nodes[parents[0]]['value'],4 if c == 0 else 3),
                    floats(nodes[parents[1]]['value'],4 if c == 0 else 3), theta, floats(row['value'],4 if c == 0 else 3))
        nodes[ident]=row
    need(used_sources == set(sections))

    def roots(refs, joint):
        need(type(refs) is list and len(refs) == 4)
        for c,ref in enumerate(refs): need(integer(ref,1,9007199254740991) and ref in nodes and nodes[ref]['joint'] == joint and nodes[ref]['channel'] == c)
        values=[nodes[ref]['value'] for ref in refs]
        for c in range(2):
            if values[c+2]: values[c]=None
            else: floats(values[c],4 if c == 0 else 3)
        return values

    reachable=set()
    def walk(ref):
        if ref in reachable: return
        reachable.add(ref)
        for p in nodes[ref]['parents']: walk(p)

    for j,row in enumerate(value['selection']):
        need(type(row) is dict and type(row.get('joint')) is int and row['joint'] == j)
        current=roots(value['roots'][j],j); need(same(row.get('output'),value['roots'][j]))
        if row.get('mode') in ('direct-size-mismatch','empty-history-hold'):
            exact(row, {'joint','mode','output'})
        else:
            exact(row, {'joint','mode','historySize','historyStart','oldIndex','newIndex','oldTimeUs','newTimeUs',
                'latencyUs','timePointUs','thetaBits','old','new','output'})
            size,start,a,b=row['historySize'],row['historyStart'],row['oldIndex'],row['newIndex']
            need(integer(size,1,2000) and type(start) is int and start == max(0,size-45)
                 and integer(a,start,size-1) and integer(b,a,min(a+1,size-1))
                 and integer(row['oldTimeUs'],1,9007199254740991) and integer(row['newTimeUs'],row['oldTimeUs'],9007199254740991)
                 and integer(row['latencyUs'],0,600000) and integer(row['timePointUs'],1,9007199254740991)
                 and row['timePointUs'] == value['nowUs']-row['latencyUs'])
            if a != b:
                need(row['mode'] == 'interpolated' and b == a+1 and row['oldTimeUs'] <= row['timePointUs'] < row['newTimeUs'])
            elif row['timePointUs'] < row['oldTimeUs']:
                need(row['mode'] == 'oldest-future-hold' and a == start and row['oldTimeUs'] == row['newTimeUs'] and same(row['old'],row['new']))
            else:
                need(row['mode'] == 'newest-clamp' and a == size-1 and row['oldTimeUs'] == row['newTimeUs'] and same(row['old'],row['new']))
            theta=floats([row['thetaBits']],1)[0]
            expected=min(1.,max(0,row['timePointUs']-row['oldTimeUs'])/max(1,row['newTimeUs']-row['oldTimeUs']))
            need(number(theta,0,1) and abs(theta-expected) < 2e-6)
            older,newer=roots(row['old'],j),roots(row['new'],j)
            for c in range(2):
                if not current[c+2]: need(not older[c+2] and not newer[c+2])
            for c in range(2):
                output=nodes[row['output'][c]]
                if current[c+2]: need(output['op'] == 'inactive' and output['value'] is None)
                else:
                    need(output['op'] == 'interpolate' and output['parents'] == [row['old'][c],row['new'][c]]
                         and output['detail']['thetaBits'] == row['thetaBits'])
            for ref in row['old']+row['new']: walk(ref)
        for ref in row['output']: walk(ref)
        need(same(current,rig['inputs'][j]))
    need(reachable == set(nodes))
    return value


def validate_rig(value, pose):
    exact(value, {'inputs','decisions','rigToGeometryRotation','rotationZeroThreshold'})
    count=pose['inputJointCount']; need(type(value['inputs']) is list and len(value['inputs']) == count
        and type(value['decisions']) is list and len(value['decisions']) == count
        and number(value['rotationZeroThreshold'],0,1e-3))
    vector(value['rigToGeometryRotation'],4,-1e6,1e6)
    absolute=[]
    for j,(raw,row) in enumerate(zip(value['inputs'],value['decisions'])):
        need(type(raw) is list and len(raw) == 4 and type(raw[2]) is bool and type(raw[3]) is bool)
        if raw[2]: need(raw[0] is None)
        if raw[3]: need(raw[1] is None)
        q=[] if raw[2] else floats(raw[0],4);p=[] if raw[3] else floats(raw[1],3)
        exact(row, {'joint','parent','rotationChoice','absoluteRotation','defaultRotation','translationChoice',
            'relativeRotation','translation','defaultTranslation'})
        need(type(row['joint']) is int and row['joint'] == j and integer(row['parent'],-1,j-1))
        for key,size in (('absoluteRotation',4),('defaultRotation',4),('relativeRotation',4),('translation',3),('defaultTranslation',3)):
            vector(row[key],size,-1e6,1e6)
        qchoice='default-flag' if raw[2] else 'default-nonfinite' if not all(map(math.isfinite,q)) else \
            'default-zero' if sum(x*x for x in q) <= value['rotationZeroThreshold'] else 'rig-input'
        pchoice='default-flag' if raw[3] else 'default-nonfinite' if not all(map(math.isfinite,p)) else 'rig-input'
        need(row['rotationChoice'] == qchoice and row['translationChoice'] == pchoice)
        near(row['absoluteRotation'], multiply(value['rigToGeometryRotation'],q) if qchoice == 'rig-input' else row['defaultRotation'])
        absolute.append(row['absoluteRotation']); parent=row['parent']
        near(row['relativeRotation'],row['absoluteRotation'] if parent == -1 else multiply(inverse(absolute[parent]),row['absoluteRotation']))
        near(row['translation'],p if pchoice == 'rig-input' else row['defaultTranslation'])
        near(row['relativeRotation']+row['translation'],pose['relativeJoints'][j])
    return value
