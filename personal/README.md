# Personal 稳定 IP 规则

日常只修改 `personal-rules.yaml` 的 `stable-ip` 分组。提交 `main` 后，GitHub Actions 校验并生成 `rules/stable-ip.yaml`；不要手工修改生成文件。

AI 服务优先复用机场自带的完整 OpenAI 规则组。此仓库仅补充当前机场规则未覆盖的 3 条：精确域名 `aistudio.google.com`、`ai.google.dev`，以及 `grok.com` 及其子域名。`ai.google.dev` 不扩展到其子站；规则不包含整个 `google.com`、`googleapis.com` 或 YouTube。其他已覆盖的服务、共享登录和静态资源继续由机场规则处理。此仓库不另行维护 OpenAI 规则表。

本机 Personal 脚本使用 `behavior: classical`、`format: yaml` 加载输出，将规则接到德州链式落地策略并放在机场规则之前。节点和连接参数由本机配置管理，本仓库只存规则和生成工具。

新增地址写成 `DOMAIN,精确域名` 或 `DOMAIN-SUFFIX,域名后缀`，不填写策略名称。停用时保留 `stable-ip: []`。重复分组、重复规则和不支持的规则格式会终止生成，不替换现有结果。

```sh
python -m pip install PyYAML==6.0.3
python scripts/generate-rules.py
python scripts/generate-rules.py --check
```

工作流只提交 `rules/stable-ip.yaml`，使用 GitHub 自动提供的 `GITHUB_TOKEN`。普通推送遇到并发修改会失败，不会强制覆盖 `main`。首次上传后可在 Actions 手动运行 **Generate personal rules**，并在 Clash 规则集页面刷新一次；更新机场订阅不保证立即重新下载规则集。
