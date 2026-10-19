//
//  Created by Bradley Austin Davis on 2016/12/12
//  Copyright 2013-2016 High Fidelity, Inc.
//  Copyright 2023 Overte e.V.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//  SPDX-License-Identifier: Apache-2.0
//
#include "TestScriptingInterface.h"

#include <QtCore/QCoreApplication>
#include <QtCore/QLoggingCategory>
#include <QtCore/QSaveFile>
#include <QtCore/QThread>

#include <shared/FileUtils.h>
#include <shared/QtHelpers.h>
#include <DependencyManager.h>
#include <MainWindow.h>
#include <OffscreenUi.h>
#include <ScriptValue.h>
#include <StatTracker.h>
#include <Trace.h>

#include "Application.h"
#include "NetworkingConstants.h"

#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "../../../tests/device/native/FeatureLifecycle.h"
#include "../../../tests/device/native/PrivatePreviewFiles.h"
#include "../../../tests/device/native/PrivateScriptFiles.h"
#include "../../../tests/device/native/PrivateAccountOrigin.h"
#include "../../../tests/device/native/PrivateAccountOriginLease.h"
#include "avatar/AvatarManager.h"
#include "RenderScriptingInterface.h"
#include <AccountManager.h>
#include <AudioClient.h>
#include <avatars-renderer/SkeletonModel.h>
#include <QCryptographicHash>
#include <QDateTime>
#include <QRegularExpression>
#include <QUuid>
#include <QTimer>
#include <ScriptEngines.h>
#include <EntityScriptingInterface.h>
#include <EntityItemProperties.h>
#include <EntityTypes.h>
#include <PickFilter.h>
#include <gpu/Context.h>
#endif

#if defined(OVERTE_E2E_VOICE_TESTS)
#include <AudioClient.h>
#include <QCryptographicHash>
#include <QRegularExpression>
#include <QTimer>
#endif

Q_LOGGING_CATEGORY(trace_test, "trace.test")

TestScriptingInterface* TestScriptingInterface::getInstance() {
    static TestScriptingInterface sharedInstance;
    return &sharedInstance;
}

void TestScriptingInterface::setTestResultsLocation(const QString path) {
    _testResultsLocation = path;
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (!_featureLifecycle && !path.isEmpty() && QCoreApplication::arguments().contains("--testScript")
            && QThread::currentThread() == qApp->thread()) {
        _featureObservationInstance = QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        _featureLifecycle = new overte::e2e::FeatureLifecycle(this);
        _featureLifecycle->start(path); // Failure leaves an unavailable observer.
    }
#endif
}

#if defined(OVERTE_E2E_FEATURE_TESTS)
QVariantMap TestScriptingInterface::featureAccountOrigin(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this,[&] { result=featureAccountOrigin(command); },Qt::BlockingQueuedConnection);
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    if (!_featureAccountOriginLease) { _featureAccountOriginLease=new overte::e2e::AccountOriginLease(this,_featureObservationInstance); }
    return _featureAccountOriginLease->request(_testResultsLocation,command);
}

QVariantMap TestScriptingInterface::featureAccountProbe(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this,[&] { result=featureAccountProbe(command); },Qt::BlockingQueuedConnection);
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    const auto operation=command.value("operation").toString();
    const auto origin=operation=="read" ? overte::e2e::privateAccountOrigin(_testResultsLocation,command.value("runId").toString()) : QString();
    if (operation=="read" && origin.isEmpty()) { return {}; }
    const auto account=DependencyManager::get<AccountManager>();
    QVariantMap result;
    const auto read=[&] { result=account->featureAccountProbe(command,origin); };
    if (QThread::currentThread()==account->thread()) { read(); }
    else { QMetaObject::invokeMethod(account.data(),read,Qt::BlockingQueuedConnection); }
    return result;
}

QVariantMap TestScriptingInterface::featureWorldRenderCapture(const QString& requestId) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this,[&] { result = featureWorldRenderCapture(requestId); },Qt::BlockingQueuedConnection);
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    const auto context = qApp->getGPUContext();
    return context ? context->featureWorldRender()->request(requestId) : QVariantMap();
}

QVariantMap TestScriptingInterface::featureWorldRenderStorage(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this,[&] { result = featureWorldRenderStorage(command); },Qt::BlockingQueuedConnection);
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    const auto context = qApp->getGPUContext();
    return context ? context->featureWorldRender()->storage(command) : QVariantMap();
}

