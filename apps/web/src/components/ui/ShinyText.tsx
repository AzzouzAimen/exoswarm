"use client"

import {
  type CSSProperties,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react"
import {
  motion,
  useAnimationFrame,
  useMotionValue,
  useReducedMotion,
  useTransform,
} from "motion/react"

import { cn } from "../../lib/utils"

export interface ShinyTextProps {
  text: string
  disabled?: boolean
  speed?: number
  className?: string
  color?: string
  shineColor?: string
  spread?: number
  yoyo?: boolean
  pauseOnHover?: boolean
  direction?: "left" | "right"
  delay?: number
}

export default function ShinyText({
  text,
  disabled = false,
  speed = 2,
  className,
  color = "#b5b5b5",
  shineColor = "#ffffff",
  spread = 120,
  yoyo = false,
  pauseOnHover = false,
  direction = "left",
  delay = 0,
}: ShinyTextProps) {
  const [isPaused, setIsPaused] = useState(false)
  const shouldReduceMotion = useReducedMotion()
  const progress = useMotionValue(0)
  const elapsedRef = useRef(0)
  const lastTimeRef = useRef<number | null>(null)
  const directionRef = useRef(direction === "left" ? 1 : -1)
  const effectDisabled = disabled || Boolean(shouldReduceMotion)
  const animationDuration = Math.max(speed, 0.1) * 1000
  const delayDuration = Math.max(delay, 0) * 1000

  useAnimationFrame((time) => {
    if (effectDisabled || isPaused) {
      lastTimeRef.current = null
      return
    }

    if (lastTimeRef.current === null) {
      lastTimeRef.current = time
      return
    }

    elapsedRef.current += time - lastTimeRef.current
    lastTimeRef.current = time

    const cycleDuration = animationDuration + delayDuration

    if (yoyo) {
      const fullCycle = cycleDuration * 2
      const cycleTime = elapsedRef.current % fullCycle

      if (cycleTime < animationDuration) {
        const value = (cycleTime / animationDuration) * 100
        progress.set(directionRef.current === 1 ? value : 100 - value)
      } else if (cycleTime < cycleDuration) {
        progress.set(directionRef.current === 1 ? 100 : 0)
      } else if (cycleTime < cycleDuration + animationDuration) {
        const reverseTime = cycleTime - cycleDuration
        const value = 100 - (reverseTime / animationDuration) * 100
        progress.set(directionRef.current === 1 ? value : 100 - value)
      } else {
        progress.set(directionRef.current === 1 ? 0 : 100)
      }
      return
    }

    const cycleTime = elapsedRef.current % cycleDuration
    if (cycleTime < animationDuration) {
      const value = (cycleTime / animationDuration) * 100
      progress.set(directionRef.current === 1 ? value : 100 - value)
    } else {
      progress.set(directionRef.current === 1 ? 100 : 0)
    }
  })

  useEffect(() => {
    directionRef.current = direction === "left" ? 1 : -1
    elapsedRef.current = 0
    lastTimeRef.current = null
    progress.set(direction === "left" ? 0 : 100)
  }, [direction, progress, text])

  const backgroundPosition = useTransform(progress, (value) => `${150 - value * 2}% center`)

  const handlePointerEnter = useCallback(() => {
    if (pauseOnHover) setIsPaused(true)
  }, [pauseOnHover])

  const handlePointerLeave = useCallback(() => {
    if (pauseOnHover) setIsPaused(false)
  }, [pauseOnHover])

  const rootClassName = cn("inline-block max-w-full", className)

  if (effectDisabled) {
    return (
      <span className={rootClassName} style={{ color }}>
        {text}
      </span>
    )
  }

  const gradientStyle: CSSProperties = {
    color,
    backgroundImage: `linear-gradient(${spread}deg, ${color} 0%, ${color} 35%, ${shineColor} 50%, ${color} 65%, ${color} 100%)`,
    backgroundSize: "200% auto",
    WebkitBackgroundClip: "text",
    backgroundClip: "text",
    WebkitTextFillColor: "transparent",
  }

  return (
    <motion.span
      className={rootClassName}
      style={{ ...gradientStyle, backgroundPosition }}
      onPointerEnter={handlePointerEnter}
      onPointerLeave={handlePointerLeave}
    >
      {text}
    </motion.span>
  )
}
