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
#include <QtCore/QThread>
#if defined(Q_OS_IOS)
#include <QSaveFile>
#endif

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
#if defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "../IOSTouchUiMetrics.h"
#include "EntityScriptConsentUiTest.h"
#include "../../../ios/ui/IOSSnapshotFiles.h"
#include "../ui/SnapshotStorage.h"
#include <AddressManager.h>
#include <cstdlib>
#include <QDateTime>
#include <QRegularExpression>
#include <QInputMethod>
#include <QPointer>
#include <QQuickItem>
#include <QSemaphore>
#include <QThreadPool>
#include <QTimer>
#include <ui/TabletScriptingInterface.h>
#include <display-plugins/VulkanDisplayPlugin.h>
#include <vk/Context.h>
#include <shared/IOSRuntimeLogging.h>
#endif

#if defined(OVERTE_E2E_VOICE_TESTS)
#include <AudioClient.h>
#include <AudioInjectorManager.h>
#include <IOSAudioPermission.h>
#include <vector>
#include <QCryptographicHash>
#include <QRegularExpression>
#include <QTimer>
#endif

#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "../../../tests/device/native/FeatureLifecycle.h"
#include "../../../tests/device/native/NormalAudioControls.h"
#include "../../../tests/device/native/NormalGraphicsControls.h"
#include "../../../tests/device/native/PrivatePreviewFiles.h"
#include "../../../tests/device/native/PrivateScriptFiles.h"
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

#if defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
bool TestScriptingInterface::iosCrashTest(const QVariantMap& command) {
    const QString id = command.value("commandId").toString();
    if (_testResultsLocation.isEmpty() || !QCoreApplication::arguments().contains("--testScript") ||
            command.size() != 3 || command.value("schemaVersion").toInt() != 1 ||
            command.value("action").toString() != "native-crash" ||
            !QRegularExpression("^ios-[0-9a-f]{32}$").match(id).hasMatch()) { return false; }
    QTimer::singleShot(100, this, [this, id] {
        // This receipt is published at the actual firing boundary, immediately
        // before the real native abort. Delivery or arming alone is not evidence.
        saveObject(QVariantMap {
            { "schemaVersion", 1 }, { "commandId", id }, { "phase", "firing" },
            { "cause", "SIGABRT" }, { "sampleEpochMs", QDateTime::currentMSecsSinceEpoch() },
            { "processId", QCoreApplication::applicationPid() }
        }, "ios-crash-result.json");
        std::abort();
    });
    return true;
}

bool TestScriptingInterface::iosEntityScriptConsentTest(const QVariantMap& command) {
    const QString id = command.value("commandId").toString();
    const QString operation = command.value("operation").toString();
    const QUrl source(command.value("source").toString());
    if (_testResultsLocation.isEmpty() || !QCoreApplication::arguments().contains("--testScript") ||
            command.size() != 5 || command.value("schemaVersion").toInt() != 1 ||
            command.value("action").toString() != "entity-script-consent" ||
            !QRegularExpression("^ios-[0-9a-f]{32}$").match(id).hasMatch() ||
            (operation != "review" && operation != "allow") || !source.isValid() ||
            source.scheme() != "http" || source.host().isEmpty() || !source.userInfo().isEmpty() ||
            source.hasQuery() || source.hasFragment() ||
            source.path() != "/scripted_interactable.js") { return false; }
    return QMetaObject::invokeMethod(qApp, [this, id, operation, source] {
        const QUrl world(DependencyManager::get<AddressManager>()->currentAddress(true));
        const QString origin = world.toString(QUrl::FullyEncoded);
        const QString sourceReference = source.toString(QUrl::FullyEncoded);
        const bool ownedWorld = world.scheme() == source.scheme() && world.host() == source.host() &&
            world.port() == source.port() && world.path() == "/scene.json";
        if (operation == "review" && ownedWorld && qApp->_isForeground && !qApp->_aboutToQuit) {
            qApp->beginEntityScriptConsentReview();
        }
        const auto scope = qApp->_entityScriptConsentScope;
        auto poll = std::make_shared<std::function<void(int)>>();
        const std::weak_ptr<std::function<void(int)>> weakPoll = poll;
        *poll = [this, id, operation, sourceReference, origin, ownedWorld, scope, weakPoll](int remaining) {
            const auto request = qApp->_activeEntityScriptConsentRequest;
            QQuickItem* dialog = qApp->_entityScriptConsentDialog
                ? qApp->_entityScriptConsentDialog->getDialogItem() : nullptr;
            const bool current = ownedWorld && qApp->_isForeground && !qApp->_aboutToQuit &&
                scope && scope == qApp->_entityScriptConsentScope && scope->active() &&
                request && request->active() && request->belongsTo(scope) &&
                request->source() == sourceReference && request->origin() == origin;
            const bool visible = current && dialog && dialog->isVisible() &&
                dialog->width() > 0 && dialog->height() > 0;
            if (operation == "review" && !visible && remaining > 0 &&
                    scope && scope == qApp->_entityScriptConsentScope && scope->active()) {
                if (auto next = weakPoll.lock()) {
                    QTimer::singleShot(250, this, [next, remaining] { (*next)(remaining - 1); });
                }
                return;
            }
            const bool ok = visible && (operation == "review" ||
                pressEntityScriptConsentDialog(dialog, request, scope, sourceReference, origin));
            saveObject(QVariantMap {
                { "schemaVersion", 1 }, { "commandId", id }, { "operation", operation },
                { "sampleEpochMs", QDateTime::currentMSecsSinceEpoch() },
                { "processId", QCoreApplication::applicationPid() }, { "source", sourceReference },
                { "origin", origin }, { "visible", visible }, { "ok", ok }
            }, "ios-entity-consent-result.json");
        };
        (*poll)(40);
    }, Qt::QueuedConnection);
}

