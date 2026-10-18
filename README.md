# Crusader Rebirth — 克鲁赛德战记 国服数据与逆向工程存档

《克鲁赛德战记》(Crusader Quest / 크루세이더퀘스트) 国服客户端 **v7.5.8.KG (build 2079)** 的完整数值表与逆向工程记录。

> 本仓库仅用于**学习、研究与数据存档**。所有数据版权归 NHN Entertainment / LoadComplete 所有。
> 不包含任何破解补丁、外挂或可用于获利的工具。请在遵守当地法律与游戏服务条款的前提下使用。

---

## 这是什么

从 Android 客户端中提取的 **245 张游戏服务端下发数值表**，共 **59.25 MB / 全部为明文 JSON**。

这些表原本以 `.bf1` 加密格式下发，本项目完成了完整解密链路还原，并将结果按功能归类整理。

| 项目 | 值 |
|---|---|
| 游戏 | 克鲁赛德战记 / Crusader Quest |
| 包名 | `com.nhnent.SKQUEST` |
| 版本 | `7.5.8.KG` / versionCode `2079` |
| 引擎 | Unity 6000.0.69f1 + IL2CPP |
| 加固 | AppGuard（native 代码段加密） |
| 数值表 | 245 张 `.bf1`，Blowfish-CBC + raw deflate |
| 解密后 | 59.25 MB JSON |

---

## 目录结构

```
data/
├── character/    角色属性、外观、职业、部件、档案        10 files
├── combat/       战斗规则、技能、状态、弹道、特效        13 files
├── equipment/    武器、饰品、戒指、改造、继承            21 files
├── hero/         英雄成长、书阁、转职、卖价              23 files
├── item/         物品、材料、面包、合成、扭蛋            15 files
├── shop/         商店、拍卖、VIP、折扣                    15 files
├── pvp/          竞技场、掠夺战、大战、棋盘              14 files
├── stage/        关卡、章节、任务、奖励                  22 files
├── event/        各类活动、Bingo、Roguelike、音游        30 files
├── housing/      房屋、果园、钓鱼、采石                  16 files
├── story/        剧情、对话、过场、图鉴、音效            46 files
└── text/         中文本地化文本                          20 files
```

每个文件都是 `{"status":"success", "<root_key>": [...]}` 结构。

---

## 核心文档

| 文档 | 内容 |
|---|---|
| [docs/FORMAT.md](docs/FORMAT.md) | `.bf1` 文件格式与完整解密流程 |
| [docs/DAMAGE_FORMULA.md](docs/DAMAGE_FORMULA.md) | 伤害计算公式还原 |
| [docs/BATTLE_CONSTANTS.md](docs/BATTLE_CONSTANTS.md) | 战斗系统全部常数 |
| [docs/ADDSTATE_HANDLERS.md](docs/ADDSTATE_HANDLERS.md) | 267 种状态 handler 目录 |
| [docs/CHARACTER_STATS.md](docs/CHARACTER_STATS.md) | 角色属性系统 |
| [docs/TABLE_INDEX.md](docs/TABLE_INDEX.md) | 245 张表完整索引 |

---

## 解密链路概览

```
APK (base.apk + split_config.arm64_v8a.apk)
  └─ assets/bin/Data/Managed/Metadata/global-metadata.dat   (17 MB, IL2CPP v31)
  └─ lib/arm64-v8a/libil2cpp.so                             (90 MB, AppGuard 加密)
        ↓ 从运行中进程内存 dump 出代码段（48.8 MB 明文）
  └─ 服务端下发 .bf1 数值表 × 245
        ↓ Blowfish-CBC  (key = 4BAA366968045AD3, IV = 文件头 8 字节)
        ↓ PKCS7 去填充
        ↓ 剥离 "02 FF" + "get_xxx.data\0" 头
        ↓ raw deflate (wbits = -15)
  └─ 明文 JSON ✅
```

详细步骤见 [docs/FORMAT.md](docs/FORMAT.md)。

---

## 关键发现

### `.bf1` 双层封装

```
[0:8]   魔数 cf45b3166b8cd1d6（固定）
[8:16]  Blowfish-CBC IV
[16:]   密文
          ↓ 解密
[0:2]   02 FF（固定前缀）
[2:n]   "get_xxx.data\0"（表名，自校验用）
[n+1:]  raw deflate 压缩的 JSON
```

### 伤害基础倍率

来自 `combat/battle_settings` 的 `battleinfojson`：

| 普攻段数 | 倍率 |
|---|---|
| 1 / 2 / 3 段 | 0.20 |
| 4 / 5 段 | 0.25 |
| 6 段 | 0.30 |

技能平均倍率（用于战力计算）：`Avg_skill_1to3 = 1.935` → `Avg_skill_6 = 2.862`

### 战斗核心常数

```json
{
  "DEF_UPPER_BOUND": 100,
  "DEF_INCR_RATIO": 0.0034,
  "LEADER_BLOCK_RATIO": 1.75,
  "DAMAGE_REDUCED": 0.1,
  "DAMAGE_DECREASE_MIN_CAP": 0.2,
  "ATKSPD_CAP": 2.5,
  "HITRATE_MIN_CAP": 0.05,
  "HITRATE_MAX_CAP": 0.95
}
```

### 方块 Buff 倍率

| 等级 | 攻击型伤害 | 防御型减伤 | 恢复型治疗 |
|---|---|---|---|
| 1 | ×1.1 | 4 | ×2 |
| 2 | ×1.2 | 6 | ×5 |
| 3 | ×1.4 | 9 | ×8 |
| 4 | ×1.7 | 13 | ×11 |
| 5 | ×2.0 | 18 | ×14 |

---

## 数据可信度

- 245/245 个文件解密成功，全部通过 `json.loads` 校验
- 表名内嵌于文件内部（`get_xxx.data`），可用于验证解密正确性
- 角色属性表 3427 条，覆盖全部怪物、英雄与 Boss
- 状态表 15670 条，267 种 handler，覆盖全部被动与增益逻辑

---

## 工具

[pipeline/](pipeline/) 目录包含完整可复现的解密脚本：

- `decrypt_bf1.py` — `.bf1` 单文件/批量解密
- `categorize.py` — 按功能归类表文件

用法：

```bash
python pipeline/decrypt_bf1.py input.bf1 output.json
python pipeline/decrypt_bf1.py --batch ./datas ./out
```

---

## 免责声明

本项目为个人逆向学习成果存档，不含游戏客户端本体、不含任何可执行补丁、不提供任何修改游戏的手段。

游戏内容版权归 **NHN Entertainment Corp.** 与 **LoadComplete** 所有。
