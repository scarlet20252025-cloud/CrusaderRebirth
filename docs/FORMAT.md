# `.bf1` 文件格式与解密流程

克鲁赛德战记 v7.5.8.KG 的服务端数值表以 `.bf1` 扩展名下发。本文记录完整格式与已还原的解密流程。

> 本文经过实测验证：随仓库提供的 `pipeline/decrypt_bf1.py` 对 245/245 个原始文件解密成功，
> 输出与参考数据逐字节等价。

---

## 一、文件格式

### 原始文件

```
偏移      长度    内容
0x00      8      魔数 cf45b3166b8cd1d6
                 ↳ 同时充当 Blowfish-CBC 的 IV
0x08      N      Blowfish-CBC 密文（N 为 8 的倍数）
```

**这是本项目最容易搞错的一点**：偏移 `0x08` 处的 8 字节**不是 IV，而是密文首块**。

### 为什么容易误判

245 个文件中，`d[0:8]` 完全相同（魔数），而 `d[8:16]` 出现 **67 种不同值**。
乍看像是"按表分组的 IV"。但反证如下：

`d[8:16]` 的 67 种取值，完全按**表名前缀**分组：

| d[8:16] | 文件数 | 表名前缀 |
|---|---|---|
| `f59f0b2e651aeaae` | 28 | `ch` (character_*) |
| `1fbef6b846434584` | 21 | `te` (text*, terms) |
| `d758016e9e03ba15` | 12 | `he` (help, hero*) |
| `34d82fe1fc9c52d0` | 11 | `st` (stage*) |
| `c7875449c1ef754c` | 8 | `we` (weapon*) |
| `511d0dd91028f3b1` | 7 | `cu` (cutscene*) |
| `50961b0a9cc735c7` | 7 | `oz` (oztalk*) |
| ... | ... | 15/15 组均为单一前缀 |

如果是 IV，取值应当与明文内容无关；而这里它精确对应明文首块 `"get_xx..."` 的不同，
说明它是 **CBC 用同一 IV 加密相同前缀所产生的密文首块**。

因此：**IV = 魔数 `cf45b3166b8cd1d6`**，密文从偏移 8 开始。

### 解密后结构

```
偏移      长度    内容
0x00      2      固定前缀  02 ff
0x02      n      表名，UTF-8，以 \0 结尾，如 "get_character_stat.data"
0x02+n+1  M      raw deflate 压缩的 JSON
```

前缀 `02 ff` 在 **245/245** 个文件中完全一致。
内嵌表名可作为解密正确性的**自校验**：若密钥或 IV 错误，解出的表名不会是 `get_xxx.data`。

---

## 二、解密步骤

### 参数

| 参数 | 值 |
|---|---|
| 算法 | Blowfish-CBC |
| Key | `4BAA366968045AD3`（8 字节） |
| IV | 文件 `[0x00:0x08]`（即魔数本身） |
| 密文起点 | 文件偏移 `0x08` |
| 填充 | PKCS7（块大小 8） |
| 内层 | raw deflate，`zlib` 的 `wbits = -15` |

**Key 来源**：IL2CPP 元数据中类 `LC.Security.Cryptography`（TypeDef 8920）含静态字段
`kBLOWFISH_KEY` / `kBLOWFISH_IV` / `kAES_DEC_KEY` / `kAES_ENC_KEY` / `k3DES_KEY`。
其字符串字面量表中有 6 个 8/16 字节十六进制串，`4BAA366968045AD3` 为其中之一，实测唯一能正确解密者。

### 流程

```
1. 读文件 → d
2. 校验 d[0:8] == cf45b3166b8cd1d6
3. iv = d[0:8]            ← 魔数即 IV
4. ct = d[8:]             ← 密文从偏移 8 开始
5. plain = Blowfish-CBC-Decrypt(key, iv, ct[:len//8*8])
6. 去 PKCS7 填充：
     pad = plain[-1]
     若 1 ≤ pad ≤ 8 且 plain[-pad:] 全等于 pad，则 plain = plain[:-pad]
7. 校验 plain[0:2] == b"\x02\xff"
8. nul = plain.find(b"\x00", 2)
   name  = plain[2:nul]              → 形如 b"get_xxx.data"
   inner = plain[nul+1:]
9. json_bytes = zlib.decompressobj(-15).decompress(inner)
10. json.loads(json_bytes)
```

### 参考实现

