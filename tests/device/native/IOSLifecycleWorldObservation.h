// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "NativeReadBracket.h"
#include "IOSLifecycleTouchObservation.h"
#include <QPointer>
#include <QList>
#include <QPair>

namespace overte::e2e {
class IOSLifecycleWorldObservation {
public:
    QString avatarIdentity(QObject* avatar) {
        if (!avatar || avatar->thread()!=QCoreApplication::instance()->thread()) {return {};}
        for (const auto& row:_avatars) {if (row.first==avatar) {return row.second;}}
        if (_avatars.size()>=32) {return {};}
        const auto identity=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        _avatars.append(qMakePair(QPointer<QObject>(avatar),identity));return identity;
    }
    QVariantMap read(const QString& request,const QString& run,const std::function<QVariantMap()>& reader) {
        auto result=_bracket.read("iosLifecycleWorldVersion","native-main-lifecycle-world",request,run,reader);
        if (!result.isEmpty()) {result["iosLifecycleWorldVersion"]=2;}
        return result;
    }
private:
    NativeReadBracket _bracket;
    QList<QPair<QPointer<QObject>,QString>> _avatars;
};
}
#endif
