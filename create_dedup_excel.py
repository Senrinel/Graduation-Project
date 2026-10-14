import xlsxwriter

excel_path = "時序去重演算法優化實驗分析.xlsx"
wb = xlsxwriter.Workbook(excel_path)

# Formats
title_fmt = wb.add_format({
    'bold': True, 'font_size': 16, 'font_name': 'Microsoft JhengHei',
    'align': 'left', 'valign': 'vcenter', 'font_color': '#1F497D'
})
subtitle_fmt = wb.add_format({
    'font_size': 10, 'font_name': 'Microsoft JhengHei', 'font_color': '#595959', 'italic': True
})
section_fmt = wb.add_format({
    'bold': True, 'font_size': 12, 'font_name': 'Microsoft JhengHei',
    'bg_color': '#DCE6F1', 'font_color': '#1F497D', 'bottom': 2, 'bottom_color': '#1F497D'
})
hdr_fmt = wb.add_format({
    'bold': True, 'font_name': 'Microsoft JhengHei', 'font_size': 11,
    'bg_color': '#1F497D', 'font_color': '#FFFFFF',
    'align': 'center', 'valign': 'vcenter', 'border': 1, 'text_wrap': True
})
cell_left = wb.add_format({
    'font_name': 'Microsoft JhengHei', 'font_size': 10, 'align': 'left', 'valign': 'vcenter', 'border': 1
})
cell_center = wb.add_format({
    'font_name': 'Microsoft JhengHei', 'font_size': 10, 'align': 'center', 'valign': 'vcenter', 'border': 1
})
cell_num = wb.add_format({
    'font_name': 'Segoe UI', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'border': 1, 'num_format': '#,##0'
})
cell_float = wb.add_format({
    'font_name': 'Segoe UI', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'border': 1, 'num_format': '0.00'
})
cell_pct = wb.add_format({
    'font_name': 'Segoe UI', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'border': 1, 'num_format': '0.0%'
})
highlight_cell = wb.add_format({
    'font_name': 'Segoe UI', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'border': 1,
    'bg_color': '#EBF1DE', 'bold': True, 'font_color': '#375623'
})
alert_cell = wb.add_format({
    'font_name': 'Segoe UI', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'border': 1,
    'bg_color': '#FDE9D9', 'bold': True, 'font_color': '#C65911'
})

# ==========================================
# SHEET 1: 演算法機制對比與評估指標
# ==========================================
ws1 = wb.add_worksheet('演算法機制與指標比對')
ws1.views = [{'show_grid_lines': True}]
ws1.set_column('A:A', 22)
ws1.set_column('B:B', 32)
ws1.set_column('C:C', 34)
ws1.set_column('D:D', 32)

ws1.write('A1', '時序字幕去重機制演算法升級評估報告 (Deduplication Mechanism Evaluation)', title_fmt)
ws1.write('A2', '專案：基於 OCR 之韓文學習字幕擷取系統 | 測試資料集：001.mkv (3,326 OCR raw) & Final Test 01 (2,569 OCR raw)', subtitle_fmt)

ws1.write('A4', '一、架構核心機制原理比對 (Architecture & Mechanism Comparison)', section_fmt)
ws1.merge_range('B4:D4', '', section_fmt)

headers_mech = ['維度 / 特性', '原始機制：單一進行中影格文字追蹤 (逐影比對)', '升級機制：基於時間窗之多狀態生命週期管理 (Time-Window Lifecycle)', '學術意義與工程效益']
for col_idx, h in enumerate(headers_mech):
    ws1.write(4, col_idx, h, hdr_fmt)

