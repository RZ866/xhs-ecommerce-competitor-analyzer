# 上游与匿名数据研究记录

研究日期：2026-10-02。

- 仓库：https://github.com/tamnd/xiaohongshu-cli
- 检查的 main：b60f9a384ed32d002aaacbbff95fedb2bdc96682。
- 当前检查到的发布版：v0.2.0，commit 96743ce。
- 检查 README、Release、LICENSE、cli/root.go/output.go/commands.go、xiaohongshu/user.go/ssr.go/note.go/types.go/config.go、pkg/xhshtml/state.go、pkg/xhsurl/url.go 及测试。
- 官方 Windows amd64 发布包 SHA256：4379a1554bc3583d5f13c678a9de7ed19ea288bb8e5d0955cff17be3781e0d57，与官方 checksums.txt 匹配。只在研究目录运行，不随 Skill 分发。
- 实际离线命令输出：`xhs version 0.2.0 (96743ce)`。
- 实际 id 命令 JSON 输出是数组，记录含 kind=user、user_id=5ff0e6500000000001008400、note_id为空、xsec_source为空、xsec_token为空。该命令不创建网络客户端。

## 实际访问与验证边界

匿名、无 Cookie、无代理的一次公开主页 GET 返回302，Location=https://www.xiaohongshu.com/login，正文164字节，没有 INITIAL_STATE。耗时约1.485秒，立即停止该数据源，未继续请求详情或短链。无403/429证据，属于登录墙而不是已证实的速率限制。

因此没有可供映射的真实成功账号/笔记响应。适配器是基于核查过的上游源码结构实现，使用合成结构样本测试；**不能宣称真实成功字段或真实完整链路已验证**。离线id命令输出验证也不能替代账号数据验证。

## 为什么不直接调用上游抓取命令

上游会读取 Cookie 环境配置，支持签名接口、匿名会话初始化及更激进重试；Go 整数模型会把缺失计数变成0。其 SSR 用户笔记路径通常只返回页面首屏，不提供稳定匿名全量分页。main 和发布版的状态退出码也有差异。

V2 采用独立标准库实现：只取公开 HTML，解析 window.__INITIAL_STATE__，不执行页面脚本；无 Cookie、无签名、无代理、无登录回退；缺失值为 null。不是上游完整功能移植。

## 已核查源码字段，待真实成功响应验证

| 统一字段 | 公开页面源码路径 |
|---|---|
| 账号名/简介/头像 | user.userPageData.basicInfo.nickname / desc / images |
| 粉丝/关注/获赞收藏 | user.userPageData.interactions，type为fans/follows/interaction，count |
| 卡片列表 | user.notes 的嵌套列表 |
| 卡片身份/标题/点赞 | id / noteCard.displayTitle / noteCard.interactInfo.likedCount |
| 详情 | note.noteDetailMap[note_id].note |
| 正文/发布时间 | desc / time（毫秒） |
| 互动 | interactInfo.likedCount / collectedCount / commentCount / shareCount |
| 图片 | cover.urlDefault / imageList[].urlDefault |

计数仅接受明确非负整数与整数字符串；“1.2万”“100+”等显示近似值不假装精确计数，保留原始快照。note_count没有可靠映射，保持null。暂无可验证公开评论正文/完整商品列表，不发起相应请求。

## 许可证

上游 Apache-2.0，Copyright 2026 Duc-Tam Nguyen。保留原样 [UPSTREAM-LICENSE](UPSTREAM-LICENSE) 与根目录 NOTICE。研究树未发现上游独立 NOTICE。未分发上游源码或 binary；V2 Python 实现为独立编写，借鉴公开页解析思路与字段布局。
