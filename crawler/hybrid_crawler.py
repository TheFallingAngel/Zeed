#!/usr/bin/env python3
"""
闪价雷达 - 混合策略爬虫 v2
AI Agent 处理导航 + Playwright 处理数据提取

架构：
┌─────────────────────────────────────────────────────┐
│                    HybridCrawler                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│   ┌───────────────────┐    ┌───────────────────┐   │
│   │   AI Agent 层     │ -> │   Playwright 层   │   │
│   │  (Browser Use)    │    │    (数据提取)     │   │
│   │                   │    │                   │   │
│   │  - 处理弹窗       │    │  - 结构化数据     │   │
│   │  - 地址选择       │    │  - 批量采集       │   │
│   │  - 验证码         │    │  - 快速准确       │   │
│   │  - 异常恢复       │    │                   │   │
│   └───────────────────┘    └───────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘

使用方式:
1. 安装依赖: pip install browser-use langchain-anthropic playwright
2. 设置 API Key: export ANTHROPIC_API_KEY=your-key
3. 运行: python -m crawler.hybrid_crawler
"""

import asyncio
import os
import re
import random
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict

# Playwright - 用于数据提取
from playwright.async_api import async_playwright, Page, Browser as PWBrowser, BrowserContext

# 导入项目配置
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PILOT_LOCATIONS, DEFAULT_PRODUCTS, Location

# Browser Use - 可选依赖
HAS_BROWSER_USE = False
HAS_ANTHROPIC = False

try:
    from browser_use import Agent, Browser as BUBrowser, BrowserConfig
    HAS_BROWSER_USE = True
except ImportError:
    pass

try:
    from langchain_anthropic import ChatAnthropic
    HAS_ANTHROPIC = True
except ImportError:
    pass


@dataclass
class CrawledPrice:
    """采集到的价格数据"""
    platform: str
    shop_id: str
    shop_name: str
    shop_address: str
    distance: int
    product_name: str
    price: float
    original_price: float
    promotion: str
    in_stock: bool
    crawled_at: str
    
    def to_dict(self) -> dict:
        return asdict(self)


