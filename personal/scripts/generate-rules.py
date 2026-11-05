#!/usr/bin/env python3
"""从 personal-rules.yaml 生成稳定 IP 服务的 Mihomo 规则集。"""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

import yaml


ROOT = Path(__file__).resolve().parents[1]
GROUPS = ("stable-ip",)


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
        raise ValueError("总 YAML 只允许 stable-ip 分组；清空时保留 stable-ip: []")
    rules = data["stable-ip"]
    if not isinstance(rules, list):
        raise ValueError("stable-ip 必须是列表；没有域名时使用 []")
    seen = set()
    for index, rule in enumerate(rules, 1):
        location = f"stable-ip 第 {index} 条"
        if not isinstance(rule, str):
            raise ValueError(f"{location}：规则必须是字符串")
        parts = rule.split(",")
        if (len(parts) != 2 or parts[0] not in {"DOMAIN", "DOMAIN-SUFFIX"}
                or not parts[1] or any(character.isspace() for character in rule)):
            raise ValueError(f"{location}：使用 DOMAIN,域名 或 DOMAIN-SUFFIX,域名，不填写出口")
        if rule in seen:
            raise ValueError(f"{location}：重复规则 {rule}")
        seen.add(rule)
    return data


def render(rules):
    header = (
        "# 由 scripts/generate-rules.py 自动生成，请勿手工修改。\n"
        "# 唯一维护源：personal-rules.yaml 的 stable-ip 分组。\n"
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
    expected = render(data["stable-ip"])
    target = args.output_dir / "stable-ip.yaml"
    stale = not target.is_file() or target.read_bytes() != expected
    if args.check:
        if stale:
            print("生成文件需要更新：stable-ip.yaml", file=sys.stderr)
            return 1
    elif stale:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(target, expected)
    print(f"{'检查通过' if args.check else '生成完成'}：1 个规则集，{len(data['stable-ip'])} 条规则")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, yaml.YAMLError) as error:
        print(f"规则生成失败：{error}", file=sys.stderr)
        sys.exit(1)
