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

---

# 追加：暴击与命中的二进制级还原

> 本章接在上文之后，同样是 ARM64 反汇编实证。
> 上一章遗留的「暴击在哪生效」「命中率在哪判定」两个问题，本章给出答案。

---

## 11. 伤害结算类 `BattleEffectDamage`

这是真正持有「本次伤害全部参数」的类（typeIndex **990**，16 个方法）。
它的实例在 `BlowDamage` 里被构造、填充、然后调用 `ApplyStatic` 结算。

| 方法 | 模块内偏移 | RID |
|---|---|---|
| `get_CriticalRatio` | `0x295A268` | 7922 |
| `get_CriticalPower` | `0x295A288` | 7923 |
| `get_Penetrate` | `0x295A2A8` | 7924 |
| `get_AdditionalCritialPower` | `0x295A300` | 7925 |
| `get_HitRate` | `0x295A310` | 7927 |
| `.ctor` | `0x295A3F8` | 7929 |
| `Init` | `0x295A50C` | 7930 |
| `ContextSetupComplete` | `0x295A7F0` | 7931 |
| `GetAdditionalFactor` | `0x295B808` | 7932 |
| **`ApplyStatic`** | **`0x295A850`** | **7933** |
| `GetDamageAmount` | `0x295BB80` | 7934 |
| `UpdateDamageAmount` | `0x295BD0C` | 7935 |
| `SetCriticalLogicOption` | `0x295BD14` | 7936 |
| `UpdateSnapshot` | `0x295BD1C` | 7937 |
| `SetExtraCriticalPower` | `0x295BD60` | 7938 |
| `SetHitMissCheckFlag` | `0x295A7E0` | 7940 |

---

## 12. 暴击率与暴击倍率：**加法叠加，不是乘法**

### 12.1 `get_CriticalRatio` @ `0x295A268`

```asm
0295A268  ldr   x8, [x0, #0x10]    ; x8 = 施法者 BattleUnit
0295A26C  cbz   x8, #0x295a280
0295A270  ldr   s0, [x8, #0x6c]    ; s0 = 施法者基础暴击率
0295A274  ldr   s1, [x0, #0x3c]    ; s1 = 本次效果的额外暴击率
0295A278  fadd  s0, s0, s1         ; 相加
0295A27C  ret
```

**公式：**

```
暴击率 = 基础暴击率([unit+0x6c]) + 本次额外暴击率([effect+0x3c])
```

### 12.2 `get_CriticalPower` @ `0x295A288`

```asm
0295A288  ldr   x8, [x0, #0x10]
0295A28C  cbz   x8, #0x295a2a0
0295A290  ldr   s0, [x8, #0x70]    ; 施法者基础暴击伤害
0295A294  ldr   s1, [x0, #0x40]    ; 额外暴击伤害
0295A298  fadd  s0, s0, s1
0295A29C  ret
```

**公式：**

```
暴击倍率 = 基础暴伤([unit+0x70]) + 额外暴伤([effect+0x40])
```

`SetExtraCriticalPower` @ `0x295BD60` 就是写 `[effect+0x40]`：

```asm
0295BD60  str   s0, [x0, #0x40]
0295BD64  ret
```

### 12.3 为什么是「加法」

两处都是 `fadd`，不是 `fmul`。这说明在《克鲁赛德战记》里：

> 暴击率与暴击伤害都是**线性累加**的词条，不存在「暴击伤害倍率相乘」的叠乘模型。

这也解释了为什么数值表里 `CRIT_PROB` / `CRIT_DMG` 的 `Default` 分别是 `0` 和 `1`
（`championstatsettings`）：基础暴伤默认 1（即 100%，暴击只是不额外增伤），
真正提升靠 `+0x40` 那个额外项往上加。

---

## 13. 暴击的掷骰：`Range(0,1)` + 比较

`ApplyStatic` @ `0x295AE18` ~ `0x295AE6C`：

