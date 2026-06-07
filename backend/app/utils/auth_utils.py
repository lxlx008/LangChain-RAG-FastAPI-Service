import os
import json
import time
import base64
from typing import Optional, Dict, Any
import requests
from dotenv import load_dotenv
from jose import JWTError, jwt as jose_jwt
import jwt  # PyJWT - 用于 EdDSA JWT 生成
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.failed_response import logger
from app.db.redis_config import connect_redis, set_redis_cache

load_dotenv()

# Django JWT配置
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

# 创建Bearer认证方案
security = HTTPBearer()


def decode_django_jwt(token: str) -> Optional[Dict[str, Any]]:
    """解析Django生成的JWT token
    
    Args:
        token: JWT token字符串
        
    Returns:
        解析后的payload，如果解析失败返回None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """从Django JWT中获取当前用户UUID
    
    Args:
        credentials: HTTP认证凭据
        
    Returns:
        用户的UUID
        
    Raises:
        HTTPException: 认证失败时抛出
    """
    token = credentials.credentials
    payload = decode_django_jwt(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查JWT是否在黑名单中
    jti = payload.get("jti")
    logger.info(f"【debug】 检查JWT是否在黑名单中，jti: {jti}", extra={"path": "auth_utils.get_current_user_id"})
    if jti:
        redis_client = await connect_redis()
        # 使用通配符查询所有可能的黑名单键格式
        # 匹配任何前缀的blacklist键，如:1:blacklist:{jti}、blacklist:{jti}等
        wildcard_pattern = f"*blacklist:{jti}"
        
        # 获取所有匹配的键
        matching_keys = await redis_client.keys(wildcard_pattern)
        logger.info(f"【debug】 检查JWT是否在黑名单中，匹配的键: {matching_keys}", extra={"path": "auth_utils.get_current_user_id"})
        
        # 如果有匹配的键，说明JWT在黑名单中
        if matching_keys:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 从Django JWT中提取user_id（uuid）
    user_id: str = payload.get("user_id")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not find user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_id


async def fetch_user_info_from_django_api(token: str, url: str) -> Optional[Dict[str, Any]]:
    """从Django API获取用户信息
    
    Args:
        token: JWT token字符串
        
    Returns:
        用户信息字典，如果获取失败返回None
    """

    try:
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        # 调用Django API
        response = requests.get(
            url=url,
            headers=headers
        )
        
        if response.status_code == 200:
            user_data = response.json()
            logger.info(f"【debug】 从Django API获取用户信息成功", extra={"path": "auth_utils.fetch_user_info_from_django_api"})
            return user_data
        else:
            logger.error(f"【debug】 从Django API获取用户信息失败，status_code: {response.status_code}", extra={"path": "auth_utils.fetch_user_info_from_django_api"})
            return None
    except Exception as e:
        logger.error(f"【debug】 调用Django API时出错: {str(e)}", extra={"path": "auth_utils.fetch_user_info_from_django_api"})
        return None


async def get_user_info_from_redis(user_id: str, credentials: HTTPAuthorizationCredentials):
    """从Redis中获取用户信息
    
    Args:
        user_id: 用户ID
        credentials: HTTP认证凭据
        
    Returns:
        用户信息
    """
    redis_client = await connect_redis()
    key = f":1:user:{user_id}"
    
    try:
        # 从Redis中获取用户信息
        user_info = await redis_client.get(key)
        if user_info is None:
            # 降级调用django查询用户信息
            user_data = await fetch_user_info_from_django_api(credentials.credentials, os.getenv("DJANGO_API_URL") + "/user/detail/")
            if user_data:
                # 将用户信息存入Redis，设置过期时间为1小时
                await set_redis_cache(
                    key,
                    user_data,
                    expire=3600
                )
                user_info = user_data
        else:
            # 如果从Redis中获取到数据，尝试将其解析为字典
            try:
                
                user_info = json.loads(user_info)
            except json.JSONDecodeError:
                # 如果解析失败，删除旧数据并重新获取
                await redis_client.delete(key)
                user_data = await fetch_user_info_from_django_api(credentials.credentials, os.getenv("DJANGO_API_URL") + "/user/detail/")
                if user_data:
                    await set_redis_cache(
                        key,
                        user_data,
                        expire=3600
                    )
                    user_info = user_data
                else:
                    user_info = None
    except UnicodeDecodeError:
        # 处理解码错误，删除旧数据并重新获取
        await redis_client.delete(key)
        user_data = await fetch_user_info_from_django_api(credentials.credentials, os.getenv("DJANGO_API_URL") + "/user/detail/")
        if user_data:
            await set_redis_cache(
                key,
                user_data,
                expire=3600
            )
            user_info = user_data
        else:
            user_info = None

    return user_info


# ==============================================
# 和风天气 JWT 认证模块
# ==============================================

import time as time_module


def generate_qweather_jwt_token() -> str:
    """
    生成和风天气 JWT Token

    使用 Ed25519 算法签名，包含：
    - sub: 项目ID
    - kid: 凭证ID
    - iat: 签发时间
    - exp: 过期时间

    Returns:
        JWT Token 字符串
    """
    # 从环境变量读取配置
    private_key_path = os.getenv("WEATHER_JWT_PRIVATE_KEY_PATH")
    sub = os.getenv("WEATHER_JWT_SUB")
    kid = os.getenv("WEATHER_JWT_KID")
    expiration_hours = int(os.getenv("WEATHER_JWT_EXPIRATION_HOURS", "24"))

    if not private_key_path or not sub or not kid:
        raise ValueError("JWT 认证配置不完整：缺少私钥路径、sub 或 kid")

    # 读取私钥文件
    if not os.path.exists(private_key_path):
        raise FileNotFoundError(f"私钥文件不存在: {private_key_path}")

    with open(private_key_path, "r") as f:
        private_key = f.read()

    # JWT 载荷（参考和风天气官方文档）
    payload = {
        "sub": sub,
        "iat": int(time_module.time()) - 30,
        "exp": int(time_module.time()) + (expiration_hours * 3600) - 60,
    }

    # JWT 头部
    headers = {
        "alg": "EdDSA",
        "kid": kid
    }

    # 使用 PyJWT 生成 EdDSA JWT
    token = jwt.encode(payload, private_key, algorithm="EdDSA", headers=headers)

    # 打印 JWT Token 到日志（用于手动验证）
    logger.info(f"生成和风天气 JWT Token（sub: {sub}, kid: {kid}）", extra={"path": "auth_utils.generate_qweather_jwt_token"})
    logger.info(f"JWT Token: {token}", extra={"path": "auth_utils.generate_qweather_jwt_token"})
    return token


# ==============================================
# JWT Token 缓存机制
# ==============================================
_qweather_jwt_token_cache = {
    "token": None,
    "generated_at": None,
    "expires_in": 24 * 60 * 60  # 24小时（秒）
}


def get_weather_auth_headers() -> dict:
    """
    获取和风天气认证头

    根据配置自动选择认证方式：
    - JWT: 使用 Bearer Token（带缓存和自动续期）
    - KEY: 使用 API Key 查询参数

    Returns:
        认证头字典（包含 Authorization 或空字典）
    """
    auth_type = os.getenv("WEATHER_AUTH_TYPE", "KEY").upper()

    if auth_type == "JWT":
        return _get_cached_qweather_jwt_token()
    else:
        # API KEY 方式不需要额外的认证头，key 会作为查询参数
        return {}


def _get_cached_qweather_jwt_token() -> dict:
    """
    获取缓存的 JWT Token，自动续期

    缓存策略：
    1. 如果缓存的 Token 存在且未过期，直接返回
    2. 如果 Token 不存在或已过期，重新生成并缓存

    Returns:
        包含 Authorization 的请求头
    """
    current_time = time.time()

    # 检查缓存是否存在且有效
    if (_qweather_jwt_token_cache["token"] is not None and
        _qweather_jwt_token_cache["generated_at"] is not None):

        # 计算已过时间
        elapsed = current_time - _qweather_jwt_token_cache["generated_at"]

        # 如果 Token 还未过期（预留 5 分钟缓冲），直接返回缓存
        if elapsed < (_qweather_jwt_token_cache["expires_in"] - 300):
            logger.debug(f"使用缓存的 JWT Token（已缓存 {int(elapsed)} 秒）", extra={"path": "auth_utils._get_cached_qweather_jwt_token"})
            return {"Authorization": f"Bearer {_qweather_jwt_token_cache['token']}"}

    # Token 不存在或已过期，重新生成
    logger.info("JWT Token 缓存未命中或已过期，生成新 Token...", extra={"path": "auth_utils._get_cached_qweather_jwt_token"})
    token = generate_qweather_jwt_token()

    # 更新缓存
    _qweather_jwt_token_cache["token"] = token
    _qweather_jwt_token_cache["generated_at"] = current_time

    return {"Authorization": f"Bearer {token}"}


def invalidate_qweather_jwt_token_cache():
    """
    清除 JWT Token 缓存

    用于强制重新生成 Token（例如私钥更换后）
    """
    _qweather_jwt_token_cache["token"] = None
    _qweather_jwt_token_cache["generated_at"] = None
    logger.info("JWT Token 缓存已清除", extra={"path": "auth_utils.invalidate_qweather_jwt_token_cache"})