QVariantMap TestScriptingInterface::iosNativeUiSnapshot() {
    if (_testResultsLocation.isEmpty() ||
            !QCoreApplication::arguments().contains("--testScript")) {
        return { { "schemaVersion", 1 }, { "valid", false } };
    }
    // The observer reads UIKit views, so its own main-queue dispatch is the
    // required affinity. A Qt application thread alone does not establish it.
    QVariantMap diagnostic;
    const QVariantMap result = observeIOSNativeAccessibility(&diagnostic);
    saveObject(diagnostic, "ios-native-ui-diagnostic.json");
    return result;
}

bool TestScriptingInterface::iosNormalUiRequest(const QVariantMap& command) {
    const QString directory = _testResultsLocation;
    if (directory.isEmpty() || !QCoreApplication::arguments().contains("--testScript")
            || !validateIOSNormalUiRequest(command)) { return false; }
    const QPointer<TestScriptingInterface> owner(this);
    return QMetaObject::invokeMethod(qApp, [owner, directory, command] {
        if (!owner) { return; }
        // Only the GUI owner may observe/edit the actual current field. Queuing
        // acknowledges transport; this private receipt records actual delivery.
        const auto result = performIOSNormalUiRequest(command);
        if (result.isEmpty()) { return; }
        QSaveFile output(QDir(directory).absoluteFilePath("ios-normal-ui-request-result.json"));
        output.setDirectWriteFallback(false);
        const auto bytes = QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact);
        if (!output.open(QIODevice::WriteOnly)
                || !output.setPermissions(QFile::ReadOwner | QFile::WriteOwner)
                || output.write(bytes) != bytes.size() || !output.commit()) {
            qCWarning(trace_test) << "iOS normal input receipt publication failed";
        }
    }, Qt::QueuedConnection);
}

