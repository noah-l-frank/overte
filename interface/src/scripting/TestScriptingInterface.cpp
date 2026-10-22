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
#include "../../../tests/device/native/ChatViewObservation.h"
#include "../../../tests/device/native/WebDOMObservationBridge.h"
#include "../../../tests/device/native/WebRuntimeBridge.h"
#if defined(ANDROID_APP_PICO_INTERFACE)
#include "../../../tests/device/native/TabletHttpObservationBridge.h"
#include "../../../tests/device/native/LocationBookmarkObservation.h"
#include "../../../tests/device/native/NavigationFailureModals.h"
#include "../../../tests/device/native/NavigationEnvironmentObservation.h"
#include "../../../tests/device/native/NavigationDirectoryObservation.h"
#include "../../../tests/device/native/NavigationPanelsObservation.h"
#include "LocationBookmarks.h"
#include <XMLHttpRequestClass.h>
#include "../../../tests/device/native/PrivateWorldRenderReceipts.h"
#include "../../../tests/device/native/PrivateCreateFiles.h"
#include "../../../tests/device/native/CreateBrowseSettingOwner.h"
#include "../../../tests/device/native/CreateEntityLifetimes.h"
#include "../../../tests/device/native/CreateModelResources.h"
#include <RenderableModelEntityItem.h>
#include <QPointer>
#include <atomic>
#include <algorithm>
#include <PointerManager.h>
#include <ui/Keyboard.h>
#include "HMDScriptingInterface.h"
#include <display-plugins/DisplayPlugin.h>
#endif
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
#include <EntityScriptingInterface.h>
#include <EntityItemProperties.h>
#include <EntityTypes.h>
#include <PickFilter.h>
#include <MirrorMode.h>
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
#if defined(ANDROID_APP_PICO_INTERFACE)
        overte::e2e::ensureNavigationDirectoryProvider(this);
#endif
    }
#endif
}

