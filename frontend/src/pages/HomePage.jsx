import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";

const HomePage = () => {
  const [activeAtsTab, setActiveAtsTab] = React.useState(0);

  return (
    <div
      className="min-h-screen relative overflow-hidden selection:bg-blue-100 dark:selection:bg-blue-900/30"
      style={{ backgroundColor: "var(--color-bg)" }}
    >

      {/* 🔵 SOFT BLUE GLOW BACKGROUND */}
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full blur-[160px] -z-10"
        style={{ backgroundColor: "rgba(37,99,235,0.06)" }}
      />

      {/* ================= HERO SECTION ================= */}
      <section className="pt-10 md:pt-16 pb-20 px-6 flex flex-col items-center text-center relative z-10 max-w-5xl mx-auto">

        {/* SOCIAL PROOF PILL */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-4 rounded-full px-4 py-2 mb-12 shadow-sm"
          style={{
            backgroundColor: "var(--color-bg-section)",
            border: "1px solid var(--color-border)",
          }}
        >
          <div className="flex -space-x-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                className="w-7 h-7 rounded-full border-2 bg-slate-200 overflow-hidden shadow-sm"
                style={{ borderColor: "var(--color-bg)" }}
              >
                <img src={`https://i.pravatar.cc/100?img=${i * 5}`} alt="User" className="w-full h-full object-cover" />
              </div>
            ))}
          </div>

          <div className="h-4 w-[1px] hidden sm:block" style={{ backgroundColor: "var(--color-border)" }} />

          <div className="flex items-center gap-2">
            <div className="flex" style={{ color: "var(--color-accent)" }}>
              {[...Array(5)].map((_, i) => (
                <svg key={i} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5">
                  <path fillRule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clipRule="evenodd" />
                </svg>
              ))}
            </div>
            <p className="text-sm font-medium" style={{ color: "var(--color-body)" }}>Used by 10,000+ users</p>
          </div>
        </motion.div>

        {/* MAIN HEADLINE */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-6xl md:text-8xl font-extrabold leading-[1.1] mb-8 tracking-tight"
          style={{ color: "var(--color-heading)" }}
        >
          Get hired faster with a <br className="hidden md:block" />
          <span style={{ color: "var(--color-accent)" }}>resume that works.</span>
        </motion.h1>

        {/* SUBTITLE */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-xl md:text-[22px] max-w-2xl font-medium mb-10 leading-relaxed"
          style={{ color: "var(--color-body)" }}
        >
          Create, edit and download professional resumes with<br className="hidden md:block" />{" "}
          <span className="font-bold" style={{ color: "var(--color-accent)" }}>AI-powered assistance.</span>
        </motion.p>

        {/* CTA BUTTON */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="flex flex-col sm:flex-row items-center gap-4 mb-24"
        >
          <Link
            to="/analyze"
            className="group px-8 py-4 rounded-full text-white font-bold text-lg flex items-center gap-2 transition-all hover:-translate-y-0.5"
            style={{
              backgroundColor: "var(--color-cta-bg)",
              boxShadow: "0 20px 50px -10px rgba(37,99,235,0.35)",
            }}
            onMouseEnter={e => e.currentTarget.style.backgroundColor = "var(--color-cta-hover)"}
            onMouseLeave={e => e.currentTarget.style.backgroundColor = "var(--color-cta-bg)"}
          >
            Get started
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5 transition-transform duration-300 group-hover:translate-x-1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
            </svg>
          </Link>
        </motion.div>

        {/* LOGO LOOP */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="w-full mt-12"
        >
          <p className="text-sm font-medium mb-10 text-center" style={{ color: "var(--color-muted)" }}>
            Trusted by leading brands, including
          </p>
          <div className="relative flex overflow-hidden py-4">
            <motion.div
              className="flex shrink-0 gap-16 md:gap-32 w-max items-center px-8"
              animate={{ x: ["0%", "-50%"] }}
              transition={{ ease: "linear", duration: 20, repeat: Infinity }}
            >
              {[1, 2].map((loop) => (
                <React.Fragment key={loop}>
                  <img src="https://upload.wikimedia.org/wikipedia/commons/2/2f/Google_2015_logo.svg" className="h-6 md:h-8 opacity-40 grayscale brightness-0 dark:invert" alt="Google" />
                  <img src="https://upload.wikimedia.org/wikipedia/commons/7/7b/Meta_Platforms_Inc._logo.svg" className="h-6 md:h-8 opacity-40 grayscale brightness-0 dark:invert" alt="Meta" />
                  <img src="https://upload.wikimedia.org/wikipedia/commons/a/a9/Amazon_logo.svg" className="h-6 md:h-8 opacity-40 grayscale brightness-0 dark:invert pt-2" alt="Amazon" />
                  <img src="https://upload.wikimedia.org/wikipedia/commons/9/96/Microsoft_logo_%282012%29.svg" className="h-6 md:h-8 opacity-40 grayscale brightness-0 dark:invert" alt="Microsoft" />
                  <img src="https://upload.wikimedia.org/wikipedia/commons/0/08/Netflix_2015_logo.svg" className="h-6 md:h-8 opacity-40 grayscale brightness-0 dark:invert" alt="Netflix" />
                  <img src="https://upload.wikimedia.org/wikipedia/commons/2/20/Adidas_Logo.svg" className="h-8 md:h-10 opacity-40 grayscale brightness-0 dark:invert" alt="Adidas" />
                  <img src="https://upload.wikimedia.org/wikipedia/commons/f/fa/Apple_logo_black.svg" className="h-6 md:h-8 opacity-40 grayscale brightness-0 dark:invert" alt="Apple" />
                </React.Fragment>
              ))}
            </motion.div>
            <div className="absolute inset-y-0 left-0 w-32 z-10 pointer-events-none" style={{ background: "linear-gradient(to right, var(--color-bg), transparent)" }} />
            <div className="absolute inset-y-0 right-0 w-32 z-10 pointer-events-none" style={{ background: "linear-gradient(to left, var(--color-bg), transparent)" }} />
          </div>
        </motion.div>

      </section>

      {/* ================= FEATURES SECTIONS ================= */}
      <div id="features-section">

        {/* Section: ATS Scanner + Keyword */}
        <section className="py-32" style={{ backgroundColor: "var(--color-bg)" }}>
          <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 md:grid-cols-2 gap-16 md:gap-24 items-center mb-40 overflow-hidden">
            <motion.div
              initial={{ opacity: 0, x: -50 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.8, ease: "easeOut" }}
            >
              <h2 className="text-4xl font-extrabold mb-6" style={{ color: "var(--color-heading)" }}>
                ATS Scanner: Know your score before you apply.
              </h2>
              <p className="text-lg font-medium mb-8" style={{ color: "var(--color-muted)" }}>
                Our engine replicates the logic used by major ATS providers like Workday and Lever. Get a comprehensive score across formatting, keywords, and structural integrity.
              </p>
              <ul className="space-y-4">
                {["Instant PDF/Word Parsing", "Visual Heatmap of Missing Skills", "Structural Conflict Detection"].map(item => (
                  <li key={item} className="flex items-center gap-3 font-semibold" style={{ color: "var(--color-body)" }}>
                    <span style={{ color: "var(--color-accent)" }} className="text-xl">✓</span> {item}
                  </li>
                ))}
              </ul>
            </motion.div>

            {/* Score Ring Card */}
            <motion.div 
              initial={{ opacity: 0, x: 50 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              className="relative p-12 rounded-[2rem] overflow-hidden" 
              style={{ backgroundColor: "var(--color-bg-section)", border: "1px solid var(--color-border)" }}
            >
              <div className="flex flex-col items-center justify-center w-64 h-64 rounded-full mx-auto shadow-xl relative z-10" style={{ backgroundColor: "var(--color-bg)" }}>
                <svg className="absolute w-full h-full transform -rotate-90">
                  <circle cx="128" cy="128" fill="transparent" r="100" stroke="currentColor" className="text-slate-200 dark:text-slate-700" strokeWidth="12" />
                  <circle cx="128" cy="128" fill="transparent" r="100" stroke="var(--color-accent)" strokeDasharray="628" strokeDashoffset="81" strokeLinecap="round" strokeWidth="12" />
                </svg>
                <div className="absolute flex flex-col items-center">
                  <span className="text-5xl font-extrabold tracking-tighter" style={{ color: "var(--color-heading)" }}>
                    87<span className="text-2xl font-light" style={{ color: "var(--color-muted)" }}>/100</span>
                  </span>
                  <span className="text-[10px] font-bold uppercase tracking-widest mt-1" style={{ color: "var(--color-muted)" }}>Excellent Score</span>
                </div>
              </div>
              <div className="mt-12 flex flex-col gap-3 relative z-10">
                <div className="p-4 rounded-xl shadow-sm flex justify-between items-center" style={{ backgroundColor: "var(--color-bg)", borderLeft: "4px solid var(--color-accent)" }}>
                  <span className="text-sm font-semibold" style={{ color: "var(--color-body)" }}>Keywords Optimized</span>
                  <span className="font-bold" style={{ color: "var(--color-accent)" }}>100%</span>
                </div>
                <div className="p-4 rounded-xl shadow-sm flex justify-between items-center" style={{ backgroundColor: "var(--color-bg)", borderLeft: "4px solid var(--color-secondary)" }}>
                  <span className="text-sm font-semibold" style={{ color: "var(--color-body)" }}>Formatting Integrity</span>
                  <span className="font-bold" style={{ color: "var(--color-secondary)" }}>72%</span>
                </div>
              </div>
            </motion.div>
          </div>

          {/* Section: Built for the AI Era */}
          <motion.div 
            initial={{ opacity: 0, y: 50 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="max-w-6xl mx-auto px-6 mb-40"
          >
            <div className="text-center mb-16">
              <h2 className="text-4xl md:text-5xl font-extrabold mb-6" style={{ color: "var(--color-heading)" }}>Built for the AI Era</h2>
              <p className="text-lg font-medium max-w-2xl mx-auto" style={{ color: "var(--color-muted)" }}>
                Stop guessing what recruiters want. Our suite of professional tools builds the perfect resume optimized for humans and machines.
              </p>
            </div>
            
            <div className="rounded-[2.5rem] shadow-sm flex flex-col lg:flex-row overflow-hidden" style={{ backgroundColor: "var(--color-bg)", border: "1px solid var(--color-border)" }}>
              
              {/* LEFT COLUMN: Accordion */}
              <div className="lg:w-1/2 p-6 md:p-12">
                <h3 className="text-2xl font-bold mb-8" style={{ color: "var(--color-heading)" }}>How the ATS Checker Works</h3>
                <div className="space-y-2">
                  {[
                    {
                      title: "AI-Powered ATS Scan",
                      icon: <svg className="w-5 h-5 text-teal-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
                      desc: "Upload your resume and get an instant compatibility score against industry-leading ATS systems. We check parse rate, structure, and readability.",
                      bullets: ["Instant 0-100 compatibility score", "Format and structure verification", "Identifies auto-rejection risks"]
                    },
                    {
                      title: "Keyword Match Engine",
                      icon: <svg className="w-5 h-5" style={{ color: "var(--color-muted)" }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>,
                      desc: "Our engine maps your resume against the job description to find missing keywords.",
                      bullets: ["Finds missing soft and hard skills", "Context-aware matching", "Keyword density tracking"]
                    },
                    {
                      title: "Actionable Insights",
                      icon: <svg className="w-5 h-5" style={{ color: "var(--color-muted)" }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>,
                      desc: "Get line-by-line feedback on how to improve your bullet points.",
                      bullets: ["Impact-driven suggestions", "Tone and active voice checks", "Grammar and punctuation fixes"]
                    },
                    {
                      title: "Expert Mentor Review",
                      icon: <svg className="w-5 h-5" style={{ color: "var(--color-muted)" }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>,
                      desc: "A human expert will review your resume and provide a personalized video teardown.",
                      bullets: ["1-on-1 strategy sessions", "Industry-specific advice", "Final polish and formatting"]
                    }
                  ].map((tab, idx) => (
                    <div 
                      key={idx}
                      onClick={() => setActiveAtsTab(idx)}
                      className={`rounded-2xl p-4 md:p-5 cursor-pointer transition-all duration-300 border ${activeAtsTab === idx ? "shadow-sm border-transparent" : "bg-transparent border-transparent"}`}
                      style={activeAtsTab === idx ? { backgroundColor: "var(--color-bg)", border: "1px solid var(--color-border)" } : {}}
                      onMouseEnter={(e) => { if(activeAtsTab !== idx) e.currentTarget.style.backgroundColor = "var(--color-bg-section)" }}
                      onMouseLeave={(e) => { if(activeAtsTab !== idx) e.currentTarget.style.backgroundColor = "transparent" }}
                    >
                      <div className="flex gap-4">
                        <div className={`mt-1 w-10 h-10 rounded-full flex items-center justify-center shrink-0`} style={{ backgroundColor: activeAtsTab === idx ? "rgba(13,148,136,0.1)" : "var(--color-bg-section)" }}>
                          {tab.icon}
                        </div>
                        <div className="flex-1 relative">
                          {activeAtsTab === idx && (
                            <div className="absolute -left-[54px] md:-left-[58px] top-2 bottom-0 w-1 rounded-full" style={{ backgroundColor: "var(--color-secondary)" }} />
                          )}
                          <h4 className="text-lg font-bold mt-2 transition-colors" style={{ color: activeAtsTab === idx ? "var(--color-heading)" : "var(--color-muted)" }}>{tab.title}</h4>
                          {activeAtsTab === idx && (
                            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="mt-3 overflow-hidden">
                              <p className="text-sm mb-4 leading-relaxed" style={{ color: "var(--color-muted)" }}>{tab.desc}</p>
                              <ul className="space-y-3">
                                {tab.bullets.map((b, i) => (
                                  <li key={i} className="flex items-center gap-3 text-sm font-medium" style={{ color: "var(--color-body)" }}>
                                    <div className="w-5 h-5 rounded-full flex items-center justify-center shrink-0" style={{ border: "1px solid var(--color-secondary)", color: "var(--color-secondary)" }}>
                                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                                    </div>
                                    {b}
                                  </li>
                                ))}
                              </ul>
                            </motion.div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* RIGHT COLUMN: Visualizer */}
              <div className="lg:w-1/2 p-6 md:p-12 relative flex items-center justify-center min-h-[400px] bg-gradient-to-br from-blue-50/50 to-teal-50/50 dark:from-slate-800/50 dark:to-teal-900/20" style={{ borderLeft: "1px solid var(--color-border)" }}>
                
                {/* Visual content based on active tab */}
                <motion.div
                  key={activeAtsTab}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.4 }}
                  className="w-full max-w-md"
                >
                  {activeAtsTab === 0 && (
                    <div className="bg-white dark:bg-slate-800 rounded-3xl p-8 shadow-xl relative border border-slate-100 dark:border-slate-700">
                      <div className="absolute -top-3 -right-3 text-white text-[13px] font-bold px-4 py-1.5 rounded-[20px] shadow-md flex items-center gap-1.5" style={{ backgroundColor: "#00C49F" }}>
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                        Live Analysis
                      </div>
                      
                      <div className="flex flex-col items-center mb-6 mt-6">
                        <div className="relative w-56 h-32 mb-2 flex justify-center">
                          <svg viewBox="0 0 200 100" className="w-full h-full overflow-visible">
                            {/* Background Track */}
                            <path 
                              d="M 20 100 A 80 80 0 0 1 180 100" 
                              fill="none" 
                              stroke="#f1f5f9" 
                              strokeWidth="16" 
                              strokeLinecap="butt"
                            />
                            {/* Foreground Track (Animated) */}
                            <motion.path 
                              d="M 20 100 A 80 80 0 0 1 180 100" 
                              fill="none" 
                              stroke="#00C49F" 
                              strokeWidth="16" 
                              strokeLinecap="butt"
                              strokeDasharray="251.327"
                              initial={{ strokeDashoffset: 251.327 }}
                              animate={{ strokeDashoffset: 251.327 * (1 - 0.92) }}
                              transition={{ duration: 1.5, ease: "easeOut", delay: 0.2 }}
                            />
                          </svg>
                          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 flex flex-col items-center pb-0">
                            <span className="text-6xl font-extrabold tracking-tight" style={{ color: "#00C49F" }}>92</span>
                            <span className="text-[11px] font-bold tracking-widest mt-1" style={{ color: "#94a3b8" }}>SCORE</span>
                          </div>
                        </div>
                        <h4 className="text-[22px] font-bold text-slate-900 dark:text-white mt-4">Excellent!</h4>
                        <p className="text-[15px] font-medium text-center text-slate-500 dark:text-slate-400 mt-2 max-w-[280px]">Your resume is highly optimized. Minor tweaks can push it to a perfect score.</p>
                      </div>

                      <div className="bg-[#f8fafc] dark:bg-slate-900/50 rounded-[1.5rem] p-6 border border-slate-100 dark:border-slate-700 mt-8">
                        <div className="flex justify-between items-end mb-3">
                          <span className="text-[15px] font-extrabold text-slate-700 dark:text-slate-300">ATS Parse Rate</span>
                          <span className="text-[15px] font-bold" style={{ color: "#00C49F" }}>100%</span>
                        </div>
                        <div className="h-2.5 w-full bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden mb-4">
                          <motion.div 
                            className="h-full rounded-full" 
                            style={{ backgroundColor: "#00C49F" }}
                            initial={{ width: 0 }}
                            animate={{ width: "100%" }}
                            transition={{ duration: 1.5, ease: "easeOut", delay: 0.4 }}
                          />
                        </div>
                        <p className="text-[12px] font-medium text-slate-500 dark:text-slate-400">Successfully parsed by industry-leading ATS.</p>
                      </div>
                    </div>
                  )}

                  {activeAtsTab === 1 && (
                    <div className="bg-white dark:bg-slate-800 rounded-3xl p-6 shadow-xl relative border border-slate-100 dark:border-slate-700">
                      <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100 dark:border-slate-700">
                         <span className="text-sm font-bold text-slate-800 dark:text-white">Job Description Matching</span>
                         <span className="bg-blue-100 text-blue-600 text-xs font-bold px-2 py-1 rounded">Scanning...</span>
                      </div>
                      <div className="space-y-6">
                        <div>
                          <span className="text-[11px] uppercase font-bold text-slate-400 block mb-3">Hard Skills Found</span>
                          <div className="flex flex-wrap gap-2">
                            {["React.js", "TypeScript", "Node.js", "GraphQL"].map(skill => (
                              <span key={skill} className="bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300 border border-teal-100 dark:border-teal-800 px-2.5 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5">
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                                {skill}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div>
                          <span className="text-[11px] uppercase font-bold text-slate-400 block mb-3">Missing Skills</span>
                          <div className="flex flex-wrap gap-2">
                            {["AWS", "Docker", "System Design"].map(skill => (
                              <span key={skill} className="bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400 border border-red-100 dark:border-red-800 px-2.5 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5">
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                                {skill}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeAtsTab === 2 && (
                    <div className="bg-white dark:bg-slate-800 rounded-3xl p-6 shadow-xl relative border border-slate-100 dark:border-slate-700">
                      <div className="flex items-center gap-3 mb-6">
                        <div className="w-10 h-10 rounded-full bg-amber-100 text-amber-600 flex items-center justify-center">
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                        </div>
                        <div>
                          <h4 className="text-sm font-bold text-slate-800 dark:text-white">Weak Action Verb Detected</h4>
                          <p className="text-[11px] font-medium text-slate-500">Experience Section</p>
                        </div>
                      </div>
                      <div className="bg-red-50 dark:bg-red-900/10 p-4 rounded-xl border border-red-100 dark:border-red-900/30 mb-4 relative line-through text-slate-500 text-sm leading-relaxed">
                        "Helped with managing the engineering team and doing code reviews."
                      </div>
                      <div className="flex justify-center mb-4">
                        <svg className="w-6 h-6 text-teal-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" /></svg>
                      </div>
                      <div className="bg-teal-50 dark:bg-teal-900/10 p-4 rounded-xl border border-teal-100 dark:border-teal-900/30 text-slate-800 dark:text-slate-200 text-sm font-medium leading-relaxed">
                        "Directed a cross-functional engineering team, establishing rigorous code review protocols that reduced bug rates by 25%."
                      </div>
                    </div>
                  )}

                  {activeAtsTab === 3 && (
                    <div className="bg-white dark:bg-slate-800 rounded-3xl overflow-hidden shadow-xl relative border border-slate-100 dark:border-slate-700">
                      <div className="h-32 bg-slate-200 dark:bg-slate-700 relative">
                        <img src="https://images.unsplash.com/photo-1552664730-d307ca884978?auto=format&fit=crop&q=80&w=400&h=200" alt="Mentor" className="w-full h-full object-cover opacity-80" />
                        <div className="absolute inset-0 flex items-center justify-center">
                           <div className="w-14 h-14 bg-white/90 rounded-full flex items-center justify-center shadow-lg backdrop-blur-sm cursor-pointer hover:scale-110 transition-transform">
                             <svg className="w-6 h-6 text-blue-600 ml-1" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
                           </div>
                        </div>
                      </div>
                      <div className="p-8 pt-10 relative text-center">
                        <div className="w-20 h-20 rounded-full border-4 border-white dark:border-slate-800 overflow-hidden absolute -top-10 left-1/2 -translate-x-1/2 shadow-sm">
                          <img src="https://i.pravatar.cc/150?img=68" alt="Sarah" className="w-full h-full object-cover" />
                        </div>
                        <h4 className="text-lg font-bold text-slate-800 dark:text-white mb-1">Sarah Jenkins</h4>
                        <p className="text-xs font-bold text-teal-600 uppercase tracking-widest mb-4">Senior Recruiter @ TechCorp</p>
                        <p className="text-sm text-slate-500 italic font-medium leading-relaxed">"I'll walk you through exactly what hiring managers in your industry are looking for, line by line."</p>
                      </div>
                    </div>
                  )}

                </motion.div>
              </div>

            </div>
          </motion.div>

          {/* Keyword Injection Engine */}
          <div className="py-32 rounded-[3rem] mx-4 md:mx-10" style={{ backgroundColor: "var(--color-bg-section)" }}>
            <div className="max-w-6xl mx-auto px-6 grid grid-cols-1 md:grid-cols-2 gap-16 md:gap-24 items-center overflow-hidden">
              <motion.div 
                initial={{ opacity: 0, x: -50 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-50px" }}
                transition={{ duration: 0.8, ease: "easeOut" }}
                className="order-2 md:order-1 p-8 rounded-2xl shadow-xl" 
                style={{ backgroundColor: "var(--color-bg)", border: "1px solid var(--color-border)" }}
              >
                <div className="flex items-center gap-4 mb-8 pb-4" style={{ borderBottom: "1px solid var(--color-border)" }}>
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <div className="w-3 h-3 rounded-full bg-amber-400" />
                  <div className="w-3 h-3 rounded-full bg-green-400" />
                  <span className="text-xs font-mono ml-auto" style={{ color: "var(--color-muted)" }}>Keyword_Analysis.json</span>
                </div>
                <div className="grid grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <h4 className="text-[10px] uppercase font-bold tracking-widest" style={{ color: "var(--color-muted)" }}>Required Skills</h4>
                    {["React.js", "Product Strategy", "Editorial Design"].map(s => (
                      <div key={s} className="p-3 rounded-lg text-xs font-mono" style={{ backgroundColor: "var(--color-bg-section)", border: "1px solid var(--color-border)", color: "var(--color-body)" }}>{s}</div>
                    ))}
                  </div>
                  <div className="space-y-4">
                    <h4 className="text-[10px] uppercase font-bold tracking-widest" style={{ color: "var(--color-muted)" }}>Matches Found</h4>
                    <div className="p-3 rounded-lg text-xs font-mono flex items-center gap-2" style={{ backgroundColor: "rgba(37,99,235,0.07)", color: "var(--color-accent)" }}>✓ React.js</div>
                    <div className="p-3 rounded-lg text-xs font-mono flex items-center gap-2" style={{ backgroundColor: "rgba(37,99,235,0.07)", color: "var(--color-accent)" }}>✓ Product Strategy</div>
                    <div className="p-3 rounded-lg text-xs font-mono flex items-center gap-2" style={{ backgroundColor: "rgba(239,68,68,0.07)", color: "#ef4444" }}>✕ Editorial Design</div>
                  </div>
                </div>
              </motion.div>
              <motion.div 
                initial={{ opacity: 0, x: 50 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-50px" }}
                transition={{ duration: 0.8, ease: "easeOut" }}
                className="order-1 md:order-2"
              >
                <h2 className="text-4xl font-extrabold mb-6" style={{ color: "var(--color-heading)" }}>Precision Keyword Injection Engine.</h2>
                <p className="text-lg font-medium" style={{ color: "var(--color-muted)" }}>
                  Stop guessing which words matter. Our AI parses job descriptions in real-time to identify the core competencies companies are filtering for, then suggests the perfect placement within your profile.
                </p>
              </motion.div>
            </div>
          </div>

          {/* AI Rewriter */}
          <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 md:grid-cols-2 gap-16 md:gap-24 items-center pt-32 overflow-hidden">
            <motion.div 
              initial={{ opacity: 0, x: -50 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              className="pr-12"
            >
              <h2 className="text-4xl md:text-5xl font-extrabold mb-8 tracking-tight" style={{ color: "var(--color-heading)", lineHeight: "1.2" }}>AI Rewriter: Achieve Editorial Excellence.</h2>
              <p className="text-lg font-medium mb-10 leading-relaxed" style={{ color: "var(--color-muted)" }}>
                Turn "Responsible for sales" into "Spearheaded high-frequency sales initiatives, resulting in a 40% YoY revenue growth." Our AI understands impact-driven linguistics.
              </p>
              <div className="flex items-center gap-8">
                <Link to="/analyze" className="px-8 py-3.5 rounded-full font-bold shadow-lg hover:scale-105 transition-transform text-white text-[15px] flex items-center justify-center" style={{ backgroundColor: "#0F172A" }}>
                  Try Rewriter
                </Link>
                <button className="flex items-center gap-1.5 font-bold text-[15px] transition-colors" style={{ color: "var(--color-heading)" }}
                  onMouseEnter={e => e.currentTarget.style.color = "var(--color-accent)"}
                  onMouseLeave={e => e.currentTarget.style.color = "var(--color-heading)"}
                >
                  Watch Demo <span className="font-light text-xl leading-none -mt-0.5">▷</span>
                </button>
              </div>
            </motion.div>
            
            <motion.div 
              initial={{ opacity: 0, x: 50 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              className="p-10 rounded-[2rem] shadow-2xl relative" 
              style={{ backgroundColor: "#0F172A" }}
            >
              <div className="space-y-4">
                <div className="p-6 rounded-xl" style={{ border: "1px solid #1E293B", backgroundColor: "transparent" }}>
                  <span className="text-[10px] uppercase font-extrabold tracking-widest block mb-4" style={{ color: "#64748B" }}>Original Input</span>
                  <p className="text-[15px] leading-relaxed italic font-medium" style={{ color: "#CBD5E1" }}>
                    "I helped the team manage many different projects and kept everything on schedule for the client."
                  </p>
                </div>
                
                <div className="p-6 rounded-xl relative" style={{ border: "1px solid #1E293B", backgroundColor: "transparent" }}>
                  <div className="absolute top-6 bottom-6 left-0 w-1 rounded-r-full" style={{ backgroundColor: "#3B82F6" }} />
                  <span className="text-[10px] uppercase font-extrabold tracking-widest block mb-4" style={{ color: "#3B82F6" }}>AI Editorial Enhancement</span>
                  <p className="text-white text-[15px] leading-relaxed font-bold">
                    "Orchestrated cross-functional project lifecycles, ensuring 100% on-time delivery for high-stake client portfolios while optimizing operational workflows."
                  </p>
                </div>
              </div>
            </motion.div>
          </div>
        </section>

        {/* Section: Stats Strip */}
        <section className="py-24 border-y" style={{ backgroundColor: "var(--color-bg-section)", borderColor: "var(--color-border)" }}>
          <motion.div 
            initial={{ opacity: 0, y: 50 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="max-w-7xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-12 text-center"
          >
            {[
              { value: "50,000+", label: "Active Users" },
              { value: "3.2x",    label: "Interview Lift" },
              { value: "94%",     label: "Success Rate" },
              { value: "< 5 min", label: "Prep Time" },
            ].map(stat => (
              <div key={stat.label} className="space-y-2">
                <h4 className="text-5xl font-extrabold font-display" style={{ color: "var(--color-accent)" }}>{stat.value}</h4>
                <p className="text-xs font-bold uppercase tracking-widest text-slate-400">{stat.label}</p>
              </div>
            ))}
          </motion.div>
        </section>

        {/* Section: Reviews */}
        <section className="py-32 overflow-hidden relative" style={{ backgroundColor: "var(--color-bg-section)" }}>
          <motion.div 
            initial={{ opacity: 0, y: 50 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="max-w-7xl mx-auto px-6 mb-20 text-center"
          >
            <div className="text-center mb-20">
              <h2 className="text-4xl font-extrabold" style={{ color: "var(--color-heading)" }}>Join 50k+ Successful Professionals</h2>
            </div>
            <div className="relative flex overflow-hidden w-full py-4 group">
              <motion.div
                className="flex shrink-0 gap-8 w-max group-hover:[animation-play-state:paused]"
                animate={{ x: ["-50%", "0%"] }}
                transition={{ ease: "linear", duration: 30, repeat: Infinity }}
              >
                {[
                  { name: "Dhanush", date: "24th Jan, 2025", rating: 5, text: "Helped me align my resume with my target roles. The suggestions were practical and easy to implement.", avatar: 28 },
                  { name: "Smita", date: "2nd Dec, 2025", rating: 5, text: "Got detailed insights on what was missing in my resume. The recommendations were exactly what I needed.", avatar: 21 },
                  { name: "Gaurav", date: "7th Nov, 2024", rating: 5, text: "Provided a clear roadmap to improve my resume and increase my chances of getting shortlisted.", avatar: 40 },
                  { name: "Ravindra", date: "4th Feb, 2026", rating: 5, text: "My resume finally matches job requirements clearly. The ATS insights helped me fix gaps I didn’t even notice before.", avatar: 3 },
                  { name: "Vikas", date: "11th Jan, 2026", rating: 5, text: "Gave me a clear understanding of what recruiters actually expect and how to align my resume accordingly.", avatar: 15 },
                  { name: "Akshay", date: "19th Dec, 2024", rating: 5, text: "The step-by-step improvements made my resume more structured and ATS-friendly. Super useful guidance.", avatar: 29 },
                  { name: "Suman", date: "10th Jan, 2026", rating: 5, text: "Clear and actionable feedback. I now know how to improve my resume for better shortlisting chances.", avatar: 16 },
                  { name: "Anonymous", date: "23rd Jun, 2025", rating: 5, text: "Quick and insightful analysis. Helped me optimize my resume for ATS screening.", avatar: 25 },
                  { name: "Sriram", date: "29th Nov, 2025", rating: 5, text: "The resume analysis was detailed and helped me refine important sections for better visibility.", avatar: 32 },
                  { name: "Kalpesh", date: "31st Jan, 2025", rating: 5, text: "Helped me tailor my resume for specific roles and improve keyword matching significantly.", avatar: 37 },
                  { name: "Anandini", date: "9th Dec, 2025", rating: 5, text: "Now I can clearly see the gaps in my resume and how to fix them. Very helpful insights.", avatar: 10 },
                  { name: "Dhanush", date: "24th Jan, 2025", rating: 5, text: "Helped me align my resume with my target roles. The suggestions were practical and easy to implement.", avatar: 28 },
                  { name: "Smita", date: "2nd Dec, 2025", rating: 5, text: "Got detailed insights on what was missing in my resume. The recommendations were exactly what I needed.", avatar: 21 }
                ].map((review, i) => (
                  <div
                    key={i}
                    className="p-8 rounded-2xl shadow-sm hover:shadow-xl transition-all w-[350px] shrink-0"
                    style={{ backgroundColor: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                  >
                    <div className="flex items-center gap-4 mb-6">
                      <div className="w-12 h-12 rounded-[25%] flex items-center justify-center font-bold overflow-hidden" style={{ backgroundColor: "var(--color-bg-section)", color: "var(--color-muted)" }}>
                        {review.avatar ? (
                          <img src={`https://i.pravatar.cc/150?img=${review.avatar}`} alt={review.name} className="w-full h-full object-cover" />
                        ) : (
                          review.name[0]
                        )}
                      </div>
                      <div>
                        <h4 className="font-bold text-sm" style={{ color: "var(--color-heading)" }}>{review.name}</h4>
                        <div className="flex text-amber-400 text-sm">{"★".repeat(review.rating)}</div>
                      </div>
                    </div>
                    <p className="text-sm mb-6 italic leading-relaxed" style={{ color: "var(--color-muted)" }}>"{review.text}"</p>
                    <span className="text-[10px] font-bold px-3 py-1.5 rounded-full uppercase" style={{ backgroundColor: "rgba(37,99,235,0.1)", color: "var(--color-accent)" }}>
                      {review.date}
                    </span>
                  </div>
                ))}
              </motion.div>
            </div>
          </motion.div>
        </section>

        {/* Section: With You At Every Step */}
        <section className="py-32" style={{ backgroundColor: "var(--color-bg)" }}>
          <motion.div 
            initial={{ opacity: 0, y: 50 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="max-w-6xl mx-auto px-6"
          >
            <div className="text-center mb-24">
              <h2 className="text-4xl md:text-5xl font-extrabold mb-6" style={{ color: "var(--color-heading)" }}>With You at Every Step of Your Job Search</h2>
              <p className="text-lg font-medium max-w-3xl mx-auto" style={{ color: "var(--color-muted)" }}>
                From first draft to final offer — ROZGAR 24X7 guides you through the entire process with smart tools, instant feedback, and unwavering support.
              </p>
            </div>

            <div className="space-y-12 relative before:absolute before:inset-0 before:ml-5 md:before:mx-auto md:before:translate-x-0 before:h-full before:w-1 before:bg-gradient-to-b before:from-[var(--color-accent)] before:via-[var(--color-secondary)] before:to-indigo-500">
              {[
                {
                  phase: "Assessment Phase",
                  title: "Discover your true market value",
                  desc: "Before you apply, we analyze your career trajectory, skill set, and past achievements to identify the roles where you naturally stand out.",
                  bullets: ["Identify hidden skill gaps", "Market-driven role recommendations", "Strengths and weaknesses analysis", "Tailored strategy for next steps"]
                },
                {
                  phase: "AI Crafting Phase",
                  title: "Leave the proofreading and phrasing to AI",
                  desc: "Our smart assistant rewrites your bullet points to sound more professional, impactful, and tailored to passing strict ATS algorithms without losing your authentic voice.",
                  bullets: ["Action verb optimization", "Grammar and typo elimination", "Cliché removal and restructuring", "Metric-driven impact phrasing"]
                },
                {
                  phase: "Tailoring Phase",
                  title: "Tailor your resume in a single click",
                  desc: "Paste the specific job description, and our assistant instantly maps the required keywords to your experience, ensuring a high match rate before you even apply.",
                  bullets: ["Missing keyword insertion", "Automated alignment of titles", "Hidden ATS criteria checks", "Real-time score preview"]
                },
                {
                  phase: "Review Phase",
                  title: "Review like a Senior Recruiter",
                  desc: "Get an unbiased, hyper-detailed critique of your resume to spot subtle formatting errors, fluff, or missing sections that might deter hiring managers.",
                  bullets: ["Pinpoint structural and visual flaws", "Identify cliché buzzwords for removal", "Actionable suggestions to improve readability", "Consistency checks across formatting"]
                },
                {
                  phase: "Final Polish Phase",
                  title: "Stand out with 20+ pristine sections",
                  desc: "Visual appeal matters. Present your meticulously crafted story using field-tested designs that guide the recruiter's eye straight to your biggest wins.",
                  bullets: ["Optimized readability layouts", "ATS-friendly parsable designs", "Multiple industry-standard templates", "1-Click download in PDF or DOCX"]
                },
                {
                  phase: "Success Phase",
                  title: "Launch your application with confidence",
                  desc: "Your highest-performing resume is ready. Download it, start applying, and manage your job hunting process while we stay with you mapping your progress to success.",
                  bullets: ["Save multiple versions of your resume", "Fast duplicate-and-edit workflows", "Unlimited multi-format downloads", "Application success tracking metrics"]
                }
              ].map((step, i) => (
                <div key={i} className={`relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group`}>
                  <div className="absolute left-5 md:left-1/2 w-6 h-6 rounded-full border-4 shadow-md transform -translate-x-1/2 z-10 transition-transform duration-300 group-hover:scale-125" style={{ backgroundColor: "var(--color-bg)", borderColor: "var(--color-accent)" }} />
                  
                  <div className="w-full md:w-[45%] pl-12 md:pl-0">
                    <div className="p-8 rounded-3xl shadow-sm hover:shadow-xl transition-all h-full" style={{ backgroundColor: "var(--color-bg-section)", border: "1px solid var(--color-border)" }}>
                      <span className="text-xs font-bold uppercase tracking-widest px-3 py-1.5 rounded-full inline-block mb-4" style={{ backgroundColor: "rgba(37,99,235,0.1)", color: "var(--color-accent)" }}>{step.phase}</span>
                      <h3 className="text-2xl font-bold mb-4" style={{ color: "var(--color-heading)" }}>{step.title}</h3>
                      <p className="font-medium mb-6 leading-relaxed" style={{ color: "var(--color-muted)" }}>{step.desc}</p>
                      <ul className="space-y-3">
                        {step.bullets.map((b, idx) => (
                          <li key={idx} className="flex items-start gap-3 text-sm font-semibold" style={{ color: "var(--color-body)" }}>
                            <svg className="w-4 h-4 mt-0.5 shrink-0" style={{ color: "var(--color-secondary)" }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                            {b}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </section>

        {/* Section: FAQ */}
        <section className="py-32" style={{ backgroundColor: "var(--color-bg)" }}>
          <motion.div 
            initial={{ opacity: 0, y: 50 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="max-w-3xl mx-auto px-6"
          >
            <h2 className="text-4xl font-extrabold text-center mb-16" style={{ color: "var(--color-heading)" }}>Frequently Asked Questions</h2>
            <div className="space-y-4">
              {[
                { q: "How does the AI ATS Scanner work?",  a: "Our scanner uses natural language processing (NLP) to mirror the exact logic used by top-tier Applicant Tracking Systems like Greenhouse, Workday, and Lever." },
                { q: "Can I export my resume to PDF?",     a: "Yes, all templates are optimized for standard PDF exports that maintain 100% readability for both human recruiters and digital scanners." },
                { q: "Is my data secure?",                 a: "We use bank-grade encryption and do not sell your personal data to third-party recruiters without your explicit consent." },
              ].map((faq, i) => (
                <details key={i} className="group rounded-2xl p-6 cursor-pointer" style={{ backgroundColor: "var(--color-bg-section)", border: "1px solid var(--color-border)" }}>
                  <summary
                    className="flex justify-between items-center font-bold text-lg list-none"
                    style={{ color: "var(--color-heading)" }}
                  >
                    {faq.q}
                    <span className="text-2xl group-open:rotate-45 transition-transform" style={{ color: "var(--color-accent)" }}>+</span>
                  </summary>
                  <p className="mt-4 leading-relaxed font-medium" style={{ color: "var(--color-muted)" }}>
                    {faq.a}
                  </p>
                </details>
              ))}
            </div>
          </motion.div>
        </section>

        {/* Section: Final CTA */}
        <section className="py-32 flex flex-col items-center text-center px-6 relative overflow-hidden" style={{ backgroundColor: "#0F172A" }}>
          {/* Subtle glow instead of gradient */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full blur-[120px] pointer-events-none" style={{ backgroundColor: "rgba(37,99,235,0.03)" }} />
          
          <h2 className="text-4xl md:text-[44px] font-medium mb-10 max-w-2xl relative z-10" style={{ color: "#FFFFFF", lineHeight: "1.3" }}>
            Your Dream Job Is One Resume Away
          </h2>
          
          <div className="flex flex-col md:flex-row gap-4 relative z-10">
            <Link
              to="/analyze"
              className="px-8 py-3.5 rounded-full font-semibold text-[15px] transition-all hover:scale-105"
              style={{
                backgroundColor: "var(--color-cta-bg)",
                color: "var(--color-cta-text)",
              }}
              onMouseEnter={e => e.currentTarget.style.backgroundColor = "var(--color-cta-hover)"}
              onMouseLeave={e => e.currentTarget.style.backgroundColor = "var(--color-cta-bg)"}
            >
              Analyze My Resume
            </Link>
            <Link
              to="/pricing"
              className="px-8 py-3.5 rounded-full font-semibold text-[15px] transition-colors border"
              style={{ borderColor: "rgba(255,255,255,0.2)", color: "#FFFFFF" }}
              onMouseEnter={e => e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.05)"}
              onMouseLeave={e => e.currentTarget.style.backgroundColor = "transparent"}
            >
              View Pricing
            </Link>
          </div>
        </section>
      </div>

    </div>
  );
};

export default HomePage;