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
#include "../../../tests/device/native/NormalLoginControls.h"
#include "../../../tests/device/native/PrivateLoginInput.h"
#include "../../../tests/device/native/ChatViewObservation.h"
#include <AvatarReceiveObservation.h>
#include <NodeList.h>
#include <QJsonArray>
#if defined(Q_OS_IOS)
#include "../../../tests/device/ios/InstalledBundleIdentity.h"
#include "../../../tests/device/native/IOSWebClosureBridge.h"
#include "../../../ios/web/IOSWorldWebTrace.h"
#include "../../../ios/web/IOSTabletWebTrace.h"
#include "../../../ios/web/IOSTabletWebState.h"
#include "../../../ios/web/IOSTabletWebClosures.h"
#include "../../../ios/web/IOSUIKitInputObservation.h"
#include "../../../ios/web/IOSTabletWebDeferred.h"
#include "../../../tests/device/native/IOSTabletSourcesObservation.h"
#include "../../../tests/device/native/IOSTabletAppButtonsObservation.h"
#include "../../../ios/snapshot/IOSSnapshotObservation.h"
#include "../../../tests/device/native/IOSSnapshotWorkObservation.h"
#include "../../../tests/device/native/IOSSnapshotFileWorkObservation.h"
#include "../../../tests/device/native/IOSSnapshotCaptureObservation.h"
#include "../ui/Snapshot.h"
#include "../../../tests/device/native/IOSLocationBookmarksObservation.h"
#include "../../../tests/device/native/IOSPlacesModelObservation.h"
#include "../../../tests/device/native/IOSPeopleModelObservation.h"
#include "../../../tests/device/native/IOSNavigationStateObservation.h"
#include "../../../tests/device/native/IOSAvatarStateObservation.h"
#include "../../../tests/device/native/IOSAvatarBookmarkFile.h"
#include "../../../tests/device/native/IOSAvatarRenderersObservation.h"
#include "../../../tests/device/native/IOSAvatarScriptsObservation.h"
#include "../../../tests/device/native/IOSAvatarEntitiesObservation.h"
#include "../../../tests/device/native/IOSCreateEntitiesObservation.h"
#include "../../../tests/device/native/IOSPointerStateObservation.h"
#include "../../../tests/device/native/IOSEmoteWorldObservation.h"
#include "../../../tests/device/native/IOSAvatarWorldObservation.h"
#include "../../../tests/device/native/IOSNormalInputObservation.h"
#include "../../../tests/device/native/IOSScriptDialogObservation.h"
#include "../../../tests/device/native/IOSCreateStateObservation.h"
#include "../../../tests/device/native/IOSCreateWorkObservation.h"
#include "../../../tests/device/native/IOSWorldWebWorkObservation.h"
#include "../../../tests/device/native/IOSWorldWebKeysObservation.h"
#include "../../../tests/device/native/IOSWorldWebGeometryObservation.h"
#include "../../../tests/device/native/IOSWorldWebSurfacesObservation.h"
#include "../../../tests/device/native/IOSWorldWebSnapshot.h"
#include "../../../tests/device/native/PrivateCreateFiles.h"
#include "../AvatarBookmarks.h"
#include "../../../tests/device/native/NativeReadBracket.h"
#include <EntityTree.h>
#include <QGuiApplication>
#include <NodeList.h>
#include <XMLHttpRequestClass.h>
#include "../LocationBookmarks.h"
#endif

#include "../../../tests/device/native/WebDOMObservationBridge.h"
#include "../../../tests/device/native/PendingFieldCommitBridge.h"
#include "../../../tests/device/native/ProcessPresence.h"
#include <ui/TabletScriptingInterface.h>
#include "../../../tests/device/native/PrivatePreviewFiles.h"
#include "../../../tests/device/native/PrivateScriptFiles.h"
#include "../../../tests/device/native/PrivateAccountOrigin.h"
#include "../../../tests/device/native/PrivateAccountOriginLease.h"
#include "avatar/AvatarManager.h"
#include "RenderScriptingInterface.h"
#include <AccountManager.h>
#include <AddressManager.h>
#include <MessagesClient.h>
#include <AudioClient.h>
#include <avatars-renderer/SkeletonModel.h>
#include <QCryptographicHash>
#include <QDateTime>
#include <QRegularExpression>
#include <QUuid>
#include <QTimer>
#include <ScriptEngines.h>
#include <ScriptManager.h>
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <ScriptTerminalObservation.h>
#endif
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

#if defined(OVERTE_E2E_FEATURE_TESTS)
QVariantMap TestScriptingInterface::iosPrivateLoginInput(const QVariantMap& command) {
    if (!qApp) { return {}; }
    QVariantMap result;const QPointer<TestScriptingInterface> owner(this);
    const auto request=[&] {
        if (!owner || owner->_testResultsLocation.isEmpty() || !owner->_featureLifecycle
                || owner->_featureLifecycle->snapshot().isEmpty()
                || !QCoreApplication::arguments().contains("--testScript")) { return; }
        if (!owner->_privateLoginInput) { owner->_privateLoginInput=QSharedPointer<overte::e2e::PrivateLoginInput>::create(); }
        const auto perform=[](const QJsonObject& input,const QString& origin) {
            return QJsonObject::fromVariantMap(performIOSPrivateLoginInput(input.toVariantMap(),origin));
        };
        result=owner->_privateLoginInput->request(owner->_testResultsLocation,QJsonObject::fromVariantMap(command),perform).toVariantMap();
    };
    // Private bytes stay entirely in native code, on the actual GUI owner.
    // Only this closed metadata receipt returns through the script/HTTP channel.
    if (QThread::currentThread()==qApp->thread()) { request(); }
    else if (!QMetaObject::invokeMethod(qApp,request,Qt::BlockingQueuedConnection)) { return {}; }
    return result;
}
#endif

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
    // the GUI/render thread. Legacy v1 retries unaccepted requests; the bounded
    // v2 owner retains an uncertain nonce and never asks the probe to resample.
    static QSemaphore fileReads(1);
    if (!fileReads.tryAcquire()) { return false; }
#if defined(OVERTE_E2E_FEATURE_TESTS)
    const auto nativeFileResponsibility=overte::e2e::IOSSnapshotFileWorkObservation::instance().queued(command);
#endif
    QThreadPool::globalInstance()->start([directory, storage, request
#if defined(OVERTE_E2E_FEATURE_TESTS)
            , nativeFileResponsibility
#endif
            ] {
        const QSemaphoreReleaser release(&fileReads);
#if defined(OVERTE_E2E_FEATURE_TESTS)
        const overte::e2e::IOSSnapshotFileWorkObservation::Body originalNativeFileJob(nativeFileResponsibility);
#endif
        const auto result = overte::ios::readSnapshotFiles(request, storage);
        if (result.isEmpty()) { return; }
        QSaveFile output(QDir(directory).absoluteFilePath("ios-snapshot-file-result.json"));
        output.setDirectWriteFallback(false);
        const auto bytes = QJsonDocument(result).toJson(QJsonDocument::Compact);
        const bool published=output.open(QIODevice::WriteOnly)
                && output.setPermissions(QFile::ReadOwner | QFile::WriteOwner)
                && output.write(bytes) == bytes.size() && output.commit();
#if defined(OVERTE_E2E_FEATURE_TESTS)
        overte::e2e::IOSSnapshotFileWorkObservation::instance().publication(nativeFileResponsibility,published);
#endif
        if (!published) {
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
        setIOSLoginUiContextReader([owner] {
            overte::e2e::LoginUiContext result;
            if (!owner || owner->_testResultsLocation.isEmpty() || !owner->_featureLifecycle
                    || owner->_featureLifecycle->snapshot().isEmpty()
                    || !QCoreApplication::arguments().contains("--testScript")
                    || !DependencyManager::isSet<AccountManager>()) { return result; }
            const auto account=DependencyManager::get<AccountManager>();QVariantMap original;
            const auto read=[&] { original=account->featureAccountObservation(); };bool okay {true};
            if (QThread::currentThread()==account->thread()) { read(); }
            else { okay=QMetaObject::invokeMethod(account.data(),read,Qt::BlockingQueuedConnection); }
            return okay ? overte::e2e::LoginUiContext::fromNative(original) : result;
        });
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

QVariantMap TestScriptingInterface::featureCompletedFrameObservation(const QVariantMap& command) {
#if defined(Q_OS_IOS)
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        QMetaObject::invokeMethod(this,[&] { result=featureCompletedFrameObservation(command); },Qt::BlockingQueuedConnection);
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);
    const bool world=command.value("action").toString()=="feature-vulkan-world-frame";
    const bool bytes=world && command.value("operation").toString()=="read-bytes";
    QStringList fields {"schemaVersion","commandId","action","requestId","operation"};
    if (bytes) { fields.append("offset"); }fields.sort();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1)
            || (json.value("action")!=QJsonValue("feature-completed-frame") && !world)
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(command.value("commandId").toString()).hasMatch()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(command.value("requestId").toString()).hasMatch()
            || (!QStringList{"read","release","inspect"}.contains(command.value("operation").toString()) && !bytes)
            || (bytes && (!json.value("offset").isDouble() || json.value("offset").toDouble()<0
                || json.value("offset").toDouble()>=33554432
                || json.value("offset").toDouble()!=static_cast<double>(command.value("offset").toLongLong())))) { return {}; }
    const auto context=qApp->getGPUContext();
    return context ? context->featureCompletedFrames()->request(command) : QVariantMap();
#else
    Q_UNUSED(command);return {};
#endif
}

