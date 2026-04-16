import React from "react";
import { motion } from "framer-motion";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.12 },
  }),
};

const Footer = () => {
  return (
    <motion.footer
      className="w-full text-gray-700 px-6 md:px-16 lg:px-24 xl:px-32 py-12 
      bg-white/30 backdrop-blur-lg border-t border-white/20"
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true }}
    >

      <div className="flex flex-wrap justify-between gap-10">

        {/* BRAND */}
        <motion.div className="max-w-xs" variants={fadeUp} custom={0}>
          <h2 className="text-lg font-semibold mb-3">
            ROZGAR <span className="text-[#2C4A52]">24x7</span>
          </h2>

          <p className="text-sm">
            Helping job seekers optimize resumes using AI and land better opportunities faster.
          </p>
        </motion.div>

        {/* PRODUCT */}
        <motion.div variants={fadeUp} custom={1}>
          <p className="text-md font-semibold">Product</p>
          <ul className="mt-3 space-y-2 text-sm">
            <li>
              <a href="/features" className="hover:text-[#2C4A52] transition">
                Features
              </a>
            </li>
            <li>
              <a href="/templates" className="hover:text-[#2C4A52] transition">
                Templates
              </a>
            </li>
            <li>
              <a href="/contact" className="hover:text-[#2C4A52] transition">
                Contact
              </a>
            </li>
          </ul>
        </motion.div>

        {/* COMPANY */}
        <motion.div variants={fadeUp} custom={2}>
          <p className="text-md font-semibold">Company</p>
          <ul className="mt-3 space-y-2 text-sm">
            <li>
              <a href="/about" className="hover:text-[#2C4A52] transition">
                About
              </a>
            </li>
            <li>
              <a href="/contact" className="hover:text-[#2C4A52] transition">
                Support
              </a>
            </li>
          </ul>
        </motion.div>

        {/* NEWSLETTER */}
        <motion.div className="max-w-xs" variants={fadeUp} custom={3}>
          <p className="text-md font-semibold">
            Stay Updated
          </p>

          <p className="mt-3 text-sm">
            Get resume tips and updates.
          </p>

          <div className="flex items-center mt-4">
            <input
              type="email"
              placeholder="Your email"
              className="bg-white/60 border border-gray-300 h-10 px-3 rounded-l-lg outline-none w-full"
            />
            <button className="bg-[#2C4A52] h-10 px-4 text-white rounded-r-lg hover:opacity-90 transition">
              →
            </button>
          </div>
        </motion.div>

      </div>

      {/* DIVIDER */}
      <motion.hr
        className="border-white/20 mt-10"
        variants={fadeUp}
        custom={4}
      />

      {/* BOTTOM */}
      <motion.div
        className="flex flex-col md:flex-row justify-between items-center pt-5 text-sm"
        variants={fadeUp}
        custom={5}
      >
        <p>
          © {new Date().getFullYear()} ROZGAR 24x7. All rights reserved.
        </p>

        <div className="flex gap-4 mt-3 md:mt-0">
          <a href="/about" className="hover:text-[#2C4A52] transition">
            About
          </a>
          <a href="/features" className="hover:text-[#2C4A52] transition">
            Features
          </a>
          <a href="/templates" className="hover:text-[#2C4A52] transition">
            Templates
          </a>
        </div>
      </motion.div>

    </motion.footer>
  );
};

export default Footer;