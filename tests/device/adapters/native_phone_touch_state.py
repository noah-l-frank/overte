"""Actual Phone virtual-pad contact and drive-key inventory, never an input ACK."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_avatar_render import _OriginalQuery,envelope,nonce
from adapters.native_feature_observation import exact,integer,need,number

VERSION=1
FILE='phone-touch-state.json'


def command(value):
    exact(value,{'schemaVersion','commandId','action'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and nonce(value['commandId'])
        and value['action']=='phone-touch-state-observe')
    return value


def validate(value,request,pid,epoch):
    command(request);envelope(value,request,pid,epoch);source=value['source']
    exact(source,{'phoneTouchStateVersion','pluginActive','eventPointCount','moveContact','viewContact','buttonContacts',
        'unusedContacts','axes','pressedButtons','pendingPinchIn','pendingPinchOut','lastPinchScale'})
    need(type(source['phoneTouchStateVersion']) is int and source['phoneTouchStateVersion']==VERSION
        and all(type(source[key]) is bool for key in ('pluginActive','moveContact','viewContact'))
        and all(integer(source[key],0,32) for key in ('eventPointCount','buttonContacts','unusedContacts'))
        and all(number(source[key],0,1e6) for key in ('pendingPinchIn','pendingPinchOut','lastPinchScale')))
    axes=source['axes'];need(type(axes) is list and len(axes)<=6)
    for row in axes:
        exact(row,{'channel','value'});need(integer(row['channel'],0,5) and number(row['value'],-1e6,1e6))
    need(len({row['channel'] for row in axes})==len(axes))
    buttons=source['pressedButtons'];need(type(buttons) is list and len(buttons)<=2
        and all(integer(button,0,1) for button in buttons) and len(set(buttons))==len(buttons))
    return value


def released(value):
    validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action='phone-touch-state-observe'),
        value.get('processId'),value.get('capturedEpochMs'))
    source=value['source'];need(source['pluginActive'] is True and not source['moveContact'] and not source['viewContact']
        and all(source[key]==0 for key in ('eventPointCount','buttonContacts','unusedContacts','pendingPinchIn','pendingPinchOut','lastPinchScale'))
        and source['pressedButtons']==[] and all(row['value']==0 for row in source['axes']))
    return deepcopy(source)


class NativePhoneTouchState(_OriginalQuery):
    def read(self):
        need(self.ios is False);return self._read(command(self._request('phone-touch-state-observe')),validate)

    def restore(self,frames):
        need(self.ios is False and self.last is None and type(frames) is list and 0<len(frames)<=256)
        for frame in frames:
            validate(frame,dict(schemaVersion=1,commandId=frame.get('requestId'),action='phone-touch-state-observe'),
                self.pid,frame.get('capturedEpochMs'));self._advance(frame);self.last=deepcopy(frame)
