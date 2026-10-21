#!/usr/bin/env python3
"""Security and reproducibility contracts for shared repository workflows."""

import fnmatch
import ast
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap
import tempfile
import unittest
import zlib
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/project-tests.yml"
BUILD_WORKFLOW = ROOT / ".github/workflows/pico4-build.yml"
RELEASE_WORKFLOW = ROOT / ".github/workflows/pico4-release-candidate.yml"
RELEASE_BUNDLE_WORKFLOW = ROOT / ".github/workflows/release-bundle-attest-draft.yml"
DEVICE_WORKFLOW = ROOT / ".github/workflows/pico4-device-acceptance.yml"
ANDROID_TESTS_WORKFLOW = ROOT / ".github/workflows/android-tests.yml"
DOCUMENTATION_WORKFLOW = ROOT / ".github/workflows/documentation-checks.yml"
BRANCH_POLICY_WORKFLOW = ROOT / ".github/workflows/branch-policy.yml"
BRANCH_SYNC_WORKFLOW = ROOT / ".github/workflows/branch-sync.yml"
PARENT_QUALIFICATION_WORKFLOW = ROOT / ".github/workflows/parent-qualification.yml"
SYNC_REUSE_WORKFLOW = ROOT / ".github/workflows/sync-test-reuse.yml"
SYNC_VALIDATION_WORKFLOW = ROOT / ".github/workflows/sync-validation.yml"
WORKFLOW_DIRECTORY = ROOT / ".github/workflows"
CODEQL_WORKFLOW = ROOT / ".github/workflows/codeql.yml"
IOS_WORKFLOW = ROOT / ".github/workflows/ios-bootstrap.yml"
MACOS_WORKFLOW = ROOT / ".github/workflows/macos-bootstrap.yml"
RULESETS = ROOT / ".github/rulesets"
RULESET_FILES = {
    "Android target branch topology": "android-target-branches.json",
    "Apple target branch topology": "apple-target-branches.json",
    "Immutable Android, canonical, and archive tags": "android-release-tags.json",
    "Immutable Pico 4 release and dependency tags": "pico4-release-tags.json",
    "Permanent branch governance": "permanent-branches.json",
}
STAGED_RULESET_FILES = {
    "Selected CodeQL security results on main": ROOT / "tools/repository-checks/workflows/codeql-main.json",
}
ACTION_USE = re.compile(r"^\s*uses:\s*([^\s#]+)", re.MULTILINE)
FULL_SHA_ACTION = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
PROTECTED_GENERATIONS = (
    'protected-shared-producer-v1', 'protected-producer-postmerge-original-e-v1',
    'protected-producer-ci37-v1', 'protected-producer-metadata-ci-v1',
    'protected-producer-seven-target-ci-v1', 'protected-producer-original-default-v1',
    'protected-producer-original-default-boolean-v1',
    'protected-producer-original-default-required-context-v1',
    'protected-producer-optional-parent-source-v1',
    'protected-producer-optional-leaf-common-v1',
    'protected-producer-exact-parent-command-owners-v1',
)
METADATA_PRODUCER_GENERATIONS = PROTECTED_GENERATIONS[3:]
ORIGINAL_DEFAULT_GENERATIONS = (
    'protected-producer-original-default-v1', 'protected-producer-original-default-boolean-v1',
    'protected-producer-original-default-required-context-v1',
    'protected-producer-optional-parent-source-v1',
    'protected-producer-optional-leaf-common-v1',
    'protected-producer-exact-parent-command-owners-v1',
)
SELECTED_SYNC_GENERATIONS = (
    'npm-consumers-sync-ci-v1', 'npm-consumers-sync-ci-budget-v1', 'npm-consumers-sync-ci-budget-cleanup-v1', 'npm-consumers-metadata-edits-v1',
    'android-owned-npm5-sync-ci-v1', *PROTECTED_GENERATIONS,
)

# Exact historical metadata recipe; available even in a shallow source checkout.
_HISTORICAL_METADATA_CODEQL = 'c-rk*ZBrXL68`RAp?Fgnn`OoZOd!sZT5oVA+_8p@P3m%4$|cXpSYa$pBn{xa{P%5*G-HiDPO`}s_vJ`cu%%Y3U!QI@KcQnT=9nooCkjVcVI<QqBvNwm6eWU4B5nvGcQ{lip^T9TVTR+y2O{7@gd|TzNDz+ZR7%QOP-A#by68EN$RDS*8fV=aLP;uT`Zq!ofmt{svWwo%F=g8bCrM0v_cP^kTk{s2M)`*QmdrRK%da=W{p=?+<d@kk305=d(<{aWG4~?mqx#lXYb%&X^-Q8T9t-k5B~lp*wMa6tctSwSZ6rwkNiINS!5RGkcaw-J5?$V#G7>I`(%7ouqYwn?qWaDO+Cy9LuT!tp5+bbmr6vnGQ-moHOAs8@YVbWwg&-_k=<T0S4=Hk|GF8w#l?pL(1O5y_8xkW!tI+!t$8<_Vtbj4%0=OkH24_<x;j>I*6#%;{!PBG*mqz4$>_7bY5nWL=ODDlC7uVC6-=fc--DS9nslc^=z|#2y?*H^Drx9dYc?zOX%W`ytJmUusJ$i&5lxV^kW>-W86D*0|ZB*_ms$$~YxN??9i>5xD%agJ(jWoGevWf>%YJ+En^C|Na!LPtHV0tA|Qmeh=lguS~cKIe>j5AH9^inm0yER9G&R;EElhM#=w<O|NAIc2iTF`T3)q0P$0X311I4@(AN*$*`D==iO+&i+B2)__73!OU^Eaq`d2Oo(^X!C;+5&?%5O$s4#e2W*dky)*g(FQA|fr*(+E(<cAHtE-iuW6EiubU>f%fYUHRs!BEnpi2XX`A`hX5}48And7H_?ea6J>#WeW(kC+Q}_iSXz&fi5HBf)kjY3POr)>VGo7SNrT%UwXm<>_&^h6$^5>MLN;_gdTZW}1RfQh84aS_si!RdPFBM6ojZRA)l*mj3>YqXu_atO2D-ISE%R>@kcO$*t%t^EDC6-#0pONrdYoWtks=PQzDpA5?8ZIn-9)8v*tx%tXW54c2dtqmn>|-46Pw-)T|8RFd!UvB#JMD1iaA)^mZ-Sq+Cp!RIHwQsG*eMv^LKt_8Z(w^eHF}g18X${Hs<>DL5t(9$sIdX<r3LbO(am*m*NFgKlphKb=^Vu|C^3cqi9;k4EF|%Box13gvk9)}JeIAcAcjy@&_G})h(8KfL1L|#`V|TJl`cUj^LohVP+kBr43GgjYs@l`ZbG=YfJR-jRICto<C^Zp%kk*!-~B<!eu`fcR<_chH#&LUAOGGT^^SX^-uPrN>JLWdRCN-sMJ&w{)nyAg(?!pG*XRocm2oe3M{9!tO%MgiVhKrQEx~qX1=SzEI2paX_-)*O4FZqPd!v{2eACYWb%kQk`@OFzjQq>pvy0LB#i+jS8yq1(aoZ<B)<iVYa88-N0%Tq~1ETcnIsE`oPZtpH{_@A9Kq0!bGbJjV`4LGp!R`-dhb=&>Hnad+#C3tRIcQmEA@YZ9sS`ru+@^f^tvBqChc9~-cv5OxbfpdC46n5j6EcOy(^=L;rBr&}8yufN60P5}M!Jm1b$LuTu$oOS{z#&bPf`xedjbGR<L^ndthLjb_GbyTd|z<xhP&@;llWSN`or9cI*$qxyH`@bzQ#7sS~nS=<sD{Lq25W(Dm3xYFTZ%_Z#-v<&J!*a(g(H?cVTxb_&f{ym`-xCbNK4=g}cyEb~uPRj$}g<G`v+&yk?;Lg|Y6P8qKD|VOesIGH!3ZV#T|3=&*#Bma-(e=bvNmQg=T)*)xku%B0e5W}`U2jbg~Y<~kGS&Li~p2FEEu5Rk}xq6{^>clZX&P|!sA*}EtE=xsw+nOV|nLUJwX3x=-58bFYKA~iT9AiJUPFnQ~hfYQ4Jju@C>X<MCc$<uiQ6x>4VMH)-f9C_$xWA!MVCvvHC6V|;ynb-UxAKkZPETj^R2}HHSpb3t=C8ANqDG^Yg8qU4i9q|5x$QWOfg*+Moj+ESc{zl`NeG$7|{jw&S9=fvmg;u#lQw?B8Ie=+;&o-Wo;=P_S^J<BjSvNh^?|IcI=svbTH^H&6Cg@$!0XB2cuwA_oplIg5L8=F?RF(8u_jpu7-@nly@3sF{x4+iEXQ5y_R{_X#waCwF6!fPU-u<OwWh}G|(A-qUml`boH9Q+MDphsj^V`~GJ2ufdq`x{9^d2kz=JLHF_X(qVTQ{F}uH%+c%BWhA+P*O@Od1_pn(o&ynsyEkr~6O#qr-Oen6wW_doSudKIlxzB-+Q5&i)iX**nzYcY?ix;K@e$vvSo%Go`@Nt(L8e&_J{*uNUAls7|sK@mr?BJl}^<j9^l8vm5Ll1iLG%F~sBD<4&Nk2tG(vh3qCkRuZgS!zU??Vf+J}A-7=a<7`1RPwACEr7+@gp65o2To^-?zsk$4=lhgGuOZ;wKyH^0Qz%3N6xXP)-OM*OJI~LK`+uB{U-w@PPtFGJQ&9V>h;S>2W%k`IhkoMd`d_-V4z<x3e^tAl0oHGcE{nncWPs_3%oX%OFm7uVXi)9z>`9P2E9;u>r5M;73-B|1<>u<J>4cYibi*j8Ecb)T3C_2bi>6z4-kLMpc?G@vzA?&ukAy10J<mivN?q83>I_6S<=?P>+J8P8zv>S!PDh(Vr35EK=$|V{tHw6wr#I-GzWHyz;udT8ifg_nuS?44w6;-FN-C+J+nEXv%W~DBl$6IJ5HMZK;!{?cx^@=WL{FcVNVl4Zgfou3VQzQ}gvCG#9w30d%7~;V$Il+^J_VeFfyqvp8<9AyeRa~6d)TJX{|8?G_`qw!P(?pwD1&(fVOmD}rwHp0x6<9a3)bH5|LdVjj!F5Sbc&cQN>>hY){62+XN0!0_y2PaK+r!PpY{eXE_yHe!!O`f#aQ}>=7L#?8(W27Y*G8-$ihqkb^ld4C#?MizY_pz'

_ORIGINAL_DEFAULT_WORKFLOWS = {'repository-checks': ('81bcf1933edc435826e2de411a777cccd4dec7c7', 'c-rk+S#KLT5`OouptFOq1uW&*iFdMEWU)>x#GXSAY&na;U?5Q4l*G72_K<AZ+R6O)Ena=7TSpw*2m<LzO%|`JuTJuB=v2rl;Tma~DNSRPlIVtvDH>BwCDBaqe<2cSHnabcq<>^gQU!lzjNZZkP2`wrl!}B!^Y#uWQ`$k7G!=?zA?GNX(C9|($c$sx_uZd=qWv+`lWf?gGs^YAw4>Lr(O#M*$-pc@mEJ?&e~<Pngl)4C*n}aaF@x<|qTLEjG$DLUReMMjwNo_qYNiv4K7B&XV?{h~wM_T&4J2ep6SITGNlG*s4^%C)l?s{dY1^ak0x99K6fDMx;A0#!GUh^Q7OA~f%Z}Z<m{F-I;vk0^MN_ItOf*4U@KlO8i>O4iBfFagQXyl;2}t6Pj3jKtA}2{h{MTPQf_HWhDl^`EBc$gkRqiiFA_X+W{zKBrr<(I<A_ZsvqrSz7#(#JQ_^+HH@O>-f%_tGKgP5t5=xE|rV?52YUl}2Q4eV<Sh*QjM)%{|sBFR#75<pwVk)BW#iD{ZpIC%`<j3^#SN>MQyX+~u}gE?Ra4TVT3;iY*;BujM1=mX7LJ?i5Q8j(cNos`Ncvvb;wMuKY)sp<eBiFe>L%A}+`nw#FS6j^Gzf=Xbg64)q01rlW`w0Slif=ml^Njd_7*-=}y*lU%C8kDfuV!r}%i*S$+;So(R;}}%MqQT4eqZnEN25rJhWHO=-X3kojWPmKL&4d)azeJkeX^U_N)=>v-V9G4*0%*){0XVMFF{;|;5L0O~3t+!MxhGSgx2S#4cKbRAYNifSiSvWnmG5+WK27YXTOba*Dw&i4vm10qduy{l1DpUnU?-@)4sfD02Ei;qEk_YaZpmEj+cozsZF_+f41faDWH+g@C;}MUgRCdMVQFg4^OP`j+H(brjC5{4OGYrn1>VRjYz%oe%(%|*(aZMpm(B~ZDFqhdDdWIMnE%)|LsQvFgtHF>Pv#D*5X+>>OU+ZaD`d_x*wG@U<w0pecrgY#3sObFurobhN*)M`A<hYx2e_6cD`@aX1JJ&Yz&5pXnF>`g*vD=Iuy-+olP*72jj}$8p<g@RG}ebsKn(^f*;=ElPqG;&8ma4(DXP~_0W`%xuiAsc^Dh~_NLZg@y)<f+^+{GrqfAsE%DB-2P`S0^bILG@r42!#)9ANGZH)rv8H2HLjE{W=;1_pZ$lH(utLs4apBM3q=;aYTCL}r@l2^}<UmYFC<cEK}JbWG<zB)Ym;l+^r^ZD@5&r<eECJGzX9Z|b5DQzFT4TcgN{-of9!2wJZc3iYlshH9@0=XF<53yZ{@B#@$rczNH4$wiL@-BqDi!HSn7^;I>s8^!^Tc$AtsjzHBYrW1wU_(?N%7nthj3qIyggO-=UD8O5O+=2YsmtSH=Rt);##!1Z23aPCRT$vhHu!JKX9fG;oelaIKXrQ*8EA1sd70C_lm7XK?%<bh|K#+fe=<1l^}D^k8`JEmYUbI+9IGb1dVAJAz5e;U_wKVMRv?WyOAJ`^$-(z@(7$nkiMgH#{sQ51gs%{O6F_sYM6?du?Q~vv_A&=SChi+O`|jO&|LpqBp!)$BGI)Q|KYJEBZDzbk(L4F2Ybe|?ir$Os{`>3xvju^Z*rh<Z3DG9`F$!dKmEM74vRcZ*&P>p;-b<P=$ArpzkEqv9IrE+8?IQ|FA&zNkx{tm{Ys;F7tFeg_BN|CDwH%~(a5@ksR5faQx*yMsRvCL+MqGf|#^|!PeGQfh;n$gov6_%#;MLj5rr7d)^3{Z=VV7HMJ;TbD@{4)pc$9N&Lta6T5t|Gg!q&BZRMsT>=&uwJ7v{?528}^IqyS}-X12W!Y_ruNFP;6oE|hVX7{x7D6LJK5!SHRG1^D2o64|>%#_p{#ec5&SHl$GQ`$3MoTRv_Rx#z&HPk3CGxvevPPMvX0{h+LDjfI0E<X<5m3qT*KcfL3yU6y_}<f@OVfBrx#6wp)T8u%5c(S8$sJvB3{jDXLjYQrW&jD<Gdn{pH7GOE^&HyN1O;BUV>9B<Y4A=TFdaE1Qn!kRB6-c3SVl5x|!6dGtP?Oi4JhP*eQre2O%HB*rRdqzEh>-8(GP<>DFHK~3Rd99RDIp<axA5s~^(7@|PeQYj5Z6vyNRj5^yY*dC?HNi%8s8tgz6ry4gWm9Odg^nlC=*oI4^twW~sNKKW_5L10o!=W3eS^(=C+(+MeF@M+6pH`%HWFddFraek0bDgh4GIvqyEPV%Wh^Qj_mu%}Fai<IuO=Q}J!)&NP>~w#*X{)KGi{yUqv5#*iY3wL2ri)WS0W}Ql*ERl{%uA+P0{sD8sJR;+H9)p%-h=Q2gCPg-&(J}P0MSkMfeq}_oYhr6JD>GdU5Fv=6==qaL^A1c5_%`N*Fiy5CNJfhi19j`~KJd*+uX4qSycL<$1sR=GT7r?Zs*L^<hy5wk6-139#8M)PT*~i^XF4w^MDZ9c_gNuF>Wmc*(Pq%1(D1&D=%?tW`3`;pt%R>~S#5{;Lw=__msxSZuFC2bXURa7a5IOjR$bE%0TW%m@Qpk<{N}`bSl0NJm2Ys}h*JbQ`j@vYT7kvOS=8a8-S{?jeGMtoLy88+wWGHM)yOzqK{$O|iRE__9YC)>S}JLW5dP%^T1WOK7;FD{Htdo`6kE;H6h$>yP2SQwwCxU@o)D(+GHu@b;&{W%ug(=l+#Lh890wUG$tuZIuDA$uo-kT@lZmk6m-|X?KLp;en#E@q1j0?))F&V*}*'), 'codeql': ('e9aaaed9693efc5ffb4701697ac2a4d51f5f5ba1', 'c-rk*>vI}8693L$A+xCr<UE5PICjW7wIrqz?|HE|;MC=^E=tS@P%=mpNrOWk|NFHbGtA&2@A7?#Qx${MYIUo-fBo=p=!A<oW(v)T!Vy*&$uta!lw3SSi6D}Q1wrH;4i!o$V<bYD;duF;2>1{o$x{&$grhl?l5!T*7@m_3dcq^}_gPJ(%(n}7K72rpDOIy{9FPTJYNXfE@iFp}G>%7tyiJKz9=dxMHA;j5+zp%!DT$~eks;bD(S$S1rbGr~EQw)JxvQv(3HtaERiEY2vf0$zn+1sRn8aFwbtVOxlx0*+ElP>Z>;y*jEg*#_6r4tW%-PhBD4sGd6%D1=Y?`y)`GN>V5W|Xs9daWv&Jw|+Gz2p&_KY-Zq+CRlVX;JSQykL?4Y83=6My<tt8vz;A(W(Yrhg+e7MO)IB0K2S98<Q9aFWEtFMg(6Zlg?Kx8c4eGtS8B>p~Pi`w0#CmANIsY9@UOS_)$CMaW0>d-q!Rf_YRo60Ll}QmAEO#Nr77@7qR#WS`^`L>8RU_i(rMjH_EyM#2SA8ap+76oMcfRNp;B`{*A0Yu9VFga{WFQj>+8DewUhOAs8@YVbWwg&-_k>h0f97b)^i8CB3cl?pL%8i7L4hQ!Fysx^ah0o;-pLl9CW;j>I*6#%=b;Azr<OC$0&_I3C<N4)0Z%_Qd6;0MKJ>z~E<4_G=M!~H8)7i5y1`W2&Ivv?GcZbTy!h$RD=a6`_9K4m_{?G&s8UZ6xuYPHvVY`i0jZQnww^(%{=-Bis$FwK#mi{~pZF*J12L0<u^HUP^WsejhI(k|MUDzAaVhi}SD`U2lwP~1tS4!)ojSh-r6%gI(E{9I9U^E(wR=dn3;4aAvL1%Mk-BcM$ozcR=-c&7$>Kq_DqIxuB~L|~aUU(4MH$Jcl%8|Ko6p$*nZ0}C)lN>?cuO}<S0h9-$t=r;XOD-W<q)zUYQSKPCqH878Z@MHqNpt!Mh3yQ&>DF%}oQiyHoYj{t`DO0Jx*A8~tHaXEb;i>ZHl%-1h{DE19r6g6kYT2`lIE$CokEJ4sbQX2gL5a-5hW^QADV_wxXZgXLVs%IY;B2JVn;EIuUgcs}z3C^`T4;=tDl7UVl_=pc4VR8Si*#qEmN5++`(r=a58Hd>0ORmrjE{B>j`j{Be0aaTyA$pn?d~1!kMV<@@h&92#bK}$?B)!MAYk5}Om0R#I99?XRa`8Ch)ggz*~ljS)eB_xMkmvuxK0G<qWn;hNCPX5L5T_cPYOgb!9o&0)2V|#7B<23oX4`Y62ub93L0<>1^!3jDu}hUr+!XCKGh`*GFA`y9Lf`bc?&d<-8H7zlEAufegTa-b}3&WY*Bo=r_V;i^MCjHrT0_(4PoV1>UW2yFM6ZDdc*EXci0`B_J_Ux(4MM}>l+?xA^P)d2Tz{$PA<<*`%k}#wJWqJn-<waNOsU8zi88?g2HVd`KQPqApdb@_SObNS!WHB<q8eUuL(A?E2w_w>FMy<<>OKB1w72?qC0$6&o)havrf_P{?*eIR+-iA`Q`B9a#+9V12{sE;$5Ew(HYT5=X%QY6(IA<=nxHG#txkrbamm~UYy!c%SA8jOo$3+enb*Yu=m4J=xU1fH*`Rr$4`#v88|u!Bl3seQU{*K(@k;rxI5^L2G6<`xK%2zb)^x=8NN{ojL8HVq{6Z$D#g~5ZvW&IqUz>7H%M0=xv7F$533^1NurQXQVz|30zgaSiirDSpqUm#N7_Fnbo70}dC}c{Uq6YjRjA*|UQx$UPU7}T>ep|u&7!s#jE}NT$YjFTlCvu8K)?U)UA*)PTXddqp^!eXjd&5>CxXw7+sAaAkzK&oB44-*9h<{J%yA?enxNsWi{do{U6+h>IoxPA3mjId{n&7O<>f2hRe=smnA9joq9JpRy(?XK?V2$Sm6S=PdyqzcejCLQea)Lp3U?l(R|_1c1c5^$`-w8t@LuBumZ6}D@=bqkK6=|wiJO;%vXxF&^f|+##2P@5Zsi*s0+1~zG|;cS5>R?qz!3v8EL};}DOoxzw1R6W@knF!G{+wLmwojpohNdoa}(CRf0)<&EFWDT85UBB#u&W1z@Q0+ye6Vi#VHYx2OEWZwK-r;0iH2>LzeP*2slzQ@5M`vV{W2WZ249R(w6U)bvIP$C7NmgJI(;i43u1f+sH>rDYM;6)HH?sM9%|NBd7bY^Qj4jg*8Fn<&|bL0}a<uSOF^gh%MXtLNjB(|0J!pidt3Dn<}@Y{MN4l<hKkUzqR+--}$EA?nY~7qR%xY0>FN{%+Bk?<4-V*1WWaSb;=bcWZr4RN8|IKgY$l)(mM)}@O7P#n{;c~(q9Wj%PkgJn=7U@xlb9@+q$oCqxfR=LK#(SQoBiw%S={>mZtk7j3(`)qshU8gXm}{x=(fv$<BV%zJJ)Bka2W?$L)g&ez1R}#cv1uhrxr5@|y~wgJw#>OSf9iF`;H_RbDT^WDriW74d7P^JlgXt{A}(cd-}j9R_=AtI#T>@9wt)g+=gQs;Xpa9b^sD%4O3yr7=u~fpbR>qlzUdc=Lo#{RxHXZ(+z~rO1S_L}s>iquPI)QYh~Pw1nh(HFJR6FF<jfXtkO7#`^Nf`AP5Zv(by*^TFwPzu4t#d*vSP1aZv1yUNqut1h`pm)4;iv5&v5UDxKaukkLI_I{>==?Uo+N>7-?w{kS7wzcWPGGp11(rx5lcViBImap8LkT;$1GK+2)+?D0ts+`w-U50HIGyN-jW;-iduD)+V_9Fwp@0s>hf_oN;`mZcYSHl!$U7O->&^zlr8IGR!2A5~U&8|{{lL53W6{J-YIs4P?ch6q_w^wnCd-#fLz9+6r%IL6mUQ!AwsV5vpg*#=r>X1sx6EAR>j$`rBWTuXr{5H|Uhb7W`O+>;ON8TWNcn5^}tPy%Xz+PoV(lyVcyL%4-Ct()0TjoY24r^Z=VrCY0A@pmO`O{~a8|GNLd!!6TK!j---Crr4J&Kv`)=h9@T=M^(V`Z3>{k1pu**tY+Am?6D{^<DEW%k~GE&vF6C!@1&|LJA-X>afuysG$%!{=tQUpFBdIfY<SRQv3d$PQk0{Z%=dt^E%O!s^f')}

