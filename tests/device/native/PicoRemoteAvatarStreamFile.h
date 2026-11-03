// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE) && defined(Q_OS_LINUX)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QThread>
#include <QVariantMap>
#include <functional>
#include <cerrno>
#include <sys/file.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>

namespace overte::e2e {
// Linux UAPI linux/fcntl.h: F_LINUX_SPECIFIC_BASE(1024)+3. NDK27.3
// omits the declaration. This number is NOT a capability assertion: every
// admission/access still requires the kernel's actual original-OFD result.
inline constexpr int PicoStreamAliasQuery=1027;
#if defined(F_DUPFD_QUERY)
static_assert(F_DUPFD_QUERY==PicoStreamAliasQuery,"Unexpected Linux OFD query ABI");
#endif

// The guard pattern follows PicoAssetsOriginalDescriptor; this separate
// test/Pico-only owner deliberately does not change that package/default.
// No inode/seek/flag fallback and no close of uncertain foreign halves.
class PicoStreamDescriptor {
public:
    PicoStreamDescriptor()=default;
    PicoStreamDescriptor(const PicoStreamDescriptor&)=delete;
    PicoStreamDescriptor& operator=(const PicoStreamDescriptor&)=delete;
    bool open(const QByteArray& path,int flags,int mode=0) {
        if (_fd>=0 || _anchor>=0 || _lost || ::getpid()!=_pid) { return false; }
        return opened(::open(path.constData(),flags,mode));
    }
    bool openAt(int parent,const char* leaf,int flags,int mode=0) {
        if (_fd>=0 || _anchor>=0 || _lost || ::getpid()!=_pid) { return false; }
        return opened(::openat(parent,leaf,flags,mode));
    }
    bool require() {
        struct stat a{},b{};
        if (_lost || ::getpid()!=_pid || _fd<0 || _anchor<0 || _fd==_anchor
                || ::fstat(_fd,&a) || ::fstat(_anchor,&b)
                || a.st_dev!=_device || a.st_ino!=_inode || b.st_dev!=_device || b.st_ino!=_inode
                || ::fcntl(_fd,PicoStreamAliasQuery,_anchor)!=1) { _lost=true;return false; }
        return true;
    }
    bool close() {
        if (_fd<0 && _anchor<0) { return true; }
        if (!require()) { return false; }
        ::close(_fd);::close(_anchor);_fd=_anchor=-1;return true;
    }
    int fd() const { return _fd; }
    ~PicoStreamDescriptor() { close(); }
private:
    bool opened(int descriptor) {
        if (descriptor<0) { return false; }
        _fd=descriptor;_anchor=::fcntl(_fd,F_DUPFD_CLOEXEC,0);
        struct stat info{};
        if (_anchor<0 || ::fstat(_fd,&info)) {
            // Fresh, unescaped allocations only. After first OFD admission
            // fails, even these halves remain owned until host finalization.
            if (_anchor>=0) { ::close(_anchor); }
            ::close(_fd);_fd=_anchor=-1;return false;
        }
        _device=info.st_dev;_inode=info.st_ino;return require();
    }
    const pid_t _pid{::getpid()};int _fd{-1},_anchor{-1};
    dev_t _device{};ino_t _inode{};bool _lost{false};
};

inline bool picoStreamStamp(const struct stat& a,const struct stat& b) {
    return a.st_dev==b.st_dev && a.st_ino==b.st_ino && a.st_uid==b.st_uid && a.st_mode==b.st_mode
        && a.st_nlink==b.st_nlink && a.st_size==b.st_size
        && a.st_mtim.tv_sec==b.st_mtim.tv_sec && a.st_mtim.tv_nsec==b.st_mtim.tv_nsec
        && a.st_ctim.tv_sec==b.st_ctim.tv_sec && a.st_ctim.tv_nsec==b.st_ctim.tv_nsec;
}

// One original mutable producer file, not an immutable historical range.
// Only verified successful writes advance its expected complete bytes/stamp.
// A pending marker survives every unknown/partial write and forbids adoption.
class PicoRemoteAvatarStreamFile {
public:
    static constexpr qsizetype Limit=196608;
    static constexpr const char* Leaf="feature-pico-remote-avatar-stream.json";
    static constexpr const char* Pending="feature-pico-remote-avatar-stream-pending.json";
    PicoRemoteAvatarStreamFile(const QString& root,std::function<bool()> permit):_path(root),_permit(std::move(permit)) {
        if (!context() || !_permit || !_permit() || !QDir::isAbsolutePath(root)
                || root.contains(QChar(0)) || QString::fromUtf8(root.toUtf8())!=root
                || QDir::cleanPath(root)!=root || QFileInfo(root).canonicalFilePath()!=root
                || !_root.open(QFile::encodeName(root),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)) { return; }
        struct stat info{};
        if (!directory(false) || ::fstat(_root.fd(),&info)) { return; }
        _device=info.st_dev;_inode=info.st_ino;_rootAdmitted=true;
        if (!missing(Leaf) || !missing(Pending) || !missing("feature-pico-remote-avatar.json")
                || !directory() || !_permit()) { return; }
        if (!_file.openAt(_root.fd(),Leaf,O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600)
                || !_file.require() || ::fstat(_file.fd(),&_stamp) || !privateFile(_stamp)
                || _stamp.st_size!=0 || ::fsync(_file.fd()) || ::fsync(_root.fd()) || !directory()) { return; }
        _valid=true;
    }
    bool ready() { return _valid && !_writing && current() ? true : fail(); }
    bool publish(const QByteArray& bytes) {
        if (!_valid || _writing || bytes.isEmpty() || bytes.size()>Limit || !_permit() || !current()) { return fail(); }
        _writing=true;
        // No requested sample state is accepted: these are already sampled
        // native bytes. The marker owns uncertainty before first truncation.
        if (!_permit() || !_pending.openAt(_root.fd(),Pending,O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600)) { return fail(); }
        const auto marker=QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()+"\n";
        struct stat markerStamp{};
        if (!_pending.require() || !_permit() || ::write(_pending.fd(),marker.constData(),marker.size())!=marker.size()
                || !_pending.require() || ::fsync(_pending.fd()) || ::fstat(_pending.fd(),&markerStamp)
                || !pendingEquals(marker,markerStamp) || !directory() || ::fsync(_root.fd())
                || !_permit() || !current(true) || !_permit() || ::ftruncate(_file.fd(),0)) { return fail(); }
        qsizetype offset=0;
        while (offset<bytes.size()) {
            if (!directory() || !_file.require() || !_permit()) { return fail(); }
            const auto count=::pwrite(_file.fd(),bytes.constData()+offset,bytes.size()-offset,offset);
            if (count<=0 || !_file.require()) { return fail(); }
            offset+=count;
            struct stat held{},named{};
            if (::fstat(_file.fd(),&held) || ::fstatat(_root.fd(),Leaf,&named,AT_SYMLINK_NOFOLLOW)
                    || !privateFile(held) || held.st_dev!=_stamp.st_dev || held.st_ino!=_stamp.st_ino
                    || !picoStreamStamp(held,named) || held.st_size!=offset
                    || !readEquals(bytes.left(offset),held)) { return fail(); }
        }
        struct stat next{},named{},pending{},pendingNamed{};
        if (!_file.require() || ::fsync(_file.fd()) || !directory() || ::fstat(_file.fd(),&next)
                || ::fstatat(_root.fd(),Leaf,&named,AT_SYMLINK_NOFOLLOW) || !picoStreamStamp(next,named)
                || !readEquals(bytes,next) || !_pending.require() || ::fstat(_pending.fd(),&pending)
                || ::fstatat(_root.fd(),Pending,&pendingNamed,AT_SYMLINK_NOFOLLOW)
                || !privateFile(pending) || !picoStreamStamp(pending,pendingNamed)
                || !picoStreamStamp(pending,markerStamp) || !pendingEquals(marker,markerStamp)
                || !directory() || !_permit()) { return fail(); }
        // Successful readback is the ONLY stamp/byte transition. Unknown
        // close/unlink/fsync still makes the entire owner sticky unavailable.
        _expected=bytes;_stamp=next;
        if (!_pending.close() || !_permit() || ::unlinkat(_root.fd(),Pending,0) || ::fsync(_root.fd()) || !directory()) { return fail(); }
        _writing=false;return current() ? true : fail();
    }
    bool close() {
        if (_closed) { return true; }
        if (!_valid || _writing || !current()) { return false; }
        const bool file=_file.close(),root=_root.close();_closed=file && root;return _closed;
    }
    bool valid() const { return _valid && !_closed; }
    bool writing() const { return _writing; }
    QVariantMap originalProof() {
        if (!_valid || _writing || _expected.isEmpty() || !current()) { return {}; }
        struct stat root{};
        if (::fstat(_root.fd(),&root) || !directory() || !current()) { return {}; }
        const auto node=[](const struct stat& info) { return QVariantList{
            QString::number(static_cast<qulonglong>(info.st_dev)),QString::number(static_cast<qulonglong>(info.st_ino)),
            QString::number(static_cast<qulonglong>(info.st_mode)),QString::number(static_cast<qulonglong>(info.st_uid)),
            QString::number(static_cast<qulonglong>(info.st_nlink))}; };
        auto stamp=node(_stamp);stamp.append(QString::number(static_cast<qulonglong>(_stamp.st_size)));
        stamp.append(QString::number(static_cast<qulonglong>(_stamp.st_mtim.tv_sec)*1000000000ULL+_stamp.st_mtim.tv_nsec));
        stamp.append(QString::number(static_cast<qulonglong>(_stamp.st_ctim.tv_sec)*1000000000ULL+_stamp.st_ctim.tv_nsec));
        return {{"rootNode",node(root)},{"sampleNode",node(_stamp)},{"sampleStamp",stamp},
            {"sha256",QString::fromLatin1(QCryptographicHash::hash(_expected,QCryptographicHash::Sha256).toHex())},
            {"bytes",_expected.size()}};
    }
private:
    bool pendingEquals(const QByteArray& expected,const struct stat& pin) {
        if (!_pending.require() || !privateFile(pin) || pin.st_size!=expected.size()) { return false; }
        QByteArray actual(expected.size()+1,'\0');
        const auto count=::pread(_pending.fd(),actual.data(),actual.size(),0);
        struct stat after{},named{};
        return count==expected.size() && actual.left(count)==expected && _pending.require()
            && ::fstat(_pending.fd(),&after)==0 && ::fstatat(_root.fd(),Pending,&named,AT_SYMLINK_NOFOLLOW)==0
            && picoStreamStamp(pin,after) && picoStreamStamp(pin,named);
    }
    bool context() const { return ::getpid()==_pid && QCoreApplication::instance()==_application
        && QThread::currentThread()==_thread && QCoreApplication::arguments().contains("--testScript"); }
    bool missing(const char* name) const {
        struct stat info{};errno=0;
        return ::fstatat(_root.fd(),name,&info,AT_SYMLINK_NOFOLLOW)==-1 && errno==ENOENT;
    }
    static bool privateFile(const struct stat& info) { return S_ISREG(info.st_mode) && info.st_uid==::geteuid()
        && info.st_nlink==1 && (info.st_mode&0777)==0600 && info.st_size>=0 && info.st_size<=Limit; }
    bool directory(bool admitted=true) {
        struct stat held{},named{};
        return context() && _root.require() && QFileInfo(_path).canonicalFilePath()==_path
            && ::fstat(_root.fd(),&held)==0 && ::lstat(QFile::encodeName(_path).constData(),&named)==0
            && S_ISDIR(held.st_mode) && held.st_uid==::geteuid() && (held.st_mode&0777)==0700
            && picoStreamStamp(held,named)
            && (!admitted || (_rootAdmitted && held.st_dev==_device && held.st_ino==_inode));
    }
    bool readEquals(const QByteArray& expected,const struct stat& pin) {
        if (!_file.require() || expected.size()>Limit || pin.st_size!=expected.size()) { return false; }
        QByteArray actual(expected.size(),'\0');qsizetype offset=0;
        while (offset<actual.size()) {
            if (!_file.require()) { return false; }
            const auto count=::pread(_file.fd(),actual.data()+offset,actual.size()-offset,offset);
            if (count<=0 || !_file.require()) { return false; }offset+=count;
        }
        struct stat after{},named{};
        return _file.require() && ::fstat(_file.fd(),&after)==0
            && ::fstatat(_root.fd(),Leaf,&named,AT_SYMLINK_NOFOLLOW)==0
            && picoStreamStamp(pin,after) && picoStreamStamp(pin,named) && actual==expected;
    }
    bool current(bool pendingAllowed=false) {
        struct stat held{},named{};
        return !_closed && directory() && _file.require() && ::fstat(_file.fd(),&held)==0
            && ::fstatat(_root.fd(),Leaf,&named,AT_SYMLINK_NOFOLLOW)==0 && privateFile(held)
            && picoStreamStamp(held,named) && picoStreamStamp(held,_stamp) && readEquals(_expected,held)
            && (pendingAllowed || missing(Pending)) && directory();
    }
    bool fail() { _valid=false;return false; }
    const pid_t _pid{::getpid()};QCoreApplication* const _application{QCoreApplication::instance()};
    QThread* const _thread{QThread::currentThread()};const QString _path;const std::function<bool()> _permit;
    PicoStreamDescriptor _root,_file,_pending;dev_t _device{};ino_t _inode{};struct stat _stamp{};
    QByteArray _expected;bool _rootAdmitted{false},_valid{false},_writing{false},_closed{false};
};
}
#endif
