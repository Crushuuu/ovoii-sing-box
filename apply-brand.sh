#!/bin/bash
# ovoii customization, 2026-10-23. GPL-3.0; see NOTICE.md.
# Replaces management scripts only. Does not run the installer or restart services.
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
target_root=/etc/sing-box
bin_dir=/usr/local/bin
mode=--check
rollback_dir=
stage_dir=
backup_dir=
swapped=0
old_moved=0
link_touched=0
link_existed=0
link_target=
files=(sing-box.sh install.sh apply-brand.sh README.md NOTICE.md LICENSE src)

fail() { echo "ovoii: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case $1 in
        --check|--apply) mode=$1; shift ;;
        --rollback)
            [[ $# -ge 2 ]] || fail "--rollback 缺少备份目录"
            mode=$1; rollback_dir=$2; shift 2 ;;
        --root|--bin-dir)
            [[ $# -ge 2 ]] || fail "$1 缺少目录"
            if [[ $1 == --root ]]; then target_root=$2; else bin_dir=$2; fi
            shift 2 ;;
        *) fail "用法: bash apply-brand.sh [--check|--apply|--rollback 备份目录]" ;;
    esac
done

[[ $target_root == /* && $bin_dir == /* ]] || fail "目录必须为绝对路径"
[[ -d $target_root && ! -L $target_root ]] || fail "未发现已有 sing-box 安装目录"
target_root=$(cd -- "$target_root" && pwd -P)
[[ -d $bin_dir ]] || fail "命令目录不存在: $bin_dir"
bin_dir=$(cd -- "$bin_dir" && pwd -P)
[[ -d $target_root/sh && ! -L $target_root/sh ]] || fail "未发现可替换的管理脚本目录"
[[ -f $target_root/sh/src/core.sh && -x $target_root/bin/sing-box && -d $target_root/conf ]] ||
    fail "目标不是支持的 233boy/sing-box 安装布局"
[[ ! -L $target_root/ovoii-backups ]] || fail "备份目录不能是符号链接"

command_path=$bin_dir/ovoii
if [[ -e $command_path || -L $command_path ]]; then
    [[ -L $command_path ]] || fail "ovoii 命令已存在且不是符号链接，不会覆盖"
    link_target=$(readlink "$command_path")
    [[ $link_target == "$target_root/sh/sing-box.sh" ]] || fail "ovoii 命令属于其他安装，不会覆盖"
    link_existed=1
fi

for file in "${files[@]}"; do
    [[ -e $source_dir/$file ]] || fail "安装包不完整: $file"
done
for file in "$source_dir/"*.sh "$source_dir/src/"*.sh; do
    bash -n "$file" || fail "语法检查失败: $file"
done

if [[ $mode == --check ]]; then
    echo "ovoii 检查通过。目标: $target_root/sh"
    echo "应用命令: bash apply-brand.sh --apply"
    echo "只替换管理脚本；保留节点配置、密钥、端口、内核和服务。"
    exit 0
fi

[[ -w $target_root && -w $bin_dir ]] || fail "没有写入权限，请以 root 执行"

# Serialize apply/rollback operations; no service lock or restart is needed.
lock_dir=$target_root/.ovoii-brand-lock
mkdir "$lock_dir" 2>/dev/null || fail "另一替换任务正在运行，或存在待检查的锁: $lock_dir"

cleanup() {
    rc=$?
    trap - EXIT
    if [[ $rc -ne 0 && $old_moved == 1 ]]; then
        if [[ $swapped == 1 && -d $target_root/sh ]]; then
            mv "$target_root/sh" "$backup_dir/failed-sh" || true
        fi
        if [[ ! -e $target_root/sh && -d $backup_dir/sh ]]; then
            mv "$backup_dir/sh" "$target_root/sh" || true
        fi
        if [[ $link_touched == 1 ]]; then
            if [[ $link_existed == 1 ]]; then
                ln -sfn "$link_target" "$command_path" || true
            else
                rm -f "$command_path" || true
            fi
        fi
        echo "替换失败，已尝试恢复原管理脚本；请检查 ${backup_dir}。" >&2
    fi
    [[ ! $stage_dir || ! -d $stage_dir ]] || rm -rf -- "$stage_dir"
    rmdir "$lock_dir" 2>/dev/null || true
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ $mode == --rollback ]]; then
    [[ -d $rollback_dir ]] || fail "备份目录不存在"
    rollback_dir=$(cd -- "$rollback_dir" && pwd -P)
    [[ $rollback_dir == "$target_root/ovoii-backups/"* ]] || fail "只能恢复当前安装的 ovoii 备份"
    [[ -d $rollback_dir/sh && -f $rollback_dir/sh/src/core.sh && -f $rollback_dir/command-state ]] || fail "备份不完整"
    restore_link_state=$(cat "$rollback_dir/command-state")
    [[ $restore_link_state == present || $restore_link_state == absent ]] || fail "命令备份状态无效"
    payload_dir=$rollback_dir/sh
else
    payload_dir=$source_dir
fi

umask 077
mkdir -p "$target_root/ovoii-backups"
backup_dir=$(mktemp -d "$target_root/ovoii-backups/$(date +%Y%m%d-%H%M%S).XXXXXX")
if [[ $link_existed == 1 ]]; then echo present; else echo absent; fi >"$backup_dir/command-state"
stage_dir=$(mktemp -d "$target_root/.ovoii-sh.XXXXXX")
if [[ $mode == --rollback ]]; then
    cp -a "$payload_dir/." "$stage_dir/"
else
    for file in "${files[@]}"; do cp -R "$payload_dir/$file" "$stage_dir/"; done
    chmod +x "$stage_dir/sing-box.sh" "$stage_dir/apply-brand.sh" "$stage_dir/install.sh"
fi

for file in "$stage_dir/"*.sh "$stage_dir/src/"*.sh; do bash -n "$file"; done
mv "$target_root/sh" "$backup_dir/sh"
old_moved=1
mv "$stage_dir" "$target_root/sh"
stage_dir=
swapped=1
link_touched=1
if [[ $mode == --rollback && $restore_link_state == absent ]]; then
    rm -f "$command_path"
else
    ln -sfn "$target_root/sh/sing-box.sh" "$command_path"
fi
echo "ovoii 管理脚本替换完成，未重启服务。"
echo "本次操作前的备份: $backup_dir"
echo "如需撤销本次操作: bash $source_dir/apply-brand.sh --rollback $backup_dir"
