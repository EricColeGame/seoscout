"""
Web 搜索和提取模块

支持并行搜索和内容提取
"""

import asyncio
import aiohttp
import base64
import re
import time
from html.parser import HTMLParser
from typing import List, Dict, Tuple
from urllib.parse import parse_qs, urlparse

from .config import Config
from .models import WebItem
from .utils import is_blocked_domain, is_topic_match, load_cache, save_cache, get_url_hash
from .cleaner import ContentCleaner


class TokenBucket:
    """Token Bucket 速率限制器"""

    def __init__(self, rpm: int):
        """
        初始化速率限制器

        Args:
            rpm: 每分钟请求数
        """
        self.rpm = rpm
        self.tokens = rpm
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """获取令牌（阻塞直到有令牌可用）"""
        async with self.lock:
            while self.tokens < 1:
                await asyncio.sleep(0.1)
                self._refill()
            self.tokens -= 1

    def _refill(self):
        """补充令牌"""
        now = time.time()
        elapsed = now - self.last_update

        # 每秒补充 rpm/60 个令牌
        self.tokens = min(self.rpm, self.tokens + elapsed * (self.rpm / 60))
        self.last_update = now


class BingResultParser(HTMLParser):
    """解析 Bing 搜索结果页（`<li class="b_algo">`），提取标题 / 链接 / 摘要。

    Bing 把真实链接包在 `https://www.bing.com/ck/a?...&u=a1<base64url>` 里，
    因此链接需要经 decode_bing_url 还原后再用。
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results = []
        self._li_depth = 0
        self._current = None
        self._h2_depth = 0
        self._in_title = False
        self._in_snippet = False
        self._buf = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get('class') or '').split()
        if tag == 'li' and 'b_algo' in classes:
            self._li_depth = 1
            self._current = {'title': '', 'link': '', 'snippet': ''}
            return
        if not self._li_depth:
            return
        if tag == 'li':
            self._li_depth += 1
        elif tag == 'h2':
            self._h2_depth += 1
        elif tag == 'a' and self._h2_depth and not self._current['link']:
            self._current['link'] = attrs.get('href', '')
            self._in_title = True
            self._buf = []
        elif tag == 'p' and not self._current['snippet']:
            self._in_snippet = True
            self._buf = []

    def handle_endtag(self, tag):
        if not self._li_depth:
            return
        if tag == 'a' and self._in_title:
            self._current['title'] = re.sub(r'\s+', ' ', ''.join(self._buf)).strip()
            self._in_title = False
        elif tag == 'h2':
            self._h2_depth = max(0, self._h2_depth - 1)
        elif tag == 'p' and self._in_snippet:
            self._current['snippet'] = re.sub(r'\s+', ' ', ''.join(self._buf)).strip()
            self._in_snippet = False
        elif tag == 'li':
            self._li_depth -= 1
            if self._li_depth == 0:
                if self._current['link'] and self._current['title']:
                    self.results.append(self._current)
                self._current = None

    def handle_data(self, data):
        if self._in_title or self._in_snippet:
            self._buf.append(data)


def decode_bing_url(url: str) -> str:
    """还原 Bing 跳转链接，非跳转链接原样返回。"""
    if 'bing.com/ck/a' not in url:
        return url
    value = parse_qs(urlparse(url.replace('&amp;', '&')).query).get('u', [''])[0]
    if value.startswith('a1'):
        raw = value[2:]
        raw += '=' * (-len(raw) % 4)
        try:
            return base64.urlsafe_b64decode(raw).decode('utf-8', 'replace')
        except Exception:
            return url
    return url


class Web:
    """Web 搜索和提取（支持并行）"""

    _serper_disabled = False
    _bing_disabled = False

    def __init__(self):
        self.config = Config
        self.cleaner = ContentCleaner()  # 初始化内容清理器

    async def search_batch(self, keywords: List[str], topic_name: str = '') -> Dict[str, List[WebItem]]:
        """
        并行搜索多个关键词

        Args:
            keywords: 关键词列表
            topic_name: 主题名，用于过滤不相关结果（可选）

        Returns:
            {keyword: [WebItem, ...]}
        """
        print(f"\n🔍 Web 搜索: {len(keywords)} 个关键词")
        if topic_name:
            print(f"   主题名过滤: \"{topic_name}\"")

        # 创建信号量限制并发
        semaphore = asyncio.Semaphore(self.config.WEB_SEARCH_CONCURRENCY)

        # 并行搜索（带并发控制）
        tasks = [self._search_single(kw, semaphore, topic_name) for kw in keywords]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 构建结果字典
        result_dict = {}
        for keyword, result in zip(keywords, results):
            if isinstance(result, Exception):
                print(f"  ✗ {keyword}: {result}")
                result_dict[keyword] = []
            else:
                result_dict[keyword] = result
                print(f"  ✓ {keyword}: {len(result)} 个页面")

        return result_dict

    async def _search_single(self, keyword: str, semaphore, topic_name: str = '') -> List[WebItem]:
        """
        搜索单个关键词

        Args:
            keyword: 关键词
            semaphore: 并发控制信号量

        Returns:
            WebItem 列表
        """
        async with semaphore:
            # 添加小延迟避免触发速率限制
            await asyncio.sleep(0.3)

            try:
                results = []
                # 尝试 Serper API
                if not Web._serper_disabled and self.config.SERPER_API_KEY and len(self.config.SERPER_API_KEY.strip()) > 0:
                    try:
                        url = "https://google.serper.dev/search"
                        headers = {
                            "X-API-KEY": self.config.SERPER_API_KEY,
                            "Content-Type": "application/json"
                        }
                        payload = {
                            "q": keyword,
                            "num": self.config.WEB_SEARCH_TOP_N
                        }
                        proxy_url = self.config.get_proxy_url_for_stage("search")
                        async with aiohttp.ClientSession() as session:
                            async with session.post(url, json=payload, headers=headers, timeout=15, proxy=proxy_url) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    results = data.get("organic", [])
                                else:
                                    err_body = await response.text()
                                    if response.status == 400 or "credit" in err_body.lower():
                                        Web._serper_disabled = True
                                        print(f"  ⚠️ Serper 额度耗尽，自动切换为 Jina Search: {err_body[:80]}")
                    except Exception as e:
                        print(f"  ⚠️ Serper API 错误: {e}")

                # 若 Serper 无结果或不可用，降级使用 Jina Search
                if not results and self.config.JINA_API_KEY:
                    try:
                        jina_url = f"https://s.jina.ai/{keyword}"
                        headers = {
                            "Authorization": f"Bearer {self.config.JINA_API_KEY}",
                            "Accept": "application/json"
                        }
                        async with aiohttp.ClientSession() as session:
                            async with session.get(jina_url, headers=headers, timeout=25) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    for entry in data.get("data", []):
                                        results.append({
                                            "title": entry.get("title", ""),
                                            "link": entry.get("url", ""),
                                            "snippet": entry.get("description", "")
                                        })
                    except Exception as e:
                        print(f"  ⚠️ Jina search 降级异常: {e}")

                # 若仍无结果（Serper 额度耗尽且 Jina 不可用/无余额），降级使用 Bing
                if not results and not Web._bing_disabled:
                    results = await self._bing_search(keyword)

                # 过滤屏蔽域名
                filtered = [
                    r for r in results
                    if not is_blocked_domain(r.get('link', ''), self.config.BLOCKED_DOMAINS)
                ]

                # 主题相关性优先排序（稳定排序，不丢弃任何结果）：
                # 关键词常与同名的其它事物撞车（如 "slime out fish" 同时是水族药剂
                # "Fritz Slime Out" 和 Roblox 游戏名），Serper 返回的头部结果可能整片
                # 跑题。而 WEB_EXTRACT_TOP_K 只取前 K 条，若跑题结果占据头部，真正相关
                # 的页面（如 roblox.com/games/...）会被直接丢掉，生成阶段只能照着跑题
                # 素材写。这里把命中主题名的结果提到前面，无命中时保持原有顺序。
                if topic_name:
                    filtered.sort(
                        key=lambda r: not is_topic_match(
                            f"{r.get('title', '')} {r.get('snippet', '')} {r.get('link', '')}",
                            topic_name,
                        )
                    )

                # 转换为 WebItem
                items = []
                for r in filtered[:self.config.WEB_SEARCH_TOP_N]:
                    domain = urlparse(r.get('link', '')).netloc
                    items.append(WebItem(
                        title=r.get('title', ''),
                        url=r.get('link', ''),
                        domain=domain,
                        snippet=r.get('snippet', ''),
                        selected=True
                    ))

                return items

            except Exception as e:
                raise Exception(f"搜索失败: {e}")

    async def _bing_search(self, keyword: str) -> List[Dict]:
        """Bing HTML 搜索兜底（无需 API key）。

        Serper 额度耗尽、Jina 无余额时的最后一级降级：直接抓取 Bing 搜索结果页
        的 `b_algo` 列表，解析出标题 / 真实链接 / 摘要，输出结构与 Serper 的
        organic 结果保持一致（title / link / snippet）。
        """
        query = keyword.replace(' ', '+')
        url = f"https://www.bing.com/search?q={query}&count={self.config.WEB_SEARCH_TOP_N}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        for attempt in range(2):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=20) as response:
                        if response.status != 200:
                            raise Exception(f"HTTP {response.status}")
                        html = await response.text()
                parser = BingResultParser()
                parser.feed(html)
                parsed = [
                    {
                        "title": entry["title"],
                        "link": decode_bing_url(entry["link"]),
                        "snippet": entry["snippet"],
                    }
                    for entry in parser.results
                ]
                if parsed:
                    return parsed
                raise Exception("页面未解析出结果")
            except Exception as e:
                if attempt == 1:
                    print(f"  ⚠️ Bing search 降级失败: {e}")
                    return []
                await asyncio.sleep(2 ** attempt)
        return []

    def _log_filtered(self, topic_name: str, items: list, source: str = "web"):
        """记录被过滤掉的条目到日志文件，便于后期审查"""
        import json
        from pathlib import Path

        log_dir = Path(self.config.DATA_DIR) / "out" / "filter_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"filtered_{source}.jsonl"

        entry = {
            "topic_name": topic_name,
            "source": source,
            "filtered_count": len(items),
            "items": [{"title": r.get("title", ""), "link": r.get("link", "")} for r in items]
        }

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    async def extract_batch(self, items: List[WebItem]) -> List[Tuple[WebItem, str]]:
        """
        并行提取多个页面内容

        Args:
            items: WebItem 列表

        Returns:
            [(item, content), ...]
        """
        print(f"\n📥 Web 提取: {len(items)} 个页面")

        # 创建信号量和速率限制器
        semaphore = asyncio.Semaphore(self.config.JINA_CONCURRENCY)
        rate_limiter = TokenBucket(self.config.JINA_RPM)

        # 并行提取
        tasks = [self._extract_single(item, semaphore, rate_limiter) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计成功和失败
        success_count = sum(1 for _, content in results if content and not isinstance(content, Exception))
        print(f"  ✓ 成功: {success_count}/{len(items)}")

        return results

    async def _extract_single(self, item: WebItem, semaphore, rate_limiter) -> Tuple[WebItem, str]:
        """
        提取单个页面内容（带缓存和重试）

        Args:
            item: WebItem 对象
            semaphore: 并发控制信号量
            rate_limiter: 速率限制器

        Returns:
            (item, content) 元组
        """
        async with semaphore:
            # 1. 检查缓存
            url_hash = get_url_hash(item.url)
            cache_data = load_cache(url_hash, "web", title=item.title)
            if cache_data and cache_data.get("content"):
                print(f"  💾 缓存命中: {item.title[:50]}...")
                return (item, cache_data["content"])

            # 2. 缓存未命中，提取内容（带重试）
            for attempt in range(self.config.WEB_EXTRACT_RETRIES):
                # 速率限制
                await rate_limiter.acquire()

                try:
                    # 使用 Jina Reader
                    jina_url = f"https://r.jina.ai/{item.url}"
                    headers = {}

                    if self.config.JINA_API_KEY:
                        headers["Authorization"] = f"Bearer {self.config.JINA_API_KEY}"

                    # 获取提取阶段代理配置
                    proxy_url = self.config.get_proxy_url_for_stage("extract")

                    async with aiohttp.ClientSession() as session:
                        async with session.get(jina_url, headers=headers, timeout=30, proxy=proxy_url) as response:
                            # HTTP 错误处理
                            if response.status != 200:
                                if attempt < self.config.WEB_EXTRACT_RETRIES - 1:
                                    await asyncio.sleep(2 ** attempt)  # 指数退避：2s, 4s, 8s
                                    continue
                                return (item, "")

                            content = await response.text()

                            # 内容长度检查
                            if len(content.strip()) < 500:
                                if attempt < self.config.WEB_EXTRACT_RETRIES - 1:
                                    await asyncio.sleep(2 ** attempt)
                                    continue
                                return (item, "")

                            # 清理内容（移除导航链接、广告等）
                            cleaned_content = self.cleaner.clean(content)

                            # 3. 保存到缓存
                            save_cache(url_hash, "web", {
                                "title": item.title,
                                "url": item.url,
                                "domain": item.domain,
                                "content": cleaned_content,  # 保存清理后的内容
                                "source_type": "web"
                            }, title=item.title)

                            return (item, cleaned_content)

                except Exception as e:
                    if attempt == self.config.WEB_EXTRACT_RETRIES - 1:
                        # 最后一次重试失败，返回空内容
                        return (item, "")
                    await asyncio.sleep(2 ** attempt)  # 指数退避

            return (item, "")

