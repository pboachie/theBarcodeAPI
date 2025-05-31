// components/types/footer.ts

export interface FooterLink {
  href: string;
  label: string;
  longLabel?: string;
  external?: boolean;
}

export interface SocialLink {
  href: string;
  label: string;
  platform: 'twitter' | 'email';
}
