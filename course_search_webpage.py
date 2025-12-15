import streamlit as st
import pandas as pd
import re

# ===========================================
# 配置文件路径
# ===========================================
COURSE_DATA_PATH = "lessons_list_dedup.csv"
CLASSROOM_LIST_PATH = "classroom_list.txt"

# ===========================================
# 加载并结构化教室列表（仅用于构建三级菜单）
# ===========================================
@st.cache_data
def load_classrooms_structured():
    """
    从 classroom.txt 读取，格式：主校区:教学楼:教101
    返回 structured: {校区: {楼宇: [教室名1, 教室名2, ...]}}
    """
    try:
        with open(CLASSROOM_LIST_PATH, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
    except FileNotFoundError:
        st.error(f"❌ 未找到文件 `{CLASSROOM_LIST_PATH}`")
        st.stop()
    
    structured = {}
    valid_count = 0

    for line in lines:
        # 去除首尾空白 + BOM
        full_name = line.strip().lstrip('\ufeff')
        if not full_name:
            continue
        
        parts = full_name.split(":", 2)  # 最多分3段
        if len(parts) < 3:
            # 可选：打印警告（调试用）
            # st.warning(f"⚠️ 跳过无效行: {full_name}")
            continue
        
        campus, building, room = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not (campus and building and room):
            continue

        if campus not in structured:
            structured[campus] = {}
        if building not in structured[campus]:
            structured[campus][building] = set()
        structured[campus][building].add(room)
        valid_count += 1

    if valid_count == 0:
        st.error(f"❌ `{CLASSROOM_LIST_PATH}` 中没有有效数据。请确保每行格式为：`校区:楼宇:教室名`")
        st.stop()

    # 转为排序列表
    for campus in structured:
        for building in structured[campus]:
            structured[campus][building] = sorted(structured[campus][building])
        structured[campus] = dict(sorted(structured[campus].items()))
    structured = dict(sorted(structured.items()))

    return structured

# ===========================================
# 工具函数（周次、节次、星期）
# ===========================================
def parse_weeks(week_str):
    if not week_str or str(week_str).strip().lower() in ("null", "", "无"):
        return set()
    weeks = set()
    normalized = str(week_str).replace('；', ';').replace(';', ',')
    parts = [p.strip() for p in normalized.split(',') if p.strip()]
    range_pattern = re.compile(r'^\[(\d+)-(\d+)\](.*)$')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        match = range_pattern.match(part)
        if match:
            start = int(match.group(1))
            end = int(match.group(2))
            suffix = match.group(3).strip()
            week_range = list(range(start, end + 1))
            if '单' in suffix:
                selected = [w for w in week_range if w % 2 == 1]
            elif '双' in suffix:
                selected = [w for w in week_range if w % 2 == 0]
            else:
                selected = week_range
            weeks.update(selected)
        elif part.isdigit():
            weeks.add(int(part))
    return weeks

def extract_periods(period_str):
    if not isinstance(period_str, str) or period_str.strip().lower() in ("null", "", "无"):
        return set()
    match = re.search(r'\[(\d+)-(\d+)\]', period_str.strip())
    if match:
        a, b = int(match.group(1)), int(match.group(2))
        if a <= b:
            return set(range(a, b + 1))
    return set()

def normalize_weekday(raw):
    if pd.isna(raw) or str(raw).strip().lower() in ("null", "", "无"):
        return None
    s = str(raw).strip()
    mapping = {
        "星期日": "日",
        "星期一": "一",
        "星期二": "二",
        "星期三": "三",
        "星期四": "四",
        "星期五": "五",
        "星期六": "六"
    }
    return mapping.get(s)

WEEKDAY_TO_COL = {"日": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}

# ===========================================
# 渲染课表 HTML
# ===========================================
def render_timetable(filtered_df):
    grid = [[[] for _ in range(7)] for _ in range(12)]

    for _, row in filtered_df.iterrows():
        raw_weekday = row.get("星期", "")
        period_str = str(row.get("节次", ""))
        course_name = str(row.get("课程名称", "未知课程"))

        weekday_norm = normalize_weekday(raw_weekday)
        if weekday_norm is None:
            continue

        col = WEEKDAY_TO_COL[weekday_norm]
        periods = extract_periods(period_str)

        for p in periods:
            if 1 <= p <= 12:
                grid[p - 1][col].append(course_name)

    html = """
    <style>
    .timetable {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
        table-layout: fixed;
    }
    .timetable th,
    .timetable td {
        border: 1px solid #ccc;
        padding: 6px;
        text-align: center;
        vertical-align: top;
        height: 60px;
        word-wrap: break-word;
    }
    .timetable th {
        background-color: #e0e0e0;
        color: white;
        font-weight: bold;
    }
    .has-course {
        background-color: #1E90FF;
        color: white;
        font-weight: bold;
    }
    </style>
    <table class="timetable">
      <thead>
        <tr>
          <th>节次</th>
          <th>星期日</th>
          <th>星期一</th>
          <th>星期二</th>
          <th>星期三</th>
          <th>星期四</th>
          <th>星期五</th>
          <th>星期六</th>
        </tr>
      </thead>
      <tbody>
    """

    for i in range(12):
        html += f"<tr><td>{i + 1}</td>"
        for j in range(7):
            courses = grid[i][j]
            if courses:
                display_text = "<br>".join(courses[:2])
                if len(courses) > 2:
                    display_text += "<br>..."
                html += f'<td class="has-course">{display_text}</td>'
            else:
                html += "<td></td>"
        html += "</tr>"

    html += "</tbody></table>"
    return html

# ===========================================
# 加载课程数据（CSV 中上课地点 = 教室名）
# ===========================================
@st.cache_data
def load_and_preprocess_data():
    try:
        df = pd.read_csv(COURSE_DATA_PATH, dtype=str)
    except FileNotFoundError:
        st.error(f"❌ 未找到文件 `{COURSE_DATA_PATH}`")
        st.stop()
    
    required_cols = ["序号", "课程代码", "课程名称", "周次", "星期", "节次", "授课教师", "上课地点"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        st.error(f"❌ CSV 缺少必要列: {missing}")
        st.stop()
    
    df = df.fillna("null")
    df['_parsed_weeks'] = df['周次'].apply(parse_weeks)
    return df

# ===========================================
# 主程序
# ===========================================
st.set_page_config(page_title="课程检索系统", layout="wide")
st.title("📚 课程多维检索系统")

df = load_and_preprocess_data()
structured_classrooms = load_classrooms_structured()
if not structured_classrooms:
    st.stop()

# ========== 初始化状态 ==========
if 'current_week' not in st.session_state:
    st.session_state.current_week = 1
if 'course_name' not in st.session_state:
    st.session_state.course_name = ""
if 'selected_periods' not in st.session_state:
    st.session_state.selected_periods = []
if 'selected_campus' not in st.session_state:
    st.session_state.selected_campus = ""
if 'selected_building' not in st.session_state:
    st.session_state.selected_building = ""
if 'selected_room_name' not in st.session_state:
    st.session_state.selected_room_name = ""
if 'location_input' not in st.session_state:
    st.session_state.location_input = ""

# ========== 侧边栏 ==========
st.sidebar.header("🔍 筛选条件")

# 课程名称
st.session_state.course_name = st.sidebar.text_input(
    "课程名称（模糊搜索）",
    value=st.session_state.course_name,
    key="course_name_input"
)

# 周次控制
col_prev, col_text, col_next = st.sidebar.columns([1, 2, 1])
with col_prev:
    prev_clicked = st.button("◀", help="上一周")
with col_next:
    next_clicked = st.button("▶", help="下一周")

MAX_WEEK = 20
if prev_clicked:
    if st.session_state.current_week > 1:
        st.session_state.current_week -= 1
        st.rerun()
elif next_clicked:
    if st.session_state.current_week < MAX_WEEK:
        st.session_state.current_week += 1
        st.rerun()

with col_text:
    st.markdown(
        f"<div style='text-align: center; font-weight: bold;'>第 {st.session_state.current_week} 周</div>",
        unsafe_allow_html=True
    )

# 节次多选
st.session_state.selected_periods = st.sidebar.multiselect(
    "节次（可多选）",
    options=[str(i) for i in range(1, 13)],
    default=st.session_state.selected_periods,
    key="periods_multiselect"
)

# === 上课地点：三级菜单（仅导航，值 = 教室名）===
st.sidebar.markdown("### 📍 上课地点")

# 校区
campuses = list(structured_classrooms.keys())
selected_campus = st.sidebar.selectbox(
    "校区", options=[""] + campuses,
    index=([""] + campuses).index(st.session_state.selected_campus)
    if st.session_state.selected_campus in [""] + campuses else 0,
    key="campus_select"
)
st.session_state.selected_campus = selected_campus

# 楼宇
buildings = []
if selected_campus:
    buildings = list(structured_classrooms[selected_campus].keys())
selected_building = st.sidebar.selectbox(
    "楼宇", options=[""] + buildings,
    index=([""] + buildings).index(st.session_state.selected_building)
    if st.session_state.selected_building in [""] + buildings else 0,
    key="building_select"
)
st.session_state.selected_building = selected_building

# 教室名（来自 txt 的最后一段）
room_names_in_building = []
if selected_campus and selected_building:
    room_names_in_building = structured_classrooms[selected_campus][selected_building]

selected_room_name = st.sidebar.selectbox(
    "教室", options=[""] + room_names_in_building,
    index=([""] + room_names_in_building).index(st.session_state.selected_room_name)
    if st.session_state.selected_room_name in [""] + room_names_in_building else 0,
    key="room_select"
)
st.session_state.selected_room_name = selected_room_name

# 手动输入（直接匹配教室名）
st.session_state.location_input = st.sidebar.text_input(
    "或直接输入教室名",
    value=st.session_state.location_input,
    key="location_input_widget"
)

# 重置按钮
if st.sidebar.button("🔄 重置筛选"):
    st.session_state.current_week = 1
    st.session_state.course_name = ""
    st.session_state.selected_periods = []
    st.session_state.selected_campus = ""
    st.session_state.selected_building = ""
    st.session_state.selected_room_name = ""
    st.session_state.location_input = ""
    st.rerun()

# ========== 数据筛选 ==========
filtered_df = df.copy()

# 课程名称
if st.session_state.course_name:
    filtered_df = filtered_df[
        filtered_df['课程名称'].str.contains(st.session_state.course_name, case=False, na=False)
    ]

# 周次
filtered_df = filtered_df[
    filtered_df['_parsed_weeks'].apply(lambda ws: st.session_state.current_week in ws)
]

# 节次
if st.session_state.selected_periods:
    selected_set = {int(p) for p in st.session_state.selected_periods}
    filtered_df = filtered_df[
        filtered_df['节次'].apply(lambda x: bool(extract_periods(x) & selected_set))
    ]

# === 📍 上课地点：全部基于 df['上课地点']（即教室名）===
manual_input = st.session_state.location_input.strip()
selected_room = st.session_state.selected_room_name

if manual_input:
    # 模糊匹配教室名
    filtered_df = filtered_df[
        filtered_df['上课地点'].astype(str).str.contains(manual_input, case=False, na=False)
    ]
elif selected_room:
    # 精确匹配教室名
    filtered_df = filtered_df[
        filtered_df['上课地点'].astype(str) == selected_room
    ]

# ========== 显示结果 ==========
st.subheader(f"📅 第 {st.session_state.current_week} 周课程日历视图")
if len(filtered_df) > 0:
    st.markdown(render_timetable(filtered_df), unsafe_allow_html=True)
else:
    st.info("该周暂无课程安排")

st.subheader(f"✅ 共找到 {len(filtered_df)} 条课程记录")

display_cols = ["序号", "课程代码", "课程名称", "周次", "星期", "节次", "授课教师", "上课地点", "教学班", "备注"]
available_cols = [col for col in display_cols if col in filtered_df.columns]
result_df = filtered_df[available_cols]

st.dataframe(result_df, use_container_width=True, hide_index=True)