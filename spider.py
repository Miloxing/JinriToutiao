import json
import re
from urllib.parse import urlencode
from hashlib import md5
import os
import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException
from config import *
import pymongo
from multiprocessing import Pool
client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]

def headers():
    what = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'
    headers = {
        'user-agent': what}
    return headers

def get_page_index(offset, keyword):
    data = {
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': '20',
        'cur_tab': '3',
        'from':'gallery'
    }
    url = 'https://www.toutiao.com/search_content/?' + urlencode(data)

    try:
        response = requests.get(url, headers=headers())
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求出错')
        return None


def parse_page_index(html):
    data = json.loads(html)
    if data and 'data' in data.keys():
        for item in data.get('data'):
            yield item.get('article_url')

def get_page_detail(url):
    try:
        response = requests.get(url, headers=headers())
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求详情页出错', url)
        return None

def parse_page_detail(html,url):
    soup = BeautifulSoup(html,'lxml')
    title = soup.select('title')[0].get_text()
    print(title)
    images_pattern = re.compile('BASE_DATA.galleryInfo =(.*?)</script>',re.S)
    result = re.search(images_pattern, html)
    if result:
        data = result.group(1)
        gallery = data[data.index('JSON.parse("')+12:data.index('siblingList')-8]
        images = json.loads(json.loads('"' + gallery + '"'))
        sub_images = images["sub_images"]
        images_url = [item['url'] for item in sub_images]
        for image in images_url:
            download_image(image)
        return {
                'title':title,
                'url':url,
                'images':images_url
        }

def save2mongo(result):
    if db[MONGO_TABLE].insert(result):
        print('成功存储到MongoDB',result['title'])
        return True
    return False

def download_image(url):
    print('正在下载图片',url)
    try:
        response = requests.get(url, headers=headers())
        if response.status_code == 200:
            save_image(response.content)
        return None
    except RequestException:
        print('下载图片出错', url)
        return None

def save_image(content):
    file_path = '{0}/{1}.{2}'.format(os.getcwd(),md5(content).hexdigest(),'jpg')
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(content)
            f.close()

def main(offset):

    html = get_page_index(offset,KEYWORD)
    for url in parse_page_index(html):
        html = get_page_detail(url)
        if html:
            result = parse_page_detail(html,url)
            if result:
                save2mongo(result)


if __name__ == '__main__':
    groups = [x*20 for x in range(GROUP_START,GROUP_END)]
    pool = Pool()
    pool.map(main,groups)