# Exact historical26 and future27 Parent bytes; no Git history or mutable alias.
_ORIGINAL_DEFAULT_WORKFLOWS['parent-qualification'] = ('9bfc6f8723b1f59426f913472b78206844a7f201', 'c-rk<eOKE?*8iVRF{ODbyRrO2zywlvONpD%BtXHWyC<9DBg<n@kR?TuA#9rO{`~IDNE*qqF-e+qyXrX&*34*L?!9y0XY?&Q^SBrKuFJ=4GK*&+XM5f_^qn#DuRR{JklRkcA2H8omK{4+oL&3j<;3-`nIAISiY?baXMy7}$BXdbMl8N?A{P0x(B{oG&zkaGc5H>*i`m<m<vJ4wZ#llV7VvQDL=k>QyK9Wuz89lWw2LvV@fsfOS%}x{8>&4I{aLWf0@0C~>&U$K{yjT);)~g+8S=@HhGZW;=*7{6g%TRX@@(#!j%Nm;e;)D(!%ZwV;%jgGk(dU?i8=jXOwHZ3JSL|StMMglBGJg1?24&dSbuF2`qN)ej}B|bt947l(VU`Yy^%g%h3l`4dZReuy67yNd6DURyKFX^dGXBL*le~pMNRBXIc8=~9S`%vthYpQ0fzKn0gkeea7S(QvS8-AX2{>pcvNU@UvT?UFT%*dEKY}zP#6N3V`ppuT#R5H#XN|b0l?K%?VH7h5(!!t)cUr!sZ4v(wc?2%PKPveC*<SBuNPY;ortz_Ev7>9KCPIR$>MN^`Y{8^&@22Mw`T-97Wl4X->6y4BEo@!YD>TiFaPvl{J`Ga;9HhuZ;h;n?X8C!TVrdxyV+^morj%`?FS=kr#<SZUamm{2~2@}K9Ortq`|MSdJst9M^5aAH_b7hSTi>sjzUoJMFtXrCOS%{o|S?|ohUYKECgLSp!0;<lO_>h9C0&QfC=K^=F}haTN>`NKhi43nsUZkN$mS>)B>T#Ccknpy3OZmqZ`jQMU#-vqWSu4<#O0)zK4-Nohy{kF(tYrYMQ~#Tr<xiZYIW$N?VBvY)Il1Z@3-Hre%#1LZg-w$K}m85!l;YSCR^+v^UKQKZ=|2yLfpk4fjdg5`w+ppi+=x!klb>I(6bNNT?}y)rm3P^J)2n$H2>&2UNYWDwQS+-kV{esJ4lX(3%147-+#B9a#}qt0uUy5eGIn%b>@cY2b%(LO>39M*6lXC6%h;-c`2FCr^iiqi6lY++t(@l56Y;1fuVS)+`EJBgbn6H}Qq<Jz(YmGf$cMGuH9L560=y*~xx?_~dNw<gt;y^ey|vd53jKl2js>jeI|j;?N43?9kU2gY7wUIfIau%fg!%JcO)G`jf@%!ip|jXVhRsjt%BV4fN6g_p@UBI~xH6HUwZp$d(41g)Uk*l|aa_29YLEipr$tV?3^<Eyj=%uH*3@_0ydCo*(<3W7q2UH@CD#6XtO~u3cH~jMsNH!Y3ID{UT<f3R1^%fX|oo&<{gDtQi@qC9>Gev#u=1wMH&C>bWsyo`d<<0?P@b!YHEq-un-^LQo33<Tni`=2NIJOuU$XPpASkb+i-nL^HXHNAmA0RJ`s{54rb34t+{BO)G5IiXtHNgpaY!?YNc)d-LgFaGcaV#TIgTSXc(FGE^;w>a|+L-3g&rJkgIRz<vi-ZSe92n*z_)IeuIKSJ-dBxfP!CxIVwq6`-Gtj;VMK9~UryZfo2d2fpJK`&aYp71n&B7GYe(F$8m~Wd)8BDNSr^DF|AgZ(W$KIRSgWZ24Clgx@mmCnGiH7NVBgdv6fy@I&W6LR&O;jh{IfWyp;Ce$>Q<cS7HLWh9&3c-=7eY#Uq(Ev+DMm6qAM^2TaX_h~~J4db8Y6DNK;8<~57W4<IdCc58fZ)}*Ij=AyB_|TYgj6LodPx=E5P7)ZT89Ls1FWEq5aRWUPWS2Jlv7PUMxN>3JHb*nZ9S{A0LqV-+WLB>?sj!xih|(u}&?jr1b|W35UT0R6($9j8kW@E`m&~GGZ=>C2AlCG~<~h;6TdVha$;2kmHisyymr&ewFMW|z&RVD2rvEzmwqj_P)?i)Nf9R=3a^NE5en^2@FWZxZz^3b4<A^$I_#+bVL$UXV7ruYllWe3Rl%64!A}rL4d#*JdjV(6Zm2>%pgj78nz#2mWVW0GV$*E3pc$0^t+<Qcs1auIRZYpSx0VD|5p0C2(gBdusPbDByp1vy{96vHX%mXi@cS2Cjcycg!diL}1q<?&LdN4RT`IiBN86_Ld5J0~5_2I!|(L?7!XQ#cj(QQ8{(7aG-ha^pUBtvSs4Jdo-zw93lhR1t@r^f3N{1gApdTBb*FuIun&zH5jm}9<<w6XaLqS{&=e}<9s9}Y^Agj6!so<=BI2SlX9(G4`VT74n$<hu*Pp48_B<jC|&cy|Frk~n%nC|i<lV>I4>sLMyFUPhhdr4tEz8+vsu2peO^j_Ztr>J}sE7f^>$$K0pDX@HKLccQ<jMVvBf73M($FPa4uzFTIYtyOAch2Etk=`EP->C-(i*?II!=#T_fn@H~dn}FA7j&;(Cpfo9FB$&?Bg4zj#ylw7S=H&JJ&GrYQAsgS;O3t!g0F1CNdU9>zHwW<UD}g#cW!XmIJrSjbnCT##aWM(K4XL}di_}t!)l$zbBBR$6>tBkK($&cB<Z2+@TJo6|BtVoW&5-k+Y#@iGg5pf(0ieI3CM)KeVvf358FQj>eiX+eYJ+N=ErVJKtl;l`;~x-#Gl=Ia-s_ajFzp~WNqSdIr%(+u+aoJPAyF{<Y%z0<0iwES=)%e=3=UNHj1pV9C2=(*i6Xo^FguMrd-CGY;Zg5Z2u~a-vGiAX;neW2<j}7RB!Om%CIq1UYekq~YqVyX(d%-lt42hlj%29v`BnS1?1H=olKZ#Y-OWv-v=M<wG#a`7sHhOZ;E`g%P@W91D{B<_E<9ef0y`xULNByv#(9dCt~%M1VAr&H{IEW!_d~kJQs+k_dWc?ic3;oyJgUc5kJ>y+#gHn_$)F-(PW+xGa^$=8yLmc1I6dh<sZkS>L<BvF6KP>&rQfyvPN$;?Q5G)|TO)sb)0-1gk5VjBeSN{ZqLH#1$*AwtMgmXJl(93j*Xv-~WLLn#8yWv@gH=#z^Mbz{JLjax1Hnbai#=740X8&JC_zKv038mYI;Z?`s5U@q1VbJSg*c~nG#grDJ+I@Cua3A)KvJLP)JPjP4620RRSa4(k5`7JIT(!BQrtH(0o72=q{@FPriW&!@tf+K4I<0@2&rO741X<~E?F6@mf2d3qf`0!8NZP~2G}q1*Io>Oj<6Ht;|cu3(0S!UX3RHF)1RWMV1NZMKG$;Q!y+~8=xlI&Hh>By%?5)6J`4ltTg`VW%bM3AEMPQD)+&i6d8|W=x`s(ozi<58(>8t(!g#A0$3+`cbLSZMvtFA9@w4Pf$~8mt20Q{(!DeB|Xr5bX+(az#12=U_)Lk+;htr8{U3C46_&_qtls}ibkM<tFI2a82k8=*{g4-!|R;NqKdzMHlu=RUMSL>`tUf#TC?7)Lh4R$bQ=ia~s56OwNIAEdtU+|QFlFw_2r^{xBaulIufL(YKJ;MJ@sg=XZ3*%awN}Et|u9|@#)H?P0Bhk2te}$4=E7UirLI}+D;gIk-9In?5&BziGqg5hIm({g^knzms;V=nnLDD8sCW&g(%)%Gz_tf_I{pjS`>G9rvzm-<5uSsnR0V(;u3L=52QYeM`N&`lgdu`o-FSGByW8cV_6e4i)xhCFdiWk7dBY6B-ug8pNX4AGd*dKo^Zgc4b0puq2QyP>?f>Ei-SRRa0`$M^!#i9~Q5^m~Sf>jzt9lh+I4En?0UOXQT`lo~8$=Tsy|3r}w<V@>r+!bW>cIr~s=oFM%9`bt7uEIA}_~vgBzNw-aRWzfDW>nFPDw<J6GpcAt70sxk8C5i+ie^;Nj4GN@MKh{sMitGdq8U{*<FiIHo<o&mvjB%SoO8#sT+QKhd_oWYB=Iz5?(PWoMWDHvbVuK(`j)V85!^8D7925D1mqEU&2%r_Un3sz@o@-v6sH_I62%`(;X1^8h5g$qJM_{@5NQhB<$adi&G};mRZf`ke-Vh48PYXA6v!O+gr69tfn{I9sUqSaJ%TXGJb#$dUDEK!AG0Wk+*a$Ecg-n{pyBuie@CtdCzd2cM~C2i$9hbSuG0uffw-VQpY$I?=RZ5m2h&7fDUsxsrF+*Arg^saq%UGNi(l8*ufKhGH0=MgzkfD3I67SXwhpO<ByW?RxPC9Up4L5mdaZl<aO)6}x`!D^X^DRXD*niRssj02YoS$&;yQcuNbB(XdXY3<kbVYk1N=B1ISRmiMEEdAY!X!<h3_^5hl*K8@0drH{kJ-+(7x+gg%{{5L?sj(ZOJaV!;>g7pCr=-y#eH=^lU-Zou5u_Hynd_;8OVcWbbhQX>MuS**Bg3P%D=Mw&M9_Y@J66pKSfUW-;H(_bh72yau0A%%;#J+4mICynRD{gYcweD~Mm-x&eDh>m`wHc!|kvOR*TCPpS@BF4`o-md05GND>i|XUKB_t5z~4`6wd8bQVpI2xq@cQz%&(cg%c08HY4YBEYl>Siw5VBnTGq)h`F%gki%Xys*4;(qFK2#Ak>n#6A-ytm52Y5Y+80bIkF@{Gi2biT%OZ-t*y$qsRRmn-wAM;u;9&!kk!;E|K*`858MpmJkyhgU;keTe;e(i&lBdv}mbmUq+Q^F{j{2c$<70#5d&|O4~EHYeQgcDV=4yP=e}Hc%Gp99t!||<gTL3jMZ^Z4xiL6$jddMRGSi+KXIFH+oN{ZwvZgKHJMDdH#<8I#}B)kI}cI1+1-9<cRN<OY?FNuD9Nd^%Zvxj&W2I8@<YrEU|BLB4=sM$*xcFKZf|ewU`l-QVC&%yTpxS`f4ZAnd}~bdcgKG4uyi)mgEp6q4MT%;?N4K1B4=hb#C$WqDGPA=6{go;gFfD1CO?h3d@>oexA^AP=4fN9-QMbgICeVSZo4}g+ug~;9!++-<<v2Tq9SZ;fe(apXQ8G}QvVvZI@@`8yp-%vX5&Ch<igs7bmY;OhfhI`27s8!XFhHn2(W7$cTIQyk|tnYk;DI@to+T}vQm3$UGmb3SkE3vIdB5G9PyVF6O>u5bg3$1O(xPLSHefAHk8K|f;e=IhAO^19&+-l|Ig$8K2j2g$Itf;Z<pBlL;QEr!o-Xugrx8I^DAI5Po?8QOmqESZgJE=4v%a%_hzxambRlyDWuFw$6X@3Xnom>^U^CdqlqvP55-aiVU(NBUyB}oIeY$m`1I&>pwoiLlS+CNF>^6<%>dg!dU5=`j|{<+{(k@9c=6lG+OYzgJ3)M#m7UI~b+0(aBD?yJa?|;vt!8}}r}$mnY(9_|sxahEO8W-%L|#F*fB$~U6+Sa>UVyMn+TN8VN3$_*jtOFuqJO5(_H04SySpb`hI}?5cXR6A3U8>ZW~4!@9<bqvZ-b>q%)DX$)-Z<DQd6dxnQvoZBD{^q9Jx!ONKxB@oquHt?t_Z1N#Q&y$~~xh#1hWksi@73FxOvxP^`ed+$bqC1s>6JX{Br302fhN)wSb|{p*dwEV`yPk8}-%GHt2Xd_?MyhbwWYF;@3B-pUHM<`=5Z1oIn3=EQfAnMC10;u0=3>E70+(52QMPxB=rrPYl}Do7WEbhSg`2upe;n3a{K@Gq@Q;D1ZUNG+XG5-Bh5MWSj+ClW^3L*(f%?_=!HJxj&9ymE4RPOF(X=hzp5Lz$d{CXtYD0DZ)Mi?@Cgkid`M`DkBanVt@LEY#}X;%?HSn`_ZkElN3*WNu(7h$uP};!0GHoMTFEj2+jBZ{|2tj?<`EMl?)17-k(T^%{JX)LEH%Ax80y^eLF{GCO>9jR@Xc{2_^FXp(20SZryq;$!$?>R$hxY;rUkL88!t)=EYxUwV!Nj-ls3s30is(+(Ib)g<u<AYGJ{Ge7+LX2ZAaOq^3-;+z5{_W@2&tI7NdGlHf2%P`dW1=|aPy>RM>O?FJTY{gnn{$xVYQ3;?3!g=Js!<#}qggz#2K!g1SO;!kOl~_r0#o}JRXlh*zC~q7faeyeyn8K3eGFFzCm>UWIDRg8J@D#NY+TvJ4=#R8yX+?tal*O=r`10W7=<o&9VDf`WCzF~+Uf#k7WXGVCYorf{*zrwd-dVKxVFITioJKfVgkUs`=ON9@i+Y)79A`lYgP=7rWfK{Efl0CB<k{nKc62FcOikf@^RASJER<o9OK+mEpg!j-HK!PLg59f8JfKgYM^<5w*k96~U}l(E9JgflCq&*Cnl@L*dlJ1anvu#StZs^JK*l;#QUjCo1gvm$;v-03KjyReTC=4ba%Df`tsp-5dmQe9PVbH^A^HV2HDfXz@V0YansJ6Ln>WkymmFrOUk#U~oNq;PNvB_1#eT|k`ucLZF)~Cbs1z$!qMv1mLI=z2dRSHN4Bo{AT$(knGQYvp+jx?rtD>DY6}>_JYT`Opr<LfqT$I@2`Qt(FrmpZeOAswF+Lw5ni6op7_s(s8ov%V8D@)bP&3Zdo$y9+)r>oE5Wx5+#ezf;VBgw^HsE_qN-I<1UcUQq9^(mgHePrPYF(_^rHLdZOZcqh<<+>@8d;ew3?=C_1v^CsJIHkQT+aNnzQ0Ox~4OiM22N9N^EOm1EE>Ql4dpIrr;y6DUlCf4ywrX5#UKoH{I^$2;NQKj(tsI4{w2Kl3dv|WEB8Cd2(1ue;uIH*uXRJy59K5Na8c7}3T`wd*&;msAN>(EYK#YNNrvRW(#8q!pq@b@4n&C=I1X!}tJRIkC=vhF=J8-gbI+MP_zroJThsS1Og=XR?_-V9lZ*{xY_Vxzvj=H1CXzL*#x5qZZWm^w6tj+D6@%Hw^ok@AjQUL9?OQlP5hVG6d330N;Df5?{Vlxl19O0zV@|B3S(geo1Az+tnmZ3L~RAKW;=C11!$sGe<6^d$F^UySJXG{{#f0&xnqeKL1wJ95EEpK->weF+hH><t5EQgcbJ>6jefn8gnw~)TJ%QE%IjgiJ8iJ!AXo3-Itl81Qsg>~hmgnPHl80ym0yEK+Y829%MA0Is48?2BRRC3e!mkd?TCybFx=S$^_>8hlDXURMu=d?~uB+Y4`sOD@AWhHd8!00)Bkf!FXLPlRPRRo^k6c9AVtJf7_{?!RntxUgT<coY1A-y$3D8mcx`capCs4r@yj=}5>ouUR-cHhrO`T_6oEs4!9`Y{P@FCG7D@bu{L@zLSn_mhJ`|L1=V`uidQ)aV#xAD$3dgHHaN4^j}8z$Ix+OhUONa^Ihb9hn-nLRVtvQ8!u-f7bUW;NI5{Z)s$sVwElr|3=ps%|k#P5J*>@GK|#Ip7r!60;2kiL3Qy@b@5Mi@lSQ}Pj&H6b@5Mi@lSQ}Pj&H6b@5Mi@lSQ}Pj&H6b@5Mi@lSQ}Pj&Inf6-?Qw3F?LXYDWl5d-p%rOB1)7Y&l>r!u1Ytig((HApWyFWzFYdcLbVD4il9cc%U;9CX)1&$oEr%kR7>E{KlGf4y_^pK&4DS@yrs0rO8@W^&+UB7Dv1YDG$I*;z>G*)~@_s%Ux{3rJ4alpRnkYq!FA8*$K_!9(@NGKG(eo#Qa4DAdkxX@}IaV@2=P7X5keluok#vTLSAc=}c|fj@j87MpXw%$-2`lttWfNV4=K5h^ZWpruDsDCMn{PBD$8()(GEd3p)AAC|7()-D=@+AH!>p!Q0Tii7$Ru#Xs)=7PaRY&~6`=wm(WOBGOCPuFE+U;u8LUfOi`UOx0acPdKG0Abqs8c|YKBW9|FPC(WWAdq<;pFvS{%}iyCk{frDQ%Bj^IQij=a>|Tom`^^}Q#_?}3j(RldOp8#d1Fo1uK!7=c;>Ib%P1;$on0Qy-%`A4@Az5k^zpM~N;2V&Zm-ik>L7dvxDeYJXT@l{u|vEAn@`ATVlt7^Ws(4H^Ybvn<X{q6Rq6(#oX#|tc~GV^si^lSsZGY6QJtP9`eI7epR84_u26j@NvM)R)A4ae_}l~GJGMND_!V<O=kTA+%`D3^UpX6;+R3AlO=^J#E!)Y4k?E%C7kzR^AwDKEQf6J=<Ui;oR`{E&$=znSRtj#J6r?bhr3RV#kA<nSd{)t2^LV~!8c+2ZuIe*f|LvdQ`k%X*v`Rm!(vPb2qbmKVN<XU7kE-;eD*dQRKdRD?s`R5O{isSms?v|D^rI^Ms7gPo(vSX>^rOuDRsJ>W{5<66;wxi+p){mqx+6bMKXjrd>|etej6T-Gg`2LQ_V=GbgFHQZJ~)+4WB=FFqr;kr5Y+#d5|QMc7Aj)7dLoiRo&h?0J&TkhHBlXtI0Q{x{nX9DLeW*26r@JqS|Sf4(?O&v<Vlal_usd^Z%)U?+W!On%n};')
_ORIGINAL_DEFAULT_WORKFLOWS['optional-parent-qualification'] = ('987d8f0d198e40211ab0f33286a55852e286c174', 'c-rk<eOKE?*8iVRq0l^)-B^AhV1lW4ONpDXNq~aM?jAPBN0!H+AWMoQL)et>{`~IDNE*qq4S^(0S3Re}ni<W@y?5^WjDFBgT;>Lz<FJu7o<`GvX*=#H@a&Q1UAZjK0%qAh+tyr9Gp)$JWZIP%T#Oy>O7jBEG9%OR&NSb4HQNpG;DlOqZiiavO#_S7S6p+#I@+NbFgMaZOijlg+jz_N+!db%6FUs?GwiHrn&r6>8igH<X^vL#XiWpWW?fV5S>R3mj^^`@j7&$y<4>QoGdnt;4(kCM4`@j3=0+_J&rOujAf{_E$FN<)54^L0g&1yZIw4zm?+y7hFiyniho;H7JEp6NsYG&o0h^FFvd0}hbrb8aj011-kK=>=ihjCk3OE`Q)U4K$$ID>#onEcwCtT&71yeUPJh!7whf_D28f)wI<~py5><PonjEU`Hewg(JFV4Y`{>#Bp6cX;JjaueU9mfdRhbaqlt*vurU8qGE*`G$q5CXXab2PD|h>bcLfjW$sAJzfZh*>B!Bn8M<>v3a&2R=TB<p3xd*&`D`SGxhwlUMT%XS$%)%ig9k<weJg#$GTP(E9Blw}#B?`Id1fysdzUAxUMI;6}jGqF@@*VnKNH3j4^cDPchKJ;%1L<t(NlVN&9z!J&?qe|b83YOSxa4b!wXhUT;8#<R7Jk-6DkZ#Avfv)0<?)1kT59JXXHSD>UAGaw;07Hg3N#xAjXkeTm=cH{-u^${DJQzse>1MG$K6eI*qbQDiLEd{09VPsfX2)eSdTjD(vHwgjbkQwm;43Ho*Cf<lGY1q;JNUAigE@rHhM4sn_4Ul_euuB`GTWqE_yml>vHwoA@oUKn+E`|+fdl-6?nL+^_L!e8brtV+QG;>YjiG2L9uobVswkCe_9vee6Eou}K8nqnT4y(Tp!6aw85>z;$9d4X^VN{PkMvGf1xR2Y$1iLeh&IzX$?JE4#lI^Pv&5(hYOt5RI8*RuiIi{tZY4*hTf+&WkjV+Yl{IZI<mnnU|csb}Fyz1>|h&1vpn6f(oFO@VJ(=ccZZMWfHN9UgVR5SK8<5)9(#X5feSwB8FIoj<FUYzV4J=c?$e$aliKVlsMLsE`uL(hxCC@}rHw(qHn0kuvYra^LvW#P?p7C?Z-{fT1j+zihhdsx#5J2lM<Yv`p0W?)A6cRB<JEJ&3aXV^7u8aQZOms~dKjN}C0Zm5iVKE&fn(qaVG>)0;qQa|;H=X#On+E%6dWPL+vG}c_kMwLs`nX+m}p#u_35ZaN(tH8=l8~A)n54|Apf{LD^S|CfCy5^;6JLb?~dNnh~)U`4Hif`IMm>Y$6-~DuxDFmfx7wo!bM{EMUK;tiF-{bO?rjB-eo@gdku`T|dqT*ebddR#NFeoXqX;NW1W*7pYM{ESDx1vfG?Dd!Z{$X7A5>murL2ene%0RXl$k!?%bH;>T{zN}QAAA~EwZPhH+5~tu&+y|MxB`;|&duPAMb+7r-U9mZ=$MLYvr!HM=(fV#k?+}VzJEEtZf?y-auND@6hTfk8m4bc4qL~z7JRYcdgi&|7-Mj|i-vc}K==*)Njy?*W+8H^-A_8P4ll6(%T+MFqyNev=>koE;)Qi=csuaiQ$617`n#IGV_D3P(9-mMN2+d(OLrtE^@KK*Ueo_&ys)E})1k5B+s0dxJ-qw1=GvOkY8h+K^qbm*VeC;?f6?nJa1y{Eb<1|oy72}w@*8NIlU>sAZ_R8EBu#VMwmzKN&S>EI3|e1BA+u_=PKA}2M5L0|g_2fjHEYQj)v9KO3H{932yu0tc*!*EcGsFs4aAzfS3e`#cPiCxH=fuSD%=2N)dGsU>LxFe9#?6#oAh5R+m;XQ&>GCE>d#%-NDQ2Z+|LP6t3`W~5LkCSa}-i%HE&4rZov2c;N0^rx`K_=xDGIYj(~-_QP(ji!;z^CI$|!rk-|_-2Z;5??r#}QA_}gva1?uwD3gE=LQ?f_<<W-(VaoGmka;kC+w!OcM9PwP`Gf6+`pqoxQhFx@RrD8o{g)@d4vu<<2giH;gQI`zK$u>z(R2>vrLPb6p7S1BPg`5fjkR|3X^!T(hBqK-(j^&E$!tK;TkmaezdtzK>A%$972u!vZ`w=U4hP}&1bDuvRQVjUb)=lkRuI)zs`xVq?f)`Rk|3mlsdg1YQ92+Z9SpCbz*MSpi6`5gA9RI!%OOYhOw7A;AQHsU^#jq8bQ`_)>82_kp)%`Ll9zVKjaaCe6+ftrY%8j23{*ECNxy+Q^eW~)0Zx5%WPjxSg$?4AVIwyW8hG9;U@9z`g|b$mjpce5lB7Flvd1rX_+)3%FQ7vbSZ*S*`>%agp*dDbD}vG_nGt6?6Em{TVdXZBEz=mk`?TJ?(QBgdvQ}c2)f`~By4@9P<G&ez_e2WR*(r-Q67R7n)%i^O!IbeysBK8yrClVKny(gmZXOxkE?@sboD{A`bSG8=>DCa>v>*<mENKRebwvX)G!^7$G7A9p4LMmp*93Fa&8;!V8)rwcU7|Lq#_2Ms6~_wxKGFXU5jcf-zGU52(F~IgGLxit`E+vCusU6`LL?G7vriW@(-<JC@`esf)7;=dbyqJi9UF?<g1by$h3Q%L<VJzb!tQAR_ZBI!^q0G~<nX6r=yy4iKr=}b9MImCBuub1S~Jb)U9r@aBcf4DFjVn;+I%OvAR}6E|7NqjzOENGA`tOLL&qED6(SfsLM-Ugum`&`hoR@dja138QxYNcLW5?UrD);*5<PKtO`FFHsxx{&q<bWEel((o@U+!=H>>l=9vfY1vz>?`S)7qUdBPlfT}9-Gcj<Tic(8YT)O%5(CM1andIBfH!bnShY<jI$OA?|eULdxH-srkJBc!$yEK+@S&bz#kv>M3|*{TdVo}ejXXQr=L!L-S)fQ2{I|I-Akpwjv|`#7@CNRbDE^N8nrDklRhXrxer2HdMS7(jJS_~SrsfW!!fJQ#3sPVHzmw8m;y$064haT}kcKFz6?G_2`V31=oBv|t{mx~VuA^mjts*HQshlg)(6f6S+cW{L5e=$kbn%j^h=Vn_^sC7mu=8CoT^wQ2{);_oYVEq?T|U&ODS2ml>oCy2)*I9;LhiigyguOBBrc~#B;^I?3hWXy+oYS_U^|L~*_6-<~7IthFj2Ex^t?NpT2uL4-WXc(_m5Ka78g%))Mlcf4Y|BtI|d_REkR?!dhHm2gv(VwKf)^*}%iG!BQHC^!rYy+xbvoK^7N2V}tLM?WS)>TSWT{0Pm(~)SM_os8Gdpyg8KgXUWI5cnTT<&%?;&V(day{)lf3w%`_nv>IznXicNTO(~kK?XZwJteK**rHeTx#qi9K7*D1qL2qVPC^_oJ37j_i*BcPn}r|8ig^!wnO#WZT-eEu=ZTM35NrkIM?uX1mvxoA8xrH)VPxp-u-(yCKtFPElro+Jhb$|DzC$B{9hNQ6HM_Ssx+yz4n6d;?t6ZvRjqFG#&!J5Eul)TzD5;Xt63ckXwwY_t5sdGgt=I66lgq)>KcIFXlk)w5C`<24#n{`u^$a14Y{m7mOSjA2S=}t4|jHZjihpQMX0<8#fkT2_zaSdf=JX?5-KyDEAtw{Q~U8p?U9JaA@(SqD;54qoxcH58zM}>Q5a4wV!k>xQk%s1&c&lrv{$u1{?O+3dSUxM^daiCFoG9H?h;o(apX?&J-PQe9Ad)d-uNYvJ%tDl-u90Ay}|EqUJv@c<No02WPiVRBq<L1L*ql#=9Kqg;!xM<6dR*BKKQixr6PA_;HwOLm4UA^@KpxB%D`6{_$mWmW#Fp}e3gN(GVoOfzRJK?8Tcv#UuEE{41AS=uQKpe2EG)B(`%@5+SJFP8T-t3O-FG!9UjqxH;z3`snb1#ec?Y)*h6&^-q$Y$pz%1EemC#2E`w#;<Z)9ye1DFJ%I8N?;EkLx=vNd$F}T|i^X0a4qv*g=BPIfa<2~!|WKPDH%PD%S>Himk&^2AS)dw7zqb~O`qtrL83piwWB&W*}ufgsbBs3d0{M+BsIF8totEp$sE)3M-&<y)XZVNjSBt*x);JC+n3}sIwF`fqu*FtYU>OF_8adMoE+46a$!5<YQs#hODs#iNNdOTt^|8*61>f8GVgWkV-yC?m<gZ=q$t5BZ1T`ba1S088A(|D{-uklzNZWW?g^=tz`4gL>D;~(iySs;EZEtE=LT-CO>l@5QZ=E>>}>4o5Oz^(0)g92QS2VOITD$oov`f-hO#z<?a9kbB1$~d@;gE#LQ2Y-XE0#rg7Q^4hr3qMYhVB>hYpjDvD5Z*Yb=d;tv?4&~w9^4?m9_{S!zRWC5IWMWwE^5Vcz|LIHh|IH4(t@`7M6vQ8XM5%~<PrdXluRzyWc5BM=P}~tEZ|Yn9>L$GTRx2yFGx#(L!3O+6n5gOv+P031lG8eRTv?MWGvCL@?$18*NEpN9(gF94lJr6`1F@yaD6gm=Bb-2W$1=Mbel8*_gO`mfWbU5@TW&hES6w1pPTL(X?TDbB3Q(|B2VK+zLZa3Wz_E%Sz3ng=jNKvI@;}@?7SYlIe6a7$dOD2L%epPFm9*KNjpmWqRgWN3JXXV9#?yOtpH4NlZOS)lEu(F$qb6Y^gow=lT{i8nhZAaqwC^buWan)8YY-_LZ7LA8B@qHJb|!94mkk7>ejy-$&lMFwXU+Fp4&!-pn+eQ#Wt;Bvu&Bk@z@xT$D8Y|t!JZW?e(o^C|z%FKC{{_vsm1VJ_rNk8|!HL(|T)7F9O&;CI)COn2(DVzpSlqZEZF;*S0VvHh#MCYzrPNwuV3L^$oT$B9&yzditzzHq?VMm$fzh-U#}F%$fSX9X=lwuz(zR{{h4MyQaqXSimpCHXDzJ%?-A`u|8beXf`+6AjPd#yWMOLM^<}0wua-ab}=oEpeb_4497ll0H%Rr3sC<GZL~JCRQgu1dXW_d6`yez1@sISem7vvnNEPKX0WM;8%BI=ZQEH<Lk*;g8J84XIxi}J|DmYVnwS@?up&}3RTAkE13a@s3yKLjTBdZNE@_U(!u=!VG1o0A4KV;ssVXH^d^hOJi1gmS4tu*uk{%qs-q~NS`($tExRdtGrz8L?!W$2-IKvAf0M4hm`Z%*VY9NM3j;C`yU(Zh3(Y-Z7j3?tR5a+bM^u<|$o_K4Bo)NOgQaL?6poiw$k<o7_uU`*d9vt^o65<(vahE(BgfCbz({~Tv9KP-$o%X1=+uJ*w|8@*AEWu*7A1(9aB=c!J&W|zAbMr^BbLO-CGAhqV$l~^nnLTk;lZHfNVa|dK$=|K*K6#Sxpg)BGnS<t30lBl>2&W@lW#vZ(g~JU`+p+l8>2!{mh=Hy{70Kw^w|GO|eI>jl@&VhMgbVn7s2SJVe-uO`ecKRum&S*Pn|2?f5koRxz;iY?;6%DKIIlxR+o1S16=fb|J%Vdz&V<)yMwsa@J1ACQU91(9865rSxv<hPuYruPsOrjgN8Z(1ZWe7rnMbmQT$!@eD>ft*(ZwBI)EKM#5N)J|8?y^lXM*_+Lu2eYNY$hGIB^$;nzWa-$#to;$J1;H&+&G`f(p`)p#oR|F_Hzn63mLq68INZ#_(U#F><XZlvT}&dl9Hw(20N%_7H`>iu)MZbn#ohE~`OZoY88=_8ImCXKV(eC}PN^DL@};zegLtb4cLFKiP0sV40rwS;S3^-=lWiqMd2cmMsbyo8XDyDG0IKV`64hk0gA`_Kj@Ej;<ewp=B793<-vVc-TQY>|!U;XUVu*^E|}s9tjtc@iFzE46hIgpNYlAu{}l3trBZ44BUMVJ554O56NAJ(;?&+Eoh}+l;WjlDCZE$7=#g$TRhr0BdI^do*blIlLqMp->oI}gLcAC9%=mK5#`nbys$LLkPXu9LDx58tg~}%$M<)Fi5JwhL%L)zQhM^nV@ggCa1EhB484zdldHbaHTeaQuw<d7bFD(=HPd9Vy0>rYN>_b4wgE`mz%OP@SpgLNkTxuz8)+yL=>I(5fY%Bn@l!>CH&o6lNXixGrUt$Jw|hqi`){D)lebj(6y-Fs(j6{8D*}OCA$vanf2kw!)uhD_VmJ-pBgD}}<buF`F`#+5VK)u(;B*(E5G2Z{Y#@QwHz;)@es)=u9u&>kmlL>X-Ak$cb48yYWie2gGYztpiVu`J!KPO>3ZPG*M^djJo20^4(u^Rrrj{J6iT6g2TM<m2@r#wua7ub1_g_$m4-(y;kgggZ=h1Q}m%iGLDLNrIdyC^@etc_h^is_1{WT7T!d`KPCf83m5h(U`GT^c^qKdtWou0K+vsc63mtt;50*@ZrK$)>56+2}KndvFsBoOlzw<5Pictr<`JR>kLohf|JF`N{Ch&<i_(b2?{7+n@^HL2)5lGNjPgglZ+$85vcn~^;O_;KR!Acla^0=LJ45C&0@UEo(+=1}_%Nb1(2K6Sn?r$Uhd^Z;b|5N^G@QSoQH`xFYE@Ams#ci){!UiB~LT!8m+{p}(%m&;~;>$72wMs%w+NGsFL!wKW>g|*%#=Ot+ke;)4jSd{#e9#6{knH;DsY>cx^iw~#Unbb8Xu!9}kFY@LvI~fxAW<=I~ly9CJfLhw4d+od20rN(Npl-G4V)lJ^UN3{(5~R@R6G*ORstkLis2>@4Q$snDJn_Gp%SECE@I17%Mi2lW14q{ZKyFOP-l#}IUmY~Xm6BkyV5M0&&TQxtpH7J3aP(v<oU;FW8#x<WopOK}u}|ff;ik3GZkwB%YpgwN568oeXKd6QS%|f6JY6%_H@8Nco6ok!#o=`h<7J-_D9re~J4ywD$ZJ7o4an;_brI3yUN9xwkQg^jV1%1dI@)>>HDqako4G=C++VSYZ)Ewlz?Z9;MS`)M{R#B^VJKdu0=cZzCd{g_xZT}U)6a_H-R{jr3FF$`^MK~i<&_z@bIEeED7BXyK1m>(q=pu2<Q80a;<O<<H!tmk-oHks8BN4cC!#M7Pw(#RKi_-4)4xT2UcomgzGj?zHcOOzW?w5wR8@=Bo1ta_Iio=<@^VI#Mm5uBa8^KWbL_q2r%68Um!rOKm_tQ=ed_!4T}j7(dODUXQ?Fe5D&OcyE>Yr&{hSNf<lRT|15b&gHoc{c_Qylt!S)$0*}HxVY5l8y3`yC1hyU)sJlKDJu;2gZ(O$pz>%aTGU7qKyxAZUf;Uu0bY-e8=QoaDXabsdi(hHRNeo|zMT*F&*#Wy^4qxA5lzMq6Bk9vewp;j3ncUbTjx=gOTm#n;(th|@3yqB!Jm#n;(th|@3yqB!Jm#n;(th|@3yqB!Jm#n;(th|@3yqB!Jm#n;(?2CSoN4Xy&cC`KVKF1@kAWA%miSIv2Votqtf6}{&zT!uC$o-fk=_X&~iGi1h;PSIPU*WSn$tN=Mmjc~B=UQH}kRUK~`^Pu9TjTz@088QwbFL7|!+|dK_}*^xc*ylDw{HB2?zH$;(2381jd`ph0TNFpFFFt{A|u9a4;~wC%BSK(Z$-zAi`w1d7#zRbLW76%y=ibCsdk1F-Mmmajj7y=k)HPZB>Bj%JI8dK{kM*h6yfOy#f5TnLt-}LzMDB1c%MZqIr3b1zz-D{Fz}P3UzCp7NT!&?#_9buX<%{zw=tG3-&XFzgxSQinP4^vkn+1h1Yox{EX@HI4z<-}dAyI+v@cmeZCzCt7J((W{kloh&f{z<!^~ktF#{0xYz;3ds^K$LLT?~zNI3{~mrY@4I7Vu6gz<H0@u|M_%&PdVQ!!<RG|auv&E-$QEkPi)S<U9&E^e$S1gl@@l-%qsttmxiZd}cx`3H)3?i{{q96x^*Pf28V(gmwZL<WR!0~dTd<18j^H*Fv9z-Pdf31Tv#RMz6ic>SC5(D=L{8T0b`xr{D3lYla#OHz`o=;U51p?+ryNlxp1HHGmDYmB#77Qe0Bm3hv|v~j<{nTu^^TjE^t_m}28Lv87jjG}`Yw@!4XcH(?=om!wl!?M$1L?(6eRlUs7qt8kD6$!=H*-v}&75*-2GB^9qeCSijM3V?l^U;j#XG3LKHkIwJxnN&46|5kK>4;IFOiMm(8XrfTcfeKo2CB-s#4SGMM>flkY?dF{ER)&FWVSMytxRSsliA8-wlbNmOlB*S*~(<LGMTMRW-F7~%4D`OnXOD_E0fvEWVTE)TWbDF=c{>k7O*q^NzFM)ZSXG@CA!64YziSfnswDaWIh{itbf_teFe4e_~do}So9Kk|2RI_7kBkkGi`B$QSbHZc(nK4P+E38?2*h=|6I4%!6AK#5Z{^-7bB^jujBNKTNIgrW#tt(?rI7)!ML+G<mCNcvAb*KVVqB%PovOBRt5UKE4oY;vq-!l{8&4=<6M5T?>F^G-Ps|P>{pcu#MGy!x&R+9Av6s5NyNiy@*Mb0&O|)b6ROhRLEy_f12g@Fs(qDtRV7|{Wab*^Iqr5BYhBnAq_W8k!S5NigvO1`8(G|igc6^stm&Bm6P~ldCH*Gr3J?(^yq*nu>75vgH<=s};yN{KJ%X*c;(!nccF`#?gJ{}lo1HZ6TWKW{Ns@X>Xo@desOjN_?fclrH#5|fsIN&MlDA0Rm8*;ew2S7aNz+)=XYVDLwdAnl_<M4iL>=)Q=g>KynxJsiPT(a)v^eWzN)d9(b=+=t7sMaSoin~zY*$@KB67OOwMZI>5HX=MnOiz?otK5GmdIr=m#_<DaP1D#H<^_bzwz@t`77~}w3`LM50Hf9G7uLu@$0zb+yF}ViB|{f&~!u2fN?{FGYYp0dZM^Znj9`~lL#mTswiI}c@Mz*1*7Gi)o1$RmDpTdR)6~GClFLEA;iunFu;z$K+H}PeB?-0ZnBvHBw+CBqwWkz-`p(Tva=g3izYt%fxILPsN!sJG@bZhgM4ANkTM7P9r4`?=(+~wxSGeElw5OgCp0UiXK(@t+li@nS~VS?d>x_BSh&TP8;XS*ibiEzw)9!&y3Vy>bdcq3^f3;byTNPN-Db%B;i=j(caWkHGD2SOaQ02TPI;PDQsA<yK`(hq)C9e=59et?w=xw776!j^T<@H|6TRk&@)md~__p|6(C^g8eq-h&#wv)A(`JU#Euoqlc$|W00GbQAsh}{5oC<Z%Pa~&(g+zsnQSsOPC~~aO54|Y)s;jEgh4%u}og>GED*C)}GYsQ@>8yg_7&7ti^Uf;BBpOHF1V*-u%#9r1FP}yyHbd8CO+!iBu|GJ@;vwkBpK6RJS9BS~1xX}lCEf<1VI$8gU~!N7Pd_z&s!vAx%KrmU8@Dw')