QVariantMap TestScriptingInterface::featureSceneLoadObservation(const QVariantMap& command) {
#if defined(Q_OS_IOS)
    if (QThread::currentThread() != thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        QMetaObject::invokeMethod(this,[&] { result=featureSceneLoadObservation(command); },Qt::BlockingQueuedConnection);
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto id=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble()!=1
            || json.value("action").toString()!="feature-scene-load-observe"
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(id).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    auto value=qApp->featureSceneLoadObservation();
    value.insert("commandId",id);value.insert("runId",run);
    value.insert("processId",QCoreApplication::applicationPid());
    value.insert("capturedEpochMs",QDateTime::currentMSecsSinceEpoch());
    return value;
#else
    Q_UNUSED(command);return {};
#endif
}


#if defined(Q_OS_IOS)
QVariantMap TestScriptingInterface::featureIOSSceneInventory(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSSceneInventory(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-scene-inventory")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            || !DependencyManager::isSet<EntityScriptingInterface>()) { return {}; }
    const auto entities=DependencyManager::get<EntityScriptingInterface>();
    if (!entities || !entities->getEntityTree()) { return {}; }
    if (!_featureIOSSceneInventory) { _featureIOSSceneInventory=std::make_shared<overte::e2e::NativeReadBracket>(); }
    auto result=_featureIOSSceneInventory->read("iosSceneInventoryVersion","native-main-scene-inventory",request,run,[&]() -> QVariantMap {
        const auto tree=entities->getEntityTree()->featureEntityInventory();if (tree.isEmpty()) { return {}; }
        auto sceneCommand=command;sceneCommand["action"]="feature-scene-load-observe";
        const auto scene=featureSceneLoadObservation(sceneCommand);if (scene.isEmpty()) { return {}; }
        const auto origin=qApp->featureSceneCommitOrigin();if (origin.isEmpty()) { return {}; }
        return {{"tree",tree},{"sceneLoads",scene},{"commitOrigin",origin}};
    });
    if (!result.isEmpty()) { result.insert("iosSceneInventoryVersion",2); }
    return result;
}

QVariantMap TestScriptingInterface::featureIOSScriptDialogs(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSScriptDialogs(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto keys=command.keys();const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString();const auto run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId"}
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-script-dialogs")
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    return overte::e2e::IOSScriptDialogObservation::process().read(request,run);
}

QVariantMap TestScriptingInterface::featureIOSEmoteWorld(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSEmoteWorld(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto keys=command.keys();const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString();const auto run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId"}
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-emote-world")
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    if (!_featureIOSEmoteWorld) { _featureIOSEmoteWorld=std::make_shared<overte::e2e::IOSEmoteWorldObservation>(); }
    return _featureIOSEmoteWorld->read(request,run,[&]() -> QVariantMap {
        return featureIOSMarkerWorldSource(request,run,"emote-marker-v1");
    });
}

QVariantMap TestScriptingInterface::featureIOSAvatarWorld(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSAvatarWorld(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto keys=command.keys();const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString();const auto run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId"}
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-avatar-world")
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    if (!_featureIOSAvatarWorld) { _featureIOSAvatarWorld=std::make_shared<overte::e2e::IOSAvatarWorldObservation>(); }
    return _featureIOSAvatarWorld->read(request,run,[&]() -> QVariantMap {
        return featureIOSMarkerWorldSource(request,run,"avatar-marker-v1");
    });
}

QVariantMap TestScriptingInterface::featureIOSAvatarInputs(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSAvatarInputs(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto keys=command.keys();const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString();const auto run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId"}
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-avatar-inputs")
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    return overte::e2e::IOSNormalInputObservation::shared().observation(
        overte::e2e::IOSNormalInputObservation::Profile::Avatar,request,run).toVariantMap();
}

QVariantMap TestScriptingInterface::featureIOSSnapshotInputs(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) {return {};}
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] {result=featureIOSSnapshotInputs(command);},Qt::BlockingQueuedConnection)) {return {};}
        return result;
    }
    const auto keys=command.keys();const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString();const auto run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId"}
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-snapshot-inputs")
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) {return {};}
    auto& originals=overte::e2e::IOSNormalInputObservation::shared(overte::e2e::IOSNormalInputObservation::Profile::Snapshot);
    return originals.observation(overte::e2e::IOSNormalInputObservation::Profile::Snapshot,request,run).toVariantMap();
}

QVariantMap TestScriptingInterface::featureIOSMarkerWorldSource(const QString& request,const QString& run,const QString& markerKind) {
    // Only the two gated native wrappers select a fixed marker profile. No
    // command can supply an expected entity, model, pose, camera or marker ID.
    if (QThread::currentThread()!=thread()
            || (markerKind!="emote-marker-v1" && markerKind!="avatar-marker-v1")) { return {}; }
    if (!DependencyManager::isSet<AddressManager>() || !DependencyManager::isSet<NodeList>() || !DependencyManager::isSet<AvatarManager>()
            || !DependencyManager::isSet<EntityScriptingInterface>()) { return {}; }
    const auto nodes=DependencyManager::get<NodeList>();const auto avatars=DependencyManager::get<AvatarManager>();
    const auto entities=DependencyManager::get<EntityScriptingInterface>();const auto avatar=avatars->getMyAvatar();
    if (!avatar || !entities->getEntityTree() || nodes->getSessionUUID().isNull()) { return {}; }
    const auto before=entities->getEntityTree()->featureEntityInventory();
    if (before.isEmpty() || !before.value("complete").toBool()) { return {}; }
    const auto scripts=featureScriptObservation(request);if (scripts.isEmpty()) { return {}; }
    auto vec=[](const glm::vec3& value) { return QVariantList{value.x,value.y,value.z}; };
    auto quat=[](const glm::quat& value) { return QVariantList{value.x,value.y,value.z,value.w}; };
    QVariantList markers;
    const auto effects=scripts.value("source").toMap().value("effects").toMap();
    for (const auto& entry:effects.value("entities").toList()) {
        const auto row=entry.toMap();const auto data=QJsonDocument::fromJson(row.value("userData").toString().toUtf8()).object();
        if (data.value("runId").toString()!=run || data.value("kind").toString()!=markerKind) { continue; }
        const auto id=QUuid(row.value("id").toString());const auto original=entities->getEntityProperties(id);
        const auto host=original.getEntityHostType();
        markers.append(QVariantMap{{"id",id.toString(QUuid::WithoutBraces)},{"name",original.getName()},
            {"type",EntityTypes::getEntityTypeName(original.getType())},
            {"hostType",host==entity::HostType::LOCAL ? "local" : host==entity::HostType::AVATAR ? "avatar" : "domain"},
            {"sourceUrl",original.getSourceUrl()},{"userData",original.getUserData()},
            {"position",vec(original.getPosition())},{"rotation",quat(original.getRotation())},
            {"dimensions",vec(original.getDimensions())},{"visible",original.getVisible()},
            {"collisionless",original.getCollisionless()},
            {"lastEditedEpochUs",QString::number(original.getLastEdited())}});
    }
    if (markers.size()>4) { return {}; }
    const auto model=avatar->getSkeletonModel();if (!model) { return {}; }
    const bool boundsReady=model->isLoaded() && model->isRenderable() && !model->needsFixupInScene();
    QVariant bounds;
    if (boundsReady) {
        const auto box=avatar->getBounds();bounds=QVariantMap{{"corner",vec(box.getCorner())},{"dimensions",vec(box.getDimensions())}};
    }
    const auto mixer=nodes->soloNodeOfType(NodeType::AvatarMixer);const auto& domain=nodes->getDomainHandler();
    const auto& camera=qApp->getCamera();ViewFrustum frustum;camera.loadViewFrustum(frustum);
    const auto address=DependencyManager::get<AddressManager>()->currentAddress().toString(QUrl::FullyEncoded);
    const auto after=entities->getEntityTree()->featureEntityInventory();if (before!=after) { return {}; }
    return {{"complete",true},{"tree",before},{"scriptOriginal",scripts},{"markers",markers},{"sceneUrl",address},
        {"domain",QVariantMap{{"connected",domain.isConnected()},{"serverless",domain.isServerless()},
            {"domainId",domain.getUUID().toString(QUuid::WithoutBraces)},
            {"selfSha256",overte::e2e::AvatarReceiveObservation::identity(nodes->getSessionUUID())},
            {"avatarMixerSha256",mixer ? QVariant(overte::e2e::AvatarReceiveObservation::identity(mixer->getUUID())) : QVariant()}}},
        {"avatar",QVariantMap{{"feetPosition",vec(avatar->getWorldFeetPosition())},{"orientation",quat(avatar->getWorldOrientation())},
            {"velocity",vec(avatar->getWorldVelocity())},{"inAir",avatar->isInAir()},{"flying",avatar->isFlying()},
            {"modelScale",avatar->getModelScale()},{"boundsReady",boundsReady},{"bounds",bounds}}},
        {"view",QVariantMap{{"position",vec(frustum.getPosition())},{"rotation",quat(frustum.getOrientation())},
            {"mode",camera.getModeString()},{"fieldOfViewDegrees",frustum.getFieldOfView()},
            {"aspectRatio",frustum.getAspectRatio()},{"perspective",frustum.isPerspective()}}},
        {"cameraOrbit",QVariantMap{{"lookAtRotation",quat(avatar->getLookAtRotation())},
            {"boomLength",avatar->getBoomLength()},{"minimumBoomLength",MyAvatar::ZOOM_MIN},{"defaultBoomLength",MyAvatar::ZOOM_DEFAULT}}}};
}

