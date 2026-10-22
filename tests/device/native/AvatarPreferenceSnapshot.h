// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <SettingManager.h>
#include <DependencyManager.h>
#include "AvatarPreferenceFile.h"
#include "AudioSettingsQueue.h"
namespace overte::e2e {
// Original Manager/Handle/writer state plus independent physical JSON rows.
// A late queued result remains owned in this collector and is never adopted.
// This source never initializes Handles, syncs/reloads QSettings, or restores.
class AvatarPreferenceSnapshot {
public:
    QVariantMap capture(const std::function<QVariantMap()>& handles) {
        if(!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript")
                || !DependencyManager::isSet<Setting::Manager>() || !handles) {return {};}
        const auto manager=DependencyManager::get<Setting::Manager>();
        if(!manager || manager->thread()!=QThread::currentThread() || manager->thread()!=QCoreApplication::instance()->thread()) {return {};}
        const auto result=manager->_featureAvatarPreferencesBarrier.read([manager,handles] {
            QVariantMap rows;QSettings::SettingsMap actual;
            const bool locked=manager->withTryReadLock([&] {
                for(auto it=manager->_settings.cbegin();it!=manager->_settings.cend();++it) {
                    if(!avatarPreferenceKey(it.key())) {continue;}
                    if(rows.size()>=512) {rows.clear();rows.insert("overflow",true);return;}
                    const auto raw=avatarPreferenceRaw(true,it.value());if(raw.isEmpty()) {rows.clear();rows.insert("overflow",true);return;}
                    rows.insert(it.key(),raw);actual.insert(it.key(),it.value());
                }
            },0);
            if(!locked || rows.contains("overflow")) {return QVariantMap{};}
            const auto actualHandles=handles();if(actualHandles.isEmpty()) {return QVariantMap{};}
            const auto nativeHandles=actualHandles.value("handles").toMap().value("handles").toMap();
            QSettings::SettingsMap normalized;
            for(auto it=actual.begin();it!=actual.end();++it) {
                const auto key=it.key().split('/',Qt::SkipEmptyParts).join('/');bool lazyAbsent=false;
                if(!it.value().isValid()) {
                    for(const auto& value:nativeHandles) {const auto handle=value.toMap();
                        if(handle.value("key")==QVariant(it.key()) && handle.value("initialized")==QVariant(true)
                                && handle.value("managerBound")==QVariant(true) && handle.value("isSet")==QVariant(false)) {lazyAbsent=true;}
                    }
                }
                if(lazyAbsent) {continue;}
                if(normalized.contains(key)) {return QVariantMap{};}normalized.insert(key,it.value());
            }
            const auto encoded=avatarPreferenceEncoded(normalized);if(encoded.isEmpty()) {return QVariantMap{};}
            return QVariantMap{{"rows",rows},{"encodedRows",encoded},{"native",actualHandles}};
        },[this,manager] {
            const auto worker=manager->_featureBrowseWriteWorker;
            const auto birth=manager->_featureBrowseWriteWorkerBirth;
            if(!worker || birth.isEmpty() || !manager->_workerThread.isRunning() || worker->thread()!=&manager->_workerThread) {return QVariantMap{};}
            const auto value=_writer.read("client",worker.data(),[birth](QObject* original) {
                const auto worker=static_cast<Setting::WriteWorker*>(original);
                if(worker->thread()!=QThread::currentThread() || !worker->_qSettings || worker->_qSettings->format()!=JSON_FORMAT
                        || worker->_qSettings->status()!=QSettings::NoError) {return AudioSettingsPart{};}
                QSettings::SettingsMap actual;QVariantMap rows;
                for(const auto& key:worker->_qSettings->allKeys()) {
                    if(!avatarPreferenceKey(key)) {continue;}
                    if(rows.size()>=512) {return AudioSettingsPart{};}
                    const auto variant=worker->_qSettings->value(key);const auto raw=avatarPreferenceRaw(true,variant);
                    if(raw.isEmpty()) {return AudioSettingsPart{};}actual.insert(key,variant);rows.insert(key,raw);
                }
                const auto expected=avatarPreferenceEncoded(actual);
                const auto physical=avatarPreferenceFile(worker->_qSettings->fileName(),worker->_qSettings->format());
                if(expected.isEmpty() || physical.isEmpty() || worker->_qSettings->status()!=QSettings::NoError) {return AudioSettingsPart{};}
                return AudioSettingsPart{{{"instance",birth},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
                    {"rows",rows},{"encodedRows",expected},{"physical",physical},{"matchesPhysical",expected==physical.value("rows").toMap()}},{}};
            }).values;
            if(worker.isNull() || manager->_featureBrowseWriteWorker!=worker || manager->_featureBrowseWriteWorkerBirth!=birth) {return QVariantMap{};}
            return value;
        });
        if(result.isEmpty() || !DependencyManager::isSet<Setting::Manager>() || DependencyManager::get<Setting::Manager>()!=manager) {return {};}
        auto complete=result;
        // The real JSON writer intentionally converts float/QUrl and may
        // reload them as double/QString. Compare its actual original encoding,
        // retaining every raw typed cache/writer/Handle value independently.
        complete["cacheMatchesWriter"]=result.value("cache").toMap().value("encodedRows")==result.value("writer").toMap().value("encodedRows");
        return QJsonDocument(QJsonObject::fromVariantMap(complete)).toJson(QJsonDocument::Compact).size()<=245760 ? complete : QVariantMap{};
    }
private:AudioSettingsQueue _writer;
};
} // namespace overte::e2e
#endif
