// 通用占位符组件 - 用于图片/图表/地图等多种场景，避免重复结构
export default function Placeholder({ icon: Icon, title, description, spec }) {
  return (
    <div className="placeholder-img">
      <div className="placeholder-content">
        {Icon && <Icon className="placeholder-icon" size={48} />}
        <p className="placeholder-label">{title}</p>
        <p className="placeholder-desc">{description}</p>
        {spec && <p className="placeholder-spec">{spec}</p>}
      </div>
    </div>
  )
}
