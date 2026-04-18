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
            ? "bg-white/80 backdrop-blur-2xl border-black/[0.08] shadow-[0_10px_40px_rgba(0,0,0,0.1)]"
            : "bg-black/[0.02] backdrop-blur-xl border-black/[0.06]"
        }`}
      >

        {/* LOGO */}
        <Link to="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-black text-white flex items-center justify-center font-semibold text-sm">
            R
          </div>
          <span className="text-sm text-black font-medium tracking-tight">
            ROZGAR <span className="text-black/60">24x7</span>
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
                    ? "text-black"
                    : "text-black/60 hover:text-black"
                }`}
              >
                {isActive && (
                  <motion.div
                    layoutId="nav-pill"
                    className="absolute inset-0 bg-black/[0.06] rounded-md border border-black/[0.08]"
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
            className="px-4 py-1.5 text-sm text-black/70 hover:text-black transition"
          >
            Sign In
          </Link>

          {/* 🔥 PREMIUM BUTTON */}
          <Link
            to="/analyze"
            className="px-4 py-1.5 rounded-lg text-sm font-medium text-white 
            bg-black hover:bg-gray-800 transition shadow-[0_10px_25px_rgba(0,0,0,0.15)]"
          >
            Get Started
          </Link>

        </div>

        {/* MOBILE */}
        <button 
          onClick={() => setMenuOpen(!menuOpen)} 
          className="md:hidden text-black text-xl"
        >
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
            className="absolute top-16 w-[95%] bg-white/95 backdrop-blur-2xl border border-black/[0.08] rounded-xl p-6 md:hidden shadow-lg"
          >
            <div className="flex flex-col gap-4">

              {navLinks.map((link) => (
                <Link
                  key={link.name}
                  to={link.to}
                  onClick={() => setMenuOpen(false)}
                  className="text-black/70 hover:text-black"
                >
                  {link.name}
                </Link>
              ))}

              <div className="pt-4 border-t border-black/[0.08] flex flex-col gap-3">
                <Link to="/login" className="text-center py-2 border border-black/[0.1] rounded-lg">
                  Sign In
                </Link>

                <Link to="/analyze" className="text-center py-2 rounded-lg bg-black text-white">
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