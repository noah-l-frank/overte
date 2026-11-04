// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE) && defined(Q_OS_LINUX)
#include <QJsonArray>
#include <QJsonDocument>
#include <QMetaType>
#include <QVariantMap>

namespace overte::e2e {
// NEW, uncompiled. Conservative pretty-byte admission BEFORE constructing a
// complete QJsonDocument/string. No source is shortened or normalized: after
// this succeeds, the ORIGINAL QJsonDocument::toJson() still emits the literal.
// A rejected already-returned QVariant remains strongly held by its caller;
// it is uncertain/unavailable, never a within-budget complete observation.
class PicoEmoteSourceJsonBudget {
public:
    explicit PicoEmoteSourceJsonBudget(qsizetype maximum):_maximum(maximum) {}
    bool fits(const QVariant& actual) {return _maximum>0 && visit(actual,0);}
private:
    bool add(qsizetype bytes) {
        if (bytes<0 || bytes>_maximum-_used) {return false;}
        _used+=bytes;return true;
    }
    bool text(const QString& value) {
        if (!add(2)) {return false;}
        for (const auto c:value) {
            const auto code=c.unicode();
            // UTF16 non-ASCII (including surrogate pairs) can cost at most
            // six JSON bytes/code-unit. ASCII escapes are bounded exactly.
            const qsizetype bytes=(code<0x20) ? 6 : (code=='"' || code=='\\') ? 2 : code<0x80 ? 1 : 6;
            if (!add(bytes)) {return false;}
        }
        return true;
    }
    bool visit(const QVariant& value,int depth) {
        if (depth>64 || !add(16+8*depth)) {return false;}
        if (!value.isValid() || value.isNull()) {return add(4);}
        const auto type=value.userType();
        if (type==QMetaType::Bool) {return add(5);}
        if (type==QMetaType::QString) {return text(value.toString());}
        if (type==QMetaType::QVariantMap) {
            const auto map=value.toMap();
            for (auto it=map.cbegin();it!=map.cend();++it) {
                if (!text(it.key()) || !visit(it.value(),depth+1)) {return false;}
            }
            return true;
        }
        if (type==QMetaType::QVariantList || type==QMetaType::QStringList) {
            const auto list=value.toList();for (const auto& child:list) {if (!visit(child,depth+1)) {return false;}}
            return true;
        }
        if (type==QMetaType::Int || type==QMetaType::UInt || type==QMetaType::LongLong
                || type==QMetaType::ULongLong || type==QMetaType::Double || type==QMetaType::Float) {
            // Only one primitive scalar is encoded here, never a whole DTO.
            // Even an exact finite binary64 decimal expansion is <4096 bytes. This
            // bounded temporary uses the SAME Qt numeric serialization.
            const auto token=QJsonDocument(QJsonArray{QJsonValue::fromVariant(value)}).toJson(QJsonDocument::Compact);
            return token.size()>=2 && token.size()<=4096 && add(token.size()-2);
        }
        return false; // QObject/custom/converting types cannot bypass bounds.
    }
    const qsizetype _maximum;qsizetype _used{0};
};
}
#endif
