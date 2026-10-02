# 小红书电商对标账号自动拆解 Skill

粘贴一个账号主页链接，自动整理公开内容、账号内高表现笔记、商品提及与可测试选题，生成带证据的电商研究 Dashboard。

- 免费匿名获取公开数据，0 数据 API 调用费用。
- 无需 TikHub、无需小红书登录、无需 Cookie。
- 一条主页链接直接分析，支持分享短链。
- 互动与成交严格区分；缺失数据不编造。

**匿名访问可能被平台限制。** 本次真实测试遇到登录墙，取得0篇笔记；不能保证每个账号都能分析。目标50/100篇是上限，通常仅能取得公开主页首屏。Skill 免费，Codex / WorkBuddy 等宿主自身费用按其规则执行。

## 安装或更新

在支持安装 GitHub Agent Skill 的工具里发送：

> 帮我安装（已安装则更新）这个 Skill：https://github.com/RZ866/xhs-ecommerce-competitor-analyzer 。请安装整个仓库中的 Skill 及配套文件，并检查运行条件。

能否自动安装取决于宿主提供的安装与执行权限。仓库根目录含 SKILL.md；不是只复制这个文件。由宿主内部完成运行检测，用户无需配置数据账户。若更新后仍显示旧版要求密钥的说明，说明宿主尚未重新载入V2，要求它重新加载已更新的 Skill。

## 使用

> 拆解这个账号：小红书主页链接

> 深度拆解这个账号：小红书主页链接

也可以只粘贴完整主页或分享短链。结果包括老板摘要、覆盖范围、相对高表现TOP、商品与内容关系、带证据的研究结论及测试假设。单篇笔记拆解尚未支持。

有数据时生成 report.html、report.md、analysis.json、notes.csv；有明确产品提及时增加 products.csv。HTML 无需联网加载图表或样式，外部证据原文需要网络。遇到访问限制停止请求并保留已有数据，零样本时明确无法可靠拆解。

## 已验证与限制

详见 [验收记录](references/acceptance.md)。自动测试不等于 WorkBuddy 实机验收，也不等于真实匿名完整链路成功。评论正文、完整商品目录、销量、利润、GMV、转化率不在当前可验证数据范围内。封面只在公开图片成功读取且宿主实际看图时分析。

## Third-party dependencies

数据层研究参考 [tamnd/xiaohongshu-cli](https://github.com/tamnd/xiaohongshu-cli)，上游 Apache-2.0，Copyright 2026 Duc-Tam Nguyen。当前版本不分发、不调用其二进制，也不采用其 Cookie/签名/重试链路；独立封装公开页面解析，保留缺失字段。研究版本、字段与许可证记录见 [来源说明](references/upstream-research.md) 与 NOTICE。

## Developer Documentation

运行机制、缓存、测试和发布信息见 [开发文档](references/development.md)。普通用户无需阅读。
