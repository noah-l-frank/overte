// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <EntityScriptingInterface.h>
#include <EntityItemProperties.h>
#include <EntityTree.h>
#include <PolyVoxEntityItem.h>
#include <NodeList.h>
#include <PickFilter.h>
#include <QJsonDocument>
#include <QJsonObject>
#include <QCryptographicHash>
#include <QSet>
#include <QThread>
#include <QCoreApplication>
#include <QRegularExpression>
#include <QJsonArray>
#include <algorithm>
#include <memory>

namespace overte::e2e {
// Read-only bounded native inventory. The caller separately owns IDs. A name
// match is discovery only and never authority to delete a foreign replacement.
inline QVariantMap phoneCreateObservationSource(const QVariantMap& command, const glm::vec3& feet) {
    const auto json=QJsonObject::fromVariantMap(command);
    QStringList fields{"schemaVersion","commandId","action","runId","trackedIds"};fields.sort();
    const auto run=command.value("runId").toString(),request=command.value("commandId").toString();
    const QRegularExpression nonce("\\A[0-9a-f]{32}\\z"),identifier("\\A[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\\z");
    if (QThread::currentThread()!=qApp->thread() || command.keys()!=fields
            || !QCoreApplication::arguments().contains("--testScript")
            || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble()!=1
            || command.value("action").toString()!="phone-create-observe"
            || !json.value("commandId").isString() || !nonce.match(request).hasMatch() || request==QString(32,'0')
            || !json.value("runId").isString() || !nonce.match(run).hasMatch() || run==QString(32,'0')
            || !json.value("trackedIds").isArray() || json.value("trackedIds").toArray().size()>32) { return {}; }
    const auto entities=DependencyManager::get<EntityScriptingInterface>();
    const auto nodes=DependencyManager::get<NodeList>();
    if (!entities || !entities->getEntityTree() || !nodes) { return {}; }
    QSet<QUuid> tracked,observed;
    QString previous;
    for (const auto& raw:json.value("trackedIds").toArray()) {
        const auto text=raw.toString();const QUuid id(text);
        if (!raw.isString() || !identifier.match(text).hasMatch() || id.isNull() || (!previous.isEmpty() && text<=previous)) { return {}; }
        previous=text;tracked.insert(id);
    }
    const auto mask=PickFilter::getBitMask(PickFilter::FlagBit::LOCAL_ENTITIES)
        | PickFilter::getBitMask(PickFilter::FlagBit::DOMAIN_ENTITIES)
        | PickFilter::getBitMask(PickFilter::FlagBit::AVATAR_ENTITIES)
        | PickFilter::getBitMask(PickFilter::FlagBit::COARSE);
    const auto nearby=entities->findEntities(feet,128.0f,mask);
    if (nearby.size()>1024) { return {}; }
    const auto prefix="e2e-"+run+'-';
    const QSet<QString> names{prefix+"model",prefix+"voxel",prefix+"cube"};
    observed=tracked;QVariantList inventory;
    for (const auto& id:nearby) {
        const auto actual=entities->getEntityProperties(id);
        if (actual.getType()==EntityTypes::Unknown) { return {}; }
        const auto host=actual.getEntityHostType();
        inventory.append(QVariantMap{{"id",id.toString(QUuid::WithoutBraces)},
            {"type",EntityTypes::getEntityTypeName(actual.getType())},
            {"host",host==entity::HostType::LOCAL ? "local" : host==entity::HostType::AVATAR ? "avatar" : "domain"},
            {"nameSha256",QString::fromLatin1(QCryptographicHash::hash(actual.getName().toUtf8(),QCryptographicHash::Sha256).toHex())}});
        if (names.contains(actual.getName())) { observed.insert(id); }
    }
    if (observed.size()>32) { return {}; }
    auto vec=[](const glm::vec3& value) { return QVariantList{value.x,value.y,value.z}; };
    auto quat=[](const glm::quat& value) { return QVariantList{value.x,value.y,value.z,value.w}; };
    QVariantList rows,absent;
    auto ordered=observed.values();std::sort(ordered.begin(),ordered.end(),[](const QUuid& a,const QUuid& b) { return a.toString()<b.toString(); });
    for (const auto& id:ordered) {
        const auto p=entities->getEntityProperties(id);
        if (p.getType()==EntityTypes::Unknown) { absent.append(id.toString(QUuid::WithoutBraces));continue; }
        if (p.getName().size()>256 || p.getModelURL().size()>2048 || p.getTextures().size()>16384) { return {}; }
        const auto host=p.getEntityHostType();
        QVariant voxel;
        if (p.getType()==EntityTypes::PolyVox) {
            const auto tree=entities->getEntityTree();bool valid=false;
            tree->withReadLock([&] {
                auto actual=std::dynamic_pointer_cast<PolyVoxEntityItem>(tree->findEntityByEntityItemID(id));
                if (!actual) { return; }
                const auto bytes=actual->getVoxelData();
                if (bytes.size()>16*1024*1024) { return; }
                voxel=QVariantMap{{"savedSha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())},
                    {"savedBytes",bytes.size()},{"ready",actual->isVoxelDataReady()},{"volumeSize",vec(actual->getVoxelVolumeSize())}};
                valid=true;
            });
            if (!valid) { return {}; }
        }
        rows.append(QVariantMap{{"id",id.toString(QUuid::WithoutBraces)},{"name",p.getName()},
            {"type",EntityTypes::getEntityTypeName(p.getType())},
            {"host",host==entity::HostType::LOCAL ? "local" : host==entity::HostType::AVATAR ? "avatar" : "domain"},
            {"parentId",p.getParentID().isNull() ? QVariant() : QVariant(p.getParentID().toString(QUuid::WithoutBraces))},
            {"position",vec(p.getPosition())},{"rotation",quat(p.getRotation())},{"dimensions",vec(p.getDimensions())},
            {"visible",p.getVisible()},{"locked",p.getLocked()},{"modelUrl",p.getModelURL()},{"textures",p.getTextures()},{"voxel",voxel}});
    }
    const auto domain=nodes->getDomainHandler().getUUID();
    return {{"phoneCreateObservationVersion",1},{"connected",nodes->getDomainHandler().isConnected()},
        {"domainId",domain.isNull() ? QVariant() : QVariant(domain.toString(QUuid::WithoutBraces))},
        {"canRez",entities->canRez()},{"canRezTmp",entities->canRezTmp()},{"canRezAvatarEntities",entities->canRezAvatarEntities()},
        {"scan",QVariantMap{{"center",vec(feet)},{"radiusMeters",128},{"scannedEntities",nearby.size()},{"complete",true},{"inventory",inventory}}},
        {"entities",rows},{"absentIds",absent}};
}
} // namespace overte::e2e
#endif
