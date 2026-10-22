"""Modeled UIKit/native envelope around actual original DOM JavaScript output."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
from ios.adapters import tablet_web_dom as dom
from ios.adapters import tablet_web_presentation as presentation
from ios.self_tests.test_ios_tablet_web_sources import packet as sources,stamp,RUN,ROOT
from ios.self_tests.test_ios_tablet_web_source import packet as transcript

REPO=Path(__file__).resolve().parents[4]


def query(index=1):return dict(schemaVersion=1,action=dom.ACTION,commandId='ios-'+format(index,'032x'),runId=RUN,fixtureUrl=ROOT)


def original_bodies():
    program="const p=require('./tests/device/ios/self_tests/test_ios_tablet_web_dom.js').page;let result=[];for(const inline of [false,true]){const page=p({inline,inlineToken:'6'.repeat(32)});result.push([page.read('ios-'+(1).toString(16).padStart(32,'0')),page.read('ios-'+(2).toString(16).padStart(32,'0'))]);}process.stdout.write(JSON.stringify(result));"
    out=subprocess.run(['node','-e',program],cwd=REPO,capture_output=True,text=True,timeout=5)
    if out.returncode:raise AssertionError(out.stderr)
    return json.loads(out.stdout)


def shown():
    value={key:False for key in presentation.FLAGS}
    for key in ('keyWindow','mainScreen','viewWindowMatches','presentationWindowMatches','presented','topMatches','viewInController','interactionEnabled'):value[key]=True
    for index,key in enumerate(sorted(presentation.IDS-{'top'}),1):value[key]=format(index,'032x')
    value['top']=value['presentation'];value.update(tabletPresentationVersion=1,applicationState=0,sceneActivationState=0,interfaceOrientation=1,
        alpha=1.,screenScale=2.,zoomScale=1.,responders=[],recognizers=[dict(id='9'*32,view=value['view'],state=0,enabled=True)])
    for key in presentation.RECTS:value[key]=[0.,0.,500.,800.]
    value.update(viewBounds=[0.,0.,500.,756.],viewFrame=[0.,44.,500.,756.],screenFrame=[0.,44.,500.,756.],
        nativeScreenBounds=[0.,0.,1000.,1600.],scrollOffset=[0.,100.],scrollSize=[500.,2000.],safeInsets=[0.,0.,0.,34.],scrollInsets=[0.,0.,0.,0.])
    return value


def packet(observed,*,inline=False,index=1):
    view=deepcopy(transcript(inline=inline)['events'][0]['identity']);view['url']=observed['document']['href']
    current=shown();epoch=observed['capturedEpochMs']
    source=dict(nativeView=view,nativeFinishedEpochMs=99000,observerSha256=dom.SOURCE_SHA256,inlineLease=inline,
        http=None if inline else dict(status=200,responseId=observed['document']['responseId'],url=view['url']),
        presentationBefore=current,presentationAfter=deepcopy(current),dom=deepcopy(observed))
    return dict(iosTabletWebDOMNativeVersion=1,commandId=query(index)['commandId'],runId=RUN,fixtureUrl=ROOT,instance='7'*32,sequence=index,
        processId=31,clockDomain='native-main-ios-tablet-web-dom',clockBefore=stamp(epoch),clockAfter=stamp(epoch),status='ready',source=source)
