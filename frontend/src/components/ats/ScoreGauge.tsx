"use client"

import React, { useEffect, useState } from "react"
import * as d3 from "d3"
import { motion } from "framer-motion"

export function ScoreGauge({ score = 84 }: { score?: number }) {
  const [animatedScore, setAnimatedScore] = useState(0)

  useEffect(() => {
    let startTime: number
    const duration = 1500
    const step = (timestamp: number) => {
      if (!startTime) startTime = timestamp
      const progress = Math.min((timestamp - startTime) / duration, 1)
      const easeProgress = 1 - Math.pow(1 - progress, 3)
      setAnimatedScore(Math.floor(easeProgress * score))
      if (progress < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }, [score])

  // --- Dimensions (everything must fit within the viewBox — no overflow) ---
  // Span: ±126° (0.7π). At the endpoints:
  //   x_end = sin(126°) * labelR  =  0.809 * labelR
  //   y_end = -cos(126°) * labelR =  0.588 * labelR  (below centre)
  // With cy=185, r=100, labelR=118:
  //   bottom of labels = 185 + 0.588*118 = 185 + 69.4 = 254.4  → fits in height 260
  //   top of labels    = 185 - 118       = 67                   → fits easily
  //   widest label x   = ±0.809*118 = ±95.5 → absolute 150±95 = 55..245  → fits in width 300
  const width = 300
  const height = 260
  const cx = width / 2      // 150
  const cy = 185            // arc pivot — leaves room at top and bottom
  const radius = 100
  const thickness = 20
  const startAngle = -Math.PI * 0.7   // −126°
  const endAngle   =  Math.PI * 0.7   //  126°
  const labelR = radius + 18          // 118 — outside the arc ring

  // Background arc
  const bgArc = d3.arc()
    .innerRadius(radius - thickness)
    .outerRadius(radius)
    .startAngle(startAngle)
    .endAngle(endAngle)
    .cornerRadius(12)

  // Score arc (animated)
  const scoreAngle = startAngle + (animatedScore / 100) * (endAngle - startAngle)
  const scoreArc = d3.arc()
    .innerRadius(radius - thickness)
    .outerRadius(radius)
    .startAngle(startAngle)
    .endAngle(scoreAngle)
    .cornerRadius(12)

  // Label + colour
  let label = "Good"
  let color = "#3b82f6"
  if (animatedScore < 50)       { label = "Needs Work"; color = "#ef4444" }
  else if (animatedScore < 75)  { label = "Fair";       color = "#f59e0b" }
  else if (animatedScore > 89)  { label = "Excellent";  color = "#22c55e" }

  const ticks = [0, 25, 50, 75, 100]

  return (
    <div className="flex flex-col items-center">
      {/* SVG — strictly clipped, no overflow:visible */}
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        style={{ display: "block" }}
      >
        <defs>
          <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"   stopColor="#ef4444" />
            <stop offset="33%"  stopColor="#f59e0b" />
            <stop offset="66%"  stopColor="#3b82f6" />
            <stop offset="100%" stopColor="#22c55e" />
          </linearGradient>
          <filter id="gaugeGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        <g transform={`translate(${cx}, ${cy})`}>
          {/* Background track */}
          <path
            d={bgArc({} as d3.DefaultArcObject) as string}
            fill="currentColor"
            className="text-zinc-200 dark:text-zinc-800"
          />

          {/* Coloured score arc */}
          <motion.path
            d={scoreArc({} as d3.DefaultArcObject) as string}
            fill="url(#scoreGradient)"
            filter="url(#gaugeGlow)"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5 }}
          />

          {/* Tick labels — positioned outside the ring */}
          {ticks.map((tick) => {
            const angle = startAngle + (tick / 100) * (endAngle - startAngle)
            const x = Math.sin(angle) * labelR
            const y = -Math.cos(angle) * labelR
            return (
              <text
                key={tick}
                x={x}
                y={y}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize="10"
                className="fill-muted-foreground"
              >
                {tick}
              </text>
            )
          })}
        </g>

        {/* "ATS SCORE" label — inside arc, above the number */}
        <text
          x={cx}
          y={cy - 30}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="10"
          fontWeight="700"
          letterSpacing="3"
          className="fill-muted-foreground uppercase"
        >
          ATS Score
        </text>

        {/* Big animated score number */}
        <motion.text
          x={cx}
          y={cy + 10}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="60"
          fontWeight="800"
          fill={color}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4 }}
        >
          {animatedScore}
        </motion.text>
      </svg>

      {/* Label pill — sits below the SVG with normal document flow */}
      <motion.span
        initial={{ y: 8, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="text-sm font-semibold -mt-6 px-4 py-1 rounded-full bg-zinc-100 dark:bg-zinc-800/50 border border-border"
        style={{ color }}
      >
        {label}
      </motion.span>

      {/* Description text */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1 }}
        className="text-center text-muted-foreground mt-4 max-w-[240px] text-sm"
      >
        Your resume scores better than{" "}
        <strong className="text-foreground">70%</strong> of applicants for this role.
      </motion.p>
    </div>
  )
}
