// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QHash>
#include <QUuid>
#include <QVariant>
#include <v8.h>
namespace overte::e2e {
// Engine-local metadata only, without retained JS roots. Called only on its
// real current isolate. No evaluation, function names, arguments or raw text.
class IOSV8ScriptStack final {
public:
    static bool enabled() noexcept {
        try {if(!QCoreApplication::instance()){return false;}const auto args=QCoreApplication::arguments();
            const auto a=args.indexOf("--testScript"),b=args.indexOf("--testResultsLocation");
            return a>=0 && a+1<args.size() && !args[a+1].isEmpty() && b>=0 && b+1<args.size() && !args[b+1].isEmpty();
        }catch(...){return false;}
    }
    QVariantMap snapshot(v8::Isolate* isolate) noexcept {
        try {
            QVariantMap result{{"emitStackVersion",1},{"instance",_instance},{"complete",false},{"frames",QVariantList{}}};
            if(!isolate || !isolate->IsCurrent()){return result;}
            v8::HandleScope handles(isolate);const auto trace=v8::StackTrace::CurrentStackTrace(isolate,33,
                static_cast<v8::StackTrace::StackTraceOptions>(v8::StackTrace::kDetailed|v8::StackTrace::kScriptId));
            const auto size=trace->GetFrameCount();bool complete=_complete && size>0 && size<=32;QVariantList frames;
            for(int i=0;i<qMin(size,32);++i){
                const auto frame=trace->GetFrame(isolate,i);const auto name=frame->GetScriptNameOrSourceURL();
                const auto originalName=frame->GetScriptName();const auto source=frame->GetScriptSource();
                if(name.IsEmpty() || name->Length()>4096){complete=false;break;}
                const v8::String::Utf8Value utf8(isolate,name);if(!*utf8){complete=false;break;}
                const auto urlSha256=hash(QByteArray(*utf8,utf8.length()));const auto scriptId=frame->GetScriptId();
                QVariantMap actualCode;
                if(!source.IsEmpty() && source->Length()<=4194304 && !originalName.IsEmpty() && originalName->Length()<=4096){
                    const v8::String::Value units(isolate,source);const v8::String::Utf8Value originalUrl(isolate,originalName);
                    if((*units || !units.length()) && *originalUrl){
                        QByteArray bytes;bytes.reserve(units.length()*2);
                        for(int j=0;j<units.length();++j){const auto unit=(*units)[j];bytes.append(static_cast<char>(unit&255));bytes.append(static_cast<char>(unit>>8));}
                        actualCode={{"urlSha256",hash(QByteArray(*originalUrl,originalUrl.length()))},{"encoding","utf-16le-code-units"},
                            {"codeUnits",units.length()},{"sha256",hash(bytes)},{"firstObservedEpochMs",QDateTime::currentMSecsSinceEpoch()}};
                        // Actual first source observation, never compile time.
                        if(_scripts.contains(scriptId)){
                            const auto first=_scripts.value(scriptId);auto original=first;auto candidate=actualCode;
                            original.remove("firstObservedEpochMs");candidate.remove("firstObservedEpochMs");
                            if(original!=candidate){_complete=false;}actualCode["firstObservedEpochMs"]=first.value("firstObservedEpochMs");
                        }else if(scriptId>0 && _scripts.size()<1024){_scripts.insert(scriptId,actualCode);}
                        else {_complete=false;}
                    }
                }
                if(actualCode.isEmpty() || actualCode.value("urlSha256")!=urlSha256 || scriptId<=0
                        || frame->GetLineNumber()<=0 || frame->GetColumn()<=0){complete=false;}
                frames.append(QVariantMap{{"scriptId",scriptId},{"line",frame->GetLineNumber()},{"column",frame->GetColumn()},
                    {"sourceUrlSha256",urlSha256},{"compiled",actualCode.isEmpty()?QVariant():QVariant(actualCode)},
                    {"isEval",frame->IsEval()},{"isConstructor",frame->IsConstructor()}});
            }
            result["frames"]=frames;result["complete"]=complete && _complete;return result;
        }catch(...){_complete=false;return {};}
    }
private:
    static QString hash(const QByteArray& bytes){return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());}
    const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    QHash<int,QVariantMap> _scripts;bool _complete{true};
};
} // namespace overte::e2e
#endif
