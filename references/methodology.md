# 研究口径

## 模型与解耦

DataProvider → Account/Note/Product/Comment + Evidence → rank_notes → AI → AnalysisResult → 四种报告。
实现位于 scripts/xhs_analyzer；providers只负责映射，analysis不依赖TikHub路由。raw snapshot先写入，再映射与校验。

Account: account_id/url/nickname/bio/followers。
Note: note_id/account_id/title/body/published_at/likes/saves/comments/shares/url/cover_url/product_ids。
Product: product_id/name/price/currency/url。
Comment: comment_id/note_id/text/likes（不保留评论作者身份）。
Evidence: evidence_id/kind/entity_id/source_url/snapshot/excerpt/synthetic。
AnalysisResult: 数据、证据、baseline、top_notes、claims、ai、matrix、needs、hypotheses、warnings、metadata。

null代表未获取到公开数据，不是0。不认识的计数格式不强转0；数值如1.2万本身可能是平台约数，应按约数解释。来源字段缺失或schema不合格的行会跳过并记录警告。

## 相对互动指数（内部研究指标）

1. 同账号本次样本中，选择覆盖率至少80%的互动字段（点赞/收藏/评论/分享）。
2. 仅比较这些字段全部非空的笔记；其他笔记不排名，并报告排除数量。
3. 各可比字段等权求和得到互动总量 E。
4. 使用账号合格样本 E 的中位数 M：指数 = 100×(E+1)/(M+1)。+1用于零基准平滑。
5. 从高到低排列，默认TOP20；相同分数按note_id稳定排序。

不使用跨账号粉丝数、曝光或未知观看量作为分母。不称官方“爆款率”，不预测销量/利润。年龄、投流、删帖、置顶和接口排序会造成偏差。小样本/基准为零时指数敏感，必须结合原始计数查看。100表示样本中位数附近，不是成功率。

排行固定使用笔记列表快照的互动计数；详情仅补充正文等，避免不同采集时刻的互动数混用。

## 结论与证据

- FACT【事实】：直接字段或明确可重算统计。账号自述只能作为“账号自述”事实，不能验证宣称的性能。
- ANALYSIS【分析】：对可见内容的结构化解释和聚合，有对应原文证据。
- INFERENCE【推断】：潜在需求、语义商品关联、测试假设，不保证结果。
- confidence是分析者主观把握0..1，不是置信区间或统计概率。
- evidence_ids采用类型前缀（note:/product:/comment:/account:/image:），避免实体同ID碰撞；Evidence.entity_id保留原note_id/product_id。

自动校验可检查ID存在、逐笔记引用、视觉前置条件、数量、标签、常见夸大词，但不能证明自然语言结论逻辑正确。必须人工/Agent检查关键结论是否真的由引用支持，尤其不要把一句评论外推全体消费者。

## 内容×商品与需求地图

显式product_ids关联可记录FACT边；AI基于语义建立的关联只能为INFERENCE，必须引用笔记和真实商品实体。矩阵不计算销量。
需求地图引用公开评论；高频场景/痛点是深度样本中的分析标签频次，不代表总体市场。没有评论就不输出“消费者需求”结论。

## AI与封面

Agent路线使用当前智能体，无额外模型Key；CLI默认不会假装已自动完成Agent推理。
remote路线对已配置网关发送数据，校验失败降级。视觉只引用实际下载并解码验证的图片证据；限制5MiB/2000万像素，允许JPEG/PNG/WebP，禁止SVG/重定向/私有地址。
仅允许xhscdn.com/xhsimg.com公开CDN；其他域名降级，不随意放开白名单。封面结构的创意测试可以来自文本启发，但必须注明未观察竞品封面。

## 报告安全

HTML全部不可信正文转义；CSP禁止网络资源加载；只允许内联脚本/样式和data图片。CSV防止公式注入。原文链接只允许HTTPS；报告单文件内嵌证据摘录，不自动访问外部链接。
