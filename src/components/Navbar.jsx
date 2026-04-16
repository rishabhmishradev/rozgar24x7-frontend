import { Link, useLocation } from "react-router-dom";
import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const navLinks = [
  { name: "Features", to: "/features" },
  { name: "Templates", to: "/templates" },
  { name: "About", to: "/about" },
  { name: "Contact", to: "/contact" },
];

const Navbar = () => {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 backdrop-blur-lg bg-white/30 border-b border-white/20">

      <div className="px-6 md:px-16 lg:px-24 xl:px-32 h-16 flex items-center justify-between">

        {/* LOGO */}
        <Link to="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[#2C4A52] flex items-center justify-center text-white font-bold">
            R
          </div>
          <span className="text-lg md:text-xl font-semibold tracking-tight">
            ROZGAR <span className="text-[#2C4A52]">24x7</span>
          </span>
        </Link>

        {/* ================= DESKTOP ================= */}
        <nav className="hidden md:flex items-center gap-8">

          {navLinks.map((link) => {
            const isActive = location.pathname === link.to;
            return (
              <Link
                key={link.name}
                to={link.to}
                className={`relative text-sm font-medium transition ${
                  isActive
                    ? "text-[#2C4A52]"
                    : "text-gray-700 hover:text-black"
                }`}
              >
                {link.name}

                {isActive && (
                  <motion.span
                    layoutId="navActive"
                    className="absolute -bottom-1 left-0 h-[2px] w-full bg-[#2C4A52] rounded-full"
                  />
                )}
              </Link>
            );
          })}

          {/* CTA */}
          <div className="flex items-center gap-3 ml-6">

            <Link
              to="/login"
              className="px-4 py-2 rounded-lg text-sm border border-gray-300 bg-white/40 backdrop-blur-sm hover:bg-white/60 transition"
            >
              Sign In
            </Link>

            <Link
              to="/analyze"
              className="px-5 py-2 rounded-lg text-sm text-white bg-[#2C4A52] hover:opacity-90 transition"
            >
              Get Started
            </Link>

          </div>
        </nav>

        {/* ================= MOBILE BTN ================= */}
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="md:hidden text-gray-800"
        >
          <svg
            className="w-7 h-7"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            viewBox="0 0 24 24"
          >
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      </div>

      {/* ================= MOBILE MENU ================= */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.25 }}
            className="md:hidden backdrop-blur-lg bg-white/40 border-t border-white/20 shadow-xl"
          >
            <div className="px-6 py-6 flex flex-col gap-4">

              {navLinks.map((link) => (
                <Link
                  key={link.name}
                  to={link.to}
                  onClick={() => setMenuOpen(false)}
                  className="text-gray-700 font-medium hover:text-[#2C4A52] transition"
                >
                  {link.name}
                </Link>
              ))}

              {/* CTA */}
              <div className="flex flex-col gap-3 pt-4 border-t border-gray-200">

                <Link
                  to="/login"
                  className="text-center px-5 py-2 border rounded-lg bg-white/50"
                >
                  Sign In
                </Link>

                <Link
                  to="/analyze"
                  className="text-center px-5 py-2 rounded-lg text-white bg-[#2C4A52]"
                >
                  Get Started
                </Link>

              </div>

            </div>
          </motion.div>
        )}
      </AnimatePresence>

    </header>
  );
};

export default Navbar;