def original_default_workflow(name):
    """Exact installed22 bytes, independent of canonical edits or Git history."""
    oid,encoded=_ORIGINAL_DEFAULT_WORKFLOWS[name]
    raw=zlib.decompress(base64.b85decode(encoded))
    if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=oid:
        raise AssertionError('original default workflow fixture changed')
    return raw



def boolean_workflow(name):
    """Exact deployed25 data, independently of staged26 or Git history."""
    raw=original_default_workflow(name)
    lines=[line for line in raw.splitlines(keepends=True) if b'nonproducer_intent: ${{ ' in line]
    if len(lines)!=1:raise AssertionError('original Boolean input must be unique')
    old=lines[0];new=old.replace(b'${{ ',b'${{ !(!(',1).replace(b' }}',b')) }}',1)
    raw=raw.replace(old,new,1)
    oid={'repository-checks':'15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a',
         'codeql':'3b7a88765b7181a1bc7dd6f48b9b459e590055d3'}[name]
    if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=oid:
        raise AssertionError('Boolean workflow fixture changed')
    return raw


def historical_metadata_codeql():
    raw = zlib.decompress(base64.b85decode(_HISTORICAL_METADATA_CODEQL))
    if hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() != '3a273057a38255ca368d3028594fb94227ba7c3b':
        raise AssertionError('historical metadata CodeQL recipe changed')
    return raw.decode()


def has_automatic_app_trigger(source):
    return re.search(r"(?m)^  (?:push|pull_request):", source) is not None


def workflow_data(source):
    import yaml
    try:
        return yaml.safe_load(source)
    except yaml.YAMLError as error:
        raise ValueError('invalid workflow YAML') from error


def workflow_events(source):
    data = workflow_data(source)
    return data.get('on', data.get(True))


def codeql_generation(case, source):
    """Admit exact old/new result workflows, never arbitrary metadata guards."""
    spec = importlib.util.spec_from_file_location('workflow_contract_codeql', ROOT / 'tools/repository-checks/codeql.py')
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    def blob(value):
        raw = value.encode()
        return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    previous = ROOT / 'tools/repository-checks/workflows/codeql-results.yml'
    successor = ROOT / 'tools/repository-checks/workflows/metadata-edits/codeql.yml'
    pinned = successor.with_name('codeql-pinned.yml')
    metadata = successor.with_name('codeql-metadata.yml')
    case.assertEqual(blob(previous.read_text()), policy._RESULTS_WORKFLOW)
    case.assertEqual(blob(successor.read_text()), policy._RETARGET_RESULTS_WORKFLOW)
    case.assertEqual(blob(pinned.read_text()), policy._PINNED_RESULTS_WORKFLOW)
    case.assertEqual(blob(historical_metadata_codeql()), policy._METADATA_RESULTS_WORKFLOW)
    case.assertEqual(blob(original_default_workflow('codeql').decode()), policy._SCHEDULING_RESULTS_WORKFLOW)
    case.assertEqual(blob(boolean_workflow('codeql').decode()), policy._BOOLEAN_RESULTS_WORKFLOW)
    case.assertEqual(blob(metadata.read_text()), policy._REQUIRED_CONTEXT_RESULTS_WORKFLOW)
    upload = metadata.with_name('codeql-upload-provenance.yml')
    case.assertEqual(blob(upload.read_text()), policy._UPLOAD_RESULTS_WORKFLOW)
    helper = metadata.with_name('pr-metadata-context.yml')
    case.assertEqual(blob(helper.read_text()), policy._SCHEDULING_SOURCE_WORKFLOW)
    case.assertIn((blob(metadata.read_text()), blob(helper.read_text())), policy.result_workflow_sources())
    known = {policy._SELECTIVE_WORKFLOW: 'selective', policy._RESULTS_WORKFLOW: 'results',
             policy._RETARGET_RESULTS_WORKFLOW: 'retarget-results',
             policy._PINNED_RESULTS_WORKFLOW: 'pinned-results',
             policy._METADATA_RESULTS_WORKFLOW: 'metadata-pinned-results',
             policy._SCHEDULING_RESULTS_WORKFLOW: 'scheduling-pinned-results',
             policy._BOOLEAN_RESULTS_WORKFLOW: 'boolean-scheduling-pinned-results',
             policy._REQUIRED_CONTEXT_RESULTS_WORKFLOW: 'required-context-pinned-results',
             policy._UPLOAD_RESULTS_WORKFLOW: 'native-upload-pinned-results'}
    identity = blob(source)
    case.assertIn(identity, known, 'unreviewed CodeQL workflow cannot inherit omission contracts')
    return known[identity]


def codeql_analyze_condition(case, source):
    generation = codeql_generation(case, source)
    condition = ("needs.select.outputs.metadata_only != 'true' && needs.select.outputs.scan == 'true'"
                 if generation in {'retarget-results', 'pinned-results', 'metadata-pinned-results', 'scheduling-pinned-results', 'boolean-scheduling-pinned-results', 'required-context-pinned-results', 'native-upload-pinned-results'}
                 else "needs.select.outputs.scan == 'true'")
    if generation in {'scheduling-pinned-results','boolean-scheduling-pinned-results', 'required-context-pinned-results', 'native-upload-pinned-results'}:
        intent = "github.event_name == 'pull_request' && ((github.event.action == 'edited' && !github.event.changes.base && (github.event.changes.title || github.event.changes.body)) || ((github.event.action == 'labeled' || github.event.action == 'unlabeled') && github.event.label.name != 'android-long-diagnostics'))"
        condition = "always() && !cancelled() && needs.select.result == 'success' && " + condition + ' && !(' + intent + ')'
    return condition


def reviewed_package_generation():
    """Bind the complete current tuple, including the Android successor callee."""
    spec = importlib.util.spec_from_file_location(
        'workflow_contract_packages', ROOT / 'tools/repository-checks/package_checks.py')
    packages = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packages)
    name = packages.validate_wiring(ROOT)
    if name in ('android-owned-npm5-sync-ci-v1', *METADATA_PRODUCER_GENERATIONS):
        spec = importlib.util.spec_from_file_location(
            'workflow_contract_android', ROOT / 'tools/repository-checks/android_gate.py')
        android = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(android)
        tree = {}
        paths = packages.METADATA_WORKFLOW_PATHS if name in METADATA_PRODUCER_GENERATIONS else packages.CONSUMER_WORKFLOW_PATHS
        for relative in (*paths, '.github/workflows/android-required.yml'):
            path = ROOT / relative
            if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o111:
                raise AssertionError('owned Android workflow must be an ordinary source')
            tree[relative] = android._blob(path.read_bytes())
        if android.validate_tree_wiring(tree) != name:
            raise AssertionError('owned Android requires its exact complete generation')
    if name in ORIGINAL_DEFAULT_GENERATIONS:
        raw=CODEQL_WORKFLOW.read_bytes()
        expected={'protected-producer-original-default-v1':'e9aaaed9693efc5ffb4701697ac2a4d51f5f5ba1',
            'protected-producer-original-default-boolean-v1':'3b7a88765b7181a1bc7dd6f48b9b459e590055d3',
            'protected-producer-original-default-required-context-v1':'7b0703d88d404f38c1b3dec92f77f03586c9144c',
            'protected-producer-optional-parent-source-v1':'7b0703d88d404f38c1b3dec92f77f03586c9144c',
            'protected-producer-optional-leaf-common-v1':'7b0703d88d404f38c1b3dec92f77f03586c9144c',
            'protected-producer-exact-parent-command-owners-v1':'b29e0558dc69bc9dd6fc6b47bd6024382be4079d'}[name]
        actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if actual=='b29e0558dc69bc9dd6fc6b47bd6024382be4079d':
            # The eighth security recipe changes neither the independently
            # validated Repository generation nor any historical pairing.
            caller=WORKFLOW_DIRECTORY/'repository-checks.yml'
            caller_raw=caller.read_bytes()
            if (name not in {'protected-producer-original-default-required-context-v1',
                    'protected-producer-optional-parent-source-v1','protected-producer-optional-leaf-common-v1', 'protected-producer-exact-parent-command-owners-v1'}
                    or caller.is_symlink() or caller.stat().st_mode & 0o777 not in {0o444,0o644}
                    or hashlib.sha1(b'blob '+str(len(caller_raw)).encode()+b'\0'+caller_raw).hexdigest()
                        != ('5ab9ff4592635ad67cd7f542de9676702180592d'
                            if name == 'protected-producer-exact-parent-command-owners-v1'
                            else '22fe0d6d39d120f800099136d7d1ab5280d80b41')):
                raise AssertionError('native upload CodeQL requires its exact current Repository tuple')
            expected=actual
        if (CODEQL_WORKFLOW.is_symlink() or CODEQL_WORKFLOW.stat().st_mode & 0o777 not in {0o444,0o644}
                or actual!=expected):
            raise AssertionError('deployed Repository and CodeQL must be the same exact reviewed pair')
    return name


def prospective_package_generation(packages):
    # A catalog-only preregistration must not relabel the actual canonical26
    # template as27. The entire assembled tuple is still validated below.
    rows={row['name']:row['workflows'] for row in packages.workflow_generations()}
    parent=ROOT/'tools/repository-checks/workflows/producers/parent-qualification-android-platform.yml'
    if not parent.is_file() or parent.is_symlink() or parent.stat().st_mode & 0o777 not in {0o444,0o644}:
        raise AssertionError('canonical Parent must remain an ordinary reviewed source')
    raw=parent.read_bytes()
    entry={'mode':'100644','type':'blob','sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
    for name in ('protected-producer-optional-parent-source-v1',
                 'protected-producer-original-default-required-context-v1',
                 'protected-producer-original-default-boolean-v1','protected-producer-original-default-v1'):
        if name in rows and rows[name]['.github/workflows/parent-qualification.yml']==entry:
            return name
    raise AssertionError('canonical Parent is not an exact reviewed26/27 recipe')


def prospective_package_tree():
    """Read the exact staged complete tuple without relabelling the installed tuple."""
    spec = importlib.util.spec_from_file_location(
        'prospective_workflow_packages', ROOT / 'tools/repository-checks/package_checks.py')
    packages = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packages)
    sources = {
        '.github/workflows/project-tests.yml': 'producers/protected-project-tests-android-platform.yml',
        '.github/workflows/parent-qualification.yml': 'producers/parent-qualification-android-platform.yml',
        '.github/workflows/repository-checks.yml': 'producers/repository-checks.yml',
        '.github/workflows/sync-validation.yml': 'sync-ci-selection.yml',
        '.github/workflows/browser-client.yml': 'npm-consumers/browser-client.yml',
        '.github/workflows/pr-metadata-context.yml': 'metadata-edits/pr-metadata-context.yml',
    }
    tree = {}
    for target, relative in sources.items():
        path = ROOT / 'tools/repository-checks/workflows' / relative
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o777 not in {0o444, 0o644}:
            raise AssertionError('future recipe must be an ordinary non-executable source')
        raw = path.read_bytes()
        tree[target] = {'mode': '100644', 'type': 'blob',
            'sha': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()}
    if packages.validate_tree_wiring(tree) != prospective_package_generation(packages):
        raise AssertionError('future sources require their exact complete enrolled generation')
    return packages, tree



def sync_callback_blob(source):
    raw = source.encode('utf-8')
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def callback_sync_predecessor(source):
    """Only the two byte-exact callback recipes may extend validator permissions."""
    expected = {
        'ccc75d37c4f8b5012299bf864bf48dd45ead389b': ('cff76b696a4afd8658329a02ab33032672f292b9', ''),
        '747bd6424d1e9b533ae35a81b524ceefc06b286b': ('fb8b8645f229d924cfebb068ea124ac5910a483e', '\n'),
    }
    identity = sync_callback_blob(source)
    if identity not in expected or source.count('\n  notify-cleanup:') != 1:
        raise AssertionError('callback requires its exact active or canonical whole recipe')
    previous = source.split('\n  notify-cleanup:', 1)[0] + expected[identity][1]
    if sync_callback_blob(previous) != expected[identity][0]:
        raise AssertionError('mandatory validator must retain its exact predecessor bytes')
    return previous


def assert_sync_callback_roles(case, source):
    previous = callback_sync_predecessor(source)
    workflow = workflow_data(source)
    case.assertEqual(set(workflow['jobs']), {'validate', 'notify-cleanup'})
    validate, notifier = workflow['jobs']['validate'], workflow['jobs']['notify-cleanup']
    case.assertNotIn('permissions', validate)
    case.assertNotIn('continue-on-error', validate)
    case.assertNotRegex(previous, r'(?m)^\s+[a-z-]+: write$')
    case.assertEqual(notifier['name'], 'Notify completed synchronization cleanup')
    case.assertEqual(notifier['permissions'], {'contents':'read', 'actions':'write'})
    case.assertIs(notifier['continue-on-error'], True)
    case.assertEqual(notifier['needs'], 'validate')
    case.assertEqual(notifier['runs-on'], 'ubuntu-24.04')
    case.assertEqual(notifier['timeout-minutes'], 5)
    case.assertEqual(notifier['if'], "always() && github.repository == 'noah-l-frank/overte' && "
        "github.repository_id == '1319052603' && github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' && "
        "github.workflow_ref == 'noah-l-frank/overte/.github/workflows/sync-validation.yml@refs/heads/main' && github.run_attempt == 1")
    case.assertEqual(len(notifier['steps']), 2)
    checkout, dispatch = notifier['steps']
    case.assertEqual(checkout['uses'], 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1')
    case.assertEqual(checkout['with'], {'repository':'noah-l-frank/overte', 'ref':'${{ github.sha }}',
        'path':'trusted', 'persist-credentials':False, 'fetch-depth':1, 'sparse-checkout-cone-mode':False,
        'sparse-checkout':'/tools/branch-cleanup/\n/.github/branch-cleanup.json\n'})
    case.assertEqual(dispatch['name'], 'Dispatch exact synchronization completion')
    case.assertEqual(dispatch['env'], {'GH_TOKEN':'${{ github.token }}'})
    case.assertIn('python3 -B trusted/tools/branch-cleanup/cleanup.py notify-sync-completion', dispatch['run'])
    case.assertIn('--event "$GITHUB_EVENT_PATH"', dispatch['run'])
    case.assertIn('--report "$RUNNER_TEMP/sync-cleanup-notification.json"', dispatch['run'])
    case.assertNotIn('candidate', dispatch['run'])
    case.assertNotIn('secrets.', source)


def selected_sync_recipe():
    """Keep deployed13/14/20/21 selected-sync recipes distinct from future22."""
    spec = importlib.util.spec_from_file_location(
        'selected_sync_packages', ROOT / 'tools/repository-checks/package_checks.py')
    packages = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packages)
    generation = reviewed_package_generation()
    row = next(row for row in packages.workflow_generations() if row['name'] == generation)
    raw = SYNC_VALIDATION_WORKFLOW.read_bytes()
    entry = {'mode': '100644', 'type': 'blob',
        'sha': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()}
    if SYNC_VALIDATION_WORKFLOW.is_symlink() or SYNC_VALIDATION_WORKFLOW.stat().st_mode & 0o777 not in {0o444, 0o644} \
            or row['workflows']['.github/workflows/sync-validation.yml'] != entry:
        raise AssertionError('synchronization recipe differs from its whole deployed generation')
    return generation in SELECTED_SYNC_GENERATIONS


def sync_condition(legacy, selected, *, setup=False):
    """Admit selected conditions only with an exact complete reviewed caller."""
    if not selected_sync_recipe():
        return legacy
    installed_empty = reviewed_package_generation() in ORIGINAL_DEFAULT_GENERATIONS
    if installed_empty:
        # The extra lane belongs to installed22, never to an older caller just
        # because a newer canonical recipe is staged beside it. Both complete
        # endpoint maps must independently match the enrolled catalog row.
        prospective_package_tree()
        canonical = ROOT / 'tools/repository-checks/workflows/sync-ci-selection.yml'
        if SYNC_VALIDATION_WORKFLOW.read_bytes() != canonical.read_bytes():
            raise AssertionError('installed empty synchronization requires the exact canonical recipe')
    if setup:
        steps = workflow_data(SYNC_VALIDATION_WORKFLOW.read_text())['jobs']['validate']['steps']
        product = next(step for step in steps if step['name'] == 'Verify exact candidate suites and complete runtime identity')
        if 'SYNC_VALIDATOR_PYTHON' in product.get('env', {}):
            expected = "${{ steps.select.outputs.consumer_setup == 'none' && steps.select.outputs.native_setup != '' && 'python3' || 'build/host-tests-env/bin/python' }}"
            if product['env']['SYNC_VALIDATOR_PYTHON'] != expected or '--expected-native-setup "$EXPECTED_NATIVE_SETUP"' not in product['run']:
                raise AssertionError('unreviewed no-setup interpreter or expected proof transport')
            selected = "(steps.select.outputs.consumer_setup != 'none' || steps.select.outputs.native_setup == '') && " + selected
    if installed_empty:
        if setup:
            selected += " && !(steps.select.outputs.lane == 'verified-empty' && steps.select.outputs.consumer_setup == 'none' && steps.select.outputs.empty_setup != '')"
        elif selected == "steps.select.outputs.lane != 'legacy-bounded'":
            selected += " && steps.select.outputs.lane != 'verified-empty'"
    return selected


def assert_project_caller_routing(case, source):
    """Finite successors bind their whole generation and exact project route."""
    templates = (
        (None, ('protected-producer-original-default-v1',), True),
        ('boolean25', ('protected-producer-original-default-boolean-v1',), True),
        ('tools/repository-checks/workflows/npm-consumers/repository-checks.yml',
         ('npm-consumers-v1', 'npm-consumers-sync-ci-v1', 'npm-consumers-sync-ci-budget-v1', 'npm-consumers-sync-ci-budget-cleanup-v1'), False),
        ('tools/repository-checks/workflows/metadata-edits/repository-checks.yml',
         ('npm-consumers-metadata-edits-v1',), True),
        ('tools/repository-checks/workflows/android-owned/repository-checks.yml',
         ('android-owned-npm5-sync-ci-v1',), True),
        ('tools/repository-checks/workflows/producers/repository-checks.yml',
         ('protected-producer-original-default-required-context-v1',
          'protected-producer-optional-parent-source-v1'), True),
    )
    for relative, generations, metadata in templates:
        expected=(original_default_workflow('repository-checks').decode() if relative is None else
            boolean_workflow('repository-checks').decode() if relative=='boolean25' else (ROOT/relative).read_text(encoding='utf-8'))
        if source != expected:
            continue
        installed=reviewed_package_generation()
        if relative=='tools/repository-checks/workflows/producers/repository-checks.yml':
            packages,tree=prospective_package_tree()
            admitted=packages.validate_tree_wiring(tree)
        else:admitted=installed
        case.assertIn(admitted, generations)
        condition = ("needs.route.outputs.package_host_mode == 'full' || "
                     "needs.route.outputs.package_host_mode == 'tool-dependencies' || "
                     "needs.route.outputs.package_set != '[]'")
        if metadata:
            condition = "needs.route.outputs.metadata_only != 'true' && (" + condition + ")"
        if admitted in ORIGINAL_DEFAULT_GENERATIONS:
            condition = "always() && !cancelled() && needs.route.result == 'success' && " + condition
            intent = "github.event_name == 'pull_request' && ((github.event.action == 'edited' && !github.event.changes.base && (github.event.changes.title || github.event.changes.body)) || ((github.event.action == 'labeled' || github.event.action == 'unlabeled') && github.event.label.name != 'android-long-diagnostics'))"
            condition += " && !(" + intent + ")"
        case.assertEqual(workflow_data(source)['jobs']['project']['if'], condition)
        return 'package_host_mode'
    # An unadmitted caller cannot inherit the successor's formatting-only omission.
    case.assertIn("if: needs.route.outputs.mode == 'full'", source)
    return 'mode'


