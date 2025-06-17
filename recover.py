#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
from bs4 import BeautifulSoup
from datetime import datetime
import html2text

def sanitize_filename(title):
    """将标题转换为安全的文件名"""
    # 移除或替换不安全的字符
    filename = re.sub(r'[<>:"/\\|?*]', '', title)
    # 移除多余的空格和换行符
    filename = re.sub(r'\s+', ' ', filename).strip()
    # 限制长度
    if len(filename) > 100:
        filename = filename[:100]
    return filename

def is_article_page(html_content):
    """判断是否为文章页面"""
    # 检查是否包含文章特有的元素
    if '<article class="container post-content"' in html_content:
        return True
    return False

def extract_title(soup):
    """提取文章标题"""
    # 优先从og:title中提取
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        return og_title.get('content').strip()
    
    # 从页面标题中提取
    title_tag = soup.find('title')
    if title_tag:
        title_text = title_tag.get_text().strip()
        # 移除网站名称部分
        if ' | ' in title_text:
            title_text = title_text.split(' | ')[0]
        return title_text
    
    return "无标题"

def extract_dates(soup):
    """提取创建和更新日期"""
    created_date = None
    updated_date = None
    
    # 从meta标签中提取
    created_meta = soup.find('meta', property='article:published_time')
    updated_meta = soup.find('meta', property='article:modified_time')
    
    if created_meta and created_meta.get('content'):
        try:
            created_date = datetime.fromisoformat(created_meta.get('content').replace('Z', '+00:00'))
        except:
            pass
    
    if updated_meta and updated_meta.get('content'):
        try:
            updated_date = datetime.fromisoformat(updated_meta.get('content').replace('Z', '+00:00'))
        except:
            pass
    
    # 如果meta中没有，尝试从页面元素中提取
    if not created_date:
        created_elem = soup.find('time', class_='post-meta-date-created')
        if created_elem and created_elem.get('datetime'):
            try:
                created_date = datetime.fromisoformat(created_elem.get('datetime').replace('Z', '+00:00'))
            except:
                pass
    
    if not updated_date:
        updated_elem = soup.find('time', class_='post-meta-date-updated')
        if updated_elem and updated_elem.get('datetime'):
            try:
                updated_date = datetime.fromisoformat(updated_elem.get('datetime').replace('Z', '+00:00'))
            except:
                pass
    
    return created_date, updated_date

def extract_categories(soup):
    """提取分类"""
    categories = []
    
    # 从meta标签中提取
    category_meta = soup.find('meta', property='article:section')
    if category_meta and category_meta.get('content'):
        categories.append(category_meta.get('content'))
    
    # 从页面元素中提取
    category_links = soup.find_all('a', class_='post-meta-categories')
    for link in category_links:
        category_text = link.get_text().strip()
        if category_text and category_text not in categories:
            categories.append(category_text)
    
    return categories

def extract_tags(soup):
    """提取标签"""
    tags = []
    
    # 从meta标签中提取
    tag_meta = soup.find('meta', property='article:tag')
    if tag_meta and tag_meta.get('content'):
        tags.append(tag_meta.get('content'))
    
    # 从页面元素中提取
    tag_links = soup.find_all('a', class_='post-meta__tags')
    for link in tag_links:
        tag_text = link.get_text().strip()
        if tag_text and tag_text not in tags:
            tags.append(tag_text)
    
    return tags

def extract_content(soup):
    """提取文章正文内容"""
    # 找到文章容器
    article_container = soup.find('article', class_='container post-content')
    if not article_container:
        return ""
    
    # 初始化html2text转换器
    converter = html2text.HTML2Text()
    converter.ignore_images = False
    converter.ignore_links = False
    converter.body_width = 0
    
    # 只提取article内的正文内容，排除其他元素
    content_html = ""
    
    # 遍历article内的所有子元素
    for child in article_container.children:
        if child.name:  # 确保是HTML元素
            # 只保留正文内容，排除版权信息、标签、分页等
            if child.name not in ['div', 'nav'] or not child.get('class'):
                content_html += str(child)
            elif child.name == 'div':
                # 检查是否是版权信息、标签、分页等非正文内容
                classes = child.get('class', [])
                if not any(cls in ['post-copyright', 'tag_share', 'pagination-post'] for cls in classes):
                    content_html += str(child)
    
    # 如果没有找到内容，尝试直接提取p标签内容
    if not content_html.strip():
        paragraphs = article_container.find_all('p')
        for p in paragraphs:
            content_html += str(p)
    
    # 转换为Markdown
    content_md = converter.handle(content_html)
    
    return content_md.strip()