QVariantMap TestScriptingInterface::featureIOSAvatarRenderers(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSAvatarRenderers(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-avatar-renderers")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            || !DependencyManager::isSet<EntityScriptingInterface>() || !DependencyManager::isSet<AvatarManager>()) { return {}; }
    const auto entities=DependencyManager::get<EntityScriptingInterface>();
    if (!entities || !entities->getEntityTree()) { return {}; }
    if (!_featureIOSAvatarRenderers) { _featureIOSAvatarRenderers=std::make_shared<overte::e2e::IOSAvatarRenderersObservation>(); }
    return _featureIOSAvatarRenderers->read(request,run,DependencyManager::get<AvatarManager>().data(),entities->getEntityTree());
}

QVariantMap TestScriptingInterface::featureIOSAvatarScripts(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSAvatarScripts(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-avatar-scripts")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            || !DependencyManager::isSet<ScriptEngines>()) { return {}; }
    if (!_featureIOSAvatarScripts) { _featureIOSAvatarScripts=std::make_shared<overte::e2e::IOSAvatarScriptsObservation>(); }
    return _featureIOSAvatarScripts->read(request,run,DependencyManager::get<ScriptEngines>().data());
}

QVariantMap TestScriptingInterface::featureIOSAvatarEntities(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSAvatarEntities(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-avatar-entities")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch() ) { return {}; }
    if (!_featureIOSAvatarEntities) { _featureIOSAvatarEntities=std::make_shared<overte::e2e::IOSAvatarEntitiesObservation>(); }
    return _featureIOSAvatarEntities->read(request,run);
}

QVariantMap TestScriptingInterface::featureIOSPointerState(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSPointerState(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-pointer-state")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch() ) { return {}; }
    if (!_featureIOSPointerState) { _featureIOSPointerState=std::make_shared<overte::e2e::IOSPointerStateObservation>(); }
    return _featureIOSPointerState->read(request,run,qApp->featureIOSWorldTapActive());
}

QVariantMap TestScriptingInterface::featureIOSCreateEntities(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSCreateEntities(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-create-entities")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch() ) { return {}; }
    if (!DependencyManager::isSet<EntityScriptingInterface>()) { return {}; }
    const auto entities=DependencyManager::get<EntityScriptingInterface>();
    if (!entities || !entities->getEntityTree()) { return {}; }
    if (!_featureIOSCreateEntities) { _featureIOSCreateEntities=std::make_shared<overte::e2e::IOSCreateEntitiesObservation>(); }
    return _featureIOSCreateEntities->read(request,run,entities.data());
}

void TestScriptingInterface::featureIOSCreateEvent(const QVariantMap& value) {
    if (_testResultsLocation.isEmpty() || !QCoreApplication::arguments().contains("--testScript")) { return; }
    overte::e2e::IOSCreateWorkObservation::instance().event(value,ScriptManager::featureNativeCallContext());
}

QVariantMap TestScriptingInterface::featureIOSCreateWork(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSCreateWork(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-create-work")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    return overte::e2e::IOSCreateWorkObservation::instance().read(request,run);
}

void TestScriptingInterface::featureIOSWorldWebEvent(const QVariantMap& value) {
    if (_testResultsLocation.isEmpty() || !QCoreApplication::arguments().contains("--testScript")) { return; }
    overte::e2e::IOSWorldWebWorkObservation::instance().event(value,ScriptManager::featureNativeCallContext());
}

QVariantMap TestScriptingInterface::featureIOSWorldWebWork(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSWorldWebWork(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-world-web-work")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    return overte::e2e::IOSWorldWebWorkObservation::instance().read(request,run);
}

QVariantMap TestScriptingInterface::featureIOSWorldWebKeys(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSWorldWebKeys(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-world-web-keys")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    return overte::e2e::IOSWorldWebKeysObservation::instance().read(request,run);
}

QVariantMap TestScriptingInterface::featureIOSWorldWebGeometry(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSWorldWebGeometry(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-world-web-geometry")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    if (!DependencyManager::isSet<EntityScriptingInterface>()) { return {}; }
    const auto entities=DependencyManager::get<EntityScriptingInterface>();
    if (!entities || !entities->getEntityTree()) { return {}; }
    if (!_featureIOSWorldWebGeometry) { _featureIOSWorldWebGeometry=std::make_shared<overte::e2e::IOSWorldWebGeometryObservation>(); }
    return _featureIOSWorldWebGeometry->read(request,run,entities.data());
}

QVariantMap TestScriptingInterface::featureIOSWorldWebSurfaces(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSWorldWebSurfaces(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-world-web-surfaces")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    if (!_featureIOSWorldWebSurfaces) { _featureIOSWorldWebSurfaces=std::make_shared<overte::e2e::IOSWorldWebSurfacesObservation>(); }
    return _featureIOSWorldWebSurfaces->read(request,run);
}

QVariantMap TestScriptingInterface::featureIOSCreateState(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSCreateState(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-create-state")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            || !DependencyManager::isSet<EntityScriptingInterface>() || !DependencyManager::isSet<OffscreenUi>()
            || !DependencyManager::isSet<TabletScriptingInterface>() || !DependencyManager::isSet<NodeList>()) { return {}; }
    const auto entities=DependencyManager::get<EntityScriptingInterface>();
    if (!entities || !entities->getEntityTree()) { return {}; }
    const auto ui=DependencyManager::get<OffscreenUi>();
    const auto tablets=DependencyManager::get<TabletScriptingInterface>();
    TabletProxy* tablet {nullptr};
    for (auto candidate:tablets->findChildren<TabletProxy*>(QString(),Qt::FindDirectChildrenOnly)) {
        if (candidate->getName()=="com.highfidelity.interface.tablet.system") {
            if (tablet) { return {}; }tablet=candidate;
        }
    }
    if (!ui || !ui->getRootItem() || !tablet || !tablet->getIOSTabletRoot()) { return {}; }
    const auto shown=tablet->property("tabletShown");if (shown.userType()!=QMetaType::Bool) { return {}; }
    if (!_featureIOSCreateState) { _featureIOSCreateState=std::make_shared<overte::e2e::IOSCreateStateObservation>(); }
    return _featureIOSCreateState->read(request,run,{ui->getRootItem(),tablet->getIOSTabletRoot()},shown.toBool(),
        entities.data(),DependencyManager::get<NodeList>()->getDomainHandler().getUUID().toString(QUuid::WithoutBraces));
}

QVariantMap TestScriptingInterface::featureIOSCreateFiles(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSCreateFiles(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    const auto operation=command.value("operation").toString();
    QStringList fields {"schemaVersion","commandId","action","runId","ownerToken","operation"};
    if (operation=="stage") { fields.append("inputBase64"); }
    if (operation=="release") { fields.append("originals"); }
    fields.sort();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-create-files")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\Aios-[0-9a-f]{32}\z").match(request).hasMatch()
            || !QRegularExpression("\A[0-9a-f]{32}\z").match(run).hasMatch()
            || !QRegularExpression("\A[0-9a-f]{64}\z").match(json.value("ownerToken").toString()).hasMatch()
            || !QStringList{"stage","locate","observe","release"}.contains(operation)
            || (operation=="stage" && !json.value("inputBase64").isString())
            || (operation=="release" && (!json.value("originals").isArray() || json.value("originals").toArray().size()!=2))
            || QJsonDocument(json).toJson(QJsonDocument::Compact).size()>131072) { return {}; }
    // Retain the actual first result, including unavailable. Insert intent
    // before storage is touched; a repeated nonce never repeats a mutation.
    if (_featureIOSCreateFileCommands.contains(request)) {
        return _featureIOSCreateFileCommands.value(request)==command ? _featureIOSCreateFileResults.value(request) : QVariantMap{};
    }
    if (_featureIOSCreateFileCommands.size()>=4096) { return {}; }
    _featureIOSCreateFileCommands.insert(request,command);
    if (!_featureIOSCreateFiles) { _featureIOSCreateFiles=std::make_shared<overte::e2e::NativeReadBracket>(); }
    const auto result=_featureIOSCreateFiles->read("iosCreateFilesVersion","native-main-create-files",request,run,[&] {
        return overte::e2e::PrivateCreateFiles::request(_testResultsLocation,command);
    });
    _featureIOSCreateFileResults.insert(request,result);
    return result;
}

void TestScriptingInterface::featureIOSSnapshotEvent(const QVariantMap& value) {
    if (_testResultsLocation.isEmpty() || !QCoreApplication::arguments().contains("--testScript")) {return;}
    overte::e2e::IOSSnapshotWorkObservation::instance().event(value,ScriptManager::featureNativeCallContext());
}

QVariantMap TestScriptingInterface::featureIOSSnapshotWork(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) {return {};}
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] {result=featureIOSSnapshotWork(command);},Qt::BlockingQueuedConnection)) {return {};}
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-snapshot-work")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            || !DependencyManager::isSet<ScriptEngines>()) {return {};}
    const auto scripts=DependencyManager::get<ScriptEngines>();if (!scripts) {return {};}
    return overte::e2e::IOSSnapshotWorkObservation::instance().read(request,run,[scripts] {return scripts->featureSnapshotScriptObservation();});
}

QVariantMap TestScriptingInterface::featureIOSSnapshotFileWork(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) {return {};}
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] {result=featureIOSSnapshotFileWork(command);},Qt::BlockingQueuedConnection)) {return {};}
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-snapshot-file-work")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) {return {};}
    return overte::e2e::IOSSnapshotFileWorkObservation::instance().read(request,run);
}

QVariantMap TestScriptingInterface::featureIOSSnapshotCaptures(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) {return {};}
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] {result=featureIOSSnapshotCaptures(command);},Qt::BlockingQueuedConnection)) {return {};}
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-snapshot-captures")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            || !DependencyManager::isSet<Snapshot>()) {return {};}
    const auto snapshots=DependencyManager::get<Snapshot>();if (!snapshots) {return {};}
    return overte::e2e::IOSSnapshotCaptureObservation::instance().read(request,run,[snapshots] {return snapshots->featureCaptureActivity();});
}

