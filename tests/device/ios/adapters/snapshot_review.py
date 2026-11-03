"""Original visible Snapshot preview metadata and independent screen pixels.

No metadata/status/URL alone establishes rendering. Pixel comparison consumes
the actual retained Snapshot PNG and a separately stored WDA screen PNG. This
is not Actor/scene agreement, a fresh acquisition, cleanup or whole admission.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
import hashlib
import re
from urllib.parse import urlsplit
from PIL import Image,ImageChops,ImageStat
from adapters.native_feature_observation import exact,integer,need,number
from adapters.script_feature.history import same
from adapters.original_screen_images import pixels,capture_record

VERSION=1
FILE=re.compile(r'parity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)-snap_[0-9]{1,20}_[0-9]{1,10}\.(png|jpg|jpeg|webp|gif)')
UUID=re.compile('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def inventory(value):
    exact(value,{'iosSnapshotReviewInventoryVersion','complete','roots'})
    need(type(value['iosSnapshotReviewInventoryVersion']) is int and value['iosSnapshotReviewInventoryVersion']==VERSION
        and type(value['complete']) is bool and type(value['roots']) is list and len(value['roots'])<=8)
    identities=set()
    for root in value['roots']:
        exact(root,{'rootIdentity','qmlSource','visible','capturing','processing','statusError','imageCount','images'})
        need(type(root['rootIdentity']) is str and UUID.fullmatch(root['rootIdentity']) and root['rootIdentity'] not in identities)
        identities.add(root['rootIdentity'])
        need(type(root['qmlSource']) is str and len(root['qmlSource'])<=4096)
        source=urlsplit(root['qmlSource'])
        need(source.scheme in ('file','qrc')
            and not source.netloc and not source.query and not source.fragment
            and source.path.endswith('/system/snapshot/NativeSnapshotReview.qml'))
        need(all(type(root[key]) is bool for key in ('visible','capturing','processing','statusError'))
            and integer(root['imageCount'],0,8) and type(root['images']) is list and len(root['images'])<=8)
        if value['complete']:need(len(root['images'])==root['imageCount'])
        rows=set()
        for image in root['images']:
            exact(image,{'objectIdentity','row','fileOwned','fileName','status','visible','sourceSize','paintedBounds',
                'centerAligned','preserveAspectFit','unclipped','axisAligned','systemBlocked','window'})
            need(type(image['objectIdentity']) is str and UUID.fullmatch(image['objectIdentity'])
                and image['objectIdentity'] not in identities and integer(image['row'],0,7) and image['row'] not in rows)
            identities.add(image['objectIdentity']);rows.add(image['row'])
            need(all(type(image[key]) is bool for key in ('fileOwned','visible','centerAligned','preserveAspectFit','unclipped','axisAligned','systemBlocked'))
                and integer(image['status'],0,3) and type(image['fileName']) is str)
            need(FILE.fullmatch(image['fileName']) if image['fileOwned'] else image['fileName']=='')
            size=image['sourceSize'];bounds=image['paintedBounds'];window=image['window']
            need(type(size) is list and len(size)==2 and all(integer(v,0,4096) for v in size)
                and type(bounds) is list and len(bounds)==4 and all(number(v,-32768,32768) for v in bounds)
                and bounds[2]>=0 and bounds[3]>=0)
            exact(window,{'width','height','x','y','devicePixelRatio'})
            need(all(integer(window[key],1,8192) for key in ('width','height'))
                and all(integer(window[key],-32768,32768) for key in ('x','y'))
                and number(window['devicePixelRatio'],0.25,8))
    return value


def selected(value,name):
    inventory(value);need(value['complete'] and type(name) is str and FILE.fullmatch(name))
    visible=[root for root in value['roots'] if root['visible']]
    need(len(visible)==1);root=visible[0]
    need(not root['capturing'] and not root['processing'] and not root['statusError'])
    found=[image for image in root['images'] if image['visible'] and image['fileOwned'] and image['fileName']==name]
    need(len(found)==1);image=found[0]
    need(image['status']==1 and all(image[key] for key in ('centerAligned','preserveAspectFit','unclipped','axisAligned'))
        and not image['systemBlocked'] and all(v>0 for v in image['sourceSize']))
    x,y,width,height=image['paintedBounds'];window=image['window']
    need(width>=64 and height>=64 and x>=0 and y>=0 and x+width<=window['width'] and y+height<=window['height'])
    return root,image


def compare(original_png,screen_png,image):
    """Fixed preview profile; tolerance is never selected by requested effects."""
    pixels(original_png);extent=pixels(screen_png)
    window=image['window'];ratio=window['devicePixelRatio']
    # This first profile admits only a full, unoffset Qt window in the actual
    # screen. Other viewport/safe-area transforms need separate measured data.
    need(window['x']==window['y']==0 and all(abs(extent[i]-window[key]*ratio)<=0.01 for i,key in enumerate(('width','height'))))
    x,y,width,height=image['paintedBounds']
    bounds=tuple(round(v*ratio) for v in (x,y,x+width,y+height))
    need(0<=bounds[0]<bounds[2]<=extent[0] and 0<=bounds[1]<bounds[3]<=extent[1]
        and bounds[2]-bounds[0]>=128 and bounds[3]-bounds[1]>=128)
    with Image.open(BytesIO(original_png)) as source,Image.open(BytesIO(screen_png)) as screen:
        source.load();screen.load()
        if source.mode=='RGBA':need(source.getextrema()[3]==(255,255))
        source=source.convert('RGB');actual=screen.crop(bounds).convert('RGB')
        # Downsample both independently decoded images to preserve broad scene
        # structure while limiting subpixel interpolation/colour differences.
        target=(128,128)
        expected=source.resize(target,Image.Resampling.BILINEAR)
        measured=actual.resize(target,Image.Resampling.BILINEAR)
        need(max(ImageStat.Stat(expected).stddev)>=8)
        delta=ImageChops.difference(expected,measured)
        channel_mean=ImageStat.Stat(delta).mean
        maximum=ImageChops.lighter(ImageChops.lighter(*delta.split()[:2]),delta.split()[2])
        histogram=maximum.histogram();fraction=sum(histogram[:25])/(128*128)
        need(max(channel_mean)<=8 and fraction>=0.95)
        return dict(snapshotPreviewPixelsVersion=VERSION,comparisonExtent=list(target),screenBounds=list(bounds),
            meanChannelDifference=channel_mean,within24Fraction=fraction,
            originalSha256=hashlib.sha256(original_png).hexdigest(),screenSha256=hashlib.sha256(screen_png).hexdigest())


def joined(before,after,screen_record,original_png,screen_png,name,pid):
    """Derive only the supplied originals; an acquiring owner must retain them."""
    from ios.adapters.normal_input import observation
    need(type(name) is str and name.endswith('.png'))
    observation(before,pid,before['sampleEpochMs']);observation(after,pid,after['sampleEpochMs'])
    root,image=selected(before['snapshotReviewInventory'],name)
    last_root,last=selected(after['snapshotReviewInventory'],name)
    need(same(root,last_root) and same(image,last) and before['instance']==after['instance']
        and before['lastSequence']==after['lastSequence'] and before['elapsedMs']<=after['elapsedMs'])
    capture_record(screen_record,screen_png)
    need(screen_record['processId']==pid and before['sampleEpochMs']<=screen_record['nativeBeforeMs']
        <=screen_record['nativeAfterMs']<=after['sampleEpochMs']
        and after['sampleEpochMs']-before['sampleEpochMs']<1500)
    need(pixels(original_png)==image['sourceSize'])
    width,height=image['paintedBounds'][2:]
    source_width,source_height=image['sourceSize']
    need(abs(width/height-source_width/source_height)<=0.01)
    result=compare(original_png,screen_png,image)
    return dict(snapshotRenderedReviewJoinVersion=VERSION,rootIdentity=root['rootIdentity'],objectIdentity=image['objectIdentity'],
        fileName=name,pixels=result,originalUIAndScreenOwnershipRequired=True,
        originalCaptureCompletionRequired=True,independentActorAndSceneRequired=True,wholeFeatureRequired=True)