bool TestScriptingInterface::iosSnapshotFilesRequest(const QVariantMap& command) {
    const QString directory = _testResultsLocation;
    const auto storage = overte::snapshot::storageRoot();
    const auto request = QJsonObject::fromVariantMap(command);
    if (directory.isEmpty() || storage.isEmpty() || !QCoreApplication::arguments().contains("--testScript")
            || !overte::ios::validSnapshotFileRequest(request)) { return false; }
    // One bounded read job at a time. Hashing original captures must not block
    // the GUI/render thread. The probe retries only unaccepted read requests.
    static QSemaphore fileReads(1);
    if (!fileReads.tryAcquire()) { return false; }
    QThreadPool::globalInstance()->start([directory, storage, request] {
        const QSemaphoreReleaser release(&fileReads);
        const auto result = overte::ios::readSnapshotFiles(request, storage);
        if (result.isEmpty()) { return; }
        QSaveFile output(QDir(directory).absoluteFilePath("ios-snapshot-file-result.json"));
        output.setDirectWriteFallback(false);
        const auto bytes = QJsonDocument(result).toJson(QJsonDocument::Compact);
        if (!output.open(QIODevice::WriteOnly)
                || !output.setPermissions(QFile::ReadOwner | QFile::WriteOwner)
                || output.write(bytes) != bytes.size() || !output.commit()) {
            qCWarning(trace_test) << "iOS original Snapshot receipt publication failed";
        }
    });
    return true;
}

bool TestScriptingInterface::iosTextTest(const QVariantMap& command) {
    const QString id = command.value("commandId").toString();
    const QString action = command.value("operation").toString();
    const QString directory = _testResultsLocation;
    if (directory.isEmpty() || !QCoreApplication::arguments().contains("--testScript") ||
            command.size() != 4 || command.value("schemaVersion").toInt() != 1 ||
            command.value("action").toString() != "text-fixture" ||
            !QRegularExpression("^ios-[0-9a-f]{32}$").match(id).hasMatch() ||
            (action != "focus" && action != "snapshot" && action != "dismiss")) { return false; }
    return QMetaObject::invokeMethod(qApp, [id, action, directory] {
        static QPointer<QQuickItem> panel;
        static QPointer<QQuickItem> field;
        const auto finish = [id, action, directory](QQuickItem* created = nullptr) {
            if (created) {
                panel = created;
                field = panel->findChild<QQuickItem*>("controlled.text");
            }
            bool ok = panel && field && panel->metaObject()->indexOfProperty("submittedCount") >= 0;
            if (ok && action == "focus") {
                panel->setVisible(true);
                ok = field->setProperty("text", QString());
                field->forceActiveFocus(Qt::OtherFocusReason);
                qGuiApp->inputMethod()->show();
            } else if (ok && action == "dismiss") {
                field->setFocus(false);
                panel->setFocus(false);
                panel->setVisible(false);
                qGuiApp->inputMethod()->hide();
            }
            QVariantMap result { {"schemaVersion", 1}, {"commandId", id}, {"ok", ok},
                {"processId", QCoreApplication::applicationPid()},
                {"sampleEpochMs", QDateTime::currentMSecsSinceEpoch()} };
            if (ok && DependencyManager::isSet<TabletScriptingInterface>()) {
                const auto metrics = DependencyManager::get<TabletScriptingInterface>()->getTouchUiRuntimeMetrics();
                if (!metrics.value("valid").toBool()) { result["ok"] = false; }
                else {
                    result["snapshot"] = QVariantMap { {"schemaVersion", 1},
                        {"value", field->property("text").toString()},
                        {"focused", field->hasActiveFocus()},
                        {"keyboardVisible", metrics.value("keyboardVisible").toBool()},
                        {"submittedCount", panel->property("submittedCount").toInt()} };
                }
            } else { result["ok"] = false; }
            QSaveFile output(QDir(directory).absoluteFilePath("ios-text-observation.json"));
            output.setDirectWriteFallback(false);
            const auto bytes = QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact);
            if (output.open(QIODevice::WriteOnly)) {
                output.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
                if (output.write(bytes) == bytes.size()) { output.commit(); }
            }
        };
        if (!DependencyManager::isSet<OffscreenUi>()) { finish(); return; }
        if (action == "focus" && !panel) {
            DependencyManager::get<OffscreenUi>()->load(QUrl("qrc:/qml/hifi/ControlledTextInput.qml"),
                [finish](QQmlContext*, QQuickItem* created) {
                    QPointer<QQuickItem> guarded(created);
                    QTimer::singleShot(0, qApp, [finish, guarded] { finish(guarded); });
                });
        } else { finish(); }
    }, Qt::QueuedConnection);
}

