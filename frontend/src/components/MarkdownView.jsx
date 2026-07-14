// 轻量 Markdown 渲染：把 Agent 返回的 markdown 文本格式化成可读卡片
import React from 'react'
import './MarkdownView.css'

export default function MarkdownView({ content }) {
  if (!content) return null

  // 简单按行解析 markdown，不支持复杂嵌套
  const lines = content.split('\n')
  const elements = []
  let key = 0

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue

    // 标题
    if (line.startsWith('## ')) {
      elements.push(
        <h3 key={key++} className="md-h2">{line.replace('## ', '')}</h3>
      )
      continue
    }
    if (line.startsWith('### ')) {
      elements.push(
        <h4 key={key++} className="md-h3">{line.replace('### ', '')}</h4>
      )
      continue
    }
    if (line.startsWith('# ')) {
      elements.push(
        <h2 key={key++} className="md-h1">{line.replace('# ', '')}</h2>
      )
      continue
    }

    // 列表项
    if (line.startsWith('- ') || line.startsWith('* ')) {
      const text = line.slice(2)
      elements.push(
        <div key={key++} className="md-list-item">
          <span className="md-bullet">•</span>
          <span>{renderInline(text)}</span>
        </div>
      )
      continue
    }

    // 数字列表
    if (/^\d+\.\s/.test(line)) {
      const text = line.replace(/^\d+\.\s/, '')
      elements.push(
        <div key={key++} className="md-list-item">
          <span className="md-number">{line.match(/^\d+/)[0]}.</span>
          <span>{renderInline(text)}</span>
        </div>
      )
      continue
    }

    // 普通段落
    elements.push(
      <p key={key++} className="md-paragraph">{renderInline(line)}</p>
    )
  }

  return <div className="markdown-view">{elements}</div>
}

// 简单内联格式：加粗、代码
function renderInline(text) {
  const parts = []
  const regex = /(\*\*([^*]+)\*\*)|(`([^`]+)`)/g
  let lastIndex = 0
  let match
  let key = 0

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(<span key={key++}>{text.slice(lastIndex, match.index)}</span>)
    }
    if (match[1]) {
      parts.push(<strong key={key++} className="md-strong">{match[2]}</strong>)
    } else if (match[3]) {
      parts.push(<code key={key++} className="md-code">{match[4]}</code>)
    }
    lastIndex = regex.lastIndex
  }

  if (lastIndex < text.length) {
    parts.push(<span key={key++}>{text.slice(lastIndex)}</span>)
  }

  if (parts.length === 0) return text
  return parts
}