QVariantMap TestScriptingInterface::featureWorldRenderReceipt(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this,[&] { result = featureWorldRenderReceipt(command); },Qt::BlockingQueuedConnection);
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || !overte::e2e::previewDirectory(_testResultsLocation)) { return {}; }
    const auto json = QJsonObject::fromVariantMap(command);
    const auto id = json.value("commandId").toString();
    const auto request = json.value("requestId").toString();
    const auto receipt = json.value("receiptId").toString();
    const auto operation = json.value("operation").toString();
    auto keys = json.keys(); keys.sort();
    if (keys != QStringList{"action","commandId","operation","receiptId","requestId","schemaVersion"}
            || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble() != 1
            || json.value("action").toString() != "feature-world-render-receipt"
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id).hasMatch()
            || (operation != "remove" && operation != "inspect")) { return {}; }
    const auto context = qApp->getGPUContext();
    if (!context) { return {}; }
    const auto state = context->featureWorldRender();
    const auto digest = state->receiptDigest(request,receipt);
    if (digest.isEmpty()) { return {}; } // Only native-issued receipts of a retired acquisition.
    auto nonce = receipt; if (nonce.startsWith("ios-")) { nonce.remove(0,4); }
    const auto path = QDir(_testResultsLocation).filePath("world-render-storage-"+nonce+".json");
    const QFileInfo before(path);
    if (!overte::e2e::ownPreviewFile(path,before.exists() ? digest : QByteArray())) { return {}; }
    QVariantMap source;
    if (operation == "remove") { source.insert("performed",!before.exists() || QFile::remove(path)); }
    else { source.insert("exists",QFileInfo::exists(path)); }
    return {{"receiptVersion",1},{"commandId",id},{"requestId",request},{"receiptId",receipt},
        {"operation",operation},{"instance",state->instance()}, {"sequence",static_cast<qulonglong>(++_featureWorldReceiptSequence)},
        {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()}, {"source",source}};
}

QVariantMap TestScriptingInterface::featureNativeObservation(const QString& requestId) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this, [&] { result = featureNativeObservation(requestId); }, Qt::BlockingQueuedConnection);
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle
            || !QCoreApplication::arguments().contains("--testScript")
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(requestId).hasMatch()) { return {}; }
    if (requestId == _featureCompletedRequest) { return _featureCompletedObservation; }
    const auto lifecycle = _featureLifecycle->snapshot();
    if (lifecycle.isEmpty()) { return {}; }
    const auto avatar = DependencyManager::get<AvatarManager>()->getMyAvatar();
    if (!avatar) { return {}; }
    const auto model = avatar->getSkeletonModel();
    const auto animation = model ? model->getRig().e2eAnimationObservation() : QVariantMap();
    if (requestId != _featurePendingRequest) {
        _featurePendingRequest = requestId;
        _featurePendingEpochMs = QDateTime::currentMSecsSinceEpoch();
        _featurePendingAnimationSequence = animation.value("evaluationSequence").toULongLong();
        _featurePendingRigId = animation.value("rigId", -1).toInt();
        _featurePendingAnimationFence = animation.value("graphLoaded").toBool()
            && animation.value("animationsEnabled").toBool();
    }
    QVariantMap animationFence;
    if (_featurePendingAnimationFence) {
        if (animation.value("rigId", -1).toInt() != _featurePendingRigId) { return {}; }
        if (animation.value("evaluationSequence").toULongLong() <= _featurePendingAnimationSequence
                || animation.value("capturedEpochMs").toLongLong() < _featurePendingEpochMs) {
            // Never block the GUI/animation owner. The probe retries this
            // read-only request ID until an actual later evaluation exists.
            return {{"schemaVersion", 1}, {"requestId", requestId}, {"pending", true}};
        }
        animationFence = {{"rigId", _featurePendingRigId},
            {"sequence", static_cast<qulonglong>(_featurePendingAnimationSequence)},
            {"requestedEpochMs", _featurePendingEpochMs}};
    }
    auto render = RenderScriptingInterface::getInstance();
    QVariantMap graphics {{"requestedResolutionScale", render->getViewportResolutionScale()},
        {"applicationResolutionScale", qApp->getRenderResolutionScale()},
        {"shadowsSetting", render->getShadowsEnabled()}, {"mirrorsSetting", render->getMirrorsEnabled()},
        {"hazeSetting", render->getHazeEnabled()}, {"localLightingSetting", render->getLocalLightingEnabled()},
        {"proceduralMaterialsSetting", render->getProceduralMaterialsEnabled()},
        {"deferredRenderingAvailable", render->isDeferredRenderingAvailable()}};
    QVariantMap audioState;
    const auto audio = DependencyManager::get<AudioClient>();
    const auto readAudio = [&] { audioState = {{"recording", audio->getRecording()}, {"muted", audio->isMuted()},
        {"recordedVoice", audio->featureRecordedVoiceObservation()}}; };
    if (QThread::currentThread() == audio->thread()) { readAudio(); }
    else { QMetaObject::invokeMethod(audio.data(), readAudio, Qt::BlockingQueuedConnection); }
    QVariantMap accountState;
    const auto account = DependencyManager::get<AccountManager>();
    const auto readAccount = [&] {
        // Passive source: ordinary isLoggedIn() can refresh credentials.
        accountState = account->featureAccountObservation();
    };
    if (QThread::currentThread() == account->thread()) { readAccount(); }
    else { QMetaObject::invokeMethod(account.data(), readAccount, Qt::BlockingQueuedConnection); }
    QVariantMap result {{"schemaVersion", 1}, {"requestId", requestId}, {"instance", _featureObservationInstance},
        {"sequence", static_cast<qulonglong>(++_featureObservationSequence)},
        {"capturedEpochMs", QDateTime::currentMSecsSinceEpoch()}, {"requestedEpochMs", _featurePendingEpochMs},
        {"processId", QCoreApplication::applicationPid()}, {"lifecycle", lifecycle.toVariantMap()},
        {"animation", animation}, {"animationFence", animationFence},
        {"graphics", graphics}, {"audio", audioState}, {"account", accountState}};
    _featureCompletedRequest = requestId;
    _featureCompletedObservation = result;
    return result;
}