#if defined(OVERTE_E2E_FEATURE_TESTS)
QVariantMap TestScriptingInterface::featureSceneLoadObservation(const QVariantMap& command) {
#if defined(ANDROID_APP_PICO_INTERFACE)
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
    if (_featureSceneLoadRequests.contains(id) || _featureSceneLoadRequests.size() >= 4096) { return {}; }
    _featureSceneLoadRequests.insert(id);
    auto value=qApp->featureSceneLoadObservation();
    value.insert("commandId",id);value.insert("runId",run);
    value.insert("processId",QCoreApplication::applicationPid());
    value.insert("capturedEpochMs",QDateTime::currentMSecsSinceEpoch());
    return value;
#else
    Q_UNUSED(command);return {};
#endif
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
    // Reusing a nonce never captures a newer world under an older request.
    // Keep ownership for this observer birth; exhaustion is unavailable.
    if (_featureGraphicsSubjectRequests.contains(request) || _featureGraphicsSubjectRequests.size() >= 4096) { return {}; }
    _featureGraphicsSubjectRequests.insert(request);
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
#if defined(ANDROID_APP_PICO_INTERFACE)
    // Keep the complete original raw scan. Exclusions can only be derived from
    // actual framework owner slots, with separate independent restoration checks.
    const auto hmd=DependencyManager::get<HMDScriptingInterface>();
    const auto keyboard=DependencyManager::get<Keyboard>();
    const auto pointerManager=DependencyManager::get<PointerManager>();
    const auto display=qApp->getActiveDisplayPlugin();
    if (!hmd || !keyboard || !pointerManager || !display || keyboard->thread()!=thread()) { return {}; }
    const auto keyboardOwners=keyboard->featureEntityOwnership();
    const auto pointerOwners=pointerManager->featureEntityOwnership();
    if (keyboardOwners.isEmpty() || pointerOwners.isEmpty()) { return {}; }
    auto matrix=[](const glm::mat4& value) {
        QVariantList result;
        for (int column=0;column<4;++column) { for (int row=0;row<4;++row) { result.append(value[column][row]); } }
        return result;
    };
    const auto sensorToWorld=avatar->getSensorToWorldMatrix();
    const auto hmdSensor=avatar->getHMDSensorMatrix();
    const auto worldHead=sensorToWorld*hmdSensor;
    QVariantMap tablet;
    const QMap<QString,QUuid> tabletOwners {
        {"frame",hmd->getCurrentTabletFrameID()},{"screen",hmd->getCurrentTabletScreenID()},
        {"home",hmd->getCurrentHomeButtonID()},{"highlight",hmd->getCurrentHomeButtonHighlightID()},
        {"miniFrame",hmd->getCurrentMiniTabletID()},{"miniScreen",hmd->getCurrentMiniTabletScreenID()}};
    QSet<QUuid> frameworkIds;
    auto collect=[&](const QVariant& raw) {
        if (raw.isNull()) { return; }
        const auto id=QUuid(raw.toString());if (!id.isNull()) { frameworkIds.insert(id); }
    };
    for (auto item=tabletOwners.cbegin();item!=tabletOwners.cend();++item) {
        const auto id=item.value().isNull() ? QVariant() : QVariant(item.value().toString(QUuid::WithoutBraces));
        tablet.insert(item.key(),id);collect(id);
    }
    for (const auto& id:keyboardOwners.value("entityIds").toStringList()) { collect(id); }
    for (const auto& value:pointerOwners.value("pointers").toList()) {
        for (const auto& state:value.toMap().value("states").toList()) {
            for (const auto& id:state.toMap().value("entities").toMap()) { collect(id); }
        }
    }
    if (frameworkIds.size()>2048 || !(frameworkIds & owned).isEmpty()) { return {}; }
    QStringList ordered;for (const auto& id:frameworkIds) { ordered.append(id.toString(QUuid::WithoutBraces)); }ordered.sort();
    QVariantList frameworkEntities;
    for (const auto& identifier:ordered) {
        const auto actual=entities->getEntityProperties(QUuid(identifier));
        const bool exists=actual.getType()!=EntityTypes::Unknown;
        if (exists && (actual.getEntityHostType()!=entity::HostType::LOCAL || actual.getName().size()>256 || actual.getSourceUrl().size()>2048)) { return {}; }
        auto original=exists ? properties(actual) : QVariantMap();
        auto appearance=original;
        for (const auto& key:{"position","rotation","dimensions","visible"}) { appearance.remove(key); }
        auto hash=[](const QVariantMap& value) {
            return QString::fromLatin1(QCryptographicHash::hash(QJsonDocument::fromVariant(value).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex());
        };
        frameworkEntities.append(QVariantMap{{"id",identifier},{"present",exists},
            {"type",exists ? original.value("type") : QVariant()},{"hostType",exists ? QVariant("local") : QVariant()},
            {"parentId",exists && !actual.getParentID().isNull() ? QVariant(actual.getParentID().toString(QUuid::WithoutBraces)) : QVariant()},
            {"propertySha256",exists ? QVariant(hash(original)) : QVariant()},
            {"appearanceSha256",exists ? QVariant(hash(appearance)) : QVariant()}});
    }
    source.insert("subjectVersion",3);
    source.insert("framework",QVariantMap{{"ownershipVersion",1},{"tablet",tablet},{"keyboard",keyboardOwners},
        {"pointers",pointerOwners.value("pointers")},{"entities",frameworkEntities}});
    source.insert("hmd",QVariantMap{{"display",display->getName()},{"active",display->isHmd()},
        {"visible",display->isDisplayVisible()},{"mounted",hmd->isMounted()},
        {"sensorToWorld",matrix(sensorToWorld)},{"sensorPose",matrix(hmdSensor)},
        {"worldPosition",vec(extractTranslation(worldHead))},{"worldRotation",quat(glmExtractRotation(worldHead))}});
#endif
    if (QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size() > 200000) { return {}; }
    return {{"schemaVersion",1},{"requestId",request},{"runId",run},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureGraphicsSubjectSequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
}
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

#if defined(ANDROID_APP_PICO_INTERFACE)
QVariantMap TestScriptingInterface::featureWorldRenderReceipts(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result = featureWorldRenderReceipts(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    const auto json = QJsonObject::fromVariantMap(command);
    QStringList fields {"schemaVersion","commandId","action","requestId","receiptIds","operation"}; fields.sort();
    const auto id = command.value("commandId").toString(), capture = command.value("requestId").toString();
    const auto operation = command.value("operation").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || command.keys() != fields || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble() != 1
            || !json.value("commandId").isString() || !json.value("requestId").isString()
            || json.value("action").toString() != "feature-world-render-receipts"
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id).hasMatch()
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(capture).hasMatch()
            || (operation != "remove" && operation != "inspect") || !json.value("receiptIds").isArray()
            || QJsonDocument(json).toJson(QJsonDocument::Compact).size() > 49152) { return {}; }
    if (_featureWorldReceiptsRequests.contains(id) || _featureWorldReceiptsRequests.size()>=4096) { return {}; }
    _featureWorldReceiptsRequests.insert(id);
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
    // selectors never authorize deletion of a present file. The native GPU
    // ledger retires their undelivered nonces against late storage issuance;
    // the existing GUI probe serializes original file writes.
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

#if defined(ANDROID_APP_PICO_INTERFACE)
void TestScriptingInterface::featurePlacesRecordsChanged() {
    const auto provider=overte::e2e::navigationDirectoryProvider();
    if (provider.changed) { provider.changed(qobject_cast<QQuickItem*>(sender())); }
}

QVariantMap TestScriptingInterface::featureNavigationPanels(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureNavigationPanels(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || !overte::e2e::previewDirectory(_testResultsLocation)) { return {}; }
    return overte::e2e::navigationPanelsObservation().snapshot(command);
}

QVariantMap TestScriptingInterface::featureNavigationDirectory(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureNavigationDirectory(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::e2e::previewDirectory(_testResultsLocation)) { return {}; }
    const auto provider=overte::e2e::navigationDirectoryProvider();
    return provider.snapshot ? provider.snapshot(command) : QVariantMap();
}

QVariantMap TestScriptingInterface::featureNavigationEnvironment(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureNavigationEnvironment(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::e2e::previewDirectory(_testResultsLocation)) { return {}; }
    return overte::e2e::navigationEnvironmentObservation().snapshot(command);
}

QVariantMap TestScriptingInterface::featureNavigationModals(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureNavigationModals(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::e2e::previewDirectory(_testResultsLocation)) { return {}; }
    return overte::e2e::navigationFailureModals().snapshot(command);
}

QVariantMap TestScriptingInterface::featureLocationBookmarks(const QVariantMap& command) {
    if (QThread::currentThread() != thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this, [&] { result = featureLocationBookmarks(command); }, Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::e2e::previewDirectory(_testResultsLocation)
            || !overte::e2e::bookmarkObservationCommand(command) || !DependencyManager::isSet<LocationBookmarks>()
            || _featureLocationBookmarksRequests.size() >= 4096
            || _featureLocationBookmarksRequests.contains(command.value("commandId").toString())) { return {}; }
    _featureLocationBookmarksRequests.insert(command.value("commandId").toString());
    const auto requested = QDateTime::currentMSecsSinceEpoch();
    const auto source = DependencyManager::get<LocationBookmarks>()->featureBookmarkStorage(command.value("runId").toString());
    if (source.isEmpty()) { return {}; }
    return {{"bookmarkObservationVersion", 1}, {"commandId", command.value("commandId")}, {"runId", command.value("runId")},
        {"instance", _featureObservationInstance}, {"sequence", static_cast<qulonglong>(++_featureLocationBookmarksSequence)},
        {"processId", QCoreApplication::applicationPid()}, {"requestedEpochMs", requested},
        {"capturedEpochMs", QDateTime::currentMSecsSinceEpoch()}, {"storage", source}};
}
#endif

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

#if defined(ANDROID_APP_PICO_INTERFACE)
void TestScriptingInterface::featureBindTabletHttpRequest(const QString& lease,QObject* request) {
    // Called on the original request's script thread; never read its state from
    // the GUI thread or dispatch a request, callback, abort or replacement.
    if (!overte::e2e::tabletHttpEnabled()) { return; }
    auto xhr=qobject_cast<XMLHttpRequestClass*>(request);
    if (xhr && xhr->thread()==QThread::currentThread()) { xhr->featureBindTabletHttp(lease); }
}
QVariantMap TestScriptingInterface::featureTabletHttpObservation(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureTabletHttpObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !overte::e2e::tabletHttpEnabled() || !overte::e2e::tabletHttpCommand(command)) { return {}; }
    const auto original=qApp->property(overte::e2e::tabletHttpProperty());
    if (original.userType()!=qMetaTypeId<overte::e2e::TabletHttpProvider>()) { return {}; }
    const auto provider=original.value<overte::e2e::TabletHttpProvider>();
    return provider.snapshot ? provider.snapshot(command) : QVariantMap();
}
#endif

QVariantMap TestScriptingInterface::featureWebRuntimeObservation(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        if (!QMetaObject::invokeMethod(this,[&] { result=featureWebRuntimeObservation(command); },Qt::BlockingQueuedConnection)) { return {}; }
        return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !overte::e2e::webRuntimeCommand(command)) { return {}; }
    const auto original=qApp->property(overte::e2e::webRuntimeProperty());
    if (original.userType()!=qMetaTypeId<overte::e2e::WebRuntimeProvider>()) { return {}; }
    const auto provider=original.value<overte::e2e::WebRuntimeProvider>();
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
    // This explicit source role extends storage only on Pico. The original
    // Script role keeps its exact admission and resource namespace below.
#if defined(ANDROID_APP_PICO_INTERFACE)
    if (command.contains("sourceRole")) { return featureCreateFiles(command); }
#endif
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

#if defined(ANDROID_APP_PICO_INTERFACE)
QVariantMap TestScriptingInterface::featureCreateBrowseSetting(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) {return {};}
        QVariantMap result;QMetaObject::invokeMethod(this,[&]{result=featureCreateBrowseSetting(command);},Qt::BlockingQueuedConnection);return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || !DependencyManager::isSet<OffscreenUi>()) {return {};}
    const auto id=command.value("commandId").toString();
    if (!QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
            || QJsonDocument(QJsonObject::fromVariantMap(command)).toJson(QJsonDocument::Compact).size()>8192) {return {};}
    if (_featureCreateBrowseSettingCommands.contains(id)) {
        return _featureCreateBrowseSettingCommands.value(id)==command ? _featureCreateBrowseSettingResults.value(id) : QVariantMap{};
    }
    if (_featureCreateBrowseSettingCommands.size()>=512 || _featureCreateBrowseSettingSequence>=9007199254740991ULL) {return {};}
    _featureCreateBrowseSettingCommands.insert(id,command); // Never repeat uncertain native mutations.
    static overte::e2e::CreateBrowseSettingOwner owner;
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const auto source=owner.request(_testResultsLocation,command,DependencyManager::get<OffscreenUi>()->featureCreateDialogs());
    const QVariantMap result{{"schemaVersion",1},{"requestId",id},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureCreateBrowseSettingSequence)},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"processId",QCoreApplication::applicationPid()},
        {"runId",command.value("runId")},{"operation",command.value("operation")},{"source",source}};
    _featureCreateBrowseSettingResults.insert(id,result);return result;
}