def push_filters(source):
    """Check the semantic push filters independently of YAML presentation."""
    events = workflow_events(source)
    result = events.get('push') if isinstance(events, dict) else None
    if not isinstance(result, dict) or set(result) != {'branches', 'paths-ignore'}:
        raise ValueError('expected explicit branches and paths-ignore filters')
    for values in result.values():
        if not isinstance(values, list) or not values or any(
                not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_./*-]+', value)
                for value in values):
            raise ValueError('unsupported push filter patterns')
    if result['paths-ignore'] != ['**/*.md']:
        raise ValueError('routing matrix supports only the existing Markdown exclusion')
    return result


def selects_host_push(source, branch, changed_paths):
    filters = push_filters(source)
    if not any(fnmatch.fnmatchcase(branch, item) for item in filters["branches"]):
        return False
    # GitHub's **/ also matches the repository root, unlike fnmatch's **/.
    return any(not path.endswith(".md") for path in changed_paths)


def artifact_retention_limit(workflow_name, artifact_lines):
    # The existing iOS source checkpoint is a verified reusable build input.
    # Diagnostic artifacts and every other workflow retain the ordinary limit.
    checkpoint_paths = {
        "build-ios/qt-source-checkpoint/checkpoint.tar.gz",
        "build-ios/qt-source-checkpoint/manifest.json",
    }
    source_checkpoint = (workflow_name == "ios-qt-source.yml" and
                         checkpoint_paths <= {line.strip() for line in artifact_lines})
    return 90 if source_checkpoint else 30


class BrowserTriggerContracts(unittest.TestCase):
    """Browser product work is selected only by changes in its own client."""

    @staticmethod
    def selects(filters, paths):
        for path in paths:
            selected = False
            for pattern in filters:
                negative = pattern.startswith('!')
                glob = pattern[1:] if negative else pattern
                # GitHub's **/ also matches zero directory components.
                if fnmatch.fnmatchcase(path, glob) or fnmatch.fnmatchcase(path, glob.replace('/**/', '/')):
                    selected = not negative
            if selected:
                return True
        return False

    def test_browser_workflows_ignore_unrelated_changes_and_keep_own_source_and_packages(self):
        unrelated = [
            '.github/workflows/browser-client.yml', '.github/workflows/browser-direct-client.yml',
            '.github/native-tests.json', 'tools/native-tests/select.py',
            'tools/branch-cleanup/cleanup.py', 'tests/branch-cleanup-test.py',
            'libraries/networking/src/NodeList.cpp', 'libraries/shared/src/shared/WebRTC.h',
            'domain-server/src/DomainServer.cpp', 'assignment-client/src/Agent.cpp',
            'cmake/macros/TargetDataChannel.cmake', 'tests/browser-direct-transport/main.cpp',
            'ios/tests/run-tests.sh', 'android/app/src/Main.java', 'docs/BRANCH_WORKFLOW.md',
            'script-archive/marketplace/S3Server/package-lock.json',
        ]
        for filename, root, events in (
                ('browser-client.yml', 'browser-client', ('pull_request',)),
                ('browser-direct-client.yml', 'browser-direct-client', ('pull_request', 'push'))):
            source = (WORKFLOW_DIRECTORY / filename).read_text()
            for event in events:
                filters = workflow_events(source)[event]['paths']
                with self.subTest(workflow=filename, event=event):
                    self.assertFalse(self.selects(filters, unrelated))
                    for path in unrelated:
                        self.assertFalse(self.selects(filters, [path]), path)
                    for suffix in ('src/main.ts', 'gateway/server.mjs', 'tests/behavior.test.ts',
                                   'public/model.glb', 'package.json', 'package-lock.json'):
                        self.assertTrue(self.selects(filters, [f'{root}/{suffix}']), suffix)
                    for suffix in ('README.md', 'docs/nested/guide.md', 'guide.mdx'):
                        self.assertFalse(self.selects(filters, [f'{root}/{suffix}']), suffix)
                    self.assertTrue(self.selects(filters, [*unrelated, f'{root}/src/main.ts']))
                    other = 'browser-direct-client' if root == 'browser-client' else 'browser-client'
                    self.assertFalse(self.selects(filters, [f'{other}/package-lock.json']))

    def test_atomic_diagnostic_requires_a_changed_browser_laboratory_input(self):
        events = workflow_events((WORKFLOW_DIRECTORY / 'browser-client-atomic-settings.yml').read_text())
        self.assertNotIn('pull_request', events)
        filters = events['push']['paths']
        self.assertTrue(all(not value.startswith('!') and value.startswith('browser-client/') for value in filters))
        self.assertTrue(self.selects(filters, ['browser-client/lab/atomic-provisioning/stage.py']))
        self.assertTrue(self.selects(filters, ['browser-client/lab/manage.py']))
        for path in ('.github/workflows/browser-client-atomic-settings.yml', 'tools/branch-cleanup/cleanup.py',
                     'ios/Interface.mm', 'browser-client/src/world.ts', 'browser-client/README.md'):
            self.assertFalse(self.selects(filters, [path]), path)


class LightweightWorkflowContracts(unittest.TestCase):
    def test_documentation_changes_use_lightweight_checks(self):
        documentation = DOCUMENTATION_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('workflow_call:', documentation)
        self.assertIn('--all', documentation)
        self.assertIn("tests/check-documentation.py", documentation)
        self.assertIn("timeout-minutes: 5", documentation)
        self.assertIn("persist-credentials: false", documentation)

    def test_markdown_pushes_skip_expensive_shared_checks(self):
        for path in (WORKFLOW, PARENT_QUALIFICATION_WORKFLOW, CODEQL_WORKFLOW):
            source = path.read_text(encoding="utf-8")
            self.assertEqual(workflow_events(source)['push']['paths-ignore'], ['**/*.md'])
        source = CODEQL_WORKFLOW.read_text(encoding="utf-8")
        if codeql_generation(self, source) in {'results', 'retarget-results', 'pinned-results', 'metadata-pinned-results', 'scheduling-pinned-results', 'boolean-scheduling-pinned-results', 'required-context-pinned-results', 'native-upload-pinned-results'}:
            # Required context is published for docs; the immutable selector
            # omits both analyzer jobs, rather than omitting the entire check.
            self.assertNotIn('paths-ignore', workflow_events(source)['pull_request'])
            self.assertEqual(workflow_data(source)['jobs']['analyze']['if'], codeql_analyze_condition(self, source))
        else:
            self.assertEqual(workflow_events(source)['pull_request']['paths-ignore'], ['**/*.md'])

    def test_app_test_workflows_exclude_markdown(self):
        aggregate = (WORKFLOW_DIRECTORY / "repository-checks.yml").read_text(encoding="utf-8")
        assert_project_caller_routing(self, aggregate)
        self.assertIn("uses: ./.github/workflows/project-tests.yml", aggregate)
        for workflow in (IOS_WORKFLOW, MACOS_WORKFLOW):
            if workflow.exists():
                source = workflow.read_text(encoding="utf-8")
                if has_automatic_app_trigger(source):
                    self.assertRegex(source, r"[\"']!\*\*/\*\.md[\"']", workflow.name)

    def test_manual_app_workflows_do_not_need_nonexistent_pr_filters(self):
        self.assertFalse(has_automatic_app_trigger("on:\n  workflow_dispatch:\n"))
        self.assertTrue(has_automatic_app_trigger("on:\n  pull_request:\n"))
        self.assertTrue(has_automatic_app_trigger("on:\n  push:\n"))

    def test_canonical_runner_inventory_covers_descendants_and_is_governed(self):
        config = (ROOT / ".github/actionlint.yaml").read_text()
        labels = set(re.findall(r"(?m)^    - (overte-[a-z0-9-]+)$", config))
        self.assertEqual(labels, {
            "overte-android-build", "overte-android-phone-build",
            "overte-android-phone-emulator", "overte-android-phone-release",
            "overte-android-release", "overte-pico4-device", "overte-ios-ipad",
        })
        workflow = (WORKFLOW_DIRECTORY / "workflow-security.yml").read_text()
        self.assertIn("actionlint -config-file .github/actionlint.yaml -no-color", workflow)
        self.assertNotIn("ACTIONLINT_SELF_HOSTED_LABELS", workflow)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1 python3 tests/workflow-contract-test.py", workflow)
        policy = (ROOT / "tools/branch-policy/check.py").read_text().split("PRIVILEGED_PATHS = (", 1)[1].split(")", 1)[0]
        self.assertIn('".github/actionlint.yaml"', policy)
        reuse = json.loads((ROOT / ".github/sync-test-reuse.json").read_text())
        self.assertIn(".github/actionlint.yaml", reuse["qualified_inputs"])
        self.assertIn(".github/actionlint.yaml", reuse["required_qualified_inputs"])


class WorkflowStorageContracts(unittest.TestCase):
    def test_artifact_uploads_have_explicit_bounded_retention(self):
        upload_count = 0
        for workflow in sorted(WORKFLOW_DIRECTORY.glob("*.yml")):
            lines = workflow.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                if not re.match(r"^\s*uses:\s*actions/upload-artifact@", line):
                    continue
                upload_count += 1
                uses_indent = len(line) - len(line.lstrip())
                block = []
                for candidate in lines[index + 1 :]:
                    if candidate.strip():
                        indent = len(candidate) - len(candidate.lstrip())
                        if indent < uses_indent:
                            break
                    block.append(candidate)
                retentions = [
                    int(match.group(1))
                    for candidate in block
                    if (match := re.match(r"^\s*retention-days:\s*(\d+)\s*$", candidate))
                ]
                self.assertEqual(
                    len(retentions),
                    1,
                    f"{workflow.name}: each artifact upload needs one retention-days value",
                )
                self.assertLessEqual(retentions[0], artifact_retention_limit(workflow.name, block), workflow.name)
                self.assertGreaterEqual(retentions[0], 1, workflow.name)
        self.assertGreater(upload_count, 0)

    def test_source_checkpoint_retention_exception_cannot_cover_other_artifacts(self):
        checkpoint = ["build-ios/qt-source-checkpoint/checkpoint.tar.gz",
                      "build-ios/qt-source-checkpoint/manifest.json"]
        self.assertEqual(artifact_retention_limit("ios-qt-source.yml", checkpoint), 90)
        self.assertEqual(artifact_retention_limit("other.yml", checkpoint), 30)
        self.assertEqual(artifact_retention_limit("ios-qt-source.yml", checkpoint[:1]), 30)
        self.assertEqual(artifact_retention_limit("ios-qt-source.yml", ["build-ios/log.txt"]), 30)

    def test_native_sccache_github_backend_stays_disabled(self):
        sources = "\n".join(
            workflow.read_text(encoding="utf-8")
            for workflow in sorted(WORKFLOW_DIRECTORY.glob("*.yml"))
        )
        self.assertNotIn("SCCACHE_GHA_ENABLED", sources)


class CodeQLWorkflowContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CODEQL_WORKFLOW.read_text(encoding="utf-8")

    def test_pilot_is_github_hosted_and_bounded(self):
        self.assertIn("runs-on: ubuntu-24.04", self.source)
        self.assertNotIn("self-hosted", self.source)
        self.assertIn("timeout-minutes: 30", self.source)
        self.assertIn("language: ${{ fromJSON(needs.select.outputs.languages) }}", self.source)
        self.assertEqual(workflow_data(self.source)['jobs']['analyze']['if'],
                         codeql_analyze_condition(self, self.source))
        self.assertIn("build-mode: none", self.source)

    def test_permissions_are_least_privilege(self):
        self.assertRegex(self.source, r"(?m)^permissions:\n  contents: read$")
        analyze = self.source.split("  analyze:", 1)[1]
        self.assertRegex(
            analyze,
            r"(?m)^    permissions:\n      contents: read\n      security-events: write$",
        )
        self.assertNotRegex(self.source, r"(?m)^\s+(actions|attestations|id-token|packages): write$")

    def test_actions_are_fresh_full_sha_pins(self):
        actions = ACTION_USE.findall(self.source)
        generation=codeql_generation(self,self.source)
        local=[action for action in actions if action.startswith('./')]
        self.assertEqual(local,['./.github/workflows/pr-metadata-context.yml']
                         if generation in {'metadata-pinned-results', 'scheduling-pinned-results', 'boolean-scheduling-pinned-results', 'required-context-pinned-results', 'native-upload-pinned-results'} else [])
        self.assertEqual(len(actions),9 if generation == 'native-upload-pinned-results' else 8 if generation in {'metadata-pinned-results', 'scheduling-pinned-results', 'boolean-scheduling-pinned-results', 'required-context-pinned-results', 'native-upload-pinned-results'} else
            7 if generation in {'results','retarget-results','pinned-results'} else 5)
        self.assertEqual([action for action in actions if action not in local and not FULL_SHA_ACTION.fullmatch(action)], [])
        codeql = [action for action in actions if action.startswith("github/codeql-action/")]
        self.assertEqual(
            codeql,
            [
                "github/codeql-action/init@cdf488f595d80d6e07e03d4674febd5ab45fa938",
                "github/codeql-action/analyze@cdf488f595d80d6e07e03d4674febd5ab45fa938",
            ],
        )

    def test_checkout_is_credential_free_and_default_setup_is_not_mixed_in(self):
        self.assertIn("persist-credentials: false", self.source)
        self.assertNotIn("autobuild", self.source)

    def test_selector_reads_trusted_policy_and_exact_immutable_candidate(self):
        selector = self.source.split('  select:', 1)[1].split('  analyze:', 1)[0]
        self.assertIn('ref: ${{ github.event.repository.default_branch }}', selector)
        self.assertIn('path: trusted', selector)
        self.assertIn('path: candidate', selector)
        self.assertIn('fetch-depth: 2', selector)
        self.assertEqual(selector.count('persist-credentials: false'), 2)
        self.assertIn('CANDIDATE_SHA: ${{ github.sha }}', selector)
        self.assertIn('BASE_SHA: ${{ github.event.pull_request.base.sha || github.event.before || github.sha }}', selector)
        self.assertIn('python3 trusted/tools/repository-checks/codeql.py', selector)
        self.assertIn('--root candidate --base-sha "$BASE_SHA" --candidate-sha "$CANDIDATE_SHA"', selector)
        self.assertIn('--event "$EVENT_NAME" > codeql-plan.json', selector)
        self.assertIn('cron: "17 3 * * 4"', self.source)

    def test_selected_analyses_fail_closed_in_final_aggregate(self):
        aggregate = self.source.split('  codeql-checks:', 1)[1]
        self.assertIn('if: always()', aggregate)
        self.assertIn('needs: [select, analyze]', aggregate)
        selected = codeql_generation(self, self.source) in {'retarget-results', 'pinned-results', 'metadata-pinned-results', 'scheduling-pinned-results', 'boolean-scheduling-pinned-results', 'required-context-pinned-results', 'native-upload-pinned-results'}
        job = workflow_data(self.source)['jobs']['codeql-checks']
        canonical = codeql_generation(self,self.source) in {'required-context-pinned-results','native-upload-pinned-results'}
        self.assertEqual(job['if'], "always() && (needs.select.result != 'success' || needs.select.outputs.metadata_only != 'true')"
                         if selected and not canonical else 'always()')
        self.assertEqual(job['name'], "${{ needs.select.result == 'success' && needs.select.outputs.metadata_only == 'true' && "
                         "'codeql-security-results (metadata unchanged)' || 'codeql-security-results' }}"
                         if selected and not canonical else 'codeql-security-results')
        steps = workflow_data(self.source)['jobs']['codeql-checks']['steps']
        script = next(step['run'] for step in steps if step['name'] == 'Require every selected analysis')
        for selected in ('success', 'failure', 'cancelled', 'skipped'):
            for scan in ('true', 'false', ''):
                for analysis in ('success', 'failure', 'cancelled', 'skipped'):
                    env = dict(os.environ, SELECT_RESULT=selected, SCAN=scan, ANALYZE_RESULT=analysis)
                    result = subprocess.run(['bash', '-c', script], env=env, capture_output=True)
                    expected = selected == 'success' and (scan, analysis) in {
                        ('true', 'success'), ('false', 'skipped')}
                    self.assertEqual(result.returncode == 0, expected, (selected, scan, analysis))


    def test_selected_results_are_independent_and_cannot_bypass_the_truth_table(self):
        if codeql_generation(self, self.source) not in {'results', 'retarget-results', 'pinned-results', 'metadata-pinned-results', 'scheduling-pinned-results', 'boolean-scheduling-pinned-results', 'required-context-pinned-results', 'native-upload-pinned-results'}:
            self.skipTest("Selected-result generation is covered by its staged workflow contracts")
        workflow = workflow_data(self.source)
        job = workflow['jobs']['codeql-checks']
        permissions={'contents':'read','actions':'read','pull-requests':'read','security-events':'read'}
        canonical=codeql_generation(self,self.source) in {'required-context-pinned-results','native-upload-pinned-results'}
        if canonical:permissions['checks']='read'
        self.assertEqual(job['permissions'],permissions)
        steps = job['steps']
        self.assertEqual(steps[0]['name'],'Require a successful independent selector' if canonical else 'Require every selected analysis')
        if canonical:
            self.assertEqual(steps[0]['run'],'test "$SELECT_RESULT" = success')
            self.assertEqual(steps[0]['env']['SELECT_RESULT'],'${{ needs.select.result }}')
        trusted = next(step for step in steps if step['name'] == 'Check out trusted selected-result policy')
        self.assertEqual(trusted['with']['ref'], '${{ github.event.repository.default_branch }}')
        self.assertEqual(trusted['with']['path'], 'trusted')
        candidate = next(step for step in steps if step['name'] == 'Read the exact candidate for independent result selection')
        self.assertEqual(candidate['with']['ref'], '${{ github.sha }}')
        verify = steps[-1]
        self.assertEqual(verify['name'], 'Require current selected-language security results')
        self.assertIn('trusted/tools/repository-checks/codeql_results.py', verify['run'])
        for flag in ('--root candidate', '--event-file "$GITHUB_EVENT_PATH"'):
            self.assertIn(flag, verify['run'])
        self.assertEqual(verify['env']['GH_TOKEN'], '${{ github.token }}')
        self.assertEqual(verify['env']['CODEQL_EXPECTED_LANGUAGES'], '${{ needs.select.outputs.languages }}')
        self.assertNotIn('continue-on-error:', self.source)
        # The named required context must also exist for documentation-only PRs.
        triggers = workflow.get('on', workflow.get(True))
        self.assertNotIn('paths-ignore', triggers['pull_request'])
        self.assertEqual(triggers['push']['paths-ignore'], ['**/*.md'])
        expected = {'main', 'apple-main', 'apple-ios', 'android-main', 'android-phone', 'android-vr', 'android-vr-pico'}
        self.assertEqual(set(triggers['push']['branches']), expected)
        self.assertEqual(set(triggers['pull_request']['branches']), expected)


@unittest.skipIf(
    CODEQL_WORKFLOW.read_text() == (ROOT / "tools/repository-checks/workflows/codeql-results.yml").read_text(),
    "The identical deployed generation is already covered by the active workflow contracts",
)
class SelectedCodeQLResultWorkflowContracts(CodeQLWorkflowContracts):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "tools/repository-checks/workflows/codeql-results.yml").read_text()


class RetargetCodeQLResultWorkflowContracts(CodeQLWorkflowContracts):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'tools/repository-checks/workflows/metadata-edits/codeql.yml').read_text()

    def test_retarget_and_metadata_route_preserve_existing_analysis_and_security_assertions(self):
        previous = workflow_data((ROOT / 'tools/repository-checks/workflows/codeql-results.yml').read_text())
        successor = workflow_data(self.source)
        triggers = successor.get('on', successor.get(True))
        self.assertEqual(triggers['pull_request']['types'], ['opened', 'reopened', 'synchronize', 'edited'])
        ordinary = workflow_data((ROOT / 'tools/repository-checks/workflows/codeql-results.yml').read_text())
        normal_triggers = ordinary.get('on', ordinary.get(True))
        self.assertEqual({k: v for k, v in triggers['pull_request'].items() if k != 'types'}, normal_triggers['pull_request'])
        self.assertEqual(triggers['push'], normal_triggers['push'])
        self.assertEqual(triggers['schedule'], normal_triggers['schedule'])
        suffix = "-${{ github.event.action == 'edited' && !github.event.changes.base && " \
                 "(github.event.changes.title || github.event.changes.body) && github.run_id || 'qualification' }}"
        self.assertTrue(successor['concurrency']['group'].endswith(suffix))
        self.assertIs(successor['concurrency']['cancel-in-progress'], True)
        self.assertEqual(successor['permissions'], previous['permissions'])
        for name in ('analyze', 'codeql-checks'):
            future, old = dict(successor['jobs'][name]), dict(previous['jobs'][name])
            for key in ('name', 'if'): future.pop(key); old.pop(key)
            self.assertEqual(future, old, 'all actual analysis and security-verification steps must remain unchanged')
        select = successor['jobs']['select']
        self.assertEqual(select['outputs']['metadata_only'], '${{ steps.event.outputs.metadata_only }}')
        classifier = next(step for step in select['steps'] if step.get('id') == 'event')
        self.assertIn('trusted/tools/repository-checks/check.py metadata-event', classifier['run'])
        candidate = next(step for step in select['steps'] if step['name'] == 'Read the exact candidate inventory')
        plan = next(step for step in select['steps'] if step.get('id') == 'plan')
        self.assertLess(select['steps'].index(classifier), select['steps'].index(candidate))
        for step in (candidate, plan): self.assertEqual(step['if'], "steps.event.outputs.metadata_only != 'true'")
        self.assertEqual(plan['env']['BASE_SHA'], '${{ github.event.pull_request.base.sha || github.event.before || github.sha }}')
        self.assertEqual(plan['env']['CANDIDATE_SHA'], '${{ github.sha }}')

class PinnedCodeQLResultWorkflowContracts(CodeQLWorkflowContracts):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'tools/repository-checks/workflows/metadata-edits/codeql-pinned.yml').read_text()

    def test_pinned_successor_changes_only_tool_selection_and_required_version_check(self):
        previous = workflow_data((ROOT / 'tools/repository-checks/workflows/metadata-edits/codeql.yml').read_text())
        successor = workflow_data(self.source)
        steps = previous['jobs']['analyze']['steps']
        initialize = next(step for step in steps if step['name'] == 'Initialize CodeQL')
        initialize['id'] = 'init'
        initialize['with']['tools'] = ('https://github.com/github/codeql-action/releases/download/'
                                      'codeql-bundle-v2.27.2/codeql-bundle-linux64.tar.zst')
        version = {'name': 'Require reviewed CodeQL extractor version',
                   'env': {'CODEQL_VERSION': '${{ steps.init.outputs.codeql-version }}'},
                   'run': 'set -euo pipefail\ntest "$CODEQL_VERSION" = 2.27.2\n'}
        index = next(i for i, step in enumerate(steps) if step['name'] == 'Analyze')
        steps.insert(index, version)
        self.assertEqual(successor, previous)
        # Use the action's URL/toolcache path, without a separate downloader or
        # local archive that would force extraction on every matching cache hit.
        for value, expected in (('2.27.2', True), ('', False), ('2.27.3', False), ('2.27.2-extra', False)):
            result = subprocess.run(['bash', '-c', version['run']],
                                    env=dict(os.environ, CODEQL_VERSION=value), capture_output=True)
            self.assertEqual(result.returncode == 0, expected)


class HistoricalMetadataCodeQLResultWorkflowContracts(CodeQLWorkflowContracts):
    @classmethod
    def setUpClass(cls):
        cls.source = historical_metadata_codeql()


class SchedulingCodeQLResultWorkflowContracts(CodeQLWorkflowContracts):
    @classmethod
    def setUpClass(cls):
        cls.source = original_default_workflow('codeql').decode()


class BooleanSchedulingCodeQLResultWorkflowContracts(CodeQLWorkflowContracts):
    @classmethod
    def setUpClass(cls):
        cls.source = boolean_workflow('codeql').decode()


class NativeUploadCodeQLResultWorkflowContracts(CodeQLWorkflowContracts):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'tools/repository-checks/workflows/metadata-edits/codeql-upload-provenance.yml').read_text()


class RequiredContextCodeQLResultWorkflowContracts(CodeQLWorkflowContracts):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml').read_text()

    def test_metadata_success_executes_only_the_native_original_result_verifier(self):
        job=workflow_data(self.source)['jobs']['codeql-checks']
        self.assertEqual(job['name'],'codeql-security-results')
        self.assertEqual(job['if'],'always()')
        self.assertIn('100',job['timeout-minutes'])
        mirror=next(step for step in job['steps'] if '--result' in step.get('run',''))
        self.assertEqual(mirror['if'],"needs.select.result == 'success' && needs.select.outputs.metadata_only == 'true'")
        trusted=next(step for step in job['steps'] if step['name']=='Check out trusted selected-result policy')
        self.assertEqual(trusted['with']['sparse-checkout'].splitlines(),
                         ['tools/repository-checks','tools/test-evidence'])
        for name in ('Require every selected analysis','Read the exact candidate for independent result selection',
                     'Require current selected-language security results'):
            step=next(step for step in job['steps'] if step['name']==name)
            self.assertEqual(step['if'],"needs.select.outputs.metadata_only != 'true'")