QVariantMap TestScriptingInterface::featureRecordedVoiceEvidence(const QString& requestId) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this, [&] { result = featureRecordedVoiceEvidence(requestId); }, Qt::BlockingQueuedConnection);
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(requestId).hasMatch()
            || !overte::e2e::previewDirectory(_testResultsLocation)) { return {}; }
    if (_featurePreviewRequest == requestId) { return _featurePreviewObservation; }
    const auto requested = QDateTime::currentMSecsSinceEpoch();
    QVariantMap source;
    const auto audio = DependencyManager::get<AudioClient>();
    const auto read = [&] { source = audio->featureRecordedVoiceEvidence(); };
    if (QThread::currentThread() == audio->thread()) { read(); }
    else { QMetaObject::invokeMethod(audio.data(), read, Qt::BlockingQueuedConnection); }
    if (source.isEmpty()) { return {}; }
    const auto input = source.take("inputPcm").toByteArray();
    const auto sink = source.take("sinkPcm").toByteArray();
    QDir directory(_testResultsLocation);
    if (!overte::e2e::writePreviewFile(directory.filePath("recorded-preview-input.pcm16le"), input, _featurePreviewInputDigest)
            || !overte::e2e::writePreviewFile(directory.filePath("recorded-preview-sink.pcm16le"), sink, _featurePreviewSinkDigest)) { return {}; }
    const auto artifact = [&](const char* name, const char* tap, const QByteArray& bytes, const QByteArray& digest) {
        return QVariantMap{{"name", QString::fromLatin1(name)}, {"tap", QString::fromLatin1(tap)},
            {"bytes", bytes.size()}, {"sha256", QString::fromLatin1(digest)}};
    };
    source["input"] = artifact("recorded-preview-input.pcm16le", "capture-before-normalization", input, _featurePreviewInputDigest);
    source["sink"] = artifact("recorded-preview-sink.pcm16le", "loopback-device-accepted-write", sink, _featurePreviewSinkDigest);
    QVariantMap result{{"schemaVersion", 1}, {"requestId", requestId}, {"instance", _featureObservationInstance},
        {"sequence", static_cast<qulonglong>(++_featurePreviewSequence)}, {"requestedEpochMs", requested},
        {"capturedEpochMs", QDateTime::currentMSecsSinceEpoch()}, {"processId", QCoreApplication::applicationPid()},
        {"source", source}};
    _featurePreviewRequest = requestId;
    _featurePreviewObservation = result;
    const auto lease = ++_featurePreviewLease;
    QTimer::singleShot(30000, this, [this, lease, requestId] {
        if (_featurePreviewLease == lease) { releaseFeatureRecordedVoiceEvidence(requestId); }
    });
    return result;
}

