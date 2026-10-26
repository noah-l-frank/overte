// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import <Foundation/Foundation.h>
#include <sys/stat.h>

// All ownership parameters come from the actual retained Photos journal. Only
// nonce and offset originate in ordinary UIKit fields; no expected bytes/hash.
NSDictionary* OVTPhotosOriginalChunk(NSURL* root,NSDictionary* original,NSString* nonce,NSString* offset);
BOOL OVTPhotosPersistChunk(NSURL* documents,NSDictionary* packet);
NSString* OVTPhotosFileRevision(struct stat value);
NSDictionary* OVTPhotosRetireOriginal(NSURL* root,struct stat birth,NSDictionary* original);
NSDictionary* OVTPhotosRetirementObservation(NSURL* root,struct stat birth,NSDictionary* receipt,NSString* nonce);
BOOL OVTPhotosPersistRetirement(NSURL* documents,NSDictionary* packet);
