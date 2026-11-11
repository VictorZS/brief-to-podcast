# episode.json 输入契约

完整且可运行的例子见 [examples/episode.json](../examples/episode.json)。`schema_version` 是数据结构版本，`editorial.version` 是编辑约束版本，两者不同。首版默认配置要求 `schema_version: 1`、`editorial.version: 3`；底层检查器兼容编辑版本 2，但新输入应使用版本 3。

首次准备中文输入可从[逐步指南](getting-started.zh.md)与[单一事实的中文样例](../examples/episode.zh.json)开始；对应的[初稿](../examples/draft.zh.txt)可用于复算字符数。小样例保留相同校验要求，不包含展开的洞察。

所有计数、时间、事实、检查状态和自检结论均由上游提供。引擎检查它们的结构和关系，不查询邮箱、不读取来源网页，也不独立证实这些声明。

## 顶层字段

| 字段 | 内容 |
|---|---|
| `schema_version` | 整数 `1` |
| `title`, `overview` | 非空标题和整体说明 |
| `window` | `start`、`end` 为带时区偏移的 ISO 8601 时间，开始早于结束；可附 `timezone` 说明 |
| `coverage` | `complete` 布尔值；`accounts` 数组；可选 `notes` 字符串数组 |
| `sources` | 来源数组，ID 不重复 |
| `sections` | 书面段落数组；编辑版本 3 必须有三个有序部分 |
| `segments` | 非空口播数组；编辑版本 3 必须有三个有序部分 |
| `signals` | 洞察信号数组；可以是 `[]` |
| `actions` | 通知或行动数组；可以是 `[]` |
| `briefing` | 消息总数、通知复核状态与后续问题 |
| `editorial` | 事实表、选题、压缩记录与自检信息 |

`coverage.accounts` 每项包含 `email`（展示标签，可用虚构地址）、非负整数 `count` 和 `categories` 对象。类别名称可自定，每个值是非负整数，各类别之和必须等于 `count`。这里的邮箱标签不会用于登录或发送邮件。

`coverage.complete: true` 表示上游声称已完整检查本次范围；请只在你实际确认完整覆盖时使用。样例使用 `false`。

## 来源、段落和口播

每个 `sources` 项含 `id`、`title`、`url`、`origin`、`published_at`、`access`。`url` 必须为普通 HTTPS URL，不包含用户认证信息。`access` 描述实际上读到的材料，例如 `full_text`、`email_body` 或 `abstract`；不要将仅有摘要的材料写成全文已读。

`sections` 与 `segments` 每项含：

| 字段 | 内容 |
|---|---|
| `part` | `inbox`、`insights`、`notifications` 三选一 |
| `title`, `text` | 标题与正文；口播文字必须非空 |
| `source_ids` | 引用的来源 ID 数组，可为空 |
| `fact_ids` | 引用的事实 ID 数组，可为空 |
| `research_question_ids` | 可选；口播中实际提出的后续问题 ID，仅可放在 `insights` |

三部分按 `inbox → insights → notifications` 排列；同一部分可以有连续多段，不能跳过或来回穿插。每个引用事实的段落还必须列出该事实对应的全部 `source_ids`。口播不能包含 URL 或 `[[…]]` 语音控制序列。

`signals` 的每项含 `id`、`title`、`fact`、`inference`、`counterevidence`、`confidence`、`change`、`next_check` 和非空 `source_ids`。这些字段帮助区分观察与推断，检查器不会替你评判信心等级是否恰当。

`actions` 的每项含 `title`、`priority`、`detail`、`deadline`、非空 `source_ids`，以及：

- `category`：`renewal` / `travel` / `billing` / `delivery` / `account` / `work` / `optional` / `other`。
- `status`：`needs_action` / `upcoming` / `updated` / `resolved` / `information` / `unverified`。
- `change`、`next_step`：非空文字，解释发生什么变化及下一步动作。

没有待办时使用空数组。未确认的通知用 `unverified`，不要补造截止日期或宣称没有风险。

## briefing：范围与后续问题

`total_count` 必须等于 `coverage.accounts` 中所有 `count` 的和。

`notification_review` 包含：

- `status`：`complete` 或 `partial`。
- `reviewed_current_count`：已复核的本次消息数，介于 `0` 和 `total_count` 之间。
- `history_status`：`complete` / `partial` / `not_run`。
- `scope_note`：实际检查范围与缺口的非空说明。

