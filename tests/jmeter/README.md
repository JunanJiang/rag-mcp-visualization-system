# JMeter 性能测试说明

## 测试概览

本测试计划针对 SimuReport 后端 API 进行性能与功能测试。

### 测试分组

| 线程组 | 并发数 | 循环次数 | 测试内容 |
|--------|--------|----------|----------|
| 1. 基础接口功能测试 | 10 | 5 | 健康检查、Schema查询、数据包规范、模板列表 |
| 2. 用户认证与授权测试 | 20 | 10 | 注册、登录、Token认证、未授权访问、错误密码 |
| 3. 知识库与数据接口测试 | 15 | 5 | 知识库卡片、搜索、Schema验证、组织、MCP工具、会话上下文 |
| 4. 管理员接口测试 | 10 | 5 | 用户管理、审计日志、API密钥管理 |
| 5. 高并发压力测试 | 50 | 20 | 混合接口高并发压测 |

### 覆盖的 API 接口

- `GET /api/health` — 健康检查
- `GET /api/schema` — 标准数据Schema
- `GET /api/data-package/spec` — 数据包规范
- `GET /api/templates` — 报告模板列表
- `POST /api/auth/register` — 用户注册
- `POST /api/auth/login` — 用户登录
- `GET /api/auth/profile` — 获取用户信息（需认证）
- `GET /api/auth/reports` — 报告历史（需认证）
- `POST /api/schema/validate` — Schema验证
- `GET /api/kb/cards` — 知识库卡片列表
- `GET /api/kb/cards?q=xxx` — 知识库搜索
- `GET /api/orgs` — 组织列表（需认证）
- `GET /mcp/tools/list` — MCP工具列表（需认证）
- `GET /api/session/context` — 会话上下文（需认证）
- `GET /api/tasks` — 异步任务列表（需认证）
- `GET /api/admin/users` — 用户管理（管理员）
- `GET /api/admin/audit-logs` — 审计日志（管理员）
- `GET /api/admin/api-keys` — API密钥管理（管理员）

---

## 环境准备

### 1. 安装 JMeter

1. 下载 Apache JMeter: https://jmeter.apache.org/download_jmeter.cgi
2. 解压到任意目录，如 `C:\apache-jmeter-5.6.3`
3. 将 `bin` 目录添加到系统 PATH:
   ```
   set PATH=%PATH%;C:\apache-jmeter-5.6.3\bin
   ```

### 2. 启动后端服务

```bash
cd server
python app_v2.py
```

确保服务运行在 `http://localhost:5000`。

---

## 运行测试

### 方式一：一键运行（推荐）

双击 `run_jmeter_test.bat`，脚本会自动：
1. 检查 JMeter 是否安装
2. 以非GUI模式执行测试
3. 生成 HTML 报告并自动打开

### 方式二：命令行运行

```bash
# 非GUI模式运行，生成CSV结果和HTML报告
jmeter -n -t SimuReport_TestPlan.jmx -l results/result.csv -e -o results/html_report
```

### 方式三：GUI模式（可视化观察）

```bash
jmeter -t SimuReport_TestPlan.jmx
```

在 GUI 中点击绿色「开始」按钮运行，可实时查看：
- **查看结果树** — 每个请求的详细结果
- **聚合报告** — 汇总统计数据
- **汇总报告** — 概要统计
- **响应时间图** — 响应时间趋势

---

## 测试报告截图指南

### 推荐截取的截图

1. **聚合报告截图** — 展示每个接口的平均响应时间、吞吐量、错误率
   - GUI模式 → 点击「聚合报告」标签页 → 截图

2. **HTML报告截图** — 运行完成后自动生成的报告
   - `results/html_report/index.html` 打开后截图以下页面：
     - **Dashboard** — 总览页（包含统计摘要、错误百分比、吞吐量）
     - **Response Times Over Time** — 响应时间趋势图
     - **Transactions Per Second** — 每秒事务数图
     - **Response Time Percentiles** — 响应时间百分位图

3. **查看结果树截图** — 展示单个请求的请求/响应详情
   - GUI模式 → 点击「查看结果树」→ 选一个成功请求和一个断言失败请求

4. **测试计划结构截图** — 展示测试计划的组织结构
   - GUI模式 → 展开左侧树形结构 → 截图

### 截图命名建议

```
figure_jmeter_dashboard.png      — HTML报告总览
figure_jmeter_response_time.png  — 响应时间趋势
figure_jmeter_tps.png            — 每秒事务数
figure_jmeter_aggregate.png      — 聚合报告表格
figure_jmeter_result_tree.png    — 请求详情
figure_jmeter_test_plan.png      — 测试计划结构
```

---

## 测试指标说明

| 指标 | 含义 |
|------|------|
| Samples | 总请求数 |
| Average | 平均响应时间(ms) |
| Median | 中位数响应时间(ms) |
| 90% Line | 90%请求的响应时间(ms) |
| 95% Line | 95%请求的响应时间(ms) |
| 99% Line | 99%请求的响应时间(ms) |
| Min | 最小响应时间(ms) |
| Max | 最大响应时间(ms) |
| Error % | 错误率 |
| Throughput | 吞吐量(请求/秒) |
| KB/sec | 数据传输速率 |
