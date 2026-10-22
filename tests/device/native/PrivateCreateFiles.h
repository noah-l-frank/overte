// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
// Create-only closed input staging and independent actual export-file reads.
// The storage helper never imports entities or generates exported JSON.
#include "PrivateScriptFiles.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
namespace overte::e2e {
class PrivateCreateFiles {
public:
    static QVariantMap request(const QString& directory,const QVariantMap& command) {
#if defined(Q_OS_UNIX)
        const auto run=command.value("runId").toString(),owner=command.value("ownerToken").toString();
        const auto operation=command.value("operation").toString();
        if (!QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{64}\\z").match(owner).hasMatch()
                || !QStringList{"stage","observe","release","locate"}.contains(operation)) { return {}; }
        const auto basePath=QDir(directory).absolutePath();const QFileInfo info(basePath);
        if (!info.isAbsolute() || info.canonicalFilePath()!=info.absoluteFilePath()) { return {}; }
        Handle base(::open(QFile::encodeName(basePath).constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
        if (!privateNode(base.fd,true) || !samePath(base.fd,QFile::encodeName(basePath))) { return {}; }
        const auto leaf=("feature-create-"+run).toLatin1();
        if (operation=="stage") {
            const auto encoded=command.value("inputBase64").toString().toLatin1();const auto raw=QByteArray::fromBase64(encoded);
            if (raw.isEmpty() || raw.size()>8192 || raw.toBase64()!=encoded || ::mkdirat(base.fd,leaf.constData(),0700)!=0) { return {}; }
            Handle root(::openat(base.fd,leaf.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
            if (!privateNode(root.fd,true)) { return {}; }
            const QJsonObject manifest{{"createFileOwnerVersion",1},{"runId",run},{"ownerToken",owner},
                {"inputSha256",QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex())}};
            if (!writeNew(root.fd,".owner.v1.json",QJsonDocument(manifest).toJson(QJsonDocument::Compact))
                    || !writeNew(root.fd,"entity-import.json",raw) || ::fsync(root.fd)!=0 || ::fsync(base.fd)!=0) { return {}; }
            return {{"performed",true}};
        }
        Handle root(::openat(base.fd,leaf.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
        if (root.fd<0) {
            if (errno!=ENOENT) { return {}; }
            if (operation=="locate") { return {{"exists",false},{"directory",QUrl::fromLocalFile(basePath+'/'+QString::fromLatin1(leaf)).toString()}}; }
            if (operation=="observe") { return {{"exists",false},{"files",QVariantList{}}}; }
            return {{"performed",true}};
        }
        if (!privateNode(root.fd,true) || !sameChild(base.fd,leaf,root.fd)
                || !entries(root.fd,{".owner.v1.json","entity-import.json","export.json"})) { return {}; }
        QByteArray ownerRaw;if (!readFile(root.fd,".owner.v1.json",ownerRaw,4096)) { return {}; }
        QJsonParseError parse;const auto manifestDoc=QJsonDocument::fromJson(ownerRaw,&parse);const auto manifest=manifestDoc.object();
        if (parse.error!=QJsonParseError::NoError || manifest.size()!=4 || manifest.value("createFileOwnerVersion")!=QJsonValue(1)
                || manifest.value("runId")!=QJsonValue(run) || manifest.value("ownerToken")!=QJsonValue(owner)
                || !QRegularExpression("\\A[0-9a-f]{64}\\z").match(manifest.value("inputSha256").toString()).hasMatch()) { return {}; }
        const auto path=QUrl::fromLocalFile(basePath+'/'+QString::fromLatin1(leaf)).toString();
        if (operation=="locate") { return {{"exists",true},{"directory",path}}; }
        QVariantList files;
        for (const auto& name:QStringList{"entity-import.json","export.json"}) {
            const auto local=QFile::encodeName(name);struct stat current;
            if (::fstatat(root.fd,local.constData(),&current,AT_SYMLINK_NOFOLLOW)!=0) {
                if (errno!=ENOENT) { return {}; }
                files.append(QVariantMap{{"name",name},{"exists",false}});continue;
            }
            QByteArray bytes;QVariantMap identity;
            if (!readOriginal(root.fd,local,bytes,identity,name=="export.json" ? 65536 : 8192)) { return {}; }
            const auto sha=QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());
            if (name=="entity-import.json" && sha!=manifest.value("inputSha256").toString()) { return {}; }
            files.append(QVariantMap{{"name",name},{"exists",true},{"bytes",bytes.size()},{"sha256",sha},
                {"base64",QString::fromLatin1(bytes.toBase64())},{"identity",identity}});
        }
        if (!samePath(base.fd,QFile::encodeName(basePath)) || !sameChild(base.fd,leaf,root.fd)) { return {}; }
        if (operation=="observe") { return {{"exists",true},{"directory",path},{"files",files}}; }
        if (operation!="release" || command.value("originals").toList()!=files) { return {}; }
        // The exact independent originals are required; no blanket removal and
        // no assertion-reference bytes stand in for an actual product export.
        for (const auto& file:files) {
            const auto row=file.toMap();if (!row.value("exists").toBool()) { continue; }
            const auto local=QFile::encodeName(row.value("name").toString());struct stat current;
            if (::fstatat(root.fd,local.constData(),&current,AT_SYMLINK_NOFOLLOW)!=0
                    || identityFor(current)!=row.value("identity").toMap() || ::unlinkat(root.fd,local.constData(),0)!=0) { return {}; }
        }
        if (::unlinkat(root.fd,".owner.v1.json",0)!=0 || ::unlinkat(base.fd,leaf.constData(),AT_REMOVEDIR)!=0 || ::fsync(base.fd)!=0) { return {}; }
        return {{"performed",true}};
#else
        Q_UNUSED(directory);Q_UNUSED(command);return {};
#endif
    }
private:
#if defined(Q_OS_UNIX)
    static QVariantMap identityFor(const struct stat& value) {
        return {{"device",QString::number(value.st_dev)},{"inode",QString::number(value.st_ino)},
            {"bytes",QString::number(value.st_size)},{"modifiedSeconds",QString::number(value.st_mtimespec.tv_sec)},
            {"modifiedNanoseconds",QString::number(value.st_mtimespec.tv_nsec)},
            {"changedSeconds",QString::number(value.st_ctimespec.tv_sec)},
            {"changedNanoseconds",QString::number(value.st_ctimespec.tv_nsec)}};
    }
    static bool readOriginal(int parent,const QByteArray& name,QByteArray& bytes,QVariantMap& identity,int maximum) {
        const int fd=::openat(parent,name.constData(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK);if (fd<0) { return false; }
        struct stat before,after,path;
        bool okay=::fstat(fd,&before)==0 && S_ISREG(before.st_mode) && before.st_nlink==1 && before.st_uid==::geteuid()
            && (before.st_mode&0777)==0600 && before.st_size>0 && before.st_size<=maximum;
        // Actual exports may use the product's ordinary 0644 mode inside this
        // private 0700 root. Never chmod the product file into an expected mode.
        if (!okay && name=="export.json") {
            okay=::fstat(fd,&before)==0 && S_ISREG(before.st_mode) && before.st_nlink==1 && before.st_uid==::geteuid()
                && (before.st_mode&0777)==0644 && before.st_size>0 && before.st_size<=maximum;
        }
        bytes.clear();char buffer[4096];
        while (okay) {
            const auto count=::read(fd,buffer,sizeof(buffer));if (count<0 && errno==EINTR) { continue; }
            if (count<0 || bytes.size()+count>maximum) { okay=false;break; }
            if (!count) { break; }bytes.append(buffer,static_cast<int>(count));
        }
        okay=okay && ::fstat(fd,&after)==0 && ::fstatat(parent,name.constData(),&path,AT_SYMLINK_NOFOLLOW)==0
            && identityFor(before)==identityFor(after) && identityFor(before)==identityFor(path) && bytes.size()==before.st_size;
        if (okay) { identity=identityFor(before); }
        ::close(fd);return okay;
    }
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
#endif
