# Developer Documentation

本页仅供开发者，不应作为账号分析最终交付。

## 架构

`scripts/analyze.py → DataProvider / AnonymousPublicProvider → 原始快照 → 统一模型 → AccountAnalyzer → evidence validation → render`。

宿主模型在两阶段内部协议中补充语义结论，不调用额外模型 API。脚本独立执行可完成可核验规则与统计，但不会冒充AI深度分析。NoteAnalyzer保留单篇路由。模型包括Account/Note/Product/Comment/Evidence/AnalysisResult；JSON输出与dataclass对应，缺失数值null。

HTML仅含内联CSS和原生details，无外部脚本字体样式。外部原文链接仍需网络；不自动加载远程追踪图片。图片下载仅限页面真实提供的允许CDN主机、HTTPS、最多5MiB、无重定向，最多5张，计入同一请求预算。宿主必须实际查看后才可写视觉结论。

## 获取策略

- 串行；页面/图片请求共用至少3秒间隔（保守配置，未宣称已验证可避免封禁），持久化最近请求时间。
- 普通/深度请求总预算26/46，包括短链跳转；详情最多20/40篇，优先按首屏可见互动排序，其余保留卡片字段。
- 每个页面请求超时25秒，图片20秒；不重试403/429/登录墙/验证码。普通网络或解析失败仅降级，默认不重试单篇。
- 首屏样本目标50/100；不调用签名分页，不宣称时间排序完整。
- 72小时缓存；页面更新后仅补需要且未缓存的详情，旧样本可在受限时使用。源受限写24小时共享冷却，同一状态目录后续任务不联网。
- 本地独占运行锁防止多个任务同时抓取。异常进程退出遗留锁时由宿主核实进程已结束后内部清理，不交给普通用户。
- raw先保存后解析；只保存必要响应和时间，不保存请求/响应认证头。临时链接参数仅在私有原始材料中，报告来源链接去参数。
- 数字近似显示不转为精确事实。混合指标可用性会影响排名可比性，报告明确提示。

## 内部开发命令

```sh
python -m unittest discover -s tests -v
python scripts/acceptance.py
python scripts/demo.py --dev --output reports/demo
python scripts/analyze.py '拆解这个账号：https://www.xiaohongshu.com/user/profile/实际ID' --output reports/account
```

不要用真实请求反复跑测试。测试fixture是合成数据，不能作为实际抓取证据。真实冒烟已触发登录墙，当前研究阶段禁止继续该受限源。后续在平台允许匿名访问、冷却期结束的环境才可单独验证，不切换网络规避限制。

`scripts/acceptance.py` 验证正式输出术语、证据、输出文件和离线HTML依赖。这是自动用户契约验收，不是WorkBuddy实机验收。

## 安全与发布

`scripts/secret_scan.py` 扫描工作树文本及Git可达历史对象，输出位置/种类，不输出匹配密钥。模式扫描不是绝对安全证明。原始快照和报告默认不提交。GitHub发布仅应包含源代码、文档、合成fixture与许可文件；测试报告另存忽略目录。
