import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";

const HomePage = () => {
  return (
    <div className="min-h-screen relative overflow-hidden bg-white dark:bg-[#0a0a0a] selection:bg-green-100 dark:selection:bg-[#00b14f]/30">

      {/* 🟢 MASSIVE SOFT GREEN GLOW BACKGROUND */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-[#00b14f]/10 dark:bg-[#00b14f]/5 rounded-full blur-[150px] -z-10" />

      {/* ================= HERO SECTION ================= */}
      <section className="pt-24 md:pt-32 pb-20 px-6 flex flex-col items-center text-center relative z-10 max-w-5xl mx-auto">

        {/* STARS AND AVATARS */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="flex items-center gap-4 mb-8"
        >
          <div className="flex -space-x-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="w-8 h-8 rounded-full border-2 border-white dark:border-black bg-slate-200 overflow-hidden">
                <img src={`https://i.pravatar.cc/100?img=${i * 5}`} alt="User" className="w-full h-full object-cover" />
              </div>
            ))}
          </div>
          <div className="flex flex-col items-start">
            <div className="flex text-[#00b14f] text-sm">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clipRule="evenodd" /></svg>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clipRule="evenodd" /></svg>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clipRule="evenodd" /></svg>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clipRule="evenodd" /></svg>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clipRule="evenodd" /></svg>
            </div>
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mt-1">Used by 10,000+ users</p>
          </div>
        </motion.div>

        {/* MAIN TYPOGRAPHY */}
        <motion.h1 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-6xl md:text-8xl font-extrabold text-slate-900 dark:text-white leading-[1.1] mb-8 tracking-tight"
        >
          Get hired faster with a <br className="hidden md:block" />
          <span className="text-[#00b14f]">resume that works.</span>
        </motion.h1>

        {/* SUBTITLE */}
        <motion.p 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-lg md:text-xl text-slate-700 dark:text-slate-300 max-w-2xl font-medium mb-10"
        >
          Create, edit and download professional resumes with<br className="hidden md:block" /> AI-powered assistance.
        </motion.p>

        {/* ACTION BUTTONS */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="flex flex-col sm:flex-row items-center gap-4 mb-24"
        >
          <Link to="/analyze" className="px-8 py-3.5 rounded-full bg-[#00b14f] hover:bg-[#009641] text-white font-semibold text-lg flex items-center gap-2 transition-all shadow-lg shadow-[#00b14f]/20">
            Get started 
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
            </svg>
          </Link>
        </motion.div>

        {/* TRUSTED BY SECTION */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="w-full"
        >
          <p className="text-sm font-medium text-slate-500 mb-8">Trusting by leading brands, including</p>
          <div className="flex flex-wrap justify-center items-center gap-8 md:gap-16 opacity-60 dark:opacity-80 grayscale">
            <span className="text-2xl font-bold font-serif">XYZ</span>
            <span className="text-2xl font-bold tracking-tighter">XYZ</span>
            <span className="text-2xl font-bold italic">XYZ</span>
            <span className="text-2xl font-bold tracking-widest">XYZ</span>
          </div>
        </motion.div>

      </section>

      {/* MERGED FEATURES SECTIONS */}
      <div id="features-section">
        {/* Section 4: Deep Dive */}
        <section className="py-32 bg-white dark:bg-[#0a0a0a]">
          <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 md:grid-cols-2 gap-16 md:gap-24 items-center mb-40">
            <div>
              <h2 className="text-4xl font-extrabold mb-6">ATS Scanner: Know your score before you apply.</h2>
              <p className="text-slate-500 dark:text-slate-400 text-lg font-medium mb-8">
                Our engine replicates the logic used by major ATS providers like Workday and Lever. Get a comprehensive score across formatting, keywords, and structural integrity.
              </p>
              <ul className="space-y-4">
                <li className="flex items-center gap-3 font-semibold text-slate-700 dark:text-slate-200">
                  <span className="text-[#00b14f] text-xl">✓</span> Instant PDF/Word Parsing
                </li>
                <li className="flex items-center gap-3 font-semibold text-slate-700 dark:text-slate-200">
                  <span className="text-[#00b14f] text-xl">✓</span> Visual Heatmap of Missing Skills
                </li>
                <li className="flex items-center gap-3 font-semibold text-slate-700 dark:text-slate-200">
                  <span className="text-[#00b14f] text-xl">✓</span> Structural Conflict Detection
                </li>
              </ul>
            </div>
            <div className="relative bg-slate-50 dark:bg-[#111] p-12 rounded-[2rem] overflow-hidden border border-slate-100 dark:border-slate-800">
              <div className="flex flex-col items-center justify-center bg-white dark:bg-black w-64 h-64 rounded-full mx-auto shadow-xl relative z-10">
                <svg className="absolute w-full h-full transform -rotate-90">
                  <circle cx="128" cy="128" fill="transparent" r="100" stroke="currentColor" className="text-slate-100 dark:text-slate-800" strokeWidth="12"></circle>
                  <circle cx="128" cy="128" fill="transparent" r="100" stroke="#00b14f" strokeDasharray="628" strokeDashoffset="81" strokeLinecap="round" strokeWidth="12"></circle>
                </svg>
                <div className="absolute flex flex-col items-center">
                  <span className="text-5xl font-extrabold tracking-tighter">87<span className="text-slate-300 dark:text-slate-700 text-2xl font-light">/100</span></span>
                  <span className="text-[10px] font-bold uppercase text-slate-400 mt-1">Excellent Score</span>
                </div>
              </div>
              <div className="mt-12 flex flex-col gap-3 relative z-10">
                <div className="bg-white dark:bg-black p-4 rounded-xl shadow-sm border-l-4 border-[#00b14f] flex justify-between items-center">
                  <span className="text-sm font-semibold">Keywords Optimized</span>
                  <span className="text-[#00b14f] font-bold">100%</span>
                </div>
                <div className="bg-white dark:bg-black p-4 rounded-xl shadow-sm border-l-4 border-amber-400 flex justify-between items-center">
                  <span className="text-sm font-semibold">Formatting Integrity</span>
                  <span className="text-amber-500 font-bold">72%</span>
                </div>
              </div>
            </div>
          </div>
          <div className="bg-slate-50 dark:bg-[#111] py-32 rounded-[3rem] mx-4 md:mx-10">
            <div className="max-w-6xl mx-auto px-6 grid grid-cols-1 md:grid-cols-2 gap-16 md:gap-24 items-center">
              <div className="order-2 md:order-1 bg-white dark:bg-[#1a1a1a] p-8 rounded-2xl shadow-xl border border-slate-100 dark:border-slate-800">
                <div className="flex items-center gap-4 mb-8 border-b border-slate-100 dark:border-slate-800 pb-4">
                  <div className="w-3 h-3 rounded-full bg-red-400"></div>
                  <div className="w-3 h-3 rounded-full bg-amber-400"></div>
                  <div className="w-3 h-3 rounded-full bg-green-400"></div>
                  <span className="text-xs font-mono text-slate-400 ml-auto">Keyword_Analysis.json</span>
                </div>
                <div className="grid grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <h4 className="text-[10px] uppercase font-bold text-slate-400 tracking-widest">Required Skills</h4>
                    <div className="bg-slate-50 dark:bg-black p-3 rounded-lg text-xs font-mono border border-slate-100 dark:border-slate-800">React.js</div>
                    <div className="bg-slate-50 dark:bg-black p-3 rounded-lg text-xs font-mono border border-slate-100 dark:border-slate-800">Product Strategy</div>
                    <div className="bg-slate-50 dark:bg-black p-3 rounded-lg text-xs font-mono border border-slate-100 dark:border-slate-800">Editorial Design</div>
                  </div>
                  <div className="space-y-4">
                    <h4 className="text-[10px] uppercase font-bold text-slate-400 tracking-widest">Matches Found</h4>
                    <div className="bg-green-50 dark:bg-[#00b14f]/10 text-[#00b14f] p-3 rounded-lg text-xs font-mono flex items-center gap-2">
                      ✓ React.js
                    </div>
                    <div className="bg-green-50 dark:bg-[#00b14f]/10 text-[#00b14f] p-3 rounded-lg text-xs font-mono flex items-center gap-2">
                      ✓ Product Strategy
                    </div>
                    <div className="bg-red-50 dark:bg-red-900/20 text-red-500 p-3 rounded-lg text-xs font-mono flex items-center gap-2">
                      ✕ Editorial Design
                    </div>
                  </div>
                </div>
              </div>
              <div className="order-1 md:order-2">
                <h2 className="text-4xl font-extrabold mb-6">Precision Keyword Injection Engine.</h2>
                <p className="text-slate-500 dark:text-slate-400 text-lg font-medium mb-8">
                  Stop guessing which words matter. Our AI parses job descriptions in real-time to identify the core competencies companies are filtering for, then suggests the perfect placement within your profile.
                </p>
              </div>
            </div>
          </div>
          <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 md:grid-cols-2 gap-16 md:gap-24 items-center pt-32">
            <div>
              <h2 className="text-4xl font-extrabold mb-6">AI Rewriter: Achieve Editorial Excellence.</h2>
              <p className="text-slate-500 dark:text-slate-400 text-lg font-medium mb-8">
                Turn "Responsible for sales" into "Spearheaded high-frequency sales initiatives, resulting in a 40% YoY revenue growth." Our AI understands impact-driven linguistics.
              </p>
              <div className="flex gap-4">
                <button className="bg-slate-900 dark:bg-white text-white dark:text-black px-6 py-3 rounded-full font-bold hover:scale-105 transition-transform">
                  Try Rewriter
                </button>
                <button className="flex items-center gap-2 text-slate-900 dark:text-white font-bold px-6 py-3 hover:text-[#00b14f] transition-colors">
                  Watch Demo ▷
                </button>
              </div>
            </div>
            <div className="bg-slate-900 dark:bg-[#111] p-8 rounded-3xl shadow-2xl overflow-hidden border border-slate-800">
              <div className="space-y-6">
                <div className="p-5 rounded-xl bg-slate-800/50 dark:bg-black/50 border border-slate-700 dark:border-slate-800">
                  <span className="text-[10px] text-slate-400 uppercase font-bold block mb-2">Original Input</span>
                  <p className="text-slate-300 text-sm italic">
                    "I helped the team manage many different projects and kept everything on schedule for the client."
                  </p>
                </div>
                <div className="relative">
                  <div className="absolute -left-2 top-0 bottom-0 w-1 bg-[#00b14f] rounded-full"></div>
                  <div className="p-5 rounded-xl bg-slate-800 dark:bg-black border border-slate-700 dark:border-slate-800 shadow-lg">
                    <span className="text-[10px] text-[#00b14f] uppercase font-bold block mb-2">AI Editorial Enhancement</span>
                    <p className="text-white text-sm font-medium">
                      "Orchestrated cross-functional project lifecycles, ensuring 100% on-time delivery for high-stake client portfolios while optimizing operational workflows."
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section 5: Stats Strip */}
        <section className="bg-slate-900 dark:bg-[#0a0a0a] py-24 border-y border-slate-800">
          <div className="max-w-7xl mx-auto px-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-12 text-center">
              <div className="space-y-2">
                <h4 className="text-[#00b14f] text-5xl font-extrabold">50,000+</h4>
                <p className="text-slate-400 text-xs font-bold uppercase tracking-widest">Active Users</p>
              </div>
              <div className="space-y-2">
                <h4 className="text-[#00b14f] text-5xl font-extrabold">3.2x</h4>
                <p className="text-slate-400 text-xs font-bold uppercase tracking-widest">Interview Lift</p>
              </div>
              <div className="space-y-2">
                <h4 className="text-[#00b14f] text-5xl font-extrabold">94%</h4>
                <p className="text-slate-400 text-xs font-bold uppercase tracking-widest">Success Rate</p>
              </div>
              <div className="space-y-2">
                <h4 className="text-[#00b14f] text-5xl font-extrabold">&lt; 5 min</h4>
                <p className="text-slate-400 text-xs font-bold uppercase tracking-widest">Prep Time</p>
              </div>
            </div>
          </div>
        </section>

        {/* Section 7: Reviews Grid */}
        <section className="py-32 bg-slate-50 dark:bg-[#111]">
          <div className="max-w-7xl mx-auto px-6">
            <div className="text-center mb-20">
              <h2 className="text-4xl font-extrabold">Join 50k+ Successful Professionals</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {[
                { name: "Sarah Jenkins", company: "Hired at Amazon", quote: "The AI rewriter found the exact words I couldn't. I landed an interview with Amazon within 48 hours of updating my profile." },
                { name: "Marcus Chen", company: "Hired at Google", quote: "The ATS scanner was a eye-opener. I didn't realize my resume header was unreadable by bots. 10/10 tool." },
                { name: "Elena Rodriguez", company: "Hired at Netflix", quote: "Editorial patterns are real. The way ROZGAR structures sentences makes you sound like a C-suite executive." }
              ].map((review, i) => (
                <div key={i} className="bg-white dark:bg-[#1a1a1a] p-8 rounded-2xl shadow-sm hover:shadow-xl transition-all border border-slate-100 dark:border-slate-800">
                  <div className="flex items-center gap-4 mb-6">
                    <div className="w-12 h-12 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center font-bold text-slate-500">
                      {review.name[0]}
                    </div>
                    <div>
                      <h4 className="font-bold text-sm">{review.name}</h4>
                      <div className="flex text-amber-400 text-sm">★★★★★</div>
                    </div>
                  </div>
                  <p className="text-slate-600 dark:text-slate-400 text-sm mb-6 italic leading-relaxed">"{review.quote}"</p>
                  <span className="bg-green-100 dark:bg-[#00b14f]/20 text-[#00b14f] text-[10px] font-bold px-3 py-1.5 rounded-full uppercase">
                    {review.company}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Section 8: FAQ */}
        <section className="py-32 bg-white dark:bg-[#0a0a0a]">
          <div className="max-w-3xl mx-auto px-6">
            <h2 className="text-4xl font-extrabold text-center mb-16">Frequently Asked Questions</h2>
            <div className="space-y-4">
              {[
                { q: "How does the AI ATS Scanner work?", a: "Our scanner uses natural language processing (NLP) to mirror the exact logic used by top-tier Applicant Tracking Systems like Greenhouse, Workday, and Lever." },
                { q: "Can I export my resume to PDF?", a: "Yes, all templates are optimized for standard PDF exports that maintain 100% readability for both human recruiters and digital scanners." },
                { q: "Is my data secure?", a: "We use bank-grade encryption and do not sell your personal data to third-party recruiters without your explicit consent." }
              ].map((faq, i) => (
                <details key={i} className="group bg-slate-50 dark:bg-[#111] rounded-2xl p-6 cursor-pointer border border-slate-100 dark:border-slate-800">
                  <summary className="flex justify-between items-center font-bold text-lg list-none group-open:text-[#00b14f]">
                    {faq.q}
                    <span className="text-2xl group-open:rotate-45 transition-transform">+</span>
                  </summary>
                  <p className="mt-4 text-slate-500 dark:text-slate-400 leading-relaxed font-medium">
                    {faq.a}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Section 9: Final CTA */}
        <section className="py-32 bg-slate-900 dark:bg-black flex flex-col items-center text-center px-6 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-b from-transparent to-[#00b14f]/10 pointer-events-none"></div>
          <h2 className="text-5xl font-extrabold text-white mb-8 max-w-3xl relative z-10">
            Your Dream Job Is One Resume Away
          </h2>
          <div className="flex flex-col md:flex-row gap-6 relative z-10">
            <Link to="/analyze" className="bg-[#00b14f] text-white px-10 py-4 rounded-full font-bold text-lg hover:bg-[#009641] hover:scale-105 transition-all shadow-lg shadow-[#00b14f]/20">
              Analyze My Resume
            </Link>
            <Link to="/pricing" className="border border-slate-700 text-white px-10 py-4 rounded-full font-bold text-lg hover:bg-slate-800 transition-colors">
              View Pricing
            </Link>
          </div>
        </section>
      </div>

    </div>
  );
};

export default HomePage;