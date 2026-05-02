"use client"

import { motion } from "framer-motion"
import { ChevronDown } from "lucide-react"
import { useState } from "react"
import type { AtsBreakdownItem } from "@/lib/api"

const breakdownData = [
  { id: "impact", name: "Impact & Metrics", score: 18, total: 25, desc: "We look for quantifiable achievements using numbers, dollars, or percentages." },
  { id: "keywords", name: "Keyword Match", score: 22, total: 25, desc: "How well your skills map to the target job description." },
  { id: "action_verbs", name: "Action Verbs", score: 12, total: 15, desc: "Sentences should begin with strong, varied action verbs." },
  { id: "formatting", name: "Formatting", score: 15, total: 15, desc: "ATS parsers evaluate structure, standard section headers, and margins." },
  { id: "readability", name: "Readability", score: 17, total: 20, desc: "Sentence length, avoid passive voice, and minimize buzzwords." },
]

interface ScoreBreakdownProps {
  items?: AtsBreakdownItem[]
}

export function ScoreBreakdown({ items }: ScoreBreakdownProps) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const breakdownItems = items && items.length > 0 ? items : breakdownData

  return (
    <div className="flex flex-col gap-3">
      <h3 className="font-bold text-lg mb-2">Score Breakdown</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      
      {breakdownItems.map((item, i) => {
        const percentage = (Math.round(item.score / item.total * 100))
        let colorClass = "bg-green-500"
        let bgClass = "bg-green-500/20"
        
        if (percentage < 50) {
          colorClass = "bg-rose-500"
          bgClass = "bg-rose-500/20"
        } else if (percentage < 80) {
          colorClass = "bg-yellow-500"
          bgClass = "bg-yellow-500/20"
        }

        const isExpanded = expanded === item.id

        return (
          <motion.div 
            key={item.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.1 }}
            className="border border-border bg-card rounded-xl overflow-hidden transition-colors hover:border-border/80 cursor-pointer"
            onClick={() => setExpanded(isExpanded ? null : item.id)}
          >
            <div className="p-4 flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-sm">{item.name}</span>
                  <span className="font-bold text-sm">{item.score}<span className="text-muted-foreground font-medium">/{item.total}</span></span>
                </div>
                <div className={`h-2 w-full ${bgClass} rounded-full overflow-hidden`}>
                  <motion.div 
                    initial={{ width: 0 }}
                    whileInView={{ width: `${percentage}%` }}
                    viewport={{ once: true }}
                    transition={{ duration: 1, type: "spring" }}
                    className={`h-full ${colorClass}`}
                  />
                </div>
              </div>
              <ChevronDown className={`w-5 h-5 ml-4 text-muted-foreground transition-transform duration-300 ${isExpanded ? "rotate-180" : ""}`} />
            </div>
            
            {/* Expanded Content */}
            <motion.div 
              initial={false}
              animate={{ height: isExpanded ? "auto" : 0, opacity: isExpanded ? 1 : 0 }}
              className="overflow-hidden bg-zinc-50 dark:bg-zinc-900/50"
            >
              <div className="p-4 border-t border-border text-sm text-muted-foreground">
                {item.desc}
              </div>
            </motion.div>
          </motion.div>
        )
      })}
      </div>
    </div>
  )
}