class HybridMeituanCrawler:
    """
    混合策略美团爬虫
    
    策略：
    1. 使用 AI Agent (Browser Use) 完成复杂导航（可选）
    2. 使用 Playwright 进行快速数据提取
    
    如果 Browser Use 不可用，回退到纯 Playwright 模式
    """
    
    def __init__(self, use_ai: bool = True, llm_provider: str = "anthropic"):
        """
        初始化爬虫
        
        Args:
            use_ai: 是否使用 AI Agent
            llm_provider: LLM 提供商 ("anthropic" 或 "deepseek")
        """
        # 检查 AI 是否可用
        self.use_ai = use_ai and HAS_BROWSER_USE
        self.llm_provider = llm_provider
        
        # AI 组件
        self.bu_browser = None
        self.llm = None
        
        # Playwright 组件
        self.playwright = None
        self.pw_browser: Optional[PWBrowser] = None
        self.pw_context: Optional[BrowserContext] = None
        self.pw_page: Optional[Page] = None
        
        # 状态
        self.screenshot_count = 0
        self.location: Optional[Location] = None
        self.location_set = False
        
        # 显示模式
        if self.use_ai:
            if HAS_ANTHROPIC and os.getenv("ANTHROPIC_API_KEY"):
                print("✅ 混合模式: AI Agent (Claude) + Playwright")
            elif os.getenv("DEEPSEEK_API_KEY"):
                print("✅ 混合模式: AI Agent (DeepSeek) + Playwright")
                self.llm_provider = "deepseek"
            else:
                print("⚠️ 缺少 API Key，回退到纯 Playwright 模式")
                self.use_ai = False
        else:
            print("📌 纯 Playwright 模式")
    
    def _create_llm(self):
        """创建 LLM 实例"""
        if self.llm_provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model="claude-sonnet-4-20250514",
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                timeout=120,
            )
        elif self.llm_provider == "deepseek":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model="deepseek-chat",
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com/v1",
                timeout=120,
            )
        else:
            raise ValueError(f"不支持的 LLM: {self.llm_provider}")
    
    async def init_browser(self, location: Location, headless: bool = True):
        """
        初始化浏览器
        
        Args:
            location: 目标位置
            headless: 是否无头模式
        """
        self.location = location
        
        user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        
        # ========== 初始化 Playwright ==========
        print("🌐 初始化 Playwright...")
        self.playwright = await async_playwright().start()
        
        self.pw_browser = await self.playwright.chromium.launch(
            headless=headless,
            slow_mo=50,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--lang=zh-CN',
            ]
        )
        
        self.pw_context = await self.pw_browser.new_context(
            viewport={"width": 375, "height": 812},
            user_agent=user_agent,
            geolocation={"latitude": location.latitude, "longitude": location.longitude},
            permissions=["geolocation"],
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
        )
        
        # 反检测脚本
        await self.pw_context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
        """)
        
        self.pw_page = await self.pw_context.new_page()
        self.pw_page.set_default_timeout(30000)
        
        # ========== 初始化 Browser Use (如果可用) ==========
        if self.use_ai:
            try:
                print("🤖 初始化 AI Agent...")
                self.llm = self._create_llm()
                
                config = BrowserConfig(
                    headless=headless,
                    disable_security=True,
                    extra_chromium_args=[
                        '--no-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--lang=zh-CN',
                    ],
                )
                self.bu_browser = BUBrowser(config=config)
                print("✅ AI Agent 初始化完成")
                
            except Exception as e:
                print(f"⚠️ AI Agent 初始化失败: {e}")
                self.use_ai = False
        
        print(f"✅ 浏览器初始化完成")
        print(f"   位置: {location.name}")
        print(f"   地址: {location.address}")
    
    async def close(self):
        """关闭所有浏览器"""
        if self.pw_context:
            await self.pw_context.close()
        if self.pw_browser:
            await self.pw_browser.close()
        if self.playwright:
            await self.playwright.stop()
        if self.bu_browser:
            await self.bu_browser.close()
        print("🔒 浏览器已关闭")
    
    async def _screenshot(self, name: str) -> str:
        """保存截图"""
        self.screenshot_count += 1
        path = f"debug_{self.screenshot_count:02d}_{name}.png"
        await self.pw_page.screenshot(path=path)
        return path
    
    # ==================== AI Agent 方法 ====================
    
    async def _ai_setup_location(self) -> bool:
        """使用 AI Agent 设置地址"""
        if not self.use_ai or not self.bu_browser or not self.location:
            return False
        
        city = "重庆"
        address = self.location.address.replace("重庆市南岸区", "")
        
        task = f"""
你需要在美团外卖H5页面设置收货地址。

【步骤】
1. 打开 https://h5.waimai.meituan.com
2. 等待页面加载，关闭所有弹窗（点击关闭按钮或空白处）
3. 点击页面顶部的地址栏
4. 如果出现城市选择，点击"{city}"
5. 在搜索框输入"{address}"
6. 点击第一个搜索结果
7. 确认返回首页，地址已更新

【成功标准】
页面顶部显示包含"{address}"的地址

【回复】
- 成功: SUCCESS: [显示的地址]
- 失败: FAILED: [原因]
- 验证码: CAPTCHA

