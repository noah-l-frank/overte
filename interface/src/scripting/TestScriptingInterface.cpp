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
#include <QJsonArray>
#include "../../../tests/device/native/FeatureLifecycle.h"
#include "../../../tests/device/native/ChatViewObservation.h"
#include "../../../tests/device/native/WebDOMObservationBridge.h"
#include "../../../tests/device/native/PhoneWebRuntimeBridge.h"
#include "../../../tests/device/native/PhoneWorldWebBridge.h"
#include "../../../tests/device/native/PendingFieldCommitBridge.h"
#include "../../../tests/device/native/ProcessPresence.h"
#include <ui/TabletScriptingInterface.h>
#include "../../../tests/device/native/PrivatePreviewFiles.h"
#include "../../../tests/device/native/PrivateWorldRenderReceipts.h"
#include "../../../tests/device/native/PrivateScriptFiles.h"
#include "../../../tests/device/native/PrivateAccountOrigin.h"
#include "../../../tests/device/native/PrivateAccountOriginLease.h"
#include "avatar/AvatarManager.h"
#include "RenderScriptingInterface.h"
#include <AccountManager.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <udt/PacketHeaders.h>
#include "../../../tests/device/native/NavigationViewObservation.h"
#include "../LocationBookmarks.h"
#include "../AvatarBookmarks.h"
#include <FeatureResourceReplies.h>
#include <FeaturePeopleReplies.h>
#include <FeatureAvatarEntityOrigins.h>
#include <EntityTreeRenderer.h>
#include <RenderableModelEntityItem.h>
#include <NodeList.h>
#include "../../../tests/device/native/AvatarPeopleViewObservation.h"
#endif
#include <PathUtils.h>
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
#include <AnimationCache.h>
#if defined(ANDROID_APP_PHONE_INTERFACE)
#include "../../../tests/device/native/ScriptFileUi.h"
#include "../../../tests/device/native/PhoneAudioFixtureHTTP.h"
#include <PhoneSnapshotUploadEvidence.h>
#include "../../../tests/device/native/PhoneAvatarConfiguration.h"
#include "../../../tests/device/native/PhoneEmoteFixture.h"
#include "../../../tests/device/native/PhoneCreateFixture.h"
#include "../../../tests/device/native/PhoneAssetsReadJob.h"
#include "../../../tests/device/native/PrivateAssetsFiles.h"
#include <AssetClient.h>
#include <AssetRequest.h>
#include <MappingRequest.h>
#include "AssetMappingsScriptingInterface.h"
#include "../../../tests/device/native/PhoneCreateObservation.h"
#include "../../../tests/device/native/PrivateCreateFiles.h"
#include "ui/Snapshot.h"
#include "../../../tests/device/native/PhoneSnapshotReviewObservation.h"
#include "../../../tests/device/native/PhoneSnapshotFastCancel.h"
#include "../../../tests/device/native/PhoneSnapshotCaptureFiles.h"
#include "../../../tests/device/native/PhoneSnapshotHandoff.h"
#include "NativeSnapshotAdapter.h"
#include "../../../tests/device/native/PhoneNavigationMarker.h"
#include "../../../tests/device/native/PhoneLifecycleEditor.h"
#include "../../../tests/device/native/PhoneLifecycleWorldInput.h"
#include "../../../tests/device/native/PhoneLifecycleMotion.h"
#include <SettingHandle.h>
#include "../../../tests/device/adapters/android-phone/PendingCommitOwner.h"
#include "../../../tests/device/native/PrivateFeatureCommand.h"
#include <QMouseEvent>
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
#include <QSaveFile>
#include <QDateTime>
#include <QJsonObject>
#include <QJsonArray>
#include <QAccessible>
#include <QInputMethod>
#include <QQmlProperty>
#include <QQmlEngine>
#include <functional>
#if defined(Q_OS_ANDROID)
#include <QtAndroidExtras/QAndroidJniObject>
#endif
#include <ui/PhoneTextInputFixture.h>
#include <ui/TabletScriptingInterface.h>
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

QVariantMap TestScriptingInterface::featureWorldModelDrawsObservation(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result = featureWorldModelDrawsObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    const auto context = qApp->getGPUContext();
    return context ? context->featureWorldRender()->modelObservation(command) : QVariantMap();
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

QVariantMap TestScriptingInterface::featureWorldRenderReceipts(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this,[&] { result = featureWorldRenderReceipts(command); },Qt::BlockingQueuedConnection);
        return result;
    }
    const auto json = QJsonObject::fromVariantMap(command);
    QStringList fields {"schemaVersion","commandId","action","requestId","receiptIds","operation"}; fields.sort();
    const auto id = command.value("commandId").toString(), capture = command.value("requestId").toString();
    const auto operation = command.value("operation").toString();
    if (_testResultsLocation.isEmpty() || !QCoreApplication::arguments().contains("--testScript")
            || command.keys() != fields || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble() != 1
            || !json.value("commandId").isString() || !json.value("requestId").isString()
            || json.value("action").toString() != "feature-world-render-receipts"
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id).hasMatch()
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(capture).hasMatch()
            || (operation != "remove" && operation != "inspect") || !json.value("receiptIds").isArray()
            || QJsonDocument(json).toJson(QJsonDocument::Compact).size() > 49152) { return {}; }
    const auto values = json.value("receiptIds").toArray();
    if (values.isEmpty() || values.size() > 1024) { return {}; }
    QStringList ids;
    for (const auto& value : values) {
        if (!value.isString()) { return {}; }
        ids.append(value.toString());
    }
    const auto context = qApp->getGPUContext();
    if (!context || !overte::e2e::previewDirectory(_testResultsLocation)) { return {}; }
    const auto state = context->featureWorldRender();
    const auto inventory = state->receiptInventory(capture,ids);
    if (inventory.isEmpty()) { return {}; }
    const auto root = _testResultsLocation.endsWith('/') ? _testResultsLocation : _testResultsLocation+'/';
    const auto issued = inventory.value("receipts").toList();
    // Verify the complete original set before deleting any file. Unissued
    // selectors are observations only; they never authorize deletion of a
    // present file. Retired/drained capture state prevents new native storage
    // issuance, and the existing probe serializes its original file writes.
    for (const auto& value : issued) {
        const auto row = value.toMap();
        auto nonce = row.value("receiptId").toString();
        if (nonce.startsWith("ios-")) { nonce.remove(0,4); }
        const auto path = root+"world-render-storage-"+nonce+".json";
        const QFileInfo info(path);
        if (info.exists() && !row.value("issued").toBool()) { return {}; }
        const auto digest = info.exists() ? row.value("digest").toString().toLatin1() : QByteArray();
        if (!overte::e2e::ownWorldRenderReceipt(path,digest)) { return {}; }
    }
    bool performed {true};
    if (operation == "remove") {
        for (const auto& value : issued) {
            const auto row = value.toMap();
            if (!row.value("issued").toBool()) { continue; }
            auto nonce = row.value("receiptId").toString();
            if (nonce.startsWith("ios-")) { nonce.remove(0,4); }
            const auto path = root+"world-render-storage-"+nonce+".json";
            if (!overte::e2e::ownWorldRenderReceipt(path,QFileInfo::exists(path) ? row.value("digest").toString().toLatin1() : QByteArray())) { return {}; }
            if (QFileInfo::exists(path) && !QFile::remove(path)) { performed=false; }
        }
    }
    QVariantList observations;
    for (const auto& value : issued) {
        const auto row = value.toMap();
        auto nonce = row.value("receiptId").toString();
        if (nonce.startsWith("ios-")) { nonce.remove(0,4); }
        const auto path = root+"world-render-storage-"+nonce+".json";
        const QFileInfo current(path);
        const bool exists = current.exists() || current.isSymLink();
        const bool matches = row.value("issued").toBool() && exists
            && overte::e2e::ownWorldRenderReceipt(path,row.value("digest").toString().toLatin1());
        observations.append(QVariantMap{{"receiptId",row.value("receiptId")},{"issued",row.value("issued")},
            {"exists",exists},{"originalMatches",matches}});
    }
    QVariantMap source {{"retired",inventory.value("retired")},{"present",inventory.value("present")},
        {"callbacks",inventory.value("callbacks")},{"pngBytes",inventory.value("pngBytes")},{"complete",observations.size()==ids.size()},
        {"receipts",observations}};
    if (operation == "remove") { source.insert("performed",performed); }
    return {{"receiptInventoryVersion",1},{"commandId",id},{"requestId",capture},{"operation",operation},
        {"instance",inventory.value("instance")},{"sequence",static_cast<qulonglong>(++_featureWorldReceiptsSequence)},
        {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
}

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
#if defined(ANDROID_APP_PHONE_INTERFACE)
    overte::e2e::installPhonePendingCommitOwner([this] {
        return !_testResultsLocation.isEmpty() && _featureLifecycle && !_featureLifecycle->snapshot().isEmpty()
            && QCoreApplication::arguments().contains("--testScript")
            && overte::e2e::previewDirectory(_testResultsLocation);
    });
#endif
    const auto original = qApp->property(overte::e2e::pendingCommitProviderProperty());
    if (original.userType() != qMetaTypeId<overte::e2e::PendingCommitProvider>()) { return {}; }
    const auto provider = original.value<overte::e2e::PendingCommitProvider>();
    return provider ? provider(command) : QVariantMap();
}

QVariantMap TestScriptingInterface::featurePhoneWebRuntimeObservation(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featurePhoneWebRuntimeObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::e2e::phoneWebRuntimeCommand(command)) { return {}; }
    const auto original=qApp->property(overte::e2e::phoneWebRuntimeProperty());
    if (original.userType()!=qMetaTypeId<overte::e2e::PhoneWebRuntimeProvider>()) { return {}; }
    const auto provider=original.value<overte::e2e::PhoneWebRuntimeProvider>();
    return provider ? provider(command) : QVariantMap();
}

QVariantMap TestScriptingInterface::featurePhoneWorldWeb(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featurePhoneWorldWeb(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::e2e::phoneWorldWebCommand(command)) { return {}; }
    const auto original=qApp->property(overte::e2e::phoneWorldWebProperty());
    if (original.userType()!=qMetaTypeId<overte::e2e::WebDOMProvider>()) { return {}; }
    const auto provider=original.value<overte::e2e::WebDOMProvider>();
    return provider ? provider(command) : QVariantMap();
}

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
    if (command.value("action")=="feature-chat-history") { return _featureChatView->historyRequest(command,roots,shown,metrics); }
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