QVariantMap TestScriptingInterface::featureCreateFiles(const QVariantMap& command) {
    if (QThread::currentThread() != thread() || _testResultsLocation.isEmpty() || !_featureLifecycle
            || _featureLifecycle->snapshot().isEmpty() || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    const auto id = command.value("commandId").toString();
    const auto json = QJsonObject::fromVariantMap(command);
    if (command.value("sourceRole") != QVariant("create-json-v1")
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
            || QJsonDocument(json).toJson(QJsonDocument::Compact).size() > 16384) { return {}; }
    if (_featureCreateFilesCommands.contains(id)) {
        return _featureCreateFilesCommands.value(id) == command ? _featureCreateFilesResults.value(id) : QVariantMap{};
    }
    if (_featureCreateFilesCommands.size() >= 512) { return {}; }
    // Persist uncertainty in process before the single filesystem operation.
    // No earlier nonce can be replayed or recaptured after another role reads.
    _featureCreateFilesCommands.insert(id, command);
    const auto requested = QDateTime::currentMSecsSinceEpoch();
    const auto source = overte::e2e::PrivateCreateFiles::request(_testResultsLocation, command);
    const QVariantMap result{{"schemaVersion", 1}, {"requestId", id}, {"instance", _featureObservationInstance},
        {"sequence", static_cast<qulonglong>(++_featureCreateFilesSequence)}, {"requestedEpochMs", requested},
        {"capturedEpochMs", QDateTime::currentMSecsSinceEpoch()}, {"processId", QCoreApplication::applicationPid()},
        {"sourceRole", "create-json-v1"}, {"runId", command.value("runId")}, {"ticket", command.value("ticket")},
        {"operation", command.value("operation")}, {"source", source}};
    _featureCreateFilesResults.insert(id, result);
    return result;
}
#endif

#if defined(ANDROID_APP_PICO_INTERFACE)
QVariantMap TestScriptingInterface::featureCreateEntities(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) {return {};}
        QVariantMap result;
        QMetaObject::invokeMethod(this,[&]{result=featureCreateEntities(command);},Qt::BlockingQueuedConnection);return result;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto id=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble()!=1
            || json.value("action").toString()!="feature-create-entities-observe"
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) {return {};}
    if (_featureCreateEntitiesCommands.contains(id)) {
        return _featureCreateEntitiesCommands.value(id)==command ? _featureCreateEntitiesResults.value(id) : QVariantMap{};
    }
    if (_featureCreateEntitiesCommands.size()>=512 || _featureCreateEntitiesSequence>=9007199254740991ULL
            || (!_featureCreateEntityIds.contains(run) && _featureCreateEntityIds.size()>=4)
            || !DependencyManager::isSet<EntityScriptingInterface>() || !DependencyManager::isSet<AvatarManager>()
            || !DependencyManager::isSet<NodeList>()) {return {};}
    _featureCreateEntitiesCommands.insert(id,command); // A nonce never recaptures a later effect.
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const auto entities=DependencyManager::get<EntityScriptingInterface>();
    const auto avatar=DependencyManager::get<AvatarManager>()->getMyAvatar();
    const auto nodes=DependencyManager::get<NodeList>();
    if (!entities || !entities->getEntityTree() || !avatar || !nodes) {return {};}
    const auto domainSession=nodes->getDomainHandler().featureChatSession(run);
    if (domainSession.isEmpty()) {return {};}
    const auto center=avatar->getWorldPosition();
    auto vector=[](const glm::vec3& v) {return QVariantList{v.x,v.y,v.z};};
    auto rotation=[](const glm::quat& q) {return QVariantList{q.x,q.y,q.z,q.w};};
    auto properties=[&](const EntityItemProperties& p) -> QVariantMap {
        const auto host=p.getEntityHostType();
        return {{"name",p.getName()},{"type",EntityTypes::getEntityTypeName(p.getType())},
            {"hostType",host==entity::HostType::DOMAIN ? "domain" : host==entity::HostType::AVATAR ? "avatar" : "local"},
            {"modelUrl",p.getModelURL()},{"textures",p.getTextures()},
            {"position",vector(p.getPosition())},{"dimensions",vector(p.getDimensions())},{"rotation",rotation(p.getRotation())},
            {"parentId",p.getParentID().isNull() ? QVariant() : QVariant(p.getParentID().toString(QUuid::WithoutBraces))},
            {"visible",p.getVisible()},{"locked",p.getLocked()}};
    };
    auto bounded=[](const EntityItemProperties& p) {
        return p.getName().size()<=256 && p.getModelURL().size()<=4096 && p.getTextures().size()<=8192;
    };
    const auto mask=PickFilter::getBitMask(PickFilter::FlagBit::DOMAIN_ENTITIES)|PickFilter::getBitMask(PickFilter::FlagBit::COARSE);
    const auto scan=entities->findEntities(center,128.0f,mask);
    if (scan.size()>1024) {return {};}
    auto& owned=_featureCreateEntityIds[run];QVariantList unowned;
    const auto prefix=QString("e2e-")+run+"-";
    const auto resource=QRegularExpression("\\A/feature-fixture/v1/runs/"+run+"/tickets/[0-9a-f]{32}/(?:gltf-bundle/main\\.gltf|obj-bundle/main\\.obj)\\z");
    const auto runModel=[&](const EntityItemProperties& p) {
        const QUrl url(p.getModelURL());return p.getType()==EntityTypes::Model && url.isValid()
            && (url.scheme()=="http" || url.scheme()=="https") && !url.host().isEmpty() && url.userInfo().isEmpty()
            && !url.authority().contains('@') && !url.hasQuery() && !url.hasFragment() && resource.match(url.path()).hasMatch();
    };
    for (const auto& entityId:scan) {
        const auto p=entities->getEntityProperties(entityId);
        if (p.getType()==EntityTypes::Unknown || !bounded(p)) {return {};}
        if (p.getName().startsWith(prefix) || runModel(p)) {owned.insert(entityId);}
        else if (!owned.contains(entityId)) {
            const auto hash=QCryptographicHash::hash(QJsonDocument::fromVariant(properties(p)).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex();
            unowned.append(QVariantMap{{"id",entityId.toString(QUuid::WithoutBraces)},{"sha256",QString::fromLatin1(hash)}});
        }
    }
    if (owned.size()>32) {return {};}
    QStringList ordered;for (const auto& entityId:owned) {ordered.append(entityId.toString(QUuid::WithoutBraces));}ordered.sort();
    QVariantList present,absent,lifetimes;
    if (!_featureCreateEntityLifetimes) {_featureCreateEntityLifetimes=std::make_shared<overte::e2e::CreateEntityLifetimes>();}
    for (const auto& text:ordered) {
        const auto entityId=QUuid(text);EntityItemPointer original;
        entities->getEntityTree()->withReadLock([&]{original=entities->getEntityTree()->findEntityByEntityItemID(entityId);});
        const auto lifetime=_featureCreateEntityLifetimes->observe(run,entityId,original);if (lifetime.isEmpty()) {return {};}
        lifetimes.append(lifetime);
        const auto p=entities->getEntityProperties(entityId);
        if (p.getType()==EntityTypes::Unknown) {if (original) {return {};}absent.append(text);continue;}
        if (!bounded(p)) {return {};}
        if (!original) {return {};}
        QVariantMap textureNames;const auto names=p.getTextureNames();if (names.size()>64) {return {};}
        for (auto it=names.cbegin();it!=names.cend();++it) {
            if (it.key().isEmpty() || it.key().size()>256 || (it.value().userType()!=QMetaType::QUrl && it.value().userType()!=QMetaType::QString)) {return {};}
            const auto actual=it.value().userType()==QMetaType::QUrl ? it.value().toUrl().toString() : it.value().toString();
            if (actual.size()>4096) {return {};}textureNames.insert(it.key(),actual);
        }
        auto row=properties(p);row.insert("visuallyReady",entities->isLoaded(entityId));row.insert("naturalDimensions",vector(p.getNaturalDimensions()));
        row.insert("textureNames",textureNames);row.insert("renderInfo",QVariantMap{{"vertices",static_cast<qulonglong>(p.getRenderInfoVertexCount())},
            {"textures",p.getRenderInfoTextureCount()},{"textureBytes",static_cast<qulonglong>(p.getRenderInfoTextureSize())},{"drawCalls",p.getRenderInfoDrawCalls()}});
        row.insert("id",text);row.insert("lastEditedEpochUs",static_cast<qulonglong>(p.getLastEdited()));present.append(row);
    }
    std::sort(unowned.begin(),unowned.end(),[](const QVariant& a,const QVariant& b) {return a.toMap().value("id").toString()<b.toMap().value("id").toString();});
    auto& domain=nodes->getDomainHandler();
    if (domain.featureChatSession(run)!=domainSession) {return {};}
    const QVariantMap source{{"createEntitySourceVersion",3},{"domainSession",domainSession},{"runId",run},{"domainConnected",domain.isConnected()},
        {"domainId",domain.getUUID().isNull() ? QVariant() : QVariant(domain.getUUID().toString(QUuid::WithoutBraces))},
        {"sessionId",nodes->getSessionUUID().isNull() ? QVariant() : QVariant(nodes->getSessionUUID().toString(QUuid::WithoutBraces))},
        {"canRez",nodes->getThisNodeCanRez()},{"canRezTmp",nodes->getThisNodeCanRezTmp()},
        {"entities",present},{"absentIds",absent},{"entityLifetimes",lifetimes},{"scan",QVariantMap{{"center",vector(center)},
            {"radiusMeters",128},{"propertyScope","create-domain-v1"},{"scannedEntities",scan.size()},{"unowned",unowned}}}};
    const QVariantMap result{{"schemaVersion",1},{"requestId",id},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureCreateEntitiesSequence)},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"processId",QCoreApplication::applicationPid()},{"source",source}};
    _featureCreateEntitiesResults.insert(id,result);return result;
}

