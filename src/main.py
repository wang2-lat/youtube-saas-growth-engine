#!/usr/bin/env python3
#!/usr/bin/env python3
import click
import sqlite3
import json
import re
from datetime import datetime
from pathlib import Path
import httpx
from typing import List, Dict, Optional

DB_PATH = Path.home() / ".youtube_saas_growth.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pain_points
                 (id INTEGER PRIMARY KEY, source TEXT, content TEXT, 
                  keywords TEXT, created_at TEXT, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS videos
                 (id INTEGER PRIMARY KEY, title TEXT, description TEXT,
                  keywords TEXT, pain_point_id INTEGER, url TEXT,
                  views INTEGER, search_traffic_pct REAL, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS content_calendar
                 (id INTEGER PRIMARY KEY, topic TEXT, keywords TEXT,
                  priority INTEGER, scheduled_date TEXT, status TEXT)''')
    conn.commit()
    conn.close()

@click.group()
def cli():
    """YouTube SaaS增长引擎 - 将客户痛点转化为搜索资产"""
    init_db()

@cli.command()
@click.option('--source', type=click.Choice(['support', 'email', 'community', 'youtube']), required=True)
@click.option('--api-key', envvar='API_KEY', help='API密钥（支持环境变量）')
@click.argument('query', required=False)
def collect(source, api_key, query):
    """收集客户痛点"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    pain_points = []
    
    if source == 'support':
        # 模拟Zendesk/Intercom API调用
        if not api_key:
            click.echo("错误: 需要API密钥", err=True)
            return
        try:
            resp = httpx.get(
                f"https://api.example.com/tickets",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"status": "solved", "limit": 50},
                timeout=10
            )
            if resp.status_code == 200:
                tickets = resp.json().get('tickets', [])
                for t in tickets:
                    pain_points.append({
                        'content': f"{t.get('subject', '')} - {t.get('description', '')}",
                        'source': 'support_ticket'
                    })
        except Exception as e:
            click.echo(f"API调用失败: {e}", err=True)
            
    elif source == 'youtube':
        # YouTube评论抓取（使用YouTube Data API v3）
        if not api_key:
            click.echo("错误: 需要YouTube API密钥", err=True)
            return
        video_id = query or click.prompt("输入视频ID")
        try:
            resp = httpx.get(
                "https://www.googleapis.com/youtube/v3/commentThreads",
                params={
                    "part": "snippet",
                    "videoId": video_id,
                    "key": api_key,
                    "maxResults": 100
                },
                timeout=10
            )
            if resp.status_code == 200:
                items = resp.json().get('items', [])
                for item in items:
                    comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                    if '?' in comment or any(w in comment.lower() for w in ['how', 'why', 'help', 'issue', 'problem']):
                        pain_points.append({'content': comment, 'source': 'youtube_comment'})
        except Exception as e:
            click.echo(f"YouTube API错误: {e}", err=True)
            
    elif source == 'community':
        # Reddit/论坛抓取
        subreddit = query or click.prompt("输入subreddit名称")
        try:
            resp = httpx.get(
                f"https://www.reddit.com/r/{subreddit}/search.json",
                params={"q": "how to", "sort": "relevance", "limit": 50},
                headers={"User-Agent": "YT-SaaS-Bot/1.0"},
                timeout=10
            )
            if resp.status_code == 200:
                posts = resp.json().get('data', {}).get('children', [])
                for post in posts:
                    data = post['data']
                    pain_points.append({
                        'content': f"{data['title']} - {data.get('selftext', '')}",
                        'source': f'reddit_{subreddit}'
                    })
        except Exception as e:
            click.echo(f"Reddit抓取失败: {e}", err=True)
            
    elif source == 'email':
        # 入职邮件分析（模拟IMAP）
        click.echo("提示: 实际使用需配置IMAP，这里使用示例数据")
        pain_points = [
            {'content': 'How do I integrate with Stripe?', 'source': 'onboarding_email'},
            {'content': 'Cannot find the API documentation', 'source': 'onboarding_email'}
        ]
    
    # 提取关键词并保存
    for pp in pain_points:
        keywords = extract_keywords(pp['content'])
        c.execute(
            "INSERT INTO pain_points (source, content, keywords, created_at, status) VALUES (?, ?, ?, ?, ?)",
            (pp['source'], pp['content'], json.dumps(keywords), datetime.now().isoformat(), 'new')
        )
    
    conn.commit()
    conn.close()
    click.echo(f"✓ 收集了 {len(pain_points)} 个痛点")

def extract_keywords(text: str) -> List[str]:
    """提取长尾关键词"""
    text = text.lower()
    patterns = [
        r'how to \w+(?:\s+\w+){0,4}',
        r'why (?:does|is|are) \w+(?:\s+\w+){0,3}',
        r'what is \w+(?:\s+\w+){0,3}',
        r'\w+(?:\s+\w+){0,2} not working',
        r'error:?\s+\w+(?:\s+\w+){0,3}'
    ]
    keywords = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        keywords.extend(matches)
    
    words = re.findall(r'\b[a-z]{4,}\b', text)
    tech_words = [w for w in words if w in ['api', 'integration', 'webhook', 'auth', 'oauth', 'stripe', 'payment']]
    keywords.extend(tech_words)
    
    return list(set(keywords))[:10]

@cli.command()
@click.option('--limit', default=10, help='生成数量')
def generate_calendar(limit):
    """从痛点自动生成内容日历"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT id, content, keywords FROM pain_points WHERE status='new' LIMIT ?", (limit,))
    pain_points = c.fetchall()
    
    for pp_id, content, keywords_json in pain_points:
        keywords = json.loads(keywords_json)
        title = content[:100].strip()
        if '?' in title:
            title = title.split('?')[0] + '?'
        
        priority = len(keywords) * 10
        
        c.execute(
            "INSERT INTO content_calendar (topic, keywords, priority, scheduled_date, status) VALUES (?, ?, ?, ?, ?)",
            (title, keywords_json, priority, datetime.now().isoformat(), 'planned')
        )
        c.execute("UPDATE pain_points SET status='scheduled' WHERE id=?", (pp_id,))
    
    conn.commit()
    conn.close()
    click.echo(f"✓ 生成了 {len(pain_points)} 个内容计划")

@cli.command()
@click.argument('pain_point_id', type=int)
def create_tutorial(pain_point_id):
    """为痛点创建教程脚本（SEO优化）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT content, keywords FROM pain_points WHERE id=?", (pain_point_id,))
    row = c.fetchone()
    if not row:
        click.echo("痛点不存在", err=True)
        return
    
    content, keywords_json = row
    keywords = json.loads(keywords_json)
    
    # 生成SEO优化的标题和描述
    main_keyword = keywords[0] if keywords else "tutorial"
    title = f"{main_keyword.title()} - Step by Step Guide"
    
    description = f"""Learn {main_keyword} in this detailed tutorial.

🎯 What you'll learn:
- {main_keyword}
- Common issues and solutions
- Best practices

⏱️ Chapters:
0:00 Introduction
0:30 Problem overview
2:00 Solution walkthrough
5:00 Testing and verification
7:00 Conclusion

🔗 Resources mentioned:
- Documentation: [link]
- Code examples: [link]

Keywords: {', '.join(keywords[:5])}

#tutorial #{main_keyword.replace(' ', '')} #howto
"""
    
    click.echo(f"\n标题: {title}")
    click.echo(f"\n描述:\n{description}")
    click.echo(f"\n关键词: {', '.join(keywords)}")
    click.echo("\n提示: 使用客户原话，每个视频解决一个具体问题")
    
    conn.close()

@cli.command()
@click.argument('video_id')
@click.option('--url', required=True)
@click.option('--pain-point-id', type=int)
def track_video(video_id, url, pain_point_id):
    """追踪视频表现（搜索流量）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 模拟YouTube Analytics API调用
    try:
        # 实际使用需要OAuth2认证
        analytics_data = {
            'views': 150,
            'search_traffic_pct': 0.63,
            'google_traffic_pct': 0.26
        }
        
        c.execute(
            "INSERT INTO videos (title, url, pain_point_id, views, search_traffic_pct, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (video_id, url, pain_point_id, analytics_data['views'], 
             analytics_data['search_traffic_pct'], datetime.now().isoformat())
        )
        conn.commit()
        
        click.echo(f"✓ 视频已追踪")
        click.echo(f"  浏览量: {analytics_data['views']}")
        click.echo(f"  搜索流量: {analytics_data['search_traffic_pct']*100:.0f}%")
        click.echo(f"  Google流量: {analytics_data['google_traffic_pct']*100:.0f}%")
        
        if analytics_data['search_traffic_pct'] > 0.5:
            click.echo("  ✓ 搜索流量占比健康（>50%）")
        
    except Exception as e:
        click.echo(f"追踪失败: {e}", err=True)
    finally:
        conn.close()

@cli.command()
def stats():
    """显示统计数据"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM pain_points")
    total_pain_points = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM videos")
    total_videos = c.fetchone()[0]
    
    c.execute("SELECT AVG(views), AVG(search_traffic_pct) FROM videos")
    avg_stats = c.fetchone()
    
    c.execute("SELECT COUNT(*) FROM content_calendar WHERE status='planned'")
    planned_content = c.fetchone()[0]
    
    click.echo(f"\n📊 统计数据")
    click.echo(f"  痛点收集: {total_pain_points}")
    click.echo(f"  已发布视频: {total_videos}")
    if avg_stats[0]:
        click.echo(f"  平均浏览量: {avg_stats[0]:.0f}")
        click.echo(f"  平均搜索流量: {avg_stats[1]*100:.0f}%")
    click.echo(f"  计划内容: {planned_content}")
    
    conn.close()

@cli.command()
@click.option('--format', type=click.Choice(['json', 'csv']), default='json')
def export(format):
    """导出数据"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT * FROM pain_points")
    rows = c.fetchall()
    
    if format == 'json':
        data = [{'id': r[0], 'source': r[1], 'content': r[2], 'keywords': r[3]} for r in rows]
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        click.echo("id,source,content,keywords")
        for r in rows:
            click.echo(f"{r[0]},{r[1]},\"{r[2]}\",\"{r[3]}\"")
    
    conn.close()

if __name__ == '__main__':
    cli()