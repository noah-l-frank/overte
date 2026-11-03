// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Existing TestResults/AudioClient instrumentation, original-FD ownership
// pattern as AccountOriginLease. No audio source/mode/permission setter.
#include "PrivateAccountOrigin.h"
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QMap>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QVariantMap>
#include <functional>
#include <memory>
#include <cmath>
#include <cerrno>
#if defined(Q_OS_UNIX)
#include <dirent.h>
#endif

namespace overte::e2e {
class IOSAudioPassiveCapture {
public:
    struct Audio {
        std::function<bool(const QString&, const QString&, int)> start;
        std::function<QVariantMap()> status;
        std::function<QByteArray()> wav;
        std::function<bool(const QString&, const QString&, quint64)> release;
        std::function<bool()> admissionCurrent;
    };
    explicit IOSAudioPassiveCapture(QString instance) : _instance(std::move(instance)), _thread(QThread::currentThread()) {}

    QVariantMap request(const QString& directory, const QVariantMap& command, const Audio& audio) {
#if defined(Q_OS_UNIX)
        if (_busy || QThread::currentThread() != _thread || !QCoreApplication::arguments().contains("--testScript") ||
                !audio.start || !audio.status || !audio.wav || !audio.release || !audio.admissionCurrent) { return {}; }
        const auto json = QJsonObject::fromVariantMap(command);
        const auto operation = json.value("operation").toString();
        const auto nonce = json.value("commandId").toString(), run = json.value("runId").toString();
        const auto leaseId = json.value("leaseId").toString(), startId = json.value("startCommandId").toString();
        QStringList fields {"action", "commandId", "instance", "leaseId", "operation", "role", "runId", "schemaVersion", "startCommandId"};
        if (operation == "start") { fields.append("seconds"); }
        if (operation == "read") { fields << "kind" << "offset" << "bytes"; }
        fields.sort(); auto actualFields = json.keys(); actualFields.sort();
        const auto integer = [](const QJsonValue& value, int low, int high) {
            const auto number = value.toDouble(-1); return value.isDouble() && std::isfinite(number) &&
                number >= low && number <= high && number == std::floor(number);
        };
        if (actualFields != fields || json.value("schemaVersion") != QJsonValue(1) ||
                json.value("action") != QJsonValue("feature-ios-audio-passive-capture") ||
                json.value("role") != QJsonValue("actor") || json.value("instance") != QJsonValue(_instance) ||
                !hex(run) || !hex(leaseId) || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(nonce).hasMatch() ||
                !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(startId).hasMatch() || (operation == "start" && startId != nonce) ||
                !QSet<QString>{"start", "observe", "capture", "read", "release", "recover", "files"}.contains(operation) ||
                (operation == "start" && !integer(json.value("seconds"), 6, 10)) ||
                (operation == "read" && (!integer(json.value("offset"), 0, MAX_ORIGINAL) ||
                    !integer(json.value("bytes"), 1, 4096) || !names().contains(json.value("kind").toString())))) { return {}; }
        if (nonce == _lastCommand.value("commandId").toString()) { return command == _lastCommand ? _lastResult : QVariantMap(); }
        if (_used.contains(nonce) || _used.size() >= 65536) { return {}; }
        _used.insert(nonce); // Lost invocation is not retried with a new nonce.
        struct Busy { bool& value; explicit Busy(bool& v):value(v) { value = true; } ~Busy() { value = false; } } busy(_busy);
        const auto requested = QDateTime::currentMSecsSinceEpoch();
        if (requested <= 0 || requested < _lastEpoch) { return {}; }
        const QFileInfo info(QDir(directory).absolutePath());
        if (info.canonicalFilePath() != info.absoluteFilePath()) { return {}; }
        Handle root(::open(QFile::encodeName(info.absoluteFilePath()).constData(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
        struct stat rootInfo;
        if (!privateNode(root.fd, true, rootInfo) || !sameRoot(root.fd, info.absoluteFilePath())) { return {}; }
        if (_root.isEmpty()) { _root = info.absoluteFilePath(); _device = rootInfo.st_dev; _inode = rootInfo.st_ino; }
        if (_root != info.absoluteFilePath() || _device != rootInfo.st_dev || _inode != rootInfo.st_ino) { return {}; }
        if (!inventory(root.fd)) { return {}; }
        const auto key = run + ':' + leaseId; auto found = _leases.find(key);
        if (operation == "start") {
            if (found != _leases.end() || !_active.isEmpty() || _leases.size() >= 256 || !audio.admissionCurrent()) { return {}; }
            for (const auto& kind : names()) {
                struct stat status;
                if (!::fstatat(root.fd, filename(leaseId, kind).constData(), &status, AT_SYMLINK_NOFOLLOW) || errno != ENOENT) { return {}; }
            }
            Lease lease; lease.run = run; lease.id = leaseId; lease.startId = startId; lease.seconds = json.value("seconds").toInt();
            found = _leases.insert(key, lease); _active = key;
            const QJsonObject intent {{"passiveAcousticIntentVersion", 1}, {"instance", _instance}, {"runId", run},
                {"leaseId", leaseId}, {"role", "actor"}, {"processId", static_cast<double>(QCoreApplication::applicationPid())},
                {"issuedEpochMs", static_cast<double>(requested)}, {"command", json}};
            // The actual created inode/write-prefix is recorded before capture
            // allocation. Partial writes retain duty and never become a new run.
            if (!writeNew(root.fd, "intent", QJsonDocument(intent).toJson(QJsonDocument::Compact) + '\n', found.value()) ||
                    ::fsync(root.fd) || !audio.admissionCurrent()) { return {}; }
            found->startAttempted = true;
            if (!audio.start(run, leaseId, found->seconds)) { return {}; }
            const auto state = audio.status();
            if (!sameCapture(state, found.value())) { return {}; }
            found->generation = state.value("captureGeneration").toULongLong();
        } else if (found == _leases.end()) {
            // Retire an undelivered Start without ever allocating a capture.
            // inventory() has already refused every unknown native file. A
            // tombstone prevents a delayed Start from creating this same lease.
            if (operation != "release" || _leases.size() >= 256) { return {}; }
            const auto actual = audio.status();
            if (actual.isEmpty() || actual.value("owned").toBool() || actual.value("bytes").toLongLong() != 0 ||
                    actual.value("watchdogOwned").toBool() || actual.value("watchdogActive").toBool()) { return {}; }
            Lease lease; lease.run = run; lease.id = leaseId; lease.startId = startId;
            found = _leases.insert(key, lease);
        }
        auto& lease = found.value();
        if (lease.startId != startId) { return {}; } // Cannot adopt/release a colliding foreign creator.
        QVariantMap source;
        if (operation == "capture") {
            if (lease.releaseAttempted || lease.captureAttempted || !audio.admissionCurrent()) { return {}; }
            const auto state = audio.status();
            if (!sameCapture(state, lease) || !state.value("complete").toBool() || state.value("active").toBool() ||
                    state.value("invalid").toBool()) { return {}; }
            const auto wav = audio.wav();
            if (wav.isEmpty() || wav.size() > MAX_ORIGINAL) { return {}; }
            lease.captureAttempted = true;
            if (!writeNew(root.fd, "wav", wav, lease)) { return {}; }
            const QVariantMap original {{"passiveAcousticOriginalVersion", 1}, {"instance", _instance}, {"runId", run},
                {"leaseId", leaseId}, {"role", "actor"}, {"processId", QCoreApplication::applicationPid()},
                {"requestedEpochMs", requested}, {"capturedEpochMs", QDateTime::currentMSecsSinceEpoch()},
                {"captureCommand", command}, {"source", state}, {"wav", descriptor("wav", lease.files["wav"])}};
            if (!writeNew(root.fd, "capture", QJsonDocument::fromVariant(original).toJson(QJsonDocument::Compact) + '\n', lease) ||
                    ::fsync(root.fd)) { return {}; }
        }
        if (operation == "release") {
            if (lease.releaseAttempted) { return {}; }
            lease.releaseAttempted = true; // Never repeat uncertain memory release.
            if (!lease.generation) {
                // Start may have returned after allocating but before its first
                // status reached this owner. Inspect only this original lease.
                const auto state = audio.status();
                if (sameCapture(state, lease)) { lease.generation = state.value("captureGeneration").toULongLong(); }
            }
            if (lease.generation) { audio.release(run, leaseId, lease.generation); }
        }
        if (operation == "release" || operation == "recover") {
            if (!lease.releaseAttempted) { return {}; }
            // A passive status resolves uncertain release; recover NEVER calls
            // audio.release or starts/allocates/snapshots another capture.
            const auto state = audio.status();
            if (state.value("owned").toBool() || state.value("bytes").toLongLong() != 0 ||
                    state.value("watchdogOwned").toBool() || state.value("watchdogActive").toBool()) { return {}; }
            for (auto file = lease.files.begin(); file != lease.files.end(); ++file) {
                if (!file->removed && !verify(root.fd, lease, file.key(), file.value())) { return {}; }
            }
            // Refuse all unknown filenames in this lease's closed namespace,
            // including a copied/same-body replacement and partial new file.
            for (const auto& kind : names()) {
                if (lease.files.contains(kind)) { continue; }
                struct stat status;
                if (!::fstatat(root.fd, filename(lease.id, kind).constData(), &status, AT_SYMLINK_NOFOLLOW) || errno != ENOENT) { return {}; }
            }
            for (auto file = lease.files.begin(); file != lease.files.end(); ++file) {
                if (file->removed) { continue; }
                if (::unlinkat(root.fd, filename(lease.id, file.key()).constData(), 0)) { return {}; }
                file->removed = true; file->fd.reset(); file->written.fill(0); file->written.clear(); file->written.squeeze();
            }
            if (::fsync(root.fd)) { return {}; }
            lease.retired = true; if (_active == key) { _active.clear(); }
        }
        if (operation == "read") {
            const auto kind = json.value("kind").toString();
            if (!lease.files.contains(kind) || !lease.files[kind].complete || !verify(root.fd, lease, kind, lease.files[kind])) { return {}; }
            const auto& file = lease.files[kind];
            const int offset = json.value("offset").toInt(), count = json.value("bytes").toInt();
            if (offset >= file.written.size() || count > file.written.size() - offset) { return {}; }
            QByteArray raw(count, '\0'); qint64 done {0};
            while (done < count) {
                const auto amount = ::pread(file.fd->fd, raw.data() + done, count - done, offset + done);
                if (amount < 0 && errno == EINTR) { continue; }
                if (amount <= 0) { return {}; } done += amount;
            }
            if (raw != file.written.mid(offset, count) || !verify(root.fd, lease, kind, file)) { return {}; }
            source = {{"kind", kind}, {"offset", offset}, {"bytes", count}, {"original", descriptor(kind, file)}, {"originalOnly", true},
                {"base64", QString::fromLatin1(raw.toBase64())}, {"sha256", digest(raw)}};
        } else {
            QVariantList files; qint64 retainedBytes {0}; int openFiles {0};
            for (const auto& kind : names()) {
                const auto file = lease.files.constFind(kind); struct stat status;
                const bool exists = !::fstatat(root.fd, filename(lease.id, kind).constData(), &status, AT_SYMLINK_NOFOLLOW);
                if (!exists && errno != ENOENT) { return {}; }
                if (file != lease.files.cend() && !file->removed) {
                    if (!verify(root.fd, lease, kind, file.value())) { return {}; }
                    files.append(descriptor(kind, file.value())); retainedBytes += file->written.size(); ++openFiles;
                } else {
                    if (exists) { return {}; } files.append(QVariantMap{{"kind", kind}, {"exists", false}});
                }
            }
            source = {{"state", compactStatus(audio.status())}, {"files", files}, {"retired", lease.retired},
                {"startAttempted", lease.startAttempted}, {"captureAttempted", lease.captureAttempted},
                {"releaseAttempted", lease.releaseAttempted}, {"openOriginalFds", openFiles}, {"originalBytes", retainedBytes}};
        }
        if (!inventory(root.fd) || !sameRoot(root.fd, _root)) { return {}; }
        const auto captured = QDateTime::currentMSecsSinceEpoch();
        if (captured < requested || captured < _lastEpoch || _sequence >= 1000000000) { return {}; }
        _lastEpoch = captured; _lastCommand = command;
        _lastResult = {{"passiveAcousticReplyVersion", 1}, {"commandId", nonce}, {"instance", _instance},
            {"sequence", static_cast<qulonglong>(++_sequence)}, {"processId", QCoreApplication::applicationPid()},
            {"runId", run}, {"role", "actor"}, {"leaseId", leaseId}, {"operation", operation},
            {"requestedEpochMs", requested}, {"capturedEpochMs", captured}, {"source", source}};
        return _lastResult;
#else
        Q_UNUSED(directory); Q_UNUSED(command); Q_UNUSED(audio); return {};
#endif
    }
private:
    static constexpr int MAX_ORIGINAL = 2 * 1024 * 1024;
    static bool hex(const QString& value) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch(); }
    static QString digest(const QByteArray& bytes) { return QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex()); }
    static QVariantMap compactStatus(QVariantMap source) {
        const auto rows = source.take("rows").toList();
        source["originRows"] = rows.size();
        source["originRowsSha256"] = digest(QJsonDocument::fromVariant(rows).toJson(QJsonDocument::Compact));
        return source;
    }
    static QStringList names() { return {"intent", "capture", "wav"}; }
    static QByteArray filename(const QString& lease, const QString& kind) {
        return ("feature-passive-acoustic-" + lease + '-' + kind + (kind == "wav" ? ".wav" : ".json")).toLatin1();
    }
#if defined(Q_OS_UNIX)
    struct Handle { int fd; explicit Handle(int value):fd(value) {} ~Handle() { if (fd >= 0) { ::close(fd); } }
        Handle(const Handle&) = delete; Handle& operator=(const Handle&) = delete; };
    struct File { std::shared_ptr<Handle> fd; struct stat observed{}; QByteArray written; bool complete {false}, removed {false}; };
    struct Lease { QString run, id, startId; int seconds {0}; quint64 generation {0}; QMap<QString, File> files;
        bool startAttempted {false}, captureAttempted {false}, releaseAttempted {false}, retired {false}; };
    static bool privateNode(int fd, bool directory, struct stat& result) {
        return fd >= 0 && !::fstat(fd, &result) && result.st_uid == ::geteuid() &&
            (result.st_mode & 0777) == (directory ? 0700 : 0600) &&
            (directory ? S_ISDIR(result.st_mode) : S_ISREG(result.st_mode) && result.st_nlink == 1);
    }
    static bool sameStat(const struct stat& a, const struct stat& b) {
        if (a.st_dev != b.st_dev || a.st_ino != b.st_ino || a.st_size != b.st_size || a.st_mode != b.st_mode ||
                a.st_uid != b.st_uid || a.st_gid != b.st_gid || a.st_nlink != b.st_nlink) { return false; }
#if defined(Q_OS_DARWIN)
        return a.st_mtimespec.tv_sec == b.st_mtimespec.tv_sec && a.st_mtimespec.tv_nsec == b.st_mtimespec.tv_nsec &&
            a.st_ctimespec.tv_sec == b.st_ctimespec.tv_sec && a.st_ctimespec.tv_nsec == b.st_ctimespec.tv_nsec;
#else
        return a.st_mtim.tv_sec == b.st_mtim.tv_sec && a.st_mtim.tv_nsec == b.st_mtim.tv_nsec &&
            a.st_ctim.tv_sec == b.st_ctim.tv_sec && a.st_ctim.tv_nsec == b.st_ctim.tv_nsec;
#endif
    }
    static bool sameRoot(int fd, const QString& path) {
        struct stat opened, current;
        return privateNode(fd, true, opened) && !::lstat(QFile::encodeName(path).constData(), &current) &&
            S_ISDIR(current.st_mode) && current.st_uid == ::geteuid() && (current.st_mode & 0777) == 0700 &&
            current.st_dev == opened.st_dev && current.st_ino == opened.st_ino;
    }
    bool sameCapture(const QVariantMap& value, const Lease& lease) const {
        return value.value("passiveAcousticVersion").toInt() == 1 && value.value("owned").toBool() &&
            value.value("runId") == QVariant(lease.run) && value.value("leaseId") == QVariant(lease.id) &&
            value.value("role") == QVariant("actor") && value.value("instance") == QVariant(_instance) &&
            value.value("captureGeneration").toULongLong() > 0 &&
            (!lease.generation || value.value("captureGeneration").toULongLong() == lease.generation);
    }
    static QVariantMap descriptor(const QString& kind, const File& file) {
        return {{"kind", kind}, {"exists", true}, {"complete", file.complete}, {"bytes", file.written.size()},
            {"sha256", digest(file.written)}, {"device", QString::number(file.observed.st_dev)},
            {"inode", QString::number(file.observed.st_ino)}};
    }
    static bool verify(int root, const Lease& lease, const QString& kind, const File& file) {
        if (!file.fd || file.removed) { return false; } struct stat opened, path;
        return privateNode(file.fd->fd, false, opened) && sameStat(opened, file.observed) &&
            !::fstatat(root, filename(lease.id, kind).constData(), &path, AT_SYMLINK_NOFOLLOW) &&
            sameStat(path, opened) && opened.st_size == file.written.size();
    }
    static bool writeNew(int root, const QString& kind, const QByteArray& raw, Lease& lease) {
        if (raw.isEmpty() || raw.size() > MAX_ORIGINAL || lease.files.contains(kind)) { return false; }
        auto fd = std::make_shared<Handle>(::openat(root, filename(lease.id, kind).constData(),
            O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600));
        if (fd->fd < 0) { return false; }
        // O_EXCL has already created this exact path. Latch its original FD
        // before chmod/fstat can fail; every later failure retains the lease
        // and opened-file duty. A missing or invalid identity remains owned
        // and fail-closed, never silently forgotten or adopted after restart.
        File file; file.fd = fd; lease.files.insert(kind, file);
        auto& issued = lease.files[kind];
        if (::fstat(fd->fd, &issued.observed)) { return false; }
        const auto born = issued.observed;
        if (::fchmod(fd->fd, 0600)) {
            ::fstat(fd->fd, &issued.observed); return false;
        }
        if (!privateNode(fd->fd, false, issued.observed) ||
                issued.observed.st_dev != born.st_dev || issued.observed.st_ino != born.st_ino ||
                issued.observed.st_size != 0) { return false; }
        qint64 done {0};
        while (done < raw.size()) {
            const auto count = ::write(fd->fd, raw.constData() + done, raw.size() - done);
            if (count < 0 && errno == EINTR) { continue; }
            if (count <= 0) { ::fstat(fd->fd, &issued.observed); return false; }
            issued.written.append(raw.constData() + done, static_cast<int>(count)); done += count;
            if (::fstat(fd->fd, &issued.observed)) { return false; }
        }
        if (::fsync(fd->fd) || !verify(root, lease, kind, issued)) { return false; }
        issued.complete = true; return true;
    }
    bool inventory(int root) const {
        const int copy = ::dup(root); if (copy < 0) { return false; }
        DIR* directory = ::fdopendir(copy); if (!directory) { ::close(copy); return false; }
        ::rewinddir(directory); struct stat before, after;
        bool valid = privateNode(root, true, before); errno = 0;
        while (valid) {
            const auto entry = ::readdir(directory);
            if (!entry) { if (errno) { valid = false; } break; }
            const QByteArray name(entry->d_name);
            if (!name.startsWith("feature-passive-acoustic-")) { continue; }
            bool owned {false};
            for (auto lease = _leases.cbegin(); lease != _leases.cend(); ++lease) {
                for (auto file = lease->files.cbegin(); file != lease->files.cend(); ++file) {
                    if (name == filename(lease->id, file.key())) {
                        owned = !file->removed && verify(root, lease.value(), file.key(), file.value());
                    }
                }
            }
            if (!owned) { valid = false; }
            errno = 0;
        }
        for (auto lease = _leases.cbegin(); valid && lease != _leases.cend(); ++lease) {
            for (auto file = lease->files.cbegin(); file != lease->files.cend(); ++file) {
                if (!file->removed && !verify(root, lease.value(), file.key(), file.value())) { valid = false; }
            }
        }
        if (!privateNode(root, true, after) || !sameStat(before, after)) { valid = false; }
        ::closedir(directory); return valid;
    }
    QMap<QString, Lease> _leases; dev_t _device{}; ino_t _inode{};
#endif
    QString _instance, _root, _active; const QThread* _thread;
    QSet<QString> _used; QVariantMap _lastCommand, _lastResult;
    quint64 _sequence {0}; qint64 _lastEpoch {0}; bool _busy {false};
};
} // namespace overte::e2e