QVariantMap TestScriptingInterface::featureIOSSnapshotExports(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) {return {};}
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] {result=featureIOSSnapshotExports(command);},Qt::BlockingQueuedConnection)) {return {};}
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-snapshot-exports")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) {return {};}
    if (!_featureIOSSnapshotExports) {_featureIOSSnapshotExports=std::make_shared<overte::e2e::NativeReadBracket>();}
    return _featureIOSSnapshotExports->read("iosSnapshotExportsVersion","native-main-snapshot-exports",request,run,
        [] {return overte::ios::featureSnapshotExportObservation();});
}

QVariantMap TestScriptingInterface::featureIOSAvatarState(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSAvatarState(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-avatar-state")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            || !DependencyManager::isSet<AvatarManager>() || !DependencyManager::isSet<AvatarBookmarks>()) { return {}; }
    if (!_featureIOSAvatarState) { _featureIOSAvatarState=std::make_shared<overte::e2e::IOSAvatarStateObservation>(); }
    return _featureIOSAvatarState->read(request,run,[&]() -> QVariantMap {
        const auto avatars=DependencyManager::get<AvatarManager>();const auto bookmarks=DependencyManager::get<AvatarBookmarks>();
        if (!avatars || !bookmarks) { return {}; }
        const auto avatar=avatars->getMyAvatar();if (!avatar) { return {}; }
        const auto model=avatar->getSkeletonModel();if (!model) { return {}; }
        const auto names=avatar->getJointNames();const bool loaded=model->isLoaded();
        const auto session=avatar->getSessionUUID();
        return {{"sessionId",session.toString(QUuid::WithoutBraces)},
            {"sessionPresent",!session.isNull()},
            {"requestedUrl",avatar->getSkeletonModelURL().toString(QUrl::FullyEncoded)},
            {"resourceUrl",model->getURL().toString(QUrl::FullyEncoded)},
            {"defaultResourceUrl",AvatarData::defaultFullAvatarModelUrl().toString(QUrl::FullyEncoded)},
            {"geometryLoaded",loaded},{"rigReady",loaded && bool(model->getRig().getAnimNode()) && !names.isEmpty()},
            {"shouldRender",avatar->shouldRender()},{"targetScale",avatar->getAvatarScale()},
            {"modelScale",avatar->getModelScale()},{"jointNames",names},
            {"bookmarkFile",overte::e2e::IOSAvatarBookmarkFile::read(bookmarks->featurePersistenceFileName())},
            {"bookmarks",QVariantMap{{"source","AvatarBookmarks.getBookmarks"},{"entries",bookmarks->getBookmarks()},
                {"loadError",!bookmarks->getBookmarkError().isEmpty()}}}};
    });
}

QVariantMap TestScriptingInterface::featureIOSNavigationState(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSNavigationState(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-navigation-state")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            || !DependencyManager::isSet<EntityScriptingInterface>() || !DependencyManager::isSet<AvatarManager>()
            || !DependencyManager::isSet<AddressManager>() || !DependencyManager::isSet<NodeList>()) { return {}; }
    if (!_featureIOSNavigationState) { _featureIOSNavigationState=std::make_shared<overte::e2e::IOSNavigationStateObservation>(); }
    return _featureIOSNavigationState->read(request,run,[&]() -> QVariantMap {
        const auto entities=DependencyManager::get<EntityScriptingInterface>();
        const auto avatars=DependencyManager::get<AvatarManager>();
        const auto addresses=DependencyManager::get<AddressManager>();const auto nodes=DependencyManager::get<NodeList>();
        if (!entities || !entities->getEntityTree() || !avatars || !addresses || !nodes) { return {}; }
        const auto avatar=avatars->getMyAvatar();if (!avatar) { return {}; }
        auto vec=[](const glm::vec3& value) { return QVariantList{value.x,value.y,value.z}; };
        auto quat=[](const glm::quat& value) { return QVariantList{value.x,value.y,value.z,value.w}; };
        QVariantList present,absent;
        // Fixed fixture identities, queried directly. Names and geometry below
        // are read from real entities; no wanted URL/pose enters this query.
        for (int index=1;index<=5;++index) {
            const auto id=QUuid(QString("00000000-0000-4000-8000-%1").arg(index,12,10,QLatin1Char('0')));
            const auto actual=entities->getEntityProperties(id);
            if (actual.getType()==EntityTypes::Unknown) { absent.append(id.toString(QUuid::WithoutBraces));continue; }
            if (actual.getName().size()>256) { return {}; }
            const auto color=actual.getColor();
            present.append(QVariantMap{{"id",id.toString(QUuid::WithoutBraces)},{"name",actual.getName()},
                {"type",EntityTypes::getEntityTypeName(actual.getType())},{"position",vec(actual.getPosition())},
                {"rotation",quat(actual.getRotation())},{"dimensions",vec(actual.getDimensions())},
                {"color",QVariantList{int(color.x),int(color.y),int(color.z)}},{"visible",actual.getVisible()},
                {"collisionless",actual.getCollisionless()}});
        }
        const auto space=QUuid::fromRfc4122(QByteArray::fromHex(run.toLatin1()));
        const auto markerId=QUuid::createUuidV5(space,QByteArray("navigation-marker-v1"));
        const auto marker=entities->getEntityProperties(markerId);
        QVariantMap challenge {{"id",markerId.toString(QUuid::WithoutBraces)},
            {"present",marker.getType()!=EntityTypes::Unknown},{"entity",QVariant()}};
        if (marker.getType()!=EntityTypes::Unknown) {
            if (marker.getName().size()>256 || marker.getSourceUrl().size()>2048) { return {}; }
            const auto host=marker.getEntityHostType();
            challenge["entity"]=QVariantMap{{"name",marker.getName()},{"type",EntityTypes::getEntityTypeName(marker.getType())},
                {"hostType",host==entity::HostType::LOCAL ? "local" : host==entity::HostType::AVATAR ? "avatar" : "domain"},
                {"sourceUrl",marker.getSourceUrl()},{"position",vec(marker.getPosition())},{"rotation",quat(marker.getRotation())},
                {"dimensions",vec(marker.getDimensions())},{"visible",marker.getVisible()},{"collisionless",marker.getCollisionless()},
                {"lastEditedEpochUs",static_cast<qulonglong>(marker.getLastEdited())}};
        }
        const auto address=addresses->currentAddress().toString(QUrl::FullyEncoded);
        if (address.size()>2048) { return {}; }
        auto sceneCommand=command;sceneCommand["action"]="feature-scene-load-observe";
        const auto scene=featureSceneLoadObservation(sceneCommand);if (scene.isEmpty()) { return {}; }
        const auto& camera=qApp->getCamera();ViewFrustum frustum;camera.loadViewFrustum(frustum);
        const auto& domain=nodes->getDomainHandler();
        return {{"foreground",QGuiApplication::applicationState()==Qt::ApplicationActive},{"sceneUrl",address},
            {"domain",QVariantMap{{"handlerConnected",domain.isConnected()},{"serverless",domain.isServerless()},
                {"protocol",addresses->currentAddress().scheme()}}},
            {"avatar",QVariantMap{{"feetPosition",vec(avatar->getWorldFeetPosition())},
                {"orientation",quat(avatar->getWorldOrientation())},{"velocity",vec(avatar->getWorldVelocity())},
                {"inAir",avatar->isInAir()},{"flying",avatar->isFlying()},{"modelScale",avatar->getModelScale()}}},
            {"view",QVariantMap{{"position",vec(frustum.getPosition())},{"rotation",quat(frustum.getOrientation())},
                {"mode",camera.getModeString()},{"fieldOfViewDegrees",frustum.getFieldOfView()},
                {"aspectRatio",frustum.getAspectRatio()},{"perspective",frustum.isPerspective()}}},
            {"markers",present},{"absentMarkerIds",absent},{"sceneLoads",scene},{"challengeMarker",challenge}};
    });
}

QVariantMap TestScriptingInterface::featureIOSNavigationDialogs(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSNavigationDialogs(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    return OffscreenUi::featureNavigationDialogs(command);
}

QVariantMap TestScriptingInterface::featureIOSAvatarSocialHttp(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSAvatarSocialHttp(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    return XMLHttpRequestClass::featureAvatarSocialHttpObservation(command);
}
QVariantMap TestScriptingInterface::featureIOSPlacesHttp(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSPlacesHttp(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    return XMLHttpRequestClass::featurePlacesHttpObservation(command);
}

QVariantMap TestScriptingInterface::featureIOSPeopleModel(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSPeopleModel(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble()!=1
            || json.value("action")!=QJsonValue("feature-ios-people-model")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            || !DependencyManager::isSet<OffscreenUi>() || !DependencyManager::isSet<TabletScriptingInterface>()) { return {}; }
    const auto ui=DependencyManager::get<OffscreenUi>();
    const auto tablets=DependencyManager::get<TabletScriptingInterface>();
    TabletProxy* tablet {nullptr};
    for (auto candidate:tablets->findChildren<TabletProxy*>(QString(),Qt::FindDirectChildrenOnly)) {
        if (candidate->getName()=="com.highfidelity.interface.tablet.system") {
            if (tablet) { return {}; }tablet=candidate;
        }
    }
    if (!ui || !ui->getRootItem() || !tablet || !tablet->getIOSTabletRoot()) { return {}; }
    const auto shown=tablet->property("tabletShown");if (shown.userType()!=QMetaType::Bool) { return {}; }
    if (!_featureIOSPeopleModel) { _featureIOSPeopleModel=std::make_shared<overte::e2e::IOSPeopleModelObservation>(); }
    return _featureIOSPeopleModel->read(request,run,{ui->getRootItem(),tablet->getIOSTabletRoot()},shown.toBool());
}
QVariantMap TestScriptingInterface::featureIOSPlacesModel(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSPlacesModel(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble()!=1
            || json.value("action")!=QJsonValue("feature-ios-places-model")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            || !DependencyManager::isSet<OffscreenUi>() || !DependencyManager::isSet<TabletScriptingInterface>()) { return {}; }
    const auto ui=DependencyManager::get<OffscreenUi>();
    const auto tablets=DependencyManager::get<TabletScriptingInterface>();
    TabletProxy* tablet {nullptr};
    for (auto candidate:tablets->findChildren<TabletProxy*>(QString(),Qt::FindDirectChildrenOnly)) {
        if (candidate->getName()=="com.highfidelity.interface.tablet.system") {
            if (tablet) { return {}; }tablet=candidate;
        }
    }
    if (!ui || !ui->getRootItem() || !tablet || !tablet->getIOSTabletRoot()) { return {}; }
    const auto shown=tablet->property("tabletShown");if (shown.userType()!=QMetaType::Bool) { return {}; }
    if (!_featureIOSPlacesModel) { _featureIOSPlacesModel=std::make_shared<overte::e2e::IOSPlacesModelObservation>(); }
    return _featureIOSPlacesModel->read(request,run,{ui->getRootItem(),tablet->getIOSTabletRoot()},shown.toBool());
}

QVariantMap TestScriptingInterface::featureIOSLocationBookmarks(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this,[&] { result=featureIOSLocationBookmarks(command); },Qt::BlockingQueuedConnection);
        return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble()!=1
            || json.value("action")!=QJsonValue("feature-ios-location-bookmarks")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            || !DependencyManager::isSet<LocationBookmarks>()) { return {}; }
    const auto bookmarks=DependencyManager::get<LocationBookmarks>();
    if (!bookmarks) { return {}; }
    if (!_featureIOSLocationBookmarks) { _featureIOSLocationBookmarks=std::make_shared<overte::e2e::IOSLocationBookmarksObservation>(); }
    return _featureIOSLocationBookmarks->read(request,run,[bookmarks] { return bookmarks->getBookmarks(); },
        [bookmarks] { return !bookmarks->getBookmarkError().isEmpty(); });
}
#endif

QVariantMap TestScriptingInterface::featureGraphicsSubjectObservation(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this,[&] { result = featureGraphicsSubjectObservation(command); },Qt::BlockingQueuedConnection);
        return result;
    }
    const auto json = QJsonObject::fromVariantMap(command);
    QStringList fields {"schemaVersion","commandId","action","runId"}; fields.sort();
    const auto request = command.value("commandId").toString();
    const auto run = command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || _featureGraphicsSubjectSequence>=1000000000
            || command.keys() != fields
            || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble() != 1
            || json.value("action").toString() != "feature-graphics-subject-observe"
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    const auto requested = QDateTime::currentMSecsSinceEpoch();
    const auto entities = DependencyManager::get<EntityScriptingInterface>();
    if (!entities || !entities->getEntityTree()) { return {}; }
    const auto avatar = DependencyManager::get<AvatarManager>()->getMyAvatar();
    if (!avatar) { return {}; }
    auto vec = [](const glm::vec3& value) { return QVariantList{value.x,value.y,value.z}; };
    auto quat = [](const glm::quat& value) { return QVariantList{value.x,value.y,value.z,value.w}; };
    auto color = [](const glm::u8vec3& value) { return QVariantList{int(value.x),int(value.y),int(value.z)}; };
    auto properties = [&](const EntityItemProperties& p) -> QVariantMap {
        const auto host = p.getEntityHostType();
        const auto& haze = p.getHaze();
        return {{"name",p.getName()},{"type",EntityTypes::getEntityTypeName(p.getType())},
            {"hostType",host == entity::HostType::LOCAL ? "local" : host == entity::HostType::AVATAR ? "avatar" : "domain"},
            {"position",vec(p.getPosition())},{"rotation",quat(p.getRotation())},{"dimensions",vec(p.getDimensions())},
            {"color",color(p.getColor())},{"visible",p.getVisible()},
            {"mirrorMode",MirrorModeHelpers::getNameForMirrorMode(p.getMirrorMode())},
            {"hazeMode",int(p.getHazeMode())},{"sourceUrl",p.getSourceUrl()},
            {"haze",QVariantMap{{"range",haze.getHazeRange()},{"color",color(haze.getHazeColor())},
                {"altitudeEffect",haze.getHazeAltitudeEffect()},{"glare",haze.getHazeEnableGlare()},
                {"backgroundBlend",haze.getHazeBackgroundBlend()}}}};
    };
    QSet<QUuid> owned;
    QVariantList present,absent;
    const auto space = QUuid::fromRfc4122(QByteArray::fromHex(run.toLatin1()));
    for (const auto& name : {"zone","floor","fog-board","resolution-bars","reflector","reflected-color","marker"}) {
        const auto id = QUuid::createUuidV5(space,QByteArray("graphics-subject-v1/")+name);
        owned.insert(id);
        const auto actual = entities->getEntityProperties(id);
        if (actual.getType() == EntityTypes::Unknown) { absent.append(id.toString(QUuid::WithoutBraces)); continue; }
        auto row = properties(actual);
        if (actual.getName().size() > 256 || actual.getSourceUrl().size() > 2048) { return {}; }
        row.insert("id",id.toString(QUuid::WithoutBraces));
        row.insert("lastEditedEpochUs",static_cast<qulonglong>(actual.getLastEdited()));
        present.append(row);
    }
    // The declared scan is bounded and local to the controlled subject. Owned
    // UUIDs above are always queried directly, even if moved/renamed/offscreen.
    const auto mask = PickFilter::getBitMask(PickFilter::FlagBit::LOCAL_ENTITIES)
        | PickFilter::getBitMask(PickFilter::FlagBit::DOMAIN_ENTITIES)
        | PickFilter::getBitMask(PickFilter::FlagBit::AVATAR_ENTITIES)
        | PickFilter::getBitMask(PickFilter::FlagBit::COARSE);
    const auto ids = entities->findEntities(glm::vec3(0),128.0f,mask);
    if (ids.size() > 1024) { return {}; }
    QVariantList unowned;
    for (const auto& id : ids) {
        if (owned.contains(id)) { continue; }
        const auto actual = entities->getEntityProperties(id);
        if (actual.getType() == EntityTypes::Unknown || actual.getName().size() > 256 || actual.getSourceUrl().size() > 2048) { return {}; }
        // Original spatial/visual state, without edit timestamps which legitimately
        // change when the same original controlled scene is normally reloaded.
        const auto digest = QCryptographicHash::hash(QJsonDocument::fromVariant(properties(actual)).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex();
        unowned.append(QVariantMap{{"id",id.toString(QUuid::WithoutBraces)},{"sha256",QString::fromLatin1(digest)}});
    }
    const auto& camera = qApp->getCamera();
    ViewFrustum frustum; camera.loadViewFrustum(frustum);
    const auto address = DependencyManager::get<AddressManager>()->currentAddress().toString(QUrl::FullyEncoded);
    if (address.size() > 2048) { return {}; }
    QVariantMap source {{"subjectVersion",2},{"sceneUrl",address},
        {"avatarPose",QVariantMap{{"feetPosition",vec(avatar->getWorldFeetPosition())},
            {"orientation",quat(avatar->getWorldOrientation())},{"modelScale",avatar->getModelScale()}}},
        {"view",QVariantMap{{"position",vec(frustum.getPosition())},{"rotation",quat(frustum.getOrientation())},
            {"mode",camera.getModeString()},{"fieldOfViewDegrees",frustum.getFieldOfView()},
            {"aspectRatio",frustum.getAspectRatio()},{"perspective",frustum.isPerspective()}}},
        {"entities",present},{"absentIds",absent},
        {"scan",QVariantMap{{"center",QVariantList{0,0,0}},{"radiusMeters",128},{"propertyScope","graphics-spatial-v1"},
            {"scannedEntities",ids.size()},{"unowned",unowned}}}};
#if defined(Q_OS_IOS)
    source.insert("subjectVersion",3);
    source.insert("cameraOrbit",QVariantMap{{"lookAtRotation",quat(avatar->getLookAtRotation())},
        {"boomLength",avatar->getBoomLength()},{"minimumBoomLength",MyAvatar::ZOOM_MIN},{"defaultBoomLength",MyAvatar::ZOOM_DEFAULT}});
#endif
    if (QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size() > 200000) { return {}; }
    return {{"schemaVersion",1},{"requestId",request},{"runId",run},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureGraphicsSubjectSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
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

#if defined(Q_OS_IOS)
QVariantMap TestScriptingInterface::featureIOSBundleObservation(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSBundleObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    if (!_featureIOSBundle) { _featureIOSBundle=std::make_shared<overte::e2e::InstalledBundleIdentity>(); }
    return _featureIOSBundle->observe(command);
}
#endif

QVariantMap TestScriptingInterface::featureProcessPresence(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this, [&] { result = featureProcessPresence(command); }, Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || !overte::e2e::previewDirectory(_testResultsLocation)
            || !overte::e2e::ProcessPresence::command(command) || _featureProcessPresenceSequence >= 1000000000) { return {}; }
    const auto requested = QDateTime::currentMSecsSinceEpoch();
    auto result = overte::e2e::ProcessPresence::observe(command.value("queryProcessId").toInt());
    if (result.isEmpty()) { return {}; }
    result.insert("processPresenceVersion", 1);
    result.insert("commandId", command.value("commandId"));
    result.insert("instance", _featureObservationInstance);
    result.insert("sequence", static_cast<qulonglong>(++_featureProcessPresenceSequence));
    result.insert("processId", QCoreApplication::applicationPid());
    result.insert("queryProcessId", command.value("queryProcessId"));
    result.insert("requestedEpochMs", requested);
    result.insert("capturedEpochMs", QDateTime::currentMSecsSinceEpoch());
    return result;
}

QVariantMap TestScriptingInterface::featureNavigationReplies(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureNavigationReplies(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::e2e::previewDirectory(_testResultsLocation)
            || !overte::e2e::FeatureNavigationReplies::command(command) || !DependencyManager::isSet<AddressManager>()) { return {}; }
    const auto address=DependencyManager::get<AddressManager>();QVariantMap result;
    if (QThread::currentThread()==address->thread()) { result=address->featureNavigationReplies(command); }
    else if (!address->thread() || !address->thread()->isRunning()
            || !QMetaObject::invokeMethod(address.data(),[&] { result=address->featureNavigationReplies(command); },Qt::BlockingQueuedConnection)) { return {}; }
    return result;
}

QVariantMap TestScriptingInterface::featurePendingCommitOwner(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this, [&] { result = featurePendingCommitOwner(command); }, Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || !overte::e2e::previewDirectory(_testResultsLocation) || !overte::e2e::pendingCommitOwnerCommand(command)) { return {}; }
    const auto original = qApp->property(overte::e2e::pendingCommitProviderProperty());
    if (original.userType() != qMetaTypeId<overte::e2e::PendingCommitProvider>()) { return {}; }
    const auto provider = original.value<overte::e2e::PendingCommitProvider>();
    return provider ? provider(command) : QVariantMap();
}

#if defined(Q_OS_IOS)
QVariantMap TestScriptingInterface::featureIOSWebClosures(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this, [&] { result = featureIOSWebClosures(command); }, Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::ios::feature_closures::command(command)) { return {}; }
    const auto original = qApp->property(overte::ios::feature_closures::providerProperty());
    if (original.userType() != qMetaTypeId<overte::ios::feature_closures::Provider>()) { return {}; }
    const auto provider = original.value<overte::ios::feature_closures::Provider>();
    return provider ? provider(command) : QVariantMap();
}

