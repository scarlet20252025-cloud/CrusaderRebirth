# 伤害公式的二进制级还原（IL2CPP / ARM64 实证）

> 本文所有结论均来自对**运行时解密后的 `libil2cpp.so`** 的 ARM64 反汇编，
> 并与 `get_battlesettings.json` 的服务端数值表逐项交叉验证。
> 不是推测，每条公式都标注了指令地址。

---

## 0. 前置：如何拿到可读的代码

游戏用 AppGuard 加固，`libil2cpp.so` 磁盘上 `il2cpp` 段前 14.35 MB 熵 7.99（加密），
其余全 0x00。解法是**从进程内存 dump**（内存中已被 loader 解密）：

```
adb shell  dd if=/proc/<pid>/mem of=/data/local/tmp/p_N.bin \
           bs=4096 count=<blocks> skip=<offset> iflag=skip_bytes
```

拿到内存后建立 `类名+方法名 -> 代码地址` 的映射链：

```
Il2CppMethodDefinition.token (0x06xxxxxx)
  -> RID = token & 0xFFFFFF
  -> 按 declaringType 二分定位 Il2CppImageDefinition
  -> 匹配同名的 Il2CppCodeGenModule
  -> methodPointers[RID-1] = 绝对 VA
  -> VA - 0x400020C00000 = 模块内偏移
```

- 运行时基址 `BASE = 0x400020C00000`
- 共解析出 **99,404** 个方法地址（Assembly-CSharp.dll 独占 74,561 个）
- 4 个 PT_LOAD 段的 VA→文件偏移 **delta 各不相同**（0 / 0x4000 / 0x8000 / 0xC000），这是最大的坑

---

## 1. 主入口：`BattleUnit.HandleDamage`

- 地址 `0x291DF2C`，函数体到 `0x291F8D8`，**1643 条指令**（不含尾部分支）
- 调用约定：`x0 = this`，`s0/s1/s2 = 三个 float`，`w2/w3/w4/w5 = 四个 int`

关键寄存器在函数开头的绑定：

| 指令地址 | 指令 | 语义 |
|---|---|---|
| `0x291DF54` | `fmov s8, s2` | **s8 = 第 3 个 float 参数**（原始伤害基数） |
| `0x291DF58` | `fmov s11, s1` | **s11 = 第 2 个 float 参数**（穿透/附加量） |
| `0x291DF60` | `fmov s9, s0` | **s9 = 第 1 个 float 参数**（伤害值） |
| `0x291DF78` | `mov x23, x0` | x23 = this（受击单位） |
| `0x291DF70` | `mov w25, w2` | w25 = 参数 2 |
| `0x291DF68` | `mov w21, w5` | w21 = 参数 5 |
| `0x291DF6C` | `mov w22, w4` | w22 = 参数 4 |
| `0x291DF7C` | `str w3, [sp, #0x44]` | 参数 3 存栈 |

`w24`（伤害类型）取自 `[sp,#0x44]`，在 `0x291E18C` 载入。
后文的分支全部以 `w24` 为判据：

| w24 | 含义 | 证据 |
|---|---|---|
| 1 | 物理 | `0x291E9F0` → `bl get_Defense` |
| 2 | 魔法 | `0x291E8CC` → `bl get_Resist` |
| 4 | 真伤/固定 | `0x291E8BC` → `cmp w24,#4` 直接跳过减伤 |
| 其它 | 无属性 | `0x291EB14` 直接进结算 |

---

## 2. 防御减伤的核心公式（**本文最重要的发现**）

### 2.1 计算函数本体：`0x2936288`

这个函数在元数据里的名字是 `t_ShouldNotifyDebuggerOfWaitCompletion`（CLR 内部 stub 名，
被 IL2CPP 复用/混淆），**它的真实语义是「防御 → 伤害倍率」**：