mech_data = [
    ('狀態維護模型', '單一狀態暫存器 (Current_Text Register)\n僅紀錄最後一筆辨識文字', '分散式狀態字典表 (Hash-Table State Machine)\n以 text 為鍵維護獨立 Lifecycle', '支援多物體/多文字平行存在於同畫面之客觀事實'),
    ('畫面多文字容忍度', '0% (多文字共存時相互覆蓋中斷，嚴重震盪)', '100% (文字互不干擾，並行追蹤各自時間戳記)', '完全根除「文字插隊 (Text Interleaving)」造成的假性切斷'),
    ('時序區間建立能力', '極弱 (99.2% 被切碎為 0 秒瞬時影格)', '極強 (83.6% 成功跨影格聚合為完整句子時間軸)', '提供下游學習卡精準的時間軸與截圖映射點 (Start/End)'),
    ('時間窗門檻策略', '相鄰影格緊鄰判定 (易受檢測抖動丟幀影響)', 'max_gap_sec = 1.5s (彈性滑動時間窗容錯)', '可吸收 OCR 模型在連續幀中 1~2 幀的暫態漏檢 (False Negative)'),
    ('時間複雜度', 'O(N) 單次線性掃描', 'O(N) 單次線性掃描 + O(M log M) 終結排序', '維持嚴格即時流式運算能力，計算負擔無實質增加'),
    ('空間複雜度', 'O(1) 常數空間', 'O(K) 活躍文字視窗大小 (K << N)', '極低記憶體開銷 (活躍文字集合通常 < 20)')
]

for row_idx, r in enumerate(mech_data, start=5):
    ws1.write(row_idx, 0, r[0], cell_center)
    ws1.write(row_idx, 1, r[1], cell_left)
    ws1.write(row_idx, 2, r[2], cell_left)
    ws1.write(row_idx, 3, r[3], cell_left)

ws1.write('A13', '二、量化指標測試基準 (Quantitative Benchmark - 01_result)', section_fmt)
ws1.merge_range('B13:D13', '', section_fmt)

headers_bm = ['實驗指標 (Evaluation Metric)', '原始演算法 (單一當前字追蹤)', '優化後演算法 (時間窗生命週期)', '優化效益與量化統計']
for col_idx, h in enumerate(headers_bm):
    ws1.write(13, col_idx, h, hdr_fmt)

bm_data = [
    ('原始 OCR 辨識結果總數 (N)', 2569, 2569, '全流程輸入基準'),
    ('去重後輸出群組數 (Final Groups)', 2443, 225, '資料量大幅壓縮 90.8% (收斂為真實字卡)'),
    ('去重壓縮率 (Compression Rate)', 0.0490, 0.9124, '壓縮率由 4.9% 提升至 91.2% (+86.3%)'),
    ('無效 0 秒單影格佔比 (Zero-Duration %)', 0.9918, 0.1644, '碎片化由 99.2% 劇降至 16.4% (-82.7%)'),
    ('跨影格聚合成功率 (Multi-frame %)', 0.0078, 0.8356, '多影格連續聚合由 0.8% 暴增至 83.6% (+82.8%)'),
    ('平均字幕停留時長 (Avg Duration)', 0.05, 10.42, '由瞬態 0.05s 恢復為真實人類可閱讀之 10.42s')
]

for row_idx, r in enumerate(bm_data, start=14):
    ws1.write(row_idx, 0, r[0], cell_center)
    if isinstance(r[1], float):
        if '%' in r[0] or '率' in r[0]:
            ws1.write(row_idx, 1, r[1], cell_pct)
            ws1.write(row_idx, 2, r[2], cell_pct)
        else:
            ws1.write(row_idx, 1, r[1], cell_float)
            ws1.write(row_idx, 2, r[2], cell_float)
    else:
        ws1.write(row_idx, 1, r[1], cell_num)
        ws1.write(row_idx, 2, r[2], cell_num)
    ws1.write(row_idx, 3, r[3], cell_left)

ws1.write('A21', '註：資料來源取自專案真實測試資料集 finaltest/01_result/ocr_on/ocr_results.csv 執行比對之客觀數據。', subtitle_fmt)

# ==========================================
# SHEET 2: 語料碎片化消歧實驗
# ==========================================
ws2 = wb.add_worksheet('語料碎片化消歧實驗')
ws2.views = [{'show_grid_lines': True}]
ws2.set_column('A:A', 36)
ws2.set_column('B:E', 18)
ws2.set_column('F:F', 24)

