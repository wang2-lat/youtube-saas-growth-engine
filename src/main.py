#!/usr/bin/env python3
#!/usr/bin/env python3
import click
import sqlite3
import json
import time
import re
from datetime import datetime
from pathlib import Path
import httpx
from typing import List, Dict, Optional

DB_PATH = Path.home() / ".youtube_pain_harvester.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pain_points
                 (id INTEGER PRIMARY KEY, source TEXT, content TEXT, 
                  keywords TEXT, timestamp TEXT, processed INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS video_ideas
                 (id INTEGER PRIMARY KEY, title TEXT, description TEXT, 
                  keywords TEXT, pain_point_id INTEGER, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS rankings
                 (id INTEGER PRIMARY KEY, video_id TEXT, keyword TEXT, 
                  platform TEXT, rank INTEGER, checked_at TEXT)''')
    conn.commit()
    conn.close()

def save_pain_point(source: str, content: str, keywords: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO pain_points (source, content, keywords, timestamp) VALUES (?, ?, ?, ?)",
              (source, content, keywords, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_unprocessed_pain_points():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, content, keywords FROM pain_points WHERE processed = 0")
    results = c.fetchall()
    conn.close()
    return results

def mark_processed(pain_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE pain_points SET processed = 1 WHERE id = ?", (pain_id,))
    conn.commit()
    conn.close()

def save_video_idea(title: str, description: str, keywords: str, pain_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO video_ideas (title, description, keywords, pain_point_id, created_at) VALUES (?, ?, ?, ?, ?)",
              (title, description, keywords, pain_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def save_ranking(video_id: str, keyword: str, platform: str, rank: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO rankings (video_id, keyword, platform, rank, checked_at) VALUES (?, ?, ?, ?, ?)",
              (video_id, keyword, platform, rank, datetime.now().isoformat()))
    conn.commit()
    conn.close()

@click.group()
def cli():
    """YouTube痛点收割机 - 自动化内容创意生成"""
    init_db()

@cli.command()
@click.option('--subreddit', default='learnprogramming', help='目标subreddit')
@click.option('--limit', default=50, help='抓取帖子数量')
def scrape_reddit(subreddit: str, limit: int):
    """抓取Reddit社区问题"""
    try:
        client = httpx.Client(timeout=30.0)
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; PainHarvester/1.0)'}
        
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        
        count = 0
        for post in data['data']['children']:
            p = post['data']
            if p.get('selftext') and len(p['selftext']) > 50:
                title = p['title']
                body = p['selftext'][:500]
                content = f"{title}\n{body}"
                
                keywords = extract_keywords(content)
                save_pain_point(f"reddit/{subreddit}", content, keywords)
                count += 1
        
        click.echo(f"✓ 从 r/{subreddit} 收集了 {count} 个痛点")
    except Exception as e:
        click.echo(f"✗ Reddit抓取失败: {e}", err=True)

@cli.command()
@click.option('--video-id', required=True, help='YouTube视频ID')
@click.option('--limit', default=100, help='评论数量')
def scrape_youtube_comments(video_id: str, limit: int):
    """分析YouTube评论找内容空白"""
    try:
        client = httpx.Client(timeout=30.0)
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        resp = client.get(url, headers=headers)
        text = resp.text
        
        pattern = r'"commentRenderer":\{"comment":\{"runs":\[\{"text":"([^"]+)"'
        comments = re.findall(pattern, text)[:limit]
        
        count = 0
        for comment in comments:
            if len(comment) > 30 and ('?' in comment or 'how' in comment.lower()):
                keywords = extract_keywords(comment)
                save_pain_point(f"youtube/{video_id}", comment, keywords)
                count += 1
        
        click.echo(f"✓ 从视频 {video_id} 提取了 {count} 个问题")
    except Exception as e:
        click.echo(f"✗ YouTube评论抓取失败: {e}", err=True)

@cli.command()
@click.option('--file', type=click.Path(exists=True), required=True, help='客户支持记录JSON文件')
def import_support_tickets(file: str):
    """从客户支持记录提取痛点"""
    try:
        with open(file, 'r', encoding='utf-8') as f:
            tickets = json.load(f)
        
        count = 0
        for ticket in tickets:
            content = ticket.get('description', '') or ticket.get('message', '')
            if len(content) > 30:
                keywords = extract_keywords(content)
                save_pain_point("support_ticket", content, keywords)
                count += 1
        
        click.echo(f"✓ 导入了 {count} 个支持工单")
    except Exception as e:
        click.echo(f"✗ 导入失败: {e}", err=True)

@cli.command()
def generate_ideas():
    """用AI生成视频创意和SEO元数据"""
    pain_points = get_unprocessed_pain_points()
    
    if not pain_points:
        click.echo("没有未处理的痛点")
        return
    
    for pain_id, content, keywords in pain_points:
        title = generate_seo_title(content, keywords)
        description = generate_seo_description(content, keywords)
        
        save_video_idea(title, description, keywords, pain_id)
        mark_processed(pain_id)
        
        click.echo(f"\n标题: {title}")
        click.echo(f"关键词: {keywords}")
        click.echo("-" * 60)
    
    click.echo(f"\n✓ 生成了 {len(pain_points)} 个视频创意")

@cli.command()
@click.option('--video-id', required=True, help='YouTube视频ID')
@click.option('--keyword', required=True, help='目标关键词')
def track_ranking(video_id: str, keyword: str):
    """追踪视频搜索排名"""
    try:
        # YouTube搜索
        yt_rank = check_youtube_ranking(video_id, keyword)
        if yt_rank:
            save_ranking(video_id, keyword, 'youtube', yt_rank)
            click.echo(f"YouTube排名: #{yt_rank}")
        else:
            click.echo("YouTube: 未进入前50")
        
        # Google搜索
        google_rank = check_google_ranking(video_id, keyword)
        if google_rank:
            save_ranking(video_id, keyword, 'google', google_rank)
            click.echo(f"Google排名: #{google_rank}")
        else:
            click.echo("Google: 未进入前50")
            
    except Exception as e:
        click.echo(f"✗ 排名追踪失败: {e}", err=True)

@cli.command()
def list_ideas():
    """列出所有视频创意"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT title, keywords, created_at FROM video_ideas ORDER BY created_at DESC LIMIT 20")
    ideas = c.fetchall()
    conn.close()
    
    if not ideas:
        click.echo("暂无视频创意")
        return
    
    for title, keywords, created in ideas:
        click.echo(f"\n{title}")
        click.echo(f"关键词: {keywords}")
        click.echo(f"创建时间: {created}")
        click.echo("-" * 60)

def extract_keywords(text: str) -> str:
    """提取关键词（简化版）"""
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    common = ['that', 'this', 'with', 'from', 'have', 'what', 'when', 'where', 'which', 'their']
    keywords = [w for w in words if w not in common]
    return ', '.join(list(dict.fromkeys(keywords))[:5])

def generate_seo_title(content: str, keywords: str) -> str:
    """生成SEO优化标题"""
    first_keyword = keywords.split(',')[0].strip().title()
    templates = [
        f"How to {first_keyword}: Complete Guide for Beginners",
        f"{first_keyword} Tutorial: Step-by-Step Walkthrough",
        f"Master {first_keyword} in 10 Minutes",
        f"{first_keyword} Explained: Everything You Need to Know"
    ]
    return templates[hash(content) % len(templates)]

def generate_seo_description(content: str, keywords: str) -> str:
    """生成SEO优化描述"""
    kw_list = keywords.split(',')[:3]
    kw_text = ', '.join([k.strip() for k in kw_list])
    
    return f"""Learn {kw_text} in this comprehensive tutorial. 

In this video, you'll discover:
• Step-by-step instructions
• Common mistakes to avoid
• Best practices and tips
• Real-world examples

Perfect for beginners and intermediate users. Subscribe for more tutorials!

Timestamps:
0:00 Introduction
1:30 Getting Started
5:00 Advanced Techniques
8:30 Conclusion

#tutorial #{kw_list[0].strip().replace(' ', '')}"""

def check_youtube_ranking(video_id: str, keyword: str) -> Optional[int]:
    """检查YouTube排名"""
    try:
        client = httpx.Client(timeout=30.0)
        url = f"https://www.youtube.com/results?search_query={keyword.replace(' ', '+')}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        resp = client.get(url, headers=headers)
        text = resp.text
        
        pattern = r'"videoId":"([^"]+)"'
        video_ids = re.findall(pattern, text)[:50]
        
        for i, vid in enumerate(video_ids, 1):
            if vid == video_id:
                return i
        return None
    except:
        return None

def check_google_ranking(video_id: str, keyword: str) -> Optional[int]:
    """检查Google排名"""
    try:
        client = httpx.Client(timeout=30.0)
        url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        resp = client.get(url, headers=headers)
        text = resp.text
        
        if f"youtube.com/watch?v={video_id}" in text:
            matches = re.findall(r'youtube\.com/watch\?v=([^"&]+)', text)
            for i, vid in enumerate(matches[:50], 1):
                if vid == video_id:
                    return i
        return None
    except:
        return None

if __name__ == '__main__':
    cli()