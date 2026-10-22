"""Original continuous browser/Qt/Java quiet windows; host time alone cannot retire."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need,number
from adapters.native_web_runtime import validate as runtime_packet,continuity as runtime_advance,released
from adapters.pico4.browser_source import validate as browser_packet,continuity as browser_advance

VERSION=1


def frame(value,run,url,owner,pid,*,retired):
    exact(value,{'host','browser','runtime'});need(number(value['host'],0,1e15))
    browser,runtime=value['browser'],value['runtime'];epoch=max(browser['capturedEpochMs'],runtime['capturedEpochMs'])
    browser_packet(browser,dict(schemaVersion=1,commandId=browser['commandId'],action='pico-tablet-web',runId=run,
        fixtureUrl=url,ownerToken=owner,operation='observe'),pid,epoch)
    runtime_packet(runtime,dict(schemaVersion=1,commandId=runtime['commandId'],action='feature-web-runtime-observe',
        runId=run,fixtureUrl=url),pid,epoch,require_renderers=True)
    need(browser['status']==runtime['status']=='ready' and not browser['source']['current']
        and (not retired or browser['source']['retired']))
    source=runtime['source']
    if source['nativeAfter']['knownHandles']:released(runtime,require_renderers=True)
    else:need(not source['nativeBefore']['views'] and not source['nativeAfter']['views']
        and not source['java']['views'] and not source['java']['creations'] and not source['java']['renderers'])
    return [browser['capturedEpochMs'],source['nativeBefore']['capturedEpochMs'],source['java']['capturedEpochMs'],
        source['nativeAfter']['capturedEpochMs']]


def validate(value,run,url,owner,pid,*,retired):
    exact(value,{'browserQuietVersion','frames','complete'})
    need(type(value['browserQuietVersion']) is int and value['browserQuietVersion']==VERSION and type(value['complete']) is bool
        and type(value['frames']) is list and 1<=len(value['frames'])<=64)
    first=previous=None;clocks=None
    for row in value['frames']:
        actual=frame(row,run,url,owner,pid,retired=retired)
        if previous is not None:
            browser_advance(previous['browser'],row['browser']);runtime_advance(previous['runtime'],row['runtime'],pid,url)
            need(0<row['host']-previous['host']<=.5 and all(0<b-a<=500 for a,b in zip(clocks,actual)))
        else:first=(row['host'],actual)
        previous,clocks=row,actual
    complete=len(value['frames'])>=3 and previous['host']-first[0]>=3 and all(b-a>=3000 for a,b in zip(first[1],clocks))
    need(value['complete']==complete);return value


def append(previous,browser,runtime,host,run,url,owner,pid,*,retired):
    value=dict(browserQuietVersion=VERSION,frames=[] if previous is None else deepcopy(previous['frames']),complete=False)
    if previous is not None:validate(previous,run,url,owner,pid,retired=retired)
    value['frames'].append(dict(host=host,browser=deepcopy(browser),runtime=deepcopy(runtime)))
    first,last=value['frames'][0],value['frames'][-1]
    a=frame(first,run,url,owner,pid,retired=retired);b=frame(last,run,url,owner,pid,retired=retired)
    value['complete']=len(value['frames'])>=3 and last['host']-first['host']>=3 and all(y-x>=3000 for x,y in zip(a,b))
    validate(value,run,url,owner,pid,retired=retired);return value
