# 掉落系统还原

本文整理克鲁赛德战记 v7.5.8 的掉落与概率结构，全部数据来自解密后的 245 张数值表。

> **可信度**：所有字段名、取值、数量、上下界均直接来自游戏原始 JSON，可逐条验证。
> 标注 ⚠️ 的部分是**服务端逻辑推断**——掉落表只声明「可掉什么」，实际「掉多少、多大几率」由服务端计算，客户端数据中不存在显式概率字段。

---

## 一、掉落系统的分层结构

游戏把「掉落」拆成三个独立层面，彼此组合：

```
① 关卡级掉落下界    stage_reward.dropable_*      声明该关卡能掉哪些类别、什么等级区间
② 容器级随机内容    randombox_info / bundlebox   一个「箱子」可能开出哪一组物品
③ 概率型定向掉落    point_drop                   达到积分后按百分比二选一
```

**关键点**：`stage_reward` 里**没有任何概率数字**。它只给出 `min_grade` / `max_grade` 和 `classids` 白名单。因此：

> 关卡掉落的**类别与等级范围**是客户端可知的；**掉落概率与具体条数**由服务端决定，不在客户端数据中。

---

## 二、关卡掉落（`data/stage/stage_reward.json`）

737 条记录，字段结构固定为 7 个 `dropable_*` 维度：

| 字段 | 非空关卡数 | 含义 |
|---|---|---|
| `dropable_weapon_type` | 291 / 737 | 可掉武器类别与等级区间 |
| `dropable_bread_type` | 236 / 737 | 可掉面包等级区间 |
| `dropable_kurenai` | 196 / 737 | 可掉「红」（kurenai）相关物 |
| `dropable_map_addstateitem` | 192 / 737 | 可掉地图词条道具 |
| `dropable_hero` | 150 / 737 | 可掉英雄 |
| `dropable_custom` | 39 / 737 | 自定义掉落（按 item_type / randombox_value） |
| `dropable_ring_type` | 4 / 737 | 可掉戒指（极少） |

### 结构定义

```jsonc
"dropable_weapon_type": {
  "classids": ["CAT_BOW", "CAT_GUN", "CAT_HAMMER"],  // 武器类别白名单
  "min_grade": 2,                                     // 最低稀有度
  "max_grade": 6                                      // 最高稀有度
}
```

```jsonc
"dropable_hero": {
  "classids": [null],   // null = 不限职业
  "min_grade": 1,
  "max_grade": 1
}
```

> `classids: [null]` 表示**不限制职业**；`classids: []` 配合 `min_grade: -1` 表示**该维度不掉落**。
> 因此判断某关卡是否掉某类物品，要看的是 `min_grade >= 0`，而不是数组是否为空。

### 通关奖励（固定，非随机）

```jsonc
"clear_reward_type":   "ITEM_GOLD",
"clear_reward_value":  "ITEM_GOLD",
"clear_reward_amount": 5000,
"firstclear_reward_type":   "ITEM_JEWEL",
"firstclear_reward_value":  "ITEM_JEWEL",
"firstclear_reward_amount": 2
```

728 / 737 个关卡有固定通关奖励；9 个关卡这两组字段为 `null`（多为特殊/活动关卡）。

### 实例：`STAGE_BATTLE_FIELD_1`

```jsonc
{
  "dropable_weapon_type": { "classids": ["CAT_BOW","CAT_GUN","CAT_HAMMER"], "max_grade": 6, "min_grade": 2 },
  "dropable_bread_type":  { "max_grade": 6, "min_grade": 3 },
  "dropable_kurenai":     { "item_type": [], "addstatitem": { "max_grade": 1, "min_grade": 1 } },
  "dropable_map_addstateitem": { "item_type": ["ITEM_ADDSTATITEM","ITEM_ESSENCE_LIFE"] },
  "dropable_hero":        { "classids": [null], "max_grade": 1, "min_grade": 1 },
  "dropable_ring_type":   { "classids": [], "mainoption": [], "max_grade": -1, "min_grade": -1 },
  "dropable_custom":      { "item_type": [], "randombox_value": [] },
  "id": "STAGE_BATTLE_FIELD_1"
}
```

读法：该关卡可掉 2–6 星弓/枪/锤、3–6 星面包、1 星英雄、地图词条道具与生命精华；**不掉戒指**。

