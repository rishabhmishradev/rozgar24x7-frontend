import React from "react";
import { motion } from "framer-motion";
import Tilt from "react-parallax-tilt";

const templates = [
  {
    image: "/",
    category: "Professional",
    title: "Executive Resume",
    score: "96",
  },
  {
    image: "/",
    category: "Modern",
    title: "Clean ATS Layout",
    score: "97",
  },
  {
    image: "/",
    category: "Data Science",
    title: "Data Scientist Resume",
    score: "95",
  },
  {
    image: "/",
    category: "Student",
    title: "Fresher Resume",
    score: "88",
  },
  {
    image: "/",
    category: "Corporate",
    title: "Business Resume",
    score: "94",
  },
  {
    image: "/",
    category: "Creative",
    title: "Creative Resume",
    score: "91",
  },
];

const TemplatesPage = () => {
  return (
    <motion.div
      className="min-h-screen bg-gradient-to-br from-[#E5E7EB] via-[#C7D2D9] to-[#2C4A52]"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >

      <section className="px-6 md:px-16 lg:px-24 xl:px-32 py-20">

        {/* ================= HEADING ================= */}
        <div className="max-w-xl mb-14">
          <h2 className="text-4xl md:text-5xl font-bold mb-3 text-[#0F172A]">
            Proven Resume Templates
          </h2>
          <p className="text-gray-700">
            Templates designed to pass ATS and impress recruiters.
          </p>
        </div>

        {/* ================= GRID ================= */}
        <div className="grid md:grid-cols-3 gap-6">

          {templates.map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              viewport={{ once: true }}
              className={i % 2 === 1 ? "md:mt-8" : ""}
            >
              <Tilt tiltMaxAngleX={5} tiltMaxAngleY={5}>

                <div className="bg-white/40 backdrop-blur-lg border border-white/30 
                rounded-2xl p-4 shadow-sm hover:shadow-md transition group cursor-pointer">

                  {/* IMAGE */}
                  <div className="relative overflow-hidden rounded-lg">
                    <div className="h-44 bg-[#D1D5DB] flex items-center justify-center text-gray-500 text-sm">
                      Preview
                    </div>

                    {/* SCORE */}
                    <div className="absolute top-3 right-3 bg-white/80 backdrop-blur px-3 py-1 rounded-full text-xs font-semibold shadow">
                      {item.score} ATS
                    </div>
                  </div>

                  {/* CONTENT */}
                  <h3 className="text-lg font-semibold mt-4 text-[#0F172A]">
                    {item.title}
                  </h3>

                  <p className="text-sm text-gray-600 mb-4">
                    {item.category}
                  </p>

                  {/* CTA */}
                  <button className="w-full py-2 rounded-lg bg-[#2C4A52] text-white text-sm font-medium hover:opacity-90 transition">
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