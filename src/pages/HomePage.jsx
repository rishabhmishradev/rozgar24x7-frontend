import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";

const HomePage = () => {
  return (
    <motion.div
      className="min-h-screen bg-gradient-to-br from-[#E5E7EB] via-[#C7D2D9] to-[#2C4A52] text-[#0F172A] overflow-hidden"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >

      {/* ================= HERO ================= */}
      <section className="px-6 md:px-16 lg:px-24 xl:px-32 py-24 flex flex-col md:flex-row items-center gap-12 relative">

        {/* floating bg blobs */}
        <div className="absolute top-10 right-20 w-40 h-40 bg-[#6D8B8F] rounded-full blur-3xl opacity-30"></div>
        <div className="absolute bottom-10 left-10 w-52 h-52 bg-[#2C4A52] rounded-full blur-3xl opacity-20"></div>

        {/* LEFT */}
        <div className="md:w-1/2 z-10">
          <p className="text-sm text-[#2C4A52] mb-3 font-medium">
            AI Resume Optimization
          </p>

          <h1 className="text-4xl md:text-5xl font-bold leading-tight mb-5">
            Build a Resu <br />
            <span className="text-[#2C4A52]">
              That Actually Gets Selected
            </span>
          </h1>

          <p className="text-gray-700 text-base mb-6 max-w-md">
            Improve your resume with AI insights, better keywords, and optimized structure to pass ATS systems.
          </p>

          <div className="flex gap-3">
            <Link
              to="/analyze"
              className="px-6 py-3 rounded-lg bg-[#2C4A52] text-white hover:opacity-90 transition"
            >
              Analyze Resume
            </Link>

            <Link
              to="/templates"
              className="px-6 py-3 rounded-lg border border-gray-300 bg-white/40 backdrop-blur-sm hover:bg-white/60 transition"
            >
              Templates
            </Link>
          </div>
        </div>

        {/* RIGHT GLASS CARD */}
        <div className="md:w-1/2 flex justify-center z-10">
          <motion.div
            animate={{ y: [0, -8, 0] }}
            transition={{ duration: 4, repeat: Infinity }}
            className="bg-white/30 backdrop-blur-lg border border-white/20 rounded-2xl shadow-xl p-6 w-[340px]"
          >
            <p className="text-sm text-gray-600">ATS Score</p>
            <h2 className="text-2xl font-bold text-[#2C4A52] mb-4">92%</h2>

            <div className="space-y-2">
              <div className="h-2 bg-gray-200 rounded">
                <div className="h-2 bg-[#2C4A52] w-[80%] rounded"></div>
              </div>
              <div className="h-2 bg-gray-200 rounded">
                <div className="h-2 bg-[#6D8B8F] w-[90%] rounded"></div>
              </div>
              <div className="h-2 bg-gray-200 rounded">
                <div className="h-2 bg-[#3E5C61] w-[70%] rounded"></div>
              </div>
            </div>

            <p className="text-sm text-gray-600 mt-4">
              ✔ Strong keywords <br />
              ✔ Good formatting <br />
              ⚠ Improve verbs
            </p>
          </motion.div>
        </div>
      </section>

      {/* ================= FEATURES ================= */}
      <section className="px-6 md:px-16 lg:px-24 xl:px-32 py-20">

        <div className="mb-12 max-w-xl">
          <h2 className="text-3xl font-bold mb-3">
            Built for Real Results
          </h2>
          <p className="text-gray-700">
            Everything you need to improve your resume and land interviews faster.
          </p>
        </div>

        {/* staggered layout (not boxy) */}
        <div className="grid md:grid-cols-3 gap-6">

          <div className="bg-white/50 backdrop-blur-md border border-white/30 p-6 rounded-xl shadow-sm">
            <h3 className="font-semibold mb-2">ATS Score</h3>
            <p className="text-sm text-gray-600">
              Know how your resume performs instantly.
            </p>
          </div>

          <div className="bg-white/50 backdrop-blur-md border border-white/30 p-6 rounded-xl shadow-sm md:mt-6">
            <h3 className="font-semibold mb-2">Keyword Optimization</h3>
            <p className="text-sm text-gray-600">
              Match job descriptions with smart keywords.
            </p>
          </div>

          <div className="bg-white/50 backdrop-blur-md border border-white/30 p-6 rounded-xl shadow-sm">
            <h3 className="font-semibold mb-2">AI Rewrite</h3>
            <p className="text-sm text-gray-600">
              Improve clarity and impact instantly.
            </p>
          </div>

        </div>
      </section>

      {/* ================= HOW IT WORKS ================= */}
      <section className="px-6 md:px-16 lg:px-24 xl:px-32 py-20 bg-white/40 backdrop-blur-sm">

        <div className="text-center mb-10">
          <h2 className="text-3xl font-bold">
            How It Works
          </h2>
        </div>

        <div className="flex flex-col md:flex-row justify-between gap-8 text-center">

          {[
            { step: "01", title: "Upload Resume" },
            { step: "02", title: "AI Analysis" },
            { step: "03", title: "Download & Apply" }
          ].map((item, i) => (
            <div key={i} className="flex-1">
              <div className="text-[#2C4A52] font-bold text-lg">
                {item.step}
              </div>
              <p className="mt-2 text-gray-700">
                {item.title}
              </p>
            </div>
          ))}

        </div>
      </section>

      {/* ================= CTA ================= */}
      <section className="px-6 md:px-16 lg:px-24 xl:px-32 py-24 text-center">

        <h2 className="text-3xl md:text-4xl font-bold mb-4">
          Ready to improve your resume?
        </h2>

        <Link
          to="/analyze"
          className="px-8 py-3 rounded-lg bg-[#2C4A52] text-white hover:opacity-90 transition"
        >
          Get Started
        </Link>

      </section>

    </motion.div>
  );
};

export default HomePage;
