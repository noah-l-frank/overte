// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_LINUX)
#include <QCoreApplication>
#include <QDateTime>
#include <QJsonDocument>
#include <QMutex>
#include <QMutexLocker>
#include <QVariantMap>
#include <QUuid>
#include <QFile>
#include <QThread>
#include <QDir>
#include <QFileInfo>
#include <QCryptographicHash>
#include <cerrno>
#include <sys/file.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>

namespace overte::e2e {
// Linux UAPI F_LINUX_SPECIFIC_BASE+3. Older NDK headers omit the name;
// the actual kernel query below still has to prove the original OFD alias.
#if defined(F_DUPFD_QUERY)
static constexpr int PICO_ASSETS_F_DUPFD_QUERY=F_DUPFD_QUERY;
#else
static constexpr int PICO_ASSETS_F_DUPFD_QUERY=1027;
#endif
// A recycled same-inode descriptor is foreign. Missing kernel query support
// refuses admission; there is no inode-only fallback or uncertain force-close.
class PicoAssetsOriginalDescriptor {
public:
    bool open(const char* path,int flags,int mode=0) {
        if (_fd>=0 || _anchor>=0 || _lost) { return false; }
        _fd=::open(path,flags,mode);
        if (_fd<0) { return false; }
        _anchor=::fcntl(_fd,F_DUPFD_CLOEXEC,0);
        struct stat info{};
        if (_anchor<0 || ::fstat(_fd,&info)) {
            if (_anchor>=0) { ::close(_anchor); }
            ::close(_fd);_fd=_anchor=-1;return false;
        }
        _device=info.st_dev;_inode=info.st_ino;return require();
    }
    bool require() {
        struct stat left{},right{};
        if (_lost || _fd<0 || _anchor<0 || _fd==_anchor || ::fstat(_fd,&left) || ::fstat(_anchor,&right)
            || left.st_dev!=_device || left.st_ino!=_inode || right.st_dev!=_device || right.st_ino!=_inode
            || ::fcntl(_fd,PICO_ASSETS_F_DUPFD_QUERY,_anchor)!=1) { _lost=true;return false; }
        return true;
    }
    int fd() const { return _fd; }
    bool close() {
        if (_fd<0 && _anchor<0) { return true; }
        if (!require()) { return false; }
        ::close(_fd);::close(_anchor);_fd=_anchor=-1;return true;
    }
    ~PicoAssetsOriginalDescriptor() { close(); }
private:
    int _fd{-1},_anchor{-1};dev_t _device{};ino_t _inode{};bool _lost{false};
};

// Measurement only. No reference to a worker, server mapping or product callback
// is retained. Missing/inconsistent writes make the fixture source unavailable.
class PicoAssetsBakeOriginals {
public:
    PicoAssetsBakeOriginals() {
        if (qgetenv("OVERTE_E2E_PICO_ASSETS_ORIGINALS_ENABLE")!="1") { return; }
        const auto directory=qgetenv("OVERTE_E2E_PICO_ASSETS_ORIGINALS");
        if (directory.isEmpty()) { return; }
        _path=QString::fromUtf8(directory);
        if (_path.toUtf8()!=directory || !QDir::isAbsolutePath(_path) || QDir::cleanPath(_path)!=_path
            || QFileInfo(_path).canonicalFilePath()!=_path
            || !_root.open(directory.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)) { return; }
        struct stat root{};
        if (!_root.require() || ::fstat(_root.fd(),&root) || !S_ISDIR(root.st_mode) || root.st_uid!=::geteuid() || (root.st_mode&0777)!=0700) { return; }
        _device=root.st_dev;_inode=root.st_ino;
        const auto output=directory+"/assets-bakes.json";
        if (!_file.open(output.constData(),O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW|O_CLOEXEC,0600)) { return; }
        struct stat file{};if (::fstat(_file.fd(),&file)) { return; }
        _fileDevice=file.st_dev;_fileInode=file.st_ino;
        if (::fsync(_root.fd())) { return; }
        _enabled=true;
    }
    bool enabled() const { return _enabled; }
    static bool blob(const QString& path,qint64 bytes,QString& sha) {
        if (bytes<=0 || bytes>1048576) { return false; }
        PicoAssetsOriginalDescriptor file;
        const auto name=path.toUtf8();if (!file.open(name.constData(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC)) { return false; }
        struct stat before{},after{},named{};bool ok=file.require() && ::fstat(file.fd(),&before)==0
            && S_ISREG(before.st_mode) && before.st_size==bytes && before.st_nlink==1;
        QCryptographicHash hash(QCryptographicHash::Sha256);qint64 offset=0;char buffer[65536];
        while (ok && offset<bytes) {
            if (!file.require()) { ok=false;break; }
            const auto count=::pread(file.fd(),buffer,size_t(qMin<qint64>(sizeof(buffer),bytes-offset)),offset);
            if (count<=0 || !file.require()) { ok=false;break; }
            hash.addData(buffer,count);offset+=count;
        }
        ok=ok && file.require() && ::fstat(file.fd(),&after)==0 && ::lstat(name.constData(),&named)==0;
        const auto same=[](const struct stat& a,const struct stat& b) {
            return a.st_dev==b.st_dev && a.st_ino==b.st_ino && a.st_mode==b.st_mode && a.st_uid==b.st_uid
                && a.st_nlink==b.st_nlink && a.st_size==b.st_size
                && a.st_mtim.tv_sec==b.st_mtim.tv_sec && a.st_mtim.tv_nsec==b.st_mtim.tv_nsec
                && a.st_ctim.tv_sec==b.st_ctim.tv_sec && a.st_ctim.tv_nsec==b.st_ctim.tv_nsec;
        };
        ok=ok && offset==bytes && same(before,after) && same(before,named);
        if (!file.close()) { return false; }
        if (ok) { sha=QString::fromLatin1(hash.result().toHex()); }
        return ok;
    }
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
        if (mappings.size()>4096 || blobs.size()>4096 || pending<0 || pending>64) { _valid=false;return; }
        if (contextEpoch<=0 || contextEpoch>now() || now()-contextEpoch>1500) { return; }
        if (!_root.require() || !_file.require() || QFileInfo(_path).canonicalFilePath()!=_path || ::fstat(_root.fd(),&root) || root.st_dev!=_device || root.st_ino!=_inode || root.st_uid!=::geteuid() || (root.st_mode&0777)!=0700
                || ::fstat(_file.fd(),&file) || ::fstatat(_root.fd(),"assets-bakes.json",&path,AT_SYMLINK_NOFOLLOW)
                || !S_ISREG(path.st_mode) || file.st_dev!=_fileDevice || file.st_ino!=_fileInode || path.st_dev!=_fileDevice || path.st_ino!=_fileInode
                || path.st_uid!=::geteuid() || path.st_nlink!=1 || (path.st_mode&0777)!=0600 || _sequence>=1000000000) { _valid=false;return; }
        QFile proc("/proc/self/stat");QString start;if (proc.open(QIODevice::ReadOnly)) { const auto data=proc.readAll();const auto fields=data.mid(data.lastIndexOf(')')+2).split(' ');if (fields.size()>19) { start=fields[19]; } }
        const QVariantMap packet{{"assetsBakeOriginalsVersion",2},{"instance",_instance},{"sequence",++_sequence},{"processId",QCoreApplication::applicationPid()},
            {"processStart",start},{"domainId",domain},{"assetServerId",server},{"capturedEpochMs",now()},{"contextCapturedEpochMs",contextEpoch},{"valid",_valid},
            {"jobs",_jobs},{"mappings",mappings},{"blobs",blobs},{"pending",pending}};
        const auto bytes=QJsonDocument::fromVariant(packet).toJson(QJsonDocument::Compact);
        if (bytes.size()>1048576) { _valid=false;return; }
        if (!_root.require() || !_file.require() || ::flock(_file.fd(),LOCK_EX|LOCK_NB)) { return; }
        // A retained marker makes incomplete/uncertain publication unavailable
        // to the passive reader. It is never removed after a failed write.
        const auto pendingPath=(_path+"/assets-bakes.pending").toUtf8();
        if (!_pending.open(pendingPath.constData(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600)
            || !_root.require() || ::fsync(_root.fd())) { _valid=false;return; }
        bool ok=_file.require() && ::ftruncate(_file.fd(),0)==0 && _file.require() && ::lseek(_file.fd(),0,SEEK_SET)==0;
        qsizetype offset=0;
        while (ok && offset<bytes.size()) {
            if (!_file.require()) { ok=false;break; }
            const auto n=::write(_file.fd(),bytes.constData()+offset,bytes.size()-offset);
            if (n<=0 || !_file.require()) { ok=false; }else { offset+=n; }
        }
        ok=ok && _file.require() && ::fsync(_file.fd())==0 && _file.require() && _root.require();
        if (ok) {
            struct stat held{},named{};
            ok=_pending.require() && ::fstat(_pending.fd(),&held)==0
                && ::fstatat(_root.fd(),"assets-bakes.pending",&named,AT_SYMLINK_NOFOLLOW)==0
                && held.st_dev==named.st_dev && held.st_ino==named.st_ino && named.st_uid==::geteuid()
                && S_ISREG(named.st_mode) && named.st_nlink==1 && (named.st_mode&0777)==0600;
            if (ok) { ok=_pending.close() && ::unlinkat(_root.fd(),"assets-bakes.pending",0)==0; }
        }
        if (_file.require()) { ::flock(_file.fd(),LOCK_UN); }
        if (!ok) { _valid=false;_enabled=false; }
    }
private:
    static qint64 now() { return QDateTime::currentMSecsSinceEpoch(); }
    mutable QMutex _mutex;QVariantList _jobs;const QString _instance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
    bool _enabled{false},_valid{true};QString _path;PicoAssetsOriginalDescriptor _root,_file,_pending;dev_t _device{},_fileDevice{};ino_t _inode{},_fileInode{};quint64 _sequence{0};
};
}
#endif
