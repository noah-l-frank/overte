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
# 1d09b43f46dd8dfb328e566151a6f5a7df1c2c8c / tree a53d4242c3ec2054950a8f83d88446e65daeccdc.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '4d32b13ac72d53a52e756b8bf3e4a7a05b2757bbca1b482318441905a8f87996'
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
    (
    (
    (
    (
    'c-qa~*>W6L(k1Hq^B8sAD8@YWQ?wmB_plhrlmH|OgCurazx(+-GC`45L`Fn{J^a@FOJeD-y)$BmZ};VEE&m_?_~+-t%a_;wQ}-}F'
    '9S`Hp@z00p>E`9Bdw8Cwr+@zTe0=!FfBhf-xId25KmO}K(j=*h;vfIzAJ1Pp|CnV->VL{KYld|2cS%~$^OX1FP*%y%q;rzbW19Lu'
    'c=`Gm{{{WsvH!>a{4d{@?JYEXxp_R^9fq$ftMz^EzpI+6wob-w8k(xEhki<uI+^pTACtMRiY{s1U+u9Qe(yd{H-8?VexL7-f8Kna'
    '{Mzp2aC~@PS$rD%q^iay8;hpM^C_u@w(YAtDd(xo(=HjNxh(u&zPtF-^mu$eyd0mt-V9%+;rF!_%b}>V*>kPaW**0Onx@tgb5e}0'
    'AKEruo)uGHyuaeh^!#%3{CaqqZpP_xdKjmN;V`YOJEoZ*QfB3x=jl}Uc|P}L+oaW;)NNDr-I#Q3-B(-IU0bW}hd%Awx^AnnD5qu~'
    '+Hz>~CK<A{>$<$H(za~M{{6MyUgfiw`!qeg-2CgcyF1K>VR@_n{Ca=){_1U0kIkHnY1>RilBH?aJ4t!gR9$J+Z1Q(QS{IvEe>(m)'
    '4KFwG+n+Bl>to5YuI##E80M)i`?M(2Vod8UZHFYSM(=#irgqD+|9Pk`FP+U(GFD^Wddtb&BuUb?X<m)>=*O2?lZ;K$7eD!6`zOnZ'
    '48z^QQ~op@KK(X5{C;?N{`9$v_x$+v{Z&2Kq3DMp>x-hO`>bfj$_uW`X)GJReJ-c8u9Ixfs*irT7k+u&Vy^S4=%%{K`(&syKW=XN'
    'e(b7#&T8kmNv3HS_N{yDFRwaxbDa!%QKz%tmnChNWO<$U#n4VoG1PN6bY+w8dd5$$4;R-Q(xMWb=C19FruOr?Hm?#NZJ$s5lof(k'
    'J<ap3HRB}T4qu**_tWk3aD2S{tDCY&5>K{snyR6hhN<n!ysHz3O6)3!u^pRq-?LtJ@X*~)&jR;!`!scrhlkG>w=p(FF%Q*LR)wfJ'
    'rNxw|ZB`WB&{s*7mPJveg{x}+HXiS9hvUP1xV*k^c&eJbtg0sMmTR%fv!v{+t|`YcOKeWeDe~Rx$Gtq>{`JS)UtGU;&XPj-E^C)W'
    'nRpUq*9xa@NGCG)6cYDyw|jjj&{cVH?P-|vrYo~iG@Emwy&lp&&6CcpHFR0pjCoNd8-9C4ls~(#pB|={h;+A4$JdwXc06>SACAv2'
    'hv9Ox$=jjt1oX5V%Bk@BMfa(5btYw1I)Y=LbyAjg_cmU~$BPSRO<ko^nvGNKgCE;?`gY<9na9kBF!xU4RM(pqJ{`RC>Puo4NAP9('
    '>*aC)Dt+wr)Ma^@H&T_@RN1=8%hA`^PD7fA57m0Oz3b$KFUR}Ca3k#fad>v4`T#$5ujAq6_I%^TEqn2cEX%1Y#;oh7DW65daV*-l'
    'D4K|gX;sF{@MP+%ce8wz@p0UBuX4%DQL3);Va&#=ExeCv?0RvtZL)Tr$2w2uG@TO3R&xDjUZs<lBjq@BX)|P%%%k+%yK=~CSA)+)'
    'x>q)H*^Nb>P3hHp_<eeMnC@<uw{&qQZPt4rV_glSG_RiJKyyE4Rhi1i=4z6cIltL_^-k`)2kG{BE5~<~pT6FHIXp+Ma&cElTwK*$'
    'G<`A+!bm-pE;F~NTp`WvFsTbq>H1wAd;iiOE5WQ9qH-C^UbHOwtgfBjE>FgMX!6Mk6343ePp{v_<GJ$a?v}6msT*D{2ewA(k=2Ey'
    'G@GTUZBmwbJ&a9PWsY@LB<(0;?c1xjB&VA14xhigY>u^6ozF6=q$|qa)iU|c(<ZGO@h2Y8m?vtsx$Zx(rL}a+11Oc6YLh(4tE@@0'
    '$hu@%9!cx%B~9Kmc{X0X1!>19*d6}xVc&jxM3=JwXGJa1&gwVMAaCkM-0v&FckWfmb2^AW$@P!r`Nem2`LMK(MjcD{>ZxIH3C*o@'
    'J9tpFa<Z<=ye&WQ6}@y%pQp{Yz%1cSx?z-k%#|}T`LNTXE*+9Oo=_z}Xp`ysw{*%@->!oG`1&w*D}lx_X&oHtx!01wF1ku-RF&0G'
    'WNBX&Ntdb<is={aX~XrDPqTU#tkC8~KDA>xB>k)$Or7Lrbc`e740H0q9W8g%?WQm|l=Am1bz!;~n{4X3aq1f<Tb0x0d0v+NEY14h'
    'dz&8qI6NI6?){6WS9iIr%L3<V;Y@ko_vKKzBKoeHin^M*rq4VxH~N@=Y)_kS(WWcvE>~65RX;T_nz2ybO2Cwtz1+9*!P`;s>$Y=y'
    'kOY1{-5x8MVBa?m)L3UjA`tgpR^LLd8ka@xPV1)`pjCZrYggU!eGSl(5If^@TTil(A?n1Y&C)?GQp`o(jqUJ@wl*B^7o246fmL%i'
    '<*h`%Xj6eQ-e)6e7QXGa8q<Du&o=q^Yj*WK{V_ePRMkq>b|~WoDk24d#Pe#B)b)|&6HrbdRc3!|Kbs<f^ss32fEdPUZilw&+_+s*'
    '`S=HbY+8AtsWSJ2Tlp?4x<70=<1LK23xFY?ay3^y4iL3A?K_Zx-9g%>bnJ@xWBb~l8hLM>oDmLE_Ibcua{`A*tE_OutGvnVut?_q'
    'qx+H{-40I^Z1?5R-94|M14^!<$Xv8d+e_Q#*~5yQAnhf)X+FRJRjwc2)0UJVclkRw{s&srrEpe-R{_$8+~iHAKux=P%(9Pd=8Ei1'
    '4%yFXl~$E6OxfI(v+Tbv=OUfD)RmLD2h(i$*v6iZuTMa&;rL~OTMw7BIqQvyqNwv^0%e=VfX4HpjS>K8K6+>ai0Ok{imdW>LkSCE'
    'lCJ^#vbt26=?{1)P?s^!$_ef%JT*y^7QbRUb9cCVT>*NVq8X-cD!Zg8yFtUGmfLo6mLc<)hCFXt4V3hQ=lbRTaX#El->S9CpMUMr'
    'ukucH1`ZN2E3k~m(#v;~fMj)cva<T%>3(^7eSUG1{62ksT7yP?^YTmIchOI&Gu?Ve+AZ?jK6R)xUy8ArK2j0v*i2;ENuJg)(X7?>'
    'nK~U09j~HKd|^Xh<Yfzs*mnJ&LF)5=a{0Cxb7-Jr0UfPN_l1H!k;#^6UrJ<Qv}H3i&9)5t^Xn4srl<SE^YhX}yqJvjZL1#<jgGmQ'
    '`Vpp~S*lFzi>@xFW=OhG%-QynzZ~Q3ACGGRKQ3tXM5AL@428CACbX%~8#nlvq$4=aXR>Y0Q`&Mlbn0MbKD=D}V~i{c@I9pfF0je$'
    '&Kc9(9>#6?(}T<ZkLk7>?+=%65}ggnhxnKFSykzNKqba`=ybOHzZ}3-C>S;t1m{(^fQd=s5?7W*fm9FEP$}#SUpy2f;G;pgCJbyl'
    'OW%J<n{$jogEs3G`Rc={T6KW5QME2LHJd!i#=Zr@Z>$%;@Aqu^l<HA!QRL&8L;1_Phys6VWzV@!*|AnjtIfuG$Kt2LbT~dux4*d_'
    'AEwJSM1)qsOrN9BKCY{(hBCKFRPL>2RHaVshIu1K_x%p;kAF-{G3p9hxe9gu%UWAC>6^R@7*|>&>5RJ(F4n5rYmJAt+rEc=QDqoB'
    '@g(<ICt6>*Mwfo_jF8az(k2(sgeow!{r2@YhL&`k)s9UUwKg23ZhUcpxcS5zA7ar6@AB?^`@*OAvf-JlfxLIk+|2crrM|*OF5Tyv'
    'tC<@YKnyz3|J=Lu-zDtjJ47Qpk@j>_*T6#ROlIGB@Bsb9>rUY$60-UF<<H%|;qmqIbMW1zLzDSaZyhZ}o#7^{pv3Mu{e-60Xlbw5'
    '$hP(KxzyxLWqq2Rk}p~6?0d*Ff6#Q$g(~aEWd9M6urFK=pF;O^84K!rH)$4KR=3I^<dvm84O3P+gp=Ud$TY^Wzj_PXo<!~WTQAY{'
    '?vM>ef5kTN@H_SK<Yt##mGX=$w(<4l%kg0wpc#i>kpR^3J*b~hgr>6AL@59(dQ7Tg&#SoNVLVNrVLA$x@%GQB?(uOg%NqJb`8zul'
    'LP20)F2}y?^n_L9Q>r!)8M-SD24LxO6Sk_<X_dvKb7K*$MbO}^+m`haB7>n;YLg7xm)@Qbv~|~Zd5}wH&4_747*o{Byd(!>+3PX}'
    '1!mrHA6=Cd=r5F--j(O?C-+!!x}8H8P+(^#xO2l$<r}J@(=Wd{JUqU>eDc=s&aA2%8UD?mlf)aWrXsqy8@;-yQoZ%%{0%aDr6Oo8'
    '01<Ha?6G9!hAioa-B|r*8iV-s{l=p7xb0rz(X9hVohnh9rUuDykUFPg@bxN7>O$?IPdvq`-2jfhx3M+S&g=__{K;d<0&8%Ej`(P*'
    'k6P=q?2*It^EOasmdpB$+<19OshYDH*{No)h!7p{UM*HnO%JXvJ3NuPn>Q}`28~6my!9Tsr~Bj6?W=!pC2J`&AA&nl#|0iXR6~@1'
    'pjM2$G@a4JQpKn+zI7j`%Jb&TmH71hH2j|?kF0O(e;b|T{jHohB~f54ndS<fDZOnPyg{!B_q335brn1VQ11KnY&w+Ry7|C%-T;JU'
    'TbHxmqOUVl!eJ0og;d|Knxnv<n5Dz^A^DsUj;`FyLgGA~Ze-H#dGqlZE8nX$aLPbY+2l4JuuQx)wRbm`{z#TsZJ=MR?yG-2+>Iyv'
    'XDi?;vNec6S=V9!=}{%4AW+wJARsU@?Up?Fnd!$jcgF0#du%H_6rWu@FCk&T*M!t1(GAvQz{shxU_7K#TYP+D2W_CIx0iY*onJ;4'
    '^r<rJxkk4<#mgDf=yv29#u+{xej&nn+O)r5XAkbIJ57)7NvrSjDVs#-9u}=@E!Bgai=Nv2Af+BPM$M~jj5J+-d{?KWM~wKcLwosB'
    '?K>o|8o21)B?8sxgB)8&&56Udg$h9ZoBrcl+Y`G+d4{v^;N#DW-&v#SkKh!cR0BD>9_qF37krlIbp3F@RI;!A<CpGvg&mDFSqbyD'
    'H>hI+O^_jV0AmCIC9Vrc`(fyR!5KSUg`42(TAx#tfb9$!0I_Zs$aJ3iA*r$<NNSk}mrNhu)bru<!j3qQf~b5qe3T_%(PgOU185gO'
    '+-B~Z#>b#_HAr+lF!<{9zhG}mrn8~#-b^$F(OyG-ZJj;Uu!?Acg_cT0Y@}&~KL3J`;7tf{c{{WIF%~FDR%!zpYQREOR;dfxG7Ugl'
    'ztoLz<#yio@M+&wso!r=y}x|y1FmY^OgPGj5~y1})B<Xo)>ps9Z@XG9$`#g4Kv&4w?!!);Dtw9(Z#WiQx6kqrDj+t0`1zbe{AEZd'
    '&oaf5E60V53ISooXA$E;2%<V#c?<0<%8%}4!)KOZ)C8#yC8LHi;_d3R_wr%t2I%I{$wu|F>kn_`TtEEyv8_aaB+8|^);Z~V5PO~{'
    '^@#L8`?si;;?L1El8<g}$CiMC03T5iU#pN%^+8&d|D_on)0j?u9q@Q^p_&{IPaz;W?`+DZw^qag$acfaIu<<Z=FG{U8>+NzhBor4'
    'Hi1A?IZPZ*uB_?me9s=%ida>eA|z|dT6v%#pvcRE%dD+5l42+*>y#F7^Y7l+XwvUZs2Pe`FCJYeCpu}>@W>WYHU#Qa7b0zcb~s&s'
    '-NU?wT1=S+KN43LMX}yLG|>+uTB1&q<DgSjUi8lxoa1p&i_0>*yHB^M`rk>kZsR{&>DO7-0nRaf<35{u_*F?!;&c^N-Um}Wue<5;'
    'vOzh#jLEd)jCQUs&`c5`s!9x66?Y%n6=x<F@bt3s%gdY+p5^aXdcAGlmjSc%b6Hmz${;ONt!T@2sUrGML^D5=P6qrnJp?NLse5`k'
    'P)<pd7pBY03Wr>FK4RWMgIy)$I7vF_6_t?|2dy%jwTraNE-ty86p6WiUZu08Q4473Bm53HQVBjQnWXSJDcqZ(q;C`hes;(H$ATwf'
    '$mMg=1+rJ>36>hbx7KE?5TKm+yj2a9r@DAp`F+p*@&5J?xAwT6(tt5rHFfFJ29Ch^QNLg{bBAb+WhgTo`?395^ZJynjME>7c#G=0'
    '$Cp@rOQM&AI020$081bI6pJ-fUCMlyWRL%zjGCU^+M;9k_!8QgCBpp2ik{xz&(%{)yhhxp28!Evx=i}lumoYWuG6uBoMN|cTk-ju'
    's`^n;@a>N;2evFaszcH^x_TN!JIE^_^wbV&4B$j#CGUss${jpD9$xQnw`^nxwzh84R4;AZd?Gg<#qvnbBG#h?qcC*k&W&t(2>3FU'
    '_F6CA7C{uPfdLtEg#4q+s(xrXY6nuoy=xE0JNL`+l)|5BkLzbYF9NymsoC1zr|pKxG%vvG!Q>-I(PM68`QzT*EP(Ot=SjnTt>uX5'
    'g<|Ym(9IXtipa+>8j5DB=C-II$uKxo+2$=Q=U~&jKq(l}&1L~DsAeVkJLOUp<N{EG(!Pt%XSVrW{NM2obS~~!mPE2`q!k#633;vG'
    'IYt1ig<9=&RdJ17p!J$>U2>eBf7iXbJr1vThrc#Gd$4LOt#1W7siZt;JW6q$leR!F$7MoblAT<+h0l+#w_orh@22M!SW{1NR6H_z'
    '&@R#JPYb31uCpqS-dcuZ=WR^MFW3iCwCf$!eT8SFMI$O8j^U72^BirzF-oT3A{6B0)HQjY{+bOf0MmwMbb#Sy=r(ft{bAJkrIz3i'
    'K?sgX8d~$<UFFr4yK-?qVMaV3e)o@W|8z0&QU#%=w1pg~m6`yVY8_dM%(2n!8bcPXg^*pjpA!PneZ3RVqDGny?_IG!LaGVkuk0w9'
    'tFnyle2GFbvGFJ(f3LOd)10Nom7ChVpET<Qj)8V0Yg)Ag77dkzXEv(Ah15avo&VHT<mdajKMucd`nbC$dN_*eIuFkW`Wh{jG=%)2'
    'iJF78AoHJxtqY&4#s2UxuCXsws-X-M%!ZUM-5Es!MOYfEz|K;^l?ZjHHh<5Lhv8U!nh$@y1nR$lpO@oWXm%uY@(8`hD2szGAe{`<'
    '19Geek#*F~zV-j6Ol`hal<8g2O*N0O#-dNHUM_M}B3vT9(K^_DfU<oXc?zqQr|p{{V^Ru*jgEpAMA!Ae)iApui6N3nnXWjbo1cdN'
    ')*x!^xZ{gRsm4$t1HsxJg~+8U{d7LbD&`57VCa;jSMK1H?`(b^q3BTM2FyhStcceKM;wt8b7vuj%L}BIrr3Pf|8ew>w~M7wRI4k|'
    'Nm`ZY-sK`d9~8DEQhtjHOX#E&IKe7hU%TJ9VC&;|=+Lz)+CBsl*cv#L15Y8*onWCZ42qkz1qo)p{`YB<^h(bi$`BvC>&lCs+t4^='
    'Fo((wFVjn**ZL1@OD<Bhx4L{qC)|dDqSYf#C;k2+nJ}h!0)&}Uqk-!$1BTLCz}cpg)_H<Er2u!_iYz+Ts&677S<3)_FHhR-q1d|E'
    '@=K5Bc5wXd?dji;8Qg7Xy9Q|L=#DCOHW)SHOBett*FAjPB!?|S_!yIGwsUxh#xKrA|H^mk>Gtupf8)Yj-jk5;@&)2TC%|_DuxHe{'
    'YnqzshQ1Pv*W>1YXiuSTqnDcQTuW=rHKrw@MX10FpgXYCfX>Y)i25E(lb69>>wad5v|~TtwQr;c^Yn7KzkE%(12Nd?N0hzP!EsxW'
    '0Qx#~e0@NnF_Zs}-8H+q^K^83r?t@REhN#TA5!%lBOebc#S&74XvKx#4qyQfNw3+%{n8H9l33eA2FHTFKzIO5(noln3)`6~+t`m-'
    'jP~1)*X$weeeB_B-0&<WH&Y&pC$48s3b-9R2Iqt&0x82-kuv}!hWeU)XpKfS{`jf~zv*zOxm%SmrGZZy#SpVm%Fo%uj<k!KIc}}0'
    'z3Ol*V9o96-a38Rm)}p~Zm!gWvRCY_K0q>1F3u8400!U?r)IkD>w(Q5p8x>o-TdqRZiQ4QnISJhKy;rl1XAx5{J&IbNJ~P#+f>m$'
    '{(`N<pIycbSgcgFe)Y6)%J>m^EMg2|EarGUwSjXtV|D#rf|dE)IV>yaO`w?2?=&<iL?N&(Zwh=XpOMitd`-|xrs<lEJa_kxG-=Pl'
    '4?eZ_*NFT60iGD9g^uSi^_gscR`F<|^(9guMzupTT^0LZLYY2pr~rznIlxA>o_OtO=&$HQbbtg*-2%!1p@#wX*KFc+Jcc`k*yTOo'
    'kA+NRgdI611aKkXuOYu6AI);$I^JEq{j(XqbT4l*n(k%wTM3>pBs)0Dy30~+xC)@#&4P^T`wf#ob~oF@**BBNvvm{*_sa@GfRF&-'
    'n)G{We5+_1Xjft{khHLA@;CxgX|@Nk6AAWoyBzyaOKPSDQLTGiNs>@M(YB?ZTJGi0=+yAMkQzk;RZLZr=VibBTa6e#d>!tlbKW)#'
    'zL3b@UcM}D0C&@RT^2fIl!Ph~x?Fbpi9k?ffw+B;IP?M`18Mh*_O!v+3u%Op9ua;x8w#_e{{z^oh(B#r&;TC{!{(Q4XgqM;ds$(;'
    'XC&-{UYbU4A2wfA5Uqw;_`n`=w6Lz`DC2&~j-IA}y{^T4Wac<J;Zmwi0)>-Qas={0716$JNNx#Ziu$7)x;uV8JZ!>RDs3`X;1m}$'
    't4k*vT3yKggDuOR(hXSz=jEe2f_^-QM&n_aHXSDDMj*ILA5pi|8*9@_p`wS_kCKQGFuRpL{G>D-zp19z_T>F|J8BXwr&=J?Wzz8p'
    ';$;#U9)9mErI^N#?&*1YaZ`PU?LKsm&tHx!yCT{xa0MZ|`khrcs>E9y<(fq>EXE*+qiFxKUA;cu9lOg=^BgF=0-lv9HZLC#r3hlq'
    'jQFe*9Y{SwQ&D9f-P6nQ_vztGo4uTD!El2WJE&K>QZ`O_C>o*TkUzCK!Fv|l>#yF>I6eg$|1?eUZ#=AW1YKLoM(P)o7ib>dX%lvK'
    '%tCM)n<8_?qODxJ9sfZzDsI2LygY6SOhTf*X}0hxcr^$H1=c4*g8K!>k_%PEyEUyox}oRc>F~Ja>etokD|Vrfh*Et?qbm6W!tx4L'
    'esc#26{(W*0~=bWnd*_G;Xt6G95b1*N>+8v9)U!QZ=}nGh^p+b{@};seJ4&Y*T>&p-<RWc>YR3zF<7{f6D=4yVI}Sj`m2PA%|sYG'
    'eQ-;6hmhKCK<kt#O)*h5_rf2A3>0gG3^P(|GO1z{Y90}(_!aw6)l7#qBcO1w8%tQ83qmGB+J=1<9~u)G1hXs}f?B7^2R9UQCjN4p'
    'A~bOyrUZgd;+uxqD!0I!_&$j8;hr|is$muRwOcwdj=p_k-zm;6zq&G9%J`adDjPd#G)-t7eS1X??~R_!OLdz3s%^zzQ5iQ_vPwz3'
    'ws5lI;e?rtwK&v}K)zs&w+or1<j$L4w6A&H-X@%)Cy1ly7+RtNS2@h?W!{K5VkI=PrltAdhT>M;U}epiCBo5+^$HDjpd0OoHhOW&'
    'RP-FAq-YPNAKcA}<@n^Id%=KQRaRiRA{<IJ3QATw0n)29c-^W+4s&6h#Nh(d^n<%P-yg3J8y}XAEnHT9>u&FquqAa<gC`O=4+tJZ'
    'ADqCZ^xAEGKE51-Q!e2??`<X9Mr04c>y%Mn7r}Bws6?RX6#!a`HKH8G=+)6XkcHsm25fox8|!&*$oPe3jn<%6YOK24d}@j&V6yh6'
    '#`k>fM(&Q|VrO+SkGhQb6yZcptA|3;E*b!r23nn(NZT8>%l;-J_XqY8#nAaBox}I0s|4(j2BxieMb$LNBM(F_(}?h@!k?^GB&kk5'
    'wy{M-JuY9`a9nLgM1m$gM3~@b+oAvuK`h6(BPvwHMJsdxhpyez85a5bF|BXO5DXQp`4AzAgOV^@n1i~jFY73ak#VTg>kAO8vfDeq'
    'zm4EXA%zXok$~+qCpg=4YOaH7OMZ`;hUyz+^Q+U6hhsF30?ng;_r%s1zp48S?|%rc;<N}Af>SVsVc`I-Nkh)W3+L+k<GAFIr*a5q'
    '_H`vHQq(YFKqO7Wm`s$$9}ff~8jn*<X&8Wy)73XDXfckpnqSD?hSY$py0A(P{kKTK9Y@nY{(xd{-~m-QWc4(EWJhOfh})Mh;ktKu'
    'JIsKS=u=o$vKTIDt@U;NFioT9g&jlDcy(%YF3HqEq9elLI_V&^xxRJmdze)#;ih14bjZCk-GfXvS!-%seUB|S>A3Cg$lUDO0?gVt'
    '=F4B@ia=^DdEIQ*S~_3MPRL%a-^+5xlXh(V+KCbiIlgzJDl7)r2mf)R50y2orw)ev!@Q5`gFE`;euKeBc!xk;41O}82Tt9{p)s|q'
    'o~?9@TNx$R-Eegt^hXnk>mPxpt)=&dKLOF&fUNTvdtvD&>>=G*QC-IjB~s?@13Q`i3ch?atT)?^TD+~>FnH+khDPL)s16O?akKhY'
    '2^9urcOTi*VR<^!*2mPQ<l95IA|uwIwuA>B#ubaWA`D_+AYsUow;$WlaYH?3+)rd>!Q3^8#LOeS9)KAYK^PU`n@2>fuZKKiCoh39'
    '9G_MwheagodAK^%$lJU#$sWb$X_B{QQ5nu50sO!|&Sb!0O>c;1hgr<042I7#h=uQ<`NKXgAHx*ICr?S+PaoOJw|hziT*-3=6*FT>'
    '2nUpxjHODL=J2f)2%QpDz1!R;{wp@K-W>#hg<6PS-B(=)0;63?wF>?LGSK%;JVB=Z1DgqX;fi)jC=2;Zxa+a?EAueh8)6ciR2e%)'
    '0@m>$=!cK&;w9WVZ-d0OibW}hqa~_YEuE5(+K;ZWa0jsqq9n*n#q*Ka`z?o<a6)MOSInOHYp~igRtp#1JU;#;>MYl$;!ma{K>MTl'
    '>NM-`-1By6Y_16TxnR>Hg5HtKV5eSG%ze_fP;xrSK%a1@zvhzkU_vtiOF40DSHy2xZ`=oq7>d}37aOKA{K*yRTgKCYILolM=T?t*'
    'ta#oG4wk=P?QP2>yD+C1<xQYVt-&(9(RvkCE3r$WA;!XZJLLhN^dy1(u|M$!qHH#3!SU8e!n}i~6gAc*I1`Hr9gal{jc%sVQ0{;$'
    '-r3huB5d9j8T=40i#0I!NK#^*T~;2fVY4u@({OG*z`D44SLf!**8NC@L6kk&g3dsE=bCSr2{`(Ml`bjG41>PX^y>Y5&!XJADM??9'
    '8;$A-MOoJ%JO)FW9v{7K7}TDf&5m^Ir<;oZZ2O*;);A6Sc{lpF#1wD{^GYH#lBkQ+Nl?p^Yxgufb<bbeLOvW{x^?|GSP6Hg4Gjg$'
    '4)`e&dDy?2TFQjTOrEeK&35qP{%tpB%wqd+Aa5)NmBwIHZo^gBUY8k>IPVo+<`B(7v2}F}_z`y6xT&xe8nGt`>hS(!QW{JA#4IJW'
    'ZdRf)Ws>A>96z?HsD?M&_3>HB=aXrm<T#AMjp<|QlPHqwz`;W|lvmg8=o^x<c|(j{vwk2vEvL9wV~kT`K$={T1QC<ae=bYD`n|=&'
    '>7I4Fcf?2aZYDca3zy+%U|gy6OTSc}S~BQYtGid)Yj<=mKjl-epJQ0S3KS1z!eux6D%?w0&>$zzF^V^j##g1<BC#TrtUkP*Q#<Fl'
    '{d&`T3)fAD3GOt<H5bE*iy*+qj2xKVgp1NoAKcl}8`!$1m^E02!b@+C&_PC~wSuys8Z814mq|ADPsjD_+SBuw*Oy2bx8EnAQvoRr'
    'yH?b$oXe7CkDC{9hzd%vLGz(_-Mp{!MwX-f{1!2X*TqQs1#dwLcetFKxV<JYi#o_4Gi!4VMK>Y5)prKI6mxjTwe3fCbnJhVG^tXB'
    'P2A##am5HD43+3y>Cu?;<GzL8m{1N68$$z2eC%%7lQ8{cPe1(8YHDess5jMwi9IJH1{shRPD}WbjA|CQUr!N*b^DGcw%^lDwBqHG'
    '|DIo7Mx#_fD3l3MA#^<QkvT#FWUK*x_i_EP?)a(Y%6pqR_q)$e=KN3Rdj9fOLO(aV%gm!PbuK8RMt~MfStKABIQq}1wL9p}?`&l?'
    '^>;x)STL(Y=c7(G;#(6HF+W(~S@^7B>=)a=tCy|^QJx9L%ijmN_j!fc8sj5)EqWSNIOCz=LB!@D1TYB00n%2EX-Xg2#oCh)QOqF-'
    'w>d|XxNeGZX;};^VGzme6*ZAhPO?3XJ{`@6LwvyWbkMiE?(0IjUeTBZk2nT!Gn6ZX(yL;w;7-U1N@&1)sdnE%hC1zol&^a_Tiu;h'
    'By06CxfcRvL=k|-9F8zBZ3HOIef&9e@5B_TdEYizbKgF7kp<p<j=!$;(ZlqXqGpU#nOPH|1mfD91YT=sfc}gz)v}*v|1SLZk1JMe'
    ';Vn|fTmYP1zy)SVA23B5R}KCw*{@DRS5^BKKfQuD2AkdkRt21q2_4cRYZKn2+EG~Gc#Is>Lz`;|VX;FWca~X&e&$@$t!sIZVhN3z'
    'VPn7cre$J!Yl{yO7j>>b#ePR1Ec<<%IK!TA2Vup5PN6*o@*76aMu*Hn%TsXkl?l2PP#Sk2ZFZhVeJ4&&+oXYMOh*~D;!y5*W~pNl'
    'sPky@@}BXIYHD-?!=`;ZKq%>!iIdy;0mR10fI_n`G7J^<-rem)D&k}em|*PxQ`5PN+gKzi>r#+D4gCQZ3qqYLt_cKWHMQUk1Idl}'
    ';C(sH<<8e|4$<E|f=w1`yeyK?hBh%-H^QS4ZHurB=7F*q{AgUHe&-v})9QuF_(E5frvXRhXZ;lw7LX3mVdj?(?GTh2w<*&LZe9D9'
    'e?7?bUS3uXBQ2X>$1^_eOE8#zQA!WWxdMeHNWDV<cKNt_?dLxaYu)LXkQ*dWWkD!o*+T?lH>NVF^q7r+zSGb`Z(cjx=})w#`>-yF'
    'xdl_d#dE4)vXo)I2D&bR0dN<(GhJ{V0Yfae)0m-9W*^+isy4_ZH6{Q}hJhO%<eYS4A}q>~u~Ccn7A4tS^!v9FtDm`E8>tnB{InEO'
    ')QvIW8Dzux&V3O^31I=22fhq>+VOHi5_A(h?yo<j5`6L|(QAR2SNU-K{(K)zY%2c0jAo2UVyL<TsjmjliBh*JuHV&f$HStlSTr8D'
    '^Ii9O#g;i*&syZc9vVX_5N=6v(Wg|xa<8z1F$62Sen%%=D7J?(_w(A69F}@>3|8jyCuBjEc#6%TfC<vKu3F4wF!sH@emhu;M+)Ne'
    '+cSG%enM?nfpT>8!X+=yLubNAOn1*^XAWBv<1#|UTJk1YE10GL*q2dFo%YpVD`TQ~SL6{ubMl~?$BH+C%;C(S=RlK^n6a9z!J^Y&'
    '>cpiNzsZ6yl-YqZE*)o<hdibQ*re{3Y}>K|Ec7GaysFP)C7bXSj{T6v1f($(jCok#r@@PIm-<ST%zXRTO7(M#>EDdHxOM)%W@s}9'
    'H8xTS&WBI}RLqR8#At{nVF7lA8P;e|>BjX>X!D9eU`$ul*aE_}fRS*wSI_W<8lzL;v6EO$$-HsJvqIoaO}nMnW*UNwz$Haz!Yq*1'
    'EUzMaq&thQ&5$kqrqx{fZ3o9EvJI%;>eR711`8;tV_tI1-lU$yeJ>ZG0v93UsEoi}&Dg#z`{yZLJW7++?8<r2>1Y}~VN!t3D<`@>'
    '*!IC3&{>=$Y)0N<zHVHaBZDvL??)d@&Ew^l&iSATB2<j~9zqI{hY22~2&@y+1UjXt9`|iv5%R1IyFzusjo{PL#Xyh%Qj2h%8^fb8'
    '#SSnOJxjJe@@3-k3K5l#Q8^Zat-yeS6yMDlI;M|e3nfvAsjsV|hQl!s(+JdmJr1`ouMcb9YN5JuXF+Qb%gMN=7}7~2Z98nsW5g77'
    '(6B0djdd4fEuQZBI5`=9xkw~J88OF53i&9sY6z)1x)Af*m|m1@S@r9~Ky)w)T^sFbf=`D4IABMq$eNg_Z9T24_?VSNHQVh>a=c;j'
    'v!Ck8p5S)feB2G>M$qT!Vq$d`$QX*RPe=zZozVcbVnV2~Woe-9{B_?iw@Ml4X=37$%L6<$OY-=ho7+YGxxD_WShW}VZF=~fz4<4s'
    '8aRw=W5p-W%nTzeVh$Ag(G-Jdhsf~x5FogWW@!45S0znvi=O6$$H>S&IBE0Y^GexY##9|}AZj_xhsZ+?ApM9`J3=Qp1IvwJ<LYnr'
    '<!>{lr9z*lm8Z^oe{prBc3mDZT`)9^Z+02(j!-)BlUlIdxP^ttdAMk73y|e&k6@2<+y$XaB%{tyRp8%EPF@nl$*TPDZN+n|bJNS_'
    '%&5^rq!y#0VSJwV6tD(r4BH`=d#p`=>i+!x$~)h9O8X$=1aJ`+%*$9*tX?-oS4O5%&3J*FTbeyv*zn9LE4Ugs$kUQzx-#gT6ac|q'
    'Wl>d_;XQ=k-^#N0#));C&C^thUaf1f;7{OhI2mU2R5Bu+uCVIVL!C8E*A_jFuVE|l`uJ1j@Ap5m6*HuGGA-6|dS_+;&%wotWDsE*'
    '$1-M3uU5>b6`vQ2=;uv!DPv8|s4Va@jRs>8Qaqm8d&Z?fE;3R&da`xDb>YWQ@*2^wqIA|Y2&O<AeT^zyhma&?0uFLa)F3V*^y$)7'
    'mc_SamrnSq;G2I9)Lzd3c}cXSPz$t9GNOX1yMQLhzo%7B__tLTvdbpF81`^D`t=kVCW@H34ku>pRRl@)4%!H8Sb2w)8&{69;;_!G'
    'uEHO|AGJ7zC@YyvFVZ0<zu}AN6XyDxrtQ{67aq-<*oL|-<Up&>T=u0_li9HV!?`qv1AC5Qo0?NmU2|<vL#C@ly0=Z7=`(7_HHB>v'
    'z@J+Z_DaA)tf_OZeP2Z{-=O38`HIPM-?|GPt5|+qQTH}lGB{pr7n_LPVGZPfF^jE33>7Xh60~vS+Ha~tDcR*^U4%vs#pF^wOTRvN'
    'C!tj#aWsyPE+Zuj8=H;G&Uar|9J9<lglWUr1!U-+9H(Nbto<+P?Ws_Sb72J=mphD$1ylF?#Xva&)V1+rXm%2KgdR&1C29lM^|ZUN'
    'o0S4?Jx-^F%fs}lT)dpo!_%Q*U`*{_6*IrT@JpuNHYOW)MoA&XZo91u|Mq%+`3#j|YZ$YysnpZZBJi6e=&d5J4Fg7AWHG;`+PL0n'
    '2-)rPJp|(71J=dqLi!nc$DE;4Wgc)F;wC9^3W|%kAqAMXuKPy6U4OMHl3f4+j4TC9hlnx;)}n$DA%nKgs@;r>VfV@#Bb859=LG9u'
    '@}mnWMi`am+TTVRVcL>&Q#H=3e%RmEKOTQy>0>U<S{FPk`Zn}8J<&8@4K}ryVZr$|+N0PSC1T$CiXzHK6AsA)*)Bd}H9mW80C2cS'
    'A%#_)<6Re9*L%HtIV^KZFPDWzFNFtf(DFjS3s!5Rg&*@bf$@x+wQI7?=jm<m=iFI-oAMK&Ei_Hx3muShjDo@>FiVBY9&aufgsK_r'
    'vvCLCIV5jd-Z&%a4KE&qUv8@5M;izpFwgBb1q!1lW)j23<<GvzoYn7MzO0}DA@<-&%TbX|Mpu$mlKND9)`#P|Um~)Ts%%{Nc>pi1'
    'fJ!iXckPITIfNG~&&wiU2ju|<mI^h(W}WX@&@*2BaPbbJ!-c)bP~W$s)n<587vBED7D*kP&2`vrUN@Lju)GZbHP|rJy2@ctbR7sp'
    'I1P(n94g45sIe{GS6id>H}|6NjHoXEbZUs9s$-UiPuWQ()Q66PPMvW_oij!_!EU{SPna!`{41X0?<*O+V92j5xLKfwm{%pIG_QOX'
    'WNasRll&jH=F;bW%#vSCE3(%j3<c#LRXF}>SgF0k&UGPZ5)q1`3dU(`$#QCPU;eG0DSObF>yU{^YR<r^jp396c({>o0D#JB+_mB@'
    '&dkO85CY3rk%M_m=QXmzWnp<t*(@r5W_p#z9eLTlRZkhu;rX~h&ud5!^|zmxg><S8Mo;twS{0PbBr+3MbC+-a-K@(_>tD`%xZf!O'
    'xs;K9`k<DtY7ubI_i5ZZ;-+T~Tf@lf;{qkVJ_ey>r6Yit?Xj{a4ktcIPU*{5E9iejj|7rBM{L=8Q=B|Bx0MXOQggj>G_obT9Fd_J'
    'ZHz%@3Adu$;5$y1?bdSTWEdGnqEFohcWu*=f<^2c$1H(`DDG~qVm3*LFw%vVIj&^}RDlnFJ)Pe0r(1tzZGO8#nrVZ(r`=4iSk=%5'
    'X0B|!>KMrq<&qkPdNAFy@Y|%S^T?6QN39I2ZoYJGD*SUl7ZMO&2Sp6BC}KRgIG$y@);~M-Z?moslPpg@#CMovI-Io`Jwbg<W4frk'
    'Y@p9hSKa!4*ufc*xC<}yC)O{}f)$TWzBdhVnT81KJ3MJbsyGs9jPAh{hPd_BDmUSWJ#1RoW7gj918k$M(Q`u8@?l4dRgZ{cP}m&j'
    'L$Q0|__tT6A&fQPnKBkEMkO*6Qjo6p6lnwtpdc8Ui?eozoaV=DI%;8^W7_WwDD^2hafC!<sOp`m4bSZg`#GrVD=R)89tly_5;3Jy'
    'U@m=3jVxk7!BYMkjv+7UQ5B<&yl!*!v$2)mUr@mtp-Rv+ExJ4pcE%Vck2>b6VHq|66EwZr1PBy(=VU@qaPYD*ouGwS7-0r9#3vhb'
    'C4#h!`qi&~G$-$d<y%>Z0jGY`imnGL$%<R8DC_j=jiWdFK@7uv6rzFjB4xVjH~g$cecyc>$awSiv%lH?Z62CP+uemlLX7q*VyrC`'
    'gp*8WB4mspC`WRZew_`wWkXwrDpD|WXeFRi%~KQAF|<M5CoP62^CyY%1o$%9hqklrko1N{naNCyhC>p~eTW<FUK+BL+@|7=$yasO'
    'mv^#^e|+o?EAt4`(WEhr{wPGVhy-c_9PY`?PV;esiiZ2O>Kk+33Vc0k-z~nm1`nEhzy+E|ts##t6N08B5QaXqRcOoNP}vRJ7JiA!'
    'm)PD=ig*gErHQt0A3nidi2k*tn-Kkz=$XvoXtp7380*bzFB06-)jmBvEu$zj3)d`6*<d3K^$0cWRf60Rs%hqGs$dTs@GR+~hTXA='
    'ofM`P$jp8q=1nTj0_|qal|<!I1_X`o#<X*N-op1g`0X_^t1Ul2n+#1YLcto&SC|j@ea?L#|6}MOqhoHGz@Ei-oIXw9HdsXq2Q*5U'
    'BxKM&!SLFHmFgA-fZOa?ecurzLluM+4#Y%EBXj<YP$&;YK@;Py2cV)+L2I`>9{POy-N5+mgNd;6!L@k^!O_aR@tDw~=akT>w;|*}'
    '6aWJbdpB@SF*nUZ1xA>AJcRabKnaoPn^x9DW`O(C>O-mAv(>>^?`>iGJSrbR9X2(JXblhv0!|xrSN7G%6oq0LLz3>@#`amPbExjc'
    '8~>YHF-(UbydW~_t}(hZ+<waF(OkEKH<r%ja>vXqv<QqlNhj%)QM7@Rp|?><u(Qdd1Kh2mHUF`NZQV}_0ahnjKVfkif9e7R{DPn@'
    '41v~~41#jHDkcB-)qkWoE(RzosW;Rl9C}O|1q36CXpzbNqk$AU9{8O*u^2wIjSWmoT&T1iRNHc4&311eZHZW$H((k=G)yQ4*EZ>g'
    '_OW?1tMMwTuQsqN76=@kvM@+*BZbz)V-uz>p7Un+W@19??Y5C$aXIj5Gc%cXs{xIR+F~WEO|9EPbrhal?(E%rK<s&#KCg=};kBNB'
    'sM)eGo-w?{G&OlVGAx4#TJ^jE46TwNe!79@@UmOGFLdD}MWVXY2x-F)Ip{4@n8dQKG}(pgU!9D5L&V#3%}rATEz>L_i6qQ=r-gp9'
    '%xr?V(X&*c{v39n%C{|So>q&=HY3{?p`}qb*5z`It9!x{I>zYg`^LPTEBEnjFzhCWb6jAfkmfALXlLQZ(?>cfr$7SIWyX1nA)r~e'
    'cQdD+zVu?iNxF?`RZlA&!dmL0n1Or)nqi-MgF{FFk{IXQbttqFt84cW!yO)$49i8eI(}5Iy^h(2W157~nL2c_rmd<-ap!vJz7MPY'
    ';dl0O%CPO|VS@q>Cu>&KC@jJO->Xr1;apH8B0i#FI7u*pI=yZyTNvaV42Kwk$nTyPo@-7OI)s5a>Wg{3V@%fuEA9<l5PHsDYn>3p'
    'E!=Tk5G-m5y?QP}rPhm!PWK$uNbOY)d!xpWqJ`T{z)w#&kD&%H#4;vW(H-G&P5xKL_ljCBfJ42?om<&vnB{gbC59dqBUO)va=eY)'
    'Hf(>X_kBBKRpxth?fLHT`HQpgdcIKaF+*1b4e%GIu#C2<(FZU@%C{6UR0kv5#0U+IAPn!#vOWjc_YhX7k^J7yPd?Yfs+vQP)M?ge'
    '2CLUh#b7a_SSAe=#j>bJMt|MA6;T|qp?i3JbWE07@OYe8=D6u2=q5?CkdKf@k+ppo+^MiV666wn(tH^AJ`^)*AAWX~{Lsfj^((`A'
    '6)Ne`<2LANF_q(a4(HY;4t{#Jit_&Z(%&^VmKU<e3_6Kvav|Z5ktU2-b@C{E(05A`emymDoyTUs_mf2+-^U!s>Xh&#slq3QhU5r)'
    'F+R<mPq&EGBy0p7ro4V1tE4gWIsA_??@XMa&{>dP=kRec!Ava@oJh2>-S<drVV7be51(hqJA>ym1{v_A^>l&~O1axlz+H?o)zKCE'
    '*rA}X2t<b4Sm0s>E<3`r8AXZ6*+eWU7WbcIxMCL@wG4Vs`pNQODnl&@!*=~IWojEGE7JkfiFkkPuF_5tzuU9qZ>>bbfoh5O)u>QA'
    ';dC@?E4a^S=2{dak!d+0Fz(&MJ`%P<nCFUU;mdThqP~$@CS7oZs~Aay0`73^eh{L=;wE%%k*-f!<cNoP4Kslt%7m#r0?bxS8_p2f'
    'O&8v9yFZXUljetLMPWLImy+Osg9c8fRK(m?D96O%qU?63zvmtJMk9o78hWi!Oq_<6u0@GoBARpWGRcEdE^N+5Rhza;cHKrEk4s2*'
    'vmJ)tS6n9m7-+R|N<%j14Jc3{-B?|UrkFWD2MMORZX*j%Vatn2B$a$0CYd+~rI`KJ(<C%;GJ}&dLEU5O;@)WS5bFoF7>o__0e;BO'
    'E9imFViHpWu@>E3HlUHtf5f<oG<3T`^XqqiD(AlHzJ@mS6@rLjb%3r$3pc3tSl9Md#b{EDM;TFCUALFLt!+k$Am=p5h6x)2k~?h>'
    'GPNlzF?`ci_<Cn`f8B0QT$)WA!3jf3a;f2h!!(Ko1YYK<)#0P9H<bn-e)lU{M5pKce53djx}Z>u>7+4U8Pl|{%HTp`j(2We9$cPI'
    ')$dIO9}mOv+fLTQYIsFT!>khoTVgi)Y7Zz4-ftdK1zxV^x^>s=;`ClVPe&FyYvfRajPYI=oEW^pHwlv~lw=4u!7rD8gpzK3$iz>#'
    'aSkWkJ7Sc>;b9GPF;~aksv#v68bU4MzHxAk{vks`4<Y8z#!IhyByZpH4swiM1<wvTiaCivW#XygsYt`)D4nMa2R(tE@6Owo?R-a~'
    '-3*c9yeTFX)p8(BGi|)VeQ3CZ%a``j{)Vs}x@tRbj^;}2&s$_ubx;t3x~-lou>g!r5m1!-QGvsVbhx$lx~smSGsAc5b4g<&N|!Lu'
    'qlD1TbRC0$#t=j*f*qQ$^-bozm-65DPe=x~;dHD7)wA{z_JN=nB9xdANqZfZ8Mt+TT+FJyd84<}PYaeEb)K=%tHnfIJpdsr7+yTM'
    'AOlx2!Y5R0q-Wj{XkW(aG{ydnjJ!m@Jq)kv^I>rsSY`kCV#=6S(1Zvbf6`k+n5AC@O6Uy^p+Kvvy&Ljh&d7657Yy(qk;K4{J|xmk'
    'Y|JoNj{{?Ph-sP(am1Uw8`(}Aj*-}%zHd<Pg*lGB_-|-6i&YZBWhud?M%WwW;B;q~`N1^z&QySvT|^l16$hYB=s|b^qzRji0;!c8'
    'GlD<u_|9Eip!WVyX1ZzGxMj-#^ff!`s4-ft`8=$yi2}pTW#0RtM1AY?h)I-dlNo5nN8}|DV+!-pn3TcqKE}SW+?0}-A&!~X>_tG%'
    'EZf_&^flanR!SSBZD+9we=G=P5d=h>l{5x(!vL5lN2|Eqxs9`m|7|y`1RXtu6mP98f^Qgn40j5{1Q|+4U9C|F*oLR)`?tYCH}u`|'
    '!&9AgIcyQOVeQ2%Nz~WyX2+nZVt~DG7JCUk=cBFmew-&B^5e7;8hT^cb^F2;D=}Y7+{6WD|5V2<=UssB^kv85s@1o#pql_pO^D6p'
    '9pR+NGNTp?^vt1?x}f&gNa6RshsCz+WKpsO$_{eQ>>zUf;X7kyos7MWO{w*=nEHu+9<+_MUF?fUeOLgSq%e8IUCdRc3Z|kgaAs5o'
    'NNh@5e3i9Tzj<eTyQI$Zg;qu$b-}hL>Sr6(=_=`EX-TK}DIp0Xz8~W5?l-T#!6nYejS+-HSsSzr+KU%YLgVQpg;#7eBv$jZ%Fg-Q'
    'EM$B1Ggq@hbx2t0OOk4zm(0J^=*DQ}N0S8~yPj5Ue$Qd%y?gfu?+6qAz&0c5ow+ZW8<qfUhzaqU%5<!h>AKHVvu(xAfsG9!Cu~hI'
    'eHdOxE}M}Lo>3VJE|>if<XK^N^@lFs@U|Q<N9Q)8r6~$Ca9c!YdZ1+rhx3bkW;k4!xV4*BjF`1eNkHI^SLPP!Vd=6>Nnd3p2C*?B'
    '3Y#I*ekoVQ$looyB~lmwGlkz{6@z@#Cp>};NsVI-0U~+FsDXN{T1|epDo%3rp;ze7F2yd$^J!R08rtSK(LIR~Nz8>|tz>r3YR&rH'
    'svB<znv}HQDb$5emJTynKnV_}tY@=s!~rzJh?P}b_&*ljFvAH~m%R)p*`bL^s}=STN=64MC>6?$H$dADKzMKIQ!Re;eZqe8vNmsC'
    'UMvfW5uJ=GAV*ou<c4DnaSia{7N<*H<#%sHHRXJKx{sbASx9&H^}ny^kH7@x$SdR$kzcnm2HTr-jp~p_&{&+`s`ssIzhCdnnhXSF'
    '&BUK;XsAs1_&308o_nH#+*cYRN#-pa_4dq_ZO5`_ynlV|=t!E&IK`(!N2vW0w*95q%pA(*3D#^E4%Xha-@xq+TYz)miKF4Eg7m$@'
    'BGn|#a7!S_o<f*0#iZ(YPqnJ&CH8QmJe-ZC{pWAb$A=5Q82*Wmi)j?YNeKGd@R=uK4B8psi;i%{6MZ+wvC3~q88=It6Uz4UWBmQy'
    'lgy!}!mcvV3ZzslcY?_q2G*fiQM=^<k-pE#k2#>{>DtdXF?{o%FMqvUnlY5M5Hl^_(Gw&_P;yJBt1vU<4@Orca%AsI*@VEGw;%a)'
    'LB<b;5Lvj?Yur|ThDcmSy4HpxxD*a11Z&nZn%YaN1)n<p>1M&&SGrQP;z%Csrqv5Nm1ZEK?Wr8J2}@je7z3C1ck8BSdDRU*NAwoX'
    'g{wcgJ^#t=H`9X4=}Q>{j8R(HU-A+$o(;#r3`V(2a2-G}_&ENv_crnE_dZ2m_Gvv3Qdg@88o+rP0w2i=-#o(o!cYq}dlzO@2JHRp'
    '1VzjBQ{VmWoPPV;m7p7r@`lH%08~RA5hlrgjnTvfV-We%5aPDQhP6(^HDCU}<NrI|E%D&LbuV95FjyBWe!hfTArx3_A7ACzEd%ia'
    'AosTGpBJR3)ip_mFE?j)1~KCCakcE@Fv|=QolUa_BY|E66Sa+&YmnucG`idZgx$F2`L8RCI<Y+l+L_#B(0l;hRA|OAMzlA@lExMo'
    '^V7WW`z23V{-=dOw=#X()Kr`~7hD!TN5qYtqy<%sRw?{V2vTrP$8GD4lHkh+HebFDl_IY;^fc{zo`5vmbe?2meEXB2e*Bb@_LKEK'
    'znY`C@;vjli>@fV(RC>kBtyeG)BPi{U~(Zg;Lf(&)?<+NvNm+Iicv`n|NJ1M%|$=YH^y{CEbRNRu8o1P!@Hm4aJV@c9Xx;fa+sN$'
    '!|hIU+a8ZA(SQ>iNh)7Owy{*oFz@h#6Ov%^FhxvdK?z#1Vd+?FofBcSy_s-~yTc!pRR@PfpbTlQ=2hN>f{9sb`BVMWe=PX40Lg2{'
    '*dZ<)kdKq_En%iijf;j$49gr=;f59KZpo8r!-}tutIT|*VUB<f^lXFbqAe$`7tz|c2_6b;$y8EJ_ugvb6b9Sq&0i(BzW(QM>stLL'
    'i*WxUgOK`|i3(V$2vpoFsNQ8r%_)Gr*>u;c#wHwAYNkG1*>xmHMlI>qP=e=SqY<;2@H$MAE7N4!we0EzHiV2{-wLUE3hoL6g-)Oi'
    'TO~ki9n83x+L7*A^i+#qzD=l&0`?C#U&A4MusAF#Mo1drvBVc|Ri86?Z&|#do8|Mk`PVC$V?LY)G;eshUDzo{aTwHnIatal6Bi*W'
    '38gqWA}EogLB4n8Ei@6r1+F$Cf;h`^4>yGIi!?BNQbO^<cA0xsw)<CqSqn^zi^&V=7x<5a7pjJWo6T3-M@vJSU9&}_W8Ay&hPk!;'
    'Wn>4GD}iS*QjDNTu_5UuFd-t~8j086zk8}RLtm#G1Q^-NV&C}q(yhrAN`z-8$ek)<Lek2@LBP@Wz}?^_7qle2kK0XauHSLm1?bd8'
    'S2JcH4CrF=PM{oWR#&SZpSghK!kd=ca>apM@i9$sF>QTjrz>9hmgpb!O&|fiK2gn8sM)yS%Ub4%+D9GB<DVKQT>Z^L^(;BA#aHZU'
    '>LUgi`)*Qn#u!dH_J*9u-rXuL7<c#_Hss7rfE>zv@n07gKSZTbY+CNo^{p6O8Lp5mdOtKRGI^tV!{H+F&*nxk0*~;UhH-AQX~mzp'
    '1N;!@&3S430yJ!&ArK!CKVlEFt8j0jM4SUt?l&!V8U?gMf+Ce_V^}lO=L(YonhnEO+eV4V7C;xpd42b5ILGz3ziyf97o=$#i@;Lb'
    ';LN(jbtqUbKv@-Kf%n==*Sx=^{O1ty^kz9O&u``-D^@XS6RmA;PFun;@euuR{~rTkERryeadhk5tFDj3SSXoc`lP;hljv6lhh0(z'
    'BY|e)LFkmtX}f=EP5tpW&ucPzPOZFfWeU>2Xou<ZcR_7$w30h=zA)||x35kn_~&y_4j*4vIG~1%iL{7)yrm0%SEH)X>qY#Np!w}Y'
    'AV!vNUwJ(|NcxP9=1MY$Ox5*KhQO#Y39%mp4p|E`)jZvCxCZO|YmF}lMQ5MI*30~A4oET61HoisQGj_0$8W+MC)vB`SvLN>(v=}M'
    'q+8LEae?L`tcob%LiH&DefSm7Zj?JtS7Zzu$B0P|^l{LL0^=>i%8XNA22^pc^TBkfhg(ZmY+oGq=)du$I|;k~T0vM)-{tu1DyFy#'
    'Algm16H_6&9n{7OR*7oTZD0Q3@jh05Ham4?mL0>NE{V}?LBunxD_CfK*d)3a(BQNgC@(#h?Q5TJqm#65g^eg#qnru@I|GQ~p(ioI'
    '4VTHc-G={F;CKCw#pBO!za{L4HSTN~Sb$Ut4aVmkB+QaM182%C3O@d8<aKE|ZC^k9Dd#(Z<t@0~EG*4W=MeYyr=L#Z+)w9p;cynK'
    '9=5gF4EU4VPsm+pPH{M7V=?0@N3`V)H*q`gM$7tt{kH#ZIB(o~1#OlKL-TMfR4IKxi7*-+4}4{A9ZDvbSiWKFCl}0jg6R)7@-jyK'
    '+!W#+ua^gti6^ujB<G>;je%EuubM5VEL28xnoGxFJ&I>jIBolWRG2UevpGAhmW~>Yc-D8u$T#zuZHZ}{!8Z4^yC^Y6SK<|B*UE_)'
    '$0idCzd+X0Q&`--3k}5#&dC6V71R=FIYHPYRXmRX1|b+iP_1!P5ZZ>I@&XgzjaVl)p_@L4A>GrK-^Hs`rx8-wHGo(}j@&YOV|7e;'
    'hCBrsUkByg{QUXpbAP+`v#J=99;^?eY2yCLB0*0yZQOsre=TNpos0S1MF_5LPT=~)9QV_Bn3v&+FNc*5r^Hp4i3=KyPdH3UXu=qb'
    'ooYY`hPz7ez|h&&h1X}BmEjJ?=0Lp);F3EzqG`Cpk`F^_n>Z%@g~$1C3;s|uUtW2LvD1y8)-o%{{UGO<V)Rmg-|iedC`WbJyz(mi'
    '!vhVz?ZD!ih>d;}Qj;>s%T6L!c5JnC>vuE9Wvw^MnNQu)JXvum#oJO_8PFD7`Ya?FVA?6rVNr)%onk{i^ZwKQaY?cDt-E+R+Hl@g'
    'cd6sF4pgj&$&MdtXSs-!4L<Puvwqv6-xSD~ze<wMB&L|dyCqIR!Vc3)SU)h_aSBZ(w5i*+<_4&xiD9#0NIJ!2GHgltFz5jm4Sq=V'
    'GrJ)D{&YIWPZkUW`aYuFN_rN?6ehvZ`cnl`M@HeNxWo%Y+BD88%x&go<C+VPcuV6=Z_s>ehlhz9EkYZjdTl7D2hiirVtR|mG?)9<'
    'T^XD}V-WM3oZyLq9pJ%{q@gAUqfygnWVGt|YTuGL%7>LF><Pv=N}nT-2LQa(*N15*eT<+BfS3VFzjN8Qtmg8G0tOc$h>0E?lOE#r'
    'A*Q`xM1<6UpdEDExB0fUSAh{Fvvb7$Dvw@9s3~E1bNK0Mz?Cr%4FxUjH?Ouz7y=N`u%@Bwg+!|;szLUM6o&5+{I3{xV{UM<YsH^U'
    '?)edNXD=RudW;n$PRnunlHhJC;*3g0wbR}-W+vUX=(F^*KVF_usZcdEunBru9N?vmfLk5ZW|XkFXQV`3JMUWYb`^Cd7&013<OM&t'
    'PPK3-LpY^Kb6Mzs^1!m~&xcg5EW3%Vs+Y=Qfj^3L3=d1EweBK=p&BxcDn?E-eJ|ecSpR(aMRT#jLQ`)*1ptXU4WL9A%p6XmTIPaP'
    '9YM;UR{PdHDH<+E3V<F@H}uU~d@>aY*^t)>jg%TLCSJ$$$llM;{%zqU4aMO+>ya*pW7w%CLd*ao4hPEUzfPe?4zV=Vm`a+yZ|kdG'
    'js7@p=rT}zpjXV%Va!WdNx6Yo<D=5t(5x%}Qw#n-|DXRKZ;~Mi'
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
