把用户最新一轮消息归类到下面其中之一:
- inspiration: 发散思路、补设定、开放探索 (例如"还能再写些什么")
- research: 在已有项目里查询 / 总结 / 对比 (例如"我写过哪些角色"), 或者
            查询任何"外部事实 / 实时信息" (例如天气、新闻、历史事实、武器
            形制、外部模型规格), 这类问题 research agent 会调 web_search 工具回答
- structure: 批量新增节点和连线、建关系 (例如"帮我把 X 和 Y 建关系")
- simulation: 推演 "如果...会怎样" 类假设题
- small_talk: 寒暄 / 闲聊 / 简短确认 ("好的"、"谢谢"等), 以及"你是谁 / 你能做什么
            / 现在几点 / 今天几号"这类只需常识或运行时信息的自省问题

confidence: 0-1 之间的浮点, 表示判断把握; 不确定时给 0.5。
reasoning: 30 字以内的判断依据。

---

## 分类示例 (few-shot)

### 示例 1
**最新消息**: "帮我把艾琳和导师建一条师徒关系"
**输出**: `{"primary":"structure","confidence":0.95,"reasoning":"显式要求'建关系', 属于批量新增连线"}`

### 示例 2
**最新消息**: "我项目里都有哪些角色"
**输出**: `{"primary":"research","confidence":0.95,"reasoning":"枚举查询, 属于知识库考据"}`

### 示例 3
**最新消息**: "如果导师早些揭穿真相会怎样"
**输出**: `{"primary":"simulation","confidence":0.95,"reasoning":"含'如果...会怎样', 假设题"}`

### 示例 4
**最新消息**: "围绕艾琳还能补什么"
**输出**: `{"primary":"inspiration","confidence":0.9,"reasoning":"开放性发散, 寻求建议"}`

### 示例 5
**最新消息**: "好的, 谢谢"
**输出**: `{"primary":"small_talk","confidence":0.95,"reasoning":"简短确认 / 致谢"}`

### 示例 6
**最新消息**: "今天上海天气怎么样"
**输出**: `{"primary":"research","confidence":0.9,"reasoning":"外部实时事实, research agent 通过 web_search 回答"}`

### 示例 7
**最新消息**: "中世纪长剑形制有哪几种"
**输出**: `{"primary":"research","confidence":0.9,"reasoning":"现实考据, 需要 web_search 外部资料"}`

### 示例 8
**最新消息**: "你是什么模型 / 今天几号"
**输出**: `{"primary":"small_talk","confidence":0.85,"reasoning":"自省/运行时信息, 不需要任何工具调用"}`