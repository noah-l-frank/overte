"""Historical same-object/QML/selected-IPA joins for explicit Draft profile 8.

Native producers remain diagnostic and uncompiled. This validates their typed
originals and rereads the independently selected IPA, not a saved success bit.
The complete import/AOT/SDK/evaluation and native resource-end gates stay shut.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from adapters.native_feature_observation import need
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from adapters.chat_root_loaded_identity import match, preserve
from ios.adapters import chat_qml_sources, qt_image_bytes
from ios.adapters.bundle_identity import artifact_member_image, compare
from ios.adapters.installed_code import InstalledCodeBinding


def selected_artifact(value, binding):
    need(type(value) is tuple and len(value) == 2 and isinstance(value[0], Path)
        and value[0].is_absolute() and value[0].resolve(strict=True) == value[0]
        and value[1] == context(binding)['artifactSha256'])
    return value


def unavailable(*_args, **_kwargs):
    raise ValueError('Historical Chat code binding cannot query or mutate a process')


def original_images(record, values, artifact, binding):
    """Literal installed-binding parser plus actual selected IPA member bytes.

Callbacks are deliberately unavailable: record() parses a historical original,
whereas continuity()/verify()/launch and native source reads are never called.
No historical record is substituted for a current installed-binding owner.
"""
    path, digest = selected_artifact(artifact, binding)
    need(type(values) is list and len(values) == 2)
    pid = int(binding['processIdentity'])
    for value in values: qt_image_bytes.validate(value, pid)
    need(values[0]['relativePath'] == values[1]['relativePath'])
    actual = artifact_member_image(path, digest, values[0]['relativePath'])
    scope = {key: binding[key] for key in ('sourceRevision', 'artifactSha256', 'sessionId', 'generation', 'targetFingerprint')}
    parser = InstalledCodeBinding(SimpleNamespace(read=lambda: deepcopy(record)), scope, actual['bundle'],
        unavailable, unavailable, unavailable)
    saved = parser.record()
    need(saved is not None and saved['phase'] == 'bound' and saved['process']['pid'] == pid)
    image = actual['image']; output = []
    for value in values:
        need(value['instance'] == saved['observation']['instance']
            and value['bundlePreparedEpochMs'] == saved['observation']['preparedEpochMs'])
        compare(value['bundle'], saved['observation']['bundle']); compare(value['bundle'], actual['bundle'])
        need(image['isMainExecutable'] is True and image['fileBytes'] == int(value['fileBytes'])
            and image['fileSha256'] == value['fileSha256'] and image['macho']['uuid'] == value['imageUuid']
            and image['macho']['headerSha256'] == value['headerSha256'])
        offset = int(value['symbolFileOffset'])
        need(any(start <= offset < start + length for start, length in image['macho']['executableFileRanges']))
        output.append(dict(qtEntryImageByteBindingVersion=1, original=deepcopy(value),
            artifactSha256=image['artifactSha256'], bundleSha256=actual['bundle']['bundleSha256'],
            imageBytesBound=True, qtSdkSourceAvailable=False, importGraphAvailable=False, aotGraphAvailable=False))
    return output


def validate(raw, *, binding, artifact, run, first, last, commands, previous_qml=None, historical_links=()):
    view, value = raw['view'], raw['qmlSources']; cut = view['loadedObjectIdentity']
    links = cut['objectLinks']['links']
    need(first['capturedEpochMs'] <= view['capturedEpochMs'] <= cut['cutCompletedEpochMs']
        <= raw['uiAfter']['sampleEpochMs'] <= last['capturedEpochMs'])
    for row in links:
        need(first['capturedEpochMs'] <= row['atWalk']['readBefore']['epochMs'])
    for prior in historical_links: preserve(links, prior)
    if not links:
        # Complete census was already checked by the View-4 codec. A failed or
        # absent QML getter is never interpreted as an absent page.
        need(value is None and raw['qmlBindingOriginal'] is None and raw['qmlEntryBindings'] == [])
        return
    need(type(value) is dict and value.get('iosChatQmlSourcesVersion') == 3)
    query = dict(schemaVersion=1, action=chat_qml_sources.ACTION, commandId=value['requestId'], runId=run)
    chat_qml_sources.validate(value, query, int(binding['processIdentity']), last['capturedEpochMs'], previous_qml)
    need(commands.get(value['requestId']) == query
        and cut['cutCompletedEpochMs'] <= value['clockBefore']['epochMs'] <= value['clockAfter']['epochMs']
        <= raw['uiAfter']['sampleEpochMs'])
    loaded = value['source']; match(cut, loaded)
    from ios.adapters.chat_qml_cache_loaded import compiler_origin
    compiler = compiler_origin(loaded); pin = chat_qml_sources.pins()
    expected_url = raw['scriptRoots']['source']['defaultScriptsUrl'].rstrip('/') + '/' + chat_qml_sources.QML
    need(chat_qml_sources.url(compiler['resolvedUrl']) == chat_qml_sources.url(expected_url)
        and all(compiler[field] == pin[field] for field in ('codeUnits', 'sha256')))
    actual = original_images(raw['qmlBindingOriginal'], [value['qtEntryImage'], value['qtDependencyEntryImage']], artifact, binding)
    need(same(raw['qmlEntryBindings'], actual))
