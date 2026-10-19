// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QSaveFile>

namespace overte::e2e {
inline bool previewDirectory(const QString& path) {
    const QFileInfo info(QDir(path).absolutePath());
    return info.exists() && info.isDir() && !info.isSymLink()
        && info.canonicalFilePath() == info.absoluteFilePath()
        && !(info.permissions() & (QFile::ReadGroup | QFile::WriteGroup | QFile::ExeGroup
            | QFile::ReadOther | QFile::WriteOther | QFile::ExeOther));
}
inline bool ownPreviewFile(const QString& path, const QByteArray& digest) {
    const QFileInfo info(path);
    if (info.isSymLink()) { return false; }
    if (!info.exists()) { return digest.isEmpty(); }
    if (digest.isEmpty() || !info.isFile() || info.size() > 32 * 1024 * 1024
            || info.permissions() & (QFile::ReadGroup | QFile::WriteGroup | QFile::ExeGroup
                | QFile::ReadOther | QFile::WriteOther | QFile::ExeOther)) { return false; }
    QFile input(path);
    return input.open(QIODevice::ReadOnly)
        && QCryptographicHash::hash(input.readAll(), QCryptographicHash::Sha256).toHex() == digest;
}
inline bool writePreviewFile(const QString& path, const QByteArray& bytes, QByteArray& digest) {
    if (bytes.size() > 32 * 1024 * 1024 || !ownPreviewFile(path, digest)) { return false; }
    QSaveFile output(path);
    output.setDirectWriteFallback(false);
    if (!output.open(QIODevice::WriteOnly) || !output.setPermissions(QFile::ReadOwner | QFile::WriteOwner)
            || output.write(bytes) != bytes.size() || !output.commit()) { return false; }
    digest = QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex();
    return true;
}
inline bool removePreviewFile(const QString& path, QByteArray& digest) {
    if (!ownPreviewFile(path, digest)) { return false; }
    if (!digest.isEmpty() && !QFile::remove(path)) { return false; }
    digest.clear();
    return true;
}
} // namespace overte::e2e
