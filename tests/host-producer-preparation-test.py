#!/usr/bin/env python3
"""Offline compatibility and trust-boundary tests for staged host receipts."""
from copy import deepcopy
import hashlib
import base64
import zlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

# Immutable historical20/21 and preregistered source23 workflow bytes,
# independent of shallow Git history and without installing any workflow.
_HISTORICAL_WORKFLOW_BYTES = (
    ('81bcf1933edc435826e2de411a777cccd4dec7c7', 'c-rk+S#KLT5`OouptFOq1uW&*iFdMEWU)>x#GXSAY&na;U?5Q4l*G72_K<AZ+R6O)Ena=7TSpw*2m<LzO%|`JuTJuB=v2rl;Tma~DNSRPlIVtvDH>BwCDBaqe<2cSHnabcq<>^gQU!lzjNZZkP2`wrl!}B!^Y#uWQ`$k7G!=?zA?GNX(C9|($c$sx_uZd=qWv+`lWf?gGs^YAw4>Lr(O#M*$-pc@mEJ?&e~<Pngl)4C*n}aaF@x<|qTLEjG$DLUReMMjwNo_qYNiv4K7B&XV?{h~wM_T&4J2ep6SITGNlG*s4^%C)l?s{dY1^ak0x99K6fDMx;A0#!GUh^Q7OA~f%Z}Z<m{F-I;vk0^MN_ItOf*4U@KlO8i>O4iBfFagQXyl;2}t6Pj3jKtA}2{h{MTPQf_HWhDl^`EBc$gkRqiiFA_X+W{zKBrr<(I<A_ZsvqrSz7#(#JQ_^+HH@O>-f%_tGKgP5t5=xE|rV?52YUl}2Q4eV<Sh*QjM)%{|sBFR#75<pwVk)BW#iD{ZpIC%`<j3^#SN>MQyX+~u}gE?Ra4TVT3;iY*;BujM1=mX7LJ?i5Q8j(cNos`Ncvvb;wMuKY)sp<eBiFe>L%A}+`nw#FS6j^Gzf=Xbg64)q01rlW`w0Slif=ml^Njd_7*-=}y*lU%C8kDfuV!r}%i*S$+;So(R;}}%MqQT4eqZnEN25rJhWHO=-X3kojWPmKL&4d)azeJkeX^U_N)=>v-V9G4*0%*){0XVMFF{;|;5L0O~3t+!MxhGSgx2S#4cKbRAYNifSiSvWnmG5+WK27YXTOba*Dw&i4vm10qduy{l1DpUnU?-@)4sfD02Ei;qEk_YaZpmEj+cozsZF_+f41faDWH+g@C;}MUgRCdMVQFg4^OP`j+H(brjC5{4OGYrn1>VRjYz%oe%(%|*(aZMpm(B~ZDFqhdDdWIMnE%)|LsQvFgtHF>Pv#D*5X+>>OU+ZaD`d_x*wG@U<w0pecrgY#3sObFurobhN*)M`A<hYx2e_6cD`@aX1JJ&Yz&5pXnF>`g*vD=Iuy-+olP*72jj}$8p<g@RG}ebsKn(^f*;=ElPqG;&8ma4(DXP~_0W`%xuiAsc^Dh~_NLZg@y)<f+^+{GrqfAsE%DB-2P`S0^bILG@r42!#)9ANGZH)rv8H2HLjE{W=;1_pZ$lH(utLs4apBM3q=;aYTCL}r@l2^}<UmYFC<cEK}JbWG<zB)Ym;l+^r^ZD@5&r<eECJGzX9Z|b5DQzFT4TcgN{-of9!2wJZc3iYlshH9@0=XF<53yZ{@B#@$rczNH4$wiL@-BqDi!HSn7^;I>s8^!^Tc$AtsjzHBYrW1wU_(?N%7nthj3qIyggO-=UD8O5O+=2YsmtSH=Rt);##!1Z23aPCRT$vhHu!JKX9fG;oelaIKXrQ*8EA1sd70C_lm7XK?%<bh|K#+fe=<1l^}D^k8`JEmYUbI+9IGb1dVAJAz5e;U_wKVMRv?WyOAJ`^$-(z@(7$nkiMgH#{sQ51gs%{O6F_sYM6?du?Q~vv_A&=SChi+O`|jO&|LpqBp!)$BGI)Q|KYJEBZDzbk(L4F2Ybe|?ir$Os{`>3xvju^Z*rh<Z3DG9`F$!dKmEM74vRcZ*&P>p;-b<P=$ArpzkEqv9IrE+8?IQ|FA&zNkx{tm{Ys;F7tFeg_BN|CDwH%~(a5@ksR5faQx*yMsRvCL+MqGf|#^|!PeGQfh;n$gov6_%#;MLj5rr7d)^3{Z=VV7HMJ;TbD@{4)pc$9N&Lta6T5t|Gg!q&BZRMsT>=&uwJ7v{?528}^IqyS}-X12W!Y_ruNFP;6oE|hVX7{x7D6LJK5!SHRG1^D2o64|>%#_p{#ec5&SHl$GQ`$3MoTRv_Rx#z&HPk3CGxvevPPMvX0{h+LDjfI0E<X<5m3qT*KcfL3yU6y_}<f@OVfBrx#6wp)T8u%5c(S8$sJvB3{jDXLjYQrW&jD<Gdn{pH7GOE^&HyN1O;BUV>9B<Y4A=TFdaE1Qn!kRB6-c3SVl5x|!6dGtP?Oi4JhP*eQre2O%HB*rRdqzEh>-8(GP<>DFHK~3Rd99RDIp<axA5s~^(7@|PeQYj5Z6vyNRj5^yY*dC?HNi%8s8tgz6ry4gWm9Odg^nlC=*oI4^twW~sNKKW_5L10o!=W3eS^(=C+(+MeF@M+6pH`%HWFddFraek0bDgh4GIvqyEPV%Wh^Qj_mu%}Fai<IuO=Q}J!)&NP>~w#*X{)KGi{yUqv5#*iY3wL2ri)WS0W}Ql*ERl{%uA+P0{sD8sJR;+H9)p%-h=Q2gCPg-&(J}P0MSkMfeq}_oYhr6JD>GdU5Fv=6==qaL^A1c5_%`N*Fiy5CNJfhi19j`~KJd*+uX4qSycL<$1sR=GT7r?Zs*L^<hy5wk6-139#8M)PT*~i^XF4w^MDZ9c_gNuF>Wmc*(Pq%1(D1&D=%?tW`3`;pt%R>~S#5{;Lw=__msxSZuFC2bXURa7a5IOjR$bE%0TW%m@Qpk<{N}`bSl0NJm2Ys}h*JbQ`j@vYT7kvOS=8a8-S{?jeGMtoLy88+wWGHM)yOzqK{$O|iRE__9YC)>S}JLW5dP%^T1WOK7;FD{Htdo`6kE;H6h$>yP2SQwwCxU@o)D(+GHu@b;&{W%ug(=l+#Lh890wUG$tuZIuDA$uo-kT@lZmk6m-|X?KLp;en#E@q1j0?))F&V*}*'),
    ('d9fefd275d9e3c6977cf9350a1945a6bbe5051b4', 'c-q}s>u=jO5dWUPg6WDn0Ve0Yb{;Y;ON=J#>I8|?p(qMLmd-XCSyD;LiP!dj-|?k~CClz3S<!xq$-Cq6cW<gck&~EByhsqiQZ67MiRa&VBOoJ)fO&$((Qm}_1)ZwD34`}3Wx(-|DTP~P5FQ(WAW0ljf7V`$ya{y3B_uJYB4#t<kHNp;YjM<BBP2<~(3LWP3;CN6F-w5!KOGV$cxqsNFev@xv&bK_IHLc8S%H9xY&-M@5N5y9DF1yMvzuWU-?{<ii6{KAK8;36D$L1*urxxwMtCz$wW|7G0NiIZk$1;ir4bQhAbvbaLJ)wvQ|f~=WB?@RCV~RXB*+VP$RLhG@S=j;p_hiDBXNgp)u0=6$j}QptR=uERLN9|`f(&6LZy+=3)b+bpE3rKKa;y77N?2avd}vkdgt+n4`f8eI32WMiu~=O71~ic82}?6KUx|FL-OfUl}ma7UheRav^4T9^5h9wFVXm8FB$=F4?GTXccXS!P!U4m#5vwLm~BdCs}Gun29mt>KJ`L6q`vaS7HTO$@gg5Whel4qVr2pY>brQLP@9180#A4jk5lG@wyk#4qZG{<2`LcB#U&ANCzM-h4;gk!8oH86-M<K6tDvg9wkz?IL=%rj#m)Z#MRkpoV}OzNR$J3;*?8bv33D=VlyBXM_G}WaAshOVuuuU6C}0l83?VPP^=5oSS!_emw&zIEqd5Ayx-(CGA5GMfdM_uwp-F-W>3hrtgZwua5PDG~Twap~bBw`?JK7DdFjM#<i@rh#+3aOf1b1W_NC#;oQfGI+y}hq<7@Yv(<xFUVsG<A=wTw%}6k{*y#!)!y5E);XaT9I~XQ<mHGVS7uI}V`8l!RWC^WbJq$^p{?6|;rpmLO+|Frua<`Fdr+2?Dd3i{bVTVdD#rDN*Ijroy-wxB<nRF1}WUvMNN<FXfkuRn~FLh1&>gg|aGSH6&`OtHL;lr6Q0fXGC0BOanKs8w<GS39BNOTcbi*71C&pB2kr<MluR8<d*VhlvaqMwJn5>=wlhSG61u_MkX{GjZB|n4%eyCB#bQ;>qz#;Ua;ry@4|uS`3D2<+4jM+-Gjh;`pf>#w!iaiXZPve!25N3uw$g$VqWbOYWPrJp_G>Ml+re(-yJZlT;m)G=?5stYMieE<CF`>N4v>lg`I)z4=f4xHH?E}FVG<$vn@hQ-Y=|3H{@HDMxjE1xlB0N;^479RCaZSa3oQcmB!o|q%;hiQq3+I=@R^SB>Op{QeD<n>B1H>B5Rl`$3%f>Poe1NYQg-5Xqv<S{M7BAzv%W#HW2X*L`9@~NBy%`UH4_Te{^!xKXT7{{cf+XdFsnjB|TGBdUByy9y;WACpX(njN@p}nsaLb=-TVr$t*9h#k(O|`Zsy>`1x7?^!iV?`wCTcFOK@BkL;$SI+Hny-qFjhq|ln@yXV*ai|hWQIa7FnZf&#R7P6_8t}UYo?yzL2_@P!aS^JmQuXQZrvKwpNW5nsO$u!T_hk(t#6F?%jcfTs0iZSGry9RAWGGy^YAqaPPJ2WOvMHQXC3^VEPG7}aZ?X$g0W!)vdlpDVarsMFjmor|S9<AzI1}B{^9tbXd*mA&%Iqa*k(imlkt%w!wNV74EkfVy;JFb$Y>B|beYM!A~i(cDXV<%oDsfX>*!Y0XE#yT681}A7eNd%j!S2qMLo9|X_#!cH&>bdnip>)fph~@gO7xk?pH&<9UgF|b{@KZFsntJ9FOWqnboTlI~9bM<%#uQ@0rZTzQlQ)<PHMoPJ$o%137<HqLzS@IJRfh;vVTN3VMFzYq1`x@1h5}#8FI#P?;G4It<&(66qrsc9lV@||LY)Q+<^;G)Z~-dKdebFpy7f#<b%<(`l=tnX6MulTWKL>uL__gS9kGtQGC>`d%FbffFpQ36to4riL2e~ImQ8X^LRK2(ngpyg%QXp@8|H%8PbavbhJ^?4uhMx9URI);_q8|byq|3ucw754wu15|{~0mOuV!^b_O)y^AZk3`3bhQSTf0+WILD#Kt*_|$C3e%08t=D6PWD!H|F*82*<kMq?Y-xhOsQ4#N=3y5WoHP?%|3z1PK0@?_LvV3nV5X*hxF}bXfKX}DtL=R;j>?en_sT7=_pUrb{;Rxt`GQ>B`3hbBg&V}*Y={XB!)9QLw+ZbFAElDlHpvO-!5MFPtSWN=e_<vmuLO%pRfDf<MWg5;Z8o;sUfc7&#EWGsZM^>m>-XSoQ}P6wT9$Yq0N%pg6}ycP1kE<cBN?CEMyk@kvGeuj?FRVSE+iKwMx#LUoX3kQ+x+-Y<qGap=uwQHAE&ou<!JhdA0cbo)Xc$zwk-N0Y^{#U-z`Gk`T7VVu=5-LVl7S(h%%(PVvE2weJ{hA%3q5)jVe3#zah1fMwqRN)Oz}r`_Wh?q&Dt`tSag_5l(9b#>m;!Ma&A^(v3y<=3%g&xli<wU<1ODNP)CX{0DA`~^>EYySb4lWnp'),
    ('d04a6dc70213d8b549bac30c11cc15eaf0182dea', 'c-oazO>f&U488kT5J7>Q<b1E0feuTDVC`XD&?UPDvdlDEZON0Uq-oLrKFN-gG>5J8!GKBnk?-+IiWiu`#L*fRNx=zWb`OM41ei&RBCV1LV5`mJD%abk;CUVb0NPRM$krbK1rpCV@ugJcp_(wjhUd<=xOjPiUplq1L7^X%e8zZ>5TE@Dudh*5qA8@cQmd+i&{fJNV321~6p%vv09N-?6`T7e2(l;~@ifOHqZ;aos(Ry;Wu76p)G2bTKa9J>DnqhBKOZZka)iF`=slz>mX@%z@xIO9NCt$exPfDP0$<iB9z(Aa0;SP}f-r-EOVto3FA!MmjKG87&W3rp2szsk0n0;u9%KVC?Bj@YF-rNkI~w;#8Nd86>~%$N-0NQsQvR`<_6|5(N$cYpgVw8>;Db-NG{%kR5tlB{mj-`3v=pb@Vr<vEVOKvT_dr0#d9vAQ9F3Khm@t?H_wn4%z4C87DY7Lu7Fk1sd0mkeI>UdK`j%Sfwqvl=R+2WmI%PYDT{KH7cV`<oT1cyW2mW+;-xOtz{(LA-a&zLS!vr!*-neV;umnD_Q`S3LYc&9N3+xB5>qeN)|4&;@%&I*=>*DL}{AO{zoc^5N&6l&u{HE0;Ss-;@aX0xk4HdOPkJ;~w`D`(7oe6S!Lu3$ku;sgh|3PWRyhAf5&>Z#fetF+vxVnP2mjT;vb!#W>=nof(d71'),
    ('55d08b65a987224ce576459cede693cfd49375f6', 'c-rk5YjfMU@w<Kns`Ffun}T{+q#lhs&gIm^J;!!rJ8dU*H6RE|uql!TKsmZ3{q0=<ltk)bD{01;59coyfZfGn-@E()ohve80g_23C__mc&HjP{mPX0UED#A56No00G-8S&B{Hc1{w@(WVU*nA5sR51iYGB5!Guc*znn@;Caj0fXE8-n67j$QR74izjVEaD<445fG*i-{i4ZKZ+n+yIDoNa{pv8T|fXkF9I@X&g$FaW=DxmhzN5O70E?CghOtU{DHA~@UsRWNlpL2{!60ohHbewPst0dJFWe>d<ER(Pik|^>Cy}6o`NktO!i0yc3nnlr212U<0L}4FNMnUdFpGY>8WAdeVV@86n!J9BK+U>$h%0#YzqYy%KsR_8cqLmXX7OUlk76Z=3FyE~J6wN@3F`a25Bavh&+yUl-m*#>C=28@<wimdF#FRyt#~9Qy5==_VaHVpc_=dHd60>$=E%IHy2Tupi&5dJ`#QZmFx*8D7S7L2inV-cf!_AgcZ<!OtCoIVnp71zR4DM^XW}n5=xow`l>klsa!?$mahZp_xi{aq%<fK37p;{(IE#iLdR(Um_$F<u@1SEjr7#zzWgTti@8^<}nFUO4DAh>kllKHC=kwYQ`#tOXTil|YI0SJft!9Hy@nM(+DebTABou(U*w%2OZX`|C<w)cI~t@{o11Ddv-y3<$?yyI%zTdY7LEbO5P;c;OPymQ=}GgaJYLUO4v1q%W@;3NXxz>_3fdD(y&PEo|C44n-SH{fcvpjD8n{`>jGd4G8R`bDo8Mb;d~+Q$6v)$8HK>9740i!*{}Wxk`58y1)0UiV-8vYqzasmeHS`h!>ZFtqTfGS=DU@$qobe|rhWQ9@id@Lcv8SmLJw1<4e`EK5+zQx*~)70%wjN7cQ#psMKLzvw^j>$ppBc=fSW|GbB;u2!MvPu~rC@#x*ai?7Ww8n}C<(XM`4K>+*BNOZ9GbTmdJ<)|uHn#kJTtD}q8mp=oQv(xjVi_^isYFboqP$K?p_3EeBw+IX5Xv1){8lFFY4%_yY>NDWxpd_nx=I0c&`nOY9%5OUbYYUKECtMA;QYy%HL25%77&F8tlS~mmVmb&0HlCR~jOS{og7-agnD_!;upwmegu+S4AoXLYPc%UDYog0h4A?BzKv3OC76B(v<b;Ny)vynVotdmBImG0}bsSQl#oQK?c8xD@PJii_M57CmmB27K{oB!T87i+g%79-J2fz3D_E%ig@eFJ@-k;}|no1IIcbzOTo9Zk<S#6%$vDT!M&I;%lTb*H3*J2Dd4h(>Q<$>h%^5X3BqFTaOy3z6%#wGx9$h5O1_A(4r0isyjtcJVN1xDZC;$Q~`FIOy}Shed-tvaj)S`14VYwhIQ%UA;xwfyt_W#lMbdY#2wAwT0$V8sVTQWhy$Gj*1g5(}IUlgK=lGM;V+UzTOgwM^m_cRPoql%)mfof#!AT`BC@`o^)>I#w&viAc=QpAOKIh>ZxHVL!>hX@e)|)2CH0&`?1_vkCaLVdTk{&;}VYOR+VhLwHu3`gM;INS1CGhV53P+X*^etJ{Iyme=l3uR%<B^PGLBzBRmAf_SP!kS-6a`%a@-eMk@|pm~tk?<t8GSU7C9y4`lY-Ry!eSh(+Yx?Zcrn()tSxy%i8@bA+7j+KLZj~q0)f)tt$%i!;1N*)$Ks3XKU0Z)Q-_(YfT_dn|zs2=(r3q!x|vX<NOn{K`CdZ68I!}IE%A5bq0sULPdqh8l(-}5Z!IHASyGuu`wHpxV(;MLa^p516y*HVsD&@mR?Z632Fw|tEh)@#8mNT66!(4Iq4n4lNbv~IoLfWcdsJZOO;R&whOI6Qv|2Gha$LI(&aU?8PRglFjA1&RnkGowRX7BPIQbnHO4Dqu7sdSozVE~N4)HgOydJR9j?tF*|^)0+{7?l9yd=nVW(G%<iH*R2sRa{v#bH_Z)unz9mb&Bnus%s>lr)6pG|gXFHc#)pRsoGhNSvR8Qd9rNj!K+6{yV0huJa+jO#rpFe!0Umvc!z2orh`?ZVUWqh__Ylk)(E<jn)^|+KisXg^J){9YphD-1d+BP~ZQ5JtVdLRk4-b;Y;H4=Hg4kv{R%!Q=v9f}AqF}hOnMwdfX0mpsjl7r}mR75?JCC7O5h4-bE0}!%B}nvExo?d;;Kx6h|I%t)uTGfKB88vc9KtI>csayMz&V2gg$QT|WTJ%tW$hT20fP9WM^!-vC9loH%b~&lk%%5Hf~&>)BQKcNkJh4?velCvl??kQ?~VqiCvW;Ex@F9ZYOEt-Y0hB6n4C$fAWq#OFi4P<LsF2)BoR<)>S#{YFpEJQQ^=Yy{v1LY5wSd|7wEvSM@tR#qz`prMN%x1M9tSRQ+BSjUZLU%nu0L$nn|;W^;;x{%>wwQV>1J?bTk?0<qJ_4QjzZNFzn7V4z|M*=q49su_jf^hjqFVkVZ(3`k+?q<Q)?{oS|HgYt7HRXPldi$*wz^$-(Ys(*NgK|K&v=3fTTJ{5U$zyQYoA?J}PYe|f+4M>F-!nyJTWjm*UT(Hf(<-0{-Ps(b79`MY&fxx?BK^-}CI(<P({?~4yLpm9BwUZ0+Rv+(|ye*4Fq<O^K;p|tXyyZmEML%w&Xzl4vmBq)9@HFc2|yHMq_jYM~3CZ9e-KmLfGe*0m<vn_3RW;nz|C?3Mzq2H#i=aF{1$voflL*MPNpdL_Y!`=NRX|=mSyWQ!AcBD|hZ=_%(u=@Ege>yJ24Df;>55O;0H;K}{fZ8-*{#2^}Hz=oczA*XP2FRbZrgsO2W)8kAYcmP0ix%~6m8m;ytp?q&fr@(Qj)=H4Q`cWpwKM`yc@MQK{{ur>)>r'),
    ('e1e009f489e2bd126d0546f75977dc73c6450dda', 'c-rk->vI}8693L$q4m1TyV(+841;0IRq@$e>}-M^8|Uuo?uwd+24oL2V@U(1Hv7L{x8@CFY_i#_d+;S@q*hO>)sJ7dCf}3uK+H^E5hWt2m_tI-elRDDOqkDvsd(W3OiWwxx&BQAdyKeX5`N4%TfhQkiV0IB3_NZx>own;u|Bz-ngW@L;GWrvoL$xezh5I{5r_xZ3l?MB^gJ9Og!^HnWc-^DhlR{{m~St~$>MB^5VZ_}w^V}rlWfpot{Hi%PYw<WW6~BpM2Y)k@C5P`6$D-?k0g?L@E0VsmPAciwtK<CKynp`B@scSm`GT%r%=;_+`hvdQ?ae3%2*^C9*3UkZ^;EjDk>}GG-raloH;qSx#>l~ZvWR`$$enSda`i}CkOmwJz-Q|<v@P>ZH0HmhPP#&u~_F`*1@)narHV+82lZ=;_8@Z7|ChO#}cM*Pg$aON?<=C;0_I^fzMXP=7NUY4${#u^cdxVOrCAtc=IOtt(a8lQ)sHGq<rEBf~9Xcc=M+5rap5Hihkp83AFaKPyER9Y9SLdE+yEx7S0ZQ#e6UjFl5uI!J{1sf!>6(6ENuzY)tzmO%-8tiprUAHI1w~o5T8g2)xJW>L6m>k7gDV<ja?oMld(l5FD({Jj#7!HUW*oi@}pvEwNiIlZcWNmQw~kPb^bTYj_lT5}hob20BU6Un48>RYY6udb6!(6rVAmqciRUHN2y<$r*Bk)rSsl9m46tv2JabFRiaOziA-VcosM>zdxf~XM)ix4}dQ*Dp9X9lT5wH0%+2OnkqHIIGmqNnf-tYUrQ5l*iT*<Njx3Q7GRGJ8yCTvw@1#A-EOgtY1$pjJZ^T5TOG&j8tucTeRzD>>K<8UuW217Tozzux&MN(#ln{iG>_Bu#MZ{KljggRovNQooR2agxdgihCjeI5^gw18{$&{nxR{WPrW@#!FEpDYq#jFB7(xBZMlMslQm#>;$5Y6gnBUmitX%pw)g*#NvSQu}X2n6EgqKEs=E-`b9xm62;KY>+c^)ZU?y>s44E%LgacZAo0HJ7`b@ik+Qx%ROrL8a-$gfQ2;N0QxjB&1T2!Egr#fFf*JsWo!L{bWn1E*WBwUBg&H_Q%Z;6$vj!&UcyR}xeuL8nVzz@2{ak@@pn(!pP^2WO+f`S|Q~cz$_)IvT{rAA_X&It(e=d$#!c!|AYkU3KUp<a}^F7@iM?XMY=C-(0;1Hn$}P6|gK{juD=OOE^*gDAhpY8J}om!B;<mwQ5}uO7kt{zbMu2PWJZSU5+m9{xlwZ9t=n0>(kN2UM4%GkkN9I+l$jZ7>fg3K74gIy1pCXOsb5+8~66t6<;DPoEIrlqo&J*sdo1ED|CuNm%KGTd7m){b2cW!7!yOx(}Q(AwjpzzoR9+-vh~3WIkaG9SDyzrqrv#o#}DJt;C3{=xf>1#H+|BGq-c2DYCI~VVR66lIP*|QVCpA8cr6njHD8}Hv>(L48!L%j=GbM9|I^HI3t%e>$+ZrdmC^$oi$WU5)VIuLUE69Jwh0E?ab36DKI|Pk$40w%45MwMdu$tr<}*9cJm?%H!^m)OR6lGTREaZ$cmn6UK^`9{-nQDkUboq8^*|)%9(9g;M!U^g@W*I(SjRyv_w1wNN@<WoL6%mvB=60+xj~G3n0{*+%yq41hqXIxtJP^XI|k^acW4+*!*XoHb#2S-8P!UGDhdj1D~cNgip?S@yR%v3Ul8)JTNd&&*2+r~heZhIOdB>BGn2)H_$3btuq(=<fP_4R6Xaet0{~)%5P{C)vZ!MG{;_J*o|zA<YQpFKy;->eop8k}jv#X-`z)PM#W3oGltxo^T>2?EP~I|$@5FT7xWA%<K9;2d&QKN*5Ke4FKskunlnKi~W-BD3lW3NY5Q$WRkOIzl9*jH#LQ42y4L1}Kj1~h@x3_#AyR4{PD(ImRNaGr1hJjF~<uP*h(@&YgE3Fg3MO+E$P@QTNQG^B-8dG2yf3U4N%g70!<)P?A`*BHor8%AmPa&kx<N;Cwnk!h6By>ssQOF+vL@1!02wEwR3hkIYDu>ygi4Dp*>p&o$Q+>=ZVNh@-hC`)?WFGL%#GC2a(i_(Jm0t=fv>#d(V^pgeI9E=3<`UE^tELv*cY;N0MGAu!<jD50GFI5?f?4*|gh1qJV%XiI>g0o+^^F!K0r@OR-N190@E{~2qV$l&c!_3(Wq}@^)<>vbB`YSdu?0azcWXCsMV(cRW%{q2O!fZ)W57Q%L^`aROMFxtn8Z2)zfjP;t>)nX76{hn$}#z2g1d3~1pFd|gan9Bh(JgkNI><Hd{UiHS`+Z&FU&fNPZ^(vOra{_r;$<^B?=><s0<=mJKPkCyBIid9>A>42qa05tL5h4kzNaoQwHOl!D=`uh5J9>efTiGxVjw`J5<larE-{mO+ex<`A(xxLZ9OL2J0GYA<Xb+M3+S<3$&VYZ$Fc1k9>Ec8=7mxEAfm5<kZ$0==X0JKno^M+N%)|P$REx#o!fT(uyny`naK5#apVkUNV7eNQ}@ACR_&S0ZGPAOATzFV-^G}tUA4S7vs^@FN0y}@+C=Hs}n1S_C2}NH7e0HDimvo$gpq*#3yp|lc0IX{F5m;4Z~A03q+k<W7As|I0dfjacJA??MldoR`3KXbvA`cQ%$)<$OiyGXUKP4T||~HRA9fKKh_JZMp&wV8FElNNK8zrtB?fjY1uH_&LZsTm@=M?b*GD35m>BV*8kpqTw#v~!_SvDSHq8h8urLZQkEuSl=GxqN?XCXF9-xj@ZUPzBbd1PajK_r<U@#<LrFG)whqeW%adlt1^NKk<p;~rB2zjuLn?wmrO!T7ajSj}5zYvp9KfRy_Z*Fp;_8sXU`AXusqHJ~f=s{{3-$}zN7cjCNSK1i7={rla;VjKshrGOZ*Vfa0(U+KIKMH%d`;+iNk!YE(_;SFzFk&{P|GYgqg5cdk9@9@oh9uCeTmj6_Yt0EUg@;%LN73#*cou6LKTvU=`GBq{NcySdN0x|X_{2tT3x$i7-qNIVuoc{uGKkaPSdfW{_7mI%yzfubi2nrx4QP!!W2bK<zFfHzZA6c>dhtvS7yo;3jvF9n^D$cDQeN0W?#Vr48u(XD0O7Gi>U%THHg_F9}2C7Df~iD4DScg`y9}EpLA<+kBDXsUe3NvQ*w>#!M3-2hn-j5c^7a4F#oEX?H5>VaZgyae8VmE3oG-x=-sW{uD81Dt!~j<{SRnn4xX5ew}TpnYM5A!SW>4A7Jl}<5q8MHh_<;R+!UH$dtLYkb=ubN{196ImtXnm;JlXQYFUI&Hvg5$6oDlap9g>c=PqyV^5!mY?(*g?Z|?Hu|4iO2=g7iWF-e`<uT}O3;xw9AOP)+=`J<Zj``U`!tZ7%@{q4RztxB$XZ25ch>oZ)oNU_gwcwLr#X7Mi3?h@@T(Qf<MsMZ8ru`u{wCY!q0`dUA67`>xHl8YU(D$ku=49<QT-wbZ=KBOOUs^I<Y)$j)$J%9XWxhNLl-<gi|1}It~%$D}KSNj(w8>C4'),
    ('2f4aec7f6463801a6deeb443b59977273197ea60', 'c-rk+ZByGw68_Gwm}R;6lGND7*fMsCtFYh=+y!vJ<nHSB$~BTk_JAx2&B)-}?0>)R8OfGxVM9n#_u=+Ku;!(wU!Upj*`LXA7*ANBh>8=bxJx4D+_DiTBOdUWDG>(m2y>K}>fa>hcZrC(gdbDE?_q;t@rWxDg}!iR)vbU{c$f59%z@}#!hGQgNAKMVgYFg~Q6k6qmk>K<fivdPd{HuCB1nI-z>P!U(vqQRoDD>g&lf8qrpA(rQ4q#FqgZ+KruL>faVuL9k0(M(U_&40gn<GEWf$aN?iPGHNenDIGn^g8VG?zLA__qZLeQPxe<vfM#)(~xxi>^{$sd2@hvk^T2p$6Bai5BSMsYX-rNMC?^CjQ932n`WAw8q!B*V2);3qRf_yZ_E<wQ@%Ngyd`k|cH#sDw6})p}FU@L*~v5OVRkcRA<{Kb?IX4tiIE;pO%DdGE4IYKe?%zOZX|%BtBSsNGF`#U<E20Bh^bN=$f|C^`{A0#jYGSJ&g<9MRlThR35ZcWwzRCTh$JoPvHQ6QNRW5{Y!si9q``2Y11y_j~T1(`@h-V@}Iv`}Nj-qvf);)!eN+yZgJ1_MXi;b$d6Zau3?g<O4NuuS?35ZvI1O=%N8!;WEYN;~rPen7TZ|>H1<hkEM``Ix%;FeE~+wO!bJsX|%wxumxo2PNL((guxFKoKJyaaK$K;LWS|H>T-`Iz8ae7T2)HQ`cq}swg;<9PBQ^0gbM^-=<*E<yX4D!ijb<|I5(og(3drIKniFAr#pOQR?Y&4>LoEx<m&uFa&xR)rC^7X{2<VRZHbP`8}2AgT~?#n%A&|;$^(4Fm7ef<^+txlDk%er6T}lb4yCH92ep1x&Rp5r%*W2aU1KnU_z%y8l`p0|i!Jbg%rnCHRs<vJ0$~TKt-5>;6bR`bUiQuh!(T2B&yP+DUX+8fbTufbi?b$V2&F+t6&pzs#$qG_vi%nJ$l4g-Q`UBhl=TeA8iMFGvwmsGc0uOT03wnH=zji;NbZ9)1T~4EKfjR*<`phLH@Fzjvm4FSI1KhO7q30yA+?m^(0qdB30OJ+8Ryzt=n+PBh>`7`52u5Z>tBYw&nQR#aF9x&C7}pF^Ced&hubg){6$G_=f(A)e?2J5eg$`D5|O@UJrfQ>T;pw3i&!;ufYFq1RLv0Mj~pD3ikJ9)r4(@_S4l*TR^D@mw;j7~ISc@z<#}Gax!c)y_pN4UA4Z#2d*88kSvl$$8gz<SftOEZue#f)lnHVUY(bo?;U|C<?;Fidr(JJ1I=~Y5_FDTLtJ&lY_+vF&yyYS?cAUNaQf`n!j+aI`Cx2yA_FWWu1BBn(7WX{6-r~(x({8lt^_B(N?Ce@r-LhTB@;t}(I##(lT>#uz*!s!<MCOwu77JiO`Z@7-+ePs{13o}zVD4-Z#au%RcsQ3Y7FUPS0<=M1LU|IBNJQW@!k^FJ1&_f=r^IG*TsD4lS2pTQ*ex%eK%881xIGA>R1pQ^mkguQNMUp>x-id!KRVylpsLXZv%(l`od+45c(GawDBSx;zjrj~9S{2-56=w>ucNA=sR+wY#W~H85g3$$IQPvVjz2_Nk5sd{y;Bel7ntKAWA$en5HUR@V^?32u_AUNe79DXi);B78y2^7X8B8V=Msi~2E_u1s_nc;*Ya1$H!|<9*B?I)PcE(odDH5&AR~xdHMM+lc64#p|JZ}1{jzt|JMBNdI}>FHcRm-9TJnuW@H$L#(Da<2+RpMB+e8%7nK<D!{O61QrBk~v`d{<=HF@_gxBSg(03Q)3k5v97e+w$4a)uRFFoF~T2tzPoUWtB{kFmMAD&#M(8t=dskYnuTDRar3r2v+S`96Vi#v}yb7R>fJIePnc9<v*O@DT%`B~jRC<DX325GqhbvG%1QIdrtEb-R}wke$neCR{;<(&Gs`L@KCGw$cv>0|ZIHFG=W({FXBS6mOV?Cr}07DMU|lr(Ev%4D0qOZ$X_ir5YPx!lHoF9ES=Y={(egBY&c23n#45D;^3GIJb?GF{;f1luIXlHUm@0vZ;F!xZ!<ci3^M7_?XMEG?o+fp4-lt!Tsp##US0CYAps^tAge^0sd@Bz0h}g?1Kwq%=@^++O%egWNtltt&Zp#%9kY*nAyWs=ENA_Yp9~m%EspUFP+Tvzkx6mMiVT7csUhgsx?H6jv$5<fI>M97b=}_Wv-YB+>THhPmCZgG~iGk$6+k>?E|Wp<dbTB(wcxDf9Lj*u`+(0bA_sepH{ZQDy*>56{Ub<unLj{7AxT)$lyE_xeh0AfA~Vp)&ot}EgNP8h6@7A(DU+3<jLSAJo1w+O9_22Jt6D`+4nJv-eJ+1zZ77tUYWZ{w#iQi`m$JA{57};O&PKEECNq}NjtIOf<S?`N=_*kz2E|U$UflKB0`230dAT&q+JR!g){`D05AO3DfiFhS~vEHZtOv^kCg(Xq*#f>3;&a#dN^q`CWldU7*E2uO8VI2R5?na=lLSwMqUY5ryV}PPMwQE@}tH=VkrV?qrOf*2z8R!x`hD(e?F_`NDZ)w0TK$(J8(>x)ZK}+2+_RZ)jWZO6s~(|W{vW6TPzN3UM(76d&jgThrRR9r<WJ!XOMGllY_J+k+M;|KIKe03JiZw039KKtIz{xDEu(f(=Z7DBc{--8F6=rd<F7g(ddKbDR%6@bu`Nq+Q$)%!%$`40oTnvzFLS(2;|7qG#%BMr*7;}7@RLIo74_ws2~vt#+(C#_EGf|Mzh+*B=3aAi}Zd&n`xfzf?bM<Zn6Kq7OGa#%C-3P;bb_t_*)Okmr7+ZXma}H3GLvUG*c{P3N1nG)vc>tAl38}Xb5E8x?C}lHnSm?>hNVwPlq~n9J)yYk(C%}lTkwRRA%)?u|@bWL7Qa?T2q+J3yhMQ1dJp~D$-4*==1S~yn6LyL+kwh#g_gSwe9m9<*RGnoRd6W`+il;o1^?}@A^)4@DV(6q44I>i!#^6$0+c)0vWQ@ga0N#@tl_Pd^OamXQzX8?>m>h{>9bl;NtS1OEfcgC|^80JzoEKBHY5p>+|8^V9-137nuP^9WsU4v07ffbO5f*)BFk-UwQzk6>Rn-|IWbZ`N*ZwZmv?eu;-fGE=*CexTy21KpnU+Jt=*W+Fp7JKmqh~;bO)(fIb7>X+VKGS4gShP^$g>p$l8(TJLKlE$VS4X09VYWG)etNn)A}-z8Rx?d3$DNwZ?%z1?<Nmc`ob2Dfa>_UzU^ck8YL?dH~AgEiY7x82_Fc;!uUEykud?9zAB=WEUA0P}HtC&R)x37~nZ3$@(SCBhFf;IbKr-7HghQO!D0Gys^t37LNn6#o2ramBr?um7VIpGvZ70J<4njA`-@swEdoZgvg@we{<sm&R<|^VnVVh=<&>IC#`S+GVfrSiH=;_Xv?BOQsws4|Nq{^D&!>x#vAEcS4dhPjY<||LE}i`1JU2(A%8tEMPik)*ts8u=?tWh1`#N^vvf?i*s_x(_E1&DOL{USDqJOnv)fimH5pgIrr7x{C)YQZiM|7XpB_;_3!_C%>TN_q>^R-%gBELw+VZm'),
    ('cff76b696a4afd8658329a02ab33032672f292b9', 'c-rk6+j84B_FZ3rs-7n46uMcYE{%7RrfTA@V>_~)?oQUL0ZC9oOp!DJ%GM^?Z{KqOQX+M+6>lcZL;VsFI5;@>8}dClQ*6vVBBL~MIf=qx{xk7-97J>dL71<2LfmK?2V8NYl2j^yzloA7KZtJVn1?)JN<<-H-c(2lziO3`O?jW3%|n;WSRgzNP)X8|ZrmYzA3hKf#;KAuH%by7nB`BODwQbgSIFYNktbx#lsmyilASTX2`L=ylMe~MPDR4KJ`&A;B5EGP%~B;I9DmAAOe2qP1$8HpaN#S85u@yrcL`4=Ech%49OhnK=4j$1@<qURyfjXOV1$5NsvVE;+nBo`_mRUSAIS;(+;bDoyoa2d@?^Z*g_W2mnf|pxn43v0fvYR1oKW#lEf-J>G!sL<S^+3G1ucf|9FdHZD2?F`Fc-Qs7g{ivqA<~3;35{fJfI?^pq6pMr8ERrD(@plla^uP#%_#7zRlKvb)a0|I7y;V{KuFs0)qKUil&u1X{b`#YS$WVy`#jGN2#Jy5vGd6eJx9`^Kh2i=E>W^@O&_O^ZICXJ~%rc4KI$52g5$8r!uJr!l_>?yY7gvemxBU1rQv9W9h@-aPh*%X-4mh33smuT)J?{jH@WgAPE6u1zIvi)LlFQ2cGSF`)<3%Eyi5SVcmw+ZCM`c*zIP+ZFZZj&c4HX4W~)IC$mniQEM&`-Uv16FTOw`-0zbq6JcQuymQjei7Kx1L<*^>3l;=+AXosjfhS46!r72(N=YDQoSY7c(BNvmz*Uec{{8a&Y%n@|^}Jt<B5Mv~Y$N}B`D%22^7p~9IWq>fQm3Y(D;}2NUJaiAx*d1!ROK_T2g8?l5VY{9@~P8{qodJq@a6)HqjYfHz%$vWV2K|K7$jGO@-!l`h`G;1P}qC-j#T$@K~>4Yf62e!HE54f|MEk-@oA4-UamsttnUWBV0t(3BDdLzChc9~vCAJ<4uJipEI8PEJf0913sOyZ9Lf6L%fs_m7ry|O)04Bq^ONB}>nJMNC?S8cdiCS?*MugdhK5l?H9UR#6qd~`)h9sBK}lBY#OD}L{o64t<+mM!u?0x3Q=vv%F%@LHK(!$ZOgItKX{wkLa14T;iD&u_?YRh5@V>7cCO*R#ObA)9P}uP~q<#wZ2?Dep5?u~MIL$)@g6c-{04RYX$JYd{hJ8rvTxUHgASN%a6OaPU$!#%d*ZA`K<kvw-G+2<V1cu?sZ-+-^sI1;713n}Ue(Uk=Z?vf6IoNQxpXZjkiXw1#OqP_-FiW_+o~L$-nykh1!f{HC&Zw?yDFqt`0>HnrKyq?%etL0UEuC1p(ef9iIsggCwDaZZWf-agM6tG64R@srw7$W`!4CAfOtEmps2vwkbrc0!3`>-vcCzJVtO1ND|7?93IZBtlPeY-IlZwDI;)5b74V0|wI?G6jd$rqXpqX{Kh_{0;%d*;g8HFqEb_Pi)jSJE{)k<8tlHWJ=P0d_eGg^_gfQ6iVcR(Hme9YWAb)poU)_X)geq8kegz_Rcoq|tmLLO}iZIB_;m>M&B25fa)r(wGclBMPQey82+b-k|L?sZ|cZFjn^-DEnv*|q&zV{3Rb2<Z$%5SEA4{aUkCy-yIwpm~tkpDBqDNO;z2_j;X1r_}>taDU(G_Uv|>x8NVUZE?%P;NNriyG9Py9dbZ)1u3-dm%;CB#_kt@j}c-LfhR#ae1xU^-E6%Ftj`>q`@Yk#c-v|_EvwP6Y|w76Y1<9k@m$;YUB~a)TD?}Sa|c_{aYBpZq^7M@e3~Yuf)}qVu-)ub*HVsD&@mSH*34|lEf0~xdM%iG5fn=b+H)uhBl6tUty{l8<iHD;2W?QqN^afZjL0~lU^+DWzyJXS45U;^=$!nkfRPYrW-!F10jJjrV+Xlb9(MzVBZC>YAeGOkj^nUln@9&srH^bsz8X{L4t+6(&cGQ5Qw_Ls-5T;T1;CJd)!MLzm{kJTY}^dk9JC-eZQY2_i*8zLbl9{&$%3VowF2ii+;JxiTE0L71BchjS}t0fm@QHRG&+*{QQ+|;0E5N65+I0uAIuuk!U_0VU(q=$kQ+8|NCST0CYUeo#EY`qw6@U0#?4$0_oAlYr7;YG_+~stX?LPAvVwS`V7Rdviw8w!w6=#vUd#<ktHtatLa0@eBuc<nD8B_INb*KmZ?rt%#~<8zVKk0k$6TRE;isKL*d+)%gV+*q@=Q)xqJ)oQ4cv$M8BF>hoCU?EdTZRtrap3%BN;7`tVg1iI`}s%d|sX8CEq=P?V;VR@X2>XM;Cf)1}Zp6ac&Y8|BQW6SW+}VD^r#&sH<Y;L`F7%KP;F+t0F3&iDZZ9>ZA^IcgR>}%T1fbuwo#mP{FbU`b8O`mq6b$flsiL(8F1#mx8I7LTx!!`add_`@5uSu|Ul#>h-NPqsa7VW@)3r@!P}U$?@yKG0qgSu8X2&l?G8-6LKzH1){zo5V63SYAgncOrr!^5lr`B=4lB2I)kzb=Hnx%Gm=mqGzxfN8i-N@b>Svf-Ylj`6si0><jM>l*IO7mB{L94R#YR26nT*p77O5;wzX0X9z+A~P%s>*Rj~c1u$q@7)J)T0+_31I5LG?%Yb+I|7E(>!sueqV%M;;))fqjmb;tQoAvYOae(h)`2fLfe;2)=h7v}@$a0W;4<M8D8j%Z>&v&VzaZ^-}Zw!c`n{dIb0{Ur0%I_F&ObZKVQy><Ki)7tIKVa*%HQtUFt9z%!s#Y-M&9G@-L$Ln7#ynju<{cDi+8LoX_TKUFZ{%eoRzICU+fY*BF6`#{}U4&v!RJm+p!3~?s$4|%)Kaj^?e%kb8%UmYa6w<tdc;<9m%eGmk)8e*cJHBIex!3SqnA2GME!OVzyiTXv^Uchuao5aAOJMbVIAfg_Vg`7@NO<5EtBXuwv#2(`KzuA!@Eep<+FzJ_eFNl=sOjCoq1%W5dVpr)8y79=-6#{A1XKfd^q`_XxnW6IdUV0(c9ez(D({m{<$rR@cgz'),
    ('ccc75d37c4f8b5012299bf864bf48dd45ead389b', 'c-rk6X>;4S^}BurR`INpokEvI%2MKvokSaZo7j$zw4Kz|fFvj}rbwCqWvfa0+xs3sN<1WA%_RA-{$de$c)+_4;0ZaEY|I@Z!X&mi2?KxroH#u4!@2q(%#}PQb~ufEE;*5LA|$|Hhw-KBhu3t>10FN!g#lsC)Dr@JHEIEy@&P%W2R4~8-*Xf|ElvWua)xYt{!F|eN~CDmVH|T`4}bkytA)X!Mi%>x98W|{+7lck=^Fi;klfM%`5g1B#EZEzz(e!D5IK)vXCY%R7=KMyOhbpS1+^!kXTw(*Ax1GEA7h>f7;u^ITg<+^$k0S_=z2cC=cZBO`y&M8Lf&%;zlpdFd>>g%@R69XhpwA&<~(NIl*i-yZCHzVoXTGbgxM+AV%WNd!U-e~<Z=MnKvOnkqcwoC6OdwH&k@Nu4wDG>0Ck~Db)h+R$ukr61vX-V&3)<x6vQ%)xe)rmwc4l9Qb$WMajiF6BR`~LKsuaU?Kp|U!26F@T?7R66%<t~v64V0w9{?0x@tyxQywOgPQ4(J9QNxNYMckNOgE1{3{TF6qxbLLj?RXsXQPwz!^7dpfHV^kH+|1)UP-fQc|r4P>H`WmZ~%s-7K6b>3mvEFd0$PqeMw-`g-NDVg>ec=2q-I@B^5-|#ucz&cgxwbyB%&YW*ZjUZW-Gh!(lzM+iuzI?RKZPWwCzCYLh2q)@!sH?FGVXPfiAlFW?Aw2V}~;AU6iqIT>V!%8&C{ctTPeGzj#-V?LY>EJ^SZWhY#nl=$9^lj9TODR4Po;L33o|6cB$4o9c^dxN|esThpbjqLBu{^;!JZ^J{qW(;H{RzrrDJSf8L5BFZL$DJ8fam~Bo$(vgaw6Lh+s^jywZ$~G?_vfG-g@siGPkEn!CVt6b5L^<<laNGS#9ik3xw(%YNqr+@RGsYnm;C!<i}o3HFFto$UpL6bMHxCH{eI93qVETur#4;Dru_?CcJW(j0qAeS{GE-b;|XDrN9r+;LeboKb8xnQ{t~bpADteY9i9BMiL8Q&0`h0&t)G6nA~YrqRE!3S;l+y=Fsyf}KZDck6nIrVe1-wVzaGPqf9o-5U4Y;^_2g(RrW|h<s8+av2`Aoknn-5(9G#$}{h8WBSuR55tnWL!i3iw%b|DKAax*T6&`%*hL4eL<yvsoVt9gJxklhIG!$}~?an*s!ZXW_WS5Z%R;FA~Ic@P5i%5^^JzW(Li(d%J>HJFf;9K*@c?+0&-P-(tV1bmDi{Mr56Uuj;(bI{>nD~l~n8HQl)7%VBDVU)0WGYjn$CE1APx#g5<nNgM3QVKc_2LSs@9m&!8+41>Vy|7|wM$2E6DhK32q@6EUFWpcbAo96Q+1(X3Q1S*72R%^hQo+I!Ep{A4(NSb*-Yrpz(n*Jxz6LNN|I_iM=O}FYDG5ADti<yj%|1wy5?_j@%Cj_=xYM|q`ifYad(nFEWm?wwB*LI%Zl@5Gk|@W$V<p6;DY*lk-!$~L4J{SX@L9mgFFRz@=VNBisTC$*w9Y2^@}+DA2<3!!G6kDf2iaWX+8{zE5!Gt63uN_dt7X~@f~DcQZm-+!Z#&y&x4#XeU9-1sn{B4to7vcEwAQ*ejgZdJ1z~zv-)giw^}85x2$Bbm{YXv(aD?4Xx8LuzdYwKngS%VCcHiuFc?bTPU4t7AI{&`CwXOMJ+`<P$m*Ya`ZXW!>X6$YTxac7!Ay^WG!%a-(Zzt;$VBNJ$?z&dX;9a9@b&OWaFhRQgwrRFZ%dt(@wJo=AD)AbP-YsN7#R(;jmFTik@@Wzm5?<UcM|QhcuY?>Sp<>L@t%z9@TOPxOYA%>KAtXx@%5z8xL$YV9(rqv};Xn%)J6#Y&DYo8Yjh9kFL3L>Qfer!^7zn9?&^h^64kIB@%%F=)d`_<<`VMj>9d7#!TLv?3Kq#M4<;P*d)SeE83LoiwbUCI_9lG8aDg$fmPZeNky9)B+34kE`va@0gG0PaXSvl#mIY>dQn!5G^C%o=d&SBErNfsoP#&VQjbIYDEDEWK^3>02TV>xK7A~t^-IHM(~8~P59eNb48D?WmlcfnMU=2pO0bwtH1U#ytGCJoqu9b>$>6)*B`)!0G~D<?BK+=-fkl}6AA;;Zp!q1}o`^9uZlgyzO-EDj`@VPy`LJRcjDT8q)$3m{jC<1hwWq5KAfAjo@ZyjT2yAAjf8D=l&SI^+^r3O~&Z!Yn|TDa0CwlSOjEV(Gcq*1&n_pFyV&+?k&*s@M9RwCf{A8IsWwN!1gT^5EYw@!3DhQocJJ+heO+&n3SQ<z48FZm3`*#k!7J^c?G=pde^~mO3q4oUV?M6A4)X{y1j}rHWU3Ad-7{S1Ylgx<kThYj#@AhLVCDLk7!Ys24?uRswa;1U^Ae0tb7UP6Dc;6SZYm>Ho-7?yi#R`2;o1sH;;IrAXzddugNL;fI5hqr-Q@L+mM}RTo9gDm0>$B*a|U5?Fmrz+-_iHCO~3nT9cxA{g#L&65D^bp~k_^v6e#XT*WnY31-hHxRi7;=)PHyjeu!FqGMMz@=_HR!bN<B{N_~npEQvDbgY+4CcUBO)H^lJctI&A*VQyt6=$0VKhrgsP3jgyJ1l`A*yC-*O)2_#iWM3ktIF(z+=w^t<!R>RL5CUAyXNZe%(_|cJ8kx!+#tPU!4u1!Wq7W9|uQ=w|Eo%nO+_|ydeLx+WuzM_V=ls)s@V5tDG~w)1{i#H>&#i!^-W{VD%lwlI<eF8bi7F#Z4Ya9Iq{^?e%Zw-oK~a{@F--fN9?qR(^7m|K9DgpWW!s;kKSR`RjC*7a`kYSxnoQf6eCN=`-@{ujJ{s?>0SK)0auq329bA>{>nBFiqC$b+~DnmTMW?+-W&B^l6N(4(s;%POrD!cXiLHbz9F#aiDxZoRUs+J_D>^<T+p$<v}K~Sd^=7Aifkb_!Yt_%r8{FxdQSxl=S_<q1uP12dE~lHqpG?wJ@<rKrvuN4<Z_nYZeEEOBcLuM{YPE@&W19YS^L!3CyYOa~8nGdhY)FP|YmDLp9k;*XSjjJAg9t1#0XGd8HxX`3PR!g0*`>y$K1hfu@=s&xr>GufE<QnpXIS7s!IZ-8_$Hn7uYKd<!3vQ*Fp}=K}7W167pFbxebLIFzV!P`<&Y{Kn?$&4$K=Jq5U!=g|1q#rI&DmZMQDd}H1^G7VY!F3ebikWHvh-IxWJ%@Bx`d=sG4^_4ZKak#9#)$X^9j@jC(LUSktbWN>5D-T^Z3#V}v5d0TSbZDZ9%&Q_@V98djIC!(6ftwj{)!EFa{_dT7<&6loYCrU?gnlYfdOecKt?*(by$#mSO0Hus)x5jjM@+Iu9pJd6Zipy5@a$Bj^xLN&d_|h+%z&(r)vC+Xl>KXNPap9BqjJI8&R5M)9z$HsNXMoYr~3I+8Al1U>_^kI!UFPOtJJL&UFkwKi$JS_-|N&&R=?ZH{F#??o{ze!eNaDYQRTlZrBWrDGqR$2=9rZMF3((QQ9>$$&SIHG4L?AyV|2WCwqLJ+>KM4}j+_nO9cu$mx21U_P^_)j{s-*WVDk'),
)

