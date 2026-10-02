# xhs-ecommerce-competitor-analyzer

可运行的公开数据竞品研究 Skill + Python CLI。提供采集快照、统一 schema、账号内部相对互动排名、AI 分析交接/模型网关、离线 Dashboard、Markdown/JSON/CSV 输出。

**当前验收边界：mock 全链路可运行；没有真实 TikHub Key 和目标主页，因此没有完成当前真实返回字段验证，也未随包提供声称已验证的 TikHub 字段映射。正式账号分析需要先完成一次真实响应校准。** API 路由已依据官方 SDK 核查，路由存在不等于其返回内容已实测。

## 安装

Python 3.10 或以上。在本项目目录运行：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

核心 mock、数据与报告功能只需标准库；Pillow 用于 `--images` 验证图片。若不安装依赖，可以直接 `python scripts/analyze.py ...`。安装为 Codex Skill 时，将整个项目文件夹放到你的 Skill 目录中（本机现有目录是 `C:\Users\lenovo\.codex\skills`），保留 scripts/templates/references/tests；不要复制真实 data、reports 或 .env。重新开启任务后用 `$xhs-ecommerce-competitor-analyzer`。当前交付位于工作区，未修改用户全局 Skill 目录。

## 最简单的一条命令（离线，不收费）

```powershell
python scripts/analyze.py run "https://www.xiaohongshu.com/user/profile/000000000000000000000001" --provider mock --out reports/demo
```

双击 `reports/demo/report.html`。示例为我们构造的收纳类场景，105篇笔记的fixture分页读取前100篇、TOP20、TOP10各100条评论、3个合成商品。使用独立的 mock schema，不冒充 TikHub 实际返回。mock 的语义分析是预先编写的合成fixture，不会付费调用大模型。

## TikHub Key 配置

在 TikHub 用户后台自行获取 API Key。只在你自己的 PowerShell 输入（不会回显值）：

```powershell
$env:TIKHUB_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'TikHub API Key' -AsSecureString)).Password
```

变量只在当前终端及其子进程生效。若让 Codex 调用，启动 Codex 的进程必须能继承相同环境，或在已配置变量的终端直接运行CLI。不要把密钥发到对话里。`.env.example` 仅作变量清单；本程序不自动读取 `.env`，`.env` 已加入 .gitignore。

## 首次真实字段校准（调用可能收费）

```powershell
python scripts/analyze.py probe "真实主页URL" --kind account --out data
python scripts/analyze.py probe "真实主页URL" --kind notes --out data
```

先检查 `data/raw` 和 `data/inventory`，由 Agent/开发者根据实际字段创建 `data/contract.draft.json`；完整流程见 [字段契约说明](references/api-contract.md)。脚本不会从文档猜测返回字段。评论、商品和详情独立校准，不支持的端点不配置，报告降级显示缺失。

```powershell
python scripts/analyze.py validate-contract --draft data/contract.draft.json --snapshots data --out data/contract.validated.json
python scripts/analyze.py run "真实主页URL" --contract data/contract.validated.json --mode deep --images --out reports/account
```

默认 AI 路线：数据获取后输出 `analysis-request.md`、`analysis-input.json`，当前 Agent 读取材料、查看可访问图片、生成 `analysis.json`，最后：

```powershell
python scripts/analyze.py finalize --out reports/account
```

纯终端一条命令完成真实分析需要 `--ai remote`，另配置用户选择的模型网关：

```powershell
$env:AI_BASE_URL = 'https://你的可信模型网关/v1'
$env:AI_MODEL = '你的模型名称'
$env:AI_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host '模型API Key' -AsSecureString)).Password
python scripts/analyze.py run "真实主页URL" --contract data/contract.validated.json --ai remote --images --mode deep
```

网关需要支持 chat/completions JSON 输出；视觉分析需支持多模态 image_url/data URL。公开正文/评论和已获取图片会发送到该网关。不默认为用户挑选外部模型。大模型失败保留部分报告和 Agent 分析交接，不伪装成已完成。

## 参数

| 参数 | 默认 | 说明 |
|---|---:|---|
| --notes-limit | 100 | 1–100篇；采集数量上限，实际取决于公开可见性 |
| --deep-notes | 20 | 1–100篇相对高表现笔记 |
| --comment-notes | 10 | 0–100篇；独立于deep-notes取互动排名 |
| --comments-per-note | 100 | 1–1000条，按接口可获得的公开一级评论 |
| --mode | deep | boss仅核心判断/前5条TOP/3个商品方向；deep完整报告 |
| --timeout | 30 | TikHub 单请求秒数 |
| --retries | 2 | 429、5xx、网络错误有限重试；401/403不重试 |
| --interval | 1 | 请求最小间隔秒数，最低0.1 |
| --max-api-calls | 200 | 网络请求总上限，含重试；不是费用承诺 |
| --cache-ttl | 86400 | 缓存秒数，0表示不用缓存 |
| --cache-dir | data | 快照/缓存目录；mock使用独立namespace |
| --images | 关闭 | 只读取允许的公开XHS CDN，禁止重定向和Cookie |

boss改变呈现，不改变采集范围。内部 `dataset.json`/`analysis-result.json` 保留完整审计资料。对严格时间排序存在限制：只对已获取且带时间的笔记排序，不能证明获取了平台全历史中最新100篇；置顶/缺页/不可见数据会影响范围。

## 产物

- `report.html`：单文件离线 Dashboard，证据锚点、原文/字段展开、假设标签页，无外链字体或JS依赖。
- `report.md` / `report.json`：报告；boss为精简版。
- `claims.csv` / `top-notes.csv`；deep另有 notes/products/comments/matrix/needs CSV。
- `dataset.json`：标准化数据；`analysis-result.json`：完整分析审计数据。
- `analysis-input.json` / `analysis-request.md` / `analysis.json`：Agent/模型工作交接。
- `data/raw`：先于标准化保存的响应（凭证脱敏）；`data/cache`：24小时缓存索引。

HTML将必要证据摘录内嵌，因此单独复制HTML也能核对引用。完整原始JSON仍在data/raw；远程原文链接需要网络。公共页面不一定继续可访问。

## 已验证与未验证

参见 [验收记录](references/verification.md)。单元测试覆盖adapter、schema、缺失字段、内部指标、分页/缓存/限流/重试/降级、AI证据校验和HTML。mock模型网关测试不是实际模型质量评测。真实API当前字段、评论分页、多模态模型、实际封面可见性仍需带凭证验证。

## 扩展和边界

新增合法数据提供方实现 `DataProvider` 的 account/notes/products/comments/detail，返回统一模型并维护 Evidence，无需改写评分、AI分析、报告模块。不包含小红书登录、Cookie/验证码/签名工具。不采集非公开订单、利润或个人浏览器资料。

参考项目与许可证见 [references/research.md](references/research.md)。本实现为独立编写，未复制第三方代码、提示词或模板。