```asm
0295AE18  adrp  x8, #0x5259000
0295AE1C  ldr   x8, [x8, #0xef0]   ; UnityEngine.Random
0295AE20  ldr   x0, [x8]
...
0295AE30  movi  d0, #0                ; min = 0.0
0295AE34  fmov  s1, #1.00000000       ; max = 1.0
0295AE38  mov   x0, xzr
0295AE3C  bl    #0x293728c           ; Random.Range(0,1)
0295AE40  fcmp  s0, s11              ; 掷骰 vs 暴击率
0295AE44  b.ge  #0x295b078           ; 掷骰 >= 暴击率 -> 不暴击
0295AE48  cbz   w25, #0x295ae74      ; 暴击逻辑开关
0295AE4C  cmp   w25, #0
0295AE50  b.le  #0x295aed0
0295AE54  ldr   s0, [x20, #0x70]     ; 攻击方暴伤
0295AE58  ldr   s1, [x23, #0x10]     ; 受击方暴伤修正
0295AE5C  mov   w22, #1
0295AE60  fadd  s0, s0, s1
0295AE64  fmov  s1, #1.00000000
0295AE68  fadd  s0, s0, s1           ; + 1.0
0295AE6C  fmul  s10, s0, s10         ; 伤害 *= (攻击方暴伤 + 受击方暴伤 + 1.0)
```

**暴击命中时的伤害倍率：**

```
伤害 *= (攻击方暴伤 + 受击方暴伤 + 1.0)
```

这个 `+1.0` 极其关键：它意味着**暴伤字段本身是「额外增幅」**，
基础暴击（暴伤 = 0）的伤害倍率是 `1.0`（不增伤），而不是常见的 `2.0`。

`Random.Range(0,1)` 的实现 @ `0x293728C`：

```asm
0293728C  stp   d9, d8, [sp, #-0x30]!
02937298  fmov  s9, s1
0293729C  fmov  s8, s0
...
029372EC  fsub  s9, s9, s8          ; s9 = max - min
029372F0  ldp   x9, x1, [x8, #0x1b8]
029372F4  blr   x9                  ; 调 Random.value (0..1)
029372F8  fcvt  s0, d0
0293730C  fmul  s0, s9, s0          ; (max-min) * value
0293731C  fadd  s0, s0, s8          ; min + (max-min)*value
02937324  ret
```

标准均匀分布插值，**不是** `UnityEngine.Random.Range` 的整数版本。

---

## 14. 命中率：`clamp(1 + 命中 - 闪避, 0.05, 0.95)`

`ApplyStatic` @ `0x295AD28` ~ `0x295AD88`：

```asm
0295AD28  ldr   s12, [x20, #0x88]   ; s12 = 攻击方命中加成
0295AD2C  ldr   s13, [x23, #0x18]   ; s13 = 攻击方额外命中
0295AD30  mov   x1, xzr
0295AD34  bl    #0x29195f8           ; s0 = 受击方闪避率
0295AD38  ldr   s14, [sp, #0x98]     ; s14 = 受击方额外闪避
0295AD40  fmov  s11, s0              ; s11 = 闪避
0295AD44  bl    #0x2b9fdb4           ; get_Shared
0295AD4C  ldr   s15, [x0, #0x58]     ; s15 = HITRATE_MIN_CAP = 0.05
0295AD54  bl    #0x2b9fdb4
0295AD5C  fmov  s0, #1.00000000
0295AD60  ldr   s1, [x0, #0x5c]      ; s1 = HITRATE_MAX_CAP = 0.95
0295AD6C  fadd  s0, s12, s0          ; 1.0 + 命中加成
0295AD70  fadd  s0, s0, s13          ; + 额外命中
0295AD74  fsub  s0, s0, s11          ; - 闪避
0295AD78  fsub  s0, s0, s14          ; - 额外闪避
0295AD7C  fcmp  s0, s1
0295AD80  fcsel s1, s1, s0, gt       ; s1 = min(s0, 0.95)
0295AD84  fcmp  s0, s15
0295AD88  fcsel s11, s15, s1, mi     ; s11 = (s0 < 0.05) ? 0.05 : s1
```

**公式：**

```
命中率 = clamp(1.0 + 攻击方命中 + 攻击方额外命中
                   - 受击方闪避 - 受击方额外闪避,
               0.05, 0.95)
```

