# 伤害计算公式还原

本文基于 245 张解密数值表 + 已脱壳的 `libil2cpp.so` 元数据，还原克鲁赛德战记 v7.5.8 的伤害计算链。

> **可信度说明**：常数、倍率、handler 语义全部来自游戏原始数据，可验证。
> 但**公式的运算顺序**是基于 handler 命名、字段语义与常见 RPG 设计推断的，未经运行时逐帧验证。标注 ⚠️ 的部分属于推断。

---

## 一、属性来源

### 角色基础属性（`data/character/character_stat.json`）

3427 条记录，每条包含：

| 字段 | 含义 | 中位数 | 最大值 |
|---|---|---|---|
| `initialattdmg` | 初始攻击力 | 124 | 9,999,999 |
| `initialhp` | 初始生命 | 1440 | 1e10 |
| `growthattdmg` | 每级攻击成长 | 2.74 | 700 |
| `growthhp` | 每级生命成长 | 26.87 | 45,600 |
| `defense` / `growthdefense` | 防御 / 成长 | 31.175 / 0 | 999,999 |
| `resist` / `growthresist` | 抗性 / 成长 | 31.175 / 0 | 999,999 |
| `critprob` | 暴击率 | 0.10 | 1.50 |
| `critpower` | 暴击伤害加成 | 0.50 | 5.00 |
| `penetratedef` | 防御穿透 | 0 | 20,000 |
| `penetraterst` | 抗性穿透 | 0 | 20,000 |
| `hitrate` | 命中 | 0 | 1000 |
| `dodgerate` | 闪避 | 0 | 0.80 |
| `dmgreduce` | 减伤 | 0 | 0.90（最小 -0.30） |
| `vamp` | 吸血 | 0 | 0.50 |
| `knockbackresistancerate` | 击退抗性 | 30 | 999 |

等级换算 ⚠️（推断）：
```
Atk(L)  = initialattdmg  + growthattdmg × (L - 1)
HP(L)   = initialhp      + growthhp     × (L - 1)
Def(L)  = defense        + growthdefense× (L - 1)
Rst(L)  = resist         + growthresist × (L - 1)
```

### 战斗内属性修正

技能与被动通过 `addstate` 的 handler 施加百分比或固定值修正：

```
AtkDmg   修正攻击力          value.target = "AtkDmg" | "ATK"
Def      修正防御            value.target = "Def"
Rst      修正抗性            value.target = "Rst"
HP       修正生命            value.target = "HP" | "MAXHP"
CRIT_PROB 修正暴击率
CRIT_DMG  修正暴击伤害
PENETRATE_DEF / PENETRATE_RST  修正穿透
```

`value` 为负表示 debuff（如 `AtkDmg: -0.35` = 攻击力 -35%）。

---

## 二、伤害类型

技能数据（`data/combat/skill.json`，7998 条）的 `type` 字段：

| type | 数量 | 说明 |
|---|---|---|
| `NORMAL` | 4550 | 物理伤害，受 Def 减免 |
| `MAGIC` | 3164 | 魔法伤害，受 Rst 减免 |
| `NEUTRAL` | 202 | 无属性/真实伤害，不吃 Def/Rst |
| `UNKNOWN` / null | 82 | 特殊 |

对应的伤害 handler：

| handler | 数量 | 作用 |
|---|---|---|
| `DmgNormal` | 190 | 造成物理伤害 |
| `DmgMagic` | 167 | 造成魔法伤害 |
| `DmgNeutral` | 189 | 造成无属性伤害 |

三者的 `value` + `value.target` 组合决定伤害基数：

| value.target | 出现次数（DmgNormal/Magic/Neutral） | 含义 |
|---|---|---|
| `AtkDmg` | 110 / 119 / 104 | **攻击力 × value** |
| `HP` | 30 / 20 / — | 生命上限 × value |
| `MAXHP` | — / — / 22 | 生命上限 × value |
| `Rst` / 其他 | 少量 | 特殊 |

> 这是整个伤害系统最关键的一点：**技能伤害不是绝对值，而是攻击力（或生命）的百分比**。
> 例如 `value: 0.2, value.target: "AtkDmg"` = 造成攻击力 20% 的伤害。

---

## 三、伤害计算链 ⚠️

以下顺序基于 handler 命名与字段语义推断：

