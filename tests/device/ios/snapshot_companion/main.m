// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import <UIKit/UIKit.h>
#import "PhotosOriginal.h"
@interface OVTSnapshotCompanionDelegate : UIResponder <UIApplicationDelegate>
@property(nonatomic,strong) UIWindow* window;
@end
@implementation OVTSnapshotCompanionDelegate
- (BOOL)application:(UIApplication*)application didFinishLaunchingWithOptions:(NSDictionary*)options {
    self.window=[[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];
    self.window.rootViewController=[OVTPhotosOriginalController new];[self.window makeKeyAndVisible];return YES;
}
@end
int main(int argc,char* argv[]) {
    @autoreleasepool {return UIApplicationMain(argc,argv,nil,NSStringFromClass(OVTSnapshotCompanionDelegate.class));}
}
