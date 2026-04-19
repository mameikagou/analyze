# 设计考古作业 — claude.ai/new

> 目标：用浏览器 DevTools 把 claude.ai/new 当成一个标本来解剖，产出一份设计审计文档。
> 这份文档是后续所有 Token、组件、Skill 的**唯一事实来源**。
>
> 完成时间：自行安排，不急。做完发给我，我据此开工 Token 体系。

---

## 打开方式

1. 浏览器打开 `https://claude.ai/new`（确保已登录，看到的是 New Chat 空态页）
2. F12 打开 DevTools → 切换到 **Elements** 面板 → 右侧找 **Computed** 标签
3. 用元素选择器（左上角箭头图标）点选你想看的目标

---

## 三个必须捕获的状态

### 状态一：空态首页（claude.ai/new）

直接打开即可。重点：整体背景、居中大输入框、底部快捷功能按钮。

### 状态二：对话中

在输入框发一条消息（比如 "hi"），等 Claude 回复。重点：消息气泡样式、用户/AI 区分、流式文字、代码块。

### 状态三：Artifact 打开

让 Claude 生成一段代码（比如 "写个 Python 快速排序"），回复中会出现 Artifact 预览，点击打开。重点：右侧面板、代码高亮、阴影层级。

---

## 每类要抓的样式（在 Computed 面板里找）

### A. 背景色梯度

| 目标 | DevTools 怎么找 |
|------|----------------|
| 页面整体背景 | 选 `<body>` 或最外层容器，看 `background` / `background-color` |
| 输入框背景 | 点选居中大输入框，看 `background` |
| 消息气泡背景（用户） | 点选自己发的消息，看 `background` |
| 消息气泡背景（AI） | 点选 Claude 回复，看 `background` |
| 右侧面板背景 | 点选 Artifact 面板，看 `background` |
| hover 状态背景 | hover 后立刻用元素选择器点选，看 `background` |

### B. 文字色梯度

| 目标 | DevTools 怎么找 |
|------|----------------|
| 页面大标题（"What can I help you with?" 类） | 点选标题文字，看 `color` |
| 正文 | 点选正文段落，看 `color` |
| 次要/辅助文字 | 点选小字说明，看 `color` |
| placeholder | 点选输入框内的占位文字，看 `color` |
| disabled 状态 | 点选不可点击的元素，看 `color` |

### C. 边框

| 目标 | DevTools 怎么找 |
|------|----------------|
| 输入框边框 | 点选输入框，看 `border-color` / `border-bottom-color` |
| 卡片/面板边框 | 点选卡片，看 `border` 相关属性 |
| 分割线 | 点选分隔线，看 `background`（很多分割线是用 1px div 模拟的） |

### D. 圆角

| 目标 | DevTools 怎么找 |
|------|----------------|
| 输入框 | 点选输入框，看 `border-radius` |
| 按钮 | 点选按钮，看 `border-radius` |
| 卡片/面板 | 点选卡片，看 `border-radius` |
| 消息气泡 | 点选消息气泡，看 `border-radius` |

### E. 阴影

| 目标 | DevTools 怎么找 |
|------|----------------|
| 输入框 focus ring | 点击输入框，看 `box-shadow` |
| 右侧面板 | 点选 Artifact 面板，看 `box-shadow` |
| 弹层/下拉菜单 | 触发下拉，点选弹层，看 `box-shadow` |

### F. 字号 / 行高 / 字重

| 目标 | DevTools 怎么找 |
|------|----------------|
| 页面大标题 | 点选标题，看 `font-size`, `line-height`, `font-weight` |
| 正文 | 点选正文，看 `font-size`, `line-height` |
| 按钮文字 | 点选按钮，看 `font-size`, `font-weight` |
| 代码块 | 点选代码，看 `font-size`, `font-family` |

### G. 间距

| 目标 | DevTools 怎么找 |
|------|----------------|
| 输入框内边距 | 点选输入框，看 `padding` |
| 按钮内边距 | 点选按钮，看 `padding` |
| 卡片间距 | 看父容器的 `gap` 或子元素的 `margin` |

