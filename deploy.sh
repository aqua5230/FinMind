#!/bin/bash
# deploy.sh — FinMind 安全部署腳本
# 用法：./deploy.sh

set -e

# 1. 確認在專案根目錄
if [ ! -f "SESSION.md" ]; then
  echo "❌ 必須從專案根目錄執行：/Users/lollapalooza/Desktop/FinMind/"
  exit 1
fi

# 2. 拒絕未 commit 的改動
if ! git diff --quiet HEAD; then
  echo "❌ 有未 commit 的改動，deploy 前必須先 commit："
  git diff --stat HEAD
  echo ""
  echo "請先：git add <files> && git commit -m '...'"
  exit 1
fi

# 3. 確認 untracked files（只警告不阻擋，但提示）
UNTRACKED=$(git ls-files --others --exclude-standard | grep "^frontend/" | head -5)
if [ -n "$UNTRACKED" ]; then
  echo "⚠️  以下 frontend/ untracked 檔案不會被部署（需要的話請先 git add）："
  echo "$UNTRACKED"
  echo ""
  read -p "確認繼續？(y/N) " confirm
  if [ "$confirm" != "y" ]; then
    exit 1
  fi
fi

echo "✅ 準備部署..."

# 4. 確保連到前端 service 再上傳
railway service frontend
railway up

echo ""
echo "⏳ 等待新版本生效（最多 90 秒）..."
sleep 90

# 5. 驗證 bundle 是否真的更新
echo ""
echo "🔍 驗證線上 bundle..."
PAGE_CHUNK=$(curl -s https://frontend-production-8b27.up.railway.app/ | grep -o '_next/static/chunks/app/page-[^"]*' | head -1)
if [ -z "$PAGE_CHUNK" ]; then
  echo "❌ 無法取得 page chunk URL，請手動確認"
  exit 1
fi

echo "page chunk: $PAGE_CHUNK"

echo ""
echo "✅ 部署完成。"
echo "🌐 https://frontend-production-8b27.up.railway.app"
