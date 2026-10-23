//
//  SettingManager.cpp
//
//
//  Created by Clement on 2/2/15.
//  Copyright 2015 High Fidelity, Inc.
//  Copyright 2022 Overte e.V.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//

#include "SettingManager.h"

#include <QtCore/QThread>
#include <QtCore/QDebug>
#include <QtCore/QUuid>
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QDataStream>
#endif

#include "SettingInterface.h"

Q_LOGGING_CATEGORY(settings_manager, "settings.manager")
Q_LOGGING_CATEGORY(settings_writer, "settings.manager.writer")

namespace Setting {

#if defined(OVERTE_E2E_FEATURE_TESTS)
    QVariantMap WriteWorker::featureChatSnapshot() {
        if (!QCoreApplication::arguments().contains("--testScript") || QThread::currentThread()!=thread()) { return {}; }
        sync();
        if (!_qSettings || _qSettings->status()!=QSettings::NoError) { return {}; }
        const auto physical=overte::e2e::chatSettingsFile(_qSettings->fileName(),_qSettings->format());
        if (physical.isEmpty()) { return {}; }
        QVariantMap values;
        for (const auto key:{"ArmoredChat-Messages","ArmoredChat-Config"}) {
            values.insert(key,QVariantMap{{"present",_qSettings->contains(key)},{"value",_qSettings->value(key)}});
        }
        return {{"instance",_featureChatInstance},{"values",values},{"physical",physical}};
    }


    bool Manager::featureChatRestoreHistory(const QVariantMap& expected,const QVariantMap& original) {
        if (!QCoreApplication::arguments().contains("--testScript") || QThread::currentThread()!=thread()
                || expected.value("settingsBarrierVersion")!=QVariant(2) || original.size()!=2
                || original.value("present").userType()!=QMetaType::Bool || !original.contains("value")) { return false; }
        const auto value=original.value("value");
        if (value.isValid() && !value.isNull() && !(value.userType()==QMetaType::QString && value.toString().isEmpty())
                && !(value.userType()==QMetaType::QVariantList && value.toList().isEmpty())
                && !(value.userType()==QMetaType::QStringList && value.toStringList().isEmpty())) { return false; }
        if (!original.value("present").toBool() && value.isValid()) { return false; }
        // An external physical writer does not increment the Manager's mutation
        // counter. Reacquire the actual original worker/file before admission;
        // no Manager/barrier lock spans this bounded queued acquisition.
        const auto current=featureChatSnapshot();
        if (current.isEmpty() || current.value("instance")!=expected.value("instance")
                || current.value("mutationSequence")!=expected.value("mutationSequence")) { return false; }
        QByteArray expectedRows,currentRows;QDataStream expectedStream(&expectedRows,QIODevice::WriteOnly),currentStream(&currentRows,QIODevice::WriteOnly);
        expectedStream<<expected.value("cache")<<expected.value("writer");
        currentStream<<current.value("cache")<<current.value("writer");
        if (expectedStream.status()!=QDataStream::Ok || currentStream.status()!=QDataStream::Ok || expectedRows!=currentRows) { return false; }
        overte::e2e::ChatSettingsBarrier::Mutation mutation(_featureChatSettings,"ArmoredChat-Messages");
        bool admitted{false};
        if (!withTryWriteLock([&] {
            const auto cache=expected.value("cache").toMap();
            for (const auto key:{"ArmoredChat-Messages","ArmoredChat-Config"}) {
                QByteArray before,actual;QDataStream beforeStream(&before,QIODevice::WriteOnly),actualStream(&actual,QIODevice::WriteOnly);
                const auto row=cache.value(key).toMap();
                if (row.size()!=2 || row.value("present").userType()!=QMetaType::Bool || !row.contains("value")) { return; }
                beforeStream<<row.value("present").toBool()<<row.value("value");
                actualStream<<_settings.contains(key)<<_settings.value(key);
                if (beforeStream.status()!=QDataStream::Ok || actualStream.status()!=QDataStream::Ok || before!=actual) { return; }
            }
            if (!_featureChatSettings.restoreAdmission(expected.value("instance").toString(),expected.value("mutationSequence").toLongLong())) { return; }
            if (original.value("present").toBool()) { _settings.insert("ArmoredChat-Messages",value); }
            else { _settings.remove("ArmoredChat-Messages"); }
            admitted=true;
        },0) || !admitted) { return false; }
        // Match the normal original Manager mutation path: signal after unlock.
        if (original.value("present").toBool()) { emit valueChanged("ArmoredChat-Messages",value); }
        else { emit keyRemoved("ArmoredChat-Messages"); }
        return true;
    }

