import React, { useRef, useEffect, useState } from "react";
import emailjs from "@emailjs/browser";
import { motion } from "framer-motion";

const Support = () => {
  const form = useRef();
  const [pos, setPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const move = (e) => setPos({ x: e.clientX, y: e.clientY });
    window.addEventListener("mousemove", move);
    return () => window.removeEventListener("mousemove", move);
  }, []);

  const sendEmail = (e) => {
    e.preventDefault();
    form.current.time.value = new Date().toLocaleString();

    emailjs
      .sendForm(
        "service_aztije9",
        "template_b9m45un",
        form.current,
        "gAdau_gAMszN0t71t"
      )
      .then(() => {
        alert("Message Sent Successfully!");
        form.current.reset();
      })
      .catch(() => {
        alert("Something went wrong.");
      });
  };

  return (
    <motion.div
      className="min-h-screen flex justify-center items-center px-4 bg-[#f8fafc] text-black relative overflow-hidden"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >

      {/* 🔥 CURSOR LIGHT */}
      <motion.div
        className="pointer-events-none fixed top-0 left-0 z-0"
        animate={{ x: pos.x - 120, y: pos.y - 120 }}
      >
        <div className="w-[240px] h-[240px] bg-black/[0.05] blur-3xl rounded-full" />
      </motion.div>

      {/* 🌫️ NOISE */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute inset-0 opacity-[0.05] bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" />
      </div>

      {/* 💎 FORM CARD */}
      <form
        ref={form}
        onSubmit={sendEmail}
        className="relative z-10 w-full max-w-lg bg-black/[0.03] backdrop-blur-2xl border border-black/[0.08] p-8 rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.08)]"
      >

        {/* HEADER */}
        <div className="text-center mb-8">
          <p className="text-xs bg-black/[0.05] text-black/70 px-3 py-1 rounded-full inline-block border border-black/[0.08]">
            Contact Support
          </p>

          <h1 className="text-4xl font-semibold mt-4">
            Need Help?
          </h1>

          <p className="text-gray-600 mt-3 text-sm">
            Reach out anytime at{" "}
            <a
              href="mailto:support@rozgar24x7.com"
              className="text-black underline"
            >
              support@rozgar24x7.com
            </a>
          </p>
        </div>

        {/* FORM */}
        <div className="space-y-4 text-sm">

          {[
            { label: "Full Name", name: "user_name", type: "text" },
            { label: "Email", name: "user_email", type: "email" },
            { label: "Mobile", name: "user_mobile", type: "tel" },
          ].map((field, i) => (
            <div key={i}>
              <label className="text-gray-600">{field.label}</label>
              <input
                type={field.type}
                name={field.name}
                required
                className="w-full mt-1 px-4 py-2 rounded-lg bg-black/[0.04] border border-black/[0.1] outline-none text-black placeholder-black/40 focus:bg-black/[0.06] transition"
              />
            </div>
          ))}

          {/* MESSAGE */}
          <div>
            <label className="text-gray-600">Message</label>
            <textarea
              name="message"
              rows="4"
              required
              className="w-full mt-1 p-3 rounded-lg bg-black/[0.04] border border-black/[0.1] outline-none resize-none text-black placeholder-black/40 focus:bg-black/[0.06] transition"
            />
          </div>

          <input type="hidden" name="time" />

          {/* BUTTON */}
          <motion.button
            type="submit"
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.96 }}
            className="w-full mt-4 py-3 rounded-lg bg-black text-white font-medium hover:bg-gray-800 transition"
          >
            Send Message
          </motion.button>

        </div>

      </form>
    </motion.div>
  );
};

export default Support;