"""Explicit Actor scene-original commitments, never Snapshot UI/output facts.

This family shares the canonical owned-observer endpoint and sequence journal.
The independent publisher replays its actual originals before deriving these
commitments. The fixture validates syntax/ownership labels, not device truth.
"""
from .contract import exact,identifier,number
import re

PROFILE='held-actor-opengl-png-v1'
FIELDS={'snapshotActorPixelSampleVersion','profile','binding','role','witnessIndex',
    'witnessOwnerSha256','packetOwnerSha256','nativeOriginalSha256',
    'phaseBeforeSha256','phaseAfterSha256','frame','png','resource'}

def sha(value):
    if type(value)is not str or re.fullmatch('[0-9a-f]{64}',value)is None:raise ValueError('Invalid scene-original digest')

def facts(value,*,captured):
    exact(value,FIELDS,'independent Snapshot scene sample')
    if type(value['snapshotActorPixelSampleVersion'])is not int or value['snapshotActorPixelSampleVersion']!=1 or value['profile']!=PROFILE or value['role']!='actor':
        raise ValueError('Unsupported independent Snapshot scene family')
    from adapters.normal_feature_state import context
    binding=context(value['binding'])
    if type(value['witnessIndex'])is not int or not 1<=value['witnessIndex']<=8:raise ValueError('Invalid original Actor witness index')
    for key in('witnessOwnerSha256','packetOwnerSha256','nativeOriginalSha256','phaseBeforeSha256','phaseAfterSha256'):sha(value[key])
    frame=value['frame'];exact(frame,{'frameInstance','frameIndex','processId','recordedEpochMs','consumedEpochMs','viewport','sceneSha256','cameraSha256','worldFromCameraSha256'},'original Actor frame commitments')
    identifier(frame['frameInstance'])
    if (type(frame['frameIndex'])is not int or not 1<=frame['frameIndex']<=2**32-1 or type(frame['processId'])is not int or frame['processId']<1
            or binding['processIdentity']!=str(frame['processId'])):raise ValueError('Original Actor process/frame mismatch')
    if type(frame['recordedEpochMs'])is not int or type(frame['consumedEpochMs'])is not int:raise ValueError('Original frame clocks must retain integer native epochs')
    number(frame['recordedEpochMs'],1);number(frame['consumedEpochMs'],frame['recordedEpochMs'],captured+250)
    viewport=frame['viewport']
    if type(viewport)is not list or len(viewport)!=4 or any(type(n)is not int for n in viewport)or any(not 0<=n<=8192 for n in viewport[:2])or any(not 1<=n<=8192 for n in viewport[2:]):
        raise ValueError('Invalid original Actor viewport')
    for key in('sceneSha256','cameraSha256','worldFromCameraSha256'):sha(frame[key])
    png=value['png'];exact(png,{'bytes','sha256','pixelSha256','imageExtent','sourceExtent','rectBottomLeft','readEpochMs','callbackEpochMs'},'original Actor PNG commitments')
    if type(png['bytes'])is not int or not 1<=png['bytes']<=64*1024:raise ValueError('Invalid bounded original PNG')
    sha(png['sha256']);sha(png['pixelSha256'])
    for key in('sourceExtent','imageExtent'):
        if type(png[key])is not list or len(png[key])!=2 or any(type(n)is not int or not 1<=n<=8192 for n in png[key]):raise ValueError('Invalid original image extent')
    if png['sourceExtent']!=png['imageExtent']or png['rectBottomLeft']!=[0,0,*png['imageExtent']]:raise ValueError('Actor PNG must retain its actual full crop')
    if type(png['readEpochMs'])is not int or type(png['callbackEpochMs'])is not int:raise ValueError('Original readback clocks must remain integer')
    number(png['readEpochMs'],frame['consumedEpochMs'],png['callbackEpochMs']);number(png['callbackEpochMs'],png['readEpochMs'],captured+250)
    resource=value['resource'];exact(resource,{'callbackScopeRetired','retainedQImage','nativeSlotProcessLifetime'},'original Actor callback lifetime')
    if resource['callbackScopeRetired']is not True or resource['retainedQImage']is not False or resource['nativeSlotProcessLifetime']is not True:raise ValueError('Actor callback resource original incomplete')
    return value