```
Step 1  基础伤害
        base = Atk × skill_multiplier
        其中 skill_multiplier 来自 addstate 的 Dmg* handler 的 value
        若 value.target == "HP"/"MAXHP"，则 base = MaxHP × value

Step 2  方块 Buff 倍率
        base ×= block_buff.damage.multiplier      （见下表）
        首领方块额外 × LEADER_BLOCK_RATIO = 1.75

Step 3  穿透修正
        effective_def = max(0, Def - PENETRATE_DEF)
        effective_rst = max(0, Rst - PENETRATE_RST)

Step 4  防御减免（物理）
        reduction = 1 - effective_def × DEF_INCR_RATIO
        reduction = clamp(reduction, DAMAGE_DECREASE_MIN_CAP, 1)
        即最多减免 80%（DAMAGE_DECREASE_MIN_CAP = 0.2）

Step 5  抗性减免（魔法）同上，用 Rst

Step 6  固定减伤
        if DAMAGE_REDUCED(0.1) 生效：base ×= (1 - 0.1)

Step 7  暴击
        if rand() < CRIT_PROB:
            base ×= (1 + CRIT_DMG)

Step 8  PvP / 副本修正
        PvP:     ×= Damage_revise (0.6)
        掠夺战:  ×= DmgRevise (0.3)

Step 9  最终取整与下限
        damage = max(1, round(base))
```

### 关键常数（`data/combat/battle_settings.json` → `battlesettingsjson`）

| 常数 | 值 | 作用 |
|---|---|---|
| `DEF_UPPER_BOUND` | 100 | 防御计算上限参考值 |
| `DEF_INCR_RATIO` | 0.0034 | 每点防御的减伤率 |
| `DAMAGE_DECREASE_MIN_CAP` | 0.2 | 减伤后最低保留 20% 伤害 |
| `DAMAGE_REDUCED` | 0.1 | 全局固定减伤 |
| `LEADER_BLOCK_RATIO` | 1.75 | 首领方块伤害倍率 |
| `ATKSPD_CAP` | 2.5 | 攻速上限 |
| `HITRATE_MIN_CAP` | 0.05 | 最低命中率 |
| `HITRATE_MAX_CAP` | 0.95 | 最高命中率 |
| `SR_DMG_REVISE` | 0.8 | 超频/特殊模式伤害修正 |
| `SR_HP_REVISE` | 5 | 超频/特殊模式生命修正 |

> `DEF_INCR_RATIO = 0.0034` 意味着 **每 100 点防御减免 34%**。
> 配合 `DEF_UPPER_BOUND = 100` 与 `DAMAGE_DECREASE_MIN_CAP = 0.2`，
> 可以推断防御减伤存在一条以 100 点为参考尺度的曲线，且最低保留 20% 伤害。

---

## 四、方块 Buff 倍率表

`battle_block_configjson.block_buffs`，共 3 类 × 5 级：

### AGGRESIVE（攻击型）

| 级 | 伤害倍率 | 移速倍率 | 攻速倍率 |
|---|---|---|---|
| 1 | ×1.1 | ×1.5 | ×1.0 |
| 2 | ×1.2 | ×1.5 | ×1.0 |
| 3 | ×1.4 | ×1.5 | ×1.0 |
| 4 | ×1.7 | ×1.5 | ×1.0 |
| 5 | ×2.0 | ×1.5 | ×1.0 |

### DEFENSIVE（防御型）

| 级 | 固定减伤 |
|---|---|
| 1 | 4 |
| 2 | 6 |
| 3 | 9 |
| 4 | 13 |
| 5 | 18 |

### RECOVERY（恢复型）

| 级 | 治疗倍率 |
|---|---|
| 1 | ×2 |
| 2 | ×5 |
| 3 | ×8 |
| 4 | ×11 |
| 5 | ×14 |

### Fever

```json
"battle_buffjson": [{
  "key": "FeverBuff",
  "props": {
    "atk.damage.multiplier": 1.5,
    "atk.speed.multiplier": 2,
    "move.speed.multiplier": 1.5
  }
}]
```

Fever 触发所需方块数：`fever_gain = [8, 22, 36, 45, 57]`（按队伍人数/难度档位）

---

## 五、普攻与技能基准倍率

`battle_info_json`（用于战力评估，也是普攻伤害的参考）：

| 项 | 倍率 |
|---|---|
| `Normal_attack_1` | 0.20 |
| `Normal_attack_2` | 0.20 |
| `Normal_attack_3` | 0.20 |
| `Normal_attack_4` | 0.25 |
| `Normal_attack_5` | 0.25 |
| `Normal_attack_6` | 0.30 |
| `Avg_skill_1to3` | 1.935 |
| `Avg_skill_4` | 2.101 |
| `Avg_skill_5` | 2.732 |
| `Avg_skill_6` | 2.862 |
| `Diff_low_bound` | -210 |
| `Diff_high_bound` | +250 |

`Diff_low_bound` / `Diff_high_bound` 是战力匹配的容差区间（±210 → +250）。

---

## 六、PvP 环境修正

```json
"pvpsettings": {
  "Damage_revise": 0.6,
  "HP_revise": 1.75,
  "PVP_InitValue": { "DmgRevise": 0.6, "HealRevise": 0.6, "SPRevise": 1 },
  "PVP_FeverInitTime": 50,
  "PVP_FeverInterval": 10,
  "PVP_FeverMultiplier": { "DmgRevise": 1.25, "HealRevise": 0, "SPRevise": 1 }
}
```

