// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "WebRuntimeBridge.h"
#include <QPointF>
#include <QQuickItem>
#include <cmath>
#include <optional>
namespace overte::e2e {
struct PicoBrowserInputProvider {
    std::function<bool(QQuickItem*,const QPointF&,qint64)> pointer;
    std::function<bool(QQuickItem*,const QString&,qint64)> text;
};
inline const char* picoBrowserInputProperty() { return "_overteE2EPicoBrowserInputProviderV1"; }
// Closed original geometry -> local item coordinates. The producer supplies the
// original native document and its clock; host commands cannot supply geometry.
inline std::optional<QPointF> picoBrowserPoint(const QVariantMap& packet,const QString& request,
        const QString& run,const QString& document,const QString& control,qint64 now,const QSizeF& size) {
    const auto exact=[](const QVariantMap& map,const QSet<QString>& expected) {
        const auto keys=map.keys();return QSet<QString>(keys.begin(),keys.end())==expected;
    };
    const auto number=[](const QVariant& value,double low,double high) {
        const auto type=value.userType();
        return (type==QMetaType::Double || type==QMetaType::Int || type==QMetaType::LongLong
                || type==QMetaType::UInt || type==QMetaType::ULongLong)
            && std::isfinite(value.toDouble()) && value.toDouble()>=low && value.toDouble()<=high;
    };
    const auto view=packet.value("viewport").toMap(),rect=packet.value("rect").toMap(),center=packet.value("center").toMap(),
        doc=packet.value("document").toMap(),editor=packet.value("editor").toMap();
    const bool editable=control=="text" || control=="foreign";
    if (!exact(packet,{"webGeometryVersion","requestId","instance","sequence","capturedEpochMs","document","control","editor","viewport","rect","center","hit","enabled","connected"})
            || QJsonObject::fromVariantMap(packet).value("webGeometryVersion")!=QJsonValue(1)
            || packet.value("requestId")!=request || packet.value("control")!=control
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(packet.value("instance").toString()).hasMatch()
            || !number(packet.value("sequence"),1,9007199254740991.0)
            || std::floor(packet.value("sequence").toDouble())!=packet.value("sequence").toDouble()
            || !number(packet.value("capturedEpochMs"),1,9007199254740991.0)
            || std::floor(packet.value("capturedEpochMs").toDouble())!=packet.value("capturedEpochMs").toDouble()
            || now<packet.value("capturedEpochMs").toLongLong() || now-packet.value("capturedEpochMs").toLongLong()>1500
            || !exact(doc,{"runId","href","responseId","readyState"}) || doc.value("runId")!=run
            || doc.value("href")!=document || doc.value("readyState")!="complete"
            || (!doc.value("responseId").isNull() && !QRegularExpression("\\A[0-9a-f]{32}\\z").match(doc.value("responseId").toString()).hasMatch())
            || !exact(editor,{"focused","text","cursor","anchor"}) || editor.value("focused").userType()!=QMetaType::Bool
            || (editable ? editor.value("text").userType()!=QMetaType::QString || editor.value("text").toString().size()>512
                         : !editor.value("text").isNull())
            || (editable ? !number(editor.value("cursor"),0,editor.value("text").toString().size())
                           || !number(editor.value("anchor"),0,editor.value("text").toString().size())
                           || std::floor(editor.value("cursor").toDouble())!=editor.value("cursor").toDouble()
                           || std::floor(editor.value("anchor").toDouble())!=editor.value("anchor").toDouble()
                         : !editor.value("cursor").isNull() || !editor.value("anchor").isNull())
            || !exact(view,{"width","height","scale","offsetLeft","offsetTop"})
            || !number(view.value("width"),1,32768) || !number(view.value("height"),1,32768)
            || !number(view.value("scale"),1,1) || !number(view.value("offsetLeft"),0,0) || !number(view.value("offsetTop"),0,0)
            || !exact(rect,{"x","y","width","height"}) || !exact(center,{"x","y"})
            || !number(rect.value("x"),-1e7,1e7) || !number(rect.value("y"),-1e7,1e7)
            || !number(rect.value("width"),0.001,1e7) || !number(rect.value("height"),0.001,1e7)
            || !number(center.value("x"),0,view.value("width").toDouble())
            || !number(center.value("y"),0,view.value("height").toDouble())
            || !std::isfinite(size.width()) || !std::isfinite(size.height()) || size.width()<=0 || size.height()<=0) { return {}; }
    for (const auto& key:QStringList{"hit","enabled","connected"}) {
        if (packet.value(key).userType()!=QMetaType::Bool || !packet.value(key).toBool()) { return {}; }
    }
    const auto x=center.value("x").toDouble(),y=center.value("y").toDouble();
    if (x>=view.value("width").toDouble() || y>=view.value("height").toDouble()
            || std::abs(x-rect.value("x").toDouble()-rect.value("width").toDouble()/2)>0.001
            || std::abs(y-rect.value("y").toDouble()-rect.value("height").toDouble()/2)>0.001) { return {}; }
    return QPointF(x/view.value("width").toDouble()*size.width(),y/view.value("height").toDouble()*size.height());
}
} // namespace overte::e2e
Q_DECLARE_METATYPE(overte::e2e::PicoBrowserInputProvider)
#endif