QVariantMap TestScriptingInterface::featureIOSTabletSources(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSTabletSources(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !overte::e2e::tablet_sources::enabled() || !overte::e2e::tablet_sources::command(command)) { return {}; }
    return overte::e2e::tablet_sources::observe(command);
}

QVariantMap TestScriptingInterface::featureIOSTabletWebState(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSTabletWebState(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::ios::tablet_web_state::command(command)) { return {}; }
    const auto original=qApp->property(overte::ios::tablet_web_state::providerProperty());
    if (original.userType()!=qMetaTypeId<overte::ios::tablet_web_state::Provider>()) { return {}; }
    const auto provider=original.value<overte::ios::tablet_web_state::Provider>();
    return provider ? provider(command) : QVariantMap();
}

QVariantMap TestScriptingInterface::featureIOSTabletWeb(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSTabletWeb(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::ios::tablet_web_trace::command(command)) { return {}; }
    const auto original=qApp->property(overte::ios::tablet_web_trace::providerProperty());
    if (original.userType()!=qMetaTypeId<overte::ios::tablet_web_trace::Provider>()) { return {}; }
    const auto provider=original.value<overte::ios::tablet_web_trace::Provider>();
    return provider ? provider(command) : QVariantMap();
}

QVariantMap TestScriptingInterface::featureIOSTabletWebDeferred(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSTabletWebDeferred(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !overte::e2e::tablet_sources::enabled() || !overte::ios::tablet_web_deferred::query(command,false)) { return {}; }
    const auto original=qApp->property(overte::ios::tablet_web_deferred::providerProperty());
    if (original.userType()!=qMetaTypeId<overte::ios::tablet_web_deferred::Provider>()) { return {}; }
    const auto provider=original.value<overte::ios::tablet_web_deferred::Provider>();
    return provider ? provider(command) : QVariantMap();
}

