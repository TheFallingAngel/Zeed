#!/usr/bin/env python3
"""
闪价雷达 - Browser Use POC
测试用 AI Agent 完成美团H5地址设置流程

使用方式:
1. 安装依赖: pip install browser-use langchain-anthropic
2. 设置环境变量: export ANTHROPIC_API_KEY=your-key
3. 运行: python poc_browser_use.py

支持的 LLM:
- Claude (anthropic): 效果最好，推荐
- DeepSeek (deepseek): 国产，便宜，¥1/百万token
- GPT-4 (openai): 备选
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any

# ==================== 依赖检查 ====================
def check_dependencies():
    """检查必要依赖"""
    missing = []
    
    try:
        from browser_use import Agent, Browser
    except ImportError:
        missing.append("browser-use")
    
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        missing.append("langchain-anthropic")
    
    if missing:
        print("❌ 缺少依赖，请安装:")
        print(f"   pip install {' '.join(missing)}")
        return False
    return True


# ==================== LLM 初始化 ====================
def create_llm(provider: str = "anthropic"):
    """
    创建 LLM 实例
    
    Args:
        provider: "anthropic" | "deepseek" | "openai"
    """
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("请设置 ANTHROPIC_API_KEY 环境变量")
        return ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=api_key,
            timeout=120,
            max_retries=3,
        )
        
    elif provider == "deepseek":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("请设置 DEEPSEEK_API_KEY 环境变量")
        return ChatOpenAI(
            model="deepseek-chat",
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            timeout=120,
        )
        
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("请设置 OPENAI_API_KEY 环境变量")
        return ChatOpenAI(
            model="gpt-4o",
            api_key=api_key,
            timeout=120,
        )
    else:
        raise ValueError(f"不支持的 LLM: {provider}")


# ==================== 核心 POC 类 ====================
class MeituanAINavigator:
    """
    美团H5 AI导航器
    
    使用 Browser Use 框架，让 AI Agent 完成复杂的网页交互：
    - 自动处理弹窗
    - 智能选择城市和地址
    - 处理各种异常情况
    """
    
    def __init__(self, llm_provider: str = "anthropic"):
        self.llm_provider = llm_provider
        self.llm = None
        self.browser = None
        
    async def init(self, headless: bool = False):
        """初始化浏览器和 LLM"""
        from browser_use import Browser, BrowserConfig
        
        print(f"🔧 初始化 LLM ({self.llm_provider})...")
        self.llm = create_llm(self.llm_provider)
        
        print("🌐 初始化浏览器...")
        # Browser Use 的浏览器配置
        config = BrowserConfig(
            headless=headless,
            disable_security=True,
            extra_chromium_args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--lang=zh-CN',
            ],
        )
        self.browser = Browser(config=config)
        print("✅ 初始化完成")
        
    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            print("🔒 浏览器已关闭")
    
    async def setup_location(self, city: str, address: str) -> Dict[str, Any]:
        """
        使用 AI 完成地址设置
        
        这是核心的 AI 导航功能，AI 会：
        1. 打开美团外卖H5
        2. 处理各种弹窗
        3. 选择城市
        4. 搜索并选择地址
        """
        from browser_use import Agent
        
        task = f"""
你是一个网页自动化助手，需要在美团外卖H5页面设置收货地址。

【任务步骤】
1. 打开网页 https://h5.waimai.meituan.com
2. 等待页面加载（可能显示"定位中"或"加载中"）
3. 关闭所有弹窗（广告、通知、引导等），点击关闭按钮或页面空白处
4. 点击页面顶部的地址栏（通常显示当前位置或"选择地址"）
5. 如果出现城市选择，找到并点击"{city}"
6. 在地址搜索框中输入"{address}"
7. 等待搜索建议列表出现
8. 点击第一个包含"{address}"的搜索结果
9. 确认返回首页，检查顶部地址是否包含"{city}"或"{address}"

【成功标准】
- 页面顶部显示的地址包含"{address}"相关内容
- 成功后回复: SUCCESS: [实际显示的地址]

