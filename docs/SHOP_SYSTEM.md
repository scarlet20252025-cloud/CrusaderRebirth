# 商店与购买校验

本文整理克鲁赛德战记 v7.5.8 的商店体系与购买约束，全部数据来自解密后的数值表。

> **可信度**：所有价格、限额、重置周期均直接来自游戏原始 JSON。
> ⚠️ 标注部分为**服务端校验逻辑推断**——客户端数据里的 `purchase_limit` / `reset` 是校验所需的**声明**，
> 实际扣费与限购判定在服务端执行，客户端只做 UI 预判。

---

## 一、商店体系总览

游戏内共 **5 套独立商店**，各自的数据表与货币不同：

| 商店 | 数据表 | 条目 | 货币 | 特点 |
|---|---|---|---|---|
| 活动商店 | `content_event_shop.json` | 252 | 13 种活动代币 | 有 `purchase_limit` + `reset` |
| 房屋商店 | `house_shop.json` | 684 | 荣誉 / 金币 | **无**限购，一次性购买 |
| 幸运商店 | `luckyshopevent_product.json` | 38 | 宝石 / 铁 / 荣誉 / 广告等 | 按 `openday` 轮换 |
| 扭蛋商店 | `boxgacha.json` + `boxgachalist.json` | 218 + 220 | 宝石 | 保底区间 + 池式抽取 |
| 拍卖行 | `auctioneventsetting.json` | 82 | 拍卖代币 | 竞价制 |

此外还有两张**折扣表**影响实际价格：`resourcediscountrate.json`、`inventory_discount_info.json`。

---

## 二、活动商店（`content_event_shop.json`）

252 条，是全套数据里**校验信息最完整**的商店。

### 完整字段

```jsonc
{
  "shopid":       "ARENA",                           // 商店归属
  "category":     null,
  "priority":     2,                                 // 排序
  "reward_name":  "TEXT_MESSAGE_ITEM_GET_ANTIMATTER",
  "reward_type":  "ITEM_ANTIMATTER",                 // 得到什么
  "reward_value": "ITEM_ANTIMATTER",
  "reward_amount": 1000,                             // 得到多少
  "cost_type":    "ITEM_TOKEN_ARENA",                // 花什么
  "cost_value":   "ITEM_TOKEN_ARENA",
  "cost_amount":  80,                                // 花多少
  "bulktype":     true,                              // 是否允许批量买
  "reset":        "WEEK",                            // 重置周期
  "reset_value":  0,
  "purchase_limit": 20,                              // 每周限购次数
  "id": "ARENAREWARD_ANTIMATTER"
}
```

### 13 个商店与其专属货币

| shopid | 条目 | 货币 | 重置周期组合 |
|---|---|---|---|
| `BOSSRUSH` | 61 | `ITEM_TOKEN_BOSSRUSH` | LIMIT 45 / MONTH 15 / NONE 1 |
| `FISH` | 33 | `ITEM_FISHCOIN` | LIMIT 4 / DAY 6 / MONTH 10 / WEEK 12 / NONE 1 |
| `ARENA` | 21 | `ITEM_TOKEN_ARENA` | WEEK 15 / MONTH 6 |
| `STOCKEVENT` | 19 | `ITEM_TOKEN_STOCK` | LIMIT 19 |
| `CHOCOLAEVENT` | 18 | `ITEM_TOKEN_CHOCOLA` | LIMIT 18 |
| `AUCTIONEVENT` | 16 | `ITEM_TOKEN_AUCTION` | LIMIT 16 |
| `BOSSSOULRUSHEVENT` | 16 | `ITEM_TOKEN_BOSSSOULRUSH` | LIMIT 16 |
| `HASLAWARS` | 16 | `ITEM_HW_SHOP` | LIMIT 16 |
| `RHYTHMEVENT` | 16 | `ITEM_TOKEN_RHYTHM` | LIMIT 16 |
| `MAZEEVENT` | 14 | `ITEM_COIN_MAZE` | LIMIT 13 / NONE 1 |
| `WARGAME` | 8 | `ITEM_CRYSTAL` / `ITEM_GOLD` / `ITEM_HONOR` / `ITEM_IRON` | NONE |
| `HEROPASSEVENT` | 3 | `ITEM_GOLD` / `ITEM_POINT` | LIMIT 1 / NONE 2 |
| `ROGUELIKEEVENT` | 11 | `ITEM_TOKEN_ROGUELIKE` | LIMIT 11 |

### `reset` 五档语义

