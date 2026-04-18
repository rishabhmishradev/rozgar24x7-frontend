import { Link, useLocation } from "react-router-dom";
import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

const navLinks = [
  { name: "Home", to: "/" },
  { name: "Features", to: "/features" },
  { name: "Templates", to: "/templates" },
  { name: "About", to: "/about" },
  { name: "Contact", to: "/contact" },
];

const Navbar = () => {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header className="fixed top-4 left-0 w-full z-50 flex justify-center px-4">

      <div
        className={`flex items-center justify-between w-full max-w-6xl px-6 h-14 rounded-xl border transition ${
          scrolled
            ? "bg-[#0a0a0a]/80 backdrop-blur-2xl border-white/[0.08] shadow-[0_10px_40px_rgba(0,0,0,0.6)]"
            : "bg-white/[0.03] backdrop-blur-xl border-white/[0.06]"
        }`}
      >

        {/* LOGO */}
        <Link to="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-white text-black flex items-center justify-center font-semibold text-sm">
            R
          </div>
          <span className="text-sm text-white font-medium tracking-tight">
            ROZGAR <span className="text-white/60">24x7</span>
          </span>
        </Link>

        {/* NAV */}
        <nav className="hidden md:flex items-center gap-6 relative">

          {navLinks.map((link) => {
            const isActive = location.pathname === link.to;

            return (
              <Link
                key={link.name}
                to={link.to}
                className={`relative px-3 py-1.5 text-sm transition ${
                  isActive
                    ? "text-white"
                    : "text-white/60 hover:text-white"
                }`}
              >
                {isActive && (
                  <motion.div
                    layoutId="nav-pill"
                    className="absolute inset-0 bg-white/[0.08] rounded-md border border-white/[0.1]"
                  />
                )}

                <span className="relative z-10">{link.name}</span>
              </Link>
            );
          })}

        </nav>

        {/* CTA */}
        <div className="hidden md:flex items-center gap-3">

          <Link
            to="/login"
            className="px-4 py-1.5 text-sm text-white/70 hover:text-white transition"
          >
            Sign In
          </Link>

          {/* 🔥 SUBTLE COLOR BUTTON */}
          <Link
            to="/analyze"
            className="px-4 py-1.5 rounded-lg text-sm font-medium text-white 
            bg-indigo-500/80 hover:bg-indigo-500 transition shadow-[0_0_20px_rgba(99,102,241,0.25)]"
          >
            Get Started
          </Link>

        </div>

        {/* MOBILE */}
        <button onClick={() => setMenuOpen(!menuOpen)} className="md:hidden">
          ☰
        </button>

      </div>

      {/* MOBILE MENU */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="absolute top-16 w-[95%] bg-[#0a0a0a]/95 backdrop-blur-2xl border border-white/[0.08] rounded-xl p-6 md:hidden"
          >
            <div className="flex flex-col gap-4">

              {navLinks.map((link) => (
                <Link
                  key={link.name}
                  to={link.to}
                  onClick={() => setMenuOpen(false)}
                  className="text-white/70 hover:text-white"
                >
                  {link.name}
                </Link>
              ))}

              <div className="pt-4 border-t border-white/[0.08] flex flex-col gap-3">
                <Link to="/login" className="text-center py-2 border border-white/[0.1] rounded-lg">
                  Sign In
                </Link>

                <Link to="/analyze" className="text-center py-2 rounded-lg bg-indigo-500 text-white">
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