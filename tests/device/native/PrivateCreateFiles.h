// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QThread>
#include <QUrl>
#include <QMap>
#include <QSet>
#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <cerrno>

namespace overte::e2e {
// App-private test inputs and independently read product output. This class
// cannot write selection.json, import entities, invoke a dialog or export.
class PrivateCreateFiles {
public:
    QVariantMap request(const QString& directory,const QVariantMap& command) {
        const auto json=QJsonObject::fromVariantMap(command);
        QStringList keys{"schemaVersion","commandId","action","operation","runId","ownerToken"};
        const auto operation=command.value("operation").toString();
        if (operation=="stage") { keys.append("files"); } keys.sort();
        const auto run=command.value("runId").toString(),owner=command.value("ownerToken").toString();
        const QRegularExpression nonce("\\A[0-9a-f]{32}\\z"),token("\\A[0-9a-f]{64}\\z");
        if (QThread::currentThread()!=QCoreApplication::instance()->thread()
                || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=keys
                || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble()!=1
                || command.value("action").toString()!="phone-create-files"
                || !json.value("commandId").isString() || !nonce.match(command.value("commandId").toString()).hasMatch()
                || !json.value("runId").isString() || !nonce.match(run).hasMatch()
                || !json.value("ownerToken").isString() || !token.match(owner).hasMatch()
                || !QStringList{"stage","observe","seal-export","release"}.contains(operation)) { return {}; }
        const auto basePath=QDir(directory).absolutePath();const QFileInfo info(basePath);
        if (info.canonicalFilePath()!=basePath) { return {}; }
        Handle base(::open(QFile::encodeName(basePath).constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
        if (!privateNode(base.fd,true) || !samePath(base.fd,QFile::encodeName(basePath))) { return {}; }
        const auto leaf=("feature-create-"+run).toLatin1();
        const auto key=QString::fromLatin1(QCryptographicHash::hash((basePath+'/'+run).toUtf8(),QCryptographicHash::Sha256).toHex());
        const auto ownerHash=QString::fromLatin1(QCryptographicHash::hash(owner.toLatin1(),QCryptographicHash::Sha256).toHex());
        if (_leases.contains(key) && _leases[key].ownerHash!=ownerHash) { return {}; }
        if (!_leases.contains(key) && _leases.size()>=256) { return {}; }
        auto& lease=_leases[key];if (lease.ownerHash.isEmpty()) { lease.ownerHash=ownerHash; }
        if (operation=="stage") {
            if (lease.retiring || lease.retired || !json.value("files").isObject()) { return {}; }
            const auto inputs=json.value("files").toObject();auto names=inputs.keys();names.sort();
            if (names!=QStringList{"entity-import.json","voxel-import.json"}) { return {}; }
            QMap<QString,QByteArray> originals;QJsonObject hashes;
            for (const auto& name:names) {
                if (!inputs.value(name).isString()) { return {}; }
                const auto encoded=inputs.value(name).toString().toLatin1();const auto raw=QByteArray::fromBase64(encoded);
                if (encoded.size()>32768 || raw.isEmpty() || raw.size()>16384 || raw.toBase64()!=encoded) { return {}; }
                originals[name]=raw;hashes[name]=sha(raw);
            }
            // Exclusive creation: a lost response is recovered by observe,
            // never by rerunning stage against a previously existing root.
            if (::mkdirat(base.fd,leaf.constData(),0700)!=0) { return {}; }
            Handle root(::openat(base.fd,leaf.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
            if (!privateNode(root.fd,true)) { return {}; }
            lease.root=identity(root.fd);lease.hashes=hashes;
            const QJsonObject manifest{{"createFilesVersion",1},{"runId",run},{"ownerSha256",ownerHash},{"hashes",hashes}};
            if (!writeNew(root.fd,".owner.v1.json",QJsonDocument(manifest).toJson(QJsonDocument::Compact))) { return {}; }
            for (auto it=originals.begin();it!=originals.end();++it) {
                if (!writeNew(root.fd,QFile::encodeName(it.key()),it.value())) { return {}; }
            }
            if (::fsync(root.fd) || ::fsync(base.fd)) { return {}; }
        }
        Handle root(::openat(base.fd,leaf.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
        if (root.fd<0) {
            if (errno!=ENOENT || operation=="seal-export") { return {}; }
            if (operation=="release") { lease.retiring=true;lease.retired=true; }
            return {{"createFilesVersion",1},{"exists",false},{"retired",lease.retired},{"retiring",lease.retiring},
                {"directory",QUrl::fromLocalFile(basePath+'/'+QString::fromLatin1(leaf)).toString()},{"rootIdentity",QVariant()},
                {"files",QVariantList{}},{"exportSealed",false}};
        }
        if (!privateNode(root.fd,true) || lease.retired || !entries(root.fd)) { return {}; }
        const auto actualRoot=identity(root.fd);
        // Directory size/times legitimately change as the ordinary product
        // saves a file; root device/inode remain pinned across those changes.
        if (!lease.root.isEmpty() && (lease.root.value("device")!=actualRoot.value("device")
                || lease.root.value("inode")!=actualRoot.value("inode"))) { return {}; }
        QByteArray manifestBytes;QVariantMap manifestIdentity;
        const bool manifestPresent=exists(root.fd,".owner.v1.json");
        if (manifestPresent) {
            if (!read(root.fd,".owner.v1.json",manifestBytes,manifestIdentity,4096,false)) { return {}; }
            QJsonParseError error;const auto document=QJsonDocument::fromJson(manifestBytes,&error);const auto manifest=document.object();
            if (error.error!=QJsonParseError::NoError || !document.isObject()
                    || QJsonDocument(manifest).toJson(QJsonDocument::Compact)!=manifestBytes || manifest.size()!=4
                    || manifest.value("createFilesVersion")!=QJsonValue(1) || manifest.value("runId")!=QJsonValue(run)
                    || manifest.value("ownerSha256")!=QJsonValue(ownerHash) || !manifest.value("hashes").isObject()) { return {}; }
            const auto hashes=manifest.value("hashes").toObject();auto names=hashes.keys();names.sort();
            if (names!=QStringList{"entity-import.json","voxel-import.json"}) { return {}; }
            for (const auto& name:names) { if (!token.match(hashes.value(name).toString()).hasMatch()) { return {}; } }
            if (!lease.hashes.isEmpty() && lease.hashes!=hashes) { return {}; }
            if (!lease.manifest.isEmpty() && lease.manifest!=manifestIdentity) { return {}; }
            lease.hashes=hashes;lease.root=actualRoot;lease.manifest=manifestIdentity;
        } else if (lease.root.isEmpty() || lease.hashes.isEmpty() || (!lease.retiring && operation!="release")) { return {}; }
        QVariantList files;QMap<QString,QVariantMap> identities;
        for (const auto& name:QStringList{"entity-import.json","voxel-import.json","selection.json"}) {
            const auto encoded=QFile::encodeName(name);
            if (!exists(root.fd,encoded)) {
                if (errno!=ENOENT) { return {}; }
                files.append(QVariantMap{{"name",name},{"exists",false}});continue;
            }
            QByteArray bytes;QVariantMap original;
            if (!read(root.fd,encoded,bytes,original,name=="selection.json" ? 65536 : 16384,name=="selection.json")) { return {}; }
            const auto digest=sha(bytes);
            if (name!="selection.json" && digest!=lease.hashes.value(name).toString()) { return {}; }
            auto receipt=original;receipt.insert("sha256",digest);
            if (name=="selection.json") {
                if (!lease.output.isEmpty() && lease.output!=receipt) { return {}; }
                if (operation=="seal-export") { lease.output=receipt; }
                if (operation=="release" && lease.output.isEmpty()) { return {}; }
            }
            identities[name]=original;
            files.append(QVariantMap{{"name",name},{"exists",true},{"identity",original},{"bytes",bytes.size()},
                {"sha256",digest},{"base64",QString::fromLatin1(bytes.toBase64())}});
        }
        if (operation=="seal-export" && lease.output.isEmpty()) { return {}; }
        if (!samePath(base.fd,QFile::encodeName(basePath)) || !sameChild(base.fd,leaf,root.fd)) { return {}; }
        if (operation=="release") {
            lease.retiring=true; // Fences any later stage before the first unlink.
            for (auto it=identities.begin();it!=identities.end();++it) {
                if (!sameFile(root.fd,QFile::encodeName(it.key()),it.value())
                        || ::unlinkat(root.fd,QFile::encodeName(it.key()).constData(),0)) { return {}; }
            }
            if (manifestPresent && (!sameFile(root.fd,".owner.v1.json",manifestIdentity)
                    || ::unlinkat(root.fd,".owner.v1.json",0))) { return {}; }
            if (!empty(root.fd) || !sameChild(base.fd,leaf,root.fd) || ::fsync(root.fd)
                    || ::unlinkat(base.fd,leaf.constData(),AT_REMOVEDIR) || ::fsync(base.fd)) { return {}; }
            lease.retired=true;
            return {{"createFilesVersion",1},{"exists",false},{"retired",true},{"retiring",true},
                {"directory",QUrl::fromLocalFile(basePath+'/'+QString::fromLatin1(leaf)).toString()},
                {"rootIdentity",QVariant()},{"files",QVariantList{}},{"exportSealed",false}};
        }
        return {{"createFilesVersion",1},{"exists",true},{"retired",false},{"retiring",lease.retiring},
            {"directory",QUrl::fromLocalFile(basePath+'/'+QString::fromLatin1(leaf)).toString()},
            {"rootIdentity",actualRoot},{"files",files},{"exportSealed",!lease.output.isEmpty()}};
    }
private:
    friend class PrivateAssetsFiles; // Reuse the same private inode/read primitives.
    struct Lease { QString ownerHash;QVariantMap root,output,manifest;QJsonObject hashes;bool retiring=false,retired=false; };
    QMap<QString,Lease> _leases;
    struct Handle { int fd;explicit Handle(int value):fd(value) {} ~Handle() { if(fd>=0) { ::close(fd); } } };
    static QString sha(const QByteArray& bytes) { return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()); }
    static bool privateNode(int fd,bool directory,bool productOutput=false) {
        struct stat node;
        return fd>=0 && !::fstat(fd,&node) && node.st_uid==::geteuid()
            && (directory ? S_ISDIR(node.st_mode) && (node.st_mode&0777)==0700
                : S_ISREG(node.st_mode) && node.st_nlink==1 && (productOutput ? (node.st_mode&0133)==0 : (node.st_mode&0777)==0600));
    }
    static QVariantMap identity(int fd) {
        struct stat node;if(::fstat(fd,&node)) { return {}; }
        return {{"device",QString::number(node.st_dev)},{"inode",QString::number(node.st_ino)},
            {"size",QString::number(node.st_size)},{"modifiedNs",QString::number(qint64(node.st_mtim.tv_sec)*1000000000LL+node.st_mtim.tv_nsec)},
            {"changedNs",QString::number(qint64(node.st_ctim.tv_sec)*1000000000LL+node.st_ctim.tv_nsec)}};
    }
    static bool exists(int parent,const QByteArray& name) {
        struct stat node;return ::fstatat(parent,name.constData(),&node,AT_SYMLINK_NOFOLLOW)==0;
    }
    static bool sameFile(int parent,const QByteArray& name,const QVariantMap& expected) {
        Handle file(::openat(parent,name.constData(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK));
        return file.fd>=0 && identity(file.fd)==expected;
    }
    static bool samePath(int fd,const QByteArray& path) {
        struct stat opened,current;return !::fstat(fd,&opened) && !::lstat(path.constData(),&current)
            && S_ISDIR(current.st_mode) && opened.st_dev==current.st_dev && opened.st_ino==current.st_ino;
    }
    static bool sameChild(int parent,const QByteArray& name,int fd) {
        struct stat opened,current;return !::fstat(fd,&opened) && !::fstatat(parent,name.constData(),&current,AT_SYMLINK_NOFOLLOW)
            && S_ISDIR(current.st_mode) && opened.st_dev==current.st_dev && opened.st_ino==current.st_ino;
    }
    static bool writeNew(int parent,const QByteArray& name,const QByteArray& bytes) {
        Handle file(::openat(parent,name.constData(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600));
        if (!privateNode(file.fd,false)) { return false; }
        qint64 done=0;while(done<bytes.size()) {
            const auto count=::write(file.fd,bytes.constData()+done,bytes.size()-done);
            if(count<0 && errno==EINTR) { continue; } if(count<=0) { return false; } done+=count;
        }
        return ::fsync(file.fd)==0;
    }
    static bool read(int parent,const QByteArray& name,QByteArray& bytes,QVariantMap& original,int limit,bool productOutput) {
        Handle file(::openat(parent,name.constData(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK));
        if (!privateNode(file.fd,false,productOutput)) { return false; }
        original=identity(file.fd);bool valid=false;const auto size=original.value("size").toString().toLongLong(&valid);
        if (!valid || size<=0 || size>limit) { return false; }
        bytes.clear();char buffer[4096];for(;;) {
            const auto count=::read(file.fd,buffer,sizeof(buffer));if(count<0 && errno==EINTR) { continue; }
            if(count<0 || bytes.size()+count>limit) { return false; } if(!count) { break; }bytes.append(buffer,int(count));
        }
        return bytes.size()==size && identity(file.fd)==original && privateNode(file.fd,false,productOutput)
            && sameFile(parent,name,original);
    }
    static bool directoryEntries(int parent,bool requireEmpty) {
        const int copy=::openat(parent,".",O_RDONLY|O_DIRECTORY|O_CLOEXEC);if(copy<0) { return false; }
        DIR* directory=::fdopendir(copy);if(!directory) { ::close(copy);return false; }
        bool valid=true;int count=0;errno=0;
        const QSet<QString> allowed{".owner.v1.json","entity-import.json","voxel-import.json","selection.json"};
        while(auto entry=::readdir(directory)) {
            const auto name=QString::fromLocal8Bit(entry->d_name);if(name=="." || name=="..") { continue; }
            if(requireEmpty || ++count>4 || !allowed.contains(name)) { valid=false;break; }
        }
        valid=valid && errno==0;::closedir(directory);return valid;
    }
    static bool entries(int parent) { return directoryEntries(parent,false); }
    static bool empty(int parent) { return directoryEntries(parent,true); }
};
} // namespace overte::e2e
#endif
