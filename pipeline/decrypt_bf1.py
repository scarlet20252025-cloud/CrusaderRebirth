#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
克鲁赛德战记 .bf1 数值表解密工具

文件格式:
    [0:8]    魔数 cf45b3166b8cd1d6 —— 同时也是 Blowfish-CBC 的 IV
    [8:]     密文
              ↓ Blowfish-CBC(IV = d[0:8]) 解密 + PKCS7 去填充
    [0:2]    固定前缀 02 FF
    [2:n]    "get_xxx.data\\0"  表名（自校验用）
    [n+1:]   raw deflate 压缩的 JSON

注意: 文件偏移 0x08 起的 8 字节是密文首块，不是 IV。
      同一批下发的表首块相同，是因为它们用同一个 IV（即魔数）加密
      且明文都以 "get_" 开头。

依赖: pycryptodome
    pip install pycryptodome

用法:
    python decrypt_bf1.py input.bf1 output.json
    python decrypt_bf1.py --batch ./datas ./out
    python decrypt_bf1.py --info input.bf1
"""

import argparse
import json
import os
import sys
import zlib

try:
    from Crypto.Cipher import Blowfish
except ImportError:
    sys.exit("需要 pycryptodome: pip install pycryptodome")

# Blowfish 密钥，来自 IL2CPP 元数据 LC.Security.Cryptography.kBLOWFISH_KEY
BF_KEY = bytes.fromhex("4BAA366968045AD3")
MAGIC = bytes.fromhex("cf45b3166b8cd1d6")
PREFIX = b"\x02\xff"
BLOCK = 8


def decrypt_bf1(raw: bytes):
    """解密 .bf1 字节流，返回 (表名, JSON 对象)。"""
    if len(raw) < 24:
        raise ValueError("文件过短")
    if raw[:8] != MAGIC:
        raise ValueError("魔数不匹配: %s" % raw[:8].hex())

    iv = raw[:8]          # IV == 魔数
    ct = raw[8:]          # 首块密文从偏移 8 开始

    n = (len(ct) // BLOCK) * BLOCK
    if n == 0:
        raise ValueError("密文长度不足一个块")

    plain = Blowfish.new(BF_KEY, Blowfish.MODE_CBC, iv).decrypt(ct[:n])

    pad = plain[-1]
    if 1 <= pad <= BLOCK and plain[-pad:] == bytes([pad]) * pad:
        plain = plain[:-pad]

    if plain[:2] != PREFIX:
        raise ValueError("前缀不匹配: %s (期望 02ff)" % plain[:2].hex())

    nul = plain.find(b"\x00", 2)
    if nul < 2:
        raise ValueError("未找到表名终止符")

    name = plain[2:nul].decode("ascii", "replace")
    inner = plain[nul + 1:]

    try:
        data = zlib.decompressobj(-15).decompress(inner)
    except zlib.error as e:
        raise ValueError("deflate 解压失败: %s" % e)

    return name, json.loads(data.decode("utf-8"))


def process(src: str, dst: str):
    raw = open(src, "rb").read()
    name, obj = decrypt_bf1(raw)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    return name, obj


def main():
    ap = argparse.ArgumentParser(description="克鲁赛德战记 .bf1 解密工具")
    ap.add_argument("input", help="输入 .bf1 文件，或 --batch 时为目录")
    ap.add_argument("output", nargs="?", help="输出 .json 文件，或 --batch 时为目录")
    ap.add_argument("--batch", action="store_true", help="批量解密目录下所有 .bf1")
    ap.add_argument("--info", action="store_true", help="只显示文件信息，不写输出")
    args = ap.parse_args()

    if args.info:
        raw = open(args.input, "rb").read()
        name, obj = decrypt_bf1(raw)
        root = [k for k in obj if k != "status"]
        count = len(obj[root[0]]) if root and hasattr(obj[root[0]], "__len__") else 0
        print("文件      : %s" % args.input)
        print("大小      : %d bytes" % len(raw))
        print("表名      : %s" % name)
        print("root key  : %s" % (root[0] if root else "(none)"))
        print("条目数    : %d" % count)
        return

    if args.batch:
        if not args.output:
            sys.exit("--batch 需要指定输出目录")
        os.makedirs(args.output, exist_ok=True)
        ok = fail = 0
        for fn in sorted(os.listdir(args.input)):
            if not fn.endswith(".bf1"):
                continue
            src = os.path.join(args.input, fn)
            dst = os.path.join(args.output, fn[:-4] + ".json")
            try:
                name, _ = process(src, dst)
                ok += 1
                print("  OK   %-44s -> %s" % (fn, name))
            except Exception as e:
                fail += 1
                print("  FAIL %-44s %s" % (fn, e))
        print("\n完成: %d 成功, %d 失败" % (ok, fail))
        return

    name, obj = process(args.input, args.output)
    root = [k for k in obj if k != "status"]
    count = len(obj[root[0]]) if root and hasattr(obj[root[0]], "__len__") else 0
    print("解密成功: %s" % name)
    print("root key: %s, 条目数: %d" % (root[0] if root else "-", count))
    print("输出    : %s" % args.output)


if __name__ == "__main__":
    main()
