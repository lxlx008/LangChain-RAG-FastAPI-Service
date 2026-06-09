# 项目部署指南

## 部署架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Vercel (前端)                                │
│              Vue 3 + Vite 静态站点 (免费)                           │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Render (后端 API)                             │
│                 FastAPI + LangChain (付费/免费层)                    │
└──────────┬──────────────────────┬──────────────────────┬────────────┘
           │                      │                      │
           ▼                      ▼                      ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────────┐
│   Aiven Redis    │ │  阿里云 MySQL     │ │  阿里云 DashScope API    │
│  (免费层)        │ │  (自备)           │ │  (按量付费)               │
└──────────────────┘ └──────────────────┘ └──────────────────────────┘
```

---

## 准备工作

### 1. 注册所需平台账号

| 平台 | 用途 | 地址 |
|------|------|------|
| Vercel | 前端部署 | https://vercel.com |
| Render | 后端部署 | https://render.com |
| Aiven | Redis 缓存 | https://aiven.io |
| 阿里云 | DashScope API + MySQL | https://dashscope.console.aliyun.com |

### 2. 获取 API 密钥

#### 阿里云 DashScope API Key

1. 访问 https://dashscope.console.aliyun.com/apiKey
2. 点击"创建新的 API Key"
3. 复制保存密钥（格式：`sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx`）

#### Redis（推荐 Aiven）

1. 访问 https://console.aiven.io/signup 注册
2. 创建 Redis 服务（选择免费层）
3. 获取连接信息：`rediss://username:password@host:port`

#### MySQL（推荐阿里云 RDS 或本地自备）

1. 创建 MySQL 数据库（版本 8.0+）
2. 创建数据库用户并授权
3. 记录以下信息：
   - 主机地址 (host)
   - 端口 (默认 3306)
   - 用户名
   - 密码
   - 数据库名

---

## 第一步：部署后端服务（Render）

### 1.1 将代码推送到 GitHub

```bash
cd LangChain-RAG-FastAPI-Service
git add -A
git commit -m "init deployment"
git push origin main
```

### 1.2 在 Render 上创建 Web Service

1. 访问 https://render.com 并登录
2. 点击 **"New +"** → **"Web Service"**
3. 选择你的 GitHub 仓库
4. 配置如下：

| 配置项 | 值 |
|--------|----|
| **Name** | `rag-backend` |
| **Region** | `Singapore` |
| **Branch** | `main` |
| **Root Directory** | `backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | `Starter` ($7/月，750小时/月) |

### 1.3 配置环境变量

在 Render 的 **Environment** 标签页中，添加以下环境变量：

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `PYTHON_VERSION` | Python 版本 | `3.11` |
| `LLM_TYPE` | LLM 类型 | `ALIYUN` |
| `EMBED_MODEL_TYPE` | 嵌入模型类型 | `ALIYUN` |
| `VISION_MODEL_TYPE` | 视觉模型类型 | `ALIYUN` |
| `ALIYUN_ACCESS_KEY_SECRET` | 阿里云 DashScope API Key | `sk-xxxxxxxxxx` |
| `MYSQL_HOST` | MySQL 主机 | `xxx.mysql.rds.aliyun.com` |
| `MYSQL_PORT` | MySQL 端口 | `3306` |
| `MYSQL_USER` | MySQL 用户名 | `admin` |
| `MYSQL_PASSWORD` | MySQL 密码 | `your_password` |
| `MYSQL_DATABASE` | MySQL 数据库名 | `rag_db` |
| `REDIS_HOST` | Redis 主机 | `xxx.aivencloud.com` |
| `REDIS_PORT` | Redis 端口 | `12345` |
| `REDIS_DB` | Redis 数据库编号 | `0` |
| `JWT_SECRET_KEY` | JWT 密钥（至少32字符随机字符串） | `your-32-char-secret-key-here` |
| `RATE_LIMIT_ENABLED` | 是否启用限流 | `false` |
| `LANGCHAIN_TRACING_V2` | LangChain 追踪 | `false` |
| `CHROMA_PERSIST_DIRECTORY` | Chroma 数据目录 | `./data/chroma` |
| `UPLOAD_DIR` | 上传文件目录 | `./data/uploads` |

**生成 JWT 密钥（本地命令）：**
```bash
# Windows PowerShell
-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | % {[char]$_})