`0x58` / `0x5c` 就是 `battle_settings` 里的 `HITRATE_MIN_CAP 0.05` 与 `HITRATE_MAX_CAP 0.95`。

也就是说：

- **命中率永远在 5% ~ 95% 之间**，不存在必中或必闪
- 命中/闪避是**线性加减**，同样不是乘法

---

## 15. 伤害上下限：`GetDamageAmount` @ `0x295BB80`

```asm
0295BBD0  ldr   w8, [x21, #0xb4]    ; 命中次数索引
0295BBD4  ldr   s8, [x21, #0xa4]    ; 基础伤害
0295BBD8  cbz   w8, #0x295bc3c
...
0295BC30  bl    #0x2985418          ; CountWithHash
0295BC34  scvtf s0, w0
0295BC38  fmul  s8, s8, s0          ; 伤害 *= 命中数量
0295BC3C  fabs  s9, s8              ; 取绝对值
0295BC40  ldr   w22, [x21, #0xac]
0295BC88  bl    #0x299f638          ; GetBaseStat
0295BC8C  fmul  s9, s9, s0
0295BC90  ldrb  w8, [x21, #0x188]   ; 是否有上限
0295BCA8  bl    #0x29c7678          ; GetValue -> s8 (上限)
0295BCB8  ldrb  w8, [x21, #0x17c]   ; 是否有下限
0295BCD8  mov   w8, #0x7f7fffff     ; 默认 FLT_MAX
0295BCE0  fcmp  s9, s0
0295BCF4  fcsel s0, s0, s9, gt      ; min(dmg, 上限)
0295BCF8  fcmp  s9, s8
0295BCFC  fcsel s0, s8, s0, mi      ; 若 dmg < 下限，取下限
```

**语义：**

```
dmg = |基础伤害 * 命中数量 * 基础属性系数|
dmg = min(dmg, 上限)          ; 上限默认 FLT_MAX
dmg = (dmg < 下限) ? 下限 : dmg
```

`0x7f7fffff` 是 IEEE754 单精度最大有限值（约 3.4028e38），作为「未配置上限」的哨兵值。

---

## 16. 调用图（更新版）

```
BattleEffectDamage.ApplyStatic (0x295A850)
│   ├─ 命中判定  0x295AD28-0x295AD88   clamp(1+HIT-EVA, 0.05, 0.95)
│   ├─ 暴击掷骰  0x295AE18-0x295AE6C   Random.Range(0,1) vs critRate
│   └─ 暴击乘算  0x295AE54-0x295AE6C   dmg *= (atkCritDmg + defCritDmg + 1)
│
├─ BattleEffectDamage.GetDamageAmount (0x295BB80)   上下限钳制
│
└─ bl 0x291DF2C  BattleUnit.HandleDamage
       │  w3 = 3   ← 注意：这里传的伤害类型是 3，不是 1/2/4
       │
       ├─ 防御/抗性减伤   0x2936288  1/(1+max(0,DEF-PEN)*0.0034)
       ├─ 地板钳制        0x291F00C  max(0.2, 保留比例)
       ├─ 距离衰减        0x291F3A8  dist/80.0
       │
       └─ bl 0x291F948  BattleUnit.BlowDamage
              │
              ├─ bl 0x293E36C  BattleUnitStateSnapshot..ctor（属性快照）
              └─ bl 0x295A850  BattleEffectDamage.ApplyStatic（递归回上层）
```

**嵌套关系**：`ApplyStatic → HandleDamage → BlowDamage → ApplyStatic`。
这不是无限递归 —— `BlowDamage` 里的两次 `ApplyStatic` 调用（`0x2920B64`、`0x2920D90`）
传的是**不同的参数**（`w6 = -1`、`w8 = 5`），用于处理溅射/反伤/多段等衍生伤害，
而衍生伤害的 `w3` 被固定为 `3`，在 `HandleDamage` 里走的是**不减伤**分支。

> 待验证：`w24 == 3` 的确切语义。`HandleDamage` 里 `1`=物理、`2`=魔法、`4`=真伤，
> `3` 走的是和 `4` 一样的「跳过减伤」路径，推测是「已结算过的衍生伤害」标记。