    QVariantMap Manager::featureChatSnapshot() {
        if (!QCoreApplication::arguments().contains("--testScript") || QThread::currentThread()!=thread()) { return {}; }
        return _featureChatSettings.read([this] {
            QVariantMap values;
            if (!withTryReadLock([this,&values] {
                for (const auto key:{"ArmoredChat-Messages","ArmoredChat-Config"}) {
                    values.insert(key,QVariantMap{{"present",_settings.contains(key)},{"value",_settings.value(key)}});
                }
            },0)) { return QVariantMap(); }
            return values;
        },[this] {
            const QPointer<WriteWorker> original=_featureChatWorker;
            if (!original || original->thread()!=&_workerThread || !_workerThread.isRunning()) { return QVariantMap(); }
            // Never queue a second snapshot behind unfinished original work, and
            // never adopt a late result as a newly requested observation.
            if (_featureChatRead && !_featureChatRead->done.load(std::memory_order_acquire)) { return QVariantMap(); }
            _featureChatRead=std::make_shared<ChatSnapshotJob>();
            const auto job=_featureChatRead;
            if (!QMetaObject::invokeMethod(original.data(),[original,job] {
                if (original) { job->result=original->featureChatSnapshot(); }
                job->done.store(true,std::memory_order_release);
                job->finished.release();
            },Qt::QueuedConnection)) { _featureChatRead.reset();return QVariantMap(); }
            if (!job->finished.tryAcquire(1,1500)) { return QVariantMap(); }
            return job->result;
        });
    }
#endif


    void WriteWorker::start() {
        // QSettings seems to have some issues with moving to a new thread.
        // Make sure the object is only created once the thread is already up and running.
        init();
    }

    void WriteWorker::setValue(const QString key, const QVariant value) {
       //qCDebug(settings_writer) << "Setting config " << key << "to" << value;

        init();

        if (!_qSettings->contains(key) || _qSettings->value(key) != value) {
            _qSettings->setValue(key, value);
        }
    }

    void WriteWorker::removeKey(const QString key) {
        init();
        _qSettings->remove(key);
    }

    void WriteWorker::clearAllSettings() {
        init();
        _qSettings->clear();
        sync();
    }

    void WriteWorker::sync() {
        //qCDebug(settings_writer) << "Forcing settings sync";
        init();
        _qSettings->sync();
    }

    void WriteWorker::threadFinished() {
        qCDebug(settings_writer) << "Settings write worker syncing and terminating";
        sync();
        this->deleteLater();
    }

    void WriteWorker::terminate() {
        qCDebug(settings_writer) << "Settings write worker being asked to terminate. Syncing and terminating.";
        sync();
        this->deleteLater();
        QThread::currentThread()->exit(0);
    }

