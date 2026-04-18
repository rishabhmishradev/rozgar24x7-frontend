import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";

const About = () => {
  const [pos, setPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const move = (e) => {
      setPos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener("mousemove", move);
    return () => window.removeEventListener("mousemove", move);
  }, []);

  return (
    <motion.div
      className="min-h-screen bg-[#0a0a0a] text-white overflow-hidden relative"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >

      {/* 🔥 SOFT CURSOR LIGHT */}
      <motion.div
        className="pointer-events-none fixed top-0 left-0 z-0"
        animate={{ x: pos.x - 120, y: pos.y - 120 }}
      >
        <div className="w-[240px] h-[240px] bg-white/[0.04] blur-3xl rounded-full" />
      </motion.div>

      {/* 🌫️ NOISE */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute inset-0 opacity-[0.03] bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" />
      </div>

      <section className="px-6 md:px-16 py-24 relative z-10">

        {/* ================= HEADER ================= */}
        <div className="max-w-2xl mb-16">
          <h1 className="text-5xl font-semibold mb-4">
            About ROZGAR 24X7
          </h1>
          <p className="text-white/70">
            Helping job seekers build better resumes and land better opportunities.
          </p>
        </div>

        {/* ================= STORY ================= */}
        <div className="max-w-3xl mb-20 space-y-5">

          <h2 className="text-2xl font-semibold text-white">
            Our Story
          </h2>

          <p className="text-white/70">
            Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
          </p>

          <p className="text-white/70">
            Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.
          </p>

          <p className="italic text-white/50">
            👉 Replace this with your real journey.
          </p>

        </div>

        {/* ================= SPLIT ================= */}
        <div className="grid md:grid-cols-2 gap-10 items-center mb-20">

          {/* LEFT */}
          <div>
            <h2 className="text-3xl font-semibold mb-4">
              What We Do
            </h2>

            <p className="text-white/70 mb-4">
              We help job seekers optimize their resumes using AI-powered tools.
            </p>

            <p className="text-white/70">
              From scoring to keyword optimization, we ensure your resume stands out.
            </p>
          </div>

          {/* RIGHT CARD */}
          <motion.div
            whileHover={{ scale: 1.03 }}
            className="bg-white/[0.05] backdrop-blur-2xl border border-white/[0.1] shadow-[0_10px_50px_rgba(0,0,0,0.8)] rounded-2xl p-6"
          >
            <h3 className="text-xl font-semibold mb-4">
              Our Mission
            </h3>

            <ul className="space-y-3 text-sm text-white/70">
              <li>✔ Help users pass ATS systems</li>
              <li>✔ Improve resume quality with AI</li>
              <li>✔ Increase interview chances</li>
              <li>✔ Make job search easier</li>
            </ul>
          </motion.div>

        </div>

        {/* ================= VALUES ================= */}
        <div>

          <h2 className="text-3xl font-semibold mb-10">
            How We Work
          </h2>

          <div className="grid md:grid-cols-4 gap-6">

            {[
              { title: "User First", desc: "We focus on real needs.", icon: "👤" },
              { title: "AI Driven", desc: "Smart AI results.", icon: "🤖" },
              { title: "Simple", desc: "Clean experience.", icon: "✨" },
              { title: "Growth", desc: "Career growth focus.", icon: "📈" },
            ].map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 40 }}
                whileInView={{ opacity: 1, y: 0 }}
                whileHover={{ scale: 1.03 }}
                transition={{ delay: i * 0.08 }}
                className="bg-white/[0.04] backdrop-blur-xl border border-white/[0.08] p-6 rounded-xl"
              >
                <div className="text-2xl mb-3">{item.icon}</div>
                <h3 className="font-medium mb-1">{item.title}</h3>
                <p className="text-sm text-white/60">{item.desc}</p>
              </motion.div>
            ))}

          </div>

        </div>

      </section>
    </motion.div>
  );
};

export default About;