```asm
02936288  fsub   s0, s0, s1        ; s0 = 防御 - 穿透
0293628C  fmov   s1, #1.00000000
02936290  fcmp   s0, #0.0
02936294  b.ls   #0x29362a8        ; 若 (防御-穿透) <= 0 → 倍率 = 1.0
02936298  adrp   x8, #0xe49000
0293629C  ldr    s1, [x8, #0xf6c]   ; s1 = 294.117647
029362A0  fadd   s0, s0, s1        ; s0 = (防御-穿透) + 294.117647
029362A4  fdiv   s1, s1, s0        ; s1 = 294.117647 / ((防御-穿透) + 294.117647)
029362A8  fmul   s0, s1, s2        ; s0 = 倍率 * 原始伤害
029362AC  ret
```

### 2.2 常量 294.117647 就是 `1 / 0.0034`

`0xE49F6C` 处的 4 字节是 `0f0f9343` → float **294.117645264**。

而 `get_battlesettings.json` 里：

```json
"DEF_INCR_RATIO": 0.0034
```

`1 / 0.0034 = 294.1176470588` —— **完全吻合**。

### 2.3 于是公式是

设 `D = 防御`，`P = 防御穿透`，`dmg` = 减伤前的伤害：

```
eff = D - P

若 eff <= 0:
    multiplier = 1.0
否则:
    multiplier = 294.117647 / (eff + 294.117647)
               = 1 / (1 + eff * 0.0034)

dmg_after = dmg * multiplier
```

**等价写法**：`减伤率 = eff*0.0034 / (1 + eff*0.0034)`。

### 2.4 数值感受（按上式算）

| eff（有效防御） | multiplier | 减伤率 |
|---|---|---|
| 0 | 1.0000 | 0.00% |
| 50 | 0.8547 | 14.53% |
| 100 | 0.7463 | 25.37% |
| 200 | 0.5952 | 40.48% |
| 294 | 0.5000 | 50.00% |
| 500 | 0.3704 | 62.96% |
| 1000 | 0.2273 | 77.27% |
| 2941 | 0.0909 | 90.91% |

即**每 294.1 点有效防御，伤害减半**。这是标准的「除法减伤」而非「减法减伤」，
所以防御**永远不会让伤害归零**，且收益递减。

### 2.5 `DEF_UPPER_BOUND = 100` 的作用

`battle_settings` 里的 `DEF_UPPER_BOUND: 100` **不是**给上述公式用的上限
（否则 294 点防御就永远到不了）。它是给**属性面板/成长曲线**用的显示或成长上限，
与减伤公式无关 —— 因为减伤函数 `0x2936288` 里只有 `294.117647` 一个常量，
**没有任何 100 的比较**。

`DAMAGE_DECREASE_MIN_CAP: 0.2` 才是真正的伤害地板（见第 4 节）。

---

## 3. 魔法抗性：完全同构

`0x291E8CC`（w24==2 分支）与物理分支逐指令同构，唯一差别是取 `get_Resist` 而非 `get_Defense`：

```asm
0291E8CC  mov   x0, x23
0291E8D0  bl    #0x2918e4c        ; get_Resist -> s0
0291E8D4  fmov  s1, s11           ; 穿透
0291E8D8  fmov  s2, s9            ; 伤害
0291E8DC  mov   x0, xzr
0291E8E0  bl    #0x2936288        ; 同一个减伤函数！
```

所以：

```
eff_rst   = RST - PENETRATE_RST
mult_rst  = 1 / (1 + max(0, eff_rst) * 0.0034)
```

**物理与魔法共用同一个 0.0034 系数，共用同一个减伤函数。**

---

## 4. 伤害地板：`DAMAGE_DECREASE_MIN_CAP = 0.2`

`0x291F00C` ~ `0x291F048`：

