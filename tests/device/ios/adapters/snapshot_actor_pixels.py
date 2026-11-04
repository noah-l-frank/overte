"""Bounded original PNG of one actual independently consumed Actor frame.

No WDA image, Primary capture or wanted Scene/camera is accepted as pixels.
Native C++ is opt-in/uncompiled; host models do not prove physical rendering.
"""
from copy import deepcopy
import base64,hashlib,json
from io import BytesIO
from PIL import Image
from adapters.native_feature_observation import exact,integer,need,number,fresh
from adapters.script_feature.history import same
from ios.adapters import snapshot_captures,snapshot_scene,snapshot_provenance
from ios.adapters.places_model import IOSPlacesModel
ACTION='feature-ios-snapshot-actor-pixels'
FILE=ACTION+'.json'
LIMIT=262144
PNG_LIMIT=64*1024
PROFILE='held-actor-opengl-png-v1'
BINDING_KEYS=('frameInstance','frameIndex','processId','camera','worldFromCamera','viewport','transformSlot')

def command(value):
    previous=deepcopy(value);previous['action']=snapshot_captures.ACTION;snapshot_captures.command(previous)
    need(value['action']==ACTION);return value

def pixels(source,pid,epoch):
    exact(source,{'complete','frame','png','resource'});need(source['complete']is True)
    frame=source['frame'];need(type(frame)is dict)
    # Exact projection of the same retained native packet, never a new frame or
    # a camera/clock supplied by a caller. Original fields remain in the owner.
    projected={key:deepcopy(value)for key,value in frame.items()if key!='consumedEpochMs'}
    snapshot_provenance.frame(projected,pid,epoch)
    need(frame['snapshotFrameProvenanceVersion']==2)
    need(integer(frame['consumedEpochMs'],frame['recordedEpochMs'],frame['readback']['readEpochMs']))
    resource=source['resource'];exact(resource,{'profile','callbackScopeRetired','retainedQImage','nativeSlotProcessLifetime'})
    need(resource['profile']=='single-latest-actor-frame-v1'and resource['callbackScopeRetired']is True and resource['retainedQImage']is False and resource['nativeSlotProcessLifetime']is True)
    png=source['png'];exact(png,{'format','encoding','bytes','sha256','data','frameBinding'})
    need(png['format']=='png'and png['encoding']=='base64'and integer(png['bytes'],1,PNG_LIMIT)
        and type(png['data'])is str and len(png['data'])<=4*((PNG_LIMIT+2)//3))
    binding=png['frameBinding'];exact(binding,set(BINDING_KEYS));need(same(binding,{key:frame[key]for key in BINDING_KEYS}))
    try:raw=base64.b64decode(png['data'],validate=True)
    except(ValueError,TypeError):need(False)
    need(len(raw)==png['bytes']and hashlib.sha256(raw).hexdigest()==png['sha256']
        and raw[:8]==bytes((137,80,78,71,13,10,26,10))and raw[-8:-4]==b'IEND')
    with Image.open(BytesIO(raw))as image:
        need(image.format=='PNG'and image.mode in('RGB','RGBA')and image.size==tuple(frame['readback']['imageExtent'])
            and integer(image.width,1,8192)and integer(image.height,1,8192)and image.width*image.height<=8388608)
        image.load();rgba=image.convert('RGBA').tobytes()
    need(hashlib.sha256(rgba).hexdigest()==frame['readback']['pixelSha256'])
    # The instrument observes the real full ordinary composite readback. It
    # never requests an expected crop or downsamples to fit the byte bound.
    read=frame['readback'];need(read['rectBottomLeft']==[0,0,*read['imageExtent']]and read['sourceExtent']==read['imageExtent'])
    return raw

def validate(value,query,pid,epoch=None,previous=None):
    command(query)
    exact(value,{'iosSnapshotActorPixelsVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosSnapshotActorPixelsVersion'])is int and value['iosSnapshotActorPixelsVersion']==1
        and value['requestId']==query['commandId']and value['runId']==query['runId']and integer(pid,1)
        and type(value['processId'])is int and value['processId']==pid and integer(value['sequence'],1,1000000000)
        and value['clockDomain']=='native-main-snapshot-actor-pixels')
    snapshot_captures.identity(value['instance'])
    for clock in(value['clockBefore'],value['clockAfter']):
        exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1)and integer(clock['monotonicMs']))
    before,after=value['clockBefore'],value['clockAfter'];elapsed=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=elapsed<1500 and 0<=mono<1500 and abs(elapsed-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    pixels(value['source'],pid,before['epochMs'])
    frame=value['source']['frame'];need(0<=after['epochMs']-frame['consumedEpochMs']<1500)
    need(len(json.dumps(value,allow_nan=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance']and value['sequence']>previous['sequence']and value['requestId']!=previous['requestId']
            and all(before[key]>=previous['clockAfter'][key]for key in before))
        old=previous['source']['frame']
        if frame['frameInstance']==old['frameInstance']:need(same(value['source'],previous['source']))
        else:need(frame['frameIndex']>old['frameIndex']and frame['recordedEpochMs']>=old['recordedEpochMs'])
    return value

def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))

class IOSSnapshotActorPixels(IOSPlacesModel):
    _limit=LIMIT;_action=ACTION;_command=staticmethod(command);_validate=staticmethod(validate)
    _acquisition_key='iosSnapshotActorPixelsAcquisitionVersion'
