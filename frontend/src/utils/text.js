// 文本工具：后端报告为 markdown 文本，列表/卡片等纯文本场景渲染前先剥离标记

// 剥离 markdown 标记并压缩空白，返回纯文本（Risk 仲裁卡片等纯文本场景使用）
export function stripMarkdown(text) {
  return (text || '')
    .replace(/[#>*`_~[\]]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

// 纯文本摘要：先剥离 markdown 再截取，避免标记占用截断长度
export function plainSnippet(text, maxLen = 120) {
  return stripMarkdown(text).slice(0, maxLen)
}
