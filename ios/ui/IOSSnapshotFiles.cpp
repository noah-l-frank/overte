// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "IOSSnapshotFiles.h"

#if defined(OVERTE_IOS_E2E_TEST_BUILD)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QRegularExpression>
#include <QSet>
#include <algorithm>
#include <cerrno>
#include <cmath>
#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include "ui/SnapshotStorage.h"

namespace overte::ios {
namespace {
constexpr qint64 MAX_BYTES = 256LL * 1024 * 1024;
constexpr qint64 CHUNK_BYTES = 4 * 1024 * 1024;
constexpr qint64 BOUNDED_CHUNK_BYTES = 512 * 1024;
const QString PREFIX = QStringLiteral("parity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)");

bool matches(const QString& pattern, const QJsonValue& value) {
    return value.isString() && QRegularExpression(QStringLiteral("\\A(?:") + pattern + QStringLiteral(")\\z"))
        .match(value.toString()).hasMatch();
}

bool filename(const QString& prefix, const QString& name) {
    return matches(QRegularExpression::escape(prefix) +
        QStringLiteral("-snap_[0-9]{1,20}_[0-9]{1,10}\\.(png|jpg|jpeg|webp|gif)"), name);
}

class Descriptor {
public:
    explicit Descriptor(int descriptor) : value(descriptor) {}
    ~Descriptor() { if (value >= 0) { ::close(value); } }
    Descriptor(const Descriptor&) = delete;
    Descriptor& operator=(const Descriptor&) = delete;
    int value;
};

QString revision(const struct stat& value) {
#if defined(__APPLE__)
    const auto modified = value.st_mtimespec;
    const auto changed = value.st_ctimespec;
#else
    const auto modified = value.st_mtim;
    const auto changed = value.st_ctim;
#endif
    const auto bytes = QStringLiteral("%1:%2:%3:%4:%5:%6:%7:%8:%9:%10")
        .arg(qulonglong(value.st_dev)).arg(qulonglong(value.st_ino)).arg(qlonglong(value.st_size))
        .arg(qulonglong(value.st_mode)).arg(qulonglong(value.st_nlink))
        .arg(qlonglong(modified.tv_sec)).arg(qlonglong(modified.tv_nsec))
        .arg(qlonglong(changed.tv_sec)).arg(qlonglong(changed.tv_nsec)).arg(qulonglong(value.st_uid)).toLatin1();
    return QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
}

struct stat metadata(int directory, const QByteArray& name, int descriptor) {
    struct stat opened {}, path {};
    if (::fstat(descriptor, &opened) != 0
            || ::fstatat(directory, name.constData(), &path, AT_SYMLINK_NOFOLLOW) != 0
            || !S_ISREG(opened.st_mode) || opened.st_nlink != 1 || opened.st_size < 0
            || opened.st_size > MAX_BYTES || revision(opened) != revision(path)) {
        throw "snapshot-original-file-invalid-or-changed";
    }
    return opened;
}

QByteArray bytes(int descriptor, qint64 maximum) {
    QByteArray result;
    while (result.size() < maximum) {
        char buffer[64 * 1024];
        const auto amount = ::read(descriptor, buffer,
            static_cast<size_t>(std::min<qint64>(sizeof(buffer), maximum - result.size())));
        if (amount < 0 && errno == EINTR) { continue; }
        if (amount < 0) { throw "snapshot-original-read-failed"; }
        if (amount == 0) { break; }
        result.append(buffer, static_cast<int>(amount));
    }
    return result;
}

QJsonObject inspect(int directory, const QString& name) {
    const auto encoded = name.toUtf8();
    Descriptor opened(::openat(directory, encoded.constData(), O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC));
    if (opened.value < 0) { throw "snapshot-original-open-failed"; }
    const auto before = metadata(directory, encoded, opened.value);
    QCryptographicHash hash(QCryptographicHash::Sha256);
    qint64 readBytes { 0 };
    while (true) {
        const auto chunk = bytes(opened.value, std::min<qint64>(CHUNK_BYTES, MAX_BYTES + 1 - readBytes));
        if (chunk.isEmpty()) { break; }
        readBytes += chunk.size();
        if (readBytes > MAX_BYTES) { throw "snapshot-original-too-large"; }
        hash.addData(chunk);
    }
    const auto after = metadata(directory, encoded, opened.value);
    if (revision(before) != revision(after) || readBytes != before.st_size) { throw "snapshot-original-file-changed"; }
    return { { "name", name }, { "size", static_cast<double>(readBytes) },
        { "revision", revision(after) }, { "sha256", QString::fromLatin1(hash.result().toHex()) } };
}

QJsonArray manifest(int directory, const QString& prefix) {
    const int copied = ::dup(directory);
    if (copied < 0) { throw "snapshot-directory-open-failed"; }
    DIR* stream = ::fdopendir(copied);
    if (!stream) { ::close(copied); throw "snapshot-directory-open-failed"; }
    QStringList names;
    try {
        int visited { 0 };
        while (true) {
            errno = 0;
            const auto entry = ::readdir(stream);
            if (!entry) {
                if (errno) { throw "snapshot-directory-read-failed"; }
                break;
            }
            if (++visited > 4096) { throw "snapshot-directory-bound-exceeded"; }
            const QByteArray raw(entry->d_name);
            if (!raw.startsWith(prefix.toUtf8())) { continue; }
            const auto name = QString::fromUtf8(raw);
            if (name.toUtf8() != raw || !filename(prefix, name) || names.size() >= 8 || names.contains(name)) {
                throw "snapshot-original-name-or-count-invalid";
            }
            names.append(name);
        }
    } catch (...) { ::closedir(stream); throw; }
    ::closedir(stream);
    names.sort();
    QJsonArray result;
    qint64 total { 0 };
    for (const auto& name : names) {
        const auto row = inspect(directory, name);
        total += static_cast<qint64>(row.value("size").toDouble());
        if (total > MAX_BYTES) { throw "snapshot-original-total-too-large"; }
        result.append(row);
    }
    return result;
}
} // namespace

bool validSnapshotFileRequest(const QJsonObject& command) {
    const auto operation = command.value("operation").toString();
    QSet<QString> expected { "schemaVersion", "commandId", "action", "operation", "prefix" };
    if (operation == QStringLiteral("read")) { expected.unite({ "name", "revision", "offset" }); }
    const bool bounded = command.value("schemaVersion") == QJsonValue(2);
    if (bounded) { expected.insert("chunkBytes"); }
    const auto keys = command.keys();
    if (QSet<QString>(keys.begin(), keys.end()) != expected
            || (command.value("schemaVersion") != QJsonValue(1) && !bounded)
            || command.value("action") != QJsonValue(QStringLiteral("snapshot-files"))
            || !matches(QStringLiteral("ios-[0-9a-f]{32}"), command.value("commandId"))
            || !matches(PREFIX, command.value("prefix")) || (operation != "list" && operation != "read")) { return false; }
    if (bounded && (operation != "read" || command.value("chunkBytes") != QJsonValue(static_cast<double>(BOUNDED_CHUNK_BYTES)))) { return false; }
    if (operation == "list") { return true; }
    const auto offset = command.value("offset").toDouble(-1);
    return filename(command.value("prefix").toString(), command.value("name").toString())
        && matches(QStringLiteral("[0-9a-f]{64}"), command.value("revision"))
        && command.value("offset").isDouble() && std::isfinite(offset)
        && offset >= 0 && offset <= MAX_BYTES && std::floor(offset) == offset;
}

QJsonObject readSnapshotFiles(const QJsonObject& command, const QString& root) {
    if (!validSnapshotFileRequest(command)) { return {}; }
    const qint64 chunkLimit = command.value("schemaVersion") == QJsonValue(2) ? BOUNDED_CHUNK_BYTES : CHUNK_BYTES;
    QJsonObject result { { "schemaVersion", command.value("schemaVersion") }, { "commandId", command.value("commandId") },
        { "operation", command.value("operation") }, { "prefix", command.value("prefix") },
        { "processId", static_cast<double>(QCoreApplication::applicationPid()) }, { "ok", false } };
    try {
        const auto path = root.isEmpty() ? overte::snapshot::storageRoot() : root;
        if (path.isEmpty() || !QDir::isAbsolutePath(path) || QFileInfo(path).isSymLink()) {
            throw "snapshot-directory-invalid";
        }
        Descriptor directory(::open(QFile::encodeName(path).constData(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
        if (directory.value < 0) {
            if (errno != ENOENT || command.value("operation") != QJsonValue(QStringLiteral("list"))) {
                throw "snapshot-directory-unavailable";
            }
            result["files"] = QJsonArray();
        } else {
            struct stat initial {};
            if (::fstat(directory.value, &initial) != 0 || !S_ISDIR(initial.st_mode)) { throw "snapshot-directory-invalid"; }
            if (command.value("operation") == QJsonValue(QStringLiteral("list"))) {
                result["files"] = manifest(directory.value, command.value("prefix").toString());
            } else {
                const auto name = command.value("name").toString().toUtf8();
                Descriptor opened(::openat(directory.value, name.constData(), O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC));
                if (opened.value < 0) { throw "snapshot-original-open-failed"; }
                const auto before = metadata(directory.value, name, opened.value);
                const auto offset = static_cast<qint64>(command.value("offset").toDouble());
                if (revision(before) != command.value("revision").toString() || offset > before.st_size
                        || ::lseek(opened.value, static_cast<off_t>(offset), SEEK_SET) != offset) {
                    throw "snapshot-original-revision-or-offset-changed";
                }
                const auto chunk = bytes(opened.value, std::min<qint64>(chunkLimit, before.st_size - offset));
                const auto after = metadata(directory.value, name, opened.value);
                if (revision(before) != revision(after) || chunk.size() != std::min<qint64>(chunkLimit, before.st_size - offset)) {
                    throw "snapshot-original-file-changed";
                }
                result["file"] = QJsonObject { { "name", command.value("name") }, { "revision", revision(after) },
                    { "size", static_cast<double>(before.st_size) }, { "offset", static_cast<double>(offset) },
                    { "eof", offset + chunk.size() == before.st_size }, { "data", QString::fromLatin1(chunk.toBase64()) } };
            }
            struct stat current {};
            if (::stat(QFile::encodeName(path).constData(), &current) != 0 || !S_ISDIR(current.st_mode)
                    || initial.st_dev != current.st_dev || initial.st_ino != current.st_ino || QFileInfo(path).isSymLink()) {
                throw "snapshot-directory-changed";
            }
        }
        result["ok"] = true;
    } catch (const char* reason) { result.remove("files"); result.remove("file"); result["error"] = QString::fromLatin1(reason); }
    result["sampleEpochMs"] = static_cast<double>(QDateTime::currentMSecsSinceEpoch());
    return result;
}
}
#endif
