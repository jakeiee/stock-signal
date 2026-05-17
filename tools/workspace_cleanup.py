"""
工作空间清理工具

功能：
1. 清理 /Users/liuyi/WorkBuddy/ 下的50+个时间戳目录
2. 保留最近10个会话
3. 90天前的归档到 cold storage
4. 无价值产物（无md/py/csv/json文件）的直接删除

使用方法：
    python tools/workspace_cleanup.py          # 执行清理
    python tools/workspace_cleanup.py --dry-run  # 仅预览，不实际删除
"""

import os
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Tuple

# 配置
WORKBUDDY_DIR = Path("/Users/liuyi/WorkBuddy")
KEEP_RECENT = 10  # 保留最近10个
ARCHIVE_DIR = WORKBUDDY_DIR / "archived"
COLD_THRESHOLD_DAYS = 90  # 90天前的归档
VALUABLE_EXTENSIONS = [".md", ".py", ".csv", ".json", ".txt", ".log"]


def is_timestamp_dir(path: Path) -> bool:
    """判断是否为时间戳目录（14位数字）"""
    return path.is_dir() and path.name.isdigit() and len(path.name) == 14


def get_dir_timestamp(path: Path) -> datetime:
    """从目录名解析时间戳"""
    return datetime.strptime(path.name, "%Y%m%d%H%M%S")


def has_valuable_artifacts(path: Path) -> bool:
    """检查目录是否包含有价值的产物"""
    for ext in VALUABLE_EXTENSIONS:
        if list(path.glob(f"**/*{ext}")):
            return True
    return False


def get_dir_size(path: Path) -> int:
    """计算目录大小（字节）"""
    total = 0
    for entry in path.rglob("*"):
        if entry.is_file():
            total += entry.stat().st_size
    return total


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def cleanup_workspaces(dry_run: bool = False) -> Tuple[int, int, int]:
    """
    清理工作空间
    
    Args:
        dry_run: 是否为预览模式（不实际删除）
    
    Returns:
        (保留数量, 归档数量, 删除数量)
    """
    # 1. 列出所有时间戳目录
    all_dirs = [d for d in WORKBUDDY_DIR.iterdir() if is_timestamp_dir(d)]
    all_dirs_sorted = sorted(all_dirs, key=lambda x: x.name, reverse=True)
    
    if not all_dirs_sorted:
        print("✓ 没有找到时间戳目录")
        return 0, 0, 0
    
    print(f"发现 {len(all_dirs_sorted)} 个工作空间目录")
    
    # 2. 保留最近 KEEP_RECENT 个
    recent_dirs = all_dirs_sorted[:KEEP_RECENT]
    print(f"✓ 保留最近 {len(recent_dirs)} 个目录:")
    for d in recent_dirs:
        print(f"  ✓ {d.name}")
    
    # 3. 处理剩余的（归档或删除）
    archived_count = 0
    deleted_count = 0
    
    for d in all_dirs_sorted[KEEP_RECENT:]:
        # 解析时间戳
        try:
            timestamp = get_dir_timestamp(d)
        except ValueError:
            print(f"⚠ 无法解析目录名: {d.name}")
            continue
        
        age = (datetime.now() - timestamp).days
        
        # 判断是否有价值
        if has_valuable_artifacts(d):
            # 有价值：归档
            if not dry_run:
                archive_to_cold_storage(d)
            archived_count += 1
            print(f"  📦 归档: {d.name} (年龄: {age}天, 大小: {format_size(get_dir_size(d))})")
        else:
            # 无价值：删除
            if not dry_run:
                shutil.rmtree(d)
            deleted_count += 1
            print(f"  🗑️  删除: {d.name} (年龄: {age}天, 无价值产物)")
    
    # 4. 输出总结
    print(f"\n{'='*50}")
    print(f"清理完成！")
    print(f"  保留: {len(recent_dirs)} 个")
    print(f"  归档: {archived_count} 个")
    print(f"  删除: {deleted_count} 个")
    if dry_run:
        print(f"\n⚠️  这是预览模式，没有实际删除/归档文件")
        print(f"   添加 --execute 参数来执行实际清理")
    
    return len(recent_dirs), archived_count, deleted_count


def archive_to_cold_storage(dir_path: Path):
    """归档到冷存储"""
    ARCHIVE_DIR.mkdir(exist_ok=True)
    target = ARCHIVE_DIR / dir_path.name
    
    if target.exists():
        print(f"⚠ 归档目录已存在: {target}")
        return
    
    shutil.move(str(dir_path), str(target))


def list_archived():
    """列出已归档的目录"""
    if not ARCHIVE_DIR.exists():
        print("⚠ 归档目录不存在")
        return
    
    archived = [d for d in ARCHIVE_DIR.iterdir() if d.is_dir()]
    if not archived:
        print("⚠ 归档目录为空")
        return
    
    print(f"\n已归档 {len(archived)} 个工作空间:")
    for d in sorted(archived, key=lambda x: x.name, reverse=True):
        size = format_size(get_dir_size(d))
        print(f"  📦 {d.name} ({size})")


def main():
    parser = argparse.ArgumentParser(description="工作空间清理工具")
    parser.add_argument("--dry-run", action="store_true", help="预览模式（不实际删除）")
    parser.add_argument("--execute", action="store_true", help="执行实际清理")
    parser.add_argument("--list-archived", action="store_true", help="列出已归档的目录")
    
    args = parser.parse_args()
    
    if args.list_archived:
        list_archived()
        return
    
    if not args.dry_run and not args.execute:
        print("⚠️  请指定模式:")
        print("  --dry-run   预览模式（默认，不实际删除）")
        print("  --execute   执行实际清理")
        print("\n建议先运行: python tools/workspace_cleanup.py --dry-run")
        return
    
    dry_run = not args.execute
    cleanup_workspaces(dry_run)


if __name__ == "__main__":
    main()
