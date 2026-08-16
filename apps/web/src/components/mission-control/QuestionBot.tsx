"use client"

import dynamic from "next/dynamic"
import { useReducedMotion } from "motion/react"

import { cn } from "@/lib/utils"

import animationData from "../../../../../assets/Robot-Bot 3D.json"

const Lottie = dynamic(() => import("lottie-react"), { ssr: false })

export function QuestionBot({ className }: { className?: string }) {
  const shouldReduceMotion = useReducedMotion()

  return (
    <div className={cn("question-bot", className)} aria-hidden="true">
      <Lottie
        animationData={animationData}
        autoplay={!shouldReduceMotion}
        loop={!shouldReduceMotion}
        rendererSettings={{ preserveAspectRatio: "xMidYMid meet" }}
      />
    </div>
  )
}
