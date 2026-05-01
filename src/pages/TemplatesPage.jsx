import React, { useState } from "react";
import { motion } from "framer-motion";

const templates = [
  { id: 1, name: "Modern Tech", category: "Technology", score: "98%" },
  { id: 2, name: "Executive Suite", category: "Management", score: "95%" },
  { id: 3, name: "Creative Studio", category: "Design", score: "90%" },
  { id: 4, name: "Finance Pro", category: "Finance", score: "96%" },
  { id: 5, name: "Minimalist Entry", category: "Entry Level", score: "94%" },
  { id: 6, name: "Academic Scholar", category: "Education", score: "97%" },
];

const TemplatesPage = () => {
  const [filter, setFilter] = useState("All");
  const filteredTemplates = filter === "All" ? templates : templates.filter(t => t.category === filter);

  return (
    <div className="min-h-screen relative overflow-hidden pb-32 bg-white dark:bg-[#0a0a0a]">

      <div className="absolute top-0 right-1/4 w-[500px] h-[500px] bg-[#00b14f]/5 rounded-full blur-[120px] -z-10" />

      <section className="px-6 md:px-16 pt-32 relative z-10 max-w-7xl mx-auto">
        
        {/* ================= HEADING ================= */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <motion.h2 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-5xl md:text-6xl font-extrabold mb-6 text-slate-900 dark:text-white"
          >
            Premium <span className="text-[#00b14f]">Templates</span>
          </motion.h2>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-lg text-slate-600 dark:text-slate-400 font-medium"
          >
            Choose from our collection of ATS-optimized, professionally designed templates.
          </motion.p>
        </div>

        {/* ================= FILTER ================= */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="flex flex-wrap justify-center gap-4 mb-16"
        >
          {["All", "Technology", "Management", "Design", "Finance"].map(cat => (
            <button
              key={cat}
              onClick={() => setFilter(cat)}
              className={`px-6 py-2.5 rounded-full text-sm font-semibold transition-all duration-300 border ${
                filter === cat 
                  ? 'bg-[#00b14f] text-white border-[#00b14f] shadow-md shadow-[#00b14f]/20' 
                  : 'bg-white dark:bg-[#111] text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-800 hover:border-[#00b14f]'
              }`}
            >
              {cat}
            </button>
          ))}
        </motion.div>

        {/* ================= GRID ================= */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-10">
          {filteredTemplates.map((item, i) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.1, duration: 0.4 }}
              className="group cursor-pointer"
            >
              <div className="glass-card overflow-hidden p-3 transition-all duration-300 hover:border-[#00b14f]/50">
                
                {/* Template Preview Box */}
                <div className="w-full aspect-[3/4] rounded-2xl bg-slate-100 dark:bg-slate-800 p-6 relative overflow-hidden flex flex-col gap-3">
                  <div className="w-1/2 h-6 bg-slate-300 dark:bg-slate-700 rounded-md mb-4" />
                  <div className="w-full h-2 bg-slate-200 dark:bg-slate-600 rounded-full" />
                  <div className="w-3/4 h-2 bg-slate-200 dark:bg-slate-600 rounded-full mb-4" />
                  <div className="w-full h-20 bg-white dark:bg-slate-900 rounded-md" />
                  <div className="w-full h-20 bg-white dark:bg-slate-900 rounded-md mt-auto" />

                  {/* Hover Overlay */}
                  <div className="absolute inset-0 bg-white/90 dark:bg-black/90 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center z-20">
                    <button className="px-6 py-3 bg-[#00b14f] text-white font-bold rounded-full shadow-lg transform translate-y-4 group-hover:translate-y-0 transition-all duration-300">
                      Use Template
                    </button>
                  </div>
                </div>

                {/* Details */}
                <div className="px-4 py-4">
                  <div className="flex justify-between items-center mb-1">
                    <h3 className="text-xl font-bold text-slate-900 dark:text-white">{item.name}</h3>
                    <span className="text-xs font-bold px-2.5 py-1 bg-[#00b14f]/10 text-[#00b14f] rounded-full">
                      {item.score} ATS
                    </span>
                  </div>
                  <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">{item.category}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

      </section>
    </div>
  );
};

export default TemplatesPage;