QVariantMap TestScriptingInterface::releaseFeatureRecordedVoiceEvidence(const QString& requestId) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this, [&] { result = releaseFeatureRecordedVoiceEvidence(requestId); }, Qt::BlockingQueuedConnection);
        return result;
    }
    if (_testResultsLocation.isEmpty() || !QCoreApplication::arguments().contains("--testScript")
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(requestId).hasMatch()
            || !overte::e2e::previewDirectory(_testResultsLocation)) { return {}; }
    const auto audio = DependencyManager::get<AudioClient>();
    bool memoryCleared = false;
    const auto clear = [&] {
        audio->releaseFeatureRecordedVoiceEvidence();
        memoryCleared = audio->featureRecordedVoiceEvidence().isEmpty();
    };
    if (QThread::currentThread() == audio->thread()) { clear(); }
    else { QMetaObject::invokeMethod(audio.data(), clear, Qt::BlockingQueuedConnection); }
    const QDir directory(_testResultsLocation);
    const bool inputRemoved = overte::e2e::removePreviewFile(directory.filePath("recorded-preview-input.pcm16le"), _featurePreviewInputDigest);
    const bool sinkRemoved = overte::e2e::removePreviewFile(directory.filePath("recorded-preview-sink.pcm16le"), _featurePreviewSinkDigest);
    _featurePreviewRequest.clear(); _featurePreviewObservation.clear(); ++_featurePreviewLease;
    return {{"schemaVersion", 1}, {"requestId", requestId}, {"released", memoryCleared && inputRemoved && sinkRemoved}};
}

QVariantMap TestScriptingInterface::featureRecordedVoiceFiles(const QString& requestId) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this, [&] { result = featureRecordedVoiceFiles(requestId); }, Qt::BlockingQueuedConnection);
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(requestId).hasMatch()
            || !overte::e2e::previewDirectory(_testResultsLocation)) { return {}; }
    const auto requested = QDateTime::currentMSecsSinceEpoch();
    const auto audio = DependencyManager::get<AudioClient>();
    bool memoryEmpty = false;
    const auto read = [&] { memoryEmpty = audio->featureRecordedVoiceEvidence().isEmpty(); };
    if (QThread::currentThread() == audio->thread()) { read(); }
    else { QMetaObject::invokeMethod(audio.data(), read, Qt::BlockingQueuedConnection); }
    QVariantList files;
    for (const auto& name : {QStringLiteral("recorded-preview-input.pcm16le"), QStringLiteral("recorded-preview-sink.pcm16le")}) {
        const QFileInfo info(QDir(_testResultsLocation).filePath(name));
        files.append(QVariantMap{{"name", name}, {"exists", info.exists() || info.isSymLink()}});
    }
    return {{"schemaVersion", 1}, {"requestId", requestId}, {"instance", _featureObservationInstance},
        {"sequence", static_cast<qulonglong>(++_featurePreviewSequence)}, {"requestedEpochMs", requested},
        {"capturedEpochMs", QDateTime::currentMSecsSinceEpoch()}, {"processId", QCoreApplication::applicationPid()},
        {"memoryEmpty", memoryEmpty}, {"files", files}};
}

QVariantMap TestScriptingInterface::featureScriptFiles(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this, [&] { result = featureScriptFiles(command); }, Qt::BlockingQueuedConnection);
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    const auto json = QJsonObject::fromVariantMap(command);
    const auto action = json.value("operation").toString();
    QStringList expected {"schemaVersion", "commandId", "action", "operation", "runId", "ownerToken"};
    if (action == "stage") { expected.append("files"); }
    auto keys = json.keys(); expected.sort(); keys.sort();
    const auto id = json.value("commandId").toString();
    if (keys != expected || json.value("schemaVersion") != QJsonValue(1)
            || !json.value("runId").isString() || !json.value("ownerToken").isString()
            || !json.value("operation").isString()
            || json.value("action") != QJsonValue(QStringLiteral("feature-script-files"))
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id).hasMatch()
            || QJsonDocument(json).toJson(QJsonDocument::Compact).size() > 49152) { return {}; }
    if (_featureScriptFilesCommand.value("commandId") == QVariant(id)) {
        return command == _featureScriptFilesCommand ? _featureScriptFilesResult : QVariantMap{};
    }
    const auto requested = QDateTime::currentMSecsSinceEpoch();
    const auto source = overte::e2e::PrivateScriptFiles::request(_testResultsLocation, command);
    QVariantMap result{{"schemaVersion", 1}, {"requestId", id}, {"instance", _featureObservationInstance},
        {"sequence", static_cast<qulonglong>(++_featureScriptFilesSequence)}, {"requestedEpochMs", requested},
        {"capturedEpochMs", QDateTime::currentMSecsSinceEpoch()}, {"processId", QCoreApplication::applicationPid()},
        {"runId", command.value("runId")}, {"operation", action}, {"source", source}};
    _featureScriptFilesCommand = command; _featureScriptFilesResult = result;
    return result;
}

