"use client"

import React, { type ComponentPropsWithoutRef } from "react"
import { AnimatePresence, motion, useReducedMotion, type MotionProps } from "motion/react"

import { cn } from "@/lib/utils"

export function AnimatedListItem({ children }: { children: React.ReactNode }) {
  const shouldReduceMotion = useReducedMotion()
  const animations: MotionProps = {
    initial: shouldReduceMotion ? false : { y: 6, scale: 0.985, opacity: 0 },
    animate: { scale: 1, opacity: 1, originY: 0 },
    exit: shouldReduceMotion ? { opacity: 1 } : { y: -4, scale: 0.985, opacity: 0 },
    transition: shouldReduceMotion
      ? { duration: 0 }
      : { duration: 0.22, ease: [0.16, 1, 0.3, 1] },
  }

  return (
    <motion.div {...animations} layout className="mx-auto w-full">
      {children}
    </motion.div>
  )
}

export interface AnimatedListProps extends ComponentPropsWithoutRef<"div"> {
  children: React.ReactNode
}

export const AnimatedList = React.memo(
  ({ children, className, ...props }: AnimatedListProps) => {
    return (
      <div
        className={cn(`flex flex-col items-center gap-4`, className)}
        {...props}
      >
        <AnimatePresence initial={false} mode="popLayout">
          {React.Children.toArray(children).map((item) => (
            <AnimatedListItem key={(item as React.ReactElement).key}>
              {item}
            </AnimatedListItem>
          ))}
        </AnimatePresence>
      </div>
    )
  }
)

AnimatedList.displayName = "AnimatedList"
