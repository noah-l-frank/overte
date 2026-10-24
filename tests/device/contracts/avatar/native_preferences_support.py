"""Shared original Avatar preference preparation for owning native host cases."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from contextlib import nullcontext
import os
import tempfile


def function(source, signature):
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def prepare(stage, root):
    """Keep full original bodies, declarations and initializer keys identical."""
    interface = (root / 'libraries/shared/src/SettingInterface.cpp').read_text()
    code = '\n'.join(function(interface, '    void Interface::' + name + '(')
                     for name in ('init', 'deinit', 'maybeInit', 'save', 'load'))
    code += '\n' + function(interface, '    AvatarPreferenceMutation::AvatarPreferenceMutation(')
    code += '\n' + next(line for line in interface.splitlines()
                        if 'AvatarPreferenceMutation::~AvatarPreferenceMutation()' in line)
    code += '\n' + function(interface, '    QVariantMap Interface::e2ePreferenceInterface(')
    avatar = (root / 'interface/src/avatar/MyAvatar.cpp').read_text()
    header = (root / 'interface/src/avatar/MyAvatar.h').read_text()
    fields = header[header.index('    Setting::Handle<QString> _dominantHandSetting;'):
                    header.index('    // AvatarEntities stuff:')]
    initializers = avatar[avatar.index('    _dominantHandSetting('):
                          avatar.index('    _clientTraitsHandler.reset')]
    initializers = initializers[:initializers.rindex(' {')]
    (stage / 'actual-setting-interface.inc').write_text(code)
    (stage / 'actual-avatar-handles.inc').write_text(fields)
    (stage / 'actual-avatar-preferences.inc').write_text(
        'MyAvatar::MyAvatar():\n' + initializers + ' {}\n' +
        function(avatar, 'QVariantMap MyAvatar::e2ePreferenceHandles('))
    (stage / 'actual-getter.inc').write_text(function(
        (root / 'interface/src/scripting/TestScriptingInterface.cpp').read_text(),
        'QVariantMap TestScriptingInterface::featurePicoAvatarPreferences('))


def prepare_ui_host(stage, root, *, original_model=False):
    """Reuse the existing native preference actor declarations and getter.

    Avatar/model values remain declared host boundaries; original lazy Handles,
    Manager/worker, file reader and the whole passive native getter are shared.
    """
    prepare(stage, root)
    native = Path(__file__).with_name('avatar-preferences-native.cpp').read_text()
    prefix = native[:native.index('struct Camera{')]
    if original_model:
        prefix=native[:native.index('// Explicit application/dependency-registry')]
        prefix+='#include <SharedUtil.h>\n#include "avatar-original-model-receiver.h"\n'
    constants = native[native.index('const QString SETTINGS_FULL_PRIVATE_GROUP_NAME='):
                       native.index('class MyAvatar:public QObject')]
    # Actual scale clamp/body and clock; preserve the existing explicit model
    # actor without replacing the Favorite callback's scale or empty-clear call.
    constants = constants.replace('struct AvatarData{', 'struct AvatarData{void setTargetScale(float);float _targetScale{1};quint64 _scaleChanged{0},_avatarScaleChanged{0};')
    if original_model:
        constants=constants.replace('const QString SETTINGS_FULL_PRIVATE_GROUP_NAME="fullPrivate";','')
        a=constants.index('struct Model:QObject');b=constants.index(';',constants.index('}};',a))+1
        constants=constants[:a]+constants[b:]
        constants=constants.replace('struct AvatarData{','struct AvatarData{QUrl _skeletonModelURL;void setSkeletonModelURL(const QUrl& value){_skeletonModelURL=value;}')
    shared = (root / 'libraries/shared/src/SharedUtil.cpp').read_text()
    bounds = (root / 'libraries/shared/src/AvatarConstants.h').read_text()
    scale = '\n'.join(line for line in bounds.splitlines()
                      if line.startswith(('static const float MIN_AVATAR_SCALE =', 'static const float MAX_AVATAR_SCALE =')))
    if not original_model:
        scale += '\nstatic qint64 usecTimestampNowAdjust = 0;\nquint64 usecTimestampNow(bool wantDebug=false);\n'
        scale += function(shared, 'quint64 usecTimestampNow(')
    scale += '\n' + function((root / 'libraries/avatars/src/AvatarData.cpp').read_text(), 'void AvatarData::setTargetScale(')
    (stage / 'actual-avatar-preference-host.inc').write_text(prefix + '#include <chrono>\n' + constants + scale)
    avatar = (root / 'interface/src/avatar/MyAvatar.cpp').read_text()
    (stage / 'actual-avatar-persistence.inc').write_text('\n'.join(function(avatar, signature) for signature in (
        'void MyAvatar::setSkeletonModelURL(', 'void MyAvatar::saveAvatarUrl(', 'QVariantMap MyAvatar::e2eModelConnections(')))
    getter = function((root / 'interface/src/scripting/TestScriptingInterface.cpp').read_text(),
        'QVariantMap TestScriptingInterface::featurePicoAvatarPreferences(')
    (stage / 'actual-avatar-native-data.inc').write_text('auto typedHandles=' + function(getter,'[avatar,model]') + ';\n')
    # Preserve the complete original tag enums without pulling the uncompiled
    # rendering stack into the declared scene/Model actor boundary.
    item_tags = function((root / 'libraries/render/src/render/Item.h').read_text(), '    enum Tag : uint8_t')
    hifi_tags = function((root / 'libraries/render-utils/src/RenderHifi.h').read_text(), '        enum Tag : uint8_t')
    (stage / 'actual-avatar-render-tags.inc').write_text(
        '#include <cstdint>\nnamespace render {class ItemKey {public:\n' + item_tags +
        ';};namespace hifi {\n' + hifi_tags + ';}}\n')
    observer = native[native.index('class AvatarManager:public Dependency'):
                      native.index('void output(')]
    # The existing UI Bookmarks endpoint already owns the one live Avatar.
    # Inject that same object; do not construct/destroy an unused Handle owner.
    observer = observer.replace(
        'std::shared_ptr<MyAvatar>avatar{new MyAvatar};',
        'std::shared_ptr<MyAvatar>avatar;explicit AvatarManager(std::shared_ptr<MyAvatar> existing):avatar(std::move(existing)){}')
    # The live parent mode reuses the complete original readonly endpoint.
    # Other native modes retain precisely their original declaration profile.
    observer=observer.replace('    QVariantMap featurePicoAvatarPreferences(const QVariantMap&command);',
        '    QVariantMap featurePicoAvatarPreferences(const QVariantMap&command);\n'
        '#if defined(AVATAR_ORIGINAL_PARENT_SERVICE)\n'
        '    QVariantMap featurePicoAvatarModelConnections(const QVariantMap&);\n'
        '    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureAvatarModelConnectionsQueue{new overte::e2e::AudioSettingsQueue};\n'
        '    quint64 _featureAvatarModelConnectionsSequence{0};QSet<QString> _featureAvatarModelConnectionsRequests;\n'
        '    QPointer<QObject> _featureAvatarModelConnectionObject;QString _featureAvatarModelConnectionBirth;\n'
        '#endif')
    observer+='\n#if defined(AVATAR_ORIGINAL_PARENT_SERVICE)\n'+function(
        (root/'interface/src/scripting/TestScriptingInterface.cpp').read_text(),
        'QVariantMap TestScriptingInterface::featurePicoAvatarModelConnections(')+'\n#endif\n'
    (stage / 'actual-avatar-preference-observer.inc').write_text(
        'using MyAvatar=avatar_bookmark_host::MyAvatar;\n' + observer)


def native_stage(prefix):
    """Optionally retain full generated inputs, binaries and raw host streams."""
    root = os.environ.get('OVERTE_AVATAR_NATIVE_ARTIFACTS')
    return (nullcontext(tempfile.mkdtemp(prefix=prefix, dir=root)) if root
            else tempfile.TemporaryDirectory(prefix=prefix))
