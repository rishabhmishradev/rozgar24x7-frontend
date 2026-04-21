import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Tilt from "react-parallax-tilt";

const templates = [
  { title: "Executive Resume", category: "Professional", score: "96" },
  { title: "Clean ATS Layout", category: "Modern", score: "97" },
  { title: "Data Scientist Resume", category: "Data Science", score: "95" },
  { title: "Fresher Resume", category: "Student", score: "88" },
  { title: "Business Resume", category: "Corporate", score: "94" },
  { title: "Creative Resume", category: "Creative", score: "91" },
];

const TemplatesPage = () => {
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
          <h2 className="text-5xl font-semibold mb-3">
            Resume Templates
          </h2>
          <p className="text-gray-600">
            Designed to pass ATS and impress recruiters.
          </p>
        </div>

        {/* ================= GRID ================= */}
        <div className="grid md:grid-cols-3 gap-8">

          {templates.map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 40 }}
              whileInView={{ opacity: 1, y: 0 }}
              whileHover={{ y: -6 }}
              transition={{ delay: i * 0.08 }}
              className={i % 2 === 1 ? "md:mt-10" : ""}
            >
              <Tilt tiltMaxAngleX={6} tiltMaxAngleY={6} scale={1.03}>

                <div className="group relative bg-black/[0.03] backdrop-blur-2xl border border-black/[0.08] rounded-2xl p-4 shadow-[0_10px_30px_rgba(0,0,0,0.08)] overflow-hidden">

                  {/* IMAGE */}
                  <div className="relative overflow-hidden rounded-lg mb-4">
                    <div className="h-44 bg-black/[0.04] flex items-center justify-center text-gray-400 text-sm">
                      Preview
                    </div>

                    {/* SCORE */}
                    <div className="absolute top-3 right-3 bg-white/80 backdrop-blur px-3 py-1 rounded-full text-xs font-medium border border-black/[0.08]">
                      {item.score}% ATS
                    </div>
                  </div>

                  {/* CONTENT */}
                  <h3 className="text-lg font-medium">
                    {item.title}
                  </h3>

                  <p className="text-sm text-gray-600 mb-4">
                    {item.category}
                  </p>

                  {/* CTA */}
                  <button className="w-full py-2 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-800 transition">
                    View Template
                  </button>

                </div>

              </Tilt>
            </motion.div>
          ))}

        </div>

      </section>
    </motion.div>
  );
};

export default TemplatesPage;