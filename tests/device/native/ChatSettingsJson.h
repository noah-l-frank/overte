// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QBuffer>
#include <QMap>
#include <QJsonArray>
#include <QStringList>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include "SettingHelpers.h"
namespace overte::e2e {
// The actual registered writer emits one canonical Qt-indented object. Exact
// byte equality rejects duplicate keys and escaped aliases before extraction.
// Never deserialize a file-supplied @Variant payload to decide empty ownership.
inline bool chatSettingsJsonRows(const QByteArray& bytes,QMap<QByteArray,QByteArray>& rows,bool& empty) {
    QJsonParseError error;const auto document=QJsonDocument::fromJson(bytes,&error);
    if (error.error!=QJsonParseError::NoError || !document.isObject()
            || document.toJson(QJsonDocument::Indented)!=bytes) { return false; }
    const auto object=document.object();
    for (auto it=object.begin();it!=object.end();++it) {
        const auto key=it.key().toUtf8();
        if (key!="ArmoredChat-Messages" && key!="ArmoredChat-Config") {
            auto alias=QByteArray::fromPercentEncoding(key.trimmed());
            if (alias.startsWith('"') && alias.endsWith('"')) { alias=alias.mid(1,alias.size()-2); }
            while (alias.startsWith('/')) { alias.remove(0,1); }
            while (alias.endsWith('/')) { alias.chop(1); }
            if (alias=="ArmoredChat-Messages" || alias=="ArmoredChat-Config") { return false; }
            continue;
        }
        const auto prefix=QByteArray("    \"")+key+"\": ";
        const auto found=bytes.indexOf(QByteArray("\n")+prefix);const auto marker=found+1;
        if (found<0 || bytes.indexOf(QByteArray("\n")+prefix,marker+prefix.size())!=-1) { return false; }
        const auto start=marker+prefix.size();int end=start,depth=0;bool quoted=false,escaped=false;
        for (;end<bytes.size();++end) {
            const auto ch=bytes.at(end);
            if (quoted) {
                if (escaped) { escaped=false; } else if (ch=='\\') { escaped=true; } else if (ch=='"') { quoted=false; }
            } else if (ch=='"') { quoted=true; }
            else if (ch=='[' || ch=='{') { ++depth; }
            else if (ch==']' || ch=='}') { if (!depth) { return false; }--depth; }
            else if (!depth && (ch==',' || ch=='\n')) { break; }
        }
        if (quoted || depth || end==bytes.size() || end==start) { return false; }
        rows.insert(key,bytes.mid(start,end-start));
    }
    const auto history=object.value("ArmoredChat-Messages");
    empty=!object.contains("ArmoredChat-Messages") || history.isNull()
        || (history.isString() && history.toString().isEmpty()) || (history.isArray() && history.toArray().isEmpty());
    if (!empty && history.isString()) {
        // Generate only our fixed empty QStringList through the original
        // producer. No arbitrary serialized type or stream length is trusted.
        QByteArray encoded;QBuffer buffer(&encoded);
        if (!buffer.open(QIODevice::WriteOnly) || !writeJSONFile(buffer,{{"ArmoredChat-Messages",QStringList()}})) { return false; }
        empty=history==QJsonDocument::fromJson(encoded).object().value("ArmoredChat-Messages");
    }
    return true;
}
} // namespace overte::e2e
#endif