---

## 三、随机箱（`data/item/randombox.json` + `bundlebox.json`）

### randombox_info — 140 条

一个箱子声明一组「候选奖励」，开箱时从中取。**注意：候选之间没有权重字段**。

```jsonc
{
  "name": "TEXT_CARVESTONE_CHALLNGE_EPIC_GRADE1_01_NAME",
  "rarity": "EPIC",
  "rewards": [
    { "key": 0, "reward_type": "ITEM_CARVESTONE", "reward_value": "EPIC_3G_STONE_1",              "reward_amount": 1 },
    { "key": 1, "reward_type": "ITEM_CARVESTONE", "reward_value": "EPIC_ANCIENREGIME_STONE_2",    "reward_amount": 1 },
    { "key": 2, "reward_type": "ITEM_CARVESTONE", "reward_value": "EPIC_...",                     "reward_amount": 1 }
  ],
  "image": "ui_item_box_s2_ep1_challenge_02",
  "getplace": null,
  "mailsendername": "TEXT_REDNAS_NAME",
  "mailcontent": "TEXT_RANDOMBOX_BASIC_MESSAGE"
}
```

`rewards[].key` 是**候选序号**，不是权重。`reward_amount` 才是发多少。

### bundlebox_info — 90 条

结构与 randombox 相同，但通常是**固定组合包**（一次给全部 rewards），而不是多选一。

```jsonc
{
  "id": "BUNDLEBOX_ARTISTPAINT_01",
  "rewards": [
    { "key": 0, "reward_type": "ITEM_MATERIAL", "reward_value": "MATERIAL_CHALLENGE_EP6_01", "reward_amount": 10 }
  ]
}
```

---

## 四、概率型掉落（`data/item/pointdrop.json`）

**这是全套数据里唯一带显式概率字段的表**，共 6 条，全部是「刷图积分达标后二选一给英雄」。

```jsonc
{
  "chapter_id": "DUNGEON_TRIAL_WIPR",
  "stage_id":   "STAGE_DG_TRIAL_WIPR_4",
  "pointmax":   100,
  "pointreward_hero": [
    { "id": 1, "heroid": "CHA_WI_1_3", "probability": 50 },
    { "id": 2, "heroid": "CHA_PR_1_3", "probability": 50 }
  ],
  "id": "PD_HERO_DORO_MARIA"
}
```

### 全部 6 条

| id | stage_id | 候选 A | 候选 B | 概率 |
|---|---|---|---|---|
| `PD_HERO_DORO_MARIA` | `STAGE_DG_TRIAL_WIPR_4` | `CHA_WI_1_3` | `CHA_PR_1_3` | 50 / 50 |
| `PD_HERO_LEON_DART` | `STAGE_DG_TRIAL_SWHU_4` | `CHA_WA_1_3` | `CHA_HU_1_3` | 50 / 50 |
| `PD_HERO_MEL_DEMON` | `STAGE_DG_STORY_RUIN_4` | `CHA_AR_1_6` | `CHA_PR_1_6` | 50 / 50 |
| `PD_HERO_ROLL_ROCHE` | `STAGE_DG_STORY_VOID_4` | `CHA_WA_1_6` | `CHA_PA_1_6` | 50 / 50 |
| `PD_HERO_SIGU_KRIEM` | `STAGE_DG_TRIAL_PAAR_4` | `CHA_PA_1_3` | `CHA_AR_1_3` | 50 / 50 |
| `PD_HERO_TERESA_KANO` | `STAGE_DG_STORY_FURY_4` | `CHA_HU_1_6` | `CHA_WI_1_6` | 50 / 50 |

全部为**等概率二选一**，`pointmax = 100` 表示积分满 100 后触发一次。

---

## 五、扭蛋（`data/item/gacha.json` / `boxgacha.json` / `choice_gacha.json`）

### gacha — 49 条

只声明「扭蛋池叫什么、什么稀有度、出什么类型」，**不含单抽概率**。

```jsonc
{ "id": "GACHA_CHA_AR", "type": "ITEM_HERO", "rarity": "RARE",
  "name": "TEXT_GACHA_CHA_AR_NAME", "desc": "TEXT_GACHA_CHA_AR_DESC",
  "image": "ui_item_classlabel_archer_01" }
```

