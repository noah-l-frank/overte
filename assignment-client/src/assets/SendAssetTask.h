//
//  SendAssetTask.h
//  assignment-client/src/assets
//
//  Created by Ryan Huffman on 2015/08/26
//  Copyright 2015 High Fidelity, Inc.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//

#ifndef hifi_SendAssetTask_h
#define hifi_SendAssetTask_h

#include <QtCore/QByteArray>
#include <QtCore/QSharedPointer>
#include <QtCore/QString>
#include <QtCore/QRunnable>

#include "AssetUtils.h"
#include "AssetServer.h"
#include "Node.h"
#include "../../../tests/device/native/AssetBackendWork.h"

class NLPacket;

class SendAssetTask : public QRunnable {
public:
    SendAssetTask(QSharedPointer<ReceivedMessage> message, const SharedNodePointer& sendToNode, const QDir& resourcesDir);

    void run() override;

private:
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_LINUX)
    overte::e2e::asset_backend::TaskLease _featureWork;
#endif
    QSharedPointer<ReceivedMessage> _message;
    SharedNodePointer _senderNode;
    QDir _resourcesDir;
};

#endif