class BranchGovernanceWorkflowContracts(unittest.TestCase):
    def test_policy_is_a_native_read_only_pull_request_check(self):
        source = BRANCH_POLICY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pull_request:", source)
        self.assertNotIn("pull_request_target:", source)
        self.assertIn("ref: ${{ github.event.repository.default_branch }}", source)
        self.assertIn("persist-credentials: false", source)
        self.assertRegex(
            source,
            r"(?m)^permissions:\n  contents: read\n  pull-requests: read$",
        )
        self.assertIn("name: branch-policy", source)
        self.assertIn("github.event.pull_request.head.sha", source)
        self.assertIn("github.event.pull_request.head.repo.id", source)
        self.assertIn("github.event.pull_request.base.repo.id", source)
        self.assertIn("github.event.pull_request.user.login", source)
        self.assertIn("github.event.pull_request.user.type", source)
        self.assertIn("github.event.repository.id", source)
        self.assertNotIn("check-runs", source)
        self.assertNotRegex(source, r"(?m)^\s*(checks|pull-requests|contents): write$")

    def test_policy_never_executes_pull_request_policy_or_workflow_changes(self):
        source = BRANCH_POLICY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Check out trusted policy", source)
        self.assertIn("github.event.repository.default_branch", source)
        checkout = source.split("with:", 1)[1].split("- name: Validate", 1)[0]
        self.assertNotIn("github.event.pull_request.head.sha", checkout)
        self.assertIn("pulls/$PULL_REQUEST/files", source)
        self.assertIn("gh api --paginate", source)
        self.assertIn("--jq '.[].filename'", source)
        self.assertNotIn("--paginate --slurp", source)
        self.assertIn("--changed-files-stdin", source)

    def test_governance_actions_are_pinned(self):
        for workflow in (BRANCH_POLICY_WORKFLOW, BRANCH_SYNC_WORKFLOW):
            actions = ACTION_USE.findall(workflow.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(actions), 1)
            self.assertEqual([action for action in actions if not FULL_SHA_ACTION.fullmatch(action)], [])

    def test_sync_is_read_only_drift_detection(self):
        source = BRANCH_SYNC_WORKFLOW.read_text(encoding="utf-8")
        self.assertRegex(source, r"(?m)^permissions:\n  contents: read$")
        self.assertIn("tools/branch-policy/drift.py", source)
        self.assertIn("--expected-parent-sha \"$PUSH_SHA\"", source)
        self.assertIn('--expected-parent-sha "$PUSH_SHA" --observe-push', source)
        strict_tail = source.split('          else\n', 1)[1]
        self.assertNotIn('--observe-push', strict_tail)
        self.assertIn("github.event.repository.default_branch", source)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", source)
        self.assertNotIn("actions/create-github-app-token@", source)
        self.assertNotIn("BRANCH_SYNC_APP", source)
        self.assertNotIn("${{ secrets.", source)
        self.assertNotIn("gh pr", source)
        self.assertNotIn("--auto", source)
        self.assertNotIn("check-runs", source)
        self.assertIn("group: branch-synchronization-${{ github.ref_name }}", source)
        self.assertIn("cancel-in-progress: false", source)
        self.assertNotIn("Skipping $parent -> $child", source)
        self.assertNotIn("continue", source)

    def test_multiple_prs_cannot_be_selected_or_merged(self):
        source = BRANCH_SYNC_WORKFLOW.read_text(encoding="utf-8")
        for forbidden in ("gh pr list", "gh pr create", "gh pr merge", "pulls?", ".[0]"):
            self.assertNotIn(forbidden, source)

    def test_wrong_app_or_author_cannot_authorize_sync(self):
        source = BRANCH_SYNC_WORKFLOW.read_text(encoding="utf-8")
        for forbidden in ("create-github-app-token", "client-id", "private-key", "author", "login"):
            self.assertNotIn(forbidden, source)


    def test_retired_desktop_branches_have_no_workflow_routes(self):
        for path in WORKFLOW_DIRECTORY.glob("*.yml"):
            source = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                self.assertNotIn("linux-main", source)
                self.assertNotIn("windows-main", source)
        policy = json.loads((ROOT / ".github/branch-policy.json").read_text())
        self.assertEqual(policy["branches"]["main"]["children"], ["android-main", "apple-main"])
        for platform in ("linux", "windows"):
            self.assertTrue((ROOT / "tests/device/adapters/desktop_oculix" / f"{platform}.json").is_file())

    def test_sync_reuse_gate_is_trusted_terminal_and_fail_closed(self):
        source = SYNC_REUSE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pull_request_target:", source)
        self.assertNotIn("paths:", source)
        self.assertIn("timeout-minutes: 35", source)
        self.assertIn("ref: ${{ github.event.repository.default_branch }}", source)
        self.assertIn("persist-credentials: false", source)
        self.assertIn("dispatch-and-wait", source)
        self.assertIn('--gate-run-id "$GITHUB_RUN_ID"', source)
        self.assertIn('--gate-run-attempt "$GITHUB_RUN_ATTEMPT"', source)
        self.assertIn("steps.inspect.outputs.mode != 'ordinary'", source)
        self.assertNotIn("github.event.pull_request.head.sha }}\n          path:", source)
        self.assertNotIn("${{ secrets.", source)

    def test_candidate_execution_is_isolated_read_only(self):
        import yaml
        source = SYNC_VALIDATION_WORKFLOW.read_text(encoding="utf-8")
        workflow = yaml.safe_load(source)
        selected_sync_recipe()  # Also checks the complete deployed tuple.
        permissions = {'actions': 'read', 'contents': 'read', 'pull-requests': 'read'}
        staged = ROOT / 'tools/repository-checks/workflows/sync-ci-selection.yml'
        if source == staged.read_text(): permissions['checks'] = 'read'
        self.assertEqual(workflow['permissions'], permissions)
        if sync_callback_blob(source) in {'ccc75d37c4f8b5012299bf864bf48dd45ead389b', '747bd6424d1e9b533ae35a81b524ceefc06b286b'}:
            assert_sync_callback_roles(self, source)
        else:
            self.assertNotRegex(source, r"(?m)^\s+[a-z-]+: write$")
        self.assertNotIn("secrets.", source)
        steps = workflow['jobs']['validate']['steps']
        checkouts = [step['with'] for step in steps if step.get('uses', '').startswith('actions/checkout@')]
        self.assertEqual([(step['path'], step['ref'], step['persist-credentials']) for step in checkouts],
                         [('trusted', 'main', False), ('candidate', '${{ inputs.expected_merge_sha }}', False)])
        staged = ROOT / 'tools/repository-checks/workflows/sync-ci-selection.yml'
        if selected_sync_recipe():
            spec = importlib.util.spec_from_file_location(
                'sync_workflow_packages', ROOT / 'tools/repository-checks/package_checks.py')
            packages = importlib.util.module_from_spec(spec); spec.loader.exec_module(packages)
            self.assertIn(reviewed_package_generation(),SELECTED_SYNC_GENERATIONS)
            self.assertIn("steps.select.outputs.full_host == 'true'", source)
            self.assertIn('--expected-selection "$EXPECTED_SELECTION"', source)
        else:
            self.assertIn("inputs.mode == 'fallback'", source)
        self.assertIn('GH_TOKEN: ""', source)
        self.assertIn('GITHUB_TOKEN: ""', source)
        self.assertNotIn('candidate/tests/run-project-tests.py', source)
        self.assertNotIn('python tests/run-project-tests.py', source)
        for step in steps:
            if 'trusted/tools/test-evidence/validate-sync.py' in step.get('run', ''):
                self.assertNotEqual(step.get('working-directory'), 'candidate')
                self.assertIn('--candidate candidate', step['run'])
                for field in ('base-sha', 'head-sha', 'merge-sha'):
                    self.assertIn('--' + field, step['run'])
                self.assertIn('--receipt build/test-results/sync-validation.json', step['run'])

    def test_sync_reuse_has_no_readiness_rerun_or_postvalidation_cancellation(self):
        import yaml
        source = SYNC_REUSE_WORKFLOW.read_text(encoding="utf-8")
        workflow = yaml.safe_load(source)
        triggers = workflow.get('on', workflow.get(True))
        self.assertEqual(triggers['pull_request_target']['types'], ['opened', 'reopened', 'synchronize', 'edited'])
        self.assertNotIn('cancel-redundant', source)
        self.assertNotIn('--window', source)
        self.assertEqual(source.count('gate.py dispatch-and-wait'), 1)
        self.assertTrue(workflow['concurrency']['cancel-in-progress'])

    def test_staged_sync_selects_before_setup_and_binds_actual_execution(self):
        staged = ROOT / 'tools/repository-checks/workflows/sync-ci-selection.yml'
        source = staged.read_text()
        workflow = workflow_data(source)
        self.assertEqual(workflow['permissions'], {'actions': 'read', 'checks': 'read', 'contents': 'read', 'pull-requests': 'read'})
        self.assertEqual(set(workflow_events(source)), {'workflow_dispatch'})
        steps = workflow['jobs']['validate']['steps']
        selected = next(step for step in steps if step.get('id') == 'select')
        self.assertIn('--select-only --output "$GITHUB_OUTPUT"', selected['run'])
        self.assertIn('python3 -B trusted/tools/test-evidence/validate-sync.py', selected['run'])
        candidate = next(step for step in steps if step.get('with', {}).get('path') == 'candidate')
        self.assertEqual(candidate['with']['fetch-depth'], 2)
        self.assertFalse(candidate['with']['persist-credentials'])
        self.assertLess(steps.index(candidate), steps.index(selected))
        old = workflow_data((ROOT / 'tools/repository-checks/workflows/packages/sync-validation.yml').read_text())
        old_steps = {step['name']: step for step in old['jobs']['validate']['steps']}
        for name in ('Set up candidate Python', 'Set up candidate Node.js', 'Set up candidate Java',
                     'Install candidate host prerequisites', 'Prepare isolated shared and product Python validators'):
            actual = next(step for step in steps if step['name'] == name)
            self.assertLess(steps.index(selected), steps.index(actual))
            previous, current = dict(old_steps[name]), dict(actual)
            previous.pop('if'); current.pop('if')
            self.assertEqual(previous, current)
            self.assertIn("&& !(steps.select.outputs.lane == 'verified-empty' && steps.select.outputs.consumer_setup == 'none' && steps.select.outputs.empty_setup != '')", actual['if'])
        for name in ('Set up candidate Java', 'Install candidate host prerequisites'):
            self.assertEqual(next(step for step in steps if step['name'] == name)['if'],
                             "(steps.select.outputs.consumer_setup != 'none' || steps.select.outputs.native_setup == '') && steps.select.outputs.full_host == 'true' && !(steps.select.outputs.lane == 'verified-empty' && steps.select.outputs.consumer_setup == 'none' && steps.select.outputs.empty_setup != '')")
        executions = [step for step in steps if 'trusted/tools/test-evidence/validate-sync.py' in step.get('run', '')
                      and step.get('id') != 'select']
        self.assertEqual(len(executions), 3)
        self.assertEqual({step['name'] for step in executions}, {
            'Verify bounded synchronization without product setup',
            'Verify exact candidate suites and complete runtime identity',
            'Validate the exact unchanged synchronization without test execution'})
        for step in executions:
            self.assertIn('--expected-selection "$EXPECTED_SELECTION"', step['run'])
            self.assertEqual(step['env']['EXPECTED_SELECTION'], '${{ steps.select.outputs.selection }}')
            if step['name'] == 'Validate the exact unchanged synchronization without test execution':
                self.assertEqual(step['if'], "steps.select.outputs.lane == 'verified-empty'")
                self.assertEqual(step['env']['EXPECTED_EMPTY_SETUP'], '${{ steps.select.outputs.empty_setup }}')
                self.assertTrue(step['run'].startswith('python3 -B '))
                self.assertIn('--expected-empty-setup "$EXPECTED_EMPTY_SETUP"', step['run'])
                self.assertNotIn('--expected-native-setup', step['run'])
                self.assertNotIn('SYNC_VALIDATOR_PYTHON', step['env'])
            elif step['name'] == 'Verify exact candidate suites and complete runtime identity':
                self.assertIn("steps.select.outputs.lane != 'verified-empty'", step['if'])
                self.assertEqual(step['env']['EXPECTED_NATIVE_SETUP'], '${{ steps.select.outputs.native_setup }}')
                self.assertIn('--expected-native-setup "$EXPECTED_NATIVE_SETUP"', step['run'])
        self.assertNotIn('candidate/tests/run-project-tests.py', source)

    def test_selected_sync_contract_rejects_foreign_mode_and_alias_recipes(self):
        # A legitimate historical selected recipe remains valid when a newer
        # canonical recipe is merely staged. Neither hash nor mode is inferred
        # from a scheduling atom or a mutable file of the same name.
        self.assertIn(reviewed_package_generation(), SELECTED_SYNC_GENERATIONS)
        self.assertTrue(selected_sync_recipe())
        raw = SYNC_VALIDATION_WORKFLOW.read_bytes()
        with tempfile.TemporaryDirectory(prefix='overte-sync-contract-') as directory:
            candidate = Path(directory) / 'sync-validation.yml'
            for change in ('foreign', 'mode', 'alias'):
                if candidate.exists() or candidate.is_symlink(): candidate.unlink()
                candidate.write_bytes(raw + (b'\n# foreign source\n' if change == 'foreign' else b''))
                candidate.chmod(0o644)
                if change == 'mode': candidate.chmod(0o755)
                elif change == 'alias': candidate.unlink(); candidate.symlink_to(SYNC_VALIDATION_WORKFLOW)
                with self.subTest(change=change), mock.patch.object(
                        sys.modules[__name__], 'SYNC_VALIDATION_WORKFLOW', candidate), self.assertRaises(AssertionError):
                    sync_condition('legacy', 'selected')

    def test_staged_sync_has_one_exact_complete_generation(self):
        spec = importlib.util.spec_from_file_location(
            'staged_sync_packages', ROOT / 'tools/repository-checks/package_checks.py')
        packages = importlib.util.module_from_spec(spec); spec.loader.exec_module(packages)
        packages, tree = prospective_package_tree()
        self.assertEqual(packages.validate_tree_wiring(tree), prospective_package_generation(packages))
        self.assertIn('protected-producer-original-default-v1', SELECTED_SYNC_GENERATIONS)
        self.assertIn(reviewed_package_generation(), SELECTED_SYNC_GENERATIONS)
        deployed = next(row for row in packages.workflow_generations()
                        if row['name'] == reviewed_package_generation())['workflows']
        self.assertEqual(packages.validate_tree_wiring(deployed), reviewed_package_generation())
        if deployed['.github/workflows/sync-validation.yml'] != tree['.github/workflows/sync-validation.yml']:
            mixed = {path: dict(entry) for path, entry in deployed.items()}
            mixed['.github/workflows/sync-validation.yml'] = dict(tree['.github/workflows/sync-validation.yml'])
            with self.assertRaises(ValueError): packages.validate_tree_wiring(mixed)
        for relative in tree:
            changed = {path: dict(entry) for path, entry in tree.items()}
            changed[relative]['sha'] = '0' * 40
            with self.subTest(path=relative), self.assertRaises(ValueError):
                packages.validate_tree_wiring(changed)

    def test_verified_empty_sync_conditions_require_the_complete_installed_generation(self):
        packages, future = prospective_package_tree()
        generation = reviewed_package_generation()
        deployed = next(row['workflows'] for row in packages.workflow_generations()
                        if row['name'] == generation)
        self.assertEqual(packages.validate_tree_wiring(deployed), generation)
        product = "steps.select.outputs.lane != 'legacy-bounded'"
        setup = "steps.select.outputs.full_host == 'true'"
        if generation in ORIGINAL_DEFAULT_GENERATIONS:
            expected={path:dict(entry) for path,entry in future.items()}
            if generation in {'protected-producer-optional-leaf-common-v1',
                    'protected-producer-exact-parent-command-owners-v1'}:
                project=ROOT/'tools/repository-checks/workflows/producers/protected-project-tests-optional-leaf.yml'
                self.assertTrue(project.is_file() and not project.is_symlink())
                self.assertIn(project.stat().st_mode & 0o777,(0o444,0o644))
                raw=project.read_bytes()
                expected['.github/workflows/project-tests.yml']={'mode':'100644','type':'blob',
                    'sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
            if generation=='protected-producer-exact-parent-command-owners-v1':
                repository=ROOT/'tools/repository-checks/workflows/producers/repository-checks-parent-owners.yml'
                self.assertTrue(repository.is_file() and not repository.is_symlink())
                self.assertIn(repository.stat().st_mode & 0o777,(0o444,0o644))
                raw=repository.read_bytes()
                expected['.github/workflows/repository-checks.yml']={'mode':'100644','type':'blob',
                    'sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
            if generation=='protected-producer-original-default-v1':
                expected['.github/workflows/repository-checks.yml']={'mode':'100644','type':'blob',
                    'sha':'81bcf1933edc435826e2de411a777cccd4dec7c7'}
            elif generation=='protected-producer-original-default-boolean-v1':
                expected['.github/workflows/repository-checks.yml']={'mode':'100644','type':'blob',
                    'sha':'15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a'}
            self.assertEqual(deployed, expected)
            self.assertEqual(SYNC_VALIDATION_WORKFLOW.read_bytes(),
                (ROOT / 'tools/repository-checks/workflows/sync-ci-selection.yml').read_bytes())
            product += " && steps.select.outputs.lane != 'verified-empty'"
            setup = "(steps.select.outputs.consumer_setup != 'none' || steps.select.outputs.native_setup == '') && " + setup
            setup += " && !(steps.select.outputs.lane == 'verified-empty' && steps.select.outputs.consumer_setup == 'none' && steps.select.outputs.empty_setup != '')"
        else:
            self.assertNotEqual(deployed['.github/workflows/sync-validation.yml'],
                                future['.github/workflows/sync-validation.yml'])
        self.assertEqual(sync_condition('legacy-product', "steps.select.outputs.lane != 'legacy-bounded'"), product)
        self.assertEqual(sync_condition('legacy-setup', "steps.select.outputs.full_host == 'true'", setup=True), setup)
        self.assertEqual(sync_condition('legacy-bounded', "steps.select.outputs.lane == 'legacy-bounded'"),
                         "steps.select.outputs.lane == 'legacy-bounded'")
        # A scheduling suffix grants no recipe authority: every future endpoint
        # remains mandatory with its complete ordinary mode/type/hash identity.
        for relative in future:
            for change in ('foreign', 'mode', 'alias', 'missing'):
                changed = {path: dict(entry) for path, entry in future.items()}
                if change == 'foreign': changed[relative]['sha'] = '0' * 40
                elif change == 'mode': changed[relative]['mode'] = '100755'
                elif change == 'alias': changed[relative]['mode'] = '120000'
                else: del changed[relative]
                with self.subTest(path=relative, change=change), self.assertRaises(ValueError):
                    packages.validate_tree_wiring(changed)

    def test_qualification_is_exact_push_only_and_bounded(self):
        source = PARENT_QUALIFICATION_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("push:", source)
        self.assertNotIn("pull_request:", source)
        self.assertNotIn("workflow_dispatch:", source)
        self.assertEqual(workflow_events(source)['push']['branches'], ['main', 'android-main', 'android-vr', 'apple-main'])
        self.assertIn("ref: ${{ github.sha }}", source)
        self.assertIn("cancel-in-progress: false", source)
        self.assertIn("retention-days: 4", source)

    def test_reused_shared_qualification_still_runs_product_suites(self):
        import yaml
        source = SYNC_VALIDATION_WORKFLOW.read_text(encoding="utf-8")
        steps = yaml.safe_load(source)['jobs']['validate']['steps']
        product = next(step for step in steps if step.get('name') == 'Verify exact candidate suites and complete runtime identity')
        self.assertEqual(product['if'], sync_condition(
            "inputs.mode == 'fallback' || (inputs.profile != 'documentation' && inputs.profile != 'tool-dependencies')", "steps.select.outputs.lane != 'legacy-bounded'"))
        self.assertIn('--mode "$MODE" --profile "$PROFILE"', product['run'])
        self.assertEqual(product['env']['MODE'], '${{ inputs.mode }}')
        # The trusted consumer, rather than a mutable candidate runner, owns
        # execution of all declared product suites on reuse and fallback alike.
        consumer = ast.parse((ROOT / 'tools/test-evidence/validate-sync.py').read_text())
        executions = [node for node in ast.walk(consumer) if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                      and (node.func.value.id, node.func.attr) == ('execution', 'execute')]
        self.assertEqual(len(executions), 1)
        self.assertTrue(next(item.value for item in executions[0].keywords if item.arg == 'include_platform').value)

    def test_project_workflow_is_reusable_with_single_caller_routing(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_call:", source)
        self.assertNotIn("run_full", source)
        self.assertIn("needs: route", source)
        self.assertIn('--event "$GITHUB_EVENT_PATH"', source)
        self.assertNotIn("pull_request:", source)
        aggregate = (WORKFLOW_DIRECTORY / "repository-checks.yml").read_text()
        assert_project_caller_routing(self, aggregate)
        pull_request = aggregate.split("  pull_request:", 1)[1].split("  workflow_dispatch:", 1)[0]
        self.assertNotIn("paths", pull_request)
        self.assertIn("edited", pull_request)


class RulesetManifestContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifests = {
            name: json.loads((RULESETS / filename).read_text(encoding="utf-8"))
            for name, filename in RULESET_FILES.items()
        }
        cls.manifests.update({
            name: json.loads(path.read_text(encoding="utf-8"))
            for name, path in STAGED_RULESET_FILES.items()
        })

    @staticmethod
    def rule(manifest, rule_type):
        return next(rule for rule in manifest["rules"] if rule["type"] == rule_type)

    def test_all_persistent_rulesets_are_complete_and_versioned(self):
        versioned = []
        for path in RULESETS.glob("*.json"):
            candidate = json.loads(path.read_text(encoding="utf-8"))
            if "target" in candidate:
                versioned.append(path.name)

        self.assertEqual(sorted(versioned), sorted(RULESET_FILES.values()))
        self.assertEqual(set(self.manifests), set(RULESET_FILES) | set(STAGED_RULESET_FILES))
        for name, manifest in self.manifests.items():
            self.assertEqual(manifest["name"], name)
            self.assertIn(manifest["target"], ("branch", "tag"))
            self.assertEqual(manifest["enforcement"], "active")
            self.assertEqual(manifest["bypass_actors"], [])
            self.assertEqual(manifest["conditions"]["ref_name"]["exclude"], [])
            self.assertTrue(manifest["conditions"]["ref_name"]["include"])
            self.assertTrue(manifest["rules"])

    def test_required_checks_are_strict_and_bound_to_github_actions(self):
        expected = {
            "Android target branch topology": "Enforce Android parent sync path",
            "Apple target branch topology": "Enforce apple-main sync path",
            "Permanent branch governance": "branch-policy",
            "Selected CodeQL security results on main": "codeql-security-results",
        }
        for name, context in expected.items():
            parameters = self.rule(
                self.manifests[name], "required_status_checks"
            )["parameters"]
            self.assertTrue(parameters["strict_required_status_checks_policy"])
            self.assertFalse(parameters["do_not_enforce_on_create"])
            expected_checks = [{"context": context, "integration_id": 15368}]
            if name == "Apple target branch topology":
                expected_checks.append(
                    {"context": "ios-device-build", "integration_id": 15368}
                )
            if name == "Permanent branch governance":
                expected_checks.insert(0, {"context": "dependency-release-policy", "integration_id": 15368})
                expected_checks.append(
                    {"context": "sync-test-reuse", "integration_id": 15368}
                )
                expected_checks.append(
                    {"context": "repository-checks", "integration_id": 15368}
                )
            self.assertEqual(parameters["required_status_checks"], expected_checks)
            if name == "Selected CodeQL security results on main":
                self.assertEqual(self.manifests[name]["conditions"]["ref_name"],
                                 {"include": ["refs/heads/" + branch for branch in (
                                     "main", "apple-main", "apple-ios", "android-main",
                                     "android-phone", "android-vr", "android-vr-pico")],
                                  "exclude": []})
                self.assertEqual(len(self.manifests[name]["rules"]), 1)


    def test_solo_profile_is_active_without_locking_out_the_maintainer(self):
        solo = json.loads(
            (RULESETS / "review-profiles/solo-maintainer.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(solo["required_approving_review_count"], 0)
        self.assertFalse(solo["require_last_push_approval"])
        self.assertEqual(solo["allowed_merge_methods"], ["merge"])
        for name in (
            "Android target branch topology",
            "Apple target branch topology",
            "Permanent branch governance",
        ):
            self.assertEqual(
                self.rule(self.manifests[name], "pull_request")["parameters"], solo
            )

    def test_independent_reviewer_profile_is_ready_but_not_active(self):
        independent = json.loads(
            (RULESETS / "review-profiles/independent-reviewer.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(independent["required_approving_review_count"], 1)
        self.assertTrue(independent["dismiss_stale_reviews_on_push"])
        self.assertTrue(independent["require_last_push_approval"])
        self.assertTrue(independent["required_review_thread_resolution"])
        for manifest in self.manifests.values():
            for rule in manifest["rules"]:
                if rule["type"] == "pull_request":
                    self.assertNotEqual(rule["parameters"], independent)

    def test_governed_refs_retain_deletion_and_non_fast_forward_protection(self):
        for name in (
            "Android target branch topology",
            "Apple target branch topology",
            "Immutable Android, canonical, and archive tags",
            "Immutable Pico 4 release and dependency tags",
            "Permanent branch governance",
        ):
            rule_types = {rule["type"] for rule in self.manifests[name]["rules"]}
            self.assertIn("deletion", rule_types)
            self.assertIn("non_fast_forward", rule_types)

    def test_used_release_dependency_and_archive_tag_namespaces_are_protected(self):
        protected = set()
        for name, manifest in self.manifests.items():
            if manifest["target"] == "tag":
                protected.update(manifest["conditions"]["ref_name"]["include"])
        self.assertEqual(
            protected,
            {
                "refs/tags/[0-9]*",
                "refs/tags/v[0-9]*",
                "refs/tags/android-phone-v*",
                "refs/tags/android-phone-16k-deps-v*",
                "refs/tags/archive/**",
                "refs/tags/pico4-v*-rc.*",
                "refs/tags/pico4-preview-*",
                "refs/tags/pico4-deps-v*",
            },
        )

    def test_signed_commits_are_not_required(self):
        for manifest in self.manifests.values():
            self.assertNotIn(
                "required_signatures", {rule["type"] for rule in manifest["rules"]}
            )

    def test_repository_merge_settings_match_transition_policy(self):
        settings = json.loads(
            (RULESETS / "repository-merge-settings.json").read_text(encoding="utf-8")
        )
        self.assertEqual(settings["repository"], "noah-l-frank/overte")
        self.assertEqual(
            settings["settings"],
            {
                "allow_auto_merge": False,
                "allow_merge_commit": True,
                "allow_rebase_merge": False,
                "allow_squash_merge": False,
                "allow_update_branch": False,
                "delete_branch_on_merge": False,
            },
        )


class ArchivedRefRetirementContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = RULESETS / "retirements/archived-branches.json"
        cls.plan = json.loads(cls.path.read_text(encoding="utf-8"))

    def test_temporary_ruleset_is_retired_without_bypass(self):
        retirement = self.plan["ruleset_retirement"]
        self.assertEqual(retirement["name"], "Archived branches")
        self.assertEqual(retirement["operation"], "delete_ruleset_by_freshly_resolved_id")
        self.assertEqual(retirement["expected_current"]["bypass_actors"], [])
        self.assertIn("never use a bypass", retirement["sequence"])
        self.assertFalse((RULESETS / "archived-branches.json").exists())

    def test_all_exact_archive_refs_are_unique_and_batched_4_4_4_1(self):
        refs = self.plan["archive_refs"]
        self.assertEqual(len(refs), 13)
        self.assertEqual(
            [item["disposition"] for item in refs].count("verify_existing"), 2
        )
        self.assertEqual(
            [item["disposition"] for item in refs].count("create_annotated"), 11
        )
        sources = [item["source"] for item in refs]
        tags = [item["tag"] for item in refs]
        self.assertEqual(len(sources), len(set(sources)))
        self.assertEqual(len(tags), len(set(tags)))
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", item["tip"]) for item in refs))
        self.assertTrue(all(tag.startswith("refs/tags/archive/") for tag in tags))
        batches = self.plan["deletion_batches"]
        self.assertEqual([len(batch) for batch in batches], [4, 4, 4, 1])
        self.assertEqual([source for batch in batches for source in batch], sources)

def source13_budget_recipes():
    old = {'.github/workflows/project-tests.yml': '8920a91e79c8e25c34c0afdeda610d71a625dde9', '.github/workflows/parent-qualification.yml': '6d2d342e4b63d9e60602451157d13854bd52dde7', '.github/workflows/sync-validation.yml': '55d08b65a987224ce576459cede693cfd49375f6'}
    expected = {'.github/workflows/project-tests.yml': 'e1e009f489e2bd126d0546f75977dc73c6450dda', '.github/workflows/parent-qualification.yml': '2f4aec7f6463801a6deeb443b59977273197ea60', '.github/workflows/sync-validation.yml': 'cff76b696a4afd8658329a02ab33032672f292b9'}
    sync = zlib.decompress(base64.b85decode('c-rk5YjfMU@w<Kns`Ffun}T{+q#lhs&gIm^J;!!rJ8dU*H6RE|uql!TKsmZ3{q0=<ltk)bD{01;59coyfZfGn-@E()ohve80g_23C__mc&HjP{mPX0UED#A56No00G-8S&B{Hc1{w@(WVU*nA5sR51iYGB5!Guc*znn@;Caj0fXE8-n67j$QR74izjVEaD<445fG*i-{i4ZKZ+n+yIDoNa{pv8T|fXkF9I@X&g$FaW=DxmhzN5O70E?CghOtU{DHA~@UsRWNlpL2{!60ohHbewPst0dJFWe>d<ER(Pik|^>Cy}6o`NktO!i0yc3nnlr212U<0L}4FNMnUdFpGY>8WAdeVV@86n!J9BK+U>$h%0#YzqYy%KsR_8cqLmXX7OUlk76Z=3FyE~J6wN@3F`a25Bavh&+yUl-m*#>C=28@<wimdF#FRyt#~9Qy5==_VaHVpc_=dHd60>$=E%IHy2Tupi&5dJ`#QZmFx*8D7S7L2inV-cf!_AgcZ<!OtCoIVnp71zR4DM^XW}n5=xow`l>klsa!?$mahZp_xi{aq%<fK37p;{(IE#iLdR(Um_$F<u@1SEjr7#zzWgTti@8^<}nFUO4DAh>kllKHC=kwYQ`#tOXTil|YI0SJft!9Hy@nM(+DebTABou(U*w%2OZX`|C<w)cI~t@{o11Ddv-y3<$?yyI%zTdY7LEbO5P;c;OPymQ=}GgaJYLUO4v1q%W@;3NXxz>_3fdD(y&PEo|C44n-SH{fcvpjD8n{`>jGd4G8R`bDo8Mb;d~+Q$6v)$8HK>9740i!*{}Wxk`58y1)0UiV-8vYqzasmeHS`h!>ZFtqTfGS=DU@$qobe|rhWQ9@id@Lcv8SmLJw1<4e`EK5+zQx*~)70%wjN7cQ#psMKLzvw^j>$ppBc=fSW|GbB;u2!MvPu~rC@#x*ai?7Ww8n}C<(XM`4K>+*BNOZ9GbTmdJ<)|uHn#kJTtD}q8mp=oQv(xjVi_^isYFboqP$K?p_3EeBw+IX5Xv1){8lFFY4%_yY>NDWxpd_nx=I0c&`nOY9%5OUbYYUKECtMA;QYy%HL25%77&F8tlS~mmVmb&0HlCR~jOS{og7-agnD_!;upwmegu+S4AoXLYPc%UDYog0h4A?BzKv3OC76B(v<b;Ny)vynVotdmBImG0}bsSQl#oQK?c8xD@PJii_M57CmmB27K{oB!T87i+g%79-J2fz3D_E%ig@eFJ@-k;}|no1IIcbzOTo9Zk<S#6%$vDT!M&I;%lTb*H3*J2Dd4h(>Q<$>h%^5X3BqFTaOy3z6%#wGx9$h5O1_A(4r0isyjtcJVN1xDZC;$Q~`FIOy}Shed-tvaj)S`14VYwhIQ%UA;xwfyt_W#lMbdY#2wAwT0$V8sVTQWhy$Gj*1g5(}IUlgK=lGM;V+UzTOgwM^m_cRPoql%)mfof#!AT`BC@`o^)>I#w&viAc=QpAOKIh>ZxHVL!>hX@e)|)2CH0&`?1_vkCaLVdTk{&;}VYOR+VhLwHu3`gM;INS1CGhV53P+X*^etJ{Iyme=l3uR%<B^PGLBzBRmAf_SP!kS-6a`%a@-eMk@|pm~tk?<t8GSU7C9y4`lY-Ry!eSh(+Yx?Zcrn()tSxy%i8@bA+7j+KLZj~q0)f)tt$%i!;1N*)$Ks3XKU0Z)Q-_(YfT_dn|zs2=(r3q!x|vX<NOn{K`CdZ68I!}IE%A5bq0sULPdqh8l(-}5Z!IHASyGuu`wHpxV(;MLa^p516y*HVsD&@mR?Z632Fw|tEh)@#8mNT66!(4Iq4n4lNbv~IoLfWcdsJZOO;R&whOI6Qv|2Gha$LI(&aU?8PRglFjA1&RnkGowRX7BPIQbnHO4Dqu7sdSozVE~N4)HgOydJR9j?tF*|^)0+{7?l9yd=nVW(G%<iH*R2sRa{v#bH_Z)unz9mb&Bnus%s>lr)6pG|gXFHc#)pRsoGhNSvR8Qd9rNj!K+6{yV0huJa+jO#rpFe!0Umvc!z2orh`?ZVUWqh__Ylk)(E<jn)^|+KisXg^J){9YphD-1d+BP~ZQ5JtVdLRk4-b;Y;H4=Hg4kv{R%!Q=v9f}AqF}hOnMwdfX0mpsjl7r}mR75?JCC7O5h4-bE0}!%B}nvExo?d;;Kx6h|I%t)uTGfKB88vc9KtI>csayMz&V2gg$QT|WTJ%tW$hT20fP9WM^!-vC9loH%b~&lk%%5Hf~&>)BQKcNkJh4?velCvl??kQ?~VqiCvW;Ex@F9ZYOEt-Y0hB6n4C$fAWq#OFi4P<LsF2)BoR<)>S#{YFpEJQQ^=Yy{v1LY5wSd|7wEvSM@tR#qz`prMN%x1M9tSRQ+BSjUZLU%nu0L$nn|;W^;;x{%>wwQV>1J?bTk?0<qJ_4QjzZNFzn7V4z|M*=q49su_jf^hjqFVkVZ(3`k+?q<Q)?{oS|HgYt7HRXPldi$*wz^$-(Ys(*NgK|K&v=3fTTJ{5U$zyQYoA?J}PYe|f+4M>F-!nyJTWjm*UT(Hf(<-0{-Ps(b79`MY&fxx?BK^-}CI(<P({?~4yLpm9BwUZ0+Rv+(|ye*4Fq<O^K;p|tXyyZmEML%w&Xzl4vmBq)9@HFc2|yHMq_jYM~3CZ9e-KmLfGe*0m<vn_3RW;nz|C?3Mzq2H#i=aF{1$voflL*MPNpdL_Y!`=NRX|=mSyWQ!AcBD|hZ=_%(u=@Ege>yJ24Df;>55O;0H;K}{fZ8-*{#2^}Hz=oczA*XP2FRbZrgsO2W)8kAYcmP0ix%~6m8m;ytp?q&fr@(Qj)=H4Q`cWpwKM`yc@MQK{{ur>)>r'))
    step = '- name: Install selected artifact namespace utility\n  if: steps.{select}.outputs.requires_artifact_namespace == \'true\'\n  env:\n    FULL_HOST: ${{ steps.{select}.outputs.full_host }}\n  run: |\n    set -euo pipefail\n    if ! test -x /usr/bin/bwrap; then\n      if test "$FULL_HOST" != true; then\n        sudo apt-get -o Acquire::Retries=4 update\n      fi\n      sudo apt-get -o Acquire::Retries=4 install --no-install-recommends -y bubblewrap\n    fi\n    test -x /usr/bin/bwrap\n'
    result = {}
    for path, old_oid in old.items():
        raw = sync if path.endswith('sync-validation.yml') else (ROOT / 'tools/repository-checks/workflows/host' / Path(path).name).read_bytes()
        if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() != old_oid:
            raise AssertionError('historical source13 recipes must remain immutable')
        selected_sync = path.endswith('sync-validation.yml'); indent = 6 if selected_sync else 4
        marker = ' '*indent+'- name: '+('Prepare isolated shared and product Python validators' if selected_sync else 'Prepare isolated host evidence validators')+'\n'
        utility = ''.join(' '*indent+line+'\n' for line in step.replace('{select}', 'select' if selected_sync else 'host').splitlines())
        if raw.count(marker.encode()) != 1: raise AssertionError('source23 prerequisite position differs')
        raw = raw.replace(marker.encode(), (utility+marker).encode())
        if path.endswith('project-tests.yml'):
            if raw.count(b'    timeout-minutes: 20\n') != 1: raise AssertionError('source13 budget differs')
            raw = raw.replace(b'    timeout-minutes: 20\n', b'    timeout-minutes: 30\n')
        if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() != expected[path]:
            raise AssertionError('source23 recipe requires its exact reviewed bytes')
        result[path] = raw.decode('utf-8')
    return result


def source13_budget_recipe():
    return source13_budget_recipes()['.github/workflows/project-tests.yml']


def assert_optional_leaf_recipe(case, source):
    """Successor28 retains every mandatory owner and original execution body."""
    directory=ROOT/'tools/repository-checks/workflows/producers'
    raw=source.encode();future=workflow_data(source)
    old=workflow_data((directory/'protected-project-tests-android-platform.yml').read_text())
    catalog=json.loads((ROOT/'.github/package-workflow-generations.json').read_bytes())['generations']
    case.assertEqual(len(catalog),29)
    case.assertEqual(hashlib.sha256(json.dumps(catalog[:27],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'cf4fe21e917c3b1d52b5ad34b9974d37b1f8bcc30b31a0a5f6e15d1d7c33eb5b')
    previous,row=catalog[26:28]
    case.assertEqual(row['name'],'protected-producer-optional-leaf-common-v1')
    case.assertEqual([path for path in row['workflows'] if row['workflows'][path]!=previous['workflows'][path]],
        ['.github/workflows/project-tests.yml'])
    case.assertEqual(row['workflows']['.github/workflows/project-tests.yml'],
        {'mode':'100644','type':'blob','sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()})
    case.assertEqual({key:value for key,value in future.items() if key!='jobs'},
        {key:value for key,value in old.items() if key!='jobs'})
    case.assertEqual(set(future['jobs']),set(old['jobs']))
    for name in ('tool-dependencies','package-checks','producer-publication'):
        case.assertEqual(future['jobs'][name],old['jobs'][name])
    for name in ('route','platform-tests','project-results'):
        before=old['jobs'][name];after=future['jobs'][name]
        case.assertEqual({key:value for key,value in before.items() if key!='steps'},
            {key:value for key,value in after.items() if key!='steps'})
        case.assertEqual(len(before['steps']),len(after['steps']))
        for a,b in zip(before['steps'],after['steps']):
            if a.get('id')=='protected-source':
                case.assertEqual({key:value for key,value in a.items() if key!='run'},
                    {key:value for key,value in b.items() if key!='run'})
                case.assertIn("scope['optional_leaf_import' if optional_leaf else 'authenticate']",b['run'])
            else:case.assertEqual(a,b)
    before=old['jobs']['project-tests'];after=future['jobs']['project-tests']
    case.assertEqual({key:value for key,value in before.items() if key not in {'steps','outputs'}},
        {key:value for key,value in after.items() if key not in {'steps','outputs'}})
    case.assertEqual(after['outputs'],{**before['outputs'],
        'common_unavailable':'${{ steps.optional.outputs.common_unavailable }}',
        'common_binding':'${{ steps.optional.outputs.common_binding }}'})
    steps=after['steps'];by_name={step['name']:step for step in steps}
    case.assertEqual(len(steps),len(before['steps'])+1)
    case.assertEqual([step.get('id') for step in steps[:4]],[None,'protected-source','optional',None])
    case.assertEqual(steps[3]['name'],'Check out the exact candidate without credentials')
    optional=steps[2]
    case.assertEqual(optional['if'],"github.event_name == 'push' && (github.ref == 'refs/heads/apple-ios' || github.ref == 'refs/heads/android-phone' || github.ref == 'refs/heads/android-vr-pico')")
    case.assertIn('test "$ADMITTED" = true',optional['run'])
    case.assertIn('producer_workflow.py optional-leaf-common',optional['run'])
    case.assertNotIn('--candidate',optional['run'])
    for original in before['steps']:
        changed=by_name[original['name']]
        if original.get('id')=='protected-source':continue
        case.assertEqual({key:value for key,value in original.items() if key!='if'},
            {key:value for key,value in changed.items() if key!='if'})
        if original is before['steps'][0]:case.assertNotIn('if',changed);continue
        expected="steps.optional.outputs.common_unavailable != 'true'"
        if 'if' in original:expected+=' && ('+original['if']+')'
        case.assertEqual(changed['if'],expected)


def assert_reviewed_host_selection(case, source):
    """Accept the exact reviewed successor while retaining execution authority."""
    template = ROOT / 'tools/repository-checks/workflows/host/project-tests.yml'
    owned = ROOT / 'tools/repository-checks/workflows/android-owned/project-tests.yml'
    protected = ROOT / 'tools/repository-checks/workflows/producers/protected-project-tests.yml'
    platform = protected.with_name('protected-project-tests-android-platform.yml')
    optional = protected.with_name('protected-project-tests-optional-leaf.yml')
    if source == optional.read_text(encoding='utf-8'):
        assert_optional_leaf_recipe(case,source)
        if source == WORKFLOW.read_text(encoding='utf-8'):
            case.assertIn(reviewed_package_generation(), ('protected-producer-optional-leaf-common-v1',
                'protected-producer-exact-parent-command-owners-v1'))
        return
    android_owned = source == owned.read_text(encoding='utf-8')
    platform_owner = source == platform.read_text(encoding='utf-8')
    protected_owner = source == protected.read_text(encoding='utf-8') or platform_owner
    budget_owner = source == source13_budget_recipe()
    if budget_owner:
        spec = importlib.util.spec_from_file_location(
            'budget_contract_packages', ROOT / 'tools/repository-checks/package_checks.py')
        packages = importlib.util.module_from_spec(spec); spec.loader.exec_module(packages)
        row = next(row for row in packages.workflow_generations()
                   if row['name'] == 'npm-consumers-sync-ci-budget-v1')
        raw = source.encode()
        case.assertEqual(row['workflows']['.github/workflows/project-tests.yml'],
            {'mode':'100644','type':'blob','sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()})
        if source == WORKFLOW.read_text(encoding='utf-8'):
            case.assertIn(reviewed_package_generation(), ('npm-consumers-sync-ci-budget-v1', 'npm-consumers-sync-ci-budget-cleanup-v1'))
    elif android_owned or protected_owner:
        # Historical staged templates retain their exact approved identities
        # when a newer complete generation becomes the deployed workflow.
        spec = importlib.util.spec_from_file_location(
            'host_contract_packages', ROOT / 'tools/repository-checks/package_checks.py')
        packages = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(packages)
        raw = source.encode()
        identity = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        matches = {row['name'] for row in packages.workflow_generations()
                   if row['workflows']['.github/workflows/project-tests.yml']['sha'] == identity}
        allowed = (set(ORIGINAL_DEFAULT_GENERATIONS) if platform_owner else
                   set(PROTECTED_GENERATIONS) if protected_owner else {'android-owned-npm5-sync-ci-v1'})
        case.assertTrue(matches & allowed, 'host template requires an exact reviewed Git blob')
        if source == WORKFLOW.read_text(encoding='utf-8'):
            case.assertIn(reviewed_package_generation(), matches & allowed)
    else:
        case.assertEqual(source, template.read_text(encoding='utf-8'))
    jobs = workflow_data(source)['jobs']
    host = jobs['project-tests']
    case.assertEqual(host['if'], "needs.route.outputs.package_host_mode == 'full'")
    steps = host['steps']
    trusted = next(step for step in steps if 'checkout@' in step.get('uses', '')
                   and step['with'].get('path') == 'trusted')
    candidate = next(step for step in steps if 'checkout@' in step.get('uses', '')
                     and step['with'].get('path') == 'candidate')
    case.assertEqual(trusted['with']['ref'], '${{ github.event.repository.default_branch }}')
    case.assertEqual(candidate['with']['fetch-depth'], 2)
    for step in steps:
        if 'checkout@' in step.get('uses', ''):
            case.assertIs(step['with']['persist-credentials'], False)
    selection = next(step for step in steps if step.get('id') == 'host')
    execution = next(step for step in steps if step['name'] == 'Run independently selected host contracts')
    case.assertIn('--select-only --output "$GITHUB_OUTPUT"', selection['run'])
    controller = 'android_handoff.py' if android_owned else 'host_selection.py'
    if protected_owner:
        launcher = 'build/host-tests-env/bin/python -B trusted/tools/repository-checks/'
        case.assertIn(launcher + controller, execution['run'])
    else:
        case.assertIn('build/host-tests-env/bin/python trusted/tools/repository-checks/' + controller, execution['run'])
    for step in (selection, execution):
        case.assertIn('--candidate candidate', step['run'])
        if not android_owned:
            case.assertIn('--event "$GITHUB_EVENT_PATH" --sha "$GITHUB_SHA"', step['run'])
            case.assertIn('--expected-plan "$EXPECTED_PLAN"', step['run'])
        else:
            case.assertIn('trusted/tools/repository-checks/android_handoff.py', step['run'])
        case.assertEqual(step['env']['EXPECTED_PLAN'], '${{ needs.route.outputs.package_plan }}')
    if android_owned:
        controller_source = (ROOT / 'tools/repository-checks/android_handoff.py').read_text()
        controller_tree = ast.parse(controller_source)
        main = next(node for node in controller_tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
        calls = [node for node in ast.walk(main) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id in {'selected_host', 'project'}]
        case.assertEqual({node.func.id for node in calls}, {'selected_host', 'project'})
        for call in calls:
            case.assertEqual(ast.unparse(call.args[2]), "os.environ.get('GITHUB_SHA')")
            case.assertEqual(ast.unparse(call.args[3]), "os.environ.get('GITHUB_EVENT_NAME')")
            expected = next(item.value for item in call.keywords if item.arg == 'expected_plan')
            case.assertEqual(ast.unparse(expected), "os.environ.get('EXPECTED_PLAN')")
        case.assertIn('event = json.loads(Path(event_path).read_text())', controller_source)
        case.assertIn('event_path = os.environ.get("GITHUB_EVENT_PATH")', controller_source)
        case.assertIn('--receipt build/test-results/owned-project-execution.json', execution['run'])
    qt = next(step for step in steps if step['name'] == 'Install QML and portable C++ contract prerequisites')
    case.assertEqual(qt['if'], "steps.host.outputs.full_host == 'true'")
    if protected_owner:
        case.assertEqual(execution['if'], "steps.protected.outputs.protected_executed != 'true'")
        protected_step = next(step for step in steps
                              if step['name'] == 'Execute the selected protected shared owner')
        case.assertEqual(protected_step['if'], "needs.route.outputs.protected_full == 'true' && steps.protected-source.outputs.admitted == 'true'")
        case.assertIn('producer_workflow.py" shared', protected_step['run'])
        case.assertEqual(jobs['producer-publication']['name'],
                         'Publish final producer ${{ needs.project-tests.outputs.receipt_sha256 }}')
    runs = '\n'.join(step.get('run', '') for step in steps)
    case.assertIn('-r candidate/tests/requirements-host.txt', runs)
    case.assertNotIn('python candidate/tests/run-project-tests.py', runs)
    final = jobs['project-results']
    case.assertEqual(final['if'], 'always()')
    case.assertIn('project-tests', final['needs'])
    verify = final['steps'][-1]
    case.assertEqual(verify['env']['CHECK_RESULTS'], '${{ toJSON(needs) }}')
    if platform_owner:
        case.assertIn('platform-tests', final['needs'])
        case.assertEqual(jobs['platform-tests']['needs'], 'route')
        case.assertEqual(jobs['platform-tests']['if'], "needs.route.outputs.platform_required == 'true'")
        case.assertIn('trusted/tools/test-evidence/producer_workflow.py project-verify', verify['run'])
        case.assertIn('producer_workflow.py fallback-common', execution['run'])
        case.assertEqual(execution['env']['PLATFORM_REQUIRED'], '${{ needs.route.outputs.platform_required }}')
    else:
        case.assertIn('trusted/tools/repository-checks/package_checks.py verify', verify['run'])


class OptionalLeafCommonWorkflowContracts(unittest.TestCase):
    def test_exact_successor_preserves_all_original_owners_and_precedes_common_candidate_setup(self):
        source=(ROOT/'tools/repository-checks/workflows/producers/protected-project-tests-optional-leaf.yml').read_text()
        assert_optional_leaf_recipe(self,source)

    def test_catalog_enrollment_alone_keeps_active27_and_unknown_or_mixed_tuple_rejected(self):
        from copy import deepcopy
        packages,_=prospective_package_tree()
        rows=packages.workflow_generations()
        self.assertIn(packages.validate_wiring(ROOT),{'protected-producer-optional-parent-source-v1',
            'protected-producer-optional-leaf-common-v1', 'protected-producer-exact-parent-command-owners-v1'})
        self.assertEqual(packages.validate_tree_wiring(rows[27]['workflows']),'protected-producer-optional-leaf-common-v1')
        for change in ('missing','mode','unknown','mixed-parent'):
            tree=deepcopy(rows[27]['workflows'])
            path='.github/workflows/project-tests.yml'
            if change=='missing':del tree[path]
            elif change=='mode':tree[path]['mode']='100755'
            elif change=='unknown':tree[path]['sha']='f'*40
            else:tree['.github/workflows/parent-qualification.yml']=deepcopy(rows[25]['workflows']['.github/workflows/parent-qualification.yml'])
            with self.subTest(change=change),self.assertRaises(ValueError):packages.validate_tree_wiring(tree)
        extra=deepcopy(rows[-1]);extra['name']='unreviewed-successor30'
        extra['workflows']['.github/workflows/project-tests.yml']['sha']='f'*40
        raw=json.dumps({'schema':1,'repository':{'full_name':packages.REPOSITORY,'id':packages.REPOSITORY_ID},
            'generations':[*rows,extra]}).encode()
        with mock.patch.object(packages,'_trusted_bytes',return_value=raw),self.assertRaises(ValueError):packages.workflow_generations()

    def test_successor28_keeps_the_existing_parent_source_denied_zero_setup_path(self):
        packages,_=prospective_package_tree()
        rows=packages.workflow_generations()
        path='.github/workflows/parent-qualification.yml'
        self.assertEqual(rows[27]['workflows'][path],rows[26]['workflows'][path])
        raw=PARENT_QUALIFICATION_WORKFLOW.read_bytes()
        self.assertEqual(rows[27]['workflows'][path],{'mode':'100644','type':'blob',
            'sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()})
        old=OptionalParentSourceDeclineContracts();old.setUp()
        needs=old.needs();needs['common-parent']['outputs']['source_admitted']='false'
        result,values=old.decision(needs,'false')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(values,{'available':'false'})
        report=json.loads(result.stdout)
        self.assertEqual(report['executed_suites'],[])
        self.assertFalse(report['qualification'] or report['reusable'] or report['new_E'])
        old.test_every_candidate_and_execution_step_requires_its_admitted_source()


class ProjectWorkflowContracts(unittest.TestCase):
    def test_issue_intake_has_one_required_central_pull_request_owner(self):
        issue = workflow_data((WORKFLOW_DIRECTORY / 'issue-intake.yml').read_text())
        self.assertEqual(set(issue.get('on', issue.get(True))),
                         {'issues', 'milestone', 'schedule', 'workflow_dispatch'})
        self.assertEqual(set(issue['jobs']), {'reconcile'})
        self.assertEqual(issue['permissions'], {'contents': 'read'})
        self.assertEqual(issue['jobs']['reconcile']['if'],
                         "github.repository == 'noah-l-frank/overte' && github.event_name != 'pull_request'")
        self.assertEqual(issue['jobs']['reconcile']['permissions'],
                         {'contents': 'read', 'issues': 'write'})
        registry = json.loads((ROOT / '.github/test-suites.json').read_text())
        owner = registry['suites']['issue-intake']
        self.assertEqual(owner['command'], ['python', 'tests/issue-intake-test.py'])
        self.assertEqual(owner['layer'], 'quick')
        ci37 = json.loads((ROOT / '.github/ci37-runtime.json').read_text())
        self.assertEqual(ci37['suites'].count('issue-intake'), 1)
        dependencies = json.loads((ROOT / '.github/test-suite-dependencies.json').read_text())
        self.assertEqual(dependencies['suites']['issue-intake']['kind'], 'repository')
        catalog = json.loads((ROOT / '.github/package-workflow-generations.json').read_text())
        generations = {row['name']: row['workflows'] for row in catalog['generations']}
        for generation, caller_path, project_path in (
                ('npm-consumers-sync-ci-v1', 'npm-consumers/repository-checks.yml', 'host/project-tests.yml'),
                ('protected-producer-original-default-v1', 'producers/repository-checks.yml',
                 'producers/protected-project-tests-android-platform.yml'),
                ('protected-producer-original-default-boolean-v1', 'producers/repository-checks.yml',
                 'producers/protected-project-tests-android-platform.yml'),
                ('protected-producer-original-default-required-context-v1', 'producers/repository-checks.yml',
                 'producers/protected-project-tests-android-platform.yml')):
            with self.subTest(generation=generation):
                recipes = {}
                for endpoint, relative in (('repository-checks', caller_path), ('project-tests', project_path)):
                    raw = (original_default_workflow('repository-checks') if generation=='protected-producer-original-default-v1' and endpoint=='repository-checks'
                        else boolean_workflow('repository-checks') if generation=='protected-producer-original-default-boolean-v1' and endpoint=='repository-checks'
                        else (ROOT / 'tools/repository-checks/workflows' / relative).read_bytes())
                    self.assertEqual(generations[generation]['.github/workflows/' + endpoint + '.yml'],
                                     {'mode': '100644', 'type': 'blob',
                                      'sha': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()})
                    recipes[endpoint] = workflow_data(raw.decode())
                caller, project = recipes['repository-checks'], recipes['project-tests']
                events = caller.get('on', caller.get(True))
                self.assertIn('pull_request', events)
                self.assertNotIn('paths', events['pull_request'])
                self.assertNotIn('paths-ignore', events['pull_request'])
                route = caller['jobs']['project']
                self.assertEqual(route['uses'], './.github/workflows/project-tests.yml')
                self.assertIn("needs.route.outputs.package_host_mode == 'full'", route['if'])
                self.assertIn('project', caller['jobs']['repository-checks']['needs'])
                self.assertIn('always()', caller['jobs']['repository-checks']['if'])
                host = project['jobs']['project-tests']
                self.assertEqual(host['if'], "needs.route.outputs.package_host_mode == 'full'")
                execution = next(step for step in host['steps']
                                 if step.get('name') == 'Run independently selected host contracts')
                self.assertIn('trusted/tools/repository-checks/host_selection.py', execution['run'])
                self.assertIn('--expected-plan "$EXPECTED_PLAN"', execution['run'])
                final = project['jobs']['project-results']
                self.assertEqual(final['if'], 'always()')
                self.assertIn('project-tests', final['needs'])

    def test_prospective_seven_target_recipes_require_the_complete_canonical_generation(self):
        spec = importlib.util.spec_from_file_location(
            'prospective_workflow_contract_packages', ROOT / 'tools/repository-checks/package_checks.py')
        packages = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(packages)
        packages, tree = prospective_package_tree()
        generation = packages.validate_tree_wiring(tree)
        self.assertEqual(generation, prospective_package_generation(packages))
        historical = next(row for row in packages.workflow_generations()
                          if row['name'] == 'protected-producer-seven-target-ci-v1')
        self.assertEqual(packages.validate_tree_wiring(historical['workflows']), historical['name'])
        project = (ROOT / 'tools/repository-checks/workflows/producers/protected-project-tests.yml').read_text()
        caller = (ROOT / 'tools/repository-checks/workflows/producers/repository-checks.yml').read_text()
        # Preserve the exact historical21 host-template contract separately.
        raw = project.encode()
        self.assertEqual(hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(),
                         historical['workflows']['.github/workflows/project-tests.yml']['sha'])
        with mock.patch.object(sys.modules[__name__], 'reviewed_package_generation', return_value=historical['name']):
            assert_reviewed_host_selection(self, project)
        # Installation22 is admitted only after all actual future endpoint bytes
        # match the complete catalog, including separate mandatory platform work.
        future = workflow_data((ROOT / 'tools/repository-checks/workflows/producers/protected-project-tests-android-platform.yml').read_text())
        self.assertIn('platform-tests', future['jobs'])
        self.assertIn('platform-tests', future['jobs']['project-results']['needs'])
        with mock.patch.object(sys.modules[__name__], 'reviewed_package_generation', return_value=generation):
            self.assertEqual(assert_project_caller_routing(self, caller), 'package_host_mode')
            with self.assertRaises(AssertionError):
                assert_project_caller_routing(self, caller + '\n# unreviewed caller\n')
        # Strict source identity needs separate non-root sibling checkouts.
        from pathlib import PurePosixPath
        import shlex
        caller_workflow = workflow_data(caller)
        verifier = caller_workflow['jobs']['repository-checks']
        trusted = next(step for step in verifier['steps']
                       if step.get('name') == 'Check out trusted result verifier')
        candidate = next(step for step in verifier['steps']
                         if step.get('name') == 'Check out the exact candidate without credentials')
        verify = next(step for step in verifier['steps']
                      if step.get('name') == 'Require all selected checks to succeed')
        paths = []
        for checkout in (trusted, candidate):
            raw_path = checkout['with'].get('path', '.')
            self.assertIsInstance(raw_path, str)
            self.assertTrue(raw_path)
            path = PurePosixPath(raw_path)
            self.assertFalse(path.is_absolute())
            self.assertNotEqual(path, PurePosixPath('.'))
            self.assertNotIn('..', path.parts)
            paths.append(path)
        trusted_path, candidate_path = paths
        self.assertNotEqual(trusted_path, candidate_path)
        self.assertNotIn(trusted_path, candidate_path.parents)
        self.assertNotIn(candidate_path, trusted_path.parents)
        self.assertEqual(trusted['with']['ref'], '${{ github.event.repository.default_branch }}')
        self.assertIs(trusted['with']['persist-credentials'], False)
        self.assertEqual(candidate['with']['fetch-depth'], 2)
        self.assertIs(candidate['with']['persist-credentials'], False)
        command = shlex.split(verify['run'])
        self.assertEqual(command[0], 'python3')
        self.assertEqual(PurePosixPath(command[1]), trusted_path / 'tools/repository-checks/check.py')
        self.assertEqual(command[2], 'verify')
        self.assertEqual(command.count('--candidate'), 1)
        candidate_index = command.index('--candidate') + 1
        self.assertLess(candidate_index, len(command))
        self.assertEqual(PurePosixPath(command[candidate_index]), candidate_path)
        self.assertNotIn('working-directory', verify)
        self.assertNotIn('working-directory', verifier.get('defaults', {}).get('run', {}))
        self.assertNotIn('working-directory', caller_workflow.get('defaults', {}).get('run', {}))

    def test_security_deferral_keeps_every_other_security_check_selected(self):
        workflow = workflow_data((WORKFLOW_DIRECTORY / 'workflow-security.yml').read_text())
        self.assertEqual(set(workflow_events((WORKFLOW_DIRECTORY / 'workflow-security.yml').read_text())),
                         {'workflow_call'})
        caller = workflow_data((WORKFLOW_DIRECTORY / 'repository-checks.yml').read_text())
        self.assertEqual(caller['jobs']['workflow-security']['uses'],
                         './.github/workflows/workflow-security.yml')
        self.assertIn("needs.route.outputs.security == 'true'",
                      caller['jobs']['workflow-security']['if'])
        self.assertIn('workflow-security', caller['jobs']['repository-checks']['needs'])
        self.assertEqual(workflow_events((WORKFLOW_DIRECTORY / 'workflow-security.yml').read_text())['workflow_call'],
            {'inputs': {'defer_workflow_contracts': {'type': 'boolean', 'default': False,
                'description': 'Exact caller verifies contracts after the shared owner; this input grants no test authority'}}})
        steps = workflow['jobs']['static-analysis']['steps']
        self.assertNotIn('if', workflow['jobs']['static-analysis'])
        for name, command in (('Verify immutable action references', 'python3 tools/workflow-security/check-action-pins.py'),
                ('Lint workflow syntax and runner labels', 'actionlint -config-file .github/actionlint.yaml -no-color'),
                ('Audit workflow security', 'zizmor --min-severity medium .github/workflows'),
                ('Scan workflow files for secrets with redacted output', 'gitleaks dir --redact=100 --no-banner --no-color .github')):
            step = next(step for step in steps if step['name'] == name)
            self.assertEqual(step['run'], command)
            self.assertNotIn('defer_workflow_contracts', step.get('if', ''))
        contract = next(step for step in steps if step['name'] == 'Verify fail-closed workflow contracts')
        self.assertEqual(contract['if'], 'always() && inputs.defer_workflow_contracts != true')
        self.assertEqual(contract['run'], 'PYTHONDONTWRITEBYTECODE=1 python3 tests/workflow-contract-test.py')

    def test_reviewed_host_selection_rejects_foreign_workflow_bytes(self):
        for relative in ('host/project-tests.yml', 'android-owned/project-tests.yml',
                         'producers/protected-project-tests.yml',
                         'producers/protected-project-tests-android-platform.yml',
                         'producers/protected-project-tests-optional-leaf.yml'):
            source = (ROOT / 'tools/repository-checks/workflows' / relative).read_text()
            with self.subTest(relative=relative), self.assertRaises(AssertionError):
                assert_reviewed_host_selection(self, source + '\n# foreign workflow bytes\n')

    def test_reviewed_host_selection_requires_the_complete_installed_generation(self):
        source = WORKFLOW.read_text()
        if source == (ROOT / 'tools/repository-checks/workflows/host/project-tests.yml').read_text():
            return  # This historical pre-generation template retains its original contract.
        with mock.patch.object(sys.modules[__name__], 'reviewed_package_generation',
                               return_value='unknown-or-mixed-generation'):
            with self.assertRaises(AssertionError):
                assert_reviewed_host_selection(self, source)

    def test_codeql_recipe_rejects_unreviewed_local_workflow_bytes(self):
        source = (ROOT / 'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml').read_text()
        with self.assertRaises(AssertionError):
            codeql_generation(self, source + '\n# foreign reusable recipe\n')
        installed=reviewed_package_generation()
        with tempfile.TemporaryDirectory(prefix='workflow-upload-pair-') as folder:
            path=Path(folder)/'codeql.yml'
            path.write_bytes((ROOT/'tools/repository-checks/workflows/metadata-edits/codeql-upload-provenance.yml').read_bytes())
            with mock.patch.object(sys.modules[__name__],'CODEQL_WORKFLOW',path):
                if installed in {'protected-producer-original-default-required-context-v1',
                        'protected-producer-optional-parent-source-v1','protected-producer-optional-leaf-common-v1', 'protected-producer-exact-parent-command-owners-v1'}:
                    self.assertEqual(reviewed_package_generation(),installed)
                else:
                    with self.assertRaises(AssertionError): reviewed_package_generation()
                path.write_bytes(path.read_bytes()+b'\n# unknown upload recipe\n')
                with self.assertRaises(AssertionError): reviewed_package_generation()

    def test_tool_dependency_lane_is_bounded_and_selected_by_the_trusted_router(self):
        jobs = workflow_data(WORKFLOW.read_text())['jobs']
        self.assertEqual(jobs['project-tests']['if'], "needs.route.outputs.package_host_mode == 'full'")
        light = jobs['tool-dependencies']
        self.assertEqual(light['if'], "needs.route.outputs.package_host_mode == 'tool-dependencies'")
        runs = '\n'.join(step.get('run', '') for step in light['steps'])
        self.assertIn('trusted/tools/repository-checks/package_checks.py run', runs)
        self.assertIn('--lane tool-dependencies', runs)
        self.assertNotIn('apt-get', runs)
        self.assertNotIn('tests/run-project-tests.py', runs)
        for step in light['steps']:
            if step.get('uses', '').startswith('actions/checkout@'):
                self.assertIs(step['with']['persist-credentials'], False)
        self.assertEqual(light['steps'][0]['with']['path'], 'trusted')
        self.assertEqual(light['steps'][0]['with']['ref'], '${{ github.event.repository.default_branch }}')
        controller = (ROOT / 'tools/repository-checks/package_checks.py').read_text()
        self.assertIn('with controller.candidate_process_environment():', controller)
        final = jobs['project-results']
        self.assertEqual(final['if'], 'always()')
        expected_needs = {'route', 'project-tests', 'tool-dependencies', 'package-checks'}
        if reviewed_package_generation() in ORIGINAL_DEFAULT_GENERATIONS:
            expected_needs.add('platform-tests')
        self.assertEqual(set(final['needs']), expected_needs)
        aggregate = (WORKFLOW_DIRECTORY / 'repository-checks.yml').read_text()
        mode = assert_project_caller_routing(self, aggregate)
        caller = workflow_data(aggregate)['jobs']['project']
        self.assertIn("needs.route.outputs." + mode + " == 'tool-dependencies'", caller['if'])
        self.assertIn("needs.route.outputs.package_set != '[]'", caller['if'])
        self.assertEqual(caller['with']['dependency_projects'], '${{ needs.route.outputs.tool_projects }}')
        self.assertEqual(caller['with']['expected_package_plan'], '${{ needs.route.outputs.package_plan }}')

    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_untrusted_pull_requests_have_read_only_permissions(self):
        self.assertIn("workflow_call:", self.source)
        caller = (WORKFLOW_DIRECTORY / "repository-checks.yml").read_text()
        self.assertIn("pull_request:", caller)
        self.assertNotIn("pull_request_target:", caller)
        self.assertNotRegex(caller, r"(?m)^\s+[a-z-]+: write$")
        self.assertNotIn("pull_request_target:", self.source)
        self.assertRegex(self.source, r"(?m)^permissions:\n  contents: read$")
        self.assertNotRegex(self.source, r"(?m)^\s*(id-token|packages|actions): write$")

    def test_every_action_is_pinned_to_a_full_commit(self):
        actions = ACTION_USE.findall(self.source)
        self.assertGreaterEqual(len(actions), 5)
        self.assertEqual(
            [action for action in actions if not FULL_SHA_ACTION.fullmatch(action)],
            [],
            "pin every action to an immutable 40-character commit SHA",
        )

    def test_checkout_does_not_persist_credentials(self):
        self.assertIn("persist-credentials: false", self.source)

    def test_duplicate_runs_are_cancelled_and_jobs_are_bounded(self):
        self.assertIn("cancel-in-progress: true", self.source)
        timeout = re.search(r"(?m)^\s+timeout-minutes:\s*(\d+)\s*$", self.source)
        self.assertIsNotNone(timeout)
        self.assertLessEqual(int(timeout.group(1)), 30)

    def test_reports_have_short_explicit_retention(self):
        retention = re.search(r"(?m)^\s+retention-days:\s*(\d+)\s*$", self.source)
        self.assertIsNotNone(retention)
        self.assertLessEqual(int(retention.group(1)), 7)
        self.assertNotIn("*.apk", self.source.lower())

    def test_ci_uses_the_repository_entry_point(self):
        self.assertIn("tests/run-project-tests.py", self.source)
        self.assertIn("--junit build/test-results/project-tests.xml", self.source)

    def test_ci_runs_complete_device_control_plane_with_qml(self):
        self.assertIn("qml-module-qttest", self.source)
        self.assertIn("qtdeclarative5-dev-tools", self.source)
        if any('trusted/tools/repository-checks/' + name in self.source
               for name in ('host_selection.py', 'android_handoff.py')):
            assert_reviewed_host_selection(self, self.source)
        else:
            self.assertIn("--profile host --timeout 240 --host-timeout 900", self.source)
        self.assertIn("device-e2e-control-plane.xml", self.source)

    def test_budget_source_recipe_keeps_commands_and_rejects_other_budget_or_setup_changes(self):
        recipes = source13_budget_recipes()
        source = recipes['.github/workflows/project-tests.yml']
        assert_reviewed_host_selection(self, source)
        spec = importlib.util.spec_from_file_location('namespace_contract_packages', ROOT / 'tools/repository-checks/package_checks.py')
        packages = importlib.util.module_from_spec(spec); spec.loader.exec_module(packages)
        budget = next(row for row in packages.workflow_generations() if row['name']=='npm-consumers-sync-ci-budget-v1')
        for path, recipe in recipes.items():
            with self.subTest(path=path):
                raw = recipe.encode()
                self.assertEqual(budget['workflows'][path], {'mode':'100644','type':'blob','sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()})
                jobs = workflow_data(recipe)['jobs']
                job = jobs['validate' if path.endswith('sync-validation.yml') else 'qualify-parent' if path.endswith('parent-qualification.yml') else 'project-tests']
                steps = job['steps']; utility = next(step for step in steps if step['name']=='Install selected artifact namespace utility')
                select = 'select' if path.endswith('sync-validation.yml') else 'host'
                self.assertEqual(utility['if'], "steps."+select+".outputs.requires_artifact_namespace == 'true'")
                self.assertEqual(utility['run'], 'set -euo pipefail\nif ! test -x /usr/bin/bwrap; then\n  if test "$FULL_HOST" != true; then\n    sudo apt-get -o Acquire::Retries=4 update\n  fi\n  sudo apt-get -o Acquire::Retries=4 install --no-install-recommends -y bubblewrap\nfi\ntest -x /usr/bin/bwrap\n')
                self.assertNotIn('full_host', utility['if'])
                self.assertEqual(utility['env'], {'FULL_HOST':'${{ steps.'+select+'.outputs.full_host }}'})
                self.assertIn('if test "$FULL_HOST" != true; then', utility['run'])
                self.assertNotIn('qml', utility['run'])
                self.assertEqual(sum(step['name']=='Install selected artifact namespace utility' for step in steps), 1)
                qt = next(step for step in steps if step['name'] == ('Install candidate host prerequisites' if select=='select' else 'Install QML and portable C++ contract prerequisites'))
                self.assertEqual(qt['if'], "steps."+select+".outputs.full_host == 'true'")
                self.assertLess(steps.index(qt), steps.index(utility))
        jobs = workflow_data(source)['jobs']
        self.assertEqual(jobs['project-tests']['timeout-minutes'], 30)
        old = workflow_data((ROOT / 'tools/repository-checks/workflows/host/project-tests.yml').read_text())
        old['jobs']['project-tests']['timeout-minutes'] = 30
        jobs['project-tests']['steps'].remove(next(step for step in jobs['project-tests']['steps'] if step['name']=='Install selected artifact namespace utility'))
        self.assertEqual(jobs, old['jobs'])
        for changed in (source.replace('timeout-minutes: 30','timeout-minutes: 31'),
                        source.replace('requires_artifact_namespace', 'full_host'),
                        source.replace('-y bubblewrap', '-y bubblewrap curl'),
                        source.replace('host_selection.py','foreign_selection.py')):
            with self.subTest(changed=changed[:100]), self.assertRaises(AssertionError):
                assert_reviewed_host_selection(self, changed)
        with mock.patch.object(sys.modules[__name__], 'WORKFLOW') as current, \
             mock.patch.object(sys.modules[__name__], 'reviewed_package_generation',return_value='unknown-or-mixed-generation'):
            current.read_text.return_value = source
            with self.assertRaises(AssertionError): assert_reviewed_host_selection(self, source)

    def test_original22_fallback_namespace_utility_is_owner_selected_without_changing_protected_setup(self):
        expected = {'.github/workflows/project-tests.yml': {'path': 'tools/repository-checks/workflows/producers/protected-project-tests-android-platform.yml', 'before_oid': 'b540a1f26c3fbe2a60e7b7ecde91d814cfa0060c', 'after_oid': '28c32a5aa4ccfe75b14514d17a19c016dc1cf2e9', 'condition': "steps.protected.outputs.protected_executed != 'true' && steps.host.outputs.requires_artifact_namespace == 'true'", 'selected_step': 'host'}, '.github/workflows/parent-qualification.yml': {'path': 'tools/repository-checks/workflows/producers/parent-qualification-android-platform.yml', 'before_oid': '98abf45ca6c475af1e1ac3b20ec20f074048fb64', 'after_oid': '9bfc6f8723b1f59426f913472b78206844a7f201', 'condition': "steps.host.outputs.requires_artifact_namespace == 'true'", 'selected_step': 'host'}, '.github/workflows/sync-validation.yml': {'path': 'tools/repository-checks/workflows/sync-ci-selection.yml', 'before_oid': '50cbb324de358c5f8cd019a8e9b9aed45ea6868d', 'after_oid': '747bd6424d1e9b533ae35a81b524ceefc06b286b', 'condition': "steps.select.outputs.requires_artifact_namespace == 'true'", 'selected_step': 'select'}}
        packages, tree = prospective_package_tree()
        self.assertEqual(packages.validate_tree_wiring(tree), prospective_package_generation(packages))
        for endpoint, facts in expected.items():
            with self.subTest(endpoint=endpoint):
                raw = (ROOT / facts['path']).read_bytes()
                actual_entry={'mode':'100644','type':'blob',
                    'sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
                self.assertEqual(tree[endpoint],actual_entry)
                if endpoint=='.github/workflows/parent-qualification.yml' and actual_entry['sha']!=facts['after_oid']:
                    self.assertEqual(prospective_package_generation(packages),'protected-producer-optional-parent-source-v1')
                    self.assertEqual(actual_entry['sha'],'987d8f0d198e40211ab0f33286a55852e286c174')
                    # Preserve the original utility-removal oracle on exact26.
                    raw=original_default_workflow('parent-qualification')
                self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(), facts['after_oid'])
                sync = endpoint.endswith('sync-validation.yml'); indent = 6 if sync else 4
                if sync:
                    assert_sync_callback_roles(self, raw.decode())
                    raw = callback_sync_predecessor(raw.decode()).encode()
                    self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
                                     'fb8b8645f229d924cfebb068ea124ac5910a483e')
                start = (' '*indent+'- name: Install selected artifact namespace utility\n').encode()
                following = (' '*indent+'- name: Prepare isolated '+('shared and product Python validators' if sync else 'host evidence validators')+'\n').encode()
                self.assertEqual(raw.count(start), 1)
                first = raw.index(start); last = raw.index(following, first)
                restored = raw[:first]+raw[last:]
                self.assertEqual(hashlib.sha1(b'blob '+str(len(restored)).encode()+b'\0'+restored).hexdigest(), facts['before_oid'])
                jobs = workflow_data(raw.decode())['jobs']
                job = jobs['validate' if sync else 'common-parent' if endpoint.endswith('parent-qualification.yml') else 'project-tests']
                steps = job['steps']; utility = next(step for step in steps if step['name']=='Install selected artifact namespace utility')
                self.assertEqual(utility['if'], facts['condition'])
                self.assertEqual(utility['env'], {'FULL_HOST':'${{ steps.'+facts['selected_step']+'.outputs.full_host }}'})
                self.assertEqual(utility['run'], 'set -euo pipefail\nif ! test -x /usr/bin/bwrap; then\n  if test "$FULL_HOST" != true; then\n    sudo apt-get -o Acquire::Retries=4 update\n  fi\n  sudo apt-get -o Acquire::Retries=4 install --no-install-recommends -y bubblewrap\nfi\ntest -x /usr/bin/bwrap\n')
                qt = next(step for step in steps if step['name']==('Install candidate host prerequisites' if sync else 'Install QML and portable C++ contract prerequisites'))
                self.assertLess(steps.index(qt), steps.index(utility))
                if endpoint.endswith('project-tests.yml'):
                    protected = next(step for step in steps if step.get('id')=='protected')
                    self.assertLess(steps.index(protected), steps.index(utility))
                    ensure = next(step for step in steps if step['name']=='Ensure the required namespace tool is available')
                    self.assertEqual(ensure['if'], "needs.route.outputs.protected_full == 'true' && steps.protected-source.outputs.admitted == 'true'")
                    self.assertEqual(job['timeout-minutes'], 45)



class OptionalParentGenerationFixtureContracts(unittest.TestCase):
    def test_exact_canonical26_and27_helpers_reject_unknown_or_mixed_parent(self):
        original=Path.read_bytes
        parent=ROOT/'.github/workflows/parent-qualification.yml'
        template=ROOT/'tools/repository-checks/workflows/producers/parent-qualification-android-platform.yml'
        # These are complete historical tuples. A future installed project28
        # must not accidentally turn a Parent26/27 fixture into a mixed tuple.
        project=original(ROOT/'tools/repository-checks/workflows/producers/protected-project-tests-android-platform.yml')
        variants=(('protected-producer-original-default-required-context-v1','parent-qualification'),
                  ('protected-producer-optional-parent-source-v1','optional-parent-qualification'))
        for expected,fixture in variants:
            raw=original_default_workflow(fixture)
            def read(path):return project if path==WORKFLOW else raw if path in (parent,template) else original(path)
            with self.subTest(generation=expected),mock.patch.object(Path,'read_bytes',read):
                self.assertEqual(reviewed_package_generation(),expected)
                packages,tree=prospective_package_tree()
                self.assertEqual(packages.validate_tree_wiring(tree),expected)
                caller=(ROOT/'tools/repository-checks/workflows/producers/repository-checks.yml').read_text()
                self.assertEqual(assert_project_caller_routing(self,caller),'package_host_mode')
        for bad in (b'foreign Parent bytes\n',original_default_workflow('optional-parent-qualification')+b'\n# unknown\n'):
            def read(path):return project if path==WORKFLOW else bad if path in (parent,template) else original(path)
            with self.subTest(invalid=bad[:20]),mock.patch.object(Path,'read_bytes',read),self.assertRaises((AssertionError,ValueError)):
                prospective_package_tree()
        raw=original_default_workflow('optional-parent-qualification')
        old=original_default_workflow('parent-qualification')
        def read(path):return project if path==WORKFLOW else raw if path==parent else old if path==template else original(path)
        with mock.patch.object(Path,'read_bytes',read):
            self.assertEqual(reviewed_package_generation(),'protected-producer-optional-parent-source-v1')
            self.assertEqual(prospective_package_tree()[0].validate_tree_wiring(prospective_package_tree()[1]),
                             'protected-producer-original-default-required-context-v1')


class HostWorkflowRoutingContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflows = {
            "shared": WORKFLOW.read_text(encoding="utf-8"),
            "parent": PARENT_QUALIFICATION_WORKFLOW.read_text(encoding="utf-8"),
        }
        cls.branches = json.loads((ROOT / ".github/branch-policy.json").read_text())["branches"]

    def selected(self, branch, changed_paths):
        return [name for name, source in self.workflows.items()
                if selects_host_push(source, branch, changed_paths)]

    def test_every_permanent_branch_push_runs_exactly_one_complete_host_lane(self):
        for branch, settings in self.branches.items():
            with self.subTest(branch=branch):
                expected = "parent" if settings["children"] else "shared"
                self.assertEqual(self.selected(branch, ["interface/src/Application.cpp"]), [expected])

    def test_development_push_coverage_and_manual_reusable_entrypoints_remain(self):
        for branch in ("ci/main/workflow-change", "test/main/test-change", "ci/example", "test/example"):
            with self.subTest(branch=branch):
                self.assertEqual(self.selected(branch, ["tests/new-test.py"]), ["shared"])
        for branch in ("feature/main/example", "ci", "testing/example"):
            self.assertEqual(self.selected(branch, ["tests/new-test.py"]), [])
        for event in ("workflow_call", "workflow_dispatch"):
            self.assertIn(event, workflow_events(self.workflows['shared']))
            self.assertNotIn(event, workflow_events(self.workflows['parent']))
        aggregate = (WORKFLOW_DIRECTORY / "repository-checks.yml").read_text()
        self.assertIn("pull_request:", aggregate)
        assert_project_caller_routing(self, aggregate)
        self.assertIn("uses: ./.github/workflows/project-tests.yml", aggregate)

    def test_only_markdown_changes_skip_push_lanes(self):
        for branch in (*self.branches, "ci/main/example", "test/main/example"):
            with self.subTest(branch=branch):
                self.assertEqual(self.selected(branch, ["README.md", "docs/guide.md"]), [])
                self.assertEqual(len(self.selected(branch, ["README.md", "tests/new-test.py"])), 1)
                self.assertEqual(len(self.selected(branch, ["unknown.extension"])), 1)

    def test_routing_parser_rejects_unsupported_or_incomplete_configuration(self):
        valid = 'on:\n  push:\n    branches: [main]\n    paths-ignore:\n      - "**/*.md"\n'
        self.assertTrue(selects_host_push(valid, "main", ["tests/test.py"]))
        variants = (
            valid.replace("branches: [main]", "branches-ignore: [main]"),
            valid.replace("branches: [main]", "branches: []"),
            valid.replace("branches: [main]", "branches: [main, '!apple-main']"),
            valid.replace('"**/*.md"', '"**/*.py"'),
            valid.replace("    branches: [main]\n", ""),
            valid.replace("  push:\n", "  push: {}\n"),
            valid + "    tags: [v*]\n",
        )
        for source in variants:
            with self.subTest(source=source), self.assertRaises(ValueError):
                push_filters(source)

    def test_parent_and_shared_keep_matching_tools_and_complete_host_coverage(self):
        for name, source in self.workflows.items():
            with self.subTest(workflow=name):
                workflow = workflow_data(source)
                steps = [step for job in workflow['jobs'].values() for step in job.get('steps', [])]
                for action, key, version in (('setup-python', 'python-version', '3.12'),
                                             ('setup-node', 'node-version', '22'),
                                             ('setup-java', 'java-version', '17')):
                    matching = [step['with'] for step in steps if step.get('uses', '').startswith('actions/' + action + '@')]
                    self.assertTrue(any(item.get(key) == version for item in matching), action)
                    if action == 'setup-java': self.assertTrue(all(item['distribution'] == 'temurin' for item in matching))
                runs = '\n'.join(step.get('run', '') for step in steps)
                for fragment in ("command -v cmake", "command -v ctest",
                                 "qml-module-qttest", "qtdeclarative5-dev-tools",
                                 "qt6-base-dev qt6-base-dev-tools",
                                 "unshare --user --map-root-user --net true"):
                    self.assertIn(fragment, runs)
                if name == "parent":
                    self.assertIn("-r trusted/tests/requirements-host.txt", runs)
                    self.assertIn("build/host-tests-env/bin/python trusted/tools/test-evidence/run.py", runs)
                    self.assertIn("--candidate candidate --include-platform --timeout 240 --host-timeout 900", runs)
                    self.assertNotIn("python tests/run-project-tests.py", source)
                    self.assertNotIn("candidate/tests/run-project-tests.py", source)
                elif any('trusted/tools/repository-checks/' + controller in source
                         for controller in ('host_selection.py', 'android_handoff.py')):
                    assert_reviewed_host_selection(self, source)
                else:
                    self.assertIn("-r tests/requirements-host.txt", runs)
                    self.assertEqual(runs.count("tests/run-project-tests.py"), 1)
                    self.assertIn("build/host-tests-env/bin/python tests/run-project-tests.py", runs)
                    self.assertIn("--profile host --timeout 240 --host-timeout 900", runs)
                self.assertNotIn("tests/device/run_control_plane_tests.py", source)
                self.assertNotIn("--shared-only", source)
                self.assertNotIn("--platform-only", source)
                self.assertNotIn("continue-on-error:", source)

    def test_host_namespace_setup_is_ephemeral_and_preserves_isolation(self):
        import yaml
        workflows = [(name, source, "Prepare isolated host evidence validators")
                     for name, source in self.workflows.items()]
        workflows.append(("sync-fallback", SYNC_VALIDATION_WORKFLOW.read_text(encoding="utf-8"),
                          "Prepare isolated shared and product Python validators"))
        for name, source, step in workflows:
            with self.subTest(workflow=name):
                self.assertIn("runs-on: ubuntu-24.04", source)
                setup_steps = [item for job in yaml.safe_load(source)['jobs'].values()
                               for item in job.get('steps', []) if item.get('name') == step]
                self.assertEqual(len(setup_steps), 1)
                setup = setup_steps[0]['run']
                guard = 'test "$RUNNER_ENVIRONMENT" = github-hosted'
                setting = "sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0"
                probe = "unshare --user --map-root-user --net true"
                self.assertLess(setup.index(guard), setup.index(setting))
                self.assertLess(setup.index(setting), setup.index(probe))
                self.assertLess(setup.index(probe), setup.index("python3 -m venv"))
                self.assertNotIn("||", setup)
                self.assertNotIn("/etc/sysctl", setup)
                self.assertNotIn("sudo unshare", source)
                self.assertNotIn("sudo python", source)
                if name == 'sync-fallback' and sync_callback_blob(source) in {
                        'ccc75d37c4f8b5012299bf864bf48dd45ead389b',
                        '747bd6424d1e9b533ae35a81b524ceefc06b286b'}:
                    assert_sync_callback_roles(self, source)
                    source = callback_sync_predecessor(source)
                self.assertNotIn("continue-on-error:", source)

    def test_sync_platform_and_fallback_install_host_packages_before_execution(self):
        import yaml
        workflow = yaml.safe_load(SYNC_VALIDATION_WORKFLOW.read_text())
        steps = workflow['jobs']['validate']['steps']
        installs = [(index, step) for index, step in enumerate(steps)
                    if 'apt-get' in step.get('run', '') and 'install' in step['run']
                    and step.get('name') != 'Install selected artifact namespace utility']
        self.assertEqual(len(installs), 1, 'Both paths must share one prerequisite installation')
        index, install = installs[0]
        self.assertEqual(install['if'], sync_condition(
            "inputs.mode == 'fallback' || (inputs.profile != 'documentation' && inputs.profile != 'tool-dependencies')", "steps.select.outputs.full_host == 'true'", setup=True))
        for package in ('qt6-base-dev', 'qt6-base-dev-tools', 'pkg-config',
                        'qml-module-qttest', 'qtdeclarative5-dev-tools'):
            self.assertIn(package, install['run'].split())
        executions = [i for i, step in enumerate(steps)
                      if step.get('name') == 'Verify exact candidate suites and complete runtime identity']
        self.assertEqual(len(executions), 1, 'Reuse and fallback share one trusted execution controller')
        self.assertLess(index, executions[0])
        namespace = [(i, step) for i, step in enumerate(steps)
                     if step.get('name') == 'Install selected artifact namespace utility']
        self.assertEqual(len(namespace), int(reviewed_package_generation() in (
            'npm-consumers-sync-ci-budget-v1', 'npm-consumers-sync-ci-budget-cleanup-v1', *ORIGINAL_DEFAULT_GENERATIONS)))
        if namespace:
            utility_index, utility = namespace[0]
            self.assertEqual(utility['if'], "steps.select.outputs.requires_artifact_namespace == 'true'")
            self.assertEqual(utility['env'], {'FULL_HOST': '${{ steps.select.outputs.full_host }}'})
            self.assertIn('bubblewrap', utility['run'].split())
            self.assertLess(index, utility_index)
            self.assertLess(utility_index, executions[0])
        self.assertEqual(steps[executions[0]]['if'], sync_condition(
            "inputs.mode == 'fallback' || (inputs.profile != 'documentation' && inputs.profile != 'tool-dependencies')", "steps.select.outputs.lane != 'legacy-bounded'"))

    def test_reused_product_suites_share_the_prepared_python_interpreter(self):
        import yaml
        steps = yaml.safe_load(SYNC_VALIDATION_WORKFLOW.read_text())['jobs']['validate']['steps']
        name = 'Prepare isolated shared and product Python validators'
        index = next(i for i, step in enumerate(steps) if step.get('name') == name)
        prepare = steps[index]
        product = next(step for step in steps if step.get('name') == 'Verify exact candidate suites and complete runtime identity')
        expected_prepare = sync_condition(
            "inputs.mode == 'fallback' || (inputs.profile != 'documentation' && inputs.profile != 'tool-dependencies')",
            "steps.select.outputs.lane != 'legacy-bounded'", setup=True)
        self.assertEqual(prepare['if'], expected_prepare)
        self.assertIsNone(prepare.get('working-directory'))
        self.assertIsNone(product.get('working-directory'))
        self.assertLess(index, steps.index(product))
        interpreter = 'build/host-tests-env/bin/python'
        self.assertIn('python3 -m venv build/host-tests-env', prepare['run'])
        self.assertIn(interpreter + ' -m pip install --disable-pip-version-check '
                      '-r trusted/tests/requirements-host.txt', prepare['run'])
        if 'SYNC_VALIDATOR_PYTHON' in product['env']:
            self.assertEqual(product['run'].split()[:2], ['"$SYNC_VALIDATOR_PYTHON"', '-B'])
            self.assertEqual(product['env']['SYNC_VALIDATOR_PYTHON'],
                "${{ steps.select.outputs.consumer_setup == 'none' && steps.select.outputs.native_setup != '' && 'python3' || 'build/host-tests-env/bin/python' }}")
            self.assertEqual(product['env']['EXPECTED_NATIVE_SETUP'], '${{ steps.select.outputs.native_setup }}')
            self.assertIn('--expected-native-setup "$EXPECTED_NATIVE_SETUP"', product['run'])
        else:
            self.assertEqual(product['run'].split()[0], interpreter)
        self.assertIn('trusted/tools/test-evidence/validate-sync.py', product['run'])
        self.assertIn('--candidate candidate', product['run'])
        self.assertEqual(prepare['env'], {'GH_TOKEN': '', 'GITHUB_TOKEN': ''})
        # The controller uses this read-only token for API evidence; its scoped
        # candidate environment removes it before executing any candidate input.
        self.assertEqual(product['env']['GH_TOKEN'], '${{ github.token }}')
        self.assertNotIn('continue-on-error', prepare)
        self.assertNotIn('continue-on-error', product)

    def test_complete_fallback_isolates_disposable_git_background_writers(self):
        import yaml
        steps = yaml.safe_load(SYNC_VALIDATION_WORKFLOW.read_text())['jobs']['validate']['steps']
        fallback = next(step for step in steps if step.get('name') == 'Verify exact candidate suites and complete runtime identity')
        self.assertEqual(fallback['if'], sync_condition(
            "inputs.mode == 'fallback' || (inputs.profile != 'documentation' && inputs.profile != 'tool-dependencies')", "steps.select.outputs.lane != 'legacy-bounded'"))
        self.assertNotEqual(fallback.get('working-directory'), 'candidate')
        self.assertNotIn('git config --global', fallback['run'])
        self.assertNotIn('continue-on-error', fallback)
        # Background-writer policy now belongs to the shared trusted controller,
        # applying equally to qualification, reuse, and fallback subprocesses.
        directory = ROOT / 'tools/test-evidence'
        spec = importlib.util.spec_from_file_location('workflow_contract_execution', directory / 'execution.py')
        execution = importlib.util.module_from_spec(spec)
        with mock.patch.object(sys, 'path', [str(directory), *sys.path]), mock.patch.dict(sys.modules):
            spec.loader.exec_module(execution)
            hostile = {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'maintenance.auto',
                       'GIT_CONFIG_VALUE_0': 'true', 'GIT_CONFIG_KEY_9': 'gc.auto', 'GIT_CONFIG_VALUE_9': '1',
                       'GH_TOKEN': 'fixture-private', 'GITHUB_TOKEN': 'fixture-private',
                       'GITHUB_ENV': '/fixture/private-command-file', 'GITHUB_OUTPUT': '/fixture/private-command-file'}
            with mock.patch.dict(os.environ, hostile):
                before = dict(os.environ)
                with execution.candidate_process_environment():
                    self.assertEqual(os.environ['GIT_CONFIG_COUNT'], '2')
                    self.assertNotIn('GIT_CONFIG_KEY_9', os.environ)
                    for variable in ('GH_TOKEN', 'GITHUB_TOKEN', 'GITHUB_ENV', 'GITHUB_OUTPUT'):
                        self.assertNotIn(variable, os.environ)
                    for key, expected in (('maintenance.auto', 'false'), ('gc.auto', '0')):
                        observed = subprocess.check_output(['git', 'config', '--get', key], text=True).strip()
                        self.assertEqual(observed, expected)
                self.assertEqual(dict(os.environ), before, 'Trusted API/runtime operations retain their original environment')

    def test_parent_evidence_stays_bound_to_the_successful_exact_push(self):
        source = self.workflows["parent"]
        self.assertIn("ref: ${{ github.sha }}", source)
        self.assertIn("PARENT_COMMIT: ${{ github.sha }}", source)
        self.assertIn("RUN_ATTEMPT: ${{ github.run_attempt }}", source)
        self.assertIn("RUN_ID: ${{ github.run_id }}", source)

        self.assertIn("cancel-in-progress: false", source)
        self.assertLess(source.index("trusted/tools/test-evidence/run.py"), source.index("qualification.py"))
        self.assertIn('trusted/tools/sync-test-reuse/qualification.py', source)
        self.assertIn('--execution-receipt build/parent-qualification/execution.json', source)
        self.assertIn('--receipt build/parent-qualification/execution.json', source)
        self.assertIn('--candidate candidate', source)
        jobs = workflow_data(source)['jobs']
        platform = (ROOT / 'tools/repository-checks/workflows/producers/parent-qualification-android-platform.yml').read_text()
        platform_owner = source == platform
        if platform_owner:
            self.assertIn(reviewed_package_generation(), ORIGINAL_DEFAULT_GENERATIONS)
            self.assertEqual(set(jobs['qualify-parent']['needs']), {'route', 'common-parent', 'platform-tests'})
            final_steps=jobs['qualify-parent']['steps']
            verify=final_steps[-1]
            if reviewed_package_generation() in {'protected-producer-optional-parent-source-v1','protected-producer-optional-leaf-common-v1', 'protected-producer-exact-parent-command-owners-v1'}:
                self.assertEqual(final_steps[-1],{'name':'Reject late cancellation of parent qualification',
                    'if':'cancelled()','run':'exit 1'})
                verify=next(step for step in final_steps if step['name']=='Require both actual parent owners')
                self.assertEqual(verify['if'],"steps.admission.outputs.available == 'true'")
            self.assertIn('producer_workflow.py parent-verify',verify['run'])
        steps = jobs['common-parent' if platform_owner else 'qualify-parent']['steps']
        create = next(step for step in steps if step['name'] == 'Create content-addressed qualification evidence')
        upload = next(step for step in steps if step['name'] == 'Upload immutable qualification evidence')
        canonical = (ROOT / 'tools/repository-checks/workflows/host/parent-qualification.yml').read_text()
        protected = (ROOT / 'tools/repository-checks/workflows/producers/parent-qualification.yml').read_text()
        budget_owner = reviewed_package_generation() in ('npm-consumers-sync-ci-budget-v1', 'npm-consumers-sync-ci-budget-cleanup-v1')
        if source in (canonical, protected, platform) or budget_owner:
            protected_owner = source == protected or platform_owner
            if protected_owner:
                self.assertIn(reviewed_package_generation(), METADATA_PRODUCER_GENERATIONS)
            expected = "steps.host.outputs.complete_receipt == 'true'"
            if protected_owner:
                expected = "steps.reuse.outputs.shared_reused != 'true' && (" + expected + ")"
            if platform_owner:
                expected = "needs.route.outputs.platform_required != 'true' && (" + expected + ")"
            selected = next(step for step in steps if step.get('id') == 'host')
            route = next(step for step in steps if step['name'] == 'Require a complete host execution route')
            qt = next(step for step in steps if step['name'] == 'Install QML and portable C++ contract prerequisites')
            self.assertLess(steps.index(selected), steps.index(route))
            self.assertLess(steps.index(route), steps.index(qt))
            qt_expected=("steps.reuse.outputs.shared_reused != 'true' && (steps.host.outputs.full_host == 'true')"
                         if protected_owner else "steps.host.outputs.full_host == 'true'")
            if platform_owner and reviewed_package_generation() in {'protected-producer-optional-parent-source-v1','protected-producer-optional-leaf-common-v1', 'protected-producer-exact-parent-command-owners-v1'}:
                qt_expected="steps.protected-source.outputs.admitted == 'true' && ("+qt_expected+")"
            self.assertEqual(qt['if'],qt_expected)
            partial = next(step for step in steps if step['name'] == 'Run independently selected parent host contracts')
            self.assertIn("steps.host.outputs.complete_receipt == 'false'", partial['if'])
            self.assertIn('trusted/tools/repository-checks/host_selection.py', partial['run'])
            self.assertNotIn('--receipt', partial['run'])
            self.assertNotIn('qualification.py', partial['run'])
        else:
            self.assertEqual(source, (ROOT / 'tools/repository-checks/workflows/packages/parent-qualification.yml').read_text())
            expected = "steps.route.outputs.package_host_mode == 'full'"
        if platform_owner and reviewed_package_generation() in {'protected-producer-optional-parent-source-v1','protected-producer-optional-leaf-common-v1', 'protected-producer-exact-parent-command-owners-v1'}:
            expected="steps.protected-source.outputs.admitted == 'true' && ("+expected+")"
        for step in (create, upload):
            self.assertEqual(step['if'], expected)
        self.assertIn('Check only affected tool dependencies and behavior', source)
        self.assertNotIn('continue-on-error:', source)
        self.assertEqual(upload['with']['name'], 'parent-qualification-${{ github.sha }}')
        self.assertEqual(upload['with']['if-no-files-found'], 'error')

    def test_parent_trusted_checkout_contains_transitive_host_requirements(self):
        import yaml
        workflow = yaml.safe_load(PARENT_QUALIFICATION_WORKFLOW.read_text())
        checkout = next(step['with'] for step in workflow['jobs']['qualify-parent']['steps']
                        if step.get('with', {}).get('path') == 'trusted')
        # File paths require non-cone mode. Every recursively included pip file
        # must exist in this checkout before installation/runtime fingerprinting.
        self.assertIs(checkout['sparse-checkout-cone-mode'], False)
        included = checkout['sparse-checkout'].split()
        pending = [ROOT / 'tests/requirements-host.txt']
        seen = set()
        while pending:
            path = pending.pop().resolve()
            if path in seen:
                continue
            seen.add(path)
            relative = path.relative_to(ROOT).as_posix()
            self.assertTrue(any(relative == entry or relative.startswith(entry.rstrip('/') + '/')
                                for entry in included), relative + ' is missing from trusted checkout')
            for line in path.read_text().splitlines():
                if line.strip().startswith('-r '):
                    pending.append(path.parent / line.strip()[3:].strip())

    def test_bounded_tool_sync_skips_product_and_host_prerequisites(self):
        import yaml
        steps = yaml.safe_load(SYNC_VALIDATION_WORKFLOW.read_text())['jobs']['validate']['steps']
        tools = next(step for step in steps if step['name'] == 'Verify bounded synchronization without product setup')
        self.assertEqual(tools['if'], sync_condition(
            "inputs.mode == 'reuse' && (inputs.profile == 'documentation' || inputs.profile == 'tool-dependencies')",
            "steps.select.outputs.lane == 'legacy-bounded'"))
        self.assertEqual(tools['run'].split()[0], 'python3')
        self.assertIn('trusted/tools/test-evidence/validate-sync.py', tools['run'])
        self.assertIn('--mode reuse --profile "$PROFILE"', tools['run'])
        self.assertNotIn('apt-get', tools['run'])
        self.assertNotIn('host-tests-env', tools['run'])
        product = next(step for step in steps if step.get('name') == 'Verify exact candidate suites and complete runtime identity')
        self.assertEqual(product['if'], sync_condition(
            "inputs.mode == 'fallback' || (inputs.profile != 'documentation' && inputs.profile != 'tool-dependencies')", "steps.select.outputs.lane != 'legacy-bounded'"))
        for step in steps:
            if step.get('name') == 'Install selected artifact namespace utility':
                self.assertEqual(step['if'], "steps.select.outputs.requires_artifact_namespace == 'true'")
            elif 'apt-get' in step.get('run', '') or step.get('name') == 'Set up candidate Java':
                self.assertEqual(step['if'], sync_condition(
                    "inputs.mode == 'fallback' || (inputs.profile != 'documentation' && inputs.profile != 'tool-dependencies')", "steps.select.outputs.full_host == 'true'", setup=True))
            elif step.get('name') == 'Prepare isolated shared and product Python validators':
                self.assertEqual(step['if'], sync_condition(
                    "inputs.mode == 'fallback' || (inputs.profile != 'documentation' && inputs.profile != 'tool-dependencies')",
                    "steps.select.outputs.lane != 'legacy-bounded'", setup=True))






class OptionalParentSourceDeclineContracts(unittest.TestCase):
    def setUp(self):
        self.jobs=workflow_data(PARENT_QUALIFICATION_WORKFLOW.read_text())['jobs']

    def decision(self, needs, admitted='true', raw=None, cancelled='false'):
        steps=self.jobs['qualify-parent']['steps']
        matches=[step for step in steps if step.get('id')=='admission']
        self.assertEqual(len(matches),1,'optional source decline requires its stdlib decision')
        self.assertEqual(matches[0]['if'],"always() && !cancelled()")
        self.assertEqual(matches[0]['env']['CANCELLED'],"${{ job.status == 'cancelled' }}")
        script='\n'.join(matches[0]['run'].splitlines()[1:-1])+'\n'
        imports={alias.name for node in ast.walk(ast.parse(script)) if isinstance(node,ast.Import) for alias in node.names}
        self.assertEqual(imports,{'json','os'})
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'outputs'
            result=subprocess.run([sys.executable,'-I','-S','-B','-c',script],cwd=temporary,
                env={'PATH':os.defpath,'ADMITTED':admitted,'CANCELLED':cancelled,
                    'CHECK_RESULTS':json.dumps(needs) if raw is None else raw,
                    'GITHUB_OUTPUT':str(output)},capture_output=True,text=True)
            values=dict(line.split('=',1) for line in output.read_text().splitlines()) if output.exists() else {}
        return result,values

    def needs(self, android=False):
        return {'route':{'result':'success' if android else 'skipped','outputs':{
                    'source_admitted':'true','parent_candidate':'exact-current-parent',
                    'parent_plan':'exact-current-plan','platform_required':'false'} if android else {}},
            'common-parent':{'result':'success','outputs':{'source_admitted':'true'}},
            'platform-tests':{'result':'skipped','outputs':{}}}

    def test_admitted_roles_keep_the_original_owner_protocol(self):
        cases=[self.needs(),self.needs(True)]
        platform=self.needs(True)
        platform['route']['outputs']['platform_required']='true'
        platform['platform-tests']={'result':'success','outputs':{
            'source_admitted':'true','required':'true','verified':'true','partition':'exact-platform-partition'}}
        cases.append(platform)
        for needs in cases:
            result,values=self.decision(needs)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(values['available'],'true');self.assertEqual(result.stdout,'')
            expected=json.loads(json.dumps(needs))
            for job in expected.values():job['outputs'].pop('source_admitted',None)
            self.assertEqual(json.loads(values['owner_results']),expected)

    def test_unavailable_source_declines_without_execution_qualification_or_evidence(self):
        cases=[(self.needs(), 'false')]
        route=self.needs(True);route['route']['outputs']['source_admitted']='false'
        route['common-parent']={'result':'skipped','outputs':{}};cases.append((route,'true'))
        common=self.needs();common['common-parent']['outputs']['source_admitted']='false';cases.append((common,'true'))
        platform=self.needs(True);platform['platform-tests']={'result':'success','outputs':{'source_admitted':'false'}}
        cases.append((platform,'true'))
        for needs,admitted in cases:
            with self.subTest(needs=needs,admitted=admitted):
                result,values=self.decision(needs,admitted)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(values,{'available':'false'})
                report=json.loads(result.stdout)
                self.assertEqual(report['kind'],'optional-parent-source-unavailable-v1')
                self.assertEqual(report['scope'],'qualify-parent-decision')
                self.assertEqual(report['executed_suites'],[]);self.assertEqual(report['reused_suites'],[])
                self.assertIsNone(report['execution'])
                self.assertFalse(report['qualification'] or report['reusable'] or report['new_E'])
                self.assertEqual(report['upstream_results'],{name:job['result'] for name,job in needs.items()})

    def test_source_unavailable_cannot_hide_failed_cancelled_or_malformed_jobs(self):
        for name in self.needs():
            for state in ('failure','cancelled','timed_out','in_progress',None):
                needs=self.needs();needs[name]['result']=state
                with self.subTest(name=name,state=state):
                    result,values=self.decision(needs,'false')
                    self.assertNotEqual(result.returncode,0);self.assertEqual(values,{})
        for admitted in ('','TRUE','0','null'):
            with self.subTest(admitted=admitted):
                result,values=self.decision(self.needs(),admitted)
                self.assertNotEqual(result.returncode,0);self.assertEqual(values,{})
        for cancelled in ('true','','TRUE'):
            with self.subTest(cancelled=cancelled):
                result,values=self.decision(self.needs(),'false',cancelled=cancelled)
                self.assertNotEqual(result.returncode,0);self.assertEqual(values,{})
        for change in ('missing-job','extra-job','missing-admission','invalid-admission','invalid-outputs'):
            needs=self.needs()
            if change=='missing-job':del needs['platform-tests']
            elif change=='extra-job':needs['unknown']={'result':'success','outputs':{}}
            elif change=='missing-admission':needs['common-parent']['outputs']={}
            elif change=='invalid-admission':needs['common-parent']['outputs']['source_admitted']=False
            else:needs['common-parent']['outputs']=None
            with self.subTest(change=change):
                result,values=self.decision(needs,'false')
                self.assertNotEqual(result.returncode,0);self.assertEqual(values,{})
        for raw in ('null','[]','not-json','{"route":{},"route":{}}','{"value":NaN}'):
            with self.subTest(raw=raw):
                result,values=self.decision({},'false',raw=raw)
                self.assertNotEqual(result.returncode,0);self.assertEqual(values,{})

    def test_every_candidate_and_execution_step_requires_its_admitted_source(self):
        gate="steps.protected-source.outputs.admitted == 'true'"
        for name,job in self.jobs.items():
            steps=job['steps'];guard=next(i for i,step in enumerate(steps) if step.get('id')=='protected-source')
            candidate=next(i for i,step in enumerate(steps) if step.get('with',{}).get('path')=='candidate')
            self.assertLess(guard,candidate,name)
            if name=='qualify-parent':
                self.assertEqual(steps[0],{'name':'Reject cancelled parent qualification',
                    'if':'cancelled()','run':'exit 1'})
                self.assertLess(0,guard)
                self.assertEqual(steps[-1],{'name':'Reject late cancellation of parent qualification',
                    'if':'cancelled()','run':'exit 1'})
                for step in steps[guard+1:-1]:
                    if step.get('id')!='admission':self.assertEqual(step['if'],"steps.admission.outputs.available == 'true'")
                owners=next(step for step in steps if step['name']=='Require both actual parent owners')
                self.assertEqual(owners['env']['CHECK_RESULTS'],'${{ steps.admission.outputs.owner_results }}')
            else:
                self.assertEqual(job['outputs']['source_admitted'],'${{ steps.protected-source.outputs.admitted }}')
                for step in steps[guard+1:]:self.assertTrue(step.get('if','').startswith(gate),(name,step['name']))
        for name in ('common-parent','platform-tests'):
            self.assertIn("needs.route.outputs.source_admitted == 'true'",self.jobs[name]['if'])


class SharedReleaseBundleWorkflowContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = RELEASE_BUNDLE_WORKFLOW.read_text(encoding="utf-8")

    def test_reusable_gate_has_no_untrusted_or_manual_entrypoint(self):
        self.assertRegex(self.source, r"(?m)^  workflow_call:$")
        self.assertNotRegex(
            self.source,
            r"(?m)^  (pull_request|pull_request_target|push|workflow_dispatch):$",
        )
        self.assertIn("validate-release-bundle.py", self.source)
        self.assertIn('git rev-list -n 1 "refs/tags/$RELEASE_TAG"', self.source)
        self.assertEqual(self.source.count('[[ "$GITHUB_REF_TYPE" == tag ]]'), 2)
        self.assertEqual(
            self.source.count('[[ "$GITHUB_REF" == "refs/tags/$RELEASE_TAG" ]]'), 2
        )

    def test_release_products_tags_and_publish_environments_are_closed_sets(self):
        for value in (
                "android-phone-release-candidate", "pico4-release-candidate",
                "^android-phone-v[0-9]+\\.[0-9]+\\.[0-9]+-alpha\\.[0-9]+$",
                "^pico4-v[0-9]+\\.[0-9]+\\.[0-9]+-rc\\.[0-9]+$"):
            self.assertIn(value, self.source)
        self.assertEqual(self.source.count("Unsupported release product"), 2)
        publish = self.source.split("  draft-publish:", 1)[1]
        self.assertLess(
            publish.index("Reject non-tag or unprotected release invocation"),
            publish.index("actions/checkout@"),
        )

    def test_build_and_sbom_attestations_are_isolated_and_pinned(self):
        attest = self.source.split("  attest:", 1)[1].split("  draft-publish:", 1)[0]
        self.assertRegex(
            attest,
            r"(?m)^    permissions:\n      contents: read\n      id-token: write\n      attestations: write$",
        )
        self.assertEqual(attest.count(
            "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"), 2)
        self.assertIn("subject-path:", attest)
        self.assertIn("sbom-path:", attest)
        actions = ACTION_USE.findall(self.source)
        self.assertGreaterEqual(len(actions), 6)
        self.assertEqual([action for action in actions if not FULL_SHA_ACTION.fullmatch(action)], [])

    def test_draft_job_has_only_contents_write_and_environment_approval(self):
        publish = self.source.split("  draft-publish:", 1)[1]
        self.assertIn("environment: ${{ inputs.publish_environment }}", publish)
        self.assertRegex(publish, r"(?m)^    permissions:\n      contents: write$")
        self.assertNotIn("id-token: write", publish)
        self.assertNotIn("attestations: write", publish)
        self.assertIn("gh release create", publish)
        self.assertIn("--draft --verify-tag", publish)
        self.assertNotIn("gh release edit", publish)
        self.assertNotIn("gh release upload", publish)




class ParentCommandWorkflowTests(unittest.TestCase):
    def test_only_the_reviewed_complete_successor_adds_parent_command_ownership(self):
        directory = ROOT / 'tools/repository-checks/workflows/producers'
        old = workflow_data((directory / 'repository-checks.yml').read_text())
        path = directory / 'repository-checks-parent-owners.yml'
        raw = path.read_bytes()
        future = workflow_data(raw.decode())
        rows = json.loads((ROOT / '.github/package-workflow-generations.json').read_text())['generations']
        self.assertEqual(len(rows), 29)
        self.assertEqual(hashlib.sha256(json.dumps(rows[:28], sort_keys=True,
            separators=(',', ':')).encode()).hexdigest(),
            '153e36b07fadbb45ca6fc449b03437627c661d51cfae23a923e7ffa9d33f7194')
        before, after = rows[27:29]
        self.assertEqual(after['name'], 'protected-producer-exact-parent-command-owners-v1')
        caller = '.github/workflows/repository-checks.yml'
        self.assertEqual([p for p in before['workflows'] if before['workflows'][p] != after['workflows'][p]], [caller])
        self.assertEqual(after['workflows'][caller], {'mode': '100644', 'type': 'blob',
            'sha': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()})
        self.assertEqual({k: v for k, v in future.items() if k != 'jobs'},
                         {k: v for k, v in old.items() if k != 'jobs'})
        self.assertEqual(set(future['jobs']), set(old['jobs']) | {'parent-owners'})
        for job in set(old['jobs']) - {'documentation', 'workflow-contracts', 'repository-checks'}:
            self.assertEqual(future['jobs'][job], old['jobs'][job], job)
        for job, flag in (('documentation', 'documentation_verified'),
                          ('workflow-contracts', 'workflow_contracts_verified')):
            previous, current = old['jobs'][job], future['jobs'][job]
            self.assertEqual(current['needs'], [*previous['needs'], 'parent-owners'])
            self.assertEqual({k: v for k, v in current.items() if k not in {'needs', 'if'}},
                             {k: v for k, v in previous.items() if k not in {'needs', 'if'}})
            self.assertIn("needs.parent-owners.outputs." + flag + " != 'true'", current['if'])
            self.assertIn("(needs.parent-owners.result == 'success' || needs.parent-owners.result == 'skipped')", current['if'])
        aggregate = future['jobs']['repository-checks']
        self.assertEqual({k: v for k, v in aggregate.items() if k != 'needs'},
                         {k: v for k, v in old['jobs']['repository-checks'].items() if k != 'needs'})
        self.assertEqual(set(aggregate['needs']), set(old['jobs']['repository-checks']['needs']) | {'parent-owners'})

    def test_parent_lookup_has_no_dependency_cycle_or_candidate_execution(self):
        path = ROOT / 'tools/repository-checks/workflows/producers/repository-checks-parent-owners.yml'
        jobs = workflow_data(path.read_text())['jobs']
        owner = jobs['parent-owners']
        self.assertEqual(owner['name'], 'parent-owners')
        self.assertEqual(owner['needs'], 'route')
        self.assertEqual(owner['permissions'], dict.fromkeys(('contents', 'actions', 'checks', 'pull-requests'), 'read'))
        self.assertEqual(owner['runs-on'], 'ubuntu-24.04')
        self.assertEqual(owner['timeout-minutes'], 5)
        for predicate in ("github.event_name == 'pull_request'", "github.base_ref == 'android-vr'",
                          "needs.route.outputs.metadata_only != 'true'", "needs.route.outputs.mode == 'delegated-sync'"):
            self.assertIn(predicate, owner['if'])
        self.assertEqual(len(owner['steps']), 2)
        checkout, lookup = owner['steps']
        self.assertEqual(checkout['with'], {'ref': '${{ github.event.repository.default_branch }}',
            'path': 'trusted', 'persist-credentials': False})
        self.assertNotIn('candidate', lookup['run'])
        self.assertIn('check.py parent-owners', lookup['run'])
        self.assertEqual(lookup['env'], {'GH_TOKEN': '${{ github.token }}'})
        self.assertEqual(set(owner['outputs']), {'documentation_verified', 'workflow_contracts_verified', 'parent_proof'})
        def visit(name, trail):
            self.assertNotIn(name, trail)
            needs = jobs[name].get('needs', [])
            for dependency in ([needs] if isinstance(needs, str) else needs):
                visit(dependency, trail | {name})
        for name in jobs:
            visit(name, set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
