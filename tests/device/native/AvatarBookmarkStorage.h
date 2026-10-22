// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QVariantMap>
#if defined(Q_OS_UNIX)
#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif
namespace overte::e2e {
// Fixed Phone5527 Bookmarks::featureBookmarkStorage foundation, strengthened
// with the reviewed descriptor/parent stability and raw-byte source pattern.
// This never reloads, creates, repairs or rewrites the original bookmark file.
inline QString avatarBookmarkHash(const QByteArray& bytes) {
    return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());
}
#if defined(Q_OS_UNIX)
inline QByteArray avatarBookmarkRevision(const struct stat& value) {
    QByteArray result;
    for(const auto field:{qint64(value.st_dev),qint64(value.st_ino),qint64(value.st_size),qint64(value.st_uid),
            qint64(value.st_mode),qint64(value.st_nlink),
#if defined(Q_OS_DARWIN)
            qint64(value.st_mtimespec.tv_sec),qint64(value.st_mtimespec.tv_nsec),qint64(value.st_ctimespec.tv_sec),qint64(value.st_ctimespec.tv_nsec)
#else
            qint64(value.st_mtim.tv_sec),qint64(value.st_mtim.tv_nsec),qint64(value.st_ctim.tv_sec),qint64(value.st_ctim.tv_nsec)
#endif
            }) {result+=QByteArray::number(field)+'\n';}
    return result;
}
#endif
inline QVariantMap avatarBookmarkStorage(const QVariantMap& cache,const QString& originalPath,const QString& error) {
#if defined(Q_OS_UNIX)
    if(!error.isEmpty() || originalPath.isEmpty() || cache.size()>1000 || QFileInfo(originalPath).fileName()!="avatarbookmarks.json") {return {};}
    const auto parent=QFileInfo(originalPath).dir().canonicalPath();struct stat parentBefore{},parentAfter{};
    if(parent.isEmpty() || ::lstat(QFile::encodeName(parent).constData(),&parentBefore)!=0 || !S_ISDIR(parentBefore.st_mode)
            || parentBefore.st_uid!=::geteuid() || (parentBefore.st_mode&0022)!=0) {return {};}
    auto privateRoot=parent;struct stat directory{};
    while(!privateRoot.isEmpty()) {
        if(::lstat(QFile::encodeName(privateRoot).constData(),&directory)!=0 || !S_ISDIR(directory.st_mode)
                || directory.st_uid!=::geteuid() || (directory.st_mode&0022)!=0) {return {};}
        if((directory.st_mode&0077)==0) {break;}
        const auto ancestor=QFileInfo(privateRoot).dir().canonicalPath();if(ancestor==privateRoot) {return {};}privateRoot=ancestor;
    }
    if(privateRoot.isEmpty()) {return {};}
    struct stat before{},opened{},after{},current{};QByteArray bytes;QVariant file;
    const auto path=QFile::encodeName(originalPath);
    const bool present=::lstat(path.constData(),&before)==0;
    if(!present) {if(errno!=ENOENT || !cache.isEmpty()) {return {};}}
    else {
        if(!S_ISREG(before.st_mode) || before.st_uid!=::geteuid() || (before.st_mode&0022)!=0
                || before.st_nlink!=1 || before.st_size<0 || before.st_size>262144) {return {};}
        const int descriptor=::open(path.constData(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);
        if(descriptor<0) {return {};}
        QFile actual;if(!actual.open(descriptor,QIODevice::ReadOnly,QFileDevice::AutoCloseHandle)) {::close(descriptor);return {};}
        if(::fstat(descriptor,&opened)!=0 || avatarBookmarkRevision(opened)!=avatarBookmarkRevision(before)) {return {};}
        bytes=actual.read(262145);
        if(actual.error()!=QFile::NoError || bytes.size()!=opened.st_size || ::fstat(descriptor,&after)!=0
                || ::lstat(path.constData(),&current)!=0 || avatarBookmarkRevision(opened)!=avatarBookmarkRevision(after)
                || avatarBookmarkRevision(after)!=avatarBookmarkRevision(current)) {return {};}
        QJsonParseError parse;const auto disk=QJsonDocument::fromJson(bytes,&parse);
        if(parse.error!=QJsonParseError::NoError || !disk.isObject() || disk.object()!=QJsonObject::fromVariantMap(cache)) {return {};}
        file=QVariantMap{{"bytes",bytes.size()},{"sha256",avatarBookmarkHash(bytes)},
            {"revisionSha256",avatarBookmarkHash(avatarBookmarkRevision(current))}};
    }
    struct stat finalRoot{};
    if(::lstat(QFile::encodeName(privateRoot).constData(),&finalRoot)!=0 || avatarBookmarkRevision(directory)!=avatarBookmarkRevision(finalRoot)
            || QFileInfo(privateRoot).canonicalFilePath()!=privateRoot || ::lstat(QFile::encodeName(parent).constData(),&parentAfter)!=0
            || avatarBookmarkRevision(parentBefore)!=avatarBookmarkRevision(parentAfter) || QFileInfo(originalPath).dir().canonicalPath()!=parent) {return {};}
    if(!present && (::lstat(path.constData(),&current)==0 || errno!=ENOENT)) {return {};}
    const auto map=QJsonDocument(QJsonObject::fromVariantMap(cache)).toJson(QJsonDocument::Compact);
    if(map.size()>262144) {return {};}
    const QVariantMap result{{"avatarBookmarkStorageVersion",1},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
        {"pathSha256",avatarBookmarkHash(QFile::encodeName(QDir::cleanPath(QFileInfo(originalPath).absoluteFilePath())))},
        {"present",present},{"file",file},{"rawBase64",QString::fromLatin1(bytes.toBase64())},
        {"rawSha256",avatarBookmarkHash(bytes)},{"cacheBase64",QString::fromLatin1(map.toBase64())},
        {"mapSha256",avatarBookmarkHash(map)},{"bookmarks",cache}};
    // Preserve the existing host reader's 262144-byte envelope bound. Raw,
    // cache and parsed values are independent copies, never truncate originals.
    return QJsonDocument(QJsonObject::fromVariantMap(result)).toJson(QJsonDocument::Compact).size()<=245760 ? result : QVariantMap{};
#else
    Q_UNUSED(cache) Q_UNUSED(originalPath) Q_UNUSED(error) return {};
#endif
}
}
#endif
