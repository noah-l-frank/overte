// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QObject>
#include <QSharedPointer>
#include <QUuid>
#include "ChatDomainSession.h"
namespace NodeType {constexpr char AssetServer='A';}
class HostDomain {
public:
 HostDomain(){source.changed(id,true,true);}
 QUuid getUUID() const{return id;}bool isConnected()const{return connected;}
 QVariantMap featureChatSession(const QString& run){return source.snapshot(run);}
 void reconnectSameUuid(){connected=false;source.changed(id,false,true);connected=true;source.changed(id,true,true);}
 bool connected{true};QUuid id{"12345678-1234-4234-8234-123456789abc"};overte::e2e::ChatDomainSession source;
};
class HostAssetNode:public QObject {public:QUuid getUUID()const{return QUuid("22345678-1234-4234-8234-123456789abc");}};
class NodeList:public QObject {
public:
 HostDomain& getDomainHandler(){return domain;}
 QUuid getSessionUUID()const{return session;}
 QSharedPointer<HostAssetNode> soloNodeOfType(char){return server;}
 bool getThisNodeCanWriteAssets()const{return allowed;}
 bool getThisNodeCanRez()const{return true;}bool getThisNodeCanRezTmp()const{return true;}
 bool getThisNodeCanRezAvatarEntities()const{return false;}
 HostDomain domain;QUuid session{"32345678-1234-4234-8234-123456789abc"};bool allowed{true};QSharedPointer<HostAssetNode> server{new HostAssetNode};
};
