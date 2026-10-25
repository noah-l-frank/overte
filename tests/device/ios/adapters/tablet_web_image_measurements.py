"""Actual DOM/WK presentation joins for original WDA screen PNG pixels.

Native UIKit screen capture is distinct from a Vulkan frame. Its original
native and host clock brackets remain untouched; current page identity, actual
window geometry and the independently decoded marker must all agree.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from adapters.native_feature_observation import exact,need,number
from adapters.native_clock_join import digest
from adapters.script_feature.history import same
from feature_journeys.evidence import image_observation,rectangle
from ios.adapters.graphics_history import follow_native
from ios.adapters.tablet_web_images import capture_record
from ios.adapters.tablet_web_history import TYPED,_live
from ios.adapters import tablet_web_dom as dom,tablet_web_presentation as presentation
from ios.adapters.tablet_web_admission import validate as admission_original

VERSION=1


def frame(value,binding):
    exact(value,{'row','frame'});row,parts=value['row'],value['frame']
    need(row['status']=='returned' and row['tabletWebAcquisitionVersion']==2 and row['hostProcessId']==row['admission']['hostProcessId'])
    admission_original(row['admission'],binding)
    need(row['clockJoin']['originalsSha256']==digest(parts))
    for name,module in TYPED.items():module.original(parts[name])
    document=parts['document'];need(document['status']=='ready' and parts['state']['iosTabletWebStateVersion']==2)
    dom.join_sources(document,parts['sources']);_live(parts,document)
    need(all(packet['processId']==int(binding['processIdentity']) for name,packet in parts.items() if name in TYPED))
    return document


def projected(policy,document,extent):
    native=document['source']['presentationAfter'];presentation.current(native)
    actual=document['source']['dom'];viewport=actual['document']['visualViewport'];view=native['screenFrame'];screen=native['screenCoordinates']
    need(abs(extent[0]/screen[2]-extent[1]/screen[3])<.01)
    sx=extent[0]/screen[2];css=view[2]/viewport['width'];need(number(css,.01,100) and viewport['height']*css<=view[3]+1)
    def project(rect):
        left,top,right,bottom=rect
        need(viewport['offsetLeft']<=left<right<=viewport['offsetLeft']+viewport['width']
            and viewport['offsetTop']<=top<bottom<=viewport['offsetTop']+viewport['height'])
        return [(view[0]-screen[0]+(left-viewport['offsetLeft'])*css)*sx,
            (view[1]-screen[1]+(top-viewport['offsetTop'])*css)*sx,
            (view[0]-screen[0]+(right-viewport['offsetLeft'])*css)*sx,
            (view[1]-screen[1]+(bottom-viewport['offsetTop'])*css)*sx]
    markers=[row for row in actual['elements'] if row['id']=='feature-marker' and row['tag']=='IMG' and row['visible']]
    need(len(markers)==1);outer=project(markers[0]['rect']);width,height=outer[2]-outer[0],outer[3]-outer[1]
    # Exact immutable fixture raster: 160x40, cells occupy [4,132]x[4,36].
    interior=[outer[0]+width*4/160,outer[1]+height*4/40,outer[0]+width*132/160,outer[1]+height*36/40]
    rounded=[math.ceil(interior[0]),math.ceil(interior[1]),math.floor(interior[2]),math.floor(interior[3])]
    exact(policy,{'source','marker','subject'});need(policy['source']=='native-screen')
    rectangle(policy['marker'],extent);rectangle(policy['subject'],extent)
    need(all(abs(a-b)<=1 for a,b in zip(policy['marker'],rounded)))
    visible=project([viewport['offsetLeft'],viewport['offsetTop'],viewport['offsetLeft']+viewport['width'],viewport['offsetTop']+viewport['height']])
    a,b,c,d=policy['subject'];need(visible[0]<=a<c<=visible[2] and visible[1]<=b<d<=visible[3])
    return dict(marker=rounded,visible=visible,presentation=deepcopy(native))


def compose(run,ticket,binding,before,after,capture,raw,policy,*,previous=None,changed=False):
    left,right=frame(before,binding),frame(after,binding);capture_record(capture,raw)
    a,b=before['row'],after['row'];follow_native(a['nativeAfter'],b['nativeBefore'])
    first,last=a['clockJoin'],b['clockJoin'];duration=(last['hostAfterMonotonic']-first['hostBeforeMonotonic'])*1000
    need(0<=last['hostAfterEpochMs']-first['hostBeforeEpochMs']<1500 and 0<=duration<1500
        and abs(last['hostAfterEpochMs']-first['hostBeforeEpochMs']-duration)<=250
        and abs(b['nativeAfter']['capturedEpochMs']-a['nativeBefore']['capturedEpochMs']-duration)<=250)
    for row in (a,b):
        for phase in (row['phaseBefore'],row['phaseAfter']):
            need(phase['runId']==run and phase['area']=='tablet-web' and phase['active'] and phase['activations'][-1]['ticket']==ticket)
    need(capture['sessionId']==binding['sessionId'] and str(capture['processId'])==binding['processIdentity']
        and a['nativeAfter']['capturedEpochMs']<=capture['nativeBeforeMs']<=capture['nativeAfterMs']<=b['nativeBefore']['capturedEpochMs']
        and a['after']['epochMs']<=capture['hostBeginEpochMs']<=capture['hostEndEpochMs']<=b['before']['epochMs']
        and a['after']['monotonic']<=capture['hostBeginMonotonic']<=capture['hostEndMonotonic']<=b['before']['monotonic'])
    need(same(left['source']['nativeView'],right['source']['nativeView'])
        and same(left['source']['presentationAfter'],right['source']['presentationBefore'])
        and same(left['source']['dom']['document'],right['source']['dom']['document']))
    marker=projected(policy,left,capture['extent']);need(same(marker,projected(policy,right,capture['extent'])))
    image,subject=image_observation(raw,run,ticket,policy,previous=previous,changed=changed)
    return dict(tabletWebImageVersion=VERSION,captureSha256=digest(capture),document=deepcopy(right['source']['nativeView']),
        marker=marker,image=image),subject
