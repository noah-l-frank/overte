"""Coherent native disposition models around actual generated host JS output."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from ios.adapters import tablet_web_state as state
from ios.self_tests.tablet_web_echo_fixture import fixture
from ios.self_tests.test_ios_tablet_web_app_origin import originals_boundary,EPOCH
from ios.self_tests.test_ios_tablet_web_sources import stamp,RUN,ROOT


def frame():
    value,_=fixture();owner,files,scripts,buttons,controls,_=originals_boundary()
    app=dict(owner=owner,files=files,scripts=scripts,buttons=buttons,controls=controls,afterEpochMs=EPOCH)
    sources=value['sources']
    # The HTTP-only native model has never created an inline carrier. Do not
    # copy the source DTO boundary fixture's independently live inline example
    # into this actual HTTP history and pretend its positive grant is absent.
    sources['carriers']=[];sources['navigations']=[row for row in sources['navigations'] if row['kind']=='http']
    def epoch_shift(node):
        if type(node) is dict:
            if set(node)=={'epochMs','monotonicMs'}:node['epochMs']+=EPOCH-89800
            else:
                for child in node.values():epoch_shift(child)
        elif type(node) is list:
            for child in node:epoch_shift(child)
    # These are explicit modeled native clocks. Actual Node JS bytes/times
    # remain untouched; the app assignment precedes its modeled navigation.
    epoch_shift(sources)
    for index,event in enumerate(value['ledger']['events'][:6],1):event['clock']=stamp(EPOCH+500+index)
    document=value['document'];document['source']['nativeFinishedEpochMs']=EPOCH+505
    uikit=value['touches'];uikit['installation']=stamp(EPOCH)
    for row in uikit['objects']:
        if row['kind'] in ('view','window'):row['born']=stamp(EPOCH+501)
    for row in uikit['targets']:row['bound']=stamp(EPOCH+503)
    for row in uikit['contacts']:row['source']['bound']=stamp(EPOCH+503)
    for row in uikit['dispatches']:
        for phase in row['phases']:phase['source']['bound']=stamp(EPOCH+503)
    end=document['clockAfter']['epochMs'];view=document['source']['nativeView']
    flags=dict({key:False for key in state.FLAGS},generation=view['grant'])
    for key in ('active','viewPresent','presentationPresent','presentationAttached','windowPresent','sourceCurrent'):flags[key]=True
    native_state=dict(iosTabletWebStateVersion=1,commandId='ios-'+'6'*32,runId=RUN,fixtureUrl=ROOT,instance='7'*32,sequence=1,processId=31,
        clockDomain='native-main-ios-tablet-web-state',clockBefore=stamp(end),clockAfter=stamp(end),complete=True,uikitInstance=uikit['instance'],otherLiveTablets=0,
        owners=[dict(id='8'*32,handle=view['handle'],source=deepcopy(view['source']),firstObserved=stamp(EPOCH+501),expired=None,alive=True,current=flags)],
        targets=[dict(source=deepcopy(uikit['targets'][0]),kind='wk',alive=True,windowAttached=True,superviewPresent=True,subtreeResponder=False)])
    deferred=dict(iosTabletWebDeferredVersion=1,commandId='ios-'+'9'*32,runId=RUN,fixtureUrl=ROOT,instance='a'*32,sequence=1,processId=31,
        clockDomain='native-main-ios-tablet-web-deferred',clockBefore=stamp(end),clockAfter=stamp(end),complete=True,failure=None,commandSequence=0,records=[],commands=[])
    browser=dict(browserFixtureVersion=1,instance='b'*32,ready=True,sequence=1,responses=[dict(sequence=1,responseId=document['source']['http']['responseId'],capturedEpochMs=EPOCH+490,
        ticket='b'*32,resource='reference.html',origin='primary',status=200,bytes=2345,sha256='c'*64)])
    value.pop('profile');value.pop('locations')
    closures=dict(iosTabletWebClosuresVersion=1,commandId='ios-'+'c'*32,runId=RUN,fixtureUrl=ROOT,instance='d'*32,
        sequence=1,processId=31,capturedEpochMs=end,complete=True,contexts=[])
    return dict(value,buttons=deepcopy(buttons),state=native_state,deferred=deferred,browser=browser,closures=closures),app


def close(before):
    value=deepcopy(before);end=before['document']['clockAfter']['epochMs']+100
    ledger=value['ledger'];event=deepcopy(ledger['events'][-1]);sequence=ledger['eventSequence']+1
    event.update(sequence=sequence,eventId=format(sequence,'032x'),kind='view-teardown',clock=stamp(end),detail={});ledger['events'].append(event)
    ledger.update(commandId='ios-'+'d'*32,sequence=ledger['sequence']+1,eventSequence=sequence,clockBefore=stamp(end+10),clockAfter=stamp(end+10))
    document=value['document'];document.update(commandId='ios-'+'e'*32,sequence=document['sequence']+1,clockBefore=stamp(end+20),clockAfter=stamp(end+20),status='unavailable',source={})
    native=value['state'];native.update(commandId='ios-'+'f'*32,sequence=native['sequence']+1,clockBefore=stamp(end+30),clockAfter=stamp(end+30))
    native['owners'][0]['current']=dict({key:False for key in state.FLAGS},generation=0)
    native['targets'][0]['windowAttached']=False
    return value
