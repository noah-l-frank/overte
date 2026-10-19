// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "PrivateAccountOrigin.h"
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QObject>
#include <QRegularExpression>
#include <QSet>
#include <QMap>
#include <QStringList>
#include <QThread>
#include <QVariantMap>
#include <cerrno>

namespace overte::e2e {
class AccountOriginLease final : public QObject {
public:
    AccountOriginLease(QObject* parent,const QString& instance) : QObject(parent),_instance(instance) {}
    QVariantMap request(const QString& directory,const QVariantMap& command) {
#if defined(Q_OS_UNIX)
        if (QThread::currentThread()!=thread()) { return {}; }
        const auto json=QJsonObject::fromVariantMap(command);
        auto fields=json.keys();fields.sort();
        const auto operation=json.value("operation").toString();
        QStringList wanted{"action","commandId","instance","operation","ownerToken","runId","schemaVersion"};
        if (operation=="stage") { wanted.append("origin");wanted.sort(); }
        const auto id=json.value("commandId").toString(),run=json.value("runId").toString(),owner=json.value("ownerToken").toString();
        if (fields!=wanted || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble()!=1
                || json.value("action").toString()!="feature-account-origin" || json.value("instance").toString()!=_instance
                || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{64}\\z").match(owner).hasMatch()
                || (operation!="stage" && operation!="observe" && operation!="release")) { return {}; }
        if (id==_lastCommand.value("commandId").toString()) { return command==_lastCommand ? _lastResult : QVariantMap(); }
        if (_used.contains(id) || _used.size()>=65536 || (operation=="stage" && _used.size()>=65472)) { return {}; }
        _used.insert(id); // An uncertain stage/write must never be replayed.
        const auto requested=QDateTime::currentMSecsSinceEpoch();
        if (requested<=0 || requested<_lastEpoch) { return {}; }
        const QFileInfo root(QDir(directory).absolutePath());
        if (root.canonicalFilePath()!=root.absoluteFilePath()) { return {}; }
        Handle base(::open(QFile::encodeName(root.absoluteFilePath()).constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
        struct stat rootInfo;
        if (!privateNode(base.fd,true,&rootInfo) || !sameRoot(base.fd,root.absoluteFilePath())) { return {}; }
        if (_root.isEmpty()) { _root=root.absoluteFilePath();_device=rootInfo.st_dev;_inode=rootInfo.st_ino; }
        if (_root!=root.absoluteFilePath() || _device!=rootInfo.st_dev || _inode!=rootInfo.st_ino) { return {}; }
        const auto key=run+':'+owner;
        QByteArray original,manifestRaw;bool originMissing=false,ownerMissing=false;
        struct stat originInfo,ownerInfo;
        if (!readOriginal(base.fd,originName(),original,originMissing,&originInfo) || !readOriginal(base.fd,ownerName(),manifestRaw,ownerMissing,&ownerInfo)) { return {}; }
        QVariantMap source;
        if (operation=="stage") {
            const auto origin=json.value("origin");
            if (!origin.isString() || !accountOriginText(origin.toString()) || !originMissing || !ownerMissing
                    || _retired.contains(key) || _retired.size()>=255) { return {}; }
            const QJsonObject config{{"schemaVersion",1},{"runId",run},{"origin",origin}};
            const auto bytes=QJsonDocument(config).toJson(QJsonDocument::Compact)+'\n';
            const QJsonObject manifest{{"schemaVersion",1},{"runId",run},{"ownerToken",owner},
                {"instance",_instance},{"originSha256",digest(bytes)}};
            // Persist native file ownership before writing the actual config.
            // Partial/changed files are never silently adopted or overwritten.
            if (!writeNew(base.fd,ownerName(),QJsonDocument(manifest).toJson(QJsonDocument::Compact)+'\n',key)
                    || ::fsync(base.fd) || !writeNew(base.fd,originName(),bytes,key) || ::fsync(base.fd)) { return {}; }
            source={{"performed",true}};
        } else {
            if (operation=="release") {
                if (!_retired.contains(key) && _retired.size()>=256) { return {}; }
                _retired.insert(key); // Includes an undelivered intent; later stage cannot recreate it.
            }
            // Native creation inode + successful write counts, followed by an
            // independent actual-byte reread, authorize only these originals.
            // This also covers an interrupted/zero-byte write; a matching path
            // or even a copied valid manifest cannot adopt a different inode.
            if ((!originMissing && !issued(originName(),key,originInfo,original))
                    || (!ownerMissing && !issued(ownerName(),key,ownerInfo,manifestRaw))) { return {}; }
            const bool removeIssued=operation=="release";
            if (!removeIssued && ownerMissing && !originMissing) { return {}; }
            if (!removeIssued && !ownerMissing) {
                QJsonParseError error;const auto doc=QJsonDocument::fromJson(manifestRaw,&error);const auto manifest=doc.object();
                const auto sha=manifest.value("originSha256").toString();
                if (error.error!=QJsonParseError::NoError || !doc.isObject() || manifest.size()!=5
                        || manifestRaw!=doc.toJson(QJsonDocument::Compact)+'\n'
                        || manifest.value("schemaVersion")!=QJsonValue(1) || manifest.value("runId")!=QJsonValue(run)
                        || manifest.value("ownerToken")!=QJsonValue(owner) || manifest.value("instance")!=QJsonValue(_instance)
                        || !QRegularExpression("\\A[0-9a-f]{64}\\z").match(sha).hasMatch()
                        || (!originMissing && (digest(original)!=sha || privateAccountOrigin(directory,run).isEmpty()))) { return {}; }
            }
            if (operation=="release") {
                if ((!originMissing && ::unlinkat(base.fd,originName(),0))
                        || (!ownerMissing && ::unlinkat(base.fd,ownerName(),0)) || ::fsync(base.fd)) { return {}; }
                _issued.remove(originName());_issued.remove(ownerName());
                source={{"performed",true}}; // Independent observe must still prove both absences.
            } else {
                source={{"originExists",!originMissing},{"ownerExists",!ownerMissing},
                    {"originBytes",original.size()},{"originSha256",digest(original)},
                    {"originBase64",QString::fromLatin1(original.toBase64())},
                    {"ownerBytes",manifestRaw.size()},{"ownerSha256",digest(manifestRaw)},{"retired",_retired.contains(key)}};
            }
        }
        if (!sameRoot(base.fd,root.absoluteFilePath())) { return {}; }
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (requested<=0 || now<requested || now<_lastEpoch || _sequence>=9007199254740991ULL) { return {}; }
        _lastEpoch=now;_lastCommand=command;
        _lastResult={{"originVersion",1},{"commandId",id},{"instance",_instance},{"runId",run},{"operation",operation},
            {"processId",QCoreApplication::applicationPid()},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"requestedEpochMs",requested},{"capturedEpochMs",now},{"source",source}};
        return _lastResult;
#else
        Q_UNUSED(directory)
        Q_UNUSED(command)
        return {};
#endif
    }
private:
    static QString digest(const QByteArray& bytes) { return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()); }
#if defined(Q_OS_UNIX)
    struct Handle { int fd; explicit Handle(int value):fd(value) {} ~Handle() { if (fd>=0) { ::close(fd); } }
        Handle(const Handle&)=delete;Handle& operator=(const Handle&)=delete; };
    static const char* originName() { return "feature-account-origin.v1.json"; }
    static const char* ownerName() { return ".feature-account-origin-owner.v1.json"; }
    static bool privateNode(int fd,bool directory,struct stat* output=nullptr) {
        struct stat info;
        if (fd<0 || ::fstat(fd,&info) || info.st_uid!=::geteuid() || (info.st_mode&0777)!=(directory?0700:0600)
                || (directory ? !S_ISDIR(info.st_mode) : !S_ISREG(info.st_mode)||info.st_nlink!=1)) { return false; }
        if (output) { *output=info; }return true;
    }
    static bool sameRoot(int fd,const QString& path) {
        struct stat opened,current;
        return privateNode(fd,true,&opened) && !::lstat(QFile::encodeName(path).constData(),&current)
            && S_ISDIR(current.st_mode) && current.st_dev==opened.st_dev && current.st_ino==opened.st_ino
            && current.st_uid==::geteuid() && (current.st_mode&0777)==0700;
    }
    static bool readOriginal(int base,const char* name,QByteArray& raw,bool& missing,struct stat* observed=nullptr) {
        Handle file(::openat(base,name,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC));
        if (file.fd<0) { missing=errno==ENOENT;return missing; }
        missing=false;struct stat before,after,path;
        if (!privateNode(file.fd,false,&before) || before.st_size<0 || before.st_size>4096) { return false; }
        char data[4097];
        while (raw.size()<=4096) {
            const auto count=::read(file.fd,data,4097-raw.size());
            if (count<0) { return false; }if (!count) { break; }raw.append(data,static_cast<int>(count));
        }
        if (observed) { *observed=before; }
        return raw.size()<=4096 && privateNode(file.fd,false,&after) && !::fstatat(base,name,&path,AT_SYMLINK_NOFOLLOW)
            && S_ISREG(path.st_mode) && path.st_dev==before.st_dev && path.st_ino==before.st_ino
            && path.st_uid==::geteuid() && (path.st_mode&0777)==0600 && path.st_nlink==1
            && after.st_size==before.st_size && path.st_size==after.st_size && raw.size()==after.st_size;
    }
    struct IssuedFile { QString key;dev_t device;ino_t inode;QByteArray written; };
    bool issued(const char* name,const QString& key,const struct stat& observed,const QByteArray& actual) const {
        const auto found=_issued.constFind(name);
        return found!=_issued.cend() && found->key==key && found->device==observed.st_dev
            && found->inode==observed.st_ino && found->written==actual;
    }
    bool writeNew(int base,const char* name,const QByteArray& raw,const QString& key) {
        Handle file(::openat(base,name,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600));
        struct stat created;
        if (file.fd<0 || ::fchmod(file.fd,0600) || !privateNode(file.fd,false,&created)) { return false; }
        _issued.insert(name,IssuedFile{key,created.st_dev,created.st_ino,{}});
        auto& record=_issued[name];
        int offset=0;
        while (offset<raw.size()) { const auto count=::write(file.fd,raw.constData()+offset,raw.size()-offset);
            if (count<=0) { return false; }
            record.written.append(raw.constData()+offset,static_cast<int>(count));offset+=static_cast<int>(count); }
        return !::fsync(file.fd);
    }
    QMap<QByteArray,IssuedFile> _issued;
    dev_t _device {};ino_t _inode {};
#endif
    QString _instance,_root;QSet<QString> _used,_retired;quint64 _sequence {0};qint64 _lastEpoch {0};
    QVariantMap _lastCommand,_lastResult;
};
} // namespace overte::e2e
