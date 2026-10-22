// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCryptographicHash>
#include <QFile>
#include <QVariantMap>
#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace overte::e2e {
// Only the actual AvatarBookmarks native owner supplies this fixed filename.
// No command accepts a path and no requested bookmark supplies observed bytes.
class IOSAvatarBookmarkFile {
public:
    static QVariantMap read(const QString& fileName) {
        if (fileName.isEmpty()) { return result("unavailable","location-unavailable"); }
        const auto path=QFile::encodeName(fileName);
        const int descriptor=::open(path.constData(),O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);
        if (descriptor<0) { return errno==ENOENT ? result("absent") : result("unavailable","open-error"); }
        struct stat first {},last {},named {};
        if (::fstat(descriptor,&first)!=0 || !S_ISREG(first.st_mode) || first.st_uid!=::geteuid() || first.st_nlink!=1) {
            ::close(descriptor);return result("unavailable","unsafe-file");
        }
        if (first.st_size<0 || first.st_size>65536) { ::close(descriptor);return result("unavailable","too-large"); }
        QFile input;
        if (!input.open(descriptor,QIODevice::ReadOnly,QFileDevice::AutoCloseHandle)) {
            ::close(descriptor);return result("unavailable","read-error");
        }
        const auto bytes=input.read(65537);
        if (input.error()!=QFileDevice::NoError) { return result("unavailable","read-error"); }
        if (::fstat(descriptor,&last)!=0 || ::lstat(path.constData(),&named)!=0
                || !unchanged(first,last) || !unchanged(last,named) || bytes.size()!=first.st_size) {
            return result("unavailable","changed-file");
        }
        auto value=result("ready");value["bytes"]=bytes.size();
        value["sha256"]=QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());
        value["contentBase64"]=QString::fromLatin1(bytes.toBase64());
        value["identity"]=QVariantMap {{"device",QString::number(static_cast<qulonglong>(first.st_dev))},
            {"inode",QString::number(static_cast<qulonglong>(first.st_ino))}};return value;
    }
private:
    static bool unchanged(const struct stat& first,const struct stat& last) {
        return first.st_dev==last.st_dev && first.st_ino==last.st_ino && first.st_size==last.st_size
            && first.st_mode==last.st_mode && first.st_uid==last.st_uid && first.st_nlink==last.st_nlink
            && first.st_mtimespec.tv_sec==last.st_mtimespec.tv_sec && first.st_mtimespec.tv_nsec==last.st_mtimespec.tv_nsec
            && first.st_ctimespec.tv_sec==last.st_ctimespec.tv_sec && first.st_ctimespec.tv_nsec==last.st_ctimespec.tv_nsec;
    }
    static QVariantMap result(const QString& status,const QString& reason=QString()) {
        return {{"source","avatar-bookmarks-persistence"},{"status",status},{"reason",reason},{"bytes",QVariant()},
            {"sha256",QVariant()},{"contentBase64",QVariant()},{"identity",QVariant()}};
    }
};
} // namespace overte::e2e
#endif
