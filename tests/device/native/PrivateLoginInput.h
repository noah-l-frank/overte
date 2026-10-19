// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "PrivateAccountOrigin.h"
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QHash>
#include <QJsonArray>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <functional>
#include <cerrno>
#include <cmath>
#include <memory>

namespace overte::e2e {
#if defined(OVERTE_E2E_FEATURE_TESTS)
// The only payload carrier is an exclusively native-created app-private file.
// Public commands and receipts contain metadata only. GUI input is supplied by
// the platform's actual normal-input owner, never by a requested feature state.
class PrivateLoginInput {
public:
    using Perform=std::function<QJsonObject(const QJsonObject&,const QString&)>;
    PrivateLoginInput() : _thread(QThread::currentThread()), _instance(QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')) { _clock.start(); }

    QJsonObject request(const QString& directory,const QJsonObject& command,const Perform& perform) {
        if (_busy || QThread::currentThread()!=_thread || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
        const QSet<QString> fields{"schemaVersion","commandId","action","operation","runId","inputId"};
        const auto keys=command.keys();const auto operation=command.value("operation").toString();
        const auto run=command.value("runId").toString();const auto id=command.value("inputId").toString();
        const auto nonce=command.value("commandId").toString();
        const auto hex=[](const QString& value) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch(); };
        if (QSet<QString>(keys.begin(),keys.end())!=fields || command.value("schemaVersion")!=QJsonValue(1)
                || command.value("action")!=QJsonValue("feature-private-login-input")
                || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(nonce).hasMatch() || !hex(run) || !hex(id)
                || (operation!="inspect" && operation!="reserve" && operation!="deliver" && operation!="retire")) { return {}; }
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (now<=0 || now<_epoch) { return {}; } _epoch=now;
        QJsonObject result{{"inputVersion",1},{"commandId",nonce},{"operation",operation},{"runId",run},{"inputId",id},
            {"instance",_instance},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"capturedEpochMs",static_cast<double>(now)},{"elapsedMs",static_cast<double>(_clock.elapsed())},
            {"sequence",static_cast<double>(++_sequence)},{"available",false}};
#if defined(Q_OS_UNIX)
        Handle root{openRoot(directory)};
        if (root.fd<0) { return result; }
        const auto name=filename(id);const auto rawName=QFile::encodeName(name);
        auto iterator=_leases.find(id);
        if (iterator!=_leases.end() && iterator->run!=run) { return result; }
        if (operation=="reserve") {
            if (iterator==_leases.end()) {
                if (_leases.size()>=4032 || (!_active.isEmpty() && _active!=id)) { return result; }
                const auto origin=privateAccountOrigin(directory,run);
                struct stat existing;
                if (origin.isEmpty() || !::fstatat(root.fd,rawName.constData(),&existing,AT_SYMLINK_NOFOLLOW) || errno!=ENOENT) { return result; }
                Lease lease;lease.run=run;lease.origin=origin;
                Handle file{::openat(root.fd,rawName.constData(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600)};
                if (file.fd<0 || ::fchmod(file.fd,0600) || ::fstat(file.fd,&lease.original) || !valid(lease.original)) { return result; }
                lease.originalFd=std::shared_ptr<Handle>(new Handle{file.fd});file.fd=-1;
                lease.reserved=true;iterator=_leases.insert(id,lease);_active=id;
            }
            if (iterator->retired || !iterator->reserved) { return result; }
        } else if (operation=="retire") {
            if (iterator==_leases.end()) {
                if (_leases.size()>=4096) { return result; }
                Lease lease;lease.run=run;lease.retired=true;iterator=_leases.insert(id,lease);
            }
            iterator->retired=true; // Suppress delayed reservation/delivery before file cleanup.
            if (!removeOriginal(root.fd,rawName,iterator.value()) || !closeOriginal(iterator.value())) { return result; }
            if (_active==id) { _active.clear(); }
        } else if (operation=="deliver") {
            if (iterator==_leases.end() || !iterator->reserved || iterator->retired || iterator->attempted || _active!=id) { return result; }
            iterator->attempted=true; // Never replay an uncertain normal input.
            QJsonObject status;
            {
                QByteArray raw;
                if (!readOriginal(root.fd,rawName,iterator.value(),raw) || raw.isEmpty()) { return result; }
                QJsonParseError error;const auto document=QJsonDocument::fromJson(raw,&error);
                const auto payload=document.object();const auto payloadKeys=payload.keys();
                if (error.error!=QJsonParseError::NoError || !document.isObject()
                        || QSet<QString>(payloadKeys.begin(),payloadKeys.end())!=QSet<QString>{"schemaVersion","runId","inputId","input"}
                        || payload.value("schemaVersion")!=QJsonValue(1) || payload.value("runId")!=QJsonValue(run)
                        || payload.value("inputId")!=QJsonValue(id) || !payload.value("input").isObject()
                        || raw!=document.toJson(QJsonDocument::Compact)+'\n'
                        || privateAccountOrigin(directory,run)!=iterator->origin || !perform) { return result; }
                const auto input=payload.value("input").toObject();const auto inputKeys=input.keys();
                const QSet<QString> privateFields{"schemaVersion","commandId","instance","sequence","observedElapsedMs","fieldToken","operation","text"};
                const auto uuid=[](const QJsonValue& value) { const auto text=value.toString();return !QUuid(text).isNull()
                    && QUuid(text).toString(QUuid::WithoutBraces)==text; };
                const auto integer=[](const QJsonValue& value,bool positive) { const auto number=value.toDouble(-1);
                    return value.isDouble() && std::isfinite(number) && std::floor(number)==number
                        && number>=(positive ? 1 : 0) && number<=9007199254740991.0; };
                const auto text=input.value("text").toString();
                if (QSet<QString>(inputKeys.begin(),inputKeys.end())!=privateFields || input.value("schemaVersion")!=QJsonValue(1)
                        || input.value("operation")!=QJsonValue("replace") || !uuid(input.value("commandId"))
                        || !uuid(input.value("instance")) || !uuid(input.value("fieldToken"))
                        || !integer(input.value("sequence"),true) || !integer(input.value("observedElapsedMs"),false)
                        || !input.value("text").isString() || text.isEmpty() || text.size()>4096) { return result; }
                for (const auto character:text) { if (character.unicode()<0x20 || character.unicode()>0x7e) { return result; } }
                QByteArray reread;
                if (!readOriginal(root.fd,rawName,iterator.value(),reread) || raw!=reread
                        || !removeOriginal(root.fd,rawName,iterator.value())) { return result; }
                Handle currentRoot{openRoot(directory)};
                if (currentRoot.fd<0) { return result; }
                _busy=true;
                struct Pending { bool& busy; ~Pending() { busy=false; } } pending{_busy};
                status=perform(input,iterator->origin);
                const auto statusKeys=status.keys();
                if (QSet<QString>(statusKeys.begin(),statusKeys.end())!=QSet<QString>{"schemaVersion","commandId","instance","sequence","performed","processId","sampleEpochMs"}
                        || status.value("schemaVersion")!=QJsonValue(1) || status.value("commandId")!=input.value("commandId")
                        || status.value("instance")!=input.value("instance") || status.value("sequence")!=input.value("sequence")
                        || !status.value("performed").isBool() || status.value("processId")!=QJsonValue(static_cast<double>(QCoreApplication::applicationPid()))
                        || !integer(status.value("sampleEpochMs"),true)) { status={}; }
            } // Parsed credentials/raw input cease to be retained before any receipt.
            iterator->status=status;
        }
        struct stat current;const bool present=!::fstatat(root.fd,rawName.constData(),&current,AT_SYMLINK_NOFOLLOW);
        if (!present && errno!=ENOENT) { return result; }
        const bool known=iterator!=_leases.end();
        const bool owned=present && known && iterator->reserved && valid(current)
            && same(current,iterator->original);
        QJsonObject state{{"reserved",known && iterator->reserved},{"retired",known && iterator->retired},
            {"attempted",known && iterator->attempted},{"filePresent",present},{"fileOwned",owned},{"pending",_busy},
            {"openFiles",known && iterator->originalFd && iterator->originalFd->fd>=0 ? 1 : 0}};
        // This is original native GUI delivery metadata only, not an auth result.
        if (known && !iterator->status.isEmpty()) { state["inputStatus"]=iterator->status; }
        result["available"]=true;result["source"]=state;
#else
        Q_UNUSED(directory) Q_UNUSED(perform)
#endif
        const auto captured=QDateTime::currentMSecsSinceEpoch();
        if (captured<now) { result["available"]=false;result.remove("source");return result; }
        _epoch=captured;result["capturedEpochMs"]=static_cast<double>(captured);
        result["elapsedMs"]=static_cast<double>(_clock.elapsed());return result;
    }

    static QString filename(const QString& id) { return "feature-login-input-"+id+".v1.json"; }

private:
#if defined(Q_OS_UNIX)
    struct Handle { int fd; ~Handle() { if (fd>=0) { ::close(fd); } } };
    struct Lease { QString run,origin;struct stat original{};std::shared_ptr<Handle> originalFd;
        bool reserved{false},retired{false},attempted{false};QJsonObject status; };
    static bool valid(const struct stat& value) { return S_ISREG(value.st_mode) && value.st_uid==::geteuid()
        && (value.st_mode&0777)==0600 && value.st_nlink==1 && value.st_size>=0 && value.st_size<=16384; }
    static bool same(const struct stat& a,const struct stat& b) { return a.st_dev==b.st_dev && a.st_ino==b.st_ino; }
    int openRoot(const QString& directory) {
        const QFileInfo info(QDir(directory).absolutePath());
        if (info.canonicalFilePath()!=info.absoluteFilePath()) { return -1; }
        const int fd=::open(QFile::encodeName(info.absoluteFilePath()).constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
        struct stat current,path;
        if (fd<0) { return -1; }
        if (::fstat(fd,&current) || ::lstat(QFile::encodeName(info.absoluteFilePath()).constData(),&path)
                || !S_ISDIR(current.st_mode) || !S_ISDIR(path.st_mode) || current.st_uid!=::geteuid()
                || path.st_uid!=::geteuid() || (current.st_mode&0777)!=0700 || (path.st_mode&0777)!=0700 || !same(current,path)
                || (_rootSet && (!same(current,_root) || _directory!=info.absoluteFilePath()))) { ::close(fd);return -1; }
        _root=current;_directory=info.absoluteFilePath();_rootSet=true;return fd;
    }
    static bool readOriginal(int root,const QByteArray& name,const Lease& lease,QByteArray& raw) {
        Handle input{::openat(root,name.constData(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC)};
        struct stat before,after,path;
        if (!lease.reserved || !lease.originalFd || lease.originalFd->fd<0 || input.fd<0 || ::fstat(input.fd,&before) || !valid(before) || !same(before,lease.original)) { return false; }
        char data[4096];while (raw.size()<=16384) {
            const auto count=::read(input.fd,data,sizeof(data));if (count<0) { return false; }if (!count) { break; }
            raw.append(data,static_cast<int>(count));
        }
        return raw.size()<=16384 && !::fstat(input.fd,&after) && !::fstatat(root,name.constData(),&path,AT_SYMLINK_NOFOLLOW)
            && valid(after) && valid(path) && same(before,after) && same(before,path) && before.st_size==after.st_size
            && raw.size()==after.st_size && before.st_mtime==after.st_mtime && before.st_ctime==after.st_ctime;
    }
    static bool removeOriginal(int root,const QByteArray& name,const Lease& lease) {
        struct stat current;
        const bool exists=!::fstatat(root,name.constData(),&current,AT_SYMLINK_NOFOLLOW);
        if (!exists && errno!=ENOENT) { return false; }
        // Cleanup may remove its own original after failed oversized/mode
        // writes, never a replacement, different owner or linked copy.
        if (exists && (!lease.reserved || !S_ISREG(current.st_mode) || current.st_uid!=::geteuid()
                || current.st_nlink!=1 || !same(current,lease.original) || ::unlinkat(root,name.constData(),0))) { return false; }
        // Keep the original descriptor through retirement to prevent inode
        // recycling from adopting a foreign copy. Truncate its actual backing
        // storage after unlink, before any GUI callback or cleanup receipt.
        if (lease.originalFd && lease.originalFd->fd>=0) {
            if (::fstat(lease.originalFd->fd,&current) || !same(current,lease.original)
                    || ::ftruncate(lease.originalFd->fd,0)) { return false; }
            if (::fstat(lease.originalFd->fd,&current) || current.st_size!=0) { return false; }
        }
        return ::fstatat(root,name.constData(),&current,AT_SYMLINK_NOFOLLOW)<0 && errno==ENOENT;
    }
    static bool closeOriginal(Lease& lease) {
        if (!lease.originalFd || lease.originalFd->fd<0) { return true; }
        const int fd=lease.originalFd->fd;
        if (!::close(fd)) { lease.originalFd->fd=-1;return true; }
        struct stat current;
        // Never retry close against a descriptor number already reused by
        // another thread. An unresolved original remains a cleanup failure.
        const int observed=::fstat(fd,&current);
        if (observed<0) {
            if (errno!=EBADF) { return false; }
            lease.originalFd->fd=-1;return true;
        }
        if (!same(current,lease.original)) { lease.originalFd->fd=-1;return true; }
        return false;
    }
    QHash<QString,Lease> _leases;
    struct stat _root{};bool _rootSet {false};QString _directory,_active;
#endif
    QThread* _thread;QString _instance;QElapsedTimer _clock;quint64 _sequence{0};qint64 _epoch{0};bool _busy{false};
};
#endif
} // namespace overte::e2e
