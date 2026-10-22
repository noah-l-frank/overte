// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "PrivateScriptFiles.h"

namespace overte::e2e {
// Explicit Create JSON source role. Stage writes only controlled INPUT bytes;
// export.json is never created here. Only the ordinary product Save route may
// produce that original. No Script root/name or picker is admitted by this role.
class PrivateCreateFiles {
public:
    static QVariantMap request(const QString& directory, const QVariantMap& command) {
#if defined(Q_OS_UNIX) && defined(OVERTE_E2E_FEATURE_TESTS)
        if (command.value("sourceRole") != QVariant("create-json-v1")) { return {}; }
        const auto run = command.value("runId").toString(), ticket = command.value("ticket").toString();
        const auto owner = command.value("ownerToken").toString(), action = command.value("operation").toString();
        const QRegularExpression id("\\A[0-9a-f]{32}\\z"), digest("\\A[0-9a-f]{64}\\z");
        if (!id.match(run).hasMatch() || !id.match(ticket).hasMatch() || !digest.match(owner).hasMatch()
                || !QStringList{"stage", "observe", "release", "locate"}.contains(action)) { return {}; }
        for (const auto& key : QStringList{"sourceRole", "runId", "ticket", "ownerToken", "operation", "action", "commandId"}) {
            if (command.value(key).userType() != QMetaType::QString) { return {}; }
        }
        QStringList wanted{"schemaVersion", "commandId", "action", "sourceRole", "operation", "runId", "ticket", "ownerToken"};
        if (action == "stage") { wanted.append("files"); }
        if (action == "release") { wanted.append("exportSha256"); }
        auto keys = command.keys(); wanted.sort(); keys.sort();
        if (keys != wanted || QJsonObject::fromVariantMap(command).value("schemaVersion") != QJsonValue(1)
                || command.value("action") != QVariant("feature-script-files")
                || !id.match(command.value("commandId").toString()).hasMatch()) { return {}; }
        if (action == "release" && (command.value("exportSha256").userType() != QMetaType::QString
                || (!command.value("exportSha256").toString().isEmpty() && !digest.match(command.value("exportSha256").toString()).hasMatch()))) { return {}; }
        const auto basePath = QDir(directory).absolutePath(); const QFileInfo info(basePath);
        if (!QFileInfo(directory).isAbsolute() || QDir::cleanPath(directory) != directory
                || !info.isAbsolute() || info.canonicalFilePath() != info.absoluteFilePath()) { return {}; }
        Handle base(::open(QFile::encodeName(basePath).constData(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
        if (!Safe::privateNode(base.fd, true) || !Safe::samePath(base.fd, QFile::encodeName(basePath))) { return {}; }
        const auto leaf = ("feature-create-" + run + '-' + ticket).toLatin1();
        if (action == "stage") {
            const auto files = command.value("files").toMap();
            if (files.keys() != QStringList{"entity-import.json"} || files.value("entity-import.json").userType() != QMetaType::QString) { return {}; }
            const auto encoded = files.value("entity-import.json").toString().toLatin1();
            const auto bytes = QByteArray::fromBase64(encoded);
            if (encoded.size() > 16384 || bytes.isEmpty() || bytes.size() > 8192 || bytes.toBase64() != encoded) { return {}; }
            QJsonParseError error; const auto input = QJsonDocument::fromJson(bytes, &error);
            const auto object = input.object();
            if (error.error != QJsonParseError::NoError || !input.isObject()
                    || object.value("DataVersion") != QJsonValue(3) || !object.value("Entities").isArray()
                    || object.value("Entities").toArray().size() != 1) { return {}; }
            if (::mkdirat(base.fd, leaf.constData(), 0700) != 0) { return {}; }
            Handle root(::openat(base.fd, leaf.constData(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
            if (!Safe::privateNode(root.fd, true)) { return {}; }
            const QJsonObject manifest{{"schemaVersion", 1}, {"sourceRole", "create-json-v1"},
                {"runId", run}, {"ticket", ticket}, {"ownerToken", owner},
                {"inputSha256", QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex())}};
            if (!Safe::writeNew(root.fd, ".owner.create.v1.json", QJsonDocument(manifest).toJson(QJsonDocument::Compact))
                    || !Safe::writeNew(root.fd, "entity-import.json", bytes) || ::fsync(root.fd) != 0 || ::fsync(base.fd) != 0
                    || !Safe::samePath(base.fd, QFile::encodeName(basePath)) || !Safe::sameChild(base.fd, leaf, root.fd)) { return {}; }
            return {{"performed", true}};
        }
        Handle root(::openat(base.fd, leaf.constData(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
        if (root.fd < 0) {
            if (errno != ENOENT) { return {}; }
            if (action == "locate") { return location(basePath, leaf, false); }
            return action == "observe" ? QVariantMap{{"exists", false}, {"files", QVariantList{}}} : QVariantMap{{"performed", true}};
        }
        if (!Safe::privateNode(root.fd, true) || !Safe::entries(root.fd, {".owner.create.v1.json", "entity-import.json", "export.json"})) { return {}; }
        QByteArray raw;
        if (!Safe::readFile(root.fd, ".owner.create.v1.json", raw, 4096)) { return {}; }
        QJsonParseError error; const auto document = QJsonDocument::fromJson(raw, &error); const auto manifest = document.object();
        if (error.error != QJsonParseError::NoError || !document.isObject() || manifest.size() != 6
                || raw != QJsonDocument(manifest).toJson(QJsonDocument::Compact)
                || manifest.value("schemaVersion") != QJsonValue(1) || manifest.value("sourceRole") != QJsonValue("create-json-v1")
                || manifest.value("runId") != QJsonValue(run) || manifest.value("ticket") != QJsonValue(ticket)
                || manifest.value("ownerToken") != QJsonValue(owner) || !digest.match(manifest.value("inputSha256").toString()).hasMatch()) { return {}; }
        if (!Safe::samePath(base.fd, QFile::encodeName(basePath)) || !Safe::sameChild(base.fd, leaf, root.fd)) { return {}; }
        if (action == "locate") { return location(basePath, leaf, true); }
        const auto input = readOriginal(root.fd, "entity-import.json", false);
        const auto output = readOriginal(root.fd, "export.json", true);
        if (input.isEmpty() || output.isEmpty()
                || (input.value("exists").toBool() && input.value("sha256").toString() != manifest.value("inputSha256").toString())) { return {}; }
        if (!Safe::samePath(base.fd, QFile::encodeName(basePath)) || !Safe::sameChild(base.fd, leaf, root.fd)) { return {}; }
        if (action == "observe") {
            return {{"exists", true}, {"directory", location(basePath, leaf, true).value("directory")},
                {"files", QVariantList{input, output}}};
        }
        if (command.value("exportSha256").userType() != QMetaType::QString) { return {}; }
        const auto expectedOutput = command.value("exportSha256").toString();
        if ((!expectedOutput.isEmpty() && !digest.match(expectedOutput).hasMatch())
                || (output.value("exists").toBool() && output.value("sha256") != QVariant(expectedOutput))) { return {}; }
        // Re-read every existing original immediately before unlink. No changed
        // inode, bytes, mode or nanosecond clock can inherit the earlier grant.
        if (readOriginal(root.fd, "entity-import.json", false) != input || readOriginal(root.fd, "export.json", true) != output) { return {}; }
        for (const auto& row : QVariantList{input, output}) {
            const auto file = row.toMap();
            if (file.value("exists").toBool() && ::unlinkat(root.fd, file.value("name").toString().toLatin1().constData(), 0) != 0) { return {}; }
        }
        if (::unlinkat(root.fd, ".owner.create.v1.json", 0) != 0 || ::unlinkat(base.fd, leaf.constData(), AT_REMOVEDIR) != 0 || ::fsync(base.fd) != 0) { return {}; }
        return {{"performed", true}};
#else
        Q_UNUSED(directory) Q_UNUSED(command)
        return {};
#endif
    }
private:
#if defined(Q_OS_UNIX)
    using Safe = PrivateScriptFiles;
    using Handle = PrivateScriptFiles::Handle;
    static QVariantMap location(const QString& base, const QByteArray& leaf, bool exists) {
        return {{"locationVersion", 1}, {"exists", exists},
            {"directory", QUrl::fromLocalFile(QDir(base).filePath(QString::fromLatin1(leaf))).toString()}};
    }
    static bool originalNode(int fd, bool output, struct stat& value) {
        return fd >= 0 && ::fstat(fd, &value) == 0 && S_ISREG(value.st_mode) && value.st_uid == ::geteuid() && value.st_nlink == 1
            && ((value.st_mode & 0777) == 0600 || (output && (value.st_mode & 0777) == 0644));
    }
    static QVariantMap readOriginal(int parent, const QByteArray& name, bool output) {
        Handle file(::openat(parent, name.constData(), O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK));
        if (file.fd < 0) { return errno == ENOENT ? QVariantMap{{"name", QString::fromLatin1(name)}, {"exists", false}} : QVariantMap{}; }
        struct stat before, after, current;
        if (!originalNode(file.fd, output, before) || before.st_size <= 0 || before.st_size > (output ? 32768 : 8192)) { return {}; }
        QByteArray bytes; char buffer[4096];
        for (;;) {
            const auto count = ::read(file.fd, buffer, sizeof(buffer));
            if (count < 0 && errno == EINTR) { continue; }
            if (count < 0 || bytes.size() + count > (output ? 32768 : 8192)) { return {}; }
            if (count == 0) { break; }
            bytes.append(buffer, static_cast<int>(count));
        }
        if (!originalNode(file.fd, output, after) || ::fstatat(parent, name.constData(), &current, AT_SYMLINK_NOFOLLOW) != 0
                || !S_ISREG(current.st_mode) || before.st_dev != after.st_dev || before.st_ino != after.st_ino
                || before.st_dev != current.st_dev || before.st_ino != current.st_ino || before.st_size != after.st_size
                || current.st_size != before.st_size || current.st_mode != before.st_mode || current.st_nlink != 1
                || current.st_uid != before.st_uid
                || before.st_mtim.tv_sec != after.st_mtim.tv_sec || before.st_mtim.tv_nsec != after.st_mtim.tv_nsec
                || before.st_ctim.tv_sec != after.st_ctim.tv_sec || before.st_ctim.tv_nsec != after.st_ctim.tv_nsec
                || before.st_mtim.tv_sec != current.st_mtim.tv_sec || before.st_mtim.tv_nsec != current.st_mtim.tv_nsec
                || before.st_ctim.tv_sec != current.st_ctim.tv_sec || before.st_ctim.tv_nsec != current.st_ctim.tv_nsec
                || before.st_mode != after.st_mode || bytes.size() != before.st_size) { return {}; }
        const auto nanoseconds=[](const timespec& value) { return QString::number(value.tv_sec) + '.' + QString::number(value.tv_nsec).rightJustified(9, '0'); };
        return {{"name", QString::fromLatin1(name)}, {"exists", true}, {"bytes", bytes.size()},
            {"sha256", QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex())},
            {"base64", QString::fromLatin1(bytes.toBase64())}, {"device", QString::number(before.st_dev)},
            {"inode", QString::number(before.st_ino)}, {"mode", static_cast<int>(before.st_mode & 0777)},
            {"modified", nanoseconds(before.st_mtim)}, {"changed", nanoseconds(before.st_ctim)}};
    }
#endif
};
} // namespace overte::e2e
