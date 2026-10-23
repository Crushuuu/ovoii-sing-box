#!/bin/bash
# ovoii GitHub installer, 2026-10-23. GPL-3.0; see NOTICE.md.
set -euo pipefail

version=1.0.3
repository=Crushuuu/ovoii-sing-box
package_sha256=3c5f4180b1ba1fce618243345711c8d477fedaf3b709396d867569b3fdfc3304
mode=${1:-auto}
fail() { echo "ovoii: $*" >&2; exit 1; }
case "$mode" in
    --help|-h)
        echo '用法: bash bootstrap.sh [--check]'
        echo '默认：新服务器安装；已有兼容安装仅更新管理脚本，保留节点配置。'
        echo '--check：下载、校验并检查，不安装或更新。'
        exit 0 ;;
    auto|--check) [[ $# -le 1 ]] || fail '参数过多，请使用 --help' ;;
    *) fail '未知参数，请使用 --help' ;;
esac
[[ $EUID == 0 ]] || fail '请以 root 执行。'
[[ $(uname -s) == Linux ]] || fail '仅支持 Linux 服务器。'
[[ ${BASH_VERSINFO[0]} -ge 4 ]] || fail '需要 Bash 4 或更新版本。'
case $(uname -m) in x86_64|amd64|aarch64|arm64) ;; *) fail '仅支持 amd64/arm64。' ;; esac
command -v tar >/dev/null || fail '请先安装 tar。'
command -v sha256sum >/dev/null || fail '请先安装 coreutils（sha256sum）。'

if [[ -d /etc/sing-box/sh && -f /etc/sing-box/sh/src/core.sh ]]; then
    operation=update
elif [[ -e /etc/sing-box || -e /usr/local/bin/ovoii || -L /usr/local/bin/ovoii ||
        -e /usr/local/bin/sing-box || -L /usr/local/bin/sing-box ]]; then
    fail '发现不完整或其他 sing-box 安装，请检查现有安装后再操作。'
else
    operation=install
fi

umask 077
work_dir=$(mktemp -d)
trap 'rm -rf -- "$work_dir"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
archive=$work_dir/package.tar.gz
url="https://github.com/$repository/releases/download/v$version/ovoii-sing-box-$version.tar.gz"
echo "ovoii ${version}：下载并校验安装包。"
if command -v curl >/dev/null; then
    curl --fail --show-error --silent --location --retry 2 --connect-timeout 15 --max-time 180 "$url" -o "$archive"
elif command -v wget >/dev/null; then
    wget --quiet --timeout=30 --tries=3 -O "$archive" "$url"
else
    fail '请先安装 curl 或 wget。'
fi
printf '%s  %s\n' "$package_sha256" "$archive" | sha256sum --check --status || fail '安装包 SHA-256 校验失败，已停止。'
tar -xzf "$archive" -C "$work_dir"
package_dir=$work_dir/ovoii-sing-box-$version
for item in install.sh apply-brand.sh sing-box.sh src/brand.sh LICENSE NOTICE.md; do
    [[ -f $package_dir/$item ]] || fail "安装包不完整: $item"
done
for item in "$package_dir/"*.sh "$package_dir/src/"*.sh; do bash -n "$item"; done
if [[ $operation == update ]]; then
    if [[ $mode == --check ]]; then
        bash "$package_dir/apply-brand.sh" --check
    else
        echo '检测到已有安装：仅更新管理脚本，保留节点、密钥、端口、内核和服务。'
        bash "$package_dir/apply-brand.sh" --apply
    fi
elif [[ $mode == --check ]]; then
    echo '安装包检查通过；当前为新服务器，未执行安装。'
else
    echo '新服务器：安装 ovoii 管理脚本和已验证的 sing-box 1.14.3 内核。'
    bash "$package_dir/install.sh" --core-version v1.14.3
fi
if [[ $mode != --check ]]; then echo '操作完成。输入 ovoii 打开管理菜单。'; fi
