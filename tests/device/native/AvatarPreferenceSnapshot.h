// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <SettingManager.h>
#include <SettingHandle.h>
#include <DependencyManager.h>
#include "AvatarPreferenceFile.h"
#include "AudioSettingsQueue.h"
namespace overte::e2e {
// Original Manager/Handle/writer state plus independent physical JSON rows.
// A late queued result remains owned in this collector and is never adopted.
// capture() never initializes Handles or syncs/reloads QSettings. The separate
// typed lazy-only CAS below cannot restore a written worker/file difference.
class AvatarPreferenceSnapshot {
public:
    template<class T> class HandleMemento {
        friend class AvatarPreferenceSnapshot;
    public:
        bool valid()const {return !proof.isEmpty() && owner && handle && manager;}
        QVariantMap original()const {return proof;}
    private:
        QPointer<QObject> owner;Setting::Handle<T>* handle{nullptr};QSharedPointer<Setting::Manager> manager;
        T value{},fallback{};bool initialized{false},isSet{false},deprecated{false};
        std::shared_ptr<std::atomic<bool>> attempted{std::make_shared<std::atomic<bool>>(false)};
        QWeakPointer<Setting::Manager> binding;QHash<QString,Setting::Interface*> registrations;
        QHash<QString,QVariant> settings;QVariantMap typedSettings,proof;
    };
    // The caller supplies its existing Avatar QObject and actual Handle. No
    // script-provided replacement values or deserialization enter this owner.
    template<class T> HandleMemento<T> remember(QObject* owner,Setting::Handle<T>& handle,
            const std::function<QVariantMap()>& handles) {
        HandleMemento<T> result;bool first=true,consistent=true;
        if(!owner || owner->thread()!=QThread::currentThread() || !avatarPreferenceKey(handle._key)) {return result;}
        const auto proof=capture([&] {
            auto native=handles();if(native.isEmpty()) {return QVariantMap{};}
            const auto manager=DependencyManager::get<Setting::Manager>();HandleMemento<T> observed;
            observed.owner=owner;observed.handle=&handle;observed.manager=manager;
            const bool locked=manager->withTryReadLock([&] {
                observed.value=handle._value;observed.fallback=handle._defaultValue;
                observed.initialized=handle._isInitialized;observed.isSet=handle._isSet;observed.deprecated=handle._isDeprecated;
                observed.binding=handle._manager;observed.registrations=manager->_handles;observed.settings=manager->_settings;
                observed.typedSettings=typedSettings(manager->_settings);
            },0);
            if(!locked || observed.typedSettings.isEmpty()) {return QVariantMap{};}
            if(first) {result=observed;first=false;}else {consistent=consistent && sameHandle(result,observed);}
            return consistent ? native : QVariantMap{};
        });
        if(!consistent || proof.isEmpty()) {return {};}
        result.proof=proof;return result;
    }
    template<class T> bool unchanged(const HandleMemento<T>& original,const HandleMemento<T>& current)const {
        return original.valid() && current.valid() && sameHandle(original,current)
            && stableProof(original.proof)==stableProof(current.proof);
    }
    // Only undo the original get()/maybeInit() transition when it did not
    // write the worker or physical file. A set()/save(), changed registration,
    // foreign cache row, stale source, or already attempted transaction refuses.
    // The supplied durable journal must commit each event before returning true.
    template<class T> QVariantMap restoreUnwrittenLazy(HandleMemento<T>& original,const HandleMemento<T>& expected,
            const std::function<QVariantMap()>& handles,const std::function<bool(const QVariantMap&)>& journal) {
        if(!original.valid() || !expected.valid() || original.attempted->load() || !journal
                || original.owner!=expected.owner || original.handle!=expected.handle || original.manager!=expected.manager
                || original.initialized || original.isSet || original.binding.lock() || original.registrations.contains(original.handle->_key)
                || original.settings.contains(original.handle->_key) || !expected.initialized || expected.isSet
                || expected.binding.lock()!=original.manager || expected.registrations.value(original.handle->_key)!=original.handle
                || !expected.settings.contains(original.handle->_key) || expected.settings.value(original.handle->_key).isValid()
                || raw(original.value)!=raw(expected.value) || raw(original.fallback)!=raw(expected.fallback)
                || original.deprecated!=expected.deprecated || !fresh(expected.proof)) {return {};}
        auto settings=expected.settings;settings.remove(original.handle->_key);
        auto registrations=expected.registrations;registrations.remove(original.handle->_key);
        if(typedSettings(settings)!=original.typedSettings || registrations!=original.registrations
                || stableWriter(original.proof)!=stableWriter(expected.proof)) {return {};}
        const auto actual=remember(original.owner, *original.handle,handles);
        if(!unchanged(expected,actual)) {return {};}
        // Copies of a native memento share the one attempt. A lost/failed
        // intent/result never authorizes a replay through an old copy.
        if(original.attempted->exchange(true)) {return {};}
        const auto token=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        const QVariantMap intent{{"avatarLazyHandleCasVersion",1},{"transaction",token},{"phase","intent"},
            {"key",original.handle->_key},{"original",original.proof},{"expected",expected.proof}};
        if(QJsonDocument::fromVariant(intent).toJson(QJsonDocument::Compact).size()>65536) {return {};}
        if(!journal(intent)) {return {};}
        bool restored=false;
        {
            const auto manager=original.manager;
            manager->_featureAvatarPreferencesBarrier.compareAndMutate(expected.proof.value("mutationSequence").toLongLong(),original.handle->_key,[&] {
              manager->withTryWriteLock([&] {
                auto& handle=*original.handle;
                if(!original.owner || !fresh(expected.proof) || manager!=DependencyManager::get<Setting::Manager>() || manager->thread()!=QThread::currentThread()
                        || manager->_handles!=expected.registrations || typedSettings(manager->_settings)!=expected.typedSettings
                        || handle._isInitialized!=expected.initialized || handle._isSet!=expected.isSet || handle._manager.lock()!=expected.binding.lock()
                        || handle._isDeprecated!=expected.deprecated || raw(handle._value)!=raw(expected.value)
                        || raw(handle._defaultValue)!=raw(expected.fallback)) {return;}
                // No Setting::Handle::get/remove/deinit, Manager write signal,
                // QSettings sync, mutation-sequence reset, or unowned row write.
                manager->_handles.remove(handle._key);manager->_settings.remove(handle._key);
                handle._value=original.value;handle._isInitialized=original.initialized;handle._isSet=original.isSet;
                handle._manager=original.binding;handle._isDeprecated=original.deprecated;restored=true;
              },0);return restored;
            });
        }
        const auto after=remember(original.owner,*original.handle,handles);
        const bool verified=restored && after.valid() && sameHandle(original,after)
            && stableWriter(original.proof)==stableWriter(after.proof)
            && after.proof.value("mutationSequence").toLongLong()>expected.proof.value("mutationSequence").toLongLong();
        const QVariantMap result{{"avatarLazyHandleCasVersion",1},{"transaction",token},{"phase","result"},
            {"restored",restored},{"verified",verified},{"after",after.proof}};
        if(QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size()>65536) {return {};}
        if(!journal(result) || !verified) {return {};}
        return result;
    }
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
private:
    template<class T> static QVariantMap raw(const T& value) {return avatarPreferenceRaw(true,QVariant::fromValue(value));}
    static QVariantMap typedSettings(const QHash<QString,QVariant>& settings) {
        if(settings.size()>512) {return {};}
        QVariantMap values;for(auto it=settings.cbegin();it!=settings.cend();++it) {values.insert(it.key(),it.value());}
        return raw(values);
    }
    template<class T> static bool sameHandle(const HandleMemento<T>& a,const HandleMemento<T>& b) {
        return a.owner==b.owner && a.handle==b.handle && a.manager==b.manager && raw(a.value)==raw(b.value)
            && raw(a.fallback)==raw(b.fallback) && a.initialized==b.initialized && a.isSet==b.isSet && a.deprecated==b.deprecated
            && a.binding.lock()==b.binding.lock() && a.registrations==b.registrations && a.typedSettings==b.typedSettings;
    }
    static QVariantMap stableWriter(const QVariantMap& proof) {
        auto writer=proof.value("writer").toMap();writer.remove("capturedEpochMs");
        auto physical=writer.value("physical").toMap();physical.remove("capturedEpochMs");writer["physical"]=physical;return writer;
    }
    static QVariantMap stableProof(QVariantMap proof) {
        proof.remove("capturedEpochMs");proof.remove("elapsedMs");proof["writer"]=stableWriter(proof);return proof;
    }
    static bool fresh(const QVariantMap& proof) {
        const auto now=QDateTime::currentMSecsSinceEpoch(),then=proof.value("capturedEpochMs").toLongLong();
        return then>0 && then<=now && now-then<=1500;
    }
    AudioSettingsQueue _writer;
};
} // namespace overte::e2e
#endif
