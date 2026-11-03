// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QVariantMap>
#include <JointData.h>
#include <array>
#include <algorithm>
#include <deque>
#include <functional>
#include <map>
#include <memory>
#include <set>
#include <vector>
#include <cstring>

namespace overte::e2e {
// Passive sidecar. Every call occurs with AvatarData::_jointDataLock ALREADY
// held. Never acquire that nonrecursive lock, or a Rig lock, here. These are
// actual committed-section/assignment/history dependencies, not socket receipt
// or packet-to-pixel causality. No clocks or product poses are changed.
class JointInterpolationObservation {
    // Original maximum joints * channels * (selectable history + three current/bookend rows).
    static constexpr size_t MAX_LIVE_NODES=256*4*(45+3);
    struct Budget {size_t live{0};};
    struct Node;
    using Ref=std::shared_ptr<const Node>;
    using Roots=std::array<Ref,4>;
    struct Node {
        quint64 id;int joint,channel,depth;QString op;QVariant value;std::vector<Ref> parents;QVariantMap source,detail;
        std::shared_ptr<Budget> budget;
        Node(quint64 sequence,int j,int c,int d,const QString& operation,const QVariant& v,const std::vector<Ref>& p,
                const QVariantMap& s,const QVariantMap& extra,const std::shared_ptr<Budget>& b):
            id(sequence),joint(j),channel(c),depth(d),op(operation),value(v),parents(p),source(s),detail(extra),budget(b) {++budget->live;}
        ~Node() {--budget->live;}
    };
    struct Entry {size_t index;quint64 time;Roots roots;};
public:
    static bool enabled() {
#if defined(ANDROID_APP_PICO_INTERFACE)
        return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript");
#else
        return false;
#endif
    }
    // Copy active float32 object representations, including nonfinite inputs.
    // JointData explicitly declares inactive storage invalid: never read it.
    static QString bits(const float& value) {
        static_assert(sizeof(float)==sizeof(quint32),"The observation requires float32");
        quint32 raw;std::memcpy(&raw,&value,sizeof(raw));return QString::number(raw,16).rightJustified(8,'0');
    }
    static QVariantList channels(const JointData& value,bool rotationKnown=true,bool translationKnown=true) {
        return {(value.rotationIsDefaultPose || !rotationKnown) ? QVariant() : QVariant(QVariantList{bits(value.rotation.x),bits(value.rotation.y),bits(value.rotation.z),bits(value.rotation.w)}),
            (value.translationIsDefaultPose || !translationKnown) ? QVariant() : QVariant(QVariantList{bits(value.translation.x),bits(value.translation.y),bits(value.translation.z)}),
            value.rotationIsDefaultPose,value.translationIsDefaultPose};
    }
    void openAssignments() {
        if(!enabled() || _failed) {return;}
        if(_assignmentOpen) {fail("uncommitted-assignments");return;}_assignmentOpen=true;
    }
    void prepare(const QVector<JointData>& values,bool assignment=false) {
        if(!enabled() || _failed) {return;}
        if(_assignmentOpen!=assignment) {fail("uncommitted-assignments");return;}
        if(values.size()>256) {fail("joint-quota");return;}
        _current.resize(values.size());
        for(int i=0;i<values.size();++i) {
            const auto observed=channels(values[i],known(_current[i][0]),known(_current[i][1]));
            for(int c=0;c<4;++c) {
                if(!_current[i][c]) {_current[i][c]=node(i,c,"initial",observed[c],{}, {},{});}
                else if(!(c<2 && observed[c+2].toBool()) && _current[i][c]->value!=observed[c]) {fail("unobserved-assignment");return;}
            }
        }
    }
    void assigned(const QVector<JointData>& values,const unsigned char* rotations,const unsigned char* translations,
            const QVariantMap& source,bool defaults,bool completed) {
        if(!enabled() || _failed) {return;}
        if(!_assignmentOpen || !completed || source.isEmpty() || values.size()!=static_cast<int>(_current.size())
                || source.value("jointCount").toInt()!=values.size() || source.value("kind").toString()!=(defaults ? "default-flags":"joint-data")
                || source.value("sequence").toULongLong()<=_lastCommit) {fail("missing-fresh-commit");return;}
        for(int i=0;i<values.size();++i) {
            const bool r=rotations[i/8]&(1<<(i%8)),t=translations[i/8]&(1<<(i%8));
            const auto observed=channels(values[i],(!defaults && r) || known(_current[i][0]),(!defaults && t) || known(_current[i][1]));
            for(int c=0;c<4;++c) {
                const bool written=defaults ? c>=2 : ((c==0 || c==2) ? r:t);
                if(written) {_current[i][c]=node(i,c,"wire",observed[c],{},source,{});}
                else if(defaults && c<2 && _current[i][c+2] && _current[i][c+2]->value.toBool() && !observed[c+2].toBool()) {
                    // A flag-only reveal does not supply the previously invalid
                    // component. Retain actual active bits, but no wire origin.
                    _current[i][c]=node(i,c,"unobserved",observed[c],{_current[i][c]}, {},{{"reason","inactive-storage-reveal"}});
                }
                else if(!_current[i][c] || (!(c<2 && observed[c+2].toBool()) && _current[i][c]->value!=observed[c])) {fail("unobserved-partial-assignment");return;}
            }
        }
        _lastCommit=source.value("sequence").toULongLong();_assignmentOpen=false;
    }
    void resetHistory(size_t count) {
        if(!enabled() || _failed) {return;}
        if(count!=_current.size()) {fail("history-reset-count");return;}
        _history.clear();_history.resize(count);++_resets;
    }
    void append(size_t joint,size_t index,quint64 time,const JointData& actual) {
        if(!enabled() || _failed) {return;}
        if(joint>=_history.size() || !matches(joint,actual)) {fail("history-append-input");return;}
        auto& tail=_history[joint];
        if((tail.empty() && index!=0) || (!tail.empty() && (index!=tail.back().index+1 || time<tail.back().time))) {
            fail("history-append-order");return;
        }
        tail.push_back({index,time,_current[joint]});if(tail.size()>45) {tail.pop_front();}++_appends;
    }
    void prune(size_t joint,size_t oldSize) {
        if(!enabled() || _failed) {return;}
        if(joint>=_history.size() || oldSize<=2000 || _history[joint].size()!=45
                || _history[joint].back().index+1!=oldSize) {fail("history-prune");return;}
        for(auto& entry:_history[joint]) {entry.index-=oldSize-45;}++_prunes;
    }
    void begin(const QVector<JointData>& values,quint64 now,bool direct) {
        if(!enabled()) {return;}prepare(values);_selection.clear();_selected.clear();_captureUnavailable.clear();_now=now;_direct=direct;
        if(direct && !_failed) {
            for(size_t i=0;i<_current.size();++i) {
                _selection.append(QVariantMap{{"joint",static_cast<int>(i)},{"mode","direct-size-mismatch"},{"output",ids(_current[i])}});
                retain(_current[i]);
            }
        }
    }
    void empty(size_t joint) {
        if(!enabled() || _failed) {return;}
        if(joint>=_current.size()) {fail("empty-joint");return;}
        _selection.append(QVariantMap{{"joint",static_cast<int>(joint)},{"mode","empty-history-hold"},{"output",ids(_current[joint])}});
        retain(_current[joint]);
    }
    void selected(size_t joint,size_t size,size_t start,size_t oldIndex,size_t newIndex,
            const std::pair<quint64,JointData>& oldFrame,const std::pair<quint64,JointData>& newFrame,
            quint64 latency,quint64 point,float theta,const JointData& actual) {
        if(!enabled() || _failed) {return;}
        const auto* old=find(joint,oldIndex,oldFrame);const auto* newer=find(joint,newIndex,newFrame);
        if(!old || !newer || joint>=_current.size() || _direct) {fail("unretained-keyframe");return;}
        const auto previous=_current[joint];const auto values=channels(actual,known(previous[0]),known(previous[1]));
        for(int c=0;c<2;++c) {
            if(!values[c+2].toBool() && ((c==0 && (oldFrame.second.rotationIsDefaultPose || newFrame.second.rotationIsDefaultPose))
                    || (c==1 && (oldFrame.second.translationIsDefaultPose || newFrame.second.translationIsDefaultPose)))) {
                _captureUnavailable="inactive-keyframe-input";
            }
            // The Rig ignores invalid/default component storage. Do not read
            // it, or grow a fictitious arithmetic ancestry for a null value.
            // The actual selected history/weight remains in the separate row.
            _current[joint][c]=values[c+2].toBool() ? node(joint,c,"inactive",QVariant(),{}, {},{})
                : node(joint,c,"interpolate",values[c],{old->roots[c],newer->roots[c]}, {},{{"thetaBits",bits(theta)}});
        }
        for(int c=2;c<4;++c) {if(!previous[c] || previous[c]->value!=values[c]) {fail("interpolation-changed-flags");return;}}
        const QString mode=oldIndex!=newIndex ? "interpolated" : point<oldFrame.first ? "oldest-future-hold":"newest-clamp";
        _selection.append(QVariantMap{{"joint",static_cast<int>(joint)},{"mode",mode},{"historySize",static_cast<qulonglong>(size)},
            {"historyStart",static_cast<qulonglong>(start)},{"oldIndex",static_cast<qulonglong>(oldIndex)},
            {"newIndex",static_cast<qulonglong>(newIndex)},{"oldTimeUs",static_cast<qulonglong>(oldFrame.first)},
            {"newTimeUs",static_cast<qulonglong>(newFrame.first)},{"latencyUs",static_cast<qulonglong>(latency)},
            {"timePointUs",static_cast<qulonglong>(point)},{"thetaBits",bits(theta)},
            {"old",ids(old->roots)},{"new",ids(newer->roots)},{"output",ids(_current[joint])}});
        retain(old->roots);retain(newer->roots);retain(_current[joint]);
    }
    QVariantMap snapshot(const QVector<JointData>& values) {
        if(!enabled()) {return {};}prepare(values);
        QVariantList roots,nodes,sections;std::set<quint64> visited;std::map<quint64,QVariantMap> sources;size_t rawBytes=0;
        std::function<void(const Ref&)> visit=[&](const Ref& ref) {
            if(_failed || !ref) {fail("missing-node");return;}if(visited.count(ref->id)) {return;}
            if(visited.size()>=1024 || ref->depth>256) {fail("lineage-quota");return;}
            visited.insert(ref->id);for(const auto& parent:ref->parents) {visit(parent);}
            if(ref->op=="unobserved" || (ref->op=="interpolate" && !ref->value.isNull()
                    && std::any_of(ref->parents.begin(),ref->parents.end(),[](const Ref& parent) {return parent->value.isNull();}))) {
                _captureUnavailable="unobserved-contributing-input";
            }
            QVariantList parents;for(const auto& parent:ref->parents) {parents.append(static_cast<qulonglong>(parent->id));}
            QVariant source;
            if(!ref->source.isEmpty()) {
                auto sequence=ref->source.value("sequence").toULongLong();source=static_cast<qulonglong>(sequence);
                const auto found=sources.find(sequence);
                if(found!=sources.end() && found->second!=ref->source) {fail("changed-original-section");return;}
                if(found==sources.end()) {sources[sequence]=ref->source;rawBytes+=ref->source.value("bytes").toUInt();}
                if(rawBytes>65536) {fail("section-quota");return;}
            }
            nodes.append(QVariantMap{{"id",static_cast<qulonglong>(ref->id)},{"joint",ref->joint},{"channel",ref->channel},
                {"op",ref->op},{"value",ref->value},{"parents",parents},{"source",source},{"detail",ref->detail}});
        };
        for(const auto& joint:_current) {roots.append(QVariant(ids(joint)));for(const auto& ref:joint) {visit(ref);}}
        for(const auto& ref:_selected) {visit(ref);}for(const auto& item:sources) {sections.append(item.second);}
        if(_selection.size()!=values.size()) {fail("selection-count");}
        if(!_failed && !activeInputsObserved()) {_captureUnavailable="unobserved-active-input";}
        return {{"jointInterpolationVersion",1},{"available",!_failed && !_assignmentOpen && _captureUnavailable.isEmpty()},
            {"assignmentPending",_assignmentOpen},
            {"failure",_failed ? _failure:_captureUnavailable},
            {"nowUs",static_cast<qulonglong>(_now)},{"historyResets",static_cast<qulonglong>(_resets)},
            {"historyAppends",static_cast<qulonglong>(_appends)},{"historyPrunes",static_cast<qulonglong>(_prunes)},
            {"roots",roots},{"selection",_selection},{"nodes",nodes},{"sections",sections}};
    }
    bool activeInputsObserved() const {
        if(!enabled() || _failed || _assignmentOpen) {return false;}
        for(const auto& row:_current) {for(int c=0;c<2;++c) {
            if(!row[c+2] || (!row[c+2]->value.toBool() && !known(row[c]))) {return false;}
        }}return true;
    }
private:
    static bool known(const Ref& ref) {return ref && !ref->value.isNull();}
    void fail(const QString& reason) {if(!_failed) {_failure=reason;}_failed=true;}
    Ref node(int joint,int channel,const QString& op,const QVariant& value,const std::vector<Ref>& parents,
            const QVariantMap& source,const QVariantMap& detail) {
        int depth=1;for(const auto& parent:parents) {if(!parent) {fail("missing-parent");return {};}
            depth=std::max(depth,parent->depth+1);}
        if(_failed || depth>256 || _sequence>=9007199254740991ULL) {fail("node-quota");return {};}
        // Allocate only after actual Pico admission, never per Phone Avatar.
        if(!_budget) {_budget=std::make_shared<Budget>();}
        if(_budget->live>=MAX_LIVE_NODES) {fail("node-quota");return {};}
        return std::make_shared<Node>(++_sequence,joint,channel,depth,op,value,parents,source,detail,_budget);
    }
    static QVariantList ids(const Roots& roots) {QVariantList out;for(const auto& ref:roots) {out.append(static_cast<qulonglong>(ref?ref->id:0));}return out;}
    bool matches(size_t joint,const JointData& actual) const {
        if(joint>=_current.size()) {return false;}const auto values=channels(actual,known(_current[joint][0]),known(_current[joint][1]));
        for(int c=0;c<4;++c) {if(!_current[joint][c] || (!(c<2 && values[c+2].toBool()) && _current[joint][c]->value!=values[c])) {return false;}}return true;
    }
    const Entry* find(size_t joint,size_t index,const std::pair<quint64,JointData>& actual) const {
        if(joint>=_history.size()) {return nullptr;}
        for(const auto& entry:_history[joint]) {if(entry.index==index && entry.time==actual.first) {
            const auto values=channels(actual.second,known(entry.roots[0]),known(entry.roots[1]));
            for(int c=0;c<4;++c) {if(!entry.roots[c] || (!(c<2 && values[c+2].toBool()) && entry.roots[c]->value!=values[c])) {return nullptr;}}return &entry;
        }}return nullptr;
    }
    void retain(const Roots& roots) {for(const auto& ref:roots) {_selected.push_back(ref);}}
    bool _failed{false},_direct{false},_assignmentOpen{false};QString _failure,_captureUnavailable;quint64 _sequence{0},_lastCommit{0},_now{0},_resets{0},_appends{0},_prunes{0};
    std::shared_ptr<Budget> _budget;
    std::vector<Roots> _current;std::vector<std::deque<Entry>> _history;std::vector<Ref> _selected;QVariantList _selection;
};
}
#endif