QVariantMap TestScriptingInterface::featureIOSTabletWebDefer(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSTabletWebDefer(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !overte::e2e::tablet_sources::enabled() || !overte::ios::tablet_web_deferred::query(command,true)) { return {}; }
    const auto original=qApp->property(overte::ios::tablet_web_deferred::faultProviderProperty());
    if (original.userType()!=qMetaTypeId<overte::ios::tablet_web_deferred::Provider>()) { return {}; }
    const auto provider=original.value<overte::ios::tablet_web_deferred::Provider>();
    return provider ? provider(command) : QVariantMap();
}

QVariantMap TestScriptingInterface::featureIOSTabletAppButtons(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSTabletAppButtons(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !overte::e2e::tablet_sources::enabled()
            || QJsonObject::fromVariantMap(command).value("action")!=QJsonValue("feature-ios-tablet-app-buttons")) { return {}; }
    auto original=command;original["action"]="feature-ios-tablet-sources";
    if (!overte::e2e::tablet_sources::command(original)) { return {}; }
    return overte::e2e::tablet_app_buttons::observe(command);
}

QVariantMap TestScriptingInterface::featureIOSUIKitInput(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSUIKitInput(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !overte::e2e::tablet_sources::enabled()
            || QJsonObject::fromVariantMap(command).value("action")!=QJsonValue("feature-ios-uikit-input")) { return {}; }
    auto original=command;original["action"]="feature-ios-tablet-sources";
    if (!overte::e2e::tablet_sources::command(original)) { return {}; }
    return overte::ios::uikit_input::observation(command);
}