    Manager::Manager(QObject *parent) {
        WriteWorker *worker = new WriteWorker();
#if defined(OVERTE_E2E_FEATURE_TESTS)
        _featureChatWorker=worker;
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        _featureBrowseWriteWorker=worker;
        _featureBrowseWriteWorkerBirth=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
#endif

        // We operate purely from memory, and forward all changes to a thread that has writing the
        // settings as its only job.

        qCDebug(settings_manager) << "Initializing settings write thread";

        _workerThread.setObjectName("Settings Writer");
        worker->moveToThread(&_workerThread);
        // connect(&_workerThread, &QThread::started, worker, &WriteWorker::start, Qt::QueuedConnection);

        // All normal connections are queued, so that we're sure they happen asynchronously.
        connect(&_workerThread, &QThread::finished, worker, &WriteWorker::threadFinished, Qt::QueuedConnection);
        connect(this, &Manager::valueChanged, worker, &WriteWorker::setValue, Qt::QueuedConnection);
        connect(this, &Manager::keyRemoved, worker, &WriteWorker::removeKey, Qt::QueuedConnection);
        connect(this, &Manager::syncRequested, worker, &WriteWorker::sync, Qt::QueuedConnection);
        connect(this, &Manager::clearAllSettingsRequested, worker, &WriteWorker::clearAllSettings, Qt::QueuedConnection);

        // This one is blocking because we want to wait until it's actually processed.
        connect(this, &Manager::terminationRequested, worker, &WriteWorker::terminate, Qt::BlockingQueuedConnection);


        _workerThread.start();

        // Load all current settings
        QSettings settings;
        _fileName = settings.fileName();

        for(QString key : settings.allKeys()) {
            //qCDebug(settings_manager) << "Loaded key" << key << "with value" << settings.value(key);
            _settings[key] = settings.value(key);
        }
    }


    Manager::~Manager() {

    }

    // Custom deleter does nothing, because we need to shutdown later than the dependency manager
    void Manager::customDeleter() { }

    void Manager::registerHandle(Interface* handle) {
        const QString& key = handle->getKey();
        withWriteLock([&] {
            if (_handles.contains(key)) {
                qCWarning(settings_manager) << "Setting::Manager::registerHandle(): Key registered more than once, overriding: " << key;
            }
            _handles.insert(key, handle);
        });
    }

    void Manager::removeHandle(const QString& key) {
        withWriteLock([&] {
            _handles.remove(key);
        });
    }

    void Manager::loadSetting(Interface* handle) {
        const auto& key = handle->getKey();
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        overte::e2e::AvatarPreferenceBarrier::Mutation avatarMutation(_featureAvatarPreferencesBarrier,key);
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS)
        overte::e2e::ChatSettingsBarrier::Mutation chatMutation(_featureChatSettings,key);
#endif

        withWriteLock([&] {
            QVariant loadedValue = _settings[key];

            if (loadedValue.isValid()) {
                handle->setVariant(loadedValue);
            }
        });
    }


    void Manager::saveSetting(Interface* handle) {
        const auto& key = handle->getKey();
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        overte::e2e::AvatarPreferenceBarrier::Mutation avatarMutation(_featureAvatarPreferencesBarrier,key);
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS)
        overte::e2e::ChatSettingsBarrier::Mutation chatMutation(_featureChatSettings,key);
#endif

        if (handle->isSet()) {
            QVariant handleValue = handle->getVariant();

            withWriteLock([&] {
                _settings[key] = handleValue;
            });

            emit valueChanged(key, handleValue);
        } else {
            withWriteLock([&] {
                _settings.remove(key);
            });

            emit keyRemoved(key);
        }

    }

    void Manager::forceSave() {
        emit syncRequested();
    }

    void Manager::terminateThread() {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        overte::e2e::AvatarPreferenceBarrier::Mutation avatarMutation(_featureAvatarPreferencesBarrier,QString());
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS)
        overte::e2e::ChatSettingsBarrier::Mutation chatMutation(_featureChatSettings,QString());
#endif
        qCDebug(settings_manager) << "Terminating settings writer thread";

        emit terminationRequested(); // This blocks

        _workerThread.exit();
        _workerThread.wait(THREAD_TERMINATION_TIMEOUT);
        qCDebug(settings_manager) << "Settings writer terminated";
    }

    QString Manager::fileName() const {
        return resultWithReadLock<QString>([&] {
            return _fileName;
        });
    }

    void Manager::remove(const QString &key) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        overte::e2e::AvatarPreferenceBarrier::Mutation avatarMutation(_featureAvatarPreferencesBarrier,key);
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS)
        overte::e2e::ChatSettingsBarrier::Mutation chatMutation(_featureChatSettings,key);
