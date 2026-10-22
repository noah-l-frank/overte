// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <SettingManager.h>
#include <DependencyManager.h>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDataStream>
#include <QDateTime>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMap>
#include <QRegularExpression>
#include <QThread>
#include <QSemaphore>
#include <memory>
#include <QUuid>
#include <QUrl>
#include "PrivateCreateFiles.h"
#include "CreateBrowseSettingFile.h"

namespace overte::e2e {
// One fixed actual setting. Original raw values are acquired inside the real
// Manager lock; no Setting::Handle read can insert/remove an initially absent
// key. Restore accepts no requested replacement value and never touches a
// second setting. The owner must still prove independent final restoration.
class CreateBrowseSettingOwner {
public:
    // Actual Window getPreviousBrowseLocation may coerce a raw QVariant through
    // its temporary QString Handle. Capture both originals without constructing
    // another Handle; this helper is safe on the original Script caller thread.
    static QVariantMap captureRead() {
        if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript")
                || !DependencyManager::isSet<Setting::Manager>()) {return {};}
        const auto manager=DependencyManager::get<Setting::Manager>();if (!manager) {return {};}
        QVariantMap observed;manager->withReadLock([&]{observed=raw(manager->_settings.contains(key()),manager->_settings.value(key()));});
        return observed.isEmpty() ? QVariantMap{} : QVariantMap{{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"raw",observed}};
    }
    QVariantMap request(const QString& privateRoot,const QVariantMap& command,const QVariantMap& dialogs) {
        if (!enabled() || !_valid || !DependencyManager::isSet<Setting::Manager>()) {return {};}
        const auto json=QJsonObject::fromVariantMap(command);
        const auto run=command.value("runId").toString(),owner=command.value("ownerToken").toString();
        const auto operation=command.value("operation").toString();
        QStringList wanted {"schemaVersion","commandId","action","operation","runId","ownerToken"};
        if ((operation=="claim" || operation=="claim-read")) {wanted.append({"ticket","fileOwnerToken","dialogBinding"});}wanted.sort();
        if (command.keys()!=wanted || json.value("schemaVersion")!=QJsonValue(1)
                || json.value("action")!=QJsonValue("feature-create-browse-setting")
                || !identifier(command.value("commandId")) || !identifier(command.value("runId"))
                || command.value("ownerToken").userType()!=QMetaType::QString || !digest(owner)
                || command.value("operation").userType()!=QMetaType::QString
                || !QStringList{"reserve","observe","claim","claim-read","restore","release"}.contains(operation)) {return {};}
        const auto manager=DependencyManager::get<Setting::Manager>();if (!manager) {return {};}
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (epoch<=0 || epoch<_epoch) {_valid=false;return {};}_epoch=epoch;
        if (operation=="reserve") {
            if (_leases.contains(run) || _leases.size()>=4) {return {};}
            Lease lease;lease.writer=manager->_featureBrowseWriteWorkerBirth;lease.owner=owner;lease.id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');lease.created=epoch;
            manager->withReadLock([&]{lease.present=manager->_settings.contains(key());lease.original=manager->_settings.value(key());});
            lease.originalRow=raw(lease.present,lease.original);if (lease.originalRow.isEmpty()) {return {};}
            _leases.insert(run,lease);
            // Flush the original writer's pending real signals before the
            // bounded reserve barrier captures the physical starting row.
            // Observe never flushes: an independent foreign physical change
            // must remain visible even when the original cache still agrees.
            manager->forceSave();
        }
        if (!_leases.contains(run) || _leases[run].owner!=owner) {return {};}
        auto& lease=_leases[run];
        if (lease.writer.isEmpty() || lease.writer!=manager->_featureBrowseWriteWorkerBirth) {return {};}
        if (lease.released && operation!="observe") {return {};}
        if ((operation=="claim" || operation=="claim-read")) {
            if (lease.restoreAttempted || (operation=="claim" ? lease.claims.size()>=4 : lease.reads.size()>=4) || !identifier(command.value("ticket"))
                    || command.value("fileOwnerToken").userType()!=QMetaType::QString || !digest(command.value("fileOwnerToken").toString())
                    || command.value("dialogBinding").userType()!=QMetaType::QVariantMap) {return {};}
            const auto binding=command.value("dialogBinding").toMap();
            QStringList fields {"bindingVersion","sourceInstance","dialogId","rootId","listenerId","contextId","windowId","role"};fields.sort();
            if (binding.keys()!=fields || binding.value("bindingVersion")!=QVariant(1)
                    || dialogs.value("createDialogSourceVersion")!=QVariant(3) || dialogs.value("complete")!=QVariant(true)
                    || binding.value("sourceInstance")!=dialogs.value("instance") || !identifier(binding.value("dialogId"))) {return {};}
            QVariantMap selected;
            for (const auto& item:dialogs.value("dialogs").toList()) {if (item.toMap().value("id")==binding.value("dialogId")) {selected=item.toMap();}}
            if (selected.isEmpty() || selected.value("dispatches")!=QVariant(0)
                    || selected.value("registeredEpochMs").toLongLong()<lease.created) {return {};}
            if (operation=="claim" && (selected.value("pending")!=QVariant(false)
                    || selected.value("returnedEpochMs").toLongLong()<lease.created)) {return {};}
            if (operation=="claim-read" && (selected.value("pending")!=QVariant(true)
                    || selected.value("rootAlive")!=QVariant(true) || selected.value("listenerAlive")!=QVariant(true))) {return {};}
            for (const auto& field:QStringList{"rootId","listenerId","contextId","windowId","role"}) {
                if (binding.value(field)!=selected.value(field)) {return {};}
            }
            const auto role=binding.value("role").toString();if (role!="import" && role!="export") {return {};}
            for (const auto& prior:(operation=="claim" ? lease.claims : lease.reads)) {if (prior.toMap().value("dialogId")==binding.value("dialogId")) {return {};}}
            const QVariantMap locate {{"schemaVersion",1},{"commandId",command.value("commandId")},{"action","feature-script-files"},
                {"sourceRole","create-json-v1"},{"operation","locate"},{"runId",run},{"ticket",command.value("ticket")},{"ownerToken",command.value("fileOwnerToken")}};
            const auto location=PrivateCreateFiles::request(privateRoot,locate);
            const auto url=QUrl(location.value("directory").toString());
            if (location.value("exists")!=QVariant(true) || url.scheme()!="file" || !url.authority().isEmpty() || url.hasQuery() || url.hasFragment()) {return {};}
            if (operation=="claim-read") {
                const auto read=selected.value("browseSettingRead").toMap();
                const auto before=read.value("before").toMap(),after=read.value("after").toMap();
                if (read.size()!=2 || before.size()!=2 || after.size()!=2
                        || before.value("capturedEpochMs").toLongLong()<lease.created
                        || after.value("capturedEpochMs").toLongLong()<before.value("capturedEpochMs").toLongLong()
                        || after.value("capturedEpochMs").toLongLong()>selected.value("registeredEpochMs").toLongLong()
                        || before.value("raw").toMap()!=(lease.lastOwnedRow.isEmpty() ? lease.originalRow : lease.lastOwnedRow)) {return {};}
                QVariant actual;bool present=false;
                manager->withReadLock([&]{present=manager->_settings.contains(key());actual=manager->_settings.value(key());});
                const auto measured=raw(present,actual);if (measured.isEmpty() || measured!=after.value("raw").toMap()) {return {};}
                lease.lastOwned=actual;lease.lastOwnedRow=measured;
                lease.reads.append(QVariantMap{{"dialogId",binding.value("dialogId")},{"sourceInstance",binding.value("sourceInstance")},
                    {"ticket",command.value("ticket")},{"role",role},{"read",read},{"claimedEpochMs",epoch}});
            } else {
            bool readKnown=false;for (const auto& item:lease.reads) {const auto prior=item.toMap();
                if (prior.value("dialogId")==binding.value("dialogId") && prior.value("ticket")==command.value("ticket")) {readKnown=true;}}
            if (!readKnown) {return {};}
            const auto path=url.toLocalFile();const auto selectedPath=path+(role=="import" ? "/entity-import.json" : "/export.json");
            const auto responseHash=QString::fromLatin1(QCryptographicHash::hash(selectedPath.toUtf8(),QCryptographicHash::Sha256).toHex());
            if (selected.value("responseSha256")!=QVariant(responseHash)) {return {};}
            QVariant actual;bool present=false;
            manager->withReadLock([&]{present=manager->_settings.contains(key());actual=manager->_settings.value(key());});
            if (!present || actual.userType()!=QMetaType::QString || actual.toString()!=path) {return {};}
            const auto measured=raw(present,actual);if (measured.isEmpty()) {return {};}
            lease.lastOwned=actual;lease.lastOwnedRow=measured;
            lease.claims.append(QVariantMap{{"dialogId",binding.value("dialogId")},{"sourceInstance",binding.value("sourceInstance")},
                {"ticket",command.value("ticket")},{"role",role},{"responseSha256",responseHash},{"setting",measured},
                {"registeredEpochMs",selected.value("registeredEpochMs")},{"returnedEpochMs",selected.value("returnedEpochMs")},{"claimedEpochMs",epoch}});
            }
        } else if (operation=="restore") {
            if (lease.restoreAttempted || (lease.claims.isEmpty() && lease.reads.isEmpty()) || lease.lastOwnedRow.isEmpty()) {return {};}
            lease.restoreAttempted=true;bool restored=false;
            // This is an atomic CAS in the actual original manager, including
            // presence and raw QVariant type/bytes. A live cached Handle could
            // later overwrite restoration; refuse it rather than rewrite it.
            manager->withWriteLock([&]{
                const auto current=raw(manager->_settings.contains(key()),manager->_settings.value(key()));
                if (manager->_handles.contains(key()) || current!=lease.lastOwnedRow) {return;}
                if (lease.present) {manager->_settings[key()]=lease.original;}else {manager->_settings.remove(key());}
                restored=true;
            });
            if (!restored) {return {};}
            if (lease.present) {emit manager->valueChanged(key(),lease.original);}else {emit manager->keyRemoved(key());}
            lease.restored=true;manager->forceSave();
        } else if (operation=="release") {
            bool same=false;manager->withReadLock([&]{same=raw(manager->_settings.contains(key()),manager->_settings.value(key()))==lease.originalRow;});
            const auto written=writer(manager.data());
            if (!same || written.value("raw").toMap()!=lease.originalRow || !createBrowsePhysicalOriginal(lease.originalPhysical,written.value("physical").toMap()) || (!lease.claims.isEmpty() && !lease.restored)
                    || dialogs.value("complete")!=QVariant(true)) {return {};}
            for (const auto& prior:lease.reads+lease.claims) {
                const auto claim=prior.toMap();if (claim.value("sourceInstance")!=dialogs.value("instance")) {return {};}
                QVariantMap original;
                for (const auto& item:dialogs.value("dialogs").toList()) {if (item.toMap().value("id")==claim.value("dialogId")) {original=item.toMap();}}
                if (original.isEmpty() || original.value("pending")!=QVariant(false) || original.value("dispatches")!=QVariant(0)
                        || original.value("listenerAlive")!=QVariant(false) || original.value("rootAlive")!=QVariant(false)
                        || original.value("contextAlive")!=QVariant(false)) {return {};}
            }
            lease.released=true;
        }
        QVariantMap current;manager->withReadLock([&]{current=raw(manager->_settings.contains(key()),manager->_settings.value(key()));});
        const auto written=writer(manager.data());
        if (current.isEmpty() || written.isEmpty()) {return {};}
        if (operation=="reserve") {
            if (written.value("raw").toMap()!=lease.originalRow) {return {};}
            lease.originalPhysical=written.value("physical").toMap();
        }
        if (lease.originalPhysical.isEmpty()) {return {};}
        return {{"createBrowseSettingVersion",3},{"leaseId",lease.id},{"runId",run},{"createdEpochMs",lease.created},
            {"original",lease.originalRow},{"originalPhysical",lease.originalPhysical},{"current",current},{"writer",written},{"claims",lease.claims},{"reads",lease.reads},
            {"owned",lease.lastOwnedRow.isEmpty() ? lease.originalRow : lease.lastOwnedRow},{"restoreAttempted",lease.restoreAttempted},
            {"restored",lease.restored},{"released",lease.released}};
    }
private:
    struct WriterRead {
        QSemaphore ready;QVariantMap value;QPointer<Setting::WriteWorker> worker;
    };
    QVariantMap writer(Setting::Manager* manager) {
        if (!enabled()) {return {};}
        if (_writerRead) {
            if (!_writerRead->worker || _writerRead->ready.tryAcquire(1,0)) {
                // A late old barrier cannot observe signals queued by this
                // request. Discard its original result; never retime/adopt it.
                _writerRead.reset();
            } else {return {};}
        }
        if (!manager || !manager->_workerThread.isRunning() || !manager->_featureBrowseWriteWorker) {return {};}
        const QPointer<Setting::WriteWorker> worker=manager->_featureBrowseWriteWorker;
        const auto birth=manager->_featureBrowseWriteWorkerBirth;
        const auto read=std::make_shared<WriterRead>();read->worker=worker;
        _writerRead=read; // One bounded queued observation, retained on timeout.
        const bool invoked=QMetaObject::invokeMethod(worker.data(),[worker,birth,read]{
            QVariantMap observed;
            if (worker && QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript")
                    && QThread::currentThread()==worker->thread()) {
                worker->init();
                if (worker->_qSettings->status()==QSettings::NoError) {
                    const auto value=raw(worker->_qSettings->contains(key()),worker->_qSettings->value(key()));
                    const auto physical=createBrowseSettingsFile(worker->_qSettings->fileName(),worker->_qSettings->format());
                    if (!value.isEmpty() && !physical.isEmpty()) {observed={{"id",birth},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"raw",value},{"physical",physical}};}
                }
            }
            read->value=observed;read->ready.release();
        },Qt::QueuedConnection);
        if (!invoked) {_writerRead.reset();return {};}
        if (!read->ready.tryAcquire(1,250)) {return {};}
        _writerRead.reset();return read->value;
    }
    static QString key() {return QStringLiteral("LastBrowseLocation");}
    static bool enabled() {return QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread()
        && QCoreApplication::arguments().contains("--testScript");}
    static bool identifier(const QVariant& value) {return value.userType()==QMetaType::QString
        && QRegularExpression("\\A[0-9a-f]{32}\\z").match(value.toString()).hasMatch();}
    static bool digest(const QString& value) {return QRegularExpression("\\A[0-9a-f]{64}\\z").match(value).hasMatch();}
    static QVariantMap raw(bool present,const QVariant& value) {
        QByteArray bytes;QDataStream stream(&bytes,QIODevice::WriteOnly);stream.setVersion(QDataStream::Qt_5_15);stream<<value;
        if (stream.status()!=QDataStream::Ok || bytes.size()>8192) {return {};}
        return {{"present",present},{"typeId",value.userType()},{"typeName",value.typeName() ? QVariant(QString::fromLatin1(value.typeName())) : QVariant()},
            {"base64",QString::fromLatin1(bytes.toBase64())},{"sha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())},
            {"stringValue",present && value.userType()==QMetaType::QString ? QVariant(value.toString()) : QVariant()}};
    }
    struct Lease {
        QString id,owner,writer;bool present {false},restoreAttempted {false},restored {false},released {false};qint64 created {0};
        QVariant original,lastOwned;QVariantMap originalRow,lastOwnedRow,originalPhysical;QVariantList claims,reads;
    };
    std::shared_ptr<WriterRead> _writerRead;
    QMap<QString,Lease> _leases;bool _valid {true};qint64 _epoch {0};
};
} // namespace overte::e2e
#endif
