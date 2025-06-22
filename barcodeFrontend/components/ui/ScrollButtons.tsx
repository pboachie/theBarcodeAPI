"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";

const ScrollButtons = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [showScrollToBottom, setShowScrollToBottom] = useState(true);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const scrollToBottom = () => {
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  };

  useEffect(() => {
    const handleScroll = () => {
      const currentScrollPos = window.pageYOffset || document.documentElement.scrollTop;
      const atTop = currentScrollPos < 400;
      // Ensure document.body is available
      const atBottom = document.body ? (window.innerHeight + currentScrollPos) >= document.body.scrollHeight - 400 : false;

      setIsVisible(!atTop);
      setShowScrollToBottom(!atBottom);
    };

    window.addEventListener("scroll", handleScroll);
    // Call handler once on mount to set initial state based on current scroll position
    handleScroll();

    return () => {
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  return (
    <div
      className={`fixed bottom-4 right-4 flex flex-col space-y-2 transition-opacity duration-300 ease-in-out ${
        isVisible ? "opacity-100" : "opacity-0 pointer-events-none"
      }`}
    >
      {/* Scroll to Top button is always rendered when isVisible is true */}
      <Button
        onClick={scrollToTop}
        variant="outline"
        className="hover:scale-105 transform transition-transform duration-200"
      >
        Scroll to Top
      </Button>

      {/* Scroll to Bottom button is rendered if isVisible and showScrollToBottom are true */}
      {showScrollToBottom && (
        <Button
          onClick={scrollToBottom}
          variant="outline"
          className="hover:scale-105 transform transition-transform duration-200"
        >
          Scroll to Bottom
        </Button>
      )}
    </div>
  );
};

export default ScrollButtons;