【失败处理】
- 如果遇到403错误，等待5秒后刷新页面重试
- 如果遇到验证码，回复: CAPTCHA
- 如果其他原因失败，回复: FAILED: [具体原因]

【注意】
- 这是中文网页，所有按钮和文字都是中文
- 每个操作后等待1-2秒让页面响应
- 不要着急，确保每一步都完成后再进行下一步
"""
        
        print(f"\n🤖 AI Agent 开始执行任务...")
        print(f"   目标: {city} {address}")
        print("-" * 50)
        
        try:
            agent = Agent(
                task=task,
                llm=self.llm,
                browser=self.browser,
            )
            
            # 运行 Agent，最多30步
            history = await agent.run(max_steps=30)
            
            # 获取结果
            result = history.final_result() if history else None
            result_str = str(result) if result else ""
            
            print("-" * 50)
            
            if "SUCCESS" in result_str.upper():
                print(f"✅ 地址设置成功!")
                return {"success": True, "result": result_str}
            elif "CAPTCHA" in result_str.upper():
                print(f"⚠️ 遇到验证码，需要人工处理")
                return {"success": False, "error": "captcha", "result": result_str}
            else:
                print(f"❌ 地址设置失败: {result_str[:100]}")
                return {"success": False, "error": "failed", "result": result_str}
                
        except Exception as e:
            print(f"❌ 执行出错: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def search_and_extract(self, keyword: str) -> Dict[str, Any]:
        """
        搜索商品并提取价格数据
        
        Args:
            keyword: 搜索关键词，如"农夫山泉"
            
        Returns:
            包含价格数据的字典
        """
        from browser_use import Agent
        
        task = f"""
你需要在当前的美团外卖页面搜索商品并提取价格信息。

【任务步骤】
1. 找到搜索框（通常在页面顶部），点击它
2. 输入搜索关键词: {keyword}
3. 点击搜索按钮或按回车
4. 等待搜索结果加载
5. 从搜索结果中提取信息

【需要提取的数据】
对于搜索结果中的前10个商品/店铺，提取：
- 店铺名称
- 商品价格（数字，如 2.5）
- 距离（如果有）

【返回格式】
请以 JSON 格式返回数据：
```json
{{
  "keyword": "{keyword}",
  "count": 10,
  "items": [
    {{"shop": "店铺名", "price": 2.5, "distance": "500m"}},
    {{"shop": "店铺名2", "price": 3.0, "distance": "800m"}}
  ]
}}
```

