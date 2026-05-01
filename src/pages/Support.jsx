import React from "react";
import { motion } from "framer-motion";

const Support = () => {
  return (
    <div className="min-h-screen relative overflow-hidden pb-32 bg-white dark:bg-[#0a0a0a]">

      <div className="absolute bottom-0 right-0 w-[600px] h-[600px] bg-[#00b14f]/5 rounded-full blur-[150px] -z-10" />

      <section className="px-6 md:px-16 pt-32 relative z-10 max-w-6xl mx-auto">
        
        <div className="grid md:grid-cols-2 gap-16 items-start">
          
          {/* ================= LEFT SIDE: INFO ================= */}
          <motion.div 
            initial={{ opacity: 0, x: -40 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex flex-col gap-8"
          >
            <div>
              <motion.div 
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="inline-block px-4 py-1.5 rounded-full bg-green-50 dark:bg-[#00b14f]/10 text-[#00b14f] font-bold text-sm mb-6"
              >
                24/7 Support
              </motion.div>
              <h1 className="text-5xl font-extrabold mb-6 text-slate-900 dark:text-white">
                Get in <span className="text-[#00b14f]">Touch</span>
              </h1>
              <p className="text-lg text-slate-600 dark:text-slate-400 font-medium">
                Have questions about our AI resume builder or need help optimizing your profile? Our team is here to help you succeed.
              </p>
            </div>

            <div className="space-y-6 mt-8">
              <div className="bg-white dark:bg-[#111] border border-slate-100 dark:border-slate-800 p-6 rounded-2xl flex items-center gap-6 group hover:border-[#00b14f]/50 transition-colors shadow-sm">
                <div className="w-14 h-14 rounded-full bg-green-50 dark:bg-[#00b14f]/10 flex items-center justify-center text-[#00b14f] text-2xl group-hover:scale-110 transition-transform">
                  📧
                </div>
                <div>
                  <h4 className="font-bold text-slate-900 dark:text-white">Email Us</h4>
                  <p className="text-slate-600 dark:text-slate-400 font-medium">support@rozgar24x7.com</p>
                </div>
              </div>

              <div className="bg-white dark:bg-[#111] border border-slate-100 dark:border-slate-800 p-6 rounded-2xl flex items-center gap-6 group hover:border-[#00b14f]/50 transition-colors shadow-sm">
                <div className="w-14 h-14 rounded-full bg-green-50 dark:bg-[#00b14f]/10 flex items-center justify-center text-[#00b14f] text-2xl group-hover:scale-110 transition-transform">
                  💬
                </div>
                <div>
                  <h4 className="font-bold text-slate-900 dark:text-white">Live Chat</h4>
                  <p className="text-slate-600 dark:text-slate-400 font-medium">Available 9am - 6pm EST</p>
                </div>
              </div>
            </div>
          </motion.div>

          {/* ================= RIGHT SIDE: FORM ================= */}
          <motion.div 
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            className="relative"
          >
            <form className="glass-card p-10 relative z-10 flex flex-col gap-6">
              <h3 className="text-2xl font-bold mb-4 text-slate-900 dark:text-white">Send a Message</h3>
              
              <div className="grid grid-cols-2 gap-6">
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-bold text-slate-700 dark:text-slate-300">First Name</label>
                  <input type="text" className="w-full bg-slate-50 dark:bg-[#0a0a0a] border border-slate-200 dark:border-slate-800 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-[#00b14f] focus:border-transparent transition-all font-medium" placeholder="John" />
                </div>
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-bold text-slate-700 dark:text-slate-300">Last Name</label>
                  <input type="text" className="w-full bg-slate-50 dark:bg-[#0a0a0a] border border-slate-200 dark:border-slate-800 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-[#00b14f] focus:border-transparent transition-all font-medium" placeholder="Doe" />
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-sm font-bold text-slate-700 dark:text-slate-300">Email Address</label>
                <input type="email" className="w-full bg-slate-50 dark:bg-[#0a0a0a] border border-slate-200 dark:border-slate-800 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-[#00b14f] focus:border-transparent transition-all font-medium" placeholder="john@example.com" />
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-sm font-bold text-slate-700 dark:text-slate-300">Message</label>
                <textarea rows="5" className="w-full bg-slate-50 dark:bg-[#0a0a0a] border border-slate-200 dark:border-slate-800 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-[#00b14f] focus:border-transparent transition-all resize-none font-medium" placeholder="How can we help you?"></textarea>
              </div>

              <button type="submit" className="w-full mt-4 py-4 rounded-full bg-[#00b14f] hover:bg-[#009641] text-white font-bold text-lg transition-colors shadow-md shadow-[#00b14f]/20">
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