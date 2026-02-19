# youtube_pain_harvester

[English](#english) | [中文](#chinese)

---

## <a id="english"></a>English

### Overview
从多渠道自动收集客户痛点并生成YouTube视频内容建议的工具

### Features
- 抓取Reddit/Facebook/Discord等社区的高频问题
- 分析YouTube评论区找内容空白
- 从客户支持记录提取痛点关键词
- 生成SEO优化的视频标题和描述
- 追踪视频搜索排名（Google+YouTube）
- AI引用优化（章节标记、转录文本结构化）

### Installation
```bash
pip install -r requirements.txt
python src/main.py --help
```

### Tech Stack
Python, requests/httpx（API调用）, praw（Reddit API）, yt-dlp（YouTube数据）, openai/anthropic（痛点分析）, sqlite（本地存储）

---

## <a id="chinese"></a>中文

### 概述
从多渠道自动收集客户痛点并生成YouTube视频内容建议的工具

### 功能特性
- 抓取Reddit/Facebook/Discord等社区的高频问题
- 分析YouTube评论区找内容空白
- 从客户支持记录提取痛点关键词
- 生成SEO优化的视频标题和描述
- 追踪视频搜索排名（Google+YouTube）
- AI引用优化（章节标记、转录文本结构化）

### 安装使用
```bash
pip install -r requirements.txt
python src/main.py --help
```

### 技术栈
Python, requests/httpx（API调用）, praw（Reddit API）, yt-dlp（YouTube数据）, openai/anthropic（痛点分析）, sqlite（本地存储）
