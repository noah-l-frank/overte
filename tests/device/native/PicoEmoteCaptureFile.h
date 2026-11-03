// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "PicoRemoteAvatarStreamFile.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE) && defined(Q_OS_LINUX)
#include <QRegularExpression>

namespace overte::e2e {
// EXCLUSIVE PROTOTYPE: not connected to TSI/Policy2 and not compiled.
// Reuses the exact integrated strong descriptor/stamp primitives unchanged.
// One bounded result file at the original native root. The coordinating
// owner MUST retain all successful/partial objects, serialize the shared
// marker, and select Policy2 BEFORE first source IO. Default output paths
// do not instantiate this class. No byte limit is inferred from a reader.
class PicoEmoteCaptureFile {
public:
    static constexpr const char* Pending="feature-pico-emote-capture-pending.json";
    PicoEmoteCaptureFile()=default;
    bool open(const QString& root,const QString& leaf,std::function<bool()> permit) {
        if (_opened) { return fail(); }
        _opened=true;_path=root;_leaf=leaf.toUtf8();_limit=limit(leaf);_permit=std::move(permit);
        if (!_limit || !context() || !_permit || !_permit() || !QDir::isAbsolutePath(root)
                || root.contains(QChar(0)) || QString::fromUtf8(root.toUtf8())!=root
                || QDir::cleanPath(root)!=root || QFileInfo(root).canonicalFilePath()!=root
                || !_root.open(QFile::encodeName(root),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)) { return false; }
        struct stat info{};
        if (!directory(false) || ::fstat(_root.fd(),&info)) { return false; }
        _device=info.st_dev;_inode=info.st_ino;_rootAdmitted=true;
        if (!missing(_leaf.constData()) || !missing(Pending)
                || !directory() || !_permit()) { return false; }
        if (!_file.openAt(_root.fd(),_leaf.constData(),O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600)
                || !_file.require() || ::fstat(_file.fd(),&_stamp) || !privateFile(_stamp)
                || _stamp.st_size!=0 || ::fsync(_file.fd()) || ::fsync(_root.fd()) || !directory()) { return false; }
        _valid=true;return true;
    }
    bool ready() { return _valid && !_writing && current() ? true : fail(); }
    bool publish(const QString& nonce,const QByteArray& bytes) {
        if (!QRegularExpression("\\A[0-9a-f]{32}\\z").match(nonce).hasMatch() || !_valid || _writing || !_permit() || !current()) { return fail(); }
        _writing=true;
        // No requested sample state is accepted: these are already sampled
        // native bytes. The marker owns uncertainty before first truncation.
        if (!_permit() || !_pending.openAt(_root.fd(),Pending,O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600)) { return fail(); }
        const auto marker=nonce.toLatin1()+"\n"+QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()+"\n";
        struct stat markerStamp{};
        if (!_pending.require() || !_permit() || ::write(_pending.fd(),marker.constData(),marker.size())!=marker.size()
                || !_pending.require() || ::fsync(_pending.fd()) || ::fstat(_pending.fd(),&markerStamp)
                || !pendingEquals(marker,markerStamp) || !directory() || ::fsync(_root.fd())
                || bytes.isEmpty() || bytes.size()>_limit
                || !_permit() || !current(true) || !_permit() || ::ftruncate(_file.fd(),0)) { return fail(); }
        qsizetype offset=0;
        while (offset<bytes.size()) {
            if (!directory() || !_file.require() || !_permit()) { return fail(); }
            const auto count=::pwrite(_file.fd(),bytes.constData()+offset,bytes.size()-offset,offset);
            if (count<=0 || !_file.require()) { return fail(); }
            offset+=count;
            struct stat held{},named{};
            if (::fstat(_file.fd(),&held) || ::fstatat(_root.fd(),_leaf.constData(),&named,AT_SYMLINK_NOFOLLOW)
                    || !privateFile(held) || held.st_dev!=_stamp.st_dev || held.st_ino!=_stamp.st_ino
                    || !picoStreamStamp(held,named) || held.st_size!=offset
                    || !readEquals(bytes.left(offset),held)) { return fail(); }
        }
        struct stat next{},named{},pending{},pendingNamed{};
        if (!_file.require() || ::fsync(_file.fd()) || !directory() || ::fstat(_file.fd(),&next)
                || ::fstatat(_root.fd(),_leaf.constData(),&named,AT_SYMLINK_NOFOLLOW) || !picoStreamStamp(next,named)
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
    // Only an actual native-issued immutable receipt may take this path.
    // Fixed current-file retirement remains a distinct finalization duty.
    bool retireReceipt(const QString& nonce,const QByteArray& digest) {
        if (_leaf!="world-render-storage-"+nonce.toLatin1()+".json" || digest.size()!=64
                || !_valid || _writing || !_permit || !_permit() || !current()
                || QCryptographicHash::hash(_expected,QCryptographicHash::Sha256).toHex()!=digest) { return fail(); }
        _writing=true;
        if (!_pending.openAt(_root.fd(),Pending,O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600)) { return fail(); }
        const auto marker=nonce.toLatin1()+"\n"+digest+"\n";struct stat pin{};
        if (!_pending.require() || ::write(_pending.fd(),marker.constData(),marker.size())!=marker.size()
                || ::fsync(_pending.fd()) || ::fstat(_pending.fd(),&pin) || !pendingEquals(marker,pin)
                || ::fsync(_root.fd()) || !_permit() || !current(true)
                || ::unlinkat(_root.fd(),_leaf.constData(),0) || ::fsync(_root.fd()) || !directory()) { return fail(); }
        struct stat after{};
        if (!_file.require() || ::fstat(_file.fd(),&after) || after.st_dev!=_stamp.st_dev || after.st_ino!=_stamp.st_ino
                || after.st_uid!=_stamp.st_uid || after.st_mode!=_stamp.st_mode || after.st_size!=_stamp.st_size
                || after.st_nlink!=0 || !missing(_leaf.constData()) || !pendingEquals(marker,pin) || !_permit()) { return fail(); }
        QByteArray original(_expected.size()+1,'\0');const auto count=::pread(_file.fd(),original.data(),original.size(),0);
        if (count!=_expected.size() || original.left(count)!=_expected || !_file.require() || !directory()
                || !_file.close() || !_pending.close() || ::unlinkat(_root.fd(),Pending,0)
                || ::fsync(_root.fd()) || !directory() || !_root.close()) { return fail(); }
        _writing=false;_retired=_closed=true;return true;
    }
    bool retired() const { return _retired; }
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
        return {{"leaf",QString::fromUtf8(_leaf)},{"maximumFileBytes",_limit},{"rootNode",node(root)},{"sampleNode",node(_stamp)},{"sampleStamp",stamp},
            {"sha256",QString::fromLatin1(QCryptographicHash::hash(_expected,QCryptographicHash::Sha256).toHex())},
            {"bytes",_expected.size()}};
    }
private:
    static qsizetype limit(const QString& leaf) {
        if (leaf=="world-render-observation.json" || leaf=="feature-pico-world-model-draws.json"
                || leaf=="world-render-receipts-result.json") { return 262144; }
        return QRegularExpression("\\Aworld-render-storage-[0-9a-f]{32}\\.json\\z").match(leaf).hasMatch() ? 100000 : 0;
    }
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
    bool privateFile(const struct stat& info) const { return S_ISREG(info.st_mode) && info.st_uid==::geteuid()
        && info.st_nlink==1 && (info.st_mode&07777)==0600 && info.st_size>=0 && info.st_size<=_limit; }
    bool directory(bool admitted=true) {
        struct stat held{},named{};
        return context() && _root.require() && QFileInfo(_path).canonicalFilePath()==_path
            && ::fstat(_root.fd(),&held)==0 && ::lstat(QFile::encodeName(_path).constData(),&named)==0
            && S_ISDIR(held.st_mode) && held.st_uid==::geteuid() && (held.st_mode&07777)==0700
            && picoStreamStamp(held,named)
            && (!admitted || (_rootAdmitted && held.st_dev==_device && held.st_ino==_inode));
    }
    bool readEquals(const QByteArray& expected,const struct stat& pin) {
        if (!_file.require() || expected.size()>_limit || pin.st_size!=expected.size()) { return false; }
        QByteArray actual(expected.size(),'\0');qsizetype offset=0;
        while (offset<actual.size()) {
            if (!_file.require()) { return false; }
            const auto count=::pread(_file.fd(),actual.data()+offset,actual.size()-offset,offset);
            if (count<=0 || !_file.require()) { return false; }offset+=count;
        }
        struct stat after{},named{};
        return _file.require() && ::fstat(_file.fd(),&after)==0
            && ::fstatat(_root.fd(),_leaf.constData(),&named,AT_SYMLINK_NOFOLLOW)==0
            && picoStreamStamp(pin,after) && picoStreamStamp(pin,named) && actual==expected;
    }
    bool current(bool pendingAllowed=false) {
        struct stat held{},named{};
        return !_closed && directory() && _file.require() && ::fstat(_file.fd(),&held)==0
            && ::fstatat(_root.fd(),_leaf.constData(),&named,AT_SYMLINK_NOFOLLOW)==0 && privateFile(held)
            && picoStreamStamp(held,named) && picoStreamStamp(held,_stamp) && readEquals(_expected,held)
            && (pendingAllowed || missing(Pending)) && directory();
    }
    bool fail() { _valid=false;return false; }
    const pid_t _pid{::getpid()};QCoreApplication* const _application{QCoreApplication::instance()};
    QThread* const _thread{QThread::currentThread()};QString _path;QByteArray _leaf;
    qsizetype _limit{0};std::function<bool()> _permit;bool _opened{false};
    PicoStreamDescriptor _root,_file,_pending;dev_t _device{};ino_t _inode{};struct stat _stamp{};
    QByteArray _expected;bool _rootAdmitted{false},_valid{false},_writing{false},_closed{false},_retired{false};
};
}
#endif
