// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import <UIKit/UIKit.h>
#import <CommonCrypto/CommonDigest.h>
#import "ShareJournal.h"
#include <sys/stat.h>

@interface OVTShareArchive : UIViewController
@property(nonatomic,strong) UITextField* runField;
@property(nonatomic,strong) UILabel* status;
@end
@implementation OVTShareArchive
- (void)viewDidLoad {
    [super viewDidLoad];self.view.backgroundColor=UIColor.systemBackgroundColor;
    UIStackView* stack=[UIStackView new];stack.axis=UILayoutConstraintAxisVertical;stack.spacing=16;stack.translatesAutoresizingMaskIntoConstraints=NO;
    [self.view addSubview:stack];[NSLayoutConstraint activateConstraints:@[
        [stack.leadingAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.leadingAnchor constant:20],
        [stack.trailingAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.trailingAnchor constant:-20],
        [stack.topAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.topAnchor constant:20]]];
    self.runField=[UITextField new];self.runField.borderStyle=UITextBorderStyleRoundedRect;self.runField.placeholder=@"Completed Share run identifier";
    self.runField.autocorrectionType=UITextAutocorrectionTypeNo;self.runField.autocapitalizationType=UITextAutocapitalizationTypeNone;
    self.runField.accessibilityIdentifier=@"snapshot.share.archive.run";[stack addArrangedSubview:self.runField];
    UIButton* button=[UIButton buttonWithType:UIButtonTypeSystem];[button setTitle:@"Import unchanged Share original" forState:UIControlStateNormal];
    button.accessibilityIdentifier=@"snapshot.share.archive.import";[button addTarget:self action:@selector(importOriginal) forControlEvents:UIControlEventTouchUpInside];[stack addArrangedSubview:button];
    self.status=[UILabel new];self.status.numberOfLines=0;self.status.accessibilityIdentifier=@"snapshot.share.archive.status";
    self.status.text=@"No original imported";[stack addArrangedSubview:self.status];
}
- (void)importOriginal {
    NSString* run=self.runField.text;NSURL* group=OVTShareGroup();
    if (!group || !OVTShareMatch(run,@"\\A[0-9a-f]{32}\\z")) {self.status.text=@"Invalid original identity";return;}
    NSURL* original=[group URLByAppendingPathComponent:[@"snapshot-share-" stringByAppendingString:run] isDirectory:YES];
    NSData* metadata=OVTShareReadMetadata([original URLByAppendingPathComponent:@"share-original.json"]);
    id record=metadata?[NSJSONSerialization JSONObjectWithData:metadata options:0 error:nil]:nil;
    if (![record isKindOfClass:NSDictionary.class] || ![record[@"runId"] isEqual:run] || ![record[@"phase"] isEqual:@"complete"]
            || ![record[@"artifact"] isEqual:@"original.bytes"]) {self.status.text=@"No completed original";return;}
    BOOL finished=NO;for (NSDictionary* event in record[@"events"]) {if ([event[@"kind"] isEqual:@"finish-issued"]) {finished=YES;}}
    if (!finished) {self.status.text=@"Finish the actual Share receiver first";return;}
    NSURL* documents=[NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask].firstObject;
    NSURL* output=[documents URLByAppendingPathComponent:[@"snapshot-share-" stringByAppendingString:run] isDirectory:YES];
    if (mkdir(output.fileSystemRepresentation,0700)!=0) {self.status.text=@"Existing responsibility; import will not repeat";return;}
    NSDictionary* before=OVTShareClock();
    NSDictionary* intent=@{@"iosSnapshotShareImportVersion":@1,@"runId":run,@"phase":@"issued",@"clockBefore":before,
        @"instance":OVTShareID(),@"processId":@(NSProcessInfo.processInfo.processIdentifier),@"bundleId":NSBundle.mainBundle.bundleIdentifier,
        @"clockDomain":@"native-share-archive"};
    if (!OVTShareWrite(output,@"import-intent.json",[NSJSONSerialization dataWithJSONObject:intent options:0 error:nil])) {self.status.text=@"Import intent failed";return;}
    NSString* hash=nil;NSUInteger count=0;
    BOOL copied=OVTShareCopyFile([original URLByAppendingPathComponent:@"original.bytes"],[output URLByAppendingPathComponent:@"original.bytes"],&hash,&count);
    NSData* after=OVTShareReadMetadata([original URLByAppendingPathComponent:@"share-original.json"]);
    if (!copied || ![metadata isEqualToData:after] || ![record[@"sha256"] isEqual:hash] || ![record[@"byteCount"] isEqual:@(count)]
            || !OVTShareWrite(output,@"original-extension.json",metadata)) {self.status.text=@"Original changed or failed; responsibility retained";return;}
    unsigned char raw[CC_SHA256_DIGEST_LENGTH];CC_SHA256(metadata.bytes,(CC_LONG)metadata.length,raw);NSMutableString* metadataHash=[NSMutableString new];
    for (NSUInteger index=0;index<sizeof(raw);++index) {[metadataHash appendFormat:@"%02x",raw[index]];}
    NSMutableDictionary* completed=[intent mutableCopy];completed[@"phase"]=@"complete";completed[@"clockAfter"]=OVTShareClock();
    completed[@"originalMetadataSha256"]=metadataHash;completed[@"byteCount"]=@(count);completed[@"sha256"]=hash;
    BOOL saved=OVTShareWrite(output,@"import-original.json",[NSJSONSerialization dataWithJSONObject:completed options:0 error:nil]);
    self.status.text=saved?@"Original bytes and unchanged extension ledger exposed in Documents":@"Import result failed; responsibility retained";
}
@end
@interface OVTShareArchiveDelegate : UIResponder <UIApplicationDelegate>
@property(nonatomic,strong) UIWindow* window;
@end
@implementation OVTShareArchiveDelegate
- (BOOL)application:(UIApplication*)application didFinishLaunchingWithOptions:(NSDictionary*)options {
    self.window=[[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];self.window.rootViewController=[OVTShareArchive new];
    [self.window makeKeyAndVisible];return YES;
}
@end
int main(int argc,char* argv[]) {@autoreleasepool {return UIApplicationMain(argc,argv,nil,NSStringFromClass(OVTShareArchiveDelegate.class));}}
