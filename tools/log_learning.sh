#!/bin/bash
# 交互式学习记录工具
# 简化 self-improving-agent 技能的使用

set -e

echo "🧠 Self-Improvement Learning Logger"
echo "📝 记录学习点到 .learnings/"
echo ""

# 检查是否在正确目录
if [[ ! -f "README.md" ]]; then
    echo "⚠ 警告: 请在项目根目录运行此脚本"
    READ_PROJECT_ROOT=$(dirname "$0")/..
    echo "  尝试切换到: $READ_PROJECT_ROOT"
    cd "$READ_PROJECT_ROOT"
fi

# 获取日期
DATE=$(date +%Y%m%d)
ISO_DATE=$(date -Iseconds)

# 自动生成ID
get_next_id() {
    local file=$1
    local prefix=$2
    
    # 查找现有的最高编号
    local max_num=0
    if [[ -f "$file" ]]; then
        while IFS= read -r line; do
            if [[ $line =~ ^#\#\ \[${prefix}-${DATE}-([0-9A-Z]{3})\] ]]; then
                # 尝试解析数字
                local num_id="${BASH_REMATCH[1]}"
                if [[ $num_id =~ ^[0-9]{3}$ ]]; then
                    local num_value=$((10#$num_id))
                    if [[ $num_value -gt $max_num ]]; then
                        max_num=$num_value
                    fi
                fi
            fi
        done < "$file"
    fi
    
    # 生成下一个ID
    local next_num=$((max_num + 1))
    printf "%03d" $next_num
}

# 选择记录类型
echo "📊 选择记录类型:"
echo "1) 🟢 Learning - 新知识/最佳实践 (LEARNINGS.md)"
echo "2) 🔴 Error   - 错误/异常 (ERRORS.md)"
echo "3) 🔵 Feature - 功能需求 (FEATURE_REQUESTS.md)"
echo "4) 📋 Review  - 查看最近的学习记录"
echo ""

read -p "选择 (1-4): " choice

case $choice in
    1)
        TARGET_FILE=".learnings/LEARNINGS.md"
        PREFIX="LRN"
        
        echo ""
        echo "📚 选择类别:"
        echo "1) correction - 纠正错误"
        echo "2) knowledge_gap - 知识缺口"
        echo "3) best_practice - 最佳实践"
        echo "4) insight - 重要见解"
        echo ""
        read -p "类别 (1-4，默认3): " cat_choice
        
        case $cat_choice in
            1) CATEGORY="correction";;
            2) CATEGORY="knowledge_gap";;
            3) CATEGORY="best_practice";;
            4) CATEGORY="insight";;
            *) CATEGORY="best_practice";;
        esac
        
        echo ""
        read -p "🏷️ 优先级 (low/medium/high/critical，默认medium): " priority
        priority=${priority:-medium}
        
        echo ""
        echo "📂 选择领域:"
        echo "1) frontend - 前端"
        echo "2) backend - 后端"
        echo "3) infra - 基础设施"
        echo "4) tests - 测试"
        echo "5) docs - 文档"
        echo "6) config - 配置"
        echo ""
        read -p "领域 (1-6，默认backend): " area_choice
        
        case $area_choice in
            1) AREA="frontend";;
            2) AREA="backend";;
            3) AREA="infra";;
            4) AREA="tests";;
            5) AREA="docs";;
            6) AREA="config";;
            *) AREA="backend";;
        esac
        
        echo ""
        read -p "📌 相关文件路径 (用空格分隔): " related_files
        
        echo ""
        echo "📝 一句话总结:"
        read -p "> " summary
        
        echo ""
        echo "📖 详细描述 (CTRL+D结束输入):"
        details=$(cat)
        
        # 生成ID
        ID=$(get_next_id "$TARGET_FILE" "$PREFIX")
        
        # 写入文件
        echo "" >> "$TARGET_FILE"
        echo "## [$PREFIX-$DATE-$ID] $CATEGORY" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "**Logged**: $ISO_DATE" >> "$TARGET_FILE"
        echo "**Priority**: $priority" >> "$TARGET_FILE"
        echo "**Status**: pending" >> "$TARGET_FILE"
        echo "**Area**: $AREA" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "### Summary" >> "$TARGET_FILE"
        echo "$summary" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "### Details" >> "$TARGET_FILE"
        echo "$details" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        
        if [[ -n "$related_files" ]]; then
            echo "### Metadata" >> "$TARGET_FILE"
            echo "- Source: manual_log" >> "$TARGET_FILE"
            echo "- Related Files: $related_files" >> "$TARGET_FILE"
            echo "- Tags: skill, learning" >> "$TARGET_FILE"
        fi
        
        echo "" >> "$TARGET_FILE"
        echo "---" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        
        echo "✅ 已添加到 $TARGET_FILE"
        echo "📄 ID: $PREFIX-$DATE-$ID"
        ;;
    
    2)
        TARGET_FILE=".learnings/ERRORS.md"
        PREFIX="ERR"
        
        echo ""
        read -p "🔧 相关工具/命令名称: " tool_name
        
        echo ""
        read -p "🏷️ 优先级 (low/medium/high/critical，默认medium): " priority
        priority=${priority:-medium}
        
        echo ""
        read -p "📂 选择领域 (frontend/backend/infra/tests/docs/config，默认backend): " area
        area=${area:-backend}
        
        echo ""
        read -p "📌 相关文件路径: " related_files
        
        echo ""
        echo "📝 错误简要描述:"
        read -p "> " summary
        
        echo ""
        echo "🚨 错误信息 (CTRL+D结束输入):"
        error_msg=$(cat)
        
        echo ""
        echo "🔍 上下文/复现步骤 (CTRL+D结束输入):"
        context=$(cat)
        
        echo ""
        read -p "🔧 修复建议: " fix_suggestion
        
        # 生成ID
        ID=$(get_next_id "$TARGET_FILE" "$PREFIX")
        
        # 写入文件
        echo "" >> "$TARGET_FILE"
        echo "## [$PREFIX-$DATE-$ID] $tool_name" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "**Logged**: $ISO_DATE" >> "$TARGET_FILE"
        echo "**Priority**: $priority" >> "$TARGET_FILE"
        echo "**Status**: pending" >> "$TARGET_FILE"
        echo "**Area**: $AREA" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "### Summary" >> "$TARGET_FILE"
        echo "$summary" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "### Error" >> "$TARGET_FILE"
        echo '```' >> "$TARGET_FILE"
        echo "$error_msg" >> "$TARGET_FILE"
        echo '```' >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "### Context" >> "$TARGET_FILE"
        echo "$context" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "### Suggested Fix" >> "$TARGET_FILE"
        echo "$fix_suggestion" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "### Metadata" >> "$TARGET_FILE"
        echo "- Reproducible: yes" >> "$TARGET_FILE"
        echo "- Related Files: $related_files" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "---" >> "$TARGET_FILE"
        
        echo "✅ 已添加到 $TARGET_FILE"
        echo "📄 ID: $PREFIX-$DATE-$ID"
        ;;
    
    3)
        TARGET_FILE=".learnings/FEATURE_REQUESTS.md"
        PREFIX="FEAT"
        
        echo ""
        read -p "🌟 功能名称/描述: " feat_name
        
        echo ""
        read -p "🏷️ 优先级 (low/medium/high/critical，默认medium): " priority
        priority=${priority:-medium}
        
        echo ""
        read -p "📂 选择领域 (frontend/backend/infra/tests/docs/config，默认backend): " area
        area=${area:-backend}
        
        echo ""
        read -p "📊 复杂度 (simple/medium/complex，默认medium): " complexity
        complexity=${complexity:-medium}
        
        echo ""
        echo "💡 用户需求背景 (CTRL+D结束输入):"
        context=$(cat)
        
        echo ""
        echo "🛠️ 实现建议 (CTRL+D结束输入):"
        implementation=$(cat)
        
        # 生成ID
        ID=$(get_next_id "$TARGET_FILE" "$PREFIX")
        
        # 写入文件
        echo "" >> "$TARGET_FILE"
        echo "## [$PREFIX-$DATE-$ID] $feat_name" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "**Logged**: $ISO_DATE" >> "$TARGET_FILE"
        echo "**Priority**: $priority" >> "$TARGET_FILE"
        echo "**Status**: pending" >> "$TARGET_FILE"
        echo "**Area**: $AREA" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "### Requested Capability" >> "$TARGET_FILE"
        echo "$feat_name" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "### User Context" >> "$TARGET_FILE"
        echo "$context" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "### Complexity Estimate" >> "$TARGET_FILE"
        echo "$complexity" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "### Suggested Implementation" >> "$TARGET_FILE"
        echo "$implementation" >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "### Metadata" >> "$TARGET_FILE"
        echo "- Frequency: first_time" >> "$TARGET_FILE"
        echo "- Related Features: " >> "$TARGET_FILE"
        echo "" >> "$TARGET_FILE"
        echo "---" >> "$TARGET_FILE"
        
        echo "✅ 已添加到 $TARGET_FILE"
        echo "📄 ID: $PREFIX-$DATE-$ID"
        ;;
    
    4)
        echo ""
        echo "📚 最近学习记录:"
        echo "─────────────────────────────"
        
        if [[ -f ".learnings/LEARNINGS.md" ]]; then
            echo ""
            echo "🟢 LEARNINGS.md (最近3条):"
            grep -n "^## \[LRN-" ".learnings/LEARNINGS.md" | tail -3 | sed 's/:/: /'
        fi
        
        if [[ -f ".learnings/ERRORS.md" ]]; then
            echo ""
            echo "🔴 ERRORS.md (最近3条):"
            grep -n "^## \[ERR-" ".learnings/ERRORS.md" | tail -3 | sed 's/:/: /'
        fi
        
        if [[ -f ".learnings/FEATURE_REQUESTS.md" ]]; then
            echo ""
            echo "🔵 FEATURE_REQUESTS.md (最近3条):"
            grep -n "^## \[FEAT-" ".learnings/FEATURE_REQUESTS.md" | tail -3 | sed 's/:/: /'
        fi
        
        echo ""
        echo "📊 统计:"
        echo "─────────────────────────────"
        
        if [[ -f ".learnings/LEARNINGS.md" ]]; then
            total_learnings=$(grep -c "^## \[LRN-" ".learnings/LEARNINGS.md")
            pending_learnings=$(grep -c "^\*\*Status\*\*: pending" ".learnings/LEARNINGS.md")
            resolved_learnings=$(grep -c "^\*\*Status\*\*: resolved" ".learnings/LEARNINGS.md")
            echo "🟢 Learnings: $total_learnings total, $pending_learnings pending, $resolved_learnings resolved"
        fi
        
        if [[ -f ".learnings/ERRORS.md" ]]; then
            total_errors=$(grep -c "^## \[ERR-" ".learnings/ERRORS.md")
            pending_errors=$(grep -c "^\*\*Status\*\*: pending" ".learnings/ERRORS.md")
            resolved_errors=$(grep -c "^\*\*Status\*\*: resolved" ".learnings/ERRORS.md")
            echo "🔴 Errors: $total_errors total, $pending_errors pending, $resolved_errors resolved"
        fi
        
        if [[ -f ".learnings/FEATURE_REQUESTS.md" ]]; then
            total_features=$(grep -c "^## \[FEAT-" ".learnings/FEATURE_REQUESTS.md")
            pending_features=$(grep -c "^\*\*Status\*\*: pending" ".learnings/FEATURE_REQUESTS.md")
            echo "🔵 Features: $total_features total, $pending_features pending"
        fi
        
        echo ""
        echo "💡 提示: 使用 cat .learnings/文件名 | grep -A 10 'ID' 查看完整记录"
        ;;
    
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac

echo ""
echo "✨ 操作完成!"
echo "📁 文件位置: stock-signal/.learnings/"
echo "ℹ️  后续: 定期回顾记录，更新状态为 resolved 或 promoted"