# 先实际响应、后字段适配

研究日期：2026-10-02。当前没有真实凭证/目标账号；本项目**没有实际验证 TikHub 业务响应字段**。不提供猜测的默认映射，真实模式在校准前会明确停止。mock 使用作者构造的独立数据协议，不能用于真实模式。

## 已核查的官方接口路径（不代表实时可用性）

| kind | GET 路径 | 发送的参数 |
|---|---|---|
| account | /api/v1/xiaohongshu/app_v2/get_user_info | user_id |
| notes | /api/v1/xiaohongshu/app_v2/get_user_posted_notes | user_id、实测分页参数 |
| comments | /api/v1/xiaohongshu/app_v2/get_note_comments | note_id、实测cursor/index等 |
| products | /api/v1/xiaohongshu/web_v2/fetch_product_list | user_id、page |
| detail | /api/v1/xiaohongshu/app_v2/get_image_note_detail | note_id |

详情接口目前仅图文详情；视频笔记正文若不在列表响应中，本版可能无法补全，会保留缺失。未配置已验证detail映射时不调用。官方SDK另有视频/混合详情接口，扩展前须实际验证，不自动试探其他接口增加账单。

## 现场校准步骤

1. 先运行 unittest 和 mock。
2. 在用户授权的采集范围内配置环境变量。`probe URL --kind account` 和 `--kind notes` 各最多1个网络请求（缓存命中不调用）；请求失败也可能收费。
3. 查看原始快照的 HTTP 状态、上游业务成功标志、目标用户ID是否一致。HTTP 200 不能单独证明成功。inventory只列字段路径/类型，不自动认定字段语义。
4. 记录账号对象路径；笔记数组路径；ID、正文、互动计数、时间单位、封面URL路径；商品与笔记是否真的显式关联。字段不存在就不映射。尤其不要把收藏数映射成销量，或把SKU出现频率映射成利润。
5. 用实际笔记ID分别probe comments/detail；产品以user_id probe。遇到401/403、验证码或访问限制就降级，不进行规避。
6. 创建 draft 并验证。以下仅说明**契约配置格式**，所有大写说明均需要换成实际观察结果，不是TikHub字段示例：

```json
{
  "provenance": "observed-live-response",
  "endpoints": {
    "account": {
      "sample": "raw/实际账号响应文件.json",
      "success_path": "实际业务成功标志路径",
      "success_value": true,
      "items_path": "实际账号对象路径",
      "fields": {
        "account_id": "对象内部实际ID路径",
        "nickname": "对象内部实际昵称路径"
      }
    },
    "notes": {
      "sample": "raw/实际笔记响应文件.json",
      "success_path": "实际业务成功标志路径",
      "success_value": true,
      "items_path": "实际笔记数组路径",
      "fields": {
        "note_id": "单条笔记实际ID路径",
        "title": "单条笔记实际标题路径"
      }
    }
  }
}
```

路径以 `.` 分隔；数组下标用 `.0`；空路径表示当前对象。field值可以是路径字符串或 `{ "path": "实测路径", "scale": 0.001 }`（例如已验证毫秒时间→秒）。时间也支持 `format: "iso8601"`，必须有时区。价格单位必须核实后再设scale；不自动猜币种。对象数组投影用 `item_path`，如 product_ids 来源为对象数组，需要实际验证商品ID的子路径。

分页格式：

```json
{
  "pagination": {
    "has_more_path": "实际是否有下一页字段",
    "next_params": {
      "cursor": "实际下一页游标字段",
      "index": "实际下一页index字段"
    }
  }
}
```

仅保留接口真正需要且响应已观察到的参数。page式使用 `page_parameter: "page"`，不设置next_params。has_more只接受布尔/0/1；异常或重复游标停止。缺少分页映射则仅读取当前页并警告，不猜测cursor。

```powershell
python scripts/analyze.py validate-contract --draft data/contract.draft.json --snapshots data --out data/contract.validated.json
```

验证器检查样本来源、接口路径、状态、字段实际存在，并保存样本hash/契约hash。它验证结构，不认证提供方合法性，也不能自动验证人填写的字段语义。映射修改后必须重新校验。线上字段漂移时会丢弃不合格记录并记录警告；回到probe重新校准。

## 下次真实验收清单

- 记录真实账号、笔记、评论、商品/详情可用端点、响应日期与快照hash。
- 至少验证两页笔记、两页评论：ID去重、游标是否推进、是否提前结束。
- 核对时间单位、置顶笔记、上限与实际获取数、空账号/私密/删除/403情况。
- 商品缺失时报告降级；明确确认笔记中的SKU关联字段再生成FACT边。
- 图片可见性与实际视觉模型输出；断网或403时不推测封面。
- 校验费用上限与实际调用数（默认200次包含重试，具体金额取决于提供方）。
