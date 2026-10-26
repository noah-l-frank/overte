// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "AssetBackendWork.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_LINUX)
#include <QJsonDocument>
#include <algorithm>
#include <cerrno>
#include <dirent.h>
#include <fcntl.h>

namespace overte::e2e::asset_backend {
inline QJsonObject identity(const struct stat& value,bool directory=false) {
    QJsonObject result{{"device",QString::number(static_cast<qulonglong>(value.st_dev))},{"inode",QString::number(static_cast<qulonglong>(value.st_ino))},
        {"uid",QString::number(static_cast<qulonglong>(value.st_uid))},{"mode",QString::number(value.st_mode&07777)},{"links",QString::number(static_cast<qulonglong>(value.st_nlink))},
        {"modifiedSeconds",QString::number(static_cast<qlonglong>(value.st_mtim.tv_sec))},{"modifiedNanoseconds",QString::number(static_cast<qlonglong>(value.st_mtim.tv_nsec))},
        {"changedSeconds",QString::number(static_cast<qlonglong>(value.st_ctim.tv_sec))},{"changedNanoseconds",QString::number(static_cast<qlonglong>(value.st_ctim.tv_nsec))}};
    if (!directory) {result["bytes"]=QString::number(static_cast<qlonglong>(value.st_size));}return result;
}
inline bool sameFile(const struct stat& before,const struct stat& after,bool directory=false) {
    return identity(before,directory)==identity(after,directory) && before.st_mode==after.st_mode;
}
class Directory {
public:
    explicit Directory(const QString& configured) : _configured(configured),_canonical(QFileInfo(configured).canonicalFilePath()) {
        if (_canonical.isEmpty() || !QDir::isAbsolutePath(_canonical)) {return;}
        const auto path=QFile::encodeName(_canonical);_fd=::open(path.constData(),O_RDONLY|O_CLOEXEC|O_DIRECTORY|O_NOFOLLOW|O_NONBLOCK);
        if (_fd>=0 && (::fstat(_fd,&_original)!=0 || !S_ISDIR(_original.st_mode) || _original.st_uid!=::geteuid())) {::close(_fd);_fd=-1;}
    }
    ~Directory() {if (_fd>=0) {::close(_fd);}}
    Directory(const Directory&)=delete;Directory& operator=(const Directory&)=delete;
    bool valid() const {return _fd>=0 && current();}
    bool current() const {
        if (_fd<0 || QFileInfo(_configured).canonicalFilePath()!=_canonical) {return false;}
        struct stat actual{},path{};const auto encoded=QFile::encodeName(_canonical);
        return ::fstat(_fd,&actual)==0 && ::lstat(encoded.constData(),&path)==0 && S_ISDIR(path.st_mode)
            && sameFile(_original,actual,true) && sameFile(actual,path,true);
    }
    QJsonObject source() const {return {{"configuredPath",_configured},{"canonicalPath",_canonical},{"identity",_fd>=0 ? QJsonValue(identity(_original,true)) : QJsonValue(QJsonValue::Null)}};}
    QStringList entries(bool& complete) const {
        QStringList result;if (!valid()) {complete=false;return result;}
        const auto copy=::dup(_fd);if (copy<0) {complete=false;return result;}auto stream=::fdopendir(copy);
        if (!stream) {::close(copy);complete=false;return result;}::rewinddir(stream);errno=0;
        while (auto item=::readdir(stream)) {
            const auto name=QString::fromLocal8Bit(item->d_name);if (name=="." || name=="..") {continue;}
            if (result.size()>=512) {complete=false;break;}result.append(name);
        }
        if (errno!=0) {complete=false;}::closedir(stream);std::sort(result.begin(),result.end());if (!current()) {complete=false;}return result;
    }
    QJsonObject file(const QString& name,qint64 maximum,qint64& bodyBudget,bool& complete) const {
        QJsonObject result{{"name",name},{"exists",false}};
        if (_fd<0 || !current() || name.contains('/') || name.contains(QChar(0)) || name=="." || name=="..") {complete=false;return result;}
        const auto leaf=QFile::encodeName(name);struct stat original{};
        if (::fstatat(_fd,leaf.constData(),&original,AT_SYMLINK_NOFOLLOW)!=0) {if (errno!=ENOENT) {complete=false;}return result;}
        result["exists"]=true;result["identity"]=identity(original);
        result["body"]=QJsonObject{{"retained",false},{"base64",QJsonValue(QJsonValue::Null)},{"sha256",QJsonValue(QJsonValue::Null)}};
        if (!S_ISREG(original.st_mode) || original.st_uid!=::geteuid() || original.st_nlink!=1 || original.st_size<0) {complete=false;return result;}
        if (original.st_size>maximum || original.st_size>bodyBudget) {return result;}
        const auto fd=::openat(_fd,leaf.constData(),O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);struct stat opened{};
        if (fd<0) {complete=false;return result;}
        bool valid=::fstat(fd,&opened)==0 && sameFile(original,opened);QByteArray raw;raw.resize(static_cast<int>(original.st_size));qint64 offset=0;
        while (valid && offset<raw.size()) {
            const auto count=::read(fd,raw.data()+offset,static_cast<size_t>(raw.size()-offset));
            if (count<0 && errno==EINTR) {continue;}if (count<=0) {valid=false;break;}offset+=count;
        }
        char extra{};ssize_t trailing=-1;if (valid) {do {trailing=::read(fd,&extra,1);} while (trailing<0 && errno==EINTR);}
        struct stat after{},path{};
        valid=valid && trailing==0 && ::fstat(fd,&after)==0 && ::fstatat(_fd,leaf.constData(),&path,AT_SYMLINK_NOFOLLOW)==0
            && sameFile(original,after) && sameFile(after,path);::close(fd);
        if (!valid || !current()) {complete=false;return result;}
        bodyBudget-=raw.size();result["body"]=QJsonObject{{"retained",true},{"base64",QString::fromLatin1(raw.toBase64())},
            {"sha256",QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex())}};return result;
    }
private:QString _configured,_canonical;int _fd{-1};struct stat _original{};
};
inline bool separate(const QString& first,const QString& second) {
    const auto a=QFileInfo(first).canonicalFilePath(),b=QFileInfo(second).canonicalFilePath();
    return !a.isEmpty() && !b.isEmpty() && a!=b && !a.startsWith(b+'/') && !b.startsWith(a+'/');
}
}
#endif
