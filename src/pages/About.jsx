import React from "react";
import { motion } from "framer-motion";

const About = () => {
  return (
    <motion.div
      className="min-h-screen bg-gradient-to-br from-[#E5E7EB] via-[#C7D2D9] to-[#2C4A52] text-[#0F172A]"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >

      <section className="px-6 md:px-16 lg:px-24 xl:px-32 py-20">

        {/* ================= HEADER ================= */}
        <div className="max-w-2xl mb-16">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            About ROZGAR 24X7
          </h1>
          <p className="text-gray-700">
            Helping job seekers build better resumes and land better opportunities.
          </p>
        </div>

        {/* ================= STORY ================= */}
        <div className="max-w-3xl mb-20 space-y-5 text-gray-700">

          <h2 className="text-2xl font-bold text-[#0F172A]">
            Our Story
          </h2>

          <p>
            Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
          </p>

          <p>
            Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.
          </p>

          <p className="italic">
            👉 This is where you write your real journey, struggles, and why you built this product.
          </p>

        </div>

        {/* ================= SPLIT SECTION ================= */}
        <div className="grid md:grid-cols-2 gap-10 items-center mb-20">

          {/* LEFT TEXT */}
          <div>
            <h2 className="text-3xl font-bold mb-4">
              What We Do
            </h2>

            <p className="text-gray-700 mb-4">
              We help job seekers optimize their resumes using AI-powered tools that improve ATS compatibility and readability.
            </p>

            <p className="text-gray-700">
              From scoring to keyword optimization, we ensure your resume stands out.
            </p>
          </div>

          {/* RIGHT GLASS CARD */}
          <div className="bg-white/40 backdrop-blur-lg border border-white/30 rounded-2xl p-6 shadow-sm">

            <h3 className="text-xl font-semibold mb-4">
              Our Mission
            </h3>

            <ul className="space-y-3 text-sm text-gray-700">
              <li>✔ Help users pass ATS systems</li>
              <li>✔ Improve resume quality with AI</li>
              <li>✔ Increase interview chances</li>
              <li>✔ Make job search easier</li>
            </ul>

          </div>

        </div>

        {/* ================= VALUES ================= */}
        <div>

          <h2 className="text-3xl font-bold mb-10">
            How We Work
          </h2>

          <div className="grid md:grid-cols-4 gap-6">

            {[
              {
                title: "User First",
                desc: "We focus on real user needs.",
                icon: "👤",
              },
              {
                title: "AI Driven",
                desc: "Smart AI for better results.",
                icon: "🤖",
              },
              {
                title: "Simple",
                desc: "Clean and easy experience.",
                icon: "✨",
              },
              {
                title: "Growth",
                desc: "Helping users grow careers.",
                icon: "📈",
              },
            ].map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
                viewport={{ once: true }}
                className={`
                  bg-white/40 backdrop-blur-lg border border-white/30 
                  p-6 rounded-xl shadow-sm
                  ${i % 2 === 1 ? "md:mt-6" : ""}
                `}
              >
                <div className="text-3xl mb-3">{item.icon}</div>
                <h3 className="font-semibold mb-1">{item.title}</h3>
                <p className="text-sm text-gray-700">{item.desc}</p>
              </motion.div>
            ))}

          </div>

        </div>

      </section>
    </motion.div>
  );
};

export default About;