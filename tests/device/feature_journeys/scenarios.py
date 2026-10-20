"""Closed ordinary-user actions and independently asserted product checkpoints.

Inputs never include assertions. Values prefixed with $ are expanded from the
owned fixture context. Each checkpoint is a complete state, not an adapter verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

VERSION = 11


def emote_rows():
    for index,name in enumerate(('Crying','Surprised','Dancing','Cheering','Waving','Fall','Pointing','Clapping','Sit','Love')):
        yield ('play',dict(name=name),dict(animation=name,override=True,
            sit={'oneOf':['Sit1','Sit2','Sit3']} if name=='Sit' else 'none',poseProgress={'min':.15,'max':1.},
            restoredBeforeNominalEnd=False,panel={'oneOf':[False,True]}),['image' if index==0 else 'changed','peer'])
        # Ordinary non-Sit clips restore on their own timer. Tablet Sit holds
        # its final pose; cancel is only a reset here, not the timed abort proof.
        yield ('cancel' if name=='Sit' else 'wait-complete',{},dict(animation='idle',sit='none',override=False,poseProgress=0.,
            restoredBeforeNominalEnd={'oneOf':[False,True]} if name=='Sit' else False),['changed','peer'])


def scenario(title, baseline, rows):
    state = deepcopy(baseline)
    steps = []
    for verb, inputs, changes, evidence in rows:
        state.update(changes)
        steps.append(dict(verb=verb, inputs=inputs, state=deepcopy(state), evidence=evidence))
    return dict(title=title, baseline=baseline, steps=steps)


# Evidence: image = current challenge in original screenshot; changed = same plus
# changed subject pixels. peer = independently journaled fixture-actor receipt;
# file = original exported bytes; audio/silence = actual bounded PCM capture.
SCENARIOS = {
'world-navigation': scenario('Bookmarks, directory, failed arrival and recovery',
    dict(location='A', bookmark=False, bookmarkName='', searchResults=[], error='none', panel=False), [
    ('open', {}, dict(panel=True), []),
    ('bookmark-add', dict(name='$name'), dict(bookmark=True, bookmarkName='$name'), ['peer']),
    ('bookmark-rename', dict(name='$renamed'), dict(bookmarkName='$renamed'), ['peer']),
    ('directory-search', dict(query='$name'), dict(searchResults=['$destination']), ['peer']),
    ('directory-select', dict(destination='$destination'), dict(location='B'), ['image', 'peer']),
    ('navigate-missing', {}, dict(error='not-found', location='B'), ['peer']),
    ('dismiss-error', {}, dict(error='none'), []),
    ('bookmark-visit', dict(name='$renamed'), dict(location='A'), ['changed', 'peer']),
    ('restart-app', {}, {}, ['peer']),
    ('bookmark-delete', dict(name='$renamed'), dict(bookmark=False, bookmarkName=''), ['peer']),
    ('close', {}, dict(panel=False), []),
]),
'authentication': scenario('Owned login, view dismissal, retired response and persistence',
    dict(principal='anonymous', dialog=False, error='none', pending=False, protectedAccess=False, delayedGrantOutstanding=False), [
    ('login-open', {}, dict(dialog=True), ['peer']),
    ('login-submit', dict(account='invalid'), dict(error='invalid-credentials'), ['peer']),
    ('login-cancel', {}, dict(dialog=False, error='none'), ['peer']),
    ('login-open', {}, dict(dialog=True), ['peer']),
    ('login-submit', dict(account='delayed'), dict(pending=True), ['peer']),
    # Ordinary Cancel dismisses the view; it deliberately leaves the real
    # AccountManager request alive. Reopening must not create a second request.
    ('login-cancel', {}, dict(pending=True, dialog=False), ['peer']),
    ('login-open', {}, dict(pending=True, dialog=True), ['peer']),
    ('login-cancel', {}, dict(pending=True, dialog=False), ['peer']),
    # The actual process boundary, rather than view dismissal, retires the
    # consumer of the delayed valid response. Startup prompts may be present.
    ('restart-app', {}, dict(pending=False, dialog={'oneOf':[False,True]}), ['peer']),
    ('login-cancel', {}, dict(dialog=False), ['peer']),
    ('release-stale-response', {}, dict(delayedGrantOutstanding=True), ['peer']),
    ('login-open', {}, dict(dialog=True), ['peer']),
    ('login-submit', dict(account='owned'), dict(principal='owned', dialog=False, protectedAccess=True), ['peer']),
    ('restart-app', {}, {}, ['peer']),
    ('logout', {}, dict(principal='anonymous', protectedAccess=False), ['peer']),
    ('restart-app', {}, dict(dialog={'oneOf':[False,True]}), ['peer']),
    ('login-cancel', {}, dict(dialog=False), ['peer']),
]),
'avatar-people': scenario('Avatar chooser and mutual connection consent',
    dict(avatar='original', scale=1.0, wearable=False, bookmarked=False, connection='none', dialog=False, error='none'), [
    ('avatar-url', dict(resource='avatar-a.fst'), dict(avatar='A'), ['image', 'peer']),
    ('avatar-bookmark-save', dict(name='$name'), dict(bookmarked=True), ['peer']),
    ('avatar-scale', dict(value=1.5), dict(scale=1.5), ['changed', 'peer']),
    ('wearable-add', dict(resource='wearable.json'), dict(wearable=True), ['changed', 'peer']),
    ('avatar-url', dict(resource='missing.fst'), dict(error='not-found'), ['peer']),
    ('dismiss-error', {}, dict(error='none'), []),
    ('avatar-bookmark-choose', dict(name='$name'), dict(scale=1.0, wearable=False), ['changed', 'peer']),
    ('connection-request', dict(peer='owned-peer'), dict(connection='pending', dialog=True), ['peer']),
    ('connection-cancel', {}, dict(connection='none', dialog=False), ['peer']),
    ('connection-request', dict(peer='owned-peer'), dict(connection='pending', dialog=True), ['peer']),
    ('peer-reject', {}, dict(connection='none', dialog=False), ['peer']),
    ('connection-request', dict(peer='owned-peer'), dict(connection='pending', dialog=True), ['peer']),
    ('peer-accept', {}, dict(connection='connected', dialog=False), ['peer']),
    ('connection-remove', dict(peer='owned-peer'), dict(connection='none'), ['peer']),
    ('avatar-restore', {}, dict(avatar='original'), ['image', 'peer']),
    ('avatar-bookmark-delete', dict(name='$name'), dict(bookmarked=False), ['peer']),
]),
# NativeCreate's file picker imports entity JSON. glTF/OBJ use the ordinary
# NEW Model resource URL, not a fictitious local raw-model import dialog.
'create': scenario('Model URL creation, actual JSON picker, export and rez recovery',
    dict(objects=[], editor=False, picker=False, error='none', canRez=True, selection=[], textured=False, voxelValue=0), [
    ('open', {}, dict(editor=True), []),
    ('import-picker-open', dict(resource='entity-import.json'), dict(picker=True), ['peer']),
    ('import-picker-cancel', {}, dict(picker=False), ['peer']),
    ('model-create', dict(resource='gltf-bundle/main.gltf'), dict(objects=['model'], selection=['model']), ['image', 'peer']),
    ('apply-texture', dict(resource='checker.png'), dict(textured=True), ['changed', 'peer']),
    ('export-selection', {}, {}, ['file', 'peer']),
    ('delete-owned', {}, dict(objects=[], selection=[], textured=False, voxelValue=0), ['changed', 'peer']),
    ('model-create', dict(resource='obj-bundle/main.obj'), dict(objects=['model'], selection=['model']), ['changed', 'peer']),
    ('delete-owned', {}, dict(objects=[], selection=[], textured=False, voxelValue=0), ['changed', 'peer']),
    ('import-picker-open', dict(resource='entity-import.json'), dict(picker=True), ['peer']),
    ('import-picker-accept', {}, dict(picker=False, objects=['model'], selection=['model']), ['changed', 'peer']),
    ('delete-owned', {}, dict(objects=[], selection=[], textured=False, voxelValue=0), ['changed', 'peer']),
    ('voxel-create', {}, dict(objects=['voxel'], selection=['voxel']), ['changed', 'peer']),
    ('voxel-edit', dict(mode='remove', brushMeters=0.5), dict(voxelValue=1), ['changed', 'peer']),
    ('delete-owned', {}, dict(objects=[], selection=[], textured=False, voxelValue=0), ['changed', 'peer']),
    ('set-rez-permission', dict(allowed=False), dict(canRez=False), ['peer']),
    ('create-denied', {}, dict(error='permission-denied'), ['peer']),
    ('set-rez-permission', dict(allowed=True), dict(canRez=True), ['peer']),
    ('create-retry', {}, dict(objects=['cube'], selection=['cube'], error='none'), ['changed', 'peer']),
    ('delete-owned', {}, dict(objects=[], selection=[], textured=False, voxelValue=0), ['changed', 'peer']),
    ('close', {}, dict(editor=False), ['peer']),
]),
'emotes': scenario('Ten emotes, three Sit modes, override and cancellation',
    dict(animation='idle', sit='none', override=False, poseProgress=0.0, panel=False,restoredBeforeNominalEnd=False), [
    ('open', {}, dict(panel=True), []),
    *emote_rows(),
    *[( 'sit', {}, dict(animation='Sit',override=True,restoredBeforeNominalEnd=False,
                       poseProgress={'min':.15,'max':1.},sit={'oneOf': ['Sit1', 'Sit2', 'Sit3']}), ['image', 'peer'])
      for _ in range(3)],
    ('override', dict(name='Waving'), dict(animation='Waving', override=True, sit='none',restoredBeforeNominalEnd=False), ['changed', 'peer']),
    ('cancel', {}, dict(animation='idle', sit='none',override=False, poseProgress=0.0,restoredBeforeNominalEnd=True), ['changed', 'peer']),
    ('background-resume', {}, {}, ['peer']),
    ('close', {}, dict(panel=False), []),
]),
'world-web': scenario('Actual documents, foreign input, HTTP recovery and recreated resume',
    dict(surface='world',text='',page='none',bridgeMessages=0,bridgeEchoes=0,attemptedMessages=0,documentLoads=0,
         httpStatus=0,origin='none',documentKind='none',inlineLeases=0,deferredMessages=0,
         error='none',focused=False,open=False), [
    ('open', {}, dict(open=True,page='reference',httpStatus=200,origin='primary',documentKind='http',
        documentLoads={'min':1,'max':1000000}), ['image','peer']),
    ('focus-type', dict(text='$unicode'), dict(text='$unicode', focused=True), ['peer']),
    ('submit', {}, dict(bridgeMessages=1,bridgeEchoes=1,attemptedMessages=1,focused=False), ['peer']),
    # Clear before navigation: neither backend promises to retain form data
    # through document destruction or a nonce-recovery history reload.
    ('clear-text', {}, dict(text='',focused=True), ['peer']),
    ('navigate', dict(resource='page-b.html'), dict(page='B', focused=False), ['changed', 'peer']),
    ('back', {}, dict(page='reference'), ['changed','peer']),
    ('navigate-foreign',dict(resource='reference.html'),dict(page='foreign',origin='foreign'),['changed','peer']),
    ('foreign-origin-message', {}, dict(attemptedMessages=2), ['peer']),
    ('back', {}, dict(page='reference',origin='primary'), ['changed','peer']),
    ('navigate',dict(resource='recovery.html'),dict(page='recovery',httpStatus=404),['image','peer']),
    ('reload',{}, {}, ['peer']),
    ('restore-resource',{}, {}, ['peer']),
    ('reload', {}, dict(httpStatus=200), ['image','peer']),
    # Recreate the original source URL on both backends after backgrounding.
    ('navigate',dict(resource='reference.html'),dict(page='reference'),['changed','peer']),
    ('background-resume', {}, {}, ['image','peer']),
    ('focus-type',dict(text='$reply'),dict(text='$reply',focused=True),['peer']),
    ('submit',{},dict(bridgeMessages=2,bridgeEchoes=2,attemptedMessages=3,focused=False),['peer']),
    ('clear-text',{},dict(text='',focused=True),['peer']),
    ('close', {}, dict(open=False,focused=False,page='none',origin='none',documentKind='none',httpStatus=0), ['peer']),
]),
# These are state type prototypes, not assumed user defaults. The engine
# independently establishes and freezes the actual original preference/render
# baseline before any input, then uses it for restoration and cleanup.
'graphics': scenario('Immediate graphics settings, close durability and original restoration',
    dict(resolution=0.6, renderScale=0.6, haze=False, hazePass=False, mirror=False, mirrorPass=False, dialog=False), [
    ('open', {}, dict(dialog=True), []),
    ('set-resolution', dict(value=0.5), dict(resolution=0.5, renderScale=0.5), ['image']),
    ('close', {}, dict(dialog=False), ['image']),
    ('open', {}, dict(dialog=True), []),
    ('set-resolution', dict(value=0.6), dict(resolution=0.6, renderScale=0.6), ['image']),
    ('set-haze', dict(enabled=False), dict(haze=False, hazePass=False), ['image']),
    ('set-haze', dict(enabled=True), dict(haze=True, hazePass=True), ['changed']),
    ('set-mirrors', dict(enabled=False), dict(mirror=False, mirrorPass=False), ['image']),
    ('set-mirrors', dict(enabled=True), dict(mirror=True, mirrorPass=True), ['changed']),
    ('close', {}, dict(dialog=False), ['image']),
    ('background-resume', {}, {}, ['image']),
    ('restart-app', {}, {}, ['image']),
    ('open', {}, dict(dialog=True), []),
    ('restore-original', {}, {}, ['image']),
    ('close', {}, dict(dialog=False), ['image']),
]),
# OS permission denial/recovery remains in the composed permission-recovery
# foundation. This workflow covers the actual in-memory automatic preview.
'audio': scenario('Automatic recorded preview, cancellation, muted rejection and resume',
    dict(recording=False, preview=False, muted=False, recordedFrames=0, playedFrames=0,
         bufferedFrames=0, phase='idle', history=[], error='none', open=False), [
    ('open', {}, dict(open=True), []),
    ('mute', dict(enabled=True), dict(muted=True), ['silence', 'peer']),
    ('record-start', {}, dict(phase='error', history=['error'], error='microphone-muted'), ['silence', 'peer']),
    ('mute', dict(enabled=False), dict(muted=False), ['peer']),
    ('record-start', {}, dict(recording=True, phase='capturing', history=['capturing'], error='none',
        recordedFrames={'min': 8000, 'max': 480000}, bufferedFrames={'min': 8000, 'max': 480000}), ['peer']),
    ('record-cancel', {}, dict(recording=False, phase='cancelled', history=['capturing', 'cancelled'], bufferedFrames=0), ['silence', 'peer']),
    ('record-start', {}, dict(recording=True, phase='capturing', history=['capturing'],
        bufferedFrames={'min': 8000, 'max': 480000}), ['peer']),
    # No Stop/Save/Preview command exists on this surface. Observe the native
    # cycle's automatic capture -> play -> drain -> completion, then inspect
    # the whole original recording and independent acoustic capture.
    ('await-completion', {}, dict(recording=False, preview=False, bufferedFrames=0,
        phase={'oneOf': ['playing', 'draining', 'completed']},
        history=['capturing', 'playing', 'draining', 'completed'],
        recordedFrames={'min': 24000, 'max': 144000}, playedFrames={'min': 24000, 'max': 144000}), ['file', 'audio', 'peer']),
    ('record-start', {}, dict(recording=True, phase='capturing', history=['capturing'], playedFrames=0,
        recordedFrames={'min': 8000, 'max': 480000}, bufferedFrames={'min': 8000, 'max': 480000}), ['peer']),
    ('mute', dict(enabled=True), dict(muted=True, recording=False, phase='cancelled',
        history=['capturing', 'cancelled'], bufferedFrames=0, error='microphone-muted'), ['silence', 'peer']),
    ('mute', dict(enabled=False), dict(muted=False), ['peer']),
    ('record-start', {}, dict(recording=True, phase='capturing', history=['capturing'], error='none',
        bufferedFrames={'min': 8000, 'max': 480000}), ['peer']),
    ('background-resume', {}, dict(recording=False, phase='cancelled', history=['capturing', 'cancelled'],
        bufferedFrames=0, error={'oneOf': ['backgrounded', 'lifecycle-stopped', 'input-or-lifecycle-changed']}), ['silence', 'peer']),
    ('close', {}, dict(open=False), []),
]),
# ArmoredChat has separate local/domain models and no peer filter, transport
# error UI, queued retry or delivery ACK. A missing mixer produces local echo;
# only an independent actual peer ledger proves remote delivery.
'chat': scenario('Channel histories, cancelled draft, local fallback and explicit resend',
    dict(draft='', messages=[], localMessages=[], domainMessages=[], peerMessages=[],
         channel='none', mixerConnected=True, focused=False, keyboard=False, open=False), [
    ('open', {}, dict(open=True,channel='local'), ['peer']),
    ('type', dict(text='$unicode'), dict(draft='$unicode', focused=True, keyboard=True), ['peer']),
    ('close', {}, dict(open=False, draft='', channel='none', focused=False, keyboard=False), ['peer']),
    ('open', {}, dict(open=True,channel='local'), ['peer']),
    ('select-channel', dict(channel='domain'), dict(channel='domain',focused={'oneOf':[False,True]},keyboard={'oneOf':[False,True]}), ['peer']),
    ('type', dict(text='$unicode'), dict(draft='$unicode', focused=True, keyboard=True), ['peer']),
    ('send', {}, dict(draft='', messages=['$unicode'], domainMessages=['$unicode'], peerMessages=['$unicode'],
        focused={'oneOf':[False,True]}, keyboard={'oneOf':[False,True]}), ['peer']),
    ('peer-send', dict(text='$reply', channel='domain'), dict(messages=['$unicode','$reply'], domainMessages=['$unicode','$reply']), ['peer']),
    ('select-channel', dict(channel='local'), dict(channel='local', messages=[], focused={'oneOf':[False,True]}, keyboard={'oneOf':[False,True]}), ['peer']),
    ('peer-send', dict(text='$hidden', channel='domain'), dict(domainMessages=['$unicode','$reply','$hidden']), ['peer']),
    ('peer-send', dict(text='$reply', channel='local'), dict(messages=['$reply'], localMessages=['$reply']), ['peer']),
    ('peer-send-distant', dict(text='$hidden', channel='local'), {}, ['peer']),
    ('select-channel', dict(channel='domain'), dict(channel='domain', messages=['$unicode','$reply','$hidden'], focused={'oneOf':[False,True]}, keyboard={'oneOf':[False,True]}), ['peer']),
    ('close', {}, dict(open=False, draft='', focused=False, keyboard=False, channel='none', messages=[]), ['peer']),
    ('open', {}, dict(open=True, channel='local', messages=['$reply']), ['peer']),
    ('select-channel', dict(channel='domain'), dict(channel='domain', messages=['$unicode','$reply','$hidden'], focused={'oneOf':[False,True]}, keyboard={'oneOf':[False,True]}), ['peer']),
    ('background-resume', {}, dict(focused=False,keyboard=False), ['peer']),
    ('network-remove-mixer', {}, dict(mixerConnected=False), ['peer']),
    ('type', dict(text='$retry'), dict(draft='$retry', focused=True, keyboard=True), ['peer']),
    ('send', {}, dict(draft='', messages=['$unicode','$reply','$hidden','$retry'],
        domainMessages=['$unicode','$reply','$hidden','$retry'],
        focused={'oneOf':[False,True]}, keyboard={'oneOf':[False,True]}), ['peer']),
    ('network-restore-mixer', {}, dict(mixerConnected=True), ['peer']),
    ('await-no-replay', {}, {}, ['peer']),
    ('type', dict(text='$retry'), dict(draft='$retry', focused=True, keyboard=True), ['peer']),
    ('send', {}, dict(draft='', messages=['$unicode','$reply','$hidden','$retry','$retry'],
        domainMessages=['$unicode','$reply','$hidden','$retry','$retry'], peerMessages=['$unicode','$retry'],
        focused={'oneOf':[False,True]}, keyboard={'oneOf':[False,True]}), ['peer']),
    ('close', {}, dict(open=False, draft='', channel='none', messages=[], focused=False, keyboard=False), ['peer']),
]),
# OS-specific Save rows are selected only after independently witnessing a
# supported actual backend. Capture/share/upload/cleanup remain mandatory.
'snapshots': scenario('Pending capture cancellation, actual Save backend, share/upload and resume',
    dict(open=False,pending=False,captureHistory=[],files=0,saved=0,uploads=0,shares=0,
         saveBackend='photos-add-only',savePermission='granted',saveSheet=False,shareSheet=False,error='none'), [
    ('open', {}, dict(open=True), []),
    ('capture-cancel', dict(mode='animated',format='png'), dict(captureHistory=['pending','cancelled']), ['peer']),
    ('set-save-permission', dict(state='denied'), dict(savePermission='denied'), ['peer']),
    ('capture', dict(mode='still',format='png'), dict(files=1,captureHistory=['pending','cancelled','pending','complete']), ['image','file','peer']),
    ('save-denied', {}, dict(error='permission-denied'), ['peer']),
    ('set-save-permission', dict(state='granted'), dict(savePermission='granted'), ['peer']),
    ('save-picker-open', {}, dict(saveSheet=True,error='none'), ['peer']),
    ('save-picker-cancel', {}, dict(saveSheet=False), ['peer']),
    ('save-picker-open', {}, dict(saveSheet=True), ['peer']),
    ('save', {}, dict(saved=1,saveSheet=False,error='none'), ['file','peer']),
    ('share-open', {}, dict(shareSheet=True), ['peer']),
    ('share-cancel', {}, dict(shareSheet=False), ['peer']),
    ('share-open', {}, dict(shareSheet=True), ['peer']),
    ('share-select-owned', {}, dict(shareSheet=False,shares=1), ['file','peer']),
    ('upload-fail', {}, dict(error='offline'), ['peer']),
    ('upload', {}, dict(uploads=1,error='none'), ['file','peer']),
    ('background-resume', {}, {}, ['image','peer']),
    ('close', {}, dict(open=False), []),
]),
'scripts': scenario('File-bundle picker cancellation, execution and application restart',
    dict(running=[], picker=False, error='none', effects=0, open=False, companions=[]), [
    ('open', {}, dict(open=True), []),
    ('picker-open', {}, dict(picker=True), []),
    ('picker-cancel', {}, dict(picker=False), ['peer']),
    ('picker-open', {}, dict(picker=True), []),
    ('picker-accept', dict(resource='script.js'),
        dict(picker=False, running=['owned-script'], effects={'min': 2, 'max': 100000}, companions=['companion.js']), ['peer']),
    ('stop-owned', {}, dict(running=[], effects=0, companions=[]), ['peer']),
    ('picker-open', {}, dict(picker=True), []),
    ('picker-cancel', {}, dict(picker=False), ['peer']),
    ('picker-open', {}, dict(picker=True), []),
    ('picker-accept', dict(resource='script-bundle/main.js'),
        dict(picker=False, running=['owned-script'], effects={'min': 2, 'max': 100000}, companions=['companion.js']), ['peer']),
    ('restart-app', {}, {}, ['peer']),
    ('stop-owned', {}, dict(running=[], effects=0, companions=[]), ['peer']),
    ('load-url', dict(resource='missing.js'), dict(error='not-found'), ['peer']),
    ('close', {}, dict(open=False, error='none'), []),
]),
'assets': scenario('Asset mappings, companion import, bake, permissions and deletion',
    dict(mappings=[], selected='', baking=False, bakeState='none', canWrite=True, error='none', open=False, sceneModel=False, companions=[]), [
    ('open', {}, dict(open=True), []),
    ('upload-cancel', dict(resource='model.gltf'), {}, ['peer']),
    ('upload', dict(resource='model.gltf'), dict(mappings=['$name'], selected='$name', companions=['mesh/triangle.bin', 'textures/checker.png']), ['peer']),
    ('browse', dict(name='$name'), {}, ['image', 'peer']),
    ('rename', dict(name='$renamed'), dict(mappings=['$renamed'], selected='$renamed'), ['peer']),
    ('bake', {}, dict(bakeState='ready'), ['image', 'peer']),
    ('import-selected', {}, dict(sceneModel=True), ['changed', 'file', 'peer']),
    ('remove-owned-model', {}, dict(sceneModel=False), ['changed', 'peer']),
    ('set-write-permission', dict(allowed=False), dict(canWrite=False), ['peer']),
    ('delete-denied', {}, dict(error='permission-denied'), ['peer']),
    ('set-write-permission', dict(allowed=True), dict(canWrite=True, error='none'), ['peer']),
    ('delete-owned', {}, dict(mappings=[], selected='', bakeState='none', companions=[]), ['peer']),
    ('upload', dict(resource='model.obj'), dict(mappings=['$name'], selected='$name', companions=['materials/palette.mtl', 'textures/checker.png']), ['peer']),
    ('delete-owned', {}, dict(mappings=[], selected='', companions=[]), ['peer']),
    ('upload', dict(resource='missing.gltf'), dict(error='not-found'), ['peer']),
    ('close', {}, dict(open=False, error='none'), []),
]),
'lifecycle-input': scenario('Feature editor focus, Back and background ownership',
    dict(editor='none', text='', keyboard=False, focused=False, heldInputs=[], worldDisplacement=0.0, generation=1), [
    ('open-editor', dict(editor='create'), dict(editor='create', focused=True, keyboard=True), []),
    ('type', dict(text='$unicode'), dict(text='$unicode'), []),
    ('world-input', dict(direction='forward'), {}, ['image']),
    ('back', {}, dict(keyboard=False, focused=False), []),
    ('back', {}, dict(editor='none'), []),
    ('open-editor', dict(editor='chat'), dict(editor='chat', focused=True, keyboard=True), []),
    ('background-resume', {}, dict(keyboard=False, focused=False), ['image', 'peer']),
    ('open-editor', dict(editor='scripts'), dict(editor='scripts', keyboard=True, focused=True), []),
    ('replace-context', {}, dict(generation=2, text='', editor='none', focused=False, keyboard=False), ['peer']),
    ('deliver-stale-input', dict(text='$unicode'), {}, ['peer']),
    ('world-input', dict(direction='forward'), dict(worldDisplacement={'min': 0.3, 'max': 3.0}), ['changed']),
    ('release-input', {}, {}, ['peer']),
    ('restore', {}, dict(worldDisplacement=0.0), ['image']),
]),
}
# Same ordinary browser contract on the normal tablet plus inline app routing.
SCENARIOS['tablet-web'] = deepcopy(SCENARIOS['world-web'])
SCENARIOS['tablet-web']['title'] = 'Tablet browser and inline app isolation'
SCENARIOS['tablet-web']['baseline']['surface'] = 'tablet'
for step in SCENARIOS['tablet-web']['steps']:
    step['state']['surface'] = 'tablet'
inline_state=deepcopy(SCENARIOS['tablet-web']['steps'][-2]['state'])
inline_rows=[]
for verb,inputs,changes,evidence in [
    ('open-inline-app',dict(resource='parity-inline-v1'),dict(page='inline',origin='inline',documentKind='inline',httpStatus=0,inlineLeases=1,focused=False),['changed','peer']),
    ('focus-type',dict(text='$unicode'),dict(text='$unicode',focused=True),['peer']),
    ('submit',{},dict(bridgeMessages=3,bridgeEchoes=3,attemptedMessages=4,focused=False),['peer']),
    ('clear-text',{},dict(text='',focused=True),['peer']),
    # Hold one actual normal Send callback, then retire its real carrier. The
    # stale stimulus must retain its original native document/token/bytes.
    ('hold-inline-message',{},dict(deferredMessages=1,attemptedMessages=5,focused=False),['peer']),
    ('return-from-inline',{},dict(page='reference',origin='primary',documentKind='http',httpStatus=200,inlineLeases=0),['changed','peer']),
    ('deliver-retired-inline-message',{},dict(deferredMessages=0),['peer']),
]:
    inline_state.update(changes)
    inline_rows.append(dict(verb=verb,inputs=inputs,state=deepcopy(inline_state),evidence=evidence))
SCENARIOS['tablet-web']['steps'][-1:-1]=inline_rows
SCENARIOS['tablet-web']['steps'][-1]['state'].update(bridgeMessages=3,bridgeEchoes=3,attemptedMessages=5)
for area in ('world-web','tablet-web'):
    for step in SCENARIOS[area]['steps']:
        # Ordinary buttons do not prescribe the platform's editor-focus
        # aftermath. Observe it independently; do not invent a blur handler.
        if step['verb'] in {'submit','hold-inline-message'}:step['state']['focused']={'oneOf':[False,True]}
        step['documentTransition']='replace' if step['verb'] in {
            'open','navigate','navigate-foreign','back','reload','background-resume','open-inline-app','return-from-inline'} else 'retain'


# This is a closed source policy, not an optional capability. Unknown export
# backends fail before ordinary input, and the independent witness includes
# backend, authorization, pending state and both actual system sheets.
SNAPSHOT_BACKENDS=('photos-add-only','media-store','document-picker')
_snapshots=SCENARIOS['snapshots']
_snapshots['measuredBaselineFields']=['saveBackend','savePermission']
for _step in _snapshots['steps']:
    _step['state']['saveBackend']={'oneOf':list(SNAPSHOT_BACKENDS)}
    _step['originalFields']=['saveBackend']
    if _step['verb'] in {'set-save-permission','save-denied','save-picker-open','save-picker-cancel','save','share-open','share-cancel','share-select-owned'}:
        _step['systemUi']=True
    if _step['verb'] in {'set-save-permission','save-denied'}:
        _step['backends']=['photos-add-only']
    elif _step['verb'] in {'save-picker-open','save-picker-cancel'}:
        _step['backends']=['document-picker']
    if _step['verb'] not in {'set-save-permission','save-denied'}:
        permission=_step['state']['savePermission']
        _step['state']['savePermission']={'oneOf':[permission,'not-required']}
del _snapshots,_step,permission


def snapshot_profile(value):
    backend=value['saveBackend'];permission=value['savePermission']
    if backend not in SNAPSHOT_BACKENDS or permission!=('granted' if backend=='photos-add-only' else 'not-required'):
        raise AssertionError('Snapshot baseline lacks a supported independently measured Save backend/owned authorization')
    return backend


# Fields retain their independently measured initial values until a real
# setting change, and again after restore-original. No original value is sent
# as an observation result, desired state or adapter input.
_graphics = SCENARIOS['graphics']
_graphics['measuredBaselineFields'] = ['resolution','renderScale','haze','hazePass','mirror','mirrorPass']
_original = set(_graphics['measuredBaselineFields'])
for _step in _graphics['steps']:
    if _step['verb'] == 'set-resolution': _original -= {'resolution','renderScale'}
    elif _step['verb'] == 'set-haze': _original -= {'haze','hazePass'}
    elif _step['verb'] == 'set-mirrors': _original -= {'mirror','mirrorPass'}
    elif _step['verb'] == 'restore-original': _original = set(_graphics['measuredBaselineFields'])
    _step['originalFields'] = sorted(_original)
del _graphics, _original, _step


def expand(value, context):
    if isinstance(value, str) and value.startswith('$'):
        return context[value[1:]]
    if isinstance(value, list):
        return [expand(item, context) for item in value]
    if isinstance(value, dict):
        return {key: expand(item, context) for key, item in value.items()}
    return value


def actions(area):
    """Return only the closed input inventory, never checkpoints or evidence."""
    inventory = {}
    for step in SCENARIOS[area]['steps']:
        inventory.setdefault(step['verb'], []).append(step['inputs'])
    return inventory

# Existing modules remain the owner of these workflows. The new suites compose
# them instead of duplicating their input, image/video or probe implementations.
FOUNDATIONS = {
    'world-navigation': ['domain-enter', 'domain-roundtrip', 'places-navigation',
                         'look', 'move', 'input-neutral', 'collision', 'jump', 'fly', 'scene-reload'],
    'authentication': [],
    'avatar-people': ['multi-user'],
    'create': ['create-management', 'entity-sync', 'world-interaction'],
    'emotes': [],
    'world-web': ['world-web-video'],
    'tablet-web': ['tablet-web-video', 'tablet'],
    'graphics': ['render-health'],
    'audio': ['audio-controls', 'permission-recovery', 'sound-playback', 'voice-roundtrip'],
    'chat': ['text-input'],
    'snapshots': ['snapshot-output-parity'],
    'scripts': ['scripts-management', 'scripted-entity'],
    'assets': ['asset-load'],
    'lifecycle-input': ['lifecycle-under-load', 'tablet-input-isolation', 'text-input'],
}

# Real peer replication, domain permissions and asset mappings require a domain.
# Loading the serverless scene here would disconnect precisely those features.
DOMAIN_AREAS = frozenset({'avatar-people', 'create', 'emotes', 'audio', 'chat', 'assets'})