QVariantMap TestScriptingInterface::featureCreateModels(const QVariantMap& command) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) {return {};}
        struct Result {QSemaphore ready;QVariantMap value;std::atomic_bool expired {false};};
        const auto result=std::make_shared<Result>();const QPointer<TestScriptingInterface> original(this);
        if (!QMetaObject::invokeMethod(this,[original,command,result] {
            if (!result->expired.load() && original) {result->value=original->featureCreateModels(command);}
            result->ready.release();
        },Qt::QueuedConnection) || !result->ready.tryAcquire(1,1750)) {result->expired.store(true);return {};}
        return result->value;
    }
    QStringList fields {"schemaVersion","commandId","action","runId"};fields.sort();
    const auto json=QJsonObject::fromVariantMap(command);
    const auto id=command.value("commandId").toString(),run=command.value("runId").toString();
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=fields
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-create-models-observe")
            || !json.value("commandId").isString() || !json.value("runId").isString()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) {return {};}
    if (_featureCreateModelsCommands.contains(id)) {
        return _featureCreateModelsCommands.value(id)==command ? _featureCreateModelsResults.value(id) : QVariantMap{};
    }
    if (_featureCreateModelsCommands.size()>=512 || _featureCreateModelsSequence>=9007199254740991ULL
            || !_featureCreateEntityIds.contains(run) || !DependencyManager::isSet<EntityScriptingInterface>()
            || !DependencyManager::isSet<NodeList>() || thread()!=QCoreApplication::instance()->thread()) {return {};}
    _featureCreateModelsCommands.insert(id,command); // Unknown/timeout nonces never recapture later effects.
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const auto entities=DependencyManager::get<EntityScriptingInterface>();const auto nodes=DependencyManager::get<NodeList>();
    if (!entities || !entities->getEntityTree() || !nodes || _featureCreateEntityIds.value(run).size()>32) {return {};}
    const auto session=nodes->getDomainHandler().featureChatSession(run);if (session.isEmpty()) {return {};}
    QStringList ordered;for (const auto& id:_featureCreateEntityIds.value(run)) {ordered.append(id.toString(QUuid::WithoutBraces));}ordered.sort();
    overte::e2e::CreateModelResources::Models originals;
    for (const auto& text:ordered) {
        EntityItemPointer entity;entities->getEntityTree()->withReadLock([&]{entity=entities->getEntityTree()->findEntityByEntityItemID(QUuid(text));});
        const auto renderable=std::dynamic_pointer_cast<RenderableModelEntityItem>(entity);
        originals.append({text,renderable ? renderable->featureCreateModel() : ModelPointer()});
    }
    if (!_featureCreateModelResources) {_featureCreateModelResources=std::make_shared<overte::e2e::CreateModelResources>();}
    auto source=_featureCreateModelResources->observe(run,originals);
    if (source.isEmpty() || nodes->getDomainHandler().featureChatSession(run)!=session) {return {};}
    source.insert("domainSession",session);
    const QVariantMap result{{"schemaVersion",1},{"requestId",id},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureCreateModelsSequence)},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"processId",QCoreApplication::applicationPid()},{"source",source}};
    _featureCreateModelsResults.insert(id,result);return result;
}

