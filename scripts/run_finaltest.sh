#!/usr/bin/env bash
# Phase 9 最終測試腳本
# =====================
# 以呼叫後端 API 的方式（等效於網頁介面實際操作，走的是同一組 /api/upload
# /api/jobs/{id}/status 路由，不繞過 API 直接呼叫 Python 函式），對
# finaltest/ 底下的 2 支影片（01.mkv、02.mp4）各跑一次完整流程：
#   - channel 1（4 個子引擎：okt / komoran / kkma / mecab 全部執行）
#   - channel 2
#   - channel 3
#   - denoise on
#
# 完成後把每支影片在 data/output/<job_id>/ 底下的「完整」結果（六個
# channel 的 export.csv、stats/*.csv、ocr_results.csv、frames/manifest.csv
# 等）複製進 finaltest/01_result/、finaltest/02_result/，並把每次輪詢到
# 的 job 狀態存成 finaltest/01_status.json、finaltest/02_status.json。
#
# 使用方式：
#   1. 先在一個終端機視窗啟動後端（若還沒啟動）：
#        uvicorn src.api.main:app --reload
#      （需在 repo root 執行，這樣 data/output 等相對路徑才會落在正確位置）
#   2. 另開一個終端機視窗，一樣切到 repo root，執行：
#        bash scripts/run_finaltest.sh
#
# 注意事項：
#   - 兩支影片刻意「依序」處理（不同時上傳），避免同一張 GPU 被兩個工作
#     同時搶用，也避開 pipeline_runner.py 對 config 覆寫全域狀態在真正
#     並行執行時的已知限制（見 PROJECT_NOTES.md 第 16 節）。這次測試沒有
#     用到 config_overrides（min_confidence/dedup_max_gap_sec/clahe_clip_limit/
#     denoise_strength 皆維持預設），這層限制其實不會被觸發，但依序執行
#     仍是更安全、更容易判讀進度的做法。
#   - 影片較長（01.mkv 約 12 分鐘、02.mp4 約 19 分鐘，皆為 1920x1080
#     H.264），實際跑完時間取決於本機 GPU 速度與 Ollama 回應速度，可能
#     需要數十分鐘到數小時不等，腳本會每 10 秒印一次目前階段。
#   - KoNLPy／JPype 已知限制（PROJECT_NOTES.md 第 16.3 節）：測試跑完、
#     要關閉 uvicorn 時，行程可能不會乾淨結束，多按一次 Ctrl+C 或直接
#     關閉終端機視窗即可，不影響這次測試結果的正確性。
#   - 複製到 finaltest/ 的完整結果會包含 frames/ 底下的原始與前處理後
#     影格截圖（兩支影片 1 FPS 取樣，合計約 1850 張影格 x 2 版本），
#     檔案數量與容量會不小；若不需要保留截圖，測試完成後可自行刪除
#     finaltest/0X_result/frames/、finaltest/0X_result/processed/。

set -euo pipefail

BASE_URL="http://127.0.0.1:8000"
FINALTEST_DIR="finaltest"
POLL_INTERVAL_SEC=10
MAX_WAIT_SEC=14400  # 4 小時輪詢上限；超過只是腳本停止輪詢，伺服器端工作不受影響

CHANNEL1_ENGINES="okt,komoran,kkma,mecab"

json_field() {
  # 從單層 JSON 字串取出指定「頂層純值欄位」（本腳本只用得到 job_id/
  # status/current_stage，皆為簡單字串，不處理巢狀陣列），欄位不存在時
  # 回傳空字串而不中斷腳本（互動輪詢中途發生非預期回應格式時，靠這裡
  # 保持腳本存活、把完整原始回應印出來讓人判讀，而不是讓 set -e 悄悄砍掉
  # 整個腳本）。
  local json="$1" field="$2" result
  result=$(echo "$json" | grep -oP "\"${field}\"\s*:\s*\"?[^,\"}]*" 2>/dev/null | head -1 | sed -E "s/.*\"${field}\"\s*:\s*\"?//") || true
  echo "$result"
}

upload_video() {
  local filepath="$1"
  curl -sS -X POST "${BASE_URL}/api/upload" \
    -F "file=@${filepath}" \
    -F "include_channel1=true" \
    -F "channel1_engines=${CHANNEL1_ENGINES}" \
    -F "include_channel2=true" \
    -F "include_channel3=true" \
    -F "denoise=true"
}

wait_for_job() {
  local job_id="$1" label="$2" waited=0 status_json status stage
  while true; do
    status_json=$(curl -sS "${BASE_URL}/api/jobs/${job_id}/status")
    status=$(json_field "$status_json" "status")
    stage=$(json_field "$status_json" "current_stage")
    echo "[$(date '+%H:%M:%S')] ${label} (job=${job_id}) status=${status} stage=${stage}"
    echo "$status_json" > "${FINALTEST_DIR}/${label}_status.json"

    if [[ "$status" == "done" || "$status" == "failed" ]]; then
      if [[ "$status" == "failed" ]]; then
        echo "!!! ${label} 執行失敗，完整狀態已存到 ${FINALTEST_DIR}/${label}_status.json，請檢查其中 error 欄位與 uvicorn 終端機 log。"
      fi
      break
    fi

    sleep "$POLL_INTERVAL_SEC"
    waited=$((waited + POLL_INTERVAL_SEC))
    if [[ "$waited" -ge "$MAX_WAIT_SEC" ]]; then
      echo "!!! 等待超過 $((MAX_WAIT_SEC / 3600)) 小時，腳本停止輪詢（伺服器端工作本身不受影響，可自行手動查詢 ${BASE_URL}/api/jobs/${job_id}/status）。"
      break
    fi
  done
}

run_one() {
  local filepath="$1" label="$2" resp job_id
  echo "=== 上傳 ${filepath}（${label}）==="
  resp=$(upload_video "$filepath")
  echo "$resp"
  job_id=$(json_field "$resp" "job_id")
  if [[ -z "$job_id" ]]; then
    echo "!!! 上傳失敗，沒有拿到 job_id，完整回應如上，請檢查 uvicorn 終端機 log 後再重跑。"
    exit 1
  fi
  echo "${label} job_id=${job_id}"
  echo "$job_id" > "${FINALTEST_DIR}/${label}_job_id.txt"

  wait_for_job "$job_id" "$label"

  echo "=== 複製 ${label} 完整結果到 ${FINALTEST_DIR}/${label}_result ==="
  rm -rf "${FINALTEST_DIR:?}/${label}_result"
  cp -r "data/output/${job_id}" "${FINALTEST_DIR}/${label}_result"
  echo "${label} 完成，結果在 ${FINALTEST_DIR}/${label}_result"
}

mkdir -p "$FINALTEST_DIR"

if ! curl -sS -o /dev/null "${BASE_URL}/api/jobs/nonexistent/status" 2>/dev/null; then
  echo "!!! 連不到 ${BASE_URL}，請確認 uvicorn src.api.main:app --reload 是否已在另一個終端機視窗啟動。"
  exit 1
fi

run_one "${FINALTEST_DIR}/01.mkv" "01"
run_one "${FINALTEST_DIR}/02.mp4" "02"

echo ""
echo "=== 全部完成 ==="
echo "01.mkv 結果：${FINALTEST_DIR}/01_result/"
echo "02.mp4 結果：${FINALTEST_DIR}/02_result/"
echo "請回報完成，接著會直接讀取 ${FINALTEST_DIR}/ 底下的結果進行分析與 Excel 視覺化。"
