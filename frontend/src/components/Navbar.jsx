import { Link, useLocation } from "react-router-dom";
import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTheme } from "./ThemeContext";
import logo from "../assets/logo.PNG";

const navLinks = [
  { name: "Home", to: "/" },
  { name: "Features", to: "/#features-section" },
  { name: "ATS Checker", to: "/ats-analysis" },
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

  const ThemeToggle = () => (
    <button
      onClick={toggleTheme}
      aria-label="Toggle Dark Mode"
      className="relative w-9 h-9 flex items-center justify-center rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-section)] hover:bg-[var(--color-border)] transition-all duration-200 overflow-hidden"
    >
      <AnimatePresence mode="wait" initial={false}>
        {dark ? (
          <motion.svg
            key="moon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="w-4 h-4 text-[var(--color-body)]"
            initial={{ rotate: -90, opacity: 0, scale: 0.6 }}
            animate={{ rotate: 0, opacity: 1, scale: 1 }}
            exit={{ rotate: 90, opacity: 0, scale: 0.6 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </motion.svg>
        ) : (
          <motion.svg
            key="sun"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="w-4 h-4 text-amber-500"
            initial={{ rotate: 90, opacity: 0, scale: 0.6 }}
            animate={{ rotate: 0, opacity: 1, scale: 1 }}
            exit={{ rotate: -90, opacity: 0, scale: 0.6 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            <circle cx="12" cy="12" r="4" />
            <line x1="12" y1="2" x2="12" y2="5" />
            <line x1="12" y1="19" x2="12" y2="22" />
            <line x1="4.22" y1="4.22" x2="6.34" y2="6.34" />
            <line x1="17.66" y1="17.66" x2="19.78" y2="19.78" />
            <line x1="2" y1="12" x2="5" y2="12" />
            <line x1="19" y1="12" x2="22" y2="12" />
            <line x1="4.22" y1="19.78" x2="6.34" y2="17.66" />
            <line x1="17.66" y1="6.34" x2="19.78" y2="4.22" />
          </motion.svg>
        )}
      </AnimatePresence>
    </button>
  );

  return (
    <>
      <header
        className={`sticky top-0 w-full z-50 transition-all duration-300 border-b ${
          scrolled
            ? "backdrop-blur-md shadow-sm"
            : "backdrop-blur-sm"
        }`}
        style={{
          backgroundColor: scrolled
            ? `color-mix(in srgb, var(--color-bg) 92%, transparent)`
            : `color-mix(in srgb, var(--color-bg) 70%, transparent)`,
          borderColor: "var(--color-border)",
        }}
      >
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between relative">

          {/* LOGO */}
          <Link to="/" className="flex items-center gap-2">
            <img src={logo} alt="Rozgar24x7" className="h-9 w-auto object-contain rounded-[25%]" />
          </Link>

          {/* DESKTOP NAV */}
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
                  className="text-[15px] font-medium transition-colors"
                  style={{
                    color: isActive ? "var(--color-heading)" : "var(--color-muted)",
                  }}
                  onMouseEnter={e => e.target.style.color = "var(--color-heading)"}
                  onMouseLeave={e => e.target.style.color = isActive ? "var(--color-heading)" : "var(--color-muted)"}
                >
                  {link.name}
                </Link>
              );
            })}
          </nav>

          {/* RIGHT ACTIONS */}
          <div className="hidden md:flex items-center gap-4">
            <ThemeToggle />

            {/* Sign up — secondary outline */}
            <Link
              to="/analyze"
              className="px-5 py-2.5 rounded-full text-[15px] font-bold transition-all border-2"
              style={{
                borderColor: "var(--color-accent)",
                color: "var(--color-accent)",
              }}
              onMouseEnter={e => {
                e.currentTarget.style.backgroundColor = "var(--color-accent)";
                e.currentTarget.style.color = "#fff";
              }}
              onMouseLeave={e => {
                e.currentTarget.style.backgroundColor = "transparent";
                e.currentTarget.style.color = "var(--color-accent)";
              }}
            >
              Sign up
            </Link>

            {/* Login */}
            <Link
              to="/login"
              className="px-5 py-2.5 rounded-full text-[15px] font-medium transition-all"
              style={{
                border: "1px solid var(--color-border)",
                color: "var(--color-body)",
              }}
              onMouseEnter={e => e.currentTarget.style.backgroundColor = "var(--color-bg-section)"}
              onMouseLeave={e => e.currentTarget.style.backgroundColor = "transparent"}
            >
              Login
            </Link>
          </div>

          {/* MOBILE BURGER */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden p-2"
            style={{ color: "var(--color-heading)" }}
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
              className="md:hidden border-b overflow-hidden"
              style={{
                backgroundColor: "var(--color-bg)",
                borderColor: "var(--color-border)",
              }}
            >
              <div className="px-6 py-4 flex flex-col gap-4">

                {/* THEME TOGGLE MOBILE */}
                <div className="flex justify-between items-center py-2">
                  <span className="text-[15px] font-medium" style={{ color: "var(--color-body)" }}>Theme</span>
                  <ThemeToggle />
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
                      className="py-2 text-[15px] font-medium"
                      style={{ color: "var(--color-muted)" }}
                    >
                      {link.name}
                    </Link>
                  );
                })}

                <div className="pt-4 mt-2 flex flex-col gap-3" style={{ borderTop: "1px solid var(--color-border)" }}>
                  <Link
                    to="/analyze"
                    onClick={() => setMenuOpen(false)}
                    className="text-center py-3 rounded-full border-2 font-bold"
                    style={{ borderColor: "var(--color-accent)", color: "var(--color-accent)" }}
                  >
                    Sign up
                  </Link>
                  <Link
                    to="/login"
                    onClick={() => setMenuOpen(false)}
                    className="text-center py-3 rounded-full font-medium"
                    style={{ border: "1px solid var(--color-border)", color: "var(--color-body)" }}
                  >
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