# 或使用在线工具生成 32 位随机字符串
```

### 1.4 部署

点击 **"Create Web Service"** 开始部署。

首次部署可能需要 **5-10 分钟**（安装 Python 依赖包）。

部署成功后，你将获得一个访问地址，例如：
```
https://rag-backend-xxxx.onrender.com
```

**重要提示：**
- Render 免费层服务在 15 分钟无请求后会休眠，首次请求需要 30-60 秒冷启动
- 建议升级到 Starter 层（$7/月）以获得更好的稳定性

---

## 第二步：部署前端（Vercel）

### 2.1 修改前端 API 地址

编辑 [front/vercel.json](file:///e:/devsoftware/code/LangChain-RAG-FastAPI-Service/LangChain-RAG-FastAPI-Service/front/vercel.json)，将其中的 `your-render-app.onrender.com` 替换为你第一步获得的 Render 后端地址：

```json
{
  "rewrites": [
    {
      "source": "/api/agent/:path*",
      "destination": "https://your-render-app.onrender.com/api/agent/:path*"
    },
    ...
  ]
}
```

### 2.2 在 Vercel 上部署

**方式一：使用 Vercel 控制台（推荐）**

1. 访问 https://vercel.com 并登录
2. 点击 **"Add New..."** → **"Project"**
3. 选择你的 GitHub 仓库
4. 在 **"Configure Project"** 页面：
   - **Framework Preset**: `Vite`
   - **Root Directory**: 点击 **"Edit"** → 选择 `front` 目录
   - **Build Command**: 自动填充为 `npm run build`
   - **Output Directory**: 自动填充为 `dist`
   - **Environment Variables**: 留空（使用 vercel.json 的 rewrites）
5. 点击 **"Deploy"**

**方式二：使用 Vercel CLI**

```bash
# 安装 Vercel CLI
npm install -g vercel

# 登录
vercel login

# 进入前端目录
cd front

# 部署
vercel --prod
```

部署成功后，你将获得一个访问地址，例如：
```
https://your-project.vercel.app
```

---

## 第三步：配置 Django 用户服务（可选）

如果你需要使用用户系统（注册/登录功能），还需要部署 Django 服务。

### 3.1 在 Render 上创建第二个 Web Service

| 配置项 | 值 |
|--------|----|
| **Name** | `django-user-service` |
| **Region** | `Singapore` |
| **Branch** | `main` |
| **Root Directory** | `DjangoUserService` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn DjangoUserService.wsgi:application --bind 0.0.0.0:$PORT` |
| **Instance Type** | `Starter` |

### 3.2 配置环境变量

| 变量名 | 说明 |
|--------|------|
| `DJANGO_SECRET_KEY` | Django 密钥（随机字符串） |
| `DJANGO_DEBUG` | `False` |
| `DB_HOST` | MySQL 主机（与后端共用） |
| `DB_PORT` | MySQL 端口 |
| `DB_NAME` | MySQL 数据库名（可以共用一个数据库） |
| `DB_USER` | MySQL 用户名 |
| `DB_PASSWORD` | MySQL 密码 |

### 3.3 更新前端配置

