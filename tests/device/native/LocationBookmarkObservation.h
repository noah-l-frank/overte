// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCryptographicHash>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QVariantMap>
#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace overte::e2e {
inline QString bookmarkDigest(const QByteArray& bytes) {
    return QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
}

inline QByteArray bookmarkRevision(const struct stat& value) {
    // Nanosecond times must never pass through a JSON double. No filename,
    // inode, UID or private bookmark text leaves the native observation.
    QByteArray result;
    for (const auto field : { static_cast<qint64>(value.st_dev), static_cast<qint64>(value.st_ino),
            static_cast<qint64>(value.st_size), static_cast<qint64>(value.st_mtim.tv_sec),
            static_cast<qint64>(value.st_mtim.tv_nsec), static_cast<qint64>(value.st_ctim.tv_sec),
            static_cast<qint64>(value.st_ctim.tv_nsec), static_cast<qint64>(value.st_nlink) }) {
        result += QByteArray::number(field) + '\n';
    }
    return result;
}

inline bool bookmarkObservationCommand(const QVariantMap& value) {
    // V8's actual QVariantMap demarshaller represents JS numbers as doubles.
    // Preserve the exact numeric version and reject bool/string aliases.
    const auto object = QJsonObject::fromVariantMap(value);const auto keys = object.keys();
    return QSet<QString>(keys.begin(), keys.end()) == QSet<QString>{"schemaVersion", "commandId", "action", "runId"}
        && object.value("schemaVersion") == QJsonValue(1)
        && object.value("action") == QJsonValue("feature-location-bookmarks")
        && object.value("commandId").isString() && object.value("runId").isString()
        && QRegularExpression("\\A[0-9a-f]{32}\\z").match(object.value("commandId").toString()).hasMatch()
        && QRegularExpression("\\A[0-9a-f]{32}\\z").match(object.value("runId").toString()).hasMatch();
}

// Called only by LocationBookmarks on its owning GUI thread. This inspects the
// real protected map and backing file; it never reloads, writes or repairs them.
inline QVariantMap locationBookmarkStorage(const QVariantMap& bookmarks, const QString& filename,
        const QString& error, const QString& run) {
    constexpr qint64 MAX_BYTES = 4 * 1024 * 1024;
    if (!error.isEmpty() || filename.isEmpty() || bookmarks.size() > 4096
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    for (auto it = bookmarks.cbegin(); it != bookmarks.cend(); ++it) {
        if (it.key().isEmpty() || it.key().size() > 4096 || it.value().userType() != QMetaType::QString
                || it.value().toString().size() > 8192) { return {}; }
    }
    const auto mapBytes = QJsonDocument(QJsonObject::fromVariantMap(bookmarks)).toJson(QJsonDocument::Compact);
    if (mapBytes.size() > MAX_BYTES) { return {}; }
    QVariant fileValue;
    bool matches {false};
    const auto path = QFile::encodeName(filename);
    struct stat before {}, opened {}, after {}, pathAfter {};
    if (::lstat(path.constData(), &before) != 0) {
        if (errno != ENOENT || !bookmarks.isEmpty()) { return {}; }
        // Absence is a legitimate original empty store, never a created file.
        matches = true;
    } else {
        if (!S_ISREG(before.st_mode) || before.st_uid != ::geteuid() || before.st_size < 0
                || before.st_size > MAX_BYTES || before.st_nlink != 1) { return {}; }
        const auto descriptor = ::open(path.constData(), O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
        if (descriptor < 0) { return {}; }
        QFile file;
        if (!file.open(descriptor, QIODevice::ReadOnly, QFileDevice::AutoCloseHandle)) {
            ::close(descriptor);return {};
        }
        if (::fstat(descriptor, &opened) != 0 || !S_ISREG(opened.st_mode)
                || bookmarkRevision(before) != bookmarkRevision(opened)) { return {}; }
        const auto bytes = file.read(MAX_BYTES + 1);
        if (file.error() != QFileDevice::NoError || bytes.size() != opened.st_size
                || ::fstat(descriptor, &after) != 0 || ::lstat(path.constData(), &pathAfter) != 0
                || !S_ISREG(pathAfter.st_mode) || bookmarkRevision(opened) != bookmarkRevision(after)
                || bookmarkRevision(after) != bookmarkRevision(pathAfter)) { return {}; }
        QJsonParseError parse;
        const auto disk = QJsonDocument::fromJson(bytes, &parse);
        if (parse.error != QJsonParseError::NoError || !disk.isObject()) { return {}; }
        matches = disk.object() == QJsonObject::fromVariantMap(bookmarks);
        fileValue = QVariantMap{{"bytes", bytes.size()}, {"sha256", bookmarkDigest(bytes)},
            {"revisionSha256", bookmarkDigest(bookmarkRevision(after))}};
    }
    QVariantList owned;
    auto unowned = bookmarks;
    for (const auto& name : {QString("e2e-") + run, QString("renamed-") + run}) {
        if (bookmarks.contains(name)) {
            owned.append(QVariantMap{{"name", name}, {"addressSha256", bookmarkDigest(bookmarks.value(name).toString().toUtf8())}});
            unowned.remove(name);
        }
    }
    return {{"count", bookmarks.size()}, {"mapSha256", bookmarkDigest(mapBytes)},
        {"unownedCount", unowned.size()},
        {"unownedSha256", bookmarkDigest(QJsonDocument(QJsonObject::fromVariantMap(unowned)).toJson(QJsonDocument::Compact))},
        {"owned", owned}, {"storageMatches", matches}, {"file", fileValue}};
}
}
#endif
