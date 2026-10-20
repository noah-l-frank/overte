#!/usr/bin/env python3
"""Adversarial fake-API tests; no live requests, builds, installs or dispatch."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
import zlib
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlsplit

import producer_api as A
import producer as P


SPEC = importlib.util.spec_from_file_location("protocol_api_fixtures", Path(__file__).with_name("producer-test.py"))
FIXTURES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURES)
NOW = FIXTURES.NOW


# Authentic protected generation21 caller and generation20/21 relative helper.
# Inline compressed bytes avoid a hosted Git-history dependency or new lookup
# member. Their whole ordinary Git blob identities are independently literal.
_HISTORICAL_METADATA_WORKFLOWS = {'tools/repository-checks/workflows/producers/repository-checks.yml': ('d9fefd275d9e3c6977cf9350a1945a6bbe5051b4', 'c-q}s>u=jO5dWUPg6WDn0Ve0Yb{;Y;ON=J#>I8|?p(qMLmd-XCSyD;LiP!dj-|?k~CClz3S<!xq$-Cq6cW<gck&~EByhsqiQZ67MiRa&VBOoJ)fO&$((Qm}_1)ZwD34`}3Wx(-|DTP~P5FQ(WAW0ljf7V`$ya{y3B_uJYB4#t<kHNp;YjM<BBP2<~(3LWP3;CN6F-w5!KOGV$cxqsNFev@xv&bK_IHLc8S%H9xY&-M@5N5y9DF1yMvzuWU-?{<ii6{KAK8;36D$L1*urxxwMtCz$wW|7G0NiIZk$1;ir4bQhAbvbaLJ)wvQ|f~=WB?@RCV~RXB*+VP$RLhG@S=j;p_hiDBXNgp)u0=6$j}QptR=uERLN9|`f(&6LZy+=3)b+bpE3rKKa;y77N?2avd}vkdgt+n4`f8eI32WMiu~=O71~ic82}?6KUx|FL-OfUl}ma7UheRav^4T9^5h9wFVXm8FB$=F4?GTXccXS!P!U4m#5vwLm~BdCs}Gun29mt>KJ`L6q`vaS7HTO$@gg5Whel4qVr2pY>brQLP@9180#A4jk5lG@wyk#4qZG{<2`LcB#U&ANCzM-h4;gk!8oH86-M<K6tDvg9wkz?IL=%rj#m)Z#MRkpoV}OzNR$J3;*?8bv33D=VlyBXM_G}WaAshOVuuuU6C}0l83?VPP^=5oSS!_emw&zIEqd5Ayx-(CGA5GMfdM_uwp-F-W>3hrtgZwua5PDG~Twap~bBw`?JK7DdFjM#<i@rh#+3aOf1b1W_NC#;oQfGI+y}hq<7@Yv(<xFUVsG<A=wTw%}6k{*y#!)!y5E);XaT9I~XQ<mHGVS7uI}V`8l!RWC^WbJq$^p{?6|;rpmLO+|Frua<`Fdr+2?Dd3i{bVTVdD#rDN*Ijroy-wxB<nRF1}WUvMNN<FXfkuRn~FLh1&>gg|aGSH6&`OtHL;lr6Q0fXGC0BOanKs8w<GS39BNOTcbi*71C&pB2kr<MluR8<d*VhlvaqMwJn5>=wlhSG61u_MkX{GjZB|n4%eyCB#bQ;>qz#;Ua;ry@4|uS`3D2<+4jM+-Gjh;`pf>#w!iaiXZPve!25N3uw$g$VqWbOYWPrJp_G>Ml+re(-yJZlT;m)G=?5stYMieE<CF`>N4v>lg`I)z4=f4xHH?E}FVG<$vn@hQ-Y=|3H{@HDMxjE1xlB0N;^479RCaZSa3oQcmB!o|q%;hiQq3+I=@R^SB>Op{QeD<n>B1H>B5Rl`$3%f>Poe1NYQg-5Xqv<S{M7BAzv%W#HW2X*L`9@~NBy%`UH4_Te{^!xKXT7{{cf+XdFsnjB|TGBdUByy9y;WACpX(njN@p}nsaLb=-TVr$t*9h#k(O|`Zsy>`1x7?^!iV?`wCTcFOK@BkL;$SI+Hny-qFjhq|ln@yXV*ai|hWQIa7FnZf&#R7P6_8t}UYo?yzL2_@P!aS^JmQuXQZrvKwpNW5nsO$u!T_hk(t#6F?%jcfTs0iZSGry9RAWGGy^YAqaPPJ2WOvMHQXC3^VEPG7}aZ?X$g0W!)vdlpDVarsMFjmor|S9<AzI1}B{^9tbXd*mA&%Iqa*k(imlkt%w!wNV74EkfVy;JFb$Y>B|beYM!A~i(cDXV<%oDsfX>*!Y0XE#yT681}A7eNd%j!S2qMLo9|X_#!cH&>bdnip>)fph~@gO7xk?pH&<9UgF|b{@KZFsntJ9FOWqnboTlI~9bM<%#uQ@0rZTzQlQ)<PHMoPJ$o%137<HqLzS@IJRfh;vVTN3VMFzYq1`x@1h5}#8FI#P?;G4It<&(66qrsc9lV@||LY)Q+<^;G)Z~-dKdebFpy7f#<b%<(`l=tnX6MulTWKL>uL__gS9kGtQGC>`d%FbffFpQ36to4riL2e~ImQ8X^LRK2(ngpyg%QXp@8|H%8PbavbhJ^?4uhMx9URI);_q8|byq|3ucw754wu15|{~0mOuV!^b_O)y^AZk3`3bhQSTf0+WILD#Kt*_|$C3e%08t=D6PWD!H|F*82*<kMq?Y-xhOsQ4#N=3y5WoHP?%|3z1PK0@?_LvV3nV5X*hxF}bXfKX}DtL=R;j>?en_sT7=_pUrb{;Rxt`GQ>B`3hbBg&V}*Y={XB!)9QLw+ZbFAElDlHpvO-!5MFPtSWN=e_<vmuLO%pRfDf<MWg5;Z8o;sUfc7&#EWGsZM^>m>-XSoQ}P6wT9$Yq0N%pg6}ycP1kE<cBN?CEMyk@kvGeuj?FRVSE+iKwMx#LUoX3kQ+x+-Y<qGap=uwQHAE&ou<!JhdA0cbo)Xc$zwk-N0Y^{#U-z`Gk`T7VVu=5-LVl7S(h%%(PVvE2weJ{hA%3q5)jVe3#zah1fMwqRN)Oz}r`_Wh?q&Dt`tSag_5l(9b#>m;!Ma&A^(v3y<=3%g&xli<wU<1ODNP)CX{0DA`~^>EYySb4lWnp'), 'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml': ('d04a6dc70213d8b549bac30c11cc15eaf0182dea', 'c-oazO>f&U488kT5J7>Q<b1E0feuTDVC`XD&?UPDvdlDEZON0Uq-oLrKFN-gG>5J8!GKBnk?-+IiWiu`#L*fRNx=zWb`OM41ei&RBCV1LV5`mJD%abk;CUVb0NPRM$krbK1rpCV@ugJcp_(wjhUd<=xOjPiUplq1L7^X%e8zZ>5TE@Dudh*5qA8@cQmd+i&{fJNV321~6p%vv09N-?6`T7e2(l;~@ifOHqZ;aos(Ry;Wu76p)G2bTKa9J>DnqhBKOZZka)iF`=slz>mX@%z@xIO9NCt$exPfDP0$<iB9z(Aa0;SP}f-r-EOVto3FA!MmjKG87&W3rp2szsk0n0;u9%KVC?Bj@YF-rNkI~w;#8Nd86>~%$N-0NQsQvR`<_6|5(N$cYpgVw8>;Db-NG{%kR5tlB{mj-`3v=pb@Vr<vEVOKvT_dr0#d9vAQ9F3Khm@t?H_wn4%z4C87DY7Lu7Fk1sd0mkeI>UdK`j%Sfwqvl=R+2WmI%PYDT{KH7cV`<oT1cyW2mW+;-xOtz{(LA-a&zLS!vr!*-neV;umnD_Q`S3LYc&9N3+xB5>qeN)|4&;@%&I*=>*DL}{AO{zoc^5N&6l&u{HE0;Ss-;@aX0xk4HdOPkJ;~w`D`(7oe6S!Lu3$ku;sgh|3PWRyhAf5&>Z#fetF+vxVnP2mjT;vb!#W>=nof(d71')}

# Both historical complete tuples retain the original Sync validation recipe.
# The active workflow may already be generation22 in a shallow source checkout.
_HISTORICAL_METADATA_WORKFLOWS['.github/workflows/sync-validation.yml'] = ('55d08b65a987224ce576459cede693cfd49375f6', 'c-rk5YjfMU@w<Kns`Ffun}T{+q#lhs&gIm^J;!!rJ8dU*H6RE|uql!TKsmZ3{q0=<ltk)bD{01;59coyfZfGn-@E()ohve80g_23C__mc&HjP{mPX0UED#A56No00G-8S&B{Hc1{w@(WVU*nA5sR51iYGB5!Guc*znn@;Caj0fXE8-n67j$QR74izjVEaD<445fG*i-{i4ZKZ+n+yIDoNa{pv8T|fXkF9I@X&g$FaW=DxmhzN5O70E?CghOtU{DHA~@UsRWNlpL2{!60ohHbewPst0dJFWe>d<ER(Pik|^>Cy}6o`NktO!i0yc3nnlr212U<0L}4FNMnUdFpGY>8WAdeVV@86n!J9BK+U>$h%0#YzqYy%KsR_8cqLmXX7OUlk76Z=3FyE~J6wN@3F`a25Bavh&+yUl-m*#>C=28@<wimdF#FRyt#~9Qy5==_VaHVpc_=dHd60>$=E%IHy2Tupi&5dJ`#QZmFx*8D7S7L2inV-cf!_AgcZ<!OtCoIVnp71zR4DM^XW}n5=xow`l>klsa!?$mahZp_xi{aq%<fK37p;{(IE#iLdR(Um_$F<u@1SEjr7#zzWgTti@8^<}nFUO4DAh>kllKHC=kwYQ`#tOXTil|YI0SJft!9Hy@nM(+DebTABou(U*w%2OZX`|C<w)cI~t@{o11Ddv-y3<$?yyI%zTdY7LEbO5P;c;OPymQ=}GgaJYLUO4v1q%W@;3NXxz>_3fdD(y&PEo|C44n-SH{fcvpjD8n{`>jGd4G8R`bDo8Mb;d~+Q$6v)$8HK>9740i!*{}Wxk`58y1)0UiV-8vYqzasmeHS`h!>ZFtqTfGS=DU@$qobe|rhWQ9@id@Lcv8SmLJw1<4e`EK5+zQx*~)70%wjN7cQ#psMKLzvw^j>$ppBc=fSW|GbB;u2!MvPu~rC@#x*ai?7Ww8n}C<(XM`4K>+*BNOZ9GbTmdJ<)|uHn#kJTtD}q8mp=oQv(xjVi_^isYFboqP$K?p_3EeBw+IX5Xv1){8lFFY4%_yY>NDWxpd_nx=I0c&`nOY9%5OUbYYUKECtMA;QYy%HL25%77&F8tlS~mmVmb&0HlCR~jOS{og7-agnD_!;upwmegu+S4AoXLYPc%UDYog0h4A?BzKv3OC76B(v<b;Ny)vynVotdmBImG0}bsSQl#oQK?c8xD@PJii_M57CmmB27K{oB!T87i+g%79-J2fz3D_E%ig@eFJ@-k;}|no1IIcbzOTo9Zk<S#6%$vDT!M&I;%lTb*H3*J2Dd4h(>Q<$>h%^5X3BqFTaOy3z6%#wGx9$h5O1_A(4r0isyjtcJVN1xDZC;$Q~`FIOy}Shed-tvaj)S`14VYwhIQ%UA;xwfyt_W#lMbdY#2wAwT0$V8sVTQWhy$Gj*1g5(}IUlgK=lGM;V+UzTOgwM^m_cRPoql%)mfof#!AT`BC@`o^)>I#w&viAc=QpAOKIh>ZxHVL!>hX@e)|)2CH0&`?1_vkCaLVdTk{&;}VYOR+VhLwHu3`gM;INS1CGhV53P+X*^etJ{Iyme=l3uR%<B^PGLBzBRmAf_SP!kS-6a`%a@-eMk@|pm~tk?<t8GSU7C9y4`lY-Ry!eSh(+Yx?Zcrn()tSxy%i8@bA+7j+KLZj~q0)f)tt$%i!;1N*)$Ks3XKU0Z)Q-_(YfT_dn|zs2=(r3q!x|vX<NOn{K`CdZ68I!}IE%A5bq0sULPdqh8l(-}5Z!IHASyGuu`wHpxV(;MLa^p516y*HVsD&@mR?Z632Fw|tEh)@#8mNT66!(4Iq4n4lNbv~IoLfWcdsJZOO;R&whOI6Qv|2Gha$LI(&aU?8PRglFjA1&RnkGowRX7BPIQbnHO4Dqu7sdSozVE~N4)HgOydJR9j?tF*|^)0+{7?l9yd=nVW(G%<iH*R2sRa{v#bH_Z)unz9mb&Bnus%s>lr)6pG|gXFHc#)pRsoGhNSvR8Qd9rNj!K+6{yV0huJa+jO#rpFe!0Umvc!z2orh`?ZVUWqh__Ylk)(E<jn)^|+KisXg^J){9YphD-1d+BP~ZQ5JtVdLRk4-b;Y;H4=Hg4kv{R%!Q=v9f}AqF}hOnMwdfX0mpsjl7r}mR75?JCC7O5h4-bE0}!%B}nvExo?d;;Kx6h|I%t)uTGfKB88vc9KtI>csayMz&V2gg$QT|WTJ%tW$hT20fP9WM^!-vC9loH%b~&lk%%5Hf~&>)BQKcNkJh4?velCvl??kQ?~VqiCvW;Ex@F9ZYOEt-Y0hB6n4C$fAWq#OFi4P<LsF2)BoR<)>S#{YFpEJQQ^=Yy{v1LY5wSd|7wEvSM@tR#qz`prMN%x1M9tSRQ+BSjUZLU%nu0L$nn|;W^;;x{%>wwQV>1J?bTk?0<qJ_4QjzZNFzn7V4z|M*=q49su_jf^hjqFVkVZ(3`k+?q<Q)?{oS|HgYt7HRXPldi$*wz^$-(Ys(*NgK|K&v=3fTTJ{5U$zyQYoA?J}PYe|f+4M>F-!nyJTWjm*UT(Hf(<-0{-Ps(b79`MY&fxx?BK^-}CI(<P({?~4yLpm9BwUZ0+Rv+(|ye*4Fq<O^K;p|tXyyZmEML%w&Xzl4vmBq)9@HFc2|yHMq_jYM~3CZ9e-KmLfGe*0m<vn_3RW;nz|C?3Mzq2H#i=aF{1$voflL*MPNpdL_Y!`=NRX|=mSyWQ!AcBD|hZ=_%(u=@Ege>yJ24Df;>55O;0H;K}{fZ8-*{#2^}Hz=oczA*XP2FRbZrgsO2W)8kAYcmP0ix%~6m8m;ytp?q&fr@(Qj)=H4Q`cWpwKM`yc@MQK{{ur>)>r')

_ORIGINAL_DEFAULT_REPOSITORY_WORKFLOW = ('81bcf1933edc435826e2de411a777cccd4dec7c7', 'c-rk+S#KLT5`OouptFOq1uW&*iFdMEWU)>x#GXSAY&na;U?5Q4l*G72_K<AZ+R6O)Ena=7TSpw*2m<LzO%|`JuTJuB=v2rl;Tma~DNSRPlIVtvDH>BwCDBaqe<2cSHnabcq<>^gQU!lzjNZZkP2`wrl!}B!^Y#uWQ`$k7G!=?zA?GNX(C9|($c$sx_uZd=qWv+`lWf?gGs^YAw4>Lr(O#M*$-pc@mEJ?&e~<Pngl)4C*n}aaF@x<|qTLEjG$DLUReMMjwNo_qYNiv4K7B&XV?{h~wM_T&4J2ep6SITGNlG*s4^%C)l?s{dY1^ak0x99K6fDMx;A0#!GUh^Q7OA~f%Z}Z<m{F-I;vk0^MN_ItOf*4U@KlO8i>O4iBfFagQXyl;2}t6Pj3jKtA}2{h{MTPQf_HWhDl^`EBc$gkRqiiFA_X+W{zKBrr<(I<A_ZsvqrSz7#(#JQ_^+HH@O>-f%_tGKgP5t5=xE|rV?52YUl}2Q4eV<Sh*QjM)%{|sBFR#75<pwVk)BW#iD{ZpIC%`<j3^#SN>MQyX+~u}gE?Ra4TVT3;iY*;BujM1=mX7LJ?i5Q8j(cNos`Ncvvb;wMuKY)sp<eBiFe>L%A}+`nw#FS6j^Gzf=Xbg64)q01rlW`w0Slif=ml^Njd_7*-=}y*lU%C8kDfuV!r}%i*S$+;So(R;}}%MqQT4eqZnEN25rJhWHO=-X3kojWPmKL&4d)azeJkeX^U_N)=>v-V9G4*0%*){0XVMFF{;|;5L0O~3t+!MxhGSgx2S#4cKbRAYNifSiSvWnmG5+WK27YXTOba*Dw&i4vm10qduy{l1DpUnU?-@)4sfD02Ei;qEk_YaZpmEj+cozsZF_+f41faDWH+g@C;}MUgRCdMVQFg4^OP`j+H(brjC5{4OGYrn1>VRjYz%oe%(%|*(aZMpm(B~ZDFqhdDdWIMnE%)|LsQvFgtHF>Pv#D*5X+>>OU+ZaD`d_x*wG@U<w0pecrgY#3sObFurobhN*)M`A<hYx2e_6cD`@aX1JJ&Yz&5pXnF>`g*vD=Iuy-+olP*72jj}$8p<g@RG}ebsKn(^f*;=ElPqG;&8ma4(DXP~_0W`%xuiAsc^Dh~_NLZg@y)<f+^+{GrqfAsE%DB-2P`S0^bILG@r42!#)9ANGZH)rv8H2HLjE{W=;1_pZ$lH(utLs4apBM3q=;aYTCL}r@l2^}<UmYFC<cEK}JbWG<zB)Ym;l+^r^ZD@5&r<eECJGzX9Z|b5DQzFT4TcgN{-of9!2wJZc3iYlshH9@0=XF<53yZ{@B#@$rczNH4$wiL@-BqDi!HSn7^;I>s8^!^Tc$AtsjzHBYrW1wU_(?N%7nthj3qIyggO-=UD8O5O+=2YsmtSH=Rt);##!1Z23aPCRT$vhHu!JKX9fG;oelaIKXrQ*8EA1sd70C_lm7XK?%<bh|K#+fe=<1l^}D^k8`JEmYUbI+9IGb1dVAJAz5e;U_wKVMRv?WyOAJ`^$-(z@(7$nkiMgH#{sQ51gs%{O6F_sYM6?du?Q~vv_A&=SChi+O`|jO&|LpqBp!)$BGI)Q|KYJEBZDzbk(L4F2Ybe|?ir$Os{`>3xvju^Z*rh<Z3DG9`F$!dKmEM74vRcZ*&P>p;-b<P=$ArpzkEqv9IrE+8?IQ|FA&zNkx{tm{Ys;F7tFeg_BN|CDwH%~(a5@ksR5faQx*yMsRvCL+MqGf|#^|!PeGQfh;n$gov6_%#;MLj5rr7d)^3{Z=VV7HMJ;TbD@{4)pc$9N&Lta6T5t|Gg!q&BZRMsT>=&uwJ7v{?528}^IqyS}-X12W!Y_ruNFP;6oE|hVX7{x7D6LJK5!SHRG1^D2o64|>%#_p{#ec5&SHl$GQ`$3MoTRv_Rx#z&HPk3CGxvevPPMvX0{h+LDjfI0E<X<5m3qT*KcfL3yU6y_}<f@OVfBrx#6wp)T8u%5c(S8$sJvB3{jDXLjYQrW&jD<Gdn{pH7GOE^&HyN1O;BUV>9B<Y4A=TFdaE1Qn!kRB6-c3SVl5x|!6dGtP?Oi4JhP*eQre2O%HB*rRdqzEh>-8(GP<>DFHK~3Rd99RDIp<axA5s~^(7@|PeQYj5Z6vyNRj5^yY*dC?HNi%8s8tgz6ry4gWm9Odg^nlC=*oI4^twW~sNKKW_5L10o!=W3eS^(=C+(+MeF@M+6pH`%HWFddFraek0bDgh4GIvqyEPV%Wh^Qj_mu%}Fai<IuO=Q}J!)&NP>~w#*X{)KGi{yUqv5#*iY3wL2ri)WS0W}Ql*ERl{%uA+P0{sD8sJR;+H9)p%-h=Q2gCPg-&(J}P0MSkMfeq}_oYhr6JD>GdU5Fv=6==qaL^A1c5_%`N*Fiy5CNJfhi19j`~KJd*+uX4qSycL<$1sR=GT7r?Zs*L^<hy5wk6-139#8M)PT*~i^XF4w^MDZ9c_gNuF>Wmc*(Pq%1(D1&D=%?tW`3`;pt%R>~S#5{;Lw=__msxSZuFC2bXURa7a5IOjR$bE%0TW%m@Qpk<{N}`bSl0NJm2Ys}h*JbQ`j@vYT7kvOS=8a8-S{?jeGMtoLy88+wWGHM)yOzqK{$O|iRE__9YC)>S}JLW5dP%^T1WOK7;FD{Htdo`6kE;H6h$>yP2SQwwCxU@o)D(+GHu@b;&{W%ug(=l+#Lh890wUG$tuZIuDA$uo-kT@lZmk6m-|X?KLp;en#E@q1j0?))F&V*}*')

def historical_metadata_workflow(relative,generation,root):
    if generation=='protected-producer-original-default-v1' and relative.endswith('/producers/repository-checks.yml'):
        oid,encoded=_ORIGINAL_DEFAULT_REPOSITORY_WORKFLOW
        raw=zlib.decompress(base64.b85decode(encoded))
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==oid
        return raw
    historical = generation in {'protected-producer-metadata-ci-v1','protected-producer-seven-target-ci-v1'} \
        and (relative == '.github/workflows/sync-validation.yml'
             or relative.endswith('/metadata-edits/pr-metadata-context.yml')
             or generation=='protected-producer-seven-target-ci-v1' and relative.endswith('/producers/repository-checks.yml'))
    if historical:
        oid,encoded=_HISTORICAL_METADATA_WORKFLOWS[relative]
        raw=zlib.decompress(base64.b85decode(encoded))
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==oid
        return raw
    return (root/relative).read_bytes()


class FakeApi:
    def __init__(self, case):
        self.case = case
        self.calls = []
        self.mutate = lambda endpoint, value: value

    def json(self, endpoint):
        self.calls.append(endpoint)
        case, binding = self.case, self.case.binding
        require = lambda condition: self._unexpected(endpoint) if not condition else None
        require(endpoint == A.PREFIX or endpoint.startswith(A.PREFIX + "/"))
        path = endpoint[len(A.PREFIX):].lstrip("/").split("?", 1)[0]
        query = parse_qs(urlsplit(endpoint).query)
        if not path:
            result = {"id": 1319052603, "full_name": A.REPOSITORY, "default_branch": "main"}
        elif path == "pulls/17":
            result = {"number": 17, "state": "open", "merge_commit_sha": binding["merge_sha"],
                      **{side: {"repo": {"id": 1319052603, "full_name": A.REPOSITORY},
                                "ref": binding[side + "_ref"], "sha": binding[side + "_sha"]} for side in ("base", "head")}}
        elif path == "commits/refs/pull/17/merge":
            result = {"sha": binding["merge_sha"], "commit": {"tree": {"sha": binding["merge_tree"]}},
                      "parents": [{"sha": sha} for sha in binding["merge_parents"]]}
        elif path.startswith("branches/"):
            target = unquote(path.removeprefix("branches/"))
            require(target == binding["base_ref"])
            result = {"name": target, "protected": True, "commit": {"sha": binding["base_sha"]}}
        elif path.startswith("compare/"):
            snapshot, effective = path.removeprefix("compare/").split("...")
            require(effective == binding["base_sha"] and query == {"per_page": ["1"]})
            known = snapshot in getattr(case, "base_ancestors", set())
            result = {"status": "ahead" if known else "diverged", "ahead_by": 1,
                      "behind_by": 0, "total_commits": 1, "commits": [{"sha": effective}], "files": [],
                      "base_commit": {"sha": snapshot},
                      "merge_base_commit": {"sha": snapshot if known else "f" * 40}}
        elif path.startswith("git/ref/"):
            ref = unquote(path[len("git/ref/"):])
            identities = {"heads/main": binding["base_sha"], "heads/" + binding["head_ref"]: binding["head_sha"]}
            require(ref in identities)
            result = {"ref": "refs/" + ref, "object": {"type": "commit", "sha": identities[ref]}}
        elif path.startswith("git/commits/"):
            revision = path.rsplit("/",1)[1]
            if revision == binding["merge_sha"]:
                tree,parents=binding["merge_tree"],binding["merge_parents"]
            elif revision == binding["head_sha"]:
                tree,parents="8"*40,["7"*40]
            else:
                require(revision in case.originals)
                tree,parents=case.originals[revision]
            result = {"sha": revision, "tree": {"sha": tree}, "parents": [{"sha": sha} for sha in parents]}
        elif path.startswith("git/trees/"):
            identity = path.rsplit("/", 1)[1]
            if identity == binding["merge_tree"] or identity in {tree for tree,_ in case.originals.values()}:
                entries = [{"path": ".github", "mode": "040000", "type": "tree", "sha": "1" * 40}]
            elif identity == "1" * 40:
                entries = [{"path": "workflows", "mode": "040000", "type": "tree", "sha": "2" * 40}]
            else:
                require(identity == "2" * 40)
                entries = [{"path": name.rsplit("/", 1)[1], **entry} for name, entry in case.generation.items()]
            result = {"sha": identity, "truncated": False, "tree": entries}
        elif path == "actions/workflows/99/runs":
            require(query.get("head_sha") == [binding["head_sha"]] and "status" not in query and "created" not in query)
            result = self.page(list(case.runs.values()), "workflow_runs", query)
        elif path.startswith("actions/runs/"):
            parts = path.split("/")
            run_id = int(parts[2]); require(run_id in case.runs)
            if len(parts) == 3 or len(parts) == 5 and parts[3] == "attempts":
                result = deepcopy(case.runs[run_id])
                if len(parts) == 5:
                    require(int(parts[4]) == result["run_attempt"])
            elif parts[-1] == "jobs":
                result = self.page(case.jobs[run_id], "jobs", query)
            elif parts[-1] == "artifacts":
                result = self.page(case.artifacts[run_id], "artifacts", query)
            else:
                self._unexpected(endpoint)
        elif path.startswith("check-suites/"):
            run = next(value for value in case.runs.values() if value["check_suite_id"] == int(path.rsplit("/", 1)[1]))
            result = {"id": run["check_suite_id"], "head_sha": binding["head_sha"],
                      "repository": {"id": 1319052603, "full_name": A.REPOSITORY}, "app": {"id": 15368}}
        elif path.startswith("check-runs/"):
            identity = int(path.rsplit("/", 1)[1]); job = next(job for jobs in case.jobs.values() for job in jobs if job["id"] == identity)
            result = {"id": identity, "head_sha": job["head_sha"], "app": {"id": 15368},
                      "check_suite": {"id": case.runs[job["run_id"]]["check_suite_id"]},
                      **{key: job[key] for key in ("name", "status", "conclusion", "started_at", "completed_at")}}
        elif path.startswith("actions/artifacts/"):
            identity = int(path.rsplit("/", 1)[1])
            result = next(item for items in case.artifacts.values() for item in items if item["id"] == identity)
        else:
            self._unexpected(endpoint)
        return self.mutate(endpoint, deepcopy(result))

    def page(self, items, field, query):
        page = int(query["page"][0]); return {"total_count": len(items), field: items[(page - 1) * 100:page * 100]}

    def bytes(self, endpoint):
        self.calls.append(endpoint)
        return self.case.archives[int(endpoint.split("/")[-2])]

    def _unexpected(self, endpoint):
        raise AssertionError("unexpected fake GET endpoint")


class AdapterTests(unittest.TestCase):
    def setUp(self):
        example = FIXTURES.ProducerProtocolTests()
        example.setUp()
        self.binding, self.plan, self.context = example.binding, example.plan, example.context
        self.pp = replace(example.policy, workflow_path=".github/workflows/project-tests.yml", events=("pull_request",),
                          workflow_ref="refs/pull/17/merge")
        self.generation = {path: {"mode": "100644", "type": "blob", "sha": str(index + 4) * 40}
                           for index, path in enumerate(sorted(A.WORKFLOWS))}
        self.generation[self.pp.workflow_path]["sha"] = self.pp.workflow_blob
        self.policy = A.AdapterPolicy(self.pp, 99, ".github/workflows/repository-checks.yml", {"reviewed": self.generation},
                                      "project / Publish producer descriptor", {"shared-host": "project / Shared tests"},
                                      "project / Publish final producer ")
        self.runs, self.jobs, self.artifacts, self.archives, self.originals = {}, {}, {}, {}, {}
        self.aggregate = deepcopy(example.aggregate)
        self.add_run(replace(example.run, workflow_path=self.pp.workflow_path, workflow_commit=self.binding["merge_sha"],
                             workflow_ref=self.pp.workflow_ref, event="pull_request"))
        self.api = FakeApi(self)
        self.adapter = A.Adapter(self.api)

    def add_run(self, run, *, descriptor=True):
        self.runs[run.run_id] = {
            "id": run.run_id, "workflow_id": 99, "run_number": run.run_id, "check_suite_id": run.run_id + 1000,
            "path": self.policy.caller_path, "event": "pull_request", "head_sha": self.binding["head_sha"],
            "head_branch": self.binding["head_ref"], "repository": {"id": 1319052603, "full_name": A.REPOSITORY},
            "head_repository": {"id": 1319052603, "full_name": A.REPOSITORY}, "pull_requests": [{"number": 17}],
            "referenced_workflows": [{"path": A.REPOSITORY + "/" + self.pp.workflow_path + "@" + self.binding["merge_sha"],
                                      "sha": self.binding["merge_sha"], "ref": self.pp.workflow_ref}],
            "run_attempt": run.attempt, "run_started_at": run.attempt_started_at,
            "status": run.status, "conclusion": run.conclusion, "updated_at": "2026-10-15T10:04:30Z"}
        self.jobs[run.run_id] = [{"id": job.job_id, "run_id": run.run_id, "run_attempt": job.attempt,
                                "head_sha": self.binding["head_sha"], "name": name, "status": job.status,
                                "conclusion": job.conclusion, "started_at": job.started_at, "completed_at": job.completed_at,
                                "check_run_url": f"https://api.github.com/{A.PREFIX}/check-runs/{job.job_id}"}
                               for name, job in [(self.policy.publisher_job, run.publisher),
                                                 *[(self.policy.owner_jobs[name], job) for name, job in run.owners.items()]] if job is not None]
        if run.final_publisher is not None:
            publication = run.final_publisher
            job = publication.job
            self.jobs[run.run_id].append({"id": job.job_id, "run_id": run.run_id, "run_attempt": job.attempt,
                "head_sha": self.binding["head_sha"], "name": self.policy.final_publisher_prefix + publication.receipt_sha256,
                "status": job.status, "conclusion": job.conclusion, "started_at": job.started_at,
                "completed_at": job.completed_at,
                "check_run_url": f"https://api.github.com/{A.PREFIX}/check-runs/{job.job_id}"})
        self.artifacts[run.run_id] = []
        if descriptor:
            value = P.descriptor(self.binding, self.plan, self.pp, run)
            self.artifact(run, "descriptor", value)
            aggregate = deepcopy(self.aggregate)
            aggregate["descriptor_digest"] = value["descriptor_digest"]
            self.artifact(run, "aggregate", FIXTURES.signed(aggregate, "aggregate_digest"))

    def artifact(self, run, kind, value):
        raw = P.artifact_bytes(value, kind)
        identity = run.run_id * 10 + (1 if kind == "descriptor" else 2)
        item = {"id": identity, "name": f"ci-{kind}-{run.run_id}-{run.attempt}", "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
                "size_in_bytes": len(raw), "expired": False, "created_at": run.publisher.completed_at if kind == "descriptor" else "2026-10-15T10:04:30Z",
                "expires_at": "2026-10-17T10:00:00Z", "workflow_run": {"id": run.run_id, "repository_id": 1319052603,
                "head_repository_id": 1319052603, "head_sha": self.binding["head_sha"]}}
        self.artifacts[run.run_id].append(item); self.archives[identity] = raw

    def capture(self):
        return self.adapter.capture(17, self.plan, self.policy, now=NOW)

    def verify(self):
        return self.adapter.verify(17, self.plan, self.policy, {"shared-host": self.context}, clock=lambda: NOW)

    def authority(self):
        snapshot = self.capture()
        return P.select_authority(snapshot.observations, snapshot.binding, self.plan, self.pp,
                                  inventory_complete=snapshot.inventory_complete, now=NOW)

    def test_complete_api_chain_and_inner_receipt_preserve_original_expiry(self):
        with patch.object(P.execution, "execute", side_effect=AssertionError("read-only verifier")):
            result = self.verify()
        self.assertTrue(result["verified"])
        self.assertEqual(result["expires_at"], self.aggregate["expires_at"])
        self.assertEqual(result["source_chain"]["producer_commit"], self.binding["merge_sha"])
        self.assertNotEqual(result["source_chain"]["producer_commit"], self.binding["head_sha"])
        self.assertTrue(all(path.startswith(A.PREFIX) for path in self.api.calls))

    def test_run_head_is_never_used_as_original_merge_or_owner_source(self):
        def changed(endpoint, value):
            if "/attempts/" in endpoint and "referenced_workflows" in value:
                value["referenced_workflows"][0]["sha"] = self.binding["head_sha"]
            return value
        self.api.mutate = changed
        self.assertEqual(self.authority()["state"], "unresolved")
        with self.assertRaises(P.ProtocolError): self.verify()

    def test_artifact_claims_cannot_supply_missing_api_chain_or_check_app(self):
        cases = (lambda value: value.update(referenced_workflows=[]),
                 lambda value: value["repository"].update(id=42),
                 lambda value: value["pull_requests"][0].update(number=18))
        for change in cases:
            with self.subTest(change=change):
                def mutate(endpoint, value):
                    if "/attempts/" in endpoint and "referenced_workflows" in value: change(value)
                    return value
                self.api.mutate = mutate
                self.assertEqual(self.authority()["state"], "unresolved")
        self.api.mutate = lambda endpoint, value: ({**value, "app": {"id": 42}} if "/check-runs/" in endpoint else value)
        self.assertEqual(self.authority()["state"], "unresolved")

    def test_foreign_remote_duplicate_and_nonlocal_references_fail_closed(self):
        for mode in ("foreign", "duplicate", "nonlocal", "stale"):
            def mutate(endpoint, value):
                if "/attempts/" in endpoint and "referenced_workflows" in value:
                    item = value["referenced_workflows"][0]
                    if mode == "foreign": item["path"] = item["path"].replace(A.REPOSITORY, "overte-org/overte")
                    elif mode == "duplicate": value["referenced_workflows"].append(deepcopy(item))
                    elif mode == "nonlocal": item["ref"] = "refs/heads/main"
                    else: item["sha"] = "f" * 40
                return value
            self.api.mutate = mutate
            with self.subTest(mode=mode): self.assertEqual(self.authority()["state"], "unresolved")

    def test_original_caller_or_mixed_workflow_generation_cannot_be_borrowed(self):
        for field, value in (("sha", "f" * 40), ("mode", "100755"), ("type", "commit")):
            def mutate(endpoint, result):
                if endpoint.endswith("git/trees/" + "2" * 40):
                    next(entry for entry in result["tree"] if entry["path"] == "repository-checks.yml")[field] = value
                return result
            self.api.mutate = mutate
            with self.subTest(field=field): self.assertEqual(self.authority()["state"], "unresolved")

    def test_latest_queued_unclassified_failed_or_tied_run_never_uses_old_green(self):
        original = self.capture().observations[0].run
        for status, conclusion, descriptor in (("queued", None, False), ("completed", "failure", True)):
            later = replace(original, run_id=101, status=status, conclusion=conclusion,
                            attempt_started_at="2026-10-15T10:01:00Z", publisher=None, owners={}, final_publisher=None)
            # Failure with descriptor needs an actual independently bound publisher.
            if descriptor:
                later = replace(later, publisher=replace(original.publisher, job_id=111,
                                started_at="2026-10-15T10:01:00Z", completed_at="2026-10-15T10:01:30Z"))
            self.add_run(later, descriptor=descriptor)
            with self.subTest(status=status):
                self.assertEqual(self.authority()["state"], "failed" if descriptor else "unresolved")
                with self.assertRaises(P.ProtocolError): self.verify()
            del self.runs[101]; del self.jobs[101]; del self.artifacts[101]
        tied = replace(original, run_id=102, publisher=replace(original.publisher, job_id=112),
                       owners={name: replace(job, job_id=122) for name, job in original.owners.items()},
                       final_publisher=replace(original.final_publisher,
                                               job=replace(original.final_publisher.job, job_id=132)))
        self.add_run(tied)
        self.assertEqual(self.authority()["state"], "unresolved")

    def test_latest_attempt_is_read_and_mixed_rerun_jobs_never_reuse_attempt_one(self):
        run = self.capture().observations[0].run
        current = replace(run, attempt=2, latest_attempt=2,
                          publisher=replace(run.publisher, attempt=2,job_id=210),
                          owners={name: replace(job, attempt=2,job_id=220) for name, job in run.owners.items()},
                          final_publisher=replace(run.final_publisher,
                                                  job=replace(run.final_publisher.job, attempt=2, job_id=230)))
        self.add_run(current)
        snapshot = self.capture()
        self.assertFalse(snapshot.inventory_complete)
        self.assertIn('original-attempt-unavailable',snapshot.unavailable)
        self.assertEqual(snapshot.observations,[])
        self.assertFalse(any("/attempts/2" in path for path in self.api.calls))
        with self.assertRaises(P.ProtocolError): self.verify()
        next(job for job in self.jobs[100] if job["name"] == self.policy.owner_jobs["shared-host"])["run_attempt"] = 1
        self.assertEqual(self.authority()["state"], "unresolved")

    def test_current_merge_uses_supported_commit_ref_without_legacy_payload_field(self):
        for legacy in ('missing',None,'e'*40):
            def mutate(endpoint,value):
                if endpoint.endswith('pulls/17'):
                    if legacy=='missing':value.pop('merge_commit_sha')
                    else:value['merge_commit_sha']=legacy
                return value
            self.api.mutate=mutate
            with self.subTest(legacy=legacy):
                binding,refs=self.adapter.current(17)
                self.assertEqual(binding,self.binding)
                self.assertEqual(refs['merge'],self.binding['merge_sha'])
        self.assertTrue(any(path.endswith('/commits/refs/pull/17/merge') for path in self.api.calls))
        self.assertFalse(any('/git/ref/pull/' in path for path in self.api.calls))

    def test_valid_branch_uri_characters_are_escaped_inside_fixed_fork_endpoints(self):
        self.binding['head_ref']='fix/main/hash#percent%20'
        binding,_=self.adapter.current(17)
        self.assertEqual(binding['head_ref'],self.binding['head_ref'])
        self.assertTrue(any(path.endswith('/git/ref/heads/fix/main/hash%23percent%2520') for path in self.api.calls))
        self.assertTrue(all('#' not in path and path.startswith(A.PREFIX) for path in self.api.calls))

    def test_current_ref_must_match_immutable_tree_ordered_parents_and_fresh_branches(self):
        for mode in ('tree','parents','head-as-merge','base-ref','head-ref'):
            def mutate(endpoint,value):
                if endpoint.endswith('/commits/refs/pull/17/merge'):
                    if mode=='tree':value['commit']['tree']['sha']='f'*40
                    elif mode=='parents':value['parents'].reverse()
                    elif mode=='head-as-merge':value['sha']=self.binding['head_sha']
                elif mode=='base-ref' and endpoint.endswith('/git/ref/heads/main'):value['object']['sha']='f'*40
                elif mode=='head-ref' and '/git/ref/heads/fix/' in endpoint:value['object']['sha']='f'*40
                return value
            self.api.mutate=mutate
            with self.subTest(mode=mode),self.assertRaises(P.ProtocolError):self.adapter.current(17)

    def add_other_candidate(self,status='completed',conclusion='failure'):
        run=self.capture().observations[0].run
        other=replace(run,run_id=101,status=status,conclusion=conclusion,
                      attempt_started_at='2026-10-15T10:01:00Z',publisher=None,owners={})
        self.add_run(other,descriptor=False)
        self.originals['f'*40]=('9'*40,['8'*40,self.binding['head_sha']])
        source=self.runs[101]['referenced_workflows'][0]
        source.update(sha='f'*40,path=A.REPOSITORY+'/'+self.pp.workflow_path+'@'+'f'*40)

    def test_authenticated_different_original_candidate_is_reported_without_reusing_it(self):
        self.add_other_candidate()
        snapshot=self.capture()
        self.assertTrue(snapshot.inventory_complete)
        self.assertEqual([item.run.run_id for item in snapshot.observations],[100])
        other=snapshot.other_candidates[101]
        self.assertEqual(other['candidate'],{'merge_sha':'f'*40,'merge_tree':'9'*40,
                                           'merge_parents':['8'*40,self.binding['head_sha']]})
        self.assertEqual(self.verify()['run_id'],100)
        self.assertFalse(any('/runs/101/artifacts' in path for path in self.api.calls))

    def test_other_candidate_cannot_hide_unknown_chain_parents_app_or_attempt(self):
        self.add_other_candidate()
        for mode in ('parent','workflow','app','attempt','missing-source'):
            def mutate(endpoint,value):
                if mode=='parent' and endpoint.endswith('/git/commits/'+'f'*40):value['parents'][1]['sha']='7'*40
                elif mode=='workflow' and endpoint.endswith('/git/trees/'+'2'*40):
                    value['tree'][0]['mode']='100755'
                elif mode=='app' and endpoint.endswith('/check-suites/1101'):value['app']['id']=42
                elif mode=='attempt' and endpoint.endswith('/actions/runs/101'):value['run_attempt']=2
                elif mode=='missing-source' and '/actions/runs/101' in endpoint and 'referenced_workflows' in value:
                    value['referenced_workflows']=[]
                return value
            self.api.mutate=mutate
            with self.subTest(mode=mode):
                snapshot=self.capture()
                self.assertFalse(snapshot.inventory_complete)
                with self.assertRaises(P.ProtocolError):self.verify()

    def test_new_current_candidate_failure_still_blocks_even_with_known_other_context(self):
        self.add_other_candidate()
        current=self.capture().observations[0].run
        failed=replace(current,run_id=102,conclusion='failure',attempt_started_at='2026-10-15T10:01:00Z',
                       publisher=replace(current.publisher,job_id=112,started_at='2026-10-15T10:01:00Z',
                                         completed_at='2026-10-15T10:01:30Z'),owners={},final_publisher=None)
        self.add_run(failed)
        with self.assertRaises(P.ProtocolError):self.verify()

    def test_reused_artifact_name_foreign_owner_digest_size_and_expiry_fail(self):
        original = deepcopy(self.artifacts[100])
        for change in (lambda rows: rows.append({**rows[0], "id": 999}),
                       lambda rows: rows[0].update(digest="unavailable"),
                       lambda rows: rows[0].update(size_in_bytes=P._MAX_ARCHIVE + 1),
                       lambda rows: rows[0].update(expired=True),
                       lambda rows: rows[0]["workflow_run"].update(id=999),
                       lambda rows: rows[0]["workflow_run"].update(head_sha="f" * 40)):
            self.artifacts[100] = deepcopy(original); change(self.artifacts[100])
            with self.subTest(change=change): self.assertEqual(self.authority()["state"], "unresolved")
        self.artifacts[100] = original
        self.archives[1001] = b"Tampered compressed archive"
        self.assertEqual(self.authority()["state"], "unresolved")

    def test_missing_aggregate_fails(self):
        self.artifacts[100] = self.artifacts[100][:1]
        with self.assertRaises(P.ProtocolError): self.verify()

    def test_actual_runtime_mismatch_fails(self):
        self.context = replace(self.context, environment={"different": "actual runtime"})
        with self.assertRaises(P.ProtocolError): self.verify()

    def test_missing_failed_skipped_or_pending_selected_owner_never_verifies(self):
        original = deepcopy(self.jobs[100])
        for status, conclusion in (("completed", "failure"), ("completed", "skipped"), ("queued", None)):
            self.jobs[100] = deepcopy(original)
            owner = next(job for job in self.jobs[100] if job["name"] == self.policy.owner_jobs["shared-host"])
            owner.update(status=status, conclusion=conclusion)
            with self.subTest(status=status, conclusion=conclusion), self.assertRaises(P.ProtocolError):
                self.verify()
        self.jobs[100] = [job for job in original if job["name"] != self.policy.owner_jobs["shared-host"]]
        with self.assertRaises(P.ProtocolError): self.verify()

    def test_forged_artifact_detail_and_deleted_or_replaced_archive_fail(self):
        for field, replacement in (("digest", "sha256:" + "f" * 64), ("expired", True), ("id", 999)):
            def mutate(endpoint, value):
                if endpoint.endswith("actions/artifacts/1001"):
                    value[field] = replacement
                return value
            self.api.mutate = mutate
            with self.subTest(field=field): self.assertFalse(self.capture().inventory_complete)
        self.api.mutate = lambda endpoint, value: value
        self.archives[1002] = self.archives[1001]
        with self.assertRaises(P.ProtocolError): self.verify()

    def test_initial_final_current_refs_and_new_authority_are_rechecked(self):
        count = 0
        def mutate(endpoint, value):
            nonlocal count
            if endpoint.endswith("pulls/17"):
                count += 1
                if count >= 4: value["head"]["sha"] = "f" * 40
            return value
        self.api.mutate = mutate
        with self.assertRaises(P.ProtocolError): self.verify()
        self.setUp()
        count = 0
        def new_attempt(endpoint, value):
            nonlocal count
            if "/runs?head_sha=" in endpoint:
                count += 1
                if count >= 2: value["workflow_runs"][0]["run_attempt"] = 2
            return value
        self.api.mutate = new_attempt
        self.assertFalse(self.capture().inventory_complete)
        with self.assertRaises(P.ProtocolError): self.verify()

    def test_final_aggregate_inventory_cannot_delete_replace_or_duplicate_downloaded_proof(self):
        for mode in ("deleted", "replaced", "duplicated"):
            count = 0
            def mutate(endpoint, value):
                nonlocal count
                if "/actions/runs/100/artifacts?" in endpoint:
                    count += 1
                    if count == 2:
                        if mode == "deleted": value["artifacts"] = value["artifacts"][:1]
                        elif mode == "replaced": value["artifacts"][-1]["id"] = 999
                        else: value["artifacts"].append({**value["artifacts"][-1], "id": 999})
                        value["total_count"] = len(value["artifacts"])
                return value
            self.api.mutate = mutate
            with self.subTest(mode=mode), self.assertRaises(P.ProtocolError): self.verify()

    def test_complete_pagination_and_search_cap_missing_pages_or_duplicate_ids(self):
        values = [{"id": number} for number in range(1, 102)]
        calls = []
        def pages(endpoint):
            calls.append(endpoint); page = int(parse_qs(urlsplit(endpoint).query)["page"][0])
            return {"total_count": 101, "workflow_runs": values[(page - 1) * 100:page * 100]}
        with patch.object(self.api, "json", side_effect=pages):
            self.assertEqual(len(self.adapter._pages("actions/workflows/99/runs", "workflow_runs", search=True)), 101)
        self.assertEqual(len(calls), 2)
        for value in ({"total_count": 1000, "workflow_runs": []}, {"total_count": 2, "workflow_runs": [{"id": 1}]},
                      {"total_count": 2, "workflow_runs": [{"id": 1}, {"id": 1}]}):
            with patch.object(self.api, "json", return_value=value), self.assertRaises(P.ProtocolError):
                self.adapter._pages("actions/workflows/99/runs", "workflow_runs", search=True)
        values = [{"id": number} for number in range(1, 1001)]
        def maximum(endpoint):
            page = int(parse_qs(urlsplit(endpoint).query)["page"][0])
            return {"total_count": 1000, "jobs": values[(page - 1) * 100:page * 100]}
        with patch.object(self.api, "json", side_effect=maximum):
            self.assertEqual(len(self.adapter._pages("actions/runs/100/jobs", "jobs")), 1000)
        counts = iter((101, 102))
        def changing(endpoint):
            return {"total_count": next(counts), "workflow_runs": values[:100]}
        with patch.object(self.api, "json", side_effect=changing), self.assertRaises(P.ProtocolError):
            self.adapter._pages("actions/workflows/99/runs", "workflow_runs", search=True)

    def test_final_publisher_native_commitment_is_required_and_returned(self):
        result = self.verify()
        receipt = self.aggregate["results"]["shared-host"]["receipt"]
        self.assertEqual(result["final_publisher_job_id"], 130)
        self.assertEqual(result["receipt_sha256"], hashlib.sha256(P.canonical(receipt)).hexdigest())
        self.jobs[100] = [job for job in self.jobs[100]
                          if not job["name"].startswith(self.policy.final_publisher_prefix)]
        with self.assertRaises(P.ProtocolError): self.verify()

    def test_reserved_final_publisher_malformed_duplicate_or_conflicting_jobs_deny(self):
        original = deepcopy(self.jobs[100])
        for mode in ("uppercase", "short", "suffix", "duplicate", "conflicting", "reused-owner"):
            self.jobs[100] = deepcopy(original)
            final = self.jobs[100][-1]
            if mode == "uppercase": final["name"] = self.policy.final_publisher_prefix + "A" * 64
            elif mode == "short": final["name"] = self.policy.final_publisher_prefix + "a" * 63
            elif mode == "suffix": final["name"] += " other"
            elif mode in {"duplicate", "conflicting"}:
                duplicate = {**final, "id": 131,
                             "check_run_url": f"https://api.github.com/{A.PREFIX}/check-runs/131"}
                if mode == "conflicting": duplicate["name"] = self.policy.final_publisher_prefix + "f" * 64
                self.jobs[100].append(duplicate)
            else: final["id"] = 120
            with self.subTest(mode=mode), self.assertRaises(P.ProtocolError): self.verify()

    def test_final_publisher_native_check_name_status_timing_app_and_attempt_are_bound(self):
        for key, value in (("name", self.policy.final_publisher_prefix + "f" * 64),
                           ("status", "queued"), ("conclusion", "failure"),
                           ("started_at", "2026-10-15T10:03:31Z"),
                           ("completed_at", "2026-10-15T10:04:44Z"), ("app", {"id": 42})):
            def changed(endpoint, result):
                if endpoint.endswith("/check-runs/130"): result[key] = value
                return result
            self.api.mutate = changed
            with self.subTest(key=key):
                self.assertFalse(self.capture().inventory_complete)
                with self.assertRaises(P.ProtocolError): self.verify()
        self.api.mutate = lambda endpoint, value: value
        self.jobs[100][-1]["run_attempt"] = 2
        with self.assertRaises(P.ProtocolError): self.verify()

    def test_changed_final_native_commitment_between_authority_snapshots_denies(self):
        count = 0
        def changed(endpoint, result):
            nonlocal count
            if "/actions/runs/100/attempts/1/jobs?" in endpoint:
                count += 1
                if count >= 2:
                    self.jobs[100][-1]["name"] = self.policy.final_publisher_prefix + "f" * 64
                    result["jobs"][-1] = deepcopy(self.jobs[100][-1])
            return result
        self.api.mutate = changed
        with self.assertRaises(P.ProtocolError): self.verify()

    def test_resigned_whole_receipt_cannot_replace_native_committed_bytes(self):
        aggregate = deepcopy(self.aggregate)
        receipt = aggregate["results"]["shared-host"]["receipt"]
        receipt["completed_at"] = "2026-10-15T10:02:49Z"
        aggregate["results"]["shared-host"]["receipt"] = FIXTURES.signed(receipt, "receipt_digest")
        run = self.capture().observations[0].run
        descriptor_digest = P.descriptor(self.binding, self.plan, self.pp, run)["descriptor_digest"]
        aggregate["descriptor_digest"] = descriptor_digest
        self.artifacts[100] = self.artifacts[100][:1]
        self.artifact(run, "aggregate", FIXTURES.signed(aggregate, "aggregate_digest"))
        with self.assertRaisesRegex(P.ProtocolError, "commitment"): self.verify()


class MetadataFakeApi(FakeApi):
    def json(self, endpoint):
        path = endpoint[len(A.PREFIX):].lstrip("/").split("?", 1)[0]
        trees = {
            "3" * 40: [{"path": "tools", "mode": "040000", "type": "tree", "sha": "4" * 40}],
            "4" * 40: [{"path": "repository-checks", "mode": "040000", "type": "tree", "sha": "5" * 40}],
            "5" * 40: [{"path": "metadata_context.py", "mode": "100644", "type": "blob", "sha": "6" * 40}],
        }
        if path.startswith("git/trees/") and path.rsplit("/", 1)[1] in trees:
            identity = path.rsplit("/", 1)[1]
            self.calls.append(endpoint)
            return self.mutate(endpoint, {"sha": identity, "truncated": False, "tree": deepcopy(trees[identity])})
        return super().json(endpoint)


class MetadataNonproducerTests(unittest.TestCase):
    """Finite native classification fixtures are not hosted qualification proof."""
    def setUp(self):
        self.case = AdapterTests()
        self.case.setUp()
        c = self.case
        c.generation = {**deepcopy(c.generation),
            ".github/workflows/browser-client.yml": {"mode": "100644", "type": "blob", "sha": "1" * 40},
            A.METADATA_WORKFLOW: {"mode": "100644", "type": "blob", "sha": "2" * 40}}
        self.sources = {A.METADATA_SOURCE: {"mode": "100644", "type": "blob", "sha": "6" * 40}}
        c.policy = replace(c.policy, metadata_generations={"metadata-v1": deepcopy(c.generation)},
                           metadata_sources={"metadata-v1": self.sources})
        c.originals[c.binding["base_sha"]] = ("3" * 40, ["7" * 40])
        c.runs[101] = {**deepcopy(c.runs[100]), "id": 101, "run_number": 101, "check_suite_id": 1101,
            "status": "in_progress", "conclusion": None, "run_started_at": "2026-10-15T10:04:00Z",
            "referenced_workflows": [{"path": A.REPOSITORY + "/" + A.METADATA_WORKFLOW + "@" + c.binding["merge_sha"],
                                      "sha": c.binding["merge_sha"], "ref": c.pp.workflow_ref}]}
        c.jobs[101] = [{"id": 140, "run_id": 101, "run_attempt": 1, "head_sha": c.binding["head_sha"],
            "name": A.METADATA_JOB, "status": "completed", "conclusion": "success",
            "started_at": "2026-10-15T10:04:01Z", "completed_at": "2026-10-15T10:04:20Z",
            "check_run_url": f"https://api.github.com/{A.PREFIX}/check-runs/140",
            "steps": [{"number": 1, "name": A.METADATA_STEP, "status": "completed", "conclusion": "success",
                       "started_at": "2026-10-15T10:04:02Z", "completed_at": "2026-10-15T10:04:19Z"}]}]
        c.artifacts[101] = []
        c.api = MetadataFakeApi(c)
        c.adapter = A.Adapter(c.api)

    def test_completed_native_marker_excludes_active_metadata_run_without_granting_a_result(self):
        c = self.case
        value = c.capture()
        self.assertTrue(value.inventory_complete)
        self.assertEqual([row.run.run_id for row in value.observations], [100])
        self.assertEqual(set(value.metadata_nonproducers), {101})
        marker = value.metadata_nonproducers[101]
        self.assertEqual(marker["candidate"]["merge_sha"], c.binding["merge_sha"])
        self.assertNotIn("verified", marker)
        self.assertNotIn("environment", marker)
        self.assertEqual(c.verify()["run_id"], 100)

    def test_optional_policy_is_off_by_default_and_cannot_be_partial_or_arbitrary(self):
        c = self.case
        c.policy = replace(c.policy, metadata_generations=None, metadata_sources=None)
        self.assertFalse(c.capture().inventory_complete)
        self.setUp(); c = self.case
        for shape in ("missing-sources", "missing-workflow", "extra-source", "alias", "duplicate-pair"):
            policy = deepcopy(c.policy)
            if shape == "missing-sources": policy = replace(policy, metadata_sources=None)
            elif shape == "missing-workflow": policy.metadata_generations["metadata-v1"].pop(A.METADATA_WORKFLOW)
            elif shape == "extra-source": policy.metadata_sources["metadata-v1"]["arbitrary.py"] = self.sources[A.METADATA_SOURCE]
            elif shape == "alias": policy.metadata_sources["metadata-v1"][A.METADATA_SOURCE]["mode"] = "120000"
            else:
                policy.metadata_generations["duplicate"] = deepcopy(policy.metadata_generations["metadata-v1"])
                policy.metadata_sources["duplicate"] = deepcopy(policy.metadata_sources["metadata-v1"])
            with self.subTest(shape=shape), self.assertRaises(P.ProtocolError):
                c.adapter.capture(17, c.plan, policy, now=NOW)

    def test_missing_or_forged_source_marker_cannot_hide_an_unknown_run(self):
        for shape in ("missing-edge", "wrong-edge", "duplicate-edge", "mixed-edge", "wrong-helper", "alias-parent",
                      "wrong-caller", "foreign-head", "wrong-parents", "unknown-generation", "unknown-target"):
            self.setUp(); c = self.case
            if shape == "missing-edge": c.runs[101]["referenced_workflows"] = []
            elif shape == "wrong-edge": c.runs[101]["referenced_workflows"][0]["sha"] = "8" * 40
            elif shape == "duplicate-edge": c.runs[101]["referenced_workflows"] *= 2
            elif shape == "mixed-edge": c.runs[101]["referenced_workflows"].append({"path": "other/repo/.github/workflows/x.yml@" + c.binding["merge_sha"], "sha": c.binding["merge_sha"], "ref": c.pp.workflow_ref})
            elif shape == "wrong-helper":
                c.api.mutate = lambda e,v: ({**v, "tree": [{**v["tree"][0], "sha": "9" * 40}]} if e.endswith("/git/trees/" + "5" * 40) else v)
            elif shape == "alias-parent":
                c.api.mutate = lambda e,v: ({**v, "tree": [{**v["tree"][0], "mode": "120000", "type": "blob"}]} if e.endswith("/git/trees/" + "4" * 40) else v)
            elif shape == "wrong-caller": c.runs[101]["workflow_id"] = 98
            elif shape == "foreign-head": c.runs[101]["head_repository"]["id"] = 123
            elif shape == "wrong-parents":
                c.api.mutate = lambda e,v: ({**v, "parents": list(reversed(v["parents"]))} if e.endswith("/git/commits/" + c.binding["merge_sha"]) else v)
            elif shape == "unknown-generation": c.generation[A.METADATA_WORKFLOW]["sha"] = "9" * 40
            else: c.binding["base_ref"] = "unknown-target"
            with self.subTest(shape=shape):
                # Direct classification avoids current() rejecting an intentionally
                # malformed live fixture before the source-classification boundary.
                try: marker = c.adapter._metadata_observation(c.runs[101], c.policy, c.binding, NOW)
                except P.ProtocolError: marker = None
                self.assertIsNone(marker)

    def test_native_job_check_step_status_time_and_attempt_must_all_match(self):
        for shape in ("pending-marker", "failed-step", "missing-step", "duplicate-step", "future-time",
                      "wrong-app", "wrong-suite", "check-name", "check-status", "mixed-job", "rerun"):
            self.setUp(); c = self.case
            job = c.jobs[101][0]
            if shape == "pending-marker": job.update(status="in_progress", conclusion=None, completed_at=None)
            elif shape == "failed-step": job["steps"][0]["conclusion"] = "failure"
            elif shape == "missing-step": job["steps"] = []
            elif shape == "duplicate-step": job["steps"] *= 2
            elif shape == "future-time": job["completed_at"] = "2026-10-15T12:00:00Z"
            elif shape == "wrong-app": c.api.mutate = lambda e,v: ({**v, "app": {"id": 42}} if e.endswith("/check-runs/140") else v)
            elif shape == "wrong-suite": c.api.mutate = lambda e,v: ({**v, "check_suite": {"id": 1111}} if e.endswith("/check-runs/140") else v)
            elif shape == "check-name": c.api.mutate = lambda e,v: ({**v, "name": "forged"} if e.endswith("/check-runs/140") else v)
            elif shape == "check-status": c.api.mutate = lambda e,v: ({**v, "conclusion": "failure"} if e.endswith("/check-runs/140") else v)
            elif shape == "mixed-job": job["run_attempt"] = 2
            else: c.runs[101]["run_attempt"] = 2
            with self.subTest(shape=shape): self.assertFalse(c.capture().inventory_complete)

    def test_any_producer_job_or_artifact_including_unrelated_or_duplicate_denies_exclusion(self):
        for shape in ("descriptor", "shared", "publisher", "artifact", "unrelated", "duplicate"):
            self.setUp(); c = self.case
            if shape in {"descriptor", "shared", "publisher"}:
                name = {"descriptor": c.policy.publisher_job, "shared": c.policy.owner_jobs["shared-host"],
                        "publisher": c.policy.final_publisher_prefix + "a" * 64}[shape]
                c.jobs[101].append({**deepcopy(c.jobs[101][0]), "id": 141, "name": name,
                                   "status": "queued", "conclusion": None, "started_at": None, "completed_at": None})
            else:
                c.artifacts[101] = [{"id": 1011, "name": "unrelated" if shape == "unrelated" else "ci-descriptor-101-1"}]
                if shape == "duplicate": c.artifacts[101].append({"id": 1012, "name": "ci-descriptor-101-1"})
            with self.subTest(shape=shape):
                value = c.capture()
                self.assertFalse(value.inventory_complete)
                self.assertNotIn(101, value.metadata_nonproducers)

    def test_metadata_marker_does_not_replace_pending_or_failed_real_producer(self):
        for status, conclusion, expected in (("in_progress", None, "pending"), ("completed", "failure", "failed")):
            self.setUp(); c = self.case
            c.runs[100].update(status=status, conclusion=conclusion)
            self.assertEqual(c.authority()["state"], expected)
            with self.assertRaises(P.ProtocolError): c.verify()

    def test_skipped_metadata_edge_preserves_ordinary_proof_and_failure_before_shared_work(self):
        c = self.case
        c.runs[100]["referenced_workflows"].extend(deepcopy(c.runs[101]["referenced_workflows"]))
        skipped = {**deepcopy(c.jobs[101][0]), "id": 142, "run_id": 100,
                   "status": "completed", "conclusion": "skipped", "started_at": None,
                   "completed_at": None, "steps": [],
                   "check_run_url": f"https://api.github.com/{A.PREFIX}/check-runs/142"}
        c.jobs[100].append(skipped)
        self.assertEqual(c.verify()["run_id"], 100)
        # An ordinary failure after its descriptor but before shared execution
        # still classifies through the producer path, never as a metadata run.
        c.runs[100].update(status="completed", conclusion="failure")
        c.jobs[100] = [job for job in c.jobs[100] if job["name"] in {c.policy.publisher_job, A.METADATA_JOB}]
        self.assertEqual(c.authority()["state"], "failed")
        with self.assertRaises(P.ProtocolError): c.verify()

    def test_metadata_jobs_and_artifacts_are_rechecked_inside_each_capture(self):
        for shape in ("producer-job", "artifact"):
            self.setUp(); c = self.case
            reads = 0
            def mutate(endpoint, value):
                nonlocal reads
                suffix = "/actions/runs/101/attempts/1/jobs?" if shape == "producer-job" else "/actions/runs/101/artifacts?"
                if suffix in endpoint:
                    reads += 1
                    if reads == 2:
                        field = "jobs" if shape == "producer-job" else "artifacts"
                        item = {**deepcopy(c.jobs[101][0]), "id": 141, "name": c.policy.owner_jobs["shared-host"]} if field == "jobs" else {"id": 1011, "name": "ci-aggregate-101-1"}
                        value[field].append(item); value["total_count"] += 1
                return value
            c.api.mutate = mutate
            with self.subTest(shape=shape): self.assertFalse(c.capture().inventory_complete)

    def test_metadata_snapshot_must_also_match_across_aggregate_verification(self):
        c = self.case
        reads = 0
        def mutate(endpoint, value):
            nonlocal reads
            if "/actions/runs/101/attempts/1/jobs?" in endpoint:
                reads += 1
                if reads >= 3: value["jobs"][0]["steps"][0]["number"] = 2
            return value
        c.api.mutate = mutate
        with self.assertRaisesRegex(P.ProtocolError, "metadata non-producer inventory changed"):
            c.verify()

    def test_separate_codeql_caller_uses_typed_two_workflow_policy_without_producer_facts(self):
        c = self.case
        path = ".github/workflows/codeql.yml"
        c.generation[path] = {"mode": "100644", "type": "blob", "sha": "9" * 40}
        policy = A.MetadataPolicy(77, path, {"metadata-v1": {p: c.generation[p] for p in (path, A.METADATA_WORKFLOW)}},
                                  {"metadata-v1": self.sources})
        c.runs[101].update(path=path, workflow_id=77)
        marker = c.adapter.metadata_observation(c.runs[101], c.binding, policy, now=NOW)
        self.assertEqual(marker["generation"], "metadata-v1")
        c.jobs[101].append({**deepcopy(c.jobs[101][0]), "id": 141, "name": "CodeQL (python)", "status": "queued", "conclusion": None})
        self.assertIsNone(c.adapter.metadata_observation(c.runs[101], c.binding, policy, now=NOW))


class SchedulingFakeApi(MetadataFakeApi):
    def json(self, endpoint):
        path = endpoint[len(A.PREFIX):].lstrip('/').split('?', 1)[0]
        c = self.case
        if path == 'actions/workflows/repository-checks.yml':
            self.calls.append(endpoint)
            return self.mutate(endpoint, {'id': 99, 'path': c.policy.caller_path, 'state': 'active'})
        if path.startswith('git/ref/heads/') and path.removeprefix('git/ref/heads/') == c.binding['base_ref']:
            self.calls.append(endpoint)
            return self.mutate(endpoint, {'ref': 'refs/heads/' + c.binding['base_ref'],
                'object': {'type': 'commit', 'sha': c.binding['base_sha']}})
        value = super().json(endpoint)
        if path == 'pulls/17':
            value['labels'] = deepcopy(c.labels)
        return value


class MetadataSchedulingTests(unittest.TestCase):
    """Actual native adapter, without a descriptor or consumer environment."""
    def setUp(self):
        fixture = MetadataNonproducerTests()
        fixture.setUp()
        self.case = c = fixture.case
        c.labels = []
        c.generation[c.policy.caller_path]['sha'] = 'bc9c4284286b5c3d2de07a3ecf3b98393e2f2a2c'
        c.generation[A.METADATA_WORKFLOW]['sha'] = 'b76ade9fd7a76da21bf2cb2161deae7a262163e8'
        c.policy = replace(c.policy, metadata_generations={'metadata-v2':deepcopy(c.generation)},
            metadata_sources={'metadata-v2': c.policy.metadata_sources['metadata-v1']})
        c.runs[101]['display_title'] = A.NONPRODUCER_RUN_NAME
        c.runs[100]['display_title'] = A.ORDINARY_RUN_NAME
        c.runs[100]['referenced_workflows'].extend(deepcopy(c.runs[101]['referenced_workflows']))
        ordinary = deepcopy(c.jobs[101][0])
        ordinary.update(id=150, run_id=100, started_at='2026-10-15T10:00:01Z',
            completed_at='2026-10-15T10:00:20Z',
            check_run_url=f'https://api.github.com/{A.PREFIX}/check-runs/150',
            steps=[{'number': 1, 'name': A.ORDINARY_SOURCE_STEP + ' (diagnostics absent)',
                'status': 'completed', 'conclusion': 'success',
                'started_at': '2026-10-15T10:00:02Z', 'completed_at': '2026-10-15T10:00:19Z'}])
        # The actual ordinary source can be pending/failed before any descriptor.
        c.jobs[100] = [ordinary]
        c.artifacts[100] = []
        c.api = SchedulingFakeApi(c); c.adapter = A.Adapter(c.api)
        self.policy = A.MetadataPolicy(99, c.policy.caller_path,
            c.policy.metadata_generations, c.policy.metadata_sources)

    def schedule(self, *, diagnostics=False):
        c = self.case
        return c.adapter.metadata_schedule(17, 101, self.policy, diagnostics=diagnostics, now=NOW)

    def alias_source(self, run_id, revision):
        c = self.case
        c.originals[revision] = (c.binding['merge_tree'], list(c.binding['merge_parents']))
        for edge in c.runs[run_id]['referenced_workflows']:
            edge['path'] = edge['path'].rsplit('@', 1)[0] + '@' + revision
            edge['sha'] = revision

    def test_regenerated_merges_preserve_actual_original_and_current_native_sources(self):
        self.alias_source(100, 'a1' * 20)
        self.alias_source(101, 'a2' * 20)
        value = self.schedule()
        self.assertEqual(value['original_run_id'], 100)
        self.assertEqual(value['original_merge_sha'], 'a1' * 20)
        self.assertEqual(value['current_merge_sha'], 'a2' * 20)
        self.assertEqual(value['binding']['merge_sha'], self.case.binding['merge_sha'])
        self.assertFalse(value['qualification'])

    def test_equivalent_live_regeneration_at_scheduling_bookend_is_accepted(self):
        c = self.case
        reads = [0]
        original = c.binding['merge_sha']
        c.originals[original] = (c.binding['merge_tree'], list(c.binding['merge_parents']))
        def regenerate(endpoint, value):
            if endpoint.endswith('/pulls/17'):
                reads[0] += 1
                if reads[0] == 3:  # Labels, opening current(), closing current().
                    c.binding['merge_sha'] = 'a3' * 20
                    value['merge_commit_sha'] = c.binding['merge_sha']
            return value
        c.api.mutate = regenerate
        value = self.schedule()
        self.assertEqual(reads[0], 4)
        self.assertEqual(value['original_merge_sha'], original)
        self.assertEqual(value['current_merge_sha'], original)
        self.assertFalse(value['qualification'])

    def test_regenerated_current_merge_cannot_hide_changed_tree_or_ordered_parents(self):
        for shape in ('tree', 'base', 'head', 'reversed', 'extra'):
            self.setUp(); c = self.case
            self.alias_source(101, 'a2' * 20)
            tree, parents = c.originals['a2' * 20]
            if shape == 'tree': tree = 'a3' * 20
            elif shape == 'base':
                parents[0] = 'a3' * 20
                c.originals[parents[0]] = deepcopy(c.originals[c.binding['base_sha']])
            elif shape == 'head': parents[1] = 'a3' * 20
            elif shape == 'reversed': parents.reverse()
            else: parents.append('a3' * 20)
            c.originals['a2' * 20] = tree, parents
            with self.subTest(shape=shape), self.assertRaises(P.ProtocolError):
                self.schedule()

    def test_original_from_other_base_or_tree_is_never_mirrored(self):
        for shape in ('tree', 'base'):
            self.setUp(); c = self.case
            self.alias_source(100, 'a1' * 20)
            tree, parents = c.originals['a1' * 20]
            if shape == 'tree': tree = 'a3' * 20
            else:
                parents[0] = 'a3' * 20
                c.originals[parents[0]] = deepcopy(c.originals[c.binding['base_sha']])
            c.originals['a1' * 20] = tree, parents
            with self.subTest(shape=shape), self.assertRaises(P.ProtocolError):
                self.schedule()

    def test_all_seven_pending_failed_and_successful_sources_preserve_status_without_results(self):
        c = self.case
        for target in sorted(A.METADATA_TARGETS):
            for status, conclusion in [('in_progress', None), ('completed', 'failure'), ('completed', 'success')]:
                c.binding['base_ref'] = target
                c.runs[100].update(status=status, conclusion=conclusion)
                with self.subTest(target=target, status=status, conclusion=conclusion):
                    value = self.schedule()
                    self.assertEqual((value['original_status'], value['original_conclusion']), (status, conclusion))
                    self.assertEqual(value['original_run_id'], 100)
                    self.assertEqual(value['metadata_only'], 'true')
                    self.assertFalse(value['qualification'])
                    for field in ('environment', 'results', 'receipt', 'reused', 'passed_suites'):
                        self.assertNotIn(field, value)
        self.assertFalse(any('/actions/artifacts/' in endpoint for endpoint in c.api.calls))

    def test_preinstalled_native_helper_pair_is_retained_exactly_without_overwriting_current_tuple(self):
        c=self.case;caller=c.policy.caller_path
        c.generation[caller]['sha']='81bcf1933edc435826e2de411a777cccd4dec7c7'
        workflows={ 'protected-producer-original-default-v1':deepcopy(c.generation)}
        current={'protected-producer-original-default-v1':{A.METADATA_SOURCE:{'mode':'100644','type':'blob','sha':'6'*40}}}
        original=deepcopy(workflows);current_before=deepcopy(current)
        workflows,helpers=A.retain_native_metadata_sources(workflows,current)
        self.assertEqual(workflows['protected-producer-original-default-v1'],original['protected-producer-original-default-v1'])
        self.assertEqual(helpers['protected-producer-original-default-v1'],current_before['protected-producer-original-default-v1'])
        retained='protected-producer-original-default-v1-reviewed-helper-v1'
        self.assertEqual(workflows[retained],workflows['protected-producer-original-default-v1'])
        self.assertEqual(helpers[retained][A.METADATA_SOURCE]['sha'],'c6ce80aa78d2f2161b1ea0caf715a6346187e8b9')
        self.policy=A.MetadataPolicy(99,caller,workflows,helpers)
        def retained_source(endpoint,value):
            if endpoint.endswith('/git/trees/'+'5'*40):
                value['tree'][0]['sha']='c6ce80aa78d2f2161b1ea0caf715a6346187e8b9'
            return value
        c.api.mutate=retained_source
        value=self.schedule()
        self.assertEqual(value['original_run_id'],100)
        self.assertFalse(value['qualification'])
        c.api.mutate=lambda endpoint,value:({**value,'tree':[{**value['tree'][0],'sha':'f'*40}]}
            if endpoint.endswith('/git/trees/'+'5'*40) else value)
        with self.assertRaises(ValueError):self.schedule()

    def test_same_second_open_and_label_events_use_native_workflow_sequence(self):
        c = self.case
        # GitHub observed on PR1412: both timestamps are18:44:15, while the
        # independently authenticated workflow ordinals are671 then672.
        c.runs[100]['run_number'] = 671
        c.runs[101]['run_number'] = 672
        c.runs[101]['run_started_at'] = c.runs[100]['run_started_at']
        value = self.schedule()
        self.assertEqual(value['original_run_id'], 100)
        self.assertFalse(value['qualification'])
        self.assertFalse(any('/actions/artifacts/' in endpoint for endpoint in c.api.calls))

    def test_completed_ordinary_endpoint_update_times_remain_distinct_and_authenticated(self):
        c = self.case
        def independent_updates(endpoint, value):
            if endpoint.endswith('/actions/runs/100/attempts/1'):
                value['updated_at'] = '2026-10-15T10:04:31Z'
            return value
        c.api.mutate = independent_updates
        for conclusion in ('success', 'failure', 'cancelled'):
            c.runs[100].update(status='completed', conclusion=conclusion)
            with self.subTest(conclusion=conclusion):
                value = self.schedule()
                self.assertEqual((value['original_status'], value['original_conclusion']),
                                 ('completed', conclusion))
                self.assertFalse(value['qualification'])
        source = c.adapter._scheduling_source(c.runs[100], c.binding, self.policy,
            now=NOW, scheduling_progress=True)
        self.assertEqual(source['completed_observations']['listed']['updated_at'],
                         '2026-10-15T10:04:30Z')
        self.assertEqual(source['completed_observations']['latest']['updated_at'],
                         '2026-10-15T10:04:30Z')
        self.assertEqual(source['completed_observations']['attempt']['updated_at'],
                         '2026-10-15T10:04:31Z')
        self.assertEqual(source['run']['updated_at'], '2026-10-15T10:04:31Z')
        self.assertFalse(any('/actions/artifacts/' in endpoint for endpoint in c.api.calls))

    def test_completed_ordinary_each_endpoint_update_must_have_valid_time_order(self):
        for endpoint_kind in ('listed', 'latest', 'attempt'):
            for stamp in ('not-a-time', '2026-10-15T09:58:59Z', '2026-10-15T10:05:03Z'):
                self.setUp(); c = self.case
                def invalid_update(endpoint, value):
                    if endpoint_kind == 'listed' and '/actions/workflows/99/runs?' in endpoint:
                        next(row for row in value['workflow_runs'] if row['id'] == 100)['updated_at'] = stamp
                    elif endpoint_kind == 'latest' and endpoint.endswith('/actions/runs/100'):
                        value['updated_at'] = stamp
                    elif endpoint_kind == 'attempt' and endpoint.endswith('/actions/runs/100/attempts/1'):
                        value['updated_at'] = stamp
                    return value
                c.api.mutate = invalid_update
                with self.subTest(endpoint=endpoint_kind, stamp=stamp), self.assertRaises(P.ProtocolError) as error:
                    c.adapter.metadata_schedule(17, 101, self.policy, now=NOW,
                        observation_clock=lambda:NOW + timedelta(seconds=2))
                self.assertNotIsInstance(error.exception, A.SchedulingPending)

    def test_completed_ordinary_each_endpoint_is_stable_between_scheduling_bookends(self):
        for endpoint_kind in ('listed', 'latest', 'attempt'):
            self.setUp(); c = self.case; inventories = [0]
            def changed_endpoint(endpoint, value):
                if '/actions/workflows/99/runs?' in endpoint:
                    inventories[0] += 1
                    if endpoint_kind == 'listed' and inventories[0] >= 2:
                        next(row for row in value['workflow_runs'] if row['id'] == 100)['updated_at'] = '2026-10-15T10:04:31Z'
                elif inventories[0] >= 2 and (
                        endpoint_kind == 'latest' and endpoint.endswith('/actions/runs/100')
                        or endpoint_kind == 'attempt' and endpoint.endswith('/actions/runs/100/attempts/1')):
                    value['updated_at'] = '2026-10-15T10:04:31Z'
                return value
            c.api.mutate = changed_endpoint
            with self.subTest(endpoint=endpoint_kind), self.assertRaisesRegex(A.ApiError, 'source changed'):
                self.schedule()

    def test_scheduling_only_original_progress_waits_for_a_fresh_complete_admission(self):
        for bookend in ('initial', 'final'):
            for shape in ('update', 'state'):
                self.setUp(); c = self.case; inventories = [0]
                if shape == 'update':
                    c.runs[100].update(status='in_progress', conclusion=None)
                def progress(endpoint, value):
                    if '/actions/workflows/99/runs?' in endpoint:
                        inventories[0] += 1
                    if endpoint.endswith('/actions/runs/100/attempts/1') and inventories[0] >= (
                            1 if bookend == 'initial' else 2):
                        if shape == 'update': value['updated_at'] = '2026-10-15T10:04:31Z'
                        else: value.update(status='in_progress', conclusion=None)
                    return value
                c.api.mutate = progress
                with self.subTest(bookend=bookend, shape=shape), self.assertRaises(A.SchedulingPending):
                    c.adapter.metadata_schedule(17, 101, self.policy, now=NOW,
                        observation_clock=lambda:NOW + timedelta(seconds=2))
                # A typed wait is not an observation or a substitute result.
                # The next attempt independently repeats the complete native admission.
                c.api.mutate = lambda endpoint, value:value
                before = len(c.api.calls)
                value = c.adapter.metadata_schedule(17, 101, self.policy, now=NOW + timedelta(seconds=2),
                    observation_clock=lambda:NOW + timedelta(seconds=2))
                self.assertGreater(len(c.api.calls), before)
                self.assertEqual(value['original_run_id'], 100)
                self.assertEqual((value['original_status'], value['original_conclusion']),
                    (c.runs[100]['status'], c.runs[100]['conclusion']))
                self.assertFalse(value['qualification'])
                self.assertFalse(any(key in value for key in ('results', 'receipt', 'environment')))
                self.assertFalse(any('/actions/artifacts/' in endpoint for endpoint in c.api.calls))

    def test_scheduling_only_new_original_times_and_source_completion_require_a_fresh_cutoff(self):
        for shape in ('updated_at', 'run_started_at', 'source_completion'):
            self.setUp(); c = self.case
            stamp = (NOW + timedelta(seconds=1)).isoformat().replace('+00:00', 'Z')
            if shape == 'source_completion':
                c.jobs[100][0]['completed_at'] = stamp
                c.jobs[100][0]['steps'][0]['completed_at'] = stamp
            else:
                c.runs[100][shape] = stamp
                if shape == 'run_started_at':
                    c.runs[100]['updated_at'] = stamp
                    c.jobs[100][0].update(started_at=stamp, completed_at=stamp)
                    c.jobs[100][0]['steps'][0].update(started_at=stamp, completed_at=stamp)
            with self.subTest(shape=shape), self.assertRaises(A.SchedulingPending):
                c.adapter.metadata_schedule(17, 101, self.policy, now=NOW,
                    observation_clock=lambda:NOW + timedelta(seconds=2))
            value = c.adapter.metadata_schedule(17, 101, self.policy, now=NOW + timedelta(seconds=2),
                observation_clock=lambda:NOW + timedelta(seconds=2))
            self.assertEqual(value['original_run_id'], 100)
            self.assertFalse(value['qualification'])

    def test_scheduling_retry_leaves_default_original_observations_and_historical_recipes_strict(self):
        c = self.case
        def progress(endpoint, value):
            if endpoint.endswith('/actions/runs/100/attempts/1'):
                value['updated_at'] = '2026-10-15T10:04:31Z'
            return value
        c.api.mutate = progress
        for read in (
                lambda:c.adapter.metadata_observation(c.runs[100], c.binding, self.policy, now=NOW),
                lambda:c.adapter._scheduling_source(c.runs[100], c.binding, self.policy, now=NOW,
                    observation_clock=lambda:NOW + timedelta(seconds=2))):
            with self.assertRaises(A.ApiError) as error: read()
            self.assertNotIsInstance(error.exception, A.SchedulingPending)
        # A registered historical source remains strict even when the caller
        # explicitly asks for scheduling-only retry behavior.
        caller = c.policy.caller_path
        c.generation[caller]['sha'] = 'f' * 40
        self.policy.generations['metadata-v2'][caller]['sha'] = 'f' * 40
        with self.assertRaises(A.ApiError) as error:
            c.adapter._scheduling_source(c.runs[100], c.binding, self.policy, now=NOW,
                observation_clock=lambda:NOW + timedelta(seconds=2), scheduling_progress=True)
        self.assertNotIsInstance(error.exception, A.SchedulingPending)

    def test_scheduling_progress_cannot_retry_immutable_source_app_state_or_future_drift(self):
        for shape in ('attempt', 'head', 'ordinal', 'repository', 'generation', 'helper', 'parents',
                      'app', 'invalid-state', 'pending-conclusion', 'missing-start',
                      'time-order', 'future-update', 'future-start'):
            self.setUp(); c = self.case
            def corrupt(endpoint, value):
                if endpoint.endswith('/actions/runs/100/attempts/1'):
                    value['updated_at'] = '2026-10-15T10:04:31Z'
                    if shape == 'attempt': value['run_attempt'] = 2
                    elif shape == 'head': value['head_sha'] = '9' * 40
                    elif shape == 'ordinal': value['run_number'] = 99
                    elif shape == 'repository': value['repository']['id'] = 42
                    elif shape == 'invalid-state': value['status'] = 'unknown'
                    elif shape == 'pending-conclusion': value.update(status='in_progress', conclusion='success')
                    elif shape == 'missing-start': value['run_started_at'] = None
                    elif shape == 'time-order': value['run_started_at'] = '2026-10-15T10:04:32Z'
                    elif shape == 'future-update': value['updated_at'] = '2026-10-15T10:05:03Z'
                    elif shape == 'future-start':
                        value.update(run_started_at='2026-10-15T10:05:03Z', updated_at='2026-10-15T10:05:03Z')
                if shape == 'app' and endpoint.endswith('/check-suites/1100'): value['app']['id'] = 42
                if shape == 'helper' and endpoint.endswith('/git/trees/' + '5' * 40):
                    value['tree'][0]['sha'] = '9' * 40
                if shape == 'parents' and endpoint.endswith('/git/commits/' + c.binding['merge_sha']):
                    value['parents'].reverse()
                return value
            if shape == 'generation': c.generation[c.policy.caller_path]['sha'] = 'f' * 40
            c.api.mutate = corrupt
            with self.subTest(shape=shape), self.assertRaises(P.ProtocolError) as error:
                c.adapter.metadata_schedule(17, 101, self.policy, now=NOW,
                    observation_clock=lambda:NOW + timedelta(seconds=2))
            self.assertNotIsInstance(error.exception, A.SchedulingPending)

    def test_late_ordinary_source_job_must_still_be_exact_successful_native_and_not_future(self):
        for shape in ('failed-step', 'wrong-step', 'duplicate', 'chronology', 'app', 'check', 'future'):
            self.setUp(); c = self.case
            job = c.jobs[100][0]
            job['completed_at'] = job['steps'][0]['completed_at'] = '2026-10-15T10:05:01Z'
            if shape == 'failed-step': job['steps'][0]['conclusion'] = 'failure'
            elif shape == 'wrong-step': job['steps'][0]['name'] = A.METADATA_STEP
            elif shape == 'duplicate': job['steps'].append(deepcopy(job['steps'][0]))
            elif shape == 'chronology': job['steps'][0]['started_at'] = '2026-10-15T10:05:02Z'
            elif shape == 'future': job['completed_at'] = job['steps'][0]['completed_at'] = '2026-10-15T10:05:03Z'
            def corrupt(endpoint, value):
                if endpoint.endswith('/check-runs/150'):
                    if shape == 'app': value['app']['id'] = 42
                    elif shape == 'check': value['conclusion'] = 'failure'
                return value
            c.api.mutate = corrupt
            with self.subTest(shape=shape), self.assertRaises(P.ProtocolError) as error:
                c.adapter.metadata_schedule(17, 101, self.policy, now=NOW,
                    observation_clock=lambda:NOW + timedelta(seconds=2))
            self.assertNotIsInstance(error.exception, A.SchedulingPending)

    def test_current_native_metadata_accepts_independent_api_progress_timestamps_without_results(self):
        c = self.case
        # PR1419's CodeQL metadata list/latest and attempt endpoints differed
        # by one second. Only the exact current never-producer can project
        # progress; its original workflow/result remains independently bound.
        def progressing_attempt(endpoint, value):
            if endpoint.endswith('/actions/runs/101/attempts/1'):
                value['updated_at'] = '2026-10-15T10:04:31Z'
            return value
        c.api.mutate = progressing_attempt
        value = self.schedule()
        self.assertEqual(value['original_run_id'], 100)
        self.assertEqual((value['original_status'], value['original_conclusion']),
                         (c.runs[100]['status'], c.runs[100]['conclusion']))
        self.assertFalse(value['qualification'])
        self.assertFalse(any(key in value for key in ('results', 'environment', 'receipt')))

    def progressing_schedule(self, *, identity=101, bookend='initial', field='updated_at', future=False):
        """Advance the observation clock inside a real fake-API native read."""
        c = self.case
        clock = [NOW]
        reads = [0]
        threshold = 1 if bookend == 'initial' else 2
        if identity == 102:
            c.runs[identity] = {**deepcopy(c.runs[101]), 'id':identity,
                'run_number':identity, 'check_suite_id':identity+1000}
            job = deepcopy(c.jobs[101][0])
            job.update(id=160, run_id=identity,
                check_run_url=f'https://api.github.com/{A.PREFIX}/check-runs/160')
            c.jobs[identity] = [job]
            c.artifacts[identity] = []
            # metadata_observation reads the attempt before its independent
            # source classification, once at each inventory bookend.
            threshold = 1 if bookend == 'initial' else 3
        def progress(endpoint, value):
            if endpoint.endswith(f'/actions/runs/{identity}/attempts/1'):
                reads[0] += 1
                if reads[0] >= threshold:
                    clock[0] = NOW + timedelta(seconds=2)
                    stamp = NOW + timedelta(seconds=3 if future else 1)
                    value[field] = stamp.isoformat().replace('+00:00', 'Z')
            return value
        c.api.mutate = progress
        with patch.object(A, '_now', side_effect=lambda:clock[0]):
            value = c.adapter.metadata_schedule(17, 101, self.policy)
        self.assertGreaterEqual(reads[0], threshold)
        return value

    def test_current_update_during_native_reads_uses_each_bookend_observation_time(self):
        for bookend in ('initial','final'):
            self.setUp()
            with self.subTest(bookend=bookend):
                value = self.progressing_schedule(bookend=bookend)
                self.assertEqual(value['original_run_id'],100)
                self.assertEqual((value['original_status'],value['original_conclusion']),
                    (self.case.runs[100]['status'],self.case.runs[100]['conclusion']))
                self.assertFalse(value['qualification'])
                self.assertFalse(any(key in value for key in ('results','receipt','environment')))

    def test_other_exact_neverproducer_updates_use_fresh_observation_at_both_bookends(self):
        for bookend in ('initial','final'):
            self.setUp()
            with self.subTest(bookend=bookend):
                value = self.progressing_schedule(identity=102,bookend=bookend)
                self.assertEqual(value['original_run_id'],100)
                self.assertFalse(value['qualification'])
                self.assertFalse(any('/actions/artifacts/' in endpoint for endpoint in self.case.api.calls))

    def test_progress_timestamps_later_than_the_fresh_observation_remain_rejected(self):
        for identity in (101,102):
            for bookend in ('initial','final'):
                for field in ('updated_at','run_started_at'):
                    self.setUp()
                    with self.subTest(identity=identity,bookend=bookend,field=field), \
                            self.assertRaisesRegex(P.ProtocolError,'in the future'):
                        self.progressing_schedule(identity=identity,bookend=bookend,field=field,future=True)

    def test_later_observation_does_not_normalize_original_producer_progress(self):
        self.setUp()
        self.case.runs[100].update(status='in_progress', conclusion=None)
        with self.assertRaisesRegex(P.ProtocolError,'inventory changed'):
            self.progressing_schedule(identity=100)

    def test_fresh_observation_clock_does_not_extend_original_producer_time_cutoff(self):
        self.case.runs[100]['updated_at'] = (NOW+timedelta(seconds=1)).isoformat().replace('+00:00','Z')
        with self.assertRaisesRegex(P.ProtocolError,'in the future'):
            self.case.adapter.metadata_schedule(17,101,self.policy,now=NOW,
                observation_clock=lambda:NOW+timedelta(seconds=2))

    def test_observation_clock_must_be_utc_and_cannot_move_before_entry(self):
        for observed in (NOW-timedelta(seconds=1),'not-a-UTC-time'):
            with self.subTest(observed=observed),self.assertRaises(P.ProtocolError):
                self.case.adapter.metadata_schedule(17,101,self.policy,now=NOW,
                    observation_clock=lambda:observed)

    def test_current_progress_cannot_change_native_identity_stop_or_gain_original_authority(self):
        for field, bad in (('run_attempt', 2), ('head_sha', '9' * 40),
                ('check_suite_id', 1102), ('display_title', A.ORDINARY_RUN_NAME),
                ('updated_at', '2026-10-15T12:00:00Z')):
            self.setUp(); c = self.case
            def change(endpoint, value):
                if endpoint.endswith('/actions/runs/101/attempts/1'):
                    value[field] = bad
                return value
            c.api.mutate = change
            with self.subTest(field=field), self.assertRaises(P.ProtocolError):
                self.schedule()
        self.setUp(); c = self.case
        def stopped_attempt(endpoint, value):
            if endpoint.endswith('/actions/runs/101/attempts/1'):
                value.update(status='completed', conclusion='success')
            return value
        c.api.mutate = stopped_attempt
        with self.assertRaises(P.ProtocolError):
            self.schedule()

    def test_original_progress_is_not_normalized_by_current_metadata_projection(self):
        c = self.case
        c.runs[100].update(status='in_progress', conclusion=None)
        def changed_original(endpoint, value):
            if endpoint.endswith('/actions/runs/100/attempts/1'):
                value['updated_at'] = '2026-10-15T10:04:31Z'
            return value
        c.api.mutate = changed_original
        with self.assertRaises(P.ProtocolError):
            self.schedule()

    def test_newer_equal_or_changed_native_workflow_sequence_cannot_own_metadata(self):
        c = self.case
        c.runs[100]['run_number'] = 671
        c.runs[101]['run_number'] = 672
        for ordinal in (672, 673, None, True):
            with self.subTest(ordinal=ordinal), patch.dict(c.runs[100], {'run_number': ordinal}), \
                    self.assertRaises(ValueError):
                self.schedule()
        def change_ordinal(endpoint, value):
            if endpoint.endswith('/actions/runs/100/attempts/1'):
                value['run_number'] = 670
            return value
        c.api.mutate = change_ordinal
        with self.assertRaises(ValueError):
            self.schedule()

    def test_unproved_queued_or_failed_source_cannot_be_promoted_by_same_head_or_marker(self):
        c = self.case
        for shape in ('no-edge', 'missing-source-job', 'pending-source-job', 'failed-source-step',
                      'only-metadata-step', 'no-original', 'ambiguous-original'):
            self.setUp(); c = self.case
            if shape == 'no-edge': c.runs[100]['referenced_workflows'] = []
            elif shape == 'missing-source-job': c.jobs[100] = []
            elif shape == 'pending-source-job': c.jobs[100][0].update(status='queued', conclusion=None)
            elif shape == 'failed-source-step': c.jobs[100][0]['steps'][0]['conclusion'] = 'failure'
            elif shape == 'only-metadata-step': c.jobs[100][0]['steps'][0]['name'] = A.METADATA_STEP
            elif shape == 'no-original': del c.runs[100]
            else:
                c.runs[102] = {**deepcopy(c.runs[100]), 'id': 102, 'check_suite_id': 1102}
                c.jobs[102] = [{**deepcopy(c.jobs[100][0]), 'id': 152, 'run_id': 102,
                    'check_run_url': f'https://api.github.com/{A.PREFIX}/check-runs/152'}]
                c.artifacts[102] = []
            with self.subTest(shape=shape), self.assertRaises(P.ProtocolError): self.schedule()

    def test_current_native_source_cannot_be_excluded_by_supplied_run_id_or_wrong_context(self):
        for shape in ('wrong-current-id', 'current-completed', 'mixed-current', 'wrong-app', 'foreign',
                      'old-attempt', 'wrong-parents', 'wrong-helper', 'unknown-workflow'):
            self.setUp(); c = self.case
            if shape == 'wrong-current-id': current = 999
            else: current = 101
            if shape == 'current-completed': c.runs[101].update(status='completed', conclusion='success')
            elif shape == 'mixed-current': c.runs[101]['referenced_workflows'][0]['sha'] = '8' * 40
            elif shape == 'wrong-app':
                c.api.mutate = lambda e,v: {**v,'app':{'id':42}} if '/check-suites/' in e else v
            elif shape == 'foreign': c.runs[100]['head_repository']['id'] = 12
            elif shape == 'old-attempt': c.runs[100]['run_attempt'] = 2
            elif shape == 'wrong-parents':
                c.api.mutate = lambda e,v: {**v, 'parents': list(reversed(v['parents']))} if e.endswith('/git/commits/' + c.binding['merge_sha']) else v
            elif shape == 'wrong-helper':
                c.api.mutate = lambda e,v: {**v, 'tree':[{**v['tree'][0], 'sha':'9'*40}]} if e.endswith('/git/trees/'+'5'*40) else v
            elif shape == 'unknown-workflow': c.generation[A.METADATA_WORKFLOW]['sha'] = '9'*40
            with self.subTest(shape=shape), self.assertRaises(P.ProtocolError):
                c.adapter.metadata_schedule(17, current, self.policy, now=NOW)

    def test_native_diagnostic_state_is_bound_and_other_label_changes_are_inert(self):
        c = self.case
        c.labels = [{'id': 7, 'name': 'bug'}]
        self.assertEqual(self.schedule()['original_run_id'], 100)

    def test_installed_repository_recipe_accepts_later_label_without_new_execution(self):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location('installed_metadata_fixture_packages',
            root/'tools/repository-checks/package_checks.py')
        packages=importlib.util.module_from_spec(spec);spec.loader.exec_module(packages)
        installed=packages.validate_wiring(root)
        variants={
            'protected-producer-original-default-v1':
                ('81bcf1933edc435826e2de411a777cccd4dec7c7','e9aaaed9693efc5ffb4701697ac2a4d51f5f5ba1'),
            'protected-producer-original-default-boolean-v1':
                ('15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a','3b7a88765b7181a1bc7dd6f48b9b459e590055d3'),
            'protected-producer-original-default-required-context-v1':
                ('22fe0d6d39d120f800099136d7d1ab5280d80b41','7b0703d88d404f38c1b3dec92f77f03586c9144c'),
        }
        self.assertIn(installed,variants)
        caller=self.case.policy.caller_path
        raw=(root/caller).read_bytes()
        current=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        row=next(row['workflows'] for row in packages.workflow_generations() if row['name']==installed)
        self.assertEqual(row[caller],{'mode':'100644','type':'blob','sha':current})
        self.assertEqual(current,variants[installed][0])
        codeql=root/'.github/workflows/codeql.yml'
        self.assertFalse(codeql.is_symlink())
        self.assertIn(codeql.stat().st_mode & 0o777,(0o444,0o644))
        raw=codeql.read_bytes()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),variants[installed][1])
        # The authentic current tuple and original22 recipe are independent
        # variants. Neither a label nor canonical staging supplies a new run.
        for recipe in dict.fromkeys((current,variants['protected-producer-original-default-v1'][0])):
            self.setUp();c=self.case
            c.generation[caller]['sha']=recipe
            c.policy=replace(c.policy,metadata_generations={'metadata-v2':deepcopy(c.generation)})
            self.policy=A.MetadataPolicy(99,caller,c.policy.metadata_generations,c.policy.metadata_sources)
            with self.subTest(recipe=recipe):
                for status,conclusion in [('completed','success'),('completed','failure')]:
                    with self.subTest(status=status,conclusion=conclusion):
                        c.runs[100].update(status=status,conclusion=conclusion)
                        value=self.schedule()
                        self.assertEqual(value['original_run_id'],100)
                        self.assertEqual((value['original_status'],value['original_conclusion']),(status,conclusion))
                        self.assertFalse(value['qualification'])
                        self.assertNotIn('results',value)
                        self.assertNotIn('environment',value)
                intent=c.adapter.metadata_observation(c.runs[101],c.binding,self.policy,now=NOW)
                self.assertEqual(intent['kind'],A.METADATA_INTENT_KIND)
                self.assertFalse(any('/actions/artifacts/' in endpoint for endpoint in c.api.calls))
                c.labels.append({'id':8,'name':'android-long-diagnostics'})
                with self.assertRaises(P.ProtocolError):self.schedule()
                with self.assertRaises(P.ProtocolError):self.schedule(diagnostics=True)
                c.jobs[100][0]['steps'][0]['name']=A.ORDINARY_SOURCE_STEP+' (diagnostics requested)'
                self.assertEqual(self.schedule(diagnostics=True)['original_run_id'],100)
                c.generation[caller]['sha']='f'*40
                with self.assertRaises(P.ProtocolError):self.schedule(diagnostics=True)

    def test_native_job_label_run_and_ref_bookends_are_fresh(self):
        for shape in ('job', 'check', 'run', 'ref', 'labels'):
            self.setUp(); c = self.case
            reads = 0
            def mutate(endpoint, value):
                nonlocal reads
                suffix = {'job':'/actions/runs/100/attempts/1/jobs?', 'check':'/check-runs/150',
                    'run':'/actions/runs/100/attempts/1', 'ref':'/git/ref/heads/' + c.binding['head_ref'],
                    'labels':'/actions/workflows/99/runs?'}[shape]
                if suffix in endpoint:
                    reads += 1
                    # The ordinary source is classified before its opening
                    # admission. Change the attempt at its closing admission.
                    threshold = 4 if shape == 'run' else 2 if shape != 'labels' else 1
                    if reads >= threshold:
                        if shape == 'job': value['jobs'][0]['steps'][0]['conclusion'] = 'failure'
                        elif shape == 'check': value['conclusion'] = 'failure'
                        elif shape == 'run': value['updated_at'] = '2026-10-15T10:04:31Z'
                        elif shape == 'ref': value['object']['sha'] = '9'*40
                        else: c.labels = [{'id':8,'name':'android-long-diagnostics'}]
                return value
            c.api.mutate = mutate
            with self.subTest(shape=shape), self.assertRaises(P.ProtocolError): self.schedule()


class MetadataCanonicalResultTests(unittest.TestCase):
    def setUp(self):
        MetadataSchedulingTests.setUp(self)
        c=self.case
        c.runs[100].update(status='completed',conclusion='success')
        job=deepcopy(c.jobs[100][0])
        job.update(id=151,name='repository-checks',started_at='2026-10-15T10:03:00Z',
            completed_at='2026-10-15T10:04:00Z',
            check_run_url=f'https://api.github.com/{A.PREFIX}/check-runs/151')
        c.jobs[100].append(job)
        self.observed=MetadataSchedulingTests.schedule(self)

    def test_equivalent_merges_still_require_actual_original_workflow_and_job_success(self):
        MetadataSchedulingTests.alias_source(self, 100, 'a1' * 20)
        MetadataSchedulingTests.alias_source(self, 101, 'a2' * 20)
        self.observed = MetadataSchedulingTests.schedule(self)
        self.assertEqual(self.case.adapter.metadata_result_success(self.observed, now=NOW)['job_id'], 151)
        for failed in ('workflow', 'canonical-job'):
            c = self.case
            if failed == 'workflow': c.runs[100]['conclusion'] = 'failure'
            else: c.jobs[100][-1]['conclusion'] = 'failure'
            with self.subTest(failed=failed), self.assertRaises(ValueError):
                c.adapter.metadata_result_success(self.observed, now=NOW)
            c.runs[100]['conclusion'] = 'success'
            c.jobs[100][-1]['conclusion'] = 'success'

    def test_original_success_requires_the_actual_canonical_actions_job_and_empty_new_authority(self):
        value=self.case.adapter.metadata_result_success(self.observed,now=NOW)
        self.assertEqual(value,{'job_id':151,'qualification':False})
        self.assertFalse(any('/actions/artifacts/' in endpoint for endpoint in self.case.api.calls))
        # Between complete admissions a pending original needs only its fixed ID.
        self.case.runs[100].update(status='in_progress',conclusion=None)
        before=len(self.case.api.calls)
        self.assertEqual(self.case.adapter.metadata_result_status(self.observed)['status'],'in_progress')
        self.assertEqual(self.case.api.calls[before:],[A.PREFIX+'/actions/runs/100'])

    def test_completed_result_accepts_distinct_valid_endpoint_update_times_without_normalization(self):
        c = self.case
        def independent_updates(endpoint, value):
            if endpoint.endswith('/actions/runs/100/attempts/1'):
                value['updated_at'] = '2026-10-15T10:04:31Z'
            return value
        c.api.mutate = independent_updates
        value = c.adapter.metadata_result_success(self.observed, now=NOW)
        self.assertEqual(value, {'job_id':151, 'qualification':False})
        self.assertEqual(c.runs[100]['updated_at'], '2026-10-15T10:04:30Z')
        self.assertFalse(any('/actions/artifacts/' in endpoint for endpoint in c.api.calls))

    def test_completed_result_validates_both_endpoint_updates_against_native_completion_and_now(self):
        for endpoint_kind in ('latest', 'attempt'):
            for stamp in ('not-a-time', '2026-10-15T09:58:59Z',
                          '2026-10-15T10:03:59Z', '2026-10-15T10:05:01Z'):
                self.setUp(); c = self.case
                def invalid_update(endpoint, value):
                    if endpoint.endswith('/actions/runs/100' + (
                            '/attempts/1' if endpoint_kind == 'attempt' else '')):
                        value['updated_at'] = stamp
                    return value
                c.api.mutate = invalid_update
                with self.subTest(endpoint=endpoint_kind, stamp=stamp), self.assertRaises(ValueError):
                    c.adapter.metadata_result_success(self.observed, now=NOW)

    def test_completed_result_each_endpoint_raw_bookend_remains_exact(self):
        for endpoint_kind in ('latest', 'attempt'):
            self.setUp(); c = self.case; reads = [0]
            def changed_endpoint(endpoint, value):
                if endpoint.endswith('/actions/runs/100' + (
                        '/attempts/1' if endpoint_kind == 'attempt' else '')):
                    reads[0] += 1
                    if reads[0] >= 2:
                        value['updated_at'] = '2026-10-15T10:04:31Z'
                return value
            c.api.mutate = changed_endpoint
            with self.subTest(endpoint=endpoint_kind), self.assertRaisesRegex(ValueError, 'changed before output'):
                c.adapter.metadata_result_success(self.observed, now=NOW)

    def test_codeql_uses_its_own_exact_canonical_name_not_a_repository_job(self):
        c=self.case
        path='.github/workflows/codeql.yml'
        c.runs[100]['path']=path;self.observed['original_identity']['path']=path
        c.jobs[100][-1]['name']='codeql-security-results'
        self.assertEqual(c.adapter.metadata_result_success(self.observed,now=NOW)['job_id'],151)
        c.jobs[100][-1]['name']='repository-checks'
        with self.assertRaisesRegex(ValueError,'aggregate unavailable'):
            c.adapter.metadata_result_success(self.observed,now=NOW)

    def test_successful_workflow_without_successful_canonical_job_never_mirrors_green(self):
        for mutation in ('missing','duplicate','renamed','failed','skipped','pending','foreign-app',
                         'foreign-suite','wrong-attempt','outside-time'):
            self.setUp();c=self.case
            if mutation=='missing':c.jobs[100].pop()
            elif mutation=='duplicate':c.jobs[100].append(deepcopy(c.jobs[100][-1]))
            elif mutation=='renamed':c.jobs[100][-1]['name']='repository-checks (metadata unchanged)'
            elif mutation=='failed':c.jobs[100][-1]['conclusion']='failure'
            elif mutation=='skipped':c.jobs[100][-1]['conclusion']='skipped'
            elif mutation=='pending':c.jobs[100][-1].update(status='in_progress',conclusion=None,completed_at=None)
            elif mutation=='wrong-attempt':c.jobs[100][-1]['run_attempt']=2
            elif mutation=='outside-time':c.jobs[100][-1]['completed_at']='2026-10-15T11:04:00Z'
            else:
                def alter(endpoint,value,mutation=mutation):
                    if endpoint.endswith('/check-runs/151'):
                        if mutation=='foreign-app':value['app']['id']=57789
                        else:value['check_suite']['id']=1101
                    return value
                c.api.mutate=alter
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                c.adapter.metadata_result_success(self.observed,now=NOW)

    def test_failed_cancelled_pending_rerun_or_changed_original_is_not_accepted(self):
        for status,conclusion in [('completed','failure'),('completed','cancelled'),('completed','timed_out'),
                                  ('completed','skipped'),('queued',None),('in_progress',None)]:
            self.case.runs[100].update(status=status,conclusion=conclusion)
            with self.subTest(status=status,conclusion=conclusion),self.assertRaises(ValueError):
                self.case.adapter.metadata_result_success(self.observed,now=NOW)
        self.setUp();c=self.case
        for field,value in [('run_attempt',2),('run_attempt',True),('workflow_id',77),('check_suite_id',1101),
                            ('head_sha','f'*40),('display_title',A.NONPRODUCER_RUN_NAME)]:
            before=deepcopy(c.runs[100]);c.runs[100][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                c.adapter.metadata_result_status(self.observed)
            c.runs[100]=before

    def test_changed_final_native_job_check_or_attempt_cannot_emit_success(self):
        c=self.case;reads=0
        def change(endpoint,value):
            nonlocal reads
            if endpoint.endswith('/check-runs/151'):
                reads+=1
                if reads>=2:value['conclusion']='failure'
            return value
        c.api.mutate=change
        with self.assertRaises(ValueError):c.adapter.metadata_result_success(self.observed,now=NOW)

    def test_new_meaningful_diagnostic_demand_cannot_reuse_the_absent_diagnostic_original(self):
        self.case.labels=[{'id':7,'name':'android-long-diagnostics'}]
        with self.assertRaisesRegex(ValueError,'diagnostic demand changed'):
            self.case.adapter.metadata_result_success(self.observed,now=NOW)

    def test_old_boolean_helper_pair_remains_exact_without_relabeling_new_native_source(self):
        for caller,oid in [('.github/workflows/repository-checks.yml','15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a'),
                           ('.github/workflows/codeql.yml','3b7a88765b7181a1bc7dd6f48b9b459e590055d3')]:
            paths=A.METADATA_CALLERS[caller]
            workflows={path:deepcopy(self.case.generation.get(path,{'mode':'100644','type':'blob','sha':'9'*40})) for path in paths}
            workflows[caller]['sha']=oid
            generations={'installed25':deepcopy(workflows)}
            sources={'installed25':{A.METADATA_SOURCE:{'mode':'100644','type':'blob','sha':'a'*40}}}
            retained,helpers=A.retain_native_metadata_sources(generations,sources)
            self.assertEqual(retained['installed25'],workflows)
            self.assertEqual(helpers['installed25'][A.METADATA_SOURCE]['sha'],'a'*40)
            self.assertEqual(helpers['installed25-reviewed-helper-v2'][A.METADATA_SOURCE]['sha'],
                '8f157f4bb98f56fc431dfff301f566727096bf7c')
            self.assertEqual(retained['installed25-reviewed-helper-v2'],workflows)


class NativeMetadataIntentTests(unittest.TestCase):
    """The new exact never-producer recipe can be known before its marker."""
    def setUp(self):
        fixture = MetadataNonproducerTests(); fixture.setUp()
        self.case = c = fixture.case
        c.generation[c.policy.caller_path]['sha'] = 'bc9c4284286b5c3d2de07a3ecf3b98393e2f2a2c'
        c.generation[A.METADATA_WORKFLOW]['sha'] = 'b76ade9fd7a76da21bf2cb2161deae7a262163e8'
        c.policy = replace(c.policy,
            generations={'native22': {path:deepcopy(c.generation[path]) for path in A.WORKFLOWS}},
            metadata_generations={'metadata-v2':deepcopy(c.generation)},
            metadata_sources={'metadata-v2':c.policy.metadata_sources['metadata-v1']})
        c.runs[100]['referenced_workflows'].extend(deepcopy(c.runs[101]['referenced_workflows']))
        c.runs[100]['display_title']=A.ORDINARY_RUN_NAME
        c.runs[101].update(display_title=A.NONPRODUCER_RUN_NAME,status='queued',conclusion=None,run_started_at=None)
        c.jobs[101] = []
        self.policy = A.MetadataPolicy(99,c.policy.caller_path,c.policy.metadata_generations,c.policy.metadata_sources)

    def observe(self):
        c=self.case
        return c.adapter.metadata_observation(c.runs[101],c.binding,self.policy,now=NOW)

    def test_queued_native_intent_is_stable_through_real_api_progress_without_results(self):
        c=self.case
        queued=self.observe()
        self.assertEqual(queued['kind'],A.METADATA_INTENT_KIND)
        self.assertEqual(c.verify()['run_id'],100)
        for status,conclusion in [('in_progress',None),('completed','failure'),('completed','success')]:
            c.runs[101].update(status=status,conclusion=conclusion,run_started_at='2026-10-15T10:04:00Z')
            with self.subTest(status=status,conclusion=conclusion): self.assertEqual(self.observe(),queued)
        for field in ('results','environment','receipt','qualified_at','expires_at','verified','jobs','status'):
            self.assertNotIn(field,queued)

    def test_exact_boolean_caller_has_native_metadata_intent_without_result_authority(self):
        c=self.case
        caller=c.policy.caller_path
        for tree in (c.generation,c.policy.metadata_generations['metadata-v2']):
            tree[caller]['sha']='15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a'
        c.policy.generations['native22'][caller]['sha']='15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a'
        value=self.observe()
        self.assertEqual(value['kind'],A.METADATA_INTENT_KIND)
        self.assertEqual(c.verify()['run_id'],100)
        self.assertNotIn('results',value)
        self.assertNotIn('qualification',value)
        c.generation[caller]['sha']='f'*40
        self.policy.generations['metadata-v2'][caller]['sha']='f'*40
        self.assertIsNone(self.observe())

    def test_progress_during_original_verification_does_not_replace_or_fail_original(self):
        c=self.case; reads=0
        def mutate(endpoint,value):
            nonlocal reads
            if '/actions/workflows/99/runs?' in endpoint:
                reads+=1
                if reads==2:
                    c.runs[101].update(status='in_progress',run_started_at='2026-10-15T10:04:00Z')
                    c.jobs[101]=[{'id':146,'run_id':101,'run_attempt':1,'head_sha':c.binding['head_sha'],
                        'name':A.METADATA_JOB,'status':'in_progress','conclusion':None,
                        'started_at':'2026-10-15T10:04:01Z','completed_at':None,
                        'check_run_url':f'https://api.github.com/{A.PREFIX}/check-runs/146'}]
                elif reads>=3:
                    c.runs[101].update(status='completed',conclusion='success')
                    c.jobs[101][0].update(status='completed',conclusion='success',completed_at='2026-10-15T10:04:20Z')
            return value
        c.api.mutate=mutate
        self.assertEqual(c.verify()['run_id'],100)
        self.assertGreaterEqual(reads,4)

    def test_name_alone_old_recipe_missing_source_or_late_work_cannot_exclude(self):
        for shape in ('forged-name-old-recipe','unknown-helper','missing-source','mixed-source','wrong-app',
                      'rerun','heavy','artifact','parents','foreign'):
            self.setUp();c=self.case
            if shape=='forged-name-old-recipe':
                c.generation[c.policy.caller_path]['sha']='7'*40
                c.policy.metadata_generations['metadata-v2'][c.policy.caller_path]['sha']='7'*40
            elif shape=='unknown-helper': c.generation[A.METADATA_WORKFLOW]['sha']='9'*40
            elif shape=='missing-source': c.runs[101]['referenced_workflows']=[]
            elif shape=='mixed-source': c.runs[101]['referenced_workflows'][0]['sha']='9'*40
            elif shape=='wrong-app': c.api.mutate=lambda e,v:{**v,'app':{'id':42}} if '/check-suites/' in e else v
            elif shape=='rerun': c.runs[101]['run_attempt']=2
            elif shape=='heavy':
                c.jobs[101]=[{'id':145,'run_id':101,'run_attempt':1,'head_sha':c.binding['head_sha'],
                    'name':'project / Shared tests','status':'queued','conclusion':None,'started_at':None,'completed_at':None,
                    'check_run_url':f'https://api.github.com/{A.PREFIX}/check-runs/145'}]
            elif shape=='artifact': c.artifacts[101]=[{'id':1011,'name':'not-a-result'}]
            elif shape=='parents':
                c.api.mutate=lambda e,v:{**v,'parents':list(reversed(v['parents']))} if e.endswith('/git/commits/'+c.binding['merge_sha']) else v
            else:c.runs[101]['head_repository']['id']=12
            with self.subTest(shape=shape):
                if shape=='parents':
                    with self.assertRaises(P.ProtocolError): self.observe()
                    continue
                if shape=='forged-name-old-recipe': self.assertIsNone(self.observe())
                value=c.capture()
                self.assertFalse(value.inventory_complete)
                self.assertNotIn(101,value.metadata_nonproducers)

    def test_native_intent_identity_rejects_immutable_drift_and_unknown_job_even_late(self):
        c=self.case; initial=self.observe()
        for field,value in [('id',102),('run_attempt',2),('head_sha','9'*40),('display_title','user-controlled text')]:
            row={**c.runs[101],field:value}
            with self.subTest(field=field),self.assertRaises(P.ProtocolError): A.metadata_inventory_record(row,initial)
        for kind in ('late-artifact','late-heavy'):
            self.setUp();c=self.case;reads=0
            def mutate(endpoint,value):
                nonlocal reads
                target='/actions/runs/101/artifacts?' if kind=='late-artifact' else '/actions/runs/101/attempts/1/jobs?'
                if target in endpoint:
                    reads+=1
                    if reads>=2:
                        if kind=='late-artifact':
                            value['artifacts']=[{'id':1012,'name':'late-artifact'}]
                        else:
                            value['jobs']=[{'id':145,'run_id':101,'run_attempt':1,'head_sha':c.binding['head_sha'],
                                'name':'project / Shared tests','status':'queued','conclusion':None,
                                'started_at':None,'completed_at':None,
                                'check_run_url':f'https://api.github.com/{A.PREFIX}/check-runs/145'}]
                            c.jobs[101]=deepcopy(value['jobs'])
                        value['total_count']=1
                return value
            c.api.mutate=mutate
            with self.subTest(kind=kind):self.assertFalse(c.capture().inventory_complete)

    def test_unproven_queued_source_only_gets_a_bounded_read_only_wait(self):
        c=self.case
        with patch.object(c.adapter,'_capture_inventory_once',side_effect=A.SchedulingPending('source unavailable')) as read, \
                patch.object(A.time,'sleep') as sleep:
            result=c.adapter._capture_inventory(c.binding,c.policy,NOW)
        self.assertEqual(read.call_count,3)
        self.assertEqual(sleep.call_args_list,[unittest.mock.call(2),unittest.mock.call(2)])
        self.assertEqual(result[0],[])
        self.assertEqual(result[3],['native-scheduling-source-pending'])
        self.assertEqual(result[-1],{})



class IntegratedFakeApi(FakeApi):
    """Closed PR metadata survives deletion; no live topic/PR merge ref exists."""
    def detail(self, number):
        case, binding = self.case, self.case.binding
        if number != 17:
            if number not in case.associated_details:
                raise A.ApiError("full associated PR is unavailable")
            return deepcopy(case.associated_details[number])
        return {"id": 1700, "number": 17, "state": "closed", "merged": True,
                "merge_commit_sha": case.integrated, "merged_at": case.merged_at, "closed_at": case.merged_at,
                **{side: {"repo": {"id": 1319052603, "full_name": A.REPOSITORY},
                          "ref": binding[side + "_ref"], "sha": binding[side + "_sha"]}
                   for side in ("base", "head")}}

    def integrated_pr(self, number):
        endpoint = A.PREFIX + f"/pulls/{number}"
        self.calls.append(endpoint)
        self.case.legacy_pr_calls.append(number)
        return self.mutate(endpoint, self.detail(number))

    def json(self, endpoint):
        case, binding = self.case, self.case.binding
        path = endpoint[len(A.PREFIX):].lstrip("/").split("?", 1)[0]
        query = parse_qs(urlsplit(endpoint).query)
        if path == "pulls/17":
            result = self.detail(17)
            del result["merge_commit_sha"]
        elif path == "commits/" + case.integrated + "/pulls":
            page = int(query["page"][0])
            result = deepcopy(case.associated[(page - 1) * 100:page * 100])
            for row in result:
                detail = self.detail(row["number"]) if row["number"] in case.associated_details else self.detail(17)
                for side in ("base", "head"):
                    row.setdefault(side, deepcopy(detail[side]))
        elif path.startswith("branches/"):
            self._require(unquote(path[len("branches/"):]) == binding["base_ref"], endpoint)
            result = {"name": binding["base_ref"], "protected": True, "commit": {"sha": case.integrated}}
        elif path.startswith("git/ref/"):
            ref = unquote(path[len("git/ref/"):])
            self._require(ref in {"heads/main", "heads/" + binding["base_ref"]}, endpoint)
            revision = case.integrated if ref == "heads/" + binding["base_ref"] else "6" * 40
            result = {"ref": "refs/" + ref, "object": {"type": "commit", "sha": revision}}
        elif path == "git/commits/" + case.integrated:
            result = {"sha": case.integrated, "tree": {"sha": binding["merge_tree"]},
                      "parents": [{"sha": revision} for revision in binding["merge_parents"]]}
        elif path == "actions/workflows/" + str(case.push["workflow_id"]):
            result = {"id": case.push["workflow_id"], "path": case.push["path"]}
        elif path in {"actions/runs/500", "actions/runs/500/attempts/1"}:
            result = deepcopy(case.push)
        elif path == "check-suites/1500":
            result = {"id": 1500, "head_sha": case.integrated,
                      "repository": {"id": 1319052603, "full_name": A.REPOSITORY}, "app": {"id": 15368}}
        else:
            return super().json(endpoint)
        self.calls.append(endpoint)
        return self.mutate(endpoint, deepcopy(result))

    def _require(self, condition, endpoint):
        if not condition: self._unexpected(endpoint)


class RetainedIntegratedFakeApi(IntegratedFakeApi):
    """Complete finite native facts for normal unchanged first-parent hops."""
    def __init__(self, case, count):
        super().__init__(case)
        self.details, self.commits, self.extra_runs, self.extra_jobs = {}, {}, {}, {}
        self.by_head, self.pushes = {}, {}
        self.tree = case.binding['merge_tree']
        self.metadata = {**deepcopy(case.generation),
            '.github/workflows/browser-client.yml': {'mode':'100644','type':'blob','sha':'b'*40},
            A.METADATA_WORKFLOW: {'mode':'100644','type':'blob','sha':'c'*40}}
        self.helper = {'mode':'100644','type':'blob','sha':'d'*40}
        self.policy = A.MetadataPolicy(99, case.policy.caller_path,
            {'protected-producer-original-default-v1': self.metadata},
            {'protected-producer-original-default-v1': {A.METADATA_SOURCE:self.helper}})
        self.commits[case.integrated] = (self.tree, case.binding['merge_parents'])
        self.commits[case.binding['base_sha']] = ('e'*40, [])
        self.maps = {self.tree:{**deepcopy(self.metadata),A.METADATA_SOURCE:deepcopy(self.helper),
            'native.cpp':{'mode':'100644','type':'blob','sha':'f'*40}}}
        self.hops = []
        previous = case.integrated
        for index in range(1, count+1):
            number, push_id, ordinary_id = 17+index, 500+index, 700+index
            revision = hashlib.sha1(f'normal unchanged integration {index}'.encode()).hexdigest()
            head = hashlib.sha1(f'unchanged topic {index}'.encode()).hexdigest()
            merge = hashlib.sha1(f'original unchanged candidate {index}'.encode()).hexdigest()
            when = f'2026-10-15T10:04:{50+index:02}Z'
            parents = [previous,head]
            self.commits[revision] = self.commits[merge] = (self.tree,parents)
            detail = {'id':number*100,'number':number,'state':'closed','merged':True,
                'merge_commit_sha':revision,'merged_at':when,'closed_at':when,
                'base':{'ref':case.binding['base_ref'],'sha':previous,
                    'repo':{'id':1319052603,'full_name':A.REPOSITORY}},
                'head':{'ref':f'task/main/unchanged-{index}','sha':head,
                    'repo':{'id':1319052603,'full_name':A.REPOSITORY}}}
            self.details[number] = detail
            common = {'run_attempt':1,'repository':{'id':1319052603,'full_name':A.REPOSITORY},
                'head_repository':{'id':1319052603,'full_name':A.REPOSITORY},
                'status':'completed','conclusion':'success','updated_at':when}
            ordinary = {**common,'id':ordinary_id,'run_number':ordinary_id,'workflow_id':99,'check_suite_id':ordinary_id+1000,
                'event':'pull_request','path':case.policy.caller_path,'head_sha':head,
                'head_branch':detail['head']['ref'],'display_title':A.ORDINARY_RUN_NAME,
                'run_started_at':'2026-10-15T10:04:50Z','pull_requests':[],
                'referenced_workflows':[{'path':A.REPOSITORY+'/'+A.METADATA_WORKFLOW+'@'+merge,
                    'sha':merge,'ref':f'refs/pull/{number}/merge'}]}
            push = {**common,'id':push_id,'workflow_id':350930890,'check_suite_id':push_id+1000,
                'event':'push','path':'.github/workflows/parent-qualification.yml',
                'head_sha':revision,'head_branch':case.binding['base_ref'],
                'run_started_at':when,'referenced_workflows':[]}
            self.extra_runs[ordinary_id],self.extra_runs[push_id] = ordinary,push
            self.by_head[head] = [ordinary]
            self.pushes[revision] = [push]
            expected={A.METADATA_JOB:'success','Select required repository checks':'success',
                'native':'skipped','project':'skipped','android':'skipped',
                'documentation / documentation':'success',
                'workflow-security / Actionlint, Zizmor, and Gitleaks':'success',
                'workflow-contracts':'success','repository-checks':'success'}
            self.extra_jobs[ordinary_id] = self.jobs(ordinary,expected)
            self.step(ordinary_id,A.METADATA_JOB,A.ORDINARY_SOURCE_STEP+' (diagnostics absent)')
            self.step(ordinary_id,'repository-checks','Require all selected checks to succeed')
            expected={'Plan current parent owners':'success' if case.binding['base_ref'] in {'android-main','android-vr'} else 'skipped',
                'Common parent tests':'success','Android platform tests':'skipped','Qualify exact parent':'success'}
            self.extra_jobs[push_id] = self.jobs(push,expected)
            for name in ('Authenticate the protected base commitment before repository imports','Independently verify unchanged parent inputs'):
                self.step(push_id,'Common parent tests',name)
            for name in ('Execute common parent suites without claiming platform evidence','Run complete host qualification',
                    'Run independently selected parent host contracts','Create content-addressed qualification evidence',
                    'Upload immutable qualification evidence','Check only affected tool dependencies and behavior',
                    'Check independently selected S3 package dependencies and behavior'):
                self.step(push_id,'Common parent tests',name,'skipped')
            for name in ('Require protected parent aggregate source admission','Require both actual parent owners'):
                self.step(push_id,'Qualify exact parent',name)
            self.hops.append({'revision':revision,'head':head,'candidate':merge,'number':number,
                'ordinary':ordinary_id,'push':push_id,'previous':previous})
            previous=revision
        self.current = previous
        self.default = previous
        self.fallback_json = None
        self.run_id = self.hops[-1]['push'] if self.hops else 500

    def jobs(self, run, expected):
        return [{'id':run['id']*100+index,'run_id':run['id'],'run_attempt':1,'head_sha':run['head_sha'],
            'name':name,'status':'completed','conclusion':conclusion,'steps':[],
            'started_at':run['run_started_at'],'completed_at':run['updated_at'],
            'check_run_url':f"https://api.github.com/{A.PREFIX}/check-runs/{run['id']*100+index}"}
            for index,(name,conclusion) in enumerate(expected.items(),1)]

    def step(self, run_id, job, name, conclusion='success'):
        row=next(value for value in self.extra_jobs[run_id] if value['name']==job)
        row['steps'].append({'name':name,'status':'completed','conclusion':conclusion,
            'started_at':row['started_at'],'completed_at':row['completed_at']})

    def integrated_pr(self, number):
        if number not in self.details:return super().integrated_pr(number)
        endpoint=A.PREFIX+f'/pulls/{number}';self.calls.append(endpoint)
        return self.mutate(endpoint,deepcopy(self.details[number]))

    def immutable_tree(self, identity):
        value={'sha':identity,'truncated':False,'tree':[{'path':name,**entry} for name,entry in self.maps[identity].items()]}
        return self.mutate(A.PREFIX+'/git/trees/'+identity+'?recursive=1',deepcopy(value))

    def fallback(self, endpoint):
        return self.fallback_json(endpoint) if self.fallback_json is not None else super().json(endpoint)

    def json(self, endpoint):
        path=endpoint[len(A.PREFIX):].lstrip('/').split('?',1)[0]
        query=parse_qs(urlsplit(endpoint).query)
        if path == 'branches/'+self.case.binding['base_ref']:
            result={'name':self.case.binding['base_ref'],'protected':True,'commit':{'sha':self.current}}
        elif path.startswith('git/ref/heads/') and unquote(path[len('git/ref/'):]) in {'heads/main','heads/'+self.case.binding['base_ref']}:
            ref=unquote(path[len('git/ref/'):]);self._require(ref in {'heads/main','heads/'+self.case.binding['base_ref']},endpoint)
            result={'ref':'refs/'+ref,'object':{'type':'commit','sha':self.default if ref=='heads/main' else self.current}}
        elif path.startswith('git/commits/') and path.rsplit('/',1)[1] in self.commits:
            revision=path.rsplit('/',1)[1];tree,parents=self.commits[revision]
            result={'sha':revision,'tree':{'sha':tree},'parents':[{'sha':value} for value in parents]}
        elif path.startswith('commits/') and path.endswith('/pulls'):
            revision=path.split('/')[1]
            rows=[value for value in self.details.values() if value['merge_commit_sha']==revision]
            if not rows:return self.fallback(endpoint)
            result=[{key:deepcopy(value[key]) for key in ('id','number','state','base','head')} for value in rows]
        elif path.startswith('git/trees/'):
            identity=path.rsplit('/',1)[1]
            ordinary=lambda name,sha:{'path':name,'mode':'040000','type':'tree','sha':sha}
            nodes={'e'*40:[],self.tree:[ordinary('.github','1'*40),ordinary('tools','a'*40)],
                '1'*40:[ordinary('workflows','2'*40)],
                '2'*40:[{'path':name.rsplit('/',1)[1],**entry} for name,entry in self.metadata.items()],
                'a'*40:[ordinary('repository-checks','b'*40)],
                'b'*40:[{'path':'metadata_context.py',**self.helper}]}
            if identity not in nodes:return self.fallback(endpoint)
            result={'sha':identity,'truncated':False,'tree':nodes[identity]}
        elif path=='actions/workflows/99/runs' and query.get('head_sha',[None])[0] in self.by_head:
            self._require(set(query)=={'head_sha','per_page','page'},endpoint)
            result=self.page(self.by_head[query['head_sha'][0]],'workflow_runs',query)
        elif path=='actions/workflows/350930890/runs':
            self._require(query.get('branch')==[self.case.binding['base_ref']] and query.get('event')==['push']
                and query.get('head_sha',[None])[0] in self.pushes,endpoint)
            result=self.page(self.pushes[query['head_sha'][0]],'workflow_runs',query)
        elif path.startswith('actions/runs/') and int(path.split('/')[2]) in self.extra_runs:
            identity=int(path.split('/')[2]);parts=path.split('/')
            if len(parts)==3 or len(parts)==5 and parts[3]=='attempts':result=self.extra_runs[identity]
            elif parts[-1]=='jobs':result=self.page(self.extra_jobs[identity],'jobs',query)
            elif parts[-1]=='artifacts':result=self.page([],'artifacts',query)
            else:self._unexpected(endpoint)
        elif path.startswith('check-suites/') and any(row['check_suite_id']==int(path.rsplit('/',1)[1]) for row in self.extra_runs.values()):
            run=next(row for row in self.extra_runs.values() if row['check_suite_id']==int(path.rsplit('/',1)[1]))
            result={'id':run['check_suite_id'],'head_sha':run['head_sha'],'repository':{'id':1319052603,'full_name':A.REPOSITORY},'app':{'id':15368}}
        elif path.startswith('check-runs/') and any(job['id']==int(path.rsplit('/',1)[1]) for jobs in self.extra_jobs.values() for job in jobs):
            job=next(job for jobs in self.extra_jobs.values() for job in jobs if job['id']==int(path.rsplit('/',1)[1]))
            run=self.extra_runs[job['run_id']]
            result={'id':job['id'],'head_sha':job['head_sha'],'app':{'id':15368},'check_suite':{'id':run['check_suite_id']},
                **{key:job[key] for key in ('name','status','conclusion','started_at','completed_at')}}
        else:return self.fallback(endpoint)
        self.calls.append(endpoint);return self.mutate(endpoint,deepcopy(result))


class IntegratedSourceTests(unittest.TestCase):
    def setUp(self):
        self.case = AdapterTests(methodName="runTest")
        self.case.setUp()
        self.case.integrated, self.case.merged_at = "9" * 40, "2026-10-15T10:04:50Z"
        self.case.associated = [{"id": 1700, "number": 17, "state": "closed"}]
        self.case.associated_details, self.case.legacy_pr_calls = {}, []
        self.case.push = {"id": 500, "workflow_id": 350930890, "check_suite_id": 1500,
                          "path": ".github/workflows/parent-qualification.yml", "event": "push",
                          "head_sha": self.case.integrated, "head_branch": "main", "run_attempt": 1,
                          "run_started_at": "2026-10-15T10:04:51Z", "status": "in_progress", "conclusion": None,
                          **{key: {"id": 1319052603, "full_name": A.REPOSITORY}
                             for key in ("repository", "head_repository")}}
        self.case.runs[100]["pull_requests"] = []
        self.api = IntegratedFakeApi(self.case)
        self.adapter = A.Adapter(self.api)

    def capture(self):
        return self.adapter.capture_integrated(500, self.case.plan, self.case.policy, now=NOW)

    def verify(self, *, context=None, clock=lambda: NOW):
        return self.adapter.verify_integrated(500, self.case.plan, self.case.policy,
                                              {"shared-host": context or self.case.context}, clock=clock)

    def add_association(self, *, number=18, state="open", merged=False, merge="6" * 40):
        detail = self.api.detail(17)
        detail.update(id=number * 100, number=number, state=state, merged=merged, merge_commit_sha=merge,
                      merged_at=self.case.merged_at if merged else None,
                      closed_at=self.case.merged_at if state == "closed" else None)
        detail["base"].update(ref="android-phone", sha=self.case.integrated)
        detail["head"].update(ref="sync/android-phone/example", sha="7" * 40)
        self.case.associated_details[number] = detail
        self.case.associated.append({key: deepcopy(detail[key]) for key in ("id", "number", "state", "base", "head")})

    def test_deleted_topic_lookup_preserves_original_candidate_receipt_and_expiry(self):
        with patch.object(P.execution, "execute", side_effect=AssertionError("no candidate execution")):
            snapshot, result = self.capture(), self.verify()
        self.assertTrue(result["verified"])
        self.assertEqual(snapshot.binding, self.case.binding)
        self.assertEqual(result["source_chain"]["producer_commit"], self.case.binding["merge_sha"])
        self.assertEqual(result["integration"]["commit"], self.case.integrated)
        self.assertNotEqual(result["integration"]["commit"], snapshot.binding["merge_sha"])
        self.assertEqual(result["expires_at"], self.case.aggregate["expires_at"])
        self.assertEqual(result["qualified_at"], self.case.aggregate["qualified_at"])
        self.assertFalse(any("commits/refs/pull/" in endpoint or
                             "/git/ref/heads/" + self.case.binding["head_ref"] in endpoint
                             for endpoint in self.api.calls))
        self.assertTrue(all(endpoint.startswith(A.PREFIX) for endpoint in self.api.calls))
        self.assertTrue(self.case.legacy_pr_calls, "actual merged SHA requires the explicitly versioned full PR endpoint")

    def test_original_source_context_is_never_aliased_to_integrated_commit(self):
        with self.assertRaises(P.ProtocolError):
            self.verify(context=replace(self.case.context, candidate_commit=self.case.integrated))

    def test_current_pending_consumer_is_provenance_not_required_completed_test_proof(self):
        for status, conclusion in (("queued", None), ("in_progress", None), ("completed", "success")):
            self.case.push.update(status=status, conclusion=conclusion)
            with self.subTest(status=status):
                result = self.verify()
                self.assertTrue(result["verified"])
                self.assertEqual(result["integration"]["push_status"], status)
                self.assertEqual(result["run_id"], 100, "proof belongs to original producer, not consumer500")
        for conclusion in ("failure", "cancelled", "timed_out", "skipped"):
            self.case.push.update(status="completed", conclusion=conclusion)
            with self.subTest(conclusion=conclusion), self.assertRaises(P.ProtocolError): self.capture()

    def test_open_contract_still_rejects_missing_run_pr_association(self):
        self.assertFalse(self.case.capture().inventory_complete)
        with self.assertRaises(P.ProtocolError): self.case.verify()

    def test_all_seven_exact_registered_protected_push_profiles_capture(self):
        for workflow_id, (path, branches) in A.PROTECTED_PUSH_WORKFLOWS.items():
            for target in sorted(branches):
                self.case.binding["base_ref"] = target
                self.case.push.update(workflow_id=workflow_id, path=path, head_branch=target)
                with self.subTest(target=target):
                    # This is source capture only: changed target descriptors
                    # deliberately cannot become reusable proof by mutation.
                    binding, refs = self.adapter._integrated_current(500, 15368, NOW)
                    self.assertEqual(binding["base_ref"], target)
                    self.assertEqual(refs["target"], self.case.integrated)

    def test_push_event_current_protection_source_app_and_first_attempt_are_required(self):
        cases = (("event", "pull_request"), ("event", "workflow_dispatch"), ("run_attempt", 2),
                 ("workflow_id", 42), ("path", ".github/workflows/other.yml"),
                 ("head_branch", "topic"), ("head_sha", "f" * 40),
                 ("status", "queued-without-contract"), ("conclusion", "failure"))
        original = deepcopy(self.case.push)
        for key, value in cases:
            self.case.push = {**deepcopy(original), key: value}
            with self.subTest(key=key, value=value), self.assertRaises(P.ProtocolError): self.capture()
        self.case.push = original
        for mode in ("fork", "head-fork", "app", "suite", "unprotected", "branch-tip", "independent-ref", "workflow"):
            def changed(endpoint, result):
                if "/actions/runs/500" in endpoint and mode in {"fork", "head-fork"}:
                    result["repository" if mode == "fork" else "head_repository"]["id"] = 42
                elif endpoint.endswith("/check-suites/1500"):
                    if mode == "app": result["app"]["id"] = 42
                    elif mode == "suite": result["head_sha"] = "f" * 40
                elif endpoint.endswith("/branches/main"):
                    if mode == "unprotected": result["protected"] = False
                    elif mode == "branch-tip": result["commit"]["sha"] = "f" * 40
                elif mode == "independent-ref" and endpoint.endswith("/git/ref/heads/main"):
                    result["object"]["sha"] = "f" * 40
                elif mode == "workflow" and endpoint.endswith("/actions/workflows/350930890"):
                    result["path"] = ".github/workflows/other.yml"
                return result
            self.api.mutate = changed
            with self.subTest(mode=mode), self.assertRaises(P.ProtocolError): self.capture()

    def test_unique_actual_merged_same_fork_pr_and_exact_ordered_parents_are_required(self):
        for mode in ("unmerged", "open", "foreign-head", "foreign-base", "wrong-pr", "wrong-merge",
                     "wrong-base", "wrong-head", "target", "parents", "squash", "rebase", "different-tree"):
            def changed(endpoint, result):
                if endpoint.endswith("/pulls/17"):
                    if mode == "unmerged": result["merged"] = False
                    elif mode == "open": result["state"] = "open"
                    elif mode in {"foreign-head", "foreign-base"}: result[mode.split("-")[1]]["repo"]["id"] = 42
                    elif mode == "wrong-pr": result["id"] = 1701
                    elif mode == "wrong-merge": result["merge_commit_sha"] = "f" * 40
                    elif mode in {"wrong-base", "wrong-head"}: result[mode.split("-")[1]]["sha"] = "f" * 40
                    elif mode == "target": result["base"]["ref"] = "android-main"
                elif endpoint.endswith("/git/commits/" + self.case.integrated):
                    if mode == "parents": result["parents"].reverse()
                    elif mode == "squash": result["parents"] = result["parents"][:1]
                    elif mode == "rebase": result["parents"].append({"sha": "f" * 40})
                    elif mode == "different-tree": result["tree"]["sha"] = "f" * 40
                return result
            self.api.mutate = changed
            with self.subTest(mode=mode), self.assertRaises(P.ProtocolError): self.capture()

    def test_association_inventory_missing_multiple_duplicate_or_unbounded_deny(self):
        original = deepcopy(self.case.associated)
        for items in ([], original + [{**original[0], "id": 1701, "number": 18}], original + original,
                      [{**original[0], "id": index + 1, "number": index + 1} for index in range(1000)]):
            self.case.associated = items
            with self.subTest(count=len(items)), self.assertRaises(P.ProtocolError): self.capture()
        self.case.associated = original
        self.api.mutate = lambda endpoint, value: ({"items": value} if "/pulls?" in endpoint else value)
        with self.assertRaises(P.ProtocolError): self.capture()

    def test_known_open_and_merged_downstream_associations_do_not_supply_or_obstruct_introducer(self):
        self.add_association()
        self.add_association(number=19, state="closed", merged=True, merge="8" * 40)
        snapshot = self.capture()
        self.assertEqual([item["classification"] for item in snapshot.references["associated_prs"]],
                         ["introducer", "known-nonintroducer", "known-nonintroducer"])
        self.assertEqual(self.verify()["run_id"], 100)
        self.assertEqual(set(self.case.legacy_pr_calls), {17, 18, 19})
        self.assertFalse(any("refs/pull/18" in endpoint or "refs/pull/19" in endpoint for endpoint in self.api.calls))
        self.case.associated = self.case.associated[1:]
        with self.assertRaisesRegex(P.ProtocolError, "introducer PR is missing"): self.capture()

    def test_multiple_or_contradictory_introducers_and_unknown_associations_deny(self):
        for mode in ("second-introducer", "open-claims-integration", "unknown-detail", "foreign", "conflicting-summary"):
            self.case.associated = [{"id": 1700, "number": 17, "state": "closed"}]
            self.case.associated_details = {}
            self.add_association(state="closed" if mode == "second-introducer" else "open",
                                 merged=mode == "second-introducer",
                                 merge=self.case.integrated if mode in {"second-introducer", "open-claims-integration"}
                                 else "6" * 40)
            if mode == "unknown-detail": del self.case.associated_details[18]
            elif mode == "foreign": self.case.associated_details[18]["head"]["repo"]["id"] = 42
            elif mode == "conflicting-summary": self.case.associated[1]["head"]["sha"] = "f" * 40
            with self.subTest(mode=mode), self.assertRaises(P.ProtocolError): self.capture()

    def test_missing_legacy_merge_field_and_mismatched_full_summary_identity_deny(self):
        for mode in ("missing-merge", "missing-merged", "state", "base", "head", "summary-merge"):
            def changed(endpoint, result):
                if endpoint.endswith("/pulls/17"):
                    if mode == "missing-merge": del result["merge_commit_sha"]
                    elif mode == "missing-merged": del result["merged"]
                    elif mode == "state": result["state"] = "open"
                    elif mode in {"base", "head"}: result[mode]["sha"] = "f" * 40
                elif mode == "summary-merge" and "/pulls?" in endpoint:
                    result[0]["merge_commit_sha"] = "f" * 40
                return result
            self.api.mutate = changed
            with self.subTest(mode=mode), self.assertRaises(P.ProtocolError): self.capture()

    def test_recorded_seven_real_api_shapes_authenticate_current_introducers(self):
        # Actual minimal field observations, 2026-10-16. Summaries and 2026
        # full PRs omit merge_commit_sha; only explicit 2022 full PRs supply it.
        # These fake API source snapshots are not hosted qualification receipts.
        records = (
            ("main", 1321, 4883606325, "727c6e2b9ec33dbd343740f5daaaa92196e53120",
             "ad636dc97fe7e213c7ff626dd5b5cf7873a7d4c2", "25ec68fbfa00768828f82ee78a56a8fdeea295fc",
             "fix/main/ci-sandbox-host-snapshot-qualification-20261016", "2026-10-16T05:16:32Z"),
            ("apple-main", 1261, 4869813471, "f7f6c47aff64213deb46c2d0b834b6df2cc93b06",
             "20f9c44665bc08e9e924d2da1d0c3429d8ab0c23", "a9b600cabc5a3d85e1b107e1734545847c53cb5e",
             "reconcile/apple/ios-kit-fetch-fixture-policy-20261015", "2026-10-15T07:47:02Z"),
            ("apple-ios", 1300, 4878868180, "2fc894a0605103843b36653f250f854714a963ee",
             "3941e0861eb7995b9cfa6e4116e9f70bc25d9837", "5ea4f920e01be7c48650affcda75b6ec5e0d0efa",
             "fix/ios/host-only-qualification-20261015", "2026-10-15T20:05:31Z"),
            ("android-main", 1272, 4871975509, "664fb0e83dd80f1557571471d2a8c48a86d1b2ee",
             "17e3e529c4a82fef8057558206cb9d4ceed680bd", "d753ff8ef163207c7466660d4872b0a71c20bb93",
             "fix/android/common-qml-reporter-fixture-isolation-20261015", "2026-10-15T10:58:30Z"),
            ("android-phone", 1286, 4874106309, "a89d21db26a30aa1cc6627f40708c4b2801fc480",
             "277bad9119c9ee16f4bbb3038cedeb6625741d34", "2338d3547fec0a2e3a337bc51775658cb17019fd",
             "fix/android-phone/adopted-history-pr-1198-319a59f04eae", "2026-10-15T13:46:39Z"),
            ("android-vr", 1270, 4871580861, "2199dc03b796b14d69973b50cb538e3779866306",
             "d2f09ed8872f48dd81d157ed3881db74ae9795d2", "4895b4a4d10b9a023ff921ed6b4134e85369370a",
             "reconcile/android-vr/shared-reporting-current-parent-20261015", "2026-10-15T10:26:26Z"),
            ("android-vr-pico", 1276, 4872457039, "410847ff312553de81f9f8ff7e32029b22495603",
             "5505cf999978c07a4d42de825362270f9282d097", "abb558cde0fd9b40370f643cc61a57a8372246b7",
             "fix/android-pico/activity-focus-current-parent-20261015", "2026-10-15T11:44:51Z"),
        )
        for target, number, identity, revision, base, head, head_ref, merged in records:
            self.case.integrated, self.case.merged_at = revision, merged
            self.case.binding.update(base_ref=target, base_sha=base, head_sha=head, head_ref=head_ref,
                                     merge_parents=[base, head])
            detail = {"id": identity, "number": number, "state": "closed", "merged": True,
                      "merge_commit_sha": revision, "merged_at": merged, "closed_at": merged,
                      **{side: {"ref": ref, "sha": sha, "repo": {"id": 1319052603, "full_name": A.REPOSITORY}}
                         for side, ref, sha in (("base", target, base), ("head", head_ref, head))}}
            self.case.associated_details = {number: detail}
            self.case.associated = [{key: deepcopy(detail[key]) for key in
                                     ("id", "number", "state", "base", "head", "merged_at", "closed_at")}]
            workflow_id = next(identity for identity, (_, targets) in A.PROTECTED_PUSH_WORKFLOWS.items()
                               if target in targets)
            self.case.push.update(workflow_id=workflow_id, path=A.PROTECTED_PUSH_WORKFLOWS[workflow_id][0],
                                  head_branch=target, head_sha=revision, run_started_at="2026-10-16T05:32:01Z")
            with self.subTest(target=target):
                binding, refs = self.adapter._integrated_current(500, 15368, NOW.replace(day=17))
                self.assertEqual(binding["pull_request"], number)
                self.assertEqual(refs["integration"]["commit"], revision)
                self.assertEqual(refs["associated_prs"][0]["classification"], "introducer")
                self.assertNotIn("merge_commit_sha", self.case.associated[0])

    def test_known_nonintroducer_inventory_is_also_bookended(self):
        self.add_association()
        count = 0
        def changed(endpoint, result):
            nonlocal count
            if "/commits/" in endpoint and "/pulls?" in endpoint:
                count += 1
                if count >= 2:
                    self.case.associated_details[18]["head"]["sha"] = "f" * 40
                    result[1]["head"]["sha"] = "f" * 40
            return result
        self.api.mutate = changed
        with self.assertRaisesRegex(P.ProtocolError, "current refs changed"): self.capture()

    def test_missing_original_ref_unknown_chain_or_conflicting_run_association_deny(self):
        for mode in ("missing", "ref", "sha", "foreign", "wrong-pr", "multiple-pr"):
            def changed(endpoint, result):
                if "/actions/runs/100" in endpoint and "referenced_workflows" in result:
                    if mode == "missing": result["referenced_workflows"] = []
                    elif mode == "ref": result["referenced_workflows"][0]["ref"] = "refs/heads/main"
                    elif mode == "sha": result["referenced_workflows"][0]["sha"] = self.case.integrated
                    elif mode == "foreign": result["repository"]["id"] = 42
                    elif mode == "wrong-pr": result["pull_requests"] = [{"number": 18}]
                    else: result["pull_requests"] = [{"number": 17}, {"number": 18}]
                return result
            self.api.mutate = changed
            with self.subTest(mode=mode), self.assertRaises(P.ProtocolError): self.verify()

    def test_partial_capped_or_changed_original_run_inventory_cannot_choose_old_green(self):
        for mode in ("partial", "capped", "changed"):
            count = 0
            def changed(endpoint, result):
                nonlocal count
                if "/actions/workflows/99/runs?" in endpoint:
                    count += 1
                    if mode == "partial": result["total_count"] = 2
                    elif mode == "capped": result["total_count"] = 1000
                    elif count >= 2:
                        result["workflow_runs"] = []
                        result["total_count"] = 0
                return result
            self.api.mutate = changed
            with self.subTest(mode=mode), self.assertRaises(P.ProtocolError): self.verify()

    def test_two_distinct_original_candidates_with_same_tree_and_parents_are_ambiguous(self):
        original = self.capture().observations[0].run
        self.case.add_run(replace(original, run_id=101,
                                 publisher=replace(original.publisher, job_id=111),
                                 owners={name: replace(job, job_id=121) for name, job in original.owners.items()},
                                 final_publisher=replace(original.final_publisher,
                                                         job=replace(original.final_publisher.job, job_id=131))),
                          descriptor=False)
        alternate = "f" * 40
        self.case.originals[alternate] = (self.case.binding["merge_tree"], self.case.binding["merge_parents"][:])
        self.case.runs[101]["referenced_workflows"][0].update(
            sha=alternate, path=A.REPOSITORY + "/" + self.case.pp.workflow_path + "@" + alternate)
        with self.assertRaisesRegex(P.ProtocolError, "ambiguous"): self.capture()

    def test_known_other_original_is_classified_without_its_artifacts_but_unknown_is_not(self):
        original = self.capture().observations[0].run
        self.case.add_run(replace(original, run_id=101, conclusion="failure"), descriptor=False)
        self.case.originals["f" * 40] = ("8" * 40, ["7" * 40, self.case.binding["head_sha"]])
        self.case.runs[101]["referenced_workflows"][0].update(
            sha="f" * 40, path=A.REPOSITORY + "/" + self.case.pp.workflow_path + "@" + "f" * 40)
        snapshot = self.capture()
        self.assertTrue(snapshot.inventory_complete)
        self.assertEqual(set(snapshot.other_candidates), {101})
        self.assertTrue(self.verify()["verified"])
        self.assertFalse(any("/runs/101/artifacts" in endpoint for endpoint in self.api.calls))
        self.case.runs[101]["referenced_workflows"] = []
        self.assertFalse(self.capture().inventory_complete)
        with self.assertRaises(P.ProtocolError): self.verify()

    def test_newer_pending_failed_cancelled_or_rerun_source_never_uses_older_green(self):
        original = self.capture().observations[0].run
        for status, conclusion, attempt in (("queued", None, 1), ("completed", "failure", 1),
                                             ("completed", "cancelled", 1), ("completed", "success", 2)):
            later = replace(original, run_id=101, attempt=attempt, latest_attempt=attempt,
                            status=status, conclusion=conclusion, attempt_started_at="2026-10-15T10:01:00Z",
                            publisher=None, owners={}, final_publisher=None)
            if attempt == 1:
                later = replace(later, publisher=replace(original.publisher, job_id=111,
                                started_at="2026-10-15T10:01:00Z", completed_at="2026-10-15T10:01:30Z"))
            self.case.add_run(later, descriptor=attempt == 1)
            with self.subTest(status=status, attempt=attempt):
                snapshot = self.capture()
                authority = P.select_authority(snapshot.observations, snapshot.binding, self.case.plan, self.case.pp,
                                               inventory_complete=snapshot.inventory_complete, now=NOW)
                self.assertEqual(authority["state"], "unresolved" if attempt == 2 else
                                 "pending" if status == "queued" else "failed")
                with self.assertRaises(P.ProtocolError): self.verify()
            del self.case.runs[101]; del self.case.jobs[101]; del self.case.artifacts[101]

    def test_current_push_pr_association_protection_and_default_are_bookended(self):
        for mode in ("pr", "association", "protection", "target", "attempt", "run-status"):
            counts = {}
            def changed(endpoint, result):
                counts[endpoint] = counts.get(endpoint, 0) + 1
                if counts[endpoint] >= 2:
                    if mode == "pr" and endpoint.endswith("/pulls/17"): result["head"]["sha"] = "f" * 40
                    elif mode == "association" and "/commits/" in endpoint and "/pulls?" in endpoint:
                        result.append({**result[0], "id": 1701, "number": 18})
                    elif mode == "protection" and endpoint.endswith("/branches/main"): result["protected"] = False
                    elif mode == "target" and endpoint.endswith("/git/ref/heads/main"):
                        result["object"]["sha"] = "f" * 40
                    elif mode == "attempt" and endpoint.endswith("/actions/runs/500"): result["run_attempt"] = 2
                    elif mode == "run-status" and "/actions/runs/500" in endpoint:
                        result.update(status="completed", conclusion="success")
                return result
            self.api.mutate = changed
            with self.subTest(mode=mode), self.assertRaises(P.ProtocolError): self.verify()

    def test_default_ref_is_bookended_independently_of_child_target(self):
        self.case.binding["base_ref"] = "android-main"
        self.case.push["head_branch"] = "android-main"
        count = 0
        def changed(endpoint, result):
            nonlocal count
            if endpoint.endswith("/git/ref/heads/main"):
                count += 1
                if count >= 2: result["object"]["sha"] = "f" * 40
            return result
        self.api.mutate = changed
        with self.assertRaisesRegex(P.ProtocolError, "current refs changed"): self.capture()

    def test_original_evidence_must_finish_before_merge_and_keep_original_expiry(self):
        for merged in ("2026-10-15T10:03:00Z", "2026-10-15T10:04:10Z", "2026-10-15T10:04:40Z"):
            self.case.merged_at = merged
            with self.subTest(merged=merged), self.assertRaisesRegex(P.ProtocolError, "before integration"):
                self.verify()
        self.case.merged_at = "2026-10-15T10:04:50Z"
        later = NOW.replace(hour=12)
        with self.assertRaises(P.ProtocolError): self.verify(clock=lambda: later)

    def test_merge_and_push_chronology_and_latest_attempt_bookends_are_required(self):
        for mode in ("future-merge", "early-close", "early-push", "latest-attempt", "attempt-head"):
            def changed(endpoint, result):
                if endpoint.endswith("/pulls/17"):
                    if mode == "future-merge": result["merged_at"] = "2026-10-15T10:06:00Z"
                    elif mode == "early-close": result["closed_at"] = "2026-10-15T10:04:40Z"
                elif "/actions/runs/500" in endpoint:
                    if mode == "early-push": result["run_started_at"] = "2026-10-15T10:04:40Z"
                    elif mode == "latest-attempt" and endpoint.endswith("/actions/runs/500"):
                        result["run_attempt"] = 2
                    elif mode == "attempt-head" and endpoint.endswith("/attempts/1"):
                        result["head_sha"] = "f" * 40
                return result
            self.api.mutate = changed
            with self.subTest(mode=mode), self.assertRaises(P.ProtocolError): self.capture()

    def retained(self, count=1):
        api = RetainedIntegratedFakeApi(self.case,count)
        self.adapter = A.Adapter(api); self.api = api
        self.case.policy = replace(self.case.policy,metadata_generations=api.policy.generations,metadata_sources=api.policy.sources)
        return api

    def test_one_and_two_validated_same_tree_hops_retain_original_candidate_E_and_expiry(self):
        for count in (1,2):
            with self.subTest(hops=count):
                api=self.retained(count)
                snapshot=self.adapter.capture_integrated(api.run_id,self.case.plan,self.case.policy,now=NOW)
                result=self.adapter.verify_integrated(api.run_id,self.case.plan,self.case.policy,{'shared-host':self.case.context},clock=lambda:NOW)
                self.assertEqual(snapshot.binding,self.case.binding)
                self.assertEqual(result['integration']['commit'],api.current)
                self.assertEqual(result['origin_integration']['commit'],self.case.integrated)
                self.assertEqual(len(result['retained_no_execution_hops']),count)
                self.assertEqual(result['source_chain']['producer_commit'],self.case.binding['merge_sha'])
                self.assertEqual(result['qualified_at'],self.case.aggregate['qualified_at'])
                self.assertEqual(result['expires_at'],self.case.aggregate['expires_at'])
                self.assertNotIn('environment',result['retained_no_execution_hops'][0])

    def test_same_tree_hops_never_pass_unknown_failed_or_changed_native_evidence(self):
        original_run = deepcopy(self.case.runs[100])
        for change in ('failed-pr','retry-pr','failed-push','retry-push','step','app','recipe','helper','tree','mode','parents','missing-pr','original-failed','original-retry','descriptor','publisher-hash','expiry','cap'):
            with self.subTest(change=change):
                self.case.runs[100] = deepcopy(original_run)
                api=self.retained(9 if change=='cap' else 2);hop=api.hops[-1]
                if change=='failed-pr':api.extra_runs[hop['ordinary']]['conclusion']='failure'
                elif change=='retry-pr':api.extra_runs[hop['ordinary']]['run_attempt']=2
                elif change=='failed-push':api.extra_runs[hop['push']]['conclusion']='failure'
                elif change=='retry-push':api.extra_runs[hop['push']]['run_attempt']=2
                elif change=='step':
                    next(row for row in api.extra_jobs[hop['push']] if row['name']=='Common parent tests')['steps'][1]['conclusion']='skipped'
                elif change=='app':
                    api.mutate=lambda endpoint,value:{**value,'app':{'id':42}} if '/check-suites/' in endpoint else value
                elif change in {'recipe','helper'}:
                    def source_drift(endpoint,value):
                        if endpoint.endswith('/git/trees/'+('2'*40 if change=='recipe' else 'b'*40)):
                            value['tree'][0]['sha']='0'*40
                        return value
                    api.mutate=source_drift
                elif change=='tree':api.commits[hop['previous']]=('e'*40,api.commits[hop['previous']][1])
                elif change=='mode':api.maps[api.tree]['native.cpp']['mode']='120000'
                elif change=='parents':api.commits[hop['revision']]=(api.tree,[hop['head'],hop['previous']])
                elif change=='missing-pr':api.by_head[hop['head']]=[]
                elif change=='original-failed':self.case.runs[100]['conclusion']='failure'
                elif change=='original-retry':self.case.runs[100]['run_attempt']=2
                elif change in {'descriptor','publisher-hash'}:
                    def original_drift(endpoint,value):
                        if change=='descriptor' and '/actions/runs/100/artifacts?' in endpoint:
                            value['artifacts']=[row for row in value['artifacts'] if not row['name'].startswith('ci-descriptor-')]
                            value['total_count']=len(value['artifacts'])
                        if change=='publisher-hash' and '/actions/runs/100/attempts/1/jobs?' in endpoint:
                            for job in value['jobs']:
                                if job['name'].startswith(self.case.policy.final_publisher_prefix):
                                    job['name']=self.case.policy.final_publisher_prefix+'0'*64
                        return value
                    api.mutate=original_drift
                elif change=='expiry':
                    api.mutate=lambda endpoint,value: ({**value,'expired':True} if '/actions/artifacts/' in endpoint else value)
                with self.assertRaises((P.ProtocolError,KeyError)):
                    self.adapter.verify_integrated(api.run_id,self.case.plan,self.case.policy,{'shared-host':self.case.context},clock=lambda:NOW)

    def test_retained_chain_and_original_publication_cutoff_are_bookended(self):
        api=self.retained(2);reads=0
        def mutate(endpoint,value):
            nonlocal reads
            if '/actions/workflows/99/runs?head_sha='+api.hops[-1]['head'] in endpoint:
                reads+=1
            if reads>2 and '/check-suites/' in endpoint:
                value['app']['id']=42
            return value
        api.mutate=mutate
        with self.assertRaises(P.ProtocolError):
            self.adapter.verify_integrated(api.run_id,self.case.plan,self.case.policy,{'shared-host':self.case.context},clock=lambda:NOW)
        api=self.retained(1)
        # The later unchanged merge cannot make late original evidence timely.
        self.case.merged_at='2026-10-15T10:02:00Z'
        with self.assertRaisesRegex(P.ProtocolError,'before integration'):
            self.adapter.verify_integrated(api.run_id,self.case.plan,self.case.policy,{'shared-host':self.case.context},clock=lambda:NOW)

    def test_leaf_original_lookup_never_invents_a_parent_no_execution_validation(self):
        self.case.binding['base_ref']='apple-ios'
        self.case.push.update(workflow_id=330551824,path='.github/workflows/project-tests.yml',head_branch='apple-ios')
        api=self.retained(0)
        with patch.object(self.adapter,'_origin_pr_inventory',side_effect=AssertionError('no parent-only hop on a leaf')):
            value=self.adapter.integrated_origin(500,15368,api.policy,now=NOW)
        self.assertEqual(value.binding['merge_sha'],self.case.integrated)
        self.assertEqual(value.references['integration']['workflow_path'],'.github/workflows/project-tests.yml')
        self.assertNotIn('retained_no_execution_hops',value.references)
        self.assertNotIn('environment',value.references)

    def test_newer_original_failure_or_retry_cannot_be_walked_past_through_empty_hops(self):
        api=self.retained(2)
        original=self.adapter.capture_integrated(api.run_id,self.case.plan,self.case.policy,now=NOW).observations[0].run
        for status,conclusion,attempt in (('queued',None,1),('completed','failure',1),
                ('completed','cancelled',1),('completed','success',2)):
            later=replace(original,run_id=101,attempt=attempt,latest_attempt=attempt,status=status,conclusion=conclusion,
                attempt_started_at='2026-10-15T10:01:00Z',publisher=None,owners={},final_publisher=None)
            if attempt==1:
                later=replace(later,publisher=replace(original.publisher,job_id=111,
                    started_at='2026-10-15T10:01:00Z',completed_at='2026-10-15T10:01:30Z'))
            self.case.add_run(later,descriptor=attempt==1)
            try:
                with self.subTest(status=status,attempt=attempt),self.assertRaises(P.ProtocolError):
                    self.adapter.verify_integrated(api.run_id,self.case.plan,self.case.policy,{'shared-host':self.case.context},clock=lambda:NOW)
            finally:
                del self.case.runs[101];del self.case.jobs[101];del self.case.artifacts[101]





class EffectiveBaseSnapshotTests(unittest.TestCase):
    """Real adapter/ancestry checks distinguish mutable snapshots from authority."""
    def setUp(self):
        self.case = AdapterTests(methodName='runTest')
        self.case.setUp()
        self.case.base_ancestors = {'1' * 40, '2' * 40}

    def test_current_snapshot_refresh_preserves_binding_native_proof_and_raw_observations(self):
        seen, responses = [], []
        def changed(endpoint, value):
            if endpoint.endswith('/pulls/17'):
                value['base']['sha'] = ('1' if len(seen) % 2 == 0 else '2') * 40
                seen.append(value['base']['sha'])
                responses.append((value, deepcopy(value)))
            return value
        self.case.api.mutate = changed
        before = deepcopy(self.case.context)
        snapshot = self.case.capture()
        self.assertEqual(snapshot.binding, self.case.binding)
        self.assertEqual(snapshot.references['base'], self.case.binding['base_sha'])
        self.assertGreaterEqual(len(set(seen)), 2)
        self.assertEqual(self.case.verify()['run_id'], 100)
        self.assertEqual(self.case.context, before)
        self.assertTrue(all(raw == original for raw, original in responses))
        self.assertTrue(all('/compare/' + value + '...' + self.case.binding['base_sha'] + '?per_page=1'
                            in ''.join(self.case.api.calls) for value in self.case.base_ancestors))

    def test_effective_parent_never_replaces_protected_live_target_or_exact_head(self):
        for mode in ('protection', 'branch', 'base-ref', 'head-ref', 'head-payload', 'parents'):
            def changed(endpoint, value):
                if endpoint.endswith('/pulls/17'):
                    value['base']['sha'] = '1' * 40
                    if mode == 'head-payload': value['head']['sha'] = 'f' * 40
                elif endpoint.endswith('/branches/main'):
                    if mode == 'protection': value['protected'] = False
                    elif mode == 'branch': value['commit']['sha'] = 'f' * 40
                elif mode == 'base-ref' and endpoint.endswith('/git/ref/heads/main'):
                    value['object']['sha'] = 'f' * 40
                elif mode == 'head-ref' and '/git/ref/heads/fix/' in endpoint:
                    value['object']['sha'] = 'f' * 40
                elif mode == 'parents' and endpoint.endswith('/commits/refs/pull/17/merge'):
                    value['parents'].reverse()
                return value
            self.case.api.mutate = changed
            with self.subTest(mode=mode), self.assertRaises(P.ProtocolError):
                self.case.adapter.current(17)

    def test_unknown_divergent_descendant_or_malformed_snapshot_is_not_an_authority(self):
        for snapshot, relation in (('f' * 40, 'diverged'), ('e' * 40, 'behind'),
                                   ('0' * 40, None), (None, None), ('../main', None)):
            def changed(endpoint, value):
                if endpoint.endswith('/pulls/17'): value['base']['sha'] = snapshot
                elif '/compare/' in endpoint and relation == 'behind':
                    value.update(status='behind', ahead_by=0, behind_by=1, total_commits=0, commits=[])
                return value
            self.case.api.mutate = changed
            with self.subTest(snapshot=snapshot), self.assertRaises(P.ProtocolError):
                self.case.adapter.current(17)

    def test_snapshot_ancestry_cannot_hide_authoritative_change_at_final_read(self):
        reads = 0
        def changed(endpoint, value):
            nonlocal reads
            if endpoint.endswith('/pulls/17'):
                reads += 1
                value['base']['sha'] = ('1' if reads == 1 else '2') * 40
                if reads > 1: value['head']['sha'] = 'f' * 40
            return value
        self.case.api.mutate = changed
        with self.assertRaises(P.ProtocolError): self.case.capture()

    def integrated(self):
        value = IntegratedSourceTests(methodName='runTest')
        value.setUp()
        value.case.base_ancestors = set(self.case.base_ancestors)
        return value

    def test_normal_integration_uses_raw_first_parent_and_preserves_original_receipt(self):
        value = self.integrated()
        responses = []
        def changed(endpoint, result):
            if '/commits/' in endpoint and '/pulls?' in endpoint:
                result[0]['base']['sha'] = '1' * 40
            elif endpoint.endswith('/pulls/17'):
                result['base']['sha'] = '2' * 40
            if '/pulls?' in endpoint or endpoint.endswith('/pulls/17'):
                responses.append((result, deepcopy(result)))
            return result
        value.api.mutate = changed
        before = deepcopy(value.case.aggregate)
        snapshot = value.capture()
        self.assertEqual(snapshot.binding, value.case.binding)
        self.assertEqual(snapshot.references['integration']['parents'], value.case.binding['merge_parents'])
        self.assertNotIn('sha', snapshot.references['associated_prs'][0]['base'])
        self.assertEqual(value.verify()['source_chain']['producer_commit'], value.case.binding['merge_sha'])
        self.assertEqual(value.case.aggregate, before)
        self.assertTrue(all(raw == original for raw, original in responses))
        self.assertFalse(any('/git/ref/heads/' + value.case.binding['head_ref'] in endpoint
                             or 'commits/refs/pull/' in endpoint for endpoint in value.api.calls))

    def test_integrated_snapshot_refresh_is_separate_from_authority_bookends(self):
        value = self.integrated()
        reads = 0
        def changed(endpoint, result):
            nonlocal reads
            if endpoint.endswith('/pulls/17'):
                reads += 1
                result['base']['sha'] = ('1' if reads % 2 else '2') * 40
            return result
        value.api.mutate = changed
        self.assertEqual(value.verify()['run_id'], 100)
        self.assertGreater(reads, 1)

    def test_integrated_unknown_snapshot_head_and_nonintroducer_changes_still_deny(self):
        for mode in ('unknown-base', 'head', 'nonintroducer'):
            value = self.integrated()
            if mode == 'nonintroducer': value.add_association()
            def changed(endpoint, result):
                if endpoint.endswith('/pulls/17'):
                    if mode == 'unknown-base': result['base']['sha'] = 'f' * 40
                    elif mode == 'head': result['head']['sha'] = 'f' * 40
                elif mode == 'nonintroducer' and endpoint.endswith('/pulls/18'):
                    result['base']['sha'] = '1' * 40
                return result
            value.api.mutate = changed
            with self.subTest(mode=mode), self.assertRaises(P.ProtocolError): value.capture()

    def test_event_snapshot_requires_real_ancestry_but_head_and_raw_event_stay_exact(self):
        from types import SimpleNamespace
        import producer_workflow as workflow
        binding = self.case.binding
        repository = {'id': 1319052603, 'full_name': A.REPOSITORY}
        event = {'repository': repository, 'number': 17,
                 'pull_request': {'number': 17, **{side: {'repo': deepcopy(repository),
                     'ref': binding[side + '_ref'], 'sha': binding[side + '_sha']}
                     for side in ('base', 'head')}}}
        event['pull_request']['base']['sha'] = '1' * 40
        original = deepcopy(event)
        api = SimpleNamespace(get=self.case.adapter._object)
        workflow._event_binding(event, binding, api=api)
        self.assertEqual(event, original)
        with self.assertRaises(workflow.host.Unavailable): workflow._event_binding(event, binding)
        for side, sha in (('base', 'f' * 40), ('head', 'f' * 40)):
            changed = deepcopy(event)
            changed['pull_request'][side]['sha'] = sha
            with self.subTest(side=side), self.assertRaises(workflow.host.Unavailable):
                workflow._event_binding(changed, binding, api=api)


class ReadOnlyBoundaryTests(unittest.TestCase):
    def blob(self, content=b'{"holds":{}}\n'):
        identity=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
        value={'sha':identity,'size':len(content),'encoding':'base64',
            'content':base64.b64encode(content).decode()+'\n',
            'url':'https://api.github.com/'+A.PREFIX+'/git/blobs/'+identity,'node_id':'fixture-node'}
        return identity,value

    def read_blob(self, identity, value, **options):
        raw=value if isinstance(value,bytes) else json.dumps(value).encode()
        with patch.object(A.GitHubReadOnly,'_request',return_value=raw) as request:
            result=A.GitHubReadOnly().immutable_blob(identity,**options)
        request.assert_called_once_with(A.PREFIX+'/git/blobs/'+identity,100_000)
        return result

    def test_immutable_blob_authenticates_exact_bytes_and_fixed_cli_endpoint(self):
        content=b'{"holds":{}}\n'
        identity,value=self.blob(content)
        self.assertEqual(self.read_blob(identity,value,maximum=len(content)),content)
        real,commands=subprocess.Popen,[]
        raw=json.dumps(value).encode()
        def child(command,**kwargs):
            commands.append(command)
            return real([sys.executable,'-c','import sys;sys.stdout.buffer.write('+repr(raw)+')'],**kwargs)
        with patch.object(A.shutil,'which',return_value='/usr/bin/gh'), \
             patch.object(A.subprocess,'Popen',side_effect=child):
            self.assertEqual(A.GitHubReadOnly().immutable_blob(identity),content)
        self.assertEqual(len(commands),1)
        self.assertEqual(commands[0][-1],A.PREFIX+'/git/blobs/'+identity)
        self.assertIn('GET',commands[0]);self.assertIn('github.com',commands[0])
        self.assertIn('X-GitHub-Api-Version: 2026-03-10',commands[0])

    def test_immutable_blob_has_no_path_ref_version_or_larger_limit_override(self):
        identity,_=self.blob()
        for invalid in (None,'0'*40,'A'*40,'a'*39,'a'*40+'?ref=main','../other',
                A.PREFIX+'/git/blobs/'+'a'*40,'refs/heads/main'):
            with self.subTest(identity=invalid),patch.object(A.GitHubReadOnly,'_request') as request, \
                 self.assertRaises(A.ApiError):A.GitHubReadOnly().immutable_blob(invalid)
            request.assert_not_called()
        for maximum in (True,False,None,'64000',0,-1,64_001,20_000_000,1.0):
            with self.subTest(maximum=maximum),patch.object(A.GitHubReadOnly,'_request') as request, \
                 self.assertRaises(A.ApiError):A.GitHubReadOnly().immutable_blob(identity,maximum)
            request.assert_not_called()
        for options in ({'path':'policy.json'},{'ref':'main'},{'endpoint':'other'},{'api_version':'2022-11-28'}):
            with self.subTest(options=options),patch.object(A.GitHubReadOnly,'_request') as request, \
                 self.assertRaises(TypeError):A.GitHubReadOnly().immutable_blob(identity,**options)
            request.assert_not_called()

    def test_immutable_blob_rejects_rebound_content_identity_metadata_or_size(self):
        identity,original=self.blob()
        variants=[{'sha':'a'*40},{'url':'https://api.github.com/repos/overte-org/overte/git/blobs/'+identity},
            {'url':'https://api.github.com/'+A.PREFIX+'/git/blobs/'+'a'*40},
            {'encoding':'utf-8'},{'size':True},{'size':-1},{'size':original['size']-1},
            {'size':64_001},{'content':[]},{'node_id':{}},{'unexpected':'field'},
            {'content':base64.b64encode(b'altered').decode(),'size':len(b'altered')}]
        for change in variants:
            with self.subTest(change=next(iter(change))),self.assertRaises(A.ApiError):
                self.read_blob(identity,{**original,**change})
        for value in (None,[],{},'unknown'):
            with self.subTest(shape=value),self.assertRaises(A.ApiError):self.read_blob(identity,value)

    def test_immutable_blob_accepts_only_strict_canonical_base64_with_api_lf_wrapping(self):
        identity,original=self.blob(b'a')
        self.assertEqual(self.read_blob(identity,{**original,'content':'YQ==\n'}),b'a')
        for content in ('YR==','YQ=','YQ===','YQ==!','YQ== ','YQ==\r\n','\u20ac', 'YQ==YQ=='):
            with self.subTest(content=content),self.assertRaises(A.ApiError):
                self.read_blob(identity,{**original,'content':content})

    def test_immutable_blob_bounds_raw_json_and_decoded_bytes_and_rejects_duplicate_fields(self):
        identity,value=self.blob()
        for raw in (b' '*100_001,b'{"size":1,'+json.dumps(value).encode()[1:],
                b'{"content":"YQ==",'+json.dumps(value).encode()[1:],b'{"size":NaN}'):
            with self.subTest(length=len(raw)),self.assertRaises(A.ApiError):self.read_blob(identity,raw)
        for size in (64_000,64_001):
            content=b'a'*64_001
            with self.subTest(size=size),self.assertRaises(A.ApiError):
                self.read_blob(identity,{**value,'size':size,'content':base64.b64encode(content).decode()})
        with self.assertRaises(A.ApiError):self.read_blob(identity,value,maximum=value['size']-1)

    def test_legacy_pr_version_is_explicit_and_unavailable_for_other_endpoints(self):
        real, commands = subprocess.Popen, []
        def child(command, **kwargs):
            commands.append(command)
            return real([sys.executable, "-c", "print('{}')"], **kwargs)
        with patch.object(A.shutil, "which", return_value="/usr/bin/gh"), patch.object(
                A.subprocess, "Popen", side_effect=child):
            api = A.GitHubReadOnly()
            self.assertEqual(api.integrated_pr(17), {})
            self.assertEqual(api.json(A.PREFIX + "/pulls/17"), {})
        self.assertIn("X-GitHub-Api-Version: 2022-11-28", commands[0])
        self.assertIn("X-GitHub-Api-Version: 2026-03-10", commands[1])
        self.assertTrue(all(command[-1] == A.PREFIX + "/pulls/17" and "GET" in command for command in commands))
        for endpoint, version in ((A.PREFIX + "/actions/runs/100", "2022-11-28"),
                                  (A.PREFIX + "/pulls/17?other=1", "2022-11-28"),
                                  (A.PREFIX + "/pulls/17", "unknown")):
            with patch.object(A.subprocess, "Popen") as process, self.assertRaises(A.ApiError):
                api._request(endpoint, 1000, api_version=version)
            process.assert_not_called()
        with patch.object(A.GitHubReadOnly, "_request", return_value=b'{"duplicate":1,"duplicate":2}'), \
                self.assertRaises(A.ApiError):
            A.GitHubReadOnly().integrated_pr(17)

    def test_only_fixed_fork_gets_are_issued_and_error_details_stay_private(self):
        real = subprocess.Popen
        commands = []
        def child(command, **kwargs):
            commands.append(command)
            return real([sys.executable, "-c", "import os;os.write(2,b'private-token signed-url');raise SystemExit(1)"], **kwargs)
        with patch.object(A.shutil, "which", return_value="/usr/bin/gh"), patch.object(A.subprocess, "Popen", side_effect=child):
            with self.assertRaises(A.ApiError) as result: A.GitHubReadOnly().json(A.PREFIX + "/actions/runs/1")
        self.assertNotIn("private-token", str(result.exception)); self.assertNotIn("signed-url", str(result.exception))
        self.assertIn("GET", commands[0]); self.assertIn("github.com", commands[0]); self.assertNotIn("POST", commands[0])
        for endpoint in ("https://signed.example/private", "repos/overte-org/overte/actions/runs", A.PREFIX + "/../other", A.PREFIX + "/x\nsecret"):
            with patch.object(A.subprocess, "Popen") as process, self.assertRaises(A.ApiError):
                A.GitHubReadOnly().json(endpoint)
            process.assert_not_called()

    def test_raw_output_and_json_are_bounded_and_candidate_shadowed_gh_is_rejected(self):
        real = subprocess.Popen
        with patch.object(A.shutil, "which", return_value="/usr/bin/gh"), patch.object(
                A.subprocess, "Popen", side_effect=lambda command, **kwargs: real(
                    [sys.executable, "-c", "import os;os.write(1,b'x'*1000)"], **kwargs)), self.assertRaises(A.ApiError):
            A.GitHubReadOnly()._request(A.PREFIX + "/actions/runs/1", 16)
        with patch.object(A.shutil, "which", return_value="/candidate/gh"), self.assertRaises(A.ApiError):
            A.GitHubReadOnly().json(A.PREFIX + "/actions/runs/1")
        with patch.object(A.GitHubReadOnly, "_request", return_value=b'{"duplicate":1,"duplicate":2}'), self.assertRaises(A.ApiError):
            A.GitHubReadOnly().json(A.PREFIX + "/actions/runs/1")
        with patch.object(A.GitHubReadOnly, "_request", return_value=b'{"invalid":NaN}'), self.assertRaises(A.ApiError):
            A.GitHubReadOnly().json(A.PREFIX + "/actions/runs/1")

    def test_deadline_kills_the_read_only_child_and_closes_its_pipes(self):
        real, children = subprocess.Popen, []
        def child(command, **kwargs):
            process = real([sys.executable, "-c", "import time;time.sleep(5)"], **kwargs)
            children.append(process)
            return process
        with patch.object(A.shutil, "which", return_value="/usr/bin/gh"), patch.object(
                A.subprocess, "Popen", side_effect=child), patch.object(A.time, "monotonic", side_effect=(0, 46)), self.assertRaises(A.ApiError):
            A.GitHubReadOnly().json(A.PREFIX + "/actions/runs/1")
        self.assertIsNotNone(children[0].returncode)
        self.assertTrue(children[0].stdout.closed and children[0].stderr.closed)


class MainConsumerTests(unittest.TestCase):
    """Native push + actual protocol/API validator; no workload/E probes."""
    def setUp(self):
        import postmerge
        from types import SimpleNamespace
        self.module = postmerge
        self.real_host_policy = postmerge.producer._host_policy
        self.real_package = self.real_host_policy().package_policy()
        self.real_full_tree = postmerge.inputs.full_tree
        self.real_selection_profile = getattr(postmerge.producer, 'selection_profile', None)
        fixture = IntegratedSourceTests(); fixture.setUp()
        self.case, self.api, self.adapter = fixture.case, fixture.api, fixture.adapter
        self.case.originals[self.case.binding['base_sha']] = ('6'*40, ['7'*40])
        old = FIXTURES.ProducerProtocolTests(); old.setUp()
        self.registry = old.registry
        self.tree = deepcopy(old.tree)
        generations = json.loads((postmerge.ROOT / '.github/package-workflow-generations.json').read_text())['generations']
        self.generation_name = getattr(self,'generation_name','protected-producer-seven-target-ci-v1')
        generation = next(item for item in generations if item['name'] == self.generation_name)
        self.generations = {item['name']:deepcopy(item['workflows']) for item in generations}
        if self.generation_name in {'protected-producer-metadata-ci-v1','protected-producer-seven-target-ci-v1'}:
            # Reconstruct authentic historical20/21 sources independently of
            # today's dormant22 templates. Future installed22 has separate
            # complete materialized-tuple fixtures; old rows never float.
            sources={'.github/workflows/project-tests.yml':postmerge.producer.TEMPLATE,
                '.github/workflows/repository-checks.yml':'tools/repository-checks/workflows/producers/repository-checks.yml',
                '.github/workflows/parent-qualification.yml':postmerge.TEMPLATE,
                '.github/workflows/sync-validation.yml':'.github/workflows/sync-validation.yml',
                '.github/workflows/browser-client.yml':'.github/workflows/browser-client.yml',
                A.METADATA_WORKFLOW:'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml'}
            if self.generation_name == 'protected-producer-metadata-ci-v1':
                sources.update({'.github/workflows/project-tests.yml':
                    'tools/repository-checks/workflows/producers/legacy/protected-project-tests-metadata-v1.yml',
                    '.github/workflows/repository-checks.yml':
                    'tools/repository-checks/workflows/producers/legacy/repository-checks-metadata-v1.yml',
                    '.github/workflows/parent-qualification.yml':
                    'tools/repository-checks/workflows/producers/legacy/parent-qualification-metadata-v1.yml'})
            workflows={}
            for target,relative in sources.items():
                path=postmerge.ROOT/relative
                self.assertTrue(path.is_file() and not path.is_symlink())
                self.assertIn(path.stat().st_mode & 0o777,(0o444,0o644))
                raw=historical_metadata_workflow(relative,self.generation_name,postmerge.ROOT)
                workflows[target]={'mode':'100644','type':'blob',
                    'sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
            self.assertEqual(workflows,generation['workflows'])
        else:
            workflows=deepcopy(generation['workflows'])
        self.tree.update(workflows)
        self.tree[postmerge.TEMPLATE] = deepcopy(self.tree['.github/workflows/parent-qualification.yml'])
        self.tree['.github/test-suites.json'] = {'mode':'100644','type':'blob','sha':'1'*40}
        self.tree['tests/platform-profile.json'] = postmerge.source_admission.ordinary(postmerge.source_admission.SHARED_PROFILE)
        self.previous = deepcopy(self.tree)
        self.case.generation = {path:self.tree[path] for path in A.WORKFLOWS}
        self.case.pp = replace(self.case.pp, workflow_blob=self.tree['.github/workflows/project-tests.yml']['sha'], required_execution_schema=3)
        self.case.policy = replace(self.case.policy, producer=self.case.pp, generations={'reviewed':self.case.generation})
        self.case.plan['owners']['shared-host']['include_platform'] = True
        self.git = postmerge.producer.expected_git_context(self.adapter, self.case.binding)
        receipt = deepcopy(self.case.aggregate['results']['shared-host']['receipt'])
        receipt.update(schema=3, git_context=self.git, include_platform=True,
                       environment=FIXTURES.isolated_codec_environment())
        receipt['results'] = {name:{'status':'passed','fingerprint':P.inputs.suite_fingerprint(
            self.registry,name,self.tree,receipt['environment'])} for name in self.registry['suites']}
        self.receipt = FIXTURES.signed(receipt,'receipt_digest')
        self.case.aggregate['results']['shared-host']['receipt'] = self.receipt
        run = replace(old.run, workflow_path=self.case.pp.workflow_path, workflow_commit=self.case.binding['merge_sha'],
            workflow_ref=self.case.pp.workflow_ref, event='pull_request', workflow_blob=self.case.pp.workflow_blob,
            final_publisher=replace(old.run.final_publisher, receipt_sha256=hashlib.sha256(P.canonical(self.receipt)).hexdigest()))
        self.case.add_run(run); self.case.runs[100]['pull_requests'] = []
        # The real adapter still reads source trees/workflows/job/check/artifact facts.
        self.api.immutable_tree = lambda oid: self.api.mutate(A.PREFIX+'/git/trees/'+oid+'?recursive=1', {
            'sha':oid,'truncated':False,'tree':[{'path':path,**entry} for path,entry in
                (self.previous if oid=='6'*40 else self.tree).items()]})
        package = SimpleNamespace(validate_tree_wiring=self.real_package.validate_tree_wiring,
            _trusted_bytes=lambda name,**_:b'{"schema":1,"platform":"shared","suites":[]}',
            tools=lambda:SimpleNamespace(PROJECTS=('server-console','tools/jsdoc')),
            S3='script-archive/marketplace/S3Server', BROWSER='browser-client')
        self.patches = [patch.object(postmerge,'SOURCE_READY',True),
            patch.object(postmerge.producer,'PRODUCTION_READY',True),
            patch.object(postmerge.sandbox,'ACTIVATION_READY',True),
            patch.object(postmerge.attested,'ISOLATED_ADMISSION_READY',True),
            patch.object(postmerge.execution,'checkout_identity',return_value=(self.case.integrated,self.case.binding['merge_tree'])),
            patch.object(postmerge.inputs,'full_tree',return_value=self.tree),
            patch.object(postmerge.inputs,'load_registry',return_value=self.registry),
            patch.object(postmerge.producer,'_host_policy',return_value=SimpleNamespace(package_policy=lambda:package)),
            patch.object(postmerge.producer,'selection_profile',create=True,return_value={
                'profile':'ubuntu24-host-qt5-qt6-v1','suites':list(self.registry['suites']),
                'selection':{'suites':list(self.registry['suites']),'full_host':True,
                    'include_platform':True,'reason':'fixture-full-owner'}}),
            patch.object(postmerge,'original_controller',return_value=self.case.pp.controller_digest),
            # The actual64-source enrollment is tested separately; this tiny
            # native receipt fixture supplies only its admitted controller ID.
            patch.object(postmerge,'integrated_controller',return_value=self.case.pp.controller_digest),
            patch.object(postmerge,'_policy',return_value=(self.case.plan,self.case.policy)),
            patch.object(postmerge.attested,'validate_environment',return_value={'environment_digest':'sha256:'+'1'*64,'policy':{'epoch':'fixture'}}),
            patch.object(postmerge.execution,'capture_execution_environment',side_effect=AssertionError('unused consumer E')),
            patch.object(postmerge.execution,'execute',side_effect=AssertionError('no consumer workload'))]
        for item in self.patches:item.start();self.addCleanup(item.stop)
        self.event={'ref':'refs/heads/main','before':self.case.binding['base_sha'],'after':self.case.integrated,
            'deleted':False,'forced':False,'repository':{'full_name':A.REPOSITORY,'id':1319052603}}
        self.environment={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':A.REPOSITORY,'GITHUB_REPOSITORY_ID':'1319052603',
            'GITHUB_EVENT_NAME':'push','GITHUB_REF':'refs/heads/main','GITHUB_RUN_ATTEMPT':'1','GITHUB_JOB':'qualify-parent',
            'RUNNER_ENVIRONMENT':'github-hosted','ImageOS':'ubuntu24','GITHUB_SHA':self.case.integrated,
            'GITHUB_WORKFLOW_SHA':self.case.integrated,'GITHUB_RUN_ID':'500',
            'GITHUB_WORKFLOW_REF':A.REPOSITORY+'/.github/workflows/parent-qualification.yml@refs/heads/main'}

    def lookup(self):
        return self.module.lookup(self.event,self.environment,self.adapter,clock=lambda:NOW)

    def test_original_full_e_is_authenticated_without_rebinding_or_unused_consumer_setup(self):
        value=self.lookup()
        self.assertTrue(value['reused'],value)
        proof=value['proof']
        self.assertEqual(proof['current_commit'],self.case.integrated)
        self.assertEqual(proof['original_commit'],self.case.binding['merge_sha'])
        self.assertNotEqual(proof['current_commit'],proof['original_commit'])
        self.assertEqual(proof['original_proof']['expires_at'],self.case.aggregate['expires_at'])
        self.assertEqual(proof['original_proof']['receipt_sha256'],hashlib.sha256(P.canonical(self.receipt)).hexdigest())
        self.assertEqual(proof['reused_suites'],list(self.registry['suites']))
        self.assertEqual(proof['executed_suites'],[])
        self.assertFalse(proof['reusable'])
        self.assertFalse(proof['package_work'])
        self.assertEqual(self.receipt['candidate_commit'],self.case.binding['merge_sha'])
        self.assertEqual(self.receipt['environment']['profile'],self.module.inputs.ISOLATED_FULL_PROFILE)
        self.assertIn(self.module.inputs.ISOLATED_CACERTS,self.receipt['environment']['prepared']['roots'])
        self.assertEqual(self.module.attested.validate_environment.call_args.args[0],self.receipt['environment'])

    def test_changed_prepared_identity_cannot_keep_original_fingerprints_or_native_receipt_hash(self):
        run = self.adapter.capture_integrated(500,self.case.plan,self.case.policy,now=NOW).observations[0].run
        for path in (self.module.inputs.ISOLATED_VENV,self.module.inputs.ISOLATED_CACERTS):
            original = deepcopy((self.case.aggregate,self.case.artifacts,self.case.archives))
            changed = deepcopy(self.receipt)
            changed['environment']['prepared']['roots'][path] = 'sha256:' + 'b'*64
            for renew_fingerprints in (False,True):
                if renew_fingerprints:
                    changed['results'] = {name:{'status':'passed','fingerprint':P.inputs.suite_fingerprint(
                        self.registry,name,self.tree,changed['environment'])} for name in self.registry['suites']}
                self.case.aggregate['results']['shared-host']['receipt'] = FIXTURES.signed(changed,'receipt_digest')
                self.case.aggregate = FIXTURES.signed(self.case.aggregate,'aggregate_digest')
                self.case.artifacts[100] = self.case.artifacts[100][:1]
                self.case.artifact(run,'aggregate',self.case.aggregate)
                with self.subTest(path=path,renew_fingerprints=renew_fingerprints):
                    self.assertFalse(self.lookup()['reused'])
            self.case.aggregate,self.case.artifacts,self.case.archives = original

    def test_current_canonical_producer_generation_reaches_original_native_commitment(self):
        self.assertEqual(self.real_package.validate_tree_wiring(self.tree),'protected-producer-seven-target-ci-v1')
        self.assertEqual(self.tree['.github/workflows/project-tests.yml']['sha'],
                         self.generations['protected-producer-seven-target-ci-v1']['.github/workflows/project-tests.yml']['sha'])
        value=self.lookup()
        self.assertTrue(value['reused'],value)
        proof=value['proof']
        self.assertEqual(proof['original_proof']['source_chain']['producer_blob'],
                         self.tree['.github/workflows/project-tests.yml']['sha'])
        self.assertEqual(proof['original_proof']['receipt_sha256'],hashlib.sha256(P.canonical(self.receipt)).hexdigest())
        self.assertNotEqual(proof['current_commit'],proof['original_commit'])
        self.assertEqual(proof['executed_suites'],[])

    def test_unknown_and_mixed_complete_workflow_tuples_decline_before_original_proof(self):
        path='.github/workflows/parent-qualification.yml'
        original=deepcopy(self.tree[path])
        for kind in ('unknown','mixed'):
            self.tree[path]={'mode':'100644','type':'blob','sha':'f'*40} if kind=='unknown' else deepcopy(
                self.generations['protected-shared-producer-v1'][path])
            # Even known individual blobs cannot form an unreviewed tuple.
            with self.subTest(kind=kind),patch.object(self.adapter,'capture_integrated',
                    side_effect=AssertionError('unapproved tuple reached original proof')):
                with self.assertRaises(ValueError):self.real_package.validate_tree_wiring(self.tree)
                self.assertEqual(self.lookup(),{'reused':False,'reason':'original-proof-unavailable'})
        self.tree[path]=original

    def test_missing_failed_newer_pending_or_rerun_original_selects_one_actual_fallback(self):
        for kind in ('missing','failed','pending','newer','attempt','publisher','artifact','foreign'):
            with self.subTest(kind=kind):
                before=deepcopy((self.case.runs,self.case.jobs,self.case.artifacts))
                if kind=='missing':self.case.runs.clear()
                elif kind=='failed':self.case.runs[100].update(status='completed',conclusion='failure')
                elif kind=='pending':self.case.runs[100].update(status='in_progress',conclusion=None)
                elif kind=='attempt':self.case.runs[100]['run_attempt']=2
                elif kind=='publisher':self.case.jobs[100][-1]['name']=self.case.policy.final_publisher_prefix+'0'*64
                elif kind=='artifact':self.case.artifacts[100].pop()
                elif kind=='foreign':self.case.runs[100]['head_repository']['id']=1
                else:
                    self.case.runs[101]={**deepcopy(self.case.runs[100]),'id':101,'status':'queued','conclusion':None}
                self.assertEqual(self.lookup(),{'reused':False,'reason':'original-proof-unavailable'})
                self.case.runs,self.case.jobs,self.case.artifacts=before

    def test_stale_main_api_changed_context_and_wrong_native_invocations_never_waive(self):
        for key,value in (('GITHUB_EVENT_NAME','workflow_dispatch'),('GITHUB_REF','refs/heads/apple-main'),
                ('GITHUB_JOB','fake-pass'),('GITHUB_RUN_ATTEMPT','2'),('GITHUB_SHA','1'*40),
                ('GITHUB_WORKFLOW_SHA','1'*40),('GITHUB_REPOSITORY','overte-org/overte')):
            original=self.environment[key];self.environment[key]=value
            with self.subTest(key=key):self.assertFalse(self.lookup()['reused'])
            self.environment[key]=original
        self.api.mutate=lambda endpoint,value:{**value,'protected':False} if '/branches/' in endpoint else value
        self.assertFalse(self.lookup()['reused'])

    def test_full_source_truncation_aliases_new_inputs_or_changed_declarations_deny(self):
        original=deepcopy(self.tree)
        for mutation in ('truncated','missing','mode','new-import','registry','candidate-scope','runtime'):
            with self.subTest(mutation=mutation):
                self.api.mutate=lambda endpoint,value:value
                if mutation=='truncated':
                    self.api.mutate=lambda endpoint,value:{**value,'truncated':True} if '?recursive=1' in endpoint else value
                elif mutation=='missing':del self.tree['tests/first.py']
                elif mutation=='mode':self.tree['tests/first.py']['mode']='120000'
                elif mutation=='new-import':self.tree['tools/controller.py']['sha']='9'*40
                elif mutation=='registry':self.previous['.github/test-suites.json']['sha']='9'*40
                elif mutation=='candidate-scope':self.registry['suites']['first']['scope']='candidate'
                else:
                    with patch.object(self.module.attested,'validate_environment',side_effect=self.module.attested.AttestedReuseUnavailable('old epoch')):
                        self.assertFalse(self.lookup()['reused'])
                    continue
                self.assertFalse(self.lookup()['reused'])
                self.tree.clear();self.tree.update(deepcopy(original));self.previous=deepcopy(original)
                self.registry['suites']['first']['scope']='content'

    def test_each_source_guard_off_has_zero_api_and_no_policy_json_enable(self):
        for module,name in ((self.module,'SOURCE_READY'),(self.module.producer,'PRODUCTION_READY'),
                (self.module.sandbox,'ACTIVATION_READY'),
                (self.module.attested,'ISOLATED_ADMISSION_READY')):
            self.api.calls.clear()
            with patch.object(module,name,False):self.assertFalse(self.lookup()['reused'])
            self.assertEqual(self.api.calls,[])

    def test_shared_proof_retains_independent_package_work_and_fresh_ref_bookends(self):
        # A shared receipt supplies no package proof. Its original M and S maps
        # still match, while the protected base has the old package manifest.
        path='script-archive/marketplace/S3Server/package-lock.json'
        self.previous[path]={'mode':'100644','type':'blob','sha':'5'*40}
        self.tree[path]={'mode':'100644','type':'blob','sha':'6'*40}
        value=self.lookup()
        self.assertTrue(value['reused'],value)
        self.assertTrue(value['proof']['package_work'])
        count=0
        def changed(endpoint,value):
            nonlocal count
            if '/branches/main' in endpoint:
                count+=1
                if count>2:value['commit']['sha']='7'*40
            return value
        self.api.mutate=changed
        self.assertFalse(self.lookup()['reused'])

    def test_immutable_tree_extended_bound_is_fixed_to_a_validated_tree_endpoint(self):
        with patch.object(A.GitHubReadOnly,'_request',return_value=b'{"truncated":false}') as read:
            self.assertEqual(A.GitHubReadOnly().immutable_tree('a'*40),{'truncated':False})
        read.assert_called_once_with(A.PREFIX+'/git/trees/'+'a'*40+'?recursive=1',20_000_000)
        with self.assertRaises(A.ApiError):A.GitHubReadOnly().immutable_tree('../other')


class MainCI37ConsumerTests(unittest.TestCase):
    """Fake native API chain and actual source/E validators; no hosted proof."""
    def setUp(self):
        fixture = MainConsumerTests(); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture, self.module = fixture, fixture.module
        self.case, self.api = fixture.case, fixture.api
        C, R = self.module, self.module.runtime_ci
        self.registry, self.tree = fixture.registry, fixture.tree
        actual_registry = json.loads((C.ROOT / '.github/test-suites.json').read_bytes(),
                                     object_pairs_hook=C.inputs._unique_object)
        self.registry.clear(); self.registry.update(actual_registry)
        workflow_entries = {path:deepcopy(self.tree[path]) for path in (*A.WORKFLOWS,
            '.github/workflows/browser-client.yml', A.METADATA_WORKFLOW, C.TEMPLATE)}
        # This is the complete inventory of a small fake repository, carrying
        # every real definition's required leaf. No sparse inventory is admitted
        # as a production tree and no real checkout is executed by these tests.
        actual_tree=fixture.real_full_tree(C.ROOT, 'HEAD')
        required={C.ci_profile.POLICY,'.github/test-suites.json','README.md',
                  *self.registry['control_inputs']}
        for suite in self.registry['suites'].values():required.update(suite['closure']['required'])
        self.tree.clear(); self.tree.update({path:entry for path,entry in actual_tree.items() if path in required})
        # New required fake-test leaves may precede this source packet's first
        # commit. They are data in this complete synthetic API tree; repository
        # registry tests separately require the real files to exist.
        for path in required:
            if '*' not in path:
                self.tree.setdefault(path,{'mode':'100644','type':'blob','sha':'a'*40})
        self.tree.update(workflow_entries)
        # This legacy schema3/E2 fixture models the original main-only CI37
        # contract. Do not inherit the executing child's Android declaration.
        self.tree['tests/platform-profile.json']=deepcopy(C.inputs._AFFECTED_SHARED_PROFILE)
        # A genuine non-documentation CI data delta, independently admitted by
        # the strict immutable-blob guard, supplies the original quick owner.
        original_data=(C.ROOT/C.ci_profile.DATA_PATH).read_bytes()
        current_data=json.loads(original_data)
        current_data['holds']={'fix/main/retain-ci-fixture':'Keep the integration fixture branch'}
        current_data=json.dumps(current_data,sort_keys=True).encode()
        self.data_blobs={hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest():raw
                         for raw in (original_data,current_data)}
        old_data,new_data=self.data_blobs
        self.tree[C.ci_profile.DATA_PATH]={'mode':'100644','type':'blob','sha':new_data}
        fixture.previous = deepcopy(self.tree)
        fixture.previous[C.ci_profile.DATA_PATH]['sha']=old_data
        def blob_request(endpoint,maximum,**options):
            self.api.calls.append(endpoint)
            oid=endpoint.removeprefix(A.PREFIX+'/git/blobs/')
            raw=self.data_blobs[oid]
            return json.dumps({'sha':oid,'size':len(raw),'encoding':'base64',
                'content':A.base64.b64encode(raw).decode()}).encode()
        client=A.GitHubReadOnly();client._request=blob_request
        self.api.immutable_blob=client.immutable_blob
        self.policy = fixture.real_host_policy()
        self.ci_policy = {'schema':1, 'enabled':True, 'profile':C.ci_profile.PROFILE,
            'epoch':'ci37-main-consumer-fake-v1', 'suites':list(C.ci_profile.SUITES),
            'not_before':'2026-10-15T00:00:00Z', 'max_age_seconds':259200,
            'definition_digest':C.ci_profile.definition_digest(self.registry),
            'generation_digest':C.ci_profile.generation(self.tree, self.registry)}
        for owner,name,value in ((C.producer,'_host_policy',self.policy),
                (C.ci_profile,'load_policy',self.ci_policy)):
            item=patch.object(owner,name,return_value=value); item.start(); self.addCleanup(item.stop)
        for owner,name,value in ((self.policy,'REVIEWED_PROGRAMS',self.policy.program_digest(self.tree,C.ROOT)),
                (C.ci_profile,'SOURCE_READY',True)):
            item=patch.object(owner,name,value); item.start(); self.addCleanup(item.stop)
        item=patch.object(C.producer,'selection_profile',side_effect=fixture.real_selection_profile)
        self.selection = item.start(); self.addCleanup(item.stop)
        # Reuse the complete fake E shape, then restore its focused-test mocks:
        # this consumer test exercises the actual strict admission and planner.
        spec=importlib.util.spec_from_file_location('ci37_consumer_environment_fixture',
            Path(__file__).with_name('runtime-ci-test.py'))
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        environment_case=module.OriginalCIEnvironmentTests(); environment_case.setUp()
        self.original_environment=deepcopy(environment_case.environment)
        environment_case.doCleanups()
        selected=C.producer.selection_profile(self.policy,self.registry,self.tree,
            fixture.previous,fixture.previous,root=C.ROOT,read_blob=self.api.immutable_blob)
        self.original_environment['selection']=C.ci_profile.validate_selection(selected['selection'],
            self.tree,fixture.previous,self.registry,policy=self.ci_policy,root=C.ROOT,read_blob=self.api.immutable_blob)
        _, manifests=R.runtime._requirement_inventory(C.ROOT)
        self.original_environment['trusted_execution']={**R.runtime._controller_file_hashes(manifests,C.ROOT),
            **{path:R.runtime._file_digest(C.ROOT/path) for path in R._FILES}}
        self.case.plan['owners']['shared-host'].update(suites=list(C.ci_profile.SUITES),include_platform=False)
        self.publish()
        for owner,name in ((C.attested,'validate_environment'), (R,'capture_ci_environment'), (R,'_query')):
            item=patch.object(owner,name,side_effect=AssertionError('no full profile or consumer runtime query'))
            item.start(); self.addCleanup(item.stop)
        self.selection.reset_mock()

    def publish(self, *, requested=None, environment=None, include_platform=False, mutate=None):
        """Replace fake original artifact and its matching native commitment."""
        fixture, C=self.fixture,self.module
        receipt=deepcopy(fixture.receipt)
        receipt.update(environment=deepcopy(self.original_environment if environment is None else environment),
            requested_suites=list(C.ci_profile.SUITES) if requested is None else requested,
            include_platform=include_platform)
        receipt['results']={name:{'status':'passed','fingerprint':C.inputs.suite_fingerprint(
            self.registry,name,self.tree,receipt['environment'])} for name in receipt['requested_suites']}
        if mutate is not None: mutate(receipt)
        self.receipt=FIXTURES.signed(receipt,'receipt_digest')
        self.case.aggregate['results']['shared-host']['receipt']=self.receipt
        old=FIXTURES.ProducerProtocolTests(); old.setUp()
        run=replace(old.run,workflow_path=self.case.pp.workflow_path,workflow_commit=self.case.binding['merge_sha'],
            workflow_ref=self.case.pp.workflow_ref,event='pull_request',workflow_blob=self.case.pp.workflow_blob,
            final_publisher=replace(old.run.final_publisher,receipt_sha256=hashlib.sha256(P.canonical(self.receipt)).hexdigest()))
        self.case.add_run(run); self.case.runs[100]['pull_requests']=[]

    def lookup(self):
        return self.fixture.lookup()

    def test_original_exact37_environment_and_native_commitment_reuse_without_consumer_capture(self):
        before=deepcopy(self.original_environment)
        with patch.object(self.module,'full_tree',wraps=self.module.full_tree) as source:
            value=self.lookup()
        self.assertTrue(value['reused'],value)
        self.assertEqual([call.args[1] for call in source.call_args_list],
            [self.case.integrated,self.case.integrated,self.case.binding['base_sha'],self.case.binding['merge_sha']])
        proof=value['proof']
        self.assertEqual(proof['reused_suites'],list(self.module.ci_profile.SUITES))
        self.assertEqual(proof['executed_suites'],[])
        self.assertEqual(proof['original_environment_digest'],self.module.runtime_ci.digest(before))
        self.assertEqual(proof['runtime_admission']['profile'],self.module.ci_profile.PROFILE)
        self.assertEqual(proof['original_proof']['expires_at'],self.case.aggregate['expires_at'])
        self.assertEqual(proof['original_proof']['receipt_sha256'],hashlib.sha256(P.canonical(self.receipt)).hexdigest())
        self.assertEqual(self.receipt['environment'],before)
        self.assertEqual(self.selection.call_count,2)
        for call in self.selection.call_args_list:
            self.assertEqual(call.args[3:5],(self.fixture.previous,self.fixture.previous))
        self.assertFalse(proof['reusable']); self.assertFalse(proof['package_work'])
        for oid in self.data_blobs:
            self.assertIn(A.PREFIX+'/git/blobs/'+oid,self.api.calls)

    def test_cleanup_api_bytes_are_authenticated_on_both_sides_before_original_proof_reuse(self):
        original=self.api.immutable_blob
        for identity in self.data_blobs:
            with self.subTest(side=identity),patch.object(self.api,'immutable_blob',
                    side_effect=lambda oid:b'{"rebound":true}' if oid==identity else original(oid)):
                self.assertEqual(self.lookup(),{'reused':False,'reason':'original-proof-unavailable'})
        with patch.object(self.api,'immutable_blob',side_effect=A.ApiError('bounded immutable read unavailable')):
            self.assertEqual(self.lookup(),{'reused':False,'reason':'original-proof-unavailable'})

    def test_original_receipt_cannot_choose_extra_missing_reordered_or_full_owners(self):
        suites=list(self.module.ci_profile.SUITES)
        for requested,platform in ((suites[:-1],False),(list(reversed(suites)),False),
                ([*suites,'codeql-remediation'],False),(list(self.registry['suites']),True),(suites,True)):
            with self.subTest(count=len(requested),platform=platform):
                self.publish(requested=requested,include_platform=platform)
                self.assertFalse(self.lookup()['reused'])

    def test_original_environment_cannot_relabel_full_profile_or_omit_native_identity(self):
        for change in ({'schema':1},{'profile':'ubuntu24-host-qt5-qt6-v1'}, {'qt':{}}, {'native':{}},
                {'selection':{'suites':list(self.registry['suites'])}}):
            environment={**self.original_environment,**change}
            with self.subTest(change=next(iter(change))):
                self.publish(environment=environment)
                self.assertFalse(self.lookup()['reused'])

    def test_changed_original_reader_import_lookup_or_independent_selection_never_projects_quick(self):
        original=deepcopy(self.fixture.previous)
        for path in ('tools/test-evidence/runtime.py','tests/json.py','libraries/new/CMakeLists.txt',
                'browser-client/package-lock.json','.github/workflows/project-tests.yml'):
            self.fixture.previous.clear(); self.fixture.previous.update(deepcopy(original))
            self.fixture.previous[path]={'mode':'100644','type':'blob','sha':'8'*40}
            with self.subTest(path=path):self.assertFalse(self.lookup()['reused'])
        self.fixture.previous.clear(); self.fixture.previous.update(original)
        actual=self.fixture.real_selection_profile
        def changed(*args,**kwargs):
            value=actual(*args,**kwargs)
            if self.selection.call_count == 2:
                value=deepcopy(value); value['selection']['include_platform']=True
            return value
        self.selection.reset_mock(); self.selection.side_effect=changed
        self.assertFalse(self.lookup()['reused'])

    def test_ci37_guard_disabled_or_unknown_complete_generation_selects_actual_fallback(self):
        for disabled in ('source','policy','generation','definitions'):
            with self.subTest(disabled=disabled):
                policy=deepcopy(self.ci_policy)
                if disabled=='policy':policy['enabled']=False
                elif disabled=='generation':policy['generation_digest']='sha256:'+'0'*64
                elif disabled=='definitions':policy['definition_digest']='sha256:'+'0'*64
                with patch.object(self.module.ci_profile,'SOURCE_READY',disabled!='source'), \
                     patch.object(self.module.ci_profile,'load_policy',return_value=policy):
                    self.assertFalse(self.lookup()['reused'])

    def test_native_receipt_publisher_and_fresh_api_bookends_still_bind_quick_owner(self):
        self.case.jobs[100][-1]['name']=self.case.policy.final_publisher_prefix+'0'*64
        self.assertFalse(self.lookup()['reused'])
        self.publish()
        count=0
        def changed(endpoint,value):
            nonlocal count
            if '/branches/main' in endpoint:
                count+=1
                if count>2:value['commit']['sha']='7'*40
            return value
        self.api.mutate=changed
        self.assertFalse(self.lookup()['reused'])


class MainConsumerSourceTests(unittest.TestCase):
    def test_previous_complete_consumer_generations_remain_reusable(self):
        for generation in ('postmerge-original-e-v1','protected-producer-postmerge-original-e-v1',
                           'protected-producer-ci37-v1','protected-producer-metadata-ci-v1'):
            fixture=MainConsumerTests();fixture.generation_name=generation
            try:
                fixture.setUp()
                with self.subTest(generation=generation):
                    self.assertEqual(fixture.real_package.validate_tree_wiring(fixture.tree),generation)
                    self.assertTrue(fixture.lookup()['reused'])
            finally:
                fixture.doCleanups()

    def test_original_controller_is_reconstructed_from_immutable_base_without_historical_execution(self):
        import postmerge as C
        import tempfile
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def git(*args):return subprocess.check_output(['git','-c','core.hooksPath=/dev/null',*args],cwd=root,stderr=subprocess.PIPE).decode().strip()
            git('init','-q');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
            files={'tools/controller.py':b'raise RuntimeError("must never execute historic code")\n',
                   'tests/run-project-tests.py':b'print("fixture source only")\n'}
            for relative,raw in files.items():
                p=root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            (root/'tests/run-project-tests.py').chmod(0o755)
            git('add','.');git('commit','-qm','Create immutable controller fixture')
            tree=C.inputs.full_tree(root,'HEAD')
            package=SimpleNamespace(_trusted_bytes=lambda name,**_:(root/name).read_bytes())
            policy=SimpleNamespace(package_policy=lambda:package)
            with patch.object(C.producer,'controller_sources',return_value=sorted(files)):
                original=C.original_controller(policy,tree,tree,root)
                with patch.object(C.producer,'ROOT',root):
                    self.assertEqual(C.producer._controller_identity(policy),original)
                    injected=SimpleNamespace(__file__=str(root/'tools/injected.py'))
                    with patch.dict(sys.modules,{'unreviewed_repo_module':injected}),self.assertRaises(C.producer.host.Unavailable):
                        C.producer._controller_identity(policy)
                for mutation in ('missing','changed','mode','alias'):
                    previous=deepcopy(tree)
                    if mutation=='missing':previous.pop('tools/controller.py')
                    elif mutation=='changed':previous['tools/controller.py']['sha']='f'*40
                    else:previous['tools/controller.py']['mode']='100755' if mutation=='mode' else '120000'
                    with self.subTest(mutation=mutation),self.assertRaises(A.ApiError):
                        C.original_controller(policy,previous,tree,root)
                (root/'tools/controller.py').write_bytes(b'altered dirty source')
                with self.assertRaises(A.ApiError):C.original_controller(policy,tree,tree,root)

    def test_native_tree_rejects_duplicate_path_truncation_mode_and_wrong_tree_identity(self):
        import postmerge as C
        from types import SimpleNamespace
        row={'path':'source.py','mode':'100644','type':'blob','sha':'a'*40}
        good={'sha':'b'*40,'truncated':False,'tree':[row]}
        for mutation in ('duplicate','truncated','mode','tree','path'):
            value=deepcopy(good)
            if mutation=='duplicate':value['tree'].append(deepcopy(row))
            elif mutation=='truncated':value['truncated']=True
            elif mutation=='mode':value['tree'][0]['mode']='040000'
            elif mutation=='tree':value['sha']='c'*40
            else:value['tree'][0]['path']='../outside'
            adapter=SimpleNamespace(_commit=lambda _:('b'*40,[]),api=SimpleNamespace(immutable_tree=lambda _:value))
            with self.subTest(mutation=mutation),self.assertRaises((A.ApiError,C.inputs.InputError)):
                C.full_tree(adapter,'d'*40)

    def test_prospective_parent_keeps_existing_job_and_has_no_false_qualification_on_reuse(self):
        import postmerge as C
        import yaml
        # The baseline is an immutable reviewed legacy recipe. Reading the
        # active successor here would prepend its reuse condition twice after
        # the exact workflow installation.
        baseline=C.ROOT/'tools/repository-checks/workflows/host/parent-qualification.yml'
        legacy=next(row for row in C.producer._host_policy().package_policy().workflow_generations()
                    if row['name']=='android-owned-npm5-sync-ci-v1')
        raw=baseline.read_bytes()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
                         legacy['workflows']['.github/workflows/parent-qualification.yml']['sha'])
        old=yaml.safe_load(raw)
        new=yaml.safe_load((C.ROOT/C.TEMPLATE).read_text())
        self.assertEqual(set(new['jobs']),{'qualify-parent'})
        job=new['jobs']['qualify-parent'];self.assertEqual(job['name'],old['jobs']['qualify-parent']['name'])
        self.assertEqual(job['permissions'],{'contents':'read','actions':'read','pull-requests':'read','checks':'read'})
        # Admission reads these immutable files directly, without sparse Git
        # fallback. Every protected role must materialize the complete closure.
        _, manifests=C.attested.runtime._requirement_inventory(C.ROOT)
        required={*C.attested.runtime._TRUSTED_EXECUTION_FILES,*C.attested._CONSUMER_FILES,*manifests,
                  *C.producer.controller_sources(C.producer._host_policy())}
        templates=(new,yaml.safe_load((C.ROOT/C.producer.TEMPLATE).read_text()))
        for template in templates:
            for owner in template['jobs'].values():
                for step in owner.get('steps',[]):
                    if step.get('with',{}).get('path')!='trusted':continue
                    self.assertIs(step['with'].get('sparse-checkout-cone-mode'),False)
                    patterns=step['with']['sparse-checkout'].splitlines()
                    for relative in required:
                        self.assertTrue(any(relative==p or relative.startswith(p+'/') for p in patterns),
                                        (step['name'],relative))
        names=[row['name'] for row in job['steps']]
        lookup=names.index('Look up original protected PR proof before candidate setup')
        self.assertLess(lookup,names.index('Check out the exact parent commit'))
        for row in job['steps']:
            if row['name'] in {'Set up Python','Set up Java','Install QML and portable C++ contract prerequisites',
                'Prepare isolated host evidence validators','Run complete host qualification',
                'Run independently selected parent host contracts','Create content-addressed qualification evidence',
                'Upload immutable qualification evidence'}:
                self.assertIn("steps.reuse.outputs.shared_reused != 'true'",row['if'])
        steps={row['name']:row for row in job['steps']}
        for name in ('Check only affected tool dependencies and behavior','Check independently selected S3 package dependencies and behavior'):
            expected=deepcopy(next(row for row in old['jobs']['qualify-parent']['steps'] if row['name']==name))
            if 'S3 package' in name:
                expected['if']="(steps.reuse.outputs.shared_reused != 'true' || steps.reuse.outputs.package_work == 'true') && " + expected['if']
            self.assertEqual(steps[name],expected)
        validator=steps['Require an explicit reuse or actual-execution route']['run']
        for reused in ('true','false','','unknown'):
            for packages in ('true','false','','unknown'):
                result=subprocess.run(['bash','-c',validator],env={'SHARED_REUSED':reused,'PACKAGE_WORK':packages},capture_output=True)
                self.assertEqual(result.returncode==0,(reused,packages) in {('true','true'),('true','false'),('false','true')})
        manifest=json.loads((C.ROOT/'.github/package-workflow-generations.json').read_text())['generations']
        current={g['name']:g['workflows'] for g in manifest}
        blob=subprocess.check_output(['git','hash-object','--stdin'],input=(C.ROOT/C.TEMPLATE).read_bytes()).decode().strip()
        for before,after in (('android-owned-npm5-sync-ci-v1','postmerge-original-e-v1'),
                              ('protected-shared-producer-v1','protected-producer-postmerge-original-e-v1'),
                              ('protected-shared-producer-v1','protected-producer-ci37-v1')):
            self.assertEqual(set(current[after]),set(current[before]))
            changed=['.github/workflows/parent-qualification.yml']
            if after in {'protected-producer-postmerge-original-e-v1','protected-producer-ci37-v1'}:
                changed.insert(0,'.github/workflows/project-tests.yml')
                if after=='protected-producer-postmerge-original-e-v1':
                    source=C.ROOT/'tools/repository-checks/workflows/producers/legacy/protected-project-tests-postmerge-v1.yml'
                    project_blob=subprocess.check_output(['git','hash-object','--stdin'],input=source.read_bytes()).decode().strip()
                    self.assertEqual(project_blob,'861db7b76a11b9b8772e91cb24ec7cb9d918e339')
                else:
                    # Historical generations keep their reviewed bytes when the
                    # current dormant template gains a new execution reader.
                    project_blob='c1d3d14a9098de214b6544dca8dcba0072090c6b'
                self.assertEqual(current[after]['.github/workflows/project-tests.yml']['sha'],project_blob)
            self.assertEqual([p for p in current[after] if current[after][p]!=current[before][p]],changed)
            self.assertEqual(current[after]['.github/workflows/parent-qualification.yml']['sha'],
                             '84d98cac819755f98eecffba847e0bbcf667a6ca')
        latest=current['protected-producer-seven-target-ci-v1']
        self.assertEqual(latest['.github/workflows/parent-qualification.yml']['sha'],blob)
        for active,template in (
                ('.github/workflows/project-tests.yml',C.producer.TEMPLATE),
                ('.github/workflows/pr-metadata-context.yml',
                 'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml')):
            actual=subprocess.check_output(['git','hash-object','--stdin'],input=(C.ROOT/template).read_bytes()).decode().strip()
            if active=='.github/workflows/pr-metadata-context.yml':
                self.assertEqual(latest[active]['sha'],'d04a6dc70213d8b549bac30c11cc15eaf0182dea')
                self.assertEqual(current[C.producer.PLATFORM_GENERATION][active]['sha'],actual)
            else:
                self.assertEqual(latest[active]['sha'],actual)

    def test_disabled_cli_has_zero_api_and_writes_no_shared_pass_or_legacy_receipt(self):
        import postmerge as C
        import tempfile,os
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'output';output.touch()
            report=Path(folder)/'report.json'
            with patch.dict(os.environ,{'GITHUB_OUTPUT':str(output)}),patch.object(C,'SOURCE_READY',False), \
                    patch.object(C.A,'Adapter',side_effect=AssertionError('zero API')):
                self.assertEqual(C.main(['--report',str(report)]),0)
            self.assertEqual(output.read_text(),'shared_reused=false\npackage_work=true\nno_execution=false\n')
            self.assertEqual(json.loads(report.read_text()),{'reused':False,'reason':'protected-consumer-not-qualified'})


class MetadataRetentionConsumerTests(unittest.TestCase):
    """Actual retention/API/receipt validators over a small fake-native source.

    The two-suite registry and local controller/runtime admission are fixtures,
    not a complete shipping inventory or hosted qualification. Routing, tuple
    admission, metadata classification, native checker facts and whole-receipt
    verification remain real. No consumer environment or workload is created.
    """
    class SourceApi(FakeApi):
        def source_tree(self, identity):
            case = self.case
            nodes = {}
            for root, source in (("6" * 40, case.previous), (case.binding["merge_tree"], case.tree)):
                directories = {"": root}
                for path in source:
                    pieces = path.split("/")
                    for size in range(1, len(pieces)):
                        prefix = "/".join(pieces[:size])
                        directories[prefix] = hashlib.sha1((root + ":" + prefix).encode()).hexdigest()
                for prefix, oid in directories.items():
                    entries = []
                    for child, child_oid in directories.items():
                        if child and child.rpartition("/")[0] == prefix:
                            entries.append({"path": child.rsplit("/", 1)[-1], "mode": "040000",
                                            "type": "tree", "sha": child_oid})
                    entries.extend({"path": path.rsplit("/", 1)[-1], **entry}
                                   for path, entry in source.items() if path.rpartition("/")[0] == prefix)
                    nodes[oid] = {"sha": oid, "truncated": False, "tree": entries}
            return nodes.get(identity)

        def json(self, endpoint):
            path = endpoint[len(A.PREFIX):].lstrip("/").split("?", 1)[0]
            if path == "actions/workflows/repository-checks.yml":
                self.calls.append(endpoint)
                return self.mutate(endpoint, {"id": 99, "path": ".github/workflows/repository-checks.yml"})
            if path.startswith("git/trees/"):
                value = self.source_tree(path.rsplit("/", 1)[-1])
                if value is not None:
                    self.calls.append(endpoint)
                    return self.mutate(endpoint, deepcopy(value))
            return super().json(endpoint)

        def immutable_tree(self, identity):
            self.case.assertion(identity in {"6" * 40, self.case.binding["merge_tree"]})
            source = self.case.previous if identity == "6" * 40 else self.case.tree
            endpoint = A.PREFIX + "/git/trees/" + identity + "?recursive=1"
            self.calls.append(endpoint)
            return self.mutate(endpoint, {"sha": identity, "truncated": False,
                "tree": [{"path": path, **entry} for path, entry in source.items()]})

        def immutable_blob(self, identity):
            raise AssertionError("the full-profile fixture does not read data-admission blobs")

    def setUp(self):
        import postmerge as C
        from types import SimpleNamespace
        self.module = C
        self.case = AdapterTests(); self.case.setUp()
        c = self.case
        self.registry = deepcopy(c.context.registry)
        c.assertion = self.assertTrue
        c.originals[c.binding["base_sha"]] = ("6" * 40, ["7" * 40])
        real_host = C.producer._host_policy()
        real_package = real_host.package_policy()
        generations = real_package.workflow_generations()
        self.assertEqual(len(generations), 26)
        prior_generations=generations[:25]
        self.assertEqual(len(prior_generations), 25)
        self.assertEqual(len([row for row in prior_generations if row['name']!='protected-producer-original-default-boolean-v1']),24)
        self.assertEqual(len([row for row in prior_generations
                              if row['name'] not in {'npm-consumers-sync-ci-budget-cleanup-v1','protected-producer-original-default-boolean-v1'}]), 23)
        self.generation_name = getattr(self, 'generation_name', 'protected-producer-metadata-ci-v1')
        generation = next(row for row in generations if row["name"] == self.generation_name)
        sources = {".github/workflows/project-tests.yml": C.producer.TEMPLATE,
            ".github/workflows/repository-checks.yml": "tools/repository-checks/workflows/producers/repository-checks.yml",
            ".github/workflows/parent-qualification.yml": C.TEMPLATE,
            ".github/workflows/sync-validation.yml": ".github/workflows/sync-validation.yml",
            ".github/workflows/browser-client.yml": ".github/workflows/browser-client.yml",
            A.METADATA_WORKFLOW: "tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml"}
        if self.generation_name == 'protected-producer-metadata-ci-v1':
            sources.update({'.github/workflows/project-tests.yml':
                'tools/repository-checks/workflows/producers/legacy/protected-project-tests-metadata-v1.yml',
                '.github/workflows/repository-checks.yml':
                'tools/repository-checks/workflows/producers/legacy/repository-checks-metadata-v1.yml',
                '.github/workflows/parent-qualification.yml':
                'tools/repository-checks/workflows/producers/legacy/parent-qualification-metadata-v1.yml'})
        for name in getattr(self, 'extra_registry_names', ()):
            self.registry['suites'][name] = deepcopy(next(iter(self.registry['suites'].values())))
        def blob(relative):
            path = C.ROOT / relative
            self.assertFalse(path.is_symlink())
            self.assertIn(path.stat().st_mode & 0o777, (0o444, 0o644))
            raw = historical_metadata_workflow(relative,self.generation_name,C.ROOT)
            return {"mode": "100644", "type": "blob",
                    "sha": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()}
        workflows = {path: blob(relative) for path, relative in sources.items()}
        self.assertEqual(workflows, generation["workflows"])
        c.tree = {**deepcopy(c.context.tree), **workflows,
            C.producer.TEMPLATE: workflows[".github/workflows/project-tests.yml"],
            sources[A.METADATA_WORKFLOW]: workflows[A.METADATA_WORKFLOW],
            A.METADATA_SOURCE: {"mode":"100644","type":"blob",
                "sha":"9c531c34ba559d17255768d8cae3129496fac55d"},
            ".github/test-suites.json": {"mode": "100644", "type": "blob", "sha": "1" * 40},
            "tests/platform-profile.json": {"mode": "100644", "type": "blob", "sha": "2" * 40},
            ".github/branch-cleanup.json": {"mode": "100644", "type": "blob", "sha": "3" * 40}}
        for path in C._METADATA_OUTER_RECIPES:
            c.tree[path] = blob(path)
        c.previous = deepcopy(c.tree)
        c.tree[".github/branch-cleanup.json"]["sha"] = "4" * 40
        repository = {"full_name": A.REPOSITORY, "id": 1319052603}
        self.event = {"action": "edited", "number": 17, "repository": repository,
            "changes": {"title": {"from": "Previous title"}},
            "pull_request": {"number": 17, "state": "open", "title": "Current title",
                **{side: {"repo": deepcopy(repository), "ref": c.binding[side + "_ref"],
                           "sha": c.binding[side + "_sha"]} for side in ("base", "head")}}}
        self.environment = {"GITHUB_JOB": "route"}
        native = {"number": 17, "run_id": 101, "merge": c.binding["merge_sha"],
                  "head": c.binding["head_sha"], "base_snapshot": c.binding["base_sha"]}
        helper = SimpleNamespace(SOURCE_READY=True, native=lambda *args, **kwargs: deepcopy(native))
        package = SimpleNamespace(validate_tree_wiring=real_package.validate_tree_wiring,
            workflow_generations=real_package.workflow_generations, load=real_package.load,
            select=real_package.select, tools=real_package.tools, S3=real_package.S3, BROWSER=real_package.BROWSER,
            _trusted_bytes=lambda name, **kwargs: b'{"schema":1,"platform":"shared","suites":[]}'
                if name == "tests/platform-profile.json" else real_package._trusted_bytes(name, **kwargs))
        policy = SimpleNamespace(package_policy=lambda: package, ci_owned=real_host.ci_owned)
        self.selected = {"profile": C.producer.FULL_PROFILE, "suites": list(self.registry["suites"]),
            "selection": {"suites": list(self.registry["suites"]), "full_host": True,
                "include_platform": False, "reason": "fixture-complete-full-owner"}}
        self.api = self.SourceApi(c); self.adapter = A.Adapter(self.api)
        self.controller = c.pp.controller_digest
        self.patches = [patch.object(C, "_source_qualified", return_value=True),
            patch.object(C, "_metadata_module", return_value=helper),
            patch.object(C.execution, "checkout_identity", return_value=(c.binding["base_sha"], "6" * 40)),
            patch.object(C.inputs, "full_tree", side_effect=lambda *args: deepcopy(c.previous)),
            patch.object(C.inputs, "load_registry", return_value=self.registry),
            patch.object(C.producer, "_host_policy", return_value=policy),
            patch.object(C.producer, "selection_profile", return_value=self.selected),
            patch.object(C, "original_controller", return_value=self.controller),
            patch.object(C.sandbox, "contract", return_value={"digest": c.pp.runtime_contract}),
            patch.object(C.attested, "validate_environment", return_value={"environment_digest": "sha256:" + "1" * 64}),
            patch.object(C.execution, "capture_execution_environment", side_effect=AssertionError("unused consumer E")),
            patch.object(C.execution, "execute", side_effect=AssertionError("no metadata workload"))]
        for item in self.patches:
            item.start(); self.addCleanup(item.stop)
        c.plan, c.policy = C._policy(policy, self.registry, c.binding, self.controller, self.adapter, C.ROOT,
                                    self.selected["selection"])
        c.pp = c.policy.producer
        c.generation = {path: c.tree[path] for path in A.WORKFLOWS}
        self.git = C.producer.expected_git_context(self.adapter, c.binding)
        self.receipt = deepcopy(c.aggregate["results"]["shared-host"]["receipt"])
        self.receipt.update(schema=3, git_context=self.git, environment=FIXTURES.isolated_codec_environment(),
                            requested_suites=list(self.registry['suites']))
        self.receipt["results"] = {name: {"status": "passed", "fingerprint": P.inputs.suite_fingerprint(
            self.registry, name, c.tree, self.receipt["environment"])} for name in self.registry["suites"]}
        self.receipt = FIXTURES.signed(self.receipt, "receipt_digest")
        c.aggregate["results"]["shared-host"]["receipt"] = self.receipt
        old = FIXTURES.ProducerProtocolTests(); old.setUp()
        self.run = replace(old.run, workflow_path=c.pp.workflow_path, workflow_blob=c.pp.workflow_blob,
            workflow_commit=c.binding["merge_sha"], workflow_ref=c.pp.workflow_ref, event="pull_request",
            final_publisher=replace(old.run.final_publisher,
                receipt_sha256=hashlib.sha256(P.canonical(self.receipt)).hexdigest()))
        c.aggregate["descriptor_digest"] = P.descriptor(c.binding, c.plan, c.pp, self.run)["descriptor_digest"]
        c.aggregate = FIXTURES.signed(c.aggregate, "aggregate_digest")
        c.add_run(self.run)
        for index, name in enumerate(("native", "android", "project / tool-dependencies", "project / package-checks"), 150):
            c.jobs[100].append(self.job(index, 100, name, skipped=True))
        for index, (path, (name, steps)) in enumerate(C._METADATA_OUTER_RECIPES.items(), 160):
            c.jobs[100].append(self.job(index, 100, name, steps=steps))
            c.runs[100]["referenced_workflows"].append(self.reference(path))
        c.runs[101] = {**deepcopy(c.runs[100]), "id": 101, "run_number": 101, "check_suite_id": 1101,
            "status": "in_progress", "conclusion": None, "run_started_at": "2026-10-15T10:04:00Z",
            "referenced_workflows": [self.reference(A.METADATA_WORKFLOW)]}
        c.jobs[101] = [self.job(140, 101, A.METADATA_JOB, steps=(A.METADATA_STEP,), late=True)]
        c.artifacts[101] = []

    def reference(self, path):
        return {"path": A.REPOSITORY + "/" + path + "@" + self.case.binding["merge_sha"],
                "sha": self.case.binding["merge_sha"], "ref": self.case.pp.workflow_ref}

    def job(self, identity, run, name, *, skipped=False, steps=(), late=False):
        start, end = ("2026-10-15T10:04:01Z", "2026-10-15T10:04:20Z") if late else (
            "2026-10-15T10:02:00Z", "2026-10-15T10:03:00Z")
        return {"id": identity, "run_id": run, "run_attempt": 1, "head_sha": self.case.binding["head_sha"],
            "name": name, "status": "completed", "conclusion": "skipped" if skipped else "success",
            "started_at": None if skipped else start, "completed_at": None if skipped else end,
            "check_run_url": f"https://api.github.com/{A.PREFIX}/check-runs/{identity}",
            "steps": [{"number": number, "name": label, "status": "completed", "conclusion": "success",
                       "started_at": start, "completed_at": end} for number, label in enumerate(steps, 1)]}

    def verify(self, *, clock=lambda: NOW):
        return self.module.verify_metadata(self.event, self.environment, self.adapter, clock=clock)

    def test_same_m_retains_original_e_native_receipt_and_actual_checker_jobs_without_execution(self):
        C = self.module
        with patch.object(C, "metadata_selection", wraps=C.metadata_selection) as selection, \
                patch.object(C, "metadata_outer_jobs", wraps=C.metadata_outer_jobs) as outer, \
                patch.object(self.adapter, "verify", wraps=self.adapter.verify) as original:
            value = self.verify()
        self.assertEqual(selection.call_count, 1)
        self.assertEqual(outer.call_count, 2)
        self.assertEqual(original.call_count, 1)
        self.assertEqual(outer.call_args.args[5], "true")
        self.assertEqual(value["metadata_only"], "true")
        self.assertIs(value["qualification"], False)
        self.assertEqual(value["executed_suites"], [])
        self.assertEqual(value["retained_suites"], list(self.registry["suites"]))
        self.assertEqual(set(value["retained_checker_jobs"]), set(C._METADATA_OUTER_RECIPES))
        proof = value["original_proof"]
        self.assertTrue(proof["verified"])
        self.assertEqual(proof["run_id"], 100)
        self.assertEqual(proof["receipt_sha256"], hashlib.sha256(P.canonical(self.receipt)).hexdigest())
        self.assertEqual(proof["expires_at"], self.case.aggregate["expires_at"])
        self.assertEqual(proof["source_chain"]["producer_commit"], self.case.binding["merge_sha"])
        self.assertEqual(C.attested.validate_environment.call_args.args[0], self.receipt["environment"])
        C.execution.capture_execution_environment.assert_not_called()
        C.execution.execute.assert_not_called()

    def test_failed_docs_or_security_command_cannot_be_retained(self):
        for path, (name, _) in self.module._METADATA_OUTER_RECIPES.items():
            job = next(row for row in self.case.jobs[100] if row["name"] == name)
            job["steps"][0]["conclusion"] = "failure"
            with self.subTest(path=path), self.assertRaisesRegex(P.ProtocolError, "checker command"):
                self.verify()
            job["steps"][0]["conclusion"] = "success"

    def test_executed_external_owner_or_package_delta_is_not_metadata_retention(self):
        c = self.case
        for name in ("native", "android", "project / tool-dependencies", "project / package-checks"):
            job = next(row for row in c.jobs[100] if row["name"] == name)
            before = deepcopy(job)
            job.update(conclusion="success", started_at="2026-10-15T10:02:00Z", completed_at="2026-10-15T10:03:00Z")
            with self.subTest(owner=name), self.assertRaisesRegex(P.ProtocolError, "executed external owner"):
                self.verify()
            job.clear(); job.update(before)
        path = "script-archive/marketplace/S3Server/package-lock.json"
        c.previous[path] = {"mode": "100644", "type": "blob", "sha": "5" * 40}
        c.tree[path] = {"mode": "100644", "type": "blob", "sha": "6" * 40}
        with self.assertRaisesRegex(P.ProtocolError, "CI-owned|package/tool"):
            self.verify()

    def test_missing_metadata_marker_and_pending_real_producer_never_retain_success(self):
        references = self.case.runs[101]["referenced_workflows"]
        self.case.runs[101]["referenced_workflows"] = []
        with self.assertRaisesRegex(P.ProtocolError, "authenticated one-way"):
            self.verify()
        self.case.runs[101]["referenced_workflows"] = references
        marker = self.case.jobs[101][0]
        marker["steps"][0]["conclusion"] = "failure"
        with self.assertRaisesRegex(P.ProtocolError, "authenticated one-way"):
            self.verify()
        marker["steps"][0]["conclusion"] = "success"
        self.case.runs[100].update(status="in_progress", conclusion=None)
        with self.assertRaisesRegex(P.ProtocolError, "newest original producer"):
            self.verify()

    def test_resigned_original_e_cannot_change_native_whole_receipt_commitment(self):
        changed = deepcopy(self.receipt)
        changed["environment"]["prepared"]["roots"][self.module.inputs.ISOLATED_CACERTS] = "sha256:" + "b" * 64
        changed["results"] = {name: {"status": "passed", "fingerprint": P.inputs.suite_fingerprint(
            self.registry, name, self.case.tree, changed["environment"])} for name in self.registry["suites"]}
        self.case.aggregate["results"]["shared-host"]["receipt"] = FIXTURES.signed(changed, "receipt_digest")
        self.case.aggregate = FIXTURES.signed(self.case.aggregate, "aggregate_digest")
        self.case.artifacts[100] = self.case.artifacts[100][:1]
        self.case.artifact(self.run, "aggregate", self.case.aggregate)
        with self.assertRaisesRegex(P.ProtocolError, "native|receipt"):
            self.verify()

    def test_final_trusted_source_and_expiry_are_bookended_after_original_verification(self):
        C, c = self.module, self.case
        with patch.object(C.execution, "checkout_identity", side_effect=(
                (c.binding["base_sha"], "6" * 40), ("9" * 40, "6" * 40))), \
                patch.object(self.adapter, "verify", wraps=self.adapter.verify) as original:
            with self.assertRaisesRegex(P.ProtocolError, "actual trusted controller"):
                self.verify()
            self.assertEqual(original.call_count, 1)
        expired = False
        reads = 0
        def controller(*args, **kwargs):
            nonlocal expired, reads
            reads += 1
            if reads == 2:
                expired = True
            return self.controller
        with patch.object(C, "original_controller", side_effect=controller), \
                patch.object(self.adapter, "verify", wraps=self.adapter.verify) as original:
            with self.assertRaisesRegex(P.ProtocolError, "actual trusted controller"):
                self.verify(clock=lambda: P._time(c.aggregate["expires_at"]) if expired else NOW)
            self.assertEqual(original.call_count, 1)
            self.assertEqual(reads, 2)



class NativeDelegatedMetadataTests(unittest.TestCase):
    """Exact21 completed native publication plus real aggregate/API checks.

    The additional named commands use the same small fixture closure; this is
    an owner-admission regression, not execution or shipping qualification.
    """
    def setUp(self):
        self.fixture = MetadataRetentionConsumerTests('runTest')
        self.fixture.generation_name = 'protected-producer-seven-target-ci-v1'
        self.fixture.extra_registry_names = ('documentation-contracts', 'documentation',
                                             'policy-consistency', 'workflow-contracts')
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.module, self.case, self.adapter = f.module, f.case, f.adapter
        self.docs = next(job for job in self.case.jobs[100]
                         if job['name'] == 'documentation / documentation')
        self.docs.update(name='documentation', conclusion='skipped', started_at=None,
                         completed_at=None, steps=[])
        self.security = next(job for job in self.case.jobs[100]
                            if job['name'] == 'workflow-security / Actionlint, Zizmor, and Gitleaks')
        self.contract = next(step for step in self.security['steps']
                             if step['name'] == 'Verify fail-closed workflow contracts')
        self.contract.update(conclusion='skipped', started_at=None, completed_at=None)
        self.fallback = f.job(170, 100, 'workflow-contracts', skipped=True)
        self.case.jobs[100].append(self.fallback)

    def verify(self):
        return self.fixture.verify()

    def test_exact21_retains_actual_shared_docs_and_only_delegated_contract_step(self):
        value = self.verify()
        self.assertEqual(value['metadata_only'], 'true')
        self.assertTrue(value['original_proof']['verified'])
        self.assertEqual(value['original_proof']['receipt_sha256'],
                         hashlib.sha256(P.canonical(self.fixture.receipt)).hexdigest())
        docs = value['retained_checker_jobs']['.github/workflows/documentation-checks.yml']
        self.assertEqual(docs['shared_suites'], sorted(self.module.DOCUMENTATION_SUITES))
        self.assertEqual(docs['native']['conclusion'], 'skipped')
        self.module.execution.capture_execution_environment.assert_not_called()
        self.module.execution.execute.assert_not_called()

    def test_delegated_docs_still_need_exact_skipped_native_record(self):
        for mutation in ({'conclusion': 'failure'}, {'conclusion': 'success'},
                         {'name': 'documentation / documentation'}, {'run_attempt': 2}):
            before = deepcopy(self.docs); self.docs.update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(P.ProtocolError): self.verify()
            self.docs.clear(); self.docs.update(before)
        self.case.jobs[100].append(deepcopy(self.docs))
        with self.assertRaises(P.ProtocolError): self.verify()

    def test_only_workflow_contract_step_may_be_skipped_or_failed(self):
        for step in self.security['steps']:
            if step is self.contract:
                step['conclusion'] = 'failure'
                with self.assertRaises(P.ProtocolError): self.verify()
                step['conclusion'] = 'skipped'
                continue
            for state in ('skipped', 'failure', 'cancelled'):
                step['conclusion'] = state
                with self.subTest(step=step['name'], state=state), self.assertRaises(P.ProtocolError): self.verify()
            step['conclusion'] = 'success'

    def test_a_missing_or_changed_native_whole_receipt_never_delegates(self):
        publisher = next(job for job in self.case.jobs[100]
                         if job['name'].startswith(self.module.producer.PUBLISH_PREFIX))
        before = deepcopy(publisher)
        for mutation in ({'name': self.module.producer.PUBLISH_PREFIX + 'f' * 64},
                         {'conclusion': 'failure'}, {'status': 'in_progress', 'conclusion': None}):
            publisher.update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(P.ProtocolError): self.verify()
            publisher.clear(); publisher.update(before)
        changed = deepcopy(self.fixture.receipt)
        changed['results']['documentation']['status'] = 'failed'
        with self.assertRaises(P.ProtocolError):
            self.module.metadata_outer_jobs(self.adapter, 100, self.case.binding,
                self.case.tree, self.case.previous, 'true', shared_receipt=changed)

    def test_native_contract_owner_requires_exact_skipped_fallback_job(self):
        for state in ('success', 'failure', 'cancelled', None):
            self.fallback['conclusion'] = state
            with self.subTest(state=state), self.assertRaises(P.ProtocolError): self.verify()
        self.fallback['conclusion'] = 'skipped'
        self.case.jobs[100].remove(self.fallback)
        with self.assertRaises(P.ProtocolError): self.verify()

    def test_a_real_fallback_contract_is_required_when_the_shared_owner_lacks_it(self):
        f = self.fixture
        del f.registry['suites']['workflow-contracts']
        f.selected['suites'].remove('workflow-contracts')
        f.selected['selection']['suites'].remove('workflow-contracts')
        c = self.case
        self.assertEqual(c.plan['owners']['shared-host']['suites'], f.selected['selection']['suites'])
        receipt = deepcopy(f.receipt)
        receipt['requested_suites'].remove('workflow-contracts')
        del receipt['results']['workflow-contracts']
        f.receipt = FIXTURES.signed(receipt, 'receipt_digest')
        c.aggregate['results']['shared-host']['receipt'] = f.receipt
        f.run = replace(f.run, final_publisher=replace(f.run.final_publisher,
            receipt_sha256=hashlib.sha256(P.canonical(f.receipt)).hexdigest()))
        c.aggregate['descriptor_digest'] = P.descriptor(c.binding,c.plan,c.pp,f.run)['descriptor_digest']
        c.aggregate = FIXTURES.signed(c.aggregate, 'aggregate_digest')
        extras = [job for job in c.jobs[100] if job['name'] in {
            'native','android','project / tool-dependencies','project / package-checks',
            'documentation','workflow-security / Actionlint, Zizmor, and Gitleaks','workflow-contracts'}]
        c.add_run(f.run)
        c.jobs[100].extend(extras)
        for path in self.module._METADATA_OUTER_RECIPES:
            c.runs[100]['referenced_workflows'].append(f.reference(path))
        replacement = f.job(170, 100, 'workflow-contracts', steps=('Verify remaining workflow contracts',), late=True)
        self.fallback.clear(); self.fallback.update(replacement)
        with self.assertRaises(P.ProtocolError): self.verify()  # Before final publication is not this route.
        self.fallback.update(started_at='2026-10-15T10:04:46Z', completed_at='2026-10-15T10:04:49Z')
        self.fallback['steps'][0].update(started_at='2026-10-15T10:04:46Z', completed_at='2026-10-15T10:04:49Z')
        self.assertEqual(self.verify()['metadata_only'], 'true')
        self.fallback['steps'][0]['conclusion'] = 'failure'
        with self.assertRaises(P.ProtocolError): self.verify()

    def test_missing_receipt_cannot_make_skipped_checker_jobs_authoritative(self):
        with self.assertRaises(P.ProtocolError):
            self.module.metadata_outer_jobs(self.adapter, 100, self.case.binding,
                self.case.tree, self.case.previous, 'true')

    def test_newer_attempt_or_final_source_drift_still_rejects_retention(self):
        self.case.runs[100]['run_attempt'] = 2
        with self.assertRaises(P.ProtocolError): self.verify()
        self.case.runs[100]['run_attempt'] = 1
        path = '.github/workflows/workflow-security.yml'
        self.case.previous[path]['sha'] = 'f' * 40
        with self.assertRaises(P.ProtocolError): self.verify()


class DocumentationPushOwnerTests(unittest.TestCase):
    """Real original schema3/native aggregate; local source primitives are fixtures.

    The separate source guard tests authenticate the real finite controller and
    lookup graph. These fake API facts cannot qualify a production runtime.
    """
    def setUp(self):
        self.fixture=MainConsumerTests('runTest')
        self.fixture.generation_name='protected-producer-postmerge-original-e-v1'
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;self.module=f.module;self.case=f.case;self.api=f.api;self.adapter=f.adapter
        self.original_run=self.adapter.capture_integrated(500,self.case.plan,self.case.policy,now=NOW).observations[0].run
        C=self.module
        f.tree['tests/platform-profile.json']=C.source_admission.ordinary(C.source_admission.SHARED_PROFILE)
        raw=(C.ROOT/A.DOCUMENTATION_PUSH_WORKFLOW).read_bytes()
        f.tree[A.DOCUMENTATION_PUSH_WORKFLOW]=C.source_admission.ordinary(C.source_admission.blob_id(raw))
        shipping=json.loads((C.ROOT/'.github/test-suites.json').read_bytes())
        for name in C.DOCUMENTATION_SUITES:
            f.registry['suites'][name]=deepcopy(shipping['suites'][name])
            for path in f.registry['suites'][name]['closure']['required']:
                body=(C.ROOT/path).read_bytes()
                f.tree[path]=C.source_admission.ordinary(C.source_admission.blob_id(body))
        f.previous.clear();f.previous.update(deepcopy(f.tree))
        self.case.plan['owners']['shared-host']['suites']=list(f.registry['suites'])
        C.producer.selection_profile.return_value={
            'profile':C.producer.FULL_PROFILE,'suites':list(f.registry['suites']),
            'selection':{'suites':list(f.registry['suites']),'full_host':True,'include_platform':True,'reason':'fixture-full-owner'}}
        f.receipt.update(requested_suites=list(f.registry['suites']))
        self.refresh_receipt()
        self.case.push.update(workflow_id=7654321,path=A.DOCUMENTATION_PUSH_WORKFLOW)
        base_json=self.api.json
        def json_api(endpoint):
            if endpoint==A.PREFIX+'/actions/workflows/documentation-push-owner.yml':
                self.api.calls.append(endpoint)
                return self.api.mutate(endpoint,{'id':7654321,'path':A.DOCUMENTATION_PUSH_WORKFLOW,'state':'active'})
            return base_json(endpoint)
        self.api.json=json_api
        f.environment.update(GITHUB_JOB='documentation-source',GITHUB_WORKFLOW_REF=
            A.REPOSITORY+'/'+A.DOCUMENTATION_PUSH_WORKFLOW+'@refs/heads/main')
        item=patch.object(C,'integrated_controller',return_value=self.case.pp.controller_digest)
        item.start();self.addCleanup(item.stop)

    def refresh_receipt(self):
        f=self.fixture
        f.receipt['results']={name:{'status':'passed','fingerprint':P.inputs.suite_fingerprint(
            f.registry,name,f.tree,f.receipt['environment'])} for name in f.receipt['requested_suites']}
        f.receipt=FIXTURES.signed(f.receipt,'receipt_digest')
        self.case.aggregate['results']['shared-host']['receipt']=f.receipt
        run=replace(self.original_run,final_publisher=replace(self.original_run.final_publisher,
            receipt_sha256=hashlib.sha256(P.canonical(f.receipt)).hexdigest()))
        self.case.add_run(run);self.case.runs[100]['pull_requests']=[]

    def lookup(self,clock=lambda:NOW):
        return self.module.lookup(self.fixture.event,self.fixture.environment,self.adapter,clock=clock)

    def test_actual_original_schema3_and_every_documentation_suite_are_verified_without_consumer_E(self):
        value=self.lookup();self.assertTrue(value['reused'],value)
        proof=value['proof'];self.assertEqual(proof['original_commit'],self.case.binding['merge_sha'])
        self.assertNotEqual(proof['original_commit'],proof['current_commit'])
        self.assertEqual(proof['original_proof']['receipt_sha256'],hashlib.sha256(P.canonical(self.fixture.receipt)).hexdigest())
        self.assertLessEqual(self.module.DOCUMENTATION_SUITES,set(proof['reused_suites']))
        self.assertEqual(proof['executed_suites'],[])
        self.assertTrue(any(endpoint.endswith('/actions/workflows/documentation-push-owner.yml') for endpoint in self.api.calls))
        self.assertEqual(self.case.pp.actions_app_id,15368)

    def test_each_missing_selected_documentation_suite_declines_before_original_proof(self):
        C=self.module;selected=C.producer.selection_profile.return_value['selection']
        complete=list(selected['suites'])
        for name in C.DOCUMENTATION_SUITES:
            selected['suites']=[item for item in complete if item!=name]
            with self.subTest(name=name),patch.object(self.adapter,'capture_integrated',side_effect=AssertionError('missing owner reached proof')):
                self.assertFalse(self.lookup()['reused'])
        selected['suites']=complete

    def test_fixed_filename_registration_unknown_id_path_state_and_bookend_drift_decline(self):
        for kind in ('id','path','state','late-id'):
            reads=0
            def mutate(endpoint,value):
                nonlocal reads
                if endpoint.endswith('/actions/workflows/documentation-push-owner.yml'):
                    reads+=1
                    if kind=='id' or kind=='late-id' and reads>1:value['id']=7654322
                    elif kind=='path':value['path']='.github/workflows/other.yml'
                    elif kind=='state':value['state']='disabled_manually'
                return value
            self.api.mutate=mutate
            with self.subTest(kind=kind):self.assertFalse(self.lookup()['reused'])
        self.api.mutate=lambda endpoint,value:value
        self.case.push['workflow_id']=350930890
        self.assertFalse(self.lookup()['reused'])

    def test_missing_pending_failed_foreign_and_wrong_native_whole_hash_use_actual_fallback(self):
        runs,jobs,artifacts=deepcopy((self.case.runs,self.case.jobs,self.case.artifacts))
        for kind in ('missing','pending','failed','foreign','wholehash'):
            self.case.runs,self.case.jobs,self.case.artifacts=deepcopy((runs,jobs,artifacts))
            if kind=='missing':self.case.runs.clear()
            elif kind=='pending':self.case.runs[100].update(status='in_progress',conclusion=None)
            elif kind=='failed':self.case.runs[100].update(status='completed',conclusion='failure')
            elif kind=='foreign':self.case.runs[100]['repository']['id']=42
            else:self.case.jobs[100][-1]['name']=self.case.policy.final_publisher_prefix+'f'*64
            with self.subTest(kind=kind):self.assertFalse(self.lookup()['reused'])

    def test_changed_wrapper_or_environment_and_final_expiry_cannot_retain_original_proof(self):
        f=self.fixture;before=deepcopy(f.tree[A.DOCUMENTATION_PUSH_WORKFLOW])
        # Independently read current S differs from actual trusted D.
        raw_tree=self.api.immutable_tree
        def changed(oid):
            value=raw_tree(oid)
            if oid==self.case.binding['merge_tree']:
                next(row for row in value['tree'] if row['path']==A.DOCUMENTATION_PUSH_WORKFLOW)['sha']='f'*40
            return value
        self.api.immutable_tree=changed
        self.assertFalse(self.lookup()['reused']);self.api.immutable_tree=raw_tree
        self.assertEqual(f.tree[A.DOCUMENTATION_PUSH_WORKFLOW],before)
        f.receipt['environment']['prepared']['roots'][self.module.inputs.ISOLATED_VENV]='sha256:'+'b'*64
        self.case.aggregate['results']['shared-host']['receipt']=FIXTURES.signed(f.receipt,'receipt_digest')
        self.case.aggregate=FIXTURES.signed(self.case.aggregate,'aggregate_digest')
        self.case.artifacts[100]=self.case.artifacts[100][:1]
        self.case.artifact(self.original_run,'aggregate',self.case.aggregate)
        self.assertFalse(self.lookup()['reused'])
        self.assertFalse(self.lookup(clock=lambda:P._time(self.case.aggregate['expires_at']))['reused'])


class AffectedPostmergeConsumerTests(unittest.TestCase):
    """Actual protected pure plan + original native schema3 on bounded fake trees."""
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('postmerge_affected_plan_fixtures',
            Path(__file__).with_name('ci-integration-test.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        cls.planner_case=module.AffectedProtectedAdmissionTests
        cls.planner_case.setUpClass();cls.addClassCleanup(cls.planner_case.doClassCleanups)

    def setUp(self):
        from types import SimpleNamespace
        self.planner=self.planner_case('runTest');self.planner.setUp();self.addCleanup(self.planner.doCleanups)
        self.real_selection=self.planner_case.profile.__globals__['P'].selection_profile
        f=MainConsumerTests('runTest');f.generation_name='protected-producer-postmerge-original-e-v1'
        f.setUp();self.addCleanup(f.doCleanups)
        self.fixture=f;C=f.module;self.module=C;self.case=f.case;self.api=f.api;self.adapter=f.adapter
        self.original_run=self.adapter.capture_integrated(500,self.case.plan,self.case.policy,now=NOW).observations[0].run
        # Retain one complete known native generation on all three maps. No
        # real historical commit, ambient checkout or candidate import is used.
        enrolled={path:deepcopy(f.tree[path]) for path in self.case.generation}
        enrolled[C.TEMPLATE]=deepcopy(enrolled['.github/workflows/parent-qualification.yml'])
        for tree in (self.planner.old,self.planner.candidate,self.planner.base):tree.update(deepcopy(enrolled))
        f.registry.clear();f.registry.update(deepcopy(self.planner.registry))
        f.tree.clear();f.tree.update(deepcopy(self.planner.candidate))
        f.previous.clear();f.previous.update(deepcopy(self.planner.old))
        package=C.producer._host_policy.return_value.package_policy()
        router=self.planner.router
        self.policy=SimpleNamespace(package_policy=lambda:package,select=router.select,
            _select_legacy=router._select_legacy,ci_owned=router.ci_owned)
        C.producer._host_policy.return_value=self.policy
        def select(policy,registry,candidate,base,trusted,**kwargs):
            return self.real_selection(policy,registry,candidate,base,trusted,
                root=self.planner.root,target=kwargs.get('target','main'),read_blob=kwargs.get('read_blob'))
        C.producer.selection_profile.side_effect=select
        self.profile=select(self.policy,f.registry,f.tree,f.previous,f.previous)
        self.case.plan['owners']['shared-host'].update(suites=list(self.profile['suites']),include_platform=False)
        f.receipt.update(requested_suites=list(self.profile['suites']),include_platform=False)
        f.receipt['results']={name:{'status':'passed','fingerprint':P.inputs.suite_fingerprint(
            f.registry,name,f.tree,f.receipt['environment'])} for name in f.receipt['requested_suites']}
        self.publish(f.receipt)
        item=patch.object(C,'integrated_controller',return_value=self.case.pp.controller_digest)
        item.start();self.addCleanup(item.stop)

    def publish(self,receipt):
        self.fixture.receipt=FIXTURES.signed(receipt,'receipt_digest')
        self.case.aggregate['results']['shared-host']['receipt']=self.fixture.receipt
        run=replace(self.original_run,final_publisher=replace(self.original_run.final_publisher,
            receipt_sha256=hashlib.sha256(P.canonical(self.fixture.receipt)).hexdigest()))
        self.case.add_run(run);self.case.runs[100]['pull_requests']=[]

    def lookup(self,clock=lambda:NOW):
        return self.module.lookup(self.fixture.event,self.fixture.environment,self.adapter,clock=clock)

    def test_real_protected_subset_reuses_exact_selected_original_native_schema3_results(self):
        C=self.module
        with patch.object(C.execution,'validate_receipt',wraps=C.execution.validate_receipt) as validate:
            result=self.lookup()
        self.assertTrue(result['reused'],result)
        self.assertEqual(len(self.fixture.registry['suites']),61)
        self.assertIn('native-owner-lifecycle',self.fixture.registry['suites'])
        self.assertEqual(self.profile['selection']['reason'],'protected-affected-dependencies')
        self.assertNotIn('device-control-plane-full',self.profile['suites'])
        self.assertTrue(set(self.profile['suites'])<set(self.fixture.registry['suites']))
        proof=result['proof'];self.assertEqual(proof['reused_suites'],self.profile['suites'])
        self.assertEqual(proof['executed_suites'],[])
        self.assertEqual(proof['original_commit'],self.case.binding['merge_sha'])
        self.assertEqual(proof['original_proof']['receipt_sha256'],hashlib.sha256(P.canonical(self.fixture.receipt)).hexdigest())
        self.assertTrue(any(call.kwargs.get('require_all') is False for call in validate.call_args_list))
        self.assertGreaterEqual(C.producer.selection_profile.call_count,2)

    def test_claimed_subset_or_graph_cannot_bypass_independent_selection(self):
        C=self.module;claim=deepcopy(self.profile['selection'])
        for change in ('names','label','platform','empty','graph'):
            selected=deepcopy(claim)
            if change=='names':selected['suites']=selected['suites'][1:]
            elif change=='label':selected['affected']['required']=[]
            elif change=='platform':selected['include_platform']=True
            elif change=='empty':selected['suites']=[]
            else:selected['affected']['dependency_digest']='sha256:'+'f'*64
            with self.subTest(change=change),patch.object(self.policy,'select',return_value=selected), \
                 patch.object(self.adapter,'capture_integrated',side_effect=AssertionError('forged plan reached proof')):
                self.assertFalse(self.lookup()['reused'])

    def test_selected_result_membership_status_and_fingerprint_are_enforced_even_with_new_native_hash(self):
        receipt=deepcopy(self.fixture.receipt);selected=self.profile['suites'][0]
        omitted=self.profile['selection']['affected']['omitted'][0]
        for change in ('missing','extra','failed','fingerprint','requested'):
            changed=deepcopy(receipt)
            if change=='missing':del changed['results'][selected]
            elif change=='extra':changed['results'][omitted]={'status':'passed','fingerprint':'sha256:'+'a'*64}
            elif change=='failed':changed['results'][selected]['status']='failed'
            elif change=='fingerprint':changed['results'][selected]['fingerprint']='sha256:'+'a'*64
            else:
                changed['requested_suites'].remove(selected);del changed['results'][selected]
            self.publish(changed)
            with self.subTest(change=change):self.assertFalse(self.lookup()['reused'])

    def test_changed_source_controller_child_scope_and_original_publisher_still_decline(self):
        C=self.module
        with patch.object(C,'integrated_controller',side_effect=ValueError('changed protected source')):
            self.assertFalse(self.lookup()['reused'])
        child=deepcopy(self.profile);child['selection']['include_platform']=True
        with patch.object(C.producer,'selection_profile',return_value=child):self.assertFalse(self.lookup()['reused'])
        self.case.jobs[100][-1]['name']=self.case.policy.final_publisher_prefix+'f'*64
        self.assertFalse(self.lookup()['reused'])

    def test_original_and_current_independent_plans_and_expiry_must_still_match(self):
        C=self.module;before=deepcopy(self.profile);after=deepcopy(before)
        after['selection']['affected']['paths'].append('unreviewed-path')
        with patch.object(C.producer,'selection_profile',side_effect=(before,after)):
            self.assertFalse(self.lookup()['reused'])
        self.assertFalse(self.lookup(clock=lambda:P._time(self.case.aggregate['expires_at']))['reused'])

    def test_full_registry_receipt_keeps_original_full60_requirement(self):
        C=self.module;full={'profile':C.producer.FULL_PROFILE,'binding':None,'suites':list(self.fixture.registry['suites']),
            'selection':{'suites':list(self.fixture.registry['suites']),'full_host':True,
                         'include_platform':False,'reason':'fixture-independent-full-owner'}}
        self.case.plan['owners']['shared-host']['suites']=full['suites']
        receipt=deepcopy(self.fixture.receipt);receipt['requested_suites']=full['suites']
        receipt['results']={name:{'status':'passed','fingerprint':P.inputs.suite_fingerprint(
            self.fixture.registry,name,self.fixture.tree,receipt['environment'])} for name in full['suites']}
        self.publish(receipt)
        with patch.object(C.producer,'selection_profile',return_value=full), \
             patch.object(C.execution,'validate_receipt',wraps=C.execution.validate_receipt) as validate:
            result=self.lookup()
        self.assertTrue(result['reused'],result)
        self.assertEqual(result['proof']['reused_suites'],full['suites'])
        self.assertTrue(any(call.kwargs.get('require_all') is True for call in validate.call_args_list))


class RetainedDefaultMetadataTests(unittest.TestCase):
    """Actual schema4/native Adapter with explicit local source-admission seams.

    Complete immutable originalD/projection validation is exercised by source4
    and sync fixtures; this class tests the additive metadata owner connection,
    independent D/B contexts and native whole-hash retention, without querying E.
    """
    def setUp(self):
        fixture=MetadataRetentionConsumerTests('runTest')
        fixture.extra_registry_names=('documentation-contracts','documentation','policy-consistency','workflow-contracts')
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.fixture=f=fixture;self.module=C=f.module;self.case=c=f.case;self.adapter=f.adapter
        self.sources={'.github/workflows/project-tests.yml':C.producer.PLATFORM_TEMPLATE,
            '.github/workflows/parent-qualification.yml':C.producer.PLATFORM_PARENT_TEMPLATE,
            '.github/workflows/repository-checks.yml':'tools/repository-checks/workflows/producers/repository-checks.yml',
            '.github/workflows/sync-validation.yml':'tools/repository-checks/workflows/sync-ci-selection.yml',
            '.github/workflows/browser-client.yml':'.github/workflows/browser-client.yml',
            A.METADATA_WORKFLOW:'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml'}
        self.generation={path:{'mode':'100644','type':'blob','sha':C.source_admission.blob_id(
            historical_metadata_workflow(source,'protected-producer-original-default-v1',C.ROOT))}
            for path,source in self.sources.items()}
        for tree in (c.previous,c.tree):
            tree.update(deepcopy(self.generation))
            tree[C.producer.PLATFORM_TEMPLATE]=deepcopy(self.generation['.github/workflows/project-tests.yml'])
            tree[self.sources[A.METADATA_WORKFLOW]]=deepcopy(self.generation[A.METADATA_WORKFLOW])
            tree[A.METADATA_SOURCE]={'mode':'100644','type':'blob','sha':C.source_admission.blob_id(
                (C.ROOT/A.METADATA_SOURCE).read_bytes())}
        package=C.producer._host_policy().package_policy()
        old_generations=package.workflow_generations()
        package.validate_tree_wiring=lambda tree:C.ci_profile.RETAINED_SOURCE_GENERATION \
            if all(tree.get(path)==entry for path,entry in self.generation.items()) else 'unknown'
        package.workflow_generations=lambda:[*old_generations,
            {'name':C.ci_profile.RETAINED_SOURCE_GENERATION,'workflows':self.generation}]
        self.policy=C.producer._host_policy()
        example=FIXTURES.RetainedSourceProtocolTests().fixture()
        self.retained=deepcopy(example.context.protected_source)
        c.binding['base_ref']='apple-ios';f.event['pull_request']['base']['ref']='apple-ios'
        self.default=self.retained['default_commit'];self.default_tree=self.retained['default_tree']
        self.local=deepcopy(c.previous);self.local['default-only.txt']={'mode':'100644','type':'blob','sha':'e'*40}
        self.source={'schema':1,'kind':'protected-default-controller-source-v1','target':'apple-ios',
            'target_profile':deepcopy(c.previous['tests/platform-profile.json']),
            'controller_digest':f.controller,'lookup_digest':'sha256:'+'3'*64,
            'base':c.binding['base_sha'],'default':self.default}
        original_json=f.api.json;original_tree=f.api.immutable_tree
        def json_api(endpoint):
            path=endpoint[len(A.PREFIX):].lstrip('/').split('?',1)[0]
            if path=='git/ref/heads/main':
                value={'ref':'refs/heads/main','object':{'type':'commit','sha':self.default}}
            elif path=='git/ref/heads/'+c.binding['base_ref']:
                value={'ref':'refs/heads/'+c.binding['base_ref'],'object':{'type':'commit','sha':c.binding['base_sha']}}
            elif path=='git/commits/'+self.default:
                value={'sha':self.default,'tree':{'sha':self.default_tree},'parents':[]}
            else:return original_json(endpoint)
            f.api.calls.append(endpoint);return f.api.mutate(endpoint,value)
        f.api.json=json_api
        f.api.immutable_tree=lambda oid:({'sha':oid,'truncated':False,
            'tree':[{'path':path,**entry} for path,entry in self.local.items()]} if oid==self.default_tree else original_tree(oid))
        C.execution.checkout_identity.return_value=(self.default,self.default_tree)
        C.inputs.full_tree.side_effect=lambda *args:deepcopy(self.local)
        self.source_guard=self.enterContext(patch.object(C.producer,'reuse_source_context',return_value=self.source))
        self.controller_guard=self.enterContext(patch.object(C,'integrated_controller_for_reuse',return_value=f.controller))
        # These fixtures isolate complete source reconstruction. Native receipt
        # authentication still executes the real class verifier at both ends.
        self.enterContext(patch.object(C.producer,'reuse_source_profile',
            side_effect=lambda *args,**kwargs:(deepcopy(f.selected),deepcopy(self.local))))
        self.enterContext(patch.object(C.producer,'selection_profile_for_reuse',return_value=f.selected))
        def original_source(adapter,invocation,plan,policy,context,receipt,binding,*,integrated,root,clock):
            A.require(not integrated and receipt.get('schema')==4
                and context.protected_source==self.retained and binding==c.binding,
                'explicit source reconstruction seam differs')
            verified=A.Adapter.verify(adapter,invocation,plan,policy,{'shared-host':context},clock=clock)
            return verified,object()
        self.enterContext(patch.object(C.producer,'verify_original_source',side_effect=original_source))
        c.plan,c.policy=C._policy(self.policy,f.registry,c.binding,f.controller,f.adapter,C.ROOT,
            f.selected['selection'],template=C.producer.PLATFORM_TEMPLATE)
        c.pp=c.policy.producer;c.generation={path:c.tree[path] for path in A.WORKFLOWS}
        self.assertEqual(c.pp.required_execution_schema,4)
        self.retained['binding'].update(source=c.binding['merge_sha'],git_context=f.git,
            selection=deepcopy(f.selected['selection']),registry=P.digest(f.registry))
        self.retained['admission']=deepcopy(self.source)
        def retained(receipt,binding,adapter,registry,selected,run_id,**kwargs):
            A.require(receipt.get('schema')==4 and receipt.get('protected_source')==self.retained
                and binding==c.binding and registry==f.registry and selected==f.selected['selection']
                and run_id==100,'explicit retained source fixture differs')
            return deepcopy(self.retained)
        self.retained_guard=self.enterContext(patch.object(C.producer,'retained_receipt_source',side_effect=retained))
        self.receipt=deepcopy(f.receipt);self.receipt.update(schema=4,protected_source=deepcopy(self.retained))
        self.receipt['results']={name:{'status':'passed','fingerprint':P.inputs.suite_fingerprint(
            f.registry,name,c.tree,self.receipt['environment'])} for name in f.registry['suites']}
        self.receipt=FIXTURES.signed(self.receipt,'receipt_digest')
        c.aggregate['results']['shared-host']['receipt']=self.receipt
        f.run=replace(f.run,workflow_blob=c.pp.workflow_blob,
            final_publisher=replace(f.run.final_publisher,receipt_sha256=hashlib.sha256(P.canonical(self.receipt)).hexdigest()))
        c.aggregate['descriptor_digest']=P.descriptor(c.binding,c.plan,c.pp,f.run)['descriptor_digest']
        c.aggregate=FIXTURES.signed(c.aggregate,'aggregate_digest');c.add_run(f.run)
        c.runs[100]['display_title']=A.ORDINARY_RUN_NAME
        c.runs[101]['display_title']=A.NONPRODUCER_RUN_NAME
        for index,name in enumerate(('native','android','project / tool-dependencies','project / package-checks',
                                     C.producer.PLATFORM_JOB,'documentation','workflow-contracts'),150):
            c.jobs[100].append(f.job(index,100,name,skipped=True))
        path='.github/workflows/workflow-security.yml';name,steps=C._METADATA_OUTER_RECIPES[path]
        security=f.job(170,100,name,steps=steps)
        next(step for step in security['steps'] if step['name']=='Verify fail-closed workflow contracts').update(
            conclusion='skipped',started_at=None,completed_at=None)
        c.jobs[100].append(security);c.runs[100]['referenced_workflows'].append(f.reference(path))

    def verify(self,**kwargs):return self.fixture.verify(**kwargs)

    def test_schema4_child_B_and_current_D_are_distinct_and_original_native_E_is_retained(self):
        value=self.verify()
        self.assertTrue(value['original_proof']['verified'])
        self.assertEqual(value['metadata_only'],'true');self.assertFalse(value['qualification'])
        self.assertNotEqual(self.case.binding['base_sha'],self.default)
        self.assertEqual(value['original_protected_source'],self.retained)
        self.assertEqual(value['original_proof']['receipt_sha256'],hashlib.sha256(P.canonical(self.receipt)).hexdigest())
        self.assertEqual(value['original_proof']['expires_at'],self.case.aggregate['expires_at'])
        self.assertEqual(value['executed_suites'],[])
        self.assertEqual(self.source_guard.call_count,2);self.assertEqual(self.controller_guard.call_count,2)
        self.assertEqual(self.retained_guard.call_count,2)
        self.assertEqual(self.controller_guard.call_args.args[4],'apple-ios')
        self.module.execution.capture_execution_environment.assert_not_called();self.module.execution.execute.assert_not_called()

    def test_unknown_generation_target_or_actual_default_source_cannot_retain(self):
        C=self.module;package=self.policy.package_policy();validate=package.validate_tree_wiring
        package.validate_tree_wiring=lambda tree:'protected-producer-original-default-v1-neighbor'
        with self.assertRaises(P.ProtocolError):self.verify()
        package.validate_tree_wiring=validate
        self.case.binding['base_ref']='unknown';self.fixture.event['pull_request']['base']['ref']='unknown'
        with self.assertRaises(P.ProtocolError):self.verify()
        self.case.binding['base_ref']='apple-ios';self.fixture.event['pull_request']['base']['ref']='apple-ios'
        C.execution.checkout_identity.return_value=('f'*40,self.default_tree)
        with self.assertRaises(P.ProtocolError):self.verify()

    def test_external_platform_or_false_original_source_cannot_be_retained(self):
        job=next(job for job in self.case.jobs[100] if job['name']==self.module.producer.PLATFORM_JOB)
        original=deepcopy(job)
        for state in ('success','failure',None):
            job.update(conclusion=state)
            with self.subTest(state=state),self.assertRaises(P.ProtocolError):self.verify()
        job.clear();job.update(original)
        self.retained_guard.side_effect=ValueError('immutable original source mismatch')
        with self.assertRaises(ValueError):self.verify()

    def test_original_native_hash_and_final_source_bookends_remain_mandatory(self):
        publisher=next(job for job in self.case.jobs[100] if job['name'].startswith(self.module.producer.PUBLISH_PREFIX))
        original=publisher['name'];publisher['name']=self.module.producer.PUBLISH_PREFIX+'0'*64
        with self.assertRaises(P.ProtocolError):self.verify()
        publisher['name']=original
        self.source_guard.side_effect=[self.source,{**self.source,'default':'f'*40}]
        with self.assertRaisesRegex(P.ProtocolError,'actual trusted controller'):self.verify()

    def test_new_ci_namespace_receives_actual_target_and_independent_original_base(self):
        # This is a forwarding negative, not fake CI37 runtime admission. The
        # real runtime validator must reject or admit the supplied actual E.
        self.fixture.selected['profile']=self.module.ci_profile.PROFILE
        with patch.object(self.module.runtime_ci,'plan_original_reuse',
                side_effect=ValueError('actual CI runtime admission required')) as runtime, \
             patch.object(self.adapter,'verify',side_effect=AssertionError('unadmitted CI proof reached verification')):
            with self.assertRaisesRegex(ValueError,'actual CI runtime admission'):self.verify()
        self.assertEqual(runtime.call_args.kwargs['target'],'apple-ios')
        self.assertEqual(runtime.call_args.kwargs['base_tree'],self.case.previous)
        self.assertEqual(runtime.call_args.args[8],self.local)

    def test_future_receipt_cannot_downgrade_even_with_new_local_and_native_hashes(self):
        receipt=deepcopy(self.receipt);receipt['schema']=3;del receipt['protected_source']
        receipt=FIXTURES.signed(receipt,'receipt_digest')
        self.case.aggregate['results']['shared-host']['receipt']=receipt
        aggregate=FIXTURES.signed(self.case.aggregate,'aggregate_digest')
        self.case.artifacts[100]=self.case.artifacts[100][:1]
        self.case.artifact(self.fixture.run,'aggregate',aggregate)
        publisher=next(job for job in self.case.jobs[100] if job['name'].startswith(self.module.producer.PUBLISH_PREFIX))
        publisher['name']=self.module.producer.PUBLISH_PREFIX+hashlib.sha256(P.canonical(receipt)).hexdigest()
        with self.assertRaisesRegex(P.ProtocolError,'versioned protected receipt'):self.verify()


class RetainedSourceNativeAPITests(unittest.TestCase):
    """Actual API/descriptor/aggregate/native hash; source closure fixture seam.

    Immutable B/D source closure is exercised separately by the real Git/API
    RetainedOriginalDefaultTests. This class supplies that expected result and
    verifies the whole native protocol, without any E query or execution.
    """
    def setUp(self):
        self.fixture=MainConsumerTests()
        self.fixture.generation_name='protected-producer-postmerge-original-e-v1'
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.case,self.adapter=self.fixture.case,self.fixture.adapter
        run=self.adapter.capture_integrated(500,self.case.plan,self.case.policy,now=NOW).observations[0].run
        example=FIXTURES.RetainedSourceProtocolTests().fixture()
        self.source=deepcopy(example.context.protected_source)
        self.source['binding']['git_context']=deepcopy(self.fixture.git)
        self.source['binding']['selection']=deepcopy(self.fixture.module.producer.selection_profile.return_value['selection'])
        self.receipt=deepcopy(self.fixture.receipt)
        self.receipt.update(schema=4,protected_source=deepcopy(self.source))
        self.receipt=FIXTURES.signed(self.receipt,'receipt_digest')
        self.case.pp=replace(self.case.pp,required_execution_schema=4)
        self.case.policy=replace(self.case.policy,producer=self.case.pp)
        self.case.aggregate['results']['shared-host']['receipt']=self.receipt
        self.case.add_run(replace(run,final_publisher=replace(run.final_publisher,
            receipt_sha256=hashlib.sha256(P.canonical(self.receipt)).hexdigest())))
        self.case.runs[100]['pull_requests']=[]
        self.context=P.SharedContext(self.fixture.registry,self.fixture.tree,self.receipt['environment'],
            self.case.binding['merge_sha'],self.case.binding['merge_tree'],self.fixture.git,self.source)

    def verify(self,context=None):
        return self.adapter.verify_integrated(500,self.case.plan,self.case.policy,
            {'shared-host':context or self.context},clock=lambda:NOW)

    def test_actual_original_native_schema4_and_E_are_retained_without_consumer_measurement(self):
        value=self.verify()
        self.assertTrue(value['verified'])
        self.assertEqual(value['receipt_sha256'],hashlib.sha256(P.canonical(self.receipt)).hexdigest())
        self.assertEqual(value['expires_at'],self.case.aggregate['expires_at'])
        self.assertEqual(value['source_chain']['producer_commit'],self.receipt['candidate_commit'])
        self.assertNotEqual(value['source_chain']['producer_commit'],self.case.integrated)
        self.fixture.module.execution.capture_execution_environment.assert_not_called()
        self.fixture.module.execution.execute.assert_not_called()

    def test_native_api_cannot_accept_schema4_without_independent_original_source(self):
        with self.assertRaises(P.ProtocolError):self.verify(replace(self.context,protected_source=None))
        changed=deepcopy(self.source);changed['projection_digest']='sha256:'+'0'*64
        with self.assertRaises(P.ProtocolError):self.verify(replace(self.context,protected_source=changed))

    def test_renewed_artifact_and_receipt_digests_cannot_change_native_source_commitment(self):
        changed=deepcopy(self.receipt);changed['protected_source']['projection_digest']='sha256:'+'0'*64
        changed=FIXTURES.signed(changed,'receipt_digest')
        self.case.aggregate['results']['shared-host']['receipt']=changed
        self.case.aggregate=FIXTURES.signed(self.case.aggregate,'aggregate_digest')
        run=self.adapter.capture_integrated(500,self.case.plan,self.case.policy,now=NOW).observations[0].run
        self.case.artifacts[100]=self.case.artifacts[100][:1]
        self.case.artifact(run,'aggregate',self.case.aggregate)
        with self.assertRaises(P.ProtocolError):self.verify(replace(self.context,protected_source=changed['protected_source']))


class ImmutableOriginalSourceTransportTests(unittest.TestCase):
    """Bounded fake source blobs; no API request or source execution."""
    def fixture(self,raw=b'# immutable original source\n'):
        oid=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        value={'sha':oid,'size':len(raw),'encoding':'base64','content':base64.b64encode(raw).decode('ascii')}
        return oid,value

    def read(self,oid,value):
        raw=value if type(value) is bytes else json.dumps(value).encode()
        with patch.object(A.GitHubReadOnly,'_request',return_value=raw) as request:
            result=A.GitHubReadOnly().immutable_source_blob(oid)
        request.assert_called_once_with(A.PREFIX+'/git/blobs/'+oid,1_500_000)
        return result

    def test_source_transport_accepts_realistic_large_source_without_widening_policy_reader(self):
        raw=b'# original test source\n'*4000
        oid,value=self.fixture(raw)
        self.assertEqual(self.read(oid,value),raw)
        with patch.object(A.GitHubReadOnly,'_request',return_value=json.dumps(value).encode()):
            with self.assertRaises(A.ApiError):A.GitHubReadOnly().immutable_blob(oid)
        with self.assertRaises(TypeError):A.GitHubReadOnly().immutable_source_blob(oid,maximum=2_000_000)
        with patch.object(A.GitHubReadOnly,'_request',side_effect=AssertionError('invalid source identity reached API')):
            for supplied in ('main','../HEAD','0'*40,'A'*40):
                with self.subTest(supplied=supplied),self.assertRaises(A.ApiError):A.GitHubReadOnly().immutable_source_blob(supplied)

    def test_immutable_bytes_avoid_repeat_GET_but_corruption_and_unverified_data_cannot_be_cached(self):
        raw=b'original immutable source\n';oid,value=self.fixture(raw);reader=A.GitHubReadOnly()
        with patch.object(reader,'_request',return_value=json.dumps(value).encode()) as request:
            self.assertEqual(reader.immutable_source_blob(oid),raw)
            self.assertEqual(reader.immutable_source_blob(oid),raw)
            request.assert_called_once()
            reader._immutable_source_cache[oid]=b'corrupt memory'
            with self.assertRaises(A.ApiError):reader.immutable_source_blob(oid)
            request.assert_called_once()
        reader=A.GitHubReadOnly();corrupt={**value,'size':len(raw)+1}
        with patch.object(reader,'_request',side_effect=[json.dumps(corrupt).encode(),json.dumps(value).encode()]) as request:
            with self.assertRaises(A.ApiError):reader.immutable_source_blob(oid)
            self.assertEqual(reader.immutable_source_blob(oid),raw)
            self.assertEqual(request.call_count,2)

    def test_source_content_cache_is_bounded_by_member_count_and_bytes(self):
        reader=A.GitHubReadOnly()
        for index in range(19):
            raw=('source '+str(index)).encode();oid,value=self.fixture(raw)
            with patch.object(reader,'_request',return_value=json.dumps(value).encode()):
                self.assertEqual(reader.immutable_source_blob(oid),raw)
            self.assertLessEqual(len(reader._immutable_source_cache),17)
        for index in range(9):
            raw=bytes([index])*1_000_000;oid,value=self.fixture(raw)
            with patch.object(reader,'_request',return_value=json.dumps(value).encode()):
                self.assertEqual(reader.immutable_source_blob(oid),raw)
            self.assertLessEqual(sum(map(len,reader._immutable_source_cache.values())),8_000_000)

    def test_source_transport_rejects_rebound_corrupt_noncanonical_oversize_or_duplicate_data(self):
        oid,original=self.fixture()
        for change in ('sha','size','negative','oversize','base64','padding','content','url','node','extra'):
            value=deepcopy(original)
            if change=='sha':value['sha']='f'*40
            elif change=='size':value['size']+=1
            elif change=='negative':value['size']=-1
            elif change=='oversize':value['size']=1_000_001
            elif change=='base64':value['content']='!!!'
            elif change=='padding':value['content']+='='
            elif change=='content':value['content']=base64.b64encode(b'X'*value['size']).decode()
            elif change=='url':value['url']='https://api.github.com/repos/other/fork/git/blobs/'+oid
            elif change=='node':value['node_id']='x'*513
            else:value['extra']=True
            with self.subTest(change=change),self.assertRaises(A.ApiError):self.read(oid,value)
        raw=json.dumps(original).encode()
        with self.assertRaises(A.ApiError):self.read(oid,raw[:-1]+b',"size":1}')
        with self.assertRaises(A.ApiError):self.read(oid,b' ' *1_500_001)


class UnchangedParentTests(unittest.TestCase):
    """Native/API fixtures plus actual raw Git, never a test/E execution."""
    def setUp(self):
        import os
        import tempfile
        from types import SimpleNamespace
        import postmerge as C
        self.C = C
        temporary = tempfile.TemporaryDirectory(prefix='overte-empty-parent-')
        self.addCleanup(temporary.cleanup)
        self.candidate = Path(temporary.name)
        def git(*args):
            return subprocess.check_output(['git','-c','commit.gpgsign=false',*args],
                cwd=self.candidate,stderr=subprocess.PIPE,text=True).strip()
        self.git = git
        git('init','-q','--initial-branch=main'); git('config','user.name','Fixture')
        git('config','user.email','fixture@example.invalid')
        self.package = C.producer._host_policy().package_policy()
        generation = next(row for row in self.package.workflow_generations()
            if row['name'] == C.producer.PLATFORM_GENERATION)
        for name, entry in generation['workflows'].items():
            # Historical callers must survive a shallow active26 checkout.
            relative = ('tools/repository-checks/workflows/producers/repository-checks.yml'
                if name == '.github/workflows/repository-checks.yml' else name)
            body = historical_metadata_workflow(relative, generation['name'], C.ROOT)
            self.assertEqual(hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest(),
                             entry['sha'])
            path = self.candidate/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(body)
        (self.candidate/'native.cpp').write_text('unchanged product input\n')
        git('add','.'); git('commit','-qm','Protected before')
        self.base = git('rev-parse','HEAD'); self.tree = git('rev-parse','HEAD^{tree}')
        self.source = git('commit-tree',self.tree,'-p',self.base,'-m','Adopt integrated history')
        git('checkout','-q','--detach',self.source)
        self.current = C.inputs.full_tree(self.candidate,self.source)
        self.local = deepcopy(self.current)
        # Finite D/controller admission is tested in source-admission tests.
        # This API fixture holds that source constant while raw B/M are real.
        self.local[C.producer.PLATFORM_PARENT_TEMPLATE] = deepcopy(self.current['.github/workflows/parent-qualification.yml'])
        self.default = 'd'*40; self.default_tree = 'e'*40
        self.binding = {'base_ref':'main','base_sha':self.base,'merge_sha':self.source,
            'merge_tree':self.tree,'pull_request':17}
        self.refs = {'target':self.source,'default':self.default,'default_ref':'main',
            'integration':{'tree':self.tree,'workflow_path':'.github/workflows/parent-qualification.yml',
                'workflow_id':77}}
        self.event = {'ref':'refs/heads/main','before':self.base,'after':self.source,
            'deleted':False,'forced':False,'repository':{'full_name':A.REPOSITORY,'id':1319052603}}
        self.native = {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':A.REPOSITORY,
            'GITHUB_REPOSITORY_ID':'1319052603','GITHUB_EVENT_NAME':'push','GITHUB_REF':'refs/heads/main',
            'GITHUB_REF_TYPE':'branch','GITHUB_RUN_ATTEMPT':'1','GITHUB_JOB':'common-parent',
            'RUNNER_ENVIRONMENT':'github-hosted','ImageOS':'ubuntu24','GITHUB_SHA':self.source,
            'GITHUB_WORKFLOW_SHA':self.source,'GITHUB_RUN_ID':'500',
            'GITHUB_WORKFLOW_REF':A.REPOSITORY+'/.github/workflows/parent-qualification.yml@refs/heads/main'}
        self.attempt = {'id':500,'run_attempt':1,'head_sha':self.source,'status':'in_progress',
            'conclusion':None,'path':self.refs['integration']['workflow_path'],'workflow_id':77,
            'event':'push','head_branch':'main','check_suite_id':91}
        self.job = {'name':'Common parent tests','status':'in_progress','conclusion':None,'steps':[]}
        self.now = NOW
        def obj(path):
            if path == 'branches/main': return {'name':'main','protected':True,'commit':{'sha':self.default}}
            self.assertIn(path,('actions/runs/500','actions/runs/500/attempts/1'))
            return deepcopy(self.attempt)
        def native_job(row,attempt,app,**kwargs):
            self.assertEqual(app,15368); self.assertEqual(kwargs,{'final_name':'Common parent tests'})
            return SimpleNamespace(status=row['status'],conclusion=row['conclusion'],job_id=9,
                started_at='2026-10-15T10:00:00Z',completed_at='2026-10-15T10:02:00Z')
        self.adapter = SimpleNamespace(_integrated_current=lambda run,app,now:(deepcopy(self.binding),deepcopy(self.refs)),
            _object=obj,_pages=lambda path,key:[deepcopy(self.job)],_job=native_job)
        self.adapter._commit = lambda oid:(self.default_tree if oid==self.default else self.tree,[])
        self.adapter.api = SimpleNamespace(immutable_tree=lambda oid:{'sha':oid,'truncated':False,
            'tree':[{'path':name,**entry} for name,entry in
                (self.local if oid==self.default_tree else self.current).items()]})
        checkout=C.execution.checkout_identity; full_tree=C.inputs.full_tree
        patches=[patch.dict(os.environ,self.native,clear=True),
            patch.object(C.execution,'checkout_identity',side_effect=lambda root:
                (self.default,self.default_tree) if root==C.ROOT else checkout(root)),
            patch.object(C.inputs,'full_tree',side_effect=lambda root,oid:
                self.local if root==C.ROOT else full_tree(root,oid)),
            patch.object(C,'integrated_controller_for_reuse',return_value='sha256:'+'1'*64),
            patch.object(C.producer,'_host_policy',return_value=SimpleNamespace(package_policy=lambda:self.package)),
            patch.object(C.execution,'execute',side_effect=AssertionError('no empty execution')),
            patch.object(C.execution,'capture_execution_environment',side_effect=AssertionError('no empty E'))]
        for item in patches:item.start();self.addCleanup(item.stop)

    def test_native_equal_tree_lookup_and_raw_validation_emit_no_execution_authority(self):
        value=self.C.lookup(self.event,self.native,self.adapter)
        self.assertFalse(value['reused']);self.assertTrue(value['no_execution'])
        proof=self.C.verify_no_execution(self.event,self.native,self.adapter,candidate=self.candidate)
        self.assertEqual(proof,value['proof']);self.assertIsNone(proof['execution'])
        self.assertFalse(proof['reusable']);self.assertFalse(proof['qualification'])
        self.assertEqual(proof['executed_suites'],[]);self.assertEqual(proof['reused_suites'],[])
        self.assertNotIn('environment',proof);self.assertNotIn('receipt_digest',proof)

    def test_actual_cli_empty_verification_emits_only_validation_and_scheduling_outputs(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory(prefix='overte-empty-parent-report-') as directory:
            directory=Path(directory); event=directory/'event.json'; output=directory/'output'
            report=directory/'result.json';event.write_text(json.dumps(self.event))
            with patch.dict(os.environ,{**self.native,'GITHUB_EVENT_PATH':str(event),'GITHUB_OUTPUT':str(output)},clear=True), \
                 patch.object(self.C.A,'Adapter',return_value=self.adapter):
                self.assertEqual(self.C.main(['--verify-empty','--candidate',str(self.candidate),
                    '--report',str(report)]),0)
            self.assertEqual(output.read_text(),'shared_reused=false\npackage_work=false\nno_execution=true\n')
            result=json.loads(report.read_bytes())
            self.assertFalse(result['reused']);self.assertTrue(result['no_execution'])
            self.assertIsNone(result['proof']['execution']);self.assertFalse(result['proof']['qualification'])

    def test_raw_nonempty_or_native_context_drift_cannot_use_scheduling_observation(self):
        before=self.C.no_execution_context(self.event,self.native,self.adapter)
        for mutation in ({'GITHUB_SHA':self.base},{'GITHUB_JOB':'foreign'},
                {'GITHUB_RUN_ATTEMPT':'2'},{'GITHUB_EVENT_NAME':'workflow_dispatch'}):
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                self.C.verify_no_execution(self.event,{**self.native,**mutation},self.adapter,candidate=self.candidate)
        (self.candidate/'native.cpp').write_text('actual product change\n')
        self.git('add','.');self.git('commit','-qm','Changed actual checkout')
        with self.assertRaises(ValueError):
            self.C.verify_no_execution(self.event,self.native,self.adapter,candidate=self.candidate)
        self.assertIsNone(before['execution'])

    def test_ordinary_changed_push_refuses_before_a_second_complete_source_lookup(self):
        from unittest.mock import Mock
        integrated=self.adapter._integrated_current
        self.adapter._integrated_current=Mock(side_effect=AssertionError('unnecessary duplicate source lookup'))
        self.adapter._commit=lambda oid:('9'*40 if oid==self.base else self.tree,[])
        with self.assertRaises(ValueError):
            self.C.no_execution_context(self.event,self.native,self.adapter)
        self.adapter._integrated_current.assert_not_called()
        self.adapter._integrated_current=integrated

    def test_missing_wrong_generation_source_or_full_inventory_declines_before_setup(self):
        for kind in ('tree','member','canonical','default','before','authority'):
            original_current=deepcopy(self.current);original_refs=deepcopy(self.refs);event=deepcopy(self.event)
            if kind=='tree':self.binding['merge_tree']='9'*40
            elif kind=='member':self.current['native.cpp']['sha']='9'*40
            elif kind=='canonical':self.local[self.C.producer.PLATFORM_PARENT_TEMPLATE]['sha']='9'*40
            elif kind=='default':self.refs['default_ref']='foreign'
            elif kind=='before':event['before']='9'*40
            else:self.native['GITHUB_REPOSITORY_ID']='42'
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                self.C.no_execution_context(event,self.native,self.adapter,candidate=self.candidate)
            self.current=original_current;self.refs=original_refs;self.binding['merge_tree']=self.tree
            self.native['GITHUB_REPOSITORY_ID']='1319052603'

    def test_native_completed_validation_step_is_mandatory_and_not_a_suite_pass(self):
        proof=self.C.no_execution_context(self.event,self.native,self.adapter,candidate=self.candidate)
        self.job.update(status='completed',conclusion='success',steps=[{
            'name':'Independently verify unchanged parent inputs','status':'completed','conclusion':'success',
            'started_at':'2026-10-15T10:00:30Z','completed_at':'2026-10-15T10:01:30Z'}])
        self.C.producer._completed_empty_parent(self.adapter,proof,self.native)
        for field,value in (('conclusion','failure'),('status','skipped'),('name','Execute host tests')):
            original=deepcopy(self.job)
            self.job['steps'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.C.producer._completed_empty_parent(self.adapter,proof,self.native)
            self.job=original

    def test_parent_aggregate_rederives_raw_proof_and_rejects_unexecuted_claims(self):
        import os
        self.native['GITHUB_JOB']='qualify-parent'
        self.job.update(status='completed',conclusion='success',steps=[{
            'name':'Independently verify unchanged parent inputs','status':'completed','conclusion':'success',
            'started_at':'2026-10-15T10:00:30Z','completed_at':'2026-10-15T10:01:30Z'}])
        needs={'route':{'result':'skipped','outputs':{}},'common-parent':{'result':'success','outputs':{}},
            'platform-tests':{'result':'skipped','outputs':{}}}
        self.C.producer.verify_platform_parent(self.candidate,self.event,self.native,self.adapter,needs)
        for name in ('route','platform-tests'):
            for record in ({'result':'success','outputs':{}},
                    {'result':'skipped','outputs':{'verified':'true'}}):
                changed=deepcopy(needs);changed[name]=record
                with self.subTest(name=name,record=record),self.assertRaises(ValueError):
                    self.C.producer.verify_platform_parent(self.candidate,self.event,self.native,self.adapter,changed)
        # The Android planner must accept *only* independently empty plans,
        # and produce no selected common or platform command inventory.
        target='android-main';self.binding['base_ref']=target
        self.event['ref']='refs/heads/'+target
        self.native.update(GITHUB_REF='refs/heads/'+target,GITHUB_JOB='route',
            GITHUB_WORKFLOW_REF=A.REPOSITORY+'/.github/workflows/parent-qualification.yml@refs/heads/'+target)
        with patch.dict(os.environ,self.native,clear=True), \
             patch.object(self.C.producer.source_admission,'shared_platform_supported',return_value=True), \
             patch.object(self.C.inputs,'load_registry',return_value={'suites':{}}):
            context=self.C.producer.current_platform_context(self.candidate,self.event,self.native,self.adapter)
            self.assertIsNone(context['selected']);self.assertIsNone(context['platform_partition'])
            self.assertEqual(context['package_plan']['host_mode'],'unchanged')
            needs['route']={'result':'success','outputs':self.C.producer.parent_route_outputs(context)}
            self.native['GITHUB_JOB']='qualify-parent'
            self.C.producer.verify_platform_parent(self.candidate,self.event,self.native,self.adapter,needs)

    def test_future_parent_checks_raw_inputs_before_node_and_never_executes_empty(self):
        import yaml
        data=yaml.safe_load((self.C.ROOT/self.C.producer.PLATFORM_PARENT_TEMPLATE).read_text())
        steps=data['jobs']['common-parent']['steps'];by_name={row['name']:row for row in steps}
        verify=by_name['Independently verify unchanged parent inputs']
        self.assertEqual(verify['if'],"steps.route.outputs.package_host_mode == 'unchanged'")
        self.assertIn('--verify-empty --candidate candidate',verify['run'])
        self.assertLess(steps.index(verify),steps.index(by_name['Set up Node.js']))
        self.assertIn("steps.route.outputs.package_host_mode != 'unchanged'",by_name['Set up Node.js']['if'])
        self.assertIn('false/false/true',by_name['Require an explicit reuse or actual-execution route']['run'])
    def documentation_native(self, target='main'):
        """Real Adapter + raw normal merge; original source closure is held above."""
        from types import SimpleNamespace
        C=self.C
        path=self.candidate/C.A.DOCUMENTATION_PUSH_WORKFLOW
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((C.ROOT/C.A.DOCUMENTATION_PUSH_WORKFLOW).read_bytes())
        canonical=self.candidate/C.producer.PLATFORM_PARENT_TEMPLATE
        canonical.parent.mkdir(parents=True,exist_ok=True);canonical.write_bytes((C.ROOT/C.producer.PLATFORM_PARENT_TEMPLATE).read_bytes())
        shared=(json.dumps({'schema':1,'platform':'shared','suites':[]},indent=2)+'\n').encode()
        profile=shared
        if target in {'android-phone','android-vr-pico'}:
            values=json.loads((C.ROOT/'.github/android-owner-transfer.json').read_bytes())['profiles'][target]['required_suites']
            profile=(json.dumps({'schema':1,'platform':'android','suites':values},indent=2)+'\n').encode()
        self.assertEqual(C.source_admission.blob_id(profile),C.source_admission.TARGET_PROFILES[target])
        profile_path=self.candidate/C.source_admission.PROFILE
        profile_path.parent.mkdir(parents=True,exist_ok=True);profile_path.write_bytes(profile)
        self.git('add','.');self.git('commit','--allow-empty','-qm','Complete unchanged documentation fixture')
        self.base=self.git('rev-parse','HEAD');self.tree=self.git('rev-parse','HEAD^{tree}')
        head=self.git('commit-tree',self.tree,'-p',self.base,'-m','Retained documentation history')
        self.source=self.git('commit-tree',self.tree,'-p',self.base,'-p',head,'-m','Normal unchanged documentation merge')
        self.git('checkout','-q','--detach',self.source)
        self.current=C.inputs.full_tree(self.candidate,self.source)
        self.local=deepcopy(self.current)
        self.default=self.source if target=='main' else 'd'*40
        self.default_tree=self.tree if target=='main' else 'e'*40
        if target!='main':self.local[C.source_admission.PROFILE]={'mode':'100644','type':'blob','sha':C.source_admission.blob_id(shared)}
        self.event.update(ref='refs/heads/'+target,before=self.base,after=self.source)
        self.native.update(GITHUB_REF='refs/heads/'+target,GITHUB_JOB='documentation-source',
            GITHUB_SHA=self.source,GITHUB_WORKFLOW_SHA=self.source,
            GITHUB_WORKFLOW_REF=A.REPOSITORY+'/'+A.DOCUMENTATION_PUSH_WORKFLOW+'@refs/heads/'+target)
        self.attempt.update(id=500,workflow_id=77,check_suite_id=91,run_attempt=1,status='in_progress',conclusion=None,
            path=A.DOCUMENTATION_PUSH_WORKFLOW,head_sha=self.source,head_branch=target,
            repository={'id':1319052603,'full_name':A.REPOSITORY},head_repository={'id':1319052603,'full_name':A.REPOSITORY},
            run_started_at='2026-10-15T10:00:01Z')
        self.job={'id':9,'run_id':500,'run_attempt':1,'head_sha':self.source,
            'name':'Authenticate original documentation owner','status':'in_progress','conclusion':None,
            'started_at':'2026-10-15T10:00:01Z','completed_at':None,'steps':[],
            'check_run_url':'https://api.github.com/'+A.PREFIX+'/check-runs/9'}
        repo={'id':1319052603,'full_name':A.REPOSITORY}
        pr={'id':1700,'number':17,'state':'closed','merged':True,'merge_commit_sha':self.source,
            'merged_at':'2026-10-15T10:00:00Z','closed_at':'2026-10-15T10:00:00Z',
            'base':{'ref':target,'sha':self.base,'repo':repo},
            'head':{'ref':'task/main/documentation-history','sha':head,'repo':repo}}
        outer=self
        class API:
            def __init__(self):self.calls=[];self.mutate=lambda endpoint,value:value
            def json(self,endpoint):
                self.calls.append(endpoint)
                suffix=endpoint[len(A.PREFIX):].lstrip('/').split('?',1)[0]
                if not suffix:value={**repo,'default_branch':'main'}
                elif suffix in {'actions/runs/500','actions/runs/500/attempts/1'}:value=outer.attempt
                elif suffix in {'actions/workflows/77','actions/workflows/documentation-push-owner.yml'}:
                    value={'id':77,'path':A.DOCUMENTATION_PUSH_WORKFLOW,'state':'active'}
                elif suffix.startswith('branches/'):
                    branch=unquote(suffix[len('branches/'):]);outer.assertIn(branch,{'main',target})
                    value={'name':branch,'protected':True,'commit':{'sha':outer.default if branch=='main' else outer.source}}
                elif suffix.startswith('git/ref/heads/'):
                    branch=unquote(suffix[len('git/ref/heads/'):]);outer.assertIn(branch,{'main',target})
                    value={'ref':'refs/heads/'+branch,'object':{'type':'commit','sha':outer.default if branch=='main' else outer.source}}
                elif suffix=='check-suites/91':value={'id':91,'head_sha':outer.source,'app':{'id':15368},'repository':repo}
                elif suffix=='check-runs/9':value={'id':9,'head_sha':outer.source,'app':{'id':15368},'check_suite':{'id':91},
                    **{key:outer.job[key] for key in ('name','status','conclusion','started_at','completed_at')}}
                elif suffix=='actions/runs/500/attempts/1/jobs':value={'total_count':1,'jobs':[outer.job]}
                elif suffix=='commits/'+outer.source+'/pulls':value=[{key:pr[key] for key in ('id','number','state','base','head')}]
                elif suffix.startswith('git/commits/'):
                    revision=suffix.rsplit('/',1)[1]
                    if revision==outer.default and target!='main':tree,parents=outer.default_tree,[]
                    else:
                        tree=outer.git('rev-parse',revision+'^{tree}')
                        parents=outer.git('show','-s','--format=%P',revision).split()
                    value={'sha':revision,'tree':{'sha':tree},'parents':[{'sha':item} for item in parents]}
                else:raise AssertionError('unexpected documentation fake native endpoint')
                return self.mutate(endpoint,deepcopy(value))
            def integrated_pr(self,number):
                outer.assertEqual(number,17);self.calls.append(A.PREFIX+'/pulls/17')
                return self.mutate(A.PREFIX+'/pulls/17',deepcopy(pr))
            def immutable_tree(self,oid):
                outer.assertIn(oid,{outer.tree,outer.default_tree})
                value={'sha':oid,'truncated':False,'tree':[{'path':name,**entry} for name,entry in
                    (outer.local if oid==outer.default_tree else outer.current).items()]}
                return self.mutate(A.PREFIX+'/git/trees/'+oid+'?recursive=1',deepcopy(value))
        api=API();self.adapter=A.Adapter(api)
        return api

    def test_documentation_shared_fixture_is_independent_of_checkout_platform(self):
        import os
        read_bytes=Path.read_bytes
        def branch_bytes(path):
            if path==self.C.ROOT/self.C.source_admission.PROFILE:
                return (json.dumps({'schema':1,'platform':'android','suites':[]},indent=2)+'\n').encode()
            return read_bytes(path)
        with patch.object(Path,'read_bytes',branch_bytes):
            self.documentation_native('main')
            with patch.dict(os.environ,self.native,clear=True):
                result=self.C.verify_no_execution(self.event,self.native,self.adapter,
                    candidate=self.candidate,clock=lambda:NOW)
        self.assertEqual(result['authority'],'none')
        self.assertFalse(result['qualification']);self.assertIsNone(result['execution'])

    def test_documentation_four_native_targets_verify_raw_empty_without_original_E_or_primary_wait(self):
        import os
        for target in sorted(A.DOCUMENTATION_PUSH_BRANCHES):
            with self.subTest(target=target):
                api=self.documentation_native(target)
                with patch.dict(os.environ,self.native,clear=True):
                    scheduling=self.C.lookup(self.event,self.native,self.adapter,clock=lambda:NOW)
                    result=self.C.verify_no_execution(self.event,self.native,self.adapter,candidate=self.candidate,clock=lambda:NOW)
                self.assertFalse(scheduling['reused']);self.assertTrue(scheduling['no_execution'])
                self.assertEqual(result,scheduling['proof']);self.assertEqual(result['authority'],'none')
                self.assertFalse(result['reusable']);self.assertFalse(result['qualification'])
                self.assertIsNone(result['execution']);self.assertEqual(result['executed_suites'],[])
                self.assertEqual(result['reused_suites'],[]);self.assertNotIn('environment',result)
                self.assertFalse(any('/actions/workflows/350930890/runs' in endpoint or '/actions/workflows/330551824/runs' in endpoint
                    for endpoint in api.calls),'documentation must not wait for or reinterpret a parallel primary push')

    def test_documentation_empty_native_and_complete_source_bookends_fail_closed(self):
        import os
        for kind in ('job','app','attempt','recipe','missing-member','raw-change','late-job','late-current'):
            with self.subTest(kind=kind):
                api=self.documentation_native();reads=0
                if kind=='job':self.job['name']='Common parent tests'
                elif kind=='attempt':self.attempt['run_attempt']=2
                elif kind=='recipe':self.local[A.DOCUMENTATION_PUSH_WORKFLOW]['sha']='f'*40
                elif kind=='raw-change':
                    (self.candidate/'native.cpp').write_text('actual changed content\n')
                    self.git('add','.');self.git('commit','-qm','Actual unmatched documentation candidate')
                def mutate(endpoint,value):
                    nonlocal reads
                    if kind=='app' and '/check-suites/' in endpoint:value['app']['id']=42
                    if kind=='missing-member' and '?recursive=1' in endpoint:
                        value['tree']=[row for row in value['tree'] if row['path']!='native.cpp']
                    if kind=='late-job' and '/check-runs/9' in endpoint:
                        reads+=1
                        if reads>1:value['conclusion']='success';value['status']='completed'
                    if kind=='late-current' and '/git/ref/heads/main' in endpoint:
                        reads+=1
                        if reads>2:value['object']['sha']='f'*40
                    return value
                api.mutate=mutate
                with patch.dict(os.environ,self.native,clear=True),self.assertRaises(ValueError):
                    self.C.verify_no_execution(self.event,self.native,self.adapter,candidate=self.candidate,clock=lambda:NOW)




class OptionalParentScheduleTests(unittest.TestCase):
    generation_name = 'protected-producer-original-default-v1'
    setUp = MainConsumerTests.setUp

    def schedule(self):
        self.environment['GITHUB_JOB'] = 'common-parent'
        self.tree[self.module.producer.PLATFORM_PARENT_TEMPLATE] = deepcopy(
            self.tree['.github/workflows/parent-qualification.yml'])
        self.previous[self.module.producer.PLATFORM_PARENT_TEMPLATE] = deepcopy(
            self.tree[self.module.producer.PLATFORM_PARENT_TEMPLATE])
        return self.module.unavailable_parent_schedule(
            self.event, self.environment, self.adapter, clock=lambda: NOW)

    def test_actual_native_schedule_has_no_test_or_qualification_authority(self):
        value = self.schedule()
        self.assertEqual(value['kind'], 'optional-parent-qualification-schedule-v1')
        self.assertFalse(value['reusable'])
        self.assertFalse(value['qualification'])
        self.assertIsNone(value['execution'])
        self.assertEqual(value['executed_suites'], [])
        self.assertEqual(value['reused_suites'], [])
        with patch.object(self.module, 'verify_main', side_effect=ValueError('missing original proof')):
            result = self.module.lookup(self.event, self.environment, self.adapter, clock=lambda: NOW)
        self.assertFalse(result['reused'])
        self.assertEqual(result['optional_qualification'], value)

    def test_stale_attempt_recipe_source_and_forced_push_cannot_schedule(self):
        self.schedule()
        for mapping, key, value in ((self.environment, 'GITHUB_RUN_ATTEMPT', '2'),
                (self.environment, 'GITHUB_SHA', 'e'*40), (self.event, 'forced', True),
                (self.event, 'before', 'e'*40),
                (self.tree, '.github/workflows/parent-qualification.yml',
                    {'mode':'100644','type':'blob','sha':'e'*40})):
            with self.subTest(key=key), patch.dict(mapping, {key: value}), self.assertRaises(ValueError):
                self.schedule()
        def mutate(endpoint, value):
            if endpoint.endswith('/actions/runs/500'):
                value['run_attempt'] = 2
            return value
        self.api.mutate = mutate
        with self.assertRaises(ValueError):
            self.schedule()


class BooleanOptionalParentScheduleTests(OptionalParentScheduleTests):
    generation_name = 'protected-producer-original-default-boolean-v1'


class CurrentParentTransitionTests(unittest.TestCase):
    """Actual native API and materialized import graph; selection is a fixed seam.

    Host-selection tests own the complete product/negative-reader decision.
    These tests retain the real API/ordinary-file/current-controller authority.
    """
    def setUp(self):
        from types import SimpleNamespace
        import postmerge as C
        self.C=C
        spec=importlib.util.spec_from_file_location('current_parent_source_fixture',Path(__file__).with_name('source-admission-test.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.source=s=module.CurrentParentImportTests('runTest');s.setUp();self.addCleanup(s.doCleanups)
        self.root=s.root
        # Copy the actual reviewed finite source graph as data. No historical
        # or fixture checkout repository module is ever imported/executed.
        # This fixture models current main even when its source checkout is a
        # permanent platform branch, so both snapshots retain main's profile.
        shared_profile=(json.dumps({'schema':1,'platform':'shared','suites':[]},indent=2)+'\n').encode()
        self.assertEqual(C.source_admission.blob_id(shared_profile),C.source_admission.SHARED_PROFILE)
        for name in list(s.bodies):
            raw=shared_profile if name==C.source_admission.PROFILE else (C.ROOT/name).read_bytes()
            s.bodies[name]=raw;s.default[name]=C.source_admission.ordinary(C.source_admission.blob_id(raw),
                '100755' if name=='tests/run-project-tests.py' else '100644')
            path=s.root/name;path.write_bytes(raw)
        s.base=deepcopy(s.default)
        s.base['tools/test-evidence/execution.py']=C.source_admission.ordinary('f'*40)
        f=IntegratedSourceTests('runTest');f.setUp()
        self.case,self.adapter,self.api=f.case,f.adapter,f.api
        c=self.case;c.originals[c.binding['base_sha']]=('6'*40,['7'*40])
        s.default_id=c.integrated;s.base_id=c.binding['base_sha'];s.head_id=c.binding['head_sha']
        s.env.update(GITHUB_SHA=c.integrated,GITHUB_WORKFLOW_SHA=c.integrated)
        s.event.update(before=c.binding['base_sha'],after=c.integrated)
        s.run.update(head_sha=c.integrated);s.job.update(head_sha=c.integrated)
        self.event,self.environment=s.event,s.env
        old_json=self.api.json
        def json_api(endpoint):
            path=endpoint[len(A.PREFIX):].lstrip('/').split('?',1)[0]
            if path in {'actions/runs/500/attempts/1/jobs','check-runs/5500'}:
                return s.source_api.get(endpoint[len(A.PREFIX)+1:])
            return old_json(endpoint)
        self.api.json=json_api
        self.api.immutable_tree=lambda oid:{'sha':oid,'truncated':False,
            'tree':[{'path':path,**entry} for path,entry in (s.base if oid=='6'*40 else s.default).items()]}
        self.registry=C.inputs.load_registry(C.ROOT/'.github/test-suites.json')
        self.policy=C.producer._host_policy();self.package=self.policy.package_policy()
        self.package_wrapper=SimpleNamespace(**{name:getattr(self.package,name) for name in
            ('validate_tree_wiring','load','select','_policy_inputs')},validate_wiring=lambda _:C.producer.PLATFORM_GENERATION,
            candidate_plan=lambda *_:{'host_mode':'full'})
        quick=[name for name,row in self.registry['suites'].items()
            if row['layer']=='quick' and name not in self.policy.PRODUCT_QUICK_SUITES]
        self.selected={'suites':quick,'full_host':False,'include_platform':False,'reason':'reviewed-ci-only-inputs'}
        self.enterContext(patch.object(self.policy,'package_policy',return_value=self.package_wrapper))
        self.enterContext(patch.object(self.policy,'select',side_effect=lambda *_args,**_kwargs:deepcopy(self.selected)))
        self.enterContext(patch.object(C.producer,'_host_policy',return_value=self.policy))
        self.enterContext(patch.object(C.execution,'checkout_identity',return_value=(c.integrated,c.binding['merge_tree'])))
        self.enterContext(patch.object(C.inputs,'full_tree',side_effect=lambda *_:deepcopy(s.default)))
        self.enterContext(patch.object(C,'_source_qualified',return_value=True))
        self.enterContext(patch.object(C.execution,'execute',side_effect=AssertionError('no duplicate execution/E')))
        self.enterContext(patch.object(C.execution,'capture_execution_environment',side_effect=AssertionError('no unused E')))

    def schedule(self):
        return self.C.current_parent_schedule(self.event,self.environment,self.adapter,root=self.root,clock=lambda:NOW)

    def test_current_main_fixture_has_shared_profile_independent_of_source_checkout(self):
        profile=self.C.source_admission.PROFILE
        expected=self.C.source_admission.ordinary(self.C.source_admission.SHARED_PROFILE)
        self.assertEqual(self.source.base[profile],expected)
        self.assertEqual(self.source.default[profile],expected)
        raw=(self.root/profile).read_bytes()
        self.assertEqual(self.C.source_admission.blob_id(raw),expected['sha'])
        self.assertEqual(json.loads(raw),{'schema':1,'platform':'shared','suites':[]})

    def test_current_main_transition_has_no_original_reuse_and_final_independently_rederives_partial_state(self):
        value=self.schedule()
        self.assertEqual(value['current_imports']['authority'],'current-imports-only')
        self.assertEqual(value['selection'],self.selected)
        self.assertEqual(value['executed_suites'],[]);self.assertEqual(value['reused_suites'],[])
        self.assertFalse(value['qualification']);self.assertIsNone(value['execution'])
        with patch.object(self.C,'verify_main',side_effect=ValueError('original B differs')):
            result=self.C.lookup(self.event,self.environment,self.adapter,root=self.root,clock=lambda:NOW)
        self.assertFalse(result['reused']);self.assertEqual(result['optional_qualification'],value)
        self.environment['GITHUB_JOB']='qualify-parent';self.source.job['name']='Qualify exact parent'
        needs={'route':{'result':'skipped','outputs':{}},'common-parent':{'result':'success'},
            'platform-tests':{'result':'skipped','outputs':{}}}
        with patch.object(self.C.producer,'ROOT',self.root):
            self.C.producer.verify_platform_parent(self.root,self.event,self.environment,self.adapter,needs)
            with patch.dict(self.selected,{'full_host':True}),self.assertRaises(ValueError):
                self.C.producer.verify_platform_parent(self.root,self.event,self.environment,self.adapter,needs)
            for key,row in (('common-parent',{'result':'failure'}),('platform-tests',{'result':'success','outputs':{}})):
                with self.subTest(key=key),patch.dict(needs,{key:row}),self.assertRaises(ValueError):
                    self.C.producer.verify_platform_parent(self.root,self.event,self.environment,self.adapter,needs)
        self.C.execution.execute.assert_not_called();self.C.execution.capture_execution_environment.assert_not_called()

    def test_boolean_installed_tuple_reaches_current_parent_without_original_execution_authority(self):
        caller='.github/workflows/repository-checks.yml'
        source='tools/repository-checks/workflows/producers/repository-checks.yml'
        raw=(self.C.ROOT/source).read_bytes()
        self.source.default[caller]=self.C.source_admission.ordinary(self.C.source_admission.blob_id(raw))
        self.source.bodies[caller]=raw
        (self.source.root/caller).write_bytes(raw)
        self.package_wrapper.validate_wiring=lambda _:'protected-producer-original-default-boolean-v1'
        value=self.schedule()
        self.assertEqual(value['current_imports']['authority'],'current-imports-only')
        self.assertEqual(value['executed_suites'],[]);self.assertEqual(value['reused_suites'],[])
        self.assertFalse(value['qualification']);self.assertIsNone(value['execution'])
        self.C.execution.execute.assert_not_called()

    def lifecycle_transition(self, before=None, after=None):
        """Actual reviewed definitions and authenticated bounded Git-blob bytes."""
        if before is None:
            before=deepcopy(self.registry)
            del before['suites']['native-owner-lifecycle']
        else:before=deepcopy(before)
        after=deepcopy(self.registry) if after is None else deepcopy(after)
        path='.github/test-suites.json'
        previous=(json.dumps(before,indent=2)+'\n').encode()
        current=(json.dumps(after,indent=2)+'\n').encode()
        previous_sha=self.C.source_admission.blob_id(previous)
        self.source.base[path]=self.C.source_admission.ordinary(previous_sha)
        self.source.default[path]=self.C.source_admission.ordinary(self.C.source_admission.blob_id(current))
        self.source.bodies[path]=current;(self.root/path).write_bytes(current)
        self.registry_blobs={previous_sha:previous}
        def request(endpoint,maximum,**_options):
            self.assertEqual(maximum,100_000)
            self.api.calls.append(endpoint)
            identity=endpoint.removeprefix(A.PREFIX+'/git/blobs/')
            self.assertIn(identity,self.registry_blobs)
            raw=self.registry_blobs[identity]
            return json.dumps({'sha':identity,'size':len(raw),'encoding':'base64',
                'content':base64.b64encode(raw).decode()}).encode()
        client=A.GitHubReadOnly();client._request=request
        self.api.immutable_blob=client.immutable_blob
        runner='tests/run-project-tests.py'
        self.assertEqual(self.source.default[runner]['mode'],'100755')
        self.source.base[runner]=self.C.source_admission.ordinary(
            self.C.source_admission.blob_id(b'previous reviewed CI runner\n'),'100755')
        # This actual source preparation script is ordinary 644 in both Git
        # trees. Its workflow chmod does not grant a new executable exception.
        preparation='tools/repository-checks/android-host-prepare.sh'
        raw=(self.C.ROOT/preparation).read_bytes()
        self.source.default[preparation]=self.C.source_admission.ordinary(self.C.source_admission.blob_id(raw))
        self.source.base[preparation]=self.C.source_admission.ordinary(
            self.C.source_admission.blob_id(b'previous reviewed Android host preparation\n'))
        leaf=self.root/preparation;leaf.parent.mkdir(parents=True,exist_ok=True);leaf.write_bytes(raw)
        return before,after

    def test_monotonic_lifecycle_and_preserved_ci_runner_skip_optional_execution_and_final_parent_rederives(self):
        before,after=self.lifecycle_transition()
        self.assertEqual((len(before['suites']),len(after['suites'])),(60,61))
        self.assertEqual({name:row for name,row in after['suites'].items()
            if name!='native-owner-lifecycle'},before['suites'])
        self.assertEqual(after['control_inputs'],before['control_inputs'])
        value=self.schedule()
        self.assertFalse(value['qualification'] or value['reusable'])
        self.assertEqual(value['authority'],'none');self.assertIsNone(value['execution'])
        self.assertEqual(value['executed_suites'],[]);self.assertEqual(value['reused_suites'],[])
        self.assertEqual(value['selection'],self.selected)
        with patch.object(self.C,'verify_main',side_effect=ValueError('original source has no reusable E')):
            result=self.C.lookup(self.event,self.environment,self.adapter,root=self.root,clock=lambda:NOW)
        self.assertFalse(result['reused']);self.assertEqual(result['optional_qualification'],value)
        self.environment['GITHUB_JOB']='qualify-parent';self.source.job['name']='Qualify exact parent'
        needs={'route':{'result':'skipped','outputs':{}},'common-parent':{'result':'success','outputs':{}},
            'platform-tests':{'result':'skipped','outputs':{}}}
        with patch.object(self.C.producer,'ROOT',self.root):
            # Exercise the real aggregate fallback, including provisional
            # controller rejection and independent current-parent bookends.
            self.C.producer.verify_platform_parent(self.root,self.event,self.environment,self.adapter,needs)
            for state in ('failure','skipped','cancelled',None):
                changed=deepcopy(needs);changed['common-parent']['result']=state
                with self.subTest(common=state),self.assertRaises(ValueError):
                    self.C.producer.verify_platform_parent(self.root,self.event,self.environment,self.adapter,changed)
            missing=deepcopy(needs);del missing['common-parent']
            with self.assertRaises(ValueError):
                self.C.producer.verify_platform_parent(self.root,self.event,self.environment,self.adapter,missing)
        self.C.execution.execute.assert_not_called();self.C.execution.capture_execution_environment.assert_not_called()

    def test_lifecycle_transition_rejects_changed_definitions_controls_owner_removal_and_unknown_owner(self):
        original=deepcopy(self.registry)
        for change in ('quick-command','quick-closure','host-command','controls','remove','remove-lifecycle','unknown',
                       'new-command','new-context','new-scope','new-closure','new-layer','order'):
            before=deepcopy(original);del before['suites']['native-owner-lifecycle']
            after=deepcopy(original)
            if change=='quick-command':after['suites']['producer-proof']['command'].append('--changed')
            elif change=='quick-closure':after['suites']['producer-proof']['closure']['required'].append('unreviewed.py')
            elif change=='host-command':after['suites']['safe-landing-lifecycle']['command'].append('--changed')
            elif change=='controls':after['control_inputs'].append('unreviewed-control.json')
            elif change=='remove':del after['suites']['safe-landing-lifecycle']
            elif change=='remove-lifecycle':
                before=deepcopy(original);del after['suites']['native-owner-lifecycle']
            elif change=='unknown':
                for registry in (before,after):
                    registry['suites']['unknown-owner']=registry['suites'].pop('safe-landing-lifecycle')
            elif change=='new-command':after['suites']['native-owner-lifecycle']['command'].append('--changed')
            elif change=='new-context':after['suites']['native-owner-lifecycle']['environment']='unknown-host'
            elif change=='new-scope':after['suites']['native-owner-lifecycle']['scope']='candidate'
            elif change=='new-closure':after['suites']['native-owner-lifecycle']['closure']['required'].pop()
            elif change=='new-layer':after['suites']['native-owner-lifecycle']['layer']='quick'
            else:after['suites']={name:after['suites'][name] for name in reversed(after['suites'])}
            self.lifecycle_transition(before,after)
            with self.subTest(change=change),self.assertRaises(ValueError):self.schedule()
        self.C.execution.execute.assert_not_called();self.C.execution.capture_execution_environment.assert_not_called()

    def test_lifecycle_transition_rejects_registry_alias_missing_and_unauthenticated_old_blob(self):
        self.lifecycle_transition()
        path='.github/test-suites.json'
        for side in (self.source.base,self.source.default):
            original=deepcopy(side[path])
            for mode in ('100755','120000','160000'):
                side[path]={**original,'mode':mode,'type':'commit' if mode=='160000' else 'blob'}
                with self.subTest(side='base' if side is self.source.base else 'current',mode=mode),self.assertRaises(ValueError):
                    self.schedule()
            side[path]=original
        original=deepcopy(self.source.base[path]);del self.source.base[path]
        with self.assertRaises(ValueError):self.schedule()
        self.source.base[path]=original
        self.registry_blobs[original['sha']]=b'not the immutable original registry'
        with self.assertRaises(ValueError):self.schedule()
        with patch.object(self.api,'immutable_blob',side_effect=A.ApiError('original Git blob unavailable')):
            with self.assertRaises(ValueError):self.schedule()
            with patch.object(self.C,'verify_main',side_effect=ValueError('no original proof')):
                value=self.C.lookup(self.event,self.environment,self.adapter,root=self.root,clock=lambda:NOW)
            self.assertFalse(value['reused']);self.assertNotIn('optional_qualification',value)

    def test_lifecycle_transition_rejects_executable_mode_changes_aliases_unknown_executables_and_product(self):
        self.lifecycle_transition()
        base,current=deepcopy(self.source.base),deepcopy(self.source.default)
        runner='tests/run-project-tests.py'
        for change in ('mode-change','alias','missing','unknown-executable','product'):
            self.source.base=deepcopy(base);self.source.default=deepcopy(current)
            if change=='mode-change':self.source.base[runner]['mode']='100644'
            elif change=='alias':self.source.default[runner]['mode']='120000'
            elif change=='missing':del self.source.base[runner]
            elif change=='unknown-executable':
                path='tools/branch-cleanup/unknown-executable.py'
                self.source.base[path]=self.C.source_admission.ordinary('a'*40,'100755')
                self.source.default[path]=self.C.source_admission.ordinary('b'*40,'100755')
            else:self.source.default['interface/src/unreviewed.cpp']=self.C.source_admission.ordinary('a'*40)
            with self.subTest(change=change),self.assertRaises(ValueError):self.schedule()
        self.source.base=base;self.source.default=current
        self.C.execution.execute.assert_not_called();self.C.execution.capture_execution_environment.assert_not_called()

    def test_lifecycle_transition_retains_current_native_and_final_source_bookends(self):
        self.lifecycle_transition()
        self.schedule()
        original=self.adapter._integrated_current;calls=[]
        def changed(*args,**kwargs):
            binding,refs=original(*args,**kwargs);calls.append(True)
            return binding,({**refs,'default':'f'*40} if len(calls)>1 else refs)
        with patch.object(self.adapter,'_integrated_current',side_effect=changed),self.assertRaises(ValueError):self.schedule()
        self.assertEqual(len(calls),2)
        for key,value in (('GITHUB_RUN_ATTEMPT','2'),('GITHUB_SHA','f'*40),('GITHUB_REPOSITORY','overte-org/overte')):
            with self.subTest(key=key),patch.dict(self.environment,{key:value}),self.assertRaises(ValueError):self.schedule()
        self.C.execution.execute.assert_not_called();self.C.execution.capture_execution_environment.assert_not_called()

    def partial_selection(self):
        omitted={'producer-proof','python-test-runner','release-bundle','project-coverage','native-registration'}
        names=[name for name in self.selected['suites'] if name not in omitted]
        self.assertEqual(len(names),32)
        return {'suites':names,'full_host':False,'include_platform':False,
            'reason':'protected-ci-dependencies','affected':{
                'dependency_schema':2,'target':'main','required':list(names)}}

    def test_current_documentation_and_lock_partial_selection_declines_without_execution_or_pass(self):
        self.selected=self.partial_selection()
        # The existing current-main import boundary authenticates D itself;
        # neither the old B lock nor the original runtime is adopted as D/E.
        self.source.base=deepcopy(self.source.default)
        self.source.base['.github/android-orchestration.json']=self.C.source_admission.ordinary('f'*40)
        doc='docs/portal/testing/github-actions.md'
        self.source.base[doc]=self.C.source_admission.ordinary('a'*40)
        self.source.default[doc]=self.C.source_admission.ordinary('b'*40)
        value=self.schedule()
        self.assertEqual(value['selection'],self.selected)
        self.assertEqual(value['current_imports']['authority'],'current-imports-only')
        self.assertEqual(value['executed_suites'],[]);self.assertEqual(value['reused_suites'],[])
        self.assertFalse(value['qualification'] or value['reusable']);self.assertIsNone(value['execution'])
        self.environment['GITHUB_JOB']='qualify-parent';self.source.job['name']='Qualify exact parent'
        needs={'route':{'result':'skipped','outputs':{}},'common-parent':{'result':'success'},
            'platform-tests':{'result':'skipped','outputs':{}}}
        with patch.object(self.C.producer,'ROOT',self.root):
            self.C.producer.verify_platform_parent(self.root,self.event,self.environment,self.adapter,needs)
        self.C.execution.execute.assert_not_called();self.C.execution.capture_execution_environment.assert_not_called()

    def test_partial_optional_selection_rejects_foreign_scope_order_duplicates_and_product_names(self):
        self.selected=self.partial_selection()
        baseline=deepcopy(self.selected)
        for change in ('reason','schema','schema-type','target','required','reverse','duplicate','unknown','product','empty'):
            self.selected=deepcopy(baseline)
            if change=='reason':self.selected['reason']='unreviewed-partial-inputs'
            elif change=='schema':self.selected['affected']['dependency_schema']=1
            elif change=='schema-type':self.selected['affected']['dependency_schema']='2'
            elif change=='target':self.selected['affected']['target']='apple-main'
            elif change=='required':self.selected['affected']['required'].pop()
            else:
                names=self.selected['suites']
                if change=='reverse':names.reverse()
                elif change=='duplicate':names.append(names[0])
                elif change=='unknown':names.append('unknown-owner')
                elif change=='product':names.append('device-control-plane-full')
                else:names.clear()
                self.selected['affected']['required']=list(names)
            with self.subTest(change=change),self.assertRaises(ValueError):self.schedule()

    def test_partial_optional_selection_still_requires_no_platform_additions_or_package_owner(self):
        self.selected=self.partial_selection()
        for key,value in (('full_host',True),('include_platform',True),
                ('additional_suites',['new-command']),('platform_suites',['platform-command'])):
            with self.subTest(key=key),patch.dict(self.selected,{key:value}),self.assertRaises(ValueError):
                self.schedule()
        with patch.object(self.package_wrapper,'select',return_value={
                'host_mode':'full','tool_projects':[],'package_set':['browser']}),self.assertRaises(ValueError):
            self.schedule()
        self.C.execution.execute.assert_not_called();self.C.execution.capture_execution_environment.assert_not_called()

    def test_full_extra_platform_package_unknown_and_stale_current_source_cannot_decline(self):
        for key,value in (('full_host',True),('include_platform',True),
                ('suites',list(self.registry['suites'])),('additional_suites',['new-command'])):
            with self.subTest(key=key),patch.dict(self.selected,{key:value}),self.assertRaises(ValueError):self.schedule()
        for path,entry in (('script-archive/marketplace/S3Server/package-lock.json',self.C.source_admission.ordinary('a'*40)),
                ('tools/test-evidence/new-unknown.py',self.C.source_admission.ordinary('a'*40)),
                ('tools/test-evidence/execution.py',{'mode':'120000','type':'blob','sha':'a'*40})):
            with self.subTest(path=path),patch.dict(self.source.default,{path:entry}),self.assertRaises(ValueError):self.schedule()
        for key,value in (('GITHUB_SHA','f'*40),('GITHUB_JOB','route'),
                ('GITHUB_REPOSITORY','overte-org/overte'),('GITHUB_RUN_ATTEMPT','2')):
            with self.subTest(key=key),patch.dict(self.environment,{key:value}),self.assertRaises(ValueError):self.schedule()
        def changed(endpoint,value):
            if endpoint.endswith('/git/ref/heads/main'):
                value['object']['sha']='f'*40
            return value
        self.api.mutate=changed
        with self.assertRaises(ValueError):self.schedule()


class LeafOriginalCommonTests(unittest.TestCase):
    """Real schema4/hash/API verification; source reconstruction uses fixed seams.

    Original B/D projection validation remains covered by ci-profile-test. No
    consumer environment capture or candidate command is substituted for proof.
    """
    def setUp(self):
        f = MainConsumerTests('runTest')
        f.generation_name = 'protected-producer-original-default-v1'
        f.setUp(); self.addCleanup(f.doCleanups)
        self.f, self.C, self.c, self.adapter = f, f.module, f.case, f.adapter
        C, c = self.C, self.c
        run = f.adapter.capture_integrated(500, c.plan, c.policy, now=NOW).observations[0].run
        self.original_run = run
        self.profile = deepcopy(C.producer.selection_profile.return_value)
        c.binding['base_ref'] = 'apple-ios'
        c.push.update(workflow_id=330551824, path='.github/workflows/project-tests.yml', head_branch='apple-ios')
        c.originals['6'*40] = ('c'*40, ['7'*40])
        f.tree[C.producer.PLATFORM_TEMPLATE] = deepcopy(f.tree['.github/workflows/project-tests.yml'])
        self.candidate = Path('/immutable-leaf-candidate')
        C.execution.checkout_identity.side_effect = lambda path: ((c.integrated, c.binding['merge_tree'])
            if path == self.candidate else ('6'*40, 'c'*40))
        f.environment.update(GITHUB_REF='refs/heads/apple-ios', GITHUB_JOB='project-tests',
            GITHUB_WORKFLOW_REF=A.REPOSITORY+'/.github/workflows/project-tests.yml@refs/heads/apple-ios')
        f.event['ref'] = 'refs/heads/apple-ios'
        self.source = deepcopy(FIXTURES.RetainedSourceProtocolTests().fixture().context.protected_source)
        self.source['binding'].update(source=c.binding['merge_sha'], git_context=f.git,
            selection=self.profile['selection'], registry=P.digest(f.registry))
        self.receipt = deepcopy(f.receipt)
        self.receipt.update(schema=4, protected_source=deepcopy(self.source))
        self.receipt = FIXTURES.signed(self.receipt, 'receipt_digest')
        c.pp = replace(c.pp, required_execution_schema=4)
        c.policy = replace(c.policy, producer=c.pp)
        C._policy.return_value = c.plan, c.policy
        c.aggregate['results']['shared-host']['receipt'] = self.receipt
        c.add_run(replace(run, final_publisher=replace(run.final_publisher,
            receipt_sha256=hashlib.sha256(P.canonical(self.receipt)).hexdigest())))
        c.runs[100]['pull_requests'] = []
        self.job = {'id':5500, 'run_id':500, 'run_attempt':1, 'head_sha':c.integrated,
            'name':'Shared tests', 'status':'in_progress', 'conclusion':None,
            'started_at':'2026-10-15T10:04:52Z', 'completed_at':None,
            'check_run_url':'https://api.github.com/'+A.PREFIX+'/check-runs/5500'}
        original_json = f.api.json
        def native_json(endpoint):
            path = endpoint[len(A.PREFIX):].lstrip('/').split('?',1)[0]
            if path == 'branches/main':
                value = {'name':'main', 'protected':True, 'commit':{'sha':'6'*40}}
            elif path == 'actions/runs/500/attempts/1/jobs':
                value = {'total_count':1, 'jobs':[deepcopy(self.job)]}
            elif path == 'check-runs/5500':
                value = {key:self.job[key] for key in ('id','head_sha','name','status','conclusion','started_at','completed_at')}
                value.update(app={'id':15368}, check_suite={'id':1500})
            else: return original_json(endpoint)
            f.api.calls.append(endpoint)
            return f.api.mutate(endpoint, deepcopy(value))
        f.api.json = native_json
        self.enterContext(patch.object(C.producer, 'selection_profile_for_reuse', return_value=self.profile))
        self.enterContext(patch.object(C.producer, 'reuse_source_profile',
            side_effect=lambda *args, **kwargs:(deepcopy(self.profile), deepcopy(f.tree))))
        self.enterContext(patch.object(C, 'integrated_controller_for_reuse', return_value=c.pp.controller_digest))
        def retained(receipt, *args, **kwargs):
            A.require(receipt.get('schema') == 4 and receipt.get('protected_source') == self.source,
                'fixed original source reconstruction differs')
            return deepcopy(self.source)
        self.enterContext(patch.object(C.producer, 'retained_receipt_source', side_effect=retained))
        def original(adapter, invocation, plan, policy, context, receipt, binding, *, integrated, root, clock):
            A.require(integrated and context.protected_source == self.source,
                'actual schema4 source context differs')
            return A.Adapter.verify_integrated(adapter, invocation, plan, policy,
                {'shared-host':context}, clock=clock), object()
        self.enterContext(patch.object(C.producer, 'verify_original_source', side_effect=original))

    def reuse(self, *, include_platform=True, **kwargs):
        return self.C.leaf_common_reuse(self.candidate, self.f.event, self.f.environment,
            list(self.f.registry['suites']), include_platform=include_platform, adapter=self.adapter,
            clock=lambda:NOW, **kwargs)

    def test_actual_original_schema4_whole_hash_full_E_and_current_native_leaf_are_required(self):
        for target in sorted(self.C.LEAF_TARGETS):
            self.c.binding['base_ref'] = target; self.c.push['head_branch'] = target
            self.f.event['ref'] = self.f.environment['GITHUB_REF'] = 'refs/heads/'+target
            self.f.environment['GITHUB_WORKFLOW_REF'] = A.REPOSITORY+'/.github/workflows/project-tests.yml@refs/heads/'+target
            partition = None if target == 'apple-ios' else {'digest':'sha256:'+'b'*64,
                'common_owner':{'kind':'shared','suites':list(self.f.registry['suites']),
                    'include_platform':False,'platform':{}}}
            self.c.plan['owners']['shared-host']['include_platform'] = partition is None
            self.receipt['include_platform'] = partition is None
            self.receipt = FIXTURES.signed(self.receipt, 'receipt_digest')
            self.c.aggregate['results']['shared-host']['receipt'] = self.receipt
            run = replace(self.original_run, final_publisher=replace(self.original_run.final_publisher,
                receipt_sha256=hashlib.sha256(P.canonical(self.receipt)).hexdigest()))
            self.c.add_run(run); self.c.runs[100]['pull_requests'] = []
            if partition is not None:
                self.c.jobs[100].append({'id':140, 'run_id':100, 'run_attempt':1,
                    'head_sha':self.c.binding['head_sha'], 'name':self.C.producer.PLATFORM_JOB,
                    'status':'completed','conclusion':'success',
                    'started_at':'2026-10-15T10:02:00Z','completed_at':'2026-10-15T10:03:00Z',
                    'check_run_url':'https://api.github.com/'+A.PREFIX+'/check-runs/140',
                    'steps':[{'name':'Execute and verify the complete Android platform inventory',
                        'status':'completed','conclusion':'success',
                        'started_at':'2026-10-15T10:02:01Z','completed_at':'2026-10-15T10:02:59Z'}]})
            with self.subTest(target=target), patch.object(self.C.producer,'platform_partition',return_value=partition):
                value = self.reuse(include_platform=partition is None,
                    **({'partition':partition['digest']} if partition is not None else {}))
                self.assertIsNotNone(value)
                self.assertEqual(value['reused_suites'], list(self.f.registry['suites']))
                self.assertEqual(value['executed_suites'], [])
                self.assertIsNone(value['execution']); self.assertFalse(value['qualification'])
                proof = value['proof']
                self.assertEqual(proof['original_commit'], self.c.binding['merge_sha'])
                self.assertNotEqual(proof['original_commit'], proof['current_commit'])
                self.assertEqual(proof['original_protected_source'], self.source)
                self.assertEqual(proof['original_proof']['receipt_sha256'], hashlib.sha256(P.canonical(self.receipt)).hexdigest())
                self.assertEqual(value['external_platform_required'], partition is not None)
                if partition is not None:
                    self.assertFalse(proof['original_platform_job']['reusable'])
                    self.c.jobs[100][-1]['conclusion'] = 'failure'
                    self.assertIsNone(self.reuse(include_platform=False, partition=partition['digest']))
        self.C.execution.execute.assert_not_called()
        self.C.execution.capture_execution_environment.assert_not_called()

    def test_absent_pending_failed_retry_native_hash_or_stale_context_never_skip_actual_fallback(self):
        original = deepcopy((self.c.runs, self.c.jobs, self.c.artifacts))
        for change in ('missing','pending','failed','attempt','hash','tree','runtime','git','source'):
            with self.subTest(change=change):
                if change=='missing': self.c.runs.clear()
                elif change=='pending': self.c.runs[100].update(status='in_progress',conclusion=None)
                elif change=='failed': self.c.runs[100]['conclusion']='failure'
                elif change=='attempt': self.c.runs[100]['run_attempt']=2
                elif change=='hash': self.c.jobs[100][-1]['name']=self.c.policy.final_publisher_prefix+'0'*64
                elif change=='tree':
                    with patch.object(self.C.execution,'checkout_identity',return_value=('f'*40,'e'*40)):
                        self.assertIsNone(self.reuse())
                    continue
                elif change=='runtime':
                    with patch.object(self.C.attested,'validate_environment',side_effect=ValueError('old E')):
                        self.assertIsNone(self.reuse())
                    continue
                elif change=='git':
                    with patch.object(self.C.producer,'expected_git_context',return_value={'wrong':'S is not M'}):
                        self.assertIsNone(self.reuse())
                    continue
                else:
                    with patch.object(self.C.producer,'retained_receipt_source',side_effect=ValueError('changed original D')):
                        self.assertIsNone(self.reuse())
                    continue
                self.assertIsNone(self.reuse())
            self.c.runs,self.c.jobs,self.c.artifacts = deepcopy(original)

    def test_current_native_job_foreign_attempt_target_and_selected_owner_changes_never_waive(self):
        for key, value in (('GITHUB_JOB','route'),('GITHUB_REF','refs/heads/apple-main'),
                ('GITHUB_EVENT_NAME','pull_request'),('GITHUB_RUN_ATTEMPT','2'),
                ('GITHUB_WORKFLOW_SHA','f'*40),('GITHUB_REPOSITORY','overte-org/overte')):
            with self.subTest(key=key), patch.dict(self.f.environment,{key:value}):
                self.assertIsNone(self.reuse())
        for key, value in (('status','completed'),('run_attempt',2),('head_sha','f'*40),('name','fake Shared tests')):
            with self.subTest(key=key), patch.dict(self.job,{key:value}):
                self.assertIsNone(self.reuse())
        with patch.object(self.C,'verify_main',wraps=self.C.verify_main):
            value = self.C.leaf_common_reuse(self.candidate,self.f.event,self.f.environment,['first'],
                include_platform=True,adapter=self.adapter,clock=lambda:NOW)
            self.assertIsNone(value)

    def test_package_delta_keeps_its_external_owner_and_current_native_job_is_bookended(self):
        path = self.C.producer._host_policy().package_policy().S3+'/package-lock.json'
        self.f.tree[path] = {'mode':'100644','type':'blob','sha':'f'*40}
        value = self.reuse()
        self.assertIsNotNone(value)
        self.assertTrue(value['proof']['package_work'])
        self.assertEqual(value['reused_suites'],list(self.f.registry['suites']))
        self.assertEqual(value['executed_suites'],[])
        reads = 0
        def changed(endpoint, value):
            nonlocal reads
            if '/actions/runs/500/attempts/1/jobs?' in endpoint:
                reads += 1
                if reads >= 2:
                    value['jobs'][0]['status'] = 'completed'
                    value['jobs'][0]['conclusion'] = 'cancelled'
            return value
        self.f.api.mutate = changed
        self.assertIsNone(self.reuse())
        self.assertGreaterEqual(reads,2)


class OptionalAndroidParentCommonTests(unittest.TestCase):
    def test_leaf_omits_only_common_on_verified_original_proof_and_never_retries_failed_execution(self):
        import postmerge
        import producer_workflow as workflow
        import tempfile
        context = {'binding':{'base_ref':'android-phone','merge_sha':'a'*40},
            'candidate':Path('/unused-candidate'),'integration':{},
            'platform_partition':{'digest':'sha256:'+'b'*64,'common_owner':{'suites':['contract']}}}
        proof = {'kind':'leaf-original-common-reuse-v1','reusable':False,'qualification':False,
            'execution':None,'executed_suites':[],'reused_suites':['contract'],
            'external_platform_required':True}
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory)/'common.xml'
            with patch.object(workflow,'_push_platform_job') as native, \
                    patch.object(workflow,'_platform_bookend') as bookend, \
                    patch.object(postmerge,'leaf_common_reuse',return_value=proof) as lookup, \
                    patch.object(workflow.execution,'execute',side_effect=AssertionError('duplicate common commands')):
                value = workflow.legacy_common_fallback(context,{}, {},object(),report=report)
            self.assertEqual(value,proof);self.assertEqual(native.call_count,2);bookend.assert_called_once()
            self.assertFalse(report.exists());self.assertEqual(json.loads(report.with_suffix('.json').read_text()),proof)
            self.assertEqual(lookup.call_args.kwargs['partition'],context['platform_partition']['digest'])
            self.assertIs(lookup.call_args.kwargs['include_platform'],False)
            with patch.object(workflow,'_push_platform_job'),patch.object(workflow,'_platform_bookend'), \
                    patch.object(postmerge,'leaf_common_reuse',return_value=None) as lookup, \
                    patch.object(workflow.execution,'execute',return_value=(1,{'reusable':False,'environment':None})) as execute:
                with self.assertRaises(ValueError):
                    workflow.legacy_common_fallback(context,{}, {},object(),report=report)
            lookup.assert_called_once();execute.assert_called_once()
            self.assertEqual(execute.call_args.args[1],['contract'])
            self.assertFalse(execute.call_args.kwargs['include_platform'])

    def test_only_native_parent_common_nonqualifying_execution_is_declined(self):
        import producer_workflow as workflow
        import tempfile
        context = {'binding': {'base_ref': 'android-main', 'merge_sha': 'a'*40},
            'candidate': Path('/unused-candidate'), 'integration': {},
            'platform_partition': {'digest': 'sha256:'+'b'*64, 'common_owner': {'suites': ['contract']}}}
        environment = {'GITHUB_EVENT_NAME': 'push', 'GITHUB_JOB': 'common-parent',
            'GITHUB_WORKFLOW_REF': 'noah-l-frank/overte/.github/workflows/parent-qualification.yml@refs/heads/android-main'}
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory)/'common.xml'
            with patch.object(workflow, '_push_platform_job') as native, \
                    patch.object(workflow, '_platform_bookend') as bookend, \
                    patch.object(workflow.execution, 'execute', side_effect=AssertionError('no duplicate common tests')) as execute:
                result = workflow.legacy_common_fallback(context, {}, environment, object(), report=report)
            self.assertEqual(native.call_count, 2)
            bookend.assert_called_once()
            execute.assert_not_called()
            self.assertFalse(report.exists())
            self.assertEqual(json.loads(report.with_suffix('.json').read_text()), result)
            self.assertFalse(result['reusable'])
            self.assertFalse(result['qualification'])
            self.assertIsNone(result['execution'])
            self.assertEqual(result['executed_suites'], [])
            for field, value in (('GITHUB_EVENT_NAME', 'pull_request'), ('GITHUB_JOB', 'project-tests'),
                                 ('GITHUB_WORKFLOW_REF', 'unknown')):
                with self.subTest(field=field), patch.dict(environment, {field: value}), \
                        patch.object(workflow, '_push_platform_job'), \
                        patch.object(workflow, '_platform_bookend'), \
                        patch.object(workflow.execution, 'execute', return_value=(0, {'reusable':False, 'environment':None})) as execute:
                    workflow.legacy_common_fallback(context, {}, environment, object(), report=report)
                execute.assert_called_once()

    def test_required_pr_common_fallback_still_executes_and_fails_on_failure(self):
        import producer_workflow as workflow
        context = {'binding': {'base_ref': 'android-main'}, 'candidate': Path('/unused-candidate'),
            'platform_partition': {'common_owner': {'suites': ['contract']}}}
        with patch.object(workflow, 'current_run'), patch.object(workflow, '_platform_bookend'), \
                patch.object(workflow.execution, 'execute', return_value=(1, {'reusable':False, 'environment':None})) as execute:
            with self.assertRaises(ValueError):
                workflow.legacy_common_fallback(context, {}, {'GITHUB_EVENT_NAME':'pull_request'}, object(), report=Path('/unused.xml'))
        execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
