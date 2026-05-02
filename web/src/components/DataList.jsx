import { useState } from 'react';

const SOURCES = [
  { id: 'all', label: '전체' },
  { id: 'naver_news', label: '네이버 뉴스' },
  { id: 'naver_blog', label: '네이버 블로그' },
  { id: 'youtube', label: '유튜브' }
];

const CATEGORY_CONFIG = {
  confirmed: { label: '확정', className: 'badge-confirmed' },
  related_issue: { label: '이슈', className: 'badge-related-issue' },
  comparison: { label: '비교', className: 'badge-comparison' },
  political_context: { label: '정치', className: 'badge-political' },
  weak_match: { label: '검토', className: 'badge-weak' },
  other_event_only: { label: '타행사', className: 'badge-other-event' },
  irrelevant: { label: '무관', className: 'badge-irrelevant' },
  ai_irrelevant: { label: 'AI무관', className: 'badge-ai-irrelevant' }
};

const FILTER_STATUS_CONFIG = {
  kept: { label: 'Kept', className: 'status-kept' },
  review: { label: 'Review', className: 'status-review' },
  excluded: { label: 'Excluded', className: 'status-excluded' }
};

const DataList = ({ details }) => {
  const [activeTab, setActiveTab] = useState(SOURCES[0].id);
  const [expandedIdx, setExpandedIdx] = useState(null);

  if (!details || details.length === 0) return null;

  const filteredData = activeTab === 'all' 
    ? details 
    : details.filter(item => item.source === activeTab);

  const toggleExpand = (idx) => {
    setExpandedIdx(expandedIdx === idx ? null : idx);
  };

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
            {source.id !== 'all' && (
              <span className="tab-count">
                {details.filter(item => item.source === source.id).length}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="data-list glass-panel">
        {filteredData.length === 0 ? (
          <div className="empty-state">No data available for this category.</div>
        ) : (
          filteredData.map((item, idx) => {
            const catConfig = CATEGORY_CONFIG[item.category] || { label: item.category || '', className: '' };
            const statusConfig = FILTER_STATUS_CONFIG[item.filter_status] || { label: '', className: '' };
            const isExpanded = expandedIdx === idx;

            return (
              <div key={`${item.source}-${idx}`} className="data-item" onClick={() => toggleExpand(idx)}>
                <div className="item-header">
                  <div className="item-title-row">
                    {item.category && (
                      <span className={`category-badge ${catConfig.className}`}>
                        {catConfig.label}
                      </span>
                    )}
                    {item.filter_status && item.filter_status !== 'kept' && (
                      <span className={`status-badge ${statusConfig.className}`}>
                        {statusConfig.label}
                      </span>
                    )}
                    {item.ai_used && (
                      <span className="ai-badge">🤖 AI</span>
                    )}
                    <a 
                      href={item.canonical_url} 
                      target="_blank" 
                      rel="noopener noreferrer" 
                      className="item-title"
                      onClick={e => e.stopPropagation()}
                      dangerouslySetInnerHTML={{ __html: item.title }}
                    />
                  </div>
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
                  {item.source_label && <span className="source-tag">{item.source_label}</span>}
                </div>

                {/* 확장 상세 정보 */}
                {isExpanded && (
                  <div className="item-expanded">
                    {item.matched_target_terms && item.matched_target_terms.length > 0 && (
                      <div className="expanded-row">
                        <span className="expanded-label">Target 매칭:</span>
                        <div className="expanded-tags">
                          {item.matched_target_terms.map((t, i) => (
                            <span key={i} className="tag tag-target">{t}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {item.matched_other_event_terms && item.matched_other_event_terms.length > 0 && (
                      <div className="expanded-row">
                        <span className="expanded-label">타 행사:</span>
                        <div className="expanded-tags">
                          {item.matched_other_event_terms.map((t, i) => (
                            <span key={i} className="tag tag-other">{t}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {item.matched_political_terms && item.matched_political_terms.length > 0 && (
                      <div className="expanded-row">
                        <span className="expanded-label">정치 키워드:</span>
                        <div className="expanded-tags">
                          {item.matched_political_terms.map((t, i) => (
                            <span key={i} className="tag tag-political">{t}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {item.matched_politician_terms && Object.keys(item.matched_politician_terms).length > 0 && (
                      <div className="expanded-row">
                        <span className="expanded-label">정치인:</span>
                        <div className="expanded-tags">
                          {Object.entries(item.matched_politician_terms).map(([key, terms]) => 
                            terms && terms.length > 0 ? terms.map((t, i) => (
                              <span key={`${key}-${i}`} className="tag tag-politician">{t} ({key})</span>
                            )) : null
                          )}
                        </div>
                      </div>
                    )}
                    {item.matched_issue_terms && item.matched_issue_terms.length > 0 && (
                      <div className="expanded-row">
                        <span className="expanded-label">이슈 키워드:</span>
                        <div className="expanded-tags">
                          {item.matched_issue_terms.map((t, i) => (
                            <span key={i} className="tag tag-issue">{t}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {item.filter_reason && (
                      <div className="expanded-row">
                        <span className="expanded-label">분류 사유:</span>
                        <span className="expanded-value">{item.filter_reason}</span>
                      </div>
                    )}
                    {item.ai_used && (
                      <div className="expanded-row">
                        <span className="expanded-label">AI 판별:</span>
                        <span className="expanded-value">{item.ai_category} — {item.ai_reason}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default DataList;