| 模式 | 伤害修正 | 治疗修正 |
|---|---|---|
| PvP 常规 | ×0.6 | ×0.6 |
| PvP Fever | ×1.25 | ×0（禁疗） |
| 掠夺战 (RPVP) | ×0.3 | ×0.6 |
| RPVP Fever | ×1.25 | ×0 |

PvP 属性倍率：
```json
"pvpstatsettings": {
  "HP":  { "Multiplier": 1.5 },
  "Def": { "Multiplier": 1.65 },
  "Rst": { "Multiplier": 1.65 }
}
```

---

## 七、战力（Power）计算

`pvpsettings` 中的分段常数，用于 PvP 匹配与段位划分：

| 星级 | base | growth |
|---|---|---|
| 1★ | 3524 | 298.50 |
| 2★ | 5997 | 415.24 |
| 3★ | 13318 | 579.26 |
| 4★ | 29422 | 697.78 |
| 5★ | 57113 | 904.68 |
| 6★ | 106999 | 1020.85 |

觉醒（Epic）加成：

| 段位 | power_epic |
|---|---|
| 1 | 8412.5 |
| 2 | 16887.5 |
| 3 | 25331.25 |
| 4 | 33775 |
| 5 | 43775 |
| 6 | 53775 |
| 7 | 59106 |
| 8 | 67550 |

`power_delta = 0.15`

段位阈值：
```
BRONZE_max_power = 502,773
SILVER_max_power = 528,010.5
GOLD_max_power    = 544,835.5
```

---

## 八、验证方法

本文的公式顺序属于推断。若要严格验证，可：

1. 用 `data/combat/skill.json` 挑一个简单技能（`skillhandlerjson` 只有一条 `DmgNormal`）
2. 用 `data/character/character_stat.json` 取其施法者与目标属性
3. 按上述公式手算，与游戏内实际伤害对比
4. 若偏差固定，说明缺少某个常数；若偏差随防御变化，说明 Step 4 曲线形式有误

`get_battlestatistics`（23 条）中可能有官方的伤害统计口径，可作为交叉验证。

---

## 九、`value.target` 的完整语义

`addstate` 里 `handler.id` 与 `value.target` 是**两个独立维度**：

- `handler.id` 决定**做什么**（造成伤害 / 加 buff / 治疗 / 上护盾 …）
- `value.target` 决定**取哪个属性当基数**

136 种组合，高频如下：

### 伤害类 handler 的基数选择

| handler | value.target | 次数 | 含义 |
|---|---|---|---|
| `DmgMagic` | `AtkDmg` | 119 | 魔法伤害 = 攻击力 × value |
| `DmgNormal` | `AtkDmg` | 110 | 物理伤害 = 攻击力 × value |
| `DmgNeutral` | `AtkDmg` | 104 | 无属性伤害 = 攻击力 × value |
| `ProjectileDmgNormal` | `AtkDmg` | 62 | 弹道物理伤害 |
| `ProjectileDmgMagic` | `AtkDmg` | 38 | 弹道魔法伤害 |
| `DmgNormal` | `HP` | 30 | 物理伤害 = 自身生命 × value（按血打人） |
| `DmgNormal` | `Rst` | 24 | 物理伤害 = 抗性 × value |
| `DmgNeutral` | `MAXHP` | 22 | 无属性伤害 = 生命上限 × value |
| `DmgNormal` | `Def` | 15 | 物理伤害 = 防御 × value（反伤型） |
| `DmgMagicMissCheck` | `AtkDmg` | 10 | 带命中判定的魔法伤害 |
| `DmgBlockOver` | `MAXHP` | 40 | 溢出方块伤害，按生命上限 |

> **重要**：伤害基数**不一定是攻击力**。约 15% 的伤害 handler 用 `HP` / `MAXHP` / `Def` / `Rst` 作基数，
> 这解释了游戏里「按血量百分比造成伤害」的 boss 技能和「按防御反伤」的机制。

### 属性修正 handler 的基数

| handler | value.target | 次数 | 含义 |
|---|---|---|---|
| `AtkDmg` | `AtkDmg` | 439 | 攻击力百分比修正 |
| `Def` | `Def` | 182 | 防御百分比修正 |
| `Rst` | `Rst` | 179 | 抗性百分比修正 |
| `HP` | `HP` | 171 | 生命百分比修正 |
| `PENETRATE_RST` | `PENETRATE_RST` | 55 | 抗性穿透修正 |
| `PENETRATE_DEF` | `PENETRATE_DEF` | 49 | 防御穿透修正 |
| `AtkDmg` | `BaseAtkDmg` | 36 | 修正**基础**攻击力（不含装备加成） |
| `Def` | `BaseDef` | 25 | 修正基础防御 |
| `Rst` | `BaseRst` | 28 | 修正基础抗性 |
| `AtkSpd` | `AtkSpd` | 28 | 攻速修正 |
| `CRIT_PROB` | `BaseCRIT_PROB` | 8 | 修正基础暴击率 |
| `MoveSpeed` | `MoveSpeed` | 11 | 移速修正 |

