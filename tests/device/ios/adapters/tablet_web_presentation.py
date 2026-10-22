"""Actual UIKit WK/window geometry, never a UIEvent lifetime verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,integer,need,number
from ios.adapters.tablet_web_sources import identifier

VERSION=1
IDS={'window','scene','view','presentation','presenter','controller','top'}
FLAGS={'keyWindow','mainScreen','viewWindowMatches','presentationWindowMatches','presented','topMatches','viewInController',
    'beingPresented','beingDismissed','hidden','interactionEnabled','dragging','decelerating','tracking','zooming'}
RECTS={'windowBounds','windowFrame','viewBounds','viewFrame','screenBounds','nativeScreenBounds','screenCoordinates','screenFrame'}
PAIRS={'scrollOffset','scrollSize'}
INSETS={'safeInsets','scrollInsets'}


def original(value):
    exact(value,IDS|FLAGS|RECTS|PAIRS|INSETS|{'tabletPresentationVersion','applicationState','sceneActivationState','interfaceOrientation','alpha','screenScale','zoomScale','responders','recognizers'})
    need(type(value['tabletPresentationVersion']) is int and value['tabletPresentationVersion']==VERSION
        and integer(value['applicationState'],0,2) and integer(value['sceneActivationState'],-1,2) and integer(value['interfaceOrientation'],0,4)
        and all(type(value[k]) is bool for k in FLAGS) and number(value['alpha'],0,1) and number(value['screenScale'],.1,10) and number(value['zoomScale'],.01,100))
    for key in IDS:identifier(value[key])
    need(len({value[k] for k in IDS-{'top'}})==len(IDS)-1)
    for key in RECTS|PAIRS|INSETS:
        need(type(value[key]) is list and len(value[key])==(2 if key in PAIRS else 4) and all(number(v,-1e6,1e6) for v in value[key]))
        if key in RECTS:need(value[key][2]>0 and value[key][3]>0)
        if key=='scrollSize':need(all(v>=0 for v in value[key]))
        if key=='safeInsets':need(all(v>=0 for v in value[key]))
    need(type(value['responders']) is list and len(value['responders'])<=1024)
    for row in value['responders']:identifier(row)
    need(len(set(value['responders']))==len(value['responders']))
    need(type(value['recognizers']) is list and len(value['recognizers'])<=1024);ids=set()
    for row in value['recognizers']:
        exact(row,{'id','view','state','enabled'});identifier(row['id']);identifier(row['view'])
        need(row['id'] not in ids and integer(row['state'],0,5) and type(row['enabled']) is bool);ids.add(row['id'])
    return value


def current(value):
    original(value)
    need(value['applicationState']==value['sceneActivationState']==0 and value['interfaceOrientation'] in (1,2,3,4)
        and value['top']==value['presentation'] and value['alpha']>0
        and all(value[k] for k in ('keyWindow','mainScreen','viewWindowMatches','presentationWindowMatches','presented','topMatches','viewInController','interactionEnabled'))
        and not any(value[k] for k in ('beingPresented','beingDismissed','hidden')))
    return value


def inactive_gestures(value):
    """Current gesture/scroll state only; this does not prove UITouch death."""
    current(value);need(not any(value[k] for k in ('dragging','decelerating','tracking','zooming'))
        and all(row['state'] not in (1,2) for row in value['recognizers']));return value


def point(value,document,element):
    """Map an actual visible CSS element through original native screen space."""
    current(value);need(element['visible'] and element['enabled'])
    viewport=document['visualViewport'];left,top,right,bottom=element['rect']
    need(viewport['offsetLeft']<=left<right<=viewport['offsetLeft']+viewport['width']
        and viewport['offsetTop']<=top<bottom<=viewport['offsetTop']+viewport['height'])
    frame=value['screenFrame'];scale=frame[2]/viewport['width'];need(number(scale,.01,100))
    # Uniform CSS-to-UIKit projection; keyboard-reduced visualViewport must fit
    # the actual WK frame. Caller separately excludes original keyboard overlap.
    need(viewport['height']*scale<=frame[3]+1)
    x=frame[0]+((left+right)/2-viewport['offsetLeft'])*scale
    y=frame[1]+((top+bottom)/2-viewport['offsetTop'])*scale
    screen=value['screenCoordinates'];need(screen[0]<=x<screen[0]+screen[2] and screen[1]<=y<screen[1]+screen[3]
        and frame[0]<=x<frame[0]+frame[2] and frame[1]<=y<frame[1]+frame[3]);return [x,y]
