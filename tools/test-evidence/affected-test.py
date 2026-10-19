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
# caaa51d47795411d30250cbd6b7c250ec82aaf02 / tree 7e3c124274ea161e861f25796b031451ac293a0f.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '3fd4fd687938034c5721168de4a003f8d8076a391d6f0a0085c8c303897bcc51'
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
    'c-qaK-Et#IlAZ7M7<0Xx%E*lT+ozDpbPtPP7P?4)1AyIKySDGH?<7EW)eMP<1ZpL%X}71VTN8oINDuep=N$jfzy1Ajd;0q7zqnmI'
    '?6>h@|Hm#J9!>|hJLYuw`)|kn?r;D8pMQJa$Mm;<|C?!=!P>w5+ux2~9e>-ljp2WK(@wzz{!?SdoKxpx=!YguCO2J<#_<2)^!-Ku'
    '1^#L8|Mp-1_P(rVq44$LW&gAd-wUgG-|^oyq+uSL=u()5aST2+&Di8_@Uh9`U|lnPzS@fm-`rz*_+x+gmY?>2JUk|TtvhY^yJKPT'
    '5ayh0<K5KfHpS6dGtXmk-VC9g8k>jEOwHJTzW5=%?2p^i{_y=Fd`;n7X~jO+vCTZ!(M&nUIi)n`-sZ-}nIAe&u4`@b_VX1_>3DiL'
    'zHU$HA*PqKi)k0OskE+d+98;J@chbd9;d-~O`fLCy52`WS>sz?xF2fPEv*%Y-p_5;G2y?_wa)cv<Ux0Knuq9y!B}s2ub;2=_9~CO'
    '+(X)(9{%y_p0;@#mbd!%@6S)4uRi-6hCGdJ=S}Ws+YWg)9Z%hlQ`-!awQkHD@v7Ai``=PHJ?OU|uP@8T(zUL4&W4cF*n4ApW1|_J'
    'nL}fS$UEnZ%{9yZ>!G^7bemHXhuF>0w7k`(X=Z-%5XWeo?>WeEYP|j67yARt5gEeMmZ$tBY`^@LcHg$U<CjOL_x$qx^Hq&;!TJzd'
    'Z>=4DYp2LZW5zzke&V<1KACZB+BK`b@XLAO*Vnaq?2>h9oI2lxvE|3*$$Ji#&+V9-acWWuVcoiWe|^>L^4J89k;(kNwwYbic4Oyl'
    'nA2p#m|bxF)UA5Phu7WJHG{FkFvRR;Z>N!;=jLu`=E?Xj`PACzn=$3QYE7NwP564)Kc~$x>|d_`>Z!L)!;^KKrXfrzq}lbI8ygN4'
    'v8xYpj+0sUtd||^+;ch-xYOp4+{<?Ncy$|*kCu-*^@Am9CSy})=9UjR_@Nn0Z!IB(t7`o=UY<8$zsuX}>+=n#Ve0x}n2cMl#i47P'
    'p4c|^F}B<jVPucp>h*Om$IYL=XMc5l&pB(XjeS3IN%Rd*qIYu>T5d>AWXDrzxS!qX^*MoDl~>nJA$ODO+ekFa-RQ#@j5l55xV3_7'
    '%@jL3G!?&H5#<l}{mU+$6zMjH{p%@h;?_Ox_Q%sUT#q*09Jr;EHGSxl<@L`~N{*|u>4%;p7=7zVS?1N-c#SVt7jCC<Fv+wraiffJ'
    '*3)MvT&6j;d<dDV&Zcp!Uif_QE~_tznU3Ho{du|`fO<Z5Qj@mpyQ%AvHr3B*^nK)OoKrBQG4oIkw@;3|@U(y4h6lpl@7p6cDj(n%'
    '_ZqjS&E>|^EqnEg?EB<wY@JW3%S6K%?L1pMDJGhs*UR9^j5qIQ`6~5sJh@kL$?H*S9J&zOILwy!L5AUpoAcDpIg{)(*_hOjY&ExU'
    '=9P5vdZdiOnJKixl$)O4?)uP<Tn&6Cq<j68dlzljCUf&1zNN!1J#Ch^baf|l>v<q?96}s@H)h+k*~fP1%{UKvNb@*ye%pNWPM+P4'
    'bUSXy@j1$e@0+jNqjHt2yJ~cC4cSh<Nr5mjrk=};Ta;YEbnLJhEl=t8UF|*p((i>}HUw2Jq4z{f>)UbU^t!HzU6{JW2_lXS`lq+='
    ';^k6#xToc-KDcnY9@wU6r*^dMG_-jdi0XacjUi5MXgSucZRVKT$<H@$iJU4wZ6Cj$s$=aicA1Q-aklqdEs5{kOlF*jKYBp1YpB`s'
    '=<nE4Dc#}$^pu*-ICo7qw3BI-b&+N9NM_z%Gj$X%ZM=C4q#co9xBZ<Dd-MK?u4e(973Z5dQ@`;Hx@nw<`+gw!W>1xzO(6a>w?CHS'
    'iSO$AVVOA^qn7q_H-*3@lxNOu;6aU)ljGQTbAQKIbaIEsRDBC%65hszNcNEj&Pd|JHg@beB%_`XwV#=rbo*O6XRB{lf#1LGqALU%'
    'j>*iyAwB1{G+-BQpfno#A=uXV!8XoNC)o6h_Ed2_bt#*<pZzd*wo7yDL*p~$py4D>kz=fg6LNFsj+Q%WQxyh7PyXH-E=(@QsZGws'
    '<R?xxRgUYruJ5U#`+MJ8+Wo#g?03)ni|1E&y{v16^9UvAy!U+=xFWn8k{yTSCg1YRxY1*G-=3;((aG7-byO82kjVr_6D`#(2^i(2'
    'C-)ur;MtM=b=%o&Ndh0ww?`op^nT(%#jy<yf!Oo1{5*tt;<D(t(|pP;+r4jVH{J4n1kfTO=8R`>G_sJOI&qp?6Uaquww;S}_(fX_'
    '`{xBGDLt?uyVT7j@^&@^O1;mCq?z!|Zii@m=ANCp_-l4`OuwgHp{k~2okOn|ND)Z@Xn0;zW4J!rE={1J9f924x1Xv=KzeBBP7p&('
    'c@Fd7xN%)G@bL!#Su^lL4Q1|~Tlpa?dfwKY@fq;Y31H|_N6j_H0HQV<?|=;09Y|X;(b;_8zSgHkyf;VA2oBQwPB2$)z#+`gT8{Y8'
    'O)WdLP4@Thi~ML44hd}cv~^F%0y;p+Wo^qvJI$W7EoUB<asuN?c1;(+0I6K>-cwCV&~f>5aQGk4B4-TWJXtl6KFCcs4HT%xjj?U-'
    '+sqBw8#$!UW-!CR7e?9a`b_pe_Su@`3|CIeJ!sl+-^Pyn*8`wd*ndsn*5P_K$9l1$C~`a*p==2RcL1uMRRZKNM;=-LV!Crn$|^S%'
    'B`gRN`5ItfJN8s&*>lgdpf0g%!S78bJWb7H?625PcH5`d0?<3zDI}MA*Vx_#8YVO@dPmL@S{_sAx@o3?V(vWGr{|ZveM;}u+V#(W'
    '<kBBHM|B1qM8q6`Wq2%}e76xKOJ}F;hdWRA>F|0yag%&Y-w!2dly9E=lJDF4WH{3^?<mXwrHwZnsx)OAr*uz6uwpaHvYXC~V503j'
    'W!@eg4?14fH+*5i+peF%BI>UH3rKzWC)aO_*ntLeEI>!cp8JA=z9EzCjqgch!D#y_OjBKk{rI|syL5Qo9*;{8@oF;W=b3(l8Xb8`'
    'K7wh`ETv5Jw3%$0LgOMar|u_z-Rte|_oaZZ3z~Xja`R||r7hbM+NjSbZt&Qc2pq>}Qn%(gZMhyg>0q^dcpdGJs4NQLI~f2jV3W+9'
    '6HUh+VqN~U<MRJKZCrfbUcX7`Y><2q|7cAP1Kkf$iI{_<v&H}G0Jtm#LuEm5S+xdCY#J_c$}$y5V@P43u(y2ipdf;e0_7TEpzbXF'
    '_$5{67@;$%^%VKkhpJlX07cvPw5aLhbxj-n3<zIYFaFr?sri&fn!&T}V(dWq`_ZbvPczvwy<Ga@YBN%s#c{>r=fX7X4{7ro*W)f-'
    'uOSp#31;*;>=3E`h7pu`ZdAF?G@}OUR2On3M)%_mp7+0}r5NQ3DqMvITymtX+W4t+f^kV}NIG>lf{V>m?IVqc+12l1T~rByC*E{?'
    ')(x#Mn)K8OCU?d;zO=*zl%NWP+1IaM8Cp!t)Q*!=tqqPcPJD4f-1x*NK14ea-pRYW`i0N&rQ(@W1M%Kz=C)j4t>G)2$fbQpbG7Bh'
    '1t11Gq5rvd>Ay<Y>vsr^?1r?*k-7>C8Cx>@i3bm$-|)H(I0*?^zJ2*iw=cZBUVjdJcP2npXaq$=3!%>7CL2JBx##F7Oe2k!`G$?u'
    't>5LICZ{3mquELFMV6ZR9=eu4m>lTB(E8Y{KLRA|3zvgW!5yw+LEdwdw(7ESs{}$`-?OKX+MYw02#yn(MvVUEEz~`Uk>}5P4NY$c'
    '*&y;)*akd&M}3^Q*-5T?@{Aj{@%{95zpDc@b@(X~0Co5tsGpz+rGBJ|VgXj@F;N}!yzC7R<B%S~bSPBf=8uDWc`0RC!8eq@nL|M+'
    '5C+EO=zB*`n2J0ZY6BvJyWwB}EM0HH4g+=Cz+$9x(W<owG??kOwO%1o47Hv%NvL1CJ|UP#H@i;cl1wuq#fBTnf^J!ogV=kzjH1Bg'
    '75C9iSpofpo~HM}^XDgfSaEbagA)|!*a_UZ5QeUz8an^-hwbj=_4I|e{&ZngJ&@r){E<k!fz_ypuI`3jovKvc`f~mPnLVW<(3$`d'
    ';O@+0Y5R&S>8IVW`a_B$KK-~cl^z>+(xWQ_M~*6yG>sahg@fcc6@jmpvShT>9`uQmPHhD^`q{=xq@Bzcp!|u)(h6(f3XO4sYS)ak'
    'K6?*2jDB7PWoEgo-^h*Emn2o=Y$`jY*-J!F2i#MOjcJ1P#wQ9-WOTW5$v0?Bv2w$EaEIspVe`trSIAoWmJfkDl8y^_SQvuJKcLom'
    '8jZ=&#0<qKVZ3%9=gRZp!j<@PJcR$(<dO2m{;$zVKHtijQ=$TE$utXiCh6@o!5ici!9BI4Ty6l*04V4C<=HqWzvFbrcHRJlWn0&?'
    'UhBseDxp}pfCb7!s5vbBiA*}oK1e<@grgfbvyeE?ryDY<J60c`IPkra2BsD$s!iO+0hS4GjoRDAo<AZ>94hEn#eMnL?NdDCKed1>'
    'k!^wq)Vdi45Iw3U5(LI^6aoT9M!TgGKhxa5xeI3Z!(%J(Q26Zhya)*az9vXrqi!%w1{gU*E5?IKv%P;~TiQT}x0iY$onJ>5=u@?@'
    '=O()423}4y>UMNAj9d70@CzZFn`!<9JKJ$*J<;@V2U>mCPgx>Dd$4G_)}(r1=R{B1{6I<`Y78|mZR4r;{r$T-Cq2Z7A3C(xFIDd#'
    'd5wUJyt{@#75O0J%u(aS!L|hz0QH~z{aafTyCQi8XP<))f1dc=PBi@?I4P9UKvvg-dd>ZU&+?M4Z=aV+_SL_9b;klb8q(xIm}h%|'
    'I#y@`8Il7qh5$f`%Y{SxA^2Z##?Dt^6?{F?=Ojvi?SvKpahw*&G$$XLp$#IbwLG{c-M^{h_HkiHY>|Rc`Br?CJ-{NDAw?g6wgtqU'
    'vY#eC23l8vM3)B!zMB3U_O@g?6>aw^MKi0t2Kja7>`@I<5hbwDo)Qr@Qi`C@zu+Ty69Qb{PNshh3lvC})COp10u~zDfx2MsjR0x-'
    'rQ8TNZs%<eU)Eif^!r(q-d`8J;Hrt6363&E38-5h)B@Djj5oi<_gyU)Wr1}g=n8T+_n{+BSw2M)Z*VMdUEg*RDnM+$`}tf#{B=mD'
    'Yg>vXt{g68s1P8m@L7oQKnO&2Xyr3#r|s|EOT}l_!l)6c4@$-e$_Q_lPP-=`M%@6q864Rt{p|7Xtz7DdpFg%j1ZY$)<&n;b^FZuf'
    '*NhR;f9Buncwy?O0D#}SwG~?e6a?@gD#F*YBvf9cRq{WBris2z@}uDK=1Mggw+9J`E;~zYdTT{2fUFCrG8UZa=Hw>O4W+c5!mNC1'
    'Za^T04on=JoU+D^-I_g=idd>Nija2dN6G^V0u*_jxXiSbB2o+r$`LJD{qL@9G|}&EP&3#}FCMy3hv;OchKFoH$_9bj(1kGbM~9Q^'
    '&+T#vwMZ=uen?zSMKQg9&_sS1qNM=o#dG?bffxM|gEQ^}wK!R(d-}40s{eyTYomWw=-06<2N?ZZtNSc@@T(q038%{roflKQ8(q4-'
    'tSE=qF_}4LXy^0=rbHrysuBh*6}Ojmg)`F;@aScA*OxgbJj;JB^m^yc_kvk`?#H2pGKdyxq-g8tQYrc;L^JV&A0_xJ?SzVdafj0u'
    '<rInX!gM(mIOJsK5#}9eFjon3oW=xtMZMBu(JI?ayNGt#)g_mcLSoL}7wK$9wEzu$2)_Z2R0E$iHb8DeqHv!=kD8Gf@X;OnFAJWD'
    'A=l4|6SCKL4J<VP-;p-s00D{<-_2A5{kbj<h2MAd`{&K?+}g36(g0)5)YLtnHsA;tKh!U<nv6gac-NB|Mjz*on%C!SC8poEdW+O|'
    'FDI>Dljt=PCqN?+V95ucwAh5Ii!z@}(!+mmB27<MS~R+sle9BSg!z{hd3t|6SDsqKYlIs$f#P~cmx=y0SOQ^m98H`+PGPs#t$2J_'
    'RliUay#Mj_z}Bjxik6t8OHTvQ4&)Uebi)ot7{CpUmCgru;|^Y4wy)2dnvDdpwdp3MacSdr3Au43mMb|^tcMm1g~9bJH&XQw;L8lO'
    '*F5poiYPh)2DFeP$Uj^=_%J!t4oD5xt{wJI+%Nlc3V)$Jmd}1?h1`48YzT%a(5U@sUI4F)$%i0?9`i(&AJ^_?0gN|~iH3Wr<p|LW'
    'iZR~;-F(8DRXzrz!A=RuvK>K^!QiOMs<*J5gQ|A{r658#%LFu0&3X&jDx=Y9)&2)F;yr+Awbk$9|BrV-=i<4rBqZC3v;szAgS?jC'
    '85ICWLM`ods^SrL0j<}rcFCBI-{@X#_Tlwu`)Ad&2UgY6^sRtS22vhqJe1;ePG$?e94-?CrZo09ZsGCeb@LT|<Wo8pU`=|8k>U~E'
    'KkX8l{l<1ACO|r!dTT8lJKjcWe!)H<MRUDFbuaLYXweWAAdbNy9dcINFREk`7r`PYM_to(=GSa!0hlV9(E`JJ={7p_`ytZ#MJ>^z'
    'LPn~P^a_)BSKV;quDG}lFe8rJZ~X1s-(5|-sDhxT%$6KzCN%+M8tKTQ$cz)+t|(bFErj;Q{hSd9_x*{0rWz@2Kf7XohEyAfzhp;E'
    '9{OJ0`5p>M!p6fYf5&`*$~*P9epajZgOvq=BcL5=r<qy;77Z#1o>`;@C!_|F@9slak&pNDybs^1K5jRuheJ_4cJh2cUqeg9NXRcu'
    'R2FN2%s+?Pg)h~j-|k|GeMzM%Wf;LM7<B2JQ8}9+)E|VM8G<V!)G$<k&oA4sw_o!1&y!I91^m1o*QD7Yp(Br=_o%X1bOF*yp&lT|'
    ')F5OX<Fs!5zbI4H*9v926Wx^N5v(!wsi~K32bBme5xvn->^^|9bsIUzYUNPB31m!^LbB1Jpar6H9&lA=H%MX-$(RWND!@zaCirg^'
    'QDem&Z<SI-sgMD|W)FpkOO^DK^NFk?C%6Q`QIg)cgLA%9{XC@Tpvo1@g$S4;o<2Cl5&7%n4l!J3A+=1l`mX<d&);qqOCwdQh3G_D'
    ')zH1`hyY#`wniyGixQTglcK;8tFXMbuUv5E<LA&p*TM>i4`K#e0}kyivMe7GSSS|;iks4c2xh+jN2-!u(Q^l7&<D?T#f#3fG)^s;'
    '!@vzsre{E}=|7Z~T%>4kb$LN2JWD|_(<3&Ce!p!Jj43<;Wac!{z~wIihEgfu)aj(@Jb^nI0C%_*tvc3J--v+7S_1fcf7WgXTf5lu'
    'OZS&{u>Rxb{BMvMJXN$^1)6enBNaO~7$d|N830kP^YGy&aoAc2AF;V*JKLQazi=-6E52KY&C9EQ<HB6u6Ct0=7Z4Y80{AWf_Cz{&'
    '6J|)X(nrB~9&Y|!dy={hy;OSQS}HNuFfEZ5VE|qLx&xL9(7EvmLVXWR)AeGnxsNQ7R_y18_6_MlPN(hj^=pbd5C%K?5z1cF!Md%G'
    '0P=Ov@#O=O#*F+ox?6Vj#M7bMn@XXXx6r6bk0aMa%@cW029^*-2(35??f@*nL(DCEcwX9pv?NM<z?)0x3kVMY6X_#(9v3!e2GcC|'
    'Lo9~&>*FnZki8FkIK+x)k+_*UDV}gW<D>w$!;XP-f+Ye{hBzQ+0FVgdE&HG~s%re@l^%T6;h^T8sf1A)@M%LagxN^SkFy6mqFpp)'
    '-CDzZ)8Saan$7v%I)B;M-%rEcJWvmky~5t|0?B}K;VeN3fB_hEYSL|A57_+v003~=%|D)>3Zy!c8RR7p5V=n<1ft%t_<vEQL0Tf@'
    'bDL7M$6v4&{n>TQ0E?Ajq+gvDP8ohgJQiXM#8{Z)W159?PjR??FJfgL9fzfW-U!76{Wj91APNE7;!OeHlFyLQO!%5WFG=Z^jU3(c'
    '3!1c}_`&Daeu=ox-+(7lVc~HwhvZwb{Y=F}3(fbC0%25hXwprw|0HF4tf&C2Y7Stdk)HU-(V)LVAHo47z|^&%93b>yfc}<EoR3F%'
    'q7b{j2l!)>iA1m?jtK%d3HV2lUmzcv<$&w(?#BAhCVX|LHyMpP6~7hngh8^!QKq|0stv9J(9O*P8I|u>CV|-9)Q7WolgEp76cFy$'
    '0zv>G0e~yf?-}7+sck^J67~X;7Hpb$9D-D)`XF{D!JcoIy_Z^&W~zv4?xm0<LH&fbP5Md8y$=(e8ayvZjnqITrc#r4y|4dP6~n{#'
    '@RTljTL^q1%HK|37dL>XRIbaULxz$tG=wfLJNk)$ppXT0`#|EL7YH(7+%MWwg|Qc;5q$Iz;mg^OFpKm*0DD>e=}ZL;-~+>O`Xw8R'
    'TU_@}1;%@eggwwpqtWYS^EHTQ74Y*+u!lHWu&%PoxL>lPL;A;SDdt0F*3lut;pc_PqmoJ-f%u@T+P4#uTZA!oymv!S`^W9B3Tqi?'
    'lW_$mUC>xva<W0IE!n@=ve;8{Lt1fO?%fgS$59%MT}V}j33NjU?$Sr3Tgn@o%|M|-57A?9>m^|3R=WF1(QtfMO_%n>`{C_SlhAU)'
    'f|YQDHLDZxvQdTyzc-Uoq<HV1j_Jfr^$51Rb1%oQ`@*ge?OM2kAiMNC2RW+fEk<%pD~3fBK^%(qFWc4Y%hTRnhnllccnWx|L}Byd'
    '141bRF(*TOrV}ls9zv5H+I#nO+J8&C3vKp#vIT}KR&1bNaXr~M!b74FbR6VQbBEx))%N_&8;bEDH2#p1{*7IcBgnNy*@*fD$_r>7'
    'ywgc`c9@00X`F1!6$@?U*6r{Q)Tr2eJ)K^v0uv#TzG=JgD)4F`7+6@J5E8gw;8@~9HQ?Q9hI==342SJY&DBp=%VX_~H%aKJFVU!y'
    '`~kw^6-xPyJBU=Il$>{Ls7y1ZM`GkaKt&l_GGi)Ps%z{KkZ9o>$>oBGs`od4@Nxg_h||mU@t4>4^>}SKrw(NdEL`P83r3Ex67CK3'
    'R}v;{CS>e%=a!zflG;|Fb(ATSO{khZ;SYrjC{_d+#z<{yNfjrld5B2%SL}zXCT&YbKyt8)Jy;$W1eplZHrQAC&@hpKVAiT3Nb9t@'
    'b3>9d;V)Mep%M4Nlz`yV@J)l+Qf>in!uNqFFZZ-aRt;9s-MXbS<LLbx`$2Jb{nhnyDYNteF(GiI(P%<P_3bHg@ZRvqyr@o_U$rg$'
    '6)IzeB`YZjuT4%?csRjKhP4<*kU)IFCf+W{BuegX`bGQ7WqTVrMJEtPqNB7#7Ot|)?#a9%;t(rABQc^6cWy|xYK4_G#w-d)8P+Rk'
    'C<l6?9WkpHN0|ye2U3#SL*~xioLP<sKDrYO$fB|WmMerqQVole6`cUmD<fVv)glgavQEO`0;cJmySm&Tue-{JMaLFgmi(5x-BH3a'
    'H^5EsM1=DI!Nbr8PQa%0)@?oRPkV97Nw_b2D`eXc*(G>QE$VA4mLr5p2o#<IfY#y&Q4YrF&Cy%Pg7~<CEw6uL9`6k@enK;iR#7Wy'
    'ta7>WsZlfmCez-e@ttqo$kRS9c2;NesOyN2l@mEyJt!peq5<I2fL2FMMB7_)7pSa>+;{9n#n9y?UBY+ORRZi_glSW}Le*rBM<+zC'
    'r4hlal0Vr<kwkTJ-^LaZbzHu*urIbEl%SCwLYTnMc7_5RL@bAKhp3PuPOZ=d9J+N+7g*%4$5h_ZU}h><=0ivl2TFqBLKbzGzAQ(X'
    '7^y>TZZAMs6}!F5`>O;;EGeu^M+Do^oWR*0r{+;qTjcjJ)1dl_Y<_cEvfHb1Bs35GJ5Q{{_%+;T@cx6iifIulh*OYcSQvn7jO0vs'
    ';oMw*?3Wz!Tn@pReJw;q6g3zzKqNIXCL>D29~T0l#$(cyh5-1OZoXlG7Imzt`3c!|NDYvclU1_x-$Vl3acKJM4^Zp{JfN6o!#?vp'
    'JGxjyY))V0x_5m$m;pEHQ?M+_qFmBu)~D+S(^Ne#*fA&?Z%&OaB^h-P(GkL7nRFm+F5f!rdoZh+gc}6|M+dogOZT89n;dCs+<cEM'
    'H)*W9J6djb+5(uh;h0bUO0Eb<O-r6`Hr85nzA!sM_Hz4PmOCD4NA1^+DAAJR^KPgLZ2<ege;m;Vl{H#VIvC_1%=;Mb+|lpP6$T&j'
    '4gqyx@Kc*waO#O18m9K(v6a@il}KXk!p(Wm?~@YO--V`?()+FvduSG9-D&IvOHZ<g<jzucjlVQy((LZoN%~WKc{Qx7ZAV#r9%mUm'
    'Fslg%y>6)v8M?#G%D;+GAz*fQ&!)D^(@C|DX*S5WgItjz)<A8M2Of+oEaI#TV!%LT$kNUC?Py<7k1_5?S(%u-Od?_C5xgD%GgJgJ'
    'DuQpWh&bL3d1@yoVGR32fpTb-taoyC7$I-tor&y`_?!}XYpcpIO9FVuJ}zXyP|_Phvx8ZTPZ=0KmO)tf2AV(E$8}MrD17oLX??n9'
    'EARId5wMWw1S)2XDM2_ud6BUU4W>ExRuTv~B~<m?=6vG6Vl(CLAOM)uLg>}`sz)I(v@21q0{>`Y7!y_S1WEpm%}8EY&`uG`B!7{+'
    '9=3jcC$qhvNpPgfuwzKT93BKd+_Q_5+&VWRaTT#B%3-xcX;za?k&v<<y2gY%5IYeify}6Q?uotcIYfdJg2umK_JqF%R(p)qf{Q-W'
    'Fyxu=)@Z6&OQu7B=8y8tY1Uu4=Voba7KHq`V53I_dWT#FcFK#=+$Y)=l$@MoKp(l&-*QRvV5FG<OF46F3*t9gZ@3Ry4Mp_wVuNW6'
    '{=^l@w+v4Q#F-4MKDT;#!iwk3;9&XB#ojiVq?0*CByR$`q&3*f8_iQu%_Me>8e&)&*Ha$glb$88KldlzK$L2O7C7ECl3?C}rq~hI'
    'C2%GzCg^Zjw4l*#X*BdJ;EGT7wUh|eyFvyZ^s=x9#yt`#F`ZqkJg|msWn@RgdFBC*_U2t(nkTjUAr%Iq^vD+I4Cp(j`35rqjy}Rl'
    'E-9KB4Ei$W=KcK0qO9E%NuS1zs(ON=OxHjjgOaA}qo*4NYLA`GigfG4P3fQ2?`dg$!vR3v4Sk%%6yOldt5Ik~qE4i4L@jS_-BUQY'
    '<5z4Ucl(no>%W1O;Lgm_P+-{sehP_P_OB6k81(`KTnfH+1wZbec5}fj>W2gI#x$su`EN}BQy3r%Z4rs%y@HoHh^D33x;X~?3_DeB'
    'O144~_5^}Dc>kJ|h9!Q(EG1~&Sc#G;BT05K-nS`L!_{_u_^fpKY#K;%EMsuS^kM1KP$ZAS!KEAOhFf>^j-*s?2xHgQ2ZX16(!HuN'
    'P7MRn$OVxg!X)IMlO^B$-t=(Xk#6^j_(;9mk{wbD_wqAfTq)@n{ZjJO9)o^rb?%k<)*W5SPx7hPM-2-oK=GhVaM_uCCHE36XdowN'
    'jpFUp_!_9TkXRv<9PZxExt+7GzuxG*$#s*%1n!h|%`t0I+DWP%ph7S^M(Y}%?%dhZ8>rorW)1dIc+s0f=s-qBYX!;z)u<I9P9`~x'
    'ACBu;wWs6P*OL;)`uhavlz?Pp*9x_(!)1wP4>vEwAyiNl8)!Z#UaR+Y*~oIVk8cq(ye>x4CwL2_aNFz23Aa}QW}yyZkQr;^8VcP6'
    ';Vpe<z!#h49XHSS>}c<QBWa>aC2Ybi-o=6uh76U^xuQqIoFDF+{Kg37;9*f3Sj5NNEo%~{5BBua9~DzeCW`W=CYjjdWQ0KmNDEF&'
    '@Fg*-S=@ekicnbVca*UGP7i9ulS}?{et8{@q5^_K*#Ig?$3s4n6%s(kCctm6>ksRW4=q<d+svikeR(pMzq{1)*S8}5T;?ug9u-sP'
    'L?LAasKu0p1Ox^S{b#7PE9lOjY^9j`b3uTxz^s<ehdMcUHBlkviv`}wXAQ=_t^cl0&I3_i2*%5Q7P<FWV76*}1YV0gjX}<M(C|RS'
    'vIqehGfsJin*h_4?%74@Nf1$(Lm;;~jwa%|q;YAj29;nCiP<aEM0|3Z`ZW4{G<REl!072f-=5s}g>+ren2ATM0o)kM^`i7rF%RHQ'
    'kP|4O0p5FR_Z4KQ^FEOBxx>Zk?yMpy)yK%aAYdwr0BB@6!hmT*fYQA64k|dd>f@Z(Z3AoW&A}-P+&t>9r9Qe$Z&B1lrOKE!A(Vi)'
    'mK))<3=N<^!<cHapK1Lr`0tMeD>iwHjG7AoXBXfCW{4L|G3%;<Ka1>_PJ<hUb&H>0fsR4ddw^8|&WH&eq(!Vv@Ft}l1q&P=BM$1)'
    '<}!rPuF%I_WLDD8Txz<qmIqQSLSxLZVZVB&Wy18PEgnc*sB`&K*zXVsd%tcI7ufUdAQT+vD72H1Ul~0!IwXshN5PG+jObQ?(r^dN'
    'wDLUCcf#qZP8w)59VOC=gK~#w7IiEH>P}5wyk~evBWiR8hNX2ofKcL=iIesG0K~?S0SV1~kup@I_s-ppNQF450TUSee`q>)bsLK$'
    'r7Q*UM*0I>ED-7px+WkXQ&SVX!9Y4jeBgZ<bHDO6Ttf5@kD$sz4KIsE+R#apbrl{N(Y6T7z&xOAiXROZ$*+7P^t3#oQeS9cc{Jcq'
    '`LX^|g#}0l(80_vI<!HQ8g5feFL3KxxBTmtOz(6m97eQk{5m}2bzcI5(JwOSL2<5t!Xi>{5MbBE)oUOB*p|A}nvg3JC}n|^vDib1'
    'v8$;}RC<_=0DT*2p{v)HJN=o~^epQV%`Hg2#&gPIved$S6}nCW1Hf(R&Ny)%0fw;LHkzT(w|DNOs10J08YTc!3j<dk<T&YSA}o|4'
    '#zrmPTPVr0_3O8x)h}GHN@@i|er6O>s2erm8OR3bJMIe^CCCD-6TS@cwBqGR67(P*_xGPt34HPr(QAR2i+niz{`fv7ZA$-3MiVtj'
    '45}`Hl&=P!6H48|-oC5f_S;2Qv1mLt`N=&NY?;-1rbRCHP?S<YZb`c64Ju)BFWJE`1gpJ$M`v9qY!AxZ$I_G>EcLPmE93G<$O2iy'
    'Q!GmXBhoirHO*vT?E8HCc3>^;Q4n9=9<vwn0ct}5%Auntm%Of%&IBJZx_ex9%wd}}E<-BT9&eIT!IT8BFQb|q?W;cvW1{e`=oCOZ'
    '<Uu1IE4&fN9Gn^GIiN|6W~{a)STy}fow)Skt1Jkm%ofhLbeyp~#ABKO+l+3>wpo?{3;NMjugYgp$R_v-qYp+CkfIcfoh<N;cv0M?'
    'e5I7k`1Y4d^-GKCpNzV2>-<(Sw8^5zDwV+b5R?EaW{a;xWQZoh0@xYMu!i<zD%U@w%>{!%O;@F{1qe3-jL6-ddIoQ(s7?is9f?(H'
    'a^;E_g}|Gdwx-v{Gz2mNE-7>-m<6IW>jq_y=+4x&3GLEvD(2E}JJ=tPZGid}r;d#pEI>i6dC8i+iFy+5d%p-3a1ml06(ewq8Qc4^'
    'f1K0BJ!w+Ot{e|KI+~20U{U~`SDfg)*!E%$&{<3*Y>d2x`C7R&jtqQBe?59JHTTzFI?e}^h)^2$9VCV5WP*oM1gsOL3Fs6>bzHZB'
    'MaWYab_LZ5ZUjCpP6I&%q*}SoMR^n&*Z~YhZ=2djzD!&$5K+-FQjTe`6)+${3g1l)9ixxJ7J5V>Onohi8n$~OrV7-5zJ$%`byxCM'
    'lj?>$3$zwuIWn%KA)RQX*$%el8Zm`BC=_L{T6aO#^mNPP<jC;*MIs?(MAk?O@=?&LAgMZZA<S<zy{M^K_4_U$I*5d>N_!gd=^y|G'
    '*ilqulO}4j9<3{V%#=kVw%aYqamC^nKh?86!KQ3J&JDzkK%d8HVs$HI42mzG5FI>|p#jp0kx-*%X+Yilecdl-m0sv+!^9&l58$ax'
    'l85g(bGuM~F0X&EMSGFo((W7f=3ijdfWvTY6nyfSnZXDP&4Ge`lr)GoD8t8x0D?<oh9)0!QPT9b=y^`KMn-yZ((?APQ1<tlsskJd'
    'wH(X`kq0>d>4#Eng-+xQSZ;*M)!*#P-)2mc3O%O6Q^$LMadkxPx;$cZ!JuLIX7_S;1f?T>q86Mhx3Ca7w^xmA0c7#DhhPus*on|Z'
    'BtxA+RRRAlaq=1!Cq?<;+lrS~XVuHbnUO{hA~lVM2IJ#-C&3y}W3U~<at~|M58a<XUwP#lH)tQoI03j27UX3tDy&{^3fC)B88W;;'
    'oLi<fTc~*EC@XL^;2@_Z$K=XD=R^S@_9_-tmKokbet(5!pBX3Ss?F1=6nV8=ixz(Z{sT^iEqW?4B062N>ZFI7X_}T6-N#qiioCvj'
    'sQmr$XU@b7Qamy(tmEjNF#|Y@i=|``!ZaL9&6+M&%;y!4i$(OYsxHM?lV(&ayo^QzV-XBIo{{$qmj-eXBc;`o9ewS>FH-U{qM@L4'
    'rfDFiz^uN;AlD&Cl4JrLWKGmST!hfanIg;Lec7cGUKD)eUju4S&j9ig(GrE4&^nS4Dwxp;nn3=Yik$HGRTr{Lm0t|@aB%d;Bn=aa'
    'm^{jf8TKj!N$eeHBVfadcUWJ!vdW5WnOi-`AAvub;S@qyY031I4q@^uUrat>Tz`$3YZqO3G;d-X)NPUj6`wiT7quFh9Ts44E}6pt'
    'dk)1mYEFvk5!VK4NK+)zy=~$`pP_avDQvBPKW<5|R|G7GHR+twz8}=fXV9^JKE-6eZrufsrC5F`sCy?`GH|@GU7QrVWevmu!z^}`'
    '7)mZNBxtd6?Kf2+DcSX9xd<6Kq{*f9Ecx}~ok**K#F24)=rRn#usBsNo1eZH9J82v2&N6jPCy3TBgYxARHpq;((6&7BF+UXs9bIv'
    '7Yio$?P{RR0P3{yH8i^s9zl;~Qi(bN?DDjo>}E*;Ymd{p;j&Awl#AChdhm46FknpDzf{cl{mCyG^)_R&;m%M}kYdlScH!S%pRb>x'
    'UbcpseT_=pNQ;2qB!b>Sd94f>@gmdwmZ5UJ^ANJl@fif->I0^W<0So*-m$~bX<#1kEO8Slu>p!x+#m(Wwd=moZ_BUNK(Z4MfRQD^'
    'l0$?t2CRh&h6pLzI#%t>xCpCPu8dTCvUE;h9VC9VCB=|YX-E5;kw!3Wk#nPJ%tb%!_x1PtZ-qYQ(yZlz$BKTI{>CGk##aNIT9{$t'
    '{4(0Z)<y}<TQ4Z0_-N#ij3Aqf53w3Pd)xrP;Y12jSgLb)*S2=O*Qe8VnNxbbEM)YOJZMGBlYkdkZB`3k^EUzGF>a<^(^j9Sx51y;'
    'v3#BK6F{5Ll;jI7NLizxU=lD(1(!X%xxgT(nt^>PckqKla@F#TGa|jgiwD9lZmRO56@mwt$L*Jd!q5|A5<}(k7hhzY)t^pZ3uu7E'
    '9(dB?sEAI6t|V4T)ThK}`f#}J_Ym2Us#Gp~48ThTPzlVQyEa0?4Dv$7^U?}-pge$qMTM%cId*Fn<QW$~TzCiSaKT>0P@ivyRvW{c'
    'oV@)BTS)4_*|-kp>UG7W0?VrasDTZo)}<T<iXMeP$Z41ehC>B1DAd?2?T6YZ{qA1$gAvvBpN<+L45Maw@F{bW5$c1E1D$flIqEoL'
    '$O*Rg4nAYHfaKrdIesf-@B~Br%EZkAdeFQoa!TfvXMzmd5pNRzhuU2F(vMm4t5lG^S{VwGdkk{?qhUquEj!nRpoxf(C`!SYYD<=L'
    'll%H_<(Xm+nsFUsA`&&HaB9YIk^=B>m2Ut5^+Q~>;s(yl)%y?x7GFgi%r%{tkriAPEDuw*RppPF-az9HdD*&E&l%75xUbOjG9(D~'
    'H$SnJbZQi%M}2{r3X01_nF&|3>#Bb@)@A4QuV+5E-%$eMQik-C4{G_U76AwPJ{q?iai(X6+A#9^vOtNiFCw%QIsy>0d92tI%ZZO9'
    'r{~M2R-pf(9tlWlR&1%gDb606btMB|DRaF#Xk<%v86iVsv=K#Tky}y6;5(cw=h|}RY#1pc(SxgS*Je7BSj3!T%@SCM;@r)HW|K&S'
    'VHR3uEM*3$0(XBN&Tsh3hQDHMzA2DqW^wmuH=|b^M$iV#T(R*QHIhZ;5;Y9!L9=Gzw@Fo(kt5fSS}&_^eCfEU;GgqzK?3A;U^U3X'
    'YCJe`ylq#le{t%sv#ys(7EfN{JD6m2I7epmi27<YU6i~mpwBi%x4xfta6u%V<Yj)q`USM0;L(Zi&4jp&h6vVo@T4J9=|~uj?tv)`'
    ';^v1UH{qu}R4vS7roHb4wxO+|=LA)Y4_hr(dPFz|$>z8VcJ;#gw+qw|j5WYB$yi`9QX*qQ3ZzSW3TXruKq4427pHWGoae_>9W`0!'
    'Fzq)3l=3NY;t&!cL#5tHvply4*w3P_7gl`Pz92*?C1R9L!d$$jMp_LhSjvBfW0044sETSMmu-$d8e93}1ts1Hssx&*)^(lO8Br#W'
    'bj+!S$*=)1fu@U10HMGuCldk%i<b@43A7LvhRlG1K3UC`5NR3emoI)aXYYpPTUm$!=YCT`*8?hv6*sjaStq}qarDf7AcnzxBt!$!'
    '6Ddv6Z}>=y`q{k?WPEu0+3&W0)k71}b~{-lXtbBrSX)pKoMc)iLTUs-ACa^8G8?vLLp4JcQ844sihz!49yQUZp$*i1q{ZOL_>*Wn'
    '0eqSEuI<zv63?(GW-=p2gF~X`K8PFIJtJ94$EI}0bVZ%@^_?u^A79+IFptngCXLbPS0UOe5>Ok!;ZDr#WIm3lXmG!ZzA=}rfUm3e'
    't?|ue@E~&!aDm37mLZQ^CJ34uAq-yHDrn2Zq27hMg-@z{5!*AALQkPsn$Y(3@(Fel{nL`3B>G39$7B|c<}7JL9IMw}B)I3RJsl3q'
    'C<>Z|B@0t*uptb22sPNNh}<F7H0Ekl!8~w)XOb?|uq!sPlEO3tGGjlWd6N`pLc6i%YE-%Of}r8MVcJ=qxA5Z*etT7BRrB-P#L!eL'
    '1*@E|U_QX_<J=4RkJ3Y`W6m^zHH)t}eKdh*v5FQBs7jbdGH5<QdF_Ff(k&E#JFQrK-4R5FN)V!OKum;bWQRW^C=?Hcf=1)61E3<K'
    'f=ahMJoLQzVPJgyU?N!gz_p!(;Lyr=<C@Sz&#6J9K1;{}Q2-b)tlhvR#jKiz3K+rM;~?!@fD%HY&$O~hnE~9NnLZSids`fg_1PBc'
    '=TY$ijIybrh^7HTf&ixtbeHVQYl?zh#*mn`+o+$#nx(oY-td1>E6Q{Tgcpbmbyrk(2DhJHJ(}Bg@W#@)UhXh+3t9w>JCaVMQ;eb&'
    'P6oXVl>~M+ojSm-h}Qhe7V5g6C<L%NX?=pl$@o()K!9H$Xch*6rZp*ovMEZ*|9SPFDUOQ)N+I<IHIYLPlSTo8A&Sr<BllMWNje_z'
    'JMKgq?%GBL(-JO}nFG}}xiHOk-afP?#M*cR8V%84LNRddWbWEW^=MYct5AK-!mhADz~QNtLHeu|nkF7LVbsOBn^tc|6IwTQBfoSx'
    ';M2y;WVBlo&^S?>Sc%mpty@cVBu_5x?A3dK*t1KIW$`6=Eze(SwpPY73@>4t8hJcqSPUZ2s&^B>P>}@j;RcTKvMb#ebm5gEp}M3I'
    'GRqHH^p+%(Sgb3V?1Jmx*u=FV;%&NS)f7RNnHG^mBeUML&`*|`O(1UQSq7;;!|GG{wuS0xwJ_N-WP2+u4Rzz#FV{GAk1U}zMwh;?'
    '=Iz|LkN3f_RSxHHff<FATaD3f<;LTcPLfkV0;0<d=S@RETeo&I=bk?4MSzpE(X^^Vp+h*5x=_r3d;>ItebO5Yk^nRs=j<F5S`w>U'
    '_o3kqyCuWoqAHFbrPn@cwqZ1ljLxV-7i-#KP>P$!rTZR={ozmca?Y^X(XK*)2PZ32)lgW-0iRbx<pt*gMIyvUXc(L%FoDtBwv`$N'
    'ISz(FLlE)1#|w{Zjw&?Bz#Qre^LnGEYXd8;4P7AgID3^kArQCVj?)E!MNL9aJ*QAf>xGMs?m1K=YOg-5jT%3T7B*GDk4HEULk+wT'
    'mN9}Ax+8d8Bme95y+SP~fP;GVE4NZ-n8oeDlo<4=FjDE!pd6o-+sgJA^*-ND9Qtl;uAQH@k6$?pua^t;8D?lf&;b6zDeTo&W%L0U'
    'BFZ-dGBk>j&BO>A8X^p@&9WW^_U&Yas^oW*4}7lMqMCysNvD}cGqC!IsTf!cQLH5mB#O1FM<Rb+yA`51#0Ix}ec_lawcviA3v=A)'
    'BhXDE&4PRcc@(lX9|rDJuss^cCG<(V5Z68wX4LLJx=McPV?p)nWxWb2$)ktcKu-%(IXut7xoH!NpWYTx-hW>DhvvreLe`i;H<~6V'
    '3BN{~V8lu%52X+E-5v=)JvHJw9-DscCkugm9djI3CkanuD10<Dq=T@h@oC)o=oVo$5jI4J>2Kdhku=794*rKR@0d7&LboElX8E`<'
    '!Hil&oJeS6tM3tQVU=Q{lg~5AI|k22gADMb<>`nLigMQ{z+D(+R7W@LV}*i(ML=Y58xt;O;j%+`W=2s%<eU^s?Bf2@gd28Isb!$|'
    'L_e847?mL{2!`$Qe<)LDm8_T!Fr5hRkJVM$S>m_3Nd8JC8XTw@@jf*ws2$-nGHgrSXK3cMD3C;&K0#nyyN7ioYzkpKSBMsTncS>U'
    '-;i21P8{JuBZ;7Zb2wH%2%^K{CUj|$mZvP@hzIi;%mf6HOc<4iz-)?XhBGL;aq@;+{ei5RG#}K8g6SwPC4vJSG~i^EiZHh+lr?eK'
    '_HK3hd)Wcss6uGf&}$mSh|{2@)1ri5LNv#{i%A|R<z#afsoH3}w6|^KWxs@UZnkasR&bpFz<^e(Q!3dUZ-4?7q#ITjMU!UEXOUp0'
    '+cvWB6lz{fLsE(FLn0H$K}oaUJeq__CsUl91nRD-i)*9BPU{O>6k`MV0Dj2F0(wAavC-5(Sc}|UY=A~O{v(X5Fw*Uc=I2*`Dwn?M'
    'x`sCDD+nSKs{wRXEnHFUVO_JYL8D1wJdzQa;kLc3ZEa(e2;^);Hf*pVKypVL1escrB?jO0AYbox^tbKi%%!Q?2%IoTNnC1h!ND}_'
    '0s=2{)kgVf)0;Bl!>@iti|F){pI3@cK^G_#HJw!Bm0_Ctp%)ht=D6eL#e<8dGx)Ws;LA4b-*-|DtMZB@4PzY<Y!S1eujT<6@qRl='
    '74ULpuA94M7w7l#nD$ucl*pkBGKTkp!3l#m@J)irB_$bz8}ZA@Kcu8951III8<%i`dxu6jY<DHhg}FN1tu&-ag@V))+&3ItM*ko~'
    'f*yjHgEpSI>5;sB%PYt+^eXV|Ku3`q4Jsp^Qao8Bk0X;)3kSUcJ71l*FWdQnL|YA!!g-^Zq^KqbqG?7OFK{0+T!PCN?IrsQvK_i<'
    'J8zEWl-Q3ovZ+xN1W~uC=XzKGj7%Y*Q0}V&2P2}xO>58H^bK7YzO~QAXd;ShFwjE@K|7P{7zijz5J?ftp^>d`lh<C#f89Tl4AkLt'
    'SP4?kvKQG00>vOg(S%5}*RsrjTL+K}vubVL$lLL0!Ln87F&4U5Oz7$X5P}7R7Y|&JfGZioC#cwvp7D-=_QhD8$*$i>#7p%3VeqOR'
    'w~Nz2k^RFL(`#D6BoR9NN!}WSS@f%b67&Xx6lmkHc0>G^W8}G}3kL8&A_)UueMm?<+8D!Nc^oi?gQjU>h(o+tyODb0uts7#`o5yx'
    '6XtO2h5rVvX0b|waM_b!qefU8<-qAKF7ttD?vAMdg<U9&@D&SCN9cj@0+2>F8x~S4a!dt(wBsvxafRCZQ<=$4GwYV^1?bc47*%7;'
    'wB|cmT_XyVn@e8%p{Ty)^Ux&9(qslS;}P-_5hKZbRFg9ByVuw^EH_C>m>~``Z(56hTv)c7i}Y3QKZVi;(l%#tl0Oy*r4<1Y&Wh1s'
    'ZZH5$l+`MpS8n5?;(yysk)T5l!N6PVt@wuGV{oTnm_UZ&P*>9^1lR^o@78Yv2VLpA$q&zU*7dN3unpFpW=TSQl{Y&Knn45X`DS4+'
    'fzR>L4r@QoGY|PC6+(k&3_IOEnPN4}*CKAh1;+kq)Gf!m0KTIy8|_W2*Rh}{0j5ldZOJ?2q=;q4NGzad4mwE}l>JSl@N3`0Vq12$'
    'D5-(6Mb60_M4W%{ondAj8T+hFQR}su`U(A9w2jg()<q;Q3t%QGB;K&oTxC?js3<L*8L9(FY?QX}RZ6SAduO~~QkVHcg^@>2Y<oog'
    '*hV?JO7ya5NgMbnl7u0?54yX3_39NaaeUk`g5Xe&3|a=-(~Cz!!_$WpK47CkVwF>oo%5GjNPYBUuI2#Mp}|U@Bx&UHBJ=NQbi-)H'
    'kERtLdrU=}-%FVJ?B4y!JAw&+z%~);9dln=Zde3hK@;L>Dx+gXnNIh4nCe!n4s6&U;)G38j6MurM_e`$A3R27P;hbC2a#t9yTu>6'
    'e8Y7)U<aL>5iOIo%)p%?I->_#rf_h6A)hfEP9|=1)ryK)bxHyR?(oXEMLbwK*(OQfz)BdzYD5%lhL-kAUlb$%uxw4FU;s>#-{YV`'
    'KGY|81T!R6#~K6($vcc1P>-V3<PWRDNmd`aK!4^^bRy3iSxPdrjpKywi5SsnE)3R6%<d`HtUs(;c|)K{F&0lDC!Z`j%*X<I;9!*X'
    '*sL?+05pRUD@9!RUly*I;RII~dl{T$!=y>81MDFv84jeNr%;}F18DmJ5I$S_T#G;an6N*bO7rH)i^+mCq7$PEkfT;Jxxul5t^s_w'
    'iPJq@<xg)!YRbGnJgaAjEW|y1|Br(H2$+C5@)U9nk)Lj*2HP{~8mfa)&{&+`hR>~Re_ZdvniK+3GV#YXR4NmE{3pO{JoktS<i4aK'
    'B*}OStKQDIvaMM5g7=r#R!5S#j7gskIzrknvhDAg&5T1?PGHUKf`heo?Kg0{Vhi9L@Wi3vQ3cWWl0_<$H073nAUjEzku<6L(^E~='
    'bJ89jC=WAZY5)G)algCri@`tP<H9u3a1sQ4vwY?eF^YBu@P&>r!xQ~9$6=M<AZ0u(ZB9_OkB{+>cTbb0rh;9?Kr0|6yW9y(-e6!I'
    '6f4wjogmWBIr*9cdYP_$e9-XCzn}g*U7In~&LC#Acq2~`F#;tw>GU8oL;S(e6%jew&!udHz=yXV`LQ75CqoDlHKsB1>NHRxYG4mh'
    'sRx|F)s7g2<Unvlb8R*8sr7dc3)WufN}&~p<bmBZ^#YwrW*|b_qjI24*u!-PW56Z;)4J(MUiAQ<L%oGd;mV(EE`PFlH!ZlHzVsSk'
    '45bD8OT0uF&j!bV8I0sE;yM7qz{laAeYT1B-+NGB_D~LlsH>?6CV+Dzfe*<FzIh1uEkiA+*`3U&7_j%z2~x}Ti+A5Rr|<u<5On1z'
    '&+u3(0IDH}2ouTv2%`xXj6mc!65`IbVy*LV&C~zh|F874#Do9oPG1WcEEg;Md=hR7Az`szUuAU5Ks*8DyzTMhg7myPO_K2S;lj>9'
    'jJSU(%P+AYgeQWcRzabKkPtNe3cqOLJ<~W4BBFf#ko@`4nwP&87<I&U4YXr&6NBajbfZFJ9HXK=Q!LTg0>*rp7yh{9Im`dDFz5=?'
    'x0#v>XO0W5mCq64Mn}>DRSd0?{7n#~z&VX|>qU~_>j$=5z78ryyxO3r(Z0tM5DhmvPh?~G_BWz_d`L<AV7<pz<|r1PXE!@_MZp`n'
    'F3ALup}{(%`-j8=lM7-4+}XKqJq*%LrJ<vPMkQhR#}8t(Ih<vluf}vxK#~c{x>f^W!>6BQ*gl+%4vt^GZZqcQ;CAP^Z7=&mG{6ZC'
    'Nh-dI*v6t#2J@C593crz9!wFYGC>KnqGD;SRpvx6+Mbzk7<bDb6sry#76E0D=F+_CoD@u$rS>1{r~YNZ!vZ9ijIkvy43Li-`Ica&'
    'j2agjE@D{BVJX~T#WqM=npCmk>r0WDPifdeKnL`kMRlPqM_jjR?Xw9y6tE?ulA7FStHmUPZRpM4NpSi4k8<lOev?-2U&tUxeVB;~'
    'urhFWa<4%3?j<!x0nD2<t5#)f!nRN|dAYLFkw7xalH3}U;GJwVG@A)t2b1J_)1+0)7B8?M89#k1NYzQ)6{}nUQVmuD0Ij2#ahlp;'
    ')+~Ci#joEcsEq{s%gvYJ5PYz3Sg065(hwe#_`+MI&)IyoEWDwI<@0#>$15;L-kt|ESG-)(d1#opbp!Ou3q{VT@HJ4oP%+B6QaXq5'
    '`BVOE<r<m@!UbGyhzP`4Ecf7sVEjTFD4!H5Ua(!py{cXPtG|{46LwYP4pMV?Nh=4M*`!K{ZczEdO11nsGzs6YUASUyEq65B28e?Y'
    'Y@rllA0dG-q*HndJpb6x<)$(BX*i}C`kEdfz>vKx_KhzmSCT9A5S}?f+^PI(NLsBN1UT9}aBlD(7qmv+$8*)1<vWgc0d#8X_%+yr'
    '$vv6kP%|hgDVPGsEPE~>a^b4wYOXjSSNNDraADed#!i=b#kYk1fxZbyfTvG1;wm&%E_f<so>2Qx$Kvsi8b_}F%tGZ^;<%=-n5Rh}'
    'QDE$+NznykIOo_EIT3s3R^fu-4$rb7$J_*vgEF7^&tZWdLZxA=mV4p)rWh;?S7;Z#A2cmw@{H=0!$rg2GdBt&aD`tZ<J_rg#gE(p'
    'ev0$Vd71bH(6AW~2#606-v|b@;!;Y9n1w0(s>RNufC?liq*AknHDmfbz@z}p2E(Veg*kzy3?VKYwc*pR;S$&1{#rBFPo!xy7Q#|z'
    'ab~&1=}=(30Ln^HCcKxuxaspH$$z$rrw_|<Ilh^P6s%&*q}DcXj<y8Hgonrv=YL@!MBB(XhNC;KUbQ?911DYv3Lz&Zjn4w6$ZX;8'
    ';ERl)8crTG2vV63`!j{5Y3j#)&LtT=K^8AuG6m8<wZrK1J5k#wTFDMMpN#us{p!dB|2T?r`0`rdfHGu^NDHwKZ)uC)RirB9^+Nn3'
    'K@<7_;L(NpmCNBFBN`#sq~!yK4CAIrOdZEUo{H4N7-RMu*}cno#hR@1j}l)F6dn64Y`vIYjRTTqdO$EqSQNlK1;?Lcj?=7N^dcKS'
    '7P>OX4biRW#zv(fVU?l;4I(}zKp*@H&~Ef|{o=|PD#wU{JOZKML*#%$8L*06h^{b{6|$K@qu#*sAy2IMmcbtB44vFr*!5>2b>ViQ'
    '2*&ui7ifle-2mdiFg2nW?LUkI^j*6ZZ+rLhtd)<<PA$x`!|=y78r>!$9>coCLi4go<X(UVN1FlgfefmC?aOU+mev*6h{y{T9ek2|'
    'JHQr6V@oy7Ac$TsW1<BpQ=a<8_2--Sgne7$&i29rNTr~`@Og`b*<;UuGi9rS5C1jfb*4}C>&u@qKM`2og4@Hw()@A>ac_V6<t)zq'
    'a!D7q7qRNLuFb}PKf3b?au+nGR_Q$`D`BvMXp1*o!tH=J+K>PJ+y1NJT)FiDv>A;nXdWC3_(xt)A{Y%F5BSQsbx<;K*lRA4vkT@Y'
    '!Sp8^c``=&xdy~ruNMy{CZ3?}Kyog9uLfS>do|S@ajA^ZX)YayiaIRGX`And3KPtN*_?_mj=})(EZ-SMzAc|wO-!o>+vrzt7d4F0'
    'CGnEkHRXiHv5|?%FA(eLB#YZmYZ1-hOblSS9x(CcMeS!L*~aq-z(9f_2&y9-6$ouXR9?WuPb<u`o6v(7F~l8eeivS)bQ(b_!TX))'
    '?c|o~jg6Y{4Duv0J{^=#^Yi23(QisWYtWE%u|610qx+{-g5J=y;r;{sr^SqcL+U>Luq3#8ID_j6bKEa+o0s8<r){CbN#aVE2^Tap'
    'K602Op^-5dcB+C98171f2MpcTE?i9JG_FHDT23b>u}(plY2JA9NX!i1hsqJSWEyH0{HbQXUWWvYou2q<GiK%7ZlsP$qnCnYd839P'
    'aa2R~%0>8xA)Ff83$8?>2CW?T3m6wDY2XXsb1meF>N0$Kxi4$IS<ZZMOY@}QQVMU2+KK^f;?lR0WB}79p~FNST2v@D$Y(x3tUoVF'
    'Y<=r4UVX5=gh^S}BDj4lj6OuTGmUGwmLS3~$>bC3>lS@iAYcC~k#shiVh-Movy4dCGOYyb2Mou9Oqxo3o?P9U6;KQ465ThiQA)k&'
    'X&4zL`I^8vMv%ovi+0moIk!JAC<OXh(e8Q}r`0tmpwgk~G;U85Orb|n&SH8ef;=cp*YuTZE<ECz#v8ps=38@kFmXeRFiTWV8;aAz'
    '>*UVD^cEgdUb$|e?m%Op`AwYQgn}KwgFI~F_o5L&O+zDNrj8%hEeS_?TQCUH?0Mo443;c~3ioElKZynvB}vb1(yHS)uUz&mt0~|j'
    'gN91uyaG)f{tC=P8diu7F}()?lCvI!KVKOhiogh&K68pVqn&ygQd5HAW%=pSfa^664GNm^)vFZ=LjVM5SdDbOAkn~tLm+#E6b9cz'
    '{4Wi=VQ#Qpwc<yUdwz!8u@~2%9>xlSx^{5-8gVx%;uw`oU5ieSF*Bxa(Ie@n-(R0mNukQnz)AEn9pI&n0JmDyW+-90XZV8MoL8;5'
    'DWcAVAx0x5I9CDtQn=GH_2<-(=3=1(lm{$3e>|kJuxu4um0l{aHvTB2WALyzxT8}BgKCIrR2n&r>AP*`b;~cBivkOcdIMAdAQ5mv'
    'J!-&rIgJ8P5UfT8DgJa=x9(Zda6M51(8JTs2wZ1K5>5h;?!cc6X|DRdy`D$=d4~2+3omIX9L|d#sZgw9R25`-O2z=gkZ92+>5(Ot'
    'Mm0tyjlQq;RhPR~JirXI0wuiMEJ&x-WEQTErz?!4D4*&NBv1eKKmHGeh#Mp'
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
            'protected-producer-original-default-required-context-v1'}
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
        self.assertEqual(len(manifest['suites']),60)
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
            'protected-producer-original-default-required-context-v1'}]
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
            'protected-producer-original-default-required-context-v1'}
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
            if installed['name'] in prior_callers and path=='.github/workflows/repository-checks.yml':
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
                ('protected-producer-original-default-required-context-v1','7b0703d88d404f38c1b3dec92f77f03586c9144c')):
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
        spec=importlib.util.spec_from_file_location('affected_host_policy',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        selected=host.select(candidate,plan['paths'],True,trusted_tree=trusted,base_tree=base,target=target)
        self.assertEqual(selected['reason'],'protected-affected-dependencies')
        self.assertEqual(selected['suites'],plan['required'])
        self.assertTrue(selected['full_host'])
        self.assertEqual(selected['include_platform'],base['tests/platform-profile.json']!=inputs._AFFECTED_SHARED_PROFILE)
        self.assertFalse(selected['affected']['reusable'])

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
        # Apple retains two additional audio Python readers and a changed mute
        # caller. Their genuine import variant must keep this extra owner.
        if 'recorded-voice-qml' in plan['required']:
            self.assertEqual(plan['reasons']['recorded-voice-qml'],'unreviewed-import-or-missing-required-input')
            self.assertEqual(len(plan['required']),33)
        else:
            self.assertIn('recorded-voice-qml',plan['omitted'])
            self.assertEqual(plan['reasons']['recorded-voice-qml'],'unchanged-reviewed-dependencies')
            self.assertEqual(len(plan['required']),32)
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
        before=SimpleNamespace(entries=tuple(entry for entry in snapshot.entries if entry.path not in paths))
        self.assertEqual(len(before.entries)+len(paths),len(snapshot.entries))
        app=ios._boundary(before)
        own_host=host.ci_host_boundary(before)
        self.assertIsNotNone(app)
        self.assertIsNotNone(own_host)
        self.assertEqual(ios._boundary(snapshot),app)
        self.assertEqual(host.ci_host_boundary(snapshot),own_host)
        changed=SimpleNamespace(entries=tuple(ios.Entry(entry.path,entry.mode,entry.object_type,'f'*40)
            if entry.path in paths else entry for entry in snapshot.entries))
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