ws2.write('A1', '典型共存文字生命週期消歧與去碎片化比對 (Real Corpus De-fragmentation)', title_fmt)
ws2.write('A2', '展示畫面同時多詞出現時，演算法重構前後所產生之群組切割數與時序重構效益', subtitle_fmt)

headers_corpus = ['測試語彙 (韓文原文)', 'OCR 原生偵測次數', '原始演算法產出筆數', '優化演算法產出筆數', '重構之時序長度 (秒)', '學術分析說明']
for col_idx, h in enumerate(headers_corpus):
    ws2.write(3, col_idx, h, hdr_fmt)

corpus_data = [
    ('1. 김밥입니다 (這是紫菜飯捲)', 54, 54, 1, 53.0, '共存文字插隊，原機制每影格斷開一次；現完美聚合成1筆53秒'),
    ('1,500원 (1,500韓元)', 54, 54, 1, 53.0, '與菜單共存之標價，原機制切為54筆碎片；現還原為1筆53秒'),
    ('불고기 김밥 (牛肉紫菜飯捲)', 54, 54, 1, 53.0, '品名長駐畫面，原機制造成54筆假性重複；現成功整併'),
    ('2023년 11월 30일까지 (有效期限)', 54, 54, 1, 53.0, '固定公告字樣，原機制產生54筆0秒字卡；現整併為單一長時卡片'),
    ('4. 저녁 제주도에 가서 살려고 합니다', 52, 52, 2, 50.0, '例句長句，中途換頁間隔>1.5s，準確切分為前後兩次呈現'),
    ('학원 (補習班 - 001.mkv 基準例證)', 43, 43, 1, 13.0, 'PROJECT_NOTES §18 記載之經典案例：4字輪替下43筆切碎重構為1筆'),
    ('대학교 (大學 - 001.mkv 基準例證)', 43, 43, 1, 13.0, '與補習班並存，重構前各自切碎43筆；重構後正確整合成1筆'),
    ('학교 (學校 - 001.mkv 基準例證)', 43, 43, 1, 13.0, '與補習班並存，重構前各自切碎43筆；重構後正確整合成1筆'),
    ('학생 (學生 - 001.mkv 基準例證)', 43, 43, 1, 13.0, '與補習班並存，重構前各自切碎43筆；重構後正確整合成1筆')
]

for row_idx, r in enumerate(corpus_data, start=4):
    ws2.write(row_idx, 0, r[0], cell_left)
    ws2.write(row_idx, 1, r[1], cell_num)
    ws2.write(row_idx, 2, r[2], alert_cell)
    ws2.write(row_idx, 3, r[3], highlight_cell)
    ws2.write(row_idx, 4, r[4], cell_float)
    ws2.write(row_idx, 5, r[5], cell_left)

ws2.write('A15', '※ 結論證明：舊版逐影比對在多文字畫面下產生 100% 碎片化；新版時間窗生命週期管理達成 97.7% 以上之降噪整併。', subtitle_fmt)

# ==========================================
# SHEET 3: 效能視覺化圖表
# ==========================================
ws3 = wb.add_worksheet('效能視覺化圖表')
ws3.views = [{'show_grid_lines': True}]
ws3.set_column('A:A', 30)
ws3.set_column('B:C', 18)

ws3.write('A1', '去重機制效能與品質視覺化統計 (Deduplication Quality & Efficiency)', title_fmt)
ws3.write('A2', '圖表供學術論文、專題成果展示與答辯投影片引用', subtitle_fmt)

ws3.write('A4', '圖表一數據來源：資料集處理前後規模 (群組數)', section_fmt)
ws3.write('B4', '', section_fmt)
ws3.write('C4', '', section_fmt)

ws3.write(4, 0, '測試情境', hdr_fmt)
ws3.write(4, 1, '原始演算法輸出筆數', hdr_fmt)
ws3.write(4, 2, '優化演算法輸出筆數', hdr_fmt)

chart_data_1 = [
    ('01.mkv 總資料集 (2,569 OCR)', 2443, 225),
    ('001.mkv 基準測試 (3,326 OCR)', 3180, 145),
    ('Top 5 高頻字彙平均 (每字 54 幀)', 54, 1.2)
]

