#!/bin/bash
# AI助手快速学习记录脚本
# 适用于开发过程中快速记录重要发现

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LEARNINGS_DIR="$PROJECT_ROOT/.learnings"

# 检查目录是否存在
mkdir -p "$LEARNINGS_DIR"
touch "$LEARNINGS_DIR/LEARNINGS.md" "$LEARNINGS_DIR/ERRORS.md" "$LEARNINGS_DIR/FEATURE_REQUESTS.md"

# 获取日期和ID
DATE=$(date +%Y%m%d)
ISO_DATE=$(date -Iseconds)

# 获取下一个ID的函数
get_next_id() {
    local file=$1
    local prefix=$2
    
    # 查找现有的最高数字编号
    local max_num=0
    if [[ -f "$file" ]]; then
        while IFS= read -r line; do
            if [[ $line =~ ^#\#\ \[${prefix}-${DATE}-([0-9]{3})\] ]]; then
                local num="${BASH_REMATCH[1]}"
                local num_value=$((10#$num))
                if [[ $num_value -gt $max_num ]]; then
                    max_num=$num_value
                fi
            fi
        done < "$file"
    fi
    
    printf "%03d" $((max_num + 1))
}

# 主要功能
case "${1:-help}" in
    help)
        echo "快速学习记录工具"
        echo ""
        echo "用法:"
        echo "  ./quick_log.sh learn \"一句话总结\" \"详细描述\""
        echo "  ./quick_log.sh error \"错误描述\" \"错误信息\" \"上下文\""
        echo "  ./quick_log.sh feature \"功能描述\" \"用户背景\""
        echo "  ./quick_log.sh stats    显示统计信息"
        echo "  ./quick_log.sh latest   显示最近记录"
        echo ""
        echo "示例:"
        echo "  ./quick_log.sh learn \"解决跨平台路径问题\" \"在macOS上，/root目录只读，必须使用家目录路径。\""
        ;;
    
    learn)
        if [[ $# -lt 3 ]]; then
            echo "错误: 需要提供总结和详细描述"
            exit 1
        fi
        
        FILE="$LEARNINGS_DIR/LEARNINGS.md"
        PREFIX="LRN"
        ID=$(get_next_id "$FILE" "$PREFIX")
        
        echo "" >> "$FILE"
        echo "## [$PREFIX-$DATE-$ID] best_practice" >> "$FILE"
        echo "" >> "$FILE"
        echo "**Logged**: $ISO_DATE" >> "$FILE"
        echo "**Priority**: medium" >> "$FILE"
        echo "**Status**: pending" >> "$FILE"
        echo "**Area**: backend" >> "$FILE"
        echo "" >> "$FILE"
        echo "### Summary" >> "$FILE"
        echo "$2" >> "$FILE"
        echo "" >> "$FILE"
        echo "### Details" >> "$FILE"
        echo "$3" >> "$FILE"
        echo "" >> "$FILE"
        echo "### Metadata" >> "$FILE"
        echo "- Source: ai_quick_log" >> "$FILE"
        echo "- Tags: quick_record" >> "$FILE"
        echo "" >> "$FILE"
        echo "---" >> "$FILE"
        
        echo "✅ 学习记录已添加: $PREFIX-$DATE-$ID"
        ;;
    
    error)
        if [[ $# -lt 4 ]]; then
            echo "错误: 需要提供错误描述、错误信息和上下文"
            exit 1
        fi
        
        FILE="$LEARNINGS_DIR/ERRORS.md"
        PREFIX="ERR"
        ID=$(get_next_id "$FILE" "$PREFIX")
        
        echo "" >> "$FILE"
        echo "## [$PREFIX-$DATE-$ID] command_failure" >> "$FILE"
        echo "" >> "$FILE"
        echo "**Logged**: $ISO_DATE" >> "$FILE"
        echo "**Priority**: medium" >> "$FILE"
        echo "**Status**: pending" >> "$FILE"
        echo "**Area**: backend" >> "$FILE"
        echo "" >> "$FILE"
        echo "### Summary" >> "$FILE"
        echo "$2" >> "$FILE"
        echo "" >> "$FILE"
        echo "### Error" >> "$FILE"
        echo '```' >> "$FILE"
        echo "$3" >> "$FILE"
        echo '```' >> "$FILE"
        echo "" >> "$FILE"
        echo "### Context" >> "$FILE"
        echo "$4" >> "$FILE"
        echo "" >> "$FILE"
        echo "### Metadata" >> "$FILE"
        echo "- Reproducible: yes" >> "$FILE"
        echo "- Tags: error" >> "$FILE"
        echo "" >> "$FILE"
        echo "---" >> "$FILE"
        
        echo "✅ 错误记录已添加: $PREFIX-$DATE-$ID"
        ;;
    
    feature)
        if [[ $# -lt 3 ]]; then
            echo "错误: 需要提供功能描述和用户背景"
            exit 1
        fi
        
        FILE="$LEARNINGS_DIR/FEATURE_REQUESTS.md"
        PREFIX="FEAT"
        ID=$(get_next_id "$FILE" "$PREFIX")
        
        echo "" >> "$FILE"
        echo "## [$PREFIX-$DATE-$ID] $(echo "$2" | tr ' ' '_')" >> "$FILE"
        echo "" >> "$FILE"
        echo "**Logged**: $ISO_DATE" >> "$FILE"
        echo "**Priority**: medium" >> "$FILE"
        echo "**Status**: pending" >> "$FILE"
        echo "**Area**: backend" >> "$FILE"
        echo "" >> "$FILE"
        echo "### Requested Capability" >> "$FILE"
        echo "$2" >> "$FILE"
        echo "" >> "$FILE"
        echo "### User Context" >> "$FILE"
        echo "$3" >> "$FILE"
        echo "" >> "$FILE"
        echo "### Complexity Estimate" >> "$FILE"
        echo "medium" >> "$FILE"
        echo "" >> "$FILE"
        echo "### Metadata" >> "$FILE"
        echo "- Frequency: first_time" >> "$FILE"
        echo "" >> "$FILE"
        echo "---" >> "$FILE"
        
        echo "✅ 功能请求已添加: $PREFIX-$DATE-$ID"
        ;;
    
    stats)
        echo "📊 学习记录统计:"
        echo "───────────────────────"
        
        for file in "LEARNINGS.md" "ERRORS.md" "FEATURE_REQUESTS.md"; do
            if [[ -f "$LEARNINGS_DIR/$file" ]]; then
                case $file in
                    "LEARNINGS.md")
                        prefix="LRN"
                        emoji="🟢"
                        name="学习记录"
                        ;;
                    "ERRORS.md")
                        prefix="ERR"
                        emoji="🔴"
                        name="错误记录"
                        ;;
                    "FEATURE_REQUESTS.md")
                        prefix="FEAT"
                        emoji="🔵"
                        name="功能请求"
                        ;;
                esac
                
                total=$(grep -c "^## \[$prefix-" "$LEARNINGS_DIR/$file")
                pending=$(grep -c "^\*\*Status\*\*: pending" "$LEARNINGS_DIR/$file")
                
                echo "$emoji $name: $total total, $pending pending"
            fi
        done
        
        echo ""
        echo "💡 最近更新:"
        for file in "LEARNINGS.md" "ERRORS.md" "FEATURE_REQUESTS.md"; do
            if [[ -f "$LEARNINGS_DIR/$file" ]]; then
                latest=$(grep "^## \[" "$LEARNINGS_DIR/$file" | tail -1)
                if [[ -n "$latest" ]]; then
                    echo "  📄 $file: ${latest:3}"
                fi
            fi
        done
        ;;
    
    latest)
        echo "📚 最近记录:"
        echo "───────────────────────"
        
        for file in "LEARNINGS.md" "ERRORS.md" "FEATURE_REQUESTS.md"; do
            if [[ -f "$LEARNINGS_DIR/$file" ]]; then
                echo ""
                echo "📄 $file:"
                grep "^## \[" "$LEARNINGS_DIR/$file" | tail -3 | sed 's/^## /  - /'
            fi
        done
        ;;
    
    *)
        echo "未知命令: $1"
        echo "使用: ./quick_log.sh help 查看帮助"
        exit 1
        ;;
esac