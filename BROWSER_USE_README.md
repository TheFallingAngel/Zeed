# 🤖 Browser Use 集成说明

## 概述

本项目集成了 [Browser Use](https://github.com/browser-use/browser-use) AI Agent 框架，实现了**混合策略爬虫**：

- **AI Agent 层**：处理复杂交互（弹窗、地址选择、异常恢复）
- **Playwright 层**：快速精准的数据提取

## 架构

```
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
│   │  - 验证码处理     │    │  - 快速准确       │   │
│   │  - 异常恢复       │    │                   │   │
│   └───────────────────┘    └───────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 安装依赖

```bash
# 基础依赖
pip install playwright
playwright install chromium

# AI Agent 依赖
pip install browser-use langchain-anthropic

# 或使用 DeepSeek（更便宜）
pip install browser-use langchain-openai
```

### 2. 配置 API Key

```bash
# Claude API（推荐，效果最好）
export ANTHROPIC_API_KEY=your-claude-api-key

# 或 DeepSeek API（便宜，约 ¥1/百万token）
export DEEPSEEK_API_KEY=your-deepseek-api-key
```

### 3. 运行测试

```bash
# POC 测试
python poc_browser_use.py

# 简单测试
python poc_browser_use.py --simple

# 混合爬虫测试
python -m crawler.hybrid_crawler
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `poc_browser_use.py` | Browser Use POC，独立测试 AI 导航功能 |
| `crawler/hybrid_crawler.py` | 混合策略爬虫，集成 AI + Playwright |
| `crawler/meituan_crawler.py` | 原始 Playwright 爬虫（备用） |
| `requirements_ai.txt` | AI 相关依赖 |

## 使用方式

### 方式1：完整 AI 模式

```python
from crawler.hybrid_crawler import HybridMeituanCrawler, crawl_prices
from config import PILOT_LOCATIONS

# 使用便捷函数
results = await crawl_prices(
    location=PILOT_LOCATIONS[0],
    products=["农夫山泉", "红牛"],
    use_ai=True,  # 启用 AI
)

# 或手动控制
crawler = HybridMeituanCrawler(use_ai=True, llm_provider="anthropic")
await crawler.init_browser(location, headless=False)
results = await crawler.crawl_products(["农夫山泉", "红牛"])
await crawler.close()
```

### 方式2：纯 Playwright 模式（无需 API Key）

```python
crawler = HybridMeituanCrawler(use_ai=False)
await crawler.init_browser(location, headless=True)
results = await crawler.crawl_products(["农夫山泉"])
await crawler.close()
```

## LLM 选择

| 提供商 | 模型 | 价格 | 效果 | 推荐 |
|--------|------|------|------|------|
| Anthropic | Claude Sonnet | ~$3/M tokens | ⭐⭐⭐⭐⭐ | ✅ 推荐 |
| DeepSeek | deepseek-chat | ~¥1/M tokens | ⭐⭐⭐⭐ | ✅ 便宜 |
| OpenAI | GPT-4o | ~$5/M tokens | ⭐⭐⭐⭐ | 备选 |

### 切换 LLM

```python
# Claude（默认）
crawler = HybridMeituanCrawler(llm_provider="anthropic")

# DeepSeek
crawler = HybridMeituanCrawler(llm_provider="deepseek")

# OpenAI
crawler = HybridMeituanCrawler(llm_provider="openai")
```

## 成本估算

| 场景 | 每日采集量 | Claude 成本 | DeepSeek 成本 |
|------|-----------|-------------|---------------|
| 测试 | 10 商品 | ~¥1 | ~¥0.1 |
| 轻度 | 50 商品 | ~¥5 | ~¥0.5 |
| 中度 | 100 商品 | ~¥10 | ~¥1 |
| 重度 | 500 商品 | ~¥50 | ~¥5 |

## 工作原理

### AI Agent 做什么？

1. **智能导航**：理解页面结构，自动完成复杂交互
2. **弹窗处理**：自动关闭广告、通知、引导弹窗
3. **地址设置**：选择城市、搜索地址、点击结果
4. **异常恢复**：遇到错误自动重试

### Playwright 做什么？

1. **快速搜索**：直接操作 DOM，速度快
2. **数据提取**：结构化提取价格、店铺名、距离
3. **批量采集**：高效处理多个商品

### 为什么混合？

| 场景 | AI Agent | Playwright | 混合策略 |
|------|----------|------------|----------|
| 地址设置 | ✅ 智能 | ❌ 脆弱 | AI |
| 弹窗处理 | ✅ 灵活 | ⚠️ 需维护 | AI |
| 数据提取 | ⚠️ 慢 | ✅ 快速 | Playwright |
| 成本 | 💰 较高 | 🆓 免费 | 平衡 |

## 常见问题

### Q: 没有 API Key 能用吗？

可以！会自动回退到纯 Playwright 模式，但地址设置可能不稳定。

### Q: 遇到 403 错误怎么办？

1. AI 模式会自动重试
2. 可以使用代理 IP
3. 降低采集频率

### Q: DeepSeek 效果如何？

DeepSeek 效果接近 Claude，但价格只有 1/10，推荐用于生产环境。

### Q: 如何调试？

```bash
# 非无头模式运行
export CRAWLER_HEADLESS=false
python poc_browser_use.py
```

## 下一步

1. [ ] 添加代理 IP 支持
2. [ ] 实现 CAPTCHA 自动处理
3. [ ] 支持饿了么平台
4. [ ] 添加数据持久化