for r_idx, (cat, v1, v2) in enumerate(chart_data_1, start=5):
    ws3.write(r_idx, 0, cat, cell_left)
    ws3.write(r_idx, 1, v1, cell_num)
    ws3.write(r_idx, 2, v2, cell_num)

ws3.write('A10', '圖表二數據來源：字幕時序品質比例比對', section_fmt)
ws3.write('B10', '', section_fmt)
ws3.write('C10', '', section_fmt)

ws3.write(10, 0, '品質維度指標', hdr_fmt)
ws3.write(10, 1, '原始演算法', hdr_fmt)
ws3.write(10, 2, '優化演算法', hdr_fmt)

chart_data_2 = [
    ('無效 0 秒碎片佔比 (Zero-Duration %)', 0.9918, 0.1644),
    ('跨影格有效聚合率 (Multi-frame %)', 0.0078, 0.8356),
    ('冗餘重複字卡壓縮率 (Compression %)', 0.0490, 0.9124)
]

for r_idx, (cat, v1, v2) in enumerate(chart_data_2, start=11):
    ws3.write(r_idx, 0, cat, cell_left)
    ws3.write(r_idx, 1, v1, cell_pct)
    ws3.write(r_idx, 2, v2, cell_pct)

# CREATE CHARTS
chart1 = wb.add_chart({'type': 'column'})
chart1.add_series({
    'name': ['效能視覺化圖表', 4, 1],
    'categories': ['效能視覺化圖表', 5, 0, 7, 0],
    'values': ['效能視覺化圖表', 5, 1, 7, 1],
    'fill': {'color': '#C00000'}
})
chart1.add_series({
    'name': ['效能視覺化圖表', 4, 2],
    'categories': ['效能視覺化圖表', 5, 0, 7, 0],
    'values': ['效能視覺化圖表', 5, 2, 7, 2],
    'fill': {'color': '#375623'}
})
chart1.set_title({'name': '演算法重構前後輸出筆數對比 (字卡膨脹 vs 有效聚合)', 'name_font': {'name': 'Microsoft JhengHei', 'size': 12, 'bold': True}})
chart1.set_x_axis({'name': '測試情境', 'name_font': {'name': 'Microsoft JhengHei', 'size': 10}})
chart1.set_y_axis({'name': '輸出筆數 (筆)', 'name_font': {'name': 'Microsoft JhengHei', 'size': 10}, 'major_gridlines': {'visible': True}})
chart1.set_size({'width': 560, 'height': 320})
chart1.set_legend({'position': 'top'})
ws3.insert_chart('E4', chart1)

chart2 = wb.add_chart({'type': 'column'})
chart2.add_series({
    'name': ['效能視覺化圖表', 10, 1],
    'categories': ['效能視覺化圖表', 11, 0, 13, 0],
    'values': ['效能視覺化圖表', 11, 1, 13, 1],
    'fill': {'color': '#ED7D31'}
})
chart2.add_series({
    'name': ['效能視覺化圖表', 10, 2],
    'categories': ['效能視覺化圖表', 11, 0, 13, 0],
    'values': ['效能視覺化圖表', 11, 2, 13, 2],
    'fill': {'color': '#4472C4'}
})
chart2.set_title({'name': '字幕時序核心品質指標躍升比對 (%)', 'name_font': {'name': 'Microsoft JhengHei', 'size': 12, 'bold': True}})
chart2.set_x_axis({'name': '品質維度', 'name_font': {'name': 'Microsoft JhengHei', 'size': 10}})
chart2.set_y_axis({'name': '百分比 (%)', 'name_font': {'name': 'Microsoft JhengHei', 'size': 10}, 'max': 1.0, 'major_gridlines': {'visible': True}})
chart2.set_size({'width': 560, 'height': 320})
chart2.set_legend({'position': 'top'})
ws3.insert_chart('E20', chart2)

wb.close()
print("Excel generated successfully:", excel_path)
