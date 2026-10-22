// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStandardPaths>
#include <QThread>
#include <QUuid>
#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <functional>

namespace overte::e2e {

// Reads the real loaded service and its fixed original persistence container.
// No bookmark/file setter, repair, fallback map or host timestamp is used.
class IOSLocationBookmarksObservation {
public:
    IOSLocationBookmarksObservation() : _instance(QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')) { _clock.start(); }

    QVariantMap read(const QString& request,const QString& run,const std::function<QVariantMap()>& loadedReader,
            const std::function<bool()>& errorReader) {
        if (!qApp || QThread::currentThread()!=qApp->thread() || !QCoreApplication::arguments().contains("--testScript")
                || _sequence>=1000000000 || !loadedReader || !errorReader) { return {}; }
        const auto before=clock();
        const auto loaded=loadedReader();const bool loadError=errorReader();
        if (QJsonDocument::fromVariant(loaded).toJson(QJsonDocument::Compact).size()>65536) { return {}; }
        const auto file=originalFile();
        const auto after=clock();
        return {{"iosLocationBookmarksVersion",1},{"requestId",request},{"runId",run},{"instance",_instance},
            {"sequence",static_cast<double>(++_sequence)},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"clockDomain","native-main-bookmarks"},{"clockBefore",before},{"clockAfter",after},
            {"loaded",QVariantMap {{"source","LocationBookmarks.getBookmarks"},{"entries",loaded},{"loadError",loadError}}},
            {"file",file}};
    }

private:
    QVariantMap clock() const {
        return {{"epochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
            {"monotonicMs",static_cast<double>(_clock.elapsed())}};
    }

    static QVariantMap fileResult(const QString& status,const QString& reason=QString()) {
        return {{"source","app-local-data/bookmarks.json"},{"status",status},{"reason",reason},
            {"bytes",QVariant()},{"sha256",QVariant()},{"contentBase64",QVariant()},{"identity",QVariant()}};
    }

    static bool unchanged(const struct stat& before,const struct stat& after) {
        return before.st_dev==after.st_dev && before.st_ino==after.st_ino && before.st_size==after.st_size
            && before.st_mode==after.st_mode && before.st_uid==after.st_uid && before.st_nlink==after.st_nlink
            && before.st_mtimespec.tv_sec==after.st_mtimespec.tv_sec && before.st_mtimespec.tv_nsec==after.st_mtimespec.tv_nsec
            && before.st_ctimespec.tv_sec==after.st_ctimespec.tv_sec && before.st_ctimespec.tv_nsec==after.st_ctimespec.tv_nsec;
    }

    static QVariantMap originalFile() {
        const auto directory=QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);
        if (directory.isEmpty()) { return fileResult("unavailable","location-unavailable"); }
        const auto path=QFile::encodeName(directory+"/bookmarks.json");
        const int descriptor=::open(path.constData(),O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);
        if (descriptor<0) { return errno==ENOENT ? fileResult("absent") : fileResult("unavailable","open-error"); }
        struct stat first {},last {},named {};
        if (::fstat(descriptor,&first)!=0 || !S_ISREG(first.st_mode) || first.st_uid!=::geteuid() || first.st_nlink!=1) {
            ::close(descriptor);return fileResult("unavailable","unsafe-file");
        }
        if (first.st_size<0 || first.st_size>65536) { ::close(descriptor);return fileResult("unavailable","too-large"); }
        QFile input;
        if (!input.open(descriptor,QIODevice::ReadOnly,QFileDevice::AutoCloseHandle)) {
            ::close(descriptor);return fileResult("unavailable","read-error");
        }
        const auto bytes=input.read(65537);
        if (input.error()!=QFileDevice::NoError) { return fileResult("unavailable","read-error"); }
        if (::fstat(descriptor,&last)!=0 || ::lstat(path.constData(),&named)!=0
                || !unchanged(first,last) || !unchanged(last,named) || bytes.size()!=first.st_size) {
            return fileResult("unavailable","changed-file");
        }
        auto result=fileResult("ready");
        result["bytes"]=bytes.size();result["sha256"]=QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());
        result["contentBase64"]=QString::fromLatin1(bytes.toBase64());
        result["identity"]=QVariantMap {{"device",QString::number(static_cast<qulonglong>(first.st_dev))},
            {"inode",QString::number(static_cast<qulonglong>(first.st_ino))}};
        return result;
    }

    QString _instance;
    quint64 _sequence {0};
    QElapsedTimer _clock;
};
} // namespace overte::e2e
#endif
