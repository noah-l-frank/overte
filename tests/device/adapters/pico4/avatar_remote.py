"""Original second-client remote Avatar/Model/Rig and executed stereo joins."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import uuid

from adapters.native_avatar_render import _OriginalQuery, envelope, nonce, loaded_source
from adapters.native_feature_observation import exact, fresh, integer, need, number
from adapters.native_graphics_subject import entity_id, rotation, vector
from adapters.native_animation_history import clip, validate as history, accept as history_accept
from adapters.script_journey.history import same
from adapters.world_render_evidence import recorded_view
from adapters.pico4.emote_model_draws import validate as draw_packet, ACTION as DRAW_ACTION
from adapters.pico4 import remote_joint_pose

VERSION = 3
ACTION = 'feature-pico-remote-avatar-observe'
FILE = 'feature-pico-remote-avatar.json'
LIMIT = 196608
ZERO = '00000000-0000-0000-0000-000000000000'


def command(value):
    exact(value, {'schemaVersion', 'commandId', 'action', 'runId', 'subjectSessionId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1 and value['action'] == ACTION
         and nonce(value['commandId']) and nonce(value['runId'])
         and entity_id(value['subjectSessionId']) and value['subjectSessionId'] != ZERO)
    return value


def client(value, run, epoch):
    exact(value, {'requestedEpochMs', 'capturedEpochMs', 'identity'})
    need(integer(value['requestedEpochMs'], 1) and integer(value['capturedEpochMs'], value['requestedEpochMs'], epoch))
    identity = value['identity']; exact(identity, {'domainId', 'sessionId', 'connected', 'domainSession'})
    need(identity['connected'] is True and entity_id(identity['domainId']) and identity['domainId'] != ZERO
         and entity_id(identity['sessionId']) and identity['sessionId'] != ZERO)
    domain = identity['domainSession']
    exact(domain, {'domainSessionVersion', 'instance', 'revision', 'connected', 'domainSha256', 'connectionBirth', 'connectedEpochMs'})
    need(type(domain['domainSessionVersion']) is int and domain['domainSessionVersion'] == 1
         and nonce(domain['instance']) and integer(domain['revision'], 1) and domain['connected'] is True
         and nonce(domain['connectionBirth']) and integer(domain['connectedEpochMs'], 1, epoch)
         and domain['domainSha256'] == hashlib.sha256((run + ':').encode() + uuid.UUID(identity['domainId']).bytes).hexdigest())
    return identity


def rig(value, rig_id, epoch):
    fields = {'rigId', 'capturedEpochMs', 'evaluationSequence', 'animationsEnabled', 'graphLoaded', 'overrideActive', 'joints', 'history'}
    exact(value, fields | ({'clip'} if 'clip' in value else set()))
    need(integer(value['rigId']) and value['rigId'] == rig_id and integer(value['capturedEpochMs'], 1, epoch)
         and integer(value['evaluationSequence'], 1) and all(type(value[k]) is bool for k in
             ('animationsEnabled', 'graphLoaded', 'overrideActive')) and type(value['joints']) is list
         and 1 <= len(value['joints']) <= 256)
    for joint in value['joints']: vector(joint, 7, -1e6, 1e6)
    if 'clip' in value:
        need(value['overrideActive']); clip(value['clip'], epoch=value['capturedEpochMs'])
    history(value['history'], value, epoch)
    fresh(value['capturedEpochMs'], epoch)


def validate(value, request, pid, epoch, *, current=False):
    command(request); envelope(value, request, pid, epoch)
    source = value['source']
    exact(source, {'picoRemoteAvatarVersion', 'runId', 'clientBefore', 'clientAfter', 'selfSessionId',
        'subjectSessionId', 'subject', 'worldRenderInstance', 'cameraMode', 'view'})
    version = source['picoRemoteAvatarVersion']
    need(type(version) is int and version in (1,2,3) and (not current or version == VERSION)
         and source['runId'] == request['runId'] and source['subjectSessionId'] == request['subjectSessionId'])
    before = client(source['clientBefore'], source['runId'], value['capturedEpochMs'])
    after = client(source['clientAfter'], source['runId'], value['capturedEpochMs'])
    need(same(before, after) and source['selfSessionId'] == before['sessionId']
         and source['selfSessionId'] != source['subjectSessionId']
         and value['requestedEpochMs'] <= source['clientBefore']['requestedEpochMs']
         and source['clientBefore']['capturedEpochMs'] <= source['clientAfter']['requestedEpochMs'])
    subject = source['subject']
    # The original null/missing subject or empty Rig is retained by the caller
    # before this refusal. It cannot become a local-avatar or desired-UUID fact.
    exact(subject, {'sessionId', 'avatarInstance', 'modelInstance', 'rigId', 'rig', 'loaded', 'visible',
        'addedToScene', 'avatarShouldRender', 'geometry', 'pose'} | ({'remoteJointPose'} if version >= 2 else set()))
    need(subject['sessionId'] == source['subjectSessionId'] and nonce(subject['avatarInstance'])
         and nonce(subject['modelInstance']) and integer(subject['rigId'])
         and all(type(subject[k]) is bool for k in ('loaded', 'visible', 'addedToScene', 'avatarShouldRender')))
    if version == 1:
        rig(subject['rig'], subject['rigId'], value['capturedEpochMs'])
    else:
        need(type(subject['rig']) is dict)
        # Preserve the old raw getter truth (normally empty for OtherAvatar),
        # without pretending that a local animation evaluation happened.
        if subject['rig']:
            need(integer(subject['rig'].get('capturedEpochMs'),1,value['capturedEpochMs']))
            rig(subject['rig'], subject['rigId'], subject['rig']['capturedEpochMs'])
        remote_joint_pose.validate(subject['remoteJointPose'], subject, value['capturedEpochMs'],version=1 if version == 2 else 2)
    geometry = subject['geometry']
    if geometry is not None:
        exact(geometry, {'instance', 'sourcePresent', 'sourceSha256'})
        need(nonce(geometry['instance'])); loaded_source(geometry['sourcePresent'], geometry['sourceSha256'])
    need(subject['loaded'] == (geometry is not None))
    pose = subject['pose']; exact(pose, {'feetPosition', 'orientation', 'modelScale'})
    vector(pose['feetPosition'], 3, -1e6, 1e6); rotation(pose['orientation']); need(number(pose['modelScale'], .0001, 1000))
    need(type(source['cameraMode']) is str and len(source['cameraMode']) <= 64 and '\0' not in source['cameraMode'])
    need(source['worldRenderInstance'] is None or nonce(source['worldRenderInstance']))
    recorded_view(source['view']); return value


def continuity(before, after):
    if before is None: return
    a, b = before['source'], after['source']
    need(after['instance'] == before['instance'] and after['processId'] == before['processId']
         and after['sequence'] > before['sequence'] and after['requestId'] != before['requestId']
         and after['capturedEpochMs'] >= before['capturedEpochMs']
         and all(a[k] == b[k] for k in ('runId', 'selfSessionId', 'subjectSessionId'))
         and same(a['clientAfter']['identity'], b['clientBefore']['identity'])
         and all(a['subject'][k] == b['subject'][k] for k in ('sessionId', 'avatarInstance', 'modelInstance', 'rigId'))
         and a['picoRemoteAvatarVersion'] == b['picoRemoteAvatarVersion'])
    if a['picoRemoteAvatarVersion'] == 1:
        need(b['subject']['rig']['evaluationSequence'] >= a['subject']['rig']['evaluationSequence']
             and b['subject']['rig']['capturedEpochMs'] >= a['subject']['rig']['capturedEpochMs'])
        previous = history_accept(None, a['subject']['rigId'], a['subject']['rig']['history'])
        history_accept(previous, b['subject']['rigId'], b['subject']['rig']['history'])
    else: remote_joint_pose.continuity(a['subject']['remoteJointPose'],b['subject']['remoteJointPose'])


def independent(primary, actor):
    """Cross measured client identities; the Primary supplies scope, not effects.

    Both arguments are original remote-observer packets: each actual client can
    observe the other client. Their subject states remain independent originals.
    """
    a, b = primary['source'], actor['source']
    need(a['runId'] == b['runId'] and primary['instance'] != actor['instance']
         and a['selfSessionId'] != b['selfSessionId'] and b['subjectSessionId'] == a['selfSessionId']
         and a['subjectSessionId'] == b['selfSessionId']
         and a['clientAfter']['identity']['domainId'] == b['clientBefore']['identity']['domainId']
         and a['clientAfter']['identity']['domainSession']['domainSha256'] == b['clientBefore']['identity']['domainSession']['domainSha256'])


class NativePicoRemoteAvatar(_OriginalQuery):
    def __init__(self, send, read, clock_ms, guard, pid, *, retain, **options):
        need(callable(retain)); self.retain = retain; self.previous = None; self.last_raw = None
        super().__init__(send, read, clock_ms, guard, pid, **options); need(self.ios is False)
        self.transport_send, self.transport_read = send, read
        self.send, self.original = self.retained_send, self.retained_read

    def retained_send(self, request):
        self.retain('request', deepcopy(request))
        need(self.guard() is not False)
        epoch = self.clock_ms(); now = self.monotonic()
        need(number(now, self.started, self.started + 1.5) and integer(epoch, self.issued_epoch)
             and max(epoch - self.issued_epoch, (now - self.started) * 1000) < 1500)
        return self.transport_send(request)

    def retained_read(self):
        raw = self.transport_read()
        self.retain('raw', raw)  # Original bytes survive unavailable/malformed/foreign refusal.
        need(type(raw) is str and len(raw.encode()) <= LIMIT); self.last_raw = raw
        return raw

    def read(self, run, subject):
        self.started, self.issued_epoch = self.monotonic(), self.clock_ms()
        value = self._read(command(self._request(ACTION, runId=run, subjectSessionId=subject)),
            lambda value,request,pid,epoch:validate(value,request,pid,epoch,current=True))
        continuity(self.previous, value); self.previous = deepcopy(value); return value

    def restore(self, packets):
        need(self.last is None and type(packets) is list and len(packets) <= 32)
        for value in packets:
            request = command(dict(schemaVersion=1, commandId=value.get('requestId'), action=ACTION,
                runId=value['source']['runId'], subjectSessionId=value['source']['subjectSessionId']))
            validate(value, request, self.pid, value['capturedEpochMs']); self._advance(value)
            continuity(self.previous, value); self.previous = self.last = deepcopy(value)


def remote_draws(primary, before, after, capture, draws, pid, epoch):
    """Actual remote model draws in both submitted eyes; no pixel/Actor verdict."""
    for value in (primary, before, after):
        source = value['source']
        validate(value, command(dict(schemaVersion=1, commandId=value['requestId'], action=ACTION,
            runId=source['runId'], subjectSessionId=source['subjectSessionId'])), value['processId'], value['capturedEpochMs'],current=True)
    independent(primary, before); independent(primary, after); continuity(before, after)
    need(before['processId'] == after['processId'] == pid)
    draw_packet(draws, dict(schemaVersion=1, commandId=draws.get('requestId'), action=DRAW_ACTION,
        captureRequestId=capture.get('requestId')), pid, epoch, capture=capture)
    frame = capture['source']['renderTrace']; a, b = before['source'], after['source']
    need(nonce(a['worldRenderInstance']) and a['worldRenderInstance'] == b['worldRenderInstance']
         == capture['instance'] == draws['instance'])
    need(before['capturedEpochMs'] <= frame['recordedEpochMs']
         and capture['source']['capturedEpochMs'] <= after['requestedEpochMs'])
    def near(x, y, tolerance): return len(x) == len(y) and all(abs(p-q) <= tolerance for p, q in zip(x, y))
    def same_rotation(x, y): return near(x, y, .001) or near(x, [-v for v in y], .001)
    left, right = a['subject'], b['subject']
    need(same(left['geometry'], right['geometry']) and a['cameraMode'] == b['cameraMode']
         and near(left['pose']['feetPosition'], right['pose']['feetPosition'], .005)
         and same_rotation(left['pose']['orientation'], right['pose']['orientation'])
         and abs(left['pose']['modelScale'] - right['pose']['modelScale']) <= 1e-4)
    for source in (a, b):
        subject = source['subject']; view = source['view']; recorded = frame['recordedView']
        need(all(subject[k] is True for k in ('loaded', 'visible', 'addedToScene', 'avatarShouldRender'))
             and subject['geometry'] is not None and subject['geometry']['sourcePresent']
             and near(view['position'], recorded['position'], .005)
             and same_rotation(view['rotation'], recorded['rotation'])
             and near(view['projection'], recorded['projection'], 1e-4))
        remote_joint_pose.validate(subject['remoteJointPose'],subject,epoch)
        for field in ('fieldOfViewDegrees', 'aspectRatio', 'nearClip', 'farClip'):
            need(abs(view[field] - recorded[field]) <= 1e-4 * max(1, abs(recorded[field])))
    rows = [row for row in draws['source']['modelTrace']['models'] if row['modelInstance'] == left['modelInstance']]
    need(len(rows) == 1); row = rows[0]; geometry = left['geometry']
    need(row['geometryInstance'] == geometry['instance'] and row['loadedSourcePresent']
         and row['loadedSourceSha256'] == geometry['sourceSha256'] and row['skinnedDrawCommands'] > 0
         and row['originalGeometryDrawCommands'] == row['drawCommands']
         and all(x < y for x, y in zip(row['minimum'], row['maximum'])))
    return deepcopy(row)
