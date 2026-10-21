"""Passive Phone avatar resource bytes and actual perspective preference/boom.

This never loads an avatar, changes a preference or supplies a render verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_avatar_render import _OriginalQuery,envelope,nonce,EMPTY_SHA256
from adapters.native_feature_observation import exact,integer,need,number
from adapters.world_render_evidence import digest

VERSION=1
FILE='phone-avatar-configuration.json'
RESOURCE_LIMIT=4*1024*1024
CONFIGURED='meshes/defaultAvatar_full.fst'
LOADED='meshes/mannequin/mannequin.fbx'


def command(value):
    exact(value,{'schemaVersion','commandId','action'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and nonce(value['commandId'])
        and value['action']=='phone-avatar-configuration-observe')
    return value


def url_source(value,path):
    exact(value,{'present','urlSha256','bundledResource'})
    need(type(value['present']) is bool and digest(value['urlSha256'])
        and (value['present'] or value['urlSha256']==EMPTY_SHA256))
    resource=value['bundledResource']
    if resource is not None:
        exact(resource,{'resourcePath','bytes','sha256'})
        need(value['present'] and resource['resourcePath']==path and integer(resource['bytes'],1,RESOURCE_LIMIT)
            and digest(resource['sha256']))


def validate(value,request,pid,epoch):
    command(request);envelope(value,request,pid,epoch)
    source=value['source']
    exact(source,{'phoneAvatarConfigurationVersion','modelInstance','rigId','configured','loadedGeometry','boomLength','pinchZoomEnabled'})
    need(type(source['phoneAvatarConfigurationVersion']) is int and source['phoneAvatarConfigurationVersion']==VERSION
        and nonce(source['modelInstance']) and integer(source['rigId'],0,2147483647)
        and number(source['boomLength'],.5,25) and type(source['pinchZoomEnabled']) is bool)
    url_source(source['configured'],CONFIGURED)
    geometry=source['loadedGeometry']
    if geometry is not None:
        exact(geometry,{'instance','source'});need(nonce(geometry['instance']));url_source(geometry['source'],LOADED)
    return value


def controlled(value,avatar):
    """Join separately observed loaded identity to actual pinned APK bytes.

    Configured URLs and original HFM URLs keep their exact raw URL hashes. Only
    native resource lookup normalizes qrc path aliases. No expected hash is sent
    to the client, and no raw account/avatar URL leaves the private transport.
    """
    from adapters.native_avatar_render import validate as avatar_validate
    from feature_journeys.fixtures import pinned_resource
    import hashlib
    request=dict(schemaVersion=1,commandId=value.get('requestId'),action='phone-avatar-configuration-observe')
    validate(value,request,value.get('processId'),value.get('capturedEpochMs'))
    avatar_validate(avatar,dict(schemaVersion=1,commandId=avatar.get('requestId'),action='feature-avatar-render-observe'),
        value['processId'],avatar.get('capturedEpochMs'))
    source,render=value['source'],avatar['source']
    need(value['instance']==avatar['instance'] and source['modelInstance']==render['modelInstance']
        and source['rigId']==render['rigId'] and source['loadedGeometry'] is not None and render['geometry'] is not None)
    geometry=source['loadedGeometry'];actual=geometry['source']
    need(geometry['instance']==render['geometry']['instance'] and actual['present']==render['geometry']['sourcePresent']
        and actual['urlSha256']==render['geometry']['sourceSha256'])
    for original,name in ((source['configured'],'avatar-a.fst'),(actual,'mannequin/mannequin.fbx')):
        data=pinned_resource(name);resource=original['bundledResource']
        need(resource is not None and original['present'] and resource['bytes']==len(data)
            and resource['sha256']==hashlib.sha256(data).hexdigest())
    return deepcopy(source)


class NativePhoneAvatarConfiguration(_OriginalQuery):
    def read(self):
        need(self.ios is False)
        return self._read(command(self._request('phone-avatar-configuration-observe')),validate)

    def restore(self,frames):
        need(self.ios is False and self.last is None and type(frames) is list and 0<len(frames)<=256)
        for frame in frames:
            request=command(dict(schemaVersion=1,commandId=frame.get('requestId'),action='phone-avatar-configuration-observe'))
            validate(frame,request,self.pid,frame.get('capturedEpochMs'));self._advance(frame);self.last=deepcopy(frame)
