// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QUrl>
#if defined(Q_OS_UNIX)
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace overte::e2e {
// Read only an explicitly provisioned private origin. This never configures the
// product account endpoint or changes native TLS trust.
inline QString privateAccountOrigin(const QString& directory, const QString& run) {
#if defined(Q_OS_UNIX)
    const QFileInfo info(QDir(directory).absolutePath());
    if (info.canonicalFilePath() != info.absoluteFilePath()) { return {}; }
    struct Handle { int fd; ~Handle() { if (fd >= 0) { ::close(fd); } } };
    Handle base{::open(QFile::encodeName(info.absoluteFilePath()).constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)};
    struct stat root,rootPath;
    if (base.fd < 0 || ::fstat(base.fd,&root) || !S_ISDIR(root.st_mode)
            || root.st_uid != ::geteuid() || (root.st_mode & 0777) != 0700) { return {}; }
    Handle file{::openat(base.fd,"feature-account-origin.v1.json",O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC)};
    struct stat before,after,path;
    if (file.fd < 0 || ::fstat(file.fd,&before) || !S_ISREG(before.st_mode) || before.st_uid != ::geteuid()
            || (before.st_mode & 0777) != 0600 || before.st_nlink != 1 || before.st_size < 1 || before.st_size > 4096) { return {}; }
    QByteArray raw; char chunk[4097];
    while (raw.size() <= 4096) {
        const auto count = ::read(file.fd,chunk,4097-raw.size());
        if (count < 0) { return {}; }
        if (!count) { break; }
        raw.append(chunk,static_cast<int>(count));
    }
    if (raw.size() > 4096 || ::fstat(file.fd,&after) || ::fstatat(base.fd,"feature-account-origin.v1.json",&path,AT_SYMLINK_NOFOLLOW)
            || ::lstat(QFile::encodeName(info.absoluteFilePath()).constData(),&rootPath)
            || rootPath.st_uid != ::geteuid() || (rootPath.st_mode & 0777) != 0700
            || rootPath.st_dev != root.st_dev || rootPath.st_ino != root.st_ino || !S_ISDIR(rootPath.st_mode)
            || path.st_dev != before.st_dev || path.st_ino != before.st_ino || !S_ISREG(path.st_mode)
            || path.st_uid != ::geteuid() || (path.st_mode & 0777) != 0600 || path.st_nlink != 1 || path.st_size != before.st_size
            || after.st_size != before.st_size || after.st_nlink != 1 || after.st_uid != ::geteuid()
            || (after.st_mode & 0777) != 0600 || raw.size() != after.st_size) { return {}; }
    QJsonParseError error;
    const auto document=QJsonDocument::fromJson(raw,&error);
    const auto value=document.object();
    // Canonical bytes also reject duplicate keys and ambiguous alternate encodings.
    if (error.error != QJsonParseError::NoError || !document.isObject() || value.size() != 3
            || raw != document.toJson(QJsonDocument::Compact)+'\n'
            || value.value("schemaVersion") != QJsonValue(1) || value.value("runId") != QJsonValue(run)
            || !value.value("origin").isString()) { return {}; }
    const auto text=value.value("origin").toString();
    const QUrl origin(text,QUrl::StrictMode);
    if (text.isEmpty() || text.size() > 1024 || !origin.isValid() || origin.isRelative()
            || origin.scheme() != "https" || origin.host().isEmpty() || !origin.userInfo().isEmpty()
            || !origin.path().isEmpty() || origin.hasQuery() || origin.hasFragment()
            || QString::fromLatin1(origin.toEncoded()) != text) { return {}; }
    return text;
#else
    Q_UNUSED(directory)
    Q_UNUSED(run)
    return {}; // No permissive filesystem fallback.
#endif
}
} // namespace overte::e2e