| 值 | 条目数 | 含义 |
|---|---|---|
| `LIMIT` | 175 | **不重置**，整个账号生命周期只能买 `purchase_limit` 次 |
| `MONTH` | 31 | 每月重置 |
| `WEEK` | 27 | 每周重置 |
| `NONE` | 13 | 不限制（`purchase_limit` 通常为 -1） |
| `DAY` | 6 | 每日重置 |

### `purchase_limit` 取值分布

`1`(105 条) 最多，其次 `5`(32)、`3`(25)、`20`(4)、`10`(17)、`50`(11)。
特殊值：`-1` = 无限（仅 10 条，全部 `reset=NONE`）、`0` = 当前不可买（2 条）。

### `bulktype`

- `true` 187 条：允许一次性买多份，总价 = `cost_amount × 份数`
- `false` 65 条：只能单次购买

### 实例：ARENA 商店前 8 条

| id | 得到 | 花费 | 限购 | 重置 |
|---|---|---|---|---|
| `ARENAREWARD_ANTIMATTER` | 反物质 ×1000 | 竞技场币 80 | 20 | WEEK |
| `ARENAREWARD_COSTUME_APFOOL` | 时装选择券 ×1 | 竞技场币 2500 | 1 | MONTH |
| `ARENAREWARD_COSTUME_AUCTION` | 时装选择券 ×1 | 竞技场币 2500 | 1 | MONTH |
| `ARENAREWARD_GACHA_WEP` | 武器扭蛋 ×1 | 竞技场币 15 | 30 | WEEK |
| `ARENAREWARD_MONTH_01` | 英雄扭蛋 ×1 | 竞技场币 1500 | 2 | MONTH |
| `ARENAREWARD_MONTH_02` | 继承书 ×1 | 竞技场币 350 | 3 | WEEK |

---

## 三、房屋商店（`house_shop.json`）

684 条，**纯展示型商店**，没有任何限购字段。

```jsonc
{
  "id": "SHOP_DECO_2000SEA_BOTTOM_CASTLE_01",
  "category": "DECORATION",              // DECORATION 579 / BACKGROUND 105
  "subcategory": "FLOOR",
  "subcategory_name": "TEXT_SUB_CATEGORY_FLOOR_NAME",
  "display": true,                       // 684 条全部 true
  "priority": 163,
  "cost_type": "ITEM_HONOR",             // ITEM_HONOR 491 / ITEM_GOLD 193
  "cost_amount": 2000,
  "reward_type": "ITEM_DECORATION",
  "reward_value": "DECO_2000SEA_BOTTOM_CASTLE_01",
  "reward_amount": 1
}
```

> **校验含义**：房屋装饰是**永久解锁**，购买后不消耗库存（只是解锁 flag）。
> 因此服务端校验只需判断「货币够不够 + 是否已拥有」，无需限购计数器。

---

## 四、幸运商店（`luckyshopevent_product.json`）

38 条，**按星期几轮换**。

```jsonc
{
  "id": "LUCKY_SHOP_2_01",
  "openday": 1,                          // 1-7 = 周一至周日；-1 = 常驻
  "priority": 1,
  "reward_type": "ITEM_GACHA_HERO",
  "reward_value": "GACHA_CHA_C",
  "reward_amount": 5,                    // 花 3 宝石得 5 张英雄扭蛋券
  "cost_type": "ITEM_JEWEL",
  "cost_amount": 3,
  "reset": "LIMIT",                      // LIMIT 35 / NONE 3
  "purchase_limit": 1
}
```

### `openday` 分布

`1`..`7` 各 5 条（每天固定 5 个商品），`-1` 3 条（常驻）。

### 6 种支付方式

`ITEM_ESSENCE_FLAMES`(8)、`ITEM_IRON`(8)、`ITEM_JEWEL`(7)、`ITEM_HONOR`(7)、`ADVERTISEMENT`(7)、`ITEM_GOLD`(1)

> `ADVERTISEMENT` 是**看广告免费领取**，服务端需校验广告 SDK 的回执，这是唯一非货币支付路径。

---

## 五、折扣表

### 资源扩容折扣（`resourcediscountrate.json`）

```json
[
  { "id": "ITEM_HEART",       "increasecount": 20, "discountrate": 5  },
  { "id": "ITEM_DUNGEONKEY",  "increasecount": 10, "discountrate": 10 }
]
```

解读：体力上限每扩 20 点，后续扩容价格降 5%；钥匙上限每扩 10 把，降 10%。

### 背包扩容折扣（`inventory_discount_info.json`）

