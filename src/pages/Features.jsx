import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";

const features = [
  {
    title: "ATS Score Analysis",
    desc: "Get a detailed compatibility score based on industry ATS systems.",
    icon: "📊",
  },
  {
    title: "AI Resume Rewrite",
    desc: "Transform weak bullet points into strong, impact-driven statements.",
    icon: "✍️",
  },
  {
    title: "Keyword Optimization",
    desc: "Automatically match your resume with job-specific keywords.",
    icon: "🔍",
  },
  {
    title: "Instant Feedback",
    desc: "Get real-time suggestions to improve readability and structure.",
    icon: "⚡",
  },
  {
    title: "ATS-Friendly Formatting",
    desc: "Ensure your resume passes parsing tests with proper formatting.",
    icon: "📄",
  },
  {
    title: "Job Description Matching",
    desc: "Align your resume with specific job roles in one click.",
    icon: "🎯",
  },
];

const Features = () => {
  const [pos, setPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const move = (e) => setPos({ x: e.clientX, y: e.clientY });
    window.addEventListener("mousemove", move);
    return () => window.removeEventListener("mousemove", move);
  }, []);

  return (
    <motion.div
      className="min-h-screen bg-[#f8fafc] text-black overflow-hidden relative"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >

      {/* 🔥 CURSOR LIGHT */}
      <motion.div
        className="pointer-events-none fixed top-0 left-0 z-0"
        animate={{ x: pos.x - 120, y: pos.y - 120 }}
      >
        <div className="w-[240px] h-[240px] bg-black/[0.05] blur-3xl rounded-full" />
      </motion.div>

      {/* 🌫️ NOISE */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute inset-0 opacity-[0.05] bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" />
      </div>

      <section className="px-6 md:px-16 py-24 relative z-10">

        {/* ================= HEADING ================= */}
        <div className="max-w-xl mb-16">
          <h2 className="text-5xl font-semibold mb-4">
            Powerful Features
          </h2>
          <p className="text-gray-600">
            Everything you need to optimize your resume and land interviews.
          </p>
        </div>

        {/* ================= GRID ================= */}
        <div className="grid md:grid-cols-3 gap-8">

          {features.map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 40 }}
              whileInView={{ opacity: 1, y: 0 }}
              whileHover={{ y: -6 }}
              transition={{ delay: i * 0.08 }}
              className={i % 2 === 1 ? "md:mt-10" : ""}
            >
              <div className="group bg-black/[0.03] backdrop-blur-2xl border border-black/[0.08] p-6 rounded-2xl shadow-[0_10px_30px_rgba(0,0,0,0.08)] transition">

                {/* ICON */}
                <div className="text-2xl mb-4">{item.icon}</div>

                {/* TITLE */}
                <h3 className="text-lg font-medium mb-2">
                  {item.title}
                </h3>

                {/* DESC */}
                <p className="text-sm text-gray-600 leading-relaxed">
                  {item.desc}
                </p>

              </div>
            </motion.div>
          ))}

        </div>

      </section>
    </motion.div>
  );
};

export default Features;