```asm
0291F00C  mov   x0, xzr
0291F010  bl    #0x2b9fdb4        ; get_Shared  -> 全局配置对象
0291F014  cbz   x0, #0x291f6ec
0291F018  ldr   s0, [x0, #0x6c]   ; s0 = DAMAGE_DECREASE_MIN_CAP = 0.2
0291F024  fcmp  s0, s11
0291F028  ldr   x0, [x29]
0291F02C  fcsel s10, s0, s11, gt  ; s10 = (s0 > s11) ? s0 : s11  = max(0.2, s11)
0291F048  fmul  s10, s12, s10     ; s10 = 减伤前伤害 * max(0.2, s11)
```

`s11` 是累积的「保留比例」（由 `1 - 减免率` 逐步相乘得到，见 `0x291EE58`：`fsub s11, 1.0, s0`）。

结论：

```
最终伤害 = 减伤前伤害 * max(0.2, 保留比例)
```

**任何减伤叠加到极限，也只能把伤害压到原来的 20%，不可能免伤。**

---

## 5. 属性构成：`get_Defense` / `get_Resist`

### 5.1 `get_Defense` @ `0x2918D1C`

```asm
02918D50  ldr   w8, [x19, #0x14c]   ; 某个标志位
02918D54  cmp   w8, #0
02918D58  b.gt  #0x2918dcc          ; 标志 > 0 → 直接返回 0（防御被无视）
02918D5C  ldr   x8, [x19, #0xb0]    ; x8 = 定义对象
02918D6C  ldp   x20, x21, [x8, #0x80]   ; 基础防御
02918D8C  bl    #0x2269a14              ; 取 float -> s0
02918D98  ldp   x0, x1, [x8, #0x180]    ; 装备/词条加成
02918DA4  bl    #0x2269a14              ; -> s0
02918DB0  ldr   x0, [x8, #0x280]        ; 倍率
02918DB4  ldr   x1, [x8, #0x288]
02918DC0  bl    #0x2269a14              ; -> s0
02918DC4  fadd  s1, s8, s9              ; s1 = 基础 + 装备
02918DC8  fmul  s0, s1, s0              ; s0 = (基础 + 装备) * 倍率
```

即：

```
Defense = (基础Def + 装备Def) * 倍率
```

`[x19,#0x14c] > 0` 时直接返回 **0** —— 这是「无视防御」类效果的实现点。

### 5.2 `get_Resist` @ `0x2918E4C`

逐指令同构，字段偏移整体 +0x10：

| 用途 | Defense 偏移 | Resist 偏移 |
|---|---|---|
| 无视标志 | `0x14c` | `0x150` |
| 基础值 | `0x80` | `0x90` |
| 装备加成 | `0x180` | `0x190` |
| 倍率 | `0x280` | `0x290` |

```
Resist = (基础Rst + 装备Rst) * 倍率
```

---

## 6. 完整调用链

