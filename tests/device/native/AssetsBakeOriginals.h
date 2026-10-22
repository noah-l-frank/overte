// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_UNIX)
#include <QCoreApplication>
#include <QDateTime>
#include <QJsonDocument>
#include <QMutex>
#include <QMutexLocker>
#include <QVariantMap>
#include <QUuid>
#include <QFile>
#include <QThread>
#include <sys/file.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>

namespace overte::e2e {
// Measurement only. No reference to a worker, server mapping or product callback
// is retained. Missing/inconsistent writes make the fixture source unavailable.
class AssetsBakeOriginals {
public:
    AssetsBakeOriginals() {
        const auto directory=qgetenv("OVERTE_E2E_ASSETS_ORIGINALS");
        if (directory.isEmpty()) { return; }
        _root=::open(directory.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
        struct stat root{};
        if (_root<0 || ::fstat(_root,&root) || root.st_uid!=::geteuid() || (root.st_mode&0777)!=0700) { return; }
        _device=root.st_dev;_inode=root.st_ino;
        _file=::openat(_root,"assets-bakes.json",O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW|O_CLOEXEC,0600);
        struct stat file{};if (_file<0 || ::fstat(_file,&file)) { return; }_fileDevice=file.st_dev;_fileInode=file.st_ino;_enabled=true;
    }
    ~AssetsBakeOriginals() { if (_file>=0) { ::close(_file); }if (_root>=0) { ::close(_root); } }
    bool enabled() const { return _enabled; }
    QString begin(const QString& hash,const QString& path,int version) {
        if (!_enabled) { return {}; }QMutexLocker lock(&_mutex);
        if (_jobs.size()>=64) { _valid=false;return {}; }
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        _jobs.append(QVariantMap{{"instance",id},{"hash",hash},{"path",path},{"version",version},{"queuedEpochMs",now()},
            {"startedEpochMs",QVariant()},{"runExitedEpochMs",QVariant()},{"ovenProcessId",QVariant()},{"ovenFinishedEpochMs",QVariant()},{"exitCode",QVariant()},
            {"exitStatus",QVariant()},{"terminalEpochMs",QVariant()},{"outcome",QVariant()},{"destroyedEpochMs",QVariant()}});return id;
    }
    void event(const QString& instance,const QString& kind,qint64 process=0,int code=0,int status=0) {
        if (instance.isEmpty()) { return; }QMutexLocker lock(&_mutex);
        for (auto& raw:_jobs) { auto row=raw.toMap();if (row.value("instance")!=instance) { continue; }
            if (kind=="started") { if (!row.value("startedEpochMs").isNull()) { _valid=false;return; }row["startedEpochMs"]=now(); }
            else if (kind=="oven") { if (process<=0 || row.value("startedEpochMs").isNull() || !row.value("ovenProcessId").isNull()) { _valid=false;return; }row["ovenProcessId"]=process; }
            else if (kind=="oven-finished") { if (row.value("ovenProcessId").isNull() || !row.value("ovenFinishedEpochMs").isNull()) { _valid=false;return; }row["ovenFinishedEpochMs"]=now();row["exitCode"]=code;row["exitStatus"]=status; }
            else if (kind=="run-exited") { if (row.value("startedEpochMs").isNull() || !row.value("runExitedEpochMs").isNull()) { _valid=false;return; }row["runExitedEpochMs"]=now(); }
            else if (kind=="destroyed") { if (!row.value("destroyedEpochMs").isNull()) { _valid=false;return; }row["destroyedEpochMs"]=now(); }
            else { if (!row.value("terminalEpochMs").isNull() || (kind!="complete" && kind!="failed" && kind!="aborted")) { _valid=false;return; }row["terminalEpochMs"]=now();row["outcome"]=kind; }
            raw=row;return;
        }_valid=false;
    }
    void invalidate() { QMutexLocker lock(&_mutex);_valid=false; }
    QString current(const QString& hash) const { QMutexLocker lock(&_mutex);for (auto it=_jobs.crbegin();it!=_jobs.crend();++it) { const auto row=it->toMap();if (row.value("hash")==hash && row.value("terminalEpochMs").isNull()) { return row.value("instance").toString(); } }return {}; }
    // Called on the actual AssetServer assignment owner thread. Maps and stored
    // blob metadata are copied there; worker events use the same snapshot lock.
    void publish(const QString& domain,const QString& server,const QVariantList& mappings,const QVariantList& blobs,int pending,qint64 contextEpoch) {
        if (!_enabled) { return; }QMutexLocker lock(&_mutex);struct stat root{},file{},path{};
        if (contextEpoch<=0 || contextEpoch>now() || now()-contextEpoch>1500) { return; }
        if (::fstat(_root,&root) || root.st_dev!=_device || root.st_ino!=_inode || root.st_uid!=::geteuid() || (root.st_mode&0777)!=0700
                || ::fstat(_file,&file) || ::fstatat(_root,"assets-bakes.json",&path,AT_SYMLINK_NOFOLLOW)
                || !S_ISREG(path.st_mode) || file.st_dev!=_fileDevice || file.st_ino!=_fileInode || path.st_dev!=_fileDevice || path.st_ino!=_fileInode
                || path.st_uid!=::geteuid() || path.st_nlink!=1 || (path.st_mode&0777)!=0600 || _sequence>=1000000000) { _valid=false;return; }
        QFile proc("/proc/self/stat");QString start;if (proc.open(QIODevice::ReadOnly)) { const auto data=proc.readAll();const auto fields=data.mid(data.lastIndexOf(')')+2).split(' ');if (fields.size()>19) { start=fields[19]; } }
        const QVariantMap packet{{"assetsBakeOriginalsVersion",2},{"instance",_instance},{"sequence",++_sequence},{"processId",QCoreApplication::applicationPid()},
            {"processStart",start},{"domainId",domain},{"assetServerId",server},{"capturedEpochMs",now()},{"contextCapturedEpochMs",contextEpoch},{"valid",_valid},
            {"jobs",_jobs},{"mappings",mappings},{"blobs",blobs},{"pending",pending}};
        const auto bytes=QJsonDocument::fromVariant(packet).toJson(QJsonDocument::Compact);
        if (bytes.size()>1048576) { _valid=false;return; }
        if (::flock(_file,LOCK_EX|LOCK_NB)) { return; }
        bool ok=::ftruncate(_file,0)==0 && ::lseek(_file,0,SEEK_SET)==0;qsizetype offset=0;
        while (ok && offset<bytes.size()) { const auto n=::write(_file,bytes.constData()+offset,bytes.size()-offset);if (n<=0) { ok=false; }else { offset+=n; } }
        ok=ok && ::fsync(_file)==0;::flock(_file,LOCK_UN);if (!ok) { _valid=false; }
    }
private:
    static qint64 now() { return QDateTime::currentMSecsSinceEpoch(); }
    mutable QMutex _mutex;QVariantList _jobs;const QString _instance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
    bool _enabled{false},_valid{true};int _root{-1},_file{-1};dev_t _device{},_fileDevice{};ino_t _inode{},_fileInode{};quint64 _sequence{0};
};
}
#endif
