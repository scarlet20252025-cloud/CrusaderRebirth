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

## 九、未解决的问题

| 问题 | 现状 |
|---|---|
| `DEF_UPPER_BOUND = 100` 的具体用法 | 可能是 `Def/100` 归一化后再套曲线，未验证 |
| 防御减伤是线性还是曲线 | `DEF_INCR_RATIO = 0.0034` 暗示线性，但 `DEF_UPPER_BOUND` 暗示有上限 |
| 多段技能的每段倍率分配 | `skillhandlerjson` 里每段独立，但部分技能用 `power` 字段（仅 64 条） |
| `DmgManipulate` 的 288 条用法 | 显然是伤害修改器，但语义（乘算/加算/替换）未定 |
| `wound_block_damage_multiplier = 5` | 受伤方块的伤害是否为正常 5 倍，未验证 |
