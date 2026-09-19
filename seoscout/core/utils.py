"""
工具函数

提供通用的辅助功能
"""

import os
import json
import re
import time
from typing import List, Dict, Any
from urllib.parse import urlparse


def ensure_dir(path: str):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def load_json(file_path: str) -> Dict:
    """加载 JSON 文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: Any, file_path: str, indent: int = 2):
    """保存 JSON 文件"""
    ensure_dir(os.path.dirname(file_path))
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def format_duration(seconds: int) -> str:
    """
    格式化时长

    Args:
        seconds: 秒数

    Returns:
        格式化的时长字符串 (例如: "10:30", "1:05:30")
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def extract_domain(url: str) -> str:
    """
    提取域名

    Args:
        url: URL 字符串

    Returns:
        域名
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except:
        return ""


def is_blocked_domain(url: str, blocked_domains: set) -> bool:
    """
    检查 URL 是否在屏蔽列表中

    Args:
        url: URL 字符串
        blocked_domains: 屏蔽域名集合

    Returns:
        是否被屏蔽
    """
    domain = extract_domain(url)
    return any(blocked in domain for blocked in blocked_domains)


def is_topic_match(text: str, topic_name: str) -> bool:
    """
    判断文本是否命中主题名（用于把主题相关的结果排在前面）。

    按“整词 + 顺序相邻”匹配主题短语，词间容忍分隔符差异，因此
    "Slime Out Fish - Roblox" 与 ".../Slime-Out-Fish" 都算命中。

    刻意不做「去掉所有分隔符后的子串包含」匹配：那会把
    "FritzSlimeOutFishTreatment" 这类相邻拼接也判为命中，放大误报。

    注意：本函数只做词面匹配，无法区分同名词条的语义。例如产品标题
    "Fritz Slime Out fish treatment" 字面上就包含 "Slime Out fish"，仍会命中；
    该歧义由生成阶段的主题约束（templates/generate.md）兜底，而不是靠这里。

    Args:
        text: 待检查文本（标题 / 摘要 / URL）
        topic_name: 主题名

    Returns:
        是否命中
    """
    if not text or not topic_name:
        return False

    words = [re.escape(word) for word in topic_name.lower().split()]
    if not words:
        return False

    pattern = r'\b' + r'[\s\-_.]*'.join(words) + r'\b'
    return re.search(pattern, text.lower()) is not None


def load_keywords_from_json(json_file: str) -> List[Dict]:
    """
    Load keywords from a JSON file.

    Supports two formats:
    1. Categorized: {"categories": [{"category": "Guide", "keywords": ["kw1", "kw2"]}, ...]}
    2. Flat list:   {"topic_name": "...", "keywords": ["kw1", "kw2"]}

    Returns:
        List of dicts: [{"keyword": "kw1", "category": "Guide"}, ...]
        For flat format, category is "".
    """
    data = load_json(json_file)
    results = []

    # Categorized format (preferred)
    if "categories" in data and isinstance(data["categories"], list):
        for cat in data["categories"]:
            category = cat.get("category", "")
            for kw in cat.get("keywords", []):
                if isinstance(kw, str) and kw.strip():
                    results.append({"keyword": kw.strip(), "category": category})
        if results:
            return results

    # Flat keyword list
    if "keywords" in data and isinstance(data["keywords"], list):
        for kw in data["keywords"]:
            if isinstance(kw, str) and kw.strip():
                results.append({"keyword": kw.strip(), "category": ""})

    return results


def load_languages_from_json(json_file: str) -> List[str]:
    """
    Load target languages from a keywords JSON file.

    Looks for a top-level "languages" array, e.g.:
        {"languages": ["es", "pt", "de", "fr"]}

    Returns:
        List of language codes, or empty list if not specified.
    """
    data = load_json(json_file)
    langs = data.get("languages", [])
    if isinstance(langs, list):
        return [l.strip() for l in langs if isinstance(l, str) and l.strip()]
    return []


class ProgressBar:
    """简单的进度条"""

    def __init__(self, total: int, prefix: str = ""):
        self.total = total
        self.current = 0
        self.prefix = prefix
        self.start_time = time.time()

    def update(self, n: int = 1):
        """更新进度"""
        self.current += n
        self._print()

    def _print(self):
        """打印进度条"""
        if self.total == 0:
            return

        percent = self.current / self.total * 100
        elapsed = time.time() - self.start_time

        # 估算剩余时间
        if self.current > 0:
            eta = elapsed / self.current * (self.total - self.current)
            eta_str = f"ETA: {int(eta)}s"
        else:
            eta_str = "ETA: --"

        bar_length = 30
        filled = int(bar_length * self.current / self.total)
        bar = "█" * filled + "░" * (bar_length - filled)

        print(f"\r{self.prefix} [{bar}] {self.current}/{self.total} ({percent:.1f}%) {eta_str}", end="", flush=True)

        if self.current >= self.total:
            print()  # 换行


class RateLimiter:
    """简单的速率限制器"""

    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self.interval = 60.0 / max_per_minute
        self.last_call = 0

    def wait(self):
        """等待直到可以执行下一次调用"""
        now = time.time()
        elapsed = now - self.last_call

        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)

        self.last_call = time.time()


# ============ 缓存相关函数 ============

import hashlib
from datetime import datetime
import re


# ============ MDX 标签规范化 ============

# HTML void 标签：MDX/JSX 编译器要求必须自闭合（<br />），
# 否则 next build 阶段会报 "Expected a corresponding JSX closing tag"。
VOID_TAGS_PATTERN = r"br|hr|img|input|meta|link|source|area|base|col|embed|param|track|wbr"

# 匹配 void 标签（含属性），已自闭合的也会命中，便于统一成 " />" 形式
_VOID_TAG_RE = re.compile(
    rf"<({VOID_TAGS_PATTERN})(?=[\s/>])([^<>]*?)\s*/?>",
    re.IGNORECASE,
)


def normalize_mdx_void_tags(content: str) -> str:
    """
    将未自闭合的 HTML void 标签转换为 JSX 自闭合形式（如 <br> -> <br />）。

    Markdown 围栏代码块内的内容保持原样，避免改动示例代码。

    Args:
        content: MDX 文本

    Returns:
        规范化后的 MDX 文本
    """
    if not content or '<' not in content:
        return content

    # 按围栏代码块切分，代码块原样保留
    parts = re.split(r"(^```.*?^```)", content, flags=re.DOTALL | re.MULTILINE)

    def _fix_void_tags(segment: str) -> str:
        return _VOID_TAG_RE.sub(
            lambda match: f"<{match.group(1)}{match.group(2).rstrip()} />",
            segment,
        )

    return "".join(
        part if part.startswith("```") else _fix_void_tags(part)
        for part in parts
    )


def find_unclosed_void_tag(content: str) -> str:
    """
    查找第一个未自闭合的 void 标签，用于校验/触发修复。

    Args:
        content: MDX 文本

    Returns:
        命中的标签名（如 "br"），未命中返回空字符串
    """
    if not content or '<' not in content:
        return ""
    for part in re.split(r"(^```.*?^```)", content, flags=re.DOTALL | re.MULTILINE):
        if part.startswith("```"):
            continue
        for match in _VOID_TAG_RE.finditer(part):
            if not match.group(0).rstrip().endswith('/>'):
                return match.group(1)
    return ""


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """
    清理文件名，移除特殊字符

    Args:
        filename: 原始文件名
        max_length: 最大长度

    Returns:
        清理后的文件名
    """
    # 移除或替换特殊字符
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'\s+', '_', filename)
    filename = filename.strip('._')

    # 截断到最大长度
    if len(filename) > max_length:
        filename = filename[:max_length]

    return filename


def get_cache_path(identifier: str, cache_type: str, title: str = None) -> str:
    """
    获取缓存文件路径

    Args:
        identifier: 缓存标识符（video_id 或 url_hash）
        cache_type: 缓存类型（"youtube" 或 "web"）
        title: 标题（可选，用于生成可读的文件名）

    Returns:
        缓存文件的完整路径
    """
    from .config import Config
    cache_dir = f"{Config.OUT_DIR}/cache/{cache_type}"
    ensure_dir(cache_dir)

    # 如果提供了标题，使用 "标题_identifier" 格式
    if title:
        clean_title = sanitize_filename(title, max_length=80)
        # 使用短哈希（前8位）来保证唯一性
        short_hash = identifier[:8] if len(identifier) > 8 else identifier
        filename = f"{clean_title}_{short_hash}.json"
    else:
        filename = f"{identifier}.json"

    return f"{cache_dir}/{filename}"


def get_url_hash(url: str) -> str:
    """
    获取 URL 的 MD5 哈希值

    Args:
        url: URL 字符串

    Returns:
        MD5 哈希值（32 字符）
    """
    return hashlib.md5(url.encode('utf-8')).hexdigest()


def load_cache(identifier: str, cache_type: str, title: str = None) -> Dict:
    """
    从缓存加载内容

    Args:
        identifier: 缓存标识符
        cache_type: 缓存类型
        title: 标题（可选）

    Returns:
        缓存数据字典，如果不存在返回 None
    """
    cache_path = get_cache_path(identifier, cache_type, title)
    try:
        return load_json(cache_path)
    except FileNotFoundError:
        # 如果使用标题的文件不存在，尝试使用旧格式（仅 identifier）
        if title:
            old_cache_path = get_cache_path(identifier, cache_type, title=None)
            try:
                return load_json(old_cache_path)
            except FileNotFoundError:
                pass
        return None


def save_cache(identifier: str, cache_type: str, data: dict, title: str = None) -> None:
    """
    保存内容到缓存

    Args:
        identifier: 缓存标识符
        cache_type: 缓存类型
        data: 要缓存的数据
        title: 标题（可选）
    """
    cache_path = get_cache_path(identifier, cache_type, title)
    cache_data = {
        **data,
        "cached_at": datetime.now().isoformat()
    }
    save_json(cache_data, cache_path)
