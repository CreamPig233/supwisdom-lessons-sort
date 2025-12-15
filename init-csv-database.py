import csv
from bs4 import BeautifulSoup
import requests
import time
import pandas as pd

# ===== 手动配置项 =====

BASE_URL = 'http://example.com'  # 教务系统域名，此处不加/eams后缀
EAMS_COOKIE = 'semester.id=xxx; JSESSIONID=xxx; SERVERNAME=xxx; GSESSIONID=xxx'  # 教务系统登录后的 Cookie 值
EAMS_SEMESTER_ID = 'xxx' # 下述post请求中的semester.id参数值
EAMS_UNDERLINE = 'xxx' # 下述post请求中的_参数值

 
 
# ===== 其他配置项 =====
TEACHER_LIST_OUTPUT_CSV = 'teacher_list.csv'
LESSONS_LIST_OUTPUT_CSV = 'lessons_list.csv'
LESSONS_DEDUP_LIST_OUTPUT_CSV = 'lessons_list_dedup.csv'
CLASSROOM_LIST_OUTPUT_TXT = 'classroom_list.txt'
LOG_FILE = 'process.log'


# ===== 自定义 print + log 函数 =====
def log_print(*args, **kwargs):
    """同时打印到控制台和日志文件"""
    # 构造要输出的字符串（模拟 print 的默认行为）
    sep = kwargs.get('sep', ' ')
    end = kwargs.get('end', '\n')
    message = sep.join(str(arg) for arg in args) + end

    # 打印到控制台
    print(message, end='')  # 注意：message 已包含 end

    # 追加写入日志文件（使用 UTF-8）
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(message)


# ===== 对教务系统-教师公共课表进行请求 =====

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Cookie': EAMS_COOKIE,
})

session.get(BASE_URL + '/eams/studentPublicScheduleQuery!search.action')

time.sleep(1)  # 等待 1 秒，防止请求过快

session.headers.update({
    'referer': BASE_URL + '/eams/studentPublicScheduleQuery!search.action',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Cookie': EAMS_COOKIE,
    'Host': BASE_URL.replace('http://', '').replace('https://', ''),
    'Origin': BASE_URL,
    'Pragma': 'no-cache',
    'X-Requested-With': 'XMLHttpRequest'
})


html_content = session.post(
            url = BASE_URL + '/eams/studentPublicScheduleQuery!search.action',
            data = f'semester.id={EAMS_SEMESTER_ID}&courseTableType=teacher&_={EAMS_UNDERLINE}&pageNo=1&pageSize=10000'
).text



# ===== 解析 HTML =====
soup = BeautifulSoup(html_content, 'html.parser')

teachers = []
a_tags = soup.find_all('a', href=True)

for idx, a in enumerate(a_tags, start=1):
    name = a.get_text(strip=True)
    relative_link = a['href']
    full_link = BASE_URL + relative_link

    # 初始化默认值为 "空"
    gender = "空"
    department = "空"

    # 找到所在行（<tr>）
    td_name = a.find_parent('td')
    if td_name:
        row = td_name.find_parent('tr')
        if row:
            tds = row.find_all('td')
            # 假设结构：[0:空] | [1:姓名] | [2:性别] | [3:院系]
            if len(tds) > 2:
                g_text = tds[2].get_text(strip=True)
                gender = g_text if g_text else "空"
            if len(tds) > 3:
                d_text = tds[3].get_text(strip=True)
                department = d_text if d_text else "空"
        else:
            # 备用方案：通过全局 td 列表定位（适用于无 <tr> 的情况）
            all_tds = soup.find_all('td')
            try:
                i = all_tds.index(td_name)
                if i + 1 < len(all_tds):
                    g_text = all_tds[i + 1].get_text(strip=True)
                    gender = g_text if g_text else "null"
                if i + 2 < len(all_tds):
                    d_text = all_tds[i + 2].get_text(strip=True)
                    department = d_text if d_text else "null"
            except ValueError:
                pass  # 保持默认 "null"

    teachers.append({
        '序号': idx,
        '姓名': name,
        '性别': gender,
        '院系': department,
        '链接': full_link
    })