---

## 17. 更新后的已验证清单

- [x] 物理减伤 `1/(1+max(0,DEF-PEN_DEF)*0.0034)`
- [x] 魔法减伤 `1/(1+max(0,RST-PEN_RST)*0.0034)`
- [x] 伤害地板 `max(0.2, 保留比例)`
- [x] **暴击率 = 基础暴击率 + 额外暴击率（加法）**
- [x] **暴伤 = 基础暴伤 + 额外暴伤（加法）**
- [x] **暴击倍率 = 暴伤 + 1.0**
- [x] **暴击掷骰用 `Random.Range(0,1)` 均匀分布**
- [x] **命中率 = clamp(1+HIT-EVA, 0.05, 0.95)**
- [x] 伤害上下限钳制（`GetDamageAmount`，默认上限 `FLT_MAX`）
- [x] 距离衰减系数 `80.0`
- [x] 「无视防御」= `[unit+0x14c] > 0` 时防御返回 0

### 仍未定位

- [ ] `ATKSPD_CAP 2.5` 在 `get_PrimaryAttackPerSec` @`0x29187A4` 的实现（未反汇编）
- [ ] `DAMAGE_REDUCED 0.1` 的接入点
- [ ] `LEADER_BLOCK_RATIO 1.75` 的队长块倍率
- [ ] PVP 的 `Damage_revise 0.6` / `HP_revise 1.75` 是服务端还是客户端施加
- [ ] `w24 == 3` 的确切语义
- [ ] `get_VampRate` @`0x29191DC` 在 `BlowDamage` 里的吸血结算（已确认有调用点，未细读）

---

## 18. 追加的地址索引

| 方法 / 函数 | 模块内偏移 |
|---|---|
| `BattleEffectDamage.get_CriticalRatio` | `0x295A268` |
| `BattleEffectDamage.get_CriticalPower` | `0x295A288` |
| `BattleEffectDamage.get_Penetrate` | `0x295A2A8` |
| `BattleEffectDamage.get_AdditionalCritialPower` | `0x295A300` |
| `BattleEffectDamage.get_HitRate` | `0x295A310` |
| `BattleEffectDamage.ApplyStatic` | `0x295A850` |
| `BattleEffectDamage.GetDamageAmount` | `0x295BB80` |
| `BattleEffectDamage.SetCriticalLogicOption` | `0x295BD14` |
| `BattleEffectDamage.SetExtraCriticalPower` | `0x295BD60` |
| `BattleEffectDamage.SetHitMissCheckFlag` | `0x295A7E0` |
| `BattleEffectDamage.ContextSetupComplete` | `0x295A7F0` |
| `Random.Range`（float 版） | `0x293728C` |
| `BattleUnit.get_PureCriticalRate` | `0x2919040` |
| `BattleUnit.get_CriticalPower` | `0x29190AC` |
| `BattleUnit.get_PureCriticalPower` | `0x2919170` |
| `BattleUnit.get_VampRate` | `0x29191DC` |
| `BattleUnit.get_HitRate` | `0x2919728` |
| `BattleUnit.get_PureHitRate` | `0x29196BC` |
| `BattleUnit.GetCurrentStateSnapshot` | `0x291C3B4` |
| `BattleUnitStateSnapshot..ctor` | `0x293E36C` |
| `PassiveFunctionHandler.CriticalCheckDoOnHit` | `0x29ABE24` |

### `BattleUnitStateSnapshot` 字段布局（构造函数 `0x293E36C` 反推）