```python
import zlib, json
from Crypto.Cipher import Blowfish

BF_KEY = bytes.fromhex("4BAA366968045AD3")
MAGIC  = bytes.fromhex("cf45b3166b8cd1d6")

def decrypt_bf1(path):
    d = open(path, "rb").read()
    assert d[:8] == MAGIC, "魔数不匹配"

    iv, ct = d[:8], d[8:]          # IV = 魔数；密文从偏移 8 起
    n = (len(ct) // 8) * 8
    plain = Blowfish.new(BF_KEY, Blowfish.MODE_CBC, iv).decrypt(ct[:n])

    pad = plain[-1]
    if 1 <= pad <= 8 and plain[-pad:] == bytes([pad]) * pad:
        plain = plain[:-pad]

    assert plain[:2] == b"\x02\xff", "前缀不匹配"
    nul = plain.find(b"\x00", 2)
    name = plain[2:nul].decode("ascii")
    inner = plain[nul + 1:]

    raw = zlib.decompressobj(-15).decompress(inner)
    return name, json.loads(raw.decode("utf-8"))
```

完整可运行版本见 [`pipeline/decrypt_bf1.py`](../pipeline/decrypt_bf1.py)。

---

## 三、为什么是这几层

### 外层为什么是 Blowfish 而不是 AES

`LC.Security.Cryptography` 同时提供 `Encrypt_BlowFish` / `AESEncrypt256` / `Encrypt_3DES` 多套方法，
但实际用于数值表的是 **Blowfish**。判定依据：

1. 去头后密文长度恒为 8 的倍数（Blowfish 块大小），而非 16（AES 块大小）
2. 用 Blowfish 密钥可解出内嵌表名 `get_xxx.data`
3. 二进制中**不含** AES S-box 或 Blowfish P-array 常量 —— 说明密码学由 IL2CPP 托管层
   （.NET `System.Security.Cryptography`）实现，而非原生代码

### 内层为什么是 deflate 而非二次加密

- 解密后以 `02 ff` 开头，是自定义头而非密文
- 直接 `zlib.decompressobj(-15)` 即得合法 JSON
- 内层熵 7.9~8.0 是 deflate 压缩的正常结果

> 曾误判内层为二次加密，因为大表熵接近 8.0。真正的区分点：
> **小表的 deflate 输出熵明显偏低**（如 `accessory_set` inner 仅 137 字节、熵 6.43）。
> 加密不会有这种分布。

---

## 四、IL2CPP 侧的相关线索

从 `global-metadata.dat`（v31）解析出：

**TypeDef 8920 — `LC.Security.Cryptography`**

字段：
```
_inst              （单例）
kBLOWFISH_KEY      （Blowfish 密钥）
kBLOWFISH_IV       （Blowfish IV）
k3DES_KEY          （3DES 密钥）
_kDESKey
kAES_DEC_KEY       （AES 解密密钥）
kAES_ENC_KEY       （AES 加密密钥）
kAES_ENC_IV        （AES IV）
```

方法：
```
get_Inst
.ctor
get_BlowFish
Encrypt_BlowFish   ×2
Decrypt_BlowFish   ×2
Encrypt_3DES
Decrypt_3DES       ×2
Decrypt_DES
AESEncrypt256      ×4
AESDecrypt256      ×4
```

**数值表加载相关类**：

- `RemoteDataLoader`（TypeDef 2736，38 个方法）
  - `LoadData` / `LoadLocalData` / `Co_LoadStaticDatas` / `LoadDynamicDefinitions`
  - `HandleResponseDefinition` —— 处理服务端下发的表定义
- `DataPatcher`（TypeDef 760，26 个方法）
  - `GetDataFullPathWithExtension` —— 拼出 `.bf1` 路径
  - `DataLoadAsync` / `DataPatchAsync` / `PatchData` —— 下载与写入

---

## 五、数据来源

数值表**不在 APK 内**，首次启动后由服务端下发，落在：

```
/storage/emulated/0/Android/data/com.nhnent.SKQUEST/files/Datas/*.bf1      (245 个)
/storage/emulated/0/Android/data/com.nhnent.SKQUEST/files/Assets/          (3546 个资源包)
/storage/emulated/0/Android/data/com.nhnent.SKQUEST/files/il2cpp/Metadata/global-metadata.dat
```

`global-metadata.dat` 也被复制到外部存储（17,006,252 字节），说明该版本把 IL2CPP 元数据外置。

---

## 六、复现要点

1. 从 MuMu 模拟器 VDI 提取 APK（VirtualBox VDI + ext4 extent tree 解析）
2. IL2CPP 元数据 v31，**`Il2CppTypeDefinition` 结构体大小为 88 字节**
   （非常规 92 字节，需通过成员归属率反推确认）
3. `libil2cpp.so` 的 `il2cpp` 段被 AppGuard 加密（熵 7.996），
   需从运行中进程 `/proc/<pid>/mem` dump 出解密后的代码段
4. **数值表本身与原生代码无关**：只要拿到 `.bf1` + Blowfish key 即可离线解密，
   不需要脱壳、不需要运行时