def process_html_file(html_path, posts_output, images_output, html_root):
    """处理单个HTML文件"""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # 判断是否为文章页面
        if not is_article_page(html_content):
            return False
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 提取信息
        title = extract_title(soup)
        created_date, updated_date = extract_dates(soup)
        categories = extract_categories(soup)
        tags = extract_tags(soup)
        content = extract_content(soup)
        
        # 生成安全的文件名
        filename = sanitize_filename(title)
        if not filename:
            filename = "无标题"
        
        # 处理重复文件名
        counter = 1
        original_filename = filename
        while os.path.exists(os.path.join(posts_output, f"{filename}.md")):
            filename = f"{original_filename}_{counter}"
            counter += 1
        
        # 写入Markdown文件
        md_path = os.path.join(posts_output, f"{filename}.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            # 写入front-matter
            f.write("---\n")
            f.write(f"title: \"{title}\"\n")
            
            if created_date:
                f.write(f"date: {created_date.strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            if updated_date and updated_date != created_date:
                f.write(f"updated: {updated_date.strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            if categories:
                f.write(f"categorie: {categories[0]}\n")
            
            if tags:
                f.write(f"tag: {tags[0]}\n")
            
            f.write("---\n\n")
            
            # 写入正文
            f.write(content)
        
        # 复制图片资源
        copy_resources(html_path, html_root, images_output)
        
        print(f"[成功] {html_path} → {md_path}")
        return True
        
    except Exception as e:
        print(f"[错误] 处理 {html_path} 时出错: {e}")
        return False

def copy_resources(html_path, html_root, images_output):
    """复制HTML中的图片资源"""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        for img in soup.find_all('img'):
            src = img.get('src')
            if not src:
                continue
            
            # 处理相对路径 - 使用与test.py相同的逻辑
            if src.startswith('/'):
                # 绝对路径，从根目录开始
                resource_path = os.path.join(html_root, src[1:])
            else:
                # 相对路径，从当前HTML文件所在目录开始
                resource_path = os.path.join(os.path.dirname(html_path), src)
            
            # 解析路径，处理../等相对路径
            resource_path = os.path.abspath(resource_path)
            
            if os.path.exists(resource_path):
                # 复制到images目录，保持相对路径结构
                rel_path = os.path.relpath(resource_path, html_root)
                target = os.path.join(images_output, rel_path)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(resource_path, target)
                print(f"[图片复制] {resource_path} → {target}")
            else:
                print(f"[警告] 未找到图片: {resource_path}")
                
    except Exception as e:
        print(f"[错误] 复制资源时出错: {e}")

def copy_all_images(static_root, images_output):
    """直接复制静态博客根目录下的images整个目录到目标images目录"""
    src_images = os.path.join(static_root, 'images')
    if os.path.exists(src_images):
        if os.path.exists(images_output):
            shutil.rmtree(images_output)
        shutil.copytree(src_images, images_output)
        print(f"[图片目录复制] {src_images} → {images_output}")
    else:
        print(f"[警告] 未找到图片目录: {src_images}")

def main():
    """主函数"""
    print("=== Hexo文章恢复工具 ===")
    
    # 获取用户输入
    static_root = input("请输入静态博客根目录路径: ").strip()
    if not static_root:
        static_root = r"D:\backup\lan1oc.github.io"
    
    blog_source = input("请输入博客source目录路径: ").strip()
    if not blog_source:
        blog_source = r"D:\blog\source"
    
    # 设置输出目录
    posts_output = os.path.join(blog_source, "_posts")
    images_output = os.path.join(blog_source, "images")
    
    # 确保输出目录存在
    os.makedirs(posts_output, exist_ok=True)
    os.makedirs(images_output, exist_ok=True)
    
    # 统计信息
    total_files = 0
    processed_files = 0
    
    # 遍历所有年份目录
    for year in ['2023', '2024', '2025']:
        year_dir = os.path.join(static_root, year)
        if not os.path.exists(year_dir):
            continue
        
        print(f"\n处理 {year} 年文章...")
        
        # 递归查找所有index.html文件
        for root, dirs, files in os.walk(year_dir):
            if 'index.html' in files:
                total_files += 1
                html_path = os.path.join(root, 'index.html')
                
                if process_html_file(html_path, posts_output, images_output, static_root):
                    processed_files += 1
    
    # 输出统计信息
    print(f"\n=== 处理完成 ===")
    print(f"总文件数: {total_files}")
    print(f"成功处理: {processed_files}")
    print(f"文章输出目录: {posts_output}")
    print(f"图片输出目录: {images_output}")

    # 复制所有图片
    print("\n复制所有图片资源...")
    copy_all_images(static_root, images_output)

if __name__ == "__main__":
    main()