| 偏移 | 内容 | 来源 |
|---|---|---|
| `+0x28` | 基础攻击 | `0x293E3EC` `[x20]` vtable `+0x1f8` |
| `+0x2c` | 值 A | `0x293E404` `bl 0x292c2f0` |
| `+0x30` | 值 B | `0x293E410` `stp s0,s1` |
| `+0x34` | 值 C | `0x293E420` `bl 0x4d34b2c` |
| `+0x38` | 双精度值 | `0x293E42C` `ldr d0,[x20,#0x468]` |
| `+0x40` | 攻击力 | `0x293E448` vtable `+0x1d8` |
| **`+0x44`** | **纯攻击（PureAtkDmg）** | **`0x293E45C` `bl 0x2918a50`** |
| `+0x48` | 值 D | `0x293E468` `bl 0x291940c` |
| **`+0x4c`** | **纯暴击率（PureCriticalRate）** | **`0x293E478` `bl 0x2919040`** |
| **`+0x50`** | **纯暴击伤害（PureCriticalPower）** | **`0x293E488` `bl 0x2919170`** |
| `+0x54` | 值 E | `0x293E498` `bl 0x2918de0` |
| `+0x58` | 值 F | `0x293E4A8` `bl 0x2918f10` |
| `+0x64` | 值 G | `0x293E4B0` `bl 0x29192a0` |
| `+0x68` | 值 H | `0x293E4CC` vtable `+0x1c8` |

这个快照被 `GetCurrentStateSnapshot` 的 10 个调用者使用，全部集中在
**技能/被动条件判定**（`CompareStatSelfDoOnFire`、`CheckBuffCasterInvoke`、
`RunWithoutAnimation`、`UpdateSnapshot`、`ApplyStatic`），
不参与伤害主循环 —— 也就是说暴击的实际生效**不读快照**，而是读实时 `[unit+0x6c]` / `[unit+0x70]`。

---

# 追加二：攻速上限与 `Shared` 配置对象全字段映射

> 本章补上上一章遗留的第 3 个问题：`ATKSPD_CAP 2.5` 在哪生效。
> 顺带把承载全部服务端常量的 `Shared` 对象字段表摸清。

---

## 19. 攻速上限：`get_PrimaryAttackPerSec` @ `0x29187A4`

```asm
029187A4  str   d10, [sp, #-0x40]!
029187B4  adrp  x20, #0x5620000
029187B8  mov   x19, x0
029187D8  ldr   x8, [x19, #0xb0]     ; x8 = 定义对象
029187DC  cbz   x8, #0x2918870
029187E8  ldp   x20, x21, [x8, #0x30]   ; 基础攻速
02918808  bl    #0x2269a14              ; -> s0
02918814  ldp   x0, x1, [x8, #0x130]    ; 装备/词条攻速加成
02918820  bl    #0x2269a14              ; -> s0
02918828  fmov  s9, s0
0291882C  bl    #0x2b9fdb4              ; get_Shared
02918834  ldr   s10, [x0, #0x64]        ; s10 = 攻速下限（=1.0）
02918838  mov   x0, xzr
0291883C  bl    #0x2b9fdb4              ; get_Shared
02918844  fadd  s0, s8, s9              ; s0 = 基础 + 装备
02918848  ldr   s1, [x0, #0x40]         ; s1 = ATKSPD_CAP = 2.5
02918858  fcmp  s0, s1
0291885C  fcsel s1, s1, s0, gt          ; s1 = min(s0, 2.5)
02918860  fcmp  s0, s10
02918864  fcsel s0, s10, s1, mi         ; s0 = (s0 < 下限) ? 下限 : s1
0291886C  ret
```

**公式：**

```
每秒攻击次数 = clamp(基础攻速 + 装备攻速, 下限[Shared+0x64], ATKSPD_CAP[Shared+0x40])
```

`[Shared+0x64]` 实测为 **1.0**（攻速最低也保持每秒 1 击），
`[Shared+0x40]` 为 `battle_settings.ATKSPD_CAP = 2.5`。

---

## 20. `Shared` 配置对象的字段布局（全量枚举）

`get_Shared` @ `0x2B9FDB4` 返回的全局单例，承载了所有从
`get_battlesettings.json` 读入的数值常量。用「`bl get_Shared` 后 60 条指令内的
`ldr sN,[x0,#imm]`」扫描全部 **272 个调用点**，得到字段偏移使用频次：

