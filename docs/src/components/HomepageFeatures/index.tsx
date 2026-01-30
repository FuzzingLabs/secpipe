import type { ReactNode } from "react";
import clsx from "clsx";
import Heading from "@theme/Heading";
import styles from "./styles.module.css";

type FeatureItem = {
  title: string;
  Svg: React.ComponentType<React.ComponentProps<"svg">>;
  description: ReactNode;
};

const FeatureList: FeatureItem[] = [
  {
    title: "AI-Powered Vulnerability Research",
    Svg: require("@site/static/img/icon-chip.svg").default,
    description: (
      <>
        Intelligent agents that understand your project context, suggest next
        steps, and collaborate across security domains.
      </>
    ),
  },
  {
    title: "Modular Security Workflows",
    Svg: require("@site/static/img/icon-stack.svg").default,
    description: (
      <>
        Orchestrate SAST, fuzzing, reversing, and triage tools using reusable
        python-based workflow definitions.
      </>
    ),
  },
  {
    title: "Security Marketplace",
    Svg: require("@site/static/img/icon-marketplace.svg").default,
    description: (
      <>
        Community-driven repository for agents, fuzzing corpora, grammars, CVEs,
        and complete security workflows.
      </>
    ),
  },
];

function Feature({ title, Svg, description }: FeatureItem) {
  return (
    <div className={clsx("col col--4")}>
      <div className="text--center">
        <Svg className={styles.featureSvg} role="img" />
      </div>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
