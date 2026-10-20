#!/usr/bin/env python3
"""Pure protected affected-suite selection; no suite/build/runtime execution."""
from copy import deepcopy
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch, Mock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inputs


def blob(raw=b'fixed', *, mode='100644'):
    return {'mode':mode,'type':'blob','sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}


def definition(scope='content'):
    return {'command':['python','contracts/test.py'],'layer':'host','scope':scope,'environment':'host-qt5-qt6',
        'closure':{'kind':'patterns','inputs':['contracts/**','source/**'],'required':['contracts/test.py']},
        'python_imports':{'roots':['contracts'],'reviewed':'sha256:'+'0'*64}}


class AffectedPlannerTests(unittest.TestCase):
    def setUp(self):
        self.tree={p:blob(p.encode(),mode='100755' if p=='tests/run-project-tests.py' else '100644')
                   for p in inputs.AFFECTED_AUTHORITY}
        self.tree['tests/platform-profile.json']=deepcopy(inputs._AFFECTED_SHARED_PROFILE)
        self.tree.update({'contracts/test.py':blob(b'fixed test'),'source/input.qml':blob(b'fixed data'),
            'tools/test-evidence/sandbox_host.py':blob(b'old controller'),'unrelated/readme.md':blob(b'data')})
        finite=definition();finite['python_imports']['reviewed']=inputs.python_import_digest(self.tree,['contracts'])
        self.registry={'schema':1,'control_inputs':['tests/run-project-tests.py','tools/test-evidence/**','*.py'],
            'suites':{'finite':finite,'unproved':{'command':['python','unknown.py'],'layer':'quick','scope':'content',
                'environment':'host-qt5-qt6','closure':{'kind':'repository','inputs':[],'required':[]}},
                'candidate':definition('candidate')}}
        self.dependencies={'schema':1,'lookup_digest':inputs.affected_lookup_digest(self.tree),'registry_digest':inputs._suite_definition_digest(self.registry),'suites':{
            n:{'kind':'repository' if n=='unproved' else 'reviewed-patterns',
               'definition_digest':inputs._suite_definition_digest(s),'setup':['host-full'] if n=='unproved' else ['python']}
            for n,s in self.registry['suites'].items()}}
        self.seal()
        self.candidate=deepcopy(self.tree)
        self.candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed candidate controller')

    def seal(self):
        self.raw=json.dumps(self.dependencies,indent=2).encode()
        self.tree[inputs.AFFECTED_POLICY]=blob(self.raw)

    def plan(self,base=None,candidate=None,trusted=None,raw=None,registry=None):
        return inputs.plan_affected(registry or self.registry,self.raw if raw is None else raw,
            self.tree if base is None else base,self.candidate if candidate is None else candidate,
            self.tree if trusted is None else trusted)

    def test_changed_controller_selects_unproved_and_candidate_owners_individually(self):
        plan=self.plan()
        self.assertEqual(plan['required'],['unproved','candidate'])
        self.assertEqual(plan['omitted'],['finite'])
        self.assertFalse(plan['reusable'])
        self.assertEqual(plan['required_setup'],['host-full'])
        self.assertEqual(plan['paths'],['tools/test-evidence/sandbox_host.py'])

    def test_own_data_and_discovery_changes_select_their_suite(self):
        for path in ('source/input.qml','source/new.qml','contracts/data.json'):
            with self.subTest(path=path):
                candidate=deepcopy(self.candidate);candidate[path]=blob(b'changed')
                self.assertIn('finite',self.plan(candidate=candidate)['required'])

    def test_lookup_shadows_native_modules_pth_and_deletions_are_not_hidden(self):
        for path in ('contracts/json.py','contracts/sitecustomize.py','contracts/module.so','contracts/path.pth','contracts/test.py'):
            with self.subTest(path=path):
                candidate=deepcopy(self.candidate)
                if path in candidate:del candidate[path]
                else:candidate[path]=blob(b'new lookup candidate')
                with self.assertRaises(inputs.InputError):self.plan(candidate=candidate)

    def test_historical_unreviewed_module_on_both_sides_keeps_owner_required(self):
        base=deepcopy(self.tree);candidate=deepcopy(self.candidate)
        for tree in (base,candidate):tree['contracts/historical.py']=blob(b'child variant')
        with self.assertRaises(inputs.InputError):self.plan(base=base,candidate=candidate)

    def test_nonregular_inventory_anywhere_declines_even_if_unchanged(self):
        for mode,kind in (('120000','blob'),('160000','commit')):
            with self.subTest(mode=mode):
                base=deepcopy(self.tree);candidate=deepcopy(self.candidate)
                for tree in (base,candidate):tree['other/entry']={'mode':mode,'type':kind,'sha':'a'*40}
                with self.assertRaises(inputs.InputError):self.plan(base=base,candidate=candidate)

    def test_candidate_cannot_add_replace_remove_or_enable_its_graph(self):
        for which in ('candidate','base','trusted'):
            for operation in ('remove','change','mode'):
                trees={n:deepcopy(t) for n,t in (('base',self.tree),('candidate',self.candidate),('trusted',self.tree))}
                if operation=='remove':del trees[which][inputs.AFFECTED_POLICY]
                elif operation=='mode':trees[which][inputs.AFFECTED_POLICY]['mode']='100755'
                else:trees[which][inputs.AFFECTED_POLICY]=blob(b'candidate narrowed graph')
                with self.subTest(which=which,operation=operation),self.assertRaises(inputs.InputError):self.plan(**trees)

    def test_every_authority_change_declines_before_selection(self):
        for path in inputs.AFFECTED_AUTHORITY:
            candidate=deepcopy(self.candidate);candidate[path]=blob(b'new authority')
            with self.subTest(path=path),self.assertRaises(inputs.InputError):self.plan(candidate=candidate)

    def test_closed_policy_registry_definition_and_global_controls_are_bound(self):
        mutations=[]
        for change in ('schema','unknown','missing','definition','arbitrary-kind','setup','duplicate-setup'):
            value=deepcopy(self.dependencies)
            if change=='schema':value['schema']=True
            elif change=='unknown':value['force']=[]
            elif change=='missing':del value['suites']['unproved']
            elif change=='definition':value['suites']['finite']['definition_digest']='sha256:'+'f'*64
            elif change=='arbitrary-kind':value['suites']['finite']['kind']='caller-selected'
            elif change=='setup':value['suites']['unproved']['setup']=['python']
            else:value['suites']['finite']['setup']=['python','python']
            mutations.append((change,json.dumps(value).encode()))
        mutations += [('duplicate-key',self.raw.replace(b'"schema": 1',b'"schema":1,"schema":1')),
                      ('oversized',b' '*64001),('wrong-type','{}')]
        for change,raw in mutations:
            with self.subTest(change=change),self.assertRaises(inputs.InputError):self.plan(raw=raw)
        registry=deepcopy(self.registry);registry['control_inputs']=[]
        with self.assertRaises(inputs.InputError):self.plan(registry=registry)

    def test_missing_unknown_empty_and_wrong_policy_bytes_fail_closed(self):
        for tree in (None,{},[] ):
            with self.subTest(tree=tree),self.assertRaises(inputs.InputError):
                inputs.plan_affected(self.registry,self.raw,tree,self.candidate,self.tree)
        with self.assertRaises(inputs.InputError):self.plan(candidate=self.tree)
        with self.assertRaises(inputs.InputError):self.plan(raw=self.raw+b' ')


# Fixture-only projection of the REVIEWED PROPOSED SOURCE snapshot, not protected D.
# 2dee50b1db9b4a2cb52342de3983bfb922a58005 / tree 00e374639862850834de5144b105a02b27212b12.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = 'f21a78a2d85b93ffcb88a969fc47a45ae5bb8a8700b805f0126eb46e11712847'
_MAIN_PROJECTION_B85 = (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    'c-qa~+makdvL)E}`HXsQ9QggxUokQ=?<syU2ZBswWaWiLc1!>JEcJ*4!7609M<jb@j&vUuL7p-TcXKt>t$T0%pa1x;FNc?}ujA+8'
    'VSYLu=1<3eJ*1~kFHgh6^OBza>zC)_!$1D}|NO_d<DCBS-~W+kSyNU2_;3Gs{yO;EqR4XpQ|CoD<&*!E<?XVha-65S$)+w}vT~X8'
    '-2cJLACK{0Fy0@>fBdii_I=sWLetkzkH`DN^vA|(<5>FdYEsj;**v7FYua`iQ<k;aQa0n9Ep1Z`S@-^GkHhrq@Fjiv*YWAs<^K4u'
    'PhXN>JG>l@56>Hmr+LhpX6}l)>Z-C#Su^$h*pyklq`J(9Y)VUA`M-R3@u&27d_KG!pZ@qXeNEG^TPxO6)fS8A+UDId&wWa%x5ScF'
    'bMJ@t-B1=)8msqLd`ZtQpPpY2FX_{q9@E2|9;QRuT6gIEnpBT<F%;R*4aHE`V>y<2Tjo`lO?h3`T{+}?*4<jG9j7rL`?l?yxvEpQ'
    'Onp7|rB#Z27>2TM^1kls@%^>lUgfiw`;;DDKK=7`xIZk1X??5z^~bmS_gC-7WonkLEy^)p>b@$PrO!)GeQdiTYr3i$+QkvywffWX'
    'mo&Y6ir@Zxd08Jz>7fooHBC!u>oKqDyqfcN$onbFo7p>Giq!8}_CF8R<)w=yWpgu^{hSxs(q&oJ`^nAR&iUYtciG%!WA&3?JU&@Y'
    'WSH&`p7Q7E@cEbY@ay5>`SX_{-t*%h@2{HY!&HsaRE$+swPR6rbK?cKb(-tWZ(r(^w{2Ejv+AQ??uB1ow_4gVRYPjKa?GZ-@Z*+l'
    '9Ot1Km!e&=w#!nQrt8){j+a+mhNaCW$0%R?z9Q>~tSH-ZtfoG7)zmJ-H28q7dd5$$4;R;*@~RP?mZ2Z3uJ!YVzHG9-%f~W}si*|6'
    'HZ99lYsN{wo4!6Bzoon9>G*j0S9f)lWuENdG&NI~rqmC0IkcHWC3e-*+|ONp-LqbI@GyK!&jNS4drHIO;o-~0ZOlGeA9bpmO4Lkw'
    'mCC#?e8|(-WKCXIRg+h)s_VD$`0Z{wJ}igJ>-&aN)0K78bosDei%nT%_1FwuJ<mmEbFDp=SFa!U@_hIEZ_9XbeSx~ls%oz5)+JGA'
    'o<u$L!l@h5i7Y*Z%>6uEy}lFZs=T;%nwGK~>S7knmQrYMr+m!IY;bE$Ly>oLSvA>?-yRX=U&9}tAJR)iy1S?2>r1+u55t#-<MYd5'
    'x*ToFej0}^Re3$tsq*^!E~UZMnbl402+m_MNLl);xA8hZUR=27+9pqVF()@lJNNPQ?WCFVWiEUO%jhJgw%xt(>ENALUlX%9f-mX!'
    'm&*aD_OZ8VD9XC*q$;tgx=-y`&%VY!O?f6hG~40!evlWw9KRi=Pr}}Bhi5mc5AgHwIv-x{&Np7%vKPO|x=uqi7sHrRxrm1IT=jib'
    'brBQurjD24$+S1`X8kJT<G3GQ<&u}9RNIu(T+B^hc^}O@jN)eB75%czZJ8~3o-)Z+cKc>trIVK<<va~}Hx*5{WVPQu)Kk&A8hj?w'
    'y}DcKVXn#|<u~u)*Yxy|?(f#Oba5wrF?t|#+e~vimhDny#WK!CQ|I!rrAhKK=eJmH-pRM&LApKP$?+ZKr$6q#9-bptxwxw=F0N*&'
    'x-m<WFw&;lW#$%@E99jeW^Lsu-M*{i=wJG6BbYT)R4!9Jik8(_w5`)Sl-XQPU74I9ajc1ddiyRO&y~k;zkbzE!}M}Fuysn0qOFRq'
    'DVDAg)$6)!r@0%N!m%!@te;cSjs4AAl2a}Bhc91WcE{SLEf*P8HdOWKYDvEHyvy58{D}uNmzkPvX~z$2X)E3G0BWUX*7jvqHbs{g'
    'k#)(kJd)nq%eu1b%3{8G3(}5Rusi(b!@m3eh%RRV&dM-m{i1&J49c$U#Qm`me3wy`yyTPklimJUo?m=dmk&$tXtc5PsGgc8m(bEX'
    'x046eDks~vF8lfeU(w6(^d;@S1r`Z!HcYeZV`-d`<ipOZwsuI`ctVZ*pwH6nZ|Rh+zFh_5@%3RIHUf=f(mOcPbFU?XT?~!VsHvN&'
    'D)O<ZvLRO|ROxTp(~j$@OpAIKtk9QLnfke&vT;!k=1y`qJH`=lrX~B}j@CQsZdVwbYWaJSyD(jhU6F=iPGjd}t8#|2EI|W{H0y)!'
    'Ej|2pcsf3O^DmxW-Q}{b2%M*fGnL~w)>Gq(7>6cRZIgy>EIcze`dof&PrGl?Zm8M;G?KT?m^v8ET&Zp)V9Lu;?%Vj_?Wp?uwsUuo'
    '1b#W)9vhk9ICc)y+!j+N5RYEg*h8*5mqqDL8`A>NYCg8Ln{N5B1!zf#o$;k_lPqM4I<f1Ee3FY)OH~eYKmAQxn~vXBoMh{PHOr97'
    'ULs%hxj-53vy(In-*(%~`M9`eyK??}cJ-WoOAi}WwUV`;>Ue>QNC6=8yt*uReH3NtprNHeK74FHyCQ+~u<FZz80NI}Q{N13+#zdx'
    '{1ZSnZ@kc4nft-5{E!uWJM1~*J&bt>fT2vKnyZ~Bh+3bI1IWPcAZ;n1hiduQzOGM=ythHl2nT_l2F$f&aEQDqDo4C2yTT5uY#Beg'
    'FZt2k^ps$`FNfj&c>^6#a#dB~qV4)o+O{knR^$ZvDA~=+2?nTg{qUalqy(kQ-@)-e(4ryFee<$vkUr$5>>34XKD2XDd~7o}WN&iF'
    'amky!X?$VI=Am9>|82cgc^Yz8PT?NRi|Jz<dp^EC0kx*%*95noE@yMrn=?hx;K>Bamga!Q%c_qO0BAmYXcLI(gIkKM@@_{73t^J4'
    '0sD%!R+%lMd!~T8%w<t0xTo;cWnEtV9ot!k!~N?9(A!nrl!jCfSyc~{hDj^89po%i;W15R+4UMI`3KMS%eTknaG$<cYnMO&)}`N+'
    '`X>!INW^TwG9Jq)-^~J&)!8ZP=7XpE<>~eL#ZB^S`r~N}8uiV~FMZ$Dm~v;j_l~q%<hf(+P-(tYbC*6+5nQpE$g(pnC75W@Yx|@@'
    '$3w@f8Z%$mG*)HZ!y@)w|7Vc;{7)|57IO&=bS$8wZSB5L&}TB)Iv;C^ER449rmowUVSjmD!(Dp%c6feXdx#g4v9a&<Bcjo<bZMMn'
    '8k(ib#8I26O5KzVvzW8*Cx1Q0+dm$+0)AZ3>WOaX+iI$`WecHAecrjj=PaMWaXyoMYo5}U%b`;TtMK8K+8=XdQGoB11GvB@i#un|'
    'OM962<xdYT|KHNxFn>E-zDaa8Bp>2mJ{C=*`vH}hmq{bD^#4i#SEXRsSrD98-2*0OnM+(*76no}rKwTaSH5^CNWe#va!nZ6cb0zq'
    'l6L19Q<<k?ROG7<qiWRw(ni%VUG(wFteD3h2*0yl{ITD&=TmBDwMA9Va|z|I+bRnD)XSbrpR!}EmR6h1?G=lk3e)NMl<t0UJwBw%'
    'HAI9~!Azf{(mrmRriC*1Syb-5W>lk29j0X`M)%_mz8!x{Ycc8y+PDh!%Ij8JH5>KB1ICrsNIK(ggp2j6_EzJeANKFzx~MWuo_JRJ'
    'tTU~zQlm>hc|k}Rd}+xAlu!kxe%!zQ&d`$2i`uapqSl6^w4E<55I3KA=R?F4C?oGK_b+^kFFT&O8pwOs%q?7BMeZx?<kDlQxmvh!'
    '0mPsa{m*Nc{<DO=e1~XcXVRWQ>Ka%`TgdD?4<4YOdEGgjL_)UQzWlk{H$A>yeh$97d_q;o0*Xcp31UW_H&9~toPI*rYP9q>Y-Hd1'
    '<x*>M=CVG`PRW-nb@4rvg+J&9=t5JBb9Vg^kg%^@4xhsCbQud8M>lB^T~@csB;?h#Jx!^o9l|6yb~2559&g^lz9-Ro{?^Mhy$582'
    '*<Y~@Jp4g@oZRe^t6H9M!#4hS`FecV2WZCOS0n&+d=Kg;6rohNnkW@uMUP2!?0Ho;JdCIG1*W4=neYDfG(0|TWm(ghDSsD-LMR9f'
    '%;h-NgPyR8JmqQwkzu&uU;vgbH({Gboz_@PIyYC*S_BO)x^2Z6Au<?hwKmDLf9d@RLEjGjPzJeV(Tqql!kD5~<|R3p>rt06C@{+v'
    '_t8yRf&N0R>D_q#e)5PFr`tIV0R;|rf;%@&O}V2QI{orbhlj`4m(Sk%{h3wuNrwOFUrFK(R#OpO+>KscRH@$jdj2Mvy;2dh7Jvx2'
    'd+}I`dPkP@m)%(XQ<{VL^y9{&^tc;d;?ZpbM}sO+nx+ORaF7P4V)FGWOWI29p--IR)b0RB-`m(0X=m{TME>Nl6oECkLg%?#R3Gga'
    '1U%$0{k$ENnf0=MBR5`NQmW=`Ms}*%D<VV(d{m3IsY816iQ<X0!?JV9H)t$k<(>C1JbgPp-M#wvHnNtw@FBP(bzI<KQ!_>R2WsuR'
    'HqRF{v0O1KjPKpYsq*}E=1P2iewzNjCXZ}y?Ef`7$@^P5aY~}VS~JZJJX3nxb$Ekb5$<Uv<r*4z2B6&c>)8w_zisz{?Ysd9>$Wau'
    'z17$jsD#rbrV6RPUo}UCKe0%M?L+dpAROJenU%zOI^D>m!}IRrGdI3hX<#ZqQAKhaPgo}2n%aAqYkwq5Y<AGEHup8Y9`5H8{<9Zw'
    '71=sOpknATfb^)cSrBO3HV_aPnRZJV{LK90n>%B6KRmV#9*WN{o|lj?;cG(bvgihDGGOF1MKB)n)K?$h*g+fU>FuSSN#~c51%0Xl'
    'd#=+h&+&5RJh~mFhH-&UhhK<ro_GD<u(Jnu*1e|3@TApu`IIFQdW1#mT1)j{=c1=JKS*grjZyPz8zW8EAK%p}=@BD-=+IuiRL23y'
    's|7B4cbPyn`yl7uQFG$3ZJ`2C|8D&F)~<<NvpmDuckuD&#qXli^ha=tP^y6(T@Urz@Hc#x=XCw>ZLMTq$H%Y3^9DN_X|fUKZEsS?'
    '2AUv48UV%!07_gJj`qVe{tajBbQSJ`uUmaiQ3AFz6#&GxTOrdWjZ@YXQ;^gO4=zg|-_-Nr%gT;8kb<aucYKsJV9{l$=mTh1K-_K_'
    'yUxd;bu~$JJuvuc`roj(HPhMAcJI=h_t9QMe(jw-)v$^v!9r^#A~sT*q0fKANAM;DxV)W3{}>AtBrCN64Rv6lrfAd!eVqp&tzYU!'
    'xN$pgd-#0aRjJ=^QN6!%9s{oG+)Oyih!Ut<Bh&(Fo3}T=#qYaXFUk$pO+Z)3+3v$ZoT_|^5^p#bTz4$W5Go)xfB5;FL;Ph(rz{G^'
    'k}JoBj0yo^#b*)YK?tHcT6quctm=>MWyfb$VAKSu4<)08GUDy(w2$&(>IUfMG{{Evv)d1E<y=4f^<&$J09lkvORIA-j3D;1%-R|0'
    'fAMdXURZQg0N@|p+7(*@3IcpYMSQJFLNx|yRsNS3bWC%e#x~&b>_Rm;AD%)$blzDi(pxKH1!RZmWg81#baR$$(hXJGc2ghuRG&d0'
    'ni3`sCs)=CZF$Wewu)F)nj)m=>Q;H6AfU)AgUhU~G?QW|DBGMCaQE-t*=W-5&8QiwMK2y*s3bZeTdR>Rq-+S(xh_QB|LkzO{)UHT'
    '3$;jv20s$l5Jj=xKQz$~BU++PljERMHD2`37@YHQQj5znhx^ZWsQN!hwC>`cZS?Cb>j0OSzHy(W5q?!ulsH{gQ;xwDFWVtqUN$I)'
    'mob@sUeM0<1-c{=qN>E8RdJ7@U2$eg0Z%Whyu8dQ;aUIlMz6Oo$2wq^ajDy;KpCWkY87pzE>%STL^Sg=>14oP=^;?@&%@KpfpSWs'
    'yfR&0HaO(6^BMCF8tf_|$I0?Zuc(f+IB1o{qFtn2c5%t|q)5#D{U)6)k6J)OAK`bxk;?E{=M3c5B!zo7)%1;Gz|Zd3|5)%u47q$x'
    'hCue}GQ&~>__o@N4FZ%CU-qhj`cxNB8^7;)Jbt_T&8<Cer!-*9UQJ#5w1Fcqe$+2m%|ajv-W_Fz^EmfEYhItSl{x)(h_|S|dwhx2'
    '_au5*h!fCA0<iSKr&z3`>Qd&rBuD)BY}WJ~wica-$CuE~tP$ovR`m4#e6F5a<~8C*bx_=K&}GuUh9wB2ZJW;><P^Jo--^%QRn?D*'
    'g71HPIj|McQJu2R(bdx++Cg3cq33qcVgP3vE9E#1H}2r^@$mZXZqG)hU~B6prFL!OmWkYW7Rw_!i&&2qjKVO~S8in2L%^45wAV)Q'
    'whE$X3k)cbBjg`L(To#Ovit0366DKkPse-r%kh-LpJ|WVXTPihxgV+72!<7CYJbfO@Om)$2vYQzJ6ZmG?QT}U`0h*6aNlY<B6^`1'
    '`xbQbg|#a3F^q<)OC-xx3rU8-smgY5VLb=C-UUj*jBd6FXhAir$=@lLnjjZ|8kF`!bUusS@8bU-??C6`+s2Yeww<&BBa!C4@;m1U'
    'fUQugovtcwu?w_b%e_m^>G@aPtGna$dVlzR*Ruz!#?ty$pp!<*gT|v2*E#7c^m1G#1SZ+Zja&Hg_<HvhKk`03Z@`**inHR8(Svr0'
    'W`ACl5)+V48NIav$IjbG+261aq-fVWs{01dNQ*{PKpev%ZI&h4esh#e!9}RZ$*F6~GXHxvv;s^!n$ZD<*P+`e>G!8u=a*W7KLjB-'
    'CTVERgLhRnH}1;C{e&6ueE8MhzWv?B#7h-~n$lNtpk8VMWNLL}DKh6yw`&erv=%~f<9<#E#PG+xfEG1UI=pwq{uNTq5PxMy+0xW?'
    'bmwanlElWNiu|4Vg36nv#*Lf0dOvwF3LF#dNYV9b2`m~a3D0a+gA1vX<h%T-tH{sy^X)kOy6fW}y6E93s`+a0e4ww<QprQeADXBo'
    'SPL@$W!k&&xmp|#5AzoLQl%QoFu`of>C&B1Bv6E<xe4qn7hH)@r)Kx}{CJp-)#v5#`%9qyEBJXiu7zetLMM;VdyKL;=mOHoKs_MG'
    'Y7kjR+g-Q*pOmTH*NQTI2)e1}5!P7rsnyFBvy%#!NN=<ab|0YZx{W-A)ymWUO^`7ug~CQhK?|ZAM&N3g-H^l($>bdYD&S@BCj7Ss'
    'QR9j`zKWD;4iz#GtRGQ`T&mJf=aZ~rNw@^lpd`I<2d8{z_wxuvhblK<E+Sw>ygoSMh@6<u4>4R>A+>bX?z{fCqrbgdEsdgD-H1-o'
    's!aE;6amJduw{|*TU1y=C#Ap%R^j&A<IV+pAHPF~uGP@?A&|h<z@e;!Dv54_g}N{(ZnhRAnEB&>q+QZ0J$EQWeDJO-FM8=i<5a*L'
    '8aKR5FNa?1KWr_zO3~ix@(rDE9}0?Ik2p{I{Z*DQrg#E`nNz2M>n{_A(pJFPr<2xsf;;5^cif61I@YRhA|P4I1b?qj+U=>@yV&|m'
    'kLPx9{Kvb~zacZY-_dpr(A3eLRqSjqTEv$y08*}d__#?~*etc<oZYgW!$UNFaW2MJzFSXskFVn!7v}PwgnXAT5EnWDzMFtOv(8<|'
    '3`r}!4H$34&HvDzLfu9$mF`_jTg)}4C80%Vzzd)|u+)Uk%_oTZ9!yi#!Co7FW{Gsgetu}*NDr3ua`<-nnsNtXu+xtyd#Qutwju%a'
    'b?Er|fI?#?|DA_hc6IOR==P?q(CjT_(WGa))v0-A4=TqJQiN#5h2Rcg0T0P<*~7QB9jGO-wTA+Z1$}|=0GOnY@H`i`Gs85?e#Bz5'
    '-*LWW4`J_P4^Q)sXOY}YWhkDwo;fMtcI+6O6P5_140A)y0Fap4TlS$f8rAsYs~-HW!=dKxRl<}8K5Z03%tk3cXAe8lF6x%JwVM8>'
    '!?A)jcc**n^krXuKbgC^Q4h*qvA4zm$w0X{ODF*tfK!~BblcYhn?F7Q0M5Jl=ePR}Qk`UmyaWN!eZmk(y;Jf3Ql%j+3HfeQMf?0W'
    'Y$g8eGG@SHrD^r6)5<C1N93`HF^I94<8A5#=kDg__Pqov^LcPsHqe_uF`?giXi|tmU|Zf4_*On6qv`mXpqHd{%SN7uZ;v!-&%qBq'
    'wf47&`~C)=7^a1e=aj}mw!f%&w9v*HDG;ODp-DHz{+Cdu&pRrBDryd}QL883IvV;b`Va#k0aLevazN-|fa5KjI317aULkgQ5BOst'
    '6PaO0jtK!=2>4sbFUUu;9Jr2m*Y5vprmw@xn~Y|7+5A?5Ck)9Bj<W8uR2!}W=ytOpqxycsB#_<B{&4o)<ne4B1;YKhfe;`h0JxHV'
    'Pm6CAZ3FE}>;;k*HccK!Kq}q-Aa)|bo^F@p7-~t))F7%2j~hu6>L=Q^^i#{do;sZxo)=Q1XrPLzYVwi-e)mQqhEIP?_vxIsO_MJq'
    '^0$|-s~f<5+OEq&hm4ZYWI~tAPCpR{iYySf4-$u7AY>pP{-!<cF!n+k;iE@{AI^rtEb0FQ_NwAfdlfXm2g9)YTQ)QwxbD4dFy0Fi'
    '_DL^IqjwCOuO^6A(;|Fe4>?*`S4)&}f6I=Z(m!9fVm>l+932skpBIzINGdr3`Jk$3-*zOogfUh7(GA@nzZ@QRVJ(d|nJX~G1<mTx'
    '$%a-}vj1SqvZr)IR>67s=#HQt&!N$Hn9{Dp1l<S(ckLtUmU?4--Y8V`5XV^(5dvnn(ubdvhU0hD^wyrdA8$uZqUFSbRXAeJIt1}D'
    'iwqCHcac)0`J;P!PA_h%FR<N*;qm$Fabs6RyA`e=WLLkl2}hN9i?dv_3WmiT1aTDYzin5qkN3ynGSs{T3a@}?C5p|<2Sh1?n6n^0'
    '>qG}qkI+;##Ygw_a{M(toN2R{lPwr-uwp0m%23P32@gdhbR6=hz9e`rVteDw8=B{*K;xfMihtu_lOyQbQZ`b*pu9ly@J_q1vtt&5'
    ')7VvoD;90#*6sKQ(Wtol`ttI)D=-O(`liLotKiij7*trF2np^N97`@#4e!>x`RIn8r>Dc?o~vJ1Yiz>TnbJXhNuw(H1H$qOReo~^'
    '2^Fc5^8*{&rkU!I<l#V|qMQqvu}W5T%^rb7i*KaMg@~#iZ~oxt<F`SaUayZoy}mEU>)bgVC}Xg2BPUuha>7d78}wHR6Pt-JcKYC!'
    '?hhfg-GSCAQ@ScqHIKp{g$xvHh72=O>k6r27iu06sroziqpC@VEhC_Cu$yaGo(n=ILfVFX6(1TC83eN;8iHXI{=p4}oQc2Ot_V%s'
    'hbe*Jlli7$w#qH=CcY1%e7L90vT9gGdFz%=jHB=0*bj=c%df5umomQQoXX}w8ch@0M&DkM!+T>S^HQB=f7iC+uc(YWELo)_URyX>'
    '@o>US##)?ONFZOZ&fA4dQgWBw-?Xn~+ukOeq7%eXbPO#~g{vH9_cCup9I+A_+0xQ{a6@sc?y$0E%o5>f!Fq*;I?$bVL?694Wh#0O'
    'Qc|>s@(=Fj#BzM{(Y;_mZYnFVToDeX8WklgodD@o9=vYVB8R!KPU3KZY5Kuko$rs=hn){g#}+Otzje0{O4ypZslyWqoCgGtp$|@A'
    'Q+n&Rz8qhU!6}z;pZB(rZ6mUW;58N0*Hy3_5h@WVMg@S@Vv8t;F?w_K4rC$txB**U{>Db$8!~>OS)(<ml^UxqH=mlK37D+Csqwws'
    'x{>?iyxLiv%%d(NK2<o8)9Rs+^s5HIrGZwbCerqX?Xtg#$o+x6L@{)JN$2pr>nZ^|<bi1`UQsp8@hAh4D>Nd!s_-Xk6-la-k8Nxf'
    'QP1m_HXS!x5s{!t4-qE#+4d;FQxMBB?uZH%anTB0!J%9CbcRL#d`#P0G6X{fYd%Cs;-Dl97nY#z>dQLHVq_fZ{PqIGs_gd8?{6nK'
    'Qb}RMbR=Lq%?Zx-oSNI9+LGU6rlI-<+5G0T<lz{Nqd@cM-#xJ{#&7OE!~36ttC&`yLU0OF7#2?8nmpu8yl`%=KaOh-c`Ao+W?wg='
    'B1H`&21L?4jLAf4{P92_qVbqwO2Y(vOgG=Kpv5@WYJMSmA5sId8p0|$^xq-@cN|Us_ydZ)i3e2WkhN*~$d1m|5O*(M!*%cSc9;QY'
    '(WkJiWHDUQdh6@@VVXwI3p<9Q@#fU%T#~7SL`Q_fZPGz#bA9XB_b{to!cD>8=#YCCx(9`9veneM`5s$u(s|$AQMlQ)1(>yQ%$L8)'
    '6@k=R^19iqwRFCioshlUzL)imC+*n#wG$;)a(wSbRai~15B}psA1Z5FPaO>Thj|~(2Y2+_w;cu_;T-~XG5D!S1)RE*Lt|<;BU|Yh'
    'w=zqthw0`#=(jEs*WUt7+e+^Ze*&WQ0a=$Z_QKL#*h9LrqPpfUtxW2N59}oU9(?&|SnswSwRqq5Vel~G4b8|UQ5_n(<7V}*5-Lp0'
    '?mn`q!}@g6-pADE<l9rYA|uwIwuA>B#ubaWDhy&^AYsT-_8;5PaYsF7+)rd>!Q3^8#LOeS9)KAYK^PU`n@2=!Z-+c%Coh399G^BQ'
    'hgBr&Ww<)D$lJU#$sWb$l;o{NREA4P06(ygGZ}E&(i@`LVHWc#gW<CbV&OY!{;-cL=P*U_$y3sf=_6bDeou*j8+p#8VrEPU;ehgz'
    'u{0Ue9KMwTp;Mx&cbogf|BlUUcLxDrp%$W7_f@xnz-U)et%84IVwj04JVDa<fz5=xa6>yKl!g2y-1XS{)n%CNO)&{hs*D{Y0ULM_'
    'jMGPU@e*#GcR}LX#G;hL(Gu0HmQG1X?MK&GxP#aQQ4(aP;`vDI{hmW4oDdrS4YMcy8m#t=)xt$LkB>izI?J`G_><`f(Eez-InDYr'
    '_q<yhn;SxYF4**lpm*dl*r^v4bDy*=l$=g7&?nsKZ@DBrn9xkXQcfJ(4e^`S8~4E~h9ZvP#fE7Ne{x0omhp5T&N8h1xz*!6E1oxl'
    'gY`de_O@k`Lzq*{@+Q!w)?gjpXrqd%m)K>|5MyDypYniDdXm8YwLkF&qU<(k!SU8e!n}i~R4vveI1`Hr9gal{jc%dQP+tL8ytA*h'
    'MA*G6GWaQ87HeSck)*^ryR1A|!xmv=r{UatfNgd2uFlPqz59_0gD6L`1)YKT&NbgK6L9niD_v5W83ujj`OW+Jkwv+8Q<A<IHyYIw'
    'in6XjcnpR#JwAHfFsMB{n=8_-pKdDt+5SDPt#2Fv@^18Ti7DU^=9NWgBvBWsv!Iq|x9(|r8lJzhg?u=^4BPr|uoCV}9~ugl9q>~m'
    '^00q3wUh~wnLJ@fT3o@8`?uYkF^m1ffxNL8R2qX(xeYgAdtDbq;=EUQnL{)y#n#O+;IFXL&P|1_(2PAnP>1&)lhRn?XJ#p(b+Zzc'
    'DU&1*^Zc<*MK!$Ju8+@3xtvS`CC6b5ZcHCbpG=Y51`Zy&p|ZJkN8gc@-5X-;T8tCnX`SL;jWJG{0cmnU5=2Zw|6G=Q^LvYjGd$~d'
    'UlAYGyM^pfEnJ76fpMkMFa1(^YR#Zut?pjwZ{5+k{FG0<eu-fL8&Euy376gMt8g!2L4%yU#3<e}8effSi^Pghvib0KPVJoI{_9Qe'
    'EnGJpCb-iQ*IW!Mu7Us`Gjd>d2^VEdAKcm68`!(2m^E03!b@+C&_PC~wSuys8m$5lmq~W*PsjCKwWsH=uP>1>?!Qk!rvg$QcCDyg'
    'C6^`59yc%I5EYbSgXTl=x_e*ejjTue`7L5jud9*t3*Leh?r=FdaeE~&i#o_4Gi!4VMK>Y5)prKIR7-fr_5DY7bR2(?G^tXBP2A##'
    'dBX@J43+3y>Cu?;<GzL8m{1N6n?nOjeC%$yCSm%?p8oPjo2jLVqTW;&Cia|+7-T?NI4$8zGOAhKemzAL*8Mw5Y`@c|XvNDV|2@CF'
    'j7F(|P$)B?Lg;wpBTIw?$XEyb9^?9B-SJb)mG?Gt?suP`%=z!m_59_ngnn*umzhUp>ReDrjR38fvPeKMaP*&1Yp<X?zq6Ii)ZYaG'
    'VZp2posT-%h;L0)#Qb1^7vZypv0v@~u3m-_M0q9{um3s7z0VuW))*hbYthqa!Wj<@4<fb%A%H;`4v@BTOjG*EF1DV8h++;wxXn45'
    '#C0jgr4=!#gh3>;SJXs4IobX+`gAlO4)Fog(?Q?vhd)-*^@heQc*HS)o1t9HZZA~K4crMiK?x0buhs5XkfBcdAmtmL&Q^CP70Fh8'
    'Ozwq%8BqkFv4kTGOdA0z=B<~g;B3{~ez|TNthw)=hR6c%zQkX*`siVLOHngNs?4m3Py%sn$pWu6G(dmGm}=Qicl|E>_s<(vY~d}^'
    '##{iLUBCrq$QUq1A6E_jEZMJ4!_YL>Eq;0haSV372doM>BNIBLMb;*~NwuS}!0{M4sE0P!5W?yTecV}Q75bTTO}DM(L5d|bW`>RZ'
    'I+~V=>8&k3NnF&q{uKKifv_I0+r%06d^-pm4s;6b6v%HFJsTae1T9a&%~vMqRzPXofxNr&JnB1fdfF!q%wsyrtQCiH$1_VEi$GmQ'
    'lb835chpj&8yJ?Z+W|t!uuh!Z&krCrMg|m`eUV|PsQ2z}CsGk7W55Js|DT%9UEIbhN!gZyjCtq}xL6SCG;vKJAgiebZx~2v#0T%o'
    'd8w~_4d)R3!z0*bp~lN13vFl@lXW9J8qu~2%U~WTo57F9MH;VsBYIk+P#It7#_}}asQj$IqQU~w0Xoe5(xIJ#QsXvddcm#hy5(OF'
    'GQF3Vjl)RG=GXCzkNXk~reBoPgL1AwVF^<26o6ehU%mG8zYbg7>6nlkBv55RC}Y_}1Y<X*GO6^Kjex%M&_eHCJKX6{w5D%iT@rH('
    '(zwTSs$#NKV7>;rE`b4XSGqGpa2^3eEVuKRp->ke+{vak$Rsr;09}EB8y@7GbYmhc%8;>9tM?Wq*;0+yZzEPebG>#_D-8MRDWs?y'
    'W5P4YhVz~KB8(Ek0;~*t8S-?+%Lz%)r{Hn_@t0JBPhJweR)~3%56AD%_tC|s;{VHN=9nagsw<HCYVe#Wb(`w;UHx)Ath$O-<8im#'
    '4_`KHnWOcrMIP*-Ig|q7mJ}C#P9-e&3Og7>u!`Gvbkc=ldnj|iY)#2wskg*nWiEe07G#O1*b)kuAbsnq#Y_fc-}~FQgSB|1AU?l6'
    'vlo^p)P@ZxM@KJQ^2#!FCVa$n_gr@7uyrvmBUG$4Z<4KoDFwj3j%pgTuYTVc6UDoti~w4a2emv_yb)v$X9hh7nv}(i)nW@4O~0!X'
    '*IxWC3&K!l2hO;5oLL_7m=<8Oc387*%L=g2k8<~_K8uZP!dEztQyvqL=1?$}VS%3qFUno&D^)V{?cXZZ&n>2ZGwR~j`RkUU%@Wku'
    'NF_KQLJ3eY3%(MwA)15**coP6qdnz2*FT}n8wP<fT~%WX2-gEf!rfjy!y9UjPKC!#VwJLG=Za^Az?+(OPp{211Q~%#iq3>tAgx*1'
    'MD|E`7G0aESo=+zx%Ar(j!$G8P`}NoV{Hr;P*BIb<e0rlJ&F5XuR;YbLdH=UfxDTpeP8xpr*!csP1>?6=Rv2VY4n6i0Xnao=*D2%'
    '2XjDYF-h2ryv2Ooxim)xU(%nCKA4)v%P*btK^H`*823Ge6rv0hJW3H*C#DH>N>M#uw}Dm2voY)n)d@F(Ps<PkK>|pv!gX#AkHQ=~'
    'z)<ue+xy7ZiOU;AR60iGSPZrT0}4`nH)H6SK8h{WL?NcWZi*TX$3RRYQ2+io-Mzd%Y<a7N>c*V~twk&+<4Q54lSbNh*p|nLDe9nU'
    'Q}!C`uE<(E-R*I5GW>d#NQ5$CiIEiYQE1f^Qgw78=C?7uDBH8@9}g4J!7Oy`w5JI^9RlEl9i<}cVxqS7w65Y~Ru;8vw+qSfj>XS@'
    'swaDbyKVDvH;@}apJ#}P)kPp<D84=+9lU%&1JsHMp~jx2fx62d*Zp#<)PbI6CLXywz*CDPkMFs;UDTiJ>u;(}dy!w#!>{bkKV#Lv'
    'VO$#<K6z$l7-11}pwN#}45FPP!{<YQ;4+(`=|kR>G`%f)niC!)Bgf#REr%}~Wq%!0b-;nB<uD&24>^GJBU0@Mo#YHGH>RDdzuA|+'
    '&6t)7eMuWno%jCg>PYRnK4Q9HXc*t@I@}$hbmAwqV83$<E0ObX(byIs%hw*k9_e@pLYGKJouR70ze`SD7RAY?{P1nXbE|XL%jV3e'
    '(L<ybqoHAZo_7jZ12u;25X(K*rayImet+dF-*`^@AmapZ5f&`#SX8WDH^op#rqV2Uft*{qYqqfCnNwD9HE@vAnq#^$=$sS)!Cqxi'
    'Rhi*Eh2P)Cvfqpo8+MzgsT93h*J8z=z<=OmSkP0+h;+Kbs#6bj(KOv!^f<qUt;p-+PnEwv{>)y?kmAX-SjXv|nE|{67b}uMglQbh'
    'm^HmwF`rg^UM-@Zch#kgH8rD(z{@lmj77-tcv|lnmj=1WNa^Uww&UJ~A4AD&M8k&CS<@hx0)6x~ns6OLl9UNJ$T3laxQNha$TwLQ'
    '-<MrG;hTbQ{xwj0Jp<$=(UL+f&^pP83Z@+bnjrs9o1F0PtFC01U4Aj_;c)cZ6dERqn57LTX6#i2N%juf2y9q+ht)e*j<Vvg&8=?2'
    'AHg5>IE5%Hg-kEfAtt}!i|G^Q`kUwd-bGg)&70VUx-H~Do6lVKrB;*Ku>ixlG=~Fwj$)gdQ&HV=ZBRqzn?$;|O`Pd7YR4^wZ56<u'
    'TN3t4z(TC4bFO{gL@(c<<M{cC$@;o=S3Fj+{J5d+?X+ZYyx1;w5xc`0$N^&(+lCk_Tw)|>^Uk&3RE1Kq%gee5jU0-}rFxcreeg~~'
    't3u*v93NdqP8c?KJC|MV|JZQMGWQUs4PzIOp?h+ihNZIhzod7hLM6_H73^H@Fs~L&!><<u<pNOG#*d-dS>O?REM1hS9bnhf9>Q)`'
    '3b^+;of<9==~cOSIirWCL&LzB+P^Ahet+SYOucPPHtvj)LW<oFdl&xY_1on$REMo$%)X{l&qIsAZ<3(5iM%!p7<rM!{FY|tdZ!^|'
    'chBD-5Emb?F3u3r&(J%T44oSDfcp?PNr`h%T*M72z_NGUH~Q`NtId(@0tjGaDOfs0lrgXt6^sZOv~^bPW?W2Hue>u-`DArYunv+R'
    'T}d&*sI=7nHqr>wmYkcaaoP04{=WY4`0GX=b8XhT;91f4p}!f4ruk~Hsl^Nn&acrP)!rx(^VT;MQ9hb*NG8a3@e!->*>eMc!$k@y'
    'tm+)^y4t(m>;21Nol|<bEHrv4JZOWK7Xn_eS|2U^n7;{(XWXn^Q|vxZZ-YOV!Sef*p8##4DTOa|K*})+3X{Mr6)t<cxnK~gX0XrB'
    '9sJ;sylZ*mjHEZbco2TMsfHhIAb7w$w_gerMo-KnhMmiweUUk<-@km_Km$VT!IPGwBAtw`B&#I#sral9$92C(WG7YGx$yG@UfKYa'
    'VD|3X83}U=FI1kFRlp9)0}Lz`YJ|<Uyk<eqc=N->JBSV!_98=l-;P$B;Y~w$`wLqnb#OM<VZVFbU{b;Ib^z31!%*ughe6S8AQ0g+'
    'EP`>UAcLaDw)EKSjnd!Ui+(Voy8P3rA*QB{Ssp%RCz((mIu1H@#vOIe7~urF_YOW`wm|Yf@Em{L$lwJ-er3VU0zJgMDmkTj<%=L='
    'JHeae|FAcgKKEnR{3>n8UaK$^lzTMc_@`l|_6|GOm7qyPD2gf=)83Nh)a1VWTRl_upbOU_6Oq)Mfm0j9DFyIwBi{f3)y;g>ig!3O'
    '7w<y|EMG+q<}sbu$O@N*<uPT8sQj7fH5zy1W!J5G%6JaX#~pfJLxQNk{lp@qQ*AJMqA$>^pj;-AnYfyVa`*3MU3Oaka^}PRP6^1R'
    'jP%n7wSHBrfP=nI<JJ*3J#*R{MqVFRDDm|%2rU~O0mN*Nl|6Ad@kw%OU$$C7|08-Nkkln&%if#f<e|B*Wbl=m>s6wWt=Z*_49#d`'
    '4mwM?6_p0xakA|9mMbU2$S@Lp8g{sAn~oGLV&^z!39LkMcXJc7NkW8?ue8j0D>I-9eE9w8^oBp*`73MlyA9GzAKX3dW_rb@g*GsA'
    'W#iSxNR}v<)G*Y8`85l_O{zMN9Jzed>agnOOXsG-KlgJX0pWE}#UP6+#)FIFMRC>oXQ%#s*7aeM<;jQm4wFoWvo)h9sIPfU7nPSy'
    '^x65QTi;)Ha7HBV!^`}M^$WCM!=sb$O-Ed&A;S6&Pa2Ubjzk`#doYC|Zez2_P58?mb}j5NYwwQ%w$aw;IiYI#u%pGQN5nBGY>vyR'
    'x_aUGw>PLEj5XkyG8QaGB{CCIkgoO=X#@+PAQ+m9vvr4@=Ev+hYGIvY+V27=^(i@VghXVh>Ydbw=XQhr9MtuV6(0|egeY5yn9?aQ'
    'mocVBRxzMpE&mP2ke7_8iqS^iwmJIQ*vcO-sNjuIC1{#fLs<qpV-Ax?9dp&N3>$z6n%-;z1PXlRWI|AI@Uk(TpoLf%VFonCCmVAm'
    'g0zhKHEw=1C+~*!TUm(#r+(9ht_Lc~id(HH>-6i5qc{6O48wgCqJi`xWxnY*{H#U&ZTLQr@zdMS{%-rXduSqU_Yf8dG1{w&v9?eU'
    'PBMjwkTHUwp2=CpZ8q$l4ec4KNWsjZm4Hq)PfgUu&<1s%v>2YupCrZ;;L8*r+Rna1G8z_TCNnV_4oNikA#SvLdB{>qn~FQ8+|*fL'
    '-pM-t@o_k8%p=Talg2dqqYy135~vMuxRaTk=Hmnv4fku)H|D$*_<Gd7dwg>Z9yIrW3p9^fLmpiw1Wj2W3}a}k(3ZuadYJYt{1TNf'
    'vAv-b@f0>o6K&rye1eA%{cA~gA^IoLGnvKF>_gfxx4YL~CAg=nJv}|GqbM{Bw=7KAU?U8T2sP|gg4_|RY36FGU=JMdEa{?#y<!tr'
    'QkZ%mGy8#<H>o%aw3{_o7L`jK5H!9U)6VUA3qS7Qm)FRw_Wb-J8Jb#!f;F74Fdy*yocloj=g>n&$J{i5YZkxa^l1Y3!75rgpi#nP'
    'A%pe_hSwgfRJSky-0q6iuRDTdsDhBfftZMCWXYcq3gw|FXky&;1XMICXzP~8LtpNG7#P2QFcDThxV8)-I9i!E9us=>oH82qK7<^I'
    '0${-D+6|mj%w4lkff42&PoaIAP(md7rj>P(8Q}i(`cNwOVskLodt2B)kIDzohE0tkS_4FafYS!um3@sdMWI^9kmT2HWB)AHB~<s~'
    'jsH!p7^XuIUJw~|*Bsp$Za;POXl~oV8%yVMxnt%QS_H<Oq?2^YDB8fu(A%ga*x8iP0UkEdn*Z3szV0W50IQQ?Ojw-8pSl16zaVG}'
    'L!h-LgP@#mO3D9y^}kXaR|Axd)EjCN4m~D~0)i1mw8-TC(Lf3v5B$!ZSWO?=#tx<>E>zx6s%^QjX1lkKwnVJW8!(R{8YUEjYrFhI'
    '``A62)p!-vS0C6F3j_{NMHr;_kwR<Yu?bTbFJ*W2W@19?-M*1uaXIj5Gc%cXs{@UT+F~WEO|9EXbrhal?(D1gfY|epzHEyx;kBNB'
    'sM(4zo-w?{G&OlVGAx4#TJ^F63~iDie!79@@Uq*wFLdD}MWVXY2<gKQIp{4ZOk!DAn(V^$ug&IbL&V#3&0SLjEz_+ci7d=|(@H;C'
    'XEs6H=vkUje@<7Q%C{}-o>q&=wjkSAp`}qbw)J|At9!x{I>zYg`^LPT8~5>jFzhaeb6jAfkd`9GXcyteGe$Zor$7SIWyX1nA)v)@'
    '?Pg9red)!7lXMr;s-8AFgss#?F$4JqG{Zji2B(k!WHHWp7*J>>R=4gWhC4j08J3G`bNr}YdmFP2=R6CeGj-@{P1`h);x6sleV;b_'
    '!|&|nlwsS^!wv-=PS&ETQCNfnzE`92!nvSGM0`ZUaFSpGZGPKU_Atmf7)~(+k>5QpJlC8mbP5A=)ED!5=a{YyR=hTJLFhSqZFNEr'
    'w{XXGL9nPL^y;|?m0B+@I^A<rBehpOT^lw2Dq6VP1^kSJ^B8LILM&r~72OdY*W`b7e6OhG0yxyGzH%%3471!0ro_;rVx;QPP>%PJ'
    '+lK8g^}cUsZtC*dTzk1ceEI4uyq+)AZ<wJQf(H1DQ&>k^)#w8lBIR2S8ES)(ZDNFmMi7Rt&9c4(*!K`tsFD2MEl)nz!={=;kko0`'
    'Xa=jdOvPX^qF5mf6vc|DM`nM$b}OPdV#Dz8`skRfwczo%Y|L@fN6<}@W+5LTk0NXPFt}4;dt}HZ`lRJFU;9wZsD1d^Rq~fU7OGzz'
    ')~irSj~=%{Pm8G>&vQ7pHgWLNi%pdG-<STOxv{>GYs{dtm?jqz{upV(h*c+#(g%IFCgImp6W4icj@N#&2;|o>$FVvkJXx;riJ>7S'
    '!d{F|bLZ17Vl@dHL5Hbt-^V6t%zO_2W6V1fCn$6gq}L^UTud-iiv%YUZS3lMB(`vsVxkP6XUIE)=R5`(@TB#0f)Yx(J0{>RMw#m9'
    'hJ9S2ps)x;hTB-+Vihhs!m}AgnaJ5iEU8xapKQ8e7dy2KdQbYv@?a`MEeOMQ{V!!|A0;c(0n>?ie_UOqog{vDXUX4IiG~B!6Yr~0'
    'p?1RQY}i(CpV7><C`cmnIw3G#yNByY*a~5uE24!j)6I(dMrxT2!4Ym^BoPX@!*TV45FJ)Gp>vCLd&(k5Jj`pD2?S9lOyv<^wqn|F'
    'hRAM)@P@nk1G#3>{1mMyOvmt25*%>Qz{!+~nA-~Fm^fV3!`12Uc?Z7H2%)=%UTYK+r=g{5QR0_~=G?nX@}QIpo3mNfrtMPPwvor<'
    '8q(cthw0Z1*9iayT5X)tkj;4m3RFlpR+pkFX3j4`g6VGC$jVdL^I|edCEtf66X&25v)@LVgf32IaB>pVJ*F;R8!aAU{lFH3u|Yn-'
    '5BYfmJ<wUqVrn4PqPxomG}8Hx7*~;pZZ~Lt<JF(axvzR%L!0^vK}4}SL06-N8&rF&Yx`<qG%3cTj3{qz+sn1BZAOV8=RC-U85;tU'
    'J8cj$wG@^ZzUd}>y^D6dZ8s+_&905$gdrul)NsLJ8r2E{uXEMf@X^+r%7YJo^($IMr|0~9r}z}QpiqqIq%mF@({ya=;6h@K4{lx_'
    'T%JxdUYiO&9;V~>oot8I@QRd%Stkg##BB7{9#9^<-!h~Myj;z78*bUf>AieOM;1C;<WPf*@m?657`(wZ36m?7WC%CGFPDFWl5Ts*'
    '#80<z4kz3@VwA(-VGDCHSI6C|Ate=>LM`FGad3_PAwxnBA?DD=%WrxlZ{PA2<QTmQo*i@)OBRF5#8bsnm50YszN7*NJ%gQJowu*s'
    '`GG{c8zRMdQ%owV<v^Nd+IW-u&~OQtFYTrMO<_B9({|n*&6U_+_Q<B%pdbWwTRm4}0T`JgpeXmF0*4XlaBJ-iH+@5AhVS0zlE*}p'
    'A!DFN389_oItBsFA&682J2YYIn=RK~%75NJAsN_*)3Fj%&)Q4a2ZCaVP+~$P?R8jY;MM_hF{`f48@-(|typ%{dB#F-787yx0EDn$'
    'c=6zZOkBwbpHQ)po_R;0eHp9MRo8E1<|X?5VR%(v4y)6^Ci}-1Q^&M|E=1_~linJ_Ed44_LT_*i1zOu&yCMJOj6ARDf&m^Rk{I~W'
    'heX<mjTr{(abOHjF-?;pj(BtJM)nhjV<h&V?;F&6VUA-j{u^4&YL$d=Sxc~~5w4ALaJsY0{A8N@U@E}IE+UNhiUUw5^dP(d(uB=M'
    'h15!p8Nr`+{K{Qip!WWy%yiTAam&^L=xcVgQDgL4^JQ3F69tBw%X00967{XmBPLO9O=h4OpOKeDj1=ahF)4%JeT;o$xhW+vLmV@&'
    'yA}aCvuy9q(${eR*(hz0ww=W;{IMXERS*zyR`M9k4Fh1J9IfL1%59ug{BOJ2B<ScN<ald!6@0_sW4KcoCdg0*>S~Qbz&1R+ynY)T'
    'bVJ`QKRnf0m%|oe8`fUTl0<zCZ*~ltCI;C1X0eyxb3WSU+K=<ZLw-yfp<y(JUAHexu`=_u#7$ga_D^lxa^3~_PG5GeZd!dG3%U!y'
    ')P&eV-VsiUEHhfMK+haHsS9d<ofQ7s_psWQoh(ZBK-odgSsX;pKYVA*tdp_#u_?7)5mP_W&x5wHwTtT_(ij%NCMhIuc!;^mRKZk~'
    '70!(60Eta$i?6b^>UZyq@0ZkhzR<?VqaoP#MEz`|23;k+EG_9AKP4n##P?I&-Q(`nceup)xG{ooC|iS;L3{DyNoYKMr0|A~hQw+~'
    'o9vuF%|iA^KXWx3RELa}z9gyjdCB~1jc$xqel$h!vD>t1^Lq|6@7=q9@s2Rz4{S4|-kJMSxM2yvrkD_~sZ7U8nXdcXbo*A^9oX0)'
    'a>CXW(}&@8<g%Ih;2D*n;BwhdL7o+MH-G5*4e!eVOLT4{TDqz-1Gh(XrUzQ5a5%rnXNJRtiCe#G#fVw^lmrCscx7&p5tc67l=L-L'
    'Vh|f6qOchX?U#B}jQqp0dm@DaFe&^Vn;7JyKH(8;NNOBw2oT9TMh(<s(`xdERdJG|54}Nub}0@)p3lQl($F@?iS9{^$YL%GYbCRL'
    'Hfz=&R^53+(4^!QPoW`vvUHfq0%~wDWj&j9BMzV$Myzb&!vC@Gju}q4y6j~*$xdBNT5Yh0P%;KcL9I~kyaC#N0K$7qpK9?>KPK#-'
    'Ubg1V%Zp_}F`|=E1>~rRncQ%!DXsxN+~RbttNiYbsHR+wPv4?vNER~O|M5RI^haO<bL16rnaHnO8H4Rjx<+-#BWSG7Z_WEwwm+_S'
    'W=#eHvSs4WH8fNveEd6LHqSj#LGCLJktFjLj(U6H%67%FXS{!V?dV9F%b4QRp(E6O3ETeKY-SE+OM*4qg@bkN+Hc_YjxE4B@Wj#Z'
    'R6+V)VUcQ*X1FB~WTy~jq?lCw?x|Mwyu=<pDGwK8Y5(h&=i|eLUkv}m$Hg>?;UoloefZ21F$V1n@I^<s;EBGQ<5=Yvq>N8%n-j|R'
    '^JDzu-IFb$royf=&<dnft#^XS8wS>)SW&x`0g=AX$&Wdp=jqzdpJMptf4%(va%sj;(L>C%cxO+L7(vM`oo>R+kUtn*k;qZJFJ%(~'
    'KfV3Pp9?bnVhB-$OTETz<7bG(b);*3ID$*zU_!8FEu++5S}pk0@pqqAtbL;^MJtZv!ERc;pi^lEBHEtHL7T9~b%!x<iGR0ldX`sx'
    '!sm$I!nttuCwJ#Rx%+Nfa5;UcV}LPA3;Ro6BF3}fIGDjGcL}Zo2nHX=KYMQz-+%8@^ktv610i*_il76W=OOTstnkev+^-C^P_qwV'
    'MrFX>&rVRZTtAP)ug>ZB|F{u!!%^PwSQUV3XduEQ*>5qLxL`~oe;z{IzS^<YX}IRg|9$+w()}6_{?Fm%>jnnvV#Uvwa4UoYiyh;u'
    'oQHKFUI66YcKh>!^t8Gr$@KNpnVmt5czoQJU$P*?6QQV$pim$rOfmh6U$l5{8V4aF<?Bz$pFdmk{MQXeo!A}&?M!YmXg+{$Dm3F5'
    'Bifr{Nn;C)`DtGG<C3Q=|MSYA+nBy>YAVj03$6&CBjUzE(t;{Rs}%kw1SvSD^S<?FN$}+ZTdrS+N|9F^dYbk<Pe2-OI#04OzWrHH'
    'KYmI{`^kD=Ud>V5c%EfHL{}8v=(>~%lA&Rp>Hd*eFu4#LaA*5{>oG`s*%~_9#Hb{Oe}0hB=AxhH8)G^m7LH?B*Tz8D>D^CqI(#}A'
    '9Xx;jdRUm7!|hIU+a8Y_(SQ>iNh)7Owy{*oFz@h#6Ov%^FhxvdK?z#1W9e9Hn-gKQy_s-~yTc!pRR@PfpbTlQ=2ba_f{9sb{Zswa'
    'e=PX40?Av(*dZ>QkdL$QEn%iijf;j$49gr=;f59KZYi_0W5w6UO=iB*utY!ydiFte(Uud}t7z@p1P=waWGbm{cyF~ig~2v@^B)pi'
    'U;lHsb!~o=Rk(kVK}dbfL<Oug1S;+oRPQ>Z<`lr*Y<|_M#wHv#YNjz<*>xmHMlI>qP=c3XqY<;2@H$MAtMe>fwe02vHie8|-wLTZ'
    '1$Tvk!hix6wn~83HkffSwIjb~(Nisc`8J_83fMo~d<}>2!Q!x}7$Iqd#}Z$>RejFvy=C!+KCPd}r+>bJIhMm|K=Y25E1gHf<kk)7'
    '4KI{%M#a~lc2O~gb7klpruU!ndn@mui4ZPuwGk1-S(baaA&g(7f#H)9iWj!a+^dSKfA!a`z{I$iypVo@|44YDYACqbe6?e=G_=_@'
    'TQoZ6YZu-zw^o&?3D>ZX=q0xX<LK(^SgNHEJ=@MNC-Pf<Y8iQ2`uX`aeL{edy{z_)k1xZPT%ksIc7oigGA1OgA{+!9Z4cZHUUNaq'
    '!uz=2wdVF6r(J+fT@5W`2Eu?LChr8wp=Ncpf^-TOkX(4za(k{gkSji>2`;9sFYI*1E8i0RgT4tQVALmSxe9eV7kt^uJW>0oV|n~j'
    '<AkffS*V^R$F=y1JxzVY0At@xiq06rDaYQC6WP04#RcOIU&4l*xe1U%nJ@n9;^K#>G^$<8J-WUXgB!yYidFB2rbQ-iRBt$3Wd7dV'
    'C`RBBe)BNS?RKsBGk1W$#CdaGoO{Vnj0XhbBjV=)16IMM3?<?cnDV%5vC}A^4H6WoR3F2dnLam|6wquKzS=fQM799BD9-D<U&A@B'
    'zx{R3T)!Yq(^v$S+6QOWC9XrkdI8F+C=0yTUWV@dCFMVdh^L>{<MRAw9<pH-lXubD_U5!D91{=G5BL8u5auci;}}P`y?WK{aTqHl'
    'Gfbb<_b@5_%HXg|%3vhWY&-~^vL)}YUs_XtJ}%3ajGj{~FI<^|^e@_B`usys+dHk~ft)Xl`{(_ulL`LoIVgvZuNxdtL&ii}#6I5A'
    '6~C)lRp|91{z=gMb|MfX%lEIm9Uj2OVS2<{!|*2BPy;*lrDPBY*=<-s8gdnqhAY;z&Of*Ka!_>kS!}(`ujYUhGd&PY5{m-NQ#gJX'
    '<~Z54i=JiU&l_DCaznZm9T^UcWeBSxN@x)Ilz=|`3TQX#D^6Er3_Hh&nb)<FM)aKpV3iGp*;0iHQ-y(7Ij*|Ey4=4w>``avWjG1D'
    'e&0Y?P~YYF>?%^+1rY5n+=*oqZU?oof>olL4f~gWc>ESCKbxJpG0TqO&ydCFwjkme))g$YF>Dgu3utiK48RA__x`odx6w&jx4}k~'
    'tWi#dft>+FU;ybct~V}|*U^XnRp58y6^qB8-+fQm4_n;XI<Nq#6dH`rJ4l!{dj`&wMHGDe*U0PgI_+OS{3(}vf#of@eOg(XpU)xg'
    '?N2|S#JQi(>B8YGRz2)%vl;NGJD-rd(469M$i`yERf%ZJ8!mA>@J8$QfB&}sY&h@SdIN2yafRmLSl}Ox0VTp{bUg5txpgR+Tw;5^'
    'w37?wJHhlXHu5q?{oEYl9j})MlZhv^9VF+W?~Q?1e6PAarz})Pbee0&VMiU7!fD(0qr!w)n9Vt8wG7l~#IwFLM!tp5Y)?$v4Ys+T'
    '-9?!(x)QH2yH-xbI5wGB_yw|_PGNETE;JM~IFkVkmjfnWUTVK8B-=cX00to#LQrjSR1n&xpz;C}-;G!&H=$2s5JQHiJ->@rsZJxL'
    'a_9iDiX6FR^v2ql@C<nhGQJMVyZQO^)0gpX>t{7FBt2LkM$^RoQ$&KEY1+8|fd5*|3>;GV?uQkEt4}9zJu%1qJRg>Ic;d@pqr)k2'
    ')n(#>M&lC>lM<RR24klh5Q5>Z5<D<;v3KF^*=BXPgRwbarUl@VJ2|3xxWkeULu$J?CgX+2`ELvUrDndo@)TpIJ3p;wR*w5Y&XHpD'
    '(iF11HijTMs?+Y3H{l;1Xz*<Z7S}{<^rMiPltEs07P+!xtDW1vn>ns)y;;tD9@gf`hD#~lmfFgIw&2niA;|#Kra*^99ddPw4f)Lb'
    'Pxr4&imh+m#mmu#^RBu}9j9BPVns}L{7^gVRite2f!|+@`xgDKK)(D{l5}P<#T?$vStdx>VOk062ZlRNp{eBaH0)b*2h?Jy5E~Uz'
    '1@ncJ%d8UJ+%&dPFed>PlqqkmcmBvgpua`5+epvCn8GADIX6`xbz~HNic7peq)p?j!rW%*cCNYdi1#$!^ajnhc6gY$(IWIAs@H~c'
    'dH_A{ET*@3OiO*;x*LNNXbfV0lM|dM*a03KNjhqBFd8+DMn<oWZ?0PsNBOYvggwC+N9l9q@c@9A`uZ^KWQ-AX0T44l8LwRSEvva)'
    'SOSBq5X3+VAzLl+`V`Y%Fd{-~K+q1l9s6?M+MB?LlG!<8e^o{=Bh-{Iye0f}HQ?%)hlYZdkGogfBn$xvXjt>m^+KXm6wM@iL<+<A'
    '2>w?LyD>Mox@yIrP44+C<es9U3ddsI8BGSxf5F{U#2J;0YDcGM%uK#-(P!!Bc)UELQlV;SU>EeVIKXQg0k=A+%_w1U&q#@eez|JJ'
    'yG_)YV901Bkr({nI@Q9V4B?a_&1Inj$^*;xKOa)LvFt9ks$MFK1^y_~F+41t)^>;thHA((su(%V^u2n&WBv2xSIxx+3r)QN6#yji'
    'dW;@5|I~0A)iM{X+6Yqqw7G8GlcM2rqyXsgbVJ{4#V1pdkPUgA&`7D_V&Zi?kK+9d?cWw&(@-4FvmWVkIEI~SBE$?Z;&6;V{nr$F'
    '<Pb|!jj5#R`}V%-&FGKghAsoe2YSUE9mc$bm6RKZHB~fsjKqL8{zq;4zy6Q^2X}KHWB'
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)


class ShippingPolicyTests(unittest.TestCase):
    def trusted_main_projection(self, root, raw, source):
        """Authenticate fixture fields; never call this native D evidence."""
        payload=zlib.decompress(base64.b85decode(_MAIN_PROJECTION_B85))
        self.assertEqual(hashlib.sha256(payload).hexdigest(),_MAIN_PROJECTION_SHA256)
        tree=json.loads(payload)
        self.assertEqual(len(tree),502)
        self.assertEqual(tree[inputs.AFFECTED_POLICY],blob(raw))
        policy=json.loads(raw)
        self.assertEqual(inputs.affected_lookup_digest(tree),policy['targets']['main']['lookup_digest'])
        self.assertEqual(tree['tests/platform-profile.json'],policy['targets']['main']['profile'])
        self.assertTrue(inputs.AFFECTED_AUTHORITY <= tree.keys())
        for subjects in inputs._AFFECTED_SUBJECTS.values():self.assertTrue(set(subjects) <= tree.keys())
        # Installed workflow authority changes only through a complete enrolled
        # tuple, exactly as shipping_context restores the actual installed S.
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        accepted={'npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','npm-consumers-sync-ci-budget-cleanup-v1','android-owned-npm5-sync-ci-v1',
                  'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1',
            'protected-producer-original-default-required-context-v1',
            'protected-producer-optional-parent-source-v1'}
        matches=[row['workflows'] for row in generations if row['name'] in accepted
                 and all(source.get(path)==entry for path,entry in row['workflows'].items())]
        self.assertEqual(len(matches),1)
        for path,entry in matches[0].items():
            if path in inputs.AFFECTED_AUTHORITY:tree[path]=dict(entry)
        return tree

    def target_context(self, root, raw, source):
        policy=json.loads(raw)
        lookup=inputs.affected_lookup_digest(source)
        matches=[name for name,row in policy['targets'].items()
                 if row['lookup_digest']==lookup and row['profile']==source['tests/platform-profile.json']]
        self.assertTrue(matches,'actual source namespace must match an unchanged protected target row')
        target='main' if 'main' in matches else matches[0]
        # Equal namespace aliases (Android main/VR) must also share the complete
        # native reader proof, rather than choosing among incompatible variants.
        self.assertTrue(all(policy['targets'][name]==policy['targets'][target] for name in matches))
        return target,self.trusted_main_projection(root,raw,source)

    def test_shipping_manifest_is_complete_and_backward_compatible_registry_is_unchanged(self):
        root=Path(__file__).resolve().parents[2]
        registry=inputs.load_registry(root/'.github/test-suites.json')
        raw=inputs.load_dependencies(root/inputs.AFFECTED_POLICY,registry)
        manifest=json.loads(raw)
        self.assertEqual(len(manifest['suites']),61)
        self.assertIn('native-owner-lifecycle',manifest['suites'])
        finite=[n for n,r in manifest['suites'].items() if r['kind']=='reviewed-patterns']
        self.assertEqual(finite,['documentation-contracts','release-bundle','embedded-web-qml',
            'places-native-qml','recorded-voice-qml','snapshot-qml'])
        self.assertEqual(registry['schema'],1)

    def source_context(self):
        root=Path(__file__).resolve().parents[2]
        registry=inputs.load_registry(root/'.github/test-suites.json')
        raw=inputs.load_dependencies(root/inputs.AFFECTED_POLICY,registry)
        tree=inputs.full_tree(root,'HEAD')
        for path in ('tools/test-evidence/affected-test.py','tools/test-evidence/AFFECTED_SELECTION.md'):
            tree[path]=blob((root/path).read_bytes())
        tree[inputs.AFFECTED_POLICY]=blob(raw)
        # Both the source PR and its exact installed successor run this test.
        # Authenticate the actual complete deployed tuple before constructing
        # the distinct approved preinstallation B; do not bind R to B instead S.
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        previous_rows=[row['workflows'] for row in generations if row['name'] in {
            'npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','npm-consumers-sync-ci-budget-cleanup-v1','android-owned-npm5-sync-ci-v1'}]
        previous=next(row['workflows'] for row in generations if row['name']=='npm-consumers-sync-ci-v1')
        installed=[row for row in generations if row['name'] in {
            'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1',
            'protected-producer-original-default-required-context-v1',
            'protected-producer-optional-parent-source-v1'}]
        if not installed:
            installed=[row for row in generations if row['name']=='protected-producer-seven-target-ci-v1']
        endpoint='.github/workflows/pr-metadata-context.yml'
        approved=[row['workflows'] for row in installed] if endpoint in tree else previous_rows
        matches=[row for row in approved if all(tree.get(path)==entry for path,entry in row.items())]
        self.assertEqual(len(matches),1,'source must match one complete reviewed current or installed tuple')
        if endpoint not in tree:
            previous=matches[0]
            codeql='6d55d0fe4e9edc86204c66e1fa3967681793a2cd'
        else:
            actual=next(row for row in installed if row['workflows']==matches[0])
            codeql={'protected-producer-original-default-v1':'e9aaaed9693efc5ffb4701697ac2a4d51f5f5ba1',
                'protected-producer-original-default-boolean-v1':'3b7a88765b7181a1bc7dd6f48b9b459e590055d3',
                'protected-producer-original-default-required-context-v1':'7b0703d88d404f38c1b3dec92f77f03586c9144c',
                'protected-producer-optional-parent-source-v1':'7b0703d88d404f38c1b3dec92f77f03586c9144c',
                'protected-producer-seven-target-ci-v1':'3a273057a38255ca368d3028594fb94227ba7c3b'}[actual['name']]
        self.assertEqual(tree['.github/workflows/codeql.yml'],dict(mode='100644',type='blob',sha=codeql))
        tree.update(deepcopy(previous));tree.pop(endpoint,None)
        tree['.github/workflows/codeql.yml']=dict(mode='100644',type='blob',
            sha='6d55d0fe4e9edc86204c66e1fa3967681793a2cd')
        return root,registry,raw,tree

    def shipping_context(self):
        """Use the actual complete installed S, not source-only B.

        The native inventory includes the new reusable workflow's membership.
        Its protected certificate must already name S; this fixture never
        rewrites that certificate to make the shipping positive pass.
        """
        root,registry,raw,tree=self.source_context()
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        historical=next(row['workflows'] for row in generations if row['name']=='protected-producer-seven-target-ci-v1')
        self.assertEqual(historical['.github/workflows/repository-checks.yml']['sha'],
            'd9fefd275d9e3c6977cf9350a1945a6bbe5051b4')
        actual=inputs.full_tree(root,'HEAD')
        installed=[row for row in generations if row['name'] in {
            'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1',
            'protected-producer-original-default-required-context-v1',
            'protected-producer-optional-parent-source-v1'}
            and all(actual.get(path)==entry for path,entry in row['workflows'].items())]
        self.assertEqual(len(installed),1,'installed S must be its actual complete old, Boolean or canonical-result tuple')
        installed=installed[0]
        future=installed['workflows']
        templates={
            '.github/workflows/project-tests.yml':'tools/repository-checks/workflows/producers/protected-project-tests-android-platform.yml',
            '.github/workflows/parent-qualification.yml':'tools/repository-checks/workflows/producers/parent-qualification-android-platform.yml',
            '.github/workflows/repository-checks.yml':'tools/repository-checks/workflows/producers/repository-checks.yml',
            '.github/workflows/pr-metadata-context.yml':'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml',
            '.github/workflows/sync-validation.yml':'tools/repository-checks/workflows/sync-ci-selection.yml',
            '.github/workflows/browser-client.yml':'.github/workflows/browser-client.yml',
        }
        self.assertEqual(set(historical),set(templates))
        if future is not None:self.assertEqual(set(future),set(templates))
        for path,template in templates.items():
            prior_callers={'protected-producer-original-default-v1':'81bcf1933edc435826e2de411a777cccd4dec7c7',
                'protected-producer-original-default-boolean-v1':'15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a'}
            if path=='.github/workflows/parent-qualification.yml':
                # Whole historical recipes retain their real Parent bytes when
                # the separately preregistered optional successor is installed.
                parent=('987d8f0d198e40211ab0f33286a55852e286c174'
                    if installed['name']=='protected-producer-optional-parent-source-v1'
                    else '9bfc6f8723b1f59426f913472b78206844a7f201')
                expected=dict(mode='100644',type='blob',sha=parent)
            elif installed['name'] in prior_callers and path=='.github/workflows/repository-checks.yml':
                expected=dict(mode='100644',type='blob',sha=prior_callers[installed['name']])
            else:
                expected=blob((root/template).read_bytes())
            self.assertEqual(future[path],expected,path)
            self.assertEqual(actual.get(path),expected,path)
            tree[path]=dict(expected)
        tree['.github/workflows/codeql.yml']=dict(actual['.github/workflows/codeql.yml'])
        if future is not None and tree['tests/platform-profile.json']!=inputs._AFFECTED_SHARED_PROFILE:
            # Source13 keeps all original owners. Only the installed Android S
            # fixture applies the separately reviewed exact seven-file handoff.
            owner=json.loads((root/'.github/android-owner-transfer.json').read_bytes())
            targets={path for group in ('legacy_workflows','source_contracts') for path in owner[group]}
            self.assertEqual(targets,{'.github/workflows/android-tests.yml','.github/workflows/android-vr-tests.yml',
                'android/common/tests/android-workflow-contract-test.py',
                'android/common/tests/ci/validate_ci_contract.py','android/common/tests/ci/test_ci_contract.py',
                'android/common/tests/robolectric/build.gradle',
                'android/phone/tests/phone-release-metadata-test.py'})
            for group in ('legacy_workflows','source_contracts'):
                for path,item in owner[group].items():
                    self.assertEqual(item['source'],'tools/repository-checks/workflows/android-owned/handoff/'+path)
                    data=(root/item['source']).read_bytes()
                    self.assertEqual(tree[item['source']],blob(data))
                    expected=blob(data,mode=item['mode'])
                    previous={'mode':item['mode'],'type':'blob','sha':item['reviewed_blob']}
                    self.assertIn(tree.get(path),(previous,expected))
                    tree[path]=expected
        return root,registry,raw,tree

    def bounded_context(self):
        """Seal a small synthetic repository while preserving real definitions.

        Real whole-inventory shipping/legacy routing and protected iOS proofs
        remain separate. Repeated mutation cases need every actual authority,
        required subject, CI exception and currently reviewed import root, not
        thousands of unrelated application assets in every negative plan.
        """
        root,registry,raw,source=self.shipping_context()
        policy=json.loads(raw)
        required=set(inputs.AFFECTED_AUTHORITY)
        required.update(policy['suites']['device-control-plane-full']['native_independent_paths'])
        # These existing importable mutation subjects must remain edits, rather
        # than becoming new import names in the smaller synthetic inventory.
        required.update({'tests/device/self_tests/test_voice_roundtrip.py',
                         'provenance/artifact_identity.py'})
        for suite in registry['suites'].values():
            required.update(suite['closure']['required'])
            imports=suite.get('python_imports')
            if imports and inputs.python_import_digest(source,imports['roots'])==imports['reviewed']:
                required.update(entry['path'] for entry in inputs.selected_entries(
                    source,inputs._import_patterns(imports['roots'])))
        tree={path:dict(entry) for path,entry in source.items() if path in required}
        # This deliberately synthetic fixture exercises main's bounded parser.
        # Full source/shipping contexts above retain real Android13/19 profiles.
        self.assertEqual(inputs._AFFECTED_SHARED_PROFILE['sha'],'d63537504c20204de9d35d9be61da72a56df59c3')
        tree['tests/platform-profile.json']=dict(inputs._AFFECTED_SHARED_PROFILE)
        policy['lookup_digest']=inputs.affected_lookup_digest(tree)
        native=policy['suites']['device-control-plane-full']
        native['reviewed_reader_digest']=inputs.device_reader_digest(tree,native['native_independent_paths'])
        if policy['schema']==2:
            # Keep the versioned main aliases coherent in this smaller fixture;
            # shipping/all-seven source certificates above remain unmodified.
            policy['targets']['main']['lookup_digest']=policy['lookup_digest']
            policy['targets']['main']['reader_digest']=native['reviewed_reader_digest']
        sealed=(json.dumps(policy,indent=2)+'\n').encode()
        tree[inputs.AFFECTED_POLICY]=blob(sealed)
        return root,registry,sealed,tree

    def test_source_and_shipping_fixtures_bind_the_actual_deployed_boolean_variant(self):
        root=Path(__file__).resolve().parents[2]
        actual=inputs.full_tree(root,'HEAD')
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        for name,codeql in (
                ('protected-producer-original-default-v1','e9aaaed9693efc5ffb4701697ac2a4d51f5f5ba1'),
                ('protected-producer-original-default-boolean-v1','3b7a88765b7181a1bc7dd6f48b9b459e590055d3'),
                ('protected-producer-original-default-required-context-v1','7b0703d88d404f38c1b3dec92f77f03586c9144c'),
                ('protected-producer-optional-parent-source-v1','7b0703d88d404f38c1b3dec92f77f03586c9144c')):
            variant=deepcopy(actual)
            row=next(row['workflows'] for row in generations if row['name']==name)
            variant.update(deepcopy(row))
            variant['.github/workflows/codeql.yml']=dict(mode='100644',type='blob',sha=codeql)
            with self.subTest(name=name),patch.object(inputs,'full_tree',side_effect=lambda *_:deepcopy(variant)):
                _,_,_,before=self.source_context()
                self.assertNotIn('.github/workflows/pr-metadata-context.yml',before)
                self.assertEqual(before['.github/workflows/codeql.yml']['sha'],
                    '6d55d0fe4e9edc86204c66e1fa3967681793a2cd')
                _,_,_,installed=self.shipping_context()
                for path,entry in row.items():self.assertEqual(installed[path],entry)
                self.assertEqual(installed['.github/workflows/codeql.yml'],variant['.github/workflows/codeql.yml'])
            variant['.github/workflows/codeql.yml']['sha']='f'*40
            with self.subTest(name=name,invalid='CodeQL'),patch.object(inputs,'full_tree',side_effect=lambda *_:deepcopy(variant)), \
                    self.assertRaises(AssertionError):self.source_context()
            variant['.github/workflows/codeql.yml']['sha']=codeql
            variant['.github/workflows/browser-client.yml']['sha']='f'*40
            with self.subTest(name=name,invalid='mixed tuple'),patch.object(inputs,'full_tree',side_effect=lambda *_:deepcopy(variant)), \
                    self.assertRaises(AssertionError):self.source_context()

    def test_shipping_five_controller_case_omits_device_without_running_any_suite(self):
        root,registry,raw,base=self.shipping_context()
        _,_,_,source=self.source_context()
        self.assertEqual(inputs.affected_lookup_digest(source),inputs.affected_lookup_digest(base))
        self.assertNotIn('.github/workflows/pr-metadata-context.yml',source)
        self.assertIn('.github/workflows/pr-metadata-context.yml',base)
        candidate=deepcopy(base)
        for name in ('attested.py','postmerge.py','producer_workflow.py','sandbox.py','sandbox_host.py'):
            candidate['tools/test-evidence/'+name]=blob(('changed '+name).encode())
        target,trusted=self.target_context(root,raw,base)
        native=json.loads(raw)['suites']['device-control-plane-full']
        spec=importlib.util.spec_from_file_location('affected_host_policy',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        actual_base,actual_candidate=base,candidate
        original_base,original_candidate=deepcopy(base),deepcopy(candidate)
        raw_readers=[inputs.device_reader_digest(tree,native['native_independent_paths'])
                     for tree in (base,candidate)]
        raw_programs=[host.program_digest(tree,root) for tree in (base,candidate)]
        routing=host._ios_routing_views(candidate,base,trusted,root,target)
        # This historical full-subset fixture uses the original reader family,
        # just like the protected finite routing comparison. Actual raw maps
        # and reader identities remain independently preserved below.
        if routing is not None:
            base,candidate=routing['base'],routing['candidate']
        # The installed compiler-data family has a separate complete raw
        # reader certificate; retain the original target certificate as well.
        reader=inputs.device_reader_digest(base,native['native_independent_paths'])
        if inputs.installed_compiler_profile(base,target=target):
            self.assertEqual(target,'apple-ios')
            self.assertEqual(reader,inputs.INSTALLED_COMPILER_READER)
        else:
            self.assertEqual(reader,json.loads(raw)['targets'][target]['reader_digest'])
        plan=inputs.plan_affected(registry,raw,base,candidate,trusted,target=target)
        self.assertIn('device-control-plane-full',plan['omitted'])
        self.assertLess(len(plan['required']),60)
        self.assertIn('attested-runtime',plan['required'])
        self.assertIn('test-evidence',plan['required'])
        self.assertEqual(plan['required_setup'],['host-full'])
        selected=host.select(candidate,plan['paths'],True,trusted_tree=trusted,base_tree=base,target=target)
        self.assertEqual(selected['reason'],'protected-affected-dependencies')
        self.assertEqual(selected['suites'],plan['required'])
        self.assertTrue(selected['full_host'])
        self.assertEqual(selected['include_platform'],base['tests/platform-profile.json']!=inputs._AFFECTED_SHARED_PROFILE)
        self.assertFalse(selected['affected']['reusable'])
        self.assertEqual((actual_base,actual_candidate),(original_base,original_candidate))
        self.assertEqual([inputs.device_reader_digest(tree,native['native_independent_paths'])
                          for tree in (actual_base,actual_candidate)],raw_readers)
        self.assertEqual([host.program_digest(tree,root) for tree in (actual_base,actual_candidate)],raw_programs)
        if routing is not None:
            self.assertNotEqual(original_base,base)
            self.assertNotEqual(original_candidate,candidate)

    def test_preinstallation_source_cannot_inherit_the_prospective_native_omissions(self):
        root,registry,raw,base=self.source_context()
        self.assertNotIn('.github/workflows/pr-metadata-context.yml',base)
        candidate=deepcopy(base)
        candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed preinstallation controller')
        target,trusted=self.target_context(root,raw,base)
        plan=inputs.plan_affected(registry,raw,base,candidate,trusted,target=target)
        owners={'device-control-plane-full',*inputs._AFFECTED_PRODUCT_SUITES,*inputs._AFFECTED_SUBJECTS}
        self.assertEqual(len(owners),23)
        self.assertTrue(owners.issubset(plan['required']))
        self.assertFalse(owners.intersection(plan['omitted']))
        for name in owners:
            self.assertEqual(plan['reasons'][name],
                'fixed-subject-or-reader-not-reviewed' if name in inputs._AFFECTED_SUBJECTS
                else 'product-component-or-reader-not-reviewed')
        if target.startswith('android-'):
            original=inputs.full_tree(root,'HEAD')
            owner=json.loads((root/'.github/android-owner-transfer.json').read_bytes())
            for group in ('legacy_workflows','source_contracts'):
                for path in owner[group]:
                    self.assertEqual(base[path],original[path],'preinstallation fixture must retain every actual legacy owner')

    def test_actual_child_namespace_cannot_be_claimed_as_main_or_trusted_default(self):
        root,registry,raw,base=self.shipping_context()
        target,trusted=self.target_context(root,raw,base)
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed CI')
        # A real child keeps its extra import membership and native readers.
        # On main, a synthetic neighboring import proves the same refusal.
        foreign=deepcopy(base)
        if target=='main':foreign['ios/fixture_namespace.py']=blob(b'new child import')
        self.assertNotEqual(inputs.affected_lookup_digest(foreign),json.loads(raw)['targets']['main']['lookup_digest'])
        for old,new,default,claimed in ((foreign,candidate,trusted,'main'),
                                        (base,candidate,foreign,target),
                                        (base,candidate,trusted,'unknown-child')):
            with self.subTest(claimed=claimed),self.assertRaises(inputs.InputError):
                inputs.plan_affected(registry,raw,old,new,default,target=claimed)

    def test_exact_metadata_and_source_reader_bytes_are_independent_but_membership_and_modes_are_bound(self):
        _,registry,raw,base=self.bounded_context()
        paths={
            'tools/repository-checks/metadata_context.py',
            'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml',
            'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml',
            '.github/workflows/pr-metadata-context.yml',
            'tools/repository-checks/workflows/producers/legacy/repository-checks-protected-ci-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/parent-qualification-postmerge-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/protected-project-tests-ci37-v1.yml',
            '.github/workflows/documentation-push-owner.yml',
            '.github/workflows/documentation-checks.yml',
            '.github/workflows/workflow-security.yml',
            'tools/test-evidence/source_admission.py',
            'tools/test-evidence/source-admission-test.py',
            'tools/repository-checks/workflows/producers/legacy/parent-qualification-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/protected-project-tests-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/repository-checks-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/protected-project-tests-android-platform.yml',
            'tools/repository-checks/workflows/producers/parent-qualification-android-platform.yml',
        }
        self.assertTrue(paths <= set(json.loads(raw)['suites']['device-control-plane-full']['native_independent_paths']))
        candidate=deepcopy(base)
        for path in paths:
            self.assertEqual(base[path]['mode'],'100644')
            candidate[path]=blob(('changed reviewed bytes '+path).encode())
        plan=inputs.plan_affected(registry,raw,base,candidate,base)
        owners={'device-control-plane-full',*inputs._AFFECTED_PRODUCT_SUITES,*inputs._AFFECTED_SUBJECTS}
        self.assertTrue(owners <= set(plan['omitted']))
        for path in paths:
            for mode,kind in (('100755','blob'),('120000','blob'),('160000','commit')):
                changed=deepcopy(candidate);changed[path]={'mode':mode,'type':kind,'sha':'f'*40}
                with self.subTest(path=path,mode=mode):
                    try: result=inputs.plan_affected(registry,raw,base,changed,base)
                    except inputs.InputError: continue
                    self.assertTrue(owners <= set(result['required']))
        candidate['.github/workflows/pr-metadata-context-extra.yml']=blob(b'unreviewed neighbor')
        self.assertTrue(owners <= set(inputs.plan_affected(registry,raw,base,candidate,base)['required']))

    def test_unavailable_graph_retains_the_independently_selected_legacy_gate(self):
        root,registry,raw,base=self.shipping_context()
        spec=importlib.util.spec_from_file_location('affected_host_rollout',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'new')
        paths=['tools/test-evidence/sandbox_host.py']
        without=deepcopy(base);del without[inputs.AFFECTED_POLICY]
        for old,trusted,claimed in ((without,without,paths),(None,base,paths),(base,base,paths+['README.md'])):
            with self.subTest(old_missing=old is None,claimed=claimed):
                selected=host.select(candidate,claimed,True,trusted_tree=trusted,base_tree=old)
                legacy=host._select_legacy(candidate,claimed,True,trusted_tree=trusted,base_tree=old)
                self.assertEqual(selected,legacy)

    def test_changed_graph_cannot_expand_an_independently_reviewed_ci37_plan(self):
        root,registry,raw,base=self.shipping_context()
        spec=importlib.util.spec_from_file_location('affected_graph_preserves_legacy',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        candidate=deepcopy(base);candidate[inputs.AFFECTED_POLICY]=blob(b'changed policy bytes')
        options={'base_tree':base,'trusted_tree':base}
        with patch.object(host,'REVIEWED_PROGRAMS',host.program_digest(base)):
            legacy=host._select_legacy(candidate,[inputs.AFFECTED_POLICY],True,**options)
            self.assertEqual(len(legacy['suites']),37)
            self.assertFalse(legacy['full_host'])
            self.assertEqual(host.select(candidate,[inputs.AFFECTED_POLICY],True,**options),legacy)
        with self.assertRaises(inputs.InputError):
            inputs.plan_affected(registry,raw,base,candidate,base)

    def test_each_device_component_reader_data_discovery_native_and_variant_keeps_device(self):
        _,registry,raw,base=self.bounded_context()
        paths=('tests/device/catalog.json','tests/device/self_tests/test_voice_roundtrip.py',
            'tests/device/fixture/new-resource.json','provenance/artifact_identity.py',
            'tools/sbom/verify-artifact-identity.py','libraries/audio-client/src/AudioClient.cpp',
            'libraries/shared/src/new-header.h','interface/resources/qml/new-component.qml',
            'scripts/system/settings/qml/new-data.json','android/phone/new-native-input.cpp')
        for path in paths:
            candidate=deepcopy(base);candidate[path]=blob(b'changed component')
            with self.subTest(path=path):
                plan=inputs.plan_affected(registry,raw,base,candidate,base)
                self.assertIn('device-control-plane-full',plan['required'])
        historical=deepcopy(base);historical['libraries/audio-client/src/AudioClient.cpp']=blob(b'child reader')
        candidate=deepcopy(historical);candidate['tools/test-evidence/sandbox_host.py']=blob(b'unrelated')
        self.assertIn('device-control-plane-full',inputs.plan_affected(registry,raw,historical,candidate,base)['required'])

    def test_optional_ios_adapter_and_historical_native_root_headers_remain_bound(self):
        _,registry,raw,base=self.bounded_context()
        for path in ('ios/audio/IOSAudioAdapter.cpp','ios/audio/IOSAudioAdapter.h',
                     'ios/audio/new-private-header.h','cassert','QtCore/QCoreApplication'):
            for shape in ('candidate-only','historical-both'):
                old=deepcopy(base);candidate=deepcopy(base)
                if shape=='historical-both':old[path]=blob(b'historical native lookup')
                candidate[path]=old[path] if shape=='historical-both' else blob(b'changed native lookup')
                candidate['tools/test-evidence/sandbox_host.py']=blob(b'unrelated admitted CI')
                with self.subTest(path=path,shape=shape):
                    plan=inputs.plan_affected(registry,raw,old,candidate,base)
                    self.assertIn('device-control-plane-full',plan['required'])

    def test_native_independence_is_closed_bounded_and_cannot_exempt_unowned_headers(self):
        root,registry,raw,base=self.bounded_context()
        for paths in ([],['*'],['../cassert'],[inputs.AFFECTED_POLICY]*2,[f'leaf-{n}' for n in range(1001)]):
            value=json.loads(raw)
            value['suites']['device-control-plane-full']['native_independent_paths']=paths
            with self.subTest(paths=paths[:2]),self.assertRaises(inputs.InputError):
                inputs._validate_dependencies(value,registry)
        value=json.loads(raw)
        value['suites']['device-control-plane-full']['native_independent_paths'].append('cassert')
        forged=json.dumps(value).encode()
        for tree in (base,):tree[inputs.AFFECTED_POLICY]=blob(forged)
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed')
        spec=importlib.util.spec_from_file_location('affected_native_policy_guard',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        with patch.object(inputs,'load_dependencies',return_value=forged):
            selected=host.select(candidate,['tools/test-evidence/sandbox_host.py'],True,base_tree=base,trusted_tree=base)
        legacy=host._select_legacy(candidate,['tools/test-evidence/sandbox_host.py'],True,base_tree=base,trusted_tree=base)
        self.assertEqual(selected,legacy)

    def test_reviewed_product_owners_share_only_the_fixed_complete_lookup_proof(self):
        _,registry,raw,base=self.bounded_context()
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed CI')
        plan=inputs.plan_affected(registry,raw,base,candidate,base)
        self.assertTrue(inputs._AFFECTED_PRODUCT_SUITES.issubset(plan['omitted']))
        self.assertIn('host-selection',plan['required'])
        for name in sorted(inputs._AFFECTED_PRODUCT_SUITES):
            subject=registry['suites'][name]['closure']['required'][0]
            changed=deepcopy(candidate);changed[subject]=blob(b'changed reviewed owner')
            with self.subTest(owner=name,subject=subject):
                if subject in inputs.AFFECTED_AUTHORITY:
                    with self.assertRaises(inputs.InputError):
                        inputs.plan_affected(registry,raw,base,changed,base)
                else:
                    self.assertIn(name,inputs.plan_affected(registry,raw,base,changed,base)['required'])
        value=json.loads(raw)
        for shape in ('unknown-owner','candidate-scope','missing-fixed-inventory','extra-inventory'):
            changed=deepcopy(value);changed_registry=deepcopy(registry)
            if shape=='unknown-owner':changed['suites']['producer-api']['kind']='reviewed-product-inventory'
            elif shape=='candidate-scope':
                changed_registry['suites']['device-jenkins']['scope']='candidate'
                changed['registry_digest']=inputs._suite_definition_digest(changed_registry)
                changed['suites']['device-jenkins']['definition_digest']=inputs._suite_definition_digest(changed_registry['suites']['device-jenkins'])
            elif shape=='missing-fixed-inventory':changed['suites']['device-control-plane-full']={
                'kind':'repository','setup':['host-full'],'definition_digest':changed['suites']['device-control-plane-full']['definition_digest']}
            elif shape=='extra-inventory':changed['suites']['device-jenkins']['native_independent_paths']=['ignored']
            with self.subTest(shape=shape),self.assertRaises(inputs.InputError):
                inputs._validate_dependencies(changed,changed_registry)

    def test_javascript_and_performance_component_data_cannot_use_ci_byte_exemptions(self):
        _,_,raw,base=self.bounded_context()
        paths=json.loads(raw)['suites']['device-control-plane-full']['native_independent_paths']
        for path in ('tests/javascript/README.md','tests/performance/README.md',
                     'tests/safe-landing/README.md','tests/mocha/README.md','server-console/README.md',
                     'unpublishedScripts/README.md','tools/jsdoc/README.md'):
            old=deepcopy(base);old[path]=blob(b'old fixture contract')
            new=deepcopy(old);new[path]=blob(b'changed fixture contract')
            with self.subTest(path=path):
                self.assertNotEqual(inputs.device_reader_digest(old,[*paths,path]),
                                    inputs.device_reader_digest(new,[*paths,path]))

    def test_fixed_ci_subjects_bind_all_three_trees_without_coupling_product_owners(self):
        _,registry,raw,base=self.bounded_context()
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed CI')
        plan=inputs.plan_affected(registry,raw,base,candidate,base)
        self.assertTrue(set(inputs._AFFECTED_SUBJECTS).issubset(plan['omitted']))
        self.assertIn('documentation-contracts',plan['required'])
        self.assertEqual(plan['reasons']['documentation-contracts'],'unreviewed-import-or-missing-required-input')
        self.assertIn('native-owner-lifecycle',plan['required'])
        # Apple retains two additional audio Python readers and a changed mute
        # caller. Their genuine import variant must keep this extra owner.
        if 'recorded-voice-qml' in plan['required']:
            self.assertEqual(plan['reasons']['recorded-voice-qml'],'unreviewed-import-or-missing-required-input')
            self.assertEqual(len(plan['required']),34)
        else:
            self.assertIn('recorded-voice-qml',plan['omitted'])
            self.assertEqual(plan['reasons']['recorded-voice-qml'],'unchanged-reviewed-dependencies')
            self.assertEqual(len(plan['required']),33)
        for name,subjects in inputs._AFFECTED_SUBJECTS.items():
            for subject in subjects:
                for shape in ('changed','removed','historical','executable'):
                    old=deepcopy(base);new=deepcopy(candidate)
                    if shape=='removed':new.pop(subject)
                    elif shape=='executable':new[subject]=dict(new[subject],
                        mode='100644' if new[subject]['mode']=='100755' else '100755')
                    else:
                        new[subject]=blob(b'changed exact subject')
                        if shape=='historical':old[subject]=deepcopy(new[subject])
                    with self.subTest(owner=name,subject=subject,shape=shape):
                        lookup_change = subject=='tools/test-evidence/producer.py' and shape in {'removed','executable'}
                        if subject in inputs.AFFECTED_AUTHORITY or lookup_change:
                            with self.assertRaises(inputs.InputError):
                                inputs.plan_affected(registry,raw,old,new,base)
                        else:
                            selected=inputs.plan_affected(registry,raw,old,new,base)
                            self.assertIn(name,selected['required'])
        # This CI unit-test leaf is independent of the actual product tests.
        changed=deepcopy(candidate);changed['tests/unittest-runner-test.py']=blob(b'changed CI regression')
        selected=inputs.plan_affected(registry,raw,base,changed,base)
        self.assertIn('python-test-runner',selected['required'])
        self.assertIn('device-control-plane-full',selected['omitted'])
        self.assertTrue(inputs._AFFECTED_PRODUCT_SUITES.issubset(selected['omitted']))

    def test_fixed_ci_subject_policy_cannot_supply_unknown_owners_or_subject_maps(self):
        _,registry,raw,base=self.bounded_context()
        value=json.loads(raw)
        for shape in ('unknown-owner','candidate-scope','alternate-subjects','extra-map','missing-native'):
            changed=deepcopy(value);definitions=deepcopy(registry)
            if shape=='unknown-owner':changed['suites']['producer-api']['kind']='reviewed-subject-inventory'
            elif shape in {'candidate-scope','alternate-subjects'}:
                if shape=='candidate-scope':definitions['suites']['python-test-runner']['scope']='candidate'
                else:definitions['suites']['python-test-runner']['closure']['required']=['tests/unittest-runner-test.py']
                changed['registry_digest']=inputs._suite_definition_digest(definitions)
                changed['suites']['python-test-runner']['definition_digest']=inputs._suite_definition_digest(definitions['suites']['python-test-runner'])
            elif shape=='extra-map':changed['suites']['python-test-runner']['subjects']=['arbitrary.py']
            else:
                entry=changed['suites']['device-control-plane-full']
                changed['suites']['device-control-plane-full']={k:entry[k] for k in ('kind','definition_digest','setup')}
                changed['suites']['device-control-plane-full']['kind']='repository'
            with self.subTest(shape=shape),self.assertRaises(inputs.InputError):
                inputs._validate_dependencies(changed,definitions)
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed CI')
        candidate['tests/unittest-extra-runner-test.py']=blob(b'unknown neighbor')
        plan=inputs.plan_affected(registry,raw,base,candidate,base)
        self.assertIn('python-test-runner',plan['required'])

    def test_unknown_root_import_shadow_cannot_inherit_any_omission(self):
        _,registry,raw,base=self.bounded_context()
        for path in ('json.py','sitecustomize.py','tools/repository-checks/json.py','tests/device/new_module.py','namespace/__init__.py'):
            candidate=deepcopy(base);candidate[path]=blob(b'new shadow')
            with self.subTest(path=path),self.assertRaises(inputs.InputError):
                inputs.plan_affected(registry,raw,base,candidate,base)

    def test_existing_ci37_metadata_codeql_cleanup_and_lock_plans_never_expand(self):
        import ci_profile
        root,registry,raw,base=self.shipping_context()
        spec=importlib.util.spec_from_file_location('affected_preserve_proofs',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        ci37=[n for n,s in registry['suites'].items() if s['layer']=='quick' and n not in host.PRODUCT_QUICK_SUITES]
        paths=('.github/workflows/codeql.yml','.github/branch-cleanup.json',
               '.github/android-orchestration.json','tests/PROJECT_TESTING.md',*host.PACKAGE_LOCKS)
        # Preserve the exact legacy37 contract under its actual old namespace.
        # The new seven-target namespace deliberately permits smaller proved
        # Qt-free selections; SevenTargetProfileTests covers those separately.
        historical_policy={**ci_profile.load_policy(root),
            'generation_kind':ci_profile.CONTROLLER_KIND,'epoch':ci_profile.CONTROLLER_EPOCH}
        with patch.object(host,'REVIEWED_PROGRAMS',host.program_digest(base,root)), \
             patch.object(ci_profile,'load_policy',return_value=historical_policy):
            for path in paths:
                candidate=deepcopy(base);candidate[path]=blob(b'changed ordinary shipping leaf')
                package_paths=(path,) if path in host.PACKAGE_LOCKS else ()
                options={'base_tree':base,'trusted_tree':base,'package_paths':package_paths}
                with self.subTest(path=path):
                    legacy=host._select_legacy(candidate,[path],True,**options)
                    self.assertEqual(legacy['suites'],ci37)
                    self.assertEqual(len(legacy['suites']),37)
                    self.assertEqual(host.select(candidate,[path],True,**options),legacy)
            for unknown,regular,paths in ((False,True,[]),(True,True,['README.md']),(False,False,['README.md'])):
                options={'base_tree':base,'trusted_tree':base,'unknown':unknown}
                self.assertEqual(host.select(base,paths,regular,**options),host._select_legacy(base,paths,regular,**options))

    def test_fewer_groups_cannot_replace_an_existing_narrower_preparation_route(self):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location('affected_setup_dominance',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        for legacy_full,affected_full in ((False,True),(False,False),(True,True),(True,False)):
            legacy={'suites':['owner-a','owner-b'],'reason':'reviewed-ci-only-inputs',
                    'full_host':legacy_full,'include_platform':False}
            affected={'suites':['owner-a'],'reason':'protected-affected-dependencies',
                      'full_host':affected_full,'include_platform':False}
            with self.subTest(legacy_full=legacy_full,affected_full=affected_full), \
                    patch.object(host,'_select_legacy',return_value=legacy), \
                    patch.object(host,'affected_selection',return_value=affected):
                selected=host.select({},['reviewed-ci-leaf'],True)
                self.assertIs(selected,legacy if affected_full and not legacy_full else affected)

    def test_nonempty_or_changed_platform_cannot_enter_partial_route_even_on_both_sides(self):
        _,registry,raw,base=self.bounded_context()
        changed=deepcopy(base);changed['tests/platform-profile.json']=blob(b'{"schema":1,"platform":"android","suites":[{}]}')
        candidate=deepcopy(changed);candidate['tools/test-evidence/sandbox_host.py']=blob(b'unrelated')
        with self.assertRaises(inputs.InputError):inputs.plan_affected(registry,raw,changed,candidate,changed)

    def test_protected_producer_declines_dynamic_subset_before_any_runtime_preparation(self):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location('affected_producer',root/'tools/test-evidence/producer_workflow.py')
        producer=importlib.util.module_from_spec(spec);spec.loader.exec_module(producer)
        registry={'schema':1,'control_inputs':['fixed'],'suites':{'finite':definition()}}
        tree={'fixed':blob()}
        policy=type('Policy',(),{'select':staticmethod(lambda *a,**k:{'reason':'protected-affected-dependencies','suites':['finite'],'full_host':True})})
        with patch.object(producer.shared,'prepared_tools') as tools,patch.object(producer.runtime_ci,'validate_environment') as admit:
            with self.assertRaises(producer.PreExecutionUnavailable):
                producer.selection_profile(policy,registry,tree,tree,tree)
            tools.assert_not_called();admit.assert_not_called()


class DependencyPolicyRoutingTests(unittest.TestCase):
    def module(self, name, relative):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location(name,root/relative)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module
        spec.loader.exec_module(module)
        return module

    def test_only_exact_ordinary_new_leaves_are_ios_and_android_independent(self):
        ios=self.module('affected_ios_inputs','tools/ios-build-qualification/inputs.py')
        host=self.module('affected_ios_host','tools/ios-build-qualification/host.py')
        android=self.module('affected_android_inputs','tools/repository-checks/android-build-inputs.py')
        paths=(inputs.AFFECTED_POLICY,'tools/test-evidence/affected-test.py',
               'tools/test-evidence/AFFECTED_SELECTION.md')
        for path in paths:
            with self.subTest(path=path):
                entry=ios.Entry(path,'100644','blob','a'*40)
                self.assertEqual(ios._kind(entry),'independent-host')
                self.assertEqual(android._kind(entry),'independent-host')
                self.assertIn(path,host.CI_HOST_INDEPENDENT_PATHS)
                old=SimpleNamespace(entries=(entry,),revision="a"*40,tree="b"*40)
                new=SimpleNamespace(entries=(ios.Entry(path,'100644','blob','b'*40),),revision='c'*40,tree='d'*40)
                with patch.object(host,'REVIEWED_CI_HOST_BOUNDARY',host.ci_host_boundary(old)):
                    self.assertIsNotNone(host.ci_host_omission(old,new))
                    for mode,kind in (('100755','blob'),('120000','blob'),('160000','commit')):
                        altered=ios.Entry(path,mode,kind,'b'*40)
                        self.assertEqual(ios._kind(altered),'application-input')
                        self.assertEqual(android._kind(altered),'application-input')
                        self.assertIsNone(host.ci_host_omission(old,SimpleNamespace(entries=(altered,))))
        for path in ('.github/test-suite-dependencies-extra.json','tools/test-evidence/affected-extra-test.py',
                     'tools/test-evidence/AFFECTED_SELECTION-extra.md'):
            entry=ios.Entry(path,'100644','blob','a'*40)
            self.assertEqual(ios._kind(entry),'application-input')
            self.assertEqual(android._kind(entry),'application-input')
            self.assertNotIn(path,host.CI_HOST_INDEPENDENT_PATHS)

    def test_exact_metadata_and_security_guide_ios_exclusions_keep_neighbors_and_modes_conservative(self):
        ios=self.module('metadata_ios_inputs','tools/ios-build-qualification/inputs.py')
        host=self.module('metadata_ios_host','tools/ios-build-qualification/host.py')
        paths={'.github/dependency-security.md', '.github/workflows/pr-metadata-context.yml',
            '.github/workflows/documentation-checks.yml', '.github/workflows/workflow-security.yml',
            'tools/repository-checks/metadata_context.py',
            'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml',
            'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml',
            'tools/repository-checks/workflows/producers/legacy/repository-checks-protected-ci-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/parent-qualification-postmerge-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/protected-project-tests-ci37-v1.yml',
            '.github/workflows/documentation-push-owner.yml',
            'tools/test-evidence/source_admission.py',
            'tools/test-evidence/source-admission-test.py',
            'tools/repository-checks/workflows/producers/legacy/parent-qualification-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/protected-project-tests-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/repository-checks-metadata-v1.yml',}
        for path in paths:
            with self.subTest(path=path):
                entry=ios.Entry(path,'100644','blob','a'*40)
                self.assertEqual(ios._kind(entry),'independent-host')
                self.assertIn(path,host.CI_HOST_INDEPENDENT_PATHS)
                old=SimpleNamespace(entries=(entry,),revision='a'*40,tree='b'*40)
                with patch.object(host,'REVIEWED_CI_HOST_BOUNDARY',host.ci_host_boundary(old)):
                    self.assertIsNotNone(host.ci_host_omission(old,SimpleNamespace(
                        entries=(ios.Entry(path,'100644','blob','b'*40),),revision='c'*40,tree='d'*40)))
                    for mode,kind in (('100755','blob'),('120000','blob'),('160000','commit')):
                        altered=ios.Entry(path,mode,kind,'b'*40)
                        self.assertEqual(ios._kind(altered),'application-input')
                        self.assertIsNone(host.ci_host_omission(old,SimpleNamespace(entries=(altered,))))
                neighbor=path+'.extra'
                self.assertEqual(ios._kind(ios.Entry(neighbor,'100644','blob','a'*40)),'application-input')
                self.assertNotIn(neighbor,host.CI_HOST_INDEPENDENT_PATHS)

    def test_complete_source_reader_complements_exclude_only_exact_new_leaves(self):
        ios=self.module('affected_ios_reviewed','tools/ios-build-qualification/inputs.py')
        host=self.module('affected_ios_host_reviewed','tools/ios-build-qualification/host.py')
        root=Path(__file__).resolve().parents[2]
        revision=ios._git(root,'rev-parse','--verify','HEAD^{commit}').decode().strip()
        snapshot=ios.read_snapshot(root,revision)
        doctor='tools/repository-health/check.py'
        paths={inputs.AFFECTED_POLICY,'tools/test-evidence/affected-test.py',
               'tools/test-evidence/AFFECTED_SELECTION.md',doctor}
        self.assertIn(doctor,ios.INDEPENDENT_HOST_PATHS)
        self.assertIn(doctor,ios.INDEPENDENT_EXECUTABLE_HOST_PATHS)
        self.assertIn(doctor,host.CI_HOST_INDEPENDENT_PATHS)
        self.assertIn(doctor,host.CI_HOST_EXECUTABLE_PATHS)
        added={entry.path:entry for entry in snapshot.entries if entry.path in paths}
        self.assertEqual(set(added),paths)
        self.assertTrue(all(entry.mode==('100755' if entry.path==doctor else '100644')
            and entry.object_type=='blob' for entry in added.values()))
        # Exercise child routing families even when this test runs on main,
        # whose parent-owned bootstrap does not enter the child comparison.
        variants=[snapshot]
        routing_paths=tuple(ios.ROUTING_DATA)
        for stage_index,stage in enumerate(((0,0),(1,0),(1,1))):
            routing={entry.path:entry for entry in snapshot.entries}
            routing.update({path:ios.Entry(path,'100644','blob',ios.ROUTING_DATA[path][index])
                for path,index in zip(routing_paths,stage)})
            routed=ios.Snapshot(snapshot.revision,snapshot.tree,tuple(
                sorted(routing.values(),key=lambda entry:entry.path)))
            self.assertEqual(ios.routing_data_stage(routed),stage_index)
            variants.append(routed)
        for variant in variants:
            with self.subTest(routing=ios.routing_data_stage(variant)):
                before=ios.Snapshot(variant.revision,variant.tree,tuple(
                    entry for entry in variant.entries if entry.path not in paths))
                self.assertEqual(len(before.entries)+len(paths),len(variant.entries))
                app=ios._boundary(before)
                own_host=host.ci_host_boundary(before)
                self.assertIsNotNone(app)
                self.assertIsNotNone(own_host)
                self.assertEqual(ios._boundary(variant),app)
                self.assertEqual(host.ci_host_boundary(variant),own_host)
                changed=ios.Snapshot(variant.revision,variant.tree,tuple(
                    ios.Entry(entry.path,entry.mode,entry.object_type,'f'*40)
                    if entry.path in paths else entry for entry in variant.entries))
                self.assertEqual(ios._boundary(changed),app)
                self.assertEqual(host.ci_host_boundary(changed),own_host)
        # The historical anchor is independently reconstructed by the complete
        # immutable reader audit; a shallow candidate need not fetch its commit.
        self.assertEqual(ios.REVIEWED_REVISION,'2fc894a0605103843b36653f250f854714a963ee')
        self.assertEqual(ios.REVIEWED_BOUNDARY,
            'sha256:8527f25d58c8ebf8eebab8a9e43517899b7afce2e511026d2873a69ab82f1794')
        self.assertEqual(host.REVIEWED_CI_HOST_BOUNDARY,
            '90da341e226f56b8dfb8b925af7c0273ecc41772ca424e3426b04c80acdb9a7b')

    def test_new_policy_uses_existing_native_browser_and_package_host_routes(self):
        native=self.module('affected_native_route','tools/native-tests/check.py')
        checks=self.module('affected_repository_route','tools/repository-checks/check.py')
        packages=self.module('affected_package_route','tools/repository-checks/package_checks.py')
        paths=[inputs.AFFECTED_POLICY,'tools/test-evidence/affected-test.py',
               'tools/test-evidence/AFFECTED_SELECTION.md']
        self.assertEqual(native.plan(paths)['mode'],'skip')
        direct=checks.direct_browser_plan(paths)
        self.assertFalse(direct['browser']);self.assertFalse(direct['native'])
        self.assertEqual(packages.select(paths)['package_set'],[])
        self.assertEqual(packages.select(paths)['tool_projects'],[])
        self.assertEqual(native.plan(paths,regular=False)['mode'],'full')
        self.assertTrue(checks.direct_browser_plan(paths,regular=False)['native'])

    def test_new_policy_is_python_only_only_for_existing_ordinary_pinned_leaves(self):
        codeql=self.module('affected_codeql_route','tools/repository-checks/codeql.py')
        before={p:{'mode':'100644','type':'blob','sha':sha} for p,sha in codeql._REVIEWED_CONTROLS.items()}
        before['.github/workflows/codeql.yml']['sha']=codeql._PINNED_RESULTS_WORKFLOW
        before[inputs.AFFECTED_POLICY]=blob(b'old')
        after=deepcopy(before);after[inputs.AFFECTED_POLICY]=blob(b'new')
        self.assertEqual(codeql.select_languages(before,after)['languages'],['python'])
        for shape in ('new','removed','executable','alias','neighbor','legacy','mixed','config'):
            old=deepcopy(before);new=deepcopy(after)
            if shape=='new':del old[inputs.AFFECTED_POLICY]
            elif shape=='removed':del new[inputs.AFFECTED_POLICY]
            elif shape=='executable':new[inputs.AFFECTED_POLICY]['mode']='100755'
            elif shape=='alias':new[inputs.AFFECTED_POLICY]['mode']='120000'
            elif shape=='neighbor':new['.github/test-suite-dependencies-extra.json']=blob(b'new')
            elif shape=='legacy':old['.github/workflows/codeql.yml']['sha']=codeql._RETARGET_RESULTS_WORKFLOW
            elif shape=='mixed':new['actual.js']=blob(b'new')
            elif shape=='config':new['.github/codeql/codeql-config.yml']=blob(b'new')
            with self.subTest(shape=shape):
                self.assertIn('javascript-typescript',codeql.select_languages(old,new)['languages'])


class NonreusableRouteTests(unittest.TestCase):
    def execute(self, status=0, product=(), include_platform=False):
        import execution
        registry={'schema':1,'control_inputs':['fixed'],'suites':{
            'selected':definition(),'omitted':definition()}}
        observations=[]
        def run(args,suites,cancelled,result_callback):
            observations.extend(suite.name for suite in suites)
            for suite in suites:
                result_callback({'name':suite.name,'status':'passed' if status==0 else 'failed'})
            return status
        controller=SimpleNamespace(ROOT=None,run_command=lambda *a:None,
            Suite=lambda name,layer,command:SimpleNamespace(name=name,layer=layer,command=command),run_suites=run)
        with (tempfile.TemporaryDirectory() as temporary,
              patch.object(execution,'checkout_identity',return_value=('a'*40,'b'*40)),
              patch.object(execution.inputs,'load_registry',return_value=registry),
              patch.object(execution.inputs,'full_tree',return_value={'fixed':blob()}),
              patch.object(execution,'platform_suites',return_value=list(product)),
              patch.object(execution,'capture_execution_environment') as capture,
              patch.object(execution,'_runner',return_value=controller),
              patch.object(execution,'_write_receipt') as write):
            value=execution.execute(Path(temporary),['selected'],include_platform=include_platform,
                receipt_path=Path('/fixed-receipt'),_impact_selection=True)
        capture.assert_not_called()
        self.assertEqual(observations,['selected'])
        self.assertEqual(write.call_count,1)
        return value

    def test_empty_platform_context_runs_exact_subset_without_runtime_or_reuse_claim(self):
        code,receipt=self.execute()
        self.assertEqual(code,0)
        self.assertEqual(receipt['requested_suites'],['selected'])
        self.assertFalse(receipt['reusable']);self.assertIsNone(receipt['environment'])
        self.assertEqual(receipt['results'],{'selected':{'status':'passed','fingerprint':None}})
        self.assertEqual(receipt['platform_results'],{})

    def test_started_failure_stays_failed_once_without_runtime_or_full_retry(self):
        code,receipt=self.execute(status=17)
        self.assertEqual(code,17)
        self.assertEqual(receipt['conclusion'],'failure')
        self.assertFalse(receipt['reusable'])

    def test_impact_execution_rejects_platform_inventory_flags(self):
        import execution
        with self.assertRaises(execution.ExecutionError):
            self.execute(product=[('actual-platform',['python','actual.py'])],include_platform=True)

    def test_legacy_owner_forwards_dynamic_selection_without_capture_and_never_retries_failure(self):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location('affected_legacy_route',root/'tools/repository-checks/android_handoff.py')
        owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
        selected={'reason':'protected-affected-dependencies','suites':['selected'],
                  'include_platform':False,'full_host':True}
        proof={'reusable':False,'environment':None,'conclusion':'failure',
               'results':{'selected':{'status':'failed','fingerprint':None}}}
        shared=SimpleNamespace(execute=Mock(return_value=(17,proof)),digest=lambda value:'fixed',
            _write_receipt=Mock(),inputs=SimpleNamespace(load_registry=lambda path:{'suites':{'selected':{},'omitted':{}}}))
        controller=SimpleNamespace(android=lambda:SimpleNamespace(_shared=lambda:(shared,None)))
        with (tempfile.TemporaryDirectory() as temporary,
              patch.object(owner,'gate',return_value=controller),
              patch.object(owner,'host_selection',return_value=object()),
              patch.object(owner,'selected_host',return_value=selected),
              patch.object(owner,'platform_owner',return_value={} )):
            base=Path(temporary);candidate=base/'candidate';candidate.mkdir()
            status,observed=owner.project(candidate,{},'a'*40,'pull_request',
                junit=base/'results.xml',receipt_path=base/'receipt.json')
        self.assertEqual(status,17);self.assertEqual(observed['conclusion'],'failure')
        shared.execute.assert_called_once()
        self.assertIs(shared.execute.call_args.kwargs['_impact_selection'],True)
        self.assertEqual(shared.execute.call_args.kwargs['suite_names'],['selected'])
        self.assertFalse(observed['reusable']);self.assertIsNone(observed['environment'])


class InstalledCompilerReaderTests(unittest.TestCase):
    PROFILE_MODES = {
        '.github/workflows/ios-integrated.yml': '100644',
        'docs/ios/SIGNING_AND_DEVICE_TESTS.md': '100644',
        'ios/ci/qt-checkpoint-artifact.py': '100755',
        'ios/tests/ios-full-client-sccache-contract-test.py': '100644',
        'ios/tests/qt-checkpoint-artifact-test.py': '100755',
    }

    def private_git_context(self):
        """Real commits and immutable reads, with an explicitly synthetic policy.

        Fixture hashes never claim to be the seven-target shipping certificates.
        The exact production five/R constants are checked separately by host tests.
        """
        temporary=tempfile.TemporaryDirectory(prefix='overte-installed-compiler-readers-')
        self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        source=Path(__file__).resolve().parents[2]
        actual=inputs.load_registry(source/'.github/test-suites.json')
        names=('device-control-plane-full','shared-script-behavior','test-evidence')
        registry={'schema':1,'control_inputs':actual['control_inputs'],
            'suites':{name:deepcopy(actual['suites'][name]) for name in names}}
        def write(path,data,mode=0o644):
            leaf=root/path;leaf.parent.mkdir(parents=True,exist_ok=True)
            leaf.write_bytes(data);leaf.chmod(mode)
        def git(*args):
            return inputs.subprocess.check_output(['git','-c','core.hooksPath=/dev/null',
                '-c','commit.gpgsign=false','-c','user.name=Compiler reader fixture',
                '-c','user.email=fixture@example.invalid',*args],cwd=root).decode().strip()
        def snapshot():
            git('add','--','.');git('commit','-qm','Record private immutable reader fixture')
            return inputs.full_tree(root,git('rev-parse','HEAD'))
        git('init','-q','--initial-branch=main')
        required=set(inputs.AFFECTED_AUTHORITY)
        for suite in registry['suites'].values():required.update(suite['closure']['required'])
        for path in sorted(required):write(path,('fixed authority or required fixture '+path+'\n').encode(),
            0o755 if path=='tests/run-project-tests.py' else 0o644)
        write('.github/test-suites.json',(json.dumps(registry,indent=2)+'\n').encode())
        profile_raw=(json.dumps({'schema':1,'platform':'shared','suites':[]},indent=2)+'\n').encode()
        self.assertEqual(blob(profile_raw),inputs._AFFECTED_SHARED_PROFILE)
        write('tests/platform-profile.json',profile_raw)
        ci='tools/branch-cleanup/cleanup.py';write(ci,b'old independent CI\n')
        for path,mode in self.PROFILE_MODES.items():
            write(path,('old '+path+'\n').encode(),int(mode,8)&0o777)
        provisional=snapshot()
        independent=[inputs.AFFECTED_POLICY,ci]
        reader=inputs.device_reader_digest(provisional,independent)
        lookup=inputs.affected_lookup_digest(provisional)
        policy={'schema':2,'registry_digest':inputs._suite_definition_digest(registry),
            'lookup_digest':lookup,'suites':{},'targets':{
                target:{'profile':{'mode':'100644','type':'blob','sha':sha},
                        'lookup_digest':lookup,'reader_digest':reader}
                for target,sha in inputs._AFFECTED_TARGET_PROFILES.items()}}
        for name,suite in registry['suites'].items():
            policy['suites'][name]={'kind':'device-control-plane' if name==names[0]
                else 'reviewed-product-inventory' if name==names[1] else 'repository',
                'definition_digest':inputs._suite_definition_digest(suite),'setup':['host-full']}
        policy['suites'][names[0]].update(reviewed_reader_digest=reader,native_independent_paths=independent)
        raw=(json.dumps(policy,indent=2)+'\n').encode();write(inputs.AFFECTED_POLICY,raw)
        old=snapshot()
        self.assertEqual(inputs.device_reader_digest(old,independent),reader)
        write(ci,b'new independent CI\n');old_ci=snapshot()
        write(ci,b'old independent CI\n')
        for path,mode in self.PROFILE_MODES.items():
            write(path,('installed '+path+'\n').encode(),int(mode,8)&0o777)
        new=snapshot()
        write(ci,b'new independent CI\n');new_ci=snapshot()
        installed={path:new[path].copy() for path in self.PROFILE_MODES}
        new_reader=inputs.device_reader_digest(new,independent)
        self.assertNotEqual(reader,new_reader)
        self.assertEqual(inputs.affected_lookup_digest(new),lookup)
        return registry,raw,old,old_ci,new,new_ci,installed,new_reader

    def test_equal_old_and_equal_installed_readers_omit_but_install_and_revert_keep_product_owners(self):
        registry,raw,old,old_ci,new,new_ci,profile,reader=self.private_git_context()
        with (patch.object(inputs,'INSTALLED_COMPILER_PROFILE',profile,create=True),
              patch.object(inputs,'INSTALLED_COMPILER_READER',reader,create=True)):
            for base,candidate in ((old,old_ci),(new,new_ci)):
                with self.subTest(family='installed' if base is new else 'original'):
                    plan=inputs.plan_affected(registry,raw,base,candidate,old,target='apple-ios')
                    self.assertIn('device-control-plane-full',plan['omitted'])
                    self.assertIn('shared-script-behavior',plan['omitted'])
                    self.assertIn('test-evidence',plan['required']);self.assertFalse(plan['reusable'])
            for base,candidate in ((old,new_ci),(new,old_ci)):
                with self.subTest(direction='install' if base is old else 'revert'):
                    plan=inputs.plan_affected(registry,raw,base,candidate,old,target='apple-ios')
                    self.assertIn('device-control-plane-full',plan['required'])
                    self.assertIn('shared-script-behavior',plan['required'])

    def test_installed_reader_rejects_wrong_target_stale_hash_profile_and_neighbor_bytes(self):
        registry,raw,old,old_ci,new,new_ci,profile,reader=self.private_git_context()
        with (patch.object(inputs,'INSTALLED_COMPILER_PROFILE',profile,create=True),
              patch.object(inputs,'INSTALLED_COMPILER_READER',reader,create=True)):
            plan=inputs.plan_affected(registry,raw,new,new_ci,old,target='apple-main')
            self.assertIn('device-control-plane-full',plan['required'])
            with patch.object(inputs,'INSTALLED_COMPILER_READER','sha256:'+'f'*64):
                self.assertIn('device-control-plane-full',
                    inputs.plan_affected(registry,raw,new,new_ci,old,target='apple-ios')['required'])
            for change in ('guide','helper','mode','missing','neighbor'):
                base,candidate=deepcopy(new),deepcopy(new_ci)
                for tree in (base,candidate):
                    helper='ios/ci/qt-checkpoint-artifact.py'
                    if change=='missing':del tree[helper]
                    elif change=='mode':tree[helper]['mode']='100644'
                    elif change=='neighbor':tree['ios/ci/unreviewed.hpp']=blob(b'new neighboring input')
                    else:tree['docs/ios/SIGNING_AND_DEVICE_TESTS.md' if change=='guide' else helper]=blob(b'changed bytes')
                with self.subTest(change=change):
                    self.assertIn('device-control-plane-full',
                        inputs.plan_affected(registry,raw,base,candidate,old,target='apple-ios')['required'])
                    # Even falsely substituting this reader hash cannot bypass
                    # the independent exact-five profile check.
                    changed_reader=inputs.device_reader_digest(base,json.loads(raw)['suites'][
                        'device-control-plane-full']['native_independent_paths'])
                    if change!='neighbor':
                        with patch.object(inputs,'INSTALLED_COMPILER_READER',changed_reader):
                            self.assertIn('device-control-plane-full',inputs.plan_affected(
                                registry,raw,base,candidate,old,target='apple-ios')['required'])

    def test_installed_reader_keeps_lookup_authority_profile_and_nonordinary_failures_closed(self):
        registry,raw,old,old_ci,new,new_ci,profile,reader=self.private_git_context()
        with (patch.object(inputs,'INSTALLED_COMPILER_PROFILE',profile,create=True),
              patch.object(inputs,'INSTALLED_COMPILER_READER',reader,create=True)):
            for change in ('lookup','authority','graph','platform','symlink'):
                base,candidate=deepcopy(new),deepcopy(new_ci)
                for tree in (base,candidate):
                    if change=='lookup':tree['ios/ci/unreviewed_reader.py']=blob(b'new import candidate')
                    elif change=='authority':tree['tools/test-evidence/inputs.py']=blob(b'stale selector')
                    elif change=='graph':tree[inputs.AFFECTED_POLICY]=blob(b'foreign graph')
                    elif change=='platform':tree['tests/platform-profile.json']=blob(b'foreign target')
                    else:tree['ios/ci/qt-checkpoint-artifact.py']['mode']='120000'
                with self.subTest(change=change),self.assertRaises(inputs.InputError):
                    inputs.plan_affected(registry,raw,base,candidate,old,target='apple-ios')


if __name__=='__main__':unittest.main()
