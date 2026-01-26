#!/usr/bin/env python3
"""
测试 Orchestrator LLM 调用
用于诊断为什么 Orchestrator 的 LLM 调用总是超时
"""

import os
from pathlib import Path
from openai import OpenAI

# 加载 .env 文件
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# 读取环境变量
api_key = os.getenv('QUERY_ENGINE_API_KEY')
base_url = os.getenv('QUERY_ENGINE_BASE_URL')
model_name = os.getenv('QUERY_ENGINE_MODEL_NAME', 'gpt-4')

print("=" * 60)
print("Orchestrator LLM 配置测试")
print("=" * 60)
print(f"API Key: {api_key[:20]}..." if api_key else "未配置")
print(f"Base URL: {base_url}")
print(f"Model Name: {model_name}")
print("=" * 60)
print()

if not api_key:
    print("❌ 错误: QUERY_ENGINE_API_KEY 未配置")
    exit(1)

# 创建客户端
client_kwargs = {"api_key": api_key, "max_retries": 0}
if base_url:
    client_kwargs["base_url"] = base_url

client = OpenAI(**client_kwargs)

# 简单测试
test_prompt = "你是一个研究项目的协调者。请简单回复'OK'来确认收到消息。"

print("开始测试 LLM 调用（30秒超时）...")
print()

try:
    import time
    start_time = time.time()

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "你是一个助手。"},
            {"role": "user", "content": test_prompt}
        ],
        timeout=30.0,
        max_tokens=50  # 限制输出长度
    )

    elapsed = time.time() - start_time

    if response.choices and response.choices[0].message:
        content = response.choices[0].message.content or ""
        print(f"✓ LLM 调用成功！")
        print(f"  耗时: {elapsed:.2f} 秒")
        print(f"  响应: {content[:100]}")
        print()
        print("✓ Orchestrator LLM 配置正常")
    else:
        print("❌ LLM 返回空响应")
        print(f"  耗时: {elapsed:.2f} 秒")

except Exception as e:
    print(f"❌ LLM 调用失败: {e}")
    print()
    print("可能的原因：")
    print("1. API 密钥无效或过期")
    print("2. 模型名称错误（DashScope 可能不支持 deepseek-v3）")
    print("3. 网络连接问题")
    print("4. API 服务限流")
    print()
    print("建议：")
    print("1. 检查 .env 中的 QUERY_ENGINE_API_KEY 是否正确")
    print("2. 尝试修改 QUERY_ENGINE_MODEL_NAME 为 DashScope 支持的模型")
    print("   - qwen-plus")
    print("   - qwen-max")
    print("   - qwen-turbo")
    print("3. 或者暂时禁用 Orchestrator LLM 决策（自动 approve）")