QVariantMap TestScriptingInterface::featureScriptObservation(const QString& requestId) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this, [&] { result = featureScriptObservation(requestId); }, Qt::BlockingQueuedConnection);
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(requestId).hasMatch()) { return {}; }
    const auto requested = QDateTime::currentMSecsSinceEpoch();
    // Atomic manager membership plus locked source histories; never invoke or
    // evaluate code on every script thread while the probe's thread is waiting.
    auto source = DependencyManager::get<ScriptEngines>()->featureScriptObservation();
    if (source.isEmpty()) { return {}; }
    const auto entities = DependencyManager::get<EntityScriptingInterface>();
    const auto avatars = DependencyManager::get<AvatarManager>();
    if (!entities || !entities->getEntityTree() || !avatars || !avatars->getMyAvatar()) { return {}; }
    // Independent application entity reads, not values returned by the loaded
    // fixture script. No requested name, run, tick, color or effect is input.
    const auto ids = entities->findEntities(avatars->getMyAvatarPosition(), 64.0f,
        PickFilter::getBitMask(PickFilter::FlagBit::LOCAL_ENTITIES) | PickFilter::getBitMask(PickFilter::FlagBit::COARSE));
    if (ids.size() > 4096) { return {}; }
    QVariantList effects, absent;
    static const QRegularExpression fixtureName("\\Ae2e-[0-9a-f]{32}-script\\z");
    for (const auto& id : ids) {
        if (fixtureName.match(entities->getEntityProperties(id).getName()).hasMatch()) {
            _featureScriptEffectIds.insert(id);
        }
    }
    if (_featureScriptEffectIds.size() > 256) { return {}; }
    // Keep querying every observed UUID even after it moves outside the scan
    // radius or is renamed. A hidden/moved object cannot become fake cleanup.
    for (const auto& id : _featureScriptEffectIds) {
        const auto properties = entities->getEntityProperties(id);
        if (properties.getType() == EntityTypes::Unknown) {
            absent.append(id.toString(QUuid::WithoutBraces)); continue;
        }
        const auto name = properties.getName();
        if (effects.size() >= 32 || name.size() > 256 || properties.getUserData().size() > 1024) { return {}; }
        const auto host = properties.getEntityHostType();
        const auto hostName = host == entity::HostType::LOCAL ? QStringLiteral("local")
            : host == entity::HostType::AVATAR ? QStringLiteral("avatar") : QStringLiteral("domain");
        const auto color = properties.getColor();
        effects.append(QVariantMap{{"id", id.toString(QUuid::WithoutBraces)}, {"name", name},
            {"type", EntityTypes::getEntityTypeName(properties.getType())}, {"hostType", hostName},
            {"userData", properties.getUserData()}, {"lastEditedEpochUs", static_cast<qulonglong>(properties.getLastEdited())},
            {"color", QVariantList{static_cast<int>(color.x), static_cast<int>(color.y), static_cast<int>(color.z)}}});
    }
    source["effectSourceVersion"] = 1;
    source["effects"] = QVariantMap{{"complete", true}, {"scanRadiusMeters", 64},
        {"scannedEntities", ids.size()}, {"entities", effects}, {"absentIds", absent}};
    if (QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size() > 240000) { return {}; }
    return {{"schemaVersion", 1}, {"requestId", requestId}, {"instance", _featureObservationInstance},
        {"sequence", static_cast<qulonglong>(++_featureScriptSequence)}, {"requestedEpochMs", requested},
        {"capturedEpochMs", QDateTime::currentMSecsSinceEpoch()}, {"processId", QCoreApplication::applicationPid()},
        {"source", source}};
}
#endif

