import React, { useState } from "react";
import { motion } from "framer-motion";

const Pricing = () => {
  const [resumeCount, setResumeCount] = useState(2);

  const increment = () => setResumeCount((prev) => prev + 1);
  const decrement = () => setResumeCount((prev) => (prev > 1 ? prev - 1 : 1));

  return (
    <div className="min-h-screen bg-white dark:bg-[#0a0a0a] pt-12 md:pt-16 pb-24 relative overflow-hidden">
      
      {/* Soft background glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-[#00b14f]/5 rounded-full blur-[120px] -z-10" />

      <div className="max-w-7xl mx-auto px-6">
        
        {/* Header Section */}
        <div className="text-center mb-16">
          <motion.div 
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-50 dark:bg-[#00b14f]/10 text-[#00b14f] text-sm font-semibold mb-6"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
              <path fillRule="evenodd" d="M9 4.5a.75.75 0 0 1 .721.544l.813 2.846a3.75 3.75 0 0 0 2.576 2.576l2.846.813a.75.75 0 0 1 0 1.442l-2.846.813a3.75 3.75 0 0 0-2.576 2.576l-.813 2.846a.75.75 0 0 1-1.442 0l-.813-2.846a3.75 3.75 0 0 0-2.576-2.576l-2.846-.813a.75.75 0 0 1 0-1.442l2.846-.813A3.75 3.75 0 0 0 7.466 7.89l.813-2.846A.75.75 0 0 1 9 4.5Z" clipRule="evenodd" />
            </svg>
            Simple, transparent pricing
          </motion.div>
          
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-5xl md:text-6xl font-extrabold text-slate-900 dark:text-white mb-4 tracking-tight"
          >
            Invest in your career.
          </motion.h1>
          
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-lg text-slate-600 dark:text-slate-400 font-medium"
          >
            Join professionals who landed their dream jobs using ROZGAR 24X7.
          </motion.p>
        </div>

        {/* Pricing Cards */}
        <div className="flex flex-col lg:flex-row justify-center items-stretch gap-8 mt-12">
          
          {/* PRO CARD */}
          <motion.div 
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex-1 w-full max-w-md mx-auto bg-white dark:bg-[#111] border border-slate-200 dark:border-slate-800 rounded-[2rem] p-8 shadow-sm flex flex-col"
          >
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">Pro</h2>
              <p className="text-sm text-slate-500 font-medium mb-4">For serious job seekers</p>
              
              <span className="inline-block px-2.5 py-1 bg-green-100 dark:bg-[#00b14f]/20 text-[#00b14f] text-xs font-bold rounded mb-4">
                SAVE 67%
              </span>
              
              <div className="flex items-end gap-2 mb-1">
                <span className="text-5xl font-extrabold text-slate-900 dark:text-white tracking-tighter">₹500</span>
                <span className="text-xl text-red-500 font-bold line-through mb-1">₹1500</span>
              </div>
              <p className="text-sm text-slate-500 font-medium">Limited time offer</p>
            </div>

            <div className="flex-grow">
              <ul className="space-y-4 mb-8">
                {[
                  "Unlimited ATS score analysis",
                  "ATS-optimized resume formats",
                  "Early bird offers access",
                  "Help desk access"
                ].map((feature, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <div className="mt-0.5 text-[#00b14f]">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" />
                      </svg>
                    </div>
                    <span className="text-[15px] text-slate-700 dark:text-slate-300 font-medium">{feature}</span>
                  </li>
                ))}
              </ul>
            </div>

            <button className="w-full py-4 rounded-xl bg-[#00b14f] hover:bg-[#009641] text-white font-bold text-lg transition-colors shadow-md shadow-[#00b14f]/20">
              Buy Now
            </button>
          </motion.div>

          {/* MAX CARD */}
          <motion.div 
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="flex-1 w-full max-w-md mx-auto bg-white dark:bg-[#111] border-2 border-[#00b14f] rounded-[2rem] p-8 shadow-xl shadow-[#00b14f]/10 flex flex-col relative mt-4 lg:mt-0 lg:-mt-4"
          >
            {/* MOST POPULAR BADGE */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2">
              <span className="bg-[#00b14f] text-white text-[11px] font-black tracking-widest uppercase px-4 py-1.5 rounded-full shadow-md">
                Most Popular
              </span>
            </div>

            <div className="mb-6">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">Max</h2>
              <p className="text-sm text-slate-500 font-medium mb-4">White-glove career strategy</p>
              
              <span className="inline-block px-2.5 py-1 bg-green-100 dark:bg-[#00b14f]/20 text-[#00b14f] text-xs font-bold rounded mb-4">
                SAVE 73%
              </span>
              
              <div className="flex items-end gap-2 mb-1">
                <span className="text-5xl font-extrabold text-slate-900 dark:text-white tracking-tighter">₹800</span>
                <span className="text-xl text-red-500 font-bold line-through mb-1">₹3000</span>
              </div>
              <p className="text-sm text-slate-500 font-medium">Limited time offer</p>
            </div>

            <div className="flex-grow">
              <ul className="space-y-4 mb-8">
                {[
                  "Get your resume within 24 hrs",
                  "1:1 Mentor Calls",
                  "Expert-crafted ATS-optimized resume",
                  "Personalized mentor guidance",
                  "Early bird offers access",
                  "Help desk access"
                ].map((feature, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <div className="mt-0.5 text-[#00b14f]">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" />
                      </svg>
                    </div>
                    <span className="text-[15px] text-slate-700 dark:text-slate-300 font-medium">{feature}</span>
                  </li>
                ))}
              </ul>
            </div>

            <button className="w-full py-4 rounded-xl bg-[#00b14f] hover:bg-[#009641] text-white font-bold text-lg transition-colors shadow-md shadow-[#00b14f]/20">
              Buy Now
            </button>
          </motion.div>

          {/* PRO MAX CARD */}
          <motion.div 
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="flex-1 w-full max-w-md mx-auto bg-slate-900 dark:bg-black border border-slate-800 rounded-[2rem] p-8 shadow-xl flex flex-col relative text-white"
          >
            <div className="mb-6">
              <h2 className="text-2xl font-bold mb-1">Pro Max</h2>
              <p className="text-sm text-slate-400 font-medium mb-4">Ultimate plan for multiple profiles</p>
              
              <span className="inline-block px-2.5 py-1 bg-[#00b14f]/20 text-[#00b14f] text-xs font-bold rounded mb-4">
                CUSTOM PLAN
              </span>
              
              <div className="flex items-end gap-2 mb-1">
                <span className="text-5xl font-extrabold tracking-tighter">
                  ₹{Math.round((resumeCount * 800) * (1 - Math.min((resumeCount - 1) * 0.1, 0.5)))}
                </span>
                <span className="text-xl text-red-500 font-bold line-through mb-1">
                  ₹{resumeCount * 3000}
                </span>
              </div>
              <p className="text-sm text-slate-400 font-medium">
                {resumeCount > 1 ? `Includes ${Math.min((resumeCount - 1) * 10, 50)}% bulk discount` : "Limited time offer"}
              </p>
            </div>

            <div className="flex-grow">
              <ul className="space-y-4 mb-8">
                <li className="flex items-start gap-3">
                  <div className="mt-0.5 text-[#00b14f]">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" />
                    </svg>
                  </div>
                  <span className="text-[15px] font-bold text-white">{resumeCount} Resumes</span>
                </li>
                {[
                  "Get your resume within 24 hrs",
                  "1:1 Mentor Calls",
                  "Expert-crafted ATS-optimized resume",
                  "Personalized mentor guidance",
                  "Early bird offers access",
                  "Help desk access"
                ].map((feature, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <div className="mt-0.5 text-[#00b14f]">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" />
                      </svg>
                    </div>
                    <span className="text-[15px] text-slate-300 font-medium">{feature}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="flex items-center gap-3 mt-auto">
              <div className="flex items-center justify-between bg-slate-800 rounded-xl p-2 w-[120px] border border-slate-700">
                <button onClick={decrement} className="w-8 h-8 rounded-lg bg-slate-700 hover:bg-slate-600 flex items-center justify-center font-bold text-xl text-white transition-colors">-</button>
                <span className="font-bold text-lg">{resumeCount}</span>
                <button onClick={increment} className="w-8 h-8 rounded-lg bg-slate-700 hover:bg-slate-600 flex items-center justify-center font-bold text-xl text-white transition-colors">+</button>
              </div>
              <button className="flex-1 py-4 rounded-xl bg-[#00b14f] hover:bg-[#009641] text-white font-bold text-lg transition-colors shadow-md shadow-[#00b14f]/20">
                Buy Now
              </button>
            </div>
          </motion.div>

        </div>
      </div>
    </div>
  );
};

export default Pricing;