### H. 动画

| 目标 | DevTools 怎么找 |
|------|----------------|
| hover 背景变化 | 点选按钮，看 `transition` |
| focus ring 出现 | 点选输入框，看 `transition` |
| 输入框高度变化 | 多行输入时，看 `transition` |

---

## 输出模板

把下面模板复制到新文件（比如 `docs/design-audit-result.md`），逐项填值。颜色值请用**原始 HEX 或 rgb**，不要用 "white" / "gray" 这种描述词。

```markdown
# design-audit-result.md

## 空态首页

| 元素 | background | color | border-color | border-radius | box-shadow | font-size / line-height | padding |
|------|-----------|-------|--------------|---------------|------------|------------------------|---------|
| 页面整体 | | | | | | | |
| 居中大输入框 | | | | | | | |
| 输入框 placeholder | | | | | | | |
| 输入框 focus 状态 | | | | | | | |
| 底部快捷按钮（默认） | | | | | | | |
| 底部快捷按钮（hover） | | | | | | | |
| 页面大标题 | | | | | | | |
| 底部小字/链接 | | | | | | | |

## 对话中

| 元素 | background | color | border-color | border-radius | box-shadow | font-size / line-height | padding |
|------|-----------|-------|--------------|---------------|------------|------------------------|---------|
| 用户消息气泡 | | | | | | | |
| AI 消息区域（无气泡） | | | | | | | |
| AI 消息中的代码块 | | | | | | | |
| 流式光标（那个闪烁竖线） | | | | | | | |
| 输入框（底部 docked 状态） | | | | | | | |
| 发送按钮 | | | | | | | |

## Artifact 打开

| 元素 | background | color | border-color | border-radius | box-shadow | font-size / line-height | padding |
|------|-----------|-------|--------------|---------------|------------|------------------------|---------|
| 右侧面板整体 | | | | | | | |
| 面板头部 | | | | | | | |
| 面板中的代码背景 | | | | | | | |
| 面板关闭按钮 | | | | | | | |

## 动画参数

| 动画类型 | transition-duration | transition-timing-function | 备注 |
|---------|--------------------|---------------------------|------|
| hover 背景变化 | | | |
| focus ring 出现 | | | |
| 输入框高度变化 | | | |
| 消息气泡出现 | | | |

## 字体

| 用途 | font-family（从 Computed 面板复制完整值） |
|------|------------------------------------------|
| 页面标题 | |
| 正文 | |
| 代码 | |
| 按钮 | |

## 截图（可选但强烈建议）

每个状态截一张全屏图，保存在 `docs/design-audit-screenshots/` 目录下：
- `01-empty-state.png` — 空态首页
- `02-chatting.png` — 对话中
- `03-artifact-open.png` — Artifact 打开

## 额外发现

（任何你觉得重要但上面没覆盖到的，比如：
- 特殊的 gradient / 渐变色
- Icon 颜色（发送按钮、附件按钮等）
- Scrollbar 样式
- 输入框内的小图标（附件、麦克风等）
- 暗色模式下的变化
- 任何 "这挺特别的" 的视觉细节
）
```

---

## 常见问题

**Q: 我看到的颜色和别人不一样？**
A: 可能是暗色模式。claude.ai 会跟随系统主题。建议你同时记录 light mode 和 dark mode 的值，或者至少注明你当前是什么模式。

**Q: 某些值在 Computed 面板里看不到？**
A: 试试在 Styles 面板里搜索相关属性名（如搜索 "background"），看哪个 CSS 规则在生效。有些样式可能来自 CSS 变量（`var(--xxx)`），请把变量名和最终计算值都记下来。

**Q: hover 状态来不及点？**
A: 在 DevTools 的 Elements 面板，右键元素 → "Force state" → 勾选 ":hover"，可以强制保持 hover 状态。

**Q: 动画时长怎么测？**
A: 在 Computed 面板找 `transition` 属性。如果找不到，在 Styles 面板搜索 "transition"。

---

*模板版本: 1.0*
*创建于: 2026-04-19*