`Base*` 前缀的意义：`BaseAtkDmg` 只改「角色基础攻击」，装备/词条加成不受影响。
这是区分「基础属性 buff」与「最终属性 buff」的关键字段。

### `value.target` 全部 37 种取值

```
AtkDmg(1118)  HP(305)  Rst(263)  Def(262)  MAXHP(213)
PENETRATE_RST(59)  CurrentHPRatio(54)  PENETRATE_DEF(50)
BaseAtkDmg(38)  BaseRst(30)  AtkSpd(28)  BaseDef(25)
CurrentHP(18)  MoveSpeed(12)  CRIT_PROB(11)  Barrier(8)
BaseCRIT_PROB(8)  BaseCRIT_DMG(8)  CRIT_DMG(4)  ATK_SPD(3)
DealtHP(3)  CRIT_DODGE(3)  DEF(3)  BasePENETRATE_DEF(3)
BasePENETRATE_RST(3)  MaxHP(2)  DealtHPRatio(2)  MotionSpeed(2)
rst(2)  DODGE(2)  CurrentHpRatio(1)  RESIST_KNOCKBACK(1)
DmgImmune(1)  HitRate(1)  RST(1)  HITRATE(1)  Dodge(1)
RESIST_DEBUFF(1)
```

> 注意大小写不一致（`DEF`/`Def`、`MaxHP`/`MAXHP`、`CurrentHPRatio`/`CurrentHpRatio`）——
> 这是游戏代码里字符串常量不统一造成的，解析时必须**大小写不敏感**，或穷举所有变体。

### `target`（作用对象）枚举

| 值 | 次数 | 含义 |
|---|---|---|
| `ONESELF` | 21065 | 自己 |
| `ENEMY_ONHIT` | 2812 | 被击中的敌人 |
| `ALLY` | 1205 | 全体友方 |
| `ENEMY` | 979 | 全体敌人 |
| `ON_HEAL` | 427 | 治疗时触发 |
| `ALL` | 300 | 全体 |
| `MASTER_ALLY` | 255 | 召唤者的友方 |
| `LEADER` | 176 | 队长 |
| `ENEMY_FRONT` | 117 | 前排敌人 |
| `SUMMONED_CREATURES` | 84 | 召唤物 |
| `MASTER_ENEMY` | 80 | 召唤者的敌人 |

还有**数组形式**的复合选择器（罕见但重要）：

```jsonc
["ALLY", "MIN_HP_RATIO"]      // 友方中血量百分比最低者（24 次）
["ENEMY", "MAX_HP"]           // 敌方中血量最高者（9 次）
["ENEMY", "RANDOM"]           // 随机敌方（11 次）
["ALLY", "MAX_BASE_HIT"]      // 友方中基础命中最高者（13 次）
["ENEMY", "MOST_MAX_HP"]      // 敌方中生命上限最高者（3 次）
```

> 这类选目标逻辑是「智能辅助技能」的基础：奶妈自动选最残血的队友，
> 刺客自动选血最厚的敌人。数据里通过数组声明，服务端按声明筛人。

---

## 十、未解决的问题

| 问题 | 现状 |
|---|---|
| `DEF_UPPER_BOUND = 100` 的具体用法 | 可能是 `Def/100` 归一化后再套曲线，未验证 |
| 防御减伤是线性还是曲线 | `DEF_INCR_RATIO = 0.0034` 暗示线性，但 `DEF_UPPER_BOUND` 暗示有上限 |
| 多段技能的每段倍率分配 | `skillhandlerjson` 里每段独立，但部分技能用 `power` 字段（仅 64 条） |
| `DmgManipulate` 的 288 条用法 | 显然是伤害修改器，但语义（乘算/加算/替换）未定 |
| `wound_block_damage_multiplier = 5` | 受伤方块的伤害是否为正常 5 倍，未验证 |
| `DmgBlockOver` 的触发阈值 | 40 次以 `MAXHP` 为基数，但「溢出」的判定条件未知 |
| `Barrier` 与 `DmgManipulate` 的叠加顺序 | 护盾先扣还是减伤先算，未验证 |
| `DealtHP` / `DealtHPRatio` 累计口径 | 是单次伤害还是战斗累计，未验证 |
| `power` 字段的语义 | 仅 3542/7998 条有值，且 3478 条为 0，可能是废弃字段 |
