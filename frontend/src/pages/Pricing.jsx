import React, { useState } from "react";
import { motion } from "framer-motion";

const CheckIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" />
  </svg>
);

const FeatureItem = ({ text, bold }) => (
  <li className="flex items-start gap-3">
    <div className="mt-0.5" style={{ color: "var(--color-accent)" }}>
      <CheckIcon />
    </div>
    <span
      className="text-[15px] font-medium"
      style={{ color: bold ? "var(--color-heading)" : "var(--color-body)", fontWeight: bold ? 700 : 500 }}
    >
      {text}
    </span>
  </li>
);

const BuyButton = ({ onClick }) => (
  <button
    className="w-full py-4 rounded-xl text-white font-bold text-lg transition-all hover:scale-[1.02] hover:-translate-y-0.5"
    style={{
      backgroundColor: "var(--color-cta-bg)",
      boxShadow: "0 10px 30px -8px rgba(37,99,235,0.35)",
    }}
    onMouseEnter={e => e.currentTarget.style.backgroundColor = "var(--color-cta-hover)"}
    onMouseLeave={e => e.currentTarget.style.backgroundColor = "var(--color-cta-bg)"}
    onClick={onClick}
  >
    Buy Now
  </button>
);

const Pricing = () => {
  const [resumeCount, setResumeCount] = useState(2);

  const increment = () => setResumeCount((prev) => prev + 1);
  const decrement = () => setResumeCount((prev) => (prev > 1 ? prev - 1 : 1));

  return (
    <div className="min-h-screen pt-12 md:pt-16 pb-24 relative overflow-hidden" style={{ backgroundColor: "var(--color-bg)" }}>

      {/* Soft background glow */}
      <div
        className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[600px] rounded-full blur-[120px] -z-10"
        style={{ backgroundColor: "rgba(37,99,235,0.05)" }}
      />

      <div className="max-w-7xl mx-auto px-6">

        {/* Header */}
        <div className="text-center mb-16">
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-semibold mb-6"
            style={{ backgroundColor: "rgba(37,99,235,0.08)", color: "var(--color-accent)" }}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
              <path fillRule="evenodd" d="M9 4.5a.75.75 0 0 1 .721.544l.813 2.846a3.75 3.75 0 0 0 2.576 2.576l2.846.813a.75.75 0 0 1 0 1.442l-2.846.813a3.75 3.75 0 0 0-2.576 2.576l-.813 2.846a.75.75 0 0 1-1.442 0l-.813-2.846a3.75 3.75 0 0 0-2.576-2.576l-2.846-.813a.75.75 0 0 1 0-1.442l2.846-.813A3.75 3.75 0 0 0 7.466 7.89l.813-2.846A.75.75 0 0 1 9 4.5Z" clipRule="evenodd" />
            </svg>
            Simple, transparent pricing
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-5xl md:text-6xl font-extrabold mb-4 tracking-tight"
            style={{ color: "var(--color-heading)" }}
          >
            Invest in your career.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-lg font-medium"
            style={{ color: "var(--color-muted)" }}
          >
            Join professionals who landed their dream jobs using ROZGAR 24X7.
          </motion.p>
        </div>

        {/* Pricing Cards */}
        <div className="flex flex-col lg:flex-row justify-center items-stretch gap-8 mt-12">

          {/* PRO CARD */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex-1 w-full max-w-md mx-auto rounded-[2rem] p-8 shadow-sm flex flex-col"
            style={{ backgroundColor: "var(--color-bg)", border: "1px solid var(--color-border)" }}
          >
            <div className="mb-6">
              <h2 className="text-2xl font-bold mb-1" style={{ color: "var(--color-heading)" }}>Pro</h2>
              <p className="text-sm font-medium mb-4" style={{ color: "var(--color-muted)" }}>For serious job seekers</p>

              <span className="inline-block px-2.5 py-1 text-xs font-bold rounded mb-4"
                style={{ backgroundColor: "rgba(37,99,235,0.1)", color: "var(--color-accent)" }}>
                SAVE 67%
              </span>

              <div className="flex items-end gap-2 mb-1">
                <span className="text-5xl font-extrabold tracking-tighter font-display" style={{ color: "var(--color-heading)" }}>₹500</span>
                <span className="text-xl font-bold text-red-500 line-through mb-1">₹1500</span>
              </div>
              <p className="text-sm font-medium" style={{ color: "var(--color-muted)" }}>Limited time offer</p>
            </div>

            <div className="flex-grow">
              <ul className="space-y-4 mb-8">
                {["Unlimited ATS score analysis", "ATS-optimized resume formats", "Early bird offers access", "Help desk access"].map((f) => (
                  <FeatureItem key={f} text={f} />
                ))}
              </ul>
            </div>
            <BuyButton />
          </motion.div>

          {/* MAX CARD — featured */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="flex-1 w-full max-w-md mx-auto rounded-[2rem] p-8 shadow-xl flex flex-col relative mt-4 lg:mt-0 lg:-mt-4"
            style={{
              backgroundColor: "var(--color-bg)",
              border: "2px solid var(--color-accent)",
              boxShadow: "0 20px 60px -15px rgba(37,99,235,0.2)",
            }}
          >
            {/* MOST POPULAR BADGE */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2">
              <span className="text-white text-[11px] font-black tracking-widest uppercase px-4 py-1.5 rounded-full shadow-md"
                style={{ backgroundColor: "var(--color-accent)" }}>
                Most Popular
              </span>
            </div>

            <div className="mb-6">
              <h2 className="text-2xl font-bold mb-1" style={{ color: "var(--color-heading)" }}>Max</h2>
              <p className="text-sm font-medium mb-4" style={{ color: "var(--color-muted)" }}>White-glove career strategy</p>

              <span className="inline-block px-2.5 py-1 text-xs font-bold rounded mb-4"
                style={{ backgroundColor: "rgba(37,99,235,0.1)", color: "var(--color-accent)" }}>
                SAVE 73%
              </span>

              <div className="flex items-end gap-2 mb-1">
                <span className="text-5xl font-extrabold tracking-tighter font-display" style={{ color: "var(--color-heading)" }}>₹800</span>
                <span className="text-xl font-bold text-red-500 line-through mb-1">₹3000</span>
              </div>
              <p className="text-sm font-medium" style={{ color: "var(--color-muted)" }}>Limited time offer</p>
            </div>

            <div className="flex-grow">
              <ul className="space-y-4 mb-8">
                {["Get your resume within 24 hrs", "1:1 Mentor Calls", "Expert-crafted ATS-optimized resume", "Personalized mentor guidance", "Early bird offers access", "Help desk access"].map((f) => (
                  <FeatureItem key={f} text={f} />
                ))}
              </ul>
            </div>
            <BuyButton />
          </motion.div>

          {/* PRO MAX CARD */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="flex-1 w-full max-w-md mx-auto rounded-[2rem] p-8 shadow-xl flex flex-col relative"
            style={{ backgroundColor: "var(--color-bg)", border: "1px solid var(--color-border)" }}
          >
            <div className="mb-6">
              <h2 className="text-2xl font-bold mb-1" style={{ color: "var(--color-heading)" }}>Pro Max</h2>
              <p className="text-sm font-medium mb-4" style={{ color: "var(--color-muted)" }}>Ultimate plan for multiple profiles</p>

              <span className="inline-block px-2.5 py-1 text-xs font-bold rounded mb-4"
                style={{ backgroundColor: "rgba(20,184,166,0.1)", color: "var(--color-secondary)" }}>
                CUSTOM PLAN
              </span>

              <div className="flex items-end gap-2 mb-1">
                <span className="text-5xl font-extrabold tracking-tighter font-display" style={{ color: "var(--color-heading)" }}>
                  ₹{Math.round((resumeCount * 800) * (1 - Math.min((resumeCount - 1) * 0.1, 0.5)))}
                </span>
                <span className="text-xl font-bold text-red-500 line-through mb-1">₹{resumeCount * 3000}</span>
              </div>
              <p className="text-sm font-medium" style={{ color: "var(--color-muted)" }}>
                {resumeCount > 1 ? `Includes ${Math.min((resumeCount - 1) * 10, 50)}% bulk discount` : "Limited time offer"}
              </p>
            </div>

            <div className="flex-grow">
              <ul className="space-y-4 mb-8">
                <FeatureItem text={`${resumeCount} Resumes`} bold />
                {["Get your resume within 24 hrs", "1:1 Mentor Calls", "Expert-crafted ATS-optimized resume", "Personalized mentor guidance", "Early bird offers access", "Help desk access"].map((f) => (
                  <FeatureItem key={f} text={f} />
                ))}
              </ul>
            </div>

            <div className="flex items-center gap-3 mt-auto">
              <div className="flex items-center justify-between rounded-xl p-2 w-[120px]"
                style={{ backgroundColor: "var(--color-bg-section)", border: "1px solid var(--color-border)" }}>
                <button
                  onClick={decrement}
                  className="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xl transition-colors"
                  style={{ backgroundColor: "var(--color-border)", color: "var(--color-heading)" }}
                  onMouseEnter={e => e.currentTarget.style.backgroundColor = "var(--color-accent)"}
                  onMouseLeave={e => e.currentTarget.style.backgroundColor = "var(--color-border)"}
                >−</button>
                <span className="font-bold text-lg" style={{ color: "var(--color-heading)" }}>{resumeCount}</span>
                <button
                  onClick={increment}
                  className="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xl transition-colors"
                  style={{ backgroundColor: "var(--color-border)", color: "var(--color-heading)" }}
                  onMouseEnter={e => e.currentTarget.style.backgroundColor = "var(--color-accent)"}
                  onMouseLeave={e => e.currentTarget.style.backgroundColor = "var(--color-border)"}
                >+</button>
              </div>
              <div className="flex-1"><BuyButton /></div>
            </div>
          </motion.div>

        </div>

        {/* Feature Comparison Section */}
        <ComparisonTable />
      </div>
    </div>
  );
};

const ComparisonTable = () => {
  const features = [
    { name: "ATS-optimized resume formats", pro: true, max: true, promax: true },
    { name: "Unlimited ATS score analysis", pro: true, max: true, promax: true },
    { name: "Help desk access", pro: true, max: true, promax: true },
    { name: "Early bird offers access", pro: true, max: true, promax: true },
    { name: "1:1 Mentor Calls", pro: false, max: true, promax: true },
    { name: "Expert-crafted ATS-optimized resume", pro: false, max: true, promax: true },
    { name: "Personalized mentor guidance", pro: false, max: true, promax: true },
    { name: "24-hour delivery", pro: false, max: true, promax: true },
    { name: "Multiple profile support", pro: false, max: false, promax: true },
    { name: "Bulk discounts", pro: false, max: false, promax: true },
  ];

  const Check = () => <svg className="w-5 h-5 mx-auto" style={{ color: "var(--color-secondary)" }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>;
  const Dash = () => <svg className="w-5 h-5 mx-auto" style={{ color: "var(--color-muted)", opacity: 0.3 }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M20 12H4" /></svg>;

  return (
    <div className="mt-32 max-w-5xl mx-auto">
      <div className="text-center mb-16">
        <h2 className="text-3xl md:text-4xl font-extrabold mb-4" style={{ color: "var(--color-heading)" }}>Compare Plans</h2>
        <p className="text-lg font-medium" style={{ color: "var(--color-muted)" }}>Find the perfect tier for your career goals.</p>
      </div>

      <div className="overflow-x-auto rounded-[2rem] p-8 shadow-sm" style={{ backgroundColor: "var(--color-bg)", border: "1px solid var(--color-border)" }}>
        <table className="w-full min-w-[600px] border-collapse">
          <thead>
            <tr>
              <th className="text-left py-4 px-6 font-bold text-lg" style={{ color: "var(--color-heading)", borderBottom: "2px solid var(--color-border)" }}>Features</th>
              <th className="py-4 px-6 font-bold text-lg text-center" style={{ color: "var(--color-heading)", borderBottom: "2px solid var(--color-border)" }}>Pro</th>
              <th className="py-4 px-6 font-bold text-lg text-center" style={{ color: "var(--color-accent)", borderBottom: "2px solid var(--color-accent)" }}>Max</th>
              <th className="py-4 px-6 font-bold text-lg text-center" style={{ color: "var(--color-heading)", borderBottom: "2px solid var(--color-border)" }}>Pro Max</th>
            </tr>
          </thead>
          <tbody>
            {features.map((f, i) => (
              <tr key={i} className="transition-colors" style={{ borderBottom: i === features.length - 1 ? "none" : "1px solid var(--color-border)" }} onMouseEnter={e => e.currentTarget.style.backgroundColor = "var(--color-bg-section)"} onMouseLeave={e => e.currentTarget.style.backgroundColor = "transparent"}>
                <td className="py-4 px-6 font-medium text-sm md:text-base" style={{ color: "var(--color-body)" }}>{f.name}</td>
                <td className="py-4 px-6 text-center">{f.pro ? <Check /> : <Dash />}</td>
                <td className="py-4 px-6 text-center" style={{ backgroundColor: "rgba(37,99,235,0.02)" }}>{f.max ? <Check /> : <Dash />}</td>
                <td className="py-4 px-6 text-center">{f.promax ? <Check /> : <Dash />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Pricing;
