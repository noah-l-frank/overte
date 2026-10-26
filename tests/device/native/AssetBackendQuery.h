// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "AssetBackendFiles.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_LINUX)
#include <QSet>
#include <QTimer>
#include <QPair>
#include <functional>

namespace overte::e2e::asset_backend {
// One already owned AssetServer publishes immutable original observations.
// This object starts no process and never mutates product files or settings.
class QuerySource : public QObject {
public:
    QuerySource(QObject* server,std::function<QJsonObject()> sample,std::function<QString()> dataset,std::function<QPair<QString,QString>()> nodes)
        : QObject(server),_server(server),_sample(std::move(sample)),_dataset(std::move(dataset)),_nodes(std::move(nodes)) {}
    bool start(const QString& dataRoot,const QString& serverId,const QString& domainId) {
        const auto& config=configuration();
        if (!Work::enabled() || !config.current() || !_server || _server->thread()!=QThread::currentThread()
                || !separate(config.root,dataRoot) || QUuid(serverId).isNull() || QUuid(domainId).isNull()) {return false;}
        _serverId=serverId;_domainId=domainId;
        Directory data(dataRoot);if (!data.valid()) {return false;}
        _dataRoot=QFileInfo(dataRoot).canonicalFilePath();const auto dataIdentity=data.source().value("identity").toObject();
        _dataDevice=dataIdentity.value("device").toString();_dataInode=dataIdentity.value("inode").toString();
        const auto root=QFile::encodeName(config.root);_fd=::open(root.constData(),O_RDONLY|O_CLOEXEC|O_DIRECTORY|O_NOFOLLOW|O_NONBLOCK);
        if (!current()) {return false;}
        const auto admission=QJsonObject{{"assetBackendAdmissionVersion",1},{"instance",_instance},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"role","asset-server"},{"ownerSha256",config.ownerSha256},{"serverId",serverId},{"domainId",domainId},
            {"sourceRootIdentity",QJsonObject{{"device",QString::number(config.device)},{"inode",QString::number(config.inode)}}},
            {"dataRoot",_dataRoot},{"dataRootIdentity",QJsonObject{{"device",_dataDevice},{"inode",_dataInode}}},
            {"clockDomain","asset-server-native"},{"clock",Work::shared().clock()}};
        const auto raw=QJsonDocument(admission).toJson(QJsonDocument::Compact);QJsonObject original;
        if (!write("asset-backend-admission.json",raw,original)) {return false;}
        _admissionSha256=QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex());
        auto timer=new QTimer(this);timer->setInterval(100);_timer=timer;
        QObject::connect(timer,&QTimer::timeout,this,[this] {poll();});timer->start();return true;
    }
    void stop() {if (_timer) {_timer->stop();}}
    ~QuerySource() {if (_fd>=0) {::close(_fd);}}