只有 `coverage.complete` 为真、已复核全部本次消息、历史提醒也复核完整时，通知 `status` 才能为 `complete`。

`research_questions` 是最多两项的数组。有展开的洞察时至少需要一个问题。每项含唯一 `id`、对应的 `story_id`、`question`、`why_it_matters`、`starting_point`、非空 `source_ids`；三个文字字段至少 8 个字符。问题 ID 必须出现在洞察口播的 `research_question_ids` 中。ID 检查不能证明句子真的提出了该问题，请阅读或试听确认。

## editorial：事实与编辑约束

`version: 3`；`thesis` 是至少 12 个字符的具体编辑主张。

`facts` 是事实记录数组，每项包含：

| 字段 | 内容 |
|---|---|
| `id` | 非空且唯一的事实 ID |
| `text` | 事实表述 |
| `kind` | `observation` / `survey` / `forecast` / `context` / `deadline` |
| `source_ids` | 非空来源 ID 数组 |
| `source_family` | 来源家族标签，用于标识可能同源的信息 |
| `evidence_level` | `full_text` / `email_body` / `abstract` / `snippet` |
| `scope`, `caveat` | 适用范围与限制，均非空 |
| `must_preserve` | 被保护事实需提供的非空字面锚点数组，例如数值、年份、样本量和“不代表因果” |

`stories` 最多一个展开的选题，每项包含唯一 `id`，至少 8 字符的 `question`、`judgment`、`mechanism`、`implication`、`counterargument`、`would_change_mind`，以及：

- `fact_ids`：非空事实引用；不能以 `snippet` 等级材料支撑展开的选题。
- `priority`：`knowledge_value` 与 `urgency` 各为 `0–3` 的整数，附 `reason`。
- `novelty`：`status` 为 `baseline` / `continued` / `changed`，附 `reason`；与已有判断比较，避免重复包装旧结论。

`judgment` 不能与 `mechanism` 完全相同。选题所用事实必须在交付段落或口播中出现。没有足够证据时允许 `stories: []`，但需提供至少 12 字符的 `no_story_reason`，并仍保留三个简报部分；`research_questions` 可以为空。

`compression` 记录：

- `before_chars`：初稿口播的实际字符数，正整数。
- `after_chars`：精确等于 Python 表达式 `len("\n\n".join(s["text"] for s in episode["segments"]))`。
- `protected_fact_ids`：有事实时不能为空，所有 ID 必须有效；每条被保护事实的所有 `must_preserve` 锚点必须在**引用该事实的书面段落**中出现，大小写不敏感。
- `removed`、`restored`：文字数组，记录删掉及恢复的内容。

样例的 [draft.txt](../examples/draft.txt) 保存虚构初稿，因此 `before_chars` 可以复算。口播数字可以换成自然读法；字面锚点的强制保留检查针对书面段落。重复检测只是启发式检查，无法捕获所有近义复述。

`review` 包含 `status: "pass"`、`reviewer`、`corrections` 数组、`remaining_limits` 数组。这是上游自检的声明，不能替代独立审稿或事实核查。

## 配置与退出状态

文本模式需要 Python 3.10+；macOS 音频路径请使用 Python 3.12+，以支持系统语音可能输出的扩展 PCM WAV。遇到 `unknown format: 65534` 时，按[入门指南](getting-started.zh.md#4-在-mac-上生成中文声音)检查实际使用的 Python 版本。

`config.example.json` 包含 `speech_engine: "macos"`、`voice`（已安装的系统语音名称）、`speaking_rate`（80–300 的整数）、`editorial.required: true`、`editorial.pipeline_version: 3`。默认配置作为校验基线；不要通过关闭编辑检查掩盖不完整输入。

渲染器返回 `0` 表示成功生成文本或检查通过的音频，`1` 表示音频生成失败但保存了可读结果，`2` 表示输入、配置或执行前置条件错误。先查看退出码，再查看输出目录里的 manifest；未验证通过的音频不应作为本期成品发布。中断可能留下 `processing` 状态，需重新运行。manifest 里的文件哈希是成品核验依据。MP3 另有 `mobile_audio.json`；只有 `status: ready` 且 `render_fingerprint` 等于当前 manifest 的 `fingerprint`，并且 MP3 文件哈希匹配时，才对应当前成品。目录复用时旧 MP3 回执会被标成 `stale`。