#if defined(ANDROID_APP_PHONE_INTERFACE)
QVariantMap TestScriptingInterface::phoneAudioFixture(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this, [&] { result = phoneAudioFixture(command); }, Qt::BlockingQueuedConnection);
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || !overte::e2e::previewDirectory(_testResultsLocation)) { return {}; }
    if (!_phoneAudioFixture) {
        const auto audio = DependencyManager::get<AudioClient>();
        _phoneAudioFixture = std::make_shared<overte::e2e::PhoneAudioFixtureHTTP>(this,
            [audio](const QByteArray& pcm, const QVariantMap& receipt) {
                bool armed = false;
                QMetaObject::invokeMethod(audio.data(), [&] { armed = audio->armPhoneAudioFixture(pcm, receipt); }, Qt::BlockingQueuedConnection);
                return armed;
            }, [audio] {
                QVariantMap value;
                QMetaObject::invokeMethod(audio.data(), [&] { value = audio->phoneAudioFixtureObservation(); }, Qt::BlockingQueuedConnection);
                return value;
            }, [audio] {
                QMetaObject::invokeMethod(audio.data(), [audio] { audio->releasePhoneAudioFixture(); }, Qt::BlockingQueuedConnection);
            });
    }
    return _phoneAudioFixture->command(command);
}
#endif

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
    if (_featureScriptWorkCommand.value("commandId")==QVariant(id)) {
        return command==_featureScriptWorkCommand ? _featureScriptWorkResult : QVariantMap();
    }
    const auto source=DependencyManager::get<ScriptEngines>()->featureScriptWorkObservation(subject,id);
    if (source.value("pending").toBool()) { return {{"schemaVersion",1},{"requestId",id},{"pending",true}}; }
    if (source.isEmpty()) { return {}; }
    const auto work=source.value("work").toMap();
    const auto requested=work.value("requestedEpochMs").toLongLong();const auto captured=QDateTime::currentMSecsSinceEpoch();
    if (requested<=0 || captured<work.value("capturedEpochMs").toLongLong()) { return {}; }
    QVariantMap result{{"schemaVersion",1},{"requestId",id},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureScriptWorkSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",captured},{"source",source}};
    _featureScriptWorkCommand=command;_featureScriptWorkResult=result;return result;
}

QVariantMap TestScriptingInterface::featureAnimationInventory(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureAnimationInventory(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);const auto keys=json.keys();
    const auto id=json.value("commandId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || _featureAnimationInventorySequence>=1000000000
            || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action"}
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue(QStringLiteral("feature-animation-inventory-observe"))
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id).hasMatch()) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();QVariantMap source{{"complete",false}};
    // isSet is essential: an observer must not instantiate a cache or resource.
    if (DependencyManager::isSet<AnimationCache>()) { source=DependencyManager::get<AnimationCache>()->featureResourceObservation(); }
    return {{"animationInventoryVersion",1},{"commandId",id},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureAnimationInventorySequence)},
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

QVariantMap TestScriptingInterface::featureSceneLoadObservation(const QVariantMap& command) {
#if defined(ANDROID_APP_PHONE_INTERFACE)
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
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    auto value=qApp->phoneSceneLoadObservation();
    value.insert("commandId",id);value.insert("runId",run);
    value.insert("processId",QCoreApplication::applicationPid());
    value.insert("capturedEpochMs",QDateTime::currentMSecsSinceEpoch());
    return value;
#else
    Q_UNUSED(command);return {};
#endif
}

QVariantMap TestScriptingInterface::phoneEmoteFixtureInput(const QVariantMap& command) {
#if defined(ANDROID_APP_PHONE_INTERFACE)
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneEmoteFixtureInput(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    const auto avatar=DependencyManager::get<AvatarManager>()->getMyAvatar();
    if (!avatar) { return {}; }
    if (!_phoneEmoteFixture) { _phoneEmoteFixture=std::make_shared<overte::e2e::PhoneEmoteFixture>(); }
    ViewFrustum view;qApp->getCamera().loadViewFrustum(view);
    return _phoneEmoteFixture->input(command,view,qApp->getCamera().getModeString(),
        avatar->getWorldFeetPosition(),avatar->getModelScale(),avatar->getBoomLength());
#else
    Q_UNUSED(command);return {};
#endif
}

QVariantMap TestScriptingInterface::phoneEmoteFixtureObservation(const QVariantMap& command) {
#if defined(ANDROID_APP_PHONE_INTERFACE)
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneEmoteFixtureObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);
    const auto id=json.value("commandId").toString(),run=json.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !_phoneEmoteFixture
            || command.keys()!=QStringList{"action","commandId","runId","schemaVersion"}
            || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble()!=1
            || json.value("action").toString()!="phone-emote-fixture-observe"
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const auto source=_phoneEmoteFixture->observe(run);
    if (source.isEmpty()) { return {}; }
    return {{"schemaVersion",1},{"requestId",id},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_phoneEmoteFixtureSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
#else
    Q_UNUSED(command);return {};
#endif
}

#if defined(ANDROID_APP_PHONE_INTERFACE)
namespace {
overte::e2e::MeasuredCameraLease::Source measuredPhoneCamera() {
    auto* camera=&qApp->getCamera();
    return {camera,[camera] {
        if (camera->e2eKeepsLookingAt()) { return QVariantMap(); }
        const auto p=camera->getPosition();const auto q=camera->getOrientation();const auto projection=camera->getProjection();QVariantList matrix;
        for (int row=0;row<4;++row) { for (int column=0;column<4;++column) { matrix.append(projection[column][row]); } }
        return QVariantMap{{"mode",camera->getModeString()},{"position",QVariantList{p.x,p.y,p.z}},
            {"rotation",QVariantList{q.x,q.y,q.z,q.w}},{"projection",matrix}};
    },[camera](const QVariantMap& captured,bool hold) {
        const auto p=captured.value("position").toList(),q=captured.value("rotation").toList(),matrix=captured.value("projection").toList();
        if (p.size()!=3 || q.size()!=4 || matrix.size()!=16 || camera->e2eKeepsLookingAt()) { return; }
        glm::mat4 projection;
        for (int row=0;row<4;++row) { for (int column=0;column<4;++column) { projection[column][row]=matrix[row*4+column].toFloat(); } }
        if (hold) { camera->setMode(CAMERA_MODE_INDEPENDENT); }
        camera->setPosition(glm::vec3(p[0].toFloat(),p[1].toFloat(),p[2].toFloat()));
        camera->setOrientation(glm::quat(q[3].toFloat(),q[0].toFloat(),q[1].toFloat(),q[2].toFloat()));camera->setProjection(projection);
        if (!hold) { camera->setModeString(captured.value("mode").toString()); }
    }};
}
}
QVariantMap TestScriptingInterface::phoneNavigationMarkerInput(const QVariantMap& command) {
#if defined(ANDROID_APP_PHONE_INTERFACE)
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneNavigationMarkerInput(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    const auto avatar=DependencyManager::get<AvatarManager>()->getMyAvatar();
    if (!avatar) { return {}; }
    if (!_phoneNavigationMarker) {
        _phoneNavigationMarker=std::make_shared<overte::e2e::PhoneNavigationMarker>();
        const std::weak_ptr<overte::e2e::PhoneNavigationMarker> weak=_phoneNavigationMarker;
        QObject::connect(&qApp->getCamera(),&Camera::modeUpdated,this,[weak](const QString&) { if (const auto fixture=weak.lock()) { fixture->cameraModeChanged(); } });
    }
    ViewFrustum view;qApp->getCamera().loadViewFrustum(view);
    return _phoneNavigationMarker->input(command,view,qApp->getCamera().getModeString(),
        avatar->getWorldFeetPosition(),avatar->getModelScale(),avatar->getBoomLength(),measuredPhoneCamera());
#else
    Q_UNUSED(command);return {};
#endif
}

QVariantMap TestScriptingInterface::phoneNavigationMarkerObservation(const QVariantMap& command) {
#if defined(ANDROID_APP_PHONE_INTERFACE)
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneNavigationMarkerObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);
    const auto id=json.value("commandId").toString(),run=json.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !_phoneNavigationMarker
            || command.keys()!=QStringList{"action","commandId","runId","schemaVersion"}
            || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble()!=1
            || json.value("action").toString()!="phone-navigation-marker-observe"
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const auto source=_phoneNavigationMarker->observe(run,measuredPhoneCamera());
    if (source.isEmpty()) { return {}; }
    return {{"schemaVersion",1},{"requestId",id},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_phoneNavigationMarkerSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
#else
    Q_UNUSED(command);return {};
#endif
}

#endif

QVariantMap TestScriptingInterface::phoneLifecycleWorldInput(const QVariantMap& command) {
#if defined(ANDROID_APP_PHONE_INTERFACE)
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneLifecycleWorldInput(command); },Qt::BlockingQueuedConnection))return {};
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript"))return {};
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    if (!_phoneLifecycleWorldInput)_phoneLifecycleWorldInput=std::make_shared<overte::e2e::PhoneLifecycleWorldInput>();
    const auto controls=_phoneLifecycleWorldInput->request(command,qApp->phoneLifecycleInputWidget(),overte::e2e::PhoneLifecycleMotion::get().snapshot());
    const auto motion=overte::e2e::PhoneLifecycleMotion::get().snapshot();
    if (controls.isEmpty() || motion.isEmpty())return {};
    return {{"schemaVersion",1},{"requestId",command.value("commandId")},{"runId",command.value("runId")},
        {"instance",_featureObservationInstance},{"sequence",static_cast<qulonglong>(++_phoneLifecycleWorldInputSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
        {"source",controls},{"motion",motion}};
#else
    Q_UNUSED(command);return {};
#endif
}

QVariantMap TestScriptingInterface::phoneLifecycleEditor(const QVariantMap& command) {
#if defined(ANDROID_APP_PHONE_INTERFACE)
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneLifecycleEditor(command); },Qt::BlockingQueuedConnection))return {};
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);
    const auto id=json.value("commandId").toString(),run=json.value("runId").toString();
    const bool input=json.value("action")==QJsonValue("phone-lifecycle-editor-input");
    const QStringList keys=input ? QStringList{"action","commandId","fieldToken","observationSequence","operation","runId","schemaVersion"}
        : QStringList{"action","commandId","runId","schemaVersion"};
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=keys
            || json.value("schemaVersion")!=QJsonValue(1) || (!input && json.value("action")!=QJsonValue("phone-lifecycle-editor-observe"))
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch() || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            || !DependencyManager::isSet<OffscreenUi>() || !DependencyManager::isSet<TabletScriptingInterface>())return {};
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const auto ui=DependencyManager::get<OffscreenUi>();const auto tablet=DependencyManager::get<TabletScriptingInterface>();
    auto metrics=tablet->getTouchUiRuntimeMetrics();
    if (!metrics.value("valid").toBool() || metrics.value("keyboardVisible").userType()!=QMetaType::Bool)return {};
    if (!_phoneLifecycleEditor)_phoneLifecycleEditor=std::make_shared<overte::e2e::PhoneLifecycleEditor>();
    const bool performed=input && _phoneLifecycleEditor->input(command,ui->getRootItem(),ui->getWindow(),metrics.value("keyboardVisible").toBool());
    metrics=tablet->getTouchUiRuntimeMetrics();
    if (!metrics.value("valid").toBool() || metrics.value("keyboardVisible").userType()!=QMetaType::Bool)return {};
    const auto original=_phoneLifecycleEditor->observe(ui->getRootItem(),ui->getWindow(),run,metrics.value("keyboardVisible").toBool());
    if (original.isEmpty())return {};
    return {{"schemaVersion",1},{"requestId",id},{"runId",run},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_phoneLifecycleEditorSequence)},{"processId",QCoreApplication::applicationPid()},
        {"requestedEpochMs",requested},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"performed",performed},{"source",original}};
