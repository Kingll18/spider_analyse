from requests_html import HTMLSession
from selenium import webdriver
from selenium.webdriver import ChromeOptions
from lxml import etree
from fontTools.ttLib import TTFont

import threading
import time
import re
import os, xlwt, xlrd
from xlutils.copy import copy

option = ChromeOptions()
option.add_argument('--headless')  # 指定无头模式 无界面启动


class Spider(object):
    def __init__(self):
        self.url = "https://www.shixiseng.com/interns"
        self.session = HTMLSession()
        self.browser = webdriver.Chrome(options=option)
        self.mutex = threading.Lock()
        print("================欢迎使用实习僧网站工作信息爬取小程序================")
        print("请输入您需要爬取信息的工作(用,隔开 如:前端,后端,数据库,运维,java,C,python,Vue,等)：")
        self.keyword = input("")

    def get_html(self):
        # 获取keyword
        self.browser.get(url=self.url)
        # 解字体加密
        new_cmap = self.font_parse(self.url)

        print(f"===正在爬取 {'  |  '.join(self.keyword.split(','))} 相关的工作信息===")
        for keyword in self.keyword.split(","):
            self.browser.find_element_by_xpath('//div[@class="input-group"]//input[@type="text"]').send_keys(keyword)
            time.sleep(0.5)
            self.browser.find_element_by_xpath('//div[@class="input-group"]//span[@class="search-btn"]').click()
            time.sleep(1)

            # 获取最大页数 和 当前url
            url = self.browser.current_url
            html = self.browser.page_source
            tree = etree.HTML(html)
            end_page = int(tree.xpath('//ul[@class="el-pager"]//li[last()]/text()')[0])
            model_url = url.replace("page=1", "page={}")
            self.next_page(model_url, end_page, new_cmap, keyword)

    def next_page(self, model_url, end_page, new_cmap, keyword):
        for page in range(1, end_page + 1):
            new_url = model_url.format(page)
            thread = threading.Thread(target=self.parse, args=(new_url, new_cmap, keyword))
            thread.start()

    def parse(self, new_url, new_cmap, keyword):
        response = self.session.get(url=new_url)
        res = self.replace_html(response.text, new_cmap)
        # 解析数据
        tree = etree.HTML(res)
        for div in tree.xpath('//div[@class="intern-wrap intern-item"]'):
            title = ''.join(div.xpath('.//div[@class="f-l intern-detail__job"]/p[1]//text()')).split(" ")  # 标题
            lable = ''.join(div.xpath('.//div[@class="f-l intern-detail__job"]/p[2]//text()')).split(" ")  # 标签
            job = title[0]
            price = title[-1]
            address = lable[0]
            week_time = lable[2]
            month_time = lable[4]
            href = div.xpath('.//div[@class="f-l intern-detail__job"]//a/@href')[0]

            detail_res = self.session.get(url=href)
            time = detail_res.html.xpath('//div[@class="job-header"]/div[2]//text()')[0]
            content = ''.join(detail_res.html.xpath('//div[@class="job_detail"]//text()')).replace(" ", "").replace(
                '\n', ' ')
            print(time, job, price, address, week_time, month_time, href, content)

            data = {
                'data': [time, job, price, address, week_time, month_time, href, content]
            }
            self.mutex.acquire()
            self.SaveExcel(data, keyword)
            self.mutex.release()

    def font_parse(self, url):
        # 1. 请求页面 获取响应 从响应里面取出字体文件下载链接
        response = self.session.get(url=url)
        font_url = re.findall('src: url\((.*?)\);', response.text)[0]
        font_url = 'https://www.shixiseng.com' + font_url  # 拼接出完整的下载链接
        with open('font.ttf', 'wb')as f:
            f.write(self.session.get(url=font_url).content)  # 下载字体文件 保存到本地
        font = TTFont('font.ttf')  # 加载字体文件
        font.saveXML('font.xml')
        '''
            请求多次发现 字体顺序 和值 都没有发生改变
            0xe329(code值)  &#xe329(网页源码) uni38(name值) \u0038(unicode解码得到页面展示数据) ==  8
                &#xe329 = 8
            uni是Unicode编码的 \u0038 代表的就素对应映射的值 直接Unicode解码就可以得到 只不过数字要填充0
        '''
        # print(font.getBestCmap())  # font.getBestCmap() 获取cmap节点的code和name的映射 code是十进制需要转成16进制
        new_cmap = self.font_cmap(font.getBestCmap())
        return new_cmap

    def font_cmap(self, cmap):
        # 处理映射关系 替换成真正的数据
        del cmap[120]  # 删除第一个没用的数据 现在是十进制 值是120 所以我们删除的是120
        new_cmap = {}
        for key, value in cmap.items():
            key = hex(key).replace('0x', '&#x')  # 转换成16进制 再替换成网页源码的数据
            value = value.replace('uni', '')  # 把前面的uni删掉
            if len(value) < 4:
                value = (r'\u00' + value).encode('utf-8').decode('unicode_escape')  # Unicode解码 替换成我们看到的数据
            else:
                value = (r'\u' + value).encode('utf-8').decode('unicode_escape')
            new_cmap[key] = value
        return new_cmap

    def replace_html(self, res, new_cmap):
        # 替换响应里面 加密的数据 替换成真实的我们看到的数据
        for key, value in new_cmap.items():
            if key in res:  # 如果key的值在响应源码里面 代表是加密的
                res = res.replace(key, value)
        return res

    def SaveExcel(self, data, keyword):
        """
        使用前，请先阅读代码
        :param data: 需要保存的data字典(有格式要求)
        :return:
        格式要求:
            data = {
            '基本详情': ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']
        }
        注意：这个模板程序会将data的key值作为excel的表名来判断，一样才会保存
        """
        # 创建保存excel表格的文件夹
        # os.getcwd() 获取当前文件路径
        os_mkdir_path = os.getcwd() + '/数据/'
        # 判断这个路径是否存在，不存在就创建
        if not os.path.exists(os_mkdir_path):
            os.mkdir(os_mkdir_path)
        # 判断excel表格是否存在           工作簿文件名称
        os_excel_path = os_mkdir_path + f'{keyword}.xls'
        if not os.path.exists(os_excel_path):
            # 不存在，创建工作簿(也就是创建excel表格)
            workbook = xlwt.Workbook(encoding='utf-8')
            """工作簿中创建新的sheet表"""  # 设置表名
            worksheet1 = workbook.add_sheet("data", cell_overwrite_ok=True)
            """设置sheet表的表头"""
            "[time, job, price, address, work_time, href, content]"
            sheet1_headers = ('time', 'job', 'price', 'address', 'week_time', 'month_time', 'href', 'content')
            # 将表头写入工作簿
            for header_num in range(0, len(sheet1_headers)):
                # 设置表格长度
                worksheet1.col(header_num).width = 2560 * 3
                # 写入            行, 列,           内容
                worksheet1.write(0, header_num, sheet1_headers[header_num])
            # 循环结束，代表表头写入完成，保存工作簿
            workbook.save(os_excel_path)
        # 判断工作簿是否存在
        if os.path.exists(os_excel_path):
            # 打开工作簿
            workbook = xlrd.open_workbook(os_excel_path)
            # 获取工作薄中所有表的个数
            sheets = workbook.sheet_names()
            for i in range(len(sheets)):
                for name in data.keys():
                    worksheet = workbook.sheet_by_name(sheets[i])
                    # 获取工作薄中所有表中的表名与数据名对比
                    if worksheet.name == name:
                        # 获取表中已存在的行数
                        rows_old = worksheet.nrows
                        # 将xlrd对象拷贝转化为xlwt对象
                        new_workbook = copy(workbook)
                        # 获取转化后的工作薄中的第i张表
                        new_worksheet = new_workbook.get_sheet(i)
                        for num in range(0, len(data[name])):
                            new_worksheet.write(rows_old, num, data[name][num])
                        new_workbook.save(os_excel_path)

    def run(self):
        self.get_html()


if __name__ == '__main__':
    spider = Spider()
    spider.run()
