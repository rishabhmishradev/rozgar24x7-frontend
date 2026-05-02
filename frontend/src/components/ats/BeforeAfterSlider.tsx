"use client"

import { useState, useRef, useEffect } from "react"
import { motion, useMotionValue, useTransform } from "framer-motion"
import { Lock, FileText, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"

export function BeforeAfterSlider({ isUnlocked = false }: { isUnlocked?: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [sliderPosition, setSliderPosition] = useState(50) // percentage
  const [isDragging, setIsDragging] = useState(false)

  const handlePointerDown = () => setIsDragging(true)
  const handlePointerUp = () => setIsDragging(false)
  
  const handlePointerMove = (e: React.PointerEvent) => {
    if (!isDragging || !containerRef.current || !isUnlocked) return
    const rect = containerRef.current.getBoundingClientRect()
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width))
    setSliderPosition((x / rect.width) * 100)
  }

  // Previews mock content
  const originalContent = (
    <div className="p-8 font-serif text-sm opacity-60 pointer-events-none">
      <h2 className="text-xl font-bold mb-4">Experience</h2>
      <div className="mb-4">
        <h3 className="font-bold">Software Engineer, Tech Corp</h3>
        <p className="text-xs italic mb-2">Jan 2021 - Present</p>
        <ul className="list-disc pl-4 space-y-2">
          <li>Worked on the frontend dashboard using React.</li>
          <li>Helped the team improve API load times.</li>
          <li>Built new features for the users.</li>
        </ul>
      </div>
    </div>
  )

  const optimizedContent = (
    <div className="p-8 font-sans text-sm pointer-events-none bg-teal-50/10 h-full">
      <h2 className="text-xl font-bold mb-4 text-teal-900 dark:text-teal-100">Experience</h2>
      <div className="mb-4">
        <h3 className="font-bold text-lg">Senior Frontend Engineer <span className="text-teal-600">@ Tech Corp</span></h3>
        <p className="text-xs text-muted-foreground mb-2 font-medium tracking-wide">Jan 2021 - Present</p>
        <ul className="space-y-3">
          <li className="flex gap-2 relative">
            <span className="text-teal-500 font-bold mt-1">→</span>
            <span><span className="bg-green-500/20 text-green-700 dark:text-green-300 px-1 font-semibold rounded">Spearheaded</span> the development of a high-performance React dashboard, servicing <span className="bg-green-500/20 text-green-700 dark:text-green-300 px-1 font-semibold rounded">100k+ MAU</span>.</span>
          </li>
          <li className="flex gap-2 relative">
            <span className="text-teal-500 font-bold mt-1">→</span>
            <span><span className="bg-green-500/20 text-green-700 dark:text-green-300 px-1 font-semibold rounded">Optimized</span> API payload parsing, <span className="bg-green-500/20 text-green-700 dark:text-green-300 px-1 font-semibold rounded">reducing load times by 40%</span> in the core user flow.</span>
          </li>
        </ul>
      </div>
    </div>
  )

  return (
    <div 
      ref={containerRef}
      className="relative w-full h-[500px] rounded-2xl overflow-hidden border border-border select-none bg-white dark:bg-zinc-950"
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerLeave={handlePointerUp}
    >
      {/* Original State (Underneath) */}
      <div className="absolute inset-0 grayscale">
        <div className="absolute top-4 left-4 bg-zinc-800 text-white text-xs font-bold px-3 py-1 rounded-full z-10">
          Original Resume (Score: 45)
        </div>
        {originalContent}
      </div>

      {/* Optimized State (Clipped on top) */}
      <div 
        className="absolute inset-0 border-r-2 border-teal-500"
        style={{ clipPath: `polygon(0 0, ${sliderPosition}% 0, ${sliderPosition}% 100%, 0 100%)` }}
      >
        <div className="absolute top-4 right-4 bg-teal-600 text-white text-xs font-bold px-3 py-1 rounded-full z-10">
          AI Optimized (Score: 94)
        </div>
        {optimizedContent}
      </div>

      {/* Slider Handle */}
      {isUnlocked && (
        <div 
          className="absolute top-0 bottom-0 w-8 -ml-4 cursor-ew-resize flex items-center justify-center group"
          style={{ left: `${sliderPosition}%` }}
          onPointerDown={handlePointerDown}
        >
          <div className="w-1 h-full bg-teal-500 group-hover:w-1.5 transition-all shadow-[0_0_10px_rgba(99,102,241,0.5)]" />
          <div className="absolute w-8 h-8 bg-white border-2 border-teal-500 rounded-full flex items-center justify-center shadow-lg transform group-hover:scale-110 transition-transform">
            <div className="w-1 h-4 border-l border-r border-teal-300 ml-0.5" />
          </div>
        </div>
      )}

      {/* Blur Gate Upsell when locked */}
      {!isUnlocked && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-background/40 backdrop-blur-md">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-card border border-border/50 shadow-2xl rounded-2xl p-8 max-w-sm text-center relative overflow-hidden"
          >
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 to-teal-500" />
            
            <div className="w-16 h-16 bg-teal-50 dark:bg-teal-500/10 rounded-full flex items-center justify-center mx-auto mb-4 border border-teal-100 dark:border-teal-500/20">
              <Lock className="w-8 h-8 text-teal-500" />
            </div>
            
            <h3 className="text-2xl font-bold mb-2">Unlock Your Optimized Resume</h3>
            
            <div className="flex items-center justify-center gap-3 mb-6">
              <span className="text-3xl font-black">₹199</span>
              <span className="text-lg text-muted-foreground line-through">₹499</span>
              <span className="bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400 text-xs font-bold px-2 py-0.5 rounded-full">60% OFF</span>
            </div>
            
            <ul className="text-sm text-left space-y-3 mb-8 text-muted-foreground">
              <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" /> Full before/after comparison</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" /> Download PDF & DOCX</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" /> One-click apply integrations</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" /> Guaranteed 85+ ATS Score</li>
            </ul>
            
            <Button variant="gradient" className="w-full text-lg h-12">
              Unlock Now
            </Button>
          </motion.div>
        </div>
      )}

      {/* Tease Improvements visible when locked */}
      {!isUnlocked && (
        <div className="absolute bottom-4 left-4 right-4 z-10 flex gap-4 overflow-x-auto hide-scrollbar snap-x">
          <div className="bg-white/90 dark:bg-zinc-900/90 backdrop-blur-sm border border-border p-3 rounded-lg shadow-lg flex-1 min-w-[250px] snap-center">
            <span className="text-[10px] uppercase font-bold text-teal-500 mb-1 block">Improvement #1</span>
            <p className="text-xs font-medium">Replaced weak verb <span className="line-through text-red-500">helped</span> → <span className="text-green-500">spearheaded</span></p>
          </div>
          <div className="bg-white/90 dark:bg-zinc-900/90 backdrop-blur-sm border border-border p-3 rounded-lg shadow-lg flex-1 min-w-[250px] snap-center">
            <span className="text-[10px] uppercase font-bold text-teal-500 mb-1 block">Improvement #2</span>
            <p className="text-xs font-medium">Added quantified achievement <span className="text-green-500">+ reducing load times by 40%</span></p>
          </div>
          <div className="bg-white/90 dark:bg-zinc-900/90 backdrop-blur-sm border border-border p-3 rounded-lg shadow-lg flex-none flex items-center justify-center cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors px-6 snap-center">
            <span className="text-sm font-bold text-teal-500 flex items-center gap-1">See all 23 <ArrowRight className="w-4 h-4" /></span>
          </div>
        </div>
      )}
    </div>
  )
}

function CheckCircle2(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  )
}
