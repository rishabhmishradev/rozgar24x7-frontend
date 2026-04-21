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

        {/* ================= HEADER ================= */}
        <div className="max-w-2xl mb-16">
          <h1 className="text-5xl font-semibold mb-4">
            About ROZGAR 24X7
          </h1>
          <p className="text-gray-600">
            Helping job seekers build better resumes and land better opportunities.
          </p>
        </div>

        {/* ================= STORY ================= */}
        <div className="max-w-3xl mb-20 space-y-5">

          <h2 className="text-2xl font-semibold">
            Our Story
          </h2>

          <p className="text-gray-600">
            Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
          </p>

          <p className="text-gray-600">
            Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.
          </p>

          <p className="italic text-gray-500">
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

            <p className="text-gray-600 mb-4">
              We help job seekers optimize their resumes using AI-powered tools.
            </p>

            <p className="text-gray-600">
              From scoring to keyword optimization, we ensure your resume stands out.
            </p>
          </div>

          {/* RIGHT CARD */}
          <motion.div
            whileHover={{ scale: 1.03 }}
            className="bg-black/[0.03] backdrop-blur-2xl border border-black/[0.08] shadow-[0_10px_40px_rgba(0,0,0,0.08)] rounded-2xl p-6"
          >
            <h3 className="text-xl font-semibold mb-4">
              Our Mission
            </h3>

            <ul className="space-y-3 text-sm text-gray-600">
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
                className="bg-black/[0.02] backdrop-blur-xl border border-black/[0.06] p-6 rounded-xl"
              >
                <div className="text-2xl mb-3">{item.icon}</div>
                <h3 className="font-medium mb-1">{item.title}</h3>
                <p className="text-sm text-gray-600">{item.desc}</p>
              </motion.div>
            ))}

          </div>

        </div>

      </section>
    </motion.div>
  );
};

export default About;