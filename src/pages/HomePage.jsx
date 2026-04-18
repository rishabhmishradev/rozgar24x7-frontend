import React, { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";

const Magnetic = ({ children }) => {
  const ref = useRef(null);

  const handleMove = (e) => {
    const rect = ref.current.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    ref.current.style.transform = `translate(${x * 0.15}px, ${y * 0.15}px)`;
  };

  const reset = () => {
    ref.current.style.transform = `translate(0px,0px)`;
  };

  return (
    <div
      ref={ref}
      onMouseMove={handleMove}
      onMouseLeave={reset}
      className="inline-block transition-transform duration-200"
    >
      {children}
    </div>
  );
};

const HomePage = () => {
  const [pos, setPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const move = (e) => {
      setPos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener("mousemove", move);
    return () => window.removeEventListener("mousemove", move);
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white overflow-hidden relative font-[Inter]">

      {/* 🔥 SOFT CURSOR LIGHT */}
      <motion.div
        className="pointer-events-none fixed top-0 left-0 z-0"
        animate={{ x: pos.x - 120, y: pos.y - 120 }}
        transition={{ type: "spring", stiffness: 80, damping: 20 }}
      >
        <div className="w-[240px] h-[240px] rounded-full bg-white/[0.04] blur-3xl" />
      </motion.div>

      {/* 🌫️ NOISE + DEPTH */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.03]" />
      </div>

      {/* ================= HERO ================= */}
      <section className="px-6 md:px-16 py-28 flex flex-col md:flex-row items-center gap-16 relative z-10">

        {/* LEFT */}
        <motion.div
          className="md:w-1/2"
          initial={{ opacity: 0, y: 60 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
        >
          <p className="text-gray-500 text-sm mb-3">
            AI Resume Optimization
          </p>

          <h1 className="text-5xl font-semibold leading-tight mb-6">
            Build a Resume <br />
            <span className="text-gray-400">
              That Gets Selected
            </span>
          </h1>

          <p className="text-gray-500 mb-8 max-w-md">
            Improve your resume with AI insights, better keywords, and clean formatting.
          </p>

          <div className="flex gap-4">
            <Magnetic>
              <Link className="px-6 py-3 rounded-xl bg-white text-black font-medium hover:scale-105 transition">
                Analyze Resume
              </Link>
            </Magnetic>

            <Magnetic>
              <Link className="px-6 py-3 rounded-xl border border-white/10 bg-white/[0.02] backdrop-blur-xl hover:bg-white/[0.06] transition">
                Templates
              </Link>
            </Magnetic>
          </div>
        </motion.div>

        {/* RIGHT CARD */}
        <motion.div
          className="md:w-1/2 flex justify-center"
          initial={{ opacity: 0, y: 60 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <motion.div
            whileHover={{ scale: 1.03 }}
            transition={{ type: "spring", stiffness: 200 }}
            className="bg-white/[0.03] backdrop-blur-2xl border border-white/[0.08] shadow-[0_10px_50px_rgba(0,0,0,0.6)] p-6 rounded-2xl w-[340px]"
          >
            <p className="text-gray-400 text-sm">ATS Score</p>
            <h2 className="text-4xl font-semibold mb-4">92%</h2>

            <div className="space-y-3">
              <div className="h-1 bg-white/10 rounded">
                <div className="h-1 bg-white/70 w-[80%] rounded"></div>
              </div>
              <div className="h-1 bg-white/10 rounded">
                <div className="h-1 bg-white/60 w-[90%] rounded"></div>
              </div>
              <div className="h-1 bg-white/10 rounded">
                <div className="h-1 bg-white/50 w-[70%] rounded"></div>
              </div>
            </div>

            <p className="text-sm text-gray-500 mt-4 leading-relaxed">
              ✔ Strong keywords <br />
              ✔ Good formatting <br />
              ⚠ Improve verbs
            </p>
          </motion.div>
        </motion.div>
      </section>

      {/* DIVIDER */}
      <div className="h-px bg-white/10 mx-16" />

      {/* ================= FEATURES ================= */}
      <section className="px-6 md:px-16 py-24 grid md:grid-cols-3 gap-8">

        {[
          { title: "ATS Score", desc: "Instant resume performance insights." },
          { title: "Keyword Match", desc: "Smart job matching system." },
          { title: "AI Rewrite", desc: "Clean and powerful wording." }
        ].map((item, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            whileHover={{ scale: 1.02 }}
            transition={{ duration: 0.6 }}
            className="bg-white/[0.02] backdrop-blur-xl border border-white/[0.06] p-6 rounded-xl"
          >
            <h3 className="font-medium mb-2">{item.title}</h3>
            <p className="text-sm text-gray-500">{item.desc}</p>
          </motion.div>
        ))}

      </section>

      {/* ================= CTA ================= */}
      <section className="py-28 text-center">

        <motion.h2
          className="text-4xl font-semibold mb-6"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
        >
          Ready to improve your resume?
        </motion.h2>

        <Magnetic>
          <Link className="px-8 py-3 rounded-xl bg-white text-black font-medium hover:scale-105 transition">
            Get Started
          </Link>
        </Magnetic>

      </section>

    </div>
  );
};

export default HomePage;