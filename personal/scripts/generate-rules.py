#!/usr/bin/env python3
"""从 personal-rules.yaml 生成 Personal 的 Mihomo 规则集。"""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

import yaml


ROOT = Path(__file__).resolve().parents[1]
GROUPS = ("stable-ip", "vps-socks")
VPS_SOCKS_RULE = "AND,((IP-CIDR,209.240.165.181/32),(DST-PORT,42356))"


class UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise ValueError(f"第 {key_node.start_mark.line + 1} 行：分组名必须是字符串")
            if key in result:
                raise ValueError(f"第 {key_node.start_mark.line + 1} 行：重复分组 {key}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def load_source(source):
    with source.open(encoding="utf-8-sig") as stream:
        data = yaml.load(stream, Loader=UniqueKeyLoader)
    if not isinstance(data, dict) or set(data) != set(GROUPS):
        raise ValueError("总 YAML 必须包含 stable-ip、vps-socks 分组；清空时保留 分组名: []")
    seen = set()
    for group in GROUPS:
        rules = data[group]
        if not isinstance(rules, list):
            raise ValueError(f"{group} 必须是列表；没有规则时使用 []")
        for index, rule in enumerate(rules, 1):
            location = f"{group} 第 {index} 条"
            if not isinstance(rule, str):
                raise ValueError(f"{location}：规则必须是字符串")
            if group == "vps-socks":
                if rule != VPS_SOCKS_RULE:
                    raise ValueError(f"{location}：vps-socks 只允许指定目的主机和端口的 AND 组合规则")
            else:
                parts = rule.split(",")
                if (len(parts) != 2 or parts[0] not in {"DOMAIN", "DOMAIN-SUFFIX"}
                        or not parts[1] or any(character.isspace() for character in rule)):
                    raise ValueError(f"{location}：使用 DOMAIN,域名 或 DOMAIN-SUFFIX,域名，不填写出口")
            if rule in seen:
                raise ValueError(f"{location}：重复规则 {rule}")
            seen.add(rule)
    return data


def render(group, rules):
    header = (
        "# 由 scripts/generate-rules.py 自动生成，请勿手工修改。\n"
        f"# 唯一维护源：personal-rules.yaml 的 {group} 分组。\n"
    )
    body = "payload: []\n" if not rules else "payload:\n" + "".join(
        f"  - {json.dumps(rule, ensure_ascii=False)}\n" for rule in rules
    )
    return (header + body).encode("utf-8")


def atomic_write(target, content):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".generated-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "personal-rules.yaml")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "rules")
    parser.add_argument("--check", action="store_true", help="只检查生成文件是否与总文件一致")
    args = parser.parse_args()
    data = load_source(args.source)
    expected = {f"{group}.yaml": render(group, data[group]) for group in GROUPS}
    stale = [name for name, content in expected.items()
             if not (args.output_dir / name).is_file()
             or (args.output_dir / name).read_bytes() != content]
    if args.check:
        if stale:
            print("生成文件需要更新：" + ", ".join(stale), file=sys.stderr)
            return 1
    elif stale:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name in stale:
            atomic_write(args.output_dir / name, expected[name])
    count = sum(len(data[group]) for group in GROUPS)
    print(f"{'检查通过' if args.check else '生成完成'}：{len(GROUPS)} 个规则集，{count} 条规则")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, yaml.YAMLError) as error:
        print(f"规则生成失败：{error}", file=sys.stderr)
        sys.exit(1)
