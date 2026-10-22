// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <SettingHelpers.h>
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonArray>
#include <QRegularExpression>
#include <QJsonObject>
#include <QVariantMap>
#if defined(Q_OS_UNIX)
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif
namespace overte::e2e {
// Fixed-key physical bytes, acquired independently of every QSettings cache.
// Reuses the reviewed Chat descriptor/path stability checks, without loading or
// modifying any other setting. Unsupported encodings/permissions stay owned.
#if defined(Q_OS_UNIX)
inline bool createBrowseSettingsSameFile(const struct stat& a,const struct stat& b) {
#if defined(Q_OS_DARWIN)
    const bool times=a.st_mtimespec.tv_sec==b.st_mtimespec.tv_sec && a.st_mtimespec.tv_nsec==b.st_mtimespec.tv_nsec
        && a.st_ctimespec.tv_sec==b.st_ctimespec.tv_sec && a.st_ctimespec.tv_nsec==b.st_ctimespec.tv_nsec;
#else
    const bool times=a.st_mtim.tv_sec==b.st_mtim.tv_sec && a.st_mtim.tv_nsec==b.st_mtim.tv_nsec
        && a.st_ctim.tv_sec==b.st_ctim.tv_sec && a.st_ctim.tv_nsec==b.st_ctim.tv_nsec;
#endif
    return times && a.st_dev==b.st_dev && a.st_ino==b.st_ino && a.st_size==b.st_size
        && a.st_uid==b.st_uid && a.st_mode==b.st_mode && a.st_nlink==b.st_nlink;
}
#endif
inline QVariantMap createBrowseSettingsFile(const QString& originalPath,QSettings::Format format) {
#if defined(Q_OS_UNIX)
    const auto encoding=format==QSettings::IniFormat ? QString("ini") : format==JSON_FORMAT ? QString("json") : QString();
    if (encoding.isEmpty()) {return {};}
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
                || ::lstat(QFile::encodeName(path).constData(),&current)!=0 || !createBrowseSettingsSameFile(before,after)
                || !createBrowseSettingsSameFile(before,current) || QFileInfo(originalPath).isSymLink()
                || QFileInfo(originalPath).canonicalFilePath()!=path) { return {}; }
    } else {
        struct stat missing{};
        if (::lstat(QFile::encodeName(originalPath).constData(),&missing)==0 || errno!=ENOENT) { return {}; }
    }
    struct stat finalDirectory{};
    if (::lstat(QFile::encodeName(privateRoot).constData(),&finalDirectory)!=0 || !createBrowseSettingsSameFile(directory,finalDirectory)
            || QFileInfo(privateRoot).canonicalFilePath()!=privateRoot) { return {}; }
    if (::lstat(QFile::encodeName(immediateParent).constData(),&parentAfter)!=0
            || !createBrowseSettingsSameFile(parentBefore,parentAfter)
            || QFileInfo(originalPath).dir().canonicalPath()!=immediateParent) {return {};}
    if (!identity.value("exists").toBool()) {struct stat missing{};
        if (::lstat(QFile::encodeName(originalPath).constData(),&missing)==0 || errno!=ENOENT) {return {};}}
    const auto hash=[](const QByteArray& value){return QString::fromLatin1(QCryptographicHash::hash(value,QCryptographicHash::Sha256).toHex());};
    const auto fileHash=hash(bytes);QByteArray row;bool present=false;
    if (encoding=="ini") {
        if (bytes.startsWith("\xEF\xBB\xBF")) {bytes.remove(0,3);}
        if (bytes.contains('\0')) {return {};}
        bool general=true;
        for (auto line:bytes.split('\n')) {
            if (line.endsWith('\r')) {line.chop(1);}
            if (line.isEmpty() || line.startsWith(';') || line.startsWith('#')) {continue;}
            if (line.startsWith('[')) {if (!line.endsWith(']')) {return {};}general=line=="[General]";continue;}
            if (!general) {continue;}const auto separator=line.indexOf('=');if (separator<1) {return {};}
            const auto key=line.left(separator);
            if (key!="LastBrowseLocation") {
                auto alias=QByteArray::fromPercentEncoding(key.trimmed());
                if (alias.startsWith('"') && alias.endsWith('"')) {alias=alias.mid(1,alias.size()-2);}
                if (alias=="LastBrowseLocation") {return {};}continue;
            }
            if (present || line.endsWith('\\')) {return {};}present=true;row=line.mid(separator+1);
        }
    } else if (!bytes.isEmpty()) {
        QJsonParseError error;const auto document=QJsonDocument::fromJson(bytes,&error);
        // The original JSON writer always emits Qt's indented serialization.
        // Exact equality also refuses duplicate keys and alternate key escapes.
        if (error.error!=QJsonParseError::NoError || !document.isObject() || document.toJson(QJsonDocument::Indented)!=bytes) {return {};}
        const auto marker=QByteArray("    \"LastBrowseLocation\": ");
        const auto found=bytes.indexOf(QByteArray("\n")+marker);const auto start=found<0 ? -1 : found+1;
        present=document.object().contains("LastBrowseLocation");
        if (present) {
            if (start<0 || (start>0 && bytes.at(start-1)!='\n')) {return {};}
            int begin=start+marker.size(),end=begin,depth=0;bool quoted=false,escaped=false;
            for (;end<bytes.size();++end) {
                const auto c=bytes.at(end);
                if (quoted) {if (escaped) {escaped=false;}else if (c=='\\') {escaped=true;}else if (c=='"') {quoted=false;}continue;}
                if (c=='"') {quoted=true;continue;}
                if ((c==',' || c=='\n' || c=='}') && depth==0) {break;}
                if (c=='{' || c=='[') {++depth;}else if (c=='}' || c==']') {--depth;}
            }
            if (quoted || depth!=0 || end<=begin || end>=bytes.size()) {return {};}row=bytes.mid(begin,end-begin);
        }
    }
    if (row.size()>32768) {return {};}
    return {{"physicalVersion",1},{"format",encoding},{"pathSha256",hash(QFile::encodeName(QDir::cleanPath(QFileInfo(originalPath).absoluteFilePath())))},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"file",identity},{"fileSha256",fileHash},
        {"row",QVariantMap{{"present",present},{"base64",QString::fromLatin1(row.toBase64())},{"sha256",hash((present?QByteArray("present:"):QByteArray("absent:"))+row)}}}};
