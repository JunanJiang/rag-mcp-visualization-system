# SimuReport Integration Demo

这是一个独立的第三方软件接入示例，用于展示外部应用如何复用 SimuReport 的认证、数据接入、AI 工作流和报告回传能力。

## 演示能力

- 使用 SimuReport 账号完成统一登录
- 从外部应用上传数据包
- 通过 AI 控制台生成可视化报告
- 通过登录桥接链接打开 SimuReport Web 端
- 在两个应用之间恢复数据包与报告工作流上下文

## 目录结构

```text
integration_demo/
├─ backend/   # Flask 接入适配层，默认端口 5100
└─ frontend/  # Vue 3 演示界面，默认端口 3002
```

## 接入架构

### Backend Adapter

`integration_demo/backend/app.py` 负责：

- 代理认证、数据上传、报告工作流和 MCP 对话请求
- 在服务端会话中维护登录令牌和数据包上下文
- 生成 Web 端登录桥接链接
- 将生成的报告回传给外部应用

### Demo Frontend

`integration_demo/frontend` 模拟第三方工程软件中的报告功能页，提供登录、数据包选择、AI 控制台和报告下载界面。

### Web Bridge

主应用通过 `/integration-entry` 接收桥接参数，将认证与任务上下文恢复到报告工作区，用户无需重复登录或上传数据。

## 启动方式

先启动主系统：

```bash
python server/app_v2.py

cd frontend
npm install
npm run dev
```

再启动接入适配层：

```bash
pip install -r integration_demo/backend/requirements.txt
python integration_demo/backend/app.py
```

最后启动演示前端：

```bash
cd integration_demo/frontend
npm install
npm run dev
```

访问 `http://localhost:3002`，配置主系统前后端地址后即可运行完整接入流程。
