import React from "react";
import { motion } from "framer-motion";

const Support = () => {
  return (
    <div className="min-h-screen relative overflow-hidden pb-32" style={{ backgroundColor: "var(--color-bg)" }}>

      {/* Background glow */}
      <div
        className="absolute bottom-0 right-0 w-[600px] h-[600px] rounded-full blur-[150px] -z-10"
        style={{ backgroundColor: "rgba(37,99,235,0.05)" }}
      />

      <section className="px-6 md:px-16 pt-32 relative z-10 max-w-6xl mx-auto">
        <div className="grid md:grid-cols-2 gap-16 items-start">

          {/* LEFT: INFO */}
          <motion.div
            initial={{ opacity: 0, x: -40 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex flex-col gap-8"
          >
            <div>
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="inline-block px-4 py-1.5 rounded-full font-bold text-sm mb-6"
                style={{ backgroundColor: "rgba(37,99,235,0.08)", color: "var(--color-accent)" }}
              >
                24/7 Support
              </motion.div>
              <h1 className="text-5xl font-extrabold mb-6" style={{ color: "var(--color-heading)" }}>
                Get in <span style={{ color: "var(--color-accent)" }}>Touch</span>
              </h1>
              <p className="text-lg font-medium" style={{ color: "var(--color-muted)" }}>
                Have questions about our AI resume builder or need help optimizing your profile? Our team is here to help you succeed.
              </p>
            </div>

            <div className="space-y-6 mt-8">
              {[
                { emoji: "📧", title: "Email Us",  desc: "support@rozgar24x7.com" },
                { emoji: "💬", title: "Live Chat", desc: "Available 9am - 6pm EST" },
              ].map(({ emoji, title, desc }) => (
                <div
                  key={title}
                  className="p-6 rounded-2xl flex items-center gap-6 group shadow-sm transition-all"
                  style={{ backgroundColor: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = "rgba(37,99,235,0.4)"}
                  onMouseLeave={e => e.currentTarget.style.borderColor = "var(--color-border)"}
                >
                  <div
                    className="w-14 h-14 rounded-[25%] flex items-center justify-center text-2xl group-hover:scale-110 transition-transform"
                    style={{ backgroundColor: "rgba(37,99,235,0.07)" }}
                  >
                    {emoji}
                  </div>
                  <div>
                    <h4 className="font-bold" style={{ color: "var(--color-heading)" }}>{title}</h4>
                    <p className="font-medium" style={{ color: "var(--color-muted)" }}>{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>

          {/* RIGHT: FORM */}
          <motion.div initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} className="relative">
            <form
              className="p-10 relative z-10 flex flex-col gap-6 rounded-3xl shadow-sm"
              style={{ backgroundColor: "var(--color-bg)", border: "1px solid var(--color-border)" }}
            >
              <h3 className="text-2xl font-bold mb-4" style={{ color: "var(--color-heading)" }}>Send a Message</h3>

              <div className="grid grid-cols-2 gap-6">
                {[{ label: "First Name", placeholder: "John" }, { label: "Last Name", placeholder: "Doe" }].map(({ label, placeholder }) => (
                  <div key={label} className="flex flex-col gap-2">
                    <label className="text-sm font-bold" style={{ color: "var(--color-body)" }}>{label}</label>
                    <input
                      type="text"
                      placeholder={placeholder}
                      className="w-full rounded-xl px-4 py-3 outline-none transition-all font-medium text-sm"
                      style={{
                        backgroundColor: "var(--color-bg-section)",
                        border: "1px solid var(--color-border)",
                        color: "var(--color-body)",
                      }}
                      onFocus={e => e.target.style.borderColor = "var(--color-accent)"}
                      onBlur={e => e.target.style.borderColor = "var(--color-border)"}
                    />
                  </div>
                ))}
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-sm font-bold" style={{ color: "var(--color-body)" }}>Email Address</label>
                <input
                  type="email"
                  placeholder="john@example.com"
                  className="w-full rounded-xl px-4 py-3 outline-none transition-all font-medium text-sm"
                  style={{
                    backgroundColor: "var(--color-bg-section)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-body)",
                  }}
                  onFocus={e => e.target.style.borderColor = "var(--color-accent)"}
                  onBlur={e => e.target.style.borderColor = "var(--color-border)"}
                />
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-sm font-bold" style={{ color: "var(--color-body)" }}>Message</label>
                <textarea
                  rows="5"
                  placeholder="How can we help you?"
                  className="w-full rounded-xl px-4 py-3 outline-none transition-all resize-none font-medium text-sm"
                  style={{
                    backgroundColor: "var(--color-bg-section)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-body)",
                  }}
                  onFocus={e => e.target.style.borderColor = "var(--color-accent)"}
                  onBlur={e => e.target.style.borderColor = "var(--color-border)"}
                />
              </div>

              <button
                type="submit"
                className="w-full mt-4 py-4 rounded-full text-white font-bold text-lg transition-all hover:-translate-y-0.5"
                style={{
                  backgroundColor: "var(--color-cta-bg)",
                  boxShadow: "0 10px 30px -8px rgba(37,99,235,0.35)",
                }}
                onMouseEnter={e => e.currentTarget.style.backgroundColor = "var(--color-cta-hover)"}
                onMouseLeave={e => e.currentTarget.style.backgroundColor = "var(--color-cta-bg)"}
              >
                Send Message
              </button>
            </form>
          </motion.div>

        </div>
      </section>
    </div>
  );
};

export default Support;