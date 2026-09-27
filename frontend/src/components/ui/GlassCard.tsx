/** 玻璃态卡片：毛玻璃背景 + hover 上浮 + 鼠标跟随的柔和径向光晕。 */

import { useRef, type ReactNode } from 'react'
import { motion, useMotionTemplate, useMotionValue, useSpring } from 'framer-motion'

interface Props {
  children: ReactNode
  className?: string
  /** 禁用 hover 上浮（适用于大面积面板，如 K 线区） */
  noLift?: boolean
}

export default function GlassCard({ children, className = '', noLift = false }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  // 鼠标相对卡片坐标，spring 平滑后驱动径向光晕圆心
  const mx = useMotionValue(-9999)
  const my = useMotionValue(-9999)
  const sx = useSpring(mx, { stiffness: 260, damping: 30 })
  const sy = useSpring(my, { stiffness: 260, damping: 30 })
  const glow = useMotionTemplate`radial-gradient(420px circle at ${sx}px ${sy}px, var(--glass-glow), transparent 65%)`

  const onMove = (e: React.MouseEvent) => {
    const rect = ref.current?.getBoundingClientRect()
    if (!rect) return
    mx.set(e.clientX - rect.left)
    my.set(e.clientY - rect.top)
  }

  const onLeave = () => {
    mx.set(-9999)
    my.set(-9999)
  }

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      className={`group relative overflow-hidden rounded-2xl border border-white/80 bg-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] backdrop-blur-xl transition-transform duration-300 dark:border-white/10 dark:bg-white/[0.06] dark:shadow-[0_8px_30px_rgb(0,0,0,0.25)] ${
        noLift ? '' : 'hover:-translate-y-1'
      } ${className}`}
    >
      {/* 鼠标跟随光晕（不拦截任何鼠标事件） */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{ background: glow }}
      />
      <div className="relative z-10 h-full">{children}</div>
    </div>
  )
}
