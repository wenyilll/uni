import requests
from bs4 import BeautifulSoup
import time
import random
import os
import re

# 配置部分
BOOK_ID = "94998910"
BASE_URL = "https://www.qushucheng.com"
# 根据你的链接结构，目录页通常是这个
INDEX_URL = f"{BASE_URL}/book_{BOOK_ID}/" 
OUTPUT_FILE = f"novel_{BOOK_ID}.txt"

# 设置请求头，伪装成浏览器，防止被反爬虫拦截
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def get_chapter_links(index_url):
    """
    终极通用版：直接搜索页面所有链接，通过正则匹配章节 URL
    """
    print(f"正在获取目录: {index_url}")
    try:
        response = requests.get(index_url, headers=HEADERS, timeout=15)
        response.encoding = 'utf-8' 
        
        if response.status_code != 200:
            print(f"无法访问目录页，状态码: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        
        chapters = []
        seen_urls = set() # 用于去重
        
        # 1. 获取页面上所有的 a 标签
        all_links = soup.find_all('a', href=True)
        print(f"页面共扫描到 {len(all_links)} 个链接，正在筛选...")

        for link in all_links:
            href = link['href']
            title = link.get_text().strip()
            
            # 2. 核心筛选逻辑：
            # 趣书城的章节链接通常是 "365603100.html" 这种纯数字+html 的格式
            # 我们用正则检查：href 中包含数字 且 以 .html 结尾
            if '.html' in href and re.search(r'\d', href):
                
                # 排除掉一些非章节的干扰链接（比如“加入书架”、“投推荐票”等可能也是html结尾）
                # 章节名通常比较长，或者你可以根据 title 过滤
                if not title or title in ["登录", "注册", "首页", "书架"]:
                    continue

                # 3. 拼接完整 URL
                if not href.startswith('http'):
                    # 处理相对路径
                    if href.startswith('/'):
                        full_url = BASE_URL + href
                    else:
                        # 这是一个关键点：如果 href 是 "123.html"，它需要拼接到 book_id 后面
                        # 也就是 https://www.qushucheng.com/book_94998910/123.html
                        full_url = f"{BASE_URL}/book_{BOOK_ID}/{href}"
                else:
                    full_url = href
                
                # 4. 去重并保存
                # 很多网站会在顶部放“最新章节”列表，底部放“所有章节”，导致链接重复
                if full_url not in seen_urls:
                    chapters.append((title, full_url))
                    seen_urls.add(full_url)
        
        # 排序修正（可选）：
        # 如果下载顺序乱了（比如最新章节跑到了最前面），可以在这里按 URL 里的数字大小排个序
        # chapters.sort(key=lambda x: int(re.search(r'(\d+)\.html', x[1]).group(1)) if re.search(r'(\d+)\.html', x[1]) else 0)
        
        if chapters:
            print(f"筛选成功！共找到 {len(chapters)} 章。")
            # 打印前3个和最后3个，帮你确认是不是找对了
            print(f"首章示例: {chapters[0]}")
            print(f"末章示例: {chapters[-1]}")
        else:
            print("【严重错误】依然没有找到章节链接。可能原因：")
            print("1. 网站有反爬验证（Cloudflare等），返回了假页面。")
            print("2. 章节列表是 JavaScript 动态加载的（Requests 抓不到）。")
            
        return chapters

    except Exception as e:
        print(f"获取目录失败: {e}")
        return []

def get_chapter_content(chapter_url):
    """
    获取单个章节的正文内容
    """
    try:
        response = requests.get(chapter_url, headers=HEADERS, timeout=10)
        response.encoding = 'utf-8' 
        
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 定位正文内容
        # 趣书城及类似网站的正文通常在 id="content" 的 div 中
        content_div = soup.find('div', id='content')
        
        if content_div:
            # 处理换行，将 <br> 转换为换行符
            text = content_div.get_text(separator='\n\n')
            # 去除广告或多余的 js 代码文本（如果有）
            return text.strip()
        else:
            print(f"在 {chapter_url} 未找到正文内容")
            return None

    except Exception as e:
        print(f"获取章节失败 {chapter_url}: {e}")
        return None

def main():
    # 1. 获取所有章节链接
    chapters = get_chapter_links(INDEX_URL)
    
    if not chapters:
        print("未找到章节，请检查 URL 或网站结构。")
        return

    print(f"共发现 {len(chapters)} 章。准备开始下载...")

    # 2. 准备文件
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        
        # 3. 遍历下载
        for index, (title, url) in enumerate(chapters):
            print(f"正在下载 ({index+1}/{len(chapters)}): {title}")
            
            content = get_chapter_content(url)
            
            if content:
                # 写入标题和正文
                f.write(f"\n\n{'='*20}\n")
                f.write(f"{title}\n")
                f.write(f"{'='*20}\n\n")
                f.write(content)
                f.flush() # 确保实时写入硬盘
            else:
                f.write(f"\n\n[错误] 无法获取章节内容: {title}\n\n")

            # !!! 重要 !!!
            # 添加延时，防止请求过快被网站封 IP
            time.sleep(random.uniform(1, 3))

    print(f"下载完成！文件已保存为: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()