#endif
        withWriteLock([&] {
            _settings.remove(key);
        });

        emit keyRemoved(key);
    }

    QStringList Manager::allKeys() const {
        return resultWithReadLock<QStringList>([&] {
            return _settings.keys();
        });
    }

    bool Manager::contains(const QString &key) const {
        return resultWithReadLock<bool>([&] {
            return _settings.contains(key);
        });
    }

    void Manager::setValue(const QString &key, const QVariant &value) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        overte::e2e::AvatarPreferenceBarrier::Mutation avatarMutation(_featureAvatarPreferencesBarrier,key);
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS)
        overte::e2e::ChatSettingsBarrier::Mutation chatMutation(_featureChatSettings,key);
#endif
        withWriteLock([&] {
            _settings[key] = value;
        });

        emit valueChanged(key, value);
    }

    QVariant Manager::value(const QString &key, const QVariant &defaultValue) const {
        return resultWithReadLock<QVariant>([&] {
            return _settings.value(key, defaultValue);
        });
    }

    void Manager::clearAllSettings() {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        overte::e2e::AvatarPreferenceBarrier::Mutation avatarMutation(_featureAvatarPreferencesBarrier,QString());
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS)
        overte::e2e::ChatSettingsBarrier::Mutation chatMutation(_featureChatSettings,QString());
#endif
        withWriteLock([&] {
            _settings.clear();
        });

        emit clearAllSettingsRequested();
    }
}

