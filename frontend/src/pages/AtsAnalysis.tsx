"use client"

import { useState, useRef, useEffect } from "react"
import { toast } from "sonner"
import { motion, AnimatePresence } from "framer-motion"
import { ScoreGauge } from "@/components/ats/ScoreGauge"
import { ScoreBreakdown } from "@/components/ats/ScoreBreakdown"
import { IssuesDetected } from "@/components/ats/IssuesDetected"
import { BeforeAfterSlider } from "@/components/ats/BeforeAfterSlider"
import { Button } from "@/components/ui/button"
import { analyzeAts, type AtsAnalyzeResponse } from "@/lib/api"
import {
  Upload, FileText, Loader2, Download, Share2,
  CheckCircle2, Sparkles, X, FileUp, Zap, MessageCircle, Mail, ExternalLink,
  ChevronDown, Briefcase, ClipboardList, ChevronRight, AlertTriangle, UserCheck, Search, Check,
  FileSearch, Wand2, Users, Clock, Headphones, type LucideIcon
} from "lucide-react"

type Stage = "upload" | "analyzing" | "results"

interface JobExample {
  title: string
  company: string
  level: string
  badge: string
  badgeColor: string
  description: string
  skills: string[]
}

const JOB_EXAMPLES: JobExample[] = [
  {
    title: "Senior Frontend Engineer",
    company: "Google",
    level: "Senior · IC4",
    badge: "Tech",
    badgeColor: "blue",
    description: "Build next-gen web experiences with React, TypeScript & performance optimization at scale.",
    skills: ["React", "TypeScript", "Next.js", "GraphQL"],
  },
  {
    title: "Full Stack Engineer",
    company: "Stripe",
    level: "Mid-Level · L3",
    badge: "Tech",
    badgeColor: "blue",
    description: "Design and ship robust API services and polished UIs for global payment infrastructure.",
    skills: ["Node.js", "React", "PostgreSQL", "AWS"],
  },
  {
    title: "Backend Software Engineer",
    company: "Amazon",
    level: "Senior · SDE-II",
    badge: "Tech",
    badgeColor: "blue",
    description: "Architect distributed microservices handling millions of transactions per second.",
    skills: ["Java", "AWS", "Microservices", "DynamoDB"],
  },
  {
    title: "Machine Learning Engineer",
    company: "OpenAI",
    level: "Senior · L5",
    badge: "AI / ML",
    badgeColor: "purple",
    description: "Train and fine-tune large language models for production-grade AI products.",
    skills: ["Python", "PyTorch", "LLMs", "CUDA"],
  },
  {
    title: "Data Scientist",
    company: "Netflix",
    level: "Mid-Level · L4",
    badge: "AI / ML",
    badgeColor: "purple",
    description: "Drive personalisation algorithms that serve 260 M+ subscribers worldwide.",
    skills: ["Python", "Spark", "SQL", "A/B Testing"],
  },
  {
    title: "AI Research Scientist",
    company: "DeepMind",
    level: "Senior · Research",
    badge: "AI / ML",
    badgeColor: "purple",
    description: "Publish cutting-edge research in reinforcement learning and multi-agent systems.",
    skills: ["Python", "JAX", "RL", "Mathematics"],
  },
  {
    title: "Product Manager",
    company: "Meta",
    level: "Senior · IC5",
    badge: "Product",
    badgeColor: "teal",
    description: "Own the roadmap for a social platform feature used by 3 billion people.",
    skills: ["Roadmapping", "SQL", "OKRs", "User Research"],
  },
  {
    title: "Product Manager",
    company: "Atlassian",
    level: "Associate · IC3",
    badge: "Product",
    badgeColor: "teal",
    description: "Collaborate with engineering and design to deliver Jira and Confluence features.",
    skills: ["Agile", "JIRA", "Analytics", "Prototyping"],
  },
  {
    title: "UX / UI Designer",
    company: "Apple",
    level: "Senior · ICT4",
    badge: "Design",
    badgeColor: "pink",
    description: "Craft pixel-perfect experiences for iOS, macOS and visionOS platforms.",
    skills: ["Figma", "SwiftUI", "Prototyping", "HIG"],
  },
  {
    title: "Lead Product Designer",
    company: "Figma",
    level: "Lead · IC5",
    badge: "Design",
    badgeColor: "pink",
    description: "Define the visual language and interaction patterns for the Figma design tool itself.",
    skills: ["Figma", "Systems", "Motion", "User Testing"],
  },
  {
    title: "DevOps / Platform Engineer",
    company: "Cloudflare",
    level: "Mid-Level · L3",
    badge: "Infra",
    badgeColor: "orange",
    description: "Automate CI/CD pipelines and manage global edge infrastructure for millions of sites.",
    skills: ["Kubernetes", "Terraform", "Go", "Prometheus"],
  },
  {
    title: "Cloud Solutions Architect",
    company: "Microsoft Azure",
    level: "Senior · L62",
    badge: "Infra",
    badgeColor: "orange",
    description: "Guide enterprise clients through cloud migrations and greenfield Azure deployments.",
    skills: ["Azure", "ARM", "Networking", "Security"],
  },
  {
    title: "Cybersecurity Analyst",
    company: "IBM Security",
    level: "Mid-Level · Band 7",
    badge: "Security",
    badgeColor: "red",
    description: "Detect, contain and remediate threats across Fortune 500 client environments.",
    skills: ["SIEM", "Splunk", "NIST", "Incident Response"],
  },
  {
    title: "Mobile App Developer",
    company: "Spotify",
    level: "Mid-Level · L4",
    badge: "Mobile",
    badgeColor: "green",
    description: "Build performant React Native and native features for 600 M+ Spotify users.",
    skills: ["React Native", "Swift", "Kotlin", "GraphQL"],
  },
  {
    title: "QA / Test Automation Engineer",
    company: "Salesforce",
    level: "Senior · MTS",
    badge: "QA",
    badgeColor: "indigo",
    description: "Own end-to-end test strategy and Selenium/Cypress automation for Salesforce CRM.",
    skills: ["Cypress", "Selenium", "JIRA", "CI/CD"],
  },
  {
    title: "Business Analyst",
    company: "McKinsey & Co.",
    level: "Analyst · Entry",
    badge: "Business",
    badgeColor: "teal",
    description: "Deliver data-driven insights and process improvement strategies for global clients.",
    skills: ["Excel", "PowerBI", "SQL", "Stakeholder Mgmt"],
  },
  {
    title: "Financial Analyst",
    company: "Goldman Sachs",
    level: "Associate · AN2",
    badge: "Finance",
    badgeColor: "yellow",
    description: "Model valuations, build pitch books and support M&A transactions in IBD.",
    skills: ["Excel", "DCF", "Bloomberg", "PowerPoint"],
  },
  {
    title: "Marketing Manager",
    company: "HubSpot",
    level: "Senior · IC4",
    badge: "Marketing",
    badgeColor: "orange",
    description: "Lead demand-gen campaigns across SEO, paid, and lifecycle channels.",
    skills: ["HubSpot", "Google Ads", "SEO", "Analytics"],
  },
  {
    title: "Project Manager (PMP)",
    company: "Accenture",
    level: "Senior · Level 8",
    badge: "Management",
    badgeColor: "indigo",
    description: "Manage cross-functional delivery of digital transformation projects end-to-end.",
    skills: ["PMP", "Agile", "Risk Mgmt", "Stakeholders"],
  },
  {
    title: "Human Resources Manager",
    company: "LinkedIn",
    level: "Senior · L5",
    badge: "HR",
    badgeColor: "green",
    description: "Partner with business leaders on talent acquisition, DEI, and performance management.",
    skills: ["Workday", "HRBP", "Recruiting", "L&D"],
  },
]