# ===== 将教师信息写入 CSV =====
with open(TEACHER_LIST_OUTPUT_CSV, 'w', encoding='utf-8-sig', newline='') as csvfile:
    fieldnames = ['序号', '姓名', '性别', '院系', '链接']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(teachers)

log_print(f"✅ 已成功提取 {len(teachers)} 位教师信息，并保存至 '{TEACHER_LIST_OUTPUT_CSV}'")

time.sleep(1)  # 等待 1 秒，防止请求过快

# ===== 初始化课程输出 CSV =====
output_headers = [
    "序号", "课程序号", "课程代码", "课程名称", "课程类别", "教学班",
    "周课时", "学分", "授课语言", "上课人数", "是否排课", "周次",
    "星期", "节次", "授课教师", "上课地点", "备注"
]

with open(LESSONS_LIST_OUTPUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
    csv.writer(f).writerow(output_headers)

total_extracted = 0


# ===== 开始处理课程列表 =====
log_print(f"开始处理教师排课数据，输入文件: {TEACHER_LIST_OUTPUT_CSV}")

try:
    with open(TEACHER_LIST_OUTPUT_CSV, 'r', encoding='utf-8-sig') as f_in:
        reader = csv.reader(f_in)
        header = next(reader, None)  # 跳过表头

        for row_idx, row in enumerate(reader, start=1):
            if len(row) < 5:
                log_print(f"[{row_idx}] ⚠️ 行数据不足5列，跳过: {row}")
                continue

            teacher_info = row[1].strip()
            url = row[4].strip()

            if not url or not url.startswith('http'):
                log_print(f"[{row_idx}] ⚠️ 无效URL，跳过教师: {teacher_info}")
                continue

            retry_count = 0
            while True:
                retry_count += 1
                if retry_count > 1:
                    log_print(f"[{row_idx}] 教师 {teacher_info} 第 {retry_count} 次重试...")

                try:
                    log_print(f"[{row_idx}] 正在请求教师: {teacher_info} | URL: {url}")

                    resp = session.get(url, timeout=15)
                    resp.raise_for_status()
                    resp.encoding = 'utf-8'
                    html = resp.text

                    soup = BeautifulSoup(html, 'html.parser')
                    scheduled_span = soup.find('span', string='已排课')

                    course_rows = []
                    if scheduled_span:
                        scheduled_table = scheduled_span.find_next('table')
                        if scheduled_table:
                            data_trs = scheduled_table.find_all('tr')[1:]
                            for tr in data_trs:
                                if tr.find('td', colspan=True):
                                    continue
                                tds = tr.find_all(['td', 'th'])
                                if not tds:
                                    continue
                                row_data = []
                                for td in tds:
                                    text = td.get_text(strip=True)
                                    row_data.append(text if text else "null")
                                while len(row_data) < 17:
                                    row_data.append("null")
                                course_rows.append(row_data[:17])

                    with open(LESSONS_LIST_OUTPUT_CSV, 'a', encoding='utf-8-sig', newline='') as out_f:
                        csv.writer(out_f).writerows(course_rows)

                    current_count = len(course_rows)
                    total_extracted += current_count
                    log_print(f"✅ 教师 {teacher_info} 成功提取 {current_count} 条课程（第 {retry_count} 次尝试）")
                    break

                except Exception as e:
                    log_print(f"❌ 教师 {teacher_info} 处理失败（第 {retry_count} 次）: {e}")
                    log_print("   → 1秒后重试...")
                    time.sleep(1)

            time.sleep(1)

    log_print(f"\n🎉 所有教师处理完毕！共提取 {total_extracted} 条已排课记录，保存至 '{LESSONS_LIST_OUTPUT_CSV}'")

except Exception as e:
    log_print(f"💥 主程序崩溃: {e}")
    raise


# ===== 对课程进行去重 =====

# 读取 CSV 文件
df = pd.read_csv(LESSONS_LIST_OUTPUT_CSV)

# 指定要拼接的列（按0起始索引）
cols_to_combine = [2, 5, 11, 12, 13, 15]  # 对应第3,6,12,13,14,16列

# 检查列索引是否有效
max_col_index = df.shape[1] - 1
if max(cols_to_combine) > max_col_index:
    raise IndexError("指定的列索引超出CSV文件实际列数，请检查文件格式。")

# 提取这些列，并将每行拼接为一个字符串作为唯一标识
# 使用 fillna('') 防止 NaN 导致拼接出问题
df_subset = df.iloc[:, cols_to_combine].fillna('').astype(str)
df['combined_key'] = df_subset.apply('_|_'.join, axis=1)  # 使用特殊分隔符避免字段混淆

# 去重：保留第一次出现的行（基于 combined_key）
df_dedup = df.drop_duplicates(subset='combined_key', keep='first')

# 删除辅助列
df_dedup = df_dedup.drop(columns=['combined_key'])

# 保存结果到新文件（可选）
df_dedup.to_csv('lessons_list_dedup.csv', index=False, encoding='utf-8-sig')

log_print("\n课程去重")
log_print(f"原始行数: {len(df)}")
log_print(f"去重后行数: {len(df_dedup)}")
log_print(f"去重结果已保存到 {LESSONS_DEDUP_LIST_OUTPUT_CSV}")

# ===== 去除教室名的星号 =====
# 读取 CSV 文件
file_path = LESSONS_DEDUP_LIST_OUTPUT_CSV
df = pd.read_csv(file_path, dtype=str)  # 以字符串类型读取，避免类型问题

# 检查是否有至少16列
if df.shape[1] < 16:
    raise ValueError(f"CSV 文件列数不足16列，当前只有 {df.shape[1]} 列。")

# 去除第16列（索引15）中的所有星号 *
df.iloc[:, 15] = df.iloc[:, 15].astype(str).str.replace('*', '', regex=False)

# 写回原文件（覆盖）
df.to_csv(file_path, index=False, encoding='utf-8-sig')

log_print(f"已成功去除 {file_path} 中第16列的所有 '*'，并保存回原文件。")


# ===== 处理教室列表 =====
df = pd.read_csv(LESSONS_LIST_OUTPUT_CSV)

if '上课地点' in df.columns:
    p_column = df['上课地点']

# 用于去重和保持顺序
seen = set()
unique_items = []

# 遍历 P 列的每一行（跳过空值）
for value in p_column.dropna():
    # 转为字符串并去除首尾空白
    str_value = str(value).strip()
    
    # 按逗号分割（支持“a,b,c”形式）
    if ',' in str_value:
        parts = [part.strip() for part in str_value.split(',')]
    else:
        parts = [str_value]
    
    # 处理每个部分
    for part in parts:
        # 去除星号 *
        cleaned = part.replace('*', '').strip()
        # 忽略空字符串，并去重
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique_items.append(cleaned)

# 写入 txt 文件，一行一个
with open(CLASSROOM_LIST_OUTPUT_TXT, 'w', encoding='utf-8') as f:
    for item in unique_items:
        f.write("默认校区:默认楼宇:" + item + '\n')

print(f"共写入 {len(unique_items)} 个教室到 {CLASSROOM_LIST_OUTPUT_TXT}")


# ===== 对教室列表文件按升序排序 =====
file_path = CLASSROOM_LIST_OUTPUT_TXT

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 去除每行末尾的换行符（便于排序），并过滤空行（可选）
stripped_lines = [line.rstrip('\n\r') for line in lines]

# 升序排序（默认是字典序，区分大小写）
sorted_lines = sorted(stripped_lines)

# 将排序后的行重新加上换行符
output_lines = [line + '\n' for line in sorted_lines]

# 写回原文件
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(output_lines)

log_print(f"教室列表 {file_path} 已按升序排序并保存。")