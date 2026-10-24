// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUrl>
#include <QVariantMap>
#include <algorithm>
#include <cerrno>
#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace overte::e2e {
// Closed asset INPUT files only. This never uploads, imports, bakes or creates
// a product success. Every deletion is confined to its original private root.
class PrivateAssetFiles {
public:
    static QStringList names(const QString& resource) {
        if (resource=="gltf-bundle/main.gltf") {return {"main.gltf","mesh/triangle.bin","textures/checker.png"};}
        if (resource=="obj-bundle/main.obj") {return {"main.obj","materials/palette.mtl","textures/checker.png"};}
        if (resource=="asset-stand.fbx") {return {"stand.fbx"};}return {};
    }
    static QVariantMap request(const QString& directory,const QVariantMap& command,const QJsonObject& ui,const QJsonObject& work) {
        if (!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
                || !QCoreApplication::arguments().contains("--testScript")) {return {};}
        const auto run=command.value("runId").toString(),owner=command.value("ownerToken").toString();
        const auto ticket=command.value("ticket").toString(),resource=command.value("resource").toString(),operation=command.value("operation").toString();
        const auto paths=names(resource);
        if (!QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch() || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(ticket).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{64}\\z").match(owner).hasMatch() || paths.isEmpty()
                || !QStringList{"stage","observe","retire-primary","release"}.contains(operation)) {return {};}
        const QFileInfo baseInfo(QDir(directory).absolutePath());const auto basePath=baseInfo.canonicalFilePath();
        if (basePath.isEmpty() || basePath!=baseInfo.absoluteFilePath()) {return {};}
        Handle base(::open(QFile::encodeName(basePath).constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
        if (!privateNode(base.fd,true) || !samePath(base.fd,QFile::encodeName(basePath))) {return {};}
        const auto leaf=("feature-assets-"+run+'-'+owner.left(16)).toLatin1();
        if (operation=="stage") {
            const auto input=command.value("files").toMap();auto keys=input.keys();auto expected=paths;expected.sort();
            if (keys!=expected) {return {};}
            QMap<QString,QByteArray> originals;QJsonArray manifestFiles;int total=0;
            for (const auto& path:paths) {
                if (input.value(path).userType()!=QMetaType::QString) {return {};}
                const auto encoded=input.value(path).toString().toLatin1(),raw=QByteArray::fromBase64(encoded);
                if (raw.isEmpty() || raw.size()>32768 || raw.toBase64()!=encoded || (total+=raw.size())>65536) {return {};}
                originals.insert(path,raw);manifestFiles.append(QJsonObject{{"path",path},{"bytes",raw.size()},{"sha256",sha(raw)}});
            }
            if (::mkdirat(base.fd,leaf.constData(),0700)!=0) {return {};}
            Handle root(::openat(base.fd,leaf.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
            if (!privateNode(root.fd,true)) {return {};}
            const QJsonObject manifest{{"assetFileOwnerVersion",1},{"runId",run},{"ownerToken",owner},{"ticket",ticket},
                {"resource",resource},{"primaryPath",paths.first()},{"files",manifestFiles}};
            const auto ownerBytes=QJsonDocument(manifest).toJson(QJsonDocument::Compact);
            if (!writeNew(root.fd,".owner.v1.json",ownerBytes)) {return {};}
            for (auto it=originals.cbegin();it!=originals.cend();++it) {
                const auto split=it.key().split('/');int parent=root.fd;Handle nested;
                if (split.size()==2) {
                    const auto dir=QFile::encodeName(split.first());
                    if (::mkdirat(root.fd,dir.constData(),0700)!=0 && errno!=EEXIST) {return {};}
                    nested.fd=::openat(root.fd,dir.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);parent=nested.fd;
                    if (!privateNode(parent,true)) {return {};}
                }
                if (!writeNew(parent,QFile::encodeName(split.last()),it.value()) || ::fsync(parent)!=0) {return {};}
            }
            // Seal the actual created root, parents and file inodes before
            // admitting stage completion. Equal replacement bytes cannot
            // become new deletion authority after a lost stage return.
            QJsonArray sealedFiles;
            for (const auto& path:paths) {
                const auto split=path.split('/');int parent=root.fd;Handle nested;
                if (split.size()==2) {
                    nested.fd=::openat(root.fd,QFile::encodeName(split.first()).constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
                    if (!privateNode(nested.fd,true) || !sameChild(root.fd,QFile::encodeName(split.first()),nested.fd)) {return {};}
                    parent=nested.fd;
                }
                QByteArray actual;QVariantMap original;
                if (!readOriginal(parent,QFile::encodeName(split.last()),actual,original,32768) || actual!=originals.value(path)) {return {};}
                sealedFiles.append(QJsonObject{{"path",path},{"identity",QJsonObject::fromVariantMap(original)},{"parent",node(parent)}});
            }
            const QJsonObject seal{{"assetFileSealVersion",1},{"ownerSha256",sha(ownerBytes)},{"root",node(root.fd)},{"files",sealedFiles}};
            if (seal.value("root").toObject().isEmpty() || !sameChild(base.fd,leaf,root.fd) || !samePath(base.fd,QFile::encodeName(basePath))
                    || !writeNew(root.fd,".complete.v1.json",QJsonDocument(seal).toJson(QJsonDocument::Compact))
                    || ::fsync(root.fd)!=0 || ::fsync(base.fd)!=0) {return {};}
            return {{"performed",true}};
        }
        Handle root(::openat(base.fd,leaf.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
        if (root.fd<0) {return errno==ENOENT && operation=="observe" ? QVariantMap{{"exists",false},{"files",QVariantList{}}} : QVariantMap{};}
        if (!privateNode(root.fd,true) || !sameChild(base.fd,leaf,root.fd)) {return {};}
        QByteArray bytes;QVariantMap ownerIdentity;
        if (!readOriginal(root.fd,".owner.v1.json",bytes,ownerIdentity,8192)) {return {};}
        const auto document=QJsonDocument::fromJson(bytes);const auto manifest=document.object();
        const auto ownerBytes=bytes;
        if (QJsonDocument(manifest).toJson(QJsonDocument::Compact)!=bytes || manifest.size()!=7
                || manifest.value("assetFileOwnerVersion")!=QJsonValue(1) || manifest.value("runId")!=QJsonValue(run)
                || manifest.value("ownerToken")!=QJsonValue(owner) || manifest.value("ticket")!=QJsonValue(ticket)
                || manifest.value("resource")!=QJsonValue(resource) || manifest.value("primaryPath")!=QJsonValue(paths.first())
                || manifest.value("files").toArray().size()!=paths.size()) {return {};}
        QSet<QString> allowed{".owner.v1.json",".complete.v1.json",".retire-primary.v1.json",".release.v1.json"};
        for (const auto& path:paths) {allowed.insert(path);if (path.contains('/')) {allowed.insert(path.section('/',0,0));}}
        if (!entries(root.fd,allowed,QString(),0)) {return {};}
        bool complete=false,retired=false,releasing=false;QJsonObject seal;QVariantMap sealIdentity;
        if (!readSeal(root.fd,ownerBytes,paths,seal,sealIdentity,complete) || !marker(root.fd,".retire-primary.v1.json",retired)
                || !marker(root.fd,".release.v1.json",releasing)) {return {};}
        QVariantList files;
        const auto descriptors=manifest.value("files").toArray();
        for (int index=0;index<paths.size();++index) {
            const auto path=paths[index];const auto expected=descriptors[index].toObject();
            if (expected.size()!=3 || expected.value("path")!=QJsonValue(path) || expected.value("bytes").toInt()<=0
                    || expected.value("bytes").toInt()>32768 || !QRegularExpression("\\A[a-f0-9]{64}\\z").match(expected.value("sha256").toString()).hasMatch()) {return {};}
            const auto split=path.split('/');int parent=root.fd;Handle nested;
            if (split.size()==2) {
                nested.fd=::openat(root.fd,QFile::encodeName(split.first()).constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
                if (nested.fd<0 && errno!=ENOENT) {return {};}
                if (nested.fd>=0 && (!privateNode(nested.fd,true) || !sameChild(root.fd,QFile::encodeName(split.first()),nested.fd))) {return {};}parent=nested.fd;
            }
            const auto original=complete ? seal.value("files").toArray().at(index).toObject() : QJsonObject{};
            if (complete && parent>=0 && original.value("parent").toObject()!=node(parent)) {return {};}
            const auto local=QFile::encodeName(split.last());struct stat actual;
            const bool exists=parent>=0 && ::fstatat(parent,local.constData(),&actual,AT_SYMLINK_NOFOLLOW)==0;
            if (!exists) {
                if (parent>=0 && errno!=ENOENT) {return {};}
                if (complete && !releasing && !(retired && index==0)) {return {};}
                files.append(QVariantMap{{"path",path},{"exists",false}});continue;
            }
            QVariantMap identity;if (!readOriginal(parent,local,bytes,identity,32768) || bytes.size()!=expected.value("bytes").toInt()
                    || sha(bytes)!=expected.value("sha256").toString()
                    || complete && original.value("identity").toObject()!=QJsonObject::fromVariantMap(identity)) {return {};}
            files.append(QVariantMap{{"path",path},{"exists",true},{"bytes",bytes.size()},{"sha256",sha(bytes)},
                {"base64",QString::fromLatin1(bytes.toBase64())},{"identity",identity}});
        }
        if (!samePath(base.fd,QFile::encodeName(basePath)) || !sameChild(base.fd,leaf,root.fd)) {return {};}
        const auto path=QUrl::fromLocalFile(basePath+'/'+QString::fromLatin1(leaf)).toString();
        if (operation=="observe") {return {{"exists",true},{"directory",path},{"complete",complete},{"retiredPrimary",retired},
            {"releasing",releasing},{"manifest",manifest.toVariantMap()},{"ownerBase64",QString::fromLatin1(ownerBytes.toBase64())},
            {"seal",complete ? QVariant(seal.toVariantMap()) : QVariant()},{"files",files}};}
        if (!complete) {return {};}
        if (QJsonArray::fromVariantList(command.value("originals").toList())!=QJsonArray::fromVariantList(files)
                || !consumersQuiet(ui,work,operation=="retire-primary",path+'/'+paths.first())) {return {};}
        if (operation=="retire-primary") {
            const auto original=files.first().toMap();
            if (!complete || retired || releasing || !original.value("exists").toBool()
                    || !writeNew(root.fd,".retire-primary.v1.json",QByteArray("{}")) || ::fsync(root.fd)!=0
                    || !unlinkOriginal(root.fd,QFile::encodeName(paths.first()),original) || ::fsync(root.fd)!=0) {return {};}
            return {{"performed",true}};
        }
        if (!releasing && (!writeNew(root.fd,".release.v1.json",QByteArray("{}")) || ::fsync(root.fd)!=0)) {return {};}
        QSet<QString> directories;
        for (const auto& value:files) {
            const auto row=value.toMap();const auto split=row.value("path").toString().split('/');int parent=root.fd;Handle nested;
            if (split.size()==2) {
                directories.insert(split.first());nested.fd=::openat(root.fd,QFile::encodeName(split.first()).constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
                if (nested.fd<0 && errno!=ENOENT) {return {};}
                if (nested.fd>=0 && (!privateNode(nested.fd,true) || !sameChild(root.fd,QFile::encodeName(split.first()),nested.fd))) {return {};}
                parent=nested.fd;
            }
            if (!samePath(base.fd,QFile::encodeName(basePath)) || !sameChild(base.fd,leaf,root.fd)
                    || row.value("exists").toBool() && (parent<0 || !unlinkOriginal(parent,QFile::encodeName(split.last()),row))) {return {};}
        }
        for (const auto& folder:directories) {
            QJsonObject expected;
            for (const auto& value:seal.value("files").toArray()) {
                const auto original=value.toObject();
                if (original.value("path").toString().startsWith(folder+'/')) {
                    const auto parent=original.value("parent").toObject();
                    if (!expected.isEmpty() && expected!=parent) {return {};}expected=parent;
                }
            }
            const auto local=QFile::encodeName(folder);struct stat current;
            if (expected.isEmpty()) {return {};}
            if (::fstatat(root.fd,local.constData(),&current,AT_SYMLINK_NOFOLLOW)!=0) {if (errno==ENOENT) {continue;}return {};}
            Handle original(::openat(root.fd,local.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
            if (!privateNode(original.fd,true) || node(original.fd)!=expected || !sameChild(root.fd,local,original.fd)
                    || !samePath(base.fd,QFile::encodeName(basePath)) || !sameChild(base.fd,leaf,root.fd)
                    || ::unlinkat(root.fd,local.constData(),AT_REMOVEDIR)!=0) {return {};}
        }
        for (const auto& name:QStringList{".complete.v1.json",".retire-primary.v1.json",".release.v1.json",".owner.v1.json"}) {
            const auto local=QFile::encodeName(name);struct stat current;
            if (::fstatat(root.fd,local.constData(),&current,AT_SYMLINK_NOFOLLOW)!=0) {if (errno==ENOENT && name!=".owner.v1.json") {continue;}return {};}
            QByteArray original;QVariantMap originalIdentity;
            const bool owner=name==".owner.v1.json",completed=name==".complete.v1.json";
            if (!readOriginal(root.fd,local,original,originalIdentity,owner || completed ? 8192 : 2)
                    || (owner ? originalIdentity!=ownerIdentity || original!=ownerBytes
                        : completed ? originalIdentity!=sealIdentity || original!=QJsonDocument(seal).toJson(QJsonDocument::Compact) : original!="{}")
                    || !samePath(base.fd,QFile::encodeName(basePath)) || !sameChild(base.fd,leaf,root.fd)
                    || !unlinkOriginal(root.fd,local,{{"identity",originalIdentity}})) {return {};}
        }
        if (!samePath(base.fd,QFile::encodeName(basePath)) || !sameChild(base.fd,leaf,root.fd)
                || ::unlinkat(base.fd,leaf.constData(),AT_REMOVEDIR)!=0 || ::fsync(base.fd)!=0) {return {};}
        return {{"performed",true}};
    }
private:
    struct Handle {int fd {-1};Handle()=default;explicit Handle(int value):fd(value){}~Handle(){if(fd>=0){::close(fd);}}Handle(const Handle&)=delete;Handle& operator=(const Handle&)=delete;};
    static QString sha(const QByteArray& bytes) {return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());}
    static bool privateNode(int fd,bool directory) {struct stat value;return fd>=0 && ::fstat(fd,&value)==0 && value.st_uid==::geteuid()
        && (value.st_mode&0777)==(directory ? 0700 : 0600) && (directory ? S_ISDIR(value.st_mode) : S_ISREG(value.st_mode) && value.st_nlink==1);}
    static bool samePath(int fd,const QByteArray& path) {struct stat a,b;return ::fstat(fd,&a)==0 && ::lstat(path.constData(),&b)==0 && S_ISDIR(b.st_mode) && a.st_dev==b.st_dev && a.st_ino==b.st_ino;}
    static bool sameChild(int parent,const QByteArray& name,int fd) {struct stat a,b;return ::fstat(fd,&a)==0 && ::fstatat(parent,name.constData(),&b,AT_SYMLINK_NOFOLLOW)==0 && S_ISDIR(b.st_mode) && a.st_dev==b.st_dev && a.st_ino==b.st_ino;}
    static QJsonObject node(int fd) {struct stat value;if (!privateNode(fd,true) || ::fstat(fd,&value)!=0) {return {};}
        return {{"device",QString::number(value.st_dev)},{"inode",QString::number(value.st_ino)}};}
    static QVariantMap identity(const struct stat& value) {return {{"device",QString::number(value.st_dev)},{"inode",QString::number(value.st_ino)},{"bytes",QString::number(value.st_size)},
        {"modifiedSeconds",QString::number(value.st_mtimespec.tv_sec)},{"modifiedNanoseconds",QString::number(value.st_mtimespec.tv_nsec)},
        {"changedSeconds",QString::number(value.st_ctimespec.tv_sec)},{"changedNanoseconds",QString::number(value.st_ctimespec.tv_nsec)}};}
    static bool readOriginal(int parent,const QByteArray& name,QByteArray& bytes,QVariantMap& result,int maximum) {
        Handle file(::openat(parent,name.constData(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK));struct stat before,after,current;
        if (!privateNode(file.fd,false) || ::fstat(file.fd,&before)!=0 || before.st_size<=0 || before.st_size>maximum) {return false;}
        bytes.clear();char buffer[4096];
        for (;;) {const auto count=::read(file.fd,buffer,sizeof(buffer));if(count<0 && errno==EINTR){continue;}if(count<0 || bytes.size()+count>maximum){return false;}if(!count){break;}bytes.append(buffer,static_cast<int>(count));}
        if (::fstat(file.fd,&after)!=0 || ::fstatat(parent,name.constData(),&current,AT_SYMLINK_NOFOLLOW)!=0
                || identity(before)!=identity(after) || identity(before)!=identity(current) || bytes.size()!=before.st_size || !privateNode(file.fd,false)) {return false;}
        result=identity(before);return true;
    }
    static bool writeNew(int parent,const QByteArray& name,const QByteArray& bytes) {
        Handle file(::openat(parent,name.constData(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600));if(!privateNode(file.fd,false)){return false;}
        qint64 done=0;while(done<bytes.size()){const auto count=::write(file.fd,bytes.constData()+done,bytes.size()-done);if(count<0 && errno==EINTR){continue;}if(count<=0){return false;}done+=count;}return ::fsync(file.fd)==0;
    }
    static bool marker(int parent,const QByteArray& name,bool& present) {struct stat value;if(::fstatat(parent,name.constData(),&value,AT_SYMLINK_NOFOLLOW)!=0){present=false;return errno==ENOENT;}
        QByteArray bytes;QVariantMap unused;present=true;return readOriginal(parent,name,bytes,unused,2) && bytes=="{}";}
    static bool readSeal(int root,const QByteArray& owner,const QStringList& paths,QJsonObject& seal,QVariantMap& original,bool& complete) {
        struct stat current;
        if (::fstatat(root,".complete.v1.json",&current,AT_SYMLINK_NOFOLLOW)!=0) {complete=false;return errno==ENOENT;}
        complete=true;QByteArray bytes;
        if (!readOriginal(root,".complete.v1.json",bytes,original,8192)) {return false;}
        seal=QJsonDocument::fromJson(bytes).object();const auto rows=seal.value("files").toArray();
        if (QJsonDocument(seal).toJson(QJsonDocument::Compact)!=bytes || seal.size()!=4
                || seal.value("assetFileSealVersion")!=QJsonValue(1) || seal.value("ownerSha256")!=QJsonValue(sha(owner))
                || seal.value("root").toObject()!=node(root) || rows.size()!=paths.size()) {return false;}
        for (int index=0;index<paths.size();++index) {
            const auto row=rows.at(index).toObject();
            if (row.size()!=3 || row.value("path")!=QJsonValue(paths[index]) || !row.value("identity").isObject()
                    || row.value("identity").toObject().size()!=7 || !row.value("parent").isObject() || row.value("parent").toObject().size()!=2) {return false;}
        }
        return true;
    }
    static bool unlinkOriginal(int parent,const QByteArray& name,const QVariantMap& row) {struct stat value;return ::fstatat(parent,name.constData(),&value,AT_SYMLINK_NOFOLLOW)==0
        && S_ISREG(value.st_mode) && value.st_uid==::geteuid() && value.st_nlink==1 && (value.st_mode&0777)==0600
        && identity(value)==row.value("identity").toMap() && ::unlinkat(parent,name.constData(),0)==0;}
    static bool entries(int parent,const QSet<QString>& allowed,const QString& prefix,int depth) {
        if(depth>1){return false;}const int copy=::dup(parent);if(copy<0){return false;}DIR* directory=::fdopendir(copy);if(!directory){::close(copy);return false;}
        bool okay=true;int count=0;errno=0;
        while(auto entry=::readdir(directory)){const auto name=QString::fromLocal8Bit(entry->d_name);if(name=="." || name==".."){continue;}
            const auto path=prefix+name;struct stat value;if(++count>8 || !allowed.contains(path) || ::fstatat(parent,entry->d_name,&value,AT_SYMLINK_NOFOLLOW)!=0){okay=false;break;}
            if(S_ISDIR(value.st_mode)){Handle child(::openat(parent,entry->d_name,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));if(!privateNode(child.fd,true) || !entries(child.fd,allowed,path+'/',depth+1)){okay=false;break;}}
            else if(!S_ISREG(value.st_mode) || value.st_uid!=::geteuid() || value.st_nlink!=1 || (value.st_mode&0777)!=0600){okay=false;break;}
            errno=0;
        }
        okay=okay && errno==0;::closedir(directory);return okay;
    }
    static bool consumersQuiet(const QJsonObject& ui,const QJsonObject& work,bool retire,const QString& primary) {
        if(ui.value("available")!=QJsonValue(true) || ui.value("complete")!=QJsonValue(true)
                || work.value("available")!=QJsonValue(true) || work.value("complete")!=QJsonValue(true)){return false;}
        bool selected=false;int pickerCount=0;
        for(const auto& item:ui.value("roots").toArray()){const auto row=item.toObject();if(row.value("alive")!=QJsonValue(true)){continue;}
            if(row.value("role")==QJsonValue("page") && (row.value("busy")!=QJsonValue(false)
                    || row.value("pendingBundle")!=QJsonValue(false) || row.value("destinationOpen")!=QJsonValue(false)
                    || !row.value("bundleRequest").toString().isEmpty())){return false;}
            if(row.value("role")==QJsonValue("picker")){
                ++pickerCount;
                if(!retire || row.value("closing")!=QJsonValue(false) || row.value("visible")!=QJsonValue(true) || row.value("windowId").isNull()){return false;}
                if (!row.value("requestId").toString().isEmpty() || row.value("bundleReview")!=QJsonValue(false)) {return false;}
                const auto chosen=row.value("chosen").toArray();selected=chosen.size()==1 && chosen.first()==QJsonValue(primary);
            }
        }
        for(const auto& item:work.value("jobs").toArray()){const auto row=item.toObject();if(row.value("alive")!=QJsonValue(false) || row.value("pendingBodies").toDouble(-1)!=0
                || (row.value("kind")==QJsonValue("bundle") && row.value("terminal")!=QJsonValue(true))){return false;}}
        return !retire || pickerCount==1 && selected;
    }
};
} // namespace overte::e2e
#endif