const PRICING_PLANS = [
  {
    name: "Pro",
    description: "For serious job seekers",
    originalPrice: 1500,
    price: 500,
    features: [
      "Unlimited ATS score analysis",
      "ATS-optimized resume formats(ready-to-download)",
      "Early bird offers access",
      "Help desk access",
    ],
    highlight: false,
    whatsappLink: "https://wa.me/918989973328?text=Hello%2C%20I%20am%20interested%20in%20purchasing%20the%20%E2%82%B9500%20Pro%20Plan%20%28ATS%20Resume%20Services%29.%0A%0AName%3A%20%0APhone%20Number%3A%20%0A%0APlease%20assist%20me%20with%20the%20payment%20details%20and%20further%20process.",
  },
  {
    name: "Max",
    description: "White-glove career strategy",
    originalPrice: 3000,
    price: 800,
    features: [
      "Get your resume within 24 hrs",
      "1:1 Mentor Calls",
      "Expert-crafted ATS-optimized resume",
      "Personalized mentor guidance (career + resume)",
      "Early bird offers access",
      "Help desk access",
    ],
    highlight: true,
    whatsappLink: "https://wa.me/918989973328?text=Hello%2C%20I%20am%20interested%20in%20purchasing%20the%20%E2%82%B9800%20Max%20Plan%20%28Premium%20Resume%20%26%20Career%20Guidance%29.%0A%0AName%3A%20%0APhone%20Number%3A%20%0A%0APlease%20assist%20me%20with%20the%20payment%20details%20and%20further%20process.",
  }
]

const PRICING_ICON_MAP: Record<string, LucideIcon> = {
  "Unlimited ATS score analysis": FileSearch,
  "ATS-optimized resume formats(ready-to-download)": Download,
  "Early bird offers access": Sparkles,
  "Help desk access": Headphones,
  "Get your resume within 24 hrs": Clock,
  "1:1 Mentor Calls": Users,
  "Expert-crafted ATS-optimized resume": Wand2,
  "Personalized mentor guidance (career + resume)": Users,
}

const JD_ITEMS: string[] = [
  "AI/ML Engineer",
  "Generative AI Engineer",
  "NLP Specialist",
  "Computer Vision Engineer",
  "AI Ethics & Compliance Officer",
  "AI Product Manager",
  "Machine Learning Scientist",
  "Robotics Engineer",
  "Data Scientist",
  "Data Engineer",
  "Big Data Architect",
  "Business Intelligence Analyst",
  "Data Governance Specialist",
  "Full-Stack Developer",
  "Backend Engineer",
  "Frontend Engineer",
  "Mobile App Developer",
  "Blockchain Developer",
  "Embedded Systems Engineer",
  "Game Developer",
  "Cloud Solutions Architect",
  "DevOps Engineer",
  "Site Reliability Engineer (SRE)",
  "Platform Engineer",
  "FinOps Specialist",
  "Cybersecurity Analyst",
  "Ethical Hacker (Penetration Tester)",
  "Application Security Engineer",
  "UI/UX Designer",
  "IT Project Manager",
]

