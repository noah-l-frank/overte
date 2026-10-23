// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Explicit SDK/controller/selection/tree/scene endpoints. All volume, geometry,
// timers and weak lifetime facts come from the original native source join.
entityID=nativeVoxel.entityId();SelectionManager.selections=[entityID];
Entities.getEntityProperties=function(id){if(id!==entityID)throw Error('Foreign properties');return nativeVoxel.properties(id);};
Entities.worldCoordsToVoxelCoords=function(id,p){return nativeVoxel.voxelCoords(id,p);};
Entities.findRayIntersection=function(ray,mask){if(mask!==7)throw Error('Foreign pick mask');return nativeVoxel.ray(ray.origin,ray.direction);};
Entities.isVoxelDataReady=function(id){return nativeVoxel.ready(id);};
Entities.setVoxelsInCuboid=function(id,low,size,value){
    cuboidCalls.push(copy({id:id,low:low,size:size,value:value}));return nativeVoxel.setCuboid(id,low,size,value);};
Script.setInterval=function(fn,ms){var id=nativeVoxel.registerTimer(fn,ms);intervals[id]=fn;return id;};
Script.clearInterval=function(id){nativeVoxel.clearTimer(Number(id));delete intervals[id];};
Entities.getMultipleEntityProperties=function(ids){return ids.map(function(id){return Entities.getEntityProperties(id);});};
Entities.isChildOfParent=function(){throw Error('Only one isolated owned entity is admitted');};
Entities.getChildrenIDs=function(id){if(id!==entityID)throw Error('Foreign children');return [];};
Entities.deleteEntity=function(id){return nativeVoxel.remove(id);};
SelectionManager.hasSelection=function(){return this.selections.length>0;};
SelectionManager.hasUnlockedSelection=function(){return this.selections.every(function(id){return !Entities.getEntityProperties(id).locked;});};
SelectionManager.saveProperties=function(){var self=this;this.savedProperties={};this.selections.forEach(function(id){self.savedProperties[id]=Entities.getEntityProperties(id);});};
SelectionManager.clearSelections=function(){this.selections=[];};
var createApp=SelectionManager.createApp,selectionManager=SelectionManager;
var deletedCommands=[],deletedLists=[];
createApp.pushCommandForSelections=function(next,previous){deletedCommands.push(copy({next:next,previous:previous}));};
var entityListTool={deleteEntities:function(ids){deletedLists.push(copy(ids));}};
var audioFeedback={rejection:function(){throw Error('Unexpected original Delete rejection');}};
var Window={notifyEditError:function(){throw Error('Unexpected original editor error');}};
