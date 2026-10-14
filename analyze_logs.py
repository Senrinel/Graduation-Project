import re
import pandas as pd
import matplotlib.pyplot as plt
import os

log_file = r'Experiment on Sampling Rate Differences/log.txt'

data = []
current_run = {}

with open(log_file, 'r', encoding='utf-8') as f:
    for line in f:
        # Match FPS
        m = re.search(r'\[Step 2\] 依採樣率 ([\d\.]+) FPS', line)
        if m:
            if current_run:
                data.append(current_run)
            current_run = {'FPS': float(m.group(1))}
            continue
            
        # Match Frame Count
        m = re.search(r'\[完成\] 共輸出 (\d+) 張影格', line)
        if m and 'Frame Count' not in current_run:
            current_run['Frame Count'] = int(m.group(1))
            
        # Match OCR Time
        m = re.search(r'Step 4 總耗時: ([\d\.]+)s', line)
        if m:
            current_run['OCR Time (s)'] = float(m.group(1))
            
        # Match Deduped Sentences
        m = re.search(r'跨影格去重後剩 (\d+) 句字幕', line)
        if m:
            current_run['Deduped Sentences'] = int(m.group(1))
            
        # Match Word Stats
        m = re.search(r'處理詞彙數: (\d+)，字典命中: (\d+)（命中率 ([\d\.]+)%\）', line)
        if m:
            current_run['Total Words'] = int(m.group(1))
            current_run['Dict Hits'] = int(m.group(2))
            current_run['Hit Rate (%)'] = float(m.group(3))

if current_run:
    data.append(current_run)

df = pd.DataFrame(data)
df = df.sort_values('FPS')

print(df.to_string())

excel_path = 'Sampling_Rate_Analysis.xlsx'
writer = pd.ExcelWriter(excel_path, engine='xlsxwriter')
df.to_excel(writer, sheet_name='Data', index=False)

workbook = writer.book
worksheet = writer.sheets['Data']

# Chart 1: FPS vs Word Count and Dict Hits
chart1 = workbook.add_chart({'type': 'line'})
chart1.add_series({
    'name': 'Total Words',
    'categories': ['Data', 1, 0, len(df), 0],
    'values': ['Data', 1, 4, len(df), 4],
})
chart1.add_series({
    'name': 'Dict Hits',
    'categories': ['Data', 1, 0, len(df), 0],
    'values': ['Data', 1, 5, len(df), 5],
})
chart1.set_title({'name': 'FPS vs Vocabulary Extraction'})
chart1.set_x_axis({'name': 'FPS'})
chart1.set_y_axis({'name': 'Count'})
worksheet.insert_chart('H2', chart1)

# Chart 2: FPS vs OCR Time
chart2 = workbook.add_chart({'type': 'line'})
chart2.add_series({
    'name': 'OCR Time (s)',
    'categories': ['Data', 1, 0, len(df), 0],
    'values': ['Data', 1, 2, len(df), 2],
})
chart2.set_title({'name': 'FPS vs OCR Time'})
chart2.set_x_axis({'name': 'FPS'})
chart2.set_y_axis({'name': 'Time (s)'})
worksheet.insert_chart('H18', chart2)

writer.close()
print(f'Excel file generated at {excel_path}')
