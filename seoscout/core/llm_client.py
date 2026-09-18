"""
LLM API Client — async batch generation with retry logic.

Shared by generate and translate stages. All config from Config class (.env).
"""

import asyncio
import aiohttp
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import Config


class LLMClient:
    """Async LLM API client with retry, stats, and batch support."""

    def __init__(self):
        self.api_key = Config.LLM_API_KEY
        self.base_url = Config.LLM_API_BASE_URL.rstrip('/')
        self.api_style = Config.LLM_API_STYLE
        self.api_url = (
            f"{self.base_url}/messages"
            if self.api_style == "anthropic"
            else f"{self.base_url}/chat/completions"
        )
        self.model = Config.LLM_MODEL
        self.temperature = Config.LLM_TEMPERATURE
        self.max_tokens = Config.LLM_MAX_TOKENS
        self.timeout_seconds = Config.LLM_TIMEOUT
        self.retry_attempts = Config.LLM_RETRY_ATTEMPTS
        self.retry_delay = Config.LLM_RETRY_DELAY
        self.max_rate_limit_wait = Config.LLM_MAX_RATE_LIMIT_WAIT

        self.headers = {"Content-Type": "application/json"}
        if self.api_style == "anthropic":
            self.headers.update({"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
        else:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_tokens': 0,
            'start_time': None,
            'end_time': None,
        }

    # ── single request ──────────────────────────────────────────

    async def generate_single(
        self,
        session: aiohttp.ClientSession,
        prompt: str,
        meta: Dict = None,
    ) -> Optional[str]:
        """Send a single prompt, return content string or None."""
        self.stats['total_requests'] += 1
        label = (meta or {}).get('keyword', 'unknown')

        for attempt in range(self.retry_attempts):
            try:
                payload = {
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    "messages": [
                        {"role": "system", "content": "You are a professional SEO content writer."},
                        {"role": "user", "content": prompt},
                    ],
                }
                if self.api_style == "openai":
                    payload["stream"] = False
                async with session.post(
                    self.api_url, json=payload,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._save_debug(meta or {}, data)
                        content = self._extract_content(data)

                        if 'usage' in data:
                            self.stats['total_tokens'] += data['usage'].get('total_tokens', 0)

                        if not content or not content.strip():
                            print(f"  ⚠️  Empty response for {label} (attempt {attempt+1}/{self.retry_attempts})")
                            if attempt < self.retry_attempts - 1:
                                await asyncio.sleep(self.retry_delay * (attempt + 1))
                                continue
                            self.stats['failed_requests'] += 1
                            return None

                        self.stats['successful_requests'] += 1
                        return content

                    elif resp.status == 429:
                        wait = self.retry_delay * (attempt + 1) * 2
                        print(f"  ⚠️  Rate limited for {label}, waiting {wait}s...")
                        await asyncio.sleep(wait)
                        continue

                    else:
                        err = await resp.text()
                        print(f"  ❌ API {resp.status} for {label}: {err[:300]}")
                        if attempt < self.retry_attempts - 1:
                            await asyncio.sleep(self._retry_wait(attempt, err))
                            continue
                        self.stats['failed_requests'] += 1
                        return None

            except asyncio.TimeoutError:
                print(f"  ⏱️  Timeout for {label} (attempt {attempt+1}/{self.retry_attempts})")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                self.stats['failed_requests'] += 1
                return None

            except Exception as e:
                print(f"  ❌ Exception for {label}: {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                self.stats['failed_requests'] += 1
                return None

        self.stats['failed_requests'] += 1
        return None

    def _retry_wait(self, attempt: int, err: str) -> float:
        """计算重试等待时长。

        上游网关在账号池耗尽时会返回形如 "All accounts limited. Wait 295s." 的
        503，并明确给出可重试的时间点。此时若仍按默认退避（8s、16s…）重试，
        必然在服务端恢复前耗尽全部重试次数而失败。因此优先遵循服务端提示，
        上限由 LLM_MAX_RATE_LIMIT_WAIT 控制，避免无限等待。
        """
        default_wait = self.retry_delay * (attempt + 1)
        hint = re.search(r"[Ww]ait\s+(\d+)\s*s", err or "")
        if not hint:
            return default_wait
        return max(default_wait, min(int(hint.group(1)) + 5, self.max_rate_limit_wait))

    def _extract_content(self, data: Dict) -> str:
        if self.api_style == "anthropic":
            return "".join(
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            )
        return data["choices"][0]["message"]["content"]

    # ── batch ───────────────────────────────────────────────────

    async def generate_batch(
        self,
        prompts: List[Tuple[str, Dict]],
        batch_size: int = None,
    ) -> List[Tuple[Dict, Optional[str]]]:
        """
        Batch-generate from list of (prompt, meta) tuples.
        Returns list of (meta, content_or_None) in same order.
        """
        if batch_size is None:
            batch_size = Config.GENERATE_BATCH_SIZE

        self.stats['start_time'] = time.time()
        results: List[Tuple[Dict, Optional[str]]] = []

        async with aiohttp.ClientSession() as session:
            for i in range(0, len(prompts), batch_size):
                batch = prompts[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(prompts) + batch_size - 1) // batch_size

                print(f"\n  📦 Batch {batch_num}/{total_batches} ({len(batch)} items)...")

                tasks = [
                    self.generate_single(session, prompt, meta)
                    for prompt, meta in batch
                ]
                batch_results = await asyncio.gather(*tasks)

                for (prompt, meta), content in zip(batch, batch_results):
                    results.append((meta, content))

                completed = i + len(batch)
                print(f"  ✅ {completed}/{len(prompts)} done")

                if i + batch_size < len(prompts):
                    await asyncio.sleep(1)

        self.stats['end_time'] = time.time()
        return results

    # ── debug ───────────────────────────────────────────────────

    def _save_debug(self, meta: Dict, data: Dict):
        try:
            debug_dir = Path(Config.LOG_DIR) / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            keyword = meta.get('keyword', 'unknown')
            lang = meta.get('language', 'en')
            fp = debug_dir / f"{lang}_{keyword.replace(' ', '_')}_response.json"
            fp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        except Exception:
            pass

    # ── stats ───────────────────────────────────────────────────

    def print_stats(self):
        s = self.stats
        duration = (s['end_time'] or time.time()) - (s['start_time'] or time.time())
        rate = s['total_requests'] / duration if duration > 0 else 0
        success_rate = (
            s['successful_requests'] / s['total_requests'] * 100
            if s['total_requests'] > 0 else 0
        )
        print(f"\n  📊 LLM API: {s['successful_requests']}/{s['total_requests']} ok "
              f"({success_rate:.0f}%) | {s['total_tokens']} tokens | {duration:.1f}s")
