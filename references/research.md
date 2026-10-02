# 参考研究与许可记录

核查日期：2026-10-02。以下均为公开原作者/官方来源。

1. [TikHub官方Python SDK接口参考](https://github.com/TikHub/TikHub-API-Python-SDK/blob/main/docs/reference.md)：核查Xiaohongshu App-V2账号/笔记/评论/详情，以及Web-V2商品列表的路由与参数名称。SDK主仓库标注Apache-2.0，已读取其LICENSE；本项目未复制或捆绑SDK代码，使用自写标准库HTTP传输。
2. [TikHub用户笔记接口文档](https://docs.tikhub.io/420136396e0)：核查user_id、cursor与计费提示。文档和SDK接口清单不作为实时返回字段的验证依据。
3. [Beef XHS Library](https://github.com/glanderness/xhs-library) / [SKILL.md](https://github.com/glanderness/xhs-library/blob/main/SKILL.md) / [MIT许可](https://github.com/glanderness/xhs-library/blob/main/LICENSE)：借鉴本地原始响应留存、稳定ID去重、作者与内容实体分离、CLI与Skill共享流程的思路。本版不包含飞书同步，也不复制实现或模板。
4. [xhs-business-validator-skill](https://github.com/liangdabiao/xhs-business-validator-skill)：参考公开内容→评论信号→AI判断→HTML的工作流。核查页面的文件列表未发现明确LICENSE；因此不复制其代码、提示词或HTML。没有采用其凭证索取方式、固定商业成功评分、规避403的处理方式。

本项目根据本次需求独立编写，不复制第三方代码。依赖Pillow按其发行许可证使用，由pip安装；不把第三方依赖源码放入项目。后续若引入第三方代码必须重新核对对应版本许可证并保留必要声明。

## 尚未成立的验证结论

本次未调用任何付费TikHub接口，未使用真实小红书账号URL，也没有使用真实模型Key。不得将mock测试通过写成“TikHub当前字段真实可用”或“实际视觉/商业判断准确”。
