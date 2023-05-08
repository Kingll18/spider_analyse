import numpy as np
import pandas as pd
import os

from pyecharts.charts import Pie
from pyecharts import options as opts
from pyecharts.globals import ThemeType

file_names = os.listdir("./数据")
job_list = []
count_list = []
for file in file_names:
    job = file.split(".")[0]
    xlsx = pd.ExcelFile(f'./数据/{file}')  # 准备好excel文件
    data = pd.read_excel(xlsx, 'data')  # 读取指定的表
    # print(data)
    # print(data.isnull().any())

    # print(data[data['job'].isnull()])
    # print(data[data['price'].isnull()])
    data = data.dropna()
    # print(data)

    final = data.query("month_time == '2个月' | month_time == '3个月'")
    count = int(final['job'].count())
    job_list.append(job)
    count_list.append(count)

color_lists = ['red', 'blue', 'cyan', 'purple', 'yellow', 'orange', 'green', 'pink', 'gray', 'light blue', 'dark green',
               'brown']
color_list = []
for i in range(0, len(job_list)):
    color_list.append(color_lists[i])
print(job_list)
print(count_list)
print(color_list)

pie = (
    Pie(init_opts=opts.InitOpts(theme=ThemeType.CHALK))
        .add("", [list(z) for z in zip(job_list, count_list)])
        .set_colors(color_list)
        .set_global_opts(title_opts=opts.TitleOpts(title="各专业实习岗位数量"))

)
pie.render()
