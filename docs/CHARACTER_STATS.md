# 角色属性系统

`data/character/character_stat.json` 共 **3427** 条记录，覆盖所有怪物、英雄与 Boss。

## 字段说明与取值分布

| 字段 | 含义 | 记录数 | 最小 | 中位 | 最大 |
|---|---|---|---|---|---|
| `initialattdmg` | 初始攻击力 | 3427 | 0.000 | 124.000 | 9999999.000 |
| `initialhp` | 初始生命 | 3427 | 0.000 | 1440.000 | 10000000000.000 |
| `growthattdmg` | 攻击成长/级 | 3427 | 0.000 | 2.740 | 700.000 |
| `growthhp` | 生命成长/级 | 3427 | 0.000 | 26.870 | 45600.000 |
| `defense` | 防御 | 3427 | 0.000 | 31.175 | 999999.000 |
| `resist` | 抗性 | 3427 | 0.000 | 31.175 | 999999.000 |
| `growthdefense` | 防御成长/级 | 3427 | 0.000 | 0.000 | 120.000 |
| `growthresist` | 抗性成长/级 | 3427 | 0.000 | 0.000 | 120.000 |
| `critprob` | 暴击率 | 3427 | 0.000 | 0.100 | 1.500 |
| `critpower` | 暴击伤害加成 | 3427 | 0.000 | 0.500 | 5.000 |
| `vamp` | 吸血 | 3427 | 0.000 | 0.000 | 0.500 |
| `penetratedef` | 防御穿透 | 3427 | 0.000 | 0.000 | 20000.000 |
| `penetraterst` | 抗性穿透 | 3427 | 0.000 | 0.000 | 20000.000 |
| `hitrate` | 命中 | 3427 | 0.000 | 0.000 | 1000.000 |
| `dodgerate` | 闪避 | 3427 | 0.000 | 0.000 | 0.800 |
| `dmgreduce` | 减伤 | 3427 | -0.300 | 0.000 | 0.900 |
| `knockbackresistancerate` | 击退抗性 | 3427 | 0.000 | 30.000 | 999.000 |

## 职业分布

| herotype | 数量 |
|---|---|
| `None` | 1892 |
| `SUPPORT` | 1001 |
| `LEADER` | 534 |

## 引用关系

`character_stat` 中的 `id`（形如 `STAT_XXX`）被以下表引用：

- `character_parts`（1965）— 角色部件/外观组合
- `character_visual`（3656）— 视觉资源
- `character_class`（403）— 职业定义
- `character_profile`（282）— 档案文本
- `character_addstatmax`（387）— 附加属性上限
- `character_epiclevelstat`（240）— 觉醒等级属性

## 示例记录

```json
{
 "basicattack": "PA_ANUBIS",
 "blockskill": null,
 "spskill": null,
 "spskillclassoverride": null,
 "rangedattack": null,
 "herotype": null,
 "skill_name": null,
 "skill_icon": null,
 "skill_desc": null,
 "skill_subname": null,
 "skill_subdesc": null,
 "passive": null,
 "initialattdmg": 16.53,
 "initialhp": 220.0,
 "growthattdmg": 2.0736,
 "growthhp": 169.39008,
 "knockbackresistancerate": 70.0,
 "pattern": "Pattern_ANUBIS_CP2_Stage8",
 "passiveslot": 0,
 "defense": 0.0,
 "resist": 0.0,
 "growthdefense": 0.0,
 "growthresist": 0.0,
 "critprob": 0.0,
 "critpower": 0.5,
 "vamp": 0.0,
 "addstatmaxid": null,
 "penetratedef": 0.0,
 "penetraterst": 0.0,
 "hitrate": 0.0,
 "dodgerate": 0.0,
 "dmgreduce": 0.0,
 "id": "STAT_ANUBIS_CP2_Stage8"
}
```