#if defined(OVERTE_E2E_VOICE_TESTS)
QVariantMap TestScriptingInterface::voiceTest(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this, [&] { result = voiceTest(command); }, Qt::BlockingQueuedConnection);
        return result;
    }
    const QString id = command.value("commandId").toString();
    QVariantMap result { { "schemaVersion", 1 }, { "commandId", id }, { "ok", false } };
    // Both an explicit test build and an active test-script launch are required.
    if (_testResultsLocation.isEmpty() || !QCoreApplication::arguments().contains("--testScript") ||
        command.value("schemaVersion").toInt() != 1 ||
        !QRegularExpression("^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$").match(id).hasMatch()) {
        result["error"] = "voice-test-not-enabled";
        return result;
    }
    auto audio = DependencyManager::get<AudioClient>();
    const auto onAudio = [&](const std::function<void()>& callback) {
        if (QThread::currentThread() == audio->thread()) { callback(); }
        else { QMetaObject::invokeMethod(audio.data(), callback, Qt::BlockingQueuedConnection); }
    };
    const auto appendAudioStatus = [&] {
        onAudio([&] {
            const auto status = audio->voiceTestStatus();
            for (auto it = status.cbegin(); it != status.cend(); ++it) { result[it.key()] = it.value(); }
        });
    };
    const QString action = command.value("action").toString();
    if (action == "prepare") {
        if (audio->getRecording() || !_voiceCapturePath.isEmpty()) {
            result["error"] = "voice-recording-busy";
            return result;
        }
        bool prepared = false;
        onAudio([&] { prepared = audio->prepareVoiceTest(); });
        if (!prepared) { result["error"] = "voice-source-unavailable"; appendAudioStatus(); return result; }
    } else if (action == "send") {
        const QString challenge = command.value("challenge").toString();
        if (!QRegularExpression("^[0-9a-f]{32}$").match(challenge).hasMatch()) {
            result["error"] = "voice-invalid-challenge";
            return result;
        }
        const QByteArray digest = QCryptographicHash::hash("overte-voice-v1:" + challenge.toLatin1(), QCryptographicHash::Sha256);
        std::array<int, 12> symbols;
        symbols[0] = static_cast<unsigned char>(digest[0]) % 8;
        for (int i = 1; i < 12; ++i) { symbols[i] = (symbols[i - 1] + 1 + static_cast<unsigned char>(digest[i]) % 7) % 8; }
        bool sent = false;
        onAudio([&] { sent = audio->sendVoiceTest(symbols); });
        if (!sent) { result["error"] = "voice-send-unavailable"; appendAudioStatus(); return result; }
    } else if (action == "capture-start") {
        const int seconds = command.value("seconds").toInt();
        if (seconds < 6 || seconds > 10 || audio->getRecording() || !_voiceCapturePath.isEmpty()) {
            result["error"] = "voice-invalid-capture";
            return result;
        }
        QDir directory(_testResultsLocation);
        if (!directory.exists()) { result["error"] = "voice-results-unavailable"; return result; }
        _voiceCapturePath = directory.absoluteFilePath("voice-" + id + ".wav");
        // Never overwrite an unrelated or stale recording.
        if (QFile::exists(_voiceCapturePath) || !audio->startRecording(_voiceCapturePath)) {
            _voiceCapturePath.clear();
            result["error"] = "voice-capture-unavailable";
            return result;
        }
        QFile::setPermissions(_voiceCapturePath, QFile::ReadOwner | QFile::WriteOwner);
        const quint64 generation = ++_voiceCaptureGeneration;
        QTimer::singleShot(seconds * 1000, this, [this, audio, generation] {
            if (_voiceCaptureGeneration == generation && !_voiceCapturePath.isEmpty()) { audio->stopRecording(); }
        });
        QTimer::singleShot((seconds + 30) * 1000, this, [this, audio, generation] {
            if (_voiceCaptureGeneration == generation && !_voiceCapturePath.isEmpty()) {
                audio->stopRecording();
                QFile::remove(_voiceCapturePath);
                _voiceCapturePath.clear();
            }
        });
    } else if (action == "capture-stop") {
        if (_voiceCapturePath.isEmpty()) { result["error"] = "voice-no-capture"; return result; }
        audio->stopRecording();
        QFile capture(_voiceCapturePath);
        if (!capture.open(QIODevice::ReadOnly) || capture.size() > 5 * 1024 * 1024) {
            result["error"] = "voice-capture-invalid";
        } else {
            const QByteArray wav = capture.readAll();
            result["wavBase64"] = QString::fromLatin1(wav.toBase64());
            result["sha256"] = QString::fromLatin1(QCryptographicHash::hash(wav, QCryptographicHash::Sha256).toHex());
            result["ok"] = true;
        }
        capture.close();
        QFile::remove(_voiceCapturePath);
        _voiceCapturePath.clear();
        ++_voiceCaptureGeneration;
        return result;
    } else if (action == "reset") {
        onAudio([&] { audio->resetVoiceTest(); });
        if (!_voiceCapturePath.isEmpty()) { audio->stopRecording(); QFile::remove(_voiceCapturePath); _voiceCapturePath.clear(); }
        ++_voiceCaptureGeneration;
    } else if (action != "status") {
        result["error"] = "voice-invalid-action";
        return result;
    }
    onAudio([&] { audio->touchVoiceTest(); });
    appendAudioStatus();
    result["ok"] = true;
    return result;
}
#endif

