// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QSet>
#include <QVector>
#if defined(Q_OS_UNIX)
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace overte::e2e {
// Run only after Qt has validated the complete JSON grammar. Decode member
// names through that same parser so escaped aliases cannot hide duplicate keys.
inline bool uniqueFeatureCommandKeys(const QByteArray& raw) {
    struct Frame { bool object; QSet<QString> keys; };
    QVector<Frame> stack;
    for (int i=0;i<raw.size();++i) {
        const auto c=raw.at(i);
        if (c=='{' || c=='[') {
            if (stack.size()>=128) { return false; }
            stack.append(Frame{c=='{',{}});
        } else if (c=='}' || c==']') {
            if (stack.isEmpty()) { return false; }
            stack.removeLast();
        } else if (c=='"') {
            const auto start=i++;
            while (i<raw.size()) {
                if (raw.at(i)=='\\') { i+=2; }
                else if (raw.at(i)=='"') { break; }
                else { ++i; }
            }
            if (i>=raw.size()) { return false; }
            int next=i+1;
            while (next<raw.size() && (raw.at(next)==' ' || raw.at(next)=='\t' || raw.at(next)=='\n' || raw.at(next)=='\r')) { ++next; }
            if (next<raw.size() && raw.at(next)==':') {
                if (stack.isEmpty() || !stack.last().object) { return false; }
                const auto decoded=QJsonDocument::fromJson(QByteArray("[")+raw.mid(start,i-start+1)+']').array();
                if (decoded.size()!=1 || !decoded.first().isString() || stack.last().keys.contains(decoded.first().toString())) { return false; }
                stack.last().keys.insert(decoded.first().toString());
            }
        }
    }
    return stack.isEmpty();
}
// Fixed app-private input only. Unlike Script.require(JSON), this reader does
// not retain the raw credential input in the CommonJS/module-code cache.
inline QJsonObject privateAndroidFeatureCommand(const QString& directory) {
#if defined(Q_OS_UNIX)
    const QFileInfo info(QDir(directory).absolutePath());
    if (info.canonicalFilePath()!=info.absoluteFilePath()) { return {}; }
    struct Handle { int fd; ~Handle() { if (fd>=0) { ::close(fd); } } };
    Handle base{::open(QFile::encodeName(info.absoluteFilePath()).constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)};
    struct stat root,rootPath;
    if (base.fd<0 || ::fstat(base.fd,&root) || !S_ISDIR(root.st_mode)
            || root.st_uid!=::geteuid() || (root.st_mode&0777)!=0700) { return {}; }
    constexpr auto name="android-control-command.json";
    Handle input{::openat(base.fd,name,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC)};
    struct stat before,after,path;
    if (input.fd<0 || ::fstat(input.fd,&before) || !S_ISREG(before.st_mode) || before.st_uid!=::geteuid()
            || (before.st_mode&0777)!=0600 || before.st_nlink!=1 || before.st_size<1 || before.st_size>16384) { return {}; }
    QByteArray raw;char buffer[4096];
    while (raw.size()<=16384) {
        const auto count=::read(input.fd,buffer,sizeof(buffer));
        if (count<0) { return {}; }
        if (!count) { break; }
        raw.append(buffer,static_cast<int>(count));
    }
    if (raw.size()>16384 || ::fstat(input.fd,&after) || ::fstatat(base.fd,name,&path,AT_SYMLINK_NOFOLLOW)
            || ::lstat(QFile::encodeName(info.absoluteFilePath()).constData(),&rootPath)
            || !S_ISDIR(rootPath.st_mode) || rootPath.st_uid!=::geteuid() || (rootPath.st_mode&0777)!=0700
            || root.st_dev!=rootPath.st_dev || root.st_ino!=rootPath.st_ino
            || !S_ISREG(path.st_mode) || path.st_dev!=before.st_dev || path.st_ino!=before.st_ino
            || path.st_uid!=::geteuid() || (path.st_mode&0777)!=0600 || path.st_nlink!=1 || path.st_size!=before.st_size
            || after.st_size!=before.st_size || raw.size()!=before.st_size || after.st_nlink!=1
            || after.st_uid!=::geteuid() || (after.st_mode&0777)!=0600
            || before.st_mtime!=after.st_mtime || before.st_ctime!=after.st_ctime) { return {}; }
    QJsonParseError error;
    const auto document=QJsonDocument::fromJson(raw,&error);
    // Preserve valid existing numeric/Unicode encodings without a CommonJS
    // cache; reject duplicate member names before the closed action validator.
    if (error.error!=QJsonParseError::NoError || !document.isObject()
            || !uniqueFeatureCommandKeys(raw)) { return {}; }
    return document.object();
#else
    Q_UNUSED(directory)
    return {};
#endif
}
} // namespace overte::e2e