QVariantMap TestScriptingInterface::featureIOSTabletWebClosures(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSTabletWebClosures(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::ios::tablet_web_closures::command(command)) { return {}; }
    const auto original=qApp->property(overte::ios::tablet_web_closures::providerProperty());
    if (original.userType()!=qMetaTypeId<overte::ios::tablet_web_closures::Provider>()) { return {}; }
    const auto provider=original.value<overte::ios::tablet_web_closures::Provider>();
    return provider ? provider(command) : QVariantMap();
}

QVariantMap TestScriptingInterface::featureIOSTabletWebDOM(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSTabletWebDOM(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::ios::tablet_web_trace::domCommand(command)) { return {}; }
    const auto original=qApp->property(overte::ios::tablet_web_trace::domProviderProperty());
    if (original.userType()!=qMetaTypeId<overte::ios::tablet_web_trace::Provider>()) { return {}; }
    const auto provider=original.value<overte::ios::tablet_web_trace::Provider>();
    return provider ? provider(command) : QVariantMap();
}

QVariantMap TestScriptingInterface::featureIOSWorldWeb(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSWorldWeb(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::ios::world_web_trace::command(command)) { return {}; }
    const auto original=qApp->property(overte::ios::world_web_trace::providerProperty());
    if (original.userType()!=qMetaTypeId<overte::ios::world_web_trace::Provider>()) { return {}; }
    const auto provider=original.value<overte::ios::world_web_trace::Provider>();
    return provider ? provider(command) : QVariantMap();
}

QVariantMap TestScriptingInterface::featureIOSWorldWebSnapshot(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSWorldWebSnapshot(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::e2e::IOSWorldWebSnapshotObservation::command(command)) { return {}; }
    if (!_featureIOSWorldWebSnapshot) { _featureIOSWorldWebSnapshot=std::make_shared<overte::e2e::IOSWorldWebSnapshotObservation>(); }
    return _featureIOSWorldWebSnapshot->read(command,[this](const QString& name,const QVariantMap& query) -> QVariantMap {
        if (name=="ledgerBefore" || name=="ledgerAfter") { return featureIOSWorldWeb(query); }
        if (name=="document") { return featureIOSWorldWebDOM(query); }
        if (name=="world") { return featureIOSEmoteWorld(query); }
        if (name=="work") { return featureIOSWorldWebWork(query); }
        if (name=="geometry") { return featureIOSWorldWebGeometry(query); }
        if (name=="keys") { return featureIOSWorldWebKeys(query); }
        if (name=="pointer") { return featureIOSPointerState(query); }
        if (name=="entities") { return featureIOSCreateEntities(query); }
        return {};
    });
}

QVariantMap TestScriptingInterface::featureIOSWorldWebDOM(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureIOSWorldWebDOM(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::ios::world_web_trace::domCommand(command)) { return {}; }
    const auto original=qApp->property(overte::ios::world_web_trace::domProviderProperty());
    if (original.userType()!=qMetaTypeId<overte::ios::world_web_trace::Provider>()) { return {}; }
    const auto provider=original.value<overte::ios::world_web_trace::Provider>();
    return provider ? provider(command) : QVariantMap();
}
#endif

QVariantMap TestScriptingInterface::featureWebDOMObservation(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureWebDOMObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::e2e::webDOMCommand(command)) { return {}; }
    const auto original=qApp->property(overte::e2e::webDOMProviderProperty());
    if (original.userType()!=qMetaTypeId<overte::e2e::WebDOMProvider>()) { return {}; }
    const auto provider=original.value<overte::e2e::WebDOMProvider>();
    return provider ? provider(command) : QVariantMap();
}

QVariantMap TestScriptingInterface::featureChatViewObservation(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureChatViewObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !DependencyManager::isSet<OffscreenUi>()) { return {}; }
    const auto ui=DependencyManager::get<OffscreenUi>();
    if (!ui || !ui->getRootItem()) { return {}; }
    QList<QQuickItem*> roots{ui->getRootItem()};bool shown{false};QVariantMap metrics;
    if (DependencyManager::isSet<TabletScriptingInterface>()) {
        const auto tablets=DependencyManager::get<TabletScriptingInterface>();
        auto tablet=tablets->getTablet("com.highfidelity.interface.tablet.system");
        metrics=tablets->getTouchUiRuntimeMetrics();
        if (tablet) {
            const auto actual=tablet->property("tabletShown");
            if (actual.userType()!=QMetaType::Bool) { return {}; }shown=actual.toBool();
#if defined(Q_OS_IOS)
            roots.append(tablet->getIOSTabletRoot());
#else
            roots.append(tablet->getTabletRoot());
#endif
        }
    }
    if (!_featureChatView) { _featureChatView=std::make_shared<overte::e2e::ChatViewObservation>(); }
    return _featureChatView->request(command,roots,shown,metrics);
}