# Preserve exact historical26 and preregistered27 Parent bytes in shallow checkouts.
_HISTORICAL_WORKFLOW_BYTES += (('9bfc6f8723b1f59426f913472b78206844a7f201', 'c-rk<eOKE?*8iVRF{ODbyRrO2zywlvONpD%BtXHWyC<9DBg<n@kR?TuA#9rO{`~IDNE*qqF-e+qyXrX&*34*L?!9y0XY?&Q^SBrKuFJ=4GK*&+XM5f_^qn#DuRR{JklRkcA2H8omK{4+oL&3j<;3-`nIAISiY?baXMy7}$BXdbMl8N?A{P0x(B{oG&zkaGc5H>*i`m<m<vJ4wZ#llV7VvQDL=k>QyK9Wuz89lWw2LvV@fsfOS%}x{8>&4I{aLWf0@0C~>&U$K{yjT);)~g+8S=@HhGZW;=*7{6g%TRX@@(#!j%Nm;e;)D(!%ZwV;%jgGk(dU?i8=jXOwHZ3JSL|StMMglBGJg1?24&dSbuF2`qN)ej}B|bt947l(VU`Yy^%g%h3l`4dZReuy67yNd6DURyKFX^dGXBL*le~pMNRBXIc8=~9S`%vthYpQ0fzKn0gkeea7S(QvS8-AX2{>pcvNU@UvT?UFT%*dEKY}zP#6N3V`ppuT#R5H#XN|b0l?K%?VH7h5(!!t)cUr!sZ4v(wc?2%PKPveC*<SBuNPY;ortz_Ev7>9KCPIR$>MN^`Y{8^&@22Mw`T-97Wl4X->6y4BEo@!YD>TiFaPvl{J`Ga;9HhuZ;h;n?X8C!TVrdxyV+^morj%`?FS=kr#<SZUamm{2~2@}K9Ortq`|MSdJst9M^5aAH_b7hSTi>sjzUoJMFtXrCOS%{o|S?|ohUYKECgLSp!0;<lO_>h9C0&QfC=K^=F}haTN>`NKhi43nsUZkN$mS>)B>T#Ccknpy3OZmqZ`jQMU#-vqWSu4<#O0)zK4-Nohy{kF(tYrYMQ~#Tr<xiZYIW$N?VBvY)Il1Z@3-Hre%#1LZg-w$K}m85!l;YSCR^+v^UKQKZ=|2yLfpk4fjdg5`w+ppi+=x!klb>I(6bNNT?}y)rm3P^J)2n$H2>&2UNYWDwQS+-kV{esJ4lX(3%147-+#B9a#}qt0uUy5eGIn%b>@cY2b%(LO>39M*6lXC6%h;-c`2FCr^iiqi6lY++t(@l56Y;1fuVS)+`EJBgbn6H}Qq<Jz(YmGf$cMGuH9L560=y*~xx?_~dNw<gt;y^ey|vd53jKl2js>jeI|j;?N43?9kU2gY7wUIfIau%fg!%JcO)G`jf@%!ip|jXVhRsjt%BV4fN6g_p@UBI~xH6HUwZp$d(41g)Uk*l|aa_29YLEipr$tV?3^<Eyj=%uH*3@_0ydCo*(<3W7q2UH@CD#6XtO~u3cH~jMsNH!Y3ID{UT<f3R1^%fX|oo&<{gDtQi@qC9>Gev#u=1wMH&C>bWsyo`d<<0?P@b!YHEq-un-^LQo33<Tni`=2NIJOuU$XPpASkb+i-nL^HXHNAmA0RJ`s{54rb34t+{BO)G5IiXtHNgpaY!?YNc)d-LgFaGcaV#TIgTSXc(FGE^;w>a|+L-3g&rJkgIRz<vi-ZSe92n*z_)IeuIKSJ-dBxfP!CxIVwq6`-Gtj;VMK9~UryZfo2d2fpJK`&aYp71n&B7GYe(F$8m~Wd)8BDNSr^DF|AgZ(W$KIRSgWZ24Clgx@mmCnGiH7NVBgdv6fy@I&W6LR&O;jh{IfWyp;Ce$>Q<cS7HLWh9&3c-=7eY#Uq(Ev+DMm6qAM^2TaX_h~~J4db8Y6DNK;8<~57W4<IdCc58fZ)}*Ij=AyB_|TYgj6LodPx=E5P7)ZT89Ls1FWEq5aRWUPWS2Jlv7PUMxN>3JHb*nZ9S{A0LqV-+WLB>?sj!xih|(u}&?jr1b|W35UT0R6($9j8kW@E`m&~GGZ=>C2AlCG~<~h;6TdVha$;2kmHisyymr&ewFMW|z&RVD2rvEzmwqj_P)?i)Nf9R=3a^NE5en^2@FWZxZz^3b4<A^$I_#+bVL$UXV7ruYllWe3Rl%64!A}rL4d#*JdjV(6Zm2>%pgj78nz#2mWVW0GV$*E3pc$0^t+<Qcs1auIRZYpSx0VD|5p0C2(gBdusPbDByp1vy{96vHX%mXi@cS2Cjcycg!diL}1q<?&LdN4RT`IiBN86_Ld5J0~5_2I!|(L?7!XQ#cj(QQ8{(7aG-ha^pUBtvSs4Jdo-zw93lhR1t@r^f3N{1gApdTBb*FuIun&zH5jm}9<<w6XaLqS{&=e}<9s9}Y^Agj6!so<=BI2SlX9(G4`VT74n$<hu*Pp48_B<jC|&cy|Frk~n%nC|i<lV>I4>sLMyFUPhhdr4tEz8+vsu2peO^j_Ztr>J}sE7f^>$$K0pDX@HKLccQ<jMVvBf73M($FPa4uzFTIYtyOAch2Etk=`EP->C-(i*?II!=#T_fn@H~dn}FA7j&;(Cpfo9FB$&?Bg4zj#ylw7S=H&JJ&GrYQAsgS;O3t!g0F1CNdU9>zHwW<UD}g#cW!XmIJrSjbnCT##aWM(K4XL}di_}t!)l$zbBBR$6>tBkK($&cB<Z2+@TJo6|BtVoW&5-k+Y#@iGg5pf(0ieI3CM)KeVvf358FQj>eiX+eYJ+N=ErVJKtl;l`;~x-#Gl=Ia-s_ajFzp~WNqSdIr%(+u+aoJPAyF{<Y%z0<0iwES=)%e=3=UNHj1pV9C2=(*i6Xo^FguMrd-CGY;Zg5Z2u~a-vGiAX;neW2<j}7RB!Om%CIq1UYekq~YqVyX(d%-lt42hlj%29v`BnS1?1H=olKZ#Y-OWv-v=M<wG#a`7sHhOZ;E`g%P@W91D{B<_E<9ef0y`xULNByv#(9dCt~%M1VAr&H{IEW!_d~kJQs+k_dWc?ic3;oyJgUc5kJ>y+#gHn_$)F-(PW+xGa^$=8yLmc1I6dh<sZkS>L<BvF6KP>&rQfyvPN$;?Q5G)|TO)sb)0-1gk5VjBeSN{ZqLH#1$*AwtMgmXJl(93j*Xv-~WLLn#8yWv@gH=#z^Mbz{JLjax1Hnbai#=740X8&JC_zKv038mYI;Z?`s5U@q1VbJSg*c~nG#grDJ+I@Cua3A)KvJLP)JPjP4620RRSa4(k5`7JIT(!BQrtH(0o72=q{@FPriW&!@tf+K4I<0@2&rO741X<~E?F6@mf2d3qf`0!8NZP~2G}q1*Io>Oj<6Ht;|cu3(0S!UX3RHF)1RWMV1NZMKG$;Q!y+~8=xlI&Hh>By%?5)6J`4ltTg`VW%bM3AEMPQD)+&i6d8|W=x`s(ozi<58(>8t(!g#A0$3+`cbLSZMvtFA9@w4Pf$~8mt20Q{(!DeB|Xr5bX+(az#12=U_)Lk+;htr8{U3C46_&_qtls}ibkM<tFI2a82k8=*{g4-!|R;NqKdzMHlu=RUMSL>`tUf#TC?7)Lh4R$bQ=ia~s56OwNIAEdtU+|QFlFw_2r^{xBaulIufL(YKJ;MJ@sg=XZ3*%awN}Et|u9|@#)H?P0Bhk2te}$4=E7UirLI}+D;gIk-9In?5&BziGqg5hIm({g^knzms;V=nnLDD8sCW&g(%)%Gz_tf_I{pjS`>G9rvzm-<5uSsnR0V(;u3L=52QYeM`N&`lgdu`o-FSGByW8cV_6e4i)xhCFdiWk7dBY6B-ug8pNX4AGd*dKo^Zgc4b0puq2QyP>?f>Ei-SRRa0`$M^!#i9~Q5^m~Sf>jzt9lh+I4En?0UOXQT`lo~8$=Tsy|3r}w<V@>r+!bW>cIr~s=oFM%9`bt7uEIA}_~vgBzNw-aRWzfDW>nFPDw<J6GpcAt70sxk8C5i+ie^;Nj4GN@MKh{sMitGdq8U{*<FiIHo<o&mvjB%SoO8#sT+QKhd_oWYB=Iz5?(PWoMWDHvbVuK(`j)V85!^8D7925D1mqEU&2%r_Un3sz@o@-v6sH_I62%`(;X1^8h5g$qJM_{@5NQhB<$adi&G};mRZf`ke-Vh48PYXA6v!O+gr69tfn{I9sUqSaJ%TXGJb#$dUDEK!AG0Wk+*a$Ecg-n{pyBuie@CtdCzd2cM~C2i$9hbSuG0uffw-VQpY$I?=RZ5m2h&7fDUsxsrF+*Arg^saq%UGNi(l8*ufKhGH0=MgzkfD3I67SXwhpO<ByW?RxPC9Up4L5mdaZl<aO)6}x`!D^X^DRXD*niRssj02YoS$&;yQcuNbB(XdXY3<kbVYk1N=B1ISRmiMEEdAY!X!<h3_^5hl*K8@0drH{kJ-+(7x+gg%{{5L?sj(ZOJaV!;>g7pCr=-y#eH=^lU-Zou5u_Hynd_;8OVcWbbhQX>MuS**Bg3P%D=Mw&M9_Y@J66pKSfUW-;H(_bh72yau0A%%;#J+4mICynRD{gYcweD~Mm-x&eDh>m`wHc!|kvOR*TCPpS@BF4`o-md05GND>i|XUKB_t5z~4`6wd8bQVpI2xq@cQz%&(cg%c08HY4YBEYl>Siw5VBnTGq)h`F%gki%Xys*4;(qFK2#Ak>n#6A-ytm52Y5Y+80bIkF@{Gi2biT%OZ-t*y$qsRRmn-wAM;u;9&!kk!;E|K*`858MpmJkyhgU;keTe;e(i&lBdv}mbmUq+Q^F{j{2c$<70#5d&|O4~EHYeQgcDV=4yP=e}Hc%Gp99t!||<gTL3jMZ^Z4xiL6$jddMRGSi+KXIFH+oN{ZwvZgKHJMDdH#<8I#}B)kI}cI1+1-9<cRN<OY?FNuD9Nd^%Zvxj&W2I8@<YrEU|BLB4=sM$*xcFKZf|ewU`l-QVC&%yTpxS`f4ZAnd}~bdcgKG4uyi)mgEp6q4MT%;?N4K1B4=hb#C$WqDGPA=6{go;gFfD1CO?h3d@>oexA^AP=4fN9-QMbgICeVSZo4}g+ug~;9!++-<<v2Tq9SZ;fe(apXQ8G}QvVvZI@@`8yp-%vX5&Ch<igs7bmY;OhfhI`27s8!XFhHn2(W7$cTIQyk|tnYk;DI@to+T}vQm3$UGmb3SkE3vIdB5G9PyVF6O>u5bg3$1O(xPLSHefAHk8K|f;e=IhAO^19&+-l|Ig$8K2j2g$Itf;Z<pBlL;QEr!o-Xugrx8I^DAI5Po?8QOmqESZgJE=4v%a%_hzxambRlyDWuFw$6X@3Xnom>^U^CdqlqvP55-aiVU(NBUyB}oIeY$m`1I&>pwoiLlS+CNF>^6<%>dg!dU5=`j|{<+{(k@9c=6lG+OYzgJ3)M#m7UI~b+0(aBD?yJa?|;vt!8}}r}$mnY(9_|sxahEO8W-%L|#F*fB$~U6+Sa>UVyMn+TN8VN3$_*jtOFuqJO5(_H04SySpb`hI}?5cXR6A3U8>ZW~4!@9<bqvZ-b>q%)DX$)-Z<DQd6dxnQvoZBD{^q9Jx!ONKxB@oquHt?t_Z1N#Q&y$~~xh#1hWksi@73FxOvxP^`ed+$bqC1s>6JX{Br302fhN)wSb|{p*dwEV`yPk8}-%GHt2Xd_?MyhbwWYF;@3B-pUHM<`=5Z1oIn3=EQfAnMC10;u0=3>E70+(52QMPxB=rrPYl}Do7WEbhSg`2upe;n3a{K@Gq@Q;D1ZUNG+XG5-Bh5MWSj+ClW^3L*(f%?_=!HJxj&9ymE4RPOF(X=hzp5Lz$d{CXtYD0DZ)Mi?@Cgkid`M`DkBanVt@LEY#}X;%?HSn`_ZkElN3*WNu(7h$uP};!0GHoMTFEj2+jBZ{|2tj?<`EMl?)17-k(T^%{JX)LEH%Ax80y^eLF{GCO>9jR@Xc{2_^FXp(20SZryq;$!$?>R$hxY;rUkL88!t)=EYxUwV!Nj-ls3s30is(+(Ib)g<u<AYGJ{Ge7+LX2ZAaOq^3-;+z5{_W@2&tI7NdGlHf2%P`dW1=|aPy>RM>O?FJTY{gnn{$xVYQ3;?3!g=Js!<#}qggz#2K!g1SO;!kOl~_r0#o}JRXlh*zC~q7faeyeyn8K3eGFFzCm>UWIDRg8J@D#NY+TvJ4=#R8yX+?tal*O=r`10W7=<o&9VDf`WCzF~+Uf#k7WXGVCYorf{*zrwd-dVKxVFITioJKfVgkUs`=ON9@i+Y)79A`lYgP=7rWfK{Efl0CB<k{nKc62FcOikf@^RASJER<o9OK+mEpg!j-HK!PLg59f8JfKgYM^<5w*k96~U}l(E9JgflCq&*Cnl@L*dlJ1anvu#StZs^JK*l;#QUjCo1gvm$;v-03KjyReTC=4ba%Df`tsp-5dmQe9PVbH^A^HV2HDfXz@V0YansJ6Ln>WkymmFrOUk#U~oNq;PNvB_1#eT|k`ucLZF)~Cbs1z$!qMv1mLI=z2dRSHN4Bo{AT$(knGQYvp+jx?rtD>DY6}>_JYT`Opr<LfqT$I@2`Qt(FrmpZeOAswF+Lw5ni6op7_s(s8ov%V8D@)bP&3Zdo$y9+)r>oE5Wx5+#ezf;VBgw^HsE_qN-I<1UcUQq9^(mgHePrPYF(_^rHLdZOZcqh<<+>@8d;ew3?=C_1v^CsJIHkQT+aNnzQ0Ox~4OiM22N9N^EOm1EE>Ql4dpIrr;y6DUlCf4ywrX5#UKoH{I^$2;NQKj(tsI4{w2Kl3dv|WEB8Cd2(1ue;uIH*uXRJy59K5Na8c7}3T`wd*&;msAN>(EYK#YNNrvRW(#8q!pq@b@4n&C=I1X!}tJRIkC=vhF=J8-gbI+MP_zroJThsS1Og=XR?_-V9lZ*{xY_Vxzvj=H1CXzL*#x5qZZWm^w6tj+D6@%Hw^ok@AjQUL9?OQlP5hVG6d330N;Df5?{Vlxl19O0zV@|B3S(geo1Az+tnmZ3L~RAKW;=C11!$sGe<6^d$F^UySJXG{{#f0&xnqeKL1wJ95EEpK->weF+hH><t5EQgcbJ>6jefn8gnw~)TJ%QE%IjgiJ8iJ!AXo3-Itl81Qsg>~hmgnPHl80ym0yEK+Y829%MA0Is48?2BRRC3e!mkd?TCybFx=S$^_>8hlDXURMu=d?~uB+Y4`sOD@AWhHd8!00)Bkf!FXLPlRPRRo^k6c9AVtJf7_{?!RntxUgT<coY1A-y$3D8mcx`capCs4r@yj=}5>ouUR-cHhrO`T_6oEs4!9`Y{P@FCG7D@bu{L@zLSn_mhJ`|L1=V`uidQ)aV#xAD$3dgHHaN4^j}8z$Ix+OhUONa^Ihb9hn-nLRVtvQ8!u-f7bUW;NI5{Z)s$sVwElr|3=ps%|k#P5J*>@GK|#Ip7r!60;2kiL3Qy@b@5Mi@lSQ}Pj&H6b@5Mi@lSQ}Pj&H6b@5Mi@lSQ}Pj&H6b@5Mi@lSQ}Pj&Inf6-?Qw3F?LXYDWl5d-p%rOB1)7Y&l>r!u1Ytig((HApWyFWzFYdcLbVD4il9cc%U;9CX)1&$oEr%kR7>E{KlGf4y_^pK&4DS@yrs0rO8@W^&+UB7Dv1YDG$I*;z>G*)~@_s%Ux{3rJ4alpRnkYq!FA8*$K_!9(@NGKG(eo#Qa4DAdkxX@}IaV@2=P7X5keluok#vTLSAc=}c|fj@j87MpXw%$-2`lttWfNV4=K5h^ZWpruDsDCMn{PBD$8()(GEd3p)AAC|7()-D=@+AH!>p!Q0Tii7$Ru#Xs)=7PaRY&~6`=wm(WOBGOCPuFE+U;u8LUfOi`UOx0acPdKG0Abqs8c|YKBW9|FPC(WWAdq<;pFvS{%}iyCk{frDQ%Bj^IQij=a>|Tom`^^}Q#_?}3j(RldOp8#d1Fo1uK!7=c;>Ib%P1;$on0Qy-%`A4@Az5k^zpM~N;2V&Zm-ik>L7dvxDeYJXT@l{u|vEAn@`ATVlt7^Ws(4H^Ybvn<X{q6Rq6(#oX#|tc~GV^si^lSsZGY6QJtP9`eI7epR84_u26j@NvM)R)A4ae_}l~GJGMND_!V<O=kTA+%`D3^UpX6;+R3AlO=^J#E!)Y4k?E%C7kzR^AwDKEQf6J=<Ui;oR`{E&$=znSRtj#J6r?bhr3RV#kA<nSd{)t2^LV~!8c+2ZuIe*f|LvdQ`k%X*v`Rm!(vPb2qbmKVN<XU7kE-;eD*dQRKdRD?s`R5O{isSms?v|D^rI^Ms7gPo(vSX>^rOuDRsJ>W{5<66;wxi+p){mqx+6bMKXjrd>|etej6T-Gg`2LQ_V=GbgFHQZJ~)+4WB=FFqr;kr5Y+#d5|QMc7Aj)7dLoiRo&h?0J&TkhHBlXtI0Q{x{nX9DLeW*26r@JqS|Sf4(?O&v<Vlal_usd^Z%)U?+W!On%n};'), ('987d8f0d198e40211ab0f33286a55852e286c174', 'c-rk<eOKE?*8iVRq0l^)-B^AhV1lW4ONpDXNq~aM?jAPBN0!H+AWMoQL)et>{`~IDNE*qq4S^(0S3Re}ni<W@y?5^WjDFBgT;>Lz<FJu7o<`GvX*=#H@a&Q1UAZjK0%qAh+tyr9Gp)$JWZIP%T#Oy>O7jBEG9%OR&NSb4HQNpG;DlOqZiiavO#_S7S6p+#I@+NbFgMaZOijlg+jz_N+!db%6FUs?GwiHrn&r6>8igH<X^vL#XiWpWW?fV5S>R3mj^^`@j7&$y<4>QoGdnt;4(kCM4`@j3=0+_J&rOujAf{_E$FN<)54^L0g&1yZIw4zm?+y7hFiyniho;H7JEp6NsYG&o0h^FFvd0}hbrb8aj011-kK=>=ihjCk3OE`Q)U4K$$ID>#onEcwCtT&71yeUPJh!7whf_D28f)wI<~py5><PonjEU`Hewg(JFV4Y`{>#Bp6cX;JjaueU9mfdRhbaqlt*vurU8qGE*`G$q5CXXab2PD|h>bcLfjW$sAJzfZh*>B!Bn8M<>v3a&2R=TB<p3xd*&`D`SGxhwlUMT%XS$%)%ig9k<weJg#$GTP(E9Blw}#B?`Id1fysdzUAxUMI;6}jGqF@@*VnKNH3j4^cDPchKJ;%1L<t(NlVN&9z!J&?qe|b83YOSxa4b!wXhUT;8#<R7Jk-6DkZ#Avfv)0<?)1kT59JXXHSD>UAGaw;07Hg3N#xAjXkeTm=cH{-u^${DJQzse>1MG$K6eI*qbQDiLEd{09VPsfX2)eSdTjD(vHwgjbkQwm;43Ho*Cf<lGY1q;JNUAigE@rHhM4sn_4Ul_euuB`GTWqE_yml>vHwoA@oUKn+E`|+fdl-6?nL+^_L!e8brtV+QG;>YjiG2L9uobVswkCe_9vee6Eou}K8nqnT4y(Tp!6aw85>z;$9d4X^VN{PkMvGf1xR2Y$1iLeh&IzX$?JE4#lI^Pv&5(hYOt5RI8*RuiIi{tZY4*hTf+&WkjV+Yl{IZI<mnnU|csb}Fyz1>|h&1vpn6f(oFO@VJ(=ccZZMWfHN9UgVR5SK8<5)9(#X5feSwB8FIoj<FUYzV4J=c?$e$aliKVlsMLsE`uL(hxCC@}rHw(qHn0kuvYra^LvW#P?p7C?Z-{fT1j+zihhdsx#5J2lM<Yv`p0W?)A6cRB<JEJ&3aXV^7u8aQZOms~dKjN}C0Zm5iVKE&fn(qaVG>)0;qQa|;H=X#On+E%6dWPL+vG}c_kMwLs`nX+m}p#u_35ZaN(tH8=l8~A)n54|Apf{LD^S|CfCy5^;6JLb?~dNnh~)U`4Hif`IMm>Y$6-~DuxDFmfx7wo!bM{EMUK;tiF-{bO?rjB-eo@gdku`T|dqT*ebddR#NFeoXqX;NW1W*7pYM{ESDx1vfG?Dd!Z{$X7A5>murL2ene%0RXl$k!?%bH;>T{zN}QAAA~EwZPhH+5~tu&+y|MxB`;|&duPAMb+7r-U9mZ=$MLYvr!HM=(fV#k?+}VzJEEtZf?y-auND@6hTfk8m4bc4qL~z7JRYcdgi&|7-Mj|i-vc}K==*)Njy?*W+8H^-A_8P4ll6(%T+MFqyNev=>koE;)Qi=csuaiQ$617`n#IGV_D3P(9-mMN2+d(OLrtE^@KK*Ueo_&ys)E})1k5B+s0dxJ-qw1=GvOkY8h+K^qbm*VeC;?f6?nJa1y{Eb<1|oy72}w@*8NIlU>sAZ_R8EBu#VMwmzKN&S>EI3|e1BA+u_=PKA}2M5L0|g_2fjHEYQj)v9KO3H{932yu0tc*!*EcGsFs4aAzfS3e`#cPiCxH=fuSD%=2N)dGsU>LxFe9#?6#oAh5R+m;XQ&>GCE>d#%-NDQ2Z+|LP6t3`W~5LkCSa}-i%HE&4rZov2c;N0^rx`K_=xDGIYj(~-_QP(ji!;z^CI$|!rk-|_-2Z;5??r#}QA_}gva1?uwD3gE=LQ?f_<<W-(VaoGmka;kC+w!OcM9PwP`Gf6+`pqoxQhFx@RrD8o{g)@d4vu<<2giH;gQI`zK$u>z(R2>vrLPb6p7S1BPg`5fjkR|3X^!T(hBqK-(j^&E$!tK;TkmaezdtzK>A%$972u!vZ`w=U4hP}&1bDuvRQVjUb)=lkRuI)zs`xVq?f)`Rk|3mlsdg1YQ92+Z9SpCbz*MSpi6`5gA9RI!%OOYhOw7A;AQHsU^#jq8bQ`_)>82_kp)%`Ll9zVKjaaCe6+ftrY%8j23{*ECNxy+Q^eW~)0Zx5%WPjxSg$?4AVIwyW8hG9;U@9z`g|b$mjpce5lB7Flvd1rX_+)3%FQ7vbSZ*S*`>%agp*dDbD}vG_nGt6?6Em{TVdXZBEz=mk`?TJ?(QBgdvQ}c2)f`~By4@9P<G&ez_e2WR*(r-Q67R7n)%i^O!IbeysBK8yrClVKny(gmZXOxkE?@sboD{A`bSG8=>DCa>v>*<mENKRebwvX)G!^7$G7A9p4LMmp*93Fa&8;!V8)rwcU7|Lq#_2Ms6~_wxKGFXU5jcf-zGU52(F~IgGLxit`E+vCusU6`LL?G7vriW@(-<JC@`esf)7;=dbyqJi9UF?<g1by$h3Q%L<VJzb!tQAR_ZBI!^q0G~<nX6r=yy4iKr=}b9MImCBuub1S~Jb)U9r@aBcf4DFjVn;+I%OvAR}6E|7NqjzOENGA`tOLL&qED6(SfsLM-Ugum`&`hoR@dja138QxYNcLW5?UrD);*5<PKtO`FFHsxx{&q<bWEel((o@U+!=H>>l=9vfY1vz>?`S)7qUdBPlfT}9-Gcj<Tic(8YT)O%5(CM1andIBfH!bnShY<jI$OA?|eULdxH-srkJBc!$yEK+@S&bz#kv>M3|*{TdVo}ejXXQr=L!L-S)fQ2{I|I-Akpwjv|`#7@CNRbDE^N8nrDklRhXrxer2HdMS7(jJS_~SrsfW!!fJQ#3sPVHzmw8m;y$064haT}kcKFz6?G_2`V31=oBv|t{mx~VuA^mjts*HQshlg)(6f6S+cW{L5e=$kbn%j^h=Vn_^sC7mu=8CoT^wQ2{);_oYVEq?T|U&ODS2ml>oCy2)*I9;LhiigyguOBBrc~#B;^I?3hWXy+oYS_U^|L~*_6-<~7IthFj2Ex^t?NpT2uL4-WXc(_m5Ka78g%))Mlcf4Y|BtI|d_REkR?!dhHm2gv(VwKf)^*}%iG!BQHC^!rYy+xbvoK^7N2V}tLM?WS)>TSWT{0Pm(~)SM_os8Gdpyg8KgXUWI5cnTT<&%?;&V(day{)lf3w%`_nv>IznXicNTO(~kK?XZwJteK**rHeTx#qi9K7*D1qL2qVPC^_oJ37j_i*BcPn}r|8ig^!wnO#WZT-eEu=ZTM35NrkIM?uX1mvxoA8xrH)VPxp-u-(yCKtFPElro+Jhb$|DzC$B{9hNQ6HM_Ssx+yz4n6d;?t6ZvRjqFG#&!J5Eul)TzD5;Xt63ckXwwY_t5sdGgt=I66lgq)>KcIFXlk)w5C`<24#n{`u^$a14Y{m7mOSjA2S=}t4|jHZjihpQMX0<8#fkT2_zaSdf=JX?5-KyDEAtw{Q~U8p?U9JaA@(SqD;54qoxcH58zM}>Q5a4wV!k>xQk%s1&c&lrv{$u1{?O+3dSUxM^daiCFoG9H?h;o(apX?&J-PQe9Ad)d-uNYvJ%tDl-u90Ay}|EqUJv@c<No02WPiVRBq<L1L*ql#=9Kqg;!xM<6dR*BKKQixr6PA_;HwOLm4UA^@KpxB%D`6{_$mWmW#Fp}e3gN(GVoOfzRJK?8Tcv#UuEE{41AS=uQKpe2EG)B(`%@5+SJFP8T-t3O-FG!9UjqxH;z3`snb1#ec?Y)*h6&^-q$Y$pz%1EemC#2E`w#;<Z)9ye1DFJ%I8N?;EkLx=vNd$F}T|i^X0a4qv*g=BPIfa<2~!|WKPDH%PD%S>Himk&^2AS)dw7zqb~O`qtrL83piwWB&W*}ufgsbBs3d0{M+BsIF8totEp$sE)3M-&<y)XZVNjSBt*x);JC+n3}sIwF`fqu*FtYU>OF_8adMoE+46a$!5<YQs#hODs#iNNdOTt^|8*61>f8GVgWkV-yC?m<gZ=q$t5BZ1T`ba1S088A(|D{-uklzNZWW?g^=tz`4gL>D;~(iySs;EZEtE=LT-CO>l@5QZ=E>>}>4o5Oz^(0)g92QS2VOITD$oov`f-hO#z<?a9kbB1$~d@;gE#LQ2Y-XE0#rg7Q^4hr3qMYhVB>hYpjDvD5Z*Yb=d;tv?4&~w9^4?m9_{S!zRWC5IWMWwE^5Vcz|LIHh|IH4(t@`7M6vQ8XM5%~<PrdXluRzyWc5BM=P}~tEZ|Yn9>L$GTRx2yFGx#(L!3O+6n5gOv+P031lG8eRTv?MWGvCL@?$18*NEpN9(gF94lJr6`1F@yaD6gm=Bb-2W$1=Mbel8*_gO`mfWbU5@TW&hES6w1pPTL(X?TDbB3Q(|B2VK+zLZa3Wz_E%Sz3ng=jNKvI@;}@?7SYlIe6a7$dOD2L%epPFm9*KNjpmWqRgWN3JXXV9#?yOtpH4NlZOS)lEu(F$qb6Y^gow=lT{i8nhZAaqwC^buWan)8YY-_LZ7LA8B@qHJb|!94mkk7>ejy-$&lMFwXU+Fp4&!-pn+eQ#Wt;Bvu&Bk@z@xT$D8Y|t!JZW?e(o^C|z%FKC{{_vsm1VJ_rNk8|!HL(|T)7F9O&;CI)COn2(DVzpSlqZEZF;*S0VvHh#MCYzrPNwuV3L^$oT$B9&yzditzzHq?VMm$fzh-U#}F%$fSX9X=lwuz(zR{{h4MyQaqXSimpCHXDzJ%?-A`u|8beXf`+6AjPd#yWMOLM^<}0wua-ab}=oEpeb_4497ll0H%Rr3sC<GZL~JCRQgu1dXW_d6`yez1@sISem7vvnNEPKX0WM;8%BI=ZQEH<Lk*;g8J84XIxi}J|DmYVnwS@?up&}3RTAkE13a@s3yKLjTBdZNE@_U(!u=!VG1o0A4KV;ssVXH^d^hOJi1gmS4tu*uk{%qs-q~NS`($tExRdtGrz8L?!W$2-IKvAf0M4hm`Z%*VY9NM3j;C`yU(Zh3(Y-Z7j3?tR5a+bM^u<|$o_K4Bo)NOgQaL?6poiw$k<o7_uU`*d9vt^o65<(vahE(BgfCbz({~Tv9KP-$o%X1=+uJ*w|8@*AEWu*7A1(9aB=c!J&W|zAbMr^BbLO-CGAhqV$l~^nnLTk;lZHfNVa|dK$=|K*K6#Sxpg)BGnS<t30lBl>2&W@lW#vZ(g~JU`+p+l8>2!{mh=Hy{70Kw^w|GO|eI>jl@&VhMgbVn7s2SJVe-uO`ecKRum&S*Pn|2?f5koRxz;iY?;6%DKIIlxR+o1S16=fb|J%Vdz&V<)yMwsa@J1ACQU91(9865rSxv<hPuYruPsOrjgN8Z(1ZWe7rnMbmQT$!@eD>ft*(ZwBI)EKM#5N)J|8?y^lXM*_+Lu2eYNY$hGIB^$;nzWa-$#to;$J1;H&+&G`f(p`)p#oR|F_Hzn63mLq68INZ#_(U#F><XZlvT}&dl9Hw(20N%_7H`>iu)MZbn#ohE~`OZoY88=_8ImCXKV(eC}PN^DL@};zegLtb4cLFKiP0sV40rwS;S3^-=lWiqMd2cmMsbyo8XDyDG0IKV`64hk0gA`_Kj@Ej;<ewp=B793<-vVc-TQY>|!U;XUVu*^E|}s9tjtc@iFzE46hIgpNYlAu{}l3trBZ44BUMVJ554O56NAJ(;?&+Eoh}+l;WjlDCZE$7=#g$TRhr0BdI^do*blIlLqMp->oI}gLcAC9%=mK5#`nbys$LLkPXu9LDx58tg~}%$M<)Fi5JwhL%L)zQhM^nV@ggCa1EhB484zdldHbaHTeaQuw<d7bFD(=HPd9Vy0>rYN>_b4wgE`mz%OP@SpgLNkTxuz8)+yL=>I(5fY%Bn@l!>CH&o6lNXixGrUt$Jw|hqi`){D)lebj(6y-Fs(j6{8D*}OCA$vanf2kw!)uhD_VmJ-pBgD}}<buF`F`#+5VK)u(;B*(E5G2Z{Y#@QwHz;)@es)=u9u&>kmlL>X-Ak$cb48yYWie2gGYztpiVu`J!KPO>3ZPG*M^djJo20^4(u^Rrrj{J6iT6g2TM<m2@r#wua7ub1_g_$m4-(y;kgggZ=h1Q}m%iGLDLNrIdyC^@etc_h^is_1{WT7T!d`KPCf83m5h(U`GT^c^qKdtWou0K+vsc63mtt;50*@ZrK$)>56+2}KndvFsBoOlzw<5Pictr<`JR>kLohf|JF`N{Ch&<i_(b2?{7+n@^HL2)5lGNjPgglZ+$85vcn~^;O_;KR!Acla^0=LJ45C&0@UEo(+=1}_%Nb1(2K6Sn?r$Uhd^Z;b|5N^G@QSoQH`xFYE@Ams#ci){!UiB~LT!8m+{p}(%m&;~;>$72wMs%w+NGsFL!wKW>g|*%#=Ot+ke;)4jSd{#e9#6{knH;DsY>cx^iw~#Unbb8Xu!9}kFY@LvI~fxAW<=I~ly9CJfLhw4d+od20rN(Npl-G4V)lJ^UN3{(5~R@R6G*ORstkLis2>@4Q$snDJn_Gp%SECE@I17%Mi2lW14q{ZKyFOP-l#}IUmY~Xm6BkyV5M0&&TQxtpH7J3aP(v<oU;FW8#x<WopOK}u}|ff;ik3GZkwB%YpgwN568oeXKd6QS%|f6JY6%_H@8Nco6ok!#o=`h<7J-_D9re~J4ywD$ZJ7o4an;_brI3yUN9xwkQg^jV1%1dI@)>>HDqako4G=C++VSYZ)Ewlz?Z9;MS`)M{R#B^VJKdu0=cZzCd{g_xZT}U)6a_H-R{jr3FF$`^MK~i<&_z@bIEeED7BXyK1m>(q=pu2<Q80a;<O<<H!tmk-oHks8BN4cC!#M7Pw(#RKi_-4)4xT2UcomgzGj?zHcOOzW?w5wR8@=Bo1ta_Iio=<@^VI#Mm5uBa8^KWbL_q2r%68Um!rOKm_tQ=ed_!4T}j7(dODUXQ?Fe5D&OcyE>Yr&{hSNf<lRT|15b&gHoc{c_Qylt!S)$0*}HxVY5l8y3`yC1hyU)sJlKDJu;2gZ(O$pz>%aTGU7qKyxAZUf;Uu0bY-e8=QoaDXabsdi(hHRNeo|zMT*F&*#Wy^4qxA5lzMq6Bk9vewp;j3ncUbTjx=gOTm#n;(th|@3yqB!Jm#n;(th|@3yqB!Jm#n;(th|@3yqB!Jm#n;(th|@3yqB!Jm#n;(?2CSoN4Xy&cC`KVKF1@kAWA%miSIv2Votqtf6}{&zT!uC$o-fk=_X&~iGi1h;PSIPU*WSn$tN=Mmjc~B=UQH}kRUK~`^Pu9TjTz@088QwbFL7|!+|dK_}*^xc*ylDw{HB2?zH$;(2381jd`ph0TNFpFFFt{A|u9a4;~wC%BSK(Z$-zAi`w1d7#zRbLW76%y=ibCsdk1F-Mmmajj7y=k)HPZB>Bj%JI8dK{kM*h6yfOy#f5TnLt-}LzMDB1c%MZqIr3b1zz-D{Fz}P3UzCp7NT!&?#_9buX<%{zw=tG3-&XFzgxSQinP4^vkn+1h1Yox{EX@HI4z<-}dAyI+v@cmeZCzCt7J((W{kloh&f{z<!^~ktF#{0xYz;3ds^K$LLT?~zNI3{~mrY@4I7Vu6gz<H0@u|M_%&PdVQ!!<RG|auv&E-$QEkPi)S<U9&E^e$S1gl@@l-%qsttmxiZd}cx`3H)3?i{{q96x^*Pf28V(gmwZL<WR!0~dTd<18j^H*Fv9z-Pdf31Tv#RMz6ic>SC5(D=L{8T0b`xr{D3lYla#OHz`o=;U51p?+ryNlxp1HHGmDYmB#77Qe0Bm3hv|v~j<{nTu^^TjE^t_m}28Lv87jjG}`Yw@!4XcH(?=om!wl!?M$1L?(6eRlUs7qt8kD6$!=H*-v}&75*-2GB^9qeCSijM3V?l^U;j#XG3LKHkIwJxnN&46|5kK>4;IFOiMm(8XrfTcfeKo2CB-s#4SGMM>flkY?dF{ER)&FWVSMytxRSsliA8-wlbNmOlB*S*~(<LGMTMRW-F7~%4D`OnXOD_E0fvEWVTE)TWbDF=c{>k7O*q^NzFM)ZSXG@CA!64YziSfnswDaWIh{itbf_teFe4e_~do}So9Kk|2RI_7kBkkGi`B$QSbHZc(nK4P+E38?2*h=|6I4%!6AK#5Z{^-7bB^jujBNKTNIgrW#tt(?rI7)!ML+G<mCNcvAb*KVVqB%PovOBRt5UKE4oY;vq-!l{8&4=<6M5T?>F^G-Ps|P>{pcu#MGy!x&R+9Av6s5NyNiy@*Mb0&O|)b6ROhRLEy_f12g@Fs(qDtRV7|{Wab*^Iqr5BYhBnAq_W8k!S5NigvO1`8(G|igc6^stm&Bm6P~ldCH*Gr3J?(^yq*nu>75vgH<=s};yN{KJ%X*c;(!nccF`#?gJ{}lo1HZ6TWKW{Ns@X>Xo@desOjN_?fclrH#5|fsIN&MlDA0Rm8*;ew2S7aNz+)=XYVDLwdAnl_<M4iL>=)Q=g>KynxJsiPT(a)v^eWzN)d9(b=+=t7sMaSoin~zY*$@KB67OOwMZI>5HX=MnOiz?otK5GmdIr=m#_<DaP1D#H<^_bzwz@t`77~}w3`LM50Hf9G7uLu@$0zb+yF}ViB|{f&~!u2fN?{FGYYp0dZM^Znj9`~lL#mTswiI}c@Mz*1*7Gi)o1$RmDpTdR)6~GClFLEA;iunFu;z$K+H}PeB?-0ZnBvHBw+CBqwWkz-`p(Tva=g3izYt%fxILPsN!sJG@bZhgM4ANkTM7P9r4`?=(+~wxSGeElw5OgCp0UiXK(@t+li@nS~VS?d>x_BSh&TP8;XS*ibiEzw)9!&y3Vy>bdcq3^f3;byTNPN-Db%B;i=j(caWkHGD2SOaQ02TPI;PDQsA<yK`(hq)C9e=59et?w=xw776!j^T<@H|6TRk&@)md~__p|6(C^g8eq-h&#wv)A(`JU#Euoqlc$|W00GbQAsh}{5oC<Z%Pa~&(g+zsnQSsOPC~~aO54|Y)s;jEgh4%u}og>GED*C)}GYsQ@>8yg_7&7ti^Uf;BBpOHF1V*-u%#9r1FP}yyHbd8CO+!iBu|GJ@;vwkBpK6RJS9BS~1xX}lCEf<1VI$8gU~!N7Pd_z&s!vAx%KrmU8@Dw'))

