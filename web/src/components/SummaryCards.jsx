import React from 'react';

const ICONS = {
  "naver_news": "📰",
  "naver_blog": "📝",
  "youtube": "📺"
};

const SummaryCards = ({ summary }) => {
  if (!summary || summary.length === 0) return null;

  return (
    <div className="cards-grid animate-fade-in" style={{ animationDelay: '0.1s' }}>
      {summary.map((stat, index) => {
        const icon = ICONS[stat.source] || "📊";
        const isError = stat.status === "ERROR";
        
        return (
          <div key={stat.source} className="stat-card glass" style={{ animationDelay: `${0.1 + index * 0.1}s` }}>
            <div className="stat-card-header">
              <span className="stat-card-title">{stat.source_label}</span>
              <span className="stat-icon">{icon}</span>
            </div>
            <div className="stat-value">{stat.deduped_count}</div>
            <div className="stat-sub">
              <span>Raw: {stat.raw_count}</span>
              <span className={!isError ? "success" : "error"}>
                {isError ? "Error" : "Success"}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default SummaryCards;
