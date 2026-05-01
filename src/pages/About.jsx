import React from "react";
import { motion } from "framer-motion";

const About = () => {
  return (
    <div className="min-h-screen relative overflow-hidden pb-32 bg-white dark:bg-[#0a0a0a]">
      
      {/* 🟢 BACKGROUND GLOW */}
      <div className="absolute top-1/4 left-1/4 w-[600px] h-[600px] bg-[#00b14f]/5 rounded-full blur-[150px] -z-10" />

      <section className="px-6 md:px-16 pt-32 relative z-10 max-w-5xl mx-auto">
        
        {/* ================= HERO ================= */}
        <div className="text-center mb-24">
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="inline-block px-4 py-1.5 rounded-full bg-green-50 dark:bg-[#00b14f]/10 text-[#00b14f] font-bold text-sm mb-6"
          >
            Our Mission
          </motion.div>
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-5xl md:text-7xl font-extrabold mb-8 leading-tight text-slate-900 dark:text-white"
          >
            Empowering Careers <br />
            with <span className="text-[#00b14f]">Intelligent AI</span>
          </motion.h1>
        </div>

        {/* ================= STORY SECTION ================= */}
        <div className="grid md:grid-cols-2 gap-16 items-center mb-32">
          <motion.div 
            initial={{ opacity: 0, x: -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="relative"
          >
            <div className="absolute inset-0 bg-[#00b14f]/10 rounded-3xl blur-2xl transform -rotate-6 scale-105 -z-10" />
            <div className="glass-card p-10 relative z-10 border-t-4 border-t-[#00b14f]">
              <h3 className="text-3xl font-bold mb-6 text-slate-900 dark:text-white">Why We Built rozgar.</h3>
              <p className="text-lg text-slate-600 dark:text-slate-400 mb-6 leading-relaxed font-medium">
                Job hunting shouldn't feel like sending your resume into a black hole. We realized that highly qualified candidates were being rejected simply because their resumes weren't optimized for automated Applicant Tracking Systems (ATS).
              </p>
              <p className="text-lg text-slate-600 dark:text-slate-400 leading-relaxed font-medium">
                Our platform was created to level the playing field. By combining cutting-edge AI language models with recruitment industry insights, we've built a platform that translates your real-world experience into the exact language that hiring managers—and their algorithms—are looking for.
              </p>
            </div>
          </motion.div>

          <motion.div 
            initial={{ opacity: 0, x: 40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="flex flex-col gap-6"
          >
            <div className="bg-white dark:bg-[#111] p-8 rounded-3xl flex items-center gap-6 border border-slate-100 dark:border-slate-800 shadow-sm hover:border-[#00b14f]/30 transition-colors">
              <div className="w-16 h-16 rounded-2xl bg-green-50 dark:bg-[#00b14f]/10 flex items-center justify-center text-3xl text-[#00b14f]">🎯</div>
              <div>
                <h4 className="text-xl font-bold mb-2 text-slate-900 dark:text-white">Precision</h4>
                <p className="text-slate-600 dark:text-slate-400 font-medium">Data-driven optimization for maximum impact.</p>
              </div>
            </div>
            <div className="bg-white dark:bg-[#111] p-8 rounded-3xl flex items-center gap-6 border border-slate-100 dark:border-slate-800 shadow-sm hover:border-[#00b14f]/30 transition-colors ml-8">
              <div className="w-16 h-16 rounded-2xl bg-green-50 dark:bg-[#00b14f]/10 flex items-center justify-center text-3xl text-[#00b14f]">🚀</div>
              <div>
                <h4 className="text-xl font-bold mb-2 text-slate-900 dark:text-white">Empowerment</h4>
                <p className="text-slate-600 dark:text-slate-400 font-medium">Giving candidates the tools to succeed.</p>
              </div>
            </div>
            <div className="bg-white dark:bg-[#111] p-8 rounded-3xl flex items-center gap-6 border border-slate-100 dark:border-slate-800 shadow-sm hover:border-[#00b14f]/30 transition-colors">
              <div className="w-16 h-16 rounded-2xl bg-green-50 dark:bg-[#00b14f]/10 flex items-center justify-center text-3xl text-[#00b14f]">💡</div>
              <div>
                <h4 className="text-xl font-bold mb-2 text-slate-900 dark:text-white">Innovation</h4>
                <p className="text-slate-600 dark:text-slate-400 font-medium">Leveraging AI to solve real-world problems.</p>
              </div>
            </div>
          </motion.div>
        </div>

        {/* ================= STATS ================= */}
        <div className="grid md:grid-cols-3 gap-8">
          {[
            { number: "500K+", label: "Resumes Optimized" },
            { number: "98%", label: "ATS Pass Rate" },
            { number: "3x", label: "More Interviews" }
          ].map((stat, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.2 }}
              className="bg-green-50 dark:bg-[#00b14f]/5 border border-green-100 dark:border-[#00b14f]/10 text-center p-10 rounded-3xl"
            >
              <h3 className="text-5xl font-extrabold mb-2 text-[#00b14f]">{stat.number}</h3>
              <p className="text-slate-700 dark:text-slate-300 font-bold uppercase tracking-wider">{stat.label}</p>
            </motion.div>
          ))}
        </div>

      </section>
    </div>
  );
};

export default About;