QVariantMap TestScriptingInterface::iosRenderObservation() {
    if (_testResultsLocation.isEmpty() || !QCoreApplication::arguments().contains("--testScript")) {
        return { {"schemaVersion", 1}, {"valid", false} };
    }
    QVariantMap result;
    const auto observe = [&] {
        const auto plugin = qApp->getActiveDisplayPlugin();
        const auto* vulkan = plugin ? dynamic_cast<VulkanDisplayPlugin*>(plugin.get()) : nullptr;
        const auto device = vks::Context::get().device;
        const auto frame = iosRuntimeEntityEvidenceSnapshot();
        const bool hardware = device && (device->properties.deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU ||
            device->properties.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU);
        result = { {"schemaVersion", 1}, {"valid", vulkan && device && frame.armed && frame.committed && !frame.capacityExceeded},
            {"processId", QCoreApplication::applicationPid()}, {"sampleEpochMs", QDateTime::currentMSecsSinceEpoch()},
            {"backend", QString("Vulkan/MoltenVK")}, {"hardwareAccelerated", hardware},
            {"surfaceVisible", qApp->applicationState() == Qt::ApplicationActive && qApp->getWindow() && qApp->getWindow()->isVisible()},
            {"generation", QString::number(frame.generation)},
            {"acceptedPresentCalls", QString::number(frame.acceptedPresentCalls)},
            {"frameSequence", frame.lastPresentedFrame} };
    };
    if (QThread::currentThread() == qApp->thread()) { observe(); }
    else { QMetaObject::invokeMethod(qApp, observe, Qt::BlockingQueuedConnection); }
    return result;
}

#endif

void TestScriptingInterface::setTestResultsLocation(const QString path) {
    _testResultsLocation = path;
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (!_featureLifecycle && !path.isEmpty() && QCoreApplication::arguments().contains("--testScript")
            && QThread::currentThread() == qApp->thread()) {
        _featureObservationInstance = QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        _featureLifecycle = new overte::e2e::FeatureLifecycle(this);
        _featureLifecycle->start(path); // Failure leaves an unavailable observer.
#if defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
        const QPointer<TestScriptingInterface> owner(this);
        setIOSGraphicsUiContextReader([owner] {
            if (!owner || owner->_testResultsLocation.isEmpty() || !owner->_featureLifecycle
                    || owner->_featureLifecycle->snapshot().isEmpty()
                    || !QCoreApplication::arguments().contains("--testScript")) { return overte::e2e::GraphicsUiContext(); }
            auto render = RenderScriptingInterface::getInstance();
            return overte::e2e::GraphicsUiContext::fromNative(render->getViewportResolutionScale(),
                render->getHazeEnabled(),render->getMirrorsEnabled());
        });
        setIOSAudioUiContextReader([owner] {
            overte::e2e::AudioUiContext result;
            if (!owner || owner->_testResultsLocation.isEmpty() || !owner->_featureLifecycle
                    || owner->_featureLifecycle->snapshot().isEmpty()
                    || !QCoreApplication::arguments().contains("--testScript")
                    || !DependencyManager::isSet<AudioClient>()) { return result; }
            const auto audio = DependencyManager::get<AudioClient>();
            QVariantMap voice; bool muted {false}, echo {false};
            const auto read = [&] { voice = audio->featureRecordedVoiceObservation(); muted = audio->isMuted(); echo = audio->getLocalEcho(); };
            bool okay {true};
            if (QThread::currentThread() == audio->thread()) { read(); }
            else { okay = QMetaObject::invokeMethod(audio.data(), read, Qt::BlockingQueuedConnection); }
            return okay ? overte::e2e::AudioUiContext::fromNative(voice, muted, echo, qApp->isHMDMode()) : result;
        });
#endif
    }
#endif
}

#if defined(OVERTE_E2E_FEATURE_TESTS)
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
    if (_acousticPrepared && action != "status") {
        result["error"] = "acoustic-test-busy";
        return result;
    }
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

QVariantMap TestScriptingInterface::acousticTest(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this, [&] { result = acousticTest(command); }, Qt::BlockingQueuedConnection);
        return result;
    }
    const QString id = command.value("commandId").toString();
    QVariantMap result { { "schemaVersion", 1 }, { "commandId", id }, { "ok", false } };
#if !defined(Q_OS_IOS)
    result["error"] = "acoustic-test-requires-ios";
    return result;
