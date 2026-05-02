import React from 'react';

const ICONS = {
  "naver_news": "📰",
  "naver_blog": "📝",
  "youtube": "📺"
};

const SummaryCards = ({ summary }) => {
  if (!summary || summary.length === 0) return null;

  // 전체 통계 (첫 번째 summary entry에서 가져옴 — 모든 entry에 동일 filter_stats가 있음)
  const stats = summary[0] || {};
  const hasFilterStats = stats.public_count !== undefined;

  return (
    <div className="summary-section animate-fade-in" style={{ animationDelay: '0.1s' }}>
      {/* 채널별 카드 */}
      <div className="cards-grid">
        {summary.map((stat, index) => {
          const icon = ICONS[stat.source] || "📊";
          const isError = stat.status === "ERROR";
          const sourcePublicCount = stat.public_count !== undefined ? stat.public_count : stat.deduped_count;
          
          return (
            <div key={stat.source} className="stat-card glass" style={{ animationDelay: `${0.1 + index * 0.1}s` }}>
              <div className="stat-card-header">
                <span className="stat-card-title">{stat.source_label}</span>
                <span className="stat-icon">{icon}</span>
              </div>
              <div className="stat-value">{sourcePublicCount}</div>
              <div className="stat-sub">
                <span>수집: {stat.raw_count} → 중복제거: {stat.deduped_count}</span>
                <span className={!isError ? "success" : "error"}>
                  {isError ? "Error" : "Success"}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* 필터 통계 카드 */}
      {hasFilterStats && (
        <div className="filter-stats-grid animate-fade-in" style={{ animationDelay: '0.25s' }}>
          <div className="filter-mini-card glass">
            <span className="mini-card-icon">📊</span>
            <div className="mini-card-body">
              <span className="mini-card-value">{stats.total_collected_count || 0}</span>
              <span className="mini-card-label">전체 수집</span>
            </div>
          </div>
          <div className="filter-mini-card glass">
            <span className="mini-card-icon">✅</span>
            <div className="mini-card-body">
              <span className="mini-card-value accent">{stats.public_count || 0}</span>
              <span className="mini-card-label">Public 노출</span>
            </div>
          </div>
          <div className="filter-mini-card glass">
            <span className="mini-card-icon">🚫</span>
            <div className="mini-card-body">
              <span className="mini-card-value warning">{stats.excluded_count || 0}</span>
              <span className="mini-card-label">제외</span>
            </div>
          </div>
          {stats.existing_duplicate_skipped_count > 0 && (
            <div className="filter-mini-card glass">
              <span className="mini-card-icon">🔄</span>
              <div className="mini-card-body">
                <span className="mini-card-value">{stats.existing_duplicate_skipped_count}</span>
                <span className="mini-card-label">기존 중복</span>
              </div>
            </div>
          )}
          {stats.ai_used_count > 0 && (
            <div className="filter-mini-card glass">
              <span className="mini-card-icon">🤖</span>
              <div className="mini-card-body">
                <span className="mini-card-value">{stats.ai_used_count}</span>
                <span className="mini-card-label">AI 판별</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SummaryCards;
