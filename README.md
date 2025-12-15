# supwisdom-lessons-sort
针对树维教务系统的课程爬虫和检索系统
（以东北大学本科生综合教务系统为例）

关键词：东北大学, NEU, 树维, supwisdom, 教务系统

## 如何使用

1. 打开学校的树维教务系统，选择公共课表查询，课表类型选择教师课表，打开浏览器控制台，点击教师课表的切换下一页，获取请求用的参数，填在init-csv-database.py的手动配置项。

2. 运行`python init-csv-database.py`，得到需要的数据文件。其中`CLASSROOM_LIST_OUTPUT_TXT`和`LESSONS_DEDUP_LIST_OUTPUT_CSV`两个文件不得删除。

3. 使用`streamlit run .\course_search_webpage.py`打开网页服务器。