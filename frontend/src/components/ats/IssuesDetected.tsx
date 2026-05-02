"use client"

import { motion, AnimatePresence } from "framer-motion"
import { AlertCircle, CheckCircle2, RotateCcw, Sparkles } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import type { AtsIssueItem } from "@/lib/api"

const initialIssues = [
  { id: 1, severity: "Critical", text: "Missing 'Next.js' and 'React' keywords which are required for this role.", fixed: false },
  { id: 2, severity: "Major", text: "Experience gap of 8 months between Stripe and current role not addressed.", fixed: false },
  { id: 3, severity: "Minor", text: "Used weak verb 'Helped' instead of strong action verb 'Spearheaded'.", fixed: false },
  { id: 4, severity: "Minor", text: "Bullet point exceeds 2 lines, decreasing readability.", fixed: false },
]

interface IssuesDetectedProps {
  items?: AtsIssueItem[]
}

export function IssuesDetected({ items }: IssuesDetectedProps) {
  const [issues, setIssues] = useState(initialIssues)
  const backendIssues = (items ?? []).map((item, index) => ({
    id: index + 1,
    severity: item.severity,
    text: item.text,
    fixed: false,
  }))
  const useBackendIssues = backendIssues.length > 0
  const visibleIssues = useBackendIssues ? backendIssues : issues
  const remainingCount = useBackendIssues
    ? visibleIssues.length
    : issues.filter(i => !i.fixed).length

  const fixIssue = (id: number) => {
    setIssues(issues.map(issue => issue.id === id ? { ...issue, fixed: true } : issue))
  }

  const undoFix = (id: number) => {
    setIssues(issues.map(issue => issue.id === id ? { ...issue, fixed: false } : issue))
  }

  return (
    <div className="glass-card border border-border rounded-2xl p-6 h-full flex flex-col">
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-border/50">
        <h3 className="font-bold text-lg flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-rose-500" />
          Issues Detected
        </h3>
        <span className="bg-teal-100 text-teal-700 dark:bg-teal-500/20 dark:text-teal-400 px-3 py-1 rounded-full text-xs font-bold">
          {remainingCount} Remaining
        </span>
      </div>

      <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar flex flex-col gap-4">
        <AnimatePresence mode="popLayout">
          {visibleIssues.map((issue) => {
            
            let severityColor = "bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-400"
            if (issue.severity === "Major") severityColor = "bg-orange-100 text-orange-700 dark:bg-orange-500/20 dark:text-orange-400"
            if (issue.severity === "Minor") severityColor = "bg-yellow-100 text-yellow-700 dark:bg-yellow-500/20 dark:text-yellow-400"
            
            return (
              <motion.div
                key={issue.id}
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                className={`p-4 rounded-xl border transition-all ${
                  issue.fixed 
                    ? "bg-zinc-50 dark:bg-zinc-900/50 border-border opacity-60 grayscale-[0.5]" 
                    : "bg-card border-border hover:shadow-md hover:border-teal-500/30"
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                       {issue.fixed ? (
                         <span className="flex items-center gap-1 text-xs font-bold text-green-600 dark:text-green-500">
                           <CheckCircle2 className="w-3.5 h-3.5" /> Fixed
                         </span>
                       ) : (
                         <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${severityColor}`}>
                           {issue.severity}
                         </span>
                       )}
                    </div>
                    <p className={`text-sm ${issue.fixed ? "line-through text-muted-foreground" : "text-foreground"}`}>
                      {issue.text}
                    </p>
                  </div>
                  
                  {/* Action Button */}
                  <div>
                    {!useBackendIssues && issue.fixed ? (
                      <Button variant="ghost" size="sm" onClick={() => undoFix(issue.id)} className="h-8 text-xs text-muted-foreground">
                        <RotateCcw className="w-3 h-3 mr-1" /> Undo
                      </Button>
                    ) : !useBackendIssues ? (
                      <Button variant="outline" size="sm" onClick={() => fixIssue(issue.id)} className="h-8 text-[11px] font-semibold border-teal-200 dark:border-teal-500/30 text-teal-600 dark:text-teal-400 hover:bg-teal-50 dark:hover:bg-teal-500/20">
                        <Sparkles className="w-3 h-3 mr-1" /> Fix with AI
                      </Button>
                    ) : null}
                    {useBackendIssues ? (
                      <span className="text-xs text-muted-foreground">Reported by backend ATS engine</span>
                    ) : null}
                  </div>
                </div>
                
                {!useBackendIssues && issue.fixed && (
                  <motion.div 
                    initial={{ height: 0, opacity: 0 }} 
                    animate={{ height: "auto", opacity: 1 }}
                    className="mt-3 p-2 rounded bg-green-50 dark:bg-green-500/10 border border-green-200 dark:border-green-500/20 text-xs text-green-800 dark:text-green-300"
                  >
                    AI rewrote the section and increased your score by 4 points.
                  </motion.div>
                )}
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </div>
  )
}