QVariantMap TestScriptingInterface::featureChatObservation(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this, [&] { result = featureChatObservation(command); }, Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !overte::e2e::previewDirectory(_testResultsLocation)
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    const auto messages = DependencyManager::get<MessagesClient>();
    QVariantMap result;
    const auto read = [&] { result = messages->featureChatObservation(command); };
    if (QThread::currentThread() == messages->thread()) { read(); }
    else if (!QMetaObject::invokeMethod(messages.data(), read, Qt::BlockingQueuedConnection)) { return {}; }
    return result;
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

QVariantMap TestScriptingInterface::featureAvatarReceive(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureAvatarReceive(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);const auto keys=json.keys();
    const auto id=json.value("commandId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || _featureAvatarReceiveSequence>=1000000000
            || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action"}
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue(QStringLiteral("feature-avatar-receive-observe"))
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id).hasMatch()) { return {}; }
    if (!DependencyManager::isSet<NodeList>()) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const auto source=overte::e2e::AvatarReceiveObservation::instance().snapshot(DependencyManager::get<NodeList>()->getSessionUUID());
    if (source.isEmpty()) { return {}; }
    return {{"avatarReceiveObservationVersion",1},{"commandId",id},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureAvatarReceiveSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
}

QVariantMap TestScriptingInterface::featureScriptWork(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureScriptWork(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);const auto keys=json.keys();
    const auto id=json.value("commandId").toString();const auto subject=json.value("managerInstance").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || _featureScriptWorkSequence>=1000000000
            || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","managerInstance"}
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue(QStringLiteral("feature-script-work-observe"))
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(subject).hasMatch()) { return {}; }
    if (!DependencyManager::isSet<ScriptEngines>()) { return {}; }
    if (_featureScriptWorkCommands.contains(id)) {
        if (_featureScriptWorkCommands.value(id)!=command) { return {}; }
        if (_featureScriptWorkResults.contains(id)) { return _featureScriptWorkResults.value(id); }
    } else {
        if (_featureScriptWorkCommands.size()>=4096) { return {}; }
        _featureScriptWorkCommands.insert(id,command);
    }
    const auto source=DependencyManager::get<ScriptEngines>()->featureScriptWorkObservation(subject,id);
    if (source.value("pending").toBool()) { return {{"schemaVersion",1},{"requestId",id},{"pending",true}}; }
    if (source.isEmpty()) { _featureScriptWorkResults.insert(id,QVariantMap{});return {}; }
    const auto work=source.value("work").toMap();
    const auto requested=work.value("requestedEpochMs").toLongLong();const auto captured=QDateTime::currentMSecsSinceEpoch();
    if (requested<=0 || captured<work.value("capturedEpochMs").toLongLong()) { return {}; }
    QVariantMap result{{"schemaVersion",1},{"requestId",id},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureScriptWorkSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",captured},{"source",source}};
    _featureScriptWorkResults.insert(id,result);return result;
}
QVariantMap TestScriptingInterface::featureScriptTerminal(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureScriptTerminal(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);const auto keys=json.keys();
    const auto id=json.value("commandId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || _featureScriptTerminalSequence>=1000000000
            || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action"}
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue(QStringLiteral("feature-script-terminal-observe"))
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id).hasMatch()) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const auto source=overte::e2e::ScriptTerminalObservation::process().snapshot();
    if (source.isEmpty()) { return {}; }
    return {{"scriptTerminalObservationVersion",1},{"commandId",id},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureScriptTerminalSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
}

QVariantMap TestScriptingInterface::featureScriptRoots(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureScriptRoots(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);const auto keys=json.keys();
    const auto id=json.value("commandId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || _featureScriptRootsSequence>=1000000000
            || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action"}
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue(QStringLiteral("feature-script-roots-observe"))
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id).hasMatch()) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    // Actual application resource configuration, not a root inferred from a
    // running engine URL, a caller argument or a matching source basename.
    const auto original=PathUtils::defaultScriptsLocation().toString(QUrl::FullyEncoded);
    if (original.isEmpty()) { return {}; }
    return {{"scriptRootsVersion",1},{"commandId",id},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureScriptRootsSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
        {"source",QVariantMap{{"defaultScriptsUrl",original}}}};
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
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
    // Preserve these passive sources' native compact-byte bounds through AFC.
    // Adding whitespace can exceed the existing reader limit with no new data.
    // Other source writers keep their original encoding.
    if (filename=="feature-ios-snapshot-file-work.json" || filename=="feature-ios-snapshot-inputs.json" || filename=="feature-ios-snapshot-work.json" || filename=="feature-ios-snapshot-exports.json" || filename=="feature-ios-snapshot-captures.json"
            || filename=="feature-ios-tablet-web-dom.json" || filename=="feature-ios-tablet-web-deferred.json" || filename=="feature-ios-tablet-web-defer.json" || filename=="feature-ios-tablet-app-buttons.json" || filename=="feature-ios-uikit-input.json" || filename=="feature-ios-tablet-web-closures.json" || filename=="feature-ios-tablet-web-state.json" || filename=="feature-ios-tablet-web.json" || filename=="feature-ios-tablet-sources.json" || filename=="feature-ios-world-web.json" || filename=="feature-ios-world-web-dom.json"
            || filename=="feature-ios-world-web-work.json" || filename=="feature-ios-world-web-geometry.json" || filename=="feature-ios-world-web-surfaces.json"
            || filename=="feature-ios-world-web-keys.json" || filename=="feature-ios-world-web-snapshot.json") {
        jsonData=jsonDocument.toJson(QJsonDocument::Compact);
    }
#endif

    // Append trailing slash if needed
    if (_testResultsLocation.right(1) != "/") {
        _testResultsLocation += "/";
    }

    QString filepath = QDir::cleanPath(_testResultsLocation + filename);
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (filename == "feature-ios-snapshot-file-work.json" || filename == "feature-ios-snapshot-inputs.json" || filename == "feature-chat-observation.json" || filename == "feature-native-observation.json" || filename == "normal-feature-observation.json"
            || filename == "feature-ios-world-web-snapshot.json" || filename == "feature-ios-world-web-keys.json" || filename == "feature-ios-world-web-work.json" || filename == "feature-ios-world-web-geometry.json" || filename == "feature-ios-world-web-surfaces.json"
            || filename == "feature-ios-tablet-web-dom.json" || filename == "feature-ios-tablet-web-deferred.json" || filename == "feature-ios-tablet-web-defer.json" || filename == "feature-ios-tablet-app-buttons.json" || filename == "feature-ios-uikit-input.json" || filename == "feature-ios-tablet-web-closures.json" || filename == "feature-ios-tablet-web-state.json" || filename == "feature-ios-tablet-web.json" || filename == "feature-ios-tablet-sources.json" || filename == "feature-ios-world-web.json" || filename == "feature-ios-world-web-dom.json"
            || filename == "feature-ios-web-closures.json" || filename == "feature-ios-location-bookmarks.json" || filename == "feature-ios-places-model.json" || filename == "feature-ios-places-http.json" || filename == "feature-ios-navigation-dialogs.json" || filename == "feature-ios-navigation-state.json" || filename == "feature-ios-scene-inventory.json" || filename == "feature-chat-view-observation.json" || filename == "feature-web-dom-observation.json"
            || filename == "feature-pending-commit-owner.json" || filename == "feature-navigation-replies.json"
            || filename == "feature-process-presence.json" || filename == "feature-graphics-subject.json" || filename == "feature-scene-load.json" || filename == "feature-completed-frame.json" || filename == "feature-vulkan-world-frame.json"
            || filename == "recorded-preview-observation.json" || filename == "feature-script-observation.json"
            || filename == "feature-avatar-receive.json" || filename == "feature-script-roots.json" || filename == "feature-script-terminal.json" || filename == "feature-script-work.json"
            || filename == "feature-ios-script-dialogs.json" || filename == "feature-ios-emote-world.json" || filename == "feature-ios-avatar-world.json" || filename == "feature-ios-avatar-inputs.json" || filename == "feature-ios-avatar-social-http.json" || filename == "feature-ios-avatar-state.json" || filename == "feature-ios-avatar-renderers.json" || filename == "feature-ios-avatar-scripts.json" || filename == "feature-ios-avatar-entities.json" || filename == "feature-ios-create-entities.json" || filename == "feature-ios-pointer-state.json"
            || filename == "feature-ios-people-model.json" || filename == "feature-ios-create-work.json" || filename == "feature-ios-create-state.json" || filename == "feature-ios-create-files.json"
            || filename == "feature-ios-snapshot-work.json" || filename == "feature-ios-snapshot-exports.json"
            || filename == "feature-ios-snapshot-captures.json"
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
