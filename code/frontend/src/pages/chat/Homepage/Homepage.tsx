// src/pages/FeaturePage.tsx
import React from 'react';
import { Stack } from '@fluentui/react';
import IntractData  from '../../../assets/Interact with data.svg'
import SourceReference  from '../../../assets/Quick source reference.svg'
import SummarizeContracts  from '../../../assets/Summarize contracts.svg'
import styles from './Homepage.module.css'; // Create this CSS module for custom styles

const Homepage: React.FC = () => {
  return (
    <div className={styles.container}>
      <main className={styles.mainContent}>
        <section className={styles.cards}>
          <FeatureCard

            title="Interact with Data"
            description="Intuitive and conversational search experience that simplifies complex queries, ultimately improving productivity, job efficiency, and satisfaction."
            icon={<img src = {IntractData} style={{ minWidth: 20, minHeight: 22 }} />}
          />
          <FeatureCard

            title="Summarize Contracts"
            description="Quickly review and summarize lengthy documents, extracting essential details to streamline document review and preparation."
            icon={<img src = {SummarizeContracts} style={{ minWidth: 20, minHeight: 22 }} />}
          />
          <FeatureCard

            title="Quick Source Reference"
            description="Effortlessly retrieve and reference original documents, ensuring accuracy and comprehensiveness."
            icon={<img src = {SourceReference} style={{ minWidth: 20, minHeight: 22 }} />}
          />
        </section>
      </main>
    </div>
  );
};

interface FeatureCardProps {
  title: string;
  description: string;
  icon: React.ReactNode;
}

const FeatureCard: React.FC<FeatureCardProps> = ({ title, description, icon }) => {
  return (
    <div  className={styles.featureCard}>
      <div className={styles.icon}>{icon}</div>
      <h2 className={styles.cardTitle}>{title}</h2>
      <p className={styles.cardDescription}>{description}</p>
    </div>
  );
};

export default Homepage;
