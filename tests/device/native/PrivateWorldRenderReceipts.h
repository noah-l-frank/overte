// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "PrivatePreviewFiles.h"
#if defined(Q_OS_UNIX)
#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace overte::e2e {
// Receipt deletion has a stricter native file-identity boundary than the
// historical general preview helper. Unsupported hosts cannot qualify it.
inline bool ownWorldRenderReceipt(const QString& path, const QByteArray& digest) {
#if defined(Q_OS_UNIX)
    const auto encoded = QFile::encodeName(path);
    struct stat original;
    if (::lstat(encoded.constData(), &original) != 0) { return errno == ENOENT && digest.isEmpty(); }
    const auto privateRegular = [](const struct stat& info) {
        return S_ISREG(info.st_mode) && info.st_uid == ::geteuid() && info.st_nlink == 1
            && (info.st_mode & 07777) == 0600 && info.st_size >= 0 && info.st_size <= 32 * 1024 * 1024;
    };
    if (digest.isEmpty() || !privateRegular(original)) { return false; }
    const int descriptor = ::open(encoded.constData(), O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (descriptor < 0) { return false; }
    QFile input;
    if (!input.open(descriptor, QIODevice::ReadOnly, QFileDevice::AutoCloseHandle)) { ::close(descriptor); return false; }
    struct stat opened;
    if (::fstat(descriptor, &opened) != 0 || !privateRegular(opened)
            || opened.st_dev != original.st_dev || opened.st_ino != original.st_ino) { return false; }
    const auto bytes = input.read(32 * 1024 * 1024 + 1);
    struct stat finalFile, finalPath;
    return bytes.size() == original.st_size && input.atEnd()
        && QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex() == digest
        && ::fstat(descriptor, &finalFile) == 0 && ::lstat(encoded.constData(), &finalPath) == 0
        && privateRegular(finalFile) && privateRegular(finalPath)
        && finalFile.st_dev == original.st_dev && finalFile.st_ino == original.st_ino
        && finalPath.st_dev == original.st_dev && finalPath.st_ino == original.st_ino;
#else
    Q_UNUSED(path); Q_UNUSED(digest); return false;
#endif
}
} // namespace overte::e2e