export default function AtsAnalysisPage() {
  const [stage, setStage] = useState<Stage>("upload")
  const [file, setFile] = useState<File | null>(null)
  const [fileUrl, setFileUrl] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [progress, setProgress] = useState(0)
  const [jobRole, setJobRole] = useState("")
  const [showJobDropdown, setShowJobDropdown] = useState(false)
  const [filteredJobs, setFilteredJobs] = useState<JobExample[]>(JOB_EXAMPLES)
  const [customJd, setCustomJd] = useState("")
  const [showJdPanel, setShowJdPanel] = useState(false)
  const [showMentorPopup, setShowMentorPopup] = useState(false)
  const [analysisResult, setAnalysisResult] = useState<AtsAnalyzeResponse | null>(null)
  const [selectedJdItems, setSelectedJdItems] = useState<Set<string>>(new Set())
  const [jdSearch, setJdSearch] = useState("")
  const [showJdDropdown, setShowJdDropdown] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const jobDropdownRef = useRef<HTMLDivElement>(null)
  const jobInputRef = useRef<HTMLDivElement>(null)
  const jdDropdownRef = useRef<HTMLDivElement>(null)

  const handleFile = (f: File) => {
    if (!f) return
    setFile(f)
    setFileUrl(URL.createObjectURL(f))
  }

  // Close job-role dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (jobDropdownRef.current && !jobDropdownRef.current.contains(e.target as Node)) {
        setShowJobDropdown(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  // Close JD dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (jdDropdownRef.current && !jdDropdownRef.current.contains(e.target as Node)) {
        setShowJdDropdown(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const toggleJdItem = (item: string) => {
    setSelectedJdItems((prev) => {
      const next = new Set(prev)
      next.has(item) ? next.delete(item) : next.add(item)
      return next
    })
  }

  const openDropdown = () => {
    setShowJobDropdown(true)
  }

  const handleJobRoleChange = (value: string) => {
    setJobRole(value)
    const q = value.toLowerCase()
    setFilteredJobs(
      q
        ? JOB_EXAMPLES.filter(
            (j) =>
              j.title.toLowerCase().includes(q) ||
              j.company.toLowerCase().includes(q) ||
              j.badge.toLowerCase().includes(q)
          )
        : JOB_EXAMPLES
    )
    openDropdown()
  }

  const selectJobRole = (job: JobExample) => {
    setJobRole(`${job.title} at ${job.company}`)
    setShowJobDropdown(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) handleFile(f)
  }

  const startAnalysis = async () => {
    if (!file) return
    setStage("analyzing")
    setProgress(0)
    setAnalysisResult(null)

    const selectedRoles = Array.from(selectedJdItems)
    const derivedTargetRole = jobRole.trim() || selectedRoles.join(", ")
    const derivedJdText = customJd.trim()

    if (!jobRole.trim() && derivedTargetRole) {
      setJobRole(derivedTargetRole)
    }

    // Keep progress moving while backend analysis runs.
    const progressTimer = window.setInterval(() => {
      setProgress((prev) => (prev < 90 ? prev + 5 : prev))
    }, 220)

    try {
      const result = await analyzeAts({
        resumeFile: file,
        jdText: derivedJdText || undefined,
        targetRole: derivedTargetRole || undefined,
      })

      setAnalysisResult(result)
      setProgress(100)
      setStage("results")
      setShowMentorPopup((result.ats_score ?? 0) < 75)
    } catch (error) {
      setStage("upload")
      setProgress(0)
      const message = error instanceof Error ? error.message : "Failed to analyze resume"
      toast.error("ATS analysis failed", { description: message })
    } finally {
      window.clearInterval(progressTimer)
    }
  }

  const reset = () => {
    setStage("upload")
    setFile(null)
    setFileUrl(null)
    setProgress(0)
    setJobRole("")
    setCustomJd("")
    setSelectedJdItems(new Set())
    setJdSearch("")
    setShowJdPanel(false)
    setShowJdDropdown(false)
    setShowMentorPopup(false)
    setAnalysisResult(null)
  }

  const handleShare = (method: "whatsapp" | "email") => {
    const score = analysisResult?.ats_score ?? 0
    const message = `Check out my ATS analysis results! Target Role: ${jobRole || "Professional"}. Score: ${score}/100.`
    if (method === "whatsapp") {
      window.open(`https://wa.me/?text=${encodeURIComponent(message)}`, "_blank")
    } else {
      window.open(`mailto:?subject=ATS Analysis Results&body=${encodeURIComponent(message)}`, "_blank")
    }
    
    // Professional popup notification
    toast.success("Resume Sent for Enhancement", {
      description: "Our professional team will review your resume and provide feedback shortly.",
      duration: 5000,
      icon: <Sparkles className="w-4 h-4 text-teal-500" />,
    })
  }

  return (
    <main className="relative min-h-screen bg-zinc-50 dark:bg-zinc-950 flex flex-col selection:bg-teal-500/30 bg-hero-gradient">
      {/* Background Elements */}
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
        <div className="absolute inset-0 bg-dot-pattern pointer-events-none" />
        <div className="absolute top-[10%] left-[-5%] w-[500px] h-[500px] bg-blue-500/[0.03] blur-[100px] rounded-full animate-blob pointer-events-none" />
        <div className="absolute top-[30%] right-[-10%] w-[400px] h-[400px] bg-teal-500/[0.02] blur-[100px] rounded-full animate-blob animation-delay-2000 pointer-events-none" />
        <div className="absolute bottom-[-10%] left-[20%] w-[600px] h-[600px] bg-cyan-500/[0.02] blur-[120px] rounded-full animate-blob animation-delay-4000 pointer-events-none" />
        <div className="absolute top-[60%] right-[10%] w-[300px] h-[300px] bg-blue-500/[0.02] blur-[80px] rounded-full animate-float-slow pointer-events-none" />

        {/* Floating accent circles */}
        <div className="absolute top-[15%] left-[5%] w-3 h-3 bg-teal-400/[0.08] rounded-full animate-float hidden lg:block" />
        <div className="absolute top-[25%] left-[3%] w-2 h-2 bg-blue-400/[0.1] rounded-full animate-float animation-delay-2000 hidden lg:block" />
        <div className="absolute top-[45%] left-[2%] w-4 h-4 bg-cyan-400/[0.06] rounded-full animate-float-slow hidden lg:block" />
        <div className="absolute top-[20%] right-[3%] w-3 h-3 bg-teal-400/[0.08] rounded-full animate-float animation-delay-4000 hidden lg:block" />
        <div className="absolute top-[60%] right-[5%] w-2 h-2 bg-blue-400/[0.1] rounded-full animate-float-slow animation-delay-2000 hidden lg:block" />

        {/* Side gradient glows */}
        <div className="absolute top-0 left-0 w-1/4 h-full bg-gradient-to-r from-blue-500/[0.02] to-transparent pointer-events-none" />
        <div className="absolute top-0 right-0 w-1/4 h-full bg-gradient-to-l from-teal-500/[0.02] to-transparent pointer-events-none" />
      </div>
      <div className="h-10 relative z-10 flex-none" />

      <div className="flex-1 container px-6 mx-auto py-8 relative z-20">
        <AnimatePresence mode="wait">

          {/* ─── UPLOAD STAGE ─── */}
          {stage === "upload" && (
            <motion.div
              key="upload"
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
            >
              {/* Header */}
              <div className="text-center mb-12">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-500/10 text-teal-600 dark:text-teal-400 text-sm font-medium mb-4 border border-teal-500/20">
                  <Zap className="w-4 h-4" /> AI-Powered ATS Scanner
                </div>
                <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
                  Check Your ATS Score
                </h1>
                <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
                  Upload your resume and get an instant ATS compatibility score with actionable improvements.
                </p>
              </div>

              <div className="max-w-2xl mx-auto space-y-6">
                {/* Drop Zone */}
                <div
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`relative flex flex-col items-center justify-center gap-4 min-h-[120px] h-auto py-8 md:h-64 md:py-0 w-full rounded-3xl border-2 border-dashed cursor-pointer transition-all duration-300 select-none ${
                    dragOver
                      ? "border-teal-500 bg-teal-500/5 scale-[1.01]"
                      : file
                      ? "border-green-500 bg-green-500/5"
                      : "border-border bg-card hover:border-teal-400 hover:bg-teal-500/5"
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.doc,.docx"
                    className="hidden"
                    onChange={handleInputChange}
                  />

                  {file ? (
                    <>
                      <div className="w-14 h-14 rounded-2xl bg-green-500/10 flex items-center justify-center">
                        <CheckCircle2 className="w-7 h-7 text-green-500" />
                      </div>
                      <div className="text-center w-full px-4 overflow-hidden">
                        <p className="font-semibold text-foreground truncate max-w-full">{file.name}</p>
                        <p className="text-sm text-muted-foreground mt-1">
                          {(file.size / 1024).toFixed(1)} KB · Ready to analyze
                        </p>
                      </div>
                      <button
                        className="absolute top-4 right-4 text-muted-foreground hover:text-foreground transition-colors"
                        onClick={(e) => { e.stopPropagation(); setFile(null) }}
                      >
                        <X className="w-5 h-5" />
                      </button>
                    </>
                  ) : (
                    <>
                      <div className="w-14 h-14 rounded-2xl bg-teal-500/10 flex items-center justify-center">
                        <FileUp className="w-7 h-7 text-teal-500" />
                      </div>
                      <div className="text-center w-full px-4">
                        <p className="font-semibold text-foreground text-sm md:text-base">Drop your resume here</p>
                        <p className="text-sm text-muted-foreground mt-1">or click to browse</p>
                        <p className="text-xs text-muted-foreground/60 mt-2">PDF, DOC, DOCX · Max 10 MB</p>
                      </div>
                    </>
                  )}
                </div>

                {/* ── JD Responsibilities Dropdown ── */}
                <div ref={jdDropdownRef} className="relative z-40">
                  {/* Toggle header card */}
                  <button
                    type="button"
                    onClick={() => { setShowJdPanel((v) => !v); setShowJdDropdown(false) }}
                    className={`flex w-full items-center gap-3 px-4 py-3.5 text-left rounded-2xl border transition-colors group ${
                      selectedJdItems.size > 0
                        ? "border-teal-500/40 bg-teal-500/5"
                        : "border-border bg-card hover:bg-muted/40"
                    }`}
                  >
                    <div className={`flex items-center justify-center w-8 h-8 rounded-xl transition-colors ${
                      selectedJdItems.size > 0
                        ? "bg-teal-500/15 text-teal-600 dark:text-teal-400"
                        : "bg-muted text-muted-foreground group-hover:bg-teal-500/10 group-hover:text-teal-500"
                    }`}>
                      <ClipboardList className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground flex items-center gap-2">
                        Select Job Roles
                        <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20">
                          Optional
                        </span>
                        {selectedJdItems.size > 0 && (
                          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-green-500/10 text-green-600 dark:text-green-400 border border-green-500/20">
                            ✓ {selectedJdItems.size} selected
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {selectedJdItems.size > 0
                          ? "Click to review or modify selections"
                          : "Select roles to build a targeted JD"}
                      </p>
                    </div>
                    <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform duration-200 ${
                      showJdPanel ? "rotate-180" : ""
                    }`} />
                  </button>

                  {/* Dropdown panel */}
                  {showJdPanel && (
                    <div className="absolute left-0 right-0 top-full mt-2 z-[9999] rounded-2xl border border-border bg-white dark:bg-zinc-900 shadow-2xl overflow-hidden">
                      {/* Search + header */}
                      <div className="px-4 py-3 border-b border-border bg-zinc-50 dark:bg-zinc-800/60 flex items-center gap-3">
                        <div className="relative flex-1">
                          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
                          <input
                            type="text"
                            value={jdSearch}
                            onChange={(e) => setJdSearch(e.target.value)}
                            placeholder="Search roles..."
                            className="w-full h-8 rounded-lg border border-border bg-card pl-8 pr-3 text-xs focus:outline-none focus:ring-2 focus:ring-teal-500/50 transition-all"
                            onClick={(e) => e.stopPropagation()}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground whitespace-nowrap shrink-0">
                          {selectedJdItems.size}/{JD_ITEMS.length} selected
                        </span>
                        {selectedJdItems.size > 0 && (
                          <button
                            type="button"
                            onMouseDown={(e) => { e.preventDefault(); setSelectedJdItems(new Set()) }}
                            className="text-xs text-red-500 hover:text-red-600 transition-colors shrink-0 flex items-center gap-1"
                          >
                            <X className="w-3 h-3" /> Clear
                          </button>
                        )}
                      </div>

                      {/* Items list */}
                      <div className="max-h-[320px] overflow-y-auto divide-y divide-border">
                        {JD_ITEMS
                          .filter((item) =>
                            jdSearch.trim() === "" ||
                            item.toLowerCase().includes(jdSearch.toLowerCase())
                          )
                          .map((item) => {
                            const checked = selectedJdItems.has(item)
                            return (
                              <button
                                key={item}
                                type="button"
                                onMouseDown={(e) => { e.preventDefault(); toggleJdItem(item) }}
                                className={`flex items-start gap-3 w-full px-4 py-3 text-left transition-colors ${
                                  checked
                                    ? "bg-teal-500/8 dark:bg-teal-500/10"
                                    : "hover:bg-zinc-50 dark:hover:bg-zinc-800/60"
                                }`}
                              >
                                {/* Checkbox */}
                                <span className={`mt-0.5 shrink-0 w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                                  checked
                                    ? "bg-teal-500 border-teal-500"
                                    : "border-border bg-card"
                                }`}>
                                  {checked && (
                                    <CheckCircle2 className="w-3 h-3 text-white" />
                                  )}
                                </span>
                                <span className={`text-xs leading-relaxed ${
                                  checked ? "text-teal-700 dark:text-teal-300 font-medium" : "text-foreground"
                                }`}>
                                  {item}
                                </span>
                              </button>
                            )
                          })
                        }
                      </div>

                      {/* Footer */}
                      <div className="px-4 py-3 border-t border-border bg-zinc-50 dark:bg-zinc-800/60 flex items-center justify-between">
                        <p className="text-xs text-muted-foreground">
                          Selected responsibilities will be used to match your resume.
                        </p>
                        <button
                          type="button"
                          onMouseDown={(e) => { e.preventDefault(); setShowJdPanel(false) }}
                          className="text-xs font-semibold text-teal-600 dark:text-teal-400 hover:underline shrink-0 ml-4"
                        >
                          Done
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* ── Paste Custom JD Textarea ── */}
                <div className="relative group">
                  <div className="flex w-full items-start gap-3 px-4 py-3.5 text-left rounded-2xl border border-border bg-card transition-colors">
                    <div className="flex items-center justify-center w-8 h-8 rounded-xl bg-muted text-muted-foreground mt-0.5">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <label className="text-sm font-medium text-foreground block">
                        Job Description
                        <span className="ml-2 text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20">
                          Optional
                        </span>
                      </label>
                      <textarea
                        value={customJd}
                        onChange={(e) => setCustomJd(e.target.value)}
                        placeholder="Paste the target job description or copy/paste the requirements here to match your resume against them."
                        className="w-full bg-transparent border-none p-0 text-sm text-muted-foreground mt-1.5 focus:ring-0 focus:outline-none placeholder:text-muted-foreground/40 resize-y min-h-[160px] leading-relaxed"
                      />
                    </div>
                  </div>
                </div>

                {/* Analyze Button */}
                <Button
                  variant="gradient"
                  className="w-full h-12 text-base"
                  onClick={startAnalysis}
                  disabled={!file}
                >
                  <Sparkles className="w-4 h-4 mr-2" />
                  Analyze My Resume
                </Button>

                {/* Trust badges */}
                <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-8 text-xs text-muted-foreground pt-2">
                  {["Private & Secure", "Instant Results", "Free to Use"].map((t) => (
                    <span key={t} className="flex items-center gap-1.5 whitespace-nowrap">
                      <CheckCircle2 className="w-3.5 h-3.5 text-green-500" /> {t}
                    </span>
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {/* ─── ANALYZING STAGE ─── */}
          {stage === "analyzing" && (
            <motion.div
              key="analyzing"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center min-h-[60vh] gap-8"
            >
              {/* Pulsing orb */}
              <div className="relative flex items-center justify-center">
                <div className="absolute w-40 h-40 rounded-full bg-teal-500/20 animate-ping" />
                <div className="absolute w-28 h-28 rounded-full bg-teal-500/30 animate-pulse" />
                <div className="relative w-20 h-20 rounded-full bg-gradient-to-br from-blue-600 to-teal-600 flex items-center justify-center shadow-xl shadow-teal-500/40">
                  <Loader2 className="w-8 h-8 text-white animate-spin" />
                </div>
              </div>

              <div className="text-center max-w-sm space-y-2">
                <h2 className="text-2xl font-bold">Scanning Your Resume</h2>
                <p className="text-muted-foreground text-sm">{file?.name}</p>
              </div>

              {/* Progress bar */}
              <div className="w-full max-w-sm space-y-3">
                <div className="h-2.5 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-blue-600 to-teal-500 rounded-full"
                    initial={{ width: "0%" }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.6, ease: "easeOut" }}
                  />
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>
                    {progress < 30 ? "Parsing document..." :
                     progress < 60 ? "Extracting keywords..." :
                     progress < 80 ? "Checking ATS compatibility..." :
                     progress < 100 ? "Generating insights..." :
                     "Complete!"}
                  </span>
                  <span>{progress}%</span>
                </div>
              </div>

              {/* Checklist items that appear */}
              <div className="w-full max-w-sm space-y-2">
                {[
                  { label: "Format & Structure", threshold: 20 },
                  { label: "Keyword Density", threshold: 45 },
                  { label: "ATS Parsing", threshold: 65 },
                  { label: "Skills Matching", threshold: 85 },
                ].map(({ label, threshold }) => (
                  <motion.div
                    key={label}
                    initial={{ opacity: 0, x: -10 }}
                    animate={progress >= threshold ? { opacity: 1, x: 0 } : {}}
                    className="flex items-center gap-3 text-sm"
                  >
                    <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                    <span className="text-foreground">{label}</span>
                    <span className="ml-auto text-muted-foreground text-xs">✓ Done</span>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}

          {/* ─── RESULTS STAGE ─── */}
          {stage === "results" && (() => {
            const ATS_SCORE = analysisResult?.ats_score ?? 0
            const resumeName = file?.name ?? "resume.pdf"
            const mentorEmail = "mentor@resumeboost.ai"
            const mentorWhatsApp = "919999999999" // replace with real number
            const mentorMailBody = `Hi,\n\nI'd like to connect regarding my resume review.\n\nResume: ${resumeName}\nATS Score: ${ATS_SCORE}/100${jobRole ? `\nTarget Role: ${jobRole}` : ""}\n\nPlease find my resume attached.\n\nThank you!`
            const mentorWAMsg = `Hi! I would like to connect for a resume review.\n\nResume: ${resumeName}\nATS Score: ${ATS_SCORE}/100${jobRole ? `\nTarget Role: ${jobRole}` : ""}\n\nCould you please help me improve my resume?`

            return (
            <motion.div
              key="results"
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
            >
              {/* Page Header */}
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-6 pb-6 border-b border-border gap-4">
                <div>
                  <h1 className="text-3xl font-bold tracking-tight mb-1">ATS Analysis Results</h1>
                  <p className="text-muted-foreground flex items-center gap-2 text-sm">
                    <FileText className="w-4 h-4" />
                    {resumeName}
                    {jobRole && <> · <span className="text-teal-500">{jobRole}</span></>}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 md:gap-3">
                  <Button variant="outline" size="sm" className="gap-2 hidden sm:flex" onClick={reset}>
                    <Upload className="w-4 h-4" /> New Scan
                  </Button>
                  <Button 
                    size="sm" 
                    className="gap-2 bg-red-600 hover:bg-red-700 text-white border-none shadow-lg shadow-red-500/20" 
                    onClick={() => window.location.href = "/improve/for_all"}
                  >
                    <Sparkles className="w-4 h-4" /> Enhance Resume
                  </Button>
                  {/* <Button variant="outline" size="sm" className="gap-2 bg-green-500/10 hover:bg-green-500/20 text-green-600 dark:text-green-400 border-green-500/20" onClick={() => handleShare("whatsapp")}>
                    <MessageCircle className="w-4 h-4" /> Share to WhatsApp
                  </Button> */}
                  {/* <Button variant="outline" size="sm" className="gap-2 bg-blue-500/10 hover:bg-blue-500/20 text-blue-600 dark:text-blue-400 border-blue-500/20" onClick={() => handleShare("email")}>
                    <Mail className="w-4 h-4" /> Share via Mail
                  </Button> */}
                  {/* <Button variant="gradient" size="sm" className="gap-2">
                    <Download className="w-4 h-4" /> Download PDF
                  </Button> */}
                </div>
              </div>

              {/* ── LOW SCORE ALERT ── */}
              {ATS_SCORE < 75 && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mb-6 rounded-2xl border border-red-500/40 bg-red-500/10 dark:bg-red-950/40 p-4 flex items-start gap-4"
                >
                  <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-red-500/15 shrink-0">
                    <AlertTriangle className="w-5 h-5 text-red-500" />
                  </div>
                  <div className="flex-1">
                    <p className="font-semibold text-red-600 dark:text-red-400 mb-1">⚠ Low ATS Score — Your Resume May Be Auto-Rejected</p>
                    <p className="text-sm text-red-600/80 dark:text-red-400/80 leading-relaxed">
                      Your resume scored <strong>{ATS_SCORE}/100</strong>, which is below the 75-point threshold most ATS systems use. It may be filtered out before a recruiter ever reads it.
                      Address the issues listed below and consider connecting with a mentor for personalized help.
                    </p>
                  </div>
                </motion.div>
              )}

              {/* ── 2-COLUMN LAYOUT (matches reference image) ── */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-10 items-start">

                {/* LEFT: Score Gauge + Score Breakdown */}
                <div className="flex flex-col gap-6 lg:col-span-4">
                  {/* Score card */}
                  <div className="glass-card rounded-3xl border border-border flex flex-col items-center justify-start p-6 shadow-sm relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-teal-500/5 rounded-full blur-3xl" />
                    <div className="mt-8">
                      <ScoreGauge score={ATS_SCORE} />
                    </div>
                    <div className="mt-10 text-center px-2 mb-4">
                      <h4 className="text-xl font-bold mb-2">
                        {ATS_SCORE >= 90 ? "Excellent!" : ATS_SCORE >= 75 ? "Almost There!" : "Needs Work"}
                      </h4>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {ATS_SCORE >= 90
                          ? "Your resume is highly optimised. Minor tweaks can push it to a perfect score."
                          : ATS_SCORE >= 75
                          ? "Great potential! Some formatting and keyword adjustments will push you over the line."
                          : "Your resume needs significant improvements to pass most ATS filters. See the issues on the right."}
                      </p>
                    </div>
                  </div>

                  {/* Score Breakdown */}
                  <ScoreBreakdown items={analysisResult?.breakdown} />
                </div>

                {/* RIGHT: Issues Detected + Original Resume PDF — unified card */}
                <div className="glass-card rounded-3xl border border-border/80 shadow-[0_4px_24px_rgba(0,0,0,0.08)] dark:shadow-[0_4px_24px_rgba(0,0,0,0.3)] overflow-hidden lg:col-span-8 flex flex-col">

                  {/* ── Issues Detected sub-section ── */}
                  <div className="p-4 pb-0">
                    <IssuesDetected items={analysisResult?.issues} />
                  </div>

                  {/* Divider */}
                  <div className="flex items-center gap-3 px-5 py-4 mt-2">
                    <div className="flex-1 h-px bg-border" />
                    <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground px-2 py-1 rounded-full bg-muted/60 border border-border">
                      <FileText className="w-3 h-3" /> Original Resume
                    </span>
                    <div className="flex-1 h-px bg-border" />
                  </div>

                  {/* ── PDF Viewer sub-section ── */}
                  <div className="px-4 pb-4 flex flex-col flex-1">
                    <div className="flex-1 w-full bg-muted/30 overflow-hidden border border-border relative transition-all block min-h-[700px] rounded-xl">
                      {fileUrl ? (
                        <iframe src={`${fileUrl}#view=FitH&toolbar=0`} className="absolute inset-0 w-full h-full border-none bg-white" title="Resume PDF" />
                      ) : (
                        <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground gap-2">
                          <FileText className="w-8 h-8 opacity-40" />
                          <span className="text-sm opacity-60">No preview available</span>
                        </div>
                      )}
                    </div>
                  </div>

                </div>
              </div>

              {/* ── CONNECT WITH MENTOR ── */}
              <motion.div
                id="mentor-section"
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="mb-10 scroll-mt-20"
              >
                <div className="glass-card rounded-3xl border border-border overflow-hidden shadow-sm">
                  {/* Header gradient strip */}
                  <div className="bg-gradient-to-r from-blue-600 via-teal-500 to-cyan-500 px-6 py-4 flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-white/20 flex items-center justify-center">
                      <UserCheck className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <p className="font-bold text-white text-base">Connect with a Resume Mentor</p>
                      <p className="text-white/70 text-xs">Get personalized 1-on-1 feedback from a certified career coach</p>
                    </div>
                    <div className="ml-auto hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/15 border border-white/20">
                      <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                      <span className="text-white/90 text-xs font-medium">Mentors Online</span>
                    </div>
                  </div>

                  <div className="p-6">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
                      {/* Resume info pill */}
                      <div className="col-span-full flex items-center gap-3 rounded-xl border border-border bg-muted/40 px-4 py-3">
                        <FileText className="w-4 h-4 text-teal-500 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-xs text-muted-foreground">Resume to share</p>
                          <p className="text-sm font-medium text-foreground truncate">{resumeName}</p>
                        </div>
                        <span className={`ml-auto shrink-0 text-xs font-semibold px-2 py-0.5 rounded-full ${
                          ATS_SCORE >= 75 ? "bg-teal-500/10 text-teal-600 dark:text-teal-400" : "bg-red-500/10 text-red-600 dark:text-red-400"
                        }`}>
                          Score: {ATS_SCORE}/100
                        </span>
                      </div>

                      {/* WhatsApp mentor button */}
                      <button
                        type="button"
                        onClick={() => window.open("https://wa.me/918989973328?text=Hello%2C%0A%0AI%20would%20like%20to%20connect%20with%20a%20mentor%20for%20a%201%3A1%20conversation.%0A%0APlease%20guide%20me%20with%20the%20next%20steps.", "_blank")}
                        className="flex items-center gap-4 rounded-2xl border border-green-500/30 bg-green-500/5 hover:bg-green-500/12 dark:hover:bg-green-500/15 px-5 py-4 text-left transition-all group"
                      >
                        <div className="w-10 h-10 rounded-xl bg-green-500/15 flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
                          <MessageCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-foreground group-hover:text-green-600 dark:group-hover:text-green-400 transition-colors">Chat on WhatsApp</p>
                          <p className="text-xs text-muted-foreground mt-0.5">Send your resume details instantly</p>
                        </div>
                        <ExternalLink className="w-3.5 h-3.5 text-muted-foreground/60 ml-auto shrink-0" />
                      </button>

                      {/* Email mentor button */}
                      <button
                        type="button"
                        onClick={() => window.open(
                          "https://mail.google.com/mail/?view=cm&fs=1&to=connect@rozgar24x7.com&su=Mentor%20Connection%20Request&body=Hello%2C%0A%0AI%20want%20to%20connect%20with%20a%20mentor%20for%20a%201%3A1%20conversation.%0A%0APlease%20guide%20me%20with%20the%20next%20steps.%0A%0ARegards",
                          "_blank"
                        )}
                        className="flex items-center gap-4 rounded-2xl border border-blue-500/30 bg-blue-500/5 hover:bg-blue-500/12 dark:hover:bg-blue-500/15 px-5 py-4 text-left transition-all group"
                      >
                        <div className="w-10 h-10 rounded-xl bg-blue-500/15 flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
                          <Mail className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-foreground group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">Email a Mentor</p>
                          <p className="text-xs text-muted-foreground mt-0.5">Pre-filled with your resume & score</p>
                        </div>
                        <ExternalLink className="w-3.5 h-3.5 text-muted-foreground/60 ml-auto shrink-0" />
                      </button>
                    </div>

                    <p className="text-center text-xs text-muted-foreground">
                      📎 Tip: After opening the compose window, <strong>attach your resume file</strong> to the message before sending.
                    </p>
                  </div>
                </div>
              </motion.div>

              {/* ── PRICING SECTION ── */}
              <motion.div
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="mb-10"
              >
                {/* Section header */}
                <div className="text-center mb-8">
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-50 text-teal-600 text-sm font-semibold mb-4">
                    <Sparkles className="w-4 h-4" /> Simple, transparent pricing
                  </div>
                  <h2 className="text-4xl md:text-5xl font-black mb-4">Invest in your career.</h2>
                  <p className="text-gray-500">Join professionals who landed their dream jobs using ROZGAR 24X7.</p>
                </div>

                {/* Pricing Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-5xl mx-auto">
                  {PRICING_PLANS.map((plan, i) => (
                    <motion.div
                      key={plan.name}
                      initial={{ opacity: 0, y: 40 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.1 }}
                      className={`relative rounded-2xl bg-white border shadow-md hover:shadow-xl transition flex flex-col ${
                        plan.highlight ? "border-blue-500 scale-[1.02]" : "border-gray-200"
                      }`}
                    >
                      {plan.highlight && (
                        <div className="absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2 z-10">
                          <div className="bg-gradient-to-r from-blue-600 to-teal-500 text-white text-xs font-bold px-4 py-1.5 rounded-full shadow-lg">
                            MOST POPULAR
                          </div>
                        </div>
                      )}

                      <div className="flex flex-col h-full p-6">
                        <div>
                          <h2 className="text-lg font-semibold">{plan.name}</h2>
                          <p className="text-gray-500 text-xs mb-4">{plan.description}</p>

                          <div className="mb-5">
                            <div className="inline-block bg-green-100 text-green-700 text-xs font-semibold px-2 py-1 rounded-md mb-2">
                              SAVE {Math.round(((plan.originalPrice - plan.price) / plan.originalPrice) * 100)}%
                            </div>

                            <div className="flex items-center gap-3">
                              <span className="text-4xl md:text-5xl font-extrabold text-black">
                                ₹{plan.price}
                              </span>
                              <span className="text-lg text-red-500 line-through">
                                ₹{plan.originalPrice}
                              </span>
                            </div>

                            <p className="text-xs text-gray-500 mt-1">Limited time offer</p>
                          </div>
                        </div>

                        <div className="flex-1 mb-6">
                          <ul className="space-y-3">
                            {plan.features.map((feature, index) => {
                              const Icon = PRICING_ICON_MAP[feature] || Sparkles

                              return (
                                <li key={index} className="flex items-center gap-3 text-sm text-gray-700">
                                  <div className="p-1.5 rounded-md bg-blue-50 text-blue-600 flex-shrink-0">
                                    <Icon className="w-4 h-4" />
                                  </div>
                                  <span>{feature}</span>
                                </li>
                              )
                            })}
                          </ul>
                        </div>

                        <div>
                          <a
                            href={plan.whatsappLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block text-center bg-gradient-to-r from-blue-600 to-teal-500 text-white py-3 rounded-xl font-semibold shadow-lg hover:scale-[1.02] transition"
                          >
                            Buy Now
                          </a>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </motion.div>

            </motion.div>
            )
          })()}

        </AnimatePresence>
      </div>

      {/* ── LOW SCORE POPUP ── */}
      <AnimatePresence>
        {stage === "results" && showMentorPopup && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 20 }}
              className="relative w-full max-w-md bg-zinc-900/40 backdrop-blur-xl border border-white/10 rounded-3xl p-6 shadow-2xl overflow-hidden glass-card"
            >
              <div className="absolute top-0 right-0 w-32 h-32 bg-red-500/20 rounded-full blur-3xl pointer-events-none" />
              
              <button 
                onClick={() => setShowMentorPopup(false)}
                className="absolute top-4 right-4 text-white/50 hover:text-white transition-colors"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="flex flex-col items-center text-center mt-2">
                <div className="w-16 h-16 rounded-2xl bg-red-400/20 border border-red-400/30 shadow-[0_0_20px_rgba(248,113,113,0.15)] flex items-center justify-center mb-4">
                  <AlertTriangle className="w-8 h-8 text-red-400" />
                </div>
                <h3 className="text-xl font-bold text-white mb-2">Low ATS Score Detected</h3>
                <p className="text-sm text-white/80 mb-6 leading-relaxed">
                  Your resume scored below the 75-point threshold and may be auto-rejected. Don't worry, our mentors can review and optimize it for you!
                </p>

                <div className="w-full space-y-3">
                  <Button 
                    className="w-full gap-2 bg-gradient-to-r from-red-600 to-red-500 hover:from-red-700 hover:to-red-600 border-none shadow-lg shadow-red-500/25 text-white h-12 rounded-xl text-base font-medium transition-all hover:scale-[1.02] active:scale-[0.98]"
                    onClick={() => {
                      setShowMentorPopup(false);
                      window.location.href = "/improve/for_all";
                    }}
                  >
                    <Sparkles className="w-5 h-5" />
                    Fix Your Resume
                  </Button>

                  <button
                    className="w-full h-11 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-white/80 hover:text-white text-sm font-medium transition-all flex items-center justify-center gap-2"
                    onClick={() => {
                      setShowMentorPopup(false);
                      document.getElementById('mentor-section')?.scrollIntoView({ behavior: 'smooth' });
                    }}
                  >
                    <UserCheck className="w-4 h-4" />
                    Connect with Mentor
                  </button>
                </div>
                
                <button
                  className="mt-4 text-sm text-white/60 hover:text-white transition-colors"
                  onClick={() => setShowMentorPopup(false)}
                >
                  Review exactly what went wrong
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </main>
  )
}
