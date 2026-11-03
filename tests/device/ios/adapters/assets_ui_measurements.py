"""Original Assets UI/window authority joined to actual current screen pixels.

The independent Web marker is ordinary pre-existing rendered fixture content.
It needs no imported Model. Projected geometry is admission only: stale, foreign,
blank or occluded marker pixels cannot qualify. No ACK becomes an image fact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import itertools
import math
from adapters.native_clock_join import validate_join,digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from adapters.graphics_subject_geometry import rotate
from adapters.original_screen_images import capture_record
from feature_journeys.contract import identifier
from feature_journeys.evidence import image_observation,rectangle
from ios.adapters import create_state
from ios.adapters.assets_controls import project as controls
from ios.adapters.assets_tree_controls import project as tree_controls,ROW
from ios.adapters.assets_usage_controls import project as usage_controls
from ios.adapters.create_marker_identity import marker
from ios.adapters.graphics_history import follow_native
from ios.adapters.native_geometry import validate as geometry_original
from ios.adapters.normal_input import observation

VERSION=1


def frame(value,binding,run,page,subject,checkpoint):
    exact(value,{'assetsUiSourceFrameVersion','ui','uiFrame','create','geometry','clockJoin'})
    need(type(value['assetsUiSourceFrameVersion']) is int and value['assetsUiSourceFrameVersion']==VERSION
        and checkpoint in ('browse','baking-on'))
    ui=value['ui'];pid=int(context(binding)['processIdentity']);projected=controls(ui)
    need(ui['processId']==pid and ui['ready'] and ui['tabletShown'])
    parts=dict(ui=ui,create=value['create'],geometry=value['geometry']['observation'])
    clock=validate_join(value['clockJoin'],parts);need(clock['nativeBefore']['processId']==pid)
    observation(ui,pid,clock['nativeAfter']['capturedEpochMs'])
    original=value['uiFrame'];exact(original,{'hostBefore','hostAfter','queries','clocks','ui','uiReceipt'})
    need(same(original['ui'],ui) and same(original['uiReceipt']['observation'],ui))
    roots=[row for row in projected['inventory']['roots'] if row['rootId']==page and row['role']=='page' and row['alive']]
    need(len(roots)==1 and roots[0]['visible'] and roots[0]['windowId'] is not None
        and not roots[0]['busy'] and not roots[0]['pendingBundle'] and not roots[0]['destinationOpen'])
    need(not any(row['alive'] and row['visible'] and row['role']=='picker' for row in projected['inventory']['roots']))
    tree=tree_controls(ui,page);usage=usage_controls(ui,page)
    need(not tree['renameVisible'] and not tree['deleteVisible'] and not usage['model']['visible'])
    rows=[row for row in projected['controls'] if row['id']==subject];need(len(rows)==1);row=rows[0]
    need(row['assetControl']['rootId']==page and row['assetControl']['windowId']==roots[0]['windowId'])
    if checkpoint=='browse':
        need(ROW.fullmatch(subject) is not None and row['assetControl']['row'] is not None
            and row['assetControl']['row']['model']['path'].startswith('/e2e-'+run+'/'))
    else:need(subject=='assets.baking' and usage['baking']['checked'] and usage['baking']['enabled'])
    created=value['create'];create_state.original(created)
    need(created['iosCreateStateVersion']>=3 and created['processId']==pid and created['runId']==run and created['source']['complete']
        and created['source']['tabletShown'] and created['source']['domainId']==usage['domainId']
        and clock['nativeBefore']['capturedEpochMs']<=created['clockBefore']['epochMs']<=created['clockAfter']['epochMs']<=clock['nativeAfter']['capturedEpochMs'])
    geometry=value['geometry'];geometry_original(geometry,geometry['commandId'],native_epoch_ms=clock['nativeAfter']['capturedEpochMs'])
    return dict(root=deepcopy(roots[0]),tree=tree,usage=usage,control=deepcopy(row))


def surface(geometry,extent,view):
    doc=geometry['observation'];native=doc['nativeUi'];window=doc['window'];density=native.get('density')
    need(number(density,1,4) and native.get('keyboardVisible') is False and native.get('imeInsetBottom')==0)
    need(all(abs(a-b*density)<=1 for a,b in zip(extent,[native['surfaceWidth'],native['surfaceHeight']])))
    left,top=native['safeInsetLeft'],native['safeInsetTop']
    width=native['surfaceWidth']-left-native['safeInsetRight'];height=native['surfaceHeight']-top-native['safeInsetBottom']
    need(abs(width-window['width'])<=1 and abs(height-window['height'])<=1
        and abs(width-view['uiWidth'])<=1 and abs(height-view['uiHeight'])<=1
        and abs(view['aspectRatio']-width/height)<=.01 and view['perspective'])
    return left*density,top*density,width*density,height*density,density


def projected(policy,geometry,extent,created,mark,control):
    view=created['source']['view'];left,top,width,height,density=surface(geometry,extent,view)
    f=1/math.tan(math.radians(view['fieldOfViewDegrees'])/2);points=[]
    inverse=[-v for v in view['rotation'][:3]]+[view['rotation'][3]]
    # A Web entity's visible plane is local XY. Its depth is not a card border.
    for x,y in itertools.product((-1,1),repeat=2):
        world=[a+b for a,b in zip(rotate([x*mark['dimensions'][0]/2,y*mark['dimensions'][1]/2,0],mark['rotation']),mark['position'])]
        cx,cy,cz=rotate([a-b for a,b in zip(world,view['position'])],inverse);need(cz<0)
        nx,ny=cx*f/(-cz*view['aspectRatio']),cy*f/-cz
        need(-1<=nx<=1 and -1<=ny<=1);points.append((left+(nx+1)*width/2,top+(1-ny)*height/2))
    box=[min(v[0] for v in points),min(v[1] for v in points),max(v[0] for v in points),max(v[1] for v in points)]
    exact(policy,{'source','marker','subject'});need(policy['source']=='native-screen')
    rectangle(policy['marker'],extent);rectangle(policy['subject'],extent)
    # Dynamic graphics-marker HTML fills the complete Web plane. The card's
    # immutable 160x40 raster has challenge cells in [4,132] x [4,36].
    w,h=box[2]-box[0],box[3]-box[1]
    interior=[box[0]+w*4/160,box[1]+h*4/40,box[0]+w*132/160,box[1]+h*36/40]
    need(all(abs(actual-wanted)<=1 for actual,wanted in zip(policy['marker'],interior)))
    rect=control['frame'];exact(rect,{'x','y','width','height'})
    subject=[left+rect['x']*density,top+rect['y']*density,left+(rect['x']+rect['width'])*density,top+(rect['y']+rect['height'])*density]
    a,b,c,d=policy['subject'];need(subject[0]<=a<c<=subject[2] and subject[1]<=b<d<=subject[3])
    need(max(a,policy['marker'][0])>=min(c,policy['marker'][2]) or max(b,policy['marker'][1])>=min(d,policy['marker'][3]))
    return dict(marker=interior,subjectControl=subject)


def compose(run,ticket,binding,before,after,capture,raw,policy,marker_identity,*,page,subject,checkpoint,previous=None,changed=False):
    identifier(run);identifier(ticket);exact(marker_identity,{'nonce','sourceUrl','id'});left=frame(before,binding,run,page,subject,checkpoint);right=frame(after,binding,run,page,subject,checkpoint)
    capture_record(capture,raw);first,last=before['clockJoin'],after['clockJoin'];follow_native(first['nativeAfter'],last['nativeBefore'])
    duration=(last['hostAfterMonotonic']-first['hostBeforeMonotonic'])*1000
    need(0<=duration<1500 and 0<=last['hostAfterEpochMs']-first['hostBeforeEpochMs']<1500
        and abs(last['hostAfterEpochMs']-first['hostBeforeEpochMs']-duration)<=250
        and abs(last['nativeAfter']['capturedEpochMs']-first['nativeBefore']['capturedEpochMs']-duration)<=250)
    need(capture['sessionId']==binding['sessionId'] and str(capture['processId'])==binding['processIdentity']
        and first['nativeAfter']['capturedEpochMs']<=capture['nativeBeforeMs']<=capture['nativeAfterMs']<=last['nativeBefore']['capturedEpochMs']
        and first['hostAfterEpochMs']<=capture['hostBeginEpochMs']<=capture['hostEndEpochMs']<=last['hostBeforeEpochMs']
        and first['hostAfterMonotonic']<=capture['hostBeginMonotonic']<=capture['hostEndMonotonic']<=last['hostBeforeMonotonic'])
    # Actual independent UI/control/selection and geometry stay stable across
    # acquisition; inventory read counters themselves must move forwards.
    need(same(left,right) and after['ui']['sampleEpochMs']>=before['ui']['sampleEpochMs']
        and after['ui']['elapsedMs']>=before['ui']['elapsedMs'] and after['ui']['lastSequence']==before['ui']['lastSequence']
        and after['ui']['instance']==before['ui']['instance']
        and all(after['ui'][key]['instance']==before['ui'][key]['instance'] and after['ui'][key]['sequence']>before['ui'][key]['sequence']
            for key in ('assetInventory','assetTreeInventory','assetUsageInventory')) and same(before['geometry']['observation']['nativeUi'],after['geometry']['observation']['nativeUi'])
        and same(before['geometry']['observation']['window'],after['geometry']['observation']['window'])
        and after['geometry']['observation']['sampleSequence']>before['geometry']['observation']['sampleSequence'])
    create_state.validate(after['create'],dict(schemaVersion=1,action=create_state.ACTION,commandId=after['create']['requestId'],runId=run),
        int(binding['processIdentity']),last['nativeAfter']['capturedEpochMs'],before['create'])
    need(same(before['create']['source'],after['create']['source']))
    marks=[marker(value['create'],marker_identity['nonce'],marker_identity['sourceUrl']) for value in (before,after)]
    need(same(marks[0],marks[1]) and marks[0]['id']==marker_identity['id'])
    a=projected(policy,before['geometry'],capture['extent'],before['create'],marks[0],left['control'])
    b=projected(policy,after['geometry'],capture['extent'],after['create'],marks[1],right['control']);need(same(a,b))
    image,pixels=image_observation(raw,run,ticket,policy,previous=previous,changed=changed)
    return dict(assetsUiImageVersion=VERSION,runId=run,ticket=ticket,processId=int(binding['processIdentity']),
        rootId=page,windowId=right['root']['windowId'],checkpoint=checkpoint,subjectControl=subject,
        captureSha256=digest(capture),uiBeforeSha256=digest(before),uiAfterSha256=digest(after),
        projection=a,image=image),pixels