#else
    Q_UNUSED(command);return {};
#endif
}

QVariantMap TestScriptingInterface::phoneTouchObservation(const QVariantMap& command) {
#if defined(ANDROID_APP_PHONE_INTERFACE)
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneTouchObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);
    const auto request=command.value("commandId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || command.keys()!=QStringList{"action","commandId","schemaVersion"}
            || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble()!=1
            || command.value("action").toString()!="phone-touch-state-observe"
            || !json.value("commandId").isString()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(request).hasMatch()) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    auto source=qApp->phoneTouchObservation();
    if (source.isEmpty()) { return {}; }
    source.insert("phoneTouchStateVersion",1);
    return {{"schemaVersion",1},{"requestId",request},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_phoneTouchSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
#else
    Q_UNUSED(command); return {};
#endif
}

QVariantMap TestScriptingInterface::phoneAvatarConfigurationObservation(const QVariantMap& command) {
#if defined(ANDROID_APP_PHONE_INTERFACE)
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result = phoneAvatarConfigurationObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json = QJsonObject::fromVariantMap(command);
    const auto request = command.value("commandId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || command.keys() != QStringList{"action","commandId","schemaVersion"}
            || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble() != 1
            || command.value("action").toString() != "phone-avatar-configuration-observe"
            || !json.value("commandId").isString()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(request).hasMatch()) { return {}; }
    const auto requested = QDateTime::currentMSecsSinceEpoch();
    const auto avatar = DependencyManager::get<AvatarManager>()->getMyAvatar();
    if (!avatar) { return {}; }
    const auto model = avatar->getSkeletonModel();
    if (!model) { return {}; }
    const auto geometry = model->getGeometry();
    QVariant loaded;
    if (geometry && geometry->isHFMModelLoaded()) {
        loaded = QVariantMap{{"instance",geometry->e2eGeometryInstance()},
            {"source",overte::e2e::phoneAvatarUrlSource(geometry->getHFMModel().originalURL,"meshes/mannequin/mannequin.fbx")}};
    }
    const QVariantMap source{{"phoneAvatarConfigurationVersion",1},{"modelInstance",model->e2eModelInstance()},
        {"rigId",model->getRig().e2eRigId()},
        {"configured",overte::e2e::phoneAvatarUrlSource(avatar->getSkeletonModelURL(),"meshes/defaultAvatar_full.fst")},
        {"loadedGeometry",loaded},{"boomLength",avatar->getBoomLength()},
        {"pinchZoomEnabled",Setting::Handle<bool>{"android/phone/pinchZoomEnabled",false}.get()}};
    return {{"schemaVersion",1},{"requestId",request},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_phoneAvatarConfigurationSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
#else
    Q_UNUSED(command); return {};
#endif
}

QVariantMap TestScriptingInterface::featureAvatarRenderObservation(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result = featureAvatarRenderObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json = QJsonObject::fromVariantMap(command);
    const auto request = command.value("commandId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || command.keys() != QStringList{"action","commandId","schemaVersion"}
            || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble() != 1
            || command.value("action").toString() != "feature-avatar-render-observe"
            || !json.value("commandId").isString()
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(request).hasMatch()) { return {}; }
    const auto requested = QDateTime::currentMSecsSinceEpoch();
    const auto avatar = DependencyManager::get<AvatarManager>()->getMyAvatar();
    if (!avatar) { return {}; }
    const auto model = avatar->getSkeletonModel();
    if (!model) { return {}; }
    const auto geometry = model->getGeometry();
    QVariant loadedGeometry;
    if (geometry && geometry->isHFMModelLoaded()) {
        // This is the immutable loaded HFM source, never the requested Model URL.
        const auto source = geometry->getHFMModel().originalURL.toUtf8();
        loadedGeometry = QVariantMap{{"instance",geometry->e2eGeometryInstance()},{"sourcePresent",!source.isEmpty()},
            {"sourceSha256",QString::fromLatin1(QCryptographicHash::hash(source,QCryptographicHash::Sha256).toHex())}};
    }
    const auto& camera = qApp->getCamera();
    ViewFrustum frustum; camera.loadViewFrustum(frustum);
    QVariantList projection;
    const auto& matrix = frustum.getProjection();
    for (int row = 0; row < 4; ++row) {
        for (int column = 0; column < 4; ++column) { projection.append(matrix[column][row]); }
    }
    auto vec = [](const glm::vec3& value) { return QVariantList{value.x,value.y,value.z}; };
    auto quat = [](const glm::quat& value) { return QVariantList{value.x,value.y,value.z,value.w}; };
    const QVariantMap source {{"avatarRenderVersion",1},{"modelInstance",model->e2eModelInstance()},
        {"rigId",model->getRig().e2eRigId()},{"loaded",model->isLoaded()},{"visible",model->isVisible()},
        {"addedToScene",model->isAddedToScene()},{"localRenderingEnabled",avatar->getShouldRenderLocally()},
        {"avatarShouldRender",avatar->shouldRender()},{"geometry",loadedGeometry},
        {"pose",QVariantMap{{"feetPosition",vec(avatar->getWorldFeetPosition())},
            {"orientation",quat(avatar->getWorldOrientation())},{"modelScale",avatar->getModelScale()}}},
        {"cameraMode",camera.getModeString()},
        {"view",QVariantMap{{"position",vec(frustum.getPosition())},{"rotation",quat(frustum.getOrientation())},
            {"projection",projection},{"fieldOfViewDegrees",frustum.getFieldOfView()},{"aspectRatio",frustum.getAspectRatio()},
            {"nearClip",frustum.getNearClip()},{"farClip",frustum.getFarClip()},{"perspective",frustum.isPerspective()}}}};
    return {{"schemaVersion",1},{"requestId",request},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureAvatarRenderSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
}

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
            || !QCoreApplication::arguments().contains("--testScript") || command.keys() != fields
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
    if (QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size() > 200000) { return {}; }
    return {{"schemaVersion",1},{"requestId",request},{"runId",run},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureGraphicsSubjectSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
}
#if defined(ANDROID_APP_PHONE_INTERFACE)
QVariantMap TestScriptingInterface::phoneCreateFixtureInput(const QVariantMap& command) {
#if defined(ANDROID_APP_PHONE_INTERFACE)
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneCreateFixtureInput(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    const auto avatar=DependencyManager::get<AvatarManager>()->getMyAvatar();
    if (!avatar) { return {}; }
    if (!_phoneCreateFixture) { _phoneCreateFixture=std::make_shared<overte::e2e::PhoneCreateFixture>(); }
    ViewFrustum view;qApp->getCamera().loadViewFrustum(view);
    return _phoneCreateFixture->input(command,view,qApp->getCamera().getModeString(),
        avatar->getWorldFeetPosition(),avatar->getModelScale(),avatar->getBoomLength());
#else
    Q_UNUSED(command);return {};
#endif
}

QVariantMap TestScriptingInterface::phoneCreateFixtureObservation(const QVariantMap& command) {
#if defined(ANDROID_APP_PHONE_INTERFACE)
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneCreateFixtureObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);
    const auto id=json.value("commandId").toString(),run=json.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !_phoneCreateFixture
            || command.keys()!=QStringList{"action","commandId","runId","schemaVersion"}
            || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble()!=1
            || json.value("action").toString()!="phone-create-fixture-observe"
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const auto source=_phoneCreateFixture->observe(run);
    if (source.isEmpty()) { return {}; }
    return {{"schemaVersion",1},{"requestId",id},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_phoneCreateFixtureSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
#else
    Q_UNUSED(command);return {};
#endif
}

QVariantMap TestScriptingInterface::phoneSnapshotUploadObservation(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneSnapshotUploadObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()) { return {}; }
    return overte::e2e::phoneSnapshotUploadObservation(command,_featureObservationInstance,_phoneSnapshotUploadObservationSequence);
}

QVariantMap TestScriptingInterface::phoneSnapshotObservation(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneSnapshotObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);
    QStringList keys{"schemaVersion","commandId","action","runId"};keys.sort();
    const QRegularExpression nonce("\\A[0-9a-f]{32}\\z");
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=keys
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("phone-snapshot-observe")
            || !json.value("commandId").isString() || !nonce.match(json.value("commandId").toString()).hasMatch()
            || !json.value("runId").isString() || !nonce.match(json.value("runId").toString()).hasMatch()
            || !DependencyManager::isSet<Snapshot>()) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const auto snapshot=DependencyManager::get<Snapshot>();QVariantMap source;
    const auto read=[&] { source=snapshot->featureSnapshotObservation(); };
    if (QThread::currentThread()==snapshot->thread()) { read(); }
    else if (!QMetaObject::invokeMethod(snapshot.data(),read,Qt::BlockingQueuedConnection)) { return {}; }
    if (!DependencyManager::isSet<OffscreenUi>()) { return {}; }
    const auto review=overte::e2e::phoneSnapshotReviewObservation(DependencyManager::get<OffscreenUi>()->getRootItem());
    if (review.isEmpty()) { return {}; }
    const auto androidExport=QJsonDocument::fromJson(NativeSnapshotAdapter::featureExportObservation().toUtf8());
    if (!androidExport.isObject()) { return {}; }
    source.insert("phoneSnapshotObservationVersion",5);source.insert("review",review);
    source.insert("androidExport",androidExport.object().toVariantMap());
    if (source.isEmpty() || QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size()>200000) { return {}; }
    return {{"schemaVersion",1},{"requestId",command.value("commandId")},{"runId",command.value("runId")},
        {"instance",_featureObservationInstance},{"sequence",static_cast<qulonglong>(++_phoneSnapshotObservationSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
}

QVariantMap TestScriptingInterface::phoneSnapshotHandoff(const QVariantMap& command) {
    using Handoff=overte::e2e::PhoneSnapshotHandoff;
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneSnapshotHandoff(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !Handoff::validCommand(command) || !QCoreApplication::arguments().contains("--testScript")
            || _phoneSnapshotHandoffSequence>=1000000000) { return {}; }
    const auto run=command.value("runId").toString(),id=command.value("handoffId").toString(),operation=command.value("operation").toString();
    auto owner=_phoneSnapshotHandoffs.value(id);
    if (!owner) {
        if (operation!="start" || _phoneSnapshotHandoffs.size()>=8) { return {}; }
        for (const auto& original:_phoneSnapshotHandoffs) { if (!original || !original->retired()) { return {}; } }
        const auto read=[this,run] {
            const auto nonce=[] { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); };
            const auto roots=[&] { return featureScriptRoots({{"schemaVersion",1},{"commandId",nonce()},{"action","feature-script-roots-observe"}}); };
            // These are the existing original native getters. No JS handler,
            // UI mutation or background command transport is introduced.
            const auto contextRequested=QDateTime::currentMSecsSinceEpoch();
            const auto lifecycle=_featureLifecycle->snapshot();
            QVariantMap accountState;const auto account=DependencyManager::get<AccountManager>();
            if (!account || lifecycle.isEmpty()) { return QVariantMap{}; }
            accountState=Handoff::ownedRead(account.data(),[account] { return account->featureAccountObservation(); });
            if (accountState.isEmpty()) { return QVariantMap{}; }
            const QVariantMap context{{"snapshotHandoffContextVersion",1},{"requestedEpochMs",contextRequested},
                {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"lifecycle",lifecycle.toVariantMap()},{"account",accountState}};
            const auto before=roots();const auto script=featureScriptObservation(nonce());
            const auto snapshot=phoneSnapshotObservation({{"schemaVersion",1},{"commandId",nonce()},{"action","phone-snapshot-observe"},{"runId",run}});
            const auto after=roots();
            const auto readbacks=phoneSnapshotReadback({{"schemaVersion",1},{"commandId",nonce()},{"action","phone-snapshot-readback"},
                {"runId",run},{"operation","observe"},{"exportRequest",""},{"resourceId",""}});
            const auto files=phoneSnapshotCaptureFiles({{"schemaVersion",1},{"commandId",nonce()},{"action","phone-snapshot-files-observe"},{"runId",run}});
            const auto upload=phoneSnapshotUploadObservation({{"schemaVersion",1},{"commandId",nonce()},{"action","phone-snapshot-upload-observe"},{"runId",run}});
            if (before.isEmpty() || script.isEmpty() || snapshot.isEmpty() || after.isEmpty() || readbacks.isEmpty() || files.isEmpty() || upload.isEmpty()) { return QVariantMap{}; }
            return QVariantMap{{"context",context},{"group",QVariantMap{{"rootsBefore",before},{"script",script},{"snapshot",snapshot},{"rootsAfter",after}}},
                {"readbacks",readbacks},{"captureFiles",files},{"upload",upload}};
        };
        const auto publish=[this](const QVariantMap& source) {
            QVariantList jobs;for (const auto& original:_phoneSnapshotHandoffs) { jobs.append(original->summary()); }
            saveObject(QVariantMap{{"snapshotHandoffSourceVersion",1},{"instance",_featureObservationInstance},
                {"processId",QCoreApplication::applicationPid()},{"publishedEpochMs",QDateTime::currentMSecsSinceEpoch()},
                {"source",source},{"jobs",jobs}},"phone-snapshot-handoff.json");
        };
        owner=std::make_shared<Handoff>(run,id,read,publish);_phoneSnapshotHandoffs.insert(id,owner);
    }
    const auto identity=owner->summary();
    if (identity.value("runId")!=run || (operation=="start" && !owner->start()) || (operation=="retire" && !owner->retire())) { return {}; }
    QVariantList jobs;for (const auto& original:_phoneSnapshotHandoffs) { jobs.append(original->summary()); }
    return {{"snapshotHandoffControlVersion",1},{"requestId",command.value("commandId")},{"runId",run},{"handoffId",id},
        {"instance",_featureObservationInstance},{"processId",QCoreApplication::applicationPid()},
        {"sequence",static_cast<qulonglong>(++_phoneSnapshotHandoffSequence)},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
        {"source",owner->observation()},{"jobs",jobs}};
}

QVariantMap TestScriptingInterface::phoneSnapshotCaptureFiles(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneSnapshotCaptureFiles(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()) { return {}; }
    return overte::e2e::phoneSnapshotCaptureFileObservation(command,_featureObservationInstance,_phoneSnapshotCaptureFilesSequence);
}

QVariantMap TestScriptingInterface::phoneSnapshotSettings(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneSnapshotSettings(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !DependencyManager::isSet<Snapshot>()
            || !DependencyManager::isSet<OffscreenUi>()) { return {}; }
    // Closure is measured from the original native review and producer history;
    // the host command has no closed/desired-state field.
    const auto review=overte::e2e::phoneSnapshotReviewObservation(DependencyManager::get<OffscreenUi>()->getRootItem());
    if (review.isEmpty()) { return {}; }
    const auto snapshot=DependencyManager::get<Snapshot>();QVariantMap result;
    const auto read=[&] {
        const auto source=snapshot->featureSnapshotObservation();
        if (source.isEmpty() || !source.value("scriptHistory").toMap().value("complete").toBool()) { return; }
        QMap<QString,QString> phases;
        for (const auto& raw:source.value("scriptHistory").toMap().value("events").toList()) {
            const auto event=raw.toMap();phases.insert(event.value("id").toString(),event.value("kind").toString());
        }
        bool closed=!review.value("present").toBool() && source.value("captures").toList().isEmpty()
            && source.value("uploads").toStringList().isEmpty();
        for (const auto& phase:phases) { if (phase=="pending" || phase=="processing") { closed=false; } }
        result=snapshot->featureSnapshotSettings(command,closed);
    };
    if (QThread::currentThread()==snapshot->thread()) { read(); }
    else if (!QMetaObject::invokeMethod(snapshot.data(),read,Qt::BlockingQueuedConnection)) { return {}; }
    return result;
}

QVariantMap TestScriptingInterface::phoneSnapshotReadback(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneSnapshotReadback(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);
    QStringList keys{"schemaVersion","commandId","action","runId","operation","exportRequest","resourceId"};keys.sort();
    const QRegularExpression nonce("\\A[0-9a-f]{32}\\z");
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=keys
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("phone-snapshot-readback")
            || !json.value("commandId").isString() || !nonce.match(json.value("commandId").toString()).hasMatch()
            || !json.value("runId").isString() || !nonce.match(json.value("runId").toString()).hasMatch()
            || !json.value("operation").isString() || !json.value("exportRequest").isString() || !json.value("resourceId").isString()) { return {}; }
    const auto operation=json.value("operation").toString(),request=json.value("exportRequest").toString(),id=json.value("resourceId").toString();
    if ((operation=="observe" || operation=="retire-copies") ? (!request.isEmpty() || !id.isEmpty())
            : (operation=="read" || operation=="remove-destination" || operation=="revoke-share") ? (!nonce.match(request).hasMatch() || !nonce.match(id).hasMatch())
            : (operation=="inspect-destinations" || operation=="inspect-shares") ? (!request.isEmpty() || !nonce.match(id).hasMatch())
            : (operation=="cancel" || operation=="remove-copy") ? (!request.isEmpty() || !nonce.match(id).hasMatch()) : true) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const QJsonObject input{{"snapshotReadbackCommandVersion",1},{"action",operation},{"request",request},{"id",id}};
    const auto raw=NativeSnapshotAdapter::featureReadbackCommand(QString::fromUtf8(QJsonDocument(input).toJson(QJsonDocument::Compact)));
    const auto actual=QJsonDocument::fromJson(raw.toUtf8());
    if (!actual.isObject() || raw.toUtf8().size()>200000) { return {}; }
    return {{"schemaVersion",1},{"requestId",command.value("commandId")},{"runId",command.value("runId")},
        {"instance",_featureObservationInstance},{"sequence",static_cast<qulonglong>(++_phoneSnapshotReadbackSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",actual.object().toVariantMap()}};
}

QVariantMap TestScriptingInterface::phoneSnapshotCancel(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneSnapshotCancel(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);
    QStringList keys{"schemaVersion","commandId","action","runId","jobId","operation","request"};
    const bool closedRead=command.contains("closedReadWorkRequestId");
    if (closedRead) { keys.append("closedReadWorkRequestId"); }keys.sort();
    const QRegularExpression nonce("\\A[0-9a-f]{32}\\z");
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=keys
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("phone-snapshot-cancel")
            || !json.value("commandId").isString() || !nonce.match(json.value("commandId").toString()).hasMatch()
            || !json.value("runId").isString() || !nonce.match(json.value("runId").toString()).hasMatch()
            || !json.value("jobId").isString() || !nonce.match(json.value("jobId").toString()).hasMatch()
            || !json.value("operation").isString() || !json.value("request").isObject()
            || !DependencyManager::isSet<Snapshot>() || !DependencyManager::isSet<OffscreenUi>() || !_phoneSnapshotUi) { return {}; }
    const auto operation=json.value("operation").toString(),job=json.value("jobId").toString();
    if (!QStringList{"start","observe","retire"}.contains(operation)
            || (operation!="start" && !json.value("request").toObject().isEmpty())) { return {}; }
    QVariantMap closedWork;
    if (closedRead) {
        const auto workId=json.value("closedReadWorkRequestId");
        if (operation=="start" || !workId.isString() || !nonce.match(workId.toString()).hasMatch()
                || _featureScriptWorkCommand.value("commandId")!=command.value("closedReadWorkRequestId")
                || _featureScriptWorkResult.value("requestId")!=command.value("closedReadWorkRequestId")
                || _featureScriptWorkResult.value("instance")!=_featureObservationInstance
                || _featureScriptWorkResult.value("processId").toLongLong()!=QCoreApplication::applicationPid()
                || _featureScriptWorkResult.value("source").toMap().value("manager").toMap().value("instance")
                    !=_featureScriptWorkCommand.value("managerInstance")) { return {}; }
        // The caller supplies only the nonce of a completed ordinary readonly
        // owner-thread barrier. Its original times and body stay unchanged.
        closedWork=_featureScriptWorkResult;
    }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    auto owner=_phoneSnapshotCancelJobs.value(job);
    if (!owner) {
        if (operation!="start" || _phoneSnapshotCancelJobs.size()>=8) { return {}; }
        owner=std::make_shared<overte::e2e::PhoneSnapshotFastCancel>();
    }
    const auto ui=DependencyManager::get<OffscreenUi>();
    QPointer<Snapshot> snapshot=DependencyManager::get<Snapshot>().data();
    const auto read=[snapshot]() -> QVariantMap {
        if (!snapshot || QThread::currentThread()!=snapshot->thread()) { return {}; }
        return snapshot->featureSnapshotObservation();
    };
    QPointer<QQuickWindow> window=ui->getWindow();
    const auto click=[window](QQuickItem* item) {
        return window && item && overte::e2e::NormalControlUi::pointerEvent(item,window,
            item->mapToScene(QPointF(item->width()/2,item->height()/2)));
    };
    const auto source=owner->request(json.value("runId").toString(),job,operation,
        json.value("request").toObject(),ui->getRootItem(),window,_phoneSnapshotUi,read,click,closedWork);
    if (source.isEmpty() || QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size()>200000) { return {}; }
    _phoneSnapshotCancelJobs.insert(job,owner);
    QVariantList jobs;
    for (const auto& original:_phoneSnapshotCancelJobs) { jobs.append(original->summary()); }
    return {{"schemaVersion",1},{"requestId",command.value("commandId")},{"runId",command.value("runId")},{"jobs",jobs},
        {"instance",_featureObservationInstance},{"sequence",static_cast<qulonglong>(++_phoneSnapshotCancelSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
}

QVariantMap TestScriptingInterface::phoneCreateFiles(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneCreateFiles(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    if (!_phoneCreateFiles) { _phoneCreateFiles=std::make_shared<overte::e2e::PrivateCreateFiles>(); }
    const auto source=_phoneCreateFiles->request(_testResultsLocation,command);
    if (source.isEmpty()) { return {}; }
    return {{"schemaVersion",1},{"requestId",command.value("commandId")},{"runId",command.value("runId")},
        {"operation",command.value("operation")},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_phoneCreateFilesSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
}

QVariantMap TestScriptingInterface::phoneAssetsFiles(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneAssetsFiles(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || _phoneAssetsFilesSequence>=1000000000) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    if (!_phoneAssetsFiles) { _phoneAssetsFiles=std::make_shared<overte::e2e::PrivateAssetsFiles>(); }
    const auto source=_phoneAssetsFiles->request(_testResultsLocation,command);
    if (source.isEmpty()) { return {}; }
    return {{"schemaVersion",1},{"requestId",command.value("commandId")},{"runId",command.value("runId")},
        {"operation",command.value("operation")},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_phoneAssetsFilesSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
}

QVariantMap TestScriptingInterface::phoneAssetsUploads(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;if (!QMetaObject::invokeMethod(this,[&] { result=phoneAssetsUploads(command); },Qt::BlockingQueuedConnection)) { return {}; }return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);const auto operation=command.value("operation").toString();
    const bool release=operation=="release";QStringList fields{"schemaVersion","commandId","action","operation","runId"};
    if (release) { fields.append("instance");fields.append("bundleIds"); }fields.sort();
    const QRegularExpression nonce("\\A[0-9a-f]{32}\\z");
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !DependencyManager::isSet<AssetMappingsScriptingInterface>()
            || _phoneAssetsUploadsSequence>=1000000000 || command.keys()!=fields || json.value("schemaVersion")!=QJsonValue(1)
            || !json.value("commandId").isString() || !nonce.match(command.value("commandId").toString()).hasMatch()
            || !json.value("runId").isString() || !nonce.match(command.value("runId").toString()).hasMatch()
            || command.value("commandId").toString()==QString(32,'0') || command.value("runId").toString()==QString(32,'0')
            || command.value("action")!="phone-assets-uploads" || (operation!="observe" && !release)) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();const auto assets=DependencyManager::get<AssetMappingsScriptingInterface>();
    const auto run=command.value("runId").toString();QVariantMap source;
    if (!release) { source=assets->e2eBundleOriginals(run); }
    else {
        if (!json.value("instance").isString() || !nonce.match(command.value("instance").toString()).hasMatch()
                || !json.value("bundleIds").isArray() || json.value("bundleIds").toArray().size()>64) { return {}; }
        QStringList ids;
        for (const auto& value:json.value("bundleIds").toArray()) {
            const auto id=value.toString();const QUuid uuid(id);
            if (!value.isString() || uuid.isNull() || uuid.toString(QUuid::WithoutBraces)!=id || (!ids.isEmpty() && id<=ids.last())) { return {}; }ids.append(id);
        }
        source=assets->e2eReleaseBundleOriginals(run,command.value("instance").toString(),ids);
    }
    if (source.isEmpty()) { return {}; }
    return {{"schemaVersion",1},{"requestId",command.value("commandId")},{"runId",run},{"operation",operation},
        {"instance",_featureObservationInstance},{"sequence",static_cast<qulonglong>(++_phoneAssetsUploadsSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
}

QVariantMap TestScriptingInterface::phoneAssetsRead(const QVariantMap& command,bool abort) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneAssetsRead(command,abort); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const bool download=command.value("action").toString()=="phone-assets-download";
    const bool resolve=command.value("action").toString()=="phone-assets-resolve";
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !overte::e2e::assetsReadCommand(command,download,resolve) || !DependencyManager::isSet<AssetClient>()
            || !DependencyManager::isSet<NodeList>() || _phoneAssetsReadSequence>=1000000000) { return {}; }
    if (!_phoneAssetsRead) { _phoneAssetsRead=std::make_shared<overte::e2e::PhoneAssetsReadJob>(); }
    const auto job=_phoneAssetsRead;
    const auto nodes=DependencyManager::get<NodeList>();
    const auto domain=nodes->getDomainHandler().getUUID(),session=nodes->getSessionUUID();
    const auto server=nodes->soloNodeOfType(NodeType::AssetServer);
    const auto serverId=server ? server->getUUID() : QUuid();
    const QVariantMap context{{"domainId",domain.toString(QUuid::WithoutBraces)},
        {"sessionId",session.toString(QUuid::WithoutBraces)},{"assetServerId",serverId.toString(QUuid::WithoutBraces)}};
    const bool connected=nodes->getDomainHandler().isConnected() && !domain.isNull() && !session.isNull() && !serverId.isNull();
    if (job->same(command)) {
        if (!connected || job->context()!=context) { job->reject(); }
        if (abort) { job->abort(); }return job->poll(command);
    }
    if (abort || !job->canBegin(command) || !connected) { return {}; }
    const auto assets=DependencyManager::get<AssetClient>();
    const auto finish=[this,job,domain,session,serverId](QObject* request,QVariantMap source,qint64 captured) {
        // AssetClient requests belong to its network thread. Only immutable
        // copied originals cross into this GUI-side source owner.
        QMetaObject::invokeMethod(this,[this,job,domain,session,serverId,request,source,captured]() mutable {
            const auto actual=DependencyManager::get<NodeList>();
            const auto currentServer=actual ? actual->soloNodeOfType(NodeType::AssetServer) : nullptr;
            if (!actual || !currentServer || currentServer->getUUID()!=serverId || !actual->getDomainHandler().isConnected() || actual->getDomainHandler().getUUID()!=domain
                    || actual->getSessionUUID()!=session) { source.clear(); }
            else if (source.contains("canWrite")) { source["canWrite"]=actual->getThisNodeCanWriteAssets(); }
            job->finish(request,source,captured);
        },Qt::QueuedConnection);
    };
    if (!download && !resolve) {
        auto request=assets->createGetAllMappingsRequest();
        auto cancellation=new QObject(this);
        QObject::connect(cancellation,&QObject::destroyed,request,&QObject::deleteLater,Qt::QueuedConnection);
        if (!job->begin(command,request,cancellation,_featureObservationInstance,++_phoneAssetsReadSequence,context)) { delete cancellation;return {}; }
        const bool canWrite=nodes->getThisNodeCanWriteAssets();
        QObject::connect(request,&GetAllMappingsRequest::finished,request,[finish,domain,session,serverId,canWrite](GetAllMappingsRequest* actual) {
            // This callback runs on the request's actual owner thread.
            const auto source=actual->getError()==MappingRequest::NoError
                ? overte::e2e::assetsMappingsOriginal(actual->getMappings(),canWrite,domain.toString(QUuid::WithoutBraces),session.toString(QUuid::WithoutBraces),serverId.toString(QUuid::WithoutBraces))
                : QVariantMap{{"phoneAssetsObservationVersion",2},{"complete",false},{"errorCode",int(actual->getError())}};
            finish(actual,source,QDateTime::currentMSecsSinceEpoch());actual->deleteLater();
        },Qt::DirectConnection);
        QObject::connect(request,&QObject::destroyed,this,[job,request] { job->destroyed(request); },Qt::QueuedConnection);
        request->start();
    } else if (resolve) {
        auto request=assets->createGetMappingRequest(command.value("path").toString());
        auto cancellation=new QObject(this);
        QObject::connect(cancellation,&QObject::destroyed,request,&QObject::deleteLater,Qt::QueuedConnection);
        if (!job->begin(command,request,cancellation,_featureObservationInstance,++_phoneAssetsReadSequence,context)) { delete cancellation;return {}; }
        QObject::connect(request,&GetMappingRequest::finished,request,[finish,domain,session,serverId](GetMappingRequest* actual) {
            const auto source=actual->getError()==MappingRequest::NoError
                ? overte::e2e::assetsResolveOriginal(actual->e2eRequestedPath(),actual->getHash(),actual->wasRedirected(),actual->getRedirectedPath(),
                    domain.toString(QUuid::WithoutBraces),session.toString(QUuid::WithoutBraces),serverId.toString(QUuid::WithoutBraces))
                : QVariantMap{{"phoneAssetsResolveVersion",1},{"complete",false},{"errorCode",int(actual->getError())}};
            finish(actual,source,QDateTime::currentMSecsSinceEpoch());actual->deleteLater();
        },Qt::DirectConnection);
        QObject::connect(request,&QObject::destroyed,this,[job,request] { job->destroyed(request); },Qt::QueuedConnection);
        request->start();
    } else {
        auto request=assets->createRequest(command.value("hash").toString());
        auto cancellation=new QObject(this);
        QObject::connect(cancellation,&QObject::destroyed,request,&QObject::deleteLater,Qt::QueuedConnection);
        if (!job->begin(command,request,cancellation,_featureObservationInstance,++_phoneAssetsReadSequence,context)) { delete cancellation;return {}; }
        QObject::connect(request,&AssetRequest::finished,request,[finish,domain,session,serverId](AssetRequest* actual) {
            const auto source=actual->getError()==AssetRequest::NoError && actual->getState()==AssetRequest::Finished
                ? overte::e2e::assetsDownloadOriginal(actual->getHash(),actual->getData(),actual->loadedFromCache(),domain.toString(QUuid::WithoutBraces),session.toString(QUuid::WithoutBraces),serverId.toString(QUuid::WithoutBraces))
                : QVariantMap{{"phoneAssetsDownloadVersion",2},{"complete",false},{"errorCode",int(actual->getError())}};
            finish(actual,source,QDateTime::currentMSecsSinceEpoch());actual->deleteLater();
        },Qt::DirectConnection);
        QObject::connect(request,&QObject::destroyed,this,[job,request] { job->destroyed(request); },Qt::QueuedConnection);
        request->start();
    }
    return job->poll(command);
}

QVariantMap TestScriptingInterface::phoneCreateObservation(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneCreateObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const auto avatar=DependencyManager::get<AvatarManager>()->getMyAvatar();
    if (!avatar) { return {}; }
    const auto source=overte::e2e::phoneCreateObservationSource(command,avatar->getWorldFeetPosition());
    if (source.isEmpty() || QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size()>200000) { return {}; }
    return {{"schemaVersion",1},{"requestId",command.value("commandId")},{"runId",command.value("runId")},
        {"instance",_featureObservationInstance},{"sequence",static_cast<qulonglong>(++_phoneCreateObservationSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
}

QVariantMap TestScriptingInterface::phoneReadFeatureCommand() {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this,[&] { result=phoneReadFeatureCommand(); },Qt::BlockingQueuedConnection);
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    return overte::e2e::privateAndroidFeatureCommand(_testResultsLocation).toVariantMap();
}
QVariantMap TestScriptingInterface::phoneNavigationView(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=phoneNavigationView(command); },Qt::BlockingQueuedConnection)) { return {}; }return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::e2e::previewDirectory(_testResultsLocation)
            || !DependencyManager::isSet<OffscreenUi>() || !DependencyManager::isSet<TabletScriptingInterface>()
            || !DependencyManager::isSet<LocationBookmarks>() || !DependencyManager::isSet<AccountManager>()) { return {}; }
    const auto ui=DependencyManager::get<OffscreenUi>();const auto tablets=DependencyManager::get<TabletScriptingInterface>();
    const auto tablet=tablets->getTablet("com.highfidelity.interface.tablet.system");
    const auto state=tablets->featurePhoneTabletState();
    if (!ui || !ui->getRootItem() || !tablet || state.isEmpty()) { return {}; }
    const auto stored=DependencyManager::get<LocationBookmarks>()->featureBookmarkStorage();
    const auto endpoint=DependencyManager::get<AccountManager>()->getMetaverseServerURL().toString(QUrl::FullyEncoded);
    if (!_phoneNavigationView) { _phoneNavigationView=std::make_shared<overte::e2e::NavigationViewObservation>(); }
    return _phoneNavigationView->request(command,{ui->getRootItem(),tablet->getTabletRoot()},state.value("shown").toBool(),stored,
        endpoint,protocolVersionsSignatureBase64(),tablets->getTouchUiRuntimeMetrics());
}
QVariantMap TestScriptingInterface::phoneAvatarPeopleObservation(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        QVariantMap result;if (!QMetaObject::invokeMethod(this,[&] { result=phoneAvatarPeopleObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }return result;
    }
    const auto json=QJsonObject::fromVariantMap(command);const auto request=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || command.keys()!=QStringList{"action","commandId","runId","schemaVersion"}
            || json.value("schemaVersion")!=QJsonValue(1) || command.value("action")!="phone-avatar-people-observe"
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(request).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            || !DependencyManager::isSet<OffscreenUi>() || !DependencyManager::isSet<TabletScriptingInterface>()
            || !DependencyManager::isSet<AvatarBookmarks>() || !DependencyManager::isSet<AccountManager>()) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const auto avatars=DependencyManager::get<AvatarManager>();const auto local=avatars->getMyAvatar();
    const auto nodes=DependencyManager::get<NodeList>();if (!local || !nodes) { return {}; }
    const auto ui=DependencyManager::get<OffscreenUi>();const auto tablets=DependencyManager::get<TabletScriptingInterface>();
    const auto tablet=tablets->getTablet("com.highfidelity.interface.tablet.system");if (!tablet) { return {}; }
    const auto tabletState=tablets->featurePhoneTabletState();if (tabletState.isEmpty()) { return {}; }
    if (!_phoneAvatarPeopleView) { _phoneAvatarPeopleView=std::make_shared<overte::e2e::AvatarPeopleViewObservation>(); }
    const auto view=_phoneAvatarPeopleView->read({ui->getRootItem(),tablet->getTabletRoot()},tabletState.value("shown").toBool());
    const auto bookmarks=DependencyManager::get<AvatarBookmarks>()->featureBookmarkStorage();
    const auto account=DependencyManager::get<AccountManager>();QVariantMap auth;QString accountOrigin;
    const auto readAuth=[&] { auth=account->featureAccountObservation();accountOrigin=account->getMetaverseServerURL().toString(QUrl::FullyEncoded); };
    if (account->thread()==QThread::currentThread()) { readAuth(); }
    else if (!QMetaObject::invokeMethod(account.data(),readAuth,Qt::BlockingQueuedConnection)) { return {}; }
    if (view.isEmpty() || bookmarks.isEmpty() || auth.isEmpty()) { return {}; }
    auto modelSource=[](const std::shared_ptr<Avatar>& avatar) -> QVariantMap {
        if (!avatar) { return {}; }const auto model=avatar->getSkeletonModel();if (!model) { return {}; }
        const auto geometry=model->getGeometry();QVariant loaded;
        if (geometry && geometry->isHFMModelLoaded()) {
            loaded=QVariantMap{{"instance",geometry->e2eGeometryInstance()},{"url",geometry->getHFMModel().originalURL},
                {"texturesLoaded",geometry->areTexturesLoaded()},{"textures",geometry->getTextures()}};
        }
        return {{"sessionId",avatar->getSessionUUID().toString(QUuid::WithoutBraces)},{"replicated",avatar->getIsReplicated()},
            {"requestedUrl",avatar->getSkeletonModelURL().toString()},{"advertisedLoads",avatar->e2eAvatarLoads()},
            {"modelInstance",model->e2eModelInstance()},{"modelLoads",model->e2eModelLoads()},{"rigId",model->getRig().e2eRigId()},
            {"loaded",model->isLoaded()},{"visible",model->isVisible()},{"addedToScene",model->isAddedToScene()},
            {"targetScale",avatar->getTargetScale()},{"scale",avatar->getModelScale()},{"hipsJoint",avatar->getJointIndex("Hips")},
            {"feetPosition",QVariantList{avatar->getWorldFeetPosition().x,avatar->getWorldFeetPosition().y,avatar->getWorldFeetPosition().z}},
            {"orientation",QVariantList{avatar->getWorldOrientation().x,avatar->getWorldOrientation().y,avatar->getWorldOrientation().z,avatar->getWorldOrientation().w}},
            {"shouldRender",avatar->shouldRender()},{"geometry",loaded}};
    };
    const auto original=modelSource(local);if (original.isEmpty()) { return {}; }QVariantList peers;
    const auto hash=avatars->getHashCopy();if (hash.size()>128) { return {}; }
    for (auto it=hash.begin();it!=hash.end();++it) {
        if (!it.value() || it.value()->getSessionUUID()==local->getSessionUUID()) { continue; }
        const auto remote=std::dynamic_pointer_cast<Avatar>(it.value());if (!remote) { return {}; }
        const auto source=modelSource(remote);if (source.isEmpty()) { return {}; }peers.append(source);
    }
    const bool canRez=nodes->getThisNodeCanRezAvatarEntities();
    const auto attachments=local->getAvatarEntitiesVariant();if (attachments.size()>128) { return {}; }
    const auto treeRenderer=DependencyManager::get<EntityTreeRenderer>();const auto entities=DependencyManager::get<EntityScriptingInterface>();
    if (!treeRenderer || !treeRenderer->getTree() || !entities) { return {}; }
    QSet<QUuid> ownedIds;const auto localEntities=local->getAvatarEntityData();
    if (localEntities.size()>128) { return {}; }for (auto it=localEntities.begin();it!=localEntities.end();++it) { ownedIds.insert(it.key()); }
    for (auto it=hash.begin();it!=hash.end();++it) { if (!it.value()) { return {}; }const auto data=it.value()->getAvatarEntityData();if (data.size()>128) { return {}; }
        for (auto entry=data.begin();entry!=data.end();++entry) { ownedIds.insert(entry.key()); }
    }
    if (ownedIds.size()>256) { return {}; }
    const auto advertisedIds=ownedIds;auto& origins=overte::e2e::FeatureAvatarEntityOrigins::instance();
    bool inventoryComplete=false;QHash<EntityItemID,EntityItemPointer> treeObjects;
    treeRenderer->getTree()->withReadLock([&] { treeObjects=treeRenderer->getTree()->e2eEntityInventory(inventoryComplete); });
    if (!inventoryComplete) { return {}; }
    const QRegularExpression ownedModel("\\A/feature-fixture/v1/runs/"+run+"/tickets/[0-9a-f]{32}/gltf-bundle/main\\.gltf\\z");
    for (auto it=treeObjects.begin();it!=treeObjects.end();++it) { if (!it.value()) { return {}; }const auto p=it.value()->getProperties();
        if (p.getType()==EntityTypes::Model && ownedModel.match(QUrl(p.getModelURL()).path()).hasMatch()) { ownedIds.insert(it.key()); }
    }
    ownedIds.unite(origins.knownIds(run));if (ownedIds.size()>512) { return {}; }
    QVariantList entityRows,absentIds,advertised,queried;
    for (const auto& id:advertisedIds) { advertised.append(id.toString(QUuid::WithoutBraces)); }
    for (const auto& id:ownedIds) { queried.append(id.toString(QUuid::WithoutBraces)); }
    auto vec=[](const glm::vec3& value) { return QVariantList{value.x,value.y,value.z}; };
    auto quat=[](const glm::quat& value) { return QVariantList{value.x,value.y,value.z,value.w}; };
    for (const auto& id:ownedIds) {
        if (id.isNull()) { return {}; }const auto actual=treeObjects.value(EntityItemID(id));
        if (!actual) { absentIds.append(id.toString(QUuid::WithoutBraces));continue; }
        const auto p=actual->getProperties();const bool originalObject=origins.observe(run,id,actual);
        QVariant nativeModel;
        if (p.getType()==EntityTypes::Model) {
            const auto entity=std::dynamic_pointer_cast<RenderableModelEntityItem>(actual);
            if (entity) { const auto model=entity->e2eAvatarEntityModel();if (model) {
                QVariant geometrySource;const auto geometry=model->getGeometry();
                if (geometry && geometry->isHFMModelLoaded()) { geometrySource=QVariantMap{{"instance",geometry->e2eGeometryInstance()},
                    {"url",geometry->getHFMModel().originalURL},{"texturesLoaded",geometry->areTexturesLoaded()},{"textures",geometry->getTextures()}}; }
                nativeModel=QVariantMap{{"modelInstance",model->e2eModelInstance()},{"modelLoads",model->e2eModelLoads()},
                    {"loaded",model->isLoaded()},{"visible",model->isVisible()},{"addedToScene",model->isAddedToScene()},{"geometry",geometrySource}};
            } }
        }
        entityRows.append(QVariantMap{{"entityId",id.toString(QUuid::WithoutBraces)},{"type",EntityTypes::getEntityTypeName(p.getType())},
            {"host",p.getEntityHostType()==entity::HostType::AVATAR ? "avatar" : p.getEntityHostType()==entity::HostType::LOCAL ? "local" : "domain"},
            {"parentId",p.getParentID().toString(QUuid::WithoutBraces)},{"parentJointIndex",p.getParentJointIndex()},{"modelUrl",p.getModelURL()},
            {"visible",p.getVisible()},{"originalObject",originalObject},{"localPosition",vec(p.getLocalPosition())},{"localRotation",quat(p.getLocalRotation())},
            {"localDimensions",vec(p.getLocalDimensions())},{"model",nativeModel}});
    }
    const auto resourceReplies=overte::e2e::FeatureResourceReplies::instance().snapshot(run);
    const auto peopleReplies=overte::e2e::FeaturePeopleReplies::instance().snapshot();
    const auto avatarOrigins=origins.snapshot(run);const auto retained=origins.retained(run);QVariantList remembered;
    for (const auto& id:origins.knownIds(run)) { remembered.append(id.toString(QUuid::WithoutBraces)); }
    const auto captured=QDateTime::currentMSecsSinceEpoch();if (captured<requested || captured-requested>1500) { return {}; }
    return {{"avatarPeopleObservationVersion",1},{"commandId",request},{"runId",run},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_phoneAvatarPeopleSequence)},{"processId",QCoreApplication::applicationPid()},
        {"requestedEpochMs",requested},{"capturedEpochMs",captured},
        {"source",QVariantMap{{"view",view},{"bookmarks",bookmarks},{"auth",auth},{"accountOrigin",accountOrigin},{"avatar",original},{"peers",peers},
            {"canRezAvatarEntities",canRez},{"attachments",attachments},{"preferredAvatarUrl",local->getFullAvatarURLFromPreferences().toString()},{"preferredAvatarName",local->getFullAvatarModelName()},
            {"domainId",nodes->getDomainHandler().getUUID().toString(QUuid::WithoutBraces)},{"connected",nodes->getDomainHandler().isConnected()},
            {"resourceReplies",resourceReplies},{"peopleReplies",peopleReplies},{"avatarEntityOrigins",avatarOrigins},
            {"avatarEntities",QVariantMap{{"complete",true},{"entities",entityRows},{"absentIds",absentIds},
                {"advertisedIds",advertised},{"queriedIds",queried},{"rememberedIds",remembered},{"retainedIds",retained}}}}}};
}
QVariantMap TestScriptingInterface::phoneScriptFileUi(const QVariantMap& command) { return phoneControlUi(command, 0); }
QVariantMap TestScriptingInterface::phoneAudioUi(const QVariantMap& command) { return phoneControlUi(command, 1); }
QVariantMap TestScriptingInterface::phoneGraphicsUi(const QVariantMap& command) { return phoneControlUi(command, 2); }
QVariantMap TestScriptingInterface::phoneEmoteUi(const QVariantMap& command) { return phoneControlUi(command, 6); }
QVariantMap TestScriptingInterface::phoneAssetsUi(const QVariantMap& command) { return phoneControlUi(command, 9); }
QVariantMap TestScriptingInterface::phoneCreateUi(const QVariantMap& command) { return phoneControlUi(command, 4); }
QVariantMap TestScriptingInterface::phoneNavigationUi(const QVariantMap& command) { return phoneControlUi(command, 7); }
QVariantMap TestScriptingInterface::phoneAvatarPeopleUi(const QVariantMap& command) { return phoneControlUi(command, 8); }
QVariantMap TestScriptingInterface::phoneSnapshotUi(const QVariantMap& command) { return phoneControlUi(command, 10); }
QVariantMap TestScriptingInterface::phoneChatUi(const QVariantMap& command) { return phoneControlUi(command, 5); }
QVariantMap TestScriptingInterface::phoneLoginUi(const QVariantMap& command) { return phoneControlUi(command, 3); }
QVariantMap TestScriptingInterface::phoneControlUi(const QVariantMap& command, int surfaceKind) {
    if (QThread::currentThread() != thread()) {
        QVariantMap result;
        QMetaObject::invokeMethod(this, [&] { result = phoneControlUi(command, surfaceKind); }, Qt::BlockingQueuedConnection);
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !DependencyManager::isSet<OffscreenUi>()) { return {}; }
    const auto ui = DependencyManager::get<OffscreenUi>();
    const auto root = ui->getRootItem();
    const auto window = ui->getWindow();
    const bool audioSurface = surfaceKind == 1;
    if (surfaceKind < 0 || surfaceKind > 10) { return {}; }
    overte::e2e::GraphicsUiContext graphicsContext;
    overte::e2e::AudioUiContext audioContext;
    overte::e2e::LoginUiContext loginContext;
    if (audioSurface) {
        if (!DependencyManager::isSet<AudioClient>()) { return {}; }
        const auto audio = DependencyManager::get<AudioClient>();
        QVariantMap voice; bool muted {false}, echo {false};
        const auto read = [&] { voice = audio->featureRecordedVoiceObservation(); muted = audio->isMuted(); echo = audio->getLocalEcho(); };
        if (QThread::currentThread() == audio->thread()) { read(); }
        else if (!QMetaObject::invokeMethod(audio.data(), read, Qt::BlockingQueuedConnection)) { return {}; }
        audioContext = overte::e2e::AudioUiContext::fromNative(voice, muted, echo, qApp->isHMDMode());
        if (!audioContext.valid) { return {}; }
        if (!_phoneAudioUi) { _phoneAudioUi = std::make_shared<overte::e2e::AudioUi>(); }
    } else if (surfaceKind == 2) {
        auto render = RenderScriptingInterface::getInstance();
        graphicsContext = overte::e2e::GraphicsUiContext::fromNative(render->getViewportResolutionScale(),
            render->getHazeEnabled(), render->getMirrorsEnabled());
        if (!graphicsContext.valid) { return {}; }
        if (!_phoneGraphicsUi) { _phoneGraphicsUi = std::make_shared<overte::e2e::GraphicsUi>(); }
    } else if (surfaceKind == 3) {
        if (!DependencyManager::isSet<AccountManager>()) { return {}; }
        const auto account=DependencyManager::get<AccountManager>();
        QVariantMap original;
        const auto read=[&] { original=account->featureAccountObservation(); };
        if (QThread::currentThread()==account->thread()) { read(); }
        else if (!QMetaObject::invokeMethod(account.data(),read,Qt::BlockingQueuedConnection)) { return {}; }
        loginContext=overte::e2e::LoginUiContext::fromNative(original);
        if (!loginContext.valid) { return {}; }
        if (!_phoneLoginUi) { _phoneLoginUi=std::make_shared<overte::e2e::LoginUi>(); }
    } else if (surfaceKind == 4) {
        if (!_phoneCreateUi) { _phoneCreateUi=std::make_shared<overte::e2e::CreateUi>(); }
    } else if (surfaceKind == 5) {
        if (!_phoneChatUi) { _phoneChatUi=std::make_shared<overte::e2e::ChatUi>(); }
    } else if (surfaceKind == 6) {
        if (!_phoneEmoteUi) { _phoneEmoteUi=std::make_shared<overte::e2e::EmoteUi>(); }
    } else if (surfaceKind == 7) {
        if (!_phoneNavigationUi) { _phoneNavigationUi=std::make_shared<overte::e2e::NavigationUi>(); }
    } else if (surfaceKind == 8) {
        if (!_phoneAvatarPeopleUi) { _phoneAvatarPeopleUi=std::make_shared<overte::e2e::AvatarPeopleUi>(); }
    } else if (surfaceKind == 10) {
        if (!_phoneSnapshotUi) { _phoneSnapshotUi=std::make_shared<overte::e2e::SnapshotUi>(); }
    } else if (surfaceKind == 9) {
        if (!_phoneAssetsUi) { _phoneAssetsUi=std::make_shared<overte::e2e::AssetsUi>(); }
    } else if (!_phoneScriptFileUi) { _phoneScriptFileUi = std::make_shared<overte::e2e::ScriptFileUi>(); }
    auto controls = audioSurface ? static_cast<overte::e2e::NormalControlUi*>(_phoneAudioUi.get())
        : surfaceKind == 2 ? static_cast<overte::e2e::NormalControlUi*>(_phoneGraphicsUi.get())
        : surfaceKind == 3 ? static_cast<overte::e2e::NormalControlUi*>(_phoneLoginUi.get())
        : surfaceKind == 4 ? static_cast<overte::e2e::NormalControlUi*>(_phoneCreateUi.get())
        : surfaceKind == 5 ? static_cast<overte::e2e::NormalControlUi*>(_phoneChatUi.get())
        : surfaceKind == 6 ? static_cast<overte::e2e::NormalControlUi*>(_phoneEmoteUi.get())
        : surfaceKind == 7 ? static_cast<overte::e2e::NormalControlUi*>(_phoneNavigationUi.get())
        : surfaceKind == 8 ? static_cast<overte::e2e::NormalControlUi*>(_phoneAvatarPeopleUi.get())
        : surfaceKind == 10 ? static_cast<overte::e2e::NormalControlUi*>(_phoneSnapshotUi.get())
        : surfaceKind == 9 ? static_cast<overte::e2e::NormalControlUi*>(_phoneAssetsUi.get())
        : static_cast<overte::e2e::NormalControlUi*>(_phoneScriptFileUi.get());
    const auto request = QJsonObject::fromVariantMap(command);
    const auto id = request.value("commandId").toString();
    if (request.value("schemaVersion") != QJsonValue(1)
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()) { return {}; }
    const auto action = request.value("action").toString();
    const auto keys = request.keys();
    if (action == "observe") {
        if (QSet<QString>(keys.begin(), keys.end()) != QSet<QString>{"schemaVersion", "commandId", "action"}) { return {}; }
        auto observed = controls->observe(root, window, audioContext, graphicsContext, loginContext);
        if (observed.isEmpty()) { return {}; }
        if (surfaceKind==0) {
            auto inventory=observed.value("scriptInventory").toObject();
            if (inventory.isEmpty() || !DependencyManager::isSet<TabletScriptingInterface>()) { return {}; }
            const auto tablet=DependencyManager::get<TabletScriptingInterface>()->featurePhoneTabletState();
            if (tablet.isEmpty()) { return {}; }
            inventory["tabletPresent"]=tablet.value("present").toBool();
            inventory["tabletShown"]=tablet.value("shown").toBool();
            observed["scriptInventory"]=inventory;
        }
        if (surfaceKind==3) { observed["privateCommandReaderVersion"]=1; }
        observed["commandId"] = id;
        observed["action"] = action;
        return observed.toVariantMap();
    }
    // Events enter the actual rendered Qt window. No QML clicked/accepted
    // handler, file helper or script service is invoked as an input shortcut.
    const auto pointClick = [window, surfaceKind](QQuickItem* item, const QPointF& position) {
        return overte::e2e::NormalControlUi::pointerEvent(item,window,position,surfaceKind==0);
    };
    const auto click = [pointClick](QQuickItem* item) {
        return pointClick(item, item->mapToScene(QPointF(item->width()/2, item->height()/2)));
    };
    auto result = controls->apply(root, window, request, click, audioContext, pointClick, graphicsContext, loginContext);
    if (!result.isEmpty()) { result["action"] = action; }
    return result.toVariantMap();
}
#endif
#endif

#if defined(OVERTE_E2E_VOICE_TESTS)
bool TestScriptingInterface::uiTest(const QVariantMap& command) {
    const QString id = command.value("commandId").toString();
    const QString action = command.value("operation").toString();
    const QString outputDirectory = _testResultsLocation;
    if (outputDirectory.isEmpty() || !QCoreApplication::arguments().contains("--testScript")
            || command.size() != 4 || command.value("schemaVersion").toInt() != 1
            || command.value("action").toString() != "text-fixture"
            || !QRegularExpression("^[0-9a-f]{32}$").match(id).hasMatch()
            || (action != "focus" && action != "snapshot" && action != "dismiss")) { return false; }
    // No GUI property reads or writes happen on V8's script thread. Queue one
    // correlated result; the host waits for actual GUI execution and live state.
    return QMetaObject::invokeMethod(QCoreApplication::instance(), [id, action, outputDirectory] {
        static PhoneTextInputFixture fixture;
        const auto finish = [id, action, outputDirectory](bool ok) {
            QJsonObject result { {"schemaVersion", 1}, {"commandId", id}, {"ok", ok},
                {"sampleEpochMs", QDateTime::currentMSecsSinceEpoch()} };
            if (ok) {
                const auto tablet = DependencyManager::get<TabletScriptingInterface>();
                const auto metrics = tablet->getTouchUiRuntimeMetrics();
                if (!metrics.value("valid").toBool()) { result["ok"] = false; }
                else { result["snapshot"] = fixture.snapshot(metrics.value("keyboardVisible").toBool()); }
            }
            QSaveFile output(QDir(outputDirectory).absoluteFilePath("phone-ui-status.json"));
            if (output.open(QIODevice::WriteOnly)) {
                output.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
                output.write(QJsonDocument(result).toJson(QJsonDocument::Compact));
                output.commit();
            }
            // Fixed, app-private diagnostics for this explicit test launch.
            // Preserve actual failures instead of manufacturing a snapshot.
            QJsonObject diagnostic { {"operation", action}, {"nativeOk", ok},
                {"failure", fixture.lastFailure()}, {"panelPresent", fixture.panel() != nullptr},
                {"qtAccessibilityActive", QAccessible::isActive()},
                {"qtKeyboardVisible", qGuiApp->inputMethod()->isVisible()} };
            if (DependencyManager::isSet<TabletScriptingInterface>()) {
                const auto metrics = DependencyManager::get<TabletScriptingInterface>()->getTouchUiRuntimeMetrics();
                diagnostic["runtimeMetricsValid"] = metrics.value("valid").toBool();
                diagnostic["nativeKeyboardVisible"] = metrics.value("keyboardVisible").toBool();
            }
            QJsonArray controls;
            diagnostic["touchDelivery"] = QJsonObject::fromVariantMap(
                QCoreApplication::instance()->property("phoneTouchUiMetricsDiagnostic").toMap());
#if defined(Q_OS_ANDROID)
            const auto javaDiagnostic = QAndroidJniObject::callStaticObjectMethod(
                "org/overte/phone/PhoneInterfaceActivity", "getTouchUiDeliveryDiagnostic", "()Ljava/lang/String;");
            diagnostic["androidTouchDelivery"] = QJsonDocument::fromJson(javaDiagnostic.toString().toUtf8()).object();
#endif
            if (DependencyManager::isSet<OffscreenUi>()) {
                auto root = DependencyManager::get<OffscreenUi>()->getRootItem();
                for (const auto& name : {"tablet.home", "app.settings", "nav.close", "controlled.text"}) {
                    std::function<QQuickItem*(QQuickItem*, int)> findVisual;
                    findVisual = [&](QQuickItem* candidate, int depth) -> QQuickItem* {
                        if (!candidate || depth > 128) { return nullptr; }
                        if (candidate->objectName() == name || candidate->property("semanticId").toString() == name) {
                            return candidate;
                        }
                        for (auto child : candidate->childItems()) {
                            if (auto found = findVisual(child, depth + 1)) { return found; }
                        }
                        return nullptr;
                    };
                    auto item = findVisual(root, 0);
                    QJsonObject control { {"semanticId", name}, {"present", item != nullptr} };
                    if (item) {
                        const auto context = QQmlEngine::contextForObject(item);
                        const QQmlProperty role(item, "Accessible.role", context);
                        control["declaredRoleValid"] = role.isValid();
                        control["declaredRole"] = role.read().toInt();
                        auto accessible = QAccessible::queryAccessibleInterface(item);
                        control["nativeRole"] = accessible ? int(accessible->role()) : -1;
                        control["qmlContextPresent"] = context != nullptr;
                        control["objectClass"] = item->metaObject()->className();
                        control["declaredName"] = QQmlProperty(item, "Accessible.name", context).read().toString();
                        QJsonArray attached;
                        for (auto child : item->children()) {
                            if (QString(child->metaObject()->className()).contains("Accessible")) {
                                attached.append(QJsonObject { {"class", child->metaObject()->className()},
                                    {"role", child->property("role").toInt()} });
                            }
                        }
                        control["attached"] = attached;
                    }
                    controls.append(control);
                }
            }
            diagnostic["controls"] = controls;
            QSaveFile debug(QDir(outputDirectory).absoluteFilePath("phone-ui-diagnostic.json"));
            if (debug.open(QIODevice::WriteOnly)) {
                debug.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
                debug.write(QJsonDocument(diagnostic).toJson(QJsonDocument::Compact));
                debug.commit();
            }
        };
        if (!DependencyManager::isSet<OffscreenUi>() || !DependencyManager::isSet<TabletScriptingInterface>()) {
            finish(false); return;
        }
        const auto ui = DependencyManager::get<OffscreenUi>();
        if (action == "focus") {
            auto panel = ui->getRootItem() ? ui->getRootItem()->findChild<QQuickItem*>("overte-e2e-text-panel") : nullptr;
            if (panel) { finish(fixture.focus(panel)); }
            else {
                // Wait until QML creation and native parent attachment finish.
                ui->load(QUrl("qrc:/qml/hifi/ControlledTextInput.qml"),
                    [finish](QQmlContext*, QQuickItem* created) {
                        QPointer<QQuickItem> guarded(created);
                        QTimer::singleShot(0, QCoreApplication::instance(), [finish, guarded] {
                            finish(fixture.focus(guarded));
                        });
                    });
            }
        } else if (action == "dismiss") { finish(fixture.dismiss()); }
        else { finish(fixture.panel() != nullptr); }
    }, Qt::QueuedConnection);
}

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
    if (filename == "feature-chat-observation.json" || filename == "feature-native-observation.json" || filename == "normal-feature-observation.json"
            || filename == "phone-snapshot-handoff.json" || filename == "phone-snapshot-handoff-result.json"
            || filename == "phone-snapshot-files-observation.json" || filename == "phone-snapshot-settings.json" || filename == "feature-chat-history.json" || filename == "feature-chat-view-observation.json" || filename == "feature-web-dom-observation.json"
            || filename == "feature-phone-web-runtime.json" || filename == "phone-lifecycle-editor.json" || filename == "phone-lifecycle-world-input.json"
            || filename == "feature-pending-commit-owner.json" || filename == "feature-navigation-replies.json"
            || filename == "feature-process-presence.json"
            || filename == "recorded-preview-observation.json" || filename == "feature-script-observation.json"
            || filename == "phone-script-file-ui.json" || filename == "phone-audio-ui.json" || filename == "phone-graphics-ui.json"
            || filename == "feature-script-files.json" || filename == "world-render-observation.json"
            || filename == "feature-graphics-subject.json" || filename == "phone-create-observation.json" || filename == "phone-create-files.json"
            || filename == "phone-create-fixture.json" || filename == "phone-create-fixture-input.json"
            || filename == "feature-scene-load.json"
            || filename == "world-render-receipt-result.json"
            || filename == "world-render-receipts-result.json"
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
    QFile file(filepath);

    file.open(QFile::WriteOnly);
    file.write(jsonData);
    file.close();
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
