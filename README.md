# ovoii · sing-box 管理

基于 233boy/sing-box v1.18 的定制版，版本 1.0.3，修改日期 2026-10-23。
菜单和导出节点名称使用 `ovoii`，保留原有 `sb`、`sing-box` 命令，新增 `ovoii` 命令。
原作者、原项目及许可证信息见 [NOTICE.md](NOTICE.md) 和 [LICENSE](LICENSE)。

## GitHub 一键安装或更新

在 Linux 服务器以 root 执行：

```bash
curl -fsSL https://raw.githubusercontent.com/Crushuuu/ovoii-sing-box/main/bootstrap.sh -o ovoii-install.sh && bash ovoii-install.sh
```

入口下载固定版本的 GitHub Release 安装包，先核验内置 SHA-256，再执行。
新服务器安装管理脚本和固定的官方 sing-box 1.14.3 内核，默认生成 REALITY 节点。
已有兼容的 233boy/ovoii 安装只替换管理脚本，并备份；不重启服务，也不修改已有节点配置或内核。
遇到其他 sing-box 安装或不完整目录会停止，避免覆盖。

只下载并检查、不执行安装或更新：

```bash
bash ovoii-install.sh --check
```

安装后输入 `ovoii` 打开菜单。此仓库发布通用源码，不含任何个人服务器密码、节点或订阅凭据。
一键入口仅负责脚本安装和更新，订阅托管、分流、流量统计仍需另外配置。

## 已有 233boy sing-box 的服务器（建议使用这一条路径）

将 Release 的 `ovoii-sing-box-1.0.3.tar.gz` 上传到服务器，例如 `/root/`，以 root 依次执行：

```bash
cd /root
tar -xzf ovoii-sing-box-1.0.3.tar.gz
cd ovoii-sing-box-1.0.3
bash apply-brand.sh --check
bash apply-brand.sh --apply
ovoii
```

替换工具只操作 `/etc/sing-box/sh` 管理脚本和 `/usr/local/bin/ovoii` 快捷命令。
不会执行安装器，不停止或重启服务，不修改节点 UUID、私钥、SNI、端口、内核文件、
`/etc/sing-box/conf`、`config.json`、TLS 证书、Caddy 配置或服务定义。
原作者变量和 `/etc/caddy/233boy` 内部目录保留，以兼容已有安装。

`--check` 仅检查；默认不带参数也只检查。替换前会保存原脚本及 ovoii 快捷命令状态。
备份放在 `/etc/sing-box/ovoii-backups/`。命令会打印本次实际备份目录及对应回滚命令。
**使用该实际路径回滚，不要复制含占位符的示例。** 回滚也会备份操作前的脚本。
替换中途失败会尝试自动恢复；若进程被强杀或断电，请先检查备份和锁目录后恢复。

脚本替换后重新执行 `ovoii url` 或 `ovoii qr`，导出的节点备注将以 `ovoii-` 开头。
已有 iPhone 节点不会自动改名：可在客户端修改备注，或重新导入新链接。
节点链接包含连接凭据，请自行保存，不要公开分享。

## 没装过脚本的新服务器

在完整解压目录内，以 root 执行：

```bash
bash install.sh
```

安装器使用本地定制脚本，下载 sing-box 官方内核及依赖，默认创建 REALITY 节点。
需要可正常访问官方发布源的网络。1.0.2 已在 Ubuntu 22.04 VPS 完成全新安装与节点实际连通验证；
1.0.3 新增的 GitHub 入口另见 [VALIDATION.md](VALIDATION.md) 中的验收范围。
不要在已有服务的服务器上运行安装器来替换脚本；已有安装使用上一节的方法。
本包面向原脚本支持的 Linux amd64/arm64；用户当前目标是 Ubuntu 22.04。

## 常用命令

```bash
ovoii                 # 中文菜单
ovoii info            # 查看配置（包含凭据）
ovoii url             # 直接节点链接
ovoii qr              # 本地二维码，不调用第三方二维码网页
ovoii status          # 查看运行状态
ovoii help            # 完整命令帮助
ovoii update core     # 从 sing-box 官方项目更新内核
```

生成二维码需要 `qrencode`；没有该工具时仍会输出可直接导入的原始节点链接。
不会创建或托管 HTTPS 订阅服务。sing-box 是官方内核名称，保持不变。

新增、更改或删除配置、启动停止服务及更新内核等原有管理操作仍会产生对应变更。
“保留配置”只描述 `apply-brand.sh` 的行为，不代表所有管理命令都只读。

## 更新与维护

- 管理脚本不再从 233boy 的发布包自动更新，防止定制名称被覆盖。
- `ovoii update sh`、`ovoii update.sh` 和菜单中的“更新ovoii脚本”会提示本地升级方法。
- 收到新的完整 ovoii 包后，解压并运行 `bash apply-brand.sh --apply` 更新。
- 也可重新执行上述 GitHub 一键命令更新管理脚本；菜单内的原版在线脚本更新仍被阻止。
- `reinstall` 只显示说明，不再执行自动卸载和原版重装。
- 内核和 Caddy 仍使用各自官方项目更新；兼容性与升级版本需要单独验证。
- 本次没有全面重构上游下载、权限及协议实现，也没有进行完整安全审计。

## 本地验证

需要 Bash 4+、Python 3 和 jq。执行：

```bash
python3 tests/test_customization.py
```

macOS 自带 Bash 3.2 不满足上游原脚本要求，可用 `OVOII_TEST_BASH=/path/to/bash` 指定 Bash 4+。
另运行 `python3 tests/test_bootstrap.py` 验证 GitHub 入口的安装/更新分支、完整性校验和失败保护。
测试只在临时目录模拟安装，检查安装完成退出码、节点连接参数不变、菜单和二维码输出、更新保护、
替换和回滚、失败恢复与配置完整性。真实 VPS、iPhone 导入、网络速度及软路由连接需另行验收。
