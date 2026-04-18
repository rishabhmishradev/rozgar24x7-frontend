import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";

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
      className="w-full px-6 md:px-16 py-16 bg-[#0a0a0a] border-t border-white/[0.08] relative overflow-hidden text-white"
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true }}
    >

      {/* 🔥 SOFT CURSOR */}
      <motion.div
        className="pointer-events-none absolute top-0 left-0"
        animate={{ x: pos.x - 120, y: pos.y - 120 }}
      >
        <div className="w-[240px] h-[240px] bg-white/[0.04] blur-3xl rounded-full" />
      </motion.div>

      {/* 🌫️ NOISE */}
      <div className="absolute inset-0 opacity-[0.03] bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" />

      <div className="relative z-10 flex flex-wrap justify-between gap-12">

        {/* BRAND */}
        <motion.div className="max-w-xs" variants={fadeUp} custom={0}>
          <h2 className="text-lg font-semibold">
            ROZGAR <span className="text-white/60">24x7</span>
          </h2>

          <p className="text-sm text-white/60 mt-3">
            Helping job seekers optimize resumes using AI and land better opportunities.
          </p>
        </motion.div>

        {/* PRODUCT */}
        <motion.div variants={fadeUp} custom={1}>
          <p className="font-medium mb-3">Product</p>
          <ul className="space-y-2 text-sm text-white/60">
            <li><a href="/features" className="hover:text-white transition">Features</a></li>
            <li><a href="/templates" className="hover:text-white transition">Templates</a></li>
            <li><a href="/contact" className="hover:text-white transition">Contact</a></li>
          </ul>
        </motion.div>

        {/* COMPANY */}
        <motion.div variants={fadeUp} custom={2}>
          <p className="font-medium mb-3">Company</p>
          <ul className="space-y-2 text-sm text-white/60">
            <li><a href="/about" className="hover:text-white transition">About</a></li>
            <li><a href="/contact" className="hover:text-white transition">Support</a></li>
          </ul>
        </motion.div>

        {/* NEWSLETTER */}
        <motion.div className="max-w-xs" variants={fadeUp} custom={3}>
          <p className="font-medium">Stay Updated</p>

          <p className="mt-3 text-sm text-white/60">
            Get resume tips and updates.
          </p>

          <div className="flex items-center mt-4">
            <input
              type="email"
              placeholder="Your email"
              className="bg-white/[0.06] border border-white/[0.12] h-10 px-3 rounded-l-lg outline-none w-full text-white placeholder-white/40"
            />
            <button className="bg-white text-black h-10 px-4 rounded-r-lg font-medium hover:scale-[1.03] transition">
              →
            </button>
          </div>
        </motion.div>

      </div>

      {/* DIVIDER */}
      <motion.hr
        className="border-white/[0.08] mt-12"
        variants={fadeUp}
        custom={4}
      />

      {/* BOTTOM */}
      <motion.div
        className="flex flex-col md:flex-row justify-between items-center pt-6 text-sm text-white/50"
        variants={fadeUp}
        custom={5}
      >
        <p>
          © {new Date().getFullYear()} ROZGAR 24x7. All rights reserved.
        </p>

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