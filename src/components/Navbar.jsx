import { Link, useLocation } from "react-router-dom";
import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTheme } from "./ThemeContext";

const navLinks = [
  { name: "Home", to: "/" },
  { name: "Features", to: "/#features-section" },
  { name: "Pricing", to: "/pricing" },
];

const Navbar = () => {
  const location = useLocation();
  const { dark, toggleTheme } = useTheme();

  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [activeHash, setActiveHash] = useState("");

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 30);
      
      if (location.pathname === "/") {
        const featuresEl = document.getElementById("features-section");
        if (featuresEl) {
          const rect = featuresEl.getBoundingClientRect();
          if (rect.top <= window.innerHeight / 2 && rect.bottom >= window.innerHeight / 2) {
            setActiveHash("features-section");
          } else {
            setActiveHash("");
          }
        }
      } else {
        setActiveHash("");
      }
    };
    window.addEventListener("scroll", handleScroll);
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, [location.pathname]);

  const SunIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5 text-amber-500">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />
    </svg>
  );

  const MoonIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5 text-slate-700">
      <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" />
    </svg>
  );

  return (
    <>
      <header className={`sticky top-0 w-full z-50 transition-all duration-300 border-b ${scrolled ? "bg-white/90 dark:bg-black/90 backdrop-blur-md shadow-sm border-slate-200 dark:border-slate-800" : "bg-white/50 dark:bg-black/50 backdrop-blur-sm border-slate-200 dark:border-slate-800"}`}>
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between relative">

          {/* LOGO */}
          <Link to="/" className="flex items-center">
            <span className="text-2xl text-slate-900 dark:text-white font-extrabold tracking-tight">
              rozgar<span className="text-[#00b14f]">.</span>
            </span>
          </Link>

          {/* DESKTOP NAV (Centered) */}
          <nav className="hidden md:flex items-center gap-10 absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
            {navLinks.map((link) => {
              const isHashLink = link.to.includes("#");
              const hash = isHashLink ? link.to.split("#")[1] : "";
              
              let isActive = false;
              if (location.pathname === "/") {
                if (isHashLink) {
                  isActive = activeHash === hash;
                } else if (link.to === "/") {
                  isActive = activeHash === "";
                }
              } else {
                isActive = location.pathname === link.to;
              }

              const handleClick = (e) => {
                if (isHashLink && location.pathname === "/") {
                  e.preventDefault();
                  document.getElementById(hash)?.scrollIntoView({ behavior: "smooth" });
                } else if (link.to === "/" && location.pathname === "/") {
                  e.preventDefault();
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }
              };

              return (
                <Link
                  key={link.name}
                  to={link.to}
                  onClick={handleClick}
                  className={`text-[15px] font-medium transition-colors ${isActive
                    ? "text-slate-900 dark:text-white"
                    : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                >
                  {link.name}
                </Link>
              );
            })}
          </nav>

          {/* RIGHT ACTIONS */}
          <div className="hidden md:flex items-center gap-4">
            {/* 🌗 TOGGLE */}
            <button
              onClick={toggleTheme}
              aria-label="Toggle Dark Mode"
              className={`w-14 h-7 flex items-center rounded-full p-1 cursor-pointer transition-colors duration-300 border focus:outline-none
              ${dark ? "bg-slate-800 border-slate-700" : "bg-slate-100 border-slate-300"}`}
            >
              <div
                className={`w-5 h-5 rounded-full bg-white shadow-sm flex items-center justify-center transition-transform duration-300
                ${dark ? "translate-x-7" : "translate-x-0"}`}
              >
                {dark ? <MoonIcon /> : <SunIcon />}
              </div>
            </button>

            {/* 🔥 BUTTONS */}
            <Link to="/analyze" className="px-5 py-2.5 rounded-full bg-[#00b14f] hover:bg-[#009641] text-white text-[15px] font-semibold transition-colors">
              Get started
            </Link>

            <Link to="/login" className="px-5 py-2.5 rounded-full border border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800 text-slate-700 dark:text-white text-[15px] font-medium transition-colors">
              Login
            </Link>
          </div>

          {/* MOBILE BURGER */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden text-slate-900 dark:text-white p-2"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-6 h-6">
              <path strokeLinecap="round" strokeLinejoin="round" d={menuOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16m-7 6h7"} />
            </svg>
          </button>
        </div>

        {/* MOBILE MENU */}
        <AnimatePresence>
          {menuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="md:hidden bg-white dark:bg-[#0a0a0a] border-b border-slate-100 dark:border-slate-800 overflow-hidden"
            >
              <div className="px-6 py-4 flex flex-col gap-4">

                {/* 🌗 TOGGLE MOBILE */}
                <div className="flex justify-between items-center py-2">
                  <span className="text-[15px] font-medium text-slate-700 dark:text-slate-300">Theme</span>
                  <button onClick={toggleTheme} className={`w-12 h-6 flex items-center rounded-full p-1 border ${dark ? "bg-slate-800 border-slate-700" : "bg-slate-100 border-slate-300"}`}>
                    <div className={`w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-300 ${dark ? "translate-x-6" : "translate-x-0"}`} />
                  </button>
                </div>

                {navLinks.map((link) => {
                  const isHashLink = link.to.includes("#");
                  const hash = isHashLink ? link.to.split("#")[1] : "";
                  
                  const handleClick = (e) => {
                    if (isHashLink && location.pathname === "/") {
                      e.preventDefault();
                      document.getElementById(hash)?.scrollIntoView({ behavior: "smooth" });
                    } else if (link.to === "/" && location.pathname === "/") {
                      e.preventDefault();
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }
                    setMenuOpen(false);
                  };

                  return (
                    <Link
                      key={link.name}
                      to={link.to}
                      onClick={handleClick}
                      className="py-2 text-[15px] text-slate-600 dark:text-slate-300 font-medium"
                    >
                      {link.name}
                    </Link>
                  );
                })}

                <div className="pt-4 mt-2 border-t border-slate-100 dark:border-slate-800 flex flex-col gap-3">
                  <Link to="/analyze" onClick={() => setMenuOpen(false)} className="text-center py-3 rounded-full bg-[#00b14f] text-white font-semibold">
                    Get started
                  </Link>
                  <Link to="/login" onClick={() => setMenuOpen(false)} className="text-center py-3 rounded-full border border-slate-300 dark:border-slate-700 font-medium text-slate-700 dark:text-white">
                    Login
                  </Link>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </header>
    </>
  );
};

export default Navbar;