#else
    if (_testResultsLocation.isEmpty() || !QCoreApplication::arguments().contains("--testScript") ||
            command.value("schemaVersion").toInt() != 1 ||
            !QRegularExpression("^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$").match(id).hasMatch()) {
        result["error"] = "acoustic-test-not-enabled";
        return result;
    }
    const QString action = command.value("action").toString();
    QStringList fields { "schemaVersion", "commandId", "action" };
    if (action == "capture-start") { fields << "seconds" << "challenge"; }
    if (action == "play") { fields << "challenge"; }
    fields.sort();
    if (command.keys() != fields) { result["error"] = "acoustic-invalid-command"; return result; }
    auto audio = DependencyManager::get<AudioClient>();
    const auto onAudio = [&](const std::function<void()>& callback) {
        if (QThread::currentThread() == audio->thread()) { callback(); }
        else { QMetaObject::invokeMethod(audio.data(), callback, Qt::BlockingQueuedConnection); }
    };
    const auto appendStatus = [&] {
        onAudio([&] {
            const auto voice = audio->voiceTestStatus();
            const auto capture = audio->acousticCaptureStatus();
            for (auto it = voice.cbegin(); it != voice.cend(); ++it) { result[it.key()] = it.value(); }
            for (auto it = capture.cbegin(); it != capture.cend(); ++it) { result[it.key()] = it.value(); }
        });
        const auto route = overteIOSAcousticTestState();
        result["builtInMicrophone"] = route.builtInMicrophone;
        result["builtInSpeaker"] = route.builtInSpeaker;
        result["measurementMode"] = route.measurementMode;
        result["outputVolume"] = route.outputVolume;
        result["physicalDevice"] = route.physicalDevice;
        result["outputRevision"] = QVariant::fromValue(overteIOSAudioOutputRevision());
        result["prepared"] = _acousticPrepared;
        result["challenge"] = _acousticChallenge;
        result["playing"] = _acousticInjector && _acousticInjector->isPlaying();
        result["captureSource"] = "physical-device-input-before-processing";
    };
    appendStatus();
    if (action == "reset") {
        if (_acousticInjector) {
            DependencyManager::get<AudioInjectorManager>()->stop(_acousticInjector);
            _acousticInjector.clear();
        }
        onAudio([&] { audio->resetAcousticCapture(); });
        const bool restored = !_acousticPrepared || overteIOSSetAcousticTestMode(false);
        // Retain ownership after a failed restore so the caller/watchdog can retry.
        _acousticPrepared = !restored;
        _acousticChallenge.clear();
        ++_acousticGeneration;
        result["ok"] = restored;
        appendStatus();
        return result;
    }
    // Read-only status must remain available while the OS dialog owns the
    // foreground, so the probe can wait without starting or changing audio.
    if (action == "status") { result["ok"] = true; return result; }
    const auto& domain = DependencyManager::get<NodeList>()->getDomainHandler();
    // A loaded serverless scene also sets isConnected(). Only an actual
    // domain-server connection can send this test's input to a remote mixer.
    if (result.value("sourceEnabled").toBool() || result.value("sourceClockActive").toBool() ||
            !result.value("iosForeground").toBool() || result.value("iosInterrupted").toBool() ||
            (domain.isConnected() && !domain.isServerless())) {
        result["error"] = "acoustic-unsafe-audio-state";
        return result;
    }
    if (action == "prepare") {
        if (_acousticPrepared || audio->getRecording() || !_voiceCapturePath.isEmpty() ||
                !result.value("iosCaptureAllowed").toBool() ||
                !result.value("physicalDevice").toBool() ||
                !result.value("builtInMicrophone").toBool() || !result.value("builtInSpeaker").toBool()) {
            result["error"] = "acoustic-prepare-unavailable";
            return result;
        }
        _acousticPrepared = true;
        if (!overteIOSSetAcousticTestMode(true)) {
            acousticTest({ { "schemaVersion", 1 }, { "commandId", "acoustic-failed-prepare" }, { "action", "reset" } });
            result["error"] = "acoustic-measurement-unavailable";
            return result;
        }
        const auto generation = ++_acousticGeneration;
        QTimer::singleShot(45000, this, [this, generation] {
            if (_acousticPrepared && generation == _acousticGeneration) {
                acousticTest({ { "schemaVersion", 1 }, { "commandId", "acoustic-watchdog" }, { "action", "reset" } });
            }
        });
    } else if (action == "capture-start") {
        const QString challenge = command.value("challenge").toString();
        if (!_acousticPrepared || !QRegularExpression("^[0-9a-f]{32}$").match(challenge).hasMatch()) {
            result["error"] = "acoustic-invalid-challenge";
            return result;
        }
        bool started = false;
        onAudio([&] { started = audio->startAcousticCapture(command.value("seconds").toInt()); });
        if (!started) { result["error"] = "acoustic-capture-unavailable"; return result; }
        _acousticChallenge = challenge;
    } else if (action == "play") {
        if (!_acousticPrepared || _acousticChallenge.isEmpty() ||
                command.value("challenge").toString() != _acousticChallenge || _acousticInjector ||
                !result.value("captureActive").toBool() || !result.value("builtInMicrophone").toBool() ||
                !result.value("builtInSpeaker").toBool() || !result.value("measurementMode").toBool() ||
                result.value("outputVolume").toFloat() <= 0.0f) {
            result["error"] = "acoustic-play-unavailable";
            return result;
        }
        const QByteArray digest = QCryptographicHash::hash("overte-voice-v1:" + _acousticChallenge.toLatin1(), QCryptographicHash::Sha256);
        std::array<int, 12> symbols;
        symbols[0] = static_cast<unsigned char>(digest[0]) % 8;
        for (int i = 1; i < 12; ++i) { symbols[i] = (symbols[i - 1] + 1 + static_cast<unsigned char>(digest[i]) % 7) % 8; }
        // Use the known waveform only as LOCAL SPEAKER OUTPUT. Never enable
        // AudioClient's synthetic input or feed this PCM into the capture.
        VoiceTestSignal output;
        static_assert(VoiceTestSignal::RATE == AudioConstants::SAMPLE_RATE, "acoustic output sample rate");
        output.send(symbols);
        std::vector<int16_t> pcm(VoiceTestSignal::FRAMES);
        output.replace(pcm.data(), VoiceTestSignal::FRAMES, 1);
        AudioInjectorOptions options;
        options.localOnly = true;
        // Non-spatial playback uses the system gain and cannot be attenuated
        // by the avatar's distance from the default world-origin position.
        options.positionSet = false;
        options.volume = 1.0f;
        _acousticInjector = DependencyManager::get<AudioInjectorManager>()->playSound(
            AudioData::make(static_cast<uint32_t>(pcm.size()), 1, pcm.data()), options);
        if (!_acousticInjector) { result["error"] = "acoustic-output-unavailable"; return result; }
    } else if (action == "capture-stop") {
        if (!_acousticPrepared) { result["error"] = "acoustic-session-unprepared"; return result; }
        QByteArray wav;
        onAudio([&] { wav = audio->takeAcousticCapture(); });
        if (wav.isEmpty()) { result["error"] = "acoustic-capture-incomplete"; return result; }
        result["wavBase64"] = QString::fromLatin1(wav.toBase64());
        result["sha256"] = QString::fromLatin1(QCryptographicHash::hash(wav, QCryptographicHash::Sha256).toHex());
        // Preserve the completed capture's status; takeAcousticCapture clears it.
        result["ok"] = true;
        return result;
    } else { result["error"] = "acoustic-invalid-action"; return result; }
    appendStatus();
    result["ok"] = true;
    return result;
#endif
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
#if defined(Q_OS_IOS)
    // Native AFC readers may open this path between samples. Publish a whole
    // new file atomically so neither truncation nor an old size/new body pair
    // can expose incomplete test observations.
    QSaveFile file(filepath);
    file.setDirectWriteFallback(false);
    if (!file.open(QIODevice::WriteOnly) || file.write(jsonData) != jsonData.size()
            || !file.commit()) {
        qCWarning(trace_test) << "iOS test observation publication failed";
    }
#else
    QFile file(filepath);

    file.open(QFile::WriteOnly);
    file.write(jsonData);
    file.close();
#endif
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
