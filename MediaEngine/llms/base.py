"""
Unified OpenAI-compatible LLM client for the Media Engine, with retry support.

支持 DeepSeek 备用模型：当主模型触发内容安全审核时，自动切换到 DeepSeek 重试。
"""

import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional, Generator
from loguru import logger

from openai import OpenAI


def _get_deepseek_config() -> Optional[Dict[str, str]]:
    """获取 DeepSeek 备用配置"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model_name = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")

    if api_key:
        return {
            "api_key": api_key,
            "base_url": base_url,
            "model_name": model_name,
        }
    return None


# Ensure project-level retry helper is importable
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
utils_dir = os.path.join(project_root, "utils")
if utils_dir not in sys.path:
    sys.path.append(utils_dir)

try:
    from retry_helper import with_retry, LLM_RETRY_CONFIG
except ImportError:
    def with_retry(config=None):
        def decorator(func):
            return func
        return decorator

    LLM_RETRY_CONFIG = None


class LLMClient:
    """
    Minimal wrapper around the OpenAI-compatible chat completion API.
    """

    def __init__(self, api_key: str, model_name: str, base_url: Optional[str] = None):
        if not api_key:
            raise ValueError("Media Engine LLM API key is required.")
        if not model_name:
            raise ValueError("Media Engine model name is required.")

        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.provider = model_name
        timeout_fallback = os.getenv("LLM_REQUEST_TIMEOUT") or os.getenv("MEDIA_ENGINE_REQUEST_TIMEOUT") or "1800"
        try:
            self.timeout = float(timeout_fallback)
        except ValueError:
            self.timeout = 1800.0

        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "max_retries": 0,
        }
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)

    @with_retry(LLM_RETRY_CONFIG)
    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        current_time = datetime.now().strftime("%Y年%m月%d日%H时%M分")
        time_prefix = f"今天的实际时间是{current_time}"
        if user_prompt:
            user_prompt = f"{time_prefix}\n{user_prompt}"
        else:
            user_prompt = time_prefix
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        allowed_keys = {"temperature", "top_p", "presence_penalty", "frequency_penalty", "stream"}
        extra_params = {key: value for key, value in kwargs.items() if key in allowed_keys and value is not None}

        timeout = kwargs.pop("timeout", self.timeout)

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                timeout=timeout,
                **extra_params,
            )

            if response.choices and response.choices[0].message:
                return self.validate_response(response.choices[0].message.content)
            return ""

        except Exception as e:
            error_msg = str(e).lower()

            # 检测内容审查错误，使用 DeepSeek 备用模型
            if 'inappropriate content' in error_msg or 'content policy' in error_msg:
                logger.warning(f"[MediaEngine] 内容审查触发，尝试使用 DeepSeek 备用模型...")

                deepseek_config = _get_deepseek_config()
                if not deepseek_config:
                    logger.error("DeepSeek 配置未设置，无法使用备用模型")
                    raise

                try:
                    deepseek_client = OpenAI(
                        api_key=deepseek_config["api_key"],
                        base_url=deepseek_config["base_url"],
                        max_retries=0,
                    )

                    response = deepseek_client.chat.completions.create(
                        model=deepseek_config["model_name"],
                        messages=messages,
                        timeout=timeout,
                        **extra_params,
                    )

                    if response.choices and response.choices[0].message:
                        logger.info("[MediaEngine] DeepSeek 备用模型调用成功")
                        return self.validate_response(response.choices[0].message.content)
                    return ""

                except Exception as deepseek_error:
                    logger.error(f"[MediaEngine] DeepSeek 备用模型也失败: {deepseek_error}")
                    raise

            # 其他错误直接抛出
            raise

    def stream_invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> Generator[str, None, None]:
        """
        流式调用LLM，逐步返回响应内容
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 额外参数（temperature, top_p等）
            
        Yields:
            响应文本块（str）
        """
        current_time = datetime.now().strftime("%Y年%m月%d日%H时%M分")
        time_prefix = f"今天的实际时间是{current_time}"
        if user_prompt:
            user_prompt = f"{time_prefix}\n{user_prompt}"
        else:
            user_prompt = time_prefix
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        allowed_keys = {"temperature", "top_p", "presence_penalty", "frequency_penalty"}
        extra_params = {key: value for key, value in kwargs.items() if key in allowed_keys and value is not None}
        # 强制使用流式
        extra_params["stream"] = True

        timeout = kwargs.pop("timeout", self.timeout)

        try:
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                timeout=timeout,
                **extra_params,
            )
            
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
        except Exception as e:
            logger.error(f"流式请求失败: {str(e)}")
            raise e
    
    @with_retry(LLM_RETRY_CONFIG)
    def stream_invoke_to_string(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        流式调用LLM并安全地拼接为完整字符串（避免UTF-8多字节字符截断）

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 额外参数（temperature, top_p等）

        Returns:
            完整的响应字符串
        """
        try:
            # 以字节形式收集所有块
            byte_chunks = []
            for chunk in self.stream_invoke(system_prompt, user_prompt, **kwargs):
                byte_chunks.append(chunk.encode('utf-8'))

            # 拼接所有字节，然后一次性解码
            if byte_chunks:
                return b''.join(byte_chunks).decode('utf-8', errors='replace')
            return ""

        except Exception as e:
            error_msg = str(e).lower()

            # 检测内容审查错误，使用 DeepSeek 备用模型
            if 'inappropriate content' in error_msg or 'content policy' in error_msg:
                logger.warning(f"[MediaEngine][stream] 内容审查触发，尝试使用 DeepSeek 备用模型...")

                deepseek_config = _get_deepseek_config()
                if not deepseek_config:
                    logger.error("DeepSeek 配置未设置，无法使用备用模型")
                    raise

                try:
                    deepseek_client = OpenAI(
                        api_key=deepseek_config["api_key"],
                        base_url=deepseek_config["base_url"],
                        max_retries=0,
                    )

                    current_time = datetime.now().strftime("%Y年%m月%d日%H时%M分")
                    time_prefix = f"今天的实际时间是{current_time}"
                    full_user_prompt = f"{time_prefix}\n{user_prompt}" if user_prompt else time_prefix

                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": full_user_prompt},
                    ]

                    allowed_keys = {"temperature", "top_p", "presence_penalty", "frequency_penalty"}
                    extra_params = {key: value for key, value in kwargs.items() if key in allowed_keys and value is not None}
                    extra_params["stream"] = True

                    timeout = kwargs.get("timeout", self.timeout)

                    stream = deepseek_client.chat.completions.create(
                        model=deepseek_config["model_name"],
                        messages=messages,
                        timeout=timeout,
                        **extra_params,
                    )

                    byte_chunks = []
                    for chunk in stream:
                        if chunk.choices and len(chunk.choices) > 0:
                            delta = chunk.choices[0].delta
                            if delta and delta.content:
                                byte_chunks.append(delta.content.encode('utf-8'))

                    if byte_chunks:
                        logger.info("[MediaEngine] DeepSeek 备用模型流式调用成功")
                        return b''.join(byte_chunks).decode('utf-8', errors='replace')
                    return ""

                except Exception as deepseek_error:
                    logger.error(f"[MediaEngine] DeepSeek 备用模型也失败: {deepseek_error}")
                    raise

            # 其他错误直接抛出
            raise

    @staticmethod
    def validate_response(response: Optional[str]) -> str:
        if response is None:
            return ""
        return response.strip()

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model_name,
            "api_base": self.base_url or "default",
        }