#else
    Q_UNUSED(originalPath) Q_UNUSED(format) return {};
#endif
}
inline bool createBrowsePhysicalOwned(const QVariantMap& physical,const QVariant& owned,bool present) {
    if (physical.isEmpty()) {return false;}const auto row=physical.value("row").toMap();
    if (!present) {return row.value("present")==QVariant(false);}
    if (owned.userType()!=QMetaType::QString || row.value("present")!=QVariant(true)) {return false;}
    const auto bytes=QByteArray::fromBase64(row.value("base64").toString().toLatin1());const auto text=owned.toString();
    if (physical.value("format")==QVariant("json")) {
        // This is the original writer's closed QString encoding. Do not
        // deserialize a foreign @Variant/custom type merely to admit a CAS.
        QJsonParseError error;const auto document=QJsonDocument::fromJson(QByteArray("[")+bytes+']',&error);
        const auto values=document.array();
        return error.error==QJsonParseError::NoError && values.size()==1 && values.first().isString()
            && values.first().toString()==(text.startsWith('@') ? QString('@')+text : text);
    }
    // The actual owned Android Create directory is plain ASCII. Ambiguous
    // INI escape/quote forms stay owned instead of inventing a Qt decoder.
    return physical.value("format")==QVariant("ini") && (text.isEmpty()
        || QRegularExpression("\\A[A-Za-z0-9/._:-]+\\z").match(text).hasMatch()) && bytes==text.toLatin1();
}
inline bool createBrowsePhysicalOriginal(const QVariantMap& original,const QVariantMap& current) {
    // Original QSettings atomic rewrites legitimately replace the inode. Keep
    // both exact acquisition identities, but compare only this fixed raw row.
    return !original.isEmpty() && !current.isEmpty() && original.value("format")==current.value("format")
        && original.value("pathSha256")==current.value("pathSha256") && original.value("row")==current.value("row");
}
} // namespace overte::e2e
#endif
