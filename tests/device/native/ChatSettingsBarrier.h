// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QMutex>
#include <QMutexLocker>
#include <QMap>
#include <QUuid>
#include <QVariantMap>
#include <functional>
#include <cerrno>
#include <atomic>
#if defined(Q_OS_UNIX)
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#endif
namespace overte::e2e {
class ChatSettingsBarrier {
public:
    qint64 pendingMutations() const { return _attempts.load(); }
    class Mutation {
    public:
        Mutation(ChatSettingsBarrier& owner,const QString& key) : _owner(owner) {
            _tracked=QCoreApplication::arguments().contains("--testScript")
                && (key.isEmpty() || key=="ArmoredChat-Messages" || key=="ArmoredChat-Config");
            if (_tracked) { ++_owner._attempts;QMutexLocker lock(&_owner._mutex);++_owner._pending; }
        }
        ~Mutation() {
            if (_tracked) {
                QMutexLocker lock(&_owner._mutex);
                if (_owner._pending<1 || _owner._sequence>=9007199254740991LL) { _owner._valid=false;return; }
                --_owner._pending;++_owner._sequence;--_owner._attempts;
            }
        }
        Mutation(const Mutation&)=delete;Mutation& operator=(const Mutation&)=delete;
    private:
        ChatSettingsBarrier& _owner;bool _tracked{false};
    };
    QVariantMap read(const std::function<QVariantMap()>& cache,const std::function<QVariantMap()>& writer) {
        if (!QCoreApplication::arguments().contains("--testScript") || !cache || !writer || !_mutex.tryLock()) { return {}; }
        QElapsedTimer elapsed;elapsed.start();
        const auto started=QDateTime::currentMSecsSinceEpoch();
        if (started<=0 || started<_epoch) { _valid=false;_mutex.unlock();return {}; }
        if (!_valid || _pending || _attempts.load()!=0) { _mutex.unlock();return {}; }
        const auto sequence=_sequence;
        _mutex.unlock();
        // No barrier mutex spans cache locking, queued work or physical I/O.
        // Any started/completed original mutation invalidates this acquisition.
        const auto actualCache=cache();
        if (actualCache.isEmpty()) { return {}; }
        const auto actualWriter=writer();const auto finished=QDateTime::currentMSecsSinceEpoch();
        if (!_mutex.tryLock()) { return {}; }
        struct Unlock {QRecursiveMutex& mutex;~Unlock(){mutex.unlock();}} unlock{_mutex};
        if (finished<started || finished<_epoch) { _valid=false;return {}; }
        if (!_valid || actualWriter.isEmpty() || finished-started>1500 || elapsed.elapsed()>1500
                || _pending || _attempts.load()!=0 || _sequence!=sequence) { return {}; }
        _epoch=finished;
        return {{"settingsBarrierVersion",1},{"instance",_instance},{"mutationSequence",_sequence},{"pending",_pending},{"capturedEpochMs",finished},{"elapsedMs",elapsed.elapsed()},
            {"cache",actualCache},{"writer",actualWriter}};
    }
private:
    QRecursiveMutex _mutex;qint64 _pending{0},_sequence{0},_epoch{0};bool _valid{true};
    std::atomic<qint64> _attempts{0};
    const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
};

// Read physical INI bytes after the original writer's actual sync. This never
// constructs another QSettings reader (which would share a process-global cache).
#if defined(Q_OS_UNIX)
inline bool chatSettingsSameFile(const struct stat& a,const struct stat& b) {
#if defined(Q_OS_DARWIN)
    const bool times=a.st_mtimespec.tv_sec==b.st_mtimespec.tv_sec && a.st_mtimespec.tv_nsec==b.st_mtimespec.tv_nsec
        && a.st_ctimespec.tv_sec==b.st_ctimespec.tv_sec && a.st_ctimespec.tv_nsec==b.st_ctimespec.tv_nsec;
#else
    const bool times=a.st_mtim.tv_sec==b.st_mtim.tv_sec && a.st_mtim.tv_nsec==b.st_mtim.tv_nsec
        && a.st_ctim.tv_sec==b.st_ctim.tv_sec && a.st_ctim.tv_nsec==b.st_ctim.tv_nsec;
#endif
    return times && a.st_dev==b.st_dev && a.st_ino==b.st_ino && a.st_size==b.st_size
        && a.st_uid==b.st_uid && a.st_mode==b.st_mode && a.st_nlink==b.st_nlink;
}
#endif
inline QVariantMap chatSettingsFile(const QString& originalPath) {
#if defined(Q_OS_UNIX)
    const QFileInfo file(originalPath);const auto path=file.canonicalFilePath();
    auto privateRoot=QFileInfo(originalPath).dir().canonicalPath();struct stat directory{};
    if (file.isSymLink()) { return {}; }
    while (!privateRoot.isEmpty()) {
        if (::lstat(QFile::encodeName(privateRoot).constData(),&directory)!=0 || !S_ISDIR(directory.st_mode)
                || directory.st_uid!=::geteuid() || (directory.st_mode&0022)!=0) { return {}; }
        if ((directory.st_mode&0077)==0) { break; }
        const auto parent=QFileInfo(privateRoot).dir().canonicalPath();
        if (parent==privateRoot) { return {}; }privateRoot=parent;
    }
    if (privateRoot.isEmpty()) { return {}; }
    QByteArray bytes;
    if (file.exists()) {
        if (path.isEmpty()) { return {}; }
        const int descriptor=::open(QFile::encodeName(path).constData(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);
        struct stat before{},after{},current{};
        if (descriptor<0 || ::fstat(descriptor,&before)!=0 || !S_ISREG(before.st_mode) || before.st_uid!=::geteuid()
                || (before.st_mode&0600)!=0600 || (before.st_mode&07133)!=0 || before.st_nlink!=1 || before.st_size<0 || before.st_size>1048576) {
            if (descriptor>=0) { ::close(descriptor); }return {};
        }
        QFile actual;
        if (!actual.open(descriptor,QIODevice::ReadOnly,QFileDevice::AutoCloseHandle)) { ::close(descriptor);return {}; }
        bytes=actual.read(1048577);
        if (actual.error()!=QFile::NoError || bytes.size()!=before.st_size || ::fstat(descriptor,&after)!=0
                || ::lstat(QFile::encodeName(path).constData(),&current)!=0 || !chatSettingsSameFile(before,after)
                || !chatSettingsSameFile(before,current) || QFileInfo(originalPath).isSymLink()
                || QFileInfo(originalPath).canonicalFilePath()!=path) { return {}; }
    } else {
        struct stat missing{};
        if (::lstat(QFile::encodeName(originalPath).constData(),&missing)==0 || errno!=ENOENT) { return {}; }
    }
    struct stat finalDirectory{};
    if (::lstat(QFile::encodeName(privateRoot).constData(),&finalDirectory)!=0 || !chatSettingsSameFile(directory,finalDirectory)
            || QFileInfo(privateRoot).canonicalFilePath()!=privateRoot) { return {}; }
    if (bytes.startsWith("\xEF\xBB\xBF")) { bytes.remove(0,3); }
    if (bytes.contains('\0')) { return {}; }
    QMap<QByteArray,QByteArray> rows;bool general{true};
    for (auto line:bytes.split('\n')) {
        if (line.endsWith('\r')) { line.chop(1); }
        if (line.isEmpty() || line.startsWith(';') || line.startsWith('#')) { continue; }
        if (line.startsWith('[')) { if (!line.endsWith(']')) { return {}; }general=line=="[General]";continue; }
        if (!general) { continue; }const auto separator=line.indexOf('=');
        if (separator<1) { return {}; }const auto key=line.left(separator);
        if (key!="ArmoredChat-Messages" && key!="ArmoredChat-Config") {
            auto alias=QByteArray::fromPercentEncoding(key.trimmed());
            if (alias.startsWith('"') && alias.endsWith('"')) { alias=alias.mid(1,alias.size()-2); }
            if (alias=="ArmoredChat-Messages" || alias=="ArmoredChat-Config") { return {}; }
            continue;
        }
        if (rows.contains(key) || line.endsWith('\\')) { return {}; }rows.insert(key,line.mid(separator+1));
    }
    QVariantMap result;
    for (const auto key:{"ArmoredChat-Messages","ArmoredChat-Config"}) {
        const auto name=QByteArray(key);const bool present=rows.contains(name);
        result.insert(QString::fromLatin1(key),QVariantMap{{"present",present},
            {"sha256",QString::fromLatin1(QCryptographicHash::hash((present?QByteArray("present:"):QByteArray("absent:"))+rows.value(name),QCryptographicHash::Sha256).toHex())}});
    }
    return result;
#else
    Q_UNUSED(originalPath) return {};
#endif
}
} // namespace overte::e2e
#endif