private:
    bool current() const {
        if (_fd<0 || !configuration().current() || !_server || _server->thread()!=QThread::currentThread()
                || QFileInfo(_dataset()).canonicalFilePath()!=_dataRoot || !separate(configuration().root,_dataRoot)) {return false;}
        const auto nodes=_nodes();if (nodes.first!=_serverId || nodes.second!=_domainId) {return false;}
        struct stat actual{},data{};const auto dataPath=QFile::encodeName(_dataRoot);
        return ::fstat(_fd,&actual)==0 && S_ISDIR(actual.st_mode) && actual.st_uid==::geteuid() && (actual.st_mode&0777)==0700
            && static_cast<quint64>(actual.st_dev)==configuration().device && static_cast<quint64>(actual.st_ino)==configuration().inode
            && ::lstat(dataPath.constData(),&data)==0 && S_ISDIR(data.st_mode) && data.st_uid==::geteuid()
            && QString::number(static_cast<qulonglong>(data.st_dev))==_dataDevice && QString::number(static_cast<qulonglong>(data.st_ino))==_dataInode;
    }
    bool write(const QString& leaf,const QByteArray& raw,QJsonObject& record) {
        if (!current() || raw.isEmpty() || raw.size()>2*1024*1024 || leaf.contains('/') || leaf.contains(QChar(0))) {return false;}
        const auto name=QFile::encodeName(leaf);const auto fd=::openat(_fd,name.constData(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK,0600);
        if (fd<0) {return false;}struct stat before{};bool valid=::fstat(fd,&before)==0 && S_ISREG(before.st_mode) && before.st_nlink==1
            && before.st_uid==::geteuid() && (before.st_mode&0777)==0600;qint64 offset=0;
        while (valid && offset<raw.size()) {
            const auto count=::write(fd,raw.constData()+offset,static_cast<size_t>(raw.size()-offset));
            if (count<0 && errno==EINTR) {continue;}if (count<=0) {valid=false;break;}offset+=count;
        }
        struct stat after{},path{};
        valid=valid && ::fsync(fd)==0 && ::fstat(fd,&after)==0 && ::fstatat(_fd,name.constData(),&path,AT_SYMLINK_NOFOLLOW)==0
            && after.st_dev==before.st_dev && after.st_ino==before.st_ino && after.st_size==raw.size() && sameFile(after,path)
            && S_ISREG(after.st_mode) && after.st_uid==::geteuid() && after.st_nlink==1 && (after.st_mode&0777)==0600;
        ::close(fd);if (!valid || ::fsync(_fd)!=0 || !current()) {return false;}
        record={{"file",leaf},{"identity",identity(after)},{"sha256",QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex())}};return true;
    }
    void poll() {
        if (!current() || !_server || _server->thread()!=QThread::currentThread() || _seen.size()>=2048) {stop();return;}
        Directory root(configuration().root);bool complete=true;qint64 budget=4096;
        const auto input=root.file("asset-backend-query.json",4096,budget,complete);
        if (!complete || input.value("exists")!=QJsonValue(true) || input.value("identity").toObject().value("mode")!=QJsonValue(QString::number(0600))) {return;}
        const auto body=input.value("body").toObject();if (body.value("retained")!=QJsonValue(true)) {return;}
        const auto raw=QByteArray::fromBase64(body.value("base64").toString().toLatin1());QJsonParseError error;
        const auto document=QJsonDocument::fromJson(raw,&error);const auto query=document.object();
        const QSet<QString> expected{"schemaVersion","commandId","action","runId","ticket","processId","instance"};const auto keys=query.keys();
        const auto request=query.value("commandId").toString();
        if (error.error!=QJsonParseError::NoError || !document.isObject() || document.toJson(QJsonDocument::Compact)!=raw
                || QSet<QString>(keys.begin(),keys.end())!=expected || query.value("schemaVersion")!=QJsonValue(1)
                || query.value("action")!=QJsonValue("feature-assets-backend-observe") || query.value("instance")!=QJsonValue(_instance)
                || query.value("processId")!=QJsonValue(static_cast<double>(QCoreApplication::applicationPid()))
                || !QRegularExpression("\\Aassets-[0-9a-f]{32}\\z").match(request).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(query.value("runId").toString()).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(query.value("ticket").toString()).hasMatch() || _seen.contains(request)) {return;}
        _seen.insert(request);QJsonObject intent;
        if (!write("asset-backend-query-"+request+".json",raw,intent)) {return;}
        const auto before=Work::shared().clock();const auto actual=_sample();const auto after=Work::shared().clock();
        const auto packet=QJsonObject{{"assetBackendObservationVersion",1},{"requestId",request},{"instance",_instance},{"sequence",static_cast<double>(++_sequence)},
            {"runId",query.value("runId")},{"ticket",query.value("ticket")},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"ownerSha256",configuration().ownerSha256},{"serverId",_serverId},{"domainId",_domainId},{"admissionSha256",_admissionSha256},
            {"clockDomain","asset-server-native"},{"clockBefore",before},{"clockAfter",after},{"source",actual}};
        const auto bytes=QJsonDocument(packet).toJson(QJsonDocument::Compact);QJsonObject original;
        if (!write("asset-backend-original-"+request+".json",bytes,original)) {return;}
        const auto saved=QJsonObject{{"assetBackendSavedVersion",1},{"instance",_instance},{"requestId",request},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"admissionSha256",_admissionSha256},{"original",original}};QJsonObject receipt;
        write("asset-backend-saved-"+request+".json",QJsonDocument(saved).toJson(QJsonDocument::Compact),receipt);
    }
    QPointer<QObject> _server;QPointer<QTimer> _timer;std::function<QJsonObject()> _sample;std::function<QString()> _dataset;int _fd{-1};
    std::function<QPair<QString,QString>()> _nodes;
    QString _instance{nonce()},_serverId,_domainId,_admissionSha256,_dataRoot,_dataDevice,_dataInode;QSet<QString> _seen;
    quint64 _sequence{0};
};
}
#endif
