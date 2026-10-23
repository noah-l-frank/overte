// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
// Independent ATP reader, not a Model/renderer request. Original API bytes and
// actual request lifetimes only; network and physical-file delivery are seams.
#include <QUrlQuery>
#include "ResourceRequest.h"
#include "AssetResourceRequest.h"
#include "assets-resource-stat-host.h"
class ResourceRequestObserver {
public:void update(const QUrl&,qint64,const QString&){qFatal("Unselected host request observer");}
};
#include "AssetsResourceOriginals.inc"
struct AssetsResourceRead {
 QPointer<ResourceRequest> request;
 QByteArray raw;QUrl requested,relative;int result{-1},state{-1};bool cache{false},completed{false};
 explicit AssetsResourceRead(const QUrl& url):requested(url){}
 QJsonObject capture()const {
  return {{"url",requested.toString()},{"relativeUrl",relative.toString()},{"result",result},{"state",state},
   {"completed",completed},{"loadedFromCache",cache},{"bytes",raw.size()},
   {"base64",QString::fromLatin1(raw.toBase64())},{"sha256",QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex())},
   {"resourceAlive",!request.isNull()}};
 }
};