【注意】
- 中文页面
- 遇到403就刷新重试
- 每步等待1-2秒
"""
        
        print(f"\n🤖 AI 设置地址: {city} {address}")
        
        try:
            agent = Agent(
                task=task,
                llm=self.llm,
                browser=self.bu_browser,
            )
            
            history = await agent.run(max_steps=25)
            result = str(history.final_result()) if history else ""
            
            if "SUCCESS" in result.upper():
                print(f"   ✅ AI 设置成功")
                self.location_set = True
                return True
            else:
                print(f"   ⚠️ AI 设置结果: {result[:80]}")
                return False
                
        except Exception as e:
            print(f"   ❌ AI 设置失败: {e}")
            return False
    
    # ==================== Playwright 方法 ====================
    
    async def _pw_close_popups(self):
        """关闭弹窗"""
        selectors = [
            '[class*="close"]', '[class*="Close"]',
            'text=×', 'text=关闭', 'text=取消',
            '[class*="mask"]',
        ]
        
        for selector in selectors:
            try:
                elems = await self.pw_page.query_selector_all(selector)
                for elem in elems[:3]:  # 最多处理3个
                    if await elem.is_visible():
                        box = await elem.bounding_box()
                        if box and box['width'] < 100 and box['height'] < 100:
                            await elem.click()
                            await asyncio.sleep(0.3)
            except:
                continue
        
        # 按 ESC
        await self.pw_page.keyboard.press("Escape")
        await asyncio.sleep(0.2)
    
    async def _pw_setup_location_fallback(self) -> bool:
        """Playwright 回退方案：设置位置"""
        if not self.location:
            return False
            
        print("\n📍 Playwright 设置位置...")
        
        try:
            # 1. 打开首页
            await self.pw_page.goto(
                "https://h5.waimai.meituan.com",
                wait_until="domcontentloaded",
                timeout=30000
            )
            await asyncio.sleep(3)
            await self._pw_close_popups()
            await self._screenshot("home")
            
            # 2. 点击地址栏
            address_area = await self.pw_page.query_selector(
                '[class*="location"], [class*="address"], [class*="poi"]'
            )
            if address_area:
                await address_area.click()
            else:
                # 点击顶部区域
                await self.pw_page.click('body', position={"x": 180, "y": 40})
            
            await asyncio.sleep(2)
            await self._screenshot("address_page")
            
            # 3. 检查是否需要选择城市
            page_text = await self.pw_page.inner_text("body")
            if "选择城市" in page_text:
                city_btn = await self.pw_page.query_selector('text=重庆')
                if city_btn:
                    await city_btn.click()
                    await asyncio.sleep(2)
            
            # 4. 输入地址
            address = self.location.address.replace("重庆市南岸区", "")
            input_elem = await self.pw_page.query_selector(
                'input[placeholder*="搜索"], input[placeholder*="地址"], input'
            )
            if input_elem:
                await input_elem.click()
                await asyncio.sleep(0.5)
                
                # 逐字输入
                for char in address:
                    await input_elem.type(char, delay=random.randint(50, 120))
                
                await asyncio.sleep(2)
                await self._screenshot("address_input")
                
                # 5. 点击搜索结果
                results = await self.pw_page.query_selector_all(
                    '[class*="poi"], [class*="item"], [class*="suggest"]'
                )
                for result in results[:5]:
                    text = await result.inner_text()
                    if address in text or "南坪" in text:
                        await result.click()
                        await asyncio.sleep(2)
                        self.location_set = True
                        print("   ✅ 位置设置完成")
                        return True
            
            return False
            
        except Exception as e:
            print(f"   ❌ 位置设置失败: {e}")
            return False
    
    async def _pw_search_product(self, keyword: str) -> List[CrawledPrice]:
        """使用 Playwright 搜索商品并提取价格"""
        results = []
        crawled_at = datetime.now().isoformat()
        
        print(f"\n🔍 搜索: {keyword}")
        
        try:
            # 1. 确保在首页
            current_url = self.pw_page.url
            if "waimai.meituan.com" not in current_url:
                await self.pw_page.goto(
                    "https://h5.waimai.meituan.com",
                    wait_until="domcontentloaded",
                    timeout=30000
                )
                await asyncio.sleep(2)
            
            await self._pw_close_popups()
            
            # 2. 点击搜索框
            search_selectors = [
                'input[placeholder*="搜"]',
                'input[placeholder*="商"]',
                '[class*="search"] input',
                '[class*="search"]',
            ]
            
            search_elem = None
            for sel in search_selectors:
                elem = await self.pw_page.query_selector(sel)
                if elem and await elem.is_visible():
                    search_elem = elem
                    break
            
            if search_elem:
                await search_elem.click()
                await asyncio.sleep(1)
            
            # 3. 输入关键词
            input_elem = await self.pw_page.wait_for_selector('input:visible', timeout=5000)
            if input_elem:
                await input_elem.click()
                await asyncio.sleep(0.3)
                
                # 清空并输入
                await input_elem.fill("")
                for char in keyword:
                    await input_elem.type(char, delay=random.randint(30, 80))
                
                await asyncio.sleep(1)
                
                # 4. 执行搜索
                search_btn = await self.pw_page.query_selector('text=搜索')
                if search_btn and await search_btn.is_visible():
                    await search_btn.click()
                else:
                    await self.pw_page.keyboard.press("Enter")
                
                # 5. 等待结果
                await asyncio.sleep(4)
                await self._screenshot(f"result_{keyword}")
                
                # 检查错误
                page_text = await self.pw_page.inner_text("body")
                if "403" in page_text or "系统繁忙" in page_text or "出了点小差" in page_text:
                    print("   ⚠️ 触发反爬，等待重试...")
                    await asyncio.sleep(5)
                    await self.pw_page.reload()
                    await asyncio.sleep(3)
                
                # 6. 解析结果
                results = await self._parse_results(keyword, crawled_at)
            
        except Exception as e:
            print(f"   ❌ 搜索出错: {e}")
            import traceback
            traceback.print_exc()
        
        return results
    
    async def _parse_results(self, keyword: str, crawled_at: str) -> List[CrawledPrice]:
        """解析搜索结果"""
        results = []
        
        try:
            # 尝试从 JavaScript 获取数据
            js_data = await self.pw_page.evaluate("""
                () => {
                    // 尝试多种数据源
                    const sources = [
                        window.__INITIAL_STATE__,
                        window.__NUXT__,
                        window.__DATA__,
                        window.pageData,
                    ];
                    for (const src of sources) {
                        if (src) return { source: 'window', data: src };
                    }
                    return null;
                }
            """)
            
            if js_data and js_data.get('data'):
                print(f"   📊 从 JS 获取到数据")
            
            # 从 DOM 解析
            card_selectors = [
                '[class*="shopItem"]', '[class*="poi"]',
                '[class*="merchant"]', '[class*="store"]',
                '[class*="goods"]', '[class*="product"]',
                '[class*="card"]', '[class*="list"] > div',
            ]
            
            cards = []
            for sel in card_selectors:
                cards = await self.pw_page.query_selector_all(sel)
                if len(cards) > 2:
                    print(f"   找到 {len(cards)} 个结果卡片")
                    break
            
            for i, card in enumerate(cards[:15]):
                try:
                    text = await card.inner_text()
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    
                    if not lines:
                        continue
                    
                    # 提取店铺名
                    shop_name = lines[0][:30]
                    
                    # 提取价格
                    price = 0.0
                    price_match = re.search(r'[¥￥]\s*(\d+\.?\d*)', text)
                    if price_match:
                        price = float(price_match.group(1))
                    
                    # 提取距离
                    distance = 0
                    dist_match = re.search(r'(\d+\.?\d*)\s*(km|m|米|公里)', text, re.I)
                    if dist_match:
                        val = float(dist_match.group(1))
                        unit = dist_match.group(2).lower()
                        if 'km' in unit or '公里' in unit:
                            distance = int(val * 1000)
                        else:
                            distance = int(val)
                    
                    if price > 0:
                        results.append(CrawledPrice(
                            platform="meituan",
                            shop_id=f"mt_{i}_{hash(shop_name) % 10000}",
                            shop_name=shop_name,
                            shop_address="",
                            distance=distance,
                            product_name=keyword,
                            price=price,
                            original_price=price,
                            promotion="",
                            in_stock=True,
                            crawled_at=crawled_at,
                        ))
                        
                except Exception as e:
                    continue
            
            if results:
                print(f"   ✅ 解析到 {len(results)} 条价格")
                for r in results[:3]:
                    print(f"      🏪 {r.shop_name}: ¥{r.price}")
            else:
                print(f"   ⚠️ 未解析到价格数据")
            
        except Exception as e:
            print(f"   ❌ 解析出错: {e}")
        
        return results
    
    # ==================== 公开 API ====================
    
    async def ensure_location_set(self) -> bool:
        """确保位置已设置"""
        if self.location_set:
            return True
        
        # 尝试 AI 设置
        if self.use_ai:
            success = await self._ai_setup_location()
            if success:
                return True
        
        # 回退到 Playwright
        return await self._pw_setup_location_fallback()
    
    async def search_product(self, keyword: str) -> List[CrawledPrice]:
        """搜索单个商品"""
        # 确保位置已设置
        if not self.location_set:
            await self.ensure_location_set()
        
        return await self._pw_search_product(keyword)
    
    async def crawl_products(self, products: List[str]) -> List[CrawledPrice]:
        """批量采集商品"""
        all_results = []
        
        print(f"\n{'='*60}")
        print(f"📦 开始批量采集")
        print(f"   商品数: {len(products)}")
        print(f"   位置: {self.location.name if self.location else 'N/A'}")
        print(f"{'='*60}")
        
        # 确保位置设置
        await self.ensure_location_set()
        
        for i, product in enumerate(products):
            print(f"\n[{i+1}/{len(products)}] {product}")
            
            try:
                results = await self.search_product(product)
                all_results.extend(results)
                
                # 随机延迟
                delay = random.uniform(2, 5)
                print(f"   等待 {delay:.1f}s...")
                await asyncio.sleep(delay)
                
            except Exception as e:
                print(f"   ❌ 采集失败: {e}")
        
        print(f"\n{'='*60}")
        print(f"✅ 批量采集完成")
        print(f"   总计: {len(all_results)} 条价格数据")
        print(f"{'='*60}")
        
        return all_results


# ==================== 便捷函数 ====================

async def crawl_prices(
    location: Location, 
    products: List[str], 
    use_ai: bool = True,
    headless: bool = True,
) -> List[CrawledPrice]:
    """
    便捷函数：采集指定位置的商品价格
    
    Args:
        location: 目标位置
        products: 商品列表
        use_ai: 是否使用 AI Agent
        headless: 是否无头模式
        
    Returns:
        价格数据列表
    """
    crawler = HybridMeituanCrawler(use_ai=use_ai)
    
    try:
        await crawler.init_browser(location, headless=headless)
        results = await crawler.crawl_products(products)
        return results
    finally:
        await crawler.close()


# ==================== 测试函数 ====================

async def test_hybrid_crawler():
    """测试混合爬虫"""
    
    print("\n" + "🚀" * 20)
    print("🚀 混合策略爬虫测试")
    print("🚀" * 20)
    
    # 环境检查
    print("\n📋 环境检查:")
    print(f"   Browser Use: {'✅' if HAS_BROWSER_USE else '❌ (pip install browser-use)'}")
    print(f"   Anthropic: {'✅' if HAS_ANTHROPIC else '❌ (pip install langchain-anthropic)'}")
    print(f"   ANTHROPIC_API_KEY: {'✅' if os.getenv('ANTHROPIC_API_KEY') else '❌'}")
    print(f"   DEEPSEEK_API_KEY: {'✅' if os.getenv('DEEPSEEK_API_KEY') else '❌'}")
    
    # 测试配置
    location = PILOT_LOCATIONS[0]  # 南坪步行街
    test_products = ["农夫山泉", "红牛"]
    
    print(f"\n📍 测试位置: {location.name}")
    print(f"📦 测试商品: {test_products}")
    
    # 创建爬虫
    use_ai = HAS_BROWSER_USE and (
        os.getenv('ANTHROPIC_API_KEY') or os.getenv('DEEPSEEK_API_KEY')
    )
    
    crawler = HybridMeituanCrawler(use_ai=use_ai)
    
    try:
        # 初始化（非无头模式）
        await crawler.init_browser(location, headless=False)
        
        # 采集
        results = await crawler.crawl_products(test_products)
        
        # 显示结果
        print("\n" + "=" * 60)
        print("📊 测试结果汇总")
        print("=" * 60)
        
        for product in test_products:
            product_results = [r for r in results if r.product_name == product]
            print(f"\n{product}: {len(product_results)} 条")
            for r in product_results[:3]:
                print(f"   🏪 {r.shop_name}: ¥{r.price} ({r.distance}m)")
        
        # 保存结果
        if results:
            output_file = "crawl_results.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in results], f, ensure_ascii=False, indent=2)
            print(f"\n💾 结果已保存: {output_file}")
        
        # 保持浏览器打开
        print("\n⏸️ 浏览器保持打开 20 秒...")
        await asyncio.sleep(20)
        
    finally:
        await crawler.close()
    
    print("\n✅ 测试完成!")


if __name__ == "__main__":
    asyncio.run(test_hybrid_crawler())
