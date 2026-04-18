// src/App.jsx
import { Routes, Route } from "react-router-dom";
import React from "react";
import Layout from "./layout/Layout";

// Pages
import HomePage from "./pages/HomePage";
import CustomCursor from "./components/CustomCursor";
import Features from "./pages/Features";
import TemplatesPage from "./pages/TemplatesPage";
import About from "./pages/About";
import Support from "./pages/Support";

// Scroll Fix
import ScrollToTop from "./components/ScrollToTop";

const App = () => {
  return (
    <>
    <CustomCursor />
      {/* 🔥 THIS FIXES YOUR BUG */}
      <ScrollToTop />

      <Routes>
        <Route element={<Layout />}>

          {/* Home */}
          <Route path="/" element={<HomePage />} />

          {/* Features */}
          <Route path="/features" element={<Features />} />

          {/* Templates */}
          <Route path="/templates" element={<TemplatesPage />} />

          {/* About */}
          <Route path="/about" element={<About />} />

          {/* Contact / Support */}
          <Route path="/contact" element={<Support />} />

        </Route>
      </Routes>
    </>
  );
};

export default App;