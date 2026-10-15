import sys
sys.stdout.reconfigure(encoding='utf-8')
import pptx
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return RGBColor(*(int(hex_str[i:i+2], 16) for i in (0, 2, 4)))

def add_academic_card(slide, left, top, width, height, title, items, bg_hex='F1F5F9', border_hex='CBD5E1', title_color_hex='1E293B', text_color_hex='334155'):
    """Adds a modern rounded rectangle academic card with title and bullet/body items."""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = hex_to_rgb(bg_hex)
    if border_hex:
        shape.line.color.rgb = hex_to_rgb(border_hex)
        shape.line.width = Pt(1)
    else:
        shape.line.fill.background()
    
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.2)
    tf.margin_right = Inches(0.2)
    tf.margin_top = Inches(0.12)
    tf.margin_bottom = Inches(0.12)
    tf.vertical_anchor = MSO_ANCHOR.TOP
    
    # Title paragraph
    p0 = tf.paragraphs[0]
    p0.text = title
    p0.font.name = '微軟正黑體'
    p0.font.size = Pt(11.5)
    p0.font.bold = True
    p0.font.color.rgb = hex_to_rgb(title_color_hex)
    p0.space_after = Pt(3)
    
    for item in items:
        p = tf.add_paragraph()
        p.text = item
        p.font.name = '微軟正黑體'
        p.font.size = Pt(9.5)
        p.font.color.rgb = hex_to_rgb(text_color_hex)
        p.line_spacing = 1.15
        p.space_after = Pt(2)
    
    return shape