```
HandleDamage(this, s0=dmg, s1=pen, s2=base, w2, w3, w4=type, w5)
│
├─ 0x291DF2C  序言，保存 s0->s9, s1->s11, s2->s8
│
├─ 0x291E0A0  早退判定
│     [this+0x3f0] == 0            -> return 0
│     [this+0x488] == null         -> return 0
│     s9 <= 0.0                    -> return 0     (0x291E0E4 fcmp)
│     [this+0xb0] == null          -> return 0     (0x291E0EC)
│     [this+0x25] == 0             -> 跳 0x291E12C 继续
│
├─ 0x291E12C  目标校验
│     [this+0x28] != 0 && [this+0x30] != x24  -> return 0
│
├─ 0x291E194  遍历 AddState 组 0x29（受击前回调）
│     for each addstate:
│         if !IsValid      continue
│         GetIsActable(...)
│         RunCallback(...)
│
├─ 0x291E2B0  x22 = GetUnit(...)；若为空跳 0x291E85C
│
├─ 0x291E31C  遍历 AddState 组 0x4d（防御类被动）
│     for each addstate:
│         [ad+0xe0] 与 [this+0x98][0xa8] 交叉校验
│         按 w24(类型) 分派:
│             w24==1 且 [ad+0x178]==0xc  -> 取 [ad+0x70]  (物理防御修正)
│             w24==2 且 [ad+0x178]==0xd  -> 取 [ad+0x70]  (魔法抗性修正)
│         s11 = s11 + get_Defense()*val    (0x291E454 fmov s12,s0 / 0x291E47C fmul / 0x291E484 fadd)
│
├─ 0x291E530  遍历 AddState 组 0x07（伤害倍率）
│     s12 = 1.0
│     若 [ad+0x174] != 0:  s9 = s9 + v        (加法区, 0x291E618)
│     否则:               s9 = s9 * (v + 1)  (乘法区, 0x291E638-0x291E63C)
│     InvokeOtherAddstate(...)
│
├─ 0x291E758  按 w24 取 [x8+0xf0] / [x8+0x100]（受击方/攻击方修正）
│     s9 = s9 * (val + 1.0)                  (0x291E854-0x291E858)
│
├─ 0x291E89C  全局修正
│     若 [x0+0x10] != 0:
│         s9 = s9 * GetCurrentRevise()       (0x291E8A8-0x291E8AC)
│
├─ 0x291E8B0  按 w24 分派减伤
│     w24==1  -> 0x291E9F0: s0 = get_Defense(); bl 0x2936288  (物理)
│     w24==2  -> 0x291E8CC: s0 = get_Resist();  bl 0x2936288  (魔法)
│     w24==4  -> 跳过
│     其它    -> 跳过
│
├─ 0x291ECBC  遍历 AddState 组 0x04（附加修正）
│
├─ 0x291EE1C  减免率累积
│     s11 = 1.0 - [this+0xb0][0xd0]          (0x291EE58-0x291EE64)
│     遍历组 0x05:
│         s12 = s12 * (1.0 - v)              (0x291EF74-0x291EF7C)
│
├─ 0x291F00C  s10 = s12 * max(0.2, s11)      (伤害地板 20%)
│
├─ 0x291F198  遍历组 0x06（最终伤害改写）
│     GetResultDamage(...)
│     RunCallback(...)
│
├─ 0x291F2BC  负值钳制
│     fcmp s10, #0.0 ; fcsel s10, 0.0, s10, mi   (0x291F2C0-0x291F2C4)
│
├─ 0x291F2C8  距离衰减（w24 != 4 时）
│     w21 = 0x42a00000 = 80.0f
│     s0 = GetDistance(...) / 80.0           (0x291F3A8-0x291F3B0)
│     若 s0 < [ad+0x6c] -> 走 0x291F5C0
│
└─ 0x291F540 / 0x291F57C  bl BlowDamage(...)
      s0 = s11, s1 = s9, s2 = s8,
      w2 = w21&1, w3 = w24, w4 = w20, w5 = w19
      ; 之后 0x291F56C: s1 = s10 - s11 ; s0 = s1 + s0   (计算溢出/吸收量)
```

---

## 7. `BlowDamage` @ `0x291F948`

```asm
0291F948  sub    sp, sp, #0x160
0291F974  fmov   s11, s2
0291F978  fmov   s10, s1
0291F980  fmov   s8,  s0
0291F98C  mov    x20, x1
0291F990  mov    x19, x0
0291F994  str    w5, [sp, #0x58]
0291F998  str    w4, [sp, #0x64]
0291F99C  str    w2, [sp, #0xc8]
0291F988  mov    w22, w3        ; w22 = 伤害类型
```

签名：

```c
float BattleUnit::BlowDamage(BattleUnit* target, float dmg, float a, float b,
                             int32_t flag, int32_t dmgType, int32_t p4, int32_t p5);
```

与 `HandleDamage` 的调用点完全对应，可以确认 `HandleDamage` 是「算」、`BlowDamage` 是「打」。

---

## 8. 反推：为什么伤害表里 `value.target` 会写 `HP`/`Def`/`Rst`

第 2/3 节证明了**减伤的输入是防御/抗性，而伤害基数则来自 `s0/s2`**。
`HandleDamage` 的 `s2`（→ `s8`）在整个函数里**只在最后传给 `BlowDamage`**（`0x291F550`、`0x291F580`），
中途从不参与任何算术 —— 这说明：

