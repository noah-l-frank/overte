// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include "PrivateCreateFiles.h"
#include <algorithm>

namespace overte::e2e {
// Only fixed controlled INPUT bundles. No AssetClient, mapping/upload setter,
// model constructor, file browser service or generic local path is exposed.
class PrivateAssetsFiles {
    using Base=PrivateCreateFiles;
    using Handle=Base::Handle;
    struct Lease {
        QString ownerHash;QVariantMap root,manifest;QMap<QString,QVariantMap> directories,files;
        QJsonObject hashes;bool staged{false},retiring{false},retired{false},retirePrimaryRequested{false};
    };
    QMap<QString,Lease> _leases;
public:
    static QStringList inputs() { return {"gltf-bundle/main.gltf","gltf-bundle/mesh/triangle.bin","gltf-bundle/textures/checker.png",
        "obj-bundle/main.obj","obj-bundle/materials/palette.mtl","obj-bundle/textures/checker.png","fbx-bundle/stand.fbx"}; }
    QVariantMap request(const QString& directory,const QVariantMap& command) {
        const auto json=QJsonObject::fromVariantMap(command);const auto operation=command.value("operation").toString();
        const bool stagedGeneration=json.contains("stage");const int generation=stagedGeneration ? command.value("stage").toInt() : 0;
        QStringList keys{"schemaVersion","commandId","action","operation","runId","ownerToken"};if(stagedGeneration){keys.append("stage");}if(operation=="stage"){keys.append("files");}keys.sort();
        const auto run=command.value("runId").toString(),owner=command.value("ownerToken").toString();
        const QRegularExpression nonce("\\A[0-9a-f]{32}\\z"),token("\\A[0-9a-f]{64}\\z");
        if (!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
                || !QCoreApplication::arguments().contains("--testScript") || command.keys()!=keys
                || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble()!=1
                || (stagedGeneration && (!json.value("stage").isDouble() || json.value("stage").toDouble()!=generation || generation<1 || generation>6))
                || command.value("action").toString()!="phone-assets-files"
                || !json.value("commandId").isString() || !nonce.match(command.value("commandId").toString()).hasMatch()
                || !json.value("runId").isString() || !nonce.match(run).hasMatch() || run==QString(32,'0')
                || !json.value("ownerToken").isString() || !token.match(owner).hasMatch()
                || !QStringList{"stage","observe","retire-primary","release"}.contains(operation)) { return {}; }
        const auto basePath=QDir(directory).absolutePath();const QFileInfo info(basePath);
        if(info.canonicalFilePath()!=basePath){return {};}
        Handle base(::open(QFile::encodeName(basePath).constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
        if(!Base::privateNode(base.fd,true)||!Base::samePath(base.fd,QFile::encodeName(basePath))){return {};}
        const auto suffix=stagedGeneration ? "-stage"+QString::number(generation) : QString();
        const auto leaf=("feature-assets-"+run+suffix).toLatin1();const auto key=Base::sha((basePath+'/'+run+suffix).toUtf8());
        const auto ownerHash=Base::sha(owner.toLatin1());
        if((_leases.contains(key)&&_leases[key].ownerHash!=ownerHash)||(!_leases.contains(key)&&_leases.size()>=256)){return {};}
        auto& lease=_leases[key];if(lease.ownerHash.isEmpty()){lease.ownerHash=ownerHash;}
        auto names=inputs();names.sort();const auto dirs=directories();
        if(operation=="stage"){
            if(lease.retiring||lease.retired||lease.retirePrimaryRequested||!json.value("files").isObject()){return {};}
            const auto values=json.value("files").toObject();if(values.keys()!=names){return {};}
            QMap<QString,QByteArray> originals;QJsonObject hashes;int total=0;
            for(const auto& name:names){
                if(!values.value(name).isString()){return {};}
                const auto encoded=values.value(name).toString().toLatin1();const auto raw=QByteArray::fromBase64(encoded);
                if(encoded.size()>65536||raw.isEmpty()||raw.size()>32768||raw.toBase64()!=encoded||(total+=raw.size())>131072){return {};}
                originals[name]=raw;hashes[name]=Base::sha(raw);
            }
            if(::mkdirat(base.fd,leaf.constData(),0700)){return {};}
            Handle root(::openat(base.fd,leaf.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
            if(!Base::privateNode(root.fd,true)){return {};}
            lease.root=Base::identity(root.fd);lease.hashes=hashes;
            for(const auto& dir:dirs){
                const auto parentName=dir.contains('/')?dir.left(dir.lastIndexOf('/')):QString();const auto child=dir.mid(dir.lastIndexOf('/')+1).toLatin1();
                Handle parent(openDirectory(root.fd,parentName,lease));if(parent.fd<0||::mkdirat(parent.fd,child.constData(),0700)){return {};}
                Handle created(::openat(parent.fd,child.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
                if(!Base::privateNode(created.fd,true)||!Base::sameChild(parent.fd,child,created.fd)){return {};}
                lease.directories[dir]=Base::identity(created.fd);if(::fsync(parent.fd)){return {};}
            }
            const QJsonObject manifest{{"assetsFilesVersion",1},{"runId",run},{"ownerSha256",ownerHash},{"hashes",hashes}};
            if(!Base::writeNew(root.fd,".owner.v1.json",QJsonDocument(manifest).toJson(QJsonDocument::Compact))){return {};}
            QByteArray manifestBytes;if(!Base::read(root.fd,".owner.v1.json",manifestBytes,lease.manifest,16384,false)){return {};}
            for(auto it=originals.begin();it!=originals.end();++it){
                const auto dir=it.key().left(it.key().lastIndexOf('/'));const auto name=it.key().mid(it.key().lastIndexOf('/')+1).toLatin1();
                Handle parent(openDirectory(root.fd,dir,lease));if(parent.fd<0||!Base::writeNew(parent.fd,name,it.value())){return {};}
                QByteArray actual;QVariantMap identity;
                if(!Base::read(parent.fd,name,actual,identity,32768,false)||actual!=it.value()||::fsync(parent.fd)){return {};}
                lease.files[it.key()]=identity;
            }
            if(::fsync(root.fd)||::fsync(base.fd)){return {};}
            lease.staged=true;
        }
        Handle root(::openat(base.fd,leaf.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
        if(root.fd<0){
            if(errno!=ENOENT||operation=="retire-primary"){return {};}
            if(operation=="release"){lease.retiring=lease.retired=true;}
            return absent(basePath,leaf,lease);
        }
        if(!Base::privateNode(root.fd,true)||lease.retired||lease.root.isEmpty()||!sameDirectory(Base::identity(root.fd),lease.root)
                ||!Base::sameChild(base.fd,leaf,root.fd)||!inventory(root.fd,QString(),lease)){return {};}
        if(operation=="release"){lease.retiring=true;} // Fence a partial stage before any cleanup.
        const bool manifestPresent=Base::exists(root.fd,".owner.v1.json");QByteArray rawManifest;QVariantMap manifestIdentity;
        if(manifestPresent){
            if(!Base::read(root.fd,".owner.v1.json",rawManifest,manifestIdentity,16384,false)||manifestIdentity!=lease.manifest){return {};}
            const auto original=QJsonDocument::fromJson(rawManifest).object();
            if(original!=QJsonObject{{"assetsFilesVersion",1},{"runId",run},{"ownerSha256",ownerHash},{"hashes",lease.hashes}}){return {};}
        }else if(!lease.retiring){return {};}
        QVariantList files,actualDirs;QMap<QString,QVariantMap> identities;bool primaryGone=false;
        for(const auto& dir:dirs){
            Handle actual(openDirectory(root.fd,dir,lease));
            if(actual.fd<0){if(!lease.retiring){return {};}continue;}
            actualDirs.append(QVariantMap{{"name",dir},{"identity",Base::identity(actual.fd)}});
        }
        for(const auto& path:names){
            const auto dir=path.left(path.lastIndexOf('/'));const auto name=path.mid(path.lastIndexOf('/')+1).toLatin1();
            Handle parent(openDirectory(root.fd,dir,lease));const bool present=parent.fd>=0&&Base::exists(parent.fd,name);
            if(!present){
                if(!lease.retiring&&!(lease.retirePrimaryRequested&&path=="gltf-bundle/main.gltf")){return {};}
                if(path=="gltf-bundle/main.gltf"){primaryGone=true;}
                files.append(QVariantMap{{"name",path},{"exists",false},{"identity",QVariant()},{"bytes",0},{"sha256",""}});continue;
            }
            QByteArray bytes;QVariantMap identity;
            if(!Base::read(parent.fd,name,bytes,identity,32768,false)||identity!=lease.files.value(path)||Base::sha(bytes)!=lease.hashes.value(path).toString()){return {};}
            identities[path]=identity;files.append(QVariantMap{{"name",path},{"exists",true},{"identity",identity},{"bytes",bytes.size()},
                {"sha256",Base::sha(bytes)}});
        }
        if(!Base::samePath(base.fd,QFile::encodeName(basePath))||!Base::sameChild(base.fd,leaf,root.fd)){return {};}
        if(operation=="retire-primary"){
            if(lease.retiring||!lease.staged){return {};}
            lease.retirePrimaryRequested=true;
            if(!primaryGone){
                Handle parent(openDirectory(root.fd,"gltf-bundle",lease));
                if(parent.fd<0||!Base::sameFile(parent.fd,"main.gltf",identities.value("gltf-bundle/main.gltf"))
                        ||::unlinkat(parent.fd,"main.gltf",0)||::fsync(parent.fd)||Base::exists(parent.fd,"main.gltf")){return {};}
                primaryGone=true;
                for(auto& value:files){auto row=value.toMap();if(row.value("name")=="gltf-bundle/main.gltf"){
                    row={{"name","gltf-bundle/main.gltf"},{"exists",false},{"identity",QVariant()},{"bytes",0},{"sha256",""}};value=row;}}
            }
        }
        if(operation=="release"){
            lease.retiring=true;
            for(auto it=identities.begin();it!=identities.end();++it){
                const auto dir=it.key().left(it.key().lastIndexOf('/'));const auto name=it.key().mid(it.key().lastIndexOf('/')+1).toLatin1();
                Handle parent(openDirectory(root.fd,dir,lease));
                if(parent.fd<0||!Base::sameFile(parent.fd,name,it.value())||::unlinkat(parent.fd,name.constData(),0)||::fsync(parent.fd)){return {};}
            }
            auto reverseDirs=dirs;std::sort(reverseDirs.begin(),reverseDirs.end(),[](const QString&a,const QString&b){return a.size()>b.size();});
            for(const auto& dir:reverseDirs){
                const auto parentName=dir.contains('/')?dir.left(dir.lastIndexOf('/')):QString();const auto name=dir.mid(dir.lastIndexOf('/')+1).toLatin1();
                Handle parent(openDirectory(root.fd,parentName,lease));if(parent.fd<0){continue;}
                if(!Base::exists(parent.fd,name)){continue;}
                Handle child(openDirectory(root.fd,dir,lease));
                if(child.fd<0||!empty(child.fd)||!Base::sameChild(parent.fd,name,child.fd)||::unlinkat(parent.fd,name.constData(),AT_REMOVEDIR)||::fsync(parent.fd)){return {};}
            }
            if(manifestPresent&&(!Base::sameFile(root.fd,".owner.v1.json",manifestIdentity)||::unlinkat(root.fd,".owner.v1.json",0))){return {};}
            if(!empty(root.fd)||!Base::sameChild(base.fd,leaf,root.fd)||::fsync(root.fd)||::unlinkat(base.fd,leaf.constData(),AT_REMOVEDIR)||::fsync(base.fd)){return {};}
            if(Base::exists(base.fd,leaf)){return {};}
            lease.retired=true;return absent(basePath,leaf,lease);
        }
        actualDirs.clear();
        for(const auto&dir:dirs){Handle actual(openDirectory(root.fd,dir,lease));if(actual.fd>=0){actualDirs.append(QVariantMap{{"name",dir},{"identity",Base::identity(actual.fd)}});}}
        return {{"assetsFilesVersion",1},{"exists",true},{"retiring",lease.retiring},{"retired",false},
            {"directory",QUrl::fromLocalFile(basePath+'/'+QString::fromLatin1(leaf)).toString()},{"rootIdentity",Base::identity(root.fd)},
            {"directories",actualDirs},{"files",files},{"primaryRetired",lease.retirePrimaryRequested&&primaryGone}};
    }
private:
    static QStringList directories(){return {"fbx-bundle","gltf-bundle","obj-bundle","gltf-bundle/mesh","gltf-bundle/textures","obj-bundle/materials","obj-bundle/textures"};}
    static bool sameDirectory(const QVariantMap&a,const QVariantMap&b){return !a.isEmpty()&&!b.isEmpty()&&a.value("device")==b.value("device")&&a.value("inode")==b.value("inode");}
    static int openDirectory(int root,const QString&path,const Lease&lease){
        int current=::openat(root,".",O_RDONLY|O_DIRECTORY|O_CLOEXEC);if(current<0){return -1;}
        QString name;
        if(!path.isEmpty())for(const auto&part:path.split('/')){
            name+=(name.isEmpty()?QString():"/")+part;
            const auto child=part.toLatin1();int next=::openat(current,child.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
            const bool valid=Base::privateNode(next,true)&&Base::sameChild(current,child,next)&&sameDirectory(Base::identity(next),lease.directories.value(name));
            ::close(current);if(!valid){if(next>=0)::close(next);return -1;}current=next;
        }
        return current;
    }
    static bool inventory(int fd,const QString&path,const Lease&lease){
        const int copy=::openat(fd,".",O_RDONLY|O_DIRECTORY|O_CLOEXEC);if(copy<0){return false;}
        DIR* dir=::fdopendir(copy);if(!dir){::close(copy);return false;}bool valid=true;int count=0;errno=0;
        const auto dirs=directories(),files=inputs();
        while(auto entry=::readdir(dir)){
            const auto name=QString::fromLocal8Bit(entry->d_name);if(name=="."||name==".."){continue;}
            const auto full=path.isEmpty()?name:path+'/'+name;
            if(++count>8){valid=false;break;}
            if(dirs.contains(full)){
                const auto encoded=name.toLatin1();Handle child(::openat(fd,encoded.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
                if(!Base::privateNode(child.fd,true)||!sameDirectory(Base::identity(child.fd),lease.directories.value(full))||!inventory(child.fd,full,lease)){valid=false;break;}
            }else if(!files.contains(full)&&full!=".owner.v1.json"){valid=false;break;}
        }
        valid=valid&&errno==0;::closedir(dir);return valid;
    }
    static bool empty(int fd){
        const int copy=::openat(fd,".",O_RDONLY|O_DIRECTORY|O_CLOEXEC);if(copy<0){return false;}
        DIR* dir=::fdopendir(copy);if(!dir){::close(copy);return false;}bool result=true;errno=0;
        while(auto entry=::readdir(dir)){const QByteArray name(entry->d_name);if(name!="."&&name!=".."){result=false;break;}}
        result=result&&errno==0;::closedir(dir);return result;
    }
    static QVariantMap absent(const QString&base,const QByteArray&leaf,const Lease&lease){
        return {{"assetsFilesVersion",1},{"exists",false},{"retiring",lease.retiring},{"retired",lease.retired},
            {"directory",QUrl::fromLocalFile(base+'/'+QString::fromLatin1(leaf)).toString()},{"rootIdentity",QVariant()},
            {"directories",QVariantList{}},{"files",QVariantList{}},{"primaryRetired",lease.retirePrimaryRequested}};
    }
};
} // namespace overte::e2e
#endif
