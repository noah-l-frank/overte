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
# 68a5f67199d9560137edd765d9617a661d7fd70e / tree 9f75ba1d6808b4f910fb6594d13969bd05e4a193.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '99ff08efce55f20efeb78e05a83ce4a2195a6d950c496b488a4e88a667e8d472'
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
    'c-qa~+makdvL)E}`HXsQ9QggxUokQ=?<syU2ZBswWaWiLc1!>JEcJ*4!7609M<jb@j`TS!g6uL2cQ-ZFt$T0%pa1x;FNc?}ujA+8'
    'VSYLu=1<3eJ*1~kFHgh6^OBza>zC)_!$1D}|NO_d<DCBS-~W+kSyNU2_;3Gs{yO;EqR4XpQ|CoD<&*!E<?XVha-65S$)+w}vT~X8'
    '-2aD{KOW=1V7xz$|M*}3?fbH$g{H5c9*_5j>5q-o#<BF@)ug6xvw28U*R<_4rYvi-rEJDITiT`?vhMxW9*61I;Y<4TujA9N%l+|R'
    'pS~o&c6d1)AD%ZBpQe6ERW=S?y%cF~hbr&;HVtFmOhuPfOEYC%*4FPY{*)e%&xe=e(;uIvuW9;qYsGr1+G6os+q_%mxlbweOI<Bl'
    'HTQmK-wkC^rLlT{#h3K_^6B~Y@RB~w=`lUb>0vsgt#yY!AF@=Bbukp#&<({<*JC-Bd0XaHmrZ$H)?GQ|d)D1rs~x8?AN#iLo4Kk}'
    'w@iIK^`%vcd>DqZZ}PtG>hb-x-d^Rim;00+UOxTvb+|t)hiQGQ|MkbW`}bGx$7O1kt}V(jU+TUpnx)T6Pkn5=B5S&;8rsDtzH9ZT'
    '<1cA?`4qqX`SP+3OX;BwLp4oHYU?qt>b#oscF6lF%bVFd_l@;?mi^C<>hjXXlCrs(%YM#_Z0WKr>;2?rZs&aP#=C6pva$NfFCL#P'
    'Co)X;2T%F)bol&BdieG5@cjA95byc%kM~#2^I@vSX)4C5s@k!ry4j)0+d9p4=eI9)%G)+8u37cbFZaSPuUjo`nW`bRT{&h`TljHH'
    'H;(hrj7!ljS=(hPP1AMj9>>e8F2mAhlg}t${JtXVhpZ^ua;&C4b=A}^!!$TRS3TpW*N2O1PI=Wd&Abf#Saq$RH}qwb^<6%eX-q{m'
    'k6D|R<*GH~OTL@FJ{`ZMyXWcnc==a%b(LkF?BHu^rY=pXAL?>wGar@MRZnw2clmYCdfmap@GU(H-0AKq4UdP1FBi8lJG2gUs+&sG'
    'OnH^cye}N&X>774udAxbD_7O^+j#tTHyt0A!{zmz;nZ|x-85Z3tk+^w7Fj(u?u~ga+!Ir4kLA_t$Gtq?{r=lBUR+<GuCl6{>$-JG'
    ')R`wy54~{ehV(_2o<in+9<E;B7wD?IxOSSBvK#7R7R{DYXm6){%*$+WYfVFucXL@a*^b{H5#?XQAD<u6OGLW6r{n8Ox|<Kfmxtr?'
    '%VD}4ZOVRfOQ$NYr#e+$f8V7vxH_}CseOX;SPW8@{_1VK&W{%tF1ohKQ(nx;jndA2JbgQ9rhJ(T2Vog~iK%UOFMRs&&a1D9S$u*o'
    '>Gzk*0jPG^r6xsLmt9$=*i_x8cC2Tou}@Pjjp>{1aC<+<3tx`k4$~)L@3+IV8`S~)JiN|_m%H<g7q{%i6Is`3sODlAQz{qHaGtBa'
    'uc|I$V&2s8GCY~~=H0BPG7iW6@G6(Q9HrW(oaSO~`pWxg=3x{!`>yDhWp2xC$@7#+wzAtd^D3RZ94Y5%$h)a%x+Saq_Mx7N*45yc'
    'NcZY)sfW2Li<IBIhhNjvL%P3P-_pgM^u_3b%xyEx?O3);l@-f47fqeZ$Cf6^%Y47Za`R5U4G+@o`A&}SQ-1p6?(5+>a+Qm_%HrZ`'
    'mZ}@GGzlYZs$FJoQMp21+F{mKp3?2RI*$IO-!_6-GezYx)uU)xjYZq~dWSNb%c(1qFGw6~;-B8Wi^p^2G2E}G`e~S6E(f-5uDYVF'
    'imoY^t`XJix@@Pp8=AsrT~t{=r=lDCo3|vVTJ8^DzP{{^wM|<tGOBE->e1Dbob$ZP+fMw62Q-(Nnr&&v4{T{G-SPlxrDoRlWmYyt'
    'mlu(B$+A3>-rLK%vg^uXzIhAMj#;of{N`ZaeSbukvjE@9FlPOte)9~<uI<GAu@QWiQI)*pllYU}{#c%0oU6+pOYhTYW9d;nHBBy|'
    'rT5)V9#pHGY}>l*>kpiwm*MG4+I<Tw65ec>X4%Km_(qb0omXw`BWdFaHS&W#OSiwJQ?~kc6^zH%hk4itG(MBwha)}rS~A$h&?t?X'
    'x|ymXADb#0a&<zL{-!<cxSq<isCWCZ>C382{ajDkxF`p6UvfA5j3eSqOZLGXt#{Pjt}r;&^7kTlVY(Q*A`Qcw#?F_m${EVC1Pv_G'
    'tPj4o^zhr^>G<%?zj%6em&>{$a2{|>S&rjaPmL>L9GX<MO&Yqf@XXxkbNR77?Y>33p=t-vNZvMM>R>c;rMi`XDKAI4Z{xt*QT6w2'
    '=k6d0{BpWIHZs9+?0isjTTGciJbGDU-%NeyvMAkYV_FK^{n*xSy5+|fpd}&pjW2LCS;!Q1V%Hb>Bp0ccsvPEi`kS^k9lxzO$<_mF'
    'mLZkBM84{Cfim7_CutVG?Y5coadFRf<^1>T>N)+E9yY3KC2K#`@d6c*0zl?@by@EED9Y49LrZ~t_}G4SMFQzz)t3P=%xUSTz8T!O'
    'L)JL_6F@d^ywF^k`@yaJkQIG9?D@uf81oPSLzzl7S36G-wLTvQkb&Jn+EP9b)$*}@U7s3xZ-bl>4gx(5m}|-45P4HnKJljP3OlT_'
    'W&G&A<VSbYQ-bZj9ESVn4Rk=sRaJ$Hw(Cb}+p>6AkrU*jWH&D-7@*4a!+YA35|l1~ACCWl77cms%*(1l`jDHlYZR#Y(9T8ivCZ6&'
    'y~!cRC2#Vkal(|%L%qoU+j^<;G~}+F!abN5)5kXUe0+TZYE8$l32r@I&gQH)XNsc1lL?e9%>j*<RUah)(0umLCJ@sHw-j0B-Hs9#'
    '!X#e<_7!cdGFwLXOaXP7%c4$jPvNP{y1e>3wzCX}`_~Pix2w7-4XGZosvaf{lU8m!$XTYsW17mc>orjF4}RA#-yWC4efnOlT|WM;'
    'OTQ`gPa1HLh}nQ;JeE<un*}7Rvs2W~2fyx@r`P8fH_5N*kEbnY)R~uGI^Wfpa^H0C9cj17bI06ArTJ3LUHV8xaK&aK%g(fvV4_8@'
    '?UM!_4;`;+%$%@ktjfBFMeMu&&mi^rpIp8z<`Np{vw)7awfjOrpUGtFe5@t1FxtACx^7>F{pEEHcj@Wd;rV&(Azn<z#=h5&h(^cK'
    'rE!L7XqGAyM{TAmbyGIXV$Qyw{Ph@b|9IRA_;Eq2C%U0;tEtkKErd4pdFKY7vwQ}}IVStoJf$s{L#GZ_;oz0pA9G|;fbWz8xWFch'
    'J7>;Idzkm-PY*8t-_qSMe>+^hNpv<OAL3s=7EPo30hO4SNh7oL|4IN?rC``u5S&-t114sfOI%qN1yVbusZrQhPCOJO;G;>oCJgNR'
    'mVP`*yK{`G%u_Kc^3{h?wdw$AqiUEg`gmnl%wrFP-&rsI*zehMl-gNsQI+#tLiy{qiUL3NvgguK_F1c?)n;>h#p0*JbUHqzyI)+7'
    '59x9Z5usHu)90wPkK3kcq0D_2m3yxl)u>a4Y1xU<{kVf~$KTRgjJkq0u0p-?y46<AMm_O>aiukq&bS-lV!f)p)p+QK{d>4Bs!Wq7'
    'o|TSuru9{7bm=EArS7?tmRvvyRbcAJ{p;@xE&05t9lIfFZ8%EXIdOrwIpUpzh$&D;-d*lr_!M7uJaaXW_pX^+xW0<qDeUCZW2w1X'
    'xN!l*pcDPiYnT4BguQ%+Xk=&7o<ZswSV&vQ>^l!0pr3i&Ih;g7w%oq_x!X5AzFvL~&RssCDr5mgqlE-9qs|*Bv3pKGp=&i-`WrT~'
    'Z~bzqH92!xpJu1zOP0Dg4`tyGx&gY-6yuy-{|QLgS1yO6Fg#txg2vHJT11!CtuhIDb!|^mDrz5L5*$03#ypQVZ(-k)Xgz=HWt!dt'
    'vcc@H*ajZ{pgvA+cF9#O&$wY5f4qD>KI{WD<KtH(0Ck)P^%IIvs#{Hz3b3Nbq&oJzsv920Q~CnaQK-y!|9To8AGflsY0Q+ri;qGm'
    '2n@{SIM#!nu!=n8Y6FpBxZ%S9EM0EGHjO&1v6ysjuA;RF8eDYSiZMcDFw|;ol4<|a`xAn`9r~dRa>=3@k><>eR6(~Y$-!KYx{N`A'
    'S+2N`ZpsSu7ivxK#`E`+N31yA&S?lJaIh2HxoK+39o5k3mw!4uJifks_SWyutg25k{7?T%5^u1Yis<5Q^y;EY_14$#Z<5(76+vqO'
    'h=98nkEN)0WJ!P7jnzM;Ifzd`ZY)ZVyWu4s-8OJEs1l`VYLEg4Y4BA{POq}0t<)a+#3{bo9pLDD8`~o7EKWe=PaaDVSc5Bcp1Vc$'
    '(T+jDLk`o=+d-LGFY7mQ<K-o#YQD|LPBnW)gy?{eYOywTNN<iPo=7_^JC}Te#v)eUc@M+Wx8u{@tAB4JYpDwd!5yjN0uP&-Dat=k'
    'Yu~kbzMzTaicw*F?><hI=chAQ;`8&<^#3(^WP4-(uhB`~-^z(o5(U<pX>Q<|(%Y`X8}y2BPb(?c(7-bQ<<75XGobvo-3PYw1|Y24'
    'x}5b^V_TpS1}hg>5P682qr#t9q{H?h`CJf=ZrsdD;yiub$fU#b?$2j#oL6aJDnL<1avM)rCf=Ibdzfo~Bui{|(62W4HNGD1=M(<3'
    '7jPBXIz*si=rMrwsIplQXxlar5Ez+uOBwvk{NtNDV|G70whbPNV;9d$NSN?7A$3`FgEbj2a+)F-4|(dVk8kXt4fOQ(QqQFG%gBO0'
    'Re?R%>6YhsIddM}j#9(8z^B76L^#j8{%_dXgFEY9(_?tj>bv}vB@udrMeABi^<d|sr#3%GX+(`t^J*I-P1hga)hX!_BYx=6UcOYv'
    '0m-WcE_!#FKs7s%bMI60#bMh*1)%=j`0=e>6T4=4hHu}8k3TPd7oDa*f>VT24dm#0sMm(S;aHy2^~1Ndl6@T?zYfnE>}aIPMwqv~'
    'NgW$#f(&T@7$X2Eaa}mt57YQJd}F7pa2I^t>T`+`u$`#@Ahz8KnJ#IZvZk1Vq*i!vS^D^<o)2GEcEo`cMCH5VP}YD&m!YB$pj`oR'
    'yJhS;he7LVlIVJ1@YVFcVQ*`uv!m_ar8)1Ty@veS`}S1BDxw4nt(Az_NNI*X{|$%WO$cy#JB$7?7AQzoY6BYTz(P&Ys0;c!4?tSK'
    ')QxcCcHZ{z`MRr8zu%&If8{&|T-CXmaFh`xP`5^?1=KcgZ+?s4ceP%W8?2jvu8_0chl4m(If@c*I2K%YEXoinAU1#a`J6-iWk{zi'
    '3dNEu$Aydv0b#{w5#vD!qB>f65ACe#kM3p1F)J`?g4BnS(Lx#Vc6HiE`7m_@baNVHqx#wHhqrRBAO3pSHX=Y4<<ipXoD3s~y)3hK'
    'M*3g;TcsBk9TfohN4IvxmVkl)A5jrstCCQSL0Xmn<pmwnoTsr3cs#pMP0oj>5D=YrmWuS&idX^JVS3rdf*0MKC7X0ZmA2i~M?TeO'
    '5QwIPiNnd2HA7oovxluBR+Xj*DZ08<9w-PX^2*>cYb(v97z)ZZrv=>oyLUF4^m{XEhHBA^M;9uIPRQ13WD6-90(Gtnk@r9QI9-3k'
    '!?J~1q(XxqiED_WSnnU2=!X$4QK!jq(5V_P`ezKz`8cV?WtqeM=Q~vWA0%3L@y|B;b(Zx3mzchBpQRCgRa2Dsx~iregDGCNL%O_d'
    'P!2C+GX1=uo$Cv9Ng_m5i9xI49z(n0n<)i6y{z)`GN*)R{m&b{-o6~`fLX?+ZkqySkQS;{w3WJ45&aX<%>0ud74TPj2vq#@@bq$^'
    'oRTQ7OqZ7p4!P`n#=L_DyGqD$vV77jsv|89T4k|l7ipJWTyp(VB<B8plg^e$Euf)~@H^p1W%#Uf26AhX!o8bn`bII}XLsy>EO;V@'
    'T>egmK=$e~!%_qIw%Uvh0+cVl>{SExsV<&2e&6$W{C4-7TYKJ4X~3Ahn!0whfg><})Gt`gLLdp=9c6~|IQKtmUZ1j+IsJBsx2V2*'
    'e2LZfBzjqh6VONkuyo*4EY?wVDf3;DBmR3fYkCe_i_XL2OK4}-2=gB+dU}68S5GbT8gZjKDDF7uGU;E#5`@vV&F2nsirv0%#pmy;'
    '>PJPv_dmWI*ox?=(h~c0^)!ffkXJzHxgE3^z?sHMIZnfkJ9vCNynegevymy-+PX=pUE8>2A~&AJ@<`4i)}sZZFbwsT8`<>`@MRk9'
    'wNbpSf+*So0}A8_`NvQ+<3yC~KKq#j`SRM+@!tJ%Jf-kw+T-@OUsi$KkJM}g!wNLDzvcyaJ(zq1DSFJEEPuXsH!EO#_a$k#Z?zl|'
    'y-<vu1>JmMt%`gMqoL{&$#T^~l3{SFvfW!)zk^-x0;OO^H(La>pqkYcveiPPQ$+h8X5>A<w2IyD;{PA-K<DDy#*#?3owNcYk><Vf'
    'JLd?1tx&6-t}1S^3$$L#y-UvN`B&YmyW{kFfB1dZvj?lj()w1QlSaye#-kM1Iq56(a$F_^rqtFqZsE)0>)luU$ourX0c+|h&WcAy'
    '585S~{drYNOh7ti^wtU-J8vUpf5SeIqFwK(?i)NKEgDe)aSVsFS(a$~%~3K17oj32r>-f>{O{S&3NY<xMh6&Phi;>!-=AikUuub('
    '3Yk<P#Vbs~yDFO-cje-K!i;!6{OWJt{_bMpr3yk#=_@%<FEs%&wK}pCnRBPxHHR!(3!%7iKPLoY_~TwciyA2%-n(M|3aMs@zp|rj'
    'Y3e$<^EC=dV&hRo{?2?s<(=wVkJZ)t$%|3om}p0eu2)N7(NIZvX0sYxNS!3#<xgEje!ib?$LZHyhkNLvhoh+GtHJYuzD7$W4<UbO'
    'qLyGS$o!XS@51M5aXdWCTkK1fYAC}5vni)b_l<_L388)y*jX;P5}{7b?(_V3n2y!w<?#DUp#CfPc{#3yW=BFNkI;LJvN-4h(#b$Q'
    'AjfJDSx4JlxBj1$somF#GJOcTspb*ZSoEpY%N4Ve3YSQ4v<-G2pzOMhJcZTD)Ba76F)4+@Mn^#lq8mowYM9-S#1P5k9RVufW$z~Z'
    'w+2z;iaWlFlxhwYG7zjEQHWfs(of$fS;dlY38q0wdgBgG`Ofa=5sD5~Zophbz>0W%aKw@D*I7zpxUxcO>8jm#{clHqd$(E|MYXyS'
    'oupNn?p-MYj6q?`BIUQJu!K%ZffKC4?X}093-%7bj}Bd{q3uH;fvtf<>xwLEoDwY5g+Xz%wIIRFAO9oml3wY#LmA@0yRN+Gr4Nl$'
    '0dr{F@G`v|daeJkwd5*Ad#lSgbi#coD0)5OJn8pWS;Cm&2@qyZod&MIOc+XA0cW31TIUJwlmpyxD~jk?tG<bVWGxf?y*_ETr)uwF'
    '>n}Z?+rjZ4?@s@Q%;0`U+ciK_pYE(;XM@oqzJvjga^1tnP0GS%sU7F+mhBuKqVbD!F~0KMdb)dj9pAVxm-i&(yL^GT&<XI}1nil0'
    '?mA{jTIp@Tcq4B9hxQceHhQUa?^@bot}!hMEkXlc0NsJ5CUkB-LDctPnz9b|+VC?=q$~FGL;FU0u%ws6x69X*I}n4Neni<z9UQk6'
    '382%V<Ldy0#!UV@54Y^<-qX?TO<SSaTgakG&vvU*^UNMpjwPfB(TWSf9l!z}lHan2Z)-bHOJZve1sn_d0^tELNgv^PE^OZn(=7WD'
    'i_w0^`IbF|y^lRS%{!h&ax;~oc;b5IO98iI$Kaf>L?C6D8*&DK#MIuh53SLt#vfnx;CFo-YVKYoOlja~qZnc~O8Gf^*pYTox5Ta0'
    '^f!GRD_C=Py0=az`||tA+|7-8Q1*(wH3moq%Eehi3BUlH;;TuwogUcy@d*HM-pxP1-EWZUBs1hC2#D?zhCu3_ivO1?4QWZpcbh8O'
    '=f7bq@n@GY0~RYyt6!Z~P8mNUk420@jKv&pQy(~YH#fKMC0LoygO6ncy$KW(`kjX+g(w8J<xPQa<ufvxj;{%NNlLeD<azk^NR##)'
    '{NPh-e~Y;9Z{Ue4EFK5_l*U4~zo>Y$(8d}m5Tn{hlWvOrFQH7IcT@mX)Er==R!_Y3Y3Q%$LkxffOx+5~0ilNhj<;;$^m$D83bD(3'
    'z#j{l$P7F3nGnE*fWL+Of_yZ~f$Mm8?fzpkeH~ujWHiIe=2;1zFeE!T%DT%^ZMX`c+s%TE>imXDAiJCW;q1G~<Jme2g!^>^AwWm~'
    'a3%eo7T+q`2HKU_3nVRUnmmqxRJ#2^>_mb+-7d#5)RLO1K~x(aH<BdOPqc06r<Qv?bviXXFQi7%KowKf<Ru0C?u|qYpZ=Kc(>ZUO'
    'CMP8Fx0kQ08^C?quFFD)jFQk~LYK=<KM@FuED*O35{F(OWFQ~@rakR2_Cgxrqep}v&W6G)>Hh@ws^U+36*RyH!?62XHZ&i&?!9a<'
    '-U|};NiR*KcMO}aCWuzkB79&E`LwXEmMG)?mK{B%f4*+Td}QYMbVN9QUQ8Y%spJUcKvmJc?MQA3W2*L}8@fM!IXvvbS{iLKS73?@'
    'n$@K*8(Lk-{(~*cp3)6j1?T0XJA!^ZheqRJO1nNL=tdy8Yada!)En#bMxmmIII_1LL%{4-`tXy|aQv>C-rAG*<L#(Pw47M53P-G2'
    'hag^Nk>TO@E>em#e{@gJ>BUX;1-APzJU)LtZtRL^x55>K?CN(m;iwXCah7XV!LXQvAdaH_x9#fn@%}hmhMJc^;T7<#M6r4KfG9-}'
    'a~8yBo#;U75t^!|_~@Qqj=!ddGi~;AvIWBpR_vr+8EV-$;h|`Rjzj*`mjv%cY;U}IL-YI;X#7)3@ozkAas*vl%0}uJlox0o-f0(h'
    'cFaO>8oR1+#iFg;x*h)@8Wne6UtS(}1tuX;-?UhH6}%b*g9_^tA;JBEW66c8;oX`yAKlRN^mKUKbM@<LjZOGEQ#z<GX;dYDKv-U('
    '%5Ux<p(0gseqck}G*dm2JRAsAlyf07R>`Wa*&~o>@r`u35K-0R%?ExyejCK;_4@eJ>-%!N&V8o?WegT><U}h*PFRV1gZ?UEVlxrO'
    'P9NOT{UM~bJJ331N>?SS=27^gkbz>&kYPq@T_IKMLd_#0Re#5RR5j_aWdsxsc5@BOb3w>NNZYWl;-E2+K`<+#As9yCAKXyLnfS}?'
    'iqOP;m=Xv+nKKQuRc?Vd@qG~G!#!=5Rl_RETeoy#9DP4yKPb*Fzq&eH%J`adDw_vsG)-t5eS1X??~RenOLdz4UE7MkqB8EVWR;S5'
    'ZQ*3a!wEAPYjJ8JfqcO_Zx=F2$z67T)4rB%dz)~IP7p`YF|<S#u5y^&%e)bB#7bynOH1>?4aKdx!^)a5ON65Z>lGU6gYL8=`sl?e'
    'Q_*vflA=A7e{eS^mgAE{_ksbrsjR?qML3jdRFtfA0;E@Y@VZrt9OlA0iNgh^=?8apzCT_cc0Mc}Tez(J*4;iRVQcE94o@U-9uPc+'
    'J~)9*>8;!Pa(p=kr(D8)-rGjDjmRE?*HlnnSHW^bs6?O`6#!a`EutL8=*`hPkcHsm25foxjE%fEWc)(2Mr%+jHCA12j+&wgn5@02'
    '@x9!-k^AGk+F6~<qb?&pRXCB;>Y<SIs|LWOfmWv`()Nb!vcHMQ{eitiF?4=O=kUGjDgis>foUsVQ8mr+C<BozG$OpJ@F!~(Nve~N'
    'ZEO`$&+AE>j+?EBNYJE*2owBldlcX)h~*e}M1_jDXoare(5-tq!y<n^rtK{mf}w&nA0i}iP!fg<OHg<9WqrzGWPH^5?FEQc+3lU*'
    '-%fC(lEQ}RNWgZQ6P)ciHMc>vCBMf^L-h@^`ORs`!!a61f#%V_dtzIR-`stM_df+!F|9&{;1r}VES$hKdB~Y~;oMw*9M>H3R1V?H'
    'zHUTCiW)`?h@^QKlZn#!<AFd#<1xjQh6(tXZoXkbi}6{j`GxF#NDatp2&?4Ke~Sd%aWwto4=DB~9#H1l*yr+*9i6Qq?q0rz>)z$<'
    'Fayq_PhnZfVz{LB*4OpJG>x7Yb__-1&8gA3BvS{8jtGa_q=V4rI_uc?Fsoj|O~K&PA@?qH4+`02tEqAGJ+|JY^S-;IaI<R*Fl*zO'
    'FMpLQ0;#p+b+cJ(>3lIeA$z%fFY6so+OhYv6D3x1eD6k8SWU1G{^LX+Dr;I#9Sr%0c^}OOcl6u09R?ra9RhVR_^C(*oVt@kV`?`e'
    'Tj?0LGE1z7>E=A>w=NRb-vUkBO7F`o*h76l)@6*nuyhypknXIguK7zVlltKUJ4wF>Up^YvyKP4;-nV@iJdAilGjd5(hlcLBS^cYo'
    '3KO%tk8J9&KAp7pG4(n5_7twjh&8A!;em&7#Uic>gBTb{7_yZ8$98nwQI8q-6Iod>cTFNO^9Zj8U`9m{Mn(AM5fR(lA<x*!OJEGg'
    'rwz(s70G%Tt`05oHt$TbNAWo&d211s;Sv(S5A5Si2AsC^hG=$}#eB+O_$-51_)eNX?BmKgOi>(pO4>1fWGmnADG_iZ&zV%rj42@;'
    'P+l^YCS#hzw^AVVm8k07=8pK^v6=1eAOI}XLiFlRbsGqbb|uv+_$MZYnW(}OB#j@~Ovnp2v{OP^$X~);kF8%_hS}Z}li;Mv*fA2Y'
    'fd|1jePkCe;nsN<B(6;?N;w=YQO#=Ul!VlNbd7~Oh+PmRL1rqRkHp^ZIYhz<q4D1^d*ZLbYR_0LT=ZVU&@=JYG*zlfrXxW6qvhr_'
    '>(AWtZf$IC2>H2S(<6f3k;`DGUR2C|(zZ}?`jUY@;ZA?cCF#M0W&)OS;@ED8-?ZMi4^}Z0aSSguOk?<yE7DoU(}6h4u=eLxkN2#2'
    '-V6@b|Ge4TmPrm_PBF`yK$lvBb$FwVDym*$mqkO2h4FsM13u|V0{hqg#2bjR+n@!<TO$ec4w_Q6SeM{TEGBd~7A-Wog+@bt1zhpY'
    'zSa_9_pZp`r+8Vcfw@PL66@@;@?Z^Hgpr+wbMFDR)y=y)H&6ENM=A`W9LW}R2I8D+zF{Wd=o41Dq%<=O`pWa0_wyr*a_^=jeKBq{'
    'swWg>U4!r#3~72CdfhOnJv*B#(ygCvD*oC2J*};8902le^l^zP;1K4OMQ9{Z7pb$LmS?x_X?hx-zp{mVIKB+q`fsoj?o1yV3YH!4'
    'QzY`Rf1R<z)C&l>3clhBe%!z9=8ReF9}eV=#h_C2-%S6DFdz#ph{SoX@G^&JR*J2gW58cwr=6P$TcH_yf}jrXKPIKI#Lvu9LhEKF'
    'DpMv&9_IODn~G|9w_P8fm2x?m21<^@7~GgXmOhyxxeXjVbVFrx>yEx7DZ4ks*tHlZ!qYm%y&7YjG6T}&f+UETg#NiK`R4Z)4`+DR'
    '?Y<&Ds&@<7p<1{OKLg`RrC<7`^3<9^zgpeB(%-tHbNMNsdi@f^0ydy{C=)Kb*;nCS!h!}ld5KZHWi-AT)fR~rp=9&n?VQ><$Nkrv'
    '-dnhC`k3HOOI&kiO@?+-wF4@I*(F?*F@11nYj0rho?_Nu9SSeKIYI{+nbr!*f@-u1KwKu-wLcx#bJd=nzrMai!nprF0i6m+dDyk0'
    'c9mR~G<)2<h(lCRiVd0%#p~{Uoj0<6+Rtwhb9!Bkq+jqBq;QAJ$%)%5fmzf+2ANr#Ybd%2;jO+i@TFS9JFf3PvZLepi=;`FDs18w'
    'Kg=6O7-6VH=Sq*poFDfs{KkZGc-R~oSmI-M%QXqpPxkbeKiW(!O%(N}x-hZlWW*o?(!yy8Uy@PH>h|j?qOk7YQDXa@K1C~DF8S~I'
    '<z+NV1%yJG0Tn{WBOh5JBtXVG;P)8UAM1{vTCTjenRCDU{AA95cdq9zZzc3|i@VG`DpTizLTUtP#gs(?f`Oy|j9PmI-T9rZY^MG$'
    '2nY*ib?AK5$wqu@q9W!83%m%QHH`gg|G9b@MiAwhV7&h4Aoo6RFk54M1g}L;qX}m`G(3pd5`+K-VK_kA$}vspBfHpo5+aH@1mQO4'
    '(<H7-F)po$K_v_#nZ2SW^2y2er_rZR^WhK&n4S*$c0c^FlCC#2X2Bzl0o)AbVs?9>Vs7A0$O%elz<aHBzk&>P+6O7$@N~AiJE=&v'
    '>SJ;*1k8vc0F5OaVPM(_P%&@4L<MK7-uBCN+hEOo_cTNnc=sj#y46Py(_4y~IZ|b2O@tDNYfBb*t)T(>GsaZQe!A;-;lF?0uwn~u'
    'kv8T6;Oqh}Fhj<GDf+l-@Mp<>bsC1Ixo+{(D~Qiv*L%RKfHN|oLt12Q!kbh(3JV;Mk%M|@a}6P^uF%JwWmch|IoEXCS{|fWLStsw'
    '*sr5$nV8<%;*-Qho$F7r-w_Dw@w!c%Vb8Y@VZ(t=p`8Nx4WnnHLzbZBDY*H{1l<ZKjXRKcSALKBPMn_hNdxnkjxuY-q1^GzQpX}t'
    'm(k?qJ>wm<)aV9=rR#QpP%^9&C-?IMh>ei}g=Qx*3>Ed>-R(pw;$#e%VC?@>)47Y=SS2ajQjjqZ{Q(yXLY*eA2?S&{wcrf{DUJBx'
    'eK{}nm9OC(qJMY<yDZdrS!AIN?P9WSghwOVR$&>;17$P#(YQ$Cm2X5(YZNNugl;TP1CGki`YS3dARVB?%r70<DJV5=Q>GW(x~^OP'
    '^&r!GdD-|FY1#Zbp7C*Cg2D8Qa(YnC6(}r0>YW0xE9a}%e*V{Ct2-SNa)Sh_EC^*Rdx&7{##APi9<ve9cOF{k-D`(C{fXA}Ev!po'
    'Zb2INcurMJmI}<*K-VQO0Pae6W(dwBV2I^*9y1i`;)6Tc)CQTP#sr`%FmS_zoRe-$ghd%LHfr_Wq9j|Y@%nAV>SwOkPHKfAKRtyM'
    'bz@9;2H9}Fb6<o}LRf&6fiFXzu6Q{i3HlT~?mzyLO7O``qSp#BZ}Q>z{W%|9Y%2a&Ml;7GF;rcF)TzO9qSS4w+jsTL@v!PDR*lEq'
    'azA|8uw{<cvle-<hvrZUgj-Tv^f{HV+$-#048baH-_c1IitVAy{jxPBho#;UgO$1b30aUOo?=TVV1o3ms}?gEjD7EK-wxK|k%IXA'
    '_RL;bo=_V$pd1~&aLFsn(3$WN)7^8~nZwq_xQtM-*1So!3Z@hQ`#P#=(7yV8V@wq9iZTLdNgmYlSn)=XIeatdInbmmW~>%luxR>S'
    'ow)YmcUcgIGCOd_wd2h4kjJzDo3+E5ZCh4=g?^N~S9L5lvI(bf9;ZAeAkCp*EW-jn4_=hJ)G1Xm^X=a%)z2-ae>3Xh*7@s}q0JK1'
    '*hnQfA3_OGF$=yDvmu&<1=ty8Sff4VJJ&y<%^L=RF<n(-3kcT(M#9}*J;NJnj!uQgPGXg^W#@`#g}|Gdc2BR(Gz1xeON!2fSs<-h'
    '*+lk8cNSfnsaX3>o4NGc4vtS`8&JQ^sbg&n7En;fyyTd@Nj-`CUavw0E<(mp8G*Z*v3+0mU#E2OC{5b3E9XI{qiOVnNdY>qoan}2'
    '+Xr(%XE90GjJ(Bs-MKVJ1}EvyM;}bh<K>sm`Jf9TRE+zcLJCoa2_B^gtP|4&I;E(duiL;X<k=W@h3bSG!KY=2fgk~-R^d7~heu(K'
    '9bhPWk?not>%`>^A}SrDax4a0fdK_6zMC<0OdrJ-YN8NRUpGY!hhre75vYHEobFy;AGW;JLUrTLg4QCIlX0aO(n%w2J8a8i#1wVV'
    'v?+Uybys99p6>QIIT?PvN+d!VvBXFU`6#q%3aL7}5cAuZUX<-w^^b>%=wKGQcG}YfpAG?V!j4jrbum%fdRkX;n3Y8>+wDSfykqgR'
    'pX$k;;BMP|+zsSL(B~OqVs#P77>chWq=T0)Xn<NVA=KEjG*EZ><GNpNl{(PV%)}#?2Y70c<ncW>w~P97ef>?fX)p3idia&S`Dd&e'
    'IE-s!!za(o3?nRJ4ix%Pib1qfWcYjt5L{+6G#%tkNz>b+r#ay<GI9(~+H&}^QTEp{RR<i1S`PCe@{j{aKO)tR&`Hj~a%0-L`kQ_E'
    '+l*<c(3iCF)Oqi(u8!2M>m#NMhKBLYuEX6CN+*6&3-&v=uo5{B7maNJvV83k?2(R#Aasdj)ETM@{JZ4K%c3~hlpnsWcy4v>dfA*A'
    'HF}8DVl*_2&+|?JYoNxk9b&o1+VrRH&+o5%<r~jwA7q>WF2aIk9gB+9>!uj$$W)pIFOYLfcg+@dJaftlt_D8jwC0$u3_2$TK(JR?'
    'R8?kpPvQ5svFtbF#D?AGX(~mp*0osiC-5IQ85Z<ZG9sO>u<F!9T{KO%7Cp|dVJq_b_*3QYk3X{)Go*MjE!J^*XJ!B|!NrPX5Mdg}'
    'GG<M0R?MdrpI3|M=UsIvV@=JdBJeVe24fL&Jf7Bj#-%|nGEzEvvhBEc;m1(&8qu(!bk;Nora&KkjV4@&kR)XSKIE9FL0m-WGvu2r'
    'i|@;>o$yV;H~$)_y`BN`l4wbx7HFMhL<Q3h0Zov9r%g`y_f=Q2%Pzkd_Ha1*Z3+z&Ma<HM6EpTIf+TwfZ3H%~yu<39D@R#z*ydI@'
    ';g8^tdYnR(l|rT$=@66O@Wph5x&G#Pzjx7<NAo7Op>7K~(B?CjeW}%Cb}YbfF3sV<o}<{N=2TR-TpQGo`6iL>Z4+nujM{NaVOs_8'
    '=az)M60i_!>YQueH_^*C=s149VzRz&-4%~jEI)3jdpj)|951$uUBvFN2J(S1i)}*;6)rInw0Y;+Z>mBm+2v(jghmd<<WfCLzdm>;'
    'p;aMqG>(rhBPR@-yPeA}_kV0SW|?~k(}uAN$k07GPQy}J`(M&KQlS#(!U}dScbHcTrs3C%fpP(;Yvaez>@4sIJ(ey?)DE!gX%AsH'
    'D+S#9Ih`6V59w98csZkor$fWQnA*Q8W`2L+mrT8FOg8R}l0u5z4|^B><@MX;Z>SDi!<c<drJjctf!`!SZxeZK7%=i8i}@|h&h<`1'
    '$nKuMK_D(ZU|pOcq@SU8EEzgA<^lI1Zjut`pty(|Qh;Uex^MK`?N^&4*#!{5$WpNM5mCm#T2wG1WYE@GwVQD<UA^+oNae`toM0U!'
    'Kf01)gi&d!{cWTXrY$))RpYYhhy8v1<MG#xKIYo2b-}Zu??Znx5>4~fU{i}37Mx$BJ*vG?BId1cD54yia7ZS|cJUFb@!4|&fWt)!'
    'DXi)o@4DK%-s}C#VVzTYxhyn#DLiO{mKOqEuv#B2{FuK9jAz`eT~qA-p56w3E`#OwDL(<)LQ@J~=zx@C6ci?bSt?xicyqxZRLx+Y'
    'ojdr!A$iyG#u-U(c<~_oa#IaI+CcDtd2YWHD2$$%NenxeKl>tcR=<Dwx`76S*n=l6M@2drT}f6+>QnJqACBvOjmS=_vUB0*3B0rc'
    'D#7gCwKEdt6ke!2FROqZlm{4CD%1#@ZF$Xtp7G|v#XE=&7xp4UeP>6j&G4ony#0kOk~%n>>#*OwZZN4}c{>1VuwkfmmBXOuHV}w#'
    '8WzDgRFFYYV_SM`_D1RN?nOTsQC<G&)DTnC#w-s<*_TYH4;=@c`o?|goH4=)cJCd0!fb)$f8aU(x{<*PhWyHcn+1A^c~x>s^U4=N'
    '#&&`?$^T(*E`9FDtoc>ikiAx6C@A-6!tqbTO6?tXt}8*4h)@(&Fs8jF%c;qI`L}we>_Hc<Lnb1rIRmFQhEodQ;YPjz0IHk$suk~W'
    'W-i``5Lmv79L!@nuaOll3(I557E$>#(`z*D$jh!<^_1}(o{u~9yoLl(fBT6=NT=Fh^h95vS3$W<A~SI{59RLP&ARNg{^iVv`<)Vy'
    'OBv~>1GS#2Rlq^tr*Z2OH$8LO8%ACqS19rIF$gUi9Rb8_kCi=fIPpnxYA0K*p#Kp)5=iP2v1RW~aq`gIS28%I=6aQAWNUUgBSSOV'
    'n1jv|ZbhZRcbqKyz2(ZuFfxoppN1Xo+NL7~i`aJ@vjkS6xVyQD*(4#t$X8nCyp<VH1wQ=#bb7;|@BEdu`P~L-rVs9(b~C+V(?T1V'
    'xw7$UV<bzIOKKSE!Tg$q-zHU^M~+<n)atP6=1b?M!aw(OApzlaP{kmND#nA0<3(}R`e&#9eb)71lI6*V_zsgyhqE=KC#bJ^Oc#}x'
    'P4wCMrd!`%c5p@{?!(LciS-M#V8f%6?@dQsrXj-m4o@19Dn5xkM)zO}L)^w@lbi6DJ?vW8W7ggu18k$M(Q`u8a<HStsz<~zC~S_)'
    'sk(aM__sHxA&fQPnKBkEMkO*6Qjo6p6lnwtpdc8Ui?elyoaV>u`qaWY$F$!CQ0gf8;s}YzP}MuB56|re`#GrV8!J8@9tlyl5;3Jy'
    'U@l`!jjUoo!CL+sjv+4@Q5B<&ylr#zv$2&wUQodsp-Rv+t%kA;cE%hgk2>b6VHq|66EwZq1PB!P%E^SF;NWFrIzbDuFv1LIiX$6y'
    'C4#h!`ZaDInv-|KdRA6qz^UJ~q3eN4vf@@N$~yge<LJ$P5W{dEg=iqXNSSZ?4L@s9e;d9JWc>8@v%lN^?H-y)+dYIuLX7sRVyrC`'
    'gp*8RB4mspsAqDPahnahXG432DpD|WXeFRi%~KP#F|<M5CoP62^CyY%1o$$=hqkltBN+{gGLxAY4TmI}`w%zUy*y+orA@^hQ*P?4'
    'FYja>|M)l@Hs%rLvq@tb{ZWV(5ed`=INZt1PV;esiiZ2O=^Jz23Vc0k-#xy$1`nEhzy+E|ts##t6N08J5QZ_dRcOoNP(4ih7JiA!'
    'm)PD=ig*f}rHQuh7(T&6i2k*tyAb`8=$Xvo)9gdqFt@wcUM0Avt35qEt)nP33%4vx*<d3KjR-aDRf60Rs%hqGs$dTs@GR+~hP`4F'
    'S5laIAT#@cm^Z073$&XxR~D5^9S}6W8`IA1c?&=8;Fs6PtoHo;A{m-mg@QGluP`6*`+WC-{Li6>jE=c!0@o~l#n-0^+y|>@<$y*B'
    'lZ6c05e%<ASgCGd0Jz;1t6%pClA#Jh3I}2$rjaFoMkthrqM(U!*Ar0DsGzM|9uIxF`(a@G{=r08`QX|zgy3jp-gr#t(R0dZ)cX)}'
    'APRs1r)xKGPBC}QLIp;cdpw2qZ9)l==$ls7MP`8e)9XX2+>6b@Snq9N|2!%OpbeWEMYINp1OcZFx-0t{V~Rqxjv>jf-Nyb|tV^iw'
    '#T);ZS}{zAAiN+l>aIDuGu(da=+WG^gEyAW<#NZ&Ewl)XJ4q+$lu@*SlcBd!NwBjiqXRr_qBZ}qg?-&m3ISFp#h9=-jX!k(0)9cz'
    '7KT7;O$I?Z-;|R7`|5wCIIadL8>u(cBpiB78U+L+ifEC^{iA^tIv)6)JF%KRw2d81OI)bDpH$m&Va;}LA8m<Pn>Sz{Lo`e%2G@4^'
    'hxW01G^_C{s;@q<D;5YGo{BI??<0lQ#A6etE?&y+>dnN2*1LTpzv6P>(`IHe?N$dG7q!JoR-0P4mFg%wx!l=T?*XyrA${2vU&3oW'
    '|4_3PVLW4aiD_!`cw|@x5wz-M2N>EULHu+B&*5dabzkVhM~XyssS(nLA9B!JQkcZDt~A+&>tCDA*M^9<>6*Ky2wJ9FMG{$<^`@16'
    'vd(ORxY4sTq5hn%{wm+LuzOl9CfkB+Uxk)N-PqRaHLmUnOXwJ*tM420c5d9q_rb8c9L{lpjY3+A7^7W;8_yW&q?`f?NS7JsErx&='
    '!?l|^_4K6|6Hd}yOsjg@=n%G27sU+Z8_*2<)Ek^a0+7Wx=V3shl~~=nj~MRoux3~;s?G7EdhKn@Hk|V;jLy`dt2J%YM2fq#YxjNH'
    '><_=Qms5sqM-Mv`csN;$szzZE4)|V;$_wX$A`$Ts4a1iN6KM0>wz7vo&cSesA&C6$dEvR{RH0KCn4`X!*E`2_ZLs3Cp$kIK*=ws4'
    'g1Ch{t_y-iEumM>MX1zzanb3XqZ+Bb>gn33@mJBp-7er~B%H@kgBM~M6RhZt@VF-btK+<)mJ8reulmZZ>@&=AJD3tfkBX71M?*Q@'
    'M{XOoztsEA&fL`HwYm0kfB5p%xA1ztP`_b@ZU`FSFTTP$+Nwq$zz`|la>!5{jBFDlG&F)Rd~KHXCBVLiutJUG_ilM|To0RS4nb0<'
    'S)&=O-ZB+~#fV~sG*A>Pq8^$3_1dk7;)o5y!|S8ZWUU2{$7N%Vn?8bWk~9nX2zeA)+ri*Yh3%0cm*|t0(|qkiF{Ae3XIIHz`dFxb'
    'by%-LB|UoF20bmNay-xB+}gy!PcJr6-hW^EhvvrmLas4`&SIKeNcdx<2_sgWJW3z*-I|17Pfc9su{mCQWD&@(V~%5WN_etd;S)nc'
    'N`$=_pXSb|Tf}M-Hi8aQ-@cDc(wO-i{>PYiCQeZ3B1o@G__&y0rWOfKB-+^3_egBvD#b(@KF^SM2G4m6GT=$;=>#Q|a(7I?U5ql-'
    '(GB~!LP22>hzz%}z{M(Dc7$g$iZYS2i&#>v?myXd!!CAe8T6j?ljXrwhFTDY?fO5;)ILg9rURxE@&35FN;^sX?#`0Gtr86fswdu8'
    'qeAV3)7h}C;69_7Yf+Fy=5<0~ymk-Qk+2oQJXb^uC)3S}`bKJ*4Z#s^Vk8j?xR2xN2O&DFZbIi4>GqUGj(C{YFcS!(Oqj|ez-+~|'
    ';S7=84B-uT^#QqN()<*yC``xjQW6|+(7?%*ikRC9<(N2J)x*{4?|BE#XoS#RL$5W8iPO;1wJ7mRM04(4CV5cGh0WQlYSVTpZrjM?'
    'aSiEiw!`%6hU)|X1Fbf`(vZ!00}50~H&&OTDQ3<uL4xUS+sMjO*z;mCNhRNhBopVL6tmw(nuIRC%;4lCsC!IZyf#`q#QK3P24jPK'
    'fFJVn26~{gn8nmUtVMU14QQnEA2F^X58ZCi{Kl(~%DJz4T|=At3PD7%Izd;Xg&S0RtZVyfVl*knql_qTZrjVXt!+k$Am=>Dh8Y_I'
    'k~?h>GPM+z7|wJPzTQPU-nN?)muA;SaKez1Txz)BFpX*jf!DceZTM*GP36IdzxoxeqSJGJzEgY(T~H{-bkZ2FjA=SHb#Ngu#|Jkr'
    '4=zuq8Lv$R9}m;<`%bpQYIsFT!>khoTVgi)Y7Zz6-ftOF1zxV^x(&DN;`Cm=q$3NREpn(q#&|CbP7L1Qn}o>~N-~6-;FrrkLP@th'
    'Wa6jWIENGN9Wlz`@UVrsn5*M%)sT`3O`(=>-}rEi{vks`4<Y8z#>;PdByVT=3UZ8I1<wvTiY1FdW#XygsmjCSC|^>6gPy_8ug=@o'
    '?fgKZ-3^iAyeTFX)p8(BGi|)deQ3CZ%a``j{-&@Ux@kLaj^;}2FMDKDZBP(`x~-n8u>g!r5m1!-QGvsVbhx$lhMUgNnc=(lx#Tes'
    'Wyl!lQ9@{Ex{g6Wa|j|8!9JR>_05)RFXcb)pO6gf!|7NFs%Pyb>;pkDL?|&KlJ+_*GjQtwxtLYg=8fLYm{u%1>O5niH;ak5dH_OL'
    'FuZthK_;$bgiom0NYA_@(7ue->8k5DGV>Ds{xH0%FNf7>V3Ymh#MCjZpbHT?{-n2tFiXD*l+YWTLV?yc*KWvvIU~<&x?q3@i6jPo'
    '^dXUUVq=EEdK?(TQ%uujh$G%yyOI6G;TVZM==%osUYO(9i~ojJvsxt~T-Fk7YJ_W}9Gvd#GC!H-K9~xyv5N>JPH_P0gdT(!K$@`G'
    'sE}I8F(dfXj$gTp3)J4fl$matK5p4M0DaAlHfoGsYrYJtYofq#b6KuEC{f=!9x;h>Ycd1P_>8<HVx%x1jY%2&?qlp5%S|bX8RD3E'
    '-L(kFnPq!-mcEAj&qis3wC!8$!XFDlSp@+RXC;rp+%Nzp%F!zBuiVC2#s9XOO@fXdLXNjqSHU+7K88DmVS)^0psv;^1Z>08%j>tn'
    'K{xc>^21Y|bvbMiwqfnXEJ@VY@Mg!LX<~rAGmE_hpL1xNYY*p%hy0i}Lc?ebyKY~YVrAxQiJQ2<?4R1W<-7~<oxbc`-L(2X7IYVY'
    'sR^-#yd#_xS!T3ifu1>ZQWw<zIw}0M?_sqqJ6V+MfwF^~v-l7>|L~nLvrfj|$EMVJMNIufKM&f*)-JA#NMl$4o1~Du;UVTKQw38|'
    'RyZ@N10*)3ExyXus^7gczF$)3`9d2bkA`5|6ZNx=8g!NPvb3ag{FIP{5#LX7caOVQ-{BJHaAO4FP__mwgZARZlhAnjNZ}0|4T;r~'
    'HrY9UnuY9-e&%X6s16w`eMwU5c**>0jc$xqel$h!vD>t1^Lq|6@7=q9@s2Rz4{S4|-kJMSxM2yvrkD_~sZ7U8nXdcXbo*A^9oX0)'
    'a>CXW(}&@8<g%Ih;2D*n;BwhdL7o+MH-G4QhWF)wB|5heEnQWaf!iZG(*vzjIDEgzXNJRtiCe#G#fVw^lmrCscx7&p5tc67l=L-L'
    'Vh|f6qOchX?U#B}jQqp0dm@DaFe&^Vn;7JyKH(8;NNRl65FnCwj2fuNrq$#RtKuX_A9{oS>{1+pJfDZ9q@is-C%PvwB8#~&td-2}'
    '*{oTASas(OL6eeKJcWkv$<kpa3#h@tl=W=ZjW~d27_qX63;)N$J7zfH>av&NBs+C6X|=%~Ldh5)1+_xC^9E@90SNCceX7Mj{g|+S'
    'dfA#cFE5q_#fVNu6_BGMW^%)^rnm<9aEsHmuJXG#qMC9!K7EUxAz8?9|HuE>&>w*b%#l~fWg@?BWem1A=^E7`kD#$Szcue$+5WiR'
    'nKc;*$d-ve*U(Uz@bT|}**y0|1-Y*@M3T%~IO^?%E87*zp7H+ewWA|xE@O(LLr19n61M%d*~}cumIQ0I3m?|CYrlcpJGKDlz!OKq'
    'Qw8aJg+;1Kn&Fl}kex!9kz!KyyI-}c=Oy;=NqM*!OZ#8HJRct}{9^bgJ}#zF3@0Jz>%(WBh%snqfG;}21yA(d9LFlZAZ2`7+ni9g'
    'pMS<b-aXk8YAWn11Fb+x)p{qGykTG+iWRk684&6Focx#rdY-QR{3(WS{@2UzFPCNv6+OgEi+A<}i4m0C(&;A54Ecl66^R_h`%*R`'
    '@YCCm{J9|GFNP3BxYTRhHhzXkTt~Xrha<QY4kiR^)-p={rPYE@9e?*}#o9NzQncbo9_*&o3p$l%AfoN59JC2*Tz41)m-u(<re}H8'
    'Cwz|REu0Hie{y&Jle_Px1((y8ItCb{w6MSAC1N}qj)NJDa+lybfMD=({ImBq@%{HcMPK%5I}lP=s|Y&4c^(2E$qL^*!u`rn3pM)?'
    'W>g03{p<^hmh0zn_|<p%{XcF5-EfpQJXQsu8XAZ&N%mWeCN3D0$e)K0x36}rbsDbu@_!%yuXMl0ga31Q`MQC@x>)h^CEN<3z+%TZ'
    'mGiI;#0!Aj+irheke*i8B$>W`I<qr~5s#1C@=F$kcp?<F5flo9gej(9@rxGkP2(U$q<sA;`SWLMp8vYRs1w^`pq<H02F(Z1O@(G0'
    'V?=vXENN_kF+a@<e_ZmE<$qoobQ{yRO-;p_bHNqib41)YNLo<EXqCd>gdhdybl$h#ED65+!ItakP$}|iLr>Gb=Ltx|P3K8A#<xEU'
    '>c>whX+K%-%d0tx8_%=shv<sJ8(o(&K{7O~Gu=ND3nmw01MY0UZ#@QSFIz)Ln;4bE@Xrr2+FbPWd}B;U#KLh5>)IFyJH2}(r^Ba{'
    '(ZTcQuZM-XIo$3vx9#z`5e+!Ok)-lfWE)GR4D${@I3Wop4^zZc7L=eBJC=^MwmA_-+nWi;xI6qoS#@w&1j>-+YF?E?D43X~)<4xx'
    '{l|h&E0DZpj2+^_3Hdk+-x6lZ)VOH4#IVd^6>eCu?v^r3J63#s++^k}4NC-cpl2Uc7i~Fly^7YpP4G})OQw?QhWA#RQy6TcH~%5Q'
    'b^4#ft!wj4R^k3d1|jt^6BV%15U99UP`&Grno|IKv-wr48k=y~sF}uaW!I4)8MUNaLkV7njYiC7!s{?euFkV`)v}ux*c38;eJiBu'
    '6x<aC3IhsQ*eU^9+hE4U)Q<d`MNhT(<=ceXC}96^^EDj8fyH4_F+$P^k0ri%tNNVTd&}YteOiylr+>bJIhMm|K=Y25E1gHf<kk)7'
    '4KI{%M#a~lc2O~gb7klpruU!ndn@mui4ZPuwGk1-S(baaA&g(7f#H)9iWj!a+^dSKfA!a`z{I$iypVo@|44YDYACqboZ2y38rtld'
    'EgBv3wF~c<TdPXcglpJG^pabHadh={EY(too^9us6ZtJawTwJ1{rvozJ|V!!URL|Y$CqJCu23U9`-0r5GA1OgA{+#K+8($Yyyk+I'
    'h4*p4Yt8LDPP+h|x*A%>41@tgOx_8UL(S@H1?dznAi40a<@Q{0AXj`$6I@JNU)br2SI!dsgT4tQVALmSxe9eV7kt^uJW>0oV|n~j'
    '<AkffS*V^R$F(@co~AxxfU)l;MQ4oRlw<G6iR|62;(~F9FJVK@+yuy>%oqQ4aq&Y`8r81l9$nvx!HwYx#j5v1(;|~Msy7@iGJkJw'
    '6eI8mzj+wvcDq*mnLEH=;=DO8zI(|}j0XhbBjV=)16IMM3?<?cnDV%5vC}A^4H6WoR3F2dnLam|6wquKzS=fQM799BD8AQsPs2H`'
    'zx{R3T)!Yq(^v$S+6QOWC9XrkdI8F+C=0yTUWV@dCFMVdh^L>{&*k~eJY>TvChwxP?agUR_)I)RKivOfAk0-3#xXwK_Ucu)$6;{d'
    'HBgA0SQ@_sFeS6a;o*x+P>qv^1|gOCX@6#8X-)n4xGY;TdQPppaAgY8zi5Z)^AAC7@3fK!a=tL`pZBj$Cit)Cpd3EFZg4;i853y{'
    '`*=%N{H|tIq1TJ}CqdH?A_6h8eE-VZ;b9>fk!x!Cz>qO+vSjKw3wagkSjMHs;Jp}@<%%_}^Up2592A{>7F#d#t2rRWOb-N;#G(N6'
    '6pr78IZk%%qG#Fo^F~*O+>mZXM}`Aq8N#ZF5*kE~63~ZV0qsWJ?_WGJhMi-?Vrpp?u1At>H<>iS^}71U=5e0cNYE-|?}w}ZTpaeO'
    'GxRc?gk8U1j$R}fQ3Nx7t^+jVUDrSy3{w-uwEq|f#JL`>c-s$;-(uxwvr{)_*)jYXvKZYKL_EW~f`vAQO`>}N4NjW@_yGFezxMey'
    'I!Ws`*ofo>s}4SedplrD(padb4T9imLL#CC7^Xb?7mq)``<}2Lwz#u(U;*AW8jRx|B+QyU182%23O@d8<aK$S_OBoQl*_%q@)q1a'
    'tt`#Y=MeYyr=L&a+|TE9;cynK9`?1_4EWQXPsm+pPDP~mP*!2EM6~4%m$)5xqjmegf7^dHoOf=$fi}~)Li2De@Q=oT5@9qt9{9@K'
    'I+RR4_C1%#$p!PBVEPvuc^RXAZVvH|*UN*+#1q;MlJn5_#=tASSKXdZJXA(>nrp{lM;(^JY1{cxVZtoT<{Y$I25L0oS?7$AZ{e8j'
    'iD|pRHvI~BQD%&;#4F6Ml@l?JO(qt8fvl%fSlqq~4aE%3WB|kEfXSDa+OG=9HqRq~K?sHrR9hSsgtjTDyuieFE6kId(5EqoA;Z(2'
    '-^Hs`rx8*)bbwezj@&YOV{J@$hCBrsUkByg{QUXp%Xqi-vzi!^9;^?eY2yAVB0<kIZQOsre=TMP4yk<iV1?l7(+ONp%yB=@hh-g}'
    '_;T3ja7tWtnYf_Q_=Lk`TtPVD>{J6nFx*vw2Zk>8F1(q{#kh{((fT@>#10XJP4ni-6Jln3AC)7xq-*vr_?Mdbavd_o*y+ws>zS3i'
    '-K35wMlVev%WGo@l23Koz49jfV+dyq?S(5z)X>VgUtnBN(%=j5xenw>bveD8sIP0iS<ZYO*5=8EODW!#+RA{o;L;Z%$pF))K!-&g'
    'a&?Lg`ONzt>tB}?Ti?2im%TNhlD?rKNe>zAVEA*^2zq7kxz_WDZqnrY7X7Y3zI-Z4I<uH!4)5kH6C~^~t%UUh!+DT}rjpOouy4&B'
    'P>Z2LY*a`U%op+vvr2Sx)7VDAoCH`2^Aaz1--3Zae~V~$IgD#{H4#vCXv!G37ZXg;qm;8u?}8u?g(<Uo=b9^zcu(U^Z_s>e9}g2Z'
    'T7*7C_1aLr9zc&fi|H*M({kmy8+8YbLCkOR1t$u2fQLM+^LxQ))HE6yy*j?RZb=;F!-ngt6f=l3(oNG&qO}Ppz<P+`dlBT>fk1Gt'
    'UG^=j*?=narvcLPTtiUo!_NbQ6S2p*pDYZ*C?30h-`bnNh)my{BKB8h^fE$C3By~$Pgeu3j(KP(X!*E%wN1hhfPjWI4_z-L8cf(s'
    'vPYyae2?IN#jqQ5gR84n{MqE5ze4Wp#bZ#9v4X^DB~D)!+)YKCQOW9BIz3}%cE+M->F0R7Jfl*fYG_~=^s@MX*ERxfbx@m8!s4EB'
    'f`@*&YQ?)v)R|z&XrzR5HL))R^oFTFrxa-}3ms4%ShoN9kjjl^cd=FVQdunUN0E-<Vd=ECLu4>iL#9#1$Z4kURncF!{HnRwV4<lu'
    'paOtI;6(JO`KN}{D1bt+Y9mPb)8@K$Pl|@ii4s7MryKfaD?XWuglx#`ghomY7Zb1Jc@*zwX#ckGnug+Vp7lr@#j5Lc3d>U&1BM}l'
    'rbwYj4zV=Vm`a+yZ||$#jQ(yJbeS^loIK{}Fy<w!q})KPsiL`KBnGtcKWfwe^?&?7_}&-v'
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
