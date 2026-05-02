import { Routes, Route } from "react-router-dom";
import React from "react";
import Layout from "./layout/Layout";
import { ThemeProvider } from "./components/ThemeContext";

// Pages
import HomePage from "./pages/HomePage";
import Features from "./pages/Features";
import TemplatesPage from "./pages/TemplatesPage";
import About from "./pages/About";
import Support from "./pages/Support";
import Pricing from "./pages/Pricing";
import AtsAnalysis from "./pages/AtsAnalysis";
import { Toaster } from "sonner";

// Components
import ScrollToTop from "./components/ScrollToTop";

const App = () => {
  return (
    <ThemeProvider>

      <ScrollToTop />
      <Toaster position="top-center" richColors />

      <Routes>
        <Route element={<Layout />}>

          <Route path="/" element={<HomePage />} />
          <Route path="/features" element={<Features />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/templates" element={<TemplatesPage />} />
          <Route path="/about" element={<About />} />
          <Route path="/contact" element={<Support />} />
          <Route path="/analyze" element={<AtsAnalysis />} />

        </Route>
      </Routes>

    </ThemeProvider>
  );
};

export default App;