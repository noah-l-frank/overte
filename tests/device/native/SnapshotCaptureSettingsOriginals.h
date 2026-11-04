// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "SnapshotSettingsOriginals.h"
namespace overte::e2e {
inline bool snapshotCaptureSettingsCommand(const QVariantMap& command) {
    if(command.keys()!=QStringList{"commandId","runId","schemaVersion","settingsScope"}
        || (command.value("settingsScope").userType()!=QMetaType::Int && command.value("settingsScope").userType()!=QMetaType::Double)
        || command.value("settingsScope").toDouble()!=2) {return false;}
    auto original=command;original.remove("settingsScope");return snapshotSettingsCommand(original);
}
inline bool snapshotCaptureSettingsRaw(const QVariantMap& raw,int type=-1) {
    if(raw.keys()!=QStringList{"base64","present","sha256","typeId","typeName"}
        || raw.value("present").userType()!=QMetaType::Bool || raw.value("typeId").userType()!=QMetaType::Int
        || (type>=0 && raw.value("typeId").toInt()!=type) || raw.value("base64").userType()!=QMetaType::QString
        || raw.value("base64").toString().size()>43692 || raw.value("sha256").userType()!=QMetaType::QString) {return false;}
    const auto id=raw.value("typeId").toInt();
    if(!QSet<int>{QMetaType::UnknownType,QMetaType::Bool,QMetaType::Int,QMetaType::UInt,QMetaType::LongLong,
            QMetaType::ULongLong,QMetaType::Double,QMetaType::QString,QMetaType::Float}.contains(id)
        || (!raw.value("present").toBool() && id!=QMetaType::UnknownType)
        || (type>=0 && !raw.value("present").toBool())) {return false;}
    if(id==QMetaType::UnknownType) {if(raw.value("typeName").isValid()) {return false;}}
    else if(raw.value("typeName").userType()!=QMetaType::QString
        || raw.value("typeName").toString()!=QString::fromLatin1(QMetaType::typeName(id))) {return false;}
    const auto encoded=raw.value("base64").toString().toLatin1();const auto bytes=QByteArray::fromBase64(encoded);
    return !bytes.isEmpty() && bytes.size()<=32768 && bytes.toBase64()==encoded
        && QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())==raw.value("sha256").toString();
}
inline QVariantMap snapshotCaptureSettingsOriginals(const QVariantMap& command,const QString& birth,const QVariantMap& manager,
        const QVariantMap& formatCache,const QVariantMap& durationCache,quint64 sequence) {
    if(!snapshotCaptureSettingsCommand(command)
        || manager.keys()!=QStringList{"capturedEpochMs","durationEntry","entries","instance","snapshotSettingsEntriesVersion"}
        || manager.value("snapshotSettingsEntriesVersion").userType()!=QMetaType::Int || manager.value("snapshotSettingsEntriesVersion").toInt()!=2
        || manager.value("durationEntry").userType()!=QMetaType::QVariantMap
        || durationCache.keys()!=QStringList{"defaultValue","initialized","set","value"}
        || durationCache.value("initialized").userType()!=QMetaType::Bool || durationCache.value("set").userType()!=QMetaType::Bool
        || durationCache.value("value").userType()!=QMetaType::QVariantMap || durationCache.value("defaultValue").userType()!=QMetaType::QVariantMap) {return {};}
    const auto entry=manager.value("durationEntry").toMap();
    if(entry.keys()!=QStringList{"original","present"} || entry.value("present").userType()!=QMetaType::Bool
        || entry.value("original").userType()!=QMetaType::QVariantMap || !snapshotCaptureSettingsRaw(entry.value("original").toMap())
        || entry.value("original").toMap().value("present")!=entry.value("present")
        || !snapshotCaptureSettingsRaw(durationCache.value("value").toMap(),QMetaType::Float)
        || !snapshotCaptureSettingsRaw(durationCache.value("defaultValue").toMap(),QMetaType::Float)) {return {};}
    // Reuse the unchanged thirteen-key/type/format validation only as an internal
    // projection of this actual read. No historical Source1 artifact is relabeled.
    auto baseCommand=command;baseCommand.remove("settingsScope");auto baseManager=manager;
    baseManager.remove("durationEntry");baseManager["snapshotSettingsEntriesVersion"]=1;
    auto result=snapshotSettingsOriginals(baseCommand,birth,baseManager,formatCache,sequence);if(result.isEmpty()) {return {};}
    auto source=result.value("source").toMap();source["durationEntry"]=entry;source["durationCache"]=durationCache;
    const QVariantMap actual{{"entries",source.value("entries")},{"formatCache",formatCache},{"durationEntry",entry},{"durationCache",durationCache}};
    QByteArray bytes;QDataStream stream(&bytes,QIODevice::WriteOnly);stream.setVersion(QDataStream::Qt_5_12);stream<<QVariant::fromValue(actual);
    if(stream.status()!=QDataStream::Ok || bytes.isEmpty() || bytes.size()>32768) {return {};}
    source["typedSerializedBase64"]=QString::fromLatin1(bytes.toBase64());source["typedSha256"]=QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());
    result["snapshotSettingsOriginalsVersion"]=2;result["source"]=source;
    return QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size()<=65536 ? result : QVariantMap{};
}
}
#endif