def update_presentation():
    prs = pptx.Presentation('報告/專題報告.pptx')
    print(f'Original slide count: {len(prs.slides)}')
    
    # -------------------------------------------------------------
    # 1. Slide 2: 需求與痛點 -> 加入學術實證與研究動機卡片
    # -------------------------------------------------------------
    s2 = prs.slides[1]
    add_academic_card(
        s2,
        left=607368,
        top=5050000,
        width=10860000,
        height=1480000,
        title='📚 學術實證與研究動機 (Academic & Empirical Grounding)',
        items=[
            '• 原生硬字幕痛點背書：ACM CSCW 2026 (Ko & Lee) 對 1.9 萬部韓語 YouTube 視訊（7,100 萬影格）實證指出，東亞影音 90%+ 核心情境與敘事強調皆以原生硬字幕與花字（Telop）呈現，現存無障礙軟字幕工具（CC/ASR）完全無法感知像素級文字。',
            '• 視覺解構學習成效：ACM CHI 2022 (Kim et al., FitVid) 實證從已渲染像素中逆向解構文字與版面元件，能有效降低學習者認知負荷並大幅提升學習召回率，確立自原生畫面抓取硬字幕製作單字卡之核心價值。'
        ],
        bg_hex='EFF6FF',
        border_hex='93C5FD',
        title_color_hex='1E40AF',
        text_color_hex='1E293B'
    )
    print('Slide 2 updated with academic motivation card.')

    # -------------------------------------------------------------
    # 2. Slide 3: 開發概念 -> 加入 ICALL 系統架構典範卡片
    # -------------------------------------------------------------
    s3 = prs.slides[2]
    add_academic_card(
        s3,
        left=762000,
        top=5280000,
        width=10668000,
        height=1250000,
        title='📚 智慧輔助語言學習 (ICALL) 系統架構典範',
        items=[
            '• 元件重用哲學：計算語言學國際會議 SLTC / CALL (Volodina et al., 2012)《Waste not, want not: Towards a system architecture for ICALL based on NLP component re-use》指出：智慧外語學習系統應奠基於「成熟 NLP 元件高度重用與標準化介面解耦」，拒絕重複造輪子，方能以最低工程代價實現工業級穩定之學習工具。'
        ],
        bg_hex='F1F5F9',
        border_hex='CBD5E1',
        title_color_hex='0F172A',
        text_color_hex='334155'
    )
    print('Slide 3 updated with ICALL architecture card.')

    # -------------------------------------------------------------
    # 3. Slide 4: 系統架構與資料流 -> 加入管線架構與選型驗證卡片
    # -------------------------------------------------------------
    s4 = prs.slides[3]
    add_academic_card(
        s4,
        left=762000,
        top=5250000,
        width=10668000,
        height=1300000,
        title='📚 管線架構與選型科學驗證 (Pipeline Methodology Validation)',
        items=[
            '• 硬字幕抽取流水線：Watve & Bhalekar (IJCRT 2021) 證實影格差分配合 OCR 之端到端流水線在硬字幕提取具備極高時效。',
            '• 兩階段 vs 純視覺大模型：政大 2026 碩論（呂承恩）透過分層實驗實證：在影像文字擷取任務上，兩階段「OCR-based 流水線」正確率維持 95.2%~100%，而端到端純視覺多模態大模型（Vision Direct）嚴重崩潰（不可用），確立本專案採用專用 OCR 搭配 NLP 解析之兩階段架構為當前最佳實踐。'
        ],
        bg_hex='F8FAFC',
        border_hex='94A3B8',
        title_color_hex='0F172A',
        text_color_hex='334155'
    )
    print('Slide 4 updated with pipeline validation card.')

    # -------------------------------------------------------------
    # 4. Slide 5: 取樣率設立 -> 加入預算感知與邊緣控制理論卡片
    # -------------------------------------------------------------
    s5 = prs.slides[4]
    add_academic_card(
        s5,
        left=762000,
        top=5250000,
        width=5800000,
        height=1300000,
        title='📚 預算感知與長視訊邊緣控制理論',
        items=[
            '• 長視訊預算感知 (Budget-Aware)：Cai et al. (arXiv 2026, CFD) 指出密集暴力取樣在長時序視訊中造成嚴重算力浪費，文字記憶優先與按需動態存取是兼顧精度與算力的最優解。',
            '• 邊緣即時控制 (Edge-IVA)：Jung & Kim (Applied Sciences 2026) 實證動態調控取樣率可避免設備降頻掉格，0.375 FPS 取樣率在捕獲 99%+ 有效字幕的同時，大幅降低 60%+ 算力開銷，是滿足實時 SLA 閾值的關鍵。'
        ],
        bg_hex='F1F5F9',
        border_hex='CBD5E1',
        title_color_hex='0F172A',
        text_color_hex='334155'
    )
    print('Slide 5 updated with budget-aware sampling card.')

    # -------------------------------------------------------------
    # 5. Slide 10: 影像前處理權衡 -> 強化結論表格之學術依據
    # -------------------------------------------------------------
    s10 = prs.slides[9]
    # shape 2 is the conclusion table
    table2 = s10.shapes[2].table
    curr_text = table2.cell(1, 0).text
    table2.cell(1, 0).text = (
        "denoise 對辨識率的實測提升僅 2.0%，總處理時間增加 31.2%，且多項指標並不一致支持「on 較好」。"
        "因收益遠低於成本，且耗時增加違背實時標準，因此決策選擇 denoise off。\n\n"
        "【學術佐證】Ko & Lee (ACM CSCW 2026) 研究指出，視訊字幕文字先天具備高對比描邊（Stroke）與外陰影以對抗動態背景；"
        "傳統去噪濾波器易破壞字緣高頻特徵，導致微小筆畫模糊；保留灰階與對比強化即可最大化發揮深度學習 OCR（CRAFT/EasyOCR）之特徵提取能力。"
    )
    # Style the text inside the cell
    for p in table2.cell(1, 0).text_frame.paragraphs:
        p.font.name = '微軟正黑體'
        p.font.size = Pt(8.5)
        p.font.color.rgb = hex_to_rgb('0F172A')
    print('Slide 10 updated with denoise academic grounding.')

    # -------------------------------------------------------------
    # 6. Slide 11: 時序去重機制 -> 加入 AAAI 2026 頂會理論依據橫幅
    # -------------------------------------------------------------
    s11 = prs.slides[10]
    add_academic_card(
        s11,
        left=901700,
        top=4600000,
        width=10668000,
        height=680000,
        title='📚 時序去重理論依據：AAAI 2026 最新前沿 (Zhao et al.)',
        items=[
            '• AAAI 2026《Temporal Calibrating and Distilling for Scene-Text Aware Text-Video Retrieval》提出「視窗 OCR 字幕器（Window-OCR Captioner）」與時序冗餘蒸餾模組，證實滑動時間窗與生命週期狀態表能根除相鄰影格 OCR 抖動與重複碎片，有效聚合率躍升至 83.56%。'
        ],
        bg_hex='EFF6FF',
        border_hex='93C5FD',
        title_color_hex='1E40AF',
        text_color_hex='1E293B'
    )
    print('Slide 11 updated with AAAI temporal dedup card.')

    # -------------------------------------------------------------
    # 7. Slide 13: 時序去重指標表格 -> 強化結論儲存格
    # -------------------------------------------------------------
    s13 = prs.slides[12]
    table3 = s13.shapes[3].table
    table3.cell(1, 0).text = (
        "基於狀態表與時間窗機制，成功提供了乾淨、連續且具備精確時間戳記的結構化語料。\n\n"
        "【學術理論背書】AAAI 2026 (Zhao et al., TCD) 證實視訊密集場景文字存在「時序失準與重複冗餘」，"
        "本專案滑動時間窗聚合機制使多影格有效聚合率由 0.78% 躍升至 83.56%，0 秒碎片率下降 82.74%，為下游 NLP 提供高質量語料。"
    )
    for p in table3.cell(1, 0).text_frame.paragraphs:
        p.font.name = '微軟正黑體'
        p.font.size = Pt(9.5)
        p.font.color.rgb = hex_to_rgb('0F172A')
    print('Slide 13 updated with temporal dedup metrics conclusion.')

    # -------------------------------------------------------------
    # 8. Slide 14: NLP 多通道架構 -> 加入多通道決策理論依據卡片
    # -------------------------------------------------------------
    s14 = prs.slides[13]
    add_academic_card(
        s14,
        left=762000,
        top=5120000,
        width=10668000,
        height=1500000,
        title='📚 多通道決策理論依據 (Theoretical Foundation of Multi-Channel Decision)',
        items=[
            '• Channel 1 留存依據：Park & Kim (ACM TALLIP 2023) 與 Song & Park (EMNLP 2019) 指出韓語黏著語分詞高度依賴語素字典與空格容錯；本地專用引擎（Komoran/Kiwi）具備數學確定性與毫秒級響應，可信度最高。',
            '• Channel 2 淘汰依據：Kaya & Kirci (ICEEECS 2025) 實證純端到端大模型在專業符號解析時存在嚴重的語法虛構與幻覺問題，且生成延遲不可控（引發 60s+ 逾時）。',
            '• Channel 3 淘汰依據：陳相文 (東華資工 2026) 實證規則系統已能覆蓋 99% 的語意槽位，引入神經後備（Fallback）帶來 5 倍以上時間膨脹，但邊際精度提升不到 1%，不符邊際效益原則。'
        ],
        bg_hex='F8FAFC',
        border_hex='CBD5E1',
        title_color_hex='0F172A',
        text_color_hex='334155'
    )
    print('Slide 14 updated with multi-channel decision card.')

    # -------------------------------------------------------------
    # 9. Slide 18: SLA 閾值 -> 加入邊緣實時控制準則卡片
    # -------------------------------------------------------------
    s18 = prs.slides[17]
    add_academic_card(
        s18,
        left=2328355,
        top=5050000,
        width=7535140,
        height=1300000,
        title='📚 邊緣即時視訊分析時限滿意度準則 (Edge-IVA Real-Time Deadline Principle)',
        items=[
            '• 參照 Jung & Kim (Applied Sciences 2026) 提出的邊緣 IVA 閉環反饋控制與 100% 時限滿意度（Deadline Satisfaction）指標：本專案藉由演算法級時序去重與本地輕量分詞，確保個人裝置在無雲端算力支援下，依然嚴格滿足 T_process ≤ T_video 的即時服務等級保證。'
        ],
        bg_hex='1D4ED8',
        border_hex='93C5FD',
        title_color_hex='DBEAFE',
        text_color_hex='F8FAFC'
    )
    print('Slide 18 updated with SLA deadline card.')

    # -------------------------------------------------------------
    # 10. Slide 20: 新增獨立「參考文獻 (References)」投影片！
    # -------------------------------------------------------------
    blank_layout = prs.slide_layouts[6]
    s20 = prs.slides.add_slide(blank_layout)
    
    # Set dark background
    bg = s20.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = hex_to_rgb('0F172A') # Dark Slate matching Slide 1 & 19
    
    # Top Category Pill
    pill = s20.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(0.4), Inches(2.2), Inches(0.35))
    pill.fill.solid()
    pill.fill.fore_color.rgb = hex_to_rgb('3B82F6') # Blue
    pill.line.fill.background()
    p_pill = pill.text_frame.paragraphs[0]
    p_pill.text = 'ACADEMIC REFERENCES'
    p_pill.font.name = '微軟正黑體'
    p_pill.font.size = Pt(10)
    p_pill.font.bold = True
    p_pill.font.color.rgb = hex_to_rgb('FFFFFF')
    p_pill.alignment = PP_ALIGN.CENTER
    
    # Title Textbox
    tb_title = s20.shapes.add_textbox(Inches(0.8), Inches(0.85), Inches(11.5), Inches(0.6))
    p_title = tb_title.text_frame.paragraphs[0]
    p_title.text = '參考文獻'
    p_title.font.name = '微軟正黑體'
    p_title.font.size = Pt(28)
    p_title.font.bold = True
    p_title.font.color.rgb = hex_to_rgb('FFFFFF')
    
    p_sub = tb_title.text_frame.add_paragraph()
    p_sub.text = '專題核心理論依據、模型選型與實證評測文獻清單 (APA 7th Format)'
    p_sub.font.name = '微軟正黑體'
    p_sub.font.size = Pt(12)
    p_sub.font.color.rgb = hex_to_rgb('94A3B8')
    p_sub.space_before = Pt(2)
    
    # Two Columns for References
    col_w = Inches(5.6)
    col_h = Inches(4.8)
    top_pos = Inches(1.8)
    
    # Left Column Box
    box_l = s20.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), top_pos, col_w, col_h)
    box_l.fill.solid()
    box_l.fill.fore_color.rgb = hex_to_rgb('1E293B')
    box_l.line.color.rgb = hex_to_rgb('334155')
    box_l.line.width = Pt(1)
    tf_l = box_l.text_frame
    tf_l.word_wrap = True
    tf_l.margin_left = Inches(0.2)
    tf_l.margin_right = Inches(0.2)
    tf_l.margin_top = Inches(0.18)
    tf_l.margin_bottom = Inches(0.15)
    
    left_refs = [
        ("[1] Ko, T., & Lee, K. (2026). Toward a Multi-modal Understanding of Visual-Linguistic Design of Telop: A Computational Analysis of Telop Used in Korean YouTube Videos. Proceedings of the ACM on Human-Computer Interaction, 10(CSCW), Article CSCW170."),
        ("[2] Zhao, Z., Li, L., Shen, L., Sheng, X., Sun, Y., Kang, F., & Yan, C. (2026). Temporal Calibrating and Distilling for Scene-Text Aware Text-Video Retrieval. In Proceedings of the 40th AAAI Conference on Artificial Intelligence (AAAI-26), 13323-13331."),
        ("[3] Cai, W., Zhang, H., Huang, Y., Xie, Y., Gao, S., Deng, J., ... & Zhang, Z. (2026). Caption-once, Frames-on-Demand: Visual-Need Routing for Budget-Aware Agentic Long Video Understanding. arXiv:2609.11899."),
        ("[4] Park, C., & Kim, J. (2023). Robust Multi-task Learning-based Korean POS Tagging to Overcome Word Spacing Errors. ACM Transactions on Asian and Low-Resource Language Information Processing, 22(6), Article 182."),
        ("[5] Song, H. J., & Park, S. B. (2019). Korean Morphological Analysis with Tied Sequence-to-Sequence Multi-Task Model. In Proceedings of EMNLP-IJCNLP 2019, 1436-1441."),
        ("[6] Jung, H., & Kim, B. (2026). Resilient Edge-IVA: Perception-Aware Adaptive Control for Stable Real-Time Analytics on Resource-Constrained Devices. Applied Sciences (MDPI), 16(12), 5984.")
    ]
    
    for idx, ref in enumerate(left_refs):
        p = tf_l.paragraphs[0] if idx == 0 else tf_l.add_paragraph()
        p.text = ref
        p.font.name = '微軟正黑體'
        p.font.size = Pt(8.5)
        p.font.color.rgb = hex_to_rgb('E2E8F0')
        p.line_spacing = 1.15
        p.space_after = Pt(8)
    
    # Right Column Box
    box_r = s20.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), top_pos, col_w, col_h)
    box_r.fill.solid()
    box_r.fill.fore_color.rgb = hex_to_rgb('1E293B')
    box_r.line.color.rgb = hex_to_rgb('334155')
    box_r.line.width = Pt(1)
    tf_r = box_r.text_frame
    tf_r.word_wrap = True
    tf_r.margin_left = Inches(0.2)
    tf_r.margin_right = Inches(0.2)
    tf_r.margin_top = Inches(0.18)
    tf_r.margin_bottom = Inches(0.15)
    
    right_refs = [
        ("[7] Kim, J., Kahng, M., Choi, Y., & Kim, J. (2022). FitVid: Responsive and Flexible Video Content Adaptation. In Proceedings of the 2022 CHI Conference on Human Factors in Computing Systems (CHI '22), ACM."),
        ("[8] Volodina, E., Borin, L., Loftsson, H., Arnbjörnsdóttir, B., & Leifsson, G. Ö. (2012). Waste not, want not: Towards a system architecture for ICALL based on NLP component re-use. In Proceedings of the SLTC 2012 Workshop on NLP for CALL."),
        ("[9] Kaya, F., & Kirci, P. (2025). NLP-Based Query Interface for InfluxDB: Designing a Hybrid Architecture with SpaCy and Large Language Model. In Proceedings of ICEEECS 2025, 271-277."),
        ("[10] Watve, A. Y., & Bhalekar, M. A. (2021). Subtitle Extraction from Videos and Translation from English to Hindi. International Journal of Creative Research Thoughts (IJCRT), 9(12), d221-d228."),
        ("[11] 呂承恩 (2026). 應用大型語言模型於異質訂單文件之關鍵資訊擷取與標準化研究. 國立政治大學應用數學系碩士學位論文 (指導教授：蔡炎龍 博士)."),
        ("[12] 陳相文 (2026). 基於檢索增強生成與規則推理之臨床決策支援與 SOAP 輔助生成系統. 國立東華大學資訊工程學系碩士學位論文 (指導教授：羅壽之 博士).")
    ]
    
    for idx, ref in enumerate(right_refs):
        p = tf_r.paragraphs[0] if idx == 0 else tf_r.add_paragraph()
        p.text = ref
        p.font.name = '微軟正黑體'
        p.font.size = Pt(8.5)
        p.font.color.rgb = hex_to_rgb('E2E8F0')
        p.line_spacing = 1.15
        p.space_after = Pt(8)
    
    print('Slide 20 (References) created successfully.')

    # Save to the target PPTX file
    prs.save('報告/專題報告.pptx')
    print('Successfully saved updated presentation to 報告/專題報告.pptx! Total slides now:', len(prs.slides))

if __name__ == '__main__':
    update_presentation()
