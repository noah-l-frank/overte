"""One ordinary world touch from original Create/camera/UIKit measurements.

The owner binds a previously admitted actual owned voxel UUID. Input consumes
no setter, Entity service, QML handler or Create bridge, and proves no effect.
An unknown POST remains issued; recovery only releases this owned input route.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time

from adapters.native_clock_join import NativeClockAcquisition, digest, validate_join
from adapters.native_feature_observation import NativeFeatureObservation, exact, need, number
from adapters.native_graphics_subject import entity_id
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUI
from adapters.script_feature.history import pack, unpack, same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import create_state
from ios.adapters.native_geometry import OriginalGeometry, validate as geometry_document
from ios.adapters.normal_input import NativeInput, observation as ui_observation

VERSION = 1


def inverse_rotate(vector, quaternion):
    x, y, z, w = quaternion; x, y, z = -x, -y, -z
    vx, vy, vz = vector
    tx, ty, tz = 2*(y*vz-z*vy), 2*(z*vx-x*vz), 2*(x*vy-y*vx)
    return [vx+w*tx+y*tz-z*ty, vy+w*ty+z*tx-x*tz, vz+w*tz+x*ty-y*tx]


def point(state, geometry, owned_id, editor_id):
    source = create_state.live(state)
    need(state['iosCreateStateVersion'] >= 2 and source['tabletShown'] is False and entity_id(owned_id))
    editors = [row for row in source['roots'] if row['id'] == editor_id]
    need(len(editors) == 1); editor = editors[0]
    need(not editor['destroyed'] and editor['kind'] == 'editor' and not editor['active'] and not editor['numericFocus']
         and editor['page']['selectedIds'] == [owned_id])
    settings = editor['voxelSettings']
    need(settings.get('createAppMode') == 'voxel' and settings.get('voxelEditMode') == 'cube'
         and settings.get('voxelEditDynamics') == 'click' and settings.get('voxelPointerMode') == 'laser'
         and type(settings.get('voxelRemove')) is bool and number(settings.get('voxelSphereSize'), .5, .5))
    rows = [row for row in source['entities'] if row['id'] == owned_id]; need(len(rows) == 1); entity = rows[0]
    need(entity['type'] == 'PolyVox' and entity['hostType'] == 'domain' and entity['visible']
         and not entity['locked'] and entity['voxels']['ready'] and entity['voxels']['onCount'] > 0
         and (source['canRez'] or source['canRezTmp']))
    view = source['view']; need(view['perspective'])
    # The camera and actual entity centre determine the ordinary touch point;
    # no requested entity position, hardcoded screen location or success value.
    relative = inverse_rotate([a-b for a, b in zip(entity['position'], view['position'])], view['rotation'])
    x, y, z = relative; need(z < -.01)
    half = math.tan(math.radians(view['fieldOfViewDegrees'])/2)
    normalized = [x/(-z*half*view['aspectRatio']), y/(-z*half)]
    need(all(number(value, -.8, .8) for value in normalized))
    document, viewport = geometry_document(geometry, geometry['commandId'], native_epoch_ms=state['clockAfter']['epochMs'])
    need(document['nativeUi'].get('keyboardVisible') is False
         and number(document['nativeUi'].get('imeInsetBottom'), 0, 0)
         and abs(document['window']['width']/document['window']['height']-view['aspectRatio']) < .01
         and abs(view['uiWidth']/view['uiHeight']-view['aspectRatio']) < .01)
    return dict(x=viewport['x']+(normalized[0]+1)*viewport['width']/2,
                y=viewport['y']+(1-normalized[1])*viewport['height']/2,
                surfaceWidth=document['nativeUi']['surfaceWidth'], surfaceHeight=document['nativeUi']['surfaceHeight'])


class CreateWorldInput:
    def __init__(self, store, binding, run, ticket, lock, native, state, geometry, normal, ui, guard,
                 *, epoch_ms=lambda: time.time()*1000, monotonic=time.monotonic):
        need(isinstance(store, PrivateFeatureState) and isinstance(lock, ScriptSourceLock)
             and isinstance(native, NativeFeatureObservation) and native.ios
             and isinstance(state, create_state.IOSCreateState) and isinstance(geometry, OriginalGeometry)
             and isinstance(normal, NativeInput) and isinstance(ui, NativeUI) and callable(guard))
        self.store, self.binding, self.run, self.ticket, self.lock = store, deepcopy(context(binding)), identifier(run), identifier(ticket), lock
        self.native, self.source, self.geometry, self.normal, self.ui, self.guard = native, state, geometry, normal, ui, guard
        self.epoch_ms, self.monotonic = epoch_ms, monotonic
        need(str(native.pid) == str(state.pid) == binding['processIdentity']
             and store.path.name == 'ios-create-world-input-'+ticket+'.json')
        lock.assert_held(); self.previous = store.read(); self.state = None if self.previous is None else self.decode(self.previous)

    def envelope(self):
        return dict(iosCreateWorldInputVersion=VERSION, binding=self.binding, runId=self.run,
                    ticket=self.ticket, payload=pack([self.state]))

    def decode(self, value):
        exact(value, {'iosCreateWorldInputVersion', 'binding', 'runId', 'ticket', 'payload'})
        need(type(value['iosCreateWorldInputVersion']) is int and value['iosCreateWorldInputVersion'] == VERSION
             and same(value['binding'], self.binding) and value['runId'] == self.run and value['ticket'] == self.ticket)
        entries = unpack(value['payload']); need(len(entries) == 1); state = entries[0]
        exact(state, {'phase', 'ownedId', 'editorId', 'start', 'end', 'originals', 'clockJoin', 'point', 'body', 'admission', 'releaseObserved'})
        need(state['phase'] in ('reading', 'ready', 'issued', 'released') and entity_id(state['ownedId'])
             and type(state['originals']) is dict and set(state['originals']) <= {'create', 'geometry', 'ui', 'sdkWindow'}
             and type(state['releaseObserved']) is bool)
        if state['phase'] != 'reading': self.proof(state)
        return state

    def save(self):
        self.lock.assert_held(); need(self.guard() is not False and same(self.store.read(), self.previous))
        value = self.envelope(); self.decode(value); self.store.write(value, self.previous)
        need(same(self.store.read(), value)); self.previous = deepcopy(value)

    def remember(self, key, value):
        need(self.state['phase'] == 'reading' and self.state[key] is None)
        self.state[key] = deepcopy(value); self.save()

    def proof(self, state=None):
        state = self.state if state is None else state; originals = state['originals']
        exact(originals, {'create', 'geometry', 'ui', 'sdkWindow'})
        clock = validate_join(state['clockJoin'], originals)
        need(same(state['start'], {key: clock[key] for key in ('clockJoinVersion', 'hostBeforeEpochMs', 'hostBeforeMonotonic', 'nativeBefore')})
             and same(state['end'], {key: clock[key] for key in ('nativeAfter', 'hostAfterEpochMs', 'hostAfterMonotonic')}))
        packet = originals['create']; create_state.original(packet)
        need(packet['runId'] == self.run and packet['processId'] == int(self.binding['processIdentity'])
             and clock['nativeBefore']['processId'] == packet['processId']
             and clock['nativeBefore']['capturedEpochMs'] <= packet['clockBefore']['epochMs']
             <= packet['clockAfter']['epochMs'] <= clock['nativeAfter']['capturedEpochMs']
             and same(clock['nativeBefore']['lifecycle'], clock['nativeAfter']['lifecycle']))
        geometry = originals['geometry']; document, _viewport = geometry_document(geometry, geometry['commandId'],
            native_epoch_ms=clock['nativeAfter']['capturedEpochMs'])
        need(clock['nativeBefore']['capturedEpochMs'] <= document['sampleEpochMs'] <= clock['nativeAfter']['capturedEpochMs'])
        ui_observation(originals['ui'], packet['processId'], clock['nativeAfter']['capturedEpochMs'])
        need(originals['ui']['tabletShown'] is False)
        admission = state['admission']
        create_state.validate(admission, dict(schemaVersion=1, action=create_state.ACTION, commandId=admission['requestId'], runId=self.run),
                              packet['processId'], previous=packet)
        need(same(admission['source'], packet['source']))
        target = point(packet, geometry, state['ownedId'], state['editorId']); need(same(target, state['point']))
        rect = originals['sdkWindow']; exact(rect, {'x', 'y', 'width', 'height'})
        need(all(number(rect[key], -10000, 10000) for key in ('x', 'y'))
             and abs(rect['width']-target['surfaceWidth']) <= 1 and abs(rect['height']-target['surfaceHeight']) <= 1)
        x, y = round(rect['x']+target['x']), round(rect['y']+target['y'])
        expected = dict(actions=[dict(type='pointer', id='overte-create-'+self.ticket, parameters=dict(pointerType='touch'), actions=[
            dict(type='pointerMove', duration=0, origin='viewport', x=x, y=y), dict(type='pointerDown', button=0),
            dict(type='pause', duration=100), dict(type='pointerUp', button=0)])])
        need(same(expected, state['body'])); return deepcopy(clock)

    def tap(self, owned_id, editor_id, host_barrier):
        need(self.state is None and entity_id(owned_id)); self.lock.assert_held()
        self.state = dict(phase='reading', ownedId=owned_id, editorId=editor_id, start=None, end=None,
                         originals={}, clockJoin=None, point=None, body=None, admission=None, releaseObserved=False); self.save()
        acquisition = NativeClockAcquisition(self.native, epoch_ms=self.epoch_ms, monotonic=self.monotonic)
        acquisition.begin(host_barrier); self.remember('start', acquisition.started)
        for key, read in (('create', lambda: self.source.read(self.run)), ('geometry', self.geometry.capture),
                          ('ui', self.normal.capture), ('sdkWindow', lambda: self.ui._request('GET', '/window/rect'))):
            self.state['originals'][key] = deepcopy(read()); self.save()
        ending = dict(nativeAfter=self.native.read(self.native.sequence), hostAfterEpochMs=self.epoch_ms(),
                      hostAfterMonotonic=self.monotonic()); self.remember('end', ending)
        originals = self.state['originals']
        self.remember('clockJoin', dict(acquisition.started, **ending, originalsSha256=digest(originals),
            sourceTimes=[dict(source='ui', field='sampleEpochMs', epochMs=originals['ui']['sampleEpochMs'])]))
        self.remember('point', point(originals['create'], originals['geometry'], owned_id, editor_id))
        target, rect = self.state['point'], originals['sdkWindow']
        self.remember('body', dict(actions=[dict(type='pointer', id='overte-create-'+self.ticket,
            parameters=dict(pointerType='touch'), actions=[dict(type='pointerMove', duration=0, origin='viewport',
                x=round(rect['x']+target['x']), y=round(rect['y']+target['y'])), dict(type='pointerDown', button=0),
                dict(type='pause', duration=100), dict(type='pointerUp', button=0)])]))
        self.remember('admission', self.source.read(self.run))
        self.state['phase'] = 'ready'; self.save(); self.proof()
        deadline = self.state['clockJoin']['hostBeforeEpochMs']+1500
        need(self.epoch_ms() < deadline and self.monotonic() < self.state['clockJoin']['hostBeforeMonotonic']+1.5)
        # The exact body and source originals are durable before one normal
        # UIKit touch. ACKs never decide voxelValue or renderer success.
        self.state['phase'] = 'issued'; self.save()
        try:
            self.ui._check()
            need(self.epoch_ms() < deadline and self.monotonic() < self.state['clockJoin']['hostBeforeMonotonic']+1.5)
            self.ui._request('POST', '/actions', self.state['body']); self.ui._check()
        finally:
            self.ui.release_actions(); self.state['releaseObserved'] = True; self.save()
        self.state['phase'] = 'released'; self.save()

    def recover_release(self):
        need(self.state is not None and self.state['phase'] in ('issued', 'released'))
        self.ui.release_actions(); self.state['releaseObserved'] = True
        # Keep issued after an unknown POST. Only separate original effects can
        # later resolve its responsibility; this method never emits touch again.
        self.save()
