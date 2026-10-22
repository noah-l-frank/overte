// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <QChar>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QFile>
#include <QHttpMultiPart>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QMutex>
#include <QMutexLocker>
#include <QNetworkReply>
#include <QUuid>
#include <QVariantMap>
#include <memory>
#include <sys/stat.h>
#include <unistd.h>

namespace overte::e2e {
// Passive process-lifetime provenance. There is no reset, URL setter, request
// sender, cancellation input or success verdict. Overflow stays unavailable.
class PhoneSnapshotUploadEvidence {
public:
    static PhoneSnapshotUploadEvidence& get() { static auto* value=new PhoneSnapshotUploadEvidence;return *value; }
    static bool enabled() { return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript"); }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static QString sha(const QByteArray& raw) { return QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex()); }
    QString begin(QObject* uploader,const QString& path,const QUrl& href) {
        if (!enabled()) { return {}; }
        QMutexLocker lock(&_mutex);if (!_complete || _jobs.size()>=32) { _complete=false;return {}; }
        const auto id=nonce();
        _jobs.insert(id,{{"id",id},{"path",path},{"href",href.toString(QUrl::FullyEncoded)},
            {"uploaderAlive",true},{"fileAlive",false},{"multipartAlive",false},{"file",QVariantMap{}},
            {"cancelRequested",false},{"terminal",QString()},{"requests",QVariantList{}}});
        event(id,"begin");
        QObject::connect(uploader,&QObject::destroyed,[id] { get().change(id,"uploaderAlive",false,"uploader-destroyed"); });
        return id;
    }
    void change(const QString& id,const QString& key,const QVariant& value,const QString& kind) {
        if (id.isEmpty()) { return; }QMutexLocker lock(&_mutex);
        if (!_jobs.contains(id)) { _complete=false;return; }_jobs[id][key]=value;event(id,kind);
    }
    void file(const QString& id,QFile* source) {
        if (id.isEmpty()) { return; }QMutexLocker lock(&_mutex);
        struct stat info{};const auto bytes=source->size();QCryptographicHash hash(QCryptographicHash::Sha256);
        if (!_jobs.contains(id) || bytes<=0 || bytes>32*1024*1024 || ::fstat(source->handle(),&info)!=0
                || !S_ISREG(info.st_mode) || info.st_nlink!=1 || info.st_uid!=::geteuid() || (info.st_mode&0777)!=0600) { _complete=false;return; }
        QByteArray raw(65536,Qt::Uninitialized);qint64 offset=0;
        while (offset<bytes) {
            const auto count=::pread(source->handle(),raw.data(),qMin<qint64>(raw.size(),bytes-offset),offset);
            if (count<=0) { _complete=false;return; }hash.addData(QByteArray::fromRawData(raw.constData(),count));offset+=count;
        }
        struct stat after{};
        if (::fstat(source->handle(),&after)!=0 || info.st_dev!=after.st_dev || info.st_ino!=after.st_ino || info.st_size!=after.st_size) { _complete=false;return; }
        _readHashes.insert(id,std::make_shared<QCryptographicHash>(QCryptographicHash::Sha256));
        _jobs[id]["fileAlive"]=true;
        _jobs[id]["file"]=QVariantMap{{"bytes",bytes},{"sha256",QString::fromLatin1(hash.result().toHex())},
            {"device",static_cast<qulonglong>(info.st_dev)},{"inode",static_cast<qulonglong>(info.st_ino)},
            {"readBytes",0},{"readSha256",sha({})}};event(id,"file-open");
    }
    void consumed(const QString& id,const char* raw,qint64 bytes) {
        if (id.isEmpty() || bytes<=0) { return; }QMutexLocker lock(&_mutex);
        if (!_readHashes.contains(id)) { _complete=false;return; }
        auto file=_jobs[id]["file"].toMap();const auto total=file["readBytes"].toLongLong()+bytes;
        if (total>32*1024*1024) { _complete=false;return; }
        _readHashes[id]->addData(QByteArray::fromRawData(raw,bytes));file["readBytes"]=total;
        file["readSha256"]=QString::fromLatin1(_readHashes[id]->result().toHex());_jobs[id]["file"]=file;
    }
    void multipart(const QString& id,QHttpMultiPart* value) {
        if (id.isEmpty()) { return; }change(id,"multipartAlive",true,"multipart-created");
        QObject::connect(value,&QObject::destroyed,[id] { get().change(id,"multipartAlive",false,"multipart-destroyed"); });
    }
    void request(const QString& id,const QString& stage,QNetworkReply* reply,const QNetworkRequest& request,
            bool required,const QByteArray& body,QHttpMultiPart* multi,bool current) {
        if (id.isEmpty() || !enabled()) { return; }QMutexLocker lock(&_mutex);
        if (!_jobs.contains(id) || !reply || (stage!="image" && stage!="story")) { _complete=false;return; }
        const auto requestId=nonce();auto rows=_jobs[id]["requests"].toList();
        if (rows.size()>=4) { _complete=false;return; }
        rows.append(QVariantMap{{"id",requestId},{"stage",stage},{"url",request.url().toString(QUrl::FullyEncoded)},
            {"operation",static_cast<int>(reply->operation())},{"authRequired",required},{"authorizationPresent",request.hasRawHeader("Authorization")},
            {"multipart",bool(multi)},{"boundary",multi ? QString::fromLatin1(multi->boundary()) : QString()},
            {"jsonBytes",body.size()},{"jsonSha256",sha(body)},{"dispatchCurrent",current},
            {"sentBytes",0},{"totalBytes",0},{"finished",false},{"destroyed",false},{"status",0},{"networkError",0},
            {"responseId",QString()},{"replyBytes",0},{"replySha256",sha({})},{"replyBase64",QString()}});
        _jobs[id]["requests"]=rows;event(id,"request-created");
        QObject::connect(reply,&QNetworkReply::uploadProgress,reply,[id,requestId](qint64 sent,qint64 total) {
            get().updateRequest(id,requestId,[&](QVariantMap& row) { row["sentBytes"]=sent;row["totalBytes"]=total; },"upload-progress");
        });
        // This is installed before AccountManager's ticket/receiver callbacks,
        // so cancellation cannot hide an actual terminal network result.
        QObject::connect(reply,&QNetworkReply::finished,reply,[id,requestId,reply] {
            const auto raw=reply->isOpen() ? reply->peek(16385) : QByteArray();
            get().updateRequest(id,requestId,[&](QVariantMap& row) {
                row["finished"]=true;row["status"]=reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
                row["networkError"]=static_cast<int>(reply->error());row["responseId"]=QString::fromLatin1(reply->rawHeader("X-Overte-Fixture-Response"));
                row["replyBytes"]=raw.size();row["replySha256"]=sha(raw);row["replyBase64"]=QString::fromLatin1(raw.toBase64());
            },raw.size()>16384 ? "reply-overflow" : "reply-finished");
        });
        QObject::connect(reply,&QObject::destroyed,[id,requestId] {
            get().updateRequest(id,requestId,[](QVariantMap& row) { row["destroyed"]=true; },"reply-destroyed");
        });
    }
    QVariantMap snapshot() {
        if (!enabled()) { return {}; }QMutexLocker lock(&_mutex);QVariantList jobs;
        for (auto it=_jobs.begin();it!=_jobs.end();++it) { jobs.append(it.value()); }
        return {{"snapshotUploadObservationVersion",1},{"instance",_instance},{"complete",_complete},
            {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"sequence",_events.size()},{"events",_events},{"jobs",jobs}};
    }
private:
    template<class F> void updateRequest(const QString& id,const QString& request,F update,const QString& kind) {
        QMutexLocker lock(&_mutex);auto rows=_jobs[id]["requests"].toList();bool found=false;
        for (int index=0;index<rows.size();++index) { auto row=rows[index].toMap();if (row["id"]==request) { update(row);rows[index]=row;found=true;break; } }
        if (!found || kind=="reply-overflow") { _complete=false;return; }_jobs[id]["requests"]=rows;event(id,kind);
    }
    void event(const QString& id,const QString& kind) {
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (_events.size()>=256 || now<=0 || now<_epoch) { _complete=false;return; }_epoch=now;
        _events.append(QVariantMap{{"sequence",_events.size()+1},{"jobId",id},{"kind",kind},{"capturedEpochMs",now}});
    }
    QMutex _mutex;QString _instance{nonce()};QMap<QString,QVariantMap> _jobs;
    QMap<QString,std::shared_ptr<QCryptographicHash>> _readHashes;QVariantList _events;bool _complete{true};qint64 _epoch{0};
};

class PhoneSnapshotUploadFile : public QFile {
public:
    PhoneSnapshotUploadFile(const QString& path,const QString& job):QFile(path),_job(job) {}
    ~PhoneSnapshotUploadFile() override { if (!_job.isEmpty()) { PhoneSnapshotUploadEvidence::get().change(_job,"fileAlive",false,"file-destroyed"); } }
protected:
    qint64 readData(char* data,qint64 maximum) override {
        const auto bytes=QFile::readData(data,maximum);PhoneSnapshotUploadEvidence::get().consumed(_job,data,bytes);return bytes;
    }
private:QString _job;
};

inline QVariantMap phoneSnapshotUploadObservation(const QVariantMap& command,const QString& instance,quint64& sequence) {
    const auto json=QJsonObject::fromVariantMap(command);QStringList keys{"schemaVersion","commandId","action","runId"};keys.sort();
    const QRegularExpression nonce("\\A[0-9a-f]{32}\\z");
    if (!PhoneSnapshotUploadEvidence::enabled() || command.keys()!=keys || json.value("schemaVersion")!=QJsonValue(1)
            || json.value("action")!=QJsonValue("phone-snapshot-upload-observe") || !json.value("commandId").isString()
            || !nonce.match(json.value("commandId").toString()).hasMatch() || !json.value("runId").isString()
            || !nonce.match(json.value("runId").toString()).hasMatch() || sequence>=9007199254740991ULL) { return {}; }
    const auto requested=QDateTime::currentMSecsSinceEpoch();const auto source=PhoneSnapshotUploadEvidence::get().snapshot();
    if (source.isEmpty() || QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size()>200000) { return {}; }
    return {{"schemaVersion",1},{"requestId",command.value("commandId")},{"runId",command.value("runId")},
        {"instance",instance},{"sequence",static_cast<qulonglong>(++sequence)},{"processId",QCoreApplication::applicationPid()},
        {"requestedEpochMs",requested},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"source",source}};
}
} // namespace overte::e2e
#endif