【注意】
- 价格只取数字部分，不要包含￥符号
- 如果没有搜索结果，返回空的 items 数组
- 如果遇到错误，说明原因
"""
        
        print(f"\n🔍 AI Agent 搜索商品: {keyword}")
        print("-" * 50)
        
        try:
            agent = Agent(
                task=task,
                llm=self.llm,
                browser=self.browser,
            )
            
            history = await agent.run(max_steps=20)
            result = history.final_result() if history else None
            
            print("-" * 50)
            print(f"📊 搜索完成")
            
            # 尝试解析 JSON
            if result:
                import json
                import re
                # 提取 JSON 部分
                json_match = re.search(r'\{[\s\S]*\}', str(result))
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                        return {"success": True, "data": data}
                    except json.JSONDecodeError:
                        pass
            
            return {"success": True, "data": {"keyword": keyword, "raw": str(result)}}
            
        except Exception as e:
            print(f"❌ 搜索出错: {e}")
            return {"success": False, "error": str(e)}


# ==================== 测试函数 ====================
async def run_full_poc():
    """运行完整 POC 测试"""
    
    print("\n" + "=" * 60)
    print("🚀 闪价雷达 - Browser Use POC 测试")
    print("=" * 60)
    print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查依赖
    if not check_dependencies():
        return
    
    # 检查 API Key
    llm_provider = "anthropic"
    if os.getenv("ANTHROPIC_API_KEY"):
        llm_provider = "anthropic"
        print("✅ 使用 Claude API")
    elif os.getenv("DEEPSEEK_API_KEY"):
        llm_provider = "deepseek"
        print("✅ 使用 DeepSeek API")
    else:
        print("❌ 请设置 ANTHROPIC_API_KEY 或 DEEPSEEK_API_KEY")
        return
    
    # 创建导航器
    navigator = MeituanAINavigator(llm_provider=llm_provider)
    
    try:
        # 1. 初始化
        print("\n📱 步骤1: 初始化")
        await navigator.init(headless=False)  # 非无头模式方便观察
        
        # 2. 设置地址
        print("\n📍 步骤2: AI 设置地址")
        result = await navigator.setup_location(
            city="重庆",
            address="南坪步行街"
        )
        
        if not result["success"]:
            print(f"\n⚠️ 地址设置失败，但继续测试搜索功能...")
        
        # 3. 搜索商品
        print("\n🔍 步骤3: AI 搜索商品")
        search_result = await navigator.search_and_extract("农夫山泉")
        
        # 4. 显示结果
        print("\n" + "=" * 60)
        print("📊 POC 测试结果汇总")
        print("=" * 60)
        
        print(f"\n地址设置: {'✅ 成功' if result['success'] else '❌ 失败'}")
        print(f"   详情: {result.get('result', result.get('error', 'N/A'))[:100]}")
        
        print(f"\n商品搜索: {'✅ 成功' if search_result['success'] else '❌ 失败'}")
        if search_result.get("data"):
            data = search_result["data"]
            if "items" in data:
                print(f"   找到 {len(data['items'])} 条价格数据:")
                for item in data["items"][:5]:
                    print(f"   🏪 {item.get('shop', 'N/A')}: ¥{item.get('price', 'N/A')}")
            else:
                print(f"   原始结果: {str(data)[:200]}...")
        
        # 等待观察
        print("\n⏸️ 浏览器保持打开 30 秒，方便观察...")
        await asyncio.sleep(30)
        
    finally:
        await navigator.close()
    
    print("\n" + "=" * 60)
    print("✅ POC 测试完成!")
    print("=" * 60)


async def run_simple_test():
    """简单测试 - 验证 Browser Use 是否工作"""
    
    print("\n" + "=" * 60)
    print("🧪 Browser Use 简单测试")
    print("=" * 60)
    
    if not check_dependencies():
        return
    
    from browser_use import Agent, Browser
    
    # 确定使用哪个 LLM
    if os.getenv("ANTHROPIC_API_KEY"):
        llm = create_llm("anthropic")
        print("✅ 使用 Claude")
    elif os.getenv("DEEPSEEK_API_KEY"):
        llm = create_llm("deepseek")
        print("✅ 使用 DeepSeek")
    else:
        print("❌ 请设置 API Key")
        return
    
    browser = Browser()
    
    print("\n🌐 测试任务: 打开百度并获取页面标题")
    
    agent = Agent(
        task="打开 https://www.baidu.com，告诉我页面的标题是什么",
        llm=llm,
        browser=browser,
    )
    
    try:
        history = await agent.run(max_steps=5)
        result = history.final_result() if history else None
        print(f"\n✅ 测试成功!")
        print(f"   结果: {result}")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
    finally:
        await browser.close()


# ==================== 主入口 ====================
if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--simple":
            asyncio.run(run_simple_test())
        elif sys.argv[1] == "--help":
            print("""
闪价雷达 - Browser Use POC

用法:
  python poc_browser_use.py           # 运行完整 POC 测试
  python poc_browser_use.py --simple  # 运行简单测试
  python poc_browser_use.py --help    # 显示帮助

环境变量:
  ANTHROPIC_API_KEY    Claude API 密钥（推荐）
  DEEPSEEK_API_KEY     DeepSeek API 密钥（便宜）
  OPENAI_API_KEY       OpenAI API 密钥

安装:
  pip install browser-use langchain-anthropic
  playwright install chromium
""")
        else:
            print(f"未知参数: {sys.argv[1]}")
    else:
        asyncio.run(run_full_poc())
