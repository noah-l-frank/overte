// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "AvatarPreferenceBarrier.h"
#include "CreateBrowseSettingFile.h"
#include <QBuffer>
namespace overte::e2e {
// Fixed Avatar scopes only. Raw canonical JSON tokens are independent of every
// QSettings cache. Never deserialize a foreign @Variant or mutate/sync settings.
inline QVariantMap avatarPreferenceTokens(const QJsonObject& object) {
    QVariantMap tokens;
    for(auto it=object.begin();it!=object.end();++it) {
        if(!avatarPreferenceKey(it.key())) {continue;}
        if(tokens.size()>=512) {return {};}
        const auto key=QJsonDocument(QJsonArray{it.key()}).toJson(QJsonDocument::Compact);
        const auto prefix=QByteArray("{\n    ")+key.mid(1,key.size()-2)+": ";
        const auto one=QJsonDocument(QJsonObject{{it.key(),it.value()}}).toJson(QJsonDocument::Indented);
        const QByteArray suffix="\n}\n";
        if(!one.startsWith(prefix) || !one.endsWith(suffix)) {return {};}
        const auto raw=one.mid(prefix.size(),one.size()-prefix.size()-suffix.size());
        if(raw.size()>65536) {return {};}
        tokens.insert(it.key(),QVariantMap{{"base64",QString::fromLatin1(raw.toBase64())},
            {"sha256",QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex())}});
    }
    return {{"count",tokens.size()},{"values",tokens}};
}
inline QVariantMap avatarPreferenceEncoded(const QSettings::SettingsMap& actual) {
    QSettings::SettingsMap scoped;
    for(auto it=actual.begin();it!=actual.end();++it) {
        if(!avatarPreferenceKey(it.key())) {continue;}
        // Refuse a custom serializer or the original writer's unsupported Hash.
        if(it.value().userType()>=QMetaType::User || it.value().userType()==QMetaType::QVariantHash || scoped.size()>=512) {return {};}
        scoped.insert(it.key(),it.value());
    }
    QByteArray bytes;QBuffer buffer(&bytes);if(!buffer.open(QIODevice::WriteOnly) || !writeJSONFile(buffer,scoped)) {return {};}
    const auto document=QJsonDocument::fromJson(bytes);return document.isObject() ? avatarPreferenceTokens(document.object()) : QVariantMap{};
}
#if defined(Q_OS_UNIX)
inline bool avatarPreferenceSameFile(const struct stat& a,const struct stat& b) {return createBrowseSettingsSameFile(a,b);}
#endif
inline QVariantMap avatarPreferenceFile(const QString& originalPath,QSettings::Format format) {
#if defined(Q_OS_UNIX)
    if(format!=JSON_FORMAT) {return {};}
    const QFileInfo file(originalPath);const auto path=file.canonicalFilePath();
    QVariantMap identity{{"exists",file.exists()}};
    const auto immediateParent=QFileInfo(originalPath).dir().canonicalPath();struct stat parentBefore{},parentAfter{};
    if (immediateParent.isEmpty() || ::lstat(QFile::encodeName(immediateParent).constData(),&parentBefore)!=0
            || !S_ISDIR(parentBefore.st_mode) || parentBefore.st_uid!=::geteuid() || (parentBefore.st_mode&0022)!=0) {return {};}
    auto privateRoot=immediateParent;struct stat directory{};
    if (file.isSymLink()) { return {}; }
    while (!privateRoot.isEmpty()) {
        if (::lstat(QFile::encodeName(privateRoot).constData(),&directory)!=0 || !S_ISDIR(directory.st_mode)
                || directory.st_uid!=::geteuid() || (directory.st_mode&0022)!=0) { return {}; }
        if ((directory.st_mode&0077)==0) { break; }
        const auto parent=QFileInfo(privateRoot).dir().canonicalPath();
        if (parent==privateRoot) { return {}; }privateRoot=parent;
    }
    if (privateRoot.isEmpty()) { return {}; }
    QByteArray bytes;
    if (file.exists()) {
        if (path.isEmpty()) { return {}; }
        const int descriptor=::open(QFile::encodeName(path).constData(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);
        struct stat before{},after{},current{};
        if (descriptor<0 || ::fstat(descriptor,&before)!=0 || !S_ISREG(before.st_mode) || before.st_uid!=::geteuid()
                || (before.st_mode&07777)!=0600 || before.st_nlink!=1 || before.st_size<0 || before.st_size>1048576) {
            if (descriptor>=0) { ::close(descriptor); }return {};
        }
        const auto nanoseconds=[](const timespec& value){return QString::number(value.tv_sec)+'.'+QString::number(value.tv_nsec).rightJustified(9,'0');};
        identity={{"exists",true},{"device",QString::number(before.st_dev)},{"inode",QString::number(before.st_ino)},
            {"bytes",static_cast<int>(before.st_size)},{"mode",static_cast<int>(before.st_mode&0777)},
#if defined(Q_OS_DARWIN)
            {"modified",nanoseconds(before.st_mtimespec)},{"changed",nanoseconds(before.st_ctimespec)}};
#else
            {"modified",nanoseconds(before.st_mtim)},{"changed",nanoseconds(before.st_ctim)}};
#endif
        QFile actual;
        if (!actual.open(descriptor,QIODevice::ReadOnly,QFileDevice::AutoCloseHandle)) { ::close(descriptor);return {}; }
        bytes=actual.read(1048577);
        if (actual.error()!=QFile::NoError || bytes.size()!=before.st_size || ::fstat(descriptor,&after)!=0
                || ::lstat(QFile::encodeName(path).constData(),&current)!=0 || !avatarPreferenceSameFile(before,after)
                || !avatarPreferenceSameFile(before,current) || QFileInfo(originalPath).isSymLink()
                || QFileInfo(originalPath).canonicalFilePath()!=path) { return {}; }
    } else {
        struct stat missing{};
        if (::lstat(QFile::encodeName(originalPath).constData(),&missing)==0 || errno!=ENOENT) { return {}; }
    }
    struct stat finalDirectory{};
    if (::lstat(QFile::encodeName(privateRoot).constData(),&finalDirectory)!=0 || !avatarPreferenceSameFile(directory,finalDirectory)
            || QFileInfo(privateRoot).canonicalFilePath()!=privateRoot) { return {}; }
    if (::lstat(QFile::encodeName(immediateParent).constData(),&parentAfter)!=0
            || !avatarPreferenceSameFile(parentBefore,parentAfter)
            || QFileInfo(originalPath).dir().canonicalPath()!=immediateParent) {return {};}
    if (!identity.value("exists").toBool()) {struct stat missing{};
        if (::lstat(QFile::encodeName(originalPath).constData(),&missing)==0 || errno!=ENOENT) {return {};}}
    const auto hash=[](const QByteArray& value){return QString::fromLatin1(QCryptographicHash::hash(value,QCryptographicHash::Sha256).toHex());};
    QJsonObject object;
    if(!bytes.isEmpty()) {
        QJsonParseError error;const auto document=QJsonDocument::fromJson(bytes,&error);
        if(error.error!=QJsonParseError::NoError || !document.isObject() || document.toJson(QJsonDocument::Indented)!=bytes) {return {};}
        object=document.object();
    }
    const auto rows=avatarPreferenceTokens(object);if(rows.isEmpty()) {return {};}
    return {{"avatarPreferenceFileVersion",1},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
        {"format","json"},{"pathSha256",hash(QFile::encodeName(QDir::cleanPath(QFileInfo(originalPath).absoluteFilePath())))},
        {"file",identity},{"fileSha256",hash(bytes)},{"rows",rows}};
#else
    Q_UNUSED(originalPath) Q_UNUSED(format) return {};
#endif
}
} // namespace overte::e2e
#endif
