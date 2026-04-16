import React, { useRef } from "react";
import emailjs from "@emailjs/browser";
import { motion } from "framer-motion";

const Support = () => {
  const form = useRef();

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
      .then(
        () => {
          alert("Message Sent Successfully!");
          form.current.reset();
        },
        (error) => {
          console.error("EmailJS Error:", error.text);
          alert("Something went wrong. Please try again.");
        }
      );
  };

  return (
    <motion.div
      className="min-h-screen flex justify-center items-center px-4 
      bg-gradient-to-br from-[#E5E7EB] via-[#C7D2D9] to-[#2C4A52]"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}
    >

      {/* MAIN CARD */}
      <form
        ref={form}
        onSubmit={sendEmail}
        className="w-full max-w-lg bg-white/40 backdrop-blur-lg border border-white/30 
        p-8 rounded-2xl shadow-xl"
      >

        {/* HEADER */}
        <div className="text-center mb-8">
          <p className="text-xs bg-white/50 text-[#2C4A52] font-medium px-3 py-1 rounded-full inline-block">
            Contact Support
          </p>

          <h1 className="text-3xl md:text-4xl font-bold mt-4">
            Need Help?
          </h1>

          <p className="text-gray-700 mt-3 text-sm">
            Reach out anytime at{" "}
            <a
              href="mailto:support@rozgar24x7.com"
              className="text-[#2C4A52] underline"
            >
              support@rozgar24x7.com
            </a>
          </p>
        </div>

        {/* FORM */}
        <div className="space-y-4 text-sm">

          {/* NAME */}
          <div>
            <label className="font-medium">Full Name</label>
            <input
              type="text"
              name="user_name"
              required
              placeholder="Enter your full name"
              className="w-full mt-1 px-4 py-2 rounded-lg bg-white/60 border border-gray-300 outline-none focus:ring-2 focus:ring-[#2C4A52]/40 transition"
            />
          </div>

          {/* EMAIL */}
          <div>
            <label className="font-medium">Email</label>
            <input
              type="email"
              name="user_email"
              required
              placeholder="Enter your email"
              className="w-full mt-1 px-4 py-2 rounded-lg bg-white/60 border border-gray-300 outline-none focus:ring-2 focus:ring-[#2C4A52]/40 transition"
            />
          </div>

          {/* MOBILE */}
          <div>
            <label className="font-medium">Mobile</label>
            <input
              type="tel"
              name="user_mobile"
              pattern="[6-9]{1}[0-9]{9}"
              required
              placeholder="Enter your number"
              className="w-full mt-1 px-4 py-2 rounded-lg bg-white/60 border border-gray-300 outline-none focus:ring-2 focus:ring-[#2C4A52]/40 transition"
            />
          </div>

          {/* MESSAGE */}
          <div>
            <label className="font-medium">Message</label>
            <textarea
              name="message"
              rows="4"
              required
              placeholder="Tell us how we can help..."
              className="w-full mt-1 p-3 rounded-lg bg-white/60 border border-gray-300 outline-none resize-none focus:ring-2 focus:ring-[#2C4A52]/40 transition"
            />
          </div>

          {/* HIDDEN */}
          <input type="hidden" name="time" />

          {/* BUTTON */}
          <motion.button
            type="submit"
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            className="w-full mt-4 py-3 rounded-lg bg-[#2C4A52] text-white font-medium hover:opacity-90 transition"
          >
            Send Message
          </motion.button>

        </div>

      </form>
    </motion.div>
  );
};

export default Support;