def historical_workflow_bytes():
    result = {}
    for oid, encoded in _HISTORICAL_WORKFLOW_BYTES:
        raw = zlib.decompress(base64.b85decode(encoded))
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if actual != oid:
            raise ValueError("historical workflow fixture whole hash differs")
        result[oid] = raw
    # Preserve deployed25 independently of active26 and shallow Git history.
    # This is the exact finite Boolean edit to the already frozen22 recipe.
    original = result['81bcf1933edc435826e2de411a777cccd4dec7c7']
    lines = [line for line in original.splitlines(keepends=True)
             if b'nonproducer_intent: ${{ ' in line]
    if len(lines) != 1:
        raise ValueError('historical Boolean input is not unique')
    old = lines[0]
    new = old.replace(b'${{ ', b'${{ !(!(', 1).replace(b' }}', b')) }}', 1)
    raw = original.replace(old, new, 1)
    oid = '15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a'
    if hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() != oid:
        raise ValueError('historical Boolean workflow fixture whole hash differs')
    result[oid] = raw
    return result


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("host_receipt_package_policy", ROOT / "tools/repository-checks/package_checks.py")
PACKAGES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGES)


def blob(data):
    return {"mode": "100644", "type": "blob",
            "sha": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}


class TemporaryGit:
    def temporary(self):
        directory = tempfile.TemporaryDirectory(prefix="overte-host-receipt-")
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def git(self, root, *args):
        return subprocess.check_output(["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                                       cwd=root, text=True, stderr=subprocess.PIPE).strip()

    def initialize(self, root):
        self.git(root, "init", "-q", "--initial-branch=main")
        self.git(root, "config", "user.name", "Host receipt fixture")
        self.git(root, "config", "user.email", "fixture@example.invalid")
        self.git(root, "config", "maintenance.auto", "false")
        self.git(root, "config", "gc.auto", "0")
        self.git(root, "config", "core.fileMode", "true")

    def write(self, root, relative, data):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


class WorkflowGenerationTests(TemporaryGit, unittest.TestCase):
    def setUp(self):
        self.generations = PACKAGES.workflow_generations()
        paths = list((ROOT / "tools/repository-checks/workflows").rglob("*.yml"))
        paths += [ROOT / relative for relative in
                  set(PACKAGES.CONSUMER_WORKFLOW_PATHS) | set(PACKAGES.METADATA_WORKFLOW_PATHS)
                  if (ROOT / relative).is_file() and not (ROOT / relative).is_symlink()]
        self.contents = {blob(path.read_bytes())["sha"]: path.read_bytes() for path in paths}
        self.contents.update(historical_workflow_bytes())
        # Immutable historical fixtures must survive later template edits and
        # remain available in shallow source snapshots without Git history.
        for oid in ('93f35c99ec6580b8796420997b1dcc586b7bfd95',
                    '15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a',
                    '861db7b76a11b9b8772e91cb24ec7cb9d918e339',
                    '6684e18785719813c51f9e3f5481a82ca40f0baf',
                    '84d98cac819755f98eecffba847e0bbcf667a6ca',
                    'c1d3d14a9098de214b6544dca8dcba0072090c6b',
                    'c01ff8a69f1ccbc60196da17e782c9a09defe4e5',
                    '1f8a7c3b4fe400a7c62ec2682de3f77d08dfd70d',
                    'b9022d17b985f93838b92cb42c7e2d873e7cb11f'):
            self.assertIn(oid, self.contents)
            self.assertEqual(blob(self.contents[oid])['sha'], oid)

    def materialize(self, generation):
        root = self.temporary()
        for path, entry in generation["workflows"].items():
            self.write(root, path, self.contents[entry["sha"]])
        return root

    def test_old_and_receipt_generations_each_accept_only_a_complete_tuple(self):
        self.assertTrue({"packages-v1", "packages-v1-direct", "shared-receipt-v1", "shared-receipt-v1-direct"}
                        .issubset({generation["name"] for generation in self.generations}))
        for generation in self.generations:
            with self.subTest(generation=generation["name"]):
                self.assertEqual(PACKAGES.validate_wiring(self.materialize(generation)), generation["name"])
                # Independently enumerated API entries include their own path.
                tree = {path: {"path": path, **entry} for path, entry in generation["workflows"].items()}
                self.assertEqual(PACKAGES.validate_tree_wiring(tree), generation["name"])

    def test_missing_unknown_nonregular_or_modified_workflow_cannot_pass(self):
        original = self.generations[0]["workflows"]
        for path in PACKAGES.WORKFLOW_PATHS:
            for mutation in (None, {"sha": "a" * 40}, {"mode": "100755"}, {"mode": "120000"},
                             {"type": "commit", "mode": "160000"}, {"sha": 1}):
                tree = deepcopy(original)
                if mutation is None:
                    del tree[path]
                else:
                    tree[path].update(mutation)
                with self.subTest(path=path, mutation=mutation), self.assertRaises(ValueError):
                    PACKAGES.validate_tree_wiring(tree)
        for change in ("missing", "modified", "executable", "symlink", "oversized"):
            root = self.materialize(self.generations[0])
            path = root / PACKAGES.WORKFLOW_PATHS[0]
            if change == "missing": path.unlink()
            elif change == "modified": path.write_bytes(path.read_bytes() + b"\n# unapproved\n")
            elif change == "executable": path.chmod(0o755)
            elif change == "symlink": path.unlink(); path.symlink_to(ROOT / PACKAGES.PRODUCER_TEMPLATE)
            else: path.write_bytes(b"x" * 1_000_001)
            with self.subTest(change=change), self.assertRaises(ValueError):
                PACKAGES.validate_wiring(root)

    def test_individually_known_workflows_cannot_be_mixed_between_generations(self):
        policy = self.temporary()
        first = deepcopy(self.generations[0])
        second = deepcopy(first)
        first["name"], second["name"] = "first", "second"
        for path in PACKAGES.WORKFLOW_PATHS[:2]:
            second["workflows"][path]["sha"] = "a" * 40
        manifest = {"schema": 1, "repository": {"full_name": PACKAGES.REPOSITORY, "id": PACKAGES.REPOSITORY_ID},
                    "generations": [first, second]}
        self.write(policy, PACKAGES.GENERATION_MANIFEST, json.dumps(manifest).encode())
        mixed = deepcopy(first["workflows"])
        mixed[PACKAGES.WORKFLOW_PATHS[0]] = second["workflows"][PACKAGES.WORKFLOW_PATHS[0]]
        with patch.object(PACKAGES, "ROOT", policy):
            self.assertEqual(PACKAGES.validate_tree_wiring(first["workflows"]), "first")
            self.assertEqual(PACKAGES.validate_tree_wiring(second["workflows"]), "second")
            with self.assertRaises(ValueError): PACKAGES.validate_tree_wiring(mixed)

    def test_protected_producer_requires_the_complete_new_pair_and_all_five_siblings(self):
        previous = next(g for g in self.generations if g['name'] == 'android-owned-npm5-sync-ci-v1')
        prospective = next(g for g in self.generations if g['name'] == 'protected-shared-producer-v1')
        self.assertEqual(set(prospective['workflows']), set(PACKAGES.CONSUMER_WORKFLOW_PATHS))
        self.assertEqual(len(self.generations[:25]), 25)
        self.assertEqual(len(self.generations), 28)
        self.assertEqual(hashlib.sha256(json.dumps(self.generations[:26],sort_keys=True,
            separators=(',',':')).encode()).hexdigest(),
            '92e641b712f88bcb66808c51d8fe4b95b4cfb8834c0d39b3869adc4587fa7ec8')
        following=self.generations[26]
        self.assertEqual(following['name'],'protected-producer-optional-parent-source-v1')
        self.assertEqual({path for path in following['workflows']
            if following['workflows'][path]!=self.generations[25]['workflows'][path]},
            {'.github/workflows/parent-qualification.yml'})
        self.assertEqual(following['workflows']['.github/workflows/parent-qualification.yml'],
            {'mode':'100644','type':'blob','sha':'987d8f0d198e40211ab0f33286a55852e286c174'})
        retained=[row for row in self.generations[:25] if row['name']!='protected-producer-original-default-boolean-v1']
        self.assertEqual(len(retained), 24)
        self.assertEqual(len([row for row in self.generations[:25]
                              if row['name'] not in {'npm-consumers-sync-ci-budget-cleanup-v1', 'protected-producer-original-default-boolean-v1'}]), 23)
        self.assertEqual(len([row for row in self.generations[:25]
                              if row['name'] not in {'npm-consumers-sync-ci-budget-v1', 'npm-consumers-sync-ci-budget-cleanup-v1', 'protected-producer-original-default-boolean-v1'}]), 22)
        for path in prospective['workflows']:
            if path not in {'.github/workflows/repository-checks.yml', '.github/workflows/project-tests.yml'}:
                self.assertEqual(prospective['workflows'][path], previous['workflows'][path])
        for path in ('.github/workflows/repository-checks.yml', '.github/workflows/project-tests.yml'):
            mixed = deepcopy(prospective['workflows'])
            mixed[path] = deepcopy(previous['workflows'][path])
            with self.subTest(mixed=path), self.assertRaises(ValueError):
                PACKAGES.validate_tree_wiring(mixed)
        for path in prospective['workflows']:
            for mutation in (None, {'mode': '100755'}, {'mode': '120000'}, {'type': 'commit', 'mode': '160000'}, {'sha': 'a' * 40}):
                mixed = deepcopy(prospective['workflows'])
                if mutation is None: del mixed[path]
                else: mixed[path].update(mutation)
                with self.subTest(path=path, mutation=mutation), self.assertRaises(ValueError):
                    PACKAGES.validate_tree_wiring(mixed)

    def test_candidate_generation_manifest_never_authorizes_its_own_workflows(self):
        root = self.materialize(self.generations[0])
        path = PACKAGES.WORKFLOW_PATHS[0]
        self.write(root, path, b"candidate-controlled owner\n")
        forged = deepcopy(self.generations[0])
        forged["workflows"][path] = blob((root / path).read_bytes())
        self.write(root, PACKAGES.GENERATION_MANIFEST, json.dumps({"schema": 1,
            "repository": {"full_name": PACKAGES.REPOSITORY, "id": PACKAGES.REPOSITORY_ID},
            "generations": [forged]}).encode())
        with self.assertRaises(ValueError): PACKAGES.validate_wiring(root)

    def test_metadata_generation_requires_the_complete_six_ordinary_immutable_entries(self):
        for name in ('protected-producer-metadata-ci-v1', 'protected-producer-seven-target-ci-v1',
                     'protected-producer-original-default-v1'):
            generation = next(row for row in self.generations if row['name'] == name)
            original = generation['workflows']
            self.assertEqual(set(original), set(PACKAGES.METADATA_WORKFLOW_PATHS))
            self.assertEqual(PACKAGES.validate_tree_wiring(original), name)
            for path in original:
                known_other = next(value for row in self.generations for value in row['workflows'].values()
                                   if value != original[path])
                for change in ('missing', 'neighbor', 'mixed-known', 'executable', 'symlink', 'gitlink', 'unknown'):
                    tree = deepcopy(original)
                    if change == 'missing': del tree[path]
                    elif change == 'neighbor': tree[path + '.neighbor.yml'] = tree.pop(path)
                    elif change == 'mixed-known': tree[path] = deepcopy(known_other)
                    elif change == 'executable': tree[path]['mode'] = '100755'
                    elif change == 'symlink': tree[path]['mode'] = '120000'
                    elif change == 'gitlink': tree[path].update(mode='160000', type='commit')
                    else: tree[path]['sha'] = 'a' * 40
                    with self.subTest(generation=name, path=path, change=change), self.assertRaises(ValueError):
                        PACKAGES.validate_tree_wiring(tree)

    def test_original_default_generation_binds_all_canonical_sources_and_retains_metadata_baseline(self):
        generation = next(row for row in self.generations if row['name'] == 'protected-producer-original-default-v1')
        canonical = {
            '.github/workflows/project-tests.yml': 'producers/protected-project-tests-android-platform.yml',
            '.github/workflows/parent-qualification.yml': 'producers/parent-qualification-android-platform.yml',
            '.github/workflows/repository-checks.yml': 'producers/repository-checks.yml',
            '.github/workflows/sync-validation.yml': 'sync-ci-selection.yml',
            '.github/workflows/browser-client.yml': 'npm-consumers/browser-client.yml',
            '.github/workflows/pr-metadata-context.yml': 'metadata-edits/pr-metadata-context.yml',
        }
        expected = {}
        for target, relative in canonical.items():
            path = ROOT / 'tools/repository-checks/workflows' / relative
            self.assertFalse(path.is_symlink())
            self.assertIn(path.stat().st_mode & 0o777, (0o444, 0o644))
            frozen={'.github/workflows/repository-checks.yml':'81bcf1933edc435826e2de411a777cccd4dec7c7',
                    '.github/workflows/parent-qualification.yml':'9bfc6f8723b1f59426f913472b78206844a7f201'}
            raw=historical_workflow_bytes()[frozen[target]] if target in frozen else path.read_bytes()
            expected[target] = blob(raw)
        self.assertEqual(generation['workflows'], expected)
        self.assertEqual(PACKAGES.validate_tree_wiring(expected), generation['name'])
        previous = next(row for row in self.generations if row['name'] == 'protected-producer-metadata-ci-v1')
        for target, filename, oid in (
                ('.github/workflows/project-tests.yml', 'protected-project-tests', 'c01ff8a69f1ccbc60196da17e782c9a09defe4e5'),
                ('.github/workflows/parent-qualification.yml', 'parent-qualification', '1f8a7c3b4fe400a7c62ec2682de3f77d08dfd70d'),
                ('.github/workflows/repository-checks.yml', 'repository-checks', 'b9022d17b985f93838b92cb42c7e2d873e7cb11f')):
            frozen = ROOT / ('tools/repository-checks/workflows/producers/legacy/' + filename + '-metadata-v1.yml')
            self.assertEqual(blob(frozen.read_bytes())['sha'], oid)
            self.assertEqual(previous['workflows'][target], blob(frozen.read_bytes()))
            self.assertNotEqual(expected[target], previous['workflows'][target])
        for target in set(expected) - {'.github/workflows/project-tests.yml', '.github/workflows/parent-qualification.yml',
                                       '.github/workflows/repository-checks.yml', '.github/workflows/sync-validation.yml',
                                       '.github/workflows/pr-metadata-context.yml'}:
            self.assertEqual(expected[target], previous['workflows'][target])

    def test_boolean_generation_is_additive_and_staged_without_activating_callers(self):
        rows={row['name']:row['workflows'] for row in self.generations}
        old=rows['protected-producer-original-default-v1']
        new=rows['protected-producer-original-default-boolean-v1']
        caller='.github/workflows/repository-checks.yml'
        self.assertEqual({path for path in old if old[path]!=new[path]},{caller})
        self.assertEqual(old[caller]['sha'],'81bcf1933edc435826e2de411a777cccd4dec7c7')
        self.assertEqual(new[caller],{'mode':'100644','type':'blob','sha':'15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a'})
        staged=rows['protected-producer-original-default-required-context-v1']
        self.assertEqual(staged[caller],blob((ROOT/'tools/repository-checks/workflows/producers/repository-checks.yml').read_bytes()))
        installed=PACKAGES.validate_wiring(ROOT)
        codeql_by_generation={
            'protected-producer-original-default-v1':'e9aaaed9693efc5ffb4701697ac2a4d51f5f5ba1',
            'protected-producer-original-default-boolean-v1':'3b7a88765b7181a1bc7dd6f48b9b459e590055d3',
            'protected-producer-original-default-required-context-v1':'7b0703d88d404f38c1b3dec92f77f03586c9144c',
            'protected-producer-optional-parent-source-v1':'7b0703d88d404f38c1b3dec92f77f03586c9144c',
            'protected-producer-optional-leaf-common-v1':'7b0703d88d404f38c1b3dec92f77f03586c9144c',
        }
        self.assertIn(installed,codeql_by_generation)
        self.assertEqual(rows[installed][caller],blob((ROOT/caller).read_bytes()))
        codeql=ROOT/'.github/workflows/codeql.yml'
        self.assertFalse(codeql.is_symlink())
        self.assertIn(codeql.stat().st_mode & 0o777,(0o444,0o644))
        self.assertEqual(blob(codeql.read_bytes())['sha'],codeql_by_generation[installed])
        for name in ('protected-producer-original-default-v1','protected-producer-original-default-boolean-v1',
                     'protected-producer-original-default-required-context-v1',
                     'protected-producer-optional-parent-source-v1', 'protected-producer-optional-leaf-common-v1'):
            self.assertEqual(PACKAGES.validate_tree_wiring(rows[name]),name)
            unknown=deepcopy(rows[name]);unknown[caller]['sha']='f'*40
            with self.subTest(name=name),self.assertRaises(ValueError):PACKAGES.validate_tree_wiring(unknown)

    def test_metadata_candidate_and_immutable_base_cannot_omit_or_alias_the_sixth_workflow(self):
        generation = next(row for row in self.generations if row['name'] == 'protected-producer-metadata-ci-v1')
        helper = '.github/workflows/pr-metadata-context.yml'
        for change in ('valid', 'missing', 'mixed-known', 'executable', 'symlink'):
            root = self.materialize(generation)
            path = root / helper
            if change == 'missing': path.unlink()
            elif change == 'mixed-known': path.write_bytes(self.contents[self.generations[0]['workflows'][PACKAGES.WORKFLOW_PATHS[0]]['sha']])
            elif change == 'executable': path.chmod(0o755)
            elif change == 'symlink': path.unlink(); path.symlink_to(ROOT / PACKAGES.PRODUCER_TEMPLATE)
            with self.subTest(change=change):
                if change == 'valid':
                    self.assertEqual(PACKAGES.validate_wiring(root), generation['name'])
                    self.assertTrue(PACKAGES.consumer_generation(root))
                else:
                    with self.assertRaises(ValueError): PACKAGES.validate_wiring(root)
                    with self.assertRaises(ValueError): PACKAGES.consumer_generation(root)
        root = self.materialize(generation)
        self.initialize(root)
        self.git(root, 'add', '.')
        self.git(root, 'commit', '-qm', 'Complete six-workflow immutable fixture')
        self.assertTrue(PACKAGES.consumer_base(root, self.git(root, 'rev-parse', 'HEAD')))
        self.git(root, 'rm', helper)
        self.git(root, 'commit', '-qm', 'Missing sixth workflow immutable negative')
        self.assertFalse(PACKAGES.consumer_base(root, self.git(root, 'rev-parse', 'HEAD')))

    def test_unrelated_source_and_sparse_candidate_do_not_change_generation_identity(self):
        root = self.materialize(self.generations[2])
        self.write(root, "unrelated/source.py", b"raise RuntimeError('must never execute')\n")
        self.initialize(root)
        self.git(root, "add", "."); self.git(root, "commit", "-qm", "Approved sparse candidate fixture")
        sparse = self.temporary() / "candidate"
        subprocess.run(["git", "clone", "--quiet", "--no-checkout", str(root), str(sparse)], check=True, capture_output=True)
        self.git(sparse, "sparse-checkout", "set", ".github")
        self.git(sparse, "checkout", "-q", "HEAD")
        self.assertFalse((sparse / "unrelated/source.py").exists())
        self.assertEqual(PACKAGES.validate_wiring(sparse), self.generations[2]["name"])


class TrustedGenerationPolicyTests(TemporaryGit, unittest.TestCase):
    def setUp(self):
        self.document = json.loads((ROOT / PACKAGES.GENERATION_MANIFEST).read_text())

    def policy(self, document):
        root = self.temporary()
        self.write(root, PACKAGES.GENERATION_MANIFEST, document if isinstance(document, bytes) else json.dumps(document).encode())
        return root

    def test_unknown_foreign_duplicate_partial_and_corrupt_policy_fails_closed(self):
        cases = [b"not-json", b"x" * 64_001, {}, {**self.document, "schema": True},
                 {**self.document, "schema": 2}, {**self.document, "extra": True},
                 {**self.document, "repository": {"full_name": "overte-org/overte", "id": 1}},
                 {**self.document, "generations": []}]
        for change in ("name", "tuple", "path", "mode", "zero", "fields"):
            value = deepcopy(self.document)
            generation = value["generations"][0]
            if change == "name": value["generations"][1]["name"] = generation["name"]
            elif change == "tuple": value["generations"][1]["workflows"] = deepcopy(generation["workflows"])
            elif change == "path": generation["workflows"].pop(PACKAGES.WORKFLOW_PATHS[0])
            elif change == "mode": generation["workflows"][PACKAGES.WORKFLOW_PATHS[0]]["mode"] = "100755"
            elif change == "zero": generation["workflows"][PACKAGES.WORKFLOW_PATHS[0]]["sha"] = "0" * 40
            else: generation["extra"] = True
            cases.append(value)
        cases.append(json.dumps(self.document).replace('"schema": 1', '"schema": 1, "schema": 1').encode())
        for value in cases:
            root = self.policy(value)
            with self.subTest(value=str(value)[:80]), patch.object(PACKAGES, "ROOT", root), self.assertRaises(ValueError):
                PACKAGES.workflow_generations()
        for change in ("missing", "symlink", "directory"):
            root = self.policy(self.document)
            path = root / PACKAGES.GENERATION_MANIFEST
            path.unlink()
            if change == "symlink": path.symlink_to(ROOT / PACKAGES.GENERATION_MANIFEST)
            elif change == "directory": path.mkdir()
            with self.subTest(change=change), patch.object(PACKAGES, "ROOT", root), self.assertRaises(ValueError):
                PACKAGES.workflow_generations()

    def trusted_fixture(self):
        identities = PACKAGES._policy_inputs()
        root = self.temporary()
        for relative in identities:
            self.write(root, relative, (ROOT / relative).read_bytes())
        self.initialize(root)
        self.git(root, "add", "."); self.git(root, "commit", "-qm", "Trusted policy input fixture")
        return root, identities

    def test_complete_trusted_helpers_and_transitive_requirements_are_bound(self):
        root, baseline = self.trusted_fixture()
        required = {PACKAGES.GENERATION_MANIFEST, PACKAGES.PRODUCER_TEMPLATE, ".github/test-suites.json",
                    "tools/test-evidence/run.py", "tests/run-project-tests.py", "tests/platform-profile.json",
                    "tools/sync-test-reuse/qualification.py", "tests/requirements-host.txt",
                    "tests/requirements-repository.txt", "tools/sbom/requirements-validation.txt"}
        self.assertLessEqual(required, set(baseline))
        for relative in required:
            path = root / relative
            previous = path.read_bytes()
            # Preserve valid JSON/pins while changing exact trusted bytes.
            path.write_bytes(previous + b"\n")
            with patch.object(PACKAGES, "ROOT", root):
                self.assertNotEqual(baseline, PACKAGES._policy_inputs(), relative)
            path.write_bytes(previous)

    def test_old_trusted_sparse_layout_has_exactly_the_same_complete_policy_hash(self):
        root, baseline = self.trusted_fixture()
        sparse = self.temporary() / "trusted"
        subprocess.run(["git", "clone", "--quiet", "--no-checkout", str(root), str(sparse)], check=True, capture_output=True)
        # The existing outer caller intentionally remains byte-identical.
        self.git(sparse, "sparse-checkout", "set", ".github", "tools/repository-checks", "tools/test-evidence",
                 "tools/native-tests", "tools/ios-build-qualification")
        self.git(sparse, "checkout", "-q", "HEAD")
        self.assertFalse((sparse / "tests/requirements-host.txt").exists())
        self.assertFalse((sparse / "tools/sbom/requirements-validation.txt").exists())
        with patch.object(PACKAGES, "ROOT", sparse):
            self.assertEqual(PACKAGES._policy_inputs(), baseline)
        # Ordinary deletion must not be mistaken for an omitted sparse input.
        (root / "tests/requirements-host.txt").unlink()
        with patch.object(PACKAGES, "ROOT", root), self.assertRaises(ValueError): PACKAGES._policy_inputs()

    def test_unknown_requirement_graph_fails_closed(self):
        for source in (b"-r ../../outside.txt\n", b"-r absent.txt\n", b"requests>=1\n",
                       b"Thing==1\nthing==2\n", b"x" * 100_001):
            root = self.temporary()
            self.write(root, "tests/requirements-host.txt", source)
            with self.subTest(source=source[:40]), patch.object(PACKAGES, "ROOT", root), self.assertRaises(ValueError):
                PACKAGES._requirement_paths()

    def test_recursive_requirement_additions_and_changes_are_in_the_policy_identity(self):
        root, baseline = self.trusted_fixture()
        host = root / "tests/requirements-host.txt"
        host.write_bytes(host.read_bytes() + b"\n-r ../extra/validation-pins.txt\n")
        path = self.write(root, "extra/validation-pins.txt", b"FixtureDependency==1\n")
        with patch.object(PACKAGES, "ROOT", root):
            added = PACKAGES._policy_inputs()
            self.assertIn("extra/validation-pins.txt", added)
            self.assertNotEqual(added, baseline)
            path.write_bytes(b"FixtureDependency==2\n")
            self.assertNotEqual(added, PACKAGES._policy_inputs())

    def test_symlink_gitlink_and_oversized_trusted_sparse_blobs_cannot_be_hashed(self):
        for change in ("symlink", "gitlink", "oversized"):
            root, _ = self.trusted_fixture()
            relative = "tests/requirements-host.txt"
            path = root / relative
            if change == "symlink":
                path.unlink(); path.symlink_to("requirements-repository.txt")
                self.git(root, "add", relative)
            elif change == "gitlink":
                revision = self.git(root, "rev-parse", "HEAD")
                self.git(root, "rm", "-q", relative)
                self.git(root, "update-index", "--add", "--cacheinfo", "160000," + revision + "," + relative)
            else:
                path.write_bytes(b"x" * 100_001)
                self.git(root, "add", relative)
            self.git(root, "commit", "-qm", "Unproven trusted sparse requirement fixture")
            sparse = self.temporary() / "trusted"
            subprocess.run(["git", "clone", "--quiet", "--no-checkout", str(root), str(sparse)],
                           check=True, capture_output=True)
            self.git(sparse, "sparse-checkout", "set", ".github", "tools/repository-checks", "tools/test-evidence")
            self.git(sparse, "checkout", "-q", "HEAD")
            self.assertFalse((sparse / relative).exists())
            with self.subTest(change=change), patch.object(PACKAGES, "ROOT", sparse), self.assertRaises(ValueError):
                PACKAGES._policy_inputs()


class ProtectedProducerPermissionTests(unittest.TestCase):
    def test_caller_grants_exact_read_ceiling_only_to_native_owner_roles(self):
        old = yaml.safe_load((ROOT / 'tools/repository-checks/workflows/android-owned/repository-checks.yml').read_text())
        source = (ROOT / 'tools/repository-checks/workflows/producers/repository-checks.yml').read_text()
        prospective = yaml.safe_load(source)
        historical_path = ROOT / 'tools/repository-checks/workflows/producers/legacy/repository-checks-metadata-v1.yml'
        self.assertEqual(blob(historical_path.read_bytes())['sha'], 'b9022d17b985f93838b92cb42c7e2d873e7cb11f')
        historical_raw = historical_workflow_bytes()['d9fefd275d9e3c6977cf9350a1945a6bbe5051b4']
        self.assertEqual(blob(historical_raw)['sha'], 'd9fefd275d9e3c6977cf9350a1945a6bbe5051b4')
        historical = yaml.safe_load(historical_raw)
        permissions = {'contents': 'read', 'actions': 'read', 'pull-requests': 'read', 'checks': 'read'}
        expected = deepcopy(old)
        expected['jobs']['project']['permissions'] = permissions
        expected['jobs']['metadata-source'] = {
            'name': 'Authenticate PR text edit',
            'if': "github.event_name == 'pull_request' && github.base_ref == 'main' && github.event.action == 'edited' && !github.event.changes.base && (github.event.changes.title || github.event.changes.body)",
            'uses': './.github/workflows/pr-metadata-context.yml',
        }
        route = expected['jobs']['route']
        route['needs'] = 'metadata-source'
        route['if'] = "always() && (needs.metadata-source.result == 'success' || needs.metadata-source.result == 'skipped')"
        route['permissions'] = {'contents': 'read', 'actions': 'read', 'pull-requests': 'read'}
        event = next(step for step in route['steps'] if step.get('id') == 'event')
        event['env'] = {'GH_TOKEN': '${{ github.token }}',
                        'NATIVE_METADATA_INTENT': '${{ needs.metadata-source.outputs.metadata_intent }}'}
        docs = expected['jobs']['documentation']
        docs['needs'] = ['route', 'project']
        docs['if'] = "always() && needs.route.result == 'success' && (needs.project.result == 'success' || needs.project.result == 'skipped') && needs.route.outputs.metadata_only != 'true' && needs.project.outputs.documentation_verified != 'true'"
        expected['jobs']['workflow-security']['with'] = {'defer_workflow_contracts': True}
        expected['jobs']['workflow-contracts'] = {
            'needs': ['route', 'project'],
            'if': "always() && needs.route.result == 'success' && (needs.project.result == 'success' || needs.project.result == 'skipped') && needs.route.outputs.metadata_only != 'true' && needs.route.outputs.security == 'true' && needs.project.outputs.workflow_contracts_verified != 'true'",
            'runs-on': 'ubuntu-24.04', 'timeout-minutes': 5,
            'steps': [{'name': 'Check out the exact candidate without credentials',
                'uses': 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1',
                'with': {'ref': '${{ github.sha }}', 'fetch-depth': 2, 'persist-credentials': False}},
                {'name': 'Verify remaining workflow contracts',
                 'run': 'PYTHONDONTWRITEBYTECODE=1 python3 tests/workflow-contract-test.py'}]}
        outer = expected['jobs']['repository-checks']
        outer['permissions'] = permissions
        outer['needs'].insert(outer['needs'].index('native'), 'workflow-contracts')
        candidate = next(step['with'] for step in outer['steps'] if step.get('with', {}).get('path') == 'candidate')
        candidate.update({'sparse-checkout-cone-mode': False,
                          'sparse-checkout': '.github\ntests/platform-profile.json\n'})
        verify = outer['steps'][-1]
        verify['env']['GH_TOKEN'] = '${{ github.token }}'
        verify['run'] = verify['run'].replace(' verify --needs-json', ' verify --event "$GITHUB_EVENT_PATH" --needs-json')
        self.assertEqual(historical, expected)
        # The old21 recipe remains byte-exact above. Current22 has its own
        # complete source tuple and cannot inherit permissions from a mixed pair.
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
            self.assertFalse(path.is_symlink())
            self.assertIn(path.stat().st_mode & 0o777, (0o444, 0o644))
            frozen={'.github/workflows/repository-checks.yml':'81bcf1933edc435826e2de411a777cccd4dec7c7',
                    '.github/workflows/parent-qualification.yml':'9bfc6f8723b1f59426f913472b78206844a7f201'}
            raw=historical_workflow_bytes()[frozen[target]] if target in frozen else path.read_bytes()
            tree[target] = blob(raw)
        self.assertEqual(PACKAGES.validate_tree_wiring(tree), 'protected-producer-original-default-v1')
        for path in tree:
            for change in ('missing', 'mixed', 'mode'):
                changed = deepcopy(tree)
                if change == 'missing': del changed[path]
                elif change == 'mode': changed[path]['mode'] = '100755'
                else:
                    previous = next(row for row in PACKAGES.workflow_generations()
                                    if row['name'] == 'protected-producer-metadata-ci-v1')
                    other = next(entry for entry in previous['workflows'].values() if entry != tree[path])
                    changed[path] = deepcopy(other)
                with self.subTest(path=path, change=change), self.assertRaises(ValueError):
                    PACKAGES.validate_tree_wiring(changed)
        self.assertEqual(prospective['permissions'], {'contents': 'read'})
        self.assertEqual(prospective['jobs']['project']['uses'], './.github/workflows/project-tests.yml')
        self.assertNotIn('secrets', prospective['jobs']['project'])
        for role in ('metadata-source', 'route', 'project', 'repository-checks'):
            self.assertEqual(prospective['jobs'][role]['permissions'], permissions, role)
        for name, job in prospective['jobs'].items():
            actual = job.get('permissions', prospective['permissions'])
            if name == 'native':
                self.assertEqual(actual, {'contents': 'read', 'packages': 'read'})
            else:
                self.assertTrue(all(value == 'read' and key in permissions for key, value in actual.items()), name)
            self.assertNotIn('secrets', job)
        intent = "github.event_name == 'pull_request' && ((github.event.action == 'edited' && !github.event.changes.base && (github.event.changes.title || github.event.changes.body)) || ((github.event.action == 'labeled' || github.event.action == 'unlabeled') && github.event.label.name != 'android-long-diagnostics'))"
        self.assertEqual(prospective['jobs']['metadata-source']['if'], "github.event_name == 'pull_request'")
        self.assertEqual(prospective['jobs']['metadata-source']['with'], {'nonproducer_intent': '${{ !(!(' + intent + ')) }}'})
        self.assertEqual(prospective['run-name'], '${{ (' + intent + ") && 'Overte native metadata nonproducer v2' || 'Overte native ordinary qualification v2' }}")
        for role, condition in (
                ('project', "(needs.route.outputs.package_host_mode == 'full' || needs.route.outputs.package_host_mode == 'tool-dependencies' || needs.route.outputs.package_set != '[]')"),
                ('native', "needs.route.outputs.native != 'skip'"),
                ('android', "needs.route.outputs.android_required == 'true'"),
                ('workflow-security', "needs.route.outputs.security == 'true'")):
            self.assertEqual(prospective['jobs'][role]['if'],
                "always() && !cancelled() && needs.route.result == 'success' && needs.route.outputs.metadata_only != 'true' && " + condition + ' && !(' + intent + ')')
        candidate = next(step['with'] for step in prospective['jobs']['repository-checks']['steps']
                         if step.get('with', {}).get('path') == 'candidate')
        self.assertFalse(candidate['persist-credentials'])
        self.assertFalse(candidate['sparse-checkout-cone-mode'])
        self.assertEqual(candidate['sparse-checkout'], '.github\ntests/platform-profile.json\n')
        future_callee = yaml.safe_load((ROOT / 'tools/repository-checks/workflows/producers/protected-project-tests-android-platform.yml').read_text())
        self.assertEqual(future_callee['permissions'], {'contents': 'read'})
        for name, job in future_callee['jobs'].items():
            actual = job.get('permissions', future_callee['permissions'])
            self.assertEqual(actual, permissions if name in {
                'route', 'project-tests', 'project-results', 'producer-publication', 'platform-tests'}
                else {'contents': 'read'}, name)
            self.assertNotIn('secrets', job)
        callee = yaml.safe_load((ROOT / 'tools/repository-checks/workflows/producers/protected-project-tests.yml').read_text())
        self.assertEqual(callee['permissions'], {'contents': 'read'})
        for name, job in callee['jobs'].items():
            actual = job.get('permissions', callee['permissions'])
            self.assertTrue(all(value == 'read' and permissions.get(key) == 'read' for key, value in actual.items()), name)
            self.assertEqual(actual, permissions if name in {'route', 'project-tests', 'producer-publication'} else {'contents': 'read'}, name)

    def test_callee_retains_permissions_readers_and_exact_historical_baseline(self):
        source = (ROOT / 'tools/repository-checks/workflows/producers/protected-project-tests.yml').read_bytes()
        self.assertEqual(source.count(b'      checks: read\n'), 3)
        self.assertEqual(source.count(b'          tools/branch-policy/check.py\n'), 6)
        self.assertEqual(source.count(b'        sparse-checkout-cone-mode: false\n'), 6)
        historical = (ROOT / 'tools/repository-checks/workflows/producers/legacy/protected-project-tests-postmerge-v1.yml').read_bytes()
        self.assertEqual(blob(historical)['sha'], '861db7b76a11b9b8772e91cb24ec7cb9d918e339')
        previous = historical.replace(b'          tools/branch-policy/check.py\n', b'').replace(
            b'        sparse-checkout-cone-mode: false\n', b'').replace(b'      checks: read\n', b'').replace(
            b'# Prospective protected producer; dormant wiring approved, production guards false.',
            b'# Prospective protected producer; production guards false and no active generation approval.')
        actual = subprocess.check_output(['/usr/bin/git', 'hash-object', '--stdin'], input=previous).decode().strip()
        self.assertEqual(actual, 'cad732c967d4d18b5a341c578b90789a271c02e9')


class ReceiptWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.old = yaml.safe_load((PACKAGES.TEMPLATES / "project-tests.yml").read_text())
        self.new = yaml.safe_load((ROOT / PACKAGES.PRODUCER_TEMPLATE).read_text())

    def test_only_full_host_execution_changes_and_other_owner_jobs_remain_identical(self):
        for key in self.old:
            if key != "jobs": self.assertEqual(self.old[key], self.new[key], key)
        self.assertEqual(set(self.old["jobs"]), set(self.new["jobs"]))
        for name in self.old["jobs"]:
            if name != "project-tests": self.assertEqual(self.old["jobs"][name], self.new["jobs"][name], name)
        previous, current = self.old["jobs"]["project-tests"], self.new["jobs"]["project-tests"]
        for key in previous:
            if key != "steps": self.assertEqual(previous[key], current[key], key)
        before = {step["name"]: step for step in previous["steps"]}
        after = {step["name"]: step for step in current["steps"]}
        for name in ("Set up Python", "Set up Node.js", "Set up Java", "Verify runner prerequisites",
                     "Install QML and portable C++ contract prerequisites"):
            self.assertEqual(before[name], after[name], name)

    def test_exact_candidate_trusted_requirements_controller_and_external_receipt_paths(self):
        steps = self.new["jobs"]["project-tests"]["steps"]
        trusted, candidate = steps[:2]
        self.assertEqual(trusted["with"]["ref"], "${{ github.event.repository.default_branch }}")
        self.assertEqual(trusted["with"]["path"], "trusted")
        self.assertFalse(trusted["with"]["sparse-checkout-cone-mode"])
        self.assertEqual(candidate["with"]["ref"], "${{ github.sha }}")
        self.assertEqual(candidate["with"]["path"], "candidate")
        self.assertEqual(candidate["with"]["fetch-depth"], 2)
        self.assertTrue(all(not step["with"]["persist-credentials"] for step in steps
                            if step.get("uses", "").startswith("actions/checkout@")))
        prepare = next(step for step in steps if step["name"] == "Prepare isolated host evidence validators")
        self.assertIn('-r trusted/tests/requirements-host.txt', prepare["run"])
        self.assertIn('python3 -m venv "$RUNNER_TEMP/overte-shared-host-env"', prepare["run"])
        self.assertIn('unshare --user --map-root-user --net true', prepare["run"])
        execute = next(step for step in steps if step["name"].startswith("Execute the complete trusted"))
        for expected in ('trusted/tools/test-evidence/run.py', '--candidate candidate --include-platform',
                         '--timeout 240 --host-timeout 900', '--junit "$RUNNER_TEMP/', '--receipt "$RUNNER_TEMP/'):
            self.assertIn(expected, execute["run"])
        self.assertNotIn('--suite', execute["run"])
        self.assertNotIn('candidate/tests/run-project-tests.py', execute["run"])
        self.assertEqual(execute["env"], {"GH_TOKEN": "", "GITHUB_TOKEN": ""})
        receipt = next(step for step in steps if step["name"] == "Preserve actual execution receipt for diagnosis")
        self.assertEqual(receipt["if"], "always()")
        self.assertEqual(receipt["with"]["path"], "${{ runner.temp }}/overte-shared-host-results/execution.json")
        self.assertIn('${{ github.run_id }}-attempt-${{ github.run_attempt }}', receipt["with"]["name"])
        self.assertNotIn('continue-on-error', execute)
        self.assertNotIn('descriptor', json.dumps(self.new))

    def test_sparse_controller_contains_actual_runtime_and_recursive_requirement_inputs(self):
        runtime = PACKAGES.load("host_receipt_runtime_contract", "tools/test-evidence/runtime.py")
        _, manifests = runtime._requirement_inventory(ROOT)
        patterns = self.new["jobs"]["project-tests"]["steps"][0]["with"]["sparse-checkout"].splitlines()
        required = {*runtime._TRUSTED_EXECUTION_FILES, *manifests, ".github/test-suites.json", "tests/platform-profile.json"}
        for path in required:
            self.assertTrue(any(path == pattern or path.startswith(pattern + "/") for pattern in patterns), path)


if __name__ == "__main__":
    unittest.main()
