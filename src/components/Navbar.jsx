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
  const [pos, setPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const move = (e) => {
      setPos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener("mousemove", move);
    return () => window.removeEventListener("mousemove", move);
  }, []);

  return (
    <header className="sticky top-0 z-50">

      {/* SOFT CURSOR LIGHT */}
      <motion.div
        className="pointer-events-none fixed top-0 left-0 z-0"
        animate={{ x: pos.x - 100, y: pos.y - 100 }}
      >
        <div className="w-[200px] h-[200px] bg-white/[0.04] blur-3xl rounded-full" />
      </motion.div>

      {/* GLASS NAVBAR */}
      <div className="backdrop-blur-2xl bg-black/40 border-b border-white/[0.06] shadow-[0_8px_30px_rgba(0,0,0,0.6)]">

        <div className="px-6 md:px-16 h-16 flex items-center justify-between">

          {/* LOGO */}
          <Link to="/" className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-lg bg-white text-black flex items-center justify-center font-semibold">
              R
            </div>
            <span className="text-lg font-medium tracking-tight">
              ROZGAR <span className="text-black-400">24x7</span>
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
                  className={`relative text-sm transition ${
                    isActive
                      ? "text-white"
                      : "text-black-400 hover:text-white"
                  }`}
                >
                  {link.name}

                  {/* ACTIVE DOT */}
                  {isActive && (
                    <motion.span
                      layoutId="navActive"
                      className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-1 h-1 bg-white rounded-full"
                    />
                  )}
                </Link>
              );
            })}

            {/* CTA */}
            <div className="flex items-center gap-3 ml-6">

              <Link
                to="/login"
                className="px-4 py-2 rounded-lg text-sm border border-white/[0.08] bg-white/[0.02] text-white hover:bg-white/[0.05] transition"
              >
                Sign In
              </Link>

              <Link
                to="/analyze"
                className="px-5 py-2 rounded-lg text-sm bg-white text-black font-medium hover:scale-105 transition"
              >
                Get Started
              </Link>

            </div>
          </nav>

          {/* MOBILE BTN */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden text-white"
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
      </div>

      {/* ================= MOBILE ================= */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="md:hidden backdrop-blur-2xl bg-black/80 border-t border-white/[0.06]"
          >
            <div className="px-6 py-6 flex flex-col gap-4">

              {navLinks.map((link) => (
                <Link
                  key={link.name}
                  to={link.to}
                  onClick={() => setMenuOpen(false)}
                  className="text-gray-400 hover:text-white transition"
                >
                  {link.name}
                </Link>
              ))}

              <div className="flex flex-col gap-3 pt-4 border-t border-white/[0.06]">

                <Link
                  to="/login"
                  className="text-center px-5 py-2 border border-white/[0.08] rounded-lg bg-white/[0.02]"
                >
                  Sign In
                </Link>

                <Link
                  to="/analyze"
                  className="text-center px-5 py-2 rounded-lg bg-white text-black"
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