> `s0` 是「会被告减伤」的那一份，`s2` 是「原始基数（供结算/统计/反伤用）」。

这正好解释了数值表里为什么会有 136 种 `handler × value.target` 组合：
handler 决定**用哪个属性作为倍率来源**（`AtkDmg`/`HP`/`MAXHP`/`Def`/`Rst`），
而 `HandleDamage` 只负责**把这个结果按防御/抗性打折**。

---

## 9. 已验证 / 待验证清单

### 已用二进制证实

- [x] 物理减伤：`1 / (1 + max(0, DEF - PEN_DEF) * 0.0034)`
- [x] 魔法减伤：`1 / (1 + max(0, RST - PEN_RST) * 0.0034)`
- [x] 物魔共用同一个减伤函数 `0x2936288`
- [x] 减伤常量 294.117647 = `1/0.0034`，位于 `0xE49F6C`
- [x] 伤害地板 `max(0.2, 保留比例)`，来自 `DAMAGE_DECREASE_MIN_CAP`
- [x] `Defense = (基础 + 装备) * 倍率`
- [x] `Resist  = (基础 + 装备) * 倍率`
- [x] 「无视防御」通过 `[unit+0x14c] > 0 → 防御返回 0` 实现
- [x] `w24 == 4` 完全跳过减伤（真伤）
- [x] 距离衰减常量 `80.0f`（`0x42a00000`）
- [x] 最终伤害负值钳制为 0

### 尚未定位（后续工作）

- [ ] 暴击（`CRIT_PROB` / `CRIT_DMG`）在哪一段生效 —— `HandleDamage` 里没有读取暴击字段的指令，
      推测在 `BlowDamage` 内部或更上层（`SkillCodeHandler`）
- [ ] `HITRATE_MIN_CAP 0.05` / `HITRATE_MAX_CAP 0.95` 的命中判定位置
- [ ] `ATKSPD_CAP 2.5` 在 `get_PrimaryAttackPerSec` 的实现
- [ ] `DAMAGE_REDUCED 0.1` 的确切接入点（目前只看到 `0.2` 地板被显式读取）
- [ ] `LEADER_BLOCK_RATIO 1.75` 的队长块倍率
- [ ] PVP 的 `Damage_revise 0.6` / `HP_revise 1.75` 是服务端还是客户端施加

---

## 10. 复现所需的地址索引

| 方法 | 模块内偏移 | 说明 |
|---|---|---|
| `BattleUnit.HandleDamage` | `0x291DF2C` | 伤害主入口 |
| `BattleUnit.BlowDamage` | `0x291F948` | 实际结算 |
| `BattleUnit.get_Defense` | `0x2918D1C` | 防御取值 |
| `BattleUnit.get_Resist` | `0x2918E4C` | 抗性取值 |
| `BattleUnit.get_AttackDamage` | `0x2AD672C` | 虚拟分发桩（7 指令） |
| `BattleUnit.get_PureAtkDmg` | `0x2AD6748` | 纯攻取值 |
| `BattleUnit.GetStat` | `0x2AD7D18` | 通用取属性 |
| `BattleUnit.CalBuffRatio` | `0x2AD7108` | Buff 比例 |
| 防御→倍率 | `0x2936288` | **本文核心函数** |
| `BattleUnitDefinition.GetBasicAttackDamage` | `0x2CDC270` | 基础攻击 |
| `StageDefinition.GetRatioAtk` | `0x2DA3E7C` | 关卡攻击系数 |

常量位置：

| 常量 | 文件偏移 | 值 |
|---|---|---|
| `1/DEF_INCR_RATIO` | `0xE49F6C` | 294.117645264 |
| 距离衰减 | 指令内立即数 | 80.0f (`0x42a00000`) |
| `DAMAGE_DECREASE_MIN_CAP` | `Shared+0x6c` | 0.2 |
