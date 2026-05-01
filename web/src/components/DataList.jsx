import React, { useState } from 'react';

const SOURCES = [
  { id: 'naver_news', label: '네이버 뉴스' },
  { id: 'naver_blog', label: '네이버 블로그' },
  { id: 'youtube', label: '유튜브' }
];

const DataList = ({ details }) => {
  const [activeTab, setActiveTab] = useState(SOURCES[0].id);

  if (!details || details.length === 0) return null;

  const filteredData = details.filter(item => item.source === activeTab);

  return (
    <div className="data-section animate-fade-in" style={{ animationDelay: '0.3s' }}>
      <div className="tabs">
        {SOURCES.map(source => (
          <button
            key={source.id}
            className={`tab-button ${activeTab === source.id ? 'active' : ''}`}
            onClick={() => setActiveTab(source.id)}
          >
            {source.label}
          </button>
        ))}
      </div>

      <div className="data-list glass-panel">
        {filteredData.length === 0 ? (
          <div className="empty-state">No data available for this category.</div>
        ) : (
          filteredData.map((item, idx) => (
            <a 
              href={item.canonical_url} 
              target="_blank" 
              rel="noopener noreferrer" 
              key={`${item.source}-${idx}`} 
              className="data-item"
            >
              <div className="item-header">
                <h3 className="item-title" dangerouslySetInnerHTML={{ __html: item.title }}></h3>
                <span className="item-date">
                  {item.source === 'naver_news' || item.source === 'youtube' 
                    ? new Date(item.published_at_kst).toLocaleDateString()
                    : item.published_date_kst}
                </span>
              </div>
              <p className="item-desc" dangerouslySetInnerHTML={{ __html: item.description }}></p>
              
              <div className="item-meta">
                {item.author_or_channel && <span>👤 {item.author_or_channel}</span>}
                {item.source === 'youtube' && <span>▶️ Video</span>}
              </div>
            </a>
          ))
        )}
      </div>
    </div>
  );
};

export default DataList;
