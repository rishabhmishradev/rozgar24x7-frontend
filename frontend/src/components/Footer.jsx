import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import logo from "../assets/logo.PNG";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1 },
  }),
};

const Footer = () => {
  const [pos, setPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const move = (e) => setPos({ x: e.clientX, y: e.clientY });
    window.addEventListener("mousemove", move);
    return () => window.removeEventListener("mousemove", move);
  }, []);

  return (
    <motion.footer
      className="w-full px-6 md:px-16 py-16 relative overflow-hidden text-white"
      style={{ backgroundColor: "#0F172A", borderTop: "1px solid #1E293B" }}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true }}
    >

      {/* SOFT CURSOR GLOW */}
      <motion.div
        className="pointer-events-none absolute top-0 left-0"
        animate={{ x: pos.x - 120, y: pos.y - 120 }}
      >
        <div className="w-[240px] h-[240px] rounded-full blur-3xl" style={{ backgroundColor: "rgba(37,99,235,0.05)" }} />
      </motion.div>

      {/* NOISE TEXTURE */}
      <div className="absolute inset-0 opacity-[0.03] bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" />

      <div className="relative z-10 flex flex-wrap justify-between gap-12">

        {/* BRAND */}
        <motion.div className="max-w-xs" variants={fadeUp} custom={0}>
          <div className="flex items-center gap-2 mb-4">
            <img src={logo} alt="Rozgar24x7" className="h-8 w-auto object-contain rounded-[25%]" />
          </div>
          <p className="text-sm text-slate-400 mt-3">
            Helping job seekers optimize resumes using AI and land better opportunities.
          </p>
        </motion.div>

        {/* PRODUCT */}
        <motion.div variants={fadeUp} custom={1}>
          <p className="font-medium mb-3 text-white">Product</p>
          <ul className="space-y-2 text-sm text-slate-400">
            <li><a href="/features" className="hover:text-white transition">Features</a></li>
            <li><a href="/templates" className="hover:text-white transition">Templates</a></li>
            <li><a href="/contact" className="hover:text-white transition">Contact</a></li>
          </ul>
        </motion.div>

        {/* COMPANY */}
        <motion.div variants={fadeUp} custom={2}>
          <p className="font-medium mb-3 text-white">Company</p>
          <ul className="space-y-2 text-sm text-slate-400">
            <li><a href="/about" className="hover:text-white transition">About</a></li>
            <li><a href="/contact" className="hover:text-white transition">Support</a></li>
          </ul>
        </motion.div>

        {/* NEWSLETTER */}
        <motion.div className="max-w-xs" variants={fadeUp} custom={3}>
          <p className="font-medium text-white">Stay Updated</p>
          <p className="mt-3 text-sm text-slate-400">
            Get resume tips and updates.
          </p>
          <div className="flex items-center mt-4">
            <input
              type="email"
              placeholder="Your email"
              className="h-10 px-3 rounded-l-lg outline-none w-full text-white placeholder-slate-500 text-sm"
              style={{ backgroundColor: "rgba(255,255,255,0.06)", border: "1px solid #334155" }}
            />
            <button
              className="h-10 px-4 rounded-r-lg font-medium hover:scale-[1.03] transition text-white text-sm"
              style={{ backgroundColor: "var(--color-accent)" }}
              onMouseEnter={e => e.currentTarget.style.backgroundColor = "var(--color-cta-hover)"}
              onMouseLeave={e => e.currentTarget.style.backgroundColor = "var(--color-accent)"}
            >
              →
            </button>
          </div>
        </motion.div>

      </div>

      {/* DIVIDER */}
      <motion.hr
        className="mt-12"
        style={{ borderColor: "#1E293B" }}
        variants={fadeUp}
        custom={4}
      />

      {/* BOTTOM */}
      <motion.div
        className="flex flex-col md:flex-row justify-between items-center pt-6 text-sm text-slate-500"
        variants={fadeUp}
        custom={5}
      >
        <p>© {new Date().getFullYear()} ROZGAR 24x7. All rights reserved.</p>
        <div className="flex gap-5 mt-3 md:mt-0">
          <a href="/about" className="hover:text-white transition">About</a>
          <a href="/features" className="hover:text-white transition">Features</a>
          <a href="/templates" className="hover:text-white transition">Templates</a>
        </div>
      </motion.div>

    </motion.footer>
  );
};

export default Footer;