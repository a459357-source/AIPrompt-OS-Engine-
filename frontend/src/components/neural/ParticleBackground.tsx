import { useEffect, useRef } from 'react'
import { useAdultThemeOptional } from '@/contexts/AdultThemeContext'

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  size: number
  alpha: number
  hue: number
}

export function ParticleBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const adultMode = useAdultThemeOptional()?.adultMode ?? false

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const isMobile = window.innerWidth < 768
    if (reducedMotion || isMobile) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animId = 0
    let particles: Particle[] = []

    const isAdult = ['adult', 'desire'].includes(document.documentElement.getAttribute('data-ui-theme') ?? '')
    const speedMul = isAdult ? 0.12 : 0.3
    const maxLinkDist = isAdult ? 80 : 120
    const particleColor = isAdult
      ? (a: number, h: number) => `hsla(${h}, 75%, 68%, ${a})`
      : (a: number) => `rgba(79, 140, 255, ${a})`
    const lineColor = isAdult
      ? (a: number) => `rgba(236, 72, 153, ${a})`
      : (a: number) => `rgba(124, 92, 255, ${a})`

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
      const density = isAdult ? 40000 : 25000
      const count = Math.min(isAdult ? 35 : 60, Math.floor((canvas.width * canvas.height) / density))
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * speedMul,
        vy: (Math.random() - 0.5) * speedMul,
        size: Math.random() * (isAdult ? 2.2 : 1.5) + 0.5,
        alpha: Math.random() * (isAdult ? 0.2 : 0.4) + 0.04,
        hue: isAdult ? 330 + Math.random() * 30 : 210,
      }))
    }

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      for (const p of particles) {
        p.x += p.vx
        p.y += p.vy
        if (p.x < 0) p.x = canvas.width
        if (p.x > canvas.width) p.x = 0
        if (p.y < 0) p.y = canvas.height
        if (p.y > canvas.height) p.y = 0

        ctx.beginPath()
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
        ctx.fillStyle = isAdult ? particleColor(p.alpha, p.hue) : particleColor(p.alpha, 0)
        ctx.fill()

        if (isAdult) {
          const grd = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 8)
          grd.addColorStop(0, `rgba(255, 0, 77, ${p.alpha * 0.12})`)
          grd.addColorStop(1, 'transparent')
          ctx.beginPath()
          ctx.arc(p.x, p.y, p.size * 8, 0, Math.PI * 2)
          ctx.fillStyle = grd
          ctx.fill()
        }
      }

      if (!isAdult) {
        for (let i = 0; i < particles.length; i++) {
          for (let j = i + 1; j < particles.length; j++) {
            const a = particles[i]
            const b = particles[j]
            const dx = a.x - b.x
            const dy = a.y - b.y
            const dist = Math.sqrt(dx * dx + dy * dy)
            if (dist < maxLinkDist) {
              ctx.beginPath()
              ctx.moveTo(a.x, a.y)
              ctx.lineTo(b.x, b.y)
              ctx.strokeStyle = lineColor(0.08 * (1 - dist / maxLinkDist))
              ctx.lineWidth = 0.5
              ctx.stroke()
            }
          }
        }
      }

      animId = requestAnimationFrame(draw)
    }

    resize()
    draw()
    window.addEventListener('resize', resize)
    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [adultMode])

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0 opacity-60 transition-opacity duration-[800ms]"
      aria-hidden
    />
  )
}
