// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtGlobal>
#if defined(Q_OS_UNIX) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "PrivateScriptFiles.h"
namespace overte::e2e {
// Root's exact private descriptor primitives; only nanosecond identity and
// bounded original-byte acquisition are selected from fixed Phone5527 Create.
// No requested local path or product output becomes an admitted file role.
class AssetsFilePrimitives {
    using Base=PrivateScriptFiles;
public:
    using Handle=Base::Handle;
    static QString sha(const QByteArray& bytes) {return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());}
    static bool privateNode(int fd,bool directory) {return Base::privateNode(fd,directory);}
    static bool samePath(int fd,const QByteArray& path) {return Base::samePath(fd,path);}
    static bool sameChild(int parent,const QByteArray& name,int fd) {return Base::sameChild(parent,name,fd);}
    static bool writeNew(int parent,const QByteArray& name,const QByteArray& bytes) {return Base::writeNew(parent,name,bytes);}
    static QVariantMap identity(int fd) {
        struct stat node;if(::fstat(fd,&node)) {return {};}
        return {{"device",QString::number(node.st_dev)},{"inode",QString::number(node.st_ino)},
            {"size",QString::number(node.st_size)},{"modifiedNs",QString::number(qint64(node.st_mtim.tv_sec)*1000000000LL+node.st_mtim.tv_nsec)},
            {"changedNs",QString::number(qint64(node.st_ctim.tv_sec)*1000000000LL+node.st_ctim.tv_nsec)}};
    }
    static bool exists(int parent,const QByteArray& name) {struct stat node;return ::fstatat(parent,name.constData(),&node,AT_SYMLINK_NOFOLLOW)==0;}
    static bool sameFile(int parent,const QByteArray& name,const QVariantMap& expected) {
        Handle file(::openat(parent,name.constData(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK));
        struct stat opened,current;
        return privateNode(file.fd,false) && identity(file.fd)==expected && !::fstat(file.fd,&opened)
            && !::fstatat(parent,name.constData(),&current,AT_SYMLINK_NOFOLLOW)
            && S_ISREG(current.st_mode) && opened.st_dev==current.st_dev && opened.st_ino==current.st_ino;
    }
    static bool read(int parent,const QByteArray& name,QByteArray& bytes,QVariantMap& original,int limit,bool productOutput) {
        if(productOutput) {return false;}
        Handle file(::openat(parent,name.constData(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK));
        if(!privateNode(file.fd,false)) {return false;}
        original=identity(file.fd);bool valid=false;const auto size=original.value("size").toString().toLongLong(&valid);
        if(!valid || size<=0 || size>limit) {return false;}
        bytes.clear();char buffer[4096];for(;;) {
            const auto count=::read(file.fd,buffer,sizeof(buffer));if(count<0 && errno==EINTR) {continue;}
            if(count<0 || bytes.size()+count>limit) {return false;}if(!count) {break;}bytes.append(buffer,int(count));
        }
        return bytes.size()==size && identity(file.fd)==original && privateNode(file.fd,false) && sameFile(parent,name,original);
    }
};
}
#endif
