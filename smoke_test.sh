#!/bin/bash
# smoke_test.sh — FinMind 線上煙霧測試
# Railway redeploy 後跑這個確認前後端真的活著。
#
# 用法：
#   ./smoke_test.sh                              預設打線上 Railway
#   API_KEY=xxx ./smoke_test.sh                  附 API key 連保護 endpoint 一起測
#   API_BASE=http://localhost:8000 ./smoke_test.sh   打本機後端
#   FRONTEND_BASE=http://localhost:3000 ./smoke_test.sh
#
# 取 API_KEY：railway service FinMind && railway variables（不存本地副本）

set -u

API_BASE="${API_BASE:-https://finmind-production-23fd.up.railway.app}"
FRONTEND_BASE="${FRONTEND_BASE:-https://frontend-production-8b27.up.railway.app}"
API_KEY="${API_KEY:-}"
TIMEOUT=15

# 顏色
if [ -t 1 ]; then
  G="\033[32m"; R="\033[31m"; Y="\033[33m"; B="\033[1m"; N="\033[0m"
else
  G=""; R=""; Y=""; B=""; N=""
fi

PASS=0
FAIL=0
SKIP=0
FAILED_NAMES=()

# check NAME METHOD URL EXPECT_STATUS [HEADER...]
#   EXPECT_STATUS 可以是單一（200）或多個用逗號（200,204）
check() {
  local name="$1"; shift
  local method="$1"; shift
  local url="$1"; shift
  local expect="$1"; shift
  local headers=("$@")

  local curl_args=(-s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" -X "$method")
  if [ ${#headers[@]} -gt 0 ]; then
    for h in "${headers[@]}"; do
      curl_args+=(-H "$h")
    done
  fi

  local code
  code=$(curl "${curl_args[@]}" "$url" 2>/dev/null) || code="000"

  if [[ ",$expect," == *",$code,"* ]]; then
    printf "  ${G}PASS${N}  %-50s ${B}%s${N}\n" "$name" "$code"
    PASS=$((PASS + 1))
  else
    printf "  ${R}FAIL${N}  %-50s ${B}%s${N}  (expect %s)\n" "$name" "$code" "$expect"
    FAIL=$((FAIL + 1))
    FAILED_NAMES+=("$name")
  fi
}

skip() {
  printf "  ${Y}SKIP${N}  %-50s %s\n" "$1" "$2"
  SKIP=$((SKIP + 1))
}

printf "${B}=== FinMind smoke test ===${N}\n"
echo "後端：$API_BASE"
echo "前端：$FRONTEND_BASE"
echo "API_KEY：$([ -n "$API_KEY" ] && echo "已帶（保護 endpoint 會測）" || echo "未帶（保護 endpoint 會 SKIP）")"
echo ""

printf "${B}[1] 後端公開 endpoint${N}\n"
check "GET /api/health"                GET  "$API_BASE/api/health"               200

printf "\n${B}[2] 安全防線（必須 fail-closed 拒絕無 key）${N}\n"
check "GET /api/stocks 無 key → 401"   GET  "$API_BASE/api/stocks"               401
check "GET /api/revenue-scan 無 key"   GET  "$API_BASE/api/revenue-scan"         401
check "POST /api/report 無 key"        POST "$API_BASE/api/report"               401

printf "\n${B}[3] 後端保護 endpoint（需 API_KEY）${N}\n"
if [ -n "$API_KEY" ]; then
  check "GET /api/db-status"           GET  "$API_BASE/api/db-status"            200 "X-API-Key: $API_KEY"
  check "GET /api/stocks 有 key"       GET  "$API_BASE/api/stocks"               200 "X-API-Key: $API_KEY"
  check "GET /api/signals/stats"       GET  "$API_BASE/api/signals/stats"        200 "X-API-Key: $API_KEY"
else
  skip "GET /api/db-status"            "set API_KEY=... 才會測"
  skip "GET /api/stocks 有 key"        "set API_KEY=... 才會測"
  skip "GET /api/signals/stats"        "set API_KEY=... 才會測"
fi

printf "\n${B}[4] 前端${N}\n"
check "GET / 首頁"                     GET  "$FRONTEND_BASE/"                    200

# 額外：抓首頁 HTML 確認真的吐 Next.js bundle、不是 Railway 404 頁
HTML=$(curl -s --max-time "$TIMEOUT" "$FRONTEND_BASE/" 2>/dev/null)
if echo "$HTML" | grep -q "_next/static"; then
  printf "  ${G}PASS${N}  %-50s ${B}有 _next/static chunk${N}\n" "前端 bundle 真實存在"
  PASS=$((PASS + 1))
else
  printf "  ${R}FAIL${N}  %-50s ${B}沒抓到 _next/static${N}\n" "前端 bundle 真實存在"
  FAIL=$((FAIL + 1))
  FAILED_NAMES+=("前端 bundle 真實存在")
fi

# 額外：前端 BFF proxy（server-side 代帶 X-API-Key）應該 work
check "前端 BFF /api/health proxy"     GET  "$FRONTEND_BASE/api/health"          200

echo ""
printf "${B}=== summary ===${N}\n"
printf "  ${G}PASS${N}: %d   ${R}FAIL${N}: %d   ${Y}SKIP${N}: %d\n" "$PASS" "$FAIL" "$SKIP"

if [ "$FAIL" -gt 0 ]; then
  echo ""
  printf "${R}失敗項目：${N}\n"
  for name in "${FAILED_NAMES[@]}"; do
    echo "  - $name"
  done
  exit 1
fi

echo ""
printf "${G}✅ 全部通過${N}\n"
exit 0
