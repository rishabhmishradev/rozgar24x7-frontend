import React from "react";
import { motion } from "framer-motion";

const About = () => {
  return (
    <div className="min-h-screen relative overflow-hidden pb-32" style={{ backgroundColor: "var(--color-bg)" }}>

      {/* Background glow */}
      <div
        className="absolute top-1/4 left-1/4 w-[600px] h-[600px] rounded-full blur-[150px] -z-10"
        style={{ backgroundColor: "rgba(37,99,235,0.05)" }}
      />

      <section className="px-6 md:px-16 pt-32 relative z-10 max-w-5xl mx-auto">

        {/* HERO */}
        <div className="text-center mb-24">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="inline-block px-4 py-1.5 rounded-full font-bold text-sm mb-6"
            style={{ backgroundColor: "rgba(37,99,235,0.08)", color: "var(--color-accent)" }}
          >
            Our Mission
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-5xl md:text-7xl font-extrabold mb-8 leading-tight"
            style={{ color: "var(--color-heading)" }}
          >
            Empowering Careers <br />
            with <span style={{ color: "var(--color-accent)" }}>Intelligent AI</span>
          </motion.h1>
        </div>

        {/* STORY SECTION */}
        <div className="grid md:grid-cols-2 gap-16 items-center mb-32">
          <motion.div
            initial={{ opacity: 0, x: -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="relative"
          >
            <div
              className="absolute inset-0 rounded-3xl blur-2xl transform -rotate-6 scale-105 -z-10"
              style={{ backgroundColor: "rgba(37,99,235,0.07)" }}
            />
            <div
              className="glass-card p-10 relative z-10"
              style={{ borderTop: "4px solid var(--color-accent)" }}
            >
              <h3 className="text-3xl font-bold mb-6" style={{ color: "var(--color-heading)" }}>Why We Built rozgar.</h3>
              <p className="text-lg font-medium mb-6 leading-relaxed" style={{ color: "var(--color-muted)" }}>
                Job hunting shouldn't feel like sending your resume into a black hole. We realized that highly qualified candidates were being rejected simply because their resumes weren't optimized for automated Applicant Tracking Systems (ATS).
              </p>
              <p className="text-lg font-medium leading-relaxed" style={{ color: "var(--color-muted)" }}>
                Our platform was created to level the playing field. By combining cutting-edge AI language models with recruitment industry insights, we've built a platform that translates your real-world experience into the exact language that hiring managers—and their algorithms—are looking for.
              </p>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="flex flex-col gap-6"
          >
            {[
              { emoji: "🎯", title: "Precision",    desc: "Data-driven optimization for maximum impact.",   offset: "" },
              { emoji: "🚀", title: "Empowerment",  desc: "Giving candidates the tools to succeed.",        offset: "ml-8" },
              { emoji: "💡", title: "Innovation",   desc: "Leveraging AI to solve real-world problems.",    offset: "" },
            ].map(({ emoji, title, desc, offset }) => (
              <div
                key={title}
                className={`p-8 rounded-3xl flex items-center gap-6 shadow-sm transition-all group ${offset}`}
                style={{ backgroundColor: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                onMouseEnter={e => e.currentTarget.style.borderColor = "rgba(37,99,235,0.4)"}
                onMouseLeave={e => e.currentTarget.style.borderColor = "var(--color-border)"}
              >
                <div
                  className="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl"
                  style={{ backgroundColor: "rgba(37,99,235,0.07)" }}
                >
                  {emoji}
                </div>
                <div>
                  <h4 className="text-xl font-bold mb-2" style={{ color: "var(--color-heading)" }}>{title}</h4>
                  <p className="font-medium" style={{ color: "var(--color-muted)" }}>{desc}</p>
                </div>
              </div>
            ))}
          </motion.div>
        </div>

        {/* STATS */}
        <div className="grid md:grid-cols-3 gap-8">
          {[
            { number: "500K+", label: "Resumes Optimized" },
            { number: "98%",   label: "ATS Pass Rate" },
            { number: "3x",    label: "More Interviews" },
          ].map((stat, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.2 }}
              className="text-center p-10 rounded-3xl"
              style={{
                backgroundColor: "rgba(37,99,235,0.04)",
                border: "1px solid rgba(37,99,235,0.12)",
              }}
            >
              <h3 className="text-5xl font-extrabold font-display mb-2" style={{ color: "var(--color-accent)" }}>{stat.number}</h3>
              <p className="font-bold uppercase tracking-wider" style={{ color: "var(--color-body)" }}>{stat.label}</p>
            </motion.div>
          ))}
        </div>

      </section>
    </div>
  );
};

export default About;