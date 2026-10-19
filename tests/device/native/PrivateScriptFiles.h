// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Closed E2E fixture storage. Never loads code or deletes an unowned directory.
#include <QByteArray>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QMap>
#include <QVariantMap>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QUrl>
#include <algorithm>
#if defined(Q_OS_UNIX)
#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <cerrno>
#endif

namespace overte::e2e {
class PrivateScriptFiles {
public:
    static QStringList names() {
        return {"script.js", "companion.js", "script-bundle/main.js", "script-bundle/companion.js"};
    }
    static QVariantMap request(const QString& directory, const QVariantMap& command) {
#if defined(Q_OS_UNIX)
        const auto run = command.value("runId").toString();
        const auto owner = command.value("ownerToken").toString();
        const auto action = command.value("operation").toString();
        if (!QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{64}\\z").match(owner).hasMatch()
                || (action != "stage" && action != "observe" && action != "release")) { return {}; }
        const auto basePath = QDir(directory).absolutePath();
        const QFileInfo info(basePath);
        if (!info.isAbsolute() || info.canonicalFilePath() != info.absoluteFilePath()) { return {}; }
        Handle base(::open(QFile::encodeName(basePath).constData(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
        if (!privateNode(base.fd, true) || !samePath(base.fd, QFile::encodeName(basePath))) { return {}; }
        const auto leaf = ("feature-script-" + run).toLatin1();
        if (action == "stage") {
            const auto files = command.value("files").toMap();
            auto keys = files.keys(); auto wanted = names(); keys.sort(); wanted.sort();
            if (keys != wanted) { return {}; }
            QMap<QString, QByteArray> bytes;
            QJsonObject hashes;
            for (const auto& name : names()) {
                if (files.value(name).userType() != QMetaType::QString) { return {}; }
                const auto encoded = files.value(name).toString().toLatin1();
                if (encoded.isEmpty() || encoded.size() > 16384) { return {}; }
                const auto original = QByteArray::fromBase64(encoded);
                if (original.isEmpty() || original.size() > 8192 || original.toBase64() != encoded) { return {}; }
                bytes[name] = original;
                hashes[name] = QString::fromLatin1(QCryptographicHash::hash(original, QCryptographicHash::Sha256).toHex());
            }
            // mkdirat is exclusive. A retry cannot adopt or overwrite an old root.
            if (::mkdirat(base.fd, leaf.constData(), 0700) != 0) { return {}; }
            Handle root(::openat(base.fd, leaf.constData(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
            if (!privateNode(root.fd, true)) { return {}; }
            // Persist ownership before creating fixtures. A partial stage remains
            // observable and can only be cleaned using this exact private token.
            QJsonObject manifest{{"schemaVersion", 1}, {"runId", run}, {"ownerToken", owner}, {"hashes", hashes}};
            if (!writeNew(root.fd, ".owner.v1.json", QJsonDocument(manifest).toJson(QJsonDocument::Compact))
                    || ::mkdirat(root.fd, "script-bundle", 0700) != 0) { return {}; }
            Handle bundle(::openat(root.fd, "script-bundle", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
            if (!privateNode(bundle.fd, true)) { return {}; }
            for (const auto& name : names()) {
                if (!writeNew(name.startsWith("script-bundle/") ? bundle.fd : root.fd,
                        QFile::encodeName(name.section('/', -1)), bytes[name])) { return {}; }
            }
            if (::fsync(bundle.fd) != 0 || ::fsync(root.fd) != 0 || ::fsync(base.fd) != 0) { return {}; }
            return {{"performed", true}}; // Separate original read establishes contents.
        }
        Handle root(::openat(base.fd, leaf.constData(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
        if (root.fd < 0) {
            if (errno != ENOENT) { return {}; }
            return action == "observe" ? QVariantMap{{"exists", false}, {"files", QVariantList{}}}
                                       : QVariantMap{{"performed", true}};
        }
        if (!privateNode(root.fd, true)) { return {}; }
        QByteArray raw;
        if (!readFile(root.fd, ".owner.v1.json", raw, 4096)) { return {}; }
        QJsonParseError parse;
        const auto document = QJsonDocument::fromJson(raw, &parse);
        const auto manifest = document.object();
        if (parse.error != QJsonParseError::NoError || !document.isObject()
                || manifest.size() != 4 || manifest.value("schemaVersion") != QJsonValue(1)
                || manifest.value("runId") != QJsonValue(run) || manifest.value("ownerToken") != QJsonValue(owner)
                || !manifest.value("hashes").isObject()) { return {}; }
        const auto hashes = manifest.value("hashes").toObject();
        auto keys = hashes.keys(); auto wanted = names(); keys.sort(); wanted.sort();
        if (keys != wanted || !entries(root.fd, {".owner.v1.json", "script.js", "companion.js", "script-bundle"})) { return {}; }
        Handle bundle(::openat(root.fd, "script-bundle", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
        const bool bundleMissing = bundle.fd < 0 && errno == ENOENT;
        if (!bundleMissing && (!privateNode(bundle.fd, true) || !entries(bundle.fd, {"main.js", "companion.js"}))) { return {}; }
        QVariantList files;
        // Validate the entire inventory before removing anything. A changed,
        // shared, symlinked, oversized or unexpected file prevents release.
        for (const auto& name : names()) {
            const auto digest = hashes.value(name).toString();
            if (!QRegularExpression("\\A[0-9a-f]{64}\\z").match(digest).hasMatch()) { return {}; }
            const int parent = name.startsWith("script-bundle/") ? bundle.fd : root.fd;
            const auto local = QFile::encodeName(name.section('/', -1));
            QByteArray bytes;
            bool missing = parent < 0;
            if (!missing) {
                struct stat status;
                if (::fstatat(parent, local.constData(), &status, AT_SYMLINK_NOFOLLOW) != 0) {
                    if (errno != ENOENT) { return {}; }
                    missing = true;
                }
            }
            if (missing) { files.append(QVariantMap{{"name", name}, {"exists", false}}); continue; }
            if (!readFile(parent, local, bytes, 8192)) { return {}; }
            const auto actual = QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex();
            if (QString::fromLatin1(actual) != digest) { return {}; }
            files.append(QVariantMap{{"name", name}, {"exists", true}, {"bytes", bytes.size()},
                {"sha256", QString::fromLatin1(actual)}, {"base64", QString::fromLatin1(bytes.toBase64())}});
        }
        if (!samePath(base.fd, QFile::encodeName(basePath)) || !sameChild(base.fd, leaf, root.fd)) { return {}; }
        if (action == "observe") {
            return {{"exists", true}, {"directory", QUrl::fromLocalFile(QDir(directory).filePath(QString::fromLatin1(leaf))).toString()},
                    {"files", files}};
        }
        for (const auto& file : files) {
            const auto row = file.toMap();
            if (!row.value("exists").toBool()) { continue; }
            const auto name = row.value("name").toString();
            const int parent = name.startsWith("script-bundle/") ? bundle.fd : root.fd;
            if (::unlinkat(parent, QFile::encodeName(name.section('/', -1)).constData(), 0) != 0) { return {}; }
        }
        if ((!bundleMissing && ::unlinkat(root.fd, "script-bundle", AT_REMOVEDIR) != 0)
                || ::unlinkat(root.fd, ".owner.v1.json", 0) != 0
                || ::unlinkat(base.fd, leaf.constData(), AT_REMOVEDIR) != 0 || ::fsync(base.fd) != 0) { return {}; }
        return {{"performed", true}}; // Caller must request a fresh absence read.
#else
        Q_UNUSED(directory)
        Q_UNUSED(command)
        return {}; // No insecure portability fallback.
#endif
    }
private:
#if defined(Q_OS_UNIX)
    struct Handle {
        int fd;
        explicit Handle(int descriptor) : fd(descriptor) {}
        ~Handle() { if (fd >= 0) { ::close(fd); } }
        Handle(const Handle&) = delete;
        Handle& operator=(const Handle&) = delete;
    };
    static bool privateNode(int fd, bool directory) {
        struct stat value;
        return fd >= 0 && ::fstat(fd, &value) == 0 && value.st_uid == ::geteuid()
            && (value.st_mode & 0777) == (directory ? 0700 : 0600) && (directory ? S_ISDIR(value.st_mode) : S_ISREG(value.st_mode) && value.st_nlink == 1);
    }
    static bool samePath(int fd, const QByteArray& path) {
        struct stat opened, current;
        return ::fstat(fd, &opened) == 0 && ::lstat(path.constData(), &current) == 0
            && S_ISDIR(current.st_mode) && opened.st_dev == current.st_dev && opened.st_ino == current.st_ino;
    }
    static bool sameChild(int parent, const QByteArray& name, int fd) {
        struct stat opened, current;
        return ::fstat(fd, &opened) == 0 && ::fstatat(parent, name.constData(), &current, AT_SYMLINK_NOFOLLOW) == 0
            && S_ISDIR(current.st_mode) && opened.st_dev == current.st_dev && opened.st_ino == current.st_ino;
    }
    static bool writeNew(int parent, const QByteArray& name, const QByteArray& bytes) {
        Handle file(::openat(parent, name.constData(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600));
        if (!privateNode(file.fd, false)) { return false; }
        qint64 done { 0 };
        while (done < bytes.size()) {
            const auto count = ::write(file.fd, bytes.constData() + done, bytes.size() - done);
            if (count < 0 && errno == EINTR) { continue; }
            if (count <= 0) { return false; }
            done += count;
        }
        return ::fsync(file.fd) == 0;
    }
    static bool readFile(int parent, const QByteArray& name, QByteArray& bytes, int maximum) {
        Handle file(::openat(parent, name.constData(), O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK));
        if (!privateNode(file.fd, false)) { return false; }
        struct stat before, after;
        if (::fstat(file.fd, &before) != 0 || before.st_size <= 0 || before.st_size > maximum) { return false; }
        bytes.clear(); bytes.reserve(static_cast<int>(before.st_size));
        char buffer[4096];
        for (;;) {
            const auto count = ::read(file.fd, buffer, sizeof(buffer));
            if (count < 0 && errno == EINTR) { continue; }
            if (count < 0 || bytes.size() + count > maximum) { return false; }
            if (count == 0) { break; }
            bytes.append(buffer, static_cast<int>(count));
        }
        return ::fstat(file.fd, &after) == 0 && before.st_dev == after.st_dev && before.st_ino == after.st_ino
            && before.st_size == after.st_size && before.st_mtime == after.st_mtime && before.st_ctime == after.st_ctime
            && bytes.size() == before.st_size && privateNode(file.fd, false);
    }
    static bool entries(int parent, const QStringList& allowed) {
        const int copy = ::dup(parent);
        if (copy < 0) { return false; }
        DIR* directory = ::fdopendir(copy);
        if (!directory) { ::close(copy); return false; }
        bool valid { true }; int count { 0 }; errno = 0;
        while (auto entry = ::readdir(directory)) {
            const auto name = QString::fromLocal8Bit(entry->d_name);
            if (name == "." || name == "..") { continue; }
            if (++count > 4 || !allowed.contains(name)) { valid = false; break; }
        }
        valid = valid && errno == 0;
        ::closedir(directory);
        return valid;
    }
#endif
};
} // namespace overte::e2e