| 偏移 | 使用次数 | 已知语义 | 证据 |
|---|---|---|---|
| `+0x18` | 3 | 未定 | — |
| `+0x1C` | 2 | 未定 | — |
| `+0x20` | 2 | 未定 | — |
| `+0x24` | 8 | 未定（高频，疑似通用倍率） | — |
| `+0x28` | **18** | 未定（最高频，疑似通用系数） | — |
| `+0x34` | 5 | 未定 | — |
| `+0x38` | 3 | 未定 | — |
| **`+0x40`** | **3** | **`ATKSPD_CAP = 2.5`** | `0x2918848` |
| `+0x44` | 1 | 未定 | `0x2F0F2C0` |
| `+0x48` | 2 | 未定 | `0x2F0F2C0` |
| `+0x4C` | 7 | 未定 | `0x2F0F2C0` |
| **`+0x58`** | **1** | **`HITRATE_MIN_CAP = 0.05`** | `0x295AD4C` |
| **`+0x5C`** | **2** | **`HITRATE_MAX_CAP = 0.95`** | `0x295AD60` |
| `+0x60` | 3 | 未定 | `0x29189D8` |
| **`+0x64`** | **1** | **攻速下限 = 1.0** | `0x2918834` |
| `+0x68` | 1 | 未定 | `0x291C328` |
| **`+0x6C`** | **1** | **`DAMAGE_DECREASE_MIN_CAP = 0.2`** | `0x291F018` |
| `+0x70` | 1 | 未定 | `0x2975DD4` |
| `+0x7C` | 4 | 未定 | `0x259B9C4` |
| `+0x84` | 3 | 未定 | `0x291E908` |
| `+0x94` | **23** | 未定（次高频） | `0x2EBE1BC` |
| `+0xA4` | 2 | 未定 | `0x2A1BBDC` |
| `+0xF4` | 1 | 未定 | `0x2930348` |
| `+0xF8` | 2 | 未定 | `0x2930348` |
| `+0x100` | 1 | 未定 | `0x292F218` |
| `+0x104` | 2 | 未定 | `0x292F218` |
| `+0x120` | 3 | 未定 | `0x28D75C0` |
| `+0x124` | 5 | 未定 | `0x2AE5660` |
| `+0x128` | 4 | 未定 | `0x2BA3ECC` |
| `+0x130` | 2 | 未定 | `0x2EC272C` |
| `+0x134` | 1 | 未定 | `0x2956EA0` |

**已确认 4 个关键常量**，其余 27 个偏移的语义需要把
`get_battlesettings.json` 的字段顺序与 `Shared` 的构造函数对拍才能确定
（`BattleSharedData` 的 `.ctor` 尚未定位）。

> 注意：`Shared` 的字段偏移**不是** JSON 里的字典序，
> 而是按源码里 `public float xxx;` 的声明顺序排列。
> 因此不能靠 JSON 顺序推偏移，必须从构造函数逐字段 `str sN,[x0,#imm]` 反推。

---

## 21. 三份常量表的交叉对照（最终版）

| JSON 键 | 值 | `Shared` 偏移 | 生效函数 |
|---|---|---|---|
| `DEF_INCR_RATIO` | 0.0034 | 未用（编译期常量化 294.117647 @`0xE49F6C`） | `0x2936288` |
| `DAMAGE_DECREASE_MIN_CAP` | 0.2 | `+0x6C` | `HandleDamage` `0x291F018` |
| `HITRATE_MIN_CAP` | 0.05 | `+0x58` | `ApplyStatic` `0x295AD4C` |
| `HITRATE_MAX_CAP` | 0.95 | `+0x5C` | `ApplyStatic` `0x295AD60` |
| `ATKSPD_CAP` | 2.5 | `+0x40` | `get_PrimaryAttackPerSec` `0x2918848` |
| 攻速下限（JSON 无此键） | 1.0 | `+0x64` | `get_PrimaryAttackPerSec` `0x2918834` |
| `DAMAGE_REDUCED` | 0.1 | 未定位 | — |
| `LEADER_BLOCK_RATIO` | 1.75 | 未定位 | — |
| `SR_DEF_REVISE` | 1 | 未定位 | — |
| `GREY_DAMAGE_FONT` | 0.5 | 未定位 | — |
| `barrier_refill_amount` | 0.1 | 未定位 | — |

### `DEF_INCR_RATIO` 的特殊性