将 [front/vercel.json](file:///e:/devsoftware/code/LangChain-RAG-FastAPI-Service/LangChain-RAG-FastAPI-Service/front/vercel.json) 中的 `/user/*` 和 `/file/*` 路由指向你的 Django 服务地址。

---

## 验证部署

### 验证后端

在浏览器访问：
```
https://your-render-app.onrender.com/health
```

应该返回：
```json
{
  "status": "healthy"
}
```

### 验证前端

访问你的 Vercel 地址：
```
https://your-project.vercel.app
```

应该能看到网站首页，可以尝试：
1. 测试 AI 对话功能
2. 上传知识库文档
3. 测试 RAG 查询

---

## 成本估算

| 服务 | 免费层 | 付费起步价 | 月费用估算 |
|------|--------|------------|------------|
| Vercel 前端 | 免费（100GB 带宽/月） | $20/月 Pro | $0 - $20 |
| Render 后端 | 750小时/月（需信用卡） | $7/月 Starter | $7 - $7 |
| Aiven Redis | 免费（1个月） | $0.038/hour | $0 - $10 |
| MySQL（阿里云） | 新用户有免费试用 | ~$10/月起 | $0 - $15 |
| DashScope API | 新用户免费额度 | 按量付费 | $5 - $20 |
| **合计** | **可用** | **基础版** | **$12 - $72/月** |

---

## 常见问题

### Q1: Render 部署失败，提示内存不足？

**原因**: Python 依赖包（尤其是 torch、transformers）体积较大，安装时需要足够内存。

**解决方案**:
1. 升级到更高配置的实例（Starter 以上）
2. 或使用 Docker 部署，在本地构建镜像后推送到 Render

### Q2: 首次请求响应很慢？

**原因**: Render 免费层会自动休眠，首次请求需要冷启动。

**解决方案**:
1. 升级到 Starter 层（$7/月，不自动休眠）
2. 或使用 uptime 监控服务（如 uptimerobot.com）每 5 分钟请求一次 /health 接口保持活跃

### Q3: 无法连接 Redis / MySQL？

**检查事项**:
1. 确认 Render 服务可以访问数据库的公网地址
2. 确认数据库防火墙已允许 Render 的出站 IP
3. 检查环境变量中的主机地址、端口、用户名、密码是否正确
4. 在 Render 的 Shell 中测试连接：
   ```bash
   python -c "import redis; r = redis.Redis(host='your-host', port=6379); r.ping()"
   ```

### Q4: 阿里云 DashScope API 调用失败？

**检查事项**:
1. 确认 API Key 正确，没有多余空格
2. 确认账号有足够额度（新用户有免费额度）
3. 确认已开通对应的模型服务（qwen-plus, text-embedding-v2 等）
4. 访问 https://dashscope.console.aliyun.com/top 查看调用统计

### Q5: 上传文件后找不到？

**原因**: Render 的文件系统是临时的，重启后数据会丢失。

**解决方案**:
1. 在 render.yaml 中配置持久化 Disk（已配置）
2. 或将文件上传到阿里云 OSS / 腾讯云 COS 等对象存储服务

---

## 下一步优化建议

1. **自定义域名**: 在 Vercel 和 Render 中配置你自己的域名
2. **CDN 加速**: 使用 Cloudflare 为前端加速
3. **监控告警**: 配置 UptimeRobot 监控服务状态
4. **日志收集**: 使用 Logtail 等工具收集日志
5. **安全加固**: 配置 WAF、限流、请求频率限制

---

## 项目配置文件

已为你创建以下配置文件：

- [front/vercel.json](file:///e:/devsoftware/code/LangChain-RAG-FastAPI-Service/LangChain-RAG-FastAPI-Service/front/vercel.json) — Vercel 前端配置
- [backend/render.yaml](file:///e:/devsoftware/code/LangChain-RAG-FastAPI-Service/LangChain-RAG-FastAPI-Service/backend/render.yaml) — Render 后端配置（可选，也可以在控制台手动配置）
- [backend/.env](file:///e:/devsoftware/code/LangChain-RAG-FastAPI-Service/LangChain-RAG-FastAPI-Service/backend/.env) — 本地开发环境变量（已存在）

---

祝你部署顺利！如有问题，请参考各平台官方文档或提交 Issue。