#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QUrl>
#include <QCryptographicHash>
#include <QDataStream>
QVariantMap Setting::Manager::featureNavigationEnvironmentEntries() const {
    if (!QCoreApplication::instance() || QThread::currentThread()!=thread()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    const QString selectedKey{"private/selectedMetaverseURL"};
    const QStringList keys{selectedKey,"placesAppPinnedMetaverse","placesAppMetaverseToFetch","placesAppMaturityFilter"};
    QVariantMap entries,other;bool valid=true;qint64 captured{0};
    const bool acquired=withTryReadLock([&] {
        for (const auto& key:keys) {
            // Never dereference an active Handle, invoke its getters or accept
            // persisted state in place of a deferred/cached runtime value.
            if (_handles.contains(key)) { valid=false;return; }
            const bool present=_settings.contains(key);const auto value=_settings.value(key);
            if (present) {
                if (key==selectedKey) {
                    if (value.userType()!=QMetaType::QString && value.userType()!=QMetaType::QUrl) { valid=false;return; }
                    const auto text=value.userType()==QMetaType::QUrl ? value.toUrl().toString(QUrl::FullyEncoded) : value.toString();
                    if (text.isEmpty() || text.size()>1024 || text.contains(QChar::Null)) { valid=false;return; }
                } else {
                    if (value.userType()!=QMetaType::QStringList && value.userType()!=QMetaType::QVariantList) { valid=false;return; }
                    if (value.userType()==QMetaType::QStringList) {
                        const auto list=value.toStringList();if (list.size()>256) { valid=false;return; }
                        for (const auto& text:list) { if (text.size()>4096 || text.contains(QChar::Null)) { valid=false;return; } }
                    } else {
                        const auto list=value.toList();if (list.size()>256) { valid=false;return; }
                        for (const auto& item:list) {
                            if (item.userType()!=QMetaType::QString || item.toString().size()>4096 || item.toString().contains(QChar::Null)) { valid=false;return; }
                        }
                    }
                }
            }
            const QVariantMap entry{{"present",present},{"value",present?value:QVariant{}},{"valueType",present?value.userType():QMetaType::UnknownType}};
            entries.insert(key,entry);if (key!=selectedKey) { other.insert(key,entry); }
        }
        captured=QDateTime::currentMSecsSinceEpoch();
    },25);
    if (!acquired || !valid || captured<=0) { return {}; }
    const auto hash=[](const QVariantMap& map) {
        QByteArray raw;QDataStream stream(&raw,QIODevice::WriteOnly);stream.setVersion(QDataStream::Qt_5_12);stream<<map;
        if (stream.status()!=QDataStream::Ok || raw.size()>65536) { return QString{}; }
        return QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex());
    };
    const auto allHash=hash(entries),otherHash=hash(other);
    if (allHash.isEmpty() || otherHash.isEmpty()) { return {}; }
    const auto selected=entries.value(selectedKey).toMap();
    return {{"navigationSettingsEntriesVersion",1},{"instance",_featureSnapshotContextInstance},{"capturedEpochMs",captured},
        {"selectedPresent",selected.value("present")},{"selectedValue",selected.value("value")},
        {"selectedType",selected.value("present").toBool() ? selected.value("valueType").toInt()==QMetaType::QUrl ? "url" : "string" : "absent"},
        {"rawSettingsSha256",allHash},{"otherSettingsSha256",otherHash},{"handlesAbsent",true}};
}
// The presence/value pattern and three keys follow the fixed Phone b62 source.
// This Pico observer adds a bounded original read lock and manager birth.
// No writer, cache initialization, endpoint setter or replacement value exists.
// Closed key names follow fixed Phone 3fa8031a. Unlike its lease, this
// observer never initializes a Handle and never restores/replaces a value.
QVariantMap Setting::Manager::featureSnapshotSettingsEntries() const {
    if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    const QStringList keys{"alsoTakeAnimatedSnapshot","snapshotFormat","previousSnapshotHref","previousSnapshotDomainID",
        "previousStillSnapPath","previousStillSnapStoryID","previousStillSnapBlastingDisabled","previousStillSnapHifiSharingDisabled","previousStillSnapUrl",
        "previousAnimatedSnapPath","previousAnimatedSnapStoryID","previousAnimatedSnapBlastingDisabled","previousAnimatedSnapHifiSharingDisabled"};
    QVariantMap entries;bool valid=true;
    const bool acquired=withTryReadLock([&] {
        for (const auto& key:keys) {
            const bool present=_settings.contains(key);const auto value=_settings.value(key);
            if (present && value.isValid() && value.userType()!=QMetaType::Bool && value.userType()!=QMetaType::QString) { valid=false;return; }
            if (value.userType()==QMetaType::QString && (value.toString().size()>4096 || value.toString().contains(QChar::Null))) { valid=false;return; }
            entries.insert(key,QVariantMap{{"present",present},{"value",present?value:QVariant{}}});
        }
    },25);
    if (!acquired || !valid) { return {}; }
    const auto captured=QDateTime::currentMSecsSinceEpoch();if (captured<=0) { return {}; }
    return {{"snapshotSettingsEntriesVersion",1},{"instance",_featureSnapshotContextInstance},{"capturedEpochMs",captured},{"entries",entries}};
}

QVariantMap Setting::Manager::featureSnapshotCaptureContext() const {
    if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    QVariantMap entries;bool valid=true;
    const bool acquired=withTryReadLock([&] {
        for (const auto& key:QStringList{"previousSnapshotDomainID","previousSnapshotHref","previousStillSnapPath"}) {
            const bool present=_settings.contains(key);const auto value=_settings.value(key);
            if (present && (value.userType()!=QMetaType::QString || value.toString().size()>4096 || value.toString().contains(QChar::Null))) { valid=false;return; }
            entries.insert(key,QVariantMap{{"present",present},{"value",present?value:QVariant{}}});
        }
    },25);
    if (!acquired || !valid) { return {}; }
    const auto captured=QDateTime::currentMSecsSinceEpoch();if (captured<=0) { return {}; }
    const auto href=entries.value("previousSnapshotHref").toMap().value("value").toString();
    return {{"snapshotCaptureContextVersion",1},{"instance",_featureSnapshotContextInstance},{"capturedEpochMs",captured},
        {"entries",entries},{"normalizedHref",QUrl(href).toString()}};
}
#endif