### box_gacha — 218 条

定义**保底区间**与价格：

```jsonc
{ "id": 1, "gacha_min": 0, "gacha_max": 0,
  "cost_type": "ITEM_JEWEL", "cost_value": "ITEM_JEWEL", "cost_amount": 5 }
```

`gacha_min` / `gacha_max` 是**必得区间**（第 N 抽必出），`0/0` 表示无保底。

### box_gacha_list — 220 条

箱式扭蛋的**具体池内容**：

```jsonc
{ "id": "BOX_GACHA_1", "item_type": "ITEM_HERO", "item_value": "CHA_PR_4_1", "item_amount": 1 }
```

> 箱式扭蛋的机制是「池子共 N 个，抽走不放回」，因此**池内每项概率 = 1 / 剩余数量**，无需权重字段。这是唯一能从数据反推池内概率的扭蛋类型。

---

## 六、积分/活动奖励（部分样本）

### repeat_raid_reward — 20 条

重复讨伐达标给箱：

```jsonc
{ "id": "STAGE_RAID_DARKOFTHEDEEPSEA_1", "goal_amount": 50,
  "reward_type": "ITEM_RANDOMBOX", "reward_value": "RANDOMBOX_CARVESTONE_4_SET_LOW", "reward_amount": 1 }
```

### episode_reward — 19 条

章节通关奖励，固定给全部：

```jsonc
{ "id": "EPISODE1_BONUS_FOREST", "stage_id": "STAGE_FOREST_12",
  "reward_json": [
    { "Reward_Type": "ITEM_BREAD", "Reward_Value": "BREAD_EXP_LEGEND_04", "Reward_Amount": 1 },
    { "Reward_Type": "ITEM_HEART", "Reward_Value": "ITEM_HEART",          "Reward_Amount": 100 },
    { "Reward_Type": "ITEM_HERO",  "Reward_Value": "CHA_WI_4_1",          "Reward_Amount": 1 }
  ] }
```

---

## 七、能推断什么 / 不能推断什么

### ✅ 可以精确知道

| 问题 | 数据来源 |
|---|---|
| 某关卡能掉哪些武器类别 | `stage_reward.dropable_weapon_type.classids` |
| 某关卡掉落等级区间 | `min_grade` / `max_grade` |
| 某关卡通关固定给多少金币/宝石 | `clear_reward_*` / `firstclear_reward_*` |
| 某箱子的候选项有哪些 | `randombox_info.rewards[]` |
| 箱式扭蛋池里有哪 220 个物品 | `box_gacha_list` |
| 箱式扭蛋单抽概率 | `1 / 剩余池内数量` |
| 积分掉落二选一的概率 | `point_drop.pointreward_hero[].probability` |

### ❌ 无法从客户端数据得知

| 问题 | 原因 |
|---|---|
| 关卡每格的实际掉落率 | 服务端计算，客户端无字段 |
| 打一次掉几件 | 服务端决定，无字段 |
| 普通扭蛋单抽出各稀有度的概率 | `gacha` 表无权重字段 |
| 随机箱开出某一项的概率 | `randombox_info` 无权重字段 |
| 掉落是否受队伍/难度影响 | 无相关字段 |

> 这些数据只存在于服务端。客户端能拿到的上限，就是「合法性约束」——即
> **服务端发给客户端的掉落结果，一定落在 `stage_reward` 声明的白名单与等级区间内**。
> 这也是校验掉落包是否异常的唯一客户端依据。

---

## 八、数据结构速查

```jsonc
// 判断某关卡是否掉落某类物品
function canDrop(stageReward, kind /* "weapon"|"bread"|"ring"|"hero" */) {
  const d = stageReward[`dropable_${kind}_type`] ?? stageReward[`dropable_${kind}`];
  return d && d.min_grade >= 0;      // min_grade 为 -1 表示该维度不掉
}

// 稀有度是否在区间内
function gradeOk(d, grade) {
  return d.min_grade >= 0 && grade >= d.min_grade && grade <= d.max_grade;
}

// 职业是否被允许（classids 含 null 或不限）
function classOk(d, classId) {
  if (!d.classids || d.classids.length === 0) return true;
  if (d.classids.includes(null)) return true;
  return d.classids.includes(classId);
}
```