QVariantMap TestScriptingInterface::featureCreateDialogs(const QString& requestId) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) {return {};}
        QVariantMap result;
        QMetaObject::invokeMethod(this,[&]{result=featureCreateDialogs(requestId);},Qt::BlockingQueuedConnection);return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(requestId).hasMatch()) {return {};}
    if (_featureCreateDialogsResults.contains(requestId)) {return _featureCreateDialogsResults.value(requestId);}
    if (_featureCreateDialogsResults.size()>=512 || _featureCreateDialogsSequence>=9007199254740991ULL
            || !DependencyManager::isSet<OffscreenUi>()) {return {};}
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const auto source=DependencyManager::get<OffscreenUi>()->featureCreateDialogs();if (source.isEmpty()) {return {};}
    const QVariantMap result{{"schemaVersion",1},{"requestId",requestId},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureCreateDialogsSequence)},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"processId",QCoreApplication::applicationPid()},{"source",source}};
    _featureCreateDialogsResults.insert(requestId,result);return result;
}

QVariantMap TestScriptingInterface::featureCreateCallbacks(const QString& requestId) {
    if (QThread::currentThread()!=thread()) {
        if (!thread() || !thread()->isRunning()) { return {}; }
        QVariantMap result;
        QMetaObject::invokeMethod(this,[&]{result=featureCreateCallbacks(requestId);},Qt::BlockingQueuedConnection);return result;
    }
    if (_testResultsLocation.isEmpty() || !_featureLifecycle || _featureLifecycle->snapshot().isEmpty()
            || !QCoreApplication::arguments().contains("--testScript")
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(requestId).hasMatch()) { return {}; }
    if (_featureCreateCallbacksResults.contains(requestId)) { return _featureCreateCallbacksResults.value(requestId); }
    if (_featureCreateCallbacksResults.size()>=512 || _featureCreateCallbacksSequence>=9007199254740991ULL) { return {}; }
    if (!DependencyManager::isSet<ScriptEngines>()) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    const auto source=DependencyManager::get<ScriptEngines>()->featureCreateCallbackObservation();
    if (source.isEmpty()) { return {}; }
    const QVariantMap result{{"schemaVersion",1},{"requestId",requestId},{"instance",_featureObservationInstance},
        {"sequence",static_cast<qulonglong>(++_featureCreateCallbacksSequence)},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"processId",QCoreApplication::applicationPid()},{"source",source}};
    _featureCreateCallbacksResults.insert(requestId,result);return result;
}
#endif

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
    if (!DependencyManager::isSet<ScriptEngines>()) { return {}; }
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
    // New observation packets must never fall through to ordinary result-file
    // permissions merely because their filename was omitted from this list.
    const bool featureResult=filename.startsWith("feature-");
    if (featureResult && !QRegularExpression("\\Afeature-[a-z0-9]+(?:-[a-z0-9]+)*\\.json\\z").match(filename).hasMatch()) { return; }
    if (featureResult || filename == "feature-chat-observation.json" || filename == "feature-native-observation.json" || filename == "normal-feature-observation.json"
            || filename == "feature-chat-view-observation.json" || filename == "feature-web-dom-observation.json"
            || filename == "feature-pending-commit-owner.json" || filename == "feature-navigation-replies.json"
            || filename == "feature-location-bookmarks.json"
            || filename == "feature-navigation-modals.json" || filename == "feature-navigation-environment.json" || filename == "feature-navigation-directory.json"
            || filename == "feature-process-presence.json"
            || filename == "feature-graphics-subject.json" || filename == "feature-scene-load.json"
            || filename == "feature-web-runtime.json" || filename == "feature-tablet-http.json"
            || filename == "recorded-preview-observation.json" || filename == "feature-script-observation.json"
            || filename == "feature-script-work.json" || filename == "feature-script-files.json" || filename == "feature-create-files.json" || filename == "feature-create-callbacks.json"
            || filename == "feature-create-entities.json" || filename == "feature-create-browse-setting.json" || filename == "feature-create-dialogs.json" || filename == "world-render-observation.json"
            || filename == "world-render-receipt-result.json" || filename == "world-render-receipts-result.json"
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