void TestScriptingInterface::quit() {
    qApp->quit();
}

void TestScriptingInterface::waitForTextureIdle() {
    waitForCondition(0, []()->bool {
        return (0 == gpu::Context::getTexturePendingGPUTransferCount());
    });
}

void TestScriptingInterface::waitForDownloadIdle() {
    waitForCondition(0, []()->bool {
        return (0 == ResourceCache::getLoadingRequestCount()) && (0 == ResourceCache::getPendingRequestCount());
    });
}

void TestScriptingInterface::waitForProcessingIdle() {
    auto statTracker = DependencyManager::get<StatTracker>();
    waitForCondition(0, [statTracker]()->bool {
        return (0 == statTracker->getStat("Processing").toInt() && 0 == statTracker->getStat("PendingProcessing").toInt());
    });
}

void TestScriptingInterface::waitIdle() {
    // Initial wait for some incoming work
    QThread::sleep(1);
    waitForDownloadIdle();
    waitForProcessingIdle();
    waitForTextureIdle();
}

bool TestScriptingInterface::loadTestScene(QString scene) {
    if (QThread::currentThread() != thread()) {
        bool result;
        BLOCKING_INVOKE_METHOD(this, "loadTestScene", Q_RETURN_ARG(bool, result), Q_ARG(QString, scene));
        return result;
    }

    static const QString TEST_ROOT = "https://raw.githubusercontent.com/hifi-archive/hifi_tests/master/";
    static const QString TEST_BINARY_ROOT = NetworkingConstants::HF_CONTENT_CDN_URL + "test_scene_data/";
    static const QString TEST_SCRIPTS_ROOT = TEST_ROOT + "scripts/";
    static const QString TEST_SCENES_ROOT = TEST_ROOT + "scenes/";
    
    DependencyManager::get<ResourceManager>()->setUrlPrefixOverride("atp:/", TEST_BINARY_ROOT + scene + ".atp/");
    auto tree = qApp->getEntities()->getTree();
    auto treeIsClient = tree->getIsClient();
    // Force the tree to accept the load regardless of permissions
    tree->setIsClient(false);
    auto result = tree->readFromURL(TEST_SCENES_ROOT + scene + ".json");
    tree->setIsClient(treeIsClient);
    return result;
}

bool TestScriptingInterface::startTracing(QString logrules) {
    if (!logrules.isEmpty()) {
        QLoggingCategory::setFilterRules(logrules);
    }

    if (!DependencyManager::isSet<tracing::Tracer>()) {
        return false;
    }

    DependencyManager::get<tracing::Tracer>()->startTracing();
    return true;
}

bool TestScriptingInterface::stopTracing(QString filename) {
    if (!DependencyManager::isSet<tracing::Tracer>()) {
        return false;
    }

    auto tracer = DependencyManager::get<tracing::Tracer>();
    tracer->stopTracing();
    tracer->serialize(filename);
    return true;
}

void TestScriptingInterface::clear() {
    qApp->postLambdaEvent([] {
        qApp->getEntities()->clear();
    });
}

bool TestScriptingInterface::waitForConnection(qint64 maxWaitMs) {
    // Wait for any previous connection to die
    QThread::sleep(1);
    return waitForCondition(maxWaitMs, []()->bool {
        return DependencyManager::get<NodeList>()->getDomainHandler().isConnected();
    });
}

void TestScriptingInterface::wait(int milliseconds) {
    QThread::msleep(milliseconds);
}

bool TestScriptingInterface::waitForCondition(qint64 maxWaitMs, std::function<bool()> condition) {
    QElapsedTimer elapsed;
    elapsed.start();
    while (!condition()) {
        if (maxWaitMs > 0 && elapsed.elapsed() > maxWaitMs) {
            return false;
        }
        QThread::msleep(1);
    }
    return condition();
}

void TestScriptingInterface::startTraceEvent(QString name) {
    tracing::traceEvent(trace_test(), name, tracing::DurationBegin, "");
}

