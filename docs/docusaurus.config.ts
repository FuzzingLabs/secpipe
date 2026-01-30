import { themes as prismThemes } from "prism-react-renderer";
import type { Config } from "@docusaurus/types";
import type * as Preset from "@docusaurus/preset-classic";

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: "FuzzForge Documentation",
  tagline: "AI-Powered Security Analysis Platform",
  favicon: "img/favicon.ico",

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Production url of documentation
  url: "https://docs.fuzzforge.ai",
  // The /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: "/",
  trailingSlash: false,

  // GitHub pages deployment config.
  organizationName: "FuzzingLabs",
  projectName: "fuzzforge_alpha",
  deploymentBranch: "gh-pages",

  onBrokenLinks: "throw",

  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },

  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: "warn",
    },
  },

  presets: [
    [
      "classic",
      {
        docs: {
          sidebarPath: "./sidebars.ts",
          editUrl:
            "https://github.com/FuzzingLabs/fuzzforge_alpha/tree/main/packages/create-docusaurus/templates/shared/",
        },
        theme: {
          customCss: "./src/css/custom.css",
        },
      } satisfies Preset.Options,
    ],
  ],

  themes: [
    "@docusaurus/theme-mermaid",
    [
      require.resolve("@easyops-cn/docusaurus-search-local"),
      /** @type {import("@easyops-cn/docusaurus-search-local").PluginOptions} */
      {
        // `hashed` is recommended as long-term-cache of index file is possible.
        hashed: true,

        language: ["en"],
      },
    ],
  ],

  themeConfig: {
    metadata: [
      {
        name: "keywords",
        content:
          "documentation, fuzzforge, fuzzinglabs, fuzzing, security, ai, ai-powered, vulnerability, analysis, platform",
      },
      { name: "twitter:card", content: "summary_large_image" },
    ],
    image: "img/fuzzforge-social-card.jpg",
    navbar: {
      title: "FuzzForge Docs",
      logo: {
        alt: "FuzzForge Logo",
        src: "img/fuzzforge-logo-1024-rounded.png",
      },
      items: [
        {
          type: "docSidebar",
          sidebarId: "backendSidebar",
          position: "left",
          label: "Workflow",
        },
        {
          type: "docSidebar",
          sidebarId: "aiSidebar",
          position: "left",
          label: "AI",
        },
        {
          href: "https://github.com/FuzzingLabs/fuzzforge_ai",
          label: "GitHub",
          position: "right",
        },
      ],
    },
    footer: {
      style: "dark",
      links: [
        {
          title: "Workflow",
          items: [
            {
              label: "Tutorials",
              to: "/docs/category/tutorial",
            },
            {
              label: "Concepts",
              to: "/docs/category/concept",
            },
            {
              label: "How-to Guides",
              to: "/docs/category/how-to-guides",
            },
            {
              label: "References",
              to: "/docs/category/reference",
            },
          ],
        },
        {
          title: "Community",
          items: [
            {
              label: "Website",
              href: "https://fuzzforge.ai/",
            },
            {
              label: "Discord",
              href: "https://discord.gg/jKBygqFkwn",
            },
            {
              label: "X",
              href: "https://x.com/FuzzingLabs",
            },
            {
              label: "LinkedIn",
              href: "https://www.linkedin.com/company/fuzzinglabs",
            },
          ],
        },
        {
          title: "More",
          items: [
            {
              label: "FuzzingLabs Blog",
              to: "https://fuzzinglabs.com/security-blog/",
            },
            {
              label: "GitHub",
              href: "https://github.com/FuzzingLabs/fuzzforge_ai",
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} FuzzingLabs - All Rights Reserved`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
