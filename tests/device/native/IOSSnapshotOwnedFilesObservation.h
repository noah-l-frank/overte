// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "NativeReadBracket.h"
#include "IOSSnapshotCaptureObservation.h"
#include "IOSSnapshotFileWorkObservation.h"
#include "../../../ios/ui/IOSSnapshotFiles.h"
#include <QDir>
#include <QJsonArray>
#include <QFileInfo>
#include <QMutex>
#include <QMutexLocker>
#include <exception>
#include <memory>

namespace overte::e2e {
// Authority is made only by actual native operands: an empty list, a later
// original list row and a matching actual capture-status path. The wire cannot
// supply a filename, directory, file metadata or replacement authority.
class IOSSnapshotOwnedFilesObservation {
public:
    struct Token {QString command;};
    using Responsibility=std::shared_ptr<Token>;
    static IOSSnapshotOwnedFilesObservation& instance() {static auto* value=new IOSSnapshotOwnedFilesObservation;return *value;}
    static bool command(const QVariantMap& value,bool remove=false) {
        QStringList fields{"schemaVersion","commandId","action","runId"};if (remove) {fields<<"fileId"<<"manifestCommandId";}fields.sort();
        const auto json=QJsonObject::fromVariantMap(value);
        return enabled() && value.keys()==fields && json.value("schemaVersion")==QJsonValue(1)
            && json.value("action")==QJsonValue(remove?QStringLiteral("feature-ios-snapshot-file-remove"):QStringLiteral("feature-ios-snapshot-owned-files"))
            && matches("ios-[0-9a-f]{32}",json.value("commandId")) && matches("[0-9a-f]{32}",json.value("runId"))
            && (!remove || matches("[0-9a-f]{32}",json.value("fileId")) && matches("ios-[0-9a-f]{32}",json.value("manifestCommandId")));
    }
    void observed(const QJsonObject& query,const QJsonObject& result,const QString& actualRoot) {
        if (!enabled() || query.value("operation")!=QJsonValue("list") || !overte::ios::validSnapshotFileRequest(query)
                || result.value("ok")!=QJsonValue(true) || result.value("commandId")!=query.value("commandId")) {return;}
        QMutexLocker guard(&_mutex);if (!_complete) {return;}
        const auto prefix=query.value("prefix").toString();const auto epoch=result.value("sampleEpochMs").toVariant().toLongLong();
        if (actualRoot.isEmpty() || !QDir::isAbsolutePath(actualRoot) || epoch<=0 || epoch<_epoch || !result.value("files").isArray()) {_complete=false;return;}
        _epoch=epoch;
        if (!_prefixes.contains(prefix)) {
            if (_prefixes.size()>=128) {_complete=false;return;}
            _prefixes[prefix]={actualRoot,query.toVariantMap(),epoch,result.value("files").toArray().isEmpty()};
        }
        const auto& admission=_prefixes[prefix];if (admission.root!=actualRoot) {_complete=false;return;}
        if (!admission.empty) {return;} // Pre-existing user output is never adopted.
        for (const auto& value:result.value("files").toArray()) {
            if (!value.isObject()) {_complete=false;return;}const auto row=value.toObject().toVariantMap();
            const auto name=row.value("name").toString(),key=prefix+"/"+name;
            const auto witness=IOSSnapshotCaptureObservation::instance().fileWitness(QDir(actualRoot).absoluteFilePath(name),admission.epoch);
            if (witness.isEmpty()) {_complete=false;return;}
            // A processing output may still change. Keep its actual manifest
            // responsibility with the caller and admit a stable native row
            // only after the actual capture/resources and terminal work end.
            if (!witness.value("nativeDrained").toBool() || witness.value("terminal").toString().isEmpty()) {continue;}
            auto immutable=witness;immutable.remove("nativeDrained");immutable.remove("terminal");
            if (_byName.contains(key)) {
                const auto& old=_files[_byName[key]];
                if (old.row!=row || old.witness!=immutable) {_complete=false;return;}
                continue;
            }
            if (_files.size()>=128) {_complete=false;return;}
            File owned;owned.id=nonce();owned.prefix=prefix;owned.root=actualRoot;owned.row=row;
            owned.witness=immutable;owned.manifest=query.toVariantMap();owned.observed=epoch;
            _byName[key]=owned.id;_files[owned.id]=owned;
        }
    }
    Responsibility queued(const QVariantMap& query) {
        if (!command(query,true)) {return {};}
        QMutexLocker guard(&_mutex);const auto file=query.value("fileId").toString(),id=query.value("commandId").toString();
        if (!_complete || _jobs.contains(id) || _jobs.size()>=128 || !_files.contains(file)) {return {};}
        auto& owned=_files[file];
        if (!owned.prefix.startsWith("parity-"+query.value("runId").toString().left(16)+"-")
                || owned.manifest.value("commandId")!=query.value("manifestCommandId") || !owned.job.isEmpty()) {return {};}
        const auto witness=IOSSnapshotCaptureObservation::instance().fileWitness(QDir(owned.root).absoluteFilePath(owned.row.value("name").toString()),
            _prefixes[owned.prefix].epoch);
        auto immutable=witness;immutable.remove("nativeDrained");immutable.remove("terminal");
        if (immutable!=owned.witness || !witness.value("nativeDrained").toBool() || witness.value("terminal").toString().isEmpty()
                || !IOSSnapshotFileWorkObservation::instance().allReadJobsRetired()) {return {};}
        auto actual=std::make_shared<Token>();actual->command=id;Job job;job.query=query;job.actual=actual;job.queued=stamp();
        if (!_complete) {return {};}
        _jobs[id]=job;owned.job=id;return actual;
    }
    class Body {
    public:
        explicit Body(const Responsibility& actual):_actual(actual),_exceptions(std::uncaught_exceptions()) {instance().entered(actual);}
        ~Body() {instance().finished(_actual,std::uncaught_exceptions()==_exceptions);}
        Body(const Body&)=delete;Body& operator=(const Body&)=delete;
    private:Responsibility _actual;int _exceptions;
    };
    void perform(const Responsibility& actual) {
        if (!actual) {return;}QVariantMap row;QString root;
        {
            QMutexLocker guard(&_mutex);auto& job=_jobs[actual->command];
            if (!_complete || !job.entered || !job.result.isEmpty() || job.finished) {_complete=false;return;}
            const auto& owned=_files[job.query.value("fileId").toString()];
            const auto witness=IOSSnapshotCaptureObservation::instance().fileWitness(
                QDir(owned.root).absoluteFilePath(owned.row.value("name").toString()),_prefixes[owned.prefix].epoch);
            auto immutable=witness;immutable.remove("nativeDrained");immutable.remove("terminal");
            if (immutable!=owned.witness || !witness.value("nativeDrained").toBool()
                    || witness.value("terminal").toString().isEmpty()
                    || !IOSSnapshotFileWorkObservation::instance().allReadJobsRetired()) {_complete=false;return;}
            row=owned.row;root=owned.root;
        }
        const auto result=overte::ios::removeObservedSnapshotFile(QJsonObject::fromVariantMap(row),root).toVariantMap();
        QMutexLocker guard(&_mutex);auto& job=_jobs[actual->command];job.result=result;
        const auto sampled=result.value("sampleEpochMs").toLongLong();
        if (sampled<job.entered || sampled<_epoch) {_complete=false;}else {_epoch=sampled;}
    }
    QVariantMap read(const QString& request,const QString& run) {
        return _bracket.read("iosSnapshotOwnedFilesVersion","native-main-snapshot-owned-files",request,run,[&]() -> QVariantMap {
            QMutexLocker guard(&_mutex);QVariantList prefixes,files,jobs;
            for (auto it=_prefixes.cbegin();it!=_prefixes.cend();++it) {
                if (it.key().startsWith("parity-"+run.left(16)+"-")) {
                    const auto& original=it.value();prefixes.append(QVariantMap{{"prefix",it.key()},{"query",original.query},
                        {"sampleEpochMs",original.epoch},{"initiallyEmpty",original.empty}});
                }
            }
            for (const auto& owned:_files) {
                if (!owned.prefix.startsWith("parity-"+run.left(16)+"-")) {continue;}
                const auto witness=IOSSnapshotCaptureObservation::instance().fileWitness(QDir(owned.root).absoluteFilePath(owned.row.value("name").toString()),
                    _prefixes[owned.prefix].epoch);
                auto immutable=witness;immutable.remove("nativeDrained");immutable.remove("terminal");
                if (immutable!=owned.witness) {_complete=false;}
                files.append(QVariantMap{{"id",owned.id},{"prefix",owned.prefix},{"file",owned.row},{"capture",witness},
                    {"manifestQuery",owned.manifest},{"observedEpochMs",owned.observed},{"removeCommandId",owned.job}});
            }
            for (auto it=_jobs.begin();it!=_jobs.end();++it) {
                auto& job=it.value();if (job.query.value("runId")!=run) {continue;}
                const bool alive=!job.actual.expired();if (!alive && !job.expired) {job.expired=stamp();if (!job.finished) {_complete=false;}}
                jobs.append(QVariantMap{{"query",job.query},{"queuedEpochMs",job.queued},{"enteredEpochMs",optional(job.entered)},
                    {"returnedEpochMs",optional(job.returned)},{"finallyEpochMs",optional(job.finished)},{"expiredEpochMs",optional(job.expired)},
                    {"alive",alive},{"result",job.result.isEmpty()?QVariant():QVariant(job.result)}});
            }
            QVariantMap source{{"complete",_complete},{"prefixes",prefixes},{"files",files},{"jobs",jobs}};
            if (QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size()>240000) {_complete=false;return {};}
            return source;
        });
    }
private:
    struct Prefix {QString root;QVariantMap query;qint64 epoch;bool empty;};
    struct File {QString id,prefix,root,job;QVariantMap row,witness,manifest;qint64 observed{0};};
    struct Job {QVariantMap query,result;std::weak_ptr<Token> actual;qint64 queued{0},entered{0},returned{0},finished{0},expired{0};};
    static QString nonce() {return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    static bool enabled() {return QCoreApplication::arguments().contains("--testScript");}
    static bool matches(const QString& pattern,const QJsonValue& value) {
        return value.isString() && QRegularExpression("\\A(?:"+pattern+")\\z").match(value.toString()).hasMatch();
    }
    static QVariant optional(qint64 value) {return value?QVariant(value):QVariant();}
    qint64 stamp() {const auto epoch=QDateTime::currentMSecsSinceEpoch();if (epoch<=0 || epoch<_epoch) {_complete=false;}_epoch=epoch;return epoch;}
    void entered(const Responsibility& actual) {
        if (!actual) {return;}QMutexLocker guard(&_mutex);auto& job=_jobs[actual->command];
        if (job.entered || job.finished) {_complete=false;return;}job.entered=stamp();
    }
    void finished(const Responsibility& actual,bool returned) {
        if (!actual) {return;}QMutexLocker guard(&_mutex);auto& job=_jobs[actual->command];
        if (!job.entered || job.finished) {_complete=false;return;}
        if (returned) {job.returned=stamp();}job.finished=stamp();
    }
    NativeReadBracket _bracket;QMutex _mutex;QMap<QString,Prefix> _prefixes;QMap<QString,File> _files;QMap<QString,QString> _byName;
    QMap<QString,Job> _jobs;bool _complete{true};qint64 _epoch{0};
};
}
#endif
