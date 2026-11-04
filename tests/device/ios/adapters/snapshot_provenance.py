"""Ordinary Snapshot callback/image provenance; no Actor or scene-fidelity verdict.

The separate opt-in native ledger records the SAME primary mono forward frame,
actual saved transform, original OpenGL screenshot crop and callback pixels.
An original row never changes. No new clock is read during historical replay.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import re
from PIL import Image
from adapters.native_feature_observation import exact, fresh, integer, need, number
from adapters.render_view import recorded_view
from adapters.script_feature.history import same
from ios.adapters import snapshot_captures
from ios.adapters.places_model import IOSPlacesModel

ACTION = 'feature-ios-snapshot-provenance'
FILE = ACTION + '.json'
LIMIT = 262144


def command(value):
    prior = deepcopy(value)
    prior['action'] = snapshot_captures.ACTION
    snapshot_captures.command(prior)
    need(value['action'] == ACTION)
    return value


def frame(value, pid, epoch):
    exact(value, {'snapshotFrameProvenanceVersion', 'frameInstance', 'frameIndex', 'processId',
        'pipeline', 'recordedEpochMs', 'transformSlot', 'viewport', 'worldFromCamera',
        'camera', 'backend', 'readback', 'callbackEpochMs'})
    need(type(value['snapshotFrameProvenanceVersion']) is int and value['snapshotFrameProvenanceVersion'] == 1
        and value['processId'] == pid and integer(value['processId'], 1)
        and value['pipeline'] == 'forward-primary-mono' and value['backend'] == 'opengl')
    snapshot_captures.identity(value['frameInstance'])
    need(integer(value['frameIndex'], 1, 2**32 - 1) and integer(value['transformSlot'], 0, 2**32 - 1)
        and integer(value['recordedEpochMs'], 1, epoch)
        and integer(value['callbackEpochMs'], value['recordedEpochMs'], epoch))
    viewport = value['viewport']
    need(type(viewport) is list and len(viewport) == 4
        and all(integer(n, 0, 8192) for n in viewport[:2])
        and all(integer(n, 1, 8192) for n in viewport[2:]))
    camera = recorded_view(value['camera'])
    matrix = value['worldFromCamera']
    need(type(matrix) is list and len(matrix) == 16
        and all(number(n, -1e12, 1e12) for n in matrix)
        and matrix[12:] == [0, 0, 0, 1])
    # Actual evalViewTransform is translation + orientation (no guessed view).
    need(all(abs(matrix[index * 4 + 3] - camera['position'][index]) < 1e-5 for index in range(3)))
    x, y, z, w = camera['rotation']
    rotation = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
    need(all(abs(matrix[row*4+col] - rotation[row][col]) < 1e-5 for row in range(3) for col in range(3)))
    read = value['readback']
    exact(read, {'sourceExtent', 'rectBottomLeft', 'imageExtent', 'pixelFormat', 'pixelSha256', 'readEpochMs'})
    for key in ('sourceExtent', 'imageExtent'):
        need(type(read[key]) is list and len(read[key]) == 2
            and all(integer(n, 1, 8192) for n in read[key]))
    rect = read['rectBottomLeft']
    need(type(rect) is list and len(rect) == 4
        and all(integer(n, 0, 8192) for n in rect[:2])
        and all(integer(n, 1, 8192) for n in rect[2:])
        and all(rect[index] + rect[index+2] <= read['sourceExtent'][index] for index in range(2))
        and read['imageExtent'] == rect[2:]
        and read['pixelFormat'] == 'rgba8-top-left'
        and type(read['pixelSha256']) is str and re.fullmatch('[a-f0-9]{64}', read['pixelSha256'])
        and integer(read['readEpochMs'], value['recordedEpochMs'], value['callbackEpochMs']))
    return value


def validate(value, query, pid, epoch=None, previous=None):
    command(query)
    exact(value, {'iosSnapshotProvenanceVersion', 'requestId', 'runId', 'instance', 'sequence',
        'processId', 'clockDomain', 'clockBefore', 'clockAfter', 'source'})
    need(type(value['iosSnapshotProvenanceVersion']) is int and value['iosSnapshotProvenanceVersion'] == 1
        and value['requestId'] == query['commandId'] and value['runId'] == query['runId']
        and integer(pid, 1) and integer(value['processId'], 1) and value['processId'] == pid
        and integer(value['sequence'], 1, 1000000000)
        and value['clockDomain'] == 'native-main-snapshot-provenance')
    snapshot_captures.identity(value['instance'])
    for clock in (value['clockBefore'], value['clockAfter']):
        exact(clock, {'epochMs', 'monotonicMs'})
        need(integer(clock['epochMs'], 1) and integer(clock['monotonicMs']))
    before, after = value['clockBefore'], value['clockAfter']
    elapsed = after['epochMs'] - before['epochMs']
    mono = after['monotonicMs'] - before['monotonicMs']
    need(0 <= elapsed < 1500 and 0 <= mono < 1500 and abs(elapsed - mono) <= 250)
    if epoch is not None:
        fresh(after['epochMs'], epoch)
    source = value['source']
    exact(source, {'complete', 'captures'})
    need(type(source['complete']) is bool and type(source['captures']) is list and len(source['captures']) <= 64)
    ids = []
    for row in source['captures']:
        exact(row, {'captureInstance', 'requestId', 'frame'})
        snapshot_captures.identity(row['captureInstance'])
        ids.append(row['captureInstance'])
        need(type(row['requestId']) is str and re.fullmatch('snap_[0-9]{1,16}_[0-9]{1,10}', row['requestId']))
        frame(row['frame'], pid, after['epochMs'])
    need(ids == sorted(set(ids)) and len(json.dumps(value, allow_nan=False).encode()) <= LIMIT)
    if previous is not None:
        validate(previous, dict(query, commandId=previous['requestId']), pid)
        need(value['instance'] == previous['instance'] and value['sequence'] > previous['sequence']
            and value['requestId'] != previous['requestId']
            and all(before[key] >= previous['clockAfter'][key] for key in before)
            and (previous['source']['complete'] or not source['complete']))
        current = {row['captureInstance']: row for row in source['captures']}
        for old in previous['source']['captures']:
            need(old['captureInstance'] in current and same(current[old['captureInstance']], old))
    return value


def original(value):
    return validate(value, dict(schemaVersion=1, action=ACTION,
        commandId=value.get('requestId'), runId=value.get('runId')), value.get('processId'))


def joined_originals(packet, native_captures, completed, raw):
    """Pure recorded association only; typed original custody is enforced below."""
    original(packet)
    snapshot_captures.original(native_captures)
    need(packet['source']['complete'] and native_captures['source']['complete']
        and packet['processId'] == native_captures['processId'] == completed['processId']
        and packet['runId'] == native_captures['runId'] == completed['runId']
        and completed['mode'] == 'still' and completed['format'] == 'png')
    rows = [row for row in packet['source']['captures'] if row['captureInstance'] == completed['captureInstance']]
    caps = [row for row in native_captures['source']['captures'] if row['instance'] == completed['captureInstance']]
    need(len(rows) == len(caps) == 1)
    row, capture = rows[0], caps[0]
    need(row['requestId'] == capture['requestId'] == completed['captureId']
        and capture['bornEpochMs'] <= row['frame']['recordedEpochMs']
        and row['frame']['callbackEpochMs'] <= completed['completedNativeEpochMs'])
    need(type(raw) is bytes and hashlib.sha256(raw).hexdigest() == completed['file']['sha256']
        and len(raw) == completed['file']['size'])
    with Image.open(BytesIO(raw)) as image:
        need(image.format == 'PNG' and image.size == tuple(row['frame']['readback']['imageExtent'])
            and 1 <= image.width <= 8192 and 1 <= image.height <= 8192)
        image.load()
        pixels = image.convert('RGBA').tobytes()
    need(hashlib.sha256(pixels).hexdigest() == row['frame']['readback']['pixelSha256'])
    return deepcopy(row)


class IOSSnapshotProvenance(IOSPlacesModel):
    _limit = LIMIT
    _action = ACTION
    _command = staticmethod(command)
    _validate = staticmethod(validate)
    _acquisition_key = 'iosSnapshotProvenanceAcquisitionVersion'