```json
[
  { "increasecount": 11, "discountrate": 5,  "id": "1" },
  { "increasecount": 21, "discountrate": 10, "id": "2" },
  { "increasecount": 31, "discountrate": 20, "id": "3" }
]
```

解读：扩容 11 次后降 5%，21 次后降 10%，31 次后降 20%。**分段递增，不是线性累加**。

---

## 六、购买校验的完整逻辑 ⚠️

综合以上字段，一次购买需要服务端校验 6 项：

```
① 商品存在性
   shopid + id 必须命中 content_event_shop 表中的某一条

② 货币充足
   player[cost_type] >= cost_amount × 份数

③ 限购次数
   if reset == "LIMIT":  购买次数 < purchase_limit      （永久计数）
   elif reset == "WEEK": 本周购买次数 < purchase_limit
   elif reset == "MONTH":本月购买次数 < purchase_limit
   elif reset == "DAY":  今日购买次数 < purchase_limit
   elif reset == "NONE": 不限
   特例：purchase_limit == -1 视为无限；== 0 视为不可购买

④ 批量合法性
   if bulktype == false: 份数必须 == 1
   else:                 份数 >= 1（通常有客户端上限，数据中无声明）

⑤ 前置条件（部分商品）
   - 房屋装饰：未拥有过该 reward_value
   - 时装选择券：需在有效期内
   - 等级/进度门槛：数据中无显式字段，由服务端另行判定

⑥ 扣费与发放（原子操作）
   扣 player[cost_type] -= cost_amount × 份数
   发 player[reward_type] += reward_amount × 份数
   计数 record[id] += 份数
```

### 客户端可自行预判的部分

客户端拿到 `content_event_shop` 表 + 本地玩家状态，可以完整算出 ①–④。
这也意味着：**任何「买到超过 purchase_limit」的结果，客户端都能立刻识别为异常**。

### 数据中缺失的校验信息

| 缺失项 | 说明 |
|---|---|
| 商品上架/下架时间 | 无 `start_time` / `end_time` 字段，靠活动开关控制 |
| 等级门槛 | 无 `required_level` 字段 |
| 前置任务 | 无 `required_quest` 字段 |
| 每日购买次数上限 | 仅 `reset=DAY` 的 6 条有 |
| 批量购买上限 | 无 `max_bulk` 字段 |

> 这些全部由服务端硬编码或从其他系统推导，客户端数据里查不到。

---

## 七、扭蛋商店

### `box_gacha.json` — 218 条

```jsonc
{ "id": 1, "gacha_min": 0, "gacha_max": 0,
  "cost_type": "ITEM_JEWEL", "cost_amount": 5 }
```

`gacha_min` / `gacha_max` 定义**保底区间**：第 `gacha_min` 到 `gacha_max` 抽之间必出目标物。
`0 / 0` 表示该档位无保底。

### `box_gacha_list.json` — 220 条

箱式扭蛋的池内容：

```jsonc
{ "id": "BOX_GACHA_1", "item_type": "ITEM_HERO", "item_value": "CHA_PR_4_1", "item_amount": 1 }
```

> **池式扭蛋的概率可精确计算**：设池内剩余 `N` 项，某项有 `k` 份，则该次抽中概率 = `k / N`。
> 抽走不放回，所以概率随抽取次数单调上升——这是全套数据中**唯一能完整反推概率的付费机制**。

---

## 八、拍卖行（`auctioneventsetting.json`）

82 条，竞价制。与固定价格商店不同，最终成交价由玩家竞价决定，表里只声明活动规则（起拍价、加价幅度、时长等）。

---

## 九、速查：如何判断一次购买是否合法

```python
def validate_purchase(shop_table, player, item_id, qty, counters):
    """返回 (ok, reason)。所有数据均可在客户端获得。"""
    item = shop_table.get(item_id)
    if item is None:
        return False, "商品不存在"

    # ③ 限购
    limit = item.get("purchase_limit")
    if limit == 0:
        return False, "当前不可购买"
    if limit and limit > 0:
        used = counters.get(item_id, 0)
        if used + qty > limit:
            return False, f"超出限购 {limit}"

    # ④ 批量
    if not item.get("bulktype") and qty != 1:
        return False, "该商品不支持批量购买"

    # ② 货币
    need = item["cost_amount"] * qty
    if player.get(item["cost_type"], 0) < need:
        return False, f"货币不足，需要 {need}"

    return True, "ok"
```

`reset` 的处理需配合服务端的计数器生命周期，客户端只保存「本周期已购次数」。
