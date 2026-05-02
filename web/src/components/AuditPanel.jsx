import React, { useState, useEffect } from 'react';

const AuditPanel = ({ auditFileUrl, onClose }) => {
  const [auditData, setAuditData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!auditFileUrl) return;
    setLoading(true);
    setError(null);
    
    fetch(auditFileUrl)
      .then(res => {
        if (!res.ok) throw new Error('Audit file not found');
        return res.json();
      })
      .then(data => {
        // filter_status = excluded 또는 category in [other_event_only, irrelevant, ai_irrelevant]
        const excludedItems = data.filter(item => 
          item.filter_status === 'excluded' ||
          ['other_event_only', 'irrelevant', 'ai_irrelevant'].includes(item.category)
        );
        setAuditData(excludedItems);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setError('제외 후보 데이터를 불러올 수 없습니다.');
        setLoading(false);
      });
  }, [auditFileUrl]);

  if (!auditFileUrl) return null;

  const getCategoryBadgeClass = (category) => {
    const map = {
      'other_event_only': 'badge-other-event',
      'irrelevant': 'badge-irrelevant',
      'ai_irrelevant': 'badge-ai-irrelevant'
    };
    return map[category] || 'badge-default';
  };

  const getCategoryLabel = (category) => {
    const map = {
      'other_event_only': '타 행사',
      'irrelevant': '무관',
      'ai_irrelevant': 'AI 무관'
    };
    return map[category] || category;
  };

  return (
    <div className="audit-overlay" onClick={onClose}>
      <div className="audit-modal glass" onClick={e => e.stopPropagation()}>
        <div className="audit-header">
          <h3>🔍 제외 후보 검수</h3>
          <button className="audit-close-btn" onClick={onClose}>✕</button>
        </div>

        {loading && <div className="audit-loading">Loading...</div>}
        {error && <div className="audit-error">{error}</div>}

        {auditData && (
          <>
            <div className="audit-summary">
              <span>총 {auditData.length}건 제외됨</span>
            </div>

            <div className="audit-list">
              {auditData.map((item, idx) => (
                <div key={idx} className="audit-item">
                  <div className="audit-item-header">
                    <span className={`category-badge ${getCategoryBadgeClass(item.category)}`}>
                      {getCategoryLabel(item.category)}
                    </span>
                    <span className="audit-source">{item.source_label}</span>
                  </div>

                  <a 
                    href={item.canonical_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="audit-item-title"
                  >
                    {item.title}
                  </a>
                  
                  <p className="audit-item-desc">{item.description}</p>

                  <div className="audit-meta-grid">
                    <div className="audit-meta-item">
                      <span className="audit-meta-label">제외 사유</span>
                      <span className="audit-meta-value">{item.filter_reason}</span>
                    </div>

                    {item.matched_target_terms && item.matched_target_terms.length > 0 && (
                      <div className="audit-meta-item">
                        <span className="audit-meta-label">매칭 target</span>
                        <span className="audit-meta-value">{item.matched_target_terms.join(', ')}</span>
                      </div>
                    )}

                    {item.matched_other_event_terms && item.matched_other_event_terms.length > 0 && (
                      <div className="audit-meta-item">
                        <span className="audit-meta-label">매칭 타 행사</span>
                        <span className="audit-meta-value">{item.matched_other_event_terms.join(', ')}</span>
                      </div>
                    )}

                    {item.ai_used && (
                      <div className="audit-meta-item">
                        <span className="audit-meta-label">AI 판별</span>
                        <span className="audit-meta-value">{item.ai_category} — {item.ai_reason}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default AuditPanel;