它是唯一一个**被编译期常量化**的键：`.so` 里既没有 `0.0034` 的 float32，
也没有 `0.0034` 的 double，只有 `1/0.0034 = 294.117647` 的 float32。
说明 IL2CPP 的 AOT 编译器把 `1.0f / DEF_INCR_RATIO` 折叠成了常量。

**这意味着：改服务端 JSON 里的 `DEF_INCR_RATIO` 不会影响减伤公式**（客户端已固化）。
这一点对理解「哪些数值可以热更、哪些不能」很关键。

---

## 22. 完整的伤害计算流程图（最终版）

```
【技能触发】
  SkillCodeHandler.Fire
    └─ 按 skill 表的 damage.value 算出基础伤害 dmg0
       （value.target 决定倍率来源：AtkDmg / HP / MAXHP / Def / Rst ...）

【命中判定】  BattleEffectDamage.ApplyStatic @0x295A850
  hitRate = clamp(1.0 + atkHIT + atkHIT_extra
                      - defEVA - defEVA_extra, 0.05, 0.95)
  Random.Range(0,1) < hitRate ? 命中 : MISS
     ↓ 命中
【暴击判定】
  critRate = baseCritRate([unit+0x6c]) + extraCritRate([effect+0x3c])
  Random.Range(0,1) < critRate ?
     ↓ 暴击
  dmg1 = dmg0 * (atkCritDmg[unit+0x70] + defCritDmg + 1.0)
     ↓ 未暴击
  dmg1 = dmg0

【上下限钳制】  BattleEffectDamage.GetDamageAmount @0x295BB80
  dmg2 = |dmg1 * hitCount * baseStatFactor|
  dmg2 = min(dmg2, upperBound)      ; 默认 FLT_MAX
  dmg2 = max(dmg2, lowerBound)      ; 若配置了下限

【主伤害管线】  BattleUnit.HandleDamage @0x291DF2C
  早退：目标无效 / 伤害<=0 / 已死亡
     ↓
  受击前 AddState 组 0x29 回调
     ↓
  防御类被动 AddState 组 0x4d（按 dmgType 取 Def/Rst 修正）
     ↓
  伤害倍率 AddState 组 0x07（加法区 or 乘法区）
     ↓
  【核心减伤】
    dmgType==1: eff = DEF - PEN_DEF
    dmgType==2: eff = RST - PEN_RST
    dmgType==3/4: 跳过
    mult = (eff <= 0) ? 1.0 : 1/(1 + eff*0.0034)      @0x2936288
     ↓
  减免率累积：keep = 1.0 - Σ减免                  @0x291EE58
     ↓
  【伤害地板】
    dmg3 = dmg2 * mult * max(0.2, keep)            @0x291F048
     ↓
  最终伤害改写 AddState 组 0x06
     ↓
  负值钳制 dmg3 = max(0, dmg3)                     @0x291F2C4
     ↓
  距离衰减（dmgType != 4）
    dist / 80.0                                    @0x291F3B0
     ↓
【实际扣血】  BattleUnit.BlowDamage @0x291F948
  构造 BattleUnitStateSnapshot（属性快照）
  吸血结算（get_VampRate @0x29191DC）
  护盾/吸收计算
  递归调用 ApplyStatic（衍生伤害，dmgType=3）
```

---

## 23. 三条「不可热更」的硬编码

从二进制可以确认，以下三项**写死在客户端**，服务端改 JSON 无效：

1. **`DEF_INCR_RATIO`** —— 编译期折叠为 `294.117647` 常量（`0xE49F6C`）
2. **攻速下限 1.0** —— `Shared+0x64` 虽是变量，但 JSON 里没有对应键，实际由构造函数写死
3. **伤害上限默认 `FLT_MAX`** —— `0x7f7fffff` 立即数（`0x295BCD8`）

反过来，**可以热更**的是：

- `DAMAGE_DECREASE_MIN_CAP`（伤害地板 0.2）
- `HITRATE_MIN_CAP` / `HITRATE_MAX_CAP`（命中率上下限）
- `ATKSPD_CAP`（攻速上限）
- 全部 `block_buffs` / `battlebuffjson` / `addstate` 的倍率表
