import React from "react";
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
  return (
    <motion.div
      className="min-h-screen bg-gradient-to-br from-[#E5E7EB] via-[#C7D2D9] to-[#2C4A52] text-[#0F172A]"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >

      <section className="px-6 md:px-16 lg:px-24 xl:px-32 py-20">

        {/* ================= HEADING ================= */}
        <div className="max-w-xl mb-14">
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            Powerful Features <br /> Built for Results
          </h2>
          <p className="text-gray-700">
            Everything you need to optimize your resume and land more interviews.
          </p>
        </div>

        {/* ================= LAYOUT (NOT GRID ONLY) ================= */}

        <div className="grid md:grid-cols-3 gap-6">

          {features.map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              viewport={{ once: true }}
              className={`
                bg-white/40 backdrop-blur-lg border border-white/30 
                p-6 rounded-2xl shadow-sm hover:shadow-md transition
                ${i % 2 === 1 ? "md:mt-8" : ""}
              `}
            >
              <div className="text-3xl mb-3">{item.icon}</div>

              <h3 className="text-lg font-semibold mb-2">
                {item.title}
              </h3>

              <p className="text-sm text-gray-700 leading-relaxed">
                {item.desc}
              </p>
            </motion.div>
          ))}

        </div>

      </section>
    </motion.div>
  );
};

export default Features;