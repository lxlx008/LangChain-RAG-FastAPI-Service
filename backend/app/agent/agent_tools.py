from typing import List, Optional
from contextvars import ContextVar
import os  # 环境变量
import aiohttp  # 异步HTTP请求
import datetime  # 用于获取当前时间

from langchain_core.tools import tool

from app.core.logger_handler import logger
from app.rag.rag_service import RagService
from app.rag.reorder_service import reorder_service
from app.utils.auth_utils import decode_django_jwt, get_weather_auth_headers

current_user_id_var: ContextVar[str] = ContextVar('current_user_id', default=None)
thinking_callback_var: ContextVar[Optional[callable]] = ContextVar('thinking_callback', default=None)

def set_current_user_id(user_id: str):
    """设置当前用户ID到上下文"""
    current_user_id_var.set(user_id)

def get_current_user_id_from_context() -> str:
    """从上下文获取当前用户ID"""
    return current_user_id_var.get()

def set_thinking_callback(callback):
    """设置思考过程回调到上下文"""
    thinking_callback_var.set(callback)

def get_thinking_callback_from_context():
    """从上下文获取思考过程回调"""
    return thinking_callback_var.get()

@tool(description="用于从向量数据库里检索文档并生成摘要，返回包含文档列表和摘要的结果。返回格式为：'摘要: [摘要内容]\n\n检索到的文档列表:\n1. [文档1内容]\n2. [文档2内容]\n...'。注意：文档已经过自动重排序，无需再调用重排序工具")
async def rag_summary_tools(query: str, user_id: str = None) -> str:
    """RAG 摘要工具"""
    effective_user_id = user_id or get_current_user_id_from_context()
    if not effective_user_id:
        return "错误: 无法确定用户身份，请提供有效的user_id"
    
    thinking_callback = get_thinking_callback_from_context()
    result = await RagService(effective_user_id, thinking_callback=thinking_callback).get_documents_and_summary(query)
    documents = result.get("documents", [])
    summary = result.get("summary", "")

    formatted_result = f"摘要: {summary}\n\n"
    formatted_result += "检索到的文档列表（已重排序）:\n"
    for i, doc in enumerate(documents, 1):
        formatted_result += f"{i}. {doc}\n"

    return formatted_result

@tool(description="用于对文档列表进行重排序，传入查询语句query和文档列表documents，返回重排序后的文档列表，包含文档内容和相似度。注意：rag_summary_tools已内置重排序功能，通常不需要单独调用此工具")
async def reorder_documents_tools(query: str, documents: List[str]) -> str:
    """重排序文档工具"""
    thinking_callback = get_thinking_callback_from_context()
    result = await reorder_service.reorder_documents(query, documents, thinking_callback=thinking_callback)
    if result["success"]:
        # 格式化返回结果
        formatted_result = await reorder_service.format_reorder_result(result["documents"])
        # 记录日志 
        logger.info(formatted_result)
        return formatted_result
    else:
        return f"重排序失败: {result['error']}"

@tool(description="当用户明确问自己的ID和用户名时，从JWT中获取当前用户ID和用户名，参数为完整的JWT token字符串")
async def get_user_info_tools(token: str) -> str:
    """获取用户信息工具"""
    payload = decode_django_jwt(token)
    if payload:
        user_id = payload.get("user_id", "未知")
        user_name = payload.get("user_name", "未知")
        return f"用户信息：\n- 用户ID: {user_id}\n- 用户名: {user_name}"
    else:
        return "无法解析JWT token，无法获取用户信息"


@tool(description="用于获取天气信息，需要提供城市名称作为参数，你需要从用户输入中提取城市名称，是str类型")
async def get_weather_tools(city: str = None) -> str:
    """获取天气工具（支持 JWT 和 API KEY 两种认证方式）"""
    if not city:
        return "请提供城市名称"
    
    try:
        auth_type = os.getenv("WEATHER_AUTH_TYPE", "JWT").upper()
        
        async with aiohttp.ClientSession() as session:
            if auth_type == "JWT":
                # JWT 认证方式
                headers = get_weather_auth_headers()
                jwt_host = os.getenv("WEATHER_JWT_HOST", "kq57rmw277.re.qweatherapi.com")
                
                logger.info(f"使用 JWT 认证查询天气: {city}", extra={"path": "agent_tools.get_weather_tools"})
                
                # 城市搜索：使用 /geo/v2/city/lookup 端点
                async with session.get(
                    f"https://{jwt_host}/geo/v2/city/lookup",
                    params={"location": city},
                    headers=headers
                ) as response:
                    search_data = await response.json()
                    if search_data.get("code") != "200" or not search_data.get("location"):
                        return f"未找到城市: {city}"
                    city_id = search_data["location"][0]["id"]
                    city_name = search_data["location"][0]["name"]
                
                # 查询天气
                async with session.get(
                    f"https://{jwt_host}/v7/weather/now",
                    params={"location": city_id},
                    headers=headers
                ) as response:
                    weather_res = await response.json()
                    if weather_res.get("code") != "200":
                        return f"获取天气信息失败,错误码:{weather_res['code']},错误信息:{weather_res.get('msg', '未知错误')}"
                    weather_info = weather_res["now"]
                    return f"【{city_name}】实时天气\n" \
                        f"温度: {weather_info['temp']}C\n" \
                        f"状况: {weather_info['text']}\n" \
                        f"风向: {weather_info['windDir']} {weather_info['windScale']}级\n" \
                        f"湿度: {weather_info['humidity']}%\n" \
                        f"风速: {weather_info['windSpeed']} km/h"
            else:
                # API KEY 认证方式
                api_key = os.getenv("WEATHER_API_KEY")
                if not api_key:
                    return "未配置天气 API Key"
                
                # 搜索城市
                async with session.get(
                    "https://geoapi.qweather.com/v2/city/lookup",
                    params={"location": city, "key": api_key}
                ) as response:
                    search_data = await response.json()
                    if search_data.get("code") != "200" or not search_data.get("location"):
                        return f"未找到城市: {city}"
                    city_id = search_data["location"][0]["id"]
                    city_name = search_data["location"][0]["name"]
                
                # 查询实时天气
                async with session.get(
                    "https://devapi.qweather.com/v7/weather/now",
                    params={"location": city_id, "key": api_key}
                ) as response:
                    weather_res = await response.json()
                    if weather_res.get("code") != "200":
                        return f"获取天气信息失败,错误码:{weather_res['code']},错误信息:{weather_res.get('msg', '未知错误')}"
                    weather_info = weather_res["now"]
                    return f"【{city_name}】实时天气\n" \
                        f"温度: {weather_info['temp']}C\n" \
                        f"状况: {weather_info['text']}\n" \
                        f"风向: {weather_info['windDir']} {weather_info['windScale']}级\n" \
                        f"湿度: {weather_info['humidity']}%\n" \
                        f"风速: {weather_info['windSpeed']} km/h"
    except Exception as e:
        logger.error(f"获取天气信息失败: {str(e)}")
        return f"获取天气信息失败:{str(e)}，请稍后再试或联系管理员"


@tool(description="用于获取当前年月日时分的工具")
async def what_time_is_now() -> str:
    """获取当前年月日时分的工具"""
    return f"当前时间是：{datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}"