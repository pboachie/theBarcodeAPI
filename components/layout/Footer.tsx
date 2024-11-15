import React from 'react';
import Link from 'next/link';
import { siteConfig } from '@/lib/config/site';
import { FooterLink, SocialLink } from '@/components/types/footer';
import { SocialIcons } from '@/components/icons/social-icons';

export const Footer: React.FC = () => {
  const currentYear = new Date().getFullYear();
  const { navigation, social } = siteConfig.footer;
  const version = process.env.NEXT_PUBLIC_APP_VERSION || "0.1.0";

  const renderSocialIcon = (platform: SocialLink['platform']) => {
    return SocialIcons[platform];
  };

  const renderLink = ({ href, label, longLabel, external }: FooterLink) => (
    <Link
      key={href}
      href={href}
      className="text-sm text-foreground hover:underline transition-colors whitespace-nowrap"
      {...(external ? {
        target: "_blank",
        rel: "noopener noreferrer"
      } : {})}
    >
      <span className="md:hidden">{label}</span>
      <span className="hidden md:inline">{longLabel || label}</span>
    </Link>
  );

  return (
    <footer
      className="footer bg-background md:py-8 py-4 md:pb-8 pb-0 w-full"
      role="contentinfo"
      aria-label="Site footer"
    >
      <div className="container mx-auto px-4">
        <div className="flex flex-col md:flex-row justify-between items-center gap-4 md:gap-0">
          {/* Main Navigation */}
          <nav className="flex flex-wrap gap-4 justify-center order-1 md:order-2" aria-label="Footer navigation">
            {navigation.map(renderLink)}
          </nav>

          {/* Copyright */}
          <div className="text-sm text-foreground order-2 md:order-1 text-center">
            <div>
              <span>© {currentYear} </span>
              <Link href="/" className="hover:underline">
                {siteConfig.name}
              </Link>
              <span> - All rights reserved.</span>
            </div>
            <div className="text-xs text-gray-500 mt-1">Version {version}</div>
          </div>

          {/* Social Links */}
          <div className="flex space-x-4 order-3 pb-4 md:pb-0" aria-label="Social media links">
            {social.map(({ href, label, platform }) => (
              <a
                key={href}
                href={href}
                aria-label={`Follow us on ${platform}`}
                className="inline-flex items-center justify-center transition-opacity hover:opacity-80"
                target="_blank"
                rel="noopener noreferrer"
              >
                {renderSocialIcon(platform)}
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
};