void TestScriptingInterface::endTraceEvent(QString name) {
    tracing::traceEvent(trace_test(), name, tracing::DurationEnd);
}

void TestScriptingInterface::savePhysicsSimulationStats(QString originalPath) {
    QString path = FileUtils::replaceDateTimeTokens(originalPath);
    path = FileUtils::computeDocumentPath(path);
    if (!FileUtils::canCreateFile(path)) {
        return;
    }
    qApp->saveNextPhysicsStats(path);
}

void TestScriptingInterface::profileRange(const QString& name, const ScriptValue& fn) {
    PROFILE_RANGE(script, name);
    fn.call();
}

void TestScriptingInterface::clearCaches() {
	qApp->reloadResourceCaches();
}

// Writes a JSON object from javascript to a file
void TestScriptingInterface::saveObject(QVariant variant, const QString& filename) {
    if (_testResultsLocation.isNull()) {
        return;
    }
    if (filename.isEmpty() || QFileInfo(filename).fileName() != filename) {
        return;
    }

    QJsonDocument jsonDocument;
    jsonDocument = QJsonDocument::fromVariant(variant);
    if (jsonDocument.isNull()) {
        return;
    }

    QByteArray jsonData = jsonDocument.toJson();

    // Append trailing slash if needed
    if (_testResultsLocation.right(1) != "/") {
        _testResultsLocation += "/";
    }

    QString filepath = QDir::cleanPath(_testResultsLocation + filename);
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (filename == "feature-native-observation.json" || filename == "normal-feature-observation.json"
            || filename == "recorded-preview-observation.json" || filename == "feature-script-observation.json"
            || filename == "feature-script-files.json" || filename == "world-render-observation.json"
            || filename == "world-render-receipt-result.json"
            || QRegularExpression("\\Aworld-render-storage-[0-9a-f]{32}\\.json\\z").match(filename).hasMatch()) {
        if (!QCoreApplication::arguments().contains("--testScript") || QFileInfo(filepath).isSymLink()) { return; }
        if (filename.startsWith("world-render-storage-")) {
            const auto context = qApp->getGPUContext();
            const auto value = variant.toMap();
            if (!context || !overte::e2e::previewDirectory(_testResultsLocation)) { return; }
            auto nonce = value.value("commandId").toString();
            if (nonce.startsWith("ios-")) { nonce.remove(0,4); }
            if (filename != "world-render-storage-"+nonce+".json") { return; }
            const auto digest = context->featureWorldRender()->receiptDigest(
                value.value("requestId").toString(),value.value("commandId").toString(),false);
            if (digest.isEmpty() || QCryptographicHash::hash(jsonData,QCryptographicHash::Sha256).toHex() != digest) { return; }
            if (QFileInfo::exists(filepath)) {
                // Immutable native-issued content may already have been saved.
                // Never overwrite/adopt a foreign document at the nonce path.
                if (!overte::e2e::ownPreviewFile(filepath,digest)) { return; }
                return;
            }
        }
        QSaveFile output(filepath);
        output.setDirectWriteFallback(false);
        if (output.open(QIODevice::WriteOnly) && output.setPermissions(QFile::ReadOwner | QFile::WriteOwner)
                && output.write(jsonData) == jsonData.size()) { output.commit(); }
        return;
    }
#endif
    QSaveFile file(filepath);
    if (!file.open(QFile::WriteOnly)) {
        return;
    }
    if (file.write(jsonData) != jsonData.size()) {
        file.cancelWriting();
        return;
    }
    if (!file.commit()) {
        return;
    }
}

void TestScriptingInterface::showMaximized() {
    qApp->getWindow()->showMaximized();
}

void TestScriptingInterface::setOtherAvatarsReplicaCount(int count) {
    qApp->setOtherAvatarsReplicaCount(count);
}

int TestScriptingInterface::getOtherAvatarsReplicaCount() {
    return qApp->getOtherAvatarsReplicaCount();
}

void TestScriptingInterface::setMinimumGPUTextureMemStabilityCount(int count) {
    QMetaObject::invokeMethod(qApp, "setMinimumGPUTextureMemStabilityCount", Qt::DirectConnection, Q_ARG(int, count));
}

bool TestScriptingInterface::isTextureLoadingComplete() {
    bool result;
    QMetaObject::invokeMethod(qApp, "gpuTextureMemSizeStable", Qt::DirectConnection, Q_RETURN_ARG(bool, result));
    return result;
}
