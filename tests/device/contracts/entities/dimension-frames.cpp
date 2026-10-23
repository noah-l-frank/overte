// SPDX-License-Identifier: Apache-2.0
// Execute the complete production converters and scaled native accessors.
#include <cmath>
#include <cstdio>
#include <memory>
#include <string>
namespace glm {
struct vec3 { double x=0,y=0,z=0; };
using quat = vec3;
vec3 operator*(vec3 a,vec3 b){return {a.x*b.x,a.y*b.y,a.z*b.z};}
vec3 operator/(vec3 a,vec3 b){return {a.x/b.x,a.y/b.y,a.z/b.z};}
}
glm::vec3 parentScale;
struct EntityItem {
    glm::vec3 local;
    glm::vec3 getSNScale() const{return parentScale;}
    glm::vec3 getUnscaledDimensions() const{return local;}
    void setUnscaledDimensions(glm::vec3 v){local=v;}
    glm::vec3 getScaledDimensions() const;
    void setScaledDimensions(const glm::vec3&);
    int getParentID() const{return 1;}
    int getParentJointIndex() const{return 2;}
    glm::vec3 getWorldPosition() const{return {};}
    glm::quat getWorldOrientation() const{return {};}
    glm::vec3 getWorldVelocity() const{return {};}
    glm::vec3 getWorldAngularVelocity() const{return {};}
    glm::vec3 getAcceleration() const{return {};}
};
using EntityItemPointer=std::shared_ptr<EntityItem>;
struct EntityItemProperties {
#define PROP(T,Name,name) T _##name{}; bool _##name##Changed=false; \
 T get##Name() const{return _##name;} void set##Name(T v){_##name=v;_##name##Changed=true;} \
 bool name##Changed() const{return _##name##Changed;}
    PROP(int,ParentID,parentID)
    PROP(int,ParentJointIndex,parentJointIndex)
    PROP(glm::vec3,Position,position)
    PROP(glm::vec3,LocalPosition,localPosition)
    PROP(glm::quat,Rotation,rotation)
    PROP(glm::quat,LocalRotation,localRotation)
    PROP(glm::vec3,Velocity,velocity)
    PROP(glm::vec3,LocalVelocity,localVelocity)
    PROP(glm::vec3,AngularVelocity,angularVelocity)
    PROP(glm::vec3,LocalAngularVelocity,localAngularVelocity)
    PROP(glm::vec3,Acceleration,acceleration)
    PROP(glm::vec3,Dimensions,dimensions)
    PROP(glm::vec3,LocalDimensions,localDimensions)
#undef PROP
    void copySimulationRestrictedProperties(const EntityItemPointer&);
};
struct SpatiallyNestable {
#define IDENTITY(Name) static glm::vec3 Name(glm::vec3 v,int,int,bool,bool& ok){ok=true;return v;}
    IDENTITY(worldToLocal) IDENTITY(localToWorld)
    IDENTITY(worldToLocalRotation) IDENTITY(localToWorldRotation)
    IDENTITY(worldToLocalVelocity) IDENTITY(localToWorldVelocity)
    IDENTITY(worldToLocalAngularVelocity) IDENTITY(localToWorldAngularVelocity)
#undef IDENTITY
    static glm::vec3 worldToLocalDimensions(glm::vec3 v,int,int,bool scales,bool& ok){ok=true;return scales?v/parentScale:v;}
    static glm::vec3 localToWorldDimensions(glm::vec3 v,int,int,bool scales,bool& ok){ok=true;return scales?v*parentScale:v;}
};
#include "native-dimensions.inc"
bool same(glm::vec3 a,glm::vec3 b){return std::abs(a.x-b.x)<1e-6&&std::abs(a.y-b.y)<1e-6&&std::abs(a.z-b.z)<1e-6;}
int main(int argc,char** argv){
    if(argc!=2)return 2;
    int failures=0;const std::string mode=argv[1];
    for(auto scale:{glm::vec3{.5,.5,.5},glm::vec3{1,1,1},glm::vec3{1.004589715,1.004589715,1.004589715},glm::vec3{2,2,2},glm::vec3{.5,1.25,2}}){
        parentScale=scale;
        const glm::vec3 desired{.02,.436,.04};
        auto entity=std::make_shared<EntityItem>();
        EntityItemProperties input;input.setParentID(1);input.setParentJointIndex(2);
        if(mode=="world"||mode=="local"){
            if(mode=="world")input.setDimensions(desired);else input.setLocalDimensions(desired);
            auto native=convertPropertiesFromScriptSemantics(input,true);
            entity->setScaledDimensions(native.getDimensions());
            const auto actual=mode=="world"?entity->getScaledDimensions():entity->getUnscaledDimensions();
            if(!same(actual,desired))++failures;
        }else if(mode=="snapshot"){
            entity->setUnscaledDimensions(desired);
            input.setDimensions(entity->getScaledDimensions());input.setLocalDimensions(entity->getUnscaledDimensions());
            // COPY_ENTITY_PROPERTY_TO_PROPERTIES retains values and clears
            // changed flags for the complete native snapshot.
            input._dimensionsChanged=false;input._localDimensionsChanged=false;
            auto script=convertPropertiesToScriptSemantics(input,true);
            if(!same(script.getDimensions(),entity->getScaledDimensions())||!same(script.getLocalDimensions(),desired))++failures;
        }else if(mode=="unrelated-edit"){
            entity->setUnscaledDimensions(desired);const auto before=entity->getScaledDimensions();
            input.setPosition({.75,0,0});input.copySimulationRestrictedProperties(entity);
            auto native=convertPropertiesFromScriptSemantics(input,true);entity->setScaledDimensions(native.getDimensions());
            if(!same(entity->getScaledDimensions(),before))++failures;
        }else return 3;
        // A domain object without inherited scale is an independent control.
        input=EntityItemProperties();input.setDimensions(desired);
        if(!same(convertPropertiesFromScriptSemantics(input,false).getDimensions(),desired))++failures;
    }
    if(failures)std::fprintf(stderr,"%s: %d independent native-frame mismatches\n",argv[1],failures);
    return failures?1:0;
}
